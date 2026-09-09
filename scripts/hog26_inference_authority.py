"""Bind outcome inference and evaluation semantics to exact local source bytes."""

import hashlib

import numpy as np
import torch

SOURCES = (
    "src/clasher/torch_sim/simple_catalog.py",
    "src/clasher/torch_sim/simple_runtime.py",
    "src/clasher/torch_sim/simple_rolling_spells.py",
    "src/clasher/torch_sim/simple_targeting.py",
    "src/clasher/torch_sim/simple_attack_locks.py",
    "src/clasher/torch_sim/simple_engine.py",
    "scripts/run_hog26_procedural_outcome_shard.py",
    "scripts/collect_hog26_frozen_final.py",
    "scripts/audit_hog26_procedural_outcome_shard.py",
    "scripts/hog26_seeded_opening_audit.py",
    "src/clasher/rl/seeded_deals.py",
    "scripts/collect_hog26_complete_outcomes.py",
    "scripts/hog26_scenario_clusters.py",
    "src/clasher/rl/outcome_model.py",
    "src/clasher/rl/public_margin_dynamics.py",
    "src/clasher/rl/direct_simple_behavior.py",
    "scripts/train_hog26_actor_outcome.py",
    "scripts/hog26_public_outcome_projection.py",
    "scripts/hog26_public_slice_gates.py",
    "scripts/evaluate_hog26_frozen_outcome.py",
    "scripts/hog26_frozen_outcome.py",
    "scripts/freeze_hog26_outcome_cohort.py",
    "scripts/train_hog26_procedural_outcome_candidate.py",
    "scripts/audit_hog26_outcome_corpora.py",
    "scripts/hog26_inference_authority.py",
)


def capture_inference_authority(root):
    return {
        "schema": "clasher.hog26.inference-authority.v1",
        "sources": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES},
        "runtime": {"numpy": np.__version__, "torch": str(torch.__version__)},
    }


def validate_inference_authority(authority, root):
    if authority != capture_inference_authority(root):
        raise ValueError("outcome inference source or runtime authority changed")
