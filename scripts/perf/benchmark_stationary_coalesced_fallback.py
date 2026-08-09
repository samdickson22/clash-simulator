#!/usr/bin/env python3
"""Run stationary rollouts with explicit Crown-fallback scan behavior."""

from __future__ import annotations

import argparse
import sys

import benchmark_stationary_rollout

from clasher import entities


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--coalesced-fallback-scan",
        choices=("off", "on"),
        required=True,
    )
    args, remaining = parser.parse_known_args()
    entities._COALESCE_CROWN_FALLBACK_TARGET_SCAN = (
        args.coalesced_fallback_scan == "on"
    )
    sys.argv = [sys.argv[0], *remaining]
    benchmark_stationary_rollout.main()


if __name__ == "__main__":
    main()
