#!/usr/bin/env python3
"""Bounded feasibility probe for value-ranked Simple Gym root actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.simple_pytorch_backend import (
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
)
from clasher.rl.simple_tensor_collector import (
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


class ForcedLearnerRootPolicy:
    """Force vectorized roots, then use deterministic learner continuation."""

    def __init__(
        self,
        base: object,
        *,
        learner_players: torch.Tensor,
        root_actions: torch.Tensor | None,
    ) -> None:
        self.base = base
        self.learner_players = learner_players
        self.root_actions = root_actions
        self.calls = 0

    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        decision = self.base(boundary)  # type: ignore[operator]
        actions = decision.actions.clone()
        rows = torch.arange(actions.shape[0], device=actions.device)
        if self.calls == 0 and self.root_actions is not None:
            actions[rows, self.learner_players] = self.root_actions
        else:
            learner_state = self.base._state_from_prefixed_mapping(  # type: ignore[attr-defined]
                boundary.recurrent_inputs, "learner"
            )
            deterministic, *_tail = self.base.model.act(  # type: ignore[attr-defined]
                self.base.inputs(boundary),  # type: ignore[attr-defined]
                learner_state,
                deterministic=True,
            )
            learner_actions = deterministic[:, 0].reshape(actions.shape[0], 2)
            actions[rows, self.learner_players] = learner_actions[
                rows, self.learner_players
            ]
        decision = replace(decision, actions=actions)
        self.calls += 1
        return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1193401)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--warmup-steps", type=int, default=20)
    parser.add_argument("--horizon-steps", type=int, default=24)
    parser.add_argument("--action-samples", type=int, default=8)
    parser.add_argument("--opponent-strategy", default="balanced")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    return parser.parse_args()


def load_collector(args: argparse.Namespace) -> SimplePytorchTrainingCollector:
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    vocabulary = load_current_client_typed_vocabulary()
    if tuple(payload["token_names"]) != vocabulary.token_names:
        raise ValueError("checkpoint vocabulary differs from current typed vocabulary")
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=config.max_entities,
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=True,
    )
    device = torch.device(args.device)
    model = ClasherPolicy(config, builder.card_stat_features).to(device).eval()
    model.load_state_dict(payload["model_state_dict"], strict=True)
    return SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=args.batch_size,
        device=device,
        decision_interval=8,
        gamma=0.995,
        supported_decks_path="training_decks/simple_gym_supported_v1.json",
        typed_vocabulary_path=(
            "reports/current_client_youtube_stable_vocabulary_v1.json"
        ),
        mirror_match=False,
        opponent_mode="strategy",
        opponent_strategy=args.opponent_strategy,
        learner_deck_name="Hog 2.6 Cycle",
        learner_sampling_temperature=0.1,
        max_effects=64,
    )


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.warmup_steps < 0 or args.horizon_steps < 1:
        raise ValueError("batch/warmup/horizon arguments are invalid")
    if args.action_samples < 2:
        raise ValueError("action-samples must be at least two")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    args.batch_size = args.action_samples
    collector = load_collector(args)
    model = collector.policy.model
    state = model.initial_state(args.batch_size, device=args.device)
    base_policy = collector.collector.policy
    if args.warmup_steps:
        collector.collector.policy = ForcedLearnerRootPolicy(
            base_policy,
            learner_players=collector.learner_players,
            root_actions=None,
        )
        _arrays, state, *_history = collector.collect(args.warmup_steps, state)
        collector.collector.policy = base_policy

    # Turn one real public state into an exact candidate-leading tensor batch.
    collector.collector.bridge.runtime.fanout_row_(0)
    history = collector.collector.bridge.adapter.history
    for tensor in (
        history.previous_actions,
        history.previous_rewards,
        history.episode_starts,
    ):
        tensor.copy_(tensor[:1].expand_as(tensor))
    state = tuple(value[:1].expand_as(value).clone() for value in state)
    collector.learner_players.fill_(0)
    collector.policy.learner_players.fill_(0)

    observation = collector.collector.bridge.observe()
    packet = collector.collector.public_mask_provider(
        SimpleTensorMaskRequest(observation, args.warmup_steps, False)
    )
    for descriptor in fields(observation.actor):
        tensor = getattr(observation.actor, descriptor.name)
        if not torch.equal(tensor, tensor[:1].expand_as(tensor)):
            raise RuntimeError(
                f"fanout actor field {descriptor.name} is not row-exact"
            )
    if not torch.equal(packet.masks, packet.masks[:1].expand_as(packet.masks)):
        raise RuntimeError("fanout public masks are not row-exact")
    rows = torch.arange(args.batch_size, device=collector.learner_players.device)
    learner_masks = packet.masks[rows, collector.learner_players]
    common_legal = learner_masks.all(dim=0).cpu().numpy()
    legal = np.flatnonzero(common_legal).astype(np.int64, copy=False)
    if legal.size < 2:
        raise RuntimeError("probe state has fewer than two common legal actions")
    candidates = sample_action_subset(
        legal,
        sample_limit=args.action_samples,
        no_op_action=model.num_actions - 2,
        rng=np.random.default_rng(args.seed),
    )

    if candidates.size != args.batch_size:
        raise RuntimeError("vectorized probe candidate count changed")
    root_actions = torch.as_tensor(
        candidates,
        dtype=torch.int64,
        device=collector.learner_players.device,
    )
    collector.collector.policy = ForcedLearnerRootPolicy(
        base_policy,
        learner_players=collector.learner_players,
        root_actions=root_actions,
    )
    started = time.perf_counter()
    arrays, *_tail = collector.collect(
        args.horizon_steps,
        (state[0].clone(), state[1].clone()),
    )
    discounts = np.power(0.995, np.arange(args.horizon_steps, dtype=np.float64))
    discounted = (arrays["rewards"].astype(np.float64) * discounts[None, :]).sum(
        axis=1
    )
    done = arrays["dones"].any(axis=1)
    rows_out: list[dict[str, Any]] = []
    for index, action in enumerate(candidates.tolist()):
        rows_out.append(
            {
                "action": int(action),
                "discounted_return_mean": float(discounted[index]),
                "terminal": bool(done[index]),
            }
        )
    rows_out.sort(key=lambda row: float(row["discounted_return_mean"]), reverse=True)
    elapsed = time.perf_counter() - started
    payload = {
        "schema": "clasher.simple-counterfactual-teacher-probe.v2",
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "seed": args.seed,
        "batch_size": args.batch_size,
        "warmup_steps": args.warmup_steps,
        "horizon_steps": args.horizon_steps,
        "action_samples": len(rows_out),
        "opponent_strategy": args.opponent_strategy,
        "device": args.device,
        "elapsed_seconds": elapsed,
        "candidate_actions_per_second": len(rows_out) / elapsed,
        "rows": rows_out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
