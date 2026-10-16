"""PROPOSAL: bounded fixture/root diagnosis with the UNCHANGED semantic-v1 rules.

CPU1, after old3586969 terminates and exact script review. No broad sweep.
Observes the exact old scenarios without changing their steps/comparison,
captures constructor/pre/post-first-mismatch roots, then compares eight specific
natural fixtures in both seats. Every mismatch remains FAIL.
"""
import hashlib
import copy
import json
from pathlib import Path
import sys
import traceback

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized execution invalidates collection assertions')

from differential import config, clasher_core
import probe_dash_semantic_v1 as synthetic
import probe_dash_natural_v1 as natural
from snapshot_contract_v1 import VERSION

CASES = [('zap', 1), ('zap', -4), ('freeze', 1), ('log', -4),
         ('ice_spirit', 0), ('electro_dragon', 6), ('magic_archer', 10), ('executioner', 10)]
LEGACY = [('zap',1,0,'state.entities.7.facing[1]'),
          ('electro_dragon',6,14,'state.entities.8.facing[1]'),
          ('ice_spirit',0,23,'state.entities.8.stats.ordinary')]
LEGACY_VALUES = {'zap': (750,1250), 'electro_dragon': (-1000,0), 'ice_spirit': (False,True)}
EXPECTED_NATIVE = '7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff'


def observe_legacy_fixture(module, callback, cfg):
    """Read-only observation of unchanged fixture calls; wrappers preserve all returns/steps."""
    captured = dict(initial_root=None, first_context=None, compared_ticks=0)
    original_factory = module.clasher_core.BattleState
    original_initial, original_compare = module.initial, module.full_compare
    instances = []
    actual_native = None
    before = None

    def factory(raw):
        nonlocal actual_native
        result = original_factory(raw)
        if captured['initial_root'] is None:
            actual_native = result
            captured['initial_root'] = dict(python=json.loads(raw), native=json.loads(result.snapshot()))
        return result

    def initial(*args, **kwargs):
        b = original_initial(*args, **kwargs)
        original_step = b.step
        instances.append((b, original_step))
        def step(*step_args, **step_kwargs):
            nonlocal before
            if actual_native is not None:
                before = dict(python=json.loads(module.probe_snapshot(b, cfg)),
                              native=json.loads(actual_native.snapshot()))
            return original_step(*step_args, **step_kwargs)
        b.step = step
        return b

    def compare(b, native, config):
        result = original_compare(b, native, config)
        equal = native.digest() == module.battle_digest(b)
        if captured['first_context'] is None and (result[0] or not equal):
            assert before is not None
            captured['first_context'] = dict(relative_tick=captured['compared_ticks'],
                before=copy.deepcopy(before), after=dict(python=json.loads(module.probe_snapshot(b,config)),
                                                        native=json.loads(native.snapshot())),
                differences=copy.deepcopy(result[0]), digest_equal=equal)
        captured['compared_ticks'] += 1
        return result
    try:
        module.clasher_core.BattleState = factory
        module.initial, module.full_compare = initial, compare
        captured['result'] = callback()
    finally:
        module.clasher_core.BattleState = original_factory
        module.initial, module.full_compare = original_initial, original_compare
        for b, original_step in instances:
            b.step = original_step
    assert captured['initial_root'] is not None, 'constructor not observed'
    return captured


def legacy_capture(name, lead, seat):
    card, kind, tile = synthetic.CASES[name]
    cards = tuple(dict.fromkeys(('Bandit', card) + synthetic.FILL))[:8]
    cfg = config(cards)
    observed = observe_legacy_fixture(synthetic, lambda: synthetic.one(card,kind,tile,lead,seat,cfg,cards), cfg)
    return dict(case=name,lead=lead,seat=seat,contract=VERSION,
                source_sha256=hashlib.sha256(Path(synthetic.__file__).read_bytes()).hexdigest(),**observed)


def check_collection(legacy, rows):
    expected_legacy = {(name,lead,seat) for name,lead,_,_ in LEGACY for seat in (0,1)}
    assert len(legacy)==len(expected_legacy) and {(r['case'],r['lead'],r['seat']) for r in legacy}==expected_legacy
    for capture in legacy:
        assert 'error' not in capture and capture['initial_root']['python'] and capture['initial_root']['native'], capture
        result,context=capture['result'],capture['first_context']
        assert context and context['before']['python'] and context['before']['native'], capture['case']
        assert context['after']['python'] and context['after']['native'], capture['case']
        assert 'error' not in result and result['cast']['python'] is True
        assert result['cast']['before_export'] or result['cast']['native'] is True
        if capture['seat']==0:
            expected=next(r for r in LEGACY if r[0]==capture['case'])
            assert result['first']==context['relative_tick']==expected[2] and result['field']==expected[3], capture['case']
            values=LEGACY_VALUES[capture['case']]
            assert any(d['field']==expected[3] and d.get('python')==values[0] and d.get('native')==values[1]
                       for d in context['differences']), capture['case']
        if capture['case']=='zap' and capture['seat']==0:
            row=next(r for r in capture['initial_root']['python']['entities'] if r['id']==7)
            assert row['stun']>0 and row['frozen_moving'] is True and row['route'], row
            assert row['dash']['phase']=='travel', row
    expected = {(case, lead, seat) for case, lead in CASES for seat in (0, 1)}
    assert len(rows) == len(expected) and {(r['case'],r['lead'],r['seat']) for r in rows} == expected
    for row in rows:
        assert row['contract'] == VERSION and row['fixture'] == natural.FIXTURE and 'error' not in row, row
        assert 1<=row['compared_ticks']<=45 and row['fresh_troop_templates'] and row['applicability'], row
        assert row['initial_root']['python'] and row['initial_root']['native']
        cast = row['cast']
        assert cast['python'] is True and (cast['before_export'] or cast['native'] is True), row
        reference = row['reference_launch']['before']
        assert reference['charging'] is True and reference['stunned'] is False
        assert reference['target_edge_distance'] is not None and row['reference_launch_tick'] >= 36


def check_results(legacy,rows):
    check_collection(legacy,rows)
    for row in rows:
        assert row['first'] is None and not row['differences'] and row['digest_diverged'] is False, row
        assert row['compared_ticks']==45


if __name__ == '__main__':
    out = Path(sys.argv[1])
    native_sha=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest()
    assert native_sha==EXPECTED_NATIVE, ('unexpected actually imported native',clasher_core.__file__,native_sha)
    legacy, rows = [], []
    for name,lead,_,_ in LEGACY:
        for seat in (0,1):
            try:
                result=legacy_capture(name,lead,seat)
            except Exception:
                result=dict(case=name,lead=lead,seat=seat,error=traceback.format_exc(limit=5))
            legacy.append(result)
    for name, lead in CASES:
        card, kind, tile = synthetic.CASES[name]
        cards = tuple(dict.fromkeys(('Bandit',card)+synthetic.FILL))[:8]
        cfg = config(cards)
        for seat in (0, 1):
            try:
                result = dict(natural.one(card,kind,tile,lead,seat,cfg,cards),case=name,seat=seat)
            except Exception:
                result = dict(contract=VERSION,fixture=natural.FIXTURE,case=name,lead=lead,seat=seat,
                              error=traceback.format_exc(limit=5))
            rows.append(result)
            print(json.dumps({key:result.get(key) for key in ('case','lead','seat','first','field','error','digest_diverged')}),flush=True)
    collection_error=error=None
    try:
        check_collection(legacy,rows)
    except Exception:
        collection_error=traceback.format_exc(limit=4)
    try:
        check_results(legacy,rows)
    except Exception:
        error = traceback.format_exc(limit=4)
    result = dict(contract=VERSION,fixture=natural.FIXTURE,status='CAPTURE_INVALID' if collection_error else 'CAPTURE_COMPLETE',
                  scope='16 natural + six exact legacy continuations/paired roots; not full sweep or engine acceptance',
                  semantic_status='FAIL: six legacy discrepancies retained',
                  natural_comparison_status='FAIL' if error else 'NO_DISCREPANCIES_IN_SELECTED16',
                  execution=dict(native_module=clasher_core.__file__,native_sha256=native_sha,
                                 python=sys.executable,python_version=sys.version,
                                 synthetic_module=synthetic.__file__,natural_module=natural.__file__),
                  collection_status='INVALID' if collection_error else 'COMPLETE',collection_error=collection_error,
                  legacy=legacy,rows=rows,validation_error=error)
    with out.open('x') as final:
        json.dump(result,final,indent=1)
    # Exit0 attests only complete collection; no comparison PASS is manufactured from a subset.
    raise SystemExit(1 if collection_error else 0)
