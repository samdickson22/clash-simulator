"""safe_input: the ONE shared read/write/subprocess gate for the PREREG-K4S END tooling (ruling P2-1). CANDIDATE r1.

Stdlib only; Python 3.8+; Linux only (O_NOFOLLOW / O_DIRECTORY / dir_fd). No check is an `assert`: every gate is an
explicit raise of Refusal, so it holds under `python -O`. Nothing here does I/O at import time.

Semantics (README.md has the full contract and the residuals):

* Policy / Role. A Policy is built from an explicit host and explicit roles. A Role is (name, absolute root, access
  'read' | 'write', max_size, exact relative names and/or component-wise patterns, exemptions subset of {E1, E4},
  grants subset of GRANTS). There are no defaults: an unknown role refuses, a role with no names refuses.
* Names first. Every path (role root + relative name) is refused by NAME before any syscall touches it:
  malformed ('', '.', '..', absolute, trailing '/', NUL/control/backslash), outcome components (games, hub-blocks
  and their '.x' variants), outcome leaves (complete.json family, interference.json, hub-ack.json,
  hub-ack.returned.json, end-raw.json, local-/end-complete.json, and '<name>.tmp' / '.<name>' variants) in ANY
  component, K4S reporting jobs (k4s-confirm-*), live guard jobs (k4s-end-guard-*), the strict END namespace
  (consecutive components k4s-confirm/end), FROZEN-T1 launch namespaces, the 04 perception root and the v4 cache
  repo. Only three grants can lift a namespace rule, each for exact names only (reporting-job-exact, end-json-exact,
  guard-job); outcome names, T1 and perception roots can never be granted. Then the role allowlist.
* Walk. The root must be canonical (realpath == root, every ancestor lstat-checked: no symlink). The walk opens
  '/' and then every component with O_DIRECTORY|O_NOFOLLOW (each lstat'ed via fstatat first; the opened fd must be
  the same dev/ino). The leaf is fstatat'ed WITHOUT opening (symlink, FIFO, socket, device, directory, st_nlink != 1
  and size > cap all refuse before open), then opened O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY and fstat'ed again
  (regular, same dev/ino, st_nlink == 1, size <= cap, optional exact size) BEFORE any byte is read.
* Reads take exactly the inspected size from the gated fd (short read = shrink, an extra byte = growth), with an
  optional expected SHA-256 checked before bytes are returned. read_json is size-capped, strict UTF-8, refuses
  duplicate keys and NaN/Infinity.
* E1: only the root-level symlink visualize_battle.py with exact link text examples/visualize_battle.py, validated
  by readlinkat without following; the target is opened through the normal gate. E4: exactly four tracked
  complete.json path+SHA pairs; hash_e4/copy_e4/git_hash_e4 never return bytes; any other complete.json refuses.
* Writes: Writer holds the canonical root fd; mkdir_excl / create_excl / open_excl use O_CREAT|O_EXCL|O_NOFOLLOW
  (mkdirat for directories) relative to component-wise opened parents; never truncate, never overwrite, fsync file
  and directory. write_refusal_receipt writes a write-once receipt into a declared refusal role.
* Subprocess: run_checked(argv) with an explicit absolute argv[0], no shell, explicit env, bounded stdout/stderr,
  watchdog timeout (process-group kill), and rc checked BEFORE the caller can see stdout. hostname_checked,
  ps_checked and git_* require rc == 0; valid-looking stdout with a nonzero rc refuses.
* Remote: remote_program_source() returns the exact source shipped over ssh stdin (the same _CORE gate code that
  this module executes locally, plus a small main); the request is explicit JSON passed as one hex argv word.
  parse_remote_response() validates the reply strictly.

The single accepted residual (coordinator scope ruling 2026-10-12 16:00Z): concurrent replacement of a path between
a check and its use by another local actor (TOCTOU). Static aliases, hard links and forbidden locations are not
residuals; they refuse.
"""
import binascii
import fnmatch
import hashlib
import json
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time

# ---------------------------------------------------------------------------------------------------------------------
# _CORE: the gate code shared verbatim by this module (exec'd below) and by the remote reader program
# (remote_program_source()). One source of truth for names, the component walk and the leaf gate. Python 3.8, stdlib.
# ---------------------------------------------------------------------------------------------------------------------
_CORE = r'''
import errno, hashlib, os, re, stat

HOSTS = tuple("127x%02d" % _i for _i in range(1, 19))
OUTCOME_DIRS = ("games", "hub-blocks")
OUTCOME_LEAVES = ("complete.json", "local-complete.json", "end-complete.json", "interference.json",
                  "hub-ack.json", "hub-ack.returned.json", "end-raw.json")
REPORTING_JOB = re.compile(r"k4s-confirm-.*", re.S)
GUARD_JOB = re.compile(r"k4s-end-guard-.*", re.S)
END_PAIR = ("k4s-confirm", "end")
T1_LAUNCH_NAMESPACES = (                       # FROZEN-T1.json launch_namespaces (S4 r3b T1_LAUNCH_NAMESPACES)
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op5-08join-r2",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/smoke-after-op6-08-r7",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op6-0108-r1",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op6-01-r1",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/qualified-op6-08-r1",
)
PERCEPTION_PREFIXES = {"127x04": ("/mpac/sdicks02/jobs",)}       # 04 perception storage (S1/S1b FORBIDDEN_PREFIXES)
GLOBAL_FORBIDDEN_PREFIXES = ("/mpac/sdicks02/repos/clasher-v4-cache",)
GRANTS = ("reporting-job-exact", "end-json-exact", "guard-job")
E4_COMPLETE_JSON = {                           # COORDINATOR 2026-10-12 17:12Z ruling E4 (E2 first). Hash only.
    "imitation/model/receipts/throughput-0935/complete.json":
        "d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc",
    "reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json":
        "0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json":
        "9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json":
        "724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d",
}
CHUNK = 1 << 20
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC


class Refusal(Exception):
    """Fail-closed refusal. `code` is a stable machine-readable class; `reason` is human text."""

    def __init__(self, code, reason):
        Exception.__init__(self, code + ": " + reason)
        self.code = code
        self.reason = reason


def refuse(code, reason):
    raise Refusal(code, reason)


def _bad_text(text):
    return "\\" in text or any(ord(c) < 32 or ord(c) == 127 for c in text)


def check_abs(path):
    """A normalized absolute path other than '/'; returns its components."""
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or path == "/"
            or path.endswith("/") or _bad_text(path)):
        refuse("path", "not a usable absolute path: %r" % (path,))
    parts = path[1:].split("/")
    if any(p in ("", ".", "..") for p in parts):
        refuse("path", "empty, '.' or '..' component: %r" % (path,))
    return parts


def check_rel(rel):
    """A normalized relative path; returns its components."""
    if not isinstance(rel, str) or rel == "" or rel.startswith("/") or rel.endswith("/") or _bad_text(rel):
        refuse("path", "not a usable relative path: %r" % (rel,))
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        refuse("path", "empty, '.' or '..' component: %r" % (rel,))
    return parts


def _family(name, base):
    return name == base or name.startswith(base + ".") or name.startswith("." + base)


def name_gate(path, host, grants, e4_leaf=False):
    """Refuse an absolute path by NAME only (no syscall). `e4_leaf` exempts only a final component that is exactly
    'complete.json' (the caller has already matched the exact E4 path)."""
    if host not in HOSTS:
        refuse("policy", "unknown host %r" % (host,))
    parts = check_abs(path)
    folded = [p.casefold() for p in parts]
    last = len(parts) - 1
    for i, p in enumerate(folded):
        for d in OUTCOME_DIRS:
            if _family(p, d):
                refuse("name", "outcome directory component %r in %s" % (parts[i], path))
        for leaf in OUTCOME_LEAVES:
            if _family(p, leaf) and not (e4_leaf and i == last and parts[i] == "complete.json"):
                refuse("name", "outcome name %r in %s" % (parts[i], path))
        if REPORTING_JOB.fullmatch(p) and "reporting-job-exact" not in grants:
            refuse("name", "K4S reporting job component %r in %s" % (parts[i], path))
        if GUARD_JOB.fullmatch(p) and "guard-job" not in grants:
            refuse("name", "guard job component %r in %s" % (parts[i], path))
        if i < last and (p, folded[i + 1]) == END_PAIR:
            if "end-json-exact" not in grants:
                refuse("name", "strict END namespace k4s-confirm/end in %s" % path)
            if i + 1 == last or not folded[last].endswith(".json"):
                refuse("name", "strict END namespace: only named .json files inside it: %s" % path)
    lowered = path.casefold()
    for prefix in T1_LAUNCH_NAMESPACES + GLOBAL_FORBIDDEN_PREFIXES + PERCEPTION_PREFIXES.get(host, ()):
        if lowered == prefix.casefold() or lowered.startswith(prefix.casefold() + "/"):
            refuse("name", "forbidden namespace %s for %s: %s" % (prefix, host, path))
    return parts


def _classify(error):
    if error.errno == errno.ELOOP:
        return "symlink"
    if error.errno == errno.ENOTDIR:
        return "not-dir"
    if error.errno == errno.ENOENT:
        return "missing"
    return "open"


def open_dirs(start_fd, parts, label):
    """openat each component under start_fd with O_DIRECTORY|O_NOFOLLOW (fstatat'ed first, same dev/ino after).
    Returns a NEW fd (start_fd stays open)."""
    fd = os.dup(start_fd)
    try:
        for part in parts:
            try:
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except OSError as error:
                refuse(_classify(error), "%s: component %r: %s" % (label, part, os.strerror(error.errno)))
            if stat.S_ISLNK(st.st_mode):
                refuse("symlink", "%s: component %r is a symlink" % (label, part))
            if not stat.S_ISDIR(st.st_mode):
                refuse("not-dir", "%s: component %r is not a directory" % (label, part))
            try:
                nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                code = _classify(error)
                try:                                     # O_DIRECTORY|O_NOFOLLOW on a symlink gives ENOTDIR
                    if stat.S_ISLNK(os.stat(part, dir_fd=fd, follow_symlinks=False).st_mode):
                        code = "symlink"
                except OSError:
                    pass
                refuse(code, "%s: component %r: %s" % (label, part, os.strerror(error.errno)))
            now = os.fstat(nxt)
            if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
                os.close(nxt)
                refuse("changed", "%s: component %r changed between check and open" % (label, part))
            os.close(fd)
            fd = nxt
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_root(root):
    """A canonical root directory: realpath == root, every ancestor lstat'ed (no symlink), then a component-wise
    O_DIRECTORY|O_NOFOLLOW walk from '/'. Returns an fd."""
    parts = check_abs(root)
    for i in range(len(parts)):
        prefix = "/" + "/".join(parts[:i + 1])
        try:
            st = os.lstat(prefix)
        except OSError as error:
            refuse("root", "root %s: %s: %s" % (root, prefix, os.strerror(error.errno)))
        if stat.S_ISLNK(st.st_mode):
            refuse("root", "root %s: ancestor or root %s is a symlink" % (root, prefix))
        if not stat.S_ISDIR(st.st_mode):
            refuse("root", "root %s: %s is not a directory" % (root, prefix))
    if os.path.realpath(root) != root:
        refuse("root", "root %s is not canonical" % root)
    top = os.open("/", DIR_FLAGS)
    try:
        return open_dirs(top, parts, "root " + root)
    except Refusal as error:
        refuse("root", error.reason)
    finally:
        os.close(top)


def open_leaf(dir_fd, name, cap, expected_size, label):
    """The descriptor gate. fstatat (no open) refuses symlink / non-regular / st_nlink != 1 / oversize; then
    O_NOFOLLOW|O_NONBLOCK open and fstat: regular, same dev/ino, st_nlink == 1, size within cap (and == expected)."""
    try:
        st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError as error:
        refuse(_classify(error), "%s: %s" % (label, os.strerror(error.errno)))
    if stat.S_ISLNK(st.st_mode):
        refuse("symlink", "%s: leaf is a symlink" % label)
    if not stat.S_ISREG(st.st_mode):
        refuse("not-regular", "%s: leaf is not a regular file (mode %o)" % (label, st.st_mode))
    if st.st_nlink != 1:
        refuse("nlink", "%s: hard-linked leaf (st_nlink %d)" % (label, st.st_nlink))
    if st.st_size > cap or (expected_size is not None and st.st_size != expected_size):
        refuse("size", "%s: size %d (cap %d, expected %r)" % (label, st.st_size, cap, expected_size))
    try:
        fd = os.open(name, LEAF_FLAGS, dir_fd=dir_fd)
    except OSError as error:
        refuse(_classify(error), "%s: %s" % (label, os.strerror(error.errno)))
    now = os.fstat(fd)
    problem = None
    if not stat.S_ISREG(now.st_mode):
        problem = ("not-regular", "opened object is not a regular file")
    elif (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
        problem = ("changed", "leaf changed between check and open")
    elif now.st_nlink != 1:
        problem = ("nlink", "hard-linked leaf at open (st_nlink %d)" % now.st_nlink)
    elif now.st_size > cap or (expected_size is not None and now.st_size != expected_size):
        problem = ("size", "size at open %d (cap %d, expected %r)" % (now.st_size, cap, expected_size))
    if problem is not None:
        os.close(fd)
        refuse(problem[0], "%s: %s" % (label, problem[1]))
    return fd, now


def read_exact(fd, size, sink, label):
    """Exactly `size` bytes from the gated fd into sink; a short read refuses (shrink), an extra byte refuses
    (growth)."""
    left = size
    while left:
        chunk = os.read(fd, min(CHUNK, left))
        if not chunk:
            refuse("shrink", "%s: file shrank while read" % label)
        sink(chunk)
        left -= len(chunk)
    if os.read(fd, 1):
        refuse("growth", "%s: file grew while read" % label)
    if os.fstat(fd).st_size != size:
        refuse("growth", "%s: size changed while read" % label)
'''

exec(compile(_CORE, "<safe_input _CORE>", "exec"), globals())   # defines the names above in this module

# ---------------------------------------------------------------------------------------------------------------------
# Single-source constants (item 10)
# ---------------------------------------------------------------------------------------------------------------------
APPROVED_K4S_MANIFEST_SHA256 = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
END_BASES = {"127x03": "/mpac/sdicks02/jobs/clasher/k4s-end-r1", "127x04": "/mpac/sdicks02/jobs-k4s/k4s-end-r1"}
Q4_GUARD_PARENTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
GUARD_JOB_NAME = re.compile(r"k4s-end-guard-r[1-9][0-9]*-(rd[0-9]{2}-a[0-9]{2}|pf[0-9]{2})")
STRICT_END_DIR = "reports/explore/k4s-confirm/end"
E3_ADMISSIONS_DIR = "reports/explore/k4s-confirm/end-guard-admissions"
E1_ALIAS = "visualize_battle.py"
E1_LINK_TEXT = "examples/visualize_battle.py"
E2_PATH = "imitation/model/receipts/throughput-0935/complete.json"
EXEMPTIONS = ("E1", "E4")
REMOTE_PYTHON = "/usr/bin/python3"
SSH_BINARY = "/usr/bin/ssh"
SSH_OPTIONS = ("-T", "-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=4", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no")
MAX_ROLE_SIZE = 64 << 30
REMOTE_REQUEST_SCHEMA = "clasher.k4s.safe-input.remote-request.v1"
REMOTE_RESPONSE_SCHEMA = "clasher.k4s.safe-input.remote-response.v1"
REMOTE_MAX_ITEMS = 256
REMOTE_MAX_CONTENT = 8 << 20
REFUSAL_SCHEMA = "clasher.k4s.safe-input-refusal.v1"
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_ROLE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def constants_fingerprint():
    """SHA-256 of the canonical JSON of every single-source constant (names, namespaces, E1/E2/E3/E4, bases, Q4,
    manifest). Adopters pin this value (README.md) so a silently edited copy of this layer is detectable."""
    doc = {"hosts": list(HOSTS), "outcome_dirs": list(OUTCOME_DIRS), "outcome_leaves": list(OUTCOME_LEAVES),
           "reporting_job": REPORTING_JOB.pattern, "guard_job": GUARD_JOB.pattern, "end_pair": list(END_PAIR),
           "t1_launch_namespaces": list(T1_LAUNCH_NAMESPACES),
           "perception_prefixes": {k: list(v) for k, v in PERCEPTION_PREFIXES.items()},
           "global_forbidden_prefixes": list(GLOBAL_FORBIDDEN_PREFIXES), "grants": list(GRANTS),
           "e4": E4_COMPLETE_JSON, "approved_manifest": APPROVED_K4S_MANIFEST_SHA256, "end_bases": END_BASES,
           "q4_guard_parents": Q4_GUARD_PARENTS, "guard_job_name": GUARD_JOB_NAME.pattern,
           "strict_end_dir": STRICT_END_DIR, "e3_admissions_dir": E3_ADMISSIONS_DIR,
           "e1": [E1_ALIAS, E1_LINK_TEXT], "e2": E2_PATH}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require(condition, code, reason):
    if not condition:
        refuse(code, reason)


# ---------------------------------------------------------------------------------------------------------------------
# Policy and roles (item 1)
# ---------------------------------------------------------------------------------------------------------------------
def _pattern_parts(pattern):
    parts = check_rel(pattern)
    for p in parts:
        require(p == "**" or "**" not in p, "policy", "'**' must be a whole component: %r" % pattern)
    return parts


def _match(pparts, rparts):
    if not pparts:
        return not rparts
    head = pparts[0]
    if head == "**":
        return any(_match(pparts[1:], rparts[i:]) for i in range(len(rparts) + 1))
    return bool(rparts) and fnmatch.fnmatchcase(rparts[0], head) and _match(pparts[1:], rparts[1:])


def _names(value, label):
    require(isinstance(value, (tuple, list, frozenset, set)) and all(isinstance(v, str) for v in value),
            "policy", "%s must be a collection of strings" % label)
    return tuple(sorted(set(value)))


class Role(object):
    """One declared input/output role. All fields are explicit; nothing defaults to 'allowed'."""
    __slots__ = ("name", "root", "access", "max_size", "exact", "patterns", "exemptions", "grants", "_pparts")

    def __init__(self, name, root, access, max_size, exact=(), patterns=(), exemptions=(), grants=()):
        require(isinstance(name, str) and _ROLE_NAME.fullmatch(name) is not None, "policy", "bad role name %r" % name)
        check_abs(root)
        require(access in ("read", "write"), "policy", "role %s: access must be 'read' or 'write'" % name)
        require(type(max_size) is int and 0 < max_size <= MAX_ROLE_SIZE, "policy", "role %s: bad max_size" % name)
        exact, patterns = _names(exact, "exact"), _names(patterns, "patterns")
        exemptions, grants = frozenset(_names(exemptions, "exemptions")), frozenset(_names(grants, "grants"))
        require(exact or patterns, "policy", "role %s declares no names" % name)
        for rel in exact:
            check_rel(rel)
        pparts = tuple(_pattern_parts(p) for p in patterns)
        require(exemptions <= frozenset(EXEMPTIONS), "policy", "role %s: unknown exemption" % name)
        require(grants <= frozenset(GRANTS), "policy", "role %s: unknown grant" % name)
        require(not (grants & {"reporting-job-exact", "end-json-exact"}) or not patterns, "policy",
                "role %s: reporting-job/END grants require exact names only" % name)
        require("end-json-exact" not in grants or all(r.endswith(".json") for r in exact), "policy",
                "role %s: end-json-exact allows named .json files only" % name)
        self.name, self.root, self.access, self.max_size = name, root, access, max_size
        self.exact, self.patterns, self.exemptions, self.grants, self._pparts = exact, patterns, exemptions, grants, pparts

    def allows(self, rel):
        parts = rel.split("/")
        return rel in self.exact or any(_match(p, parts) for p in self._pparts)

    def __setattr__(self, key, value):
        require(not hasattr(self, "_pparts"), "policy", "Role is immutable")
        object.__setattr__(self, key, value)


class Policy(object):
    """host + roles. A local policy (remote=False) must run on `host` (nodename check); a remote policy describes
    another host's paths and is only used to build remote requests."""

    def __init__(self, host, roles, remote=False):
        require(host in HOSTS, "policy", "unknown host %r" % (host,))
        require(remote in (True, False), "policy", "remote must be a bool")
        if not remote:
            node = os.uname().nodename.split(".")[0]
            require(node == host, "policy", "local policy for %s but this host is %s" % (host, node))
        table = {}
        for role in roles:
            require(isinstance(role, Role), "policy", "roles must be Role objects")
            require(role.name not in table, "policy", "duplicate role %s" % role.name)
            name_gate(role.root, host, role.grants)
            table[role.name] = role
        require(table, "policy", "policy declares no roles")
        self.host, self.remote, self._roles = host, remote, table

    def role(self, name):
        role = self._roles.get(name) if isinstance(name, str) else None
        require(role is not None, "policy", "unknown role %r" % (name,))
        return role


def _gate(policy, role_name, rel, access, e4=False):
    """Every name-level check for (role, rel), in order, with no syscall. Returns (role, parts)."""
    require(isinstance(policy, Policy), "policy", "a Policy is required")
    role = policy.role(role_name)
    require(role.access == access, "policy", "role %s is not a %s role" % (role.name, access))
    parts = check_rel(rel)
    e4_leaf = bool(e4) and "E4" in role.exemptions and rel in E4_COMPLETE_JSON
    require(not e4 or e4_leaf, "exemption", "not an exact E4 path for an E4 role: %s" % rel)
    name_gate(role.root + "/" + rel, policy.host, role.grants, e4_leaf=e4_leaf)
    require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))
    return role, parts


def gate_names(policy, role_name, rel, e4=False):
    """Public pure check: True or Refusal, for planning (no syscall)."""
    role = policy.role(role_name)
    _gate(policy, role_name, rel, role.access, e4)
    return role.root + "/" + rel


# ---------------------------------------------------------------------------------------------------------------------
# Reads (items 2, 3, 6)
# ---------------------------------------------------------------------------------------------------------------------
class Input(object):
    """A gated open regular file. Its bytes are reachable only through these methods, each usable once."""

    def __init__(self, fd, st, label):
        self._fd, self.size, self.dev, self.ino, self.label = fd, st.st_size, st.st_dev, st.st_ino, label

    def _consume(self, sink):
        require(self._fd is not None, "state", "%s already consumed or closed" % self.label)
        try:
            read_exact(self._fd, self.size, sink, self.label)
        finally:
            self.close()

    def read_bytes(self, expected_sha256=None):
        chunks = []
        self._consume(chunks.append)
        data = b"".join(chunks)
        if expected_sha256 is not None:
            require(hashlib.sha256(data).hexdigest() == expected_sha256, "sha", "%s: SHA-256 mismatch" % self.label)
        return data

    def sha256(self):
        digest = hashlib.sha256()
        self._consume(digest.update)
        return digest.hexdigest()

    def copy_to(self, writer, dst_rel, expected_sha256=None, mode=0o444):
        try:
            out = writer.open_excl(dst_rel)
        except BaseException:
            self.close()
            raise
        try:
            self._consume(out.write)
        except BaseException:
            out.abort()
            raise
        result = out.finish(mode)
        if expected_sha256 is not None:
            require(result["sha256"] == expected_sha256, "sha", "%s: copied SHA-256 mismatch (partial kept at %s)"
                    % (self.label, dst_rel))
        return result

    def close(self):
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _open_gated(policy, role_name, rel, expected_size, max_size, e4):
    role, parts = _gate(policy, role_name, rel, "read", e4)
    cap = role.max_size if max_size is None else min(role.max_size, max_size)
    require(type(cap) is int and cap > 0, "policy", "bad max_size")
    require(expected_size is None or type(expected_size) is int, "policy", "bad expected_size")
    label = "%s:%s" % (role.name, rel)
    root = open_root(role.root)
    try:
        parent = open_dirs(root, parts[:-1], label)
    finally:
        os.close(root)
    try:
        fd, st = open_leaf(parent, parts[-1], cap, expected_size, label)
    finally:
        os.close(parent)
    return Input(fd, st, label)


def open_input(policy, role_name, rel, expected_size=None, max_size=None):
    """Gate everything (names, allowlist, root, components, descriptor) and return an Input. Never for E4 paths."""
    return _open_gated(policy, role_name, rel, expected_size, max_size, e4=False)


def read_bytes(policy, role_name, rel, expected_size=None, expected_sha256=None, max_size=None):
    return open_input(policy, role_name, rel, expected_size, max_size).read_bytes(expected_sha256)


def sha256_input(policy, role_name, rel, expected_size=None, max_size=None):
    item = open_input(policy, role_name, rel, expected_size, max_size)
    size = item.size
    return {"sha256": item.sha256(), "size": size}


def _no_dups(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "json", "duplicate key %r" % key)
        out[key] = value
    return out


def _no_constant(name):
    refuse("json", "non-finite constant %s" % name)


def loads_strict(data, label="json"):
    """Strict UTF-8 JSON: duplicate keys and NaN/Infinity refuse."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        refuse("json", "%s: not UTF-8" % label)
    try:
        return json.loads(text, object_pairs_hook=_no_dups, parse_constant=_no_constant)
    except ValueError as error:
        refuse("json", "%s: %s" % (label, error))


def read_json(policy, role_name, rel, max_size, expected_sha256=None):
    """Size-capped (min of role cap and max_size) strict JSON read from the gated fd."""
    data = read_bytes(policy, role_name, rel, None, expected_sha256, max_size)
    return loads_strict(data, rel)


def copy_input(policy, role_name, rel, writer, dst_rel, expected_sha256=None, expected_size=None, mode=0o444):
    return open_input(policy, role_name, rel, expected_size).copy_to(writer, dst_rel, expected_sha256, mode)


# ---------------------------------------------------------------------------------------------------------------------
# Exemptions (item 5)
# ---------------------------------------------------------------------------------------------------------------------
def hash_e4(policy, role_name, rel):
    """E2/E4: exact path + SHA or refuse. Returns {path, sha256, size}; the bytes never reach the caller."""
    item = _open_gated(policy, role_name, rel, None, None, e4=True)
    size = item.size
    digest = item.sha256()
    require(digest == E4_COMPLETE_JSON[rel], "exemption", "E4 SHA mismatch for %s" % rel)
    return {"path": rel, "sha256": digest, "size": size}


def copy_e4(policy, role_name, rel, writer):
    """Carry an E4 file to the same relative path in a Writer (an E4 write role) without returning bytes: hash pass
    (must equal the pin), then copy pass (the copy must equal the pin too; a mismatch refuses, the partial stays)."""
    hash_e4(policy, role_name, rel)
    item = _open_gated(policy, role_name, rel, None, None, e4=True)
    try:
        out = writer.open_excl(rel, e4=True)
    except BaseException:
        item.close()
        raise
    try:
        item._consume(out.write)
    except BaseException:
        out.abort()
        raise
    result = out.finish(0o444)
    require(result["sha256"] == E4_COMPLETE_JSON[rel], "exemption", "E4 copy SHA mismatch for %s" % rel)
    return {"path": rel, "sha256": result["sha256"], "size": result["size"]}


def check_e1(policy, role_name):
    """E1: the root-level symlink visualize_battle.py must have link text exactly examples/visualize_battle.py
    (readlinkat; never followed). The target is gated as a normal input (opened and closed unread). Returns
    {alias, link, target, target_size}. Read the target with open_input(policy, role, E1_LINK_TEXT)."""
    role, _ = _gate(policy, role_name, E1_ALIAS, policy.role(role_name).access)
    require("E1" in role.exemptions, "exemption", "role %s has no E1 exemption" % role.name)
    root = open_root(role.root)
    try:
        try:
            st = os.stat(E1_ALIAS, dir_fd=root, follow_symlinks=False)
        except OSError as error:
            refuse(_classify(error), "E1 %s: %s" % (E1_ALIAS, os.strerror(error.errno)))
        require(stat.S_ISLNK(st.st_mode), "exemption", "E1 %s is not a symlink" % E1_ALIAS)
        text = os.readlink(E1_ALIAS, dir_fd=root)
    finally:
        os.close(root)
    require(text == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (text, E1_LINK_TEXT))
    if role.access == "read":
        target = open_input(policy, role_name, E1_LINK_TEXT)
        size = target.size
        target.close()
    else:
        size = None
    return {"alias": E1_ALIAS, "link": text, "target": E1_LINK_TEXT, "target_size": size}


# ---------------------------------------------------------------------------------------------------------------------
# Directory checks and the confined recursive walk
# ---------------------------------------------------------------------------------------------------------------------
def check_dir(policy, role_name, rel=None):
    """The role root (rel None) or a name-gated subdirectory must be a canonical directory; returns its identity."""
    role = policy.role(role_name)
    parts = []
    if rel is not None:
        parts = check_rel(rel)
        name_gate(role.root + "/" + rel, policy.host, role.grants)
    fd = open_root(role.root)
    try:
        sub = open_dirs(fd, parts, "%s:%s" % (role.name, rel))
    finally:
        os.close(fd)
    st = os.fstat(sub)
    os.close(sub)
    return {"dev": st.st_dev, "ino": st.st_ino, "mode": st.st_mode}


def check_absent(policy, role_name, rel):
    """The parent must be a canonical directory and the leaf must not exist (not even as a dangling symlink)."""
    role, parts = _gate(policy, role_name, rel, policy.role(role_name).access)
    root = open_root(role.root)
    try:
        parent = open_dirs(root, parts[:-1], "%s:%s" % (role.name, rel))
    finally:
        os.close(root)
    try:
        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return True
    finally:
        os.close(parent)
    refuse("exists", "%s:%s exists" % (role.name, rel))


def walk_tree(policy, role_name, rel_dir=None, max_entries=200000):
    """Confined recursive inventory. Every entry name is gated BEFORE it is lstat'ed or entered; any forbidden name,
    symlink (except the exact E1 alias at the root), special file, hard link, oversize or undeclared file refuses
    the whole walk (no pruning). Returns {files: [{rel,size,dev,ino}], e1: None|{rel,link}, e4: [rel]}. Nothing is
    read; read files with open_input and E4 paths with hash_e4/copy_e4."""
    role = policy.role(role_name)
    require(role.access == "read", "policy", "walk_tree needs a read role")
    base = []
    if rel_dir is not None:
        base = check_rel(rel_dir)
        name_gate(role.root + "/" + rel_dir, policy.host, role.grants)
    files, e4, e1, count = [], [], None, [0]
    root = open_root(role.root)
    try:
        start = open_dirs(root, base, "%s:%s" % (role.name, rel_dir))
    finally:
        os.close(root)
    stack = [(start, base)]
    try:
        while stack:
            fd, prefix = stack.pop()
            try:
                for name in sorted(os.listdir(fd)):
                    count[0] += 1
                    require(count[0] <= max_entries, "size", "walk exceeds %d entries" % max_entries)
                    rel = "/".join(prefix + [name])
                    check_rel(rel)
                    is_e4 = "E4" in role.exemptions and rel in E4_COMPLETE_JSON
                    name_gate(role.root + "/" + rel, policy.host, role.grants, e4_leaf=is_e4)
                    st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISLNK(st.st_mode):
                        require("E1" in role.exemptions and rel == E1_ALIAS, "symlink", "symlink in tree: %s" % rel)
                        link = os.readlink(name, dir_fd=fd)
                        require(link == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (link, E1_LINK_TEXT))
                        e1 = {"rel": rel, "link": link}
                    elif stat.S_ISDIR(st.st_mode):
                        stack.append((open_dirs(fd, [name], "%s:%s" % (role.name, rel)), prefix + [name]))
                    elif stat.S_ISREG(st.st_mode):
                        require(st.st_nlink == 1, "nlink", "hard-linked file in tree: %s" % rel)
                        require(st.st_size <= role.max_size, "size", "oversize file in tree: %s" % rel)
                        require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))
                        if is_e4:
                            e4.append(rel)
                        else:
                            files.append({"rel": rel, "size": st.st_size, "dev": st.st_dev, "ino": st.st_ino})
                    else:
                        refuse("not-regular", "special file in tree: %s" % rel)
            finally:
                os.close(fd)
    finally:
        for fd, _ in stack:
            os.close(fd)
    if e1 is not None:
        require(any(f["rel"] == E1_LINK_TEXT for f in files), "exemption", "E1 target missing from the tree")
    files.sort(key=lambda f: f["rel"])
    return {"files": files, "e1": e1, "e4": sorted(e4)}


# ---------------------------------------------------------------------------------------------------------------------
# Writes (item 7)
# ---------------------------------------------------------------------------------------------------------------------
class NewFile(object):
    """An exclusively created file. write() is size-capped and hashed; finish() fsyncs file and directory."""

    def __init__(self, fd, parent_fd, cap, label):
        self._fd, self._parent, self._cap, self.label = fd, parent_fd, cap, label
        self._size, self._digest = 0, hashlib.sha256()

    def write(self, data):
        require(self._fd is not None, "state", "%s already closed" % self.label)
        require(self._size + len(data) <= self._cap, "size", "%s: write exceeds cap %d" % (self.label, self._cap))
        view = memoryview(data)
        while view:
            view = view[os.write(self._fd, view):]
        self._size += len(data)
        self._digest.update(data)

    def finish(self, mode=0o444):
        require(self._fd is not None, "state", "%s already closed" % self.label)
        os.fsync(self._fd)
        os.fchmod(self._fd, mode)
        os.close(self._fd)
        self._fd = None
        os.fsync(self._parent)
        os.close(self._parent)
        self._parent = None
        return {"sha256": self._digest.hexdigest(), "size": self._size}

    def abort(self):
        """Close without publishing anything else; the partial file stays (never unlinked)."""
        for attr in ("_fd", "_parent"):
            fd = getattr(self, attr)
            if fd is not None:
                setattr(self, attr, None)
                os.close(fd)


class Writer(object):
    """Write-only access below a canonical root of a declared 'write' role. Never truncates or overwrites."""

    def __init__(self, policy, role_name):
        role = policy.role(role_name)
        require(role.access == "write", "policy", "role %s is not a write role" % role.name)
        self.policy, self.role = policy, role
        self._fd = open_root(role.root)

    def _parent(self, rel, e4=False, directory=False):
        require(self._fd is not None, "state", "writer closed")
        if directory:
            parts = check_rel(rel)
            name_gate(self.role.root + "/" + rel, self.policy.host, self.role.grants)
        else:
            _, parts = _gate(self.policy, self.role.name, rel, "write", e4)
        return open_dirs(self._fd, parts[:-1], "%s:%s" % (self.role.name, rel)), parts[-1]

    def mkdir_excl(self, rel, mode=0o755):
        parent, leaf = self._parent(rel, directory=True)
        try:
            try:
                os.mkdir(leaf, mode, dir_fd=parent)
            except FileExistsError:
                refuse("exists", "%s:%s already exists" % (self.role.name, rel))
            os.fsync(parent)
        finally:
            os.close(parent)

    def open_excl(self, rel, e4=False):
        parent, leaf = self._parent(rel, e4=e4)
        try:
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                         dir_fd=parent)
        except FileExistsError:
            os.close(parent)
            refuse("exists", "%s:%s already exists (never overwritten)" % (self.role.name, rel))
        except BaseException:
            os.close(parent)
            raise
        return NewFile(fd, parent, self.role.max_size, "%s:%s" % (self.role.name, rel))

    def create_excl(self, rel, data, mode=0o444):
        require(isinstance(data, (bytes, bytearray)), "policy", "create_excl takes bytes")
        out = self.open_excl(rel)
        try:
            out.write(bytes(data))
        except BaseException:
            out.abort()
            raise
        return out.finish(mode)

    def write_json_once(self, rel, obj, mode=0o444):
        data = (json.dumps(obj, sort_keys=True, indent=1, allow_nan=False) + "\n").encode()
        return self.create_excl(rel, data, mode)

    def publish_excl(self, tmp_rel, final_rel):
        """No-clobber publication of a file this run created (replaces `tmp` + `mv`): tmp must be a regular file with
        st_nlink == 1; linkat(tmp, final) fails if final exists in any form (never replaced); then tmp is unlinked."""
        tparent, tleaf = self._parent(tmp_rel)
        try:
            fparent, fleaf = self._parent(final_rel)
        except BaseException:
            os.close(tparent)
            raise
        try:
            try:
                st = os.stat(tleaf, dir_fd=tparent, follow_symlinks=False)
            except OSError as error:
                refuse(_classify(error), "%s: %s" % (tmp_rel, os.strerror(error.errno)))
            require(stat.S_ISREG(st.st_mode), "not-regular", "%s is not a regular file" % tmp_rel)
            require(st.st_nlink == 1, "nlink", "%s is hard-linked (st_nlink %d)" % (tmp_rel, st.st_nlink))
            try:
                os.link(tleaf, fleaf, src_dir_fd=tparent, dst_dir_fd=fparent, follow_symlinks=False)
            except FileExistsError:
                refuse("exists", "%s:%s already exists (never replaced)" % (self.role.name, final_rel))
            os.unlink(tleaf, dir_fd=tparent)
            os.fsync(fparent)
            os.fsync(tparent)
        finally:
            os.close(tparent)
            os.close(fparent)

    def create_e1_symlink(self):
        """The one symlink this layer ever creates: E1 at the root of an E1 write role."""
        require("E1" in self.role.exemptions, "exemption", "role %s has no E1 exemption" % self.role.name)
        parent, leaf = self._parent(E1_ALIAS)
        try:
            try:
                os.symlink(E1_LINK_TEXT, leaf, dir_fd=parent)
            except FileExistsError:
                refuse("exists", "E1 alias already exists")
            os.fsync(parent)
        finally:
            os.close(parent)

    def close(self):
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def utc_stamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_refusal_receipt(writer, component, refusal, context=None):
    """Write-once refusal receipt <COMPONENT>-REFUSAL-<utc>-<pid>-<hex>.json into a declared refusal role (the role
    must declare a matching pattern). Returns the relative name."""
    require(isinstance(component, str) and _COMPONENT.fullmatch(component) is not None, "policy", "bad component")
    rel = "%s-REFUSAL-%s-%d-%s.json" % (component, utc_stamp(), os.getpid(), secrets.token_hex(4))
    body = {"schema": REFUSAL_SCHEMA, "component": component, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pid": os.getpid(), "code": getattr(refusal, "code", "error"), "reason": str(refusal),
            "context": context}
    writer.write_json_once(rel, body)
    return rel


# ---------------------------------------------------------------------------------------------------------------------
# Subprocess (item 8)
# ---------------------------------------------------------------------------------------------------------------------
LINGER_GRACE = 5.0


class RunResult(object):
    __slots__ = ("argv", "rc", "stdout", "stderr")

    def __init__(self, argv, rc, stdout, stderr):
        self.argv, self.rc, self.stdout, self.stderr = argv, rc, stdout, stderr


def run_checked(argv, timeout, stdout_limit, stderr_limit=1 << 16, env=None, env_allow=(), stdin_bytes=None,
                cwd=None, ok_rcs=(0,)):
    """Run an explicit argv (absolute argv[0], never a shell). The environment is exactly `env` plus the listed
    `env_allow` names copied from os.environ. stdout/stderr are bounded (over-limit kills and refuses); a watchdog
    kills the whole process group at `timeout`. Returns RunResult only if rc is in ok_rcs (default: 0); otherwise
    Refusal('subprocess'), whatever stdout looked like."""
    require(isinstance(argv, (list, tuple)) and argv and all(isinstance(a, str) and "\x00" not in a for a in argv),
            "subprocess", "argv must be a non-empty list of strings")
    require(argv[0].startswith("/") and os.path.normpath(argv[0]) == argv[0], "subprocess",
            "argv[0] must be an absolute normalized path: %r" % argv[0])
    require(isinstance(timeout, (int, float)) and timeout > 0, "subprocess", "timeout required")
    require(type(stdout_limit) is int and stdout_limit > 0 and type(stderr_limit) is int and stderr_limit > 0,
            "subprocess", "output limits required")
    require(cwd is None or (isinstance(cwd, str) and cwd.startswith("/")), "subprocess", "cwd must be absolute")
    require(all(isinstance(r, int) for r in ok_rcs) and ok_rcs, "subprocess", "ok_rcs must be ints")
    full_env = {}
    for key in env_allow:
        if key in os.environ:
            full_env[key] = os.environ[key]
    for key, value in (env or {}).items():
        require(isinstance(key, str) and isinstance(value, str), "subprocess", "env must map str to str")
        full_env[key] = value
    try:
        proc = subprocess.Popen(list(argv), stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full_env, cwd=cwd,
                                start_new_session=True, close_fds=True, shell=False)
    except OSError as error:
        refuse("subprocess", "cannot start %s: %s" % (argv[0], error))
    state = {"out": b"", "err": b"", "over": None, "timed_out": False, "stdin_error": None}

    def kill():
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def drain(stream, key, limit):
        chunks, total = [], 0
        while True:
            data = stream.read(65536) if not hasattr(stream, "read1") else stream.read1(65536)
            if not data:
                break
            total += len(data)
            if total > limit:
                if state["over"] is None:
                    state["over"] = key
                    kill()
                continue
            chunks.append(data)
        state[key] = b"".join(chunks)

    def feed():
        try:
            proc.stdin.write(stdin_bytes)
        except (BrokenPipeError, OSError) as error:
            state["stdin_error"] = error
        finally:
            try:
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

    def expire():
        state["timed_out"] = True
        kill()

    threads = [threading.Thread(target=drain, args=(proc.stdout, "out", stdout_limit)),
               threading.Thread(target=drain, args=(proc.stderr, "err", stderr_limit))]
    if stdin_bytes is not None:
        threads.append(threading.Thread(target=feed))
    for t in threads:
        t.daemon = True
        t.start()
    watchdog = threading.Timer(timeout, expire)
    watchdog.daemon = True
    watchdog.start()
    try:
        proc.wait()
        for t in threads:
            t.join(LINGER_GRACE)                         # output must close soon after the direct child exits
        lingering = any(t.is_alive() for t in threads)
        if lingering:
            kill()
            for t in threads:
                t.join(5)
    finally:
        watchdog.cancel()
    tail = state["err"][-400:].decode("utf-8", "replace")
    require(not state["timed_out"], "subprocess", "%s timed out after %ss: %s" % (argv[0], timeout, tail))
    require(state["over"] is None, "subprocess", "%s: %s exceeded its bound" % (argv[0], state["over"]))
    require(not lingering, "subprocess", "%s: a descendant kept the output pipes open" % argv[0])
    require(proc.returncode in ok_rcs, "subprocess", "%s exited %s (stdout discarded): %s"
            % (argv[0], proc.returncode, tail))
    require(state["stdin_error"] is None, "subprocess", "%s: stdin feed failed: %s" % (argv[0], state["stdin_error"]))
    return RunResult(tuple(argv), proc.returncode, state["out"], state["err"])


_HOSTNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\n")


def hostname_checked(binary="/usr/bin/hostname", expected=None, timeout=10):
    """rc 0 and exactly one hostname line, else Refusal. `expected` (short name) must match if given."""
    result = run_checked([binary], timeout, 4096, env={"LC_ALL": "C"})
    text = result.stdout.decode("ascii", "replace")
    require(_HOSTNAME.fullmatch(text) is not None, "subprocess", "hostname output malformed: %r" % text[:80])
    name = text.strip()
    require(expected is None or name.split(".")[0] == expected, "subprocess",
            "hostname %s is not %s" % (name, expected))
    return name


PS_FIELDS = ("pid", "ppid", "pgid", "sid", "uid")
_PS_FIELD_RULES = {"pid": r"[0-9]+", "ppid": r"[0-9]+", "pgid": r"[0-9]+", "sid": r"[0-9]+", "uid": r"[0-9]+",
                   "ni": r"-|-?[0-9]+", "cls": r"[A-Z?#-]{1,4}"}


def ps_checked(binary="/usr/bin/ps", timeout=20, stdout_limit=8 << 20, fields=PS_FIELDS):
    """Full process table (`ps -e -ww -o <fields>=,args=`; fields from pid ppid pgid sid uid ni cls, pid and ppid
    required). rc must be 0; every line must parse; the table must contain this process with its real parent
    (completeness check). Returns a list of dicts (integers for the id fields, strings for ni/cls/args)."""
    fields = tuple(fields)
    require(fields[:2] == ("pid", "ppid") and len(set(fields)) == len(fields)
            and all(f in _PS_FIELD_RULES for f in fields), "subprocess", "bad ps fields %r" % (fields,))
    spec = ",".join(f + "=" for f in fields) + ",args="
    result = run_checked([binary, "-e", "-ww", "-o", spec], timeout, stdout_limit, env={"LC_ALL": "C"})
    rows, n = [], len(fields)
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        parts = line.split(None, n)
        require(len(parts) >= n and all(re.fullmatch(_PS_FIELD_RULES[f], v) for f, v in zip(fields, parts)),
                "subprocess", "ps line malformed: %r" % line[:120])
        row = {f: (v if f in ("ni", "cls") else int(v)) for f, v in zip(fields, parts)}
        row["args"] = parts[n] if len(parts) > n else ""
        rows.append(row)
    me = [r for r in rows if r["pid"] == os.getpid()]
    require(len(me) == 1 and me[0]["ppid"] == os.getppid(), "subprocess", "ps table incomplete (own process missing)")
    return rows


GIT_ENV = {"LC_ALL": "C", "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_LITERAL_PATHSPECS": "1"}


def git_checked(repo, args, git_binary="/usr/bin/git", timeout=120, stdout_limit=64 << 20, stdin_bytes=None):
    """git -C <canonical repo> <args>; rc must be 0."""
    check_abs(repo)
    require(os.path.realpath(repo) == repo, "root", "repository %s is not canonical" % repo)
    require(all(isinstance(a, str) for a in args), "subprocess", "git args must be strings")
    return run_checked([git_binary, "--no-optional-locks", "-C", repo] + list(args), timeout, stdout_limit,
                       env=GIT_ENV, stdin_bytes=stdin_bytes)


_LS_TREE = re.compile(r"([0-7]{6}) (blob|tree|commit) ([0-9a-f]{40}|[0-9a-f]{64}) +(-|[0-9]+)\t(.+)", re.S)


def git_ls_tree(repo, commit, git_binary="/usr/bin/git", timeout=300, stdout_limit=256 << 20):
    """`git ls-tree -r -l -z --full-tree <commit>` parsed strictly into [{mode,type,oid,size,path}]. Metadata only."""
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is not None,
            "subprocess", "commit must be a full object id")
    raw = git_checked(repo, ["ls-tree", "-r", "-l", "-z", "--full-tree", commit], git_binary, timeout,
                      stdout_limit).stdout
    require(raw == b"" or raw.endswith(b"\x00"), "subprocess", "ls-tree output not NUL-terminated")
    entries = []
    for record in raw.split(b"\x00")[:-1]:
        try:
            text = record.decode("utf-8")
        except UnicodeDecodeError:
            refuse("path", "non-UTF-8 tracked path")
        match = _LS_TREE.fullmatch(text)
        require(match is not None, "subprocess", "ls-tree record malformed: %r" % text[:120])
        mode, kind, oid, size, path = match.groups()
        entries.append({"mode": mode, "type": kind, "oid": oid, "size": None if size == "-" else int(size),
                        "path": path})
    return entries


def git_show_file(policy, role_name, repo, commit, rel, max_size=None, expected_sha256=None,
                  git_binary="/usr/bin/git", timeout=120):
    """`git show <commit>:<rel>` through the gate: the role root must BE the repository; names and allowlist are
    checked first (no git call for a forbidden name); the tree entry must be exactly one regular blob within the
    cap (a tracked symlink or E4 receipt is refused); the bytes must hash to the object id (and expected SHA)."""
    role = policy.role(role_name)
    require(role.root == repo, "root", "role %s is not rooted at the repository %s" % (role.name, repo))
    _gate(policy, role_name, rel, role.access)
    cap = role.max_size if max_size is None else min(role.max_size, max_size)
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is not None,
            "subprocess", "commit must be a full object id")
    raw = git_checked(repo, ["ls-tree", "-l", "-z", "--full-tree", commit, "--", rel], git_binary, timeout,
                      1 << 16).stdout
    records = [r for r in raw.split(b"\x00") if r]
    require(records, "missing", "%s is not tracked at %s" % (rel, commit[:12]))
    match = _LS_TREE.fullmatch(records[0].decode("utf-8", "replace"))
    require(len(records) == 1 and match is not None and match.group(5) == rel, "subprocess",
            "ls-tree did not return exactly %s" % rel)
    mode, kind, oid, size = match.group(1), match.group(2), match.group(3), match.group(4)
    require(kind == "blob" and mode != "120000", "symlink" if mode == "120000" else "not-regular",
            "tracked %s is not a regular blob (mode %s)" % (rel, mode))
    require(mode in ("100644", "100755"), "not-regular", "tracked %s has mode %s" % (rel, mode))
    require(int(size) <= cap, "size", "tracked %s is %s bytes (cap %d)" % (rel, size, cap))
    data = _git_blob(repo, {"oid": oid, "size": int(size), "path": rel}, git_binary, timeout)
    require(expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256, "sha",
            "tracked %s SHA-256 mismatch" % rel)
    return data


def gate_git_tree(policy, role_name, entries):
    """Pure gate over tree metadata BEFORE any blob is read. Refuses the whole tree on any forbidden name, any
    complete.json other than the exact E4 paths, any symlink other than the exact E1 entry, gitlinks, unknown modes,
    oversize blobs and undeclared paths. Returns a plan {files, e1, e4} of entries."""
    role = policy.role(role_name)
    files, e4, e1, seen = [], [], None, set()
    for entry in entries:
        path, mode = entry["path"], entry["mode"]
        require(path not in seen, "path", "duplicate tree path %s" % path)
        seen.add(path)
        is_e4 = "E4" in role.exemptions and path in E4_COMPLETE_JSON
        _gate(policy, role_name, path, role.access, e4=is_e4)
        require(entry["type"] == "blob", "not-regular", "tree entry %s is a %s" % (path, entry["type"]))
        if mode == "120000":
            require("E1" in role.exemptions and path == E1_ALIAS, "symlink", "tracked symlink %s refused" % path)
            e1 = entry
            continue
        require(mode in ("100644", "100755"), "not-regular", "tree entry %s has mode %s" % (path, mode))
        require(entry["size"] is not None and entry["size"] <= role.max_size, "size", "blob %s too large" % path)
        (e4 if is_e4 else files).append(entry)
    if e1 is not None:
        require(any(f["path"] == E1_LINK_TEXT for f in files), "exemption", "E1 target not in the tree")
    return {"files": files, "e1": e1, "e4": e4, "role": role.name}


def _git_blob(repo, entry, git_binary, timeout):
    data = git_checked(repo, ["cat-file", "blob", entry["oid"]], git_binary, timeout,
                       max(1, entry["size"] if entry["size"] is not None else 4096)).stdout
    require(entry["size"] is None or len(data) == entry["size"], "size", "blob %s size changed" % entry["path"])
    algo = hashlib.sha1 if len(entry["oid"]) == 40 else hashlib.sha256
    require(algo(b"blob %d\x00" % len(data) + data).hexdigest() == entry["oid"], "sha",
            "blob %s does not hash to its object id" % entry["path"])
    return data


def git_blob(repo, plan, entry, git_binary="/usr/bin/git", timeout=120):
    """Bytes of one planned ordinary file blob (never an E4 entry). The E1 link text is checked here as well."""
    if plan["e1"] is not None and entry is plan["e1"]:
        data = _git_blob(repo, entry, git_binary, timeout)
        require(data == E1_LINK_TEXT.encode(), "exemption", "E1 tracked link text differs")
        return data
    require(any(entry is f for f in plan["files"]), "policy", "entry %s is not a planned file" % entry.get("path"))
    return _git_blob(repo, entry, git_binary, timeout)


def git_hash_e4(repo, plan, entry, git_binary="/usr/bin/git", timeout=120):
    """E4 through git: exact path + SHA-256 or refuse; returns {path, sha256, size}, never the bytes."""
    require(any(entry is f for f in plan["e4"]), "exemption", "entry is not a planned E4 entry")
    data = _git_blob(repo, entry, git_binary, timeout)
    digest = hashlib.sha256(data).hexdigest()
    require(digest == E4_COMPLETE_JSON[entry["path"]], "exemption", "E4 SHA mismatch for %s" % entry["path"])
    return {"path": entry["path"], "sha256": digest, "size": len(data)}


def git_export(repo, plan, writer, e1_mode, git_binary="/usr/bin/git", timeout=120):
    """Export a gated plan into a Writer (same relative paths; directories created exclusively; E4 files carried
    after their pin check). E1 is either recreated as the one exact symlink (e1_mode 'symlink') or written as a
    regular copy of its verified target bytes (e1_mode 'copy', the T1 A5 dereference precedent). The choice is
    explicit because S4 r3b and S9 r1 currently disagree. Returns the inventory {path: {sha256,size}}."""
    require(e1_mode in ("symlink", "copy"), "policy", "e1_mode must be 'symlink' or 'copy'")
    made, inventory = set(), {}

    def ensure_dirs(path):
        parts = path.split("/")[:-1]
        for i in range(len(parts)):
            rel = "/".join(parts[:i + 1])
            if rel not in made:
                writer.mkdir_excl(rel)
                made.add(rel)

    for entry in plan["files"]:
        data = git_blob(repo, plan, entry, git_binary, timeout)
        ensure_dirs(entry["path"])
        result = writer.create_excl(entry["path"], data, 0o555 if entry["mode"] == "100755" else 0o444)
        inventory[entry["path"]] = result
    for entry in plan["e4"]:
        git_hash_e4(repo, plan, entry, git_binary, timeout)
        data = _git_blob(repo, entry, git_binary, timeout)
        require(hashlib.sha256(data).hexdigest() == E4_COMPLETE_JSON[entry["path"]], "exemption", "E4 changed")
        ensure_dirs(entry["path"])
        out = writer.open_excl(entry["path"], e4=True)
        out.write(data)
        inventory[entry["path"]] = out.finish(0o444)
        del data
    if plan["e1"] is not None:
        git_blob(repo, plan, plan["e1"], git_binary, timeout)
        if e1_mode == "symlink":
            writer.create_e1_symlink()
            inventory[E1_ALIAS] = {"symlink": E1_LINK_TEXT}
        else:
            target = [f for f in plan["files"] if f["path"] == E1_LINK_TEXT]
            require(len(target) == 1, "exemption", "E1 target not in the plan")
            result = writer.create_excl(E1_ALIAS, git_blob(repo, plan, target[0], git_binary, timeout), 0o444)
            result["copy_of"] = E1_LINK_TEXT
            inventory[E1_ALIAS] = result
    return inventory


# ---------------------------------------------------------------------------------------------------------------------
# Remote reader (item 9)
# ---------------------------------------------------------------------------------------------------------------------
_REMOTE_MAIN = r'''
import base64, binascii, json, sys

REQUEST_SCHEMA = "clasher.k4s.safe-input.remote-request.v1"
RESPONSE_SCHEMA = "clasher.k4s.safe-input.remote-response.v1"
MAX_ITEMS = 256
MAX_CONTENT = 8 << 20
ITEM_KEYS = {"file": ("content", "e4", "expected_size", "grants", "kind", "max_size", "rel", "root"),
             "dir": ("grants", "kind", "rel", "root"),
             "absent": ("grants", "kind", "rel", "root")}


def _emit(obj, rc):
    data = (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
    view = memoryview(data)
    while view:
        view = view[os.write(1, view):]
    os._exit(rc)


def _no_dups(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            refuse("request", "duplicate key")
        out[key] = value
    return out


def _no_constant(name):
    refuse("request", "non-finite constant")


def _int(value):
    return type(value) is int and value >= 0


def _validate(req):
    if not isinstance(req, dict) or sorted(req) != ["host", "items", "max_content", "schema"]:
        refuse("request", "bad request keys")
    if req["schema"] != REQUEST_SCHEMA or req["host"] not in HOSTS:
        refuse("request", "bad schema or host")
    if not _int(req["max_content"]) or req["max_content"] > MAX_CONTENT:
        refuse("request", "bad max_content")
    items = req["items"]
    if not isinstance(items, list) or not 0 < len(items) <= MAX_ITEMS:
        refuse("request", "bad item list")
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in ITEM_KEYS:
            refuse("request", "bad item")
        if tuple(sorted(item)) != ITEM_KEYS[item["kind"]]:
            refuse("request", "bad item keys")
        if not isinstance(item["grants"], list) or not set(item["grants"]) <= set(GRANTS):
            refuse("request", "bad grants")
        check_abs(item["root"])
        if item["kind"] == "dir" and item["rel"] == "":
            continue
        check_rel(item["rel"])
        if item["kind"] == "file":
            if not _int(item["max_size"]) or item["max_size"] == 0:
                refuse("request", "bad max_size")
            if item["expected_size"] is not None and not _int(item["expected_size"]):
                refuse("request", "bad expected_size")
            if item["content"] not in (True, False) or item["e4"] not in (True, False):
                refuse("request", "bad flags")
            if item["e4"] and (item["content"] or item["rel"] not in E4_COMPLETE_JSON):
                refuse("exemption", "E4 is hash-only at an exact path")
    return items


def main():
    status = {"request_sha256": None, "host": None, "where": None}
    try:
        if len(sys.argv) != 2:
            refuse("request", "expected one hex request argument")
        try:
            raw = binascii.unhexlify(sys.argv[1].encode("ascii"))
        except (binascii.Error, UnicodeEncodeError, ValueError):
            refuse("request", "request is not hex")
        status["request_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            req = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dups, parse_constant=_no_constant)
        except ValueError:
            refuse("request", "request is not JSON")
        items = _validate(req)
        host = req["host"]
        # 1. every name gate of every item, before any syscall on any of them
        for item in items:
            status["where"] = [item["root"], item["rel"]]
            full = item["root"] + ("/" + item["rel"] if item["rel"] else "")
            name_gate(item["root"], host, item["grants"])
            name_gate(full, host, item["grants"], e4_leaf=item["kind"] == "file" and item["e4"])
        # 2. the request is for this host
        status["where"] = None
        node = os.uname().nodename.split(".")[0]
        status["host"] = node
        if node != host:
            refuse("host", "request for %s ran on %s" % (host, node))
        # 3. gate pass: every item opened and checked before any byte of any file is read
        gated = []
        content_total = 0
        for item in items:
            status["where"] = [item["root"], item["rel"]]
            root_fd = open_root(item["root"])
            try:
                parts = item["rel"].split("/") if item["rel"] else []
                if item["kind"] == "dir":
                    fd = open_dirs(root_fd, parts, item["root"])
                    st = os.fstat(fd)
                    os.close(fd)
                    gated.append((item, None, {"dev": st.st_dev, "ino": st.st_ino, "mode": st.st_mode}))
                    continue
                parent = open_dirs(root_fd, parts[:-1], item["root"])
            finally:
                os.close(root_fd)
            try:
                if item["kind"] == "absent":
                    try:
                        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        gated.append((item, None, {}))
                        continue
                    refuse("exists", "path exists")
                fd, st = open_leaf(parent, parts[-1], item["max_size"], item["expected_size"], item["rel"])
            finally:
                os.close(parent)
            if item["content"]:
                content_total += st.st_size
                if content_total > req["max_content"]:
                    os.close(fd)
                    refuse("size", "content total exceeds max_content")
            gated.append((item, fd, {"size": st.st_size, "nlink": st.st_nlink, "mode": st.st_mode,
                                     "dev": st.st_dev, "ino": st.st_ino}))
        # 4. read pass: hash (and optionally return) exactly the inspected bytes from the gated descriptors
        out = []
        for item, fd, meta in gated:
            status["where"] = [item["root"], item["rel"]]
            record = {"kind": item["kind"], "root": item["root"], "rel": item["rel"]}
            record.update(meta)
            if fd is not None:
                digest, chunks = hashlib.sha256(), []
                def sink(chunk, digest=digest, chunks=chunks, keep=item["content"]):
                    digest.update(chunk)
                    if keep:
                        chunks.append(chunk)
                try:
                    read_exact(fd, meta["size"], sink, item["rel"])
                finally:
                    os.close(fd)
                record["sha256"] = digest.hexdigest()
                if item["e4"] and record["sha256"] != E4_COMPLETE_JSON[item["rel"]]:
                    refuse("exemption", "E4 SHA mismatch")
                record["content_b64"] = base64.b64encode(b"".join(chunks)).decode() if item["content"] else None
            out.append(record)
        _emit({"schema": RESPONSE_SCHEMA, "status": "ok", "host": status["host"],
               "request_sha256": status["request_sha256"], "items": out}, 0)
    except Refusal as error:
        _emit({"schema": RESPONSE_SCHEMA, "status": "refused", "host": status["host"],
               "request_sha256": status["request_sha256"], "code": error.code, "reason": error.reason,
               "where": status["where"]}, 3)
    except Exception as error:
        _emit({"schema": RESPONSE_SCHEMA, "status": "error", "host": status["host"],
               "request_sha256": status["request_sha256"], "code": "error",
               "reason": type(error).__name__, "where": status["where"]}, 4)


main()
'''


def remote_program_source():
    """The exact program shipped over ssh stdin to `/usr/bin/python3 -I -S -`: _CORE + the remote main."""
    return "# k4s safe_input remote reader r1 (stdlib only, python3.8+, read-only)\n" + _CORE + _REMOTE_MAIN


def remote_program_sha256():
    return hashlib.sha256(remote_program_source().encode()).hexdigest()


def build_remote_request(policy, items, max_content=0):
    """items: [{role, rel, kind ('file'|'dir'|'absent'), content?, expected_size?, e4?}]. Every name and allowlist
    check runs LOCALLY first (a forbidden path is never sent). Returns the canonical request bytes."""
    require(isinstance(policy, Policy) and policy.remote, "policy", "a remote Policy is required")
    require(isinstance(items, list) and 0 < len(items) <= REMOTE_MAX_ITEMS, "policy", "bad item list")
    require(type(max_content) is int and 0 <= max_content <= REMOTE_MAX_CONTENT, "policy", "bad max_content")
    out = []
    for item in items:
        require(isinstance(item, dict), "policy", "items must be dicts")
        kind = item.get("kind")
        role = policy.role(item.get("role"))
        rel = item.get("rel")
        grants = sorted(role.grants)
        if kind == "dir":
            if rel:
                check_rel(rel)
                name_gate(role.root + "/" + rel, policy.host, role.grants)
            out.append({"kind": "dir", "root": role.root, "rel": rel or "", "grants": grants})
        elif kind == "absent":
            _gate(policy, role.name, rel, role.access)
            out.append({"kind": "absent", "root": role.root, "rel": rel, "grants": grants})
        elif kind == "file":
            e4 = bool(item.get("e4", False))
            _gate(policy, role.name, rel, "read", e4)
            content = bool(item.get("content", False))
            require(not (e4 and content), "exemption", "E4 is hash-only")
            expected = item.get("expected_size")
            require(expected is None or type(expected) is int, "policy", "bad expected_size")
            out.append({"kind": "file", "root": role.root, "rel": rel, "grants": grants, "max_size": role.max_size,
                        "expected_size": expected, "content": content, "e4": e4})
        else:
            refuse("policy", "unknown remote item kind %r" % (kind,))
    body = {"schema": REMOTE_REQUEST_SCHEMA, "host": policy.host, "items": out, "max_content": max_content}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def remote_ssh_argv(host, request_bytes, ssh_binary=SSH_BINARY):
    """ssh argv. The remote shell receives only [A-Za-z0-9/-] words: nice -n 19 python3 -I -S - <hex request>."""
    require(host in HOSTS, "policy", "unknown host %r" % (host,))
    return [ssh_binary] + list(SSH_OPTIONS) + ["--", host, "nice", "-n", "19", REMOTE_PYTHON, "-I", "-S", "-",
                                               binascii.hexlify(request_bytes).decode()]


_RESPONSE_OK = ("host", "items", "request_sha256", "schema", "status")
_RESPONSE_REFUSED = ("code", "host", "reason", "request_sha256", "schema", "status", "where")


def parse_remote_response(request_bytes, rc, stdout):
    """Strict validation of the remote reply against the exact request. rc 0 must be status ok; rc 3 must be a
    well-formed refusal (raised as Refusal('remote-refused')); anything else refuses. Returns the item records;
    'content' (bytes) is present only for content requests and only after its size/SHA check."""
    request = loads_strict(request_bytes, "remote request")
    require(type(rc) is int, "remote", "rc must be an int")
    require(rc in (0, 3), "remote", "remote reader exited %s" % rc)
    require(isinstance(stdout, bytes) and stdout.endswith(b"\n") and stdout.count(b"\n") == 1, "remote",
            "remote output is not exactly one line")
    reply = loads_strict(stdout, "remote response")
    require(isinstance(reply, dict) and reply.get("schema") == REMOTE_RESPONSE_SCHEMA, "remote", "bad schema")
    require(reply.get("request_sha256") == hashlib.sha256(request_bytes).hexdigest(), "remote", "request SHA differs")
    if rc == 3:
        require(tuple(sorted(reply)) == _RESPONSE_REFUSED and reply["status"] == "refused", "remote",
                "rc 3 without a well-formed refusal")
        refuse("remote-refused", "%s: %s at %s (host %s)" % (reply["code"], reply["reason"], reply["where"],
                                                               reply["host"]))
    require(tuple(sorted(reply)) == _RESPONSE_OK and reply["status"] == "ok", "remote", "rc 0 without status ok")
    require(reply["host"] == request["host"], "remote", "reply host %r is not %r" % (reply["host"], request["host"]))
    records = reply["items"]
    require(isinstance(records, list) and len(records) == len(request["items"]), "remote", "item count differs")
    out = []
    for asked, got in zip(request["items"], records):
        require(isinstance(got, dict), "remote", "bad item record")
        for key in ("kind", "root", "rel"):
            require(got.get(key) == asked[key], "remote", "item %s differs" % key)
        if asked["kind"] == "absent":
            require(sorted(got) == ["kind", "rel", "root"], "remote", "bad absent record")
        elif asked["kind"] == "dir":
            require(sorted(got) == ["dev", "ino", "kind", "mode", "rel", "root"], "remote", "bad dir record")
            require(all(type(got[k]) is int and got[k] >= 0 for k in ("dev", "ino", "mode")), "remote",
                    "bad dir metadata")
            require(stat.S_ISDIR(got["mode"]), "not-dir", "remote %s is not a directory" % asked["rel"])
        else:
            require(sorted(got) == ["content_b64", "dev", "ino", "kind", "mode", "nlink", "rel", "root", "sha256",
                                    "size"], "remote", "bad file record")
            require(all(type(got[k]) is int and got[k] >= 0 for k in ("dev", "ino", "mode", "nlink", "size")),
                    "remote", "bad file metadata")
            require(stat.S_ISREG(got["mode"]), "not-regular", "remote %s is not a regular file" % asked["rel"])
            require(got["nlink"] == 1, "nlink", "remote %s has st_nlink %d" % (asked["rel"], got["nlink"]))
            require(got["size"] <= asked["max_size"], "size", "remote %s exceeds its cap" % asked["rel"])
            require(asked["expected_size"] is None or got["size"] == asked["expected_size"], "size",
                    "remote %s size differs" % asked["rel"])
            require(isinstance(got["sha256"], str) and SHA256_HEX.fullmatch(got["sha256"]) is not None, "remote",
                    "bad sha256")
            if asked["e4"]:
                require(got["sha256"] == E4_COMPLETE_JSON[asked["rel"]], "exemption", "E4 SHA mismatch")
            got = dict(got)
            b64 = got.pop("content_b64")
            if asked["content"]:
                require(isinstance(b64, str), "remote", "content missing")
                try:
                    data = binascii.a2b_base64(b64.encode("ascii"))
                except (binascii.Error, UnicodeEncodeError):
                    refuse("remote", "content is not base64")
                require(binascii.b2a_base64(data, newline=False).decode() == b64, "remote", "non-canonical base64")
                require(len(data) == got["size"] and hashlib.sha256(data).hexdigest() == got["sha256"], "remote",
                        "content does not match its size/SHA")
                got["content"] = data
            else:
                require(b64 is None, "remote", "unrequested content returned")
        out.append(got)
    return out


def main(argv=None):
    """CLI for host shell wrappers (one exact-name write role per call; exit 0 ok, 3 refused, 2 usage):
      create-excl  --host H --root R --rel REL --max-size N [--grant G]... [--mode 0444]   (bytes from stdin)
      mkdir-excl   --host H --root R --rel REL [--grant G]...
      publish-excl --host H --root R --rel TMP --final REL [--grant G]...
      remote-program-sha256"""
    import argparse
    ap = argparse.ArgumentParser(prog="safe_input", allow_abbrev=False)
    sub = ap.add_subparsers(dest="command")
    for name in ("create-excl", "mkdir-excl", "publish-excl"):
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--host", required=True)
        p.add_argument("--root", required=True)
        p.add_argument("--rel", required=True)
        p.add_argument("--grant", action="append", default=[])
        if name == "create-excl":
            p.add_argument("--max-size", type=int, required=True)
            p.add_argument("--mode", default="0444")
        if name == "publish-excl":
            p.add_argument("--final", required=True)
    sub.add_parser("remote-program-sha256", allow_abbrev=False)
    a = ap.parse_args(argv)
    if a.command is None:
        ap.print_usage(sys.stderr)
        return 2
    if a.command == "remote-program-sha256":
        print(remote_program_sha256())
        return 0
    try:
        names = (a.rel, a.final) if a.command == "publish-excl" else (a.rel,)
        size = a.max_size if a.command == "create-excl" else 1
        policy = Policy(a.host, [Role("cli", a.root, "write", size, exact=names, grants=a.grant)])
        with Writer(policy, "cli") as writer:
            if a.command == "mkdir-excl":
                writer.mkdir_excl(a.rel)
            elif a.command == "publish-excl":
                writer.publish_excl(a.rel, a.final)
            else:
                require(re.fullmatch(r"0[0-7]{3}", a.mode) is not None, "policy", "--mode must be octal like 0444")
                out = writer.open_excl(a.rel)
                try:
                    stream = sys.stdin.buffer
                    while True:
                        chunk = stream.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                except BaseException:
                    out.abort()
                    raise
                result = out.finish(int(a.mode, 8))
                print(json.dumps(result, sort_keys=True))
    except Refusal as error:
        sys.stderr.write("REFUSE %s\n" % error)
        return 3
    return 0


def remote_check(policy, items, max_content=0, ssh_binary=SSH_BINARY, timeout=300):
    """One ssh login: ship remote_program_source() on stdin, the request as one hex word; parse strictly."""
    request = build_remote_request(policy, items, max_content)
    limit = 4096 + 1024 * len(items) + 2 * max_content
    result = run_checked(remote_ssh_argv(policy.host, request, ssh_binary), timeout, limit,
                         stdin_bytes=remote_program_source().encode(), ok_rcs=(0, 3), env={"LC_ALL": "C"})
    return parse_remote_response(request, result.rc, result.stdout)


if __name__ == "__main__":
    sys.exit(main())
