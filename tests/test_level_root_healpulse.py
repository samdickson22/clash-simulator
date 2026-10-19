"""Static exported Heal payloads through the public-only exact root; no runtime startup."""
import copy
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from bot.levels.configs import LevelConfigs, _qualify
from bot.levels.root import ExactLevelRoot, _templates, public_carrier_identity

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/heal_spirit_pulse_exports.json').read_text())


def exports_at_level(level):
    exports = copy.deepcopy(FIXTURE['base'])
    for path, value in FIXTURE['level_changes'].get(str(level), []):
        target = exports
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = copy.deepcopy(value)
    digest = hashlib.sha256(json.dumps(exports, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert digest == FIXTURE['full_export_sha256'][str(level)]
    return exports


def pulse_at_level(level):
    return exports_at_level(level)['Heal']['tables']['spirit_areas']['Heal']


def resources():
    # Complete actual Heal/BattleHealer exports are decisive: notably both
    # BattleHealer scopes contain kind=Heal, an accidental spirit_areas edge.
    exports = exports_at_level(11)
    cfg = {'cards': {c: e['card'] for c, e in exports.items()}}
    for entry in exports.values():
        for table, entries in entry['tables'].items():
            cfg.setdefault(table, {}).update(entries)
    for card, carrier in FIXTURE['other_carrier_identity_projection'].items():
        cfg['cards'][card] = {'units': [[copy.deepcopy(carrier)], [copy.deepcopy(carrier)]]}
    return SimpleNamespace(config=cfg, builder=SimpleNamespace(token_names=['HealSpirit']),
                           templates={(0, 'AreaEffect'): cfg['spirit_areas']['Heal']})


def make_root(own_level=16, opponent_level=9, seat=0, other_level=16):
    R = resources()
    lc = LevelConfigs.__new__(LevelConfigs)  # in-memory exports only; no cache writes
    lc.R = R

    def entry(card, level):
        if card in FIXTURE['base']:
            e = exports_at_level(level)[card]
        else:
            e = {'card': copy.deepcopy(R.config['cards'][card]), 'tables': {}}
        return _qualify(e, card, level)

    lc.entry = entry
    root = ExactLevelRoot(SimpleNamespace(R=R),
                          {c: own_level if c == 'Heal' else other_level for c in R.config['cards']},
                          lambda c: opponent_level if c == 'Heal' else other_level,
                          11, 11, lc=lc, force=True)
    # Exercise the production level config transform; a fixed JSON writer keeps
    # this unit test independent of native/learned rollout imports in fc_cut.
    cfg, report = lc.mixed(lambda owner, card: root.level(seat, owner, card))
    root._cfg[seat] = (cfg, SimpleNamespace(text=lambda *args: json.dumps(cfg)), report)
    return root


def test_public_identity_preserves_empty_name_carriers_and_all_pulses():
    R = resources()
    pulses = [R.config['spirit_areas']['Heal']] + [
        R.config[t]['BattleHealer'] for t in ('create_areas', 'hit_areas')]
    carriers = [v['units'][0][0] for c, v in R.config['cards'].items() if c not in ('Heal', 'BattleHealer')]
    assert all(e['stats']['name'] == '' for e in pulses + carriers)
    before = copy.deepcopy(pulses + carriers)
    assert [public_carrier_identity(e) for e in pulses] == [
        'HealSpirit', 'BattleHealerSpawnHeal', 'BattleHealerHeal']
    assert [public_carrier_identity(e) for e in carriers] == [e['spell_name'] for e in carriers]
    collected = {}
    _templates(pulses + carriers, collected, 'test')
    assert len(collected) == len(pulses + carriers)
    assert pulses + carriers == before


@pytest.mark.parametrize('seat', [0, 1])
def test_producer_is_heal_with_or_without_deck_evidence(seat):
    root = make_root(seat=seat)
    pulse = root.R.config['spirit_areas']['Heal']
    identity = public_carrier_identity(pulse)
    for deck in (set(), {'Heal'}, {'Heal', 'BattleHealer'}, {'BattleHealer'},
                 set(root.R.config['cards']), {'Arrows', 'Graveyard'}):
        assert root.body_card('', seat, seat, deck, spell=identity) == 'Heal'
    # The approximate global traversal really contains the review's false edge.
    assert root._carriers['HealSpirit'] == ['BattleHealer', 'Heal']
    assert root.carrier_cards('', 'HealSpirit') == ['Heal']
    assert {'Arrows', 'Earthquake', 'Graveyard', 'BarbLog', 'GoblinCurse'} <= set(root.producers()[''])
    # These are genuinely unrelated exact templates: the repair must select
    # Heal, rather than relaxing the existing fail-closed template check.
    assert root.body_delta('Arrows', 16, '', 'HealPulse', 'HealSpirit') is None
    with pytest.raises(ValueError, match='unknown public spell carrier'):
        root.body_card('', seat, seat, set(), spell='UnknownPulse')


@pytest.mark.parametrize('seat', [0, 1])
@pytest.mark.parametrize('heal_in_deck', [False, True])
@pytest.mark.parametrize('other_level', [11, 16])
@pytest.mark.parametrize('levels', [(16, 16), (9, 16), (16, 9), (11, 16), (16, 11)])
def test_public_root_pulses_use_each_owners_exact_export(seat, levels, other_level, heal_in_deck):
    root = make_root(*levels, seat=seat, other_level=other_level)
    rows = np.zeros((2, 32), dtype=np.float32)
    rows[:, 0:2] = (0.25, 0.5)
    rows[:, 7] = 1  # public AreaEffect kind; static template's class is HealPulse
    rows[:, 9] = 1
    rows[:, 28] = 1
    rows[0, 2] = 1  # own row, followed by opponent row
    obs = SimpleNamespace(entity_ids=np.zeros(2, dtype=np.int32),
                          entity_mask=np.ones(2, dtype=bool), entity_features=rows,
                          global_features=np.zeros(18, dtype=np.float32))
    player = {'hand': ['Heal', 'Arrows', 'Earthquake', 'Graveyard'],
              'cycle': ['BarbLog', 'GoblinCurse', 'BattleHealer']}
    if not heal_in_deck:
        player['hand'].remove('Heal')
    info = SimpleNamespace(seat=seat, tick=20, own=copy.deepcopy(player),
                           packet=SimpleNamespace(observation=obs))
    payload = json.loads(root.payload(info, copy.deepcopy(player), np.random.default_rng(7)))
    for e, level, owner in zip(payload['entities'], levels, (seat, 1-seat)):
        expected = pulse_at_level(level)
        assert e['owner'] == owner
        assert e['stats'] == expected['stats']
        assert e['scope'] == expected['scope']
        assert e['scope']['heal_per_tick'] == {9: 83, 11: 100, 16: 160}[level]
        assert e['scope']['heal_interval'] == 0.25
        assert (e['effect_radius'], e['effect_duration']) == (2.5, 1.0)
        assert e['public_identity'] == expected['public_identity']
        assert 'spell_name' not in e  # public identity is not mechanical cast provenance
        key = 'Heal' if level == 11 else f'level{level}:Heal'
        assert payload['config']['spirit_areas'][key]['scope'] == expected['scope']
    assert root.stats['unmapped'] == 0


@pytest.mark.parametrize('level', [9, 11, 16])
@pytest.mark.parametrize('table', ['create_areas', 'hit_areas'])
def test_complete_battle_healer_exports_keep_their_own_exact_pulses(level, table):
    root = make_root(other_level=level)
    base = FIXTURE['base']['BattleHealer']['tables'][table]['BattleHealer']
    assert base['scope']['kind'] == 'Heal'  # the actual accidental traversal edge
    identity = public_carrier_identity(base)
    for deck in (set(), {'Heal'}, {'BattleHealer'}, {'Heal', 'BattleHealer'}):
        assert root.body_card('', 0, 0, deck, spell=identity) == 'BattleHealer'
    sd, td = root.body_delta('BattleHealer', level, '', 'HealPulse', identity)
    restored = copy.deepcopy(base)
    restored['stats'].update(sd)
    restored.update(td)
    expected = exports_at_level(level)['BattleHealer']['tables'][table]['BattleHealer']
    assert restored['stats'] == expected['stats']
    assert restored['scope'] == expected['scope']


@pytest.mark.parametrize('other_level', [11, 16])
def test_false_transitive_candidate_cannot_substitute_for_missing_exact_export(other_level):
    root = make_root(other_level=other_level)
    entry = root.lc.entry
    root.lc.entry = lambda card, level: None if card == 'Heal' else entry(card, level)
    with pytest.raises(ValueError, match='unknown public spell carrier HealSpirit'):
        root.body_card('', 0, 0, {'Heal', 'BattleHealer'}, spell='HealSpirit')
