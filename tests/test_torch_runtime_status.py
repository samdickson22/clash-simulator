from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime
from clasher.torch_sim.runtime_status import (
    TensorRuntimeStatusPhase,
    apply_runtime_status_payloads_,
    step_runtime_status_phase_,
)
from clasher.torch_sim.status_payloads import StatusTriggerOpcode


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn_building(battle: BattleState, name: str, x: float) -> Building:
    stats = battle.card_loader.get_card(name)
    assert stats is not None and stats.lifetime_ms
    return cast(
        Building,
        battle._spawn_entity(Building, Position(x, 12.0), 0, stats),
    )


def _spawn_troop(battle: BattleState, x: float) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return cast(
        Troop,
        battle._spawn_entity(Troop, Position(x, 12.0), 0, stats),
    )


def _source_card_wave(
    runtime: TensorBattleRuntime,
    *,
    target_id: int,
    source_name: str,
) -> torch.Tensor:
    wave = torch.zeros_like(runtime.battle.entity_card)
    target_slot = int(
        runtime.entity_pool.slots_for_ids(
            torch.tensor([[target_id]], device=runtime.device)
        )[0, 0].item()
    )
    wave[0, target_slot] = runtime.battle.card_to_id[source_name]
    return wave


def _synthetic_status_loader(
    tmp_path: Path,
    *,
    character_overrides: dict[str, object],
) -> CardDataLoader:
    data_file = tmp_path / "runtime_status_payloads.json"
    character = {
        "name": "RuntimeStatusSourceCharacter",
        "hitpoints": 400,
        "damage": 10,
        "range": 1000,
        "hitSpeed": 1000,
        "sightRange": 5000,
        "collisionRadius": 500,
        "speed": 60,
        "deployTime": 0,
        **character_overrides,
    }
    data_file.write_text(
        json.dumps(
            {
                "items": {
                    "spells": [
                        {
                            "id": 9_991_100,
                            "name": "RuntimeStatusSource",
                            "rarity": "Common",
                            "manaCost": 1,
                            "tidType": "TID_CARD_TYPE_CHARACTER",
                            "summonCharacterData": character,
                        }
                    ]
                }
            }
        )
    )
    return CardDataLoader(data_file)


def _runtime_without_synthetic_catalog(
    battles: list[BattleState],
) -> TensorBattleRuntime:
    # Stun/FreezeDebuff are intentionally compiled by the orthogonal status
    # payload plane; the current general card catalog rejects these synthetic
    # mechanics before that plane is attached.
    fallback_loader = CardDataLoader()
    fallback = TensorCardCatalog.compile(fallback_loader, ["Knight"])
    return TensorBattleRuntime.from_battles(battles, max_entities=8, catalog=fallback)


def test_standard_building_lifetime_and_status_match_oracle_phase_order() -> None:
    battle = _empty_battle()
    buildings = [
        _spawn_building(battle, name, 2.0 + 3.0 * index)
        for index, name in enumerate(("Cannon", "Tesla", "BombTower", "Tombstone"))
    ]
    for index, building in enumerate(buildings):
        building.apply_stun(0.1 + index * 0.05)
        building.apply_slow(0.2, 0.7)
    expected = battle.clone()
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])

    for _ in range(25):
        for entity in expected.entities.values():
            if isinstance(entity, Building):
                entity.update_hitpoint_component(0.05)
        for entity in expected.entities.values():
            if isinstance(entity, (Troop, Building)) and entity.is_alive:
                entity.update_buff_component(0.05)
        runtime.events.clear()
        result = step_runtime_status_phase_(runtime, phase)
        assert result.supported_batch.tolist() == [True]

    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    for entity_id, oracle in expected.entities.items():
        expected_building = cast(Building, oracle)
        actual = cast(Building, candidate.entities[entity_id])
        assert actual.hitpoints == expected_building.hitpoints
        assert actual.is_alive is expected_building.is_alive
        assert actual.stun_timer == expected_building.stun_timer
        assert actual.slow_timer == expected_building.slow_timer
        assert actual.slow_multiplier == expected_building.slow_multiplier
        assert actual.speed == expected_building.speed
        assert actual.lifetime_elapsed == expected_building.lifetime_elapsed
        assert actual.lifetime_decay_work == expected_building.lifetime_decay_work
        assert actual.lifetime_tick_carry_ms == expected_building.lifetime_tick_carry_ms


def test_periodic_hits_and_death_events_follow_entity_then_source_order() -> None:
    battle = _empty_battle()
    first = _spawn_troop(battle, 4.0)
    second = _spawn_troop(battle, 8.0)
    first.hitpoints = 9.0
    second.hitpoints = 30.0
    first.apply_periodic_damage(
        source_id=20,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    first.apply_periodic_damage(
        source_id=10,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    second.apply_periodic_damage(
        source_id=30,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=7.0,
    )
    expected = battle.clone()
    for entity in expected.entities.values():
        cast(Troop, entity).update_buff_component(0.05)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [True]

    valid = slice(0, int(runtime.events.count[0].item()))
    assert runtime.events.opcode[0, valid].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
    ]
    assert runtime.events.source_id[0, valid].tolist() == [20, 10, 10, 30]
    assert runtime.events.target_id[0, valid].tolist() == [
        first.id,
        first.id,
        first.id,
        second.id,
    ]
    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    for entity_id, oracle in expected.entities.items():
        actual = candidate.entities[entity_id]
        assert actual.hitpoints == oracle.hitpoints
        assert actual.is_alive is oracle.is_alive
        assert actual._periodic_damage_effects == oracle._periodic_damage_effects


def test_lifetime_damage_and_death_events_are_interleaved_in_id_order() -> None:
    battle = _empty_battle()
    first = _spawn_building(battle, "Cannon", 4.0)
    second = _spawn_building(battle, "Tesla", 8.0)
    first.hitpoints = second.hitpoints = 1.0
    expected = battle.clone()
    for entity in expected.entities.values():
        cast(Building, entity).update_hitpoint_component(0.05)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = step_runtime_status_phase_(runtime, phase)
    assert result.died[0, :2].tolist() == [True, True]
    valid = slice(0, int(runtime.events.count[0].item()))
    assert runtime.events.opcode[0, valid].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.target_id[0, valid].tolist() == [
        first.id,
        first.id,
        second.id,
        second.id,
    ]


def test_mechanic_bearing_periodic_target_fails_closed_before_mutation() -> None:
    battle = _empty_battle()
    stats = battle.card_loader.get_card("DarkPrince")
    assert stats is not None
    target = cast(
        Troop,
        battle._spawn_entity(Troop, Position(5.0, 12.0), 0, stats),
    )
    target.apply_periodic_damage(
        source_id=7,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=10.0,
    )
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    before_hp = runtime.battle.entity_hp.clone()
    before_status = runtime.status.periodic_remaining.clone()

    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.status.periodic_remaining, before_status)
    assert runtime.events.count.tolist() == [0]


def test_event_overflow_fails_closed_before_any_phase_mutation() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 5.0)
    target.hitpoints = 5.0
    target.apply_periodic_damage(
        source_id=9,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=4, event_capacity=1
    )
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    before_hp = runtime.battle.entity_hp.clone()
    before_status = runtime.status.periodic_remaining.clone()

    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.status.periodic_remaining, before_status)
    assert runtime.events.count.tolist() == [0]


def test_supported_path_never_calls_python_entity_phase_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = _empty_battle()
    building = _spawn_building(battle, "Cannon", 4.0)
    building.apply_stun(0.2)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=4)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("supported tensor phase called a Python entity method")

    monkeypatch.setattr(Building, "update_hitpoint_component", forbidden)
    monkeypatch.setattr(Entity, "update_status_effects", forbidden)
    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [True]


@pytest.mark.parametrize(
    "source_name", ["ElectroWizard", "MiniSparkys", "TriWizards", "WitchMother"]
)
def test_retained_serialized_on_hit_payload_matches_python_mechanic(
    source_name: str,
) -> None:
    battle = _empty_battle()
    source_stats = battle.card_loader.get_card(source_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = cast(
        Troop,
        battle._spawn_entity(Troop, Position(3.0, 12.0), 0, source_stats),
    )
    target = cast(
        Troop,
        battle._spawn_entity(Troop, Position(5.0, 12.0), 1, target_stats),
    )
    expected = battle.clone()
    expected_source = cast(Troop, expected.entities[source.id])
    expected_target = cast(Troop, expected.entities[target.id])
    for mechanic in expected_source.mechanics:
        if type(mechanic).__name__ == "SerializedOnHitBuff":
            mechanic.on_attack_hit(expected_source, expected_target)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = apply_runtime_status_payloads_(
        runtime,
        phase,
        _source_card_wave(runtime, target_id=target.id, source_name=source_name),
        trigger=StatusTriggerOpcode.ATTACK_HIT,
    )
    assert result.applied.any()
    assert result.rng_draws.tolist() == [0]

    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    actual = cast(Troop, candidate.entities[target.id])
    assert actual.stun_timer == expected_target.stun_timer
    assert actual.slow_timer == expected_target.slow_timer
    assert actual.slow_multiplier == expected_target.slow_multiplier
    assert (
        actual.attack_speed_debuff_multiplier
        == expected_target.attack_speed_debuff_multiplier
    )
    assert (
        actual.spawn_speed_debuff_multiplier
        == expected_target.spawn_speed_debuff_multiplier
    )
    assert actual.speed == expected_target.speed
    assert candidate.rng.getstate() == expected.rng.getstate()


def test_retained_stun_payload_consumes_exact_oracle_rng_order(
    tmp_path: Path,
) -> None:
    loader = _synthetic_status_loader(
        tmp_path,
        character_overrides={"stunChance": 50, "stunDuration": 700},
    )
    battles: list[BattleState] = []
    expected: list[BattleState] = []
    target_ids: list[int] = []
    for seed in (3, 11, 27, 91):
        battle = BattleState()
        battle.card_loader = loader.clone_lazy()
        battle.entities.clear()
        battle.next_entity_id = 1
        battle.rng.seed(seed)
        stats = battle.card_loader.get_card("RuntimeStatusSource")
        assert stats is not None
        source = cast(
            Troop,
            battle._spawn_entity(Troop, Position(3.0, 12.0), 0, stats),
        )
        target = cast(
            Troop,
            battle._spawn_entity(Troop, Position(5.0, 12.0), 1, stats),
        )
        oracle = battle.clone()
        oracle_source = cast(Troop, oracle.entities[source.id])
        oracle_target = cast(Troop, oracle.entities[target.id])
        mechanic = next(
            item for item in oracle_source.mechanics if type(item).__name__ == "Stun"
        )
        mechanic.on_attack_hit(oracle_source, oracle_target)
        battles.append(battle)
        expected.append(oracle)
        target_ids.append(target.id)

    runtime = _runtime_without_synthetic_catalog(battles)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, battles)
    wave = torch.zeros_like(runtime.battle.entity_card)
    source_card_id = runtime.battle.card_to_id["RuntimeStatusSource"]
    target_slots = runtime.entity_pool.slots_for_ids(
        torch.tensor(target_ids, device=runtime.device)[:, None]
    )[:, 0]
    rows = torch.arange(runtime.batch_size, device=runtime.device)
    wave[rows, target_slots] = source_card_id
    result = apply_runtime_status_payloads_(
        runtime,
        phase,
        wave,
        trigger=StatusTriggerOpcode.ATTACK_HIT,
    )
    assert result.rng_draws.tolist() == [1, 1, 1, 1]

    candidates = [battle.clone() for battle in battles]
    phase.sync_to_battles(runtime, candidates)
    for target_id, oracle, candidate in zip(target_ids, expected, candidates):
        assert (
            candidate.entities[target_id].stun_timer
            == oracle.entities[target_id].stun_timer
        )
        assert candidate.rng.getstate() == oracle.rng.getstate()


def test_retained_freeze_aura_payload_uses_tick_duration(
    tmp_path: Path,
) -> None:
    loader = _synthetic_status_loader(
        tmp_path,
        character_overrides={"slowData": {"radius": 2500, "multiplier": 0.6}},
    )
    battle = BattleState()
    battle.card_loader = loader
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = loader.get_card("RuntimeStatusSource")
    assert stats is not None
    source = cast(
        Troop,
        battle._spawn_entity(Troop, Position(3.0, 12.0), 0, stats),
    )
    target = cast(
        Troop,
        battle._spawn_entity(Troop, Position(4.0, 12.0), 1, stats),
    )
    expected = battle.clone()
    expected_source = cast(Troop, expected.entities[source.id])
    mechanic = next(
        item
        for item in expected_source.mechanics
        if type(item).__name__ == "FreezeDebuff"
    )
    mechanic.on_tick(expected_source, 50)

    runtime = _runtime_without_synthetic_catalog([battle])
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    wave = _source_card_wave(
        runtime, target_id=target.id, source_name="RuntimeStatusSource"
    )
    result = apply_runtime_status_payloads_(
        runtime,
        phase,
        wave,
        trigger=StatusTriggerOpcode.AURA_TICK,
        tick_duration_seconds=0.05,
    )
    assert result.applied.any()
    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    actual = cast(Troop, candidate.entities[target.id])
    oracle = cast(Troop, expected.entities[target.id])
    assert actual.slow_timer == oracle.slow_timer == 0.05
    assert actual.slow_multiplier == oracle.slow_multiplier == 0.6
    assert actual.speed == oracle.speed


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_runtime_status_phase_is_exact_and_cuda_resident() -> None:
    battle = _empty_battle()
    building = _spawn_building(battle, "Cannon", 4.0)
    building.apply_stun(0.2)
    expected = battle.clone()
    expected_building = cast(Building, expected.entities[building.id])
    expected_building.update_hitpoint_component(0.05)
    expected_building.update_buff_component(0.05)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=4, device="cuda")
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [True]
    assert runtime.status.stun_timer.device.type == "cuda"
    assert phase.lifetime_elapsed.device.type == "cuda"
    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    actual = cast(Building, candidate.entities[building.id])
    assert actual.hitpoints == expected_building.hitpoints
    assert actual.stun_timer == expected_building.stun_timer
    assert actual.lifetime_elapsed == expected_building.lifetime_elapsed


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_runtime_status_payload_dispatch_is_exact_on_cuda() -> None:
    battle = _empty_battle()
    source_stats = battle.card_loader.get_card("ElectroWizard")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = cast(
        Troop,
        battle._spawn_entity(Troop, Position(3.0, 12.0), 0, source_stats),
    )
    target = cast(
        Troop,
        battle._spawn_entity(Troop, Position(5.0, 12.0), 1, target_stats),
    )
    expected = battle.clone()
    expected_source = cast(Troop, expected.entities[source.id])
    expected_target = cast(Troop, expected.entities[target.id])
    mechanic = next(
        item
        for item in expected_source.mechanics
        if type(item).__name__ == "SerializedOnHitBuff"
    )
    mechanic.on_attack_hit(expected_source, expected_target)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8, device="cuda")
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = apply_runtime_status_payloads_(
        runtime,
        phase,
        _source_card_wave(runtime, target_id=target.id, source_name="ElectroWizard"),
        trigger=StatusTriggerOpcode.ATTACK_HIT,
    )
    assert result.applied.device.type == "cuda"
    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    actual = cast(Troop, candidate.entities[target.id])
    assert actual.stun_timer == expected_target.stun_timer
