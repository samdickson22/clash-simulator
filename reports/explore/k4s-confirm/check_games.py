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


def project(path):
    raw = json.loads(Path(path).read_text())
    m = raw['metadata']; s = raw['search_ab']
    return dict(name=Path(path).name, arm=raw['cohort'], meta={k: m.get(k) for k in META if k in m}, missing_meta=[k for k in META if k not in m],
                command=s['command_sha256'], stats=s['deadline_stats'], cache=s.get('policy_cache_counts'),
                gc_in_decision=sum(bool(e['during_decision']) for e in s['gc_maintenance']))


def path_of(d):
    if d.get('preparation_cutoff'):
        return d['preparation_cutoff']
    return 'scored' if d['scored'] else 'unscored'


def games(G, d, expect):
    found = {Path(p).name: p for p in glob.glob(str(G/d/'games/*.json'))}
    want = {f'qualification-{i:04d}-d27-{a}.json' for i, a in expect}
    return {n: project(p) for n, p in found.items()}, sorted(set(found) ^ want)


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
    out['passed'] = not out['errors']
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(passed=out['passed'], errors=out['errors'][:10])))
    sys.exit(0 if out['passed'] else 1)


if __name__ == '__main__':
    main()
