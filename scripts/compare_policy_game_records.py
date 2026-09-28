"""Compare two matched eval --games-json-out artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from clasher.paths import resolve_path
from clasher.rl.deck_benchmark import compare_game_records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    baseline = resolve_path(args.baseline, must_exist=True)
    candidate = resolve_path(args.candidate, must_exist=True)
    comparison = {
        "schema_version": 1,
        "baseline": str(baseline),
        "baseline_sha256": _sha256(baseline),
        "candidate": str(candidate),
        "candidate_sha256": _sha256(candidate),
        **compare_game_records(
            json.loads(baseline.read_text(encoding="utf-8")),
            json.loads(candidate.read_text(encoding="utf-8")),
        ),
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(comparison, sort_keys=True))


if __name__ == "__main__":
    main()
