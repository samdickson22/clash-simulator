"""K4S END host-side helpers on safe_input (S5/S6/S7 r3). Python 3.8+ stdlib plus the pinned safe_input layer.

Staged byte-identical next to safe_input.py in <END base>/tools/ on 127x03/127x04. Three users:

* k4s_end_preflight.py (S5) loads it in-process (SHA-pinned) for the registry/attempt-parent listings, the
  frozen-reader clone checks and the frozen git environment;
* the S7 host gate program carries its bytes (SHA-pinned, verified on the host before exec) for the same checks;
* k4s_end_exit_push.sh / k4s_preflight_push.sh run it through the canonical shell bootstrap r1 (``/usr/bin/python3
  -I -S -c "$k4s_loader" PATH SHA SIZE -- ...``: the interpreter opens no script by path; this file is walked, gated,
  hashed and executed from the verified bytes as __main__), and it loads safe_input through the canonical Python
  bootstrap r1 (k4s_bootstrap_load: name gate, no-follow walk, single-link leaf of the pinned size, SHA-256):

    si -- create-excl|mkdir-excl|publish-excl ...
        The safe_input CLI unchanged (si.main): exclusive, no-follow, never truncating or replacing.

    registry-snapshot --host H --repository R --round N --job J
        After END exits: list <R>/reports/explore/k4s-confirm/end/registry/round-NN/H/ names-only (every name
        checked BEFORE it is stat'ed; only attempt-NN.json, regular, st_nlink == 1), then copy each claim through
        safe_input (descriptor gate, nlink 1) into J/registry/ (exclusive) and write J/registry-listing.json
        (exclusive). Prints the listing. The wrapper pushes J/registry/ and the listing (RC-5).
    frozen-exec -- ARGV...
        Verify the --repository clone named in ARGV through safe_input (frozen-reader ruling, role "repository":
        full clone), build the frozen-reader environment (every inherited GIT_* variable removed, the P2-4 git keys
        set, XDG_CONFIG_HOME/HOME absolute+normalized+canonical or refused; HOME=//x installed as /x), statically
        check exactly the config
        files THAT environment makes git read, then exec ARGV with that same environment object.

Exit: 0 ok; 3 refused (``REFUSE <code>: <reason>`` on stderr, nothing published); 2 usage.

Two safe_input limits are handled here by composing its own primitives, never by bypassing them:
* a directory inside the strict END namespace (k4s-confirm/end) cannot be a role root or a walked directory, so the
  registry is listed names-only: ``si.open_root`` + ``si.open_dirs`` (component-wise O_NOFOLLOW) + ``os.listdir``;
  every name must match its fixed regex (round-NN / host / attempt-NN.json) BEFORE any fstatat, and claim leaves
  also pass ``si.name_gate`` with the exact END grants; anything else refuses the whole listing;
* the user's global git config cannot be disabled on git 2.25 (GIT_CONFIG_GLOBAL needs git >= 2.32), so the files
  git_config_files() enumerates for the executed environment are checked with safe_input's own repository-config
  gate (``si._check_git_config``, after ``si.name_gate``) and the code-running keys are overridden through
  GIT_CONFIG_PARAMETERS (r3, END-FULL-F3: env_path refuses relative/empty/non-normalized XDG_CONFIG_HOME and HOME,
  except HOME's leading '//' of the fleet passwd entry, which is replaced by the canonical value IN the executed
  environment; the checked paths are derived from that environment, so they cannot diverge);
* r3, END-FULL-F2: clone checks take an explicit role; only "guard-repo" (the S3 Q3 depth-1 repo) may be shallow.
"""
import hashlib
import json
import os
import re
import stat
import sys
import types

SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
END_HOSTS = ("127x03", "127x04")
STUDY_PARTS = ("reports", "explore", "k4s-confirm")
REGISTRY_REL = "reports/explore/k4s-confirm/end/registry"
ROUND_DIR = re.compile(r"round-[0-9]{2}")
CLAIM = re.compile(r"attempt-[0-9]{2}\.json")
END_GRANTS = ("end-json-exact", "end-claim-exact")
CLAIM_CAP = 1 << 20
MAX_CLAIMS = 100
# P2-4 git environment for FROZEN code that spawns git itself (frozen-reader ruling, COORDINATOR 21:28Z): every
# GIT_* key of safe_input.GIT_FIXED_ENV, plus the -c overrides git_run passes on its command line.
GIT_CONFIG_PARAMETERS = "'core.hookspath=/dev/null' 'core.fsmonitor=false' 'protocol.allow=never'"


class HostRefusal(Exception):
    def __init__(self, code, reason):
        Exception.__init__(self, code + ": " + reason)
        self.code, self.reason = code, reason


def refuse(code, reason):
    raise HostRefusal(code, reason)


# ---------------------------------------------------------------- pinned stdlib loader (before safe_input exists)
# r3 (END-FULL-F1): the vendored safe_input layer is read ONLY through the canonical bootstrap r1 below
# (bootstrap-r1/k4s_bootstrap_r1.py, pasted verbatim between its BEGIN/END lines; the pins stay outside): absolute
# normalized path (default: next to __file__, never resolved), every component outside the outcome-name families, an
# O_DIRECTORY|O_NOFOLLOW walk from "/", a regular single-link leaf of exactly SAFE_INPUT_SIZE bytes BEFORE any byte is
# read; exactly those bytes are hashed and executed. The constants fingerprint is checked afterwards.
SAFE_INPUT_FILE = "safe_input.py"
SAFE_INPUT_SIZE = 133606

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


def bootstrap_refusal(message):
    return HostRefusal("bootstrap", message)


def check_safe_input(si):
    if si.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:
        refuse("bootstrap", "safe_input constants fingerprint differs from the pin")
    return si


def load_safe_input(path=None):
    """The vendored safe_input (next to this file unless `path` is given) through the canonical bootstrap, then its
    constants fingerprint."""
    path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path
    return check_safe_input(k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, "safe_input",
                                               bootstrap_refusal))


# ---------------------------------------------------------------- names-only listings

def lstat_at(dir_fd, name):
    try:
        return os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def names_only(si, policy, role_name):
    """Sorted names directly inside a read role's root (canonical, O_NOFOLLOW walk), each name gated by
    si.name_gate before anything else; nothing is stat'ed or opened. For "must be empty" checks."""
    role = policy.role(role_name)
    fd = si.open_root(role.root)
    try:
        names = sorted(os.listdir(fd))
    finally:
        os.close(fd)
    for name in names:
        si.name_gate(role.root + "/" + name, policy.host, role.grants)
    return names


def registry_listing(si, host, repository):
    """Names-only listing of <repository>/reports/explore/k4s-confirm/end/registry: {end_exists, exists,
    claims: {"round-NN/<host>": [attempt-NN.json, ...]}}. Every component is opened O_DIRECTORY|O_NOFOLLOW from the
    canonical repository root; every name must match its regex BEFORE it is stat'ed; claim leaves must also pass
    si.name_gate with the exact END grants and be regular with st_nlink == 1. Anything else refuses."""
    si.name_gate(repository, host, ())
    root = si.open_root(repository)
    try:
        study = si.open_dirs(root, list(STUDY_PARTS), "registry " + repository)
    finally:
        os.close(root)
    out = dict(end_exists=False, exists=False, claims={})
    fds = [study]
    try:
        for name, key in (("end", "end_exists"), ("registry", "exists")):
            st = lstat_at(fds[-1], name)
            if st is None:
                return out
            if not stat.S_ISDIR(st.st_mode):
                refuse("registry", "%s is not a real directory" % name)
            fds.append(si.open_dirs(fds[-1], [name], "registry " + name))
            out[key] = True
        registry = fds[-1]
        for round_name in sorted(os.listdir(registry)):
            if ROUND_DIR.fullmatch(round_name) is None:
                refuse("registry", "unexpected name in the registry: %r" % round_name)
            round_fd = si.open_dirs(registry, [round_name], "registry " + round_name)
            try:
                for host_name in sorted(os.listdir(round_fd)):
                    if host_name not in END_HOSTS:
                        refuse("registry", "unexpected name in %s: %r" % (round_name, host_name))
                    host_fd = si.open_dirs(round_fd, [host_name], "registry " + host_name)
                    try:
                        names = sorted(os.listdir(host_fd))
                        for name in names:
                            if CLAIM.fullmatch(name) is None:
                                refuse("registry", "unexpected name in %s/%s: %r" % (round_name, host_name, name))
                            si.name_gate("%s/%s/%s/%s/%s" % (repository, REGISTRY_REL, round_name, host_name, name),
                                         host, END_GRANTS)
                            st = lstat_at(host_fd, name)
                            if st is None or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                                refuse("registry", "claim %s/%s/%s is not a single-link regular file"
                                       % (round_name, host_name, name))
                        out["claims"][round_name + "/" + host_name] = names
                    finally:
                        os.close(host_fd)
            finally:
                os.close(round_fd)
        return out
    finally:
        for fd in fds:
            os.close(fd)


def claim_rels(round_index, host, names):
    return ["%s/round-%02d/%s/%s" % (REGISTRY_REL, round_index, host, n) for n in names]


# ---------------------------------------------------------------- frozen-reader ruling: clone checks and git env

def env_path(si, env, key, required, leading_double_slash=False):
    """`env[key]` as an absolute, normalized (si.check_abs: no '//', trailing '/', '.', '..', backslash or control
    character) and canonical (realpath-equal: no symlinked component) path; None if the key is absent and not required.
    r3 (END-FULL-F3): a relative value (git resolves it against each ``git -C`` directory), an empty-but-set value
    (git falls back to another file) and any other non-normalized value are REFUSED. The single exception, allowed
    only where the caller asks for it (HOME): a leading '//' (the fleet passwd home is ``//home/sdicks02``, so sshd
    sets HOME=//home/sdicks02) is returned as '/' + rest; the caller installs that canonical value in the executed
    environment, so the value checked is the value executed."""
    if key not in env:
        if required:
            refuse("git-env", "%s is not set" % key)
        return None
    value = env[key]
    if not isinstance(value, str) or value == "":
        refuse("git-env", "%s is set but empty" % key)
    if not value.startswith("/"):
        refuse("git-env", "%s is relative (%r): git would resolve it against the -C directory" % (key, value))
    if leading_double_slash and value.startswith("//") and not value.startswith("///"):
        value = value[1:]
    try:
        si.check_abs(value)
    except si.Refusal:
        refuse("git-env", "%s is not a normalized absolute path: %r" % (key, value))
    if os.path.realpath(value) != value:
        refuse("git-env", "%s is not canonical (symlinked component): %s" % (key, value))
    return value


def frozen_git_env(si, inherited):
    """THE frozen-reader environment (single source of truth for S5, S6 frozen-exec and S7): `inherited` with every
    GIT_* key removed and the P2-4 GIT_* keys set; XDG_CONFIG_HOME (optional) must pass env_path unchanged; HOME
    (required) is replaced by its canonical env_path value (only a leading '//' can differ). No other key is changed.
    Returns a new dict; git_config_files() derives the checked paths from THIS dict."""
    home = env_path(si, inherited, "HOME", True, leading_double_slash=True)
    env_path(si, inherited, "XDG_CONFIG_HOME", False)
    env = {k: v for k, v in inherited.items() if not k.startswith("GIT_")}
    env.update({k: v for k, v in si.GIT_FIXED_ENV.items() if k.startswith("GIT_")})
    env["GIT_CONFIG_PARAMETERS"] = GIT_CONFIG_PARAMETERS
    env["HOME"] = home
    return env


def git_config_files(si, env):
    """Every config FILE the installed git (2.25.1; config.c do_git_config_sequence) reads under `env`, besides the
    repository's own .git/config and .git/config.worktree (si._git_preflight checks those) and GIT_CONFIG_PARAMETERS
    (set here, no file):
      system  /etc/gitconfig: never read, because GIT_CONFIG_NOSYSTEM=1 is required in `env`;
      XDG     $XDG_CONFIG_HOME/git/config when XDG_CONFIG_HOME is set (non-empty), else $HOME/.config/git/config;
      global  $HOME/.gitconfig (expand_user_path("~/.gitconfig"); HOME is required).
    GIT_CONFIG (read only by ``git config``) and GIT_CONFIG_GLOBAL/GIT_CONFIG_SYSTEM (git >= 2.32) are GIT_* keys and
    are removed or fixed by frozen_git_env. include/includeIf sections are refused by the static check, so no other
    file is reachable. Derived from `env` itself: the paths checked are the paths the executed git reads."""
    if env.get("GIT_CONFIG_NOSYSTEM") != "1":
        refuse("git-env", "GIT_CONFIG_NOSYSTEM=1 is required (the system config is not checked)")
    home = env_path(si, env, "HOME", True)
    xdg = env_path(si, env, "XDG_CONFIG_HOME", False)
    return ((xdg if xdg is not None else home + "/.config") + "/git/config", home + "/.gitconfig")


def check_global_git_config(si, host, env):
    """The git_config_files(env) through safe_input: each path passes si.name_gate for `host` (outcome families,
    END namespace, forbidden prefixes) BEFORE any syscall, is walked component-wise O_NOFOLLOW from '/' (a symlinked
    component refuses), and an existing file passes si._check_git_config (regular, st_nlink 1, no symlink leaf; no
    driver/include section, no code-running core key). An absent file is skipped. Returns the checked file paths."""
    checked = []
    for path in git_config_files(si, env):
        parts = si.name_gate(path, host, ())
        top = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            if not si._exists_nofollow(top, parts, path):
                continue
            parent = si.open_dirs(top, parts[:-1], path)
        finally:
            os.close(top)
        try:
            si._check_git_config(parent, parts[-1], os.path.dirname(path))
        finally:
            os.close(parent)
        checked.append(path)
    return checked


def frozen_env_checked(si, host, inherited):
    """(env, record): the ONE environment a frozen reader is executed with, and the static check of exactly the
    config files that environment makes git read. Callers execute `env` itself (never a re-derived one)."""
    env = frozen_git_env(si, inherited)
    files = git_config_files(si, env)
    checked = check_global_git_config(si, host, env)
    return env, dict(config_files=list(files), global_config_checked=checked,
                     git_keys=sorted(k for k in env if k.startswith("GIT_")))


def canonical(value):                                       # = k4s_logic.canonical (k4s_logic.py:106-107)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def bundle_sans_guard_sha256(manifest):
    """SHA-256 of the canonical bundle manifest with reference_load_profile.guard.job removed: the identity two
    per-attempt bundles share when they differ ONLY in their fresh guard job (RC-3; T1 END-A5). S5 exports it for its
    own and its compare bundle; the S7 host program recomputes it from the attempt bundle's pinned tiers-pins.json
    (END-FULL-F5b)."""
    if not isinstance(manifest, dict):
        refuse("bundle", "bundle manifest is not an object")
    stripped = json.loads(json.dumps(manifest))
    guard = (stripped.get("reference_load_profile") or {}).get("guard")
    if not isinstance(guard, dict) or not isinstance(guard.get("job"), str):
        refuse("bundle", "bundle manifest lacks reference_load_profile.guard.job")
    del guard["job"]
    return hashlib.sha256(canonical(stripped).encode()).hexdigest()


CLONE_ROLES = ("repository", "guard-repo")
PROMISOR_KEYS = (("extensions", "partialclone"), ("remote", "promisor"), ("remote", "partialclonefilter"),
                 ("core", "partialclonefilter"))
SHALLOW_CAP = 1 << 16
OID40 = re.compile(r"[0-9a-f]{40}")


def clone_repo(si, work_tree, role):
    """The si.GitRepo of a host clone in an explicit role (END-FULL-F2). "repository" (the evidence / END-JOB
    --repository clone): full, so si refuses .git/shallow. "guard-repo" (the S3 Q3 guard job repo/): the minimal
    depth-1 SHALLOW clone S3 builds and proves, so shallow is the ONE declared allowance; alternates and grafts
    still refuse. There is no default role."""
    if role not in CLONE_ROLES:
        refuse("policy", "unknown clone role %r (one of %s)" % (role, ", ".join(CLONE_ROLES)))
    return si.GitRepo(work_tree=work_tree, allow=("shallow",) if role == "guard-repo" else ())


def config_sections(text):
    """(section, key) names of a git config text, casefolded; subsections dropped (names only, values ignored)."""
    out, section = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            head = line[1:].split("]", 1)[0].strip()
            section = head.split(None, 1)[0].split(".", 1)[0].strip('"').casefold()
            line = line.split("]", 1)[1].strip() if "]" in line else ""
            if not line:
                continue
        out.append((section, line.split("=", 1)[0].strip().casefold()))
    return out


def verify_clone(si, host, work_tree, grants=(), *, role):
    """A host clone that frozen code will run git in (frozen-reader ruling), in an explicit `role` (clone_repo):
    safe_input's static git preflight (canonical work tree, real .git and objects/, no commondir, alternates, grafts,
    driver/include config or code-running core keys; shallow only for "guard-repo") via si.git_run; no refs under
    refs/replace/; .git/hooks absent or holding only *.sample files (regular, st_nlink 1); r3: no promisor/partial
    clone (extensions.partialClone, remote.*.promisor / partialclonefilter in .git/config, objects/pack/*.promisor);
    "guard-repo": `rev-parse --is-shallow-repository` is true and .git/shallow (regular, st_nlink 1) lists only
    40-hex commits present in the repository. Returns a record."""
    repo = clone_repo(si, work_tree, role)
    replace = si.git_run(repo, ["for-each-ref", "--format=%(refname)", "refs/replace/"], 60, 1 << 16).stdout
    if replace != b"":
        refuse("indirection", "%s has replace refs" % work_tree)
    git_dir = work_tree + "/.git"
    hooks_root = git_dir + "/hooks"
    policy = si.Policy(host, [si.Role("clone-git", git_dir, "read", 1 << 20,
                                      exact=("hooks", "config", "shallow", "objects/pack"), grants=grants),
                              si.Role("clone-hooks", hooks_root, "read", 1 << 20, patterns=("*.sample",),
                                      grants=grants),
                              si.Role("clone-pack", git_dir + "/objects/pack", "read", 1, patterns=("*",),
                                      grants=grants)])
    try:
        si.check_absent(policy, "clone-git", "hooks")
        hooks = []
    except si.Refusal as error:
        if error.code != "exists":
            raise
        hooks = [f["rel"] for f in si.walk_tree(policy, "clone-hooks")["files"]]
    config = si.read_bytes(policy, "clone-git", "config", max_size=1 << 20).decode("utf-8", "replace")
    promisor = sorted("%s.%s" % k for k in config_sections(config) if k in PROMISOR_KEYS)
    if promisor:
        refuse("indirection", "%s is a promisor/partial clone (%s)" % (work_tree, ", ".join(promisor)))
    try:
        si.check_absent(policy, "clone-git", "objects/pack")
        packs = []
    except si.Refusal as error:
        if error.code != "exists":
            raise
        packs = names_only(si, policy, "clone-pack")
    if any(name.endswith(".promisor") for name in packs):
        refuse("indirection", "%s has a promisor pack" % work_tree)
    record = dict(work_tree=work_tree, role=role, replace_refs=0, hooks=hooks, promisor=False, static_preflight=True)
    if role == "guard-repo":
        flag = si.git_run(repo, ["rev-parse", "--is-shallow-repository"], 60, 64).stdout
        if flag != b"true\n":
            refuse("indirection", "%s is not the depth-1 shallow Q3 guard repository" % work_tree)
        lines = si.read_bytes(policy, "clone-git", "shallow", max_size=SHALLOW_CAP).decode("ascii", "replace")
        shallow = lines.split("\n")
        if shallow[-1] != "" or not shallow[:-1] or not all(OID40.fullmatch(s) for s in shallow[:-1]):
            refuse("indirection", "%s/.git/shallow is not a list of commit ids" % work_tree)
        for commit in shallow[:-1]:
            si.git_run(repo, ["cat-file", "-e", commit + "^{commit}"], 60, 4096)
        record["shallow_commits"] = shallow[:-1]
    return record


def seed_commits(si, guard_repo, commits, *, role):
    """Ruling Q3: `git cat-file -e <c>^{commit}` for each frozen seed commit in the guard job's repo/ (role must be
    "guard-repo": the shallow allowance is declared for that role only)."""
    if role != "guard-repo":
        refuse("policy", "Q3 seed commits are checked in the guard-repo role only")
    repo = clone_repo(si, guard_repo, role)
    for commit in commits:
        si.git_run(repo, ["cat-file", "-e", commit + "^{commit}"], 60, 4096)
    return {c: True for c in commits}


# ---------------------------------------------------------------- S6: registry snapshot for the post-exit push

def registry_snapshot(si, host, repository, round_index, job):
    """RC-5 through safe_input: copy this host's round registry into <job>/registry/ and write
    <job>/registry-listing.json, both exclusive. Returns the listing document."""
    listing = registry_listing(si, host, repository)
    names = listing["claims"].get("round-%02d/%s" % (round_index, host), []) if listing["exists"] else []
    if len(names) > MAX_CLAIMS:
        refuse("registry", "too many claims")
    rels = claim_rels(round_index, host, names)
    out_names = tuple("registry/" + n for n in names) + ("registry-listing.json",)
    roles = [si.Role("job-out", job, "write", CLAIM_CAP, exact=out_names, grants=("end-claim-exact",))]
    if rels:
        roles.append(si.Role("registry", repository, "read", CLAIM_CAP, exact=rels, grants=END_GRANTS))
    policy = si.Policy(host, roles)
    claims = []
    with si.Writer(policy, "job-out") as writer:
        if names:
            writer.mkdir_excl("registry")
        for name, rel in zip(names, rels):
            got = si.copy_input(policy, "registry", rel, writer, "registry/" + name)
            claims.append(dict(name=name, sha256=got["sha256"], size=got["size"]))
        doc = dict(schema="clasher.k4s.end-registry-listing.v1", host=host, round=round_index,
                   registry_exists=listing["exists"], end_exists=listing["end_exists"], claims=claims,
                   other_rounds={k: v for k, v in listing["claims"].items()
                                 if k != "round-%02d/%s" % (round_index, host)})
        writer.write_json_once("registry-listing.json", doc)
    return doc


def option_value(argv, name):
    values = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == name]
    if len(values) != 1:
        refuse("argv", "%s must appear exactly once" % name)
    return values[0]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    try:
        si = load_safe_input()                          # canonical bootstrap r1 (END-FULL-F1)
        host = os.uname().nodename.split(".")[0]          # si.Policy re-checks it for every role below
        if host not in END_HOSTS:
            refuse("host", "runs on 127x03/127x04 only")
        if argv[0] == "registry-snapshot":
            opts = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2)}
            if sorted(opts) != ["--host", "--job", "--repository", "--round"] or len(argv) != 9:
                refuse("argv", "registry-snapshot --host H --repository R --round N --job J")
            if opts["--host"] != host or re.fullmatch(r"0|[1-9][0-9]?", opts["--round"]) is None:
                refuse("argv", "wrong host or round")
            doc = registry_snapshot(si, host, opts["--repository"], int(opts["--round"]), opts["--job"])
            print(json.dumps(doc, sort_keys=True))
            return 0
        if argv[0] == "si" and len(argv) > 2 and argv[1] == "--":
            return si.main(argv[2:])                   # the safe_input CLI (create-excl / mkdir-excl / publish-excl)
        if argv[0] == "frozen-exec" and len(argv) > 2 and argv[1] == "--":
            command = argv[2:]
            record = verify_clone(si, host, option_value(command, "--repository"), role="repository")
            env, record["git_env"] = frozen_env_checked(si, host, dict(os.environ))
            sys.stderr.write("frozen-exec: %s\n" % json.dumps(record, sort_keys=True))
            sys.stderr.flush()
            os.execvpe(command[0], command, env)                # the very env whose config files were checked
        sys.stderr.write("usage: registry-snapshot ... | frozen-exec -- ARGV...\n")
        return 2
    except Exception as error:                       # si.Refusal, HostRefusal, OSError: refuse, publish nothing
        sys.stderr.write("REFUSE %s: %s\n" % (getattr(error, "code", type(error).__name__), error))
        return 3


if __name__ == "__main__":
    sys.exit(main())
