"""Build deterministic frozen-archetype screen/quarantine deck pools."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signature(row: dict[str, Any]) -> str:
    canonical = json.dumps(sorted(row["cards"]), separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def split_decks(
    payload: dict[str, Any],
    *,
    excluded_signatures: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_archetype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["decks"]:
        if _signature(row) in excluded_signatures:
            continue
        by_archetype[str(row["archetype"])].append(dict(row))
    screen: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for archetype, rows in sorted(by_archetype.items()):
        ordered = sorted(rows, key=_signature)
        for index, row in enumerate(ordered):
            (screen if index % 3 == 0 else quarantine).append(row)
        if not any(row["archetype"] == archetype for row in screen):
            raise ValueError(f"screen split lost archetype {archetype}")
        if not any(row["archetype"] == archetype for row in quarantine):
            raise ValueError(f"quarantine split lost archetype {archetype}")

    def build(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
        total_weight = sum(float(row.get("sampling_weight", 1.0)) for row in rows)
        normalized = []
        for row in rows:
            item = dict(row)
            item["sampling_weight"] = float(
                row.get("sampling_weight", 1.0)
            ) / total_weight
            normalized.append(item)
        return {
            "schema_version": int(payload["schema_version"]),
            "metadata": {
                **dict(payload["metadata"]),
                "split": split,
                "split_authority": "hog26-action-value-frozen-archetype-v1",
                "split_rule": "sha256-card-signature-index-modulo-3",
            },
            "decks": normalized,
        }

    return build(screen, "action-value-screen"), build(
        quarantine, "action-value-quarantine"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--screen-out", type=Path, required=True)
    parser.add_argument("--quarantine-out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--exclude-signature", action="append", default=[])
    args = parser.parse_args()
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    excluded_signatures = frozenset(str(value) for value in args.exclude_signature)
    available_signatures = {_signature(row) for row in payload["decks"]}
    missing_exclusions = excluded_signatures.difference(available_signatures)
    if missing_exclusions:
        raise ValueError(
            "excluded gameplay signatures are absent from source: "
            f"{sorted(missing_exclusions)}"
        )
    screen, quarantine = split_decks(
        payload,
        excluded_signatures=excluded_signatures,
    )
    screen_signatures = {_signature(row) for row in screen["decks"]}
    quarantine_signatures = {_signature(row) for row in quarantine["decks"]}
    if screen_signatures.intersection(quarantine_signatures):
        raise ValueError("screen and quarantine deck signatures overlap")
    for path, result in (
        (args.screen_out, screen),
        (args.quarantine_out, quarantine),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    report = {
        "schema": "clasher.hog26_action_value_gameplay_splits.v1",
        "source": str(args.source.resolve()),
        "source_sha256": _sha256(args.source),
        "excluded_signatures": sorted(excluded_signatures),
        "excluded_decks": len(excluded_signatures),
        "screen": {
            "path": str(args.screen_out.resolve()),
            "sha256": _sha256(args.screen_out),
            "decks": len(screen["decks"]),
        },
        "quarantine": {
            "path": str(args.quarantine_out.resolve()),
            "sha256": _sha256(args.quarantine_out),
            "decks": len(quarantine["decks"]),
        },
        "signature_overlap": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
