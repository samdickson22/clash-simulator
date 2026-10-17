#!/usr/bin/env python3
"""Mac-only context: one SSH-04 true and bounded TCP handshakes, no ICMP."""
import argparse
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import time

from latency_client import confined, percentiles, ssh_command
from probe_process import SupervisedProcess


def tcp_target(config):
    fields = dict(line.split(None, 1) for line in config.splitlines() if " " in line)
    # SSH aliases need not be DNS names. Resolve through ssh -G, and require an
    # already numeric Tailscale address so DNS cannot escape socket timeouts.
    host = fields["hostname"]
    ipaddress.ip_address(host)
    if fields.get("proxycommand", "none") != "none" or fields.get("proxyjump", "none") != "none":
        raise ValueError("SSH uses a proxy; direct TCP is not a comparable route")
    return host, int(fields.get("port", 22))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/tmp/bot-remote-probe/network-context.json")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--stop-file", default="/tmp/bot-remote-probe/STOP")
    args = parser.parse_args()
    if sys.platform != "darwin" or not 1 <= args.count <= 30:
        parser.error("Mac only; count must be 1..30")
    try:
        output, stop = confined(args.output), confined(args.stop_file)
    except ValueError as exc:
        parser.error(str(exc))
    if output.exists():
        parser.error("refusing to overwrite output")
    os.nice(max(0, 10 - os.nice(0)))
    interrupted = False

    def halt(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, halt)

    def stopping():
        return interrupted or stop.exists()

    result = {"tcp": {}, "ssh_04_true": None,
              "note": "SSH includes authentication/startup; TCP measures only connect to SSH port, with no authentication or ICMP"}
    # Use the same no-write/no-multiplex options, but remote command is just true.
    if not stopping():
        command = ssh_command("127x04", 1, 1)[:-1] + ["true"]
        started = time.monotonic_ns()
        process = SupervisedProcess(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        try:
            while process.poll() is None and time.monotonic() < deadline and not stopping():
                time.sleep(.025)
            if process.poll() is None:
                process.finish()
            result["ssh_04_true"] = {"elapsed_ms": (time.monotonic_ns() - started) / 1e6,
                                     "returncode": process.returncode}
        finally:
            process.finish()
    for alias in ("127x04", "127x08"):
        if stopping():
            break
        values, errors = [], []
        try:
            config = subprocess.check_output(["ssh", "-G", *ssh_command(alias, 1, 1)[1:-1]],
                                             text=True, stderr=subprocess.DEVNULL, timeout=.25)
            target = tcp_target(config)
            for _ in range(args.count):
                if stopping():
                    break
                started = time.monotonic_ns()
                try:
                    with socket.create_connection(target, timeout=.25):
                        values.append((time.monotonic_ns() - started) / 1e6)
                except OSError as exc:
                    errors.append(type(exc).__name__)
                # At most 2 connects/second. STOP remains responsive while idle.
                due = time.monotonic() + .5
                while time.monotonic() < due and not stopping():
                    time.sleep(min(.025, max(0, due - time.monotonic())))
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            errors.append(str(exc))
        result["tcp"][alias] = {"count": len(values), "connect_ms": percentiles(values),
                                "samples_ms": values, "errors": errors}
    result["utc_finished"] = subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    complete = (result["ssh_04_true"] is not None and result["ssh_04_true"]["returncode"] == 0
                and len(result["tcp"]) == 2
                and all(group["count"] == args.count and not group["errors"] for group in result["tcp"].values()))
    rc = 0 if complete else 1
    print(f"__RC={rc}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
