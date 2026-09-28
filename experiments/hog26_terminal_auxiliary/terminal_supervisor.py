"""Run one frozen residual stage under the shared lock and measured RSS guard."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
import torch
from terminal_contract import MEMORY_LIMIT, load_plan
from terminal_experiment import validate_readiness
from terminal_labels import sha

ROOT = Path(__file__).resolve().parents[2]
MONITOR = Path("/Users/sam/Library/Application Support/ClasherMonitor")


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid())
    path = MONITOR / "comparison-status.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(fields, indent=2) + "\n")
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("memory", "fit"), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    lock = (MONITOR / "comparison.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    torch.set_num_threads(1)
    plan_path = ROOT / "reports/hog26_terminal_auxiliary_frozen_plan_20260912.json"
    plan = load_plan(plan_path)
    readiness = ROOT / "reports/hog26_terminal_auxiliary_readiness_20260912.json"
    if args.mode == "fit":
        validate_readiness(readiness, plan, plan_path)
    output = ROOT / ("reports/hog26_terminal_auxiliary_memory_20260912.json" if args.mode == "memory"
                     else "reports/hog26_terminal_auxiliary_comparison_20260912")
    log_path = ROOT / f"reports/hog26_terminal_auxiliary_{args.mode}_20260912.log"
    if output.exists() or log_path.exists():
        raise ValueError("existing residual output requires review")
    environment = dict(os.environ, OMP_NUM_THREADS="1",
                       PYTHONPATH=("experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:experiments/hog26_scaling_fit:"
                                   "experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:."))
    command = ["/Users/sam/Desktop/code/clasher/.venv/bin/python",
               "experiments/hog26_terminal_auxiliary/terminal_experiment.py", "--mode", args.mode,
               "--plan", str(plan_path), "--output", str(output)]
    if args.mode == "fit":
        command += ["--readiness", str(readiness)]
    peak, killed = 0, False
    with log_path.open("x") as log:
        process = subprocess.Popen(command, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        status(stage="auxiliary-" + args.mode, pid=process.pid, log=str(log_path),
               fitting_allowed=args.mode == "fit", plan_sha256=sha(plan_path),
               memory_limit_bytes=MEMORY_LIMIT)
        while process.poll() is None:
            try:
                live = psutil.Process(process.pid)
                rss = live.memory_info().rss + sum(c.memory_info().rss for c in live.children(recursive=True))
                peak = max(peak, rss)
            except psutil.NoSuchProcess:
                pass
            if peak > MEMORY_LIMIT:
                killed = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(2)
        code = process.wait()
    complete = output if args.mode == "memory" else output / "complete.json"
    if code != 0 or not complete.is_file():
        status(stage="failed", operation="auxiliary-" + args.mode, exit_code=code,
               peak_rss_bytes=peak, memory_limit_terminated=killed,
               log=str(log_path), fitting_allowed=False)
        raise SystemExit(code or 1)
    result = json.loads(complete.read_text())
    expected = "passed-auxiliary-memory-audit" if args.mode == "memory" else "auxiliary-terminal-comparison-complete"
    if result.get("status") != expected:
        status(stage="failed", operation="auxiliary-" + args.mode,
               reason="completion contract differs", fitting_allowed=False)
        raise SystemExit(1)
    status(stage="auxiliary-" + args.mode + "-complete-awaiting-review", output=str(output),
           peak_rss_bytes=peak, fitting_allowed=False)


if __name__ == "__main__":
    main()
