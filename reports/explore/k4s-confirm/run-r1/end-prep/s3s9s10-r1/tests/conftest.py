"""Offline fixtures for S1b / S3 / S9 / S10. No ssh, no host: the ssh-using scripts run against a fake `ssh` on PATH
that serves FAKE_SSH_ROOT/<host>/ as the host's /mpac/sdicks02 tree. The git fixtures are a `--shared` scratch clone
of the real 05 repository in pytest's tmp dir (reads the source through alternates; never writes to it)."""
import functools
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import s1b_copy_admissions as S1B  # noqa: E402
import s3_guard_job as S3  # noqa: E402
import s9_end_runtime as S9  # noqa: E402
import s10_stage_host as S10  # noqa: E402

CLASHER = Path(os.environ.get("CLASHER_REPO", "/mpac/sdicks02/repos/clasher"))
ADMISSIONS_DIR = S3.DEFAULT_ADMISSIONS_DIR


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env).stdout


@functools.lru_cache(maxsize=None)
def head():
    """origin/main, resolved ONCE per session (other threads fetch into the shared checkout and move it)."""
    return git(CLASHER, "rev-parse", "origin/main").decode().strip()


def py(script, *args, env=None):
    """Run a script as a subprocess with -I (and -O when pytest itself runs under -O)."""
    flags = ["-I", "-B"] + (["-O"] * sys.flags.optimize)
    return subprocess.run([sys.executable, *flags, str(ROOT / script), *map(str, args)], capture_output=True,
                          text=True, env=env, cwd=tempfile.gettempdir())      # never the deliverable dir


# ---------------------------------------------------------------- synthetic admissions (pass check_admission)

def bus_admission(host, **identity):
    ident = dict(S1B.BUS_IDENTITY[host], **identity)
    return (json.dumps(dict(utc="2026-10-12T13:30:00Z", host=host, identity=ident, exe_evidence=dict(exe="x"),
                            coordinator_ruling="OP-1 14:45Z"), indent=2) + "\n").encode()


def idle_admission(host="127x03", **identity):
    ident = dict(S1B.IDLE_IDENTITY, **identity)
    service = dict(name=S1B.IDLE_SERVICE_NAME, service=ident, wrapper_trio=[ident, dict(ident, pid=1), dict(ident, pid=2)],
                   wrapper_artifacts={}, commands=["a", "b", "c"], idle_cpu_threshold=.01, new_children_always_flag=True)
    return (json.dumps(dict(utc="2026-10-12T13:31:00Z", host=host, coordinator_ruling="x", services=[service]),
                       indent=2) + "\n").encode()


def admissions(host):
    out = {"system-bus-admission.json": bus_admission(host)}
    if host == "127x03":
        out["idle-services.json"] = idle_admission()
    return out


# ---------------------------------------------------------------- scratch repository

def commit_files(repo, parent, files, message="test"):
    """A child of parent with files {rel: bytes or None (delete)}; plumbing only, no work tree."""
    index = Path(repo) / ".git" / ("index-test-" + sha(message.encode() + parent.encode())[:8])
    env = dict(os.environ, GIT_INDEX_FILE=str(index), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    git(repo, "read-tree", parent, env=env)
    for rel, data in files.items():
        if data is None:
            git(repo, "update-index", "--force-remove", rel, env=env)
            continue
        proc = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input=data,
                              capture_output=True, check=True)
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{proc.stdout.decode().strip()},{rel}", env=env)
    tree = git(repo, "write-tree", env=env).decode().strip()
    index.unlink()
    return git(repo, "commit-tree", tree, "-p", parent, "-m", message).decode().strip()


@pytest.fixture(scope="session")
def scratch(tmp_path_factory):
    """--shared --no-checkout clone of the real 05 repository + a commit holding both hosts' committed admissions."""
    repo = tmp_path_factory.mktemp("scratch") / "repo"
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(CLASHER), str(repo)], check=True)
    base = head()
    files = {f"{ADMISSIONS_DIR}/{h}-{n}": b for h in ("127x03", "127x04") for n, b in admissions(h).items()}
    commit = commit_files(repo, base, files, "admissions")
    return dict(repo=repo, base=base, commit=commit)


@pytest.fixture(scope="session")
def guard03(scratch, tmp_path_factory):
    out = tmp_path_factory.mktemp("guard") / "g03"
    rc = S3.main(["build", "--host", "127x03", "--round", "00", "--attempt", "00", "--repository",
                  str(scratch["repo"]), "--commit", scratch["commit"], "--out", str(out)])
    assert rc == 0
    return out


@pytest.fixture(scope="session")
def runtime_build(tmp_path_factory):
    """One REAL S9 build of origin/main with the real 05 sources (read only)."""
    out = tmp_path_factory.mktemp("runtime") / "rt"
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", head(), "--out", out)
    assert result.returncode == 0, result.stderr
    return out


def make_writable_copy(src, dst):
    shutil.copytree(src, dst, symlinks=True)
    for directory, _, files in os.walk(dst):
        os.chmod(directory, 0o755)
        for f in files:
            os.chmod(os.path.join(directory, f), 0o644)
    return dst


# ---------------------------------------------------------------- fake ssh

SHIM = r'''#!{python}
"""Fake ssh: logs argv; refuses a login without the hygiene options; runs the command with bash -c, with the
host's /mpac/sdicks02 mapped to FAKE_SSH_ROOT/<host>/mpac/sdicks02 (and mapped back in its output)."""
import json, os, subprocess, sys
argv = sys.argv[1:]
opts, i = [], 0
while i < len(argv) and argv[i] != "--":
    if argv[i] == "-o":
        opts.append(argv[i + 1]); i += 2
    else:
        opts.append(argv[i]); i += 1
host, command = argv[i + 1], " ".join(argv[i + 2:])
log = os.environ["FAKE_SSH_LOG"]
n = sum(1 for _ in open(log)) + 1 if os.path.exists(log) else 1
with open(log, "a") as f:
    f.write(json.dumps(dict(argv=sys.argv, host=host, command=command, opts=opts)) + "\n")
for need in ("BatchMode=yes", "ControlMaster=no", "ControlPath=none"):
    if need not in opts:
        sys.stderr.write("shim: missing " + need + "\n"); sys.exit(255)
if os.environ.get("FAKE_SSH_FAIL_HOST") == host or os.environ.get("FAKE_SSH_FAIL_AT") == str(n):
    sys.stdin.buffer.read() if os.environ.get("FAKE_SSH_DRAIN") else None
    sys.stderr.write("shim: connection refused\n"); sys.exit(255)
root = os.path.join(os.environ["FAKE_SSH_ROOT"], host)
rewritten = command.replace("/mpac/sdicks02", root + "/mpac/sdicks02")
env = dict(os.environ, FAKE_HOSTNAME=host, PATH=os.environ["FAKE_BIN"] + ":" + os.environ["PATH"])
done = subprocess.run(["bash", "-c", rewritten], stdin=sys.stdin.buffer, capture_output=True, env=env)
back = (root + "/mpac/sdicks02").encode()
out = bytearray(done.stdout.replace(back, b"/mpac/sdicks02"))
if os.environ.get("FAKE_SSH_FLIP") == host and len(out) > 2:
    out[-2] ^= 1                                           # transport corruption of the body
sys.stdout.buffer.write(bytes(out))
sys.stderr.buffer.write(done.stderr.replace(back, b"/mpac/sdicks02"))
if os.environ.get("FAKE_SSH_EXTRA") == host:
    sys.stdout.buffer.write(b"junk")
if os.environ.get("FAKE_SSH_FLOOD") == host:
    sys.stdout.buffer.write(b"x" * (3 << 20))
sys.exit(done.returncode)
'''

HOSTNAME = "#!/bin/sh\necho \"$FAKE_HOSTNAME\"\n"
# Corrupts one staged file right after extraction (TV) when FAKE_TAR_CORRUPT names a path suffix.
TAR = r'''#!/bin/sh
/bin/tar "$@" || exit $?
if [ -n "$FAKE_TAR_CORRUPT" ]; then
  f=$(find "$5" -path "*$FAKE_TAR_CORRUPT" -type f 2>/dev/null | head -n 1)
  [ -n "$f" ] && printf x >> "$f"
fi
if [ -n "$FAKE_TAR_FLIP" ]; then          # same size, different bytes
  f=$(find "$5" -path "*$FAKE_TAR_FLIP" -type f 2>/dev/null | head -n 1)
  [ -n "$f" ] && printf X | dd of="$f" bs=1 count=1 conv=notrunc 2>/dev/null
fi
exit 0
'''
# A chmod that silently does nothing when FAKE_CHMOD_NOOP is set (F must notice the writable entries).
CHMOD = r'''#!/bin/sh
if [ -n "$FAKE_CHMOD_NOOP" ]; then exit 0; fi
exec /bin/chmod "$@"
'''


@pytest.fixture
def fake_hosts(tmp_path):
    root = tmp_path / "hosts"
    for host in ("127x03", "127x04"):
        for parent in ("/mpac/sdicks02/jobs/clasher", "/mpac/sdicks02/jobs-k4s"):
            (root / host / parent.lstrip("/")).mkdir(parents=True, exist_ok=True)
    bindir = tmp_path / "bin"
    fakebin = tmp_path / "fakebin"
    bindir.mkdir()
    fakebin.mkdir()
    (bindir / "ssh").write_text(SHIM.replace("{python}", sys.executable))
    for name, text in (("hostname", HOSTNAME), ("tar", TAR), ("chmod", CHMOD)):
        (fakebin / name).write_text(text)
    for path in list(bindir.iterdir()) + list(fakebin.iterdir()):
        path.chmod(0o755)
    log = tmp_path / "ssh-log.jsonl"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_SSH_ROOT=str(root), FAKE_SSH_LOG=str(log),
               FAKE_BIN=str(fakebin))
    yield dict(root=root, env=env, log=log)
    for directory, _, _ in os.walk(root):                  # staged trees are read-only: let pytest rotate tmp
        os.chmod(directory, 0o755)


def on_host(fake, host, path):
    return Path(fake["root"]) / host / path.lstrip("/")


def logins(log):
    return [json.loads(line) for line in open(log)] if Path(log).exists() else []


@pytest.fixture
def foreign_dir():
    """An existing, writable directory OUTSIDE the permitted output roots, harmless even if a mutant writes into it
    (never a real path such as /mpac/sdicks02/repos/...)."""
    d = Path(tempfile.mkdtemp(prefix="k4s-s3s9s10-foreign-", dir="/dev/shm"))
    yield d
    for directory, _, _ in os.walk(d):
        os.chmod(directory, 0o755)
    shutil.rmtree(d, ignore_errors=True)
