"""Shared glue for the S1b / S3 / S9 / S10 r3 candidates (stdlib only; Python 3.8+). CANDIDATE: Sol review.

Every read, hash, stat, open, stream, write, subprocess and git call in these components goes through the shared
`safe_input` layer (rulings P2-1, P2-4, D1-D4). This module only:

* loads the vendored, byte-identical safe_input.py from this directory through the bootstrap-r1 CANONICAL BOOTSTRAP
  (pasted verbatim below; END-FULL-F1): normalized absolute path, outcome name families on every component, a
  component-wise O_DIRECTORY|O_NOFOLLOW walk from "/", the leaf regular / st_nlink 1 / exactly SAFE_INPUT_SIZE
  before any byte is read, the SHA-256 pin, then exactly the verified bytes executed (never re-read). Then the
  constants fingerprint and the SHA-256 of the two shipped remote programs (reader, receive) must equal the pins;
* loads sibling modules (load_sibling) the same way, with the caller's pins;
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

# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 (bootstrap-r1/k4s_bootstrap_r1.py; paste verbatim, byte for byte) ====
# END-FULL-F1. The only way a K4S END component may read a pinned stdlib-loaded file (its vendored safe_input layer,
# or a host tool) before the shared layer exists. Stdlib only, Python 3.8+, Linux, no assert (holds under -O), no
# single-quote character (so the same text can sit inside a single-quoted shell word). Contract, in order:
#   1. the path is absolute and already normalized (normpath(p) == p; no empty, "." or ".." component, no trailing
#      slash, no control or backslash character). Nothing is canonicalized: realpath is never called;
#   2. every component (ancestors and leaf) passes the safe_input r3 OUTCOME name families (casefolded fullmatch,
#      the same regex literals; conformance-tested against si.outcome_family);
#   3. a component-wise walk from "/": each ancestor is opened O_DIRECTORY|O_NOFOLLOW relative to its parent fd and
#      fstat must say directory (a symlink, a non-directory or a missing ancestor refuses);
#   4. the leaf is fstatat-ed without following (regular, st_nlink == 1, exactly the pinned size) BEFORE it is opened,
#      then opened O_NOFOLLOW|O_NONBLOCK relative to the parent fd and fstat-ed again (same dev/ino, regular,
#      st_nlink == 1, pinned size) BEFORE any byte is read;
#   5. exactly the pinned size is read from THAT descriptor, EOF is confirmed, the SHA-256 must equal the pin, and
#      exactly those bytes are compiled and executed in a fresh module registered under the caller-given name. The
#      code object is compiled under a "<k4s-bootstrap ...>" filename (linecache is given the verified lines) so no
#      traceback, import or inspect call ever re-opens the path after hashing;
#   6. every refusal is `raise refusal(message)`, the caller-chosen refusal convention (an exception class, or a
#      callable returning the exception to raise).
K4S_BOOTSTRAP_RELEASE = "k4s-bootstrap-r1"
K4S_BOOTSTRAP_OUTCOME_FAMILIES = (                      # == safe_input r3 OUTCOME_FAMILIES (literal copy, tested)
    ("games", r"(?:.*[^a-z])?" + r"games" + r"(?:[^a-z].*)?"),
    ("hub-blocks", r"(?:.*[^a-z])?" + r"hub[-_.]?blocks?" + r"(?:[^a-z].*)?"),
    ("complete-json", r".*complete.*\.json.*"),
    ("interference-json", r".*interference.*\.json.*"),
    ("hub-ack-json", r".*hub[-_.]?ack.*\.json.*"),
    ("end-raw-json", r".*end[-_.]?raw.*\.json.*"),
)
K4S_BOOTSTRAP_MAX_SIZE = 1 << 24


def k4s_bootstrap_name_family(component):
    """The OUTCOME family label of one path component (casefolded fullmatch), or None."""
    import re
    folded = component.casefold()
    for label, rx in K4S_BOOTSTRAP_OUTCOME_FAMILIES:
        if re.fullmatch(rx, folded, re.S):
            return label
    return None


def k4s_bootstrap_default_path(module_file, leaf):
    """The sibling `leaf` of `module_file`, made absolute without resolving or normalizing anything: an alias or a
    non-normalized __file__ stays visible, so the walk refuses it."""
    import os
    directory = os.path.dirname(module_file)
    if not directory.startswith("/"):
        directory = os.getcwd() + ("/" + directory if directory else "")
    return directory + "/" + leaf


def k4s_bootstrap_read_verified(path, sha256, size, refusal):
    """Steps 1-5 up to the hash: return exactly the pinned bytes, or raise refusal(message) having read nothing that
    fails a name, walk or descriptor gate."""
    import hashlib
    import os
    import stat

    def refused(reason):
        return refusal("k4s bootstrap refused: " + reason + ": " + repr(path))

    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise refused("the SHA-256 pin is not 64 lowercase hex digits")
    if type(size) is not int or not 0 < size <= K4S_BOOTSTRAP_MAX_SIZE:
        raise refused("the size pin is not an int in 1..%d" % K4S_BOOTSTRAP_MAX_SIZE)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or path.endswith("/")
            or os.path.normpath(path) != path):
        raise refused("not an absolute normalized path")
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise refused("control or backslash character in the path")
    parts = path[1:].split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise refused("empty, . or .. component")
    for p in parts:
        family = k4s_bootstrap_name_family(p)
        if family is not None:
            raise refused("outcome name family " + family + " in component " + repr(p))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise refused("/ is not a directory")
        for name in parts[:-1]:
            try:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            except OSError as error:
                raise refused("ancestor " + repr(name) + " is a symlink, not a directory or missing ("
                              + os.strerror(error.errno) + ")")
            previous, fd = fd, child
            os.close(previous)
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise refused("ancestor " + repr(name) + " is not a directory")
        leaf = parts[-1]
        try:
            before = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as error:
            raise refused("leaf cannot be inspected (" + os.strerror(error.errno) + ")")
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise refused("leaf is not a single-link regular file of the pinned size %d" % size)
        try:
            leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC,
                              dir_fd=fd)
        except OSError as error:
            raise refused("leaf cannot be opened without following (" + os.strerror(error.errno) + ")")
        try:
            info = os.fstat(leaf_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size
                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
                raise refused("opened leaf is not the inspected single-link regular file of the pinned size")
            chunks, left = [], size
            while left > 0:
                chunk = os.read(leaf_fd, left)
                if not chunk:
                    raise refused("leaf shrank while read")
                chunks.append(chunk)
                left -= len(chunk)
            if os.read(leaf_fd, 1) != b"":
                raise refused("leaf grew while read")
        finally:
            os.close(leaf_fd)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise refused("bytes are not the pinned SHA-256 " + sha256)
    return data


def k4s_bootstrap_exec(data, path, sha256, module_name):
    """Step 5 tail: compile and execute exactly `data` (already verified) in a fresh module named `module_name`."""
    import linecache
    import sys
    import types
    filename = "<k4s-bootstrap sha256=" + sha256 + " " + path + ">"
    linecache.cache[filename] = (len(data), None, data.decode("utf-8", "replace").splitlines(True), filename)
    code = compile(data, filename, "exec", dont_inherit=True)
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__k4s_bootstrap__ = (K4S_BOOTSTRAP_RELEASE, path, sha256, len(data))
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def k4s_bootstrap_load(path, sha256, size, module_name, refusal):
    """Read `path` through the full contract and execute exactly the verified bytes as module `module_name`."""
    data = k4s_bootstrap_read_verified(path, sha256, size, refusal)
    return k4s_bootstrap_exec(data, path, sha256, module_name)
# ==== END K4S CANONICAL BOOTSTRAP r1 ====


# The pin of record: safe-input-r3 (= r2 + ruling E5; its SHA256SUMS verified, PROGRESS-r3 DONE). The fingerprint
# and the reader SHA equal r3 README section 8; the receive program SHA is what the pinned bytes produce on 3.8 and
# 3.12 (39a92e9d...), as the runner's committed erratum records (README section 8 misprints it; shipped here as
# SAFE-INPUT-R3-README-ERRATUM-receive-sha.txt).
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_SIZE = 133606
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
REMOTE_PROGRAM_SHA256 = "2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152"
RECEIVE_PROGRAM_SHA256 = "39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4"
SAFE_INPUT_RELEASE = "safe-input-r3"
# END-FULL-F1: this module's own path exactly as Python was given it (made absolute, never resolved or normalized), so
# an aliased or non-normalized location stays visible to the canonical walk, which refuses it before any read.
SAFE_INPUT_PATH = k4s_bootstrap_default_path(__file__, "safe_input.py")
HERE = SAFE_INPUT_PATH[:-len("/safe_input.py")]


def bootstrap_sibling(module_name, path, sha256, size):
    """END-FULL-F1: THE way a Part A module reads a sibling before (safe_input) or besides the shared layer: the
    canonical bootstrap (name families on every component, component-wise no-follow walk from "/", leaf regular /
    st_nlink 1 / pinned size before any byte, SHA-256 pin, exactly the verified bytes executed). A module of that name
    that is already loaded is reused only if the bootstrap loaded it from the same path with the same pins."""
    existing = sys.modules.get(module_name)
    if existing is not None:
        if getattr(existing, "__k4s_bootstrap__", None) != (K4S_BOOTSTRAP_RELEASE, path, sha256, size):
            raise SystemExit("k4s bootstrap refused: a different %s module is already loaded (want %s %s)"
                             % (module_name, path, sha256))
        return existing
    return k4s_bootstrap_load(path, sha256, size, module_name, SystemExit)


def _load_safe_input():
    module = bootstrap_sibling("safe_input", SAFE_INPUT_PATH, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE)
    checks = ((module.constants_fingerprint(), SAFE_INPUT_FINGERPRINT, "constants fingerprint"),
              (module.remote_program_sha256(), REMOTE_PROGRAM_SHA256, "remote reader program"),
              (module.receive_program_sha256(), RECEIVE_PROGRAM_SHA256, "remote receive program"))
    for got, want, label in checks:
        if got != want:
            del sys.modules["safe_input"]
            raise SystemExit("safe_input %s %s is not the pinned %s" % (label, got, want))
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


def load_sibling(module_name, sha256, size):
    """A sibling module `<HERE>/<module_name>.py` through the canonical bootstrap, with the CALLER's pins (the caller's
    K4S_SIBLING_PINS, maintained by tests/k4s_adopt.py): never a sys.path import (END-FULL-F1)."""
    return bootstrap_sibling(module_name, HERE + "/" + module_name + ".py", sha256, size)


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
              "s10_stage_host.py", "s11_host_repository.py")


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
