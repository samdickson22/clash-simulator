"""Review every completed residual fit before opened diagnostic access."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from residual_authority import pin_completed_fits
from residual_contract import sha
from review_completed import summarize_slices


def read(path, resources):
    resources[str(path)] = sha(path)
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing existing residual review")
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    plan, manifest, resources = pin_completed_fits(root)
    directory = root / "reports/hog26_residual_margin_comparison_20260912"
    tree = read(root / "reports/hog26_scaling_tree_comparison_20260912/seed1279501-summary.json", resources)
    results = {}
    for seed in plan.training.seeds:
        summary = read(directory / f"seed{seed}-summary.json", resources)
        if set(summary) != {"all_states", "representatives"}:
            raise ValueError("missing residual evaluation distribution")
        item = {"out_of_fold": {}, "folds": [], "margin_change_vs_tree_points": {}}
        for distribution, slices in summary.items():
            if set(slices) != set(tree[distribution]):
                raise ValueError("missing residual evaluation slice")
            item["out_of_fold"][distribution] = summarize_slices(slices)
            changes = {}
            for name, value in slices.items():
                original = tree[distribution][name]
                if value.get("coverage") != original.get("coverage"):
                    raise ValueError("residual/tree evaluation coverage differs")
                if "metrics" in value:
                    changes[name] = original["metrics"]["margin_mae"] - value["metrics"]["margin_mae"]
            item["margin_change_vs_tree_points"][distribution] = changes
        for fold in range(4):
            report = read(directory / f"seed{seed}-fold{fold}-report.json", resources)
            if report["fold"] != fold:
                raise ValueError("residual fold identity differs")
            row = {"fold": fold, "fitting_and_prediction_seconds": report["fitting_and_prediction_seconds"]}
            for group, count in (("fitting", 1152), ("excluded", 384)):
                if set(report[group]) != set(summary):
                    raise ValueError("missing fitting/excluded distribution")
                row[group] = {}
                for distribution, slices in report[group].items():
                    if set(slices) != set(summary[distribution]) or slices["overall"]["coverage"]["games"] != count:
                        raise ValueError("residual fold slices or counts differ")
                    row[group][distribution] = summarize_slices(slices)
            item["folds"].append(row)
        results[str(seed)] = item
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("reviewed residual resource changed")
    result = {
        "status": "completed-residual-fitting-review", "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "model": plan.model.name, "fits": 8, "artifact_count": 30,
        "data_audit": manifest["data_audit"], "seeds": results, "resources": resources,
        "wdl_reference_exact": True,
        "limitations": [
            "WDL probabilities and OOF priors exactly match existing globals references; no new classification evidence.",
            "Tree margin differences here are point estimates, not paired change intervals.",
            "Per-fold fitting/excluded metrics are point estimates; combined summaries retain clustered intervals.",
            "Every phase, family, seat, style and joint slice is retained. Missing outcomes and coverage remain inconclusive.",
            "This diagnostic comparison cannot authorize reserved collection or policy updates.",
        ],
        "acceptance": False, "policy_updates_allowed": False,
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "fits": 8, "artifact_count": 30}), flush=True)


if __name__ == "__main__":
    main()
