from __future__ import annotations

import json
from pathlib import Path

from scripts.finalize_tv_royale_gameplay_screen import finalize_gameplay_screen


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _complete_screen(tmp_path: Path, checkpoint: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "screen"
    selected = tmp_path / "development-selected.txt"
    promoted = tmp_path / "promotion-candidate.txt"
    checkpoint.write_bytes(b"checkpoint")
    selected.write_text(str(checkpoint) + "\n", encoding="utf-8")
    _write(
        root / "development_screen_summary.json",
        {
            "candidates": [
                {
                    "checkpoint": str(checkpoint),
                    "wins": 13,
                    "losses": 11,
                    "draws": 0,
                }
            ]
        },
    )
    _write(
        root / "expanded" / "expanded_summary.json",
        {"checkpoint": str(checkpoint), "games": 96, "wins": 49, "losses": 47},
    )
    _write(
        root / "priority" / "priority_summary.json",
        {
            "checkpoint": str(checkpoint),
            "games": 60,
            "passes_strict_no_regression": True,
        },
    )
    _write(
        root / "full168" / "full168_summary.json",
        {
            "checkpoint": str(checkpoint),
            "games": 168,
            "passes_strict_no_regression": True,
        },
    )
    _write(
        root / "human_meta" / "summary.json",
        {
            "checkpoint": str(checkpoint),
            "games": 128,
            "evaluation_only": True,
            "training_action_labels_used": False,
            "passes_human_meta_gate": True,
        },
    )
    return root, selected, promoted


def test_finalizer_publishes_only_after_every_gate_passes(tmp_path: Path) -> None:
    checkpoint = tmp_path / "candidate.pt"
    root, selected, promoted = _complete_screen(tmp_path, checkpoint)

    payload = finalize_gameplay_screen(
        screen_root=root,
        development_selected_path=selected,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is True
    assert promoted.read_text(encoding="utf-8").strip() == str(checkpoint)


def test_finalizer_clears_candidate_after_late_gate_failure(tmp_path: Path) -> None:
    checkpoint = tmp_path / "candidate.pt"
    root, selected, promoted = _complete_screen(tmp_path, checkpoint)
    promoted.write_text("stale candidate\n", encoding="utf-8")
    _write(
        root / "human_meta" / "summary.json",
        {
            "checkpoint": str(checkpoint),
            "games": 128,
            "evaluation_only": True,
            "training_action_labels_used": False,
            "passes_human_meta_gate": False,
        },
    )

    payload = finalize_gameplay_screen(
        screen_root=root,
        development_selected_path=selected,
        promotion_candidate_path=promoted,
    )

    assert payload["status"] == "promotion_rejected"
    assert payload["gates"]["human_meta"] is False
    assert promoted.read_text(encoding="utf-8") == ""


def test_finalizer_rejects_partial_or_nonreserved_evidence(tmp_path: Path) -> None:
    checkpoint = tmp_path / "candidate.pt"
    root, selected, promoted = _complete_screen(tmp_path, checkpoint)
    _write(
        root / "human_meta" / "summary.json",
        {
            "checkpoint": str(checkpoint),
            "games": 64,
            "evaluation_only": False,
            "training_action_labels_used": True,
            "passes_human_meta_gate": True,
        },
    )

    payload = finalize_gameplay_screen(
        screen_root=root,
        development_selected_path=selected,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is False
    assert payload["gates"]["complete_evidence_counts"] is False
    assert payload["gates"]["human_meta_evaluation_only"] is False
    assert promoted.read_text(encoding="utf-8") == ""


def test_finalizer_rejects_stale_summary_from_another_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "candidate.pt"
    root, selected, promoted = _complete_screen(tmp_path, checkpoint)
    _write(
        root / "expanded" / "expanded_summary.json",
        {"checkpoint": str(tmp_path / "other.pt"), "wins": 60, "losses": 36},
    )

    payload = finalize_gameplay_screen(
        screen_root=root,
        development_selected_path=selected,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is False
    assert payload["checkpoint_mismatches"] == ["expanded"]
    assert promoted.read_text(encoding="utf-8") == ""
