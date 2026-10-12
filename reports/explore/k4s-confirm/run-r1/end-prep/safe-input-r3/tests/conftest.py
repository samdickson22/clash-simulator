"""Shared fixtures. The module under test is ../safe_input.py, or SAFE_INPUT_UNDER_TEST (the mutation driver points it
at a mutant in a temp dir). Every test writes only under pytest's tmp_path (tempfile's temp dir) or /dev/shm."""
import importlib.util
import os
import stat
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.environ.get("SAFE_INPUT_UNDER_TEST") or os.path.join(os.path.dirname(HERE), "safe_input.py")
_spec = importlib.util.spec_from_file_location("safe_input", MODULE_PATH)
si = importlib.util.module_from_spec(_spec)
sys.modules["safe_input"] = si
_spec.loader.exec_module(si)

HOST = os.uname().nodename.split(".")[0]
CANARY_BYTES = b"SYNTHETIC-OUTCOME-CANARY-never-to-be-read\n"

# ---------------------------------------------------------------- audit hook (installed once; toggled per use)
AUDIT = {"on": False, "events": []}


def _audit(event, args):
    if AUDIT["on"] and event in ("open", "os.listdir", "os.readlink", "os.symlink", "os.mkdir", "os.link"):
        AUDIT["events"].append((event, args[0] if args else None))


sys.addaudithook(_audit)


def ok(condition, message="check failed"):
    """Explicit check (not `assert`), so it holds under python -O as well."""
    if not condition:
        raise AssertionError(message)


def refusal(code, fn, *args, **kwargs):
    """fn must raise si.Refusal with exactly this code."""
    try:
        fn(*args, **kwargs)
    except si.Refusal as error:
        ok(error.code == code, "expected refusal code %r, got %r (%s)" % (code, error.code, error))
        return error
    raise AssertionError("expected Refusal(%r); call succeeded" % code)


class Recorder(object):
    """Wraps os.open/os.stat/os.lstat/os.read/os.listdir/os.readlink while active. For os.open it resolves the target
    inode with a no-follow fstatat BEFORE delegating, so even a failed/denied open attempt is recorded by inode."""

    def __init__(self):
        self.calls, self.open_attempts, self.read_inodes = [], [], []
        self._real = {}

    def __enter__(self):
        real = self._real
        for name in ("open", "stat", "lstat", "read", "listdir", "readlink", "fstat"):
            real[name] = getattr(os, name)

        def w_open(path, flags, mode=0o777, *, dir_fd=None):
            try:
                st = real["stat"](path, dir_fd=dir_fd, follow_symlinks=False)
                ident = (st.st_dev, st.st_ino)
            except OSError:
                ident = None
            self.calls.append(("open", path, dir_fd))
            self.open_attempts.append(ident)
            return real["open"](path, flags, mode, dir_fd=dir_fd)

        def w_stat(path, *a, **k):
            self.calls.append(("stat", path, k.get("dir_fd")))
            return real["stat"](path, *a, **k)

        def w_lstat(path, *a, **k):
            self.calls.append(("lstat", path, k.get("dir_fd")))
            return real["lstat"](path, *a, **k)

        def w_read(fd, n):
            st = real["fstat"](fd)
            self.read_inodes.append((st.st_dev, st.st_ino))
            return real["read"](fd, n)

        def w_listdir(path="."):
            self.calls.append(("listdir", path, None))
            return real["listdir"](path)

        def w_readlink(path, *a, **k):
            self.calls.append(("readlink", path, k.get("dir_fd")))
            return real["readlink"](path, *a, **k)

        os.open, os.stat, os.lstat, os.read, os.listdir, os.readlink = (w_open, w_stat, w_lstat, w_read, w_listdir,
                                                                         w_readlink)
        AUDIT["events"] = []
        AUDIT["on"] = True
        return self

    def __exit__(self, *exc):
        AUDIT["on"] = False
        for name, fn in self._real.items():
            setattr(os, name, fn)
        return False

    def touched(self, ident):
        return ident in self.open_attempts or ident in self.read_inodes

    def audit_names(self):
        return [os.path.basename(str(path)) for event, path in AUDIT["events"] if isinstance(path, (str, bytes))]


@pytest.fixture
def rec():
    return Recorder()


@pytest.fixture
def base(tmp_path):
    """A canonical temp directory (tempfile's temp dir; realpath must equal the path)."""
    path = str(tmp_path.resolve())
    ok(os.path.realpath(path) == path)
    return path


def make_file(path, data=b"{}\n", mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as stream:
        stream.write(data)
    os.chmod(path, mode)
    return path


def ident(path):
    st = os.lstat(path)
    return (st.st_dev, st.st_ino)


def make_canary(base):
    """A synthetic outcome-named canary (mode 000) at <base>/canary-src/games/g1/complete.json."""
    path = os.path.join(base, "canary-src", "games", "g1", "complete.json")
    make_file(path, CANARY_BYTES, 0o644)
    os.chmod(path, 0)
    return path


def canary_unchanged(path):
    os.chmod(path, 0o600)
    try:
        with open(path, "rb") as stream:
            return stream.read() == CANARY_BYTES
    finally:
        os.chmod(path, 0)


def policy(roles, host=None, remote=False):
    return si.Policy(host or HOST, roles, remote=remote)


def role(name, root, access="read", max_size=1 << 20, exact=(), patterns=(), exemptions=(), grants=()):
    return si.Role(name=name, root=root, access=access, max_size=max_size, exact=exact, patterns=patterns,
                   exemptions=exemptions, grants=grants)
