"""Shared glue for the S1b / S3 / S9 / S10 r2 candidates (stdlib only; Python 3.8+). CANDIDATE: Sol review.

Every read, hash, stat, open, stream, write, subprocess and git call in these components goes through the shared
`safe_input` layer (rulings P2-1, P2-4, D1-D4). This module only:

* loads the vendored, byte-identical safe_input.py from this directory: the file is opened O_NOFOLLOW, must be a
  regular single-link file, its SHA-256 is checked with stdlib hashlib against SAFE_INPUT_SHA256 BEFORE anything of
  it runs, and exactly the verified bytes are executed (never re-read from disk). Then the constants fingerprint and
  the SHA-256 of the two shipped remote programs (reader, receive) must equal the pins below;
* checks that a new local output path is absolute, normalized and under a permitted 05 root (pure string check;
  creation itself goes through si.Writer: canonical parent, exclusive mkdir/create, never a followed link);
* publishes a finished `<x>.partial` directory as `<x>` with renameat2(RENAME_NOREPLACE) relative to the canonical
  parent fd (an existing `<x>` of any kind refuses; nothing is ever replaced);
* gives frozen-code subprocesses the P2-4 environment (GIT_FIXED_ENV + a fresh empty HOME; nothing inherited).
"""
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_INPUT_PATH = os.path.join(HERE, "safe_input.py")
# The pin of record: safe-input-r3 (= r2 + ruling E5; its SHA256SUMS verified, PROGRESS-r3 DONE). The fingerprint
# and the reader SHA equal r3 README §8. The receive program SHA is the value the pinned bytes produce on 3.8 and
# 3.12 (39a92e9d...); r3 README §8 prints 979b37a1..., which these bytes do not produce (disclosed in README.md).
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
REMOTE_PROGRAM_SHA256 = "2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152"
RECEIVE_PROGRAM_SHA256 = "39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4"
SAFE_INPUT_RELEASE = "safe-input-r3"


def _load_safe_input():
    existing = sys.modules.get("safe_input")
    if existing is not None:
        if getattr(existing, "_k4s_verified_sha256", None) != SAFE_INPUT_SHA256:
            raise SystemExit("a different safe_input module is already loaded; refusing to mix layers")
        return existing
    try:
        fd = os.open(SAFE_INPUT_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise SystemExit("cannot open the vendored safe_input.py without following links: %s" % error.strerror)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= (4 << 20):
            raise SystemExit("vendored safe_input.py is not a regular single-link file within 4 MiB")
        chunks, left = [], info.st_size
        while left:
            chunk = os.read(fd, left)
            if not chunk:
                raise SystemExit("vendored safe_input.py shrank while read")
            chunks.append(chunk)
            left -= len(chunk)
        if os.read(fd, 1):
            raise SystemExit("vendored safe_input.py grew while read")
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if hashlib.sha256(data).hexdigest() != SAFE_INPUT_SHA256:
        raise SystemExit("vendored safe_input.py is not the pinned %s (%s)" % (SAFE_INPUT_RELEASE, SAFE_INPUT_SHA256))
    module = types.ModuleType("safe_input")
    module.__file__ = SAFE_INPUT_PATH
    sys.modules["safe_input"] = module
    try:
        exec(compile(data, SAFE_INPUT_PATH, "exec"), module.__dict__)       # exactly the verified bytes
    except BaseException:
        del sys.modules["safe_input"]
        raise
    checks = ((module.constants_fingerprint(), SAFE_INPUT_FINGERPRINT, "constants fingerprint"),
              (module.remote_program_sha256(), REMOTE_PROGRAM_SHA256, "remote reader program"),
              (module.receive_program_sha256(), RECEIVE_PROGRAM_SHA256, "remote receive program"))
    for got, want, label in checks:
        if got != want:
            del sys.modules["safe_input"]
            raise SystemExit("safe_input %s %s is not the pinned %s" % (label, got, want))
    module._k4s_verified_sha256 = SAFE_INPUT_SHA256
    return module


si = _load_safe_input()
Refusal = si.Refusal
require = si.require
refuse = si.refuse

PRODUCTION_HOST = "127x05"
# Where these candidates may create local outputs (staging/records under the K4S runner; /tmp for scratch/tests).
PERMITTED_OUTPUT_ROOTS = ("/mpac/sdicks02/k4s-runner/", "/tmp/")
SAFE_LEAF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RENAME_NOREPLACE = 1


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    """receipts.canonical / k4s_logic.canonical (sort_keys, compact separators, no NaN)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha(value):
    return sha_bytes(canonical(value).encode())


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=1, allow_nan=False) + "\n").encode()


def local_host():
    """These tools run on 127x05 only; si.Policy re-checks the node name for every local policy."""
    node = os.uname().nodename.split(".")[0]
    require(node == PRODUCTION_HOST, "host", "these END prep tools run on %s only (this is %s)" % (PRODUCTION_HOST, node))
    return node


def output_path(path, label):
    """A new local output: absolute, normalized, under a permitted root, with a safe leaf. Returns (parent, leaf).
    Pure string check; the canonical parent, name gates and exclusive creation are si.Writer's (role roots)."""
    require(isinstance(path, str) and path.startswith("/") and os.path.normpath(path) == path and path != "/",
            "path", "%s must be an absolute normalized path: %r" % (label, path))
    require(any(path.startswith(root) for root in PERMITTED_OUTPUT_ROOTS), "path",
            "%s must be under one of %s" % (label, PERMITTED_OUTPUT_ROOTS))
    parent, leaf = path.rsplit("/", 1)
    require(SAFE_LEAF.fullmatch(leaf) is not None and not leaf.endswith(".partial"), "path",
            "%s: unsafe leaf %r" % (label, leaf))
    return parent, leaf


def input_dir(path, label):
    """A local input directory argument: absolute and normalized (roles re-check canonical ancestry by fd)."""
    require(isinstance(path, str) and path.startswith("/") and os.path.normpath(path) == path and path != "/",
            "path", "%s must be an absolute normalized path: %r" % (label, path))
    return path


def is_sha256(value):
    return isinstance(value, str) and si.SHA256_HEX.fullmatch(value) is not None


def need_sha256(value, label):
    require(is_sha256(value), "policy", "%s must be a 64-hex SHA-256 (production reads take expected SHAs)" % label)
    return value


_RENAMEAT2 = None


def _renameat2():
    global _RENAMEAT2
    if _RENAMEAT2 is None:
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            fn = libc.renameat2
        except AttributeError:
            refuse("rename", "renameat2 is unavailable (glibc < 2.28): no no-clobber publication")
        fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        fn.restype = ctypes.c_int
        _RENAMEAT2 = fn
    return _RENAMEAT2


def publish_dir(policy, role_name, partial_leaf, final_leaf):
    """renameat2(RENAME_NOREPLACE) of `<root>/<partial_leaf>` to `<root>/<final_leaf>` relative to the canonical
    root fd of a declared write role. Both names are single components, name-gated first; the source must be a real
    directory (lstat via dirfd); an existing final name of any kind refuses (never replaced)."""
    role = policy.role(role_name)
    require(role.access == "write", "policy", "role %s is not a write role" % role.name)
    for leaf in (partial_leaf, final_leaf):
        require(len(si.check_rel(leaf)) == 1, "path", "publish_dir names must be single components: %r" % leaf)
        si.name_gate(role.root + "/" + leaf, policy.host, role.grants)
    fd = si.open_root(role.root)
    try:
        st = os.stat(partial_leaf, dir_fd=fd, follow_symlinks=False)
        require(stat.S_ISDIR(st.st_mode), "not-dir", "%s is not a real directory" % partial_leaf)
        if _renameat2()(fd, partial_leaf.encode(), fd, final_leaf.encode(), RENAME_NOREPLACE) != 0:
            err = ctypes.get_errno()
            refuse("exists" if err == errno.EEXIST else "rename", "%s/%s -> %s: %s"
                   % (role.root, partial_leaf, final_leaf, os.strerror(err)))
        os.fsync(fd)
    finally:
        os.close(fd)


def unlink_own(policy, role_name, rel):
    """Remove ONE file this run created inside its own fresh .partial output (a regular single-link file, checked by
    no-follow fstatat on the gated parent fd). Used only for the guard repo's FETCH_HEAD; nothing else is deleted."""
    role, parts = si._gate(policy, role_name, rel, "write")
    root = si.open_root(role.root)
    try:
        parent = si.open_dirs(root, parts[:-1], "%s:%s" % (role.name, rel))
    finally:
        os.close(root)
    try:
        st = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        require(not stat.S_ISLNK(st.st_mode), "symlink", "%s is a symlink" % rel)
        require(stat.S_ISREG(st.st_mode), "not-regular", "%s is not a regular file" % rel)
        require(st.st_nlink == 1, "nlink", "%s is hard-linked (st_nlink %d)" % (rel, st.st_nlink))
        os.unlink(parts[-1], dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def chmod_readonly(policy, role_name, rel, mode=0o444):
    """fchmod one file of a declared role through the descriptor gate (no-follow walk, regular, st_nlink == 1)."""
    role, parts = si._gate(policy, role_name, rel, policy.role(role_name).access)
    root = si.open_root(role.root)
    try:
        parent = si.open_dirs(root, parts[:-1], "%s:%s" % (role.name, rel))
    finally:
        os.close(root)
    try:
        fd, _ = si.open_leaf(parent, parts[-1], role.max_size, None, "%s:%s" % (role.name, rel))
    finally:
        os.close(parent)
    try:
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def dirs_of(paths):
    """Every parent directory of the given relative file paths, parents first (receiver order)."""
    out = set()
    for path in paths:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            out.add("/".join(parts[:i]))
    return sorted(out, key=lambda d: (d.count("/"), d))


def import_sibling(name):
    """Import a sibling module from this directory only (python -I drops the script dir from sys.path)."""
    if sys.path[:1] != [HERE]:
        sys.path.insert(0, HERE)
    module = __import__(name)
    require(os.path.dirname(os.path.abspath(module.__file__)) == HERE, "policy",
            "sibling module %s imported from outside %s" % (name, HERE))
    return module


class Record(object):
    """A NEW local record directory (permitted root, canonical parent, exclusive mkdir) created before any other work,
    so every later refusal leaves a write-once <COMPONENT>-REFUSAL-*.json receipt in it. Its roles join the
    component's Policy (Record.roles) or, when opened before the component's policy exists (so that even a refusal
    while building that policy leaves a receipt), its own record-only Policy (open() without a policy)."""

    def __init__(self, path, component, names):
        parent, leaf = output_path(path, "--record")
        self.path, self.component, self.leaf, self.writer, self.policy = path, component, leaf, None, None
        self.roles = [si.Role("record-parent", parent, "write", 1 << 20, exact=(leaf,)),
                      si.Role("record", path, "write", 256 << 20, exact=tuple(names),
                              patterns=(component + "-REFUSAL-*.json",)),
                      si.Role("record-read", path, "read", 256 << 20, exact=tuple(names))]

    def open(self, policy=None):
        if policy is None:
            policy = si.Policy(local_host(), self.roles)
        with si.Writer(policy, "record-parent") as top:
            top.mkdir_excl(self.leaf)
        self.policy, self.writer = policy, si.Writer(policy, "record")
        return self

    def write(self, name, obj):
        self.writer.write_json_once(name, obj)
        return si.sha256_input(self.policy, "record-read", name)["sha256"]

    def refusal(self, error, context=None):
        if self.writer is None:                       # refused before the record directory existed
            return None
        return si.write_refusal_receipt(self.writer, self.component, error, context)

    def close(self):
        if self.writer is not None:
            self.writer.close()


CODE_FILES = ("end_prep_common.py", "safe_input.py", "s1b_copy_admissions.py", "s3_guard_job.py", "s9_end_runtime.py",
              "s10_stage_host.py")


def code_role():
    """Read role over this directory's code files (exact names), for the SHA-256 recorded in every manifest."""
    return si.Role("code", HERE, "read", 16 << 20, exact=CODE_FILES)


def code_sha(policy, name):
    return si.sha256_input(policy, "code", name)["sha256"]


class ScrubbedEnv(object):
    """The P2-4 environment for a frozen-code subprocess (frozen-reader interim ruling 21:28Z): exactly
    si.GIT_FIXED_ENV plus a fresh empty HOME (XDG_CONFIG_HOME inside it); nothing inherited. On exit the HOME must
    still be empty (it is removed); otherwise the run refuses and the HOME is kept as evidence."""

    def __enter__(self):
        self.home = tempfile.mkdtemp(prefix="k4s-frozen-home-")
        env = dict(si.GIT_FIXED_ENV)
        env["HOME"], env["XDG_CONFIG_HOME"] = self.home, self.home + "/xdg-config-absent"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def __exit__(self, kind, value, tb):
        try:
            os.rmdir(self.home)
        except OSError:
            if kind is None:
                refuse("subprocess", "a frozen subprocess wrote into its empty HOME %s (kept)" % self.home)
        return False
