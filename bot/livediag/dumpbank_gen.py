"""Option-2 data: paired "dump vs bank" continuations from live-like roots (bot lead live-diag, exploration tier).

Case i (bank BASE): sim_diag's case (our seat i%2, the live e16 deck vs giant_decks()[(i//2)%5], Random(BASE+i) shuffles),
opponent OPPONENTS[i % 3], our player the deterministic live twin LD-K4L-R-gs-rw (every player in the match is seeded
by the match seed, so a replay is identical up to a forced action; checked by the base game's command hash).

1. Base game (branch FREE): at every search decision of ours that is ELIGIBLE (can act, no enemy troop/building on
   our half, the search's scored work set holds >= 1 play and WAIT), log the root: tick, global features (elixir,
   tower fractions, time), hand, enemy elixir estimate, the chosen action, the best-scored play and WAIT scores.
2. Pick K roots per game (Random(BASE+i+7), uniform over eligible decisions at least 200 ticks apart).
3. For each picked root, replay the game (branch RESERVE): identical up to the root; from the root for WINDOW = 200
   ticks (10 s), whenever our search picks a NON-DEFENSIVE play (no enemy troop/building on our half) that would
   leave elixir < R (R = bot.livediag.variants.ground_reserve of our deck, 3 for e16), WAIT is played instead
   (overrides counted); outside the window the real player is unconstrained. The opponent is the real player.
Row per root: both branches' outcomes (score for our seat: win 1, draw .5, loss 0; crowns; tower HP), the root
features and scores: delta_outcome = FREE - RESERVE is the action-conditioned target of a learned reserve term
(> 0: dumping was right). Replays are checked: the search's choice at the root in RESERVE equals FREE's.
Training roots only: the A/B uses a different fresh bank.

    python -m bot.livediag.dumpbank_gen --out DIR --games N --start S --base BASE --workers W [--k 2]
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

OPPONENTS = ('R3a', 'v1', 'rext-bc', 'LIVE-K4CW-r16')   # + strong K4C-r16 (live belief; bot lead 19:2xZ); cases written
# before the change used i % 3 over the first three, and every row records its opponent
PLAYER = os.environ.get('LD_DB_PLAYER', 'LD-K4L-R-gs-rw')   # db2 (Sam 2026-10-16: holding back must be learned in rh mode): LD-K4L-R-gs-rw-rh


WINDOW = 200


class Probe:
    """Wraps our player: logs eligible roots (force None) or applies the reserve window from force['tick']."""

    def __init__(self, rt, inner, force=None):
        self.rt, self.inner, self.force = rt, inner, force
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds
        self.roots, self.forced = [], None

    def start(self, ctx):
        from bot.livediag.variants import ground_reserve
        self.inner.start(ctx)
        self.seat = ctx.seat
        self.reserve = ground_reserve(self.rt.R, ctx.own_order)

    def close(self):
        self.inner.close()

    def act(self, view):
        from bot.livediag.variants import enemy_count
        d = self.inner.act(view)
        if d.stats is None or not view.can_act or d.stats.get('source') != 'search':
            return d
        search = self.inner.search
        core = search.inner.p.core
        last = core.last or {}
        scores = {int(a): s for a, s in zip(last.get('candidates') or [], last.get('scores') or []) if s is not None}
        plays = {a: s for a, s in scores.items() if a < WAIT}
        if self.force is not None:
            t0 = self.force['tick']
            if view.tick == t0:
                self.forced = dict(tick=t0, root_action=int(d.action), overrides=0, override_ticks=[])
            if self.forced is not None and t0 <= view.tick < t0 + WINDOW and d.action < WAIT \
                    and enemy_count(self.rt, view.info.packet) == 0:
                obs = view.info.packet.observation
                card = self.rt.R.builder.card_name_for_token_id(int(list(obs.hand_ids)[d.action // 576]))
                elixir = float(obs.global_features[5]) * 10
                if elixir - float(self.rt.R.costs.get(card, 0)) < self.reserve:
                    self.forced['overrides'] += 1
                    self.forced['override_ticks'].append(view.tick)
                    return Decision(WAIT, 0, d.stats)
            return d
        if self.force is None and plays and WAIT in scores and enemy_count(self.rt, view.info.packet) == 0:
            obs = view.info.packet.observation
            b = self.rt.R.builder
            hand = [b.card_name_for_token_id(int(t)) if int(t) > 0 else None for t in list(obs.hand_ids)[:4]]
            dump = max(plays, key=lambda a: plays[a])
            self.roots.append(dict(tick=view.tick, action=int(d.action), wait_ticks=d.wait_ticks,
                                   chosen_play=bool(d.action < WAIT), dump=dump, dump_card=hand[dump // 576],
                                   dump_score=plays[dump], wait_score=scores[WAIT],
                                   timed_wait_score=max((scores[k] for k in (2400, 2401, 2402) if k in scores),
                                                        default=None),
                                   hand=hand, gf=[round(float(x), 5) for x in obs.global_features],
                                   opp_elixir=getattr(search.inner.poller, 'opponent_elixir', None),
                                   n_enemy_units=int(sum(1 for i in obs.entity_mask.nonzero()[0]
                                                         if obs.entity_features[int(i)][3] > .5))))
        return d


def case(rt, decks, i, base):
    from bot.livediag.sim_diag import LIVE_DECK
    seat = i % 2
    own, other = list(LIVE_DECK), list(decks[(i // 2) % len(decks)])
    rng = random.Random(base + i)
    rng.shuffle(own); rng.shuffle(other)
    return seat, OPPONENTS[i % len(OPPONENTS)], ([own, other] if seat == 0 else [other, own])


def play(rt, vocab, i, base, decks, force=None):
    from bot.players.royalesim_match import play_match
    from bot.live.player import make_live_player
    from bot.livediag.variants import make_variant
    seat, opp, dk = case(rt, decks, i, base)
    probe = Probe(rt, make_variant(rt, PLAYER), force)
    opponent = make_variant(rt, opp) if opp.startswith('LD-') else make_live_player(rt, opp)
    res = play_match(rt, {seat: probe, 1 - seat: opponent}, seed=base + i, decks=dk, vocab=vocab)
    score = 1. if res['winner'] == seat else (0.5 if res['winner'] is None else 0.)
    return probe, dict(score=score, crowns=res['crowns'], towers=res['towers'], ticks=res['ticks'],
                       command_sha256=res['command_sha256'], seat=seat, opponent=opp)


def worker(wid, idxs, out, base, k):
    from bot.players.runtime import Runtime
    from bot.players.royalesim_vocab import load
    from bot.livediag.sim_diag import giant_decks
    rt = Runtime()
    vocab, decks = load(rt), giant_decks(rt)
    path = out / f'roots-{wid}.jsonl'
    for i in idxs:
        t0 = time.time()
        try:
            probe, res = play(rt, vocab, i, base, decks)
            rng = random.Random(base + i + 7)
            pool = list(probe.roots)
            rng.shuffle(pool)
            picked = []
            for r in pool:
                if all(abs(r['tick'] - p['tick']) >= 200 for p in picked):
                    picked.append(r)
                if len(picked) >= k:
                    break
            rows = []
            for r in sorted(picked, key=lambda r: r['tick']):
                p2, res2 = play(rt, vocab, i, base, decks, dict(tick=r['tick']))
                f = p2.forced or {}
                rows.append(dict(index=i, base=base, root=r, reserve_branch=f, opponent=res['opponent'],
                                 seat=res['seat'], free=res, reserve=res2,
                                 replay_ok=f.get('root_action') == r['action'],
                                 delta_outcome=res['score'] - res2['score'],
                                 delta_score=r['dump_score'] - max(r['wait_score'], r['timed_wait_score'] or -9)))
            row = dict(index=i, base=base, player=PLAYER, eligible=len(probe.roots), roots=rows, base_game=res,
                       seconds=round(time.time() - t0, 1))
        except Exception:
            import traceback
            row = dict(index=i, base=base, error=traceback.format_exc()[-1500:])
        with open(path, 'a') as f:
            f.write(json.dumps(row) + '\n')


def done(out):
    keys = set()
    for p in out.glob('roots-*.jsonl'):
        for l in p.read_text().splitlines():
            try:
                r = json.loads(l)
                if 'error' not in r:
                    keys.add(r['index'])
            except Exception:
                pass
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--games', type=int, required=True)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--k', type=int, default=2)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    have = done(a.out)
    idxs = [i for i in range(a.start, a.start + a.games) if i not in have]
    (a.out / f'launch-{a.start}.json').write_text(json.dumps(dict(vars(a), out=str(a.out), todo=len(idxs),
        started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), fast=os.environ.get('CLASHER_LIVE_FAST'))) + '\n')
    procs = [Process(target=worker, args=(w, idxs[w::a.workers], a.out, a.base, a.k)) for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
