#!/usr/bin/env python3
"""Audit one explicit post-deployment tick window for all enabled 1v1 pairs."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from clasher.torch_sim.manifest_audit import audit_enabled_one_vs_one


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--ticks", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--skip-structured-observations", action="store_true")
    parser.add_argument("--jsonl-out", type=Path)
    args = parser.parse_args()

    audit = audit_enabled_one_vs_one(
        decks_path=args.decks_path,
        ticks=args.ticks,
        device=args.device,
        compare_structured_observations=not args.skip_structured_observations,
    )
    if args.jsonl_out is not None:
        args.jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        with args.jsonl_out.open("w", encoding="utf-8") as output:
            for row in audit.rows:
                output.write(json.dumps(asdict(row), sort_keys=True) + "\n")
    summary = audit.summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return int(summary["oracle_mismatches"] > 0 or summary["execution_error_pairs"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
