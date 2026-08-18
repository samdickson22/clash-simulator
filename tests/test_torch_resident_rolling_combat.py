from __future__ import annotations

import copy
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import RollingProjectile
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.combat import CombatStepResult
from clasher.torch_sim.combat_adapter import project_stationary_combat
from clasher.torch_sim.oracle_event_capture import (
    OracleEventRecord,
    OraclePayloadKind,
    PythonOracleEventCapture,
)
from clasher.torch_sim.resident_engine import _resident_deployment_catalog_closure
from clasher.torch_sim.resident_rolling_combat import (
    TensorResidentRollingCombatProjectiles,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime, TickPhase


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _battle(
    *,
    target_position: Position | None = None,
    crowded: bool = False,
) -> BattleState:
    target_position = target_position or Position(9, 14)
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1

    def spawn(name: str, position: Position, player: int) -> None:
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        battle._spawn_unit_at_position(
            position,
            player,
            stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        entity = battle.entities[battle.next_entity_id - 1]
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.stun_timer = 100.0

    spawn("Bowler", Position(9, 10), 0)
    spawn("Knight", target_position, 1)
    if crowded:
        spawn("Knight", Position(9, 12), 1)
        spawn("Knight", Position(9, 12.5), 1)
        spawn("MegaMinion", Position(9, 12), 1)
        spawn("Knight", Position(9, 20.2), 1)
    battle.entities[1].target_id = 2
    battle.entities[1].stun_timer = 0.0
    return battle


def _stack(
    battle: BattleState,
    *,
    device: str,
    event_capacity: int = 256,
) -> tuple[
    TensorBattleRuntime,
    TensorResidentRollingCombatProjectiles,
    object,
]:
    loader, closure = _resident_deployment_catalog_closure(
        battle.card_loader,
        {entity.card_stats.name for entity in battle.entities.values()},
    )
    catalog = TensorCardCatalog.compile(loader, closure, device=device)
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=24,
        event_capacity=event_capacity,
        catalog=catalog,
    )
    owner = TensorResidentRollingCombatProjectiles.from_battles(
        runtime, [battle], capacity=4
    )
    combat = project_stationary_combat(
        [battle], catalog, capacity=runtime.max_entities, device=device
    ).state
    source_slot = int(torch.where(combat.entity_id[0] == 1)[0][0].item())
    target_slot = int(torch.where(combat.entity_id[0] == 2)[0][0].item())
    combat.target_slot[0, source_slot] = target_slot
    launched = torch.zeros_like(combat.present)
    launched[0, source_slot] = True
    result = CombatStepResult(
        attacked=launched.clone(),
        projectile_launched=launched,
        damage_received=torch.zeros_like(combat.hp),
        target_before=combat.target_slot.clone(),
        target_after=combat.target_slot.clone(),
    )
    return runtime, owner, (combat, result)


def _tensor_events(
    runtime: TensorBattleRuntime, start: int
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            int(runtime.events.phase[0, slot].item()),
            int(runtime.events.opcode[0, slot].item()),
            int(runtime.events.source_id[0, slot].item()),
            int(runtime.events.target_id[0, slot].item()),
            int(runtime.events.x_units[0, slot].item()),
            int(runtime.events.y_units[0, slot].item()),
            float(runtime.events.amount[0, slot].item()),
            int(runtime.events.payload[0, slot].item()),
        )
        for slot in range(start, int(runtime.events.count[0].item()))
    ]


def _oracle_events(
    records: list[OracleEventRecord], runtime: TensorBattleRuntime
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            record.phase,
            record.opcode,
            record.source_id,
            record.target_id,
            record.x_units,
            record.y_units,
            float(record.amount),
            runtime.battle.card_to_id[str(record.payload)],
        )
        for record in records
    ]


def _object_tick(battle: BattleState) -> None:
    identities = set(battle.entities)
    battle._run_object_phase(battle.dt, identities, identities)
    battle._cleanup_dead_entities()


@pytest.mark.parametrize(
    "target_position",
    (Position(9, 14), Position(13, 14), Position(5, 14)),
)
def test_serialized_rolling_combat_full_lifecycle_matches_scalar(
    tensor_device: str,
    target_position: Position,
) -> None:
    battle = _battle(target_position=target_position)
    oracle = copy.deepcopy(battle)
    runtime, owner, launch = _stack(battle, device=tensor_device)
    combat, result = launch

    with PythonOracleEventCapture(oracle) as capture:
        with capture._scope(
            phase=TickPhase.COMBAT,
            source_id=1,
            source_payload="Bowler",
        ):
            oracle.entities[1]._create_projectile(oracle.entities[2], oracle)
        scalar_projectile = next(
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, RollingProjectile)
        )
        materialized = owner.materialize_combat_launches_(runtime, combat, result)
        assert materialized.committed.tolist() == [True]
        assert materialized.selected_count.tolist() == [1]
        assert capture.events[0].payload_kind == OraclePayloadKind.OBJECT_CHARACTER
        assert _tensor_events(runtime, 0) == _oracle_events(capture.events, runtime)
        assert owner.state.card_id[0, 0].item() == runtime.battle.card_to_id["Bowler"]
        assert owner.state.entity_id[0, 0].item() == scalar_projectile.id == 3
        public_slot = int(
            torch.where(runtime.battle.entity_id[0] == scalar_projectile.id)[0][
                0
            ].item()
        )
        assert runtime.battle.entity_kind[0, public_slot].item() == 2
        assert (
            runtime.battle.entity_card[0, public_slot].item()
            == (runtime.battle.card_to_id["Bowler"])
        )
        assert runtime.battle.entity_hp_integer_kind[0, public_slot].item()

        oracle_event_start = len(capture.events)
        for _ in range(50):
            tensor_event_start = int(runtime.events.count[0].item())
            _object_tick(oracle)
            step = owner.step_(runtime)
            assert step.committed.tolist() == [True]
            assert _tensor_events(runtime, tensor_event_start) == _oracle_events(
                capture.events[oracle_event_start:], runtime
            )
            oracle_event_start = len(capture.events)
            scalar_rollers = [
                entity
                for entity in oracle.entities.values()
                if isinstance(entity, RollingProjectile)
            ]
            if scalar_rollers:
                scalar_projectile = scalar_rollers[0]
                assert owner.state.x_units[0, 0].item() == round(
                    scalar_projectile.position.x * 1_000
                )
                assert owner.state.y_units[0, 0].item() == round(
                    scalar_projectile.position.y * 1_000
                )
                assert owner.state.distance_units[0, 0].item() == round(
                    scalar_projectile.distance_traveled * 1_000
                )
            else:
                assert not owner.state.active.any()
                break
        else:
            raise AssertionError("rolling combat projectile did not terminate")

    target_slot = int(torch.where(runtime.battle.entity_id[0] == 2)[0][0].item())
    assert (
        runtime.battle.entity_hp[0, target_slot].item() == oracle.entities[2].hitpoints
    )
    assert runtime.battle.entity_hp_integer_kind[0, target_slot].item() is (
        type(oracle.entities[2].hitpoints) is int
    )


def test_crowded_hits_once_air_exclusion_terminal_radius_and_pushback_match_scalar(
    tensor_device: str,
) -> None:
    battle = _battle(crowded=True)
    oracle = copy.deepcopy(battle)
    runtime, owner, launch = _stack(battle, device=tensor_device)
    combat, result = launch
    oracle.entities[1]._create_projectile(oracle.entities[2], oracle)
    owner.materialize_combat_launches_(runtime, combat, result)
    hit_counts = torch.zeros(runtime.max_entities, dtype=torch.int64)

    for _ in range(50):
        _object_tick(oracle)
        step = owner.step_(runtime)
        hit_counts += step.hit[0].to(torch.int64).cpu()
        for slot in torch.where(step.knockback[0])[0].tolist():
            entity_id = int(runtime.battle.entity_id[0, slot].item())
            scalar = oracle.entities[entity_id]
            target = scalar._knockback_target
            assert target is not None
            direction = step.knockback_direction_units[0, slot]
            assert direction.tolist() == [0, 4_000]
            assert step.knockback_distance_units[0, slot].item() == 1_000
        if not owner.state.active.any():
            break

    for entity_id in (2, 3, 4, 6):
        slot = int(torch.where(runtime.battle.entity_id[0] == entity_id)[0][0].item())
        assert hit_counts[slot].item() == 1
        assert (
            runtime.battle.entity_hp[0, slot].item()
            == oracle.entities[entity_id].hitpoints
        )
    air_slot = int(torch.where(runtime.battle.entity_id[0] == 5)[0][0].item())
    assert hit_counts[air_slot].item() == 0
    assert runtime.battle.entity_hp[0, air_slot].item() == oracle.entities[5].hitpoints


def test_event_capacity_failure_rolls_back_launch_and_object_tick() -> None:
    battle = _battle(target_position=Position(9, 12))
    runtime, owner, launch = _stack(battle, device="cpu", event_capacity=1)
    combat, result = launch
    runtime.events.count[0] = 1
    ids_before = runtime.battle.entity_id.clone()

    materialized = owner.materialize_combat_launches_(runtime, combat, result)

    assert materialized.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_id, ids_before)
    assert not owner.state.active.any()

    runtime.events.clear()
    assert owner.materialize_combat_launches_(runtime, combat, result).committed.all()
    state_before = owner.state.clone()
    hp_before = runtime.battle.entity_hp.clone()
    step = owner.step_(runtime)
    assert step.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, hp_before)
    for descriptor in vars(state_before):
        assert torch.equal(
            getattr(owner.state, descriptor), getattr(state_before, descriptor)
        )


def test_clone_and_fork_own_independent_rolling_state() -> None:
    battle = _battle()
    _, owner, _ = _stack(battle, device="cpu")
    owner.state.active[0, 0] = True
    owner.state.entity_id[0, 0] = 77
    cloned = owner.clone()
    forked = owner.fork([0, 0])
    cloned.state.entity_id[0, 0] = 99

    assert owner.state.entity_id[0, 0].item() == 77
    assert forked.state.entity_id[:, 0].tolist() == [77, 77]
    assert forked.catalog is owner.catalog
    assert forked.targets.collision_radius_units.data_ptr() != (
        owner.targets.collision_radius_units.data_ptr()
    )
