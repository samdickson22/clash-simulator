#!/usr/bin/env python3
"""Bounded NDJSON echo/action stub; stdin/stdout only, never opens a socket."""
import argparse
import json
import os
import signal
import sys
import time

MAX_LINE = 1024 * 1024
ACTION = {"kind": "probe_only", "card": "Knight", "slot": 0,
          "x": 9, "y": 14, "padding": "x" * 116}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=600)
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 10000 or not 0 < args.max_seconds <= 600:
        parser.error("limits: 1..10000 requests and 0 < seconds <= 600")
    os.nice(10)

    def expired(_signum, _frame):
        # Interpreter shutdown can otherwise flush a full stdout pipe forever.
        # This stub owns no files/resources requiring cleanup beyond its pipes.
        os._exit(0)

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, args.max_seconds)
    try:
        for _ in range(args.max_requests):
            line = sys.stdin.buffer.readline(MAX_LINE + 1)
            received = time.monotonic_ns()
            if not line:
                return 0
            if len(line) > MAX_LINE or not line.endswith(b"\n"):
                return 2
            try:
                request = json.loads(line)
                if (not isinstance(request, dict)
                        or not isinstance(request.get("id"), str)
                        or len(request["id"]) != 8
                        or not isinstance(request.get("padding"), str)):
                    return 2
            except (ValueError, UnicodeError):
                return 2
            response = {"id": request["id"], "action": ACTION,
                        "server_receive_ns": received,
                        "server_send_ns": time.monotonic_ns()}
            sys.stdout.buffer.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
            sys.stdout.buffer.flush()
    except BrokenPipeError:
        return 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
