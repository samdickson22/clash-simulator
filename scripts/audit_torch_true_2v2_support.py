#!/usr/bin/env python3
"""Print the exhaustive enabled-card true-team-2v2 capability boundary."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from clasher.torch_sim.two_vs_two_capability import (
    audit_enabled_true_two_vs_two_capability,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("decks.json"))
    parser.add_argument(
        "--matrix-output",
        type=Path,
        help="optional path for the complete enabled-card capability matrix",
    )
    args = parser.parse_args()

    report = audit_enabled_true_two_vs_two_capability(
        manifest_path=args.manifest,
    )
    if args.matrix_output is not None:
        args.matrix_output.write_text(
            json.dumps([asdict(row) for row in report.rows], indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report.summary(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
