"""K4S END-JOB builder, 05 only (candidate r5; INTEGRATION-AUDIT-r1 U8; plan v2 A6). Sol review before any use.

Never reads outcomes: every repository byte is a named health-only blob read through safe_input's gated git reader
(git_show_file: name gate, one regular blob, object hash checked) from the 05 full clone REPO_FULL (read only).

  build       --declared-by TEXT --out NEW_DIR
      Reads at the END evidence commit P' (EVIDENCE_COMMIT, branch k4s-end-r1): end-evidence.json (its SHA-256 must be
      the evidence of record), the K4S manifest of record (74314eda), and the evidence's plan and completion items
      (each at its own committed path and commit, an ancestor of P', with its pinned SHA; the completion must be the
      completion of record 3794d953 and name exactly the counted hosts 127x03/127x04). R6: the END namespace
      reports/explore/k4s-confirm/end/ must be absent at P'. Writes NEW_DIR/END-JOB.json with exactly the frozen
      JOB_FIELDS (end_evidence.py:306-307) and NEW_DIR/BUILD.json (sources and SHAs), both exclusively, and prints
      the END-JOB SHA-256. declared_utc is the 05 clock at build time; declared_by is the caller's text.
  self-check  --out DIR --job-sha256 S
      On a /dev/shm scratch copy of REPO_FULL/.git ONLY (no work tree is copied; nothing outside scratch is written):
      commit the END-JOB alone on P' (X), require diff-tree P' X == [END-JOB path]; materialize only the evidence
      and its artifacts (git show of their committed blobs) and run the FROZEN end_evidence.end_evidence + end_job
      (the S9 runtime's own files, pinned) against the scratch clone at X; then run the ADOPTED S9 (s3s9s10-r6,
      pinned) `equivalence` with REPO_FULL pointed at the scratch clone. r5 (SOL-REVIEW-END-INTEGRATION-r1 finding 1):
      the S9 code and the PRODUCTION runtime manifest are pinned from the S9-FINAL / RUNTIME-r6-READY markers
      (record: ADOPTED-S9-RUNTIME.json), and the manifest must name that S9 as its builder (script_sha256), P' as its
      commit, REPO_FULL as its repository and FROZEN_PYTHON as its frozen interpreter. Writes DIR/SELF-CHECK.json exclusively; the scratch
      directory is removed in every case.

The real commit (A6) is a coordinator step: copy END-JOB.json byte for byte to reports/explore/k4s-confirm/end/
END-JOB.json, `git add` exactly that path, commit it ALONE on k4s-end-r1 (parent P'), and check `git diff-tree` P' X.
Exit codes: 0 ok; 2 refused.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
SAFE_INPUT_SIZE = 133606


class JobRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise JobRefusal(message)


# ---------------------------------------------------------------- pinned layer
# safe_input is read ONLY through the canonical bootstrap r1 below (bootstrap-r1/k4s_bootstrap_r1.py, verbatim).
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


RUNNER = "/mpac/sdicks02/k4s-runner/run-r1"
REPO_FULL = RUNNER + "/end-prep/repo-full"                                  # S9 REPO_FULL (read only)
EVIDENCE_COMMIT = "98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb"                       # P' (k4s-end-r1)
STUDY_DIR = "reports/explore/k4s-confirm"
END_DIR = STUDY_DIR + "/end"
END_JOB_REL = END_DIR + "/END-JOB.json"                                    # frozen end_evidence.END_JOB_PATH
END_EVIDENCE_REL = STUDY_DIR + "/end-evidence.json"                         # S2 output path at P'
END_EVIDENCE_SHA256 = "2ab14a3e3f15d41ff80bef31a0a529eddc78a05e61f42bce1e4bfbc4de50a3fd"
K4S_MANIFEST_REL = STUDY_DIR + "/mac/K4S-MAC-MANIFEST.json"
K4S_MANIFEST_SHA256 = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
COMPLETION_SHA256 = "3794d953efb2c8af47a09ccb086cc0441f1c0dd9ea7a4f46e331315972c6e891"  # plan v2 A6 completion of record
COUNTED_HOSTS = ["127x03", "127x04"]                                        # plan v2 A6
EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
JOB_SCHEMA = "clasher.k4s.end-job.v1"
STUDY = "PREREG-K4S"
JOB_FIELDS = ("completion_sha256", "counted_hosts", "declared_by", "declared_utc", "end_evidence_sha256",
              "k4s_manifest_sha256", "plan_sha256", "schema", "study")   # = frozen end_evidence.JOB_FIELDS (tested)
BUILD_SCHEMA = "clasher.k4s.end-job-build.v1"
SELF_CHECK_SCHEMA = "clasher.k4s.end-job-self-check.v1"
END_GRANTS = ("end-json-exact", "end-claim-exact")
COMMIT = re.compile(r"[0-9a-f]{40}")
DECLARED_BY = re.compile(r"[ -~]{1,200}")
# self-check inputs (read only, pinned): the S9 runtime built at P' and the frozen files the drivers import.
# r5 (finding 1): S9_PATH/S9_SHA256 and FROZEN_RUNTIME/FROZEN_RUNTIME_MANIFEST_SHA256 are written by
# tests/adopt_pins.py from the S9-FINAL and RUNTIME-r6-READY markers (computed, never typed; record
# ADOPTED-S9-RUNTIME.json, tied to these constants by tests/test_r5.py).
FROZEN_RUNTIME = RUNNER + "/end-staging/runtime-98566c032d0b"
FROZEN_RUNTIME_MANIFEST_SHA256 = "9d6ab1f7386894727035c14a95c518b54e9472c9cb90eb6d023c589fe2269b43"
E4V3 = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
FROZEN_PINS = {                                                             # = k4s_end_preflight.FROZEN_CLOSURE
    'reports/explore/k4s-confirm/end_evidence.py': '6337e4bc2dbfeaf8a5303ac107e0e74174643aa88898dbdf610365dea131c61e',
    'reports/explore/k4s-confirm/mac/k4s_logic.py': '2e4d7a5ce5363a9778eb088be7487d5f1ef7291706f743e9dd4c7c65ee5d4864',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_end.py': '76d5ce317915b2c6364310e1bd6a513d7906ce13521029b9737c80e31cbd2260',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts.py': '839a43be635ca0de8db5f70f1a13459007a37f338e79ab6fef1fae43816460a6',
}
FROZEN_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"         # = S9 DEFAULT_PYTHON
S9_PATH = RUNNER + "/end-prep/s3s9s10-r6/s9_end_runtime.py"
S9_SHA256 = "bdc2deeb96bf60a16b8877ffa2038760673d60bb63edcde8d947195fdfdcf3a7"
SCRATCH_PARENT = "/dev/shm"
SCRATCH_GIT_ENV = {"GIT_AUTHOR_NAME": "k4s-end-job self-check", "GIT_AUTHOR_EMAIL": "scratch@127x05",
                   "GIT_COMMITTER_NAME": "k4s-end-job self-check", "GIT_COMMITTER_EMAIL": "scratch@127x05",
                   "TZ": "UTC"}

FROZEN_DRIVER = """
import json, sys
rt, evp, evsha, repo, jobsha, k4s = sys.argv[1:7]
K = rt + "/reports/explore/k4s-confirm"
sys.path[:0] = [K + "/mac", K, rt + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"]
import end_evidence as E, fleet_end
ev = E.end_evidence(evp, evsha, repo, fleet_end)
job = E.end_job(repo, ev, jobsha, k4s)
print("__K4S_FROZEN__ " + json.dumps(dict(
    end_evidence=dict(counted_hosts=ev["counted_hosts"], plan_sha256=ev["plan_sha256"],
                      completion_sha256=ev["completion_sha256"], sha256=ev["sha256"]),
    end_job=dict(commit=job["commit"], sha256=job["sha256"], repository_path=job["repository_path"],
                 registry_root=job["registry_root"]),
    job_fields=sorted(E.JOB_FIELDS), job_schema=E.JOB_SCHEMA, end_job_path=E.END_JOB_PATH), sort_keys=True))
"""
S9_DRIVER = """
import importlib.util, sys
path, repo = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("s9_end_runtime", path)
S9 = importlib.util.module_from_spec(spec)
sys.modules["s9_end_runtime"] = S9
spec.loader.exec_module(S9)
S9.REPO_FULL = repo                      # S9's documented REPO_FULL hook (INTEGRATION-AUDIT-r1 s9_equiv_drive.py)
sys.exit(S9.main(sys.argv[3:]))
"""


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def job_bytes(job):
    return (json.dumps(job, indent=1, sort_keys=True) + "\n").encode()


def load_si(directory=None):
    path = k4s_bootstrap_default_path(__file__, "safe_input.py") if directory is None else directory + "/safe_input.py"
    si = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, "safe_input", JobRefusal)
    require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input fingerprint differs from the pin")
    return si


def own_sha256(si):
    """SHA-256 of this builder file as executed (recorded in BUILD.json / SELF-CHECK.json)."""
    path = k4s_bootstrap_default_path(__file__, os.path.basename(__file__))
    P = si.Policy("127x05", [si.Role("self", os.path.dirname(path), "read", 1 << 22,
                                     exact=(os.path.basename(path),))])
    return si.sha256_input(P, "self", os.path.basename(path))["sha256"]


def on_05(si):
    require(si.hostname_checked().split(".")[0] == "127x05", "The END-JOB builder runs on 127x05")
    require(not sys.flags.optimize, "The END-JOB builder refuses -O")


def repo_policy(si, root, names):
    """One exact read role on the clone; the END-namespace grants only for names inside reports/.../end/."""
    grants = END_GRANTS if any(n.startswith(END_DIR + "/") for n in names) else ()
    return si.Policy("127x05", [si.Role("repo", root, "read", 256 << 20, exact=tuple(names), grants=grants)])


def is_ancestor(si, g, older, newer):
    return si.git_run(g, ["merge-base", "--is-ancestor", older, newer], timeout=120, ok_rcs=(0, 1)).rc == 0


def evidence_item(si, g, root, evidence, key, commit):
    """One committed evidence artifact by its own commit and path: the commit is an ancestor of P', the repository
    path is the evidence-relative path under the evidence's directory, and the blob has the pinned SHA-256."""
    item = evidence.get(key)
    require(isinstance(item, dict) and set(item) == {"commit", "path", "repository_path", "sha256"}
            and COMMIT.fullmatch(str(item["commit"])) and re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])),
            "END evidence %s item malformed" % key)
    rel = item["repository_path"]
    require(isinstance(rel, str) and rel == STUDY_DIR + "/" + item["path"] and ".." not in rel.split("/"),
            "END evidence %s repository_path is not its evidence-relative path" % key)
    require(is_ancestor(si, g, item["commit"], commit), "END evidence %s commit is not an ancestor of P'" % key)
    data = si.git_show_file(repo_policy(si, root, (rel,)), "repo", g, item["commit"], rel, max_size=64 << 20,
                            expected_sha256=item["sha256"])
    return item, data


def sources(si, root=None, commit=None):
    """Every value of the END-JOB, from committed bytes at P' (no typed value)."""
    root, commit = root or REPO_FULL, commit or EVIDENCE_COMMIT
    require(COMMIT.fullmatch(commit), "evidence commit must be 40 hex")
    g = si.GitRepo(work_tree=root)
    raw = si.git_show_file(repo_policy(si, root, (END_EVIDENCE_REL,)), "repo", g, commit, END_EVIDENCE_REL,
                           max_size=16 << 20, expected_sha256=END_EVIDENCE_SHA256)
    evidence = si.loads_strict(raw, END_EVIDENCE_REL)
    require(isinstance(evidence, dict) and evidence.get("schema") == EVIDENCE_SCHEMA
            and evidence.get("kind") == "counted-reporting", "Not the K4S counted-reporting END evidence")
    si.git_show_file(repo_policy(si, root, (K4S_MANIFEST_REL,)), "repo", g, commit, K4S_MANIFEST_REL,
                     max_size=1 << 20, expected_sha256=K4S_MANIFEST_SHA256)
    plan_item, plan_raw = evidence_item(si, g, root, evidence, "plan", commit)
    plan = si.loads_strict(plan_raw, plan_item["repository_path"])
    require(isinstance(plan, dict) and plan.get("study") == STUDY, "END plan is not the K4S reporting plan")
    completion_item, completion_raw = evidence_item(si, g, root, evidence, "completion", commit)
    require(completion_item["sha256"] == COMPLETION_SHA256, "END evidence does not bind the completion of record")
    completion = si.loads_strict(completion_raw, completion_item["repository_path"])
    hosts = completion.get("counted_host_phases") if isinstance(completion, dict) else None
    require(isinstance(hosts, dict) and sorted(hosts) == COUNTED_HOSTS
            and completion.get("reporting_complete") is True and completion.get("outcomes_sealed") is True,
            "Completion of record does not name exactly the counted hosts %s" % COUNTED_HOSTS)
    end_names = [e["path"] for e in si.git_ls_tree(g, commit) if e["path"].startswith(END_DIR + "/")]
    require(end_names == [], "R6: the END namespace must be absent at P' (found %r)" % end_names[:3])
    return dict(commit=commit, evidence=dict(path=END_EVIDENCE_REL, sha256=END_EVIDENCE_SHA256),
                k4s_manifest=dict(path=K4S_MANIFEST_REL, sha256=K4S_MANIFEST_SHA256), plan=plan_item,
                completion=completion_item, counted_hosts=sorted(hosts))


def out_policy(si, out, access="write"):
    parent, leaf = os.path.dirname(out), os.path.basename(out)
    names = ("END-JOB.json", "BUILD.json", "SELF-CHECK.json")
    return si.Policy("127x05", [si.Role("out-parent", parent, "write", 1, exact=(leaf,)),
                                si.Role("out-parent-read", parent, "read", 1, exact=(leaf,)),
                                si.Role("out", out, "write", 1 << 20, exact=names, grants=END_GRANTS),
                                si.Role("out-read", out, "read", 1 << 20, exact=names, grants=END_GRANTS)])


def build(si, declared_by, out, root=None, commit=None):
    require(isinstance(declared_by, str) and DECLARED_BY.fullmatch(declared_by) and declared_by.strip(),
            "--declared-by must be 1-200 printable ASCII characters")
    require(isinstance(out, str) and os.path.isabs(out) and os.path.normpath(out) == out, "--out must be absolute")
    P = out_policy(si, out)
    si.check_absent(P, "out-parent-read", os.path.basename(out))
    src = sources(si, root, commit)
    job = dict(schema=JOB_SCHEMA, study=STUDY, end_evidence_sha256=src["evidence"]["sha256"],
               completion_sha256=src["completion"]["sha256"], plan_sha256=src["plan"]["sha256"],
               k4s_manifest_sha256=src["k4s_manifest"]["sha256"], counted_hosts=src["counted_hosts"],
               declared_utc=iso(), declared_by=declared_by)
    require(tuple(sorted(job)) == JOB_FIELDS, "END-JOB fields differ from the frozen JOB_FIELDS")
    data = job_bytes(job)
    with si.Writer(P, "out-parent") as writer:
        writer.mkdir_excl(os.path.basename(out))
    with si.Writer(P, "out") as writer:
        made = writer.create_excl("END-JOB.json", data)
        receipt = dict(schema=BUILD_SCHEMA, utc=job["declared_utc"], repository=root or REPO_FULL,
                       end_job_sha256=made["sha256"], end_job_repository_path=END_JOB_REL, sources=src,
                       builder_sha256=own_sha256(si),
                       safe_input_sha256=SAFE_INPUT_SHA256, outcomes_read=False)
        writer.create_excl("BUILD.json", (json.dumps(receipt, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps(dict(end_job=out + "/END-JOB.json", end_job_sha256=made["sha256"]), sort_keys=True))
    return job, made["sha256"]


# ---------------------------------------------------------------- self-check (scratch only)

def frozen_inputs(si):
    """The S9 runtime manifest and the frozen files the driver imports, each with its pin, and the S9 code. r5: the
    manifest must have been built by exactly the adopted S9, at P', from REPO_FULL, with FROZEN_PYTHON."""
    P = si.Policy("127x05", [
        si.Role("rt", FROZEN_RUNTIME, "read", 256 << 20, exact=("runtime-manifest.json",)),
        si.Role("rt-files", FROZEN_RUNTIME + "/runtime", "read", 64 << 20, exact=tuple(FROZEN_PINS)),
        si.Role("s9", os.path.dirname(S9_PATH), "read", 16 << 20, exact=(os.path.basename(S9_PATH),))])
    raw = si.read_bytes(P, "rt", "runtime-manifest.json", max_size=256 << 20)
    require(sha_bytes(raw) == FROZEN_RUNTIME_MANIFEST_SHA256,
            "S9 runtime manifest differs from its pin")
    manifest = si.loads_strict(raw, "runtime-manifest.json")
    require(isinstance(manifest, dict) and manifest.get("script_sha256") == S9_SHA256,
            "S9 runtime manifest was not built by the adopted S9 (script_sha256 != S9_SHA256)")
    require(manifest.get("commit") == EVIDENCE_COMMIT and manifest.get("repository") == REPO_FULL
            and manifest.get("python") == FROZEN_PYTHON,
            "S9 runtime manifest is not P' / REPO_FULL / FROZEN_PYTHON")
    for rel, pin in sorted(FROZEN_PINS.items()):
        require(si.sha256_input(P, "rt-files", rel)["sha256"] == pin, "frozen file differs from its pin: " + rel)
    require(si.sha256_input(P, "s9", os.path.basename(S9_PATH))["sha256"] == S9_SHA256,
            "S9 s9_end_runtime.py differs from its pin")
    return manifest


def scratch_commit(si, clone, data, commit):
    """Commit the END-JOB alone on P' in the scratch clone; returns X after checking diff-tree P' X."""
    g = si.GitRepo(work_tree=clone)
    head = si.git_run(g, ["rev-parse", "--verify", "HEAD^{commit}"], timeout=60).stdout.decode().strip()
    require(head == commit, "scratch clone HEAD is not P'")
    path = os.path.join(clone, END_JOB_REL)
    os.makedirs(os.path.dirname(path))
    with open(path, "xb") as stream:
        stream.write(data)
    si.git_run(g, ["add", "--", END_JOB_REL], timeout=300)
    si.git_run(g, ["commit", "-q", "--no-verify", "-m", "K4S END: END-JOB alone (scratch self-check, not A6)"],
               timeout=300, extra_env=SCRATCH_GIT_ENV)
    x = si.git_run(g, ["rev-parse", "--verify", "HEAD^{commit}"], timeout=60).stdout.decode().strip()
    names = si.git_run(g, ["diff-tree", "-r", "-z", "--name-only", "--no-renames", commit, x],
                       timeout=300).stdout.split(b"\x00")[:-1]
    require(x != commit and names == [END_JOB_REL.encode()], "scratch X is not P' + END-JOB alone: %r" % names[:4])
    return x


def materialize_evidence(si, clone, commit, target):
    """The evidence and exactly its artifacts, from their committed blobs, at their evidence-relative paths."""
    g = si.GitRepo(work_tree=clone)
    raw = si.git_show_file(repo_policy(si, clone, (END_EVIDENCE_REL,)), "repo", g, commit, END_EVIDENCE_REL,
                           max_size=16 << 20, expected_sha256=END_EVIDENCE_SHA256)
    evidence = si.loads_strict(raw, END_EVIDENCE_REL)
    items = [evidence[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
    items += [e[f] for e in evidence["phases"] for f in ("launch", "supervisor_exit", "mhz", "census")]
    os.mkdir(target)
    files = {os.path.basename(END_EVIDENCE_REL): raw}
    for item in items:
        rel = item["repository_path"]
        require(rel == STUDY_DIR + "/" + item["path"] and ".." not in rel.split("/"), "artifact path: " + rel)
        files[item["path"]] = si.git_show_file(repo_policy(si, clone, (rel,)), "repo", g, item["commit"], rel,
                                               max_size=256 << 20, expected_sha256=item["sha256"])
    for name, data in sorted(files.items()):
        path = os.path.join(target, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "xb") as stream:
            stream.write(data)
    return os.path.join(target, os.path.basename(END_EVIDENCE_REL)), len(files)


def child_env(home):
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "HOME": home, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0", "PYTHONDONTWRITEBYTECODE": "1"}


def self_check(si, out, job_sha256, commit=None):
    commit = commit or EVIDENCE_COMMIT
    P = out_policy(si, out)
    data = si.read_bytes(P, "out-read", "END-JOB.json", max_size=1 << 16, expected_sha256=job_sha256)
    job = si.loads_strict(data, "END-JOB.json")
    require(isinstance(job, dict) and tuple(sorted(job)) == JOB_FIELDS and job_bytes(job) == data,
            "END-JOB.json is not the builder's canonical END-JOB")
    si.check_absent(P, "out-read", "SELF-CHECK.json")
    manifest = frozen_inputs(si)
    scratch = tempfile.mkdtemp(prefix="k4s-a6-scratch-", dir=SCRATCH_PARENT)
    try:
        clone = os.path.join(scratch, "clone")
        os.mkdir(clone)
        shutil.copytree(os.path.join(REPO_FULL, ".git"), os.path.join(clone, ".git"), symlinks=True)
        x = scratch_commit(si, clone, data, commit)
        evp, count = materialize_evidence(si, clone, commit, os.path.join(scratch, "evidence"))
        home = os.path.join(scratch, "home")
        os.mkdir(home)
        frozen = si.run_checked([FROZEN_PYTHON, "-I", "-B", "-c", FROZEN_DRIVER, FROZEN_RUNTIME + "/runtime", evp,
                                 END_EVIDENCE_SHA256, clone, job_sha256, K4S_MANIFEST_SHA256], 1800, 1 << 20,
                                env=child_env(home), cwd=scratch)
        lines = [l for l in frozen.stdout.decode().splitlines() if l.startswith("__K4S_FROZEN__ ")]
        require(len(lines) == 1, "frozen driver printed no result")
        frozen_result = json.loads(lines[0][len("__K4S_FROZEN__ "):])
        require(frozen_result["end_job"]["commit"] == x and frozen_result["end_job"]["sha256"] == job_sha256
                and frozen_result["end_evidence"]["counted_hosts"] == COUNTED_HOSTS
                and tuple(frozen_result["job_fields"]) == JOB_FIELDS and frozen_result["job_schema"] == JOB_SCHEMA
                and frozen_result["end_job_path"] == END_JOB_REL, "frozen end_job result differs: %r" % frozen_result)
        s9 = si.run_checked([sys.executable, "-I", "-B", "-c", S9_DRIVER, S9_PATH, clone, "equivalence", "--out",
                             FROZEN_RUNTIME, "--manifest-sha256", FROZEN_RUNTIME_MANIFEST_SHA256, "--end-job-commit",
                             x], 3600, 8 << 20, env=child_env(home), cwd=scratch)
        equivalence = json.loads(s9.stdout.decode())
        require(equivalence.get("end_job_commit") == x and equivalence.get("runtime_commit") == commit
                and equivalence.get("diff") == [END_JOB_REL] and equivalence.get("runtime_files_identical") is True
                and equivalence.get("measurement_files_identical") is True, "S9 equivalence result differs")
        require(os.listdir(home) == [], "a child wrote into its empty HOME")
        result = dict(schema=SELF_CHECK_SCHEMA, utc=iso(), end_job_sha256=job_sha256, evidence_commit=commit,
                      builder_sha256=own_sha256(si),
                      scratch_end_job_commit=x, scratch_diff=[END_JOB_REL], evidence_files_materialized=count,
                      frozen=dict(frozen_result, python=FROZEN_PYTHON, runtime=FROZEN_RUNTIME,
                                  runtime_manifest_sha256=FROZEN_RUNTIME_MANIFEST_SHA256,
                                  runtime_manifest_script_sha256=manifest["script_sha256"],
                                  runtime_manifest_git_members_sha256=manifest.get("git_members_sha256")),
                      s9_equivalence=dict(s9=S9_PATH, s9_sha256=S9_SHA256, python=sys.executable,
                                          git_members=equivalence.get("git_members"),
                                          git_members_sha256=equivalence.get("git_members_sha256"),
                                          runtime_files_sha256=equivalence.get("runtime_files_sha256"),
                                          measurement_files_sha256=equivalence.get("measurement_files_sha256")),
                      note="scratch clone = byte copy of REPO_FULL/.git only; removed after the check", ok=True)
    finally:
        for dirpath, dirnames, _ in os.walk(scratch):
            for name in dirnames:
                os.chmod(os.path.join(dirpath, name), 0o700)
        shutil.rmtree(scratch, ignore_errors=True)
    require(not os.path.exists(scratch), "scratch directory not removed: " + scratch)
    with si.Writer(P, "out") as writer:
        made = writer.create_excl("SELF-CHECK.json", (json.dumps(result, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps(dict(self_check=out + "/SELF-CHECK.json", sha256=made["sha256"], end_job_commit_scratch=x,
                          ok=True), sort_keys=True))
    return result


def main(argv=None, si=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", allow_abbrev=False)
    b.add_argument("--declared-by", required=True)
    b.add_argument("--out", required=True)
    c = sub.add_parser("self-check", allow_abbrev=False)
    c.add_argument("--out", required=True)
    c.add_argument("--job-sha256", required=True)
    a = ap.parse_args(argv)
    si = si or load_si()
    try:
        on_05(si)
        if a.command == "build":
            build(si, a.declared_by, a.out)
        else:
            self_check(si, a.out, a.job_sha256)
    except (JobRefusal, si.Refusal) as error:
        print("END-JOB REFUSED: %s" % error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
