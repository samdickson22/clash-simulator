"""Calibrate a conservative ensemble on untouched terminal counterfactual roots."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.action_value import (
    LoadedPublicActionValueHead,
    load_public_action_value_head,
)
from scripts.fit_public_action_value import _candidate_order


def _wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = proportion + z * z / (2.0 * total)
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    )
    return (center - radius) / denominator


@torch.no_grad()
def _member_state_scores(
    member: LoadedPublicActionValueHead,
    payload: dict[str, np.ndarray],
    *,
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    head = member.head
    rows: list[np.ndarray] = []
    state_count = int(payload["features"].shape[0])
    for start in range(0, state_count, batch_size):
        stop = min(state_count, start + batch_size)
        indices = slice(start, stop)
        scores = head(
            torch.as_tensor(payload["features"][indices], device=device).float(),
            torch.as_tensor(
                payload["candidate_card_features"][indices], device=device
            ).float(),
            torch.as_tensor(
                payload["candidate_tile_features"][indices], device=device
            ).float(),
            torch.as_tensor(
                payload["candidate_kinds"][indices], device=device
            ).long(),
            torch.as_tensor(
                payload["candidate_policy_log_probabilities"][indices],
                device=device,
            ).float(),
            torch.as_tensor(
                payload["candidate_policy_type_log_probabilities"][indices],
                device=device,
            ).float(),
        )
        valid = torch.as_tensor(payload["candidate_valid"][indices], device=device)
        rows.append(scores.masked_fill(~valid, -torch.inf).cpu().numpy())
    return np.concatenate(rows, axis=0)


def _true_orders(
    payload: dict[str, np.ndarray],
    state: int,
) -> list[tuple[float, int, float] | None]:
    result: list[tuple[float, int, float] | None] = []
    for candidate, valid in enumerate(payload["candidate_valid"][state]):
        result.append(
            _candidate_order(
                float(payload["candidate_scores"][state, candidate]),
                int(payload["candidate_crown_differences"][state, candidate]),
                float(
                    payload["candidate_tower_damage_differences"][state, candidate]
                ),
            )
            if bool(valid)
            else None
        )
    return result


def _pairwise_metrics(
    mean_scores: np.ndarray,
    payload: dict[str, np.ndarray],
) -> dict[str, float | int]:
    correct = pairs = 0
    priority_pairs = {"outcome": 0, "crown": 0, "damage": 0}
    priority_correct = {"outcome": 0, "crown": 0, "damage": 0}
    for state in range(mean_scores.shape[0]):
        orders = _true_orders(payload, state)
        valid = np.flatnonzero(payload["candidate_valid"][state])
        for offset, left in enumerate(valid):
            for right in valid[offset + 1 :]:
                if orders[left] == orders[right]:
                    continue
                predicted = float(mean_scores[state, left] - mean_scores[state, right])
                actual = 1.0 if orders[left] > orders[right] else -1.0
                is_correct = predicted * actual > 0.0
                correct += is_correct
                pairs += 1
                left_order = orders[left]
                right_order = orders[right]
                assert left_order is not None and right_order is not None
                if left_order[0] != right_order[0]:
                    priority = "outcome"
                elif left_order[1] != right_order[1]:
                    priority = "crown"
                else:
                    priority = "damage"
                priority_pairs[priority] += 1
                priority_correct[priority] += is_correct
    result: dict[str, float | int] = {
        "pairwise_pairs": pairs,
        "pairwise_accuracy": correct / max(1, pairs),
    }
    for priority in ("outcome", "crown", "damage"):
        count = priority_pairs[priority]
        result[f"{priority}_pairwise_pairs"] = count
        result[f"{priority}_pairwise_accuracy"] = (
            priority_correct[priority] / count if count else 0.0
        )
    return result


def evaluate_selection(
    *,
    member_scores: np.ndarray,
    payload: dict[str, np.ndarray],
    archetypes: np.ndarray,
    dispersion_scale: float,
    minimum_lower_bound_gain: float,
) -> dict[str, Any]:
    if member_scores.ndim != 3 or member_scores.shape[0] < 3:
        raise ValueError("member scores must have shape [members, states, candidates]")
    if archetypes.shape != (member_scores.shape[1],):
        raise ValueError("archetypes must identify every validation state")
    valid = payload["candidate_valid"]
    paired_gains = np.where(
        valid[None, :, :],
        member_scores - member_scores[:, :, :1],
        0.0,
    )
    gain_mean = paired_gains.mean(axis=0)
    gain_dispersion = paired_gains.std(axis=0, ddof=1)
    lower = gain_mean - dispersion_scale * gain_dispersion
    lower[~valid] = -np.inf
    lower[:, 0] = 0.0
    best = lower.argmax(axis=1)
    best_gain = lower[np.arange(len(best)), best]
    selected = np.where(best_gain > minimum_lower_bound_gain, best, 0)
    mean_scores = member_scores.mean(axis=0)
    pairwise = _pairwise_metrics(mean_scores, payload)

    overrides = improvements = regressions = optimal = 0
    base_regret = selected_regret = 0.0
    archetype_deltas: dict[str, list[float]] = defaultdict(list)
    priority_counts = {
        "outcome_improvements": 0,
        "outcome_regressions": 0,
        "crown_improvements": 0,
        "crown_regressions": 0,
        "damage_improvements": 0,
        "damage_regressions": 0,
    }
    for state, candidate in enumerate(selected.tolist()):
        orders = _true_orders(payload, state)
        valid_orders = sorted({order for order in orders if order is not None})
        ranks = {order: rank for rank, order in enumerate(valid_orders)}
        base_order = orders[0]
        selected_order = orders[candidate]
        assert base_order is not None and selected_order is not None
        best_order = valid_orders[-1]
        base_rank = ranks[base_order]
        selected_rank = ranks[selected_order]
        best_rank = ranks[best_order]
        base_regret += best_rank - base_rank
        selected_regret += best_rank - selected_rank
        optimal += selected_order == best_order
        archetype_deltas[str(archetypes[state])].append(selected_rank - base_rank)
        if candidate == 0:
            continue
        overrides += 1
        if selected_order > base_order:
            improvements += 1
            suffix = "improvements"
        elif selected_order < base_order:
            regressions += 1
            suffix = "regressions"
        else:
            continue
        if selected_order[0] != base_order[0]:
            prefix = "outcome"
        elif selected_order[1] != base_order[1]:
            prefix = "crown"
        else:
            prefix = "damage"
        priority_counts[f"{prefix}_{suffix}"] += 1
    regret_reduction = (
        (base_regret - selected_regret) / base_regret if base_regret > 0.0 else 0.0
    )
    archetype_mean_delta = {
        name: float(np.mean(values)) for name, values in sorted(archetype_deltas.items())
    }
    return {
        "dispersion_scale": dispersion_scale,
        "minimum_lower_bound_gain": minimum_lower_bound_gain,
        "states": len(selected),
        **pairwise,
        "overrides": overrides,
        "improvements": improvements,
        "regressions": regressions,
        "positive_override_precision": improvements / max(1, overrides),
        "positive_override_precision_wilson_lower": _wilson_lower(
            improvements, overrides
        ),
        "optimal_action_rate": optimal / max(1, len(selected)),
        "base_ordinal_regret": base_regret,
        "selected_ordinal_regret": selected_regret,
        "ordinal_regret_reduction": regret_reduction,
        "archetype_mean_rank_delta": archetype_mean_delta,
        "minimum_archetype_mean_rank_delta": min(archetype_mean_delta.values()),
        "selected_indices": selected,
        **priority_counts,
    }


def _thresholds(lower_best_gains: np.ndarray) -> list[float]:
    positive = lower_best_gains[np.isfinite(lower_best_gains) & (lower_best_gains > 0)]
    if not len(positive):
        return [0.0]
    quantiles = np.linspace(0.0, 1.0, 101)
    values = np.quantile(positive, quantiles)
    return sorted({0.0, *(float(value) for value in values)})


def _state_archetypes(
    corpus_report: dict[str, Any],
    opponent_decks_path: Path,
    game_ids: np.ndarray,
) -> np.ndarray:
    deck_payload = json.loads(opponent_decks_path.read_text(encoding="utf-8"))
    by_signature = {
        tuple(sorted(row["cards"])): str(row["archetype"])
        for row in deck_payload["decks"]
    }
    game_archetypes: dict[int, str] = {}
    for row in corpus_report["games"]:
        opponent = 1 - int(row["controlled_player"])
        signature = tuple(sorted(row["decks"][opponent]))
        if signature not in by_signature:
            raise ValueError("counterfactual opponent deck lacks archetype authority")
        game_archetypes[int(row["game"])] = by_signature[signature]
    return np.asarray([game_archetypes[int(game)] for game in game_ids])


def select_controller(
    single_members: list[dict[str, Any]],
    ensemble: dict[str, Any] | None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    if ensemble is not None:
        candidates.append({"kind": "ensemble", "metrics": ensemble})
    for index, row in enumerate(single_members):
        if row.get("passes") is True:
            candidates.append(
                {"kind": "single", "member_index": index, "metrics": row}
            )
    return (
        max(
            candidates,
            key=lambda item: (
                item["metrics"]["ordinal_regret_reduction"],
                item["metrics"]["outcome_pairwise_accuracy"],
                item["metrics"]["pairwise_accuracy"],
                item["metrics"]["positive_override_precision_wilson_lower"],
                item["kind"] == "ensemble",
            ),
        )
        if candidates
        else None
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", type=Path, action="append", required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--opponent-decks", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--selection-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--minimum-overrides", type=int, default=25)
    parser.add_argument("--minimum-pairwise-accuracy", type=float, default=0.65)
    parser.add_argument(
        "--minimum-outcome-pairwise-accuracy", type=float, default=0.65
    )
    parser.add_argument("--minimum-outcome-pairs", type=int, default=500)
    parser.add_argument("--minimum-regret-reduction", type=float, default=0.25)
    parser.add_argument("--minimum-precision-lower", type=float, default=0.75)
    args = parser.parse_args()
    if len(args.member) < 3:
        raise ValueError("at least three ensemble members are required")
    if args.batch_size < 1 or args.torch_threads < 1:
        raise ValueError("batch size and torch threads must be positive")
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    members = tuple(
        load_public_action_value_head(path, device=device) for path in args.member
    )
    if len({member.source_policy for member in members}) != 1:
        raise ValueError("ensemble member policy paths differ")
    if len({member.source_policy_sha256 for member in members}) != 1:
        raise ValueError("ensemble member policy hashes differ")
    if len({member.corpus_sha256 for member in members}) != 1:
        raise ValueError("ensemble member corpus hashes differ")
    if members[0].source_policy_sha256 is None:
        raise ValueError("ensemble members require portable source-policy hashes")
    with np.load(args.validation_corpus, allow_pickle=False) as source:
        payload = {name: np.asarray(source[name]) for name in source.files}
    corpus_report = json.loads(args.validation_report.read_text(encoding="utf-8"))
    archetypes = _state_archetypes(
        corpus_report,
        args.opponent_decks,
        payload["game_ids"],
    )
    raw_member_scores = np.stack(
        [
            _member_state_scores(
                member,
                payload,
                device=device,
                batch_size=args.batch_size,
            )
            for member in members
        ]
    )
    valid_nonbase = payload["candidate_valid"].copy()
    valid_nonbase[:, 0] = False
    member_gain_scales = []
    normalized_members = []
    for scores in raw_member_scores:
        gains = scores - scores[:, :1]
        finite_gains = np.abs(gains[valid_nonbase])
        scale = float(np.median(finite_gains)) if len(finite_gains) else 1.0
        scale = max(scale, 1e-6)
        member_gain_scales.append(scale)
        normalized_members.append(
            np.where(payload["candidate_valid"], gains / scale, -np.inf)
        )
    member_scores = np.stack(normalized_members)
    control_member_scores = np.zeros_like(member_scores)
    control_member_scores[:, :, 0] = 1.0
    control = evaluate_selection(
        member_scores=control_member_scores,
        payload=payload,
        archetypes=archetypes,
        dispersion_scale=0.0,
        minimum_lower_bound_gain=0.0,
    )
    control.update(_pairwise_metrics(payload["candidate_policy_logits"], payload))
    control.pop("selected_indices")
    member_metrics = []
    for path, member, scores in zip(
        args.member,
        members,
        raw_member_scores,
        strict=True,
    ):
        row = evaluate_selection(
            member_scores=np.repeat(scores[None, :, :], 3, axis=0),
            payload=payload,
            archetypes=archetypes,
            dispersion_scale=0.0,
            minimum_lower_bound_gain=member.minimum_score_gain,
        )
        row.pop("selected_indices")
        row["checkpoint"] = str(path.resolve())
        row["checkpoint_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        member_metrics.append(row)
    best_single_pairwise = max(
        float(row["pairwise_accuracy"]) for row in member_metrics
    )
    best_single_outcome_pairwise = max(
        float(row["outcome_pairwise_accuracy"]) for row in member_metrics
    )
    best_single_regret_reduction = max(
        float(row["ordinal_regret_reduction"]) for row in member_metrics
    )

    def passes_absolute(row: dict[str, Any]) -> bool:
        return bool(
            row["overrides"] >= args.minimum_overrides
            and row["pairwise_accuracy"] >= args.minimum_pairwise_accuracy
            and row["outcome_pairwise_accuracy"]
            >= args.minimum_outcome_pairwise_accuracy
            and row["outcome_pairwise_pairs"] >= args.minimum_outcome_pairs
            and row["ordinal_regret_reduction"]
            >= args.minimum_regret_reduction
            and row["positive_override_precision_wilson_lower"]
            >= args.minimum_precision_lower
            and row["minimum_archetype_mean_rank_delta"] >= 0.0
        )

    for row in member_metrics:
        row["passes"] = passes_absolute(row)
    sweep: list[dict[str, Any]] = []
    for dispersion_scale in (0.0, 0.5, 1.0, 1.5, 2.0):
        paired = np.where(
            payload["candidate_valid"][None, :, :],
            member_scores - member_scores[:, :, :1],
            0.0,
        )
        lower = paired.mean(axis=0) - dispersion_scale * paired.std(
            axis=0, ddof=1
        )
        lower[~payload["candidate_valid"]] = -np.inf
        lower[:, 0] = 0.0
        best = lower.argmax(axis=1)
        best_gains = lower[np.arange(len(best)), best]
        for threshold in _thresholds(best_gains):
            row = evaluate_selection(
                member_scores=member_scores,
                payload=payload,
                archetypes=archetypes,
                dispersion_scale=dispersion_scale,
                minimum_lower_bound_gain=threshold,
            )
            row["passes"] = passes_absolute(row)
            row.pop("selected_indices")
            sweep.append(row)
    passing = [row for row in sweep if row["passes"]]
    selected = (
        max(
            passing,
            key=lambda row: (
                row["ordinal_regret_reduction"],
                row["improvements"],
                row["positive_override_precision_wilson_lower"],
                -row["overrides"],
            ),
        )
        if passing
        else None
    )
    selected_controller = select_controller(member_metrics, selected)
    report = {
        "schema": "clasher.public_action_value_ensemble_calibration.v1",
        "passed": selected_controller is not None,
        "members": [str(path.resolve()) for path in args.member],
        "member_sha256": [
            hashlib.sha256(path.read_bytes()).hexdigest() for path in args.member
        ],
        "member_gain_scales": member_gain_scales,
        "source_policy": members[0].source_policy,
        "source_policy_sha256": members[0].source_policy_sha256,
        "training_corpus_sha256": members[0].corpus_sha256,
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_states": int(payload["features"].shape[0]),
        "thresholds": {
            "minimum_overrides": args.minimum_overrides,
            "minimum_pairwise_accuracy": args.minimum_pairwise_accuracy,
            "minimum_outcome_pairwise_accuracy": (
                args.minimum_outcome_pairwise_accuracy
            ),
            "minimum_outcome_pairs": args.minimum_outcome_pairs,
            "minimum_regret_reduction": args.minimum_regret_reduction,
            "minimum_precision_lower": args.minimum_precision_lower,
            "minimum_archetype_mean_rank_delta": 0.0,
            "best_single_pairwise_reference": best_single_pairwise,
            "best_single_outcome_pairwise_reference": (
                best_single_outcome_pairwise
            ),
            "best_single_regret_reduction_reference": (
                best_single_regret_reduction
            ),
        },
        "control": control,
        "single_members": member_metrics,
        "selected": selected,
        "selected_controller": selected_controller,
        "sweep": sweep,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if selected_controller is None:
        raise SystemExit("action-value controllers failed the offline gate")
    report_sha256 = hashlib.sha256(args.report_out.read_bytes()).hexdigest()
    artifact_path: Path
    if selected_controller["kind"] == "ensemble":
        assert selected is not None
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema": "clasher.public_action_value_ensemble.v1",
            "members": [
                os.path.relpath(path.resolve(), args.manifest_out.parent.resolve())
                for path in args.member
            ],
            "dispersion_scale": selected["dispersion_scale"],
            "minimum_lower_bound_gain": selected["minimum_lower_bound_gain"],
            "member_gain_scales": member_gain_scales,
            "calibration_report": os.path.relpath(
                args.report_out.resolve(), args.manifest_out.parent.resolve()
            ),
            "calibration_report_sha256": report_sha256,
        }
        args.manifest_out.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        artifact_path = args.manifest_out.resolve()
    else:
        artifact_path = args.member[int(selected_controller["member_index"])].resolve()
    args.selection_out.parent.mkdir(parents=True, exist_ok=True)
    selection = {
        "schema": "clasher.public_action_value_controller.v1",
        "kind": selected_controller["kind"],
        "artifact": os.path.relpath(
            artifact_path, args.selection_out.parent.resolve()
        ),
        "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "source_policy_sha256": members[0].source_policy_sha256,
        "calibration_report": os.path.relpath(
            args.report_out.resolve(), args.selection_out.parent.resolve()
        ),
        "calibration_report_sha256": report_sha256,
    }
    args.selection_out.write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(selected_controller, sort_keys=True))


if __name__ == "__main__":
    main()
