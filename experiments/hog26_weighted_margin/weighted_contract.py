"""Two fixed margin architectures, one predeclared sampling comparison."""

import json
from pathlib import Path
from typing import Literal

import torch
from semantic_contract import SHA256, StrictRecord, runtime_signature
from terminal_labels import sha

MEMORY_LIMIT = 18 * 1024**3


class Plan(StrictRecord):
    schema_id: Literal["clasher.hog26.weighted-margin.v1"]
    hypothesis: str
    feature_plan: str
    numeric_sha256: SHA256
    semantic_sha256: SHA256
    models: tuple[Literal["numeric"], Literal["semantic"]]
    seeds: tuple[Literal[1279501], Literal[1279502]]
    folds: Literal[4]
    epochs: Literal[30]
    batch_rows: Literal[512]
    sampler: Literal["fitting-row count draws per epoch with replacement proportional to unchanged margin weights"]
    objective: Literal["unweighted minibatch mean absolute residual error; same unclipped expected objective"]
    optimizer: Literal["unchanged AdamW lr0.0003 wd0.0001 clip1; CPU thread1"]
    selection: Literal["all sixteen final-epoch fits; no sweeps or selection"]
    implementation: dict[str, SHA256]
    resources: dict[str, SHA256]
    runtime: dict[str, str | int]
    acceptance: Literal[False]
    policy_updates: Literal[False]
    reserved_collection: Literal[False]
    limitations: tuple[str, ...]


def sources():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def load_plan(path):
    plan = Plan.model_validate_json(Path(path).read_text())
    if plan.implementation != sources() or plan.runtime != runtime_signature() or torch.get_num_threads() != 1:
        raise ValueError("weighted margin source or runtime changed")
    for resource, expected in plan.resources.items():
        if sha(resource) != expected:
            raise ValueError("weighted margin resource changed: " + resource)
    return plan


def publish(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
