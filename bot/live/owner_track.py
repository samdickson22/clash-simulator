"""Learned temporal owner for perception units (LIVE translator, exploration tier).

The detector gives every unit a team per frame, and its errors are transient and one-sided: enemy bodies read as ours in
busy frames (s52 audit: 33/213 enemy bodies vs 0/160 of ours). OwnerTracks follows bodies across frames regardless of
the detector's team (same raw detector class, nearest first), and gives every unit generic, causal features of its
track: the history of detector teams, where the body first appeared and how it moved, and our own deploys near its
birth. A small boosted-tree model (bot/live/playdet/trees.py format) maps them to P(opponent). No card or position rules:
the model learns how far to trust each kind of evidence from Sol-labelled live frames.

Shared by dataset building (bot/live/owner_dataset.py) and the translator (CLASHER_LIVE_OWNER_MODEL)."""
from __future__ import annotations

import math

NAMES = (
    'cur_opp', 'cur_score', 'n_obs', 'frac_opp', 'last5_frac_opp', 'streak', 'age',
    'birth_x', 'birth_y', 'birth_opp', 'cur_x', 'cur_y', 'dy', 'dx', 'speed', 'path',
    'own_deploy_dt', 'own_deploy_dist', 'own_deploy_same_card', 'card_in_our_deck', 'building', 'air',
    'n_units_frame', 'n_opp_frame', 'near_opp', 'near_ours',
    'prev_dist', 'prev_gap', 'prev_frac_opp', 'prev_n',
)
FAR, LONG = 99., 9999.


class OwnerTracks:
    """Owner-agnostic tracks: a detection continues the nearest live track of its raw class within `radius` tiles
    (+ `speed` per tick since last seen) and `max_gap` ticks; else it starts a track."""
    radius, speed, max_gap, memory = 1.2, .06, 12, 200

    def __init__(self, classes=None, deck=()):
        self.classes = classes or {}        # raw class name -> {card, kind, air} (live/yolo_synth/classes.json)
        self.deck = set(deck)
        self.tracks, self.n, self.ended = [], 0, []

    def _cls(self, u, raw):
        return raw if raw is not None else (u.get('cls') or u.get('card'))

    def update(self, tick, units, raw=None, own_plays=()):
        """units: record units (owner 0 ours / 1 opp, x, y, score); raw: their raw detector classes (units_yolo) or
        None; own_plays: our deploys so far [(tick, card, x, y)]. -> one feature row per unit (aligned with units) and
        the track id of each."""
        raw = list(raw) if raw is not None and len(raw) == len(units) else [None]*len(units)
        live = [t for t in self.tracks if tick - t['last'] <= self.max_gap]
        self.ended = [t for t in self.ended + [t for t in self.tracks if tick - t['last'] > self.max_gap]
                      if tick - t['last'] <= self.memory]
        self.tracks = live
        pairs = []
        for i, (u, r) in enumerate(zip(units, raw)):
            c = self._cls(u, r)
            for j, t in enumerate(live):
                if t['cls'] != c:
                    continue
                d = math.hypot(t['x'] - float(u['x']), t['y'] - float(u['y']))
                if d <= self.radius + self.speed*(tick - t['last']):
                    pairs.append((d, i, j))
        pairs.sort()
        got, used = {}, set()
        for d, i, j in pairs:
            if i in got or j in used:
                continue
            got[i], used = j, used | {j}
        rows, ids = [], []
        opp_pts = [(float(u['x']), float(u['y'])) for u in units if int(u['owner']) == 1]
        our_pts = [(float(u['x']), float(u['y'])) for u in units if int(u['owner']) == 0]
        for i, (u, r) in enumerate(zip(units, raw)):
            x, y, o = float(u['x']), float(u['y']), 1 if int(u['owner']) == 1 else 0
            if i in got:
                t = live[got[i]]
            else:
                self.n += 1
                t = dict(id=self.n, cls=self._cls(u, r), birth=tick, bx=x, by=y, bo=o, owners=[], path=0., x=x, y=y,
                         last=tick, scores=[])
                t['deploy'] = self._own_deploy(t, own_plays)
                t['prev'] = self._previous(t, tick)
                self.tracks.append(t)
            t['path'] += math.hypot(x - t['x'], y - t['y'])
            t['x'], t['y'], t['last'] = x, y, tick
            t['owners'].append(o)
            t['scores'].append(float(u.get('score') or 0.))
            rows.append(self._features(t, tick, o, float(u.get('score') or 0.), units, opp_pts, our_pts, x, y))
            ids.append(t['id'])
        return rows, ids

    def _previous(self, t, tick):
        """The nearest recently ended track of the same class this body could continue (a body lost for a moment and
        found again): (tiles away, ticks since it ended, its opponent fraction, its length)."""
        best = None
        for e in self.ended:
            if e['cls'] != t['cls']:
                continue
            gap = tick - e['last']
            d = math.hypot(e['x'] - t['bx'], e['y'] - t['by'])
            if d <= 3. + self.speed*gap and (best is None or d < best[0]):
                best = (d, float(gap), sum(e['owners'])/len(e['owners']), float(len(e['owners'])))
        return best or (FAR, LONG, -1., 0.)

    def _own_deploy(self, t, own_plays):
        """Our nearest own deploy before this body's birth: (ticks before, tiles away, same card)."""
        card = (self.classes.get(t['cls']) or {}).get('card')
        best = None
        for pt, pc, px, py in own_plays:
            if 0 <= t['birth'] - pt <= 200:
                d = math.hypot(px - t['bx'], py - t['by'])
                if best is None or d < best[1]:
                    best = (t['birth'] - pt, d, float(card is not None and pc == card))
        return best or (LONG, FAR, 0.)

    def _features(self, t, tick, o, score, units, opp_pts, our_pts, x, y):
        own = t['owners']
        last5 = own[-5:]
        streak = 0
        for v in reversed(own):
            if v != o:
                break
            streak += 1
        e = self.classes.get(t['cls']) or {}
        card = e.get('card')
        near = lambda pts: min((math.hypot(px - x, py - y) for px, py in pts if (px, py) != (x, y)), default=FAR)
        age = max(1, tick - t['birth'])
        return [float(o), score, float(len(own)), sum(own)/len(own), sum(last5)/len(last5), float(streak),
                float(tick - t['birth']), t['bx'], t['by'], float(t['bo']), x, y, y - t['by'], x - t['bx'],
                math.hypot(x - t['bx'], y - t['by'])/age, t['path'],
                float(t['deploy'][0]), float(t['deploy'][1]), t['deploy'][2], float(card in self.deck),
                float(e.get('kind') == 'building'), float(bool(e.get('air'))),
                float(len(units)), float(len(opp_pts)), near(opp_pts), near(our_pts), *t['prev']]
