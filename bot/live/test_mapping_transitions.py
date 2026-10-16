"""Model-free full-flow differentials against both original adapters/consumers.

The originals are hash-checked fixtures, never the new consumer in legacy mode.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest

from bot.live.translate import LiveTranslator
from bot.live.test_mapping_projection import rt, clean_policy, unit, frame, OWN, body_names

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def originals():
    paths = {'translate.py': '5361deb0dbe166fd751bbb3ed3d7a710acc23cc6cbd36cb8eaaee5eb1d9458d8',
             'births.py': '48636f630a0ba1a7567a3f383bfcbca3aeba97418b917e278aa621dd6e8fd227'}
    for name, digest in paths.items():
        assert hashlib.sha256((ROOT / 'base/bot/live' / name).read_bytes()).hexdigest() == digest
    helper = ROOT / 'base/bot/players/royalesim_translate.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '96229925be51b54ae330f0711082198dae997f0031189988125bbeb00de1bf36'
    # The combined candidate has a new shared helper. Bind the baseline class
    # to the actual old helper as well as both original consumer sources.
    old_helper = load('transition_original_shared_helper', helper)
    current = sys.modules['bot.players.royalesim_translate']
    sys.modules['bot.players.royalesim_translate'] = old_helper
    try:
        old = load('transition_original_translate', ROOT / 'base/bot/live/translate.py')
    finally:
        sys.modules['bot.players.royalesim_translate'] = current
    assert old.Translator is old_helper.Translator
    return old, load('transition_original_births', ROOT / 'base/bot/live/births.py')


@pytest.fixture
def adapters(monkeypatch):
    # Execute only the exact deployed helper functions; no vision model imports.
    def function(path, name):
        node = next(n for n in ast.parse(path.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        ns = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
        return ns[name]
    vision = types.ModuleType('clasher.vision.l1_v4')
    vision.body_action = function(ROOT / 'inputs/legacy_l1_v4.py', 'body_action')
    common = types.ModuleType('common')
    common.body_card = function(ROOT / 'inputs/legacy_common.py', 'body_card')
    monkeypatch.setitem(sys.modules, vision.__name__, vision)
    monkeypatch.setitem(sys.modules, 'common', common)
    models = []
    for tag, source, mapping in [
            ('new', ROOT / 'inputs/yolo_units.py', ROOT / 'inputs/classes.json'),
            ('old', ROOT / 'rollback/live/perception/yolo_units.py', ROOT / 'rollback/yolo/classes.json')]:
        mod = load('transition_adapter_' + tag, source)
        m = object.__new__(mod.YoloUnits)
        m.cls, m.class_list, m.map = mod.load_mapping(mapping)
        m.observation_contract = m.map.get('observation_contract')
        models.append(m)
    return models


def pair(rt, originals, monkeypatch):
    new = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    ot, ob = originals
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, 'bot.live.births', ob)
        # Use the actual attested host vocabulary, not the newly completed one.
        old = ot.LiveTranslator(rt, OWN, vocab=json.loads((ROOT / 'base/bot/players/royalesim_vocab.json').read_text()))
    assert old.tracker.__class__ is ob.UnitTracker
    return new, old


def record_pair(adapters, name, tick, owner, bodies=1):
    out = []
    for m in adapters:
        ds = [dict(name=name, class_idx=m.cls[name]['idx'], team=owner,
                   p_team=.91 if owner else .09, score=.9,
                   x=4.5 + .8 * i + .002 * (tick - 100)) for i in range(bodies)]
        m.detections = lambda image, ds=ds: copy.deepcopy(ds)
        m.ground = lambda d: (d['x'], 24. if owner else 8.)
        out.append(frame(m.step(None)['units'], tick))
    return out


def assert_public_equal(new, old, ni, oi, rt):
    a, b = ni.packet.observation, oi.packet.observation
    np.testing.assert_array_equal(a.entity_ids, b.entity_ids)
    np.testing.assert_array_equal(a.entity_mask, b.entity_mask)
    np.testing.assert_allclose(a.entity_features, b.entity_features, rtol=0, atol=0)
    assert new.plays == old.plays and new.public_events == old.public_events
    assert new.derived_plays == old.derived_plays and list(ni.events) == list(oi.events)
    assert ni.own == oi.own
    for owner in (0, 1):
        assert new._mirrors[owner].queue == old._mirrors[owner].queue
        assert new._mirrors[owner].revealed == old._mirrors[owner].revealed
        assert sum(rt.R.costs[e['name']] for e in new.public_events if e['seat'] == owner) == sum(
            rt.R.costs[e['name']] for e in old.public_events if e['seat'] == owner)


def test_review_R1_original_source_transition(rt, originals, adapters, monkeypatch):
    new, old = pair(rt, originals, monkeypatch)
    for tick in range(100, 113, 2):
        nr, oldr = record_pair(adapters, 'barbarian' if tick == 100 else 'hunter', tick, 1)
        ni, oi = new.information(nr), old.information(oldr)
        assert_public_equal(new, old, ni, oi, rt)


@pytest.mark.parametrize('names', [('barbarian', 'hunter'), ('hunter', 'barbarian')])
@pytest.mark.parametrize('owner', [0, 1])
@pytest.mark.parametrize('gap', ['none', 'capture', 'revival'])
@pytest.mark.parametrize('switch', [102, 114])
@pytest.mark.parametrize('bodies', [1, 3])
def test_original_source_proxy_transition_full_board_play_cost_cycle(
        rt, originals, adapters, monkeypatch, names, owner, gap, switch, bodies):
    new, old = pair(rt, originals, monkeypatch)
    rows = []
    end = switch + 75 if gap == 'revival' else 127
    for tick in range(100, end, 2):
        nr, oldr = record_pair(adapters, names[int(tick >= switch)], tick, owner, bodies)
        if (gap == 'capture' and tick == switch + 2 or
                gap == 'revival' and switch + 2 <= tick <= switch + 48):
            nr['units'] = oldr['units'] = []
        before = copy.deepcopy(nr)
        ni, oi = new.information(nr), old.information(oldr)
        assert nr == before
        assert_public_equal(new, old, ni, oi, rt)
        for p in new.last_projections:
            assert p['disposition'] == 'legacy_proxy'
            assert p['tracking_semantics'] == 'legacy_mapping_compat_v1'
            assert p['body_constraint'] is None
            assert p['requested_proxy_body'] == p['backend_body']
            assert p['requested_proxy_card'] == p['backend_card']
            assert p['effective_assigned_body'] is not None
            assert p['effective_track_id'] is not None
        rows.append(dict(tick=tick, projections=copy.deepcopy(new.last_projections),
                         public_events=copy.deepcopy(new.public_events), plays=copy.deepcopy(new.plays)))
    if names == ('barbarian', 'hunter') and owner == 1 and gap == 'none' and switch == 102 and bodies == 1:
        at102 = next(r for r in rows if r['tick'] == 102)['projections'][0]
        assert at102['backend_body'] != at102['effective_assigned_body']
        assert new.builder.token_names[at102['effective_assigned_body'][0]] == 'Knight'
        at110 = next(r for r in rows if r['tick'] == 110)
        assert at110['public_events'][0]['name'] == 'Musketeer'
        assert at110['public_events'][0]['tick'] == 108
        (ROOT / 'original-source-barbarian-hunter-transition.json').write_text(
            json.dumps(dict(original_translate=originals[0].__file__, original_births=originals[1].__file__,
                            rows=rows), indent=2) + '\n')


def test_all_verified_proxies_against_exact_original_sources(rt, originals, adapters, monkeypatch):
    verified = []
    for entry in adapters[0].map['names']:
        if entry.get('body_resolution') != 'resolved' or not entry.get('legacy_backend_proxy'):
            continue
        new, old = pair(rt, originals, monkeypatch)
        probe, _ = record_pair(adapters, entry['name'], 100, 1)
        if new.project_unit(probe['units'][0])['disposition'] != 'legacy_proxy':
            continue
        for tick in range(100, 127, 2):
            nr, oldr = record_pair(adapters, entry['name'], tick, 1, bodies=3)
            if tick == 104:
                nr['units'] = oldr['units'] = []
            before = copy.deepcopy(nr)
            ni, oi = new.information(nr), old.information(oldr)
            assert_public_equal(new, old, ni, oi, rt)
            assert nr == before
        verified.append(entry['name'])
    assert len(verified) == 42
    (ROOT / 'original-source-all-proxy-equivalence.json').write_text(json.dumps(
        dict(names=verified, count=len(verified), original_translate=originals[0].__file__,
             original_births=originals[1].__file__, bodies=3, missed_capture=True,
             board=True, plays=True, costs=True, cycle=True), indent=2) + '\n')


@pytest.mark.parametrize('body', [None, '', '   ', 123, [], {}])
@pytest.mark.parametrize('card_level', [True, False])
def test_malformed_resolved_body_cannot_borrow_valid_proxy(rt, body, card_level):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1', card_level=card_level)
    u = unit(body, 'Barbarians', legacy_backend_proxy=dict(body='Knight', card='Knight', origin='pinned'))
    before = copy.deepcopy(u)
    info = tr.information(frame([u]))
    obs = info.packet.observation
    assert u == before and tr.body('Knight')[0] not in obs.entity_ids[obs.entity_mask]
    assert not tr.tracker.live and not tr.public_events
    assert tr.last_projections[0]['reason'] == 'invalid_observed_body'


def test_proxy_relabel_cannot_change_an_exact_body_track(rt):
    tr = LiveTranslator(rt, OWN, legacy_mapping_compat='v1')
    tr.assign(frame([unit('RascalBoy', 'Rascals')]))
    exact = tr.tracker.live[0]
    proxy = unit('Barbarian', 'Barbarians',
                 legacy_backend_proxy=dict(body='Knight', card='Knight', origin='pinned'))
    got, _ = tr.assign(frame([proxy], 102))
    assert tr.tracker.last_tracks[0] != exact.id
    assert exact.body == exact.body_constraint
    assert tr.builder.token_names[exact.body[0]] == 'RascalBoy'
    assert body_names(tr, got) == ['Knight']
