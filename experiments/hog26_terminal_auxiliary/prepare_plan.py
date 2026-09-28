"""Freeze the first auxiliary termination test after the semantic study closes."""

import json
from pathlib import Path

import torch
from semantic_contract import runtime_signature
from terminal_contract import Plan, publish, sources
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_terminal_auxiliary_frozen_plan_20260912.json"
    if output.exists():
        raise ValueError("preserve existing auxiliary plan")
    feature_path = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    feature = json.loads(feature_path.read_text())
    label_path = root / "reports/hog26_terminal_auxiliary_label_audit_20260912.json"
    label = json.loads(label_path.read_text())
    if (label["status"] != "passed-actual-next-decision-label-audit"
            or label["source_sha256"] != sha(Path(__file__).with_name("terminal_labels.py"))):
        raise ValueError("exact actual-terminal label audit required")
    review_path = root / "reports/hog26_semantic_margin_diagnostic_review_20260912.json"
    review = json.loads(review_path.read_text())
    if (review["status"] != "completed-semantic-diagnostic-review" or review["fits"] != 8
            or not review["sources_and_references_unchanged"] or review["acceptance"]):
        raise ValueError("closed semantic comparison required")
    resources = dict(feature["authority"]["resources"])
    for path in (feature_path, label_path, review_path,
                 root / "reports/hog26_late_representative_position_audit_20260912.json",
                 root / "reports/hog26_late_representative_error_decomposition_20260912.json"):
        resources[str(path)] = sha(path)
    for directory in ("hog26_semantic_margin", "hog26_semantic_eval", "hog26_semantic_review_close", "hog26_late_position_audit"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("reviewed dependency changed")
    value = {"schema_id": "clasher.hog26.terminal-auxiliary.v1",
             "hypothesis": "The frozen public representation may predict actual termination in the next decision interval across held-out families. Test this auxiliary task before using it to influence any outcome prediction.",
             "feature_plan": str(feature_path), "label_audit": str(label_path),
             "feature_sha256": feature["features"]["matrix_sha256"], "label_sha256": label["labels_sha256"],
             "inputs": 809, "parameters": 27009, "seeds": [1279501, 1279502], "folds": 4,
             "epochs": 30, "batch_rows": 512,
             "objective": "Bernoulli NLL with unchanged phase-balanced 50/50 uniform/representative margin fitting weights",
             "optimizer": "AdamW lr0.0003 wd0.0001 clip1; one CPU thread",
             "initialization": "zero final weight; logit of fitting-weighted terminal frequency as bias",
             "selection": "all eight final-epoch models; no sweep, threshold selection, or outcome-model change",
             "implementation": sources(), "resources": resources, "runtime": runtime_signature(),
             "acceptance": False, "policy_updates": False, "diagnostic_access": False,
             "limitations": [
                 "Actual terminal time and final-row membership are labels only; no future field or endpoint override enters features.",
                 "The target is conditional on the frozen collection behavior policy, not an action-independent hazard.",
                 "Fitting probabilities target the existing weighted mixture; report both all-state and representative distributions without claiming universal calibration.",
                 "This auxiliary task is not WDL or terminal-margin acceptance. It changes no existing outcome model.",
                 "Use only the existing 1536 training games and four whole-family exclusions. Opened diagnostic and reserved data remain untouched.",
                 "Require a fresh full-resident memory and synthetic BCE step audit before fitting."]}
    plan = Plan.model_validate_json(json.dumps(value))
    publish(output, plan.model_dump(mode="json"))
    print(json.dumps({"status": "frozen-requires-memory-readiness", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
