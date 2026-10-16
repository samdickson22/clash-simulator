"""Sim twin of the live diagnosis: the live deck and player in RoyaleSim 15.535, logged in the live-log shape
(bot lead live-diag, exploration tier).

Case i (bank BASE): our seat i%2; our deck = the live e16 deck, the opponent's = GIANT_DECKS[(i//2) % n]; both
shuffled by Random(BASE+i) (own first). Per game the candidate's seat writes, in its OWN frame (x, y tiles, own king
at y=0, as live perception):
  perc  one row per 5-tick poll: tick, units [{owner 0 own / 1 enemy, cls RoyaleSim unit type, x, y}], hand (own HUD
        cards), elixir, enemy tower alive flags;
  dec   one row per poll: the candidate's action, submitted (can_act and a play), stats (LivePlayer source, ...),
        card (the hand card in the action's slot).
Analysed by bot.livediag.live_metrics.analyse, the same code as the live sessions.

    CLASHER_BOT_RUNTIME=.../r1 CLASHER_BOT_RUNTIME_PINS=r1-total CLASHER_DELAY_NATIVE_DIR=.../native-total-r1 \
    CLASHER_LIVE_FAST=student:<rl5 v10>@0.5375 python -m bot.livediag.sim_diag --out DIR \
        --candidate LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponents R3a,v1,rext-bc --games 34 --workers 6 --cores 0-29
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from multiprocessing import Process
from pathlib import Path

LIVE_DECK = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
BASE = 0x5ee0_1d1a_6000     # fixed for this diagnosis (not a HEADLINE bank; nothing is selected on it)
WAIT = 2304


def giant_decks(rt, n=4):
    """The live deck (mirror) + the n most frequent human prior decks holding Giant (C56 catalog)."""
    decks = [list(LIVE_DECK)]
    for d in sorted(rt.PRIOR['decks'], key=lambda d: -float(d.get('frequency', 0))):
        if 'Giant' in d['cards'] and sorted(d['cards']) != sorted(LIVE_DECK):
            decks.append(list(d['cards']))
        if len(decks) > n:
            break
    return decks


class Recorder:
    """Wraps the candidate; reads the RoyaleSim state the match loop already holds (offline logging only, never a
    player input)."""

    def __init__(self, inner, seat):
        self.inner, self.seat, self.name = inner, seat, inner.name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)
        self.perc, self.dec = [], []

    def bind_rsim(self, m):
        self.m = m
        if hasattr(self.inner, 'bind_rsim'):
            self.inner.bind_rsim(m)

    def start(self, ctx):
        self.inner.start(ctx)

    def close(self):
        self.inner.close()

    def frame(self, x, y):
        return (x, y) if self.seat == 0 else (18 - x, 32 - y)

    def act(self, view):
        d = self.inner.act(view)
        m, s = self.m, self.m.state
        F, units = m.tr.F, []
        for e in s['entities']:
            if e[F['kind']] in (2, 3):
                continue
            team = e[F['team']]
            if team != self.seat and e[F['status_flags']] & 3:
                continue
            x, y = self.frame(e[F['x']]/18000., e[F['y']]/18000.)
            units.append(dict(owner=0 if team == self.seat else 1, cls=m.tr.types[e[F['unit_type']]],
                              x=round(x, 2), y=round(y, 2)))
        me = s['players'][self.seat]
        hand = [m.hand_card(self.seat, k) for k in range(4)]
        n = len(self.perc)
        self.perc.append(dict(n=n, tick=view.tick, units=units, hand=dict(cards=hand), elixir=me['elixir_milli']/1000.,
                              enemy_towers=[int(v > 0) for v in s['players'][1-self.seat]['tower_hp']]))
        a = int(d.action)
        sub = bool(view.can_act and a < WAIT)
        self.dec.append(dict(n=n, tick=view.tick, action=a, submitted=sub, stats=_slim(d.stats), can_act=view.can_act,
                             wait_ticks=d.wait_ticks,
                             card=hand[a // 576] if sub else None))
        return d


def _slim(stats):
    if not stats:
        return None
    keep = ('source', 'action', 'fast_action', 'hit', 'fallback', 'student_default', 'preparation_cutoff',
            'completed', 'candidates', 'rollouts', 'search_wall_ms', 'wall_ms', 'timed_wait', 'interrupts')
    return {k: stats[k] for k in keep if k in stats}


def worker(wid, cores, jobs, out, base):
    if cores:
        os.sched_setaffinity(0, cores)
    from bot.players.runtime import Runtime
    from bot.players.royalesim_match import play_match
    from bot.players.royalesim_vocab import load
    from bot.live.player import make_live_player
    rt = Runtime()
    import clasher.rl    # r1's frozen clasher lacks main's self-contained slot_permission (legacy mode = passthrough)
    clasher.rl.__path__.append(str(Path(__file__).resolve().parents[2]/'src/clasher/rl'))
    vocab = load(rt)
    decks = giant_decks(rt)
    from bot.livediag.variants import make_variant
    make = lambda rt, name: make_variant(rt, name) if name.startswith('LD-') else make_live_player(rt, name)
    path = out/f'games-{wid}.jsonl'
    for cand, opp, i in jobs:
        seat = i % 2
        own, other = list(LIVE_DECK), list(decks[(i//2) % len(decks)])
        rng = random.Random(base + i)
        rng.shuffle(own); rng.shuffle(other)
        rec = Recorder(make(rt, cand), seat)
        players = {seat: rec, 1-seat: make_live_player(rt, opp)}
        t0 = time.time()
        try:
            res = play_match(rt, players, seed=base+i, decks=[own, other] if seat == 0 else [other, own],
                             vocab=vocab, verbose=True)
            row = dict(candidate=cand, opponent=opp, index=i, seat=seat, opp_deck=(i//2) % len(decks),
                       winner=res['winner'], draw=res.get('draw'), crowns=res['crowns'], ticks=res['ticks'],
                       score=1. if res['winner'] == seat else (0.5 if res['winner'] is None else 0.),
                       opp_plays=[(t, c) for t, c, _, ok in res['play_log'][1-seat] if ok],
                       own_plays=[(t, c, a) for t, c, a, ok in res['play_log'][seat] if ok],
                       perc=rec.perc, dec=rec.dec, seconds=round(time.time()-t0, 1))
        except Exception as ex:
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, error=traceback.format_exc()[-1500:])
        with open(path, 'a') as f:
            f.write(json.dumps(row) + '\n')


def done(out):
    keys = set()
    for p in out.glob('games-*.jsonl'):
        for l in p.read_text().splitlines():
            try:
                r = json.loads(l)
                if 'error' not in r:
                    keys.add((r['candidate'], r['opponent'], r['index']))
            except Exception:
                pass
    return keys


def main():
    from bot.live.headline_wall import parse_cores
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=34)
    ap.add_argument('--base', type=int, default=BASE)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--cores', default='', help="physical cores split evenly over workers ('' = unpinned)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    have = done(a.out)
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',') for i in range(a.games)
            if (c, o, i) not in have]
    cores = parse_cores(a.cores) if a.cores else []
    per = len(cores)//a.workers if cores else 0
    (a.out/'launch.json').write_text(json.dumps(dict(vars(a), out=str(a.out), jobs=len(jobs),
                                                     started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                     fast=os.environ.get('CLASHER_LIVE_FAST'))) + '\n')
    procs = [Process(target=worker, args=(w, cores[w*per:(w+1)*per] if per else [], jobs[w::a.workers], a.out, a.base))
             for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
