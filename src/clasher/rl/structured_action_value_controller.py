from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from .counterfactual_corpus import CandidateContext
from .structured_action_value import (
    PublicStructuredActionValueHead,
    StructuredActionValueConfig,
)


@dataclass(frozen=True)
class PublicStructuredActionValueState:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    recurrent_cell: np.ndarray | None = None
    previous_play_hazard: np.ndarray | None = None


@dataclass(frozen=True)
class LoadedPublicStructuredActionValueHead:
    head: PublicStructuredActionValueHead
    source_policy: str
    source_policy_sha256: str
    corpus_sha256: str
    minimum_score_gain: float

    @torch.no_grad()
    def score_candidates(
        self,
        state_features: Tensor,
        structured: PublicStructuredActionValueState,
        context: CandidateContext,
    ) -> np.ndarray:
        device = next(self.head.parameters()).device
        state = state_features.detach().to(device=device, dtype=torch.float32)
        if state.ndim != 1:
            raise ValueError("structured action-value parent state must be rank one")
        entity_ids = np.asarray(structured.entity_ids, dtype=np.int64)
        entity_features = np.asarray(structured.entity_features, dtype=np.float32)
        entity_mask = np.asarray(structured.entity_mask, dtype=np.bool_)
        hand_ids = np.asarray(structured.hand_ids, dtype=np.int64)
        global_features = np.asarray(
            structured.global_features,
            dtype=np.float32,
        )
        recurrent_cell = (
            None
            if structured.recurrent_cell is None
            else np.asarray(structured.recurrent_cell, dtype=np.float32)
        )
        previous_play_hazard = (
            None
            if structured.previous_play_hazard is None
            else np.asarray(structured.previous_play_hazard, dtype=np.float32)
        )
        valid = np.asarray(context.valid, dtype=np.bool_)
        candidate_count = len(valid)
        if valid.ndim != 1 or candidate_count == 0 or not bool(valid[0]):
            raise ValueError(
                "structured action-value candidates need a legal base candidate"
            )
        candidate_arrays = (
            context.kinds,
            context.card_ids,
            context.card_features,
            context.tile_features,
            context.policy_logits,
            context.policy_log_probabilities,
            context.policy_type_log_probabilities,
        )
        if any(
            np.asarray(value).ndim == 0
            or int(np.asarray(value).shape[0]) != candidate_count
            for value in candidate_arrays
        ):
            raise ValueError("structured candidate context arrays are misaligned")
        if entity_ids.shape != entity_mask.shape or entity_features.shape[:-1] != (
            entity_ids.shape
        ):
            raise ValueError("structured action-value entity state is invalid")
        valid_entities = np.flatnonzero(entity_mask)
        maximum_entities = (
            int(valid_entities[-1]) + 1 if len(valid_entities) else 1
        )
        expected_state_size = self.head.config.state_size
        if state.shape != (expected_state_size,):
            raise ValueError(
                "structured action-value parent state width is invalid"
            )
        scores = self.head(
            state.unsqueeze(0),
            torch.as_tensor(
                entity_ids[:maximum_entities], device=device
            ).unsqueeze(0),
            torch.as_tensor(
                entity_features[:maximum_entities], device=device
            ).unsqueeze(0),
            torch.as_tensor(
                entity_mask[:maximum_entities], device=device
            ).unsqueeze(0),
            torch.as_tensor(hand_ids, device=device).unsqueeze(0),
            torch.as_tensor(global_features, device=device).unsqueeze(0),
            torch.as_tensor(context.card_features, device=device).unsqueeze(0),
            torch.as_tensor(context.tile_features, device=device).unsqueeze(0),
            torch.as_tensor(context.kinds, device=device).unsqueeze(0),
            torch.as_tensor(
                context.policy_log_probabilities, device=device
            ).unsqueeze(0),
            torch.as_tensor(
                context.policy_type_log_probabilities, device=device
            ).unsqueeze(0),
            (
                None
                if recurrent_cell is None
                else torch.as_tensor(recurrent_cell, device=device).unsqueeze(0)
            ),
            (
                None
                if previous_play_hazard is None
                else torch.as_tensor(
                    previous_play_hazard, device=device
                ).unsqueeze(0)
            ),
        )[0]
        valid_tensor = torch.as_tensor(valid, device=device)
        result = np.asarray(
            scores.masked_fill(~valid_tensor, -torch.inf).cpu().numpy(),
            dtype=np.float32,
        )
        if not np.isfinite(result[valid]).all():
            raise FloatingPointError("structured action-value produced non-finite scores")
        return result

    @torch.no_grad()
    def select_candidate(
        self,
        state_features: Tensor,
        structured: PublicStructuredActionValueState,
        context: CandidateContext,
    ) -> tuple[int, np.ndarray]:
        scores = self.score_candidates(state_features, structured, context)
        best = int(np.argmax(scores))
        if scores[best] <= scores[0] + self.minimum_score_gain:
            return 0, scores
        return best, scores


def load_public_structured_action_value_head(
    path: Path,
    *,
    device: torch.device,
) -> LoadedPublicStructuredActionValueHead:
    payload: dict[str, Any] = torch.load(
        path,
        map_location="cpu",
        weights_only=False,
    )
    if payload.get("schema") != "clasher.public_structured_action_value.v1":
        raise ValueError("unsupported public structured action-value checkpoint")
    source_policy_sha256 = payload.get("source_policy_sha256")
    if not isinstance(source_policy_sha256, str) or len(source_policy_sha256) != 64:
        raise ValueError("structured action-value checkpoint lacks policy authority")
    state_dict = dict(payload["state_dict"])
    card_stats = state_dict.get("card_stat_features")
    if not isinstance(card_stats, Tensor):
        raise TypeError("structured action-value checkpoint lacks card statistics")
    head = PublicStructuredActionValueHead(
        StructuredActionValueConfig(**dict(payload["config"])),
        card_stats,
    ).to(device)
    head.load_state_dict(state_dict)
    head.eval()
    minimum_score_gain = float(payload["minimum_score_gain"])
    if not np.isfinite(minimum_score_gain) or minimum_score_gain < 0.0:
        raise ValueError("structured action-value threshold must be finite and nonnegative")
    corpus_sha256 = payload.get("corpus_sha256")
    if not isinstance(corpus_sha256, str) or len(corpus_sha256) != 64:
        raise ValueError("structured action-value checkpoint lacks corpus authority")
    return LoadedPublicStructuredActionValueHead(
        head=head,
        source_policy=str(payload["source_policy"]),
        source_policy_sha256=source_policy_sha256,
        corpus_sha256=corpus_sha256,
        minimum_score_gain=minimum_score_gain,
    )
