#!/usr/bin/env python3
"""Run stationary rollouts with mapping or dense exact entity buckets."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import battle


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--entity-buckets",
        choices=("mapping", "dense"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    battle._USE_DENSE_ENTITY_BUCKETS = args.entity_buckets == "dense"
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
