"""Freeze all sixteen opened-diagnostic evaluations after full fitting review."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from body_features import augmented_features
from body_stats import compile_body_table
from fit_authority_weighted import pin_fits
from paired_errors import paired_error_intervals
from residual_features import make_layout
from run_scaling_comparison import report_predictions
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from semantic_data import layout_hash
from terminal_labels import sha
from weighted_contract import publish
from weighted_model import make_model, predict_margin


def sources():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def check_resources(resources):
    if any(sha(path) != expected for path, expected in resources.items()):
        raise ValueError("weighted evaluation resource changed")


def reference_directory(root, kind):
    return root / "reports" / ("hog26_residual_margin_seed_transfer_20260912" if kind == "numeric"
                               else "hog26_semantic_margin_seed_transfer_20260912")


def prepare_pin(root, review_path, pin_path):
    if pin_path.exists():
        raise ValueError("preserve existing weighted evaluation pin")
    plan, _, _, resources = pin_fits(root)
    review = json.loads(review_path.read_text())
    if (review["status"] != "completed-weighted-margin-fitting-review" or review["fits"] != 16
            or review["artifact_count"] != 62 or not review["wdl_reference_exact"] or review["acceptance"]):
        raise ValueError("complete weighted fitting review required")
    check_resources(review["resources"])
    resources.update(review["resources"])
    resources[str(review_path.resolve())] = sha(review_path)
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    if json.loads((reference / "complete.json").read_text()) != {
            "status": "frozen-model-diagnostic-complete", "fits_evaluated": 20,
            "fitting": False, "acceptance": False}:
        raise ValueError("complete globals and tree references required")
    for kind in plan.models:
        directory = reference_directory(root, kind)
        expected_status = "fixed-residual-diagnostic-complete" if kind == "numeric" else "fixed-semantic-diagnostic-complete"
        if json.loads((directory / "complete.json").read_text()) != {
                "status": expected_status, "fits": 8, "fitting": False, "acceptance": False}:
            raise ValueError("complete original-sampler diagnostic required")
    for directory in (reference, *(reference_directory(root, kind) for kind in plan.models)):
        for path in directory.iterdir():
            if path.is_file():
                resources[str(path)] = sha(path)
    for directory in ("hog26_seed_transfer", "hog26_scaling_eval", "hog26_scaling_review"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for path in Path(__file__).parent.glob("*.py"):
        resources[str(path.resolve())] = sha(path)
    for relative in ("reports/hog26_seed_transfer_frozen_plan_20260911.json",
                     "reports/hog26_seed_transfer_preflight_pin_20260911.json"):
        path = root / relative
        resources[str(path)] = sha(path)
    resources.update(plan.resources)
    check_resources(resources)
    publish(pin_path, {"schema": "clasher.hog26.fixed-weighted-margin-diagnostic.v1", "fits": 16,
                       "resources": resources, "evaluation_sources": sources(),
                       "groups": {"fresh_seen_families": 288, "fresh_excluded_families": 96},
                       "paired_references": "same architecture and seed under original sampler; scaled tree matching fold",
                       "bootstrap_replicates": 2000, "bootstrap_seed": 1279511,
                       "fitting": False, "acceptance": False})
    print(json.dumps({"status": "weighted-evaluation-pinned", "sha256": sha(pin_path)}), flush=True)


def evaluate(root, pin_path, output):
    if output.exists():
        raise ValueError("preserve existing weighted evaluation")
    pin = json.loads(pin_path.read_text())
    if (pin["schema"] != "clasher.hog26.fixed-weighted-margin-diagnostic.v1" or pin["fits"] != 16
            or pin["evaluation_sources"] != sources() or pin["fitting"] is not False
            or pin["acceptance"] is not False or pin["bootstrap_replicates"] != 2000
            or pin["bootstrap_seed"] != 1279511):
        raise ValueError("weighted evaluation contract changed")
    check_resources(pin["resources"])
    plan, feature_plan, manifest, _ = pin_fits(root)
    from fit_authority import original_training_records
    from transfer_dataset import load_complete_pilot

    games, vocabulary, audit = load_complete_pilot(
        root / "datasets/derived/hog26_seed_transfer_seed1279601_20260911",
        plan_path=root / "reports/hog26_seed_transfer_frozen_plan_20260911.json",
        preflight_path=root / "reports/hog26_seed_transfer_preflight_pin_20260911.json")
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    original_manifest = json.loads((reference / "evaluation_manifest.json").read_text())
    if audit != original_manifest["data_audit"] or tuple(vocabulary) != feature_plan.data.vocabulary:
        raise ValueError("weighted diagnostic corpus differs")
    if any(not np.all(g.public["global_feature_confidence"][:, 8:14] == 1) for g in games):
        raise ValueError("weighted diagnostic baseline availability differs")
    layout = make_layout(len(vocabulary), feature_plan.data.hand_tokens)
    if layout_hash(layout) != feature_plan.data.feature_layout_sha256:
        raise ValueError("weighted diagnostic numeric layout differs")
    table = compile_body_table(vocabulary)
    semantic = np.concatenate([augmented_features(g.public, layout, table) for g in games])
    matrices = {"semantic": semantic, "numeric": np.ascontiguousarray(semantic[:, :425])}
    lengths = [len(g.public["global_features"]) for g in games]
    ids = np.repeat(np.arange(len(games)), lengths)
    progress = np.concatenate([g.public["global_features"][:, 0] for g in games])
    labels, target = [np.repeat([getattr(g, field) for g in games], lengths) for field in ("target_class", "target_margin")]
    current = np.concatenate([(g.public["global_features"][:, 8:11].sum(1) - g.public["global_features"][:, 11:14].sum(1)) / 3 for g in games])
    seats, styles, families, clusters = [np.repeat([getattr(g, field) for g in games], lengths) for field in ("seat", "style", "family", "cluster")]
    folds = np.array([int(f[-3:]) // 2 for f in families])
    evaluation = (ids, progress, labels, target, current, seats, styles, folds, clusters, families)
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f"family/{f}": families == f for f in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    training = original_training_records(root, {"data_audit": manifest["data_audit"]})
    del games
    output.mkdir()
    root_manifest = output / "evaluation_manifest.json"
    publish(root_manifest, {"pin_sha256": sha(pin_path), "pin": pin, "data_audit": audit,
                            "models": list(plan.models), "fitting": False, "acceptance": False})
    for kind in plan.models:
        directory = output / kind
        directory.mkdir()
        publish(directory / "evaluation_manifest.json", {"model": kind, "root_manifest_sha256": sha(root_manifest),
                                                           "inputs": matrices[kind].shape[1]})
        fitted = root / "reports/hog26_weighted_margin_comparison_20260913" / kind
        original = reference_directory(root, kind)
        for seed in plan.seeds:
            for fold in range(4):
                check_resources(pin["resources"])
                stem = f"seed{seed}-fold{fold}"
                model = make_model(kind)
                model.load_state_dict(torch.load(fitted / (stem + ".pt"), weights_only=True, map_location="cpu"))
                margin = predict_margin(model.eval(), matrices[kind], current)
                with np.load(reference / ("globals-" + stem + "-predictions.npz"), allow_pickle=False) as saved:
                    probability = saved["probabilities"].astype(np.float64)
                with np.load(original / (stem + "-predictions.npz"), allow_pickle=False) as saved:
                    old_margin = saved["margin"]
                    if not np.array_equal(saved["probabilities"], probability):
                        raise ValueError("original sampler WDL reference differs")
                with np.load(reference / f"tree-seed1279501-fold{fold}-predictions.npz", allow_pickle=False) as saved:
                    tree_margin = saved["margin"]
                old_report = json.loads((original / (stem + "-report.json")).read_text())
                tree_report = json.loads((reference / f"tree-seed1279501-fold{fold}-report.json").read_text())
                selected = [g for g in training if int(g["family_id"][-3:]) // 2 != fold]
                if len(selected) != 1152:
                    raise ValueError("weighted diagnostic fitting prior cohort differs")
                prior = np.mean([g["outcome_wdl"][::-1] for g in selected], axis=0)
                np.savez_compressed(directory / (stem + "-predictions.npz"), probabilities=probability, margin=margin)
                report = {}
                for group, group_mask, count in (("fresh_seen_families", folds != fold, 288),
                                                 ("fresh_excluded_families", folds == fold, 96)):
                    report[group] = report_predictions(evaluation, probability, margin, prior, fit_mask=group_mask, bootstrap=True)
                    for distribution, slices in report[group].items():
                        if slices["overall"]["coverage"]["games"] != count:
                            raise ValueError("weighted diagnostic group count differs")
                        for name, row in slices.items():
                            if "metrics" not in row:
                                continue
                            weights = evaluation_weights(ids, progress, masks[name] & group_mask,
                                                         representative=distribution == "representatives", index=index)
                            for key, old, ref_report in (("original_sampler", old_margin, old_report),
                                                         ("scaled_tree", tree_margin, tree_report)):
                                ref_row = ref_report[group][distribution][name]
                                if row["coverage"] != ref_row["coverage"]:
                                    raise ValueError("paired weighted margin coverage differs")
                                paired = paired_error_intervals(probability, probability, old, margin, labels, target, weights, clusters)
                                change = paired["metrics"]["margin_mae_reduction"]
                                expected = ref_row["metrics"]["margin_mae"] - row["metrics"]["margin_mae"]
                                if not np.isclose(change["point"], expected, rtol=1e-9, atol=1e-10):
                                    raise ValueError("paired weighted margin point differs")
                                row["paired_margin_reduction_vs_" + key] = change
                publish(directory / (stem + "-report.json"), report)
                print(json.dumps({"model": kind, "seed": seed, "fold": fold, "status": "evaluated-and-paired"}), flush=True)
        publish(directory / "complete.json", {"status": "weighted-margin-model-diagnostic-complete", "model": kind, "fits": 8, "fitting": False, "acceptance": False})
    check_resources(pin["resources"])
    publish(output / "complete.json", {"status": "weighted-margin-diagnostic-complete", "fits": 16, "fitting": False, "acceptance": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pin", "evaluate"), required=True)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--fitting-review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    if args.mode == "pin":
        if args.fitting_review is None:
            raise ValueError("completed weighted fitting review required")
        prepare_pin(root, args.fitting_review, args.pin)
    else:
        if args.output is None:
            raise ValueError("new diagnostic output required")
        evaluate(root, args.pin, args.output)


if __name__ == "__main__":
    main()
