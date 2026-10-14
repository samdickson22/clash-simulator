"""Test-only interpreter shim for `python3 -I -S <script> args...` (or `-c CODE args...`) on a fake host: os.uname() reports $FAKE_HOST
(safe_input.Policy checks the node name), then the script runs as __main__. Nothing else is changed."""
import os
import runpy
import sys

_real = os.uname()
_host = os.environ["FAKE_HOST"]
os.uname = lambda: os.uname_result((_real.sysname, _host, _real.release, _real.version, _real.machine))
args = sys.argv[1:]
while args and args[0] in ("-I", "-S", "-B"):
    args.pop(0)
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != os.path.dirname(os.path.abspath(__file__))]
if args[:1] == ["-c"]:                         # `python3 -I -S -c CODE ARGS` (the canonical shell bootstrap loader)
    sys.argv = ["-c"] + args[2:]
    exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__", "__builtins__": __builtins__})
else:
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
