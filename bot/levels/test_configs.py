"""Regression fixtures for serialized config comparison and tower-shot physics."""
import copy
import json
from types import SimpleNamespace

from .configs import LevelConfigs
from .root import ExactLevelRoot, tower_stat


def test_cache_roundtrip_preserves_support_but_damage_change_does_not(tmp_path):
    card = {'units': [[{'tunnel_origin': (0., 0.), 'stats': {'damage': 113.}}], []]}
    cfg = {'cards': {'Musketeer': card}, 'death_children': {'Musketeer': {'anchor': (1., 2.)}}}
    rt = SimpleNamespace(R=SimpleNamespace(config=cfg), pins={})
    lc = LevelConfigs(rt, cache=tmp_path)
    exported = {'level': 11, 'cards': {'Musketeer': {'card': card,
                'tables': {'death_children': cfg['death_children']}}}, 'errors': {}}
    lc.levels[11] = json.loads(json.dumps(exported))
    assert lc.check11() == (['Musketeer'], {})
    # A stale support receipt from the old raw-Python comparison is not reused.
    lc.dir.mkdir(parents=True)
    (lc.dir / 'supported.json').write_text(json.dumps({'cards': [], 'unsupported': {}}))
    assert lc.supported() == {'Musketeer'}
    lc.levels[11]['cards']['Musketeer']['card']['units'][0][0]['stats']['damage'] += 1
    good, bad = lc.check11()
    assert good == [] and 'Musketeer' in bad


def test_tower_projectile_keeps_unit_hp_and_uses_tower_damage():
    root = ExactLevelRoot.__new__(ExactLevelRoot)
    root.stats = {'towers': 0}
    shot = {'class': 'Projectile', 'stats': {'name': 'Tower', 'max_hp': 1., 'damage': 109.}, 'hp': 1.}
    before = copy.deepcopy(shot)
    root.tower(shot, 6)
    assert shot['stats']['damage'] == tower_stat('Tower', 'damage', 6) == 72
    assert shot['stats']['max_hp'] == before['stats']['max_hp'] == shot['hp'] == 1
    tower = {'class': 'Building', 'stats': {'name': 'Tower', 'max_hp': 3052., 'damage': 109.}}
    root.tower(tower, 6)
    assert tower['stats'] == {'name': 'Tower', 'max_hp': 2030., 'damage': 72.}


def test_public_spell_identity_overrides_shared_empty_body_name():
    root = ExactLevelRoot.__new__(ExactLevelRoot)
    root.R = SimpleNamespace(config={'cards': {'Arrows': {}, 'Fireball': {}}})
    root._producers = {'': ['Arrows', 'Fireball']}
    deck = {'Arrows', 'Fireball'}
    assert root.body_card('', 1, 0, deck, spell='Fireball') == 'Fireball'
    assert root.body_card('', 1, 0, deck, spell='level7:Fireball') == 'Fireball'
    assert root.body_card('', 1, 0, deck, spell='Arrows') == 'Arrows'
