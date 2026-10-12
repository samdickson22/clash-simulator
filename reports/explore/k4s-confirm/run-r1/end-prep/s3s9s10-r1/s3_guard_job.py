#!/usr/bin/env python3
"""S3 (PREREG-K4S END, RC-3 / Q2 / Q3 / Q4): per-attempt END guard-job builder, 05 only. CANDIDATE: Sol review first.

Builds, on 05, the exact contents of ONE fresh guard job for ONE host and ONE attempt. S10 ships it byte-identically
to the declared target (Q4):
    127x03  /mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd<RR>-a<NN>
    127x04  /mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd<RR>-a<NN>
Contents (nothing else):
    FROZEN-T1.json                 T1 freeze 24817e16 (git show <commit>:reports/explore/t1/FROZEN-T1.json)
    system-bus-admission.json      byte copy of the host's latest K4S admission, as COMMITTED after S1b (Q2)
    idle-services.json             127x03 only (PID 2180947), as committed after S1b
    repo/                          Q3 Option A: a K4S-owned git repository holding the four OP-5 seed/join binding
                                   commits (b2f9e25e, ce042b97 + the 08 join 0e137378, 274aed9a) as a depth-1
                                   fetch from the 05 repository, with the four seed/join files checked out
                                   at their binding commits. No remote, no FETCH_HEAD, gc.auto=0, refs/k4s-end/*.
Checks (fail closed; nothing is renamed into place unless all pass):
  * freeze SHA, its three CONFIRM deltas, parent_source_seeds and the 08 source_join equal the constants;
  * each admission = the committed bytes; content/identity per s1b.check_admission; with --s1b-manifest also
    committed SHA == S1b local SHA == on-host SHA, and the on-host path is the exact Q2 path;
  * `git cat-file -e <c>^{commit}` for all four binding commits in repo/, and for every seed file
    `git show <commit>:<path>` == the checked-out bytes == the binding SHA;
  * the FROZEN T1 parent_source_seed.committed_binding (all four bindings) and admit() run on a throw-away copy
    of the job (05 hostname, so admit() git-shows both bindings then skips them, as on 04; accepted == []);
  * the job's top level is exactly the names above; no symlink anywhere; per-file inventory recorded.
Output: <out>/<job name>/ + <out>/guard-job-manifest.json (built in <out>.partial, renamed at the end).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import end_prep_common as C                                           # noqa: E402
import s1b_copy_admissions as S1B                                    # noqa: E402  (sibling module, checked below)

for _module in (C, S1B):
    if Path(_module.__file__).resolve().parent != HERE:
        raise SystemExit("sibling module imported from outside " + str(HERE))

SCHEMA = "clasher.k4s.end-guard-job.v1"
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
GUARD_PARENTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
JOB_NAME = re.compile(r"k4s-end-guard-r1-rd([0-9]{2})-a([0-9]{2})")
DEFAULT_ADMISSIONS_DIR = "reports/explore/k4s-confirm/end-guard-admissions"   # coordinator E3 (ab171591)
DEFAULT_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
COMMIT = re.compile(r"[0-9a-f]{40}")


Refusal, require = C.Refusal, C.require


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return C.sha_file(path)                                           # O_NOFOLLOW, regular files only


def canonical_sha(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def target_job(host, round_, attempt):
    require(host in GUARD_PARENTS, "host must be 127x03 or 127x04")
    require(re.fullmatch(r"[0-9]{2}", round_ or "") and re.fullmatch(r"[0-9]{2}", attempt or ""),
            "--round and --attempt are two digits")
    name = f"k4s-end-guard-r1-rd{round_}-a{attempt}"
    require(JOB_NAME.fullmatch(name) is not None, "bad job name")
    return name, GUARD_PARENTS[host] + "/" + name


def check_target(host, path):
    """The Q4 namespace and nothing else (also used by S10 on the remote path)."""
    parent, _, name = path.rpartition("/")
    require(host in GUARD_PARENTS and parent == GUARD_PARENTS[host] and JOB_NAME.fullmatch(name) is not None
            and os.path.normpath(path) == path, f"guard job must be {GUARD_PARENTS.get(host)}/k4s-end-guard-r1-rdRR-aNN")
    return path


# ---------------------------------------------------------------- git

def git_env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}


def git(cwd, *args, env=None, binary=False):
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, env=env)
    require(result.returncode == 0, "git " + " ".join(args[:2]) + " failed: " + result.stderr.decode(errors="replace")[-300:])
    return result.stdout if binary else result.stdout.decode()


def show(repository, commit, rel):
    result = subprocess.run(["git", "-C", str(repository), "show", commit + ":" + rel], capture_output=True)
    require(result.returncode == 0, "not committed at " + commit[:12] + ": " + rel)
    return result.stdout


def committed_inputs(repository, commit, host, admissions_dir, s1b_manifest):
    require(COMMIT.fullmatch(commit or "") is not None, "--commit must be a full 40-hex commit")
    freeze_raw = show(repository, commit, FREEZE_REL)
    require(sha_bytes(freeze_raw) == FROZEN_T1_SHA, "FROZEN-T1.json at the commit is not 24817e16")
    freeze = json.loads(freeze_raw)
    for delta in GUARD_DELTAS:
        require(freeze.get(delta, {}).get("verdict") == "CONFIRM", "freeze lacks a CONFIRM " + delta)
    require(freeze.get("parent_source_seeds") == [{k: s[k] for k in ("path", "commit", "sha256")} for s in SEEDS],
            "freeze parent_source_seeds differ from the two bindings of record")
    receipt08 = json.loads(show(repository, SEEDS[1]["commit"], SEEDS[1]["path"]))
    require(receipt08.get("source_join") == {"server": {k: JOINS[0][k] for k in ("path", "commit", "sha256")},
                                             "client": {k: JOINS[1][k] for k in ("path", "commit", "sha256")}},
            "08 receipt source_join differs from the join bindings of record")
    for b in BINDINGS:
        require(freeze["files"].get(b["path"]) == b["sha256"], "binding not pinned by FROZEN-T1 files: " + b["path"])
    modules = {}
    for m in GUARD_MODULES:
        raw = show(repository, commit, f"reports/explore/t1/{m}.py")
        require(sha_bytes(raw) == freeze["files"].get(f"reports/explore/t1/{m}.py"), "T1 module differs from freeze: " + m)
        modules[m + ".py"] = raw
    admissions, s1b = {}, None
    if s1b_manifest:
        s1b = json.loads(C.read_bounded(s1b_manifest, 16 << 20))
        require(s1b.get("schema") == S1B.SCHEMA and s1b.get("status") == "copied", "not an S1b manifest")
    for name in S1B.NAMES[host]:
        rel = f"{admissions_dir}/{host}-{name}"   # E3 layout <host>-<name>.json
        raw = show(repository, commit, rel)
        identity = S1B.check_admission(host, name, raw)
        entry = dict(repository_path=rel, sha256=sha_bytes(raw), size=len(raw), identity=identity)
        if s1b is not None:
            rows = [f for f in s1b["files"] if f["host"] == host and f["name"] == name]
            require(len(rows) == 1, f"S1b manifest lacks {host}/{name}")
            row = rows[0]
            require(row["remote_path"] == f"{S1B.job_dir(host)}/{name}", f"S1b remote path differs for {host}/{name}")
            require(row["remote_sha256"] == row["local_sha256"] == entry["sha256"],
                    f"committed {host}/{name} differs from the S1b on-host/local SHA")
            entry.update(s1b_remote_path=row["remote_path"], s1b_remote_sha256=row["remote_sha256"])
        admissions[name] = (raw, entry)
    return freeze_raw, modules, admissions, (sha_file(s1b_manifest) if s1b_manifest else None)


def build_repo(repository, repo, home):
    """Q3 Option A: depth-1 fetch of exactly the four binding commits from the 05 repository (read only)."""
    env = git_env(home)
    result = subprocess.run(["git", "init", "-q", "--template=", str(repo)], capture_output=True, env=env)
    require(result.returncode == 0, "git init failed: " + result.stderr.decode(errors="replace"))
    git(repo, "config", "gc.auto", "0", env=env)
    git(repo, "config", "core.autocrlf", "false", env=env)
    commits = [b["commit"] for b in BINDINGS]
    git(repo, "fetch", "-q", "--depth=1", "--no-tags",
        "--upload-pack=git -c uploadpack.allowAnySHA1InWant=true upload-pack",
        "file://" + str(Path(repository).resolve()), *commits, env=env)
    (repo / ".git" / "FETCH_HEAD").unlink()
    for b in BINDINGS:
        git(repo, "update-ref", "refs/k4s-end/" + b["label"], b["commit"], env=env)
    for b in BINDINGS:
        git(repo, "checkout", b["commit"], "--", b["path"], env=env)
    return prove_repo(repo, env)


def prove_repo(repo, env=None):
    """git cat-file -e for all four commits (Q3 names b2f9e25e and ce042b97 first), git show == file == SHA."""
    proofs = []
    for commit in Q3_COMMITS + tuple(b["commit"] for b in JOINS):
        result = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", commit + "^{commit}"],
                                capture_output=True, env=env)
        require(result.returncode == 0, "commit absent from the guard repo: " + commit)
        proofs.append(dict(commit=commit, cat_file_e=0))
    for b in BINDINGS:
        raw = git(repo, "show", b["commit"] + ":" + b["path"], env=env, binary=True)
        path = repo / b["path"]
        require(path.is_file() and not path.is_symlink(), "seed file not checked out: " + b["path"])
        require(raw == path.read_bytes() and sha_bytes(raw) == b["sha256"], "seed bytes differ: " + b["path"])
    config = (repo / ".git" / "config").read_text()
    require("[remote" not in config and not (repo / ".git" / "FETCH_HEAD").exists(), "guard repo keeps a remote")
    return proofs


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


def frozen_check(job, modules, python):
    """FROZEN T1 committed_binding (x4) + admit() on a throw-away copy of the job (never the output)."""
    with tempfile.TemporaryDirectory(prefix="k4s-s3-frozen-") as tmp:
        mods = Path(tmp) / "t1"
        mods.mkdir()
        for name, raw in modules.items():
            (mods / name).write_bytes(raw)
        copy = Path(tmp) / "job"
        shutil.copytree(job, copy, symlinks=True)
        # Never -O: the frozen T1 checks are asserts, live on the host exactly as here.
        argv = [python, "-I", "-B", "-c", FROZEN_SNIPPET, str(mods), str(copy), json.dumps(BINDINGS),
                json.dumps(sorted(modules))]                       # the nine, verified against FROZEN-T1 above
        result = subprocess.run(argv, capture_output=True, text=True, cwd=tmp, timeout=600)
        require(result.returncode == 0, "frozen T1 seed check refused: " + result.stderr.strip()[-600:])
        out = json.loads(result.stdout)
    require(out["optimize"] == 0 and out["committed_binding_hosts"][:2] == ["127x03", "127x08"],
            "frozen committed_binding gave unexpected seed hosts")
    require(out["admit_accepted"] == [], "frozen admit() accepted a seed on 05 (unexpected)")
    out["module"] = os.path.basename(out["module"])
    return out


def inventory(job):
    rows = []
    for directory, dirnames, filenames in os.walk(job, followlinks=False):
        dirnames.sort()
        for name in dirnames + sorted(filenames):
            path = os.path.join(directory, name)
            info = os.lstat(path)
            rel = os.path.relpath(path, job)
            require(not stat.S_ISLNK(info.st_mode), "symlink in guard job: " + rel)
            require("\n" not in rel and "\\" not in rel, "unsafe name in guard job: " + repr(rel))
            if stat.S_ISDIR(info.st_mode):
                rows.append(dict(path=rel, type="d", mode=oct(info.st_mode & 0o777)))
            else:
                require(stat.S_ISREG(info.st_mode), "non-regular file in guard job: " + rel)
                rows.append(dict(path=rel, type="f", mode=oct(info.st_mode & 0o777), size=info.st_size,
                                 sha256=sha_file(path)))
    return sorted(rows, key=lambda r: r["path"])


def top_level(host):
    return sorted(["FROZEN-T1.json", "repo"] + list(S1B.NAMES[host]))


def check_job(job, host):
    require(sorted(os.listdir(job)) == top_level(host), "guard job top level must be exactly " + repr(top_level(host)))


def build(a, log=print):
    name, target = target_job(a.host, a.round, a.attempt)
    out = C.confined_new(a.out, "--out")
    partial = C.confined_new(str(out) + ".partial", "--out .partial")
    freeze_raw, modules, admissions, s1b_sha = committed_inputs(Path(a.repository), a.commit, a.host,
                                                                a.admissions_dir, a.s1b_manifest)
    partial.mkdir()
    try:
        job = partial / name
        job.mkdir()
        files = {"FROZEN-T1.json": freeze_raw, **{n: raw for n, (raw, _) in admissions.items()}}
        for fname, raw in files.items():
            C.write_new(job / fname, raw, 0o444)
        with tempfile.TemporaryDirectory(prefix="k4s-s3-home-") as home:
            proofs = build_repo(Path(a.repository), job / "repo", home)
        for b in BINDINGS:
            os.chmod(job / "repo" / b["path"], 0o444)
        check_job(job, a.host)
        frozen = frozen_check(job, modules, a.python)
        inv = inventory(job)
        manifest = dict(
            schema=SCHEMA, status="CANDIDATE-built", utc=utc(), host=a.host, round=a.round, attempt=a.attempt,
            job_name=name, target_job=target, repository_commit=a.commit, frozen_t1_sha256=FROZEN_T1_SHA,
            admissions={n: e for n, (_, e) in admissions.items()}, s1b_manifest_sha256=s1b_sha,
            bindings=[{k: b[k] for k in ("label", "path", "commit", "sha256")} for b in BINDINGS],
            q3_commits=list(Q3_COMMITS), commit_proofs=proofs, frozen_seed_check=frozen,
            top_level=top_level(a.host), inventory=inv, inventory_sha256=canonical_sha(inv),
            files=sum(r["type"] == "f" for r in inv), bytes=sum(r.get("size", 0) for r in inv),
            git_version=subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip(),
            script_sha256=sha_file(Path(__file__).resolve()), s1b_module_sha256=sha_file(S1B.__file__),
            common_sha256=sha_file(C.__file__))
        C.write_new(partial / "guard-job-manifest.json", (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
        partial.rename(out)
    except BaseException:
        remove(partial)
        raise
    path = out / "guard-job-manifest.json"
    log(f"S3 OK: {out / name} -> {target}")
    log(f"  {path} sha256 {sha_file(path)}; {manifest['files']} files, {manifest['bytes']} bytes, "
        f"inventory {manifest['inventory_sha256']}")
    for fname in ["FROZEN-T1.json"] + list(S1B.NAMES[a.host]):
        log(f"  {out / name / fname} sha256 {sha_file(out / name / fname)}")
    return manifest


def remove(path):
    if path.exists():
        for directory, _, filenames in os.walk(path):
            os.chmod(directory, 0o755)
            for f in filenames:
                if not os.path.islink(os.path.join(directory, f)):   # never chmod through a link
                    os.chmod(os.path.join(directory, f), 0o644)
        shutil.rmtree(path)


def load(out):
    path = Path(out) / "guard-job-manifest.json"
    manifest = json.loads(C.read_bounded(path, 64 << 20))
    require(manifest.get("schema") == SCHEMA and manifest.get("frozen_t1_sha256") == FROZEN_T1_SHA, "not an S3 manifest")
    return manifest, sha_file(path)


def verify(out, log=print):
    """Re-hash a built guard job against its manifest and re-prove the four commits (used by S10 before shipping)."""
    manifest, manifest_sha = load(out)
    job = Path(out) / manifest["job_name"]
    _, target = target_job(manifest["host"], manifest["round"], manifest["attempt"])
    require(target == manifest["target_job"], "manifest target differs from the Q4 namespace")
    check_job(job, manifest["host"])
    inv = inventory(job)
    require(inv == manifest["inventory"] and canonical_sha(inv) == manifest["inventory_sha256"],
            "guard job differs from its manifest inventory")
    require(sha_file(job / "FROZEN-T1.json") == FROZEN_T1_SHA, "freeze copy changed")
    for name, entry in manifest["admissions"].items():
        require(sha_file(job / name) == entry["sha256"], "admission copy changed: " + name)
        S1B.check_admission(manifest["host"], name, (job / name).read_bytes())
    prove_repo(job / "repo")
    log(f"S3 VERIFY OK: {job} manifest {manifest_sha}")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    bp = sub.add_parser("build")
    bp.add_argument("--host", required=True, choices=sorted(GUARD_PARENTS))
    bp.add_argument("--round", required=True)
    bp.add_argument("--attempt", required=True)
    bp.add_argument("--repository", default="/mpac/sdicks02/repos/clasher")
    bp.add_argument("--commit", required=True, help="commit holding FROZEN-T1 and the committed admissions (Q2)")
    bp.add_argument("--admissions-dir", default=DEFAULT_ADMISSIONS_DIR, help="repo dir holding <host>-<name> (E3)")
    bp.add_argument("--s1b-manifest", help="S1b s1b-admissions-manifest.json (cross-check; recommended)")
    bp.add_argument("--out", required=True)
    bp.add_argument("--python", default=DEFAULT_PYTHON if os.path.exists(DEFAULT_PYTHON) else sys.executable)
    vp = sub.add_parser("verify")
    vp.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        build(a) if a.command == "build" else verify(a.out)
    except Refusal as error:
        print("S3 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print(f"S3 FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
