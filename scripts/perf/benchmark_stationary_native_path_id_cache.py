#!/usr/bin/env python3
"""Run stationary rollouts with explicit native path-ID cache behavior."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import native_tilemap


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--native-path-id-cache",
        choices=("off", "on"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    native_tilemap._USE_NATIVE_PATH_ID_CELL_CACHE = args.native_path_id_cache == "on"
    native_tilemap._nearest_native_path_id_for_cell.cache_clear()
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
