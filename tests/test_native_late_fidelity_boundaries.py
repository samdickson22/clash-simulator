"""Native movement, charge, and target-removal boundaries from opened cases."""

import importlib
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.data import CardDataLoader

REFERENCE = json.loads(
    (
        Path(__file__).parent
        / "fixtures/native_late_fidelity_boundaries_15_535_86.json"
    ).read_text()
)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["name"])
def test_native_late_fidelity_boundaries(case, fast_path, monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    initialize = importlib.import_module(
        "compare_reacting_public_branches"
    ).scalar_initial
    data = json.loads(CardDataLoader().data_file.read_text())
    for override in case["ruleset_overrides"]:
        node = data
        for key in override["path"][:-1]:
            node = node[key]
        key = override["path"][-1]
        assert node[key] in (override["original"], override["native"])
        node[key] = override["native"]
    profile = tmp_path / "native-profile.json"
    profile.write_text(json.dumps(data))
    loader = CardDataLoader(profile)
    names = {
        loader.get_card(name)._raw_entry["id"]: name
        for deck in case["plan"]["decks"]
        for name in deck
    }
    battle = initialize(case["initial"], names, case["plan"]["config"], loader)
    battle.fast_path = fast_path
    expected = {frame["tick"]: frame for frame in case["expected"]}
    commands = {}
    for command in case["commands"]:
        commands.setdefault(command["submitted_tick"], []).append(command)
    while battle.tick < max(expected):
        for command in commands.get(battle.tick, []):
            assert battle.deploy_card(
                command["owner"], command["name"], Position(*command["xy"])
            )
        battle.step()
        if battle.tick not in expected:
            continue
        frame = expected[battle.tick]
        bodies = sorted(
            [
                entity.player_id,
                round(entity.position.x * 1000),
                round(entity.position.y * 1000),
                entity.hitpoints,
            ]
            for entity in battle.entities.values()
            if entity.card_stats is not None
            and entity.card_stats.name not in {"Tower", "KingTower"}
            and entity.is_alive
            and entity.entity_kind in (0, 1)
        )
        assert bodies == frame["bodies"], battle.tick
        for watcher in frame.get("watchers", []):
            entity = next(
                entity
                for entity in battle.entities.values()
                if entity.card_stats
                and entity.card_stats.name == watcher["name"]
                and entity.player_id == watcher["owner"]
                and entity.is_alive
            )
            if "charge" in watcher:
                assert entity._native_charge_progress == watcher["charge"], battle.tick
            if "timeline_ms" in watcher:
                assert (
                    entity._ordinary_clock.hit_timeline_ms == watcher["timeline_ms"]
                ), battle.tick
                assert entity._ordinary_clock.load_remaining_ms == watcher["load_ms"], (
                    battle.tick
                )
