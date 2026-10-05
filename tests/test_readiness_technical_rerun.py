"""Pre-declared technical reruns of Tier A branch claims; tmp ledgers only."""

import gzip
import json
import os
import signal
import sqlite3
import time
import types
from pathlib import Path

import pytest
from test_readiness_capture_ownership import capture, declaration
from test_readiness_execution import plan as development_plan
from test_readiness_job_selection import load_runner, run_args
from test_training_readiness_v2 import sha

from clasher.rl import readiness_capture_ownership as ownership
from clasher.rl import readiness_transport
from clasher.rl.readiness_capture_ownership import (
    AdmissionReceipt,
    AttemptDeclaration,
    RerunBranchClaim,
    claim_branch,
    claim_technical_rerun,
    declare_attempt,
    evaluate_attempt,
    is_infrastructure_failure,
    record_branch_result,
    record_exposure,
    require_admission,
    seal_roots,
    technical_rerun_candidates,
)
from clasher.rl.readiness_execution import canonical_sha, file_sha, jobs
from clasher.rl.readiness_job_selection import branch_key
from clasher.rl.training_readiness_v2 import (
    CONDITIONS,
    ROLES,
    Branch,
    Protocol,
    Report,
)

POLICY = "once_before_result"


def sealed_attempt(tmp_path, monkeypatch, *, policy=POLICY):
    source = tmp_path / "frozen-test-producer.py"
    source.write_text("synthetic producer fixture\n")
    monkeypatch.setattr(
        ownership, "required_source_pins", lambda: {str(source): file_sha(source)}
    )
    monkeypatch.setattr(
        readiness_transport, "audit_native_transport_files", lambda *a, **k: 1
    )
    monkeypatch.setattr(
        readiness_transport, "audit_scalar_decisions", lambda *a, **k: 1
    )
    d = declaration(tmp_path, fresh=True)
    storage = Path("src/clasher/rl/native_frame_storage.py").resolve()
    pins = {str(source): file_sha(source), str(storage): file_sha(storage)}
    update = {
        "source_pins": pins,
        "pre_protocol": d.pre_protocol.model_copy(update={"source_pins": pins}),
    }
    if policy is not None:
        update["technical_rerun_policy"] = policy
    d = AttemptDeclaration.model_validate(
        {**d.model_dump(), **update, "pre_protocol": update["pre_protocol"]}
    )
    monkeypatch.setattr(
        ownership,
        "_checked_calibration",
        lambda path: types.SimpleNamespace(
            ruleset_sha256=(d.gamedata_sha256,), catalog_sha256=d.catalog_sha256
        ),
    )
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    captures = [capture(ledger, d, i, tmp_path)[1] for i in range(32)]
    protocol = Protocol.model_validate(
        {
            **d.pre_protocol.model_dump(),
            "status": "frozen",
            "families": tuple(c.selected_family for c in captures),
        }
    )
    seal_roots(ledger, attempt_id=d.attempt_id, protocol=protocol)
    return types.SimpleNamespace(
        d=d,
        ledger=ledger,
        protocol=protocol,
        tmp=tmp_path,
        calibration=next(
            Path(p) for p in d.input_pins if p.endswith("/calibration.json")
        ),
        storage=storage,
    )


def claim(
    a, output, *, family=0, condition=CONDITIONS[0], role="wait", engine="reference"
):
    return claim_branch(
        a.ledger,
        attempt_id=a.d.attempt_id,
        family_id=f"family-{family}",
        condition=condition,
        candidate_role=role,
        engine=engine,
        output_path=output,
    )


def start_output(c):
    """What the runner writes before executing a job."""
    output = Path(c.output_path)
    output.mkdir()
    (output / "ownership-claim.json").write_text(c.model_dump_json())
    job = {
        "family_id": c.family_id,
        "condition": c.condition,
        "candidate_role": c.candidate_role,
        "engine": c.engine,
    }
    (output / "claim.json").write_text(json.dumps(job))
    return output


def fail_output(c, kind, message="synthetic"):
    output = start_output(c)
    (output / "failure.json").write_text(
        json.dumps(
            {
                "type": kind,
                "message": message,
                "traceback": "",
                "run_invalidating": True,
            }
        )
    )
    return output


def complete_output(a, c):
    """Write complete synthetic branch evidence for claim ``c``; return Branch."""
    output = start_output(c)
    family = next(f for f in a.protocol.families if f.family_id == c.family_id)
    job = json.loads((output / "claim.json").read_text())
    for name in ("decisions.jsonl.gz", "transport.jsonl.gz"):
        with gzip.open(output / name, "wt") as stream:
            stream.write("{}\n")
    winner = family.root_owner if c.candidate_role == "immediate_play" else None
    towers = [{"owner": 0, "hp": 1000}, {"owner": 1, "hp": 1000}]
    terminal = (
        {
            "playable": {
                "ended": True,
                "tick": 3601,
                "objects": [dict(t, cardId=-1) for t in towers],
            },
            "final": {"finalized": True, "winner": winner},
        }
        if c.engine == "reference"
        else {"game_over": True, "winner": winner, "towers": towers}
    )
    (output / "terminal.json").write_text(json.dumps(terminal))
    result = {
        "job": job,
        "root_owner": family.root_owner,
        "score": 1.0 if c.candidate_role == "immediate_play" else 0.5,
        "own_remaining_hp": 1000.0,
        "enemy_remaining_hp": 1000.0,
        "root_sha256": family.root_sha256,
        "public_packet_sha256": family.public_packet_sha256,
        "protocol_sha256": a.protocol.sha256,
        "public_contract_valid": True,
        "public_calibration_established": True,
        "legal_transport_valid": True,
        "calibration_receipt_sha256": file_sha(a.calibration),
        "gamedata_path": str(Path("gamedata.json").resolve()),
        "gamedata_sha256": a.d.gamedata_sha256,
        "catalog_sha256": a.d.catalog_sha256,
        "native_frame_storage_sha256": file_sha(a.storage),
        "catalog_path": next(p for p in a.d.input_pins if p.endswith("/catalog.csv")),
        "capture_path": str(a.tmp / f"capture-{int(c.family_id.split('-')[-1])}"),
        "root_tick": 90,
        "native_attestation_sha256": a.d.native_attestation_sha256,
        "terminal_sha256": file_sha(output / "terminal.json"),
        "decisions_sha256": file_sha(output / "decisions.jsonl.gz"),
        "transport_sha256": file_sha(output / "transport.jsonl.gz"),
    }
    if c.engine == "reference":
        session = {"status": "verified", "session_id": "synthetic-rerun-test"}
        (output / "native-session.json").write_text(json.dumps(session))
        result["native_read_session"] = session
        result["native_session_sha256"] = file_sha(output / "native-session.json")
    (output / "result.json").write_text(json.dumps(result))
    candidate = next(x for x in family.candidates if x.role == c.candidate_role)
    branch = Branch(
        protocol_sha256=a.protocol.sha256,
        family_id=c.family_id,
        root_sha256=family.root_sha256,
        public_packet_sha256=family.public_packet_sha256,
        candidate_role=c.candidate_role,
        action_id=candidate.action_id,
        condition=c.condition,
        engine=c.engine,
        artifact_sha256=file_sha(output / "result.json"),
        score=result["score"],
        own_remaining_hp=1000.0,
        enemy_remaining_hp=1000.0,
        terminal=True,
        public_contract_valid=True,
        legal_transport_valid=True,
    )
    (output / "branch.json").write_text(branch.model_dump_json())
    return branch


def record(a, c, branch):
    output = Path(c.output_path)
    record_branch_result(
        a.ledger,
        c,
        branch,
        artifact_hashes={p.name: file_sha(p) for p in output.iterdir()},
    )


def rerun(a, original, output):
    return claim_technical_rerun(
        a.ledger,
        attempt_id=a.d.attempt_id,
        original_nonce=original.nonce,
        output_path=output,
    )


def test_eligible_failures_rerun_once_count_in_evaluation_and_admission(
    tmp_path, monkeypatch
):
    a = sealed_attempt(tmp_path, monkeypatch)
    transport_key = ("family-0", CONDITIONS[0], "immediate_play", "reference")
    killed_key = ("family-1", CONDITIONS[2], "wait", "scalar")
    originals, count = {}, 0
    for family in a.protocol.families:
        for condition in CONDITIONS:
            for role in ROLES:
                for engine in ("scalar", "reference"):
                    key = (family.family_id, condition, role, engine)
                    c = claim(
                        a,
                        tmp_path / f"branch-{count:04d}",
                        family=int(family.family_id.split("-")[1]),
                        condition=condition,
                        role=role,
                        engine=engine,
                    )
                    count += 1
                    originals[key] = c
                    if key == transport_key:
                        fail_output(
                            c, "ConnectionRefusedError", "[Errno 61] Connection refused"
                        )
                    elif key == killed_key:
                        # Hard kill: ownership claim, partial files, no failure.json.
                        output = start_output(c)
                        (output / "decisions.jsonl.gz").write_bytes(b"partial")
                    else:
                        record(a, c, complete_output(a, c))
    candidates = technical_rerun_candidates(a.ledger, attempt_id=a.d.attempt_id)
    assert set(candidates) == {transport_key, killed_key}
    assert candidates[transport_key][1:] == (
        "infrastructure_failure",
        "ConnectionRefusedError",
    )
    assert candidates[killed_key][1:] == ("runner_killed_without_outcome", None)
    original_files = {
        k: {p.name: file_sha(p) for p in Path(originals[k].output_path).iterdir()}
        for k in (transport_key, killed_key)
    }
    reruns = {}
    for key in (transport_key, killed_key):
        new_path = tmp_path / f"rerun-{key[3]}"
        r = rerun(a, originals[key], new_path)
        assert isinstance(r, RerunBranchClaim)
        assert (
            r.original_nonce == originals[key].nonce and r.nonce != originals[key].nonce
        )
        assert r.output_path == str(new_path.resolve())
        assert r.model_dump(
            exclude={"nonce", "output_path", "original_nonce"}
        ) == originals[key].model_dump(exclude={"nonce", "output_path"})
        reruns[key] = r
    # The original claim can no longer record once superseded.
    with pytest.raises(ValueError, match="superseded"):
        record_branch_result(
            a.ledger, originals[transport_key], None, artifact_hashes={}
        )
    for key, r in reruns.items():
        record(a, r, complete_output(a, r))
    # Original directories are preserved untouched.
    for key in (transport_key, killed_key):
        output = Path(originals[key].output_path)
        assert {p.name: file_sha(p) for p in output.iterdir()} == original_files[key]
    with pytest.raises(ValueError, match="already re-run once"):
        rerun(a, originals[transport_key], tmp_path / "second-rerun")
    assert technical_rerun_candidates(a.ledger, attempt_id=a.d.attempt_id) == {}
    report, receipt = evaluate_attempt(
        a.ledger,
        attempt_id=a.d.attempt_id,
        calibration_receipt_path=a.calibration,
        report_path=tmp_path / "evaluation.json",
        admission_path=tmp_path / "admission.json",
    )
    assert report.status == "passed" and receipt is not None
    assert all(f.complete for f in report.families)
    listed = {
        (s.family_id, s.condition, s.candidate_role, s.engine): s
        for s in receipt.technical_reruns
    }
    assert set(listed) == {transport_key, killed_key}
    assert listed[transport_key].reason == "infrastructure_failure"
    assert listed[transport_key].failure_type == "ConnectionRefusedError"
    assert listed[killed_key].reason == "runner_killed_without_outcome"
    assert all(s.completed and len(s.evidence_sha256) == 64 for s in listed.values())
    assert listed[transport_key].rerun_nonce == reruns[transport_key].nonce
    assert report.technical_reruns == receipt.technical_reruns
    saved = Report.model_validate_json((tmp_path / "evaluation.json").read_text())
    assert saved.technical_reruns == receipt.technical_reruns
    assert "technical_reruns" in json.loads((tmp_path / "admission.json").read_text())
    assert require_admission(a.ledger, tmp_path / "admission.json") == receipt
    # A receipt that hides a rerun is not ledger-issued.
    hidden = tmp_path / "hidden.json"
    hidden.write_text(
        receipt.model_copy(update={"technical_reruns": ()}).model_dump_json()
    )
    with pytest.raises(ValueError, match="not issued"):
        require_admission(a.ledger, hidden)
    # Mutating preserved original evidence revokes admission.
    original = Path(originals[transport_key].output_path) / "failure.json"
    saved_bytes = original.read_bytes()
    original.write_text(
        json.dumps({"type": "ConnectionRefusedError", "message": "edited"})
    )
    with pytest.raises(ValueError, match="original evidence"):
        require_admission(a.ledger, tmp_path / "admission.json")
    original.write_bytes(saved_bytes)
    assert require_admission(a.ledger, tmp_path / "admission.json") == receipt
    (Path(originals[killed_key].output_path) / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="never eligible"):
        require_admission(a.ledger, tmp_path / "admission.json")


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("NativePublicProjectionError", "out-of-arena body"),
        ("ValueError", "uncertain own hand or elixir"),
        ("RunInvalidatedError", "execution input pin drift: pinned input changed"),
        ("RunInvalidatedError", "native attestation mismatch"),
        ("TimeoutError", "declared execution wall-time budget exhausted"),
        ("OperationalError", "no such table: branch_claims"),
        (
            "FileNotFoundError",
            "[Errno 2] No such file or directory: '/tmp/capture/plan.json'",
        ),
        ("KeyError", "'hp'"),
    ],
)
def test_ineligible_failures_are_refused(tmp_path, monkeypatch, kind, message):
    a = sealed_attempt(tmp_path, monkeypatch)
    c = claim(a, tmp_path / "original")
    fail_output(c, kind, message)
    with pytest.raises(ValueError, match="not a declared infrastructure failure"):
        rerun(a, c, tmp_path / "rerun")
    assert technical_rerun_candidates(a.ledger, attempt_id=a.d.attempt_id) == {}
    assert not (tmp_path / "rerun").exists()


def test_declared_infrastructure_set():
    for kind, message in [
        ("ConnectionRefusedError", "[Errno 61] Connection refused"),
        ("ConnectionResetError", "reset"),
        ("BrokenPipeError", "[Errno 32] Broken pipe"),
        ("TimeoutError", "timed out"),
        ("NativeLinkLost", "native link not recovered within 120s"),
        (
            "RunInvalidatedError",
            "native device link lost: NativeLinkLost: native link not recovered",
        ),
        ("RunInvalidatedError", "native read session could not open: adb gone"),
        ("OperationalError", "database is locked"),
        ("RunnerTerminated", "runner terminated by SIGTERM"),
        (
            "FileNotFoundError",
            "[Errno 2] No such file or directory: 'scripts/read_native_public_levels.py'",
        ),
    ]:
        assert is_infrastructure_failure(kind, message), (kind, message)


def test_failure_after_result_and_claims_with_results_are_refused(
    tmp_path, monkeypatch
):
    a = sealed_attempt(tmp_path, monkeypatch)
    after = claim(a, tmp_path / "after-result")
    complete_output(a, after)
    (Path(after.output_path) / "failure.json").write_text(
        json.dumps({"type": "OperationalError", "message": "database is locked"})
    )
    with pytest.raises(ValueError, match="never eligible"):
        rerun(a, after, tmp_path / "rerun-after")
    recorded = claim(a, tmp_path / "recorded", condition=CONDITIONS[1])
    record(a, recorded, complete_output(a, recorded))
    # Even a transport failure.json added later cannot reopen a recorded claim.
    with pytest.raises(ValueError, match="with a result"):
        rerun(a, recorded, tmp_path / "rerun-recorded")


def test_rerun_rules_new_path_once_only_and_originals_only(tmp_path, monkeypatch):
    a = sealed_attempt(tmp_path, monkeypatch)
    c = claim(a, tmp_path / "original")
    other = claim(a, tmp_path / "other", condition=CONDITIONS[1])
    unstarted = claim(a, tmp_path / "unstarted", condition=CONDITIONS[2])
    fail_output(c, "BrokenPipeError", "[Errno 32] Broken pipe")
    # The rerun output must be a new path: not the original, not another claim.
    for path in (tmp_path / "original", tmp_path / "other", tmp_path / "unstarted"):
        with pytest.raises(ValueError, match="new"):
            rerun(a, c, path)
    # A claim whose runner never created its owned directory is not eligible.
    with pytest.raises(ValueError, match="no owned output directory"):
        rerun(a, unstarted, tmp_path / "rerun-unstarted")
    r = rerun(a, c, tmp_path / "rerun")
    assert not (tmp_path / "rerun").exists()  # the runner creates it
    with pytest.raises(ValueError, match="already re-run once"):
        rerun(a, c, tmp_path / "rerun-2")
    # A rerun claim is never itself an original claim.
    with pytest.raises(ValueError, match="original branch claim"):
        claim_technical_rerun(
            a.ledger,
            attempt_id=a.d.attempt_id,
            original_nonce=r.nonce,
            output_path=tmp_path / "rerun-of-rerun",
        )
    # A failing rerun leaves the case without any result (still missing).
    fail_output(r, "ConnectionRefusedError", "refused again")
    with pytest.raises(ValueError, match="original branch claim"):
        claim_technical_rerun(
            a.ledger,
            attempt_id=a.d.attempt_id,
            original_nonce=r.nonce,
            output_path=tmp_path / "rerun-of-failed-rerun",
        )
    with sqlite3.connect(a.ledger) as db:
        assert db.execute("SELECT count(*) FROM branch_reruns").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM branch_results").fetchone()[0] == 0
    # The superseded original cannot record, and a forged rerun is unclaimed.
    with pytest.raises(ValueError, match="superseded"):
        record_branch_result(a.ledger, c, None, artifact_hashes={})
    forged = r.model_copy(update={"output_path": str(tmp_path / "other")})
    with pytest.raises(ValueError, match="unclaimed branch result"):
        record_branch_result(a.ledger, forged, None, artifact_hashes={})
    # Hard-killed claim (ownership file, no failure/result) is eligible.
    fail_less = start_output(other)
    assert set(technical_rerun_candidates(a.ledger, attempt_id=a.d.attempt_id)) == {
        ("family-0", CONDITIONS[1], "wait", "reference")
    }
    assert fail_less.is_dir()
    # Opening the attempt closes reruns.
    record_exposure(
        a.ledger,
        attempt_id=a.d.attempt_id,
        purpose="inspection",
        evidence_sha256=sha("x"),
    )
    with pytest.raises(ValueError, match="opened attempts"):
        rerun(a, other, tmp_path / "rerun-other")


def test_policy_none_attempt_refuses_reruns(tmp_path, monkeypatch):
    a = sealed_attempt(tmp_path, monkeypatch, policy=None)
    assert a.d.technical_rerun_policy == "none"
    c = claim(a, tmp_path / "original")
    fail_output(c, "ConnectionRefusedError", "[Errno 61] Connection refused")
    with pytest.raises(ValueError, match="did not pre-declare"):
        rerun(a, c, tmp_path / "rerun")
    with pytest.raises(ValueError, match="did not pre-declare"):
        technical_rerun_candidates(a.ledger, attempt_id=a.d.attempt_id)
    with sqlite3.connect(a.ledger) as db:
        assert db.execute("SELECT count(*) FROM branch_reruns").fetchone()[0] == 0
    # A hand-inserted rerun row for a policy-none attempt is rejected.
    from clasher.rl.readiness_capture_ownership import TechnicalRerun

    forged = TechnicalRerun(
        attempt_id=a.d.attempt_id,
        policy=POLICY,
        original_claim=c,
        rerun_claim=RerunBranchClaim(
            **c.model_dump(exclude={"nonce", "output_path"}),
            nonce="forged",
            output_path=str(tmp_path / "forged"),
            original_nonce=c.nonce,
        ),
        reason="infrastructure_failure",
        failure_type="ConnectionRefusedError",
        evidence={},
    )
    with sqlite3.connect(a.ledger) as db:
        db.execute(
            "INSERT INTO branch_reruns VALUES (?,?,?,?,?,?)",
            (
                c.nonce,
                "forged",
                str(tmp_path / "forged"),
                forged.reason,
                forged.evidence_sha256,
                forged.model_dump_json(),
            ),
        )
    start_output(forged.rerun_claim)
    with pytest.raises(ValueError, match="did not pre-declare"):
        record_branch_result(a.ledger, forged.rerun_claim, None, artifact_hashes={})


def test_v4_style_declaration_hash_and_records_are_unchanged(tmp_path):
    d = declaration(tmp_path)
    raw = json.loads(d.model_dump_json())
    assert "technical_rerun_policy" not in raw
    # A declaration stored before the field existed parses to "none" and keeps
    # its design hash (the hash of the stored record's canonical JSON).
    parsed = AttemptDeclaration.model_validate_json(json.dumps(raw))
    assert parsed == d and parsed.technical_rerun_policy == "none"
    assert parsed.sha256 == canonical_sha(raw) == d.sha256
    opted = AttemptDeclaration.model_validate(
        {**d.model_dump(), "technical_rerun_policy": POLICY}
    )
    assert opted.sha256 != d.sha256
    assert json.loads(opted.model_dump_json())["technical_rerun_policy"] == POLICY
    with pytest.raises(ValueError):
        AttemptDeclaration.model_validate(
            {**d.model_dump(), "technical_rerun_policy": "always"}
        )
    # Receipts/reports without reruns keep their exact prior serialization.
    receipt = AdmissionReceipt(
        attempt_id=d.attempt_id,
        ledger_path="/l",
        source_root="/s",
        design_sha256=d.sha256,
        root_seal_sha256=sha("seal"),
        protocol_sha256=sha("protocol"),
        report_path="/r",
        report_sha256=sha("r"),
        calibration_receipt_path="/c",
        calibration_receipt_sha256=sha("c"),
        source_pins=d.source_pins,
        input_pins=d.input_pins,
        gamedata_sha256=d.gamedata_sha256,
        catalog_sha256=d.catalog_sha256,
        workspace_gamedata_sha256=d.workspace_gamedata_sha256,
    )
    assert "technical_reruns" not in json.loads(receipt.model_dump_json())
    assert AdmissionReceipt.model_validate_json(receipt.model_dump_json()) == receipt


def test_runner_reruns_only_ledger_eligible_claims_of_its_engine_and_shard(
    tmp_path, monkeypatch
):
    runner = load_runner(monkeypatch)
    dev = development_plan(tmp_path, purpose="development_coverage", repetitions=1)
    fresh = dev.model_copy(update={"purpose": "fresh_acceptance"})
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(dev.model_dump_json())
    declared = jobs(fresh)
    calibration = tmp_path / "calibration.json"
    calibration.write_text("{}")
    monkeypatch.setattr(
        runner,
        "ExecutionPlan",
        types.SimpleNamespace(model_validate_json=lambda text: fresh),
    )
    monkeypatch.setattr(
        runner,
        "require_execution_plan",
        lambda *a, **k: types.SimpleNamespace(
            input_pins={str(calibration.resolve()): file_sha(calibration)}
        ),
    )
    monkeypatch.setattr(
        runner,
        "_checked_calibration",
        lambda path: types.SimpleNamespace(
            catalog_sha256=fresh.catalog_sha256,
            ruleset_sha256=tuple(
                c.input_hashes["gamedata.json"] for c in fresh.captures
            ),
        ),
    )
    scalar = [i for i, j in enumerate(declared) if j.engine == "scalar"]
    reference = next(i for i, j in enumerate(declared) if j.engine == "reference")
    eligible = {scalar[0], scalar[3], reference}
    originals = {
        branch_key(declared[i]): (
            types.SimpleNamespace(nonce=f"n-{i}", output_path=f"/old/job-{i:05d}"),
            "infrastructure_failure",
            "ConnectionRefusedError",
        )
        for i in eligible
    }
    monkeypatch.setattr(runner, "technical_rerun_candidates", lambda *a, **k: originals)
    reruns, executed = [], []

    def fake_rerun(ledger, *, attempt_id, original_nonce, output_path):
        assert not output_path.exists()
        reruns.append((original_nonce, output_path.name))
        return types.SimpleNamespace(
            model_dump=lambda mode: {"nonce": "r-" + original_nonce}
        )

    def refuse(*args, **kwargs):
        raise AssertionError("technical reruns never make ordinary claims")

    monkeypatch.setattr(runner, "claim_technical_rerun", fake_rerun)
    monkeypatch.setattr(runner, "claim_branch", refuse)
    monkeypatch.setattr(
        runner,
        "execute_job",
        lambda plan, job, output, args: (
            executed.append(output.name)
            or {"public_contract_valid": False, "public_calibration_established": False}
        ),
    )
    fresh_args = {
        "ownership_ledger": tmp_path / "ledger.sqlite",
        "attempt_id": "attempt",
        "calibration_receipt": calibration,
        "engine": "scalar",
        "technical_reruns": True,
    }
    with pytest.raises(ValueError, match="omit --unclaimed-only"):
        runner.execute(run_args(tmp_path, plan_path, unclaimed_only=True, **fresh_args))
    # Shard 1 of 2 over scalar jobs: scalar[3] is in it, scalar[0] is not.
    assert (
        runner.execute(
            run_args(tmp_path, plan_path, shard_index=1, shard_count=2, **fresh_args)
        )
        == 0
    )
    assert reruns == [(f"n-{scalar[3]}", f"job-{scalar[3]:05d}")]
    assert executed == [f"job-{scalar[3]:05d}"]
    run = tmp_path / "run"
    complete = json.loads((run / "complete.json").read_text())
    assert complete["status"] == "completed_fresh_technical_rerun_batch"
    assert complete["selected_indices"] == [scalar[3]]
    selection = json.loads((run / "technical-rerun-selection.json").read_text())
    assert selection == [
        {
            "index": scalar[3],
            "original_nonce": f"n-{scalar[3]}",
            "original_output_path": f"/old/job-{scalar[3]:05d}",
            "reason": "infrastructure_failure",
            "failure_type": "ConnectionRefusedError",
        }
    ]
    # Development (non-ledger) plans cannot use technical reruns.
    monkeypatch.setattr(
        runner,
        "ExecutionPlan",
        types.SimpleNamespace(model_validate_json=lambda text: dev),
    )
    with pytest.raises(ValueError, match="fresh Tier A"):
        runner.execute(
            run_args(
                tmp_path, plan_path, output=tmp_path / "dev-run", technical_reruns=True
            )
        )


def test_runner_signal_writes_runner_terminated_failure(tmp_path, monkeypatch):
    runner = load_runner(monkeypatch)
    dev = development_plan(tmp_path, purpose="development_coverage", repetitions=1)
    plan_path = tmp_path / "execution-plan.json"
    plan_path.write_text(dev.model_dump_json())
    before = signal.getsignal(signal.SIGTERM)

    def killed(plan, job, output, args):
        os.kill(os.getpid(), signal.SIGTERM)
        for _ in range(500):
            time.sleep(0.01)
        raise AssertionError("signal was not delivered")

    monkeypatch.setattr(runner, "execute_job", killed)
    with pytest.raises(runner.RunnerTerminated):
        runner.execute(run_args(tmp_path, plan_path, engine="scalar"))
    assert signal.getsignal(signal.SIGTERM) == before
    failures = sorted((tmp_path / "run").glob("job-*/failure.json"))
    assert len(failures) == 1
    failure = json.loads(failures[0].read_text())
    assert failure["type"] == "RunnerTerminated" and failure["after_result"] is False
    assert "SIGTERM" in failure["message"]
    assert is_infrastructure_failure(failure["type"], failure["message"])
    assert not (tmp_path / "run" / "complete.json").exists()
