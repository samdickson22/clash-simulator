"""Strict frozen experiment contract and source/resource verification."""

import hashlib
import platform
from pathlib import Path
from typing import Annotated, Any, Literal

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field, field_validator

SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MEMORY_LIMIT = 18 * 1024**3


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class ModelSpec(StrictRecord):
    name: Literal["public-numeric-residual-margin-v1"]
    inputs: Literal[425]
    hidden_width: Literal[32]
    hidden_layers: Literal[2]
    parameters: Literal[14721]
    zero_initial_residual: Literal[True]
    count_divisor: Literal[128]
    entity_identity_features: Literal[False]
    output: Literal["linear residual; add current margin and clip to [-1,1]"]
    precision: Literal["float32 model; float64 baseline addition"]


class TrainingSpec(StrictRecord):
    seeds: tuple[int, ...]
    epochs: Literal[30]
    batch_rows: Literal[512]
    optimizer: Literal["AdamW"]
    learning_rate: Literal[0.0003]
    weight_decay: Literal[0.0001]
    gradient_clip: Literal[1.0]
    objective: Literal["unchanged scalar-pilot game/phase/representative weighted absolute residual error"]
    selection: Literal["fixed final epoch; no sweeps or calibration fitting"]

    @field_validator("seeds")
    @classmethod
    def exact_seeds(cls, value):
        if value != (1279501, 1279502):
            raise ValueError("fixed two-seed replication required")
        return value


class DataSpec(StrictRecord):
    directory: str
    collection_plan: str
    preflight: str
    globals_directory: str
    games: Literal[1536]
    rows: Literal[618149]
    clusters: Literal[768]
    fitting_games_per_fold: Literal[1152]
    excluded_games_per_fold: Literal[384]
    learner_cards: tuple[str, ...]
    hand_tokens: tuple[int, ...]
    vocabulary: tuple[str, ...]
    expected_audit: dict[str, Any]
    feature_layout_sha256: SHA256

    @field_validator("learner_cards")
    @classmethod
    def eight_cards(cls, value):
        if len(value) != 8 or len(set(value)) != 8:
            raise ValueError("eight distinct declared learner cards required")
        return value

    @field_validator("hand_tokens")
    @classmethod
    def hand_inventory(cls, value):
        if len(value) != 9 or tuple(sorted(set(value))) != value or value[0] != 0 or value[1] <= 1:
            raise ValueError("empty slot plus eight distinct learner identities required")
        return value


class AuthoritySpec(StrictRecord):
    implementation: dict[str, SHA256]
    resources: dict[str, SHA256]
    runtime: dict[str, str | int]


class FrozenPlan(StrictRecord):
    schema_id: Literal["clasher.hog26.numeric-residual-margin.v1"]
    status: Literal["frozen-requires-memory-readiness"]
    created_at: str
    hypothesis: str
    model: ModelSpec
    training: TrainingSpec
    data: DataSpec
    authority: AuthoritySpec
    limitations: tuple[str, ...]
    acceptance: Literal[False]
    policy_updates_allowed: Literal[False]
    reserved_collection_allowed: Literal[False]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_inventory():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def runtime_signature():
    return {"python": platform.python_version(), "numpy": np.__version__,
            "torch": str(torch.__version__), "torch_threads": torch.get_num_threads(), "device": "cpu"}


def load_plan(path):
    plan = FrozenPlan.model_validate_json(Path(path).read_text())
    if plan.authority.implementation != source_inventory():
        raise ValueError("residual experiment source differs from frozen plan")
    if plan.authority.runtime != runtime_signature() or torch.get_num_threads() != 1:
        raise ValueError("residual runtime differs from frozen plan")
    for resource, expected in plan.authority.resources.items():
        if sha(resource) != expected:
            raise ValueError("frozen residual resource changed: " + resource)
    return plan
