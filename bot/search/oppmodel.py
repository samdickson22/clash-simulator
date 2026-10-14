"""Opponent model inside K4C-r16's rollouts: how the 3 scripted rollout styles are aggregated (exploration).

K4C-r16 (bot/search/candidates.py) scores WAIT, the timed waits and the top-8 coarse plays by the MEAN of three
160-tick `rollout_e1` values, one per scripted opponent style (balanced, pressure, defense), via the frozen
`s1/anchor.anytime`. This module re-implements that reduction (single thread, no deadline, the only path K4C
uses) with a pluggable aggregation; everything else (candidates, rollouts, coarse balanced scan, top-8 refine,
timed-wait bonus, tie-breaks, S-default) is unchanged.

Aggregations ('K4O-' + tokens):
- mean            the frozen arithmetic ((b/3 + p/3) + d/3): K4O-mean == K4C-r16 bit for bit.
- min             pessimistic: min over the 3 styles.
- w<b>.<p>.<d>    fixed weights (percent, normalised), e.g. w50.25.25. Styles with weight 0 are not rolled out
                  (the coarse balanced rollout still runs for every play).
- lo<b>.<p>.<d>-hi<b>.<p>.<d>[-th<T>]
                  online blend (arm B, data-driven): r = shrunk running mean of the opponent's elixir at issue over
                  its public plays (3 pseudo-plays at T, default 6.0); lam = sigmoid((r - T)/0.5); weights =
                  (1-lam)*lo + lam*hi. lo/hi are the fit-bank-best fixed weights vs the low-elixir (R3a-like) and
                  high-elixir (v1-like) opponents.
- x<pct><b|p|d>[d<D>][i<I>]
                  extra rollout opponent (arm C): that style with opponent command delay D and/or decision interval I
                  ticks, via NativeScripts.rollout_commands, at weight pct/100 (the 3 styles share the rest).
- c<N>            R3a's top-N proposals (default 16 = K4C-r16).
Every player logs per-decision weights and, when all 3 styles were rolled out, whether the mean reduction would
have picked another action from the same rollouts ('changed'). Deterministic: no wall clock in any decision.
"""
from __future__ import annotations

import bisect
import math
import re

from bot.players.base import WAIT
from bot.search.candidates import CandidateSearchPlayer

STYLES = ('balanced', 'pressure', 'defense')
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}


def _bonus(action, score, elixir):
    ticks = TIMED_WAITS.get(action, 10 if action == WAIT else 0)
    if ticks and abs(score) < 2:
        return score + .01*math.sqrt(ticks/20)*max(0., 1-elixir/10)
    return score


def _argmax(work, scores):
    best = None
    for a in work:
        if a in scores and (best is None or scores[a] > scores[best]+1e-9):
            best = a
    return best


def parse_spec(spec):
    """'balanced' | 'pressure' | 'defense', optionally ':d<opp delay>' and/or ':i<opp interval>' (ticks)."""
    base, *mods = spec.split(':')
    if base not in STYLES:
        raise ValueError(spec)
    kw = {m[0]: int(m[1:]) for m in mods}
    if set(kw) - {'d', 'i'}:
        raise ValueError(spec)
    return base, kw.get('d'), kw.get('i')


def reduce_scores(core, root, seat, candidates, weights, *, coarse_order=(), refine_proposals=()):
    """anchor.anytime for threads=1, deadline=None, coarse_horizon == horizon, with weights in place of the mean.

    weights: None = frozen mean arithmetic; 'min' (over the 3 styles); or {spec: weight} (sum 1, see parse_spec).
    A spec with opponent delay/interval modifiers is rolled out with NativeScripts.rollout_commands (bit-identical
    to rollout_e1 at the default delay/interval); timed waits 2401/2402, which only rollout_e1 supports, get the
    base-style value plus that spec's WAIT residual. Returns (action, info).
    """
    original = list(candidates)
    if WAIT not in original or len(set(original)) != len(original):
        raise ValueError('unique candidates including WAIT required')
    plays = [a for a in original if a < WAIT]
    hinted = list(dict.fromkeys(a for a in coarse_order if a in plays))
    scan = hinted + [a for a in plays if a not in hinted]
    cfg = core.config
    horizon = cfg.horizon
    values = {}
    used = [0]

    def roll(a, spec):
        if (a, spec) in values:
            return values[a, spec]
        base, od, oi = parse_spec(spec)
        if spec == base:
            v = core.native.rollout_e1(root, seat, a, spec, core.command_delay, core.opponent_delay,
                                       horizon, cfg.interval, cfg.elixir_weight, 1e6)
        elif a in (2401, 2402):
            v = roll(a, base) + (roll(WAIT, spec) - roll(WAIT, base))
            values[a, spec] = v
            return v
        else:
            v = core.native.rollout_commands(root, seat, a, [], base, core.command_delay,
                od if od is not None else core.opponent_delay, 1, 1, horizon, cfg.interval,
                oi if oi is not None else cfg.interval, cfg.elixir_weight, True, False, False)[0]
        values[a, spec] = v
        used[0] += 1
        return v

    specs = STYLES if weights is None or weights == 'min' else tuple(k for k, w in weights.items() if w > 0)

    def score(a, coarse=None):
        if weights is None:   # frozen order: ((0. + b/3) + p/3) + d/3, b reused from the coarse scan for plays
            s = coarse/3 if coarse is not None else 0. + roll(a, STYLES[0])/3
            for style in STYLES[1:]:
                s += roll(a, style)/3
            return s
        vals = {}
        for spec in specs:
            vals[spec] = coarse if (spec == STYLES[0] and coarse is not None) else roll(a, spec)
        if weights == 'min':
            return min(vals[s] for s in STYLES)
        return sum(weights[k]*vals[k] for k in specs)

    scores, first = {}, {}
    scores[WAIT] = score(WAIT)
    if 2400 in original:
        scores[2400] = scores[WAIT]
    for a in original:
        if a >= WAIT and a not in (WAIT, 2400):
            scores[a] = score(a)
    for a in scan:
        first[a] = 0. + roll(a, STYLES[0])
    chosen = set(sorted(plays, key=lambda a: (-first[a], original.index(a)))[:8])
    chosen.update(a for a in refine_proposals if a in plays)
    work = [a for a in original if a >= WAIT or a in chosen]
    for a in work:
        if a < WAIT:
            scores[a] = score(a, coarse=first[a])
    elixir = float(core.info.packet.observation.global_features[5])*10
    for a in scores:
        scores[a] = _bonus(a, scores[a], elixir)
    best = _argmax(work, scores)
    info = dict(rollouts=used[0])
    if weights is not None and all((WAIT if a == 2400 else a, s) in values for a in work for s in STYLES):
        mean = {}
        for a in work:
            k = WAIT if a == 2400 else a
            mean[a] = _bonus(a, ((values[k, STYLES[0]]/3) + values[k, STYLES[1]]/3) + values[k, STYLES[2]]/3,
                             elixir)
        info['changed'] = int(_argmax(work, mean) != best)
    core.last = dict(candidates=work, scores=[scores.get(a) for a in work], traces=[])
    core.deadline_stats = dict(hit=False, fallback=best is None, completed=len(scores), candidates=len(work))
    return best, info


def play_features(event, opp_seat, elixir_before):
    y = float(event['y'])
    depth = y if opp_seat == 0 else 32. - y      # tiles from the opponent's own back line
    return [float(elixir_before), depth]


class OppModelPlayer(CandidateSearchPlayer):
    def __init__(self, rt, *, agg='mean', weights=None, r3a=16, lo=None, hi=None, th=6., name=None):
        super().__init__(rt, r3a=r3a, second=0, name=name)
        self.agg, self.fixed, self.lo, self.hi, self.th = agg, weights, lo, hi, float(th)

    def start(self, ctx):
        super().start(ctx)
        import sdefault
        core = self.p.core
        self.opp_seat = 1 - ctx.seat
        self.opp_plays = []
        self._seen, self._polls = set(), []        # (tick, opponent elixir) of every poll so far
        self.opp_delay = ctx.opponent_delay
        self._dec = {}

        def score_candidates(root, seat, candidates, *, trace=False, deadline=None, fallback=WAIT):
            weights = self.current_weights()
            action, info = reduce_scores(core, root, seat, candidates, weights,
                                         coarse_order=core.coarse_order, refine_proposals=core.refine_proposals)
            action = fallback if action is None else action
            core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
            action = sdefault.apply_default(core, action, fallback, candidates)
            core.deadline_stats['rollouts'] = info['rollouts']
            self._dec = dict(info, weights=None if weights in (None, 'min') else
                             [round(weights.get(k, 0.), 4) for k in STYLES + tuple(sorted(set(weights) - set(STYLES)))])
            return action
        core.score_candidates = score_candidates

    def current_weights(self):
        if self.agg == 'mean':
            return None
        if self.agg == 'min':
            return 'min'
        if self.agg == 'fixed':
            return self.fixed
        if self.agg == 'blend':
            e = [x[0] for x in self.opp_plays]
            r = (3*self.th + sum(e))/(3 + len(e))
            lam = 1/(1 + math.exp(-(r - self.th)/.5))
            return {k: (1-lam)*self.lo[k] + lam*self.hi[k] for k in STYLES}
        raise ValueError(self.agg)

    def _observe(self, view):
        for ev in view.public_events:
            if ev.get('kind') != 'card' or ev.get('seat') != self.opp_seat:
                continue
            key = (ev['tick'], ev['name'], ev['x'], ev['y'])
            if key in self._seen:
                continue
            self._seen.add(key)
            # Exact opponent elixir drops when the command is issued, opp_delay ticks before the public event:
            # use the last poll strictly before the issue tick.
            issue = ev['tick'] - self.opp_delay
            i = bisect.bisect_left(self._polls, (issue, -1.))
            if i > 0:
                self.opp_plays.append(play_features(ev, self.opp_seat, self._polls[i-1][1]))

    def act(self, view):
        self._observe(view)
        self._dec = {}
        decision = super().act(view)
        self._polls.append((view.tick, float(self.poller.opponent_elixir)))
        return decision

    def _done(self, action, stats, wall0, wait_ticks=0):
        stats = dict(stats, **self._dec)
        return super()._done(action, stats, wall0, wait_ticks)


def make_oppmodel_player(rt, name):
    """'K4O-' + tokens (see module docstring): mean | min | w<b>.<p>.<d> | lo…-hi…[-th<T>], optional c<N>,
    and x<pct><b|p|d>[d<delay>][i<interval>] (extra rollout opponent, e.g. x25bd47 = balanced with opponent
    delay 47 at weight 0.25; the 3 styles share the rest by their w-token weights, equal by default)."""
    kw, base, extra = dict(agg='mean'), None, {}
    for token in name.split('-')[1:]:
        if token in ('mean', 'min'):
            kw['agg'] = token
        elif m := re.fullmatch(r'w(\d+)\.(\d+)\.(\d+)', token):
            base = [int(v) for v in m.groups()]
        elif m := re.fullmatch(r'x(\d+)([bpd])(?:d(\d+))?(?:i(\d+))?', token):
            spec = dict(b='balanced', p='pressure', d='defense')[m[2]]
            spec += (f':d{m[3]}' if m[3] else '') + (f':i{m[4]}' if m[4] else '')
            if spec in STYLES or spec in extra:
                raise ValueError(name)
            extra[spec] = int(m[1])/100
        elif m := re.fullmatch(r'(lo|hi)(\d+)\.(\d+)\.(\d+)', token):
            kw.update(agg='blend')
            kw[m[1]] = dict(zip(STYLES, (int(v)/sum(int(u) for u in m.groups()[1:]) for v in m.groups()[1:])))
        elif m := re.fullmatch(r'th([\d.]+)', token):
            kw['th'] = float(m[1])
        elif m := re.fullmatch(r'c(\d+)', token):
            kw['r3a'] = int(m[1])
        else:
            raise ValueError(f'unknown opponent-model token {token!r} in {name!r}')
    if kw['agg'] == 'blend' and (kw.get('lo') is None or kw.get('hi') is None):
        raise ValueError(name)
    if base is not None or extra:
        if kw['agg'] != 'mean':
            raise ValueError(name)
        base = base or [1, 1, 1]
        rest = 1 - sum(extra.values())
        if rest < -1e-9 or (sum(base) == 0 and rest > 1e-9):
            raise ValueError(name)
        weights = {k: (rest*v/sum(base) if sum(base) else 0.) for k, v in zip(STYLES, base)}   # STYLES order first
        weights.update(extra)
        kw.update(agg='fixed', weights=weights)
    return OppModelPlayer(rt, name=name, **kw)
