"""Test-only stand-in for `/usr/bin/python3 -I -B -` on a fake host (run by the generated ssh shim): os.uname()
reports $FAKE_HOST (safe_input.Policy checks the node name), then the program read from stdin runs as __main__."""
import os
import sys

_real = os.uname()
_host = os.environ["FAKE_HOST"]
os.uname = lambda: os.uname_result((_real.sysname, _host, _real.release, _real.version, _real.machine))
program = sys.stdin.buffer.read()
exec(compile(program, "<stdin>", "exec"), {"__name__": "__main__", "__file__": "<stdin>"})
