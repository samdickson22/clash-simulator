"""Require all sixteen complete fixed fits before diagnostic access."""

import json
from pathlib import Path

import numpy as np
from review_completed import validate_predictions
from semantic_contract import load_plan as load_feature_plan
from terminal_labels import sha
from weighted_contract import load_plan, sources
from weighted_experiment import validate_readiness


def pin_fits(root):
    directory = root / "reports/hog26_weighted_margin_comparison_20260913"
    completion = json.loads((directory / "complete.json").read_text())
    if completion != {"status": "weighted-margin-comparison-complete", "fits": 16, "acceptance": False}:
        raise ValueError("all sixteen weighted margin fits must complete")
    plan_path = root / "reports/hog26_weighted_margin_frozen_plan_20260913.json"
    plan = load_plan(plan_path)
    feature_plan = load_feature_plan(plan.feature_plan)
    readiness_path = root / "reports/hog26_weighted_margin_readiness_20260913.json"
    readiness = validate_readiness(readiness_path, plan, plan_path)
    manifest_path = directory / "fitting_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    reference = Path(feature_plan.data.globals_directory)
    reference_manifest = json.loads((reference / "fitting_manifest.json").read_text())
    if (manifest["plan"] != plan.model_dump(mode="json") or manifest["plan_sha256"] != sha(plan_path)
            or manifest["sources"] != sources() or manifest["readiness"] != readiness
            or manifest["input_games"] != reference_manifest["input_games"]
            or manifest["data_audit"] != reference_manifest["data_audit"]
            or manifest["numeric_sha256"] != plan.numeric_sha256
            or manifest["semantic_sha256"] != plan.semantic_sha256 or manifest["acceptance"]):
        raise ValueError("weighted margin fitting authority differs")
    expected = {"complete.json", "fitting_manifest.json"}
    resources = {str(plan_path): sha(plan_path), str(readiness_path): sha(readiness_path)}
    for kind in plan.models:
        names = {"complete.json", "fitting_manifest.json"}
        for seed in plan.seeds:
            names.update({f"seed{seed}-oof.npz", f"seed{seed}-summary.json"})
            for fold in range(4):
                stem = f"seed{seed}-fold{fold}"
                names.update({stem + ".pt", stem + "-predictions.npz", stem + "-report.json"})
        expected.update(f"{kind}/{name}" for name in names)
        model_manifest = json.loads((directory / kind / "fitting_manifest.json").read_text())
        if model_manifest != {"model": kind, "root_manifest_sha256": sha(manifest_path),
                               "inputs": 425 if kind == "numeric" else 809,
                               "wdl_fitting": False, "acceptance": False}:
            raise ValueError("weighted model manifest differs")
        if json.loads((directory / kind / "complete.json").read_text()) != {
                "status": "weighted-margin-model-complete", "model": kind, "fits": 8, "acceptance": False}:
            raise ValueError("weighted model completion differs")
        for name in names:
            path = directory / kind / name
            if path.suffix != ".npz":
                continue
            validate_predictions(path, 618149)
            reference_path = reference / name
            resources[str(reference_path)] = sha(reference_path)
            with np.load(path, allow_pickle=False) as candidate, np.load(reference_path, allow_pickle=False) as original:
                keys = ("probabilities", "prior") if name.endswith("-oof.npz") else ("probabilities",)
                if any(not np.array_equal(candidate[key], original[key]) for key in keys):
                    raise ValueError("promised globals probabilities or priors changed")
    if {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()} != expected or len(expected) != 62:
        raise ValueError("weighted margin artifact inventory differs")
    resources.update({str(directory / name): sha(directory / name) for name in sorted(expected)})
    return plan, feature_plan, manifest, resources
