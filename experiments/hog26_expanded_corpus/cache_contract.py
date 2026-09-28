"""Strict authority for a complete, streamed 6144-game feature cache."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field
from semantic_contract import SHA256, StrictRecord, runtime_signature
from terminal_labels import sha


class CachePlan(StrictRecord):
    schema_id: Literal["clasher.hog26.expanded-feature-cache.v1"]
    games: Literal[6144]
    clusters: Literal[3072]
    rows: int = Field(gt=618149)
    columns: Literal[809]
    dtype: Literal["<f4"]
    feature_plan: str
    original_prefix_rows: Literal[618149]
    original_semantic_sha256: SHA256
    original_numeric_sha256: SHA256
    cohort_rows: dict[str, int]
    game_inventory_sha256: SHA256
    implementation: dict[str, SHA256]
    resources: dict[str, SHA256]
    runtime: dict[str, str | int]
    outcome_fitting: Literal[False]
    acceptance: Literal[False]
    scope: str


def sources():
    return {p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def game_inventory_hash(games):
    value = [{"path": str(g.path), "sha256": g.sha256, "cohort": g.cohort, "rows": g.record["rows"]} for g in games]
    import hashlib

    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_plan(path):
    plan = CachePlan.model_validate_json(Path(path).read_text())
    if plan.implementation != sources() or plan.runtime != runtime_signature():
        raise ValueError("expanded cache source or runtime changed")
    for resource, expected in plan.resources.items():
        if sha(resource) != expected:
            raise ValueError("expanded cache resource changed: " + resource)
    return plan
