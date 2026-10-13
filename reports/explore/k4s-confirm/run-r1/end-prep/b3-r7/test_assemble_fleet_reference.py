"""Offline tests for assemble_fleet_reference.py (CANDIDATE b3-r3b). No host, no SSH, no outcomes.

Checks use ok() (an explicit raise), never a bare assert, so the suite keeps its force under `python -O`; the
frozen-consumer subprocesses inherit -O (frozen_python).

Groups:
- synthetic: every input is generated in a temp dir, with a synthetic git repository for the committed evidence and
  admissions, and the TEST-ONLY pins switch (K4S_S4_SYNTHETIC_PINS -> a pins file marked SYNTHETIC). Covers the happy
  path, every fail-closed branch, determinism, input immutability, and the r2 controls: confinement before any read
  (S4-F1; canaries are mode 000 and every open is recorded), production pins (S4-F2) and the StateRows mirror (S4-F3).
  r3 (SOL-REVIEW-END-PKG1-r2): hard-link inode canaries in every input class (S4-R2-F1), the strict END namespace and
  auxiliary locations (S4-R2-F2), confined synthetic pins (S4-R2-F3) and the E1-E3 rulings. r3b: ruling E4 (the
  exact four-entry complete.json exempt list, at the --repository HEAD tree and in the runtime tree). An in-process audit hook
  records the inode of every file opened, so "never opened" is checked by inode, not just by path name.
- frozen consumers: need K4S_FROZEN_ROOT = a read-only checkout of origin/main. They take the real frozen bytes and run
  the frozen consumers in fresh subprocesses: prepare_bundle.runtime_pins (parity, alias + exception included),
  tier_backend.validate_bundle, state_rows.StateRows (also on every index mutant: same verdict as the assembler),
  fleet_validity.ReportingGuard.__init__, fleet_profile.slot_layout and telemetry.validate_topology.
- production bytes on 05 (read-only; skipped elsewhere): the Q6 index bytes equal their pin and pass both the
  assembler's mirror and frozen StateRows (sparse stand-in container of the pinned size; no pickle is loaded); T1's
  committed own-tier sets equal the sets pin and lie inside the real index.
"""
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("assemble_fleet_reference", HERE / "assemble_fleet_reference.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

E4V3_REL = A.E4V3_REL
FROZEN = os.environ.get("K4S_FROZEN_ROOT")
HOST = "127x03"
JOB = "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00"
JOB_04 = "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00"
GUARD_FILES = [m + ".py" for m in A.GUARD_MODULES]
SEED_03 = "reports/explore/t1/receipts/op5-parent-source-127x03.json"
SEED_08 = "reports/explore/t1/receipts/op5-parent-source-127x08.json"
SEED_SERVER = "reports/explore/t1/receipts/op5-parent-generation-127x08.json"
SEED_CLIENT = ("reports/strategy_council_20260928/live-loop/v4/l1/receipts/a21-a2-preparation-20261010-r1/"
               "08-transport-identity-20261010T172047Z.json")
SEEDS = (SEED_03, SEED_08, SEED_SERVER, SEED_CLIENT)
ALIAS, ALIAS_TARGET = "visualize_battle.py", "examples/visualize_battle.py"
EXCEPTION = "imitation/model/receipts/throughput-0935/complete.json"
E4 = {                                       # COORDINATOR 2026-10-12 17:12Z ruling E4 (typed here, not taken from A)
    EXCEPTION: "d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc",
    "reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json":
        "0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json":
        "9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81",
    "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json":
        "724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d",
}
E4_OTHERS = sorted(set(E4) - {EXCEPTION})
REAL_E4 = dict(A.si.E4_COMPLETE_JSON)                 # the layer's production values, captured at import
REAL_E4_OIDS = dict(A.si.E4_GIT_BLOB_OIDS)
ADMISSION_REL = "reports/explore/k4s-confirm/end-guard-admissions/{host}-{name}"
GIT = ["git", "-c", "user.name=synthetic", "-c", "user.email=synthetic@invalid", "-c", "commit.gpgsign=false"]
Q6_DIR = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle")


def ok(condition, message="check failed"):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fsha(path):
    return sha(Path(path).read_bytes())


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_symlink():
        os.chmod(path, 0o644)
    path.write_bytes(data if isinstance(data, bytes) else (json.dumps(data, indent=1) + "\n").encode())
    return path


def entry(path):
    return dict(source=str(path), sha256=fsha(path))


def canary(path, data=b"CANARY: must never be read\n"):
    """A forbidden file the assembler must never open (mode 000: any read would also fail loudly)."""
    path = put(path, data)
    os.chmod(path, 0)
    return path


# ---------------------------------------------------------------- synthetic world

def blob_oid(data):
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def synthetic_e4(monkeypatch, data_by_path):
    """r4: E4 is safe_input's (paths, SHAs and git blob OIDs). Synthetic E4 bytes need the layer's SHA and OID pins
    patched IN THIS TEST ONLY (monkeypatch restores them); the paths can never change (check_exemptions)."""
    for name, data in data_by_path.items():
        monkeypatch.setitem(A.si.E4_COMPLETE_JSON, name, sha(data))
        monkeypatch.setitem(A.si.E4_GIT_BLOB_OIDS, name, blob_oid(data))


def real_e4(monkeypatch):
    """Restore the production E4 values of safe_input (for production-mode tests inside a synthetic world)."""
    for name, digest in REAL_E4.items():
        monkeypatch.setitem(A.si.E4_COMPLETE_JSON, name, digest)
    for name, oid in REAL_E4_OIDS.items():
        monkeypatch.setitem(A.si.E4_GIT_BLOB_OIDS, name, oid)


class World:
    """All inputs of one request. ``real`` = frozen root for the consumer tests (real frozen bytes)."""

    def __init__(self, tmp, monkeypatch, real=None, host=HOST, idle=False):
        # r7 (ruling IR-03): every host carries the system bus admission only, as the production pins do. idle=True
        # models a test-only coordinator re-pin of an idle service on 03 (synthetic pins), so the generic idle checks
        # stay covered.
        self.tmp, self.mp, self.real, self.host = Path(tmp), monkeypatch, real, host
        t = self.tmp
        # runtime tree: S1 runtime pin + qualified binding + e4v3 dir + the pinned alias and outcome-named exception
        self.runtime = t / "runtime"
        put(self.runtime / "src/a.py", b"A = 1\n")
        put(self.runtime / ".hidden/h.py", b"H = 1\n")
        put(self.runtime / "data/x.json", b"{}\n")
        put(self.runtime / "reports/explore/s1/anchor.py", b"# anchor\n")
        put(self.runtime / ALIAS_TARGET, b"# example\n")
        put(self.runtime / ALIAS, b"# example\n")              # r4 (D2): E1 materialised as a regular copy
        put(self.runtime / EXCEPTION, {"synthetic": "throughput receipt"})
        for i, name in enumerate(E4_OTHERS):     # E4 non-members: in the runtime copy and tracked at HEAD (synthetic)
            put(self.runtime / name, ("synthetic E4 receipt %d\n" % i).encode())
        # r6 (B1): the real shape of runtime-pin-r2 "files" is a dict {name: sha256} (f81f3655: 1557 entries)
        put(self.runtime / A.S1_RUNTIME_PINS[0], {"files": {n: fsha(self.runtime / n) for n in ("data/x.json", "src/a.py", EXCEPTION)}})
        put(self.runtime / A.S1_QUALIFIED, {"qualified_source_files": {
            "reports/explore/s1/anchor.py": fsha(self.runtime / "reports/explore/s1/anchor.py")}})
        e4v3 = self.runtime / E4V3_REL
        if real:
            for p in sorted((Path(real) / E4V3_REL).iterdir()):
                if p.is_file():
                    put(e4v3 / p.name, p.read_bytes())
        else:
            put(e4v3 / "tier_backend.py", b"# synthetic\n")
            put(e4v3 / "receipts.py", b"# synthetic\n")
            put(e4v3 / "build.sh", b"#!/bin/sh\n")
            put(e4v3 / "spec-pins.json", {"prereg_r3_sha256": "0" * 64})
            put(e4v3 / "README.md", b"not pinned\n")
            (e4v3 / "tests").mkdir()
        # models + state rows (index consistent with frozen state_rows.StateRows.__init__)
        m = t / "models"
        for name in ("v1.pt", "R3a.pt", "R3a-calibration.json"):
            put(m / name, ("synthetic " + name + "\n").encode())
        put(m / "states.pkl", b"synthetic pickle bytes, never unpickled\n")
        self.ids = [f"{i}:300:0" for i in range(12)]
        chunks = [("state-" + i).encode() for i in self.ids]
        put(m / "states-rows.bin", b"".join(chunks))
        rows, offset = [], 0
        for identity, chunk in zip(self.ids, chunks):
            rows.append(dict(id=identity, offset=offset, length=len(chunk), sha256=sha(chunk)))
            offset += len(chunk)
        self.index = dict(schema=A.STATE_ROWS_SCHEMA, pickle_protocol=5,
                          source=dict(file="states.pkl", sha256=fsha(m / "states.pkl"), rows=len(rows), verified=True),
                          container=dict(file="states-rows.bin", sha256=fsha(m / "states-rows.bin"), bytes=offset),
                          rows=rows)
        put(m / "states-rows.json", self.index)
        self.models = m
        self.sets = dict(golden=self.ids[:6], speed={k: self.ids[i:i + 3] for i, k in enumerate(A.TIERS)})
        put(t / "sets.json", self.sets)
        # repository (git): END evidence + artifacts at their relative paths, committed admissions
        self.repo = t / "repo"
        self.repo.mkdir()
        subprocess.run(GIT + ["init", "-q", str(self.repo)], check=True)
        art = self.artifacts = self.repo / A.EVIDENCE_REPO_DIR
        if real:
            put(art / "plan.json", (Path(real) / "reports/explore/k4s-confirm/plan.json").read_bytes())
        else:
            put(art / "plan.json", dict(study="PREREG-K4S", compute=dict(
                slots=11, console_slots=8, nice=10, forbidden_hosts=["127x05"],
                idle_service_exception=dict(hosts=["127x03", "127x08"]),
                hosts={h: dict(physical_cpus=list(range(55)), census_cpu=63) for h in ("127x03", "127x04")})))
        for name in ("completion.json", "ledger.json", "inventory.json"):
            put(art / "run-r1/completion" / name, {"synthetic": name})
        phases = []
        for h in ("127x03", "127x04"):
            for ph in ("reporting", "replacement-r1"):
                d = art / "run-r1/phase-meta" / f"{h}-{ph}"
                put(d / "launch.json", {"host": h})
                put(d / "supervisor-exit.json", {"host": h})
                put(d / "mhz.jsonl", b'{"utc":"x"}\n')
                put(d / "census.jsonl", b'{"utc":"x"}\n')
                phases.append(dict(host=h, phase=ph, **{f: self.item(d / n) for f, n in (
                    ("launch", "launch.json"), ("supervisor_exit", "supervisor-exit.json"),
                    ("mhz", "mhz.jsonl"), ("census", "census.jsonl"))}))
        self.evidence_doc = dict(schema=A.EVIDENCE_SCHEMA, kind="counted-reporting", plan=self.item(art / "plan.json"),
                                 completion=self.item(art / "run-r1/completion/completion.json"),
                                 blind_ledger=self.item(art / "run-r1/completion/ledger.json"),
                                 counted_inventory=self.item(art / "run-r1/completion/inventory.json"), phases=phases)
        # guard: freeze, modules, seeds (outside the repository, as in production from a repo export)
        g = t / "guard-src"
        if real:
            r = Path(real)
            put(g / "FROZEN-T1.json", (r / "reports/explore/t1/FROZEN-T1.json").read_bytes())
            for name in GUARD_FILES:
                put(g / "t1" / name, (r / "reports/explore/t1" / name).read_bytes())
            for name in SEEDS:
                put(g / "repo" / name, (r / name).read_bytes())
        else:
            for name in GUARD_FILES:
                put(g / "t1" / name, ("# synthetic " + name + "\n").encode())
            put(g / "repo" / SEED_03, dict(schema="clasher.t1.parent-source-seed.v1", host="127x03"))
            put(g / "repo" / SEED_SERVER, {"server": True})
            put(g / "repo" / SEED_CLIENT, {"client": True})
            put(g / "repo" / SEED_08, dict(schema="clasher.t1.parent-source-seed.v1", host="127x08", source_join=dict(
                server=dict(path=SEED_SERVER, commit="b" * 40, sha256=fsha(g / "repo" / SEED_SERVER)),
                client=dict(path=SEED_CLIENT, commit="c" * 40, sha256=fsha(g / "repo" / SEED_CLIENT)))))
            files = {"reports/explore/t1/" + n: fsha(g / "t1" / n) for n in GUARD_FILES}
            files.update({n: fsha(g / "repo" / n) for n in SEEDS})
            self.freeze = dict(status="FROZEN", files=files,
                               parent_source_seeds=[dict(path=n, commit="d" * 40, sha256=files[n]) for n in (SEED_03, SEED_08)],
                               **{d: dict(verdict="CONFIRM") for d in A.GUARD_DELTAS})
            put(g / "FROZEN-T1.json", self.freeze)
        self.guard = g
        self.bus_identity = dict(pid=2005 if host == "127x04" else 2049, start_ticks=1032 if host == "127x04" else 1273,
                                 exe="/usr/bin/dbus-daemon", cmdline_sha256="f" * 64, uid=103)
        self.idle_service = dict(pid=2180947, ppid=2180946, pgid=2180934, start_ticks=139691386,
                                 cmdline_sha256="a" * 64, uid=3822945)
        self.admission_docs = {"system-bus-admission.json": dict(utc="2026-10-12T00:00:00Z", host=host,
                                                                 identity=self.bus_identity)}
        if idle:
            self.admission_docs["idle-services.json"] = dict(utc="2026-10-12T00:00:00Z", host=host, services=[dict(
                name="v4-validation-cache", service=self.idle_service, wrapper_trio=[self.idle_service])])
        for name, doc in self.admission_docs.items():
            put(self.repo / self.admission_rel(name), doc)
        os.symlink(ALIAS_TARGET, self.repo / ALIAS)                   # E1: the committed mode-120000 entry
        put(self.repo / ALIAS_TARGET, b"# example\n")                # and its committed target blob
        for name in E4:                                               # E4: the four tracked complete.json files
            put(self.repo / name, (self.runtime / name).read_bytes())
        synthetic_e4(monkeypatch, {name: (self.runtime / name).read_bytes() for name in E4})
        self.write_evidence(commit=False)
        self.commit()
        # test-only pins (marker SYNTHETIC)
        self.pins = dict(
            schema=A.PINS_SCHEMA, marker="SYNTHETIC",
            models={n: fsha(m / n) for n in A.MODEL_NAMES},
            sets_canonical_sha256=A.canonical_sha(self.sets),
            measurement_files_sha256=None,
            frozen_t1_sha256=fsha(g / "FROZEN-T1.json"), k4s_plan_sha256=fsha(art / "plan.json"),
            topology=dict(P=list(range(128)), E=[], label="Linux logical IDs; physical masks pinned by reporting plan"),
            admissions={host: {n: (dict(identity=self.bus_identity) if n == "system-bus-admission.json"
                                   else dict(service=self.idle_service)) for n in self.admission_docs}},
            runtime_aliases={ALIAS: ALIAS_TARGET},
            runtime_outcome_name_exceptions={n: fsha(self.runtime / n) for n in E4},
            s1_runtime_pin_sha256=fsha(self.runtime / A.S1_RUNTIME_PINS[0]),
            s1_qualified_sha256=fsha(self.runtime / A.S1_QUALIFIED))   # r4b: no E5 key (E5 is the layer's)
        self.pins["measurement_files_sha256"] = A.canonical_sha(A.measurement_files(self.runtime / E4V3_REL, self.pins))
        self.write_pins()
        self.request = dict(
            schema=A.REQUEST_SCHEMA, host=host, runtime_root=str(self.runtime),
            runtime_files_sha256=A.canonical_sha(A.runtime_files(self.runtime, self.pins)),
            measurement_files_sha256=self.pins["measurement_files_sha256"],
            topology=copy.deepcopy(self.pins["topology"]),
            sets=entry(t / "sets.json"),
            models={n: entry(m / n) for n in A.MODEL_NAMES},
            end_evidence=dict(source=str(art / "end-evidence.json"), sha256=fsha(art / "end-evidence.json"),
                              artifacts_root=str(art)),
            guard=dict(job=JOB if host == "127x03" else JOB_04,
                       freeze=entry(g / "FROZEN-T1.json"),
                       modules={n: entry(g / "t1" / n) for n in GUARD_FILES},
                       admissions={n: entry(self.repo / self.admission_rel(n)) for n in self.admission_docs},
                       seed_inputs={n: entry(g / "repo" / n) for n in SEEDS}))
        self.committed = [[n, self.admission_rel(n), fsha(self.repo / self.admission_rel(n))] for n in self.admission_docs]

    def admission_rel(self, name):
        return ADMISSION_REL.format(host=self.host, name=name)

    def item(self, path):
        rel = Path(path).relative_to(self.artifacts)
        return dict(path=str(rel), sha256=fsha(path), commit="e" * 40,
                    repository_path=A.EVIDENCE_REPO_DIR + "/" + str(rel))

    def commit(self):
        subprocess.run(GIT + ["-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", str(self.repo), "commit", "-q", "--allow-empty", "-m", "synthetic"], check=True)

    def write_evidence(self, commit=True):
        put(self.artifacts / "end-evidence.json", (A.canonical(self.evidence_doc) + "\n").encode())
        if hasattr(self, "request"):
            self.request["end_evidence"]["sha256"] = fsha(self.artifacts / "end-evidence.json")
        if commit:
            self.commit()

    def write_pins(self):
        path = put(self.tmp / "pins-SYNTHETIC.json", self.pins)
        self.mp.setenv(A.SYNTHETIC_ENV, str(path))

    def pin(self, mutate):
        mutate(self.pins)
        self.write_pins()

    def reindex(self, index):
        path = put(self.models / "states-rows.json", index)
        self.request["models"]["states-rows.json"] = entry(path)
        self.pin(lambda p: p["models"].update({"states-rows.json": fsha(path)}))

    def run(self, out=None, dry_run=False, request=None, request_sha=None, committed=None, repository=None):
        request = self.request if request is None else request
        path = put(self.tmp / "request.json", (A.canonical(request) + "\n").encode())
        out = self.tmp / "out" / "bundle-SYNTHETIC" if out is None else Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = ["--request", str(path), "--request-sha256", request_sha or fsha(path),
                "--repository", str(self.repo if repository is None else repository), "--out", str(out)]
        for binding in (self.committed if committed is None else committed):
            argv += ["--committed-admission", *binding]
        Audit.start()                                   # r3: inode audit covers the assembler only, not test setup
        return A.main(argv + (["--dry-run"] if dry_run else [])), out


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def snapshot(root):
    return {str(p): (fsha(p), p.stat().st_mtime_ns) for p in sorted(Path(root).rglob("*"))
            if p.is_file() and "/.git/" not in str(p) and os.access(p, os.R_OK)}


@pytest.fixture
def opened(monkeypatch):
    """Records the absolute path of every leaf the assembler's safe_input layer reaches its descriptor gate for (r4:
    every read goes through si.open_leaf; the path is taken from the gated parent descriptor)."""
    seen = []
    real = A.si.open_leaf

    def record(dir_fd, name, *args):
        seen.append(os.readlink("/proc/self/fd/%d" % dir_fd) + "/" + name)
        return real(dir_fd, name, *args)
    monkeypatch.setattr(A.si, "open_leaf", record)
    return seen


# ---------------------------------------------------------------- happy path, dry run, determinism, immutability

def test_canary_checks_are_active():
    with pytest.raises(AssertionError):
        ok(False)


def test_happy_path_bundle(world):
    code, out = world.run()
    ok(code == 0 and out.is_dir() and not (out.parent / (out.name + ".partial")).exists())
    raw = (out / "tiers-pins.json").read_bytes()
    manifest = json.loads(raw)
    ok(raw == (A.canonical(manifest) + "\n").encode(), "manifest must be canonical bytes")
    ok((out / "tiers-pins.sha256").read_text() == sha(raw) + "  tiers-pins.json\n")
    ok(manifest["schema"] == "clasher.e4v3.inputs.v1" and manifest["profile"] == "fleet-reference")
    ok(manifest["final"] is False and manifest["threshold"] == A.THRESHOLD)
    ok(manifest["k4s_s4_synthetic"] == "SYNTHETIC-TEST-ONLY", "test-only pins must stamp the manifest")
    for name, digest in manifest["files"].items():
        ok(fsha(out / name) == digest, name)
        ok((out / name).stat().st_mode & 0o777 == 0o444, "bundle copies are read-only: " + name)
    ok(set(tree(out)) == set(manifest["files"]) | {"tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"})
    for name in ("tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"):     # r4: written 0444 by si.Writer
        ok((out / name).stat().st_mode & 0o777 == 0o444, "manifest/receipt files are read-only: " + name)
    p = manifest["reference_load_profile"]
    ok({k: p[k] for k in ("host", "reference_slot", "slot_count", "console_rule", "warmup_seconds", "perception")}
       == dict(host=HOST, reference_slot=0, slot_count=11, console_rule=False, warmup_seconds=300, perception="none"))
    ok(p["plan"] == "k4s-end-evidence/plan.json" and p["end_evidence"] == "k4s-end-evidence/end-evidence.json")
    ok(manifest["files"][p["end_evidence"]] == world.request["end_evidence"]["sha256"])
    g = p["guard"]
    ok(g["root"] == "t1-guard" and g["job"] == JOB and g["freeze"] == "t1-freeze.json")
    ok(g["admissions"] == {"system-bus-admission.json": "guard-admissions/system-bus-admission.json"})   # r7: IR-03
    ok(g["seed_inputs"] == {n: "seed-inputs/" + n for n in SEEDS})
    for name in A.MODEL_NAMES:
        ok(name in manifest["files"])
    for d in world.evidence_doc["phases"]:
        for f in ("launch", "supervisor_exit", "mhz", "census"):
            ok(manifest["files"]["k4s-end-evidence/" + d[f]["path"]] == d[f]["sha256"])
    ok(manifest["runtime_files"] == A.runtime_files(world.runtime, world.pins))
    ok(manifest["runtime_files"][ALIAS] == manifest["runtime_files"][ALIAS_TARGET], "alias hashes its target bytes")
    ok(set(manifest["runtime_files"]) == {"data/x.json", "src/a.py", ".hidden/h.py", "reports/explore/s1/anchor.py",
                                          ALIAS, ALIAS_TARGET, EXCEPTION} | {E4V3_REL + "/" + n for n in
                                                                              ("tier_backend.py", "receipts.py")})
    ok(manifest["measurement_files"] == {"build.sh": fsha(world.runtime / E4V3_REL / "build.sh"),
                                         "receipts.py": fsha(world.runtime / E4V3_REL / "receipts.py"),
                                         "spec-pins.json": fsha(world.runtime / E4V3_REL / "spec-pins.json"),
                                         "tier_backend.py": fsha(world.runtime / E4V3_REL / "tier_backend.py")})
    receipt = json.loads((out / "assembly-receipt.json").read_text())
    ok(receipt["manifest_sha256"] == sha(raw) and receipt["outcomes_read"] is False and receipt["final"] is False)
    ok(receipt["production_pins"] is False and receipt["status"] == "SYNTHETIC-TEST-ONLY")
    ok(receipt["committed_admissions"] == {n: dict(repository_path=r, sha256=s) for n, r, s in world.committed})


def test_host_04_has_no_idle_admission(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    _, out = w.run()
    g = json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]
    ok(g["job"] == JOB_04 and set(g["admissions"]) == {"system-bus-admission.json"})


def test_dry_run_prints_exact_manifest_and_writes_nothing(world, capsysbinary):
    before = snapshot(world.tmp)
    code, out = world.run(dry_run=True)
    printed = capsysbinary.readouterr().out
    ok(code == 0 and not out.exists() and not (out.parent / "bundle-SYNTHETIC.partial").exists())
    after = snapshot(world.tmp)
    ok({k: v for k, v in after.items() if not k.endswith("request.json")}
       == {k: v for k, v in before.items() if not k.endswith("request.json")}, "dry run wrote something")
    _, out = world.run()
    ok((out / "tiers-pins.json").read_bytes() == printed, "dry-run output must equal the real manifest bytes")


def test_deterministic_byte_identical_bundles(world):
    _, one = world.run(out=world.tmp / "o1" / "bundle-SYNTHETIC")
    _, two = world.run(out=world.tmp / "o2" / "bundle-SYNTHETIC")
    ok(tree(one) == tree(two), "identical inputs must give byte-identical bundles")


def test_inputs_are_not_modified(world):
    before = snapshot(world.tmp)
    world.run()
    after = {k: v for k, v in snapshot(world.tmp).items() if "/out/" not in k}
    ok({k: v for k, v in after.items() if not k.endswith("request.json")}
       == {k: v for k, v in before.items() if not k.endswith("request.json")})


# ---------------------------------------------------------------- fail-closed branches (each leaves no bundle)

def refused(world, match, **kw):
    out = Path(kw.pop("out", world.tmp / "out" / "bundle-SYNTHETIC"))
    with pytest.raises(A.AssemblyError, match=match):
        world.run(out=out, **kw)
    ok(not out.exists() and not (out.parent / (out.name + ".partial")).exists(), "a refusal must leave no bundle")


def test_request_sha_mismatch(world):
    refused(world, "Request SHA mismatch", request_sha="0" * 64)


def test_request_schema_and_keys(world):
    world.request["schema"] = "clasher.k4s.end-fleet-reference-request.v1"
    refused(world, "Unsupported request schema")
    world.request["schema"] = A.REQUEST_SCHEMA
    world.request["extra"] = 1
    refused(world, "Request keys differ")


@pytest.mark.parametrize("host", ["127x01", "127x08", "", None])
def test_host_not_an_end_host(world, host):
    world.request["host"] = host
    refused(world, "not a K4S END host")


def test_runtime_root_must_be_absolute_dir(world):
    world.request["runtime_root"] = "runtime"
    refused(world, "runtime_root must be an absolute path")
    world.request["runtime_root"] = str(world.tmp / "nope")
    refused(world, r"runtime tree: safe_input refused \[root\]")   # r4
    world.request["runtime_root"] = str(world.tmp) + "/./runtime"
    refused(world, "must be a normalized path")


def test_runtime_without_e4v3(world):
    shutil.rmtree(world.runtime / E4V3_REL)
    refused(world, r"runtime e4v3: safe_input refused \[missing\]")   # r4


def test_measurement_files_mismatch(world):
    put(world.runtime / E4V3_REL / "new_helper.py", b"# new\n")
    refused(world, "measurement_files differ")


def test_runtime_files_mismatch_and_incomplete_and_unqualified(world):
    put(world.runtime / "src/b.py", b"B = 2\n")
    refused(world, "runtime_files differ")
    os.remove(world.runtime / "src/b.py")
    os.remove(world.runtime / "data/x.json")
    refused(world, "Incomplete frozen runtime")
    put(world.runtime / "data/x.json", b"{}\n")
    put(world.runtime / "reports/explore/s1/anchor.py", b"# changed\n")
    refused(world, "Not the qualified S1 tier source")


def test_model_set_must_be_exact(world):
    del world.request["models"]["states.pkl"]
    refused(world, "Model inputs must be exactly")


def test_model_bytes_changed(world):
    put(world.models / "states.pkl", b"changed\n")
    refused(world, "Pin mismatch: model states.pkl")


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["speed"].pop("K4"), "sets.speed must be exactly"),
    (lambda s: s["speed"].update(K4=["missing:id"]), "absent from the pinned state index"),
    (lambda s: s["speed"].update(K2=["0:300:0", "0:300:0"]), "unique string IDs"),
    (lambda s: s.update(golden=[]), "unique string IDs"),
    (lambda s: s.update(extra=[]), "golden and speed"),
    (lambda s: s.pop("golden"), "golden and speed"),
])
def test_sets_checks(world, mutate, match):
    """Shape checks behind the pin (the pin is moved to the mutated sets so each later check is reached)."""
    sets = copy.deepcopy(world.sets)
    mutate(sets)
    put(world.tmp / "sets.json", sets)
    world.request["sets"] = entry(world.tmp / "sets.json")
    world.pin(lambda p: p.update(sets_canonical_sha256=A.canonical_sha(sets)))
    refused(world, match)


@pytest.mark.parametrize("topology,match", [
    (dict(P=[0, 1], E=[2], label="x"), "Topology must be"),
    (dict(P=[0, 0], E=[], label="x"), "unique non-negative"),
    (dict(P=[], E=[], label="x"), "unique non-negative"),
    (dict(P=[0, 1], E=[], label=""), "Topology must be"),
    (dict(P=[0, True], E=[], label="x"), "unique non-negative"),
    (dict(P=list(range(64)), E=[], label="Linux logical IDs; physical masks pinned by reporting plan"),
     "differs from the pinned target-host topology"),
])
def test_topology_checks(world, topology, match):
    world.request["topology"] = topology
    refused(world, match)


def test_evidence_schema_and_sha(world):
    world.request["end_evidence"]["sha256"] = "3" * 64
    refused(world, "Pin mismatch: END evidence")
    world.evidence_doc["schema"] = "clasher.e4v3.end-evidence.v1"
    world.write_evidence()
    refused(world, "Unsupported K4S END evidence")


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d["completion"].update(path="../escape.json"), "Unsafe relative path"),
    (lambda d: d["completion"].update(path="/abs.json"), "Unsafe relative path"),
    (lambda d: d["completion"].update(commit="e" * 39), "full commit"),
    (lambda d: d["completion"].update(commit="f" * 40), "bound to one commit"),
    (lambda d: d["completion"].pop("repository_path"), "lacks path/sha256/commit/repository_path"),
    (lambda d: d["completion"].update(repository_path="reports/x/" + d["completion"]["path"]), "not its repository path"),
    (lambda d: d["blind_ledger"].update(path=d["completion"]["path"],
                                        repository_path=d["completion"]["repository_path"]), "Conflicting END evidence pin"),
    (lambda d: d["completion"].update(path="run-r1/completion/missing.json",
                                      repository_path="reports/explore/k4s-confirm/run-r1/completion/missing.json"),
     r"END evidence artifact run-r1/completion/missing.json: safe_input refused \[missing\]"),   # r4
    (lambda d: d["completion"].update(sha256="4" * 64), "Pin mismatch: END evidence artifact"),
    (lambda d: d.update(phases=[]), "no phases"),
    (lambda d: d.update(phases=[p for p in d["phases"] if p["host"] != "127x03"]), "no counted phase on this host"),
    (lambda d: d["plan"].update(sha256=d["completion"]["sha256"], path=d["completion"]["path"],
                                repository_path=d["completion"]["repository_path"]), "not the frozen K4S plan"),
    (lambda d: d["completion"].update(path="end-evidence.json", sha256="5" * 64,
                                      repository_path="reports/explore/k4s-confirm/end-evidence.json"), "Pin mismatch|collision"),
])
def test_evidence_item_checks(world, mutate, match):
    mutate(world.evidence_doc)
    world.write_evidence()
    refused(world, match)


def test_evidence_must_be_committed_at_head_and_at_its_repository_path(world):
    world.evidence_doc["note"] = "uncommitted edit"
    world.write_evidence(commit=False)
    refused(world, "differs from its committed HEAD blob")
    world.commit()
    other = put(world.tmp / "elsewhere/end-evidence.json", (world.artifacts / "end-evidence.json").read_bytes())
    world.request["end_evidence"]["source"] = str(other)
    refused(world, "END evidence must be --repository/")


# ---------------------------------------------------------------- S4-F1: confinement BEFORE any read

def runtime_pin_names(world, *extra):
    names = ["data/x.json", "src/a.py", EXCEPTION, *extra]                 # r6: the real dict shape {name: sha256}
    path = put(world.runtime / A.S1_RUNTIME_PINS[0], {"files": {n: "0" * 64 for n in names}})
    world.pin(lambda p: p.update(s1_runtime_pin_sha256=fsha(path)))       # r4: the pin list is read SHA-pinned


def never_opened(opened, *paths):
    for path in paths:
        ok(str(path) not in opened, "forbidden bytes were opened: " + str(path))


def test_f1_absolute_runtime_pin_entry_refused_before_read(world, opened):
    target = canary(world.tmp / "elsewhere/synthetic-marker.json")
    runtime_pin_names(world, str(target))
    refused(world, r"Unsafe relative path \(S1 runtime-pin entry\)")
    never_opened(opened, target)


def test_f1_dotdot_runtime_pin_entry_refused_before_read(world, opened):
    target = canary(world.tmp / "synthetic-marker.json")
    runtime_pin_names(world, "../synthetic-marker.json")
    refused(world, r"Unsafe relative path \(S1 runtime-pin entry\)")
    never_opened(opened, target)


def test_f1_runtime_py_symlink_to_games_canary_refused_before_read(world, opened):
    target = canary(world.tmp / "games/decoy.json")
    os.symlink(target, world.runtime / "src/evil.py")
    refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: src/evil.py")   # r4: si.walk_tree
    never_opened(opened, target, world.runtime / "src/evil.py")


def test_f1_measurement_py_symlink_outside_refused_before_read(world, opened):
    target = canary(world.tmp / "outside/helper.py")
    os.symlink(target, world.runtime / E4V3_REL / "helper.py")
    refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: " + re.escape(E4V3_REL + "/helper.py"))
    never_opened(opened, target)


def test_f1_runtime_pin_entry_through_symlinked_directory_refused(world, opened):
    target = canary(world.tmp / "outside-dir/x.json")
    os.symlink(world.tmp / "outside-dir", world.runtime / "linked")
    runtime_pin_names(world, "linked/x.json")
    refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: linked")
    never_opened(opened, target)


def test_f1_outcome_names_in_runtime_inventory_refused_before_read(world, opened):
    target = canary(world.runtime / "data/games/g.json")
    runtime_pin_names(world, "data/games/g.json")
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family games")   # r4: shared denylist
    never_opened(opened, target)
    shutil.rmtree(world.runtime / "data/games")
    other = canary(world.runtime / "data/complete.json")
    runtime_pin_names(world, "data/complete.json")
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family complete-json: .*data/complete.json")
    never_opened(opened, other)


def test_f1_outcome_directory_in_runtime_tree_never_descended(world, opened):
    # r4 rename: pytest names tmp_path after the test, and a 'games' token there is itself refused by the family gate
    target = canary(world.runtime / "pkg/games/decoy.py")
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family games: component .games. in .*/pkg/games")
    never_opened(opened, target)


def test_f1_pinned_outcome_name_exception_is_path_and_sha_bound(world, monkeypatch):
    """r4: the E4 SHA is safe_input's; the pins must carry exactly it, and a different layer SHA refuses the bytes."""
    world.pin(lambda p: p["runtime_outcome_name_exceptions"].update({EXCEPTION: "9" * 64}))
    refused(world, "Runtime outcome-name exceptions must carry the E4 SHAs of safe_input")
    monkeypatch.setitem(A.si.E4_COMPLETE_JSON, EXCEPTION, "9" * 64)          # layer pin != the synthetic bytes
    refused(world, "Tracked E4 exempt complete.json differs from its pin: " + re.escape(EXCEPTION))   # HEAD first
    untrack_e4(world)
    refused(world, "Runtime outcome-named entry differs from its pin: " + re.escape(EXCEPTION))


def test_f1_runtime_alias_is_exactly_pinned(world):
    """r4 (D2, E1 materialised): any symlink at the runtime alias refuses (even with the exact link text); a regular
    copy must equal the committed E1 target blob."""
    for text in ("src/a.py", ALIAS_TARGET, str(world.runtime / ALIAS_TARGET)):
        os.remove(world.runtime / ALIAS)
        os.symlink(text, world.runtime / ALIAS)
        refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: visualize_battle.py")
    os.remove(world.runtime / ALIAS)
    put(world.runtime / ALIAS, b"# exampl3\n")                             # same size as the target, other bytes
    world.request["runtime_files_sha256"] = A.canonical_sha(A.runtime_files(world.runtime, world.pins))
    refused(world, "Runtime visualize_battle.py differs from the committed E1 target blob")
    put(world.runtime / ALIAS, b"# example\n")
    world.request["runtime_files_sha256"] = A.canonical_sha(A.runtime_files(world.runtime, world.pins))
    code, _ = world.run()
    ok(code == 0)


def test_f1_symlinked_s1_metadata_refused(world, opened):
    target = put(world.tmp / "other-pin.json", {"files": []})
    os.remove(world.runtime / A.S1_RUNTIME_PINS[0])
    os.symlink(target, world.runtime / A.S1_RUNTIME_PINS[0])
    refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: " + re.escape(A.S1_RUNTIME_PINS[0]))
    never_opened(opened, target)


def test_f1_request_source_with_symlinked_ancestor_refused(world, opened):
    os.symlink(world.models, world.tmp / "models-link")
    world.request["models"]["states.pkl"] = dict(source=str(world.tmp / "models-link/states.pkl"),
                                                 sha256=world.request["models"]["states.pkl"]["sha256"])
    refused(world, r"model states.pkl: safe_input refused \[root\]: .*models-link is a symlink")   # r4: canonical root
    never_opened(opened, world.models / "states.pkl", world.tmp / "models-link/states.pkl")


@pytest.mark.parametrize("source", [
    "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/127x03-r4/system-bus-admission.json",
    "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00/FROZEN-T1.json",
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op6-0108-r1/sets.json",
    "/tmp/x/games/sets.json",
    "/tmp/x/hub-blocks/abc/sets.json",
    "/tmp/x/interference.json",
    "/tmp/x/end-raw.json",
])
def test_f1_request_sources_in_outcome_or_job_trees_refused_by_name(world, opened, source):
    world.request["sets"] = dict(source=source, sha256="0" * 64)
    refused(world, r"sets: safe_input refused \[name\]")                          # r4: shared denylist
    ok(opened == [] or source not in opened)


def test_f1_evidence_artifact_symlink_and_outcome_names_refused_before_read(world, opened):
    outside = canary(world.tmp / "outside.json")
    target = world.artifacts / "run-r1/completion/completion.json"
    os.remove(target)
    os.symlink(outside, target)
    world.commit()
    refused(world, r"END evidence artifact run-r1/completion/completion.json: safe_input refused \[symlink\]")
    never_opened(opened, outside)
    os.remove(target)
    put(target, {"synthetic": "completion.json"})
    world.evidence_doc["completion"].update(path="run-r1/games/decoy.json", sha256="1" * 64,
                                            repository_path=A.EVIDENCE_REPO_DIR + "/run-r1/games/decoy.json")
    world.write_evidence()
    decoy = canary(world.artifacts / "run-r1/games/decoy.json")     # after the commit (git cannot read mode 000)
    refused(world, r"evidence artifact run-r1/games/decoy.json: safe_input refused \[name\]: outcome name family games")
    never_opened(opened, decoy)
    os.remove(decoy)
    world.evidence_doc["completion"].update(path="end/registry/round-00/127x03/attempt-00.json",
                                            repository_path=A.EVIDENCE_REPO_DIR + "/end/registry/round-00/127x03/attempt-00.json")
    world.write_evidence()
    refused(world, r"evidence artifact end/registry/round-00/127x03/attempt-00.json: safe_input refused \[name\]")


def test_f1_open_refuses_a_leaf_replaced_after_the_walk(world, monkeypatch):
    """r4: every copy re-gates its source and carries the planned SHA-256 and size: a source replaced between planning
    and the copy (new inode, same size, other bytes) or by a symlink is refused at the copy and never published (the
    exclusive .partial stage is kept)."""
    path = world.models / "states.pkl"
    original = path.read_bytes()
    real_write = A.write_bundle

    def replace_then_write(*args):
        replacement = put(world.models / "replacement.pkl", bytes(b ^ 1 if i == 5 else b for i, b in enumerate(original)))
        os.replace(replacement, path)
        return real_write(*args)
    monkeypatch.setattr(A, "write_bundle", replace_then_write)
    kept_partial(world, "Source changed while copying: states.pkl")

    def symlink_then_write(*args):
        os.remove(path)
        os.symlink(world.tmp / "pins-SYNTHETIC.json", path)
        return real_write(*args)
    put(path, original)
    monkeypatch.setattr(A, "write_bundle", symlink_then_write)
    kept_partial(world, r"copy states.pkl: safe_input refused \[symlink\]", out=world.tmp / "out2" / "bundle-SYNTHETIC")


def test_out_checks(world):
    (world.tmp / "out" / "bundle-SYNTHETIC").mkdir(parents=True)
    with pytest.raises(A.AssemblyError, match="new absolute directory"):
        world.run()
    shutil.rmtree(world.tmp / "out")
    (world.tmp / "out" / "bundle-SYNTHETIC.partial").mkdir(parents=True)
    with pytest.raises(A.AssemblyError, match="previous partial"):
        world.run()
    with pytest.raises(A.AssemblyError, match="inside an input tree"):
        world.run(out=world.runtime / "bundle-SYNTHETIC")
    with pytest.raises(A.AssemblyError, match="inside an input tree"):
        world.run(out=world.artifacts / "bundle-SYNTHETIC")
    with pytest.raises(A.AssemblyError, match="inside an input tree"):
        world.run(out=world.repo / "bundle-SYNTHETIC")
    ok(not (world.runtime / "bundle-SYNTHETIC").exists() and not (world.artifacts / "bundle-SYNTHETIC").exists())
    (world.tmp / "real-out").mkdir()
    os.symlink(world.tmp / "real-out", world.tmp / "out-link")
    with pytest.raises(A.AssemblyError, match=r"--out parent: safe_input refused \[root\]: .*out-link is a symlink"):
        world.run(out=world.tmp / "out-link" / "bundle-SYNTHETIC")
    ok(list((world.tmp / "real-out").iterdir()) == [], "nothing may be written through an aliased --out parent")


def kept_partial(world, match, out=None):
    """r4: a failure while WRITING keeps the exclusive .partial stage (safe_input never deletes); nothing is published
    and a later run refuses until the stage is removed by an authorized step."""
    out = Path(out or world.tmp / "out" / "bundle-SYNTHETIC")
    with pytest.raises(A.AssemblyError, match=match):
        world.run(out=out)
    ok(not out.exists() and (out.parent / (out.name + ".partial")).is_dir(), "the stage must be kept, never published")
    with pytest.raises(A.AssemblyError, match="A previous partial bundle exists"):
        A.check_out(str(out), dict(trees=(), synthetic=True))


def test_copy_verification_failure_removes_partial(world, monkeypatch):
    real_copy = A.si.copy_input

    def corrupt(policy, role, rel, writer, dst_rel, *args):
        result = real_copy(policy, role, rel, writer, dst_rel, *args)
        if dst_rel.endswith("states.pkl"):
            target = world.tmp / "out" / dst_rel
            os.chmod(target, 0o644)
            target.write_bytes(b"x" * target.stat().st_size)          # same size: only the re-hash can tell
        return result
    monkeypatch.setattr(A.si, "copy_input", corrupt)
    kept_partial(world, "Copy differs from its pin: states.pkl")


def test_source_changed_during_copy_refused(world, monkeypatch):
    """r4: the copy pass re-gates the source and checks the planned SHA-256 of the bytes it wrote."""
    real_copy = A.si.copy_input

    def rewrite_then_copy(policy, role, rel, writer, dst_rel, *args):
        if dst_rel.endswith("states.pkl"):
            source = world.models / "states.pkl"
            source.write_bytes(b"y" * source.stat().st_size)          # same size, other bytes, same inode
        return real_copy(policy, role, rel, writer, dst_rel, *args)
    monkeypatch.setattr(A.si, "copy_input", rewrite_then_copy)
    kept_partial(world, "Source changed while copying: states.pkl")


def test_cli_exit_code_on_refusal(world):
    world.request["host"] = "127x09"
    path = put(world.tmp / "request.json", (A.canonical(world.request) + "\n").encode())
    p = subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []),
                        str(HERE / "assemble_fleet_reference.py"), "--request", str(path),
                        "--request-sha256", fsha(path), "--repository", str(world.repo),
                        "--out", str(world.tmp / "cli-out-SYNTHETIC"), "--dry-run"],
                       capture_output=True, text=True)
    ok(p.returncode == 2 and "ASSEMBLY REFUSED" in p.stderr and p.stdout == "", p.stderr)


# ---------------------------------------------------------------- S4-F2: production pins, test-only switch

def test_f2_production_pins_are_the_verified_constants():
    P = A.PRODUCTION_PINS
    ok(P["models"] == {
        "v1.pt": "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed",
        "R3a.pt": "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85",
        "R3a-calibration.json": "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414",
        "states.pkl": "0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1",
        "states-rows.json": "bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5",
        "states-rows.bin": "8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb"})
    ok(P["sets_canonical_sha256"] == "d84b07f6de0ac1cffbbb199221b6fbd795e9f7169aebcbdc445bba282e0c3ae2")
    ok(P["measurement_files_sha256"] == "42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25")
    ok(set(P["admissions"]) == {"127x03", "127x04"})
    ok(set(P["admissions"]["127x03"]) == {"system-bus-admission.json"})                 # r7: ruling IR-03
    ok(set(P["admissions"]["127x04"]) == {"system-bus-admission.json"})
    ok(P["topology"]["P"] == list(range(128)) and P["topology"]["E"] == [])
    ok(set(P) == A.PIN_KEYS and P["marker"] == "PRODUCTION")


def test_f2_production_mode_is_the_default_and_refuses_synthetic_inputs(world, monkeypatch):
    untrack_e4(world)                     # r3b: synthetic E4 blobs at HEAD would refuse first (E4 production SHAs)
    monkeypatch.delenv(A.SYNTHETIC_ENV)
    real_e4(monkeypatch)                  # r4: production E4 values of safe_input (fingerprint intact)
    for name in E4_OTHERS + [EXCEPTION]:                       # and no synthetic E4 bytes in the runtime either
        os.remove(world.runtime / name)
    ok(A.active_pins() == (A.PRODUCTION_PINS, False))
    refused(world, "measurement_files_sha256 differs from the pinned inventory", out=world.tmp / "out" / "bundle")
    world.request["measurement_files_sha256"] = A.PRODUCTION_PINS["measurement_files_sha256"]
    refused(world, "measurement_files differ", out=world.tmp / "out" / "bundle")


@pytest.mark.parametrize("field,match", [
    ("states.pkl", "Input SHA differs from the pinned value: model states.pkl"),
    ("states-rows.json", "Input SHA differs from the pinned value: model states-rows.json"),
    ("states-rows.bin", "Input SHA differs from the pinned value: model states-rows.bin"),
    ("v1.pt", "Input SHA differs from the pinned value: model v1.pt"),
])
def test_f2_each_model_pin_enforced(world, field, match):
    world.pin(lambda p: p["models"].update({field: A.PRODUCTION_PINS["models"][field]}))
    refused(world, match)


def test_f2_sets_must_be_t1_own_tier_sets(world):
    world.pin(lambda p: p.update(sets_canonical_sha256=A.PRODUCTION_PINS["sets_canonical_sha256"]))
    refused(world, "sets are not T1's pinned own-tier sets")


def test_f2_measurement_and_freeze_and_plan_pins_enforced(world):
    world.pin(lambda p: p.update(measurement_files_sha256=A.PRODUCTION_PINS["measurement_files_sha256"]))
    refused(world, "measurement_files_sha256 differs from the pinned inventory")
    world.pin(lambda p: p.update(measurement_files_sha256=world.request["measurement_files_sha256"]))
    world.pin(lambda p: p.update(frozen_t1_sha256="6" * 64))
    refused(world, "differs from the pinned value: guard freeze")
    world.pin(lambda p: p.update(frozen_t1_sha256=world.request["guard"]["freeze"]["sha256"], k4s_plan_sha256="7" * 64))
    refused(world, "not the frozen K4S plan")


def test_f2_idle_admission_required_on_03_when_repinned(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch, idle=True)          # r7: a test-only re-pin (production 03: IR-03, bus only)
    del world.request["guard"]["admissions"]["idle-services.json"]
    refused(world, r"Admissions on 127x03 must be exactly")
    world.committed = [c for c in world.committed if c[0] != "idle-services.json"]
    refused(world, r"--committed-admission is required for exactly")


def test_f2_idle_admission_refused_on_04(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    rel = w.admission_rel("idle-services.json")
    put(w.repo / rel, dict(host="127x04", services=[dict(name="n", service=w.idle_service, wrapper_trio=[])]))
    w.commit()
    w.request["guard"]["admissions"]["idle-services.json"] = entry(w.repo / rel)
    w.committed.append(["idle-services.json", rel, fsha(w.repo / rel)])
    refused(w, r"--committed-admission is required for exactly \['system-bus-admission.json'\]")


def test_f2_committed_admission_argument_required(world):
    refused(world, "--committed-admission is required", committed=[])


@pytest.mark.parametrize("change,match", [
    (lambda c: c[0].__setitem__(2, "8" * 64), "Committed admission blob differs"),
    (lambda c: c[0].__setitem__(1, "reports/explore/k4s-confirm/end/127x03-bus.json"),
     r"must be exactly .*\(E3\): reports/explore/k4s-confirm/end/127x03-bus.json"),          # r4: pure E3 rule first
    (lambda c: c[0].__setitem__(1, "reports/explore/t1/receipts/system-bus-admission-127x03.json"), r"must be exactly .*\(E3\)"),
    (lambda c: c[0].__setitem__(1, "reports/explore/k4s-confirm/end-guard-admissions/127x04-system-bus-admission.json"),
     r"must be exactly reports/explore/k4s-confirm/end-guard-admissions/127x03-system-bus-admission.json \(E3\)"),
    (lambda c: c[0].__setitem__(1, "reports/explore/k4s-confirm/127x03-system-bus-admission.json"), r"\(E3\)"),
    (lambda c: c[0].__setitem__(1, "reports/explore/k4s-confirm/end-guard-admissions/games/127x03-system-bus-admission.json"),
     r"must be exactly .*\(E3\): .*/games/"),                                               # r4: pure E3 rule first
    (lambda c: c[0].__setitem__(1, "../reports/explore/k4s-confirm/127x03.json"), "Unsafe relative path"),
    (lambda c: c.append(list(c[0])), "Unknown/duplicate --committed-admission"),
    (lambda c: c[0].__setitem__(0, "owned-supervisor-admission.json"), "Unknown/duplicate --committed-admission"),
])
def test_f2_committed_admission_binding_checks(world, change, match):
    change(world.committed)
    refused(world, match)


def test_f2_admission_must_be_the_committed_copy(world):
    rel = world.admission_rel("system-bus-admission.json")
    doc = dict(world.admission_docs["system-bus-admission.json"], utc="2026-10-12T01:00:00Z")
    put(world.repo / rel, doc)                                       # work tree differs from HEAD
    world.request["guard"]["admissions"]["system-bus-admission.json"] = entry(world.repo / rel)
    refused(world, "differs from the pinned value: admission system-bus-admission.json")
    world.committed[0][2] = fsha(world.repo / rel)
    refused(world, "Committed admission blob differs")
    world.commit()
    copy_path = put(world.tmp / "copy/bus.json", (world.repo / rel).read_bytes())
    world.request["guard"]["admissions"]["system-bus-admission.json"] = entry(copy_path)
    refused(world, "Admission source is not its committed copy")


@pytest.mark.parametrize("name,mutate,match", [
    ("system-bus-admission.json", lambda d: d["identity"].update(pid=2005), "not the pinned identity"),
    ("system-bus-admission.json", lambda d: d["identity"].update(uid=0), "identity malformed"),
    ("system-bus-admission.json", lambda d: d.update(host="127x04"), "different host"),
    ("idle-services.json", lambda d: d["services"][0]["service"].update(start_ticks=1), "not the pinned service identity"),
    ("idle-services.json", lambda d: d.update(services=[]), "Idle-service admission malformed"),
    ("idle-services.json", lambda d: d["services"].append(copy.deepcopy(d["services"][0])), "Idle-service admission malformed"),
])
def test_f2_admission_content_checks(tmp_path, monkeypatch, name, mutate, match):
    world = World(tmp_path, monkeypatch, idle=name == "idle-services.json")     # r7: idle rows on a test-only re-pin
    doc = copy.deepcopy(world.admission_docs[name])
    mutate(doc)
    rel = world.admission_rel(name)
    put(world.repo / rel, doc)
    world.commit()
    world.request["guard"]["admissions"][name] = entry(world.repo / rel)
    for binding in world.committed:
        if binding[0] == name:
            binding[2] = fsha(world.repo / rel)
    refused(world, match)


def test_f2_synthetic_mode_can_never_emit_a_production_bundle(world, tmp_path, monkeypatch):
    refused(world, "require an --out named \\*SYNTHETIC\\*", out=world.tmp / "out" / "bundle")
    world.pin(lambda p: p.update(marker="PRODUCTION"))
    refused(world, "Synthetic pins must carry marker SYNTHETIC")
    world.pin(lambda p: p.update(marker="SYNTHETIC"))
    world.pin(lambda p: p.pop("topology"))
    refused(world, "Synthetic pins must carry marker SYNTHETIC and every pin key")


@pytest.mark.parametrize("job", [
    "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rd00-a00",                # 04's parent on 03
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-op6-guard-job-01-r1",
    "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4",
    "/mpac/sdicks02/jobs/clasher/k4s-confirm-r1",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00/",
    "/mpac/sdicks02/jobs/clasher/../clasher/k4s-end-guard-r1-rd00-a00",
    "/mpac/sdicks02/repos/clasher-v4-cache/k4s-end-guard-r1-rd00-a00",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r0-rd00-a00",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-a00",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1",                     # r2: per-attempt/preflight suffix required
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf1",
    "k4s-end-guard-r1-rd00-a00",
    None,
])
def test_guard_job_namespace(world, job):
    world.request["guard"]["job"] = job
    refused(world, "Guard job must be")


def test_guard_job_preflight_name_accepted(world):
    world.request["guard"]["job"] = "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf01"
    _, out = world.run()
    ok(json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]["job"].endswith("-pf01"))


def test_guard_job_must_be_fresh(world, monkeypatch):
    """r4: the guard job is a TARGET-host path; S4 only name-gates it (form, parent, shared denylist under a remote
    policy for that host with the exact guard-job grant) and never touches the local filesystem at that path.
    Freshness is enforced on the host (S3/S5/S7). r3's local os.path.lexists() probe of a remote path is removed."""
    touched = []
    for name in ("lstat", "stat"):
        real = getattr(A.os, name)
        monkeypatch.setattr(A.os, name, (lambda real: lambda p, *a, **k: touched.append(str(p)) or real(p, *a, **k))(real))
    code, _ = world.run()
    ok(code == 0 and not [p for p in touched if p.startswith(JOB)], "the remote guard job path was touched locally")
    remote = A.si.Policy(HOST, [A.si.Role("g", A.JOB_PARENTS[HOST], "write", 1, exact=("x",))], remote=True)
    with pytest.raises(A.si.Refusal, match="guard job component"):
        A.si.gate_names(remote, "g", "x/k4s-end-guard-r1-rd00-a00/y")   # without the exact grant: refused


def test_guard_04_namespace_never_perception_path(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    w.request["guard"]["job"] = JOB                                     # 04 perception jobs root
    refused(w, "Guard job must be")


@pytest.mark.parametrize("delta", ["operational_delta_op5", "operational_delta_op5_08", "operational_delta_op6"])
def test_guard_freeze_requires_confirm_deltas(world, delta):
    world.freeze[delta] = dict(verdict="REQUEST_CHANGES")
    path = put(world.guard / "FROZEN-T1.json", world.freeze)
    world.pin(lambda p: p.update(frozen_t1_sha256=fsha(path)))
    world.request["guard"]["freeze"] = entry(path)
    refused(world, "lacks a CONFIRM " + delta)


def test_guard_modules_exact_and_frozen(world):
    modules = world.request["guard"]["modules"]
    removed = modules.pop("ssh_budget.py")
    refused(world, "exactly the nine frozen T1 guard modules")
    modules["ssh_budget.py"] = removed
    modules["apt_budget.py"] = removed
    refused(world, "exactly the nine frozen T1 guard modules")
    del modules["apt_budget.py"]
    put(world.guard / "k4s_host_audit.py", b"# K4S variant\n")
    modules["host_audit.py"] = entry(world.guard / "k4s_host_audit.py")
    refused(world, "differs from the pinned value: guard module host_audit.py")


def test_guard_admission_set_checks(world):
    adm = world.request["guard"]["admissions"]
    put(world.guard / "adm/owned-supervisor-admission.json", dict(host=HOST, supervisor={}))
    adm["owned-supervisor-admission.json"] = entry(world.guard / "adm/owned-supervisor-admission.json")
    refused(world, "Admissions on 127x03 must be exactly")
    del adm["owned-supervisor-admission.json"]
    del adm["system-bus-admission.json"]
    refused(world, "Admissions on 127x03 must be exactly")


def test_guard_seed_input_checks(world):
    seeds = world.request["guard"]["seed_inputs"]
    client = seeds.pop(SEED_CLIENT)
    refused(world, "Missing pinned OP-5 seed/join input")
    seeds[SEED_CLIENT] = client
    seeds["reports/explore/t1/receipts/extra.json"] = client
    refused(world, "differs from frozen seed/join dependencies")
    del seeds["reports/explore/t1/receipts/extra.json"]
    put(world.guard / "other-03.json", dict(schema="clasher.t1.parent-source-seed.v1", host="127x03", note="other"))
    seeds[SEED_03] = entry(world.guard / "other-03.json")
    refused(world, "differs from the pinned value: seed " + SEED_03)


def test_guard_08_seed_requires_source_join(world):
    receipt = json.loads((world.guard / "repo" / SEED_08).read_text())
    del receipt["source_join"]
    path = put(world.guard / "repo" / SEED_08, receipt)
    world.freeze["files"][SEED_08] = fsha(path)
    world.freeze["parent_source_seeds"][1]["sha256"] = fsha(path)
    fpath = put(world.guard / "FROZEN-T1.json", world.freeze)
    world.pin(lambda p: p.update(frozen_t1_sha256=fsha(fpath)))
    world.request["guard"]["freeze"] = entry(fpath)
    world.request["guard"]["seed_inputs"][SEED_08] = entry(path)
    refused(world, "08 seed lacks its source_join")


def test_seed_binding_not_in_freeze_files(world):
    del world.freeze["files"][SEED_SERVER]
    fpath = put(world.guard / "FROZEN-T1.json", world.freeze)
    world.pin(lambda p: p.update(frozen_t1_sha256=fsha(fpath)))
    world.request["guard"]["freeze"] = entry(fpath)
    refused(world, "Unpinned/unsafe OP-5 seed dependency")


def test_input_entry_shape(world):
    world.request["sets"] = dict(source=str(world.tmp / "sets.json"))
    refused(world, r"must be \{source, sha256\}")
    world.request["sets"] = dict(source=str(world.tmp / "sets.json"), sha256="XYZ")
    refused(world, "Input SHA")


@pytest.mark.parametrize("plan_change,match", [
    (lambda c: c.update(forbidden_hosts=["127x03"]), "Host absent/forbidden in plan"),
    (lambda c: c.update(slots="11"), "compute.slots must be an integer"),
    (lambda c: c.pop("hosts"), "Malformed K4S plan"),
])
def test_plan_checks(world, plan_change, match):
    plan = json.loads((world.artifacts / "plan.json").read_text())
    plan_change(plan["compute"])
    put(world.artifacts / "plan.json", plan)
    world.pin(lambda p: p.update(k4s_plan_sha256=fsha(world.artifacts / "plan.json")))
    world.evidence_doc["plan"] = world.item(world.artifacts / "plan.json")
    world.write_evidence()
    refused(world, match)


def test_plan_study(world):
    plan = json.loads((world.artifacts / "plan.json").read_text())
    plan["study"] = "PREREG-SEARCH-TIERS"
    put(world.artifacts / "plan.json", plan)
    world.pin(lambda p: p.update(k4s_plan_sha256=fsha(world.artifacts / "plan.json")))
    world.evidence_doc["plan"] = world.item(world.artifacts / "plan.json")
    world.write_evidence()
    refused(world, "not the K4S reporting plan")


# ---------------------------------------------------------------- S4-F3: state index = frozen StateRows checks

INDEX_MUTANTS = [
    ("protocol-999", lambda i: i.update(pickle_protocol=999), "Unsupported state index"),
    ("protocol-bool", lambda i: i.update(pickle_protocol=True), "Unsupported state index"),
    ("schema", lambda i: i.update(schema="x"), "Unsupported state index"),
    ("source-sha", lambda i: i["source"].update(sha256="2" * 64), "not derived from the pinned states.pkl"),
    ("unverified", lambda i: i["source"].update(verified=False), "not converted from the SHA-verified"),
    ("container-sha", lambda i: i["container"].update(sha256="3" * 64), "names a different container"),
    ("row-count", lambda i: i["source"].update(rows=11), "row count differs"),
    ("offset-77", lambda i: i["rows"][0].update(offset=77), "Non-contiguous state index"),
    ("gap", lambda i: i["rows"][5].update(offset=i["rows"][5]["offset"] + 1), "Non-contiguous state index"),
    ("zero-length", lambda i: (i["rows"][3].update(length=0)), "Non-contiguous state index"),
    ("final-length", lambda i: i["container"].update(bytes=i["container"]["bytes"] + 1), "length differs from its container"),
    ("duplicate", lambda i: i["rows"][1].update(id=i["rows"][0]["id"]), "Duplicate fixed-state IDs"),
    ("missing-container", lambda i: i.pop("container"), "Malformed state index"),
]


@pytest.mark.parametrize("label,mutate,match", INDEX_MUTANTS, ids=[m[0] for m in INDEX_MUTANTS])
def test_f3_state_index_mutants_refused(world, label, mutate, match):
    index = copy.deepcopy(world.index)
    mutate(index)
    world.reindex(index)
    refused(world, match)


def test_f3_container_size_must_match_index(world):
    data = (world.models / "states-rows.bin").read_bytes() + b"x"
    put(world.models / "states-rows.bin", data)
    index = copy.deepcopy(world.index)
    index["container"]["sha256"] = sha(data)
    world.request["models"]["states-rows.bin"] = entry(world.models / "states-rows.bin")
    world.pin(lambda p: p["models"].update({"states-rows.bin": sha(data)}))
    world.reindex(index)
    refused(world, "State container size differs from its index")


# ---------------------------------------------------------------- r3: hard links, END namespace, auxiliary paths, E1-E3

class Audit:
    """In-process audit hook (sys.addaudithook; installed once). Inside the ``audited`` fixture, recording starts at
    Audit.start() (World.run calls it just before A.main, so test setup writes are not counted). For every 'open'
    event it records the path and the (st_dev, st_ino) of what the path names (lstat and stat), so an open through ANY
    hard-link name of a canary is detected by inode."""
    armed, on, events = False, False, []

    @classmethod
    def start(cls):
        cls.events = []
        cls.on = cls.armed

    @classmethod
    def hook(cls, event, args):
        if not cls.on or event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(args[0])
        inodes = set()
        for probe in (os.lstat, os.stat):
            try:
                st = probe(path)
                inodes.add((st.st_dev, st.st_ino))
            except OSError:
                pass
        cls.events.append((path, inodes))


sys.addaudithook(Audit.hook)


@pytest.fixture
def audited(monkeypatch):
    """r4: safe_input opens leaves relative to a gated directory descriptor (os.open(name, dir_fd=...)), which the
    'open' audit event cannot resolve by path; so os.open is also wrapped and records the inode of the descriptor it
    actually returned (with the dir_fd-resolved path)."""
    Audit.armed, Audit.on, Audit.events = True, False, []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if Audit.on:
            st = os.fstat(fd)
            where = os.fsdecode(path)
            if dir_fd is not None:
                where = os.readlink("/proc/self/fd/%d" % dir_fd) + "/" + where
            Audit.events.append((where, {(st.st_dev, st.st_ino)}))
        return fd
    monkeypatch.setattr(os, "open", recording_open)
    yield Audit
    Audit.armed = Audit.on = False


def inode(path):
    st = os.lstat(path)
    return st.st_dev, st.st_ino


def never_touched(audit, *paths):
    """No open event, under any name, of the inode of any of ``paths`` (and none naming the path itself)."""
    ok(audit.on, "the audit was never started")
    for path in paths:
        identity = inode(path)
        hits = [p for p, inodes in audit.events if identity in inodes or p == str(path)]
        ok(not hits, "forbidden inode was opened: " + str(path) + " via " + repr(hits[:3]))


def link_canary(world, target, label, same_bytes):
    """Replace ``target`` by a hard link to an outcome canary (TMP/games/<label>/complete.json, mode 000).
    same_bytes=True gives the canary the original bytes, so every SHA, composite pin and parse stays consistent and
    only the hard-link gate can refuse; False leaves every composite/request SHA stale."""
    target = Path(target)
    os.chmod(target, 0o644)
    data = target.read_bytes() if same_bytes else b'{"CANARY": "outcome bytes, never read"}\n'
    outcome = canary(world.tmp / "games" / label / "complete.json", data)
    os.remove(target)
    os.link(outcome, target)
    ok(os.lstat(target).st_nlink == 2 and os.lstat(target).st_mode & 0o777 == 0)
    return outcome


def _tree(rel):                          # r4: the runtime classes are refused by the one si.walk_tree pass
    return r"runtime tree: safe_input refused \[nlink\]: hard-linked file in tree: " + re.escape(rel)


def _leaf(label):                        # r4: every other class by the si descriptor gate, under its own label
    return re.escape(label) + r": safe_input refused \[nlink\]: .*hard-linked leaf"


HARDLINK_CLASSES = {                    # input class -> (target path in the World, refusal regex)
    "runtime-pin-member": (lambda w: w.runtime / "data/x.json", _tree("data/x.json")),
    "runtime-discovered-py": (lambda w: w.runtime / "src/a.py", _tree("src/a.py")),
    "runtime-e1-alias-target": (lambda w: w.runtime / ALIAS_TARGET, _tree(ALIAS_TARGET)),
    "runtime-e1-materialised-copy": (lambda w: w.runtime / ALIAS, _tree(ALIAS)),
    "runtime-e2-exception": (lambda w: w.runtime / EXCEPTION, _tree(EXCEPTION)),
    **{"runtime-e4-non-member-%d" % i: ((lambda n: lambda w: w.runtime / n)(n), _tree(n))
       for i, n in enumerate(E4_OTHERS)},
    "s1-runtime-pin-json": (lambda w: w.runtime / A.S1_RUNTIME_PINS[0], _tree(A.S1_RUNTIME_PINS[0])),
    "s1-qualified-json": (lambda w: w.runtime / A.S1_QUALIFIED, _tree(A.S1_QUALIFIED)),
    "measurement-py": (lambda w: w.runtime / E4V3_REL / "tier_backend.py", _tree(E4V3_REL + "/tier_backend.py")),
    "measurement-spec-pins": (lambda w: w.runtime / E4V3_REL / "spec-pins.json", _tree(E4V3_REL + "/spec-pins.json")),
    "q6-states-pkl": (lambda w: w.models / "states.pkl", _leaf("model states.pkl")),
    "q6-states-rows-json": (lambda w: w.models / "states-rows.json", _leaf("model states-rows.json")),
    "q6-states-rows-bin": (lambda w: w.models / "states-rows.bin", _leaf("model states-rows.bin")),
    "model-v1": (lambda w: w.models / "v1.pt", _leaf("model v1.pt")),
    "sets": (lambda w: w.tmp / "sets.json", _leaf("sets")),
    "end-evidence": (lambda w: w.artifacts / "end-evidence.json", _leaf("END evidence")),
    "evidence-artifact": (lambda w: w.artifacts / "run-r1/completion/completion.json",
                          _leaf("END evidence artifact run-r1/completion/completion.json")),
    "evidence-telemetry": (lambda w: w.artifacts / "run-r1/phase-meta/127x04-reporting/mhz.jsonl",
                           _leaf("END evidence artifact run-r1/phase-meta/127x04-reporting/mhz.jsonl")),
    "guard-freeze": (lambda w: w.guard / "FROZEN-T1.json", _leaf("guard freeze")),
    "guard-module": (lambda w: w.guard / "t1/ssh_budget.py", _leaf("guard module ssh_budget.py")),
    "admission-bus": (lambda w: w.repo / w.admission_rel("system-bus-admission.json"),
                      _leaf("admission system-bus-admission.json")),
    "admission-idle": (lambda w: w.repo / w.admission_rel("idle-services.json"), _leaf("admission idle-services.json")),
    "seed": (lambda w: w.guard / "repo" / SEED_08, _leaf("seed " + SEED_08)),
    "synthetic-pins": (lambda w: w.tmp / "pins-SYNTHETIC.json", _leaf(A.SYNTHETIC_ENV)),
}


@pytest.mark.parametrize("same_bytes", [True, False], ids=["consistent-shas", "stale-shas"])
@pytest.mark.parametrize("cls", sorted(HARDLINK_CLASSES))
def test_r3_f1_hard_link_canary_refused_before_any_read(tmp_path, monkeypatch, audited, cls, same_bytes):
    """S4-R2-F1: in every input class a hard-link alias of an outcome canary is refused by the walk's st_nlink gate,
    with the class's own label, and the canary inode is never opened under any name (it is also mode 000)."""
    world = World(tmp_path, monkeypatch, idle=cls == "admission-idle")   # r7: the idle class on a test-only re-pin
    find, label = HARDLINK_CLASSES[cls]
    outcome = link_canary(world, find(world), cls, same_bytes)
    refused(world, label)
    never_touched(audited, outcome)


def test_r3_f1_hard_linked_request_refused_before_read(world, audited):
    request = put(world.tmp / "request-src.json", (A.canonical(world.request) + "\n").encode())
    digest = fsha(request)
    outcome = link_canary(world, request, "request", same_bytes=True)
    out = world.tmp / "out" / "bundle-SYNTHETIC"
    argv = ["--request", str(request), "--request-sha256", digest, "--repository", str(world.repo), "--out", str(out)]
    for binding in world.committed:
        argv += ["--committed-admission", *binding]
    Audit.start()
    with pytest.raises(A.AssemblyError, match=r"--request: safe_input refused \[nlink\]"):
        A.main(argv)
    never_touched(audited, outcome)
    ok(not out.exists())


def test_r3_f1_descriptor_gate_refuses_a_link_made_after_the_walk(world, monkeypatch):
    """The si descriptor gate re-checks st_nlink on the OPENED descriptor before any read: a hard link that appears
    between its fstatat and its open (end-to-end, on the sets input) is refused, and no byte is read from it."""
    sets = world.tmp / "sets.json"
    real_open, real_read, opened_fds, reads = os.open, os.read, [], []

    def open_then_link(path, flags, *args, dir_fd=None, **kwargs):
        if path == "sets.json" and dir_fd is not None and not (world.tmp / "late-link.json").exists():
            os.link(sets, world.tmp / "late-link.json")
            fd = real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            opened_fds.append(fd)
            return fd
        return real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
    monkeypatch.setattr(A.si.os, "open", open_then_link)
    monkeypatch.setattr(A.si.os, "read", lambda fd, n: reads.append(os.fstat(fd).st_ino) or real_read(fd, n))
    refused(world, r"sets: safe_input refused \[nlink\]: .*hard-linked leaf at open \(st_nlink 2\)")
    ok(opened_fds and inode(sets)[1] not in reads, "a byte was read from the multiply-linked descriptor")


def test_r3_f1_descriptor_gate_unit(tmp_path):
    """r4: S4's request-source roles (Sources) refuse a hard-linked source for hashing and for reading."""
    path = put(tmp_path / "x.json", b"{}\n")
    os.link(path, tmp_path / "y.json")
    sources = A.Sources([("probe", str(path))])
    entry_ = dict(source=str(path), sha256=fsha(path))
    with pytest.raises(A.AssemblyError, match=r"probe: safe_input refused \[nlink\]"):
        A.pinned_source(sources, entry_, "probe")
    with pytest.raises(A.AssemblyError, match=r"probe: safe_input refused \[nlink\]"):
        A.pinned_json(sources, entry_, "probe")


def test_r3_f1_hard_linked_copy_source_refused_at_copy_time(world, audited, monkeypatch):
    """A link added after planning (before the copy pass) is refused by the descriptor gate; no bundle remains."""
    real_write = A.write_bundle

    def link_then_write(copies, *args):
        os.link(world.models / "states.pkl", world.tmp / "late-pkl")
        return real_write(copies, *args)
    monkeypatch.setattr(A, "write_bundle", link_then_write)
    kept_partial(world, r"copy states.pkl: safe_input refused \[nlink\]")         # r4: the stage is kept


SEALED = "reports/explore/k4s-confirm/end/receipts/round-00/127x03/raw-00/reference-warmup.json"


def test_r3_f2_sealed_end_receipt_as_sets_refused_before_open(world, audited):
    """The reviewer's reproduction: valid sets JSON at a sealed END receipt path of the repository."""
    sealed = canary(world.repo / SEALED, (A.canonical(world.sets) + "\n").encode())
    world.request["sets"] = dict(source=str(sealed), sha256=sha(A.canonical(world.sets).encode() + b"\n"))
    refused(world, r"sets: safe_input refused \[name\]: strict END namespace k4s-confirm/end")
    never_touched(audited, sealed)


@pytest.mark.parametrize("rel", ["reports/explore/k4s-confirm/end/attempt-00.json",
                                 "reports/explore/k4s-confirm/end/registry/round-00/127x03/attempt-00.json",
                                 "reports/explore/k4s-confirm/end/END-JOB.json",
                                 "copy/k4s-confirm/end/pools/round-00/x.json"])
def test_r3_f2_end_namespace_request_sources_refused(world, audited, rel):
    target = canary(world.tmp / "anywhere" / rel)
    world.request["guard"]["freeze"] = dict(source=str(target), sha256=world.request["guard"]["freeze"]["sha256"])
    refused(world, r"guard freeze: safe_input refused \[name\]: strict END namespace k4s-confirm/end")
    never_touched(audited, target)


def test_r3_f2_end_namespace_runtime_member_and_metadata_refused(world, audited):
    member = canary(world.runtime / "reports/explore/k4s-confirm/end/receipts/x.json")
    runtime_pin_names(world, "reports/explore/k4s-confirm/end/receipts/x.json")
    refused(world, r"runtime tree: safe_input refused \[name\]: strict END namespace k4s-confirm/end in .*/runtime/reports/explore/k4s-confirm/end$")
    never_touched(audited, member)
    shutil.rmtree(world.runtime / "reports/explore/k4s-confirm")
    refused(world, r"S1 runtime-pin entry reports/explore/k4s-confirm/end/receipts/x.json: safe_input refused \[name\]: strict END namespace")


def test_r3_f2_end_namespace_directory_in_runtime_tree_never_listed(world, audited, monkeypatch):
    (world.runtime / "reports/explore/k4s-confirm/end/registry").mkdir(parents=True)
    canary(world.runtime / "reports/explore/k4s-confirm/end/registry/attempt-00.json")
    listed, real_listdir = [], os.listdir                     # r4: si.walk_tree lists by descriptor
    monkeypatch.setattr(A.si.os, "listdir", lambda p=".": listed.append(
        os.readlink("/proc/self/fd/%d" % p) if isinstance(p, int) else str(p)) or real_listdir(p))
    refused(world, r"runtime tree: safe_input refused \[name\]: strict END namespace k4s-confirm/end in .*/runtime/reports/explore/k4s-confirm/end$")
    ok(not any("k4s-confirm/end" in p for p in listed), "the END namespace was listed: " + repr(listed))


def test_r3_f2_end_namespace_runtime_root(world):
    root = world.tmp / "x/reports/explore/k4s-confirm/end/runtime"
    world.request["runtime_root"] = str(root)
    refused(world, r"runtime_root: safe_input refused \[name\]: strict END namespace")


@pytest.mark.parametrize("where,match", [
    ("x/reports/explore/k4s-confirm/end/repo", r"--repository: safe_input refused \[name\]: strict END namespace"),
    ("x/games/repo", r"--repository: safe_input refused \[name\]: outcome name family games"),
    ("x/k4s-confirm-replacement-r4/repo", r"--repository: safe_input refused \[name\]: K4S reporting job"),
])
def test_r3_f2_repository_location_refused_by_name_before_lstat(world, where, match):
    refused(world, match, repository=world.tmp / where)          # the path does not exist: names refuse first


@pytest.mark.parametrize("where,match", [
    ("reports/explore/k4s-confirm/end/bundle-SYNTHETIC", r"--out: safe_input refused \[name\]: strict END namespace"),
    ("games/bundle-SYNTHETIC", r"--out: safe_input refused \[name\]: outcome name family games"),
    ("k4s-end-guard-r1-rd00-a00/bundle-SYNTHETIC", r"--out: safe_input refused \[name\]: guard job component"),
    ("o/end-raw-SYNTHETIC.json", r"--out: safe_input refused \[name\]: outcome name family end-raw-json"),   # r4 name
])
def test_r3_f2_out_location_refused_and_nothing_written(world, where, match):
    out = world.tmp / where
    out.parent.mkdir(parents=True, exist_ok=True)
    refused(world, match, out=out)
    ok(list(out.parent.iterdir()) == [], "nothing may be written into a forbidden --out location")


def test_r3_f2_out_in_t1_launch_namespace_refused():
    with pytest.raises(A.AssemblyError, match=r"--out: safe_input refused \[name\]: forbidden namespace"):
        A.check_out(A.T1_LAUNCH_NAMESPACES[0] + "/bundle", dict(trees=(), synthetic=False))


def test_r3_f2_guard_job_parent_goes_through_location_free(world, monkeypatch):
    for parent, match in (("/tmp/x/games", "outcome name family games"), (A.T1_LAUNCH_NAMESPACES[1], "forbidden namespace"),
                          ("/tmp/x/reports/explore/k4s-confirm/end", "strict END namespace")):
        monkeypatch.setitem(A.JOB_PARENTS, HOST, parent)
        world.request["guard"]["job"] = parent + "/k4s-end-guard-r1-rd00-a00"
        refused(world, r"guard job: safe_input refused \[name\]: " + match)
    for parent in ("/mpac/sdicks02/jobs/clasher", "/mpac/sdicks02/jobs-k4s"):
        ok(A.location_free(parent, "probe") == parent)


def test_r3_f2_git_blob_and_seed_paths_use_the_same_gates(world):
    calls = A.si.GIT_COUNTERS["runs"]
    with pytest.raises(A.AssemblyError, match=r"repository path reports/explore/k4s-confirm/end/END-JOB.json: "
                                              r"safe_input refused \[name\]"):
        A.Committed(str(world.repo), ["reports/explore/k4s-confirm/end/END-JOB.json"])
    ok(A.si.GIT_COUNTERS["runs"] == calls, "git ran before the name gate refused")
    world.freeze["parent_source_seeds"][0]["path"] = "reports/explore/k4s-confirm/end/receipts/seed.json"
    fpath = put(world.guard / "FROZEN-T1.json", world.freeze)
    world.pin(lambda p: p.update(frozen_t1_sha256=fsha(fpath)))
    world.request["guard"]["freeze"] = entry(fpath)
    refused(world, r"seed path: safe_input refused \[name\]: strict END namespace")


def test_r3_f2_end_guard_admissions_is_not_the_end_namespace():
    ok(A.location_free("/r/" + A.ADMISSION_REPO_DIR + "/127x03-system-bus-admission.json", "probe"))
    with pytest.raises(A.AssemblyError, match="strict END namespace"):
        A.location_free("/r/" + A.END_DIR, "probe")


def test_r3_f3_synthetic_pins_through_symlinked_parent_refused_before_read(world, audited):
    real = put(world.tmp / "pins-dir/pins-SYNTHETIC.json", world.pins)
    os.symlink(world.tmp / "pins-dir", world.tmp / "pins-link")
    world.mp.setenv(A.SYNTHETIC_ENV, str(world.tmp / "pins-link/pins-SYNTHETIC.json"))
    os.chmod(real, 0)
    refused(world, r"K4S_S4_SYNTHETIC_PINS: safe_input refused \[root\]: .*pins-link is a symlink")
    never_touched(audited, real)


@pytest.mark.parametrize("rel,match", [
    ("games/pins-SYNTHETIC.json", r"K4S_S4_SYNTHETIC_PINS: safe_input refused \[name\]: outcome name family games"),
    ("reports/explore/k4s-confirm/end/pins-SYNTHETIC.json", r"K4S_S4_SYNTHETIC_PINS: safe_input refused \[name\]: strict END"),
    ("x/complete.json", r"K4S_S4_SYNTHETIC_PINS: safe_input refused \[name\]: outcome name family complete-json"),
])
def test_r3_f3_synthetic_pins_in_outcome_locations_refused_before_read(world, audited, rel, match):
    target = canary(world.tmp / rel, (json.dumps(world.pins) + "\n").encode())
    world.mp.setenv(A.SYNTHETIC_ENV, str(target))
    refused(world, match)
    never_touched(audited, target)


def test_r3_f3_synthetic_pins_must_be_absolute_and_normalized(world):
    world.mp.setenv(A.SYNTHETIC_ENV, "pins-SYNTHETIC.json")
    refused(world, "K4S_S4_SYNTHETIC_PINS must be an absolute path")
    world.mp.setenv(A.SYNTHETIC_ENV, str(world.tmp) + "/./pins-SYNTHETIC.json")
    refused(world, "must be a normalized path")


@pytest.mark.parametrize("mutate", [
    lambda p: p["runtime_aliases"].update({"other.py": "src/a.py"}),
    lambda p: p.update(runtime_aliases={}),
    lambda p: p["runtime_outcome_name_exceptions"].update({"data/complete.json": "0" * 64}),
    lambda p: p.update(runtime_outcome_name_exceptions={"other/complete.json": "0" * 64}),
])
def test_r3_e1_e2_test_mode_cannot_widen_or_move_the_exemptions(world, mutate):
    world.pin(mutate)
    refused(world, "must be exactly the E[14] exemption|must be exactly the E4 exempt list")


def test_r3_e1_alias_must_be_the_committed_mode_120000_entry(world):
    os.remove(world.repo / ALIAS)
    put(world.repo / ALIAS, ALIAS_TARGET.encode())                     # same text, but a regular file (100644)
    world.commit()
    refused(world, "E1 alias is not a committed mode-120000 entry")
    os.remove(world.repo / ALIAS)
    os.symlink("src/a.py", world.repo / ALIAS)
    world.commit()
    # r4: phase 1 of si.git_plan refuses a wrong link by its pinned OID, before the link blob is read
    refused(world, r"--repository HEAD tree: safe_input refused \[exemption\]: E1 entry is not the exact link")
    subprocess.run(GIT + ["-C", str(world.repo), "rm", "-q", ALIAS], check=True)
    world.commit()
    refused(world, "E1 alias is not a committed mode-120000 entry")


def test_r3_e1_alias_target_must_pass_the_hard_link_gate_through_the_alias_walk(world, audited):
    """r4 (D2): the shipped regular copy and the target both pass the walk's hard-link gate (hard-linked copy refused,
    never opened); the committed target is read from git only."""
    outcome = link_canary(world, world.runtime / ALIAS, "alias", same_bytes=True)
    refused(world, r"runtime tree: safe_input refused \[nlink\]: hard-linked file in tree: visualize_battle.py")
    never_touched(audited, outcome)


def test_r3_e1_alias_is_never_opened_through_the_link(world, audited):
    """r4 (D2): the committed link is read as a blob (cat-file, never followed); the repository's work-tree link is
    never opened; the shipped regular copy and its target are hashed through the descriptor gate."""
    _, out = world.run()
    ok(not [p for p, _ in audited.events if p in (str(world.repo / ALIAS), str(world.repo / ALIAS_TARGET))],
       "the repository's E1 link or target was opened")
    hashed = {p for p, _ in audited.events}
    ok({"visualize_battle.py", "examples/visualize_battle.py"} & {os.path.basename(p) for p in hashed}
       or any(p.endswith("visualize_battle.py") for p in hashed), "the shipped E1 copy was not hashed")


def test_r3_e2_exception_is_hashed_once_never_parsed(world, audited, monkeypatch):
    parsed = []
    real_parse = A.parse_json
    monkeypatch.setattr(A, "parse_json", lambda raw, label: parsed.append(label) or real_parse(raw, label))
    world.run()
    identity = inode(world.runtime / EXCEPTION)
    ok(len([p for p, inodes in audited.events if identity in inodes]) == 1, "E2 must be opened exactly once (hash)")
    ok(not any(EXCEPTION in label or "complete" in label for label in parsed), repr(parsed))


def test_r3_e2_only_at_its_exact_runtime_path(world, audited):
    elsewhere = canary(world.runtime / "imitation/model/receipts/throughput-0936/complete.json")
    runtime_pin_names(world, "imitation/model/receipts/throughput-0936/complete.json")
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family complete-json: .*"
                   r"imitation/model/receipts/throughput-0936/complete.json")
    never_touched(audited, elsewhere)


def test_r3_e2_production_values_are_the_ruled_ones():
    ok(A.PRODUCTION_PINS["runtime_outcome_name_exceptions"] == E4 == A.si.E4_COMPLETE_JSON)
    ok(A.PRODUCTION_PINS["runtime_aliases"] == {"visualize_battle.py": "examples/visualize_battle.py"})
    A.check_exemptions(A.PRODUCTION_PINS, synthetic=False)
    bad = copy.deepcopy(A.PRODUCTION_PINS)
    bad["runtime_outcome_name_exceptions"][A.E2_PATH] = "0" * 64
    with pytest.raises(A.AssemblyError, match="E4 SHAs of safe_input"):
        A.check_exemptions(bad, synthetic=False)


def test_r3_location_free_requires_a_normalized_absolute_path():
    for bad in ("relative/x.json", "/a/../b.json", "//a/b.json", "/a/./b.json", "/a/b\\c.json", "/a/b\x00.json"):
        with pytest.raises(A.AssemblyError, match=r"probe must be an absolute path|probe must be a normalized path"):
            A.location_free(bad, "probe")


def test_r3_runtime_files_checks_the_exemptions_for_direct_callers(world):
    pins = copy.deepcopy(world.pins)
    pins["runtime_aliases"]["src/a.py"] = "data/x.json"
    with pytest.raises(A.AssemblyError, match="E1 exemption"):
        A.runtime_files(world.runtime, pins)


def test_r3_assembler_own_file_is_read_through_the_gates(world, tmp_path):
    """The receipt's assembler_sha256 is computed from a confined read of the running file (a hard-linked copy of
    the assembler refuses before planning)."""
    copy_dir = tmp_path / "asm"
    copy_dir.mkdir()
    shutil.copyfile(HERE / "assemble_fleet_reference.py", copy_dir / "asm.py")
    shutil.copyfile(HERE / "safe_input.py", copy_dir / "safe_input.py")         # r4: the pinned layer beside it
    os.link(copy_dir / "asm.py", copy_dir / "asm-link.py")
    path = put(world.tmp / "request.json", (A.canonical(world.request) + "\n").encode())
    p = subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []), str(copy_dir / "asm.py"),
                        "--request", str(path), "--request-sha256", fsha(path), "--repository", str(world.repo),
                        "--out", str(world.tmp / "cli-out-SYNTHETIC"), "--dry-run"], capture_output=True, text=True)
    ok(p.returncode == 2 and "assembler: safe_input refused [nlink]" in p.stderr and p.stdout == "", p.stderr)


def test_r3_e3_stale_identity_names_the_re_pin_ruling(world):
    doc = copy.deepcopy(world.admission_docs["system-bus-admission.json"])
    doc["identity"].update(start_ticks=9999)                          # e.g. a dbus restart after a reboot
    rel = world.admission_rel("system-bus-admission.json")
    put(world.repo / rel, doc)
    world.commit()
    world.request["guard"]["admissions"]["system-bus-admission.json"] = entry(world.repo / rel)
    world.committed[0][2] = fsha(world.repo / rel)
    refused(world, r"not the pinned identity .*coordinator re-pin ruling \(E3\)")


# ---------------------------------------------------------------- r3b: ruling E4 (exact four-entry complete.json list)

def untrack_e4(world, keep=()):
    """Remove the E4 files from the synthetic repository's HEAD tree (absence is allowed; only extras refuse)."""
    for name in sorted(set(E4) - set(keep)):
        subprocess.run(GIT + ["-C", str(world.repo), "rm", "-q", name], check=True)
    world.commit()


def moved(name):
    """The same leaf one directory over: a path that is not on the E4 list."""
    parent, leaf = name.rsplit("/", 1)
    return parent + "-moved/" + leaf


def receipt_component(rel):
    return rel[:rel.index("complete.json") + len("complete.json")]


def test_e4_production_list_is_exactly_the_ruling():
    ok(A.si.E4_COMPLETE_JSON == E4 and len(E4) == 4, "E4 constant differs from the ruling")
    ok(A.PRODUCTION_PINS["runtime_outcome_name_exceptions"] == E4)
    ok(A.PRODUCTION_PINS["runtime_outcome_name_exceptions"] is not A.si.E4_COMPLETE_JSON)
    ok(A.si.E4_GIT_BLOB_OIDS == {                       # r4: the layer's OIDs (three = SOL-REVIEW-END-PKG2-r1)
        EXCEPTION: "7c9502037a75263dcfaaf5ab33666d2b8382a201",
        "reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json":
            "a2f94dd0ce1ab1f4b233d63201a454318dc0ecff",
        "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json":
            "9e15e1f73e4f3dd05fa635da0f621851a52c873a",
        "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json":
            "1a73d2e1c54ab69fac9433047a8c957c3693d055"})
    A.check_exemptions(A.PRODUCTION_PINS, synthetic=False)


@pytest.mark.parametrize("name", sorted(E4))
def test_e4_production_check_refuses_each_entry_with_another_sha(name):
    bad = copy.deepcopy(A.PRODUCTION_PINS)
    bad["runtime_outcome_name_exceptions"][name] = "0" * 64
    with pytest.raises(A.AssemblyError, match="E4 SHAs of safe_input"):
        A.check_exemptions(bad, synthetic=False)


@pytest.mark.parametrize("name", sorted(E4))
def test_e4_production_mode_refuses_each_tracked_entry_whose_bytes_differ(world, monkeypatch, name):
    """Production pins, the build commit tracking only ``name`` (synthetic bytes != its ruled SHA): refused by the
    --repository HEAD tree check, by that exact name."""
    untrack_e4(world, keep=(name,))
    monkeypatch.delenv(A.SYNTHETIC_ENV)
    real_e4(monkeypatch)                                       # r4: production E4 SHAs and blob OIDs of safe_input
    reads = A.si.GIT_COUNTERS["object_reads"]
    refused(world, r"--repository HEAD tree: safe_input refused \[exemption\]: E4 entry " + re.escape(name)
            + " is not the pinned 100644 blob", out=world.tmp / "out" / "bundle")
    ok(A.si.GIT_COUNTERS["object_reads"] == reads, "S4-R3-F3: an object was read before the metadata refusal")


E4_PINS_MUTANTS = {
    "widen": lambda p: p["runtime_outcome_name_exceptions"].update({"data/complete.json": "0" * 64}),
    "widen-e4-copy": lambda p: p["runtime_outcome_name_exceptions"].update({moved(EXCEPTION): E4[EXCEPTION]}),
    "not-a-sha": lambda p: p["runtime_outcome_name_exceptions"].update({EXCEPTION: "z" * 64}),
    "not-a-map": lambda p: p.update(runtime_outcome_name_exceptions=sorted(E4)),
    **{"drop-%d" % i: (lambda n: lambda p: p["runtime_outcome_name_exceptions"].pop(n))(n)
       for i, n in enumerate(sorted(E4))},
    **{"move-%d" % i: (lambda n: lambda p: p["runtime_outcome_name_exceptions"].update(
        {moved(n): p["runtime_outcome_name_exceptions"].pop(n)}))(n) for i, n in enumerate(sorted(E4))},
}


@pytest.mark.parametrize("mutant", sorted(E4_PINS_MUTANTS))
def test_e4_test_mode_cannot_widen_narrow_or_move_the_list(world, mutant):
    world.pin(E4_PINS_MUTANTS[mutant])
    refused(world, "must be exactly the E4 exempt list")
    with pytest.raises(A.AssemblyError, match="must be exactly the E4 exempt list"):     # direct callers too
        A.runtime_files(world.runtime, world.pins)


def test_e4_four_entries_accepted_hashed_once_never_parsed(world, audited, monkeypatch):
    parsed, calls = [], []
    real_parse, real_git = A.parse_json, A.si.git_run
    monkeypatch.setattr(A, "parse_json", lambda raw, label: parsed.append((label, raw)) or real_parse(raw, label))

    def git(repo, args, *rest, **kwargs):                      # r4: every git call is si.git_run
        stdin = kwargs.get("stdin_bytes", rest[2] if len(rest) > 2 else None)
        if list(args) == ["cat-file", "--batch"]:
            calls.append(["cat-file", "blob", stdin.decode().strip()])
        else:
            calls.append(list(args))
        return real_git(repo, args, *rest, **kwargs)
    monkeypatch.setattr(A.si, "git_run", git)
    code, out = world.run()
    ok(code == 0 and (out / A.MANIFEST).is_file(), "the four exact entries must be accepted")
    exempt_bytes = set()
    for name in E4:
        identity = inode(world.runtime / name)
        ok(len([p for p, inodes in audited.events if identity in inodes]) == 1, "not opened exactly once: " + name)
        never_touched(audited, world.repo / name)          # the build commit's copy is hashed from git, not opened
        oid = subprocess.run(GIT + ["-C", str(world.repo), "rev-parse", "HEAD:" + name], check=True,
                             capture_output=True, text=True).stdout.strip()
        ok(calls.count(["cat-file", "blob", oid]) == 1, "committed blob not hashed exactly once: " + name)
        exempt_bytes.add((world.runtime / name).read_bytes())          # synthetic bytes, read by the test after the run
    ok(len([c for c in calls if c[:5] == ["ls-tree", "-r", "-l", "-z", "--full-tree"]]) == 1)
    ok(not any("complete" in label or raw in exempt_bytes for label, raw in parsed), "an E4 file was parsed")
    manifest = json.loads((out / A.MANIFEST).read_text())
    ok(EXCEPTION in manifest["runtime_files"] and not set(E4_OTHERS) & set(manifest["runtime_files"]),
       "E4 non-members must not become runtime members")
    ok(not [n for n in manifest["files"] if "complete.json" in n], "no E4 file is copied into the bundle")


# r4: r3's six-name OUTCOME_LEAVES list is gone (S4-R3-F2); its five non-E4 names plus Sol's r3 variants
R3_LEAVES_AND_VARIANTS = ("local-complete.json", "end-complete.json", "interference.json", "hub-ack.json",
                          "end-raw.json", "END-FINAL.json", "attempt-00.json", "end-raw-copy.json", "complete-v2.json",
                          "Complete.json", "COMPLETE.JSON", "Hub-Ack.returned.json", "END-JOB.json")


@pytest.mark.parametrize("leaf", R3_LEAVES_AND_VARIANTS)
def test_e4_exemption_is_per_name_other_outcome_leaves_still_refused(world, audited, leaf):
    """The walk's outcome-name exemption is exactly the E4 names: other outcome leaves in the inventory still refuse."""
    target = canary(world.runtime / "data" / leaf)
    runtime_pin_names(world, "data/" + leaf)
    refused(world, r"runtime tree: safe_input refused \[name\]: (outcome|END claim) name family .*" + re.escape(leaf))
    never_touched(audited, target)


def test_e4_non_members_are_checked_but_never_runtime_members(world):
    members = A.runtime_files(world.runtime, world.pins)
    ok(EXCEPTION in members and not set(E4_OTHERS) & set(members))


@pytest.mark.parametrize("rel", [
    "complete.json", "data/complete.json", "pkg/complete.json/inner.txt", moved(EXCEPTION),
    "reports/explore/k4s-confirm/end/receipts/round-00/complete.json",
    "reports/strategy_council_20260928/live-loop/v4/emulator-host/sub/complete.json",
])
def test_e4_extra_tracked_complete_json_refused(world, rel):
    """Any other tracked complete.json at the build commit (any path, any component, even a byte copy of E2)."""
    put(world.repo / rel, (world.runtime / EXCEPTION).read_bytes())
    world.commit()
    reads = A.si.GIT_COUNTERS["object_reads"]
    refused(world, r"--repository HEAD tree: safe_input refused \[name\]: tracked complete.json outside the exact "
                   r"E4 list: " + re.escape(rel))
    ok(A.si.GIT_COUNTERS["object_reads"] == reads, "S4-R3-F3: an object was read before the metadata refusal")


@pytest.mark.parametrize("rel", [
    "complete.json", "data/complete.json", ".hidden/complete.json", E4V3_REL + "/complete.json",
    "pkg/complete.json/inner.txt", moved(EXCEPTION), "imitation/model/receipts/throughput-0935/COPY/complete.json",
])
def test_e4_extra_complete_json_in_runtime_tree_refused_before_read(world, audited, rel):
    """Untracked or not: any complete.json anywhere in the runtime tree, not listed anywhere, refuses unopened."""
    target = canary(world.runtime / rel)
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family complete-json: .*"
                   + re.escape(receipt_component(rel)))
    never_touched(audited, target)


@pytest.mark.parametrize("name", sorted(E4))
@pytest.mark.parametrize("where", ["runtime", "repository"])
def test_e4_each_entry_with_changed_bytes_refused(world, where, name):
    if where == "runtime":
        put(world.runtime / name, b"synthetic changed bytes\n")
        refused(world, "Runtime outcome-named entry differs from its pin: " + re.escape(name))
    else:
        put(world.repo / name, b"synthetic changed bytes\n")
        world.commit()
        reads = A.si.GIT_COUNTERS["object_reads"]          # r4: refused by its pinned blob OID in phase 1
        refused(world, r"safe_input refused \[exemption\]: E4 entry " + re.escape(name) + " is not the pinned")
        ok(A.si.GIT_COUNTERS["object_reads"] == reads, "S4-R3-F3: the changed E4 blob was read before refusal")


@pytest.mark.parametrize("name", sorted(E4))
@pytest.mark.parametrize("where", ["runtime", "repository"])
def test_e4_each_entry_at_a_moved_path_refused(world, audited, where, name):
    if where == "runtime":
        target = world.runtime / moved(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(world.runtime / name, target)
        os.chmod(target, 0)
        refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family complete-json: .*"
                       + re.escape(moved(name)))
        never_touched(audited, target)
    else:
        (world.repo / moved(name)).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(GIT + ["-C", str(world.repo), "mv", name, moved(name)], check=True)
        world.commit()
        refused(world, r"tracked complete.json outside the exact E4 list: " + re.escape(moved(name)))


@pytest.mark.parametrize("name", sorted(E4))
@pytest.mark.parametrize("where", ["runtime", "repository"])
def test_e4_entry_as_a_link_at_its_exact_path_is_never_followed(world, audited, where, name):
    """An exact E4 path that is a symlink (to bytes with the pinned SHA) is refused, never followed or aliased."""
    if where == "runtime":
        decoy = put(world.tmp / "decoy" / name, (world.runtime / name).read_bytes())
        os.remove(world.runtime / name)
        os.symlink(decoy, world.runtime / name)
        os.chmod(decoy, 0)
        refused(world, r"runtime tree: safe_input refused \[symlink\]: symlink in tree: " + re.escape(name))
        never_touched(audited, decoy)
    else:
        decoy = put(world.repo / "decoy" / "link-target.bin", (world.repo / name).read_bytes())
        os.remove(world.repo / name)
        os.symlink(os.path.relpath(decoy, (world.repo / name).parent), world.repo / name)
        world.commit()
        refused(world, r"safe_input refused \[exemption\]: E4 entry " + re.escape(name) + " is not the pinned 100644")


@pytest.mark.parametrize("name", sorted(E4))
def test_e4_entry_as_a_directory_or_executable_refused(world, name):
    os.chmod(world.repo / name, 0o755)                                 # mode 100755 at HEAD: not the ruled entry
    world.commit()
    refused(world, r"safe_input refused \[exemption\]: E4 entry " + re.escape(name) + " is not the pinned 100644")
    os.chmod(world.repo / name, 0o644)
    world.commit()
    os.remove(world.runtime / name)
    put(world.runtime / name / "inner.txt", b"x\n")                    # a directory at the exact runtime path
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family complete-json")


def test_e4_exact_paths_still_pass_the_location_gate_only_where_exempt():
    """r4: the E4 leaf exemption is safe_input's (final component exactly complete.json at an exact E4 path)."""
    host = A.this_host()
    for name in E4:
        A.si.name_gate("/r/" + name, host, (), e4_leaf=True)
        with pytest.raises(A.AssemblyError, match=r"probe: safe_input refused \[name\]: outcome name family complete"):
            A.location_free("/r/" + name, "probe")
        with pytest.raises(A.si.Refusal, match="outcome name family games"):
            A.si.name_gate("/r/games/" + name, host, (), e4_leaf=True)
        with pytest.raises(A.si.Refusal, match="strict END namespace"):
            A.si.name_gate("/r/reports/explore/k4s-confirm/end/" + name, host, (), e4_leaf=True)


# ---------------------------------------------------------------- frozen consumers (real frozen bytes; no host)

frozen = pytest.mark.skipif(not FROZEN, reason="K4S_FROZEN_ROOT (read-only origin/main checkout) not set")
FROZEN_PINS = {
    E4V3_REL + "/tier_backend.py": "02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d",
    E4V3_REL + "/fleet_validity.py": "0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f",
    E4V3_REL + "/state_rows.py": "3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755",
    E4V3_REL + "/fleet_profile.py": "5e482f0adc43ec1ffb56a7fc271fbf93e3258b9704a7d2e32c15594c0249fc8a",
    E4V3_REL + "/prepare_bundle.py": "a1c59fa3f9d546eaf212ef63fa3b3126bc039f4a86de384761832009e3cbe1bb",
    E4V3_REL + "/receipts.py": "839a43be635ca0de8db5f70f1a13459007a37f338e79ab6fef1fae43816460a6",
    E4V3_REL + "/telemetry.py": "808d6fab49304c12b98581e67a5150e87274db5eef137f6ce351346c31c7fd24",
    "reports/explore/t1/FROZEN-T1.json": A.FROZEN_T1_SHA256,
    "reports/explore/k4s-confirm/plan.json": A.K4S_PLAN_SHA256,
}


def check_frozen_root():
    root = Path(FROZEN)
    for rel, digest in FROZEN_PINS.items():
        ok(fsha(root / rel) == digest, "K4S_FROZEN_ROOT is not the frozen tree: " + rel)
    return root


@pytest.fixture
def real_world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch, real=check_frozen_root())


def frozen_python(code, *args):
    """Fresh interpreter, isolated (-I), no bytecode writes (-B), -O propagated; frozen e4v3 first on sys.path."""
    prelude = ("import sys,json;from pathlib import Path;sys.path.insert(0,%r)\n" % str(Path(FROZEN) / E4V3_REL))
    flags = ["-I", "-B"] + (["-O"] if sys.flags.optimize else [])
    return subprocess.run([sys.executable, *flags, "-c", prelude + code, *map(str, args)], capture_output=True, text=True)


@frozen
def test_frozen_python_inherits_optimize_flag():
    p = frozen_python("print(sys.flags.optimize)")
    ok(p.returncode == 0 and p.stdout.strip() == str(sys.flags.optimize), p.stdout + p.stderr)


@frozen
def test_frozen_measurement_rule_parity_with_reviewed_A5_inventory(real_world):
    """r4: measured on a runtime-like copy of the frozen e4v3 direct files (World(real=...)); a full repository
    checkout is not a runtime export (its e4v3/receipts hold family-named, D1 non-member files the walk refuses)."""
    reviewed = json.loads((Path(FROZEN) / "reports/explore/t1/receipts/END-A5-runtime-manifest-inventory-diff.json")
                          .read_text())["full_18_inventory"]
    measured = A.measurement_files(real_world.runtime / E4V3_REL, real_world.pins)
    ok(measured == reviewed, "e4v3 at the frozen root differs from the A5 18")
    ok(A.canonical_sha(measured) == A.PRODUCTION_PINS["measurement_files_sha256"], "measurement pin != frozen e4v3")


@frozen
def test_frozen_runtime_rule_parity(real_world):
    """Same names and SHAs as frozen prepare_bundle.runtime_pins, including the pinned alias and exception."""
    code = ("import prepare_bundle,receipts,hashlib\n"
            "r=prepare_bundle.runtime_pins(Path(sys.argv[1]))\n"
            "print(hashlib.sha256(receipts.canonical(r).encode()).hexdigest(),len(r))")
    p = frozen_python(code, real_world.runtime)
    ok(p.returncode == 0, p.stderr)
    mine = A.runtime_files(real_world.runtime, real_world.pins)
    ok(p.stdout.split() == [A.canonical_sha(mine), str(len(mine))], p.stdout)
    ok(ALIAS in mine and EXCEPTION in mine and ".hidden/h.py" in mine)
    os.remove(real_world.runtime / "data/x.json")
    p = frozen_python(code, real_world.runtime)
    ok(p.returncode != 0 and "Incomplete frozen runtime" in p.stderr)
    with pytest.raises(A.AssemblyError, match="Incomplete frozen runtime"):
        A.runtime_files(real_world.runtime, real_world.pins)


@frozen
def test_frozen_validate_bundle_accepts_and_rejects(real_world):
    _, out = real_world.run()
    code = ("import tier_backend as T\n"
            "T.V1_SHA,T.STUDENT_SHA,T.CALIBRATION_SHA=sys.argv[3:6]\n"
            "m=T.validate_bundle(sys.argv[1],sys.argv[2],dry_run=True,require_references=False)\n"
            "print(m['profile'])")
    shas = [fsha(real_world.models / n) for n in ("v1.pt", "R3a.pt", "R3a-calibration.json")]
    p = frozen_python(code, out, real_world.runtime, *shas)
    ok(p.returncode == 0 and p.stdout.strip() == "fleet-reference", p.stderr)
    target = out / "seed-inputs" / SEED_03
    os.chmod(target, 0o644)
    target.write_bytes(target.read_bytes() + b" ")
    p = frozen_python(code, out, real_world.runtime, *shas)
    ok(p.returncode != 0 and "Pin mismatch: seed-inputs/" in p.stderr, p.stderr)


@frozen
def test_frozen_state_rows_and_topology(real_world):
    _, out = real_world.run()
    code = ("import state_rows,telemetry\n"
            "m=json.loads((Path(sys.argv[1])/'tiers-pins.json').read_text())\n"
            "s=state_rows.StateRows(sys.argv[1],m['files']);n=len(s.ids);s.close()\n"
            "t=telemetry.validate_topology(m['topology'],list(range(128)),darwin=False)\n"
            "print(n,len(t['P']))")
    p = frozen_python(code, out)
    ok(p.returncode == 0 and p.stdout.split() == ["12", "128"], p.stderr)


STATE_ROWS_CODE = ("import state_rows\n"
                   "files=json.loads(sys.argv[2])\n"
                   "try:\n s=state_rows.StateRows(sys.argv[1],files);print('ACCEPT',len(s.ids));s.close()\n"
                   "except (ValueError,KeyError,TypeError) as e:print('REFUSE',type(e).__name__,e)\n")


@frozen
@pytest.mark.parametrize("label,mutate,match", INDEX_MUTANTS, ids=[m[0] for m in INDEX_MUTANTS])
def test_f3_frozen_state_rows_agrees_on_every_index_mutant(tmp_path, monkeypatch, label, mutate, match):
    """Each mutant the assembler refuses is also refused by the frozen loader (same bytes, real state_rows.py)."""
    w = World(tmp_path, monkeypatch)
    index = copy.deepcopy(w.index)
    mutate(index)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("states.pkl", "states-rows.bin"):
        shutil.copyfile(w.models / name, bundle / name)
    put(bundle / "states-rows.json", index)
    files = {n: fsha(bundle / n) for n in ("states.pkl", "states-rows.json", "states-rows.bin")}
    p = frozen_python(STATE_ROWS_CODE, bundle, json.dumps(files))
    ok(p.returncode == 0 and p.stdout.startswith("REFUSE"), label + ": frozen " + p.stdout + p.stderr)
    with pytest.raises(A.AssemblyError, match=match):
        A.check_state_index(index, {"states.pkl": files["states.pkl"], "states-rows.bin": files["states-rows.bin"]},
                            (bundle / "states-rows.bin").stat().st_size)
    p = frozen_python(STATE_ROWS_CODE, bundle, json.dumps(dict(files, **{"states-rows.json": "0" * 64})))
    ok(p.stdout.startswith("REFUSE ValueError Pin mismatch"), "control: the frozen loader pins the index bytes")


@frozen
@pytest.mark.parametrize("host", ["127x03", "127x04"])
def test_frozen_slot_layout(tmp_path, monkeypatch, host):
    w = World(tmp_path, monkeypatch, real=check_frozen_root(), host=host)
    _, out = w.run()
    code = ("import fleet_profile\n"
            "m=json.loads((Path(sys.argv[1])/'tiers-pins.json').read_text());p=m['reference_load_profile']\n"
            "plan=json.loads((Path(sys.argv[1])/p['plan']).read_text())\n"
            "s,b,c=fleet_profile.slot_layout(p,plan,sys.argv[2],10)\n"
            "print(len(s),len(b),c)")
    p = frozen_python(code, out, host)
    ok(p.returncode == 0 and p.stdout.split() == ["5", "10", "63"], p.stderr)


def stage_guard_job(world, out, job, *, idle=True, extra=()):
    """The DESIGN §A guard-job layout, built from the BUNDLE copies (byte-identical by construction)."""
    m = json.loads((out / "tiers-pins.json").read_text())
    g = m["reference_load_profile"]["guard"]
    job.mkdir(parents=True)
    shutil.copyfile(out / g["freeze"], job / "FROZEN-T1.json")
    for name, source in g["admissions"].items():
        if name != "idle-services.json" or idle:
            shutil.copyfile(out / source, job / name)
    for repo_path, source in g["seed_inputs"].items():
        (job / "repo" / repo_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / source, job / "repo" / repo_path)
    for name in extra:
        put(job / name, {"host": HOST})
    m["reference_load_profile"]["guard"]["job"] = str(job)      # test-only: the namespace rule is for real hosts
    return m


GUARD_CODE = ("import fleet_validity\n"
              "m=json.loads(Path(sys.argv[2]).read_text())\n"
              "g=fleet_validity.ReportingGuard(sys.argv[1],m,[])\n"
              "print(sorted(g.admissions),sorted(g.seed_dependencies))")


@frozen
def test_frozen_reporting_guard_init_accepts_bundle_and_job(real_world):
    _, out = real_world.run()
    m = stage_guard_job(real_world, out, real_world.tmp / "job")
    mpath = put(real_world.tmp / "guard-manifest.json", m)
    p = frozen_python(GUARD_CODE, out, mpath)
    ok(p.returncode == 0, p.stderr)
    ok(p.stdout.strip() == "%s %s" % (sorted(["FROZEN-T1.json", "system-bus-admission.json"]),   # r7: IR-03 (03)
                                       sorted(SEEDS)), p.stdout)


@frozen
@pytest.mark.parametrize("repin,variant,match", [
    (True, dict(idle=False), "No such file"),            # test-only idle re-pin: the pinned idle admission is absent
    (False, dict(extra=("idle-services.json",)), "Every existing guard admission must be pinned"),  # r7: IR-03 on 03
    (False, dict(extra=("owned-supervisor-admission.json",)), "Every existing guard admission must be pinned"),
])
def test_frozen_reporting_guard_init_rejects_bad_jobs(tmp_path, monkeypatch, repin, variant, match):
    real_world = World(tmp_path, monkeypatch, real=check_frozen_root(), idle=repin)
    _, out = real_world.run()
    m = stage_guard_job(real_world, out, real_world.tmp / "job", **variant)
    mpath = put(real_world.tmp / "guard-manifest.json", m)
    p = frozen_python(GUARD_CODE, out, mpath)
    ok(p.returncode != 0 and match in p.stderr, p.stderr)


@frozen
def test_frozen_reporting_guard_detects_changed_seed_in_job(real_world):
    _, out = real_world.run()
    m = stage_guard_job(real_world, out, real_world.tmp / "job")
    (real_world.tmp / "job" / "repo" / SEED_03).write_bytes(b"{}")
    mpath = put(real_world.tmp / "guard-manifest.json", m)
    p = frozen_python(GUARD_CODE, out, mpath)
    ok(p.returncode != 0 and "OP-5 seed/join input changed" in p.stderr, p.stderr)


# ---------------------------------------------------------------- production bytes on 05 (read-only; T1-owned)

q6 = pytest.mark.skipif(not (Q6_DIR / "states-rows.json").is_file(), reason="Q6 T1 copies not on this host (05 only)")


@q6
def test_production_q6_index_passes_the_mirror():
    """Reads only the 353 KB index (never the pickle or container bytes; container size from lstat)."""
    raw = (Q6_DIR / "states-rows.json").read_bytes()
    ok(sha(raw) == A.PRODUCTION_PINS["models"]["states-rows.json"], "05 index bytes differ from the pin")
    for name in ("states.pkl", "states-rows.bin"):
        ok(os.lstat(Q6_DIR / name).st_size > 0)
    ids = A.check_state_index(json.loads(raw), A.PRODUCTION_PINS["models"], os.lstat(Q6_DIR / "states-rows.bin").st_size)
    ok(len(ids) == json.loads(raw)["source"]["rows"])


@q6
@frozen
def test_production_q6_index_passes_frozen_state_rows_and_holds_t1_sets(tmp_path):
    raw = (Q6_DIR / "states-rows.json").read_bytes()
    index = json.loads(raw)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "states-rows.json").write_bytes(raw)
    with open(bundle / "states-rows.bin", "wb") as sparse:      # stand-in: the frozen __init__ only fstat()s it
        sparse.truncate(index["container"]["bytes"])
    (bundle / "states.pkl").write_bytes(b"")
    p = frozen_python(STATE_ROWS_CODE, bundle, json.dumps(A.PRODUCTION_PINS["models"]))
    ok(p.returncode == 0 and p.stdout.split()[:2] == ["ACCEPT", str(index["source"]["rows"])], p.stdout + p.stderr)
    ids = set(A.check_state_index(index, A.PRODUCTION_PINS["models"], index["container"]["bytes"]))
    for manifest in ("END-A3-manifest-01-f6cebbaa.json", "END-A3-manifest-08-f6cebbaa.json"):
        sets = json.loads((Path(FROZEN) / "reports/explore/t1/receipts" / manifest).read_text())["sets"]
        ok(A.canonical_sha(sets) == A.PRODUCTION_PINS["sets_canonical_sha256"], manifest)
        ok(len(sets["golden"]) == 125 and all(len(sets["speed"][t]) == 300 for t in A.TIERS))
        ok(all(set(sets["speed"][t]) <= ids for t in A.TIERS), "T1 speed sets must lie in the Q6 index")
