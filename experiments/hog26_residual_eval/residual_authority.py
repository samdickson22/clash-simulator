"""Verify completed residual fits and their unchanged probability references."""

import json
from pathlib import Path

import numpy as np
from residual_contract import load_plan, sha, source_inventory
from residual_experiment import validate_readiness
from review_completed import validate_predictions


def pin_completed_fits(root):
    directory = root / "reports/hog26_residual_margin_comparison_20260912"
    completion_path = directory / "complete.json"
    completion = json.loads(completion_path.read_text())
    plan_path = root / "reports/hog26_residual_margin_frozen_plan_20260912.json"
    plan = load_plan(plan_path)
    if completion != {"status": "fixed-residual-comparison-complete", "model": plan.model.name,
                      "seeds": list(plan.training.seeds), "fits": 8, "draw_games": 0, "acceptance": False}:
        raise ValueError("all eight fixed residual fits must complete")
    readiness_path = root / "reports/hog26_residual_margin_readiness_20260912.json"
    _, memory = validate_readiness(readiness_path, plan, plan_path)
    manifest_path = directory / "fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    reference = Path(plan.data.globals_directory)
    reference_manifest = json.loads((reference / "fitting_manifest.json").read_text())
    if (manifest["plan"] != plan.model_dump(mode="json") or manifest["plan_sha256"] != sha(plan_path)
            or manifest["implementation"] != source_inventory()
            or manifest["data_audit"] != plan.data.expected_audit
            or manifest["input_games"] != reference_manifest["input_games"]
            or manifest["feature_matrix_sha256"] != memory["feature_matrix_sha256"]
            or manifest["readiness_sha256"] != sha(readiness_path)
            or manifest["paired_globals_manifest_sha256"] != sha(reference / "fitting_manifest.json")
            or manifest["wdl_fitting"] is not False or manifest["acceptance"] is not False):
        raise ValueError("residual fitting authority differs")
    expected = {"complete.json", "fitting_manifest.json"}
    for seed in plan.training.seeds:
        expected.update({f"seed{seed}-summary.json", f"seed{seed}-oof.npz"})
        for fold in range(4):
            stem = f"seed{seed}-fold{fold}"
            expected.update({stem + ".pt", stem + "-predictions.npz", stem + "-report.json"})
    actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    if actual != expected or len(actual) != 30:
        raise ValueError("residual artifact inventory differs")
    resources = {str(plan_path): sha(plan_path), str(readiness_path): sha(readiness_path)}
    for name in sorted(expected):
        path = directory / name
        resources[str(path)] = sha(path)
        if path.suffix != ".npz":
            continue
        validate_predictions(path, plan.data.rows)
        reference_path = reference / name
        resources[str(reference_path)] = sha(reference_path)
        with np.load(path, allow_pickle=False) as candidate, np.load(reference_path, allow_pickle=False) as original:
            for key in ("probabilities", "prior") if name.endswith("-oof.npz") else ("probabilities",):
                if not np.array_equal(candidate[key], original[key]):
                    raise ValueError("promised globals probability or prior reference changed")
    return plan, manifest, resources
