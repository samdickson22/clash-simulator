from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.counterfactual_corpus import CandidateContext
from clasher.rl.structured_action_value import (
    PublicStructuredActionValueHead,
    StructuredActionValueConfig,
    public_structured_action_value_checkpoint,
)
from clasher.rl.structured_action_value_controller import (
    PublicStructuredActionValueState,
    load_public_structured_action_value_head,
)


def test_structured_action_value_checkpoint_loads_and_selects(tmp_path: Path) -> None:
    torch.manual_seed(2304)
    config = StructuredActionValueConfig(
        state_size=7,
        entity_feature_size=6,
        global_feature_size=4,
        entity_card_feature_size=5,
        card_feature_size=5,
        tile_feature_size=3,
        visible_card_slots=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        hidden_size=24,
    )
    head = PublicStructuredActionValueHead(config, torch.randn(11, 5)).eval()
    path = tmp_path / "head.pt"
    torch.save(
        public_structured_action_value_checkpoint(
            head=head,
            source_policy="policy.pt",
            source_policy_sha256="a" * 64,
            corpus_sha256="b" * 64,
            minimum_score_gain=0.0,
        ),
        path,
    )
    loaded = load_public_structured_action_value_head(
        path,
        device=torch.device("cpu"),
    )
    structured = PublicStructuredActionValueState(
        entity_ids=np.asarray([2, 0, 3, 0]),
        entity_features=np.zeros((4, 6), dtype=np.float32),
        entity_mask=np.asarray([True, False, True, False]),
        hand_ids=np.asarray([2, 3, 4, 5, 6]),
        global_features=np.zeros(4, dtype=np.float32),
    )
    context = CandidateContext(
        valid=np.asarray([True, True, False]),
        kinds=np.asarray([1, 0, -1], dtype=np.int8),
        card_ids=np.asarray([0, 2, 0]),
        card_features=np.zeros((3, 5), dtype=np.float32),
        tile_features=np.zeros((3, 3), dtype=np.float32),
        policy_logits=np.zeros(3, dtype=np.float32),
        policy_log_probabilities=np.zeros(3, dtype=np.float32),
        policy_type_log_probabilities=np.zeros(3, dtype=np.float32),
    )

    selected, scores = loaded.select_candidate(
        torch.zeros(7),
        structured,
        context,
    )

    assert selected in {0, 1}
    assert np.isneginf(scores[2])
    assert loaded.source_policy_sha256 == "a" * 64

    with pytest.raises(ValueError, match="legal base"):
        loaded.select_candidate(
            torch.zeros(7),
            structured,
            replace(
                context,
                valid=np.asarray([False, True, False]),
            ),
        )
    with pytest.raises(ValueError, match="misaligned"):
        loaded.select_candidate(
            torch.zeros(7),
            structured,
            replace(context, policy_logits=np.zeros(2, dtype=np.float32)),
        )

    payload = torch.load(path, map_location="cpu", weights_only=False)
    payload["minimum_score_gain"] = float("nan")
    torch.save(payload, path)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        load_public_structured_action_value_head(
            path,
            device=torch.device("cpu"),
        )


def test_structured_action_value_controller_requires_v2_recurrent_state(
    tmp_path: Path,
) -> None:
    torch.manual_seed(2305)
    config = StructuredActionValueConfig(
        state_size=7,
        entity_feature_size=6,
        global_feature_size=4,
        entity_card_feature_size=5,
        card_feature_size=5,
        tile_feature_size=3,
        visible_card_slots=5,
        d_model=16,
        num_heads=4,
        num_layers=1,
        hidden_size=24,
        recurrent_cell_size=3,
        play_hazard_size=1,
    )
    head = PublicStructuredActionValueHead(config, torch.randn(11, 5)).eval()
    path = tmp_path / "recurrent-head.pt"
    torch.save(
        public_structured_action_value_checkpoint(
            head=head,
            source_policy="policy.pt",
            source_policy_sha256="a" * 64,
            corpus_sha256="b" * 64,
            minimum_score_gain=0.0,
        ),
        path,
    )
    loaded = load_public_structured_action_value_head(
        path,
        device=torch.device("cpu"),
    )
    structured = PublicStructuredActionValueState(
        entity_ids=np.asarray([2, 0]),
        entity_features=np.zeros((2, 6), dtype=np.float32),
        entity_mask=np.asarray([True, False]),
        hand_ids=np.asarray([2, 3, 4, 5, 6]),
        global_features=np.zeros(4, dtype=np.float32),
        recurrent_cell=np.asarray([0.2, 0.3, -0.1], dtype=np.float32),
        previous_play_hazard=np.asarray([0.4], dtype=np.float32),
    )
    context = CandidateContext(
        valid=np.asarray([True, True]),
        kinds=np.asarray([1, 0], dtype=np.int8),
        card_ids=np.asarray([0, 2]),
        card_features=np.zeros((2, 5), dtype=np.float32),
        tile_features=np.zeros((2, 3), dtype=np.float32),
        policy_logits=np.zeros(2, dtype=np.float32),
        policy_log_probabilities=np.zeros(2, dtype=np.float32),
        policy_type_log_probabilities=np.zeros(2, dtype=np.float32),
    )

    selected, scores = loaded.select_candidate(
        torch.zeros(7),
        structured,
        context,
    )

    assert selected in {0, 1}
    assert np.isfinite(scores).all()
    with pytest.raises(ValueError, match="recurrent cell shape"):
        loaded.score_candidates(
            torch.zeros(7),
            replace(structured, recurrent_cell=None),
            context,
        )
    with pytest.raises(ValueError, match="parent state width"):
        loaded.score_candidates(
            torch.zeros(10),
            structured,
            context,
        )
