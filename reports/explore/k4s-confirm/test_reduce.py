"""PREREG-K4S reducer tests (replaces T1 test_reduce.py). Synthetic trees only."""
import json, subprocess, sys
from fractions import Fraction
from pathlib import Path
import numpy as np
import pytest
import reduce as R
from synthetic import build

HERE = Path(__file__).resolve().parent
MARGINS = dict(A=dict(ref_pp=5, guard_ref_pp=10), B=dict(ref_pp=10, guard_ref_pp=15), veto_pp=5)


def test_exact_bound_matches_numpy_linear():
    rng = np.random.default_rng(0); v = rng.integers(0, 50, size=10000)
    for q in (Fraction(1, 40), Fraction(39, 40)):
        assert abs(float(R.exact_bound(v, q, 100)) - np.percentile(v, float(q)*100)) < 1e-9


def fake(values):
    """stats with every needed contrast's exact upper bound set from `values` (pp); default -20."""
    s = {p: {'contrasts': {}} for p in ('primary', 'guard', 'primary_subsample', 'guard_subsample')}
    def put(pop, key, up):
        f = Fraction(up).limit_denominator(1000)
        s[pop]['contrasts'][key] = dict(exact95=[[-100, 1], [f.numerator, f.denominator]])
    for b in (200, 180, 160, 140, 120):
        put('primary', f'K4S-{b} minus K4-200', values.get(('ref', b), -20)); put('guard', f'K4S-{b} minus K4-200', values.get(('gref', b), -20))
    put('primary', 'K4S-160 minus K4-160', values.get(('same', 160), -20)); put('primary', 'K4S-180 minus K4-180', values.get(('veto',), -20))
    for b in (140, 120): put('primary_subsample', f'K4S-{b} minus K4-{b}', values.get(('same', b), -20))
    return s


def passed(d): return [x['hypothesis'] for x in d['sequence'] if x['passed']]


def test_all_pass_full_sequence():
    d = R.decide(fake({}), 0.9, MARGINS)
    assert passed(d) == ['B(0.8)', 'B(0.7)', 'B(0.6)', 'A(0.9)', 'A(0.8)', 'A(0.7)', 'A(0.6)']
    assert d['admitted'] == {'0.9': 'A', '0.8': 'A', '0.7': 'A', '0.6': 'A'} and d['usable_cells'] == [0.9, 0.8, 0.7, 0.6]


def test_stops_at_first_failure_and_levels():
    # B(0.6) fails on the guard part (> 15): A(0.9) onward is not reached.
    d = R.decide(fake({('gref', 120): 15.5}), 0.9, MARGINS)
    assert passed(d) == ['B(0.8)', 'B(0.7)'] and [x['tested'] for x in d['sequence']] == [True]*3+[False]*4
    assert [x['passed'] for x in d['sequence']] == [True, True, False]+[None]*4
    assert d['admitted'] == {'0.9': None, '0.8': 'B', '0.7': 'B', '0.6': None}


def test_margins_inclusive_sup_strict():
    d = R.decide(fake({('ref', 160): 5, ('gref', 160): 10}), 0.9, MARGINS)
    assert d['admitted']['0.8'] == 'A'
    d = R.decide(fake({('same', 160): 0}), 0.9, MARGINS)
    assert d['sequence'][0]['passed'] is False and d['admitted']['0.8'] is None


def test_c_star_08_drops_h4_and_veto():
    d = R.decide(fake({}), 0.8, MARGINS)
    assert [x['hypothesis'] for x in d['sequence']] == ['B(0.8)', 'B(0.7)', 'B(0.6)', 'A(0.8)', 'A(0.7)', 'A(0.6)']
    assert [x['step'] for x in d['sequence']] == ['H1', 'H2', 'H3', 'H5', 'H6', 'H7']
    assert d['admitted']['0.9'] is None and 0.9 not in d['usable_cells']
    d = R.decide(fake({('veto',): 5.01}), 0.9, MARGINS)
    assert d['admitted']['0.9'] == 'A' and not d['veto_0_9_pass'] and 0.9 not in d['usable_cells']


@pytest.fixture(scope='module')
def tree(tmp_path_factory):
    return build(tmp_path_factory.mktemp('syn')/'t', seed=3, replace={'primary-0005', 'guard-0007', 'primary-0700'})


def test_reducer_end_to_end_synthetic(tree, tmp_path):
    out = tmp_path/'r.json'
    subprocess.run([sys.executable, str(HERE/'reduce.py'), '--root', str(tree), '--synthetic', '--ledger', str(tree/'ledger.json'), '--out', str(out)], check=True)
    r = json.loads(out.read_text())
    assert r['populations']['primary']['n'] == 3000 and r['populations']['guard']['n'] == 900
    assert r['populations']['primary_subsample']['n'] == 600 and r['populations']['guard_subsample']['n'] == 300
    assert len(r['replacements']) == 3 and r['decision']['validity']['inside']


def test_seal_refuses_without_release(tree, tmp_path):
    (tmp_path/'t2').mkdir()
    r = subprocess.run([sys.executable, str(HERE/'reduce.py'), '--root', str(tmp_path/'t2'), '--synthetic', '--out', str(tmp_path/'x.json')])
    assert r.returncode != 0


def test_ledger_replay_rejects_wrong_k_and_non_logical_replaces():
    from schedule import block, replacement
    lost = block('primary', 5); r = replacement(lost, [])
    ok = [dict(lost=lost, replacement=r)]
    assert R.validate_ledger(ok)[0][r['id']] == r and R.validate_ledger(ok)[1] == {'primary-0005': r['id']}
    with pytest.raises(AssertionError): R.validate_ledger([dict(lost=lost, replacement=dict(r, replacement_k=1, index=3055, id='primary-3055', seed=r['seed']+50))])
    r2 = replacement(r, ok)
    assert r2['replaces'] == 'primary-0005'
    with pytest.raises(AssertionError): R.validate_ledger(ok+[dict(lost=r, replacement=dict(r2, replaces='primary-3005'))])
    with pytest.raises(AssertionError): R.validate_ledger(ok+[dict(lost=lost, replacement=r2)])  # same block lost twice


def test_tampered_descriptors_are_rejected(tmp_path):
    import shutil
    t = build(tmp_path/'t', seed=5)
    def tamper(ident, **kw):
        p = t/ident/'complete.json'; proof = json.loads(p.read_text()); orig = json.loads(p.read_text())
        proof['descriptor'].update(kw); p.write_text(json.dumps(proof)); return p, orig
    from schedule import order_for
    for ident, kw in (('primary-0050', dict(rotation=0, order=order_for(0, True))), ('primary-0000', dict(index=1, seed=4503605807370497))):
        p, orig = tamper(ident, **kw)
        r = subprocess.run([sys.executable, str(HERE/'reduce.py'), '--root', str(t), '--synthetic', '--out', str(tmp_path/'x.json')], capture_output=True)
        assert r.returncode != 0 and b'descriptor differs' in r.stderr
        p.write_text(json.dumps(orig))


def test_ledger_rejects_loss_before_allocation():
    from schedule import block, replacement
    lost = block('primary', 3); r0 = replacement(lost, []); r1 = replacement(r0, [dict(lost=lost, replacement=r0)])
    # Event 1 loses the k=1 replacement before event 2 allocates it (Sol verifier r1 finding 3 shape).
    bad = [dict(lost=r1, replacement=dict(r0)), dict(lost=lost, replacement=r1)]
    with pytest.raises(AssertionError): R.validate_ledger(bad)
