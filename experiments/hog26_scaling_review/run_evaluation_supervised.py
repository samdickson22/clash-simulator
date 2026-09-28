"""Run the opened diagnostic only after the full fitting audit and review."""

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil
from review_completed import SEEDS, sha
from review_plan import validate_review_plan

ROOT = Path("/Users/sam/.codex/worktrees/clasher-event-policy")
MONITOR = Path("/Users/sam/Library/Application Support/ClasherMonitor")
LIMIT_BYTES = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), fitting_allowed=False)
    path = MONITOR / "comparison-status.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(fields, indent=2) + "\n")
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    os.chdir(ROOT)
    lock = (MONITOR / "comparison.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    _, paired_plan_hash = validate_review_plan(ROOT)
    review_path = ROOT / "reports/hog26_scaling_completed_comparison_review_20260912.json"
    review = json.loads(review_path.read_text())
    if (review["status"] != "completed-fitting-review" or set(review["models"]) != set(SEEDS)
            or review["acceptance"] is not False):
        raise ValueError("complete three-model fitting review required")
    for path, expected in review["resources"].items():
        if sha(Path(path)) != expected:
            raise ValueError("reviewed fitting resource changed")
    sys.path.insert(0, str(ROOT / "experiments/hog26_scaling_eval"))
    from fit_authority import pin_fits

    pin_fits(ROOT)
    output = ROOT / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    log_path = output.with_suffix(".log")
    if output.exists() or log_path.exists():
        raise ValueError("existing evaluation output requires review")
    environment = dict(
        os.environ, OMP_NUM_THREADS="1",
        PYTHONPATH=("experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:"
                    "experiments/hog26_scaling_fit:experiments/hog26_data_scaling:"
                    "experiments/hog26_scalar_pilot:src:."),
    )
    command = [
        "/Users/sam/Desktop/code/clasher/.venv/bin/python",
        "experiments/hog26_scaling_eval/evaluate_scaling.py",
        "--data", "datasets/derived/hog26_seed_transfer_seed1279601_20260911",
        "--plan", "reports/hog26_seed_transfer_frozen_plan_20260911.json",
        "--preflight", "reports/hog26_seed_transfer_preflight_pin_20260911.json",
        "--output", str(output),
    ]
    peak, killed = 0, False
    with log_path.open("x") as log:
        process = subprocess.Popen(command, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        status(stage="scaling-seed-transfer-evaluation", pid=process.pid,
               log=str(log_path), fitting_review_sha256=sha(review_path),
               paired_review_plan_sha256=paired_plan_hash,
               memory_limit_bytes=LIMIT_BYTES)
        while process.poll() is None:
            try:
                live = psutil.Process(process.pid)
                rss = live.memory_info().rss + sum(c.memory_info().rss for c in live.children(recursive=True))
                peak = max(peak, rss)
            except psutil.NoSuchProcess:
                pass
            if peak > LIMIT_BYTES:
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
    complete = output / "complete.json"
    if code != 0 or not complete.is_file():
        status(stage="failed", operation="scaling-seed-transfer-evaluation",
               exit_code=code, peak_rss_bytes=peak, memory_limit_terminated=killed,
               log=str(log_path))
        raise SystemExit(code or 1)
    value = json.loads(complete.read_text())
    if value != {"status": "frozen-model-diagnostic-complete", "fits_evaluated": 20,
                 "fitting": False, "acceptance": False}:
        status(stage="failed", operation="scaling-seed-transfer-evaluation",
               reason="completion contract differs", peak_rss_bytes=peak, log=str(log_path))
        raise SystemExit(1)
    status(stage="scaling-seed-transfer-complete-awaiting-review",
           output=str(output), peak_rss_bytes=peak, fits_evaluated=20)


if __name__ == "__main__":
    main()
