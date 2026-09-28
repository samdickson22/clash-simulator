"""Gate the frozen flat-median controller on a fresh counterfactual quarantine."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.action_value import (
    LoadedPublicActionValueEnsemble,
    load_public_action_value_controller,
)
from clasher.rl.eval import load_policy_checkpoint
from scripts.audit_structured_ranker_phase_card import summarize_phase_card_gate
from scripts.fit_public_action_value import build_preferences
from scripts.fit_structured_public_action_value import (
    _game_cluster_bootstrap_metrics,
    _load,
    _pair_metrics,
    _state_metrics,
    _threshold_metrics,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@torch.no_grad()
def _member_scores(
    ensemble: LoadedPublicActionValueEnsemble,
    payload: dict[str, np.ndarray],
    *,
    batch_size: int,
) -> np.ndarray:
    if ensemble.aggregation != "median":
        raise ValueError("fresh quarantine requires the frozen median ensemble")
    valid = np.asarray(payload["candidate_valid"], dtype=np.bool_)
    members = []
    for member in ensemble.members:
        device = next(member.head.parameters()).device
        batches = []
        for start in range(0, len(valid), batch_size):
            rows = slice(start, start + batch_size)
            batches.append(
                member.head(
                    torch.as_tensor(payload["features"][rows], device=device).float(),
                    torch.as_tensor(
                        payload["candidate_card_features"][rows], device=device
                    ).float(),
                    torch.as_tensor(
                        payload["candidate_tile_features"][rows], device=device
                    ).float(),
                    torch.as_tensor(
                        payload["candidate_kinds"][rows], device=device
                    ).long(),
                    torch.as_tensor(
                        payload["candidate_policy_log_probabilities"][rows],
                        device=device,
                    ).float(),
                    torch.as_tensor(
                        payload["candidate_policy_type_log_probabilities"][rows],
                        device=device,
                    ).float(),
                ).cpu().numpy()
            )
        members.append(np.concatenate(batches, axis=0))
    raw = np.stack(members).astype(np.float32, copy=False)
    gains = raw - raw[:, :, :1]
    gains /= np.asarray(ensemble.member_gain_scales, dtype=np.float32)[:, None, None]
    aggregate = np.median(gains, axis=0)
    aggregate[~valid] = -np.inf
    aggregate[:, 0] = 0.0
    return np.asarray(aggregate, dtype=np.float32)


def evaluate(
    *,
    controller_path: Path,
    corpus_path: Path,
    policy_path: Path,
    decks_path: Path,
    contract_path: Path,
    batch_size: int,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema") != "clasher.hog26_flat_median_fresh_gate.v1":
        raise ValueError("unexpected fresh flat-median gate contract")
    for entry in contract["sources"].values():
        path = Path(entry["path"])
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"fresh flat-median authority changed: {path}")
    payload = _load(corpus_path)
    states = np.arange(len(payload["features"]), dtype=np.int64)
    games = {int(value) for value in np.unique(payload["game_ids"]).tolist()}
    if games != set(range(int(contract["games"]))):
        raise ValueError("fresh counterfactual quarantine game IDs changed")
    controller = load_public_action_value_controller(
        controller_path,
        device=torch.device("cpu"),
    )
    if not isinstance(controller, LoadedPublicActionValueEnsemble):
        raise TypeError("fresh quarantine controller is not an ensemble")
    scores = _member_scores(controller, payload, batch_size=batch_size)
    preferences = build_preferences(payload)
    pair_metrics = _pair_metrics(scores, preferences, states)
    state_metrics = _state_metrics(scores, payload, states)
    threshold_metrics = _threshold_metrics(
        scores=scores,
        payload=payload,
        state_indices=states,
        threshold=controller.minimum_lower_bound_gain,
    )
    bootstrap = _game_cluster_bootstrap_metrics(
        scores=scores,
        payload=payload,
        preferences=preferences,
        state_indices=states,
        seed=int(contract["bootstrap_seed"]),
        samples=int(contract["bootstrap_samples"]),
    )
    policy = load_policy_checkpoint(
        policy_path,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    required_card = str(contract["required_card"])
    phase_card = summarize_phase_card_gate(
        payload,
        scores,
        holdout_games=games,
        required_card_token=policy.builder.token_id(required_card),
        minimum_phase_roots=int(contract["thresholds"]["minimum_phase_roots"]),
        minimum_phase_optimal_rate=float(
            contract["thresholds"]["minimum_phase_optimal_rate"]
        ),
        minimum_phase_improvement_recall=float(
            contract["thresholds"]["minimum_phase_improvement_recall"]
        ),
        minimum_required_card_roots=int(
            contract["thresholds"]["minimum_required_card_roots"]
        ),
        minimum_required_card_recall=float(
            contract["thresholds"]["minimum_required_card_recall"]
        ),
        minimum_score_gain=controller.minimum_lower_bound_gain,
    )
    improvements = sum(int(value) for value in threshold_metrics["improvements"].values())
    regressions = sum(int(value) for value in threshold_metrics["regressions"].values())
    thresholds = contract["thresholds"]
    gates = {
        "overall_accuracy": float(pair_metrics["accuracy"])
        >= float(thresholds["minimum_accuracy"]),
        "outcome_accuracy": float(pair_metrics["outcome_accuracy"])
        >= float(thresholds["minimum_outcome_accuracy"]),
        "optimal_action_rate": float(state_metrics["optimal_action_rate"])
        >= float(thresholds["minimum_optimal_action_rate"]),
        "minimum_overrides": int(threshold_metrics["overrides"])
        >= int(thresholds["minimum_overrides"]),
        "minimum_improvements": improvements
        >= int(thresholds["minimum_improvements"]),
        "maximum_regressions": regressions
        <= int(thresholds["maximum_regressions"]),
        "accuracy_cluster_lower": float(bootstrap["accuracy_ci95"][0])
        >= float(thresholds["minimum_accuracy_ci95_lower"]),
        "outcome_cluster_lower": float(bootstrap["outcome_accuracy_ci95"][0])
        >= float(thresholds["minimum_outcome_accuracy_ci95_lower"]),
        "optimal_cluster_lower": float(bootstrap["optimal_action_rate_ci95"][0])
        >= float(thresholds["minimum_optimal_action_rate_ci95_lower"]),
        "phase_and_hog": phase_card["passed"] is True,
    }
    return {
        "schema": "clasher.hog26_flat_median_fresh_quarantine_gate.v1",
        "passed": all(gates.values()),
        "promotion_authorized": False,
        "gates": gates,
        "pair_metrics": pair_metrics,
        "state_metrics": state_metrics,
        "threshold_metrics": threshold_metrics,
        "cluster_bootstrap": bootstrap,
        "phase_card": phase_card,
        "controller_sha256": _sha256(controller_path),
        "corpus_sha256": _sha256(corpus_path),
        "contract_sha256": _sha256(contract_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        controller_path=args.controller,
        corpus_path=args.corpus,
        policy_path=args.policy,
        decks_path=args.decks_path,
        contract_path=args.contract,
        batch_size=args.batch_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("fresh flat-median counterfactual quarantine failed")


if __name__ == "__main__":
    main()
