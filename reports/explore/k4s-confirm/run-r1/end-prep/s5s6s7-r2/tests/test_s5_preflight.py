"""S5 preflight r2 (k4s_end_preflight.py). Frozen modules are faked (fake_frozen.py); the guard monitor is a real
spawned process speaking the real checkpoint protocol. Covers Sol PKG2 S5-F1/F2/F3 regressions, the frozen-reader
clone checks and git environment, P2-3 mode/load/duration/bus bands, and verify-received through safe_input.
Not covered offline: the real frozen modules, the T1 guard on a host, torch/native loading, real bus/MHz/sshd."""
import ast
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

import fake_frozen
import helpers as H
import k4s_end_preflight as S
import s5_fixture as X
from helpers import ok, raises, refused

PROD_MANIFEST = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
PROD_CLOSURE = dict(S.FROZEN_CLOSURE)


@pytest.fixture(autouse=True)
def host_os(monkeypatch):
    saved = dict(os.environ)
    masks = {900001 + i: {2 + 2 * i, 3 + 2 * i} for i in range(10)}
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: None)
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: masks.get(pid, {0, 1}))
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 10)
    fake_frozen.CALLS.clear()
    yield
    os.environ.clear()
    os.environ.update(saved)


def by_name(result):
    return {c["name"]: c for c in result["checks"]}


# ---------------------------------------------------------------- pure checks and production anchors

@pytest.mark.parametrize("info,hold,samples,block,manifest,needle", [
    (dict(host="127x05"), 960, 60, 30, PROD_MANIFEST, "127x03/127x04"),
    (dict(nice=0), 960, 60, 30, PROD_MANIFEST, "nice 10"),
    (dict(sched_other=False), 960, 60, 30, PROD_MANIFEST, "SCHED_OTHER"),
    (dict(optimized=True), 960, 60, 30, PROD_MANIFEST, "optimized"),
    (dict(host="127x04"), 899, 60, 30, PROD_MANIFEST, "minimum"),
    (dict(), 119, 60, 30, PROD_MANIFEST, "minimum"),
    (dict(), 120, 59, 30, PROD_MANIFEST, "60 guard samples"),
    (dict(), 120, 60, 0, PROD_MANIFEST, "block seconds"),
    (dict(), 120, 60, 30, "a" * 64, "manifest of record"),
])
def test_refusals(info, hold, samples, block, manifest, needle):
    h = dict(dict(host="127x03", nice=10, sched_other=True, optimized=False), **info)
    reasons = S.refusals(h["host"], h["nice"], h["sched_other"], h["optimized"], hold, samples, block, manifest)
    ok(any(needle in r for r in reasons), reasons)
    ok(S.refusals("127x04", 10, True, False, 900, 60, 30, PROD_MANIFEST) == [])


def test_production_anchor_and_closure_equal_the_manifest_of_record():
    """S5-F1: the anchor is a code constant, and FROZEN_CLOSURE is exactly what 74314eda pins (read through
    si.git_show_file with the pinned SHA from the shared checkout: metadata + one pinned blob, no outcome data)."""
    ok(S.K4S_MANIFEST_SHA256 == PROD_MANIFEST and len(PROD_CLOSURE) == 32)
    si, _ = H.load_layers()
    repo = "/mpac/sdicks02/repos/clasher"
    P = si.Policy(os.uname().nodename.split(".")[0], [si.Role("repo", repo, "read", 4 << 20, exact=(S.MANIFEST_REL,))])
    commit = si.git_run(si.GitRepo(work_tree=repo), ["rev-parse", "--verify", "origin/main^{commit}"]).stdout
    data = si.git_show_file(P, "repo", si.GitRepo(work_tree=repo), commit.decode().strip(), S.MANIFEST_REL,
                            expected_sha256=PROD_MANIFEST)
    m = si.loads_strict(data)
    derived = {}
    for key in ("k4s_files", "end_files", "reused_readonly"):
        derived.update(m[key])
    derived.update(m["k4s_kernel"]["files"])
    derived[m["sd1_manifest"]["path"]] = m["sd1_manifest"]["sha256"]
    ok(derived == PROD_CLOSURE)
    ok(m["corpus"]["inventory"] == S.CORPUS_INVENTORY_REL)


def test_layout_refusals(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    base = str(env.base)
    good = vars(env.a).copy()
    cases = [("runtime_root", base + "/runtime"), ("runtime_root", base + "/other/runtime-0123456789ab"),
             ("bundle", base + "/elsewhere/pf00"), ("compare_bundle", env.a.bundle),
             ("repository", base + "/repository2"), ("attempt_parent", base + "/attempts/x"),
             ("out", base + "/preflight/preflight-127x03-l00/other"), ("out", base + "/attempts/preflight-127x03-l00/preflight-127x03-l00"),
             ("out", base + "/preflight/preflight-127x04-l00/preflight-127x04-l00"),
             ("corpus_inventory", base + "/inputs/corpora.json"), ("native", base + "/attempts/native.so"),
             ("native", "/tmp/native.so"), ("corpus", base + "/repository/x.pkl"),
             ("end_evidence", base + "/bundles/a00/end-evidence.json"), ("bundle_pins_sha256", "x"),
             ("compare_bundle_pins_sha256", None)]
    for key, value in cases:
        fields = dict(good, **{key: value})
        if key == "runtime_root":                              # keep the dependent path consistent
            fields["corpus_inventory"] = value + "/" + S.CORPUS_INVENTORY_REL
        a = type(env.a)(**fields)
        raises(S.PreflightRefusal, S.layout, a, env.host, base)
    S.layout(env.a, env.host, base)


# ---------------------------------------------------------------- S5-F1: anchored manifest, closure before import

CANARY_MODULE = "open(%r, 'x').write('EXECUTED')\n"


def canary_env(tmp_path, monkeypatch):
    marker = tmp_path / "EXECUTED-marker"
    contents = {S.STUDY_REL + "/end_reference.py": CANARY_MODULE % str(marker)}
    return X.build(tmp_path, monkeypatch, contents=contents), marker


def drop_runtime_modules(env):
    for name, module in list(sys.modules.items()):
        if str(getattr(module, "__file__", "") or "").startswith(str(env.runtime)):
            del sys.modules[name]
    sys.path[:] = [p for p in sys.path if not p.startswith(str(env.runtime))]


def test_unanchored_manifest_refused_and_nothing_executed(tmp_path, monkeypatch):
    """Sol S5-F1 probe: an arbitrary same-schema manifest with its own supplied SHA no longer passes; the canary
    end_reference never executes, before or after the store exists."""
    env, marker = canary_env(tmp_path, monkeypatch)
    monkeypatch.setattr(S, "K4S_MANIFEST_SHA256", PROD_MANIFEST)
    monkeypatch.setattr(S, "FROZEN_CLOSURE", PROD_CLOSURE)
    raises(S.PreflightRefusal, X.go, env, frozen_factory=S.Frozen, match="manifest of record")
    ok(not Path(env.a.out).exists() and not marker.exists())
    env.a.k4s_manifest_sha256 = PROD_MANIFEST            # caller names the right SHA; the bytes are not 74314eda
    try:
        code, result, seal = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    rows = by_name(result)
    ok(code == 1 and seal["status"] == "failed" and rows["pre_import_pins"]["passed"] is False)
    ok("frozen_import" not in rows and not marker.exists())


def test_tampered_closure_file_refused_before_import(tmp_path, monkeypatch):
    env, marker = canary_env(tmp_path, monkeypatch)
    victim = env.runtime / S.STUDY_REL / "end_evidence.py"
    os.chmod(victim, 0o644)
    victim.write_text("# same name, other bytes\n")
    try:
        code, result, _ = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    ok(code == 1 and by_name(result)["pre_import_pins"]["passed"] is False and not marker.exists())


def test_manifest_with_same_closure_but_other_bytes_refused(tmp_path, monkeypatch):
    """The anchor is the SHA of the manifest BYTES, not of the closure it yields."""
    env, marker = canary_env(tmp_path, monkeypatch)
    path = env.runtime / S.MANIFEST_REL
    doc = json.loads(path.read_text())
    doc["note"] = "same closure, other bytes"
    os.chmod(path, 0o644)
    path.write_text(json.dumps(doc, sort_keys=True) + "\n")
    try:
        code, result, _ = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    row = by_name(result)["pre_import_pins"]
    ok(code == 1 and row["passed"] is False and "sha" in row["error"] and not marker.exists(), row)


def test_code_closure_table_must_equal_the_manifest(tmp_path, monkeypatch):
    env, marker = canary_env(tmp_path, monkeypatch)
    smaller = dict(S.FROZEN_CLOSURE)
    smaller.pop(sorted(smaller)[0])
    monkeypatch.setattr(S, "FROZEN_CLOSURE", smaller)
    try:
        code, result, _ = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    row = by_name(result)["pre_import_pins"]
    ok(code == 1 and "closure differs" in row["error"] and not marker.exists(), row)


@pytest.mark.parametrize("alias", ["ancestor-symlink", "hard-link"])
def test_closure_aliases_refused_before_import(tmp_path, monkeypatch, alias):
    """Sol S5-F2 probe: an in-root ancestor symlink to a relocated directory, or a hard-linked source, is refused
    by safe_input before any byte is hashed; nothing is imported."""
    env, marker = canary_env(tmp_path, monkeypatch)
    mac = env.runtime / S.STUDY_REL / "mac"
    if alias == "ancestor-symlink":
        moved = env.runtime / "relocated-mac"
        shutil.move(str(mac), str(moved))
        os.symlink(moved, mac)
    else:
        os.link(mac / "k4s_logic.py", tmp_path / "external-alias")
    try:
        code, result, _ = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    row = by_name(result)["pre_import_pins"]
    ok(code == 1 and row["passed"] is False and ("symlink" in row["error"] or "nlink" in row["error"]), row)
    ok(not marker.exists())


def test_verified_closure_is_imported_only_afterwards(tmp_path, monkeypatch):
    """Positive control for the order: with a correctly pinned (synthetic) closure the real Frozen() import runs
    the canary, which proves the refusals above happened before any runtime code could execute."""
    env, marker = canary_env(tmp_path, monkeypatch)
    try:
        code, result, _ = X.go(env, frozen_factory=S.Frozen)
    finally:
        drop_runtime_modules(env)
    rows = by_name(result)
    ok(rows["pre_import_pins"]["passed"] is True and marker.exists() and rows["frozen_import"]["passed"] is False)


# ---------------------------------------------------------------- S5-F2: bundle stamp, input aliases

@pytest.mark.parametrize("variant", ["synthetic-key", "receipt-not-production", "receipt-status",
                                     "receipt-other-manifest", "sidecar"])
def test_s4_test_only_or_unbound_bundle_refused(tmp_path, monkeypatch, variant):
    env = X.build(tmp_path, monkeypatch)
    manifest = json.loads(H.canonical(env.F.manifest))
    over = None
    if variant == "synthetic-key":
        manifest["k4s_s4_synthetic"] = "SYNTHETIC-TEST-ONLY"
    elif variant == "receipt-not-production":
        over = dict(production_pins=False)
    elif variant == "receipt-status":
        over = dict(status="SYNTHETIC-TEST-ONLY")
    elif variant == "receipt-other-manifest":
        over = dict(manifest_sha256="0" * 64)
    shutil.rmtree(env.pf_bundle)
    env.a.bundle_pins_sha256 = X.bundle(env.pf_bundle, manifest, over)
    if variant == "sidecar":
        H.write(env.pf_bundle / "tiers-pins.sha256", "0" * 64 + "  tiers-pins.json\n")
    raises(S.PreflightRefusal, X.go, env)
    ok(not Path(env.a.out).exists())


def test_bundle_manifest_bytes_must_match_the_pin(tmp_path, monkeypatch):
    """Sidecar and assembly receipt still name the original SHA; only the pinned read can see the edit."""
    env = X.build(tmp_path, monkeypatch)
    path = env.pf_bundle / "tiers-pins.json"
    doc = json.loads(path.read_text())
    doc["files"]["extra"] = "0" * 64
    os.chmod(path, 0o644)
    path.write_text(H.canonical(doc) + "\n")
    refused(env.si, "sha", X.go, env)
    ok(not Path(env.a.out).exists())


@pytest.mark.parametrize("which", ["preflight-rd", "compare-pf"])
def test_guard_job_forms_enforced(tmp_path, monkeypatch, which):
    env = X.build(tmp_path, monkeypatch)
    target = env.pf_bundle if which == "preflight-rd" else env.at_bundle
    manifest = json.loads((target / "tiers-pins.json").read_text())
    other = env.at_job if which == "preflight-rd" else env.pf_job
    manifest["reference_load_profile"]["guard"]["job"] = str(other)
    shutil.rmtree(target)
    digest = X.bundle(target, manifest)
    if which == "preflight-rd":
        env.a.bundle_pins_sha256 = digest
        raises(S.PreflightRefusal, X.go, env, match="-pfNN")
    else:
        env.a.compare_bundle_pins_sha256 = digest
        code, result, _ = X.go(env)
        ok(code == 1 and "-pfNN" in by_name(result)["bundle_stamp"]["error"])


def test_frozen_manifest_must_be_the_pinned_bundle(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    other = dict(env.F.manifest, files={"drift": "1" * 64})
    original = env.F.ER.frozen_identity
    env.F.ER.frozen_identity = lambda a, vb, ns: (other,) + tuple(original(a, vb, ns)[1:])
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["frozen_identity"]["passed"] is False)


def test_sample_minimum_enforced(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, min_samples=10 ** 6)
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["guard_samples"]["passed"] is False)


def test_bundle_manifest_hard_link_alias_refused(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    os.link(env.pf_bundle / "tiers-pins.json", tmp_path / "alias")
    refused(env.si, "nlink", X.go, env)
    ok(not Path(env.a.out).exists())


def test_native_symlink_refused(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    real = H.write(tmp_path / "foreign-native.so", b"x")
    os.unlink(env.a.native)
    os.symlink(real, env.a.native)
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["input_locations"]["passed"] is False)


def test_existing_output_refuses_without_writing(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    canary = H.canary(tmp_path / "canary")
    os.symlink(tmp_path, env.a.out)
    refused(env.si, "exists", X.go, env)
    ok(H.canary_intact(canary))


# ---------------------------------------------------------------- frozen-reader ruling

def test_guard_repo_replace_ref_refused(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    repo = env.pf_job / "repo"
    a, b = S.SEED_COMMITS
    H.git(repo, "replace", a, b)
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["guard_repo"]["passed"] is False)


def test_guard_repo_missing_seed_commit_refused(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    monkeypatch.setattr(S, "SEED_COMMITS", ("0" * 40,) + S.SEED_COMMITS[1:])
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["guard_repo"]["passed"] is False)


def test_repository_alternates_refused(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    H.write(Path(env.a.repository) / ".git/objects/info/alternates", str(tmp_path) + "\n")
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["repository_clone"]["passed"] is False)


def test_frozen_git_env_applied_before_import(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    seen = {}

    def factory(root):
        seen.update({k: v for k, v in os.environ.items() if k.startswith("GIT_")})
        return env.F
    code, result, _ = X.go(env, frozen_factory=factory)
    ok(code == 0, result.get("error"))
    ok("GIT_DIR" not in seen and seen["GIT_NO_REPLACE_OBJECTS"] == "1" and seen["GIT_CONFIG_NOSYSTEM"] == "1")
    ok(seen["GIT_CONFIG_PARAMETERS"] == env.tool.GIT_CONFIG_PARAMETERS)


# ---------------------------------------------------------------- orchestration (P2-3 mode, load, duration, bus)

ORDER = ["listings_before", "bundle_stamp", "input_locations", "guard_repo", "repository_clone", "frozen_git_env",
         "pre_import_pins", "frozen_import", "frozen_helpers", "frozen_identity", "bundle_parity", "guard_job_fresh",
         "reporting_profile", "physical_cpus", "end_job_read_only", "backend_and_corpus", "topology",
         "guard_admission", "background_ready", "loaded_hold", "monitor_stop", "guard_samples",
         "frozen_guard_validators", "mhz_comparison", "post_pins", "cleanup"]


def test_binding_happy_path(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(bus_percent=0.1, side_file="op2-confirmations.jsonl"))
    code, result, seal = X.go(env)
    ok(code == 0 and seal["status"] == "passed" and seal["scope"] == "K4S-END-PREFLIGHT", result.get("error"))
    ok([c["name"] for c in result["checks"]] == ORDER, [c["name"] for c in result["checks"]])
    ok(result["passed"] and result["mode"] == "binding" and result["qualifying"] is True)
    ok(result["bus_band"] == "proceed" and result["bus_gate"] == "not-gated-on-127x03")
    ok(result["load"] == dict(slot_count=3, background_slots_expected=2, reference_slot_work=True,
                              background_slots_ready=2, reference_slot_states_worked=result["load"][
                                  "reference_slot_states_worked"]) and result["load"]["reference_slot_states_worked"] > 0)
    ok(result["duration"]["loaded_seconds_measured"] >= 0.2 and result["duration"]["hold_seconds_requested"] == 0.8)
    ok(result["claim"] is False and result["measure_called"] is False and fake_frozen.CALLS == [])
    ok(result["guard_sources"] == ["op2-confirmations.jsonl"] and "guard-sources/op2-confirmations.jsonl" in seal["files"])
    ok(result["attempt_parent_empty"] and result["registry_and_attempt_parent_unchanged"])
    ok(result["inputs"]["guard_job"] == str(env.pf_job) and result["safe_input_sha256"] == S.SAFE_INPUT_SHA256)
    for name, digest in seal["files"].items():
        ok(H.sha(Path(env.a.out) / name) == digest and H.nlink(Path(env.a.out) / name) == 1)
    ok(os.stat(Path(env.a.out) / "preflight-result.json").st_mode & 0o777 == 0o444)


def test_diagnostic_background_only_is_non_qualifying(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(mhz_fails=True), reference_work=False)
    code, result, _ = X.go(env)
    ok(code == 0 and result["passed"] and result["mode"] == "diagnostic" and result["qualifying"] is False)
    ok(by_name(result)["mhz_comparison"]["gate"] is False)


@pytest.mark.parametrize("percent,band", [(0.1, "proceed"), (0.5, "coordinator-decision"), (0.8, "stop")])
def test_04_bus_bands(tmp_path, monkeypatch, percent, band):
    env = X.build(tmp_path, monkeypatch, host="127x04", fake=dict(bus_percent=percent))
    code, result, _ = X.go(env)
    ok(result["bus_band"] == band and result["bus_gate"] == band, result["summaries"]["bus"]["cumulative_loaded"])
    ok(result["mode"] == "binding" and code == 0)


def test_band_edges():
    ok(S.band(None) == "unavailable" and S.band(0.3) == "proceed" and S.band(0.31) == "coordinator-decision")
    ok(S.band(0.69) == "coordinator-decision" and S.band(0.7) == "stop")


def test_short_measured_hold_is_not_binding(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    monkeypatch.setattr(S, "MIN_LOADED_SECONDS", {"127x03": 30, "127x04": 30})
    code, result, _ = X.go(env)
    ok(code == 0 and result["passed"] and result["mode"] == "diagnostic" and result["qualifying"] is False)


def test_04_login_during_hold_fails(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, host="127x04", fake=dict(login_during_hold=True))
    code, result, seal = X.go(env)
    ok(code == 1 and seal["status"] == "failed" and result["summaries"]["sshd"]["login_detected_during_hold"])


@pytest.mark.parametrize("fake,check", [(dict(reason_at_admit="op1_interference"), "guard_admission"),
                                        (dict(background_fails=True), "background_ready"),
                                        (dict(mhz_fails=True), "mhz_comparison")])
def test_failures_are_sealed_failed(tmp_path, monkeypatch, fake, check):
    env = X.build(tmp_path, monkeypatch, fake=fake)
    code, result, seal = X.go(env)
    ok(code == 1 and seal["status"] == "failed" and by_name(result)[check]["passed"] is False)
    ok(by_name(result)["cleanup"]["passed"] is True and result["qualifying"] is False)


def test_cleanup_failure_never_masks_primary(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(mhz_fails=True, close_fails=True))
    code, result, _ = X.go(env)
    rows = by_name(result)
    ok(code == 1 and rows["mhz_comparison"]["passed"] is False and rows["cleanup"]["passed"] is False)
    ok("MHz" in result["error"])


def test_registry_write_during_preflight_fails(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, fake=dict(claim_in_backend=True))
    env.F.ER.backend = lambda a: fake_frozen.Backend(dict(claim_in_backend=True), a.repository)
    code, result, _ = X.go(env)
    ok(code == 1 and result["registry_and_attempt_parent_unchanged"] is False)


def test_non_empty_attempt_parent_fails(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    (Path(env.a.attempt_parent) / "end-127x03-r00-l00").mkdir()
    code, result, _ = X.go(env)
    ok(code == 1 and result["attempt_parent_empty"] is False)


def test_guard_job_not_fresh_fails(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    H.write(env.pf_job / "STOP", "")
    code, result, _ = X.go(env)
    ok(code == 1 and by_name(result)["guard_job_fresh"]["passed"] is False)


def test_hard_linked_guard_side_file_is_not_copied(tmp_path, monkeypatch):
    """A guard side file that is a hard link to an outcome canary is refused by the descriptor gate (never read);
    the run fails because its guard sources could not be copied."""
    env = X.build(tmp_path, monkeypatch)
    canary = H.canary(tmp_path / "outcome-canary")
    original = fake_frozen.Backend.k4s_work

    def work(self, row, **kw):
        target = env.pf_job / "allowlist-occurrences.jsonl"
        if not target.exists():
            os.link(canary, target)
        return original(self, row, **kw)
    monkeypatch.setattr(fake_frozen.Backend, "k4s_work", work)
    code, result, seal = X.go(env)
    ok(code == 1 and result["guard_sources"] is None and "nlink" in result["guard_sources_error"])
    ok(not any(name.startswith("guard-sources/") for name in seal["files"]) and H.canary_intact(canary))


def test_loaded_runtime_modules_must_be_closure_or_pinned(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch)
    import types
    closure_rel = S.STUDY_REL + "/end_pool.py"
    extra_rel = "src/clasher/extra_module.py"
    extra = H.write(env.runtime / extra_rel, "x = 1\n")
    fake_a, fake_b = types.ModuleType("k4s_fake_a"), types.ModuleType("k4s_fake_b")
    fake_a.__file__ = str(env.runtime / closure_rel)
    fake_b.__file__ = str(extra)
    monkeypatch.setitem(sys.modules, "k4s_fake_a", fake_a)
    ok(S.closure_only(env.runtime) == [closure_rel])
    policy = env.si.Policy(env.host, [env.si.Role("x", str(env.runtime), "read", 1, exact=("x",))])
    ok(S.loaded_modules_check(env.si, policy, env.host, str(env.runtime), {})["outside_closure"] == [])
    monkeypatch.setitem(sys.modules, "k4s_fake_b", fake_b)
    raises(S.PreflightRefusal, S.closure_only, env.runtime, match="non-closure")
    raises(S.PreflightRefusal, S.loaded_modules_check, env.si, policy, env.host, str(env.runtime), {},
           match="outside the closure")
    got = S.loaded_modules_check(env.si, policy, env.host, str(env.runtime), {extra_rel: H.sha(extra)})
    ok(got["outside_closure"] == [extra_rel])
    refused(env.si, "sha", S.loaded_modules_check, env.si, policy, env.host, str(env.runtime), {extra_rel: "0" * 64})


def test_never_references_claim_or_measure():
    tree = ast.parse(Path(S.__file__).read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
            {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    ok(not names & {"producer_claim", "pool_context", "K4SStore", "measure", "run_attempt", "claim_attempt"})


# ---------------------------------------------------------------- 05: verify-received through safe_input

def received(tmp_path, monkeypatch, env, exit_code=0):
    """The wrapper's push of one preflight into <RECEIVE_BASE>/<host>/<attempt> (synthetic transfer)."""
    recv_base = tmp_path / "preflight-received"
    monkeypatch.setattr(S, "RECEIVE_BASE", str(recv_base))
    attempt = os.path.basename(env.a.out)
    root = recv_base / env.host / attempt
    shutil.copytree(env.a.out, root / "preflight")
    H.write(root / "exit.json", json.dumps(dict(utc="2026-10-12T22:00:00Z", host=env.host, attempt=attempt,
                                                exit_code=exit_code, command_exited=True, measurement_exists=True)))
    H.write(root / "TRANSFER-DONE.json", json.dumps(dict(utc="2026-10-12T22:00:05Z", host=env.host, attempt=attempt,
                                                         transfer_complete=True, measurement_exit_code=exit_code,
                                                         measurement_exists=True)))
    for name in ("argv.nul", "detach.json", "detach.log"):
        H.write(root / name, b"x")
    monkeypatch.setattr(os, "uname", H.fake_uname("127x05"))
    return root


def test_verify_received_happy_and_exclusive(tmp_path, monkeypatch):
    env = X.build(tmp_path, monkeypatch, host="127x04")
    code, result, _ = X.go(env)
    root = received(tmp_path, monkeypatch, env, code)
    summary, _ = S.verify_received(env.si, str(root))
    ok(summary["schema"] == S.VERIFIED_SCHEMA and summary["passed"] and summary["mode"] == "binding")
    ok(summary["qualifying"] and summary["bus_band"] == "proceed" and summary["bus_gate"] == "proceed")
    ok(summary["receipt_manifest_sha256"] == H.sha(root / "preflight/receipt-manifest.json"))
    ok(summary["preflight_result_sha256"] == H.sha(root / "preflight/preflight-result.json"))
    ok(summary["inputs"]["bundle_pins_sha256"] == env.a.bundle_pins_sha256 and summary["failed_checks"] == [])
    if sys.flags.optimize:                                    # verify-received refuses -O (explicit raise)
        raises(S.PreflightRefusal, S.main, ["verify-received", "--receive", str(root)], layers=(env.si, env.tool),
               match="-O")
        return
    rc = S.main(["verify-received", "--receive", str(root)], layers=(env.si, env.tool))
    ok(rc == 0 and json.loads((root / "PREFLIGHT-VERIFIED.json").read_text())["passed"])
    refused(env.si, "exists", S.main, ["verify-received", "--receive", str(root)], layers=(env.si, env.tool))


@pytest.mark.parametrize("mutation", ["extra-file", "hard-link", "symlink", "push-failed", "outcome-name",
                                      "seal-sha", "member-content", "exit-mismatch", "wrong-namespace",
                                      "transfer-marker"])
def test_verify_received_refusals(tmp_path, monkeypatch, mutation):
    env = X.build(tmp_path, monkeypatch)
    code, _, _ = X.go(env)
    root = received(tmp_path, monkeypatch, env, code)
    data = root / "preflight"
    if mutation == "extra-file":
        H.write(data / "extra.txt", b"x")
    elif mutation == "hard-link":
        os.link(data / "capacity.jsonl", tmp_path / "alias")
    elif mutation == "symlink":
        os.unlink(data / "capacity.jsonl")
        os.symlink(tmp_path / "x", data / "capacity.jsonl")
    elif mutation == "push-failed":
        H.write(root / "PUSH-FAILED.json", b"{}")
    elif mutation == "outcome-name":
        H.write(data / "games" / "reviewer.json", b"{}")
    elif mutation == "member-content":
        os.chmod(data / "capacity.jsonl", 0o644)
        with open(data / "capacity.jsonl", "a") as stream:
            stream.write("{}\n")
    elif mutation == "seal-sha":
        os.chmod(data / "receipt-manifest.sha256", 0o644)
        H.write(data / "receipt-manifest.sha256", "0" * 64 + "  receipt-manifest.json\n")
    elif mutation == "exit-mismatch":
        os.unlink(root / "exit.json")
        H.write(root / "exit.json", json.dumps(dict(utc="2026-10-12T22:00:00Z", host=env.host,
                                                    attempt=root.name, exit_code=1, command_exited=True,
                                                    measurement_exists=True)))
        os.unlink(root / "TRANSFER-DONE.json")
        H.write(root / "TRANSFER-DONE.json", json.dumps(dict(utc="x", host=env.host, attempt=root.name,
                                                             transfer_complete=True, measurement_exit_code=1,
                                                             measurement_exists=True)))
    elif mutation == "wrong-namespace":
        root = Path(str(root).replace("preflight-received", "preflight-received2"))
    elif mutation == "transfer-marker":
        os.unlink(root / "TRANSFER-DONE.json")
    raises((env.si.Refusal, S.PreflightRefusal), S.verify_received, env.si, str(root))
