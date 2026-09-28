"""Retain every fixed weighted-margin result, including all failed slices."""

import json
from pathlib import Path

import torch
from fit_authority_weighted import pin_fits
from review_completed import summarize_slices
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_weighted_margin_fitting_review_20260913.json"
    if output.exists():
        raise ValueError("preserve existing weighted fitting review")
    plan, _, manifest, resources = pin_fits(root)
    directory = root / "reports/hog26_weighted_margin_comparison_20260913"
    tree_path = root / "reports/hog26_scaling_tree_comparison_20260912/seed1279501-summary.json"
    tree = json.loads(tree_path.read_text())
    resources[str(tree_path)] = sha(tree_path)
    results = {}
    for kind in plan.models:
        results[kind] = {}
        old_name = "hog26_residual_margin_comparison_20260912" if kind == "numeric" else "hog26_semantic_margin_comparison_20260912"
        for seed in plan.seeds:
            old_path = root / "reports" / old_name / f"seed{seed}-summary.json"
            original = json.loads(old_path.read_text())
            resources[str(old_path)] = sha(old_path)
            summary = json.loads((directory / kind / f"seed{seed}-summary.json").read_text())
            if set(summary) != {"all_states", "representatives"}:
                raise ValueError("missing weighted margin distribution")
            row = {"out_of_fold": {}, "folds": [], "point_changes": {}}
            for distribution, slices in summary.items():
                if set(slices) != set(original[distribution]) or set(slices) != set(tree[distribution]) or len(slices) != 60:
                    raise ValueError("weighted fitting slice inventory differs")
                row["out_of_fold"][distribution] = summarize_slices(slices)
                changes = {}
                for name, value in slices.items():
                    if value.get("coverage") != original[distribution][name].get("coverage"):
                        raise ValueError("weighted comparison coverage differs")
                    if "metrics" in value:
                        changes[name] = {"vs_original_sampler": original[distribution][name]["metrics"]["margin_mae"] - value["metrics"]["margin_mae"],
                                         "vs_tree": tree[distribution][name]["metrics"]["margin_mae"] - value["metrics"]["margin_mae"]}
                row["point_changes"][distribution] = changes
            for fold in range(4):
                report = json.loads((directory / kind / f"seed{seed}-fold{fold}-report.json").read_text())
                if report["fold"] != fold:
                    raise ValueError("weighted fold identity differs")
                fold_row = {"fold": fold}
                for group, count in (("fitting", 1152), ("excluded", 384)):
                    if set(report[group]) != set(summary):
                        raise ValueError("missing weighted fold distribution")
                    fold_row[group] = {}
                    for distribution, slices in report[group].items():
                        if set(slices) != set(summary[distribution]) or slices["overall"]["coverage"]["games"] != count:
                            raise ValueError("weighted fold slices or cohort count differs")
                        fold_row[group][distribution] = summarize_slices(slices)
                row["folds"].append(fold_row)
            results[kind][str(seed)] = row
    if any(sha(path) != expected for path, expected in resources.items()):
        raise ValueError("weighted fitting resource changed during review")
    with output.open("x") as stream:
        json.dump({"status": "completed-weighted-margin-fitting-review", "fits": 16, "artifact_count": 62,
                   "wdl_reference_exact": True, "data_audit": manifest["data_audit"],
                   "results": results, "resources": resources, "acceptance": False,
                   "limitations": ["Training comparison point differences are not paired change intervals.",
                                   "All clustered gain intervals and all slices are retained; sparse coverage stays inconclusive.",
                                   "WDL is reused and supplies no independent classification evidence.",
                                   "No reserved-role changes or policy work follow from this review."]}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": "completed-weighted-margin-fitting-review", "fits": 16}), flush=True)


if __name__ == "__main__":
    main()
