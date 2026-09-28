"""Probe both resident matrices, then fit all sixteen fixed margin comparisons."""

import argparse
import hashlib
import json
import resource
import sys
from pathlib import Path

import numpy as np
import torch
from run_scaling_comparison import report_predictions
from scalar_evaluation import empirical_prior
from semantic_contract import load_plan as load_feature_plan
from semantic_contract import runtime_signature
from semantic_data import prepare_data
from terminal_labels import sha
from weighted_contract import MEMORY_LIMIT, load_plan, publish, sources
from weighted_model import fit, make_model, make_optimizer, predict_margin, step


def prepare(plan):
    feature_plan = load_feature_plan(plan.feature_plan)
    data = prepare_data(feature_plan)
    numeric = np.ascontiguousarray(data.features[:, :425])
    numeric_hash = hashlib.sha256(memoryview(numeric).cast("B")).hexdigest()
    if numeric_hash != plan.numeric_sha256 or data.feature_sha256 != plan.semantic_sha256:
        raise ValueError("weighted margin features differ from their respective original matrices")
    return data, {"numeric": numeric, "semantic": data.features}, feature_plan


def validate_memory(value, plan, plan_path):
    if (value.get("status") != "passed-weighted-margin-memory-audit" or value.get("plan_sha256") != sha(plan_path)
            or value.get("sources") != sources() or value.get("runtime") != runtime_signature()
            or value.get("numeric_sha256") != plan.numeric_sha256 or value.get("semantic_sha256") != plan.semantic_sha256
            or value.get("matrix_shapes") != {"numeric": [618149, 425], "semantic": [618149, 809]}
            or value.get("matrix_bytes") != {"numeric": 1050853300, "semantic": 2000330164}
            or value.get("parameters") != {"numeric": 14721, "semantic": 27009}
            or value.get("initial_baseline_errors") != {"numeric": 0., "semantic": 0.}
            or value.get("finite_gradients") != {"numeric": True, "semantic": True}
            or value.get("optimizer_steps") != {"numeric": True, "semantic": True}
            or value.get("sampler_draw_count") != 474642 or value.get("synthetic_rows") != 512
            or value.get("outcome_fitting") is not False or value.get("saved_model") is not False
            or not 0 < value.get("peak_rss_bytes", 0) < MEMORY_LIMIT):
        raise ValueError("weighted margin memory evidence does not establish readiness")


def validate_readiness(path, plan, plan_path):
    value = json.loads(Path(path).read_text())
    if value.get("status") != "passed" or value.get("plan_sha256") != sha(plan_path):
        raise ValueError("passed weighted margin readiness required")
    if sha(value["memory_path"]) != value["memory_sha256"]:
        raise ValueError("weighted margin memory evidence changed")
    validate_memory(json.loads(Path(value["memory_path"]).read_text()), plan, plan_path)
    return value


def memory(plan, plan_path, output):
    data, matrices, _ = prepare(plan)
    current = data.evaluation[4]
    oof_p, oof_prior, oof_margin = np.full((len(current), 3), np.nan), np.full((len(current), 3), np.nan), np.full(len(current), np.nan)
    largest = max(data.folds, key=lambda fold: len(fold.indices))
    torch.manual_seed(1279821)
    draws = torch.multinomial(torch.from_numpy(largest.margin_weights[largest.indices]), len(largest.indices), replacement=True)
    chosen = largest.indices[draws[:512].numpy()]
    errors, finite, changed, parameters = {}, {}, {}, {}
    for kind in plan.models:
        model = make_model(kind)
        errors[kind] = float(np.max(np.abs(predict_margin(model, matrices[kind], current) - current)))
        step(model, make_optimizer(model), torch.from_numpy(matrices[kind][chosen]), torch.full((512,), .125))
        finite[kind] = all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters())
        changed[kind] = bool(model.network[-1].bias.detach().abs().sum() > 0)
        parameters[kind] = sum(p.numel() for p in model.parameters())
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    assert oof_p.shape == oof_prior.shape and oof_margin.shape == current.shape
    value = {"status": "passed-weighted-margin-memory-audit", "plan_sha256": sha(plan_path),
             "sources": sources(), "runtime": runtime_signature(),
             "numeric_sha256": plan.numeric_sha256, "semantic_sha256": plan.semantic_sha256,
             "matrix_shapes": {k: list(v.shape) for k, v in matrices.items()},
             "matrix_bytes": {k: v.nbytes for k, v in matrices.items()}, "parameters": parameters,
             "initial_baseline_errors": errors, "finite_gradients": finite, "optimizer_steps": changed,
             "sampler_draw_count": len(draws), "synthetic_rows": 512, "peak_rss_bytes": peak,
             "outcome_fitting": False, "saved_model": False}
    load_plan(plan_path)
    validate_memory(value, plan, plan_path)
    publish(output, value)
    print(json.dumps({"status": value["status"], "peak_rss_bytes": peak}), flush=True)


def run_fit(plan, plan_path, readiness_path, output):
    readiness = validate_readiness(readiness_path, plan, plan_path)
    data, matrices, feature_plan = prepare(plan)
    output.mkdir()
    manifest = output / "fitting_manifest.json"
    publish(manifest, {"plan": plan.model_dump(mode="json"), "plan_sha256": sha(plan_path),
                       "sources": sources(), "input_games": data.input_games, "data_audit": data.audit,
                       "readiness": readiness, "numeric_sha256": plan.numeric_sha256,
                       "semantic_sha256": plan.semantic_sha256, "acceptance": False})
    ids, _, labels, target, current, *_ = data.evaluation
    residual = np.asarray(target - current, dtype=np.float32)
    for kind in plan.models:
        directory = output / kind
        directory.mkdir()
        publish(directory / "fitting_manifest.json", {"model": kind, "root_manifest_sha256": sha(manifest),
                "inputs": matrices[kind].shape[1], "wdl_fitting": False, "acceptance": False})
        for seed in plan.seeds:
            oof_p, oof_prior = np.full((len(ids), 3), np.nan), np.full((len(ids), 3), np.nan)
            oof_margin = np.full(len(ids), np.nan)
            for fold in data.folds:
                load_plan(plan_path)
                stem = f"seed{seed}-fold{fold.fold}"

                def log(row, kind=kind, seed=seed, fold=fold):
                    print(json.dumps({"model": kind, "seed": seed, "fold": fold.fold, **row}), flush=True)

                model = fit(matrices[kind], residual, fold.indices, fold.margin_weights, kind=kind,
                            seed=seed + fold.fold, epochs=plan.epochs, batch=plan.batch_rows, log=log)
                margin = predict_margin(model, matrices[kind], current)
                with np.load(Path(feature_plan.data.globals_directory) / (stem + "-predictions.npz"), allow_pickle=False) as saved:
                    probability = saved["probabilities"]
                if probability.shape != (len(ids), 3):
                    raise ValueError("paired globals row count differs")
                torch.save(model.state_dict(), directory / (stem + ".pt"))
                np.savez_compressed(directory / (stem + "-predictions.npz"), probabilities=probability, margin=margin)
                prior = empirical_prior(ids, labels, fold.mask)
                publish(directory / (stem + "-report.json"), {
                    "fold": fold.fold, "fitting": report_predictions(data.evaluation, probability, margin, prior, fit_mask=fold.mask),
                    "excluded": report_predictions(data.evaluation, probability, margin, prior, fit_mask=~fold.mask)})
                oof_p[~fold.mask], oof_margin[~fold.mask], oof_prior[~fold.mask] = probability[~fold.mask], margin[~fold.mask], prior
                log({"status": "weighted-margin-fit-complete"})
            if not np.isfinite(oof_p).all() or not np.isfinite(oof_margin).all():
                raise ValueError("incomplete weighted margin OOF predictions")
            np.savez_compressed(directory / f"seed{seed}-oof.npz", probabilities=oof_p, margin=oof_margin, prior=oof_prior)
            publish(directory / f"seed{seed}-summary.json", report_predictions(data.evaluation, oof_p, oof_margin, oof_prior, bootstrap=True))
        publish(directory / "complete.json", {"status": "weighted-margin-model-complete", "model": kind, "fits": 8, "acceptance": False})
    load_plan(plan_path)
    publish(output / "complete.json", {"status": "weighted-margin-comparison-complete", "fits": 16, "acceptance": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("memory", "readiness", "fit"), required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-report", type=Path)
    parser.add_argument("--readiness", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("preserve existing weighted margin output")
    torch.set_num_threads(1)
    plan = load_plan(args.plan)
    if args.mode == "memory":
        memory(plan, args.plan, args.output)
    elif args.mode == "readiness":
        if args.memory_report is None:
            raise ValueError("actual weighted margin memory report required")
        validate_memory(json.loads(args.memory_report.read_text()), plan, args.plan)
        publish(args.output, {"status": "passed", "plan_sha256": sha(args.plan),
                              "memory_path": str(args.memory_report.resolve()), "memory_sha256": sha(args.memory_report)})
    else:
        if args.readiness is None:
            raise ValueError("passed weighted margin readiness required")
        run_fit(plan, args.plan, args.readiness, args.output)


if __name__ == "__main__":
    main()
