"""Fail closed when a bounded Clasher RL phase is numerically unstable."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch

REQUIRED_METRICS = (
    "loss",
    "policy_loss",
    "value_loss",
    "entropy",
    "anchor_policy_kl",
    "approx_kl",
    "clip_fraction",
    "grad_norm",
    "optimizer_steps",
    "kl_early_stop",
    "reward_mean",
    "absolute_reward_mean",
)


def verify_training_stability(
    parent: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    *,
    start_update: int,
    end_update: int,
    max_approx_kl: float,
    max_anchor_policy_kl: float,
    max_clip_fraction: float,
) -> dict[str, Any]:
    """Verify contiguous updates, transitions, finite state, and PPO metrics."""
    expected_updates = list(range(start_update, end_update + 1))
    if len(checkpoints) != len(expected_updates):
        raise ValueError("training stability audit received the wrong update count")
    parent_transitions = int(parent.get("total_transitions", -1))
    if parent_transitions < 0:
        raise ValueError("parent checkpoint lacks total_transitions")

    rows = []
    previous_transitions = parent_transitions
    for expected_update, payload in zip(expected_updates, checkpoints, strict=True):
        update = int(payload.get("update", -1))
        if update != expected_update:
            raise ValueError(
                f"expected update {expected_update}, received checkpoint update {update}"
            )
        args = payload.get("args") or {}
        transition_delta = int(args.get("num_envs", 0)) * int(
            args.get("rollout_steps", 0)
        )
        if transition_delta <= 0:
            raise ValueError(f"update {update} has invalid rollout dimensions")
        total_transitions = int(payload.get("total_transitions", -1))
        if total_transitions != previous_transitions + transition_delta:
            raise ValueError(
                f"update {update} transition count is not contiguous: "
                f"{total_transitions} != {previous_transitions} + {transition_delta}"
            )
        previous_transitions = total_transitions

        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            raise TypeError(f"update {update} lacks a metric dictionary")
        missing = [name for name in REQUIRED_METRICS if name not in metrics]
        if missing:
            raise ValueError(f"update {update} lacks stability metrics: {missing}")
        nonfinite_metrics = [
            name
            for name, value in metrics.items()
            if isinstance(value, (float, int)) and not math.isfinite(float(value))
        ]
        if nonfinite_metrics:
            raise ValueError(
                f"update {update} has nonfinite metrics: {nonfinite_metrics}"
            )
        if float(metrics["optimizer_steps"]) <= 0.0:
            raise ValueError(f"update {update} performed no optimizer steps")
        if float(metrics["kl_early_stop"]) != 0.0:
            raise ValueError(f"update {update} hit the KL early-stop boundary")
        if abs(float(metrics["approx_kl"])) > max_approx_kl:
            raise ValueError(f"update {update} exceeded the approximate-KL bound")
        if float(metrics["anchor_policy_kl"]) > max_anchor_policy_kl:
            raise ValueError(f"update {update} exceeded the anchor-KL bound")
        clip_fraction = float(metrics["clip_fraction"])
        if not 0.0 <= clip_fraction <= max_clip_fraction:
            raise ValueError(f"update {update} exceeded the clipping bound")

        state = payload.get("model_state_dict")
        if not isinstance(state, dict) or not state:
            raise TypeError(f"update {update} lacks model state")
        nonfinite_tensors = [
            name
            for name, value in state.items()
            if isinstance(value, torch.Tensor)
            and value.is_floating_point()
            and not bool(torch.isfinite(value).all())
        ]
        if nonfinite_tensors:
            raise ValueError(
                f"update {update} has nonfinite model tensors: {nonfinite_tensors}"
            )
        rows.append(
            {
                "update": update,
                "total_transitions": total_transitions,
                "transition_delta": transition_delta,
                "loss": float(metrics["loss"]),
                "approx_kl": float(metrics["approx_kl"]),
                "anchor_policy_kl": float(metrics["anchor_policy_kl"]),
                "clip_fraction": clip_fraction,
                "grad_norm": float(metrics["grad_norm"]),
                "optimizer_steps": float(metrics["optimizer_steps"]),
            }
        )
    return {
        "schema_version": 1,
        "start_update": start_update,
        "end_update": end_update,
        "updates": len(rows),
        "transition_delta": previous_transitions - parent_transitions,
        "thresholds": {
            "max_approx_kl": max_approx_kl,
            "max_anchor_policy_kl": max_anchor_policy_kl,
            "max_clip_fraction": max_clip_fraction,
            "allow_kl_early_stop": False,
        },
        "rows": rows,
        "passes": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--checkpoint-dir", required=True, type=Path)
    parser.add_argument("--start-update", required=True, type=int)
    parser.add_argument("--end-update", required=True, type=int)
    parser.add_argument("--max-approx-kl", type=float, default=0.03)
    parser.add_argument("--max-anchor-policy-kl", type=float, default=0.01)
    parser.add_argument("--max-clip-fraction", type=float, default=0.20)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.start_update > args.end_update:
        raise ValueError("start update cannot exceed end update")

    parent = torch.load(args.parent, map_location="cpu", weights_only=False)
    paths = [
        args.checkpoint_dir / f"policy_v2_update_{update:06d}.pt"
        for update in range(args.start_update, args.end_update + 1)
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing bounded-phase checkpoints: {missing}")
    checkpoints = [
        torch.load(path, map_location="cpu", weights_only=False) for path in paths
    ]
    report = verify_training_stability(
        parent,
        checkpoints,
        start_update=args.start_update,
        end_update=args.end_update,
        max_approx_kl=args.max_approx_kl,
        max_anchor_policy_kl=args.max_anchor_policy_kl,
        max_clip_fraction=args.max_clip_fraction,
    )
    report.update(
        {
            "parent": str(args.parent.resolve()),
            "checkpoint_dir": str(args.checkpoint_dir.resolve()),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "rl_training_stability_verified", **report}))


if __name__ == "__main__":
    main()
