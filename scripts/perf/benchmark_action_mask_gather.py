#!/usr/bin/env python3
"""Benchmark exact canonical occupancy-mask gathering."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
from collections.abc import Callable

import numpy as np
from benchmark_action_mask import _prepare_battle, _run_decisions

from clasher.rl.action_space import DiscreteTileActionSpace


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--decisions", type=int, default=128)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-decisions", type=int, default=4)
    return parser.parse_args()


def _loop_gather(
    action_space: DiscreteTileActionSpace,
    world_mask: np.ndarray,
    player_id: int,
) -> np.ndarray:
    world_xy = action_space._world_tile_xy_by_player[player_id]
    out = np.zeros(world_xy.shape[0], dtype=np.bool_)
    for tile_idx in range(world_xy.shape[0]):
        wx = int(world_xy[tile_idx, 0])
        wy = int(world_xy[tile_idx, 1])
        out[tile_idx] = bool(world_mask[wy, wx])
    return out


def _install_mode(mode: str) -> None:
    def building(self, battle, player_id, size_tiles):
        world_mask = battle.get_building_placement_blocked_mask_world(size_tiles)
        if mode == "loop":
            return _loop_gather(self, world_mask, player_id)
        world_xy = self._world_tile_xy_by_player[player_id]
        return world_mask[world_xy[:, 1], world_xy[:, 0]]

    def troop(self, battle, player_id, mover_radius):
        world_mask = battle.get_troop_placement_blocked_mask_world(mover_radius)
        if mode == "loop":
            return _loop_gather(self, world_mask, player_id)
        world_xy = self._world_tile_xy_by_player[player_id]
        return world_mask[world_xy[:, 1], world_xy[:, 0]]

    building_method: Callable[..., np.ndarray] = building
    troop_method: Callable[..., np.ndarray] = troop
    DiscreteTileActionSpace._building_placement_blocked_mask_canonical = (
        building_method
    )
    DiscreteTileActionSpace._troop_placement_blocked_mask_canonical = troop_method


def _run(args: argparse.Namespace, mode: str) -> dict[str, float | str]:
    _install_mode(mode)
    battle = _prepare_battle(
        seed=args.seed,
        building_card="Cannon",
        hand_cards=["Cannon", "Knight", "Giant", "Fireball"],
        fast_path=True,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    if args.warmup_decisions:
        _run_decisions(
            action_space,
            battle,
            fast_path=True,
            decisions=args.warmup_decisions,
        )
    seconds, digest = _run_decisions(
        action_space,
        battle,
        fast_path=True,
        decisions=args.decisions,
    )
    return {
        "mode": mode,
        "seconds": seconds,
        "decisions_per_second": args.decisions / seconds,
        "sha256": digest,
    }


def main() -> None:
    args = _parse_args()
    rows = []
    for repetition in range(args.repetitions):
        order = ("loop", "gather") if repetition % 2 == 0 else ("gather", "loop")
        for mode in order:
            row = _run(args, mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("loop", "gather"):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    loop = float(summary["loop"]["seconds_median"])
    gather = float(summary["gather"]["seconds_median"])
    summary["gather_vs_loop_percent"] = 100.0 * (loop / gather - 1.0)
    print(
        json.dumps(
            {
                "machine": {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "processor": platform.processor(),
                },
                "config": vars(args),
                "rows": rows,
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
