"""K4S END host-side helpers on safe_input (S5/S6/S7 r2). Python 3.8+ stdlib plus the pinned safe_input layer.

Staged byte-identical next to safe_input.py in <END base>/tools/ on 127x03/127x04. Three users:

* k4s_end_preflight.py (S5) loads it in-process (SHA-pinned) for the registry/attempt-parent listings, the
  frozen-reader clone checks and the frozen git environment;
* the S7 host gate program carries its bytes (SHA-pinned, verified on the host before exec) for the same checks;
* k4s_end_exit_push.sh / k4s_preflight_push.sh run it with ``/usr/bin/python3 -I -S`` (so the interpreter opens
  only this one script by path; safe_input is loaded by read_pinned: O_NOFOLLOW, st_nlink 1, SHA-256):

    si -- create-excl|mkdir-excl|publish-excl ...
        The safe_input CLI unchanged (si.main): exclusive, no-follow, never truncating or replacing.

    registry-snapshot --host H --repository R --round N --job J
        After END exits: list <R>/reports/explore/k4s-confirm/end/registry/round-NN/H/ names-only (every name
        checked BEFORE it is stat'ed; only attempt-NN.json, regular, st_nlink == 1), then copy each claim through
        safe_input (descriptor gate, nlink 1) into J/registry/ (exclusive) and write J/registry-listing.json
        (exclusive). Prints the listing. The wrapper pushes J/registry/ and the listing (RC-5).
    frozen-exec -- ARGV...
        Verify the --repository clone named in ARGV through safe_input (frozen-reader ruling), then exec ARGV with
        every inherited GIT_* variable removed and the P2-4 git environment set (FROZEN_GIT_ENV).

Exit: 0 ok; 3 refused (``REFUSE <code>: <reason>`` on stderr, nothing published); 2 usage.

Two safe_input limits are handled here by composing its own primitives, never by bypassing them:
* a directory inside the strict END namespace (k4s-confirm/end) cannot be a role root or a walked directory, so the
  registry is listed names-only: ``si.open_root`` + ``si.open_dirs`` (component-wise O_NOFOLLOW) + ``os.listdir``;
  every name must match its fixed regex (round-NN / host / attempt-NN.json) BEFORE any fstatat, and claim leaves
  also pass ``si.name_gate`` with the exact END grants; anything else refuses the whole listing;
* the user's global git config cannot be disabled on git 2.25 (GIT_CONFIG_GLOBAL needs git >= 2.32), so it is
  checked with safe_input's own repository-config gate (``si._check_git_config``) and overridden for the keys that
  run code through GIT_CONFIG_PARAMETERS.
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

def read_pinned(path, sha256, cap=1 << 23):
    """Bootstrap read of one pinned file before safe_input is available: canonical absolute path, O_NOFOLLOW,
    regular, st_nlink == 1, size cap, exact size, SHA-256 equal to the pin. Returns the bytes."""
    path = str(path)
    if not path.startswith("/") or path.startswith("//") or os.path.realpath(path) != path:
        refuse("bootstrap", "pinned file path is not canonical: %r" % path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > cap:
            refuse("bootstrap", "pinned file is not a single-link regular file within the cap: %s" % path)
        chunks, left = [], st.st_size
        while left:
            chunk = os.read(fd, min(left, 1 << 20))
            if not chunk:
                refuse("bootstrap", "pinned file shrank: %s" % path)
            chunks.append(chunk)
            left -= len(chunk)
        if os.read(fd, 1):
            refuse("bootstrap", "pinned file grew: %s" % path)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if hashlib.sha256(data).hexdigest() != sha256:
        refuse("bootstrap", "pinned file SHA-256 mismatch: %s" % path)
    return data


def module_from_bytes(name, data, origin):
    module = types.ModuleType(name)
    module.__file__ = origin
    exec(compile(data, origin, "exec"), module.__dict__)
    return module


def check_safe_input(si):
    if si.constants_fingerprint() != SAFE_INPUT_FINGERPRINT:
        refuse("bootstrap", "safe_input constants fingerprint differs from the pin")
    return si


def load_safe_input(directory):
    """safe_input.py from `directory` (the staged tools dir), SHA- and fingerprint-pinned."""
    path = os.path.join(directory, "safe_input.py")
    return check_safe_input(module_from_bytes("safe_input", read_pinned(path, SAFE_INPUT_SHA256), path))


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

def frozen_git_env(si, inherited):
    """`inherited` with every GIT_* key removed and the P2-4 git keys set (no other key is changed)."""
    env = {k: v for k, v in inherited.items() if not k.startswith("GIT_")}
    env.update({k: v for k, v in si.GIT_FIXED_ENV.items() if k.startswith("GIT_")})
    env["GIT_CONFIG_PARAMETERS"] = GIT_CONFIG_PARAMETERS
    return env


def canonical_home(inherited):
    home = inherited.get("HOME") or ""
    if not home.startswith("/"):
        refuse("git-env", "HOME is not absolute")
    home = "/" + home.lstrip("/")                  # git reads //home/x and /home/x alike
    if os.path.realpath(home) != home:
        refuse("git-env", "HOME is not canonical: %s" % home)
    return home


def check_global_git_config(si, inherited):
    """The user's global git config files (the only config git 2.25 reads besides the repository's once
    GIT_CONFIG_NOSYSTEM=1) through safe_input's repository-config gate: no driver/include section, no core key that
    runs code or relocates the work tree. Each path is walked component-wise O_NOFOLLOW from '/' (a symlinked
    component refuses); an absent file is skipped. Returns the checked file paths."""
    home = canonical_home(inherited)
    xdg = inherited.get("XDG_CONFIG_HOME") or home + "/.config"
    checked = []
    for path in (home + "/.gitconfig", "/" + xdg.lstrip("/") + "/git/config"):
        parts = si.check_abs(path)
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


def verify_clone(si, host, work_tree, grants=()):
    """A host clone that frozen code will run git in (frozen-reader ruling): safe_input's static git preflight
    (canonical work tree, real .git and objects/, no commondir, alternates, grafts, shallow, driver/include config or
    code-running core keys) via si.git_run, no refs under refs/replace/, and .git/hooks absent or holding only
    *.sample files (regular, st_nlink 1). Returns a record."""
    repo = si.GitRepo(work_tree=work_tree)
    replace = si.git_run(repo, ["for-each-ref", "--format=%(refname)", "refs/replace/"], 60, 1 << 16).stdout
    if replace != b"":
        refuse("indirection", "%s has replace refs" % work_tree)
    hooks_root = work_tree + "/.git/hooks"
    policy = si.Policy(host, [si.Role("clone-git", work_tree + "/.git", "read", 1 << 20, exact=("hooks",),
                                      grants=grants),
                              si.Role("clone-hooks", hooks_root, "read", 1 << 20, patterns=("*.sample",),
                                      grants=grants)])
    try:
        si.check_absent(policy, "clone-git", "hooks")
        hooks = []
    except si.Refusal as error:
        if error.code != "exists":
            raise
        hooks = [f["rel"] for f in si.walk_tree(policy, "clone-hooks")["files"]]
    return dict(work_tree=work_tree, replace_refs=0, hooks=hooks, static_preflight=True)


def seed_commits(si, guard_repo, commits):
    """Ruling Q3: `git cat-file -e <c>^{commit}` for each frozen seed commit in the guard job's repo/."""
    repo = si.GitRepo(work_tree=guard_repo)
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
        here = os.path.dirname(os.path.abspath(__file__))
        si = load_safe_input(here)
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
            record = verify_clone(si, host, option_value(command, "--repository"))
            check_global_git_config(si, os.environ)
            sys.stderr.write("frozen-exec: %s\n" % json.dumps(record, sort_keys=True))
            sys.stderr.flush()
            os.execvpe(command[0], command, frozen_git_env(si, os.environ))
        sys.stderr.write("usage: registry-snapshot ... | frozen-exec -- ARGV...\n")
        return 2
    except Exception as error:                       # si.Refusal, HostRefusal, OSError: refuse, publish nothing
        sys.stderr.write("REFUSE %s: %s\n" % (getattr(error, "code", type(error).__name__), error))
        return 3


if __name__ == "__main__":
    sys.exit(main())
