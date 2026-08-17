import json
from copy import deepcopy
from pathlib import Path

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.entities import Troop
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.shield_champion import (
    NEVER_USED_TIME_MS,
    TensorShieldChampionCatalog,
    activate_champion_abilities_,
    apply_shield_damage_,
    champion_button_owner_mask,
    champion_can_activate,
    champion_owner_mask,
    refresh_champion_ownership_,
    tick_champion_abilities_,
)


def _enabled_names(loader: CardDataLoader) -> set[str]:
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    return {
        resolve_card_name(card, definitions) for deck in decks for card in deck["cards"]
    }


def _spawn_one(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player_id, stats)
    assert isinstance(entity, Troop)
    return entity


def test_catalog_compiles_enabled_shield_and_champion_parameters_from_factory() -> None:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    catalog = TensorShieldChampionCatalog.compile(loader, _enabled_names(loader))

    shield_rows = (catalog.mechanic_opcode == MECHANIC_OPCODE["Shield"]).nonzero()
    cloak_rows = (
        catalog.mechanic_opcode == MECHANIC_OPCODE["ArcherQueenCloak"]
    ).nonzero()
    assert shield_rows.shape[0] == 2
    assert cloak_rows.shape[0] == 1

    for card_id, slot in shield_rows.tolist():
        name = catalog.names[card_id]
        stats = loader.get_card(name)
        assert stats is not None
        mechanic = definitions[name].mechanics[slot]
        assert catalog.shield_hitpoints[card_id, slot].item() == pytest.approx(
            stats.get_scaled_stat(mechanic.shield_hp)
        )

    card_id, slot = cloak_rows[0].tolist()
    mechanic = definitions[catalog.names[card_id]].mechanics[slot]
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    entity = _spawn_one(battle, catalog.names[card_id], 0, Position(9.0, 12.0))
    attached = entity.mechanics[slot]
    assert (
        catalog.ability_elixir_cost[card_id, slot].item()
        == attached.ability.elixir_cost
    )
    assert (
        catalog.ability_cooldown_ms[card_id, slot].item()
        == attached.ability.cooldown_ms
    )
    assert (
        catalog.ability_duration_ms[card_id, slot].item()
        == attached.ability.duration_ms
    )
    assert catalog.ability_effect_count[card_id, slot].item() == 0
    assert catalog.attack_speed_multiplier[card_id, slot].item() == pytest.approx(
        mechanic.attack_speed_multiplier
    )
    assert catalog.movement_speed_multiplier[card_id, slot].item() == pytest.approx(
        mechanic.movement_speed_multiplier
    )
    assert catalog.cast_time_ms[card_id, slot].item() == mechanic.cast_time_ms
    assert catalog.trigger_delay_ms[card_id, slot].item() == mechanic.trigger_delay_ms


def test_catalog_marks_nonempty_champion_effect_payload_for_fail_closed_routing() -> (
    None
):
    loader = CardDataLoader()
    catalog = TensorShieldChampionCatalog.compile(
        loader, loader.load_card_definitions()
    )
    ability_rows = catalog.ability_duration_ms > 0
    nested_rows = ability_rows & (catalog.ability_effect_count > 0)

    assert ability_rows.sum().item() == 2
    assert nested_rows.sum().item() == 1


def test_catalog_hydrates_overridden_serialized_ability_data_like_oracle_attach() -> (
    None
):
    loader = CardDataLoader()
    stats = loader.get_card("ArcherQueen")
    assert stats is not None
    stats._raw_entry = deepcopy(stats._raw_entry)
    ability_data = stats._raw_entry["summonCharacterData"]["abilityData"]
    ability_data.update(
        {
            "manaCost": 2,
            "cooldown": 12_345,
            "buffTime": 2_345,
            "castTime": 456,
            "triggerDelay": 78,
        }
    )
    ability_data["buffData"].update({"hitSpeedMultiplier": 175, "speedMultiplier": -40})

    catalog = TensorShieldChampionCatalog.compile(loader, [stats.name])
    row = (catalog.mechanic_opcode == MECHANIC_OPCODE["ArcherQueenCloak"]).nonzero()
    assert row.shape[0] == 1
    card_id, slot = row[0].tolist()

    battle = BattleState(card_loader=loader)
    battle.entities.clear()
    battle.next_entity_id = 1
    entity = _spawn_one(battle, stats.name, 0, Position(9.0, 12.0))
    attached = entity.mechanics[slot]

    assert catalog.ability_elixir_cost[card_id, slot].item() == 2
    assert (
        catalog.ability_elixir_cost[card_id, slot].item()
        == attached.ability.elixir_cost
    )
    assert catalog.ability_cooldown_ms[card_id, slot].item() == 12_345
    assert (
        catalog.ability_cooldown_ms[card_id, slot].item()
        == attached.ability.cooldown_ms
    )
    assert catalog.ability_duration_ms[card_id, slot].item() == 2_345
    assert (
        catalog.ability_duration_ms[card_id, slot].item()
        == attached.ability.duration_ms
    )
    assert catalog.cast_time_ms[card_id, slot].item() == attached.cast_time_ms == 456
    assert (
        catalog.trigger_delay_ms[card_id, slot].item()
        == attached.trigger_delay_ms
        == 78
    )
    assert catalog.attack_speed_multiplier[card_id, slot].item() == pytest.approx(
        attached.attack_speed_multiplier
    )
    assert catalog.movement_speed_multiplier[card_id, slot].item() == pytest.approx(
        attached.movement_speed_multiplier
    )


def test_batched_shield_hits_match_serialized_oracle_and_emit_break_events() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    entities = [
        _spawn_one(battle, "DarkPrince", 0, Position(8.0, 12.0)),
        _spawn_one(battle, "Guards", 1, Position(10.0, 12.0)),
    ]
    mechanics = [
        next(item for item in entity.mechanics if type(item).__name__ == "Shield")
        for entity in entities
    ]
    current = torch.tensor(
        [[mechanic.current_shield for mechanic in mechanics]], dtype=torch.float64
    )
    break_count = torch.zeros_like(current, dtype=torch.int64)
    present = torch.ones_like(current, dtype=torch.bool)
    hits = (
        (0.0, -5.0),
        (40.0, 25.0),
        (54.0, 75.0),
        (999.0, 1.0),
    )

    for hit_values in hits:
        expected_damage = [
            mechanic.modify_incoming_damage(entity, amount)
            for mechanic, entity, amount in zip(mechanics, entities, hit_values)
        ]
        result = apply_shield_damage_(
            current,
            break_count,
            torch.tensor([hit_values], dtype=torch.float64),
            present,
        )
        assert result.hitpoint_damage.tolist()[0] == pytest.approx(expected_damage)
        assert current.tolist()[0] == pytest.approx(
            [mechanic.current_shield for mechanic in mechanics]
        )
        assert break_count.tolist()[0] == [
            entity._shield_break_count for entity in entities
        ]
        assert result.shield_broken.tolist()[0] == [
            amount > 0
            and expected == 0
            and mechanic.current_shield == 0
            and entity._shield_break_count == 1
            for amount, expected, mechanic, entity in zip(
                hit_values, expected_damage, mechanics, entities
            )
        ]


def test_champion_owner_and_button_selection_match_oracle_duplicate_rules() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    first = _spawn_one(battle, "ArcherQueen", 0, Position(7.0, 12.0))
    second = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    opponent = _spawn_one(battle, "ArcherQueen", 1, Position(11.0, 20.0))
    entities = [first, second, opponent]
    entity_id = torch.tensor([[entity.id for entity in entities]])
    player = torch.tensor([[entity.player_id for entity in entities]])
    ability_key = torch.ones_like(entity_id)
    has_ability = torch.ones_like(entity_id, dtype=torch.bool)

    for live_values in ((True, True, True), (True, False, True)):
        for entity, live in zip(entities, live_values):
            entity.is_alive = live
        alive = torch.tensor([live_values])
        owners = champion_owner_mask(entity_id, player, ability_key, alive, has_ability)
        expected = [battle.is_champion_ability_owner(entity) for entity in entities]
        assert owners.tolist()[0] == expected
        assert champion_button_owner_mask(owners, entity_id, player).tolist()[0] == (
            expected
        )


def test_champion_ownership_transfer_resets_only_selected_owner_cooldown() -> None:
    recorded = torch.zeros((1, 2, 2), dtype=torch.int64)
    entity_id = torch.tensor([[4, 7]], dtype=torch.int64)
    player = torch.tensor([[0, 0]], dtype=torch.int64)
    ability_key = torch.tensor([[1, 1]], dtype=torch.int64)
    alive = torch.tensor([[True, False]])
    has_ability = torch.ones_like(alive)
    last_use = torch.tensor([[123, 456]], dtype=torch.int64)

    initial = refresh_champion_ownership_(
        entity_id=entity_id,
        entity_player=player,
        ability_key=ability_key,
        alive=alive,
        has_ability=has_ability,
        recorded_owner_id=recorded,
        last_use_time_ms=last_use,
    )
    assert initial.owner.tolist() == [[True, False]]
    assert initial.transferred.tolist() == [[True, False]]
    assert last_use.tolist() == [[NEVER_USED_TIME_MS, 456]]
    assert recorded[0, 0, 1].item() == 4

    last_use[0, 0] = 123
    alive[0, 1] = True
    placed = refresh_champion_ownership_(
        entity_id=entity_id,
        entity_player=player,
        ability_key=ability_key,
        alive=alive,
        has_ability=has_ability,
        recorded_owner_id=recorded,
        last_use_time_ms=last_use,
    )
    assert placed.owner.tolist() == [[False, True]]
    assert placed.transferred.tolist() == [[False, True]]
    assert last_use.tolist() == [[123, NEVER_USED_TIME_MS]]
    assert recorded[0, 0, 1].item() == 7

    last_use[0, 1] = 456
    alive[0, 1] = False
    died = refresh_champion_ownership_(
        entity_id=entity_id,
        entity_player=player,
        ability_key=ability_key,
        alive=alive,
        has_ability=has_ability,
        recorded_owner_id=recorded,
        last_use_time_ms=last_use,
    )
    assert died.owner.tolist() == [[True, False]]
    assert died.transferred.tolist() == [[True, False]]
    assert last_use.tolist() == [[NEVER_USED_TIME_MS, 456]]
    assert recorded[0, 0, 1].item() == 4


def test_cloak_activation_and_all_integer_deadlines_match_python_oracle() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    queen.deploy_delay_remaining = 0.0
    queen.placement_pending = False
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0

    shape = (1, 1)
    now_ms = torch.tensor([0], dtype=torch.int64)
    player_elixir = torch.tensor([[10.0, 10.0]], dtype=torch.float64)
    entity_player = torch.tensor([[0]], dtype=torch.int64)
    owner = torch.ones(shape, dtype=torch.bool)
    alive = torch.ones(shape, dtype=torch.bool)
    placement_pending = torch.zeros(shape, dtype=torch.bool)
    deploy_delay = torch.zeros(shape, dtype=torch.float64)
    stunned = torch.ones(shape, dtype=torch.bool)
    last_use = torch.full(shape, NEVER_USED_TIME_MS, dtype=torch.int64)
    is_active = torch.zeros(shape, dtype=torch.bool)
    activation_time = torch.zeros(shape, dtype=torch.int64)
    cost = torch.tensor([[mechanic.ability.elixir_cost]], dtype=torch.int64)
    cooldown = torch.tensor([[mechanic.ability.cooldown_ms]], dtype=torch.int64)
    duration = torch.tensor([[mechanic.ability.duration_ms]], dtype=torch.int64)
    pending_until = torch.full(shape, -1, dtype=torch.int64)
    cast_lock_until = torch.full(shape, -1, dtype=torch.int64)
    attack_mode = torch.ones(shape, dtype=torch.float64)
    movement_mode = torch.ones(shape, dtype=torch.float64)
    original_movement_mode = torch.full(shape, torch.nan, dtype=torch.float64)
    stealth_until = torch.zeros(shape, dtype=torch.int64)

    can_activate = champion_can_activate(
        now_ms=now_ms,
        player_elixir=player_elixir,
        entity_player=entity_player,
        button_owner=owner,
        alive=alive,
        placement_pending=placement_pending,
        deploy_delay_seconds=deploy_delay,
        stunned=stunned,
        can_execute_while_frozen=True,
        last_use_time_ms=last_use,
        is_active=is_active,
        activation_time_ms=activation_time,
        elixir_cost=cost,
        cooldown_ms=cooldown,
        duration_ms=duration,
    )
    assert can_activate.item() == mechanic.can_activate_ability(queen)
    assert mechanic.activate_ability(queen)
    activated = activate_champion_abilities_(
        requested_players=torch.tensor([[True, False]]),
        can_activate=can_activate,
        now_ms=now_ms,
        player_elixir=player_elixir,
        entity_player=entity_player,
        last_use_time_ms=last_use,
        is_active=is_active,
        activation_time_ms=activation_time,
        elixir_cost=cost,
        cloak_mask=torch.ones(shape, dtype=torch.bool),
        trigger_delay_ms=torch.tensor([[mechanic.trigger_delay_ms]]),
        cast_time_ms=torch.tensor([[mechanic.cast_time_ms]]),
        cloak_pending_until_ms=pending_until,
        cast_lock_until_ms=cast_lock_until,
    )
    assert activated.item()
    assert player_elixir[0, 0].item() == battle.players[0].elixir
    assert last_use.item() == mechanic.ability.last_use_time
    assert activation_time.item() == mechanic.ability.activation_time
    assert pending_until.item() == mechanic._cloak_pending_until
    assert cast_lock_until.item() == mechanic._cast_lock_until

    for deadline_ms in (199, 200, 900, 950, 3650, 3700):
        battle.time = deadline_ms / 1000.0
        mechanic.on_tick(queen, 50)
        now_ms[0] = deadline_ms
        tick_champion_abilities_(
            now_ms=now_ms,
            alive=alive,
            cancel_before_effect=torch.zeros(shape, dtype=torch.bool),
            last_use_time_ms=last_use,
            is_active=is_active,
            activation_time_ms=activation_time,
            duration_ms=duration,
            cloak_mask=torch.ones(shape, dtype=torch.bool),
            cloak_pending_until_ms=pending_until,
            cast_lock_until_ms=cast_lock_until,
            attack_speed_multiplier=torch.tensor(
                [[mechanic.attack_speed_multiplier]], dtype=torch.float64
            ),
            movement_speed_multiplier=torch.tensor(
                [[mechanic.movement_speed_multiplier]], dtype=torch.float64
            ),
            attack_mode_multiplier=attack_mode,
            movement_mode_multiplier=movement_mode,
            original_movement_mode_multiplier=original_movement_mode,
            stealth_until_ms=stealth_until,
        )
        assert is_active.item() == mechanic.ability.is_active
        assert (pending_until.item() if pending_until.item() >= 0 else None) == (
            mechanic._cloak_pending_until
        )
        assert (cast_lock_until.item() if cast_lock_until.item() >= 0 else None) == (
            mechanic._cast_lock_until
        )
        assert attack_mode.item() == pytest.approx(queen.attack_mode_multiplier)
        assert movement_mode.item() == pytest.approx(queen.movement_mode_multiplier)
        assert stealth_until.item() == queen._stealth_until

    for deadline_ms, expected in ((20_699, False), (20_700, True)):
        battle.time = deadline_ms / 1000.0
        now_ms[0] = deadline_ms
        actual = champion_can_activate(
            now_ms=now_ms,
            player_elixir=player_elixir,
            entity_player=entity_player,
            button_owner=owner,
            alive=alive,
            placement_pending=placement_pending,
            deploy_delay_seconds=deploy_delay,
            stunned=stunned,
            can_execute_while_frozen=True,
            last_use_time_ms=last_use,
            is_active=is_active,
            activation_time_ms=activation_time,
            elixir_cost=cost,
            cooldown_ms=cooldown,
            duration_ms=duration,
        )
        assert actual.item() is expected
        assert actual.item() == mechanic.can_activate_ability(queen)


def test_cloak_death_before_trigger_cancels_pending_state_like_oracle() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    queen.deploy_delay_remaining = 0.0
    queen.placement_pending = False
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0
    assert mechanic.activate_ability(queen)

    shape = (1, 1)
    last_use = torch.tensor([[mechanic.ability.last_use_time]], dtype=torch.int64)
    activation_time = torch.tensor(
        [[mechanic.ability.activation_time]], dtype=torch.int64
    )
    is_active = torch.tensor([[mechanic.ability.is_active]])
    pending_until = torch.tensor([[mechanic._cloak_pending_until]], dtype=torch.int64)
    cast_lock_until = torch.tensor([[mechanic._cast_lock_until]], dtype=torch.int64)
    attack_mode = torch.ones(shape, dtype=torch.float64)
    movement_mode = torch.ones(shape, dtype=torch.float64)
    original_movement_mode = torch.full(shape, torch.nan, dtype=torch.float64)
    stealth_until = torch.zeros(shape, dtype=torch.int64)

    queen.take_damage(queen.hitpoints)
    result = tick_champion_abilities_(
        now_ms=torch.tensor([0], dtype=torch.int64),
        alive=torch.zeros(shape, dtype=torch.bool),
        cancel_before_effect=torch.zeros(shape, dtype=torch.bool),
        last_use_time_ms=last_use,
        is_active=is_active,
        activation_time_ms=activation_time,
        duration_ms=torch.tensor([[mechanic.duration_ms]], dtype=torch.int64),
        cloak_mask=torch.ones(shape, dtype=torch.bool),
        cloak_pending_until_ms=pending_until,
        cast_lock_until_ms=cast_lock_until,
        attack_speed_multiplier=torch.tensor(
            [[mechanic.attack_speed_multiplier]], dtype=torch.float64
        ),
        movement_speed_multiplier=torch.tensor(
            [[mechanic.movement_speed_multiplier]], dtype=torch.float64
        ),
        attack_mode_multiplier=attack_mode,
        movement_mode_multiplier=movement_mode,
        original_movement_mode_multiplier=original_movement_mode,
        stealth_until_ms=stealth_until,
    )

    assert result.died.item()
    assert not result.cloak_started.item()
    assert not is_active.item()
    assert not mechanic.ability.is_active
    assert pending_until.item() == -1
    assert mechanic._cloak_pending_until is None
    assert cast_lock_until.item() == -1
    assert mechanic._cast_lock_until is None
    assert last_use.item() == mechanic.ability.last_use_time
    assert activation_time.item() == mechanic.ability.activation_time
    assert attack_mode.item() == queen.attack_mode_multiplier
    assert movement_mode.item() == queen.movement_mode_multiplier
    assert stealth_until.item() == queen._stealth_until
