"""Training-family classification diagnostic using audited shared screen inputs."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from itertools import pairwise

import numpy as np
import torch
from torch.nn import functional as F

from clasher.rl.outcome_model import ActorOutcomeHead, outcome_state_sha256
from scripts.hog26_outcome_margin_transfer import (
    fit_transferred_margin,
    margin_transfer_summary,
)
from scripts.hog26_public_slice_gates import weighted_outcome_metrics
from scripts.screen_hog26_training_family_margin import family_fit_rows
from scripts.train_hog26_actor_outcome import (
    _atomic_json,
    episode_balanced_row_weights,
    file_sha256,
    phase_balanced_row_indices,
)


def fit_outcome_weights(base_weights, row_outcomes, episode_outcomes, fit_rows,
                        fit_episodes, target_mass):
    """Use fitting labels only for class weights and empirical episode prior."""
    selected = base_weights[fit_rows].clone()
    classes = row_outcomes[fit_rows].long() + 1
    mass = torch.as_tensor(target_mass, dtype=selected.dtype)
    if mass.shape != (3,) or not torch.isfinite(mass).all() or (mass <= 0).any() or not torch.isclose(mass.sum(), mass.new_tensor(1.0)):
        raise ValueError("outcome screen requires positive declared class masses")
    for label in range(3):
        mask = classes == label
        total = selected[mask].sum()
        if total <= 0:
            raise ValueError("fitting fold lacks a required outcome class")
        selected[mask] *= mass[label] / total
    selected /= selected.mean()
    weights = torch.zeros_like(base_weights)
    weights[fit_rows] = selected
    prior = torch.bincount(episode_outcomes[fit_episodes].long() + 1, minlength=3).float()
    prior /= prior.sum()
    return weights, prior


def run_outcome_screen(*, plan, features, loaded, episode_families, episode_offsets,
                       source_records, plan_path, output, started):
    transfer = plan.get("margin_transfer")
    if transfer and plan["actor_feature_set"] != "public-globals":
        raise ValueError("transfer comparison requires public globals")
    outcomes = torch.from_numpy(np.concatenate([c.arrays["final_outcomes"] for _, c in loaded])).long()
    episode_outcomes = torch.from_numpy(np.concatenate([
        c.episode_arrays["episode_final_outcomes"] for _, c in loaded
    ])).long()
    base_weights = episode_balanced_row_weights(loaded, phase_balanced=True)
    phases = np.minimum((features[:, -18].numpy() * 3).astype(int), 2)
    row_families = np.repeat(episode_families, np.diff(episode_offsets))
    all_representatives = phase_balanced_row_indices(loaded).numpy()
    representatives = all_representatives[row_families[all_representatives] != "<auxiliary>"]
    natural_rows = np.flatnonzero(row_families != "<auxiliary>")
    phase_weights = np.zeros(len(outcomes), dtype=np.float64)
    for begin, end in pairwise(episode_offsets):
        for phase in range(3):
            rows = np.flatnonzero(phases[begin:end] == phase) + begin
            if len(rows):
                phase_weights[rows] = 1 / len(rows)

    def measure(probabilities, priors, rows, weights):
        if not len(rows):
            return {"rows": 0}
        p = probabilities[rows].numpy()
        y = outcomes[rows].numpy()
        result = weighted_outcome_metrics(p, y, weights)
        normalized = weights / weights.sum()
        prior_nll = float(normalized @ -np.log(priors[rows].numpy()[np.arange(len(rows)), y + 1]))
        return {"rows": len(rows), **result, "fit_prior_nll": prior_nll,
                "nll_improvement_over_fit_prior": prior_nll - result["nll"]}

    results = []
    margin_targets = torch.from_numpy(np.concatenate([
        c.arrays["terminal_tower_margins"] for _, c in loaded
    ])).float() if transfer else None
    for seed in plan["seeds"]:
        pooled = torch.full((len(outcomes), 3), torch.nan)
        pooled_prior = torch.full_like(pooled, torch.nan)
        folds = []
        transfer_pooled = {name: torch.full((len(outcomes),), torch.nan)
                           for name in ("trained", "random")} if transfer else {}
        for index, families in enumerate(plan["held_out_training_families"]):
            fit_rows, fit_episodes, withheld = family_fit_rows(episode_families, episode_offsets, families)
            weights, prior = fit_outcome_weights(base_weights, outcomes, episode_outcomes,
                                                fit_rows, fit_episodes, plan["target_class_mass"])
            torch.manual_seed(seed + index)
            rng = np.random.default_rng(seed + index)
            head = ActorOutcomeHead(features.shape[1], hidden_size=plan["hidden_size"],
                                    separate_draw_trunk=plan["actor_feature_set"] != "public-globals")
            initial_encoder = deepcopy(head.trunk) if transfer else None
            optimizer = torch.optim.AdamW(head.parameters(), lr=plan["learning_rate"],
                                          weight_decay=plan["weight_decay"])
            for _ in range(plan["epochs"]):
                order = rng.permutation(fit_rows)
                for begin in range(0, len(order), plan["batch_size"]):
                    rows = order[begin:begin + plan["batch_size"]]
                    logits = head(features[rows], calibrated=False).outcome_logits
                    loss = (F.nll_loss(logits, outcomes[rows] + 1, reduction="none") * weights[rows]).mean()
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0, error_if_nonfinite=True)
                    optimizer.step()
            head.eval()
            head.set_prior_calibration(prior, torch.tensor(plan["target_class_mass"]))
            with torch.no_grad():
                probabilities = torch.cat([head(batch).outcome_logits.softmax(-1)
                                           for batch in features.split(2048)])
            pooled[withheld] = probabilities[withheld]
            pooled_prior[withheld] = prior
            rows = representatives[withheld[representatives]]
            fit_reps = representatives[~withheld[representatives]]
            fold = {
                "families": families, "fitting_games": len(fit_episodes),
                "fit_prior": prior.tolist(),
                "out_of_fold_representatives": measure(probabilities, prior.expand(len(outcomes), -1), rows, np.ones(len(rows))),
                "fitting_representatives": measure(probabilities, prior.expand(len(outcomes), -1), fit_reps, np.ones(len(fit_reps))),
            }
            if transfer:
                frozen_sha = outcome_state_sha256(head.state_dict())
                fold["margin_transfer"] = {}
                for name, encoder in (("trained", head.trunk), ("random", initial_encoder)):
                    predicted = fit_transferred_margin(
                        encoder, features, margin_targets, base_weights, phases, fit_rows,
                        transfer, seed + index + 100_000,
                    )
                    transfer_pooled[name][withheld] = predicted[withheld]
                    fold["margin_transfer"][name] = margin_transfer_summary(
                        predicted, margin_targets, features, episode_offsets, phases,
                        np.flatnonzero(withheld[episode_offsets[:-1]]), rows,
                    )
                if outcome_state_sha256(head.state_dict()) != frozen_sha:
                    raise ValueError("margin transfer changed the frozen outcome encoder")
                fold["frozen_outcome_state_sha256"] = frozen_sha
            folds.append(fold)
            print(json.dumps({"seed": seed, "fold": index,
                              "out_of_fold": fold["out_of_fold_representatives"],
                              "elapsed_seconds": round(time.monotonic() - started, 2)}), flush=True)
        results.append({
            "seed": seed, "folds": folds,
            "representative_overall": measure(pooled, pooled_prior, representatives, np.ones(len(representatives))),
            "representative_by_phase": {
                name: measure(pooled, pooled_prior, representatives[phases[representatives] == i],
                              np.ones(sum(phases[representatives] == i)))
                for i, name in enumerate(("early", "middle", "late"))
            },
            "full_phase": {
                name: measure(pooled, pooled_prior, natural_rows[phases[natural_rows] == i],
                              phase_weights[natural_rows[phases[natural_rows] == i]])
                for i, name in enumerate(("early", "middle", "late"))
            },
            "margin_transfer": {
                name: margin_transfer_summary(
                    predicted, margin_targets, features, episode_offsets, phases,
                    np.flatnonzero(episode_families != "<auxiliary>"), representatives,
                ) for name, predicted in transfer_pooled.items()
            },
        })
    _atomic_json(output, {
        "status": "training-only-diagnostic; no model promotion",
        "plan": plan, "plan_sha256": file_sha256(plan_path),
        "source_corpora": source_records, "feature_size": features.shape[1],
        "calibration": "fitting-episode prior correction only; no heldout shrinkage or epoch selection",
        "results": results, "elapsed_seconds": time.monotonic() - started,
    })
