#!/usr/bin/env python3
"""Fit a predeclared margin diagnostic on training-only, whole-family folds."""

from __future__ import annotations

import argparse
import json
import time
from itertools import pairwise
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from torch.nn.utils.rnn import pad_sequence

from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from clasher.rl.outcome_model import ActorOutcomeHead
from clasher.rl.temporal_margin import ActorTemporalMarginHead
from scripts.collect_hog26_direct_simple_behavior import _atomic_json, file_sha256
from scripts.pretrain_hog26_direct_simple_behavior import load_model
from scripts.run_hog26_procedural_outcome_shard import load_protocol
from scripts.train_hog26_actor_outcome import (
    episode_balanced_row_weights,
    extract_actor_features,
    phase_balanced_row_indices,
    validate_outcome_corpus,
)
from scripts.train_hog26_procedural_outcome_candidate import require_current_audit


def source_audit_path(spec, protocol):
    if spec["role"] == "procedural":
        matches = [
            r for r in protocol["training"] if r["output_corpus"] == spec["path"]
        ]
        if len(matches) == 1:
            return matches[0]["audit_report"]
    elif spec["role"] == "auxiliary":
        data = protocol["primary_candidate_data"]
        if spec["path"] in data["legacy_training_corpora"]:
            return data["legacy_audit_reports"][spec["path"]]
    raise ValueError("screen source must have its declared training-only role")


def family_fit_rows(episode_families, episode_offsets, withheld):
    excluded = np.isin(episode_families, withheld)
    row_excluded = np.repeat(excluded, np.diff(episode_offsets))
    return np.flatnonzero(~row_excluded), np.flatnonzero(~excluded), row_excluded


def full_phase_margin_summary(prediction, target, current, offsets, phases, episodes):
    """Average state errors within each game/phase, then weight games equally."""
    records = {name: [] for name in ("early", "middle", "late")}
    for episode in episodes:
        begin, end = offsets[episode:episode + 2]
        for phase, name in enumerate(records):
            rows = np.flatnonzero(phases[begin:end] == phase) + begin
            if len(rows):
                mae = float((prediction[rows] - target[rows]).abs().mean())
                baseline = float((current[rows] - target[rows]).abs().mean())
                records[name].append((len(rows), mae, baseline))
    return {
        name: {
            "games": len(rows), "rows": sum(r[0] for r in rows),
            "mae": float(np.mean([r[1] for r in rows])) if rows else None,
            "baseline_mae": float(np.mean([r[2] for r in rows])) if rows else None,
            "mae_improvement": float(np.mean([r[2] - r[1] for r in rows])) if rows else None,
        } for name, rows in records.items()
    }


def margin_row_loss(prediction, target, kind):
    if kind == "absolute":
        return F.l1_loss(prediction, target, reduction="none")
    if kind == "huber":
        return F.smooth_l1_loss(prediction, target, reduction="none")
    raise ValueError("unknown diagnostic margin loss")


def fitting_phase_weights(weights, phases, fit_rows, *, aggregate_balance):
    """Normalize fitting rows only; withheld rows have zero training mass."""
    result = torch.zeros_like(weights)
    selected = weights[fit_rows].clone()
    selected_phases = np.asarray(phases)[fit_rows]
    if aggregate_balance:
        for phase in range(3):
            mask = selected_phases == phase
            if not mask.any() or selected[mask].sum() <= 0:
                raise ValueError("fitting fold lacks a positive-weight game phase")
            selected[mask] /= selected[mask].sum()
    selected /= selected.mean()
    result[fit_rows] = selected
    return result


def fit_temporal_fold(
    features, target, weights, episode_offsets, selected_episodes, plan, power, rng
):
    head = ActorTemporalMarginHead(
        features.shape[1],
        projection_size=plan["projection_size"],
        memory_size=plan["memory_size"],
        residual_scale=plan["margin_residual_scale"],
        progress_power=power,
    )
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=plan["learning_rate"], weight_decay=plan["weight_decay"]
    )
    episodes = [slice(int(a), int(b)) for a, b in pairwise(episode_offsets)]
    for _epoch in range(plan["epochs"]):
        order = rng.permutation(selected_episodes)
        for begin in range(0, len(order), plan["episode_batch_size"]):
            slices = [
                episodes[e] for e in order[begin : begin + plan["episode_batch_size"]]
            ]
            inputs = pad_sequence([features[s] for s in slices], batch_first=True)
            labels = pad_sequence([target[s] for s in slices], batch_first=True)
            sample_weights = pad_sequence(
                [weights[s] for s in slices], batch_first=True
            )
            prediction, _memory = head(inputs)  # exact zero reset for every full game
            loss = (
                margin_row_loss(prediction, labels, plan.get("margin_loss", "huber"))
                * sample_weights
            ).sum() / sample_weights.sum()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                head.parameters(), 1.0, error_if_nonfinite=True
            )
            optimizer.step()
    with torch.no_grad():
        return torch.cat([head(features[s].unsqueeze(0))[0][0] for s in episodes])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    root = Path(__file__).resolve().parents[1]
    output = root / plan["output"]
    if output.exists():
        raise SystemExit("refusing to overwrite margin screen")
    protocol = load_protocol(root / plan["protocol"], root)
    specs = plan.get("corpora")
    if specs is None:
        specs = [
            {
                "path": plan["corpus"],
                "sha256": plan["corpus_sha256"],
                "role": "procedural",
            }
        ]
    loaded = []
    source_records = []
    seeds = set()
    hashes = set()
    episode_families_parts = []
    episode_seats_parts = []
    episode_styles_parts = []
    lengths_parts = []
    manifest = json.loads((root / protocol["procedural_decks"]["path"]).read_text())
    family_by_deck = {d["name"]: d.get("family_id") for d in manifest["decks"]}
    row_cursor = episode_cursor = 0
    for spec in specs:
        source = root / spec["path"]
        if file_sha256(source) != spec["sha256"] or spec["sha256"] in hashes:
            raise ValueError("screen source bytes drifted or were duplicated")
        require_current_audit(source, root / source_audit_path(spec, protocol))
        metadata, corpus = load_direct_simple_behavior_corpus(source)
        validate_outcome_corpus(metadata, corpus)
        if (
            metadata["checkpoint_sha256"] != protocol["base_policy"]["sha256"]
            or metadata["seed"] in seeds
        ):
            raise ValueError("screen policy drifted or collection seed duplicated")
        seeds.add(metadata["seed"])
        hashes.add(spec["sha256"])
        styles = np.asarray(metadata["opponents"])[
            corpus.episode_arrays["episode_opponent_indices"]
        ]
        if set(styles) & set(
            protocol.get("opponent_generalization", {}).get("head_held_out_styles", [])
        ):
            raise ValueError("held-out opponent appears in screen fitting data")
        if spec["role"] == "procedural":
            decks = np.asarray(metadata["opponent_decks"])[
                corpus.episode_arrays["episode_opponent_deck_indices"]
            ]
            families = np.asarray([family_by_deck[d] for d in decks])
        else:
            families = np.full(corpus.episode_count, "<auxiliary>")
        episode_families_parts.append(families)
        episode_seats_parts.append(corpus.episode_arrays["episode_learner_players"])
        episode_styles_parts.append(styles)
        lengths_parts.append(np.diff(corpus.episode_offsets))
        source_records.append(
            {
                **spec,
                "seed": metadata["seed"],
                "episodes": corpus.episode_count,
                "rows": corpus.row_count,
                "row_start": row_cursor,
                "episode_start": episode_cursor,
            }
        )
        row_cursor += corpus.row_count
        episode_cursor += corpus.episode_count
        loaded.append((metadata, corpus))
    episode_families = np.concatenate(episode_families_parts)
    lengths = np.concatenate(lengths_parts)
    episode_offsets = np.concatenate(([0], np.cumsum(lengths)))
    folds = plan["held_out_training_families"]
    flat_families = [family for fold in folds for family in fold]
    actual_families = set(episode_families) - {"<auxiliary>"}
    if (
        len(set(flat_families)) != len(flat_families)
        or set(flat_families) != actual_families
    ):
        raise ValueError(
            "folds must partition the generated training families exactly once"
        )
    torch.set_num_threads(plan["torch_threads"])
    device = torch.device("cpu")
    _, model = load_model(root / protocol["base_policy"]["path"], device)
    started = time.monotonic()
    features = torch.cat(
        [
            extract_actor_features(
                model,
                c,
                device=device,
                sequence_steps=128,
                feature_set=plan.get("actor_feature_set", "structured-summary"),
            )
            for _, c in loaded
        ]
    )
    if plan.get("zero_spatial_mechanics", False):
        if plan.get("actor_feature_set") != "spatial-mechanics":
            raise ValueError(
                "spatial ablation requires the spatial-mechanics representation"
            )
        descriptor_width = (
            model.actor_encoder.card_stat_features.shape[-1]
            + model.actor_encoder.semantic_card_features.shape[-1]
        )
        moment_width = 2 * (
            3 * (loaded[0][1].arrays["entity_features"].shape[-1] + descriptor_width)
            + 1
        )
        features[:, -18 - moment_width : -18] = 0.0
    del model
    target = torch.cat(
        [
            torch.from_numpy(c.arrays["terminal_tower_margins"].copy()).float()
            for _, c in loaded
        ]
    )
    public = features[:, -18:]
    current = (public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3
    weights = episode_balanced_row_weights(loaded, phase_balanced=True)
    row_families = np.repeat(episode_families, lengths)
    all_representatives = phase_balanced_row_indices(loaded).numpy()
    representatives = all_representatives[
        row_families[all_representatives] != "<auxiliary>"
    ]
    progress = public[:, 0].numpy()
    phases = np.minimum((progress * 3).astype(int), 2)
    row_seats = np.repeat(np.concatenate(episode_seats_parts), lengths)
    row_styles = np.repeat(np.concatenate(episode_styles_parts), lengths)
    evaluated_styles = sorted(set(row_styles[representatives]))

    def summarize(prediction, rows):
        if not len(rows):
            return {"rows": 0, "mae_improvement": None}
        pred = prediction[rows]
        truth = target[rows]
        baseline = current[rows]
        mae = (pred - truth).abs().mean().item()
        base_mae = (baseline - truth).abs().mean().item()
        return {
            "rows": len(rows),
            "mae": mae,
            "baseline_mae": base_mae,
            "mae_improvement": base_mae - mae,
            "mean_abs_correction": (pred - baseline).abs().mean().item(),
        }

    def breakdown(prediction, rows):
        return {
            "overall": summarize(prediction, rows),
            "by_phase": {
                name: summarize(prediction, rows[phases[rows] == i])
                for i, name in enumerate(("early", "middle", "late"))
            },
            "by_seat": {
                str(seat): summarize(prediction, rows[row_seats[rows] == seat])
                for seat in (0, 1)
            },
            "by_style": {
                str(style): summarize(prediction, rows[row_styles[rows] == style])
                for style in evaluated_styles
            },
        }

    results = []
    for feature_set in plan["margin_feature_sets"]:
        for power in plan["margin_progress_powers"]:
            for seed in plan["seeds"]:
                pooled = torch.full_like(target, torch.nan)
                fold_results = []
                for fold_index, families in enumerate(folds):
                    fit_rows, fitting_episodes, validation_mask = family_fit_rows(
                        episode_families, episode_offsets, families
                    )
                    test_rows = representatives[validation_mask[representatives]]
                    train_representatives = representatives[
                        ~validation_mask[representatives]
                    ]
                    torch.manual_seed(seed + fold_index)
                    rng = np.random.default_rng(seed + fold_index)
                    fit_weights = fitting_phase_weights(
                        weights,
                        phases,
                        fit_rows,
                        aggregate_balance=plan.get("aggregate_phase_balance", False),
                    )
                    if plan.get("model_type") == "temporal":
                        if feature_set != "full-state":
                            raise ValueError(
                                "temporal screen requires full public summaries"
                            )
                        prediction = fit_temporal_fold(
                            features,
                            target,
                            fit_weights,
                            episode_offsets,
                            fitting_episodes,
                            plan,
                            power,
                            rng,
                        )
                    else:
                        head = ActorOutcomeHead(
                            features.shape[1],
                            plan["hidden_size"],
                            margin_residual_scale=plan["margin_residual_scale"],
                            margin_feature_set=feature_set,
                            margin_progress_power=power,
                        )
                        for name, parameter in head.named_parameters():
                            parameter.requires_grad_(name.startswith("margin_trunk."))
                        parameters = [p for p in head.parameters() if p.requires_grad]
                        optimizer = torch.optim.AdamW(
                            parameters,
                            lr=plan["learning_rate"],
                            weight_decay=plan["weight_decay"],
                        )
                        for _epoch in range(plan["epochs"]):
                            order = rng.permutation(fit_rows)
                            for begin in range(0, len(order), plan["batch_size"]):
                                rows = order[begin : begin + plan["batch_size"]]
                                prediction = head(
                                    features[rows], calibrated=False
                                ).terminal_tower_margin
                                loss = (
                                    margin_row_loss(
                                        prediction,
                                        target[rows],
                                        plan.get("margin_loss", "huber"),
                                    )
                                    * fit_weights[rows]
                                ).mean()
                                optimizer.zero_grad(set_to_none=True)
                                loss.backward()
                                torch.nn.utils.clip_grad_norm_(
                                    parameters, 1.0, error_if_nonfinite=True
                                )
                                optimizer.step()
                        with torch.no_grad():
                            prediction = torch.cat(
                                [
                                    head(x).terminal_tower_margin
                                    for x in features.split(2048)
                                ]
                            )
                    pooled[validation_mask] = prediction[validation_mask]
                    fold_results.append(
                        {
                            "held_out_families": families,
                            "training_phase_weight_fraction": {
                                name: float(
                                    fit_weights[phases == i].sum() / fit_weights.sum()
                                )
                                for i, name in enumerate(("early", "middle", "late"))
                            },
                            "fit": breakdown(prediction, train_representatives),
                            "out_of_fold": breakdown(prediction, test_rows),
                            "full_phase_out_of_fold": full_phase_margin_summary(
                                prediction, target, current, episode_offsets, phases,
                                np.flatnonzero(validation_mask[episode_offsets[:-1]]),
                            ),
                        }
                    )
                    print(
                        json.dumps(
                            {
                                "feature_set": feature_set,
                                "power": power,
                                "seed": seed,
                                "fold": fold_index,
                                "out_of_fold": fold_results[-1]["out_of_fold"][
                                    "overall"
                                ],
                                "elapsed_seconds": round(time.monotonic() - started, 2),
                            }
                        ),
                        flush=True,
                    )
                if not torch.isfinite(pooled[representatives]).all():
                    raise ValueError(
                        "out-of-fold predictions do not cover all representatives"
                    )
                result = {
                    "feature_set": feature_set,
                    "power": power,
                    "seed": seed,
                    "folds": fold_results,
                    "pooled": breakdown(pooled, representatives),
                    "full_phase_out_of_fold": full_phase_margin_summary(
                        pooled, target, current, episode_offsets, phases,
                        np.flatnonzero(episode_families != "<auxiliary>"),
                    ),
                    "predictions": pooled[representatives].tolist(),
                }
                result["screen_point_gates_passed"] = result["pooled"]["overall"][
                    "mae_improvement"
                ] >= 0.005 and all(
                    row["mae_improvement"] is not None
                    and row["mae_improvement"] >= -0.01
                    for row in result["pooled"]["by_phase"].values()
                )
                results.append(result)
    _atomic_json(
        output,
        {
            "status": "diagnostic-only",
            "plan": plan,
            "plan_sha256": file_sha256(args.plan),
            "source_sha256": specs[0]["sha256"] if len(specs) == 1 else None,
            "source_corpora": source_records,
            "evaluation_scope": "generated-family out-of-fold rows only; auxiliaries fit only",
            "feature_size": features.shape[1],
            "representative_rows": representatives.tolist(),
            "source_episode_families": episode_families.tolist(),
            "elapsed_seconds": time.monotonic() - started,
            "results": results,
        },
    )


if __name__ == "__main__":
    main()
