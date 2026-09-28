"""Freeze the additional paired diagnostic analysis before scaled prediction."""

import hashlib
import json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_review_plan(root):
    path = root / "reports/hog26_scaling_paired_diagnostic_review_plan_20260912.json"
    plan = json.loads(path.read_text())
    if (plan["schema"] != "clasher.hog26.scaling-paired-review.v1"
            or plan["status"] != "predeclared-diagnostic-only"
            or plan["bootstrap_replicates"] != 2000 or plan["bootstrap_seed"] != 1279511
            or plan["metrics"] != ["nll_reduction", "brier_reduction", "margin_mae_reduction"]
            or plan["acceptance"] is not False or plan["fitting"] is not False):
        raise ValueError("paired review contract changed")
    source_root = root / "experiments/hog26_scaling_review"
    actual = {p.name: digest(p) for p in sorted(source_root.glob("*.py"))}
    if actual != plan["review_sources"]:
        raise ValueError("paired review source differs from pre-prediction pin")
    diagnostic_plan = root / "reports/hog26_seed_transfer_frozen_plan_20260911.json"
    if digest(diagnostic_plan) != plan["diagnostic_plan_sha256"]:
        raise ValueError("diagnostic plan changed")
    return path, digest(path)
