"""S5 preflight (k4s_end_preflight.py): check logic with fakes. The frozen modules are faked (fake_frozen.py); the
guard monitor is a real spawned process speaking the real checkpoint protocol. What this CANNOT cover offline:
the frozen modules themselves, the T1 guard on a real host, torch/native loading, real bus/MHz/sshd numbers."""
import ast
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import fake_frozen
import k4s_end_preflight as S
from helpers import ROOT, sha


def runtime_tree(runtime):
    """A runtime with the six END sources and a K4S manifest pinning them; returns the manifest SHA."""
    end_files, k4s_files = {}, {}
    for rel in S.END_SOURCES:
        path = runtime / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stand-in for " + rel + "\n")
        (k4s_files if "/mac/" in rel else end_files)[rel] = sha(path)
    manifest = runtime / S.MANIFEST_REL
    manifest.write_text(json.dumps(dict(schema="clasher.k4s.mac-manifest.v1", end_files=end_files,
                                        k4s_files=k4s_files)))
    return sha(manifest)


def git_commits(repo, n=2):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    out = []
    for i in range(n):
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", str(i)], check=True, env=env)
        out.append(subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                                  check=True).stdout.strip())
    return tuple(out)


def args(tmp, **over):
    a = SimpleNamespace(bundle=tmp / "bundle", runtime_root=tmp / "runtime", native=tmp / "native.so",
                        corpus=tmp / "K4.pkl", corpus_inventory=tmp / "corpora.json", end_evidence=tmp / "ev.json",
                        repository=tmp / "repository", attempt_parent=tmp / "attempts", out=tmp / "pre" / "out",
                        k4s_manifest_sha256="m" * 64, sd1_manifest_sha256="s" * 64, end_evidence_sha256="e" * 64,
                        compare_bundle=None, end_job_sha256=None, hold_seconds=1.0, block_seconds=0.3,
                        min_samples=3, reference_work=True)
    for p in (a.bundle, a.runtime_root, a.repository, a.attempt_parent, tmp / "pre"):
        p.mkdir(parents=True, exist_ok=True)
    a.native.write_bytes(b"native")
    a.k4s_manifest_sha256 = runtime_tree(a.runtime_root)
    a.corpus_inventory.write_text("{}")
    (a.attempt_parent / "end-127x03-r00-l00").mkdir(exist_ok=True)
    for k, v in over.items():
        setattr(a, k, v)
    return a


@pytest.fixture
def host_os(monkeypatch):
    masks = {900001: {2, 3}, 900002: {4, 5}}
    monkeypatch.setattr(os, "sched_setaffinity", lambda pid, cpus: None)
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: masks.get(pid, {0, 1}))
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 10)
    monkeypatch.setattr(socket, "gethostname", lambda: "127x03")
    # short offline holds; the production minima are covered by test_refusals
    monkeypatch.setattr(S, "MIN_HOLD_SECONDS", {"127x03": 0, "127x04": 0})
    monkeypatch.setattr(S, "MIN_SAMPLES", 3)
    monkeypatch.setattr(S, "BLOCK_SECONDS_RANGE", (0.1, 300))
    monkeypatch.setattr(S, "SEED_COMMITS", S.SEED_COMMITS)          # restored after stage() replaces it
    fake_frozen.CALLS.clear()


HOSTINFO = dict(host="127x03", nice=10, sched_other=True, optimized=False)


def stage(a, F, guard_job):
    """Bundle manifest (for the pre-import guard-repo read) and a guard job repo/ git clone with the seed commits."""
    (a.bundle / "tiers-pins.json").write_text(json.dumps(F.manifest))
    if not (guard_job / "repo" / ".git").exists():
        S.SEED_COMMITS = git_commits(guard_job / "repo")


def go(tmp, fake=None, host="127x03", **over):
    a = args(tmp, **over)
    F, guard_job = fake_frozen.make(tmp, fake, host=host)
    stage(a, F, guard_job)
    code = S.run(a, frozen_factory=lambda runtime: F, hostinfo=dict(HOSTINFO, host=host))
    result = json.loads((a.out / "preflight-result.json").read_text())
    seal = json.loads((a.out / "receipt-manifest.json").read_text())
    return code, result, seal, a, F, guard_job


def by_name(result):
    return {c["name"]: c for c in result["checks"]}


# ---------------------------------------------------------------- pure checks

@pytest.mark.parametrize("info,hold,samples,block,needle", [
    (dict(host="127x05"), 60, 60, 30, "127x03/127x04"),
    (dict(nice=0), 60, 60, 30, "nice 10"),
    (dict(sched_other=False), 60, 60, 30, "SCHED_OTHER"),
    (dict(optimized=True), 60, 60, 30, "optimized"),
    (dict(host="127x04"), 899, 60, 30, "RC-2 minimum"),
    (dict(), 59, 60, 30, "RC-2 minimum"),
    (dict(), 60, 59, 30, "60 guard samples"),
    (dict(), 60, 60, 0, "block seconds"),
])
def test_refusals(info, hold, samples, block, needle):
    h = dict(HOSTINFO, **info)
    reasons = S.refusals(h["host"], h["nice"], h["sched_other"], h["optimized"], hold, samples, block)
    assert any(needle in r for r in reasons), reasons
    assert S.refusals("127x04", 10, True, False, 900, 60, 30) == []


def test_run_refuses_before_writing(tmp_path):
    a = args(tmp_path)
    with pytest.raises(S.PreflightRefusal):
        S.run(a, frozen_factory=lambda r: pytest.fail("imported"), hostinfo=dict(HOSTINFO, nice=19))
    assert not a.out.exists()


@pytest.mark.parametrize("where", ["attempt_parent", "repository", "runtime_root", "bundle"])
def test_output_isolation(tmp_path, where):
    a = args(tmp_path)
    root = getattr(a, where)
    with pytest.raises(S.PreflightRefusal, match="overlaps"):
        S.isolated(root / "pre", [a.attempt_parent, a.repository, a.runtime_root, a.bundle])
    with pytest.raises(S.PreflightRefusal, match="overlaps"):
        S.isolated(root / "pre", [root / "pre" / "deeper"])     # output above a forbidden root
    with pytest.raises(S.PreflightRefusal, match="exists"):
        S.isolated(tmp_path / "pre", [])


def test_bundle_parity():
    m = dict(files={"a": "1"}, reference_load_profile=dict(host="127x03", guard=dict(job="/g/pre", freeze="F")))
    other = json.loads(json.dumps(m)); other["reference_load_profile"]["guard"]["job"] = "/g/attempt"
    assert S.bundle_parity(m, other)["identical_except_guard_job"] is True
    with pytest.raises(S.PreflightRefusal, match="own guard job"):
        S.bundle_parity(m, m)
    other["files"]["a"] = "2"
    with pytest.raises(S.PreflightRefusal, match="beyond guard.job"):
        S.bundle_parity(m, other)


def test_fresh_guard_job(tmp_path):
    with pytest.raises(S.PreflightRefusal, match="missing"):
        S.fresh_guard_job(tmp_path / "nope", "127x03")
    assert S.fresh_guard_job(tmp_path, "127x03")["fresh"] is True
    for name in S.GUARD_SIDE_FILES + ("STOP", "STOP-127x03"):
        (tmp_path / name).write_text("")
        with pytest.raises(S.PreflightRefusal, match="not fresh"):
            S.fresh_guard_job(tmp_path, "127x03")
        (tmp_path / name).unlink()


def test_window_max_uses_frozen_integer_rule():
    hz = 100
    series = [(float(t), t, "p") for t in range(0, 11)]          # 1 tick/s = exactly 1% of a core
    w = S.window_max(series, hz, 1)
    assert w["windows"] == 10 and abs(w["max_percent"] - 1.0) < 1e-12 and w["flagged_over_1_percent"] == 0
    series[5] = (5.0, 6, "p")                                     # a 2-tick second
    assert S.window_max(series, hz, 1)["flagged_over_1_percent"] == 1
    assert S.window_max(series, hz, 30)["windows"] == 0


def test_bus_summary_and_band():
    rows = [dict(timestamp=float(t), phase="reference-warmup" if t < 5 else S.HOLD_PHASE,
                 reporting_guard=dict(system_bus=dict(cpu_ticks=t // 10, core_fraction=0.001))) for t in range(100)]
    out = S.bus_summary(rows, 100)
    assert out["loaded_samples"] == 95 and out["cumulative_loaded"]["cpu_ticks"] == 9
    assert abs(out["cumulative_loaded"]["percent"] - 9 / 94) < 1e-12
    assert out["loaded_band"].startswith("proceed")
    assert S.band(0.5).startswith("between") and S.band(0.7).startswith("coordinator") and S.band(None) == "unavailable"


def test_sshd_and_mhz_summaries():
    rows = [dict(phase=S.HOLD_PHASE, processes=[dict(name="sshd")] * n,
                 cpu_clock_mhz_by_processor={"0": 3000.0, "1": 3100.0}) for n in (1, 1, 2, 1)]
    assert S.sshd_summary(rows)["login_detected_during_hold"] is True
    assert S.sshd_summary(rows[:2])["login_detected_during_hold"] is False
    m = S.mhz_summary(rows, [0, 1])
    assert m["occupied_mean_mhz"]["mean"] == 3050.0 and m["per_core"]["1"]["max"] == 3100.0


def test_never_calls_claim_or_measure_statically():
    tree = ast.parse((ROOT / "k4s_end_preflight.py").read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"producer_claim", "claim_attempt", "producer_registry", "pool_context", "measure",
                        "run_attempt", "REFERENCE_SCOPE", "reference", "raw_record"}
    text = (ROOT / "k4s_end_preflight.py").read_text()
    assert 'SCOPE = "K4S-END-PREFLIGHT"' in text


# ---------------------------------------------------------------- orchestration with fakes

def test_happy_path(tmp_path, host_os):
    code, result, seal, a, F, guard_job = go(tmp_path)
    assert code == 0 and result["passed"] is True and seal["status"] == "passed" and seal["scope"] == S.SCOPE
    checks = by_name(result)
    assert [c["name"] for c in result["checks"]] == [
        "guard_repo_commits", "pre_import_pins", "frozen_import", "frozen_helpers", "frozen_identity", "bundle_parity", "guard_job_fresh", "reporting_profile",
        "physical_cpus", "end_job_read_only", "backend_and_corpus", "topology", "guard_admission",
        "background_ready", "loaded_hold", "monitor_stop", "frozen_guard_validators", "mhz_comparison", "post_pins",
        "cleanup"]
    assert checks["bundle_parity"]["skipped"] and checks["end_job_read_only"]["skipped"]
    assert checks["loaded_hold"]["reference_slot_work"] > 0 and checks["loaded_hold"]["samples_after_admission"] >= 3
    assert result["claim"] is False and result["measure_called"] is False and fake_frozen.CALLS == []
    assert result["registry_and_attempt_parent_unchanged"] is True and not (a.repository / "reports").exists()
    assert result["summaries"]["samples"] >= 3 and result["summaries"]["blocks"]["completed"] >= 1
    assert result["slot_evidence"]["background_nice"] == [10, 10]
    assert set(json.loads((a.out / "receipt-manifest.json").read_text())["files"]) >= {
        "capacity.jsonl", "guard-admission.json", "guard-blocks.jsonl", "preflight-result.json"}
    assert F.calls["end_job"] == 0


def test_end_job_and_parity_when_given(tmp_path, host_os):
    a = args(tmp_path, end_job_sha256="j" * 64, compare_bundle=tmp_path / "attempt-bundle")
    F, guard_job = fake_frozen.make(tmp_path)
    stage(a, F, guard_job)
    attempt = json.loads(json.dumps(F.manifest))
    attempt["reference_load_profile"]["guard"]["job"] = str(tmp_path / "guard-job-attempt-l00")
    a.compare_bundle.mkdir()
    (a.compare_bundle / "tiers-pins.json").write_text(json.dumps(attempt))
    assert S.run(a, frozen_factory=lambda r: F, hostinfo=HOSTINFO) == 0
    checks = by_name(json.loads((a.out / "preflight-result.json").read_text()))
    assert checks["end_job_read_only"]["passed"] is True and F.calls["end_job"] == 1
    assert checks["bundle_parity"]["identical_except_guard_job"] is True
    attempt["files"] = {"x": "1"}
    (a.compare_bundle / "tiers-pins.json").write_text(json.dumps(attempt))
    b = args(tmp_path, out=tmp_path / "pre" / "out2", compare_bundle=a.compare_bundle)
    stage(b, F, guard_job)
    assert S.run(b, frozen_factory=lambda r: F, hostinfo=HOSTINFO) == 1


def test_idle_hold_without_reference_work(tmp_path, host_os):
    code, result, *_ = go(tmp_path, reference_work=False, hold_seconds=0.8, block_seconds=0.3)
    assert code == 0 and by_name(result)["loaded_hold"]["reference_slot_work"] == 0
    assert by_name(result)["mhz_comparison"]["gate"] is False


def test_admission_refusal_fails_closed(tmp_path, host_os):
    code, result, seal, *_ = go(tmp_path, fake=dict(reason_at_admit="foreign_compute"))
    assert code == 1 and result["passed"] is False and seal["status"] == "failed"
    checks = by_name(result)
    assert checks["guard_admission"]["passed"] is False and "foreign_compute" in checks["guard_admission"]["error"]
    assert "background_ready" not in checks


def test_block_refusal_fails_hold(tmp_path, host_os):
    code, result, *_ = go(tmp_path, fake=dict(reason_at_end="op1_interference"))
    assert code == 1 and by_name(result)["loaded_hold"]["passed"] is False
    assert "op1_interference" in result["summaries"]["guard_reasons"]


def test_background_failure(tmp_path, host_os):
    code, result, *_ = go(tmp_path, fake=dict(background_fails=True))
    assert code == 1 and by_name(result)["background_ready"]["passed"] is False


def test_slot_priority_readback(tmp_path, host_os, monkeypatch):
    monkeypatch.setattr(os, "getpriority", lambda which, pid: 19 if pid else 10)
    code, result, *_ = go(tmp_path)
    assert code == 1 and "priority" in by_name(result)["background_ready"]["error"]


def test_mhz_gate_only_with_reference_work(tmp_path, host_os):
    code, result, *_ = go(tmp_path, fake=dict(mhz_fails=True))
    assert code == 1 and by_name(result)["mhz_comparison"]["passed"] is False
    code, result, *_ = go(tmp_path / "b", fake=dict(mhz_fails=True), reference_work=False, hold_seconds=0.6)
    assert code == 0 and by_name(result)["mhz_comparison"]["passes"] is False


def test_registry_write_fails_preflight(tmp_path, host_os):
    code, result, *_ = go(tmp_path, fake=dict(claim_in_backend=True))
    assert code == 1 and result["registry_and_attempt_parent_unchanged"] is False


def test_04_login_during_hold_fails(tmp_path, host_os, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "127x04")
    code, result, *_ = go(tmp_path, fake=dict(login_during_hold=True), host="127x04", hold_seconds=1.0)
    assert result["summaries"]["sshd"]["login_detected_during_hold"] is True
    assert all(c["passed"] or c.get("skipped") for c in result["checks"]) and code == 1


def test_guard_job_not_fresh(tmp_path, host_os):
    a = args(tmp_path)
    F, guard_job = fake_frozen.make(tmp_path)
    stage(a, F, guard_job)
    (guard_job / "op2-confirmations.jsonl").write_text("")
    assert S.run(a, frozen_factory=lambda r: F, hostinfo=HOSTINFO) == 1
    assert by_name(json.loads((a.out / "preflight-result.json").read_text()))["guard_job_fresh"]["passed"] is False


# ---------------------------------------------------------------- 05: verify-received

def received(tmp_path, host_os):
    code, result, seal, a, F, guard_job = go(tmp_path / "h")
    root = tmp_path / "recv" / "127x03" / "preflight-127x03-l00"
    root.mkdir(parents=True)
    shutil.copytree(a.out, root / "preflight")
    for name, value in (("argv.nul", "x"), ("detach.json", "{}"), ("detach.log", "")):
        (root / name).write_text(value)
    listing = dict(registry_listing_before="absent", registry_listing_after="absent",
                   attempts_listing_before="abc", attempts_listing_after="abc")
    (root / "exit.json").write_text(json.dumps(dict(host="127x03", attempt=root.name, exit_code=code,
                                                    measurement_exists=True, **listing)))
    (root / "TRANSFER-COMPLETE.json").write_text(json.dumps(dict(
        host="127x03", attempt=root.name, transfer_complete=True, measurement_exit_code=code)))
    return root


def test_verify_received(tmp_path, host_os, monkeypatch):
    monkeypatch.setattr(S, "RECEIVE_BASE", tmp_path / "recv")
    root = received(tmp_path, host_os)
    out = S.verify_received(root)
    assert out["passed"] is True and out["status"] == "passed" and out["failed_checks"] == []
    exit_ = json.loads((root / "exit.json").read_text())
    (root / "exit.json").write_text(json.dumps(dict(exit_, registry_listing_after="changed")))
    with pytest.raises(S.PreflightRefusal, match="Registry root changed"):
        S.verify_received(root)
    (root / "exit.json").write_text(json.dumps(exit_))
    (root / "preflight" / "capacity.jsonl").write_text("tampered\n")
    with pytest.raises(S.PreflightRefusal, match="SHA mismatch"):
        S.verify_received(root)


def test_verify_received_refusals(tmp_path, host_os, monkeypatch):
    monkeypatch.setattr(S, "RECEIVE_BASE", tmp_path / "recv")
    root = received(tmp_path, host_os)
    (root / "PUSH-FAILED.json").write_text("{}")
    with pytest.raises(S.PreflightRefusal, match="PUSH-FAILED"):
        S.verify_received(root)
    (root / "PUSH-FAILED.json").unlink()
    (root / "preflight" / "extra").write_text("")
    with pytest.raises(S.PreflightRefusal, match="Extra"):
        S.verify_received(root)
    with pytest.raises(S.PreflightRefusal, match="namespace"):
        S.verify_received(tmp_path / "recv" / "127x05" / "x")


def test_cli_parser_has_no_abbreviations():
    p = S.parser()
    with pytest.raises(SystemExit):
        p.parse_args(["run", "--ou", "x"])
    a = p.parse_args(["run", "--bundle", "b", "--runtime-root", "r", "--native", "n", "--corpus", "c",
                      "--corpus-inventory", "ci", "--end-evidence", "e", "--repository", "r2", "--attempt-parent",
                      "ap", "--out", "o", "--k4s-manifest-sha256", "1", "--sd1-manifest-sha256", "2",
                      "--end-evidence-sha256", "3", "--hold-seconds", "960", "--no-reference-work"])
    assert a.reference_work is False and a.block_seconds == 30.0 and a.min_samples == 60


def test_cleanup_failure_alone_fails(tmp_path, host_os):
    code, result, seal, *_ = go(tmp_path, fake=dict(close_fails=True))
    checks = by_name(result)
    assert code == 1 and seal["status"] == "failed" and checks["cleanup"]["passed"] is False
    assert all(c["passed"] or c.get("skipped") for c in result["checks"] if c["name"] != "cleanup")


def test_cleanup_failure_never_masks_primary(tmp_path, host_os):
    code, result, *_ = go(tmp_path, fake=dict(close_fails=True, reason_at_admit="console_user"))
    checks = by_name(result)
    assert code == 1 and "console_user" in checks["guard_admission"]["error"]
    assert checks["cleanup"]["passed"] is False and "backend close failed" in checks["cleanup"]["error"]


def test_read_lines_skips_unterminated_tail(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"a": 1}\n{"a": 2}\n{"a": ')
    assert S.read_lines(p) == [{"a": 1}, {"a": 2}]


def test_pre_import_pin_mismatch_never_imports(tmp_path, host_os):
    a = args(tmp_path)
    F, guard_job = fake_frozen.make(tmp_path)
    stage(a, F, guard_job)
    (a.runtime_root / S.END_SOURCES[1]).write_text("# tampered\n")
    imported = []
    assert S.run(a, frozen_factory=lambda r: imported.append(r) or F, hostinfo=HOSTINFO) == 1
    result = json.loads((a.out / "preflight-result.json").read_text())
    assert imported == [] and by_name(result)["pre_import_pins"]["passed"] is False
    assert "end_pool.py" in by_name(result)["pre_import_pins"]["error"]
    assert json.loads((a.out / "receipt-manifest.json").read_text())["status"] == "failed"


def test_pre_import_manifest_sha_mismatch(tmp_path):
    a = args(tmp_path)
    with pytest.raises(S.PreflightRefusal, match="manifest SHA"):
        S.bootstrap(a.runtime_root, "0" * 64)
    assert S.bootstrap(a.runtime_root, a.k4s_manifest_sha256)["sources"].keys() == set(S.END_SOURCES)
    (a.runtime_root / S.END_SOURCES[0]).unlink()
    (a.runtime_root / S.END_SOURCES[0]).symlink_to(a.runtime_root / S.END_SOURCES[1])
    with pytest.raises(S.PreflightRefusal, match="linked"):
        S.bootstrap(a.runtime_root, a.k4s_manifest_sha256)


def test_guard_repo_commits(tmp_path, host_os):
    a = args(tmp_path)
    F, guard_job = fake_frozen.make(tmp_path)
    (a.bundle / "tiers-pins.json").write_text(json.dumps(F.manifest))
    with pytest.raises(S.PreflightRefusal, match="not a git checkout"):
        S.guard_repo_commits(a.bundle, ("0" * 40,))
    commits = git_commits(guard_job / "repo")
    assert S.guard_repo_commits(a.bundle, commits)["commits"] == {c: True for c in commits}
    with pytest.raises(S.PreflightRefusal, match="lacks a frozen seed commit"):
        S.guard_repo_commits(a.bundle, commits + ("1" * 40,))
    S.SEED_COMMITS = commits + ("2" * 40,)
    assert S.run(a, frozen_factory=lambda r: pytest.fail("imported"), hostinfo=HOSTINFO) == 1
    result = json.loads((a.out / "preflight-result.json").read_text())
    assert by_name(result)["guard_repo_commits"]["passed"] is False and "frozen_import" not in by_name(result)
