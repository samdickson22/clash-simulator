"""Small numeric residual model with fixed game/phase-weighted optimization."""

import time

import numpy as np
import torch
from torch import nn

INPUT_SIZE = 809
EPOCHS = 30
BATCH_ROWS = 512
SEEDS = (1279501, 1279502)


class SemanticResidualMargin(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(INPUT_SIZE, 32), nn.GELU(),
            nn.Linear(32, 32), nn.GELU(), nn.Linear(32, 1),
        )
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(self, features):
        if features.ndim != 2 or features.shape[1] != INPUT_SIZE:
            raise ValueError("expected 809 numeric public features")
        return self.network(features).squeeze(-1)


def make_optimizer(model):
    return torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)


def training_step(model, optimizer, features, targets, weights, expected_rows):
    optimizer.zero_grad(set_to_none=True)
    predicted = model(features)
    objective = ((predicted - targets).abs() * weights).sum() * expected_rows / len(features)
    if not torch.isfinite(objective):
        raise FloatingPointError("nonfinite residual objective")
    objective.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    optimizer.step()
    return float(objective.detach())


def fit_residual(features, fit_rows, target_residual, weights, *, seed,
                 epochs=EPOCHS, batch_rows=BATCH_ROWS, log=None):
    if features.dtype != np.float32 or features.ndim != 2 or features.shape[1] != INPUT_SIZE:
        raise ValueError("expected float32 public feature matrix")
    indices = np.asarray(fit_rows, dtype=np.int64)
    if (indices.ndim != 1 or not len(indices) or indices[0] < 0
            or indices[-1] >= len(features) or not np.array_equal(indices, np.unique(indices))):
        raise ValueError("fitting rows must be distinct, ordered, and in bounds")
    target_residual, weights = np.asarray(target_residual), np.asarray(weights)
    if target_residual.shape != (len(features),) or weights.shape != (len(features),):
        raise ValueError("targets and weights must match feature rows")
    active = np.zeros(len(features), dtype=bool)
    active[indices] = True
    if (not np.isfinite(target_residual[active]).all()
            or not np.isfinite(weights[active]).all() or (weights[active] < 0).any()
            or (weights[~active] != 0).any() or not np.isclose(weights[active].sum(), 1)):
        raise ValueError("invalid fitting targets or game/phase weights")
    if epochs <= 0 or batch_rows <= 0:
        raise ValueError("positive fixed training budget required")
    torch.manual_seed(seed)
    model = SemanticResidualMargin()
    optimizer = make_optimizer(model)
    x = torch.from_numpy(features)
    targets = torch.from_numpy(target_residual.astype(np.float32))
    mass = torch.from_numpy(weights.astype(np.float32))
    fitting = torch.from_numpy(indices)
    count = len(indices)
    began = time.monotonic()
    for epoch in range(epochs):
        order = torch.randperm(count)
        for start in range(0, count, batch_rows):
            chosen = fitting[order[start:start + batch_rows]]
            training_step(model, optimizer, x[chosen], targets[chosen], mass[chosen], count)
        if log:
            log({"epoch": epoch + 1, "elapsed_seconds": time.monotonic() - began})
    return model.eval()


def predict_margin(model, features, current, batch_rows=4096):
    current = np.asarray(current, dtype=np.float64)
    if current.shape != (len(features),) or not np.isfinite(current).all():
        raise ValueError("invalid public current-margin baseline")
    result = np.empty(len(features), dtype=np.float64)
    with torch.inference_mode():
        for start in range(0, len(features), batch_rows):
            end = start + batch_rows
            residual = model(torch.from_numpy(features[start:end])).numpy().astype(np.float64)
            result[start:end] = np.clip(current[start:end] + residual, -1, 1)
    if not np.isfinite(result).all():
        raise FloatingPointError("nonfinite predicted margin")
    return result
