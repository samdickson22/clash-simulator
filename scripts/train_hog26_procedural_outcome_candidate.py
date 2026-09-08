#!/usr/bin/env python3
"""Train the exact primary candidate declared by the procedural protocol."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from scripts.collect_hog26_direct_simple_behavior import file_sha256
from scripts.run_hog26_procedural_outcome_shard import load_protocol


def require_current_audit(corpus: Path, report_path: Path) -> dict[str, Any]:
    """Require a successful audit of these exact corpus bytes, not just a file."""
    report = json.loads(report_path.read_text())
    checks = report.get("checks", {})
    if (
        report.get("schema") != "clasher.hog26.outcome-corpus-audit.v1"
        or report.get("status") != "passed"
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise ValueError(f"outcome audit did not pass: {report_path}")
    matches = [
        row
        for row in report.get("corpora", [])
        if Path(row["path"]).resolve() == corpus.resolve()
    ]
    if len(matches) != 1 or matches[0].get("sha256") != file_sha256(corpus):
        raise ValueError(f"outcome audit is missing or stale for: {corpus}")
    return matches[0]


def validate_training_inputs(protocol: dict[str, Any], *, root: Path) -> None:
    readiness = protocol.get("training_readiness", {})
    if readiness.get("status") != "ready" or readiness.get("blocking_issues") != []:
        raise ValueError(
            "candidate training is not cleared by the reassessed protocol: "
            f"{readiness.get('blocking_issues', ['protocol reassessment missing'])}"
        )
    stages = [
        *protocol["training"],
        protocol["development_selection"],
        protocol["probability_calibration"],
    ]
    families = (
        [set(protocol["training"][0]["family_ids"])]
        + [
            set(protocol[key]["family_ids"])
            for key in ("development_selection", "probability_calibration")
        ]
        + [set(protocol["final_holdout"]["generated"]["family_ids"])]
    )
    if any(a & b for i, a in enumerate(families) for b in families[i + 1 :]):
        raise ValueError("procedural family roles overlap")
    if any(set(row["family_ids"]) != families[0] for row in protocol["training"]):
        raise ValueError("training shards disagree on family membership")
    from scripts.audit_hog26_procedural_outcome_shard import shard_expectations

    paths = []
    for stage in stages:
        corpus = root / stage["output_corpus"]
        audited = require_current_audit(corpus, root / stage["audit_report"])
        if (
            audited["seed"] != stage["seed"]
            or audited["episodes"] != stage["expected_games"]
        ):
            raise ValueError("audited corpus differs from stage seed/game budget")
        expected = shard_expectations(protocol, stage, root=root)
        with np.load(corpus, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata_json"]))
        if (
            set(metadata["opponents"]) != expected["expected_opponents"]
            or set(metadata["opponent_decks"]) != expected["expected_decks"]
            or metadata["supported_decks_sha256"]
            != expected["expected_supported_decks_sha256"]
            or metadata["opponent_deck_split"] != expected["expected_split"]
            or metadata["checkpoint_sha256"] != protocol["base_policy"]["sha256"]
        ):
            raise ValueError(
                "audited corpus differs from protocol collection authority"
            )
        paths.append(corpus)
    data = protocol["primary_candidate_data"]
    legacy = [*data["legacy_training_corpora"], data["validation_corpora"][1]]
    for path in legacy:
        corpus = root / path
        require_current_audit(corpus, root / data["legacy_audit_reports"][path])
        paths.append(corpus)
    forbidden = set(protocol["opponent_generalization"]["head_held_out_styles"])
    for corpus in paths:
        with np.load(corpus, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata_json"]))
            styles = np.asarray(metadata["opponents"])[
                archive["episode_opponent_indices"]
            ]
        if forbidden.intersection(styles.tolist()):
            raise ValueError(
                f"held-out opponent appears in outcome-head fitting: {corpus}"
            )


def training_command(
    protocol: dict[str, Any],
    *,
    root: Path,
    device: str,
    protocol_path: Path | None = None,
) -> list[str]:
    candidate = protocol["primary_candidate"]
    data = protocol["primary_candidate_data"]
    training_rows = protocol["training"]
    train_corpora = [
        *(root / path for path in data["legacy_training_corpora"]),
        *(root / row["output_corpus"] for row in training_rows),
    ]
    validation_corpora = [
        root / protocol["development_selection"]["output_corpus"],
        root / data["validation_corpora"][1],
    ]
    calibration_corpora = [root / protocol["probability_calibration"]["output_corpus"]]
    command = [
        sys.executable,
        str(root / "scripts" / "train_hog26_actor_outcome.py"),
        "--base-checkpoint",
        str(root / protocol["base_policy"]["path"]),
    ]
    if "generalization_evaluation" in protocol:
        if protocol_path is None:
            raise ValueError(
                "reassessed candidate requires its generalization protocol path"
            )
        command.extend(("--generalization-protocol", str(protocol_path.resolve())))
    for corpus in train_corpora:
        command.extend(("--train-corpus", str(corpus)))
    for corpus in validation_corpora:
        command.extend(("--validation-corpus", str(corpus)))
    for corpus in calibration_corpora:
        command.extend(("--calibration-corpus", str(corpus)))
    class_mass = candidate["target_class_mass_loss_draw_win"]
    gates = protocol["gates"]
    command.extend(
        (
            "--output-checkpoint",
            str(root / candidate["output_checkpoint"]),
            "--report",
            str(root / candidate["output_report"]),
            "--seed",
            str(candidate["seed"]),
            "--device",
            device,
            "--epochs",
            str(candidate["epochs"]),
            "--batch-size",
            str(candidate["batch_size"]),
            "--sequence-steps",
            str(candidate["sequence_steps"]),
            "--hidden-size",
            str(candidate["hidden_size"]),
            "--feature-set",
            str(candidate["feature_set"]),
            "--structured-residual-scale",
            str(candidate["structured_residual_scale"]),
            "--margin-residual-scale",
            str(candidate["margin_residual_scale"]),
            "--margin-feature-set",
            str(candidate["margin_feature_set"]),
            "--margin-progress-power",
            str(candidate["margin_progress_power"]),
            "--learning-rate",
            str(candidate["learning_rate"]),
            "--margin-coefficient",
            str(candidate["margin_coefficient"]),
            "--loss-class-mass",
            str(class_mass[0]),
            "--draw-class-mass",
            str(class_mass[1]),
            "--win-class-mass",
            str(class_mass[2]),
            "--minimum-nll-improvement",
            str(gates["minimum_nll_improvement"]),
            "--maximum-ece",
            str(gates["maximum_ece"]),
            "--minimum-natural-auc",
            str(gates["minimum_natural_auc"]),
            "--minimum-natural-phase-auc",
            str(gates["minimum_natural_phase_auc"]),
            "--minimum-controlled-draw-auc",
            str(gates["minimum_controlled_draw_auc"]),
            "--minimum-controlled-draw-endpoint-probability-lift",
            str(gates["minimum_controlled_draw_endpoint_probability_lift"]),
            "--maximum-natural-draw-probability",
            str(gates["maximum_natural_draw_probability"]),
            "--maximum-margin-mae",
            str(gates["maximum_margin_mae"]),
            "--minimum-margin-mae-improvement",
            str(gates["minimum_margin_mae_improvement"]),
            "--maximum-phase-margin-mae-regression",
            str(gates["maximum_phase_margin_mae_regression"]),
            "--minimum-phase-auc-lower-bound",
            str(gates["minimum_phase_auc_lower_95"]),
            "--phase-auc-bootstrap-replicates",
            str(gates["cluster_bootstrap_replicates"]),
            "--minimum-phase-bootstrap-clusters",
            str(gates["minimum_clusters_per_phase"]),
            "--phase-balanced-outcome-training",
            "--phase-balanced-margin-training",
            "--require-disjoint-natural-decks",
        )
    )
    return command


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol = load_protocol(args.protocol, root)
    command = training_command(
        protocol, root=root, device=args.device, protocol_path=args.protocol
    )
    required = [
        Path(command[index + 1])
        for index, value in enumerate(command)
        if value in {"--train-corpus", "--validation-corpus", "--calibration-corpus"}
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"candidate corpora are incomplete: {missing}")
    validate_training_inputs(protocol, root=root)
    subprocess.run(command, cwd=root, check=True)
    report_path = root / protocol["primary_candidate"]["output_report"]
    report = json.loads(report_path.read_text())
    if report.get("holdout_corpora") != []:
        raise RuntimeError("primary candidate accessed a holdout corpus")
    if "generalization_evaluation" in protocol and (
        report.get("generalization_protocol_sha256") != file_sha256(args.protocol)
        or report.get("validation_public_slices", {}).get("passed") is not True
        or report.get("calibration_timing")
        != "once-after-outcome-and-margin-epoch-selection-v1"
    ):
        raise RuntimeError("candidate lacks protocol-bound public-slice acceptance")
    print(json.dumps({"status": report.get("status"), "report": str(report_path)}))


if __name__ == "__main__":
    main()
