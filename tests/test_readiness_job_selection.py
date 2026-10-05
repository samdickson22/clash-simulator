"""Operational batches of a sealed readiness plan; no native process is contacted."""

import importlib.util
import json
import sys
import types
from itertools import combinations
from pathlib import Path

import pytest
from test_readiness_execution import plan

from clasher.rl.readiness_execution import jobs
from clasher.rl.readiness_job_selection import branch_key, select_job_indices


def coverage_plan(tmp_path):
    return plan(tmp_path, purpose="development_coverage", repetitions=1)


def test_filters_partition_the_full_sealed_matrix_disjointly(tmp_path):
    p = coverage_plan(tmp_path)
    declared = jobs(p)
    assert len(declared) == 32
    everything = set(range(len(declared)))
    for engine in ("both", "scalar", "reference"):
        eligible = {i for i, j in enumerate(declared) if engine in ("both", j.engine)}
        for count in range(1, 6):
            shards = [
                select_job_indices(p, engine=engine, shard_index=i, shard_count=count)
                for i in range(count)
            ]
            assert all(s.full_job_count == len(declared) for s in shards)
            for a, b in combinations(shards, 2):
                assert not set(a.selected_indices) & set(b.selected_indices)
            assert set().union(*(s.selected_indices for s in shards)) == eligible
    split = [
        set(select_job_indices(p, engine=e).selected_indices)
        for e in ("scalar", "reference")
    ]
    assert not split[0] & split[1] and split[0] | split[1] == everything


@pytest.mark.parametrize(
    "kwargs",
    [
        {"shard_index": 2, "shard_count": 2},
        {"shard_index": -1, "shard_count": 2},
        {"shard_count": 0},
        {"shard_count": True},
        {"engine": "native"},
        {"explicit_indices": (1, 1)},
        {"explicit_indices": (32,)},
        {"explicit_indices": (-1,)},
        {"explicit_indices": (True,)},
        {"explicit_indices": (0,), "shard_count": 2},
    ],
)
def test_invalid_selection_coordinates_are_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError):
        select_job_indices(coverage_plan(tmp_path), **kwargs)


def test_explicit_indices_must_agree_with_engine(tmp_path):
    p = coverage_plan(tmp_path)
    reference = next(i for i, j in enumerate(jobs(p)) if j.engine == "reference")
    with pytest.raises(ValueError, match="engine filter"):
        select_job_indices(p, engine="scalar", explicit_indices=(reference,))
    chosen = select_job_indices(p, explicit_indices=(5, reference))
    assert chosen.selected_indices == tuple(sorted({5, reference}))


def test_unclaimed_selection_skips_claims_without_shrinking_the_plan(tmp_path):
    p = coverage_plan(tmp_path)
    declared = jobs(p)
    claimed = frozenset(branch_key(declared[i]) for i in (0, 3, 4))
    with pytest.raises(ValueError, match="prospective ownership ledger"):
        select_job_indices(p, claimed_keys=claimed)
    # Model copies skip validation; only the purpose gate is exercised here.
    fresh = p.model_copy(update={"purpose": "fresh_acceptance"})
    chosen = select_job_indices(fresh, claimed_keys=claimed)
    assert chosen.full_job_count == len(declared) and chosen.unclaimed_only
    assert chosen.skipped_claimed_indices == (0, 3, 4)
    assert set(chosen.selected_indices) == set(range(len(declared))) - {0, 3, 4}
    # Claimed failures are skipped, never retried, even when explicitly listed.
    listed = select_job_indices(fresh, explicit_indices=(3, 5), claimed_keys=claimed)
    assert listed.selected_indices == (5,) and listed.skipped_claimed_indices == (3,)


def load_runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    spec = importlib.util.spec_from_file_location(
        "readiness_selection_runner_test", Path("scripts/run_readiness_v2.py")
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    return runner


def run_args(tmp_path, plan_path, **updates):
    values = {
        "plan": plan_path,
        "output": tmp_path / "run",
        "adb": None,
        "serial": "emulator-test",
        "port": 1,
        "native_lock": tmp_path / "native.lock",
        "max_wall_seconds": 60,
        "ownership_ledger": None,
        "attempt_id": None,
        "calibration_receipt": None,
        "engine": "both",
        "shard_index": 0,
        "shard_count": 1,
        "job_index": [],
        "unclaimed_only": False,
    }
    values.update(updates)
    return types.SimpleNamespace(**values)


def test_runner_batches_record_subset_and_never_claim_full_completion(
    tmp_path, monkeypatch
):
    runner = load_runner(monkeypatch)
    p = coverage_plan(tmp_path)
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(p.model_dump_json())
    executed = []

    def fake_job(plan, job, output, args):
        assert job.engine == "scalar"
        executed.append(output.name)
        return {"public_contract_valid": False, "public_calibration_established": False}

    monkeypatch.setattr(runner, "execute_job", fake_job)
    with pytest.raises(ValueError, match="adb"):
        runner.execute(run_args(tmp_path, plan_path, engine="reference"))
    assert not (tmp_path / "run").exists()
    with pytest.raises(ValueError, match="unclaimed-only"):
        runner.execute(run_args(tmp_path, plan_path, unclaimed_only=True))
    # A scalar-only batch of a native-bearing plan needs no device path.
    runner.execute(run_args(tmp_path, plan_path, engine="scalar"))
    run = tmp_path / "run"
    complete = json.loads((run / "complete.json").read_text())
    selection = json.loads((run / "job-selection.json").read_text())
    assert complete["full_job_count"] == len(jobs(p)) == 32
    assert complete["jobs"] == len(executed) == 16
    assert complete["status"] == "completed_development_batch"
    assert selection["selected_indices"] == complete["selected_indices"]
    assert json.loads((run / "execution-plan.json").read_text()) == json.loads(
        p.model_dump_json()
    )
    assert executed == [f"job-{i:05d}" for i in complete["selected_indices"]]


def test_job_failure_is_recorded_and_runner_continues(tmp_path, monkeypatch):
    from clasher.rl.native_public_observation import NativePublicProjectionError

    runner = load_runner(monkeypatch)
    p = coverage_plan(tmp_path)
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(p.model_dump_json())
    executed = []

    def fake_job(plan, job, output, args):
        executed.append(output.name)
        if len(executed) == 2:
            raise NativePublicProjectionError("out-of-arena body")
        return {"public_contract_valid": False, "public_calibration_established": False}

    monkeypatch.setattr(runner, "execute_job", fake_job)
    assert runner.execute(run_args(tmp_path, plan_path, engine="scalar")) == 1
    run = tmp_path / "run"
    complete = json.loads((run / "complete.json").read_text())
    # Every selected job ran exactly once; the failed one was not retried.
    assert executed == [f"job-{i:05d}" for i in complete["selected_indices"]]
    assert len(executed) == len(set(executed)) == 16
    failed = run / executed[1]
    failure = json.loads((failed / "failure.json").read_text())
    assert failure["type"] == "NativePublicProjectionError"
    assert failure["run_invalidating"] is False
    assert (failed / "claim.json").exists() and not (failed / "result.json").exists()
    for name in executed[:1] + executed[2:]:
        assert (run / name / "result.json").exists()
        assert not (run / name / "failure.json").exists()
    assert complete["status"] == "completed_development_batch_with_failed_jobs"
    assert [(f["output"], f["type"]) for f in complete["failed_jobs"]] == [
        (executed[1], "NativePublicProjectionError")
    ]


def test_clean_runner_reports_no_failed_jobs(tmp_path, monkeypatch):
    runner = load_runner(monkeypatch)
    p = coverage_plan(tmp_path)
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(p.model_dump_json())
    monkeypatch.setattr(
        runner,
        "execute_job",
        lambda *args: {"public_contract_valid": False, "public_calibration_established": False},
    )
    assert runner.execute(run_args(tmp_path, plan_path, engine="scalar")) == 0
    complete = json.loads((tmp_path / "run" / "complete.json").read_text())
    assert complete["status"] == "completed_development_batch"
    assert complete["failed_jobs"] == []


@pytest.mark.parametrize("fault", ["pin_drift", "device", "ledger_like"])
def test_run_invalidating_errors_still_abort(tmp_path, monkeypatch, fault):
    runner = load_runner(monkeypatch)
    p = coverage_plan(tmp_path)
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(p.model_dump_json())
    executed = []

    def fake_job(plan, job, output, args):
        executed.append(output.name)
        if len(executed) == 2:
            if fault == "pin_drift":
                (tmp_path / "capture" / "initial.json").write_text('{"changed":true}')
            elif fault == "device":
                raise ConnectionRefusedError("emulator missing")
            else:
                raise runner.RunInvalidatedError("ownership ledger integrity")
        return {"public_contract_valid": False, "public_calibration_established": False}

    monkeypatch.setattr(runner, "execute_job", fake_job)
    expected = ConnectionRefusedError if fault == "device" else runner.RunInvalidatedError
    with pytest.raises(expected):
        runner.execute(run_args(tmp_path, plan_path, engine="scalar"))
    run = tmp_path / "run"
    assert len(executed) == 2
    assert not (run / "complete.json").exists()
    failure = json.loads((run / executed[1] / "failure.json").read_text())
    assert failure["run_invalidating"] is True
    if fault == "pin_drift":
        assert "source changed" in failure["message"]


def test_failed_session_attestation_invalidates_run(tmp_path, monkeypatch):
    runner = load_runner(monkeypatch)

    class Session:
        provenance = {
            "status": "failed",
            "expected_attestation_sha256": "a" * 64,
            "start_attestation_sha256": "a" * 64,
            "end_attestation_sha256": "b" * 64,
        }

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def body(plan, job, output, args, stack, sessions, native_record=None):
        sessions.append(stack.enter_context(Session()))
        raise ValueError("projection failed")

    monkeypatch.setattr(runner, "_execute_job_body", body)
    with pytest.raises(runner.RunInvalidatedError, match="attestation"):
        runner.execute_job(None, None, tmp_path, None)
    # A matching attestation leaves the same job error job-local.
    Session.provenance = {**Session.provenance, "end_attestation_sha256": "a" * 64}
    (tmp_path / "native-session.json").unlink()
    with pytest.raises(ValueError, match="projection failed") as caught:
        runner.execute_job(None, None, tmp_path, None)
    assert not runner.run_invalidating(caught.value)


def test_main_exits_nonzero_when_jobs_failed(tmp_path, monkeypatch):
    runner = load_runner(monkeypatch)
    monkeypatch.setattr(
        "sys.argv",
        ["run_readiness_v2.py", "execute", "--plan", "p", "--output", "o", "--native-lock", "l"],
    )
    monkeypatch.setattr(runner, "execute", lambda args: 1)
    with pytest.raises(SystemExit) as exited:
        runner.main()
    assert exited.value.code == 1
    monkeypatch.setattr(runner, "execute", lambda args: 0)
    runner.main()
