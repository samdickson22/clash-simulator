"""Synthetic ledger invariants; no native execution or admission evidence."""

import json
import sqlite3
from pathlib import Path

import pytest
from test_training_readiness_v2 import candidates, floors, sha

from clasher.rl.readiness_capture_ownership import (
    AdmissionReceipt,
    AttemptDeclaration,
    CaptureReceipt,
    EpisodeSpec,
    _transaction,
    claim_branch,
    claim_episode,
    claimed_branch_keys,
    declare_attempt,
    get_attempt,
    get_root_seal,
    record_capture,
    record_exposure,
    require_admission,
    required_source_pins,
    seal_roots,
)
from clasher.rl.readiness_execution import (
    CAPTURE_FILES,
    CaptureBinding,
    canonical_sha,
    file_sha,
)
from clasher.rl.training_readiness_v2 import Family, Protocol


def declaration(tmp_path, *, fresh=False, attempt="attempt", offset=0):
    count = 32 if fresh else 1
    inputs = tmp_path / f"inputs-{attempt}"
    inputs.mkdir()
    workspace = Path("gamedata.json").resolve()
    marker = inputs / "source.py"
    marker.write_text("synthetic source\n")
    manifest = inputs / "manifest.json"
    manifest.write_text("{}\n")
    calibration = inputs / "calibration.json"
    calibration.write_text("{}\n")
    catalog = inputs / "catalog.csv"
    catalog.write_text("synthetic catalog\n")
    sources = required_source_pins() if fresh else {str(marker): file_sha(marker)}
    input_pins = {
        str(p): file_sha(p) for p in (workspace, manifest, calibration, catalog)
    }
    episodes = []
    for i in range(count):
        config = inputs / f"config-{i}.json"
        config.write_text(
            json.dumps({"rndSeed": offset + i, "battle": {"synthetic": True}})
        )
        episodes.append(
            EpisodeSpec(
                family_id=f"family-{i}",
                source_episode_id=f"episode-{offset + i}",
                config_path=str(config),
                config_file_sha256=file_sha(config),
                config_sha256=canonical_sha(json.loads(config.read_text())),
                root_request_sha256=canonical_sha({"id": offset + i}),
                root_owner=i % 2,
            )
        )
    historical = tmp_path / "historical.sqlite"
    with sqlite3.connect(historical) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS native_roots(group_id TEXT PRIMARY KEY,record TEXT NOT NULL)"
        )
    # Separate development-v2 ownership ledger; fresh checks require both kinds.
    development = tmp_path / "development-v2.sqlite"
    with _transaction(development):
        pass
    protocol = Protocol(
        attempt_id=attempt,
        source_pins=sources,
        config_sha256=sha("configs"),
        generator_sha256=sha("generator"),
        scalar_coverage_study_sha256=sha("synthetic-coverage"),
        floors=floors(),
    )
    return AttemptDeclaration(
        attempt_id=attempt,
        evidence_role="fresh_acceptance" if fresh else "opened_development",
        root_bank_sha256=sha("bank"),
        generator_sha256=sha("generator"),
        converter_manifest_sha256=file_sha(manifest),
        pre_protocol=protocol,
        native_attestation_sha256=sha("native"),
        gamedata_sha256=file_sha(workspace),
        catalog_sha256=file_sha(catalog),
        workspace_gamedata_sha256=file_sha(workspace),
        source_pins=sources,
        input_pins=input_pins,
        episodes=tuple(episodes),
        historical_registries=(str(historical), str(development)) if fresh else (),
    )


def capture(ledger, decl, index, rootdir, *, status="selected"):
    episode = decl.episodes[index]
    output = rootdir / f"capture-{index}"
    claim = claim_episode(
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
                "root_request": {"id": int(episode.source_episode_id.split("-")[-1])},
            }
        )
    )
    binding = CaptureBinding(
        family_id=episode.family_id,
        capture_path=str(output),
        root_tick=90,
        input_hashes={name: file_sha(output / name) for name in CAPTURE_FILES},
        config_sha256=episode.config_sha256,
        root_frame_sha256=sha(f"frame-{index}"),
    )
    family = Family(
        family_id=episode.family_id,
        independence_id=episode.source_episode_id,
        root_sha256=binding.root_sha256,
        public_packet_sha256=sha(f"public-{index}"),
        root_owner=episode.root_owner,
        role=decl.evidence_role,
        candidates=candidates(),
        original_recommendation=2304,
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
        selected_family=family if status == "selected" else None,
        capture_binding=binding if status == "selected" else None,
        failure="synthetic failure" if status == "failed" else None,
    )
    record_capture(ledger, claim, receipt)
    return claim, receipt


def test_atomic_claim_no_retry_redirect_or_existing_directory(tmp_path):
    d = declaration(tmp_path)
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    c = claim_episode(
        ledger,
        attempt_id=d.attempt_id,
        family_id="family-0",
        output_path=tmp_path / "out",
        native_attestation_sha256=d.native_attestation_sha256,
    )
    assert c.design_sha256 == d.sha256 and c.output_path == str(
        (tmp_path / "out").resolve()
    )
    assert get_attempt(ledger, d.attempt_id) == d
    for output in (tmp_path / "out", tmp_path / "redirected"):
        with pytest.raises(sqlite3.IntegrityError):
            claim_episode(
                ledger,
                attempt_id=d.attempt_id,
                family_id="family-0",
                output_path=output,
                native_attestation_sha256=d.native_attestation_sha256,
            )
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT count(*) FROM episode_claims").fetchone()[0] == 1


def test_historical_registry_readonly_and_fresh_reuse_rejected(tmp_path):
    d = declaration(tmp_path, fresh=True)
    historical = Path(d.historical_registries[0])
    with sqlite3.connect(historical) as db:
        db.execute(
            "INSERT INTO native_roots VALUES (?,?)",
            ("known", json.dumps({"config_sha256": d.episodes[0].config_sha256})),
        )
    before = file_sha(historical)
    with pytest.raises(ValueError, match="historical registry"):
        declare_attempt(tmp_path / "v2.sqlite", d)
    assert file_sha(historical) == before
    with pytest.raises(ValueError, match="non-readiness"):
        declare_attempt(
            historical, d.model_copy(update={"evidence_role": "opened_development"})
        )
    assert file_sha(historical) == before


def test_development_declared_episode_cannot_become_fresh(tmp_path):
    old = declaration(tmp_path, attempt="dev")
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, old)
    fresh = declaration(tmp_path, attempt="fresh", fresh=True)
    with pytest.raises(ValueError, match="prior development"):
        declare_attempt(ledger, fresh)


def test_failed_source_drift_is_retained_and_cannot_be_retried(tmp_path):
    d = declaration(tmp_path)
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    output = tmp_path / "failed"
    claim = claim_episode(
        ledger,
        attempt_id=d.attempt_id,
        family_id="family-0",
        output_path=output,
        native_attestation_sha256=d.native_attestation_sha256,
    )
    output.mkdir()
    (output / "failure.json").write_text('{"error":"source drift"}')
    Path(next(iter(d.source_pins))).write_text("changed")
    receipt = CaptureReceipt(
        claim_nonce=claim.nonce,
        design_sha256=claim.design_sha256,
        family_id=claim.family_id,
        config_sha256=claim.config_sha256,
        native_attestation_sha256=claim.native_attestation_sha256,
        status="failed",
        prefix_complete=False,
        artifact_hashes={"failure.json": file_sha(output / "failure.json")},
        failure="source drift",
    )
    record_capture(ledger, claim, receipt)
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT count(*) FROM captures").fetchone()[0] == 1
    with pytest.raises(ValueError, match="pinned input"):
        claim_episode(
            ledger,
            attempt_id=d.attempt_id,
            family_id="family-0",
            output_path=tmp_path / "retry",
            native_attestation_sha256=d.native_attestation_sha256,
        )


def test_root_seal_and_condition_specific_branch_claims(tmp_path):
    d = declaration(tmp_path, fresh=True)
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    captures = [capture(ledger, d, i, tmp_path)[1] for i in range(32)]
    frozen = Protocol.model_validate(
        {
            **d.pre_protocol.model_dump(),
            "status": "frozen",
            "families": tuple(c.selected_family for c in captures),
        }
    )
    seal = seal_roots(ledger, attempt_id=d.attempt_id, protocol=frozen)
    assert get_root_seal(ledger, d.attempt_id) == seal
    for i, condition in enumerate(("balanced/pressure", "defense/pressure")):
        claim = claim_branch(
            ledger,
            attempt_id=d.attempt_id,
            family_id="family-0",
            condition=condition,
            candidate_role="wait",
            engine="reference",
            output_path=tmp_path / f"branch-{i}",
        )
        assert claim.design_sha256 == d.sha256 and claim.root_seal_sha256 == seal.sha256
    with pytest.raises(sqlite3.IntegrityError):
        claim_branch(
            ledger,
            attempt_id=d.attempt_id,
            family_id="family-0",
            condition="balanced/pressure",
            candidate_role="wait",
            engine="reference",
            output_path=tmp_path / "retry-branch",
        )
    # Unclaimed-only selection reads every claim, including unfinished ones.
    assert claimed_branch_keys(ledger, attempt_id=d.attempt_id) == {
        ("family-0", c, "wait", "reference")
        for c in ("balanced/pressure", "defense/pressure")
    }
    with pytest.raises(ValueError, match="undeclared readiness attempt"):
        claimed_branch_keys(ledger, attempt_id="other-attempt")
    with pytest.raises(ValueError, match="undeclared branch"):
        claim_branch(
            ledger,
            attempt_id=d.attempt_id,
            family_id="family-0",
            condition="geometry/geometry",
            candidate_role="wait",
            engine="reference",
            output_path=tmp_path / "wrong-condition",
        )
    record_exposure(
        ledger,
        attempt_id=d.attempt_id,
        purpose="inspection",
        evidence_sha256=sha("opened"),
    )
    with pytest.raises(ValueError, match="opened attempts"):
        claim_branch(
            ledger,
            attempt_id=d.attempt_id,
            family_id="family-1",
            condition="balanced/pressure",
            candidate_role="wait",
            engine="reference",
            output_path=tmp_path / "later",
        )
    with pytest.raises(ValueError, match="never enter training"):
        record_exposure(
            ledger,
            attempt_id=d.attempt_id,
            purpose="training",
            evidence_sha256=sha("fit"),
        )


def test_missing_or_changed_precapture_design_cannot_seal(tmp_path):
    d = declaration(tmp_path, fresh=True)
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    captures = [capture(ledger, d, i, tmp_path)[1] for i in range(31)]
    # Protocol construction itself rejects a missing family, before any ledger seal.
    with pytest.raises(ValueError):
        Protocol.model_validate(
            {
                **d.pre_protocol.model_dump(),
                "status": "frozen",
                "families": tuple(c.selected_family for c in captures),
            }
        )
    last = capture(ledger, d, 31, tmp_path)[1]
    captures.append(last)
    frozen = Protocol.model_validate(
        {
            **d.pre_protocol.model_dump(),
            "status": "frozen",
            "families": tuple(c.selected_family for c in captures),
            "scalar_coverage_study_sha256": sha("changed-after-prefix"),
        }
    )
    with pytest.raises(ValueError, match="changed after pre-capture"):
        seal_roots(ledger, attempt_id=d.attempt_id, protocol=frozen)


def test_hand_authored_admission_json_is_not_authority(tmp_path):
    d = declaration(tmp_path)
    ledger = tmp_path / "v2.sqlite"
    declare_attempt(ledger, d)
    report = tmp_path / "report.json"
    report.write_text("{}")
    receipt = AdmissionReceipt(
        attempt_id=d.attempt_id,
        ledger_path=str(ledger.resolve()),
        source_root=str(Path.cwd()),
        design_sha256=d.sha256,
        root_seal_sha256=sha("fake"),
        protocol_sha256=sha("fake"),
        report_path=str(report),
        report_sha256=file_sha(report),
        calibration_receipt_path=str(report),
        calibration_receipt_sha256=file_sha(report),
        source_pins=d.source_pins,
        input_pins=d.input_pins,
        gamedata_sha256=d.gamedata_sha256,
        catalog_sha256=d.catalog_sha256,
        workspace_gamedata_sha256=d.workspace_gamedata_sha256,
    )
    output = tmp_path / "forged.json"
    output.write_text(receipt.model_dump_json())
    with pytest.raises(ValueError, match="not issued"):
        require_admission(ledger, output)


def _check_extension_lineage(ownership, ledger, d, tmp_path, monkeypatch):
    """Extension authority is ledger-issued and re-derived from verified evidence."""
    from types import SimpleNamespace

    base_path = tmp_path / "admission.json"
    evidence_path = tmp_path / "level-extension.json"
    runtime = {
        "native_attestation_sha256": d.native_attestation_sha256,
        "gamedata_sha256": d.gamedata_sha256,
    }
    evidence_path.write_text(
        json.dumps({"base": file_sha(base_path), "declaration": runtime})
    )

    def install(context):
        # Stand-in for the level-extension verifier (tested separately); it
        # still binds the evidence bytes to one parent admission digest.
        def verified(path, *, parent_sha256):
            data = json.loads(Path(path).read_text())
            if data["base"] != parent_sha256:
                raise ValueError("level extension belongs to another base admission")
            return SimpleNamespace(
                verified_levels=(10, 11, 12),
                level_sampling_scope="uniform_cards",
                native_level_scope="uniform_cards_asymmetric_kings",
                declaration=SimpleNamespace(payload=lambda: data["declaration"]),
            )

        context.setattr(ownership, "_verified_level_extension", verified)

    extended_path = tmp_path / "extended.json"
    with monkeypatch.context() as context:
        install(context)
        extended = ownership.extend_admission(
            ledger,
            base_receipt_path=base_path,
            extension_receipt_path=evidence_path,
            output_path=extended_path,
        )
        assert extended.levels == (10, 11, 12)
        assert extended.parent_admission_sha256 == file_sha(base_path)
        assert require_admission(ledger, extended_path) == extended
        # Byte-identical copies and hand-edited scopes are self-assertions.
        copied = tmp_path / "copied-extension.json"
        copied.write_bytes(extended_path.read_bytes())
        edited = tmp_path / "edited-extension.json"
        edited.write_text(
            extended.model_copy(
                update={"level_sampling_scope": "independent_cards"}
            ).model_dump_json()
        )
        for forged in (copied, edited):
            with pytest.raises(ValueError, match="not issued by the readiness ledger"):
                require_admission(ledger, forged)
        partial = tmp_path / "partial-lineage.json"
        partial.write_text(
            ownership.AdmissionReceipt.model_validate_json(base_path.read_text())
            .model_copy(update={"level_extension_sha256": sha("orphan")})
            .model_dump_json()
        )
        with pytest.raises(ValueError, match="incomplete admission extension"):
            require_admission(ledger, partial)
        with pytest.raises(ValueError, match="original nominal admission"):
            ownership.extend_admission(
                ledger,
                base_receipt_path=extended_path,
                extension_receipt_path=evidence_path,
                output_path=tmp_path / "nested.json",
            )
        # Evidence for another runtime cannot extend this admission.
        other = tmp_path / "other-runtime-extension.json"
        other.write_text(
            json.dumps(
                {
                    "base": file_sha(base_path),
                    "declaration": {**runtime, "native_attestation_sha256": sha("x")},
                }
            )
        )
        with pytest.raises(ValueError, match="runtime/ruleset differs"):
            ownership.extend_admission(
                ledger,
                base_receipt_path=base_path,
                extension_receipt_path=other,
                output_path=tmp_path / "other-extended.json",
            )
        assert not (tmp_path / "other-extended.json").exists()
        # Post-issuance evidence edits revoke the extension.
        original = evidence_path.read_bytes()
        evidence_path.write_text(original.decode().replace("{", "{ ", 1))
        with pytest.raises(ValueError, match="lineage evidence changed"):
            require_admission(ledger, extended_path)
        evidence_path.write_bytes(original)
        assert require_admission(ledger, extended_path) == extended
    return install


def test_full_synthetic_matrix_issues_bound_admission_and_mutation_revokes_it(
    tmp_path, monkeypatch
):
    """Exercise the full authority path; native mechanics auditing is tested separately."""
    import gzip
    from types import SimpleNamespace

    from clasher.rl import readiness_capture_ownership as ownership
    from clasher.rl import readiness_transport
    from clasher.rl.training_readiness_v2 import CONDITIONS, ROLES, Branch

    source = tmp_path / "frozen-test-producer.py"
    source.write_text("synthetic producer fixture\n")
    monkeypatch.setattr(
        ownership, "required_source_pins", lambda: {str(source): file_sha(source)}
    )
    # No native output is asserted by this test. A synthetic backend lets the
    # actual ledger/evaluator/guard process every declared key end to end.
    monkeypatch.setattr(
        readiness_transport, "audit_native_transport_files", lambda *args, **kwargs: 1
    )
    monkeypatch.setattr(
        readiness_transport, "audit_scalar_decisions", lambda *args, **kwargs: 1
    )
    monkeypatch.setattr(
        ownership,
        "_checked_calibration",
        lambda path: SimpleNamespace(
            ruleset_sha256=(d.gamedata_sha256,), catalog_sha256=d.catalog_sha256
        ),
    )
    d = declaration(tmp_path, fresh=True)
    storage_source = Path("src/clasher/rl/native_frame_storage.py").resolve()
    pins = {
        str(source): file_sha(source),
        str(storage_source): file_sha(storage_source),
    }
    d = d.model_copy(
        update={
            "source_pins": pins,
            "pre_protocol": d.pre_protocol.model_copy(update={"source_pins": pins}),
        }
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
    calibration = next(Path(p) for p in d.input_pins if p.endswith("/calibration.json"))
    gamedata = Path("gamedata.json").resolve()
    count = 0
    for family in protocol.families:
        for condition in CONDITIONS:
            for role in ROLES:
                for engine in ("scalar", "reference"):
                    output = tmp_path / f"branch-{count:04d}"
                    count += 1
                    claim = claim_branch(
                        ledger,
                        attempt_id=d.attempt_id,
                        family_id=family.family_id,
                        condition=condition,
                        candidate_role=role,
                        engine=engine,
                        output_path=output,
                    )
                    output.mkdir()
                    (output / "ownership-claim.json").write_text(
                        claim.model_dump_json()
                    )
                    job = {
                        "family_id": family.family_id,
                        "condition": condition,
                        "candidate_role": role,
                        "engine": engine,
                    }
                    (output / "claim.json").write_text(json.dumps(job))
                    for name in ("decisions.jsonl.gz", "transport.jsonl.gz"):
                        with gzip.open(output / name, "wt") as stream:
                            stream.write("{}\n")
                    winner = family.root_owner if role == "immediate_play" else None
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
                        if engine == "reference"
                        else {"game_over": True, "winner": winner, "towers": towers}
                    )
                    (output / "terminal.json").write_text(json.dumps(terminal))
                    result = {
                        "job": job,
                        "root_owner": family.root_owner,
                        "score": 1.0 if role == "immediate_play" else 0.5,
                        "own_remaining_hp": 1000.0,
                        "enemy_remaining_hp": 1000.0,
                        "root_sha256": family.root_sha256,
                        "public_packet_sha256": family.public_packet_sha256,
                        "protocol_sha256": protocol.sha256,
                        "public_contract_valid": True,
                        "public_calibration_established": True,
                        "legal_transport_valid": True,
                        "calibration_receipt_sha256": file_sha(calibration),
                        "gamedata_path": str(gamedata),
                        "gamedata_sha256": d.gamedata_sha256,
                        "catalog_sha256": d.catalog_sha256,
                        "native_frame_storage_sha256": file_sha(storage_source),
                        "catalog_path": next(
                            p for p in d.input_pins if p.endswith("/catalog.csv")
                        ),
                        "capture_path": str(
                            tmp_path / f"capture-{int(family.family_id.split('-')[-1])}"
                        ),
                        "root_tick": 90,
                        "native_attestation_sha256": d.native_attestation_sha256,
                        "terminal_sha256": file_sha(output / "terminal.json"),
                        "decisions_sha256": file_sha(output / "decisions.jsonl.gz"),
                        "transport_sha256": file_sha(output / "transport.jsonl.gz"),
                    }
                    if engine == "reference":
                        session = {
                            "status": "verified",
                            "session_id": "synthetic-ledger-test",
                        }
                        (output / "native-session.json").write_text(json.dumps(session))
                        result["native_read_session"] = session
                        result["native_session_sha256"] = file_sha(
                            output / "native-session.json"
                        )
                    (output / "result.json").write_text(json.dumps(result))
                    candidate = next(c for c in family.candidates if c.role == role)
                    branch = Branch(
                        protocol_sha256=protocol.sha256,
                        family_id=family.family_id,
                        root_sha256=family.root_sha256,
                        public_packet_sha256=family.public_packet_sha256,
                        candidate_role=role,
                        action_id=candidate.action_id,
                        condition=condition,
                        engine=engine,
                        artifact_sha256=file_sha(output / "result.json"),
                        score=result["score"],
                        own_remaining_hp=1000.0,
                        enemy_remaining_hp=1000.0,
                        terminal=True,
                        public_contract_valid=True,
                        legal_transport_valid=True,
                    )
                    (output / "branch.json").write_text(branch.model_dump_json())
                    ownership.record_branch_result(
                        ledger,
                        claim,
                        branch,
                        artifact_hashes={p.name: file_sha(p) for p in output.iterdir()},
                    )
    report, receipt = ownership.evaluate_attempt(
        ledger,
        attempt_id=d.attempt_id,
        calibration_receipt_path=calibration,
        report_path=tmp_path / "evaluation.json",
        admission_path=tmp_path / "admission.json",
    )
    assert report.status == "passed" and receipt is not None and count == 1024
    assert (
        require_admission(
            ledger,
            tmp_path / "admission.json",
            expected_gamedata_sha256=d.gamedata_sha256,
        )
        == receipt
    )
    with pytest.raises(ValueError, match="ruleset"):
        require_admission(
            ledger,
            tmp_path / "admission.json",
            expected_gamedata_sha256=sha("other-data"),
        )
    # A copied digest cannot be reassigned to a different module role.
    impostor = tmp_path / "different-checkout/src/clasher/balance.py"
    impostor.parent.mkdir(parents=True)
    impostor.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="source path/role"):
        require_admission(
            ledger,
            tmp_path / "admission.json",
            expected_source_pins={str(impostor): file_sha(impostor)},
            expected_source_root=tmp_path / "different-checkout",
        )
    extension = _check_extension_lineage(ownership, ledger, d, tmp_path, monkeypatch)
    # A post-admission root mutation must invalidate authority too.
    root_plan = tmp_path / "capture-0/plan.json"
    original = root_plan.read_bytes()
    root_plan.write_text('{"tampered_after_admission":true}')
    with pytest.raises(ValueError, match="artifact changed"):
        require_admission(ledger, tmp_path / "admission.json")
    root_plan.write_bytes(original)
    with monkeypatch.context() as context:
        context.setattr(
            ownership,
            "_checked_calibration",
            lambda path: SimpleNamespace(
                ruleset_sha256=(sha("another-ruleset"),),
                catalog_sha256=d.catalog_sha256,
            ),
        )
        with pytest.raises(ValueError, match="different ruleset"):
            require_admission(ledger, tmp_path / "admission.json")
    (tmp_path / "branch-0000" / "terminal.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact changed"):
        require_admission(ledger, tmp_path / "admission.json")
    # Revoking the nominal base revokes every extension derived from it.
    with monkeypatch.context() as context:
        extension(context)
        with pytest.raises(ValueError, match="artifact changed"):
            require_admission(ledger, tmp_path / "extended.json")


def _development_registry(decl):
    return Path(decl.historical_registries[1])


@pytest.mark.parametrize("reuse", ["config", "episode"])
def test_separate_development_v2_ledger_blocks_fresh_reuse(tmp_path, reuse):
    fresh = declaration(tmp_path, fresh=True, attempt="fresh")
    development = _development_registry(fresh)
    old = declaration(tmp_path, attempt="dev", offset=0 if reuse == "config" else 100)
    if reuse == "episode":
        # Same source episode under a different config is still not fresh.
        old = old.model_copy(
            update={
                "episodes": (
                    old.episodes[0].model_copy(
                        update={"source_episode_id": "episode-0"}
                    ),
                )
            }
        )
    declare_attempt(development, old)
    before = file_sha(development)
    with pytest.raises(ValueError, match="already occurs in a historical registry"):
        declare_attempt(tmp_path / "fresh.sqlite", fresh)
    assert file_sha(development) == before


def test_freshness_requires_both_registry_kinds_and_readable_files(tmp_path):
    fresh = declaration(tmp_path, fresh=True)
    v7, development = map(Path, fresh.historical_registries)
    for registries in ((str(v7),), (str(development),), (str(v7), str(v7))):
        with pytest.raises(ValueError, match="both historical"):
            declare_attempt(
                tmp_path / "fresh.sqlite",
                fresh.model_copy(update={"historical_registries": registries}),
            )
    garbage = tmp_path / "garbage.sqlite"
    garbage.write_text("not a database")
    unrelated = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(unrelated) as db:
        db.execute("CREATE TABLE other(x)")
    for bad, error in (
        (tmp_path / "missing.sqlite", FileNotFoundError),
        (garbage, sqlite3.DatabaseError),
        (unrelated, ValueError),
    ):
        with pytest.raises(error):
            declare_attempt(
                tmp_path / "fresh.sqlite",
                fresh.model_copy(
                    update={
                        "historical_registries": (str(v7), str(development), str(bad))
                    }
                ),
            )
    with sqlite3.connect(tmp_path / "fresh.sqlite") as db:
        # Every rejected declaration rolled back; nothing was declared.
        assert not db.execute("SELECT name FROM sqlite_master").fetchall()


def test_own_development_ledger_excludes_only_the_current_attempt(tmp_path):
    ledger = tmp_path / "readiness-v2.sqlite"
    with _transaction(ledger):
        pass
    fresh = declaration(tmp_path, fresh=True, attempt="fresh")
    fresh = fresh.model_copy(
        update={"historical_registries": (fresh.historical_registries[0], str(ledger))}
    )
    declare_attempt(ledger, fresh)
    claim_episode(
        ledger,
        attempt_id="fresh",
        family_id="family-0",
        output_path=tmp_path / "fresh-0",
        native_attestation_sha256=fresh.native_attestation_sha256,
    )
    # A later development declaration of a fresh config is caught before capture.
    late = declaration(tmp_path, attempt="late-dev", offset=1)
    declare_attempt(ledger, late)
    with pytest.raises(ValueError, match="freshness changed"):
        claim_episode(
            ledger,
            attempt_id="fresh",
            family_id="family-1",
            output_path=tmp_path / "fresh-1",
            native_attestation_sha256=fresh.native_attestation_sha256,
        )


def test_branch_transport_audit_runs_without_holding_the_ledger_write_lock(
    tmp_path, monkeypatch
):
    # Tier A v2 failed when 9 runners queued behind multi-second transport
    # audits held inside BEGIN IMMEDIATE and exceeded the sqlite timeout.
    from types import SimpleNamespace

    from clasher.rl import readiness_capture_ownership as ownership

    ledger = tmp_path / "ledger.sqlite"
    with ownership._transaction(ledger):
        pass
    audits = []

    def check(db, claim, branch, artifact_hashes, *, audit_transport):
        if audit_transport:
            # Another writer must be able to take the write lock immediately.
            with sqlite3.connect(ledger, timeout=0) as other:
                other.execute("BEGIN IMMEDIATE")
                other.execute("ROLLBACK")
        audits.append(audit_transport)

    monkeypatch.setattr(ownership, "_check_branch_result", check)
    claim = SimpleNamespace(nonce="n-1")
    branch = SimpleNamespace(model_dump_json=lambda: "{}")
    ownership.record_branch_result(ledger, claim, branch, artifact_hashes={"a": "b"})
    assert audits == [True, False]
    with sqlite3.connect(ledger) as db:
        assert db.execute("SELECT nonce FROM branch_results").fetchall() == [("n-1",)]
    assert ownership.LEDGER_BUSY_TIMEOUT_SECONDS >= 600
