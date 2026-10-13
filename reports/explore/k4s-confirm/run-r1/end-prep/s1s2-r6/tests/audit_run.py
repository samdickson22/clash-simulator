"""Run a script under a sys.addaudithook recorder: every open/subprocess/listdir/scandir event is appended to LOG as
one JSON line before the call proceeds. Stats have no audit event, so os.stat/os.lstat are wrapped as well (event
"stat", logged BEFORE the call, plus the resulting dev/ino), and every successful os.open/io.open logs the opened
inode (event "opened": what was actually opened, whatever the name; hard-link aliases included).
Usage: python -I [-O] audit_run.py LOG SCRIPT [ARGS...]."""
import builtins
import io
import json
import os
import runpy
import sys

log_path, script = sys.argv[1], sys.argv[2]
LOG = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC, 0o644)
REAL_STAT, REAL_LSTAT, REAL_OPEN, REAL_IO_OPEN, FSTAT = os.stat, os.lstat, os.open, io.open, os.fstat


def text(value):
    if isinstance(value, (bytes, bytearray)):
        return os.fsdecode(bytes(value))
    if isinstance(value, (str, int)) or value is None:
        return value
    return os.fspath(value) if hasattr(value, "__fspath__") else repr(value)


def emit(record):
    os.write(LOG, (json.dumps(record) + "\n").encode())


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
    emit(record)


def stat_wrapper(real, kind):
    def wrapped(path, *args, **kwargs):
        emit(dict(event="stat", kind=kind, path=text(path), dir_fd=kwargs.get("dir_fd") is not None))
        st = real(path, *args, **kwargs)
        emit(dict(event="stat-ok", kind=kind, path=text(path), dev=st.st_dev, ino=st.st_ino,
                  dir_fd=kwargs.get("dir_fd") is not None))                      # r4: relative (dir_fd) stats
        return st
    return wrapped


def os_open(path, flags, mode=0o777, *, dir_fd=None):
    fd = REAL_OPEN(path, flags, mode, dir_fd=dir_fd)
    st = FSTAT(fd)
    emit(dict(event="opened", via="os.open", path=text(path), dir_fd=dir_fd is not None, dev=st.st_dev, ino=st.st_ino))
    return fd


def io_open(file, *args, **kwargs):
    handle = REAL_IO_OPEN(file, *args, **kwargs)
    try:
        st = FSTAT(handle.fileno())
        emit(dict(event="opened", via="io.open", path=text(file), dir_fd=False, dev=st.st_dev, ino=st.st_ino))
    except (OSError, ValueError, AttributeError):
        pass
    return handle


os.stat, os.lstat, os.open = stat_wrapper(REAL_STAT, "stat"), stat_wrapper(REAL_LSTAT, "lstat"), os_open
io.open = builtins.open = io_open
import pathlib                                    # noqa: E402  r5 (3.8 portability): pathlib <= 3.10 keeps os.stat/
if hasattr(pathlib, "_NormalAccessor"):           # lstat/open as accessor CLASS attributes; plain Python wrappers would
    for _name, _fn in (("stat", os.stat), ("lstat", os.lstat), ("open", os.open)):   # bind as methods (an extra
        setattr(pathlib._NormalAccessor, _name, staticmethod(_fn))                      # positional arg), so keep
sys.addaudithook(hook)                            # them unbound: the same recording as on 3.12
sys.argv = [script, *sys.argv[3:]]
runpy.run_path(script, run_name="__main__")
