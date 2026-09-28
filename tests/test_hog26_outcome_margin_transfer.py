import numpy as np
import torch

from clasher.rl.outcome_model import outcome_state_sha256
from scripts.hog26_outcome_margin_transfer import (
    fit_transferred_margin,
    transfer_features,
)


def test_transfer_features_keep_public_suffix_and_detach_encoder():
    encoder = torch.nn.Linear(18, 4)
    public = torch.randn(6, 18)
    features = transfer_features(encoder, public)
    assert features.shape == (6, 22)
    assert torch.equal(features[:, -18:], public)
    assert not features.requires_grad


def test_margin_fit_leaves_encoder_frozen_and_ignores_withheld_targets():
    torch.manual_seed(91)
    encoder = torch.nn.Linear(18, 4)
    before = outcome_state_sha256(encoder.state_dict())
    public = torch.rand(6, 18)
    targets = torch.tensor([0.2, -0.1, 0.3, 0.9, -0.9, 0.5])
    config = {"loss": "absolute", "aggregate_phase_balance": True, "hidden_size": 2,
              "residual_scale": 0.5, "progress_power": 0.0, "learning_rate": 0.001,
              "weight_decay": 0.0001, "epochs": 1, "batch_size": 2}
    args = (encoder, public, targets, torch.ones(6), np.array([0, 1, 2, 0, 1, 2]), np.arange(3), config, 73)
    first = fit_transferred_margin(*args)
    targets[3:] *= -1
    second = fit_transferred_margin(*args)
    assert torch.equal(first, second)
    assert outcome_state_sha256(encoder.state_dict()) == before
    assert all(p.grad is None for p in encoder.parameters())
