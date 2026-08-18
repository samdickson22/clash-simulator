from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, TargetType, Troop
from clasher.spells import SPELL_REGISTRY, AreaEffectSpell
from clasher.torch_sim.resident_continuous_areas import (
    TensorContinuousAreaCatalog,
    TensorResidentContinuousAreas,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _battle() -> BattleState:
    battle = BattleState(fast_path=False)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = Troop(
        id=1,
        position=Position(9, 14),
        player_id=1,
        card_stats=stats,
        hitpoints=10_000,
        max_hitpoints=10_000,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=0,
        target_type=TargetType.BOTH,
    )
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.battle_state = battle  # type: ignore[attr-defined]
    battle.entities = {1: target}
    battle.next_entity_id = 2
    battle.players[0].hand = ["Earthquake", "Freeze", "Poison", "Knight"]
    battle.players[0].deck = [
        str(name) for name in battle.players[0].hand if name is not None
    ]
    battle.players[0].cycle_queue = deque()
    return battle


def _runtime_owner(
    battle: BattleState,
    *,
    device: str = "cpu",
    event_capacity: int = 512,
    area_capacity: int = 4,
) -> tuple[TensorBattleRuntime, TensorResidentContinuousAreas]:
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=16,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentContinuousAreas.from_battles(
        runtime, [battle], capacity=area_capacity
    )


def test_catalog_compiles_enabled_area_families_from_normalized_metadata() -> None:
    battle = _battle()
    runtime, _ = _runtime_owner(battle)
    catalog = TensorContinuousAreaCatalog.compile(runtime)

    expected = {
        "Earthquake": (3_000, 1_000, 3, False, False),
        "Freeze": (4_000, 0, 1, True, False),
        "Poison": (8_000, 1_000, 0, False, True),
    }
    for name, values in expected.items():
        card = runtime.battle.card_to_id[name]
        spell = SPELL_REGISTRY[name]
        assert isinstance(spell, AreaEffectSpell)
        assert catalog.supported[card].item() is True
        assert catalog.reason[card] == ""
        assert (
            catalog.duration_ms[card].item(),
            catalog.damage_interval_ms[card].item(),
            catalog.max_damage_ticks[card].item(),
            catalog.freeze_snapshot[card].item(),
            catalog.target_local_damage[card].item(),
        ) == values
        assert catalog.radius_units[card].item() == round(spell.radius * 1_000)
        assert catalog.damage[card].item() == spell.damage


def test_due_handoff_and_capacity_failure_are_atomic() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner(battle, event_capacity=1, area_capacity=1)
    runtime.events.count.fill_(runtime.events.capacity)
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_active = runtime.entity_pool.active.clone()
    before_rng = runtime.battle.rng.python_state(0)
    before_owner = owner.clone()
    card = runtime.battle.card_to_id["Freeze"]

    supported = owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )

    assert supported.tolist() == [False]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(runtime.entity_pool.active, before_active)
    assert runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(owner.active, before_owner.active)
    assert torch.equal(owner.area_id, before_owner.area_id)


def test_clone_fork_and_selective_reset_preserve_independent_area_state() -> None:
    battles = [_battle(), _battle()]
    runtime = TensorBattleRuntime.from_battles(
        battles, max_entities=16, event_capacity=128
    )
    owner = TensorResidentContinuousAreas.from_battles(runtime, battles, capacity=2)
    cards = torch.tensor(
        [
            runtime.battle.card_to_id["Earthquake"],
            runtime.battle.card_to_id["Poison"],
        ]
    )
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=cards,
        player_ids=torch.tensor([0, 0]),
        target_x_units=torch.tensor([9_000, 9_000]),
        target_y_units=torch.tensor([14_000, 14_000]),
        valid=torch.tensor([True, True]),
    ).all()
    cloned = owner.clone()
    forked = owner.fork([1])
    assert cloned.active.data_ptr() != owner.active.data_ptr()
    assert forked.card_id.tolist() == owner.card_id[1:2].tolist()
    cloned.age_ms[0, 0] = 900
    owner.reset_rows_([0], cloned, [0])
    assert owner.age_ms[:, 0].tolist() == [900, 0]
    assert owner.targets.entity_id.data_ptr() != forked.targets.entity_id.data_ptr()


def test_status_source_capacity_failure_rolls_back_the_whole_row() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner(battle)
    card = runtime.battle.card_to_id["Earthquake"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    runtime.status.slow_active.fill_(True)
    runtime.status.slow_movement.fill_(0.75)
    runtime.status.slow_attack.fill_(0.75)
    runtime.status.slow_spawn.fill_(0.75)
    runtime.battle.time += runtime.battle.dt
    runtime.battle.tick += 1
    assert owner.step_(runtime).committed.tolist() == [True]
    before_runtime = runtime.clone()
    before_owner = owner.clone()
    runtime.battle.time += runtime.battle.dt
    runtime.battle.tick += 1

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_runtime.battle.entity_hp)
    assert torch.equal(runtime.status.slow_active, before_runtime.status.slow_active)
    assert torch.equal(runtime.events.count, before_runtime.events.count)
    assert torch.equal(owner.age_ms, before_owner.age_ms)
    assert torch.equal(owner.next_effect_ms, before_owner.next_effect_ms)


def test_stale_target_plane_identity_fails_closed_without_area_progress() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner(battle)
    card = runtime.battle.card_to_id["Freeze"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    runtime.battle.entity_id[0, 0] = 3
    runtime.entity_pool.next_entity_id[0] = 4
    before_hp = runtime.battle.entity_hp.clone()
    before_events = runtime.events.count.clone()
    before_age = owner.age_ms.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.events.count, before_events)
    assert torch.equal(owner.age_ms, before_age)


def _advance_oracle_area_tick(battle: BattleState) -> None:
    battle.time += battle.dt
    battle.tick += 1
    for entity in list(battle.entities.values()):
        if not isinstance(entity, AreaEffect):
            entity.update_status_effects(battle.dt)
    for entity in list(battle.entities.values()):
        if type(entity) is AreaEffect:
            entity.update(battle.dt, battle)
    battle._cleanup_dead_entities()


@pytest.mark.parametrize(
    ("spell_name", "ticks"),
    (("Earthquake", 65), ("Freeze", 82), ("Poison", 180)),
)
def test_complete_continuous_area_lifecycle_matches_python(
    tensor_device: str,
    spell_name: str,
    ticks: int,
) -> None:
    seed = _battle()
    oracle = copy.deepcopy(seed)
    runtime, owner = _runtime_owner(seed, device=tensor_device, event_capacity=1_024)
    spell = SPELL_REGISTRY[spell_name]
    assert isinstance(spell, AreaEffectSpell)
    assert spell.cast(oracle, 0, Position(9, 14))
    card = runtime.battle.card_to_id[spell_name]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card], device=runtime.device),
        player_ids=torch.tensor([0], device=runtime.device),
        target_x_units=torch.tensor([9_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    ).all()
    assert runtime.battle.entity_card[0, 1].item() == 0
    assert runtime.battle.entity_hp_integer_kind[0, 1].item() is True
    assert runtime.events.opcode[0, 0].item() == RuntimeEventOpcode.AREA
    assert runtime.events.phase[0, 0].item() == TickPhase.COMMANDS
    assert runtime.events.source_id[0, 0].item() == 0
    assert runtime.events.target_id[0, 0].item() == 2
    assert runtime.events.x_units[0, 0].item() == 9_000
    assert runtime.events.y_units[0, 0].item() == 14_000
    assert runtime.events.payload[0, 0].item() == card

    for _ in range(ticks):
        before_hp = oracle.entities[1].hitpoints
        before_ids = set(oracle.entities)
        event_start = int(runtime.events.count[0].item())
        _advance_oracle_area_tick(oracle)
        runtime.battle.time += runtime.battle.dt
        runtime.battle.tick += 1
        status_result = owner.step_status_(runtime)
        area_result = owner.step_(runtime)
        assert status_result.committed.tolist() == [True]
        assert area_result.committed.tolist() == [True]

        oracle_target = oracle.entities[1]
        target_slot = int(torch.where(runtime.battle.entity_id[0] == 1)[0][0].item())
        assert (
            runtime.battle.entity_hp[0, target_slot].item() == oracle_target.hitpoints
        )
        assert runtime.battle.entity_hp_integer_kind[0, target_slot].item() is (
            type(oracle_target.hitpoints) is int
        )
        assert runtime.status.stun_timer[0, target_slot].item() == pytest.approx(
            oracle_target.stun_timer
        )
        assert runtime.status.freeze_expiry_time[
            0, target_slot
        ].item() == pytest.approx(oracle_target.freeze_expiry_time)
        assert runtime.status.slow_timer[0, target_slot].item() == pytest.approx(
            oracle_target.slow_timer
        )
        assert runtime.status.slow_multiplier[0, target_slot].item() == pytest.approx(
            oracle_target.slow_multiplier
        )
        python_periodic = tuple(oracle_target._periodic_damage_effects.values())
        tensor_periodic = runtime.status.periodic_active[0, target_slot]
        assert int(tensor_periodic.sum().item()) == len(python_periodic)
        if python_periodic:
            tensor_slot = int(torch.where(tensor_periodic)[0][0].item())
            effect = python_periodic[0]
            assert runtime.status.periodic_remaining[
                0, target_slot, tensor_slot
            ].item() == pytest.approx(effect.remaining)
            assert runtime.status.periodic_next_hit[
                0, target_slot, tensor_slot
            ].item() == pytest.approx(effect.time_to_next_hit)
            assert runtime.status.periodic_hard_active[
                0, target_slot, tensor_slot
            ].item() is (effect.hard_remaining is not None)

        scalar_areas = [
            entity for entity in oracle.entities.values() if type(entity) is AreaEffect
        ]
        retained = owner.active[0]
        assert int(retained.sum().item()) == len(scalar_areas)
        if scalar_areas:
            lane = int(torch.where(retained)[0][0].item())
            area = scalar_areas[0]
            assert owner.area_id[0, lane].item() == area.id
            assert owner.age_ms[0, lane].item() == round(area.time_alive * 1_000)
            assert (
                owner.damage_ticks_applied[0, lane].item() == area.damage_ticks_applied
            )

        expected: list[tuple[int, int, float]] = []
        damage = float(before_hp) - float(oracle_target.hitpoints)
        if damage > 0:
            expected.append((RuntimeEventOpcode.DAMAGE, 1, damage))
        if 2 in before_ids and 2 not in oracle.entities:
            expected.extend(
                (
                    (RuntimeEventOpcode.DAMAGE, 2, 1.0),
                    (RuntimeEventOpcode.DEATH, 2, 0.0),
                )
            )
        stop = int(runtime.events.count[0].item())
        actual = [
            (
                int(runtime.events.opcode[0, slot].item()),
                int(runtime.events.target_id[0, slot].item()),
                float(runtime.events.amount[0, slot].item()),
            )
            for slot in range(event_start, stop)
        ]
        assert actual == expected
        assert all(
            runtime.events.phase[0, slot].item() == TickPhase.COMBAT
            and runtime.events.source_id[0, slot].item() == 0
            and runtime.events.payload[0, slot].item() == 0
            for slot in range(event_start, stop)
        )

    assert not owner.active.any()
    assert set(oracle.entities) == {1}
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()
