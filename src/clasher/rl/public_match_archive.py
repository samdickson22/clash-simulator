"""Auditable match archives around the versioned public observation contract."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import NUM_HAND_SLOTS, NUM_TILES
from .public_policy_contract import PublicPolicySequence

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NUM_ACTIONS = NUM_HAND_SLOTS * NUM_TILES + 2


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PublicDecision(StrictRecord):
    observation_tick: int = Field(ge=0)
    submission_tick: int = Field(ge=0)
    action: int = Field(ge=0, lt=NUM_ACTIONS)
    accepted: bool | None
    execution_tick: int | None = Field(default=None, ge=0)
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def chronological(self):
        if self.submission_tick < self.observation_tick:
            raise ValueError("submission precedes its observation")
        if self.execution_tick is not None and (
            self.accepted is not True or self.execution_tick < self.submission_tick
        ):
            raise ValueError("execution lacks ordered acceptance evidence")
        if self.accepted is False and not self.rejection_reason:
            raise ValueError("rejected action requires a recorded reason")
        if self.accepted is not False and self.rejection_reason is not None:
            raise ValueError("rejection reason contradicts acceptance status")
        return self


class MatchProvenance(StrictRecord):
    schema_version: Literal[2] = 2
    physical_match_id: str = Field(min_length=1)
    duplicate_group_id: str = Field(min_length=1)
    perspective: Literal[0, 1]
    role: Literal["development", "training", "selection", "acceptance"]
    source_kind: Literal["synthetic_diagnostic", "native_reference", "observed_game"]
    source_sha256: Digest
    ruleset_sha256: Digest
    producer_sha256: Digest
    game_build: str = Field(min_length=1)
    observation_domain: Literal[
        "simulator-exact", "causal-frame-v1", "causal-vision-v1"
    ]
    seed: int | None
    tick_ms: Literal[50] = 50
    opened_for_development: bool
    coverage: Literal["partial", "complete"] = "partial"
    terminal_tick: int | None = Field(default=None, ge=0)
    terminal_result: Literal["owner_win", "owner_loss", "draw"] | None = None

    @model_validator(mode="after")
    def protect_roles(self):
        if self.coverage == "complete" and (
            self.terminal_tick is None or self.terminal_result is None
        ):
            raise ValueError("complete game requires terminal tick and result")
        if self.coverage == "partial" and self.terminal_result is not None:
            raise ValueError("partial capture must not claim a completed-game result")
        if self.opened_for_development and self.role != "development":
            raise ValueError("opened development evidence cannot change roles")
        if self.source_kind == "synthetic_diagnostic" and self.role != "development":
            raise ValueError("synthetic diagnostic is not acceptance or training data")
        return self


class ArchiveReceipt(StrictRecord):
    provenance: MatchProvenance
    observations_sha256: Digest
    decisions_sha256: Digest
    masks_sha256: Digest
    count: int = Field(gt=0)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def validate_split_assignments(provenances: list[MatchProvenance]) -> None:
    """Keep perspectives and known duplicate groups in one data role."""
    seen = {}
    for row in provenances:
        for key in (
            ("physical", row.physical_match_id),
            ("duplicate", row.duplicate_group_id),
        ):
            prior = seen.setdefault(key, row.role)
            if prior != row.role:
                raise ValueError(f"match or duplicate group crosses data roles: {key}")


def validate_rows(sequence, provenance, decisions, masks):
    sequence.__post_init__()
    count = len(sequence.arrays["own_last_play_ids"])
    if (
        len(decisions) != count
        or masks.dtype != np.bool_
        or masks.shape != (count, NUM_ACTIONS)
    ):
        raise ValueError("decisions and masks must align with public observations")
    sequence.validate_action_mask(masks)
    ticks = [row.observation_tick for row in decisions]
    if any(b <= a for a, b in pairwise(ticks)):
        raise ValueError("observation ticks must increase strictly")
    if (
        provenance.observation_domain != "simulator-exact"
        and "global_feature_confidence" not in sequence.arrays
    ):
        raise ValueError("causal observations require public confidence arrays")
    for index, row in enumerate(decisions):
        if (
            provenance.terminal_tick is not None
            and max(row.observation_tick, row.submission_tick, row.execution_tick or 0)
            > provenance.terminal_tick
        ):
            raise ValueError("decision occurs after the declared terminal tick")
        if not masks[index].any():
            raise ValueError("decision has no public legal action")
        if row.accepted is True and not masks[index, row.action]:
            raise ValueError("accepted action contradicts its public action mask")


def save_match_archive(
    path: Path,
    sequence: PublicPolicySequence,
    provenance: MatchProvenance,
    decisions: list[PublicDecision],
    masks: np.ndarray,
) -> ArchiveReceipt:
    validate_rows(sequence, provenance, decisions, masks)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{path.name}-", dir=path.parent))
    try:
        sequence.save(staging / "observations.npz")
        (staging / "decisions.json").write_text(
            json.dumps([r.model_dump() for r in decisions], indent=2) + "\n"
        )
        with (staging / "masks.npy").open("xb") as stream:
            np.save(stream, masks, allow_pickle=False)
        receipt = ArchiveReceipt(
            provenance=provenance,
            observations_sha256=digest(staging / "observations.npz"),
            decisions_sha256=digest(staging / "decisions.json"),
            masks_sha256=digest(staging / "masks.npy"),
            count=len(decisions),
        )
        (staging / "receipt.json").write_text(receipt.model_dump_json(indent=2) + "\n")
        # Refuse replacement even if another publisher claimed the destination.
        path.mkdir()
        try:
            os.rename(staging, path)
        except BaseException:
            # Only remove the empty directory claimed by this publisher.
            if path.exists() and not any(path.iterdir()):
                path.rmdir()
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return receipt


def load_match_archive(
    path: Path,
    *,
    token_names: tuple[str, ...],
    source_path: Path | None = None,
    ruleset_path: Path | None = None,
    producer_path: Path | None = None,
):
    receipt = ArchiveReceipt.model_validate_json((path / "receipt.json").read_text())
    references = (
        (source_path, receipt.provenance.source_sha256),
        (ruleset_path, receipt.provenance.ruleset_sha256),
        (producer_path, receipt.provenance.producer_sha256),
    )
    if receipt.provenance.role != "development" and any(
        path is None for path, _ in references
    ):
        raise ValueError("non-development data requires verified provenance artifacts")
    for reference_path, expected in references:
        if reference_path is not None and digest(reference_path) != expected:
            raise ValueError("provenance artifact digest mismatch")
    for name, expected in [
        ("observations.npz", receipt.observations_sha256),
        ("decisions.json", receipt.decisions_sha256),
        ("masks.npy", receipt.masks_sha256),
    ]:
        if digest(path / name) != expected:
            raise ValueError(f"archive digest mismatch: {name}")
    sequence = PublicPolicySequence.load(
        path / "observations.npz", token_names=token_names
    )
    raw = json.loads((path / "decisions.json").read_text())
    decisions = [PublicDecision.model_validate(r) for r in raw]
    masks = np.load(path / "masks.npy", allow_pickle=False)
    validate_rows(sequence, receipt.provenance, decisions, masks)
    if receipt.count != len(decisions):
        raise ValueError("archive receipt count mismatch")
    return receipt, sequence, decisions, masks
