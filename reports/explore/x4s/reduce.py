"""X4S reducer (exploration, NEVER ADOPTABLE). Pure stdlib; runs on the 05 mirror.

Only seeds whose block proof exists with all nine arms and matching game SHA-256s
count. Shared paired-seed bootstrap; percentile 95% CIs; unadjusted.
"""
import argparse, hashlib, json, math, random, subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUDGETS = (200, 160, 140, 120)


def utc(): return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()
def pct(xs, q):
    xs = sorted(xs)
    if not xs: return 0.
    k = (len(xs)-1)*q/100; f = math.floor(k); c = min(f+1, len(xs)-1)
    return xs[f]+(xs[c]-xs[f])*(k-f)
def quant(xs): return {n: pct(xs, q) for n, q in (('p50', 50), ('p95', 95), ('p99', 99), ('max', 100))}
def ci(xs): return [pct(xs, 2.5), pct(xs, 97.5)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phases', type=Path, nargs='+', required=True)
    ap.add_argument('--range', default='reporting')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    cfg = json.loads((HERE/'plan.json').read_text())
    arms = list(cfg['arms']); spec_range = cfg['seed_ranges'][a.range]; base = spec_range['base']
    rows = {}; checks = Counter(); excluded = []; proofs = {}
    for phase in a.phases:
        sched = json.loads((phase/'schedule.json').read_text())
        assert sched['range'] == a.range and sched['config_sha256'] == hashlib.sha256((HERE/'plan.json').read_bytes()).hexdigest(), phase
        for i in sched['indices']:
            proof_path = phase/'blocks'/f'{i:04d}.json'
            if not proof_path.exists():
                started = [p.name for p in (phase/'games').glob(f'sim-{i:04d}-d27-*.json')]
                if started: excluded.append(dict(phase=str(phase.name), index=i, games=sorted(started)))
                continue
            assert i not in rows, ('duplicate index', i)
            proof = json.loads(proof_path.read_text())
            order = arms[i % len(arms):]+arms[:i % len(arms)]
            assert proof['index'] == i and proof['seed'] == base+i and proof['order'] == order
            games = {}
            for arm in arms:
                p = phase/'games'/f'sim-{i:04d}-d27-{arm}.json'
                assert hashlib.sha256(p.read_bytes()).hexdigest() == proof['games'][p.name]
                r = json.loads(p.read_text()); m = r['metadata']; s = r['search_ab']; sp = cfg['arms'][arm]
                assert m['seed'] == base+i and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == 'v1-policy'
                assert m['threads'] == sp['threads'] and m['coarse_horizon'] == 160 and m['budget_ms'] == round(sp['deadline_seconds']*1000)
                assert m['default_source'] == sp['default_source'] and m['kernel'] == sp['kernel'] and m['honest_lateness']
                assert r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])
                assert m['seat'] == i % 2 and m['channel']['peak_pending'] <= 1
                width = 1 if sp['threads'] == 1 else 5
                assert s['worker_affinity'] == proof['slot_cores'][:width] and len(proof['slot_cores']) == 5
                assert set(proof['slot_cores']) <= set(range(60)) and s['nice'] == 19 and s['scheduler'] == 0
                assert s['worker_pid'] == proof['worker_pid']
                assert all(not e['during_decision'] for e in s.get('gc_maintenance', []))
                if sp['policy'] != 'v1-unmodified':
                    pc = s['policy_cache_counts']; assert pc['forward'] == pc['fallback'] == s['policy_polls'][str(m['seat'])]
                for wall, d in zip(s['latency_seconds'], s['deadline_stats']):
                    over = max(0., wall-sp['deadline_seconds'])
                    assert d['wall_seconds'] == wall and d['overrun_seconds'] == over and d['delayed_ticks'] == math.ceil(over*20)
                    checks['decisions'] += 1
                assert len(s['latency_seconds']) == len(s['deadline_stats'])
                games[arm] = r; checks['games'] += 1
            ref = games[arms[0]]['metadata']
            assert all((g['metadata']['own_deck'], g['metadata']['opponent_deck'], g['metadata']['seat']) ==
                       (ref['own_deck'], ref['opponent_deck'], ref['seat']) for g in games.values())
            rows[i] = games; proofs[i] = dict(phase=phase.name, host=games[arms[0]]['search_ab']['host'])
    idx = sorted(rows); n = len(idx)
    assert n > 0
    rng = random.Random(cfg['bootstrap']['seed'])
    samples = [[rng.randrange(n) for _ in range(n)] for _ in range(cfg['bootstrap']['reps'])]
    loss = {arm: [rows[i][arm]['loss'] for i in idx] for arm in arms}
    boot = {arm: [sum(loss[arm][j] for j in s)/n for s in samples] for arm in arms}
    def per_game(arm, f):
        return [sum(1 for d in rows[i][arm]['search_ab']['deadline_stats'] if f(d)) for i in idx]
    out = dict(utc=utc(), label='X4S exploration, NEVER ADOPTABLE', paired_seeds=n, indices=idx,
               hosts=dict(Counter(p['host'] for p in proofs.values())), excluded_interrupted=excluded,
               cells=dict(Counter(f"{i%2}-{i%5}-{(i//5)%5}" for i in idx)), checks=dict(checks),
               bootstrap=cfg['bootstrap'], arms={}, contrasts={})
    for arm in arms:
        dec = [len(rows[i][arm]['search_ab']['deadline_stats']) for i in idx]
        rates = {}
        for name, f in (('cutoff', lambda d: d['hit']), ('fallback', lambda d: d['fallback']),
                        ('student_default', lambda d: d.get('student_default', False)),
                        ('overrun', lambda d: d['wall_overrun'])):
            num = per_game(arm, f)
            rates[name+'_pct'] = 100*sum(num)/sum(dec)
            rates[name+'_ci_pct'] = ci([100*sum(num[j] for j in s)/max(1, sum(dec[j] for j in s)) for s in samples])
        ds = [d for i in idx for d in rows[i][arm]['search_ab']['deadline_stats']]
        budget = cfg['arms'][arm]['deadline_seconds']
        rs = [rows[i][arm] for i in idx]
        out['arms'][arm] = dict(
            wins=sum(r['metadata']['winner'] == r['metadata']['seat'] for r in rs), losses=int(sum(loss[arm])),
            draws=sum(r['metadata']['winner'] is None for r in rs), loss_pct=100*sum(loss[arm])/n,
            loss_ci_pct=ci([100*x for x in boot[arm]]), decisions=sum(dec), **rates,
            wall_ms=quant([1000*d['wall_seconds'] for d in ds]),
            positive_overrun_ms=quant([1000*d['overrun_seconds'] for d in ds if d['wall_overrun']]),
            cut_returns_past_deadline_plus_reserve=sum(d['hit'] and d['wall_seconds'] > budget+.008 for d in ds),
            overrun_ticks_hist=dict(Counter(str(d['delayed_ticks']) for d in ds if d['wall_overrun'])),
            preparation_cutoffs=dict(Counter(d.get('preparation_cutoff', 'scoring_or_none') for d in ds)),
            game_cpu_hours=sum(r['cpu_seconds'] for r in rs)/3600)
    pairs = []
    for b in BUDGETS:
        pairs += [(f'K4S-{b}', f'K4-{b}'), (f'K4-{b}', 'K0c-200'), (f'K4S-{b}', 'K0c-200')]
        if b != 200:
            pairs += [(f'K4-{b}', 'K4-200'), (f'K4S-{b}', 'K4-200'), (f'K4S-{b}', 'K4S-200')]
    for l, r in pairs:
        out['contrasts'][f'{l} minus {r}'] = dict(
            loss_change_pp=100*(sum(loss[l])-sum(loss[r]))/n,
            ci95_pp=ci([100*(x-y) for x, y in zip(boot[l], boot[r])]))
    out['readings'] = {}
    for b in BUDGETS:
        rescue = out['contrasts'][f'K4S-{b} minus K4-{b}']['ci95_pp'][1] < 0
        hold = out['contrasts'][f'K4S-{b} minus K4-200']['ci95_pp'][1] <= 5 if b != 200 else None
        out['readings'][str(b)] = dict(rescues_K4=rescue, holds_within_5pp_of_K4_200=hold)
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ('utc', 'paired_seeds', 'hosts', 'checks')}))


if __name__ == '__main__':
    main()
