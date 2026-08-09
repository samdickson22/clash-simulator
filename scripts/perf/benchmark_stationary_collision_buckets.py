#!/usr/bin/env python3
"""Run stationary rollouts with scalar or bucketed exact collision scans."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import battle


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--collision-candidates",
        choices=("scalar", "bucketed"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    battle._USE_COLLISION_BUCKET_CANDIDATES = (
        args.collision_candidates == "bucketed"
    )
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
