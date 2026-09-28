"""Select deterministic replay probes for a prospective reconstruction backend."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from clasher.replay_timeline import import_replay_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.shard.read_bytes()).hexdigest()
    if digest != args.sha256:
        raise ValueError("source hash mismatch")
    args.output.mkdir(exist_ok=False)
    selected = {}
    counts = Counter()
    first_ability_times = []
    for batch in pq.ParquetFile(args.shard).iter_batches(
        batch_size=64, columns=["payload_json"]
    ):
        for row in batch.to_pylist():
            payload = row["payload_json"]
            for _ in range(3):
                if not isinstance(payload, str):
                    break
                payload = json.loads(payload)
            timeline = import_replay_payload(payload)
            counts["replays"] += 1
            abilities = [a for a in timeline.actions if a.kind == "activate_ability"]
            if abilities:
                first = abilities[0]
                first_ability_times.append(first.tick / 20)
                counts["events_before_first_ability"] += next(
                    i
                    for i, a in enumerate(timeline.actions)
                    if a.kind == "activate_ability"
                )
            else:
                counts["events_in_ability_free_replays"] += len(timeline.actions)
            keys = [c.key for c in (*timeline.team_deck, *timeline.opponent_deck)]
            roles = {
                "no_ability_events": not abilities and bool(timeline.actions),
                "one_unconfirmed_ability_candidate": any(
                    len(a.ability_candidates) == 1
                    and not a.ability_source_authoritative
                    for a in abilities
                ),
                "multiple_ability_candidates": any(
                    len(a.ability_candidates) > 1 for a in abilities
                ),
                "hero_and_evolution_decks": any(k.endswith("-hero") for k in keys)
                and any(k.endswith("-ev1") for k in keys),
                "mirror_deck": "mirror" in keys,
                "same_tick_commands": len({a.tick for a in timeline.actions})
                < len(timeline.actions),
            }
            for role, present in roles.items():
                counts[role] += int(present)
                if present and role not in selected:
                    filename = f"{role}.json"
                    (args.output / filename).write_text(
                        timeline.model_dump_json(indent=2) + "\n"
                    )
                    selected[role] = {
                        "file": filename,
                        "payload_sha256": timeline.payload_sha256,
                        "actions": len(timeline.actions),
                        "reconstruction_gaps": timeline.reconstruction_gaps(),
                    }
    report = {
        "source_sha256": digest,
        "counts": dict(counts),
        "selected": selected,
        "median_first_ability_seconds": (statistics.median(first_ability_times) if first_ability_times else None),
        "status": "probe_inputs_only_no_backend_executed",
        "limits": [
            "Action prefixes are only potential reconstruction windows, not trusted observations.",
            "No-ability events do not prove complete or correctly reconstructed matches.",
            "All timing, forms and terminal outcomes still require backend/reference validation.",
        ],
    }
    (args.output / "selection.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
