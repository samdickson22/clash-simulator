"""Learned temporal owner for perception units (LIVE translator, exploration tier).

The detector gives every unit a team per frame, and its errors are transient and one-sided: enemy bodies read as ours in
busy frames (s52 audit: 33/213 enemy bodies vs 0/160 of ours). OwnerTracks follows bodies across frames regardless of
the detector's team (same raw detector class, nearest first), and gives every unit generic, causal features of its
track: the history of detector teams, where the body first appeared and how it moved, and our own deploys near its
birth. A small boosted-tree model (bot/live/playdet/trees.py format) maps them to P(opponent). No card or position rules:
the model learns how far to trust each kind of evidence from Sol-labelled live frames.

Feature sets: NAMES (v1, 30 features: the models up to v1.2) and NAMES_V2 = NAMES + PTEAM, which adds the detector's
own team probability per unit (perception `units_yolo_info[i].p_team` = P(opponent), logged from s58) as track
history. A unit without it (older runs, or an unaligned record) has pteam_known 0 and -1 in the p_team columns, so
the trees separate it with ordinary splits (the walker has no missing-value path). A model names its features;
OwnerTracks(names=...) returns exactly those columns, so v1 models see the same rows as before.

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
PTEAM = ('pteam_known', 'cur_pteam', 'mean_pteam', 'last5_pteam', 'min_pteam', 'max_pteam', 'birth_pteam')
NAMES_V2 = NAMES + PTEAM
# our own deploys of this unit's card, at THIS frame (own information: our taps): ticks since the latest one within
# OWN_WINDOW, tiles from its deploy point to the unit now, and how many in the window (a swarm walking or flying off
# its deploy point stays linked to it after its track breaks)
OWN = ('own_same_dt', 'own_same_dist_now', 'own_same_n')
OWN_WINDOW = 300
NAMES_V3 = NAMES + OWN
# swarm context at THIS frame, by card (raw classes of one card, e.g. bat / bat-evolution, count together), from the
# detector's teams: our and the opponent's other bodies of the unit's card within SWARM_TILES now, the nearest of ours,
# the most of ours near this spot over the last SWARM_FRAMES frames, and the nearest live track of the card that is
# mostly ours and went unmatched in this frame (a body of our swarm that this unit may be, read with the other team)
SWARM = ('sw_ours_n', 'sw_ours_d', 'sw_opp_n', 'sw_ours_recent', 'sw_lost_ours_d', 'sw_lost_ours_gap')
SWARM_TILES, SWARM_FRAMES = 2.5, 3
NAMES_V4 = NAMES + SWARM
# the badge/team-cue crop classifier (perception units_yolo_info[i]: badge_p_opp = P(opponent | cue visible),
# badge_visible = P(a team cue is visible)) as track history over the frames where a cue is visible (>= BADGE_SEEN);
# -1 where unknown (classifier off, no aligned info, or no visible frame yet), with known flags, as PTEAM
BADGE = ('badge_known', 'cur_badge_vis', 'cur_badge_opp', 'mean_badge_opp', 'last5_badge_opp', 'n_badge_seen',
         'frac_badge_seen')
BADGE_SEEN = .5
NAMES_V5 = NAMES + SWARM + BADGE
ALL = NAMES + PTEAM + OWN + SWARM + BADGE
FAR, LONG = 99., 9999.


class OwnerTracks:
    """Owner-agnostic tracks: a detection continues the nearest live track of its raw class within `radius` tiles
    (+ `speed` per tick since last seen) and `max_gap` ticks; else it starts a track."""
    radius, speed, max_gap, memory = 1.2, .06, 12, 200

    def __init__(self, classes=None, deck=(), names=NAMES, match='raw'):
        self.classes = classes or {}        # raw class name -> {card, kind, air} (live/yolo_synth/classes.json)
        self.deck = set(deck)
        unknown = [n for n in names if n not in ALL]
        if unknown:
            raise ValueError(f'unknown owner features {unknown}')
        self.names = tuple(names)
        self.cols = None if self.names == ALL else [ALL.index(n) for n in self.names]
        self.tracks, self.n, self.ended = [], 0, []
        self.recent = []                    # the last SWARM_FRAMES frames: [(card, x, y, owner)] (detector teams)
        # what a body must share to continue a track: 'raw' = the detector's raw class (up to v1.4c); 'card' = the
        # card of the raw class (classes.json), so a body whose raw class flips between one card's classes (bat ->
        # bat-evolution) keeps its track and history (v1.4d). Set from the owner spec's `track_match`.
        if match not in ('raw', 'card'):
            raise ValueError(f'unknown track match {match!r}')
        self.match = match

    def _key(self, cls):
        return ((self.classes.get(cls) or {}).get('card') or cls) if self.match == 'card' else cls

    def _cls(self, u, raw):
        return raw if raw is not None else (u.get('cls') or u.get('card'))

    def update(self, tick, units, raw=None, own_plays=(), info=None):
        """units: record units (owner 0 ours / 1 opp, x, y, score); raw: their raw detector classes (units_yolo) or
        None; own_plays: our deploys so far [(tick, card, x, y)]; info: perception's per-unit extras
        (units_yolo_info, {p_team, ...}) or None. -> one feature row per unit (aligned with units, the columns of
        `names`) and the track id of each."""
        raw = list(raw) if raw is not None and len(raw) == len(units) else [None]*len(units)
        aligned = info is not None and len(info) == len(units)
        pt = [i.get('p_team') if isinstance(i, dict) else None for i in info] if aligned else [None]*len(units)
        bd = [(i.get('badge_p_opp'), i.get('badge_visible'))
              if isinstance(i, dict) and i.get('badge_visible') is not None else None for i in info] \
            if aligned else [None]*len(units)
        live = [t for t in self.tracks if tick - t['last'] <= self.max_gap]
        self.ended = [t for t in self.ended + [t for t in self.tracks if tick - t['last'] > self.max_gap]
                      if tick - t['last'] <= self.memory]
        self.tracks = live
        pairs = []
        for i, (u, r) in enumerate(zip(units, raw)):
            c = self._cls(u, r)
            for j, t in enumerate(live):
                if self._key(t['cls']) != self._key(c):
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
        cards = [(self.classes.get(self._cls(u, r)) or {}).get('card') or self._cls(u, r) for u, r in zip(units, raw)]
        frame = [(c, float(u['x']), float(u['y']), 1 if int(u['owner']) == 1 else 0) for c, u in zip(cards, units)]
        unmatched = [t for j, t in enumerate(live) if j not in used and t['last'] < tick]
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
                         last=tick, scores=[], pteams=[], bp=pt[i], badges=[], badge_frames=0)
                t['deploy'] = self._own_deploy(t, own_plays)
                t['prev'] = self._previous(t, tick)
                self.tracks.append(t)
            t['path'] += math.hypot(x - t['x'], y - t['y'])
            t['x'], t['y'], t['last'] = x, y, tick
            t['owners'].append(o)
            t['scores'].append(float(u.get('score') or 0.))
            if pt[i] is not None:
                t['pteams'].append(float(pt[i]))
            if bd[i] is not None:
                t['badge_frames'] += 1
                if float(bd[i][1]) >= BADGE_SEEN and bd[i][0] is not None:
                    t['badges'].append(float(bd[i][0]))
            row = self._features(t, tick, o, float(u.get('score') or 0.), units, opp_pts, our_pts, x, y) + \
                self._pteam(t, pt[i]) + self._own_now(t, tick, x, y, own_plays) + \
                self._swarm(i, cards[i], x, y, tick, frame, unmatched) + self._badge(t, bd[i])
            rows.append(row if self.cols is None else [row[c] for c in self.cols])
            ids.append(t['id'])
        self.recent = (self.recent + [frame])[-SWARM_FRAMES:]
        return rows, ids

    @staticmethod
    def _badge(t, b):
        """BADGE columns: this frame's cue (visible P, P(opp) if visible) and the track's visible-frame history."""
        h, n = t['badges'], t['badge_frames']
        vis = -1. if b is None else float(b[1])
        cur = float(b[0]) if b is not None and b[0] is not None and float(b[1]) >= BADGE_SEEN else -1.
        if not h:
            return [float(n > 0), vis, cur, -1., -1., 0., 0.]
        last5 = h[-5:]
        return [1., vis, cur, sum(h)/len(h), sum(last5)/len(last5), float(len(h)), len(h)/max(1, n)]

    def _swarm(self, i, card, x, y, tick, frame, unmatched):
        """SWARM columns for unit i (card, at x, y) in this frame."""
        near = lambda c, px, py: c == card and math.hypot(px - x, py - y) <= SWARM_TILES
        ours = [math.hypot(px - x, py - y) for k, (c, px, py, o) in enumerate(frame)
                if k != i and o == 0 and near(c, px, py)]
        opp = sum(1 for k, (c, px, py, o) in enumerate(frame) if k != i and o == 1 and near(c, px, py))
        past = max((sum(1 for c, px, py, o in f if o == 0 and near(c, px, py)) for f in self.recent), default=0)
        lost = [(math.hypot(t['x'] - x, t['y'] - y), tick - t['last']) for t in unmatched
                if ((self.classes.get(t['cls']) or {}).get('card') or t['cls']) == card and
                sum(t['owners'])/len(t['owners']) < .5 and math.hypot(t['x'] - x, t['y'] - y) <= 2*SWARM_TILES]
        ld, lg = min(lost) if lost else (FAR, LONG)
        return [float(len(ours)), min(ours, default=FAR), float(opp), float(past), ld, float(lg)]

    def _own_now(self, t, tick, x, y, own_plays):
        """OWN columns: our deploys of this track's card in the last OWN_WINDOW ticks."""
        card = (self.classes.get(t['cls']) or {}).get('card')
        recent = [(pt, px, py) for pt, pc, px, py in own_plays
                  if card is not None and pc == card and 0 <= tick - pt <= OWN_WINDOW]
        if not recent:
            return [LONG, FAR, 0.]
        pt, px, py = max(recent)
        return [float(tick - pt), math.hypot(x - px, y - py), float(len(recent))]

    @staticmethod
    def _pteam(t, p):
        """PTEAM columns: this frame's p_team and the track's history of it (-1 where unknown)."""
        h = t['pteams']
        if not h:
            return [float(p is not None), -1., -1., -1., -1., -1., -1.]
        last5 = h[-5:]
        return [float(p is not None), float(p) if p is not None else -1., sum(h)/len(h), sum(last5)/len(last5),
                min(h), max(h), float(t['bp']) if t['bp'] is not None else -1.]

    def _previous(self, t, tick):
        """The nearest recently ended track of the same class this body could continue (a body lost for a moment and
        found again): (tiles away, ticks since it ended, its opponent fraction, its length)."""
        best = None
        for e in self.ended:
            if self._key(e['cls']) != self._key(t['cls']):
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
