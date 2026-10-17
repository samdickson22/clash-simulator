"""Sibling-leaf data for the K4L leaf term: what search compares at one root, with realized 30 s outcomes (exploration).

    python -m bot.fullpool.sibling_gen --out DIR --games N --start S --base BASE --workers W [--k 3]

Why (BOT LEAD 2026-10-17): a state-value leaf fit across games swamped phi inside decisions (leaf_diag: term spread 1.5x
phi's, uncorrelated). The leaf has to separate SIBLING leaves of one root, so the data are sibling leaves + paired outcomes.

Case i (bank BASE): our seat i % 2; OUR deck rotates (deck-diversity rule): OWN_TRAIN[i % len] = s62, old e16 and the
deckopt2 Inferno pick (3 copies each) + the 91 LIVE Battle Log decks; the opponent deck is a full-pool training sampler
deck (salt opp); opponent OPPONENTS[i % 4] (K4C-r16 twice, R3a, v1; all clockless, so a replay with the same seed is
identical up to a forced action). Our player: $SIB_PLAYER (default K4L-R-gs-rw-mk1a1-rh, the bundle's serial twin in
receding-horizon mode). Engine: ours, every card L11.
1. Base game: K root ticks are pre-drawn (Random(BASE+i+7), in [300, 3300], >= 400 apart). At our first scored decision at
   or after each (within 200 ticks) that has >= 2 scorable siblings, record the work set and scores and pick up to 3 SIBLINGS: the chosen action, WAIT (if not chosen) and
   the best-scored other play. For each sibling, the balanced native leaf (rollout_commands with rollout_e1's arguments,
   the state the vl term reads): native public view of both seats, evaluation_parts, phi, leaf tick.
   Margin series of our seat at every decision: m = (own - enemy crowns)/3 + (own - enemy tower HP)/15000 (packet).
2. Each non-chosen sibling: replay case i, force that action at that root's decision, real players afterwards, stop
   at root + 600 ticks. replay_ok = the replay's search chose the base action at the root before the override.
Target per sibling: d30 = m(root + 600) - m(root) in its branch (game end inside the window: the end margin).
Row per root: root (tick, seat, own deck, opponent, scores), siblings [{action, score, leaf pv/parts/phi, d30}].
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from multiprocessing import Process
from pathlib import Path

from bot.players.base import Decision, WAIT

S62 = ('Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant')        # Sam's live deck from s62
INFERNO = ('Valkyrie', 'Archers', 'Goblins', 'InfernoTower', 'Fireball', 'Giant', 'MiniPekka', 'Skeletons')  # deckopt2 pick
OPPONENTS = ('K4C-r16', 'R3a', 'K4C-r16', 'v1')
PLAYER = os.environ.get('SIB_PLAYER', 'K4L-R-gs-rw-mk1a1-rh')
DECKS = os.environ.get('SIB_DECKS', 'fullpool:11433651:freq=b53b02a1fde4')
WINDOW = 600


def own_train():
    from bot.fullpool.banks import E16, battlelog_decks
    return [list(S62), list(E16), list(INFERNO)] * 3 + [list(d) for d in battlelog_decks()]


def margin_gf(gf):
    import numpy as np
    from bot.fullpool.value_net import margin
    m, _ = margin(np.asarray([gf], dtype=np.float64))
    return float(m[0])


class Probe:
    def __init__(self, rt, inner, picks=(), force=None):
        self.rt, self.inner, self.picks, self.force = rt, inner, sorted(picks), force
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds
        self.roots, self.series, self.replay_choice = [], [], None

    def start(self, ctx):
        self.inner.start(ctx)
        core = self.inner.p.core
        native, cfg = core.native, core.config
        orig, todo = core.score_candidates, list(self.picks)

        def score(root, seat, cands, **kw):
            action = orig(root, seat, cands, **kw)
            tick = int(core.info.tick)
            while todo and tick > todo[0] + 200:     # no decision with >= 2 siblings within 200 ticks: give up this pick
                todo.pop(0)
            if todo and tick >= todo[0] and self.force is None:
                work, sc = core.last['candidates'], core.last['scores']
                scored = {a: s for a, s in zip(work, sc) if s is not None}
                chosen = WAIT if int(action) in (2400, 2401, 2402) else int(action)   # rh emits timed waits as WAIT
                sib = [chosen]
                if WAIT not in sib and WAIT in scored:
                    sib.append(WAIT)
                plays = sorted((a for a in scored if a < WAIT and a not in sib), key=lambda a: -scored[a])
                sib += plays[:1]
                if len(sib) < 2:          # only WAIT scorable (e.g. nothing affordable): try the next decision
                    return action
                todo.pop(0)
                leaves = []
                for a in sib:
                    phi, _, sim = native.rollout_commands(root, seat, a, [], 'balanced', core.command_delay,
                                                          core.opponent_delay, 1, 1, cfg.horizon, cfg.interval,
                                                          cfg.interval, cfg.elixir_weight, True, False, False)
                    leaves.append(dict(action=a, score=scored.get(a), phi=float(phi), tick=tick + cfg.horizon,
                                       parts=list(native.evaluation_parts(sim)),
                                       pv=[json.loads(native.public_view(sim, s)) for s in (0, 1)]))
                self.roots.append(dict(tick=tick, seat=seat, chosen=chosen, search_action=int(action), siblings=leaves,
                                       n_work=len(work)))
            if self.force is not None and tick == self.force['tick'] and self.replay_choice is None:
                self.replay_choice = WAIT if int(action) in (2400, 2401, 2402) else int(action)
            return action
        core.score_candidates = score

    def act(self, view):
        d = self.inner.act(view)
        gf = list(view.info.packet.observation.global_features)
        self.series.append((int(view.tick), margin_gf(gf)))
        if self.force is not None and int(view.tick) == self.force['tick'] and view.can_act:
            return Decision(self.force['action'])
        return d

    def close(self):
        self.inner.close()


def case(rt, i, base):
    from bot.fullpool.banks import sampler
    seat = i % 2
    owns = own_train()
    own = list(owns[i % len(owns)])
    other = sampler(DECKS).deck(i, salt=f'opp|{base}')
    rng = random.Random(base + i)
    rng.shuffle(own); rng.shuffle(other)
    return seat, OPPONENTS[i % len(OPPONENTS)], ([own, other] if seat == 0 else [other, own]), sorted(owns[i % len(owns)])


def play(rt, i, base, picks=(), force=None, max_ticks=6001):
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    seat, opp, dk, own = case(rt, i, base)
    probe = Probe(rt, make_player(rt, PLAYER), picks, force)
    res = play_match(rt, {seat: probe, 1 - seat: make_player(rt, opp)}, seed=base + i, decks=dk, max_ticks=max_ticks)
    return probe, res, dict(seat=seat, opponent=opp, own_deck=own)


def at(series, tick, end_margin):
    pts = [m for t, m in series if t <= tick]
    if not series or series[-1][0] < tick:
        return end_margin
    return pts[-1] if pts else series[0][1]


def end_margin(res, seat):
    from bot.fullpool.leaf_value import margin_final
    return margin_final(dict(towers=res['towers']), seat)


def worker(wid, idxs, out, base, k):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.fullpool.banks import select
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)
    select(rt, DECKS)
    path = out / f'sib-{wid:03d}.jsonl'
    for i in idxs:
        t0 = time.time()
        try:
            rng = random.Random(base + i + 7)
            picks = []
            while len(picks) < k:
                t = rng.randrange(300, 3300)
                if all(abs(t - p) >= 400 for p in picks):
                    picks.append(t)
            probe, res, meta = play(rt, i, base, picks)
            seat = meta['seat']
            m_end = end_margin(res, seat)
            rows = []
            for r in probe.roots:
                m0 = at(probe.series, r['tick'], m_end)
                for s in r['siblings']:
                    if s['action'] == r['chosen']:
                        s.update(d30=at(probe.series, r['tick'] + WINDOW, m_end) - m0, branch='base')
                        continue
                    p2, res2, _ = play(rt, i, base, force=dict(tick=r['tick'], action=s['action']),
                                       max_ticks=r['tick'] + WINDOW + 1)
                    m_end2 = end_margin(res2, seat) if res2['terminal'] else p2.series[-1][1]
                    s.update(d30=at(p2.series, r['tick'] + WINDOW, m_end2) - at(p2.series, r['tick'], m_end2),
                             branch='replay', replay_ok=p2.replay_choice == r['chosen'], replay_terminal=res2['terminal'])
                rows.append(dict(r, index=i, base=base, player=PLAYER, m0=m0, **meta))
            row = dict(index=i, base=base, roots=rows, winner=res['winner'], ticks=res['ticks'],
                       command_sha256=res['command_sha256'], seconds=round(time.time() - t0, 1), **meta)
        except Exception:
            import traceback
            row = dict(index=i, base=base, error=traceback.format_exc()[-1500:])
        with open(path, 'a') as f:
            f.write(json.dumps(row) + '\n')


def done(out):
    keys = set()
    for p in out.glob('sib-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                if 'error' not in r:
                    keys.add(r['index'])
            except Exception:
                pass
    return keys


def main():
    from bot.exit.generate import check_bank
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--games', type=int, required=True)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--k', type=int, default=3)
    a = ap.parse_args()
    check_bank(a.base, a.start, a.games)
    a.out.mkdir(parents=True, exist_ok=True)
    have = done(a.out)
    idxs = [i for i in range(a.start, a.start + a.games) if i not in have]
    (a.out / f'launch-{a.start}.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                                                  player=PLAYER, decks=DECKS, jobs=len(idxs))))
    procs = [Process(target=worker, args=(w, idxs[w::a.workers], a.out, a.base, a.k)) for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    bad = [p.exitcode for p in procs if p.exitcode]   # a crashed worker must fail the job (wrappers log rc)
    if bad:
        raise SystemExit(f'{len(bad)} worker process(es) failed, exit codes {bad[:8]}')


if __name__ == '__main__':
    main()
