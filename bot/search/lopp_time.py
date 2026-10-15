"""Per-decision wall/CPU of search arms on pinned cores, HEADLINE games in our engine (exploration).

    python -m bot.search.lopp_time --out DIR --candidate K4L-R-gs,K4C-r16 --opponents R3a,v1 --games 10 \
        --cores 0-9 [--group 1] [--start 0]

One worker process per group of --group PHYSICAL cores, pinned with sched_setaffinity (bot.live.headline_wall's
convention: a 3990X core c has SMT sibling c+64; this tool does not reserve siblings, it MEASURES them: the busy
share of the group's sibling logical CPUs over the run is written to every row as `sibling_busy`). Players come
from bot.eval.headline.make_player (K4L-*, K4C-*, ...), games are play_match on x4s_setup cases, rows carry the
command_sha256 so a pooled/threaded arm can be checked against its serial twin.

Per searched decision (decision.stats is not None) it records, in ms: wall and process CPU of act (the
candidate's own process; pool workers' CPU is reported by the arm as stats['pool_cpu']), wall of
core.score_candidates (`search`; the rest of act is preparation: R3a poll, belief, candidates, root), rollouts,
the arm's hit flag (search incomplete at the cutoff) and `default` (the cutoff default was played: S-default rule,
a preparation cutoff, or a LIVE- default source). `python -m bot.search.lopp_time --summary DIR` prints p50/p95/p99/mean per arm.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path


def cpu_ticks(cpus):
    busy = total = 0
    for line in Path('/proc/stat').read_text().splitlines():
        head, *vals = line.split()
        if head.startswith('cpu') and head[3:].isdigit() and int(head[3:]) in cpus:
            v = [int(x) for x in vals]
            idle = v[3] + v[4]
            busy += sum(v[:8]) - idle
            total += sum(v[:8])
    return busy, total


def instrument(player, log):
    """Wrap act and (after start) core.score_candidates; append one dict per searched decision to `log`."""
    orig_start, orig_act = player.start, player.act
    box = {}

    def start(ctx):
        orig_start(ctx)
        core = player.p.core if hasattr(player, 'p') else player.search.p.core
        inner = core.score_candidates

        def score(*a, **kw):
            t0 = time.monotonic()
            try:
                return inner(*a, **kw)
            finally:
                box['search'] = time.monotonic() - t0
        core.score_candidates = score

    def act(view, **kw):
        box.clear()
        w0, c0 = time.monotonic(), time.process_time()
        d = orig_act(view, **kw)
        wall, cpu = time.monotonic() - w0, time.process_time() - c0
        if d.stats is not None:
            s = d.stats
            log.append(dict(wall=round(1e3 * wall, 3), cpu=round(1e3 * cpu, 3),
                            search=round(1e3 * box.get('search', 0.), 3), rollouts=s.get('rollouts'),
                            learned=s.get('learned'), hit=bool(s.get('hit')), phase=s.get('phase_ms'),
                            default=bool(s.get('student_default')) or str(s.get('source', '')).startswith('default')
                            or 'preparation_cutoff' in s,
                            pool_cpu=None if s.get('pool_cpu') is None else round(1e3 * s['pool_cpu'], 3),
                            tick=int(view.tick)))
        return d
    player.start, player.act = start, act


def make_player(rt, name):
    """bot.eval.headline names plus LIVE-K4L-* (bot/search/lopp_fast.py) and K4CW-*/LIVE-* (bot/live/player.py)."""
    if name.startswith('LIVE-K4L-'):
        from bot.search.lopp_fast import make_live_lopp
        return make_live_lopp(rt, name)
    if name.startswith(('LIVE-', 'K4CW-', 'PERC-')):
        from bot.live.player import make_live_player
        return make_live_player(rt, name)
    from bot.eval.headline import make_player as headline_player
    return headline_player(rt, name)


def worker(wid, cores, jobs, out, base, fast_prep=False):
    os.sched_setaffinity(0, cores)
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    rt = Runtime()
    if fast_prep:      # every arm in this run gets lopp_fast's output-identical preparation caches
        from bot.search.lopp_fast import install_fast_prep
        install_fast_prep(rt)
    sib = {c + 64 for c in cores}
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = x4s_setup(rt, i, base)
        seat = case['seat']
        log = []
        s0 = cpu_ticks(sib)
        t0 = time.time()
        try:
            player = make_player(rt, cand)
            instrument(player, log)
            res = play_match(rt, {seat: player, 1 - seat: make_player(rt, opp)}, seed=case['seed'],
                             decks=case['decks'])
            s1 = cpu_ticks(sib)
            w = res['winner']
            row = dict(candidate=cand, opponent=opp, index=i, seat=seat, cores=cores,
                       score=0.5 if w is None or w == -1 else float(w == seat),
                       command_sha256=res['command_sha256'], wall_seconds=time.time() - t0,
                       sibling_busy=(s1[0] - s0[0]) / max(1, s1[1] - s0[1]), loadavg=os.getloadavg()[0],
                       decisions=log)
        except Exception as ex:
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, error=repr(ex)[:500],
                       trace=traceback.format_exc()[-2000:])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def parse_cores(text):
    out = []
    for part in text.split(','):
        lo, _, hi = part.partition('-')
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float('nan')


def summary(dirs):
    from collections import defaultdict
    by = defaultdict(list)
    meta = defaultdict(lambda: dict(games=0, errors=0, sib=[]))
    for d in dirs:
        for p in sorted(Path(d).glob('games-*.jsonl')):
            for line in p.read_text().splitlines():
                r = json.loads(line)
                m = meta[r['candidate']]
                if 'error' in r:
                    m['errors'] += 1
                    continue
                m['games'] += 1
                m['sib'].append(r['sibling_busy'])
                by[r['candidate']] += r['decisions']
    print('| arm | games | decisions | wall p50/p95/p99/mean ms | CPU mean ms | search p50/p95 ms | '
          'prep p50/p95 ms | pool CPU mean ms | rollouts | hit | default | sibling busy | errors |')
    print('|---' * 13 + '|')
    for arm, ds in sorted(by.items()):
        w = [d['wall'] for d in ds]
        c = [d['cpu'] for d in ds]
        s = [d['search'] for d in ds]
        prep = [d['wall'] - d['search'] for d in ds]
        pc = [d['pool_cpu'] for d in ds if d.get('pool_cpu') is not None]
        ro = [d['rollouts'] for d in ds if d.get('rollouts') is not None]
        m = meta[arm]
        print(f"| {arm} | {m['games']} | {len(ds)} | {pct(w, .5):.0f}/{pct(w, .95):.0f}/{pct(w, .99):.0f}/"
              f"{sum(w) / len(w):.0f} | {sum(c) / len(c):.0f} | {pct(s, .5):.0f}/{pct(s, .95):.0f} | "
              f"{pct(prep, .5):.0f}/{pct(prep, .95):.0f} | {sum(pc) / len(pc) if pc else float('nan'):.0f} | "
              f"{sum(ro) / max(1, len(ro)):.1f} | {sum(d['hit'] for d in ds) / len(ds):.3f} | "
              f"{sum(d.get('default', False) for d in ds) / len(ds):.3f} | "
              f"{sum(m['sib']) / max(1, len(m['sib'])):.2f} | {m['errors']} |")
    for arm, ds in sorted(by.items()):
        ph = [d['phase'] for d in ds if d.get('phase')]
        if ph:
            keys = sorted({k for p in ph for k in p})
            print(f"{arm} phases ms (p50/p95): " + ', '.join(
                f"{k} {pct([p[k] for p in ph if k in p], .5):.1f}/{pct([p[k] for p in ph if k in p], .95):.1f}"
                for k in keys))


def main():
    from bot.eval.headline import HEADLINE_BASE, done_keys, reap
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path)
    ap.add_argument('--candidate')
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--games', type=int, default=10)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--cores')
    ap.add_argument('--group', type=int, default=1)
    ap.add_argument('--base', type=int, default=HEADLINE_BASE)
    ap.add_argument('--summary', nargs='+')
    ap.add_argument('--fast-prep', action='store_true', help='install lopp_fast.install_fast_prep for every arm')
    a = ap.parse_args()
    if a.summary:
        return summary(a.summary)
    cores = parse_cores(a.cores)
    groups = [cores[i:i + a.group] for i in range(0, len(cores) - a.group + 1, a.group)]
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for i in range(a.start, a.start + a.games) for o in a.opponents.split(',')
            for c in a.candidate.split(',') if (c, o, i) not in done]
    shares = [jobs[w::len(groups)] for w in range(len(groups))]
    (a.out / f'launch-{int(time.time())}.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, groups=groups, jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, g, s, a.out, a.base, a.fast_prep))
             for w, (g, s) in enumerate(zip(groups, shares)) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
