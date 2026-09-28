"""Freeze and evaluate every residual fit on the existing opened diagnostic."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from body_features import augmented_features
from body_stats import compile_body_table
from paired_errors import paired_error_intervals
from residual_features import make_layout
from run_scaling_comparison import report_predictions
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from semantic_authority import pin_completed_fits
from semantic_contract import sha
from semantic_data import layout_hash
from semantic_training import SemanticResidualMargin, predict_margin


def sources():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def check_resources(resources):
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("frozen residual evaluation resource changed: " + path)


def prepare_pin(root, review_path, pin_path):
    if pin_path.exists():
        raise ValueError("refusing existing evaluation pin")
    plan, _, resources = pin_completed_fits(root)
    review = json.loads(review_path.read_text())
    if (review["status"] != "completed-semantic-fitting-review" or review["fits"] != 8
            or review["acceptance"] is not False or review["wdl_reference_exact"] is not True):
        raise ValueError("complete residual fitting review required")
    check_resources(review["resources"])
    resources.update(review["resources"])
    resources[str(review_path.resolve())] = sha(review_path)
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    completion = json.loads((reference / "complete.json").read_text())
    if completion != {"status": "frozen-model-diagnostic-complete", "fits_evaluated": 20,
                      "fitting": False, "acceptance": False}:
        raise ValueError("completed globals/tree diagnostic references required")
    for name in ("complete.json", "evaluation_manifest.json"):
        path = reference / name
        resources[str(path)] = sha(path)
    for seed in plan.training.seeds:
        for fold in range(4):
            for suffix in ("-predictions.npz", "-report.json"):
                path = reference / f"globals-seed{seed}-fold{fold}{suffix}"
                resources[str(path)] = sha(path)
    for fold in range(4):
        for suffix in ("-predictions.npz", "-report.json"):
            path = reference / f"tree-seed1279501-fold{fold}{suffix}"
            resources[str(path)] = sha(path)
    numeric = root / "reports/hog26_residual_margin_seed_transfer_20260912"
    if json.loads((numeric / "complete.json").read_text()) != {
            "status": "fixed-residual-diagnostic-complete", "fits": 8,
            "fitting": False, "acceptance": False}:
        raise ValueError("completed numeric residual diagnostic required")
    for path in numeric.iterdir():
        if path.is_file():
            resources[str(path)] = sha(path)
    for relative in ("reports/hog26_seed_transfer_frozen_plan_20260911.json",
                     "reports/hog26_seed_transfer_preflight_pin_20260911.json",
                     "experiments/hog26_scaling_review/paired_errors.py",
                     "experiments/hog26_scaling_review/review_completed.py",
                     "experiments/hog26_scaling_eval/fit_authority.py"):
        path = root / relative
        resources[str(path)] = sha(path)
    resources.update(plan.authority.resources)
    for path in Path(__file__).parent.glob("*.py"):
        resources[str(path.resolve())] = sha(path)
    check_resources(resources)
    pin = {"schema": "clasher.hog26.fixed-semantic-diagnostic.v1", "fits": 8,
           "resources": resources, "evaluation_sources": sources(),
           "groups": {"fresh_seen_families": 288, "fresh_excluded_families": 96},
           "paired_margin_reference": "scaled tree seed1279501 and numeric residual matching seed, each matching family fold",
           "bootstrap_replicates": 2000, "bootstrap_seed": 1279511,
           "scope": "All fits and slices; paired margin-only comparison on identical opened games. No fitting, selection, calibration, or acceptance.",
           "fitting": False, "acceptance": False}
    with pin_path.open("x") as stream:
        json.dump(pin, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "evaluation-pinned", "sha256": sha(pin_path), "fits": 8}), flush=True)


def evaluate(root, pin_path, output):
    if output.exists():
        raise ValueError("refusing existing residual evaluation")
    pin = json.loads(pin_path.read_text())
    if (pin["schema"] != "clasher.hog26.fixed-semantic-diagnostic.v1" or pin["fits"] != 8
            or pin["evaluation_sources"] != sources() or pin["fitting"] is not False
            or pin["acceptance"] is not False or pin["bootstrap_replicates"] != 2000
            or pin["bootstrap_seed"] != 1279511):
        raise ValueError("residual evaluation contract changed")
    check_resources(pin["resources"])
    plan, manifest, _ = pin_completed_fits(root)
    # Diagnostic arrays are not accessed until all fitting/review/source checks pass.
    from fit_authority import original_training_records
    from transfer_dataset import load_complete_pilot

    games, vocabulary, audit = load_complete_pilot(
        root / "datasets/derived/hog26_seed_transfer_seed1279601_20260911",
        plan_path=root / "reports/hog26_seed_transfer_frozen_plan_20260911.json",
        preflight_path=root / "reports/hog26_seed_transfer_preflight_pin_20260911.json",
    )
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    reference_manifest = json.loads((reference / "evaluation_manifest.json").read_text())
    if audit != reference_manifest["data_audit"] or tuple(vocabulary) != plan.data.vocabulary:
        raise ValueError("residual diagnostic corpus or vocabulary differs")
    if any(not np.all(g.public["global_feature_confidence"][:, 8:14] == 1) for g in games):
        raise ValueError("diagnostic baseline tower-health availability differs")
    layout = make_layout(len(vocabulary), plan.data.hand_tokens)
    if layout_hash(layout) != plan.data.feature_layout_sha256:
        raise ValueError("residual diagnostic feature layout differs")
    table = compile_body_table(vocabulary)
    features = np.concatenate([augmented_features(g.public, layout, table) for g in games])
    lengths = [len(g.public["global_features"]) for g in games]
    ids = np.repeat(np.arange(len(games)), lengths)
    progress = np.concatenate([g.public["global_features"][:, 0] for g in games])
    labels = np.repeat([g.target_class for g in games], lengths)
    target = np.repeat([g.target_margin for g in games], lengths)
    current = np.concatenate([(g.public["global_features"][:, 8:11].sum(1)
                               - g.public["global_features"][:, 11:14].sum(1)) / 3 for g in games])
    seats = np.repeat([g.seat for g in games], lengths)
    styles = np.repeat([g.style for g in games], lengths)
    families = np.repeat([g.family for g in games], lengths)
    clusters = np.repeat([g.cluster for g in games], lengths)
    folds = np.array([int(f[-3:]) // 2 for f in families])
    evaluation = (ids, progress, labels, target, current, seats, styles, folds, clusters, families)
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f"family/{f}": families == f for f in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    training = original_training_records(root, {"data_audit": manifest["data_audit"]})
    del games
    output.mkdir()
    with (output / "evaluation_manifest.json").open("x") as stream:
        json.dump({"pin_sha256": sha(pin_path), "pin": pin, "data_audit": audit,
                   "model": plan.model.name, "feature_layout_sha256": layout_hash(layout),
                   "fitting": False, "acceptance": False}, stream, indent=2)
        stream.write("\n")
    directory = root / "reports/hog26_semantic_margin_comparison_20260912"
    for seed in plan.training.seeds:
        for fold in range(4):
            check_resources(pin["resources"])
            stem = f"seed{seed}-fold{fold}"
            model = SemanticResidualMargin()
            model.load_state_dict(torch.load(directory / (stem + ".pt"), weights_only=True, map_location="cpu"))
            model.eval()
            margin = predict_margin(model, features, current)
            with np.load(reference / ("globals-" + stem + "-predictions.npz"), allow_pickle=False) as saved:
                probability = saved["probabilities"].astype(np.float64)
            with np.load(reference / f"tree-seed1279501-fold{fold}-predictions.npz", allow_pickle=False) as saved:
                tree_margin = saved["margin"]
            tree_report = json.loads((reference / f"tree-seed1279501-fold{fold}-report.json").read_text())
            numeric = root / "reports/hog26_residual_margin_seed_transfer_20260912"
            with np.load(numeric / (stem + "-predictions.npz"), allow_pickle=False) as saved:
                numeric_margin = saved["margin"]
                if not np.array_equal(saved["probabilities"], probability):
                    raise ValueError("numeric reference probability identity differs")
            numeric_report = json.loads((numeric / (stem + "-report.json")).read_text())
            selected = [g for g in training if int(g["family_id"][-3:]) // 2 != fold]
            if len(selected) != 1152:
                raise ValueError("residual fitting prior inventory changed")
            prior = np.mean([g["outcome_wdl"][::-1] for g in selected], axis=0)
            np.savez_compressed(output / (stem + "-predictions.npz"), probabilities=probability, margin=margin)
            report = {}
            for group, group_mask, count in (("fresh_seen_families", folds != fold, 288),
                                             ("fresh_excluded_families", folds == fold, 96)):
                report[group] = report_predictions(evaluation, probability, margin, prior,
                                                   fit_mask=group_mask, bootstrap=True)
                for distribution, slices in report[group].items():
                    if slices["overall"]["coverage"]["games"] != count:
                        raise ValueError("residual diagnostic group counts differ")
                    for name, row in slices.items():
                        if "metrics" not in row:
                            continue
                        original = tree_report[group][distribution][name]
                        if row["coverage"] != original["coverage"]:
                            raise ValueError("paired margin coverage differs")
                        weights = evaluation_weights(ids, progress, masks[name] & group_mask,
                                                     representative=distribution == "representatives", index=index)
                        # The same probability array is supplied twice; only the
                        # additive margin statistic is retained or interpreted.
                        paired = paired_error_intervals(probability, probability, tree_margin, margin,
                                                        labels, target, weights, clusters)
                        change = paired["metrics"]["margin_mae_reduction"]
                        expected = original["metrics"]["margin_mae"] - row["metrics"]["margin_mae"]
                        if not np.isclose(change["point"], expected, rtol=1e-9, atol=1e-10):
                            raise ValueError("paired margin difference does not reproduce report points")
                        row["paired_margin_reduction_vs_scaled_tree"] = change
                        numeric_original = numeric_report[group][distribution][name]
                        if row["coverage"] != numeric_original["coverage"]:
                            raise ValueError("numeric paired coverage differs")
                        numeric_paired = paired_error_intervals(
                            probability, probability, numeric_margin, margin,
                            labels, target, weights, clusters)
                        numeric_change = numeric_paired["metrics"]["margin_mae_reduction"]
                        numeric_expected = numeric_original["metrics"]["margin_mae"] - row["metrics"]["margin_mae"]
                        if not np.isclose(numeric_change["point"], numeric_expected, rtol=1e-9, atol=1e-10):
                            raise ValueError("numeric paired point differs")
                        row["paired_margin_reduction_vs_numeric_residual"] = numeric_change
            with (output / (stem + "-report.json")).open("x") as stream:
                json.dump(report, stream, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"seed": seed, "fold": fold, "status": "evaluated-and-paired"}), flush=True)
    check_resources(pin["resources"])
    with (output / "complete.json").open("x") as stream:
        json.dump({"status": "fixed-semantic-diagnostic-complete", "fits": 8,
                   "fitting": False, "acceptance": False}, stream, indent=2)
        stream.write("\n")


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
            raise ValueError("completed fitting review required")
        prepare_pin(root, args.fitting_review, args.pin)
    else:
        if args.output is None:
            raise ValueError("new evaluation output required")
        evaluate(root, args.pin, args.output)


if __name__ == "__main__":
    main()
