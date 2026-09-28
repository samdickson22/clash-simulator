"""Verify and evaluate a complete frozen reference cohort without training a policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

import numpy as np
from audit_native_public_boundary import audit_capture
from prepare_prospective_branch import prepare
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from clasher.rl.calibration_artifacts import artifact_digest, read_branch_evidence
from clasher.rl.calibration_collection import (
    FrozenCollectionProtocol,
    collection_sources,
    verify_protocol_documents,
)
from clasher.rl.calibration_decisions import CandidatePair, DecisionRoot
from clasher.rl.calibration_evaluation import RootAssessment, evaluate_family_metrics
from clasher.rl.calibration_families import (
    claim_acceptance_evaluation,
    require_branch_claims,
    require_unopened_acceptance,
)
from clasher.rl.native_match_registry import canonical_digest
from clasher.rl.native_public_observation import NativeProjectileCatalog
from clasher.rl.public_match_archive import load_match_archive


class BranchBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1)
    engines: tuple[Literal["native", "scalar"], ...] = Field(min_length=1)


class ExecutionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    capture: str = Field(min_length=1)
    branches: tuple[BranchBatch, ...] = ()


def utility(result, owner):
    terminal = result["terminal"]
    winner = terminal["winner"]
    if winner is not None and (type(winner) is not int or winner not in (0, 1)):
        raise ValueError("invalid terminal winner")
    if type(terminal["tick"]) is not int or not 90 <= terminal["tick"] <= 6001:
        raise ValueError("invalid playable terminal tick")
    margin = 0.0
    for tower in terminal["towers"]:
        hp = tower["hp"]
        team = tower["owner"]
        if (
            type(hp) not in (int, float)
            or not np.isfinite(hp)
            or hp < 0
            or type(team) is not int
            or team not in (0, 1)
        ):
            raise ValueError("invalid terminal Crown health")
        margin += hp if team == owner else -hp
    return (0 if winner is None else (1 if winner == owner else -1)), margin


def verify_archives(capture):
    for owner in (0, 1):
        path = capture / f"seat{owner}"
        with np.load(path / "observations.npz", allow_pickle=False) as arrays:
            tokens = tuple(json.loads(str(arrays["metadata"].item()))["token_names"])
        receipt, _, _, _ = load_match_archive(
            path,
            token_names=tokens,
            source_path=capture / "result.json",
            ruleset_path=capture / "gamedata.json",
            producer_path=capture / "producer-source.zip",
        )
        if (
            receipt.provenance.role != "acceptance"
            or receipt.provenance.opened_for_development
            or receipt.provenance.coverage != "complete"
        ):
            raise ValueError("archive is not a complete prospective reference match")


def evaluate(protocol_path, registry, index_path, catalog_path, workspace):
    protocol = FrozenCollectionProtocol.model_validate_json(protocol_path.read_bytes())
    protocol_sha = artifact_digest(protocol_path)
    reference, decision = verify_protocol_documents(protocol, protocol_path.parent)
    source_names = {
        str(p.relative_to(workspace)) for p in collection_sources(workspace)
    }
    if set(protocol.source_files) != source_names or any(
        artifact_digest(workspace / name) != sha
        for name, sha in protocol.source_files.items()
    ):
        raise ValueError("evaluation producer differs from frozen protocol")
    catalog = NativeProjectileCatalog.from_csv(
        catalog_path, expected_sha256=protocol.catalog_sha256
    )
    index_bytes = index_path.read_bytes()
    parsed_index = TypeAdapter(dict[str, ExecutionEntry]).validate_json(index_bytes)
    index = {key: value.model_dump(mode="json") for key, value in parsed_index.items()}
    declared = {
        config: family
        for family, configs in protocol.families.items()
        for config in configs
    }
    if set(index) - set(declared):
        raise ValueError("execution index contains undeclared configurations")
    cohort = {
        f: tuple("native-root-v1:" + c for c in configs)
        for f, configs in protocol.families.items()
    }
    for family in cohort:
        require_unopened_acceptance(registry, family, protocol_sha)
    # Candidate preparation is fixed computation on the recorded public action
    # sequence. No terminal utilities are read or ranked during this phase.
    prepared = {}
    public_errors = {}
    branch_errors = {}
    artifacts = {str(catalog_path): protocol.catalog_sha256}
    for kind in ("family_manifest", "reference_criteria", "decision_criteria"):
        document = protocol_path.parent / getattr(protocol, kind + "_path")
        artifacts[str(document)] = getattr(protocol, kind + "_sha256")
    for config, family in declared.items():
        public_errors[config] = []
        branch_errors[config] = []
        if config not in index:
            public_errors[config].append("missing configuration in execution index")
            continue
        entry = index[config]
        capture = Path(entry["capture"])
        try:
            prepared[config] = prepare(
                capture, protocol_path, registry, family, catalog_path, workspace
            )
            artifacts[str(capture / "artifact-receipt.json")] = artifact_digest(
                capture / "artifact-receipt.json"
            )
        except (ValueError, KeyError, OSError, AssertionError) as error:
            public_errors[config].append("capture/preparation: " + str(error))
        for batch in entry.get("branches", []):
            receipt = Path(batch["path"]) / "artifact-receipt.json"
            if receipt.exists():
                artifacts[str(receipt)] = artifact_digest(receipt)
    snapshot = {
        "protocol": protocol_sha,
        "execution_index": hashlib.sha256(index_bytes).hexdigest(),
        "artifact_receipts": artifacts,
    }
    claim_acceptance_evaluation(
        registry,
        families=cohort,
        protocol_sha256=protocol_sha,
        evidence_sha256=canonical_digest(snapshot),
    )
    assessments = []
    for config, family in declared.items():
        decision_root = None
        if config in prepared:
            entry = index[config]
            capture = Path(entry["capture"])
            branch_protocol = prepared[config]
            try:
                verify_archives(capture)
                audit = audit_capture(capture, catalog)
                if (
                    audit["errors"]
                    or not audit["sources_unchanged"]
                    or audit["paired_frames_passed"] == 0
                    or audit.get("hidden_deck_independent_vocabulary") is not True
                ):
                    raise ValueError("public reference audit failed or empty")
            except (ValueError, KeyError, OSError, AssertionError) as error:
                public_errors[config].append(str(error))
            results = {}
            try:
                for batch in entry.get("branches", []):
                    directory = Path(batch["path"])
                    engines = tuple(batch["engines"])
                    require_branch_claims(
                        registry,
                        family_id=family,
                        root_id="native-root-v1:" + config,
                        protocol_sha256=protocol_sha,
                        branch_protocol_sha256=canonical_digest(branch_protocol),
                        attempts=[
                            (c["name"], e)
                            for c in branch_protocol["candidates"]
                            for e in engines
                        ],
                        output_path=directory,
                    )
                    values = read_branch_evidence(
                        directory,
                        protocol=branch_protocol,
                        engines=engines,
                        protocol_sha256=protocol_sha,
                    )
                    provenance = json.loads((directory / "provenance.json").read_text())
                    branch_scripts = {
                        "compare_reacting_public_branches.py",
                        "prepare_prospective_branch.py",
                        "select_reacting_public_root.py",
                        "collect_public_development_games.py",
                        "read_native_public_levels.py",
                        "smoke_reference_battle.py",
                    }
                    expected_sources = {
                        name: sha
                        for name, sha in protocol.source_files.items()
                        if name.startswith("src/clasher/")
                        or Path(name).name in branch_scripts
                    }
                    if provenance["sources"] != expected_sources:
                        raise ValueError(
                            "branch producer inventory differs from frozen sources"
                        )
                    for name, sha in provenance["sources"].items():
                        if (
                            protocol.source_files.get(name) != sha
                            or artifact_digest(workspace / name) != sha
                        ):
                            raise ValueError(
                                "branch producer not bound to frozen source"
                            )
                    for name, sha in provenance["inputs"].items():
                        if artifact_digest(Path(name)) != sha:
                            raise ValueError("branch input changed")
                    for value in values:
                        if (
                            value["engine"] == "native"
                            and value.get("native_attestation_sha256")
                            != protocol.native_attestation_sha256
                        ):
                            raise ValueError(
                                "native branch runtime differs from frozen attestation"
                            )
                        key = value["candidate"], value["engine"]
                        if key in results:
                            raise ValueError("duplicate branch across batches")
                        results[key] = value
                expected = {
                    (c["name"], e)
                    for c in branch_protocol["candidates"]
                    for e in ("native", "scalar")
                }
                if set(results) != expected:
                    raise ValueError("missing declared native/scalar branch pair")
                pairs = []
                for c in branch_protocol["candidates"]:
                    nu = utility(results[c["name"], "native"], branch_protocol["owner"])
                    su = utility(results[c["name"], "scalar"], branch_protocol["owner"])
                    pairs.append(
                        CandidatePair(
                            name=c["name"],
                            native_outcome=nu[0],
                            native_hp_margin=nu[1],
                            scalar_outcome=su[0],
                            scalar_hp_margin=su[1],
                        )
                    )
                decision_root = DecisionRoot(
                    root_id="native-root-v1:" + config,
                    family_id=family,
                    baseline="recorded",
                    expected_candidates=tuple(
                        c["name"] for c in branch_protocol["candidates"]
                    ),
                    candidates=tuple(pairs),
                )
            except (ValueError, KeyError, OSError, AssertionError) as error:
                branch_errors[config].append(str(error))
        assessments.append(
            RootAssessment(
                family_id=family,
                config_sha256=config,
                decision=decision_root,
                public_errors=tuple(public_errors[config]),
                branch_errors=tuple(branch_errors[config]),
            )
        )
    report = evaluate_family_metrics(protocol.families, assessments, decision.criteria)
    stable = (
        artifact_digest(protocol_path) == snapshot["protocol"]
        and artifact_digest(index_path) == snapshot["execution_index"]
        and all(artifact_digest(Path(p)) == sha for p, sha in artifacts.items())
        and all(
            artifact_digest(workspace / p) == sha
            for p, sha in protocol.source_files.items()
        )
    )
    report.update(
        role="prospective reference evaluation",
        evidence_snapshot=snapshot,
        sources_unchanged=stable,
        acceptance_passed=report["metrics_passed"] and stable,
        training_authorized=False,
        scope=reference.model_dump(),
        admission_note="Acceptance concerns this frozen native-reference state/ranking scope only. Training still requires compatible data and the separate stage-specific prerequisites; no camera or human-strength claim.",
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ("protocol", "registry", "index", "catalog", "output"):
        p.add_argument("--" + option, type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("evaluation output already exists")
    result = evaluate(
        args.protocol, args.registry, args.index, args.catalog, Path.cwd()
    )
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    print(
        "Reference acceptance",
        result["acceptance_passed"],
        "families",
        result["family_count"],
    )


if __name__ == "__main__":
    main()
