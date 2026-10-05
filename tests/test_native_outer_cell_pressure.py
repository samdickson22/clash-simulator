"""Moving bodies can leave the quarter-tile spawn margin."""
import importlib
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.native_tilemap import clamp_native_object_axis
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS


@pytest.mark.parametrize("size", [18, 32])
@pytest.mark.parametrize("position,expected", [
    (-0.1, 0.0), (0.211, 0.211), (0.25, 0.25),
    (17.789, 17.789), (18.1, 17.999),
])
def test_native_movement_uses_full_outer_cell(size, position, expected):
    # Reuse the x-axis samples at the corresponding edge of either axis.
    offset = size - 18 if position > 1 else 0
    assert clamp_native_object_axis(position + offset, size) == pytest.approx(expected + offset)


@pytest.mark.parametrize("fast_path", [False, True])
def test_pressure_leaves_spawn_margin_without_changing_spawn(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle._spawn_unit_at_position(
        Position(18.5, 7.261), 0, battle.card_loader.get_card("Goblins"),
        snap_to_valid=False,
    )
    goblin = battle.entities[max(battle.entities)]
    assert goblin.position.x == 17.75
    goblin._pending_movement_x = .039
    goblin._pending_movement_y = 0
    goblin._pending_movement_consumed = False
    goblin.finish_movement_tick(battle)
    # Native Goblin5000016 was born at17750 and reaches17789 before walking.
    assert goblin.position.x == 17.789


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_outer_cell_pressure_preserves_giant_final_hit(monkeypatch, tmp_path, fast_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    initialize = importlib.import_module("compare_reacting_public_branches").scalar_initial
    case = json.loads((Path(__file__).parent / "fixtures/native_outer_cell_pressure_15_535_86.json").read_text())
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
    names = {loader.get_card(n)._raw_entry["id"]: n for n in PUBLIC_REFERENCE_CARDS}
    battle = initialize(case["initial"], names, case["plan"]["config"], loader)
    battle.fast_path = fast_path
    # Native character IDs increase only on character births; scalar IDs also
    # count projectiles. Bind the two at each recorded card deployment.
    next_native_id = 5000006
    native_to_scalar = {}
    commands = {}
    for command in case["commands"]:
        commands.setdefault(command["submitted_tick"], []).append(command)
    expected = {}
    for tick, native_id, x, y in case["phase_positions"]:
        expected.setdefault(tick, []).append((native_id, x, y))
    while battle.tick < 540:
        for c in commands.get(battle.tick, []):
            before = set(battle.entities)
            assert battle.deploy_card(c["owner"], c["name"], Position(*c["xy"]))
            for identity in sorted(set(battle.entities) - before):
                if battle.entities[identity].entity_kind in (0, 1):
                    native_to_scalar[next_native_id] = identity
                    next_native_id += 1
        battle.step()
        # Phase-event tick t observes the body at public frame t, before the
        # next movement component. The 381 hooks contain 197 unique positions.
        for native_id, x, y in expected.get(battle.tick, []):
            entity = battle.entities[native_to_scalar[native_id]]
            assert [round(entity.position.x * 1000), round(entity.position.y * 1000)] == [x, y], (battle.tick, native_id)
        if str(battle.tick) in case["tower_hp"]:
            assert battle.players[0].right_tower_hp == case["tower_hp"][str(battle.tick)], battle.tick
