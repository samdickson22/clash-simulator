"""Tier B ownership in a temporary readiness-v2 ledger (never the real one).

Synthetic captures and branches only; no native execution or promotion
evidence. Tier A tables and invariants are checked to remain untouched.
"""

import gzip
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_readiness_capture_ownership import declaration as tier_a_declaration
from test_readiness_tier_b import record as policy_record
from test_readiness_tier_b import strata
from test_training_readiness_v2 import candidates, floors, sha

from clasher.rl import readiness_tier_b_ledger as ledger_module
from clasher.rl import readiness_transport
from clasher.rl.readiness_capture_ownership import (
    CaptureReceipt,
    _transaction,
    claim_episode,
    declare_attempt,
)
from clasher.rl.readiness_execution import (
    CAPTURE_FILES,
    CaptureBinding,
    ExecutionPlan,
    canonical_sha,
    file_sha,
)
from clasher.rl.readiness_tier_b import TierBProtocol
from clasher.rl.readiness_tier_b_ledger import (
    TierBDeclaration,
    TierBEpisodeSpec,
    build_frozen_tier_b_protocol,
    claim_tier_b_branch,
    claim_tier_b_episode,
    declare_tier_b_attempt,
    evaluate_tier_b_attempt,
    get_tier_b_attempt,
    record_tier_b_branch_result,
    record_tier_b_capture,
    record_tier_b_exposure,
    require_tier_b_execution_plan,
    seal_tier_b_roots,
    tier_b_claimed_branch_keys,
)
from clasher.rl.training_readiness_v2 import CONDITIONS, ROLES, Branch, Family


@pytest.fixture(autouse=True)
def narrow_source_pins(tmp_path, monkeypatch):
    """Pin one synthetic producer so tests do not hash the tree per call."""
    source = tmp_path / "frozen-tier-b-producer.py"
    source.write_text("synthetic Tier B producer fixture\n")
    storage = Path("src/clasher/rl/native_frame_storage.py").resolve()
    pins = {str(source): file_sha(source), str(storage): file_sha(storage)}
    monkeypatch.setattr(ledger_module, "required_tier_b_source_pins", lambda: pins)
    return pins


def tb_declaration(tmp_path, pins, *, block="representative", attempt="tier-b", offset=1000, drop_strata=None):
    inputs = tmp_path / f"inputs-{attempt}"
    inputs.mkdir()
    files = {}
    for name in ("manifest.json", "calibration.json", "catalog.csv", "checkpoint.pt", "tier-a-admission.json"):
        files[name] = inputs / name
        files[name].write_text(f"synthetic {name}\n")
    workspace = Path("gamedata.json").resolve()
    input_pins = {str(p.resolve()): file_sha(p) for p in (workspace, *files.values())}
    cells = strata(block)
    episodes = []
    for i, cell in enumerate(cells):
        config = inputs / f"config-{i}.json"
        config.write_text(json.dumps({"rndSeed": offset + i, "battle": {"synthetic": True}}))
        episodes.append(
            TierBEpisodeSpec(
                family_id=cell.family_id,
                source_episode_id=f"{attempt}-game-{offset + i}",
                config_path=str(config),
                config_file_sha256=file_sha(config),
                config_sha256=canonical_sha(json.loads(config.read_text())),
                root_request_sha256=canonical_sha({"tier_b_request": offset + i}),
                root_owner=cell.root_owner,
                deck_id=cell.deck_id,
                phase=cell.phase,
                opponent=cell.opponent,
                probe_kind=cell.probe_kind,
            )
        )
    historical = tmp_path / "historical.sqlite"
    with sqlite3.connect(historical) as db:
        db.execute("CREATE TABLE IF NOT EXISTS native_roots(group_id TEXT PRIMARY KEY,record TEXT NOT NULL)")
    development = tmp_path / "development-v2.sqlite"
    with _transaction(development):
        pass
    protocol = TierBProtocol(
        attempt_id=attempt,
        block_kind=block,
        family_count=len(cells),
        minimum_nonwait_informative=15 if block == "representative" else None,
        checkpoint_sha256=file_sha(files["checkpoint.pt"]),
        policy_contract_sha256=sha("contract"),
        tier_a_protocol_sha256=sha("tier-a"),
        source_pins=pins,
        config_sha256=sha("configs"),
        generator_sha256=sha("generator"),
        floors=floors(),
        strata=cells,
    )
    return TierBDeclaration(
        attempt_id=attempt,
        block_kind=block,
        root_bank_sha256=sha("bank"),
        generator_sha256=sha("generator"),
        converter_manifest_sha256=file_sha(files["manifest.json"]),
        checkpoint_path=str(files["checkpoint.pt"].resolve()),
        checkpoint_sha256=file_sha(files["checkpoint.pt"]),
        tier_a_admission_path=str(files["tier-a-admission.json"].resolve()),
        tier_a_admission_sha256=file_sha(files["tier-a-admission.json"]),
        pre_protocol=protocol,
        native_attestation_sha256=sha("native"),
        gamedata_sha256=file_sha(workspace),
        catalog_sha256=file_sha(files["catalog.csv"]),
        workspace_gamedata_sha256=file_sha(workspace),
        source_pins=pins,
        input_pins=input_pins,
        episodes=tuple(episodes),
        historical_registries=(str(historical), str(development)),
    )


def tb_capture(ledger, decl, index, rootdir, *, status="selected"):
    episode = decl.episodes[index]
    output = rootdir / f"tb-capture-{index}"
    claim = claim_tier_b_episode(
        ledger,
        attempt_id=decl.attempt_id,
        family_id=episode.family_id,
        output_path=output,
        native_attestation_sha256=decl.native_attestation_sha256,
    )
    output.mkdir()
    for name in CAPTURE_FILES:
        (output / name).write_text("{}")
    (output / "gamedata.json").write_bytes(Path("gamedata.json").read_bytes())
    (output / "plan.json").write_text(
        json.dumps(
            {
                "config": json.loads(Path(episode.config_path).read_text()),
                "root_request": {"tier_b_request": int(episode.source_episode_id.split("-")[-1])},
            }
        )
    )
    binding = family = None
    record = None
    if status == "selected":
        binding = CaptureBinding(
            family_id=episode.family_id,
            capture_path=str(output),
            root_tick=400,
            input_hashes={name: file_sha(output / name) for name in CAPTURE_FILES},
            config_sha256=episode.config_sha256,
            root_frame_sha256=sha(("frame", index)),
        )
        family = Family(
            family_id=episode.family_id,
            independence_id=episode.source_episode_id,
            root_sha256=binding.root_sha256,
            public_packet_sha256=sha(("tb-public", index)),
            root_owner=episode.root_owner,
            role="fresh_acceptance",
            candidates=candidates(),
            original_recommendation=2304,
        )
        record = policy_record(family, episode.probe_kind).model_copy(
            update={"checkpoint_sha256": decl.checkpoint_sha256}
        )
    (output / "policy-root.json").write_text(
        json.dumps(
            {
                "status": status,
                "checkpoint_sha256": decl.checkpoint_sha256,
                "root_request_sha256": episode.root_request_sha256,
                "record": None if record is None else record.model_dump(mode="json"),
            }
        )
    )
    receipt = CaptureReceipt(
        claim_nonce=claim.nonce,
        design_sha256=claim.design_sha256,
        family_id=claim.family_id,
        config_sha256=claim.config_sha256,
        native_attestation_sha256=claim.native_attestation_sha256,
        status=status,
        prefix_complete=status != "failed",
        artifact_hashes={p.name: file_sha(p) for p in output.iterdir()},
        selected_family=family,
        capture_binding=binding,
        failure="synthetic failure" if status == "failed" else None,
    )
    record_tier_b_capture(ledger, claim, receipt)
    return claim, receipt


def test_declaration_requires_tier_a_admission_and_pinned_checkpoint(tmp_path, narrow_source_pins):
    d = tb_declaration(tmp_path, narrow_source_pins)
    ledger = tmp_path / "v2.sqlite"
    with pytest.raises(ValueError, match="Tier A admission ledger"):
        declare_tier_b_attempt(ledger, d, tier_a_ledger=None)
    with _transaction(tmp_path / "tier-a.sqlite"):
        pass
    # A hand-written file is not a ledger-issued Tier A admission.
    with pytest.raises(ValueError):
        declare_tier_b_attempt(ledger, d, tier_a_ledger=tmp_path / "tier-a.sqlite")
    unpinned = {k: v for k, v in d.input_pins.items() if not k.endswith("checkpoint.pt")}
    with pytest.raises(ValueError, match="frozen checkpoint must be pinned"):
        TierBDeclaration.model_validate({**d.model_dump(), "input_pins": unpinned}, strict=False)
    bound = d.pre_protocol.model_copy(update={"floors": None})
    with pytest.raises(ValueError, match="floors"):
        TierBDeclaration.model_validate({**d.model_dump(), "pre_protocol": bound.model_dump()}, strict=False)
    assert declare_tier_b_attempt(ledger, d, tier_a_ledger=None, require_tier_a=False) == d.sha256
    assert get_tier_b_attempt(ledger, d.attempt_id) == d
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM fresh_identities").fetchone()[0] == 30


def test_freshness_is_shared_across_tiers_in_both_directions(tmp_path, narrow_source_pins):
    ledger = tmp_path / "v2.sqlite"
    development = tier_a_declaration(tmp_path, attempt="tier-a-dev", offset=5000)
    declare_attempt(ledger, development)
    reused = tb_declaration(tmp_path, narrow_source_pins, attempt="tier-b-reuse", offset=5000)
    with pytest.raises(ValueError, match="Tier A attempt"):
        declare_tier_b_attempt(ledger, reused, tier_a_ledger=None, require_tier_a=False)
    d = tb_declaration(tmp_path, narrow_source_pins, attempt="tier-b", offset=1000)
    declare_tier_b_attempt(ledger, d, tier_a_ledger=None, require_tier_a=False)
    again = tb_declaration(tmp_path, narrow_source_pins, attempt="tier-b-2", offset=1000)
    with pytest.raises(ValueError, match="earlier attempt"):
        declare_tier_b_attempt(ledger, again, tier_a_ledger=None, require_tier_a=False)
    # A later Tier A attempt cannot reuse a Tier B root identity.
    later = tier_a_declaration(tmp_path, fresh=True, attempt="tier-a-later", offset=1000)
    with pytest.raises(sqlite3.IntegrityError):
        declare_attempt(ledger, later)
    # Tier A authority functions never see Tier B attempts.
    with pytest.raises(ValueError, match="undeclared readiness attempt"):
        claim_episode(
            ledger, attempt_id="tier-b", family_id="tb-0", output_path=tmp_path / "x",
            native_attestation_sha256=d.native_attestation_sha256,
        )


def test_seal_retains_missing_roots_and_freezes_policy_rankings(tmp_path, narrow_source_pins):
    d = tb_declaration(tmp_path, narrow_source_pins)
    ledger = tmp_path / "v2.sqlite"
    declare_tier_b_attempt(ledger, d, tier_a_ledger=None, require_tier_a=False)
    for i in range(30):
        tb_capture(ledger, d, i, tmp_path, status="no_eligible_root" if i == 3 else "selected")
    protocol = build_frozen_tier_b_protocol(ledger, attempt_id=d.attempt_id)
    assert protocol.generation_failures == ("tb-3: no_eligible_root",)
    assert len(protocol.families) == len(protocol.policy_roots) == 29
    hidden = protocol.model_copy(update={"generation_failures": ()})
    with pytest.raises(ValueError):
        seal_tier_b_roots(ledger, attempt_id=d.attempt_id, protocol=hidden)
    moved = TierBProtocol.model_validate(
        {**protocol.model_dump(), "strata": [s.model_dump() for s in reversed(protocol.strata)]},
        strict=False,
    )
    with pytest.raises(ValueError, match="criteria, strata or pins"):
        seal_tier_b_roots(ledger, attempt_id=d.attempt_id, protocol=moved)
    seal = seal_tier_b_roots(ledger, attempt_id=d.attempt_id, protocol=protocol)
    assert seal.protocol == protocol
    with pytest.raises(sqlite3.IntegrityError):
        seal_tier_b_roots(ledger, attempt_id=d.attempt_id, protocol=protocol)
    claim = claim_tier_b_branch(
        ledger, attempt_id=d.attempt_id, family_id="tb-0", condition=CONDITIONS[0],
        candidate_role="wait", engine="scalar", output_path=tmp_path / "branch-a",
    )
    assert claim.protocol_sha256 == protocol.sha256
    with pytest.raises(ValueError, match="undeclared branch case"):
        claim_tier_b_branch(
            ledger, attempt_id=d.attempt_id, family_id="tb-3", condition=CONDITIONS[0],
            candidate_role="wait", engine="scalar", output_path=tmp_path / "branch-b",
        )
    with pytest.raises(sqlite3.IntegrityError):
        claim_tier_b_branch(
            ledger, attempt_id=d.attempt_id, family_id="tb-0", condition=CONDITIONS[0],
            candidate_role="wait", engine="scalar", output_path=tmp_path / "branch-c",
        )
    assert tier_b_claimed_branch_keys(ledger, attempt_id=d.attempt_id) == {
        ("tb-0", CONDITIONS[0], "wait", "scalar")
    }
    with pytest.raises(ValueError, match="never enter training"):
        record_tier_b_exposure(ledger, attempt_id=d.attempt_id, purpose="training", evidence_sha256=sha("x"))
    record_tier_b_exposure(ledger, attempt_id=d.attempt_id, purpose="inspection", evidence_sha256=sha("x"))
    with pytest.raises(ValueError, match="opened attempts"):
        claim_tier_b_branch(
            ledger, attempt_id=d.attempt_id, family_id="tb-1", condition=CONDITIONS[0],
            candidate_role="wait", engine="scalar", output_path=tmp_path / "branch-d",
        )


def test_capture_policy_record_must_match_the_selected_family(tmp_path, narrow_source_pins):
    d = tb_declaration(tmp_path, narrow_source_pins)
    ledger = tmp_path / "v2.sqlite"
    declare_tier_b_attempt(ledger, d, tier_a_ledger=None, require_tier_a=False)
    original = ledger_module.PolicyRootRecord.model_validate

    def swapped(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        return result.model_copy(update={"original_recommendation": 0})

    ledger_module.PolicyRootRecord.model_validate = swapped
    try:
        with pytest.raises(ValueError, match="policy ranking record differs"):
            tb_capture(ledger, d, 0, tmp_path)
    finally:
        ledger_module.PolicyRootRecord.model_validate = original
    with pytest.raises(ValueError, match="needs a recorded capture"):
        build_frozen_tier_b_protocol(ledger, attempt_id=d.attempt_id)


def write_branch(output, claim, family, protocol, decl, role, engine, condition, calibration, storage):
    output.mkdir()
    (output / "ownership-claim.json").write_text(claim.model_dump_json())
    job = {"family_id": family.family_id, "condition": condition, "candidate_role": role, "engine": engine}
    (output / "claim.json").write_text(json.dumps(job))
    for name in ("decisions.jsonl.gz", "transport.jsonl.gz"):
        with gzip.open(output / name, "wt") as stream:
            stream.write("{}\n")
    winner = family.root_owner if role == "immediate_play" else None
    towers = [{"owner": 0, "hp": 1000}, {"owner": 1, "hp": 1000}]
    terminal = (
        {"playable": {"ended": True, "tick": 3601, "objects": [dict(t, cardId=-1) for t in towers]},
         "final": {"finalized": True, "winner": winner}}
        if engine == "reference"
        else {"game_over": True, "winner": winner, "towers": towers}
    )
    (output / "terminal.json").write_text(json.dumps(terminal))
    gamedata = Path("gamedata.json").resolve()
    result = {
        "job": job, "root_owner": family.root_owner,
        "score": 1.0 if role == "immediate_play" else 0.5,
        "own_remaining_hp": 1000.0, "enemy_remaining_hp": 1000.0,
        "root_sha256": family.root_sha256, "public_packet_sha256": family.public_packet_sha256,
        "protocol_sha256": protocol.sha256, "public_contract_valid": True,
        "public_calibration_established": True, "legal_transport_valid": True,
        "calibration_receipt_sha256": file_sha(calibration), "gamedata_path": str(gamedata),
        "gamedata_sha256": decl.gamedata_sha256, "catalog_sha256": decl.catalog_sha256,
        "native_frame_storage_sha256": file_sha(storage),
        "capture_path": str(output.parent / f"tb-capture-{int(family.family_id.split('-')[-1])}"),
        "root_tick": 400, "native_attestation_sha256": decl.native_attestation_sha256,
        "terminal_sha256": file_sha(output / "terminal.json"),
        "decisions_sha256": file_sha(output / "decisions.jsonl.gz"),
        "transport_sha256": file_sha(output / "transport.jsonl.gz"),
    }
    if engine == "reference":
        session = {"status": "verified", "session_id": "synthetic-tier-b"}
        (output / "native-session.json").write_text(json.dumps(session))
        result["native_read_session"] = session
        result["native_session_sha256"] = file_sha(output / "native-session.json")
    (output / "result.json").write_text(json.dumps(result))
    candidate = next(c for c in family.candidates if c.role == role)
    branch = Branch(
        protocol_sha256=protocol.sha256, family_id=family.family_id, root_sha256=family.root_sha256,
        public_packet_sha256=family.public_packet_sha256, candidate_role=role,
        action_id=candidate.action_id, condition=condition, engine=engine,
        artifact_sha256=file_sha(output / "result.json"), score=result["score"],
        own_remaining_hp=1000.0, enemy_remaining_hp=1000.0, terminal=True,
        public_contract_valid=True, legal_transport_valid=True,
    )
    (output / "branch.json").write_text(branch.model_dump_json())
    return branch


def sealed_probe_attempt(tmp_path, pins):
    d = tb_declaration(tmp_path, pins, block="targeted_probe")
    ledger = tmp_path / "v2.sqlite"
    declare_tier_b_attempt(ledger, d, tier_a_ledger=None, require_tier_a=False)
    for i in range(6):
        tb_capture(ledger, d, i, tmp_path, status="failed" if i == 5 else "selected")
    protocol = build_frozen_tier_b_protocol(ledger, attempt_id=d.attempt_id)
    seal_tier_b_roots(ledger, attempt_id=d.attempt_id, protocol=protocol)
    captures = []
    with sqlite3.connect(ledger) as db:
        for (raw,) in db.execute("SELECT record FROM tier_b_captures ORDER BY family_id"):
            receipt = CaptureReceipt.model_validate_json(raw)
            if receipt.capture_binding is not None:
                captures.append(receipt.capture_binding)
    catalog = next(Path(p) for p in d.input_pins if p.endswith("catalog.csv"))
    plan = ExecutionPlan(
        protocol=protocol, captures=tuple(captures), catalog_path=str(catalog),
        catalog_sha256=d.catalog_sha256, native_attestation_sha256=d.native_attestation_sha256,
        source_pins=d.source_pins, purpose="tier_b_transfer",
    )
    return d, ledger, protocol, plan


def test_full_probe_matrix_reports_separately_and_never_admits(tmp_path, narrow_source_pins, monkeypatch):
    monkeypatch.setattr(readiness_transport, "audit_native_transport_files", lambda *a, **k: 1)
    monkeypatch.setattr(readiness_transport, "audit_scalar_decisions", lambda *a, **k: 1)
    d, ledger, protocol, plan = sealed_probe_attempt(tmp_path, narrow_source_pins)
    assert require_tier_b_execution_plan(ledger, plan, attempt_id=d.attempt_id) == d
    calibration = next(Path(p) for p in d.input_pins if p.endswith("calibration.json"))
    storage = Path("src/clasher/rl/native_frame_storage.py").resolve()
    count = 0
    for family in protocol.families:
        for condition in CONDITIONS:
            for role in ROLES:
                for engine in ("scalar", "reference"):
                    output = tmp_path / f"branch-{count:04d}"
                    count += 1
                    claim = claim_tier_b_branch(
                        ledger, attempt_id=d.attempt_id, family_id=family.family_id,
                        condition=condition, candidate_role=role, engine=engine, output_path=output,
                    )
                    branch = write_branch(output, claim, family, protocol, d, role, engine, condition, calibration, storage)
                    record_tier_b_branch_result(
                        ledger, claim, branch,
                        artifact_hashes={p.name: file_sha(p) for p in output.iterdir()},
                    )
    checker = lambda path: SimpleNamespace(ruleset_sha256=(d.gamedata_sha256,), catalog_sha256=d.catalog_sha256)
    report, receipt = evaluate_tier_b_attempt(
        ledger, attempt_id=d.attempt_id, calibration_receipt_path=calibration,
        report_path=tmp_path / "tier-b-report.json", receipt_path=tmp_path / "tier-b-receipt.json",
        calibration_checker=checker,
    )
    assert count == 5 * 32
    # The failed probe root stays in accounting: the block cannot be clear.
    assert report.status == "inconclusive" and report.missing_roots == ("tb-5",)
    assert receipt.status == "inconclusive" and receipt.grants_scope is False
    assert report.representative_failure_upper_bound is None
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT count(*) FROM admissions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM tier_b_reports").fetchone()[0] == 1
    with pytest.raises(ValueError, match="opened attempts"):
        claim_tier_b_branch(
            ledger, attempt_id=d.attempt_id, family_id="tb-0", condition=CONDITIONS[0],
            candidate_role="wait", engine="scalar", output_path=tmp_path / "late",
        )
    # Mutating a sealed capture after evaluation is detected on any reuse.
    (tmp_path / "tb-capture-0" / "plan.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact changed"):
        require_tier_b_execution_plan(ledger, plan, attempt_id=d.attempt_id)


def test_executor_routes_tier_b_plans_to_tier_b_ownership_only(tmp_path, narrow_source_pins, monkeypatch):
    from test_readiness_job_selection import load_runner, run_args

    runner = load_runner(monkeypatch)
    d, ledger, _protocol, plan = sealed_probe_attempt(tmp_path, narrow_source_pins)
    plan_path = tmp_path / "tier-b-plan.json"
    plan_path.write_text(plan.model_dump_json())
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Tier A ownership used for a Tier B plan")

    for name in ("claim_branch", "record_branch_result", "require_execution_plan", "claimed_branch_keys"):
        monkeypatch.setattr(runner, name, forbidden)
    monkeypatch.setattr(runner, "record_tier_b_branch_result", lambda *a, **k: calls.append("record"))
    monkeypatch.setattr(
        runner, "_checked_calibration",
        lambda path: SimpleNamespace(ruleset_sha256=(d.gamedata_sha256,), catalog_sha256=d.catalog_sha256),
    )
    calibration = next(Path(p) for p in d.input_pins if p.endswith("calibration.json"))

    def fake_job(execution, job, output, args):
        family = next(f for f in execution.protocol.families if f.family_id == job.family_id)
        return {
            "public_contract_valid": True, "public_calibration_established": True,
            "root_sha256": family.root_sha256, "public_packet_sha256": family.public_packet_sha256,
            "score": 0.5, "own_remaining_hp": 1.0, "enemy_remaining_hp": 1.0,
        }

    monkeypatch.setattr(runner, "execute_job", fake_job)
    args = run_args(
        tmp_path, plan_path, engine="scalar", ownership_ledger=ledger,
        attempt_id=d.attempt_id, calibration_receipt=calibration, job_index=[0, 2],
    )
    assert runner.execute(args) == 0
    complete = json.loads((tmp_path / "run" / "complete.json").read_text())
    assert complete["status"] == "completed_tier_b_branch_batch"
    assert calls == ["record", "record"]
    assert len(tier_b_claimed_branch_keys(ledger, attempt_id=d.attempt_id)) == 2
