from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.verify_hog26_structured_terminal_cf_corpus import (
    STRATEGIES,
    verify_split,
)


def _write_split(
    root: Path,
    *,
    game_count: int = 12,
    recurrent: bool = False,
    game_ids: list[int] | None = None,
) -> None:
    states = []
    games = []
    selected_games = list(range(game_count)) if game_ids is None else game_ids
    for game in selected_games:
        strategy = STRATEGIES[game % len(STRATEGIES)]
        seat = (game // len(STRATEGIES)) % 2
        games.append(
            {
                "game": game,
                "strategy": strategy,
                "controlled_player": seat,
            }
        )
        for tick in (256, 384):
            states.append(
                {
                    "game": game,
                    "tick": tick,
                    "strategy": strategy,
                    "controlled_player": seat,
                    "decisive_improvement": game < 2,
                    "base_score": float(game < 4),
                }
            )
    count = len(states)
    candidate_valid = np.tile(
        np.asarray([True, True, False], dtype=np.bool_), (count, 1)
    )
    candidate_actions = np.tile(
        np.asarray([0, 1, -1], dtype=np.int64), (count, 1)
    )
    action_masks = np.zeros((count, 10), dtype=np.bool_)
    action_masks[:, :2] = True
    finite_candidate = np.zeros((count, 3), dtype=np.float32)
    finite_candidate[:4, 1] = 1.0
    padded_candidate = finite_candidate.copy()
    padded_candidate[:, 2] = -np.inf
    entity_ids = np.tile(np.asarray([2, 3, 0]), (count, 1))
    entity_mask = np.tile(np.asarray([True, True, False]), (count, 1))
    arrays = {
        "action_masks": action_masks,
        "base_actions": np.zeros(count, dtype=np.int64),
        "best_actions": np.concatenate(
            (
                np.ones(4, dtype=np.int64),
                np.zeros(count - 4, dtype=np.int64),
            )
        ),
        "candidate_actions": candidate_actions,
        "candidate_valid": candidate_valid,
        "candidate_scores": finite_candidate,
        "candidate_policy_logits": padded_candidate,
        "candidate_policy_log_probabilities": padded_candidate,
        "candidate_policy_type_log_probabilities": padded_candidate,
        "candidate_card_features": np.zeros((count, 3, 4), dtype=np.float32),
        "candidate_crown_differences": np.zeros((count, 3), dtype=np.int8),
        "candidate_tile_features": np.zeros((count, 3, 2), dtype=np.float32),
        "candidate_tower_damage_differences": np.zeros(
            (count, 3), dtype=np.float32
        ),
        "features": np.zeros((count, 5), dtype=np.float32),
        "game_ids": np.asarray([row["game"] for row in states]),
        "ticks": np.asarray([row["tick"] for row in states]),
        "structured_entity_ids": entity_ids,
        "structured_entity_features": np.zeros(
            (count, 3, 6), dtype=np.float32
        ),
        "structured_entity_mask": entity_mask,
        "structured_hand_ids": np.full((count, 5), 2, dtype=np.int64),
        "structured_global_features": np.zeros((count, 4), dtype=np.float32),
        "structured_previous_rewards": np.zeros(count, dtype=np.float32),
    }
    if recurrent:
        arrays["features"] = np.zeros((count, 69), dtype=np.float32)
        arrays["structured_recurrent_cell"] = np.zeros(
            (count, 64), dtype=np.float32
        )
        arrays["structured_previous_play_hazard"] = np.zeros(
            (count, 1), dtype=np.float32
        )
    root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(root / "train.npz", **arrays)
    report = {
        "best_action_order": "outcome-crowns-tower-damage-v1",
        "input_sha256": {
            "policy": "a" * 64,
            "decks": "b" * 64,
            "outcome": None,
            "sampling_decks": None,
            "learner_sampling_decks": "c" * 64,
            "opponent_sampling_decks": "d" * 64,
        },
        "structured_state_contract": (
            "public-actor-v2-action-time-recurrence"
            if recurrent
            else "public-actor-v1"
        ),
        "games": games,
        "states": states,
        "states_collected": count,
        "decisive_improvements": 4,
        "base_terminal_wins": 8,
    }
    (root / "train.json").write_text(json.dumps(report), encoding="utf-8")


def test_structured_counterfactual_quality_accepts_complete_split(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)

    result = verify_split(tmp_path, "train", 12)

    assert result["games"] == 12
    assert result["states"] == 24
    assert result["decisive_rate"] == 1 / 6
    assert result["candidate_seats"] == {"0": 6, "1": 6}
    assert result["tick_coverage"]["early_lt_1200"] == 24
    assert result["tick_coverage"]["overtime_ge_3600"] == 0


def test_structured_counterfactual_quality_rejects_strategy_drift(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)
    report_path = tmp_path / "train.json"
    report = json.loads(report_path.read_text())
    report["games"][0]["strategy"] = "balanced"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="strategy balance"):
        verify_split(tmp_path, "train", 12)


def test_structured_counterfactual_quality_rejects_balanced_strategy_permutation(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)
    report_path = tmp_path / "train.json"
    report = json.loads(report_path.read_text())
    report["games"][2]["strategy"], report["games"][4]["strategy"] = (
        report["games"][4]["strategy"],
        report["games"][2]["strategy"],
    )
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="strategy balance"):
        verify_split(tmp_path, "train", 12)


def test_structured_counterfactual_quality_rejects_illegal_candidate(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)
    arrays_path = tmp_path / "train.npz"
    with np.load(arrays_path, allow_pickle=False) as source:
        arrays = {name: np.asarray(source[name]) for name in source.files}
    arrays["best_actions"][:] = 1
    arrays["action_masks"][0, 1] = False
    np.savez_compressed(arrays_path, **arrays)

    with pytest.raises(ValueError, match="illegal best action"):
        verify_split(tmp_path, "train", 12)


def test_structured_counterfactual_quality_rejects_wrong_terminal_best_action(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)
    arrays_path = tmp_path / "train.npz"
    with np.load(arrays_path, allow_pickle=False) as source:
        arrays = {name: np.asarray(source[name]) for name in source.files}
    arrays["candidate_scores"][:, 0] = 1.0
    arrays["candidate_scores"][:, 1] = 0.0
    arrays["best_actions"][:] = 1
    np.savez_compressed(arrays_path, **arrays)

    with pytest.raises(ValueError, match="terminal preference order"):
        verify_split(tmp_path, "train", 12)


def test_structured_counterfactual_quality_requires_base_on_exact_tie(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path)
    arrays_path = tmp_path / "train.npz"
    with np.load(arrays_path, allow_pickle=False) as source:
        arrays = {name: np.asarray(source[name]) for name in source.files}
    arrays["base_actions"][:] = 1
    arrays["best_actions"][:] = 0
    arrays["candidate_actions"][:, :2] = np.asarray([1, 0])
    np.savez_compressed(arrays_path, **arrays)

    with pytest.raises(ValueError, match="terminal preference order"):
        verify_split(tmp_path, "train", 12)


def test_structured_counterfactual_quality_accepts_recurrent_v2(
    tmp_path: Path,
) -> None:
    _write_split(tmp_path, recurrent=True)

    result = verify_split(
        tmp_path,
        "train",
        12,
        expected_contract="public-actor-v2-action-time-recurrence",
        minimum_phase_roots={"early_lt_1200": 24},
    )

    assert result["states"] == 24
    assert result["tick_coverage"]["early_lt_1200"] == 24


def test_structured_counterfactual_quality_accepts_screened_game_ids(
    tmp_path: Path,
) -> None:
    game_ids = [*range(6), *range(500, 506)]
    _write_split(tmp_path, game_ids=game_ids)

    result = verify_split(
        tmp_path,
        "train",
        len(game_ids),
        expected_game_ids=set(game_ids),
    )

    assert result["games"] == 12
    assert result["states"] == 24


def test_structured_counterfactual_quality_uses_collector_strategy_order(
    tmp_path: Path,
) -> None:
    # These residues distinguish the collector's canonical order from the stale
    # verifier order that nearly balanced uniform corpora failed to expose.
    game_ids = [2, 4, 5, 8, 10, 11]
    _write_split(tmp_path, game_count=len(game_ids), game_ids=game_ids)

    result = verify_split(
        tmp_path,
        "train",
        len(game_ids),
        expected_game_ids=set(game_ids),
    )

    assert result["strategies"] == {
        "balanced": 2,
        "spell-control": 2,
        "split-lane": 2,
    }
