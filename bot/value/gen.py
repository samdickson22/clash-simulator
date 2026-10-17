"""Value-net data: K4S-st games on a fresh bank, dumping the planner's public search roots (exploration).

    python -m bot.value.gen --out DIR --pool R3a,v1 --games 2000 --workers 12 --base BASE

Game g is case x4s_setup(g, BASE) (candidate seat g%2, X-deck g%5 vs (g//5)%5), opponent
pool[g % len(pool)], candidate = --candidate (default K4S-st). BASE must be disjoint from the
HEADLINE bank (checked). At every searched decision of the candidate we store, for the root the
planner actually scores (public info + belief-sampled hidden opponent hand: fair), the native
public_view of BOTH seats, phi's evaluation_parts (seat-0 frame) and the tick. The final outcome
is attached per game. Output: DIR/roots/game-<g>.jsonl.gz (line 0 = header) and
DIR/games-<worker>.jsonl (one line per finished game; resume key = g).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from multiprocessing import Process
from pathlib import Path


class RootLogger:
    """Wraps a search player; records public features of every scored root."""

    def __init__(self, inner, native, rt=None):
        self.inner, self.native, self.rows, self.rt = inner, native, [], rt
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds
        self.shadow = self.probe = None

    def start(self, ctx):
        self.inner.start(ctx)
        core, native, rows = self.inner.p.core, self.native, self.rows
        orig = core.score_candidates
        if os.environ.get('BOT_VN_TEACHER'):   # value_net heads on the seat's own v5 packet at every root
            from policy import V1Policy
            from bot.fullpool.value_net import ValueProbe
            from bot.players.policy import POLICY_SEED_OFFSET
            if not hasattr(RootLogger, '_probe'):
                RootLogger._probe = ValueProbe(os.environ['BOT_VN_TEACHER'])
            self.probe = RootLogger._probe
            self.shadow = V1Policy(self.probe, self.rt.R.builder, self.rt.R.costs, ctx.seat, list(ctx.own_order),
                                   ctx.seed + POLICY_SEED_OFFSET + ctx.seat)
        probe = self.probe

        def score(root, seat, candidates, **kw):
            action = orig(root, seat, candidates, **kw)
            row = dict(tick=int(core.info.tick), seat=seat, action=int(action),
                       parts=list(native.evaluation_parts(root)),
                       pv=[json.loads(native.public_view(root, s)) for s in (0, 1)])
            if probe is not None and probe.tick == row['tick']:
                row['vn'] = probe.last
            rows.append(row)
            return action
        core.score_candidates = score

    def act(self, view):
        if self.shadow is not None:
            self.probe.last = None
            self.shadow.poll(view.tick, view.reserved.packet, view.public_events)
            self.probe.tick = int(view.tick) if self.probe.last is not None else None
        return self.inner.act(view)

    def close(self):
        self.inner.close()


def done_games(out: Path):
    keys = set()
    for p in out.glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                if 'error' not in r:
                    keys.add(r['game'])
            except Exception:
                pass
    return keys


def worker(wid, games, a):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import case as make_case, check_scope, select
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)          # BOT_FULLPOOL_POLICIES; unset = no-op
    select(rt, a.decks)           # x4s = no-op (C56 HEADLINE-v1 setup)
    check_scope(rt, a.decks, len(games), min(games, default=0), a.base)
    out = Path(a.out)
    (out / 'roots').mkdir(parents=True, exist_ok=True)
    pool = a.pool.split(',')
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for g in games:
        if (out / 'STOP').exists():
            break
        case = make_case(rt, g, a.base, a.decks)   # decks='x4s' -> x4s_setup (unchanged)
        seat, opp = case['seat'], pool[g % len(pool)]
        t0 = time.time()
        try:
            cand = RootLogger(make_player(rt, a.candidate), rt.R.native, rt)
            players = {seat: cand, 1 - seat: make_player(rt, opp)}
            res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
            head = dict(game=g, seed=case['seed'], seat=seat, opponent=opp, candidate=a.candidate,
                        winner=w, score=score, ticks=res['ticks'], towers=res['towers'], decks=case['decks'])
            tmp = out / 'roots' / f'game-{g:07d}.jsonl.gz.tmp'
            with gzip.open(tmp, 'wt') as z:
                z.write(json.dumps(head) + '\n')
                for r in cand.rows:
                    z.write(json.dumps(r) + '\n')
            tmp.rename(out / 'roots' / f'game-{g:07d}.jsonl.gz')
            row = dict(head, roots=len(cand.rows), cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0)
        except Exception as ex:  # recorded, never silently dropped
            row = dict(game=g, seat=seat, opponent=opp, error=repr(ex)[:500])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def main():
    from bot.exit.generate import check_bank
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--candidate', default='K4S-st')
    ap.add_argument('--pool', default='R3a,v1')
    ap.add_argument('--games', type=int, default=2000)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--decks', default='x4s', help="deck spec of bot/fullpool/banks.py, e.g. 'fullpool:<seed>:freq=<sha12>'")
    a = ap.parse_args()
    check_bank(a.base, a.start, a.games)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    done = done_games(out)
    games = [g for g in range(a.start, a.start + a.games) if g not in done]
    (out / 'launch.json').write_text(json.dumps(dict(args=vars(a), jobs=len(games), started=time.time())))
    procs = [Process(target=worker, args=(w, games[w::a.workers], a)) for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    bad = [p.exitcode for p in procs if p.exitcode]   # a crashed worker must fail the job (wrappers log rc)
    if bad:
        raise SystemExit(f'{len(bad)} worker process(es) failed, exit codes {bad[:8]}')


if __name__ == '__main__':
    main()
