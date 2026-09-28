"""Source-pinned auxiliary test; it cannot authorize outcome or policy acceptance."""

import json
from pathlib import Path
from typing import Literal

import torch
from semantic_contract import SHA256, StrictRecord, runtime_signature
from terminal_labels import sha

MEMORY_LIMIT = 18 * 1024**3


class Plan(StrictRecord):
    schema_id: Literal["clasher.hog26.terminal-auxiliary.v1"]
    hypothesis: str
    feature_plan: str
    label_audit: str
    feature_sha256: SHA256
    label_sha256: SHA256
    inputs: Literal[809]
    parameters: Literal[27009]
    seeds: tuple[Literal[1279501], Literal[1279502]]
    folds: Literal[4]
    epochs: Literal[30]
    batch_rows: Literal[512]
    objective: Literal["Bernoulli NLL with unchanged phase-balanced 50/50 uniform/representative margin fitting weights"]
    optimizer: Literal["AdamW lr0.0003 wd0.0001 clip1; one CPU thread"]
    initialization: Literal["zero final weight; logit of fitting-weighted terminal frequency as bias"]
    selection: Literal["all eight final-epoch models; no sweep, threshold selection, or outcome-model change"]
    implementation: dict[str, SHA256]
    resources: dict[str, SHA256]
    runtime: dict[str, str | int]
    acceptance: Literal[False]
    policy_updates: Literal[False]
    diagnostic_access: Literal[False]
    limitations: tuple[str, ...]


def sources():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def load_plan(path):
    plan = Plan.model_validate_json(Path(path).read_text())
    if plan.implementation != sources() or plan.runtime != runtime_signature() or torch.get_num_threads() != 1:
        raise ValueError("auxiliary source or runtime changed")
    for resource_path, expected in plan.resources.items():
        if sha(resource_path) != expected:
            raise ValueError("auxiliary pinned resource changed: " + resource_path)
    return plan


def publish(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
