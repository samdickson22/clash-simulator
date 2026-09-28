"""Matched frozen-encoder margin diagnostic, restricted to training families."""

import numpy as np
import torch
from torch.nn import functional as F

from clasher.rl.outcome_model import ActorOutcomeHead
from scripts.screen_hog26_training_family_margin import (
    fitting_phase_weights,
    full_phase_margin_summary,
)


@torch.no_grad()
def transfer_features(encoder, public):
    if public.shape[1] != 18:
        raise ValueError("margin transfer requires the public-global outcome encoder")
    encoded = torch.cat([encoder(batch) for batch in public.split(2048)])
    return torch.cat([encoded, public], dim=-1).detach()


def fit_transferred_margin(encoder, public, target, base_weights, phases, fit_rows, config, seed):
    if config["loss"] != "absolute":
        raise ValueError("undeclared transfer loss")
    features = transfer_features(encoder, public)
    weights = fitting_phase_weights(base_weights, phases, fit_rows,
                                   aggregate_balance=config["aggregate_phase_balance"])
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    head = ActorOutcomeHead(features.shape[1], hidden_size=config["hidden_size"],
                            margin_residual_scale=config["residual_scale"],
                            margin_progress_power=config["progress_power"],
                            margin_feature_set="full-state")
    head.requires_grad_(False)
    head.margin_trunk.requires_grad_(True)
    optimizer = torch.optim.AdamW(head.margin_trunk.parameters(), lr=config["learning_rate"],
                                  weight_decay=config["weight_decay"])
    for _ in range(config["epochs"]):
        order = rng.permutation(fit_rows)
        for begin in range(0, len(order), config["batch_size"]):
            rows = order[begin:begin + config["batch_size"]]
            prediction = head(features[rows]).terminal_tower_margin
            loss = (F.l1_loss(prediction, target[rows], reduction="none") * weights[rows]).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.margin_trunk.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
    with torch.no_grad():
        return torch.cat([head(batch).terminal_tower_margin for batch in features.split(2048)])


def margin_transfer_summary(prediction, target, public, offsets, phases, episodes, representatives):
    current = (public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3
    def summarize(rows):
        if not len(rows):
            return {"rows": 0, "mae_improvement": None}
        mae = float((prediction[rows] - target[rows]).abs().mean())
        baseline = float((current[rows] - target[rows]).abs().mean())
        return {"rows": len(rows), "mae": mae, "baseline_mae": baseline,
                "mae_improvement": baseline - mae}
    return {
        "representative_overall": summarize(representatives),
        "representative_by_phase": {
            name: summarize(representatives[phases[representatives] == i])
            for i, name in enumerate(("early", "middle", "late"))
        },
        "full_phase": full_phase_margin_summary(prediction, target, current, offsets, phases, episodes),
    }
