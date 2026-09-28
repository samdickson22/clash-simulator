"""Close all sixteen diagnostic evaluations without dropping empty or failed slices."""

import json
from pathlib import Path

import numpy as np
from evaluate_weighted import check_resources, sources
from review_completed import summarize_slices, validate_predictions
from terminal_labels import sha


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_weighted_margin_diagnostic_review_20260913.json"
    if output.exists():
        raise ValueError("preserve existing weighted diagnostic review")
    directory = root / "reports/hog26_weighted_margin_seed_transfer_20260913"
    pin_path = root / "reports/hog26_weighted_margin_evaluation_pin_20260913.json"
    pin = json.loads(pin_path.read_text())
    if pin["evaluation_sources"] != sources():
        raise ValueError("weighted evaluator source changed")
    check_resources(pin["resources"])
    if json.loads((directory / "complete.json").read_text()) != {
            "status": "weighted-margin-diagnostic-complete", "fits": 16, "fitting": False, "acceptance": False}:
        raise ValueError("all sixteen diagnostic evaluations required")
    manifest_path = directory / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    reference = root / "reports/hog26_scaling_seed_transfer_evaluation_20260912"
    original_manifest = json.loads((reference / "evaluation_manifest.json").read_text())
    if (manifest["pin"] != pin or manifest["pin_sha256"] != sha(pin_path)
            or manifest["data_audit"] != original_manifest["data_audit"]
            or manifest["models"] != ["numeric", "semantic"] or manifest["fitting"] or manifest["acceptance"]):
        raise ValueError("weighted diagnostic authority differs")
    expected = {"complete.json", "evaluation_manifest.json"}
    records = {}
    for kind in ("numeric", "semantic"):
        records[kind] = {}
        expected.update({f"{kind}/complete.json", f"{kind}/evaluation_manifest.json"})
        if json.loads((directory / kind / "complete.json").read_text()) != {
                "status": "weighted-margin-model-diagnostic-complete", "model": kind, "fits": 8,
                "fitting": False, "acceptance": False}:
            raise ValueError("weighted model diagnostic completion differs")
        if json.loads((directory / kind / "evaluation_manifest.json").read_text()) != {
                "model": kind, "root_manifest_sha256": sha(manifest_path), "inputs": 425 if kind == "numeric" else 809}:
            raise ValueError("weighted model diagnostic manifest differs")
        for seed in (1279501, 1279502):
            for fold in range(4):
                stem = f"seed{seed}-fold{fold}"
                expected.update({f"{kind}/{stem}-predictions.npz", f"{kind}/{stem}-report.json"})
                path = directory / kind / (stem + "-predictions.npz")
                validate_predictions(path, 155496)
                with np.load(path, allow_pickle=False) as candidate, np.load(
                        reference / ("globals-" + stem + "-predictions.npz"), allow_pickle=False) as globals_:
                    if not np.array_equal(candidate["probabilities"], globals_["probabilities"]):
                        raise ValueError("weighted diagnostic WDL reference changed")
                report = json.loads((directory / kind / (stem + "-report.json")).read_text())
                original = json.loads((reference / ("globals-" + stem + "-report.json")).read_text())
                if set(report) != set(pin["groups"]):
                    raise ValueError("weighted diagnostic groups differ")
                record = {}
                for group, distributions in report.items():
                    if set(distributions) != {"all_states", "representatives"}:
                        raise ValueError("weighted diagnostic distributions differ")
                    record[group] = {}
                    for distribution, slices in distributions.items():
                        if (len(slices) != 60 or set(slices) != set(original[group][distribution])
                                or slices["overall"]["coverage"]["games"] != pin["groups"][group]):
                            raise ValueError("weighted diagnostic slice inventory differs")
                        for name, row in slices.items():
                            old = original[group][distribution][name]
                            if row.get("coverage") != old.get("coverage"):
                                raise ValueError("weighted diagnostic coverage differs")
                            if "metrics" not in row:
                                continue
                            for metric in ("nll", "brier"):
                                if not np.isclose(row["metrics"][metric], old["metrics"][metric], rtol=1e-12, atol=1e-12):
                                    raise ValueError("weighted WDL point metrics differ")
                            for key in ("paired_margin_reduction_vs_original_sampler", "paired_margin_reduction_vs_scaled_tree"):
                                change = row[key]
                                if (not all(np.isfinite(change[k]) for k in ("point", "lower_95", "upper_95"))
                                        or change["lower_95"] > change["upper_95"]):
                                    raise ValueError("invalid paired weighted margin interval")
                        record[group][distribution] = {"summary": summarize_slices(slices), "slices": slices}
                records[kind][stem] = record
    if len(expected) != 38 or {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()} != expected:
        raise ValueError("weighted diagnostic artifact inventory differs")
    inventory = {str(directory / name): sha(directory / name) for name in sorted(expected)}
    check_resources(pin["resources"])
    with output.open("x") as stream:
        json.dump({"status": "completed-weighted-margin-diagnostic-review", "fits": 16, "artifact_count": 38,
                   "evaluation_pin_sha256": sha(pin_path), "data_audit": manifest["data_audit"],
                   "sources_and_references_unchanged": True, "wdl_reference_exact": True,
                   "records": records, "inventory": inventory, "acceptance": False,
                   "limitations": ["Opened diagnostic comparisons do not establish acceptance.",
                                   "Late diagnostic coverage remains sparse, with only one win-containing paired cluster.",
                                   "No new WDL model was fitted; classification evidence is reused."]}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": "completed-weighted-margin-diagnostic-review", "fits": 16}), flush=True)


if __name__ == "__main__":
    main()
