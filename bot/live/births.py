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
    def __init__(self, bodies: CardBodies, *, radius=1.2, speed=.06, max_radius=3.5, ttl=40, building_ttl=400,
                 memory=200, cluster_tiles=4.0, cluster_ticks=40, confirm_hits=2, confirm_ticks=20):
        self.cb = bodies
        self.radius, self.speed, self.max_radius = radius, speed, max_radius
        self.ttl, self.building_ttl, self.memory = ttl, building_ttl, memory
        self.cluster_tiles, self.cluster_ticks = cluster_tiles, cluster_ticks
        self.confirm_hits, self.confirm_ticks = confirm_hits, confirm_ticks
        self.live, self.dead, self.births = [], [], []
        self.pending = {}                   # track id -> [hits, (owner, card, x, y, tick)] awaiting confirmation
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

    def update(self, tick, units, tower_alive):
        """units: [(card, owner, x, y)] -> (assigned [(body or None, facing)], plays [(owner, card, x, y, tick)])."""
        taken, out, plays = set(), [], []
        for card, owner, x, y in units:
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
                if t.id in self.pending:
                    self.pending[t.id][0] += 1
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
                recent = any(b[0] == owner and b[1] == card and tick - b[4] <= self.cluster_ticks and
                             math.hypot(x - b[2], y - b[3]) <= self.cluster_tiles for b in self.births)
                self.births.append((owner, card, x, y, tick))
                if recent:
                    continue
                if owner == 1 and not self.deployable(card, x, y, tower_alive):
                    self.stats['birth_outside_zone'] += 1
                    continue
                self.pending[t.id] = [1, (owner, card, x, y, tick)]
        # A play is a birth seen again (>= confirm_hits sightings within confirm_ticks): a one-frame mislabel is not
        # a play. The play keeps the first-sighting tick and position.
        for tid, (hits, play) in list(self.pending.items()):
            if hits >= self.confirm_hits:
                plays.append(play)
                del self.pending[tid]
            elif tick - play[4] > self.confirm_ticks:
                self.stats['unconfirmed_birth'] += 1
                del self.pending[tid]
        keep, gone = [], []
        for t in self.live:
            ttl = self.building_ttl if t.body[1] == 1 else self.ttl
            (keep if tick - t.last <= ttl else gone).append(t)
        self.live = keep
        self.dead = [t for t in self.dead + gone if tick - t.last <= self.memory]
        self.births = [b for b in self.births if tick - b[4] <= self.cluster_ticks]
        return out, plays

    @staticmethod
    def deployable(card, x, y, tower_alive):
        """Opponent deploy zone in our frame. tower_alive: {('left'|'right'): bool} for OUR princess towers."""
        if card in DEPLOY_ANYWHERE or y >= 15.:
            return True
        side = 'left' if x < 9 else 'right'
        return not tower_alive.get(side, True) and y >= 9.


class ClockTracker:
    def __init__(self):
        self.overtime, self.tick, self.anchor = False, None, None

    def __call__(self, clock_s, phase, timestamp_ms=None):
        c = max(0, int(round(float(clock_s))))
        phase = int(phase or 1)
        if phase == 3 or (phase == 2 and c > 60):
            self.overtime = True
        lo = ((300 if self.overtime else 180) - c)*20 + 1
        lo = max(lo, 0)
        t = lo
        if timestamp_ms is not None:
            if self.anchor is None or self.anchor[0] != lo:
                self.anchor = (lo, float(timestamp_ms))      # first frame seen in this displayed second
            t = lo + min(19, max(0, int((float(timestamp_ms) - self.anchor[1])/50)))
        if self.tick is not None:
            t = max(t, self.tick)
        self.tick = t
        return t
