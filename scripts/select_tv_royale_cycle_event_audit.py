from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.extract_tv_royale_youtube_fullmatch import _atomic_json, _sha256

SCHEMA = "clasher.youtube.cycle_event_audit_selection.v1"


def select_stratified_events(
    events: list[dict[str, Any]],
    *,
    count: int,
    seed: int,
    excluded: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if count <= 0:
        raise ValueError("audit count must be positive")
    excluded = excluded or []
    eligible = [
        row
        for row in events
        if row.get("play_confirmed") and row.get("identity_valid")
        and not any(
            int(row["player_id"]) == int(gold["player_id"])
            and abs(int(row["timestamp_ms"]) - int(gold["timestamp_ms"])) <= 1_000
            for gold in excluded
            if gold.get("play_valid")
        )
    ]
    if not eligible:
        return []
    maximum_timestamp = max(int(row["timestamp_ms"]) for row in eligible)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        time_bin = min(3, int(row["timestamp_ms"]) * 4 // max(maximum_timestamp, 1))
        buckets[(int(row["player_id"]), time_bin)].append(row)
    for key, rows in buckets.items():
        rows.sort(
            key=lambda row: hashlib.sha256(
                f"{seed}:{key}:{row['event_id']}".encode()
            ).digest()
        )
    selected: list[dict[str, Any]] = []
    keys = sorted(buckets)
    while len(selected) < min(count, len(eligible)):
        progressed = False
        for key in keys:
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop(0))
                progressed = True
        if not progressed:
            break
    return sorted(selected, key=lambda row: int(row["timestamp_ms"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1065001)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.events.read_text(encoding="utf-8"))
    if payload.get("schema") not in {
        "clasher.youtube.hud_cycle_events.v2",
        "clasher.youtube.hud_cycle_events.v3",
    }:
        raise ValueError("unsupported cycle-event artifact")
    gold_rows = (
        []
        if args.gold is None
        else json.loads(args.gold.read_text(encoding="utf-8"))["labels"]
    )
    selected = select_stratified_events(
        payload["events"], count=args.count, seed=args.seed, excluded=gold_rows
    )
    labels = [
        {
            **row,
            "label_id": row["event_id"],
            "observed_elixir_drop": row["observed_public_elixir_drop"],
        }
        for row in selected
    ]
    output = {
        "schema": SCHEMA,
        "source_events_sha256": _sha256(args.events),
        "excluded_gold_sha256": None if args.gold is None else _sha256(args.gold),
        "seed": args.seed,
        "requested_count": args.count,
        "labels": labels,
    }
    _atomic_json(args.output, output)
    print(json.dumps({"output": str(args.output), "labels": len(labels)}, indent=2))


if __name__ == "__main__":
    main()
