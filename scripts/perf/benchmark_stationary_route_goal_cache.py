#!/usr/bin/env python3
"""Run stationary rollouts with explicit native route-goal caching."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import pathfinding


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--native-route-goal-cache",
        choices=("off", "on"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    pathfinding._USE_NATIVE_ROUTE_GOAL_CACHE = args.native_route_goal_cache == "on"
    pathfinding._cached_native_route_goal_cell_units.cache_clear()
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
