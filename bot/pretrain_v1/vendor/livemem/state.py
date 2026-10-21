"""Memory frame (native/memreader.c line) -> the perception record bot/live/translate.py consumes (LIVE, memory route).

Fair information (Sam 2026-10-17/18): the bot gets only what ClashAI and/or Hasty-CR feed their bots: unit positions,
types and sides, tower HP, OUR hand, next card and elixir, the clock. The reader never reads the opponent's hand, next
card or elixir (native/memreader.c; test_fairinfo.py proves it on a logged fake process); this module accepts ONLY the
reader's frame keys and emits ONLY the record keys below, so nothing else can reach the bot even if a reader changed.
Field adjudication (one-bot fields): reports/live/memory-route/FIELD-PARITY.md "our use" column.

Frame:  {"t": tick, "b": battle token, "s": our side, "e": our elixir raw, "h": [4 deck indices], "n": next deck index,
         "u": [[id, side, x, y, card id, hp, max hp, "character name"], ...], "m": rows skipped}  (world units, 1000/tile)
Record: tick, units [{card, class, cls, owner, x, y[, hp_frac]}], towers [{owner, kind, side, hp_frac, alive}],
        hand {cards, next}, elixir, events (only opponent spell plays, and only with spell_events=True).
Coordinates: screen tiles, x from the screen's left 0..18, y from OUR edge 0..32 (canvas.tile_to_android's frame).

Identity: a unit's card is its creating card's native id (cards.json, the 122-card pool); an evolved or hero body
carries its own native id, so its card comes from the character name: the form suffix (_EV<n>, Hero) is stripped and
the base body is looked up in the cards' body lists (own units: only our deck's cards). The body class passed on is the
BASE body (our engines model forms as their base). Names that are neither a crown tower nor a known troop/building body
(projectiles, containers, spell areas) are not units. Every policy is counted in `stats`.
"""
from __future__ import annotations

from collections import Counter
import json
import re
from pathlib import Path

FRAME_KEYS = frozenset({'t', 'b', 's', 'e', 'h', 'n', 'u', 'p', 'm'})      # private (authorized) frame
PUBLIC_KEYS = frozenset({'t', 'b', 'sides', 'u', 'p', 'm'})                # public frame
UNIT_ARITY = 8
RECORD_KEYS = frozenset({'tick', 'units', 'towers', 'hand', 'elixir', 'events'})
UNIT_KEYS = frozenset({'card', 'class', 'cls', 'owner', 'x', 'y', 'hp_frac'})
TOWER_KEYS = frozenset({'owner', 'kind', 'side', 'hp_frac', 'alive'})
EVENT_KEYS = frozenset({'owner', 'card', 'x', 'y', 'tick', 'derived'})
FORM = re.compile(r'^(?P<base>[A-Za-z0-9]+?)(?:_EV\d+|Hero)$')
TOWER_X = (3500, 9000, 14500)
TOWER_Y = (3000, 6500, 25500, 29000)   # world rows of king / princess towers at either end
TOWER_SLACK = 1500        # world units: a crown tower's x is within this of its column
GONE_FRAMES = 20          # a seen crown tower absent from this many COMPLETE frames (m == 0) in a row is destroyed
STALE_FRAMES = 40         # ... absent this many frames in a row while frames were incomplete: state unknown (stale)


class FrameError(ValueError):
    """A reader line that is not exactly the reader's frame schema; never reaches the bot."""


def collapse_identical(f):
    """Validate duplicate IDs in parsed public/private rows without mutating the raw frame.

    Keep the first wholly identical row in each table; conflicting rows always refuse.
    Return the unique frame and removed-row counts only after BOTH tables validate.
    """
    unique, duplicates = {}, {}
    for table, source in (('u', f['u']), ('p', f.get('p', ()))):
        seen, rows, count = {}, [], 0
        for row in source:
            uid = row[0]
            if uid in seen:
                prior = seen[uid]
                if row != prior or any(type(a) is not type(b) for a, b in zip(row, prior)):
                    raise FrameError('duplicate reader id (hash collision or registry corruption)')
                count += 1
            else:
                seen[uid] = row
                rows.append(row)
        unique[table], duplicates[table] = rows, count
    return (dict(f, **unique) if any(duplicates.values()) else f), duplicates


def parse_line(line):
    """Reader stdout line -> (kind, dict): kind 'none' {"t":-1}, 'err' {"t","err"}, 'public' or 'private' frames, or
    'fatal' {"fatal"}. Anything else, an extra key or an out-of-range value -> FrameError (never reaches the bot)."""
    f = json.loads(line)
    if not isinstance(f, dict):
        raise FrameError('not a frame')
    if set(f) == {'fatal'} and isinstance(f['fatal'], str):
        return 'fatal', f
    if not isinstance(f.get('t'), int):
        raise FrameError('not a frame')
    if f['t'] < 0:
        if set(f) != {'t'}:
            raise FrameError('no-battle frame with extra keys')
        return 'none', f
    if 'err' in f:
        if set(f) != {'t', 'err'} or not isinstance(f['err'], str):
            raise FrameError('refusal frame with extra keys')
        return 'err', f
    keys = set(f)
    if keys == PUBLIC_KEYS:
        kind = 'public'
        if not (isinstance(f['sides'], list) and len(f['sides']) == 2 and all(isinstance(v, int) for v in f['sides'])):
            raise FrameError('sides')
    elif keys == FRAME_KEYS:
        kind = 'private'
        if f['s'] not in (0, 1) or not isinstance(f['e'], int) or not 0 <= f['e'] <= 100000:
            raise FrameError('side/elixir out of range')
        h, n = f['h'], f['n']
        if (not isinstance(h, list) or len(h) != 4 or len(set(h)) != 4
                or not all(isinstance(i, int) and 0 <= i <= 7 for i in h) or not isinstance(n, int) or not 0 <= n <= 7):
            raise FrameError('hand/next out of range')
    else:
        raise FrameError(f'frame keys {sorted(keys)} are not a reader schema')
    if not isinstance(f['b'], int) or not 0 < f['b'] < 1 << 52 or not isinstance(f['m'], int) or f['m'] < 0:
        raise FrameError('battle token / misses')
    if not isinstance(f['u'], list):
        raise FrameError('units')
    for u in f['u']:
        if (not isinstance(u, list) or len(u) != UNIT_ARITY or not all(isinstance(v, int) for v in u[:7])
                or not isinstance(u[7], str)):
            raise FrameError('unit row is not [id, side, x, y, card, hp, max_hp, name]')
    if not isinstance(f['p'], list) or not all(isinstance(q, list) and len(q) == 3 and all(isinstance(v, int) for v in q)
                                               for q in f['p']):
        raise FrameError('projectile row is not [id, target_x, target_y]')
    return kind, f


ALIASES = Path(__file__).resolve().parent/'data'/'card-aliases.json'


def load_cards(path, aliases=ALIASES):
    """cards.json (live/nulls/cards.json: name, native id, kind, bodies) -> (id -> card, card -> row), card names in the
    bot's spelling (data/card-aliases.json)."""
    alias = json.loads(Path(aliases).read_text())['aliases'] if aliases else {}
    rows = [dict(r, name=alias.get(r['name'], r['name'])) for r in json.loads(Path(path).read_text())]
    if len({r['name'] for r in rows}) != len(rows) or len({int(r['id']) for r in rows}) != len(rows):
        raise ValueError('cards: duplicate names or ids after aliasing')
    return {int(r['id']): r['name'] for r in rows}, {r['name']: r for r in rows}


class FrameBuilder:
    """One per battle. frame(f) -> record (or None for a frame that cannot be oriented yet)."""

    def __init__(self, binding, deck_order, cards_path, *, extra_bodies=(), spell_events=False, stats=None):
        if len(deck_order) != 8 or len(set(deck_order)) != 8:
            raise ValueError('deck_order: 8 distinct cards')
        self.b, self.deck_order, self.deck = binding, list(deck_order), set(deck_order)
        self.by_id, self.card_rows = load_cards(cards_path)
        unknown = self.deck - set(self.card_rows)
        if unknown:
            raise ValueError(f'deck cards not in cards.json: {sorted(unknown)}')
        self.bodies = {}
        for name, r in self.card_rows.items():
            for k, body in enumerate(r.get('bodies') or ()):
                self.bodies.setdefault(body, []).append((k, name))
        self.known_bodies = set(self.bodies) | set(extra_bodies) | {'Goblin'}  # canonical BarrelGoblin target
        self.spell_events = spell_events
        self.stats = Counter() if stats is None else stats
        self.end = None                   # 'low' | 'high': which world end our king stands at
        self.towers_seen = {}             # (owner, kind, side) -> last hp_frac
        self.towers_missing = {}          # (owner, kind, side) -> consecutive COMPLETE frames absent
        self.towers_unseen = {}           # (owner, kind, side) -> consecutive frames absent (complete or not)
        self.tower_ids = {}               # reader id -> (owner, kind, side): a classified tower stays that tower
        self.stale = None                 # a tower key whose state is unknown for STALE_FRAMES (gate disarms)
        self.hp_unknown = {}              # (owner, kind, side) -> consecutive frames present with unreadable HP
        self.frame_ids = set()            # every reader id of the last frame (control data for the gate)
        self.proj = {}                    # non-body entity id -> [first tick, card, owner, world target or None, stable]
        self.spells = []                  # in-flight spell carriers of the last frame (RF extras; never in a record):
                                          # (owner, card, x, y, aim_x, aim_y, flown) in screen tiles / ticks
        self.hp_seen = set()              # tower keys with at least one readable HP this battle
        self.others = []                  # last frame's non-unit, non-tower entities (projectiles, spells, effects):
                                          # [id, owner, card, name, x, y] in screen tiles; LOGGED ONLY, never in a record
        self.unit_ids = []                # reader ids of the last record's units (control data: never in a record)
        self.first_seen = {}              # reader id -> [first tick, last tick, card, owner] of its current lifetime
        self.unit_first_seen = []         # first-seen tick of each unit of the last record (aligned with unit_ids)
        self.spells_seen = set()
        self.ids_seen = set()
        self.last_tick = None

    # -- identity --------------------------------------------------------------------------------
    def base_body(self, name):
        m = FORM.match(name)
        if m and m['base'] in self.known_bodies:
            return m['base'], True
        return name, False

    def observed_body(self, name, card_id):
        # Native landed BarrelGoblin is an engine Goblin, only with verified source provenance.
        # No alias to the separately playable Goblins card, evolved names, carriers or dummies.
        if name == 'BarrelGoblin' and self.by_id.get(card_id) == 'GoblinBarrel':
            return 'Goblin', False
        return self.base_body(name)

    def card_of(self, card_id, base, own):
        name = self.by_id.get(card_id)
        if name is not None:
            return name
        cands = sorted(self.bodies.get(base, ()))           # (body index, card): primary body first
        if own:
            cands = [c for c in cands if c[1] in self.deck]
        if not cands:
            self.stats[f'form_unmapped:{card_id}:{base}'] += 1
            return None
        self.stats[f'form_card:{card_id}:{base}->{cands[0][1]}'] += 1
        return cands[0][1]

    def tower_kind(self, name, card_id, x):
        if card_id in self.by_id:
            return None                                       # a playable card's body (BombTower, InfernoTower)
        kind = ('king' if name in self.b.tower_names['king'] else
                'princess' if name in self.b.tower_names['princess'] else None)
        if kind is None:
            return None
        col = TOWER_X[1] if kind == 'king' else min(TOWER_X[0], TOWER_X[2], key=lambda c: abs(c - x))
        return kind if abs(x - col) <= TOWER_SLACK else None

    def known_tower(self, uid, name, card_id, x, y, *, projectile=False):
        """Keep a cached tower only with compatible identity and geometry. A category-confirmed projectile or
        another named non-body retires the id without confirming destruction: ordinary missing/stale rules apply.
        Known troop/building reuse retains its existing destruction rule; genuine tower movement still refuses."""
        key = self.tower_ids.get(uid)
        if key is None:
            return None
        kind = key[1]
        tower_name = name in self.b.tower_names['king'] or name in self.b.tower_names['princess']
        waking = kind == 'king' and any(name == n + 'Awake' for n in self.b.tower_names['king'])
        named_body = bool(name) and self.observed_body(name, card_id)[0] in self.known_bodies
        if projectile or (name and not tower_name and not waking and not named_body):
            del self.tower_ids[uid]
            self.stats['tower_id_retired_nonbody'] += 1
            return None                           # no HP / death inferred from a non-body's reused hash
        body = card_id in self.by_id or (named_body and not tower_name and not waking)
        if body:
            # The address now holds a troop / building (a playable card id or a known body name): the tower's object
            # was freed and its memory reused, so the tower is DESTROYED and the row is a new unit (ladder session 1
            # battle 3: the opponent's left princess at 3.5% vanished, then its id came back as another entity).
            del self.tower_ids[uid]
            self.towers_seen[key] = 0.
            self.towers_missing[key] = GONE_FRAMES
            self.stats['tower_address_reused'] += 1
            return None
        if not (min(abs(x - c) for c in TOWER_X) <= TOWER_SLACK and min(abs(y - r) for r in TOWER_Y) <= TOWER_SLACK):
            self.stats['tower_id_contradicted'] += 1
            raise FrameError(f'a crown tower id moved off the tower slots (card {card_id}, name {name!r})')
        if name and name not in self.b.tower_names[kind]:
            self.stats[f'tower_name_seen:{kind}:{name}'] += 1    # e.g. a waking king: still that tower
        return kind

    def decided(self, tick, regular_ticks=3600, end_ticks=6000):
        """The battle is decided (no further input may matter): a king is down, or the clock is past regulation with
        unequal crowns (overtime ends on the first crown), or past the end of overtime. Only CONFIRMED destruction
        counts (explicit 0 HP, or gone from GONE_FRAMES complete frames): a single missed row must never end live
        play (review r12). After the real end the battle tick freezes and no new decision is made."""
        down = {k for k, f in self.towers_seen.items() if f <= 0}
        if any(k[1] == 'king' for k in down):
            return True
        ours = sum(1 for k in down if k[0] == 1)
        theirs = sum(1 for k in down if k[0] == 0)
        return (tick >= regular_ticks and ours != theirs) or tick >= end_ticks

    def all_hp_known(self):
        """Every crown tower seen this battle has had a readable HP at least once (the gate arms only then)."""
        return bool(self.towers_seen) and set(self.towers_seen) <= self.hp_seen

    # -- geometry --------------------------------------------------------------------------------
    def screen(self, x, y):
        t = self.b.tile
        sx = x/t
        if self.b.screen_x_flip[self.end]:
            sx = self.b.world_w/t - sx
        sy = y/t if self.end == 'low' else (self.b.world_h - y)/t
        return sx, sy

    # -- frame -----------------------------------------------------------------------------------
    def frame(self, f):
        side, tick = f['s'], f['t']
        # Standalone consumers retain the same check; ingest-normalized frames contribute zero.
        f, duplicates = collapse_identical(f)
        for table, count in duplicates.items():
            if count:
                self.stats[f'dup_identical:{table}'] += count
        targets = {q[0]: (q[1], q[2]) for q in f.get('p', ())}
        towers = []
        for u in f['u']:
            uid, s, x, y, card, hp, mx, name = u
            projectile = uid in targets           # p rows exist only for the reader's projectile category
            kind = self.known_tower(uid, name, card, x, y, projectile=projectile)
            if not projectile:
                kind = kind or self.tower_kind(name, card, x)
            if kind is not None and min(abs(y - r) for r in TOWER_Y) <= TOWER_SLACK:
                towers.append((kind, s, x, y, hp, mx, uid))
        kings = [t for t in towers if t[0] == 'king' and t[1] == side]
        if kings:
            end = 'low' if kings[0][3] < self.b.world_h/2 else 'high'
            if self.end is not None and end != self.end:
                self.stats['orientation_flip'] += 1
                raise FrameError('our king changed ends mid-battle')
            self.end = end
        if self.end is None:
            self.stats['frames_unoriented'] += 1
            return None
        out_towers, present = [], set()
        for kind, s, x, y, hp, mx, uid in towers:
            owner = 0 if s == side else 1
            sx, _ = self.screen(x, y)
            tside = None if kind == 'king' else ('left' if sx < 9 else 'right')
            key = (owner, kind, tside)
            if self.tower_ids.setdefault(uid, key) != key:
                self.stats['tower_id_moved'] += 1
                raise FrameError('a crown tower entity changed slot')
            if key in present:
                self.stats['tower_duplicate'] += 1
                continue
            present.add(key)
            if hp >= 0 and mx > 0:
                frac, self.hp_unknown[key] = hp/mx, 0
                self.hp_seen.add(key)
            else:                                  # unreadable HP: keep the last reading, stale after STALE_FRAMES
                frac = self.towers_seen.get(key)
                self.hp_unknown[key] = self.hp_unknown.get(key, 0) + 1
                self.stats['tower_hp_unknown'] += 1
                if frac is None:
                    frac = 1.                      # never read yet: alive, but not known (all_hp_known() False)
            frac = min(1., max(0., frac))
            self.towers_seen[key] = frac
            out_towers.append(dict(owner=owner, kind=kind, side=tside, hp_frac=frac, alive=frac > 0))
        complete = f['m'] == 0
        self.stale = next((k for k, n in self.hp_unknown.items() if n >= STALE_FRAMES and k in present), None)
        for key in self.towers_seen:
            if key in present:
                self.towers_missing[key] = self.towers_unseen[key] = 0
                continue
            owner, kind, tside = key
            self.towers_unseen[key] = self.towers_unseen.get(key, 0) + 1
            if complete:
                self.towers_missing[key] = self.towers_missing.get(key, 0) + 1
            if self.towers_missing.get(key, 0) >= GONE_FRAMES:
                self.towers_seen[key] = 0.         # gone from complete registries: destroyed (a princess leaves it)
                for i in [i for i, k in self.tower_ids.items() if k == key]:
                    del self.tower_ids[i]          # its id is retired: a reused address is a new entity
            elif self.towers_seen[key] > 0:
                self.stats['tower_row_missed'] += 1
                if self.towers_unseen[key] >= STALE_FRAMES:
                    self.stale = key
            frac = self.towers_seen[key]
            out_towers.append(dict(owner=owner, kind=kind, side=tside, hp_frac=frac, alive=frac > 0))
        units, events, ids, others = [], [], [], []
        spells = []
        for u in f['u']:
            uid, s, x, y, card, hp, mx, name = u
            owner = 0 if s == side else 1
            body = uid not in targets and (uid in self.tower_ids or self.tower_kind(name, card, x) is not None
                    or bool(name) and self.observed_body(name, card)[0] in self.known_bodies)
            life = self.proj.get(uid)
            if life is not None and (body or life[1] != card or life[2] != owner):
                del self.proj[uid]                 # the address now holds another entity: that lifetime ended
            if uid not in targets and (uid in self.tower_ids or self.tower_kind(name, card, x) is not None):
                continue
            if not body:
                sx, sy = self.screen(x, y)
                row_o = [uid, owner, self.by_id.get(card, card), name, round(sx, 3), round(sy, 3)]
                # the projectile's in-flight target: kept only while sane (on the board, unchanged for the entity's
                # whole visible lifetime); flight age counts from the entity's first sight. A frame without its
                # target (metadata read gap) keeps the lifetime and its verdict but emits nothing.
                life = self.proj.get(uid)
                if life is None:
                    life = self.proj[uid] = [tick, card, owner, None, True]
                tgt = targets.get(uid)
                if tgt is not None:
                    on_board = 0 <= tgt[0] <= self.b.world_w and 0 <= tgt[1] <= self.b.world_h
                    if life[3] is None:
                        life[3] = tgt
                    life[4] = life[4] and on_board and tgt == life[3]
                    if life[4]:
                        ax, ay = self.screen(*tgt)
                        row_o += [round(ax, 3), round(ay, 3)]
                        cname = self.by_id.get(card)
                        if cname is not None and name != 'GoblinBarrelSpell_EV1_Decoy':
                            spells.append((owner, cname, sx, sy, ax, ay, tick - life[0]))
                    else:
                        self.stats['projectile_target_unstable'] += 1
                others.append(row_o)
            if not name:
                spell = self.by_id.get(card)
                if (self.spell_events and owner == 1 and spell is not None and uid not in self.spells_seen
                        and self.card_rows[spell].get('kind') == 'spell'):
                    sx, sy = self.screen(x, y)
                    events.append(dict(owner=1, card=spell, x=sx, y=sy, tick=tick, derived=True))
                    self.stats['opp_spell_events'] += 1
                self.spells_seen.add(uid)
                self.stats['nameless_entities'] += 1
                continue
            base, form = self.observed_body(name, card)
            if uid in targets or base not in self.known_bodies:
                self.stats[f'not_a_body:{name}'] += 1
                continue
            cname = self.card_of(card, base, owner == 0)
            if cname is None:
                continue
            if form:
                self.stats['form_units'] += 1
            sx, sy = self.screen(x, y)
            row = {'card': cname, 'class': base, 'cls': base, 'owner': owner, 'x': sx, 'y': sy}
            if hp >= 0 and mx > 0:
                row['hp_frac'] = min(1., max(0., hp/mx))
            units.append(row)
            ids.append(uid)
        self.unit_ids = ids
        self.others = others
        self.spells = spells
        self.frame_ids = {u[0] for u in f['u']}
        for uid in [i for i in self.proj if i not in self.frame_ids] if f['m'] == 0 else ():
            del self.proj[uid]                     # gone from a complete frame: that lifetime ended
        if len(self.proj) > 2048:                  # long runs of incomplete frames: bound the table
            for uid in [i for i in self.proj if i not in self.frame_ids]:
                del self.proj[uid]
        # public age tracking (RF extras, rfextras.py): the tick each unit was first SEEN (its appearance is public);
        # a lifetime ends when the id is absent from a complete frame or comes back with another card / owner
        for uid in [i for i in self.first_seen if i not in self.frame_ids] if f['m'] == 0 else ():
            del self.first_seen[uid]
        firsts = []
        for uid, u in zip(ids, units):
            life = self.first_seen.get(uid)
            if life is None or life[2] != u['card'] or life[3] != u['owner']:
                life = self.first_seen[uid] = [tick, tick, u['card'], u['owner']]
            life[1] = tick
            firsts.append(life[0])
        self.unit_first_seen = firsts
        self.last_tick = tick
        hand = [self.deck_order[i] for i in f['h']]
        rec = dict(tick=tick, units=units, towers=out_towers,
                   hand=dict(cards=hand, next=self.deck_order[f['n']]),
                   elixir=f['e']/self.b.elixir_unit, events=events)
        check_record(rec)
        return rec


def check_record(rec):
    """The record carries only allow-listed keys (fair-information boundary between the reader and the bot)."""
    if set(rec) - RECORD_KEYS:
        raise FrameError(f'record keys outside the allow-list: {sorted(set(rec) - RECORD_KEYS)}')
    for u in rec['units']:
        if set(u) - UNIT_KEYS:
            raise FrameError('unit keys outside the allow-list')
    for t in rec['towers']:
        if set(t) != TOWER_KEYS:
            raise FrameError('tower keys outside the allow-list')
    for e in rec['events']:
        if set(e) != EVENT_KEYS or e['owner'] != 1:
            raise FrameError('event keys outside the allow-list')
    if set(rec['hand']) != {'cards', 'next'} or len(rec['hand']['cards']) != 4:
        raise FrameError('hand outside the allow-list')
    return rec


def crowns(rec):
    """(our crowns, their crowns) from a record's towers: a destroyed king is 3 crowns."""
    t = {(x['owner'], x['kind'], x['side']): x['alive'] for x in rec['towers']}
    def against(o):
        if t.get((o, 'king', None)) is False:
            return 3
        return sum(t.get((o, 'princess', s)) is False for s in ('left', 'right'))
    return against(1), against(0)
