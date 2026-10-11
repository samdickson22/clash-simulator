"""PREREG-K4S reducer (r3 §5, §1.2, §1.5; K4S-SPEC.md §6). Outcomes inaccessible without coordinator release.

Author: K4S prep worker (Opus). The independent integer-count verifier (verifier/verify_k4s.py) has a
different author and was written from K4S-SPEC.md and r3 without reading this file.

Order of operations: release check (or SYNTHETIC tree) -> block ledger -> integer loss matrix ->
stratified paired bootstrap (one RNG, analyses primary, guard, primary subsample, guard subsample)
-> exact rational percentile bounds -> fixed sequence H1..H7 -> admitted levels, veto, usable cells,
validity -> descriptive secondaries on separate RNG streams.
"""
import argparse, collections, json
from fractions import Fraction
from pathlib import Path
import numpy as np
from common import plan, read, write, sha, utc, ROOT
from schedule import CORE, SUBSAMPLE, ARMS, COUNTS, CELLS, SUB_LIMIT, expected_order

CELL_ARM = {1.0: 200, 0.9: 180, 0.8: 160, 0.7: 140, 0.6: 120}
Q_LO, Q_HI = Fraction(1, 40), Fraction(39, 40)


def stratified_counts(matrix, cells, reps, rng):
    """Resampled integer loss counts (reps x arms). Cells ascending; rows within a cell in input order."""
    matrix = np.asarray(matrix, dtype=np.int64); cells = np.asarray(cells)
    out = np.zeros((reps, matrix.shape[1]), np.int64)
    for c in sorted(set(cells.tolist())):
        idx = np.flatnonzero(cells == c)
        draw = rng.integers(0, len(idx), size=(reps, len(idx)))
        out += matrix[idx[draw]].sum(axis=1)
    return out


def exact_bound(values, q, n):
    """Linear percentile with rational index and weight (T1 convention), in pp/percent of n."""
    ordered = np.sort(np.asarray(values, dtype=np.int64))
    position = (len(ordered)-1)*q; i = position.numerator//position.denominator
    weight = position-i; j = min(i+1, len(ordered)-1)
    return (Fraction(int(ordered[i]))+weight*int(ordered[j]-ordered[i]))*100/n


def ci(values, n):
    lo, hi = exact_bound(values, Q_LO, n), exact_bound(values, Q_HI, n)
    return dict(ci95=[float(lo), float(hi)], exact95=[[lo.numerator, lo.denominator], [hi.numerator, hi.denominator]])


def upper(rec):
    return Fraction(*rec['exact95'][1])


def analysis(rows, arms, reps, rng):
    """One stratified analysis: per-arm counts/CIs and every ordered contrast among `arms`."""
    n = len(rows)
    loss = np.array([[r['loss'][a] for a in arms] for r in rows], dtype=np.int64)
    boot = stratified_counts(loss, [r['cell'] for r in rows], reps, rng)
    counts = loss.sum(0)
    out = dict(n=n, cells=dict(sorted(collections.Counter(r['cell'] for r in rows).items())), arms={}, contrasts={})
    for j, a in enumerate(arms):
        out['arms'][a] = dict(losses=int(counts[j]), draws=sum(r['draw'][a] for r in rows), wins=sum(r['win'][a] for r in rows),
                              loss_pct=float(Fraction(100*int(counts[j]), n)), **ci(boot[:, j], n))
    for l in range(len(arms)):
        for r_ in range(len(arms)):
            if l == r_: continue
            out['contrasts'][f'{arms[l]} minus {arms[r_]}'] = dict(point_count_diff=int(counts[l]-counts[r_]),
                mean_pp=float(Fraction(100*int(counts[l]-counts[r_]), n)), **ci(boot[:, l]-boot[:, r_], n))
    return out


def population_stats(rows, rng, reps, arms=CORE):
    """T1-compatible entry point used by the unchanged OP-6/OP-7 sensitivity sidecar (ssh_sensitivity.py)."""
    out = analysis(rows, arms, reps, rng); out['stratum_counts'] = out['cells']
    return out


def contrast(stats, pop, x, y):
    return stats[pop]['contrasts'][f'{x} minus {y}']


def decide(stats, c_star, margins):
    """Fixed sequence (r3 §1.2), admission, veto and usable cells (r3 §1.5)."""
    def arm(kind, c): return f'{kind}-{CELL_ARM[c]}'
    def parts(level, c):
        m = margins[level]
        p = dict(ref=upper(contrast(stats, 'primary', arm('K4S', c), 'K4-200')) <= m['ref_pp'],
                 guard_ref=upper(contrast(stats, 'guard', arm('K4S', c), 'K4-200')) <= m['guard_ref_pp'])
        if c <= 0.8:
            pop = 'primary' if c == 0.8 else 'primary_subsample'
            p['same'] = upper(contrast(stats, pop, arm('K4S', c), arm('K4', c))) < 0
        return p
    sequence = [('B', 0.8), ('B', 0.7), ('B', 0.6), ('A', 0.9), ('A', 0.8), ('A', 0.7), ('A', 0.6)]
    assert c_star in (0.9, 0.8)
    if c_star == 0.8: sequence.remove(('A', 0.9))
    steps = []; stopped = False
    for k, (level, c) in enumerate(sequence, 1):
        if stopped:
            steps.append(dict(step=f'H{k}', hypothesis=f'{level}({c})', tested=False, passed=False)); continue
        p = parts(level, c); ok = all(p.values())
        steps.append(dict(step=f'H{k}', hypothesis=f'{level}({c})', tested=True, passed=ok, parts=p))
        stopped = not ok
    passed = {s['hypothesis'] for s in steps if s['passed']}
    admitted = {}
    for c in (0.9, 0.8, 0.7, 0.6):
        admitted[str(c)] = 'A' if f'A({c})' in passed else 'B' if f'B({c})' in passed else None
    veto = upper(contrast(stats, 'primary', 'K4S-180', 'K4-180')) <= margins['veto_pp']
    usable = ([0.9] if admitted['0.9'] == 'A' and veto else []) + [c for c in (0.8, 0.7, 0.6) if admitted[str(c)] in ('A', 'B')]
    return dict(c_star=c_star, sequence=steps, admitted=admitted, veto_0_9_pass=veto, usable_cells=usable)


def load_blocks(root, ledger):
    lost = {e['lost']['id'] for e in ledger}
    replacements = {e['replacement']['id']: e['replacement'] for e in ledger if e['replacement'] is not None}
    pops = {'primary': {}, 'guard': {}}; files = {}
    for f in sorted(Path(root).glob('*/complete.json')):
        proof = read(f); d = proof['descriptor']; pop = d['population']; ident = d['id']
        if pop not in pops or ident in lost: continue
        if proof['host'] != '127x01': assert (f.parent/'hub-ack.json').exists(), 'completed block not durable on hub'
        if d.get('replaces'):
            r = replacements[ident]
            assert d['cell'] == r['cell'] and d['replaces'] == r['replaces'] and d['order'] == r['order']
        logical = d.get('replaces') or ident
        L = int(logical.rsplit('-', 1)[1])
        assert 0 <= L < COUNTS[pop] and d['cell'] == L % CELLS[pop] and logical not in pops[pop], 'logical block'
        assert d['order'] == expected_order(d) and set(d['order']) == (set(ARMS) if L < SUB_LIMIT[pop] else set(CORE))
        assert d['seed'] == plan()['seed_ranges'][pop]['base']+d['index']
        assert len(proof['games']) == len(d['order'])
        row = dict(id=logical, index=L, seed=d['seed'], cell=d['cell'], seat=d['seat'], host=proof['host'],
                   subsample=L < SUB_LIMIT[pop], interference=proof.get('interference', {}),
                   loss={}, draw={}, win={}, timing={}, matchup=None)
        for name, h in proof['games'].items():
            p = f.parent/'games'/name; assert sha(p) == h; files[str(p)] = h
            g = read(p); m = g['metadata']; a = g['cohort']
            assert m['terminal'] and m['seed'] == d['seed'] and m['cell'] == d['cell'] and m['seat'] == d['seat'] and a in d['order']
            lossv = int(m['winner'] is not None and m['winner'] != m['seat']); assert int(g['loss']) == lossv
            row['loss'][a] = lossv; row['draw'][a] = m['winner'] is None; row['win'][a] = m['winner'] == m['seat']
            row['timing'][a] = g['search_ab']['deadline_stats']
            row['matchup'] = (tuple(sorted(m['own_deck'])), tuple(sorted(m['opponent_deck'])))
        assert set(row['loss']) == set(d['order'])
        pops[pop][logical] = row
    assert len(pops['primary']) == COUNTS['primary'] and len(pops['guard']) == COUNTS['guard'], {k: len(v) for k, v in pops.items()}
    out = {p: sorted(v.values(), key=lambda r: r['index']) for p, v in pops.items()}
    assert sum(r['subsample'] for r in out['primary']) == SUB_LIMIT['primary'] and sum(r['subsample'] for r in out['guard']) == SUB_LIMIT['guard']
    return out, files


def all_analyses(rows, reps, rng):
    return {'primary': analysis(rows['primary'], CORE, reps, rng),
            'guard': analysis(rows['guard'], CORE, reps, rng),
            'primary_subsample': analysis([r for r in rows['primary'] if r['subsample']], ARMS, reps, rng),
            'guard_subsample': analysis([r for r in rows['guard'] if r['subsample']], ARMS, reps, rng)}


def secondary(rows, stats, cfg):
    reps = cfg['bootstrap']['reps']; out = {}
    out['F1'] = {p: contrast(stats, p, 'K4S-200', 'K4-200') for p in ('primary', 'guard')}
    out['F1_always_on_note'] = all(upper(out['F1'][p]) <= Fraction(5, 2) for p in out['F1'])
    out['monotonicity'] = {k: contrast(stats, 'primary', x, y) for k, x, y in
                           (('K4S-180 minus K4S-160', 'K4S-180', 'K4S-160'), ('K4S-200 minus K4S-180', 'K4S-200', 'K4S-180'))}
    # Flagged-block sensitivity (separate stream); never changes admission.
    rng = np.random.default_rng(cfg['bootstrap']['sensitivity_seed'])
    clean = {p: [r for r in v if not r['interference'].get('interfered')] for p, v in rows.items()}
    out['interference_excluded'] = {p: len(rows[p])-len(clean[p]) for p in rows}
    if all(clean.values()):
        out['interference_sensitivity'] = {p: analysis(clean[p], CORE, reps, rng)['contrasts'] for p in ('primary', 'guard')}
    # Matchup-cluster bootstrap over the 25 primary matchups and the 9 guard pairs (separate stream).
    rng = np.random.default_rng(cfg['bootstrap']['cluster_seed']); out['cluster'] = {}
    for p in ('primary', 'guard'):
        keys = sorted({r['matchup'] for r in rows[p]}); by = {k: [r for r in rows[p] if r['matchup'] == k] for k in keys}
        mats = {k: np.array([[r['loss'][a] for a in CORE] for r in by[k]], np.int64) for k in keys}
        draw = rng.integers(0, len(keys), size=(reps, len(keys)))
        tot = np.array([[mats[keys[i]].sum(0) for i in row] for row in draw]).sum(1)
        cnt = np.array([[len(by[keys[i]]) for i in row] for row in draw]).sum(1)
        res = {}
        for x in CORE[1:]:
            j, k = CORE.index(x), CORE.index('K4-200'); v = 100*(tot[:, j]-tot[:, k])/cnt
            res[f'{x} minus K4-200'] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
        out['cluster'][p] = dict(clusters=len(keys), ci95_pp=res)
    out['per_host_seat'] = {p: {f'{h}|seat{s}': {a: float(np.mean([r['loss'][a] for r in rows[p] if r['host'] == h and r['seat'] == s]))*100
                                                 for a in CORE}
                                for h in sorted({r['host'] for r in rows[p]}) for s in (0, 1)
                                if any(r['host'] == h and r['seat'] == s for r in rows[p])} for p in rows}
    out['draws_half_loss_pct'] = {p: {a: 100*sum(r['loss'][a]+0.5*r['draw'][a] for r in rows[p])/len(rows[p]) for a in CORE} for p in rows}
    mech = {}
    for p in rows:
        mech[p] = {}
        for a in CORE:
            ds = [d for r in rows[p] for d in r['timing'][a]]
            mech[p][a] = dict(decisions=len(ds), cutoff_pct=100*np.mean([d['hit'] for d in ds]), student_default_pct=100*np.mean([bool(d.get('student_default')) for d in ds]),
                              coarse_complete_at_cutoff_pct=100*np.mean([bool(d.get('coarse_complete')) for d in ds if d['hit']] or [0]),
                              fallback_pct=100*np.mean([d['fallback'] for d in ds]), overrun_pct=100*np.mean([d['wall_overrun'] for d in ds]),
                              play_pct=100*np.mean([d['action'] < 2304 for d in ds]),
                              median_candidates=float(np.median([d['unpruned_candidate_count'] for d in ds if d['unpruned_candidate_count'] is not None] or [0])),
                              wall_ms=dict(zip(('p50', 'p95', 'p99', 'max'), map(float, np.percentile([1000*d['wall_seconds'] for d in ds], [50, 95, 99, 100])))),
                              late_returns=sum(d['wall_seconds'] > CELL_ARM_BUDGET(a)/1000+0.008 for d in ds),
                              sd1_p_play_quartiles=None if a.startswith('K4-') else list(map(float, np.percentile([d['sd1_p_play'] for d in ds], [25, 50, 75]))))
    out['mechanism'] = mech
    return out


def verifier_view(stats, decision):
    """Fixed comparison block (K4S-SPEC §6.7): exact keys the independent verifier compares item by item."""
    names = {'primary': 'P_full', 'guard': 'G_full', 'primary_subsample': 'P_sub', 'guard_subsample': 'G_sub'}
    counts = {names[p]: {a: dict(losses=v['losses'], draws=v['draws'], n=stats[p]['n']) for a, v in stats[p]['arms'].items()} for p in names}
    def bounds(pop, x, y):
        e = contrast(stats, pop, x, y)['exact95']
        return dict(lower=e[0], upper=e[1])
    con = {}
    for c in (0.9, 0.8, 0.7, 0.6):
        con[f'P_full:dref@{c}'] = bounds('primary', f'K4S-{CELL_ARM[c]}', 'K4-200')
        con[f'G_full:drefg@{c}'] = bounds('guard', f'K4S-{CELL_ARM[c]}', 'K4-200')
    con['P_full:dsame@0.8'] = bounds('primary', 'K4S-160', 'K4-160')
    con['P_sub:dsame@0.7'] = bounds('primary_subsample', 'K4S-140', 'K4-140')
    con['P_sub:dsame@0.6'] = bounds('primary_subsample', 'K4S-120', 'K4-120')
    con['P_full:veto@0.9'] = bounds('primary', 'K4S-180', 'K4-180')
    return dict(schema='clasher.k4s.verifier-view.v1', counts=counts, contrasts=con,
                sequence=[dict(step=s['step'], hypothesis=s['hypothesis'], tested=s['tested'], passed=s['passed']) for s in decision['sequence']],
                admitted=decision['admitted'], veto_pass=decision['veto_0_9_pass'],
                usable_cells=[str(c) for c in decision['usable_cells']], validity_inside=decision['validity']['inside'])


def CELL_ARM_BUDGET(arm): return int(arm.rsplit('-', 1)[1])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True); ap.add_argument('--release', type=Path)
    ap.add_argument('--synthetic', action='store_true'); ap.add_argument('--ledger', type=Path); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); cfg = plan()
    # Must happen before touching the block directory or any raw game file.
    if a.synthetic:
        assert (a.root/'SYNTHETIC').exists() and not a.release, 'synthetic mode only on a SYNTHETIC tree'
        release = dict(synthetic=True)
    else:
        from barrier import outcome_release
        release = outcome_release(ROOT, a.release)
    ledger = read(a.ledger)['events'] if a.ledger else []
    rows, files = load_blocks(a.root, ledger)
    rng = np.random.default_rng(cfg['bootstrap']['seed'])
    stats = all_analyses(rows, cfg['bootstrap']['reps'], rng)
    margins = dict(A=cfg['decision']['A'], B=cfg['decision']['B'], veto_pp=cfg['decision']['veto_0.9_pp'])
    decision = decide(stats, cfg['c_star'], margins)
    lo, hi = cfg['decision']['validity_K4_200_primary_pct']; n = stats['primary']['n']; k = stats['primary']['arms']['K4-200']['losses']
    decision['validity'] = dict(K4_200_primary_losses=k, n=n, window_pct=[lo, hi], inside=lo*n <= 100*k <= hi*n)
    decision['status'] = 'ADMISSION' if decision['validity']['inside'] else 'SUSPENDED (validity window; independent receipts-only code review required)'
    result = dict(utc=utc(), study='PREREG-K4S', sealed=False, release=release, bootstrap=cfg['bootstrap'], populations=stats,
                  verifier_view=verifier_view(stats, decision),
                  decision=decision, secondary=secondary(rows, stats, cfg), replacements=ledger, file_shas=files,
                  plan_sha256=sha(Path(__file__).parent/'plan.json'), reducer_sha256=sha(__file__))
    write(a.out, result)
    print(json.dumps(dict(utc=result['utc'], completed=True, status=decision['status'])))


if __name__ == '__main__':
    main()
