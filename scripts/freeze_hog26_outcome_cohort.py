"""Freeze the complete declared candidate cohort before final collection."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from scripts.hog26_frozen_outcome import load_frozen_outcome_head
from scripts.run_hog26_procedural_outcome_shard import load_protocol
from scripts.train_hog26_actor_outcome import file_sha256
from scripts.train_hog26_procedural_outcome_candidate import validate_training_inputs


def require_unopened_final_paths(protocol, root):
    for stage in protocol["final_holdout"].values():
        paths = [root / stage[key] for key in (
            "output_corpus", "output_report", "audit_report"
        )]
        # Collectors may write shards before atomically publishing corpus.npz.
        paths.append((root / stage["output_corpus"]).parent)
        paths.append((root / stage["output_report"]).with_suffix(".collection-start.json"))
        if any(path.exists() for path in paths):
            raise ValueError("final collection artifacts already exist; cannot freeze")


def validate_cohort_reports(protocol, reports, root):
    expected_seeds = [protocol["primary_candidate"]["seed"],
                      *protocol["replication"]["seeds"]]
    seeds = [report["seed"] for report in reports]
    if len(set(seeds)) != len(seeds) or sorted(seeds) != sorted(expected_seeds):
        raise ValueError("freeze requires the primary and every declared replica")
    candidate = protocol["primary_candidate"]
    expected_weighting = {
        "target_class_mass": dict(zip(
            ("loss", "draw", "win"), candidate["target_class_mass_loss_draw_win"],
            strict=True,
        )),
        "outcome_training_weighting": (
            "equal-episode-equal-reached-phase-then-declared-class-mass-v1"
            if candidate["phase_balanced_outcome_training"]
            else "equal-episode-then-declared-class-mass-v1"
        ),
        "margin_training_weighting": (
            "equal-aggregate-phase-within-game-phase-v1"
            if candidate.get("aggregate_phase_margin_training", False) else
            "equal-episode-equal-reached-phase-v1"
            if candidate["phase_balanced_margin_training"]
            else "equal-episode-v1"
        ),
        "epoch_selection": "maximin-phase-then-decisive-auc-among-point-gate-passes-v1",
        "margin_epoch_selection": "maximum-mae-improvement-among-all-phase-gate-passes-v1",
    }
    fields = (
        "hidden_size", "margin_residual_scale", "margin_feature_set",
        "margin_progress_power", "epochs", "batch_size", "sequence_steps",
        "learning_rate", "margin_coefficient", "calibration_timing",
    )
    data = protocol["primary_candidate_data"]
    expected_sources = {
        "train": [*data["legacy_training_corpora"],
                  *(row["output_corpus"] for row in protocol["training"])],
        "validation": [protocol["development_selection"]["output_corpus"],
                       data["validation_corpora"][1]],
        "calibration": [protocol["probability_calibration"]["output_corpus"]],
    }
    for report in reports:
        if candidate["feature_set"] == "public-global-dynamics" and (
            report.get("state_size") != 19 or report.get("separate_draw_trunk") is not False
        ):
            raise ValueError("dynamic candidate architecture differs from its public contract")
        if candidate.get("margin_dynamics", "none") != "none" and report.get("inference_authority") != protocol.get("inference_authority"):
            raise ValueError("candidate inference authority differs from protocol")
        if (
            any(report.get(key) != candidate[key] for key in fields)
            or report.get("margin_dynamics", "none") != candidate.get("margin_dynamics", "none")
            or report.get("margin_loss", "huber") != candidate.get("margin_loss", "huber")
            or any(report.get(key) != value for key, value in expected_weighting.items())
            or report.get("actor_feature_contract") != candidate["feature_set"]
            or report.get("actor_input_critic_fields") is not False
            or report.get("actor_input_previous_reward")
            != "forced-zero-unavailable-at-live-inference"
        ):
            raise ValueError("candidate differs from declared design or public inputs")
        for role, paths in expected_sources.items():
            expected = [(str((root / path).resolve()), file_sha256(root / path))
                        for path in paths]
            actual_paths = report.get(f"{role}_corpora", [])
            actual_hashes = report.get(f"{role}_corpus_sha256", [])
            if len(actual_paths) != len(actual_hashes) or sorted(zip(
                actual_paths, actual_hashes, strict=True
            )) != sorted(expected):
                raise ValueError("candidate fitting sources differ from protocol")
    shared = (
        "state_size", "separate_draw_trunk", "structured_residual_scale",
        "target_class_mass", "outcome_training_weighting", "margin_training_weighting",
        "train_class_prior", "epoch_selection", "margin_epoch_selection",
    )
    if any(any(key not in report for key in shared) for report in reports) or any(
        any(report[key] != reports[0][key] for key in shared)
        for report in reports[1:]
    ):
        raise ValueError("candidate cohort does not share one design and fitting prior")


def freeze_cohort(protocol_path, checkpoint_paths, output, *, root):
    if output.exists():
        raise ValueError("refusing to overwrite frozen cohort")
    protocol = json.loads(protocol_path.read_text())
    require_unopened_final_paths(protocol, root)
    validate_training_inputs(protocol, root=root)
    protocol_sha = file_sha256(protocol_path)
    policy_sha = protocol["base_policy"]["sha256"]
    if file_sha256(root / protocol["base_policy"]["path"]) != policy_sha:
        raise ValueError("base policy changed before cohort freeze")
    records, reports = [], []
    for path in checkpoint_paths:
        checkpoint_sha = file_sha256(path)
        payload = torch.load(path, map_location="cpu", weights_only=True)
        state_sha = payload["training_report"]["outcome_head_state_sha256"]
        _, report = load_frozen_outcome_head(
            path, checkpoint_sha256=checkpoint_sha, state_sha256=state_sha,
            base_policy_sha256=policy_sha, protocol_sha256=protocol_sha,
        )
        reports.append(report)
        records.append({"seed": report["seed"], "path": str(path.resolve()),
                        "checkpoint_sha256": checkpoint_sha,
                        "state_sha256": state_sha})
    validate_cohort_reports(protocol, reports, root)
    require_unopened_final_paths(protocol, root)
    if file_sha256(protocol_path) != protocol_sha:
        raise ValueError("protocol changed during freeze")
    manifest = {
        "schema": "clasher.hog26.frozen-outcome-cohort.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": str(protocol_path.resolve()), "protocol_sha256": protocol_sha,
        "inference_authority": protocol.get("inference_authority"),
        "base_policy_sha256": policy_sha,
        "candidates": sorted(records, key=lambda row: row["seed"]),
        "final_artifacts_absent_at_freeze": True,
        "all_candidates_required": True,
        "public_acceptance_pending": True,
        "counterfactual_ranking_pending": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        handle.write(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_frozen_cohort(manifest_path, expected_sha256, *, root):
    """Validate all frozen candidates before any final corpus is opened."""
    if file_sha256(manifest_path) != expected_sha256:
        raise ValueError("frozen cohort manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("schema") != "clasher.hog26.frozen-outcome-cohort.v1"
        or manifest.get("final_artifacts_absent_at_freeze") is not True
        or manifest.get("all_candidates_required") is not True
    ):
        raise ValueError("invalid frozen cohort manifest")
    protocol_path = Path(manifest["protocol"])
    if file_sha256(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("frozen cohort protocol changed")
    protocol = load_protocol(protocol_path, root)
    if manifest.get("inference_authority") != protocol.get("inference_authority"):
        raise ValueError("frozen cohort inference authority changed")
    if manifest["base_policy_sha256"] != protocol["base_policy"]["sha256"]:
        raise ValueError("frozen cohort base policy changed")
    validate_training_inputs(protocol, root=root)
    candidates = []
    for row in manifest["candidates"]:
        head, report = load_frozen_outcome_head(
            Path(row["path"]), checkpoint_sha256=row["checkpoint_sha256"],
            state_sha256=row["state_sha256"],
            base_policy_sha256=manifest["base_policy_sha256"],
            protocol_sha256=manifest["protocol_sha256"],
        )
        if row["seed"] != report["seed"]:
            raise ValueError("manifest candidate seed differs from checkpoint")
        candidates.append((row, head, report))
    validate_cohort_reports(protocol, [r for _, _, r in candidates], root)
    return manifest, protocol, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze_cohort(args.protocol, args.checkpoint, args.output, root=Path.cwd())


if __name__ == "__main__":
    main()
