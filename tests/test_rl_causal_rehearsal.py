from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

from clasher.rl.causal_rehearsal import CausalDecisionRehearsal
from clasher.rl.hierarchical_imitation import NO_OP_ACTION, NUM_ACTIONS
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
)


def _artifacts(
    tmp_path: Path,
    *,
    supervised_masked: bool = False,
    tile_supervision: bool = False,
) -> tuple[Path, Path]:
    samples = 4
    token_names = ("<pad>", "<unknown>", "card_action:Knight")
    entity_ids = np.zeros((samples, 2), dtype=np.int64)
    entity_features = np.zeros((samples, 2, 32), dtype=np.float32)
    entity_mask = np.zeros((samples, 2), dtype=np.bool_)
    hand_ids = np.zeros((samples, 5), dtype=np.int64)
    hand_ids[:, 0] = 2
    globals_ = np.zeros((samples, 18), dtype=np.float32)
    masks = np.zeros((samples, NUM_ACTIONS), dtype=np.bool_)
    masks[:, NO_OP_ACTION] = True
    masks[:, 0] = True
    masks[:, 1] = True
    masks[:, 576] = True
    actions = np.asarray([NO_OP_ACTION, 0, NO_OP_ACTION, 0], dtype=np.int64)
    if supervised_masked:
        masks[1, 0] = False
    metadata = {
        "token_names": list(token_names),
        "max_entities": 2,
        "samples": samples,
    }
    corpus = tmp_path / "corpus.npz"
    corpus_values = {
        "entity_ids": entity_ids,
        "entity_features": entity_features,
        "entity_mask": entity_mask,
        "hand_ids": hand_ids,
        "global_features": globals_,
        "action_masks": masks,
        "previous_actions": np.full(samples, NO_OP_ACTION, dtype=np.int64),
        "previous_rewards": np.ones(samples, dtype=np.float32),
        "episode_starts": np.asarray([True, False, False, False], dtype=np.bool_),
        "expert_actions": actions,
        "expert_action_supervision_valid": np.ones(samples, dtype=np.bool_),
        "episode_ids": np.zeros(samples, dtype=np.int64),
        "source_frames": np.arange(samples, dtype=np.int64),
        "metadata_json": np.asarray(json.dumps(metadata)),
    }
    if tile_supervision:
        corpus_values["expert_tile_supervision_valid"] = (
            actions < NO_OP_ACTION
        )
    np.savez_compressed(corpus, **corpus_values)
    sidecar = tmp_path / "public_v2.npz"
    np.savez_compressed(
        sidecar,
        schema_version=np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
        feature_contract_version=np.asarray(REAL_PLAY_FEATURE_CONTRACT_VERSION),
        action_mask_contract_version=np.asarray(PUBLIC_ACTION_MASK_CONTRACT_VERSION),
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        entity_id_confidence=np.zeros_like(entity_ids, dtype=np.float32),
        entity_feature_confidence=np.zeros_like(entity_features),
        hand_ids=hand_ids,
        hand_id_confidence=np.ones_like(hand_ids, dtype=np.float32),
        global_features=globals_,
        global_feature_confidence=np.ones_like(globals_),
        action_masks=masks,
        expert_action_masked=~masks[np.arange(samples), actions],
        expert_actions=actions,
        episode_ids=np.zeros(samples, dtype=np.int64),
        source_frames=np.arange(samples, dtype=np.int64),
    )
    return corpus, sidecar


class _DummyPolicy(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(6))
        self.locations = nn.Parameter(torch.zeros(4, 576))

    def forward(self, inputs: object) -> SimpleNamespace:
        batch = inputs.entity_ids.shape[0]  # type: ignore[attr-defined]
        steps = inputs.entity_ids.shape[1]  # type: ignore[attr-defined]
        action_type = self.logits.reshape(1, 1, 6).expand(batch, steps, 6)
        locations = self.locations.reshape(1, 1, 4, 576).expand(
            batch, steps, 4, 576
        )
        return SimpleNamespace(
            action_type_logits=action_type,
            location_logits=locations,
            play_hazard_logits=None,
        )


class _DummyHazardPolicy(_DummyPolicy):
    def __init__(self) -> None:
        super().__init__()
        self.hazard = nn.Parameter(torch.zeros(()))
        self.config = SimpleNamespace(play_hazard_positive_weight=9.0)

    def forward(self, inputs: object) -> SimpleNamespace:
        output = super().forward(inputs)
        batch = inputs.entity_ids.shape[0]  # type: ignore[attr-defined]
        steps = inputs.entity_ids.shape[1]  # type: ignore[attr-defined]
        output.play_hazard_logits = self.hazard.expand(batch, steps)
        return output


def test_causal_rehearsal_loads_public_inputs_and_backpropagates(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    assert rehearsal.chunks.shape == (1, 4)
    assert not np.any(rehearsal.arrays["previous_rewards"])
    model = _DummyPolicy()
    loss = rehearsal.loss(model, device=torch.device("cpu"), batch_sequences=1)
    assert torch.isfinite(loss)
    loss.backward()
    assert model.logits.grad is not None
    assert bool(torch.isfinite(model.logits.grad).all())


def test_causal_rehearsal_rejects_supervised_masked_action(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path, supervised_masked=True)
    with pytest.raises(ValueError, match="supervised masked action"):
        CausalDecisionRehearsal.load(
            corpus,
            sidecar,
            token_names=("<pad>", "<unknown>", "card_action:Knight"),
            max_entities=2,
            sequence_length=4,
            seed=7,
        )


def test_causal_rehearsal_trains_dedicated_hazard_head(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    model = _DummyHazardPolicy()
    loss = rehearsal.loss(model, device=torch.device("cpu"), batch_sequences=1)
    loss.backward()
    assert model.hazard.grad is not None
    assert float(model.hazard.grad) != 0.0
    assert model.logits.grad is None


def test_causal_rehearsal_optionally_trains_public_card_choice(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    model = _DummyHazardPolicy()
    loss = rehearsal.loss(
        model,
        device=torch.device("cpu"),
        batch_sequences=1,
        card_loss_coef=1.0,
    )
    loss.backward()
    assert model.hazard.grad is not None
    assert model.logits.grad is not None
    assert float(model.logits.grad[:2].abs().sum()) > 0.0


def test_causal_rehearsal_optionally_trains_trusted_tile_choice(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path, tile_supervision=True)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    model = _DummyHazardPolicy()
    loss = rehearsal.loss(
        model,
        device=torch.device("cpu"),
        batch_sequences=1,
        card_loss_coef=1.0,
        tile_loss_coef=1.0,
    )
    loss.backward()
    assert model.locations.grad is not None
    assert float(model.locations.grad.abs().sum()) > 0.0


def test_causal_rehearsal_can_freeze_timing_while_training_card_and_tile(
    tmp_path: Path,
) -> None:
    corpus, sidecar = _artifacts(tmp_path, tile_supervision=True)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    model = _DummyHazardPolicy()
    loss = rehearsal.loss(
        model,
        device=torch.device("cpu"),
        batch_sequences=1,
        decision_loss_coef=0.0,
        card_loss_coef=1.0,
        tile_loss_coef=1.0,
    )
    loss.backward()
    assert model.hazard.grad is None or float(model.hazard.grad) == 0.0
    assert model.logits.grad is not None
    assert model.locations.grad is not None


def test_causal_rehearsal_accepts_corpus_specific_hazard_weight(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    default_model = _DummyHazardPolicy()
    default_loss = rehearsal.loss(
        default_model, device=torch.device("cpu"), batch_sequences=1
    )
    calibrated_model = _DummyHazardPolicy()
    calibrated_loss = rehearsal.loss(
        calibrated_model,
        device=torch.device("cpu"),
        batch_sequences=1,
        decision_positive_weight=1.0,
    )
    assert calibrated_loss < default_loss


def test_causal_rehearsal_weights_direct_play_gate_positives(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    rehearsal = CausalDecisionRehearsal.load(
        corpus,
        sidecar,
        token_names=("<pad>", "<unknown>", "card_action:Knight"),
        max_entities=2,
        sequence_length=4,
        seed=7,
    )
    baseline = _DummyPolicy()
    with torch.no_grad():
        baseline.logits[:4].fill_(-math.log(4.0))
    baseline_loss = rehearsal.loss(
        baseline,
        device=torch.device("cpu"),
        batch_sequences=1,
        decision_positive_weight=1.0,
    )
    baseline_loss.backward()
    weighted = _DummyPolicy()
    with torch.no_grad():
        weighted.logits[:4].fill_(-math.log(4.0))
    weighted_loss = rehearsal.loss(
        weighted,
        device=torch.device("cpu"),
        batch_sequences=1,
        decision_positive_weight=9.0,
    )
    weighted_loss.backward()

    assert baseline.logits.grad is not None
    assert weighted.logits.grad is not None
    torch.testing.assert_close(
        weighted.logits.grad,
        baseline.logits.grad,
        atol=1e-7,
        rtol=1e-7,
    )


def test_causal_rehearsal_rejects_sidecar_target_misalignment(tmp_path: Path) -> None:
    corpus, sidecar = _artifacts(tmp_path)
    with np.load(sidecar, allow_pickle=False) as payload:
        values = {name: payload[name].copy() for name in payload.files}
    values["expert_actions"][0] = 0
    np.savez_compressed(sidecar, **values)
    with pytest.raises(ValueError, match="expert_actions is not aligned"):
        CausalDecisionRehearsal.load(
            corpus,
            sidecar,
            token_names=("<pad>", "<unknown>", "card_action:Knight"),
            max_entities=2,
            sequence_length=4,
            seed=7,
        )
