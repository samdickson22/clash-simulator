"""New projectile reservations preserve their full duration on the launch tick."""
import importlib
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.data import CardDataLoader


@pytest.mark.parametrize('fast_path', [False, True])
def test_native_new_projectile_reservation_and_target_release(monkeypatch, tmp_path, fast_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    initialize = importlib.import_module('compare_reacting_public_branches').scalar_initial
    case = json.loads((Path(__file__).parent / 'fixtures/native_new_projectile_reservation_15_535_86.json').read_text())
    data = json.loads(CardDataLoader().data_file.read_text())
    for override in case['ruleset_overrides']:
        node = data
        for key in override['path'][:-1]:
            node = node[key]
        key = override['path'][-1]
        assert node[key] in (override['original'], override['native'])
        node[key] = override['native']
    profile = tmp_path / 'native-profile.json'
    profile.write_text(json.dumps(data))
    loader = CardDataLoader(profile)
    names = {loader.get_card(n)._raw_entry['id']: n for deck in case['plan']['decks'] for n in deck}
    battle = initialize(case['initial'], names, case['plan']['config'], loader)
    battle.fast_path = fast_path
    expected = {f['tick']: f for f in case['expected']}
    commands = {}
    for command in case['commands']:
        commands.setdefault(command['submitted_tick'], []).append(command)
    musketeer_id = skeleton_id = None
    native_to_scalar = {None: None, 5000004: 4}
    while battle.tick < max(expected):
        for c in commands.get(battle.tick, []):
            before = set(battle.entities)
            assert battle.deploy_card(c['owner'], c['name'], Position(*c['xy']))
            created = sorted(set(battle.entities) - before)
            if c['submitted_tick'] == 360:
                musketeer_id = created[0]
            if c['submitted_tick'] == 240:
                skeleton_id = created[1]
                native_to_scalar.update({5000013 + i: identity for i, identity in enumerate(created)})
        battle.step()
        if battle.tick in expected:
            frame = expected[battle.tick]
            musketeer = battle.entities[musketeer_id]
            assert [round(musketeer.position.x * 1000), round(musketeer.position.y * 1000)] == frame['xy'], battle.tick
            target = native_to_scalar[frame['target']]
            assert musketeer.target_id == target, battle.tick
            assert musketeer._ordinary_clock.hit_timeline_ms == frame['timeline'], battle.tick
        if str(battle.tick) in case['pending_duration']:
            assert battle.entities[skeleton_id]._pending_projectile_max_duration_ms == case['pending_duration'][str(battle.tick)]


def test_reservation_measures_at_publication_and_does_not_refresh():
    from clasher.battle import BattleState
    from clasher.entities import Projectile

    battle = BattleState()
    target = next(iter(battle.entities.values()))
    target.position = Position(0, 7.3)
    battle._logic_tick_active = True
    shot = Projectile(
        id=100, position=Position(0, 0), player_id=1,
        card_stats=None, hitpoints=1, max_hitpoints=1, damage=109,
        range=0, sight_range=0, primary_target=target, travel_speed=12,
    )
    assert not shot.reserves_pending_damage
    target.position = Position(0, 7.1)
    shot.activate_pending_damage()
    assert target._pending_projectile_max_duration_ms == 600
    target._pending_projectile_max_duration_ms = 550
    target.position = Position(0, 20)
    shot.activate_pending_damage()
    assert target._pending_projectile_max_duration_ms == 550
    assert shot._pending_damage_launch_duration_ms == 600
