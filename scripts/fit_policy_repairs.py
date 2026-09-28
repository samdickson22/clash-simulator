"""Fit outcome-verified sparse action repairs with behavior preservation."""

from __future__ import annotations

import argparse
import copy
import glob
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
import torch.nn.functional as F

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import LoadedPolicy, _policy_action, load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    sequence_chunks,
)
from clasher.rl.model import ClasherPolicy, PrototypeRepairAdapter
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.structured_obs import StructuredObservation
from clasher.rl.train_recurrent import _stack_step_inputs, maybe_silence_stdio


@dataclass
class DecisionExample:
    observation: StructuredObservation
    mask: np.ndarray
    previous_action: int
    previous_reward: float
    episode_start: bool
    state: tuple[torch.Tensor, torch.Tensor]
    parent_logits: torch.Tensor
    parent_action: int
    target_action: int
    repair_features: torch.Tensor


def _matched_files(patterns: str | list[str]) -> list[str]:
    if isinstance(patterns, str):
        patterns = [patterns]
    return sorted({filename for pattern in patterns for filename in glob.glob(pattern)})


def _selected_repairs(patterns: str | list[str]) -> list[dict[str, Any]]:
    best: dict[tuple[int, int], tuple[tuple[int, int, int], dict[str, Any]]] = {}
    for filename in _matched_files(patterns):
        payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        if "winning_repairs" not in payload:
            continue
        key = (int(payload["matchup_seed"]), int(payload["candidate_player"]))
        exact_replay = "verified" in payload
        for repair in payload["winning_repairs"]:
            score = (
                int(exact_replay),
                int(repair["candidate_crowns"])
                - int(repair["opponent_crowns"]),
                -int(repair["end_tick"]),
            )
            if key not in best or score > best[key][0]:
                best[key] = (
                    score,
                    {
                        **repair,
                        "matchup_seed": key[0],
                        "candidate_player": key[1],
                        "opponent_checkpoint": payload.get("opponent_checkpoint"),
                        "opponent_strategy": payload.get("opponent_strategy"),
                    },
                )
    return [item[1] for _, item in sorted(best.items())]


def _selected_repair_plans(patterns: str | list[str]) -> list[dict[str, Any]]:
    plans = []
    for filename in _matched_files(patterns):
        payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        if payload.get("verification") != "full-replay-plan":
            continue
        if not payload.get("repair_plan"):
            continue
        plans.append(payload)
    return sorted(
        plans,
        key=lambda item: (int(item["matchup_seed"]), int(item["candidate_player"])),
    )


@torch.no_grad()
def _decision(
    policy: LoadedPolicy,
    env: SelfPlayBattleEnv,
    player_id: int,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    device: torch.device,
    target_action: int | None = None,
) -> tuple[DecisionExample, tuple[torch.Tensor, torch.Tensor]]:
    assert env.battle is not None
    observation = policy.builder.build(env.battle, player_id)
    mask = env.get_action_mask(player_id)
    inputs = _stack_step_inputs(
        [observation],
        mask[None, :],
        np.asarray([previous_action], dtype=np.int64),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start], dtype=np.bool_),
        device,
    )
    action, _, _, next_state, output = policy.model.act(
        inputs,
        state,
        deterministic=True,
    )
    parent_action = int(action[0, 0].item())
    if output.repair_features is None:
        raise RuntimeError("policy did not expose repair features")
    example = DecisionExample(
        observation=observation,
        mask=mask.copy(),
        previous_action=previous_action,
        previous_reward=previous_reward,
        episode_start=episode_start,
        state=(state[0].detach().cpu().clone(), state[1].detach().cpu().clone()),
        parent_logits=output.joint_logits[0, 0].detach().cpu().clone(),
        parent_action=parent_action,
        target_action=parent_action if target_action is None else target_action,
        repair_features=output.repair_features[0, 0].detach().cpu().clone(),
    )
    return example, next_state


def _new_env(decks_path: Path, seed: int) -> SelfPlayBattleEnv:
    return SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path=decks_path,
        seed=seed,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path="off",
        reward_profile=DEFENSE_V2,
    )


def _repair_example(
    policy: LoadedPolicy,
    decks_path: Path,
    repair: dict[str, Any],
    *,
    device: torch.device,
    quiet_engine: bool,
) -> DecisionExample:
    matchup_seed = int(repair["matchup_seed"])
    candidate_player = int(repair["candidate_player"])
    other_player = 1 - candidate_player
    target_tick = int(repair["tick"])
    target_action = int(repair["alternative_action"])
    expected_parent_action = int(repair["baseline_action"])
    env = _new_env(decks_path, matchup_seed)
    with maybe_silence_stdio(quiet_engine):
        env.reset(seed=matchup_seed)
    opponent_rng = np.random.default_rng(matchup_seed + 91_117)
    torch.manual_seed(matchup_seed + 271_828)
    opponent_checkpoint = repair.get("opponent_checkpoint")
    opponent = (
        None
        if opponent_checkpoint is None
        else load_policy_checkpoint(
            resolve_path(str(opponent_checkpoint), must_exist=True),
            device=device,
            decks_path=decks_path,
        )
    )
    opponent_strategy_name = repair.get("opponent_strategy")
    opponent_strategy = (
        None
        if opponent_strategy_name is None
        else StrategyBot(str(opponent_strategy_name))
    )
    state = policy.model.initial_state(1, device=device)
    opponent_state = (
        None if opponent is None else opponent.model.initial_state(1, device=device)
    )
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    opponent_previous_action = env.action_space.no_op_action
    opponent_previous_reward = 0.0
    episode_start = True

    while True:
        assert env.battle is not None
        example, next_state = _decision(
            policy,
            env,
            candidate_player,
            state=state,
            previous_action=previous_action,
            previous_reward=previous_reward,
            episode_start=episode_start,
            device=device,
            target_action=target_action if env.battle.tick == target_tick else None,
        )
        if env.battle.tick == target_tick:
            if example.parent_action != expected_parent_action:
                raise RuntimeError(
                    f"repair replay diverged at seed={matchup_seed} tick={target_tick}: "
                    f"expected action {expected_parent_action}, got {example.parent_action}"
                )
            if not example.mask[target_action]:
                raise RuntimeError(
                    f"repair target {target_action} is illegal at seed={matchup_seed} "
                    f"tick={target_tick}"
                )
            return example
        if env.battle.tick > target_tick:
            raise RuntimeError(
                f"repair tick {target_tick} was skipped at seed={matchup_seed}"
            )
        if opponent is not None:
            assert opponent_state is not None
            other_action, next_opponent_state, other_mask = _policy_action(
                opponent,
                env,
                other_player,
                state=opponent_state,
                previous_action=opponent_previous_action,
                previous_reward=opponent_previous_reward,
                episode_start=episode_start,
                deterministic=True,
                device=device,
            )
        else:
            other_mask = env.get_action_mask(other_player)
            if opponent_strategy is not None:
                other_action = opponent_strategy.select_action(
                    env,
                    other_player,
                    action_mask=other_mask,
                )
            else:
                legal = np.flatnonzero(other_mask)
                other_action = (
                    int(opponent_rng.choice(legal))
                    if legal.size
                    else env.action_space.no_op_action
                )
            next_opponent_state = None
        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(
                {
                    candidate_player: example.parent_action,
                    other_player: other_action,
                },
                pre_action_masks={
                    candidate_player: example.mask,
                    other_player: other_mask,
                },
            )
        if done:
            raise RuntimeError(
                f"game ended before repair tick {target_tick} at seed={matchup_seed}"
            )
        state = next_state
        previous_action = example.parent_action
        previous_reward = float(rewards[candidate_player])
        opponent_state = next_opponent_state
        opponent_previous_action = other_action
        opponent_previous_reward = float(rewards[other_player])
        episode_start = False


def _repair_plan_examples(
    policy: LoadedPolicy,
    decks_path: Path,
    payload: dict[str, Any],
    *,
    device: torch.device,
    quiet_engine: bool,
) -> list[DecisionExample]:
    matchup_seed = int(payload["matchup_seed"])
    candidate_player = int(payload["candidate_player"])
    other_player = 1 - candidate_player
    plan = {
        int(item["tick"]): item
        for item in payload["repair_plan"]
    }
    env = _new_env(decks_path, matchup_seed)
    with maybe_silence_stdio(quiet_engine):
        env.reset(seed=matchup_seed)
    opponent_rng = np.random.default_rng(matchup_seed + 91_117)
    torch.manual_seed(matchup_seed + 271_828)
    state = policy.model.initial_state(1, device=device)
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    examples = []
    done = False
    while not done:
        assert env.battle is not None
        repair = plan.get(env.battle.tick)
        target_action = (
            int(repair["alternative_action"])
            if repair is not None
            else None
        )
        example, next_state = _decision(
            policy,
            env,
            candidate_player,
            state=state,
            previous_action=previous_action,
            previous_reward=previous_reward,
            episode_start=episode_start,
            device=device,
            target_action=target_action,
        )
        candidate_action = example.parent_action
        if repair is not None:
            expected_parent_action = int(repair["baseline_action"])
            if candidate_action != expected_parent_action:
                raise RuntimeError(
                    f"repair plan diverged at seed={matchup_seed} tick={env.battle.tick}: "
                    f"expected action {expected_parent_action}, got {candidate_action}"
                )
            assert target_action is not None
            if not example.mask[target_action]:
                raise RuntimeError(
                    f"repair plan target {target_action} is illegal at "
                    f"seed={matchup_seed} tick={env.battle.tick}"
                )
            examples.append(example)
            candidate_action = target_action
        other_mask = env.get_action_mask(other_player)
        legal = np.flatnonzero(other_mask)
        other_action = (
            int(opponent_rng.choice(legal))
            if legal.size
            else env.action_space.no_op_action
        )
        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(
                {
                    candidate_player: candidate_action,
                    other_player: other_action,
                },
                pre_action_masks={
                    candidate_player: example.mask,
                    other_player: other_mask,
                },
            )
        state = next_state
        previous_action = candidate_action
        previous_reward = float(rewards[candidate_player])
        episode_start = False

    if len(examples) != len(plan):
        raise RuntimeError(
            f"repair plan applied {len(examples)} of {len(plan)} actions for "
            f"seed={matchup_seed}"
        )
    assert env.battle is not None
    expected = payload["verified_result"]
    outcome = (
        "draw"
        if env.battle.winner is None
        else ("win" if env.battle.winner == candidate_player else "loss")
    )
    actual = {
        "outcome": outcome,
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
    }
    if actual != expected:
        raise RuntimeError(
            f"repair plan terminal mismatch for seed={matchup_seed}: "
            f"expected {expected}, got {actual}"
        )
    return examples


def _preservation_examples(
    policy: LoadedPolicy,
    decks_path: Path,
    *,
    seeds: list[int],
    games_per_seed: int,
    samples: int,
    device: torch.device,
    quiet_engine: bool,
    reservoir_seed: int,
) -> list[DecisionExample]:
    reservoir: list[DecisionExample] = []
    seen = 0
    reservoir_rng = np.random.default_rng(reservoir_seed)
    for evaluation_seed in seeds:
        for game in range(games_per_seed):
            matchup_seed = evaluation_seed + (game // 2) * 1009
            candidate_player = game % 2
            other_player = 1 - candidate_player
            env = _new_env(decks_path, matchup_seed)
            with maybe_silence_stdio(quiet_engine):
                env.reset(seed=matchup_seed)
            opponent_rng = np.random.default_rng(matchup_seed + 91_117)
            torch.manual_seed(matchup_seed + 271_828)
            state = policy.model.initial_state(1, device=device)
            previous_action = env.action_space.no_op_action
            previous_reward = 0.0
            episode_start = True
            done = False
            while not done:
                example, next_state = _decision(
                    policy,
                    env,
                    candidate_player,
                    state=state,
                    previous_action=previous_action,
                    previous_reward=previous_reward,
                    episode_start=episode_start,
                    device=device,
                )
                seen += 1
                if len(reservoir) < samples:
                    reservoir.append(example)
                else:
                    replacement = int(reservoir_rng.integers(0, seen))
                    if replacement < samples:
                        reservoir[replacement] = example
                other_mask = env.get_action_mask(other_player)
                legal = np.flatnonzero(other_mask)
                other_action = (
                    int(opponent_rng.choice(legal))
                    if legal.size
                    else env.action_space.no_op_action
                )
                with maybe_silence_stdio(quiet_engine):
                    rewards, done, _ = env.step(
                        {
                            candidate_player: example.parent_action,
                            other_player: other_action,
                        },
                        pre_action_masks={
                            candidate_player: example.mask,
                            other_player: other_mask,
                        },
                    )
                state = next_state
                previous_action = example.parent_action
                previous_reward = float(rewards[candidate_player])
                episode_start = False
    return reservoir


def _batch(
    examples: list[DecisionExample],
    device: torch.device,
) -> tuple[Any, tuple[torch.Tensor, torch.Tensor], torch.Tensor, torch.Tensor]:
    inputs = _stack_step_inputs(
        [example.observation for example in examples],
        np.stack([example.mask for example in examples]),
        np.asarray([example.previous_action for example in examples], dtype=np.int64),
        np.asarray([example.previous_reward for example in examples], dtype=np.float32),
        np.asarray([example.episode_start for example in examples], dtype=np.bool_),
        device,
    )
    state = (
        torch.cat([example.state[0] for example in examples], dim=0).to(device),
        torch.cat([example.state[1] for example in examples], dim=0).to(device),
    )
    parent_logits = torch.stack([example.parent_logits for example in examples]).to(
        device
    )
    targets = torch.as_tensor(
        [example.target_action for example in examples],
        dtype=torch.long,
        device=device,
    )
    return inputs, state, parent_logits, targets


def _safe_kl(current_logits: torch.Tensor, parent_logits: torch.Tensor) -> torch.Tensor:
    parent_log_probs = F.log_softmax(parent_logits, dim=-1)
    parent_probs = parent_log_probs.exp()
    current_log_probs = F.log_softmax(current_logits, dim=-1)
    terms = torch.where(
        parent_probs > 0.0,
        parent_probs * (parent_log_probs - current_log_probs),
        torch.zeros_like(parent_probs),
    )
    return terms.sum(dim=-1).mean()


def _factorized_repair_loss(
    output: Any,
    action_mask: torch.Tensor,
    targets: torch.Tensor,
    *,
    objective: str,
    margin: float,
) -> torch.Tensor:
    targets = targets.reshape(-1)
    action_mask = action_mask.reshape(-1, action_mask.shape[-1])
    type_logits = output.action_type_logits.reshape(
        -1,
        output.action_type_logits.shape[-1],
    )
    all_location_logits = output.location_logits.reshape(
        -1,
        NUM_HAND_SLOTS,
        NUM_TILES,
    )
    batch_size = targets.shape[0]
    if action_mask.shape[0] != batch_size or type_logits.shape[0] != batch_size:
        raise ValueError("action targets and policy outputs must have matching shapes")
    placement_mask = action_mask[:, : NUM_HAND_SLOTS * NUM_TILES].reshape(
        batch_size,
        NUM_HAND_SLOTS,
        NUM_TILES,
    )
    type_mask = torch.cat(
        [
            placement_mask.any(dim=-1),
            action_mask[:, NUM_HAND_SLOTS * NUM_TILES :],
        ],
        dim=-1,
    )
    target_types = torch.where(
        targets < NUM_HAND_SLOTS * NUM_TILES,
        torch.div(targets, NUM_TILES, rounding_mode="floor"),
        NUM_HAND_SLOTS + targets - NUM_HAND_SLOTS * NUM_TILES,
    )
    type_logits = type_logits.masked_fill(~type_mask, -torch.inf)
    if objective == "margin":
        target_type_scores = type_logits.gather(1, target_types[:, None]).squeeze(1)
        competing_type_logits = type_logits.clone()
        competing_type_logits.scatter_(1, target_types[:, None], -torch.inf)
        type_loss = F.relu(
            competing_type_logits.max(dim=1).values - target_type_scores + margin
        ).mean()
    else:
        type_loss = F.cross_entropy(type_logits, target_types)

    placement_rows = torch.nonzero(
        targets < NUM_HAND_SLOTS * NUM_TILES,
        as_tuple=False,
    ).flatten()
    if placement_rows.numel() == 0:
        return type_loss
    placement_types = target_types[placement_rows]
    location_targets = targets[placement_rows] % NUM_TILES
    location_logits = all_location_logits[
        placement_rows,
        placement_types,
    ]
    location_legal = placement_mask[placement_rows, placement_types]
    location_logits = location_logits.masked_fill(~location_legal, -torch.inf)
    if objective == "margin":
        target_location_scores = location_logits.gather(
            1,
            location_targets[:, None],
        ).squeeze(1)
        competing_location_logits = location_logits.clone()
        competing_location_logits.scatter_(
            1,
            location_targets[:, None],
            -torch.inf,
        )
        location_loss = F.relu(
            competing_location_logits.max(dim=1).values
            - target_location_scores
            + margin
        ).mean()
    else:
        location_loss = F.cross_entropy(location_logits, location_targets)
    return type_loss + location_loss


def _repair_metrics(
    policy: LoadedPolicy,
    repairs: list[DecisionExample],
    preservation: list[DecisionExample],
    device: torch.device,
    *,
    batch_size: int = 64,
) -> dict[str, float]:
    def action_agreement(examples: list[DecisionExample]) -> float:
        matches = 0
        total = 0
        for start in range(0, len(examples), batch_size):
            batch = examples[start : start + batch_size]
            inputs, state, _, targets = _batch(batch, device)
            actions = policy.model.act(
                inputs,
                state,
                deterministic=True,
            )[0][:, 0]
            matches += int((actions == targets).sum().cpu())
            total += len(batch)
        return matches / total

    policy.model.eval()
    with torch.no_grad():
        repair_accuracy = action_agreement(repairs)
        preservation_action_agreement = action_agreement(preservation)
    return {
        "repair_accuracy": repair_accuracy,
        "preservation_action_agreement": preservation_action_agreement,
    }


def main() -> None:
    args = parse_args()
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint_path = resolve_path(args.checkpoint, must_exist=True)
    policy = load_policy_checkpoint(
        checkpoint_path,
        device=device,
        decks_path=decks_path,
    )
    single_repairs_payload = _selected_repairs(args.repairs_glob)
    repair_plans_payload = _selected_repair_plans(args.repairs_glob)
    plan_step_count = sum(len(plan["repair_plan"]) for plan in repair_plans_payload)
    repair_count = len(single_repairs_payload) + plan_step_count
    if repair_count == 0:
        raise RuntimeError("no winning repairs found")
    stage_mode = args.repair_stage_size > 0
    stage_prototype_mode = (
        stage_mode and args.repair_stage_prototype_threshold is not None
    )
    if not stage_mode and args.repair_stage_prototype_threshold is not None:
        raise ValueError(
            "--repair-stage-prototype-threshold requires --repair-stage-size"
        )
    mode_count = sum(
        (
            args.repair_adapter_size > 0,
            args.repair_prototype_threshold is not None,
            stage_mode,
        )
    )
    if mode_count > 1:
        raise ValueError("choose only one repair adapter mode")

    existing_prototype_count = policy.model.config.repair_prototype_count
    existing_prototypes: torch.Tensor | None = None
    existing_prototype_deltas: torch.Tensor | None = None
    if policy.model.prototype_repair_adapter is not None:
        existing_prototypes = (
            policy.model.prototype_repair_adapter.prototypes.detach().clone()
        )
        existing_prototype_deltas = (
            policy.model.prototype_repair_adapter.deltas.detach().clone()
        )
    active_prototype_adapter = None
    active_existing_prototype_count = existing_prototype_count
    stage_index: int | None = None
    if stage_mode:
        stage_index = len(policy.model.config.repair_stage_sizes)
        padded_counts = policy.model.config.repair_stage_prototype_counts + (0,) * (
            len(policy.model.config.repair_stage_sizes)
            - len(policy.model.config.repair_stage_prototype_counts)
        )
        padded_thresholds = (
            policy.model.config.repair_stage_prototype_thresholds
            + (policy.model.config.repair_stage_prototype_threshold,) * (
                len(policy.model.config.repair_stage_sizes)
                - len(policy.model.config.repair_stage_prototype_thresholds)
            )
        )
        expanded_config = replace(
            policy.model.config,
            repair_stage_sizes=(
                *policy.model.config.repair_stage_sizes,
                args.repair_stage_size,
            ),
            repair_stage_prototype_counts=(
                *padded_counts,
                repair_count if stage_prototype_mode else 0,
            ),
            repair_stage_prototype_threshold=(
                args.repair_stage_prototype_threshold
                if stage_prototype_mode
                else policy.model.config.repair_stage_prototype_threshold
            ),
            repair_stage_prototype_thresholds=(
                *padded_thresholds,
                args.repair_stage_prototype_threshold
                if stage_prototype_mode
                else policy.model.config.repair_stage_prototype_threshold,
            ),
            repair_stage_yield_to_prior=(
                *policy.model.config.repair_stage_yield_to_prior,
                *((False,) * (
                    len(policy.model.config.repair_stage_sizes)
                    - len(policy.model.config.repair_stage_yield_to_prior)
                )),
                args.repair_stage_yield_to_prior,
            ),
            repair_stage_prototype_guard_counts=(
                *policy.model.config.repair_stage_prototype_guard_counts,
                *((0,) * (
                    len(policy.model.config.repair_stage_sizes)
                    - len(policy.model.config.repair_stage_prototype_guard_counts)
                )),
                0,
            ),
            repair_stage_prototype_guard_thresholds=(
                *policy.model.config.repair_stage_prototype_guard_thresholds,
                *((policy.model.config.repair_stage_prototype_threshold,) * (
                    len(policy.model.config.repair_stage_sizes)
                    - len(
                        policy.model.config.repair_stage_prototype_guard_thresholds
                    )
                )),
                policy.model.config.repair_stage_prototype_threshold,
            ),
            repair_stage_prototype_hard_guards=(
                *policy.model.config.repair_stage_prototype_hard_guards,
                *((False,) * (
                    len(policy.model.config.repair_stage_sizes)
                    - len(policy.model.config.repair_stage_prototype_hard_guards)
                )),
                False,
            ),
        )
        expanded_model = ClasherPolicy(
            expanded_config,
            policy.builder.card_stat_features,
        ).to(device)
        incompatible = expanded_model.load_state_dict(
            policy.model.state_dict(),
            strict=False,
        )
        allowed_prefixes: tuple[str, ...] = (f"repair_stages.{stage_index}.",)
        if stage_prototype_mode:
            allowed_prefixes = (
                *allowed_prefixes,
                f"repair_stage_prototype_adapters.{stage_index}.",
            )
        if incompatible.unexpected_keys or any(
            not name.startswith(allowed_prefixes)
            for name in incompatible.missing_keys
        ):
            raise RuntimeError(f"unexpected repair-stage mismatch: {incompatible}")
        expanded_model.eval()
        policy.model = expanded_model
        if stage_prototype_mode:
            active_prototype_adapter = cast(
                PrototypeRepairAdapter,
                policy.model.repair_stage_prototype_adapters[str(stage_index)],
            )
            active_existing_prototype_count = 0
    elif args.repair_adapter_size > 0 or args.repair_prototype_threshold is not None:
        if policy.model.config.repair_adapter_size != 0:
            raise ValueError("source checkpoint already contains a dense repair adapter")
        if args.repair_adapter_size > 0 and existing_prototype_count != 0:
            raise ValueError("cannot add a dense adapter through the repair fitter")
        if (
            existing_prototype_count > 0
            and args.repair_prototype_threshold is not None
            and args.repair_prototype_threshold
            != policy.model.config.repair_prototype_threshold
        ):
            raise ValueError("appended prototypes must retain the source threshold")
        expanded_config = replace(
            policy.model.config,
            repair_adapter_size=args.repair_adapter_size,
            repair_prototype_count=(
                existing_prototype_count + repair_count
                if args.repair_prototype_threshold is not None
                else 0
            ),
            repair_prototype_threshold=(
                args.repair_prototype_threshold
                if args.repair_prototype_threshold is not None
                else policy.model.config.repair_prototype_threshold
            ),
        )
        expanded_model = ClasherPolicy(
            expanded_config,
            policy.builder.card_stat_features,
        ).to(device)
        source_state = dict(policy.model.state_dict())
        if existing_prototype_count:
            source_state.pop("prototype_repair_adapter.prototypes")
            source_state.pop("prototype_repair_adapter.deltas")
        incompatible = expanded_model.load_state_dict(
            source_state,
            strict=False,
        )
        allowed_prefix = (
            "prototype_repair_adapter."
            if args.repair_prototype_threshold is not None
            else "repair_adapter."
        )
        if incompatible.unexpected_keys or any(
            not name.startswith(allowed_prefix) for name in incompatible.missing_keys
        ):
            raise RuntimeError(f"unexpected adapter expansion mismatch: {incompatible}")
        if existing_prototype_count:
            assert expanded_model.prototype_repair_adapter is not None
            assert existing_prototypes is not None
            assert existing_prototype_deltas is not None
            with torch.no_grad():
                expanded_model.prototype_repair_adapter.prototypes[
                    :existing_prototype_count
                ].copy_(existing_prototypes)
                expanded_model.prototype_repair_adapter.deltas[
                    :existing_prototype_count
                ].copy_(existing_prototype_deltas)
        expanded_model.eval()
        policy.model = expanded_model
        active_prototype_adapter = policy.model.prototype_repair_adapter
    elif policy.model.prototype_repair_adapter is not None:
        active_prototype_adapter = policy.model.prototype_repair_adapter
    parent_model = copy.deepcopy(policy.model).eval()
    for parameter in parent_model.parameters():
        parameter.requires_grad = False
    repairs = [
        _repair_example(
            policy,
            decks_path,
            repair,
            device=device,
            quiet_engine=args.quiet_engine,
        )
        for repair in single_repairs_payload
    ]
    repairs_payload = list(single_repairs_payload)
    for repair_plan in repair_plans_payload:
        repairs.extend(
            _repair_plan_examples(
                policy,
                decks_path,
                repair_plan,
                device=device,
                quiet_engine=args.quiet_engine,
            )
        )
        repairs_payload.extend(
            {
                **step,
                "matchup_seed": int(repair_plan["matchup_seed"]),
                "candidate_player": int(repair_plan["candidate_player"]),
                "verification": "full-replay-plan",
            }
            for step in repair_plan["repair_plan"]
        )
    trainable_prefixes: tuple[str, ...]
    if active_prototype_adapter is not None:
        new_prototypes = torch.stack(
            [repair.repair_features for repair in repairs]
        ).to(device)
        if active_existing_prototype_count:
            assert existing_prototypes is not None
            prototype_values = torch.cat(
                [existing_prototypes, new_prototypes], dim=0
            )
        else:
            prototype_values = new_prototypes
        active_prototype_adapter.set_prototypes(prototype_values)
    preservation = _preservation_examples(
        policy,
        decks_path,
        seeds=args.preservation_seed,
        games_per_seed=args.preservation_games,
        samples=args.preservation_samples,
        device=device,
        quiet_engine=args.quiet_engine,
        reservoir_seed=args.seed,
    )
    prototype_diagnostics: dict[str, float] | None = None
    if active_prototype_adapter is not None:
        adapter = active_prototype_adapter
        with torch.no_grad():
            prototype_weights = adapter.activation_weights(adapter.prototypes)
            preservation_weights = adapter.activation_weights(
                torch.stack([example.repair_features for example in preservation]).to(
                    device
                )
            )
        off_diagonal = ~torch.eye(
            adapter.prototypes.shape[0],
            dtype=torch.bool,
            device=device,
        )
        prototype_diagnostics = {
            "prototype_self_weight_min": float(
                prototype_weights.diagonal().min().cpu()
            ),
            "prototype_cross_weight_max": float(
                prototype_weights.masked_select(off_diagonal).max().cpu()
            ),
            "preservation_active_fraction": float(
                (preservation_weights.max(dim=-1).values > 0).float().mean().cpu()
            ),
            "preservation_max_weight": float(preservation_weights.max().cpu()),
        }
        print(json.dumps(prototype_diagnostics, sort_keys=True), flush=True)
    preservation_arrays: dict[str, np.ndarray] | None = None
    preservation_chunks: np.ndarray | None = None
    if args.preservation_corpus is not None:
        _, preservation_arrays = load_corpus(
            resolve_path(args.preservation_corpus, must_exist=True)
        )
        preservation_chunks = sequence_chunks(
            preservation_arrays["episode_ids"],
            np.arange(len(preservation_arrays["episode_ids"]), dtype=np.int64),
            sequence_length=args.preservation_sequence_length,
        )
    initial_metrics = _repair_metrics(policy, repairs, preservation, device)

    if active_prototype_adapter is not None:
        if stage_mode:
            assert stage_index is not None
            trainable_prefixes = (
                f"repair_stage_prototype_adapters.{stage_index}.deltas",
            )
        else:
            trainable_prefixes = ("prototype_repair_adapter.deltas",)
        if active_existing_prototype_count:
            def freeze_existing_prototype_rows(gradient: torch.Tensor) -> torch.Tensor:
                gradient = gradient.clone()
                gradient[:active_existing_prototype_count].zero_()
                return gradient

            active_prototype_adapter.deltas.register_hook(freeze_existing_prototype_rows)
    elif stage_mode:
        assert stage_index is not None
        trainable_prefixes = (f"repair_stages.{stage_index}.",)
    elif policy.model.repair_adapter is not None:
        trainable_prefixes = ("repair_adapter.",)
    else:
        trainable_prefixes = (
            "action_type_head.",
            "card_query.",
            "tile_key.",
            "location_bias.",
        )
    trainable = []
    anchors: dict[str, torch.Tensor] = {}
    for name, parameter in policy.model.named_parameters():
        parameter.requires_grad = name.startswith(trainable_prefixes)
        if parameter.requires_grad:
            trainable.append(parameter)
            anchors[name] = parameter.detach().clone()
    optimizer = torch.optim.AdamW(trainable, lr=args.learning_rate, weight_decay=0.0)
    rng = np.random.default_rng(args.seed)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_steps = set(args.save_step)
    history = []

    policy.model.train()
    for step in range(1, args.steps + 1):
        repair_inputs, repair_state, _, repair_targets = _batch(repairs, device)
        repair_output = policy.model(repair_inputs, repair_state)
        if preservation_chunks is not None and preservation_arrays is not None:
            sequence_batch_size = max(
                1,
                args.preservation_batch_size // args.preservation_sequence_length,
            )
            chunk_indices = rng.choice(
                len(preservation_chunks),
                size=min(sequence_batch_size, len(preservation_chunks)),
                replace=False,
            )
            preserve_inputs = _sequence_batch_inputs(
                preservation_arrays,
                preservation_chunks[chunk_indices],
                device,
            )
            with torch.no_grad():
                preservation_targets, _, _, _, parent_output = parent_model.act(
                    preserve_inputs,
                    deterministic=True,
                )
                parent_logits = parent_output.joint_logits
            current_preserve_output = policy.model(preserve_inputs)
            current_preserve_logits = current_preserve_output.joint_logits
            live_indices = rng.choice(
                len(preservation),
                size=min(args.preservation_batch_size, len(preservation)),
                replace=False,
            )
            live_batch = [preservation[int(index)] for index in live_indices]
            (
                live_inputs,
                live_state,
                live_parent_logits,
                live_targets,
            ) = _batch(live_batch, device)
            current_live_output = policy.model(live_inputs, live_state)
            current_live_logits = current_live_output.joint_logits[:, 0]
        else:
            preserve_indices = rng.choice(
                len(preservation),
                size=min(args.preservation_batch_size, len(preservation)),
                replace=False,
            )
            preserve_batch = [preservation[int(index)] for index in preserve_indices]
            preserve_inputs, preserve_state, parent_logits, preservation_targets = _batch(
                preserve_batch,
                device,
            )
            current_preserve_output = policy.model(
                preserve_inputs,
                preserve_state,
            )
            current_preserve_logits = current_preserve_output.joint_logits[:, 0]
            live_inputs = None
            live_parent_logits = None
            live_targets = None
            current_live_output = None
            current_live_logits = None
        repair_loss = _factorized_repair_loss(
            repair_output,
            repair_inputs.action_mask,
            repair_targets,
            objective=args.repair_objective,
            margin=args.repair_margin,
        )
        preservation_kl = _safe_kl(current_preserve_logits, parent_logits)
        preservation_margin = _factorized_repair_loss(
            current_preserve_output,
            preserve_inputs.action_mask,
            preservation_targets,
            objective="margin",
            margin=args.preservation_action_margin,
        )
        if (
            live_inputs is not None
            and live_parent_logits is not None
            and live_targets is not None
            and current_live_output is not None
            and current_live_logits is not None
        ):
            live_preservation_kl = _safe_kl(
                current_live_logits,
                live_parent_logits,
            )
            live_preservation_margin = _factorized_repair_loss(
                current_live_output,
                live_inputs.action_mask,
                live_targets,
                objective="margin",
                margin=args.preservation_action_margin,
            )
        else:
            live_preservation_kl = torch.zeros((), device=device)
            live_preservation_margin = torch.zeros((), device=device)
        l2_sum = torch.zeros((), device=device)
        l2_count = 0
        for name, parameter in policy.model.named_parameters():
            if name in anchors:
                l2_sum = l2_sum + (parameter - anchors[name]).square().sum()
                l2_count += parameter.numel()
        parameter_l2 = l2_sum / max(1, l2_count)
        loss = (
            repair_loss
            + args.preservation_kl_coef * preservation_kl
            + args.preservation_action_margin_coef * preservation_margin
            + args.live_preservation_kl_coef * live_preservation_kl
            + args.live_preservation_action_margin_coef
            * live_preservation_margin
            + args.parameter_l2_coef * parameter_l2
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, args.max_grad_norm)
        optimizer.step()

        if step == 1 or step % args.log_every == 0 or step in save_steps:
            metrics = _repair_metrics(policy, repairs, preservation, device)
            row = {
                "step": step,
                "loss": float(loss.detach()),
                "repair_loss": float(repair_loss.detach()),
                "preservation_kl": float(preservation_kl.detach()),
                "preservation_action_margin": float(preservation_margin.detach()),
                "live_preservation_kl": float(live_preservation_kl.detach()),
                "live_preservation_action_margin": float(
                    live_preservation_margin.detach()
                ),
                "parameter_l2_mean": float(parameter_l2.detach()),
                **metrics,
            }
            history.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
        if step in save_steps or step == args.steps:
            payload = copy.deepcopy(policy.checkpoint)
            # Repair fitting changes the model topology and uses its own optimizer.
            # A source optimizer state is therefore stale and unsafe to resume.
            payload.pop("optimizer_state_dict", None)
            payload["model_state_dict"] = {
                name: value.detach().cpu()
                for name, value in policy.model.state_dict().items()
            }
            payload["model_config"] = policy.model.config.to_dict()
            payload["args"] = {
                **dict(payload.get("args", {})),
                "initialization": "outcome_verified_sparse_repairs",
                "repair_source_checkpoint": str(checkpoint_path),
                "repair_count": len(repairs),
                "repair_fit_step": step,
                "repair_adapter_size": args.repair_adapter_size,
                "repair_prototype_threshold": args.repair_prototype_threshold,
                "repair_stage_size": args.repair_stage_size,
                "repair_stage_prototype_threshold": (
                    args.repair_stage_prototype_threshold
                ),
                "repair_stage_yield_to_prior": args.repair_stage_yield_to_prior,
                "preservation_samples": len(preservation),
                "preservation_corpus": args.preservation_corpus,
                "preservation_kl_coef": args.preservation_kl_coef,
                "preservation_action_margin_coef": args.preservation_action_margin_coef,
                "preservation_action_margin": args.preservation_action_margin,
                "live_preservation_kl_coef": args.live_preservation_kl_coef,
                "live_preservation_action_margin_coef": (
                    args.live_preservation_action_margin_coef
                ),
                "parameter_l2_coef": args.parameter_l2_coef,
            }
            payload["repair_fit"] = {
                "schema_version": 1,
                "step": step,
                "repairs": repairs_payload,
                "initial_metrics": initial_metrics,
                "history": history,
            }
            torch.save(payload, output_dir / f"policy_v2_repair_step_{step:04d}.pt")

    manifest = {
        "schema_version": 1,
        "checkpoint": str(checkpoint_path),
        "repair_count": len(repairs),
        "preservation_samples": len(preservation),
        "preservation_corpus": args.preservation_corpus,
        "prototype_diagnostics": prototype_diagnostics,
        "initial_metrics": initial_metrics,
        "history": history,
    }
    manifest_path = output_dir / "repair_fit_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--repairs-glob", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--seed", type=int, default=8801)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--save-step", type=int, action="append", default=[])
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--repair-adapter-size", type=int, default=0)
    parser.add_argument("--repair-prototype-threshold", type=float, default=None)
    parser.add_argument("--repair-stage-size", type=int, default=0)
    parser.add_argument(
        "--repair-stage-prototype-threshold",
        type=float,
        default=None,
    )
    parser.add_argument("--repair-stage-yield-to-prior", action="store_true")
    parser.add_argument(
        "--repair-objective",
        choices=["cross-entropy", "margin"],
        default="margin",
    )
    parser.add_argument("--repair-margin", type=float, default=0.05)
    parser.add_argument("--preservation-kl-coef", type=float, default=4.0)
    parser.add_argument("--preservation-action-margin-coef", type=float, default=0.0)
    parser.add_argument("--live-preservation-kl-coef", type=float, default=0.0)
    parser.add_argument(
        "--live-preservation-action-margin-coef",
        type=float,
        default=0.0,
    )
    parser.add_argument("--preservation-action-margin", type=float, default=0.02)
    parser.add_argument("--parameter-l2-coef", type=float, default=1.0)
    parser.add_argument("--preservation-samples", type=int, default=512)
    parser.add_argument("--preservation-corpus", default=None)
    parser.add_argument("--preservation-sequence-length", type=int, default=32)
    parser.add_argument("--preservation-batch-size", type=int, default=64)
    parser.add_argument("--preservation-seed", type=int, action="append", default=[])
    parser.add_argument("--preservation-games", type=int, default=20)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="mps")
    parser.add_argument("--quiet-engine", action="store_true", default=True)
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    args = parser.parse_args()
    if not args.preservation_seed:
        args.preservation_seed = [9601, 12001]
    if not args.save_step:
        args.save_step = [20, 50, 100, 200]
    return args


if __name__ == "__main__":
    main()
