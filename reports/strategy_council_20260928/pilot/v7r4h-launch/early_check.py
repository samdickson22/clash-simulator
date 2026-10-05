#!/usr/bin/env python3
"""Early check of one v7r4h run (PPO from the human prior, scripted-arm slot;
monitoring/report only; never stops training).

With the v7r4h critic warm-up of 60 updates (64 envs x 128 steps = 8,192
decisions per update) the actor is frozen until 491,520 decisions, so the
first window plays the human-imitation checkpoint itself. This compares
training against that first window:

* training win rate vs the fixed public scripts, from the opponent outcome
  logs: games assigned in the first window (the critic warm-up, actor frozen =
  human-prior policy; max(warm-up, 20) updates, so decisions < 491,520) versus
  games assigned in the latest window (up to the last 20 updates before the
  check point, never overlapping the first window). Bar: current >= first.
* wait probability: the monitor's per-update wait frequency at decisions where
  a play was legal (on-policy estimate of mean pi(wait | s)), pooled over the
  same latest window. Bar: >= 0.2. (The human prior starts near 0.95; the
  diagnosis-1M collapse direction is a fall toward ~0.03.)

launch.sh starts it at 655,360 (20 actor updates after the warm-up) and
819,200 decisions (40 actor updates). The bars are seed-unstable signals, not
stop rules. Writes logs/early-check-s{seed}-{decisions}.json with open("x");
exit code 0 even on a failed bar, 2 on error.

Usage: early_check.py --config CFG --seed SEED [--decisions N] [--wait]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROLLOUT_STEPS = 128
FIRST_WINDOW_UPDATES = 20
MIN_WAIT_PROBABILITY = 0.2


def wilson(wins: int, games: int) -> list[float] | None:
    if not games:
        return None
    z, p = 1.96, wins / games
    centre = (p + z * z / (2 * games)) / (1 + z * z / games)
    half = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / (1 + z * z / games)
    return [round(centre - half, 4), round(centre + half, 4)]


def monitor_rows(path: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("event") is None and "update" in row:
                    rows[int(row["update"])] = row  # a resumed segment overwrites
    return rows


def outcomes(directory: Path) -> list[dict]:
    records = []
    for path in sorted(directory.glob("worker-*-outcomes.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def summary(records: list[dict], labels: dict[str, str]) -> dict:
    from clasher.rl.council_monitor import results_by_opponent

    table = results_by_opponent(records, labels)
    for entry in table.values():
        entry["wilson95"] = wilson(entry["wins"], entry["games"])
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--arm", default="scripted", choices=("scripted", "scratch"))
    parser.add_argument("--decisions", type=int, default=655_360)
    parser.add_argument("--wait", action="store_true", help="poll until the check point is reached")
    parser.add_argument("--poll-seconds", type=int, default=120)
    parser.add_argument("--max-wait-hours", type=float, default=36.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from clasher.rl.council_monitor import initial_opponent_labels
    from clasher.rl.council_pilot import critic_warmup_updates_for_arm, load_pilot_config

    config = load_pilot_config(args.config)
    arm_dir = Path(config.output_dir) / f"seed-{args.seed}" / args.arm
    output = args.output or KIT / "logs" / f"early-check-s{args.seed}-{args.decisions}.json"
    if output.exists():
        print(f"early check already written: {output}")
        return
    per_update = config.num_envs * ROLLOUT_STEPS
    monitor_path = arm_dir / "training-monitor.jsonl"
    deadline = time.time() + args.max_wait_hours * 3600
    while True:
        rows = monitor_rows(monitor_path)
        reached = [u for u, r in rows.items() if r["learner_decisions"] >= args.decisions]
        if reached or not args.wait or time.time() > deadline:
            break
        time.sleep(args.poll_seconds)
    if not reached:
        print(f"check point {args.decisions} not reached yet in {monitor_path}", file=sys.stderr)
        sys.exit(2)
    check_update = min(reached)
    warmup = critic_warmup_updates_for_arm(config, args.arm)
    first_end = max(warmup, FIRST_WINDOW_UPDATES) * per_update
    current_start = max(first_end, args.decisions - FIRST_WINDOW_UPDATES * per_update)
    pool = arm_dir / "opponents" / "pool.json"
    labels = initial_opponent_labels(pool) if pool.exists() else {}
    records = [r for r in outcomes(arm_dir / "opponents")
               if r.get("learner_decisions_at_assignment", 0) < args.decisions]
    first = [r for r in records if r["learner_decisions_at_assignment"] < first_end]
    current = [r for r in records if current_start <= r["learner_decisions_at_assignment"] < args.decisions]
    first_table, current_table = summary(first, labels), summary(current, labels)

    def pooled_wait(lo: int, hi: int):
        waits = playable = 0.0
        for row in rows.values():
            if lo < row["learner_decisions"] <= hi and row.get("wait_probability") is not None:
                waits += row["wait_probability"] * row["playable_decisions"]
                playable += row["playable_decisions"]
        return (waits / playable if playable else None), int(playable)

    wait_first, playable_first = pooled_wait(0, first_end)
    wait_current, playable_current = pooled_wait(current_start, args.decisions)
    script_first = first_table.get("script", {}).get("win_rate")
    script_current = current_table.get("script", {}).get("win_rate")
    bars = {
        "script_win_rate_not_below_first_window": None
        if script_first is None or script_current is None
        else script_current >= script_first,
        "wait_probability_at_least_0.2": None
        if wait_current is None
        else wait_current >= MIN_WAIT_PROBABILITY,
    }
    status = (
        "insufficient-data" if any(v is None for v in bars.values())
        else "pass" if all(bars.values()) else "fail"
    )
    latest = rows[check_update]
    report = {
        "schema": "council-pilot-v7r4h-early-check-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "monitoring_only": True,
        "action_taken": "none (training continues; decisions are manual)",
        "seed": args.seed,
        "arm": args.arm,
        "config": str(args.config),
        "check_decisions": args.decisions,
        "check_update": check_update,
        "learner_decisions_at_check_update": latest["learner_decisions"],
        "critic_warmup_updates": warmup,
        "actor_updates_before_check": max(0, check_update - warmup),
        "initialization": "human prior (human-bc-natural-seed2903.pt; research artifact, not a Tier A admitted arm)",
        "first_window": {"decisions": [0, first_end], "updates": first_end // per_update,
                         "note": "critic warm-up, actor frozen (initializer policy)" if warmup >= FIRST_WINDOW_UPDATES
                         else "no critic warm-up: first 20 updates from the initializer (actor already moving)"},
        "current_window": {"decisions": [current_start, args.decisions]},
        "status": status,
        "bars": bars,
        "script_win_rate": {
            "first_window": script_first,
            "current_window": script_current,
            "first_window_games": first_table.get("script", {}).get("games", 0),
            "current_window_games": current_table.get("script", {}).get("games", 0),
            "first_window_wilson95": first_table.get("script", {}).get("wilson95"),
            "current_window_wilson95": current_table.get("script", {}).get("wilson95"),
        },
        "wait_probability": {
            "first_window": wait_first,
            "current_window": wait_current,
            "first_window_playable_decisions": playable_first,
            "current_window_playable_decisions": playable_current,
            "threshold": MIN_WAIT_PROBABILITY,
            "estimator": "on-policy wait frequency at decisions with a legal play",
        },
        "training_results_by_opponent": {"first_window": first_table, "current_window": current_table},
        "play_when_held_by_cost_at_check": latest.get("play_when_held_by_cost"),
        "entropy_at_check": latest.get("window_entropy"),
        "active_alarms_at_check": latest.get("active_alarms"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"output": str(output), "status": status, "bars": bars,
                      "script_win_rate": report["script_win_rate"],
                      "wait_probability": report["wait_probability"]}, indent=2))


if __name__ == "__main__":
    main()
