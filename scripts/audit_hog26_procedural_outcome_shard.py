#!/usr/bin/env python3
"""Audit one completed training shard against the frozen procedural protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_hog26_outcome_corpora import audit
from scripts.collect_hog26_complete_outcomes import opponent_decks_for_split
from scripts.collect_hog26_direct_simple_behavior import _atomic_json, file_sha256
from scripts.run_hog26_procedural_outcome_shard import load_protocol


def shard_expectations(
    protocol: dict[str, Any], row: dict[str, Any], *, root: Path
) -> dict[str, Any]:
    supported_path = root / protocol["procedural_decks"]["path"]
    return {
        "expected_decks": set(
            opponent_decks_for_split(
                supported_path,
                str(row["split"]),
                tuple(str(value) for value in row["family_ids"]),
            )
        ),
        "expected_opponents": {str(value) for value in row["opponents"]},
        "expected_supported_decks_sha256": file_sha256(supported_path),
        "expected_split": str(row["split"]),
        "expected_opening_schedule": row.get("opening_schedule", "fixed-template"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--training-shard", type=int, choices=(0, 1, 2))
    stage.add_argument("--development-selection", action="store_true")
    stage.add_argument("--probability-calibration", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol = load_protocol(args.protocol, root)
    if args.training_shard is not None:
        rows = protocol.get("training")
        if not isinstance(rows, list) or len(rows) != 3:
            raise TypeError("protocol training rows are malformed")
        row = rows[args.training_shard]
    elif args.development_selection:
        row = protocol.get("development_selection")
    else:
        row = protocol.get("probability_calibration")
    if not isinstance(row, dict):
        raise TypeError("protocol collection stage is malformed")
    output = root / str(row["audit_report"])
    if output.exists():
        raise SystemExit("refusing to overwrite procedural stage audit")
    report = audit(
        [root / str(row["output_corpus"])],
        **shard_expectations(protocol, row, root=root),
    )
    if int(report["episodes"]) != int(row["expected_games"]):
        raise RuntimeError("audited stage does not match frozen game budget")
    _atomic_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
