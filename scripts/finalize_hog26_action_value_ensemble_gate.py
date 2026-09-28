"""Finalize paired free-running gates for a public action-value ensemble."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

STRATEGIES = frozenset(
    {
        "bridge-pressure",
        "slow-push",
        "balanced",
        "reactive-defense",
        "spell-control",
        "split-lane",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(result: str) -> float:
    return {"loss": 0.0, "draw": 0.5, "win": 1.0}[result]


def summarize_paired_reports(
    reports: list[dict[str, Any]],
    *,
    mode: str,
    bootstrap_seed: int = 1164901,
) -> dict[str, Any]:
    if mode not in {"screen", "quarantine"}:
        raise ValueError("unknown action-value gameplay gate mode")
    expected_games = 8 if mode == "screen" else 16
    expected_seed = 1164811 if mode == "screen" else 1165811
    if len(reports) != len(STRATEGIES):
        raise ValueError("gameplay gate needs one report per frozen strategy")
    strategies = [str(report.get("strategy")) for report in reports]
    if len(set(strategies)) != len(strategies) or set(strategies) != STRATEGIES:
        raise ValueError("gameplay reports do not match the frozen strategy set")
    policies = {str(report.get("policy")) for report in reports}
    if len(policies) != 1 or None in {report.get("policy") for report in reports}:
        raise ValueError("gameplay reports use different policy authorities")
    policy_hashes = {str(report.get("policy_sha256")) for report in reports}
    if len(policy_hashes) != 1 or None in {
        report.get("policy_sha256") for report in reports
    }:
        raise ValueError("gameplay reports use different policy hashes")
    action_values = {str(report["action_value"]) for report in reports}
    if len(action_values) != 1:
        raise ValueError("gameplay reports use different action-value authorities")
    action_value_hashes = {
        str(report.get("action_value_sha256")) for report in reports
    }
    if len(action_value_hashes) != 1 or None in {
        report.get("action_value_sha256") for report in reports
    }:
        raise ValueError("gameplay reports use different action-value hashes")
    action_value_modes = {str(report.get("action_value_mode")) for report in reports}
    if len(action_value_modes) != 1 or next(iter(action_value_modes)) not in {
        "controller",
        "structured",
    }:
        raise ValueError("gameplay reports use an unsupported action-value mode")
    opponent_deck_paths = {
        str(report.get("opponent_sampling_decks_path")) for report in reports
    }
    learner_deck_paths = {
        str(report.get("learner_sampling_decks_path")) for report in reports
    }
    if len(opponent_deck_paths) != 1 or len(learner_deck_paths) != 1:
        raise ValueError("gameplay reports use different deck authorities")
    deck_hash_fields = (
        "decks_sha256",
        "learner_sampling_decks_sha256",
        "opponent_sampling_decks_sha256",
    )
    deck_hashes: dict[str, str] = {}
    for field in deck_hash_fields:
        values = {str(report.get(field)) for report in reports}
        if len(values) != 1 or None in {report.get(field) for report in reports}:
            raise ValueError(f"gameplay reports use different {field} authorities")
        deck_hashes[field] = next(iter(values))
    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for report in reports:
        expected_contract = {
            "schema_version": 1,
            "seed": expected_seed,
            "game_offset": 0,
            "decision_interval": 8,
            "max_ticks": 6000,
            "max_candidates": 6,
            "minimum_tick": 256,
            "query_stride": 16,
        }
        for key, value in expected_contract.items():
            if report.get(key) != value:
                raise ValueError(f"gameplay report changed frozen {key}")
        if len(report["games"]) != 2 * expected_games:
            raise ValueError("gameplay report has incomplete paired games")
        by_game: dict[int, dict[bool, dict[str, Any]]] = defaultdict(dict)
        for row in report["games"]:
            game = int(row["game"])
            is_repaired = bool(row["repaired"])
            if is_repaired in by_game[game]:
                raise ValueError(f"game {game} duplicates a paired arm")
            by_game[game][is_repaired] = row
        if set(by_game) != set(range(expected_games)):
            raise ValueError("gameplay report changed frozen game IDs")
        seats = [int(arms[False]["candidate_player"]) for arms in by_game.values()]
        if seats.count(0) != expected_games // 2 or seats.count(1) != (
            expected_games // 2
        ):
            raise ValueError("gameplay report is not candidate-seat balanced")
        for game, arms in sorted(by_game.items()):
            if set(arms) != {False, True}:
                raise ValueError(f"game {game} does not contain both paired arms")
            baseline = arms[False]
            repaired = arms[True]
            for key in ("seed", "candidate_player", "candidate_deck", "opponent_deck"):
                if baseline[key] != repaired[key]:
                    raise ValueError(f"paired game differs at {key}")
            if int(baseline["seed"]) != expected_seed + game * 1009:
                raise ValueError(f"game {game} changed its frozen seed")
            if baseline["result"] not in {"win", "draw", "loss"} or repaired[
                "result"
            ] not in {"win", "draw", "loss"}:
                raise ValueError(f"game {game} has an invalid result")
            pairs.append((str(report["strategy"]), baseline, repaired))
    score_deltas = np.asarray(
        [_score(repaired["result"]) - _score(base["result"]) for _, base, repaired in pairs],
        dtype=np.float64,
    )
    crown_deltas = np.asarray(
        [
            (
                int(repaired["candidate_crowns"])
                - int(repaired["opponent_crowns"])
            )
            - (int(base["candidate_crowns"]) - int(base["opponent_crowns"]))
            for _, base, repaired in pairs
        ],
        dtype=np.int64,
    )
    rng = np.random.default_rng(bootstrap_seed)
    strategy_score_rows = {
        strategy: score_deltas[
            np.asarray([name == strategy for name, _, _ in pairs], dtype=np.bool_)
        ]
        for strategy in sorted(STRATEGIES)
    }
    bootstrap_parts = [
        values[
            rng.integers(0, len(values), size=(10_000, len(values)))
        ].sum(axis=1)
        for values in strategy_score_rows.values()
    ]
    bootstrap = np.stack(bootstrap_parts, axis=1).sum(axis=1) / len(pairs)
    by_strategy_crowns: dict[str, int] = defaultdict(int)
    by_strategy_scores: dict[str, float] = defaultdict(float)
    for (strategy, _base, _repaired), delta in zip(
        pairs, crown_deltas.tolist(), strict=True
    ):
        by_strategy_crowns[strategy] += int(delta)
    for (strategy, _base, _repaired), delta in zip(
        pairs, score_deltas.tolist(), strict=True
    ):
        by_strategy_scores[strategy] += float(delta)
    win_to_loss = sum(
        base["result"] == "win" and repaired["result"] == "loss"
        for _, base, repaired in pairs
    )
    loss_to_win = sum(
        base["result"] == "loss" and repaired["result"] == "win"
        for _, base, repaired in pairs
    )
    thresholds: dict[str, float | int] = (
        {
            "games": 48,
            "maximum_win_to_loss": 0,
            "minimum_loss_to_win": 2,
            "minimum_crown_delta": 5,
            "minimum_strategy_crown_delta": 0,
            "minimum_strategy_score_delta": 0.0,
        }
        if mode == "screen"
        else {
            "games": 96,
            "maximum_win_to_loss": 0,
            "minimum_loss_to_win": 4,
            "minimum_crown_delta": 8,
            "minimum_score_bootstrap_lower": 0.0,
            "minimum_strategy_crown_delta": 0,
            "minimum_strategy_score_delta": 0.0,
        }
    )
    passed = bool(
        len(pairs) == thresholds["games"]
        and win_to_loss <= thresholds["maximum_win_to_loss"]
        and loss_to_win >= thresholds["minimum_loss_to_win"]
        and int(crown_deltas.sum()) >= thresholds["minimum_crown_delta"]
        and min(by_strategy_crowns.values())
        >= thresholds["minimum_strategy_crown_delta"]
        and min(by_strategy_scores.values())
        >= thresholds["minimum_strategy_score_delta"]
    )
    if mode == "quarantine":
        passed &= bool(float(np.quantile(bootstrap, 0.025)) > 0.0)
    return {
        "schema": "clasher.hog26_action_value_gameplay_gate.v1",
        "mode": mode,
        "passed": passed,
        "policy": next(iter(policies)),
        "policy_sha256": next(iter(policy_hashes)),
        "action_value": next(iter(action_values)),
        "action_value_sha256": next(iter(action_value_hashes)),
        "action_value_mode": next(iter(action_value_modes)),
        "learner_sampling_decks_path": next(iter(learner_deck_paths)),
        "opponent_sampling_decks_path": next(iter(opponent_deck_paths)),
        **deck_hashes,
        "games": len(pairs),
        "win_to_loss": win_to_loss,
        "loss_to_win": loss_to_win,
        "score_delta_mean": float(score_deltas.mean()) if len(score_deltas) else 0.0,
        "score_delta_bootstrap_ci95": [
            float(np.quantile(bootstrap, 0.025)),
            float(np.quantile(bootstrap, 0.975)),
        ],
        "crown_delta": int(crown_deltas.sum()),
        "strategy_crown_deltas": dict(sorted(by_strategy_crowns.items())),
        "strategy_score_deltas": dict(sorted(by_strategy_scores.items())),
        "thresholds": thresholds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--mode", choices=("screen", "quarantine"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=1164901)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.input]
    result = summarize_paired_reports(
        reports,
        mode=args.mode,
        bootstrap_seed=args.bootstrap_seed,
    )
    result["inputs"] = {
        str(path.resolve()): _sha256(path) for path in args.input
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("action-value gameplay gate failed")


if __name__ == "__main__":
    main()
