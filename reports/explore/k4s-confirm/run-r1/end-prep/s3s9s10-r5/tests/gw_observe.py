"""r5 test helper (Linux, stdlib + ctypes; ptrace/strace are unavailable): the paths a command writes under a root,
observed with inotify (every directory watched before the command; IN_CREATE/MODIFY/ATTRIB/CLOSE_WRITE/MOVED/DELETE,
so transient lock and tmp files are seen) plus a before/after lstat snapshot diff (which also catches files inside
directories the command created, where no watch existed yet). Returns sorted paths relative to the root."""
import ctypes
import ctypes.util
import os
import struct

_LIBC = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
_MASK = 0x2 | 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800      # MODIFY..MOVE_SELF, without ACCESS/OPEN
_DONT_FOLLOW, _ONLYDIR = 0x02000000, 0x01000000


def _snapshot(root):
    out = {}
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n)
            st = os.lstat(p)
            out[os.path.relpath(p, root)] = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_nlink, st.st_mode)
    return out


def observe(root, fn):
    fd = _LIBC.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "inotify_init1")
    try:
        wds = {}
        for d, dirs, files in os.walk(root):
            wd = _LIBC.inotify_add_watch(fd, d.encode(), _MASK | _DONT_FOLLOW | _ONLYDIR)
            if wd < 0:
                raise OSError(ctypes.get_errno(), "inotify_add_watch " + d)
            wds[wd] = d
        before = _snapshot(root)
        result = fn()
        seen = set()
        while True:
            try:
                buf = os.read(fd, 1 << 20)
            except BlockingIOError:
                break
            i = 0
            while i < len(buf):
                wd, mask, _, size = struct.unpack_from("iIII", buf, i)
                name = buf[i + 16:i + 16 + size].rstrip(b"\0").decode("utf-8", "surrogateescape")
                i += 16 + size
                if mask & 0x4000:                                       # IN_Q_OVERFLOW: the observation is void
                    raise RuntimeError("inotify queue overflow")
                base = wds.get(wd)
                if base is not None:
                    seen.add(os.path.relpath(os.path.join(base, name) if name else base, root))
        after = _snapshot(root)
        seen |= {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        return result, sorted(p for p in seen if p != ".")
    finally:
        os.close(fd)
