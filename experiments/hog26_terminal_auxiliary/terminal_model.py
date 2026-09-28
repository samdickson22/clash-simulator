"""Fixed public-state Bernoulli model for the next decision interval."""

import math

import numpy as np
import torch
from torch import nn


class TerminalPredictor(nn.Module):
    def __init__(self, prior=.5):
        super().__init__()
        if not 0 < prior < 1:
            raise ValueError("a nondegenerate fitting-only prior is required")
        self.network = nn.Sequential(nn.Linear(809, 32), nn.GELU(),
                                     nn.Linear(32, 32), nn.GELU(), nn.Linear(32, 1))
        nn.init.zeros_(self.network[-1].weight)
        nn.init.constant_(self.network[-1].bias, math.log(prior / (1 - prior)))

    def forward(self, features):
        if features.ndim != 2 or features.shape[1] != 809:
            raise ValueError("expected the frozen 809 public features")
        return self.network(features).squeeze(-1)


def optimizer_for(model):
    return torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)


def step(model, optimizer, x, target, weight, fitting_rows):
    optimizer.zero_grad(set_to_none=True)
    losses = nn.functional.binary_cross_entropy_with_logits(model(x), target, reduction="none")
    loss = (losses * weight).sum() * fitting_rows / len(x)
    if not torch.isfinite(loss):
        raise FloatingPointError("nonfinite auxiliary loss")
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
    optimizer.step()
    return float(loss.detach())


def fit(features, labels, rows, weights, seed, *, epochs=30, batch=512, log=None):
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not len(rows) or not np.array_equal(rows, np.unique(rows))
            or rows[0] < 0 or rows[-1] >= len(features)):
        raise ValueError("distinct ordered fitting rows required")
    active = np.zeros(len(features), dtype=bool)
    active[rows] = True
    if (features.shape[1:] != (809,) or features.dtype != np.float32
            or labels.shape != (len(features),) or weights.shape != labels.shape
            or not np.isin(labels[active], [0, 1]).all() or not np.isfinite(weights).all()
            or (weights < 0).any() or weights[~active].any()
            or not np.isclose(weights.sum(), 1) or epochs <= 0 or batch <= 0):
        raise ValueError("invalid auxiliary fitting contract")
    prior = float(np.sum(labels[active] * weights[active]))
    torch.manual_seed(seed)
    model = TerminalPredictor(prior)
    optimizer = optimizer_for(model)
    x = torch.from_numpy(features)
    y = torch.from_numpy(labels.astype(np.float32))
    w = torch.from_numpy(weights.astype(np.float32))
    selected = torch.from_numpy(rows.astype(np.int64))
    for epoch in range(epochs):
        order = torch.randperm(len(rows))
        for start in range(0, len(rows), batch):
            chosen = selected[order[start:start + batch]]
            step(model, optimizer, x[chosen], y[chosen], w[chosen], len(rows))
        if log:
            log({"epoch": epoch + 1})
    return model.eval(), prior


def predict(model, features):
    result = np.empty(len(features), dtype=np.float64)
    with torch.inference_mode():
        for start in range(0, len(features), 4096):
            result[start:start + 4096] = torch.sigmoid(model(torch.from_numpy(features[start:start + 4096]))).numpy()
    if not np.isfinite(result).all() or ((result < 0) | (result > 1)).any():
        raise ValueError("invalid auxiliary probabilities")
    return result
