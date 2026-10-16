"""Independent checks against gamedata, engine traits, and decoded RoyaleSim 16.402.

Set ROYALESIM_ROOT to relocate the read-only upstream checkout. No simulator,
network, GPU, or worker processes are started by these tests.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path

import pytest

from bot.cards import proxy_table as pt

ROOT = Path(__file__).resolve().parents[2]
RS_ROOT = Path(os.environ.get('ROYALESIM_ROOT', '/mpac/sdicks02/tmp/bot-upstream/RoyaleSim'))
# Baseline first, dated balance overlays last.
RS_FILES = sorted((RS_ROOT / 'data/derived').glob('cards-160402017*.json'),
                  key=lambda p: p.stem.removeprefix('cards-160402017').lstrip('-'))
assert RS_FILES, f'RoyaleSim 16.402 metadata required at {RS_ROOT}; set ROYALESIM_ROOT'
RS_ALL = [json.loads(p.read_text()) for p in RS_FILES]
RS = RS_ALL[-1]
CARDS = {s['name']: s for s in RS['cards']}
GD = {s['name']: s for s in json.loads((ROOT / 'gamedata.json').read_text())['items']['spells']}
VOCAB = json.loads((ROOT / 'bot/players/royalesim_vocab.json').read_text())
KINDS = {'spells_characters': 'troop', 'spells_buildings': 'building', 'spells_other': 'spell'}
VISIBLE = {n for n, s in GD.items() if not s.get('notVisible') and s.get('source') in KINDS}


def norm(name):
    return ''.join(c for c in name.casefold() if c.isalnum())


# Load only the traits module, without initializing the engine package.
_spec = importlib.util.spec_from_file_location('proxy_test_traits', ROOT / 'src/clasher/unit_traits.py')
TRAITS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TRAITS)


def gd_bodies(card):
    """Walk ALL nested graphs, including abilities, buffs, morphs and projectiles."""
    out = {}

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get('source') in ('characters', 'buildings'):
                out[obj['name']] = obj
            for k, v in obj.items():
                if k != 'evolvedSpellsData':
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    walk(GD[card])
    return out


# Typed links in extract_cards.py's derived schema. Follow references as well
# as inline objects: a spawn can be several projectile/area/buff hops away.
LINKS = {
    'summon_character': 'units', 'character': 'units', 'character2': 'units',
    'spawn_character': 'units', 'morph': 'units', 'into': 'units', 'unit': 'units',
    'attached_character': 'units', 'card': 'cards',
    'projectile': 'projectiles', 'death_spawn_projectile': 'projectiles',
    'deploy_projectile': 'projectiles', 'first_projectile': 'projectiles',
    'spawn_projectile': 'projectiles',
    'death_area_effect': 'area_effect_objects', 'spawn_area_object': 'area_effect_objects',
    'spawn_area_effect_object': 'area_effect_objects', 'area_effect_object': 'area_effect_objects',
    'deploy_area_effect': 'area_effect_objects', 'buff': 'buffs', 'target_buff': 'buffs',
}
SPAWN_TYPES = {'CharacterType': 'units', 'BuildingType': 'units',
               'AreaEffectType': 'area_effect_objects', 'BuffType': 'buffs',
               'ProjectileType': 'projectiles'}


def rs_bodies(card, data=RS):
    tables = {k: data[k] for k in ('units', 'projectiles', 'area_effect_objects', 'buffs')}
    tables['cards'] = {s['name']: s for s in data['cards']}
    seen, out = set(), set()

    def follow(table, name):
        if (table, name) in seen:
            return
        seen.add((table, name))
        obj = tables[table].get(name)
        # Inline Void buffs are embedded in strike_area.tiers rather than
        # the global buff registry; they cannot produce combat bodies.
        if obj is None and table == 'buffs':
            assert name.startswith('DarkMagicAOE_Damage_lv'), (table, name)
            return
        assert obj is not None, (table, name)
        if table == 'units':
            out.add(name)
        walk(obj)

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and k in LINKS:
                    follow(LINKS[k], v)
                elif k == 'spawn' and isinstance(v, str) and obj.get('spawn_type') in SPAWN_TYPES:
                    follow(SPAWN_TYPES[obj['spawn_type']], v)
                elif k == 'spawns':
                    for item in v:
                        typ, name = item.split(':', 1)
                        if typ in SPAWN_TYPES:
                            follow(SPAWN_TYPES[typ], name)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
    follow('cards', card)
    return out


def expected_bodies(card):
    out = set(gd_bodies(card))
    for data in RS_ALL:
        out |= rs_bodies(card, data)
    if card == 'Graveyard':
        tree = ast.parse((ROOT / 'src/clasher/balance.py').read_text())
        overrides = next(n.value for n in tree.body if isinstance(n, ast.AnnAssign)
                         and getattr(n.target, 'id', '') == 'AREA_EFFECT_FIELD_OVERRIDES')
        row = next(v for k, v in zip(overrides.keys, overrides.values)
                   if isinstance(k, ast.Constant) and k.value == 'Graveyard_rework')
        out |= {v.value for n in ast.walk(row) if isinstance(n, ast.Dict)
                for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant)
                and k.value == 'spawnCharacter' and isinstance(v, ast.Constant)}
    # Engine SkeletonKingSoulCollector uses Skeleton, the client uses its
    # SkeletonKingSkeleton row. Keep both observed spellings.
    if card == 'SkeletonKing':
        tree = ast.parse((ROOT / 'src/clasher/mechanics/champion/skeleton_king.py').read_text())
        out |= {k.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                for k in node.keywords if k.arg == 'unit_name' and isinstance(k.value, ast.Constant)}
    return out


def body_kind(name):
    # Runtime classification overrides stale gamedata's characters source:
    # BrokenCannon is a building in the decoded live client.
    if name in RS['units']:
        return 'building' if RS['units'][name]['source_table'] == 'buildings' else 'troop'
    rows = [row for card in GD for n, row in gd_bodies(card).items() if n == name]
    assert rows, name
    return 'building' if rows[0]['source'] == 'buildings' else 'troop'


def body_air(name):
    row = RS['units'].get(name)
    if row is not None:
        return bool(row.get('flying_height', 0))
    assert norm(name) in TRAITS.AIR_UNIT_NAMES or any(name in gd_bodies(c) for c in GD), name
    return norm(name) in TRAITS.AIR_UNIT_NAMES


def c56_source():
    tree = ast.parse((ROOT / 'bot/players/rext_imitate_replays.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'C56':
            return set(ast.literal_eval(node.value.args[0]))
    raise AssertionError('C56 missing')


TARGETS = sorted(VISIBLE - c56_source())


def test_scope_and_vocab():
    assert len(TARGETS) == 66
    assert set(pt.NAMED) == set(TARGETS)
    assert pt.C56 == c56_source()
    assert pt.BODIES_47 == set(VOCAB['units'])


@pytest.mark.parametrize('card', TARGETS)
def test_all_live_costs_and_shape(card):
    e = pt.NAMED[card]
    assert e['cls'] == e['kind'] == ('troop' if card in ('Heal', 'MergeMaiden') else KINDS[GD[card]['source']])
    assert isinstance(e['air'], bool) and type(e['bodies']) is int
    assert e['why']
    for data in RS_ALL:
        row = next(s for s in data['cards'] if s['name'] == card)
        if card == 'Mirror':
            assert e['cost'] is None and e['cost_rule'] == 'last_played+1'
            assert row['elixir'] == GD[card]['manaCost'] == 1  # sentinel, not payment
        elif card == 'MergeMaiden':
            assert e['cost'] is None and e['cost_rule'] == 'observed_form'
            options = row['spell']['variant']['options']
            assert {o['card'] for o in options} == set(e['forms'])
            for o in options:
                form = next(s for s in data['cards'] if s['name'] == o['card'])
                assert e['forms'][o['card']]['cost'] == form['elixir'] == o['trigger_milli'] / 1000
        else:
            assert e['cost'] == row['elixir']
            assert isinstance(e['cost'], (float, int))


def test_cost_disagreements_are_explicit():
    for data in RS_ALL:
        cards = {s['name']: s for s in data['cards']}
        diffs = {n: (GD[n]['manaCost'], cards[n]['elixir']) for n in VISIBLE
                 if GD[n]['manaCost'] != cards[n]['elixir']}
        assert diffs == pt.COST_DISAGREEMENTS == {'DarkMagic': (3, 5)}


@pytest.mark.parametrize('card', TARGETS)
def test_every_reachable_body_is_accounted_for(card):
    assert set(pt.NAMED[card]['body_map']) == expected_bodies(card)


# Independent exclusions, with behavior evidence in the engine card modules.
UNSAFE_BODIES = {
    'Miner': 'tunnel/deploy-anywhere state (cards/miner.py)',
    'IceGolemite': 'death slow/freeze (cards/ice_golem.py)',
    'Golem': 'splits into unsupported Golemites (cards/golem.py)',
    'Ghost': 'invisibility state (cards/royal_ghost.py)',
    'DarkPrince': 'shield and charge (cards/dark_prince.py / formations)',
    'Prince': 'charge state (formations / mechanic_detector)',
}


@pytest.mark.parametrize('card', TARGETS)
def test_proxy_kind_flight_and_mechanics(card):
    e = pt.NAMED[card]
    champions = {n for n, s in GD.items() if s.get('rarity') == 'Champion'}
    champion_bodies = set(VOCAB['champion_units']) | {'goblinstein', 'Goblinstein'}
    for n in champions:
        champion_bodies |= set(gd_bodies(n))
    champions |= {s['name'] for s in RS['cards'] if s.get('rarity') == 'Champion'}
    for form in e.get('forms', {}).values():
        assert form['proxy_card'] in pt.C56
        assert form['proxy_card'] not in champions | UNSAFE_BODIES.keys()
        assert form['proxy_body'] not in champion_bodies | UNSAFE_BODIES.keys()
        assert KINDS[GD[form['proxy_card']]['source']] == form['cls']
    assert e['proxy_card'] in pt.C56
    assert e['proxy_card'] not in champions | UNSAFE_BODIES.keys()
    assert e['proxy_body'] not in champion_bodies | UNSAFE_BODIES.keys()
    proxy_kind = KINDS[GD[e['proxy_card']]['source']]
    assert proxy_kind == e['cls']
    for true, proxy in e['body_map'].items():
        if proxy is None:
            assert true in pt.UNPLACED_BODIES and pt.UNPLACED_BODIES[true]
            continue
        assert proxy in VOCAB['units']
        assert proxy not in champion_bodies | UNSAFE_BODIES.keys()
        assert body_kind(proxy) == body_kind(true), (card, true, proxy)
        if body_kind(true) == 'troop':
            assert body_air(proxy) == body_air(true), (card, true, proxy)
    if e['cls'] != 'spell':
        assert e['proxy_body'] in e['body_map'].values()
        assert body_air(e['proxy_body']) == e['air']


def deployment_count(card):
    s = GD[card]
    if card == 'MergeMaiden':
        return CARDS['MergeMaiden_Normal']['count']
    if card == 'ThreeMusketeers':
        # The export omitted its list; live overlay explicitly lists 3 members.
        return len(CARDS[card]['summon_members'])
    if card == 'Heal':
        assert '_heal_spirit_entry' in (ROOT / 'src/clasher/balance.py').read_text()
        return CARDS[card]['spell']['summon']['count']
    if KINDS[s['source']] == 'spell':
        # This measures initial combat bodies, not delayed spell/curse spawns
        # (nor stationary bottles). They remain covered by body_map.
        return 0
    return (s.get('summonNumber', 1) if s.get('summonCharacterData') else CARDS[card]['count']) + s.get('summonCharacterSecondCount', 0)


@pytest.mark.parametrize('card', TARGETS)
def test_deployment_counts(card):
    assert pt.NAMED[card]['bodies'] == deployment_count(card)


def test_secondary_summon_counts_and_forms():
    # Validate the count rule on a real two-character card, even though Rascals
    # itself is C56 and therefore not a NAMED target.
    s = GD['Rascals']
    assert s['summonNumber'] + s['summonCharacterSecondCount'] == 3
    e = pt.NAMED['MergeMaiden']
    for name, f in e['forms'].items():
        assert f['air'] == body_air(name)
        assert f['bodies'] == CARDS[name]['count'] == 1
        assert body_air(f['proxy_body']) == f['air']
        assert f['proxy_body'] == e['body_map'][name]


def test_class_only():
    assert set(pt.CLASS_ONLY) == {'troop', 'building', 'air'}
    for key, e in pt.CLASS_ONLY.items():
        assert e['proxy_body'] in VOCAB['units']
        assert e['proxy_body'] not in set(VOCAB['champion_units']) | {'goblinstein'} | UNSAFE_BODIES.keys()
        assert body_kind(e['proxy_body']) == ('building' if key == 'building' else 'troop')
        assert body_air(e['proxy_body']) == (key == 'air')
        assert e['reveals_card'] is False and e['charge_elixir'] is False
        assert e['cost'] >= 0  # legacy nominal estimate, never a ledger charge


@pytest.mark.parametrize('card,expected', [
    ('ThreeMusketeers', {'Musketeer'}),
    ('Graveyard', {'Skeletons', 'SkeletonArmy'}),
    ('SkeletonBalloon', {'Skeletons', 'SkeletonArmy'}),
    ('SkeletonKing', {'Skeletons', 'SkeletonArmy'}),
    ('Tombstone', {'Skeletons', 'SkeletonArmy'}),
    ('Witch', {'Skeletons', 'SkeletonArmy'}),
    ('RoyalRecruits', {'RoyalDelivery'}),
    ('GoblinDrill', {'Goblins', 'GoblinGang', 'GoblinBarrel'}),
    ('GoblinCurse', {'Goblins', 'GoblinGang', 'GoblinBarrel'}),
    ('SpearGoblins', {'GoblinGang', 'GoblinHut'}),
    ('Barbarians', {'BarbLog'}),
])
def test_visual_families(card, expected):
    assert set(pt.SHARED_BODY[card]) == expected
    # Independent metadata confirms that these cards actually produce bodies;
    # the family equivalences above are visual facts, not proxy equality.
    assert expected_bodies(card)


def test_shared_body_scope_and_dynamic_copies():
    assert set(pt.SHARED_BODY) == set(TARGETS)
    assert all(set(v) <= pt.C56 for v in pt.SHARED_BODY.values())
    assert pt.SHARED_BODY_REVEALS_CARD is False
    for card in ('Clone', 'Mirror'):
        assert pt.NAMED[card]['body_rule'] == 'copy_observed_body'
        assert pt.SHARED_BODY[card] == []  # source families are contextual


@pytest.mark.parametrize('name,expected', [
    ('witch', 'Wizard'), ('WITCH', 'Wizard'), ('Night Witch', 'Knight'),
    ('Heal Spirit', 'ElectroSpirit'), ('Skeleton', 'Skeleton'), ('Skeletons', 'Skeleton'),
    ('Archers', 'Archer'), ('PhoenixNoRespawn', 'Minion'),
    ('GoblinDrillDig', None), ('RageBottle', None), ('ArcherQueen', None),
    ('Miner', None), ('SomeNewTroop', None), ('NotACard', None),
])
def test_canonical_lookup(name, expected):
    assert pt.proxy_body(name) == expected


def test_explicit_fallback_and_form_selection():
    assert pt.proxy_body('SomeNewTroop', kind='troop', air=False) == 'Knight'
    assert pt.proxy_body('SomeNewFlyer', kind='troop', air=True) == 'BabyDragon'
    assert pt.proxy_body('SomeNewBuilding', kind='building') == 'Cannon'
    assert pt.proxy_body('SomeNewSpell', kind='spell') is None
    assert pt.proxy_body('Spirit Empress') is None  # flight required for form
    assert pt.proxy_body('Spirit Empress', air=False) == 'Musketeer'
    assert pt.proxy_body('Spirit Empress', air=True) == 'BabyDragon'
    assert pt.proxy_body('Skeleton') == pt.BODY_ALIASES.get('Skeleton', 'Skeleton')
    assert 'Skeletons' not in pt.BODY_ALIASES


@pytest.mark.parametrize('name', [
    'GiantSkeletonBomb', 'SkeletonContainerNew', 'GoblinDrillDig', 'RageBottle',
    'RageBarbarianBottle', 'PhoenixEgg', 'SpearGoblinGiant',
])
def test_carriers_and_stationary_effects_are_never_fabricated_troops(name):
    assert name in RS['units']  # independent client identity
    assert pt.proxy_body(name, kind='troop', air=True) is None
    for e in pt.NAMED.values():
        if name in e['body_map']:
            assert e['body_map'][name] is None
    assert pt.UNPLACED_BODIES[name]


@pytest.mark.parametrize('card,proxy,body', [
    ('ThreeMusketeers', 'Musketeer', 'Musketeer'),
    ('MegaKnight', 'Valkyrie', 'Valkyrie'),
    ('BattleHealer', 'Valkyrie', 'Valkyrie'),
    ('Fisherman', 'Knight', 'Knight'),
    ('DarkWitch', 'Knight', 'Knight'),
    ('GoblinDemolisher', 'Firecracker', 'Firecracker'),
    ('ElixirGolem', 'Giant', 'Giant'),
    ('ElectroDragon', 'BabyDragon', 'BabyDragon'),
    ('Mortar', 'Xbow', 'Xbow'),
    ('Snowball', 'Zap', ''),
])
def test_reviewed_combat_roles(card, proxy, body):
    assert pt.NAMED[card]['proxy_card'] == proxy
    assert pt.NAMED[card]['proxy_body'] == body


def test_secondary_roles():
    assert pt.NAMED['DarkWitch']['body_map']['Bat'] == 'Bat'
    kamikaze = pt.NAMED['GoblinDemolisher']['body_map']['GoblinDemolisher_kamikaze_form']
    assert RS['units'][kamikaze]['kamikaze']
    for true, proxy in pt.NAMED['ElixirGolem']['body_map'].items():
        assert RS['units'][true]['target_only_buildings']
        assert RS['units'][proxy]['target_only_buildings']


def test_aliases_keep_known_policies_even_with_fallback_requested():
    for name in ('Void', 'Clone', 'Mirror', 'Miner', 'ArcherQueen', 'Goblinstein'):
        assert pt.proxy_body(name, kind='troop') is None
    for name in ('Graveyard_rework_Skeleton', 'SkeletonKingSkeleton', 'skeleton'):
        assert pt.proxy_body(name) == 'Skeleton'
    assert pt.proxy_body('goblin_drill', kind='building') == 'Cannon'


def test_review_r2_regressions():
    from bot.cards.proxy_table import NAMED, CLASS_ONLY, proxy_body, proxy_for_card, UNPLACED_BODIES
    # Ram Rider: the rider is an attached passenger, never a second combat body.
    assert NAMED['RamRider']['body_map']['RamRider'] is None and 'RamRider' in UNPLACED_BODIES
    assert proxy_body('RamRider') is None and proxy_for_card('RamRider') == 'HogRider'
    # Proxies must not invent units or payloads the true card lacks.
    for card in ('Tombstone', 'BarbarianHut', 'GoblinDrill'):
        assert 'GoblinHut_Rework' not in NAMED[card]['body_map'].values()
        assert NAMED[card]['proxy_body'] != 'GoblinHut_Rework'
    assert NAMED['LavaHound']['proxy_body'] != 'Balloon'
    assert NAMED['SuspiciousBush']['proxy_body'] != 'Wallbreaker'
    assert CLASS_ONLY['building']['proxy_body'] == 'Cannon'
    assert 'cost 4' in NAMED['GoblinCage']['why']


def test_review_r3_c56_card_lookup():
    from bot.cards.proxy_table import proxy_for_card, proxy_body
    for card in ('Knight', 'Cannon', 'HogRider', 'BabyDragon', 'Musketeer', 'Skeletons', 'GoblinHut'):
        assert proxy_for_card(card) is not None and proxy_for_card(card) == proxy_body(card), card
    for card in ('Miner', 'ArcherQueen', 'Goblinstein'):  # blocked bodies stay blocked
        assert proxy_for_card(card) is None, card
