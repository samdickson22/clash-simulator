"""Timed-wait fix arms for the live player (bot lead live-diag, exploration tier).

'LD-K4L-R-gs-rw[-wcap10|-wcapE|-wint]': bot.live.player.LivePlayer (tier search, fast tier and cutoff default
$CLASHER_LIVE_FAST = rl5 v10 live) whose search tier is the deterministic serial twin K4L-R-gs-rw of the deployed
LIVE-K4L-R-gs-rw-fc-w200-t4-p4 (lopp_fast: rw makes every c/p split equal the serial values; fc/fp are
output-identical; the live search completed before its 200 ms cutoff on 7487/7488 logged decisions, so the deployed
player makes these moves). No clock is read: the arms are deterministic and pair exactly on a case.

Arms (search candidates are K4C's W-screen8 list: plays, WAIT, timed waits 2400/2401/2402 = 10/20/40 ticks, scored
with oppmodel._bonus's timed-wait bonus +.01*sqrt(ticks/20)*(1-elixir/10)):
  (none)   the live behaviour.
  -wcap10  2401 and 2402 removed from every candidate list (longest timed wait 10 ticks, as 2400 / plain WAIT).
  -wcapE   2401 and 2402 removed only while the packet shows an enemy troop/building on our half (y < 16).
  -wint    timed waits kept, but interruptible: the chosen wait is NOT handed to the harness (wait_ticks 0); the
           player itself skips decisions (stats None, WAIT) until the wait ends, unless (a) the number of enemy
           troops/buildings on our half exceeds its count at the wait's start, or (b) a new enemy card play event
           arrived; then it decides at the next search tick. Live mapping: LiveSession/LivePlayer would keep
           can_act True during a timed wait and run this check every poll (perception-derived packet + accepted
           enemy events), deciding only on 10-tick multiples as now.
  -gf      Giant/Fireball work-set guarantee: in K4L-R's reduction (lopp.reduce_learned), for each of Giant and
           Fireball with a legal (affordable) candidate, its best balanced-coarse candidate joins the refine set
           (top-8 + R3a refine proposals), so it gets a learned value; at most 2 extra learned keys. The reduction is
           lopp.reduce_learned's own source with that one insertion (asserted anchor), swapped in for this player's
           decisions only. (The deployed wall arm uses lopp_fast's reduction; the same insertion goes there.)
  -h<T>    rollout horizon T ticks (coarse and refine, native and learned) instead of 160.
  -ew<N>   rollout leaf elixir weight N/10 instead of 1.0 (C56SearchConfig.elixir_weight: leaf value
           += w * .08 * (own - enemy elixir)/16), i.e. banked elixir is worth N/10 times more at the horizon.
  -res     elixir reserve: after the timed-wait bonus, every play key a < WAIT made while NO enemy troop/building is on
           our half pays RES_LAMBDA * max(0, R - (elixir - cost(a))) / R, where R = the cheapest cost among our deck's
           ground-hitting troops/buildings (derived from R.config: can_ground, not a spell; 3 for the e16 deck) and
           elixir = the root's own elixir. Defensive plays (enemy on our half) and waits are unchanged. Same
           source-insertion mechanism as -gf (after the `_bonus` loop). -res<N>[p<K>]: lambda = N/1000 (default 15)
           and reserve R + K (e.g. -res30, -res15p1).
  -rh      receding horizon: timed waits stay in the search as planning macros (their scores and bonus unchanged), but
           the player EMITS a plain no-op (wait_ticks 0), so it re-decides at the next search poll (10 ticks). Live
           mapping: LivePlayer would return Decision(WAIT, 0) instead of a timed wait; nothing else changes.
Suffixes combine, e.g. LD-K4L-R-gs-rw-wint-gf, LD-K4L-R-gs-rw-res-rh.
"""
from __future__ import annotations

from bot.players.base import Decision, SEARCH_INTERVAL, WAIT

LONG_WAITS = (2401, 2402)


def _is_tower(rt, packet, i):
    names = rt.R.builder.token_names
    tok = int(packet.observation.entity_ids[i])
    return 0 <= tok < len(names) and names[tok] in ('Tower', 'KingTower')


def enemy_count(rt, packet):
    obs = packet.observation
    n = 0
    for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
        f = obs.entity_features[i]
        if f[3] > .5 and (f[4] > .5 or f[5] > .5) and f[1] * 32 < 16 and not _is_tower(rt, packet, i):
            n += 1
    return n


GUARANTEE = ('Giant', 'Fireball')
ANCHOR = "        chosen.update(a for a in refine_proposals if a in plays)\n"
INSERT = '''        _names = core.hand_names()
        for _card in GUARANTEE:
            _c = [a for a in plays if _names[a // 576] == _card]
            if _c:
                chosen.add(max(_c, key=lambda a: (first[a], -original.index(a))))
'''
RES_ANCHOR = "        scores[a] = _bonus(a, scores[a], elixir)\n"
RES_INSERT = '''    _pen = getattr(core, 'reserve_penalty', None)
    if _pen is not None:
        for a in scores:
            scores[a] -= _pen(a, elixir)
'''
RES_LAMBDA = 0.015
_COMPILED = {}


def reduce_learned_mod(gf=False, res=False):
    """lopp.reduce_learned with the -gf and/or -res insertions (compiled once per combination from its source;
    each anchor must occur exactly once)."""
    key = (bool(gf), bool(res))
    if key not in _COMPILED:
        import inspect
        import bot.search.lopp as lopp
        src = inspect.getsource(lopp.reduce_learned)
        for on, anchor, insert in ((gf, ANCHOR, INSERT), (res, RES_ANCHOR, RES_INSERT)):
            if not on:
                continue
            if src.count(anchor) != 1:
                raise RuntimeError(f'reduce_learned anchor {anchor.strip()!r} not found: re-port the arm')
            src = src.replace(anchor, anchor + insert)
        ns = dict(vars(lopp), GUARANTEE=GUARANTEE)
        exec(compile(src, lopp.__file__, 'exec'), ns)
        _COMPILED[key] = ns['reduce_learned']
    return _COMPILED[key]


def ground_reserve(R, deck):
    """Cheapest cost among the deck's ground-hitting troops/buildings (R.config card data)."""
    costs = []
    for card in deck:
        e = R.config['cards'].get(card) or {}
        units = e.get('units') or []
        st = units[0][0].get('stats', {}) if units and units[0] else {}
        if st.get('can_ground') and units[0][0].get('class') in ('Troop', 'Building'):
            costs.append(float(e['cost']))
    return min(costs) if costs else 3.


class TwinSearch:
    """Deterministic K4L search with LivePlayer's search-tier call signature (default/wall0 unused: no deadline,
    so the S-default rule never fires), plus the candidate filter of the cap arms."""

    def __init__(self, rt, inner, cap=None, gf=False, horizon=None, elixir_weight=None, res=None):
        self.rt, self.inner, self.cap, self.gf, self.elixir_weight = rt, inner, cap, gf, elixir_weight
        self.res = res
        if horizon is not None:
            inner.horizon = inner.coarse_horizon = int(horizon)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    @property
    def name(self):
        return self.inner.name

    def start(self, ctx):
        self.inner.start(ctx)
        core = self.inner.p.core
        if self.elixir_weight is not None:
            import dataclasses
            core.config = dataclasses.replace(core.config, elixir_weight=float(self.elixir_weight))
        builder = self.rt.R.builder
        core.hand_names = lambda: [builder.card_name_for_token_id(int(t)) if int(t) > 0 else None
                                   for t in list(core.info.packet.observation.hand_ids)[:4]]
        if self.res:
            R, rt = self.rt.R, self.rt
            lam, extra = self.res
            reserve = ground_reserve(R, ctx.own_order) + extra
            costs = R.costs

            def reserve_penalty(a, elixir):
                if a >= WAIT or enemy_count(rt, core.info.packet) > 0:
                    return 0.
                card = core.hand_names()[a // 576]
                cost = float(costs[card]) if card in costs else 0.
                return lam * max(0., reserve - (elixir - cost)) / reserve
            core.reserve_penalty = reserve_penalty
        if self.gf or self.res:
            import bot.search.lopp as lopp
            gf, orig_sc = reduce_learned_mod(self.gf, bool(self.res)), core.score_candidates

            def score_candidates(root, seat, cands, **kw):
                saved, lopp.reduce_learned = lopp.reduce_learned, gf
                try:
                    return orig_sc(root, seat, cands, **kw)
                finally:
                    lopp.reduce_learned = saved
            core.score_candidates = score_candidates
        if self.cap is None:
            return
        orig = core.candidates

        def candidates(packet, policy_proposals=()):
            out, mask = orig(packet, policy_proposals)
            if self.cap == 'all' or enemy_count(self.rt, packet) > 0:
                out = [a for a in out if a not in LONG_WAITS]
            return out, mask
        core.candidates = candidates

    def act(self, view, *, wall0=None, default=None):
        return self.inner.act(view)

    def close(self):
        self.inner.close()


class Interruptible:
    """LivePlayer facade wrapper for -wint (see module docstring)."""

    def __init__(self, rt, live):
        self.rt, self.live = rt, live
        self.name = live.name
        self.deadline_seconds = live.deadline_seconds
        self.interrupts = 0

    def __getattr__(self, name):
        return getattr(self.live, name)

    def start(self, ctx):
        self.live.start(ctx)
        self.until, self.n0, self.ev0, self.seat = None, 0, 0, ctx.seat

    def _enemy_events(self, view):
        return sum(1 for e in view.public_events if e.get('seat') != self.seat and e.get('kind') == 'card')

    def act(self, view):
        if self.until is not None and view.tick < self.until:
            grew = enemy_count(self.rt, view.info.packet) > self.n0 or self._enemy_events(view) > self.ev0
            if not grew:
                return self._blocked(view)
            self.until = None
            self.interrupts += 1
            if view.tick % SEARCH_INTERVAL:       # decide at the next search tick
                return self._blocked(view)
        elif self.until is not None:
            self.until = None
        d = self.live.act(view)
        if d.wait_ticks and view.can_act:
            self.until = view.tick + d.wait_ticks
            self.n0, self.ev0 = enemy_count(self.rt, view.info.packet), self._enemy_events(view)
            if d.stats is not None:
                d.stats = dict(d.stats, timed_wait=d.wait_ticks, interrupts=self.interrupts)
            d = Decision(d.action, 0, d.stats)
        return d

    def _blocked(self, view):
        """Exactly what the harness does during a real timed wait: the player is polled with can_act False (both
        tiers keep their 5-tick tracking) and nothing is submitted."""
        from dataclasses import replace
        self.live.act(replace(view, can_act=False))
        return Decision(WAIT, 0, None)

    def close(self):
        self.live.close()


class RecedingHorizon:
    """LivePlayer facade wrapper for -rh: drop the timed-wait length from every decision (recorded in stats)."""

    def __init__(self, live):
        self.live, self.name, self.deadline_seconds = live, live.name, live.deadline_seconds

    def __getattr__(self, name):
        return getattr(self.live, name)

    def start(self, ctx):
        self.live.start(ctx)

    def act(self, view):
        d = self.live.act(view)
        if d.wait_ticks:
            stats = dict(d.stats, timed_wait=d.wait_ticks) if d.stats is not None else None
            d = Decision(d.action, 0, stats)
        return d

    def close(self):
        self.live.close()


def make_variant(rt, name):
    from bot.live.player import LivePlayer, FAST_DEFAULT
    from bot.eval.headline import make_player
    if not name.startswith('LD-'):
        raise ValueError(name)
    import re
    parts = name[3:].split('-')
    arms = []
    while parts and (parts[-1] in ('wcap10', 'wcapE', 'wint', 'gf', 'rh') or re.fullmatch(r'(h|ew)\d+|res(\d+)?(p\d)?', parts[-1])):
        arms.insert(0, parts.pop())
    body = '-'.join(parts)
    if body != 'K4L-R-gs-rw':
        raise ValueError(f'{name}: LD- arms are defined on the live twin K4L-R-gs-rw')
    if 'wcap10' in arms and 'wcapE' in arms:
        raise ValueError(name)
    cap = 'all' if 'wcap10' in arms else ('enemy' if 'wcapE' in arms else None)
    horizon = next((int(a[1:]) for a in arms if a.startswith('h')), None)
    ew = next((int(a[2:]) / 10 for a in arms if a.startswith('ew')), None)
    res = None
    for a in arms:
        m = re.fullmatch(r'res(\d+)?(?:p(\d))?', a)
        if m:
            res = ((int(m[1]) if m[1] else int(RES_LAMBDA * 1000)) / 1000, int(m[2] or 0))
    live = LivePlayer(rt, tier='search', fast_spec=FAST_DEFAULT, cutoff_default='it5s2', name=name)
    live.search = TwinSearch(rt, make_player(rt, body), cap=cap, gf='gf' in arms, horizon=horizon,
                             elixir_weight=ew, res=res)
    live.deadline_seconds = None
    if 'wint' in arms and 'rh' in arms:
        raise ValueError(f'{name}: wint and rh are alternatives')
    if 'rh' in arms:
        return RecedingHorizon(live)
    return Interruptible(rt, live) if 'wint' in arms else live
