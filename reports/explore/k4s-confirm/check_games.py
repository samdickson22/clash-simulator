"""PREREG-K4S: outcome-blind checks of qualification/smoke game files (r3 §4.1).

Reads only an explicit projection: cohort, metadata identity/config fields, search_ab.command_sha256 and
search_ab.deadline_stats. Never reads loss, winner, crowns or any outcome field.

  nodeadline : command hashes, K4 under K4S runtime == T1 K4-200 and K4S-200 == K4-200, per seed.
  charged    : sleep share scale_sleep/(poll+scale_sleep) == 1-c +- 0.02 on every exit path
               (belief / prescan / sample cutoff, scored, single candidate); every r3 §3.6 field present.
  zero       : every K4S decision returns the SD1 default, flagged student_default iff it is a play.
"""
import argparse, collections, glob, json, math, statistics
from pathlib import Path

FIELDS = ('hit', 'fallback', 'completed', 'candidates', 'unpruned_candidate_count', 'own_elixir', 'fallback_action', 'threads',
          'coarse_horizon', 'default_source', 'wall_overrun', 'overrun_seconds', 'delayed_ticks', 'decision_tick', 'action',
          'wall_seconds', 'cpu_seconds', 'coarse_complete', 'coarse_scored', 'plays', 'frozen_action', 'student_default',
          'sd1_default_action', 'sd1_p_play', 'coarse_order_sha256', 'chosen_action', 'fallback_used', 'selected_wait_ticks',
          'poll_seconds', 'scale_sleep_seconds', 'prep_seconds', 'scored', 'positive_overrun_ms', 'charged_extra_ticks')
META = ('study', 'speed_cell', 'budget_ms', 'reserve_ms', 'inference_scale', 'scale_mode', 'kernel', 'threads', 'coarse_horizon',
        'default_source', 's_default_rule', 'c_star', 'sd1_manifest_sha256', 'sd1_checkpoint_sha256', 'sd1_calibration_sha256',
        'sd1_threshold', 'opponent_checkpoint_sha256', 'native_sha256', 'runtime_pin_sha256', 'freeze_manifest_sha256',
        'population', 'seed', 'seed_index', 'cell', 'seat', 'rotation', 'block_id', 'replacement_k', 'scale_sleep_seconds', 'scale_sleeps')


def project(path):
    raw = json.loads(Path(path).read_text())
    m = raw['metadata']; s = raw['search_ab']
    return dict(arm=raw['cohort'], meta={k: m.get(k) for k in META if k in m}, missing_meta=[k for k in META if k not in m],
                command=s['command_sha256'], stats=s['deadline_stats'], cache=s.get('policy_cache_counts'),
                gc_in_decision=sum(bool(e['during_decision']) for e in s['gc_maintenance']))


def path_of(d):
    if d.get('preparation_cutoff'):
        return d['preparation_cutoff']
    return 'scored' if d['scored'] else 'unscored'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--games', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tolerance', type=float, default=0.02); a = ap.parse_args()
    G = a.games; out = dict(nodeadline={}, charged={}, zero={}, errors=[])
    # No deadline: command hashes.
    t1 = {Path(p).name: project(p) for p in glob.glob(str(G/'t1-nd/games/*.json'))}
    for d in ('k4s-nd-p0', 'k4s-nd-g1'):
        k = {project(p)['arm']: project(p) for p in glob.glob(str(G/d/'games/*.json'))}
        ref = [v for n, v in t1.items() if n.startswith(('qualification-0000' if d.endswith('p0') else 'qualification-0001'))]
        assert len(ref) == 1 and set(k) == {'K4-200', 'K4S-200'}, (d, len(ref), set(k))
        row = dict(t1_K4_200=ref[0]['command'], k4s_K4_200=k['K4-200']['command'], k4s_K4S_200=k['K4S-200']['command'])
        row['k4_equals_t1'] = row['t1_K4_200'] == row['k4s_K4_200']
        row['k4s_equals_k4'] = row['k4s_K4_200'] == row['k4s_K4S_200']
        out['nodeadline'][d] = row
        if not (row['k4_equals_t1'] and row['k4s_equals_k4']): out['errors'].append('nodeadline hash mismatch '+d)
    # Charged: share per exit path, fields.
    shares = collections.defaultdict(list)
    for d in ('k4s-ch-p2', 'k4s-ch-g3'):
        for p in sorted(glob.glob(str(G/d/'games/*.json'))):
            g = project(p); c = g['meta']['speed_cell']
            if g['missing_meta']: out['errors'].append(f"missing metadata {g['arm']} {g['missing_meta']}")
            if g['gc_in_decision']: out['errors'].append('GC in decision '+g['arm'])
            if g['cache'] is not None and g['cache']['forward'] != g['cache']['fallback']: out['errors'].append('forward caching '+g['arm'])
            for s in g['stats']:
                miss = [f for f in FIELDS if f not in s]
                if miss: out['errors'].append(f"missing fields {g['arm']} {miss}"); break
                if s['overrun_seconds'] != max(0., s['wall_seconds']-g['meta']['budget_ms']/1000) or s['delayed_ticks'] != math.ceil(s['overrun_seconds']*20):
                    out['errors'].append('honest lateness '+g['arm'])
                if g['meta']['default_source'] == 'SD1':
                    # The coarse order is built after the belief update, so a belief cutoff has none.
                    if (s['sd1_default_action'] != s['fallback_action'] or s['sd1_p_play'] is None
                            or (s['coarse_order_sha256'] is None) != (path_of(s) == 'belief')):
                        out['errors'].append('SD1 fields '+g['arm']); break
                    if s.get('preparation_cutoff') and s['action'] != (s['sd1_default_action'] if s['sd1_default_action'] < 2305 else 2304):
                        out['errors'].append('K4S preparation cutoff did not return SD1 default '+g['arm'])
                if c == 1.0:
                    if s['scale_sleep_seconds'] != 0.: out['errors'].append('charge at c=1 '+g['arm'])
                    continue
                share = s['scale_sleep_seconds']/(s['poll_seconds']+s['scale_sleep_seconds'])
                shares[(g['arm'], c, path_of(s))].append(share-(1-c))
    within = True
    for (arm, c, path), dev in sorted(shares.items()):
        bad = sum(abs(x) > a.tolerance for x in dev)
        out['charged'][f'{arm}|{path}'] = dict(cell=c, n=len(dev), mean_dev=statistics.fmean(dev), max_abs_dev=max(map(abs, dev)),
                                               outside_tolerance=bad, mean_within=abs(statistics.fmean(dev)) <= a.tolerance)
        within &= abs(statistics.fmean(dev)) <= a.tolerance and bad == 0
    out['charged_all_within_tolerance'] = within
    if not within: out['errors'].append('charge share outside tolerance')
    paths = {k.split('|')[1] for k in out['charged']}
    out['charged_paths_seen'] = sorted(paths)
    # Zero budget: SD1 default every decision.
    for p in sorted(glob.glob(str(G/'k4s-zero/games/*.json'))):
        g = project(p); n = len(g['stats']); ok = 0; plays = 0
        for s in g['stats']:
            expect = s['sd1_default_action'] if s['sd1_default_action'] < 2305 else 2304
            if s['action'] == expect and s['hit'] and s['student_default'] == (expect < 2304) and s['scale_sleep_seconds'] == 0.:
                ok += 1
            plays += expect < 2304
        out['zero'][g['arm']] = dict(decisions=n, sd1_default_returned=ok, sd1_plays=plays, paths=dict(collections.Counter(path_of(s) for s in g['stats'])))
        if ok != n or n == 0: out['errors'].append('zero budget '+g['arm'])
    out['passed'] = not out['errors']
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(passed=out['passed'], errors=out['errors'][:10], paths=out.get('charged_paths_seen'))))


if __name__ == '__main__':
    main()
