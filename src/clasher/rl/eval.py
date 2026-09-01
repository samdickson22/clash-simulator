from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Optional

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path, resolve_path

from .model import ClasherPolicy, PolicyConfig
from .selfplay_env import SelfPlayBattleEnv
from .structured_obs import StructuredObservationBuilder
from .train_recurrent import (
    _stack_step_inputs,
    find_latest_checkpoint,
    maybe_silence_stdio,
    resolve_torch_device,
)


@dataclass
class LoadedPolicy:
    model: ClasherPolicy
    builder: StructuredObservationBuilder
    checkpoint: dict


def load_policy_checkpoint(
    checkpoint_path: Path,
    *,
    device: torch.device,
    decks_path: str | Path,
) -> LoadedPolicy:
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if int(state.get("format_version", 0)) != 2:
        raise ValueError(f"{checkpoint_path} is not a V2 recurrent policy checkpoint")
    config = PolicyConfig.from_dict(state["model_config"])
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=config.max_entities,
        token_names=state["token_names"],
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=config.canonical_lane_globals,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    return LoadedPolicy(model=model, builder=builder, checkpoint=state)


@torch.no_grad()
def _policy_action(
    loaded: LoadedPolicy,
    env: SelfPlayBattleEnv,
    player_id: int,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    deterministic: bool,
    device: torch.device,
) -> tuple[int, tuple[torch.Tensor, torch.Tensor], np.ndarray]:
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
    action, _, _, next_state, _ = loaded.model.act(
        inputs, state, deterministic=deterministic
    )
    return int(action[0, 0].item()), next_state, mask[0]


def evaluate(
    *,
    candidate: LoadedPolicy,
    decks_path: Path,
    games: int,
    seed: int,
    decision_interval: int,
    max_ticks: int,
    opponent_mode: str,
    opponent: Optional[LoadedPolicy],
    deterministic: bool,
    quiet_engine: bool,
    device: torch.device,
) -> dict[str, float]:
    if games <= 0:
        raise ValueError("games must be positive")
    torch.manual_seed(seed)
    np.random.seed(seed)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed,
        mirror_match=False,
        canonical_perspective=True,
    )
    wins = losses = draws = 0
    candidate_crowns = opponent_crowns = 0
    ticks = 0
    actions = 0
    no_ops = 0
    playable_actions = 0
    playable_no_ops = 0
    placements = 0
    abilities = 0
    wins_as_player0 = 0
    wins_as_player1 = 0
    start_time = time.perf_counter()

    for game in range(games):
        matchup = game // 2
        matchup_seed = seed + matchup * 1009
        with maybe_silence_stdio(quiet_engine):
            env.reset(seed=matchup_seed)
        rng = np.random.default_rng(matchup_seed + 91_117)
        torch.manual_seed(matchup_seed + 271_828)
        candidate_player = game % 2
        other_player = 1 - candidate_player
        candidate_state = candidate.model.initial_state(1, device=device)
        opponent_state = (
            opponent.model.initial_state(1, device=device) if opponent is not None else None
        )
        candidate_previous_action = env.action_space.no_op_action
        opponent_previous_action = env.action_space.no_op_action
        candidate_previous_reward = 0.0
        opponent_previous_reward = 0.0
        episode_start = True
        done = False

        while not done:
            candidate_action, candidate_state, candidate_mask = _policy_action(
                candidate,
                env,
                candidate_player,
                state=candidate_state,
                previous_action=candidate_previous_action,
                previous_reward=candidate_previous_reward,
                episode_start=episode_start,
                deterministic=deterministic,
                device=device,
            )
            if opponent_mode == "noop":
                other_action = env.action_space.no_op_action
                other_mask = env.get_action_mask(other_player)
            elif opponent_mode == "random":
                other_mask = env.get_action_mask(other_player)
                legal = np.flatnonzero(other_mask)
                other_action = (
                    int(rng.choice(legal))
                    if legal.size
                    else env.action_space.no_op_action
                )
            else:
                if opponent is None or opponent_state is None:
                    raise ValueError("policy opponent requires a loaded checkpoint")
                other_action, opponent_state, other_mask = _policy_action(
                    opponent,
                    env,
                    other_player,
                    state=opponent_state,
                    previous_action=opponent_previous_action,
                    previous_reward=opponent_previous_reward,
                    episode_start=episode_start,
                    deterministic=deterministic,
                    device=device,
                )
            with maybe_silence_stdio(quiet_engine):
                rewards, done, _ = env.step(
                    {candidate_player: candidate_action, other_player: other_action},
                    pre_action_masks={
                        candidate_player: candidate_mask,
                        other_player: other_mask,
                    },
                )
            candidate_previous_action = candidate_action
            opponent_previous_action = other_action
            candidate_previous_reward = float(rewards[candidate_player])
            opponent_previous_reward = float(rewards[other_player])
            episode_start = False
            actions += 1
            no_ops += int(candidate_action == env.action_space.no_op_action)
            can_play = bool(
                np.any(candidate_mask[: env.action_space.no_op_action])
                or candidate_mask[env.action_space.ability_action]
            )
            playable_actions += int(can_play)
            playable_no_ops += int(
                can_play and candidate_action == env.action_space.no_op_action
            )
            placements += int(candidate_action < env.action_space.no_op_action)
            abilities += int(candidate_action == env.action_space.ability_action)

        assert env.battle is not None
        ticks += env.battle.tick
        candidate_crowns += env.battle.get_crown_count(candidate_player)
        opponent_crowns += env.battle.get_crown_count(other_player)
        if env.battle.winner is None:
            draws += 1
        elif env.battle.winner == candidate_player:
            wins += 1
            wins_as_player0 += int(candidate_player == 0)
            wins_as_player1 += int(candidate_player == 1)
        else:
            losses += 1

    elapsed = time.perf_counter() - start_time
    score = (wins + 0.5 * draws) / games
    standard_error = float(np.sqrt(max(0.0, score * (1.0 - score) / games)))
    return {
        "games": float(games),
        "wins": float(wins),
        "losses": float(losses),
        "draws": float(draws),
        "win_rate": wins / games,
        "score_rate": score,
        "score_ci95_low": max(0.0, score - 1.96 * standard_error),
        "score_ci95_high": min(1.0, score + 1.96 * standard_error),
        "non_loss_rate": (wins + draws) / games,
        "crown_diff_per_game": (candidate_crowns - opponent_crowns) / games,
        "average_ticks": ticks / games,
        "candidate_noop_rate": no_ops / max(1, actions),
        "candidate_noop_when_playable": playable_no_ops / max(1, playable_actions),
        "candidate_placement_rate": placements / max(1, actions),
        "candidate_ability_rate": abilities / max(1, actions),
        "wins_as_player0": float(wins_as_player0),
        "wins_as_player1": float(wins_as_player1),
        "elapsed_seconds": elapsed,
        "games_per_minute": games * 60.0 / max(1e-9, elapsed),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a V2 recurrent Clasher policy")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    parser.add_argument("--opponent", choices=["random", "noop", "policy"], default="random")
    parser.add_argument("--opponent-checkpoint", default=None)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    parser.add_argument("--quiet-engine", dest="quiet_engine", action="store_true", default=True)
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = resolve_torch_device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint_path: Path
    if args.checkpoint:
        checkpoint_path = resolve_path(args.checkpoint, must_exist=True)
    else:
        directory = resolve_path(args.checkpoint_dir, must_exist=True)
        latest_checkpoint = find_latest_checkpoint(directory)
        if latest_checkpoint is None:
            raise FileNotFoundError(f"no V2 checkpoints in {directory}")
        checkpoint_path = latest_checkpoint
    candidate = load_policy_checkpoint(
        checkpoint_path, device=device, decks_path=decks_path
    )
    opponent: Optional[LoadedPolicy] = None
    if args.opponent == "policy":
        if not args.opponent_checkpoint:
            raise ValueError("--opponent-checkpoint is required for a policy opponent")
        opponent_path = resolve_path(args.opponent_checkpoint, must_exist=True)
        opponent = load_policy_checkpoint(
            opponent_path, device=device, decks_path=decks_path
        )
        print(f"opponent_checkpoint={opponent_path}")
    print(f"device={device}")
    print(f"checkpoint={checkpoint_path}")
    print(f"checkpoint_update={candidate.checkpoint.get('update', 0)}")
    print(f"checkpoint_transitions={candidate.checkpoint.get('total_transitions', 0)}")
    metrics = evaluate(
        candidate=candidate,
        decks_path=decks_path,
        games=args.games,
        seed=args.seed,
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
        opponent_mode=args.opponent,
        opponent=opponent,
        deterministic=args.deterministic,
        quiet_engine=args.quiet_engine,
        device=device,
    )
    print(
        f"games={int(metrics['games'])} wins={int(metrics['wins'])} "
        f"losses={int(metrics['losses'])} draws={int(metrics['draws'])}"
    )
    print(
        f"win_rate={metrics['win_rate']:.3f} "
        f"score={metrics['score_rate']:.3f} "
        f"score_ci95=[{metrics['score_ci95_low']:.3f},{metrics['score_ci95_high']:.3f}] "
        f"non_loss_rate={metrics['non_loss_rate']:.3f} "
        f"crown_diff={metrics['crown_diff_per_game']:+.3f} "
        f"noop_rate={metrics['candidate_noop_rate']:.3f} "
        f"noop_when_playable={metrics['candidate_noop_when_playable']:.3f}"
    )
    print(
        f"placement_rate={metrics['candidate_placement_rate']:.3f} "
        f"ability_rate={metrics['candidate_ability_rate']:.4f} "
        f"wins_by_seat={int(metrics['wins_as_player0'])}/{int(metrics['wins_as_player1'])} "
        f"average_ticks={metrics['average_ticks']:.1f} "
        f"elapsed_seconds={metrics['elapsed_seconds']:.2f} "
        f"games_per_minute={metrics['games_per_minute']:.2f}"
    )


if __name__ == "__main__":
    main()
