"""Memory-gated auxiliary fitting, with labels isolated from public inputs."""

import argparse
import hashlib
import json
import resource
import sys
from pathlib import Path

import numpy as np
import torch
from semantic_contract import load_plan as load_feature_plan
from semantic_contract import runtime_signature
from semantic_data import prepare_data
from terminal_contract import MEMORY_LIMIT, load_plan, publish, sources
from terminal_labels import load_labels, sha
from terminal_metrics import report
from terminal_model import TerminalPredictor, fit, optimizer_for, predict, step


def prepare(plan):
    data = prepare_data(load_feature_plan(plan.feature_plan))
    labels = load_labels(data.input_games)
    if (data.feature_sha256 != plan.feature_sha256
            or hashlib.sha256(labels.tobytes()).hexdigest() != plan.label_sha256):
        raise ValueError("auxiliary feature or label authority differs")
    return data, labels


def validate_memory(value, plan, plan_path):
    if (value.get("status") != "passed-auxiliary-memory-audit" or value.get("plan_sha256") != sha(plan_path)
            or value.get("sources") != sources() or value.get("runtime") != runtime_signature()
            or value.get("feature_sha256") != plan.feature_sha256 or value.get("label_sha256") != plan.label_sha256
            or value.get("shape") != [618149, 809] or value.get("feature_bytes") != 2000330164
            or value.get("parameters") != 27009 or value.get("synthetic_rows") != 512
            or value.get("initial_probability_max_error") != 0.0 or not value.get("finite_gradients")
            or not value.get("optimizer_step") or value.get("outcome_fitting") is not False
            or value.get("saved_model") is not False
            or not 0 < value.get("peak_rss_bytes", 0) < MEMORY_LIMIT):
        raise ValueError("auxiliary memory evidence does not establish readiness")


def validate_readiness(path, plan, plan_path):
    value = json.loads(Path(path).read_text())
    if value.get("status") != "passed" or value.get("plan_sha256") != sha(plan_path):
        raise ValueError("passed auxiliary readiness required")
    if sha(value["memory_path"]) != value["memory_sha256"]:
        raise ValueError("auxiliary memory evidence changed")
    validate_memory(json.loads(Path(value["memory_path"]).read_text()), plan, plan_path)
    return value


def memory(plan, plan_path, output):
    data, _ = prepare(plan)
    model = TerminalPredictor()
    initial = predict(model, data.features)
    oof = np.full(len(initial), np.nan)
    prior = np.full(len(initial), np.nan)
    largest = max(data.folds, key=lambda f: len(f.indices))
    chosen = largest.indices[:512]
    step(model, optimizer_for(model), torch.from_numpy(data.features[chosen]), torch.zeros(512),
         torch.from_numpy(largest.margin_weights[chosen].astype(np.float32)), len(largest.indices))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    assert oof.shape == prior.shape == initial.shape
    value = {"status": "passed-auxiliary-memory-audit", "plan_sha256": sha(plan_path),
             "sources": sources(), "runtime": runtime_signature(),
             "feature_sha256": data.feature_sha256, "label_sha256": plan.label_sha256,
             "shape": list(data.features.shape), "feature_bytes": data.features.nbytes,
             "parameters": sum(p.numel() for p in model.parameters()), "synthetic_rows": 512,
             "initial_probability_max_error": float(np.max(np.abs(initial - .5))),
             "finite_gradients": all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
             "optimizer_step": bool(model.network[-1].bias.detach().abs().sum() > 0),
             "outcome_fitting": False, "saved_model": False, "peak_rss_bytes": peak}
    load_plan(plan_path)
    validate_memory(value, plan, plan_path)
    publish(output, value)
    print(json.dumps({"status": value["status"], "peak_rss_bytes": peak}), flush=True)


def run_fit(plan, plan_path, readiness_path, output):
    readiness = validate_readiness(readiness_path, plan, plan_path)
    data, labels = prepare(plan)
    output.mkdir()
    publish(output / "fitting_manifest.json", {"plan": plan.model_dump(mode="json"),
            "plan_sha256": sha(plan_path), "sources": sources(), "input_games": data.input_games,
            "feature_sha256": data.feature_sha256, "label_sha256": plan.label_sha256,
            "data_audit": data.audit, "readiness": readiness, "acceptance": False})
    for seed in plan.seeds:
        oof, oof_prior = np.full(len(labels), np.nan), np.full(len(labels), np.nan)
        for fold in data.folds:
            load_plan(plan_path)
            stem = f"seed{seed}-fold{fold.fold}"

            def log(row, seed=seed, fold=fold):
                print(json.dumps({"seed": seed, "fold": fold.fold, **row}), flush=True)

            model, prior = fit(data.features, labels, fold.indices, fold.margin_weights,
                               seed + fold.fold, epochs=plan.epochs, batch=plan.batch_rows, log=log)
            probability = predict(model, data.features)
            torch.save(model.state_dict(), output / (stem + ".pt"))
            np.savez_compressed(output / (stem + "-predictions.npz"), terminal_probability=probability)
            publish(output / (stem + "-report.json"), {
                "fold": fold.fold, "fitting_weighted_prior": prior,
                "fitting": report(data.evaluation, labels, probability, prior, fold.mask),
                "excluded": report(data.evaluation, labels, probability, prior, ~fold.mask)})
            oof[~fold.mask], oof_prior[~fold.mask] = probability[~fold.mask], prior
            log({"status": "auxiliary-fit-complete"})
        if not np.isfinite(oof).all() or not np.isfinite(oof_prior).all():
            raise ValueError("incomplete auxiliary OOF predictions")
        np.savez_compressed(output / f"seed{seed}-oof.npz", terminal_probability=oof, prior=oof_prior)
        publish(output / f"seed{seed}-summary.json", report(data.evaluation, labels, oof, oof_prior, intervals=True))
    load_plan(plan_path)
    publish(output / "complete.json", {"status": "auxiliary-terminal-comparison-complete", "fits": 8,
                                       "acceptance": False, "outcome_model_changed": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("memory", "readiness", "fit"), required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-report", type=Path)
    parser.add_argument("--readiness", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("preserve existing auxiliary output")
    torch.set_num_threads(1)
    plan = load_plan(args.plan)
    if args.mode == "memory":
        memory(plan, args.plan, args.output)
    elif args.mode == "readiness":
        if args.memory_report is None:
            raise ValueError("actual auxiliary memory report required")
        value = json.loads(args.memory_report.read_text())
        validate_memory(value, plan, args.plan)
        publish(args.output, {"status": "passed", "plan_sha256": sha(args.plan),
                              "memory_path": str(args.memory_report.resolve()), "memory_sha256": sha(args.memory_report)})
    else:
        if args.readiness is None:
            raise ValueError("passed auxiliary readiness required")
        run_fit(plan, args.plan, args.readiness, args.output)


if __name__ == "__main__":
    main()
