#!/usr/bin/env python3
"""Automatic correctness gate after the smoke (config.smoke_decisions = 98,304) of one (seed, arm).

Correctness only, never strength. Checks: every budget job completed; the
warm-start receipt hashes match and validation accuracy beats the untrained
control; the smoke milestone exists with the right council recipe; the train
logs show no NaN and rejected_actions=0; every launch receipt's source pins
equal the pilot-runtime-v1 freeze. At 64 envs the scripted smoke is
critic-only (20 warm-up updates = 163,840 decisions). Run with the runtime
interpreter (launch.sh does).
Writes only --output (open("x")).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

V7 = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r1-launch")
PINS = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v1/pilot-source-pins.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--arm", choices=("scripted", "scratch"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    import torch

    from clasher.rl.council_pilot import load_pilot_config

    config = load_pilot_config(args.config)
    run = Path(config.output_dir)
    arm_dir = run / f"seed-{args.seed}" / args.arm
    init = run / f"seed-{args.seed}" / "initialization"
    results: list[tuple[str, bool, object]] = []

    def check(name, ok, detail=None):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ("" if detail is None else f"  [{detail}]"), flush=True)

    budget = json.loads((run / "resource-budget.json").read_text())
    statuses = sorted({job["status"] for job in budget["jobs"]})
    check("all budget jobs completed", statuses == ["completed"], statuses)

    receipt = json.loads((init / "scripted-demonstrations" / "result.json").read_text())
    check("warm-start checkpoint hashes match receipt",
          sha(Path(receipt["checkpoint"])) == receipt["checkpoint_sha256"]
          and sha(Path(receipt["control_checkpoint"])) == receipt["control_checkpoint_sha256"])
    fit = receipt["fit"]
    # The warm-start receipt nests accuracies under fit["metrics"] (fixed 2026-09-30).
    metrics = {**fit, **fit.get("metrics", {})}
    check("warm-start validation accuracy > matched control",
          metrics.get("validation_accuracy", -1) > metrics.get("control_validation_accuracy", 2),
          f"{metrics.get('validation_accuracy')} vs {metrics.get('control_validation_accuracy')}")
    check("warm-start corpus within 500k decisions", receipt["corpus"]["decisions"] <= 500_000, receipt["corpus"]["decisions"])

    milestone = arm_dir / f"policy_decisions_{config.smoke_decisions:09d}.pt"
    if milestone.exists():
        payload = torch.load(milestone, map_location="cpu", weights_only=False)
        recipe = payload.get("council_recipe") or {}
        expected = 20 if args.arm == "scripted" else 0
        check("smoke milestone recipe", recipe.get("arm") == args.arm
              and recipe.get("critic_warmup_updates") == expected
              and recipe.get("target_kl") == 0.02, recipe)
        check("smoke milestone bound to config", payload.get("council_config_sha256") == sha(args.config))
    else:
        check("smoke milestone exists", False, str(milestone))

    logs = sorted(arm_dir.glob("train-*.log"))
    text = "\n".join(p.read_text(errors="replace") for p in logs)
    update_lines = [line for line in text.splitlines() if "rejected_actions=" in line]
    rejected = [int(m) for m in re.findall(r"rejected_actions=(\d+)", text)]
    check("train logs have update lines", bool(update_lines), len(update_lines))
    check("rejected_actions=0 on every update", bool(rejected) and max(rejected) == 0, max(rejected) if rejected else None)
    check("no NaN/inf in update lines", not any(re.search(r"\b(nan|inf)\b", line, re.I) for line in update_lines))
    check("training-monitor.jsonl has rows", any(p.stat().st_size > 0 for p in arm_dir.rglob("training-monitor.jsonl")))

    pins = {str(Path(k).resolve()): v for k, v in json.loads(PINS.read_text()).items()}
    launches = sorted(arm_dir.glob("launch-*.json"))
    check("launch receipts present", bool(launches), len(launches))
    check("launch source pins == pilot-runtime-v1 freeze",
          all({str(Path(k).resolve()): v for k, v in json.loads(p.read_text())["source_pins"].items()} == pins for p in launches))

    ok = all(r[1] for r in results)
    if args.output is not None:
        with args.output.open("x") as stream:
            json.dump({"status": "passed" if ok else "failed", "seed": args.seed, "arm": args.arm,
                       "checks": [{"check": n, "ok": o, "detail": str(d) if d is not None else None} for n, o, d in results]},
                      stream, indent=2)
            stream.write("\n")
    print(f"smoke check {'passed' if ok else 'failed'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
