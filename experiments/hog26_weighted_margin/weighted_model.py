"""Existing residual architectures with the same loss estimated by weighted draws."""

import numpy as np
import torch
from residual_training import NumericResidualMargin, make_optimizer, predict_margin
from semantic_training import SemanticResidualMargin

__all__ = ("batch_loss", "fit", "make_model", "make_optimizer", "predict_margin", "step")


def make_model(kind):
    if kind == "numeric":
        return NumericResidualMargin()
    if kind == "semantic":
        return SemanticResidualMargin()
    raise ValueError("unknown fixed margin architecture")


def batch_loss(prediction, target):
    return (prediction - target).abs().mean()


def step(model, optimizer, features, target):
    optimizer.zero_grad(set_to_none=True)
    loss = batch_loss(model(features), target)
    if not torch.isfinite(loss):
        raise FloatingPointError("nonfinite weighted-sampling margin loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
    optimizer.step()
    return float(loss.detach())


def fit(features, target, rows, weights, *, kind, seed, epochs=30, batch=512, log=None):
    width = 425 if kind == "numeric" else 809 if kind == "semantic" else None
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not len(rows) or not np.array_equal(rows, np.unique(rows))
            or rows[0] < 0 or rows[-1] >= len(features)):
        raise ValueError("distinct ordered fitting rows required")
    active = np.zeros(len(features), dtype=bool)
    active[rows] = True
    if (features.dtype != np.float32 or features.shape[1:] != (width,)
            or target.shape != (len(features),) or weights.shape != target.shape
            or not np.isfinite(target[active]).all() or not np.isfinite(weights).all()
            or (weights < 0).any() or weights[~active].any() or not np.isclose(weights.sum(), 1)
            or epochs <= 0 or batch <= 0):
        raise ValueError("invalid weighted margin fitting contract")
    torch.manual_seed(seed)
    model = make_model(kind)
    optimizer = make_optimizer(model)
    x, y = torch.from_numpy(features), torch.from_numpy(target.astype(np.float32))
    selected = torch.from_numpy(rows.astype(np.int64))
    mass = torch.from_numpy(weights[rows].astype(np.float64))
    for epoch in range(epochs):
        draws = torch.multinomial(mass, len(rows), replacement=True)
        for start in range(0, len(rows), batch):
            chosen = selected[draws[start:start + batch]]
            step(model, optimizer, x[chosen], y[chosen])
        if log:
            log({"epoch": epoch + 1})
    return model.eval()
