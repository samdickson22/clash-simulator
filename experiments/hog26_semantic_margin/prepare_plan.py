"""Freeze one physical-feature residual test after the preceding study is closed."""

import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from semantic_contract import FrozenPlan, runtime_signature, sha, source_inventory


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    if output.exists():
        raise ValueError("preserve existing frozen plan")
    previous_path = root / "reports/hog26_residual_margin_frozen_plan_20260912.json"
    value = json.loads(previous_path.read_text())
    closed_path = root / "reports/hog26_residual_margin_diagnostic_review_20260912.json"
    closed = json.loads(closed_path.read_text())
    if (closed["status"] != "completed-residual-diagnostic-review" or closed["fits"] != 8
            or not closed["sources_and_references_unchanged"] or closed["acceptance"]):
        raise ValueError("complete reviewed residual diagnostic required")
    audit_path = root / "reports/hog26_public_semantic_feature_audit_20260912.json"
    audit = json.loads(audit_path.read_text())
    if (audit["status"] != "passed-public-feature-audit" or audit["feature_shape"] != [618149, 809]
            or audit["outcome_fitting"] or audit["outcome_arrays_read"]):
        raise ValueError("full public-only feature audit required")
    resources = value["authority"]["resources"]
    for path, expected in resources.items():
        if sha(path) != expected:
            raise ValueError("previous frozen dependency changed: " + path)
    for path, expected in audit["source_hashes"].items():
        if sha(path) != expected:
            raise ValueError("audited feature source changed: " + path)
        resources[path] = expected
    for path, expected in audit["metadata_sources"].items():
        if path == "typed_vocabulary_digest":
            continue
        if sha(path) != expected:
            raise ValueError("audited static metadata changed: " + path)
        resources[path] = expected
    for directory in ("hog26_residual_margin", "hog26_residual_eval"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for directory in ("hog26_residual_margin_comparison_20260912", "hog26_scaling_tree_comparison_20260912"):
        for path in (root / "reports" / directory).iterdir():
            if path.is_file():
                resources[str(path)] = sha(path)
    for path in (previous_path, closed_path, audit_path,
                 root / "reports/hog26_residual_margin_fitting_review_20260912.json"):
        resources[str(path)] = sha(path)
    value.update(schema_id="clasher.hog26.semantic-residual-margin.v1",
                 created_at=datetime.now(timezone.utc).isoformat(),
                 hypothesis="Public per-body physical summaries may transfer across identities better than numeric summaries alone. Compare the fixed residual recipe with its numeric predecessor and the fixed tree; additional parameters and initialization differences prevent a pure causal attribution to information alone.")
    value["model"].update(name="public-semantic-residual-margin-v1", inputs=809, parameters=27009)
    value["model"].pop("entity_identity_features")
    value["model"]["learned_identity_features"] = False
    value["features"] = {
        "numeric_prefix": 425, "physical_columns": 384,
        "metadata": "public per-body base stats; unknown traits confidence zero",
        "geometry": "Euclidean proximity to nearest visible own or enemy crown; no target inference",
        "reductions": "own/enemy by troop/building/crown; mean, max, sum/128, confidence/128",
        "matrix_sha256": audit["feature_matrix_sha256"], "audit_path": str(audit_path),
        "audit_sha256": sha(audit_path),
    }
    value["authority"] = {"implementation": source_inventory(), "resources": resources,
                          "runtime": runtime_signature()}
    value["limitations"].extend([
        "Static base traits are not current attack state; inferred targets, hidden timing, child deployment multipliers and future observations are excluded.",
        "Eight fits use the same training games, folds, seeds and fixed 30 epochs as the numeric predecessor. No outcomes select features or epochs within this experiment.",
        "Previously opened diagnostics informed this representation hypothesis; their next evaluation remains diagnostic, never final acceptance.",
    ])
    plan = FrozenPlan.model_validate_json(json.dumps(value))
    with output.open("x") as stream:
        stream.write(plan.model_dump_json(indent=2) + "\n")
    print(json.dumps({"status": plan.status, "sha256": sha(output), "parameters": plan.model.parameters}))


if __name__ == "__main__":
    main()
