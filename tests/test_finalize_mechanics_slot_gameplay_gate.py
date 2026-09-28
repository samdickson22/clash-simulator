from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_WORKLOADS,
    finalize_gameplay_gate,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _eval_payload(
    *,
    checkpoint: Path,
    opponent_checkpoint: Path | None,
    decks: Path,
    games: int,
    seed: int,
    opponent_mode: str,
    opponent_strategy: str | None,
    metrics: dict,
) -> dict:
    outcome_metrics = {
        "wins": games // 2,
        "losses": games - games // 2,
        "draws": 0,
        "crown_diff_per_game": 0.0,
        **metrics,
    }
    return {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "opponent_checkpoint": (
            None if opponent_checkpoint is None else str(opponent_checkpoint)
        ),
        "opponent_checkpoint_sha256": (
            None if opponent_checkpoint is None else _sha256(opponent_checkpoint)
        ),
        "sampling_decks_path": str(decks),
        "sampling_decks_sha256": _sha256(decks),
        "seed": seed,
        "mirror_match": True,
        "opponent_mode": opponent_mode,
        "opponent_strategy": opponent_strategy,
        "reward_profile": "defense-v2",
        "metrics": {"games": games, **outcome_metrics},
    }


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path]:
    root = tmp_path / "gate" / "gameplay"
    root.mkdir(parents=True)
    candidate = tmp_path / "candidate.pt"
    parent = tmp_path / "parent.pt"
    probe = tmp_path / "probe.pt"
    validation_decks = tmp_path / "validation.json"
    heldout_decks = tmp_path / "heldout.json"
    hog_decks = tmp_path / "hog.json"
    candidate.write_bytes(b"candidate")
    parent.write_bytes(b"parent")
    probe.write_bytes(b"probe")
    for path in (validation_decks, heldout_decks, hog_decks):
        path.write_text("[]\n", encoding="utf-8")
    metrics = {
        name: {"accuracy_gain": 0.01, "materialized_logit_parity": True}
        for name in (
            "simulator_validation",
            "simulator_heldout",
            "human_validation",
            "human_archetype_test",
            "human_chronology_test",
        )
    }
    _write(
        root.parent / "materialized_candidate_evaluation.json",
        {
            "schema": "mechanics-slot-materialized-evaluation-v1",
            "parent_checkpoint": str(parent),
            "parent_checkpoint_sha256": _sha256(parent),
            "candidate_checkpoint": str(candidate),
            "candidate_checkpoint_sha256": _sha256(candidate),
            "probe_checkpoint": str(probe),
            "probe_checkpoint_sha256": _sha256(probe),
            "alpha": 0.1,
            "selection_splits": [
                "simulator_validation",
                "simulator_heldout",
                "human_validation",
            ],
            "post_selection_evaluation_only_splits": [
                "human_archetype_test",
                "human_chronology_test",
            ],
            "metrics": metrics,
        },
    )
    _write(
        root.parent / "selection.json",
        {
            "schema": "mechanics-slot-cross-seed-selection-v1",
            "status": "candidate_selected",
            "selected": {
                "alpha": 0.1,
                "median_seed": {"probe": str(probe)},
            },
        },
    )
    for split, decks, seed in (
        ("validation", validation_decks, 1056001),
        ("heldout", heldout_decks, 1056002),
    ):
        _write(
            root / f"direct_{split}12.metrics.json",
            _eval_payload(
                checkpoint=candidate,
                opponent_checkpoint=parent,
                decks=decks,
                games=12,
                seed=seed,
                opponent_mode="policy",
                opponent_strategy=None,
                metrics={"wins": 6, "losses": 6, "crown_diff_per_game": 0.0},
            ),
        )
        _write(root / f"direct_{split}12.games.json", {"games": []})
    specs = {
        "random12": (12, 1056010, "random", None, heldout_decks),
        "balanced12": (12, 1056011, "strategy", "balanced", heldout_decks),
        "reactive12": (
            12,
            1056012,
            "strategy",
            "reactive-defense",
            heldout_decks,
        ),
        "bridge6": (6, 1056013, "strategy", "bridge-pressure", heldout_decks),
        "slow6": (6, 1056014, "strategy", "slow-push", heldout_decks),
        "spell6": (6, 1056015, "strategy", "spell-control", heldout_decks),
        "split6": (6, 1056016, "strategy", "split-lane", heldout_decks),
        "hog12": (12, 1056017, "strategy", "balanced", hog_decks),
    }
    assert tuple(specs) == PAIRED_WORKLOADS
    defense = {
        "defense_event_success_rate": 0.45,
        "defense_event_mean_outcome": -0.05,
        "defense_events_resolved": 20,
        "candidate_noop_when_playable": 0.75,
    }
    for name, (games, seed, mode, strategy, decks) in specs.items():
        for role, checkpoint in (("parent", parent), ("candidate", candidate)):
            _write(
                root / f"{role}_{name}.metrics.json",
                _eval_payload(
                    checkpoint=checkpoint,
                    opponent_checkpoint=None,
                    decks=decks,
                    games=games,
                    seed=seed,
                    opponent_mode=mode,
                    opponent_strategy=strategy,
                    metrics=defense if name in {"balanced12", "reactive12"} else {},
                ),
            )
            _write(root / f"{role}_{name}.games.json", {"games": []})
        _write(
            root / f"{name}.compare.json",
            {
                "schema_version": 1,
                "baseline": str(root / f"parent_{name}.games.json"),
                "baseline_sha256": _sha256(root / f"parent_{name}.games.json"),
                "candidate": str(root / f"candidate_{name}.games.json"),
                "candidate_sha256": _sha256(root / f"candidate_{name}.games.json"),
                "games": games,
                "improvements": [],
                "regressions": [],
                "improvement_count": 0,
                "regression_count": 0,
                "unchanged_count": games,
                "baseline_crown_difference": 0.0,
                "candidate_crown_difference": 0.0,
                "crown_difference_change": 0.0,
                "passes_strict_no_regression": True,
            },
        )
    utilization = {
        "gate": {"passed": True},
        "zero_use_games": 0,
        "window_conversion_rate": 0.5,
        "mean_role_probability_when_legal_affordable": 0.4,
    }
    for role in ("parent", "candidate"):
        decisions = root / f"{role}_hog12.decisions.json"
        games = root / f"{role}_hog12.games.json"
        _write(decisions, {"decisions": []})
        _write(
            root / f"{role}_hog12.utilization.json",
            {
                **utilization,
                "decisions": str(decisions),
                "decisions_sha256": _sha256(decisions),
                "game_records": str(games),
                "game_records_sha256": _sha256(games),
            },
        )
    return root, candidate, parent, validation_decks, heldout_decks, hog_decks


def test_gameplay_gate_accepts_only_complete_no_regression_evidence(
    tmp_path: Path,
) -> None:
    root, candidate, parent, validation_decks, heldout_decks, hog_decks = _fixture(
        tmp_path
    )

    result = finalize_gameplay_gate(
        root=root,
        candidate_checkpoint=candidate,
        parent_checkpoint=parent,
        validation_decks=validation_decks,
        heldout_decks=heldout_decks,
        hog_decks=hog_decks,
    )

    assert result["status"] == "rl_initializer_ready"
    assert result["rl_initializer_eligible"]
    assert all(result["gates"].values())
    assert result["direct"]["games"] == 24
    assert result["paired"]["games"] == 72
    assert result["candidate_checkpoint_sha256"] == _sha256(candidate)
    assert result["parent_checkpoint_sha256"] == _sha256(parent)
    assert "not a promoted policy" in result["claim_scope"]


def test_gameplay_gate_rejects_one_paired_outcome_regression(tmp_path: Path) -> None:
    root, candidate, parent, validation_decks, heldout_decks, hog_decks = _fixture(
        tmp_path
    )
    comparison_path = root / "balanced12.compare.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["regressions"] = [{"matchup_seed": 1, "candidate_player": 0}]
    comparison["regression_count"] = 1
    comparison["unchanged_count"] = 11
    comparison["passes_strict_no_regression"] = False
    _write(comparison_path, comparison)

    result = finalize_gameplay_gate(
        root=root,
        candidate_checkpoint=candidate,
        parent_checkpoint=parent,
        validation_decks=validation_decks,
        heldout_decks=heldout_decks,
        hog_decks=hog_decks,
    )

    assert result["status"] == "rejected"
    assert not result["rl_initializer_eligible"]
    assert not result["gates"]["strict_outcome_no_regression"]


def test_gameplay_gate_rejects_checkpoint_changed_after_offline_evaluation(
    tmp_path: Path,
) -> None:
    root, candidate, parent, validation_decks, heldout_decks, hog_decks = _fixture(
        tmp_path
    )
    candidate.write_bytes(b"mutated candidate")

    with pytest.raises(ValueError, match="candidate checkpoint changed"):
        finalize_gameplay_gate(
            root=root,
            candidate_checkpoint=candidate,
            parent_checkpoint=parent,
            validation_decks=validation_decks,
            heldout_decks=heldout_decks,
            hog_decks=hog_decks,
        )


def test_gameplay_gate_rejects_stale_workload_provenance(tmp_path: Path) -> None:
    root, candidate, parent, validation_decks, heldout_decks, hog_decks = _fixture(
        tmp_path
    )
    path = root / "candidate_balanced12.metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["seed"] += 1
    _write(path, payload)

    with pytest.raises(ValueError, match="seed"):
        finalize_gameplay_gate(
            root=root,
            candidate_checkpoint=candidate,
            parent_checkpoint=parent,
            validation_decks=validation_decks,
            heldout_decks=heldout_decks,
            hog_decks=hog_decks,
        )


def test_gameplay_gate_rejects_game_records_changed_after_comparison(
    tmp_path: Path,
) -> None:
    root, candidate, parent, validation_decks, heldout_decks, hog_decks = _fixture(
        tmp_path
    )
    (root / "candidate_balanced12.games.json").write_text(
        '{"games":[{"outcome":"loss"}]}', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="candidate_sha256"):
        finalize_gameplay_gate(
            root=root,
            candidate_checkpoint=candidate,
            parent_checkpoint=parent,
            validation_decks=validation_decks,
            heldout_decks=heldout_decks,
            hog_decks=hog_decks,
        )
