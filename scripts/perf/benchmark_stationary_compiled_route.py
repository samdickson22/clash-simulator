#!/usr/bin/env python3
"""Run stationary rollouts with the Python or compiled exact route heap."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import pathfinding


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--route-kernel",
        choices=("python", "compiled"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    if (
        args.route_kernel == "compiled"
        and pathfinding._compiled_standard_grid_route_indices is None
    ):
        raise RuntimeError("Numba route accelerator is unavailable")
    pathfinding._USE_COMPILED_STANDARD_ROUTE = args.route_kernel == "compiled"
    pathfinding._cached_standard_grid_route.cache_clear()
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
