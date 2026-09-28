#!/usr/bin/env python3
"""Compare matched frozen-teacher and event-student closed-loop behavior."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "clasher.hog26.closed-loop-behavior-reproduction.v1"
EVALUATION_SCHEMA = "clasher.hog26.simple-policy-evaluation.v1"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != EVALUATION_SCHEMA:
        raise ValueError(f"unknown simple evaluation schema: {path}")
    return payload


def _score(row: dict[str, Any]) -> int:
    return int(row["wins"]) - int(row["losses"])


def _decisions(row: dict[str, Any]) -> int:
    records = row.get("records")
    if not isinstance(records, list) or len(records) != int(row["games"]):
        raise ValueError("evaluation lacks complete per-game duration records")
    return sum(int(record["decisions"]) for record in records)


def _action_hashes(row: dict[str, Any]) -> list[str] | None:
    records = row.get("records")
    if not isinstance(records, list):
        return None
    values = [record.get("action_sha256") for record in records]
    if all(isinstance(value, str) and len(value) == 64 for value in values):
        return [str(value) for value in values]
    if any(value is not None for value in values):
        raise ValueError("evaluation has a partial action-hash contract")
    return None


def _counts(rows: list[dict[str, Any]]) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        raw = row.get("card_counts")
        if not isinstance(raw, dict):
            raise TypeError("evaluation lacks per-card behavior counts")
        result.update({str(key): int(value) for key, value in raw.items()})
    return result


def _total_variation(first: Counter[str], second: Counter[str]) -> float:
    first_total = sum(first.values())
    second_total = sum(second.values())
    if first_total <= 0 or second_total <= 0:
        return 1.0
    keys = set(first) | set(second)
    return 0.5 * sum(
        abs(first[key] / first_total - second[key] / second_total) for key in keys
    )


def compare(teacher: dict[str, Any], student: dict[str, Any]) -> dict[str, Any]:
    for key in ("base_seed", "games_per_opponent", "chunk_steps"):
        if teacher.get(key) != student.get(key):
            raise ValueError(f"teacher/student evaluation {key} differs")
    teacher_rows = teacher.get("rows")
    student_rows = student.get("rows")
    if not isinstance(teacher_rows, list) or not isinstance(student_rows, list):
        raise TypeError("evaluation rows are missing")
    teacher_by_opponent = {str(row["opponent"]): row for row in teacher_rows}
    student_by_opponent = {str(row["opponent"]): row for row in student_rows}
    if teacher_by_opponent.keys() != student_by_opponent.keys():
        raise ValueError("teacher/student opponent grids differ")

    bucket_rows: list[dict[str, Any]] = []
    bucket_regressions = 0
    excessive_duration_buckets = 0
    action_hash_matches = 0
    action_hash_rows = 0
    for opponent, teacher_row in teacher_by_opponent.items():
        student_row = student_by_opponent[opponent]
        teacher_score = _score(teacher_row)
        student_score = _score(student_row)
        regression = teacher_score - student_score
        bucket_regressions += int(regression > 1)
        teacher_decisions = _decisions(teacher_row)
        student_decisions = _decisions(student_row)
        duration_ratio = student_decisions / max(1, teacher_decisions)
        excessive_duration_buckets += int(duration_ratio > 1.5)
        teacher_hashes = _action_hashes(teacher_row)
        student_hashes = _action_hashes(student_row)
        if (teacher_hashes is None) != (student_hashes is None):
            raise ValueError("teacher/student action-hash contracts differ")
        if teacher_hashes is not None and student_hashes is not None:
            if len(teacher_hashes) != len(student_hashes):
                raise ValueError("teacher/student action-hash row counts differ")
            action_hash_matches += sum(
                first == second
                for first, second in zip(teacher_hashes, student_hashes, strict=True)
            )
            action_hash_rows += len(teacher_hashes)
        bucket_rows.append(
            {
                "opponent": opponent,
                "teacher_score": teacher_score,
                "student_score": student_score,
                "score_delta": student_score - teacher_score,
                "teacher_placement_rate": float(teacher_row["placement_rate"]),
                "student_placement_rate": float(student_row["placement_rate"]),
                "teacher_decisions": teacher_decisions,
                "student_decisions": student_decisions,
                "duration_ratio": duration_ratio,
            }
        )

    teacher_counts = _counts(teacher_rows)
    student_counts = _counts(student_rows)
    missing_supported = sorted(
        card
        for card, count in teacher_counts.items()
        if count >= 2 and student_counts[card] == 0
    )
    teacher_score = sum(_score(row) for row in teacher_rows)
    student_score = sum(_score(row) for row in student_rows)
    teacher_rate = sum(
        float(row["placement_rate"]) * int(row["games"]) for row in teacher_rows
    ) / sum(int(row["games"]) for row in teacher_rows)
    student_rate = sum(
        float(row["placement_rate"]) * int(row["games"]) for row in student_rows
    ) / sum(int(row["games"]) for row in student_rows)
    cadence_ratio = student_rate / teacher_rate if teacher_rate > 0.0 else 0.0
    teacher_decisions = sum(_decisions(row) for row in teacher_rows)
    student_decisions = sum(_decisions(row) for row in student_rows)
    duration_ratio = student_decisions / max(1, teacher_decisions)
    games = sum(int(row["games"]) for row in teacher_rows)
    behavior_pass = bool(
        student_score >= teacher_score - 1
        and bucket_regressions == 0
        and 0.8 <= cadence_ratio <= 1.25
        and duration_ratio <= 1.25
        and excessive_duration_buckets == 0
        and not missing_supported
        and _total_variation(teacher_counts, student_counts) <= 0.2
    )
    scale_gate_met = games >= 56
    return {
        "schema": SCHEMA,
        "base_seed": teacher["base_seed"],
        "games": games,
        "teacher_checkpoint_sha256": teacher["checkpoint_sha256"],
        "student_checkpoint_sha256": student["checkpoint_sha256"],
        "teacher_score": teacher_score,
        "student_score": student_score,
        "score_delta": student_score - teacher_score,
        "bucket_regressions_larger_than_one_game": bucket_regressions,
        "teacher_placement_rate": teacher_rate,
        "student_placement_rate": student_rate,
        "cadence_ratio": cadence_ratio,
        "teacher_decisions": teacher_decisions,
        "student_decisions": student_decisions,
        "duration_ratio": duration_ratio,
        "duration_buckets_above_1_5x": excessive_duration_buckets,
        "exact_action_hash_matches": action_hash_matches,
        "exact_action_hash_rows": action_hash_rows,
        "exact_action_hash_match_rate": (
            action_hash_matches / action_hash_rows if action_hash_rows else None
        ),
        "teacher_card_counts": dict(sorted(teacher_counts.items())),
        "student_card_counts": dict(sorted(student_counts.items())),
        "missing_teacher_supported_cards": missing_supported,
        "card_usage_total_variation": _total_variation(teacher_counts, student_counts),
        "opponents": bucket_rows,
        "behavior_gate_pass": behavior_pass,
        "minimum_scale_games": 56,
        "scale_gate_met": scale_gate_met,
        "status": (
            "passed-closed-loop"
            if behavior_pass and scale_gate_met
            else "passed-smoke-not-promotion"
            if behavior_pass
            else "rejected"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--student", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite behavior comparison")
    result = compare(_load(args.teacher), _load(args.student))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
