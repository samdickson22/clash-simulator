#!/usr/bin/env python3
"""Bounded feasibility probe for value-ranked Simple Gym root actions."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import torch

from clasher.rl.common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SimplePytorchTrainingCollector,
    SimpleTensorStrategyOpponent,
    load_current_client_typed_vocabulary,
)
from clasher.rl.simple_tensor_collector import (
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.rl.strategy_bots import STRATEGY_NAMES
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.simple_adapter import SimpleGymHistory
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


class ForcedLearnerRootPolicy:
    """Force vectorized roots, then use deterministic learner continuation."""

    def __init__(
        self,
        base: object,
        *,
        learner_players: torch.Tensor,
        root_actions: torch.Tensor | None,
        common_random_opponent: bool = False,
    ) -> None:
        self.base = base
        self.learner_players = learner_players
        self.root_actions = root_actions
        self.common_random_opponent = common_random_opponent
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
        if self.common_random_opponent:
            opponent_players = 1 - self.learner_players
            opponent_masks = boundary.public_action_masks[rows, opponent_players]
            legal_counts = opponent_masks.sum(dim=-1)
            if bool((legal_counts == 0).any()):
                raise RuntimeError("random opponent has no legal action")
            quantile = torch.rand((), device=opponent_masks.device)
            ranks = torch.floor(quantile * legal_counts).to(torch.long)
            cumulative = opponent_masks.to(torch.int64).cumsum(dim=-1)
            opponent_actions = (cumulative > ranks[:, None]).to(torch.int64).argmax(
                dim=-1
            )
            actions[rows, opponent_players] = opponent_actions
        decision = replace(decision, actions=actions)
        self.calls += 1
        return cast(SimpleTensorPolicyDecision, decision)


def select_stratified_action_subset(
    legal_actions: np.ndarray,
    joint_logits: np.ndarray,
    *,
    sample_limit: int,
    no_op_action: int,
    parent_action: int,
    proposal_actions: np.ndarray | None = None,
    random_fraction: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Select legal root actions across cards and arena regions.

    Uniformly sampling a flat 4x18x32 action space almost never compares the
    useful tile for each card.  This selector reserves the observed parent and
    wait actions, round-robins high-logit actions across all playable hand
    slots and coarse spatial buckets, then spends a bounded fraction on
    uniform exploration.  It is a proposal mechanism only: the exact rollout
    return remains the teacher authority.
    """

    legal = np.asarray(legal_actions, dtype=np.int64)
    logits = np.asarray(joint_logits, dtype=np.float64)
    if legal.ndim != 1 or logits.ndim != 1:
        raise ValueError("legal actions and joint logits must be rank one")
    if sample_limit < 2 or sample_limit > legal.size:
        raise ValueError("sample limit must be between two and the legal count")
    if not 0.0 <= random_fraction < 1.0:
        raise ValueError("random fraction must be in [0, 1)")
    legal_set = set(legal.tolist())
    proposed = (
        np.empty((0,), dtype=np.int64)
        if proposal_actions is None
        else np.asarray(proposal_actions, dtype=np.int64)
    )
    if proposed.ndim != 1:
        raise ValueError("proposal actions must be rank one")
    required_actions = tuple(
        dict.fromkeys((no_op_action, parent_action, *proposed.tolist()))
    )
    if len(required_actions) > sample_limit:
        raise ValueError("required and proposed actions exceed the sample limit")
    for required in required_actions:
        if required not in legal_set:
            raise ValueError(f"required action {required} is not legal")
    if int(legal.max()) >= logits.size:
        raise ValueError("joint logits do not cover every legal action")

    selected: list[int] = []
    selected_set: set[int] = set()

    def add(action: int) -> None:
        if action not in selected_set and len(selected) < sample_limit:
            selected.append(action)
            selected_set.add(action)

    add(no_op_action)
    add(parent_action)
    for action in proposed.tolist():
        add(int(action))
    remaining_budget = sample_limit - len(selected)
    random_budget = min(
        remaining_budget,
        round(remaining_budget * random_fraction),
    )
    structured_budget = remaining_budget - random_budget

    # Build one ranked list per hand slot.  The first item is the best legal
    # action for that card; subsequent items are the best action in each
    # canonical lane/depth bucket, followed by the remaining policy ranking.
    by_slot: list[list[int]] = []
    for slot in range(NUM_HAND_SLOTS):
        start = slot * NUM_TILES
        stop = start + NUM_TILES
        slot_actions = legal[(legal >= start) & (legal < stop)]
        if not slot_actions.size:
            by_slot.append([])
            continue
        ordered = slot_actions[np.argsort(-logits[slot_actions], kind="stable")]
        candidates: list[int] = [int(ordered[0])]
        for depth_start, depth_stop in ((0, 8), (8, 16), (16, 24), (24, 32)):
            for lane_start, lane_stop in ((0, 9), (9, 18)):
                tile = slot_actions - start
                x = tile % BOARD_WIDTH
                y = tile // BOARD_WIDTH
                in_bucket = (
                    (x >= lane_start)
                    & (x < lane_stop)
                    & (y >= depth_start)
                    & (y < depth_stop)
                )
                bucket = slot_actions[in_bucket]
                if bucket.size:
                    candidates.append(int(bucket[np.argmax(logits[bucket])]))
        candidates.extend(int(action) for action in ordered.tolist())
        by_slot.append(list(dict.fromkeys(candidates)))

    cursors = [0] * NUM_HAND_SLOTS
    while structured_budget > 0:
        progressed = False
        for slot in range(NUM_HAND_SLOTS):
            options = by_slot[slot]
            while cursors[slot] < len(options):
                action = options[cursors[slot]]
                cursors[slot] += 1
                if action not in selected_set:
                    add(action)
                    structured_budget -= 1
                    progressed = True
                    break
            if structured_budget == 0:
                break
        if not progressed:
            break

    unexplored = np.asarray(
        [action for action in legal.tolist() if action not in selected_set],
        dtype=np.int64,
    )
    random_count = min(random_budget, int(unexplored.size))
    if random_count:
        for action in rng.choice(unexplored, size=random_count, replace=False):
            add(int(action))

    # If rounding, missing hand slots, or a tiny legal set left capacity, fill
    # it with the strongest remaining legal actions without changing the RNG.
    if len(selected) < sample_limit:
        remainder = np.asarray(
            [action for action in legal.tolist() if action not in selected_set],
            dtype=np.int64,
        )
        ordered = remainder[np.argsort(-logits[remainder], kind="stable")]
        for action in ordered.tolist():
            add(int(action))
            if len(selected) == sample_limit:
                break
    if len(selected) != sample_limit:
        raise RuntimeError("stratified candidate selection changed batch size")
    return np.sort(np.asarray(selected, dtype=np.int64))


def truncated_n_step_returns(
    rewards: np.ndarray,
    dones: np.ndarray,
    bootstrap_values: np.ndarray,
    *,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return per-branch n-step values without crossing episode boundaries."""

    reward_rows = np.asarray(rewards, dtype=np.float64)
    done_rows = np.asarray(dones, dtype=np.bool_)
    bootstrap = np.asarray(bootstrap_values, dtype=np.float64).reshape(-1)
    if reward_rows.ndim != 2 or done_rows.shape != reward_rows.shape:
        raise ValueError("rewards and dones must have equal [batch, time] shape")
    if bootstrap.shape != (reward_rows.shape[0],):
        raise ValueError("bootstrap values must have one value per branch")
    if not 0.0 < gamma <= 1.0:
        raise ValueError("gamma must be in (0, 1]")

    horizon = reward_rows.shape[1]
    discounts = np.power(gamma, np.arange(horizon, dtype=np.float64))
    terminal = done_rows.any(axis=1)
    first_terminal = np.where(terminal, done_rows.argmax(axis=1), horizon)
    valid = np.arange(horizon)[None, :] <= first_terminal[:, None]
    reward_return = (reward_rows * discounts[None, :] * valid).sum(axis=1)
    bootstrap_return = np.where(
        terminal,
        0.0,
        np.power(gamma, horizon) * bootstrap,
    )
    return reward_return + bootstrap_return, reward_return, bootstrap_return


def collect_counterfactual_branches(
    collector: SimplePytorchTrainingCollector,
    state: tuple[torch.Tensor, torch.Tensor],
    *,
    horizon_steps: int,
    stop_when_all_terminal: bool,
    chunk_steps: int,
) -> tuple[
    dict[str, Any],
    tuple[torch.Tensor, torch.Tensor],
]:
    """Collect exact branches, optionally stopping after every first terminal."""

    if horizon_steps < 1 or chunk_steps < 1:
        raise ValueError("counterfactual horizon and chunk size must be positive")
    if not stop_when_all_terminal:
        arrays, next_state, *_tail = collector.collect(
            horizon_steps, state, include_terminal_winners=True
        )
        return arrays, next_state

    remaining = horizon_steps
    next_state = state
    rewards: list[np.ndarray] = []
    dones: list[np.ndarray] = []
    winners: list[np.ndarray] = []
    seen_terminal: np.ndarray | None = None
    last_arrays: dict[str, Any] | None = None
    while remaining:
        count = min(chunk_steps, remaining)
        arrays, next_state, *_tail = collector.collect(
            count, next_state, include_terminal_winners=True
        )
        reward_chunk = np.asarray(arrays["rewards"])
        done_chunk = np.asarray(arrays["dones"], dtype=np.bool_)
        winner_chunk = np.asarray(arrays["terminal_winners"], dtype=np.int64)
        if (
            reward_chunk.ndim != 2
            or done_chunk.shape != reward_chunk.shape
            or winner_chunk.shape != done_chunk.shape
        ):
            raise RuntimeError("counterfactual collector changed reward/done shape")
        rewards.append(reward_chunk)
        dones.append(done_chunk)
        winners.append(winner_chunk)
        terminal_now = np.asarray(done_chunk.any(axis=1), dtype=np.bool_)
        if seen_terminal is None:
            seen_terminal = terminal_now.copy()
        else:
            seen_terminal = np.logical_or(seen_terminal, terminal_now)
        last_arrays = arrays
        remaining -= count
        assert seen_terminal is not None
        if bool(seen_terminal.all()):
            break
    if last_arrays is None:
        raise RuntimeError("counterfactual collection produced no chunks")
    combined = dict(last_arrays)
    combined["rewards"] = np.concatenate(rewards, axis=1)
    combined["dones"] = np.concatenate(dones, axis=1)
    combined["terminal_winners"] = np.concatenate(winners, axis=1)
    return combined, next_state


def first_terminal_outcomes(
    dones: np.ndarray,
    winners: np.ndarray,
    learner_players: np.ndarray,
) -> np.ndarray:
    done_rows = np.asarray(dones, dtype=np.bool_)
    winner_rows = np.asarray(winners, dtype=np.int64)
    learners = np.asarray(learner_players, dtype=np.int64).reshape(-1)
    if done_rows.ndim != 2 or winner_rows.shape != done_rows.shape:
        raise ValueError("terminal done/winner arrays must have equal [batch, time] shape")
    if learners.shape != (done_rows.shape[0],):
        raise ValueError("learner player array must have one entry per branch")
    terminal = done_rows.any(axis=1)
    first_terminal = np.where(
        terminal,
        done_rows.argmax(axis=1),
        done_rows.shape[1] - 1,
    )
    terminal_winners = winner_rows[np.arange(done_rows.shape[0]), first_terminal]
    return np.where(
        ~terminal,
        0,
        np.where(
            terminal_winners == learners,
            1,
            np.where(terminal_winners < 0, 0, -1),
        ),
    ).astype(np.int8, copy=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1193401)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--warmup-steps", type=int, default=20)
    parser.add_argument("--horizon-steps", type=int, default=24)
    parser.add_argument("--action-samples", type=int, default=8)
    parser.add_argument("--random-candidate-fraction", type=float, default=0.25)
    parser.add_argument("--opponent-strategy", default="balanced")
    parser.add_argument(
        "--proposal-strategy",
        action="append",
        default=[],
        dest="proposal_strategies",
        help="include this tensor strategy's learner action in every root batch",
    )
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--stop-when-all-terminal", action="store_true")
    parser.add_argument("--collection-chunk-steps", type=int, default=32)
    parser.add_argument("--state-output", type=Path, default=None)
    return parser.parse_args()


def load_collector(
    args: argparse.Namespace, *, batch_size: int | None = None
) -> SimplePytorchTrainingCollector:
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
    opponent_mode: Literal["random", "strategy"] = (
        "random" if args.opponent_strategy == "random" else "strategy"
    )
    return SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=args.batch_size if batch_size is None else batch_size,
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
    if args.collection_chunk_steps < 1:
        raise ValueError("collection chunk steps must be positive")
    if args.action_samples < 2:
        raise ValueError("action-samples must be at least two")
    unknown_proposals = set(args.proposal_strategies) - set(STRATEGY_NAMES)
    if unknown_proposals:
        raise ValueError(f"unknown proposal strategies: {sorted(unknown_proposals)}")
    if len(set(args.proposal_strategies)) != len(args.proposal_strategies):
        raise ValueError("proposal strategies must be unique")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    args.batch_size = args.action_samples
    warmup_collector = None
    warmup_state = None
    warmup_arrays: dict[str, Any] | None = None
    if args.warmup_steps:
        warmup_collector = load_collector(args, batch_size=1)
        warmup_model = warmup_collector.policy.model
        warmup_state = warmup_model.initial_state(1, device=args.device)
        warmup_base_policy = warmup_collector.collector.policy
        warmup_collector.collector.policy = ForcedLearnerRootPolicy(
            warmup_base_policy,
            learner_players=warmup_collector.learner_players,
            root_actions=None,
        )
        warmup_arrays, warmup_state, *_history = warmup_collector.collect(
            args.warmup_steps, warmup_state
        )

    collector = load_collector(args, batch_size=args.action_samples)
    model = collector.policy.model
    state = model.initial_state(args.batch_size, device=args.device)
    base_policy = collector.collector.policy
    candidate_runtime = cast(SimpleGymRuntime, collector.collector.bridge.runtime)
    if warmup_collector is not None:
        assert warmup_state is not None
        source_observation = warmup_collector.collector.bridge.observe()
        candidate_runtime.fanout_from_(
            cast(SimpleGymRuntime, warmup_collector.collector.bridge.runtime)
        )
        source_history = warmup_collector.collector.bridge.adapter.history
        collector.collector.bridge.adapter.history = SimpleGymHistory(
            previous_actions=source_history.previous_actions.expand(
                args.batch_size, -1
            ).clone(),
            previous_rewards=source_history.previous_rewards.expand(
                args.batch_size, -1
            ).clone(),
            episode_starts=source_history.episode_starts.expand(
                args.batch_size, -1
            ).clone(),
        )
        collector.collector.bridge.needs_reset.copy_(
            warmup_collector.collector.bridge.needs_reset.expand(args.batch_size)
        )
        state = (
            warmup_state[0].expand(args.batch_size, -1).clone(),
            warmup_state[1].expand(args.batch_size, -1).clone(),
        )
        learner = int(warmup_collector.learner_players[0].item())
        collector.learner_players.fill_(learner)
        collector.policy.learner_players.fill_(learner)  # type: ignore[attr-defined]
        copied_observation = collector.collector.bridge.observe()
        for descriptor in fields(source_observation.actor):
            source_value = getattr(source_observation.actor, descriptor.name)
            copied_value = getattr(copied_observation.actor, descriptor.name)
            if not torch.equal(source_value.expand_as(copied_value), copied_value):
                raise RuntimeError(
                    f"cross-runtime actor field {descriptor.name} is not exact"
                )
        if source_observation.critic is None or copied_observation.critic is None:
            if source_observation.critic is not copied_observation.critic:
                raise RuntimeError("cross-runtime critic presence changed")
        else:
            for descriptor in fields(source_observation.critic):
                source_value = getattr(source_observation.critic, descriptor.name)
                copied_value = getattr(copied_observation.critic, descriptor.name)
                if not torch.equal(source_value.expand_as(copied_value), copied_value):
                    raise RuntimeError(
                        f"cross-runtime critic field {descriptor.name} is not exact"
                    )
        if not torch.equal(
            source_observation.legal_mask.expand_as(copied_observation.legal_mask),
            copied_observation.legal_mask,
        ):
            raise RuntimeError("cross-runtime legal mask is not exact")

    # Turn one real public state into an exact candidate-leading tensor batch.
    candidate_runtime.fanout_row_(0)
    history = collector.collector.bridge.adapter.history
    for tensor in (
        history.previous_actions,
        history.previous_rewards,
        history.episode_starts,
    ):
        tensor.copy_(tensor[:1].expand_as(tensor))
    state = (
        state[0][:1].expand_as(state[0]).clone(),
        state[1][:1].expand_as(state[1]).clone(),
    )
    collector.learner_players.fill_(0)
    collector.policy.learner_players.fill_(0)  # type: ignore[attr-defined]

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
    learner_state = collector.policy._state_from_prefixed_mapping(  # type: ignore[attr-defined]
        recurrent_inputs, "learner"
    )
    rows = torch.arange(args.batch_size, device=collector.learner_players.device)
    with torch.no_grad():
        parent_actions, *_parent_tail, parent_output = model.act(
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
    proposal_vocabulary = load_current_client_typed_vocabulary()
    proposal_builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=proposal_vocabulary.token_names,
        max_entities=model.config.max_entities,
        card_semantics_version=model.config.card_semantics_version,
        canonical_lane_globals=True,
    )
    proposal_by_strategy: dict[str, int] = {}
    for strategy_name in args.proposal_strategies:
        proposed = SimpleTensorStrategyOpponent(
            proposal_builder,
            strategy_name=strategy_name,
            device=torch.device(args.device),
        )(boundary)
        action = int(proposed[0, int(collector.learner_players[0].item())].item())
        if action not in set(legal.tolist()):
            raise RuntimeError(f"strategy proposal {strategy_name} is not legal")
        proposal_by_strategy[strategy_name] = action
    candidates = select_stratified_action_subset(
        legal,
        parent_output.joint_logits[0, 0].detach().cpu().numpy(),
        sample_limit=args.action_samples,
        no_op_action=model.num_actions - 2,
        parent_action=parent_action,
        proposal_actions=np.asarray(
            list(proposal_by_strategy.values()), dtype=np.int64
        ),
        random_fraction=args.random_candidate_fraction,
        rng=np.random.default_rng(args.seed),
    )
    root_actions = torch.as_tensor(
        candidates,
        dtype=torch.int64,
        device=collector.learner_players.device,
    )
    collector.collector.policy = ForcedLearnerRootPolicy(
        base_policy,
        learner_players=collector.learner_players,
        root_actions=root_actions,
        common_random_opponent=args.opponent_strategy == "random",
    )
    started = time.perf_counter()
    arrays, _branch_state = collect_counterfactual_branches(
        collector,
        (state[0].clone(), state[1].clone()),
        horizon_steps=args.horizon_steps,
        stop_when_all_terminal=args.stop_when_all_terminal,
        chunk_steps=args.collection_chunk_steps,
    )
    realized_horizon_steps = int(arrays["rewards"].shape[1])
    unpadded_dones = np.asarray(arrays["dones"], dtype=np.bool_)
    unpadded_winners = np.asarray(arrays["terminal_winners"], dtype=np.int64)
    learner_players = collector.learner_players.detach().cpu().numpy()
    terminal_outcomes = first_terminal_outcomes(
        unpadded_dones,
        unpadded_winners,
        learner_players,
    )
    if realized_horizon_steps < args.horizon_steps:
        padding = args.horizon_steps - realized_horizon_steps
        arrays["rewards"] = np.pad(
            arrays["rewards"],
            ((0, 0), (0, padding)),
            mode="constant",
            constant_values=0.0,
        )
        arrays["dones"] = np.pad(
            arrays["dones"],
            ((0, 0), (0, padding)),
            mode="constant",
            constant_values=False,
        )
    discounted, reward_return, bootstrap_return = truncated_n_step_returns(
        arrays["rewards"],
        arrays["dones"],
        arrays["bootstrap_values"],
        gamma=0.995,
    )
    done = arrays["dones"].any(axis=1)
    rows_out: list[dict[str, Any]] = []
    for index, action in enumerate(candidates.tolist()):
        rows_out.append(
            {
                "action": int(action),
                "discounted_return_mean": float(discounted[index]),
                "discounted_reward_return": float(reward_return[index]),
                "discounted_bootstrap_return": float(bootstrap_return[index]),
                "terminal": bool(done[index]),
                "terminal_outcome": int(terminal_outcomes[index]),
            }
        )
    rows_out.sort(
        key=lambda row: (
            int(row["terminal_outcome"]),
            float(row["discounted_reward_return"]),
            float(row["discounted_return_mean"]),
        ),
        reverse=True,
    )
    elapsed = time.perf_counter() - started
    payload = {
        "schema": "clasher.simple-counterfactual-teacher-probe.v4",
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "seed": args.seed,
        "batch_size": args.batch_size,
        "warmup_steps": args.warmup_steps,
        "horizon_steps": args.horizon_steps,
        "realized_horizon_steps": realized_horizon_steps,
        "stop_when_all_terminal": bool(args.stop_when_all_terminal),
        "collection_chunk_steps": args.collection_chunk_steps,
        "action_samples": len(rows_out),
        "candidate_selector": "hand-slot-spatial-stratified-v1",
        "strategy_proposals": proposal_by_strategy,
        "return_estimator": "truncated-n-step-bootstrap-v1",
        "label_authority": "terminal-outcome-then-discounted-reward-v1",
        "random_candidate_fraction": args.random_candidate_fraction,
        "warmup_batch_size": 1 if args.warmup_steps else args.action_samples,
        "opponent_randomness": (
            "common-quantile-v1"
            if args.opponent_strategy == "random"
            else "deterministic-strategy"
        ),
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
