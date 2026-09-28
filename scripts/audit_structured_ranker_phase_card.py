"""Audit phase- and card-specific behavior of a structured action ranker."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.counterfactual_corpus import terminal_candidate_order
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.structured_action_value_controller import (
    load_public_structured_action_value_head,
)
from scripts.fit_structured_public_action_value import _all_scores, _load


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _phase(tick: int) -> str:
    if tick < 1200:
        return "early"
    if tick < 2400:
        return "mid"
    if tick < 3600:
        return "late_regulation"
    return "overtime"


def _candidate_orders(payload: dict[str, np.ndarray], state: int) -> list[tuple[float, int, float]]:
    valid = np.flatnonzero(payload["candidate_valid"][state])
    result = [(-np.inf, -(2**63), -np.inf)] * payload["candidate_valid"].shape[1]
    for candidate in valid.tolist():
        result[candidate] = terminal_candidate_order(
            float(payload["candidate_scores"][state, candidate]),
            int(payload["candidate_crown_differences"][state, candidate]),
            float(payload["candidate_tower_damage_differences"][state, candidate]),
        )
    return result


def summarize_phase_card_gate(
    payload: dict[str, np.ndarray],
    scores: np.ndarray,
    *,
    holdout_games: set[int],
    required_card_token: int,
    minimum_phase_roots: int,
    minimum_phase_optimal_rate: float,
    minimum_phase_improvement_recall: float,
    minimum_required_card_roots: int,
    minimum_required_card_recall: float,
    minimum_score_gain: float,
) -> dict[str, Any]:
    if scores.shape != payload["candidate_valid"].shape:
        raise ValueError("ranker scores and candidate validity are misaligned")
    if minimum_phase_roots <= 0 or minimum_required_card_roots <= 0:
        raise ValueError("phase and card root thresholds must be positive")
    for name, value in (
        ("minimum_phase_optimal_rate", minimum_phase_optimal_rate),
        ("minimum_phase_improvement_recall", minimum_phase_improvement_recall),
        ("minimum_required_card_recall", minimum_required_card_recall),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between zero and one")
    if minimum_score_gain < 0.0 or not np.isfinite(minimum_score_gain):
        raise ValueError("minimum score gain must be finite and nonnegative")

    required = {
        "game_ids",
        "ticks",
        "base_actions",
        "best_actions",
        "candidate_actions",
        "candidate_card_ids",
        "candidate_valid",
        "candidate_scores",
        "candidate_crown_differences",
        "candidate_tower_damage_differences",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"phase/card audit corpus is missing {missing}")
    state_indices = np.flatnonzero(
        np.isin(payload["game_ids"], np.asarray(sorted(holdout_games), dtype=np.int64))
    )
    if not len(state_indices):
        raise ValueError("phase/card audit holdout contains no states")

    rows: list[dict[str, Any]] = []
    for state in state_indices.tolist():
        valid = np.asarray(payload["candidate_valid"][state], dtype=np.bool_)
        masked_scores = np.where(valid, scores[state], -np.inf)
        raw = int(np.argmax(masked_scores))
        selected = (
            raw
            if float(masked_scores[raw])
            > float(masked_scores[0]) + minimum_score_gain
            else 0
        )
        actions = np.asarray(payload["candidate_actions"][state], dtype=np.int64)
        matches = np.flatnonzero(actions == int(payload["best_actions"][state]))
        if len(matches) != 1:
            raise ValueError("terminal best action is not unique in candidate actions")
        best = int(matches[0])
        orders = _candidate_orders(payload, state)
        base_order = orders[0]
        selected_order = orders[selected]
        best_card = int(payload["candidate_card_ids"][state, best])
        selected_card = int(payload["candidate_card_ids"][state, selected])
        rows.append(
            {
                "phase": _phase(int(payload["ticks"][state])),
                "optimal": int(selected == best),
                "improvement": int(orders[best] > base_order),
                "improved": int(selected_order > base_order),
                "regressed": int(selected_order < base_order),
                "required_optimal": int(best_card == required_card_token),
                "required_selected": int(selected_card == required_card_token),
            }
        )

    phase_metrics: dict[str, dict[str, Any]] = {}
    for phase in ("early", "mid", "late_regulation", "overtime"):
        selected_rows = [row for row in rows if row["phase"] == phase]
        roots = len(selected_rows)
        improvements = sum(int(row["improvement"]) for row in selected_rows)
        phase_metrics[phase] = {
            "roots": roots,
            "optimal_action_rate": sum(int(row["optimal"]) for row in selected_rows)
            / max(1, roots),
            "improvement_roots": improvements,
            "improvement_recall": sum(int(row["improved"]) for row in selected_rows)
            / max(1, improvements),
            "regressions": sum(int(row["regressed"]) for row in selected_rows),
        }
    card_rows = [row for row in rows if row["required_optimal"]]
    card_recall = sum(int(row["required_selected"]) for row in card_rows) / max(
        1, len(card_rows)
    )
    phase_gates = {
        phase: {
            "minimum_roots": metrics["roots"] >= minimum_phase_roots,
            "optimal_action_rate": metrics["optimal_action_rate"]
            >= minimum_phase_optimal_rate,
            "improvement_recall": metrics["improvement_recall"]
            >= minimum_phase_improvement_recall,
            "zero_regressions": metrics["regressions"] == 0,
        }
        for phase, metrics in phase_metrics.items()
    }
    card_gates = {
        "minimum_roots": len(card_rows) >= minimum_required_card_roots,
        "selection_recall": card_recall >= minimum_required_card_recall,
    }
    passed = bool(
        all(all(gates.values()) for gates in phase_gates.values())
        and all(card_gates.values())
    )
    return {
        "schema": "clasher.structured_ranker_phase_card_gate.v1",
        "passed": passed,
        "holdout_games": sorted(holdout_games),
        "holdout_states": len(rows),
        "phase_metrics": phase_metrics,
        "phase_gates": phase_gates,
        "required_card_token": required_card_token,
        "required_card_roots": len(card_rows),
        "required_card_selection_recall": card_recall,
        "required_card_gates": card_gates,
        "thresholds": {
            "minimum_phase_roots": minimum_phase_roots,
            "minimum_phase_optimal_rate": minimum_phase_optimal_rate,
            "minimum_phase_improvement_recall": minimum_phase_improvement_recall,
            "minimum_required_card_roots": minimum_required_card_roots,
            "minimum_required_card_recall": minimum_required_card_recall,
            "minimum_score_gain": minimum_score_gain,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--fit-report", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--required-card", required=True)
    parser.add_argument("--minimum-phase-roots", type=int, default=15)
    parser.add_argument("--minimum-phase-optimal-rate", type=float, default=0.35)
    parser.add_argument(
        "--minimum-phase-improvement-recall", type=float, default=0.35
    )
    parser.add_argument("--minimum-required-card-roots", type=int, default=10)
    parser.add_argument("--minimum-required-card-recall", type=float, default=0.35)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch size must be positive")

    report = json.loads(args.fit_report.read_text(encoding="utf-8"))
    if report.get("checkpoint_sha256") != _sha256(args.checkpoint):
        raise ValueError("fit report and ranker checkpoint disagree")
    if report.get("validation_corpus_sha256") != _sha256(args.validation_corpus):
        raise ValueError("fit report and validation corpus disagree")
    holdout_games = {
        int(value)
        for value in report["validation_split_contract"]["games"]["holdout"]
    }
    device = torch.device("cpu")
    loaded = load_public_structured_action_value_head(args.checkpoint, device=device)
    policy = load_policy_checkpoint(
        args.policy, device=device, decks_path=args.decks_path
    )
    required_card_token = policy.builder.token_id(args.required_card)
    payload = _load(args.validation_corpus)
    scores = _all_scores(loaded.head, payload, device, args.batch_size)
    result = summarize_phase_card_gate(
        payload,
        scores,
        holdout_games=holdout_games,
        required_card_token=required_card_token,
        minimum_phase_roots=args.minimum_phase_roots,
        minimum_phase_optimal_rate=args.minimum_phase_optimal_rate,
        minimum_phase_improvement_recall=args.minimum_phase_improvement_recall,
        minimum_required_card_roots=args.minimum_required_card_roots,
        minimum_required_card_recall=args.minimum_required_card_recall,
        minimum_score_gain=loaded.minimum_score_gain,
    )
    result.update(
        {
            "required_card": args.required_card,
            "checkpoint": str(args.checkpoint.resolve()),
            "checkpoint_sha256": _sha256(args.checkpoint),
            "fit_report": str(args.fit_report.resolve()),
            "fit_report_sha256": _sha256(args.fit_report),
            "validation_corpus": str(args.validation_corpus.resolve()),
            "validation_corpus_sha256": _sha256(args.validation_corpus),
            "policy_sha256": _sha256(args.policy),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("structured ranker phase/card gate failed")


if __name__ == "__main__":
    main()
