"""FSC reducer (U3/U4 exploration, NEVER ADOPTABLE). Stdlib (Python >= 3.8); runs on the 05 mirror after STOP.

Reuses X4S2's game checks and loaders (reports/explore/x4s2/reduce.py, unchanged). A game counts only if its block
proof exists and every game SHA-256 matches. Each host's blocks are cut to the largest complete prefix in that
host's worklist (dispatch) order; see READOUT.md. Contrasts are paired by seed; 5,000-rep percentile bootstrap.
"""
import argparse, hashlib, importlib.util, json, random, subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('x4s2_reduce', HERE.parent/'x4s2'/'reduce.py')
X = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(X)
NATIVE = '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
POLICY = 'd77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed'
STUDENT = '37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85'
HOST_WL = {'127x03': 'wl-03.json', '127x04': 'wl-04.json'}
X4S2_MIRROR = Path('/mpac/sdicks02/jobs/clasher/x4s2-20261011/mirror')
X4S2_E = [X4S2_MIRROR/'127x03/rep03EF', X4S2_MIRROR/'127x08/rep08EF']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def boot(diffs, cfg):
    """Mean (pp) and percentile CI; diffs is a list of strata (each a list of per-seed differences)."""
    n = sum(len(d) for d in diffs)
    rng = random.Random(cfg['bootstrap']['seed'])
    reps = [100*sum(sum(d[rng.randrange(len(d))] for _ in d) for d in diffs if d)/n for _ in range(cfg['bootstrap']['reps'])]
    return dict(seeds=n, loss_change_pp=100*sum(sum(d) for d in diffs)/n, ci95_pp=X.ci(reps))


def check_more(rows, cfg, arms_of):
    decks = cfg['populations']['X']['decks']
    for (pop, i), games in rows.items():
        assert pop == 'X' and set(games) == set(arms_of[i]), (pop, i)
        for arm, r in games.items():
            m = r['metadata']; sp = cfg['arms'][arm]
            assert sorted(m['own_deck']) == sorted(decks[i % 5]) and sorted(m['opponent_deck']) == sorted(decks[(i//5) % 5])
            assert m['checkpoint_sha256'] == (STUDENT if sp['policy'] == 'R3a-cached' else POLICY)
            assert m['s_default'] == (sp['kernel'] == 'K4-anytime-sdefault')


def load_host(host, phases, cfg, config_shas):
    """Rows of one host, cut to the largest complete prefix of its worklist order."""
    wl = json.loads((HERE/HOST_WL[host]).read_text())
    rows, retired, per_phase = {}, set(), {}
    for n, phase in enumerate(phases):
        sched = json.loads((phase/'schedule.json').read_text())
        assert sched['native_sha256'] == NATIVE and sched['config_sha256'] in config_shas, phase
        launch = json.loads((phase/'launch.json').read_text()); assert launch['host'] == host, phase
        got, excluded, hosts, nblocks = X.load_x4s2([phase], cfg, 'reporting', {'X'})
        assert set(hosts) <= {host} and not set(got) & set(rows), phase
        if n < len(phases)-1:  # blocks interrupted by an intermediate (console-user yield) STOP are retired
            retired |= {('X', e['index']) for e in excluded}
        rows.update(got); per_phase[phase.name] = dict(blocks=nblocks.get(phase.name, 0), interrupted=len(excluded))
    order = [(b['pop'], b['index'], b['arms']) for b in wl['blocks']]
    arms_of = {i: arms for _, i, arms in order}
    kept, skipped, cut = {}, [], None
    for pop, i, arms in order:
        if (pop, i) in rows and set(rows[(pop, i)]) == set(arms):
            kept[(pop, i)] = rows[(pop, i)]
        elif (pop, i) in retired:
            skipped.append(i)
        else:
            cut = i; break
    check_more(kept, cfg, arms_of)
    beyond = sorted(i for (_, i) in rows if ('X', i) not in kept)
    return kept, dict(host=host, phases=per_phase, prefix_blocks=len(kept), first_incomplete_index=cut,
                      yield_retired_skipped=skipped, complete_beyond_prefix_dropped=len(beyond))


def summary(rows, cfg, arm):
    games = [g[arm] for g in rows.values() if arm in g]
    s = X.summarize(games, cfg['arms'][arm]); s['seeds'] = len(games)
    return s


def diffs(rows, l, r):
    return [g[l]['loss']-g[r]['loss'] for g in rows.values() if l in g and r in g]


def outcome(c):
    lo, hi = c['ci95_pp']
    if hi <= 1.0:
        return 'always-on supported' + (' (small positive cost: lower CI > 0)' if lo > 0 else '')
    if lo > 0:
        return 'speed gate needed'
    return 'unresolved'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phases-03', type=Path, nargs='*', default=[])
    ap.add_argument('--phases-04', type=Path, nargs='*', default=[])
    ap.add_argument('--x4s-mirror', action='store_true', help='also pool with X4S (200) and X4S2 phase E (180) on 05')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    cfg = json.loads((HERE/'plan-fsc-04.json').read_text()); base = json.loads((HERE/'plan-fsc.json').read_text())
    assert all(cfg['arms'][k] == v for k, v in base['arms'].items()) and cfg['seed_ranges'] == base['seed_ranges']
    shas = {sha(HERE/'plan-fsc.json'), sha(HERE/'plan-fsc-04.json')}
    X.CONFIG_SHAS.clear(); X.CONFIG_SHAS.update(shas)
    hosts = {}
    for host, phases in (('127x03', a.phases_03), ('127x04', a.phases_04)):
        if phases:
            hosts[host] = load_host(host, phases, cfg, shas)
    out = dict(utc=X.utc(), label='FSC exploration, NEVER ADOPTABLE', reducer_sha256=sha(__file__),
               x4s2_reduce_sha256=sha(HERE.parent/'x4s2'/'reduce.py'), config_sha256=sorted(shas),
               bootstrap=cfg['bootstrap'], hosts={h: v[1] for h, v in hosts.items()}, arms={}, contrasts={})
    allrows = {k: v for h in hosts.values() for k, v in h[0].items()}
    for arm in ('K4-200', 'K4S-200', 'K4-180', 'K4S-180'):
        if any(arm in g for g in allrows.values()):
            out['arms'][arm] = summary(allrows, cfg, arm)
    d200 = diffs(allrows, 'K4S-200', 'K4-200')
    if d200:
        p = boot([d200], cfg); p['outcome'] = outcome(p)
        out['contrasts']['PRIMARY K4S-200 minus K4-200 (all prefix blocks, both hosts)'] = p
    for h, (rows, _) in hosts.items():
        d = diffs(rows, 'K4S-200', 'K4-200')
        if d: out['contrasts'][f'K4S-200 minus K4-200 ({h} only)'] = boot([d], cfg)
    if '127x03' in hosts:
        d = diffs({k: v for k, v in hosts['127x03'][0].items() if k[1] < 2400}, 'K4S-200', 'K4-200')
        if d: out['contrasts']['K4S-200 minus K4-200 (03, indices < 2400)'] = boot([d], cfg)
    d180 = diffs(allrows, 'K4S-180', 'K4-180')
    if d180:
        out['contrasts']['K4S-180 minus K4-180 (descriptive)'] = boot([d180], cfg)
    if a.x4s_mirror:
        old = X.load_x4s()
        dx = [g['K4S-200']['loss']-g['K4-200']['loss'] for g in old.values() if 'K4S-200' in g and 'K4-200' in g]
        if d200: out['contrasts']['SECONDARY K4S-200 minus K4-200 pooled with X4S 600 X seeds (stratified)'] = boot([d200, dx], cfg)
        X.CONFIG_SHAS.clear(); X.CONFIG_SHAS.update({sha(HERE.parent/'x4s2'/'plan.json'), sha(HERE.parent/'x4s2'/'plan-ext.json')})
        ext = json.loads((HERE.parent/'x4s2'/'plan-ext.json').read_text())
        e, _, _, _ = X.load_x4s2(X4S2_E, ext, 'reporting', {'X'})
        de = [g['K4S-180']['loss']-g['K4-180']['loss'] for g in e.values() if 'K4S-180' in g and 'K4-180' in g]
        if d180: out['contrasts']['K4S-180 minus K4-180 pooled with X4S2 phase E X seeds (stratified, descriptive)'] = boot([d180, de], cfg)
    a.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(utc=out['utc'], hosts={h: v['prefix_blocks'] for h, v in out['hosts'].items()})))


if __name__ == '__main__':
    main()
