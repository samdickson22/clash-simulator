"""Reproduce all auxiliary predictions from checkpoints before interpreting them."""

import json
from pathlib import Path

import numpy as np
import torch
from sampled_contract import load_plan, publish, sources
from sampled_experiment import prepare, validate_readiness
from sampled_model import TerminalPredictor, predict
from scalar_evaluation import phase_ids
from terminal_labels import sha
from terminal_metrics import report


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_terminal_weighted_sampler_fitting_review_20260912.json"
    if output.exists():
        raise ValueError("preserve existing auxiliary review")
    plan_path = root / "reports/hog26_terminal_weighted_sampler_frozen_plan_20260912.json"
    plan = load_plan(plan_path)
    review_pin = root / "reports/hog26_terminal_weighted_sampler_review_pin_20260912.json"
    pin = json.loads(review_pin.read_text())
    if pin["review_source_sha256"] != sha(__file__) or pin["fitting_plan_sha256"] != sha(plan_path):
        raise ValueError("predeclared auxiliary review source differs")
    directory = root / "reports/hog26_terminal_weighted_sampler_comparison_20260912"
    completion = json.loads((directory / "complete.json").read_text())
    if completion != {"status": "auxiliary-terminal-comparison-complete", "fits": 8,
                      "acceptance": False, "outcome_model_changed": False}:
        raise ValueError("all eight auxiliary fits must complete")
    readiness_path = root / "reports/hog26_terminal_weighted_sampler_readiness_20260912.json"
    readiness = validate_readiness(readiness_path, plan, plan_path)
    expected = {"complete.json", "fitting_manifest.json"}
    for seed in plan.seeds:
        expected.update({f"seed{seed}-oof.npz", f"seed{seed}-summary.json"})
        for fold in range(4):
            stem = f"seed{seed}-fold{fold}"
            expected.update({stem + ".pt", stem + "-predictions.npz", stem + "-report.json"})
    if {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()} != expected:
        raise ValueError("auxiliary artifact inventory differs")
    inventory = {str(directory / name): sha(directory / name) for name in sorted(expected)}
    manifest = json.loads((directory / "fitting_manifest.json").read_text())
    if (manifest["plan"] != plan.model_dump(mode="json") or manifest["plan_sha256"] != sha(plan_path)
            or manifest["sources"] != sources() or manifest["readiness"] != readiness
            or manifest["feature_sha256"] != plan.feature_sha256 or manifest["label_sha256"] != plan.label_sha256):
        raise ValueError("auxiliary fitting authority differs")
    data, labels = prepare(plan)
    if data.input_games != manifest["input_games"] or data.audit != manifest["data_audit"]:
        raise ValueError("review corpus differs")
    results = {}
    phases = phase_ids(data.evaluation[1])
    for seed in plan.seeds:
        oof, oof_prior = np.full(len(labels), np.nan), np.full(len(labels), np.nan)
        phase_prior_oof = np.full(len(labels), np.nan)
        folds = []
        for fold in data.folds:
            stem = f"seed{seed}-fold{fold.fold}"
            model = TerminalPredictor()
            model.load_state_dict(torch.load(directory / (stem + ".pt"), weights_only=True, map_location="cpu"))
            model.eval()
            probability = predict(model, data.features)
            with np.load(directory / (stem + "-predictions.npz"), allow_pickle=False) as saved:
                if set(saved.files) != {"terminal_probability"} or not np.array_equal(saved["terminal_probability"], probability):
                    raise ValueError("checkpoint does not reproduce saved auxiliary predictions")
            prior = float(np.sum(labels[fold.mask] * fold.margin_weights[fold.mask]))
            phase_prior = np.empty(len(labels))
            for phase in range(3):
                selected = fold.mask & (phases == phase)
                mass = fold.margin_weights[selected]
                frequency = float(np.sum(labels[selected] * mass) / mass.sum())
                if not 0 < frequency < 1:
                    raise ValueError("phase reference requires both terminal classes")
                phase_prior[phases == phase] = frequency
            recomputed = {"fold": fold.fold, "fitting_weighted_prior": prior,
                          "fitting": report(data.evaluation, labels, probability, prior, fold.mask),
                          "excluded": report(data.evaluation, labels, probability, prior, ~fold.mask)}
            saved_report = json.loads((directory / (stem + "-report.json")).read_text())
            if recomputed != saved_report:
                raise ValueError("auxiliary fold report does not reproduce")
            folds.append(saved_report)
            oof[~fold.mask], oof_prior[~fold.mask] = probability[~fold.mask], prior
            phase_prior_oof[~fold.mask] = phase_prior[~fold.mask]
            print(json.dumps({"seed": seed, "fold": fold.fold, "status": "checkpoint-and-report-reproduced"}), flush=True)
        with np.load(directory / f"seed{seed}-oof.npz", allow_pickle=False) as saved:
            if (set(saved.files) != {"terminal_probability", "prior"}
                    or not np.array_equal(saved["terminal_probability"], oof)
                    or not np.array_equal(saved["prior"], oof_prior)):
                raise ValueError("OOF composition differs")
        summary = report(data.evaluation, labels, oof, oof_prior, intervals=True)
        if summary != json.loads((directory / f"seed{seed}-summary.json").read_text()):
            raise ValueError("OOF metrics or clustered intervals do not reproduce")
        results[str(seed)] = {"out_of_fold": summary, "folds": folds,
                              "out_of_fold_vs_phase_only_prior": report(
                                  data.evaluation, labels, oof, phase_prior_oof, intervals=True)}
        original_directory = root / "reports/hog26_terminal_auxiliary_comparison_20260912"
        with np.load(original_directory / f"seed{seed}-oof.npz", allow_pickle=False) as original:
            if not np.array_equal(original["prior"], oof_prior):
                raise ValueError("sampler comparison fitting priors differ")
            old_probability = original["terminal_probability"]
        paired = report(data.evaluation, labels, oof, np.clip(old_probability, 1e-12, 1 - 1e-12), intervals=True)
        original_report = json.loads((original_directory / f"seed{seed}-summary.json").read_text())
        for distribution, slices in paired.items():
            if set(slices) != set(original_report[distribution]):
                raise ValueError("sampler paired slices differ")
            for name, row in slices.items():
                if "metrics" not in row:
                    continue
                old_row = original_report[distribution][name]
                if any(row[key] != old_row[key] for key in ("rows", "clusters", "positive_clusters", "negative_clusters")):
                    raise ValueError("sampler paired coverage differs")
                expected_gain = old_row["metrics"]["nll"] - summary[distribution][name]["metrics"]["nll"]
                if not np.isclose(row["metrics"]["nll_gain"], expected_gain, atol=1e-12, rtol=1e-12):
                    raise ValueError("paired NLL gain does not reproduce report points")
        results[str(seed)]["paired_nll_vs_original_sampler"] = paired
    load_plan(plan_path)
    if any(sha(path) != expected_hash for path, expected_hash in inventory.items()):
        raise ValueError("auxiliary artifact changed during review")
    publish(output, {"status": "completed-weighted-sampler-terminal-fitting-review", "fits": 8,
                     "artifact_count": 30, "checkpoint_predictions_exact": True,
                     "fold_reports_exact": True, "oof_and_intervals_exact": True,
                     "plan_sha256": sha(plan_path), "inventory": inventory,
                     "review_source_sha256": sha(__file__), "results": results,
                     "review_pin_sha256": sha(review_pin),
                     "acceptance": False, "outcome_model_changed": False,
                     "limitations": ["Training-family cross-validation only; opened diagnostic and reserved data untouched.",
                                     "This behavior-policy-dependent binary target is not WDL or terminal-margin acceptance.",
                                     "Fitting uses the margin mixture weights; assess both reporting distributions separately."]})
    print(json.dumps({"status": "completed-weighted-sampler-terminal-fitting-review", "fits": 8}), flush=True)


if __name__ == "__main__":
    main()
