from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_SPECS,
    PAIRED_WORKLOADS,
)
from scripts.finalize_zero_mechanics_rl_initializer import (
    _canonical_sha256,
    finalize_zero_initializer,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    root = tmp_path / "gameplay"
    root.mkdir()
    source = tmp_path / "source.pt"
    candidate = tmp_path / "candidate.pt"
    equivalence = tmp_path / "equivalence.json"
    heldout = tmp_path / "heldout.json"
    hog = tmp_path / "hog.json"
    source.write_bytes(b"source")
    candidate.write_bytes(b"candidate")
    heldout.write_text("[]\n", encoding="utf-8")
    hog.write_text("[]\n", encoding="utf-8")
    equivalence_payload = {
        "schema_version": 1,
        "source_checkpoint": str(source),
        "source_checkpoint_sha256": _sha256(source),
        "candidate_checkpoint": str(candidate),
        "candidate_checkpoint_sha256": _sha256(candidate),
        "exact_behavior_preservation_verified": True,
        "structure": {
            "query_nonzero_count": 0,
            "inherited_tensor_count": 12,
            "new_tensor_names": [
                "mechanics_slot_card_stats",
                "mechanics_slot_choice_query.weight",
            ],
        },
        "runtime": {
            "all_policy_outputs_bitwise_equal": True,
            "all_deterministic_actions_equal": True,
            "samples": 120,
            "deterministic_actions_compared": 120,
            "episodes": 4,
        },
    }
    equivalence_payload["evidence_sha256"] = _canonical_sha256(equivalence_payload)
    _write(equivalence, equivalence_payload)

    for name in PAIRED_WORKLOADS:
        games, seed, mode, strategy, deck_group = PAIRED_SPECS[name]
        decks = hog if deck_group == "hog" else heldout
        metrics = {
            "games": float(games),
            "wins": float(games // 2),
            "losses": float(games // 2),
            "draws": 0.0,
            "crown_diff_per_game": 0.0,
        }
        _write(
            root / f"candidate_{name}.metrics.json",
            {
                "schema_version": 1,
                "checkpoint": str(candidate),
                "checkpoint_sha256": _sha256(candidate),
                "opponent_checkpoint": None,
                "opponent_checkpoint_sha256": None,
                "sampling_decks_path": str(decks),
                "sampling_decks_sha256": _sha256(decks),
                "seed": seed,
                "mirror_match": True,
                "opponent_mode": mode,
                "opponent_strategy": strategy,
                "reward_profile": "defense-v2",
                "metrics": metrics,
            },
        )
        records = [
            {
                "game": game,
                "candidate_player": game % 2,
                "outcome": "win" if game < games // 2 else "loss",
                "candidate_crowns": 1 if game < games // 2 else 0,
                "opponent_crowns": 0 if game < games // 2 else 1,
            }
            for game in range(games)
        ]
        _write(root / f"candidate_{name}.games.json", records)

    decisions = root / "candidate_hog12.decisions.json"
    games_path = root / "candidate_hog12.games.json"
    _write(decisions, [])
    _write(
        root / "candidate_hog12.utilization.json",
        {
            "decisions": str(decisions),
            "decisions_sha256": _sha256(decisions),
            "game_records": str(games_path),
            "game_records_sha256": _sha256(games_path),
            "gate": {"passed": False},
            "zero_use_games": 12,
            "window_conversion_rate": 0.0,
            "mean_role_probability_when_legal_affordable": 0.0,
        },
    )
    return root, equivalence, source, candidate, heldout, hog


def test_zero_initializer_accepts_exact_checkpoint_and_complete_baseline(
    tmp_path: Path,
) -> None:
    root, equivalence, source, candidate, heldout, hog = _fixture(tmp_path)

    result = finalize_zero_initializer(
        root=root,
        equivalence_report=equivalence,
        source_checkpoint=source,
        candidate_checkpoint=candidate,
        heldout_decks=heldout,
        hog_decks=hog,
    )

    assert result["rl_initializer_eligible"]
    assert result["baseline_games"] == 72
    assert result["hog"]["gate"]["passed"] is False
    assert "no skill-improvement claim" in result["claim_scope"]
    assert result["evidence_sha256"][str(equivalence.resolve())] == _sha256(equivalence)


def test_zero_initializer_rejects_tampered_equivalence_report(tmp_path: Path) -> None:
    root, equivalence, source, candidate, heldout, hog = _fixture(tmp_path)
    payload = json.loads(equivalence.read_text(encoding="utf-8"))
    payload["runtime"]["all_deterministic_actions_equal"] = False
    _write(equivalence, payload)

    with pytest.raises(ValueError, match="evidence_sha256"):
        finalize_zero_initializer(
            root=root,
            equivalence_report=equivalence,
            source_checkpoint=source,
            candidate_checkpoint=candidate,
            heldout_decks=heldout,
            hog_decks=hog,
        )


def test_zero_initializer_rejects_game_records_that_disagree_with_metrics(
    tmp_path: Path,
) -> None:
    root, equivalence, source, candidate, heldout, hog = _fixture(tmp_path)
    records_path = root / "candidate_balanced12.games.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    records[0]["outcome"] = "loss"
    _write(records_path, records)

    with pytest.raises(ValueError, match="outcomes differ"):
        finalize_zero_initializer(
            root=root,
            equivalence_report=equivalence,
            source_checkpoint=source,
            candidate_checkpoint=candidate,
            heldout_decks=heldout,
            hog_decks=hog,
        )
