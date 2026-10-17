"""Positive gate: a full-pool game with a late reveal and injected unknown / alias / evolution card names.

    PYTHONPATH=. python reports/cards/belief-robust/smoke.py OUT.json [PLAYER] [PRIOR]
PLAYER (default LIVE-K4CW-r16, unbounded) is any bot.live.player.make_live_player name, e.g. the wall-clock
LIVE-K4L-R-gs-rw-fc-w200-t4-mk1a1 (bounded rebuild path). PRIOR: 'fullpool' (default, FullPoolBelief) or 'c56'
(the C56 rollback path: LivePlayer installs LiveBelief). Environment: the full-pool bundle env (BOT_BELIEF_PRIOR,
BOT_FULLPOOL_POLICIES, CLASHER_LOPP_MODELS, CLASHER_LIVE_FAST, PYTHONHASHSEED=0); run under cpu_job.sh.

The opponent fixture plays R3a, but holds LATE back until tick 2400, then deploys it at the first chance (a late reveal
after several rebuilds). Our player sees the opponent's plays renamed in its Information.events (the stream its belief
reads): Witch -> 'Gravedigger Queen' (no such card: an unknown slot), SkeletonDragons -> 'Skeleton Dragons' (display
alias), Knight -> 'Evo Knight' (evolution name). The sim keeps the true cards. Pass: terminal, 0 decision errors,
0 fast errors, 0 panics, search never disabled, no 'belief' preparation cutoff, the late card and the unknown slot in
every posterior state at every decision after their reveal.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from bot.players.base import Decision, WAIT
from bot.players.ours import play_match
from bot.players.runtime import Runtime
from bot.eval.headline import make_player
from bot.live.player import make_live_player
from bot.fullpool.banks import E16, select
from bot.fullpool.models import install_from_env

SEED = 1866440789737856          # the fullscope-belief smoke seed (trueids smoke bank; no evaluation claim)
OTHER = ['Pekka', 'Witch', 'SkeletonDragons', 'ElectroWizard', 'Arrows', 'Zap', 'Knight', 'Giant']
LATE, LATE_TICK = 'ElectroWizard', 2400
RENAME = {'Witch': 'Gravedigger Queen', 'SkeletonDragons': 'Skeleton Dragons', 'Knight': 'Evo Knight'}
UNKNOWN = '~gravediggerqueen'


class LateReveal:
    name = 'late-reveal-R3a'
    deadline_seconds = None

    def __init__(self, rt):
        self.rt, self.inner, self.played = rt, make_player(rt, 'R3a'), None

    def start(self, ctx):
        self.inner.start(ctx)

    def act(self, view):
        d = self.inner.act(view)
        hand = view.info.own['hand']
        if self.played is None and view.tick >= LATE_TICK and view.can_act and LATE in hand \
                and view.info.own['elixir'] >= self.rt.R.costs[LATE]:
            self.played = view.tick
            return Decision(hand.index(LATE) * 576 + 10 * 18 + 3)
        if d.action < WAIT and hand[d.action // 576] == LATE and self.played is None:
            return Decision(WAIT)
        return d

    def close(self):
        self.inner.close()


class Renamed:
    """Our player, seeing the opponent's card plays under other names (the stream the live translator feeds)."""

    def __init__(self, inner):
        self.inner, self.name = inner, inner.name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)

    def start(self, ctx):
        self.inner.start(ctx)

    def act(self, view):
        ev = tuple(replace(e, name=RENAME.get(e.name, e.name)) if e.kind == 'card' else e for e in view.info.events)
        return self.inner.act(replace(view, info=replace(view.info, events=ev)))

    def close(self):
        self.inner.close()

    def __getattr__(self, k):
        return getattr(self.inner, k)


def main(out, name='LIVE-K4CW-r16', prior='fullpool'):
    rt = Runtime()
    install_from_env(rt)
    select(rt, 'e16bl', 'c56' if prior == 'c56' else None)   # full-pool belief prior (as the live bundle) or C56
    strong = make_live_player(rt, name)
    opp = LateReveal(rt)
    checks = dict(late_seen_at=None, unknown_seen_at=None, late_missing=0, unknown_missing=0, checked=0)

    def observe(view, decision):
        if view.seat != 0 or not view.can_act:
            return
        b = strong.search.p.belief
        names = {e.name for e in b.events if e.kind == 'card'}
        if getattr(b, 'stale', False):
            return                           # previous posterior kept this decision (bounded rebuild pending)
        for key, card in (('late', LATE), ('unknown', UNKNOWN)):
            if card in names:
                checks[f'{key}_seen_at'] = checks[f'{key}_seen_at'] or view.tick
                checks[f'{key}_missing'] += int(not np.all(np.any(b.states == b.ids[card], axis=1)))
        checks['checked'] += 1

    result = play_match(rt, {0: Renamed(strong), 1: opp}, seed=SEED, decks=[list(E16), list(OTHER)], observer=observe)
    b = strong.search.p.belief
    ds = strong.decisions
    row = dict(player=name, prior=prior, result={k: result[k] for k in ('terminal', 'winner', 'ticks', 'command_sha256')},
               late_played_at=opp.played, belief_class=type(b).__name__, rebuilds=b.rebuilds,
               rebuild_slices=getattr(b, 'rebuild_slices', None), dropped=getattr(b, 'dropped', None),
               belief_names=sorted(n for n in b.names if n.startswith('~')),
               decisions=len(ds), sources={s: sum(d['source'] == s for d in ds) for s in {d['source'] for d in ds}},
               errors=[d for d in ds if d.get('error') or d.get('native_failures')][:5],
               belief_cutoffs=sum(d.get('preparation_cutoff') == 'belief' for d in ds),
               stale_decisions=sum(bool(d.get('belief_stale')) for d in ds),
               rebuild_walls_ms=[round(d['wall_ms'], 1) for i, d in enumerate(ds)
                                 if i and d['belief_rebuilds'] != ds[i - 1]['belief_rebuilds']],
               fast_errors=getattr(strong, 'fast_errors', 0), panics=strong.panics,
               search_disabled=strong.search_disabled, **checks)
    Path(out).write_text(json.dumps(row, indent=1, sort_keys=True) + '\n')
    ok = (result['terminal'] and not row['errors'] and not row['fast_errors'] and not row['panics']
          and not row['search_disabled'] and not row['belief_cutoffs'] and opp.played
          and checks['late_seen_at'] and checks['unknown_seen_at'] and not checks['late_missing']
          and not checks['unknown_missing'] and UNKNOWN in row['belief_names'])
    print(('BELIEF_ROBUST_SMOKE_PASS' if ok else 'BELIEF_ROBUST_SMOKE_FAIL'), json.dumps(row), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
