from __future__ import annotations

import json
from pathlib import Path

from clasher.rl.strategy_bots import STRATEGY_NAMES
from scripts.finalize_hog26_spatial_teacher_cuda_gate import finalize


def _write(
    path: Path,
    *,
    wins: list[int],
    placement_rate: float = 0.12,
) -> None:
    rows = [
        {
            "opponent": opponent,
            "games": 4,
            "wins": count,
            "losses": 4 - count,
            "draws": 0,
            "placement_rate": placement_rate,
            "simulation_backend_metadata": {"execution_mode": "cuda-graph"},
        }
        for opponent, count in zip((*STRATEGY_NAMES, "random"), wins, strict=True)
    ]
    path.write_text(
        json.dumps(
            {
                "schema": "clasher.hog26.simple-policy-evaluation.v1",
                "device": "cuda",
                "base_seed": 1249301,
                "games_per_opponent": 4,
                "checkpoint_sha256": path.stem,
                "rows": rows,
            }
        )
    )


def test_spatial_gate_accepts_broad_no_regression_improvement(tmp_path: Path) -> None:
    _write(tmp_path / "base.json", wins=[1] * 7)
    _write(tmp_path / "candidate.json", wins=[2, 2, 1, 1, 1, 1, 1])
    result = finalize(tmp_path, games=4, seed=1249301)
    assert result["status"] == "candidate-passed-development-gate"
    assert result["opponent_improvements"] == 2
    assert result["opponent_regressions"] == 0


def test_spatial_gate_rejects_shifted_regression(tmp_path: Path) -> None:
    _write(tmp_path / "base.json", wins=[1] * 7)
    _write(tmp_path / "candidate.json", wins=[2, 2, 2, 1, 1, 1, 0])
    result = finalize(tmp_path, games=4, seed=1249301)
    assert result["total_candidate_score"] > result["total_base_score"]
    assert result["opponent_regressions"] == 1
    assert result["status"] == "candidate-rejected"


def test_spatial_gate_rejects_non_cuda_graph_evidence(tmp_path: Path) -> None:
    _write(tmp_path / "base.json", wins=[1] * 7)
    _write(tmp_path / "candidate.json", wins=[2] * 7)
    payload = json.loads((tmp_path / "candidate.json").read_text())
    payload["rows"][0]["simulation_backend_metadata"]["execution_mode"] = "eager"
    (tmp_path / "candidate.json").write_text(json.dumps(payload))
    try:
        finalize(tmp_path, games=4, seed=1249301)
    except ValueError as error:
        assert "CUDA Graph" in str(error)
    else:
        raise AssertionError("eager evidence did not fail closed")
