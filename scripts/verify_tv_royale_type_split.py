"""Fail closed unless TV Royale type-imitation splits are broad enough."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_INVARIANTS: dict[str, object] = {
    "replay_overlap": 0,
    "deck_signature_overlap": 0,
    "held_out_archetype_train_overlap": 0,
    "location_supervision_rows": 0,
    "played_card_objective": "type-head-v1",
    "noop_labels": "exact",
    "incomplete_visible_hand_rows": 0,
    "visible_hand_filter": "four-known-visible-slots-v1",
    "previous_action_chain": "previous-retained-expert-action-v1",
}

# These floors are deliberately well below the first-1,814 production
# projection. They detect a collapsed split, not a small fluctuation in the
# final 2,000-game composition.
SPLIT_MINIMUMS: dict[str, dict[str, int]] = {
    "train": {
        "samples": 10_000,
        "replays": 500,
        "deck_signatures": 500,
        "distinct_arenas": 15,
        "distinct_archetypes": 8,
    },
    "validation": {
        "samples": 2_000,
        "replays": 100,
        "deck_signatures": 100,
        "distinct_arenas": 15,
        "distinct_archetypes": 8,
    },
    "archetype_test": {
        "samples": 3_000,
        "replays": 150,
        "deck_signatures": 100,
        "distinct_arenas": 15,
        "distinct_archetypes": 4,
    },
    "chronology_test": {
        "samples": 1_000,
        "replays": 50,
        "deck_signatures": 30,
        "distinct_arenas": 1,
        "distinct_archetypes": 8,
    },
}


class TypeDataInsufficient(RuntimeError):
    """The split is structurally safe but too small or narrow to train."""

    def __init__(self, details: dict[str, dict[str, dict[str, int]]]) -> None:
        super().__init__("TV Royale type-imitation data is insufficient")
        self.details = details


def _metric(split: dict[str, Any], key: str) -> int:
    if key == "distinct_arenas":
        value: object = len(split.get("arenas", {}))
    elif key == "distinct_archetypes":
        value = len(split.get("archetypes", {}))
    else:
        value = split.get(key, 0)
    if not isinstance(value, int):
        raise TypeError(f"type-split metric {key} is not an integer: {value!r}")
    return value


def verify_type_split(manifest_path: Path, *, target_games: int) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) < 2:
        raise ValueError("TV Royale type split requires schema version 2")
    if int(payload.get("source_replays", -1)) != target_games:
        raise ValueError(
            "TV Royale source replay count mismatch: "
            f"expected {target_games}, got {payload.get('source_replays')}"
        )
    if int(payload.get("reserved_final_evaluation_replays", 0)) <= 0:
        raise ValueError("TV Royale type split reserves no final-evaluation replay")

    invariants = payload.get("invariants", {})
    mismatches = {
        key: {"expected": expected, "actual": invariants.get(key)}
        for key, expected in REQUIRED_INVARIANTS.items()
        if invariants.get(key) != expected
    }
    splits = payload.get("splits", {})
    missing_splits = sorted(set(SPLIT_MINIMUMS).difference(splits))
    if mismatches or missing_splits:
        raise ValueError(
            "unsafe/incomplete TV Royale type split: "
            f"mismatches={mismatches}, missing_splits={missing_splits}"
        )

    total_samples = sum(int(row.get("samples", 0)) for row in splits.values())
    total_replays = sum(int(row.get("replays", 0)) for row in splits.values())
    if total_samples != int(payload.get("total_samples", -1)):
        raise ValueError("TV Royale type split total-sample accounting mismatch")
    if total_replays != int(payload.get("total_replays", -1)):
        raise ValueError("TV Royale type split total-replay accounting mismatch")

    insufficient: dict[str, dict[str, dict[str, int]]] = {}
    for name, minimums in SPLIT_MINIMUMS.items():
        failures: dict[str, dict[str, int]] = {}
        row = splits[name]
        for key, required in minimums.items():
            actual = _metric(row, key)
            if actual < required:
                failures[key] = {"required": required, "actual": actual}
        if failures:
            insufficient[name] = failures
    if insufficient:
        raise TypeDataInsufficient(insufficient)

    return {
        "status": "type_split_verified",
        "source_replays": target_games,
        "reserved_final_evaluation_replays": int(
            payload["reserved_final_evaluation_replays"]
        ),
        "split_metrics": {
            name: {key: _metric(splits[name], key) for key in minimums}
            for name, minimums in SPLIT_MINIMUMS.items()
        },
        **REQUIRED_INVARIANTS,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-games", required=True, type=int)
    args = parser.parse_args()
    try:
        report = verify_type_split(args.manifest, target_games=args.target_games)
    except TypeDataInsufficient as exc:
        print(
            json.dumps(
                {"status": "type_imitation_data_insufficient", "details": exc.details},
                sort_keys=True,
            )
        )
        raise SystemExit(3) from exc
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
