"""X4S-3 reducer (exploration, NEVER ADOPTABLE). Pure stdlib; runs on the job dir or its 05 mirror.

Counts a game only via its block proof (SHA-matched). A student is reduced only when every
non-retired index is terminal in both arms (fixed N). Paired seeds = indices complete for every
reduced (student, arm). Shared paired-seed bootstrap (5,000 reps, seed 2026101201), percentile 95%
CIs, unadjusted. Pooled contrasts weight K4S-120 and S-200 equally per seed (stratified by arm).
"""
import argparse, hashlib, json, math, random, subprocess
from collections import Counter
from pathlib import Path

ARMS = ('K4S-120', 'S-200')
ORDER = ('R3a', 'R4-D', 'R3a-rep', 'R4-DC')
PAIRS = (('R4-D', 'R3a'), ('R3a-rep', 'R3a'), ('R4-D', 'R3a-rep'), ('R4-DC', 'R4-D'), ('R4-DC', 'R3a'))


def utc(): return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()
def pct(xs, q):
    xs = sorted(xs)
    if not xs: return 0.
    k = (len(xs)-1)*q/100; f = math.floor(k); c = min(f+1, len(xs)-1)
    return xs[f]+(xs[c]-xs[f])*(k-f)
def ci(xs): return [pct(xs, 2.5), pct(xs, 97.5)]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_student(job, sid, plan, retired, checks):
    rt = json.loads((job/f'rt-{sid}'/'READY.json').read_text())['student'] if sid != 'R3a' else plan['student']
    base = plan['seed_ranges']['reporting']['base']; rows = {}
    for arm in ARMS:
        sp = plan['arms'][arm]; width = 1 if sp['threads'] == 1 else 5
        rows[arm] = {}
        for d in sorted((job/'games'/sid/arm).glob('a*')):
            if not d.is_dir(): continue
            sched = json.loads((d/'schedule.json').read_text())
            assert sched['range'] == 'reporting' and all(c[2] == arm for c in sched['cases']), d
            for proof_path in sorted((d/'blocks').glob('*.json')):
                proof = json.loads(proof_path.read_text()); i = proof['index']
                assert i not in rows[arm], ('duplicate', sid, arm, i)
                assert proof['seed'] == base+i and proof['order'] == [arm] and len(proof['slot_cores']) == width
                p = d/'games'/f'sim-{i:04d}-d27-{arm}.json'
                assert sha(p) == proof['games'][p.name]
                r = json.loads(p.read_text()); m = r['metadata']; s = r['search_ab']
                assert m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == 'v1-policy'
                assert m['student_id'] == sid and m['checkpoint_sha256'] == rt['checkpoint_sha256'] and m['study'].startswith('X4S-3')
                assert m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['deadline_seconds']*1000)
                assert m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_lateness']
                assert r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])
                assert m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1
                assert s['worker_affinity'] == proof['slot_cores'][:width] and set(proof['slot_cores']) <= set(range(50))
                assert s['nice'] == 10 and s['scheduler'] == 0 and s['host'] == '127x01' and s['worker_pid'] == proof['worker_pid']
                assert all(not e['during_decision'] for e in s.get('gc_maintenance', []))
                pc = s['policy_cache_counts']; assert pc['forward'] == pc['fallback'] == s['policy_polls'][str(m['seat'])]
                for wall, dd in zip(s['latency_seconds'], s['deadline_stats']):
                    over = max(0., wall-sp['deadline_seconds'])
                    assert dd['wall_seconds'] == wall and dd['overrun_seconds'] == over and dd['delayed_ticks'] == math.ceil(over*20)
                    checks['decisions'] += 1
                assert len(s['latency_seconds']) == len(s['deadline_stats'])
                rows[arm][i] = r; checks['games'] += 1
    need = set(range(plan['seed_ranges']['reporting']['count'])) - retired
    complete = all(need <= set(rows[a]) for a in ARMS)
    return rows, complete


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--students', nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    plan = json.loads((a.job/'base/repo/reports/explore/x4s3/plan.json').read_text()) if (a.job/'base').exists() else \
        json.loads((Path(__file__).parent/'plan.json').read_text())
    retired_doc = json.loads((a.job/'driver'/'retired.json').read_text()) if (a.job/'driver'/'retired.json').exists() else dict(indices=[], why=[])
    retired = set(retired_doc['indices'])
    checks = Counter(); data = {}
    for sid in a.students:
        rows, complete = load_student(a.job, sid, plan, retired, checks)
        assert complete, f'{sid}: not every non-retired index is terminal in both arms (fixed N)'
        data[sid] = rows
    idx = sorted(set.intersection(*[set(data[s][arm]) for s in data for arm in ARMS]))
    n = len(idx); assert n > 0
    for i in idx:  # identical deck/seat pairing across every (student, arm)
        keys = {(tuple(data[s][arm][i]['metadata']['own_deck']), tuple(data[s][arm][i]['metadata']['opponent_deck']),
                 data[s][arm][i]['metadata']['seat']) for s in data for arm in ARMS}
        assert len(keys) == 1, i
    rng = random.Random(plan['bootstrap']['seed'])
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(plan['bootstrap']['reps'])]
    loss = {(s, arm): [data[s][arm][i]['loss'] for i in idx] for s in data for arm in ARMS}
    out = dict(utc=utc(), label='X4S-3 exploration, NEVER ADOPTABLE', paired_seeds=n, students=list(data),
               retired=sorted(retired), checks=dict(checks), bootstrap=plan['bootstrap'],
               cells=dict(Counter(str(i % 50) for i in idx)), arms={}, contrasts={})
    for s in data:
        for arm in ARMS:
            rs = [data[s][arm][i] for i in idx]; budget = plan['arms'][arm]['deadline_seconds']
            ds = [d for r in rs for d in r['search_ab']['deadline_stats']]
            dec = [len(r['search_ab']['deadline_stats']) for r in rs]
            def rate(f):
                num = [sum(1 for d in r['search_ab']['deadline_stats'] if f(d)) for r in rs]
                return 100*sum(num)/max(1, sum(dec)), ci([100*sum(num[j] for j in smp)/max(1, sum(dec[j] for j in smp)) for smp in samples])
            L = loss[(s, arm)]
            entry = dict(losses=int(sum(L)), wins=sum(r['metadata']['winner'] == r['metadata']['seat'] for r in rs),
                         draws=sum(r['metadata']['winner'] is None for r in rs), loss_pct=100*sum(L)/n,
                         loss_ci_pct=ci([100*sum(L[j] for j in smp)/n for smp in samples]), decisions=sum(dec),
                         wall_ms_p50=pct([1000*d['wall_seconds'] for d in ds], 50), wall_ms_p99=pct([1000*d['wall_seconds'] for d in ds], 99),
                         returns_past_budget_plus_reserve=sum(d['wall_seconds'] > budget+.008 for d in ds),
                         game_cpu_hours=sum(r['cpu_seconds'] for r in rs)/3600)
            for name, f in (('cutoff', lambda d: d['hit']), ('student_default', lambda d: d.get('student_default', False)),
                            ('play', lambda d: d['action'] < 2304), ('overrun', lambda d: d['wall_overrun']), ('fallback', lambda d: d['fallback'])):
                v, c = rate(f); entry[name+'_pct'] = v; entry[name+'_ci_pct'] = c
            out['arms'][f'{s} {arm}'] = entry
    def per_seed(s, arm): return loss[(s, arm)]
    for l, r in PAIRS:
        if l not in data or r not in data: continue
        for arm in ARMS:
            dl, dr = per_seed(l, arm), per_seed(r, arm)
            out['contrasts'][f'{l} minus {r} [{arm}]'] = dict(loss_change_pp=100*(sum(dl)-sum(dr))/n,
                ci95_pp=ci([100*sum(dl[j]-dr[j] for j in smp)/n for smp in samples]))
        pooled = [sum(per_seed(l, arm)[k]-per_seed(r, arm)[k] for arm in ARMS)/len(ARMS) for k in range(n)]
        out['contrasts'][f'{l} minus {r} [pooled]'] = dict(loss_change_pp=100*sum(pooled)/n,
            ci95_pp=ci([100*sum(pooled[j] for j in smp)/n for smp in samples]))
    c = out['contrasts']
    if 'R4-D minus R3a [pooled]' in c and 'R4-D minus R3a-rep [pooled]' in c:
        out['readout'] = dict(data_helps=c['R4-D minus R3a [pooled]']['ci95_pp'][1] < 0 and c['R4-D minus R3a-rep [pooled]']['loss_change_pp'] < 0,
                              rule='upper95CI(R4-D minus R3a, pooled) < 0 AND point(R4-D minus R3a-rep, pooled) < 0')
    if 'R3a-rep minus R3a [pooled]' in c:
        out.setdefault('readout', {})['fit_seed_noise_ge_4pp'] = {k: abs(v['loss_change_pp']) >= 4 for k, v in c.items() if k.startswith('R3a-rep minus R3a')}
    if 'R4-DC minus R4-D [pooled]' in c:
        out.setdefault('readout', {})['compute_scales_point'] = c['R4-DC minus R4-D [pooled]']['loss_change_pp'] < 0
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ('utc', 'paired_seeds', 'students', 'checks')}))


if __name__ == '__main__':
    main()
