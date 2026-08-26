from __future__ import annotations

import argparse

import pytest

from scripts.validate_resident_full_matches import validate


def test_short_resident_episode_is_fully_native_and_deterministic() -> None:
    result = validate(
        argparse.Namespace(
            decks_path="decks.json",
            device="cpu",
            max_ticks=2,
            decision_interval=1,
            max_entities=16,
            max_objects=16,
            replays=2,
            require_tiebreak=False,
            seed=[202_608_261],
            policy=["noop"],
            out=None,
        )
    )

    episodes = result["episodes"]
    assert isinstance(episodes, list) and len(episodes) == 1
    episode = episodes[0]
    assert episode["done"]
    assert episode["native_ticks"] == episode["final_tick"] == 2
    assert episode["requested_native_ticks"] == 2
    assert episode["fallback_rows"] == 0
    assert episode["terminal_reason"] == "configured_tick_limit"
    assert not episode["reached_regulation_end"]
    assert result["acceptance"] == {
        "deterministic_replay": True,
        "all_requested_ticks_native": True,
        "zero_fallback": True,
        "terminal_boundary_reached": True,
        "required_tiebreak_timeline_reached": None,
        "python_parity_evaluated": False,
    }
    assert len(episode["digest"]) == 64


def test_tiebreak_gate_rejects_shortened_episode_before_execution() -> None:
    with pytest.raises(ValueError, match="STANDARD_MATCH_TICKS"):
        validate(
            argparse.Namespace(
                decks_path="decks.json",
                device="cpu",
                max_ticks=2,
                decision_interval=1,
                max_entities=16,
                max_objects=16,
                replays=2,
                require_tiebreak=True,
                seed=[202_608_261],
                policy=["noop"],
                out=None,
            )
        )
