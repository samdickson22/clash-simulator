"""Monte Carlo sibling-leaf targets (exploration; BOT LEAD 2026-10-17: change the target, not the model).

    python -m bot.fullpool.mc_gen --out DIR --games N --start S --base BASE --workers W [--k 3 --n 16 --horizon 600]

Realized outcomes of single on-policy branches were too noisy / confounded to rank sibling leaves (value-net v1 and
sibling_fit: pair accuracy 0.52-0.55 vs the search score's 0.552-0.571). Here each sibling leaf gets a low-variance
target: the mean over N continuations of the margin `horizon` ticks after the leaf, all under the SAME continuation
policy for every sibling (our side scripted balanced, the opponent K4L's learned rollout model k1a1 sampled), with common
random numbers across siblings (continuation j of every sibling uses opponent seed [match seed, root tick, j]).
Games: as bot/fullpool/sibling_gen (our deck rotates over s62/e16/Inferno x3 + the 91 Battle Log decks, opponent deck a
full-pool training-sampler deck, opponents LIVE-K4CW-r16 x2 / R3a / K4C-r16, our player the bundle's serial twin in rh
mode); only the base game is played (no forced replays). At up to K pre-drawn roots per game (first decision >= the
drawn tick, within 200 ticks, with >= 2 scorable siblings) the siblings are the chosen action, WAIT and the best other
play; each sibling's leaf is the balanced native leaf (rollout_commands = rollout_e1's arguments, the state the vl term
reads). Continuations: bot.search.lopp.batch_rollouts from the leaf state with action WAIT (no forced play; our side
then plays scripted balanced), opponent Learned(k1a1, sample=True), horizon ticks.
Margin = (own - enemy crowns)/3 + (own - enemy tower HP)/15000 (leaf_value.margin_pv); a continuation that ends the game
scores +-1 (+ the HP term is not observed then).
Row per root: siblings [{action, score, phi, tick, pv, parts, m_leaf, mc_mean, mc_std, mc_n}], root tick/seat, own deck,
opponent, match seed. Engine: ours, every card L11 (planner and truth).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from multiprocessing import Process
from pathlib import Path

from bot.players.base import WAIT

PLAYER = os.environ.get('MC_PLAYER', 'K4L-R-gs-rw-mk1a1-rh')
OPP_MODEL = os.environ.get('MC_OPP_MODEL', 'k1a1')


def continuations(core, leaf_sim, seat, tick_leaf, n, horizon, seed, model):
    """Mean / std / n of the margin `horizon` ticks after the leaf over n learned-opponent continuations."""
    import numpy as np
    from bot.search.lopp import Learned, batch_rollouts
    from bot.fullpool.leaf_value import margin_pv
    native, cfg = core.native, core.config
    vals = []
    for j in range(n):
        got = []

        def capture(sim, s, t):
            got.append(margin_pv(json.loads(native.public_view(sim, s))['towers']))
            return 0.
        opp = Learned(model, True, None, 5, seed=[int(seed), int(tick_leaf), j], rowwise=True)
        v = batch_rollouts(native, leaf_sim, seat, [WAIT], opp, delay=core.command_delay, opp_delay=core.opponent_delay,
                           horizon=horizon, interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=tick_leaf,
                           leaf=capture)[0]
        vals.append(got[0] if got else (1. if v > 0 else -1.))
    return float(np.mean(vals)), float(np.std(vals)), len(vals)


class Probe:
    def __init__(self, rt, inner, picks, n, horizon, seed):
        self.rt, self.inner, self.picks = rt, inner, sorted(picks)
        self.n, self.horizon, self.seed = n, horizon, seed
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds
        self.roots = []

    def start(self, ctx):
        from bot.search.lopp import load_model
        from bot.fullpool.leaf_value import margin_pv
        self.inner.start(ctx)
        core = self.inner.p.core
        native, cfg = core.native, core.config
        orig, todo = core.score_candidates, list(self.picks)
        model = load_model(OPP_MODEL)

        def score(root, seat, cands, **kw):
            action = orig(root, seat, cands, **kw)
            tick = int(core.info.tick)
            while todo and tick > todo[0] + 200:
                todo.pop(0)
            if todo and tick >= todo[0]:
                work, sc = core.last['candidates'], core.last['scores']
                scored = {a: s for a, s in zip(work, sc) if s is not None}
                chosen = WAIT if int(action) in (2400, 2401, 2402) else int(action)
                sib = [chosen]
                if WAIT not in sib and WAIT in scored:
                    sib.append(WAIT)
                plays = sorted((a for a in scored if a < WAIT and a not in sib), key=lambda a: -scored[a])
                sib += plays[:1]
                if len(sib) < 2:
                    return action
                todo.pop(0)
                leaves = []
                for a in sib:
                    phi, _, sim = native.rollout_commands(root, seat, a, [], 'balanced', core.command_delay,
                                                          core.opponent_delay, 1, 1, cfg.horizon, cfg.interval,
                                                          cfg.interval, cfg.elixir_weight, True, False, False)
                    pv = [json.loads(native.public_view(sim, s)) for s in (0, 1)]
                    tl = tick + cfg.horizon
                    if abs(phi) >= 2.:
                        mean, std, k = (1. if phi > 0 else -1.), 0., 0
                    else:
                        mean, std, k = continuations(core, sim, seat, tl, self.n, self.horizon, self.seed, model)
                    leaves.append(dict(action=a, score=scored.get(a), phi=float(phi), tick=tl, pv=pv,
                                       parts=list(native.evaluation_parts(sim)), m_leaf=margin_pv(pv[seat]['towers']),
                                       mc_mean=mean, mc_std=std, mc_n=k))
                self.roots.append(dict(tick=tick, seat=seat, chosen=chosen, search_action=int(action), siblings=leaves,
                                       n_work=len(work)))
            return action
        core.score_candidates = score

    def act(self, view):
        return self.inner.act(view)

    def close(self):
        self.inner.close()


def worker(wid, idxs, out, base, k, n, horizon):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import select
    from bot.fullpool.models import install_from_env
    from bot.fullpool.sibling_gen import case, DECKS
    rt = Runtime()
    install_from_env(rt)
    select(rt, DECKS)
    path = out / f'mc-{wid:03d}.jsonl'
    for i in idxs:
        t0 = time.time()
        try:
            rng = random.Random(base + i + 7)
            picks = []
            while len(picks) < k:
                t = rng.randrange(300, 3300)
                if all(abs(t - p) >= 400 for p in picks):
                    picks.append(t)
            seat, opp, dk, own = case(rt, i, base)
            probe = Probe(rt, make_player(rt, PLAYER), picks, n, horizon, base + i)
            res = play_match(rt, {seat: probe, 1 - seat: make_player(rt, opp)}, seed=base + i, decks=dk)
            row = dict(index=i, base=base, seat=seat, opponent=opp, own_deck=own, player=PLAYER, opp_model=OPP_MODEL,
                       n=n, horizon=horizon, roots=probe.roots, winner=res['winner'], ticks=res['ticks'],
                       seconds=round(time.time() - t0, 1))
        except Exception:
            import traceback
            row = dict(index=i, base=base, error=traceback.format_exc()[-1500:])
        with open(path, 'a') as f:
            f.write(json.dumps(row) + '\n')


def main():
    from bot.exit.generate import check_bank
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--games', type=int, required=True)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--n', type=int, default=16)
    ap.add_argument('--horizon', type=int, default=600)
    a = ap.parse_args()
    check_bank(a.base, a.start, a.games)
    a.out.mkdir(parents=True, exist_ok=True)
    have = set()
    for p in a.out.glob('mc-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                if 'error' not in r:
                    have.add(r['index'])
            except ValueError:
                pass
    idxs = [i for i in range(a.start, a.start + a.games) if i not in have]
    procs = [Process(target=worker, args=(w, idxs[w::a.workers], a.out, a.base, a.k, a.n, a.horizon))
             for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    bad = [p.exitcode for p in procs if p.exitcode]
    if bad:
        raise SystemExit(f'{len(bad)} worker process(es) failed, exit codes {bad[:8]}')


if __name__ == '__main__':
    main()
