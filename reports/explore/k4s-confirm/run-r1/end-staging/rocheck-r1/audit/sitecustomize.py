"""rocheck-r1 write audit (K4S END RO-1 step 1). Installed in EVERY Python process via PYTHONPATH.

Logs, per pid, to $ROCHECK_LOG_DIR/audit-<pid>.jsonl (outside every traced tree):
  * write-class audit events (open for write/append/create/excl/trunc, os.mkdir/rename/replace/remove/rmdir/
    symlink/link/chmod/chown/truncate/utime, shutil.*, tempfile.mkstemp/mkdtemp, sqlite3.connect);
  * info-class events (subprocess/exec/spawn/fork, ctypes.dlopen, mmap, socket.bind, os.chdir);
  * every raised OSError with errno EACCES/EPERM/EROFS/EDQUOT/ENOSPC/EEXIST (sys.monitoring RAISE), even if the
    caller catches it;
  * the HOST-IDENTITY shims below each time they answer.
Read-only opens are only counted (summary line at exit).

Host-identity shims (05 is not 03; these change no write path):
  platform.node() -> "127x03"; os.getpriority(PRIO_PROCESS, *) -> 10 when the real value is the harness nice 19;
  os.sched_setaffinity -> logged no-op (the process stays inside the harness taskset).
"""
import errno as _errno
import json as _json
import os as _os
import sys as _sys
import threading as _threading
import time as _time

_LOG_DIR = _os.environ.get("ROCHECK_LOG_DIR")
_HERE = __file__
_tls = _threading.local()
_fds = {}
_counts = {"read_open": 0}
_WFLAGS = _os.O_WRONLY | _os.O_RDWR | _os.O_CREAT | _os.O_TRUNC | _os.O_APPEND | _os.O_EXCL
_WRITE_EVENTS = {
    "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink", "os.link", "os.chmod", "os.chown",
    "os.truncate", "os.utime", "os.chflags", "os.lchflags", "os.lchmod", "os.lchown", "os.mkfifo", "os.mknod",
    "shutil.copyfile", "shutil.copymode", "shutil.copystat", "shutil.copytree", "shutil.move", "shutil.rmtree",
    "shutil.chown", "shutil.make_archive", "shutil.unpack_archive", "tempfile.mkstemp", "tempfile.mkdtemp",
    "sqlite3.connect", "os.setxattr", "os.removexattr",
}
_INFO_EVENTS = {
    "subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn", "os.system", "os.fork", "os.forkpty",
    "ctypes.dlopen", "mmap.__new__", "socket.bind", "os.chdir", "pty.spawn",
}
_WATCH_ERRNO = {_errno.EACCES, _errno.EPERM, _errno.EROFS, _errno.EDQUOT, _errno.ENOSPC, _errno.EEXIST}


def _emit(record):
    if not _LOG_DIR:
        return
    previous = getattr(_tls, "busy", False)
    _tls.busy = True
    try:
        _emit_inner(record)
    finally:
        _tls.busy = previous


def _emit_inner(record):
    pid = _os.getpid()
    fd = _fds.get(pid)
    if fd is None:
        fd = _os.open(_LOG_DIR + "/audit-%d.jsonl" % pid, _os.O_WRONLY | _os.O_APPEND | _os.O_CREAT, 0o644)
        _fds.clear()
        _fds[pid] = fd
        _os.write(fd, (_json.dumps(dict(kind="start", pid=pid, ppid=_os.getppid(), t=_time.time(),
                                        argv=list(getattr(_sys, "argv", []) or []), cwd=_os.getcwd(),
                                        executable=_sys.executable)) + "\n").encode())
    record.setdefault("pid", pid)
    record.setdefault("t", _time.time())
    _os.write(fd, (_json.dumps(record, default=repr) + "\n").encode())


def _stack(skip=2, depth=8):
    out = []
    try:
        f = _sys._getframe(skip)
    except ValueError:
        return out
    while f is not None and len(out) < depth:
        if f.f_code.co_filename != _HERE:
            out.append("%s:%d:%s" % (f.f_code.co_filename, f.f_lineno, f.f_code.co_name))
        f = f.f_back
    return out


def _abs(path, dir_fd=None):
    try:
        if isinstance(path, int):
            return "fd:%d->%s" % (path, _os.readlink("/proc/self/fd/%d" % path))
        if isinstance(path, bytes):
            path = _os.fsdecode(path)
        path = _os.fspath(path)
        if not _os.path.isabs(path):
            base = _os.readlink("/proc/self/fd/%d" % dir_fd) if isinstance(dir_fd, int) and dir_fd >= 0 \
                else _os.getcwd()
            path = _os.path.join(base, path)
        return _os.path.normpath(path)
    except Exception as error:  # never break the traced program
        return "unresolved:%r (%r)" % (path, error)


def _hook(event, args):
    if getattr(_tls, "busy", False):
        return
    if event != "open" and event not in _WRITE_EVENTS and event not in _INFO_EVENTS:
        return
    _tls.busy = True
    try:
        if event == "open":
            path, mode, flags = (tuple(args) + (None, None, None))[:3]
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                      (isinstance(flags, int) and bool(flags & _WFLAGS))
            if not writing:
                _counts["read_open"] += 1
                return
            _emit(dict(kind="write", event=event, path=_abs(path), mode=mode, flags=flags, stack=_stack()))
        elif event in _WRITE_EVENTS:
            a = list(args)
            paths = []
            if event in ("os.rename", "os.link", "os.symlink"):
                paths = [_abs(a[0], a[2] if len(a) > 2 else None), _abs(a[1], a[3] if len(a) > 3 else None)]
            elif event in ("tempfile.mkstemp", "tempfile.mkdtemp", "sqlite3.connect", "shutil.rmtree"):
                paths = [_abs(a[0])] if a and a[0] is not None else []
            elif event.startswith("shutil.copy") or event == "shutil.move":
                paths = [_abs(a[0]), _abs(a[1])]
            elif a:
                dir_fd = a[-1] if event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.chown",
                                             "os.utime") and isinstance(a[-1], int) else None
                paths = [_abs(a[0], dir_fd)]
            _emit(dict(kind="write", event=event, paths=paths, args=[repr(x)[:300] for x in a], stack=_stack()))
        else:
            _emit(dict(kind="info", event=event, args=[repr(x)[:600] for x in args], stack=_stack(depth=5)))
    finally:
        _tls.busy = False


_recent = []          # strong refs (bounded): identity dedupe across frames; id() alone is reused after free


def _on_raise(code, offset, exc):
    if isinstance(exc, OSError) and exc.errno in _WATCH_ERRNO and not any(e is exc for e in _recent):
        if getattr(_tls, "busy", False):
            return
        _tls.busy = True
        try:
            _recent.append(exc)
            del _recent[:-16]
            _emit(dict(kind="raise", errno=_errno.errorcode.get(exc.errno, exc.errno), error=repr(exc)[:500],
                       filename=str(getattr(exc, "filename", None)), stack=_stack(depth=8)))
        finally:
            _tls.busy = False


def _install_shims():
    import platform

    def node():
        _hook_info("shim.platform.node", ["127x03", "real=" + _os.uname().nodename])
        return "127x03"
    platform.node = node
    real_getpriority = _os.getpriority

    def getpriority(which, who):
        value = real_getpriority(which, who)
        if which == _os.PRIO_PROCESS and value == 19:
            _hook_info("shim.os.getpriority", [who, "real=19", "answered=10"])
            return 10
        return value
    _os.getpriority = getpriority

    def sched_setaffinity(pid, cpus):
        _hook_info("shim.os.sched_setaffinity", [pid, sorted(cpus), "no-op; kept " + repr(
            sorted(_os.sched_getaffinity(0)))])
    _os.sched_setaffinity = sched_setaffinity


def _hook_info(event, args):
    if getattr(_tls, "busy", False):
        return
    _tls.busy = True
    try:
        _emit(dict(kind="shim", event=event, args=[repr(x)[:300] for x in args], stack=_stack(depth=4)))
    finally:
        _tls.busy = False


def _at_exit():
    _tls.busy = True
    try:
        _emit(dict(kind="exit", read_opens=_counts["read_open"]))
    except Exception:
        pass


if _LOG_DIR:
    _sys.addaudithook(_hook)
    try:
        _M = _sys.monitoring
        _M.use_tool_id(4, "rocheck")
        _M.register_callback(4, _M.events.RAISE, _on_raise)
        _M.set_events(4, _M.events.RAISE)
    except Exception as _error:
        _emit(dict(kind="info", event="monitoring-unavailable", args=[repr(_error)]))
    _install_shims()
    import atexit as _atexit
    _atexit.register(_at_exit)
    _emit(dict(kind="info", event="sitecustomize-installed", args=[_HERE]))
