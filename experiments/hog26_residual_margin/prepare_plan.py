"""Publish the fixed residual-margin design after the scaling study is closed."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from residual_contract import FrozenPlan, runtime_signature, sha, source_inventory
from residual_data import layout_hash, learner_hand_tokens
from residual_features import make_layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing existing frozen plan")
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    collection = root / "reports/hog26_scaling_frozen_plan_20260912.json"
    preflight = root / "reports/hog26_scaling_preflight_pin_20260912.json"
    globals_directory = root / "reports/hog26_scaling_globals_comparison_20260912"
    conclusion_path = root / "reports/hog26_scaling_comparison_conclusion_20260912.json"
    conclusion = json.loads(conclusion_path.read_text())
    if conclusion["status"] != "completed-fixed-scaling-diagnostic-conclusion" or conclusion["acceptance"] is not False:
        raise ValueError("completed scaling conclusion required")
    paired_review = root / "reports/hog26_scaling_seed_transfer_review_20260912.json"
    fitting_review = root / "reports/hog26_scaling_completed_comparison_review_20260912.json"
    if (sha(paired_review) != conclusion["paired_review_sha256"]
            or sha(fitting_review) != conclusion["fitting_review_sha256"]):
        raise ValueError("reviewed scaling evidence changed")
    for review_path in (fitting_review, paired_review):
        reviewed = json.loads(review_path.read_text())
        for path, expected in reviewed["resources"].items():
            if sha(path) != expected:
                raise ValueError("closed comparison resource changed")
    reference = json.loads((globals_directory / "fitting_manifest.json").read_text())
    collected = json.loads(collection.read_text())
    learner = [d for d in collected["source_authority"]["contract"]["decks"] if d["split"] == "learner"]
    if len(learner) != 1:
        raise ValueError("one declared learner deck required")
    cards = tuple(learner[0]["cards"])
    vocabulary = tuple(reference["outcome_token_names"])
    tokens = learner_hand_tokens(vocabulary, cards)
    layout = make_layout(len(vocabulary), tokens)
    resources = {}
    for path in (collection, preflight, conclusion_path, paired_review, fitting_review):
        resources[str(path)] = sha(path)
    for path in globals_directory.iterdir():
        if path.is_file():
            resources[str(path)] = sha(path)
    authority = collected["source_authority"]
    for relative, expected in authority["sources"].items():
        path = root / relative
        if sha(path) != expected:
            raise ValueError("historical collection source changed")
        resources[str(path.resolve())] = expected
    for item in authority["resources"].values():
        if sha(item["path"]) != item["sha256"]:
            raise ValueError("historical collection resource changed")
        resources[str(Path(item["path"]).resolve())] = item["sha256"]
    for directory in ("hog26_scalar_pilot", "hog26_data_scaling", "hog26_scaling_fit"):
        for path in (root / "experiments" / directory).glob("*.py"):
            resources[str(path)] = sha(path)
    value = {
        "schema_id": "clasher.hog26.numeric-residual-margin.v1",
        "status": "frozen-requires-memory-readiness",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "A small numeric residual predictor can preserve the public current-margin baseline while learning corrections, avoiding the failed joint identity/GRU head. This is a new baseline comparison, not an isolated causal ablation.",
        "model": {"name": "public-numeric-residual-margin-v1", "inputs": 425,
                  "hidden_width": 32, "hidden_layers": 2, "parameters": 14721,
                  "zero_initial_residual": True, "count_divisor": 128,
                  "entity_identity_features": False,
                  "output": "linear residual; add current margin and clip to [-1,1]",
                  "precision": "float32 model; float64 baseline addition"},
        "training": {"seeds": [1279501, 1279502], "epochs": 30, "batch_rows": 512,
                     "optimizer": "AdamW", "learning_rate": .0003, "weight_decay": .0001,
                     "gradient_clip": 1.0,
                     "objective": "unchanged scalar-pilot game/phase/representative weighted absolute residual error",
                     "selection": "fixed final epoch; no sweeps or calibration fitting"},
        "data": {"directory": str(root / "datasets/derived/hog26_scaling_train_seed1279701_20260912"),
                 "collection_plan": str(collection), "preflight": str(preflight),
                 "globals_directory": str(globals_directory), "games": 1536, "rows": 618149,
                 "clusters": 768, "fitting_games_per_fold": 1152, "excluded_games_per_fold": 384,
                 "learner_cards": cards, "hand_tokens": tokens, "vocabulary": vocabulary,
                 "expected_audit": reference["data_audit"], "feature_layout_sha256": layout_hash(layout)},
        "authority": {"implementation": source_inventory(), "resources": resources,
                      "runtime": runtime_signature()},
        "limitations": [
            "Only existing original-plus-extension training games are fitted. Opened diagnostic and reserved data are excluded.",
            "WDL predictions reuse the matching reviewed globals fit; they are not new independent classification evidence.",
            "All family folds, both seeds, all-state and representative metrics, and clustered intervals remain required.",
            "No time caps, endpoint overrides, epoch selection, class balancing, or natural-draw fabrication.",
            "The compact hand columns cover empty plus the declared eight-card learner deck; unexpected visible hand identities refuse.",
            "Before fitting, require a source-matching full-corpus feature audit, maximal synthetic optimizer step, and measured memory below 18 GiB.",
            "After complete fitting review, evaluate all eight fixed fits on the existing opened diagnostic, regardless of fitting outcomes. Freeze the separate evaluator before prediction; do not modify this fitting directory.",
        ],
        "acceptance": False, "policy_updates_allowed": False, "reserved_collection_allowed": False,
    }
    plan = FrozenPlan.model_validate_json(json.dumps(value))
    with args.output.open("x") as stream:
        stream.write(plan.model_dump_json(indent=2) + "\n")
    print(json.dumps({"status": plan.status, "plan_sha256": sha(args.output),
                      "feature_size": plan.model.inputs, "source_files": len(plan.authority.implementation)}))


if __name__ == "__main__":
    main()
