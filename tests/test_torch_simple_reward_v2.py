from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from clasher.torch_sim.simple_reward_v2 import (
    SIMPLE_REWARD_V2_CONTRACT_ID,
    SimpleRewardV2Config,
    SimpleRewardV2ContractError,
    simple_objective_v1_breakdown,
    simple_reward_v2,
    simple_reward_v2_digest,
    simple_reward_v2_metadata,
    validate_simple_reward_v2_metadata,
)
from clasher.torch_sim.simple_state import FastGymState


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _tower_state(
    device: torch.device,
    hp: list[list[list[float]]],
) -> FastGymState:
    state = FastGymState.empty(len(hp), max_entities=6, device=device)
    values = torch.tensor(hp, dtype=torch.float32, device=device)
    state.hp[:, :6] = values.reshape(len(hp), 6)
    state.max_hp[:, :6] = torch.tensor(
        [[[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]]] * len(hp),
        dtype=torch.float32,
        device=device,
    ).reshape(len(hp), 6)
    return state


def _initial(device: torch.device, batch: int) -> torch.Tensor:
    return torch.tensor(
        [[[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]]] * batch,
        dtype=torch.float32,
        device=device,
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_objective_v1_components_match_hand_computed_public_tower_cases(
    device_name: str,
) -> None:
    device = _device(device_name)
    state = _tower_state(
        device,
        [
            [[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]],
            [[100.0, 100.0, 200.0], [50.0, 100.0, 200.0]],
            [[100.0, 100.0, 200.0], [100.0, 100.0, 180.0]],
            [[100.0, 100.0, 200.0], [0.0, 100.0, 200.0]],
            [[100.0, 100.0, 200.0], [100.0, 100.0, 0.0]],
        ],
    )
    config = SimpleRewardV2Config(gamma=0.995)
    breakdown = simple_objective_v1_breakdown(state, _initial(device, 5), config)

    torch.testing.assert_close(
        breakdown.crowns,
        torch.tensor([0.0, 0.0, 0.0, 1.0 / 3.0, 1.0], device=device),
    )
    torch.testing.assert_close(
        breakdown.princess_pressure,
        torch.tensor([0.0, 0.25, 0.0, 0.5, 0.0], device=device),
    )
    torch.testing.assert_close(
        breakdown.king_pressure,
        torch.tensor([0.0, 0.0, 0.005, 0.0, 0.0], device=device),
    )
    torch.testing.assert_close(
        breakdown.tiebreak_edge,
        torch.tensor([0.0, 0.25, 0.0, 0.0, 0.0], device=device),
    )
    torch.testing.assert_close(
        breakdown.early_king_penalty,
        torch.tensor([0.0, 0.0, 0.1, 0.0, 1.0], device=device),
    )
    torch.testing.assert_close(
        breakdown.potential,
        torch.tensor(
            [0.0, 0.0875, -0.0195, 0.55 / 3.0 + 0.125, 0.35],
            device=device,
        ),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_potential_is_antisymmetric_under_player_seat_swap(device_name: str) -> None:
    device = _device(device_name)
    hp = [[[75.0, 0.0, 190.0], [20.0, 100.0, 160.0]]]
    state = _tower_state(device, hp)
    swapped = _tower_state(device, [[hp[0][1], hp[0][0]]])
    config = SimpleRewardV2Config(gamma=0.995)

    actual = simple_objective_v1_breakdown(state, _initial(device, 1), config).potential
    reverse = simple_objective_v1_breakdown(
        swapped, _initial(device, 1)[:, [1, 0]], config
    ).potential
    torch.testing.assert_close(actual, -reverse)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_reward_uses_decision_gamma_and_absorbing_terminal_potential(
    device_name: str,
) -> None:
    device = _device(device_name)
    initial = _initial(device, 1)
    neutral = _tower_state(device, [[[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]]])
    edge = _tower_state(device, [[[100.0, 100.0, 200.0], [50.0, 100.0, 200.0]]])
    terminal = _tower_state(device, [[[100.0, 100.0, 200.0], [0.0, 0.0, 0.0]]])
    config = SimpleRewardV2Config(gamma=0.995)

    active = simple_reward_v2(
        neutral,
        edge,
        initial,
        torch.tensor([False], device=device),
        torch.tensor([-2], dtype=torch.int8, device=device),
        config,
    )
    torch.testing.assert_close(
        active,
        torch.tensor([[0.995 * 0.0875, -0.995 * 0.0875]], device=device),
    )

    won = simple_reward_v2(
        edge,
        terminal,
        initial,
        torch.tensor([True], device=device),
        torch.tensor([0], dtype=torch.int8, device=device),
        config,
    )
    torch.testing.assert_close(
        won, torch.tensor([[1.0 - 0.0875, -(1.0 - 0.0875)]], device=device)
    )
    assert torch.equal(won.sum(dim=1), torch.zeros(1, device=device))

    drawn = simple_reward_v2(
        edge,
        terminal,
        initial,
        torch.tensor([True], device=device),
        torch.tensor([-1], dtype=torch.int8, device=device),
        config,
    )
    torch.testing.assert_close(drawn, torch.tensor([[-0.0875, 0.0875]], device=device))


def test_tiebreak_edge_uses_shared_rounded_fixed_point_scale() -> None:
    device = torch.device("cpu")
    state = _tower_state(
        device,
        [[[80.0004, 100.0, 200.0], [70.0004, 100.0, 200.0]]],
    )
    breakdown = simple_objective_v1_breakdown(
        state, _initial(device, 1), SimpleRewardV2Config(gamma=0.995)
    )
    torch.testing.assert_close(breakdown.tiebreak_edge, torch.tensor([0.05]))


def test_metadata_digest_is_stable_and_compatibility_fails_closed() -> None:
    config = SimpleRewardV2Config(gamma=0.995)
    metadata = simple_reward_v2_metadata(config)
    assert metadata["reward_contract_id"] == SIMPLE_REWARD_V2_CONTRACT_ID
    assert metadata["reward_contract_digest"] == simple_reward_v2_digest(config)
    assert metadata["reward_contract_digest"] == (
        "ef3914ce85d8c820cd02cef18de4dbe52460c7ddee70cfd615ef7538a8d50d66"
    )
    validate_simple_reward_v2_metadata(metadata, config)

    for missing in tuple(metadata):
        incomplete = dict(metadata)
        incomplete.pop(missing)
        with pytest.raises(SimpleRewardV2ContractError, match="missing"):
            validate_simple_reward_v2_metadata(incomplete, config)

    with pytest.raises(SimpleRewardV2ContractError, match="spec mismatch"):
        validate_simple_reward_v2_metadata(metadata, replace(config, gamma=0.99))

    corrupt = dict(metadata)
    corrupt["reward_contract_digest"] = "0" * 64
    with pytest.raises(SimpleRewardV2ContractError, match="digest is corrupt"):
        validate_simple_reward_v2_metadata(corrupt, config)

    wrong_id = dict(metadata)
    wrong_id["reward_contract_id"] = "simple-tower-delta-v1"
    with pytest.raises(SimpleRewardV2ContractError, match="ID mismatch"):
        validate_simple_reward_v2_metadata(wrong_id, config)


@pytest.mark.parametrize(
    "config, message",
    [
        (lambda: SimpleRewardV2Config(gamma=0.0), "gamma"),
        (lambda: SimpleRewardV2Config(gamma=1.01), "gamma"),
        (lambda: SimpleRewardV2Config(gamma=float("nan")), "finite"),
        (
            lambda: SimpleRewardV2Config(
                gamma=0.995, early_king_chip_penalty_weight=-0.1
            ),
            "non-negative",
        ),
    ],
)
def test_config_rejects_invalid_numeric_semantics(config: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        config()  # type: ignore[operator]


def test_tensor_contract_rejects_malformed_inputs() -> None:
    state = _tower_state(
        torch.device("cpu"),
        [[[100.0, 100.0, 200.0], [100.0, 100.0, 200.0]]],
    )
    config = SimpleRewardV2Config(gamma=0.995)
    with pytest.raises(SimpleRewardV2ContractError, match="initial_tower_hp"):
        simple_reward_v2(
            state,
            state,
            torch.ones((1, 2, 2)),
            torch.tensor([False]),
            torch.tensor([-2], dtype=torch.int8),
            config,
        )
    with pytest.raises(SimpleRewardV2ContractError, match="done"):
        simple_reward_v2(
            state,
            state,
            _initial(torch.device("cpu"), 1),
            torch.tensor([0], dtype=torch.int64),
            torch.tensor([-2], dtype=torch.int8),
            config,
        )
