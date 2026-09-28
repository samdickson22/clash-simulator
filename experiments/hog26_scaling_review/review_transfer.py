"""Review all completed scaled diagnostic fits against the original predictions."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from paired_errors import paired_error_intervals
from review_completed import SEEDS, read, sha, summarize_slices
from review_plan import validate_review_plan


def prerequisites(root, fitting_review, resources):
    plan_path, plan_hash = validate_review_plan(root)
    resources[str(plan_path)] = plan_hash
    review = read(fitting_review, resources)
    if (review["status"] != "completed-fitting-review"
            or set(review["models"]) != set(SEEDS) or review["acceptance"] is not False):
        raise ValueError("completed fitting review required before diagnostic access")
    for path, expected in review["resources"].items():
        if sha(Path(path)) != expected:
            raise ValueError("reviewed fitting resource changed")
    expected_completion = {"status": "frozen-model-diagnostic-complete", "fits_evaluated": 20,
                           "fitting": False, "acceptance": False}
    manifests = []
    for name in ("hog26_seed_transfer_evaluation_20260911", "hog26_scaling_seed_transfer_evaluation_20260912"):
        directory = root / "reports" / name
        if read(directory / "complete.json", resources) != expected_completion:
            raise ValueError("all 20 original and scaled evaluations must complete")
        manifest = read(directory / "evaluation_manifest.json", resources)
        if manifest["fitting"] is not False or manifest["acceptance"] is not False:
            raise ValueError("unexpected evaluation scope")
        manifests.append(manifest)
        expected_files = {"complete.json", "evaluation_manifest.json"}
        for model, seeds in SEEDS.items():
            for seed in seeds:
                for fold in range(4):
                    stem = f"{model}-seed{seed}-fold{fold}"
                    expected_files.update({stem + "-report.json", stem + "-predictions.npz"})
        actual_files = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        if actual_files != expected_files:
            raise ValueError("unexpected diagnostic output inventory")
        for name in sorted(expected_files):
            path = directory / name
            resources[str(path)] = sha(path)
    if (manifests[0]["data_audit"] != manifests[1]["data_audit"]
            or manifests[0]["plan_sha256"] != manifests[1]["plan_sha256"]):
        raise ValueError("diagnostic cohorts differ")
    for manifest in manifests:
        for resource in manifest["model_resources"].values():
            if sha(Path(resource["path"])) != resource["sha256"]:
                raise ValueError("pinned diagnostic model resource changed")
    return manifests[0]["data_audit"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--fitting-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing existing transfer review")
    root, resources = args.root.resolve(), {}
    expected_audit = prerequisites(root, args.fitting_review.resolve(), resources)
    # Import and corpus access occur only after both evaluations and the fit review.
    from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
    from transfer_dataset import load_complete_pilot

    games, _, audit = load_complete_pilot(
        root / "datasets/derived/hog26_seed_transfer_seed1279601_20260911",
        plan_path=root / "reports/hog26_seed_transfer_frozen_plan_20260911.json",
        preflight_path=root / "reports/hog26_seed_transfer_preflight_pin_20260911.json",
    )
    if audit != expected_audit:
        raise ValueError("paired diagnostic corpus audit differs")
    lengths = [len(g.public["global_features"]) for g in games]
    ids = np.repeat(np.arange(len(games)), lengths)
    progress = np.concatenate([g.public["global_features"][:, 0] for g in games])
    labels = np.repeat([g.target_class for g in games], lengths)
    target = np.repeat([g.target_margin for g in games], lengths)
    seats = np.repeat([g.seat for g in games], lengths)
    styles = np.repeat([g.style for g in games], lengths)
    families = np.repeat([g.family for g in games], lengths)
    clusters = np.repeat([g.cluster for g in games], lengths)
    folds = np.array([int(f[-3:]) // 2 for f in families])
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f"family/{f}": families == f for f in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    del games
    models = {}
    for model, seeds in SEEDS.items():
        models[model] = []
        for seed in seeds:
            for fold in range(4):
                stem = f"{model}-seed{seed}-fold{fold}"
                old_dir = root / "reports/hog26_seed_transfer_evaluation_20260911"
                new_dir = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
                old_report = read(old_dir / (stem + "-report.json"), resources)
                new_report = read(new_dir / (stem + "-report.json"), resources)
                with np.load(old_dir / (stem + "-predictions.npz"), allow_pickle=False) as old:
                    old_p, old_m = old["probabilities"].astype(np.float64), old["margin"]
                with np.load(new_dir / (stem + "-predictions.npz"), allow_pickle=False) as new:
                    new_p, new_m = new["probabilities"].astype(np.float64), new["margin"]
                result = {"seed": seed, "fold": fold, "groups": {}}
                for group, group_mask, expected_games in (
                    ("fresh_seen_families", folds != fold, 288),
                    ("fresh_excluded_families", folds == fold, 96),
                ):
                    result["groups"][group] = {}
                    for distribution in ("all_states", "representatives"):
                        current, previous = new_report[group][distribution], old_report[group][distribution]
                        if (current["overall"]["coverage"]["games"] != expected_games
                                or previous["overall"]["coverage"]["games"] != expected_games
                                or set(current) != set(slices) or set(previous) != set(slices)):
                            raise ValueError("diagnostic slice inventory or counts differ")
                        reviewed = summarize_slices(current)
                        for name, row in reviewed.items():
                            if row.get("coverage") != previous[name].get("coverage"):
                                raise ValueError("paired slice coverage differs")
                            row["original_384_game_fit"] = previous[name]
                            if "metrics" not in row:
                                continue
                            weights = evaluation_weights(ids, progress, slices[name] & group_mask,
                                                         representative=distribution == "representatives", index=index)
                            row["paired_scaling_change"] = paired_error_intervals(
                                old_p, new_p, old_m, new_m, labels, target, weights, clusters,
                            )
                            row["new_minus_old_metric_points"] = {
                                key: value - previous[name]["metrics"][key]
                                for key, value in row["metrics"].items()
                                if isinstance(value, (int, float))
                                and isinstance(previous[name]["metrics"].get(key), (int, float))
                            }
                            for reduction, metric in (("nll_reduction", "nll"),
                                                      ("brier_reduction", "brier"),
                                                      ("margin_mae_reduction", "margin_mae")):
                                computed = row["paired_scaling_change"]["metrics"][reduction]["point"]
                                reported = -row["new_minus_old_metric_points"][metric]
                                if not np.isclose(computed, reported, rtol=1e-9, atol=1e-10):
                                    raise ValueError("paired error change differs from published metrics")
                            for key, value in row["paired_scaling_change"]["metrics"].items():
                                if value["point"] < 0:
                                    row["review_flags"].append(key + "-worse-than-original-fit")
                                if value["lower_95"] <= 0:
                                    row["review_flags"].append(key + "-scaling-improvement-not-established")
                        result["groups"][group][distribution] = reviewed
                models[model].append(result)
                print(json.dumps({"model": model, "seed": seed, "fold": fold, "status": "paired-review-complete"}), flush=True)
    for path, expected in resources.items():
        if sha(Path(path)) != expected:
            raise ValueError("review resource changed")
    output = {
        "status": "completed-scaling-transfer-review", "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "data_audit": audit, "models": models, "resources": resources,
        "review_sources": {p.name: sha(p) for p in Path(__file__).parent.glob("*.py")},
        "limitations": [
            "Opened diagnostic evidence only; all seeds and folds retained, with no fitting or selection.",
            "Paired intervals cover NLL, Brier, and margin MAE reductions only. Other metric changes are point estimates.",
            "NLL reductions compare model log loss directly; each model's separate prior gain uses its original training prior.",
            "Fixed epochs with four times as many games also increase optimizer updates; this does not isolate data from compute.",
            "Shared scenarios and overlapping training folds make the 20 fits dependent, not 20 independent replications.",
            "Clustered intervals do not remedy missing decisive outcomes or natural draws, and are not simultaneous intervals.",
        ],
        "fitting": False, "acceptance": False, "policy_updates_allowed": False,
    }
    with args.output.open("x") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
