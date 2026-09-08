"""Load a pinned, development-accepted outcome head without fitting it."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import torch

from clasher.rl.outcome_model import ActorOutcomeHead, outcome_state_sha256


def load_frozen_outcome_head(
    path: Path,
    *,
    checkpoint_sha256: str,
    state_sha256: str,
    base_policy_sha256: str,
    protocol_sha256: str,
) -> tuple[ActorOutcomeHead, dict[str, Any]]:
    """Require external pins before deserializing; retain fitted calibration."""
    for digest in (
        checkpoint_sha256, state_sha256, base_policy_sha256, protocol_sha256
    ):
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("frozen evaluation requires explicit SHA-256 pins")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != checkpoint_sha256:
        raise ValueError("frozen checkpoint SHA-256 mismatch")
    payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    if payload.get("schema") != "clasher.hog26.actor-outcome-training.v1":
        raise ValueError("unsupported frozen outcome checkpoint schema")
    report = payload["training_report"]
    if (
        report.get("status") != "accepted-development"
        or report.get("holdout_corpora") != []
        or report.get("holdout_corpus_sha256") != []
        or not (report.get("validation_public_slices") or {}).get("passed")
        or report.get("calibration_timing")
        != "once-after-outcome-and-margin-epoch-selection-v1"
    ):
        raise ValueError("frozen checkpoint lacks eligible development evidence")
    if (
        payload.get("base_checkpoint_sha256") != base_policy_sha256
        or report.get("base_checkpoint_sha256") != base_policy_sha256
        or report.get("generalization_protocol_sha256") != protocol_sha256
    ):
        raise ValueError("frozen checkpoint policy or protocol binding mismatch")
    state = payload["outcome_head_state_dict"]
    if (
        outcome_state_sha256(state) != state_sha256
        or report.get("outcome_head_state_sha256") != state_sha256
    ):
        raise ValueError("frozen outcome state SHA-256 mismatch")
    if any(not torch.isfinite(tensor).all() for tensor in state.values()):
        raise ValueError("frozen outcome state contains nonfinite values")
    fields = (
        "state_size", "hidden_size", "separate_draw_trunk",
        "structured_residual_scale", "margin_residual_scale",
        "margin_feature_set", "margin_progress_power",
    )
    if any(payload[key] != report.get(key) for key in fields):
        raise ValueError("frozen architecture disagrees with training report")
    head = ActorOutcomeHead(**{key: payload[key] for key in fields})
    head.load_state_dict(state, strict=True)
    head.eval()
    head.requires_grad_(False)
    if outcome_state_sha256(head.state_dict()) != state_sha256:
        raise ValueError("loading changed frozen outcome state")
    return head, report
