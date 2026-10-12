"""Run a script under a sys.addaudithook recorder: every open/subprocess/listdir/scandir event is appended to LOG as
one JSON line before the call proceeds. Usage: python -I [-O] audit_run.py LOG SCRIPT [ARGS...]."""
import json
import os
import runpy
import sys

log_path, script = sys.argv[1], sys.argv[2]
LOG = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC, 0o644)


def text(value):
    if isinstance(value, (bytes, bytearray)):
        return os.fsdecode(bytes(value))
    if isinstance(value, (str, int)) or value is None:
        return value
    return os.fspath(value) if hasattr(value, "__fspath__") else repr(value)


def hook(event, args):
    if event == "open":
        record = dict(event=event, path=text(args[0]), mode=text(args[1]) if len(args) > 1 else None,
                      flags=args[2] if len(args) > 2 and isinstance(args[2], int) else None)
    elif event == "subprocess.Popen":
        record = dict(event=event, executable=text(args[0]), argv=[text(x) for x in (args[1] or [])])
    elif event in ("os.listdir", "os.scandir"):
        record = dict(event=event, path=text(args[0]))
    else:
        return
    os.write(LOG, (json.dumps(record) + "\n").encode())


sys.addaudithook(hook)
sys.argv = [script, *sys.argv[3:]]
runpy.run_path(script, run_name="__main__")
