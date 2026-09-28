"""Guard the single frozen residual diagnostic with the shared experiment lock."""

import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
from evaluate_weighted import check_resources, sources
from weighted_contract import MEMORY_LIMIT, sha

ROOT = Path(__file__).resolve().parents[2]
MONITOR = Path("/Users/sam/Library/Application Support/ClasherMonitor")


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
    pin_path = ROOT / "reports/hog26_weighted_margin_evaluation_pin_20260913.json"
    pin = json.loads(pin_path.read_text())
    if pin["evaluation_sources"] != sources():
        raise ValueError("residual evaluation source changed")
    check_resources(pin["resources"])
    output = ROOT / "reports/hog26_weighted_margin_seed_transfer_20260913"
    log_path = ROOT / "reports/hog26_weighted_margin_evaluation_20260913.log"
    if output.exists() or log_path.exists():
        raise ValueError("existing residual diagnostic output requires review")
    environment = dict(os.environ, OMP_NUM_THREADS="1", PYTHONPATH=(
        "experiments/hog26_weighted_margin_eval:experiments/hog26_weighted_margin:experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:"
        "experiments/hog26_scaling_review:experiments/hog26_scaling_eval:"
        "experiments/hog26_seed_transfer:experiments/hog26_scaling_fit:"
        "experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:."))
    command = ["/Users/sam/Desktop/code/clasher/.venv/bin/python",
               "experiments/hog26_weighted_margin_eval/evaluate_weighted.py", "--mode", "evaluate",
               "--pin", str(pin_path), "--output", str(output)]
    peak, killed = 0, False
    with log_path.open("x") as log:
        process = subprocess.Popen(command, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        status(stage="weighted-margin-diagnostic-evaluation", pid=process.pid, log=str(log_path),
               pin_sha256=sha(pin_path), memory_limit_bytes=MEMORY_LIMIT)
        while process.poll() is None:
            try:
                live = psutil.Process(process.pid)
                peak = max(peak, live.memory_info().rss + sum(c.memory_info().rss for c in live.children(recursive=True)))
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
    completion = output / "complete.json"
    if code != 0 or not completion.is_file():
        status(stage="failed", operation="weighted-margin-diagnostic-evaluation", exit_code=code,
               peak_rss_bytes=peak, memory_limit_terminated=killed, log=str(log_path))
        raise SystemExit(code or 1)
    if json.loads(completion.read_text()) != {"status": "weighted-margin-diagnostic-complete",
                                            "fits": 16, "fitting": False, "acceptance": False}:
        status(stage="failed", operation="weighted-margin-diagnostic-evaluation", reason="completion contract differs")
        raise SystemExit(1)
    status(stage="weighted-margin-diagnostic-complete-awaiting-review", output=str(output), peak_rss_bytes=peak)


if __name__ == "__main__":
    main()
