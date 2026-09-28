"""Audit every semantic diagnostic artifact and retain both paired comparisons."""

import json
from pathlib import Path

import numpy as np
from evaluate_semantic import check_resources, sources
from review_completed import summarize_slices, validate_predictions
from semantic_contract import sha


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_semantic_margin_diagnostic_review_20260912.json"
    if output.exists():
        raise ValueError("preserve existing diagnostic review")
    directory = root / "reports/hog26_semantic_margin_seed_transfer_20260912"
    pin_path = root / "reports/hog26_semantic_margin_evaluation_pin_20260912.json"
    pin = json.loads(pin_path.read_text())
    if pin["evaluation_sources"] != sources():
        raise ValueError("semantic evaluation source changed")
    check_resources(pin["resources"])
    completion = json.loads((directory / "complete.json").read_text())
    if completion != {"status": "fixed-semantic-diagnostic-complete", "fits": 8,
                      "fitting": False, "acceptance": False}:
        raise ValueError("all eight semantic evaluations required")
    expected = {"complete.json", "evaluation_manifest.json"}
    expected.update(f"seed{seed}-fold{fold}-{suffix}"
                    for seed in (1279501, 1279502) for fold in range(4)
                    for suffix in ("predictions.npz", "report.json"))
    if {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()} != expected:
        raise ValueError("semantic diagnostic inventory differs")
    manifest = json.loads((directory / "evaluation_manifest.json").read_text())
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    reference_manifest = json.loads((reference / "evaluation_manifest.json").read_text())
    if (manifest["pin"] != pin or manifest["pin_sha256"] != sha(pin_path)
            or manifest["data_audit"] != reference_manifest["data_audit"]
            or manifest["fitting"] or manifest["acceptance"]):
        raise ValueError("semantic evaluation authority differs")
    records = {}
    for seed in (1279501, 1279502):
        for fold in range(4):
            stem = f"seed{seed}-fold{fold}"
            path = directory / (stem + "-predictions.npz")
            validate_predictions(path, 155496)
            with np.load(path, allow_pickle=False) as candidate, np.load(
                    reference / ("globals-" + stem + "-predictions.npz"), allow_pickle=False) as globals_:
                if not np.array_equal(candidate["probabilities"], globals_["probabilities"]):
                    raise ValueError("promised globals probabilities changed")
            report = json.loads((directory / (stem + "-report.json")).read_text())
            global_report = json.loads((reference / ("globals-" + stem + "-report.json")).read_text())
            if set(report) != set(pin["groups"]):
                raise ValueError("diagnostic groups differ")
            record = {}
            for group, distributions in report.items():
                if set(distributions) != {"all_states", "representatives"}:
                    raise ValueError("diagnostic distributions differ")
                record[group] = {}
                for distribution, slices in distributions.items():
                    original_slices = global_report[group][distribution]
                    if (set(slices) != set(original_slices) or len(slices) != 60
                            or slices["overall"]["coverage"]["games"] != pin["groups"][group]):
                        raise ValueError("diagnostic slices or cohort size differ")
                    for name, row in slices.items():
                        original = original_slices[name]
                        if row["coverage"] != original["coverage"]:
                            raise ValueError("diagnostic coverage differs")
                        if "metrics" not in row:
                            continue
                        for metric in ("nll", "brier"):
                            if not np.isclose(row["metrics"][metric], original["metrics"][metric], atol=1e-12, rtol=1e-12):
                                raise ValueError("unchanged WDL point differs")
                        for key in ("paired_margin_reduction_vs_scaled_tree", "paired_margin_reduction_vs_numeric_residual"):
                            if key not in row:
                                raise ValueError("missing paired comparison")
                    record[group][distribution] = {"summary": summarize_slices(slices), "slices": slices}
            records[stem] = record
    inventory = {str(directory / name): sha(directory / name) for name in sorted(expected)}
    check_resources(pin["resources"])
    result = {"status": "completed-semantic-diagnostic-review", "fits": 8, "artifact_count": 18,
              "data_audit": manifest["data_audit"], "evaluation_pin_sha256": sha(pin_path),
              "sources_and_references_unchanged": True, "wdl_probabilities_exact": True,
              "records": records, "inventory": inventory, "acceptance": False,
              "limitations": ["Opened diagnostic results are not acceptance evidence.",
                              "Late diagnostic coverage remains only 16 paired clusters with one win-containing cluster.",
                              "WDL is reused; this experiment supplies no new classification evidence."]}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "fits": 8}), flush=True)


if __name__ == "__main__":
    main()
