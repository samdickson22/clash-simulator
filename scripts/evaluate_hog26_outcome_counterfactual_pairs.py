#!/usr/bin/env python3
"""Compare actor-visible short-branch rankings with exact terminal authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "clasher.hog26.outcome-counterfactual-ranking.v1"
PROBE_SCHEMA = "clasher.simple-counterfactual-teacher-probe.v4"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if payload.get("schema") != PROBE_SCHEMA:
        raise ValueError("counterfactual probe schema changed")
    return payload


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=np.float64)
    begin = 0
    while begin < len(values):
        end = begin + 1
        while end < len(values) and values[order[end]] == values[order[begin]]:
            end += 1
        ranks[order[begin:end]] = 0.5 * (begin + end - 1)
        begin = end
    return ranks


def _spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2:
        return None
    left_rank = _average_ranks(left)
    right_rank = _average_ranks(right)
    if float(left_rank.std()) == 0.0 or float(right_rank.std()) == 0.0:
        return None
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def _reference_preference(
    left: dict[str, Any], right: dict[str, Any], *, margin_threshold: float
) -> int:
    outcome_delta = int(left["terminal_outcome"]) - int(right["terminal_outcome"])
    if outcome_delta:
        return 1 if outcome_delta > 0 else -1
    margin_delta = float(left["terminal_tower_margin"]) - float(
        right["terminal_tower_margin"]
    )
    if abs(margin_delta) < margin_threshold:
        return 0
    return 1 if margin_delta > 0 else -1


def root_phase(progress: float) -> str:
    if not 0.0 <= progress <= 1.0:
        raise ValueError("root progress must be in [0, 1]")
    return "early" if progress < 1 / 3 else "middle" if progress < 2 / 3 else "late"


def _variant_scores(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    outcome = np.asarray(
        [float(row["actor_visible_branch_utility"]) for row in rows],
        dtype=np.float64,
    )
    margin = np.asarray(
        [float(row["outcome_bootstrap_margin"]) for row in rows],
        dtype=np.float64,
    )
    disagreement = np.asarray(
        [float(row["outcome_ensemble_disagreement"]) for row in rows],
        dtype=np.float64,
    )
    return {
        "outcome": outcome,
        "outcome_minus_disagreement": outcome - disagreement,
        "margin": margin,
        "outcome_plus_0.25_margin": outcome + 0.25 * margin,
        "outcome_plus_0.50_margin": outcome + 0.50 * margin,
    }


def compare_pair(
    short: dict[str, Any],
    terminal: dict[str, Any],
    *,
    margin_threshold: float,
) -> dict[str, Any]:
    identity_fields = (
        "checkpoint_sha256",
        "seed",
        "warmup_steps",
        "opponent_strategy",
        "opponent_deck",
        "learner_seat",
        "candidate_selector",
    )
    for field in identity_fields:
        if short.get(field) != terminal.get(field):
            raise ValueError(f"paired probe differs in {field}")
    if short.get("stop_when_all_terminal") or not terminal.get(
        "stop_when_all_terminal"
    ):
        raise ValueError("paired probes do not have short/terminal roles")
    short_rows = {int(row["action"]): row for row in short["rows"]}
    terminal_rows = {int(row["action"]): row for row in terminal["rows"]}
    if short_rows.keys() != terminal_rows.keys():
        raise ValueError("paired probes use different candidate actions")
    actions = sorted(short_rows)
    ordered_short = [short_rows[action] for action in actions]
    ordered_terminal = [terminal_rows[action] for action in actions]
    if any(not bool(row["terminal"]) for row in ordered_terminal):
        raise ValueError("terminal authority contains a nonterminal branch")
    if any(row["actor_visible_branch_utility"] is None for row in ordered_short):
        raise ValueError("short probe lacks actor-visible bootstrap values")
    reference_score = np.asarray(
        [
            2.0 * int(row["terminal_outcome"])
            + float(row["terminal_tower_margin"])
            for row in ordered_terminal
        ],
        dtype=np.float64,
    )
    preferences: list[tuple[int, int, int]] = []
    for left in range(len(actions)):
        for right in range(left + 1, len(actions)):
            preference = _reference_preference(
                ordered_terminal[left],
                ordered_terminal[right],
                margin_threshold=margin_threshold,
            )
            if preference:
                preferences.append((left, right, preference))
    variants: dict[str, Any] = {}
    best_reference_index = int(reference_score.argmax())
    best_reference = ordered_terminal[best_reference_index]
    for name, scores in _variant_scores(ordered_short).items():
        concordant = 0
        tied = 0
        for left, right, preference in preferences:
            delta = float(scores[left] - scores[right])
            if delta == 0.0:
                tied += 1
            elif (1 if delta > 0 else -1) == preference:
                concordant += 1
        selected_index = int(scores.argmax())
        selected = ordered_terminal[selected_index]
        selected_outcome = int(selected["terminal_outcome"])
        best_outcome = int(best_reference["terminal_outcome"])
        margin_regret = (
            float(best_reference["terminal_tower_margin"])
            - float(selected["terminal_tower_margin"])
            if selected_outcome == best_outcome
            else None
        )
        variants[name] = {
            "spearman": _spearman(scores, reference_score),
            "strict_pair_count": len(preferences),
            "pairwise_concordance": (
                concordant / len(preferences) if preferences else None
            ),
            "pairwise_ties": tied,
            "selected_action": actions[selected_index],
            "reference_best_action": actions[best_reference_index],
            "selected_terminal_outcome": selected_outcome,
            "best_terminal_outcome": best_outcome,
            "worse_terminal_outcome": selected_outcome < best_outcome,
            "same_outcome_margin_regret": margin_regret,
        }
    return {
        "seed": int(short["seed"]),
        "warmup_steps": int(short["warmup_steps"]),
        "root_progress": short.get("root_progress"),
        "opponent_strategy": short["opponent_strategy"],
        "opponent_deck": short.get("opponent_deck"),
        "learner_seat": int(short.get("learner_seat", 0)),
        "candidate_actions": actions,
        "terminal_outcomes": [int(row["terminal_outcome"]) for row in ordered_terminal],
        "terminal_margins": [
            float(row["terminal_tower_margin"]) for row in ordered_terminal
        ],
        "variants": variants,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--short-probe", type=Path, action="append", required=True)
    parser.add_argument("--terminal-probe", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--frozen-variant", default="outcome")
    parser.add_argument("--margin-threshold", type=float, default=0.02)
    parser.add_argument("--minimum-roots", type=int, default=6)
    parser.add_argument("--minimum-roots-per-phase", type=int, default=2)
    parser.add_argument("--minimum-roots-per-seat", type=int, default=3)
    parser.add_argument("--minimum-pairwise-concordance", type=float, default=0.65)
    parser.add_argument("--maximum-mean-margin-regret", type=float, default=0.10)
    args = parser.parse_args()
    if args.report.exists():
        raise SystemExit("refusing to overwrite ranking report")
    if len(args.short_probe) != len(args.terminal_probe):
        raise ValueError("short and terminal probe counts differ")
    if (
        args.margin_threshold < 0.0
        or args.minimum_roots < 1
        or args.minimum_roots_per_phase < 1
        or args.minimum_roots_per_seat < 1
    ):
        raise ValueError("ranking gate sizes are invalid")
    roots = [
        compare_pair(_load(short), _load(terminal), margin_threshold=args.margin_threshold)
        for short, terminal in zip(
            args.short_probe, args.terminal_probe, strict=True
        )
    ]
    if not roots or args.frozen_variant not in roots[0]["variants"]:
        raise ValueError("unknown frozen ranking variant")
    selected = [root["variants"][args.frozen_variant] for root in roots]
    concordances = [
        float(row["pairwise_concordance"])
        for row in selected
        if row["pairwise_concordance"] is not None
    ]
    regrets = [
        float(row["same_outcome_margin_regret"])
        for row in selected
        if row["same_outcome_margin_regret"] is not None
    ]
    seat_roots = [int(root["learner_seat"]) for root in roots]
    seats = sorted(set(seat_roots))
    opponents = sorted({str(root["opponent_strategy"]) for root in roots})
    phase_roots = [
        root_phase(float(root["root_progress"]))
        for root in roots
        if root["root_progress"] is not None
    ]
    roots_per_phase = {
        phase: phase_roots.count(phase) for phase in ("early", "middle", "late")
    }
    roots_per_seat = {str(seat): seat_roots.count(seat) for seat in (0, 1)}
    aggregate = {
        "root_count": len(roots),
        "worse_terminal_outcomes": sum(bool(row["worse_terminal_outcome"]) for row in selected),
        "mean_pairwise_concordance": (
            float(np.mean(concordances)) if concordances else None
        ),
        "mean_same_outcome_margin_regret": (
            float(np.mean(regrets)) if regrets else None
        ),
        "seats": seats,
        "opponents": opponents,
        "phase_count": sum(count > 0 for count in roots_per_phase.values()),
        "roots_per_phase": roots_per_phase,
        "roots_per_seat": roots_per_seat,
    }
    passed = bool(
        len(roots) >= args.minimum_roots
        and seats == [0, 1]
        and len(opponents) >= 3
        and all(
            count >= args.minimum_roots_per_phase
            for count in roots_per_phase.values()
        )
        and all(
            count >= args.minimum_roots_per_seat for count in roots_per_seat.values()
        )
        and aggregate["worse_terminal_outcomes"] == 0
        and aggregate["mean_pairwise_concordance"] is not None
        and float(aggregate["mean_pairwise_concordance"])
        >= args.minimum_pairwise_concordance
        and aggregate["mean_same_outcome_margin_regret"] is not None
        and float(aggregate["mean_same_outcome_margin_regret"])
        <= args.maximum_mean_margin_regret
    )
    report = {
        "schema": SCHEMA,
        "status": "passed" if passed else "rejected",
        "frozen_variant": args.frozen_variant,
        "gates": {
            "minimum_roots": args.minimum_roots,
            "minimum_roots_per_phase": args.minimum_roots_per_phase,
            "minimum_roots_per_seat": args.minimum_roots_per_seat,
            "both_seats_required": True,
            "minimum_opponents": 3,
            "all_three_phases_required": True,
            "maximum_worse_terminal_outcomes": 0,
            "minimum_pairwise_concordance": args.minimum_pairwise_concordance,
            "maximum_mean_same_outcome_margin_regret": args.maximum_mean_margin_regret,
        },
        "aggregate": aggregate,
        "roots": roots,
        "short_probes": [
            {"path": str(path.resolve()), "sha256": file_sha256(path)}
            for path in args.short_probe
        ],
        "terminal_probes": [
            {"path": str(path.resolve()), "sha256": file_sha256(path)}
            for path in args.terminal_probe
        ],
        "policy_mutation_authorized": False,
    }
    if not math.isfinite(float(aggregate["mean_same_outcome_margin_regret"] or 0.0)):
        raise ValueError("ranking report contains nonfinite regret")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "aggregate": aggregate}))


if __name__ == "__main__":
    main()
