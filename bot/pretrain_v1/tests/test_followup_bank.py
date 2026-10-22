"""Fresh bank identity and failure accounting, without loading the simulator or checkpoints."""
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'bot/pretrain_v1'))
import compare_arms as C

spec = importlib.util.spec_from_file_location('followup_bank', ROOT/'reports/bot/pretrain-v1/sweep/make_followup_bank.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def test_disjoint_balanced_banks():
    ref = dict(cases=[dict(id='old', seed=1, row='HOG26-acct', own_levels={'HogRider': 10})],
               exclude=[], corpus_sha256='c', level_table_sha256='l')
    rd = types.SimpleNamespace(OPP_MIX_SPEC='mix', opp_deck=lambda *args: (['Cannon'], 'test'))
    lp = types.SimpleNamespace(dist_levels=lambda *args, **kwargs: {'Cannon': 9})
    first = B.build(10000, ref, {1}, rd, lp, {'king': 9}, lambda x: 'test')
    seen = {c['seed'] for c in first['cases']}
    second = B.build(20000, ref, seen | {1}, rd, lp, {'king': 9}, lambda x: 'test')
    assert not seen.intersection(c['seed'] for c in second['cases'])
    from collections import Counter
    assert set(Counter((c['opponent'], c['seat']) for c in first['cases']).values()) == {400}


def fixture(tmp_path, monkeypatch):
    import hashlib
    original = json.loads((C.E.R2/'evaluation/bank.json').read_text())
    cases = [c for c in original['cases'] if c['row'] == 'HOG26-acct'][:2]
    bank = tmp_path/'bank.json'
    bank.write_text(json.dumps(dict(cases=cases)))
    monkeypatch.setattr(C.E, 'external_identity', lambda: {})
    monkeypatch.setattr(C.E, 'origins_valid', lambda _: (True, None))
    for name in ['a', 'b']:
        p = tmp_path/name
        (p/'rows').mkdir(parents=True)
        man = dict(arm=name, assigned=[c['index'] for c in cases], ckpt_sha256=name*64, bank_path=str(bank),
                   bank_sha256=hashlib.sha256(bank.read_bytes()).hexdigest(), runtime_pins={}, external_sha256={})
        (p/'manifest.json').write_text(json.dumps(man))
        for c in cases:
            row = dict(c, ckpt_sha256=man['ckpt_sha256'], bank_sha256=man['bank_sha256'], runtime_pins={},
                       score=1, result={'terminal': True})
            (p/'rows'/f"{c['index']:04}-{name}.json").write_text(json.dumps(row))
    return cases, bank


def test_custom_bank_missing_and_failed_stay_assigned(tmp_path, monkeypatch):
    cases, _ = fixture(tmp_path, monkeypatch)
    (tmp_path/'a/rows'/f"{cases[0]['index']:04}-a.json").unlink()
    p = tmp_path/'b/rows'/f"{cases[1]['index']:04}-b.json"
    r = json.loads(p.read_text()); r['error'] = 'test interrupted'; p.write_text(json.dumps(r))
    out = tmp_path/'comparison.json'
    C.main(['--a', str(tmp_path/'a'), '--b', str(tmp_path/'b'), '--out', str(out)])
    d = json.loads(out.read_text())
    assert d['assigned'] == 2 and d['a_ran'] == 1 and d['b_ran'] == 2
    assert d['a_failed_or_not_run'] == d['b_failed_or_not_run'] == 1
    assert d['all_assigned_lower']['n'] == 2 and not d['a_wins_by_registered_rule']


def test_changed_bank_refused(tmp_path, monkeypatch):
    _, bank = fixture(tmp_path, monkeypatch)
    bank.write_text(bank.read_text()+'\n')
    import pytest
    with pytest.raises(SystemExit, match='loaded bank differs'):
        C.main(['--a', str(tmp_path/'a'), '--b', str(tmp_path/'b')])
