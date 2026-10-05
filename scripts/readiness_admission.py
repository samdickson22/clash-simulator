"""Declare, seal, plan, evaluate, and verify readiness ownership; never launch jobs."""

from __future__ import annotations

import argparse
from pathlib import Path

from clasher.rl.readiness_capture_ownership import (
    AttemptDeclaration,
    EpisodeSpec,
    declare_attempt,
    evaluate_attempt,
    execution_plan_for_attempt,
    extend_admission,
    require_admission,
    required_source_pins,
    seal_roots,
)
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_native_config import ConfigManifest
from clasher.rl.readiness_root_bank import RootBank
from clasher.rl.training_readiness_v2 import MechanismReview, Protocol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("prepare-declaration")
    draft.add_argument("--manifest", type=Path, required=True)
    draft.add_argument("--criteria", type=Path, required=True)
    draft.add_argument("--calibration-receipt", type=Path, required=True)
    draft.add_argument("--catalog", type=Path, required=True)
    draft.add_argument("--native-attestation-sha256", required=True)
    draft.add_argument("--historical-registry", type=Path, action="append", default=[])
    draft.add_argument("--attempt-id", required=True)
    draft.add_argument(
        "--role", choices=("fresh_acceptance", "opened_development"), required=True
    )
    draft.add_argument(
        "--technical-rerun-policy",
        choices=("none", "once_before_result"),
        default="none",
        help="pre-declared (design-hashed) rule: once_before_result permits one ledger-checked rerun of a branch claim that recorded no result because of a declared infrastructure failure",
    )
    draft.add_argument("--output", type=Path, required=True)
    declare = sub.add_parser("declare")
    declare.add_argument("--declaration", type=Path, required=True)
    seal = sub.add_parser("seal-roots")
    seal.add_argument("--attempt-id", required=True)
    seal.add_argument("--protocol", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    plan = sub.add_parser("prepare-branches")
    plan.add_argument("--attempt-id", required=True)
    plan.add_argument("--catalog", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--attempt-id", required=True)
    evaluate.add_argument("--calibration-receipt", type=Path, required=True)
    evaluate.add_argument("--report", type=Path, required=True)
    evaluate.add_argument("--admission", type=Path, required=True)
    evaluate.add_argument("--reviews", type=Path)
    extension = sub.add_parser("extend-levels")
    extension.add_argument("--base-admission", type=Path, required=True)
    extension.add_argument("--level-evidence", type=Path, required=True)
    extension.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--admission", type=Path, required=True)
    args = parser.parse_args()
    if args.command != "prepare-declaration" and args.ledger is None:
        parser.error("--ledger is required for ownership operations")
    if args.command == "prepare-declaration":
        manifest = ConfigManifest.model_validate_json(args.manifest.read_text())
        if manifest.failed_count or manifest.configured_count != len(manifest.episodes):
            raise ValueError(
                "converter failures must remain explicit; no partial declaration"
            )
        bank_path = args.manifest.parent / "root-bank.json"
        bank = RootBank.model_validate_json(bank_path.read_text())
        if (
            file_sha(bank_path) != manifest.root_bank_file_sha256
            or canonical_sha(bank.model_dump(mode="json")) != manifest.root_bank_sha256
        ):
            raise ValueError("root-bank identity differs from converter manifest")
        sources = required_source_pins()
        criteria = Protocol.model_validate_json(args.criteria.read_text())
        if criteria.families or criteria.status != "draft":
            raise ValueError("criteria input must precede root capture")
        generator = (
            Path(__file__).resolve().parents[1]
            / "src/clasher/rl/readiness_root_bank.py"
        )
        criteria = Protocol.model_validate(
            {
                **criteria.model_dump(),
                "attempt_id": args.attempt_id,
                "source_pins": sources,
                "generator_sha256": file_sha(generator),
                "config_sha256": file_sha(args.manifest),
            }
        )
        workspace = Path(__file__).resolve().parents[1] / "gamedata.json"
        inputs = [
            args.manifest,
            bank_path,
            args.criteria,
            args.calibration_receipt,
            args.catalog,
            Path(manifest.gamedata_path),
            workspace,
        ]
        episodes = []
        for entry in manifest.episodes:
            request = next(r for r in bank.requests if r.family_id == entry.family_id)
            if (
                entry.config_path is None
                or entry.config_sha256 is None
                or entry.config_file_sha256 is None
            ):
                raise ValueError("episode config is missing")
            config_path = (args.manifest.parent / entry.config_path).resolve()
            inputs.append(config_path)
            if (
                entry.root_request_sha256
                != canonical_sha(request.model_dump(mode="json"))
                or entry.source_episode_id != request.source_episode_id
                or entry.root_owner != request.root_owner
            ):
                raise ValueError(
                    "converter episode differs from prospective root request"
                )
            episodes.append(
                EpisodeSpec(
                    family_id=entry.family_id,
                    source_episode_id=entry.source_episode_id,
                    config_path=str(config_path),
                    config_file_sha256=entry.config_file_sha256,
                    config_sha256=entry.config_sha256,
                    root_request_sha256=entry.root_request_sha256,
                    root_owner=entry.root_owner,
                )
            )
        value = AttemptDeclaration(
            attempt_id=args.attempt_id,
            evidence_role=args.role,
            root_bank_sha256=manifest.root_bank_sha256,
            generator_sha256=file_sha(generator),
            converter_manifest_sha256=file_sha(args.manifest),
            pre_protocol=criteria,
            native_attestation_sha256=args.native_attestation_sha256,
            gamedata_sha256=manifest.gamedata_sha256,
            catalog_sha256=file_sha(args.catalog),
            workspace_gamedata_sha256=file_sha(workspace),
            source_pins=sources,
            input_pins={str(p.resolve()): file_sha(p) for p in inputs},
            episodes=tuple(episodes),
            historical_registries=tuple(
                str(p.resolve()) for p in args.historical_registry
            ),
            technical_rerun_policy=args.technical_rerun_policy,
        )
        with args.output.open("x") as stream:
            stream.write(value.model_dump_json(indent=2) + "\n")
    elif args.command == "declare":
        value = AttemptDeclaration.model_validate_json(args.declaration.read_text())
        print(declare_attempt(args.ledger, value))
    elif args.command == "seal-roots":
        value = seal_roots(
            args.ledger,
            attempt_id=args.attempt_id,
            protocol=Protocol.model_validate_json(args.protocol.read_text()),
        )
        with args.output.open("x") as stream:
            stream.write(value.model_dump_json(indent=2) + "\n")
    elif args.command == "prepare-branches":
        value = execution_plan_for_attempt(
            args.ledger, attempt_id=args.attempt_id, catalog_path=args.catalog
        )
        with args.output.open("x") as stream:
            stream.write(value.model_dump_json(indent=2) + "\n")
    elif args.command == "evaluate":
        reviews = (
            ()
            if args.reviews is None
            else tuple(
                MechanismReview.model_validate_json(row)
                for row in args.reviews.read_text().splitlines()
                if row.strip()
            )
        )
        report, admission = evaluate_attempt(
            args.ledger,
            attempt_id=args.attempt_id,
            calibration_receipt_path=args.calibration_receipt,
            report_path=args.report,
            admission_path=args.admission,
            reviews=reviews,
        )
        print(
            report.status,
            "admission issued" if admission is not None else "no admission",
        )
    elif args.command == "extend-levels":
        receipt = extend_admission(
            args.ledger,
            base_receipt_path=args.base_admission,
            extension_receipt_path=args.level_evidence,
            output_path=args.output,
        )
        print(receipt.levels, receipt.level_sampling_scope)
    else:
        receipt = require_admission(args.ledger, args.admission)
        print(receipt.attempt_id, receipt.training_scope)


if __name__ == "__main__":
    main()
