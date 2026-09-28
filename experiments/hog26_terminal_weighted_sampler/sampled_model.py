"""Change only the sampling estimator of the fixed weighted Bernoulli objective."""

import numpy as np
import torch
from terminal_model import TerminalPredictor, optimizer_for, predict  # noqa: F401


def batch_loss(logits, target):
    return torch.nn.functional.binary_cross_entropy_with_logits(logits, target, reduction="mean")


def step(model, optimizer, x, target):
    optimizer.zero_grad(set_to_none=True)
    loss = batch_loss(model(x), target)
    if not torch.isfinite(loss):
        raise FloatingPointError("nonfinite sampled auxiliary loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
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
        raise ValueError("invalid sampled fitting contract")
    prior = float(np.sum(labels[active] * weights[active]))
    torch.manual_seed(seed)
    model = TerminalPredictor(prior)
    optimizer = optimizer_for(model)
    x = torch.from_numpy(features)
    y = torch.from_numpy(labels.astype(np.float32))
    selected = torch.from_numpy(rows.astype(np.int64))
    sampling_mass = torch.from_numpy(weights[rows].astype(np.float64))
    for epoch in range(epochs):
        draws = torch.multinomial(sampling_mass, len(rows), replacement=True)
        for start in range(0, len(rows), batch):
            chosen = selected[draws[start:start + batch]]
            step(model, optimizer, x[chosen], y[chosen])
        if log:
            log({"epoch": epoch + 1})
    return model.eval(), prior
