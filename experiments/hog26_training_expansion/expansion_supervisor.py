"""Collect complete games under the shared experiment lock and RSS guard."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "collect"), required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if args.attempt < 1:
        raise ValueError("positive log attempt required")
    os.chdir(ROOT)
    lock = (MONITOR / "comparison.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    name = "hog26_training_expansion_preflight_20260913" if args.mode == "preflight" else "hog26_training_expansion_seed1280101_20260913"
    output = ROOT / "datasets/derived" / name
    if (output / "complete.json").exists():
        raise ValueError("completed expansion stage requires review, not relaunch")
    if output.exists() != args.resume:
        raise ValueError("existing partial output requires explicit matching resume")
    log_path = ROOT / f"reports/hog26_training_expansion_{args.mode}_attempt{args.attempt}_20260913.log"
    command = ["/Users/sam/Desktop/code/clasher/.venv/bin/python", "-u",
               "experiments/hog26_training_expansion/collect_expansion.py", "--mode", args.mode,
               "--output-dir", str(output)]
    if args.resume:
        command.append("--resume")
    if args.mode == "collect":
        command.extend(["--plan", str(ROOT / "reports/hog26_training_expansion_frozen_plan_20260913.json"),
                        "--preflight", str(ROOT / "reports/hog26_training_expansion_preflight_pin_20260913.json")])
    environment = dict(os.environ, OMP_NUM_THREADS="1",
                       PYTHONPATH="experiments/hog26_training_expansion:experiments/hog26_scalar_pilot:src:.")
    peak, killed = 0, False
    with log_path.open("x") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage="training-expansion-" + args.mode, pid=process.pid, output=str(output), log=str(log_path),
               expected_games=12 if args.mode == "preflight" else 4608, memory_limit_bytes=LIMIT)
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
        status(stage="training-expansion-failed", operation=args.mode, exit_code=code,
               peak_rss_bytes=peak, memory_limit_terminated=killed, log=str(log_path))
        raise SystemExit(code or 1)
    value = json.loads(complete.read_text())
    if (value.get("status") != "complete-audited" or value.get("mode") != args.mode
            or value.get("game_count") != (12 if args.mode == "preflight" else 4608)
            or value.get("fitting_allowed") is not False):
        raise ValueError("expansion completion contract differs")
    status(stage="training-expansion-" + args.mode + "-complete-awaiting-review", output=str(output), peak_rss_bytes=peak)


if __name__ == "__main__":
    main()
