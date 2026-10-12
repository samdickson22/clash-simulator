#!/usr/bin/env python3
"""S3 (PREREG-K4S END, RC-3 / Q2 / Q3 / Q4): END guard-job builder, 05 only. r2: safe_input adoption. CANDIDATE.

Builds, on 05, the exact contents of ONE fresh guard job for ONE host and ONE attempt or ONE preflight. S10 ships it
byte-identically (safe_input receive) to its declared Q4 target:
    127x03  /mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd<RR>-a<NN>   or  .../k4s-end-guard-r1-pf<NN>
    127x04  /mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd<RR>-a<NN>       or  .../k4s-end-guard-r1-pf<NN>
(-rdRR-aNN: one END attempt; -pfNN: one RC-2 preflight (S3-F3). A name is never reused.)
Contents (nothing else):
    FROZEN-T1.json             T1 freeze 24817e16, from the commit (si.git_show_file, expected SHA)
    system-bus-admission.json  the host's E3 committed admission reports/explore/k4s-confirm/end-guard-admissions/
                               <host>-system-bus-admission.json (expected SHA = the S1b manifest's on-host SHA)
    idle-services.json         127x03 only, likewise
    repo/                      Q3: a K4S-owned SHALLOW git repository holding exactly the four OP-5 seed/join binding
                               commits (b2f9e25e, ce042b97 + the 08 joins 0e137378, 274aed9a): si.git_run init,
                               depth-1 fetch by SHA from the runner-owned full clone (file protocol only), the four
                               seed/join files checked out at their binding commits (0444), loose refs
                               refs/k4s-end/<label>, no remote, no FETCH_HEAD.
Every input read goes through safe_input with an expected SHA: the freeze, the nine T1 modules (pinned by the
freeze), the 08 seed receipt, the admissions at their exact E3 paths (role exact names; no --admissions-dir: S3-F1),
and the S1b manifest (exact name, --s1b-manifest-sha256 required). Every git call is si.git_run (P2-4). The FROZEN
T1 committed_binding (x4) and admit() run on a throw-away copy, in a child with the P2-4 environment (scrubbed
GIT_*, fresh HOME), never -O, after the copy's repository passed the safe_input preflight.
Output: <out>/<job>/ + <out>/guard-job-manifest.json, built in <out>.partial (receipts kept there on refusal) and
published with renameat2(RENAME_NOREPLACE).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [_HERE]:
    sys.path.insert(0, _HERE)
import end_prep_common as C                                           # noqa: E402

if os.path.dirname(os.path.abspath(C.__file__)) != _HERE:
    raise SystemExit("end_prep_common imported from outside " + _HERE)
S1B = C.import_sibling("s1b_copy_admissions")

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-guard-job.v2"
FREEZE_REL = "reports/explore/t1/FROZEN-T1.json"
FROZEN_T1_SHA = "24817e16c3da7b5c9b6e48c56e69144e84678b7d143a146fe2884f446d07d7e4"
GUARD_DELTAS = ("operational_delta_op5", "operational_delta_op5_08", "operational_delta_op6")
GUARD_MODULES = ("common", "host_audit", "idle_services", "system_bus", "ssh_transport",
                 "perception_confirmation", "owned_supervisor", "ssh_budget", "parent_source_seed")
T1_PREFIX = "reports/explore/t1/receipts/"
L1_PREFIX = "reports/strategy_council_20260928/live-loop/v4/l1/receipts/"
SEEDS = (dict(label="seed-03", path=T1_PREFIX + "op5-parent-source-127x03.json",
              commit="b2f9e25e1002d43cc910a4bb476716cc4cd32623",
              sha256="167cbe71eeabcd455ab0763dfd5d6061bab4d132a8783622e020d78abbd18838", prefix=T1_PREFIX),
         dict(label="seed-08", path=T1_PREFIX + "op5-parent-source-127x08.json",
              commit="ce042b9775f80cb495c327b14a4712730ae95c85",
              sha256="7081bb443e7b4776679f3c25daa521216f8d3946accb55b3441fac964b1a7c27", prefix=T1_PREFIX))
JOINS = (dict(label="join-08-server", path=T1_PREFIX + "op5-parent-generation-127x08.json",
              commit="0e137378ff251896d7a27899a9453f278945276b",
              sha256="f47a87ab42d6d14e9301c94198629595d277790ada358bc3c62fb88a8abe420f", prefix=T1_PREFIX),
         dict(label="join-08-client",
              path=L1_PREFIX + "a21-a2-preparation-20261010-r1/08-transport-identity-20261010T172047Z.json",
              commit="274aed9a8fcd446ddb5a6f5ec32dc9d3d4163b6a",
              sha256="10735e94cd3888eeafa8e8fb97eab87bddc2ec27c5a5ae3ba5b1f94c50950961", prefix=L1_PREFIX))
BINDINGS = SEEDS + JOINS
Q3_COMMITS = ("b2f9e25e1002d43cc910a4bb476716cc4cd32623", "ce042b9775f80cb495c327b14a4712730ae95c85")
GUARD_PARENTS = dict(si.Q4_GUARD_PARENTS)          # Q4: 03 /mpac/sdicks02/jobs/clasher, 04 /mpac/sdicks02/jobs-k4s
JOB_NAME = re.compile(r"k4s-end-guard-r1-(?:rd([0-9]{2})-a([0-9]{2})|pf([0-9]{2}))")
REPO_FULL = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full"   # ruling 21:28Z: the runner-owned full clone
DEFAULT_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
GIT_BINARY = si.GIT_BINARY
UPLOAD_PACK = GIT_BINARY + " -c uploadpack.allowAnySHA1InWant=true upload-pack"
MANIFEST = "guard-job-manifest.json"
S1B_MANIFEST = "s1b-admissions-manifest.json"
GUARD_GIT_CONFIG_KEYS = ("core.bare", "core.filemode", "core.logallrefupdates", "core.repositoryformatversion")
# git init --template= scaffolding that must exist (empty directories are not visible to a file walk).
GIT_DIRS = (".git", ".git/objects", ".git/objects/info", ".git/objects/pack", ".git/refs", ".git/refs/heads",
            ".git/refs/tags", ".git/refs/k4s-end")


def target_job(host, round_=None, attempt=None, preflight=None):
    """The Q4 job name and target for one attempt (-rdRR-aNN) or one preflight (-pfNN); nothing else."""
    require(host in GUARD_PARENTS, "policy", "host must be 127x03 or 127x04")
    two = re.compile(r"[0-9]{2}")
    if preflight is not None:
        require(round_ is None and attempt is None and two.fullmatch(preflight or "") is not None, "policy",
                "a preflight job takes --preflight NN only")
        name = "k4s-end-guard-r1-pf" + preflight
    else:
        require(two.fullmatch(round_ or "") is not None and two.fullmatch(attempt or "") is not None, "policy",
                "--round and --attempt are two digits")
        name = "k4s-end-guard-r1-rd%s-a%s" % (round_, attempt)
    return check_name(name), GUARD_PARENTS[host] + "/" + name


def check_name(name):
    require(isinstance(name, str) and JOB_NAME.fullmatch(name) is not None
            and si.GUARD_JOB_NAME.fullmatch(name) is not None, "policy",
            "guard job must be k4s-end-guard-r1-rdRR-aNN or k4s-end-guard-r1-pfNN: %r" % (name,))
    return name


def check_target(host, path):
    """The Q4 namespace and nothing else (also used by S10 on the remote path)."""
    require(isinstance(path, str) and host in GUARD_PARENTS and "/" in path, "policy", "bad guard target")
    parent, name = path.rsplit("/", 1)
    require(parent == GUARD_PARENTS[host] and os.path.normpath(path) == path, "policy",
            "guard job must be %s/<k4s-end-guard-r1-...>" % GUARD_PARENTS.get(host))
    check_name(name)
    return path


def job_kind(name):
    m = JOB_NAME.fullmatch(check_name(name))
    if m.group(3) is not None:
        return dict(kind="preflight", preflight=m.group(3))
    return dict(kind="attempt", round=m.group(1), attempt=m.group(2))


def top_level(host):
    return sorted(["FROZEN-T1.json", "repo"] + list(S1B.NAMES[host]))


def repo_roles(repository, host):
    names = (FREEZE_REL, SEEDS[1]["path"]) + tuple("reports/explore/t1/%s.py" % m for m in GUARD_MODULES)
    names += tuple("%s/%s" % (si.E3_ADMISSIONS_DIR, S1B.e3_name(host, n)) for n in S1B.NAMES[host])
    return [si.Role("repo", repository, "read", 16 << 20, exact=names)]


def seed_paths():
    return tuple(b["path"] for b in BINDINGS)


def guard_repo_role(name, root, access="read"):
    if access == "read":
        return si.Role(name, root, "read", 16 << 20, exact=seed_paths() + (".git/config", ".git/FETCH_HEAD"),
                       grants=("guard-job",))
    refs = tuple(".git/refs/k4s-end/" + b["label"] for b in BINDINGS)
    return si.Role(name, root, "write", 1 << 20, exact=refs + (".git/FETCH_HEAD",), grants=("guard-job",))


# ---------------------------------------------------------------- committed inputs (safe_input git, expected SHAs)

def committed_inputs(policy, repository, commit, host, s1b_manifest_sha):
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "policy",
            "--commit must be a full 40-hex commit")
    repo = si.GitRepo(work_tree=repository)
    freeze_raw = si.git_show_file(policy, "repo", repo, commit, FREEZE_REL, 16 << 20, expected_sha256=FROZEN_T1_SHA)
    freeze = si.loads_strict(freeze_raw, FREEZE_REL)
    for delta in GUARD_DELTAS:
        require(isinstance(freeze.get(delta), dict) and freeze[delta].get("verdict") == "CONFIRM", "check",
                "freeze lacks a CONFIRM " + delta)
    require(freeze.get("parent_source_seeds") == [{k: s[k] for k in ("path", "commit", "sha256")} for s in SEEDS],
            "check", "freeze parent_source_seeds differ from the two bindings of record")
    receipt08 = si.loads_strict(si.git_show_file(policy, "repo", repo, SEEDS[1]["commit"], SEEDS[1]["path"], 1 << 20,
                                                 expected_sha256=SEEDS[1]["sha256"]), SEEDS[1]["path"])
    require(receipt08.get("source_join") == {"server": {k: JOINS[0][k] for k in ("path", "commit", "sha256")},
                                             "client": {k: JOINS[1][k] for k in ("path", "commit", "sha256")}},
            "check", "08 receipt source_join differs from the join bindings of record")
    files = freeze.get("files")
    require(isinstance(files, dict), "check", "freeze lacks its files map")
    for b in BINDINGS:
        require(files.get(b["path"]) == b["sha256"], "check", "binding not pinned by FROZEN-T1 files: " + b["path"])
    modules = {}
    for m in GUARD_MODULES:
        rel = "reports/explore/t1/%s.py" % m
        pin = files.get(rel)
        require(C.is_sha256(pin), "check", "FROZEN-T1 does not pin " + rel)
        modules[m + ".py"] = si.git_show_file(policy, "repo", repo, commit, rel, 16 << 20, expected_sha256=pin)
    s1b = si.read_json(policy, "s1b", S1B_MANIFEST, 16 << 20, expected_sha256=s1b_manifest_sha)
    require(isinstance(s1b, dict) and s1b.get("schema") == S1B.SCHEMA and s1b.get("status") == "copied"
            and isinstance(s1b.get("files"), list), "check", "not an S1b r2 admissions manifest")
    admissions = {}
    for name in S1B.NAMES[host]:
        rows = [f for f in s1b["files"] if isinstance(f, dict) and f.get("host") == host and f.get("name") == name]
        require(len(rows) == 1, "check", "S1b manifest lacks %s/%s" % (host, name))
        row = rows[0]
        require(row.get("remote_path") == "%s/%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE, name)
                and row.get("remote_nlink") == 1 and C.is_sha256(row.get("remote_sha256"))
                and row.get("remote_sha256") == row.get("local_sha256"), "check",
                "S1b row for %s/%s is not an exact-path single-link copy" % (host, name))
        rel = "%s/%s" % (si.E3_ADMISSIONS_DIR, S1B.e3_name(host, name))            # E3 exact layout (S3-F1)
        raw = si.git_show_file(policy, "repo", repo, commit, rel, S1B.MAX_BYTES, expected_sha256=row["remote_sha256"])
        identity = S1B.check_admission(host, name, raw)
        admissions[name] = (raw, dict(repository_path=rel, sha256=C.sha_bytes(raw), size=len(raw), identity=identity,
                                      s1b_remote_path=row["remote_path"], s1b_remote_sha256=row["remote_sha256"]))
    return freeze_raw, modules, admissions


# ---------------------------------------------------------------- the guard repository (Q3)

def build_repo(policy, repository, job):
    """Q3: depth-1 fetch of exactly the four binding commits from the full clone (file protocol), through si.git_run."""
    root = policy.role("partial").root + "/" + job + "/repo"
    source = si.GitRepo(work_tree=repository)
    for b in BINDINGS:                                     # the source passes the static preflight; commits present
        si.git_run(source, ["cat-file", "-e", b["commit"] + "^{commit}"], timeout=60)
    g = si.GitRepo(work_tree=root, protocols=("file",), allow=("shallow",))
    si.git_run(g, ["init", "-q", "--template="], timeout=60)
    si.git_run(g, ["fetch", "-q", "--depth=1", "--no-tags", "--upload-pack=" + UPLOAD_PACK, "file://" + repository]
               + [b["commit"] for b in BINDINGS], timeout=900)
    C.unlink_own(policy, "guard-repo-w", ".git/FETCH_HEAD")        # our own fresh file; it names the 05 source path
    writer = si.Writer(policy, "guard-repo-w")
    try:
        writer.mkdir_excl(".git/refs/k4s-end")
        for b in BINDINGS:
            writer.create_excl(".git/refs/k4s-end/" + b["label"], (b["commit"] + "\n").encode(), 0o444)
    finally:
        writer.close()
    for b in BINDINGS:
        si.git_run(g, ["checkout", "-q", b["commit"], "--", b["path"]], timeout=120)
        C.chmod_readonly(policy, "guard-repo", b["path"])
    return prove_repo(policy, "guard-repo", root)


def prove_repo(policy, role_name, root):
    """git cat-file -e for all four commits (Q3 b2f9e25e and ce042b97 first); git show == checked-out file == the
    binding SHA; refs exactly refs/k4s-end/<label>; config only core keys (no remote, no promisor); no FETCH_HEAD."""
    g = si.GitRepo(work_tree=root, allow=("shallow",))
    proofs = []
    for commit in Q3_COMMITS + tuple(b["commit"] for b in JOINS):
        si.git_run(g, ["cat-file", "-e", commit + "^{commit}"], timeout=60)
        proofs.append(dict(commit=commit, cat_file_e=0))
    for b in BINDINGS:
        committed = si.git_show_file(policy, role_name, g, b["commit"], b["path"], 1 << 20, expected_sha256=b["sha256"])
        checked_out = si.read_bytes(policy, role_name, b["path"], expected_sha256=b["sha256"])
        require(committed == checked_out, "check", "seed bytes differ: " + b["path"])
    refs = si.git_run(g, ["for-each-ref", "--format=%(refname) %(objectname)"], timeout=60).stdout.decode()
    want = sorted("refs/k4s-end/%s %s" % (b["label"], b["commit"]) for b in BINDINGS)
    require(sorted(refs.splitlines()) == want, "check", "guard repo refs differ from refs/k4s-end/<label>: %r"
            % refs[:300])
    config = si.read_bytes(policy, role_name, ".git/config", max_size=4096).decode("utf-8", "replace")
    keys, section = [], None
    for line in config.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            section = line.strip("[]").strip().casefold()
            continue
        keys.append("%s.%s" % (section, line.split("=", 1)[0].strip().casefold()))
    require(sorted(keys) == sorted(GUARD_GIT_CONFIG_KEYS), "check", "guard repo config is not the plain init config: %r"
            % keys)
    si.check_absent(policy, role_name, ".git/FETCH_HEAD")
    shallow = si.git_run(g, ["rev-parse", "--is-shallow-repository"], timeout=60).stdout
    require(shallow == b"true\n", "check", "guard repo is expected to be the depth-1 (shallow) Q3 clone")
    return proofs


# ---------------------------------------------------------------- frozen T1 check (throw-away copy)

FROZEN_SNIPPET = r"""
import json, sys, types
from pathlib import Path
modules, job = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(modules))
import parent_source_seed as P
allowed = {str((modules / n).resolve()) for n in json.loads(sys.argv[4])}
loaded = {str(Path(m.__file__).resolve()) for m in list(sys.modules.values()) if getattr(m, "__file__", None)
          and str(Path(m.__file__).resolve()).startswith(str(modules.resolve()) + "/")}
if Path(P.__file__).resolve().parent != modules.resolve() or not loaded <= allowed:
    raise SystemExit("guard modules imported from outside the verified nine: " + repr(sorted(loaded - allowed)))
freeze = json.loads((job / "FROZEN-T1.json").read_text())
repo = (job / "repo").resolve()
bindings = json.loads(sys.argv[3])
loaded = [P.committed_binding(repo, repo, freeze, b, b["prefix"]).get("host") for b in bindings]
accepted = P.admit(job, [], types.SimpleNamespace(sources={}))
written = json.loads((job / "parent-source-seed-admission.json").read_text())
print(json.dumps(dict(committed_binding_hosts=loaded, admit_accepted=accepted, admit_host=written["host"],
                      module=str(Path(P.__file__).resolve()), optimize=sys.flags.optimize)))
"""


def frozen_check(policy, job, files, dirs, modules, python):
    """FROZEN T1 committed_binding (x4) + admit() on a throw-away copy of the job (never the output)."""
    tmp = policy.role("frozen-tmp").root
    writer = si.Writer(policy, "frozen-tmp")
    try:
        writer.mkdir_excl("t1")
        for name, raw in sorted(modules.items()):
            writer.create_excl("t1/" + name, raw, 0o444)
        writer.mkdir_excl("job")
        for d in dirs:
            writer.mkdir_excl("job/" + d)
        for f in files:
            si.copy_input(policy, "partial-read", job + "/" + f["path"], writer, "job/" + f["path"],
                          expected_sha256=f["sha256"], expected_size=f["size"])
    finally:
        writer.close()
    copy_repo = si.GitRepo(work_tree=tmp + "/job/repo", allow=("shallow",))
    refs = si.git_run(copy_repo, ["for-each-ref", "--format=%(refname)"], timeout=60).stdout.decode().split()
    require(sorted(refs) == sorted("refs/k4s-end/" + b["label"] for b in BINDINGS), "indirection",
            "the copy's refs are not exactly refs/k4s-end/* (no replace refs)")
    with C.ScrubbedEnv() as env:
        # Never -O: the frozen T1 checks are asserts, live on the host exactly as here.
        argv = [python, "-I", "-B", "-c", FROZEN_SNIPPET, tmp + "/t1", tmp + "/job", json.dumps(list(BINDINGS)),
                json.dumps(sorted(modules))]
        result = si.run_checked(argv, 600, 1 << 20, env=env, cwd=tmp)
    out = si.loads_strict(result.stdout, "frozen seed check output")
    require(isinstance(out, dict) and out.get("optimize") == 0
            and out.get("committed_binding_hosts", [])[:2] == ["127x03", "127x08"], "check",
            "frozen committed_binding gave unexpected seed hosts")
    require(out.get("admit_accepted") == [], "check", "frozen admit() accepted a seed on 05 (unexpected)")
    out["module"] = os.path.basename(out.get("module", ""))
    return out


# ---------------------------------------------------------------- inventory

def inventory(policy, role_name, job, host):
    """Every file of the job through the confined walk (names gated before lstat; symlink/special/hard link refuse)
    and the descriptor gate; directories = parents of files plus the git scaffolding (checked as real dirs)."""
    walk = si.walk_tree(policy, role_name, job)
    require(walk["e1"] is None and not walk["e4"], "check", "guard job holds an E1/E4 entry")
    rows = []
    for f in walk["files"]:
        rel = f["rel"][len(job) + 1:]
        digest = si.sha256_input(policy, role_name, f["rel"], expected_size=f["size"])
        rows.append(dict(path=rel, size=f["size"], sha256=digest["sha256"]))
    top = sorted({r["path"].split("/")[0] for r in rows})
    require(top == top_level(host), "check", "guard job top level must be exactly %r (got %r)" % (top_level(host), top))
    dirs = sorted(set(C.dirs_of(r["path"] for r in rows)) | {"repo"} | {"repo/" + d for d in GIT_DIRS},
                  key=lambda d: (d.count("/"), d))
    for d in dirs:
        si.check_dir(policy, role_name, job + "/" + d)
    return rows, dirs


# ---------------------------------------------------------------- build / verify

def build_policy(a, parent, leaf, job, tmp):
    partial = parent + "/" + leaf + ".partial"
    s1b_dir, s1b_name = os.path.split(C.input_dir(a.s1b_manifest, "--s1b-manifest"))
    require(s1b_name == S1B_MANIFEST, "policy", "--s1b-manifest must name %s" % S1B_MANIFEST)
    roles = repo_roles(REPO_FULL, a.host) + [C.code_role(),
        si.Role("s1b", s1b_dir, "read", 16 << 20, exact=(S1B_MANIFEST,)),
        si.Role("out-parent", parent, "write", 1 << 20, exact=(leaf, leaf + ".partial")),
        si.Role("partial", partial, "write", 1 << 30, patterns=(job + "/**", MANIFEST, "S3-REFUSAL-*.json"),
                grants=("guard-job",)),
        si.Role("partial-read", partial, "read", 1 << 30, patterns=(job + "/**",), grants=("guard-job",)),
        guard_repo_role("guard-repo", partial + "/" + job + "/repo"),
        guard_repo_role("guard-repo-w", partial + "/" + job + "/repo", "write"),
        si.Role("frozen-tmp", tmp, "write", 1 << 30, patterns=("**",))]
    return si.Policy(C.local_host(), roles)


def build(a, log=print):
    name, target = target_job(a.host, a.round, a.attempt, a.preflight)
    parent, leaf = C.output_path(a.out, "--out")
    C.need_sha256(a.s1b_manifest_sha256, "--s1b-manifest-sha256")
    python = C.input_dir(a.python, "--python")
    tmp = tempfile.mkdtemp(prefix="k4s-s3-frozen-")
    try:
        policy = build_policy(a, parent, leaf, name, tmp)
        with si.Writer(policy, "out-parent") as top:
            top.mkdir_excl(leaf + ".partial")                         # first: refusals leave a receipt inside it
        writer = si.Writer(policy, "partial")
        try:
            manifest = _build(a, policy, writer, name, target, python, log)
        except BaseException as error:
            si.write_refusal_receipt(writer, "S3", error, {"job": name, "host": a.host})
            raise
        finally:
            writer.close()
        C.publish_dir(policy, "out-parent", leaf + ".partial", leaf)
    finally:
        shutil.rmtree(tmp)                                            # our own throw-away copy only
    log("S3 OK: %s/%s/%s -> %s" % (parent, leaf, name, target))
    log("  %s/%s/%s sha256 %s" % (parent, leaf, MANIFEST, manifest["_sha256"]))
    return manifest


def _build(a, policy, writer, name, target, python, log):
    freeze_raw, modules, admissions = committed_inputs(policy, REPO_FULL, a.commit, a.host, a.s1b_manifest_sha256)
    writer.mkdir_excl(name)
    writer.create_excl(name + "/FROZEN-T1.json", freeze_raw, 0o444)
    for fname, (raw, _) in sorted(admissions.items()):
        writer.create_excl(name + "/" + fname, raw, 0o444)
    writer.mkdir_excl(name + "/repo")
    proofs = build_repo(policy, REPO_FULL, name)
    rows, dirs = inventory(policy, "partial-read", name, a.host)
    frozen = frozen_check(policy, name, rows, dirs, modules, python)
    git_version = si.git_run(si.GitRepo(work_tree=REPO_FULL), ["--version"], timeout=30).stdout.decode().strip()
    manifest = dict(
        schema=SCHEMA, status="CANDIDATE-built", utc=C.utc(), host=a.host, job_name=name, job=job_kind(name),
        target_job=target, repository=REPO_FULL, repository_commit=a.commit, frozen_t1_sha256=FROZEN_T1_SHA,
        admissions={n: e for n, (_, e) in admissions.items()}, s1b_manifest_sha256=a.s1b_manifest_sha256,
        bindings=[{k: b[k] for k in ("label", "path", "commit", "sha256")} for b in BINDINGS],
        q3_commits=list(Q3_COMMITS), commit_proofs=proofs, frozen_seed_check=frozen, top_level=top_level(a.host),
        inventory=rows, dirs=dirs, inventory_sha256=C.canonical_sha(rows), files=len(rows),
        bytes=sum(r["size"] for r in rows), git_version=git_version, safe_input_sha256=C.SAFE_INPUT_SHA256,
        script_sha256=C.code_sha(policy, "s3_guard_job.py"), s1b_module_sha256=C.code_sha(policy, "s1b_copy_admissions.py"),
        common_sha256=C.code_sha(policy, "end_prep_common.py"))
    result = writer.write_json_once(MANIFEST, manifest)
    manifest["_sha256"] = result["sha256"]
    return manifest


def verify_roles(prefix, out, job):
    check_name(job)
    return [si.Role(prefix + "-out", out, "read", 64 << 20, exact=(MANIFEST,)),
            si.Role(prefix + "-job", out, "read", 1 << 30, patterns=(job + "/**",), grants=("guard-job",)),
            guard_repo_role(prefix + "-repo", out + "/" + job + "/repo")]


def verify(policy, prefix, out, job, manifest_sha256, log=print):
    """Re-hash a built guard job against its pinned manifest and re-prove the four commits (S10 runs it)."""
    C.need_sha256(manifest_sha256, "guard manifest SHA-256")
    manifest = si.read_json(policy, prefix + "-out", MANIFEST, 64 << 20, expected_sha256=manifest_sha256)
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA
            and manifest.get("frozen_t1_sha256") == FROZEN_T1_SHA and manifest.get("job_name") == job, "check",
            "not the S3 r2 manifest of guard job %s" % job)
    host = manifest.get("host")
    require(host in GUARD_PARENTS and manifest.get("target_job") == GUARD_PARENTS[host] + "/" + job
            and manifest.get("job") == job_kind(job), "check", "manifest target differs from the Q4 namespace")
    rows, dirs = inventory(policy, prefix + "-job", job, host)
    require(rows == manifest["inventory"] and C.canonical_sha(rows) == manifest["inventory_sha256"]
            and dirs == manifest["dirs"], "check", "guard job differs from its manifest inventory")
    by_path = {r["path"]: r for r in rows}
    require(by_path["FROZEN-T1.json"]["sha256"] == FROZEN_T1_SHA, "check", "freeze copy changed")
    for name, entry in sorted(manifest["admissions"].items()):
        raw = si.read_bytes(policy, prefix + "-job", job + "/" + name, expected_sha256=entry["sha256"])
        S1B.check_admission(host, name, raw)
    prove_repo(policy, prefix + "-repo", out + "/" + job + "/repo")
    log("S3 VERIFY OK: %s/%s manifest %s" % (out, job, manifest_sha256))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command")
    bp = sub.add_parser("build", allow_abbrev=False)
    bp.add_argument("--host", required=True, choices=sorted(GUARD_PARENTS))
    bp.add_argument("--round")
    bp.add_argument("--attempt")
    bp.add_argument("--preflight", help="NN: build the RC-2 preflight job k4s-end-guard-r1-pfNN instead")
    bp.add_argument("--commit", required=True, help="commit (in the full clone) holding FROZEN-T1 and the E3 admissions")
    bp.add_argument("--s1b-manifest", required=True, help="<S1b dest>/s1b-admissions-manifest.json")
    bp.add_argument("--s1b-manifest-sha256", required=True)
    bp.add_argument("--out", required=True)
    bp.add_argument("--python", default=DEFAULT_PYTHON)
    vp = sub.add_parser("verify", allow_abbrev=False)
    vp.add_argument("--out", required=True)
    vp.add_argument("--job", required=True)
    vp.add_argument("--manifest-sha256", required=True)
    a = ap.parse_args(argv)
    if a.command is None:
        ap.print_usage(sys.stderr)
        return 2
    try:
        if a.command == "build":
            build(a)
        else:
            out = C.input_dir(a.out, "--out")
            policy = si.Policy(C.local_host(), verify_roles("s3", out, a.job))
            verify(policy, "s3", out, a.job, a.manifest_sha256)
    except si.Refusal as error:
        print("S3 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print("S3 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
