"""Validate a pinned replay shard and save a few form-preserving timelines."""

import argparse
import hashlib
import json
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
        raise ValueError("shard hash mismatch")
    args.output.mkdir(exist_ok=False)
    counts, gaps, errors = Counter(), Counter(), Counter()
    sample_errors = []
    for batch in pq.ParquetFile(args.shard).iter_batches(
        batch_size=64, columns=["payload_json"]
    ):
        for row in batch.to_pylist():
            counts["source_replays"] += 1
            try:
                payload = row["payload_json"]
                for _ in range(3):
                    if not isinstance(payload, str):
                        break
                    payload = json.loads(payload)
                timeline = import_replay_payload(payload)
            except (ValueError, TypeError, KeyError) as error:
                errors[type(error).__name__] += 1
                if len(sample_errors) < 5:
                    sample_errors.append(str(error)[:1800])
                continue
            counts["imported"] += 1
            counts["actions"] += len(timeline.actions)
            gaps.update(timeline.reconstruction_gaps())
            if counts["imported"] <= 3:
                (args.output / f"sample-{counts['imported']}.json").write_text(
                    timeline.model_dump_json(indent=2) + "\n"
                )
    result = {
        "counts": dict(counts),
        "gap_counts": dict(gaps),
        "error_counts": dict(errors),
        "sample_errors": sample_errors,
        "training_admission": False,
        "source_sha256": digest,
    }
    (args.output / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
