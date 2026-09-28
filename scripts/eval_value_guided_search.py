"""Matched evaluation of recurrent outcome-guided root action reranking."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.public_outcome import load_public_outcome_head
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch


def _run_game(
    *,
    guided: bool,
    game: int,
    seed: int,
    policy_path: Path,
    outcome_path: Path,
    decks_path: Path,
    sampling_decks_path: Path,
    strategy_name: str,
    decision_interval: int,
    max_ticks: int,
    rollout_decisions: int,
    terminal_rollout: bool,
    max_candidates: int,
    minimum_value_gain: float,
    maximum_override_base_probability: float,
    query_stride: int,
    query_tick: int | None,
    device: torch.device,
) -> dict[str, Any]:
    loaded = load_policy_checkpoint(policy_path, device=device, decks_path=decks_path)
    outcome = load_public_outcome_head(outcome_path, device=device)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks_path,
        seed=seed,
        canonical_perspective=True,
        canonical_lane_globals=loaded.model.config.canonical_lane_globals,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env._structured_obs_builder = loaded.builder
    env.reset(seed=seed)
    assert env.battle is not None
    candidate_player = game % 2
    opponent = 1 - candidate_player
    bot = StrategyBot(strategy_name)
    search = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=outcome,
        device=device,
        rollout_decisions=rollout_decisions,
        terminal_rollout=terminal_rollout,
        max_candidates=max_candidates,
        minimum_value_gain=minimum_value_gain,
        maximum_override_base_probability=maximum_override_base_probability,
    )
    states = {
        player: loaded.model.initial_state(1, device=device)
        for player in (0, 1)
    }
    previous_actions = {
        player: env.action_space.no_op_action for player in (0, 1)
    }
    previous_rewards = {0: 0.0, 1: 0.0}
    episode_start = True
    decisions = 0
    playable_decisions = 0
    playable_no_ops = 0
    placements = 0
    searches = 0
    overrides = 0
    card_plays: Counter[str] = Counter()
    search_rows: list[dict[str, Any]] = []

    def describe_action(action: int) -> dict[str, Any]:
        assert env.battle is not None
        if action == env.action_space.no_op_action:
            return {"action": action, "kind": "no-op"}
        if action == env.action_space.ability_action:
            return {"action": action, "kind": "ability"}
        slot = action // NUM_TILES
        return {
            "action": action,
            "kind": "placement",
            "slot": slot,
            "tile": action % NUM_TILES,
            "card": str(env.battle.players[candidate_player].hand[slot]),
        }

    def opponent_selector(
        simulation: SelfPlayBattleEnv,
        player_id: int,
        action_mask: np.ndarray,
    ) -> int:
        return int(
            bot.select_action(
                simulation,
                player_id,
                action_mask=action_mask,
            )
        )

    done = False
    while not done:
        policy_actions, next_states, _outputs, masks = search.observe_policy_pair(
            env,
            states=states,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_start=episode_start,
        )
        candidate_action = policy_actions[candidate_player]
        candidate_mask = masks[candidate_player]
        can_play = bool(
            np.any(candidate_mask[: env.action_space.no_op_action])
            or candidate_mask[env.action_space.ability_action]
        )
        if can_play:
            playable_decisions += 1
        eligible = bool(
            guided
            and can_play
            and candidate_action == env.action_space.no_op_action
            and (
                env.battle.tick == query_tick
                if query_tick is not None
                else decisions % query_stride == 0
            )
        )
        if eligible:
            decision = search.select_action(
                env,
                candidate_player,
                states=states,
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_start=episode_start,
                opponent_selector=opponent_selector,
            )
            candidate_action = decision.action
            policy_actions = decision.policy_actions
            next_states = decision.next_states
            masks = decision.action_masks
            searches += 1
            overrides += int(decision.overridden)
            search_rows.append(
                {
                    "tick": int(env.battle.tick),
                    "base_action": decision.base_action,
                    "selected_action": decision.action,
                    "base_probability": decision.base_probability,
                    "selected_probability": decision.selected_probability,
                    "base": describe_action(decision.base_action),
                    "selected": describe_action(decision.action),
                    "candidates": [
                        {
                            **describe_action(row.action),
                            "probability": row.probability,
                        }
                        for row in decision.candidates
                    ],
                }
            )
        else:
            policy_actions[opponent] = opponent_selector(
                env,
                opponent,
                masks[opponent],
            )
        actions = dict(policy_actions)
        actions[candidate_player] = candidate_action
        if can_play and candidate_action == env.action_space.no_op_action:
            playable_no_ops += 1
        if candidate_action < env.action_space.no_op_action:
            slot = candidate_action // NUM_TILES
            card_plays[str(env.battle.players[candidate_player].hand[slot])] += 1
            placements += 1
        rewards, done, _ = env.step(actions, pre_action_masks=masks)
        states = next_states
        previous_actions = actions
        previous_rewards = {player: float(rewards[player]) for player in (0, 1)}
        episode_start = False
        decisions += 1
    assert env.battle is not None
    if env.battle.winner is None:
        result = "draw"
    elif env.battle.winner == candidate_player:
        result = "win"
    else:
        result = "loss"
    return {
        "game": game,
        "seed": seed,
        "guided": guided,
        "candidate_player": candidate_player,
        "result": result,
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(opponent),
        "ticks": int(env.battle.tick),
        "decisions": decisions,
        "playable_decisions": playable_decisions,
        "playable_no_ops": playable_no_ops,
        "playable_no_op_rate": playable_no_ops / max(1, playable_decisions),
        "placements": placements,
        "searches": searches,
        "overrides": overrides,
        "card_plays": dict(sorted(card_plays.items())),
        "search_rows": search_rows,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    card_plays: Counter[str] = Counter()
    for row in rows:
        card_plays.update(row["card_plays"])
    wins = sum(row["result"] == "win" for row in rows)
    losses = sum(row["result"] == "loss" for row in rows)
    draws = len(rows) - wins - losses
    playable = sum(int(row["playable_decisions"]) for row in rows)
    no_ops = sum(int(row["playable_no_ops"]) for row in rows)
    return {
        "games": len(rows),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / max(1, len(rows)),
        "crown_diff_per_game": sum(
            int(row["candidate_crowns"]) - int(row["opponent_crowns"])
            for row in rows
        )
        / max(1, len(rows)),
        "playable_no_op_rate": no_ops / max(1, playable),
        "placements_per_game": sum(int(row["placements"]) for row in rows)
        / max(1, len(rows)),
        "searches": sum(int(row["searches"]) for row in rows),
        "overrides": sum(int(row["overrides"]) for row in rows),
        "card_plays": dict(sorted(card_plays.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--sampling-decks-path", type=Path, required=True)
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default="balanced")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--game-offset", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1053201)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--rollout-decisions", type=int, default=2)
    parser.add_argument("--terminal-rollout", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--minimum-value-gain", type=float, default=0.02)
    parser.add_argument(
        "--maximum-override-base-probability",
        type=float,
        default=1.0,
    )
    parser.add_argument("--query-stride", type=int, default=8)
    parser.add_argument("--query-tick", type=int)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games <= 0 or args.query_stride <= 0:
        raise ValueError("games and query stride must be positive")
    device = torch.device(args.device)
    rows: list[dict[str, Any]] = []
    for game in range(args.game_offset, args.game_offset + args.games):
        game_seed = args.seed + game * 1009
        for guided in (False, True):
            row = _run_game(
                guided=guided,
                game=game,
                seed=game_seed,
                policy_path=args.policy,
                outcome_path=args.outcome,
                decks_path=args.decks_path,
                sampling_decks_path=args.sampling_decks_path,
                strategy_name=args.strategy,
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                rollout_decisions=args.rollout_decisions,
                terminal_rollout=args.terminal_rollout,
                max_candidates=args.max_candidates,
                minimum_value_gain=args.minimum_value_gain,
                maximum_override_base_probability=(
                    args.maximum_override_base_probability
                ),
                query_stride=args.query_stride,
                query_tick=args.query_tick,
                device=device,
            )
            rows.append(row)
            print(
                f"game={game} guided={int(guided)} result={row['result']} "
                f"crowns={row['candidate_crowns']}-{row['opponent_crowns']} "
                f"noop={row['playable_no_op_rate']:.3f} "
                f"searches={row['searches']} overrides={row['overrides']}",
                flush=True,
            )
    baseline = [row for row in rows if not row["guided"]]
    guided_rows = [row for row in rows if row["guided"]]
    report = {
        "schema_version": 1,
        "policy": str(args.policy.resolve()),
        "outcome": str(args.outcome.resolve()),
        "sampling_decks_path": str(args.sampling_decks_path.resolve()),
        "strategy": args.strategy,
        "seed": args.seed,
        "game_offset": args.game_offset,
        "rollout_decisions": args.rollout_decisions,
        "terminal_rollout": args.terminal_rollout,
        "max_candidates": args.max_candidates,
        "minimum_value_gain": args.minimum_value_gain,
        "maximum_override_base_probability": (
            args.maximum_override_base_probability
        ),
        "query_stride": args.query_stride,
        "query_tick": args.query_tick,
        "baseline": _summarize(baseline),
        "guided": _summarize(guided_rows),
        "games": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("baseline", "guided")}, sort_keys=True))


if __name__ == "__main__":
    main()
