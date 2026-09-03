#!/usr/bin/env python3
"""Train the exact primary candidate declared by the procedural protocol."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.run_hog26_procedural_outcome_shard import load_protocol


def training_command(
    protocol: dict[str, Any], *, root: Path, device: str
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
    calibration_corpora = [
        root / protocol["probability_calibration"]["output_corpus"]
    ]
    command = [
        sys.executable,
        str(root / "scripts" / "train_hog26_actor_outcome.py"),
        "--base-checkpoint",
        str(root / protocol["base_policy"]["path"]),
    ]
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
    command = training_command(protocol, root=root, device=args.device)
    required = [Path(command[index + 1]) for index, value in enumerate(command) if value in {"--train-corpus", "--validation-corpus", "--calibration-corpus"}]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"candidate corpora are incomplete: {missing}")
    subprocess.run(command, cwd=root, check=True)
    report_path = root / protocol["primary_candidate"]["output_report"]
    report = json.loads(report_path.read_text())
    if report.get("holdout_corpora") != []:
        raise RuntimeError("primary candidate accessed a holdout corpus")
    print(json.dumps({"status": report.get("status"), "report": str(report_path)}))


if __name__ == "__main__":
    main()
