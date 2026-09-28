"""Run complete-corpus cache extraction under the shared lock and 18 GiB guard."""

import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
import torch
from cache_contract import load_plan
from terminal_labels import sha

ROOT = Path(__file__).resolve().parents[2]
MONITOR = Path("/Users/sam/Library/Application Support/ClasherMonitor")
LIMIT = 18 * 1024**3


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
    torch.set_num_threads(1)
    plan_path = ROOT / "reports/hog26_expanded_feature_plan_20260913.json"
    load_plan(plan_path)
    output = ROOT / "reports/hog26_expanded_feature_cache_20260913"
    log_path = ROOT / "reports/hog26_expanded_feature_cache_20260913.log"
    if output.exists() or log_path.exists():
        raise ValueError("existing expanded cache output requires review")
    environment = dict(os.environ, OMP_NUM_THREADS="1", PYTHONPATH=(
        "experiments/hog26_expanded_corpus:experiments/hog26_streamed_features:"
        "experiments/hog26_parallel_expansion:experiments/hog26_parallel_collection_probe:"
        "experiments/hog26_training_expansion:experiments/hog26_data_scaling:"
        "experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:"
        "experiments/hog26_public_semantics:experiments/hog26_residual_margin:"
        "experiments/hog26_scalar_pilot:src:."))
    command = ["/Users/sam/Desktop/code/clasher/.venv/bin/python", "-u", "experiments/hog26_expanded_corpus/build_cache.py"]
    peak, killed = 0, False
    with log_path.open("x") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage="expanded-feature-cache", pid=process.pid, log=str(log_path), plan_sha256=sha(plan_path), memory_limit_bytes=LIMIT)
        while process.poll() is None:
            try:
                live = psutil.Process(process.pid)
                peak = max(peak, live.memory_info().rss + sum(c.memory_info().rss for c in live.children(recursive=True)))
            except psutil.NoSuchProcess:
                pass
            if peak > LIMIT:
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
        status(stage="expanded-feature-cache-failed", exit_code=code, peak_rss_bytes=peak,
               memory_limit_terminated=killed, log=str(log_path))
        raise SystemExit(code or 1)
    result = json.loads(complete.read_text())
    if result.get("status") != "complete-audited-expanded-feature-cache" or result.get("fitting_allowed") is not False:
        raise ValueError("expanded cache completion contract differs")
    status(stage="expanded-feature-cache-complete-awaiting-review", output=str(output), peak_rss_bytes=peak)


if __name__ == "__main__":
    main()
