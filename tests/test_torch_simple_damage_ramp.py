from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_damage_ramp import (
    FastDamageRampParameters,
    FastDamageRampState,
    pre_attack_damage_ramp_,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _parameters(state: FastDamageRampState) -> FastDamageRampParameters:
    shape = (state.batch_size, state.max_entities)
    device = state.device
    return FastDamageRampParameters(
        enabled=torch.tensor(
            [[True, True, False], [True, True, False]],
            dtype=torch.bool,
            device=device,
        ),
        stage_1_ticks=torch.full(shape, 40, dtype=torch.int32, device=device),
        stage_2_ticks=torch.full(shape, 80, dtype=torch.int32, device=device),
        stage_0_damage_multiplier=torch.tensor(
            [[1.0, 1.0, 9.0], [1.0, 1.0, 9.0]],
            dtype=torch.float32,
            device=device,
        ),
        stage_1_damage_multiplier=torch.tensor(
            [[4.0, 2.0, 9.0], [4.0, 2.0, 9.0]],
            dtype=torch.float32,
            device=device,
        ),
        stage_2_damage_multiplier=torch.tensor(
            [[16.0, 8.0, 9.0], [16.0, 8.0, 9.0]],
            dtype=torch.float32,
            device=device,
        ),
        retarget_grace_ticks=torch.full(
            shape, 16, dtype=torch.int32, device=device
        ),
    )


def _run_stage_trace(device: str) -> tuple[torch.Tensor, ...]:
    state = FastDamageRampState.empty(2, max_entities=3, device=device)
    parameters = _parameters(state)
    targets = torch.tensor(
        [[101, 102, 999], [201, 202, 999]],
        dtype=torch.int64,
        device=state.device,
    )
    stunned = torch.zeros_like(targets, dtype=torch.bool)
    snapshots: list[torch.Tensor] = []
    for tick in range(1, 81):
        result = pre_attack_damage_ramp_(
            state,
            parameters,
            current_target_stable_id=targets,
            stunned=stunned,
        )
        if tick in (1, 39, 40, 79, 80):
            snapshots.extend(
                (
                    result.connected_ticks.clone(),
                    result.stage.clone(),
                    result.damage_multiplier.clone(),
                )
            )
    return (*snapshots, state.observed_target_stable_id.clone())


def test_tower_and_mobile_like_ramps_use_exact_0_40_80_stages(
    tensor_device: str,
) -> None:
    trace = _run_stage_trace(tensor_device)
    # Snapshot groups are ticks, stage, multiplier for 1/39/40/79/80.
    expected_stage = (0, 0, 1, 1, 2)
    expected_multiplier = (1.0, 1.0, 4.0, 4.0, 16.0)
    for index, tick in enumerate((1, 39, 40, 79, 80)):
        ticks, stage, multiplier = trace[index * 3 : index * 3 + 3]
        assert ticks[:, :2].tolist() == [[tick, tick], [tick, tick]]
        assert stage[:, :2].tolist() == [
            [expected_stage[index], expected_stage[index]],
            [expected_stage[index], expected_stage[index]],
        ]
        # The first enabled lane uses tower-like values and the second uses
        # mobile continuous-damage values; the state machine is identical.
        assert multiplier[:, 0].tolist() == [expected_multiplier[index]] * 2
        mobile_expected = (1.0, 1.0, 2.0, 2.0, 8.0)[index]
        assert multiplier[:, 1].tolist() == [mobile_expected] * 2
        assert multiplier[:, 2].tolist() == [1.0, 1.0]


def test_target_change_loss_and_stun_reset_without_extra_state(
    tensor_device: str,
) -> None:
    state = FastDamageRampState.empty(1, max_entities=2, device=tensor_device)
    parameters = FastDamageRampParameters(
        enabled=torch.tensor([[True, True]], device=state.device),
        stage_1_ticks=torch.tensor([[2, 2]], dtype=torch.int32, device=state.device),
        stage_2_ticks=torch.tensor([[4, 4]], dtype=torch.int32, device=state.device),
        stage_0_damage_multiplier=torch.tensor([[1.0, 1.0]], device=state.device),
        stage_1_damage_multiplier=torch.tensor([[4.0, 4.0]], device=state.device),
        stage_2_damage_multiplier=torch.tensor([[16.0, 16.0]], device=state.device),
        retarget_grace_ticks=torch.tensor(
            [[16, 16]], dtype=torch.int32, device=state.device
        ),
    )
    no_stun = torch.zeros((1, 2), dtype=torch.bool, device=state.device)
    original = torch.tensor([[11, 21]], dtype=torch.int64, device=state.device)
    for _ in range(4):
        result = pre_attack_damage_ramp_(
            state,
            parameters,
            current_target_stable_id=original,
            stunned=no_stun,
        )
    assert result.stage.tolist() == [[2, 2]]

    replacement = torch.tensor([[12, 21]], dtype=torch.int64, device=state.device)
    changed = pre_attack_damage_ramp_(
        state,
        parameters,
        current_target_stable_id=replacement,
        stunned=no_stun,
    )
    assert changed.target_changed.tolist() == [[True, False]]
    assert changed.reset.tolist() == [[True, False]]
    assert changed.retarget_delay_ticks.tolist() == [[16, 0]]
    assert changed.connected_ticks.tolist() == [[1, 5]]
    assert changed.stage.tolist() == [[0, 2]]

    loss = pre_attack_damage_ramp_(
        state,
        parameters,
        current_target_stable_id=torch.tensor(
            [[0, 21]], dtype=torch.int64, device=state.device
        ),
        stunned=no_stun,
    )
    assert loss.reset.tolist() == [[True, False]]
    assert loss.retarget_delay_ticks.tolist() == [[16, 0]]
    assert loss.observed_target_stable_id.tolist() == [[0, 21]]
    assert loss.connected_ticks.tolist() == [[0, 6]]
    assert loss.damage_multiplier.tolist() == [[1.0, 16.0]]

    stunned = pre_attack_damage_ramp_(
        state,
        parameters,
        current_target_stable_id=torch.tensor(
            [[12, 21]], dtype=torch.int64, device=state.device
        ),
        stunned=torch.tensor([[False, True]], device=state.device),
    )
    # Fresh acquisition after a loss has no second retarget delay. Stun clears
    # the other channel without adding a cooldown owned by the stun itself.
    assert stunned.reset.tolist() == [[False, True]]
    assert stunned.retarget_delay_ticks.tolist() == [[0, 0]]
    assert stunned.observed_target_stable_id.tolist() == [[12, 0]]
    assert stunned.connected_ticks.tolist() == [[1, 0]]
    assert stunned.stage.tolist() == [[0, 0]]


def test_damage_ramp_trace_replays_deterministically(tensor_device: str) -> None:
    first = _run_stage_trace(tensor_device)
    second = _run_stage_trace(tensor_device)
    assert len(first) == len(second)
    assert all(
        torch.equal(left, right)
        for left, right in zip(first, second, strict=True)
    )


def test_damage_ramp_hot_path_has_no_host_sync_or_card_dispatch() -> None:
    source = inspect.getsource(pre_attack_damage_ramp_)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("InfernoTower", "InfernoDragon"):
        assert card_name not in source
