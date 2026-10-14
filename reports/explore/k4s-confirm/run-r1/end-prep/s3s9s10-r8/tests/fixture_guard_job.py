#!/usr/bin/env python3
"""Synthetic world + REAL S3 guard-job fixture builder (r3, END-FULL-F2). Test-only; stdlib only (no pytest).

The synthetic world (shared with conftest.py): a synthetic origin repository with the production paths, the full clone
created by the candidate's own `S9 prepare-clone` (file:// origin), and the session patches of the module constants
that bind real production bytes (pins, commits, REPO_FULL, Q5_SOURCE, ...). Nothing real is read: no repository,
T1 tree, admission, receipt or host.

build_guard_job() / the CLI build ONE guard job through the SHIPPED, unmodified S3 code path (s3_guard_job.build:
committed inputs via safe_input, si.git_run init + depth-1 file:// fetch of the four binding commits, loose
refs/k4s-end/<label>, FETCH_HEAD removed, prove_repo, frozen T1 check, renameat2 publication), so Part B can feed
the actual S3-produced job and its shallow `repo/` into its S5/S7 host checks. The only stand-in input is the S1b
admissions manifest (S3 reads it by SHA; its rows carry the synthetic admissions' SHA-256s, as an S1b run would).

CLI (on 127x05; DIR must be an existing EMPTY directory under /tmp/, S3's permitted output root):
    python3 -I -B tests/fixture_guard_job.py --dir DIR [--host 127x03|127x04] [--round RR --attempt NN | --preflight NN]
prints ONE JSON object (schema FIXTURE_SCHEMA; see build_guard_job) on stdout; exit 0, or 2 with the reason on stderr.
Everything it creates is inside DIR (files 0444: remove with `chmod -R u+w DIR && rm -rf DIR`).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if sys.path[:1] != [ROOT]:
    sys.path.insert(0, ROOT)
# END-FULL-F1: s11_host_repository (r4) is the top of the pin DAG; importing it loads end_prep_common, safe_input, s10,
# s3, s1b and s9 through the canonical bootstrap with their pins (importing a sibling by sys.path first would make the
# bootstrap refuse to reuse that unpinned module).
import s11_host_repository as S11  # noqa: E402

S10 = S11.S10

C, S3, S9 = S10.C, S10.S3, S10.S9
S1B = S3.S1B

si = C.si
HOSTS = ("127x03", "127x04")
CANARY = b"SYNTHETIC-OUTCOME-CANARY-never-to-be-read\n"
ORIG = {}
FIXTURE_SCHEMA = "clasher.k4s.test.s3-guard-job-fixture.v1"


def refused(code, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except si.Refusal as error:
        ok(error.code == code, "expected refusal %r, got %r: %s" % (code, error.code, error))
        return error
    raise AssertionError("expected Refusal(%r); call succeeded" % code)


def ok(condition, message="check failed"):
    """Explicit check (not assert): holds under python -O."""
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_file(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as stream:
        stream.write(data)
    os.chmod(path, mode)
    return path


def read(path):
    with open(path, "rb") as stream:
        return stream.read()


def chmod_tree_writable(path):
    for directory, dirs, files in os.walk(path):
        os.chmod(directory, 0o755)
        for d in dirs:
            p = os.path.join(directory, d)
            if not os.path.islink(p):
                os.chmod(p, 0o755)


def rmtree(path):
    if os.path.lexists(path):
        chmod_tree_writable(path)
        shutil.rmtree(path)


# ---------------------------------------------------------------- git (test harness only; never the candidates)

class Git(object):
    def __init__(self, home):
        self.env = {"PATH": "/usr/bin:/bin", "HOME": home, "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t", "GIT_AUTHOR_DATE": "2026-10-12T00:00:00Z",
                    "GIT_COMMITTER_DATE": "2026-10-12T00:00:00Z"}

    def __call__(self, repo, *args, data=None, env=None):
        full = dict(self.env, **(env or {}))
        result = subprocess.run(["/usr/bin/git", "-C", repo] + list(args), input=data, env=full,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError("git %s: %s" % (args[:2], result.stderr.decode()[-400:]))
        return result.stdout

    def commit(self, repo, files, message, links=None):
        for rel, data in files.items():
            path = os.path.join(repo, rel)
            if data is None:
                self(repo, "rm", "-q", "--", rel)
                continue
            make_file(path, data)
            self(repo, "add", "--", rel)
        for rel, target in (links or {}).items():
            path = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.symlink(target, path)
            self(repo, "add", "--", rel)
        self(repo, "commit", "-q", "--allow-empty", "-m", message)
        return self(repo, "rev-parse", "HEAD").decode().strip()


# ---------------------------------------------------------------- synthetic admissions (pass check_admission)

def bus_admission(host, **identity):
    ident = dict(S1B.BUS_IDENTITY[host], **identity)
    return (json.dumps(dict(utc="2026-10-12T13:30:00Z", host=host, identity=ident, exe_evidence=dict(exe="x"),
                            coordinator_ruling="OP-1 14:45Z"), indent=2) + "\n").encode()


def idle_admission(host="127x03", **identity):
    ident = dict(S1B.IDLE_IDENTITY, **identity)
    service = dict(name=S1B.IDLE_SERVICE_NAME, service=ident, wrapper_trio=[ident, dict(ident, pid=1), dict(ident, pid=2)],
                   commands=["a", "b", "c"])
    return (json.dumps(dict(utc="2026-10-12T13:31:00Z", host=host, services=[service]), indent=2) + "\n").encode()


def admissions(host):
    out = {"system-bus-admission.json": bus_admission(host)}
    if host == "127x03":
        out["idle-services.json"] = idle_admission()
    return out


# ---------------------------------------------------------------- synthetic frozen modules

PREPARE_BUNDLE = b'''import hashlib, json
from pathlib import Path
import receipts, tier_backend
def runtime_pins(root):
    root = Path(root)
    names = set(json.loads((root / "reports/explore/s1/receipts/runtime-pin-r2.json").read_text())["files"])
    names.update(str(p.relative_to(root)) for p in root.rglob("*.py"))
    missing = sorted(n for n in names if not (root / n).is_file())
    if missing:
        raise ValueError("Incomplete frozen runtime: " + repr(missing[:8]))
    return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in sorted(names)}
'''
K4S_LOGIC = b'''import hashlib, json
from pathlib import Path
def load_k4s_manifest(path, expected_sha256, runtime_root, *, require_frozen):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("K4S manifest SHA mismatch")
    manifest = json.loads(raw)
    for key in ("k4s_files", "end_files", "reused_readonly"):
        for name, pin in manifest[key].items():
            if hashlib.sha256((Path(runtime_root) / name).read_bytes()).hexdigest() != pin:
                raise ValueError("Pin mismatch " + name)
    if require_frozen and manifest.get("frozen") is not True:
        raise ValueError("not frozen")
    return manifest
'''
PARENT_SOURCE_SEED = b'''import hashlib, json, subprocess
from pathlib import Path
def committed_binding(repository, checkout, freeze, binding, prefix):
    out = subprocess.run(["git", "-C", str(repository), "show", binding["commit"] + ":" + binding["path"]],
                         stdout=subprocess.PIPE, check=True).stdout
    assert hashlib.sha256(out).hexdigest() == binding["sha256"]
    assert (Path(checkout) / binding["path"]).read_bytes() == out
    return json.loads(out)
def admit(job, accepted, args):
    Path(job, "parent-source-seed-admission.json").write_text(json.dumps({"host": "127x05"}))
    return []
'''
E4V3 = S9.E4V3_REL
MAC = S9.K4S_MAC_REL
T1 = "reports/explore/t1"


def world_files():
    """The tracked files of the synthetic base commit (production paths)."""
    files = {
        E4V3 + "/prepare_bundle.py": PREPARE_BUNDLE,
        E4V3 + "/tier_backend.py": b"TIER = 1\n",
        E4V3 + "/receipts.py": b"RECEIPTS = 1\n",
        E4V3 + "/measure_tiers.py": b"MEASURE = 1\n",
        E4V3 + "/build_tiers.sh": b"#!/bin/sh\necho build\n",
        E4V3 + "/spec-pins.json": b'{"spec": 1}\n',
        E4V3 + "/README.md": b"not in the measurement rule\n",
        MAC + "/k4s_logic.py": K4S_LOGIC,
        MAC + "/K4S-MAC-PROCEDURE.md": b"procedure\n",
        "examples/visualize_battle.py": b"print('visualize')\n",
        "src/clasher/__init__.py": b"",
        "src/clasher/core.py": b"CORE = 1\n",
        "src/clasher/tool.py": b"#!/usr/bin/env python3\nTOOL = 1\n",
        "data/catalog.json": b'{"catalog": 1}\n',
        "data/stale.json": b'{"stale": "git bytes"}\n',
        "docs/notes.md": b"non-member\n",
        E5_PATH: E5_BYTES,
        S9.SD1_REL: b'{"sd1": "synthetic SD1 manifest"}\n',
        S9.CORPORA_REL: b'{"corpora": "synthetic t1 corpus inventory"}\n',
        S9.DELTA_REL: b'{"files": {}, "synthetic": "DELTA-MANIFEST"}\n',
        S1B.HISTORY: (json.dumps([{"namespace": "k4s-confirm-reporting-r1", "phase": "reporting"},
                                  {"namespace": S1B.NAMESPACE, "phase": "replacement-r4"}]) + "\n").encode(),
    }
    for m in S3.GUARD_MODULES:
        files["%s/%s.py" % (T1, m)] = PARENT_SOURCE_SEED if m == "parent_source_seed" else ("M = %r\n" % m).encode()
    return files


E5_PATH = "scripts/compare_native_public_games.py"            # one of the nine ruled E5 paths (synthetic bytes)
E5_BYTES = b"SYNTHETIC_E5_STAND_IN = 1\n"


def blob_oid(data):
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


EXTERNALS = {"student-source/exit_r3/__init__.py": b"STUDENT = 1\n",
             "src/clasher/analysis/loss_review/tempo.py": b"TEMPO = 1\n",
             "reports/strategy_council_20260928/m0/data/roles_v2/training.json": b'{"training": 1}\n'}


def k4s_manifest(files):
    def pin(rel):
        return sha(files[rel])
    doc = {"schema": "clasher.k4s.mac-manifest.v1", "frozen": True,
           "k4s_files": {MAC + "/k4s_logic.py": pin(MAC + "/k4s_logic.py")}, "end_files": {},
           "reused_readonly": {MAC + "/K4S-MAC-PROCEDURE.md": pin(MAC + "/K4S-MAC-PROCEDURE.md"),
                               E4V3 + "/spec-pins.json": pin(E4V3 + "/spec-pins.json"),
                               E4V3 + "/measure_tiers.py": pin(E4V3 + "/measure_tiers.py")},
           "measure_tiers_unmodified": {"path": E4V3 + "/measure_tiers.py", "sha256": pin(E4V3 + "/measure_tiers.py")},
           "sd1_manifest": {"path": S9.SD1_REL, "sha256": pin(S9.SD1_REL)},
           "references": {"t1_corpus_inventory": {"path": S9.CORPORA_REL, "sha256": pin(S9.CORPORA_REL)}},
           "corpus": {"inventory": S9.CORPORA_REL},
           "k4s_kernel": {"files": {E4V3 + "/receipts.py": pin(E4V3 + "/receipts.py")}}}
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def measurement_of(files):
    out = {}
    for rel, data in files.items():
        if rel.startswith(E4V3 + "/") and "/" not in rel[len(E4V3) + 1:]:
            name = rel[len(E4V3) + 1:]
            if name.endswith((".py", ".sh")) or name == "spec-pins.json":
                out[name] = sha(data)
    return C.canonical_sha(dict(sorted(out.items())))


# ---------------------------------------------------------------- the session world

class World(object):
    pass


def restore():
    for (module_name, name), value in ORIG.items():
        if module_name == "receive_ns":
            si._RECEIVE_NS[name] = value
        else:
            setattr(sys.modules[module_name], name, value)


def _patch(module, name, value):
    ORIG.setdefault((module.__name__, name), getattr(module, name))
    setattr(module, name, value)




def _world(work):
    w = World()
    w.work = work
    w.home = os.path.join(w.work, "home")
    os.makedirs(w.home)
    w.git = git = Git(w.home)
    w.origin = os.path.join(w.work, "origin")
    os.makedirs(w.origin)
    git(w.origin, "init", "-q", "--template=")
    git(w.origin, "symbolic-ref", "HEAD", "refs/heads/main")
    files = world_files()
    base = git.commit(w.origin, files, "base", links={si.E1_ALIAS: si.E1_LINK_TEXT})
    # seed/join binding commits (the 08 seed names its two joins by commit)
    joins, seeds = [], []
    for label, rel, host in (("join-08-server", T1 + "/receipts/op5-parent-generation-127x08.json", "127x08"),
                             ("join-08-client", "reports/strategy_council_20260928/live-loop/v4/l1/receipts/"
                              "a21-a2-preparation-20261010-r1/08-transport-identity-20261010T172047Z.json", "127x08")):
        data = (json.dumps({"host": host, "label": label}) + "\n").encode()
        commit = git.commit(w.origin, {rel: data}, label)
        joins.append(dict(label=label, path=rel, commit=commit, sha256=sha(data), prefix=rel.rsplit("/", 1)[0] + "/"))
    s03 = (json.dumps({"host": "127x03"}) + "\n").encode()
    c03 = git.commit(w.origin, {T1 + "/receipts/op5-parent-source-127x03.json": s03}, "seed-03")
    s08 = (json.dumps({"host": "127x08", "source_join": {
        "server": {k: joins[0][k] for k in ("path", "commit", "sha256")},
        "client": {k: joins[1][k] for k in ("path", "commit", "sha256")}}}) + "\n").encode()
    c08 = git.commit(w.origin, {T1 + "/receipts/op5-parent-source-127x08.json": s08}, "seed-08")
    seeds = [dict(label="seed-03", path=T1 + "/receipts/op5-parent-source-127x03.json", commit=c03, sha256=sha(s03),
                  prefix=T1 + "/receipts/"),
             dict(label="seed-08", path=T1 + "/receipts/op5-parent-source-127x08.json", commit=c08, sha256=sha(s08),
                  prefix=T1 + "/receipts/")]
    w.seeds, w.joins = tuple(seeds), tuple(joins)
    # pins, K4S manifest, freeze
    all_files = dict(files)
    pins = {rel: sha(all_files[rel]) for rel in ("data/catalog.json", "src/clasher/core.py", E4V3 + "/receipts.py")}
    pins["data/stale.json"] = sha(b"a different runtime-pin-r2 byte string\n")       # tracked pin != git bytes
    pins.update({rel: sha(data) for rel, data in EXTERNALS.items()})
    runtime_pin = (json.dumps({"files": pins}, indent=1, sort_keys=True) + "\n").encode()
    qualified = (json.dumps({"qualified_source_files": {"src/clasher/core.py": sha(files["src/clasher/core.py"])}},
                            indent=1) + "\n").encode()
    manifest = k4s_manifest(all_files)
    module_pins = {"%s/%s.py" % (T1, m): sha(all_files["%s/%s.py" % (T1, m)]) for m in S3.GUARD_MODULES}
    freeze = {"files": dict(module_pins, **{b["path"]: b["sha256"] for b in seeds + joins}),
              "parent_source_seeds": [{k: s[k] for k in ("path", "commit", "sha256")} for s in seeds]}
    for delta in S3.GUARD_DELTAS:
        freeze[delta] = {"verdict": "CONFIRM"}
    freeze_raw = (json.dumps(freeze, indent=1, sort_keys=True) + "\n").encode()
    w.pins_commit = git.commit(w.origin, {S9.RUNTIME_PIN_REL: runtime_pin, S9.QUALIFIED_REL: qualified,
                                          S9.K4S_MANIFEST_REL: manifest, S3.FREEZE_REL: freeze_raw}, "pins")
    # E3 committed admissions (the bytes S1b copies from the fake hosts below)
    adm = {"%s/%s" % (si.E3_ADMISSIONS_DIR, S1B.e3_name(h, n)): data for h in HOSTS for n, data in admissions(h).items()}
    w.P = git.commit(w.origin, adm, "evidence P")
    w.X = git.commit(w.origin, {S9.END_JOB_REL: b'{"end_job": 1}\n'}, "END-JOB X")
    # r4: the END branch (BR-1) at P; the session clone below therefore has refs/remotes/origin/k4s-end-r1 = P
    git(w.origin, "update-ref", "refs/heads/" + S9.END_BRANCH, w.P)
    w.base_commit = base
    w.files = dict(all_files, **{S9.RUNTIME_PIN_REL: runtime_pin, S9.QUALIFIED_REL: qualified,
                                 S9.K4S_MANIFEST_REL: manifest, S3.FREEZE_REL: freeze_raw})
    w.pins = pins
    # the Q5 source with the externals
    w.q5 = os.path.join(w.work, "q5", "runtime")
    for rel, data in EXTERNALS.items():
        make_file(os.path.join(w.q5, rel), data)
    # session patches: synthetic world constants (production code paths unchanged)
    w.end_prep = os.path.join(w.work, "end-prep")
    os.makedirs(w.end_prep)
    _patch(S9, "REPO_FULL", os.path.join(w.end_prep, "repo-full"))
    _patch(S3, "REPO_FULL", S9.REPO_FULL)
    _patch(S9, "ORIGIN_URL", "file://" + w.origin)
    _patch(S9, "CLONE_PROTOCOL", "file")
    _patch(S9, "BASE_COMMIT", base)
    _patch(S9, "RUNTIME_PIN_SHA", sha(runtime_pin))
    _patch(S9, "QUALIFIED_SHA", sha(qualified))
    _patch(S9, "K4S_MANIFEST_SHA", sha(manifest))
    _patch(S9, "MEASUREMENT_SHA", measurement_of(all_files))
    _patch(S9, "EXTERNAL", frozenset(EXTERNALS))
    _patch(S9, "Q5_SOURCE", w.q5)
    _patch(S9, "DEFAULT_PYTHON", sys.executable)
    _patch(S9, "SUPPORT_PINS", {rel: sha(files[rel]) for rel in S9.SUPPORT_PINS})   # r4: synthetic bytes, same paths
    _patch(S3, "FROZEN_T1_SHA", sha(freeze_raw))
    _patch(S3, "SEEDS", tuple(seeds))
    _patch(S3, "JOINS", tuple(joins))
    _patch(S3, "BINDINGS", tuple(seeds) + tuple(joins))
    _patch(S3, "Q3_COMMITS", (c03, c08))
    _patch(S3, "DEFAULT_PYTHON", sys.executable)
    _patch(S1B, "HISTORY_SHA256", sha(files[S1B.HISTORY]))
    # E5 (r3): the synthetic stand-in's blob OID replaces the ruled OID of that one path (OIDs only, as the r3 tests
    # do); the shipped receive program carries its own pins, so its text is patched the same way.
    real = dict(si.E5_RUNTIME_MEMBERS)[E5_PATH]
    pairs = tuple((p, blob_oid(E5_BYTES) if p == E5_PATH else o) for p, o in si.E5_RUNTIME_MEMBERS)
    _patch(si, "E5_RUNTIME_MEMBERS", pairs)
    ORIG.setdefault(("receive_ns", "E5_RUNTIME_MEMBERS"), si._RECEIVE_NS["E5_RUNTIME_MEMBERS"])
    si._RECEIVE_NS["E5_RUNTIME_MEMBERS"] = pairs
    shipped = ORIG.get(("safe_input", "receive_program_source"), si.receive_program_source)()
    ok(shipped.count(real) == 1)
    shipped = shipped.replace(real, blob_oid(E5_BYTES))
    _patch(si, "receive_program_source", lambda: shipped)
    w.python = sys.executable
    # the full clone, through the candidate itself
    S9.prepare_clone(type("A", (), {"commit": w.P})(), log=lambda *a: None)
    w.repo_full = S9.REPO_FULL
    # r4: X2 = P + END-JOB, made AFTER the session clone (so the clone lacks its objects) and NOT on any origin branch
    # until a test advances refs/heads/k4s-end-r1 to it (refresh-clone / S11 advance tests; reset afterwards).
    w.end_job2 = b'{"end_job": 2, "synthetic": true}\n'
    w.X2 = commit_on(git, w.origin, w.P, {S9.END_JOB_REL: w.end_job2}, "END-JOB X2 (k4s-end-r1)")
    return w


def commit_on(git, repo, parent, files, message):
    """A commit = parent + files, made with plumbing in a private index (no ref, no work-tree change)."""
    index = os.path.join(os.path.dirname(repo), "index-%s" % sha(message.encode())[:8])
    env = {"GIT_INDEX_FILE": index}
    git(repo, "read-tree", parent, env=env)
    for rel, data in files.items():
        oid = git(repo, "hash-object", "-w", "--stdin", data=data).decode().strip()
        git(repo, "update-index", "--add", "--cacheinfo", "100644,%s,%s" % (oid, rel), env=env)
    tree = git(repo, "write-tree", env=env).decode().strip()
    os.unlink(index)
    return git(repo, "commit-tree", tree, "-p", parent, "-m", message).decode().strip()


# ---------------------------------------------------------------- the REAL S3 guard job (END-FULL-F2)

class Args(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def synthetic_s1b_manifest(directory):
    """The S1b admissions manifest S3 consumes (exact name; read by SHA): one exact-path single-link row per synthetic
    admission of both hosts. Returns (path, sha256)."""
    rows = []
    for host in HOSTS:
        for name, data in sorted(admissions(host).items()):
            rows.append(dict(host=host, name=name, remote_path="%s/%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE, name),
                             remote_size=len(data), remote_sha256=sha(data), remote_nlink=1,
                             local_path="%s/%s" % (S1B.E3_LOCAL, S1B.e3_name(host, name)), local_sha256=sha(data)))
    doc = dict(schema=S1B.SCHEMA, status="copied", files=rows,
               fixture="SYNTHETIC-TEST-ONLY: stand-in for an S1b run (tests/fixture_guard_job.py)")
    raw = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    path = make_file(os.path.join(directory, S3.S1B_MANIFEST), raw, 0o444)
    return path, sha(raw)


def guard_job_facts(world, out, manifest, host):
    """The JSON-able description of a built guard job (the CLI's stdout)."""
    job_dir = os.path.join(out, manifest["job_name"])
    repo_dir = os.path.join(job_dir, "repo")
    with open(os.path.join(repo_dir, ".git", "shallow")) as stream:
        shallow = sorted(stream.read().split())
    return dict(
        schema=FIXTURE_SCHEMA, synthetic=True, host=host, job_name=manifest["job_name"], job=manifest["job"],
        target_job=manifest["target_job"], out=out, job_dir=job_dir, repo_dir=repo_dir,
        manifest_path=os.path.join(out, S3.MANIFEST), manifest_sha256=manifest["_sha256"],
        top_level=manifest["top_level"], inventory_sha256=manifest["inventory_sha256"],
        bindings=manifest["bindings"], q3_commits=manifest["q3_commits"],
        refs={"refs/k4s-end/" + b["label"]: b["commit"] for b in manifest["bindings"]}, shallow=shallow,
        frozen_t1_sha256=manifest["frozen_t1_sha256"],
        admissions={n: e["sha256"] for n, e in sorted(manifest["admissions"].items())},
        git_config_keys=sorted(S3.GUARD_GIT_CONFIG_KEYS), git_dirs=list(S3.GIT_DIRS),
        world=dict(work=world.work, origin=world.origin, repo_full=world.repo_full, commit=world.P),
        code_sha256=dict(s3_guard_job=sha(read(os.path.join(ROOT, "s3_guard_job.py"))),
                         safe_input=C.SAFE_INPUT_SHA256),
        note="synthetic seed/join commits and SHAs: the job matches the PATCHED S3 constants (bindings above), "
             "not the production pins")


def build_guard_job(base, host="127x03", round_="00", attempt="00", preflight=None):
    """Build the synthetic world in <base>/world (patching the module constants: call restore() afterwards when
    used in-process), a stand-in S1b manifest in <base>/s1b, and ONE guard job with the shipped S3.build into
    <base>/guard. `base` must be an existing empty directory under /tmp/. Returns guard_job_facts()."""
    base = os.path.realpath(base)
    ok(base.startswith("/tmp/") and os.path.isdir(base) and not os.listdir(base),
       "--dir must be an existing empty directory under /tmp/ (S3 output root): %r" % base)
    work = os.path.join(base, "world")
    os.makedirs(work)
    world = _world(work)
    s1b_dir = os.path.join(base, "s1b")
    os.makedirs(s1b_dir)
    s1b_path, s1b_sha = synthetic_s1b_manifest(s1b_dir)
    out = os.path.join(base, "guard")
    a = Args(host=host, round=None if preflight else round_, attempt=None if preflight else attempt,
             preflight=preflight, commit=world.P, s1b_manifest=s1b_path, s1b_manifest_sha256=s1b_sha, out=out,
             python=sys.executable)
    manifest = S3.build(a, log=lambda *x: None)
    return guard_job_facts(world, out, manifest, host)


def main(argv=None):
    ap = argparse.ArgumentParser(description="build ONE synthetic guard job with the shipped S3 code path")
    ap.add_argument("--dir", required=True, help="existing empty directory under /tmp/")
    ap.add_argument("--host", default="127x03", choices=HOSTS)
    ap.add_argument("--round", default="00")
    ap.add_argument("--attempt", default="00")
    ap.add_argument("--preflight")
    a = ap.parse_args(argv)
    try:
        facts = build_guard_job(a.dir, a.host, a.round, a.attempt, a.preflight)
    except (si.Refusal, AssertionError, OSError, RuntimeError) as error:
        print("fixture_guard_job: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 2
    finally:
        restore()
    print(json.dumps(facts, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
