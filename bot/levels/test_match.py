"""Unit tests of the play_match levels path (bot/levels/match.py) that need no runtime."""
import json
import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from .configs import LevelConfigs
from .match import L11Packets, from_lists, install_planner, max_levels, mirror_config, resolve, tower_curve
from .root import tower_stat

DECK = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Mirror']


def test_resolve_max_and_mixed_specs():
    spec = resolve(max_levels(), [DECK, DECK])
    assert spec['cards'] == [{c: 16 for c in DECK}] * 2 and spec['towers'] == [16, 16]
    assert spec['tag'] == 'card16-tower16' and not spec['trivial'] and spec['planner'] == 'exact'
    spec = resolve({'cards': {'1': {'Giant': 9}}, 'towers': {0: 13}}, [DECK, DECK])
    assert spec['cards'][0] == {c: 11 for c in DECK}
    assert spec['cards'][1] == dict({c: 11 for c in DECK}, Giant=9)
    assert spec['towers'] == [13, 11] and spec['tag'] == 'card11-tower13/cardmixed-tower11'
    assert resolve({}, [DECK, DECK])['trivial']
    assert resolve(from_lists([{c: 16 for c in DECK}] * 2, [16, 16]), [DECK, DECK])['cards'] == \
        resolve(max_levels(), [DECK, DECK])['cards']


@pytest.mark.parametrize('bad', [dict(cards={0: 17}), dict(cards={0: 0}), dict(towers={1: 11.5}), dict(cards={0: True}),
                                 dict(cards={0: {'Hog': 12}}), dict(planner='oracle'), dict(level=16)])
def test_resolve_rejects(bad):
    with pytest.raises(ValueError):
        resolve(bad, [DECK, DECK])


def test_tower_curve_level16():
    # Level 16 crown towers (RoyaleSim 16.402 check: reports/cards/levels/RESULTS.md); level 6 = the live client.
    assert (tower_stat('KingTower', 'max_hp', 16), tower_stat('KingTower', 'damage', 16)) == (7728, 173)
    assert (tower_stat('Tower', 'max_hp', 16), tower_stat('Tower', 'damage', 16)) == (4858, 173)
    assert (tower_stat('KingTower', 'max_hp', 6), tower_stat('Tower', 'max_hp', 6)) == (3312, 2030)


def test_tower_curve_patch_only_outside_10_to_12(monkeypatch):
    calls = []
    ts = ModuleType('clasher.tower_scaling')
    ts.tower_stat = lambda name, field, level=11: calls.append((name, field, level)) or -1
    pkg = ModuleType('clasher')
    pkg.tower_scaling = ts
    monkeypatch.setitem(sys.modules, 'clasher', pkg)
    monkeypatch.setitem(sys.modules, 'clasher.tower_scaling', ts)
    original = ts.tower_stat
    with tower_curve():
        assert ts.tower_stat('KingTower', 'hitpoints', 16) == 7728
        assert ts.tower_stat('PrincessTower', 'damage', 16) == 173
        assert ts.tower_stat('PrincessTower', 'hitpoints', 11) == -1     # 10-12: the engine's own values
    assert calls == [('PrincessTower', 'hitpoints', 11)] and ts.tower_stat is original


def _unit(name, hp, key=None):
    return {'class': 'Troop', 'stats': {'name': name, 'max_hp': hp, 'payload_key': key, 'leaf_elixir_share': 1.}}


def _lc(tmp_path, cfg, exports):
    rt = SimpleNamespace(R=SimpleNamespace(config=cfg), pins={})
    lc = LevelConfigs(rt, cache=tmp_path)
    for level, cards in exports.items():
        lc.levels[level] = json.loads(json.dumps(dict(level=level, cards=cards, errors={})))
    return lc


def test_config_builder_per_seat_level16(tmp_path):
    """configs.mixed at level 16 for one seat: that seat's formation, death table and qualified spell key."""
    golem11 = {'units': [[_unit('Golem', 100.)], [_unit('Golem', 100.)]], 'cost': 8}
    golem16 = {'units': [[_unit('Golem', 159., 'level16:Golem')], [_unit('Golem', 159., 'level16:Golem')]], 'cost': 8}
    fb11 = {'units': [[{'class': 'Projectile', 'spell_name': 'Fireball', 'stats': {'name': '', 'max_hp': 1}}]] * 2,
            'spell': {'damage': 10}}
    fb16 = {'units': [[{'class': 'Projectile', 'spell_name': 'Fireball', 'stats': {'name': '', 'max_hp': 1}}]] * 2,
            'spell': {'damage': 15}}
    cfg = {'cards': {'Golem': golem11, 'Fireball': fb11}, 'death_children': {'Golem': {'n': 2, 'hp': 10}}}
    lc = _lc(tmp_path, cfg, {11: {'Golem': dict(card=golem11, tables={'death_children': {'Golem': {'n': 2, 'hp': 10}}}),
                                  'Fireball': dict(card=fb11, tables={})},
                             16: {'Golem': dict(card=golem16, tables={'death_children': {'Golem': {'n': 2, 'hp': 15}}}),
                                  'Fireball': dict(card=fb16, tables={})}})
    out, report = lc.mixed(lambda seat, card: 16 if seat == 1 else 11)
    assert out['cards']['Golem']['units'][0][0]['stats']['max_hp'] == 100.
    assert out['cards']['Golem']['units'][1][0]['stats'] == dict(golem16['units'][1][0]['stats'])
    assert out['death_children']['level16:Golem'] == {'n': 2, 'hp': 15} and out['death_children']['Golem']['hp'] == 10
    assert out['cards']['Fireball']['units'][1][0]['spell_name'] == 'level16:Fireball'
    assert out['cards']['Fireball']['units'][0][0]['spell_name'] == 'Fireball'
    assert out['cards']['level16:Fireball']['spell'] == {'damage': 15}
    assert report['changed'] == 2 and not report['unsupported']
    # All 11 = the runtime config itself.
    same, _ = lc.mixed(lambda seat, card: 11)
    assert json.dumps(same, sort_keys=True) == json.dumps(cfg, sort_keys=True)


def test_mirror_config_level17(tmp_path):
    knight12 = {'units': [[_unit('Knight', 120., 'level12:Knight')]] * 2, 'cost': 3}
    knight12['units'][0][0]['stats']['leaf_elixir_share'] = 4.
    knight17 = {'units': [[_unit('Knight', 190., 'level17:Knight')], [_unit('Knight', 190., 'level17:Knight')]], 'cost': 3}
    cfg = {'cards': {'Knight': {'units': [[_unit('Knight', 110.)]] * 2}, 'Mirror': {}, 'level12:Knight': knight12},
           'death_children': {}}
    lc = _lc(tmp_path, {'cards': {'Knight': cfg['cards']['Knight'], 'Mirror': {}}},
             {11: {'Knight': dict(card=cfg['cards']['Knight'], tables={})},
              17: {'Knight': dict(card=knight17, tables={'death_children': {'Knight': {'x': 1}}})}})
    out, bad = mirror_config(lc, cfg, 17)
    assert not bad
    unit = out['cards']['level12:Knight']['units'][0][0]['stats']
    assert unit['max_hp'] == 190. and unit['payload_key'] == 'level17:Knight' and unit['leaf_elixir_share'] == 4.
    assert out['cards']['level17:Knight']['units'][1][0]['stats']['max_hp'] == 190.
    assert out['death_children'] == {'level17:Knight': {'x': 1}}
    assert cfg['cards']['level12:Knight'] is knight12 and knight12['units'][0][0]['stats']['max_hp'] == 120.
    assert mirror_config(lc, cfg, 12) == (cfg, [])


@dataclass(frozen=True)
class _Obs:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray


@dataclass(frozen=True)
class _Packet:
    observation: _Obs


@dataclass(frozen=True)
class _Info:
    tick: int
    packet: _Packet


def test_l11_packets_rewrites_base_damage_only():
    R = SimpleNamespace(templates={(5, 'Troop'): {'stats': {'damage': 200.}}, (6, 'Building'): {'stats': {'damage': 0}}})
    feats = np.zeros((3, 33), np.float32)
    feats[0, 4], feats[0, 30], feats[0, 9] = 1, np.log1p(320.) / 8, .5     # level-16 troop, token 5
    feats[1, 5], feats[1, 30] = 1, .25                                       # building token 6 (damage 0)
    feats[2, 4], feats[2, 30] = 1, .7                                        # masked row: untouched
    info = _Info(90, _Packet(_Obs(np.array([5, 6, 5]), feats, np.array([True, True, False]))))
    norm = L11Packets(R)
    out = norm.info(info).packet.observation.entity_features
    assert out[0, 30] == np.float32(np.log1p(200.) / 8) and out[1, 30] == 0 and out[2, 30] == np.float32(.7)
    assert out[0, 9] == np.float32(.5) and info.packet.observation.entity_features[0, 30] == np.float32(np.log1p(320.) / 8)
    assert norm.counts == dict(rows=2, changed=2, unmapped=0)


def test_install_planner_scope():
    spec = resolve(max_levels(), [DECK, DECK])

    class Policy:
        name = 'R3a'
    assert install_planner(None, Policy(), 0, spec) == 'l11 (no root_fn)'
    assert install_planner(None, Policy(), 0, dict(spec, planner='l11')) == 'l11'

    class Pooled:
        root_fn, name, pool_size = None, 'K4L-R-gs-p2', 2
    assert install_planner(None, Pooled(), 0, spec).startswith('l11 (pooled p2')
    assert install_planner(None, SimpleNamespace(search=Pooled()), 0, spec).startswith('l11 (pooled p2')
    assert install_planner(None, Pooled(), 0, resolve({}, [DECK, DECK])) == 'exact (all 11 = R.root)'
