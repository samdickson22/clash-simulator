"""Audit completed fixed scaling stages without loading data or fitting models."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SEEDS = {"globals": [1279501, 1279502], "tree": [1279501], "entity": [1279501, 1279502]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, resources):
    raw = path.read_bytes()
    resources[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def validate_predictions(path, rows):
    with np.load(path, allow_pickle=False) as saved:
        expected = {"probabilities", "margin", "prior"} if path.name.endswith("-oof.npz") else {"probabilities", "margin"}
        if set(saved.files) != expected:
            raise ValueError("unexpected prediction archive fields")
        for key in expected:
            values = saved[key]
            shape = (rows,) if key == "margin" else (rows, 3)
            if values.shape != shape or not np.isfinite(values).all():
                raise ValueError("prediction rows or finite values differ")
            if key == "margin":
                if (np.abs(values) > 1 + 1e-6).any():
                    raise ValueError("margin prediction out of bounds")
            elif ((values < 0).any() or (values > 1).any()
                  or not np.allclose(values.sum(1), 1, atol=1e-6)):
                raise ValueError("invalid probability mass")


def summarize_slices(slices):
    """Keep every slice, its coverage, and its original clustered intervals."""
    result = {}
    for name, value in slices.items():
        row = dict(value)
        flags = []
        if "metrics" not in value:
            flags.append("inconclusive-empty")
        else:
            c, m = value["coverage"], value["metrics"]
            if not c["clusters_containing_loss"] or not c["clusters_containing_win"]:
                flags.append("inconclusive-missing-decisive-outcome")
            if c["scenario_clusters"] < 8:
                flags.append("below-protocol-eight-independent-cluster-floor")
            if min(c["clusters_containing_loss"], c["clusters_containing_win"]) < 2:
                flags.append("below-protocol-two-clusters-per-decisive-outcome-floor")
            if c["natural_draw_games"] == 0:
                flags.append("natural-draw-calibration-unmeasured")
            for metric in ("nll_gain", "margin_gain"):
                if m[metric] < 0:
                    flags.append(metric + "-negative-point-estimate")
                interval = value.get("intervals", {}).get("intervals", {}).get(metric)
                if interval is not None and interval["lower_95"] <= 0:
                    flags.append(metric + "-positive-improvement-not-established")
            if "intervals" not in value:
                flags.append("point-estimates-only")
        row["review_flags"] = flags
        result[name] = row
    return result


def review(root, models):
    resources, results = {}, {}
    protocol = read(root / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json", resources)
    comparison_path = root / "reports/hog26_scalar_pilot_comparison_plan_20260911.json"
    comparison = read(comparison_path, resources)
    collection_path = root / "reports/hog26_scaling_frozen_plan_20260912.json"
    read(collection_path, resources)
    expected_slices = {"overall"}
    expected_slices.update(f"fold/{fold}" for fold in range(4))
    expected_slices.update(f"seat/{seat}" for seat in (0, 1))
    expected_slices.update(f"style/{style}" for style in comparison["data"]["styles"])
    expected_slices.update(f"family/{family}" for family in comparison["data"]["families"])
    for phase in ("early", "middle", "late"):
        expected_slices.add(f"phase/{phase}")
        expected_slices.update(f"phase/{phase}/seat/{seat}/style/{style}"
                               for seat in (0, 1) for style in comparison["data"]["styles"])

    def validate_inventory(report):
        if set(report) != {"all_states", "representatives"}:
            raise ValueError("missing or unexpected evaluation distribution")
        if any(set(slices) != expected_slices for slices in report.values()):
            raise ValueError("missing or unexpected evaluation slice")

    coverage_rules = protocol["generalization_evaluation"]
    if (coverage_rules["minimum_independent_matchup_clusters_per_slice"] != 8
            or coverage_rules["minimum_clusters_with_each_decisive_outcome_per_slice"] != 2):
        raise ValueError("protocol coverage floors changed")
    shared_authority = None
    for model in models:
        directory = root / f"reports/hog26_scaling_{model}_comparison_20260912"
        completion = read(directory / "complete.json", resources)
        if completion != {
            "status": "diagnostic-comparison-complete", "model": model,
            "seeds": SEEDS[model], "draw_games": 0, "acceptance": False,
        }:
            raise ValueError(f"unexpected {model} completion")
        manifest = read(directory / "fitting_manifest.json", resources)
        keys = ("data_audit", "collection_plan_sha256", "comparison_sha256",
                "outcome_token_names", "vocabulary_sha256", "input_games",
                "implementation", "readiness_sha256", "scaling_readiness")
        authority = {k: manifest[k] for k in keys}
        if shared_authority is not None and authority != shared_authority:
            raise ValueError("completed stages disagree on fitting authority")
        shared_authority = authority
        if (authority["comparison_sha256"] != resources[str(comparison_path)]
                or authority["collection_plan_sha256"] != resources[str(collection_path)]):
            raise ValueError("frozen comparison or collection plan changed")
        if manifest["model"] != model:
            raise ValueError("manifest model mismatch")
        if (authority["data_audit"]["games"] != 1536
                or authority["data_audit"]["clusters"] != 768
                or authority["data_audit"]["rows"] != 618149
                or authority["data_audit"]["diagnostic_fitting_games"] != 0
                or len(authority["input_games"]) != 1536):
            raise ValueError("unexpected training inventory")
        for name, expected in authority["implementation"].items():
            if sha(root / "experiments/hog26_scaling_fit" / name) != expected:
                raise ValueError("fitting source changed")
        expected_files = {"complete.json", "fitting_manifest.json"}
        if model == "tree":
            expected_files.add("feature_names.json")
        model_result = {"seeds": {}}
        for seed in SEEDS[model]:
            stem = f"seed{seed}"
            expected_files.update({stem + "-summary.json", stem + "-oof.npz"})
            summary = read(directory / (stem + "-summary.json"), resources)
            previous = read(root / f"reports/hog26_scalar_birthfixed_{model}_comparison_20260911"
                            / (stem + "-summary.json"), resources)
            validate_inventory(summary)
            validate_inventory(previous)
            seed_result = {"out_of_fold": {}, "folds": [], "change_from_384_games": {}}
            for distribution, slices in summary.items():
                if slices["overall"]["coverage"]["games"] != 1536:
                    raise ValueError("incomplete out-of-fold coverage")
                seed_result["out_of_fold"][distribution] = summarize_slices(slices)
                changes = {}
                for name, value in slices.items():
                    old = previous[distribution].get(name, {})
                    if "metrics" in value and "metrics" in old:
                        changes[name] = {
                            "metric_delta": {k: value["metrics"][k] - old["metrics"][k]
                                             for k in value["metrics"]
                                             if isinstance(value["metrics"][k], (int, float))
                                             and isinstance(old["metrics"].get(k), (int, float))},
                            "previous_coverage": old["coverage"],
                            "current_coverage": value["coverage"],
                        }
                seed_result["change_from_384_games"][distribution] = changes
            for fold in range(4):
                fold_stem = stem + f"-fold{fold}"
                expected_files.update({fold_stem + "-report.json", fold_stem + "-predictions.npz",
                                       fold_stem + (".pkl" if model == "tree" else ".pt")})
                report = read(directory / (fold_stem + "-report.json"), resources)
                if report["fold"] != fold:
                    raise ValueError("fold identity mismatch")
                validate_inventory(report["fitting"])
                validate_inventory(report["excluded"])
                item = {"fold": fold, "elapsed_seconds": report["elapsed_seconds"], "distributions": {}}
                for distribution in summary:
                    fitting, excluded = report["fitting"][distribution], report["excluded"][distribution]
                    if (fitting["overall"]["coverage"]["games"] != 1152
                            or excluded["overall"]["coverage"]["games"] != 384):
                        raise ValueError("fold game counts differ")
                    gaps = {}
                    for name, value in excluded.items():
                        fit = fitting.get(name, {})
                        if "metrics" in value and "metrics" in fit:
                            gaps[name] = {k: value["metrics"][k] - fit["metrics"][k]
                                          for k in ("nll", "margin_mae")}
                    item["distributions"][distribution] = {
                        "fitting": summarize_slices(fitting),
                        "excluded": summarize_slices(excluded),
                        "excluded_minus_fitting_error": gaps,
                    }
                seed_result["folds"].append(item)
            model_result["seeds"][str(seed)] = seed_result
        actual_files = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        if actual_files != expected_files:
            raise ValueError(f"unexpected {model} files: {actual_files ^ expected_files}")
        for name in sorted(expected_files):
            path = directory / name
            resources[str(path)] = sha(path)
            if path.suffix == ".npz":
                validate_predictions(path, authority["data_audit"]["rows"])
        model_result["artifact_count"] = len(expected_files)
        model_result["prediction_archives_validated"] = True
        results[model] = model_result
    for path, expected in resources.items():
        if sha(Path(path)) != expected:
            raise ValueError("review input changed during review")
    return {
        "scope": "Fixed data-scaling diagnostic comparison; no candidate selection or acceptance.",
        "status": "completed-fitting-review" if set(models) == set(SEEDS) else "preliminary-completed-stage-review",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "data_audit": shared_authority["data_audit"],
        "models": results, "resources": resources,
        "review_source_sha256": sha(Path(__file__)),
        "limitations": [
            "Point deltas from 384 to 1536 games compare different out-of-fold populations and are not paired scaling-effect intervals.",
            "Fixed epochs with more games increase optimizer updates, so this does not isolate data from compute.",
            "Out-of-fold intervals use paired-scenario clusters; per-fold fitting comparisons are point estimates only.",
            "Each slice retains coverage and regressions; pooled improvement cannot pass a missing or regressing required slice.",
            "Zero natural draws leave natural-draw calibration unmeasured.",
            "The opened fresh-seed diagnostic remains excluded from fitting and is not untouched acceptance evidence.",
        ],
        "acceptance": False, "policy_updates_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--models", nargs="+", choices=tuple(SEEDS), default=list(SEEDS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite an existing review")
    result = review(args.root.resolve(), args.models)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "models": args.models,
                      "output": str(args.output), "acceptance": False}))


if __name__ == "__main__":
    main()
