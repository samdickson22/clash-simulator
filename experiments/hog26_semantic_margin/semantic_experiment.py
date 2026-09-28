"""Probe memory, publish readiness, or run the single fixed residual comparison."""

import argparse
import json
import resource
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from body_features import feature_names
from run_scaling_comparison import report_predictions
from scalar_evaluation import empirical_prior
from semantic_contract import (
    MEMORY_LIMIT,
    load_plan,
    runtime_signature,
    sha,
    source_inventory,
)
from semantic_data import prepare_data
from semantic_training import (
    SemanticResidualMargin,
    fit_residual,
    make_optimizer,
    predict_margin,
    training_step,
)


def publish(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def validate_memory(report, plan, plan_path):
    if (report.get("status") != "passed-synthetic-memory-audit"
            or report.get("plan_sha256") != sha(plan_path)
            or report.get("implementation") != source_inventory()
            or report.get("runtime") != runtime_signature()
            or report.get("data_audit") != plan.data.expected_audit
            or report.get("feature_shape") != [618149, 809]
            or report.get("feature_matrix_bytes") != 618149 * 809 * 4
            or not 0 < report.get("peak_rss_bytes", 0) < MEMORY_LIMIT
            or report.get("parameters") != 27009
            or report.get("synthetic_batch_rows") != 512
            or report.get("finite_gradients") is not True
            or report.get("optimizer_step") is not True
            or report.get("initial_baseline_max_abs_difference") != 0.0
            or report.get("outcome_fitting") is not False
            or report.get("saved_model") is not False):
        raise ValueError("memory report does not establish fixed residual readiness")
    digest = report.get("feature_matrix_sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("missing feature matrix authority")
    if digest != plan.features.matrix_sha256:
        raise ValueError("memory features differ from public-only audit")


def validate_readiness(path, plan, plan_path):
    readiness = json.loads(Path(path).read_text())
    if readiness.get("status") != "passed" or readiness.get("plan_sha256") != sha(plan_path):
        raise ValueError("passed matching residual readiness required")
    report_path = Path(readiness["memory_report_path"])
    if sha(report_path) != readiness["memory_report_sha256"]:
        raise ValueError("underlying residual memory report changed")
    report = json.loads(report_path.read_text())
    validate_memory(report, plan, plan_path)
    if readiness.get("feature_matrix_sha256") != report["feature_matrix_sha256"]:
        raise ValueError("readiness feature authority differs")
    return readiness, report


def memory_probe(plan, plan_path, output):
    data = prepare_data(plan)
    current = data.evaluation[4]
    torch.manual_seed(1279801)
    model = SemanticResidualMargin()
    parameters = sum(p.numel() for p in model.parameters())
    baseline = predict_margin(model, data.features, current)
    difference = float(np.max(np.abs(baseline - current)))
    # Commit the same real-size buffers used by the fitting runner.
    oof_probability = np.full((len(current), 3), np.nan)
    oof_margin = np.full(len(current), np.nan)
    oof_prior = np.full((len(current), 3), np.nan)
    largest = max(data.folds, key=lambda fold: len(fold.indices))
    selected = largest.indices[:512]
    optimizer = make_optimizer(model)
    objective = training_step(
        model, optimizer, torch.from_numpy(data.features[selected]),
        torch.full((512,), .125),
        torch.from_numpy(largest.margin_weights[selected].astype(np.float32)), len(largest.indices),
    )
    finite = all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters())
    changed = bool(model.network[-1].bias.detach().abs().sum() > 0)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    # Keep buffers live through peak capture without using corpus outcomes as targets.
    assert oof_probability.shape[0] == oof_margin.shape[0] == oof_prior.shape[0]
    report = {
        "status": "passed-synthetic-memory-audit", "plan_sha256": sha(plan_path),
        "implementation": source_inventory(), "runtime": runtime_signature(),
        "data_audit": data.audit, "feature_shape": list(data.features.shape),
        "feature_matrix_bytes": data.features.nbytes, "feature_matrix_sha256": data.feature_sha256,
        "parameters": parameters, "synthetic_batch_rows": 512, "finite_gradients": finite,
        "optimizer_step": changed, "synthetic_objective": objective,
        "initial_baseline_max_abs_difference": difference, "peak_rss_bytes": int(peak),
        "memory_limit_bytes": MEMORY_LIMIT, "outcome_fitting": False, "saved_model": False,
        "scope": "Full audited corpus and feature construction, real-size evaluation buffers, full initial prediction and maximal synthetic optimizer step. No outcome model saved.",
    }
    try:
        load_plan(plan_path)
        validate_memory(report, plan, plan_path)
    except Exception as error:
        report["status"] = "failed-synthetic-memory-audit"
        report["failure"] = f"{type(error).__name__}: {error}"
        publish(output, report)
        raise
    publish(output, report)
    print(json.dumps({"status": report["status"], "peak_rss_bytes": peak,
                      "feature_shape": report["feature_shape"]}), flush=True)


def run_fit(plan, plan_path, readiness_path, output):
    readiness, memory = validate_readiness(readiness_path, plan, plan_path)
    data = prepare_data(plan)
    if data.feature_sha256 != memory["feature_matrix_sha256"]:
        raise ValueError("fitting features differ from measured memory audit")
    reference_path = Path(plan.data.globals_directory) / "fitting_manifest.json"
    reference = json.loads(reference_path.read_text())
    output.mkdir()
    publish(output / "fitting_manifest.json", {
        "model": plan.model.name, "plan_sha256": sha(plan_path), "plan": plan.model_dump(mode="json"),
        "data_audit": data.audit, "input_games": data.input_games,
        "outcome_token_names": list(plan.data.vocabulary),
        "feature_layout": {"numeric_prefix": asdict(data.layout), "physical_names": feature_names()},
        "feature_matrix_sha256": data.feature_sha256, "implementation": source_inventory(),
        "runtime": runtime_signature(), "readiness": readiness, "readiness_sha256": sha(readiness_path),
        "paired_globals_manifest_sha256": sha(reference_path),
        "paired_globals_input_games": reference["input_games"], "parameters": 27009,
        "wdl_fitting": False, "acceptance": False,
    })
    ids, _, labels, target, current, *_ = data.evaluation
    residual_target = np.asarray(target - current, dtype=np.float32)
    for seed in plan.training.seeds:
        oof_p = np.full((len(ids), 3), np.nan)
        oof_m = np.full(len(ids), np.nan)
        oof_prior = np.full((len(ids), 3), np.nan)
        for fold in data.folds:
            load_plan(plan_path)
            stem = f"seed{seed}-fold{fold.fold}"
            began = time.monotonic()

            def log(row, seed=seed, fold=fold):
                print(json.dumps({"seed": seed, "fold": fold.fold, **row}), flush=True)

            model = fit_residual(data.features, fold.indices, residual_target, fold.margin_weights,
                                 seed=seed + fold.fold, epochs=plan.training.epochs,
                                 batch_rows=plan.training.batch_rows, log=log)
            margin = predict_margin(model, data.features, current)
            paired_path = Path(plan.data.globals_directory) / (stem + "-predictions.npz")
            with np.load(paired_path, allow_pickle=False) as saved:
                probability = saved["probabilities"]
            if probability.shape != (len(ids), 3):
                raise ValueError("paired globals row count changed")
            torch.save(model.state_dict(), output / (stem + ".pt"))
            np.savez_compressed(output / (stem + "-predictions.npz"), probabilities=probability, margin=margin)
            prior = empirical_prior(ids, labels, fold.mask)
            report = {"fold": fold.fold, "fitting_and_prediction_seconds": time.monotonic() - began,
                      "fitting": report_predictions(data.evaluation, probability, margin, prior, fit_mask=fold.mask),
                      "excluded": report_predictions(data.evaluation, probability, margin, prior, fit_mask=~fold.mask)}
            publish(output / (stem + "-report.json"), report)
            oof_p[~fold.mask] = probability[~fold.mask]
            oof_m[~fold.mask] = margin[~fold.mask]
            oof_prior[~fold.mask] = prior
            log({"status": "fit_complete", "elapsed_seconds": time.monotonic() - began})
            del model
        if not np.isfinite(oof_p).all() or not np.isfinite(oof_m).all():
            raise ValueError("incomplete residual out-of-fold predictions")
        np.savez_compressed(output / f"seed{seed}-oof.npz", probabilities=oof_p, margin=oof_m, prior=oof_prior)
        publish(output / f"seed{seed}-summary.json",
                report_predictions(data.evaluation, oof_p, oof_m, oof_prior, bootstrap=True))
    load_plan(plan_path)
    publish(output / "complete.json", {"status": "fixed-residual-comparison-complete", "model": plan.model.name,
                                       "seeds": list(plan.training.seeds), "fits": 8,
                                       "draw_games": len(np.unique(ids[labels == 1])), "acceptance": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("memory", "readiness", "fit"), required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-report", type=Path)
    parser.add_argument("--readiness", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing existing residual output")
    torch.set_num_threads(1)
    plan = load_plan(args.plan)
    if args.mode == "memory":
        memory_probe(plan, args.plan, args.output)
    elif args.mode == "readiness":
        if args.memory_report is None:
            raise ValueError("actual memory report required")
        report = json.loads(args.memory_report.read_text())
        validate_memory(report, plan, args.plan)
        publish(args.output, {"status": "passed", "plan_sha256": sha(args.plan),
                              "memory_report_path": str(args.memory_report.resolve()),
                              "memory_report_sha256": sha(args.memory_report),
                              "feature_matrix_sha256": report["feature_matrix_sha256"],
                              "scope": "Fixed training-only residual comparison; no acceptance or policy updates."})
        print(json.dumps({"status": "passed", "readiness": str(args.output)}), flush=True)
    else:
        if args.readiness is None:
            raise ValueError("matching readiness required before fitting")
        run_fit(plan, args.plan, args.readiness, args.output)


if __name__ == "__main__":
    main()
