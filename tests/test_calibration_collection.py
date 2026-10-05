"""Prospective collection must bind source, configuration, role and first attempt."""

import hashlib
import json

import pytest

from clasher.rl.calibration_collection import (
    collection_sources,
    verify_collection_protocol,
)
from clasher.rl.calibration_families import (
    FamilyExposure,
    claim_acceptance_collection,
    record_exposure,
    register_family,
)
from clasher.rl.native_match_registry import canonical_digest


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def frozen(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src/clasher").mkdir(parents=True)
    (workspace / "src/clasher/example.py").write_text("value = 1\n")
    (workspace / "scripts").mkdir()
    for p in collection_sources(workspace):
        if not p.exists():
            p.write_text("# frozen producer\n")
    rules = tmp_path / "rules.json"
    rules.write_text("{}")
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("Name\n")
    config = {"rndSeed": 91, "battle": {"deck0": [1, 2], "deck1": [3, 4]}}
    documents = {
        "family_manifest": {
            "status": "frozen",
            "families": [
                {
                    "family_id": "f",
                    "root_selection_start_tick": 900,
                    "configurations": [
                        {
                            "config": config,
                            "root_id": "native-root-v1:" + canonical_digest(config),
                            "decks": [["Knight"], ["Knight"]],
                        }
                    ],
                }
            ],
        },
        "reference_criteria": {
            "status": "frozen",
            "source_domain": "pinned-native-reference",
            "verifier": "public-reference-v1",
            "ruleset_sha256": digest(rules),
            "cards": ["Knight"],
            "level": 11,
            "base_forms_only": True,
            "metadata_version": 4,
            "maximum_entities": 128,
            "maximum_failures": 0,
            "camera_calibrated": False,
        },
        "decision_criteria": {
            "status": "frozen",
            "criteria": {
                "minimum_families": 1,
                "confidence": 0.5,
                "maximum_bad_family_rate": 0.6,
                "hp_regret_tolerance": 81.0,
                "minimum_clear_improvement_families": 1,
            },
            "baseline": "recorded",
            "selected_tie_rule": "worst-native-outcome",
            "missing_root_rule": "family-failure-no-substitution",
            "maximum_bad_families": 0,
            "maximum_regression_families": 0,
        },
    }
    for name, data in documents.items():
        (tmp_path / (name + ".json")).write_text(json.dumps(data))
    protocol = {
        "schema_version": 1,
        "status": "frozen",
        "source_domain": "pinned-native-reference",
        "game_build": "15.535.86",
        "ruleset_sha256": digest(rules),
        "catalog_sha256": digest(catalog),
        "native_attestation_sha256": "e" * 64,
        "family_manifest_path": "family_manifest.json",
        "family_manifest_sha256": digest(tmp_path / "family_manifest.json"),
        "reference_criteria_path": "reference_criteria.json",
        "reference_criteria_sha256": digest(tmp_path / "reference_criteria.json"),
        "decision_criteria_path": "decision_criteria.json",
        "decision_criteria_sha256": digest(tmp_path / "decision_criteria.json"),
        "source_files": {
            str(p.relative_to(workspace)): digest(p)
            for p in collection_sources(workspace)
        },
        "families": {"f": [canonical_digest(config)]},
        "public_opponent_seat": 0,
        "public_opponent_style": "balanced",
        "decision_stride": 30,
        "command_delay": 1,
        "startup_wait_ticks": 90,
        "max_tick": 6001,
        "root_start_ticks": {canonical_digest(config): 900},
        "branch_window_ticks": 300,
        "branch_response_seed": 1311600,
        "branch_other_style": "pressure",
        "branch_x_offsets": [-1, 1],
        "branch_include_delay_one": True,
        "collection_only": True,
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    registry = tmp_path / "registry.sqlite"
    family = register_family(
        registry,
        [config],
        family_id="f",
        role="acceptance",
        protocol_sha256=digest(path),
    )
    args = {
        "workspace": workspace,
        "registry": registry,
        "family_id": "f",
        "config": config,
        "gamedata": rules,
        "catalog": catalog,
        "opponent_seat": 0,
        "opponent_style": "balanced",
    }
    return path, args, family


def test_exact_frozen_inputs_pass_without_opening_outcomes(frozen):
    path, args, family = frozen
    _, result, sha = verify_collection_protocol(path, **args)
    assert result == family and sha == digest(path)
    assert verify_collection_protocol(path, **args)[1] == family


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "added_source",
        "rules",
        "catalog",
        "seed",
        "controller",
        "opened",
        "protocol",
    ],
)
def test_drift_or_exposure_rejected(frozen, fault):
    path, args, _ = frozen
    if fault == "source":
        (args["workspace"] / "src/clasher/example.py").write_text("value = 2\n")
    elif fault == "added_source":
        (args["workspace"] / "src/clasher/new.py").write_text("")
    elif fault in ("rules", "catalog"):
        args["gamedata" if fault == "rules" else "catalog"].write_text("changed")
    elif fault == "seed":
        args["config"]["rndSeed"] = 92
    elif fault == "controller":
        args["opponent_style"] = "pressure"
    elif fault == "opened":
        record_exposure(
            args["registry"],
            FamilyExposure(family_id="f", purpose="repair", evidence_sha256="d" * 64),
        )
    else:
        data = json.loads(path.read_text())
        data["decision_criteria_sha256"] = "d" * 64
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_collection_protocol(path, **args)


def test_attempt_cannot_be_replaced_even_if_no_result_written(frozen, tmp_path):
    path, args, family = frozen
    claim = {
        "family_id": "f",
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(path),
        "output_path": tmp_path / "first",
    }
    claim_acceptance_collection(args["registry"], **claim)
    claim["output_path"] = tmp_path / "second"
    with pytest.raises(ValueError, match="already attempted"):
        claim_acceptance_collection(args["registry"], **claim)


def test_exposure_race_is_rechecked_when_claiming(frozen, tmp_path):
    path, args, family = frozen
    verify_collection_protocol(path, **args)
    record_exposure(
        args["registry"],
        FamilyExposure(family_id="f", purpose="evaluation", evidence_sha256="d" * 64),
    )
    with pytest.raises(ValueError, match="opened"):
        claim_acceptance_collection(
            args["registry"],
            family_id="f",
            root_id=family.root_ids[0],
            protocol_sha256=digest(path),
            output_path=tmp_path / "capture",
        )


@pytest.mark.parametrize(
    "fault",
    [
        "draft",
        "reference_failure_budget",
        "sample_size",
        "root_digest",
        "unsupported_deck",
    ],
)
def test_document_content_is_validated_even_when_rehashed(frozen, fault):
    from clasher.rl.calibration_collection import (
        FrozenCollectionProtocol,
        verify_protocol_documents,
    )

    path, _, _ = frozen
    protocol = FrozenCollectionProtocol.model_validate_json(path.read_bytes())
    kind = (
        "family_manifest"
        if fault in ("root_digest", "unsupported_deck")
        else (
            "reference_criteria"
            if fault == "reference_failure_budget"
            else "decision_criteria"
        )
    )
    document = path.parent / getattr(protocol, kind + "_path")
    data = json.loads(document.read_text())
    if fault == "draft":
        data["status"] = "draft"
    elif fault == "reference_failure_budget":
        data["maximum_failures"] = 1
    elif fault == "sample_size":
        data["criteria"]["minimum_families"] = 64
    elif fault == "root_digest":
        data["families"][0]["configurations"][0]["config"]["rndSeed"] = 92
    else:
        data["families"][0]["configurations"][0]["decks"][0] = ["UnsupportedCard"]
    document.write_text(json.dumps(data))
    protocol = protocol.model_copy(update={kind + "_sha256": digest(document)})
    with pytest.raises(ValueError):
        verify_protocol_documents(protocol, path.parent)


def test_branch_source_must_match_original_claimed_path(frozen, tmp_path):
    from clasher.rl.calibration_families import require_collection_claim

    path, args, family = frozen
    capture = tmp_path / "original"
    capture.mkdir()
    binding = {
        "family_id": "f",
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(path),
    }
    claim_acceptance_collection(args["registry"], **binding, output_path=capture)
    require_collection_claim(args["registry"], **binding, capture_path=capture)
    with pytest.raises(ValueError, match="collection claim"):
        require_collection_claim(
            args["registry"], **binding, capture_path=tmp_path / "copy"
        )


def test_branch_attempts_are_atomic_and_cannot_be_replaced(frozen, tmp_path):
    import sqlite3

    from clasher.rl.calibration_families import claim_acceptance_branches

    path, args, family = frozen
    base = {
        "family_id": "f",
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(path),
    }
    claim_acceptance_collection(
        args["registry"], **base, output_path=tmp_path / "capture"
    )
    branch = base | {
        "branch_protocol_sha256": "e" * 64,
        "output_path": tmp_path / "branches",
    }
    claim_acceptance_branches(args["registry"], **branch, attempts=[("wait", "native")])
    with pytest.raises(ValueError, match="already attempted"):
        claim_acceptance_branches(
            args["registry"],
            **branch,
            attempts=[("recorded", "native"), ("wait", "native")],
        )
    with sqlite3.connect(args["registry"]) as db:
        assert db.execute(
            "SELECT candidate,engine FROM calibration_branches"
        ).fetchall() == [("wait", "native")]
    claim_acceptance_branches(args["registry"], **branch, attempts=[("wait", "scalar")])
    branch["branch_protocol_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="protocol changed"):
        claim_acceptance_branches(
            args["registry"], **branch, attempts=[("recorded", "scalar")]
        )


@pytest.fixture(params=["collection", "branches"])
def reserved_directory(frozen, tmp_path, request):
    from clasher.rl.calibration_families import (
        claim_acceptance_branches,
        require_branch_claims,
        require_collection_claim,
    )

    protocol, args, family = frozen
    registry = args["registry"]
    original = tmp_path / "original"
    binding = {
        "family_id": family.family_id,
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(protocol),
    }
    # Reservations are valid before the producer creates any output.
    claim_acceptance_collection(registry, **binding, output_path=original)
    if request.param == "branches":
        binding |= {
            "branch_protocol_sha256": "e" * 64,
            "attempts": [("wait", "native"), ("wait", "scalar")],
        }
        claim_acceptance_branches(registry, **binding, output_path=original)

    def verify(directory, **overrides):
        if request.param == "collection":
            require_collection_claim(
                registry, **(binding | overrides), capture_path=directory
            )
        else:
            require_branch_claims(
                registry, **(binding | overrides), output_path=directory
            )

    return original, registry, verify


def test_claim_follows_relocation_without_rewriting_ledger(reserved_directory, tmp_path):
    original, registry, verify = reserved_directory
    original.mkdir()
    (original / "artifact.json").write_text("{}")
    before = registry.read_bytes()
    verify(original)
    relocated = tmp_path / "relocated"
    original.rename(relocated)
    original.symlink_to(relocated.name, target_is_directory=True)
    alias = tmp_path / "alias"
    alias.symlink_to(original.name, target_is_directory=True)
    for directory in (original, relocated, alias):
        verify(directory)
    assert registry.read_bytes() == before


@pytest.mark.parametrize(
    "fault",
    [
        "copy",
        "unrelated_symlink",
        "missing",
        "missing_supplied",
        "dangling",
        "missing_original",
        "symlink_loop",
        "file",
    ],
)
def test_claim_rejects_unbound_or_unavailable_directory(
    reserved_directory, tmp_path, fault
):
    import shutil

    original, _, verify = reserved_directory
    supplied = original
    if fault in ("copy", "unrelated_symlink"):
        original.mkdir()
        (original / "artifact.json").write_text("{}")
        supplied = tmp_path / "copy"
        shutil.copytree(original, supplied)
        if fault == "unrelated_symlink":
            alias = tmp_path / "alias"
            alias.symlink_to(supplied, target_is_directory=True)
            supplied = alias
    elif fault == "missing_supplied":
        original.mkdir()
        supplied = tmp_path / "missing"
    elif fault == "dangling":
        supplied = tmp_path / "missing-target"
        original.symlink_to(supplied, target_is_directory=True)
    elif fault == "missing_original":
        original.mkdir()
        supplied = tmp_path / "relocated"
        original.rename(supplied)
    elif fault == "symlink_loop":
        original.symlink_to(original.name, target_is_directory=True)
    elif fault == "file":
        original.write_text("not a directory")
    with pytest.raises(ValueError, match="claim|reserved attempts"):
        verify(supplied)


@pytest.mark.parametrize(
    "override",
    [
        {"family_id": "different"},
        {"root_id": "native-root-v1:" + "f" * 64},
        {"protocol_sha256": "f" * 64},
    ],
)
def test_relocation_preserves_claim_metadata(reserved_directory, tmp_path, override):
    original, _, verify = reserved_directory
    relocated = tmp_path / "relocated"
    relocated.mkdir()
    original.symlink_to(relocated, target_is_directory=True)
    with pytest.raises(ValueError, match="claim|reserved attempts"):
        verify(relocated, **override)


@pytest.mark.parametrize(
    "override",
    [
        {"branch_protocol_sha256": "f" * 64},
        {"attempts": [("other-candidate", "native")]},
        {"attempts": [("wait", "other-engine")]},
        {"attempts": [("wait", "native"), ("unreserved", "scalar")]},
    ],
)
def test_relocation_preserves_branch_bindings(frozen, tmp_path, override):
    from clasher.rl.calibration_families import (
        claim_acceptance_branches,
        require_branch_claims,
    )

    protocol, args, family = frozen
    binding = {
        "family_id": family.family_id,
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(protocol),
    }
    original = tmp_path / "original"
    claim_acceptance_collection(args["registry"], **binding, output_path=original)
    binding |= {
        "branch_protocol_sha256": "e" * 64,
        "attempts": [("wait", "native")],
    }
    claim_acceptance_branches(args["registry"], **binding, output_path=original)
    relocated = tmp_path / "relocated"
    relocated.mkdir()
    original.symlink_to(relocated, target_is_directory=True)
    with pytest.raises(ValueError, match="reserved attempts"):
        require_branch_claims(
            args["registry"], **(binding | override), output_path=relocated
        )


def test_exposed_family_cannot_start_branches(frozen, tmp_path):
    from clasher.rl.calibration_families import claim_acceptance_branches

    path, args, family = frozen
    base = {
        "family_id": "f",
        "root_id": family.root_ids[0],
        "protocol_sha256": digest(path),
    }
    claim_acceptance_collection(
        args["registry"], **base, output_path=tmp_path / "capture"
    )
    record_exposure(
        args["registry"],
        FamilyExposure(family_id="f", purpose="repair", evidence_sha256="d" * 64),
    )
    with pytest.raises(ValueError, match="opened"):
        claim_acceptance_branches(
            args["registry"],
            **base,
            branch_protocol_sha256="e" * 64,
            attempts=[("wait", "native")],
            output_path=tmp_path / "branches",
        )


def test_whole_cohort_exposure_is_atomic(frozen):
    import sqlite3

    from clasher.rl.calibration_families import claim_acceptance_evaluation

    path, args, family = frozen
    families = {"f": family.root_ids, "missing": ("native-root-v1:" + "f" * 64,)}
    with pytest.raises(ValueError, match="not registered"):
        claim_acceptance_evaluation(
            args["registry"],
            families=families,
            protocol_sha256=digest(path),
            evidence_sha256="e" * 64,
        )
    with sqlite3.connect(args["registry"]) as db:
        assert (
            db.execute("SELECT COUNT(*) FROM calibration_exposures").fetchone()[0] == 0
        )
    families.pop("missing")
    claim_acceptance_evaluation(
        args["registry"],
        families=families,
        protocol_sha256=digest(path),
        evidence_sha256="e" * 64,
    )
    with pytest.raises(ValueError, match="already been opened"):
        claim_acceptance_evaluation(
            args["registry"],
            families=families,
            protocol_sha256=digest(path),
            evidence_sha256="f" * 64,
        )


def test_event_sampling_requires_complete_seeded_playable_windows(frozen):
    from clasher.rl.calibration_collection import FrozenCollectionProtocol

    path, args, _ = frozen
    data = json.loads(path.read_text())
    key = canonical_digest(args["config"])
    data.update(
        root_selection_mode="seeded-play-event",
        root_start_ticks={key: 90},
        root_event_seeds={key: 77},
        branch_window_ticks=5910,
    )
    assert (
        FrozenCollectionProtocol.model_validate_json(json.dumps(data)).root_event_seeds[
            key
        ]
        == 77
    )
    for change in (
        {"root_event_seeds": {}},
        {"branch_window_ticks": 300},
        {"root_start_ticks": {key: 900}},
    ):
        with pytest.raises(ValueError, match="event sampling"):
            FrozenCollectionProtocol.model_validate_json(json.dumps(data | change))
