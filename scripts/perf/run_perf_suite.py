#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.benchmark import run_async_queue_benchmark, run_env_benchmark


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run local perf suite and write JSON report")
    p.add_argument("--out", type=str, default="reports/perf_baseline_m4.json")
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--decks-path", type=str, default="decks.json")
    p.add_argument("--engine-fast-path", choices=["off", "shadow", "on"], default="off")
    p.add_argument("--quiet-engine", action="store_true")
    p.add_argument("--env-decisions", type=int, default=16384)
    p.add_argument("--async-actors", type=int, default=8)
    p.add_argument("--async-transitions", type=int, default=32768)
    p.add_argument("--actor-rollout-steps", type=int, default=128)
    p.add_argument("--queue-size", type=int, default=32)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    resolved_decks = resolve_decks_path(args.decks_path, must_exist=True)

    env_metrics = run_env_benchmark(
        seed=args.seed,
        decisions=args.env_decisions,
        decks_path=str(resolved_decks),
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=args.quiet_engine,
        engine_fast_path=args.engine_fast_path,
    )
    async_metrics = run_async_queue_benchmark(
        seed=args.seed,
        num_actors=args.async_actors,
        transitions_target=args.async_transitions,
        actor_rollout_steps=args.actor_rollout_steps,
        queue_size=args.queue_size,
        decks_path=str(resolved_decks),
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=args.quiet_engine,
        engine_fast_path=args.engine_fast_path,
        inference_mode="actor_local",
    )

    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "host_profile": "m4_24gb_target",
        "engine_fast_path": args.engine_fast_path,
        "env": env_metrics,
        "async_queue": async_metrics,
    }
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote={out_path}")


if __name__ == "__main__":
    main()
