"""Validate a weighted overtime screen and print its selected game IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SAMPLING_SOURCES = (
    Path("src/clasher/rl/deck_pool.py"),
    Path("src/clasher/rl/selfplay_env.py"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(
    *,
    manifest_path: Path,
    policy: Path,
    learner_decks: Path,
    opponent_decks: Path,
    selected_count: int,
) -> list[int]:
    if selected_count <= 0:
        raise ValueError("selected count must be positive")
    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    if manifest.get("schema") != "clasher.hog26_overtime_screen.v2":
        raise ValueError("overtime screen lacks weighted-sampling v2 authority")
    if manifest.get("selection_rule") != "terminal_tick_strictly_greater_than_3600":
        raise ValueError("overtime screen selection rule changed")
    inputs = manifest.get("input_sha256")
    if not isinstance(inputs, dict):
        raise TypeError("overtime screen lacks input hashes")
    authorities = (policy, learner_decks, opponent_decks, *SAMPLING_SOURCES)
    for path in authorities:
        expected = inputs.get(str(path))
        if not isinstance(expected, str) or _sha256(path) != expected:
            raise ValueError(f"overtime screen authority changed: {path}")
    selected = [int(value) for value in manifest.get("selected_games", [])]
    if len(selected) != int(manifest.get("selected_count", -1)):
        raise ValueError("overtime screen selected count is inconsistent")
    if len(selected) < selected_count:
        raise ValueError(
            f"overtime screen has {len(selected)} games, needs {selected_count}"
        )
    if len(selected) != len(set(selected)):
        raise ValueError("overtime screen repeats a selected game")
    start = int(manifest.get("game_start", -1))
    games = int(manifest.get("games", -1))
    if start < 0 or games <= 0 or any(
        value < start or value >= start + games for value in selected
    ):
        raise ValueError("overtime screen selected game is outside its range")
    return selected[:selected_count]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--learner-decks", type=Path, required=True)
    parser.add_argument("--opponent-decks", type=Path, required=True)
    parser.add_argument("--selected-count", type=int, required=True)
    args = parser.parse_args()
    selected = validate_manifest(
        manifest_path=args.manifest,
        policy=args.policy,
        learner_decks=args.learner_decks,
        opponent_decks=args.opponent_decks,
        selected_count=args.selected_count,
    )
    for game in selected:
        print(game)


if __name__ == "__main__":
    main()
