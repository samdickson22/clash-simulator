"""Fault injector for the live link-recovery validation (emulator-5594 only).

Runs the readiness runner as a child, and while it runs performs one of:
  forward  remove the owned forward (adb -s emulator-5594 forward --remove
           tcp:26796) N times at random moments inside [--start, --end] s;
  forward-break  as forward, then also destroy the established adbd<->probe
           TCP connection on the device (ss -K dport = :26789), so the
           runner's persistent session must reconnect through a new forward;
  kill     force-stop the game app once at a random moment in that window.
Every adb call is scoped with -s emulator-5594. Writes a JSON log of events.

Usage: chaos.py --mode forward|kill --log LOG.json [--count 3] [--start S]
                [--end E] [--seed N] -- RUNNER ARGV...
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ADB = "/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb"
SERIAL = "emulator-5594"
PORT = 26796
PACKAGE = "nullsroyale.rel.free"


def adb(*args):
    completed = subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True, text=True,
                               timeout=30, check=False)
    return {"argv": ["adb", "-s", SERIAL, *args], "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-400:], "stderr": completed.stderr.strip()[-400:]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("forward", "forward-break", "kill", "none"), required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--start", type=float, default=25.0)
    parser.add_argument("--end", type=float, default=110.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    count = args.count if args.mode.startswith("forward") else (1 if args.mode == "kill" else 0)
    while True:
        moments = sorted(rng.uniform(args.start, args.end) for _ in range(count))
        if all(b - a >= 8.0 for a, b in zip(moments, moments[1:])):
            break
    log = {"mode": args.mode, "seed": seed, "planned_seconds": [round(m, 2) for m in moments],
           "runner_argv": argv, "events": []}
    started = time.monotonic()
    log["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    child = subprocess.Popen(argv)
    for moment in moments:
        while time.monotonic() - started < moment:
            if child.poll() is not None:
                break
            time.sleep(0.2)
        if child.poll() is not None:
            log["events"].append({"skipped_after_exit": round(moment, 2)})
            continue
        at = round(time.monotonic() - started, 2)
        if args.mode.startswith("forward"):
            before = adb("forward", "--list")
            op = adb("forward", "--remove", f"tcp:{PORT}")
            after = adb("forward", "--list")
            broken = None
            if args.mode == "forward-break":
                broken = adb("shell", "ss -tn state established '( dport = :26789 )'; "
                             "ss -K -tn state established '( dport = :26789 )' >/dev/null; echo destroyed")
            log["events"].append({"socket_destroy": broken,
                "seconds": at, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "owned_forward_before": f"{SERIAL} tcp:{PORT} tcp:26789" in before["stdout"],
                "remove": op,
                "owned_forward_after": f"{SERIAL} tcp:{PORT} tcp:26789" in after["stdout"]})
        else:
            pid = adb("shell", "pidof", PACKAGE)
            op = adb("shell", "am", "force-stop", PACKAGE)
            gone = adb("shell", "pidof", PACKAGE)
            log["events"].append({
                "seconds": at, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pid_before": pid["stdout"], "force_stop": op, "pid_after": gone["stdout"]})
        print(f"[chaos] {args.mode} at {at}s", file=sys.stderr, flush=True)
    code = child.wait()
    log["runner_exit_code"] = code
    log["runner_wall_seconds"] = round(time.monotonic() - started, 2)
    log["final_forward"] = adb("forward", "--list")
    args.log.write_text(json.dumps(log, indent=2) + "\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
