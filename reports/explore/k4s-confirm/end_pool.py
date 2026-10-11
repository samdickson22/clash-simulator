"""PREREG-K4S END pooling (r3 §4.5; delta 8): raw per-host END files -> clasher.k4s.mac-fleet-reference.v1.

Pooling rules (r3 §4.5):
- each host's ratio to the pool lies in [0.95, 1.05] inclusive, or the pool fails closed; hosts cannot be
  excluded after counting. Ratio = median over states of (host per-state median K4S no-deadline wall) /
  (pooled per-state median over every host x repeat);
- per-state pooled values are medians over all hosts x repeats (raw-host-times-repeat);
- deadline cells carry integer counts (n, cutoff, no-complete-play, fallback) over all hosts x repeats x states.
The independent re-check (T1 check_reference.py pattern) recomputes this file from the same raw inputs.
"""
import argparse, hashlib, json, statistics
from fractions import Fraction
from pathlib import Path

LOW, HIGH = Fraction(95, 100), Fraction(105, 100)


def pool(raws, end_recheck_sha256=None):
    hosts = [r['host'] for r in raws]
    assert len(hosts) == len(set(hosts)) >= 1, 'one raw file per host'
    corpus = {r['corpus_sha256'] for r in raws}; assert len(corpus) == 1
    assert all(r['repeats'] == 3 for r in raws)
    ids = sorted(raws[0]['states']); assert all(sorted(r['states']) == ids for r in raws), 'every host measures every state'
    states = {}
    for i in ids:
        rows = [r['states'][i] for r in raws]
        results = [json.dumps(x['result'], sort_keys=True) for x in rows]; assert len(set(results)) == 1, f'fleet exactness {i}'
        states[i] = dict(k4s_wall_seconds=statistics.median([v for x in rows for v in x['k4s_wall']]),
                         sd1_poll_seconds=statistics.median([v for x in rows for v in x['sd1_poll']]),
                         k4_wall_seconds=statistics.median([v for x in rows for v in x['k4_wall']]),
                         v1_poll_seconds=statistics.median([v for x in rows for v in x['v1_poll']]),
                         result=rows[0]['result'])
    ratios = {}
    for r in raws:
        per = [statistics.median(r['states'][i]['k4s_wall'])/states[i]['k4s_wall_seconds'] for i in ids]
        ratios[r['host']] = statistics.median(per)
    conforms = all(LOW <= Fraction(v).limit_denominator(10**9) <= HIGH for v in ratios.values())
    deadline = {}
    for cell in ('1.0', '0.9', '0.8', '0.7', '0.6'):
        heads = {(r['deadline'][cell]['budget_ms'], r['deadline'][cell]['charge_scale']) for r in raws}; assert len(heads) == 1
        rows = [x for r in raws for x in r['deadline'][cell]['rows']]
        n = len(rows); assert n == 3*len(ids)*len(raws)
        c = dict(cutoff_count=sum(x['cutoff'] for x in rows), no_complete_play_count=sum(x['no_complete_play'] for x in rows),
                 fallback_count=sum(x['fallback'] for x in rows))
        budget, scale = heads.pop()
        deadline[cell] = dict(budget_ms=budget, charge_scale=scale, n=n, **c,
                              **{k.replace('_count', '_rate'): v/n for k, v in c.items()})
    return dict(schema='clasher.k4s.mac-fleet-reference.v1', corpus_sha256=corpus.pop(), repeats=3, reporting_load_profile=True,
                hosts=hosts, host_ratio_to_pool=ratios, ratio_window=[0.95, 1.05], pool_conforms=conforms,
                end_recheck_sha256=end_recheck_sha256, states=states, deadline=deadline)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--raw', type=Path, nargs='+', required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--end-recheck-sha256'); a = ap.parse_args()
    out = pool([json.loads(p.read_text()) for p in a.raw], a.end_recheck_sha256)
    out['raw_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in a.raw}
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(pool_conforms=out['pool_conforms'], ratios=out['host_ratio_to_pool'])))
    if not out['pool_conforms']: raise SystemExit('pool fails closed (r3 §4.5): re-run or coordinator ratio-unavailable declaration')


if __name__ == '__main__':
    main()
