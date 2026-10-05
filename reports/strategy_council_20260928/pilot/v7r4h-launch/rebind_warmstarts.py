#!/usr/bin/env python3
"""Reuse each seed's existing v7r1 warm start in the v7r4h pilot (no collection, no fit).

For one seed this opens the v7r4h pilot budget ledger and runs, as its recorded
child, council_pilot.rebind_warmstart_initialization: the v7r1 scripted.pt and
scripted-random-control.pt are verified against their own warm-start receipt
(runs/s290x/seed-290x/initialization/scripted-demonstrations/result.json and
plan.json in pilot/v7r1-launch), then re-published in
pilot/v7r4h-launch/runs/s290x/seed-290x/initialization with identical weights
(state digests checked) and only the two binding fields changed: the
pilot-runtime-v5 freeze digest and a BudgetSnapshot of the v7r4h ledger, which
the admission-bound validate_council_initial_policy requires. The new
scripted-demonstrations/result.json is the rebind receipt; run_council_pilot.py
reads its checkpoint/control digests and therefore never starts a warm start.
The v7r1 files are only read.

Idempotent: an existing, hash-consistent rebind receipt is reported and kept.
Run with the pilot-runtime-v5 interpreter and import path (launch.sh does).
Usage: rebind_warmstarts.py --config CFG --seed SEED [--source DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RC = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928")
V7R1_RUNS = RC / "pilot/v7r1-launch/runs"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_dir(seed: int) -> Path:
    return V7R1_RUNS / f"s{seed}" / f"seed-{seed}" / "initialization"


def verify_rebind(config, config_path: Path, seed: int, source: Path) -> dict:
    """Hash chain: v7r1 receipt -> v7r1 files -> rebind receipt -> v7r4h files."""
    import torch

    from clasher.rl.council_pilot import WARMSTART_REBIND_SCHEMA, state_dict_sha256

    target = Path(config.output_dir) / f"seed-{seed}" / "initialization"
    receipt = json.loads((target / "scripted-demonstrations" / "result.json").read_text())
    original_path = source / "scripted-demonstrations" / "result.json"
    original = json.loads(original_path.read_text())
    checks = {
        "rebind receipt schema": receipt.get("schema") == WARMSTART_REBIND_SCHEMA,
        "rebind receipt binds this config": receipt.get("pilot_config_sha256") == sha(config_path),
        "source receipt digest": receipt["source_result_sha256"] == sha(original_path),
        "source scripted.pt == v7r1 receipt": sha(original["checkpoint"])
        == original["checkpoint_sha256"],
        "source control == v7r1 receipt": sha(original["control_checkpoint"])
        == original["control_checkpoint_sha256"],
        "rebound scripted.pt digest": sha(target / "scripted.pt") == receipt["checkpoint_sha256"],
        "rebound control digest": sha(target / "scripted-random-control.pt")
        == receipt["control_checkpoint_sha256"],
        "receipt paths are the v7r4h files": Path(receipt["checkpoint"]) == target / "scripted.pt"
        and Path(receipt["control_checkpoint"]) == target / "scripted-random-control.pt",
        "not fitted, no demonstrations": receipt["fitted"] is False
        and receipt["demonstrations_collected"] is False,
        "rebind receipt pins == v7r4h freeze": receipt["source_pins_sha256"]
        == sha(Path(config.source_pins_path)),
    }
    states = {}
    for name, key in (("scripted.pt", "checkpoint"), ("scripted-random-control.pt", "control_checkpoint")):
        old = torch.load(original[key], map_location="cpu", weights_only=False)
        new = torch.load(target / name, map_location="cpu", weights_only=False)
        old_state = state_dict_sha256(old["model_state_dict"])
        new_state = state_dict_sha256(new["model_state_dict"])
        states[name] = new_state
        checks[f"{name}: weights identical to v7r1 (state digest)"] = old_state == new_state
        checks[f"{name}: binding fields updated"] = (
            new["source_pins_sha256"] == sha(Path(config.source_pins_path))
            and Path(new["resource_budget"]["ledger_path"])
            == (Path(config.output_dir) / "resource-budget.json").resolve()
            and new["resource_budget"]["active_job"] is not None
        )
    return {"checks": checks, "state_sha256": states, "receipt": receipt}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    from clasher.rl.council_pilot import (
        load_pilot_config,
        pilot_environment,
        rebind_warmstart_initialization,
    )

    config = load_pilot_config(args.config)
    source = (args.source or source_dir(args.seed)).resolve()
    admission = Path(config.nominal_admission_path)
    if args.child:
        receipt = rebind_warmstart_initialization(
            config_path=args.config, admission_path=admission, seed=args.seed, source_dir=source
        )
        print(json.dumps({k: receipt[k] for k in ("checkpoint", "checkpoint_sha256",
                                                   "control_checkpoint", "control_checkpoint_sha256")}, indent=2))
        return
    target = Path(config.output_dir) / f"seed-{args.seed}" / "initialization"
    result = target / "scripted-demonstrations" / "result.json"
    if not result.exists():
        from clasher.rl.council_budget import LocalPilotBudget

        target.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
                   "--config", str(args.config.resolve()), "--seed", str(args.seed),
                   "--source", str(source)]
        with LocalPilotBudget(
            Path(config.output_dir),
            config_sha256=sha(args.config),
            cpu_core_hour_ceiling=config.cpu_core_hour_ceiling,
            accelerator_hour_ceiling=config.accelerator_hour_ceiling,
        ) as budget, (target / "rebind.log").open("a") as log:
            budget.run(command, cwd=Path(config.gamedata_path).parent,
                       env=pilot_environment(config), log=log, cpu_cores=1)
    report = verify_rebind(config, args.config, args.seed, source)
    ok = all(report["checks"].values())
    for name, passed in report["checks"].items():
        print(("PASS " if passed else "FAIL ") + f"s{args.seed} rebind: {name}", flush=True)
    print(json.dumps({"seed": args.seed, "status": "passed" if ok else "failed",
                      "state_sha256": report["state_sha256"],
                      "checkpoint_sha256": report["receipt"]["checkpoint_sha256"],
                      "control_checkpoint_sha256": report["receipt"]["control_checkpoint_sha256"]}, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
