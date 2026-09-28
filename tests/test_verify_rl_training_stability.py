from __future__ import annotations

import pytest
import torch

from scripts.verify_rl_training_stability import verify_training_stability


def _checkpoint(update: int, *, approx_kl: float = 0.01) -> dict[str, object]:
    return {
        "update": update,
        "total_transitions": update * 8,
        "args": {"num_envs": 2, "rollout_steps": 4},
        "metrics": {
            "loss": 1.0,
            "policy_loss": 0.1,
            "value_loss": 0.2,
            "entropy": 0.3,
            "anchor_policy_kl": 0.001,
            "approx_kl": approx_kl,
            "clip_fraction": 0.1,
            "grad_norm": 1.0,
            "optimizer_steps": 2.0,
            "kl_early_stop": 0.0,
            "reward_mean": 0.0,
            "absolute_reward_mean": 0.1,
        },
        "model_state_dict": {"weight": torch.ones(2)},
    }


def test_verifies_contiguous_finite_bounded_phase() -> None:
    report = verify_training_stability(
        {"total_transitions": 80},
        [_checkpoint(11), _checkpoint(12)],
        start_update=11,
        end_update=12,
        max_approx_kl=0.03,
        max_anchor_policy_kl=0.01,
        max_clip_fraction=0.2,
    )

    assert report["passes"] is True
    assert report["transition_delta"] == 16
    assert [row["update"] for row in report["rows"]] == [11, 12]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row["metrics"].update(approx_kl=0.04), "approximate-KL"),
        (lambda row: row["metrics"].update(kl_early_stop=1.0), "early-stop"),
        (lambda row: row["metrics"].update(optimizer_steps=0.0), "optimizer"),
        (
            lambda row: row["model_state_dict"].update(
                weight=torch.tensor([float("nan")])
            ),
            "nonfinite model tensors",
        ),
    ],
)
def test_rejects_unstable_update(mutation, message: str) -> None:
    row = _checkpoint(11)
    mutation(row)

    with pytest.raises(ValueError, match=message):
        verify_training_stability(
            {"total_transitions": 80},
            [row],
            start_update=11,
            end_update=11,
            max_approx_kl=0.03,
            max_anchor_policy_kl=0.01,
            max_clip_fraction=0.2,
        )
