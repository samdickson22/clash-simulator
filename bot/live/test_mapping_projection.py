"""Canonical observations, separate capability projection, and body-constrained default tracker.

Run with exact archived runtime r1-total, single-thread BLAS, nice19, CPUs2-3.
The original 5361/4863 sources are preserved alongside this isolated package.
"""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from bot.live.translate import LiveTranslator, OBSERVATION_CONTRACT

OWN = ['Knight', 'Archers', 'Giant', 'Musketeer', 'MiniPekka', 'Fireball', 'Arrows', 'Goblins']


@pytest.fixture(scope='module')
def rt():
    from bot.players.runtime import Runtime
    return Runtime()


@pytest.fixture(autouse=True)
def clean_policy(monkeypatch):
    monkeypatch.delenv('CLASHER_LIVE_LEGACY_MAPPING_COMPAT', raising=False)


def unit(body='Knight', card='Knight', **kw):
    return dict(cls=body, card=card, owner=1, kind='troop', x=4.5, y=24., hp_frac=.7, score=.9,
                observation_contract=OBSERVATION_CONTRACT, body_resolution='resolved',
                rawdetector=dict(name='raw-name', class_idx=17, p_team=.91, variant='base'), **kw)


def frame(units, tick=100):
    return dict(tick=tick, units=units, elixir=5., hand=dict(cards=OWN[:4], next=OWN[4]), events=[])


def body_names(tr, assigned):
    return [None if b is None else tr.builder.token_names[b[0]] for b, _ in assigned]


@pytest.mark.parametrize('body,card', [('Golemite', 'Golem'), ('RascalBoy', 'Rascals'),
                                     ('RascalGirl', 'Rascals'), ('SpearGoblin', 'GoblinGang')])
def test_observed_body_survives_default_assign_tracking_and_cluster_close(rt, body, card):
    tr = LiveTranslator(rt, OWN)
    original = frame([unit(body, card)])
    before = copy.deepcopy(original)
    all_plays = []
    for tick in range(100, 123, 2):
        rec = dict(original, tick=tick)
        got, plays = tr.assign(rec)
        assert body_names(tr, got) == [body]
        all_plays += plays
        assert all(t.body == t.body_constraint for t in tr.tracker.live)
    assert original == before
    if body == 'Golemite':
        assert all_plays == []      # orphan descendant is not a parent deployment


@pytest.mark.parametrize('body,card', [('Barbarian', 'Barbarians'), ('SpearGoblin', 'SpearGoblins'),
                                     ('PhoenixEgg', 'Phoenix'), ('GoblinBrawler', 'GoblinCage'),
                                     ('DeliveryRecruit', 'RoyalDelivery')])
def test_unsupported_canonical_family_is_unplaced_even_if_body_token_exists(rt, body, card):
    tr = LiveTranslator(rt, OWN)
    got, plays = tr.assign(frame([unit(body, card)]))
    assert got == [(None, (0., 0.))] and plays == []
    assert tr.last_projections[0]['disposition'] == 'unplaced'
    assert not tr.tracker.live and not tr.tracker.history


def test_explicit_legacy_projection_preserves_observation_and_backend_play_behavior(rt):
    proxy = dict(body='Knight', card='Knight', origin='pinned-classes-mapping')
    u = unit('Barbarian', 'Barbarians', legacy_backend_proxy=proxy)
    original = copy.deepcopy(u)
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    legacy = LiveTranslator(rt, OWN)
    source = []
    for tick in range(100, 125, 2):
        got, plays = tr.assign(frame([u], tick))
        old, old_plays = legacy.assign(frame([dict(cls='Knight', card='Knight', owner=1,
                                                 x=4.5, y=24., score=.9)], tick))
        assert got == old and plays == old_plays
        source += tr.last_play_projections
    assert u == original
    assert len(source) == 1 and source[0]['backend_card'] == 'Knight'
    observed = source[0]['sources'][0]
    assert observed['observed_body'] == 'Barbarian' and observed['observed_family'] == 'Barbarians'
    assert observed['disposition'] == 'legacy_proxy' and observed['rawdetector'] == u['rawdetector']
    assert all(t.hint is None for t in tr.tracker.live) and 'spawn_card' not in u
    disabled = LiveTranslator(rt, OWN)
    assert disabled.assign(frame([u]))[0] == [(None, (0., 0.))]
    assert disabled.unknown_card == 'drop' == tr.unknown_card


@pytest.mark.parametrize('proxy,reason', [
    (dict(body='Cannon', card='Cannon', origin='pinned'), 'invalid_proxy_card_body_or_kind'),
    (dict(body='Barbarian', card='Barbarians', origin='pinned'), 'invalid_proxy_card_body_or_kind'),
    (dict(body='Knight', card='RoyalDelivery', origin='pinned'), 'invalid_proxy_card_body_or_kind'),
    (dict(body='Knight', card='Knight'), 'missing_proxy_origin')])
def test_incompatible_proxy_never_invents_entity_or_play(rt, proxy, reason):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    got, plays = tr.assign(frame([unit('Barbarian', 'Barbarians', legacy_backend_proxy=proxy)]))
    assert got == [(None, (0., 0.))] and not plays
    assert tr.last_projections[0]['reason'] == reason
    assert tr.stats[f'projection:unplaced:{reason}'] == 1


def test_unresolved_body_stays_unplaced_even_with_proxy(rt):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    u = unit('unresolved-raw', 'Barbarians', legacy_backend_proxy=dict(body='Knight', card='Knight', origin='pinned'))
    u['body_resolution'] = 'unresolved'
    got, plays = tr.assign(frame([u]))
    assert got == [(None, (0., 0.))] and not plays
    assert tr.last_projections[0]['reason'] == 'unresolved_observed_body'


def test_unknown_contract_never_falls_back_to_legacy_card_only_assignment(rt):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    u = unit('Golemite', 'Golem')
    u['observation_contract'] = 'canonical-body-v999'
    got, plays = tr.assign(frame([u, unit('RascalBoy', 'Rascals')]))
    assert got[0][0] is None and body_names(tr, got)[1] == 'RascalBoy'
    assert tr.last_projections[0]['reason'] == 'unsupported_observation_contract'
    assert plays == []


def test_launch_env_and_explicit_constructor_override(rt, monkeypatch):
    monkeypatch.setenv('CLASHER_LIVE_LEGACY_MAPPING_COMPAT', 'v1')
    assert LiveTranslator(rt, OWN).legacy_mapping_compat == 'v1'
    assert LiveTranslator(rt, OWN, legacy_mapping_compat=None).legacy_mapping_compat is None
    monkeypatch.setenv('CLASHER_LIVE_LEGACY_MAPPING_COMPAT', 'anything')
    with pytest.raises(ValueError, match='legacy_mapping_compat'):
        LiveTranslator(rt, OWN)


@pytest.mark.parametrize('card_level', [True, False])
def test_information_never_mutates_canonical_observation_and_preserves_body(rt, card_level):
    tr = LiveTranslator(rt, OWN, card_level=card_level)
    rec = frame([unit('RascalBoy', 'Rascals')])
    before = copy.deepcopy(rec)
    info = tr.information(rec)
    assert rec == before
    obs = info.packet.observation
    names = [tr.builder.token_names[int(obs.entity_ids[i])] for i in np.flatnonzero(obs.entity_mask)]
    assert 'RascalBoy' in names and 'RascalGirl' not in names


def test_child_body_cannot_continue_parent_track_or_invent_parent_play(rt):
    tr = LiveTranslator(rt, OWN)
    for tick in range(100, 113, 2):
        tr.assign(frame([unit('Golem', 'Golem')], tick))
    prior = list(tr.tracker.history)
    for tick in range(114, 137, 2):
        got, plays = tr.assign(frame([unit('Golemite', 'Golem')], tick))
        assert body_names(tr, got) == ['Golemite'] and plays == []
    assert tr.tracker.history == prior
    child = next(t for t in tr.tracker.live if tr.builder.token_names[t.body[0]] == 'Golemite')
    assert not child.main and child.state == 'child'
    snap = tr.tracker.snapshot()
    resolved = tr.tracker.resolve([('Golem', 1, 4.5, 24., .9, None, child.body)], 138)
    assert resolved[0].body == child.body
    tr.tracker.restore(snap)
    assert next(t for t in tr.tracker.live if t.id == child.id).body_constraint == child.body


def test_legacy_unmarked_tracker_path_is_exactly_original_4863(rt):
    from bot.live.births import CardBodies, UnitTracker
    path = Path(__file__).resolve().parents[3] / 'base/bot/live/births.py'
    spec = importlib.util.spec_from_file_location('original_4863', path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    a, b = UnitTracker(CardBodies(rt)), original.UnitTracker(original.CardBodies(rt))
    for tick in range(100, 180, 2):
        units = [('Golem', 1, 4.5, 24., .9), ('Rascals', 1, 9., 24., .8),
                 ('SkeletonArmy', 0, 4.5, 8., .9), ('SkeletonArmy', 0, 5.2, 8., .9)]
        assert a.update(tick, units, {'left': True, 'right': True}) == b.update(tick, units, {'left': True, 'right': True})
        assert a.history == b.history and a.stats == b.stats


def test_frozen_adapter_all_names_both_owners_into_default_consumer(rt):
    """Exercise the actual frozen adapter's step(), not manually canonicalized test rows."""
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location('frozen_canonical_adapter', root / 'inputs/yolo_units.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    mapping = json.loads((root / 'inputs/classes.json').read_text())
    y = object.__new__(adapter.YoloUnits)
    y.cls, y.class_list, y.map = adapter.load_mapping(mapping)
    y.observation_contract = mapping['observation_contract']
    y.ground = lambda d: (4.5, 24.)
    counts = dict(named=0, resolved=0, unresolved=0, exact=0, legacy_proxy=0, unplaced=0)
    audit = []
    for entry in mapping['names']:
        for owner in (0, 1):
            d = dict(name=entry['name'], class_idx=entry['idx'], team=owner,
                     p_team=.09 if owner == 0 else .91, score=.9)
            y.detections = lambda image, d=d: [d]
            dec = y.step(None)
            assert dec['unknown_units'] == []
            if not dec['units']:
                assert not y.is_unit(entry['name'])
                continue
            u = dec['units'][0]
            before = copy.deepcopy(dec)
            tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
            got, plays = tr.assign(frame(dec['units']))
            p = tr.last_projections[0]
            assert dec == before and u['card'] == entry.get('card')
            assert u['owner'] == owner and (u['x'], u['y']) == (4.5, 24.)
            assert u['rawdetector']['class_idx'] == entry['idx']
            assert u['rawdetector']['p_team'] == d['p_team'] and 'spawn_card' not in u
            assert plays == []          # one capture cannot create a deployment
            counts['named'] += 1
            counts[u['body_resolution']] += 1
            counts[p['disposition']] += 1
            if u['body_resolution'] == 'unresolved':
                assert got[0][0] is None and p['reason'] == 'unresolved_observed_body'
            elif got[0][0] is not None:
                assert got[0][0] == p['backend_body']
                assert got[0][0][1] == {'troop': 0, 'building': 1}[u['kind']]
            audit.append(dict(name=entry['name'], owner=owner, observed_body=u['cls'],
                              family=u['card'], disposition=p['disposition'], reason=p['reason']))
    assert len(mapping['names']) == 156
    assert counts['resolved'] == 91 * 2 and counts['unresolved'] == 27 * 2
    (root / 'all-mapping-consumer-audit.json').write_text(json.dumps(dict(counts=counts, rows=audit), indent=2) + '\n')


def test_compatibility_keeps_public_play_cost_and_cycle_and_separate_observed_source(rt):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    old = LiveTranslator(rt, OWN)
    for tick in range(100, 125, 2):
        canonical = frame([unit('Barbarian', 'Barbarians',
                                legacy_backend_proxy=dict(body='Knight', card='Knight', origin='pinned'))], tick)
        baseline = frame([dict(cls='Knight', card='Knight', owner=1, x=4.5, y=24., hp_frac=.7, score=.9)], tick)
        a, b = tr.information(canonical), old.information(baseline)
        assert tr.plays == old.plays and tr.public_events == old.public_events
        assert list(a.events) == list(b.events)
        assert tr._mirrors[1].queue == old._mirrors[1].queue
        assert tr._mirrors[1].revealed == old._mirrors[1].revealed
    assert len(tr.public_events) == 1 and tr.public_events[0]['name'] == 'Knight'
    assert sum(rt.R.costs[e['name']] for e in tr.public_events) == 3.
    assert tr.derived_play_projections[0]['sources'][0]['observed_family'] == 'Barbarians'


@pytest.mark.parametrize('body,card,kind,expected', [
    ('Goblin', 'Goblins', 'troop', 'Goblin_Stab'),
    ('GoblinHut', 'GoblinHut', 'building', 'GoblinHut_Rework'),
    ('SpearGoblin', 'GoblinGang', 'troop', 'SpearGoblin')])
def test_reviewed_body_alias_and_kind_template_intersection(rt, body, card, kind, expected):
    tr = LiveTranslator(rt, OWN)
    u = unit(body, card)
    u['kind'] = kind
    original = copy.deepcopy(u)
    got, plays = tr.assign(frame([u]))
    assert body_names(tr, got) == [expected] and plays == []
    assert u == original and tr.last_projections[0]['disposition'] == 'exact'
    assert tr.projection_policy['engine_body_aliases_sha256'] == '3793a3c24d8336bc13308bfef9890a01dcec9748cd5475b9d6192fa78a2cf1bc'


def test_body_alias_does_not_turn_spear_body_into_melee_or_enable_unsupported_card(rt):
    tr = LiveTranslator(rt, OWN)
    for body, card, kind in [('SpearGoblin', 'Goblins', 'troop'), ('Goblin', 'SpearGoblins', 'troop'),
                             ('Goblin', 'Goblins', 'building')]:
        u = unit(body, card)
        u['kind'] = kind
        got, plays = tr.assign(frame([u]))
        assert got[0][0] is None and plays == []


def test_every_verified_frozen_legacy_proxy_preserves_board_play_cost_and_cycle(rt):
    root = Path(__file__).resolve().parents[3]
    mapping = json.loads((root / 'inputs/classes.json').read_text())
    verified = []
    for e in mapping['names']:
        if e.get('body_resolution') != 'resolved' or not e.get('legacy_backend_proxy'):
            continue
        proxy = e['legacy_backend_proxy']
        tr, old = LiveTranslator(rt, OWN, legacy_mapping_compat='v1'), LiveTranslator(rt, OWN)
        u = unit(e['observed_body'], e['card'], legacy_backend_proxy=proxy)
        u['kind'] = e['kind']
        if tr.project_unit(u)['disposition'] != 'legacy_proxy':
            continue                      # invalid same-kind/cfg projection remains explicitly unplaced
        before = copy.deepcopy(u)
        for tick in range(100, 125, 2):
            a = tr.information(frame([u], tick))
            b = old.information(frame([dict(cls=proxy['body'], card=proxy['card'], owner=1,
                                            x=4.5, y=24., hp_frac=.7, score=.9)], tick))
            ao, bo = a.packet.observation, b.packet.observation
            np.testing.assert_array_equal(ao.entity_ids, bo.entity_ids)
            np.testing.assert_array_equal(ao.entity_mask, bo.entity_mask)
            np.testing.assert_allclose(ao.entity_features, bo.entity_features, rtol=0, atol=0)
            assert tr.public_events == old.public_events and tr.plays == old.plays
            assert tr._mirrors[1].queue == old._mirrors[1].queue
            assert tr._mirrors[1].revealed == old._mirrors[1].revealed
        assert u == before
        assert sum(rt.R.costs[x['name']] for x in tr.public_events) == sum(rt.R.costs[x['name']] for x in old.public_events)
        assert all(t.hint is None for t in tr.tracker.live)
        verified.append(e['name'])
    assert len(verified) >= 20
    (root / 'all-verified-proxy-equivalence.json').write_text(json.dumps(dict(names=verified, count=len(verified),
        board=True, plays=True, costs=True, cycle=True, synthesized_spawn_card=False), indent=2) + '\n')
