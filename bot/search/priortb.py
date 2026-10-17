"""Prior tie-break for K4L-R (token `pt<N>`, lambda = N/1000; PT1, cycle-model owner; exploration tier).

Every root key a scored by the search (plays, WAIT, timed waits) gets
    score(a) += LAMBDA * log max(pi(a), FLOOR)
from the learned prior the live stack already runs at every poll: the LivePlayer's fast tier (the f1a2 student,
bot/exit/student.py, an R3-architecture SetPolicy). With P = its gate P(play) and r = its joint card+tile log-probs,
    pi(play a) = P * softmax_{legal plays}(r)[a],    pi(WAIT) = pi(timed waits) = 1 - P,
over the fast tier's own action mask (a play outside it gets FLOOR). The prior is the forward the fast tier makes on
the same poll's packet: its CachedPolicy.sample inputs (model packet, D1 state) are kept per poll, and the forward is
recomputed lazily only at root decisions (so the fast tier's own decisions are untouched). If the fast tier did not
poll at the decision's tick, the term is 0 for every key (counted as `missing`).

The term composes into core.reserve (read by reserve.apply in lopp.reduce_learned / lopp_fast.reduce_fast, which
subtracts it from every scored key), on top of `res` / `sh` when installed. Waits get the prior too, so the term is
a tie-break between acting and holding as well as among plays, with no per-card or per-class rule.
Wiring: lopp_fast.make_live_lopp gives the search tier its LivePlayer (search._live); install() runs at the search
tier's start, after LivePlayer.start has started the fast tier. Without the token nothing here runs.

Counts per match (core.prior_counts): decisions, missing, top3_scored (the prior's top-3 plays include a play in the
scored set), top1_scored, and the sum of |term| spread; written as one JSON line per match to $BOT_PRIORTB_LOG/<pid>.jsonl
when that directory is set (analysis only).
"""
from __future__ import annotations

import json
import math
import os

WAIT = 2304
FLOOR = 1e-4


class FastPrior:
    """Per-poll prior from a started StudentPlayer (LivePlayer.fast)."""

    def __init__(self, fast):
        self.fast = fast
        self.tick = None
        self.pending = None          # (tick, model packet, d1) of the latest fast poll
        self.cache = None            # (tick, {action: log pi}, log pi wait)
        cached, poller = fast.cached, fast.poller
        sample, poll = cached.sample, poller.poll

        def poll_hook(tick, packet, public_events):
            self.tick = int(tick)
            return poll(tick, packet, public_events)

        def sample_hook(packet, d1, generator=None):
            self.pending = (self.tick, packet, d1)
            return sample(packet, d1, generator)
        poller.poll = poll_hook
        cached.sample = sample_hook

    def logpi(self, tick):
        """({play action: log pi}, log pi(wait)) for the poll at `tick`, or None."""
        if self.cache is not None and self.cache[0] == tick:
            return self.cache[1:]
        if self.pending is None or self.pending[0] != tick:
            return None
        import numpy as np
        import torch
        from imitation.model.inference import single_features
        from proposals import outputs
        _, packet, d1 = self.pending
        cached = self.fast.cached
        with torch.inference_mode():
            prob, ranks = outputs(cached.model, single_features(packet, d1, cached.costs))
        p = min(max(float(prob[0]), 0.), 1.)
        r = ranks[0].double().numpy()
        legal = np.flatnonzero(np.asarray(packet['action_mask'])[:WAIT])
        out = {}
        if len(legal):
            x = r[legal]
            x = x - x.max()
            lse = math.log(float(np.exp(x).sum()))
            lp = math.log(max(p, 1e-300))
            out = {int(a): lp + float(v) - lse for a, v in zip(legal, x)}
        self.cache = (tick, out, math.log(max(1. - p, 1e-300)))
        return self.cache[1:]


def install(rt, core, lam, live):
    """core.reserve <- (previous penalty, if any) - lam * log pi(a). Idempotent per (core, lam)."""
    prev = getattr(core, 'reserve', None)
    if prev is not None and getattr(prev, '_priortb', None) == lam:
        return
    fast = getattr(live, 'fast', None)
    if fast is None or not hasattr(fast, 'cached'):
        raise ValueError('pt<N> needs the LivePlayer fast tier (a started StudentPlayer)')
    prior = getattr(fast, '_priortb', None)
    if prior is None or prior.fast is not fast or getattr(prior, 'cached_id', None) != id(fast.cached):
        prior = FastPrior(fast)
        prior.cached_id = id(fast.cached)
        fast._priortb = prior
    floor = math.log(FLOOR)
    counts = dict(decisions=0, missing=0, top3_scored=0, top1_scored=0, spread=0.)
    state = dict(tick=None, seen=set(), top=None, lo=0., hi=0.)

    def close_tick():
        if state['tick'] is None or state['top'] is None:
            return
        top = state['top']
        counts['top3_scored'] += any(a in state['seen'] for a in top[:3])
        counts['top1_scored'] += bool(top) and top[0] in state['seen']
        counts['spread'] += state['hi'] - state['lo']

    def penalty(a, elixir):
        p = prev(a, elixir) if prev is not None else 0.
        tick = int(core.info.tick)
        if tick != state['tick']:
            close_tick()
            state.update(tick=tick, seen=set(), top=None, lo=math.inf, hi=-math.inf)
            got = prior.logpi(tick)
            counts['decisions'] += 1
            if got is None:
                counts['missing'] += 1
                state['lp'] = None
            else:
                plays, wait = got
                state['lp'] = got
                state['top'] = sorted(plays, key=lambda k: (-plays[k], k))[:3]
        got = state['lp']
        if got is None:
            return p
        plays, wait = got
        lp = wait if a >= WAIT else plays.get(int(a), floor)
        term = lam * max(lp, floor)
        state['seen'].add(int(a))
        state['lo'], state['hi'] = min(state['lo'], term), max(state['hi'], term)
        return p - term
    penalty._priortb = lam
    core.reserve = penalty
    core.prior_counts = counts
    core.prior_close = close_tick
    if not getattr(live, '_priortb_close', False):    # one count line per match, from the core's latest counts
        close = live.close

        def close_hook():
            write_counts(core, getattr(live, 'name', None))
            return close()
        live.close = close_hook
        live._priortb_close = True


def write_counts(core, name=None):
    d = os.environ.get('BOT_PRIORTB_LOG')
    counts = getattr(core, 'prior_counts', None)
    if not d or counts is None:
        return
    getattr(core, 'prior_close', lambda: None)()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f'{os.getpid()}.jsonl'), 'a') as f:
        f.write(json.dumps(dict(counts, name=name)) + '\n')
