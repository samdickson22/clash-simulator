from __future__ import annotations

import argparse

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
    assert episode["fallback_rows"] == 0
    assert len(episode["digest"]) == 64
