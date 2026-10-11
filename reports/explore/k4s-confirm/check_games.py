"""PREREG-K4S: outcome-blind checks of qualification game files (r3 §4.1). Exits nonzero on any failure.

Reads only an explicit projection: cohort, metadata identity/config fields, search_ab.command_sha256 and
search_ab.deadline_stats. Never reads loss, winner, crowns, draw or any outcome field.

Required inventory (exact; missing or extra games fail):
  t1-nd       T1 runtime, no deadline: qualification-0000 and -0001, K4-200
  k4s-nd-p0/g1  K4S runtime, no deadline: K4-200 and K4S-200 (seeds 0 / 1)
  k4s-ch-p2/g3  K4S runtime, all 10 arms charged (seeds 2 / 3)
  k4s-zero    K4S-200 and K4S-120 at a 0 ms deadline (seed 4)
  t1-inj/k4s-inj  K4-200 under the deterministic virtual clock, seeds 5 and 7, both runtimes
Checks:
  nodeadline: command hashes K4 (K4S runtime) == T1 K4-200 and K4S-200 == K4-200 per seed.
  injected:   command hashes and every per-decision timing/selection field equal between T1 and K4S runtimes;
              the decisions must cover belief or sample or prescan cutoffs, scored cutoffs and positive overruns.
  charged:    sleep share scale_sleep/(poll+scale_sleep) == 1-c +- tol on every exit path seen (mean and every
              decision); c = 1 never sleeps; scored path present for every arm and at least one preparation-cutoff
              path overall; every r3 §3.6 field present with the right nullability; honest lateness.
  zero:       every K4S decision returns the SD1 default, flagged student_default iff it is a play.
"""
import argparse, collections, glob, json, math, statistics, sys
from qual_tasks import TASKS, cores, expected_games, validate_receipts
from health import sd1_errors
from pathlib import Path

ARMS = ('K4-200', 'K4S-200', 'K4-180', 'K4S-180', 'K4-160', 'K4S-160', 'K4S-140', 'K4S-120', 'K4-140', 'K4-120')
FIELDS = ('hit', 'fallback', 'completed', 'candidates', 'unpruned_candidate_count', 'own_elixir', 'fallback_action', 'threads',
          'coarse_horizon', 'default_source', 'wall_overrun', 'overrun_seconds', 'delayed_ticks', 'decision_tick', 'action',
          'wall_seconds', 'cpu_seconds', 'coarse_complete', 'coarse_scored', 'plays', 'frozen_action', 'student_default',
          'sd1_default_action', 'sd1_p_play', 'coarse_order_sha256', 'chosen_action', 'fallback_used', 'selected_wait_ticks',
          'poll_seconds', 'scale_sleep_seconds', 'prep_seconds', 'scored', 'positive_overrun_ms', 'charged_extra_ticks')
META = ('study', 'speed_cell', 'budget_ms', 'reserve_ms', 'inference_scale', 'scale_mode', 'kernel', 'threads', 'coarse_horizon',
        'default_source', 's_default_rule', 'c_star', 'sd1_manifest_sha256', 'sd1_checkpoint_sha256', 'sd1_calibration_sha256',
        'sd1_threshold', 'opponent_checkpoint_sha256', 'native_sha256', 'runtime_pin_sha256', 'freeze_manifest_sha256',
        'population', 'seed', 'seed_index', 'cell', 'seat', 'rotation', 'block_id', 'replacement_k', 'scale_sleep_seconds',
        'scale_sleeps', 'slot', 'slot_cores', 'attempt_dir')
# Fields compared between runtimes under the virtual clock (T1 lacks the K4S-only additions).
INJECTED_FIELDS = ('hit', 'fallback', 'completed', 'candidates', 'unpruned_candidate_count', 'fallback_action', 'decision_tick',
                   'action', 'wall_seconds', 'wall_overrun', 'overrun_seconds', 'delayed_ticks')


IDENT = ('seed', 'seed_index', 'population', 'cell', 'seat', 'own_deck', 'opponent_deck', 'deadline_seconds', 'threads', 'kernel', 'arm', 'coarse_horizon')
HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE/'plan.json').read_text())
DECKS = json.loads((HERE/'guard-decks.json').read_text())
QUAL_BASE = 4503605837370496
import hashlib
SD1_SHA = hashlib.sha256((HERE/'SD1-MANIFEST.json').read_bytes()).hexdigest()


def project(path):
    raw = json.loads(Path(path).read_text())
    m = raw['metadata']; s = raw['search_ab']
    return dict(name=Path(path).name, arm=raw['cohort'], meta={k: m.get(k) for k in META if k in m}, missing_meta=[k for k in META if k not in m],
                ident={k: m.get(k) for k in IDENT}, placement=dict(affinity=s['worker_affinity'], nice=s['nice'], scheduler=s['scheduler']),
                latency_count=len(s['latency_seconds']),
                command=s['command_sha256'], stats=s['deadline_stats'], cache=s.get('policy_cache_counts'),
                gc_in_decision=sum(bool(e['during_decision']) for e in s['gc_maintenance']))


def expected_identity(runtime, mode, index, arm):
    """Outcome-free identity/configuration each qualification game must carry (mode overrides made explicit)."""
    pop = 'primary' if index in (0, 2, 4, 5, 6) else 'guard'
    cell = index % (50 if pop == 'primary' else 18)
    if pop == 'primary':
        own, opp = DECKS['primary'][cell % 5], DECKS['primary'][(cell//5) % 5]
    else:
        own, opp = DECKS['l2'][(cell//2) % 3], DECKS['guard'][cell//6]['cards']
    spec = PLAN['arms'][arm]
    deadline = dict(nodeadline=None, injected=0.2, zero=0.0).get(mode, spec['deadline_seconds'])
    threads = 1 if mode == 'injected' else 4
    kernel = 'K2-anytime' if runtime == 't1' else spec['kernel']
    ident = dict(seed=QUAL_BASE+index, seed_index=index, population='qualification', cell=cell, seat=cell % 2,
                 own_deck=sorted(own), opponent_deck=sorted(opp), deadline_seconds=deadline, threads=threads, kernel=kernel, arm=arm,
                 coarse_horizon=160)
    student = PLAN['student']
    extra = {} if runtime == 't1' else dict(speed_cell=spec['speed_cell'], budget_ms=200 if mode == 'zero' else spec['budget_ms'],
                                           inference_scale=1.0 if mode == 'zero' else spec['inference_scale'], scale_mode='poll',
                                           default_source=spec['default_source'], s_default_rule=spec['s_default_rule'], c_star=PLAN['c_star'],
                                           reserve_ms=8, sd1_manifest_sha256=SD1_SHA, sd1_checkpoint_sha256=student['checkpoint_sha256'],
                                           sd1_calibration_sha256=student['calibration_sha256'], sd1_threshold=student['threshold'],
                                           opponent_checkpoint_sha256=PLAN['policy']['checkpoint_sha256'],
                                           native_sha256=PLAN['source_reference']['native_sha256'], freeze_manifest_sha256=None,
                                           block_id=f'qualification-{index:04d}', rotation=None, replacement_k=None)
    return ident, extra


def identity_errors(g, runtime, mode, index, arm, receipts, group_dir):
    # The expected arm comes from the required inventory (file name), never from the evidence itself.
    errs = [] if g['arm'] == arm else [f"{g['name']}: cohort {g['arm']!r} != required arm {arm!r}"]
    ident, extra = expected_identity(runtime, mode, index, arm)
    got = dict(g['ident'], own_deck=sorted(g['ident']['own_deck'] or []), opponent_deck=sorted(g['ident']['opponent_deck'] or []))
    errs += [f"{g['name']}: {k} {got.get(k)!r} != {v!r}" for k, v in ident.items() if got.get(k) != v]
    errs += [f"{g['name']}: {k} {g['meta'].get(k)!r} != {v!r}" for k, v in extra.items() if g['meta'].get(k) != v]
    cores = receipts.get(index)
    if cores is None: errs.append(f"{g['name']}: no driver receipt")
    else:
        width = 1 if ident['threads'] == 1 else ident['threads']+1
        if g['placement']['affinity'] != cores[:width] or g['placement']['nice'] not in (10, 19) or g['placement']['scheduler'] != 0:
            errs.append(f"{g['name']}: placement {g['placement']}")
        if runtime == 'k4s' and (g['meta'].get('slot') != cores[0]//5 or g['meta'].get('slot_cores') != cores or g['meta'].get('attempt_dir') != str(group_dir)):
            errs.append(f"{g['name']}: slot/attempt fields")
    if mode == 'nodeadline':
        if g['stats'] or not g['latency_count']: errs.append(f"{g['name']}: no-deadline decisions")
    elif not g['stats']: errs.append(f"{g['name']}: no decisions")
    return errs


def path_of(d):
    if d.get('preparation_cutoff'):
        return d['preparation_cutoff']
    return 'scored' if d['scored'] else 'unscored'


GROUP = {'t1-nd': ('t1', 'nodeadline'), 'k4s-nd-p0': ('k4s', 'nodeadline'), 'k4s-nd-g1': ('k4s', 'nodeadline'),
         't1-inj': ('t1', 'injected'), 'k4s-inj': ('k4s', 'injected'), 'k4s-ch-p2': ('k4s', 'charged'), 'k4s-ch-g3': ('k4s', 'charged'),
         'k4s-zero': ('k4s', 'zero')}
IDENTITY_ERRORS = []


def games(G, d, expect):
    found = {Path(p).name: p for p in glob.glob(str(G/d/'games/*.json'))}
    want = {f'qualification-{i:04d}-d27-{a}.json' for i, a in expect}
    # Placement comes from the canonical task slots (qual_tasks), not from receipts the evidence supplies.
    receipts = {t[4]: cores(t[6]) for t in TASKS.values() if t[0] == d}
    out = {n: project(p) for n, p in found.items()}
    runtime, mode = GROUP[d]
    for n, g in out.items():
        IDENTITY_ERRORS.extend(identity_errors(g, runtime, mode, int(n.split('-')[1]), n.split('-d27-')[1][:-len('.json')], receipts, G/d))
    return out, sorted(set(found) ^ want)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--games', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tolerance', type=float, default=0.02); a = ap.parse_args()
    G = a.games; out = dict(nodeadline={}, injected={}, charged={}, zero={}, inventory_errors={}, errors=[])
    def need(d, expect):
        g, diff = games(G, d, expect)
        if diff: out['inventory_errors'][d] = diff; out['errors'].append(f'inventory {d}: {diff}')
        return g
    # No deadline.
    t1 = need('t1-nd', [(0, 'K4-200'), (1, 'K4-200')])
    for d, i in (('k4s-nd-p0', 0), ('k4s-nd-g1', 1)):
        k = need(d, [(i, 'K4-200'), (i, 'K4S-200')])
        try:
            row = dict(t1_K4_200=t1[f'qualification-{i:04d}-d27-K4-200.json']['command'],
                       k4s_K4_200=k[f'qualification-{i:04d}-d27-K4-200.json']['command'],
                       k4s_K4S_200=k[f'qualification-{i:04d}-d27-K4S-200.json']['command'])
        except KeyError:
            continue
        row['k4_equals_t1'] = row['t1_K4_200'] == row['k4s_K4_200']; row['k4s_equals_k4'] = row['k4s_K4_200'] == row['k4s_K4S_200']
        out['nodeadline'][d] = row
        if not (row['k4_equals_t1'] and row['k4s_equals_k4']): out['errors'].append('nodeadline hash mismatch '+d)
    # Injected (virtual clock), full runner.
    ti = need('t1-inj', [(5, 'K4-200'), (7, 'K4-200')]); ki = need('k4s-inj', [(5, 'K4-200'), (7, 'K4-200')])
    cover = collections.Counter()
    for n in sorted(set(ti) & set(ki)):
        x, y = ti[n], ki[n]
        same_cmd = x['command'] == y['command'] and len(x['stats']) == len(y['stats']) > 0
        diffs = [i for i, (u, v) in enumerate(zip(x['stats'], y['stats'])) if any(u.get(f) != v.get(f) for f in INJECTED_FIELDS)
                 or bool(u.get('preparation_cutoff')) != bool(v.get('preparation_cutoff'))]
        for v in y['stats']:
            cover['decisions'] += 1; cover['hit'] += bool(v['hit']); cover['overrun'] += bool(v['wall_overrun'])
            cover[path_of(v)] += 1; cover['scored_hit'] += bool(v['hit'] and v['scored'])
        out['injected'][n] = dict(command_equal=x['command'] == y['command'], decisions=len(y['stats']), field_mismatches=len(diffs))
        if not same_cmd or diffs: out['errors'].append(f'injected mismatch {n}')
    out['injected_coverage'] = dict(cover)
    if not (cover['scored_hit'] and cover['overrun'] and (cover['belief'] or cover['sample'] or cover['prescan'])):
        out['errors'].append('injected coverage: need scored cutoffs, overruns and a preparation cutoff')
    # Charged.
    shares = collections.defaultdict(list); paths = collections.defaultdict(set)
    for d, i in (('k4s-ch-p2', 2), ('k4s-ch-g3', 3)):
        for n, g in need(d, [(i, arm) for arm in ARMS]).items():
            c = g['meta'].get('speed_cell')
            if g['missing_meta']: out['errors'].append(f"missing metadata {n} {g['missing_meta']}")
            if not g['stats']: out['errors'].append('no decisions '+n); continue
            if g['gc_in_decision']: out['errors'].append('GC in decision '+n)
            if g['cache'] is not None and g['cache']['forward'] != g['cache']['fallback']: out['errors'].append('forward caching '+n)
            sd1 = g['meta'].get('default_source') == 'SD1'
            for s in g['stats']:
                miss = [f for f in FIELDS if f not in s]
                if miss: out['errors'].append(f'missing fields {n} {miss}'); break
                p = path_of(s); paths[g['arm']].add(p)
                bad = sd1_errors(s, PLAN['arms'][g['arm']])  # the same outcome-blind validator smoke uses (finding 20)
                if bad: out['errors'].append(f'decision fields {n}: {bad}'); break
                if s['overrun_seconds'] != max(0., s['wall_seconds']-g['meta']['budget_ms']/1000) or s['delayed_ticks'] != math.ceil(s['overrun_seconds']*20):
                    out['errors'].append('honest lateness '+n)
                if (s['frozen_action'] is None) == (p == 'scored'): out['errors'].append(f'frozen_action nullability {n} {p}')
                if sd1:
                    # The coarse order is built after the belief update, so a belief cutoff has none.
                    if (s['sd1_default_action'] != s['fallback_action'] or s['sd1_p_play'] is None
                            or (s['coarse_order_sha256'] is None) != (p == 'belief')):
                        out['errors'].append('SD1 fields '+n); break
                    if s.get('preparation_cutoff') and s['action'] != (s['sd1_default_action'] if s['sd1_default_action'] < 2305 else 2304):
                        out['errors'].append('K4S preparation cutoff did not return SD1 default '+n)
                elif s['sd1_default_action'] is not None or s['sd1_p_play'] is not None or s['coarse_order_sha256'] is not None:
                    out['errors'].append('K4 decision carries SD1 fields '+n); break
                if c == 1.0:
                    if s['scale_sleep_seconds'] != 0.: out['errors'].append('charge at c=1 '+n)
                    continue
                shares[(g['arm'], c, p)].append(s['scale_sleep_seconds']/(s['poll_seconds']+s['scale_sleep_seconds'])-(1-c))
    within = bool(shares)
    for (arm, c, p), dev in sorted(shares.items()):
        bad = sum(abs(x) > a.tolerance for x in dev)
        out['charged'][f'{arm}|{p}'] = dict(cell=c, n=len(dev), mean_dev=statistics.fmean(dev), max_abs_dev=max(map(abs, dev)), outside_tolerance=bad)
        within &= abs(statistics.fmean(dev)) <= a.tolerance and bad == 0
    out['charged_all_within_tolerance'] = within
    if not within: out['errors'].append('charge share outside tolerance (or no charged decisions)')
    out['charged_paths_seen'] = {k: sorted(v) for k, v in sorted(paths.items())}
    if any('scored' not in v for v in paths.values()) or len(paths) != len(ARMS): out['errors'].append('charged: an arm lacks scored decisions')
    if not any(p in v for v in paths.values() for p in ('belief', 'sample', 'prescan')): out['errors'].append('charged: no preparation-cutoff path seen')
    # Zero budget.
    for n, g in need('k4s-zero', [(4, 'K4S-200'), (4, 'K4S-120')]).items():
        if g['missing_meta']: out['errors'].append(f"missing metadata {n} {g['missing_meta']}")
        ok = plays = 0
        for s in g['stats']:
            expect = s['sd1_default_action'] if s['sd1_default_action'] < 2305 else 2304
            ok += s['action'] == expect and s['hit'] and s['student_default'] == (expect < 2304) and s['scale_sleep_seconds'] == 0.
            plays += expect < 2304
        out['zero'][n] = dict(decisions=len(g['stats']), sd1_default_returned=ok, sd1_plays=plays, paths=dict(collections.Counter(path_of(s) for s in g['stats'])))
        if not g['stats'] or ok != len(g['stats']): out['errors'].append('zero budget '+n)
    # Every checked game must be bound to exactly one canonical driver receipt with its hash (Sol core r3 finding 15).
    receipt_errors, bound = validate_receipts(G, lambda p: json.loads(Path(p).read_text()), lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
    unbound = sorted(f'{g}/{n}' for g, n in expected_games() if (g, n) not in bound)
    out['receipt_errors'] = receipt_errors; out['unbound_games'] = unbound
    if receipt_errors or unbound: out['errors'].append(f'driver receipts: {len(receipt_errors)} errors, {len(unbound)} unbound games')
    out['bound_game_sha256'] = {f'{g}/{n}': h for (g, n), h in sorted(bound.items())}
    # Every K4S game was produced under this job's runtime pin (Sol core r4 finding 19).
    job = Path(G).resolve().parents[1]
    pin_sha = hashlib.sha256((job/'runtime-pin.json').read_bytes()).hexdigest() if (job/'runtime-pin.json').exists() else None
    bad_pins = sorted(n for d in GROUP if GROUP[d][0] == 'k4s' for n, p in ((Path(p).name, p) for p in glob.glob(str(G/d/'games/*.json')))
                      if json.loads(Path(p).read_text())['metadata'].get('runtime_pin_sha256') != pin_sha)
    out['runtime_pin_sha256_ok'] = pin_sha is not None and not bad_pins
    if not out['runtime_pin_sha256_ok']: out['errors'].append(f'runtime pin: {bad_pins[:5]}')
    out['identity_errors'] = IDENTITY_ERRORS[:50]
    if IDENTITY_ERRORS: out['errors'].append(f'identity/configuration: {len(IDENTITY_ERRORS)} errors')
    out['passed'] = not out['errors']
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(passed=out['passed'], errors=out['errors'][:10])))
    sys.exit(0 if out['passed'] else 1)


if __name__ == '__main__':
    main()
