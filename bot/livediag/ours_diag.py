"""Engine-agnostic twin of sim_diag: bot.eval.headline cases and players (our engine by default, full-pool banks/decks,
BOT_FULLPOOL_POLICIES / BOT_BELIEF_PRIOR env as headline) with a packet-only recorder around the candidate, so
bot.livediag.sim_report computes the same metrics (reaction, undefended Giant pushes, plays by card) on full-pool runs.

The recorder reads only the candidate's own public view (contract-v5 packet, own frame): units = troop/building
entity rows (x = f0*18, y = f1*32, owner from the own/enemy flags, cls = body token name), hand from hand_ids, elixir
from the globals. Opponent plays come from play_match's play log (verbose). Rows: games-*.jsonl with candidate,
opponent, index, seat, score, perc, dec, opp_plays (sim_diag schema).

    ROOT=... PINS=live16402b-r3 source bot/fullpool/run/env.sh; python -m bot.livediag.ours_diag --out DIR \
        --candidate K4L-R-gs-mk1a1,K4L-R-gs-mk1a1-res --opponents LIVE-K4CW-r16 --games 100 --base B --decks e16bl
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

WAIT = 2304


class PacketRecorder:
    def __init__(self, rt, inner):
        self.rt, self.inner, self.name = rt, inner, inner.name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)
        self.perc, self.dec = [], []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def start(self, ctx):
        self.inner.start(ctx)

    def close(self):
        self.inner.close()

    def act(self, view):
        d = self.inner.act(view)
        self.record(view, d)
        return d

    def record(self, view, d):
        """Record an already completed decision; usable outside the match's lateness timer."""
        b = self.rt.R.builder
        names = b.token_names
        obs = view.info.packet.observation
        units = []
        for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
            f, tok = obs.entity_features[i], int(obs.entity_ids[i])
            nm = names[tok] if 0 <= tok < len(names) else str(tok)
            if nm in ('Tower', 'KingTower') or not (f[4] > .5 or f[5] > .5):
                continue
            units.append(dict(owner=0 if f[2] > .5 else 1, cls=nm, x=round(float(f[0]) * 18, 2),
                              y=round(float(f[1]) * 32, 2)))
        hand = [b.card_name_for_token_id(int(t)) if int(t) > 0 else None for t in list(obs.hand_ids)[:4]]
        n = len(self.perc)
        self.perc.append(dict(n=n, tick=view.tick, units=units, hand=dict(cards=hand),
                              elixir=float(obs.global_features[5]) * 10))
        a = int(d.action)
        sub = bool(view.can_act and a < WAIT)
        st = d.stats
        self.dec.append(dict(n=n, tick=view.tick, action=a, submitted=sub, can_act=view.can_act,
                             wait_ticks=d.wait_ticks, card=hand[a // 576] if sub else None,
                             stats=None if not st else {k: st[k] for k in ('source', 'hit', 'completed', 'timed_wait')
                                                        if k in st} or {'source': 'search'}))


def worker(wid, jobs, out, base, decks, engine):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.fullpool.banks import case as make_case, check_scope, select
    from bot.fullpool.models import install_from_env
    from bot.eval.headline import make_player
    rt = Runtime()
    install_from_env(rt)
    select(rt, decks, None)
    check_scope(rt, decks, len(jobs), min((i for _, _, i in jobs), default=0), base)
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = make_case(rt, i, base, decks)
        seat = case['seat']
        t0 = time.time()
        try:
            if cand.startswith('histnoise:'):        # bot/livediag/history_noise.py
                from bot.livediag.history_noise import NoisyPlayer, install_observe_patch
                install_observe_patch()
                _, arm, inner = cand.split(':', 2)
                pl = NoisyPlayer(rt, make_player(rt, inner), arm, cand)
                pl.opp_deck = list(case['decks'][1 - seat])
            else:
                pl = make_player(rt, cand)
            rec = PacketRecorder(rt, pl)
            res = play_match(rt, {seat: rec, 1 - seat: make_player(rt, opp)}, seed=case['seed'], decks=case['decks'],
                             verbose=True)
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
            log = res['play_log']
            row = dict(engine=engine, candidate=cand, opponent=opp, index=i, seat=seat, score=score, winner=w,
                       ticks=res['ticks'], command_sha256=res['command_sha256'], deck_lists=case['decks'],
                       opp_plays=[(t, c) for t, c, _, ok in log[1 - seat] if ok],
                       perc=rec.perc, dec=rec.dec, seconds=round(time.time() - t0, 1),
                       noise=dict(getattr(getattr(pl, 'noise', None), 'counts', {}) or {}))
        except Exception:
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, seat=seat, error=traceback.format_exc()[-1500:])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=100)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--decks', default='e16bl')
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    have = set()
    for p in a.out.glob('games-*.jsonl'):
        for l in p.read_text().splitlines():
            r = json.loads(l)
            if 'error' not in r:
                have.add((r['candidate'], r['opponent'], r['index']))
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',')
            for i in range(a.start, a.start + a.games) if (c, o, i) not in have]
    (a.out / 'launch.json').write_text(json.dumps(dict(vars(a), out=str(a.out), jobs=len(jobs),
        started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        env={k: os.environ.get(k) for k in ('CLASHER_BOT_RUNTIME', 'CLASHER_BOT_RUNTIME_PINS', 'CLASHER_LOPP_MODELS',
                                            'BOT_FULLPOOL_POLICIES', 'BOT_BELIEF_PRIOR')})) + '\n')
    procs = [Process(target=worker, args=(w, jobs[w::a.workers], a.out, a.base, a.decks, 'ours'))
             for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
