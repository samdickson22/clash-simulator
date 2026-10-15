"""bot.eval.headline for timing-sensitive wall arms: one game per dedicated core group, pinned (LIVE deliverable 4).

    CLASHER_BOT_RUNTIME=... python -m bot.live.headline_wall --out DIR --cores 0-59 --group 5 \
        --candidate K4CW-r16-w200-t4,K4CW-r16-w150-t4,K4CW-r16-w120-t4 --opponents v1,R3a --games 300 \
        [--engine rsim15535]

Identical to bot.eval.headline (same HEADLINE base, x4s_setup cases, play_match, scoring, row schema, resumable
games-*.jsonl) except:
- player names also resolve through bot.live.player.make_live_player (K4CW-*, LIVE-*);
- --cores lists PHYSICAL cores reserved for this run; they are split into groups of --group (default 5 = 4 search
  threads + 1 for the engine/poller), one worker process per group, pinned with sched_setaffinity (taskset).
  The SMT siblings of those cores (cpu+64 on a 3990X) must be left idle by the host owner; this tool checks
  nothing about other tenants.
Pair against the deterministic K4C-r16 side with bot/eval/pair_by_name.py (same base, same indices).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path


def parse_cores(text):
    out = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        out += list(range(int(a), int(b or a)+1))
    if len(set(out)) != len(out):
        raise ValueError('duplicate cores')
    return out


def pinned_worker(wid, cores, jobs, out, base, engine):
    os.sched_setaffinity(0, cores)
    import bot.eval.headline as headline
    from bot.live.player import make_live_player
    headline.make_player = make_live_player       # worker() resolves the module global at call time
    headline.worker(wid, jobs, out, base, engine)


def main():
    from bot.eval.headline import HEADLINE_BASE, done_keys, reap
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--cores', required=True, help="physical cores, e.g. '0-59' or '0-29,32-61'")
    ap.add_argument('--group', type=int, default=5)
    ap.add_argument('--base', type=int, default=HEADLINE_BASE)
    ap.add_argument('--engine', default='ours', choices=['ours', 'rsim15535', 'rsim16402'])
    a = ap.parse_args()
    cores = parse_cores(a.cores)
    groups = [cores[i:i+a.group] for i in range(0, len(cores) - a.group + 1, a.group)]
    if not groups:
        raise SystemExit('fewer cores than one group')
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for i in range(a.start, a.start + a.games) for c in a.candidate.split(',')
            for o in a.opponents.split(',') if (c, o, i) not in done]
    shares = [jobs[w::len(groups)] for w in range(len(groups))]
    (a.out / 'launch.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, groups=groups, jobs=len(jobs), started=time.time(),
        tool='bot.live.headline_wall')))
    procs = [Process(target=pinned_worker, args=(w, g, s, a.out, a.base, a.engine))
             for w, (g, s) in enumerate(zip(groups, shares)) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
