"""S4 r7 regression controls for ruling IR-03 (proposed, end-prep/IDLE-03-RETIREMENT-PROPOSAL.md): 127x03 has no idle
resident for K4S END. PRODUCTION_PINS["admissions"]["127x03"] is the system bus admission only, so a 127x03 request's
guard.admissions must be exactly {system-bus-admission.json} and its --committed-admission set is the bus only. A 127x03
request (or argv) that still names idle-services.json refuses with a message citing IR-03, before the retired committed
copy is read. 127x04 and every other pin are unchanged; the plan idle-host check (no idle admission on a host without
the exception) is unchanged. The generic idle checks stay covered by a test-only re-pin (World(idle=True)).

Real bytes (read-only, 05 only; skipped elsewhere): the three rewritten 127x03 requests in requests-ir03/ against their
end-staging sources (only guard.admissions["idle-services.json"] removed).
Checks use ok() (an explicit raise), never a bare assert, so they keep their force under python -O."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from test_assemble_fleet_reference import (GUARD_CODE, SEEDS, A, World, check_frozen_root, entry, frozen,  # noqa: F401
                                           frozen_python, fsha, ok, opened, put, refused, stage_guard_job, world)

HERE = Path(__file__).resolve().parent
BUS, IDLE = "system-bus-admission.json", "idle-services.json"
IR03 = r"refused: ruling IR-03 \(127x03 has no idle resident for K4S END"
BUS_03 = dict(pid=2049, start_ticks=1273, exe="/usr/bin/dbus-daemon", cmdline_sha256=A.DBUS_CMDLINE_SHA256, uid=103)
BUS_04 = dict(pid=2005, start_ticks=1032, exe="/usr/bin/dbus-daemon", cmdline_sha256=A.DBUS_CMDLINE_SHA256, uid=103)
# canonical_sha of the b3-r6 PRODUCTION_PINS with only admissions["127x03"]["idle-services.json"] deleted (computed from
# the b3-r6 bytes when r7 was written; see README r7): every other pin is unchanged.
R6_PINS_MINUS_03_IDLE = "95e3ec55f1fc7d8c5dfc20bde2f5cd86c3aa27c578a012156f883362bda04fd0"
STAGING = Path("/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests")
IR03_REQUESTS = HERE / "requests-ir03"
real_requests = pytest.mark.skipif(not (STAGING / "make_requests.out.json").is_file()
                                   or not (IR03_REQUESTS / "make_requests_ir03.out.json").is_file(),
                                   reason="the staged requests exist only on 127x05")


def production_admissions(world):
    """Give the synthetic world's bus admission the PRODUCTION identity and use PRODUCTION_PINS["admissions"] verbatim
    in the (synthetic) pins: the real admission pins decide this run."""
    doc = dict(world.admission_docs[BUS], identity=dict(BUS_03 if world.host == "127x03" else BUS_04))
    world.admission_docs[BUS] = doc
    rel = world.admission_rel(BUS)
    put(world.repo / rel, doc)
    world.commit()
    world.request["guard"]["admissions"][BUS] = entry(world.repo / rel)
    world.committed = [[BUS, rel, fsha(world.repo / rel)]]
    world.pin(lambda p: p.update(admissions=copy.deepcopy(A.PRODUCTION_PINS["admissions"])))


def retired_idle_file(world):
    """A committed 127x03-idle-services.json at its E3 path (as on the A' branch), named by nothing yet."""
    rel = world.admission_rel(IDLE)
    put(world.repo / rel, dict(utc="2026-10-12T00:00:00Z", host=world.host, services=[dict(
        name="v4-validation-cache", service=world.idle_service, wrapper_trio=[world.idle_service])]))
    world.commit()
    return rel


# ---------------------------------------------------------------- the pins

def test_r7_production_admission_pins_are_bus_only_on_both_hosts():
    P = A.PRODUCTION_PINS
    ok(P["admissions"] == {"127x03": {BUS: {"identity": BUS_03}}, "127x04": {BUS: {"identity": BUS_04}}})
    ok("idle" not in A.canonical(P["admissions"]), "no idle pin remains anywhere in the admissions")
    ok(A.IR03_HOST == "127x03" and A.ADMISSIONS == (BUS, IDLE))


def test_r7_every_other_pin_is_the_r6_value():
    ok(A.canonical_sha(A.PRODUCTION_PINS) == R6_PINS_MINUS_03_IDLE, "only the 03 idle pin may differ from b3-r6")


def test_r7_retired_idle_is_pin_driven_and_03_only():
    P = A.PRODUCTION_PINS
    ok(A.retired_idle("127x03", {IDLE: 1}, P) and A.retired_idle("127x03", (IDLE,), P))
    ok(not A.retired_idle("127x03", {BUS: 1}, P), "the bus admission is never retired")
    ok(not A.retired_idle("127x04", (IDLE,), P), "04 keeps its r6 refusal (not IR-03)")
    repinned = copy.deepcopy(P)
    repinned["admissions"]["127x03"][IDLE] = {"service": {}}
    ok(not A.retired_idle("127x03", (IDLE,), repinned), "a future coordinator re-pin lifts IR-03")


# ---------------------------------------------------------------- 127x03: bus only passes

def test_r7_03_bus_only_bundle(world):
    ok(world.host == "127x03" and set(world.request["guard"]["admissions"]) == {BUS})
    code, out = world.run()
    ok(code == 0)
    manifest = json.loads((out / "tiers-pins.json").read_text())
    ok(manifest["reference_load_profile"]["guard"]["admissions"] == {BUS: "guard-admissions/" + BUS})
    ok(not [n for n in manifest["files"] if IDLE in n], "no idle admission in a 03 bundle")
    receipt = json.loads((out / "assembly-receipt.json").read_text())
    ok(set(receipt["committed_admissions"]) == {BUS})


@pytest.mark.parametrize("host", ["127x03", "127x04"])
def test_r7_bus_only_passes_under_the_production_admission_pins(tmp_path, monkeypatch, host):
    w = World(tmp_path, monkeypatch, host=host)
    production_admissions(w)
    code, out = w.run()
    ok(code == 0)
    g = json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]
    ok(g["admissions"] == {BUS: "guard-admissions/" + BUS})


def test_r7_03_bus_only_ignores_the_retired_committed_idle_copy(tmp_path, monkeypatch, opened):
    """The A' branch keeps 127x03-idle-services.json (append-only); a bus-only 03 request passes and never opens it."""
    w = World(tmp_path, monkeypatch)
    production_admissions(w)
    rel = retired_idle_file(w)
    code, _ = w.run()
    ok(code == 0)
    ok(not [p for p in opened if p.endswith("/" + rel) or p.endswith("-" + IDLE)], "the retired idle copy was opened")
    ok([p for p in opened if p.endswith("/" + w.admission_rel(BUS))], "control: the recorder saw the bus admission read")


# ---------------------------------------------------------------- 127x03: idle named -> IR-03 refusal

def test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it(tmp_path, monkeypatch, opened):
    w = World(tmp_path, monkeypatch)
    production_admissions(w)
    rel = retired_idle_file(w)
    w.request["guard"]["admissions"][IDLE] = entry(w.repo / rel)          # the r6 request shape, argv bus only
    refused(w, "guard.admissions idle-services.json on 127x03 " + IR03)
    ok(not [p for p in opened if p.endswith("/" + rel)], "the retired idle copy was read before the IR-03 refusal")
    ok(str(w.guard / "FROZEN-T1.json") in opened, "control: the recorder saw the guard freeze read (step 6, earlier)")


def test_r7_03_committed_idle_binding_refuses_citing_ir03(tmp_path, monkeypatch, opened):
    w = World(tmp_path, monkeypatch)
    production_admissions(w)
    rel = retired_idle_file(w)
    w.committed.append([IDLE, rel, fsha(w.repo / rel)])                   # argv names idle, the request does not
    refused(w, "--committed-admission idle-services.json on 127x03 " + IR03)
    w.request["guard"]["admissions"][IDLE] = entry(w.repo / rel)          # both: the pure argv check comes first
    refused(w, "--committed-admission idle-services.json on 127x03 " + IR03)
    ok(not [p for p in opened if p.endswith("/" + rel)], "the retired idle copy was read")


def test_r7_committed_bindings_refusal_is_pure():
    """The argv refusal needs no file at all (step 0, before any access)."""
    rel = A.ADMISSION_REPO_DIR + "/127x03-" + IDLE
    with pytest.raises(A.AssemblyError, match="--committed-admission idle-services.json on 127x03 " + IR03):
        A.committed_bindings([[BUS, A.ADMISSION_REPO_DIR + "/127x03-" + BUS, "1" * 64], [IDLE, rel, "2" * 64]],
                             "127x03", A.PRODUCTION_PINS)
    ok(A.committed_bindings([[BUS, A.ADMISSION_REPO_DIR + "/127x03-" + BUS, "1" * 64]], "127x03", A.PRODUCTION_PINS)
       == {BUS: (A.ADMISSION_REPO_DIR + "/127x03-" + BUS, "1" * 64)})


def test_r7_03_idle_only_still_refuses_the_missing_bus(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    production_admissions(w)
    rel = retired_idle_file(w)
    w.request["guard"]["admissions"] = {IDLE: entry(w.repo / rel)}
    refused(w, "guard.admissions idle-services.json on 127x03 " + IR03)
    del w.request["guard"]["admissions"][IDLE]
    refused(w, r"Admissions on 127x03 must be exactly \['system-bus-admission.json'\]")


def test_r7_03_repinned_idle_is_accepted_test_only(tmp_path, monkeypatch):
    """Control: with a (synthetic) coordinator re-pin of the idle service on 03 the generic r6 path still works."""
    w = World(tmp_path, monkeypatch, idle=True)
    code, out = w.run()
    ok(code == 0)
    g = json.loads((out / "tiers-pins.json").read_text())["reference_load_profile"]["guard"]
    ok(set(g["admissions"]) == {BUS, IDLE})


# ---------------------------------------------------------------- 127x04 unchanged

def test_r7_04_idle_in_request_keeps_the_r6_refusal(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, host="127x04")
    production_admissions(w)
    rel = retired_idle_file(w)
    w.request["guard"]["admissions"][IDLE] = entry(w.repo / rel)
    with pytest.raises(A.AssemblyError) as info:
        w.run()
    ok(str(info.value).startswith("Admissions on 127x04 must be exactly ['system-bus-admission.json']"), str(info.value))
    ok("IR-03" not in str(info.value))
    w.committed.append([IDLE, rel, fsha(w.repo / rel)])
    with pytest.raises(A.AssemblyError) as info:
        w.run()
    ok(str(info.value).startswith("--committed-admission is required for exactly ['system-bus-admission.json'] on "
                                  "127x04"), str(info.value))
    ok("IR-03" not in str(info.value))


def test_r7_plan_idle_host_check_unchanged(tmp_path, monkeypatch):
    """:989 (an idle admission only on a plan idle_service_exception host) stays: a synthetic idle pin on 04 refuses."""
    w = World(tmp_path, monkeypatch, host="127x04")
    rel = retired_idle_file(w)
    w.request["guard"]["admissions"][IDLE] = entry(w.repo / rel)
    w.committed.append([IDLE, rel, fsha(w.repo / rel)])
    w.pin(lambda p: p["admissions"]["127x04"].update({IDLE: {"service": w.idle_service}}))
    refused(w, "Idle-service admission on a host without the exception")


# ---------------------------------------------------------------- frozen guard (fleet_validity) on a 03 bus-only bundle

@frozen
def test_r7_frozen_guard_accepts_03_bus_only_job(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, real=check_frozen_root())
    _, out = w.run()
    m = stage_guard_job(w, out, w.tmp / "job")
    ok(sorted(p.name for p in (w.tmp / "job").iterdir() if p.is_file()) == ["FROZEN-T1.json", BUS])
    p = frozen_python(GUARD_CODE, out, put(w.tmp / "guard-manifest.json", m))
    ok(p.returncode == 0, p.stderr)
    ok(p.stdout.strip() == "%s %s" % (sorted(["FROZEN-T1.json", BUS]), sorted(SEEDS)), p.stdout)


@frozen
def test_r7_frozen_guard_refuses_03_job_carrying_the_retired_idle_file(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, real=check_frozen_root())
    _, out = w.run()
    m = stage_guard_job(w, out, w.tmp / "job", extra=(IDLE,))
    p = frozen_python(GUARD_CODE, out, put(w.tmp / "guard-manifest.json", m))
    ok(p.returncode != 0 and "Every existing guard admission must be pinned" in p.stderr, p.stderr)


# ---------------------------------------------------------------- the three rewritten 127x03 requests (real, read-only)

@real_requests
@pytest.mark.parametrize("name", ["request-127x03-pf00.json", "request-127x03-rd00-a00.json",
                                  "request-127x03-rd00-a01.json"])
def test_r7_real_ir03_requests_drop_only_the_idle_admission(name):
    source_meta = json.loads((STAGING / "make_requests.out.json").read_bytes())["requests"]
    meta = json.loads((IR03_REQUESTS / "make_requests_ir03.out.json").read_bytes())["requests"]
    src_raw, new_raw = (STAGING / name).read_bytes(), (IR03_REQUESTS / name).read_bytes()
    ok(hashlib.sha256(src_raw).hexdigest() == source_meta[str(STAGING / name)]["sha256"])
    rows = [v for k, v in meta.items() if k.rsplit("/", 1)[-1] == name]   # runner: location-independent (copied trees)
    ok(len(rows) == 1, "exactly one metadata row for " + name)
    row = rows[0]
    ok(hashlib.sha256(new_raw).hexdigest() == row["sha256"] and row["source_sha256"] == hashlib.sha256(src_raw).hexdigest())
    src, new = json.loads(src_raw), json.loads(new_raw)
    ok(new_raw == (json.dumps(new, indent=1, sort_keys=True) + "\n").encode(), "same writer as make_requests")
    ok(new["host"] == "127x03" and set(new["guard"]["admissions"]) == {BUS})
    ok(new["guard"]["job"] == src["guard"]["job"], "the guard job name is unchanged")
    src["guard"]["admissions"].pop(IDLE)
    ok(new == src, "only guard.admissions[idle-services.json] differs")
    ok(row["admissions"] == {BUS: new["guard"]["admissions"][BUS]["sha256"]})
