import hashlib

import pytest
import torch

from clasher.rl.outcome_model import ActorOutcomeHead, outcome_state_sha256
from scripts.hog26_frozen_outcome import load_frozen_outcome_head


def fixture_payload():
    config = {
        "state_size": 18, "hidden_size": 4, "separate_draw_trunk": False,
        "structured_residual_scale": 0.0, "margin_residual_scale": 0.5,
        "margin_feature_set": "public-globals", "margin_progress_power": 1.0,
    }
    head = ActorOutcomeHead(**config)
    head.probability_shrinkage.fill_(0.37)
    head.outcome_probability_prior.copy_(torch.tensor([0.6, 0.1, 0.3]))
    state = head.state_dict()
    report = dict(
        **config, status="accepted-development", holdout_corpora=[],
        holdout_corpus_sha256=[], validation_public_slices={"passed": True},
        calibration_timing="once-after-outcome-and-margin-epoch-selection-v1",
        base_checkpoint_sha256="a" * 64,
        generalization_protocol_sha256="b" * 64,
        outcome_head_state_sha256=outcome_state_sha256(state),
    )
    return head, dict(
        **config, schema="clasher.hog26.actor-outcome-training.v1",
        base_checkpoint_sha256="a" * 64,
        training_report=report, outcome_head_state_dict=state,
    )


def save_and_load(tmp_path, payload, **overrides):
    path = tmp_path / "head.pt"
    torch.save(payload, path)
    pins = {
        "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "state_sha256": payload["training_report"]["outcome_head_state_sha256"],
        "base_policy_sha256": "a" * 64, "protocol_sha256": "b" * 64,
    }
    pins.update(overrides)
    return load_frozen_outcome_head(path, **pins)


def test_frozen_round_trip_preserves_calibrated_predictions(tmp_path):
    original, payload = fixture_payload()
    frozen, _ = save_and_load(tmp_path, payload)
    features = torch.randn(12, 18)
    before, after = original(features), frozen(features)
    assert torch.equal(before.outcome_logits, after.outcome_logits)
    assert torch.equal(before.terminal_tower_margin, after.terminal_tower_margin)
    assert not frozen.training
    assert not any(p.requires_grad for p in frozen.parameters())
    assert outcome_state_sha256(original.state_dict()) == outcome_state_sha256(
        frozen.state_dict()
    )


@pytest.mark.parametrize("field", [
    "checkpoint_sha256", "state_sha256", "base_policy_sha256", "protocol_sha256",
])
def test_external_pin_mismatch_rejected(tmp_path, field):
    _, payload = fixture_payload()
    with pytest.raises(ValueError, match="mismatch"):
        save_and_load(tmp_path, payload, **{field: "c" * 64})


@pytest.mark.parametrize("field,value", [
    ("status", "rejected-development"),
    ("holdout_corpora", ["already-opened.npz"]),
    ("validation_public_slices", None),
    ("calibration_timing", "per-epoch"),
])
def test_ineligible_development_evidence_rejected(tmp_path, field, value):
    _, payload = fixture_payload()
    payload["training_report"][field] = value
    with pytest.raises(ValueError, match="development evidence"):
        save_and_load(tmp_path, payload)


def test_corrupted_state_rejected_with_valid_file_digest(tmp_path):
    _, payload = fixture_payload()
    payload["outcome_head_state_dict"]["probability_shrinkage"].fill_(0.9)
    with pytest.raises(ValueError, match="state SHA-256 mismatch"):
        save_and_load(tmp_path, payload)


def test_architecture_mismatch_rejected(tmp_path):
    _, payload = fixture_payload()
    payload["margin_progress_power"] = 6.0
    with pytest.raises(ValueError, match="architecture"):
        save_and_load(tmp_path, payload)


def test_frozen_loader_reconstructs_explicit_dynamics_contract(tmp_path):
    _, payload = fixture_payload()
    for record in (payload, payload["training_report"]):
        record["state_size"] = 19
        record["margin_dynamics"] = "overtime-damage-race-v1"
    payload["training_report"]["actor_feature_contract"] = "public-global-dynamics"
    head, _ = save_and_load(tmp_path, payload)
    assert head.margin_dynamics == "overtime-damage-race-v1"
    payload["training_report"]["actor_feature_contract"] = "public-globals"
    with pytest.raises(ValueError, match="causal public feature contract"):
        save_and_load(tmp_path, payload)
