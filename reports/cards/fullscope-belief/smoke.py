"""Runtime construction and full-game belief regression; run under cpu_job.sh 1 on 04/08.

PYTHONPATH=. python reports/cards/fullscope-belief/smoke.py OUT.json
Requires fullpool/run/env.sh.
The match uses our engine on live16402c; no RoyaleSim vocabulary changes.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'reports/bot/deckopt2/harness'))
import fullpool_eval as fp

from bot.players.base import Decision, MatchContext, WAIT
from bot.players.ours import play_match
from bot.eval.headline import make_player
from bot.live.player import WallCandidatePlayer
from bot.search.players import MultiSearchPlayer
from bot.fullpool.belief import planner_belief

REQUIRED = {'Pekka', 'Witch', 'SkeletonDragons', 'ElectroWizard'}
SEED = 1866440789737856  # existing trueids smoke bank; no evaluation/selection claim


class RevealThenR3a:
    """Deploy the four fixture cards once using own HUD only, then play the R3a policy."""
    name = 'reveal-four-then-R3a'
    deadline_seconds = None

    def __init__(self, rt):
        self.rt, self.inner = rt, make_player(rt, 'R3a')
        self.remaining = set(REQUIRED)

    def start(self, ctx):
        self.inner.start(ctx)

    def act(self, view):
        decision = self.inner.act(view)  # keep the policy's public event tracking current
        if not self.remaining:
            return decision
        if view.can_act:
            for slot, card in enumerate(view.info.own['hand']):
                if card in self.remaining and view.info.own['elixir'] >= self.rt.R.costs[card]:
                    self.remaining.remove(card)
                    return Decision(slot * 576 + 10 * 18 + 3)
        return Decision(WAIT)

    def close(self):
        self.inner.close()


def main(out):
    rt = fp.runtime(fp.BELIEF)
    assert rt.pins['card_scope'] == 'full'
    configs = []
    ctx = MatchContext(seat=0, seed=SEED, own_order=tuple(rt.x4s_decks()[0]),
                       command_delay=27, opponent_delay=27)
    # Exercise both PublicPlanner construction sites, independent of the facade.
    for cls in (WallCandidatePlayer, MultiSearchPlayer):
        p = cls(rt, wall_ms=None, threads=1) if cls is WallCandidatePlayer else cls(rt)
        p.start(ctx)
        assert type(p.p.belief).__name__ == 'FullPoolBelief'
        configs.append(dict(route=cls.__name__, belief=type(p.p.belief).__name__))
        p.close()
        del p
        gc.collect()

    c56 = fp.runtime('c56')
    # C56 identity contract and the harness's explicit legacy runtime selection.
    from belief import Belief
    prior, cls = planner_belief(c56, Belief)
    assert prior is c56.PRIOR and cls is Belief
    ps = fp.players(rt, fp.LIVE, 'LIVE-K4CW-r16', 0, strong_rt=c56)
    ps[1].start(MatchContext(seat=1, seed=SEED, own_order=ctx.own_order,
                             command_delay=27, opponent_delay=27))
    configs.append(ps[1].start_config)
    assert ps[1].start_config['runtime_belief'] == 'c56'
    ps[1].close()
    del ps
    gc.collect()
    # A caller can override the fast tier independently of the prior.
    ps = fp.players(rt, fp.LIVE, 'LIVE-K4CW-r16', 0, strong_rt=c56, strong_fast=fp.FAST)
    assert str(ps[1].rec.inner.fast.path) == fp.FAST.split(':', 1)[1].split('@')[0]
    del ps, c56
    gc.collect()

    ps = fp.players(rt, fp.LIVE, 'LIVE-K4CW-r16', 1)
    strong = ps[0].rec.inner  # use the actual LivePlayer with our engine, without RoyaleSim Recorder
    assert strong.rt.belief_prior == rt.belief_prior
    original_start = strong.start

    def start(context):
        original_start(context)
        assert type(strong.search.p.belief).__name__ == 'FullPoolBelief'
        assert str(strong.fast.path) == fp.FAST.split(':', 1)[1].split('@')[0]
    strong.start = start
    revealed, represented = set(), set()

    def observe(view, decision):
        if view.seat != 0:
            return
        revealed.update(e.name for e in view.info.events if e.kind == 'card')
        belief = strong.search.p.belief
        if REQUIRED <= revealed and not represented and REQUIRED <= {e.name for e in belief.events if e.kind == 'card'}:
            for card in REQUIRED:
                assert np.all(np.any(belief.states == belief.ids[card], axis=1)), card
            represented.update(REQUIRED)

    own = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
    other = ['Pekka', 'Witch', 'SkeletonDragons', 'ElectroWizard', 'Arrows', 'Zap', 'Knight', 'Giant']
    result = play_match(rt, {0: strong, 1: RevealThenR3a(rt)}, seed=SEED,
                        decks=[own, other], observer=observe, verbose=True)
    errors = [d for d in strong.decisions if d.get('error') or d.get('native_failures')]
    row = dict(result=result, required=sorted(REQUIRED), revealed=sorted(revealed),
               belief_contains=sorted(represented), belief_class=type(strong.search.p.belief).__name__,
               belief_rebuilds=strong.search.p.belief.rebuilds, errors=errors,
               fast_errors=getattr(strong, 'fast_errors', 0), panics=strong.panics,
               search_disabled=strong.search_disabled, runtime_pins=strong.rt.pins,
               fast=str(strong.fast.path), configurations=configs)
    Path(out).write_text(json.dumps(row, indent=2, sort_keys=True) + '\n')
    assert result['terminal'] and not errors and not row['fast_errors'] and not row['panics'], row
    assert not strong.search_disabled and represented == REQUIRED, row
    print('FULLSCOPE_BELIEF_PASS', result['command_sha256'], flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
