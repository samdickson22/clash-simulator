"""Temporal entity filter on the perceived packet (bot lead, noise-robust lever (a); exploration).

The live bot decides from a packet built from ONE perception frame. Perception noise (bot/live/empirical.py, measured
on validation): a true unit is missed with Markov persistence (p(hit | hit) .92, p(hit | miss) .34, recall .81),
phantom units appear ~.19 per frame per owner, mostly right next to a real unit of that owner (median .26 tiles)
with a random card, and a detected unit's card is misread ~5% of frames. The search root and it5s2 inherit all of it.

EntityFilter keeps tracks across polls (every 5 ticks, the bot's own observation history; fair information: it reads
only the packets the bot was given) and rewrites the packet's entity table:
  - confirm   a NEW track is output only after `conf` detections, unless it is isolated (no output track of the same
              owner within `iso` tiles): a new unit far from everything is a deployment, a new unit on top of another
              is most often a phantom (conf=1: no suppression);
  - coast     a confirmed track that is not detected stays in the table for up to `coast` polls at its predicted
              position (last velocity, capped), last hp (coast=0: no fill-in); `coast_low` polls if its last hp was
              below `low_hp` (dying units are more often really gone);
  - vote      the output body is the majority over the track's last `vote` detections (vote=0: current detection);
  - memory    an expired confirmed track is remembered for `memory` polls, so a re-detection is not a new track.
Towers (always read from the HUD) and non-troop/building rows (none in perception records) pass through unchanged.

Name grammar (bot/noise/player.py): 'NR-c2i12m3v5' = conf 2, iso 1.2 tiles, coast 3, vote 5; optional 'l<k>' coast_low,
'r<tenths>' gate radius, 'M<k>' memory, 's<scope>' (a = all tiers see the filtered view (default); r = search root
only). Defaults = c1i0m0v0 = identity.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np

TOWER_NAMES = ('Tower', 'KingTower')
BOARD_W, BOARD_H = 18., 32.


@dataclass(frozen=True)
class FilterConfig:
    conf: int = 1          # detections before a non-isolated new track is output
    iso: float = 0.        # isolation radius (tiles); 0 = every new track needs `conf`
    coast: int = 0         # polls a confirmed undetected track stays in the table
    coast_low: int = -1    # coast for tracks whose last hp < low_hp (-1 = same as coast)
    low_hp: float = .25
    vote: int = 0          # majority window over the track's detected bodies (0 = current)
    gate: float = 1.0      # match radius (tiles) at dt = 0; grows by gate_v per tick
    gate_v: float = .03
    memory: int = 8        # polls an expired confirmed track is remembered
    vmax: float = .12      # tiles per tick cap on the coasting velocity
    damp: float = 1.       # coasting uses damp * velocity (0 = hold the last position)
    tok_cost: float = .6   # matching cost added for a different body
    ev: int = 0            # a new track within ev_r tiles of a same-owner play of the last `ev` ticks is output at once
    ev_r: float = 3.
    scope: str = 'a'

    def identity(self):
        return self.conf <= 1 and self.coast <= 0 and self.vote <= 1

    def tag(self):
        s = f'c{self.conf}i{int(round(self.iso*10))}m{self.coast}v{self.vote}'
        if self.coast_low >= 0:
            s += f'l{self.coast_low}'
        if self.gate != 1.0:
            s += f'r{int(round(self.gate*10))}'
        if self.memory != 8:
            s += f'M{self.memory}'
        if self.damp != 1.:
            s += f'd{int(round(self.damp*10))}'
        if self.ev:
            s += f'e{self.ev}'
        if self.scope != 'a':
            s += f's{self.scope}'
        return s


_TOKENS = {'c': ('conf', int), 'i': ('iso', lambda v: int(v)/10), 'm': ('coast', int), 'v': ('vote', int),
           'l': ('coast_low', int), 'r': ('gate', lambda v: int(v)/10), 'M': ('memory', int), 's': ('scope', str),
           'd': ('damp', lambda v: int(v)/10), 'e': ('ev', int)}


def parse_config(tag):
    kw = {}
    pos = 0
    for m in re.finditer(r'([cimvlrMde])(\d+)|s([ar])', tag):
        if m.start() != pos:
            raise ValueError(f'bad filter tag {tag!r}')
        pos = m.end()
        if m.group(3):
            kw['scope'] = m.group(3)
        else:
            name, conv = _TOKENS[m.group(1)]
            kw[name] = conv(m.group(2))
    if pos != len(tag):
        raise ValueError(f'bad filter tag {tag!r}')
    return FilterConfig(**kw)


class _Track:
    __slots__ = ('own', 'x', 'y', 'vx', 'vy', 'last', 'hits', 'miss', 'confirmed', 'toks', 'rows', 'cur', 'hp')

    def __init__(self, own, x, y, tick, tok, ent):
        self.own, self.x, self.y, self.vx, self.vy, self.last = own, x, y, 0., 0., tick
        self.hits, self.miss, self.confirmed = 1, 0, False
        self.toks = [tok]
        self.rows = {tok: ent}
        self.cur, self.hp = tok, float(ent[1][9])


def _entities(packet):
    """[(token, row, level, level_conf, id_conf, feat_conf)] of the packet's masked entity rows."""
    obs = packet.observation
    idx = np.flatnonzero(obs.entity_mask)
    lv = obs.entity_levels
    lc = obs.entity_level_confidence
    return [(int(obs.entity_ids[i]), obs.entity_features[i].copy(), int(lv[i]) if lv is not None else 0,
             float(lc[i]) if lc is not None else 0., float(packet.entity_id_confidence[i]),
             packet.entity_feature_confidence[i].copy()) for i in idx]


def _key(ent):
    row = ent[1]
    return (int(np.argmax(row[4:9])), int(row[3] > .5), ent[0], round(float(row[1]), 5), round(float(row[0]), 5))


def with_entities(packet, ents):
    """The packet with its entity table replaced by `ents` (sorted as the builder sorts; capacity-capped)."""
    obs = packet.observation
    cap = len(obs.entity_ids)
    ents = sorted(ents, key=_key)[:cap]
    ids = np.zeros_like(obs.entity_ids)
    feats = np.zeros_like(obs.entity_features)
    mask = np.zeros_like(obs.entity_mask)
    idc = np.zeros_like(packet.entity_id_confidence)
    fc = np.zeros_like(packet.entity_feature_confidence)
    levels = None if obs.entity_levels is None else np.zeros_like(obs.entity_levels)
    lconf = None if obs.entity_level_confidence is None else np.zeros_like(obs.entity_level_confidence)
    for i, (tok, row, lv, lcf, ic, frow) in enumerate(ents):
        ids[i], feats[i], mask[i], idc[i], fc[i] = tok, row, True, ic, frow
        if levels is not None:
            levels[i], lconf[i] = lv, lcf
    new_obs = replace(obs, entity_ids=ids, entity_features=feats, entity_mask=mask, entity_levels=levels,
                      entity_level_confidence=lconf)
    return replace(packet, observation=new_obs, entity_id_confidence=idc, entity_feature_confidence=fc)


class EntityFilter:
    def __init__(self, cfg: FilterConfig, tower_ids):
        self.cfg, self.towers = cfg, set(int(t) for t in tower_ids)
        self.tracks, self.memory = [], []
        self.stats = Counter()

    def update(self, tick, packet, plays=()):
        """Advance the tracks with this poll's packet; return the filtered packet (the same object if identity).
        plays: [(own, x, y, tick)] card plays seen so far, in the packet's frame (used by `ev`)."""
        if self.cfg.identity():
            return packet
        return with_entities(packet, self.step(tick, _entities(packet), plays))

    def step(self, tick, ents, plays=()):
        """ents: this poll's entity rows (_entities) -> the filtered rows."""
        cfg = self.cfg
        keep, dets = [], []
        for e in ents:
            row = e[1]
            kind = int(np.argmax(row[4:9]))
            if e[0] in self.towers or kind > 1:
                keep.append(e)
            else:
                dets.append((e, row[2] > .5, float(row[0])*BOARD_W, float(row[1])*BOARD_H))
        # predicted positions
        pred = []
        for t in self.tracks:
            dt = tick - t.last
            pred.append((t.x + t.vx*dt, t.y + t.vy*dt, cfg.gate + cfg.gate_v*dt))
        pairs = []
        pool = self.tracks + self.memory
        for j, t in enumerate(pool):
            if j < len(self.tracks):
                px, py, r = pred[j]
            else:
                dt = tick - t.last
                px, py, r = t.x, t.y, cfg.gate + cfg.gate_v*dt
            for i, (e, own, x, y) in enumerate(dets):
                if own != t.own:
                    continue
                d = math.hypot(x - px, y - py)
                if d <= r:
                    pairs.append((d + (cfg.tok_cost if e[0] != t.cur else 0.), i, j))
        pairs.sort()
        used_d, used_t, match = set(), set(), {}
        for c, i, j in pairs:
            if i in used_d or j in used_t:
                continue
            used_d.add(i); used_t.add(j); match[j] = i
        revived = []
        for j, t in enumerate(pool):
            if j in match:
                e, own, x, y = dets[match[j]]
                dt = max(1, tick - t.last)
                vx, vy = (x - t.x)/dt, (y - t.y)/dt
                sp = math.hypot(vx, vy)
                if sp > cfg.vmax:
                    vx, vy = vx*cfg.vmax/sp, vy*cfg.vmax/sp
                t.vx, t.vy = .5*(t.vx + vx), .5*(t.vy + vy)
                t.x, t.y, t.last, t.hits, t.miss = x, y, tick, t.hits + 1, 0
                t.toks.append(e[0])
                if cfg.vote > 0:
                    t.toks = t.toks[-cfg.vote:]
                t.rows[e[0]] = e
                t.cur, t.hp = e[0], float(e[1][9])
                if t.hits >= cfg.conf:
                    t.confirmed = True
                if j >= len(self.tracks):
                    revived.append(t)
                    self.stats['revived'] += 1
            elif j < len(self.tracks):
                t.miss += 1
        self.memory = [t for j, t in enumerate(self.memory, len(self.tracks)) if j not in match]
        self.tracks += revived
        # new tracks: isolated ones (no output-able track of that owner within iso) are confirmed at birth
        out_now = [t for t in self.tracks if t.confirmed and t.miss == 0]
        for i, (e, own, x, y) in enumerate(dets):
            if i in used_d:
                continue
            t = _Track(own, x, y, tick, e[0], e)
            if cfg.conf <= 1 or (cfg.iso > 0 and not any(
                    o.own == own and math.hypot(o.x - x, o.y - y) <= cfg.iso for o in out_now)):
                t.confirmed = True
            elif cfg.ev and any(po == own and 0 <= tick - pt <= cfg.ev and math.hypot(px - x, py - y) <= cfg.ev_r
                                for po, px, py, pt in plays):
                t.confirmed = True
                self.stats['ev_confirmed'] += 1
            else:
                self.stats['held'] += 1
            self.tracks.append(t)
        # expire
        alive = []
        for t in self.tracks:
            limit = cfg.coast if (cfg.coast_low < 0 or t.hp >= cfg.low_hp) else cfg.coast_low
            if not t.confirmed:
                if t.miss == 0:
                    alive.append(t)                 # tentative: must be re-detected on the next poll
                continue
            if t.miss <= max(limit, 0):
                alive.append(t)
            else:
                self.memory.append(t)
        self.tracks = alive
        self.memory = [t for t in self.memory if (tick - t.last) <= 5*cfg.memory]
        # output
        out = list(keep)
        for t in self.tracks:
            if not t.confirmed:
                continue
            tok = Counter(t.toks).most_common(1)[0][0] if cfg.vote > 1 else t.cur
            if tok not in t.rows:
                tok = t.cur
            base = t.rows[tok]
            row = t.rows[t.cur][1].copy() if tok == t.cur else base[1].copy()
            if tok != t.cur:
                self.stats['voted'] += 1
                cur = t.rows[t.cur][1]
                row[0], row[1], row[9] = cur[0], cur[1], cur[9]
                row[27], row[28] = cur[27], cur[28]
            if t.miss:
                dt = tick - t.last
                row[0] = np.clip((t.x + cfg.damp*t.vx*dt)/BOARD_W, 0., 1.)
                row[1] = np.clip((t.y + cfg.damp*t.vy*dt)/BOARD_H, 0., 1.)
                self.stats['coasted'] += 1
            out.append((tok, row) + tuple(base[2:]))
        self.stats['polls'] += 1
        return out
