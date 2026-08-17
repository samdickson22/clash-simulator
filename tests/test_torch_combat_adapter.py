from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Entity, TargetType, Troop
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.combat import UnsupportedStationaryCombatError
from clasher.torch_sim.combat_adapter import (
    UnsupportedCombatReason,
    project_stationary_combat,
    step_supported_stationary_combat_,
)
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence
from clasher.torch_sim.executor import TorchBattleExecutor

ENABLED_DIRECT_CARDS = ("Knight", "MiniPekka", "Pekka", "Valkyrie")


def _catalog(*extra: str) -> TensorCardCatalog:
    return TensorCardCatalog.compile(
        CardDataLoader(),
        {*ENABLED_DIRECT_CARDS, *extra},
    )


def _enabled_troop(
    name: str,
    entity_id: int,
    player_id: int,
    x: float,
    y: float,
    *,
    cooldown: float,
    deploy_remaining: float = 0.0,
    hp: float | None = None,
    damage: float | None = None,
) -> Troop:
    stats = CardDataLoader().get_card(name)
    assert stats is not None
    scaled_hp = float(stats.scaled_hitpoints or stats.hitpoints or 1.0)
    scaled_damage = float(stats.scaled_damage or stats.damage or 0.0)
    troop = Troop(
        id=entity_id,
        position=Position(x, y),
        player_id=player_id,
        card_stats=stats,
        hitpoints=scaled_hp if hp is None else hp,
        max_hitpoints=scaled_hp if hp is None else hp,
        damage=scaled_damage if damage is None else damage,
        range=float(stats.range or 0.0),
        sight_range=float(stats.sight_range or 0.0),
        speed=float(stats.speed or 0.0),
        target_type=TargetType.BOTH,
        attack_cooldown=cooldown,
        deploy_delay_remaining=deploy_remaining,
        placement_pending=deploy_remaining > 0.0,
    )
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _battle(entities: Sequence[Entity]) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    battle._alive_buildings = []
    battle._alive_building_cache_dirty = False
    for entity in entities:
        setattr(entity, "battle_state", battle)
    return battle


def _clone_entities(entities: Iterable[Troop]) -> list[Troop]:
    clones: list[Troop] = []
    for entity in entities:
        clone = _enabled_troop(
            entity.card_stats.name,
            entity.id,
            entity.player_id,
            entity.position.x,
            entity.position.y,
            cooldown=entity.attack_cooldown,
            deploy_remaining=entity.deploy_delay_remaining,
            hp=entity.hitpoints,
            damage=entity.damage,
        )
        clone.stun_timer = entity.stun_timer
        clone.last_attack_time = entity.last_attack_time
        clones.append(clone)
    return clones


def _oracle_combat_frame(battle: BattleState) -> None:
    for entity in sorted(tuple(battle.entities.values()), key=lambda item: item.id):
        if isinstance(entity, (Troop, Building)):
            entity.update_combat_component(battle.dt, battle)


def _assert_component_state_exact(actual: BattleState, expected: BattleState) -> None:
    assert tuple(actual.entities) == tuple(expected.entities)
    for entity_id in actual.entities:
        left = actual.entities[entity_id]
        right = expected.entities[entity_id]
        assert left.hitpoints == right.hitpoints
        assert left.is_alive is right.is_alive
        assert left.target_id == right.target_id
        assert left.attack_cooldown == right.attack_cooldown
        assert left._attack_preload_blocked is right._attack_preload_blocked
        assert left._attack_windup_active is right._attack_windup_active
        assert getattr(left, "_has_attacked_once", False) is getattr(
            right, "_has_attacked_once", False
        )
        assert hasattr(left, "_has_attacked_once") is hasattr(
            right, "_has_attacked_once"
        )
        assert left.last_attack_time == right.last_attack_time
        assert getattr(left, "_last_combat_target_id", None) == getattr(
            right, "_last_combat_target_id", None
        )
        assert (left._facing_x_units, left._facing_y_units) == (
            right._facing_x_units,
            right._facing_y_units,
        )
        if isinstance(left, Troop) and isinstance(right, Troop):
            assert left._movement_target_id == right._movement_target_id
            assert left.initial_position == right.initial_position
        if isinstance(left, Building) and isinstance(right, Building):
            assert left._tower_active is right._tower_active
            assert left.requires_activation is right.requires_activation
            assert left.activation_delay_remaining == right.activation_delay_remaining
            assert (
                left.activation_first_hit_delay_remaining
                == right.activation_first_hit_delay_remaining
            )


def test_enabled_stationary_direct_combat_projects_and_syncs_exactly() -> None:
    source = [
        _enabled_troop("Knight", 11, 0, 9.0, 13.0, cooldown=0.0),
        _enabled_troop("MiniPekka", 7, 1, 9.0, 14.1, cooldown=0.05),
    ]
    oracle = _battle(_clone_entities(source))
    tensor = _battle(_clone_entities(source))

    projection = project_stationary_combat([tensor], _catalog())
    assert projection.support_mask.tolist() == [True]
    assert projection.unsupported == ()

    _oracle_combat_frame(oracle)
    result = step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    assert result.events.attacked_entity_ids == ((0, 7), (0, 11))
    assert result.events.death_entity_ids == ()


def test_direct_damage_death_and_event_sync_are_exact() -> None:
    source = [
        _enabled_troop("MiniPekka", 1, 0, 9.0, 10.0, cooldown=0.0, damage=125.0),
        _enabled_troop(
            "Knight",
            2,
            1,
            9.0,
            10.7,
            cooldown=10.0,
            deploy_remaining=1.0,
            hp=100.0,
        ),
    ]
    oracle = _battle(_clone_entities(source))
    tensor = _battle(_clone_entities(source))
    _oracle_combat_frame(oracle)

    result = step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    assert result.events.attacked_entity_ids == ((0, 1),)
    assert result.events.death_entity_ids == ((0, 2),)
    victim = next(
        mutation for mutation in result.events.mutations if mutation.entity_id == 2
    )
    assert victim.hp_before == 100.0
    assert victim.hp_after == 0.0
    assert victim.died


def test_entity_killed_before_its_id_order_turn_gets_no_combat_mutations() -> None:
    source = [
        _enabled_troop("MiniPekka", 1, 0, 9.0, 10.0, cooldown=0.0, damage=125.0),
        _enabled_troop("Knight", 2, 1, 9.0, 10.7, cooldown=8.0, hp=100.0),
    ]
    oracle = _battle(_clone_entities(source))
    tensor = _battle(_clone_entities(source))
    _oracle_combat_frame(oracle)

    step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    victim = tensor.entities[2]
    assert isinstance(victim, Troop)
    assert victim.initial_position is None
    assert not hasattr(victim, "_last_combat_target_id")


def test_enabled_valkyrie_area_damage_syncs_exactly() -> None:
    source = [
        _enabled_troop("Valkyrie", 1, 0, 9.0, 10.0, cooldown=0.0),
        _enabled_troop("Knight", 2, 1, 9.0, 10.8, cooldown=8.0, deploy_remaining=1.0),
        _enabled_troop("Knight", 3, 1, 9.7, 10.8, cooldown=8.0, deploy_remaining=1.0),
        _enabled_troop("Knight", 4, 1, 12.0, 10.8, cooldown=8.0, deploy_remaining=1.0),
    ]
    oracle = _battle(_clone_entities(source))
    tensor = _battle(_clone_entities(source))
    _oracle_combat_frame(oracle)

    step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    assert tensor.entities[2].hitpoints < source[1].hitpoints
    assert tensor.entities[3].hitpoints < source[2].hitpoints
    assert tensor.entities[4].hitpoints == source[3].hitpoints


def test_randomized_batched_enabled_stationary_crowds_match_exactly() -> None:
    oracle_battles: list[BattleState] = []
    tensor_battles: list[BattleState] = []
    for seed in range(12):
        rng = random.Random(920_000 + seed)
        source: list[Troop] = []
        for entity_id in range(1, 5):
            source.append(
                _enabled_troop(
                    rng.choice(ENABLED_DIRECT_CARDS),
                    entity_id,
                    0,
                    (8_400 + rng.randrange(1_201)) / 1000.0,
                    (9_300 + rng.randrange(601)) / 1000.0,
                    cooldown=rng.choice((0.0, 0.05, 0.2, 0.6)),
                )
            )
        for entity_id in range(10, 26):
            target = _enabled_troop(
                rng.choice(ENABLED_DIRECT_CARDS),
                entity_id,
                1,
                (7_700 + rng.randrange(2_601)) / 1000.0,
                (10_200 + rng.randrange(1_801)) / 1000.0,
                cooldown=8.0,
                deploy_remaining=1.0,
                hp=float(rng.choice((90, 180, 350, 900))),
            )
            source.append(target)
        rng.shuffle(source)
        oracle_battles.append(_battle(_clone_entities(source)))
        tensor_battles.append(_battle(_clone_entities(source)))

    for oracle in oracle_battles:
        _oracle_combat_frame(oracle)
    result = step_supported_stationary_combat_(tensor_battles, _catalog())

    assert result.projection.support_mask.tolist() == [True] * 12
    for tensor, oracle in zip(tensor_battles, oracle_battles, strict=True):
        _assert_component_state_exact(tensor, oracle)


def test_standard_six_crown_tower_combat_frame_is_supported_exactly() -> None:
    seed = BattleState(fast_path=False)
    oracle = seed.clone()
    tensor = seed.clone()
    _oracle_combat_frame(oracle)

    projection = project_stationary_combat([tensor], _catalog())
    assert projection.support_mask.tolist() == [True]
    assert projection.unsupported == ()
    step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    dormant_kings = [
        entity
        for entity in tensor.entities.values()
        if isinstance(entity, Building) and entity._crown_tower_slot == "king"
    ]
    assert len(dormant_kings) == 2
    assert all(not king._tower_active for king in dormant_kings)
    assert all(king.last_attack_time == 0.0 for king in dormant_kings)


def test_princess_tower_target_and_clock_match_with_standard_towers_present() -> None:
    seed = BattleState(fast_path=False)
    red_left = next(
        entity
        for entity in seed.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity._crown_tower_slot == "left"
    )
    troop = _enabled_troop(
        "Knight",
        seed.next_entity_id,
        0,
        red_left.position.x,
        red_left.position.y - 1.5,
        cooldown=5.0,
        deploy_remaining=1.0,
    )
    setattr(troop, "battle_state", seed)
    seed.entities[troop.id] = troop
    seed.next_entity_id += 1
    oracle = seed.clone()
    tensor = seed.clone()
    _oracle_combat_frame(oracle)

    step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    tensor_red_left = tensor.entities[red_left.id]
    assert tensor_red_left.target_id == troop.id
    assert tensor_red_left.attack_cooldown == 0.75
    next_projection = project_stationary_combat([tensor], _catalog())
    assert next_projection.support_mask.tolist() == [False]
    assert UnsupportedCombatReason.RETAINED_COMBAT_LOCK in {
        item.reason for item in next_projection.unsupported
    }


def test_direct_crown_damage_activates_dormant_king_after_its_turn_exactly() -> None:
    seed = BattleState(fast_path=False)
    blue_king = next(
        entity
        for entity in seed.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 0
        and entity._crown_tower_slot == "king"
    )
    attacker = _enabled_troop(
        "Knight",
        seed.next_entity_id,
        1,
        blue_king.position.x,
        blue_king.position.y + 1.0,
        cooldown=0.0,
        damage=100.0,
    )
    attacker.target_id = blue_king.id
    setattr(attacker, "battle_state", seed)
    seed.entities[attacker.id] = attacker
    seed.next_entity_id += 1
    oracle = seed.clone()
    tensor = seed.clone()
    _oracle_combat_frame(oracle)

    projection = project_stationary_combat([tensor], _catalog())
    assert projection.support_mask.tolist() == [True]
    result = step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    tensor_king = tensor.entities[blue_king.id]
    assert isinstance(tensor_king, Building)
    assert tensor_king._tower_active
    assert tensor_king.activation_delay_remaining == 3.3
    assert tensor_king.activation_first_hit_delay_remaining == 0.7
    assert tensor_king.hitpoints == blue_king.hitpoints - 100.0
    assert result.events.attacked_entity_ids == ((0, attacker.id),)
    assert tensor._win_conditions_dirty is oracle._win_conditions_dirty


def test_active_king_activation_countdown_is_tensor_owned() -> None:
    seed = BattleState(fast_path=False)
    blue_king = next(
        entity
        for entity in seed.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 0
        and entity._crown_tower_slot == "king"
    )
    blue_king.activate()
    oracle = seed.clone()
    tensor = seed.clone()
    _oracle_combat_frame(oracle)

    projection = project_stationary_combat([tensor], _catalog())
    assert projection.support_mask.tolist() == [True]
    step_supported_stationary_combat_([tensor], _catalog())

    _assert_component_state_exact(tensor, oracle)
    tensor_king = tensor.entities[blue_king.id]
    assert isinstance(tensor_king, Building)
    assert tensor_king.activation_delay_remaining == 3.25
    assert tensor_king.last_attack_time == 0.0


def test_batched_standard_towers_and_randomized_direct_crown_damage_are_exact() -> None:
    oracle_battles: list[BattleState] = []
    tensor_battles: list[BattleState] = []
    for seed_value in range(8):
        rng = random.Random(771_000 + seed_value)
        seed = BattleState(fast_path=False)
        owner = seed_value % 2
        enemy_towers = [
            entity
            for entity in seed.entities.values()
            if isinstance(entity, Building) and entity.player_id != owner
        ]
        target = rng.choice(enemy_towers)
        direction = 1.0 if owner == 0 else -1.0
        attacker = _enabled_troop(
            rng.choice(ENABLED_DIRECT_CARDS),
            seed.next_entity_id,
            owner,
            target.position.x,
            target.position.y - direction,
            cooldown=0.0,
            damage=float(rng.choice((35, 80, 160))),
        )
        attacker.target_id = target.id
        setattr(attacker, "battle_state", seed)
        seed.entities[attacker.id] = attacker
        seed.next_entity_id += 1
        oracle_battles.append(seed.clone())
        tensor_battles.append(seed.clone())

    for oracle in oracle_battles:
        _oracle_combat_frame(oracle)
    result = step_supported_stationary_combat_(tensor_battles, _catalog())

    assert result.projection.support_mask.tolist() == [True] * 8
    for tensor, oracle in zip(tensor_battles, oracle_battles, strict=True):
        _assert_component_state_exact(tensor, oracle)


def test_ready_crown_projectile_remains_explicitly_fail_closed() -> None:
    battle = BattleState(fast_path=False)
    princess = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building) and entity._crown_tower_slot == "left"
    )
    princess.attack_cooldown = 0.0

    projection = project_stationary_combat([battle], _catalog())

    assert projection.support_mask.tolist() == [False]
    assert UnsupportedCombatReason.PROJECTILE_ATTACK in {
        item.reason for item in projection.unsupported if item.entity_id == princess.id
    }


def test_executor_routes_deploying_target_with_crown_combat_to_exact_runtime() -> None:
    candidate = BattleState(fast_path=False)
    red_left = next(
        entity
        for entity in candidate.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity._crown_tower_slot == "left"
    )
    troop = _enabled_troop(
        "Knight",
        candidate.next_entity_id,
        0,
        red_left.position.x,
        red_left.position.y - 3.0,
        cooldown=5.0,
        deploy_remaining=1.0,
    )
    # The complete stationary runtime owns this case. A nonzero natural speed
    # would correctly route to Python until movement integration is selected.
    troop.speed = 0.0
    setattr(troop, "battle_state", candidate)
    candidate.entities[troop.id] = troop
    candidate.next_entity_id += 1
    oracle = candidate.clone()
    oracle.step_logic_ticks(1)
    executor = TorchBattleExecutor("pytorch")

    assert executor.step_logic_ticks(candidate, 1) == 1

    assert first_divergence(battle_snapshot(oracle), battle_snapshot(candidate)) is None
    assert executor.metrics.tensor_ticks == 1
    assert executor.metrics.python_ticks == 0
    assert executor.metrics.unsupported_fallbacks == 0


@pytest.mark.parametrize(
    ("name", "mutate", "reason"),
    (
        (
            "ArcherQueen",
            lambda entity: None,
            UnsupportedCombatReason.SERIALIZED_MECHANIC,
        ),
        (
            "Musketeer",
            lambda entity: None,
            UnsupportedCombatReason.PROJECTILE_ATTACK,
        ),
        (
            "Knight",
            lambda entity: setattr(entity, "_last_combat_target_id", 99),
            UnsupportedCombatReason.RETAINED_COMBAT_LOCK,
        ),
        (
            "Prince",
            lambda entity: None,
            UnsupportedCombatReason.CHARGE_OR_KAMIKAZE,
        ),
        (
            "Knight",
            lambda entity: setattr(entity, "_river_jump_active", True),
            UnsupportedCombatReason.TARGETABILITY_STATE,
        ),
    ),
)
def test_unrepresented_enabled_state_is_explicitly_fail_closed(
    name: str,
    mutate: object,
    reason: UnsupportedCombatReason,
) -> None:
    entity = _enabled_troop(name, 1, 0, 9.0, 10.0, cooldown=0.0)
    assert callable(mutate)
    mutate(entity)
    battle = _battle([entity])
    projection = project_stationary_combat(
        [battle], _catalog("ArcherQueen", "Musketeer", "Prince")
    )

    assert projection.support_mask.tolist() == [False]
    assert reason in {item.reason for item in projection.unsupported}
    before = (entity.hitpoints, entity.target_id, entity.attack_cooldown)
    with pytest.raises(UnsupportedStationaryCombatError):
        step_supported_stationary_combat_(
            [battle], _catalog("ArcherQueen", "Musketeer", "Prince")
        )
    assert (entity.hitpoints, entity.target_id, entity.attack_cooldown) == before


def test_projection_capacity_guard_is_non_mutating() -> None:
    entities = [
        _enabled_troop("Knight", index, index % 2, 9.0, 10.0, cooldown=1.0)
        for index in range(1, 4)
    ]
    battle = _battle(entities)
    with pytest.raises(ValueError, match="cannot hold"):
        project_stationary_combat([battle], _catalog(), capacity=2)
    assert tuple(battle.entities) == (1, 2, 3)
