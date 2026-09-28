"""Train a public-state outcome value probe from complete native games."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.public_outcome import PublicOutcomeHead
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.train_recurrent import _stack_step_inputs


@dataclass(frozen=True)
class OutcomeCorpus:
    features: np.ndarray
    targets: np.ndarray
    game_ids: np.ndarray
    ticks: np.ndarray
    final_ticks: np.ndarray
    battle_ids: np.ndarray
    players: np.ndarray
    policy_controlled: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _deck_key(cards: list[str]) -> str:
    return "|".join(sorted(cards))


def _opponent_kind(opponent_mode: str, global_game: int) -> str:
    if opponent_mode != "mixed":
        return opponent_mode
    schedule = (*STRATEGY_NAMES, "random", "selfplay")
    return str(schedule[global_game % len(schedule)])


def _learner_player(opponent_mode: str, global_game: int) -> int:
    if opponent_mode != "mixed":
        return global_game % 2
    # Hold each seat for one complete eight-opponent block. Across every two
    # blocks, every opponent type is therefore observed from both seats.
    return (global_game // (len(STRATEGY_NAMES) + 2)) % 2


def validate_deck_splits(paths: dict[str, Path]) -> dict[str, Any]:
    signatures = {
        name: {_deck_key(cards) for cards in load_deck_pool(path)}
        for name, path in paths.items()
    }
    names = tuple(signatures)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = signatures[left] & signatures[right]
            if overlap:
                raise ValueError(f"public outcome deck splits overlap: {left}:{right}")
    return {
        name: {
            "path": str(paths[name].resolve()),
            "sha256": _sha256(paths[name]),
            "deck_count": len(signatures[name]),
        }
        for name in names
    }


@torch.no_grad()
def collect_outcome_corpus(
    *,
    checkpoint: Path,
    decks_path: Path,
    sampling_decks_path: Path,
    games: int,
    seed: int,
    sample_stride: int,
    perspectives: str,
    opponent_mode: str,
    device: torch.device,
    game_offset: int = 0,
) -> tuple[OutcomeCorpus, dict[str, Any]]:
    if games <= 0:
        raise ValueError("public outcome corpus requires positive games")
    if sample_stride <= 0:
        raise ValueError("public outcome sample stride must be positive")
    if perspectives not in {"learner", "both"}:
        raise ValueError("public outcome perspectives must be 'learner' or 'both'")
    if opponent_mode not in {"selfplay", "strategy", "random", "mixed"}:
        raise ValueError(
            "public outcome opponent mode must be selfplay, strategy, random, or mixed"
        )
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks_path,
        seed=seed,
        canonical_perspective=True,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env._structured_obs_builder = loaded.builder
    strategies = STRATEGY_NAMES
    all_features: list[np.ndarray] = []
    all_targets: list[float] = []
    all_game_ids: list[int] = []
    all_ticks: list[int] = []
    all_final_ticks: list[int] = []
    all_battle_ids: list[int] = []
    all_players: list[int] = []
    all_policy_controlled: list[bool] = []
    outcomes = {"win": 0, "draw": 0, "loss": 0}
    learner_outcomes = {"win": 0, "draw": 0, "loss": 0}
    learner_decks: set[str] = set()
    opponent_decks: set[str] = set()
    for game in range(games):
        global_game = game_offset + game
        learner = _learner_player(opponent_mode, global_game)
        opponent = 1 - learner
        opponent_kind = _opponent_kind(opponent_mode, global_game)
        env.reset(seed=seed + global_game * 1009)
        assert env.battle is not None
        bot = (
            StrategyBot(
                opponent_kind
                if opponent_mode == "mixed"
                else strategies[global_game % len(strategies)]
            )
            if opponent_kind in strategies
            else None
        )
        stationary_rng = np.random.default_rng(seed + global_game * 104729 + 17)
        recorded_players = (learner,) if perspectives == "learner" else (0, 1)
        modeled_players = (
            tuple(sorted({*recorded_players, learner, opponent}))
            if opponent_kind == "selfplay"
            else recorded_players
        )
        states = {
            player: loaded.model.initial_state(1, device=device)
            for player in modeled_players
        }
        previous_actions = {
            player: env.action_space.no_op_action for player in modeled_players
        }
        previous_rewards = {player: 0.0 for player in modeled_players}
        episode_start = True
        decision = 0
        game_features: dict[int, list[np.ndarray]] = {
            player: [] for player in recorded_players
        }
        game_ticks: dict[int, list[int]] = {
            player: [] for player in recorded_players
        }
        done = False
        learner_decks.add(_deck_key(env.battle.players[learner].deck))
        opponent_decks.add(_deck_key(env.battle.players[opponent].deck))
        while not done:
            learner_mask = env.get_action_mask(learner)
            opponent_mask = env.get_action_mask(opponent)
            masks = {learner: learner_mask, opponent: opponent_mask}
            policy_actions: dict[int, int] = {}
            for player in modeled_players:
                observation = loaded.builder.build(env.battle, player)
                inputs = _stack_step_inputs(
                    [observation],
                    masks[player][None, :],
                    np.asarray([previous_actions[player]], dtype=np.int64),
                    np.asarray([previous_rewards[player]], dtype=np.float32),
                    np.asarray([episode_start], dtype=np.bool_),
                    device,
                )
                action, _, _, states[player], output = loaded.model.act(
                    inputs,
                    states[player],
                    deterministic=True,
                )
                policy_actions[player] = int(action[0, 0])
                if player not in game_features or decision % sample_stride != 0:
                    continue
                assert output.repair_features is not None
                game_features[player].append(
                    output.repair_features[0, 0].detach().cpu().numpy().copy()
                )
                game_ticks[player].append(env.battle.tick)
            learner_action = policy_actions[learner]
            if opponent_kind == "selfplay":
                opponent_action = policy_actions[opponent]
            elif bot is not None:
                assert bot is not None
                opponent_action = bot.select_action(
                    env,
                    opponent,
                    action_mask=opponent_mask,
                )
            else:
                legal = np.flatnonzero(opponent_mask)
                opponent_action = int(stationary_rng.choice(legal))
            rewards, done, _ = env.step(
                {learner: learner_action, opponent: opponent_action},
                pre_action_masks={learner: learner_mask, opponent: opponent_mask},
            )
            actual_actions = {learner: learner_action, opponent: opponent_action}
            for player in modeled_players:
                previous_actions[player] = actual_actions[player]
                previous_rewards[player] = float(rewards[player])
            episode_start = False
            decision += 1
        if env.battle.winner is None:
            learner_outcomes["draw"] += 1
        elif env.battle.winner == learner:
            learner_outcomes["win"] += 1
        else:
            learner_outcomes["loss"] += 1
        final_tick = env.battle.tick
        for player in recorded_players:
            if env.battle.winner is None:
                target = 0.5
                outcome = "draw"
            elif env.battle.winner == player:
                target = 1.0
                outcome = "win"
            else:
                target = 0.0
                outcome = "loss"
            outcomes[outcome] += 1
            perspective_id = (
                global_game * 2 + player
                if perspectives == "both"
                else global_game
            )
            player_features = game_features[player]
            all_features.extend(player_features)
            all_targets.extend([target] * len(player_features))
            all_game_ids.extend([perspective_id] * len(player_features))
            all_ticks.extend(game_ticks[player])
            all_final_ticks.extend([final_tick] * len(player_features))
            all_battle_ids.extend([global_game] * len(player_features))
            all_players.extend([player] * len(player_features))
            is_policy_controlled = opponent_kind == "selfplay" or player == learner
            all_policy_controlled.extend(
                [is_policy_controlled] * len(player_features)
            )
    corpus = OutcomeCorpus(
        features=np.stack(all_features).astype(np.float32, copy=False),
        targets=np.asarray(all_targets, dtype=np.float32),
        game_ids=np.asarray(all_game_ids, dtype=np.int64),
        ticks=np.asarray(all_ticks, dtype=np.int64),
        final_ticks=np.asarray(all_final_ticks, dtype=np.int64),
        battle_ids=np.asarray(all_battle_ids, dtype=np.int64),
        players=np.asarray(all_players, dtype=np.int8),
        policy_controlled=np.asarray(all_policy_controlled, dtype=np.bool_),
    )
    return corpus, {
        "battles": games,
        "perspectives": len(np.unique(corpus.game_ids)),
        "perspective_mode": perspectives,
        "opponent_mode": opponent_mode,
        "samples": len(corpus.targets),
        "outcomes": outcomes,
        "learner_outcomes": learner_outcomes,
        "learner_decks": len(learner_decks),
        "opponent_decks": len(opponent_decks),
        "opponent_schedule": (
            [*strategies, "random", "selfplay"]
            if opponent_mode == "mixed"
            else list(strategies)
            if opponent_mode == "strategy"
            else [opponent_mode]
        ),
        "_learner_deck_keys": sorted(learner_decks),
        "_opponent_deck_keys": sorted(opponent_decks),
        "feature_size": int(corpus.features.shape[1]),
    }


def _concatenate_corpora(corpora: list[OutcomeCorpus]) -> OutcomeCorpus:
    if not corpora:
        raise ValueError("cannot concatenate an empty outcome corpus list")

    def combine(name: str) -> np.ndarray:
        return np.concatenate([getattr(corpus, name) for corpus in corpora], axis=0)

    return OutcomeCorpus(
        features=combine("features"),
        targets=combine("targets"),
        game_ids=combine("game_ids"),
        ticks=combine("ticks"),
        final_ticks=combine("final_ticks"),
        battle_ids=combine("battle_ids"),
        players=combine("players"),
        policy_controlled=combine("policy_controlled"),
    )


def _collect_outcome_shard(kwargs: dict[str, Any]) -> tuple[OutcomeCorpus, dict[str, Any]]:
    torch.set_num_threads(1)
    kwargs = dict(kwargs)
    kwargs["device"] = torch.device(str(kwargs["device"]))
    return collect_outcome_corpus(**kwargs)


def collect_outcome_corpus_parallel(
    *,
    workers: int,
    **kwargs: Any,
) -> tuple[OutcomeCorpus, dict[str, Any]]:
    games = int(kwargs["games"])
    if workers <= 0:
        raise ValueError("outcome collection workers must be positive")
    workers = min(workers, games)
    if workers == 1:
        return collect_outcome_corpus(**kwargs)
    start = int(kwargs.pop("game_offset", 0))
    base, remainder = divmod(games, workers)
    jobs: list[dict[str, Any]] = []
    offset = start
    for worker in range(workers):
        count = base + int(worker < remainder)
        job = dict(kwargs)
        job.update(games=count, game_offset=offset, device=str(kwargs["device"]))
        jobs.append(job)
        offset += count
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=mp.get_context("spawn"),
    ) as executor:
        results = list(executor.map(_collect_outcome_shard, jobs))
    corpora = [result[0] for result in results]
    metadata_rows = [result[1] for result in results]
    corpus = _concatenate_corpora(corpora)
    learner_decks = {
        key for row in metadata_rows for key in row["_learner_deck_keys"]
    }
    opponent_decks = {
        key for row in metadata_rows for key in row["_opponent_deck_keys"]
    }
    outcomes = {
        name: sum(int(row["outcomes"][name]) for row in metadata_rows)
        for name in ("win", "draw", "loss")
    }
    learner_outcomes = {
        name: sum(int(row["learner_outcomes"][name]) for row in metadata_rows)
        for name in ("win", "draw", "loss")
    }
    return corpus, {
        "battles": games,
        "perspectives": len(np.unique(corpus.game_ids)),
        "perspective_mode": str(kwargs["perspectives"]),
        "opponent_mode": str(kwargs["opponent_mode"]),
        "workers": workers,
        "samples": len(corpus.targets),
        "outcomes": outcomes,
        "learner_outcomes": learner_outcomes,
        "learner_decks": len(learner_decks),
        "opponent_decks": len(opponent_decks),
        "opponent_schedule": (
            [*STRATEGY_NAMES, "random", "selfplay"]
            if kwargs["opponent_mode"] == "mixed"
            else list(STRATEGY_NAMES)
            if kwargs["opponent_mode"] == "strategy"
            else [str(kwargs["opponent_mode"])]
        ),
        "_learner_deck_keys": sorted(learner_decks),
        "_opponent_deck_keys": sorted(opponent_decks),
        "feature_size": int(corpus.features.shape[1]),
    }


def _public_collection_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)
    result.pop("_learner_deck_keys", None)
    result.pop("_opponent_deck_keys", None)
    return result


def save_corpus(path: Path, corpus: OutcomeCorpus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez_compressed(
            handle,
            features=corpus.features,
            targets=corpus.targets,
            game_ids=corpus.game_ids,
            ticks=corpus.ticks,
            final_ticks=corpus.final_ticks,
            battle_ids=corpus.battle_ids,
            players=corpus.players,
            policy_controlled=corpus.policy_controlled,
        )


def load_corpus(path: Path) -> OutcomeCorpus:
    with np.load(path, allow_pickle=False) as payload:
        game_ids = np.asarray(payload["game_ids"])
        return OutcomeCorpus(
            features=np.asarray(payload["features"]),
            targets=np.asarray(payload["targets"]),
            game_ids=game_ids,
            ticks=np.asarray(payload["ticks"]),
            final_ticks=np.asarray(payload["final_ticks"]),
            battle_ids=(
                np.asarray(payload["battle_ids"])
                if "battle_ids" in payload.files
                else game_ids.copy()
            ),
            players=(
                np.asarray(payload["players"])
                if "players" in payload.files
                else np.full(game_ids.shape, -1, dtype=np.int8)
            ),
            policy_controlled=(
                np.asarray(payload["policy_controlled"])
                if "policy_controlled" in payload.files
                else np.ones(game_ids.shape, dtype=np.bool_)
            ),
        )


def _game_balanced_weights(game_ids: np.ndarray) -> np.ndarray:
    _, inverse, counts = np.unique(game_ids, return_inverse=True, return_counts=True)
    weights = 1.0 / counts[inverse]
    result: np.ndarray = np.asarray(
        weights / weights.mean(),
        dtype=np.float32,
    )
    return result


def _paired_player_indices(corpus: OutcomeCorpus) -> tuple[np.ndarray, np.ndarray]:
    """Return player-0/player-1 rows aligned at the same battle tick."""
    rows: dict[tuple[int, int], dict[int, int]] = {}
    for index, (battle, tick, player) in enumerate(
        zip(corpus.battle_ids, corpus.ticks, corpus.players, strict=True)
    ):
        if int(player) not in {0, 1}:
            continue
        rows.setdefault((int(battle), int(tick)), {})[int(player)] = index
    complete = [pair for pair in rows.values() if pair.keys() == {0, 1}]
    return (
        np.asarray([pair[0] for pair in complete], dtype=np.int64),
        np.asarray([pair[1] for pair in complete], dtype=np.int64),
    )


def _auc(scores: np.ndarray, targets: np.ndarray) -> float | None:
    positive = targets > 0.5
    negative = targets < 0.5
    if not positive.any() or not negative.any():
        return None
    comparisons = scores[positive, None] - scores[negative][None, :]
    return float(np.mean(comparisons > 0) + 0.5 * np.mean(comparisons == 0))


def _evaluate_probabilities(
    corpus: OutcomeCorpus,
    probabilities: np.ndarray,
) -> dict[str, Any]:
    if probabilities.shape != corpus.targets.shape:
        raise ValueError("public outcome probabilities must match corpus rows")
    game_rows = []
    for game in np.unique(corpus.game_ids):
        indices = np.flatnonzero(corpus.game_ids == game)
        progress = corpus.ticks[indices] / np.maximum(1, corpus.final_ticks[indices])
        row: dict[str, Any] = {
            "game": int(game),
            "target": float(corpus.targets[indices[0]]),
        }
        for phase, point in (("early", 1 / 6), ("middle", 1 / 2), ("late", 5 / 6)):
            nearest = indices[int(np.argmin(np.abs(progress - point)))]
            row[phase] = float(probabilities[nearest])
        game_rows.append(row)
    report: dict[str, Any] = {"games": len(game_rows)}
    targets = np.asarray([row["target"] for row in game_rows], dtype=np.float64)
    for phase in ("early", "middle", "late"):
        phase_probabilities = np.asarray(
            [row[phase] for row in game_rows],
            dtype=np.float64,
        )
        report[phase] = {
            "auc": _auc(phase_probabilities, targets),
            "brier": float(np.mean((phase_probabilities - targets) ** 2)),
            "probability_mean": float(phase_probabilities.mean()),
            "probability_std": float(phase_probabilities.std()),
        }
    return report


@torch.no_grad()
def _head_probabilities(
    head: PublicOutcomeHead,
    corpus: OutcomeCorpus,
    *,
    device: torch.device,
    antisymmetric: bool,
) -> np.ndarray:
    head.eval()
    logits = head(torch.as_tensor(corpus.features, device=device)).cpu().numpy()
    if not antisymmetric:
        return np.asarray(
            1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0))),
            dtype=np.float32,
        )
    player_0, player_1 = _paired_player_indices(corpus)
    if len(player_0) * 2 != len(corpus.targets):
        raise ValueError("antisymmetric public outcome evaluation requires paired rows")
    probabilities = np.full(corpus.targets.shape, np.nan, dtype=np.float32)
    pair_logits = 0.5 * (logits[player_0] - logits[player_1])
    player_0_probabilities = 1.0 / (
        1.0 + np.exp(-np.clip(pair_logits, -20.0, 20.0))
    )
    probabilities[player_0] = player_0_probabilities
    probabilities[player_1] = 1.0 - player_0_probabilities
    return probabilities


def evaluate_head(
    head: PublicOutcomeHead,
    corpus: OutcomeCorpus,
    *,
    device: torch.device,
    antisymmetric: bool = False,
) -> dict[str, Any]:
    probabilities = _head_probabilities(
        head,
        corpus,
        device=device,
        antisymmetric=antisymmetric,
    )
    return _evaluate_probabilities(corpus, probabilities)


def _subset_corpus(corpus: OutcomeCorpus, mask: np.ndarray) -> OutcomeCorpus:
    return OutcomeCorpus(
        features=corpus.features[mask],
        targets=corpus.targets[mask],
        game_ids=corpus.game_ids[mask],
        ticks=corpus.ticks[mask],
        final_ticks=corpus.final_ticks[mask],
        battle_ids=corpus.battle_ids[mask],
        players=corpus.players[mask],
        policy_controlled=corpus.policy_controlled[mask],
    )


def evaluate_head_by_player(
    head: PublicOutcomeHead,
    corpus: OutcomeCorpus,
    *,
    device: torch.device,
    antisymmetric: bool = False,
) -> dict[str, Any]:
    probabilities = _head_probabilities(
        head,
        corpus,
        device=device,
        antisymmetric=antisymmetric,
    )
    return {
        f"player_{player}": _evaluate_probabilities(
            _subset_corpus(corpus, corpus.players == player),
            probabilities[corpus.players == player],
        )
        for player in (0, 1)
        if np.any(corpus.players == player)
    }


@torch.no_grad()
def evaluate_head_symmetry(
    head: PublicOutcomeHead,
    corpus: OutcomeCorpus,
    *,
    device: torch.device,
) -> dict[str, Any]:
    """Audit complementary predictions for the two views of one public state."""
    player_0, player_1 = _paired_player_indices(corpus)
    if not len(player_0):
        return {"pairs": 0}
    head.eval()
    logits = head(torch.as_tensor(corpus.features, device=device)).cpu().numpy()
    logits_0 = logits[player_0]
    logits_1 = logits[player_1]
    probabilities_0 = 1.0 / (1.0 + np.exp(-np.clip(logits_0, -20.0, 20.0)))
    probabilities_1 = 1.0 / (1.0 + np.exp(-np.clip(logits_1, -20.0, 20.0)))
    logit_error = np.abs(logits_0 + logits_1)
    probability_error = np.abs(probabilities_0 + probabilities_1 - 1.0)
    return {
        "pairs": len(player_0),
        "mean_abs_logit_sum": float(logit_error.mean()),
        "max_abs_logit_sum": float(logit_error.max()),
        "mean_abs_probability_sum_error": float(probability_error.mean()),
        "max_abs_probability_sum_error": float(probability_error.max()),
    }


def evaluate_head_by_opponent(
    head: PublicOutcomeHead,
    corpus: OutcomeCorpus,
    *,
    opponent_schedule: tuple[str, ...],
    device: torch.device,
    antisymmetric: bool = False,
) -> dict[str, Any]:
    """Report calibration independently for every deterministic opponent slot."""
    if not opponent_schedule:
        raise ValueError("public outcome opponent schedule cannot be empty")
    report: dict[str, Any] = {}
    for index, opponent in enumerate(opponent_schedule):
        mask = corpus.battle_ids % len(opponent_schedule) == index
        if not np.any(mask):
            continue
        subset = _subset_corpus(corpus, mask)
        report[opponent] = {
            "aggregate": evaluate_head(
                head,
                subset,
                device=device,
                antisymmetric=antisymmetric,
            ),
            "by_player": evaluate_head_by_player(
                head,
                subset,
                device=device,
                antisymmetric=antisymmetric,
            ),
            "symmetry": evaluate_head_symmetry(head, subset, device=device),
        }
    return report


def _mean_phase_metric(report: dict[str, Any], metric: str) -> float:
    values = [report[phase][metric] for phase in ("early", "middle", "late")]
    if metric == "auc":
        return float(np.mean([0.5 if value is None else value for value in values]))
    return float(np.mean(values))


def _validation_selection_score(
    aggregate: dict[str, Any],
    by_player: dict[str, Any],
) -> tuple[float, float, float, float]:
    if len(by_player) == 2:
        seat_briers = [
            _mean_phase_metric(report, "brier") for report in by_player.values()
        ]
        seat_aucs = [_mean_phase_metric(report, "auc") for report in by_player.values()]
        return (
            max(seat_briers),
            -min(seat_aucs),
            _mean_phase_metric(aggregate, "brier"),
            -_mean_phase_metric(aggregate, "auc"),
        )
    return (
        _mean_phase_metric(aggregate, "brier"),
        -_mean_phase_metric(aggregate, "auc"),
        _mean_phase_metric(aggregate, "brier"),
        -_mean_phase_metric(aggregate, "auc"),
    )


def train_head(
    train: OutcomeCorpus,
    validation: OutcomeCorpus,
    *,
    kind: str,
    seed: int,
    epochs: int,
    learning_rate: float,
    pairwise_weight: float,
    antisymmetry_weight: float,
    device: torch.device,
) -> tuple[PublicOutcomeHead, list[dict[str, Any]], int]:
    torch.manual_seed(seed)
    head = PublicOutcomeHead(train.features.shape[1], kind).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=learning_rate, weight_decay=1e-4)
    features = torch.as_tensor(train.features, device=device)
    targets = torch.as_tensor(train.targets, device=device)
    weights = torch.as_tensor(_game_balanced_weights(train.game_ids), device=device)
    player_0_indices, player_1_indices = _paired_player_indices(train)
    if (pairwise_weight > 0.0 or antisymmetry_weight > 0.0) and not len(
        player_0_indices
    ):
        raise ValueError("paired public-value loss requires aligned player rows")
    player_0 = torch.as_tensor(player_0_indices, device=device)
    player_1 = torch.as_tensor(player_1_indices, device=device)
    best_score = (float("inf"), float("inf"), float("inf"), float("inf"))
    best_state: dict[str, Tensor] = {}
    best_epoch = 0
    rows = []
    for epoch in range(1, epochs + 1):
        head.train()
        optimizer.zero_grad(set_to_none=True)
        logits = head(features)
        losses = nn.functional.binary_cross_entropy_with_logits(
            logits,
            targets,
            reduction="none",
        )
        independent_loss = (losses * weights).mean()
        pairwise_loss = torch.zeros((), device=device)
        antisymmetry_loss = torch.zeros((), device=device)
        if len(player_0_indices):
            player_0_logits = logits[player_0]
            player_1_logits = logits[player_1]
            pairwise_loss = nn.functional.binary_cross_entropy_with_logits(
                player_0_logits - player_1_logits,
                targets[player_0],
            )
            antisymmetry_loss = torch.mean((player_0_logits + player_1_logits) ** 2)
        loss = (
            independent_loss
            + pairwise_weight * pairwise_loss
            + antisymmetry_weight * antisymmetry_loss
        )
        loss.backward()
        optimizer.step()
        validation_report = evaluate_head(head, validation, device=device)
        validation_by_player = evaluate_head_by_player(
            head,
            validation,
            device=device,
        )
        mean_brier = _mean_phase_metric(validation_report, "brier")
        mean_auc = _mean_phase_metric(validation_report, "auc")
        rows.append(
            {
                "epoch": epoch,
                "train_loss": float(loss.detach()),
                "train_independent_loss": float(independent_loss.detach()),
                "train_pairwise_loss": float(pairwise_loss.detach()),
                "train_antisymmetry_loss": float(antisymmetry_loss.detach()),
                "validation": validation_report,
                "validation_by_player": validation_by_player,
                "validation_mean_brier": mean_brier,
                "validation_mean_auc": mean_auc,
            }
        )
        score = _validation_selection_score(validation_report, validation_by_player)
        if score < best_score:
            best_score = score
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }
    head.load_state_dict(best_state)
    return head, rows, best_epoch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/"
            "policy_v2_update_000040.pt"
        ),
    )
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument(
        "--train-decks",
        type=Path,
        default=Path(
            "datasets/deck_curriculum_v2_seed1040001/"
            "train_without_tv_raw2000_human_meta.json"
        ),
    )
    parser.add_argument(
        "--validation-decks",
        type=Path,
        default=Path("datasets/deck_curriculum_v2_seed1040001/validation.json"),
    )
    parser.add_argument(
        "--heldout-decks",
        type=Path,
        default=Path("datasets/deck_curriculum_v2_seed1040001/heldout.json"),
    )
    parser.add_argument("--train-games", type=int, default=24)
    parser.add_argument("--validation-games", type=int, default=12)
    parser.add_argument("--heldout-games", type=int, default=12)
    parser.add_argument("--sample-stride", type=int, default=8)
    parser.add_argument(
        "--perspectives",
        choices=("learner", "both"),
        default="both",
        help="extract only the policy player or both public player perspectives",
    )
    parser.add_argument(
        "--opponent-mode",
        choices=("selfplay", "strategy", "random", "mixed"),
        default="mixed",
        help=(
            "frozen self-play, stationary random, all deterministic strategies, "
            "or a deterministic rotation through all eight opponent types"
        ),
    )
    parser.add_argument("--seed", type=int, default=1049601)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--pairwise-weight", type=float, default=1.0)
    parser.add_argument("--antisymmetry-weight", type=float, default=0.1)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument(
        "--collection-device",
        choices=("cpu",),
        default="cpu",
        help="CPU is required for deterministic multi-process trajectory collection",
    )
    parser.add_argument("--collection-workers", type=int, default=1)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    split_paths = {
        "train": args.train_decks,
        "validation": args.validation_decks,
        "heldout": args.heldout_decks,
    }
    deck_splits = validate_deck_splits(split_paths)
    split_games = {
        "train": args.train_games,
        "validation": args.validation_games,
        "heldout": args.heldout_games,
    }
    collection: dict[str, Any] = {}
    for index, split in enumerate(("train", "validation", "heldout")):
        path = args.corpus_root / f"{split}.npz"
        if not path.is_file():
            corpus, metadata = collect_outcome_corpus_parallel(
                workers=args.collection_workers,
                checkpoint=args.checkpoint,
                decks_path=args.decks_path,
                sampling_decks_path=split_paths[split],
                games=split_games[split],
                seed=args.seed + index,
                sample_stride=args.sample_stride,
                perspectives=args.perspectives,
                opponent_mode=args.opponent_mode,
                device=torch.device(args.collection_device),
            )
            save_corpus(path, corpus)
            collection[split] = _public_collection_metadata(metadata)
        else:
            corpus = load_corpus(path)
            collection[split] = {
                "battles": len(np.unique(corpus.battle_ids)),
                "perspectives": len(np.unique(corpus.game_ids)),
                "perspective_mode": args.perspectives,
                "opponent_mode": args.opponent_mode,
                "samples": len(corpus.targets),
                "outcomes": {
                    "win": len(np.unique(corpus.game_ids[corpus.targets > 0.5])),
                    "draw": len(np.unique(corpus.game_ids[corpus.targets == 0.5])),
                    "loss": len(np.unique(corpus.game_ids[corpus.targets < 0.5])),
                },
                "reused": True,
                "workers": args.collection_workers,
            }
    corpora = {
        split: load_corpus(args.corpus_root / f"{split}.npz")
        for split in ("train", "validation", "heldout")
    }
    opponent_schedule = (
        (*STRATEGY_NAMES, "random", "selfplay")
        if args.opponent_mode == "mixed"
        else tuple(STRATEGY_NAMES)
        if args.opponent_mode == "strategy"
        else (args.opponent_mode,)
    )
    candidates: dict[str, Any] = {}
    trained: dict[str, PublicOutcomeHead] = {}
    for kind in ("linear", "mlp"):
        head, rows, best_epoch = train_head(
            corpora["train"],
            corpora["validation"],
            kind=kind,
            seed=args.seed,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            pairwise_weight=args.pairwise_weight,
            antisymmetry_weight=args.antisymmetry_weight,
            device=device,
        )
        trained[kind] = head
        candidates[kind] = {
            "best_epoch": best_epoch,
            "epochs": rows,
            "final": {
                split: evaluate_head(head, corpus, device=device)
                for split, corpus in corpora.items()
            },
            "final_by_player": {
                split: evaluate_head_by_player(head, corpus, device=device)
                for split, corpus in corpora.items()
            },
            "final_by_opponent": {
                split: evaluate_head_by_opponent(
                    head,
                    corpus,
                    opponent_schedule=opponent_schedule,
                    device=device,
                )
                for split, corpus in corpora.items()
            },
            "final_symmetry": {
                split: evaluate_head_symmetry(head, corpus, device=device)
                for split, corpus in corpora.items()
            },
            "final_antisymmetric": {
                split: evaluate_head(
                    head,
                    corpus,
                    device=device,
                    antisymmetric=True,
                )
                for split, corpus in corpora.items()
            },
            "final_antisymmetric_by_player": {
                split: evaluate_head_by_player(
                    head,
                    corpus,
                    device=device,
                    antisymmetric=True,
                )
                for split, corpus in corpora.items()
            },
            "final_antisymmetric_by_opponent": {
                split: evaluate_head_by_opponent(
                    head,
                    corpus,
                    opponent_schedule=opponent_schedule,
                    device=device,
                    antisymmetric=True,
                )
                for split, corpus in corpora.items()
            },
            "parameter_count": sum(parameter.numel() for parameter in head.parameters()),
        }
    selected_kind = min(
        candidates,
        key=lambda kind: _validation_selection_score(
            candidates[kind]["final"]["validation"],
            candidates[kind]["final_by_player"]["validation"],
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": 1,
            "kind": selected_kind,
            "input_size": int(corpora["train"].features.shape[1]),
            "source_checkpoint": str(args.checkpoint.resolve()),
            "state_dict": {
                name: value.detach().cpu()
                for name, value in trained[selected_kind].state_dict().items()
            },
        },
        args.output,
    )
    report = {
        "schema_version": 1,
        "seed": args.seed,
        "perspective_mode": args.perspectives,
        "opponent_mode": args.opponent_mode,
        "opponent_schedule": list(opponent_schedule),
        "collection_workers": args.collection_workers,
        "pairwise_weight": args.pairwise_weight,
        "antisymmetry_weight": args.antisymmetry_weight,
        "source_checkpoint": str(args.checkpoint.resolve()),
        "deck_splits": deck_splits,
        "collection": collection,
        "candidates": candidates,
        "selected_kind_on_validation": selected_kind,
        "output": str(args.output.resolve()),
        "output_sha256": _sha256(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
