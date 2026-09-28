"""Summarize the complete tree probe without promoting a model."""

import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "reports/hog26_corrected_tree_margin_screen_20260909.json"
    report = json.loads(source.read_text())
    results = []
    for result in report["results"]:
        folds = [{"families": fold["held_out_families"],
                  "fitting_late": fold["fit"]["by_phase"]["late"],
                  "out_of_fold_late": fold["out_of_fold"]["by_phase"]["late"],
                  "out_of_fold_overall": fold["out_of_fold"]["overall"]}
                 for fold in result["folds"]]
        results.append({"seed": result["seed"], "pooled": result["pooled"],
                        "full_phase": result["full_phase_out_of_fold"], "folds": folds,
                        "all_fitting_late_gains_nonnegative": all(
                            row["fitting_late"]["mae_improvement"] >= 0 for row in folds),
                        "all_excluded_family_late_gains_nonnegative": all(
                            row["out_of_fold_late"]["mae_improvement"] >= 0 for row in folds)})
    destination = root / "reports/hog26_corrected_tree_margin_diagnosis_20260909.json"
    with destination.open("x") as stream:
        json.dump({"status": "training-only diagnosis; no candidate promotion",
                   "source_report": str(source.relative_to(root)),
                   "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "seed_predictions_identical": all(
                       row["predictions"] == report["results"][0]["predictions"]
                       for row in report["results"][1:]),
                   "interpretation_limit": "Fitting success does not establish excluded-family performance. These training-family diagnostics do not replace independent calibration or counterfactual ranking gates.",
                   "results": results}, stream, indent=2)
        stream.write("\n")
    for result in results:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
