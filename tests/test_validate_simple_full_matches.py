from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts.validate_simple_full_matches import build_simple_runtime, validate


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


def test_runtime_builder_uses_standard_expanded_catalog_and_phase_authority() -> None:
    runtime = build_simple_runtime(
        seed=202_608_263,
        decks=[["BattleRam"] * 8],
        batch_size=1,
        device="cpu",
        max_entities=16,
        max_effects=16,
        regulation_ticks=3_600,
        tiebreak_ticks=6_000,
    )

    assert runtime.spawn_blueprints is not None
    root = runtime.spawn_blueprints.cards.name_to_id["BattleRam"]
    child = int(runtime.spawn_blueprints.fast_cards.death_spawn_card_id[root])
    assert child > 0
    assert not bool(runtime.spawn_blueprints.public_card_mask[child])
    assert runtime.projector.inputs.hand_token_lookup[child].item() == 0
    assert runtime.projector.inputs.entity_token_lookup[:, child].gt(0).all()
    assert runtime.double_elixir_tick == 2_400
    assert runtime.outcomes.rules.regulation_ticks == 3_600
    assert runtime.triple_elixir_tick == 4_800
    assert runtime.outcomes.rules.tiebreak_ticks == 6_000


def test_runtime_builder_remains_strict_for_unsupported_validation_deck() -> None:
    with pytest.raises(ValueError, match="unsupported.*Golem"):
        build_simple_runtime(
            seed=202_608_263,
            decks=[["Golem"] * 8],
            batch_size=1,
            device="cpu",
            max_entities=16,
            max_effects=16,
            regulation_ticks=3_600,
            tiebreak_ticks=6_000,
        )


def test_first_legal_episode_is_bounded_terminal_and_replayed(
    tmp_path: Path,
) -> None:
    result = validate(_args(tmp_path, policy=["first-legal"]))

    episode = result["episodes"][0]
    assert episode["policy"] == "first-legal"
    assert episode["done"]
    assert episode["final_tick"] <= 4
    assert episode["committed_rows"] == episode["native_ticks"]
    assert episode["winner"] in (-1, 0, 1)
    assert len(episode["cumulative_rewards"]) == 2
    assert len(episode["digest"]) == 64
