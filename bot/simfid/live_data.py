"""LIVE memory recordings -> public game timelines for the engine-fidelity harness (simfid, exploration).

Input: one retained live-memory game directory (/mpac/sdicks02/scratch/live-mem/mirror/mem-c*/m*), read-only:
  records.jsonl      sampled public record (~5 ticks): units {card, class, owner, x, y, hp_frac}, towers, own hand/elixir.
                     OUR frame (our king at the bottom, y=0 at our edge); owner 0 = us, 1 = opponent.
  projectiles.jsonl  public projectiles/spell carriers [id, owner, ?, name, x, y(, dest_x, dest_y)] per tick.
  decisions.jsonl    our own decisions: submitted actions (slot*576 + row*18 + col, our frame).
  events.jsonl       our own tap_landed confirmations (card, tick), match_start/end, reader errors.
  session.json       result (crowns, ticks) and the confirmed native seat.

Fair information. Only public observations and our own commands are used:
- our plays: our own submitted, landed commands (card, tap tile from the decision action, landing tick);
- opponent plays: DERIVED from public births (new opponent bodies; one play per deployment cluster) and from public
  spell carriers (FireballSpell, ArrowsSpell, ...: first sighting + public destination). Opponent instant spells with
  no public carrier (Zap, Log, Earthquake, ...) are invisible here; segments are not filtered on them (see REPORT).
- levels: ours from the account (exact). The opponent's crown-tower level and card levels are inferred from the
  public HP fractions (the client shows tower HP numbers and unit level badges): the level whose max HP makes every
  observed fraction an integer HP. Unresolved card levels fall back to the median of the opponent's resolved
  levels, then its tower level, and are counted. These levels configure the simulation only; no policy sees them.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

MIRROR = Path('/mpac/sdicks02/scratch/live-mem/mirror')
ACCOUNT_LEVELS = Path('/mpac/sdicks02/scratch/barrelgoblin-fix-20261020-stageA3/base/account-levels.json')
HOG26 = ('Skeletons', 'Musketeer', 'IceGolem', 'Cannon', 'Fireball', 'Zap', 'IceSpirit', 'HogRider')
OWN_TOWER_LEVEL = 9

# Public spell carriers -> card, for opponent spell plays (first sighting with a public destination).
CARRIER_CARD = {
    'FireballSpell': 'Fireball', 'ArrowsSpell': 'Arrows', 'RocketSpell': 'Rocket', 'GoblinBarrelSpell': 'GoblinBarrel',
    'SnowballSpell': 'Snowball', 'PoisonSpell': 'Poison', 'LightningSpell': 'Lightning',
}
# Cards whose bodies arrive by a carrier or a roll (the play is not at the bodies' first sighting).
CARRIED_BODIES = {'GoblinBarrel', 'BarbLog', 'Graveyard', 'RoyalDelivery', 'GoblinDrill', 'Miner', 'GoblinCurse'}
TICK_GAP = 30          # a record gap larger than this ends a segment (reader stall / discontinuity)
MAX_SPEED = 0.16       # tiles per tick (fastest charge ~3 tiles/s)


@dataclass
class Unit:
    card: str
    cls: str
    owner: int
    x: float
    y: float
    hp: float          # hp fraction


@dataclass
class Record:
    tick: int
    units: list
    towers: dict       # (owner, kind, side) -> (hp_frac, alive)
    hand: list
    next: str | None
    elixir: float | None


@dataclass
class Play:
    side: int          # 0 us, 1 opponent
    card: str
    tick: int          # best estimate of the native execution tick
    x: float           # our frame, tiles
    y: float
    source: str        # 'own' | 'birth' | 'carrier'
    certain: bool = True
    first_seen: int | None = None
    prev_sample: int | None = None


@dataclass
class Game:
    name: str
    deck: list
    levels: dict
    records: list
    plays: list
    end_tick: int
    crowns: tuple | None
    opp_levels: dict = field(default_factory=dict)
    opp_tower_level: int | None = None
    level_notes: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    form_cards: set = field(default_factory=set)   # opponent cards seen in an evolution/hero form this game
    dropouts: list = field(default_factory=list)   # record ticks after which every opponent body vanished at once


def _jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.open():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def load_records(d: Path) -> list[Record]:
    recs = []
    last = -1
    for r in _jsonl(d / 'records.jsonl'):
        t = int(r['tick'])
        if t <= last:
            continue
        last = t
        units = [Unit(u['card'], u.get('class') or u.get('cls'), int(u['owner']), float(u['x']), float(u['y']),
                      float(u['hp_frac']) if u.get('hp_frac') is not None else math.nan) for u in r['units']]
        towers = {(int(w['owner']), w['kind'], w.get('side')): (w.get('hp_frac'), bool(w.get('alive')))
                  for w in r['towers']}
        hand = r.get('hand') or {}
        recs.append(Record(t, units, towers, list(hand.get('cards') or []), hand.get('next'), r.get('elixir')))
    return recs


def own_plays(d: Path) -> tuple[list[Play], list]:
    """Our landed commands: decision (card, tile) paired in order with the tap_landed confirmations."""
    subs = [x for x in _jsonl(d / 'decisions.jsonl')
            if x.get('submitted') and x.get('tap') is None and x.get('card') and x.get('action', 2304) < 2304]
    landed = [e for e in _jsonl(d / 'events.jsonl') if e.get('ev') == 'tap_landed']
    plays, errors = [], []
    si = 0
    for e in landed:
        while si < len(subs) and not (subs[si]['card'] == e['card'] and subs[si]['tick'] <= e['tick']):
            errors.append(('unlanded_submission', subs[si]['tick'], subs[si]['card']))
            si += 1
        if si >= len(subs):
            errors.append(('landing_without_submission', e['tick'], e['card']))
            continue
        s = subs[si]
        si += 1
        a = int(s['action']) % 576
        row, col = divmod(a, 18)
        plays.append(Play(0, e['card'], int(e['tick']), col + .5, row + .5, 'own', first_seen=int(e['tick'])))
    return plays, errors


class Tracker:
    """Frame-to-frame public body tracks per (owner, card, class); unmatched bodies are births."""

    def __init__(self):
        self.tracks = []   # dict(owner, card, cls, x, y, first, last)

    def update(self, rec: Record, prev_tick: int | None):
        dt = rec.tick - prev_tick if prev_tick is not None else 0
        live = [t for t in self.tracks if prev_tick is not None and t['last'] >= prev_tick - TICK_GAP]
        by = defaultdict(list)
        for t in live:
            by[t['owner'], t['card'], t['cls']].append(t)
        births = []
        for u in rec.units:
            cands = by.get((u.owner, u.card, u.cls), [])
            best, bd = None, 1e9
            for t in cands:
                if t['last'] == rec.tick:
                    continue
                gap = rec.tick - t['last']
                d = math.hypot(u.x - t['x'], u.y - t['y'])
                if d <= MAX_SPEED * gap + 0.75 and d < bd:
                    best, bd = t, d
            if best is None:
                t = dict(owner=u.owner, card=u.card, cls=u.cls, x=u.x, y=u.y, first=rec.tick, last=rec.tick,
                         x0=u.x, y0=u.y)
                self.tracks.append(t)
                births.append(t)
            else:
                best.update(x=u.x, y=u.y, last=rec.tick)
        return births

    def alive_near(self, owner, card, x, y, tick, radius, classes=None, before=None):
        for t in self.tracks:
            if t['owner'] != owner or t['card'] != card or t['last'] < tick - TICK_GAP:
                continue
            if before is not None and t['first'] >= before:
                continue
            if classes is not None and t['cls'] not in classes:
                continue
            if math.hypot(t['x'] - x, t['y'] - y) <= radius:
                return True
        return False


def birth_clusters(records: list[Record], owner: int):
    """-> [dict(card, tick(first seen), prev_sample, bodies=[track...])] for `owner`'s births."""
    tr = Tracker()
    clusters = []
    prev = None
    for rec in records:
        if prev is not None and rec.tick - prev > TICK_GAP:
            tr = Tracker()     # discontinuity: start over (the first frame after it yields no births)
            prev = None
        births = tr.update(rec, prev)
        if prev is None:
            prev = rec.tick
            continue
        for b in births:
            if b['owner'] != owner:
                continue
            joined = False
            for c in clusters[::-1]:
                if rec.tick - c['tick'] > 10:
                    break
                if c['card'] == b['card'] and \
                        min(math.hypot(b['x'] - o['x0'], b['y'] - o['y0']) for o in c['bodies']) <= 3.0:
                    c['bodies'].append(b)
                    joined = True
                    break
            if not joined:
                fresh = not tr.alive_near(owner, b['card'], b['x'], b['y'], rec.tick, 99., before=rec.tick)
                fresh_near = not tr.alive_near(owner, b['card'], b['x'], b['y'], rec.tick, 6., before=rec.tick)
                clusters.append(dict(card=b['card'], tick=rec.tick, prev_sample=prev, bodies=[b], fresh=fresh,
                                     fresh_near=fresh_near))
        prev = rec.tick
    return clusters


def main_classes(games_records, min_share=.5):
    """card -> the body classes present at the first sighting of a definitely fresh deployment (no body of that
    card alive anywhere), in >= min_share of them. Empirical, from public births only."""
    seen = defaultdict(lambda: defaultdict(int))
    total = defaultdict(int)
    for recs in games_records:
        for owner in (0, 1):
            for c in birth_clusters(recs, owner):
                if not c['fresh']:
                    continue
                total[c['card']] += 1
                for cls in {b['cls'] for b in c['bodies'] if b['first'] == c['tick']}:
                    seen[c['card']][cls] += 1
    return {card: sorted(cls for cls, n in seen[card].items() if n >= min_share * total[card]) for card in total}


def opponent_plays(records, projectile_rows, mains):
    plays = []
    for c in birth_clusters(records, 1):
        card = c['card']
        if card in CARRIED_BODIES:
            continue
        main = set(mains.get(card) or [])
        bodies = [b for b in c['bodies'] if b['cls'] in main] if main else c['bodies']
        if not bodies:
            continue              # child bodies only: spawns, death spawns
        if not (c['fresh'] or c['fresh_near']):
            continue              # a main body next to a live one of the same card: re-detection, not a play
        x = sum(b['x0'] for b in bodies) / len(bodies)
        y = sum(b['y0'] for b in bodies) / len(bodies)
        tick = (c['prev_sample'] + c['tick']) // 2
        plays.append(Play(1, card, tick, x, y, 'birth', certain=c['fresh'], first_seen=c['tick'],
                          prev_sample=c['prev_sample']))
    seen = set()
    prev_tick = None
    for row in projectile_rows:
        t = int(row['tick'])
        for o in row['o']:
            pid, owner, name = o[0], int(o[1]), o[3]
            card = CARRIER_CARD.get(name)
            if owner != 1 or card is None or pid in seen:
                continue
            seen.add(pid)
            if len(o) < 8:
                plays.append(Play(1, card, t - 1, float(o[4]), float(o[5]), 'carrier', certain=False, first_seen=t))
                continue
            plays.append(Play(1, card, t - 1, float(o[6]), float(o[7]), 'carrier', first_seen=t, prev_sample=prev_tick))
        prev_tick = t
    plays.sort(key=lambda p: (p.tick, p.card))
    return plays


def _is_int(v, tol=1e-6):
    return abs(v - round(v)) <= tol * max(1., abs(v))


def infer_level(fracs, max_hp_by_level):
    """fracs: observed hp fractions < 1; max_hp_by_level: {level: [max hp candidates]} -> (level | None, n_fit, n)."""
    fracs = [f for f in fracs if f is not None and not math.isnan(f) and 0 < f < 1]
    if not fracs:
        return None, 0, 0
    best, best_n = None, -1
    for L, maxes in sorted(max_hp_by_level.items()):
        n = sum(any(_is_int(f * m) for m in maxes) for f in fracs)
        if n > best_n:
            best, best_n = L, n
    if best_n < max(1, int(.9 * len(fracs))):
        return None, best_n, len(fracs)
    return best, best_n, len(fracs)


def load_game(d: Path, mains: dict | None = None) -> Game:
    d = Path(d)
    cfg = json.loads((d.parent / 'session-config.json').read_text())
    deck = list(cfg.get('deck_order') or [])
    sess = json.loads((d / 'session.json').read_text()) if (d / 'session.json').exists() else {}
    acc = json.loads(ACCOUNT_LEVELS.read_text())
    levels = None
    if tuple(deck) == HOG26 and tuple(acc['deck_order']) == HOG26:
        levels = dict(acc['effective_levels'])
    records = load_records(d)
    plays, errors = own_plays(d)
    if mains is not None:
        plays += opponent_plays(records, _jsonl(d / 'projectiles.jsonl'), mains)
    plays.sort(key=lambda p: (p.tick, p.side, p.card))
    end = int(sess.get('ticks') or (records[-1].tick if records else 0))
    # public form identities the record builder saw ('form_card:<id>:<body>-><card>'); the record collapses forms
    forms = {k.rsplit('->', 1)[-1] for k in (sess.get('builder') or {}) if k.startswith('form_card:')}
    return Game(name=str(d.relative_to(MIRROR)) if MIRROR in d.parents else str(d), deck=deck, levels=levels,
                records=records, plays=plays, end_tick=end,
                crowns=tuple(sess['crowns']) if sess.get('crowns') else None, errors=errors, form_cards=forms,
                dropouts=mass_dropouts(records))


def mass_dropouts(records):
    """Record ticks a where >= 2 healthy (hp >= .6) opponent bodies and EVERY opponent body vanish by the next
    sample: a projection/reader dropout signature (legitimate simultaneous deaths of full-HP bodies are rare)."""
    out = []
    for a, b in zip(records, records[1:]):
        if b.tick - a.tick > TICK_GAP or any(v.owner == 1 for v in b.units):
            continue
        if sum(u.owner == 1 and u.hp >= .6 for u in a.units) >= 2:
            out.append(a.tick)
    return out


def game_dirs(cohort='hog26'):
    out = []
    for d in sorted(MIRROR.glob('mem-c*/m*')):
        if not (d / 'records.jsonl').exists() or (d / 'records.jsonl').stat().st_size == 0:
            continue
        try:
            cfg = json.loads((d.parent / 'session-config.json').read_text())
        except FileNotFoundError:
            continue
        if cohort == 'hog26' and tuple(cfg.get('deck_order') or ()) != HOG26:
            continue
        out.append(d)
    return out
