from __future__ import annotations

import copy
import random
from types import MethodType
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, TargetType, Troop
from clasher.mechanics.shared.spawner import PeriodicSpawner
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.passive_mechanics import (
    STEALTH_FOREVER_MS,
    PassiveEventOpcode,
    TensorPassiveCatalog,
    TensorPassiveState,
    UnsupportedPassiveDeviceError,
    collect_souls_,
    consume_souls_,
    plan_soul_drops,
    step_hide_when_idle_,
    step_invisibility_when_not_attacking_,
    step_passive_object_phase_,
    validate_passive_device,
)
from clasher.torch_sim.rng import TensorPythonRandom

PASSIVE_NAMES = (
    "Tesla",
    "RoyalGhost",
    "SkeletonKing",
    "Witch",
    "NightWitch",
    "Tombstone",
    "Knight",
)


def _catalog(device: str | torch.device = "cpu") -> TensorPassiveCatalog:
    return TensorPassiveCatalog.compile(
        BattleState().card_loader, PASSIVE_NAMES, device=device
    )


def _entity(
    entity_id: int,
    player: int,
    stats: object,
    position: Position,
) -> Entity:
    common: dict[str, Any] = dict(
        id=entity_id,
        position=position,
        player_id=player,
        card_stats=stats,
        hitpoints=float(getattr(stats, "scaled_hitpoints", None) or 100.0),
        max_hitpoints=float(getattr(stats, "scaled_hitpoints", None) or 100.0),
        damage=float(getattr(stats, "scaled_damage", None) or 0.0),
        range=float(getattr(stats, "range", None) or 0.0),
        sight_range=float(getattr(stats, "sight_range", None) or 5.5),
    )
    if str(getattr(stats, "card_type", "")).casefold() == "building":
        return Building(**common)
    return Troop(
        **common,
        speed=float(getattr(stats, "speed", None) or 0.0),
        target_type=TargetType.BOTH,
    )


def _state(
    catalog: TensorPassiveCatalog,
    names: list[list[str]],
    ids: list[list[int]],
    players: list[list[int]],
    positions: list[list[tuple[float, float]]],
    *,
    alive: list[list[bool]] | bool = True,
) -> TensorPassiveState:
    return TensorPassiveState.from_entities(
        catalog,
        entity_id=torch.tensor(ids, dtype=torch.int64, device=catalog.device),
        card_id=torch.tensor(
            [[catalog.name_to_id[name] for name in row] for row in names],
            dtype=torch.int64,
            device=catalog.device,
        ),
        player=torch.tensor(players, dtype=torch.int8, device=catalog.device),
        x_units=torch.tensor(
            [[round(x * 1000) for x, _ in row] for row in positions],
            dtype=torch.int64,
            device=catalog.device,
        ),
        y_units=torch.tensor(
            [[round(y * 1000) for _, y in row] for row in positions],
            dtype=torch.int64,
            device=catalog.device,
        ),
        alive=torch.as_tensor(alive, dtype=torch.bool, device=catalog.device),
    )


def test_catalog_covers_every_factory_emitted_passive_with_serialized_parameters() -> (
    None
):
    loader = BattleState().card_loader
    definitions = loader.load_card_definitions()
    catalog = TensorPassiveCatalog.compile(loader, definitions)
    relevant = {
        "HideWhenIdle",
        "InvisibilityWhenNotAttacking",
        "SkeletonKingSoulCollector",
        "PeriodicSpawner",
    }
    expected = 0
    for name, definition in definitions.items():
        card_id = catalog.name_to_id[name]
        for slot, mechanic in enumerate(definition.mechanics):
            operation = type(mechanic).__name__
            if operation not in relevant:
                continue
            expected += 1
            assert (
                catalog.mechanic_opcode[card_id, slot].item()
                == (MECHANIC_OPCODE[operation])
            )
            if operation == "HideWhenIdle":
                stats = loader.get_card(name)
                assert stats is not None
                character = stats._raw_entry["summonCharacterData"]
                assert catalog.hide_delay_ms[card_id, slot].item() == (
                    character.get("hideTimeMS") or character.get("hideTimeMs")
                )
                assert catalog.rise_time_ms[card_id, slot].item() == (
                    character.get("upTimeMS") or character.get("upTimeMs")
                )
            elif operation == "InvisibilityWhenNotAttacking":
                attached = copy.deepcopy(mechanic)
                stats = loader.get_card(name)
                assert stats is not None
                attached.on_attach(type("EntityStub", (), {"card_stats": stats})())
                assert catalog.fade_delay_ms[card_id, slot].item() == (
                    getattr(attached, "fade_delay_ms")
                )
                assert catalog.fade_use_attack_range[card_id, slot].item() is (
                    getattr(attached, "use_attack_range")
                )
            elif operation == "SkeletonKingSoulCollector":
                assert catalog.soul_radius_units[card_id, slot].item() == round(
                    getattr(mechanic, "soul_collection_radius") * 1000
                )
                assert catalog.souls_per_activation[card_id, slot].item() == (
                    getattr(mechanic, "souls_per_activation")
                )
                assert catalog.max_souls[card_id, slot].item() == getattr(
                    mechanic, "max_souls"
                )
            else:
                assert catalog.periodic_operation_row[card_id, slot].item() >= 0
    assert expected >= 10


def test_hide_when_idle_clock_target_reversal_stun_and_speed_match_oracle() -> None:
    battle = BattleState()
    battle.entities.clear()
    stats = battle.card_loader.get_card("Tesla")
    target_stats = battle.card_loader.get_card("Knight")
    assert stats is not None and target_stats is not None
    tesla = _entity(1, 0, stats, Position(9.0, 12.0))
    target = _entity(2, 1, target_stats, Position(9.0, 25.0))
    battle.entities = {1: tesla, 2: target}
    setattr(tesla, "battle_state", battle)
    setattr(target, "battle_state", battle)
    for mechanic in tesla.mechanics:
        mechanic.on_attach(tesla)
    # Plain construction does not attach factory mechanics; use the detected
    # serialized operation exactly as the battle factory does.
    mechanic = copy.deepcopy(
        battle.card_loader.load_card_definitions()["Tesla"].mechanics[0]
    )
    tesla.mechanics = [mechanic]
    mechanic.on_attach(tesla)
    catalog = _catalog()
    state = _state(
        catalog,
        [["Tesla"]],
        [[1]],
        [[0]],
        [[(9.0, 12.0)]],
    )
    state.target_slot[0, 0] = 7

    timeline = [
        (400, False, False, 1.0, 1.0),
        (400, False, False, 1.0, 1.0),
        (100, False, False, 1.0, 1.0),
        (200, True, False, 1.0, 1.0),
        (200, True, True, 1.0, 1.0),
        (500, True, False, 0.5, 1.3),
    ]
    for dt_ms, has_target, stunned, slow, buff in timeline:
        target.position = Position(9.0, 13.0) if has_target else Position(9.0, 25.0)
        tesla.stun_timer = 1.0 if stunned else 0.0
        tesla.slow_multiplier = slow
        tesla.movement_speed_buff_multiplier = buff
        mechanic.on_object_tick(tesla, dt_ms)
        events = step_hide_when_idle_(
            catalog,
            state,
            dt_ms,
            has_attack_target=torch.tensor([[has_target]]),
            stunned=torch.tensor([[stunned]]),
            slow_multiplier=torch.tensor([[slow]], dtype=torch.float64),
            movement_speed_buff_multiplier=torch.tensor([[buff]], dtype=torch.float64),
        )
        assert state.hide_phase_ms.item() == pytest.approx(
            getattr(mechanic, "_phase_ms")
        )
        assert state.hidden_building.item() is bool(
            getattr(tesla, "_hidden_building", False)
        )
        assert state.special_move_active.item() is bool(
            getattr(tesla, "_special_move_active", False)
        )
        if state.hidden_building.item():
            assert state.target_slot.item() == -1
        assert all(
            opcode in {PassiveEventOpcode.HIDDEN, PassiveEventOpcode.REVEALED}
            for opcode in events.opcode.tolist()
        )


def test_invisibility_attack_and_melee_hold_match_oracle_boundaries() -> None:
    battle = BattleState()
    battle.entities.clear()
    stats = battle.card_loader.get_card("RoyalGhost")
    target_stats = battle.card_loader.get_card("Knight")
    assert stats is not None and target_stats is not None
    ghost = _entity(1, 0, stats, Position(9.0, 12.0))
    target = _entity(2, 1, target_stats, Position(9.0, 13.0))
    battle.entities = {1: ghost, 2: target}
    setattr(ghost, "battle_state", battle)
    setattr(target, "battle_state", battle)
    mechanic = copy.deepcopy(
        battle.card_loader.load_card_definitions()["RoyalGhost"].mechanics[0]
    )
    ghost.mechanics = [mechanic]
    mechanic.on_attach(ghost)
    catalog = _catalog()
    state = _state(
        catalog,
        [["RoyalGhost"]],
        [[1]],
        [[0]],
        [[(9.0, 12.0)]],
    )
    assert state.stealth_until_ms.item() == STEALTH_FOREVER_MS

    timeline = [
        (50, True, True),
        (500, False, True),
        (1_900, False, False),
        (100, False, False),
    ]
    for dt_ms, attack_started, in_range in timeline:
        if attack_started:
            mechanic.on_attack_start(ghost, target)
        target.position = (
            Position(ghost.position.x, ghost.position.y)
            if in_range
            else Position(9.0, 25.0)
        )
        ghost.target_id = target.id if in_range else None
        oracle_in_range = bool(
            ghost.target_id is not None
            and ghost._is_valid_target(target)
            and ghost.is_within_attack_reach(target)
        )
        mechanic.on_object_tick(ghost, dt_ms)
        step_invisibility_when_not_attacking_(
            catalog,
            state,
            dt_ms,
            attack_started=torch.tensor([[attack_started]]),
            has_attack_range_target=torch.tensor([[oracle_in_range]]),
        )
        assert state.fade_elapsed_ms.item() == getattr(mechanic, "time_since_attack_ms")
        assert state.stealth_until_ms.item() == getattr(ghost, "_stealth_until")


def test_soul_collection_uses_collector_then_dead_entity_id_order_and_caps() -> None:
    catalog = _catalog()
    state = _state(
        catalog,
        [["Knight", "SkeletonKing", "Knight", "Knight", "SkeletonKing"]],
        [[30, 10, 20, 40, 5]],
        [[1, 0, 1, 0, 0]],
        [[(9.0, 12.0), (9.0, 12.0), (10.0, 12.0), (9.5, 12.0), (9.0, 12.0)]],
        alive=[[False, True, False, False, True]],
    )

    events = collect_souls_(catalog, state)

    # Collector ID 5 is visited before ID 10; each independently observes the
    # same enemy deaths in target ID order 20 then 30. Ally ID 40 is ignored.
    assert events.source_entity_id.tolist() == [5, 5, 10, 10]
    assert events.target_entity_id.tolist() == [20, 30, 20, 30]
    collector_slots = {
        int(entity_id): slot for slot, entity_id in enumerate(state.entity_id[0])
    }
    assert state.souls_collected[0, collector_slots[5]].item() == 2
    assert state.souls_collected[0, collector_slots[10]].item() == 2

    for _ in range(14):
        collect_souls_(catalog, state)
    assert state.souls_collected[0, collector_slots[5]].item() == 30
    assert state.soul_ability_cost[0, collector_slots[5]].item() == 1
    consumed = consume_souls_(
        catalog,
        state,
        torch.tensor([[False, False, False, False, True]]),
    )
    assert consumed.opcode.tolist() == [PassiveEventOpcode.SOULS_CONSUMED]
    assert state.souls_collected[0, collector_slots[5]].item() == 10
    drops = plan_soul_drops(
        catalog,
        state,
        torch.tensor([[False, False, False, False, True]]),
    )
    assert drops.source_entity_id.tolist() == [5] * 5
    assert drops.formation_index.tolist() == list(range(5))


class _SpawnerEntity:
    def __init__(self) -> None:
        self.battle_state = type("BattleStub", (), {"debug_logs": False})()
        self.stunned = False
        self.spawn_rate = 1.0

    def is_stunned(self) -> bool:
        return self.stunned

    def get_spawn_rate_multiplier(self) -> float:
        return self.spawn_rate


def test_periodic_wrapper_preserves_source_id_and_wave_order_with_rng_unchanged() -> (
    None
):
    catalog = _catalog()
    names = [["Witch", "Tombstone", "NightWitch"]]
    state = _state(
        catalog,
        names,
        [[30, 10, 20]],
        [[0, 0, 0]],
        [[(9.0, 12.0), (7.0, 12.0), (11.0, 12.0)]],
    )
    definitions = BattleState().card_loader.load_card_definitions()
    oracle: dict[int, PeriodicSpawner] = {}
    expected: list[tuple[int, int, int]] = []
    for entity_id, name in sorted(zip((30, 10, 20), names[0])):
        mechanic = next(
            copy.deepcopy(item)
            for item in definitions[name].mechanics
            if isinstance(item, PeriodicSpawner)
        )

        def record(
            _self: PeriodicSpawner,
            _entity: Any,
            *,
            count: int,
            start_index: int,
            wave_size: int,
            entity_id: int = entity_id,
        ) -> None:
            expected.extend(
                (entity_id, index, wave_size)
                for index in range(start_index, start_index + count)
            )

        setattr(mechanic, "_spawn_units", MethodType(record, mechanic))
        oracle[entity_id] = mechanic
    rng = TensorPythonRandom.from_randoms([random.Random(771_991)])
    before_words = rng.words.clone()
    before_index = rng.index.clone()
    stub = _SpawnerEntity()

    for dt_ms in (1_000, 50, 3_500, 7_000):
        expected.clear()
        for entity_id in sorted(oracle):
            oracle[entity_id].on_object_tick(stub, dt_ms)
        events = step_passive_object_phase_(
            catalog,
            state,
            dt_ms,
            has_attack_target=torch.zeros(state.shape, dtype=torch.bool),
            has_attack_range_target=torch.zeros(state.shape, dtype=torch.bool),
            attack_started=torch.zeros(state.shape, dtype=torch.bool),
            stunned=torch.zeros(state.shape, dtype=torch.bool),
            slow_multiplier=torch.ones(state.shape, dtype=torch.float64),
            movement_speed_buff_multiplier=torch.ones(state.shape, dtype=torch.float64),
            spawn_rate=torch.ones(state.shape, dtype=torch.float64),
            rng=rng,
        )
        periodic = events.opcode == int(PassiveEventOpcode.PERIODIC_SPAWN)
        actual = list(
            zip(
                events.source_entity_id[periodic].tolist(),
                events.formation_index[periodic].tolist(),
                events.wave_size[periodic].tolist(),
            )
        )
        assert actual == expected
    assert torch.equal(rng.words, before_words)
    assert torch.equal(rng.index, before_index)

    for slot, entity_id in enumerate(state.entity_id[0].tolist()):
        mechanic = oracle[entity_id]
        assert state.periodic_time_since_spawn_ms[0, slot].item() == (
            mechanic.time_since_spawn_ms
        )
        assert state.periodic_spawns_created[0, slot].item() == (
            mechanic.spawns_created
        )
        assert state.periodic_pending_units[0, slot].item() == mechanic.pending_units


def test_device_contract_rejects_mps_before_state_allocation() -> None:
    with pytest.raises(UnsupportedPassiveDeviceError, match="CPU or CUDA"):
        validate_passive_device("mps")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_all_four_passive_opcode_families() -> None:
    catalog = _catalog("cuda")
    state = _state(
        catalog,
        [["Tesla", "RoyalGhost", "SkeletonKing", "Witch", "Knight"]],
        [[1, 2, 3, 4, 5]],
        [[0, 0, 0, 0, 1]],
        [[(9.0, 12.0), (8.0, 12.0), (10.0, 12.0), (7.0, 12.0), (10.5, 12.0)]],
        alive=[[True, True, True, True, False]],
    )
    rng = TensorPythonRandom.from_randoms([random.Random(1)], device="cuda")

    object_events = step_passive_object_phase_(
        catalog,
        state,
        1_000,
        has_attack_target=torch.zeros(state.shape, dtype=torch.bool, device="cuda"),
        has_attack_range_target=torch.zeros(
            state.shape, dtype=torch.bool, device="cuda"
        ),
        attack_started=torch.zeros(state.shape, dtype=torch.bool, device="cuda"),
        stunned=torch.zeros(state.shape, dtype=torch.bool, device="cuda"),
        slow_multiplier=torch.ones(state.shape, dtype=torch.float64, device="cuda"),
        movement_speed_buff_multiplier=torch.ones(
            state.shape, dtype=torch.float64, device="cuda"
        ),
        spawn_rate=torch.ones(state.shape, dtype=torch.float64, device="cuda"),
        rng=rng,
    )
    soul_events = collect_souls_(catalog, state)

    assert object_events.opcode.device.type == "cuda"
    assert soul_events.opcode.device.type == "cuda"
    assert state.souls_collected[0, 2].item() == 1
