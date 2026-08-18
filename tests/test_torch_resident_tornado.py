from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, TargetType, Troop
from clasher.kinematics import trunc_div
from clasher.spells import SPELL_REGISTRY, TornadoSpell
from clasher.torch_sim.resident_tornado import (
    TensorResidentTornadoes,
    TensorTornadoCatalog,
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
        position=Position(12.0, 14.0),
        player_id=1,
        card_stats=stats,
        hitpoints=2_000,
        max_hitpoints=2_000,
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
    battle.players[0].hand = ["Tornado", "Knight", None, None]
    battle.players[0].deck = ["Tornado", "Knight"]
    battle.players[0].cycle_queue = deque()
    return battle


def _runtime_owner(
    battles: list[BattleState],
    *,
    device: str = "cpu",
    event_capacity: int = 128,
    capacity: int = 2,
) -> tuple[TensorBattleRuntime, TensorResidentTornadoes]:
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=16,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentTornadoes.from_battles(
        runtime, battles, capacity=capacity
    )


def test_catalog_compiles_normalized_attraction_and_periodic_metadata() -> None:
    battle = _battle()
    runtime, _ = _runtime_owner([battle])
    catalog = TensorTornadoCatalog.compile(runtime)
    card = runtime.battle.card_to_id["Tornado"]
    spell = SPELL_REGISTRY["Tornado"]
    assert isinstance(spell, TornadoSpell)

    assert catalog.supported[card].item() is True
    assert catalog.reason[card] == ""
    assert catalog.duration_ms[card].item() == 1_050
    assert catalog.radius_units[card].item() == 5_500
    assert catalog.attract_percentage[card].item() == 360
    assert catalog.push_speed_factor[card].item() == 100
    assert catalog.damage[card].item() == 84
    assert catalog.damage_interval_ms[card].item() == 550
    assert catalog.effect_interval_ms[card].item() == 50
    assert catalog.buff_duration_ms[card].item() == 500
    assert catalog.controlled_by_parent[card].item() is True
    assert catalog.crown_damage[card].item() == 25


def test_due_capacity_failure_is_atomic() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner([battle], event_capacity=1, capacity=1)
    runtime.events.count.fill_(runtime.events.capacity)
    card = runtime.battle.card_to_id["Tornado"]
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_rng = runtime.battle.rng.python_state(0)

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
    assert runtime.battle.rng.python_state(0) == before_rng
    assert not owner.active.any()


def test_clone_fork_and_selective_reset_are_independent() -> None:
    battles = [_battle(), _battle()]
    runtime, owner = _runtime_owner(battles)
    card = runtime.battle.card_to_id["Tornado"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card, card]),
        player_ids=torch.tensor([0, 1]),
        target_x_units=torch.tensor([9_000, 8_000]),
        target_y_units=torch.tensor([14_000, 18_000]),
        valid=torch.tensor([True, True]),
    ).all()
    clone = owner.clone()
    fork = owner.fork([1])
    assert clone.active.data_ptr() != owner.active.data_ptr()
    assert clone.targets.entity_id.data_ptr() != owner.targets.entity_id.data_ptr()
    assert fork.player_id[:, 0].tolist() == [1]
    clone.age_ms[0, 0] = 500
    owner.reset_rows_([0], clone, [0])
    assert owner.age_ms[:, 0].tolist() == [500, 0]


def test_periodic_slot_capacity_failure_rolls_back_pull_and_area_clock() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner([battle])
    card = runtime.battle.card_to_id["Tornado"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    runtime.status.periodic_active.fill_(True)
    runtime.status.periodic_source_id.fill_(999)
    before_owner = owner.clone()
    before_vectors = runtime.phases.movement_vector_units.clone()
    before_events = runtime.events.count.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert torch.equal(owner.age_ms, before_owner.age_ms)
    assert torch.equal(runtime.phases.movement_vector_units, before_vectors)
    assert torch.equal(runtime.events.count, before_events)


def test_periodic_event_capacity_failure_is_atomic() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner([battle], event_capacity=2)
    card = runtime.battle.card_to_id["Tornado"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    assert owner.step_(runtime).committed.tolist() == [True]
    runtime.status.periodic_next_hit[runtime.status.periodic_active] = (
        runtime.battle.dt[0]
    )
    runtime.events.count.fill_(runtime.events.capacity)
    before = runtime.clone()

    result = owner.step_status_(runtime)

    assert result.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before.battle.entity_hp)
    assert torch.equal(
        runtime.status.periodic_remaining, before.status.periodic_remaining
    )
    assert torch.equal(
        runtime.status.periodic_next_hit, before.status.periodic_next_hit
    )
    assert torch.equal(runtime.events.count, before.events.count)


def _consume_tensor_attraction(runtime: TensorBattleRuntime) -> None:
    count = runtime.phases.movement_vector_count.to(torch.int64)
    has = runtime.entity_pool.active & (count > 0)
    divisor = count.clamp_min(1)
    move_x = torch.div(
        runtime.phases.movement_vector_units[:, :, 0],
        divisor,
        rounding_mode="trunc",
    )
    move_y = torch.div(
        runtime.phases.movement_vector_units[:, :, 1],
        divisor,
        rounding_mode="trunc",
    )
    runtime.battle.entity_x_units.copy_(
        torch.where(
            has,
            (runtime.battle.entity_x_units.to(torch.int64) + move_x).clamp(250, 17_750),
            runtime.battle.entity_x_units.to(torch.int64),
        ).to(torch.int32)
    )
    runtime.battle.entity_y_units.copy_(
        torch.where(
            has,
            (runtime.battle.entity_y_units.to(torch.int64) + move_y).clamp(250, 31_750),
            runtime.battle.entity_y_units.to(torch.int64),
        ).to(torch.int32)
    )
    runtime.phases.movement_vector_units.zero_()
    runtime.phases.movement_vector_count.zero_()
    runtime.phases.movement_vector_bypasses_cap.zero_()


def _advance_oracle_before_area(battle: BattleState) -> None:
    target = battle.entities[1]
    target.update_status_effects(battle.dt)
    target.begin_movement_tick()
    target.finish_movement_tick(battle)


@pytest.mark.parametrize(
    "target_position",
    (Position(12.0, 14.0), Position(12.123, 15.777), Position(9.0, 14.0)),
)
def test_exact_native_attraction_vector_uses_base_speed_and_truncation(
    tensor_device: str,
    target_position: Position,
) -> None:
    seed = _battle()
    seed.entities[1].position = target_position
    oracle = copy.deepcopy(seed)
    runtime, owner = _runtime_owner([seed], device=tensor_device)
    spell = SPELL_REGISTRY["Tornado"]
    assert isinstance(spell, TornadoSpell)
    assert spell.cast(oracle, 0, Position(9, 14))
    card = runtime.battle.card_to_id["Tornado"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card], device=runtime.device),
        player_ids=torch.tensor([0], device=runtime.device),
        target_x_units=torch.tensor([9_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    ).all()
    tornado = oracle.entities[2]
    assert type(tornado) is AreaEffect
    tornado.update(oracle.dt, oracle)

    result = owner.step_(runtime)

    scalar_target = oracle.entities[1]
    assert result.attraction_vector_units[0, 0].tolist() == [
        scalar_target._movement_vector_x_units,
        scalar_target._movement_vector_y_units,
    ]
    assert result.attraction_count[0, 0].item() == scalar_target._movement_vector_count
    if target_position.x == 12.0 and target_position.y == 14.0:
        base_speed = round(float(scalar_target.card_stats.speed or 0))
        expected_work = int(
            int(base_speed * spell.push_speed_factor / 100)
            * spell.attract_percentage
            / 100
        )
        assert result.attraction_vector_units[0, 0, 0].item() == trunc_div(
            -3_000 * expected_work, 3_000
        )


def test_complete_tornado_lifecycle_matches_python(
    tensor_device: str,
) -> None:
    seed = _battle()
    oracle = copy.deepcopy(seed)
    runtime, owner = _runtime_owner([seed], device=tensor_device, event_capacity=128)
    spell = SPELL_REGISTRY["Tornado"]
    assert isinstance(spell, TornadoSpell)
    assert spell.cast(oracle, 0, Position(9, 14))
    card = runtime.battle.card_to_id["Tornado"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card], device=runtime.device),
        player_ids=torch.tensor([0], device=runtime.device),
        target_x_units=torch.tensor([9_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    ).all()
    assert runtime.battle.entity_card[0, 1].item() == 0
    assert runtime.events.opcode[0, 0].item() == RuntimeEventOpcode.AREA
    assert runtime.events.phase[0, 0].item() == TickPhase.COMMANDS
    assert runtime.events.source_id[0, 0].item() == 0
    assert runtime.events.target_id[0, 0].item() == 2
    assert runtime.events.x_units[0, 0].item() == 9_000
    assert runtime.events.y_units[0, 0].item() == 14_000
    assert runtime.events.payload[0, 0].item() == card

    for _ in range(25):
        before_hp = oracle.entities[1].hitpoints
        event_start = int(runtime.events.count[0].item())
        oracle.time += oracle.dt
        oracle.tick += 1
        _advance_oracle_before_area(oracle)
        tornadoes = [
            entity
            for entity in oracle.entities.values()
            if type(entity) is AreaEffect and entity.is_tornado
        ]
        for tornado in tornadoes:
            tornado.update(oracle.dt, oracle)
        oracle._cleanup_dead_entities()

        runtime.battle.time += runtime.battle.dt
        runtime.battle.tick += 1
        status = owner.step_status_(runtime)
        _consume_tensor_attraction(runtime)
        area = owner.step_(runtime)
        assert status.committed.tolist() == [True]
        assert area.committed.tolist() == [True]
        assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()

        target = oracle.entities[1]
        slot = int(torch.where(runtime.battle.entity_id[0] == 1)[0][0].item())
        assert runtime.battle.entity_x_units[0, slot].item() == round(
            target.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, slot].item() == round(
            target.position.y * 1_000
        )
        assert runtime.battle.entity_hp[0, slot].item() == target.hitpoints
        assert runtime.battle.entity_hp_integer_kind[0, slot].item() is (
            type(target.hitpoints) is int
        )
        assert runtime.phases.movement_vector_units[0, slot].tolist() == [
            target._movement_vector_x_units,
            target._movement_vector_y_units,
        ]
        assert runtime.phases.movement_vector_count[0, slot].item() == (
            target._movement_vector_count
        )
        assert runtime.phases.movement_vector_bypasses_cap[0, slot].item() is (
            target._movement_vector_bypasses_cap
        )
        python_periodic = tuple(target._periodic_damage_effects.values())
        tensor_periodic = runtime.status.periodic_active[0, slot]
        assert int(tensor_periodic.sum().item()) == len(python_periodic)
        if python_periodic:
            periodic_slot = int(torch.where(tensor_periodic)[0][0].item())
            effect = python_periodic[0]
            assert runtime.status.periodic_remaining[
                0, slot, periodic_slot
            ].item() == pytest.approx(effect.remaining)
            assert runtime.status.periodic_next_hit[
                0, slot, periodic_slot
            ].item() == pytest.approx(effect.time_to_next_hit)
            assert runtime.status.periodic_hard_remaining[
                0, slot, periodic_slot
            ].item() == pytest.approx(effect.hard_remaining)

        expected: list[tuple[int, int, float]] = []
        hp_loss = float(before_hp) - float(target.hitpoints)
        if hp_loss > 0:
            expected.append((RuntimeEventOpcode.DAMAGE, 1, hp_loss))
        stop = int(runtime.events.count[0].item())
        actual = [
            (
                int(runtime.events.opcode[0, index].item()),
                int(runtime.events.target_id[0, index].item()),
                float(runtime.events.amount[0, index].item()),
            )
            for index in range(event_start, stop)
        ]
        assert actual == expected
        for index in range(event_start, stop):
            target_id = runtime.events.target_id[0, index].item()
            assert runtime.events.phase[0, index].item() == TickPhase.STATUS
            assert runtime.events.source_id[0, index].item() == target_id
            assert runtime.events.payload[0, index].item() == 0

    assert not owner.active.any()
    assert set(oracle.entities) == {1}
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
