from __future__ import annotations

import random
from collections import deque
from dataclasses import fields, is_dataclass

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6


def _battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    player = battle.players[0]
    player.hand = ["Knight", "Zap", "Cannon", "Fireball"]
    player.deck = ["Knight", "Zap", "Cannon", "Fireball"]
    player.cycle_queue = deque()
    player.elixir = 10.0
    return battle


def _engine(battles: list[BattleState], device: str = "cpu") -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=24,
        max_objects=24,
        event_capacity=256,
    )


def _tensor_snapshot(value: object, prefix: str = "") -> dict[str, torch.Tensor]:
    result: dict[str, torch.Tensor] = {}
    if isinstance(value, torch.Tensor):
        result[prefix] = value.detach().cpu().clone()
        return result
    if not is_dataclass(value):
        return result
    for descriptor in fields(value):
        child = getattr(value, descriptor.name)
        result.update(
            _tensor_snapshot(
                child,
                f"{prefix}.{descriptor.name}" if prefix else descriptor.name,
            )
        )
    return result


def _engine_snapshot(engine: TensorResidentEngine) -> dict[str, torch.Tensor]:
    result: dict[str, torch.Tensor] = {}
    for name in (
        "combat",
        "movement",
        "status",
        "mechanics",
        "objects",
        "projectile_bridge",
    ):
        result.update(_tensor_snapshot(getattr(engine, name), name))
    for name in (
        "passive",
        "combat_world",
        "damage_ramp",
        "dash",
        "leap",
        "hook",
    ):
        result.update(
            _tensor_snapshot(getattr(engine.dispatcher, name), f"dispatcher.{name}")
        )
    for name in (
        "special_triggered",
        "forced_movement",
        "knockback_target_units",
        "knockback_velocity_work",
        "initialized_entity_id",
        "multiple_target_ids",
        "multiple_target_valid",
        "underground_active",
    ):
        result[f"dispatcher.{name}"] = getattr(engine.dispatcher, name).cpu().clone()
    for name in ("battle", "status", "phases", "events"):
        result.update(
            _tensor_snapshot(getattr(engine.runtime, name), f"runtime.{name}")
        )
    result["runtime.pool.active"] = engine.runtime.entity_pool.active.cpu().clone()
    result["runtime.pool.next"] = (
        engine.runtime.entity_pool.next_entity_id.cpu().clone()
    )
    result["runtime.supported"] = engine.runtime.supported.cpu().clone()
    result["runtime.dirty"] = engine.runtime.dirty.cpu().clone()
    result["facing_x"] = engine.facing_x_units.cpu().clone()
    result["facing_y"] = engine.facing_y_units.cpu().clone()
    result["pending_projectile_max_duration_ms"] = (
        engine.pending_projectile_max_duration_ms.cpu().clone()
    )
    result["projectile_duration_ms"] = engine.projectile_duration_ms.cpu().clone()
    return result


def _mutable_pointers(engine: TensorResidentEngine) -> dict[str, int]:
    pointers: dict[str, int] = {}
    for name, tensor in _engine_snapshot(engine).items():
        del tensor
        owner: object = engine
        parts = name.split(".")
        if parts[0] == "runtime":
            owner = engine.runtime
            parts = parts[1:]
        value: object
        if parts[:2] == ["pool", "active"]:
            value = engine.runtime.entity_pool.active
        elif parts[:2] == ["pool", "next"]:
            value = engine.runtime.entity_pool.next_entity_id
        elif parts[0] in {"supported", "dirty"} and owner is engine.runtime:
            value = getattr(engine.runtime, parts[0])
        elif parts[0] == "facing_x":
            value = engine.facing_x_units
        elif parts[0] == "facing_y":
            value = engine.facing_y_units
        elif parts[0] == "pending_projectile_max_duration_ms":
            value = engine.pending_projectile_max_duration_ms
        elif parts[0] == "projectile_duration_ms":
            value = engine.projectile_duration_ms
        else:
            for part in parts:
                owner = getattr(owner, part)
            value = owner
        if isinstance(value, torch.Tensor):
            pointers[name] = value.data_ptr()
    return pointers


def _assert_engine_equal(
    expected: TensorResidentEngine,
    actual: TensorResidentEngine,
) -> None:
    left = _engine_snapshot(expected)
    right = _engine_snapshot(actual)
    assert left.keys() == right.keys()
    for name in left:
        torch.testing.assert_close(
            right[name], left[name], rtol=0, atol=0, equal_nan=True, msg=name
        )
    assert actual.runtime.battle.rng.python_state(0) == (
        expected.runtime.battle.rng.python_state(0)
    )


def test_workspace_preallocates_once_and_shares_only_immutable_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine([_battle(41), _battle(42)])
    workspace = TensorResidentWorkspace(engine)
    before_scratch = _mutable_pointers(workspace.scratch)
    before_front = _mutable_pointers(engine)

    def forbidden_clone(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("workspace tick called TensorResidentEngine.clone")

    monkeypatch.setattr(TensorResidentEngine, "clone", forbidden_clone)
    for _ in range(5):
        result = workspace.step(
            torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64),
            player_order=torch.tensor([[0, 1], [1, 0]]),
        )
        assert result.committed.tolist() == [True, True]
    assert _mutable_pointers(workspace.scratch) == before_scratch
    assert _mutable_pointers(engine) == before_front
    assert workspace.scratch.runtime.catalog is engine.runtime.catalog
    assert workspace.scratch.deployment is engine.deployment
    assert workspace.scratch.path_cache is engine.path_cache
    assert workspace.scratch.mechanics.catalog is engine.mechanics.catalog
    assert workspace.scratch.mechanics.on_hit_catalog is engine.mechanics.on_hit_catalog
    assert workspace.scratch.dispatcher.runtime is workspace.scratch.runtime
    assert workspace.scratch.dispatcher.mechanics is workspace.scratch.mechanics
    assert (
        workspace.scratch.dispatcher.passive_catalog
        is engine.dispatcher.passive_catalog
    )
    assert workspace.scratch.status.payload_catalog is engine.status.payload_catalog
    assert workspace.scratch.objects.objects.catalog is engine.objects.objects.catalog
    assert (
        workspace.scratch.projectile_bridge.catalog is engine.projectile_bridge.catalog
    )
    assert workspace.scratch.runtime.battle.time.data_ptr() != (
        engine.runtime.battle.time.data_ptr()
    )
    assert workspace.scratch.pending_projectile_max_duration_ms.data_ptr() != (
        engine.pending_projectile_max_duration_ms.data_ptr()
    )
    assert workspace.scratch.projectile_duration_ms.data_ptr() != (
        engine.projectile_duration_ms.data_ptr()
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_workspace_ticks_match_allocating_engine_exactly(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = [_battle(71), _battle(72)]
    reference = _engine([battle.clone() for battle in sources], device)
    candidate = _engine([battle.clone() for battle in sources], device)
    workspace = TensorResidentWorkspace(candidate)
    trace = (
        ((DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION), (NO_OP_ACTION, NO_OP_ACTION)),
        ((NO_OP_ACTION, NO_OP_ACTION), (DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION)),
        ((NO_OP_ACTION, NO_OP_ACTION), (NO_OP_ACTION, NO_OP_ACTION)),
        ((NO_OP_ACTION, NO_OP_ACTION), (NO_OP_ACTION, NO_OP_ACTION)),
    )
    order = torch.tensor([[0, 1], [1, 0]], device=device)
    for rows in trace:
        actions = torch.tensor(rows, dtype=torch.int64, device=device)
        expected_result = reference.step(actions, player_order=order)
        actual_result = workspace.step(actions, player_order=order)
        assert torch.equal(actual_result.committed, expected_result.committed)
        _assert_engine_equal(reference, candidate)


def test_unsupported_row_is_atomic_while_supported_peer_commits() -> None:
    supported = _battle(91)
    unsupported = _battle(92)
    unsupported.players[0].hand[0] = "Golem"
    unsupported.players[0].deck[0] = "Golem"
    engine = _engine([supported, unsupported])
    workspace = TensorResidentWorkspace(engine)
    before = _engine_snapshot(engine)
    actions = torch.tensor(
        [
            [NO_OP_ACTION, NO_OP_ACTION],
            [DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION],
        ]
    )
    result = workspace.step(actions, player_order=torch.tensor([[0, 1], [0, 1]]))
    assert result.committed.tolist() == [True, False]
    assert engine.runtime.battle.tick.tolist() == [1, 0]
    after = _engine_snapshot(engine)
    for name, value in before.items():
        if value.ndim > 0 and value.shape[0] == 2:
            torch.testing.assert_close(
                after[name][1], value[1], rtol=0, atol=0, equal_nan=True, msg=name
            )
