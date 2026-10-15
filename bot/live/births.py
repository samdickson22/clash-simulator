"""Card-level perception -> bodies, tracks and derived plays; HUD clock -> tick (LIVE track, exploration).

Perception (live/perception/common.py:frame_record, schema clasher.live.perception-frame.v1) reports each unit as the
CARD that spawned it (C56 names; towers separately) and emits NO play events. This module supplies what the bot needs
from that:

CardBodies   card -> our body tokens, from the frozen engine config (the card's units, its production children and
             its death children; token/kind exactly as the v5 builder writes them, Resources.meta['bodies']).
UnitTracker  frame-to-frame tracks per (card, owner) (nearest within a radius that grows with the gap; tracks survive
             missed detections for `ttl` ticks; expired tracks are remembered for `memory` ticks so a re-detection is
             not a birth). Each new track picks its body:
               - a live spawner building of that card/owner exists -> its production child (GoblinHut, FirespiritHut);
               - a main body of that card/owner vanished nearby recently -> its death child (Golem -> Golemite);
               - else a main body; multi-body cards (GoblinGang, Rascals, Goblinstein) fill their composition.
             A main-body birth that starts a new cluster (no other birth of that card/owner within `cluster_tiles`
             and `cluster_ticks`) is a PLAY at the birth position and first-sighting tick, if plausible: the
             opponent may deploy only on its side (y >= 15) unless the card deploys anywhere (Miner, GoblinBarrel) or
             the facing own princess tower is down (then y >= 9).
ClockTracker HUD clock (s) + elixir phase (1/2/3) + timestamp -> match tick (20/s), monotonic. Regulation shows
             180..0 (tick = (180-clock)*20 + 1..20), overtime 120..0 (tick = (300-clock)*20 + 1..20)
             (collector.py:379); phase 2 with clock > 60 or phase 3 means overtime. Within the 20-tick second the
             timestamp interpolates.
Known gaps (documented in RESULTS): spells are never seen, so the opponent's spell plays (and their elixir/cycle
effect) are missing; a play whose units are never detected is missed; units re-detected after `memory` ticks look
like a new play. The translator's stream guard (D1/OwnCycle mirrors) drops plays the trackers would reject.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math

KINDS = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
DEPLOY_ANYWHERE = {'Miner', 'GoblinBarrel', 'MightyMiner'}


class CardBodies:
    def __init__(self, rt):
        R = rt.R
        cfg = R.config
        self.costs = R.costs

        def token(template):
            stat = template['stats']['name']
            kind = template['class'] if template['class'] in ('Troop', 'Building') else None
            if kind is None:
                return None
            meta = R.meta['bodies'].get(stat)
            tok = meta['token'] if meta else 0
            if not tok or (tok, kind) not in R.templates:
                tok = next((t for (t, k), v in R.templates.items() if k == kind and v['stats']['name'] == stat), 0)
            return (int(tok), KINDS.index(kind)) if tok else None

        self.main, self.children, self.death = {}, {}, {}
        for card, c in cfg['cards'].items():
            comp = Counter()
            stats = []
            for grp in c.get('units', ()):
                for t in (grp if isinstance(grp, list) else [grp]):
                    b = token(t)
                    if b:
                        comp[b] += 1
                        stats.append(t['stats']['name'])
            self.main[card] = list(comp.items())
            kids = []
            for s in dict.fromkeys(stats):
                p = cfg['production_children'].get(s)
                for t in (p if isinstance(p, list) else [p] if p else []):
                    b = token(t)
                    if b and b not in kids:
                        kids.append(b)
            self.children[card] = kids
            dead = []
            for s in dict.fromkeys(stats):
                for t in cfg['death_children'].get(s) or ():
                    b = token(t)
                    if b and b not in dead:
                        dead.append(b)
            self.death[card] = dead

    def is_card(self, name):
        return name in self.main

    def spawner(self, card):
        return any(k == 1 for (_, k), _ in self.main.get(card, ())) and bool(self.children.get(card))


class Track:
    __slots__ = ('card', 'owner', 'body', 'x', 'y', 'first', 'last', 'facing', 'main', 'id')

    def __init__(self, tid, card, owner, body, x, y, tick, main):
        self.id, self.card, self.owner, self.body = tid, card, owner, body
        self.x, self.y, self.first, self.last, self.facing, self.main = x, y, tick, tick, (0., 0.), main


class UnitTracker:
    """Tracks + opponent plays from births.

    Play detection is per CLUSTER, not per track: a new main-body birth of owner o at (x, y) opens a cluster unless
    one of o's clusters lies within `vote_tiles` (then it joins it). For `vote_ticks` after opening, every detection of
    o within `vote_tiles` whose track was born since the cluster opened votes for its card (weighted by detection
    score >= `min_score`); frames with such a detection are hits. Once the window has passed and the cluster has
    >= `confirm_hits` hits it emits ONE play - the top-voted card at the first-sighting position and tick; a cluster
    still short of hits after `confirm_ticks` is dropped (unconfirmed). A closed cluster absorbs further births within `vote_tiles` for `relabel_ticks` (a perception
    relabel of the same spawn is not a new play; a same-card birth is the same play). Same-card births within
    `cluster_tiles`/`cluster_ticks` of a play also join it (multi-unit cards spread out)."""

    def __init__(self, bodies: CardBodies, *, radius=1.2, speed=.06, max_radius=3.5, ttl=40, building_ttl=400,
                 memory=200, cluster_tiles=4.0, cluster_ticks=40, confirm_hits=2, vote_ticks=10, vote_tiles=2.5,
                 relabel_ticks=40, min_score=.6, confirm_ticks=30):
        # Defaults from a sweep on the perception owner's 2 validation matches (sample-records, 49 opponent plays):
        # real output P/R .75/.80 (vs .33-.42/.93-1.0 with per-track confirmation); truth units .91/.86.
        self.cb = bodies
        self.radius, self.speed, self.max_radius = radius, speed, max_radius
        self.ttl, self.building_ttl, self.memory = ttl, building_ttl, memory
        self.cluster_tiles, self.cluster_ticks = cluster_tiles, cluster_ticks
        self.confirm_hits, self.vote_ticks, self.vote_tiles = confirm_hits, vote_ticks, vote_tiles
        self.relabel_ticks, self.min_score, self.confirm_ticks = relabel_ticks, min_score, confirm_ticks
        self.live, self.dead, self.clusters = [], [], []
        self.n = 0
        self.stats = Counter()

    def _match(self, pool, card, owner, x, y, tick, taken):
        best, bd = None, None
        for t in pool:
            if t.card != card or t.owner != owner or t.id in taken:
                continue
            r = min(self.max_radius, self.radius + self.speed*(tick - t.last))
            d = math.hypot(x - t.x, y - t.y)
            if d <= r and (bd is None or d < bd):
                best, bd = t, d
        return best

    def _body(self, card, owner, x, y, tick):
        cb = self.cb
        live = [t for t in self.live if t.card == card and t.owner == owner]
        if cb.spawner(card) and any(t.main and t.body[1] == 1 for t in live):
            return cb.children[card][0], False
        if cb.death.get(card) and any(t.main and abs(tick - t.last) <= 40 and math.hypot(x-t.x, y-t.y) <= 3.
                                      for t in self.dead if t.card == card and t.owner == owner):
            return cb.death[card][0], False
        main = cb.main.get(card) or []
        if not main:
            return None, False
        if len(main) == 1:
            return main[0][0], True
        have = Counter(t.body for t in live if t.main)
        total = sum(n for _, n in main)
        k = sum(have.values()) + 1
        body = max(main, key=lambda bn: (bn[1]*k/total - have[bn[0]], bn[1]))[0]
        return body, True

    def _birth(self, owner, card, x, y, tick, tower_alive):
        for c in self.clusters:
            if c['owner'] == owner and math.hypot(x - c['x'], y - c['y']) <= self.vote_tiles:
                if c['card'] is None or tick - c['t0'] <= self.relabel_ticks:
                    if c['card'] is not None and c['card'] != card:
                        self.stats['relabel_absorbed'] += 1
                    return
            if c['owner'] == owner and c['card'] == card and tick - c['t0'] <= self.cluster_ticks and \
                    math.hypot(x - c['x'], y - c['y']) <= self.cluster_tiles:
                return
        if owner == 1 and not self.deployable(card, x, y, tower_alive):
            self.stats['birth_outside_zone'] += 1
            return
        self.clusters.append(dict(owner=owner, x=x, y=y, t0=tick, votes=Counter(), hits=0, card=None, last_hit=None))

    def update(self, tick, units, tower_alive):
        """units: [(card, owner, x, y[, score])] -> (assigned [(body or None, facing)], plays [(owner, card, x, y, tick)])."""
        taken, out, plays, seen = set(), [], [], []
        for u in units:
            card, owner, x, y = u[:4]
            score = u[4] if len(u) > 4 and u[4] is not None else 1.
            t = self._match(self.live, card, owner, x, y, tick, taken)
            if t is None:
                t = self._match(self.dead, card, owner, x, y, tick, taken)
                if t is not None:              # re-detection of an expired track: not a birth
                    self.dead.remove(t)
                    self.live.append(t)
                    self.stats['revived'] += 1
            if t is not None:
                dx, dy = x - t.x, y - t.y
                if math.hypot(dx, dy) > .05:
                    t.facing = (dx, dy)
                t.x, t.y, t.last = x, y, tick
                taken.add(t.id)
                out.append((t.body, t.facing))
                seen.append((t, score))
                continue
            body, main = self._body(card, owner, x, y, tick)
            if body is None:
                self.stats[f'no_body:{card}'] += 1
                out.append((None, (0., 0.)))
                continue
            self.n += 1
            t = Track(self.n, card, owner, body, x, y, tick, main)
            self.live.append(t)
            taken.add(t.id)
            out.append((t.body, t.facing))
            self.stats['births'] += 1
            if main:
                self._birth(owner, card, x, y, tick, tower_alive)
            seen.append((t, score))
        # votes/hits for open clusters, then close the ones whose window has passed
        for c in self.clusters:
            if c['card'] is not None:
                continue
            hit = False
            for t, score in seen:
                if t.main and t.owner == c['owner'] and t.first >= c['t0'] and score >= self.min_score and \
                        math.hypot(t.x - c['x'], t.y - c['y']) <= self.vote_tiles:
                    c['votes'][t.card] += score
                    hit = True
            c['hits'] += hit
        keep = []
        for c in self.clusters:
            if c['card'] is None and tick - c['t0'] >= self.vote_ticks and \
                    (c['hits'] >= self.confirm_hits or tick - c['t0'] > self.confirm_ticks):
                if c['hits'] >= self.confirm_hits and c['votes']:
                    c['card'] = max(c['votes'].items(), key=lambda kv: (kv[1], kv[0]))[0]
                    if len(c['votes']) > 1:
                        self.stats['vote_contested'] += 1
                    plays.append((c['owner'], c['card'], c['x'], c['y'], c['t0']))
                else:
                    self.stats['unconfirmed_birth'] += 1
                    continue
            if c['card'] is None or tick - c['t0'] <= max(self.relabel_ticks, self.cluster_ticks):
                keep.append(c)
        self.clusters = keep
        keep, gone = [], []
        for t in self.live:
            ttl = self.building_ttl if t.body[1] == 1 else self.ttl
            (keep if tick - t.last <= ttl else gone).append(t)
        self.live = keep
        self.dead = [t for t in self.dead + gone if tick - t.last <= self.memory]
        return out, plays

    @staticmethod
    def deployable(card, x, y, tower_alive):
        """Opponent deploy zone in our frame. tower_alive: {('left'|'right'): bool} for OUR princess towers."""
        if card in DEPLOY_ANYWHERE or y >= 15.:
            return True
        side = 'left' if x < 9 else 'right'
        return not tower_alive.get(side, True) and y >= 9.


class ClockTracker:
    """HUD clock -> tick, robust to misread frames. Game time is linear in capture time (20 ticks/s), so
    tick = timestamp_ms/50 + offset; only the offset is estimated:
    1. an anchor, best first: `anchor(tick, timestamp_ms)` from the live loop (e.g. match start), else a CONFIRMED
       elixir-phase transition (1->2 at tick 2400, 2->3 at 4800; the new phase must hold for `confirm` frames; the
       boundary is put midway between the last old-phase and first new-phase frame) - the phase head is far more
       accurate than the clock regression;
    2. otherwise the robust centre of all clock readings: a displayed second c says tick in [lo, lo+19],
       lo = (180-c)*20+1 (regulation) or (300-c)*20+1 (overtime, chosen when nearer the current estimate); offset =
       midpoint of the 80th-percentile lower end and 20th-percentile upper end, else the median centre.
    Without timestamps: the plain per-frame reading. Monotonic. Phase deltas (elixir regen) never depend on the
    offset; only absolute boundaries (2400/4800/3600) do."""

    def __init__(self, window=4000, confirm=3):
        from collections import deque
        self.obs, self.tick = deque(maxlen=window), None
        self.confirm, self.fixed, self.candidate = confirm, None, None
        self.last_phase, self.last_ts = None, None

    def anchor(self, tick, timestamp_ms):
        self.fixed = float(tick) - float(timestamp_ms)/50

    def offset(self):
        if self.fixed is not None:
            return self.fixed
        lows = sorted(self.obs)
        n = len(lows) - 1
        lo, hi = lows[int(.8*n)], lows[int(.2*n)] + 19
        return (lo + hi)/2 if lo <= hi else lows[n//2] + 9.5

    def _phase(self, phase, ts):
        if self.candidate is not None:
            target, mid, seen = self.candidate
            if phase == target:
                seen += 1
                if seen >= self.confirm and self.fixed is None:
                    self.fixed = {2: 2400, 3: 4800}[target] - mid/50
                    self.candidate = None
                else:
                    self.candidate = (target, mid, seen)
            else:
                self.candidate = None
        if self.last_phase is not None and phase == self.last_phase + 1 and phase in (2, 3) and \
                self.last_ts is not None and ts - self.last_ts <= 1000 and self.fixed is None:
            self.candidate = (phase, (self.last_ts + ts)/2, 1)
        if self.candidate is None or phase != self.candidate[0]:
            self.last_phase, self.last_ts = phase, ts
        elif self.last_phase is None:
            self.last_phase, self.last_ts = phase, ts

    def __call__(self, clock_s, phase, timestamp_ms=None):
        c = max(0, int(round(float(clock_s))))
        phase = int(phase or 1)
        reg, ot = (180 - c)*20 + 1, (300 - c)*20 + 1
        if timestamp_ms is None:
            t = ot if (phase == 3 or (phase == 2 and c > 60)) else reg
        else:
            ts = float(timestamp_ms)
            self._phase(phase, ts)
            t0 = ts/50
            if self.obs or self.fixed is not None:
                guess = t0 + self.offset()
                lo = min((reg, ot), key=lambda v: abs(v + 9.5 - guess))
            else:
                lo = ot if (phase == 3 or (phase == 2 and c > 60)) else reg
            self.obs.append(lo - t0)
            t = int(round(t0 + self.offset()))
        t = max(t, 0)
        if self.tick is not None:
            t = max(t, self.tick)
        self.tick = t
        return t
