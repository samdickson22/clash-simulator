#!/usr/bin/env python3
"""Run the stationary-rollout driver with an explicit target crossover."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import entities


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--target-vector-min-size", type=int, required=True)
    args, remaining = parser.parse_known_args()
    entities._FAST_TARGET_VECTOR_MIN_SIZE = args.target_vector_min_size
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
