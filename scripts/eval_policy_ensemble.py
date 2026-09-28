from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import LoadedPolicy, evaluate, load_policy_checkpoint
from clasher.rl.model import PolicyOutput
from clasher.rl.reward_model import OBJECTIVE_V1, REWARD_PROFILES
from clasher.rl.train_recurrent import resolve_torch_device


class DeterministicPolicyEnsemble:
    """Run recurrent experts in lockstep and combine their deterministic actions."""

    def __init__(
        self,
        models: list[Any],
        *,
        method: str,
        weights: list[float],
    ) -> None:
        if not models:
            raise ValueError("at least one model is required")
        if len(models) != len(weights):
            raise ValueError("weights must match checkpoints")
        weight_tensor = torch.tensor(weights, dtype=torch.float32)
        if bool(torch.any(weight_tensor < 0)) or float(weight_tensor.sum()) <= 0:
            raise ValueError("weights must be non-negative with a positive sum")
        self.models = models
        self.method = method
        self.weights = (weight_tensor / weight_tensor.sum()).tolist()

    def initial_state(
        self, batch_size: int, *, device: torch.device
    ) -> list[tuple[torch.Tensor, torch.Tensor]]:
        return [
            model.initial_state(batch_size, device=device) for model in self.models
        ]

    @torch.no_grad()
    def act(
        self,
        inputs: Any,
        state: list[tuple[torch.Tensor, torch.Tensor]],
        *,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[Any], PolicyOutput]:
        if not deterministic:
            raise ValueError("ensemble evaluation currently requires deterministic actions")
        outputs = [
            model.forward(inputs, model_state)
            for model, model_state in zip(self.models, state, strict=True)
        ]
        expert_actions = [
            model._deterministic_actions(output, inputs.action_mask)
            for model, output in zip(self.models, outputs, strict=True)
        ]

        action_type_logits = sum(
            weight * output.action_type_logits
            for weight, output in zip(self.weights, outputs, strict=True)
        )
        location_logits = sum(
            weight * output.location_logits
            for weight, output in zip(self.weights, outputs, strict=True)
        )
        joint_logits = self.models[0]._joint_action_logits(
            action_type_logits, location_logits, inputs.action_mask
        )
        values = sum(
            weight * output.values
            for weight, output in zip(self.weights, outputs, strict=True)
        )
        combined = PolicyOutput(
            joint_logits=joint_logits,
            values=values,
            opponent_hand_logits=outputs[0].opponent_hand_logits,
            opponent_elixir=outputs[0].opponent_elixir,
            next_state=outputs[0].next_state,
            action_type_logits=action_type_logits,
            location_logits=location_logits,
        )

        if self.method == "average-logits":
            actions = self.models[0]._deterministic_actions(
                combined, inputs.action_mask
            )
        elif self.method == "max-value":
            value_stack = torch.stack([output.values for output in outputs], dim=0)
            selected = value_stack.argmax(dim=0)
            action_stack = torch.stack(expert_actions, dim=0)
            actions = action_stack.gather(0, selected.unsqueeze(0)).squeeze(0)
        else:
            flat_actions = torch.stack(expert_actions, dim=0).reshape(
                len(expert_actions), -1
            )
            selected_flat: list[int] = []
            for column in flat_actions.transpose(0, 1).tolist():
                counts = Counter(int(action) for action in column)
                best_count = max(counts.values())
                selected_flat.append(
                    next(action for action in column if counts[action] == best_count)
                )
            actions = torch.tensor(
                selected_flat, device=flat_actions.device, dtype=flat_actions.dtype
            ).reshape_as(expert_actions[0])

        distribution = combined.distribution()
        return (
            actions,
            distribution.log_prob(actions),
            combined.values,
            [output.next_state for output in outputs],
            combined,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a deterministic policy ensemble")
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument(
        "--method",
        choices=["average-logits", "majority", "max-value"],
        default="average-logits",
    )
    parser.add_argument("--weights", default=None)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=OBJECTIVE_V1
    )
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.torch_threads <= 0:
        raise ValueError("--torch-threads must be positive")
    torch.set_num_threads(args.torch_threads)
    device = resolve_torch_device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint_paths = [resolve_path(path, must_exist=True) for path in args.checkpoint]
    weights = (
        [float(value) for value in args.weights.split(",")]
        if args.weights
        else [1.0] * len(checkpoint_paths)
    )
    loaded = [
        load_policy_checkpoint(path, device=device, decks_path=decks_path)
        for path in checkpoint_paths
    ]
    reference_tokens = loaded[0].checkpoint["token_names"]
    reference_config = loaded[0].checkpoint["model_config"]
    for policy in loaded[1:]:
        if policy.checkpoint["token_names"] != reference_tokens:
            raise ValueError("ensemble checkpoints have different token vocabularies")
        if policy.checkpoint["model_config"] != reference_config:
            raise ValueError("ensemble checkpoints have different model configurations")

    candidate = LoadedPolicy(
        model=DeterministicPolicyEnsemble(
            [policy.model for policy in loaded], method=args.method, weights=weights
        ),
        builder=loaded[0].builder,
        checkpoint={"format_version": 2, "update": 0, "total_transitions": 0},
    )
    metrics = evaluate(
        candidate=candidate,
        decks_path=decks_path,
        games=args.games,
        seed=args.seed,
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
        opponent_mode="random",
        opponent=None,
        deterministic=True,
        quiet_engine=True,
        device=device,
        reward_profile=args.reward_profile,
    )
    payload = {
        "schema_version": 1,
        "checkpoints": [str(path) for path in checkpoint_paths],
        "method": args.method,
        "weights": weights,
        "seed": args.seed,
        "max_ticks": args.max_ticks,
        "metrics": metrics,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
