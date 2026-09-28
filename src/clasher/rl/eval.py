from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path

from .action_space import DiscreteTileActionSpace
from .common import NUM_TILES
from .deck_pool import DeckPool, load_deck_pool, sample_decks
from .location_lookahead import LocationLookahead
from .model import ClasherPolicy, PolicyConfig, PolicyOutput
from .reward_model import (
    OBJECTIVE_V1,
    REWARD_PROFILES,
    DefenseOutcomeTracker,
    incoming_tower_danger,
    potential_breakdown_p0,
)
from .selfplay_env import SelfPlayBattleEnv
from .strategy_bots import STRATEGY_NAMES, StrategyBot
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        public_history_slots=config.public_history_slots,
        public_seen_card_slots=config.public_seen_card_slots,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    return LoadedPolicy(model=model, builder=builder, checkpoint=state)


@torch.no_grad()
def _policy_step(
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
) -> tuple[
    int,
    tuple[torch.Tensor, torch.Tensor],
    np.ndarray,
    PolicyOutput,
]:
    assert env.battle is not None
    actor_observation_domain = loaded.model.config.actor_observation_domain
    observation = env.get_structured_observation(
        player_id,
        actor_observation_domain=actor_observation_domain,
    )
    mask = env.get_action_mask(
        player_id,
        actor_observation_domain=actor_observation_domain,
        structured_observation=observation,
    )[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([previous_action], dtype=np.int64),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start], dtype=np.bool_),
        device,
        public_observation_confidence=(
            loaded.model.config.public_observation_confidence
        ),
    )
    action, _, _, next_state, output = loaded.model.act(
        inputs, state, deterministic=deterministic
    )
    return int(action[0, 0].item()), next_state, mask[0], output


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
    action, next_state, mask, _ = _policy_step(
        loaded,
        env,
        player_id,
        state=state,
        previous_action=previous_action,
        previous_reward=previous_reward,
        episode_start=episode_start,
        deterministic=deterministic,
        device=device,
    )
    return action, next_state, mask


def _make_evaluation_envs(
    *,
    candidate: LoadedPolicy,
    decks_path: Path,
    sampling_decks_path: Path | None,
    candidate_sampling_decks_path: Path | None,
    opponent_sampling_decks_path: Path | None,
    decision_interval: int,
    max_ticks: int,
    seed: int,
    mirror_match: bool,
    reward_profile: str,
) -> dict[int, SelfPlayBattleEnv]:
    asymmetric_decks = (
        candidate_sampling_decks_path is not None
        or opponent_sampling_decks_path is not None
    )
    if asymmetric_decks and mirror_match:
        raise ValueError("asymmetric deck pools are incompatible with mirror_match")
    candidate_pool = candidate_sampling_decks_path or sampling_decks_path
    other_pool = opponent_sampling_decks_path or sampling_decks_path
    envs: dict[int, SelfPlayBattleEnv] = {}
    for candidate_player in ((0, 1) if asymmetric_decks else (0,)):
        player_pools = (
            (candidate_pool, other_pool)
            if candidate_player == 0
            else (other_pool, candidate_pool)
        )
        envs[candidate_player] = SelfPlayBattleEnv(
            decision_interval_ticks=decision_interval,
            max_ticks=max_ticks,
            decks_path=decks_path,
            sampling_decks_path=sampling_decks_path,
            player0_sampling_decks_path=(
                player_pools[0] if asymmetric_decks else None
            ),
            player1_sampling_decks_path=(
                player_pools[1] if asymmetric_decks else None
            ),
            learner_player_id=candidate_player,
            seed=seed,
            mirror_match=mirror_match,
            canonical_perspective=True,
            canonical_lane_globals=candidate.model.config.canonical_lane_globals,
            reward_profile=reward_profile,
        )
    if not asymmetric_decks:
        envs[1] = envs[0]
    return envs


def _sample_paired_ordered_decks(
    candidate_pool: DeckPool,
    opponent_pool: DeckPool,
    *,
    matchup_seed: int,
) -> tuple[list[str], list[str]]:
    """Sample and shuffle one logical matchup independently of physical seat."""
    deck_rng = random.Random(matchup_seed + 7_919)
    candidate_deck, _ = sample_decks(
        candidate_pool,
        rng=deck_rng,
        mirror_match=True,
    )
    opponent_deck, _ = sample_decks(
        opponent_pool,
        rng=deck_rng,
        mirror_match=True,
    )
    deck_rng.shuffle(candidate_deck)
    deck_rng.shuffle(opponent_deck)
    return candidate_deck, opponent_deck


def evaluate(
    *,
    candidate: LoadedPolicy,
    decks_path: Path,
    games: int,
    seed: int,
    decision_interval: int,
    max_ticks: int,
    opponent_mode: str,
    opponent: LoadedPolicy | None,
    deterministic: bool,
    quiet_engine: bool,
    device: torch.device,
    sampling_decks_path: Path | None = None,
    candidate_sampling_decks_path: Path | None = None,
    opponent_sampling_decks_path: Path | None = None,
    mirror_match: bool = False,
    reward_profile: str = OBJECTIVE_V1,
    opponent_bot: StrategyBot | None = None,
    candidate_defense_bot: StrategyBot | None = None,
    candidate_defense_threshold: float = 0.025,
    candidate_defense_require_lead: bool = False,
    candidate_location_lookahead: LocationLookahead | None = None,
    game_records: list[dict[str, Any]] | None = None,
    decision_trace_records: list[dict[str, Any]] | None = None,
    decision_trace_games: set[int] | None = None,
) -> dict[str, float]:
    if games <= 0:
        raise ValueError("games must be positive")
    if opponent_mode not in {"noop", "random", "policy", "strategy"}:
        raise ValueError(f"unknown evaluation opponent mode: {opponent_mode}")
    if (opponent_mode == "policy") != (opponent is not None):
        raise ValueError("policy opponent mode and checkpoint must accompany each other")
    if (opponent_mode == "strategy") != (opponent_bot is not None):
        raise ValueError("strategy opponent mode and bot must accompany each other")
    torch.manual_seed(seed)
    np.random.seed(seed)
    envs = _make_evaluation_envs(
        candidate=candidate,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks_path,
        candidate_sampling_decks_path=candidate_sampling_decks_path,
        opponent_sampling_decks_path=opponent_sampling_decks_path,
        decision_interval=decision_interval,
        max_ticks=max_ticks,
        seed=seed,
        mirror_match=mirror_match,
        reward_profile=reward_profile,
    )
    asymmetric_decks = (
        candidate_sampling_decks_path is not None
        or opponent_sampling_decks_path is not None
    )
    paired_deck_pools = (
        (
            load_deck_pool(
                candidate_sampling_decks_path
                or sampling_decks_path
                or decks_path
            ),
            load_deck_pool(
                opponent_sampling_decks_path
                or sampling_decks_path
                or decks_path
            ),
        )
        if asymmetric_decks
        else None
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
    threatened_decisions = 0
    defensive_responses = 0
    defense_events_started = 0
    defense_events_resolved = 0
    defense_events_successful = 0
    defense_event_outcome_sum = 0.0
    candidate_defense_overrides = 0
    candidate_location_lookahead_decisions = 0
    candidate_location_lookahead_overrides = 0
    incoming_danger_sum = 0.0
    incoming_danger_peak = 0.0
    board_value_sum = 0.0
    start_time = time.perf_counter()

    for game in range(games):
        matchup = game // 2
        matchup_seed = seed + matchup * 1009
        candidate_player = game % 2
        env = envs[candidate_player]
        ordered_decks = None
        if paired_deck_pools is not None:
            candidate_deck, opponent_deck = _sample_paired_ordered_decks(
                *paired_deck_pools,
                matchup_seed=matchup_seed,
            )
            ordered_decks = (
                (candidate_deck, opponent_deck)
                if candidate_player == 0
                else (opponent_deck, candidate_deck)
            )
        with maybe_silence_stdio(quiet_engine):
            env.reset(seed=matchup_seed, ordered_decks=ordered_decks)
        rng = np.random.default_rng(matchup_seed + 91_117)
        torch.manual_seed(matchup_seed + 271_828)
        other_player = 1 - candidate_player
        candidate_state = candidate.model.initial_state(1, device=device)
        opponent_state = (
            opponent.model.initial_state(1, device=device)
            if opponent is not None
            else None
        )
        candidate_previous_action = env.action_space.no_op_action
        opponent_previous_action = env.action_space.no_op_action
        candidate_previous_reward = 0.0
        opponent_previous_reward = 0.0
        episode_start = True
        done = False
        game_decision = 0
        defense_tracker = DefenseOutcomeTracker(reward_scale=1.0)

        def record_defense_update(
            *,
            done_now: bool,
            tracker: DefenseOutcomeTracker = defense_tracker,
            player_id: int = candidate_player,
            battle_env: SelfPlayBattleEnv = env,
        ) -> None:
            nonlocal defense_events_started, defense_events_resolved
            nonlocal defense_events_successful, defense_event_outcome_sum
            assert battle_env.battle is not None
            update = tracker.advance(battle_env.battle, done=done_now)
            outcome = float(update.player_rewards[player_id])
            defense_events_started += int(update.started[player_id])
            defense_events_resolved += int(update.resolved[player_id])
            defense_events_successful += int(
                update.resolved[player_id] and outcome > 0.0
            )
            defense_event_outcome_sum += outcome

        while not done:
            record_defense_update(done_now=False)
            candidate_action, candidate_state, candidate_mask, candidate_output = (
                _policy_step(
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
            )
            assert env.battle is not None
            if candidate_location_lookahead is not None:
                lookahead_result = candidate_location_lookahead.select_action(
                    env.battle,
                    candidate_player,
                    base_action=candidate_action,
                    location_logits=(
                        candidate_output.location_logits[0, 0].detach().cpu().numpy()
                    ),
                    action_mask=candidate_mask,
                )
                candidate_location_lookahead_decisions += int(
                    lookahead_result.candidates > 1
                )
                candidate_location_lookahead_overrides += int(
                    lookahead_result.overridden
                )
                candidate_action = lookahead_result.action
            breakdown = potential_breakdown_p0(env.battle)
            incoming_danger = incoming_tower_danger(env.battle, candidate_player)
            candidate_board_value = (
                breakdown.board_value
                if candidate_player == 0
                else -breakdown.board_value
            )
            incoming_danger_sum += incoming_danger
            incoming_danger_peak = max(incoming_danger_peak, incoming_danger)
            board_value_sum += candidate_board_value
            if (
                candidate_defense_bot is not None
                and incoming_danger >= candidate_defense_threshold
                and (
                    not candidate_defense_require_lead
                    or env.battle.get_crown_count(candidate_player)
                    > env.battle.get_crown_count(other_player)
                )
            ):
                override_action = candidate_defense_bot.select_action(
                    env,
                    candidate_player,
                    action_mask=candidate_mask,
                )
                candidate_defense_overrides += int(override_action != candidate_action)
                candidate_action = override_action
            if incoming_danger >= 0.025:
                threatened_decisions += 1
                defensive_responses += int(
                    candidate_action != env.action_space.no_op_action
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
            elif opponent_mode == "strategy":
                if opponent_bot is None:
                    raise ValueError("strategy opponent requires a strategy bot")
                other_mask = env.get_action_mask(other_player)
                other_action = opponent_bot.select_action(
                    env,
                    other_player,
                    action_mask=other_mask,
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
            if decision_trace_records is not None and (
                not decision_trace_games or game in decision_trace_games
            ):
                selection = env.action_space.decode_action(
                    candidate_action, candidate_player
                )
                candidate_player_state = env.battle.players[candidate_player]
                opponent_player_state = env.battle.players[other_player]
                chosen_location_logit = None
                if candidate_action < env.action_space.no_op_action:
                    slot = candidate_action // NUM_TILES
                    tile = candidate_action % NUM_TILES
                    chosen_location_logit = float(
                        candidate_output.location_logits[0, 0, slot, tile].item()
                    )
                joint_probabilities = candidate_output.distribution().probs[0, 0]
                placement_probabilities = joint_probabilities[
                    : env.action_space.no_op_action
                ].reshape(4, NUM_TILES)
                action_type_probabilities = torch.cat(
                    [
                        placement_probabilities.sum(dim=-1),
                        joint_probabilities[env.action_space.no_op_action :],
                    ]
                )
                decision_trace_records.append(
                    {
                        "game": game,
                        "game_decision": game_decision,
                        "matchup": matchup,
                        "matchup_seed": matchup_seed,
                        "candidate_player": candidate_player,
                        "tick": int(env.battle.tick),
                        "candidate_action": candidate_action,
                        "opponent_action": other_action,
                        "slot": selection.slot,
                        "position": (
                            None
                            if selection.position is None
                            else [
                                float(selection.position.x),
                                float(selection.position.y),
                            ]
                        ),
                        "is_no_op": selection.is_no_op,
                        "is_ability": selection.is_ability,
                        "action_type_logits": [
                            float(value)
                            for value in candidate_output.action_type_logits[
                                0, 0
                            ].tolist()
                        ],
                        # Exact marginalized probabilities after legal-action
                        # masking. Raw type logits alone cannot distinguish an
                        # unaffordable card from a learned refusal to play it.
                        "action_type_probabilities": [
                            float(value)
                            for value in action_type_probabilities.tolist()
                        ],
                        "predicted_value": float(candidate_output.values[0, 0]),
                        "chosen_location_logit": chosen_location_logit,
                        "legal_action_count": int(np.count_nonzero(candidate_mask)),
                        "previous_action": candidate_previous_action,
                        "previous_reward": candidate_previous_reward,
                        "hand": list(candidate_player_state.hand),
                        "elixir": float(candidate_player_state.elixir),
                        "incoming_tower_danger": incoming_danger,
                        "board_value": candidate_board_value,
                        "candidate_tower_hp": [
                            float(candidate_player_state.left_tower_hp),
                            float(candidate_player_state.right_tower_hp),
                            float(candidate_player_state.king_tower_hp),
                        ],
                        "opponent_tower_hp": [
                            float(opponent_player_state.left_tower_hp),
                            float(opponent_player_state.right_tower_hp),
                            float(opponent_player_state.king_tower_hp),
                        ],
                        "alive_entities": sum(
                            int(entity.is_alive)
                            for entity in env.battle.entities.values()
                        ),
                    }
                )
            with maybe_silence_stdio(quiet_engine):
                rewards, done, _ = env.step(
                    {candidate_player: candidate_action, other_player: other_action},
                    pre_action_masks={
                        candidate_player: candidate_mask,
                        other_player: other_mask,
                    },
                )
            record_defense_update(done_now=done)
            candidate_previous_action = candidate_action
            opponent_previous_action = other_action
            candidate_previous_reward = float(rewards[candidate_player])
            opponent_previous_reward = float(rewards[other_player])
            episode_start = False
            game_decision += 1
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
        candidate_crown_count = env.battle.get_crown_count(candidate_player)
        opponent_crown_count = env.battle.get_crown_count(other_player)
        ticks += env.battle.tick
        candidate_crowns += candidate_crown_count
        opponent_crowns += opponent_crown_count
        if env.battle.winner is None:
            draws += 1
            outcome = "draw"
        elif env.battle.winner == candidate_player:
            wins += 1
            wins_as_player0 += int(candidate_player == 0)
            wins_as_player1 += int(candidate_player == 1)
            outcome = "win"
        else:
            losses += 1
            outcome = "loss"
        if game_records is not None:
            candidate_state_at_end = env.battle.players[candidate_player]
            opponent_state_at_end = env.battle.players[other_player]
            game_records.append(
                {
                    "game": game,
                    "matchup": matchup,
                    "matchup_seed": matchup_seed,
                    "candidate_player": candidate_player,
                    "outcome": outcome,
                    "candidate_crowns": candidate_crown_count,
                    "opponent_crowns": opponent_crown_count,
                    "ticks": env.battle.tick,
                    "candidate_deck": list(candidate_state_at_end.deck),
                    "opponent_deck": list(opponent_state_at_end.deck),
                    "candidate_tower_hp": [
                        float(candidate_state_at_end.left_tower_hp),
                        float(candidate_state_at_end.right_tower_hp),
                        float(candidate_state_at_end.king_tower_hp),
                    ],
                    "opponent_tower_hp": [
                        float(opponent_state_at_end.left_tower_hp),
                        float(opponent_state_at_end.right_tower_hp),
                        float(opponent_state_at_end.king_tower_hp),
                    ],
                }
            )

    elapsed = time.perf_counter() - start_time
    score = (wins + 0.5 * draws) / games
    standard_error = float(np.sqrt(max(0.0, score * (1.0 - score) / games)))
    metrics = {
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
        "incoming_tower_danger_mean": incoming_danger_sum / max(1, actions),
        "incoming_tower_danger_peak": incoming_danger_peak,
        "board_value_edge_mean": board_value_sum / max(1, actions),
        "threatened_decisions": float(threatened_decisions),
        "defensive_action_rate_when_threatened": defensive_responses
        / max(1, threatened_decisions),
        "defense_events_started": float(defense_events_started),
        "defense_events_resolved": float(defense_events_resolved),
        "defense_event_success_rate": defense_events_successful
        / max(1, defense_events_resolved),
        "defense_event_mean_outcome": defense_event_outcome_sum
        / max(1, defense_events_resolved),
        "candidate_defense_override_rate": candidate_defense_overrides
        / max(1, actions),
        "candidate_location_lookahead_rate": candidate_location_lookahead_decisions
        / max(1, actions),
        "candidate_location_lookahead_override_rate": (
            candidate_location_lookahead_overrides / max(1, actions)
        ),
        "elapsed_seconds": elapsed,
        "games_per_minute": games * 60.0 / max(1e-9, elapsed),
    }
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a V2 recurrent Clasher policy"
    )
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    parser.add_argument(
        "--opponent",
        choices=["random", "noop", "strategy", "policy"],
        default="random",
    )
    parser.add_argument("--opponent-strategy", choices=STRATEGY_NAMES, default=None)
    parser.add_argument("--opponent-checkpoint", default=None)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--sampling-decks-path",
        default=None,
        help=(
            "optional evaluation-only deck pool; --decks-path remains the full "
            "checkpoint observation vocabulary"
        ),
    )
    parser.add_argument(
        "--candidate-sampling-decks-path",
        default=None,
        help=(
            "optional candidate-only deck pool; use with an opponent pool to "
            "evaluate a fixed-deck specialist against diverse matchups"
        ),
    )
    parser.add_argument(
        "--opponent-sampling-decks-path",
        default=None,
        help="optional opponent-only deck pool for asymmetric evaluation",
    )
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument(
        "--mirror-match",
        action="store_true",
        help="give both players the same sampled deck to isolate seat effects",
    )
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=OBJECTIVE_V1
    )
    parser.add_argument(
        "--candidate-defense-strategy",
        choices=STRATEGY_NAMES,
        default=None,
        help="experimental public-info action override under incoming danger",
    )
    parser.add_argument(
        "--candidate-defense-threshold",
        type=float,
        default=0.025,
        help="tower-danger threshold for --candidate-defense-strategy",
    )
    parser.add_argument(
        "--candidate-defense-require-lead",
        action="store_true",
        help="apply the experimental defense override only while ahead in crowns",
    )
    parser.add_argument("--location-lookahead-top-k", type=int, default=0)
    parser.add_argument("--location-lookahead-horizon", type=int, default=96)
    parser.add_argument("--location-lookahead-prior-weight", type=float, default=0.02)
    parser.add_argument("--location-lookahead-min-value-gain", type=float, default=0.0)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--games-json-out", default=None)
    parser.add_argument("--decisions-json-out", default=None)
    parser.add_argument(
        "--decision-trace-game",
        action="append",
        type=int,
        default=None,
        help="zero-based game index to include in --decisions-json-out; repeatable",
    )
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    parser.add_argument(
        "--quiet-engine", dest="quiet_engine", action="store_true", default=True
    )
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.torch_threads <= 0:
        raise ValueError("torch threads must be positive")
    torch.set_num_threads(args.torch_threads)
    device = resolve_torch_device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    sampling_decks_path = (
        resolve_decks_path(args.sampling_decks_path, must_exist=True)
        if args.sampling_decks_path is not None
        else None
    )
    candidate_sampling_decks_path = (
        resolve_decks_path(args.candidate_sampling_decks_path, must_exist=True)
        if args.candidate_sampling_decks_path is not None
        else None
    )
    opponent_sampling_decks_path = (
        resolve_decks_path(args.opponent_sampling_decks_path, must_exist=True)
        if args.opponent_sampling_decks_path is not None
        else None
    )
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
    opponent: LoadedPolicy | None = None
    if args.opponent == "policy":
        if not args.opponent_checkpoint:
            raise ValueError("--opponent-checkpoint is required for a policy opponent")
        opponent_path = resolve_path(args.opponent_checkpoint, must_exist=True)
        opponent = load_policy_checkpoint(
            opponent_path, device=device, decks_path=decks_path
        )
        print(f"opponent_checkpoint={opponent_path}")
    if args.opponent == "strategy" and not args.opponent_strategy:
        raise ValueError("--opponent-strategy is required for a strategy opponent")
    if args.opponent != "strategy" and args.opponent_strategy:
        raise ValueError("--opponent-strategy requires --opponent strategy")
    print(f"device={device}")
    print(f"checkpoint={checkpoint_path}")
    print(f"checkpoint_update={candidate.checkpoint.get('update', 0)}")
    print(f"checkpoint_transitions={candidate.checkpoint.get('total_transitions', 0)}")
    game_records: list[dict[str, Any]] | None = [] if args.games_json_out else None
    if args.decision_trace_game and not args.decisions_json_out:
        raise ValueError("--decision-trace-game requires --decisions-json-out")
    trace_games = set(args.decision_trace_game or [])
    if any(game < 0 or game >= args.games for game in trace_games):
        raise ValueError("--decision-trace-game must identify a requested game")
    decision_trace_records: list[dict[str, Any]] | None = (
        [] if args.decisions_json_out else None
    )
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
        sampling_decks_path=sampling_decks_path,
        candidate_sampling_decks_path=candidate_sampling_decks_path,
        opponent_sampling_decks_path=opponent_sampling_decks_path,
        mirror_match=args.mirror_match,
        reward_profile=args.reward_profile,
        opponent_bot=(
            StrategyBot(args.opponent_strategy)
            if args.opponent_strategy is not None
            else None
        ),
        candidate_defense_bot=(
            StrategyBot(args.candidate_defense_strategy)
            if args.candidate_defense_strategy is not None
            else None
        ),
        candidate_defense_threshold=args.candidate_defense_threshold,
        candidate_defense_require_lead=args.candidate_defense_require_lead,
        candidate_location_lookahead=(
            LocationLookahead(
                DiscreteTileActionSpace(canonical_perspective=True),
                top_k=args.location_lookahead_top_k,
                horizon_ticks=args.location_lookahead_horizon,
                prior_weight=args.location_lookahead_prior_weight,
                min_value_gain=args.location_lookahead_min_value_gain,
                reward_profile=args.reward_profile,
            )
            if args.location_lookahead_top_k > 0
            else None
        ),
        game_records=game_records,
        decision_trace_records=decision_trace_records,
        decision_trace_games=trace_games,
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
    print(
        f"incoming_danger_mean={metrics['incoming_tower_danger_mean']:.4f} "
        f"incoming_danger_peak={metrics['incoming_tower_danger_peak']:.4f} "
        f"defensive_action_rate={metrics['defensive_action_rate_when_threatened']:.3f} "
        f"board_value_edge_mean={metrics['board_value_edge_mean']:+.4f}"
    )
    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "checkpoint": str(checkpoint_path),
            "checkpoint_sha256": _file_sha256(checkpoint_path),
            "checkpoint_update": int(candidate.checkpoint.get("update", 0)),
            "opponent_mode": args.opponent,
            "opponent_checkpoint": (
                str(resolve_path(args.opponent_checkpoint, must_exist=True))
                if args.opponent_checkpoint
                else None
            ),
            "opponent_checkpoint_sha256": (
                _file_sha256(resolve_path(args.opponent_checkpoint, must_exist=True))
                if args.opponent_checkpoint
                else None
            ),
            "opponent_strategy": args.opponent_strategy,
            "reward_profile": args.reward_profile,
            "sampling_decks_path": (
                str(sampling_decks_path) if sampling_decks_path is not None else None
            ),
            "sampling_decks_sha256": (
                _file_sha256(sampling_decks_path)
                if sampling_decks_path is not None
                else None
            ),
            "candidate_sampling_decks_path": (
                str(candidate_sampling_decks_path)
                if candidate_sampling_decks_path is not None
                else None
            ),
            "candidate_sampling_decks_sha256": (
                _file_sha256(candidate_sampling_decks_path)
                if candidate_sampling_decks_path is not None
                else None
            ),
            "opponent_sampling_decks_path": (
                str(opponent_sampling_decks_path)
                if opponent_sampling_decks_path is not None
                else None
            ),
            "opponent_sampling_decks_sha256": (
                _file_sha256(opponent_sampling_decks_path)
                if opponent_sampling_decks_path is not None
                else None
            ),
            "mirror_match": args.mirror_match,
            "paired_asymmetric_matchups": bool(
                candidate_sampling_decks_path is not None
                or opponent_sampling_decks_path is not None
            ),
            "seed": args.seed,
            "deterministic": args.deterministic,
            "location_lookahead": (
                {
                    "top_k": args.location_lookahead_top_k,
                    "horizon_ticks": args.location_lookahead_horizon,
                    "prior_weight": args.location_lookahead_prior_weight,
                    "min_value_gain": args.location_lookahead_min_value_gain,
                }
                if args.location_lookahead_top_k > 0
                else None
            ),
            "metrics": metrics,
        }
        out_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"json_out={out_path}")
    if args.games_json_out:
        games_out_path = Path(args.games_json_out).expanduser().resolve()
        games_out_path.parent.mkdir(parents=True, exist_ok=True)
        games_out_path.write_text(
            json.dumps(game_records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"games_json_out={games_out_path}")
    if args.decisions_json_out:
        decisions_out_path = Path(args.decisions_json_out).expanduser().resolve()
        decisions_out_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_out_path.write_text(
            json.dumps(decision_trace_records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"decisions_json_out={decisions_out_path}")


if __name__ == "__main__":
    main()
