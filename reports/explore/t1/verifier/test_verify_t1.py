"""Synthetic-only tests for verify_t1.py. No real T1 outcome is ever read here."""
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_t1 as V  # noqa: E402

DECKS = dict(
    primary=[[f'P{k}{j}' for j in range(8)] for k in range(5)],
    l2=[[f'L{k}{j}' for j in range(8)] for k in range(3)],
    guard=[dict(cards=[f'G{k}{j}' for j in range(8)]) for k in range(3)],
)
P_LOSS = {'K0c-200': .45, 'K0c-160': .79, 'S-200': .30, 'S-160': .33,
          'K2-200': .30, 'K2-160': .34, 'K4-200': .20, 'K4-160': .27}


def matchup(pop, c):
    if pop == 'primary':
        return c % 2, DECKS['primary'][c % 5], DECKS['primary'][(c // 5) % 5]
    opp = DECKS['guard'] if pop == 'guard' else [dict(cards=d) for d in DECKS['l2']]
    return c % 2, DECKS['l2'][(c // 2) % 3], opp[c // 6]['cards']


def descriptor(pop, i, cell=None, replaces=None):
    p = V.POP[pop]
    c = i % p['cells'] if cell is None else cell
    seat, own, opp = matchup(pop, c)
    return dict(id=f'{pop}-{i:04d}', population=pop, index=i, seed=p['base'] + i, cell=c, seat=seat,
                replaces=replaces, order=list(V.ARMS))


def write_block(root, d, outcomes, terminal=True, mutate=None):
    """outcomes: {arm: 'W'|'L'|'D'}"""
    folder = root / d['id']
    (folder / 'games').mkdir(parents=True)
    (folder / 'descriptor.json').write_text(json.dumps(d))
    seat, own, opp = matchup(d['population'], d['cell'])
    shas = {}
    for arm in V.ARMS:
        tier, ms = arm.split('-')
        o = outcomes[arm]
        winner = seat if o == 'W' else (1 - seat) if o == 'L' else None
        m = dict(population=d['population'], cell=d['cell'], seed_index=d['index'], seed=d['seed'], seat=seat,
                 terminal=terminal, winner=winner, arm=arm, opponent='v1-policy',
                 deadline_seconds=V.DEADLINE[int(ms)], threads=V.SPEC[tier]['threads'],
                 kernel=V.SPEC[tier]['kernel'], default_source=V.SPEC[tier]['policy'] + '-if-no-complete-score',
                 own_deck=list(reversed(own)), opponent_deck=list(opp))
        r = dict(cohort=arm, loss=float(o == 'L') if terminal else None, metadata=m)
        if mutate:
            mutate(arm, r)
        name = f"{d['id']}-d27-{arm}.json"
        raw = json.dumps(r).encode()
        (folder / 'games' / name).write_bytes(raw)
        shas[name] = hashlib.sha256(raw).hexdigest()
    (folder / 'complete.json').write_text(json.dumps(dict(descriptor=d, games=shas)))


def draw(rng):
    out = {}
    for arm, p in P_LOSS.items():
        u = rng.random()
        out[arm] = 'L' if u < p else 'D' if u < p + .02 else 'W'
    return out


def build(tmp, pops=('primary', 'guard', 'descriptive'), lost=(), seed=7):
    """lost: list of (pop, index) originals to lose; each gets its cell-preserving replacement."""
    root = tmp / 'reporting'
    root.mkdir()
    (root / 'SYNTHETIC').write_text('synthetic test data\n')
    rng = np.random.default_rng(seed)
    truth = {}
    lost = set(lost)
    k = {}
    for pop in pops:
        for i in range(V.POP[pop]['n']):
            d = descriptor(pop, i)
            o = draw(rng)
            if (pop, i) in lost:
                (root / d['id']).mkdir()
                (root / d['id'] / 'descriptor.json').write_text(json.dumps(d))
                c = d['cell']
                kk = k.get((pop, c), 0)
                k[(pop, c)] = kk + 1
                j = V.POP[pop]['n'] + V.POP[pop]['cells'] * kk + c
                d = descriptor(pop, j, cell=c, replaces=d['id'])
            write_block(root, d, o)
            truth[(pop, d['index'])] = o
    return root, truth


def run(root, **kw):
    args = ['--blocks', str(root)]
    for k, v in kw.items():
        args += [f'--{k.replace("_", "-")}'] + (v if isinstance(v, list) else [str(v)])
    import argparse
    pops = sorted({p.name.split('-')[0] for p in root.iterdir() if p.is_dir()})
    ns = argparse.Namespace(blocks=[str(root)], exits=None, dispatch=None, release=None, repo='.', plan=None,
                            guard_decks=None, cells=None, t1_results=None, t1_indices=None,
                            tolerance_pp=1e-9, out=None, populations=pops)
    for k, v in kw.items():
        setattr(ns, k, v)
    return V.run(ns)


@pytest.fixture(scope='module')
def full(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('full')
    decks = tmp / 'guard-decks.json'
    decks.write_text(json.dumps(DECKS))
    root, truth = build(tmp, lost=[('primary', 7), ('primary', 57), ('guard', 0), ('guard', 5)])
    out, status = run(root, guard_decks=str(decks))
    return root, truth, out, status, decks


# ------------------------------------------------------------ exact arithmetic

def test_exact_quantile_matches_numpy_linear():
    rng = np.random.default_rng(1)
    for _ in range(50):
        x = rng.integers(-300, 300, size=10_000)
        xs = np.sort(x)
        for L in list(V.LEVELS.values()) + [V.V_ROUNDED]:
            a = (1 - L) / 2
            for q in (a, 1 - a):
                assert abs(float(V.exact_quantile(xs, q)) - np.percentile(x, 100 * float(q))) < 1e-9


def test_levels_are_exact_prereg_values():
    assert V.LEVELS['v'] == Fraction(59, 60)  # 1 - 0.05/3
    assert V.LEVELS['ni'] == Fraction(975, 1000) and V.LEVELS['g'] == Fraction(95, 100)


# ------------------------------------------------------------ end to end on synthetic data

def test_full_synthetic_clean_and_integer_counts(full):
    root, truth, out, status, _ = full
    assert out['mode'] == 'synthetic'
    assert not out['errors'], out['errors'][:5]
    for pop, n in (('primary', 2400), ('guard', 600), ('descriptive', 72)):
        for arm in V.ARMS:
            got = out['arms'][pop][arm]
            want = sum(1 for (p, _), o in truth.items() if p == pop and o[arm] == 'L')
            assert (got['n'], got['losses']) == (n, want)
            assert got['draws'] == sum(1 for (p, _), o in truth.items() if p == pop and o[arm] == 'D')
    c = out['contrasts']['primary']['S-200 minus K0c-200']
    want = sum((o['S-200'] == 'L') - (o['K0c-200'] == 'L') for (p, _), o in truth.items() if p == 'primary')
    assert c['point_count_diff'] == want and c['point_pp'] == pytest.approx(100 * want / 2400)
    assert 'intervals' not in out['arms']['descriptive']['K0c-200']  # descriptive never bootstrapped
    assert len([g for g in out['gates'] if g.startswith('V1|')]) == 12
    assert len([g for g in out['gates'] if g.startswith('G2|')]) == 12


def test_replacement_seed_stratified_in_lost_cell(full):
    root, truth, out, *_ = full
    assert ('guard', 600) in truth and ('guard', 605) in truth  # cells 0 and 5, not 600%18=6 / 605%18=11
    d = json.loads((root / 'guard-0600' / 'descriptor.json').read_text())
    assert d['cell'] == 0 and d['replaces'] == 'guard-0000'
    note = next(n for n in out['notes'] if n['code'] == 'REPLACEMENTS' and n['population'] == 'guard')
    assert note['lost_blocks'] == 2 and note['lost_by_cell'] == {0: 1, 5: 1}


def test_t1_comparison_match_and_mismatch(full, tmp_path):
    root, _, out, _, decks = full
    t1 = dict(arms=[dict(population=p, arm=a, **{k: out['arms'][p][a][k] for k in ('n', 'wins', 'losses', 'draws')})
                    for p in ('primary', 'guard') for a in V.ARMS],
              contrasts=[dict(population=p, left=k.split(' minus ')[0], right=k.split(' minus ')[1],
                              point_count_diff=v['point_count_diff'],
                              intervals={lv: list(v['intervals'][lv]['pp']) for lv in ('v', 'ni', 'g')})
                         for p in ('primary', 'guard') for k, v in out['contrasts'][p].items()])
    f = tmp_path / 't1.json'
    f.write_text(json.dumps(t1))
    o, s = run(root, guard_decks=str(decks), t1_results=str(f))
    assert not o['errors']
    t1['arms'][3]['losses'] += 1
    t1['contrasts'][5]['intervals']['ni'][1] += 0.01
    f.write_text(json.dumps(t1))
    o, s = run(root, guard_decks=str(decks), t1_results=str(f))
    codes = {e['code'] for e in o['errors']}
    assert s == 2 and {'MISMATCH_COUNT', 'MISMATCH_INTERVAL'} <= codes


def test_t1_indices_exact_and_validation(full, tmp_path):
    root, _, out, _, decks = full
    rng = np.random.default_rng(V.BOOT_SEED)
    idx = {}
    for pop in V.GATED:
        for c in range(V.POP[pop]['cells']):
            idx[f'{pop}:{c}'] = rng.integers(0, V.cell_size(pop, c), size=(V.REPS, V.cell_size(pop, c)))
    f = tmp_path / 'idx.npz'
    np.savez(f, **idx)
    o, _ = run(root, guard_decks=str(decks), t1_indices=str(f))
    assert o['contrasts'] == out['contrasts']  # canonical order reproduced bit-exactly
    idx['guard:3'] = idx['guard:3'] + 1  # an index escapes its stratum
    np.savez(f, **idx)
    with pytest.raises(SystemExit):
        run(root, guard_decks=str(decks), t1_indices=str(f))


# ------------------------------------------------------------ ledger failures

def test_double_count_completed_but_marked_failed(tmp_path):
    root, truth = build(tmp_path, pops=('guard',), lost=[('guard', 3)])
    # The "lost" block actually completed: write its complete files, as in review B3.
    write_block_dir = root / 'guard-0003'
    import shutil
    shutil.rmtree(write_block_dir)
    write_block(root, descriptor('guard', 3), {a: 'W' for a in V.ARMS})
    out, s = run(root)
    assert s == 2 and any(e['code'] in ('CELL_COUNT', 'ORIGINAL_AND_REPLACEMENT_BOTH_COUNTED') for e in out['errors'])
    ex = tmp_path / 'exits'
    ex.mkdir()
    (ex / 'guard-0003.json').write_text(json.dumps(dict(descriptor=descriptor('guard', 3), complete=False)))
    out, s = run(root, exits=[str(ex)])
    assert not out['errors'] and any(e['code'] == 'COMPLETE_BUT_MARKED_FAILED' for e in out['edges'])


def test_replacement_in_wrong_cell_is_error(tmp_path):
    root, _ = build(tmp_path, pops=('guard',), lost=[('guard', 0)])
    import shutil
    shutil.rmtree(root / 'guard-0600')
    write_block(root, descriptor('guard', 600), {a: 'W' for a in V.ARMS})  # cell 600%18=6: forbidden
    out, s = run(root)
    codes = {e['code'] for e in out['errors']}
    assert s == 2 and 'REPLACEMENT_NOT_CELL_PRESERVING' in codes


def test_nonterminal_game_is_error_never_dropped(tmp_path):
    root, _ = build(tmp_path, pops=('guard',))
    import shutil
    shutil.rmtree(root / 'guard-0010')
    write_block(root, descriptor('guard', 10), {a: 'D' for a in V.ARMS}, terminal=False)
    out, s = run(root)
    assert s == 2 and any(e['code'] == 'NONTERMINAL_GAME' for e in out['errors'])


def test_tampered_game_sha_is_error(tmp_path):
    root, _ = build(tmp_path, pops=('guard',))
    g = next((root / 'guard-0011' / 'games').glob('*K4-200.json'))
    g.write_text(g.read_text() + ' ')
    out, s = run(root)
    assert any(e['code'] in ('GAME_SHA_MISMATCH',) for e in out['errors'])


def test_lost_without_hub_copy_needs_dispatch(tmp_path):
    root, _ = build(tmp_path, pops=('guard',), lost=[('guard', 4)])
    import shutil
    shutil.rmtree(root / 'guard-0004')  # host died: nothing reached the hub
    out, s = run(root)
    assert any(e['code'] == 'ORIGINAL_NEVER_DISPATCHED' for e in out['errors'])
    disp = tmp_path / 'dispatch.json'
    disp.write_text(json.dumps(dict(blocks=[dict(descriptor('guard', 4), dispatch=4, host='127x03')])))
    out, s = run(root, dispatch=[str(disp)])
    assert not out['errors']


def test_wrong_arm_spec_metadata(tmp_path):
    root, _ = build(tmp_path, pops=('guard',))
    import shutil
    shutil.rmtree(root / 'guard-0002')

    def bad(arm, r):
        if arm == 'K4-160':
            r['metadata']['threads'] = 2
    write_block(root, descriptor('guard', 2), {a: 'W' for a in V.ARMS}, mutate=bad)
    out, s = run(root)
    assert any(e['code'] == 'GAME_METADATA' and e['field'] == 'threads' for e in out['errors'])


# ------------------------------------------------------------ seal

def test_sealed_without_marker_or_release(tmp_path):
    root, _ = build(tmp_path, pops=('descriptive',))
    (root / 'SYNTHETIC').unlink()
    with pytest.raises(SystemExit, match='SEALED'):
        run(root)


def test_release_reason_must_be_prereg_path(tmp_path):
    root, _ = build(tmp_path, pops=('descriptive',))
    r = tmp_path / 'r.json'
    r.write_text(json.dumps(dict(coordinator_thread=V.COORDINATOR, authorization_message_id='x',
                                 reason='explicit_coordinator_release')))
    with pytest.raises(SystemExit, match='SEALED'):
        run(root, release=str(r))
    r.write_text(json.dumps(dict(coordinator_thread=V.COORDINATOR, authorization_message_id='x',
                                 reason='fourteen_day_escape', reporting_complete_utc='2026-10-11T00:00:00Z',
                                 authorized_at_utc='2026-10-20T00:00:00Z')))
    with pytest.raises(SystemExit, match='14-day'):
        run(root, release=str(r))


# ------------------------------------------------------------ inclusive-threshold edges

def test_exact_boundary_inclusive_pass_and_flag():
    rep = V.Report()
    n = 2400
    x = np.full(V.REPS, -240, dtype=np.int64)  # every resample exactly -10.0 pp
    e, f = V.interval(x, n, V.LEVELS['v'])
    g = V.gate('V1', e[1], f[1], Fraction(-10), False, n, rep, {})
    assert e[1] == Fraction(-10) and g['passed'] is True
    assert [d['code'] for d in rep.edges] == ['EXACT_BOUNDARY']


def test_g1_strict_at_zero_fails_and_flags():
    rep = V.Report()
    x = np.zeros(V.REPS, dtype=np.int64)
    e, f = V.interval(x, 600, V.LEVELS['g'])
    g = V.gate('G1', e[1], f[1], Fraction(0), True, 600, rep, {})
    assert g['passed'] is False and rep.edges[0]['code'] == 'EXACT_BOUNDARY' and rep.edges[0]['strict']


def test_within_one_count_flag():
    rep = V.Report()
    x = np.full(V.REPS, 121, dtype=np.int64)  # +5.0417 pp at n=2400: one count above +5
    e, f = V.interval(x, 2400, V.LEVELS['ni'])
    g = V.gate('NI', e[1], f[1], Fraction(5), False, 2400, rep, {})
    assert g['passed'] is False and rep.edges[0]['code'] == 'WITHIN_ONE_COUNT_OF_THRESHOLD'


def test_level_rounding_flip_detected():
    # Construct an order statistic layout where 0.9833 and 59/60 straddle -10 pp at n=2400.
    n, thr = 2400, Fraction(-10)
    x = np.full(V.REPS, -270, dtype=np.int64)
    # Upper quantile index h = 9999*q: q=0.99165 -> 9915.508; q=119/120 -> 9915.675.
    x[9916:] = -215  # rounded: -270+.508*55 = -242.0 (pass); exact: -270+.675*55 = -232.9 (fail)
    ex, fl = V.interval(x, n, V.LEVELS['v'])
    er, _ = V.interval(x, n, V.V_ROUNDED)
    rep = V.Report()
    V.gate('V1', ex[1], fl[1], thr, False, n, rep, {}, er[1])
    assert er[1] <= thr < ex[1]
    assert 'LEVEL_ROUNDING_FLIP' in {d['code'] for d in rep.edges}


def test_validity_window_inclusive_edges(tmp_path):
    rep = V.Report()
    assert V.VALIDITY[0] <= Fraction(100 * 864, 2400) <= V.VALIDITY[1]  # exactly 36%
    assert not (V.VALIDITY[0] <= Fraction(100 * 863, 2400))


# ------------------------------------------------------------ §6.5 selection

def gates_with(passing):
    g = {}
    for t in ('S', 'K2', 'K4'):
        for s in (200, 160):
            a = f'{t}-{s}'
            g[f'V2|{a}'] = dict(passed=passing.get(('V2', a), True))
            for s1 in (200, 160):
                c = f'K0c-{s1}'
                g[f'V1|{a}|{c}'] = dict(passed=passing.get(('V1', a), True))
                g[f'G1|{a}|{c}'] = dict(passed=passing.get(('G1', a), True))
    for t, u in (('S', 'K2'), ('S', 'K4'), ('K2', 'K4')):
        for s in (200, 160):
            for su in (200, 160):
                l, r = f'{t}-{s}', f'{u}-{su}'
                g[f'NI|{l}|{r}'] = dict(passed=passing.get(('NI', l, r), False))
                g[f'G2|{l}|{r}'] = dict(passed=passing.get(('G2', l, r), True))
    return g


def test_selection_rule():
    cells = dict(K0c=200, S=200, K2=200, K4=160)
    # No NI anywhere -> most cores in A.
    assert V.select(cells, gates_with({}))['selection'] == 'K4'
    # S NI to K2 and K4 -> S.
    p = {('NI', 'S-200', 'K2-200'): True, ('NI', 'S-200', 'K4-160'): True}
    assert V.select(cells, gates_with(p))['selection'] == 'S'
    # S NI fails against K4 but K2 NI to K4 -> K2.
    p = {('NI', 'S-200', 'K2-200'): True, ('NI', 'K2-200', 'K4-160'): True}
    assert V.select(cells, gates_with(p))['selection'] == 'K2'
    # S passes NI but fails G2 vs K4 -> not S.
    p = {('NI', 'S-200', 'K2-200'): True, ('NI', 'S-200', 'K4-160'): True, ('G2', 'S-200', 'K4-160'): False}
    assert V.select(cells, gates_with(p))['selection'] == 'K4'
    # K4 infeasible on the Mac; S fails V1 -> A={K2} -> K2.
    assert V.select(dict(K0c=None, S=200, K2=160, K4=None), gates_with({('V1', 'S-200'): False}))['selection'] == 'K2'
    # Nothing admissible -> F0; missing K0c cell means 200 ms control.
    r = V.select(dict(K0c=None, S=None, K2=None, K4=None), gates_with({}))
    assert r['selection'] == 'F0' and r['control'] == 'K0c-200'


# ------------------------------------------------------------ cross-check against T1's actual reducer (read-only)

def test_cross_check_against_t1_reduce_on_synthetic(full):
    """Runs T1 reduce.population_stats (imported read-only, no bytecode written) on the same synthetic
    outcomes and requires bit-compatible counts, intervals and gate decisions (except where T1's 0.9833
    level or float path legitimately differs, which must then be FLAGGED, not silently passed)."""
    t1dir = Path(__file__).resolve().parents[1]
    if not (t1dir / 'reduce.py').exists():
        pytest.skip('T1 reducer not present')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(t1dir))
    try:
        import reduce as T1
    finally:
        sys.path.remove(str(t1dir))
    root, truth, out, _, decks = full
    rows = {}
    for pop in ('primary', 'guard'):
        logical = {}
        for p in sorted(root.glob(f'{pop}-*/complete.json')):
            d = json.loads((p.parent / 'descriptor.json').read_text())
            lid = d['replaces'] or d['id']
            o = truth[(pop, d['index'])]
            logical[lid] = dict(id=lid, seed=d['seed'], cell=d['cell'],
                                loss={a: float(o[a] == 'L') for a in V.ARMS},
                                draw={a: o[a] == 'D' for a in V.ARMS}, win={a: o[a] == 'W' for a in V.ARMS})
        rows[pop] = [v for _, v in sorted(logical.items())]
    rng = np.random.default_rng(V.BOOT_SEED)
    t1 = dict(populations={p: T1.population_stats(r, rng, V.REPS) for p, r in rows.items()})
    rep = V.Report()
    V.compare_t1(out, t1, rep, 1e-9)
    codes = {e['code'] for e in rep.errors}
    # Counts, points and every interval agree to 1e-9: identical draws (same logical ordering).
    assert not codes - {'T1_GATE_DECISION_DIFFERS'}, rep.errors[:5]
    # Any gate-decision difference must be explained by the 0.9833 level (V1/V2) or a float boundary.
    for e in rep.errors:
        assert e['gate'].split('|')[0] in ('V1', 'V2', 'NI', 'G1', 'G2')
