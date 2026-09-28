"""Freeze cache extraction only after complete expansion and prefix parity."""

import json
from pathlib import Path

import torch
from cache_contract import CachePlan, game_inventory_hash, sources
from expanded_authority import load_authority
from semantic_contract import load_plan as load_feature_plan
from semantic_contract import runtime_signature
from terminal_labels import sha


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / "reports/hog26_expanded_feature_plan_20260913.json"
    if output.exists():
        raise ValueError("preserve existing expanded cache plan")
    authority = load_authority(root)
    feature_path = root / "reports/hog26_semantic_margin_frozen_plan_20260912.json"
    feature = load_feature_plan(feature_path)
    if authority.vocabulary != feature.data.vocabulary:
        raise ValueError("expanded public vocabulary differs")
    numeric_path = root / "reports/hog26_residual_margin_memory_20260912.json"
    numeric = json.loads(numeric_path.read_text())
    resources = {**authority.resources, **feature.authority.resources}
    for path in (feature_path, numeric_path, root / "reports/hog26_streamed_feature_probe_20260913/complete.json"):
        resources[str(path)] = sha(path)
    for directory in ("hog26_streamed_features", "hog26_public_semantics", "hog26_semantic_margin",
                      "hog26_residual_margin", "hog26_terminal_auxiliary"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    for resource, expected in resources.items():
        if sha(resource) != expected:
            raise ValueError("cache dependency changed during planning")
    value = {"schema_id": "clasher.hog26.expanded-feature-cache.v1", "games": 6144, "clusters": 3072,
             "rows": sum(authority.cohort_rows.values()), "columns": 809, "dtype": "<f4",
             "feature_plan": str(feature_path), "original_prefix_rows": 618149,
             "original_semantic_sha256": feature.features.matrix_sha256,
             "original_numeric_sha256": numeric["feature_matrix_sha256"], "cohort_rows": authority.cohort_rows,
             "game_inventory_sha256": game_inventory_hash(authority.games), "implementation": sources(),
             "resources": resources, "runtime": runtime_signature(), "outcome_fitting": False, "acceptance": False,
             "scope": "Audit every complete game and stream unchanged public features. No model fitting or reserved data access; separate full-size training memory and model authority remain mandatory."}
    plan = CachePlan.model_validate_json(json.dumps(value))
    with output.open("x") as stream:
        stream.write(plan.model_dump_json(indent=2) + "\n")
    print(json.dumps({"status": "expanded-cache-plan-frozen", "rows": plan.rows, "sha256": sha(output)}), flush=True)


if __name__ == "__main__":
    main()
