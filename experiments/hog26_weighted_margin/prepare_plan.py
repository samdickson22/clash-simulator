"""Freeze the direct margin test after both auxiliary recipes are closed."""

import json
from pathlib import Path

import torch
from semantic_contract import runtime_signature
from terminal_labels import sha
from weighted_contract import Plan, publish, sources


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_weighted_margin_frozen_plan_20260913.json"
    if output.exists():
        raise ValueError("preserve existing weighted margin plan")
    feature_path = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    feature = json.loads(feature_path.read_text())
    sampler_path = root / "reports/hog26_terminal_weighted_sampler_frozen_plan_20260912.json"
    sampler = json.loads(sampler_path.read_text())
    closed_path = root / "reports/hog26_terminal_weighted_sampler_fitting_review_20260912.json"
    closed = json.loads(closed_path.read_text())
    if (closed["status"] != "completed-weighted-sampler-terminal-fitting-review"
            or not closed["checkpoint_predictions_exact"] or not closed["oof_and_intervals_exact"]):
        raise ValueError("closed sampler comparison required")
    numeric_memory_path = root / "reports/hog26_residual_margin_memory_20260912.json"
    numeric_memory = json.loads(numeric_memory_path.read_text())
    resources = dict(sampler["resources"])
    for path, expected in closed["inventory"].items():
        if sha(path) != expected:
            raise ValueError("closed sampler artifact changed")
        resources[path] = expected
    for path in (feature_path, sampler_path, closed_path, numeric_memory_path,
                 root / "reports/hog26_semantic_margin_fitting_review_20260912.json",
                 root / "reports/hog26_semantic_margin_diagnostic_review_20260912.json"):
        resources[str(path)] = sha(path)
    for directory in ("hog26_terminal_weighted_sampler", "hog26_terminal_sampler_review"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for directory in ("hog26_residual_margin_comparison_20260912", "hog26_semantic_margin_comparison_20260912"):
        for path in (root / "reports" / directory).iterdir():
            if path.is_file():
                resources[str(path)] = sha(path)
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("weighted comparison dependency changed")
    value = {"schema_id": "clasher.hog26.weighted-margin.v1",
             "hypothesis": "Test weighted-row sampling directly on both existing margin architectures, independently of the failed auxiliary predictor. The expected preclip margin objective is unchanged; sampling and gradient noise differ.",
             "feature_plan": str(feature_path), "numeric_sha256": numeric_memory["feature_matrix_sha256"],
             "semantic_sha256": feature["features"]["matrix_sha256"],
             "models": ["numeric", "semantic"], "seeds": [1279501, 1279502], "folds": 4,
             "epochs": 30, "batch_rows": 512,
             "sampler": "fitting-row count draws per epoch with replacement proportional to unchanged margin weights",
             "objective": "unweighted minibatch mean absolute residual error; same unclipped expected objective",
             "optimizer": "unchanged AdamW lr0.0003 wd0.0001 clip1; CPU thread1",
             "selection": "all sixteen final-epoch fits; no sweeps or selection",
             "implementation": sources(), "resources": resources, "runtime": runtime_signature(),
             "acceptance": False, "policy_updates": False, "reserved_collection": False,
             "limitations": [
                 "All features, architectures, initializations, outcomes, folds, seeds and loss weights match their respective predecessors.",
                 "The auxiliary termination model is not used as an input, gate or predictor; no future endpoint metadata enters these margin models.",
                 "WDL probabilities reuse matching globals references and provide no new classification evidence.",
                 "Replacement sampling preserves update count but changes row exposure and gradient noise; it does not isolate clipping alone.",
                 "Require a fresh full-resident two-matrix memory check and synthetic steps before fitting.",
                 "Review every fit, distribution and slice. After complete fitting review, freeze all sixteen opened-diagnostic evaluations regardless of fitting outcome.",
                 "Existing sparse late coverage, absent natural draws and reserved roles remain unchanged. No policy work before preserved calibration and ranking gates."]}
    plan = Plan.model_validate_json(json.dumps(value))
    publish(output, plan.model_dump(mode="json"))
    print(json.dumps({"status": "frozen-requires-memory-readiness", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
