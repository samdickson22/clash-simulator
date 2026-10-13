#!/usr/bin/env python3
"""S11 (PREREG-K4S END, integration audit U1): the host repository <base>/repository on 127x03 / 127x04, the
`--repository` clone that S5 (repository_clone), S7 (frozen reader), S6 (frozen-exec) and the frozen END itself read and
(producer_claim) write. CANDIDATE r4: host-touching; Sol review and a coordinator GO before any live run. Never inside
an END timing window or a preflight measurement on any host (C5).

What the consumers need (audit U1): a FULL non-shallow clone, verify_clone role "repository" (k4s_end_host_tool.py:
489-541: no replace refs, hooks absent or *.sample only, no promisor/partial clone, safe_input's static git preflight);
HEAD on the END branch k4s-end-r1 (BR-1), at P' for preflights (frozen fleet_end.artifact: `merge-base --is-ancestor
022ec7bf HEAD`, fleet_end.py:30-33) and at X for END (frozen end_job reads END-JOB.json from HEAD and requires it added
in exactly one commit, end_evidence.py:356-366, 415-432); a WRITABLE work tree (producer_claim mkdirs
end/registry/round-RR/<host>/ in it, end_evidence.py:499). Never main.

Modes (ONE ssh login each; S10's tools component must already have staged <base>/tools/):
  provision  --host H --commit P' : on 05, the live S9 full-clone check of REPO_FULL, refs/remotes/origin/k4s-end-r1
             must be exactly P' (a descendant of REQUIRED_ANCESTOR); `git bundle create` of that ref (complete: no
             prerequisites, exactly one ref) into a private /tmp directory, its header parsed strictly and hashed.
             On the host, ONE session (`/bin/sh -c`): [check] the SHA-bound S11 host program loads safe_input and the
             host tool from <base>/tools through the canonical bootstrap with their S7 pins (TOOL_PINS), checks <base>
             is canonical and repository / repository.partial / the transfer directory absent (reads no stdin);
             [receive] the D4 receive program (si, bootstrap-verified) creates <base>/repository-transfer-<P12>/
             exclusively with the bundle (0444, single link, SHA-256 checked); [provision] the host program re-hashes
             the bundle, makes repository.partial exclusively, `git init --template=`, fetches the bundle's ref into
             refs/heads/k4s-end-r1 (si.git_run: P2-4 environment, file protocol only, no hooks), checks it out, VERIFIES
             (below), renames repository.partial to repository with renameat2(RENAME_NOREPLACE) and verifies again.
  advance    --host H --from P' --commit X --equivalence-record F --equivalence-sha256 S [--end-job-sha256 S] : only
             after S9 refresh-clone and S9 equivalence passed (the record, read by SHA, must say P' -> X, diff exactly
             END-JOB.json, runtime/measurement files identical); X must be the tip of refs/remotes/origin/k4s-end-r1, a
             strict descendant of P'; `git bundle create P'..<ref>` (prerequisite exactly P', exactly one ref X). On the
             host, ONE session: [check] as above, plus the existing repository verified at P' with a clean work tree
             (no untracked file: no claim exists); [receive]; [advance] fetch the bundle (FETCH_HEAD only), X a strict
             descendant of P' (fast-forward only), `checkout -B k4s-end-r1 X`, VERIFY at X, END-JOB.json at HEAD has
             the OID of X's tree entry on 05 (metadata) and, with --end-job-sha256, exactly those bytes.
VERIFY (host, through the S7-pinned host tool and safe_input): k4s_end_host_tool.verify_clone(role="repository");
HEAD == the commit, HEAD -> refs/heads/k4s-end-r1, the only ref; not shallow; clean (`status --porcelain
--untracked-files=all` empty); REQUIRED_ANCESTOR is an ancestor of HEAD; .git/config exactly the four `init` core keys
(no remote, no promisor, no extensions); no hooks / shallow / alternates / grafts; the work tree root and the study
directory are owner-writable.
r5 (Sol integration r1 finding 2): every WRITING git command of the host program (provision fetch + checkout, advance
fetch + checkout) runs through _guarded: S9's GIT_WRITE_GUARD (composed verbatim into the host program) checks the
whole git write set and its ancestors BEFORE the command (FETCH_HEAD, HEAD / branch reflogs, index, packed-refs, refs,
lock siblings, .git/objects, the checkout's work-tree paths: no symlink, no hard link, no stale lock), the command runs
with the write-reducing GW_CONFIG (_git_w: si.git_run's preflight, flags and environment plus GW_CONFIG), and gw_post
re-checks afterwards (detection only). advance's checkout must write exactly END-JOB.json (diff-tree P' X).
Nothing is ever deleted on a host: the transfer directory (and, after a refusal, repository.partial) stay and are
listed in the record as needing a separately authorized cleanup. Exit codes: 0 ok; 2 refused; 1 unexpected (closed).
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile

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


# END-FULL-F1: the pins (SHA-256, size) of the sibling files this module loads, maintained by tests/k4s_adopt.py in
# dependency order (safe_input <- end_prep_common <- s9 <- s1b <- s3 <- s10 <- s11). A pin covers the file's bytes.
K4S_SIBLING_PINS = {
    'end_prep_common.py': ('2a84775bfb1365b885cb3944840e631a41eac76243558de41cc234d8ba59b877', 22617),
    's10_stage_host.py': ('e950ab171985914c0cc2fc5cf5d09b7e152fcd1f02eea9e9bb03041c9efd31c5', 68891),
}


def _k4s_common():
    """end_prep_common.py beside this file through the canonical bootstrap (never a sys.path import): its path as
    Python was given it (aliases stay visible to the walk), its pins; an already loaded end_prep_common is reused only
    if the bootstrap loaded it from that path with those pins."""
    path = k4s_bootstrap_default_path(__file__, "end_prep_common.py")
    sha256, size = K4S_SIBLING_PINS["end_prep_common.py"]
    existing = sys.modules.get("end_prep_common")
    if existing is not None:
        if getattr(existing, "__k4s_bootstrap__", None) != (K4S_BOOTSTRAP_RELEASE, path, sha256, size):
            raise SystemExit("k4s bootstrap refused: a different end_prep_common module is already loaded (want %s %s)"
                             % (path, sha256))
        return existing
    return k4s_bootstrap_load(path, sha256, size, "end_prep_common", SystemExit)


C = _k4s_common()
S10 = C.load_sibling("s10_stage_host", *K4S_SIBLING_PINS["s10_stage_host.py"])
S9 = S10.S9

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-host-repository.v1"
HOSTS = S10.HOSTS
END_BASES = dict(si.END_BASES)
BRANCH = S9.END_BRANCH                                               # k4s-end-r1 (BR-1)
BRANCH_REF = S9.END_BRANCH_REF                                       # its remote-tracking ref in REPO_FULL
# frozen fleet_end.artifact: `git merge-base --is-ancestor <A1 end-sources commit> HEAD` (fleet_end.py:30-33);
# X' 022ec7bf on k4s-end-r1 (runner PROGRESS 04:56Z; BR-1 COORDINATOR 7f93dbbf).
REQUIRED_ANCESTOR = "022ec7bf298caaab81bc6e70fe917d3e75b21bde"
REPOSITORY_LEAF, PARTIAL_LEAF = "repository", "repository.partial"
TRANSFER_PREFIX = "repository-transfer-"
BUNDLE_NAME = "k4s-end-r1.bundle"
STUDY_REL = "reports/explore/k4s-confirm"
CORE_KEYS = ("core.bare", "core.filemode", "core.logallrefupdates", "core.repositoryformatversion")
REMOTE_PYTHON = si.REMOTE_PYTHON                                     # /usr/bin/python3 (3.8), as safe_input's programs
SSH_BINARY = si.SSH_BINARY
RECORD_NAMES = ("s11-provision.json", "s11-advance.json")
BUNDLE_HEADER = b"# v2 git bundle\n"
OID = re.compile(r"[0-9a-f]{40}")
# The fixed in-argv loader of the host program: it decodes the program, refuses (exit 4) unless its SHA-256 is the
# argv commitment, then executes exactly those bytes. No single quote inside (it sits in a single-quoted shell word).
HOST_BOOTSTRAP = ('import base64,hashlib,sys;b=base64.b64decode(sys.argv[1]);'
                  'hashlib.sha256(b).hexdigest()==sys.argv[2] or sys.exit(4);'
                  'sys.argv=sys.argv[2:];exec(compile(b,"<k4s-s11-host>","exec"))')

# The host program's main (Python 3.8 stdlib + safe_input + the host tool, both loaded from <base>/tools through the
# canonical bootstrap with the S7 pins); composed after the canonical block taken from THIS file's own verified bytes.
HOST_MAIN = r'''
import base64 as _b64, ctypes as _ctypes, errno as _errno, hashlib, json as _json, os as _os, stat as _stat, sys as _sys
import tempfile as _tempfile


class _Refused(Exception):
    def __init__(self, code, reason=None):
        if reason is None:
            code, reason = "bootstrap", code
        Exception.__init__(self, "%s: %s" % (code, reason))
        self.code, self.reason = code, reason


def _require(condition, code, reason):
    if not condition:
        raise _Refused(code, reason)


def _out(tag, obj):
    _sys.stdout.write("@@%s %s\n" % (tag, _json.dumps(obj, sort_keys=True)))
    _sys.stdout.flush()


def _layers(p):
    si = k4s_bootstrap_load(p["tools"] + "/safe_input.py", p["safe_input_sha256"], p["safe_input_size"], "safe_input",
                            _Refused)
    _require(si.constants_fingerprint() == p["safe_input_fingerprint"], "pins", "safe_input fingerprint differs")
    tool = k4s_bootstrap_load(p["tools"] + "/k4s_end_host_tool.py", p["host_tool_sha256"], p["host_tool_size"],
                              "k4s_end_host_tool", _Refused)
    tool.check_safe_input(si)
    return si, tool


def _policy(si, p):
    names = (p["repository_leaf"], p["partial_leaf"], p["transfer_leaf"], "tools")
    return si.Policy(p["host"], [
        si.Role("base", p["base"], "read", 1, exact=names),
        si.Role("base-w", p["base"], "write", 1, exact=(p["partial_leaf"],)),
        si.Role("transfer", p["base"] + "/" + p["transfer_leaf"], "read", p["bundle_size"], exact=(p["bundle_name"],))])


def _git(si, path, args, ok_rcs=(0,), protocols=()):
    return si.git_run(si.GitRepo(work_tree=path, protocols=protocols), args, timeout=3600, ok_rcs=ok_rcs)


def _text(si, path, args):
    return _git(si, path, args).stdout.decode("utf-8", "replace")


def _gw_refuse(reason):
    return _Refused("git-write", reason)


def _git_w(si, path, args, protocols=()):
    """r5: the WRITING git commands (fetch, checkout): exactly si.git_run's static preflight, argv flags and
    environment (fixed env, fresh empty HOME), plus the write-reducing GW_CONFIG, which si.git_run cannot pass
    (its first argument must be the subcommand)."""
    _require(args and args[0] in ("fetch", "checkout"), "argv", "not a writing git command: %r" % (args[:1],))
    repo = si.GitRepo(work_tree=path, protocols=protocols)
    si._git_preflight(repo)
    argv = [si.GIT_BINARY] + list(si.GIT_GLOBAL_ARGS) + list(GW_CONFIG)
    for proto in repo.protocols:
        argv += ["-c", "protocol.%s.allow=always" % proto]
    argv += ["--git-dir=" + repo.git_dir, "--work-tree=" + path] + list(args)
    env = dict(si.GIT_FIXED_ENV)
    home = _tempfile.mkdtemp(prefix="k4s-s11-git-home-")
    env["HOME"], env["XDG_CONFIG_HOME"] = home, home + "/xdg-config-absent"
    try:
        return si.run_checked(argv, 3600, 64 << 20, env=env, cwd=path)
    finally:
        _os.rmdir(home)                                           # fails (refusal) if git wrote into it


def _guarded(si, path, plan, args, protocols=()):
    """gw_scan BEFORE the command (refuses with nothing written), the command, gw_post after (detection only)."""
    before = gw_scan(path, plan, _gw_refuse)
    _git_w(si, path, args, protocols)
    return gw_summary(gw_post(path, plan, before, _gw_refuse))


def _verify(si, tool, p, path, commit):
    rec = tool.verify_clone(si, p["host"], path, role="repository")
    head = _text(si, path, ["rev-parse", "HEAD"]).strip()
    _require(head == commit, "check", "%s HEAD is %s, not %s" % (path, head, commit))
    symbolic = _text(si, path, ["rev-parse", "--symbolic-full-name", "HEAD"]).strip()
    _require(symbolic == "refs/heads/" + p["branch"], "check", "%s HEAD is not on %s: %r" % (path, p["branch"], symbolic))
    refs = _text(si, path, ["for-each-ref", "--format=%(objectname) %(refname)"]).splitlines()
    _require(refs == ["%s refs/heads/%s" % (commit, p["branch"])], "check", "%s refs differ: %r" % (path, refs[:4]))
    _require(_text(si, path, ["rev-parse", "--is-shallow-repository"]) == "false\n", "check", "%s is shallow" % path)
    _require(_text(si, path, ["status", "--porcelain", "--untracked-files=all"]) == "", "check",
             "%s work tree is not clean (a claim or stray file exists)" % path)
    _require(_git(si, path, ["merge-base", "--is-ancestor", p["required_ancestor"], "HEAD"], ok_rcs=(0, 1)).rc == 0,
             "check", "%s is not a descendant of %s" % (head, p["required_ancestor"]))
    absent = ("hooks", "shallow", "objects/info/alternates", "objects/info/http-alternates", "info/grafts", "commondir",
              "config.worktree")
    pol = si.Policy(p["host"], [si.Role("repo-git", path + "/.git", "read", 1 << 16, exact=("config",) + absent),
                                si.Role("repo-tree", path, "read", 1, exact=(p["study"],))])
    config = si.read_bytes(pol, "repo-git", "config", max_size=1 << 16).decode("utf-8", "replace")
    keys, section = [], None
    for line in config.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            section = line.strip("[]").strip().casefold()
            continue
        keys.append("%s.%s" % (section, line.split("=", 1)[0].strip().casefold()))
    _require(sorted(keys) == sorted(p["core_keys"]), "check", "%s config is not the plain init config: %r"
             % (path, keys))
    for rel in absent:
        try:
            si.check_absent(pol, "repo-git", rel)
        except si.Refusal as error:
            if error.code != "missing":
                raise
    root, study = si.check_dir(pol, "repo-tree"), si.check_dir(pol, "repo-tree", p["study"])
    _require(root["mode"] & 0o200 and study["mode"] & 0o200, "check", "%s work tree is not owner-writable" % path)
    return dict(verify_clone=rec, head=head, symbolic_head=symbolic, refs=refs, shallow=False, clean=True,
                config_keys=sorted(keys), required_ancestor=p["required_ancestor"], writable=True,
                root_dev=root["dev"], root_ino=root["ino"])


def _end_job(si, p, path, rev):
    """END-JOB.json of `rev`: its blob OID must be X's tree entry on 05 (metadata) and, with end_job_sha256, its bytes
    that SHA-256: through git (si.git_show_file, expected SHA) for the commit, through the descriptor gate for HEAD's
    work-tree file (exact-name END grants)."""
    oid = _text(si, path, ["rev-parse", "%s:%s" % (rev, p["end_job_rel"])]).strip()
    _require(oid == p["end_job_oid"], "check", "END-JOB.json at %s is blob %s, not %s" % (rev, oid, p["end_job_oid"]))
    out = dict(rev=rev, oid=oid)
    if p["end_job_sha256"]:
        pol = si.Policy(p["host"], [si.Role("end-job", path, "read", 1 << 20, exact=(p["end_job_rel"],),
                                            grants=("end-json-exact", "end-claim-exact"))])
        if rev == "HEAD":
            got = si.sha256_input(pol, "end-job", p["end_job_rel"])["sha256"]
        else:
            data = si.git_show_file(pol, "end-job", si.GitRepo(work_tree=path), rev, p["end_job_rel"], 1 << 20,
                                    expected_sha256=p["end_job_sha256"])
            got = hashlib.sha256(data).hexdigest()
        _require(got == p["end_job_sha256"], "check", "END-JOB.json bytes at %s are not the pinned SHA-256" % rev)
        out["sha256"] = got
    return out


def _publish(si, base, partial, final):
    fd = si.open_root(base)
    try:
        st = _os.stat(partial, dir_fd=fd, follow_symlinks=False)
        _require(_stat.S_ISDIR(st.st_mode), "not-dir", "%s is not a real directory" % partial)
        fn = _ctypes.CDLL(None, use_errno=True).renameat2
        fn.argtypes = (_ctypes.c_int, _ctypes.c_char_p, _ctypes.c_int, _ctypes.c_char_p, _ctypes.c_uint)
        fn.restype = _ctypes.c_int
        if fn(fd, partial.encode(), fd, final.encode(), 1) != 0:          # RENAME_NOREPLACE
            err = _ctypes.get_errno()
            raise _Refused("exists" if err == _errno.EEXIST else "rename", "%s -> %s: %s"
                           % (partial, final, _os.strerror(err)))
        _os.fsync(fd)
    finally:
        _os.close(fd)


def _main(argv):
    mode, p = argv[1], _json.loads(_b64.b64decode(argv[2]).decode("utf-8"))
    _require(mode in ("check", "provision", "advance") and p["mode"] in ("provision", "advance")
             and (mode == "check" or mode == p["mode"]), "argv", "bad mode %r" % mode)
    node = _os.uname().nodename.split(".")[0]
    _require(node == p["host"], "host", "this is %s, not %s" % (node, p["host"]))
    si, tool = _layers(p)
    pol = _policy(si, p)
    si.check_dir(pol, "base")
    base = p["base"]
    final, partial = base + "/" + p["repository_leaf"], base + "/" + p["partial_leaf"]
    if mode == "check":
        git = si.run_checked([si.GIT_BINARY, "--version"], 60, 4096, env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"})
        si.check_absent(pol, "base", p["transfer_leaf"])
        si.check_absent(pol, "base", p["partial_leaf"])
        facts = dict(mode="check", host=node, git_version=git.stdout.decode("utf-8", "replace").strip(),
                     python=_sys.version.split()[0], safe_input_sha256=p["safe_input_sha256"],
                     host_tool_sha256=p["host_tool_sha256"])
        if p["mode"] == "provision":
            si.check_absent(pol, "base", p["repository_leaf"])
        else:
            si.check_dir(pol, "base", p["repository_leaf"])
            facts["before"] = _verify(si, tool, p, final, p["prior"])
        _out("CHECK", facts)
        return 0
    got = si.sha256_input(pol, "transfer", p["bundle_name"], expected_size=p["bundle_size"])
    _require(got["sha256"] == p["bundle_sha256"], "sha", "the received bundle is not the pinned bundle")
    bundle = base + "/" + p["transfer_leaf"] + "/" + p["bundle_name"]
    result = dict(mode=mode, host=node, commit=p["commit"], bundle_sha256=got["sha256"], bundle=bundle)
    if mode == "provision":
        writer = si.Writer(pol, "base-w")
        try:
            writer.mkdir_excl(p["partial_leaf"])
        finally:
            writer.close()
        _git(si, partial, ["init", "-q", "--template="])
        plan = gw_plan("refs/heads/" + p["branch"], worktree_only=(".git",))      # r5: a fresh work tree root
        result["git_write_guard"] = dict(
            fetch=_guarded(si, partial, plan, ["fetch"] + list(GW_FETCH_FLAGS) + [
                bundle, "%s:refs/heads/%s" % (p["bundle_ref"], p["branch"])], protocols=("file",)),
            checkout=_guarded(si, partial, plan, ["checkout", "-q", p["branch"]]), config=list(GW_CONFIG))
        result["partial"] = _verify(si, tool, p, partial, p["commit"])
        _publish(si, base, p["partial_leaf"], p["repository_leaf"])
        result["final"] = _verify(si, tool, p, final, p["commit"])
    else:
        result["before"] = _verify(si, tool, p, final, p["prior"])
        ref = "refs/heads/" + p["branch"]
        guard = dict(fetch=_guarded(si, final, gw_plan(ref), ["fetch"] + list(GW_FETCH_FLAGS) + [
            bundle, p["bundle_ref"]], protocols=("file",)), config=list(GW_CONFIG))
        _git(si, final, ["cat-file", "-e", p["commit"] + "^{commit}"])
        _require(p["prior"] != p["commit"] and _git(si, final, ["merge-base", "--is-ancestor", p["prior"],
                                                                 p["commit"]], ok_rcs=(0, 1)).rc == 0,
                 "check", "X is not a strict descendant of the provisioned commit (fast-forward only)")
        result["end_job_committed"] = _end_job(si, p, final, p["commit"])     # BEFORE the work tree moves
        raw = _git(si, final, ["diff-tree", "-r", "-z", "--no-renames", "--name-only", p["prior"], p["commit"]]).stdout
        paths = sorted(x for x in raw.decode("utf-8", "surrogateescape").split("\x00") if x)
        _require(paths == [p["end_job_rel"]], "check", "the checkout P' -> X would write %r, not exactly %s"
                 % (paths[:4], p["end_job_rel"]))
        guard["checkout"] = _guarded(si, final, gw_plan(ref, worktree=paths), ["checkout", "-q", "-B", p["branch"],
                                                                                p["commit"]])
        result["git_write_guard"] = guard
        result["final"] = _verify(si, tool, p, final, p["commit"])
        result["end_job"] = _end_job(si, p, final, "HEAD")
    _out("RESULT", result)
    return 0


try:
    _rc = _main(_sys.argv)
except BaseException as _error:                                   # every refusal (and anything else) is reported
    _code = getattr(_error, "code", None)
    _out("REFUSED", dict(code=_code if isinstance(_code, str) and len(_code) < 40 else type(_error).__name__,
                         reason=str(getattr(_error, "reason", _error))[:4000], type=type(_error).__name__))
    _rc = 3
_sys.stdout.flush()
_os._exit(_rc)
'''


# ---------------------------------------------------------------- local (05) side

def canonical_block(policy):
    """The canonical bootstrap block, exactly as it sits in THIS file's verified bytes (code role, read by SHA)."""
    text = si.read_bytes(policy, "code", "s11_host_repository.py", max_size=1 << 20).decode("utf-8")
    mark = "K4S CANONICAL " + "BOOTSTRAP r1"                      # split: this file holds exactly one block
    begin, end = "# ==== BEGIN " + mark + " ", "# ==== END " + mark + " ====\n"
    i, j = text.find(begin), text.find(end)
    require(i >= 0 and j > i and text.count(begin) == 1 and text.count(end) == 1, "check", "canonical block not found")
    return text[i:j + len(end)]


def host_program(policy):
    """The canonical block (from this file's verified bytes), then S9's git write guard source (r5: the same text S9
    refresh-clone executes), then HOST_MAIN."""
    data = (canonical_block(policy) + S9.GIT_WRITE_GUARD + HOST_MAIN).encode("utf-8")
    return data, C.sha_bytes(data)


def git_bundle_argv(*args):
    """`git bundle` (create / list-heads) on REPO_FULL: the THIRD git call outside si.git_run (whose subcommand
    allowlist has no `bundle`), with the same fixed P2-4 flags and environment as prepare-clone; read-only on the clone
    (writes only the bundle file under a fresh private /tmp directory)."""
    return [si.GIT_BINARY, "--no-replace-objects", "--no-optional-locks", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-c", "protocol.allow=never", "--git-dir=" + S9.REPO_FULL + "/.git",
            "bundle"] + list(args)


def parse_bundle_header(data):
    """A v2 bundle header, strictly: (prerequisites [oid], refs [(oid, name)])."""
    require(data.startswith(BUNDLE_HEADER), "check", "not a v2 git bundle")
    end = data.find(b"\n\n")
    require(end > 0, "check", "bundle header not terminated")
    prereqs, refs = [], []
    for line in data[len(BUNDLE_HEADER):end].decode("utf-8", "replace").split("\n"):
        if line.startswith("-"):
            oid = line[1:].split(" ", 1)[0]
            require(OID.fullmatch(oid) is not None, "check", "bad bundle prerequisite %r" % line[:80])
            prereqs.append(oid)
        else:
            oid, _, name = line.partition(" ")
            require(OID.fullmatch(oid) is not None and name, "check", "bad bundle ref line %r" % line[:80])
            refs.append((oid, name))
    return prereqs, refs


def make_bundle(workdir, commit, prior=None):
    """The bundle of BRANCH_REF (complete, or with exactly the prerequisite `prior`), checked: its header names exactly
    BRANCH_REF at `commit` and exactly the expected prerequisites; `git bundle list-heads` agrees. Returns its facts."""
    path = workdir + "/" + BUNDLE_NAME
    spec = BRANCH_REF if prior is None else "%s..%s" % (prior, BRANCH_REF)
    with C.ScrubbedEnv() as env:
        si.run_checked(git_bundle_argv("create", path, spec), 3600, 1 << 20, env=env, cwd=S9.REPO_FULL)
        heads = si.run_checked(git_bundle_argv("list-heads", path), 600, 1 << 20, env=env, cwd=S9.REPO_FULL).stdout
    require(heads == ("%s %s\n" % (commit, BRANCH_REF)).encode(), "check", "bundle heads %r are not exactly %s at %s"
            % (heads[:200], BRANCH_REF, commit[:12]))
    policy = si.Policy(C.local_host(), [si.Role("bundle", workdir, "read", 8 << 30, exact=(BUNDLE_NAME,))])
    got = si.sha256_input(policy, "bundle", BUNDLE_NAME)
    head = si.read_bytes(policy, "bundle", BUNDLE_NAME, expected_size=got["size"], max_size=8 << 30)[:1 << 16]
    prereqs, refs = parse_bundle_header(head)
    require(refs == [(commit, BRANCH_REF)], "check", "bundle refs differ: %r" % refs[:4])
    require(prereqs == ([] if prior is None else [prior]), "check", "bundle prerequisites %r are not %r"
            % (prereqs[:4], [] if prior is None else [prior]))
    return dict(path=path, size=got["size"], sha256=got["sha256"], refs=refs, prerequisites=prereqs, spec=spec)


def tip(g):
    return S9.ref_table(g).get(BRANCH_REF)


def params(mode, host, commit, bundle, prior=None, end_job=None):
    base = END_BASES[host]
    return dict(mode=mode, host=host, base=base, commit=commit, prior=prior, branch=BRANCH, bundle_ref=BRANCH_REF,
                repository_leaf=REPOSITORY_LEAF, partial_leaf=PARTIAL_LEAF,
                transfer_leaf=TRANSFER_PREFIX + commit[:12], bundle_name=BUNDLE_NAME, bundle_sha256=bundle["sha256"],
                bundle_size=bundle["size"], tools=S10.roots(host)["tools"],
                safe_input_sha256=S10.TOOL_PINS["safe_input.py"][1], safe_input_size=S10.TOOL_PINS["safe_input.py"][2],
                safe_input_fingerprint=C.SAFE_INPUT_FINGERPRINT,
                host_tool_sha256=S10.TOOL_PINS["k4s_end_host_tool.py"][1],
                host_tool_size=S10.TOOL_PINS["k4s_end_host_tool.py"][2], required_ancestor=REQUIRED_ANCESTOR,
                study=STUDY_REL, core_keys=list(CORE_KEYS), end_job_rel=S9.END_JOB_REL,
                end_job_oid=(end_job or {}).get("oid"), end_job_sha256=(end_job or {}).get("sha256"))


def host_words(program_sha, program_b64, mode, params_b64):
    q = shlex.quote
    return "%s -n 19 %s -I -S -c %s %s %s %s %s" % (S10.REMOTE_TOOLS["nice"], REMOTE_PYTHON, q(HOST_BOOTSTRAP),
                                                   program_b64, program_sha, mode, params_b64)


def session_script(program, p, receive_manifest):
    """ONE login: [check] (reads no stdin) -> [receive] (D4; consumes the whole stdin) -> [provision|advance]."""
    program_b64 = base64.b64encode(program[0]).decode("ascii")
    params_b64 = base64.b64encode(C.canonical(p).encode()).decode("ascii")
    receive = si.receive_ssh_argv(p["host"], si.receive_program_source().encode(), receive_manifest)
    receive_words = " ".join(receive[receive.index("--") + 2:])
    lines = ["export LC_ALL=C", "cd / || exit 9",
             host_words(program[1], program_b64, "check", params_b64) + " </dev/null", "rc=$?",
             'echo "@@RC|check|$rc"', '[ "$rc" = 0 ] || exit 10',
             receive_words, "rc=$?", 'echo "@@RC|receive|$rc"', '[ "$rc" = 0 ] || exit 11',
             host_words(program[1], program_b64, p["mode"], params_b64) + " </dev/null", "rc=$?",
             'echo "@@RC|%s|$rc"' % p["mode"], '[ "$rc" = 0 ] || exit 12', "echo @@DONE"]
    return "\n".join(lines)


def stream(program_bytes, manifest, policy, files):
    """The D4 receive stream (safe_input's framing: program, 8-byte manifest length, manifest, file bytes), every
    source read through the descriptor gate and re-hashed while streaming."""
    yield program_bytes
    yield len(manifest).to_bytes(8, "big")
    yield manifest
    for f in files:
        item = si.open_input(policy, f["src_role"], f["src_rel"], expected_size=f["size"])
        sink = hashlib.sha256()
        try:
            for chunk in item.chunks():
                sink.update(chunk)
                yield chunk
        finally:
            item.close()
        require(sink.hexdigest() == f["sha256"], "sha", "local bundle changed while streaming")


def parse_session(stdout, rc, p, manifest):
    """Strict parse of the one session: every stage status 0, the CHECK and RESULT records of the SHA-bound host
    program, and the D4 receipt (si.parse_receive_receipt) between them. Any refusal names its stage."""
    lines = stdout.decode("utf-8", "replace").split("\n")
    rcs = [line for line in lines if line.startswith("@@RC|")]
    refused = [line for line in lines if line.startswith("@@REFUSED ")]
    stages = ["check", "receive", p["mode"]]
    want = ["@@RC|%s|0" % s for s in stages]
    if rc != 0 or rcs != want or lines[-2:] != ["@@DONE", ""]:
        detail = refused[0][len("@@REFUSED "):] if refused else ""
        si.refuse("remote-refused", "S11 host session stopped (rc %s, stages %r) %s" % (rc, rcs, detail[:2000]))
    checks = [l for l in lines if l.startswith("@@CHECK ")]
    results = [l for l in lines if l.startswith("@@RESULT ")]
    require(len(checks) == 1 and len(results) == 1, "remote", "S11 host records missing or repeated")
    i, j = lines.index(want[0]), lines.index(want[1])
    receipt_lines = [l for l in lines[i + 1:j] if l]
    require(len(receipt_lines) == 1, "remote", "D4 receipt is not exactly one line")
    receipt = si.parse_receive_receipt(manifest, 0, (receipt_lines[0] + "\n").encode())
    check = si.loads_strict(checks[0][len("@@CHECK "):].encode(), "S11 check")
    result = si.loads_strict(results[0][len("@@RESULT "):].encode(), "S11 result")
    require(isinstance(result, dict) and result.get("mode") == p["mode"] and result.get("commit") == p["commit"]
            and result.get("host") == p["host"] and result.get("bundle_sha256") == p["bundle_sha256"]
            and (result.get("final") or {}).get("head") == p["commit"], "remote", "S11 result differs from the request")
    return check, receipt, result


def local_policy(extra=()):
    return si.Policy(C.local_host(), [C.code_role()] + list(extra))


def run(a, log=print):
    started = C.utc()
    mode = a.command
    record = None if a.dry_run else C.Record(a.record, "S11", RECORD_NAMES).open()   # first: receipts need a home
    logins, attempted, workdir = [], [], None
    try:
        require(a.host in HOSTS, "policy", "--host must be 127x03 or 127x04")
        if not a.dry_run:
            require(bool(a.outside_end_window), "policy",
                    "live run requires --outside-end-window '<coordinator GO / window reference>'")
        commit = S9.full_commit(a.commit, "--commit")
        prior = S9.full_commit(a.prior, "--from") if mode == "advance" else None
        extra, equivalence, end_job = [], None, None
        if mode == "advance":
            require(bool(a.equivalence_record) and C.is_sha256(a.equivalence_sha256), "policy",
                    "advance needs --equivalence-record and --equivalence-sha256 (S9 equivalence passed first)")
            parent, leaf = C.input_dir(a.equivalence_record, "--equivalence-record").rsplit("/", 1)
            extra.append(si.Role("equivalence", parent, "read", 1 << 20, exact=(leaf,)))
        policy = local_policy(extra=extra)
        clone = S9.require_full_clone((commit,) + ((prior,) if prior else ()))   # F4: live, before anything else
        g = S9.repo()
        require(tip(g) == commit, "check", "%s is %s, not --commit %s (provision P', advance X: run S9 refresh-clone)"
                % (BRANCH_REF, tip(g), commit))
        require(S9.is_ancestor(g, REQUIRED_ANCESTOR, commit), "check", "--commit is not a descendant of %s"
                % REQUIRED_ANCESTOR[:12])
        if mode == "advance":
            require(prior != commit and S9.is_ancestor(g, prior, commit), "check",
                    "X is not a strict descendant of --from P' (fast-forward only)")
            equivalence = si.read_json(policy, "equivalence", leaf, 1 << 20, expected_sha256=a.equivalence_sha256)
            require(isinstance(equivalence, dict) and equivalence.get("schema") == S9.EQUIV_SCHEMA
                    and equivalence.get("runtime_commit") == prior and equivalence.get("end_job_commit") == commit
                    and equivalence.get("diff") == [S9.END_JOB_REL]
                    and equivalence.get("runtime_files_identical") is True
                    and equivalence.get("measurement_files_identical") is True, "check",
                    "the S9 equivalence record is not a pass for %s -> %s" % (prior[:12], commit[:12]))
            entries = [e for e in si.git_ls_tree(g, commit) if e["path"] == S9.END_JOB_REL]   # metadata only
            require(len(entries) == 1 and entries[0]["type"] == "blob", "check", "X has no END-JOB.json blob")
            end_job = dict(oid=entries[0]["oid"], sha256=C.need_sha256(a.end_job_sha256, "--end-job-sha256")
                           if a.end_job_sha256 else None)
        program = host_program(policy)
        workdir = tempfile.mkdtemp(prefix="k4s-s11-bundle-", dir="/tmp")
        bundle = make_bundle(workdir, commit, prior)
        p = params(mode, a.host, commit, bundle, prior, end_job)
        src = si.Policy(C.local_host(), [si.Role("bundle", workdir, "read", 8 << 30, exact=(BUNDLE_NAME,))])
        files = [dict(src_role="bundle", src_rel=BUNDLE_NAME, dst=BUNDLE_NAME, size=bundle["size"],
                      sha256=bundle["sha256"], mode=0o444, e4=False)]
        dest = si.Policy(a.host, [si.Role("dest", p["base"] + "/" + p["transfer_leaf"], "write", si.MAX_ROLE_SIZE,
                                          patterns=("**",))], remote=True)
        manifest = si.build_receive_manifest(dest, "dest", [], files, bundle["size"])
        si.open_input(src, "bundle", BUNDLE_NAME, expected_size=bundle["size"]).close()   # gate before ssh starts
        script = session_script(program, p, manifest)
        argv = S10.ssh_script_argv(a.host, script)
        require(len(argv[-1]) < 120 * 1024, "policy", "the session command is too long for one remote word")
        summary = dict(mode=mode, host=a.host, commit=commit, prior=prior, bundle=dict(bundle, path=None),
                       host_program_sha256=program[1], receive_program_sha256=si.receive_program_sha256(),
                       transfer=p["base"] + "/" + p["transfer_leaf"], target=p["base"] + "/" + REPOSITORY_LEAF,
                       logins_planned=1)
        if a.dry_run:
            log(json.dumps(dict(summary, dry_run=True), indent=1, sort_keys=True))
            log("# session (one login): " + " ".join(argv[:-1]) + " <script %d bytes>" % len(argv[-1]))
            return summary
        logins.append(dict(label="session-" + mode, host=a.host, utc=C.utc(), script_sha256=C.sha_bytes(script.encode())))
        attempted += [p["base"] + "/" + p["transfer_leaf"]] + ([p["base"] + "/" + PARTIAL_LEAF] if mode == "provision"
                                                               else [p["base"] + "/" + REPOSITORY_LEAF])
        log("[%s] ssh session-%s %s" % (C.utc(), mode, a.host))
        result = si.run_checked(argv, 6 * 3600, 8 << 20, env={"LC_ALL": "C"}, ok_rcs=(0, 9, 10, 11, 12, 255),
                                stdin_bytes=stream(si.receive_program_source().encode(), manifest, src, files),
                                stdin_break_ok_on_nonzero=True)
        check, receipt, host_result = parse_session(result.stdout, result.rc, p, manifest)
        doc = dict(summary, schema=SCHEMA, status=mode + "d" if mode == "advance" else "provisioned",
                   started_utc=started, finished_utc=C.utc(), outside_end_window=a.outside_end_window,
                   ssh_logins=len(logins), logins=logins, full_clone=clone, equivalence=equivalence,
                   equivalence_sha256=a.equivalence_sha256 if mode == "advance" else None, end_job=end_job,
                   check=check, receive_receipt_sha256=C.canonical_sha(receipt), result=host_result,
                   host_paths_kept_needing_authorized_cleanup=[p["base"] + "/" + p["transfer_leaf"]],
                   params=p, script_sha256=C.code_sha(policy, "s11_host_repository.py"),
                   s10_sha256=C.code_sha(policy, "s10_stage_host.py"), s9_sha256=C.code_sha(policy, "s9_end_runtime.py"),
                   common_sha256=C.code_sha(policy, "end_prep_common.py"), safe_input_sha256=C.SAFE_INPUT_SHA256)
        sha = record.write("s11-%s.json" % mode, doc)
        log("S11 OK: %s %s at %s on %s (record %s/s11-%s.json sha256 %s)" % (
            mode, p["base"] + "/" + REPOSITORY_LEAF, commit[:12], a.host, a.record, mode, sha))
        return doc
    except BaseException as error:
        if record is not None:
            record.refusal(error, {"logins": logins, "started_utc": started,
                                   "host_paths_created_or_attempted_needing_authorized_cleanup": attempted})
        raise
    finally:
        if record is not None:
            record.close()
        if workdir is not None:
            for name in os.listdir(workdir):                            # our own private /tmp bundle only
                os.unlink(os.path.join(workdir, name))
            os.rmdir(workdir)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command")
    for name in ("provision", "advance"):
        sp = sub.add_parser(name, allow_abbrev=False)
        sp.add_argument("--host", required=True, choices=HOSTS)
        sp.add_argument("--commit", required=True, help="provision: P'; advance: X (tip of k4s-end-r1 in REPO_FULL)")
        sp.add_argument("--record", help="new local directory for the record (live run)")
        sp.add_argument("--outside-end-window", default="")
        sp.add_argument("--dry-run", action="store_true")
        if name == "advance":
            sp.add_argument("--from", dest="prior", required=True, help="P': the provisioned commit")
            sp.add_argument("--equivalence-record", required=True, help="the S9 equivalence record (s9-equivalence.json)")
            sp.add_argument("--equivalence-sha256", required=True)
            sp.add_argument("--end-job-sha256", help="also verify END-JOB.json bytes on the host (recommended)")
    a = ap.parse_args(argv)
    if a.command is None:
        ap.print_usage(sys.stderr)
        return 2
    for key in ("prior", "equivalence_record", "equivalence_sha256", "end_job_sha256"):
        if not hasattr(a, key):
            setattr(a, key, None)
    if not a.dry_run and not a.record:
        ap.error("--record is required unless --dry-run")
    try:
        run(a)
    except si.Refusal as error:
        print("S11 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print("S11 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
