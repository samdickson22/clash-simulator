"""pretrain-v1 featurizer: live memory record + public RF extras + bounded causal history -> integer feature arrays.

ONE implementation, imported unchanged by the offline dataset builder (dataset.py), simulator actors and the live bot
(DESIGN.md "One featurizer, three producers"). Pure numpy + stdlib: no torch, engine, reader or runtime import.

Information boundary. The only inputs are
  record   exactly live/mem/state.py RECORD_KEYS {tick, units, towers, hand, elixir, events} with its unit / tower /
           event / hand allow-lists (a logged `poll` key is the one declared logging field and is stripped);
  extras   the public RF facts the deployed FrameBuilder exposes and rfextras.py consumes: `first_seen` (first-seen
           tick of each record unit, aligned with record['units']; builder.unit_first_seen) and `spells` (in-flight
           carriers (owner, card, x, y, aim_x, aim_y, flown); builder.spells, filtered to rfextras.SPELL_CARRIERS).
           Either may be None: missing extras are explicit mask bits, as when the live translator loses them;
  History  this module's bounded state: own commands (submitted / confirmed / rejected, via History.submit/reject
           and hand changes), opponent plays OBSERVED in earlier records, and recent lagged public records.
Anything else raises FeatureError. No field exists through which an opponent hand, next card or elixir, a hidden
timer / target / level, a source label or a future event can enter. Own levels are environment configuration, not
features. Unit ids are never inputs (the record has none); motion comes from public positions in the previous poll.

Output: Features, a dict of small integer numpy arrays (exact, so offline / sim / live parity is byte equality).
Positions are in the record's screen frame (x 0..18 from the screen's left, y 0..32 from OUR edge), quantised to
1/100 tile. Action space (unchanged from the live bot): no-op NOOP=2304, else slot*576 + row*18 + col, tile centre
(col+.5, row+.5).
"""
from __future__ import annotations

from collections import Counter, deque
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np

SCHEMA = 'clasher.pretrain_v1.features.v1'
HERE = Path(__file__).resolve().parent
CATALOG_PATH = HERE/'catalog'/'catalog.json'

# record allow-lists: identical to the deployed live/mem/state.py (sha 9085e337...)
RECORD_KEYS = frozenset({'tick', 'units', 'towers', 'hand', 'elixir', 'events'})
UNIT_KEYS = frozenset({'card', 'class', 'cls', 'owner', 'x', 'y', 'hp_frac'})
TOWER_KEYS = frozenset({'owner', 'kind', 'side', 'hp_frac', 'alive'})
EVENT_KEYS = frozenset({'owner', 'card', 'x', 'y', 'tick', 'derived'})
LOG_KEYS = frozenset({'poll'})                 # declared logging fields, stripped before validation
EXTRA_KEYS = frozenset({'first_seen', 'spells'})

W, H = 18, 32
NTILE = W*H                                    # 576
NOOP = 4*NTILE                                 # 2304
COMMAND_LAG = 27                               # ticks from accepted submission to effect (DESIGN)
POLL = 5                                       # reference cadence, ticks
EXPIRE = 90                                    # an unconfirmed submission expires (LiveSession's default)

MAX_ENT = 256                                  # bodies + carriers; more is a refusal, never a silent drop
MAX_EV = 32                                    # recent public play events (own confirmed + opponent observed)
MAX_OPP = 64                                   # observed opponent play buffer (feeds the revealed-card summary)
MAX_REV = 16                                   # revealed opponent card summary rows
EV_WINDOW = 1200                               # recent-event window, ticks (60 s)
LAGS = (5, 10, 20, 40)                         # previous-record summaries, ticks
HIST_POLLS = 16                                # previous sanitized records kept (covers the 40-tick lag)
AGE_CAP = 1200
XY_Q = 100                                     # positions: 1/100 tile
HP_Q = 1000                                    # hp_frac: 1/1000
EL_Q = 1000                                    # elixir: 1/1000
V_Q = 1000                                     # motion: 1/1000 tile per tick
V_CAP = 2000
MATCH_R = 2.0                                  # motion: nearest same owner/body in the previous poll within 2 tiles
COOLDOWN = 20                                  # an opponent card is not re-detected within this many ticks
SPELL_COOLDOWN = 240                           # ... a spell's bodies (Graveyard lasts ~10 s; carrier then landing)
SPELL_GAP = 100                                # ... and only after none of its bodies were seen for this long

# entity columns
E_KIND, E_CARD, E_BODY, E_OWNER, E_X, E_Y, E_HP, E_AGE, E_VX, E_VY, E_MOT, E_AX, E_AY = range(13)
E_COLS = 13
# tower rows: own king, own left, own right, opp king, opp left, opp right; columns
TOWER_ORDER = ((0, 'king', None), (0, 'princess', 'left'), (0, 'princess', 'right'),
               (1, 'king', None), (1, 'princess', 'left'), (1, 'princess', 'right'))
T_PRESENT, T_ALIVE, T_HP = range(3)
T_COLS = 3
# hand rows: 4 slots then next; columns
H_CARD, H_COST, H_AFFORD, H_LEGAL, H_PLACE, H_NEXT = range(6)
H_COLS = 6
PLACE_CODES = {'ground': 1, 'enemy': 2, 'territory': 3, 'spell': 4}
# global columns
(G_TICK, G_ELIXIR, G_BUSY, G_PEND_CARD, G_PEND_SLOT, G_PEND_TILE, G_PEND_AGE, G_OWN_LAST, G_REJ_LAST, G_N_OWN,
 G_N_OPP, G_N_REV, G_SINCE_SUBMIT, G_X_UNITS, G_X_SPELLS, G_POLLS, G_GAP) = range(17)
G_COLS = 17
# recent events
V_PRESENT, V_OWNER, V_CARD, V_X, V_Y, V_AGE, V_SRC = range(7)
V_COLS = 7
SRC_OWN, SRC_OPP_BODY, SRC_OPP_CARRIER, SRC_OPP_EVENT, SRC_OPP_SPELLBODY = 1, 2, 3, 4, 5
# revealed opponent cards
R_PRESENT, R_CARD, R_N, R_SINCE, R_OTHERS, R_FIRST, R_UNC = range(7)
R_COLS = 7
# lag summaries
(L_PRESENT, L_LAG, L_DEL, L_DT0, L_DT1, L_DT2, L_DT3, L_DT4, L_DT5, L_NOWN, L_NOPP, L_OPP_HL, L_OPP_HR, L_OWN_HL,
 L_OWN_HR) = range(15)
L_COLS = 15


class FeatureError(ValueError):
    """An input outside the allow-list or contract (never featurised; live: a refusal, not a WAIT)."""


# -- catalog ---------------------------------------------------------------------------------------------------------
class Catalog:
    def __init__(self, path=CATALOG_PATH):
        raw = Path(path).read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        cat = json.loads(raw)
        if cat.get('schema') != 'clasher.pretrain_v1.catalog.v1':
            raise FeatureError('catalog schema')
        self.cards = cat['cards']
        self.card_idx = {c['name']: i + 2 for i, c in enumerate(self.cards)}      # 0 pad, 1 unknown
        self.by_name = {c['name']: c for c in self.cards}
        self.body_idx = {b: i + 2 for i, b in enumerate(cat['bodies'])}
        self.n_cards = len(self.cards) + 2
        self.n_bodies = len(cat['bodies']) + 2
        self.carriers = frozenset(cat['spell_carriers'])
        self.cost = np.zeros(self.n_cards, np.int16)
        self.place = np.zeros(self.n_cards, np.int16)
        self.is_spell = np.zeros(self.n_cards, bool)
        for c in self.cards:
            i = self.card_idx[c['name']]
            self.cost[i], self.place[i], self.is_spell[i] = c['cost'], PLACE_CODES[c['place']], c['kind'] == 'spell'
        # opponent play detection: a card's primary body (its first body; any body when none is listed)
        self.primary = {c['name']: (c['bodies'][0] if c['bodies'] else None) for c in self.cards}

    def card(self, name):
        return self.card_idx.get(name, 1)

    def body(self, name):
        return self.body_idx.get(name, 1)


_CATALOG = None


def catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = Catalog()
    return _CATALOG


def feature_hash():
    """sha256 over this module's bytes and the catalog's: the identity pinned in dataset and checkpoint manifests."""
    h = hashlib.sha256()
    h.update(Path(__file__).read_bytes())
    h.update(CATALOG_PATH.read_bytes())
    return h.hexdigest()


# -- validation ------------------------------------------------------------------------------------------------------
def _num(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise FeatureError(f'{what} out of range: {v!r}')
    return float(v)


def sanitize(record):
    """Allow-list check (state.check_record's sets, plus types and ranges) -> a canonical copy without logging keys."""
    if not isinstance(record, dict):
        raise FeatureError('record is not a dict')
    keys = set(record) - LOG_KEYS
    if keys != RECORD_KEYS:
        raise FeatureError(f'record keys {sorted(keys)} != allow-list')
    tick = record['tick']
    if not isinstance(tick, int) or isinstance(tick, bool) or not 0 <= tick <= 20000:
        raise FeatureError('tick')
    units = []
    for u in record['units']:
        if not isinstance(u, dict) or set(u) - UNIT_KEYS or not {'card', 'owner', 'x', 'y'} <= set(u):
            raise FeatureError('unit keys outside the allow-list')
        if u['owner'] not in (0, 1) or isinstance(u['owner'], bool):
            raise FeatureError('unit owner')
        body = u.get('class', u.get('cls'))
        if not isinstance(u['card'], str) or not isinstance(body, str):
            raise FeatureError('unit card / class')
        hp = u.get('hp_frac')
        units.append((u['card'], body, u['owner'], _num(u['x'], -1, W + 1, 'x'), _num(u['y'], -1, H + 1, 'y'),
                      None if hp is None else _num(hp, 0, 1, 'hp_frac')))
    towers = {}
    for t in record['towers']:
        if not isinstance(t, dict) or set(t) != TOWER_KEYS:
            raise FeatureError('tower keys outside the allow-list')
        key = (t['owner'], t['kind'], t['side'])
        if key not in TOWER_ORDER or key in towers:
            raise FeatureError(f'tower {key}')
        towers[key] = (_num(t['hp_frac'], 0, 1, 'tower hp'), bool(t['alive']))
    events = []
    for e in record['events']:
        if not isinstance(e, dict) or set(e) != EVENT_KEYS or e['owner'] != 1:
            raise FeatureError('event keys outside the allow-list')
        events.append((e['card'], _num(e['x'], -1, W + 1, 'event x'), _num(e['y'], -1, H + 1, 'event y'),
                       int(e['tick'])))
    hand = record['hand']
    if not isinstance(hand, dict) or set(hand) != {'cards', 'next'} or len(hand['cards']) != 4:
        raise FeatureError('hand outside the allow-list')
    if not all(isinstance(c, str) for c in hand['cards']) or not isinstance(hand['next'], str):
        raise FeatureError('hand cards')
    elixir = _num(record['elixir'], 0, 10, 'elixir')
    return dict(tick=tick, units=units, towers=towers, events=events, hand=list(hand['cards']), next=hand['next'],
                elixir=elixir)


def sanitize_extras(extras, n_units):
    if extras is None:
        return None, None
    if not isinstance(extras, dict) or set(extras) - EXTRA_KEYS:
        raise FeatureError('extras keys outside the allow-list')
    first = extras.get('first_seen')
    if first is not None:
        if len(first) != n_units or not all(isinstance(v, int) and not isinstance(v, bool) for v in first):
            first = None                               # misaligned: missing, exactly as rfextras.unit_extras returns {}
    spells = extras.get('spells')
    if spells is not None:
        out = []
        for s in spells:
            if len(s) != 7:
                raise FeatureError('carrier row is not (owner, card, x, y, aim_x, aim_y, flown)')
            owner, card, x, y, ax, ay, flown = s
            if owner not in (0, 1) or not isinstance(card, str):
                raise FeatureError('carrier owner / card')
            out.append((owner, card, _num(x, -1, W + 1, 'carrier x'), _num(y, -1, H + 1, 'carrier y'),
                        _num(ax, -1, W + 1, 'aim x'), _num(ay, -1, H + 1, 'aim y'), int(flown)))
        spells = out
    return first, spells


def q(v, k):
    return int(round(v*k))


# -- placement geometry ----------------------------------------------------------------------------------------------
FENCE = {(0, 14), (17, 14), (0, 17), (17, 17)} | {(c, 0) for c in range(18) if not 6 <= c <= 11} \
    | {(c, 31) for c in range(18) if not 6 <= c <= 11}
TOWER_BOX = {(0, 'king', None): (9.0, 3.0, 2.0), (0, 'princess', 'left'): (3.5, 6.5, 1.5),
             (0, 'princess', 'right'): (14.5, 6.5, 1.5), (1, 'king', None): (9.0, 29.0, 2.0),
             (1, 'princess', 'left'): (3.5, 25.5, 1.5), (1, 'princess', 'right'): (14.5, 25.5, 1.5)}


@lru_cache(maxsize=4096)
def tile_mask(place, alive):
    """(place code, 6 tower-alive bits in TOWER_ORDER) -> bool[576] legal tile centres, row-major (row*18 + col)."""
    m = np.zeros((H, W), bool)
    cx = np.arange(W) + .5
    cy = np.arange(H) + .5
    X, Y = np.meshgrid(cx, cy)
    fence = np.zeros((H, W), bool)
    for c, r in FENCE:
        fence[r, c] = True
    on_tower = np.zeros((H, W), bool)
    for k, a in zip(TOWER_ORDER, alive):
        if a:
            tx, ty, rad = TOWER_BOX[k]
            on_tower |= (np.abs(X - tx) <= rad + 1e-9) & (np.abs(Y - ty) <= rad + 1e-9)
    zone = (Y >= 1) & (Y < 15) | (X >= 6) & (X < 12) & (Y < 6)
    if not alive[4]:                       # enemy left princess down: left pocket + bridge
        zone |= (X < 9) & (Y >= 17) & (Y < 21) | (X >= 2.5) & (X < 4.5) & (Y >= 15) & (Y < 17)
    if not alive[5]:
        zone |= (X >= 9) & (Y >= 17) & (Y < 21) | (X >= 13.5) & (X < 15.5) & (Y >= 15) & (Y < 17)
    if place == PLACE_CODES['spell']:
        m = ~fence
    elif place == PLACE_CODES['enemy']:
        m = ~fence & ~on_tower
    elif place == PLACE_CODES['territory']:
        m = ~fence & zone
    elif place == PLACE_CODES['ground']:
        m = ~fence & zone & ~on_tower
    m = m.reshape(-1)
    m.setflags(write=False)
    return m


def nearest_legal_tile(sx, sy, mask, radius=.75):
    """(screen x, y) -> (tile, residual) for the nearest legal tile centre within `radius` tiles, else (None, d)."""
    col, row = min(max(int(math.floor(sx)), 0), W - 1), min(max(int(math.floor(sy)), 0), H - 1)
    best, bd = None, float('inf')
    for r in range(max(0, row - 2), min(H, row + 3)):
        for c in range(max(0, col - 2), min(W, col + 3)):
            if mask[r*W + c]:
                d = math.hypot(c + .5 - sx, r + .5 - sy)
                if d < bd - 1e-12:
                    best, bd = r*W + c, d
    return (best, bd) if best is not None and bd <= radius + 1e-9 else (None, bd)


# -- history ---------------------------------------------------------------------------------------------------------
class History:
    """Bounded causal state of ONE battle perspective. Create a new one per battle; never reuse across battles."""

    def __init__(self):
        self.prev = deque(maxlen=HIST_POLLS)       # sanitized previous records (dicts above), oldest first
        self.events = deque(maxlen=MAX_EV)         # (tick, owner, card idx, x_q, y_q, src)
        self.opp = deque(maxlen=MAX_OPP)           # (tick, card idx)
        self.revealed = {}                         # card idx -> first observed tick
        self.uncertain = set()                     # card idx whose cast count is not exactly identifiable
        self.last_detect = {}                      # opponent card name -> last detected tick
        self.spell_seen = {}                       # opponent spell card name -> last tick any of its bodies was seen
        self.carriers = Counter()                  # previous poll's opponent carrier keys (multiset)
        self.last_ordinary = None                  # own last confirmed non-Mirror card (Mirror's source)
        self.pending = None                        # (submit tick, slot, card idx, tile)
        self.tile_hint = {}                        # card name -> tile of an own play made without a submission
        self.n_own = 0
        self.own_last = None
        self.rej_last = None
        self.last_submit = None
        self.polls = 0
        self.last_tick = None

    # own command channel (producers call these; the effects are confirmed from the record's hand)
    def submit(self, tick, slot, card, tile):
        if self.pending is not None:
            raise FeatureError('one outstanding command at most')
        self.pending = (int(tick), int(slot), catalog().card(card), int(tile))
        self.last_submit = int(tick)

    def reject(self, tick):
        self.pending = None
        self.rej_last = int(tick)

    def hint_own_tile(self, card, tile):
        """Offline only: the tile of an own play that had no lag-aligned submission (its label was not admissible).
        Live never needs it: every own play is a submission."""
        self.tile_hint[card] = int(tile)


def _lag_summary(cur, then):
    out = np.zeros(L_COLS, np.int32)
    if then is None:
        return out
    out[L_PRESENT] = 1
    out[L_LAG] = cur['tick'] - then['tick']
    out[L_DEL] = q(cur['elixir'] - then['elixir'], EL_Q)
    for i, k in enumerate(TOWER_ORDER):
        a, b = cur['towers'].get(k), then['towers'].get(k)
        out[L_DT0 + i] = q(a[0] - b[0], HP_Q) if a is not None and b is not None else 0
    us = then['units']
    out[L_NOWN] = sum(u[2] == 0 for u in us)
    out[L_NOPP] = sum(u[2] == 1 for u in us)
    out[L_OPP_HL] = sum(u[2] == 1 and u[4] < 16 and u[3] < 9 for u in us)
    out[L_OPP_HR] = sum(u[2] == 1 and u[4] < 16 and u[3] >= 9 for u in us)
    out[L_OWN_HL] = sum(u[2] == 0 and u[4] >= 16 and u[3] < 9 for u in us)
    out[L_OWN_HR] = sum(u[2] == 0 and u[4] >= 16 and u[3] >= 9 for u in us)
    return out


def _motion(units, prev_units, dt):
    """Per unit (vx, vy, ok): nearest same-owner same-body unit of the previous poll within MATCH_R tiles, matched
    greedily by distance (a public-position finite difference, not an identity claim)."""
    n = len(units)
    out = np.zeros((n, 3), np.int32)
    if not prev_units or dt <= 0 or n == 0:
        return out
    groups = {}
    for j, p in enumerate(prev_units):
        groups.setdefault((p[1], p[2]), []).append(j)
    pairs = []
    for i, u in enumerate(units):
        for j in groups.get((u[1], u[2]), ()):
            d = math.hypot(u[3] - prev_units[j][3], u[4] - prev_units[j][4])
            if d <= MATCH_R:
                pairs.append((d, i, j))
    pairs.sort()
    used_i, used_j = set(), set()
    for d, i, j in pairs:
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        vx = (units[i][3] - prev_units[j][3])/dt
        vy = (units[i][4] - prev_units[j][4])/dt
        out[i] = (max(-V_CAP, min(V_CAP, q(vx, V_Q))), max(-V_CAP, min(V_CAP, q(vy, V_Q))), 1)
    return out


def played_cards(prev_hand, hand):
    """Own cards that left the hand between two polls (each card is in the deck once)."""
    return [c for c in prev_hand if c not in hand]


def observe(record, extras, hist):
    """One poll -> Features. Updates `hist` (call exactly once per poll, in tick order)."""
    cat = catalog()
    rec = sanitize(record)
    first, spells = sanitize_extras(extras, len(rec['units']))
    tick = rec['tick']
    if hist.last_tick is not None and tick <= hist.last_tick:
        raise FeatureError('poll tick did not advance (new battle: new History)')
    prev = hist.prev[-1] if hist.prev else None
    gap = tick - prev['tick'] if prev is not None else -1

    # own plays: a card that left the hand took effect (the pending submission's tile, else an offline hint)
    if prev is not None:
        for card in played_cards(prev['hand'], rec['hand']):
            ci = cat.card(card)
            tile = -1
            if hist.pending is not None and hist.pending[2] == ci:
                tile = hist.pending[3]
                hist.pending = None
            elif card in hist.tile_hint:
                tile = hist.tile_hint.pop(card)
            x, y = ((tile % W + .5, tile//W + .5) if tile >= 0 else (-1, -1))
            hist.events.append((tick, 0, ci, q(x, XY_Q) if tile >= 0 else -1, q(y, XY_Q) if tile >= 0 else -1, SRC_OWN))
            if card != 'Mirror':
                hist.last_ordinary = card
            hist.n_own += 1
            hist.own_last = tick
    if hist.pending is not None and tick - hist.pending[0] > EXPIRE:
        hist.pending = None
        hist.rej_last = tick

    # opponent plays observed in public (DESIGN: a revealed-card sequence with uncertainty, never a hidden hand):
    #   carriers  each new in-flight carrier instance (multiset of card + aim) is one cast, at tick - flown
    #   bodies    a rise in the count of a card's PRIMARY body (descendants never count), cooldown COOLDOWN
    #   spell bodies (Graveyard, landed Barrel, Royal Delivery): a cast only after SPELL_GAP ticks without any of
    #             that card's bodies and SPELL_COOLDOWN since its last detection; such counts are marked uncertain
    #   first poll / unexplained presence: the card is revealed, its cast is not counted (marked uncertain)
    def detect(card, t, x, y, src, cool):
        last = hist.last_detect.get(card)
        if cool and last is not None and t - last <= cool:
            return
        hist.last_detect[card] = t
        ci = cat.card(card)
        hist.events.append((t, 1, ci, q(x, XY_Q), q(y, XY_Q), src))
        hist.opp.append((t, ci))
        hist.revealed.setdefault(ci, t)
        if src == SRC_OPP_SPELLBODY:
            hist.uncertain.add(ci)

    carriers_now = Counter()
    where = {}
    for owner, card, x, y, ax, ay, flown in (spells or ()):
        if owner != 1 or card not in cat.carriers:
            continue
        key = (card, round(ax, 1), round(ay, 1))
        carriers_now[key] += 1
        where[key] = (ax, ay, flown)
    if spells is not None:
        for key, n in sorted(carriers_now.items()):
            ax, ay, flown = where[key]
            for _ in range(max(0, n - hist.carriers.get(key, 0))):
                detect(key[0], tick - max(0, min(flown, 200)), ax, ay, SRC_OPP_CARRIER, 0)
        hist.carriers = carriers_now
    prev_units = prev['units'] if prev is not None else []

    def is_spell(card):
        return card in cat.by_name and cat.by_name[card]['kind'] == 'spell'

    def opp_groups(units):
        g = {}
        for i, u in enumerate(units):
            if u[2] != 1:
                continue
            prim = cat.primary.get(u[0], u[1])
            if is_spell(u[0]) or prim is None or u[1] == prim:
                g.setdefault(u[0], []).append(i)
        return g
    g_now, g_prev = opp_groups(rec['units']), opp_groups(prev_units)
    for card, idx in sorted(g_now.items()):
        if prev is None:                                   # present before tracking: revealed, cast not counted
            ci = cat.card(card)
            hist.revealed.setdefault(ci, tick)
            hist.uncertain.add(ci)
            continue
        new = [i for i in idx if first is not None and first[i] > prev['tick']] or idx
        x = sum(rec['units'][i][3] for i in new)/len(new)
        y = sum(rec['units'][i][4] for i in new)/len(new)
        t = min(first[i] for i in new) if first is not None else tick
        if is_spell(card):
            seen = hist.spell_seen.get(card)
            if seen is None or tick - seen > SPELL_GAP:
                detect(card, t, x, y, SRC_OPP_SPELLBODY, SPELL_COOLDOWN)
            hist.spell_seen[card] = tick
        elif len(idx) > len(g_prev.get(card, ())):
            detect(card, t, x, y, SRC_OPP_BODY, COOLDOWN)
    for card, x, y, t in rec['events']:
        detect(card, t, x, y, SRC_OPP_EVENT, SPELL_COOLDOWN)

    # entities
    units = rec['units']
    n_ent = len(units) + sum(1 for s in (spells or ()) if s[1] in cat.carriers)
    if n_ent > MAX_ENT:
        raise FeatureError(f'{n_ent} entities > cap {MAX_ENT}')
    ent = np.zeros((n_ent, E_COLS), np.int16)
    mot = _motion(units, prev_units, gap if prev is not None else 0)
    for i, (card, body, owner, x, y, hp) in enumerate(units):
        ent[i, E_KIND] = 1
        ent[i, E_CARD] = cat.card(card)
        ent[i, E_BODY] = cat.body(body)
        ent[i, E_OWNER] = owner
        ent[i, E_X], ent[i, E_Y] = q(x, XY_Q), q(y, XY_Q)
        ent[i, E_HP] = -1 if hp is None else q(hp, HP_Q)
        ent[i, E_AGE] = -1 if first is None else max(0, min(AGE_CAP, tick - first[i]))
        ent[i, E_VX], ent[i, E_VY], ent[i, E_MOT] = mot[i]
    k = len(units)
    for owner, card, x, y, ax, ay, flown in (spells or ()):
        if card not in cat.carriers:
            continue
        ent[k, E_KIND] = 2
        ent[k, E_CARD] = cat.card(card)
        ent[k, E_OWNER] = owner
        ent[k, E_X], ent[k, E_Y] = q(x, XY_Q), q(y, XY_Q)
        ent[k, E_HP] = -1
        ent[k, E_AGE] = max(0, min(AGE_CAP, flown))
        ent[k, E_AX], ent[k, E_AY] = q(ax, XY_Q), q(ay, XY_Q)
        k += 1

    # towers
    tow = np.zeros((6, T_COLS), np.int16)
    alive = []
    for i, key in enumerate(TOWER_ORDER):
        t = rec['towers'].get(key)
        if t is None:
            alive.append(True)                         # never seen: assume standing (conservative placement)
            continue
        tow[i] = (1, int(t[1]), q(t[0], HP_Q))
        alive.append(bool(t[1]))
    alive = tuple(alive)

    # hand, affordability, legality (channel capacity, observed elixir, public placement geometry)
    busy = hist.pending is not None
    hand = np.zeros((5, H_COLS), np.int16)
    slot_ok = np.zeros(4, bool)
    for s, card in enumerate(rec['hand'] + [rec['next']]):
        ci = cat.card(card)
        cost, place = int(cat.cost[ci]), int(cat.place[ci])
        if card == 'Mirror':                               # engine: last ordinary card's cost + 1 and its placement
            src = cat.card(hist.last_ordinary) if hist.last_ordinary is not None else 1
            cost, place = (int(cat.cost[src]) + 1, int(cat.place[src])) if src >= 2 else (0, 0)
        hand[s, H_CARD] = ci
        hand[s, H_COST] = cost
        hand[s, H_PLACE] = place
        hand[s, H_NEXT] = int(s == 4)
        if s < 4 and ci >= 2 and place:
            afford = rec['elixir'] + 1e-9 >= cost
            hand[s, H_AFFORD] = int(afford)
            ok = afford and not busy and bool(tile_mask(place, alive).any())
            hand[s, H_LEGAL] = int(ok)
            slot_ok[s] = ok

    # recent events (most recent first, within EV_WINDOW)
    ev = np.zeros((MAX_EV, V_COLS), np.int16)
    j = 0
    for t, owner, ci, x, y, src in sorted(hist.events, key=lambda e: -e[0]):
        age = tick - t
        if age > EV_WINDOW or j >= MAX_EV:
            break
        ev[j] = (1, owner, ci, x, y, max(0, age), src)
        j += 1

    # revealed opponent cards (observed only; order of first reveal)
    rev = np.zeros((MAX_REV, R_COLS), np.int16)
    opp = list(hist.opp)
    for j, (ci, t0) in enumerate(sorted(hist.revealed.items(), key=lambda kv: (kv[1], kv[0]))[:MAX_REV]):
        plays = [i for i, (_, c) in enumerate(opp) if c == ci]
        last_i = plays[-1] if plays else None
        rev[j, R_PRESENT] = 1
        rev[j, R_CARD] = ci
        rev[j, R_N] = min(15, len(plays))
        rev[j, R_SINCE] = min(2400, tick - opp[last_i][0]) if plays else 2400
        rev[j, R_OTHERS] = min(15, len(opp) - 1 - last_i) if plays else 15
        rev[j, R_FIRST] = min(6000, tick - t0)
        rev[j, R_UNC] = int(ci in hist.uncertain)

    # previous-record summaries at ~5/10/20/40 ticks
    lag = np.zeros((len(LAGS), L_COLS), np.int32)
    for i, L in enumerate(LAGS):
        then = None
        for p in reversed(hist.prev):
            if tick - p['tick'] >= L:
                then = p if tick - p['tick'] <= L + POLL else None
                break
        lag[i] = _lag_summary(rec, then)

    g = np.zeros(G_COLS, np.int32)
    g[G_TICK] = tick
    g[G_ELIXIR] = q(rec['elixir'], EL_Q)
    g[G_BUSY] = int(busy)
    if busy:
        g[G_PEND_CARD], g[G_PEND_SLOT], g[G_PEND_TILE] = hist.pending[2], hist.pending[1], hist.pending[3]
        g[G_PEND_AGE] = tick - hist.pending[0]
    else:
        g[G_PEND_SLOT] = g[G_PEND_TILE] = g[G_PEND_AGE] = -1
    g[G_OWN_LAST] = min(AGE_CAP, tick - hist.own_last) if hist.own_last is not None else -1
    g[G_REJ_LAST] = min(AGE_CAP, tick - hist.rej_last) if hist.rej_last is not None else -1
    g[G_N_OWN] = min(255, hist.n_own)
    g[G_N_OPP] = min(255, len(hist.opp))
    g[G_N_REV] = len(hist.revealed)
    g[G_SINCE_SUBMIT] = min(AGE_CAP, tick - hist.last_submit) if hist.last_submit is not None else -1
    g[G_X_UNITS] = int(first is not None)
    g[G_X_SPELLS] = int(spells is not None)
    g[G_POLLS] = min(255, hist.polls)
    g[G_GAP] = min(255, gap)

    hist.prev.append(rec)
    hist.polls += 1
    hist.last_tick = tick
    return dict(ent=ent, tow=tow, hand=hand, glob=g, ev=ev, rev=rev, lag=lag, slot_ok=slot_ok,
                alive=np.array(alive, bool))


def legal_tiles(feat):
    """bool[4, 576]: per hand slot, legal tile centres (all False for an illegal slot)."""
    out = np.zeros((4, NTILE), bool)
    alive = tuple(bool(a) for a in feat['alive'])
    for s in range(4):
        if feat['slot_ok'][s]:
            out[s] = tile_mask(int(feat['hand'][s, H_PLACE]), alive)
    return out


def encode(slot, tile):
    return int(slot)*NTILE + int(tile)


def decode(action):
    """action -> (slot, col, row) or None for no-op."""
    if action == NOOP:
        return None
    slot, tile = divmod(int(action), NTILE)
    row, col = divmod(tile, W)
    return slot, col, row


def feature_bytes(feat):
    """Canonical serialisation for parity checks."""
    h = hashlib.sha256()
    for k in sorted(feat):
        a = np.ascontiguousarray(feat[k])
        h.update(k.encode())
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()
