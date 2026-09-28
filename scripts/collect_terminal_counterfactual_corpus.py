"""Collect exact terminal action interventions from recurrent policy trajectories."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.counterfactual_corpus import (
    build_candidate_context,
    should_query_counterfactual,
    terminal_candidate_order,
)
from clasher.rl.counterfactual_schedule import (
    phase_balanced_query_ticks,
    should_query_phase_balanced_counterfactual,
)
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.public_outcome import load_public_outcome_head
from clasher.rl.recurrent_state_contract import (
    snapshot_action_time_recurrent_state,
)
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.structured_obs import (
    StructuredObservationBuilder,
    build_canonical_tile_features,
)
from clasher.rl.value_guided_search import CandidateValue, RecurrentValueGuidedSearch


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _describe_action(
    env: SelfPlayBattleEnv,
    player_id: int,
    action: int,
) -> dict[str, Any]:
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
        "card": str(env.battle.players[player_id].hand[slot]),
    }


def _terminal_order(candidate: CandidateValue) -> tuple[float, int, float]:
    if (
        candidate.crown_difference is None
        or candidate.tower_damage_difference is None
    ):
        raise ValueError("terminal counterfactual candidate is missing tiebreak data")
    return terminal_candidate_order(
        candidate.probability,
        candidate.crown_difference,
        candidate.tower_damage_difference,
    )


def _best_terminal_candidate(
    candidates: tuple[CandidateValue, ...],
) -> CandidateValue:
    if not candidates:
        raise ValueError("terminal counterfactual candidate set is empty")
    best_order = max(_terminal_order(row) for row in candidates)
    if _terminal_order(candidates[0]) == best_order:
        return candidates[0]
    return min(
        (row for row in candidates if _terminal_order(row) == best_order),
        key=lambda row: row.action,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument(
        "--outcome",
        type=Path,
        default=None,
        help="optional nonterminal leaf head; terminal collection does not require it",
    )
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--sampling-decks-path", type=Path, default=None)
    parser.add_argument("--learner-sampling-decks-path", type=Path, default=None)
    parser.add_argument("--opponent-sampling-decks-path", type=Path, default=None)
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--game-offset", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1053401)
    parser.add_argument("--states-per-game", type=int, default=1)
    parser.add_argument("--minimum-tick", type=int, default=256)
    parser.add_argument("--query-stride", type=int, default=32)
    parser.add_argument(
        "--query-schedule",
        choices=("first-eligible", "phase-balanced"),
        default="first-eligible",
    )
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--overtime-start-tick", type=int, default=3600)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--locations-per-slot", type=int, default=1)
    parser.add_argument("--spatially-diverse-locations", action="store_true")
    parser.add_argument("--include-structured-state", action="store_true")
    parser.add_argument(
        "--include-action-time-recurrent-state",
        action="store_true",
    )
    parser.add_argument(
        "--required-candidate-card",
        action="append",
        default=[],
        help="collect only roots whose evaluated candidate set contains one of these cards",
    )
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.games <= 0 or args.states_per_game <= 0 or args.query_stride <= 0:
        raise ValueError("games, states per game, and query stride must be positive")
    if args.max_candidates <= 0 or args.locations_per_slot <= 0:
        raise ValueError("candidate and per-slot location counts must be positive")
    separate_deck_pools = (
        args.learner_sampling_decks_path is not None
        and args.opponent_sampling_decks_path is not None
    )
    if (args.learner_sampling_decks_path is None) != (
        args.opponent_sampling_decks_path is None
    ):
        raise ValueError("learner and opponent sampling deck paths require each other")
    if args.sampling_decks_path is None and not separate_deck_pools:
        raise ValueError("a shared or separate pair of sampling deck paths is required")
    if args.torch_threads <= 0:
        raise ValueError("torch threads must be positive")
    if args.include_action_time_recurrent_state and not args.include_structured_state:
        raise ValueError("action-time recurrence requires structured state")
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    loaded = load_policy_checkpoint(args.policy, device=device, decks_path=args.decks_path)
    outcome = (
        None
        if args.outcome is None
        else load_public_outcome_head(args.outcome, device=device)
    )
    semantic_builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        card_vocab=loaded.builder.card_vocab,
        max_entities=loaded.builder.max_entities,
        canonical_perspective=loaded.builder.canonical_perspective,
        canonical_lane_globals=loaded.builder.canonical_lane_globals,
        token_names=loaded.builder.token_names,
        card_semantics_version=3,
        public_history_slots=loaded.builder.public_history_slots,
        public_seen_card_slots=loaded.builder.public_seen_card_slots,
    )
    if semantic_builder.token_names != loaded.builder.token_names:
        raise ValueError("semantic card table token authority does not match policy")
    unknown_required_cards = sorted(
        set(args.required_candidate_card).difference(loaded.builder.card_vocab)
    )
    if unknown_required_cards:
        raise ValueError(
            f"required candidate cards are outside the policy deck vocabulary: "
            f"{unknown_required_cards}"
        )
    search = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=outcome,
        device=device,
        terminal_rollout=True,
        max_candidates=args.max_candidates,
        locations_per_slot=args.locations_per_slot,
        spatially_diverse_locations=args.spatially_diverse_locations,
        minimum_value_gain=0.0,
    )
    canonical_tile_features = build_canonical_tile_features()
    phase_target_ticks = (
        phase_balanced_query_ticks(
            minimum_tick=args.minimum_tick,
            max_ticks=args.max_ticks,
            states_per_game=args.states_per_game,
            decision_interval=args.decision_interval,
            phase_boundaries=(
                (args.overtime_start_tick,)
                if args.minimum_tick < args.overtime_start_tick
                else ()
            ),
        )
        if args.query_schedule == "phase-balanced"
        else ()
    )
    feature_rows: list[np.ndarray] = []
    mask_rows: list[np.ndarray] = []
    base_actions: list[int] = []
    best_actions: list[int] = []
    candidate_action_rows: list[np.ndarray] = []
    candidate_score_rows: list[np.ndarray] = []
    candidate_valid_rows: list[np.ndarray] = []
    candidate_kind_rows: list[np.ndarray] = []
    candidate_card_id_rows: list[np.ndarray] = []
    candidate_card_feature_rows: list[np.ndarray] = []
    candidate_tile_feature_rows: list[np.ndarray] = []
    candidate_policy_logit_rows: list[np.ndarray] = []
    candidate_policy_log_probability_rows: list[np.ndarray] = []
    candidate_policy_type_log_probability_rows: list[np.ndarray] = []
    candidate_crown_difference_rows: list[np.ndarray] = []
    candidate_tower_damage_difference_rows: list[np.ndarray] = []
    candidate_terminal_tick_rows: list[np.ndarray] = []
    hand_id_rows: list[np.ndarray] = []
    structured_entity_id_rows: list[np.ndarray] = []
    structured_entity_feature_rows: list[np.ndarray] = []
    structured_entity_mask_rows: list[np.ndarray] = []
    structured_hand_id_rows: list[np.ndarray] = []
    structured_global_feature_rows: list[np.ndarray] = []
    structured_opponent_history_id_rows: list[np.ndarray] = []
    structured_opponent_history_age_rows: list[np.ndarray] = []
    structured_opponent_seen_card_id_rows: list[np.ndarray] = []
    structured_previous_action_rows: list[int] = []
    structured_previous_reward_rows: list[float] = []
    structured_episode_start_rows: list[bool] = []
    structured_recurrent_cell_rows: list[np.ndarray] = []
    structured_previous_play_hazard_rows: list[np.ndarray] = []
    game_ids: list[int] = []
    tick_rows: list[int] = []
    audit_rows: list[dict[str, Any]] = []
    game_rows: list[dict[str, Any]] = []

    for game in range(args.game_offset, args.game_offset + args.games):
        game_seed = args.seed + game * 1009
        strategy_name = STRATEGY_NAMES[game % len(STRATEGY_NAMES)]
        controlled_player = (game // len(STRATEGY_NAMES)) % 2
        opponent = 1 - controlled_player
        bot = StrategyBot(strategy_name)
        common_sampling_path = (
            args.sampling_decks_path
            if args.sampling_decks_path is not None
            else args.opponent_sampling_decks_path
        )
        assert common_sampling_path is not None
        player_sampling_paths: tuple[Path | None, Path | None] = (None, None)
        if separate_deck_pools:
            assert args.learner_sampling_decks_path is not None
            assert args.opponent_sampling_decks_path is not None
            player_sampling_paths = (
                (
                    args.learner_sampling_decks_path,
                    args.opponent_sampling_decks_path,
                )
                if controlled_player == 0
                else (
                    args.opponent_sampling_decks_path,
                    args.learner_sampling_decks_path,
                )
            )
        env = SelfPlayBattleEnv(
            decision_interval_ticks=args.decision_interval,
            max_ticks=args.max_ticks,
            decks_path=args.decks_path,
            sampling_decks_path=common_sampling_path,
            player0_sampling_decks_path=player_sampling_paths[0],
            player1_sampling_decks_path=player_sampling_paths[1],
            seed=game_seed,
            canonical_perspective=True,
            canonical_lane_globals=loaded.model.config.canonical_lane_globals,
            engine_fast_path="on",
            reward_profile=DEFENSE_V2,
        )
        env._structured_obs_builder = loaded.builder
        env.reset(seed=game_seed)
        assert env.battle is not None
        decks = [list(player.deck) for player in env.battle.players]
        unknown_deck_cards = sorted(
            {
                card
                for deck in decks
                for card in deck
                if loaded.builder.token_id(card) <= 1
            }
        )
        if unknown_deck_cards:
            raise ValueError(
                "counterfactual deck cards are outside the policy vocabulary: "
                f"{unknown_deck_cards}"
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
        decision_index = 0
        last_query_decision: int | None = None
        collected = 0
        done = False

        def opponent_selector(
            simulation: SelfPlayBattleEnv,
            player_id: int,
            action_mask: np.ndarray,
            strategy_bot: StrategyBot = bot,
        ) -> int:
            return int(
                strategy_bot.select_action(
                    simulation,
                    player_id,
                    action_mask=action_mask,
                )
            )

        while not done:
            policy_actions, next_states, outputs, masks = search.observe_policy_pair(
                env,
                states=states,
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_start=episode_start,
            )
            base_action = policy_actions[controlled_player]
            controlled_mask = masks[controlled_player]
            can_play = bool(
                np.any(controlled_mask[: env.action_space.no_op_action])
                or controlled_mask[env.action_space.ability_action]
            )
            if args.query_schedule == "phase-balanced":
                query = should_query_phase_balanced_counterfactual(
                    decision_index=decision_index,
                    last_query_decision=last_query_decision,
                    tick=int(env.battle.tick),
                    collected=collected,
                    target_ticks=phase_target_ticks,
                    minimum_decision_spacing=args.query_stride,
                    can_play=can_play,
                )
            else:
                query = should_query_counterfactual(
                    decision_index=decision_index,
                    last_query_decision=last_query_decision,
                    tick=int(env.battle.tick),
                    collected=collected,
                    states_per_game=args.states_per_game,
                    minimum_tick=args.minimum_tick,
                    query_stride=args.query_stride,
                    can_play=can_play,
                )
            if query and args.required_candidate_card:
                preliminary_candidates = search.candidate_actions(
                    base_action=base_action,
                    output=outputs[controlled_player],
                    action_mask=controlled_mask,
                )
                candidate_cards = {
                    str(
                        env.battle.players[controlled_player].hand[
                            action // NUM_TILES
                        ]
                    )
                    for action in preliminary_candidates
                    if action < env.action_space.no_op_action
                }
                query = bool(
                    candidate_cards.intersection(args.required_candidate_card)
                )
            if query:
                last_query_decision = decision_index
                exact = search.select_action(
                    env,
                    controlled_player,
                    states=states,
                    previous_actions=previous_actions,
                    previous_rewards=previous_rewards,
                    episode_start=episode_start,
                    opponent_selector=opponent_selector,
                )
                repair_features = outputs[controlled_player].repair_features
                if repair_features is None:
                    raise ValueError("policy does not expose intervention features")
                features = (
                    repair_features[0, 0]
                    .detach()
                    .cpu()
                    .numpy()
                    .astype(np.float32, copy=True)
                )
                candidate_actions = np.full(
                    args.max_candidates,
                    -1,
                    dtype=np.int64,
                )
                candidate_scores = np.full(
                    args.max_candidates,
                    np.nan,
                    dtype=np.float32,
                )
                candidate_crown_differences = np.zeros(
                    args.max_candidates,
                    dtype=np.int8,
                )
                candidate_tower_damage_differences = np.full(
                    args.max_candidates,
                    np.nan,
                    dtype=np.float32,
                )
                candidate_terminal_ticks = np.full(
                    args.max_candidates,
                    -1,
                    dtype=np.int32,
                )
                for index, candidate in enumerate(exact.candidates):
                    candidate_actions[index] = candidate.action
                    candidate_scores[index] = candidate.probability
                    if candidate.crown_difference is not None:
                        candidate_crown_differences[index] = candidate.crown_difference
                    if candidate.tower_damage_difference is not None:
                        candidate_tower_damage_differences[index] = (
                            candidate.tower_damage_difference
                        )
                    if candidate.terminal_tick is not None:
                        candidate_terminal_ticks[index] = candidate.terminal_tick
                hand_ids = np.asarray(
                    [
                        loaded.builder.token_id(card_name)
                        for card_name in env.battle.players[controlled_player].hand
                    ],
                    dtype=np.int64,
                )
                if np.any(hand_ids <= 1):
                    raise ValueError(
                        "counterfactual controlled hand contains an unknown token"
                    )
                candidate_context = build_candidate_context(
                    candidate_actions=candidate_actions,
                    hand_ids=hand_ids,
                    card_stat_features=semantic_builder.card_stat_features,
                    canonical_tile_features=canonical_tile_features,
                    joint_logits=(
                        outputs[controlled_player].joint_logits[0, 0]
                        .detach()
                        .cpu()
                        .numpy()
                    ),
                    action_mask=controlled_mask,
                    no_op_action=env.action_space.no_op_action,
                )
                if exact.candidates[0].action != base_action:
                    raise ValueError("terminal candidate zero is not the base action")
                base_order = _terminal_order(exact.candidates[0])
                best_candidate = _best_terminal_candidate(exact.candidates)
                best_order = _terminal_order(best_candidate)
                best_score = float(best_candidate.probability)
                best_action = best_candidate.action
                feature_rows.append(features)
                mask_rows.append(controlled_mask.astype(np.bool_, copy=True))
                base_actions.append(base_action)
                best_actions.append(best_action)
                candidate_action_rows.append(candidate_actions)
                candidate_score_rows.append(candidate_scores)
                candidate_valid_rows.append(candidate_context.valid)
                candidate_kind_rows.append(candidate_context.kinds)
                candidate_card_id_rows.append(candidate_context.card_ids)
                candidate_card_feature_rows.append(candidate_context.card_features)
                candidate_tile_feature_rows.append(candidate_context.tile_features)
                candidate_policy_logit_rows.append(candidate_context.policy_logits)
                candidate_policy_log_probability_rows.append(
                    candidate_context.policy_log_probabilities
                )
                candidate_policy_type_log_probability_rows.append(
                    candidate_context.policy_type_log_probabilities
                )
                candidate_crown_difference_rows.append(candidate_crown_differences)
                candidate_tower_damage_difference_rows.append(
                    candidate_tower_damage_differences
                )
                candidate_terminal_tick_rows.append(candidate_terminal_ticks)
                hand_id_rows.append(hand_ids)
                if args.include_structured_state:
                    observation = env.get_structured_observation(controlled_player)
                    structured_entity_id_rows.append(
                        observation.entity_ids.astype(np.int64, copy=True)
                    )
                    structured_entity_feature_rows.append(
                        observation.entity_features.astype(np.float32, copy=True)
                    )
                    structured_entity_mask_rows.append(
                        observation.entity_mask.astype(np.bool_, copy=True)
                    )
                    structured_hand_id_rows.append(
                        observation.hand_ids.astype(np.int64, copy=True)
                    )
                    structured_global_feature_rows.append(
                        observation.global_features.astype(np.float32, copy=True)
                    )
                    structured_opponent_history_id_rows.append(
                        observation.opponent_history_ids.astype(np.int64, copy=True)
                    )
                    structured_opponent_history_age_rows.append(
                        observation.opponent_history_ages.astype(np.float32, copy=True)
                    )
                    structured_opponent_seen_card_id_rows.append(
                        observation.opponent_seen_card_ids.astype(np.int64, copy=True)
                    )
                    structured_previous_action_rows.append(
                        int(previous_actions[controlled_player])
                    )
                    structured_previous_reward_rows.append(
                        float(previous_rewards[controlled_player])
                    )
                    structured_episode_start_rows.append(bool(episode_start))
                    if args.include_action_time_recurrent_state:
                        recurrent = snapshot_action_time_recurrent_state(
                            next_states[controlled_player],
                            expected_memory_size=loaded.model.config.memory_size,
                        )
                        structured_recurrent_cell_rows.append(recurrent.cell)
                        structured_previous_play_hazard_rows.append(
                            recurrent.previous_play_hazard
                        )
                game_ids.append(game)
                tick_rows.append(int(env.battle.tick))
                audit_rows.append(
                    {
                        "game": game,
                        "seed": game_seed,
                        "strategy": strategy_name,
                        "controlled_player": controlled_player,
                        "tick": int(env.battle.tick),
                        "base": _describe_action(env, controlled_player, base_action),
                        "base_score": exact.base_probability,
                        "best": _describe_action(env, controlled_player, best_action),
                        "best_score": best_score,
                        "decisive_improvement": best_order > base_order,
                        "candidates": [
                            {
                                **_describe_action(
                                    env,
                                    controlled_player,
                                    candidate.action,
                                ),
                                "terminal_score": candidate.probability,
                                "crown_difference": candidate.crown_difference,
                                "tower_damage_difference": (
                                    candidate.tower_damage_difference
                                ),
                                "terminal_tick": candidate.terminal_tick,
                            }
                            for candidate in exact.candidates
                        ],
                    }
                )
                collected += 1
                print(
                    f"game={game} strategy={strategy_name} seat={controlled_player} "
                    f"tick={env.battle.tick} base={exact.base_probability:.1f} "
                    f"best={best_score:.1f} improved={int(best_score > exact.base_probability)}",
                    flush=True,
                )
            policy_actions[opponent] = opponent_selector(
                env,
                opponent,
                masks[opponent],
            )
            rewards, done, _ = env.step(policy_actions, pre_action_masks=masks)
            states = next_states
            previous_actions = policy_actions
            previous_rewards = {
                player: float(rewards[player]) for player in (0, 1)
            }
            episode_start = False
            decision_index += 1
        game_rows.append(
            {
                "game": game,
                "seed": game_seed,
                "strategy": strategy_name,
                "controlled_player": controlled_player,
                "decks": decks,
                "states_collected": collected,
                "winner": env.battle.winner,
                "ticks": int(env.battle.tick),
            }
        )

    arrays = {
        "features": (
            np.stack(feature_rows).astype(np.float32, copy=False)
            if feature_rows
            else np.empty(
                (0, loaded.model.config.d_model + loaded.model.config.memory_size),
                dtype=np.float32,
            )
        ),
        "action_masks": (
            np.stack(mask_rows).astype(np.bool_, copy=False)
            if mask_rows
            else np.empty((0, loaded.model.num_actions), dtype=np.bool_)
        ),
        "base_actions": np.asarray(base_actions, dtype=np.int64),
        "best_actions": np.asarray(best_actions, dtype=np.int64),
        "candidate_actions": (
            np.stack(candidate_action_rows)
            if candidate_action_rows
            else np.empty((0, args.max_candidates), dtype=np.int64)
        ),
        "candidate_scores": (
            np.stack(candidate_score_rows)
            if candidate_score_rows
            else np.empty((0, args.max_candidates), dtype=np.float32)
        ),
        "candidate_valid": (
            np.stack(candidate_valid_rows)
            if candidate_valid_rows
            else np.empty((0, args.max_candidates), dtype=np.bool_)
        ),
        "candidate_kinds": (
            np.stack(candidate_kind_rows)
            if candidate_kind_rows
            else np.empty((0, args.max_candidates), dtype=np.int8)
        ),
        "candidate_card_ids": (
            np.stack(candidate_card_id_rows)
            if candidate_card_id_rows
            else np.empty((0, args.max_candidates), dtype=np.int64)
        ),
        "candidate_card_features": (
            np.stack(candidate_card_feature_rows)
            if candidate_card_feature_rows
            else np.empty(
                (0, args.max_candidates, semantic_builder.card_stat_features.shape[1]),
                dtype=np.float32,
            )
        ),
        "candidate_tile_features": (
            np.stack(candidate_tile_feature_rows)
            if candidate_tile_feature_rows
            else np.empty(
                (0, args.max_candidates, canonical_tile_features.shape[1]),
                dtype=np.float32,
            )
        ),
        "candidate_policy_logits": (
            np.stack(candidate_policy_logit_rows)
            if candidate_policy_logit_rows
            else np.empty((0, args.max_candidates), dtype=np.float32)
        ),
        "candidate_policy_log_probabilities": (
            np.stack(candidate_policy_log_probability_rows)
            if candidate_policy_log_probability_rows
            else np.empty((0, args.max_candidates), dtype=np.float32)
        ),
        "candidate_policy_type_log_probabilities": (
            np.stack(candidate_policy_type_log_probability_rows)
            if candidate_policy_type_log_probability_rows
            else np.empty((0, args.max_candidates), dtype=np.float32)
        ),
        "candidate_crown_differences": (
            np.stack(candidate_crown_difference_rows)
            if candidate_crown_difference_rows
            else np.empty((0, args.max_candidates), dtype=np.int8)
        ),
        "candidate_tower_damage_differences": (
            np.stack(candidate_tower_damage_difference_rows)
            if candidate_tower_damage_difference_rows
            else np.empty((0, args.max_candidates), dtype=np.float32)
        ),
        "candidate_terminal_ticks": (
            np.stack(candidate_terminal_tick_rows)
            if candidate_terminal_tick_rows
            else np.empty((0, args.max_candidates), dtype=np.int32)
        ),
        "hand_ids": (
            np.stack(hand_id_rows)
            if hand_id_rows
            else np.empty((0, 4), dtype=np.int64)
        ),
        "game_ids": np.asarray(game_ids, dtype=np.int64),
        "ticks": np.asarray(tick_rows, dtype=np.int64),
    }
    if args.include_structured_state:
        spec = semantic_builder.spec
        arrays.update(
            {
                "structured_entity_ids": (
                    np.stack(structured_entity_id_rows)
                    if structured_entity_id_rows
                    else np.empty((0, spec.max_entities), dtype=np.int64)
                ),
                "structured_entity_features": (
                    np.stack(structured_entity_feature_rows)
                    if structured_entity_feature_rows
                    else np.empty(
                        (0, spec.max_entities, spec.entity_feature_size),
                        dtype=np.float32,
                    )
                ),
                "structured_entity_mask": (
                    np.stack(structured_entity_mask_rows)
                    if structured_entity_mask_rows
                    else np.empty((0, spec.max_entities), dtype=np.bool_)
                ),
                "structured_hand_ids": (
                    np.stack(structured_hand_id_rows)
                    if structured_hand_id_rows
                    else np.empty((0, 5), dtype=np.int64)
                ),
                "structured_global_features": (
                    np.stack(structured_global_feature_rows)
                    if structured_global_feature_rows
                    else np.empty((0, spec.actor_global_size), dtype=np.float32)
                ),
                "structured_opponent_history_ids": (
                    np.stack(structured_opponent_history_id_rows)
                    if structured_opponent_history_id_rows
                    else np.empty((0, spec.public_history_slots), dtype=np.int64)
                ),
                "structured_opponent_history_ages": (
                    np.stack(structured_opponent_history_age_rows)
                    if structured_opponent_history_age_rows
                    else np.empty((0, spec.public_history_slots), dtype=np.float32)
                ),
                "structured_opponent_seen_card_ids": (
                    np.stack(structured_opponent_seen_card_id_rows)
                    if structured_opponent_seen_card_id_rows
                    else np.empty((0, spec.public_seen_card_slots), dtype=np.int64)
                ),
                "structured_previous_actions": np.asarray(
                    structured_previous_action_rows, dtype=np.int64
                ),
                "structured_previous_rewards": np.asarray(
                    structured_previous_reward_rows, dtype=np.float32
                ),
                "structured_episode_starts": np.asarray(
                    structured_episode_start_rows, dtype=np.bool_
                ),
            }
        )
        if args.include_action_time_recurrent_state:
            arrays.update(
                {
                    "structured_recurrent_cell": (
                        np.stack(structured_recurrent_cell_rows)
                        if structured_recurrent_cell_rows
                        else np.empty(
                            (0, loaded.model.config.memory_size),
                            dtype=np.float32,
                        )
                    ),
                    "structured_previous_play_hazard": (
                        np.stack(structured_previous_play_hazard_rows)
                        if structured_previous_play_hazard_rows
                        else np.empty((0, 1), dtype=np.float32)
                    ),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        np.savez_compressed(handle, **arrays)  # type: ignore[arg-type]
    report = {
        "schema_version": 2,
        "candidate_card_semantics_version": 3,
        "candidate_card_feature_size": int(
            semantic_builder.card_stat_features.shape[1]
        ),
        "best_action_order": "outcome-crowns-tower-damage-v1",
        "policy": str(args.policy.resolve()),
        "outcome": None if args.outcome is None else str(args.outcome.resolve()),
        "sampling_decks_path": (
            None
            if args.sampling_decks_path is None
            else str(args.sampling_decks_path.resolve())
        ),
        "learner_sampling_decks_path": (
            None
            if args.learner_sampling_decks_path is None
            else str(args.learner_sampling_decks_path.resolve())
        ),
        "opponent_sampling_decks_path": (
            None
            if args.opponent_sampling_decks_path is None
            else str(args.opponent_sampling_decks_path.resolve())
        ),
        "input_sha256": {
            "policy": _file_sha256(args.policy),
            "decks": _file_sha256(args.decks_path),
            "outcome": (
                None if args.outcome is None else _file_sha256(args.outcome)
            ),
            "sampling_decks": (
                None
                if args.sampling_decks_path is None
                else _file_sha256(args.sampling_decks_path)
            ),
            "learner_sampling_decks": (
                None
                if args.learner_sampling_decks_path is None
                else _file_sha256(args.learner_sampling_decks_path)
            ),
            "opponent_sampling_decks": (
                None
                if args.opponent_sampling_decks_path is None
                else _file_sha256(args.opponent_sampling_decks_path)
            ),
        },
        "collection_config": {
            "decision_interval": args.decision_interval,
            "max_ticks": args.max_ticks,
            "overtime_start_tick": args.overtime_start_tick,
            "max_candidates": args.max_candidates,
            "locations_per_slot": args.locations_per_slot,
            "spatially_diverse_locations": args.spatially_diverse_locations,
            "minimum_tick": args.minimum_tick,
            "query_stride": args.query_stride,
            "states_per_game": args.states_per_game,
            "device": args.device,
            "engine_fast_path": "on",
        },
        "locations_per_slot": args.locations_per_slot,
        "spatially_diverse_locations": args.spatially_diverse_locations,
        "structured_state_contract": (
            "public-actor-v2-action-time-recurrence"
            if args.include_action_time_recurrent_state
            else "public-actor-v1"
            if args.include_structured_state
            else None
        ),
        "query_schedule": args.query_schedule,
        "query_target_ticks": list(phase_target_ticks),
        "seed": args.seed,
        "required_candidate_cards": sorted(args.required_candidate_card),
        "games_requested": args.games,
        "game_offset": args.game_offset,
        "states_requested": args.games * args.states_per_game,
        "states_collected": len(feature_rows),
        "decisive_improvements": sum(
            bool(row["decisive_improvement"]) for row in audit_rows
        ),
        "base_terminal_wins": sum(float(row["base_score"]) == 1.0 for row in audit_rows),
        "array_shapes": {name: list(array.shape) for name, array in arrays.items()},
        "array_sha256": {name: _array_sha256(array) for name, array in arrays.items()},
        "output": str(args.output.resolve()),
        "games": game_rows,
        "states": audit_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "states_collected",
                    "decisive_improvements",
                    "base_terminal_wins",
                    "array_sha256",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
