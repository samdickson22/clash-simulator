"""Matched gameplay evaluation of the frozen actor plus action-value repair."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch

from clasher.rl.action_value import (
    LoadedPublicActionValueEnsemble,
    LoadedPublicActionValueHead,
    load_public_action_value_controller,
    load_public_action_value_ensemble,
    load_public_action_value_head,
)
from clasher.rl.common import NUM_TILES
from clasher.rl.counterfactual_corpus import (
    build_candidate_context,
    top_policy_candidates,
)
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.recurrent_state_contract import (
    snapshot_action_time_recurrent_state,
)
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.structured_action_value_controller import (
    LoadedPublicStructuredActionValueHead,
    PublicStructuredActionValueState,
    load_public_structured_action_value_head,
)
from clasher.rl.structured_obs import (
    StructuredObservationBuilder,
    build_canonical_tile_features,
)
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_game(
    *,
    repaired: bool,
    game: int,
    seed: int,
    policy_path: Path,
    action_value_path: Path,
    action_value_mode: Literal["single", "ensemble", "controller", "structured"],
    decks_path: Path,
    sampling_decks_path: Path | None,
    learner_sampling_decks_path: Path | None,
    opponent_sampling_decks_path: Path | None,
    strategy_name: str,
    decision_interval: int,
    max_ticks: int,
    max_candidates: int,
    minimum_tick: int,
    query_stride: int,
    device: torch.device,
) -> dict[str, Any]:
    loaded = load_policy_checkpoint(policy_path, device=device, decks_path=decks_path)
    action_value: (
        LoadedPublicActionValueHead
        | LoadedPublicActionValueEnsemble
        | LoadedPublicStructuredActionValueHead
    )
    if action_value_mode == "structured":
        action_value = load_public_structured_action_value_head(
            action_value_path,
            device=device,
        )
    elif action_value_mode == "controller":
        action_value = load_public_action_value_controller(
            action_value_path, device=device
        )
    elif action_value_mode == "ensemble":
        action_value = load_public_action_value_ensemble(
            action_value_path, device=device
        )
    else:
        action_value = load_public_action_value_head(action_value_path, device=device)
    if action_value.source_policy_sha256 is not None:
        if action_value.source_policy_sha256 != _sha256(policy_path):
            raise ValueError("action-value head was fitted for a different actor")
    elif Path(action_value.source_policy).resolve() != policy_path.resolve():
        raise ValueError("action-value head was fitted for a different actor")
    semantic_builder = StructuredObservationBuilder(
        decks_path=decks_path,
        card_vocab=loaded.builder.card_vocab,
        max_entities=loaded.builder.max_entities,
        canonical_perspective=loaded.builder.canonical_perspective,
        canonical_lane_globals=loaded.builder.canonical_lane_globals,
        token_names=loaded.builder.token_names,
        card_semantics_version=3,
        public_history_slots=loaded.builder.public_history_slots,
        public_seen_card_slots=loaded.builder.public_seen_card_slots,
    )
    tile_features = build_canonical_tile_features()
    separate_decks = (
        learner_sampling_decks_path is not None
        and opponent_sampling_decks_path is not None
    )
    common_sampling_path = (
        sampling_decks_path
        if sampling_decks_path is not None
        else opponent_sampling_decks_path
    )
    assert common_sampling_path is not None
    candidate_player = game % 2
    opponent = 1 - candidate_player
    player_paths: tuple[Path | None, Path | None] = (None, None)
    if separate_decks:
        assert learner_sampling_decks_path is not None
        assert opponent_sampling_decks_path is not None
        player_paths = (
            (learner_sampling_decks_path, opponent_sampling_decks_path)
            if candidate_player == 0
            else (opponent_sampling_decks_path, learner_sampling_decks_path)
        )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        sampling_decks_path=common_sampling_path,
        player0_sampling_decks_path=player_paths[0],
        player1_sampling_decks_path=player_paths[1],
        seed=seed,
        canonical_perspective=True,
        canonical_lane_globals=loaded.model.config.canonical_lane_globals,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env._structured_obs_builder = loaded.builder
    env.reset(seed=seed)
    assert env.battle is not None
    candidate_deck = list(env.battle.players[candidate_player].deck)
    opponent_deck = list(env.battle.players[opponent].deck)
    bot = StrategyBot(strategy_name)
    observer = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=None,
        device=device,
        max_candidates=max_candidates,
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
    last_query_decision: int | None = None
    playable_decisions = 0
    playable_no_ops = 0
    placements = 0
    queries = 0
    overrides = 0
    card_plays: Counter[str] = Counter()
    repair_rows: list[dict[str, Any]] = []

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

    done = False
    while not done:
        policy_actions, next_states, outputs, masks = observer.observe_policy_pair(
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
            repaired
            and can_play
            and env.battle.tick >= minimum_tick
            and (
                last_query_decision is None
                or decisions - last_query_decision >= query_stride
            )
        )
        if eligible:
            last_query_decision = decisions
            output = outputs[candidate_player]
            if output.repair_features is None:
                raise ValueError("policy does not expose action-value features")
            raw_candidates = top_policy_candidates(
                base_action=candidate_action,
                joint_logits=output.joint_logits[0, 0].detach().cpu().numpy(),
                action_mask=candidate_mask,
                no_op_action=env.action_space.no_op_action,
                max_candidates=max_candidates,
            )
            candidates = np.full(max_candidates, -1, dtype=np.int64)
            candidates[: len(raw_candidates)] = raw_candidates
            hand_ids = np.asarray(
                [
                    loaded.builder.token_id(card_name)
                    for card_name in env.battle.players[candidate_player].hand
                ],
                dtype=np.int64,
            )
            context = build_candidate_context(
                candidate_actions=candidates,
                hand_ids=hand_ids,
                card_stat_features=semantic_builder.card_stat_features,
                canonical_tile_features=tile_features,
                joint_logits=output.joint_logits[0, 0].detach().cpu().numpy(),
                action_mask=candidate_mask,
                no_op_action=env.action_space.no_op_action,
            )
            if isinstance(action_value, LoadedPublicStructuredActionValueHead):
                observation = env.get_structured_observation(candidate_player)
                recurrent = (
                    snapshot_action_time_recurrent_state(
                        next_states[candidate_player],
                        expected_memory_size=loaded.model.config.memory_size,
                    )
                    if action_value.head.config.recurrent_cell_size
                    else None
                )
                selected_index, scores = action_value.select_candidate(
                    output.repair_features[
                        0, 0, : action_value.head.config.state_size
                    ],
                    PublicStructuredActionValueState(
                        entity_ids=observation.entity_ids,
                        entity_features=observation.entity_features,
                        entity_mask=observation.entity_mask,
                        hand_ids=observation.hand_ids,
                        global_features=observation.global_features,
                        recurrent_cell=(
                            None if recurrent is None else recurrent.cell
                        ),
                        previous_play_hazard=(
                            None
                            if recurrent is None
                            else recurrent.previous_play_hazard
                        ),
                    ),
                    context,
                )
                dispersion = np.zeros_like(scores)
                lower_gain = scores - scores[0]
                minimum_gain = action_value.minimum_score_gain
            elif isinstance(action_value, LoadedPublicActionValueEnsemble):
                selected_index, scores, dispersion, lower_gain = (
                    action_value.select_candidate(
                        output.repair_features[0, 0],
                        context,
                    )
                )
                minimum_gain = action_value.minimum_lower_bound_gain
            else:
                selected_index, scores = action_value.select_candidate(
                    output.repair_features[0, 0],
                    context,
                )
                dispersion = np.zeros_like(scores)
                lower_gain = scores - scores[0]
                minimum_gain = action_value.minimum_score_gain
            candidate_action = int(candidates[selected_index])
            queries += 1
            overrides += selected_index != 0
            repair_rows.append(
                {
                    "tick": int(env.battle.tick),
                    "base": describe_action(int(candidates[0])),
                    "selected": describe_action(candidate_action),
                    "minimum_score_gain": minimum_gain,
                    "ensemble": isinstance(
                        action_value, LoadedPublicActionValueEnsemble
                    ),
                    "structured": isinstance(
                        action_value, LoadedPublicStructuredActionValueHead
                    ),
                    "candidates": [
                        {
                            **describe_action(int(action)),
                            "score": float(scores[index]),
                            "gain_dispersion": float(dispersion[index]),
                            "lower_gain": float(lower_gain[index]),
                            "policy_log_probability": float(
                                context.policy_log_probabilities[index]
                            ),
                        }
                        for index, action in enumerate(candidates)
                        if action >= 0
                    ],
                }
            )
        policy_actions[opponent] = int(
            bot.select_action(env, opponent, action_mask=masks[opponent])
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
    result = (
        "draw"
        if env.battle.winner is None
        else "win"
        if env.battle.winner == candidate_player
        else "loss"
    )
    tower_damage_dealt = float(
        env.battle._tower_damage_dealt_by_player(candidate_player)
    )
    tower_damage_received = float(env.battle._tower_damage_dealt_by_player(opponent))
    return {
        "game": game,
        "seed": seed,
        "repaired": repaired,
        "candidate_player": candidate_player,
        "result": result,
        "candidate_deck": candidate_deck,
        "opponent_deck": opponent_deck,
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(opponent),
        "ticks": int(env.battle.tick),
        "decisions": decisions,
        "playable_decisions": playable_decisions,
        "playable_no_ops": playable_no_ops,
        "playable_no_op_rate": playable_no_ops / max(1, playable_decisions),
        "placements": placements,
        "queries": queries,
        "overrides": overrides,
        "card_plays": dict(sorted(card_plays.items())),
        "unplayed_deck_cards": sorted(set(candidate_deck).difference(card_plays)),
        "tower_damage_dealt": tower_damage_dealt,
        "tower_damage_received": tower_damage_received,
        "tower_damage_differential": tower_damage_dealt - tower_damage_received,
        "repair_rows": repair_rows,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cards: Counter[str] = Counter()
    card_game_opportunities: Counter[str] = Counter()
    card_games_used: Counter[str] = Counter()
    for row in rows:
        cards.update(row["card_plays"])
        card_game_opportunities.update(row["candidate_deck"])
        card_games_used.update(
            card for card, plays in row["card_plays"].items() if int(plays) > 0
        )
    wins = sum(row["result"] == "win" for row in rows)
    losses = sum(row["result"] == "loss" for row in rows)
    playable = sum(int(row["playable_decisions"]) for row in rows)
    no_ops = sum(int(row["playable_no_ops"]) for row in rows)
    return {
        "games": len(rows),
        "wins": wins,
        "losses": losses,
        "draws": len(rows) - wins - losses,
        "crown_differential": sum(
            int(row["candidate_crowns"]) - int(row["opponent_crowns"])
            for row in rows
        ),
        "tower_damage_differential": sum(
            float(row["tower_damage_differential"]) for row in rows
        ),
        "playable_no_op_rate": no_ops / max(1, playable),
        "placements": sum(int(row["placements"]) for row in rows),
        "queries": sum(int(row["queries"]) for row in rows),
        "overrides": sum(int(row["overrides"]) for row in rows),
        "card_plays": dict(sorted(cards.items())),
        "card_game_opportunities": dict(sorted(card_game_opportunities.items())),
        "card_games_used": dict(sorted(card_games_used.items())),
        "card_game_usage_rate": {
            card: card_games_used[card] / opportunities
            for card, opportunities in sorted(card_game_opportunities.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    value_group = parser.add_mutually_exclusive_group(required=True)
    value_group.add_argument("--action-value", type=Path)
    value_group.add_argument("--action-value-ensemble", type=Path)
    value_group.add_argument("--action-value-controller", type=Path)
    value_group.add_argument("--structured-action-value", type=Path)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--sampling-decks-path", type=Path)
    parser.add_argument("--learner-sampling-decks-path", type=Path)
    parser.add_argument("--opponent-sampling-decks-path", type=Path)
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default="balanced")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--game-offset", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1061001)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--minimum-tick", type=int, default=256)
    parser.add_argument("--query-stride", type=int, default=32)
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games <= 0 or args.query_stride <= 0 or args.torch_threads <= 0:
        raise ValueError("games, query stride, and torch threads must be positive")
    separate_decks = (
        args.learner_sampling_decks_path is not None
        and args.opponent_sampling_decks_path is not None
    )
    if (args.learner_sampling_decks_path is None) != (
        args.opponent_sampling_decks_path is None
    ):
        raise ValueError("learner and opponent deck paths require each other")
    if (args.sampling_decks_path is None) == (not separate_decks):
        raise ValueError("supply either shared or separate sampling deck paths")
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    action_value_path = (
        args.action_value
        or args.action_value_ensemble
        or args.action_value_controller
        or args.structured_action_value
    )
    assert action_value_path is not None
    action_value_mode: Literal[
        "single", "ensemble", "controller", "structured"
    ] = (
        "structured"
        if args.structured_action_value is not None
        else "controller"
        if args.action_value_controller is not None
        else "ensemble"
        if args.action_value_ensemble is not None
        else "single"
    )
    rows: list[dict[str, Any]] = []
    for game in range(args.game_offset, args.game_offset + args.games):
        game_seed = args.seed + game * 1009
        for repaired in (False, True):
            row = _run_game(
                repaired=repaired,
                game=game,
                seed=game_seed,
                policy_path=args.policy,
                action_value_path=action_value_path,
                action_value_mode=action_value_mode,
                decks_path=args.decks_path,
                sampling_decks_path=args.sampling_decks_path,
                learner_sampling_decks_path=args.learner_sampling_decks_path,
                opponent_sampling_decks_path=args.opponent_sampling_decks_path,
                strategy_name=args.strategy,
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                max_candidates=args.max_candidates,
                minimum_tick=args.minimum_tick,
                query_stride=args.query_stride,
                device=device,
            )
            rows.append(row)
            print(
                f"game={game} repaired={int(repaired)} result={row['result']} "
                f"crowns={row['candidate_crowns']}-{row['opponent_crowns']} "
                f"overrides={row['overrides']}",
                flush=True,
            )
    baseline = [row for row in rows if not row["repaired"]]
    repaired_rows = [row for row in rows if row["repaired"]]
    report = {
        "schema_version": 1,
        "policy": str(args.policy.resolve()),
        "policy_sha256": _sha256(args.policy),
        "action_value": str(action_value_path.resolve()),
        "action_value_sha256": _sha256(action_value_path),
        "action_value_mode": action_value_mode,
        "decks_sha256": _sha256(args.decks_path),
        "sampling_decks_path": (
            str(args.sampling_decks_path.resolve())
            if args.sampling_decks_path is not None
            else None
        ),
        "learner_sampling_decks_path": (
            str(args.learner_sampling_decks_path.resolve())
            if args.learner_sampling_decks_path is not None
            else None
        ),
        "learner_sampling_decks_sha256": (
            _sha256(args.learner_sampling_decks_path)
            if args.learner_sampling_decks_path is not None
            else None
        ),
        "opponent_sampling_decks_path": (
            str(args.opponent_sampling_decks_path.resolve())
            if args.opponent_sampling_decks_path is not None
            else None
        ),
        "opponent_sampling_decks_sha256": (
            _sha256(args.opponent_sampling_decks_path)
            if args.opponent_sampling_decks_path is not None
            else None
        ),
        "strategy": args.strategy,
        "seed": args.seed,
        "game_offset": args.game_offset,
        "decision_interval": args.decision_interval,
        "max_ticks": args.max_ticks,
        "max_candidates": args.max_candidates,
        "minimum_tick": args.minimum_tick,
        "query_stride": args.query_stride,
        "baseline": _summarize(baseline),
        "repaired": _summarize(repaired_rows),
        "games": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("baseline", "repaired")}, sort_keys=True))


if __name__ == "__main__":
    main()
