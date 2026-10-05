#!/usr/bin/env python3
"""Freeze prospective strength rules or grade bound completed pilot evaluations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--freeze-protocol", action="store_true")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--evaluation-dir", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm", choices=("scripted", "scratch"))
    parser.add_argument("--seed-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from clasher.rl.council_evaluation import (
        evaluate_recipe,
        evaluate_seed,
        freeze_protocol,
    )

    if args.freeze_protocol:
        if args.config is None:
            parser.error("--freeze-protocol requires --config")
        from clasher.rl.council_pilot import load_pilot_config

        protocol = freeze_protocol(load_pilot_config(args.config))
        print(
            json.dumps(
                {
                    "status": "prospectively-frozen-no-outcomes",
                    "protocol_sha256": protocol.sha256,
                },
                indent=2,
            )
        )
        return
    if args.protocol is None or args.arm is None or args.output is None:
        parser.error("evaluation requires --protocol, --arm and --output")
    if args.seed_report:
        report = evaluate_recipe(args.protocol, args.seed_report, arm=args.arm)
    else:
        if args.evaluation_dir is None or args.seed is None:
            parser.error("seed evaluation requires --evaluation-dir and --seed")
        report = evaluate_seed(
            args.protocol, args.evaluation_dir, seed=args.seed, arm=args.arm
        )
    if args.output.exists():
        if json.loads(args.output.read_text()) != report:
            raise ValueError(
                "existing strength report differs from verified current results"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(
        json.dumps(
            {"status": report["status"], "promotion_authorized": False}, indent=2
        )
    )


if __name__ == "__main__":
    main()
