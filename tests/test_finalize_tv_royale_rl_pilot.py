from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.finalize_tv_royale_rl_pilot import finalize_rl_pilot


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path / "pilot"
    candidate = tmp_path / "candidate.pt"
    parent = tmp_path / "parent.pt"
    promoted = tmp_path / "promoted.txt"
    candidate.write_bytes(b"candidate")
    parent.write_bytes(b"parent")
    common = {"checkpoint": str(candidate), "parent": str(parent)}
    _write(
        root / "direct_summary.json",
        {**common, "games": 48, "wins": 26, "losses": 22, "earns_priority_screen": True},
    )
    _write(
        root / "priority_summary.json",
        {**common, "games": 60, "passes_strict_no_regression": True},
    )
    _write(
        root / "full168_summary.json",
        {**common, "games": 168, "passes_strict_no_regression": True},
    )
    _write(
        root / "training_stability.json",
        {
            "parent": str(parent),
            "passes": True,
            "start_update": 41,
            "end_update": 44,
            "updates": 4,
            "transition_delta": 16_384,
        },
    )
    _write(
        root / "state_dict_audit.json",
        {
            "before": str(parent),
            "after": str(candidate),
            "passes": True,
            "actor_changed_parameter_count": 2,
            "value_changed_parameter_count": 2,
            "unauthorized_changes": [],
        },
    )
    for view, wins, losses in (("uniform", 33, 31), ("frequency_weighted", 34, 30)):
        _write(
            root / f"human_meta_{view}64.metrics.json",
            {
                "checkpoint": str(candidate),
                "opponent_checkpoint": str(parent),
                "mirror_match": True,
                "metrics": {
                    "games": 64,
                    "wins": wins,
                    "losses": losses,
                    "draws": 0,
                    "crown_diff_per_game": 0.1,
                },
            },
        )
    pool = tmp_path / "pool.json"
    pool.write_text("{}")
    manifest = tmp_path / "exclusion.json"
    _write(
        manifest,
        {
            "retained_exclusion_overlap": 0,
            "excluded_decks": 3,
            "retained_decks": 20,
            "output": str(pool),
            "output_sha256": hashlib.sha256(pool.read_bytes()).hexdigest(),
        },
    )
    return root, candidate, parent, manifest, promoted


def test_publishes_only_when_every_rl_gate_is_reverified(tmp_path: Path) -> None:
    root, candidate, parent, manifest, promoted = _setup(tmp_path)

    payload = finalize_rl_pilot(
        pilot_root=root,
        candidate=candidate,
        parent=parent,
        deck_exclusion_manifest=manifest,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is True
    assert all(payload["gates"].values())
    assert promoted.read_text().strip() == str(candidate.resolve())


def test_rejects_partial_evidence_and_clears_stale_promotion(tmp_path: Path) -> None:
    root, candidate, parent, manifest, promoted = _setup(tmp_path)
    promoted.write_text("stale\n")
    direct = json.loads((root / "direct_summary.json").read_text())
    direct["games"] = 24
    _write(root / "direct_summary.json", direct)

    payload = finalize_rl_pilot(
        pilot_root=root,
        candidate=candidate,
        parent=parent,
        deck_exclusion_manifest=manifest,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is False
    assert payload["gates"]["direct_parent_improvement"] is False
    assert promoted.read_text() == ""


def test_rejects_changed_exclusion_output_or_wrong_checkpoint(tmp_path: Path) -> None:
    root, candidate, parent, manifest, promoted = _setup(tmp_path)
    Path(json.loads(manifest.read_text())["output"]).write_text("changed")
    view = json.loads((root / "human_meta_uniform64.metrics.json").read_text())
    view["checkpoint"] = str(tmp_path / "other.pt")
    _write(root / "human_meta_uniform64.metrics.json", view)

    payload = finalize_rl_pilot(
        pilot_root=root,
        candidate=candidate,
        parent=parent,
        deck_exclusion_manifest=manifest,
        promotion_candidate_path=promoted,
    )

    assert payload["promotion_eligible"] is False
    assert payload["gates"]["checkpoint_consistency"] is False
    assert payload["gates"]["human_meta_excluded_from_training"] is False
