"""Independent integer-count verifier for the T1 search-tier confirmatory study.

Author: the T1 verifier/reviewer, not the T1 reducer's author (PREREG §2.3, §5). It imports nothing from
the T1 tree. Every constant below is transcribed from the frozen PREREG (PREREG-SEARCH-TIERS-r3-DRAFT.md,
sha ef0db97a...). T1's plan.json and guard-decks.json are read only as data and cross-checked.

What it does:
  1. Seal: refuses to open any game file unless the inputs are marked SYNTHETIC or a release receipt
     follows one of the two §6.6(b) paths.
  2. Ledger: counts a block only if complete.json exists, its 8 game SHA-256s match, and no exit record marks
     it failed. It checks cell-preserving replacement (§3.2), per-cell counts, caps and the bank prefix.
  3. Integer outcomes: loss = winner is not None and winner != seat; a draw is a non-loss; a non-terminal game
     is an error.
  4. Stratified paired bootstrap: 10,000 resamples, numpy.default_rng(2026101040), one index set shared by all
     contrasts. It draws primary cells 0..49 and then guard cells 0..17, each
     integers(0, n_c, size=(R, n_c)) over that cell's seeds sorted by seed index. T1's own index matrices can
     be supplied instead (--t1-indices) for a bit-exact comparison.
  5. Percentile intervals, both float (numpy linear) and exact (Fraction). Gates are V1, V2, G1, G2 and NI over
     every cell combination, plus the K0c@200 validity window and the §6.5 selection from a Mac cell map.
  6. Flags: any mismatch with T1's reduction; exact boundary hits; bounds within one count step of a threshold;
     float/exact decision disagreement; 0.9833-vs-(1-0.05/3) decision flips; G1 bound exactly 0 (strict gate).

Exit code: 0 clean, 1 edge-case flags only, 2 errors or mismatches.
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

COORDINATOR = '0523ae6f-baa3-4d4e-b233-b392671670db'
# §3 seed table.
POP = {
    'primary': dict(base=4503603107370496, n=2400, cells=50, bank=480, max_k=8, cap=240),
    'guard': dict(base=4503603207370496, n=600, cells=18, bank=120, max_k=5, cap=60),
    'descriptive': dict(base=4503603507370496, n=72, cells=18, bank=0, max_k=None, cap=None),
}
GATED = ('primary', 'guard')
TIERS = ('K0c', 'S', 'K2', 'K4')
CORES = {'S': 1, 'K2': 3, 'K4': 5}
DEADLINE = {200: 0.2, 160: 0.16}
SPEC = {  # §2 arms
    'K0c': dict(threads=1, kernel='coarse-first', policy='v1-cached'),
    'S': dict(threads=1, kernel='coarse-first', policy='R3a-cached'),
    'K2': dict(threads=2, kernel='K2-anytime', policy='v1-unmodified'),
    'K4': dict(threads=4, kernel='K2-anytime', policy='v1-unmodified'),
}
ARMS = tuple(f'{t}-{ms}' for t in TIERS for ms in (200, 160))
REPS = 10_000
BOOT_SEED = 2026101040
# Two-sided levels (§1, §5). V1/V2 are Bonferroni over three tiers: exactly 1 - 0.05/3.
LEVELS = {'v': Fraction(1) - Fraction(1, 20) / 3, 'ni': Fraction(39, 40), 'g': Fraction(19, 20)}
V_ROUNDED = Fraction(9833, 10000)  # plan.json's literal; flagged if it flips a decision
VALIDITY = (Fraction(36), Fraction(54))  # K0c@200 primary loss %, inclusive (§8)


class Report:
    def __init__(self):
        self.errors, self.edges, self.notes = [], [], []

    def error(self, code, **kw):
        self.errors.append(dict(code=code, **kw))

    def edge(self, code, **kw):
        self.edges.append(dict(code=code, **kw))

    def note(self, code, **kw):
        self.notes.append(dict(code=code, **kw))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def arm_of(tier, ms):
    return f'{tier}-{ms}'


def cell_size(pop, c):
    p = POP[pop]
    return p['n'] // p['cells'] + (1 if c < p['n'] % p['cells'] else 0)


# ---------------------------------------------------------------- seal

def check_seal(roots, release, repo):
    """Return the mode string; raise SystemExit before any game byte is read if sealed."""
    if release is None:
        missing = [str(r) for r in roots if not (Path(r) / 'SYNTHETIC').exists()]
        if missing:
            raise SystemExit(f'SEALED: no release receipt and inputs are not SYNTHETIC: {missing}')
        return 'synthetic'
    r = json.loads(Path(release).read_text())
    if r.get('coordinator_thread') != COORDINATOR or not r.get('authorization_message_id'):
        raise SystemExit('SEALED: release receipt lacks coordinator thread/message evidence')
    if r.get('reason') == 'committed_mac_summary':
        name = r['mac_summary_path']
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise SystemExit('SEALED: bad summary path')
        raw = subprocess.check_output(['git', '-C', str(repo), 'show', f"{r['commit']}:{name}"])
        if hashlib.sha256(raw).hexdigest() != r['mac_summary_sha256']:
            raise SystemExit('SEALED: committed Mac summary hash mismatch')
        if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', r['commit'], 'HEAD']).returncode:
            raise SystemExit('SEALED: summary commit not an ancestor of HEAD')
        return 'released:committed_mac_summary'
    if r.get('reason') == 'fourteen_day_escape':
        from datetime import datetime, timedelta
        done = datetime.fromisoformat(r['reporting_complete_utc'].replace('Z', '+00:00'))
        auth = datetime.fromisoformat(r['authorized_at_utc'].replace('Z', '+00:00'))
        if auth < done + timedelta(days=14):
            raise SystemExit('SEALED: 14-day escape not yet reached')
        return 'released:fourteen_day_escape'
    raise SystemExit(f"SEALED: release reason {r.get('reason')!r} is not a PREREG §6.6(b) path")


# ---------------------------------------------------------------- ledger

def load_blocks(roots, exits_dirs, rep, dispatch_files=()):
    exits = {}
    for d in exits_dirs:
        for p in sorted(Path(d).glob('*.json')):
            e = json.loads(p.read_text())
            bid = e['descriptor']['id']
            if bid in exits and exits[bid]['complete'] != e['complete']:
                rep.error('CONFLICTING_EXIT_RECORDS', block=bid)
            exits[bid] = e
    seen = {}
    counted = {}
    for root in roots:
        for desc_path in sorted(Path(root).glob('*/descriptor.json')):
            folder = desc_path.parent
            d = json.loads(desc_path.read_text())
            bid = d['id']
            if bid != folder.name:
                rep.error('DESCRIPTOR_ID_MISMATCH', folder=str(folder), id=bid)
            if bid in seen:
                rep.error('DUPLICATE_BLOCK_DIRECTORY', block=bid, folders=[seen[bid]['folder'], str(folder)])
                continue
            seen[bid] = dict(descriptor=d, folder=str(folder))
            complete = folder / 'complete.json'
            if not complete.exists():
                continue
            ex = exits.get(bid)
            if ex is not None and not ex['complete']:
                rep.edge('COMPLETE_BUT_MARKED_FAILED', block=bid,
                         detail='complete.json exists but the exit record says failed; excluded (review B3)')
                continue
            proof = json.loads(complete.read_text())
            if proof.get('descriptor', d) != d:
                rep.error('COMPLETE_DESCRIPTOR_MISMATCH', block=bid)
            games = proof.get('games', {})
            if len(games) != 8:
                rep.error('BLOCK_NOT_EIGHT_GAMES', block=bid, games=len(games))
                continue
            bad = [n for n, h in games.items() if not (folder / 'games' / n).exists() or sha(folder / 'games' / n) != h]
            if bad:
                rep.error('GAME_SHA_MISMATCH', block=bid, files=bad)
                continue
            counted[bid] = dict(descriptor=d, folder=folder, games=sorted(games))
    # Dispatch files (schedule output, replacement dispatches) prove a block was issued even when its
    # host was lost before any copy reached the hub.
    for f in dispatch_files:
        for d in json.loads(Path(f).read_text())['blocks']:
            d = {k: v for k, v in d.items() if k not in ('dispatch', 'host')}
            if d['id'] in seen:
                if seen[d['id']]['descriptor'] != {**seen[d['id']]['descriptor'], **d}:
                    rep.error('DISPATCH_DESCRIPTOR_MISMATCH', block=d['id'])
            else:
                seen[d['id']] = dict(descriptor=d, folder=None)
    return seen, counted, exits


def check_descriptor(d, rep):
    pop, i, c = d['population'], d['index'], d['cell']
    if pop not in POP:
        rep.error('BAD_POPULATION', block=d['id'], population=pop)
        return False
    p = POP[pop]
    ok = True
    if d['seed'] != p['base'] + i:
        rep.error('SEED_NOT_BASE_PLUS_INDEX', block=d['id'], seed=d['seed'])
        ok = False
    if not 0 <= c < p['cells']:
        rep.error('CELL_OUT_OF_RANGE', block=d['id'], cell=c)
        return False
    if i < p['n']:
        if c != i % p['cells']:
            rep.error('ORIGINAL_CELL_NOT_INDEX_MOD', block=d['id'], index=i, cell=c)
            ok = False
    else:
        j = i - p['n']
        if not p['bank'] or j >= p['bank']:
            rep.error('INDEX_OUTSIDE_RESERVATION', block=d['id'], index=i)
            return False
        if j % p['cells'] != c:
            rep.error('REPLACEMENT_NOT_CELL_PRESERVING', block=d['id'], index=i, cell=c,
                      expected_cell=j % p['cells'])
            ok = False
        if j // p['cells'] > p['max_k']:
            rep.error('BANK_ROW_EXHAUSTED', block=d['id'], k=j // p['cells'])
            ok = False
    return ok


def check_ledger(seen, counted, rep, populations=tuple(POP)):
    by_pop = defaultdict(list)
    for bid, b in counted.items():
        if check_descriptor(b['descriptor'], rep):
            by_pop[b['descriptor']['population']].append(b)
    for bid, s in seen.items():
        if bid not in counted:
            check_descriptor(s['descriptor'], rep)
    counted_ids = set(counted)
    for pop, p in POP.items():
        if pop not in populations:
            if by_pop.get(pop):
                rep.error('UNEXPECTED_POPULATION', population=pop)
            continue
        rows = by_pop.get(pop, [])
        idx = Counter(b['descriptor']['index'] for b in rows)
        dup = [i for i, k in idx.items() if k > 1]
        if dup:
            rep.error('SEED_INDEX_COUNTED_TWICE', population=pop, indices=dup)
        per_cell = Counter(b['descriptor']['cell'] for b in rows)
        if not rows and pop == 'descriptive':
            continue
        for c in range(p['cells']):
            want = cell_size(pop, c)
            got = per_cell.get(c, 0)
            if pop == 'descriptive':
                if got != want:
                    rep.note('DESCRIPTIVE_CELL_SHORT', cell=c, counted=got, planned=want)
            elif got != want:
                rep.error('CELL_COUNT', population=pop, cell=c, counted=got, required=want)
        # A counted replacement's logical original must not also be counted.
        for b in rows:
            orig = b['descriptor'].get('replaces')
            if orig and orig in counted_ids:
                rep.error('ORIGINAL_AND_REPLACEMENT_BOTH_COUNTED', block=b['descriptor']['id'], original=orig)
        # Every planned original index is counted or visibly lost (descriptor seen, not counted).
        seen_idx = {s['descriptor']['index'] for s in seen.values() if s['descriptor']['population'] == pop}
        cnt_idx = set(idx)
        missing = [i for i in range(p['n']) if i not in seen_idx]
        if missing and pop != 'descriptive':
            rep.error('ORIGINAL_NEVER_DISPATCHED', population=pop, count=len(missing), first=missing[:10])
        lost = sorted(i for i in seen_idx if i not in cnt_idx)
        if pop == 'descriptive' and any(i >= p['n'] for i in seen_idx):
            rep.error('DESCRIPTIVE_REPLACED', indices=[i for i in seen_idx if i >= p['n']])
        if pop in GATED:
            repl = sorted(i for i in seen_idx if i >= p['n'])
            if len(repl) > p['cap']:
                rep.error('REPLACEMENT_CAP_EXCEEDED', population=pop, replacements=len(repl), cap=p['cap'])
            ks = defaultdict(set)
            for i in repl:
                ks[(i - p['n']) % p['cells']].add((i - p['n']) // p['cells'])
            for c, k in ks.items():
                if k != set(range(len(k))):
                    rep.error('BANK_NOT_PREFIX', population=pop, cell=c, ks=sorted(k))
            n_lost = len(lost)
            if n_lost != len(repl):
                rep.error('LOST_VS_REPLACEMENT_COUNT', population=pop, lost=n_lost, replacements_assigned=len(repl))
            rep.note('REPLACEMENTS', population=pop, lost_blocks=n_lost, replacements_assigned=len(repl),
                     lost_by_cell=dict(Counter(s['descriptor']['cell'] for s in seen.values()
                                               if s['descriptor']['population'] == pop
                                               and s['descriptor']['index'] not in cnt_idx)))
    return by_pop


# ---------------------------------------------------------------- games

def read_games(by_pop, decks, rep):
    """Return {pop: {cell: [(index, {arm: loss_int})]}} and the per-arm W/L/D tallies."""
    data = {}
    tallies = {}
    triples = defaultdict(dict)
    for pop, rows in by_pop.items():
        cells = defaultdict(list)
        tally = {a: Counter() for a in ARMS}
        for b in rows:
            d = b['descriptor']
            losses = {}
            meta0 = None
            for name in b['games']:
                r = json.loads((b['folder'] / 'games' / name).read_text())
                m = r['metadata']
                arm = r.get('cohort')
                if arm not in ARMS or m.get('arm') != arm:
                    rep.error('ARM_LABEL', block=d['id'], file=name, cohort=arm, meta_arm=m.get('arm'))
                    continue
                tier, ms = arm.split('-')
                spec = SPEC[tier]
                for key, want in (('population', d['population']), ('cell', d['cell']),
                                  ('seed_index', d['index']), ('seed', d['seed']),
                                  ('deadline_seconds', DEADLINE[int(ms)]), ('threads', spec['threads']),
                                  ('kernel', spec['kernel']), ('opponent', 'v1-policy')):
                    if m.get(key) != want:
                        rep.error('GAME_METADATA', block=d['id'], arm=arm, field=key, got=m.get(key), want=want)
                if not str(m.get('default_source', '')).startswith(spec['policy']):
                    rep.error('GAME_METADATA', block=d['id'], arm=arm, field='default_source',
                              got=m.get('default_source'), want=spec['policy'])
                if d.get('seat') is not None and m.get('seat') != d['seat']:
                    rep.error('SEAT_MISMATCH', block=d['id'], arm=arm)
                if m.get('terminal') is not True:
                    rep.error('NONTERMINAL_GAME', block=d['id'], arm=arm)
                    continue
                seat, winner = m['seat'], m.get('winner')
                if winner not in (None, 0, 1):
                    rep.error('BAD_WINNER', block=d['id'], arm=arm, winner=winner)
                    continue
                loss = int(winner is not None and winner != seat)
                if 'loss' in r and r['loss'] is not None and float(r['loss']) != float(loss):
                    rep.error('LOSS_FIELD_INCONSISTENT', block=d['id'], arm=arm)
                tally[arm]['wins' if winner == seat else 'draws' if winner is None else 'losses'] += 1
                losses[arm] = loss
                triple = (m['seat'], tuple(sorted(m['own_deck'])), tuple(sorted(m['opponent_deck'])))
                if meta0 is None:
                    meta0 = triple
                elif triple != meta0:
                    rep.error('ARMS_NOT_PAIRED', block=d['id'], arm=arm)
            if set(losses) != set(ARMS):
                rep.error('BLOCK_MISSING_ARMS', block=d['id'], arms=sorted(set(ARMS) - set(losses)))
                continue
            prev = triples[pop].setdefault(d['cell'], meta0)
            if prev != meta0:
                rep.error('CELL_NOT_CONSTANT_MATCHUP', population=pop, cell=d['cell'], block=d['id'])
            cells[d['cell']].append((d['index'], losses))
        for c in cells:
            cells[c].sort(key=lambda x: x[0])
        data[pop] = dict(cells)
        tallies[pop] = {a: dict(n=sum(t.values()), **{k: t[k] for k in ('wins', 'losses', 'draws')})
                        for a, t in tally.items()}
    check_matchups(triples, decks, rep)
    return data, tallies


def check_matchups(triples, decks, rep):
    for pop, cmap in triples.items():
        p = POP[pop]
        if len(set(cmap.values())) != len(cmap):
            rep.error('CELLS_SHARE_MATCHUP', population=pop)
        if decks is None:
            continue
        s = lambda deck: tuple(sorted(deck))
        if pop == 'primary':
            prim = [s(x) for x in decks['primary']]
            for c, t in cmap.items():
                want = (c % 2, prim[c % 5], prim[(c // 5) % 5])  # S1/K2 harness convention
                if t != want:
                    rep.error('PRIMARY_CELL_MATCHUP', cell=c)
        else:
            own_set = {s(x) for x in decks['l2']}
            opp_set = {s(x['cards']) for x in decks['guard']} if pop == 'guard' else own_set
            cover = {(t[0], t[1], t[2]) for t in cmap.values()}
            if any(t[1] not in own_set or t[2] not in opp_set for t in cover):
                rep.error('MATCHUP_DECK_NOT_IN_POPULATION', population=pop)
            if len(cmap) == p['cells'] and len(cover) != 18:
                rep.error('MATCHUP_COVERAGE', population=pop, distinct=len(cover))


# ---------------------------------------------------------------- bootstrap and intervals

def bootstrap_counts(data, t1_indices=None, rep=None):
    """Return {pop: {arm: int64[R]}} resampled loss counts, and the index source."""
    rng = np.random.default_rng(BOOT_SEED)
    out = {}
    for pop in GATED:
        if pop not in data:
            continue
        acc = {a: np.zeros(REPS, dtype=np.int64) for a in ARMS}
        for c in range(POP[pop]['cells']):
            rows = data[pop].get(c, [])
            n_c = len(rows)
            if t1_indices is not None:
                idx = np.asarray(t1_indices[f'{pop}:{c}'])
                if idx.shape != (REPS, n_c) or (n_c and (idx.min() < 0 or idx.max() >= n_c)):
                    rep.error('T1_INDICES_NOT_STRATIFIED', population=pop, cell=c, shape=list(idx.shape))
                    raise SystemExit(2)
            else:
                idx = rng.integers(0, n_c, size=(REPS, n_c)) if n_c else np.zeros((REPS, 0), dtype=np.int64)
            for a in ARMS:
                v = np.fromiter((x[1][a] for x in rows), dtype=np.int64, count=n_c)
                acc[a] += v[idx].sum(axis=1, dtype=np.int64)
        out[pop] = acc
    return out


def exact_quantile(sorted_ints, q):
    """numpy 'linear' percentile, exactly: x[j] + g*(x[j+1]-x[j]), h=(R-1)q."""
    h = (len(sorted_ints) - 1) * q
    j = math.floor(h)
    g = h - j
    lo = int(sorted_ints[j])
    hi = int(sorted_ints[min(j + 1, len(sorted_ints) - 1)])
    return Fraction(lo) + g * (hi - lo)


def interval(counts, n, level):
    """Two-sided percentile interval in pp: exact Fractions and numpy floats."""
    xs = np.sort(counts)
    a = (1 - level) / 2
    exact = [exact_quantile(xs, a) * 100 / n, exact_quantile(xs, 1 - a) * 100 / n]
    flt = [float(v) * 100 / n for v in np.percentile(counts, [100 * float(a), 100 * float(1 - a)])]
    return exact, flt


# ---------------------------------------------------------------- gates

def gate(name, exact_ub, float_ub, threshold, strict, n, rep, ctx, rounded_ub=None):
    passed = exact_ub < threshold if strict else exact_ub <= threshold
    fpass = float_ub < float(threshold) if strict else float_ub <= float(threshold)
    step = Fraction(100, n)
    if exact_ub == threshold:
        rep.edge('EXACT_BOUNDARY', gate=name, strict=strict, bound_pp=str(exact_ub), passed=passed, **ctx)
    elif abs(exact_ub - threshold) <= step:
        rep.edge('WITHIN_ONE_COUNT_OF_THRESHOLD', gate=name, bound_pp=float(exact_ub),
                 threshold_pp=float(threshold), step_pp=float(step), passed=passed, **ctx)
    if passed != fpass:
        rep.edge('FLOAT_EXACT_DISAGREE', gate=name, exact=passed, float=fpass, bound_pp=float(exact_ub), **ctx)
    if rounded_ub is not None:
        rpass = rounded_ub < threshold if strict else rounded_ub <= threshold
        if rpass != passed:
            rep.edge('LEVEL_ROUNDING_FLIP', gate=name, exact_level_pass=passed, level_0_9833_pass=rpass, **ctx)
    return dict(gate=name, upper_pp=float(exact_ub), upper_exact=str(exact_ub), upper_float_pp=float_ub,
                threshold_pp=float(threshold), strict=strict, passed=passed, **ctx)


def reduce_all(data, tallies, boots, rep):
    out = dict(arms={}, contrasts={}, gates={})
    for pop in data:
        out['arms'][pop] = {}
        n = sum(len(v) for v in data[pop].values())
        for a in ARMS:
            t = tallies[pop][a]
            entry = dict(t, loss_pct=float(Fraction(100 * t['losses'], n)) if n else None)
            if pop in boots:
                entry['intervals'] = {}
                for k, L in LEVELS.items():
                    e, f = interval(boots[pop][a], n, L)
                    entry['intervals'][k] = dict(exact=[str(x) for x in e], pp=[float(x) for x in e], float_pp=f)
            out['arms'][pop][a] = entry
    for pop in GATED:
        if pop not in boots:
            continue
        n = sum(len(v) for v in data[pop].values())
        out['contrasts'][pop] = {}
        for left in ARMS:
            for right in ARMS:
                if left == right:
                    continue
                diff = boots[pop][left] - boots[pop][right]
                point = tallies[pop][left]['losses'] - tallies[pop][right]['losses']
                c = dict(point_count_diff=point, point_pp=float(Fraction(100 * point, n)), intervals={})
                for k, L in LEVELS.items():
                    e, f = interval(diff, n, L)
                    c['intervals'][k] = dict(exact=[str(x) for x in e], pp=[float(x) for x in e], float_pp=f)
                if pop == 'primary':
                    e, f = interval(diff, n, V_ROUNDED)
                    c['intervals']['v_rounded_0.9833'] = dict(exact=[str(x) for x in e], pp=[float(x) for x in e])
                out['contrasts'][pop][f'{left} minus {right}'] = c
    # Gate table over every cell combination (§1; §6.5 re-application needs all of them).
    g = out['gates']
    if 'primary' in boots:
        n = sum(len(v) for v in data['primary'].values())
        for t in ('S', 'K2', 'K4'):
            for s in (200, 160):
                arm = arm_of(t, s)
                e, f = interval(boots['primary'][arm], n, LEVELS['v'])
                er, _ = interval(boots['primary'][arm], n, V_ROUNDED)
                g[f'V2|{arm}'] = gate('V2', e[1], f[1], Fraction(40), False, n, rep, dict(arm=arm), er[1])
                for s1 in (200, 160):
                    ctrl = arm_of('K0c', s1)
                    diff = boots['primary'][arm] - boots['primary'][ctrl]
                    e, f = interval(diff, n, LEVELS['v'])
                    er, _ = interval(diff, n, V_ROUNDED)
                    g[f'V1|{arm}|{ctrl}'] = gate('V1', e[1], f[1], Fraction(-10), False, n, rep,
                                                 dict(left=arm, right=ctrl), er[1])
        for t, u in (('S', 'K2'), ('S', 'K4'), ('K2', 'K4')):
            for s in (200, 160):
                for su in (200, 160):
                    l, r = arm_of(t, s), arm_of(u, su)
                    e, f = interval(boots['primary'][l] - boots['primary'][r], n, LEVELS['ni'])
                    g[f'NI|{l}|{r}'] = gate('NI', e[1], f[1], Fraction(5), False, n, rep, dict(left=l, right=r))
        k0 = tallies['primary']['K0c-200']
        loss = Fraction(100 * k0['losses'], n)
        inside = VALIDITY[0] <= loss <= VALIDITY[1]
        if loss in VALIDITY:
            rep.edge('VALIDITY_WINDOW_BOUNDARY', loss_pct=str(loss))
        g['VALIDITY|K0c-200'] = dict(loss_pct=float(loss), loss_exact=str(loss), window=[36, 54], inside=inside)
    if 'guard' in boots:
        n = sum(len(v) for v in data['guard'].values())
        for t in ('S', 'K2', 'K4'):
            for s in (200, 160):
                arm = arm_of(t, s)
                for s1 in (200, 160):
                    ctrl = arm_of('K0c', s1)
                    e, f = interval(boots['guard'][arm] - boots['guard'][ctrl], n, LEVELS['g'])
                    g[f'G1|{arm}|{ctrl}'] = gate('G1', e[1], f[1], Fraction(0), True, n, rep,
                                                 dict(left=arm, right=ctrl))
        for t, u in (('S', 'K2'), ('S', 'K4'), ('K2', 'K4')):
            for s in (200, 160):
                for su in (200, 160):
                    l, r = arm_of(t, s), arm_of(u, su)
                    e, f = interval(boots['guard'][l] - boots['guard'][r], n, LEVELS['g'])
                    g[f'G2|{l}|{r}'] = gate('G2', e[1], f[1], Fraction(10), False, n, rep, dict(left=l, right=r))
    return out


def select(cells, gates):
    """§6.5. cells: {'K0c': 200|160|None, 'S'|'K2'|'K4': 200|160|None (None = Mac-infeasible)}."""
    s1 = cells.get('K0c') or 200  # §6.4: no K0c cell -> full-speed control
    ctrl = arm_of('K0c', s1)
    admissible = []
    for t in ('S', 'K2', 'K4'):
        s = cells.get(t)
        if s is None:
            continue
        a = arm_of(t, s)
        if gates[f'V1|{a}|{ctrl}']['passed'] and gates[f'V2|{a}']['passed'] and gates[f'G1|{a}|{ctrl}']['passed']:
            admissible.append(t)
    if not admissible:
        return dict(selection='F0', admissible=[], control=ctrl)
    admissible.sort(key=lambda t: CORES[t])
    for t in admissible:
        costlier = [u for u in admissible if CORES[u] > CORES[t]]
        lt = arm_of(t, cells[t])
        if all(gates[f'NI|{lt}|{arm_of(u, cells[u])}']['passed'] and
               gates[f'G2|{lt}|{arm_of(u, cells[u])}']['passed'] for u in costlier):
            return dict(selection=t, cell=cells[t], admissible=admissible, control=ctrl)
    return dict(selection=admissible[-1], cell=cells[admissible[-1]], admissible=admissible, control=ctrl)


# ---------------------------------------------------------------- comparison with T1

def compare_t1(mine, t1, rep, tol):
    """T1 schema (review §4.8): arms=[{population,arm,n,wins,losses,draws}],
    contrasts=[{population,left,right,point_count_diff,intervals:{v|ni|g:[lo,hi]}}], optional selection."""
    for a in t1.get('arms', []):
        m = mine['arms'].get(a['population'], {}).get(a['arm'])
        if m is None:
            rep.error('T1_UNKNOWN_ARM', **{k: a[k] for k in ('population', 'arm')})
            continue
        for k in ('n', 'wins', 'losses', 'draws'):
            if int(a[k]) != m[k]:
                rep.error('MISMATCH_COUNT', population=a['population'], arm=a['arm'], field=k, t1=a[k], verifier=m[k])
    seen = 0
    max_diff = 0.
    for c in t1.get('contrasts', []):
        key = f"{c['left']} minus {c['right']}"
        m = mine['contrasts'].get(c['population'], {}).get(key)
        if m is None:
            rep.error('T1_UNKNOWN_CONTRAST', population=c['population'], contrast=key)
            continue
        seen += 1
        if int(c['point_count_diff']) != m['point_count_diff']:
            rep.error('MISMATCH_POINT', population=c['population'], contrast=key,
                      t1=c['point_count_diff'], verifier=m['point_count_diff'])
        for lvl, bounds in c.get('intervals', {}).items():
            mv = m['intervals'].get(lvl)
            if mv is None:
                rep.error('T1_UNKNOWN_LEVEL', level=lvl)
                continue
            d = max(abs(float(x) - y) for x, y in zip(bounds, mv['pp']))
            max_diff = max(max_diff, d)
            if d > tol:
                rep.error('MISMATCH_INTERVAL', population=c['population'], contrast=key, level=lvl,
                          t1=bounds, verifier=mv['pp'], diff_pp=d)
    rep.note('T1_COMPARISON', contrasts_compared=seen, max_interval_diff_pp=max_diff, tolerance_pp=tol)
    if 'selection' in t1 and 'selection' in mine and t1['selection'] != mine['selection']['selection']:
        rep.error('MISMATCH_SELECTION', t1=t1['selection'], verifier=mine['selection']['selection'])


def cross_check_plan(plan, rep):
    for pop, key in (('primary', 'primary'), ('guard', 'guard'), ('descriptive', 'descriptive')):
        r = plan['seed_ranges'][key]
        if (r['base'], r['count']) != (POP[pop]['base'], POP[pop]['n']):
            rep.error('PLAN_SEED_RANGE', population=pop)
    for pop, key in (('primary', 'primary_replacements'), ('guard', 'guard_replacements')):
        r = plan['seed_ranges'][key]
        if (r['base'], r['count']) != (POP[pop]['base'] + POP[pop]['n'], POP[pop]['bank']):
            rep.error('PLAN_BANK_RANGE', population=pop)
    b = plan['bootstrap']
    if (b['reps'], b['seed']) != (REPS, BOOT_SEED):
        rep.error('PLAN_BOOTSTRAP', reps=b['reps'], seed=b['seed'])
    for c in b.get('confidences', []):
        if Fraction(str(c)) not in LEVELS.values():
            rep.edge('PLAN_LEVEL_NOT_EXACT', level=c, exact_levels=[str(x) for x in LEVELS.values()])
    for t in TIERS:
        for ms in (200, 160):
            a = plan['arms'][arm_of(t, ms)]
            if (a['threads'], a['kernel'], a['policy'], a['deadline_seconds']) != \
                    (SPEC[t]['threads'], SPEC[t]['kernel'], SPEC[t]['policy'], DEADLINE[ms]):
                rep.error('PLAN_ARM_SPEC', arm=arm_of(t, ms))


# ---------------------------------------------------------------- main

def run(args):
    rep = Report()
    mode = check_seal(args.blocks, args.release, args.repo)  # before any game byte
    if args.plan:
        cross_check_plan(json.loads(Path(args.plan).read_text()), rep)
    decks = json.loads(Path(args.guard_decks).read_text()) if args.guard_decks else None
    seen, counted, _ = load_blocks(args.blocks, args.exits or [], rep, args.dispatch or [])
    by_pop = check_ledger(seen, counted, rep, args.populations)
    data, tallies = read_games(by_pop, decks, rep)
    t1_idx = dict(np.load(args.t1_indices)) if args.t1_indices else None
    boots = bootstrap_counts(data, t1_idx, rep)
    out = reduce_all(data, tallies, boots, rep)
    if args.cells and 'primary' in boots and 'guard' in boots:
        out['selection'] = select(json.loads(Path(args.cells).read_text()), out['gates'])
    if args.t1_results:
        compare_t1(out, json.loads(Path(args.t1_results).read_text()), rep, args.tolerance_pp)
    status = 2 if rep.errors else 1 if rep.edges else 0
    out.update(mode=mode, status=['CLEAN', 'EDGE_FLAGS', 'ERRORS'][status], errors=rep.errors, edges=rep.edges,
               notes=rep.notes, verifier_sha256=sha(__file__), numpy=np.__version__,
               bootstrap=dict(reps=REPS, seed=BOOT_SEED, indices='t1-supplied' if t1_idx else 'verifier-canonical',
                              order='primary cells 0..49 then guard 0..17; integers(0,n_c,(R,n_c)); seeds by index'),
               levels={k: str(v) for k, v in LEVELS.items()})
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1) + '\n')
    return out, status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--blocks', nargs='+', required=True, help='hub phase dirs holding <block-id>/ folders')
    ap.add_argument('--exits', nargs='*', help='supervisor exits/ dirs (authoritative failed marks)')
    ap.add_argument('--dispatch', nargs='*', help='dispatch JSONs (schedule.py output, replacement dispatches)')
    ap.add_argument('--release', help='outcome release receipt (omit only for SYNTHETIC inputs)')
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[4]))
    ap.add_argument('--plan', help='T1 plan.json (data cross-check only)')
    ap.add_argument('--guard-decks', help='T1 guard-decks.json (data)')
    ap.add_argument('--cells', help='Mac cell map JSON {K0c,S,K2,K4: 200|160|null}')
    ap.add_argument('--t1-results', help='T1 reducer output to compare')
    ap.add_argument('--t1-indices', help='T1 bootstrap index matrices .npz with keys "<pop>:<cell>"')
    ap.add_argument('--populations', nargs='+', default=list(POP), help=argparse.SUPPRESS)  # tests only
    ap.add_argument('--tolerance-pp', type=float, default=1e-9)
    ap.add_argument('--out')
    out, status = run(ap.parse_args(argv))
    print(json.dumps(dict(status=out['status'], mode=out['mode'], errors=len(out['errors']),
                          edges=len(out['edges']), out=ap.parse_args(argv).out)))
    return status


if __name__ == '__main__':
    sys.exit(main())
