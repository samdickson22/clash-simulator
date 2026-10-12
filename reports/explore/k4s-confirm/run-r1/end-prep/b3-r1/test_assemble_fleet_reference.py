"""Offline tests for assemble_fleet_reference.py (CANDIDATE b3-r1). No host, no SSH, no outcomes.

Checks use ok() (an explicit raise), never a bare assert, so the suite keeps its force under `python -O`.

Two groups:
- synthetic: every input is generated in a temp dir; the frozen SHA constants are monkeypatched to the synthetic
  values. Covers the happy path, every fail-closed branch, determinism and input immutability.
- frozen consumers: need K4S_FROZEN_ROOT = a read-only checkout of origin/main (754c43cd was used). They take the
  real frozen bytes (e4v3 A5 directory, FROZEN-T1.json 24817e16, the nine T1 guard modules, the four OP-5 seed
  receipts, the K4S plan 38064dcd) and run the frozen consumers in fresh subprocesses: prepare_bundle.runtime_pins
  (parity), tier_backend.validate_bundle, state_rows.StateRows, fleet_validity.ReportingGuard.__init__,
  fleet_profile.slot_layout and telemetry.validate_topology. Skipped (with the reason) when the variable is unset.
"""
import hashlib
import importlib.util
import json
import os
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
JOB = "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1"
GUARD_FILES = [m + ".py" for m in A.GUARD_MODULES]
SEED_03 = "reports/explore/t1/receipts/op5-parent-source-127x03.json"
SEED_08 = "reports/explore/t1/receipts/op5-parent-source-127x08.json"
SEED_SERVER = "reports/explore/t1/receipts/op5-parent-generation-127x08.json"
SEED_CLIENT = ("reports/strategy_council_20260928/live-loop/v4/l1/receipts/a21-a2-preparation-20261010-r1/"
               "08-transport-identity-20261010T172047Z.json")
SEEDS = (SEED_03, SEED_08, SEED_SERVER, SEED_CLIENT)


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
    path.write_bytes(data if isinstance(data, bytes) else (json.dumps(data, indent=1) + "\n").encode())
    return path


def entry(path):
    return dict(source=str(path), sha256=fsha(path))


# ---------------------------------------------------------------- synthetic world

class World:
    """All inputs of one request. ``real`` = frozen root for the consumer tests (real frozen bytes)."""

    def __init__(self, tmp, monkeypatch, real=None, host=HOST):
        self.tmp, self.mp, self.real, self.host = Path(tmp), monkeypatch, real, host
        t = self.tmp
        # runtime tree: S1 runtime pin + qualified binding + e4v3 dir
        self.runtime = t / "runtime"
        put(self.runtime / "src/a.py", b"A = 1\n")
        put(self.runtime / "data/x.json", b"{}\n")
        put(self.runtime / "reports/explore/s1/anchor.py", b"# anchor\n")
        put(self.runtime / A.S1_RUNTIME_PINS[0], {"files": ["data/x.json", "src/a.py"]})
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
        self.mp.setattr(A, "V1_SHA", fsha(m / "v1.pt"))
        self.mp.setattr(A, "STUDENT_SHA", fsha(m / "R3a.pt"))
        self.mp.setattr(A, "CALIBRATION_SHA", fsha(m / "R3a-calibration.json"))
        put(t / "sets.json", dict(golden=self.ids[:6], speed={k: self.ids[i:i + 3] for i, k in enumerate(A.TIERS)}))
        # END evidence + artifacts at their relative paths
        art = self.artifacts = t / "repo/reports/explore/k4s-confirm"
        if real:
            put(art / "plan.json", (Path(real) / "reports/explore/k4s-confirm/plan.json").read_bytes())
        else:
            put(art / "plan.json", dict(study="PREREG-K4S", compute=dict(
                slots=11, console_slots=8, nice=10, forbidden_hosts=["127x05"],
                idle_service_exception=dict(hosts=["127x03", "127x08"]),
                hosts={h: dict(physical_cpus=list(range(55)), census_cpu=63) for h in ("127x03", "127x04")})))
            self.mp.setattr(A, "K4S_PLAN_SHA256", fsha(art / "plan.json"))
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
        self.write_evidence()
        # guard: freeze, modules, admissions, seeds
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
            self.mp.setattr(A, "FROZEN_T1_SHA256", fsha(g / "FROZEN-T1.json"))
        put(g / "adm/system-bus-admission.json", dict(utc="2026-10-12T00:00:00Z", host=host, identity=dict(
            pid=2005, start_ticks=1032, exe="/usr/bin/dbus-daemon", cmdline_sha256="f" * 64, uid=103)))
        put(g / "adm/idle-services.json", dict(utc="2026-10-12T00:00:00Z", host=host, services=[dict(
            name="v4-validation-cache", service=dict(pid=2180947), wrapper_trio=[])]))
        self.guard = g
        self.request = dict(
            schema=A.REQUEST_SCHEMA, host=host, runtime_root=str(self.runtime),
            runtime_files_sha256=A.canonical_sha(A.runtime_files(self.runtime)),
            measurement_files_sha256=A.canonical_sha(A.measurement_files(self.runtime / E4V3_REL)),
            topology=dict(P=list(range(128)), E=[], label="Linux logical IDs; physical masks pinned by reporting plan"),
            sets=entry(t / "sets.json"),
            models={n: entry(m / n) for n in A.MODEL_NAMES},
            end_evidence=dict(source=str(art / "end-evidence.json"), sha256=fsha(art / "end-evidence.json"),
                              artifacts_root=str(art)),
            guard=dict(job=JOB if host == "127x03" else "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1",
                       freeze=entry(g / "FROZEN-T1.json"),
                       modules={n: entry(g / "t1" / n) for n in GUARD_FILES},
                       admissions={"system-bus-admission.json": entry(g / "adm/system-bus-admission.json")},
                       seed_inputs={n: entry(g / "repo" / n) for n in SEEDS}))
        if host == "127x03":
            self.request["guard"]["admissions"]["idle-services.json"] = entry(g / "adm/idle-services.json")

    def item(self, path):
        rel = Path(path).relative_to(self.artifacts)
        return dict(path=str(rel), sha256=fsha(path), commit="e" * 40,
                    repository_path="reports/explore/k4s-confirm/" + str(rel))

    def write_evidence(self):
        put(self.artifacts / "end-evidence.json", (A.canonical(self.evidence_doc) + "\n").encode())
        if hasattr(self, "request"):
            self.request["end_evidence"]["sha256"] = fsha(self.artifacts / "end-evidence.json")

    def run(self, out=None, dry_run=False, request=None, request_sha=None):
        request = self.request if request is None else request
        path = put(self.tmp / "request.json", (A.canonical(request) + "\n").encode())
        out = self.tmp / "out" / "bundle" if out is None else Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = ["--request", str(path), "--request-sha256", request_sha or fsha(path), "--out", str(out)]
        return A.main(argv + (["--dry-run"] if dry_run else [])), out


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def snapshot(root):
    return {str(p): (fsha(p), p.stat().st_mtime_ns) for p in sorted(Path(root).rglob("*")) if p.is_file()}


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
    for name, digest in manifest["files"].items():
        ok(fsha(out / name) == digest, name)
        ok((out / name).stat().st_mode & 0o777 == 0o444, "bundle copies are read-only: " + name)
    ok(set(tree(out)) == set(manifest["files"]) | {"tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"})
    p = manifest["reference_load_profile"]
    ok({k: p[k] for k in ("host", "reference_slot", "slot_count", "console_rule", "warmup_seconds", "perception")}
       == dict(host=HOST, reference_slot=0, slot_count=11, console_rule=False, warmup_seconds=300, perception="none"))
    ok(p["plan"] == "k4s-end-evidence/plan.json" and p["end_evidence"] == "k4s-end-evidence/end-evidence.json")
    ok(manifest["files"][p["end_evidence"]] == world.request["end_evidence"]["sha256"])
    g = p["guard"]
    ok(g["root"] == "t1-guard" and g["job"] == JOB and g["freeze"] == "t1-freeze.json")
    ok(g["admissions"] == {"system-bus-admission.json": "guard-admissions/system-bus-admission.json",
                           "idle-services.json": "guard-admissions/idle-services.json"})
    ok(g["seed_inputs"] == {n: "seed-inputs/" + n for n in SEEDS})
    for name in A.MODEL_NAMES:
        ok(name in manifest["files"])
    for d in world.evidence_doc["phases"]:
        for f in ("launch", "supervisor_exit", "mhz", "census"):
            ok(manifest["files"]["k4s-end-evidence/" + d[f]["path"]] == d[f]["sha256"])
    ok(manifest["runtime_files"] == A.runtime_files(world.runtime))
    ok(manifest["measurement_files"] == {"build.sh": fsha(world.runtime / E4V3_REL / "build.sh"),
                                         "receipts.py": fsha(world.runtime / E4V3_REL / "receipts.py"),
                                         "spec-pins.json": fsha(world.runtime / E4V3_REL / "spec-pins.json"),
                                         "tier_backend.py": fsha(world.runtime / E4V3_REL / "tier_backend.py")})
    receipt = json.loads((out / "assembly-receipt.json").read_text())
    ok(receipt["manifest_sha256"] == sha(raw) and receipt["outcomes_read"] is False and receipt["final"] is False)


def test_host_04_has_no_idle_admission(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    _, out = w.run()
    g = json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]
    ok(g["job"] == "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1" and set(g["admissions"]) == {"system-bus-admission.json"})


def test_dry_run_prints_exact_manifest_and_writes_nothing(world, capsysbinary):
    before = snapshot(world.tmp)
    code, out = world.run(dry_run=True)
    printed = capsysbinary.readouterr().out
    ok(code == 0 and not out.exists() and not (out.parent / "bundle.partial").exists())
    after = snapshot(world.tmp)
    ok({k: v for k, v in after.items() if not k.endswith("request.json")}
       == {k: v for k, v in before.items() if not k.endswith("request.json")}, "dry run wrote something")
    _, out = world.run()
    ok((out / "tiers-pins.json").read_bytes() == printed, "dry-run output must equal the real manifest bytes")


def test_deterministic_byte_identical_bundles(world):
    _, one = world.run(out=world.tmp / "o1" / "bundle")
    _, two = world.run(out=world.tmp / "o2" / "bundle")
    ok(tree(one) == tree(two), "identical inputs must give byte-identical bundles")


def test_inputs_are_not_modified(world):
    before = snapshot(world.tmp)
    world.run()
    after = {k: v for k, v in snapshot(world.tmp).items() if "/out/" not in k}
    ok({k: v for k, v in after.items() if not k.endswith("request.json")}
       == {k: v for k, v in before.items() if not k.endswith("request.json")})


# ---------------------------------------------------------------- fail-closed branches (each leaves no bundle)

def refused(world, match, **kw):
    out = world.tmp / "out" / "bundle"
    with pytest.raises(A.AssemblyError, match=match):
        world.run(out=out, **kw)
    ok(not out.exists() and not (out.parent / "bundle.partial").exists(), "a refusal must leave no bundle")


def rewrite(path, value):
    os.chmod(path, 0o644)
    put(path, value)


def test_request_sha_mismatch(world):
    refused(world, "Request SHA mismatch", request_sha="0" * 64)


def test_request_schema_and_keys(world):
    world.request["schema"] = "other"
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
    refused(world, "runtime_root is not an existing dir")


def test_runtime_without_e4v3(world):
    shutil.rmtree(world.runtime / E4V3_REL)
    refused(world, "lacks the e4v3 directory")


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


def test_frozen_model_sha_enforced(world, monkeypatch):
    monkeypatch.setattr(A, "V1_SHA", "1" * 64)
    refused(world, "differs from the frozen value: model v1.pt")


def test_model_bytes_changed(world):
    put(world.models / "states.pkl", b"changed\n")
    refused(world, "Pin mismatch: model states.pkl")


@pytest.mark.parametrize("mutate,match", [
    (lambda i: i["source"].update(sha256="2" * 64), "not derived from the pinned states.pkl"),
    (lambda i: i["source"].update(verified=False), "not derived from the pinned states.pkl"),
    (lambda i: i["container"].update(bytes=i["container"]["bytes"] + 1), "container size differs"),
    (lambda i: i["rows"].append(dict(i["rows"][0])) or i["source"].update(rows=len(i["rows"])), "rows differ/duplicate"),
    (lambda i: i.update(schema="x"), "Unsupported state index"),
    (lambda i: i.pop("container"), "Malformed state index"),
])
def test_state_index_checks(world, mutate, match):
    mutate(world.index)
    put(world.models / "states-rows.json", world.index)
    world.request["models"]["states-rows.json"] = entry(world.models / "states-rows.json")
    refused(world, match)


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["speed"].pop("K4"), "sets.speed must be exactly"),
    (lambda s: s["speed"].update(K4=["missing:id"]), "absent from the pinned state index"),
    (lambda s: s["speed"].update(K2=["0:300:0", "0:300:0"]), "unique string IDs"),
    (lambda s: s.update(golden=[]), "unique string IDs"),
    (lambda s: s.update(extra=[]), "golden and speed"),
    (lambda s: s.pop("golden"), "golden and speed"),
])
def test_sets_checks(world, mutate, match):
    sets = json.loads((world.tmp / "sets.json").read_text())
    mutate(sets)
    put(world.tmp / "sets.json", sets)
    world.request["sets"] = entry(world.tmp / "sets.json")
    refused(world, match)


@pytest.mark.parametrize("topology,match", [
    (dict(P=[0, 1], E=[2], label="x"), "Topology must be"),
    (dict(P=[0, 0], E=[], label="x"), "unique non-negative"),
    (dict(P=[], E=[], label="x"), "unique non-negative"),
    (dict(P=[0, 1], E=[], label=""), "Topology must be"),
    (dict(P=[0, True], E=[], label="x"), "unique non-negative"),
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
    (lambda d: d["completion"].pop("repository_path"), "lacks path/sha256/commit/repository_path"),
    (lambda d: d["blind_ledger"].update(path=d["completion"]["path"]), "Conflicting END evidence pin"),
    (lambda d: d["completion"].update(path="run-r1/completion/missing.json"), "artifact missing"),
    (lambda d: d["completion"].update(sha256="4" * 64), "Pin mismatch: END evidence artifact"),
    (lambda d: d.update(phases=[]), "no phases"),
    (lambda d: d.update(phases=[p for p in d["phases"] if p["host"] != "127x03"]), "no counted phase on this host"),
    (lambda d: d["plan"].update(sha256=d["completion"]["sha256"], path=d["completion"]["path"]), "not the frozen K4S plan"),
    (lambda d: d["completion"].update(path="end-evidence.json", sha256="5" * 64), "Pin mismatch|collision"),
])
def test_evidence_item_checks(world, mutate, match):
    mutate(world.evidence_doc)
    world.write_evidence()
    refused(world, match)


def test_evidence_artifact_symlink_escape_refused(world):
    outside = put(world.tmp / "outside.json", {"synthetic": "completion.json"})
    target = world.artifacts / "run-r1/completion/completion.json"
    os.remove(target)
    os.symlink(outside, target)
    refused(world, "artifact missing under artifacts_root")


def test_outcome_paths_refused(world):
    games = world.tmp / "games"
    put(games / "x.json", {"a": 1})
    world.request["sets"] = entry(games / "x.json")
    refused(world, "Outcome-bearing path refused")
    world.request["sets"] = entry(world.tmp / "sets.json")
    put(world.tmp / "complete.json", {"a": 1})
    world.request["guard"]["admissions"]["system-bus-admission.json"] = entry(world.tmp / "complete.json")
    refused(world, "Outcome-bearing path refused")


def test_outcome_symlink_refused(world):
    games = world.tmp / "games"
    put(games / "x.json", {"a": 1})
    os.symlink(games / "x.json", world.tmp / "innocent.json")
    world.request["sets"] = entry(world.tmp / "innocent.json")
    refused(world, "Outcome-bearing path refused")


@pytest.mark.parametrize("compute,match", [
    ([], "Malformed K4S plan"),
    ({"hosts": {}}, "Malformed K4S plan"),
    ({"hosts": {"127x03": {}}, "slots": "11"}, "compute.slots must be an integer"),
])
def test_malformed_plan(world, monkeypatch, compute, match):
    put(world.artifacts / "plan.json", dict(study="PREREG-K4S", compute=compute))
    monkeypatch.setattr(A, "K4S_PLAN_SHA256", fsha(world.artifacts / "plan.json"))
    world.evidence_doc["plan"] = world.item(world.artifacts / "plan.json")
    world.write_evidence()
    refused(world, match)


def test_plan_checks(world, monkeypatch):
    plan = json.loads((world.artifacts / "plan.json").read_text())
    plan["compute"]["forbidden_hosts"] = ["127x03"]
    put(world.artifacts / "plan.json", plan)
    monkeypatch.setattr(A, "K4S_PLAN_SHA256", fsha(world.artifacts / "plan.json"))
    world.evidence_doc["plan"] = world.item(world.artifacts / "plan.json")
    world.write_evidence()
    refused(world, "Host absent/forbidden in plan")
    plan["compute"]["forbidden_hosts"] = []
    plan["study"] = "PREREG-SEARCH-TIERS"
    put(world.artifacts / "plan.json", plan)
    monkeypatch.setattr(A, "K4S_PLAN_SHA256", fsha(world.artifacts / "plan.json"))
    world.evidence_doc["plan"] = world.item(world.artifacts / "plan.json")
    world.write_evidence()
    refused(world, "not the K4S reporting plan")


@pytest.mark.parametrize("job", [
    "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1",                       # 04's parent on 03
    "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-op6-guard-job-01-r1",
    "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4",
    "/mpac/sdicks02/jobs/clasher/k4s-confirm-r1",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1/",
    "/mpac/sdicks02/jobs/clasher/../clasher/k4s-end-guard-r1",
    "/mpac/sdicks02/repos/clasher-v4-cache/k4s-end-guard-r1",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r0",
    "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-a00",
    "k4s-end-guard-r1",
    None,
])
def test_guard_job_namespace(world, job):
    world.request["guard"]["job"] = job
    refused(world, "Guard job must be")


def test_guard_job_per_attempt_name_accepted(world):
    world.request["guard"]["job"] = JOB + "-rd00-a01"
    _, out = world.run()
    ok(json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]["job"] == JOB + "-rd00-a01")


def test_guard_04_namespace_never_perception_path(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    w.request["guard"]["job"] = "/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1"     # 04 perception jobs root
    refused(w, "Guard job must be")


def test_guard_freeze_checks(world, monkeypatch):
    monkeypatch.setattr(A, "FROZEN_T1_SHA256", "6" * 64)
    refused(world, "differs from the frozen value: guard freeze")


@pytest.mark.parametrize("delta", ["operational_delta_op5", "operational_delta_op5_08", "operational_delta_op6"])
def test_guard_freeze_requires_confirm_deltas(world, monkeypatch, delta):
    world.freeze[delta] = dict(verdict="REQUEST_CHANGES")
    path = put(world.guard / "FROZEN-T1.json", world.freeze)
    monkeypatch.setattr(A, "FROZEN_T1_SHA256", fsha(path))
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
    refused(world, "differs from the frozen value: guard module host_audit.py")


def test_guard_admission_checks(world):
    adm = world.request["guard"]["admissions"]
    bus = adm.pop("system-bus-admission.json")
    refused(world, "system-bus-admission.json required")
    adm["system-bus-admission.json"] = bus
    put(world.guard / "adm/owned-supervisor-admission.json", dict(host=HOST, supervisor={}))
    adm["owned-supervisor-admission.json"] = entry(world.guard / "adm/owned-supervisor-admission.json")
    refused(world, "system-bus-admission.json required; only")
    del adm["owned-supervisor-admission.json"]
    put(world.guard / "adm/bus-04.json", dict(host="127x04", identity=dict(pid=1, start_ticks=1, exe="e", cmdline_sha256="f", uid=103)))
    adm["system-bus-admission.json"] = entry(world.guard / "adm/bus-04.json")
    refused(world, "different host")
    put(world.guard / "adm/bus-bad.json", dict(host=HOST, identity=dict(pid=1, start_ticks=1, exe="e", cmdline_sha256="f", uid=0)))
    adm["system-bus-admission.json"] = entry(world.guard / "adm/bus-bad.json")
    refused(world, "identity malformed")
    adm["system-bus-admission.json"] = bus
    put(world.guard / "adm/idle-bad.json", dict(host=HOST, services=[]))
    adm["idle-services.json"] = entry(world.guard / "adm/idle-bad.json")
    refused(world, "Idle-service admission malformed")


def test_idle_admission_refused_on_04(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    put(w.guard / "adm/idle-04.json", dict(host="127x04", services=[dict(name="n", service={}, wrapper_trio=[])]))
    w.request["guard"]["admissions"]["idle-services.json"] = entry(w.guard / "adm/idle-04.json")
    refused(w, "host without the exception")


def test_guard_seed_input_checks(world, monkeypatch):
    seeds = world.request["guard"]["seed_inputs"]
    client = seeds.pop(SEED_CLIENT)
    refused(world, "Missing pinned OP-5 seed/join input")
    seeds[SEED_CLIENT] = client
    seeds["reports/explore/t1/receipts/extra.json"] = client
    refused(world, "differs from frozen seed/join dependencies")
    del seeds["reports/explore/t1/receipts/extra.json"]
    put(world.guard / "other-03.json", dict(schema="clasher.t1.parent-source-seed.v1", host="127x03", note="other"))
    seeds[SEED_03] = entry(world.guard / "other-03.json")
    refused(world, "differs from the frozen value: seed " + SEED_03)


def test_guard_08_seed_requires_source_join(world, monkeypatch):
    receipt = json.loads((world.guard / "repo" / SEED_08).read_text())
    del receipt["source_join"]
    path = put(world.guard / "repo" / SEED_08, receipt)
    world.freeze["files"][SEED_08] = fsha(path)
    world.freeze["parent_source_seeds"][1]["sha256"] = fsha(path)
    fpath = put(world.guard / "FROZEN-T1.json", world.freeze)
    monkeypatch.setattr(A, "FROZEN_T1_SHA256", fsha(fpath))
    world.request["guard"]["freeze"] = entry(fpath)
    world.request["guard"]["seed_inputs"][SEED_08] = entry(path)
    refused(world, "08 seed lacks its source_join")


def test_seed_binding_not_in_freeze_files(world, monkeypatch):
    del world.freeze["files"][SEED_SERVER]
    fpath = put(world.guard / "FROZEN-T1.json", world.freeze)
    monkeypatch.setattr(A, "FROZEN_T1_SHA256", fsha(fpath))
    world.request["guard"]["freeze"] = entry(fpath)
    refused(world, "Unpinned/unsafe OP-5 seed dependency")


def test_input_entry_shape(world):
    world.request["sets"] = dict(source=str(world.tmp / "sets.json"))
    refused(world, r"must be \{source, sha256\}")
    world.request["sets"] = dict(source=str(world.tmp / "sets.json"), sha256="XYZ")
    refused(world, "Input SHA")


def test_out_checks(world):
    (world.tmp / "out" / "bundle").mkdir(parents=True)
    with pytest.raises(A.AssemblyError, match="new absolute directory"):
        world.run()
    shutil.rmtree(world.tmp / "out")
    (world.tmp / "out" / "bundle.partial").mkdir(parents=True)
    with pytest.raises(A.AssemblyError, match="previous partial"):
        world.run()
    with pytest.raises(A.AssemblyError, match="inside an input tree"):
        world.run(out=world.runtime / "bundle")
    with pytest.raises(A.AssemblyError, match="inside an input tree"):
        world.run(out=world.artifacts / "bundle")
    ok(not (world.runtime / "bundle").exists() and not (world.artifacts / "bundle").exists())


def test_copy_verification_failure_removes_partial(world, monkeypatch):
    real_copy = shutil.copyfile

    def corrupt(source, target):
        real_copy(source, target)
        if str(target).endswith("states.pkl"):
            Path(target).write_bytes(b"corrupted in transit\n")
    monkeypatch.setattr(A.shutil, "copyfile", corrupt)
    refused(world, "Copy differs from its pin: states.pkl")


def test_cli_exit_code_on_refusal(world):
    world.request["host"] = "127x09"
    path = put(world.tmp / "request.json", (A.canonical(world.request) + "\n").encode())
    p = subprocess.run([sys.executable, "-B", str(HERE / "assemble_fleet_reference.py"), "--request", str(path),
                        "--request-sha256", fsha(path), "--out", str(world.tmp / "cli-out"), "--dry-run"],
                       capture_output=True, text=True)
    ok(p.returncode == 2 and "ASSEMBLY REFUSED" in p.stderr and p.stdout == "", p.stderr)


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


@pytest.fixture
def real_world(tmp_path, monkeypatch):
    root = Path(FROZEN)
    for rel, digest in FROZEN_PINS.items():
        ok(fsha(root / rel) == digest, "K4S_FROZEN_ROOT is not the frozen tree: " + rel)
    return World(tmp_path, monkeypatch, real=root)


def frozen_python(code, *args):
    """Fresh interpreter, isolated (-I), no bytecode writes (-B); the frozen e4v3 directory first on sys.path."""
    prelude = ("import sys,json;from pathlib import Path;sys.path.insert(0,%r)\n" % str(Path(FROZEN) / E4V3_REL))
    p = subprocess.run([sys.executable, "-I", "-B", "-c", prelude + code, *map(str, args)], capture_output=True, text=True)
    return p


@frozen
def test_frozen_measurement_rule_parity_with_reviewed_A5_inventory():
    reviewed = json.loads((Path(FROZEN) / "reports/explore/t1/receipts/END-A5-runtime-manifest-inventory-diff.json")
                          .read_text())["full_18_inventory"]
    ok(A.measurement_files(Path(FROZEN) / E4V3_REL) == reviewed, "e4v3 at the frozen root differs from the A5 18")


@frozen
def test_frozen_runtime_rule_parity(real_world):
    code = ("import prepare_bundle,receipts,hashlib\n"
            "r=prepare_bundle.runtime_pins(Path(sys.argv[1]).resolve())\n"
            "print(hashlib.sha256(receipts.canonical(r).encode()).hexdigest())")
    p = frozen_python(code, real_world.runtime)
    ok(p.returncode == 0, p.stderr)
    ok(p.stdout.strip() == A.canonical_sha(A.runtime_files(real_world.runtime.resolve())))
    os.remove(real_world.runtime / "data/x.json")
    p = frozen_python(code, real_world.runtime)
    ok(p.returncode != 0 and "Incomplete frozen runtime" in p.stderr)
    with pytest.raises(A.AssemblyError, match="Incomplete frozen runtime"):
        A.runtime_files(real_world.runtime)


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


@frozen
@pytest.mark.parametrize("host", ["127x03", "127x04"])
def test_frozen_slot_layout(tmp_path, monkeypatch, host):
    w = World(tmp_path, monkeypatch, real=Path(FROZEN), host=host)
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
    ok(p.stdout.strip() == "%s %s" % (sorted(["FROZEN-T1.json", "idle-services.json", "system-bus-admission.json"]),
                                       sorted(SEEDS)), p.stdout)


@frozen
@pytest.mark.parametrize("variant,match", [
    (dict(idle=False), "No such file"),                                   # pinned idle admission absent in the job
    (dict(extra=("owned-supervisor-admission.json",)), "Every existing guard admission must be pinned"),
])
def test_frozen_reporting_guard_init_rejects_bad_jobs(real_world, variant, match):
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
