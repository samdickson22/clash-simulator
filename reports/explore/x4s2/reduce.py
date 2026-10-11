"""X4S2 reducer (exploration, NEVER ADOPTABLE). Pure stdlib; runs on the 05 mirror.

A game counts only if its block proof exists and every game SHA-256 matches. X-population
contrasts pair X4S2 games with the X4S games of the same seed index (X4S mirror). Each
contrast is bootstrapped over the seeds that have both arms (paired-seed resampling,
percentile 95% CI, unadjusted).
"""
import argparse, hashlib, json, math, random, subprocess
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
X4S = Path('/mpac/sdicks02/jobs/clasher/x4s-20261011/mirror')
X4S_PHASES = [X4S/'127x03/reporting-03', X4S/'127x08/reporting-08']
X4S_PLAN = HERE.parent/'x4s/plan.json'
CONFIG_SHAS = set()


def utc(): return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pct(xs, q):
    xs = sorted(xs)
    if not xs: return float('nan')
    k = (len(xs)-1)*q/100; f = math.floor(k); c = min(f+1, len(xs)-1)
    return xs[f]+(xs[c]-xs[f])*(k-f)
def ci(xs): return [pct(xs, 2.5), pct(xs, 97.5)]


def check_game(r, arm, sp, seed, budget_key='deadline_seconds'):
    m, s = r['metadata'], r['search_ab']
    assert m['seed'] == seed and m['arm'] == arm == r['cohort'] and m['terminal'] and m['opponent'] == 'v1-policy'
    assert m['threads'] == sp['threads'] == 4 and m['coarse_horizon'] == 160
    assert m['budget_ms'] == round(sp['deadline_seconds']*1000) and m['default_source'] == sp['default_source']
    assert m['kernel'] == sp['kernel'] and m['honest_lateness']
    assert r['loss'] == float(m['winner'] is not None and m['winner'] != m['seat'])
    assert m['channel']['peak_pending'] <= 1 and s['nice'] == 19 and s['scheduler'] == 0
    assert all(not e['during_decision'] for e in s.get('gc_maintenance', []))
    assert len(s['latency_seconds']) == len(s['deadline_stats'])
    for wall, d in zip(s['latency_seconds'], s['deadline_stats']):
        over = max(0., wall-sp['deadline_seconds'])
        assert d['wall_seconds'] == wall and d['overrun_seconds'] == over and d['delayed_ticks'] == math.ceil(over*20)


def load_x4s():
    cfg = json.loads(X4S_PLAN.read_text()); base = cfg['seed_ranges']['reporting']['base']
    rows = {}
    for phase in X4S_PHASES:
        for proof_path in sorted((phase/'blocks').glob('*.json')):
            proof = json.loads(proof_path.read_text()); i = proof['index']
            games = {}
            for arm, sp in cfg['arms'].items():
                if sp['threads'] != 4: continue
                p = phase/'games'/f'sim-{i:04d}-d27-{arm}.json'
                assert sha(p) == proof['games'][p.name]
                r = json.loads(p.read_text()); check_game(r, arm, sp, base+i)
                games[arm] = r
            assert i not in rows; rows[i] = games
    return rows


def load_x4s2(phases, cfg, rng_name='reporting', pops=('X', 'G')):
    rows = defaultdict(dict); excluded = []; hosts = Counter(); nblocks = Counter()
    for phase in phases:
        sched = json.loads((phase/'schedule.json').read_text())
        assert sched['range'] == rng_name, phase
        if rng_name == 'reporting': assert sched['config_sha256'] in CONFIG_SHAS, phase
        blocks = defaultdict(list)
        for c in sched['cases']: blocks[(c[0], c[1])].append(c)
        for (pop, i), cases in blocks.items():
            if pop not in pops: continue
            proof_path = phase/'blocks'/f'{pop}{i:04d}.json'
            if not proof_path.exists():
                started = sorted(p.name for p in (phase/'games').glob(f'sim-{pop}{i:04d}-d27-*.json'))
                marker = (phase/'blocks'/f'{pop}{i:04d}.started').exists()
                if started or marker: excluded.append(dict(phase=phase.name, pop=pop, index=i, games=started, marker=marker))
                continue
            proof = json.loads(proof_path.read_text())
            assert proof['pop'] == pop and proof['index'] == i and proof['order'] == [c[3] for c in cases]
            seed = cfg['seed_ranges'][f'{pop}-reporting' if rng_name == 'reporting' else rng_name]['base']+i
            assert proof['seed'] == seed
            for c in cases:
                arm = c[3]; sp = cfg['arms'][arm]
                p = phase/'games'/f'sim-{pop}{i:04d}-d27-{arm}.json'
                assert sha(p) == proof['games'][p.name]
                r = json.loads(p.read_text()); check_game(r, arm, sp, seed); m = r['metadata']
                assert m['population'] == pop and m['seat'] == i % 2
                assert m['inference_scale'] == sp['inference_scale'] and m['scale_mode'] == sp['scale_mode']
                assert r['search_ab']['worker_affinity'] == proof['slot_cores'] and set(proof['slot_cores']) <= set(range(60))
                if pop == 'G':
                    G = cfg['populations']['G']
                    assert sorted(m['own_deck']) == sorted(G['own_decks'][(i//2) % 3])
                    assert sorted(m['opponent_deck']) == sorted(G['opponent_decks'][(i//6) % 3])
                assert arm not in rows[(pop, i)]
                rows[(pop, i)][arm] = r
            hosts[r['search_ab']['host']] += 1; nblocks[phase.name] += 1
    return rows, excluded, dict(hosts), dict(nblocks)


def summarize(games, sp):
    ds = [d for r in games for d in r['search_ab']['deadline_stats']]
    n = len(ds); hits = [d for d in ds if d['hit']]
    def rate(f, pool=ds): return 100*sum(1 for d in pool if f(d))/max(1, len(pool))
    def mean_ms(key):
        v = [d[key] for d in ds if d.get(key) is not None]
        return 1000*sum(v)/len(v) if v else None
    walls = [1000*d['wall_seconds'] for d in ds]
    return dict(games=len(games), losses=int(sum(r['loss'] for r in games)),
                loss_pct=100*sum(r['loss'] for r in games)/max(1, len(games)), decisions=n,
                cutoff_pct=rate(lambda d: d['hit']), fallback_pct=rate(lambda d: d['fallback']),
                student_default_pct=rate(lambda d: d.get('student_default', False)),
                overrun_pct=rate(lambda d: d['wall_overrun']),
                coarse_complete_at_cutoff_pct=rate(lambda d: d.get('coarse_complete', False), hits) if any('coarse_complete' in d for d in hits) else None,
                play_rate_pct=rate(lambda d: d['action'] < 2304),
                poll_ms=mean_ms('poll_seconds'), scale_sleep_ms=mean_ms('scale_sleep_seconds'), prep_ms=mean_ms('prep_seconds'),
                wall_ms=dict(p50=pct(walls, 50), p95=pct(walls, 95), p99=pct(walls, 99), max=max(walls) if walls else None),
                game_cpu_hours=sum(r['cpu_seconds'] for r in games)/3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phases', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--range', default='reporting')
    ap.add_argument('--pops', nargs='+', default=['X', 'G'])  # keep in-progress populations sealed  # 'smoke' only for reducer dry-runs
    a = ap.parse_args()
    # plan-ext.json (phases E/F, added after the 07:28Z 08 extension) is a strict superset of plan.json.
    base_cfg = json.loads((HERE/'plan.json').read_text())
    cfg = json.loads((HERE/'plan-ext.json').read_text())
    assert all(cfg['arms'][k] == v for k, v in base_cfg['arms'].items()) and cfg['seed_ranges'] == base_cfg['seed_ranges']
    CONFIG_SHAS.update({sha(HERE/'plan.json'), sha(HERE/'plan-ext.json')})
    old = load_x4s()
    new, excluded, hosts, nblocks = load_x4s2(a.phases, cfg, a.range, set(a.pops))
    # Unified per-population tables: X arms from both studies (X4S arms prefixed 'x4s:').
    table = {pop: defaultdict(dict) for pop in ('X', 'G') if pop in a.pops}
    if 'X' in table:
        for i, games in old.items():
            for arm, r in games.items(): table['X'][i]['x4s:'+arm] = r
    for (pop, i), games in new.items():
        for arm, r in games.items(): table[pop][i][arm] = r
    out = dict(utc=utc(), label='X4S2 exploration, NEVER ADOPTABLE', hosts_games=hosts, blocks_per_phase=nblocks,
               excluded_interrupted=excluded, bootstrap=cfg['bootstrap'], arms={}, contrasts={})
    for pop, t in table.items():
        arms = sorted({arm for g in t.values() for arm in g})
        for arm in arms:
            idx = sorted(i for i in t if arm in t[i])
            sp = cfg['arms'].get(arm) or json.loads(X4S_PLAN.read_text())['arms'][arm.split(':', 1)[1]]
            s = summarize([t[i][arm] for i in idx], sp)
            loss = [t[i][arm]['loss'] for i in idx]
            rng = random.Random(cfg['bootstrap']['seed'])
            s['loss_ci_pct'] = ci([100*sum(loss[rng.randrange(len(idx))] for _ in idx)/len(idx)
                                   for _ in range(cfg['bootstrap']['reps'])]) if idx else None
            s['seeds'] = len(idx)
            if pop == 'G':
                s['cells'] = dict(Counter(f'{i%2}-{(i//2)%3}-{(i//6)%3}' for i in idx))
            out['arms'][f'{pop}:{arm}'] = s
    pairs = {'X': [], 'G': []}
    for b in (160, 140, 120):
        pairs['X'] += [(f'K4Sh-{b}', f'x4s:K4-{b}'), (f'K4Sh-{b}', f'x4s:K4S-{b}'), (f'K4Sh-{b}', 'x4s:K4-200'), (f'K4Sh-{b}', 'x4s:K4S-200')]
    pairs['X'] += [('K4Sh-100', 'K4-100'), ('K4Sh-100', 'x4s:K4-200'), ('K4Sh-100', 'x4s:K4S-200'), ('K4Sh-100', 'K4Sh-120'),
                   ('K4-100', 'x4s:K4-120')]
    for b in (140, 120):
        pairs['X'] += [(f'K4Sf-{b}', f'x4s:K4-{b}'), (f'K4Sf-{b}', f'x4s:K4S-{b}'), (f'K4Sf-{b}', f'K4Sh-{b}'), (f'K4Sf-{b}', 'x4s:K4-200')]
    pairs['X'] += [('K4S-140r', 'x4s:K4S-140'), ('K4Sh-140', 'K4S-140r'), ('K4Sf-140', 'K4S-140r'),
                   ('K4Sl-200', 'x4s:K4-200'), ('K4Sl-200', 'x4s:K4S-200'), ('K4Sl-140', 'x4s:K4S-140'),
                   ('K4Sl-140', 'x4s:K4-140'), ('K4Sl-140', 'K4S-140r')]
    pairs['X'] += [('K4S-180', 'K4-180'), ('K4Sl-180', 'K4-180'), ('K4Sl-180', 'K4S-180'), ('K4-180', 'x4s:K4-200'),
                   ('K4S-180', 'x4s:K4-200'), ('K4Sl-180', 'x4s:K4-200'), ('K4-180', 'x4s:K4-160'), ('K4Sl-160', 'x4s:K4-160'),
                   ('K4Sl-160', 'x4s:K4S-160'), ('K4Sl-160', 'x4s:K4-200')]
    pairs['G'] = [('K4S-200', 'K4-200'), ('K4S-140', 'K4-140'), ('K4Sh-140', 'K4-140'), ('K4Sh-140', 'K4S-140'),
                  ('K4-140', 'K4-200'), ('K4S-140', 'K4-200'), ('K4Sh-140', 'K4-200'), ('K4S-140', 'K4S-200'),
                  ('K4S-120', 'K4-120'), ('K4Sh-120', 'K4-120'), ('K4Sh-120', 'K4S-120'), ('K4S-120', 'K4-200'), ('K4Sh-120', 'K4-200'),
                  ('K4-120', 'K4-200')]
    for pop, ps in pairs.items():
        if pop not in table: continue
        t = table[pop]
        for l, r in ps:
            idx = sorted(i for i in t if l in t[i] and r in t[i])
            if not idx: continue
            diff = [t[i][l]['loss']-t[i][r]['loss'] for i in idx]
            rng = random.Random(cfg['bootstrap']['seed'])
            boot = [100*sum(diff[rng.randrange(len(idx))] for _ in idx)/len(idx) for _ in range(cfg['bootstrap']['reps'])]
            out['contrasts'][f'{pop}: {l} minus {r}'] = dict(seeds=len(idx), loss_change_pp=100*sum(diff)/len(idx), ci95_pp=ci(boot))
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(utc=out['utc'], hosts=hosts, blocks=nblocks, excluded=len(excluded))))


if __name__ == '__main__':
    main()
