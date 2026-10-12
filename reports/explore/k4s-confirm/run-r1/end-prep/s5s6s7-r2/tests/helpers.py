"""Offline test helpers (r2). Every check is an explicit raise (ok/refused), never `assert`, so the suites mean the
same under python -O. Fixtures write only under pytest's tmp_path (tempfile's dir) or /dev/shm."""
import difflib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHIMS = HERE / "shims"
CANARY = b"SYNTHETIC-OUTCOME-CANARY keep me; never to be read or overwritten\n"
GIT_ENV = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_AUTHOR_DATE="2026-10-12T00:00:00Z", GIT_COMMITTER_DATE="2026-10-12T00:00:00Z")


def ok(condition, message="check failed"):
    if not condition:
        raise AssertionError(message)


def raises(exc, fn, *a, match=None, **k):
    """fn must raise exc (and contain `match` in str(error)); returns the error."""
    try:
        fn(*a, **k)
    except exc as error:
        ok(match is None or match in str(error), "expected %r in %r" % (match, str(error)))
        return error
    raise AssertionError("expected %s; call succeeded" % exc.__name__)


def refused(si, code, fn, *a, **k):
    error = raises(si.Refusal, fn, *a, **k)
    ok(error.code == code, "expected refusal code %r, got %r (%s)" % (code, error.code, error))
    return error


def canonical(value):                                       # k4s_logic.py:106-107
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    os.chmod(path, mode)
    return path


def canary(path):
    return write(path, CANARY)


def canary_intact(path):
    return Path(path).read_bytes() == CANARY


def fake_uname(host):
    real = os.uname()
    return lambda: os.uname_result((real.sysname, host, real.release, real.version, real.machine))


def load_layers():
    """(safe_input, k4s_end_host_tool) through the production pinned loader of the preflight."""
    sys.path.insert(0, str(ROOT))
    import k4s_end_preflight
    return k4s_end_preflight.load_layers(str(ROOT))


def git(repo, *args, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["/usr/bin/git", "-C", str(repo)] + list(args), capture_output=True, text=True,
                          env=dict(env, **GIT_ENV), check=check)


def git_repo(repo, commits=1, files=None):
    """A plain git clone stand-in with `commits` commits; `files` {rel: bytes} committed in the first one."""
    repo = Path(repo)
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    out = []
    for i in range(commits):
        if i == 0:
            for rel, data in (files or {}).items():
                write(repo / rel, data)
            git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "c%d" % i)
        out.append(git(repo, "rev-parse", "HEAD").stdout.strip())
    return tuple(out)


class Store:
    """Same file semantics as k4s_logic.K4SStore (exclusive files, scope key, seal + sidecar)."""

    def __init__(self, directory, scope):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.scope = scope

    def write(self, name, value):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            stream.write(canonical(dict(scope=self.scope, **value)) + "\n")

    def seal(self, status):
        files = {str(p.relative_to(self.directory)): sha(p) for p in sorted(self.directory.rglob("*")) if p.is_file()}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        with (self.directory / "receipt-manifest.sha256").open("x") as stream:
            stream.write(sha(self.directory / "receipt-manifest.json") + "  receipt-manifest.json\n")


def substituted(source, target, replacements):
    """Copy a script replacing exactly the given lines (each must occur once); return the changed-line count."""
    text = Path(source).read_text()
    for old, new in replacements:
        ok(text.count(old) == 1, "substitution target not unique: " + old)
        text = text.replace(old, new)
    Path(target).write_text(text)
    os.chmod(target, 0o755)
    return len([l for l in difflib.unified_diff(Path(source).read_text().splitlines(), text.splitlines(), lineterm="")
                if l.startswith("-") and not l.startswith("---")])


def run(argv, env, **kw):
    return subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True, **kw)


def shim_env(tmp, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PATH"] = str(SHIMS) + os.pathsep + "/usr/bin:/bin"
    env["FAKE_LOG"] = str(Path(tmp) / "fake.log")
    env.update({k: str(v) for k, v in extra.items()})
    return env


def fake_python(tmp):
    """An interpreter stand-in for `/usr/bin/python3 -I -S script ...` whose os.uname() reports $FAKE_HOST."""
    path = Path(tmp) / "fakepy"
    path.write_text("#!/bin/sh\nexec /usr/bin/python3 -I -S %s \"$@\"\n" % (HERE / "fakepy.py"))
    os.chmod(path, 0o755)
    return path


def nlink(path):
    return os.lstat(path).st_nlink


def is_regular(path):
    return stat.S_ISREG(os.lstat(path).st_mode)


def copy_tools(tools, names=("safe_input.py", "k4s_end_host_tool.py")):
    Path(tools).mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(ROOT / name, Path(tools) / name)
        os.chmod(Path(tools) / name, 0o444)
