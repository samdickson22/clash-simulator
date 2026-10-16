"""Record a real opponent's decisions as native public views, to train a learned rollout opponent (exploration).

    python -m bot.search.lopp_record --out DIR --candidate K4C-r16 --opponents R3a,v1 --games 600 \
        --base 2249738988533344 --workers 100

Same cases, match loop and game rows as bot.eval.headline (rows are summarize/pair_by_name compatible). The
opponent player is wrapped: at every poll where its channel is free (can_act), the wrapper builds the Rust state
from the OPPONENT's own Information with the planner's own reconstruction (fair_player.Resources.root: public
entities + own HUD; the other hand is a placeholder copy, which neither public_view nor public_mask of the
acting seat reads) and records native public_view / public_mask of that seat plus the action the opponent took.
This is exactly the input a learned opponent sees inside K4C-r16's rollouts. The wrapper draws from its own
generator only, so the match is unchanged (checked against the earlier games of the same cases by
command_sha256).

DIR/rec-<worker>.jsonl.gz: one line per game {index, opponent, seat, rows: [[tick, action, wait_ticks,
view_json, mask_hex|null, legal|null], ...]}; mask_hex = packed public_mask[:2304] on plays only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

import numpy as np

from bot.eval.headline import done_keys, make_player
from bot.players.base import WAIT


class RecordingPlayer:
    def __init__(self, rt, inner):
        self.rt, self.inner = rt, inner
        self.name = inner.name
        self.deadline_seconds = inner.deadline_seconds
        self.rows, self.errors = [], 0

    def start(self, ctx):
        self.inner.start(ctx)
        self.seat = ctx.seat
        self.rng = np.random.default_rng([ctx.seed, 0x10bb, ctx.seat])

    def act(self, view):
        decision = self.inner.act(view)
        if view.can_act:
            try:
                R, info = self.rt.R, view.info
                root = R.root(info, dict(info.own), self.rng)
                vj = R.native.public_view(root, self.seat)
                a = int(decision.action)
                mask_hex = legal = None
                if a < WAIT:
                    mask = np.asarray(R.native.public_mask(root, self.seat), dtype=bool)
                    mask_hex = np.packbits(mask[:2304]).tobytes().hex()
                    legal = bool(mask[a])
                self.rows.append([int(view.tick), a, int(decision.wait_ticks), vj, mask_hex, legal])
            except Exception:
                self.errors += 1
        return decision

    def close(self):
        self.inner.close()


def worker(wid, jobs, out: Path, base: int, decks: str = 'x4s'):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.fullpool.banks import case as make_case, check_scope, select
    rt = Runtime()
    select(rt, decks)
    check_scope(rt, decks, len(jobs), min((i for _, _, i in jobs), default=0), base)
    from bot.fullpool.provenance import runtime_tag
    tag = runtime_tag(rt)
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    rec = gzip.open(out / f'rec-{wid:03d}.jsonl.gz', 'at')
    for cand, opp, i in jobs:
        case = make_case(rt, i, base, decks)   # 'x4s' -> x4s_setup
        t0 = time.time()
        try:
            seat = case['seat']
            wrapped = RecordingPlayer(rt, make_player(rt, opp))
            players = {seat: make_player(rt, cand), 1 - seat: wrapped}
            res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
            row = dict(engine='ours', candidate=cand, opponent=opp, index=i, seat=seat, seed=case['seed'],
                       score=score, winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0,
                       rec_rows=len(wrapped.rows), rec_errors=wrapped.errors, runtime=tag)
            rec.write(json.dumps(dict(index=i, opponent=opp, seat=1 - seat, runtime=tag, rows=wrapped.rows)) + '\n')
            rec.flush()
        except Exception as ex:  # recorded, never silently dropped
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], error=repr(ex)[:500],
                       trace=traceback.format_exc()[-2000:])
        fh.write(json.dumps(row) + '\n'); fh.flush()
    rec.close()


def main():
    from bot.eval.headline import reap
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', default='K4C-r16')
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--decks', default='x4s', help="'x4s' or a full-pool deck spec, e.g. 'fullpool:<seed>:own=c56' "
                    "(the search candidate needs a C56 deck; bot/fullpool/banks.py)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',')
            for i in range(a.start, a.start + a.games) if (c, o, i) not in done]
    shares = [jobs[w::a.workers] for w in range(a.workers)]
    (a.out / 'launch.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                                       jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a.out, a.base, a.decks)) for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
