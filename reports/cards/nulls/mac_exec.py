#!/usr/bin/env python3
"""Slot transport wrapper: never trust ssh macmini-fleet's process exit code.

Example: mac_exec.py -- python3 -B /.../cards/nulls/capture.py <slot arguments>
This does not grant a slot or alter the host. No SSH is performed on import.
"""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys


def parse_rc(stdout):
    matches = re.findall(r"(?m)^__RC=(-?\d+)\s*$", stdout)
    if len(matches) != 1:
        raise ValueError("missing or ambiguous explicit __RC token; SSH exit zero is not success")
    return int(matches[0])


def execute(argv):
    remote = shlex.join(argv) + '\nrc=$?\nprintf "\\n__RC=%s\\n" "$rc"\n'
    result = subprocess.run(["ssh", "macmini-fleet", "bash -c " + shlex.quote(remote)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return parse_rc(result.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not arguments:
        parser.error("a remote argument vector is required")
    raise SystemExit(execute(arguments))
