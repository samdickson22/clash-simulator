from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.merge_phase_stratified_counterfactual_corpora import merge


def _write_source(
    root: Path,
    *,
    game: int,
    tick: int,
    targets: list[int],
) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    npz = root / "source.npz"
    report = root / "source.json"
    arrays = {
        "game_ids": np.asarray([game], dtype=np.int64),
        "ticks": np.asarray([tick], dtype=np.int32),
        "candidate_actions": np.asarray([[0, -1]], dtype=np.int64),
        "candidate_valid": np.asarray([[True, False]], dtype=np.bool_),
        "features": np.zeros((1, 3), dtype=np.float32),
    }
    np.savez_compressed(npz, **arrays)
    payload = {
        "schema_version": 2,
        "policy": "policy.pt",
        "outcome": "None",
        "candidate_card_semantics_version": 3,
        "candidate_card_feature_size": 36,
        "best_action_order": "outcome-crowns-tower-damage-v1",
        "input_sha256": {
            "policy": "a" * 64,
            "decks": "b" * 64,
            "outcome": None,
            "sampling_decks": None,
            "learner_sampling_decks": "c" * 64,
            "opponent_sampling_decks": "d" * 64,
        },
        "collection_config": {
            "minimum_tick": 3600 if targets == [3600] else 256,
            "states_per_game": 1,
        },
        "structured_state_contract": "public-actor-v2-action-time-recurrence",
        "learner_sampling_decks_path": "hog.json",
        "opponent_sampling_decks_path": "opponents.json",
        "query_schedule": "phase-balanced",
        "query_target_ticks": targets,
        "sampling_decks_path": None,
        "sampling_decks_paths": [],
        "shards": 1,
        "states": [
            {
                "game": game,
                "tick": tick,
                "decisive_improvement": False,
                "base_score": 0.0,
            }
        ],
        "games": [{"game": game, "seed": 1000 + game}],
    }
    report.write_text(json.dumps(payload), encoding="utf-8")
    return npz, report


def test_phase_stratified_merge_keeps_real_overtime_rows(tmp_path: Path) -> None:
    uniform_npz, uniform_report = _write_source(
        tmp_path / "uniform", game=0, tick=3480, targets=[256, 3600]
    )
    overtime_npz, overtime_report = _write_source(
        tmp_path / "overtime", game=500, tick=3608, targets=[3600]
    )

    result = merge(
        uniform_npz=uniform_npz,
        uniform_report_path=uniform_report,
        overtime_npz=overtime_npz,
        overtime_report_path=overtime_report,
        output=tmp_path / "merged.npz",
        report_path=tmp_path / "merged.json",
    )

    assert result["states_collected"] == 2
    assert result["screened_overtime_states"] == 1
    assert result["query_schedule"].startswith("phase-stratified")
    with np.load(tmp_path / "merged.npz", allow_pickle=False) as payload:
        assert payload["ticks"].tolist() == [3480, 3608]


def test_phase_stratified_merge_rejects_non_overtime_supplement(
    tmp_path: Path,
) -> None:
    uniform_npz, uniform_report = _write_source(
        tmp_path / "uniform", game=0, tick=3480, targets=[256, 3600]
    )
    overtime_npz, overtime_report = _write_source(
        tmp_path / "overtime", game=500, tick=3592, targets=[3600]
    )

    with pytest.raises(ValueError, match="not all overtime"):
        merge(
            uniform_npz=uniform_npz,
            uniform_report_path=uniform_report,
            overtime_npz=overtime_npz,
            overtime_report_path=overtime_report,
            output=tmp_path / "merged.npz",
            report_path=tmp_path / "merged.json",
        )
