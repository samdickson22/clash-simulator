from __future__ import annotations

import numpy as np

from scripts.audit_structured_ranker_phase_card import summarize_phase_card_gate


def _payload(*, regress: bool = False) -> tuple[dict[str, np.ndarray], np.ndarray]:
    ticks = np.asarray([256, 1500, 2800, 4000] * 5, dtype=np.int64)
    rows = len(ticks)
    candidate_actions = np.tile(np.asarray([2304, 20, 40]), (rows, 1))
    best_actions = np.full(rows, 20, dtype=np.int64)
    payload = {
        "game_ids": np.arange(rows, dtype=np.int64),
        "ticks": ticks,
        "base_actions": np.full(rows, 2304, dtype=np.int64),
        "best_actions": best_actions,
        "candidate_actions": candidate_actions,
        "candidate_card_ids": np.tile(np.asarray([0, 7, 8]), (rows, 1)),
        "candidate_valid": np.ones((rows, 3), dtype=np.bool_),
        "candidate_scores": np.tile(np.asarray([0.0, 1.0, -1.0]), (rows, 1)),
        "candidate_crown_differences": np.zeros((rows, 3), dtype=np.int64),
        "candidate_tower_damage_differences": np.zeros((rows, 3), dtype=np.float32),
    }
    scores = np.tile(np.asarray([0.0, 2.0, -1.0], dtype=np.float32), (rows, 1))
    if regress:
        payload["candidate_scores"][0] = np.asarray([1.0, 2.0, 0.0])
        best_actions[0] = 20
        scores[0] = np.asarray([0.0, -1.0, 2.0])
    return payload, scores


def _audit(payload: dict[str, np.ndarray], scores: np.ndarray) -> dict[str, object]:
    return summarize_phase_card_gate(
        payload,
        scores,
        holdout_games=set(range(20)),
        required_card_token=7,
        minimum_phase_roots=5,
        minimum_phase_optimal_rate=0.80,
        minimum_phase_improvement_recall=0.80,
        minimum_required_card_roots=10,
        minimum_required_card_recall=0.80,
        minimum_score_gain=0.0,
    )


def test_phase_card_gate_accepts_balanced_exact_predictions() -> None:
    payload, scores = _payload()
    result = _audit(payload, scores)
    assert result["passed"] is True
    assert result["required_card_selection_recall"] == 1.0
    assert all(
        row["optimal_action_rate"] == 1.0
        for row in result["phase_metrics"].values()
    )


def test_phase_card_gate_rejects_terminal_regression() -> None:
    payload, scores = _payload(regress=True)
    result = _audit(payload, scores)
    assert result["passed"] is False
    assert result["phase_metrics"]["early"]["regressions"] == 1
