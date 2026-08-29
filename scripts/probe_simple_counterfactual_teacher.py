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
    parser.add_argument("--state-output", type=Path, default=None)
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
    opponent_mode = "random" if args.opponent_strategy == "random" else "strategy"
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
        opponent_mode=opponent_mode,
        opponent_strategy=(
            None if opponent_mode == "random" else args.opponent_strategy
        ),
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
    warmup_arrays: dict[str, Any] | None = None
    if args.warmup_steps:
        collector.collector.policy = ForcedLearnerRootPolicy(
            base_policy,
            learner_players=collector.learner_players,
            root_actions=None,
        )
        warmup_arrays, state, *_history = collector.collect(
            args.warmup_steps, state
        )
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
    recurrent_inputs = collector._joint_recurrent_inputs(state)
    boundary = collector.collector._policy_boundary(
        observation,
        packet,
        recurrent_inputs,
        args.warmup_steps,
    )
    learner_state = collector.policy._state_from_prefixed_mapping(
        recurrent_inputs, "learner"
    )
    rows = torch.arange(args.batch_size, device=collector.learner_players.device)
    with torch.no_grad():
        parent_actions, *_parent_tail = model.act(
            collector.policy.inputs(boundary),
            learner_state,
            deterministic=True,
        )
    parent_action = int(
        parent_actions[:, 0]
        .reshape(args.batch_size, 2)[rows, collector.learner_players][0]
        .item()
    )
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
    if parent_action not in candidates:
        replaceable = np.flatnonzero(candidates != model.num_actions - 2)
        if replaceable.size == 0:
            raise RuntimeError("candidate sample has no slot for the parent action")
        candidates[replaceable[-1]] = parent_action
        candidates = np.unique(candidates)

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
        "parent_action": parent_action,
        "elapsed_seconds": elapsed,
        "candidate_actions_per_second": len(rows_out) / elapsed,
        "rows": rows_out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.state_output is not None:
        best_action = int(rows_out[0]["action"])
        actor = observation.actor
        learner = int(collector.learner_players[0].item())

        def trajectory(name: str, root: np.ndarray) -> np.ndarray:
            prefix = (
                np.empty((0, *root.shape), dtype=root.dtype)
                if warmup_arrays is None
                else np.asarray(warmup_arrays[name][0])
            )
            combined: np.ndarray = np.concatenate((prefix, root[None]), axis=0)
            return combined

        entity_ids = trajectory(
            "entity_ids", actor.entity_ids[0, learner].cpu().numpy()
        )
        entity_features = trajectory(
            "entity_features", actor.entity_features[0, learner].cpu().numpy()
        )
        entity_mask = trajectory(
            "entity_mask", actor.entity_mask[0, learner].cpu().numpy()
        )
        hand_ids = trajectory(
            "hand_ids", actor.hand_ids[0, learner].cpu().numpy()
        )
        global_features = trajectory(
            "global_features", actor.global_features[0, learner].cpu().numpy()
        )
        action_masks = trajectory(
            "action_masks", packet.masks[0, learner].cpu().numpy()
        )
        previous_actions = trajectory(
            "previous_actions",
            np.asarray(observation.previous_actions[0, learner].cpu().item()),
        )
        previous_rewards: np.ndarray = trajectory(
            "previous_rewards",
            np.asarray(
                observation.previous_rewards[0, learner].cpu().item(),
                dtype=np.float64,
            ),
        ).astype(np.float64, copy=False)
        episode_starts = trajectory(
            "episode_starts",
            np.asarray(observation.episode_starts[0, learner].cpu().item()),
        )
        warmup_actions = (
            np.empty((0,), dtype=np.int64)
            if warmup_arrays is None
            else np.asarray(warmup_arrays["actions"][0], dtype=np.int64)
        )
        expert_actions = np.concatenate(
            (warmup_actions, np.asarray([best_action], dtype=np.int64))
        )
        valid = np.zeros(expert_actions.shape, dtype=np.bool_)
        valid[-1] = True
        placement = best_action < model.num_actions - 2
        metadata = {
            "schema": "clasher.simple-counterfactual-recurrent-example.v1",
            "source_probe": str(args.output.resolve()),
            "source_probe_sha256": hashlib.sha256(
                args.output.read_bytes()
            ).hexdigest(),
            "seed": args.seed,
            "opponent_strategy": args.opponent_strategy,
            "parent_action": parent_action,
            "best_action": best_action,
            "best_return": float(rows_out[0]["discounted_return_mean"]),
        }
        args.state_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            args.state_output,
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=global_features,
            action_masks=action_masks,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_starts=episode_starts,
            expert_actions=expert_actions,
            expert_action_supervision_valid=valid,
            expert_card_supervision_valid=valid & placement,
            expert_tile_supervision_valid=valid & placement,
            episode_ids=np.full(expert_actions.shape, args.seed, dtype=np.int64),
            source_frames=np.arange(expert_actions.size, dtype=np.int64),
            metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
        )


if __name__ == "__main__":
    main()
