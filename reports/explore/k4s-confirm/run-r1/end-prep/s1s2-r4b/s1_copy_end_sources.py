#!/usr/bin/env python3
"""S1 (PREREG-K4S END, B2 / RC-4a): exact-path copier for the reporting mhz.jsonl / census.jsonl sources. r2.

CANDIDATE: requires Sol review and a coordinator GO before any live run. Runs FROM 127x05 and reads 127x03 and
127x04 read-only over ssh. Never run inside an END timing window (first quiet read .. attempt exit + C-d), on
any host.

For each of the 10 counted (host, phase) pairs the phase directory is a FIXED literal:
    127x03: /mpac/sdicks02/jobs/clasher/<namespace>/<phase>/
    127x04: /mpac/sdicks02/jobs-k4s/<namespace>/<phase>/
with <namespace> from the committed run-r1/rounds/history.json (cross-checked against the constant table). On 04
nothing under /mpac/sdicks02/jobs/ (the perception storage) is ever named.

Within each phase directory exactly four names are ever named, by full literal path (no glob, no recursion, no
listing, no other name): launch.json, supervisor-exit.json, mhz.jsonl, census.jsonl.

Remote side (r2): the only remote program is the host's own /usr/bin/python3 -I -S running REMOTE_PROGRAM below
(stdlib only, O_RDONLY only, never writes). Each named path is opened component by component from "/" with
O_NOFOLLOW (directories O_DIRECTORY|O_NOFOLLOW, the leaf O_NOFOLLOW|O_NONBLOCK), so a symlinked leaf OR ANCESTOR
fails the open (ELOOP/ENOTDIR) and is never followed. On the opened descriptor, BEFORE ANY BYTE IS READ, it
requires a regular file, st_nlink == 1 (no hard-link alias) and the size gate: launch/exit == the committed
phase-meta size exactly, mhz/census 1 .. 95 MiB. Every gate of every file passes before any file is hashed or
streamed. Hashing/streaming reads the gated descriptor itself (no re-open), exactly st_size bytes, and refuses if
the file then has more bytes (growth).

Order (fail closed; any error refuses and stops; nothing is copied unless every check on BOTH hosts passed):
  1. login P (one per host): REMOTE inspect of the 4 files of all 5 phases (gates, then sha256).
     Local: launch/exit SHA == committed phase-meta SHA (== constant table; exit == completion-v2 binding).
  2. login C (one per host): REMOTE stream of the 10 mhz/census files; it first re-opens and re-gates all 10
     (size, device, inode == login P) and refuses before writing a byte if any changed. 05 reads exactly the sum of
     the P sizes into per-file O_CREAT|O_EXCL|O_NOFOLLOW files, then one more byte: any excess byte refuses.
     Every piece's SHA == login P, then re-read from disk.
  3. login V (one per host): REMOTE inspect again; size, SHA, device, inode unchanged; mhz/census SHA == local.
Logins: 3 per host, 6 in total (P03, P04, C03, V03, C04, V04), each with ControlMaster=no, ControlPath=none,
BatchMode=yes, StrictHostKeyChecking=yes; every remote command runs under `nice -n 19`.

Local side (05): --dest must be a canonical absolute path (realpath == the path; every component opened with
O_NOFOLLOW) strictly below DEST_ROOT, and must not exist. Its parent's descriptor is retained, dest is created
with mkdirat and every directory/file below it is created relative to retained descriptors, exclusive and
no-follow. A successful run writes <dest>/<host>/<phase>/{mhz.jsonl,census.jsonl} and <dest>/s1-copy-manifest.json.

Refusals: EVERY refusal or failure (argument errors included) writes a receipt
REFUSAL_DIR/S1-REFUSAL-<utc>-<pid>-<random>.json (exclusive, no-follow; REFUSAL_DIR is fixed, canonical, created
if missing) and, if this run created dest, also <dest>/S1-REFUSAL.json; exit 2 (refusal) or 1 (unexpected error).
No success manifest is ever written on failure; partial copies are preserved.

Test mode: only when the environment holds K4S_S1_TEST_MODE=SYNTHETIC-NOT-FOR-PRODUCTION. It allows
K4S_S1_TEST_DEST_ROOT / K4S_S1_TEST_REFUSAL_DIR and an ssh other than /usr/bin/ssh, and every manifest/receipt
then carries the TEST-ONLY schema and test_mode=true (S2 refuses such a manifest in production).
--dry-run prints the planned ssh argv and the expected SHAs; it makes no ssh call and writes nothing on success.
"""
import argparse
import errno
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time

SCHEMA = "clasher.k4s.end-sources-copy.v2"
TEST_SCHEMA = "clasher.k4s.end-sources-copy.TEST-ONLY.v2"
REFUSAL_SCHEMA = "clasher.k4s.end-sources-copy-refusal.v2"
TEST_REFUSAL_SCHEMA = "clasher.k4s.end-sources-copy-refusal.TEST-ONLY.v2"
TEST_ENV, TEST_MARKER = "K4S_S1_TEST_MODE", "SYNTHETIC-NOT-FOR-PRODUCTION"
DEST_ROOT = "/mpac/sdicks02/k4s-runner/run-r1/end-prep"
REFUSAL_DIR = DEST_ROOT + "/s1-refusals"
SSH_BINARY = "/usr/bin/ssh"
REMOTE_PYTHON = "/usr/bin/python3"
STUDY = "reports/explore/k4s-confirm"
HISTORY = STUDY + "/run-r1/rounds/history.json"
COMPLETION = STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"
COMPLETION_SHA256 = "3794d953efb2c8af47a09ccb086cc0441f1c0dd9ea7a4f46e331315972c6e891"
MAX_BYTES = 95 * 1024 * 1024
HOSTS = ("127x03", "127x04")
JOB_ROOTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
# Never named on that host (04 holds the perception storage under /mpac/sdicks02/jobs/).
FORBIDDEN_PREFIXES = {"127x03": (), "127x04": ("/mpac/sdicks02/jobs/",)}
PHASES = (("reporting", "k4s-confirm-reporting-r1"),
          ("replacement-r1", "k4s-confirm-replacement-r1"),
          ("replacement-r2", "k4s-confirm-replacement-r2"),
          ("replacement-r3", "k4s-confirm-replacement-r3"),
          ("replacement-r4", "k4s-confirm-replacement-r4"))
META = ("launch.json", "supervisor-exit.json")
SOURCES = ("mhz.jsonl", "census.jsonl")
NAMES = META + SOURCES
# Committed phase-meta SHA-256 (run-r1/phase-meta/<host>-<phase>/{launch.json, supervisor-exit.json}).
EXPECTED = {
    ("127x03", "reporting"): ("116f1ed5f998649ba950fbde08846b47b052294acbbb6432b4a04b2a324e0159",
                              "88debddf7bf33c1b0bc2f14002339c87072be956398d90bfb727c2d0c36a1033"),
    ("127x03", "replacement-r1"): ("b864703e102d9dea314e1b332ee1415518f90153a0a633a9c2b1b0ac0ca1a70b",
                                   "bffde5d4008b2a47fc867e690f18d6ae087fd09e58464816f9a2fa60dddb5efa"),
    ("127x03", "replacement-r2"): ("1d917968d9875f89c2024ba173fb1a16fcdaf8b7a5f6a5504fe3bc7b6b9df299",
                                   "834fc2475b5a071d1564076b77403d83b983dbdf2026f4ccccf7df84012c3e3f"),
    ("127x03", "replacement-r3"): ("6c49a6679c1c654879a071c44a86cda952fb40bc1722af43e3b2c22914b13efb",
                                   "cccb86839ef970ae6e9bda6a8bb3b10451aa73baad8ac0978750f7c654688616"),
    ("127x03", "replacement-r4"): ("e8f72fb483e73b5bcbb78b4aa129e5b31c61b4e2f0c45fec67d6b9637f65f2e6",
                                   "c9066d63cd1aa73de74d2214498dc7543d2d863282d3593887aec2f65642027c"),
    ("127x04", "reporting"): ("7cd6b140551d8f1d66858d98b3cf2d74b14339e7d334e6b4fc3650a3fa383c48",
                              "c0a935f6cd1ecf022bf197dc3e88604769491bb461973bcd3c106e393aa71084"),
    ("127x04", "replacement-r1"): ("420f7ec1076885ddb0c0211a39bcfa0d0ced72b9c9c3856c382eef1f4f727f0e",
                                   "c11ae500e34504872095ba1d2b50d836546923c14641684d6ab97f635e4114b2"),
    ("127x04", "replacement-r2"): ("ea88e4d5c11590390875bfc8c044f5027950349e70bdd3f5b3eef82f3683cf32",
                                   "37aafa6a128757e80082d0fbad6a1e518de88a277e342538cb2f33dbbdfc8e8b"),
    ("127x04", "replacement-r3"): ("9cd6bc37da5638dbc95a065cfd47ad467980d9b348bef2d7a711f8f9a7b4264e",
                                   "91475244cc702e33dbf0a4fd20635dcb5b2fa435b21361094263723fc4cd414c"),
    ("127x04", "replacement-r4"): ("38730d445b2a8095cbad8b393f709fbf5e0a79eb0267d6eb69c9875c2ee6c69a",
                                   "21269aa00b3340f8b75a02de5526c5f20d525d3af27a2b1c0ac6d56f8fc47cb9"),
}
SSH_OPTIONS = ("-T", "-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=4", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no")
SAFE_PATH = re.compile(r"/mpac/sdicks02/[A-Za-z0-9._/-]+")
SHA = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20
INSPECT_OUTPUT_LIMIT = 1 << 16                # 40 short lines; anything larger is refused unread
STDERR_TAIL = 4096
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
NEW_FILE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC

# Runs on 127x03/127x04 under their /usr/bin/python3 (Ubuntu 20.04: 3.8). Read-only, stdlib only.
#   inspect <kind>:<n>:<path> ...   kind exact (size == n) or max (1 <= size <= n); prints OK|size|nlink|dev|ino|sha|path
#   stream  <size>:<dev>:<ino>:<path> ...   raw bytes of each file, exactly size bytes each, to stdout
# Pass 1 opens and gates EVERY file before pass 2 reads any byte. Exit 3 = refusal (REFUSE|reason|path).
REMOTE_PROGRAM = r'''
import errno, hashlib, os, stat, sys
D = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
F = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOCTTY
def refuse(why, path):
    os.write(2, ("REFUSE|" + why + "|" + path + "\n").encode())
    if mode == "inspect":
        sys.stdout.write("REFUSE|" + why + "|" + path + "\n")
        sys.stdout.flush()
    os._exit(3)
def opened(path):
    parts = path.split("/")
    if len(parts) < 3 or parts[0] or any(p in ("", ".", "..") for p in parts[1:]):
        refuse("not a normalised absolute path", path)
    fd = os.open("/", D)
    for i, part in enumerate(parts[1:]):
        leaf = i == len(parts) - 2
        try:
            nxt = os.open(part, F if leaf else D, dir_fd=fd)
        except OSError as e:
            refuse("open of component %r failed: %s (symlink/alias, missing or not a directory)"
                   % (part, errno.errorcode.get(e.errno, e.errno)), path)
        os.close(fd)
        fd = nxt
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        refuse("not a regular file", path)
    if st.st_nlink != 1:
        refuse("hard-link alias: st_nlink=%d" % st.st_nlink, path)
    return fd, st
def exactly(fd, size, path, sink):
    left = size
    while left:
        chunk = os.read(fd, min(1 << 20, left))
        if not chunk:
            refuse("file shrank while read", path)
        sink(chunk)
        left -= len(chunk)
    if os.read(fd, 1) or os.fstat(fd).st_size != size:
        refuse("file grew while read", path)
mode, items = sys.argv[1], sys.argv[2:]
if mode not in ("inspect", "stream") or not items:
    refuse("bad mode", mode)
gated = []
for item in items:
    if mode == "inspect":
        kind, n, path = item.split(":", 2)
        if kind not in ("exact", "max") or not n.isdigit():
            refuse("bad size rule", path)
        fd, st = opened(path)
        if kind == "exact" and st.st_size != int(n):
            refuse("size %d != committed size %s" % (st.st_size, n), path)
        if kind == "max" and not 0 < st.st_size <= int(n):
            refuse("size %d outside 1..%s bytes" % (st.st_size, n), path)
    else:
        size, dev, ino, path = item.split(":", 3)
        if not 0 < int(size) <= 99614720:
            refuse("stream size outside 1..99614720 bytes", path)
        fd, st = opened(path)
        if (st.st_size, st.st_dev, st.st_ino) != (int(size), int(dev), int(ino)):
            refuse("size/device/inode changed since login P", path)
    gated.append((fd, st, path))
for fd, st, path in gated:
    if mode == "inspect":
        h = hashlib.sha256()
        exactly(fd, st.st_size, path, h.update)
        sys.stdout.write("OK|%d|%d|%d|%d|%s|%s\n" % (st.st_size, st.st_nlink, st.st_dev, st.st_ino, h.hexdigest(), path))
    else:
        def sink(chunk):
            view = memoryview(chunk)
            while view:
                view = view[os.write(1, view):]
        exactly(fd, st.st_size, path, sink)
sys.stdout.flush()
'''


class Refusal(RuntimeError):
    """Fail-closed refusal (never an assert: the checks hold under python -O)."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def test_mode():
    value = os.environ.get(TEST_ENV)
    require(value in (None, TEST_MARKER), f"{TEST_ENV} is set but is not the synthetic test marker; refusing")
    return value == TEST_MARKER


def configured(name, production):
    """Production constant; in test mode only, K4S_S1_TEST_<name> overrides it."""
    if test_mode():
        return os.environ.get("K4S_S1_TEST_" + name, production)
    return production


# ---------------------------------------------------------------- local no-follow filesystem (05)

def canonical_abs(path, label):
    text = str(path)
    require(text.startswith("/") and text != "/" and os.path.normpath(text) == text and "//" not in text,
            f"{label} must be a normalised absolute path: {text}")
    require(os.path.realpath(text) == text, f"{label} is not canonical (an ancestor is a symlink/alias): {text}")
    return text


def open_dir(path, label, create_leaf=False):
    """Descriptor of an existing canonical directory, every component opened O_NOFOLLOW from '/'."""
    parts = canonical_abs(path, label).split("/")[1:]
    fd = os.open("/", DIR_FLAGS)
    try:
        for i, part in enumerate(parts):
            if create_leaf and i == len(parts) - 1:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                raise Refusal(f"{label}: component {part!r} of {path} is a symlink/alias, missing or not a "
                              f"directory ({errno.errorcode.get(error.errno, error.errno)})") from None
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def mkdir_at(parent_fd, name, label):
    require(re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None and name not in (".", ".."), "unsafe name " + name)
    try:
        os.mkdir(name, 0o755, dir_fd=parent_fd)
    except FileExistsError:
        raise Refusal(f"{label} already exists: {name}") from None
    return os.open(name, DIR_FLAGS, dir_fd=parent_fd)


def create_exclusive(dir_fd, name):
    """O_CREAT|O_EXCL|O_NOFOLLOW: never overwrites, never follows a planted symlink or hard link."""
    try:
        return os.open(name, NEW_FILE_FLAGS, 0o644, dir_fd=dir_fd)
    except FileExistsError:
        raise Refusal("refusing to overwrite an existing file/symlink: " + name) from None


def write_all(fd, data):
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def write_exclusive(dir_fd, name, data):
    fd = create_exclusive(dir_fd, name)
    try:
        write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def sha_at(dir_fd, name):
    fd = os.open(name, READ_FLAGS, dir_fd=dir_fd)
    try:
        h, size = hashlib.sha256(), 0
        while True:
            chunk = os.read(fd, CHUNK)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_size == size, "local file changed while re-read: " + name)
        return h.hexdigest(), size
    finally:
        os.close(fd)


class Destination:
    """--dest: canonical, strictly below DEST_ROOT, new; created and filled only through retained descriptors."""

    def __init__(self, dest):
        root = canonical_abs(configured("DEST_ROOT", DEST_ROOT), "destination root")
        require(not os.path.lexists(str(dest)), "--dest must not exist: " + str(dest))
        self.path = canonical_abs(dest, "--dest")
        require(self.path.startswith(root + "/"), f"--dest must lie strictly below {root}: {self.path}")
        parent, self.name = self.path.rsplit("/", 1)
        self.parent_fd = open_dir(parent, "--dest parent")
        self.fd, self.dirs, self.files = None, {}, []

    def create(self):
        self.fd = mkdir_at(self.parent_fd, self.name, "--dest")
        st = os.fstat(self.fd)
        self.identity = dict(st_dev=st.st_dev, st_ino=st.st_ino)

    def phase_dir(self, host, phase):
        if host not in self.dirs:
            self.dirs[host] = (mkdir_at(self.fd, host, "destination host directory"), {})
        host_fd, phases = self.dirs[host]
        if phase not in phases:
            phases[phase] = mkdir_at(host_fd, phase, "destination phase directory")
        return phases[phase]

    def listing(self):
        found = []
        for top, dirs, files, top_fd in os.fwalk(".", dir_fd=self.fd, follow_symlinks=False):
            for name in dirs + files:
                st = os.stat(name, dir_fd=top_fd, follow_symlinks=False)
                require(stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1),
                        "destination holds a symlink/alias/special file: " + os.path.join(top, name))
                if not stat.S_ISDIR(st.st_mode):
                    found.append(os.path.normpath(os.path.join(top, name)))
        return sorted(found)


# ---------------------------------------------------------------- committed expectations (local git, read only)

def git_blob(repository, commit, rel):
    result = subprocess.run(["git", "-C", str(repository), "show", f"{commit}:{rel}"], capture_output=True)
    require(result.returncode == 0, f"not committed at {commit}: {rel}")
    return result.stdout


def phase_dir(host, namespace, phase):
    path = f"{JOB_ROOTS[host]}/{namespace}/{phase}"
    require(SAFE_PATH.fullmatch(path) is not None and ".." not in path.split("/"), "unsafe phase path: " + path)
    require(not any(path.startswith(p) for p in FORBIDDEN_PREFIXES[host]), f"forbidden path on {host}: {path}")
    return path


def expectations(repository, commit):
    """The plan of record from committed bytes: namespaces, phase-meta SHAs/sizes (== constants == completion)."""
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
            "--commit must be a full 40-hex commit")
    resolved = subprocess.run(["git", "-C", str(repository), "rev-parse", "--verify", commit + "^{commit}"],
                              capture_output=True, text=True)
    require(resolved.returncode == 0 and resolved.stdout.strip() == commit, "commit not in repository: " + commit)
    history = json.loads(git_blob(repository, commit, HISTORY))
    namespaces = {row["phase"]: row["namespace"] for row in history}
    require(len(namespaces) == len(history) == len(PHASES) and namespaces == dict(PHASES),
            "committed rounds/history.json differs from the copier's phase -> namespace table")
    raw = git_blob(repository, commit, COMPLETION)
    require(sha_bytes(raw) == COMPLETION_SHA256, "completion-v2 SHA differs from the completion of record")
    completion = json.loads(raw)
    require(completion.get("counted_host_phases") == {h: [p for p, _ in PHASES] for h in HOSTS},
            "completion counted_host_phases differs from the copier's 10 host/phase pairs")
    plan = []
    for host in HOSTS:
        for phase, namespace in PHASES:
            meta = f"{STUDY}/run-r1/phase-meta/{host}-{phase}"
            committed = {}
            for name in META:
                data = git_blob(repository, commit, f"{meta}/{name}")
                require(0 < len(data) <= MAX_BYTES, f"committed phase-meta size outside 1..95 MiB: {meta}/{name}")
                committed[name] = dict(sha256=sha_bytes(data), size=len(data), repository_path=f"{meta}/{name}")
            launch, exit_ = committed["launch.json"]["sha256"], committed["supervisor-exit.json"]["sha256"]
            require((launch, exit_) == EXPECTED[(host, phase)], f"committed phase-meta SHA differs from the table: {meta}")
            require(completion["supervisor_exits"][f"{host}/{phase}"]["sha256"] == exit_,
                    f"completion supervisor_exits SHA differs from phase-meta: {host}/{phase}")
            plan.append(dict(host=host, phase=phase, namespace=namespace, directory=phase_dir(host, namespace, phase),
                             committed=committed))
    return plan


# ---------------------------------------------------------------- remote commands (exact literal paths only)

def host_paths(plan, host, names):
    out = []
    for entry in plan:
        if entry["host"] == host:
            for name in names:
                path = entry["directory"] + "/" + name
                require(SAFE_PATH.fullmatch(path) is not None and ":" not in path, "unsafe path: " + path)
                require(not any(path.startswith(p) for p in FORBIDDEN_PREFIXES[host]), "forbidden path: " + path)
                out.append((entry, name, path))
    return out


def remote(mode, args):
    return (f"set -eu; LC_ALL=C; export LC_ALL; exec nice -n 19 {REMOTE_PYTHON} -I -S -c "
            + shlex.quote(REMOTE_PROGRAM) + f" {mode} " + " ".join(shlex.quote(a) for a in args))


def inspect_command(paths):
    """Size rules: launch/exit exactly the committed size; mhz/census 1..MAX_BYTES. Checked before any read."""
    args = []
    for entry, name, path in paths:
        if name in META:
            args.append(f"exact:{entry['committed'][name]['size']}:{path}")
        else:
            args.append(f"max:{MAX_BYTES}:{path}")
    return remote("inspect", args)


def copy_command(paths, first):
    return remote("stream", [f"{first[p]['size']}:{first[p]['st_dev']}:{first[p]['st_ino']}:{p}" for _, _, p in paths])


def ssh_argv(ssh, host, command):
    require(host in HOSTS, "unknown host: " + host)
    return [ssh, *SSH_OPTIONS, "--", host, command]


class Session:
    """Every login: argv list (no shell on 05), stdin /dev/null, bounded stdout, stderr tail only, hard timeout."""

    def __init__(self, ssh, log):
        self.ssh, self.log, self.logins = ssh, log, []

    def _start(self, host, command, label):
        argv = ssh_argv(self.ssh, host, command)
        self.logins.append(dict(label=label, host=host, started_utc=utc(), argv=argv))
        self.log(f"[{utc()}] ssh {label} {host}")
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tail = bytearray()

        def drain():
            for chunk in iter(lambda: proc.stderr.read(4096), b""):
                tail.extend(chunk)
                del tail[:-STDERR_TAIL]
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        return proc, tail, reader

    def _finish(self, proc, tail, reader, label, host, timer, fired):
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
        rc = proc.wait()
        reader.join(5)
        self.logins[-1].update(finished_utc=utc(), returncode=rc)
        require(not fired, f"ssh {label} {host} timed out")
        return rc, bytes(tail).decode(errors="replace")

    def run(self, host, command, label, timeout=900):
        proc, tail, reader = self._start(host, command, label)
        fired = []
        timer = threading.Timer(timeout, lambda: (fired.append(1), proc.kill()))
        timer.start()
        try:
            stdout = proc.stdout.read(INSPECT_OUTPUT_LIMIT + 1)
            too_long = len(stdout) > INSPECT_OUTPUT_LIMIT
        finally:
            rc, err = self._finish(proc, tail, reader, label, host, timer, fired)
        require(not too_long, f"ssh {label} {host}: output exceeds {INSPECT_OUTPUT_LIMIT} bytes")
        refusals = [line for line in stdout.decode(errors="replace").splitlines() if line.startswith("REFUSE|")]
        if refusals:
            raise Refusal(f"ssh {label} {host}: REMOTE REFUSE: {refusals[0]}")
        require(rc == 0, f"ssh {label} {host} failed rc={rc}: " + err[-400:])
        return stdout

    def stream(self, host, command, pieces, dest, timeout=3600):
        """Read exactly sum(sizes) bytes into exclusive per-file outputs; one more byte = excess = refusal."""
        proc, tail, reader = self._start(host, command, "C")
        fired = []
        timer = threading.Timer(timeout, lambda: (fired.append(1), proc.kill()))
        timer.start()
        written, failure = [], None
        try:
            for path, row in pieces:
                entry = row["entry"]
                h, left, fd, directory = hashlib.sha256(), row["size"], None, None
                try:
                    while left:
                        chunk = proc.stdout.read(min(CHUNK, left))
                        if not chunk:
                            break
                        if fd is None:                     # created only once its first byte has arrived
                            directory = dest.phase_dir(entry["host"], entry["phase"])
                            fd = create_exclusive(directory, row["name"])
                            dest.files.append(f"{entry['host']}/{entry['phase']}/{row['name']}")
                        h.update(chunk)
                        write_all(fd, chunk)
                        left -= len(chunk)
                    if fd is not None:
                        os.fsync(fd)
                finally:
                    if fd is not None:
                        os.close(fd)
                if left:
                    failure = f"copy stream ended early ({left} bytes missing) in {path}"
                    break
                written.append((path, row, directory, h.hexdigest()))
            if failure is None and proc.stdout.read(1):
                failure = "copy stream carries excess bytes beyond the login-P sizes; ssh killed"
                proc.kill()
        finally:
            rc, err = self._finish(proc, tail, reader, "C", host, timer, fired)
        require(failure is None, f"ssh C {host}: {failure} (rc={rc}; {err[-300:]})")
        require(rc == 0, f"ssh C {host} failed rc={rc}: " + err[-400:])
        for path, row, directory, digest in written:
            require(digest == row["sha256"], f"local copy SHA differs from on-host SHA: {path}")
            again, size = sha_at(directory, row["name"])
            require(again == row["sha256"] and size == row["size"], f"local file re-read differs: {path}")
        return written


def parse_inspection(stdout, paths, label):
    lines = stdout.decode(errors="replace").splitlines()
    n = len(paths)
    require(len(lines) == n, f"{label}: unexpected inspection output ({len(lines)} lines, want {n})")
    out = {}
    for (entry, name, path), line in zip(paths, lines):
        fields = line.split("|")
        require(len(fields) == 7 and fields[0] == "OK" and fields[6] == path
                and all(f.isdigit() for f in fields[1:5]) and SHA.fullmatch(fields[5]) is not None,
                f"{label}: bad inspection line for {path}: {line[:200]!r}")
        size, nlink, dev, ino = map(int, fields[1:5])
        require(nlink == 1, f"{label}: {path} is a hard-link alias")
        if name in META:
            require(size == entry["committed"][name]["size"], f"{label}: {path} size differs from committed")
        else:
            require(0 < size <= MAX_BYTES, f"{label}: REFUSE {path} is {size} bytes, outside 1..{MAX_BYTES}")
        out[path] = dict(entry=entry, name=name, size=size, sha256=fields[5], st_dev=dev, st_ino=ino)
    return out


def check_inspection(found, label):
    """Launch/exit identity of every phase directory (the remote side already gated type, alias and size)."""
    for path, row in found.items():
        if row["name"] in META:
            want = row["entry"]["committed"][row["name"]]["sha256"]
            require(row["sha256"] == want, f"{label}: REFUSE on-host {path} SHA {row['sha256']} != committed {want}")
        else:
            require(0 < row["size"] <= MAX_BYTES, f"{label}: REFUSE {path} is {row['size']} bytes, "
                    f"outside 1..{MAX_BYTES} (95 MiB)")


# ---------------------------------------------------------------- run

class Context:
    def __init__(self):
        self.session = None
        self.dest = None


def run(a, context, log=print):
    started = utc()
    testing = test_mode()
    plan = expectations(a.repository, a.commit)
    inspections = {h: host_paths(plan, h, NAMES) for h in HOSTS}
    copies = {h: host_paths(plan, h, SOURCES) for h in HOSTS}
    if a.dry_run:
        log(json.dumps(dict(mode="dry-run", commit=a.commit, logins=6, max_bytes=MAX_BYTES, test_mode=testing,
                            expected={f"{e['host']}/{e['phase']}": {k: v for k, v in e["committed"].items()}
                                      for e in plan}), indent=1))
        placeholder = {p: dict(size="<P size>", st_dev="<P dev>", st_ino="<P ino>") for h in HOSTS
                       for _, _, p in copies[h]}
        for label, host, command in ([("P", h, inspect_command(inspections[h])) for h in HOSTS]
                                     + [x for h in HOSTS for x in (("C", h, copy_command(copies[h], placeholder)),
                                                                  ("V", h, inspect_command(inspections[h])))]):
            log(f"# login {label} {host}")
            log(shlex.join(ssh_argv(a.ssh, host, command)))
        return None
    require(a.outside_end_window, "live run requires --outside-end-window '<coordinator GO / window reference>'")
    require(a.dest is not None, "--dest is required unless --dry-run")
    dest = Destination(a.dest)                                 # validated (not created) before any login
    context.dest = dest
    ssh = shutil.which(a.ssh)
    require(ssh is not None, "ssh not found: " + a.ssh)
    if not testing:
        require(os.path.realpath(ssh) == SSH_BINARY, f"production ssh must be {SSH_BINARY}, got {ssh}")
    session = Session(ssh, log)
    context.session = session
    first = {}
    for host in HOSTS:                                         # every check on both hosts before any copy
        stdout = session.run(host, inspect_command(inspections[host]), "P")
        first[host] = parse_inspection(stdout, inspections[host], f"P {host}")
        check_inspection(first[host], f"P {host}")
    dest.create()
    files = []
    for host in HOSTS:
        pieces = [(p, first[host][p]) for _, _, p in copies[host]]
        written = session.stream(host, copy_command(copies[host], first[host]), pieces, dest)
        again = parse_inspection(session.run(host, inspect_command(inspections[host]), "V"), inspections[host],
                                 f"V {host}")
        for path, row in first[host].items():
            then = (row["size"], row["sha256"], row["st_dev"], row["st_ino"])
            now = (again[path]["size"], again[path]["sha256"], again[path]["st_dev"], again[path]["st_ino"])
            require(now == then, f"V {host}: on-host file changed during the copy: {path}")
        for path, row, directory, digest in written:
            local_sha, local_size = sha_at(directory, row["name"])
            files.append(dict(host=host, phase=row["entry"]["phase"], name=row["name"], remote_path=path,
                              remote_size=row["size"], remote_sha256_before=row["sha256"],
                              remote_sha256_after=again[path]["sha256"], remote_st_dev=row["st_dev"],
                              remote_st_ino=row["st_ino"], local_path=f"{host}/{row['entry']['phase']}/{row['name']}",
                              local_size=local_size, local_sha256=local_sha))
    meta = [dict(host=r["entry"]["host"], phase=r["entry"]["phase"], name=r["name"], remote_path=p,
                 remote_size=r["size"], remote_sha256=r["sha256"], remote_st_dev=r["st_dev"], remote_st_ino=r["st_ino"],
                 committed_size=r["entry"]["committed"][r["name"]]["size"],
                 committed_sha256=r["entry"]["committed"][r["name"]]["sha256"],
                 committed_repository_path=r["entry"]["committed"][r["name"]]["repository_path"])
            for host in HOSTS for p, r in first[host].items() if r["name"] in META]
    on_disk = dest.listing()
    require(on_disk == sorted(f["local_path"] for f in files) and len(files) == 2 * len(plan),
            "destination holds unexpected files: " + ",".join(on_disk[:5]))
    manifest = dict(schema=TEST_SCHEMA if testing else SCHEMA, test_mode=testing, status="copied",
                    started_utc=started, finished_utc=utc(), outside_end_window=a.outside_end_window,
                    repository_commit=a.commit, script_sha256=sha_file(os.path.realpath(__file__)), ssh=ssh,
                    ssh_logins=len(session.logins), logins=session.logins, max_bytes=MAX_BYTES,
                    remote_program_sha256=sha_bytes(REMOTE_PROGRAM.encode()), remote_python=REMOTE_PYTHON,
                    dest=dest.path, dest_identity=dest.identity, files=files, meta=meta)
    data = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    write_exclusive(dest.fd, "s1-copy-manifest.json", data)
    log(f"S1 OK: {len(files)} files, {len(session.logins)} ssh logins, manifest {sha_bytes(data)}")
    return manifest


def write_refusal(context, error, status):
    """Receipt in the declared REFUSAL_DIR (always) and in dest (only if this run created it)."""
    testing = os.environ.get(TEST_ENV) == TEST_MARKER
    dest = context.dest
    record = dict(schema=TEST_REFUSAL_SCHEMA if testing else REFUSAL_SCHEMA, test_mode=testing, status=status,
                  error_type=type(error).__name__, error=str(error), utc=utc(), argv=sys.argv[1:],
                  logins=context.session.logins if context.session else [],
                  dest=dest.path if dest else None, dest_created=bool(dest and dest.fd is not None),
                  partial_files=list(dest.files) if dest else [])
    data = (json.dumps(record, indent=1, sort_keys=True) + "\n").encode()
    where = []
    directory = REFUSAL_DIR
    try:
        directory = canonical_abs(configured("REFUSAL_DIR", REFUSAL_DIR) if testing else REFUSAL_DIR,
                                  "refusal directory")
        fd = open_dir(directory, "refusal directory", create_leaf=True)
        try:
            name = f"S1-REFUSAL-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}-{secrets.token_hex(4)}.json"
            write_exclusive(fd, name, data)
            where.append(directory + "/" + name)
        finally:
            os.close(fd)
    except Exception as failure:                              # never write anywhere else
        print(f"S1 REFUSAL RECEIPT NOT WRITTEN to {directory}: {failure}", file=sys.stderr)
    if dest is not None and dest.fd is not None:
        try:
            write_exclusive(dest.fd, "S1-REFUSAL.json", data)
            where.append(dest.path + "/S1-REFUSAL.json")
        except Exception as failure:
            print(f"S1 refusal copy not written into dest: {failure}", file=sys.stderr)
    return where


class Parser(argparse.ArgumentParser):
    def error(self, message):                                 # argument errors are refusals with a receipt
        raise Refusal("argument error: " + message)


def main(argv=None):
    ap = Parser(description=__doc__.split("\n")[0])
    ap.add_argument("--repository", required=True, help="local clasher checkout (read with git show only)")
    ap.add_argument("--commit", required=True, help="full commit holding phase-meta, history.json and completion-v2")
    ap.add_argument("--dest", help="new canonical staging dir strictly below " + DEST_ROOT + " (must not exist)")
    ap.add_argument("--ssh", default="ssh", help="production: must resolve to " + SSH_BINARY)
    ap.add_argument("--outside-end-window", default="", help="required for a live run: GO/window reference")
    ap.add_argument("--dry-run", action="store_true")
    context = Context()
    try:
        a = ap.parse_args(argv)
        run(a, context)
    except SystemExit:                                        # --help
        raise
    except Refusal as error:
        receipts = write_refusal(context, error, "refused")
        print("S1 REFUSED: " + str(error) + "".join("\n  receipt: " + r for r in receipts), file=sys.stderr)
        return 2
    except Exception as error:                                # fail closed on anything unexpected
        receipts = write_refusal(context, error, "failed")
        print(f"S1 FAILED: {type(error).__name__}: {error}" + "".join("\n  receipt: " + r for r in receipts),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
