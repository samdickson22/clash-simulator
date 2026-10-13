"""X4S-4 reducer (exploration, NEVER ADOPTABLE; PLAN r3, frozen at 87809ae0), derived from the X4S-3 reducer; stdlib only.
r3 after Sol script review r2 (R2-F1, R2-F4): every read and write goes through x4s4io; every check is an explicit raise.

C5 freeze gate (Sol F4, R2-F4), before any OUTCOME field is used (the gate hashes approved files and reads mtimes only):
<job>/receipts/contention-exclusion.json must be a regular, single-link, non-writable file whose SHA-256 equals
--contention-sha; the identical bytes must be the blob at reports/explore/x4s4/receipts/contention-exclusion.json of
--freeze-commit, obtained by the self-verifying commit -> tree -> blob walk (no replace objects, no grafts, scrubbed
environment), and that commit must be reachable from origin/main; schema x4s4.contention.v3; the reporting phases on
disk must equal the receipt's, every phase's inventory (census/launch/exit/SETTLED/block listing and every counted
game's SHA-256, size and exact st_mtime_ns) must re-derive identically, and driver/retired.json must have the frozen
SHA. This gate applies to every reduction, including --allow-prefix. Output is confined to <job>/analysis/.

Counts a game only via its block proof (SHA-matched); requires bank E (game metadata `study` reads X4S-3 because the
unchanged x4s3/run.py is reused) and all four primary students. Fixed N: every non-retired index terminal in both arms for every reduced student, unless
--allow-prefix (E8 hard-stop cut: the largest seed-index prefix complete for the four primary students; R5W
secondaries use their own prefix and never cut the primary). Paired-seed bootstrap (5,000 reps, seed 2026101301),
percentile 95% CIs, unadjusted; pooled = equal arm weight.
Readout: primary Delta = mean(R5, R5-rep) - mean(R3a, R3a-rep) with the three-way outcome (helps requires the pooled
single-fit points R5 - R3a and R5-rep - R3a < 0); fit-inflated interval with sigma_fit fixed at 0.65 (E3); harmful
sub-label (E9); attribution sub-label from the CI of mean(R5, R5-rep) - R5W (E4, default unresolved); 2-df sigma_fit;
the C5 contention-excluded view (an explicit no-estimate entry when every paired seed is excluded); the primary
averaged contrast also separately by arm (Sol F14); prefix seed counts for the primary and for R5W; the E10 parity
table (disclosed, no exclusion).
"""
import argparse, hashlib, json, math, os, random, re, stat, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io, contention, studytree      # noqa: E402

ARMS = ('K4S-120', 'S-200')
ORDER = ('R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W')
PAIRS = (('R5', 'R3a'), ('R5-rep', 'R3a'), ('R5', 'R3a-rep'), ('R3a-rep', 'R3a'), ('R5', 'R5-rep'), ('R5', 'R5W'), ('R5-rep', 'R5W'))
E_BASE, E_COUNT = 4503606307370496, 1200


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def pct(xs, q):
    xs = sorted(xs)
    if not xs: return 0.
    k = (len(xs)-1)*q/100; f = math.floor(k); c = min(f+1, len(xs)-1)
    return xs[f]+(xs[c]-xs[f])*(k-f)
def ci(xs): return [pct(xs, 2.5), pct(xs, 97.5)]
def sha(p): return io.sha256_file(str(p))
FREEZE_PATH = 'reports/explore/x4s4/receipts/contention-exclusion.json'


def verify_freeze(job, contention_sha, commit, repo):
    """R2-F4: authenticate the frozen C5 receipt, its commit and every selection-relevant input before reduction."""
    job = str(job); ex = f'{job}/{contention.RECEIPT}'
    st = io.lstat(ex)
    if st is None: raise SystemExit('C5 contention receipt must be frozen before any reduction (E1)')
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_mode & 0o222:
        raise SystemExit('C5 receipt must be a regular, single-link, non-writable file')
    try: data = io.read_bytes(ex, 256 << 20)
    except io.Refusal as e: raise SystemExit(f'C5 receipt unreadable: {e}')
    if studytree.guarded_output(job, ex) is None:
        raise SystemExit('C5 receipt has no passed guard receipt (R7: guarded acceptance of contention.py)')
    if not re.fullmatch(r'[0-9a-f]{64}', contention_sha or '') or hashlib.sha256(data).hexdigest() != contention_sha:
        raise SystemExit('C5 receipt SHA differs from --contention-sha')
    if not re.fullmatch(r'[0-9a-f]{40}', commit or ''): raise SystemExit('--freeze-commit must be a full commit SHA')
    try:
        committed = io.git_committed_blob(str(repo), commit, FREEZE_PATH)
        on_main = io.git_is_ancestor(str(repo), commit)
    except io.Refusal as e:
        raise SystemExit(f'C5 freeze commit cannot be authenticated: {e}')
    if hashlib.sha256(committed).hexdigest() != contention_sha:
        raise SystemExit(f'C5 receipt is not committed with this SHA at {commit}:{FREEZE_PATH}')
    if not on_main: raise SystemExit('the C5 freeze commit is not on origin/main')
    try: body = io.loads_strict(data, 'C5 receipt')
    except io.Refusal: raise SystemExit('C5 receipt is not strict JSON')
    if not isinstance(body, dict) or body.get('schema') != contention.SCHEMA:
        raise SystemExit(f'C5 receipt schema must be {contention.SCHEMA}')
    for k in ('phases', 'coverage', 'excluded_indices', 'bad_periods', 'games_checked', 'retired_sha256'):
        if k not in body: raise SystemExit(f'C5 receipt lacks {k}')
    disk = sorted(d[len(job)+1:] for d in contention.phase_dirs(job))
    if disk != sorted(body['phases']) or sorted(body['coverage']) != disk:
        raise SystemExit('reporting phases on disk differ from the frozen C5 receipt')
    for rel in disk:
        try: now = contention.inventory(job, f'{job}/{rel}')
        except io.Refusal as e: raise SystemExit(f'C5 inventory of {rel} unreadable: {e}')
        then = {k: v for k, v in body['coverage'][rel].items() if k != 'census_samples'}
        if now != then: raise SystemExit(f'C5 source inventory of {rel} (content or mtime) changed since the freeze')
    if contention.retired_sha(job) != body['retired_sha256']:
        raise SystemExit('driver/retired.json changed since the C5 freeze')
    if not all(isinstance(i, int) and 0 <= i < E_COUNT for i in body['excluded_indices']):
        raise SystemExit('C5 excluded indices outside bank E')
    return body, contention_sha


def load_student(job, sid, plan, retired, checks):
    job = str(job)
    rt = io.read_json(f'{job}/rt-{sid}/READY.json', 4 << 20)['student'] if sid != 'R3a' else plan['student']
    base = plan['seed_ranges']['reporting']['base']; rows = {}
    for arm in ARMS:
        sp = plan['arms'][arm]; width = 1 if sp['threads'] == 1 else 5
        rows[arm] = {}
        for d in sorted(x for x in contention.phase_dirs(job) if x.split('/')[-3:-1] == [sid, arm]):
            sched = io.read_json(d+'/schedule.json', 64 << 20)
            if not (sched['range'] == 'reporting' and all(c[2] == arm for c in sched['cases'])): raise SystemExit(d)
            for bi, _ in contention.counted_games(d):
                h1 = studytree.h1_reason(job, studytree.completed_at(f'{d}/blocks/{bi:04d}.json'))
                if h1:                                                       # rule H-1: never counted (disclosed)
                    checks['h1_excluded'] += 1; continue
                proof = io.read_json(f'{d}/blocks/{bi:04d}.json', 1 << 20); i = proof['index']
                if not (i not in rows[arm]): raise SystemExit(('duplicate', sid, arm, i))
                if not (proof['seed'] == base+i and proof['order'] == [arm] and len(proof['slot_cores']) == width): raise SystemExit("reduce.py: check failed: proof['seed'] == base+i and proof['order'] == [arm] and len(proof['slot_cores']) == width")
                p = f'{d}/games/sim-{i:04d}-d27-{arm}.json'
                raw = io.read_bytes(p, 256 << 20)
                if not (hashlib.sha256(raw).hexdigest() == proof['games'][p.split('/')[-1]]): raise SystemExit("reduce.py: check failed: sha(p) == proof['games'][name]")
                r = io.loads_strict(raw, p); m = r['metadata']; s = r['search_ab']
                if not (m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == 'v1-policy'): raise SystemExit("reduce.py: check failed: m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == '")
                if not (m['student_id'] == sid and m['checkpoint_sha256'] == rt['checkpoint_sha256'] and m['study'].startswith('X4S-3')): raise SystemExit("reduce.py: check failed: m['student_id'] == sid and m['checkpoint_sha256'] == rt['checkpoint_sha256'] and m['study'].sta")
                if not (m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['deadline_seconds']*1000)): raise SystemExit("reduce.py: check failed: m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['de")
                if not (m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_lateness']): raise SystemExit("reduce.py: check failed: m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_laten")
                if not (r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])): raise SystemExit("reduce.py: check failed: r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])")
                if not (m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1): raise SystemExit("reduce.py: check failed: m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1")
                if not (s['worker_affinity'] == proof['slot_cores'][:width] and set(proof['slot_cores']) <= set(range(50))): raise SystemExit("reduce.py: check failed: s['worker_affinity'] == proof['slot_cores'][:width] and set(proof['slot_cores']) <= set(range(5")
                if not (s['nice'] == 10 and s['scheduler'] == 0 and s['host'] == '127x01' and s['worker_pid'] == proof['worker_pid']): raise SystemExit("reduce.py: check failed: s['nice'] == 10 and s['scheduler'] == 0 and s['host'] == '127x01' and s['worker_pid'] == proof[")
                if not (all(not e['during_decision'] for e in s.get('gc_maintenance', []))): raise SystemExit("reduce.py: check failed: all(not e['during_decision'] for e in s.get('gc_maintenance', []))")
                pc = s['policy_cache_counts']
                if not (pc['forward'] == pc['fallback'] == s['policy_polls'][str(m['seat'])]): raise SystemExit("reduce.py: check failed: pc['forward'] == pc['fallback'] == s['policy_polls'][str(m['seat'])]")
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
    n = len(idx)
    if n <= 0: raise SystemExit('reduce.py: no paired seeds to analyze')
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

    def delta_arm(members_t, members_c, arm):     # Sol F14: the same averaged contrast within one arm
        per = [sum(loss[(t, arm)][k] for t in members_t)/len(members_t) - sum(loss[(u, arm)][k] for u in members_c)/len(members_c)
               for k in range(n)]
        return dict(point_pp=100*sum(per)/n, ci95_pp=ci([100*sum(per[j] for j in smp)/n for smp in samples]), seeds=n, arm=arm)
    return dict(n=n, idx=idx, arms=arms, contrasts=contrasts, delta=delta, delta_arm=delta_arm, loss=loss)


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


def study_identities(job, students, plan, plan_path, body, ex_sha, commit):
    """R3-F4: the identities this reduction used, for write_report to reconcile with current evidence."""
    st = {}
    for sid in students:
        s = plan['student'] if sid == 'R3a' else io.read_json(f'{job}/rt-{sid}/READY.json', 4 << 20)['student']
        st[sid] = dict(checkpoint_sha256=s['checkpoint_sha256'], threshold=s.get('threshold'))
    gates = {m: io.sha256_file(f'{job}/data/{n}') for m, n in (('O', 'O-VERIFIED.json'), ('OW', 'OW-VERIFIED.json'), ('holdout', 'HOLDOUT-VERIFIED.json'))
             if io.lexists(f'{job}/data/{n}')}
    return dict(plan_path=plan_path, plan_sha256=io.sha256_file(plan_path), contention_receipt_sha256=ex_sha, freeze_commit=commit,
                retired_sha256=body['retired_sha256'], students=st, gates=gates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--students', nargs='+', required=True)
    ap.add_argument('--out', required=True, help='confined below <job>/analysis/')
    ap.add_argument('--contention-sha', required=True, help='SHA-256 of the frozen C5 receipt')
    ap.add_argument('--freeze-commit', required=True, help='commit on origin/main that contains the C5 receipt')
    ap.add_argument('--repo', default=io.REPO)
    ap.add_argument('--allow-prefix', action='store_true', help='E8 hard-stop cut: largest seed-index prefix (disclosed)')
    a = ap.parse_args()
    studytree.require_guard('reduce')                              # R7: runs only under guard.py --readout
    if a.job != io.JOB: raise SystemExit(f'--job must be {io.JOB}')
    out_path = io.check_writable(a.out, roles=('analysis',))
    base_plan = a.job+'/base/repo/reports/explore/x4s3/plan.json'
    plan_path = base_plan if io.lexists(a.job+'/base') else str(Path(__file__).parent/'plan.json')
    plan = io.read_json(plan_path, 16 << 20)
    rp = a.job+'/driver/retired.json'
    retired_doc = io.read_json(rp, 16 << 20) if io.lexists(rp) else dict(indices=[], why=[])
    retired = set(retired_doc['indices'])
    if not (plan['seed_ranges']['reporting'] == dict(base=E_BASE, count=E_COUNT)): raise SystemExit('evaluation bank E expected')
    if not (set(PRIMARY) <= set(a.students)): raise SystemExit('all four primary students are always reduced (E1)')
    body, ex_sha = verify_freeze(a.job, a.contention_sha, a.freeze_commit, a.repo)   # before any game read (F4)
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
               cells=dict(Counter(str(i % 50) for i in idx)), arms=res['arms'], contrasts=res['contrasts'],
               identities=study_identities(a.job, a.students, plan, plan_path, body, ex_sha, a.freeze_commit))
    ro = out['readout'] = {}
    ro['primary'] = readout(res, res['contrasts'], data)
    ro['primary_by_arm'] = {arm: dict(res['delta_arm'](['R5', 'R5-rep'], ['R3a', 'R3a-rep'], arm),
                                      definition=f'mean(R5, R5-rep) minus mean(R3a, R3a-rep), {arm} only; descriptive, no outcome rule')
                            for arm in ARMS}
    within = [res['delta']([l], [r]) for l, r in (('R5', 'R5-rep'), ('R3a-rep', 'R3a'))]
    est = (sum(w['point_pp']**2 for w in within)/2 - sum(w['se_boot_pp']**2 for w in within)/2)/2
    ro['sigma_fit_pp'] = dict(value=max(0.0, est)**.5, df=2, note='descriptive; within-group differences minus bootstrap sampling variance')
    ro['fit_seed_noise_ge_4pp'] = {k: abs(v['loss_change_pp']) >= 4 for k, v in res['contrasts'].items() if k.startswith('R3a-rep minus R3a')}
    excluded = set(body['excluded_indices'])
    kept = [i for i in idx if i not in excluded]
    if kept:
        rk = analyze(data, list(PRIMARY), kept, plan)
        sens = readout(rk, rk['contrasts'], data)
        sens.update(exclusion_sha256=ex_sha, freeze_commit=a.freeze_commit, excluded_paired_seeds=len(idx)-len(kept), estimate=True)
        ro['contention_sensitivity'] = sens
    else:                                  # Sol F14: an empty view is reported, never silently dropped
        ro['contention_sensitivity'] = dict(estimate=None, exclusion_sha256=ex_sha, freeze_commit=a.freeze_commit,
                                            excluded_paired_seeds=len(idx), seeds=0,
                                            note='every paired seed is contention-excluded; no sensitivity estimate can be computed')
    idx_w = prefix(data, list(PRIMARY)+['R5W'], retired, E_COUNT) if 'R5W' in data else []
    out['truncation'].update(r5w_prefix_seeds=len(idx_w), r5w_truncated=('R5W' in data and len(idx_w) < len(idx)),
                             r5w_reduced='R5W' in data)
    if not idx_w:
        ro['secondary_mean_R5_minus_R5W'] = dict(estimate=None, seeds=0, attribution='on-policy or deployment-matched data helps; attribution unresolved',
                                                 note='R5W not reduced or no complete R5W prefix; attribution stays at its default')
    if 'R5W' in data:                      # secondaries on R5W's own complete prefix (E8: never cuts the primary)
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
    io.replace_json(out_path, out, roles=('analysis',))
    print(json.dumps({k: out[k] for k in ('utc', 'paired_seeds', 'students', 'checks', 'truncation')}))


if __name__ == '__main__':
    main()
