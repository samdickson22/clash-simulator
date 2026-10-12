"""X4S-4 reducer (exploration, NEVER ADOPTABLE; PLAN r3, frozen at 87809ae0), derived from the X4S-3 reducer; stdlib only.

Counts a game only via its block proof (SHA-matched); asserts bank E (game metadata `study` reads X4S-3 because the
unchanged x4s3/run.py is reused). Requires the C5 contention receipt to exist (frozen before any reduction, E1) and
all four primary students. Fixed N: every non-retired index terminal in both arms for every reduced student, unless
--allow-prefix (E8 hard-stop cut: the largest seed-index prefix complete for the four primary students; R5W
secondaries use their own prefix and never cut the primary). Paired-seed bootstrap (5,000 reps, seed 2026101301),
percentile 95% CIs, unadjusted; pooled = equal arm weight.
Readout: primary Delta = mean(R5, R5-rep) - mean(R3a, R3a-rep) with the three-way outcome (helps requires the pooled
single-fit points R5 - R3a and R5-rep - R3a < 0); fit-inflated interval with sigma_fit fixed at 0.65 (E3); harmful
sub-label (E9); attribution sub-label from the CI of mean(R5, R5-rep) - R5W (E4, default unresolved); 2-df sigma_fit;
the C5 contention-excluded view; the E10 parity table (disclosed, no exclusion).
"""
import argparse, hashlib, json, math, random, subprocess
from collections import Counter
from pathlib import Path

ARMS = ('K4S-120', 'S-200')
ORDER = ('R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W')
PAIRS = (('R5', 'R3a'), ('R5-rep', 'R3a'), ('R5', 'R3a-rep'), ('R3a-rep', 'R3a'), ('R5', 'R5-rep'), ('R5', 'R5W'), ('R5-rep', 'R5W'))
E_BASE, E_COUNT = 4503606307370496, 1200


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
            if not (sched['range'] == 'reporting' and all(c[2] == arm for c in sched['cases'])): raise SystemExit(d)
            for proof_path in sorted((d/'blocks').glob('*.json')):
                proof = json.loads(proof_path.read_text()); i = proof['index']
                if not (i not in rows[arm]): raise SystemExit(('duplicate', sid, arm, i))
                if not (proof['seed'] == base+i and proof['order'] == [arm] and len(proof['slot_cores']) == width): raise SystemExit("reduce.py: check failed: proof['seed'] == base+i and proof['order'] == [arm] and len(proof['slot_cores']) == width")
                p = d/'games'/f'sim-{i:04d}-d27-{arm}.json'
                if not (sha(p) == proof['games'][p.name]): raise SystemExit("reduce.py: check failed: sha(p) == proof['games'][p.name]")
                r = json.loads(p.read_text()); m = r['metadata']; s = r['search_ab']
                if not (m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == 'v1-policy'): raise SystemExit("reduce.py: check failed: m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == '")
                if not (m['student_id'] == sid and m['checkpoint_sha256'] == rt['checkpoint_sha256'] and m['study'].startswith('X4S-3')): raise SystemExit("reduce.py: check failed: m['student_id'] == sid and m['checkpoint_sha256'] == rt['checkpoint_sha256'] and m['study'].sta")
                if not (m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['deadline_seconds']*1000)): raise SystemExit("reduce.py: check failed: m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['de")
                if not (m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_lateness']): raise SystemExit("reduce.py: check failed: m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_laten")
                if not (r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])): raise SystemExit("reduce.py: check failed: r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])")
                if not (m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1): raise SystemExit("reduce.py: check failed: m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1")
                if not (s['worker_affinity'] == proof['slot_cores'][:width] and set(proof['slot_cores']) <= set(range(50))): raise SystemExit("reduce.py: check failed: s['worker_affinity'] == proof['slot_cores'][:width] and set(proof['slot_cores']) <= set(range(5")
                if not (s['nice'] == 10 and s['scheduler'] == 0 and s['host'] == '127x01' and s['worker_pid'] == proof['worker_pid']): raise SystemExit("reduce.py: check failed: s['nice'] == 10 and s['scheduler'] == 0 and s['host'] == '127x01' and s['worker_pid'] == proof[")
                if not (all(not e['during_decision'] for e in s.get('gc_maintenance', []))): raise SystemExit("reduce.py: check failed: all(not e['during_decision'] for e in s.get('gc_maintenance', []))")
                pc = s['policy_cache_counts']; assert pc['forward'] == pc['fallback'] == s['policy_polls'][str(m['seat'])]
                for wall, dd in zip(s['latency_seconds'], s['deadline_stats']):
                    over = max(0., wall-sp['deadline_seconds'])
                    if not (dd['wall_seconds'] == wall and dd['overrun_seconds'] == over and dd['delayed_ticks'] == math.ceil(over*20)): raise SystemExit("reduce.py: check failed: dd['wall_seconds'] == wall and dd['overrun_seconds'] == over and dd['delayed_ticks'] == math.ce")
                    checks['decisions'] += 1
                if not (len(s['latency_seconds']) == len(s['deadline_stats'])): raise SystemExit("reduce.py: check failed: len(s['latency_seconds']) == len(s['deadline_stats'])")
                rows[arm][i] = r; checks['games'] += 1
    need = set(range(plan['seed_ranges']['reporting']['count'])) - retired
    complete = all(need <= set(rows[a]) for a in ARMS)
    return rows, complete


PRIMARY = ('R3a', 'R3a-rep', 'R5', 'R5-rep')
SIGMA_FIT_FIXED = 0.65


def prefix(data, students, retired, n_total):
    """Largest seed-index prefix complete in both arms for every listed student (E8); retired seeds skipped."""
    out = []
    for i in range(n_total):
        if i in retired: continue
        if all(i in data[s][arm] for s in students for arm in ARMS): out.append(i)
        else: break
    return out


def analyze(data, students, idx, plan):
    n = len(idx); assert n > 0
    for i in idx:  # identical deck/seat pairing across every (student, arm)
        keys = {(tuple(data[s][arm][i]['metadata']['own_deck']), tuple(data[s][arm][i]['metadata']['opponent_deck']),
                 data[s][arm][i]['metadata']['seat']) for s in students for arm in ARMS}
        if not (len(keys) == 1): raise SystemExit(i)
    rng = random.Random(plan['bootstrap']['seed'])
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(plan['bootstrap']['reps'])]
    loss = {(s, arm): [data[s][arm][i]['loss'] for i in idx] for s in students for arm in ARMS}
    arms, contrasts = {}, {}
    for s in students:
        for arm in ARMS:
            rs = [data[s][arm][i] for i in idx]; budget = plan['arms'][arm]['deadline_seconds']
            ds = [d for r in rs for d in r['search_ab']['deadline_stats']]
            dec = [len(r['search_ab']['deadline_stats']) for r in rs]
            def rate(f):
                num = [sum(1 for d in r['search_ab']['deadline_stats'] if f(d)) for r in rs]
                return 100*sum(num)/max(1, sum(dec)), ci([100*sum(num[j] for j in smp)/max(1, sum(dec[j] for j in smp)) for smp in samples])
            L = loss[(s, arm)]
            e = dict(losses=int(sum(L)), wins=sum(r['metadata']['winner'] == r['metadata']['seat'] for r in rs),
                     draws=sum(r['metadata']['winner'] is None for r in rs), loss_pct=100*sum(L)/n,
                     loss_ci_pct=ci([100*sum(L[j] for j in smp)/n for smp in samples]), decisions=sum(dec),
                     wall_ms_p50=pct([1000*d['wall_seconds'] for d in ds], 50), wall_ms_p99=pct([1000*d['wall_seconds'] for d in ds], 99),
                     returns_past_budget_plus_reserve=sum(d['wall_seconds'] > budget+.008 for d in ds),
                     game_cpu_hours=sum(r['cpu_seconds'] for r in rs)/3600)
            for name, f in (('cutoff', lambda d: d['hit']), ('student_default', lambda d: d.get('student_default', False)),
                            ('play', lambda d: d['action'] < 2304), ('overrun', lambda d: d['wall_overrun']), ('fallback', lambda d: d['fallback'])):
                v, cc = rate(f); e[name+'_pct'] = v; e[name+'_ci_pct'] = cc
            arms[f'{s} {arm}'] = e
    for l, r in PAIRS:
        if l not in students or r not in students: continue
        for arm in ARMS:
            dl, dr = loss[(l, arm)], loss[(r, arm)]
            contrasts[f'{l} minus {r} [{arm}]'] = dict(loss_change_pp=100*(sum(dl)-sum(dr))/n,
                ci95_pp=ci([100*sum(dl[j]-dr[j] for j in smp)/n for smp in samples]))
        pooled = [sum(loss[(l, arm)][k]-loss[(r, arm)][k] for arm in ARMS)/len(ARMS) for k in range(n)]
        contrasts[f'{l} minus {r} [pooled]'] = dict(loss_change_pp=100*sum(pooled)/n, ci95_pp=ci([100*sum(pooled[j] for j in smp)/n for smp in samples]))

    def delta(members_t, members_c):
        per = [sum(sum(loss[(t, arm)][k] for t in members_t)/len(members_t) - sum(loss[(u, arm)][k] for u in members_c)/len(members_c)
                   for arm in ARMS)/len(ARMS) for k in range(n)]
        boot = [100*sum(per[j] for j in smp)/n for smp in samples]
        mean = sum(boot)/len(boot)
        return dict(point_pp=100*sum(per)/n, ci95_pp=ci(boot), seeds=n, se_boot_pp=(sum((x-mean)**2 for x in boot)/(len(boot)-1))**.5)
    return dict(n=n, idx=idx, arms=arms, contrasts=contrasts, delta=delta, loss=loss)


def classify(d, contrasts):
    pooled_single = all(contrasts.get(f'{t} minus R3a [pooled]', dict(loss_change_pp=1.))['loss_change_pp'] < 0 for t in ('R5', 'R5-rep'))
    if d['ci95_pp'][1] < 0 and pooled_single: return 'helps'
    return 'no material effect' if d['ci95_pp'][0] > -2.0 else 'inconclusive'


def readout(res, contrasts, data):
    d = res['delta'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'])
    d['outcome'] = classify(d, contrasts)
    half = 1.96*(d['se_boot_pp']**2+SIGMA_FIT_FIXED**2)**.5
    d['fit_inflated_interval_pp'] = [d['point_pp']-half, d['point_pp']+half]
    d['fit_inflated_sigma_fit_pp'] = SIGMA_FIT_FIXED
    d['label'] = ('helps (game-sampling CI only; not robust to sigma_fit = 0.65)' if d['outcome'] == 'helps' and d['fit_inflated_interval_pp'][1] >= 0
                  else d['outcome'])
    d['harmful'] = d['ci95_pp'][0] > 0                                     # E9 sub-label
    d.update(definition='mean(R5, R5-rep) minus mean(R3a, R3a-rep), pooled, equal arm weight', mde_pp='2.1 (game sampling) to 2.8 (sigma_fit 0.65)',
             rule='helps: upper95CI < 0 AND (R5 minus R3a)[pooled] < 0 AND (R5-rep minus R3a)[pooled] < 0; '
                  'no material effect: lower95CI > -2.0 pp; else inconclusive')
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--students', nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--allow-prefix', action='store_true', help='E8 hard-stop cut: largest seed-index prefix (disclosed)')
    a = ap.parse_args()
    plan = json.loads((a.job/'base/repo/reports/explore/x4s3/plan.json').read_text()) if (a.job/'base').exists() else \
        json.loads((Path(__file__).parent/'plan.json').read_text())
    retired_doc = json.loads((a.job/'driver'/'retired.json').read_text()) if (a.job/'driver'/'retired.json').exists() else dict(indices=[], why=[])
    retired = set(retired_doc['indices'])
    if not (plan['seed_ranges']['reporting'] == dict(base=E_BASE, count=E_COUNT)): raise SystemExit('evaluation bank E expected')
    if not (set(PRIMARY) <= set(a.students)): raise SystemExit('all four primary students are always reduced (E1)')
    ex = a.job/'receipts'/'contention-exclusion.json'
    if not (ex.exists()): raise SystemExit('C5 contention receipt must be frozen before any reduction (E1)')
    checks = Counter(); data = {}; complete = {}
    for sid in a.students:
        data[sid], complete[sid] = load_student(a.job, sid, plan, retired, checks)
        if not a.allow_prefix:
            if not (complete[sid]): raise SystemExit(f'{sid}: not every non-retired index is terminal in both arms (fixed N)')
    need = [i for i in range(E_COUNT) if i not in retired]
    idx = prefix(data, PRIMARY, retired, E_COUNT)
    truncated = len(idx) < len(need)
    res = analyze(data, list(PRIMARY), idx, plan)
    out = dict(utc=utc(), label='X4S-4 exploration, NEVER ADOPTABLE', paired_seeds=res['n'], students=a.students,
               retired=sorted(retired), checks=dict(checks), bootstrap=plan['bootstrap'],
               truncation=dict(truncated=truncated, primary_prefix_seeds=len(idx), non_retired=len(need), rule='E8 largest seed-index prefix'),
               cells=dict(Counter(str(i % 50) for i in idx)), arms=res['arms'], contrasts=res['contrasts'])
    ro = out['readout'] = {}
    ro['primary'] = readout(res, res['contrasts'], data)
    within = [res['delta']([l], [r]) for l, r in (('R5', 'R5-rep'), ('R3a-rep', 'R3a'))]
    est = (sum(w['point_pp']**2 for w in within)/2 - sum(w['se_boot_pp']**2 for w in within)/2)/2
    ro['sigma_fit_pp'] = dict(value=max(0.0, est)**.5, df=2, note='descriptive; within-group differences minus bootstrap sampling variance')
    ro['fit_seed_noise_ge_4pp'] = {k: abs(v['loss_change_pp']) >= 4 for k, v in res['contrasts'].items() if k.startswith('R3a-rep minus R3a')}
    body = json.loads(ex.read_text()); excluded = set(body['excluded_indices'])
    kept = [i for i in idx if i not in excluded]
    if kept:
        rk = analyze(data, list(PRIMARY), kept, plan)
        sens = readout(rk, rk['contrasts'], data)
        sens.update(exclusion_sha256=sha(ex), excluded_paired_seeds=len(idx)-len(kept))
        ro['contention_sensitivity'] = sens
    if 'R5W' in data:                      # secondaries on R5W's own complete prefix (E8: never cuts the primary)
        idx_w = prefix(data, list(PRIMARY)+['R5W'], retired, E_COUNT)
        if idx_w:
            rw = analyze(data, list(PRIMARY)+['R5W'], idx_w, plan)
            m = rw['delta'](['R5', 'R5-rep'], ['R5W'])
            m['attribution'] = ('on-policy beyond matched data' if m['ci95_pp'][1] < 0 else
                                'matched data does at least as well' if m['ci95_pp'][0] > 0 else
                                'on-policy or deployment-matched data helps; attribution unresolved')
            ro['secondary_mean_R5_minus_R5W'] = m
            for k, v in rw['contrasts'].items():
                if 'R5W' in k: out['contrasts'][k] = dict(v, seeds=rw['n'])
            for k, v in rw['arms'].items():
                if k.startswith('R5W '): out['arms'][k] = dict(v, seeds=rw['n'])
    parity = {}
    for arm in ARMS:
        rows = {s: out['arms'][f'{s} {arm}'] for s in a.students if f'{s} {arm}' in out['arms']}
        cut = [r['cutoff_pct'] for r in rows.values()]; sd = [r['student_default_pct'] for r in rows.values()]
        parity[arm] = dict(per_student={s: dict(cutoff_pct=r['cutoff_pct'], student_default_pct=r['student_default_pct'],
                                               wall_ms_p99=r['wall_ms_p99']) for s, r in rows.items()},
                           cutoff_gap_pp=max(cut)-min(cut), student_default_gap_pp=max(sd)-min(sd),
                           gap_gt_2pp_disclosed=(max(cut)-min(cut) > 2) or (max(sd)-min(sd) > 2),
                           note='E10: disclosed next to the C5 sensitivity; triggers no exclusion; wall p99 descriptive')
    ro['timing_parity'] = parity
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ('utc', 'paired_seeds', 'students', 'checks', 'truncation')}))


if __name__ == '__main__':
    main()
