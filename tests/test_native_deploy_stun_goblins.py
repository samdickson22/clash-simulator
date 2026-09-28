"""Deployment ending under Zap retains the native walking avoidance state."""
import importlib
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.data import CardDataLoader


@pytest.mark.parametrize('fast_path', [False, True])
def test_native_goblin_steering_after_deployment_during_zap(monkeypatch, tmp_path, fast_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    initialize = importlib.import_module('compare_reacting_public_branches').scalar_initial
    case = json.loads((Path(__file__).parent / 'fixtures/native_deploy_stun_goblins_15_535_86.json').read_text())
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
    expected = {f['tick']: f['bodies'] for f in case['expected']}
    commands = {}
    for command in case['commands']:
        commands.setdefault(command['submitted_tick'], []).append(command)
    goblin_id = None
    while battle.tick < max(expected):
        for c in commands.get(battle.tick, []):
            before = set(battle.entities)
            assert battle.deploy_card(c['owner'], c['name'], Position(*c['xy']))
            if c['submitted_tick'] == 3630:
                goblin_id = max(set(battle.entities) - before)
        battle.step()
        if battle.tick in expected:
            bodies = sorted([round(e.position.x * 1000), round(e.position.y * 1000), e.hitpoints]
                            for e in battle.entities.values() if e.card_stats.name == 'Goblins')
            assert bodies == expected[battle.tick], battle.tick
        if str(battle.tick) in case['avoidance']:
            assert battle.entities[goblin_id]._native_avoidance == case['avoidance'][str(battle.tick)]
