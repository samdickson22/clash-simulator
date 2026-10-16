"""Checks for bot/cards/proxy_table.py against gamedata.json, the pool and the C56 source."""
import ast
import json
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reports/cards/tools'))

from pool import ladder_pool  # noqa: E402
from bot.cards import proxy_table as pt  # noqa: E402

GAMEDATA = {s['name']: s for s in json.loads((ROOT / 'gamedata.json').read_text())['items']['spells']}
POOL = {p['name']: p for p in ladder_pool()}
TARGETS = sorted(set(POOL) - pt.C56)
SPECIAL_BODY = {'ElectroWizard': 'ElectroWizard', 'IceWizard': 'IceWizard', 'ThreeMusketeers': 'Musketeer'}


def _norm(name):
    return ''.join(ch for ch in name.casefold() if ch.isalnum())


AIR_NORM = {_norm(n) for n in pt.AIR_BODY_NAMES}


def _is_air_body(name):
    return _norm(name) in AIR_NORM


def _tree(card):
    """Bodies named by summonCharacterData and its spawn/death chains."""
    sc = GAMEDATA[card].get('summonCharacterData') or {}
    out = set()
    if sc.get('name'):
        out.add(sc['name'])

    def walk(d):
        for key in ('spawnCharacterData', 'spawnCharacter2Data', 'deathSpawnCharacterData', 'deathSpawnCharacter2Data'):
            child = d.get(key)
            if isinstance(child, dict):
                out.add(child['name'])
                walk(child)
        for key in ('deathSpawnCharacter', 'spawnCharacter'):
            if isinstance(d.get(key), str):
                out.add(d[key])

    walk(sc)
    return out


def _char_names(obj, out):
    """Every characters-source body name in a gamedata entry (evolutions excluded)."""
    if isinstance(obj, dict):
        if obj.get('source') == 'characters' and 'name' in obj:
            out.add(obj['name'])
        for key, value in obj.items():
            if key != 'evolvedSpellsData':
                _char_names(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _char_names(value, out)
    return out


def _c56_source():
    tree = ast.parse((ROOT / 'bot/players/rext_imitate_replays.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'C56':
            return set(ast.literal_eval(node.value.args[0]))
    raise AssertionError('C56 not found')


def _main_body(card):
    return (GAMEDATA[card].get('summonCharacterData') or {}).get('name') or SPECIAL_BODY.get(card)


def test_named_covers_exactly_the_66_targets():
    assert len(TARGETS) == 66
    assert set(pt.NAMED) == set(TARGETS)
    assert not (set(pt.NAMED) & pt.C56)


def test_c56_and_body_list_match_sources():
    assert pt.C56 == frozenset(_c56_source())
    vocab = json.loads((ROOT / 'bot/players/royalesim_vocab.json').read_text())
    assert pt.BODIES_47 == frozenset(vocab['units'])


@pytest.mark.parametrize('card', TARGETS)
def test_entry_shape_costs_and_kinds(card):
    entry = pt.NAMED[card]
    assert isinstance(entry['cost'], float)
    assert entry['cost'] == float(GAMEDATA[card]['manaCost'])
    assert entry['kind'] == POOL[card]['kind']
    assert entry['cls'] == entry['kind']
    assert isinstance(entry['air'], bool)
    assert isinstance(entry['bodies'], int)
    assert isinstance(entry['why'], str) and entry['why']


@pytest.mark.parametrize('card', TARGETS)
def test_proxy_card_is_c56_with_same_kind(card):
    proxy = pt.NAMED[card]['proxy_card']
    assert proxy in pt.C56
    assert POOL[proxy]['kind'] == POOL[card]['kind']


@pytest.mark.parametrize('card', TARGETS)
def test_air_flag_matches_gamedata(card):
    main = _main_body(card)
    expected = _is_air_body(main or '') or _is_air_body(card) or card == 'DartBarrell'
    assert pt.NAMED[card]['air'] == expected


@pytest.mark.parametrize('card', TARGETS)
def test_spells_have_no_bodies(card):
    entry = pt.NAMED[card]
    if entry['kind'] != 'spell':
        return
    assert entry['body_map'] == {}
    assert entry['proxy_body'] == ''
    assert entry['bodies'] == 0


@pytest.mark.parametrize('card', [c for c in TARGETS if pt.NAMED[c]['kind'] != 'spell'])
def test_body_map_keys_are_the_gamedata_bodies(card):
    entry = pt.NAMED[card]
    if card in SPECIAL_BODY:
        assert set(entry['body_map']) == {SPECIAL_BODY[card]}
    else:
        assert set(entry['body_map']) == _tree(card)
    assert all(value in pt.BODIES_47 for value in entry['body_map'].values())


@pytest.mark.parametrize('card', [c for c in TARGETS if pt.NAMED[c]['kind'] != 'spell'])
def test_proxy_body_is_the_main_body_mapping(card):
    entry = pt.NAMED[card]
    main = _main_body(card)
    assert entry['proxy_body'] == entry['body_map'][main]
    assert entry['proxy_body'] in pt.BODIES_47


@pytest.mark.parametrize('card', [c for c in TARGETS if pt.NAMED[c]['kind'] == 'troop'])
def test_troop_bodies_keep_air_plane(card):
    entry = pt.NAMED[card]
    main = _main_body(card)
    for true_body, proxy in entry['body_map'].items():
        true_air = (true_body == main and entry['air']) or _is_air_body(true_body)
        assert _is_air_body(proxy) == true_air, (card, true_body, proxy)


def test_bodies_counts_come_from_gamedata():
    assert pt.NAMED['Barbarians']['bodies'] == 5
    assert pt.NAMED['SpearGoblins']['bodies'] == 3
    assert pt.NAMED['GoblinCage']['bodies'] == 1
    assert pt.NAMED['ThreeMusketeers']['bodies'] == 3  # hand-set, no summonNumber in gamedata


@pytest.mark.parametrize('card', TARGETS)
def test_shared_body_matches_gamedata_trees(card):
    expected = sorted(c for c in pt.C56 if _char_names(GAMEDATA[c], set()) & _char_names(GAMEDATA[card], set()))
    assert pt.SHARED_BODY[card] == expected
    assert all(c in pt.C56 for c in pt.SHARED_BODY[card])


def test_class_only_table():
    assert set(pt.CLASS_ONLY) == {'troop', 'building', 'air'}
    air_pool = [p for p in POOL.values() if p['kind'] == 'troop' and (_is_air_body(_main_body(p['name']) or '') or _is_air_body(p['name']) or p['name'] == 'DartBarrell')]
    ground_pool = [p for p in POOL.values() if p['kind'] == 'troop' and p not in air_pool]
    building_pool = [p for p in POOL.values() if p['kind'] == 'building']
    assert pt.CLASS_ONLY['troop']['cost'] == float(statistics.median(p['cost'] for p in ground_pool))
    assert pt.CLASS_ONLY['air']['cost'] == float(statistics.median(p['cost'] for p in air_pool))
    assert pt.CLASS_ONLY['building']['cost'] == float(statistics.median(p['cost'] for p in building_pool))
    for key in pt.CLASS_ONLY:
        assert pt.CLASS_ONLY[key]['proxy_body'] in pt.BODIES_47


def test_proxy_body_helper():
    assert pt.proxy_body('Witch') == 'Wizard'
    assert pt.proxy_body('Skeleton') == 'Skeleton'
    assert pt.proxy_body('SomeNewTroop', kind='troop', air=False) == pt.CLASS_ONLY['troop']['proxy_body']
    assert pt.proxy_body('SomeNewFlyer', kind='troop', air=True) == pt.CLASS_ONLY['air']['proxy_body']
    assert pt.proxy_body('SomeNewBuilding', kind='building') == pt.CLASS_ONLY['building']['proxy_body']
    assert pt.proxy_body('SomeNewSpell', kind='spell') is None
