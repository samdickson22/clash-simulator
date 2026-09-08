"""Evaluate frozen public predictions; never fit or recalibrate a head."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from clasher.rl.outcome_model import outcome_state_sha256
from scripts.audit_hog26_procedural_outcome_shard import shard_expectations
from scripts.freeze_hog26_outcome_cohort import load_frozen_cohort
from scripts.hog26_public_slice_gates import evaluate_loaded_public_slices
from scripts.pretrain_hog26_direct_simple_behavior import load_model
from scripts.train_hog26_actor_outcome import (
    _atomic_json,
    _evaluation_breakdowns,
    _outcome_source,
    all_phase_auc_confidence_passed,
    extract_actor_features,
    file_sha256,
    phase_auc_confidence_intervals,
    phase_balanced_matchup_clusters,
    phase_balanced_row_indices,
    validate_outcome_corpus,
)
from scripts.train_hog26_procedural_outcome_candidate import require_current_audit


def preflight_final_corpora(protocol, manifest, manifest_sha256, *, root):
    records = []
    for role, stage in protocol["final_holdout"].items():
        path = root / stage["output_corpus"]
        audited = require_current_audit(path, root / stage["audit_report"])
        count = stage["actor_views"] if role == "controlled_draw" else stage["expected_games"]
        if audited["seed"] != stage["seed"] or audited["episodes"] != count:
            raise ValueError("final audit does not match declared seed/game budget")
        collection = json.loads((root / stage["output_report"]).read_text())
        authority = collection.get("collection_authority", {})
        if (
            authority.get("frozen_cohort_sha256") != manifest_sha256
            or authority.get("protocol_sha256") != manifest["protocol_sha256"]
        ):
            raise ValueError("final collection is not bound to the frozen cohort")
        records.append({"role": role, "path": str(path), "sha256": audited["sha256"]})
    return records


def validate_final_metadata(protocol, role, metadata, *, root):
    stage = protocol["final_holdout"][role]
    if (
        metadata.get("seed") != stage["seed"]
        or metadata.get("checkpoint_sha256") != protocol["base_policy"]["sha256"]
    ):
        raise ValueError("final corpus policy/seed authority differs")
    if role == "generated":
        expected = shard_expectations(protocol, stage, root=root)
        if (
            set(metadata.get("opponents", [])) != expected["expected_opponents"]
            or set(metadata.get("opponent_decks", [])) != expected["expected_decks"]
            or metadata.get("supported_decks_sha256") != expected["expected_supported_decks_sha256"]
            or metadata.get("opponent_deck_split") != expected["expected_split"]
        ):
            raise ValueError("generated final corpus differs from declared families/styles")
    elif role == "reserved_original":
        if (
            set(metadata.get("opponents", [])) != set(stage["opponents"])
            or metadata.get("opponent_decks") != [stage["deck"]]
            or metadata.get("supported_decks_sha256") != protocol["original_decks"]["sha256"]
        ):
            raise ValueError("reserved final corpus differs from declared deck/styles")
    elif (
        metadata.get("physical_battle_count") != stage["physical_games"]
        or metadata.get("paired_actor_views_share_physical_battle") is not True
    ):
        raise ValueError("controlled final corpus lacks declared paired physical games")


@torch.inference_mode()
def evaluate_cohort(manifest_path, manifest_sha256, output, *, root, device):
    if output.exists():
        raise ValueError("refusing to overwrite final cohort evaluation")
    manifest, protocol, candidates = load_frozen_cohort(
        manifest_path, manifest_sha256, root=root,
    )
    records = preflight_final_corpora(protocol, manifest, manifest_sha256, root=root)
    loaded = []
    for record in records:
        path = Path(record["path"])
        metadata, corpus = load_direct_simple_behavior_corpus(path)
        validate_final_metadata(protocol, record["role"], metadata, root=root)
        validate_outcome_corpus(metadata, corpus)
        if file_sha256(path) != record["sha256"]:
            raise ValueError("final corpus changed during loading")
        loaded.append((metadata, corpus))
    _, model = load_model(root / protocol["base_policy"]["path"], torch.device(device))
    model.eval()
    model.requires_grad_(False)
    report0 = candidates[0][2]
    features = torch.cat([
        extract_actor_features(
            model, corpus, device=torch.device(device),
            sequence_steps=report0["sequence_steps"],
            feature_set=report0["actor_feature_contract"],
        ) for _, corpus in loaded
    ])
    results = []
    for record, head, training_report in candidates:
        head.to(device)
        result = evaluate_frozen_predictions(
            head, features, loaded, torch.tensor(training_report["train_class_prior"]),
            protocol, seed=record["seed"] + 40_000, device=device,
        )
        results.append({"seed": record["seed"], "checkpoint": record, "evaluation": result})
    if file_sha256(manifest_path) != manifest_sha256:
        raise ValueError("cohort manifest changed during evaluation")
    report = {
        "schema": "clasher.hog26.frozen-cohort-evaluation.v1",
        "frozen_cohort_sha256": manifest_sha256,
        "protocol_sha256": manifest["protocol_sha256"],
        "corpora": records, "candidates": results,
        "public_state_gates_passed": all(r["evaluation"]["passed"] for r in results),
        "counterfactual_ranking_pending": True, "policy_updates_allowed": False,
    }
    _atomic_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-cohort", type=Path, required=True)
    parser.add_argument("--frozen-cohort-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    args = parser.parse_args()
    evaluate_cohort(args.frozen_cohort, args.frozen_cohort_sha256, args.output,
                    root=Path.cwd(), device=args.device)


@torch.inference_mode()
def evaluate_frozen_predictions(head, features, loaded, prior, protocol, *, seed, device):
    """Compute acceptance after cohort and audited-corpus preflight by the caller."""
    if head.training or any(p.requires_grad for p in head.parameters()):
        raise ValueError("final metrics require an eval-mode frozen head")
    original_state = outcome_state_sha256(head.state_dict())
    stages = protocol["final_holdout"]
    expected = {stage["seed"]: name for name, stage in stages.items()}
    actual = [metadata["seed"] for metadata, _ in loaded]
    if len(set(actual)) != len(actual) or set(actual) != set(expected):
        raise ValueError("final metrics require every declared final corpus once")
    for metadata, corpus in loaded:
        validate_outcome_corpus(metadata, corpus)
        role = expected[metadata["seed"]]
        stage = stages[role]
        count = stage["actor_views"] if role == "controlled_draw" else stage["expected_games"]
        source = "controlled-symmetric-draws" if role == "controlled_draw" else "natural-strategy-games"
        if corpus.episode_count != count or _outcome_source(metadata) != source:
            raise ValueError("final corpus has wrong source or episode budget")
    rows = sum(corpus.row_count for _, corpus in loaded)
    if features.shape != (rows, head.state_size) or not torch.isfinite(features).all():
        raise ValueError("final public features have invalid shape or values")
    public = torch.tensor(np.concatenate([
        corpus.arrays["global_features"] for _, corpus in loaded
    ]), dtype=features.dtype)
    if not torch.equal(features[:, -18:].cpu(), public):
        raise ValueError("final feature globals differ from corpus")
    outcomes = torch.tensor(np.concatenate([
        corpus.arrays["final_outcomes"] for _, corpus in loaded
    ]))
    margins = torch.tensor(np.concatenate([
        corpus.arrays["terminal_tower_margins"] for _, corpus in loaded
    ]))
    public_slices = evaluate_loaded_public_slices(
        head, features, loaded, prior, protocol, stage="holdout", device=device, seed=seed,
    )
    breakdowns = _evaluation_breakdowns(
        head, features, outcomes, margins, loaded, device=device,
    )
    representatives = phase_balanced_row_indices(loaded)
    progress = public[representatives, 0].numpy()
    phases = np.where(progress < 1 / 3, "early", np.where(progress < 2 / 3, "middle", "late"))
    confidence = phase_auc_confidence_intervals(
        head, features[representatives], outcomes[representatives], phases,
        device=device, seed=seed + 1,
        replicates=protocol["gates"]["cluster_bootstrap_replicates"],
        clusters=phase_balanced_matchup_clusters(loaded),
    )
    gates = protocol["gates"]
    natural = breakdowns["phase_balanced_by_source"]["natural-strategy-games"]
    endpoints = breakdowns["episode_endpoints_by_source"]
    draw_auc = breakdowns["phase_balanced"]["auc_one_vs_rest"]["draw"]
    draw_lift = (
        endpoints["controlled-symmetric-draws"]["mean_outcome_probability"]["draw"]
        - endpoints["natural-strategy-games"]["mean_outcome_probability"]["draw"]
    )
    checks = {
        "natural_public_slices": public_slices["passed"],
        "decisive_phase_confidence": all_phase_auc_confidence_passed(
            confidence, minimum_lower_95=gates["minimum_phase_auc_lower_95"],
            minimum_clusters=gates["minimum_clusters_per_phase"],
        ),
        "natural_draw_probability": natural["mean_outcome_probability"]["draw"]
        <= gates["maximum_natural_draw_probability"],
        "controlled_draw_auc": draw_auc is not None
        and draw_auc >= gates["minimum_controlled_draw_auc"],
        "controlled_draw_endpoint_lift": draw_lift
        >= gates["minimum_controlled_draw_endpoint_probability_lift"],
    }
    final_state = outcome_state_sha256(head.state_dict())
    if original_state != final_state:
        raise ValueError("evaluation changed frozen outcome state")
    return {
        "schema": "clasher.hog26.frozen-outcome-metrics.v1",
        "passed": all(checks.values()), "checks": checks,
        "outcome_state_sha256_before": original_state,
        "outcome_state_sha256_after": final_state,
        "public_slices": public_slices, "phase_auc_confidence": confidence,
        "breakdowns": breakdowns,
        "controlled_draw_endpoint_probability_lift": draw_lift,
        "mixed_source_aggregate_scope": "diagnostic only; natural public slices gate classification and margin",
        "counterfactual_ranking_pending": True,
        "policy_updates_allowed": False,
    }


if __name__ == "__main__":
    main()
