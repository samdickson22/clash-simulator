from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.validate_hog26_overtime_screen_manifest import (
    SAMPLING_SOURCES,
    validate_manifest,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    policy = tmp_path / "policy.pt"
    learner = tmp_path / "learner.json"
    opponent = tmp_path / "opponent.json"
    for path, content in (
        (policy, b"policy"),
        (learner, b"learner"),
        (opponent, b"opponent"),
    ):
        path.write_bytes(content)
    payload: dict[str, object] = {
        "schema": "clasher.hog26_overtime_screen.v2",
        "game_start": 100,
        "games": 10,
        "selection_rule": "terminal_tick_strictly_greater_than_3600",
        "selected_games": [101, 104, 108],
        "selected_count": 3,
        "input_sha256": {
            str(path): _sha256(path)
            for path in (policy, learner, opponent, *SAMPLING_SOURCES)
        },
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, policy, learner, opponent, payload


def test_weighted_overtime_manifest_accepts_pinned_authorities(tmp_path: Path) -> None:
    manifest, policy, learner, opponent, _payload = _manifest(tmp_path)
    assert validate_manifest(
        manifest_path=manifest,
        policy=policy,
        learner_decks=learner,
        opponent_decks=opponent,
        selected_count=2,
    ) == [101, 104]


def test_weighted_overtime_manifest_rejects_old_schema(tmp_path: Path) -> None:
    manifest, policy, learner, opponent, payload = _manifest(tmp_path)
    payload["schema"] = "clasher.hog26_overtime_screen.v1"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="weighted-sampling v2"):
        validate_manifest(
            manifest_path=manifest,
            policy=policy,
            learner_decks=learner,
            opponent_decks=opponent,
            selected_count=2,
        )


def test_weighted_overtime_manifest_rejects_sampling_source_change(
    tmp_path: Path,
) -> None:
    manifest, policy, learner, opponent, payload = _manifest(tmp_path)
    inputs = payload["input_sha256"]
    assert isinstance(inputs, dict)
    inputs[str(SAMPLING_SOURCES[0])] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="authority changed"):
        validate_manifest(
            manifest_path=manifest,
            policy=policy,
            learner_decks=learner,
            opponent_decks=opponent,
            selected_count=2,
        )
