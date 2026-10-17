#!/usr/bin/env python3
"""Read-only macOS tailscaled CPU sampler (ps %cpu is a smoothed CPU estimate)."""
import argparse
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time

ROOT = Path("/tmp/bot-remote-probe")


def output_path(value):
    path = Path(value).absolute()
    if ROOT.is_symlink() or ROOT.resolve() not in path.resolve().parents:
        raise ValueError("output must resolve beneath /tmp/bot-remote-probe/")
    return path


def cpu_summary(values):
    ordered = sorted(values)
    return {"count": len(values), "mean_percent": statistics.mean(values) if values else None,
            "p50_percent": statistics.median(values) if values else None,
            "max_percent": max(values) if values else None,
            "p95_percent": ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)] if values else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", choices=("usual", "during"), required=True)
    parser.add_argument("--max-seconds", type=float, default=30)
    parser.add_argument("--stop-file", default=str(ROOT / "STOP"))
    parser.add_argument("--usual-file", default=str(ROOT / "tailscaled-usual.json"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("host sampling is Mac-only; local tests mock process reads")
    if not 0 < args.max_seconds <= 600:
        parser.error("0 < max-seconds <= 600 required")
    try:
        output = output_path(args.output)
        stop = output_path(args.stop_file)
        usual_file = output_path(args.usual_file)
    except ValueError as exc:
        parser.error(str(exc))
    os.nice(max(0, 10 - os.nice(0)))
    stopped = False

    def halt(_signum, _frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    started = time.monotonic()
    samples, errors = [], []
    usual = None
    if args.label == "during" and usual_file.exists():
        usual = json.loads(usual_file.read_text()).get("cpu")
    # Exact-name discovery only. Never sends a signal to these PIDs.
    pids = []
    if not stop.exists() and not stopped:
        try:
            found = subprocess.run(["pgrep", "-x", "tailscaled"], capture_output=True, text=True, timeout=.25)
            pids = [int(pid) for pid in found.stdout.split() if pid.isdecimal()]
            if found.returncode or not pids:
                errors.append("exact-name tailscaled lookup found no process")
        except subprocess.TimeoutExpired:
            errors.append("exact-name tailscaled lookup timed out")
    deadline, due = started + args.max_seconds, started
    while pids and time.monotonic() < deadline and not stopped and not stop.exists():
        now = time.monotonic()
        if now < due:
            time.sleep(min(.05, due - now, deadline - now))
            continue
        try:
            reading = subprocess.run(["ps", "-o", "%cpu=", "-p", ",".join(map(str, pids))],
                                     capture_output=True, text=True, timeout=.25,
                                     env={**os.environ, "LC_ALL": "C"})
            values = [float(value) for value in reading.stdout.split()]
            if reading.returncode or len(values) != len(pids):
                errors.append("tailscaled PID disappeared or ps failed; no rediscovery")
                break
            samples.append({"elapsed_s": now - started, "cpu_percent": sum(values)})
        except (ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(type(exc).__name__)
            break
        due = max(due + 1, time.monotonic())
    current = cpu_summary([sample["cpu_percent"] for sample in samples])
    delta = (current["mean_percent"] - usual["mean_percent"]
             if usual and usual.get("mean_percent") is not None and current["mean_percent"] is not None else None)
    result = {"label": args.label, "pids": pids, "cpu": current, "usual_cpu": usual,
              "samples": samples, "errors": errors,
              "elapsed_s": time.monotonic() - started, "mean_delta_from_usual_percentage_points": delta,
              "source": "pgrep -x tailscaled; ps -o %cpu= -p PID at <=1 Hz; smoothed estimate, not instantaneous CPU",
              "max_above_17_percent": current["max_percent"] is not None and current["max_percent"] > 17}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
