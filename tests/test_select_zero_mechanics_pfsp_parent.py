from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.finalize_mechanics_slot_gameplay_gate import PAIRED_WORKLOADS
from scripts.select_zero_mechanics_pfsp_parent import select_parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary(
    root: Path,
    *,
    wins: int,
    random_wins: int,
    noop: float,
    hog_gate: bool,
    hog_zero: int,
) -> Path:
    root.mkdir()
    checkpoint = root / "policy.pt"
    evidence = root / "evidence.json"
    summary = root / "summary.json"
    checkpoint.write_bytes(root.name.encode())
    evidence.write_text("{}\n", encoding="utf-8")
    per_workload_wins = {name: 0 for name in PAIRED_WORKLOADS}
    per_workload_wins["random12"] = random_wins
    remaining = wins - random_wins
    for name in PAIRED_WORKLOADS[1:]:
        games = 6 if name in {"bridge6", "slow6", "spell6", "split6"} else 12
        assigned = min(games, remaining)
        per_workload_wins[name] = assigned
        remaining -= assigned
    assert remaining == 0
    metrics = {}
    for name in PAIRED_WORKLOADS:
        games = 6 if name in {"bridge6", "slow6", "spell6", "split6"} else 12
        workload_wins = min(games, per_workload_wins[name])
        metrics[name] = {
            "games": games,
            "wins": workload_wins,
            "losses": games - workload_wins,
            "draws": 0,
            "crown_diff_per_game": (2 * workload_wins - games) / games,
            "candidate_noop_when_playable": noop,
        }
    payload = {
        "schema": "zero-mechanics-rl-initializer-v1",
        "rl_initializer_eligible": True,
        "baseline_games": 72,
        "candidate_checkpoint": str(checkpoint),
        "candidate_checkpoint_sha256": _sha256(checkpoint),
        "workload_metrics": metrics,
        "hog": {
            "gate": {"passed": hog_gate},
            "zero_use_games": hog_zero,
            "window_conversion_rate": 0.75,
            "mean_role_probability_when_legal_affordable": 0.70,
        },
        "evidence_sha256": {str(evidence): _sha256(evidence)},
    }
    summary.write_text(json.dumps(payload), encoding="utf-8")
    return summary


def test_parent_selector_accepts_large_active_matched_improvement(
    tmp_path: Path,
) -> None:
    incumbent = _summary(
        tmp_path / "incumbent",
        wins=15,
        random_wins=2,
        noop=0.95,
        hog_gate=False,
        hog_zero=7,
    )
    challenger = _summary(
        tmp_path / "challenger",
        wins=40,
        random_wins=10,
        noop=0.70,
        hog_gate=True,
        hog_zero=1,
    )

    result = select_parent(
        incumbent_summary=incumbent,
        challenger_summary=challenger,
    )

    assert result["challenger_selected"]
    assert not result["repair_pilot_authorized"]
    assert all(result["gates"].values())
    assert "not a promoted-policy" in result["claim_scope"]


def test_parent_selector_rejects_passive_challenger(tmp_path: Path) -> None:
    incumbent = _summary(
        tmp_path / "incumbent",
        wins=15,
        random_wins=2,
        noop=0.95,
        hog_gate=False,
        hog_zero=7,
    )
    challenger = _summary(
        tmp_path / "challenger",
        wins=40,
        random_wins=10,
        noop=0.95,
        hog_gate=True,
        hog_zero=0,
    )

    result = select_parent(
        incumbent_summary=incumbent,
        challenger_summary=challenger,
    )

    assert not result["challenger_selected"]
    assert not result["gates"]["meaningful_passivity_reduction"]
    assert not result["gates"]["no_frozen_workload"]


def test_parent_selector_authorizes_only_targeted_hog_repair(tmp_path: Path) -> None:
    incumbent = _summary(
        tmp_path / "incumbent",
        wins=15,
        random_wins=2,
        noop=0.95,
        hog_gate=False,
        hog_zero=7,
    )
    challenger = _summary(
        tmp_path / "challenger",
        wins=51,
        random_wins=10,
        noop=0.70,
        hog_gate=False,
        hog_zero=3,
    )

    result = select_parent(
        incumbent_summary=incumbent,
        challenger_summary=challenger,
    )

    assert not result["challenger_selected"]
    assert result["targeted_hog_defect"]
    assert result["repair_pilot_authorized"]
    assert result["status"] == "targeted_repair_pilot_authorized"
