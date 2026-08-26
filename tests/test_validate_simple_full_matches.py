from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts.validate_simple_full_matches import validate


def _deck_file(tmp_path: Path) -> Path:
    path = tmp_path / "decks.json"
    path.write_text(
        json.dumps(
            {
                "decks": [
                    {
                        "name": "fixture",
                        "cards": ["Knight"] * 8,
                    }
                ]
            }
        )
    )
    return path


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "decks_path": _deck_file(tmp_path),
        "device": "cpu",
        "max_entities": 16,
        "max_effects": 16,
        "regulation_ticks": 2,
        "tiebreak_ticks": 4,
        "replays": 2,
        "require_exact_timeline": False,
        "seed": [202_608_263],
        "policy": ["noop"],
        "out": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_noop_episode_replays_through_regulation_overtime_and_tiebreak(
    tmp_path: Path,
) -> None:
    result = validate(_args(tmp_path))

    assert result["acceptance"] == {
        "deterministic_replay": True,
        "all_rows_committed": True,
        "all_row_ticks_native": True,
        "zero_fallback": True,
        "terminal_boundary_reached": True,
        "noop_regulation_ot_tiebreak": True,
        "python_parity_evaluated": False,
    }
    episodes = result["episodes"]
    assert isinstance(episodes, list) and len(episodes) == 1
    episode = episodes[0]
    assert episode["final_tick"] == episode["row_ticks"] == 4
    assert episode["committed_rows"] == episode["native_ticks"] == 4
    assert episode["entered_overtime"]
    assert episode["terminal_reason"] == "tiebreak"
    assert episode["cumulative_rewards"] == (0.0, 0.0)
    assert len(episode["digest"]) == 64


def test_exact_timeline_gate_rejects_short_test_rules(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="3600/6000"):
        validate(_args(tmp_path, require_exact_timeline=True))
