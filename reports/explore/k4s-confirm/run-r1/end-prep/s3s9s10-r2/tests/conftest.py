"""Offline fixtures for the S1b / S3 / S9 / S10 r2 candidates. Fully SYNTHETIC: no real repository, T1 tree, admission,
receipt or host is read. Everything is written under one tempfile directory in /tmp (neutral names, removed at the end).

* World: a synthetic origin repository (branch main) with the production paths of the pin lists, the K4S manifest,
  e4v3, the E1 link, FROZEN-T1, the T1 modules, seed/join receipts and history.json; synthetic frozen modules that
  implement the frozen rules; the full clone is created by the candidate's own `S9 prepare-clone` (file:// origin).
  Module constants that bind real production bytes (pins, commits, REPO_FULL, Q5_SOURCE, ...) are patched for the
  whole session to the synthetic values; ORIG keeps the production values for the constant tests.
* Fake hosts: a fake ssh that runs the remote words in a user+mount+UTS namespace (`unshare -Urmu`) whose
  /mpac/sdicks02 is a bind mount of FAKE/<host> and whose hostname is the host: the shipped safe_input programs run
  unmodified, including their node-name check; the real /mpac/sdicks02 is invisible to them.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import end_prep_common as C  # noqa: E402
import s1b_copy_admissions as S1B  # noqa: E402
import s3_guard_job as S3  # noqa: E402
import s9_end_runtime as S9  # noqa: E402
import s10_stage_host as S10  # noqa: E402

si = C.si
HOSTS = ("127x03", "127x04")
CANARY = b"SYNTHETIC-OUTCOME-CANARY-never-to-be-read\n"
ORIG = {}


def ok(condition, message="check failed"):
    """Explicit check (not assert): holds under python -O."""
    if not condition:
        raise AssertionError(message)


def refused(code, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except si.Refusal as error:
        ok(error.code == code, "expected refusal %r, got %r: %s" % (code, error.code, error))
        return error
    raise AssertionError("expected Refusal(%r); call succeeded" % code)


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
           "sd1_manifest": {"sha256": "1" * 64}, "k4s_kernel": {"files": {E4V3 + "/receipts.py": pin(E4V3 + "/receipts.py")}}}
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def measurement_of(files):
    out = {}
    for rel, data in files.items():
        if rel.startswith(E4V3 + "/") and "/" not in rel[len(E4V3) + 1:]:
            name = rel[len(E4V3) + 1:]
            if name.endswith((".py", ".sh")) or name == "spec-pins.json":
                out[name] = sha(data)
    return C.canonical_sha(dict(sorted(out.items())))


# ---------------------------------------------------------------- fake ssh (namespaced fake hosts)

SHIM = r'''#!/usr/bin/python3 -IS
# Fake ssh for the S1b/S10 r2 tests only: hygiene options required; the remote words run under /bin/sh in a
# user+mount+UTS namespace whose /mpac/sdicks02 is a bind mount of ROOT/<host> and whose hostname is <host>.
import os, subprocess, sys
LOG, ROOT, MODE, FAILAT = @LOG@, @ROOT@, @MODE@, @FAILAT@
argv = sys.argv[1:]
with open(LOG, "a") as stream:
    stream.write(" ".join(argv).replace("\n", "~") + "\n")
with open(LOG) as stream:
    n = sum(1 for _ in stream)
words = " " + " ".join(argv) + " "
for need in ("BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes"):
    if " " + need + " " not in words:
        sys.stderr.write("shim: missing %s\n" % need)
        sys.exit(255)
i = argv.index("--")
host, command = argv[i + 1], " ".join(argv[i + 2:])
if FAILAT is not None and n == FAILAT:
    sys.stdin.buffer.read()
    sys.stderr.write("shim: connection refused\n")
    sys.exit(255)
inner = 'mount --bind "$1" /mpac/sdicks02 && hostname "$2" && cd / && exec /bin/sh -c "$3"'
done = subprocess.run(["/usr/bin/unshare", "-Urmu", "/bin/sh", "-c", inner, "shim", ROOT + "/" + host, host, command],
                      env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, stdout=subprocess.PIPE)
out = done.stdout
if MODE == "junk" and n == (FAILAT or n):
    out += b"junk"
elif MODE == "flip" and b'"content_b64":"' in out:
    k = out.index(b'"content_b64":"') + len(b'"content_b64":"') + 4
    out = out[:k] + (b"A" if out[k:k + 1] != b"A" else b"B") + out[k + 1:]
sys.stdout.buffer.write(out)
sys.exit(done.returncode)
'''


class FakeHosts(object):
    def __init__(self, base, fail_at=None, mode=None):
        self.base = base
        self.root = os.path.join(base, "hosts")
        self.log = os.path.join(base, "ssh.log")
        self.ssh = os.path.join(base, "ssh")
        for host in HOSTS:
            for parent in ("jobs/clasher", "jobs-k4s"):
                os.makedirs(os.path.join(self.root, host, parent), exist_ok=True)
        os.makedirs(os.path.join(self.root, "127x04", "jobs", "perception-never-touch"), exist_ok=True)
        self.write_shim(fail_at, mode)

    def write_shim(self, fail_at=None, mode=None):
        text = (SHIM.replace("@LOG@", repr(self.log)).replace("@ROOT@", repr(self.root))
                .replace("@MODE@", repr(mode)).replace("@FAILAT@", repr(fail_at)))
        with open(self.ssh, "w") as stream:
            stream.write(text)
        os.chmod(self.ssh, 0o755)

    def path(self, host, remote):
        ok(remote.startswith("/mpac/sdicks02/"), remote)
        return os.path.join(self.root, host, remote[len("/mpac/sdicks02/"):])

    def logins(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as stream:
            return [line.rstrip("\n") for line in stream]

    def tool(self, host, name, script):
        """A fake host tool at /mpac/sdicks02/fakebin/<name> (inside the namespace)."""
        path = make_file(os.path.join(self.root, host, "fakebin", name), script.encode(), 0o755)
        return "/mpac/sdicks02/fakebin/" + name, path


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


@pytest.fixture(scope="session")
def world():
    work = os.path.realpath(tempfile.mkdtemp(prefix="k4s-r2t-", dir="/tmp"))
    try:
        w = _world(work)
    except BaseException:
        restore()
        rmtree(work)
        raise
    yield w
    restore()
    rmtree(w.work)


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
    return w


@pytest.fixture
def tmpdir_(world):
    """A fresh neutral-named directory inside the session work dir (never a test-name path)."""
    path = tempfile.mkdtemp(prefix="t-", dir=world.work)
    yield path
    rmtree(path)


@pytest.fixture
def hosts(world):
    base = tempfile.mkdtemp(prefix="fh-", dir=world.work)
    fake = FakeHosts(base)
    for host in HOSTS:
        job = fake.path(host, "%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE))
        for name, data in admissions(host).items():
            make_file(os.path.join(job, name), data)
    old = (S1B.SSH_BINARY, S10.SSH_BINARY, dict(S10.REMOTE_TOOLS))
    S1B.SSH_BINARY = S10.SSH_BINARY = fake.ssh
    yield fake
    S1B.SSH_BINARY, S10.SSH_BINARY = old[0], old[1]
    S10.REMOTE_TOOLS.clear()
    S10.REMOTE_TOOLS.update(old[2])
    rmtree(base)


class Args(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def s1b_args(world, dest, **kw):
    base = dict(repository=world.repo_full, commit=world.P, dest=dest, outside_end_window="TEST GO ref",
                dry_run=False)
    base.update(kw)
    return Args(**base)


@pytest.fixture(scope="session")
def s1b_out(world):
    """One real S1b run against fake hosts (session): the admissions + manifest S3 consumes."""
    base = tempfile.mkdtemp(prefix="s1b-", dir=world.work)
    fake = FakeHosts(base)
    for host in HOSTS:
        job = fake.path(host, "%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE))
        for name, data in admissions(host).items():
            make_file(os.path.join(job, name), data)
    old = S1B.SSH_BINARY
    S1B.SSH_BINARY = fake.ssh
    try:
        dest = os.path.join(base, "dest")
        S1B.run(s1b_args(world, dest), log=lambda *a: None)
    finally:
        S1B.SSH_BINARY = old
    manifest = os.path.join(dest, "s1b-admissions-manifest.json")
    return dict(dest=dest, manifest=manifest, sha=sha(read(manifest)), logins=fake.logins())


def s3_args(world, s1b, out, host="127x03", round_="00", attempt="00", preflight=None, **kw):
    base = dict(host=host, round=None if preflight else round_, attempt=None if preflight else attempt,
                preflight=preflight, commit=world.P, s1b_manifest=s1b["manifest"], s1b_manifest_sha256=s1b["sha"],
                out=out, python=world.python)
    base.update(kw)
    return Args(**base)


@pytest.fixture(scope="session")
def guard03(world, s1b_out):
    out = os.path.join(tempfile.mkdtemp(prefix="g03-", dir=world.work), "guard")
    manifest = S3.build(s3_args(world, s1b_out, out), log=lambda *a: None)
    return dict(out=out, job=manifest["job_name"], sha=manifest["_sha256"], manifest=manifest)


@pytest.fixture(scope="session")
def runtime(world):
    out = os.path.join(tempfile.mkdtemp(prefix="rt-", dir=world.work), "runtime-P")
    manifest = S9.build(Args(commit=world.P, out=out, python=world.python), log=lambda *a: None)
    return dict(out=out, sha=manifest["_sha256"], manifest=manifest)


PRODUCTION_FILES = {"v1.pt": b"synthetic v1 model\n", "R3a.pt": b"synthetic R3a model\n",
                    "R3a-calibration.json": b'{"calibration": 1}\n', "states.pkl": b"synthetic states\n",
                    "states-rows.json": b'{"rows": 1}\n', "states-rows.bin": b"\x00\x01rows"}


def make_bundle(world, parent, name, host, runtime_manifest, guard=None, synthetic=False, receipt_overrides=None,
                manifest_overrides=None, freeze_bytes=None):
    """A synthetic S4-shaped fleet-reference bundle (schema/profile/receipt as S4 r3b writes them)."""
    root = os.path.join(parent, name)
    files = dict(PRODUCTION_FILES)
    guard_job = (guard["manifest"]["target_job"] if guard else S3.GUARD_PARENTS[host] + "/k4s-end-guard-r1-rd00-a00")
    adm_map = {}
    for n in S1B.NAMES[host]:
        rel = "t1-guard/guard-admissions/" + n
        files[rel] = admissions(host)[n]
        adm_map[n] = rel
    files["t1-guard/t1-freeze.json"] = freeze_bytes or world.files[S3.FREEZE_REL]
    seed_map = {}
    for b in S3.BINDINGS:
        rel = "t1-guard/seed-inputs/" + b["path"]
        files[rel] = world.git(world.origin, "show", b["commit"] + ":" + b["path"])
        seed_map[b["path"]] = rel
    for rel, data in files.items():
        make_file(os.path.join(root, rel), data, 0o444)
    manifest = dict(schema=S10.BUNDLE_SCHEMA, final=False, profile="fleet-reference",
                    files={rel: sha(data) for rel, data in files.items()},
                    runtime_files=runtime_manifest["runtime_files"],
                    measurement_files=runtime_manifest["measurement_files"],
                    reference_load_profile=dict(host=host, guard=dict(root="t1-guard", job=guard_job,
                                                                      freeze="t1-guard/t1-freeze.json",
                                                                      admissions=adm_map, seed_inputs=seed_map)))
    if synthetic:
        manifest["k4s_s4_synthetic"] = "SYNTHETIC-TEST-ONLY"
    manifest.update(manifest_overrides or {})
    raw = (C.canonical(manifest) + "\n").encode()
    make_file(os.path.join(root, "tiers-pins.json"), raw, 0o444)
    make_file(os.path.join(root, "tiers-pins.sha256"), ("%s  tiers-pins.json\n" % sha(raw)).encode(), 0o444)
    receipt = dict(schema=S10.ASSEMBLY_SCHEMA, manifest_sha256=sha(raw), host=host, guard_job=guard_job,
                   production_pins=not synthetic, final=False, outcomes_read=False, live_actions=False,
                   status="SYNTHETIC-TEST-ONLY" if synthetic else "CANDIDATE")
    receipt.update(receipt_overrides or {})
    rraw = (C.canonical(receipt) + "\n").encode()
    make_file(os.path.join(root, "assembly-receipt.json"), rraw, 0o444)
    return dict(dir=root, tiers=sha(raw), receipt=sha(rraw), name=name)


@pytest.fixture(scope="session", autouse=True)
def production_pins_patch(world):
    """S10 production identities -> the synthetic bundle bytes (session); ORIG keeps the real ones."""
    pins = {name: sha(data) for name, data in PRODUCTION_FILES.items()}
    _patch(S10, "PRODUCTION_PINS", pins)
    yield


def s10_args(**kw):
    base = dict(host="127x03", runtime=None, runtime_manifest_for_checks=None, runtime_manifest_sha256=None,
                bundle=None, guard_job=None, guard_job_name=None, guard_manifest_sha256=None, create_base=False,
                record=None, outside_end_window="TEST A2 GO", dry_run=False, print_roots=False)
    base.update(kw)
    return Args(**base)


def run_py(script, *args, optimize=None):
    """Run a candidate as a subprocess (-I -B; -O when pytest runs under -O), cwd /tmp."""
    flags = ["-I", "-B"] + (["-O"] * (sys.flags.optimize if optimize is None else optimize))
    return subprocess.run([sys.executable] + flags + [os.path.join(ROOT, script)] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/tmp")


def canary_file(directory, name="canary.json"):
    return make_file(os.path.join(directory, name), CANARY, 0o644)
