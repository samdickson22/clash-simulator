"""Search full-episode counterfactual repairs for one deterministic policy loss."""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import LoadedPolicy, _policy_action, load_policy_checkpoint
from clasher.rl.reward_model import DEFENSE_V2, REWARD_PROFILES, potential_breakdown_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import (
    BALANCED,
    REACTIVE_DEFENSE,
    STRATEGY_NAMES,
    StrategyBot,
)
from clasher.rl.train_recurrent import _stack_step_inputs, maybe_silence_stdio


@dataclass
class SearchSnapshot:
    tick: int
    danger: float
    battle: BattleState
    env_rng_state: Any
    env_np_rng_state: Any
    opponent_rng_state: Any | None
    opponent_policy_state: tuple[torch.Tensor, torch.Tensor] | None
    previous_potential_p0: float
    candidate_state: tuple[torch.Tensor, torch.Tensor]
    candidate_action: int
    candidate_mask: np.ndarray
    other_action: int
    other_mask: np.ndarray
    alternatives: tuple[int, ...]


@torch.no_grad()
def _policy_action_and_alternatives(
    loaded: LoadedPolicy,
    env: SelfPlayBattleEnv,
    player_id: int,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    device: torch.device,
    top_k: int,
    per_slot_k: int,
) -> tuple[
    int,
    tuple[torch.Tensor, torch.Tensor],
    np.ndarray,
    tuple[int, ...],
]:
    assert env.battle is not None
    observation = loaded.builder.build(env.battle, player_id)
    mask = env.get_action_mask(player_id)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([previous_action], dtype=np.int64),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start], dtype=np.bool_),
        device,
    )
    action, _, _, next_state, output = loaded.model.act(
        inputs,
        state,
        deterministic=True,
    )
    count = min(top_k, int(mask[0].sum()))
    actions = torch.topk(output.joint_logits[0, 0], k=max(1, count)).indices
    deterministic_action = int(action[0, 0].item())
    diverse_actions: list[int] = []
    if per_slot_k > 0:
        placement_logits = output.joint_logits[0, 0, : NUM_HAND_SLOTS * NUM_TILES]
        placement_logits = placement_logits.reshape(NUM_HAND_SLOTS, NUM_TILES)
        for slot in range(NUM_HAND_SLOTS):
            legal_count = int(mask[0, slot * NUM_TILES : (slot + 1) * NUM_TILES].sum())
            if legal_count <= 0:
                continue
            locations = torch.topk(
                placement_logits[slot],
                k=min(per_slot_k, legal_count),
            ).indices
            diverse_actions.extend(
                slot * NUM_TILES + int(location) for location in locations.cpu().tolist()
            )
    ordered = tuple(
        dict.fromkeys(
            [
                deterministic_action,
                *(int(value) for value in actions.cpu().tolist()),
                *diverse_actions,
            ]
        )
    )
    return deterministic_action, next_state, mask[0], ordered


def _clone_env(source: SelfPlayBattleEnv, snapshot: SearchSnapshot) -> SelfPlayBattleEnv:
    branch = SelfPlayBattleEnv(
        decision_interval_ticks=source.decision_interval_ticks,
        max_ticks=source.max_ticks,
        decks_path=source.decks_path,
        seed=0,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path=source.engine_fast_path,
        reward_profile=source.reward_profile,
    )
    branch.battle = snapshot.battle.clone()
    branch.rng.setstate(snapshot.env_rng_state)
    branch.np_rng.bit_generator.state = copy.deepcopy(snapshot.env_np_rng_state)
    branch._prev_reward_potential_p0 = snapshot.previous_potential_p0
    return branch


def _rollout_branch(
    *,
    source_env: SelfPlayBattleEnv,
    snapshot: SearchSnapshot,
    candidate: LoadedPolicy,
    opponent: LoadedPolicy | None,
    opponent_strategy: StrategyBot | None,
    candidate_player: int,
    action: int,
    device: torch.device,
    quiet_engine: bool,
) -> dict[str, int | str]:
    env = _clone_env(source_env, snapshot)
    other_player = 1 - candidate_player
    opponent_rng = np.random.default_rng()
    if snapshot.opponent_rng_state is not None:
        opponent_rng.bit_generator.state = copy.deepcopy(snapshot.opponent_rng_state)
    opponent_state = (
        None
        if snapshot.opponent_policy_state is None
        else (
            snapshot.opponent_policy_state[0].clone(),
            snapshot.opponent_policy_state[1].clone(),
        )
    )
    candidate_state = (
        snapshot.candidate_state[0].clone(),
        snapshot.candidate_state[1].clone(),
    )

    with maybe_silence_stdio(quiet_engine):
        rewards, done, _ = env.step(
            {candidate_player: action, other_player: snapshot.other_action},
            pre_action_masks={
                candidate_player: snapshot.candidate_mask,
                other_player: snapshot.other_mask,
            },
        )
    previous_action = action
    previous_reward = float(rewards[candidate_player])
    opponent_previous_action = snapshot.other_action
    opponent_previous_reward = float(rewards[other_player])

    while not done:
        candidate_action, candidate_state, candidate_mask = _policy_action(
            candidate,
            env,
            candidate_player,
            state=candidate_state,
            previous_action=previous_action,
            previous_reward=previous_reward,
            episode_start=False,
            deterministic=True,
            device=device,
        )
        if opponent is not None:
            assert opponent_state is not None
            other_action, opponent_state, other_mask = _policy_action(
                opponent,
                env,
                other_player,
                state=opponent_state,
                previous_action=opponent_previous_action,
                previous_reward=opponent_previous_reward,
                episode_start=False,
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
        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(
                {candidate_player: candidate_action, other_player: other_action},
                pre_action_masks={
                    candidate_player: candidate_mask,
                    other_player: other_mask,
                },
            )
        previous_action = candidate_action
        previous_reward = float(rewards[candidate_player])
        opponent_previous_action = other_action
        opponent_previous_reward = float(rewards[other_player])

    assert env.battle is not None
    winner = env.battle.winner
    return {
        "outcome": (
            "draw"
            if winner is None
            else ("win" if winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
    }


def search_loss_repairs(args: argparse.Namespace) -> dict:
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    candidate = load_policy_checkpoint(
        resolve_path(args.checkpoint, must_exist=True),
        device=device,
        decks_path=decks_path,
    )
    opponent = (
        None
        if args.opponent_checkpoint is None
        else load_policy_checkpoint(
            resolve_path(args.opponent_checkpoint, must_exist=True),
            device=device,
            decks_path=decks_path,
        )
    )
    opponent_strategy = (
        None
        if args.opponent_strategy is None
        else StrategyBot(args.opponent_strategy)
    )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=decks_path,
        seed=args.matchup_seed,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path=args.engine_fast_path,
        reward_profile=args.reward_profile,
    )
    with maybe_silence_stdio(args.quiet_engine):
        env.reset(seed=args.matchup_seed)
    opponent_rng = np.random.default_rng(args.matchup_seed + 91_117)
    torch.manual_seed(args.matchup_seed + 271_828)
    candidate_player = args.candidate_player
    other_player = 1 - candidate_player
    candidate_state = candidate.model.initial_state(1, device=device)
    opponent_state = (
        None if opponent is None else opponent.model.initial_state(1, device=device)
    )
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    opponent_previous_action = env.action_space.no_op_action
    opponent_previous_reward = 0.0
    episode_start = True
    done = False
    snapshots: list[SearchSnapshot] = []
    reactive = StrategyBot(REACTIVE_DEFENSE)
    balanced = StrategyBot(BALANCED)

    while not done:
        action, next_state, mask, top_actions = _policy_action_and_alternatives(
            candidate,
            env,
            candidate_player,
            state=candidate_state,
            previous_action=previous_action,
            previous_reward=previous_reward,
            episode_start=episode_start,
            device=device,
            top_k=args.top_k,
            per_slot_k=args.per_slot_k,
        )
        assert env.battle is not None
        breakdown = potential_breakdown_p0(env.battle)
        danger = max(
            0.0,
            -breakdown.tower_danger
            if candidate_player == 0
            else breakdown.tower_danger,
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
        candidate_crowns = env.battle.get_crown_count(candidate_player)
        alternatives = list(top_actions)
        alternatives.extend(
            [
                reactive.select_action(env, candidate_player, action_mask=mask),
                balanced.select_action(env, candidate_player, action_mask=mask),
            ]
        )
        alternatives = list(dict.fromkeys(alternatives))
        if (
            danger >= args.danger_threshold
            and candidate_crowns >= args.minimum_candidate_crowns
            and any(alternative != action for alternative in alternatives)
        ):
            snapshots.append(
                SearchSnapshot(
                    tick=env.battle.tick,
                    danger=danger,
                    battle=env.battle.clone(),
                    env_rng_state=env.rng.getstate(),
                    env_np_rng_state=copy.deepcopy(env.np_rng.bit_generator.state),
                    opponent_rng_state=(
                        copy.deepcopy(opponent_rng.bit_generator.state)
                        if opponent is None and opponent_strategy is None
                        else None
                    ),
                    opponent_policy_state=(
                        None
                        if next_opponent_state is None
                        else (
                            next_opponent_state[0].clone(),
                            next_opponent_state[1].clone(),
                        )
                    ),
                    previous_potential_p0=env._prev_reward_potential_p0,
                    candidate_state=(next_state[0].clone(), next_state[1].clone()),
                    candidate_action=action,
                    candidate_mask=mask.copy(),
                    other_action=other_action,
                    other_mask=other_mask.copy(),
                    alternatives=tuple(alternatives),
                )
            )
        with maybe_silence_stdio(args.quiet_engine):
            rewards, done, _ = env.step(
                {candidate_player: action, other_player: other_action},
                pre_action_masks={
                    candidate_player: mask,
                    other_player: other_mask,
                },
            )
        candidate_state = next_state
        previous_action = action
        previous_reward = float(rewards[candidate_player])
        opponent_state = next_opponent_state
        opponent_previous_action = other_action
        opponent_previous_reward = float(rewards[other_player])
        episode_start = False

    assert env.battle is not None
    baseline = {
        "outcome": (
            "draw"
            if env.battle.winner is None
            else ("win" if env.battle.winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
    }

    selected: list[SearchSnapshot] = []
    if args.state_selection == "temporal" and snapshots:
        selected_indices = np.linspace(
            0,
            len(snapshots) - 1,
            num=min(args.states, len(snapshots)),
            dtype=np.int64,
        )
        selected = [snapshots[int(index)] for index in selected_indices]
    else:
        for snapshot in sorted(
            snapshots,
            key=lambda item: item.danger,
            reverse=True,
        ):
            if all(
                abs(snapshot.tick - prior.tick) >= args.minimum_tick_spacing
                for prior in selected
            ):
                selected.append(snapshot)
            if len(selected) >= args.states:
                break

    branches = []
    for snapshot in sorted(selected, key=lambda item: item.tick):
        for action in snapshot.alternatives:
            if action == snapshot.candidate_action:
                continue
            result = _rollout_branch(
                source_env=env,
                snapshot=snapshot,
                candidate=candidate,
                opponent=opponent,
                opponent_strategy=opponent_strategy,
                candidate_player=candidate_player,
                action=action,
                device=device,
                quiet_engine=args.quiet_engine,
            )
            branches.append(
                {
                    "tick": snapshot.tick,
                    "danger": snapshot.danger,
                    "baseline_action": snapshot.candidate_action,
                    "alternative_action": action,
                    **result,
                }
            )

    payload = {
        "checkpoint": str(resolve_path(args.checkpoint, must_exist=True)),
        "opponent_checkpoint": (
            None
            if args.opponent_checkpoint is None
            else str(resolve_path(args.opponent_checkpoint, must_exist=True))
        ),
        "opponent_strategy": args.opponent_strategy,
        "matchup_seed": args.matchup_seed,
        "candidate_player": candidate_player,
        "baseline": baseline,
        "captured_states": len(snapshots),
        "searched_states": len(selected),
        "branches": branches,
        "winning_repairs": [branch for branch in branches if branch["outcome"] == "win"],
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    opponent_group = parser.add_mutually_exclusive_group()
    opponent_group.add_argument("--opponent-checkpoint")
    opponent_group.add_argument("--opponent-strategy", choices=STRATEGY_NAMES)
    parser.add_argument("--matchup-seed", type=int, required=True)
    parser.add_argument("--candidate-player", type=int, choices=[0, 1], required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--danger-threshold", type=float, default=0.025)
    parser.add_argument(
        "--reward-profile",
        choices=REWARD_PROFILES,
        default=DEFENSE_V2,
        help="must match the fixed evaluation protocol because reward is recurrent input",
    )
    parser.add_argument("--minimum-candidate-crowns", type=int, default=1)
    parser.add_argument("--states", type=int, default=6)
    parser.add_argument(
        "--state-selection",
        choices=["danger", "temporal"],
        default="danger",
    )
    parser.add_argument("--minimum-tick-spacing", type=int, default=96)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--per-slot-k", type=int, default=0)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument(
        "--engine-fast-path", choices=["off", "shadow", "on"], default="off"
    )
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--quiet-engine", action="store_true", default=True)
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = search_loss_repairs(args)
    output = resolve_path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
