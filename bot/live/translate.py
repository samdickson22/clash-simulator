"""Perception record -> the fair public view our players consume (LIVE track, exploration).

Modelled on bot/players/royalesim_translate.py: the same contract-v5 packet is filled from perception rows and the
SAME `Translator.observation` code (hand ids, enemy history/seen cards, own last play, levels, project_public_v5)
runs on it. Only the row source (`_rows`), the globals and the champion button are replaced.

Perception record (one frame; agreed with the perception owner). Coordinates are tiles on the 18x32 lattice in OUR
frame (our king at the bottom, y=0 at our edge); owner 0 = us, 1 = opponent:
  tick      int, optional. Else derived from clock+phase (`tick_from_clock`).
  clock     seconds left on the match clock; phase 'regular' | 'overtime' | 'ended' (optional when tick given)
  units     [{class, owner, x, y, hp_frac | hp_abs, score}]  class = game body name (body-catalog.json names,
            e.g. 'Knight', 'Archer', 'SpearGoblin'); towers may also be omitted here (see towers)
  towers    [{owner, kind: 'king'|'princess', side: 'left'|'right'|None, hp_frac, alive}]
  hand      {'cards': [4 names or None], 'next': name or None, 'probs': [...]}  (or a plain list of 4 + 'next')
  elixir    float, own
  events    [{owner, card, x, y, tick}]  accepted card plays seen THIS frame (or cumulative; de-duplicated)

Output: fair_player.Information(tick, seat=0, packet, own, events) where
  packet  ConfidenceAwareActorObservation (v5) built like ContractV5ObservationBuilder.build_public;
  own     dict(elixir, hand, cycle, refill) from the HUD + OwnTracker (own play order is own information);
  events  derived_public_state.PublicEvent rows of ENEMY card plays (opponent elixir/cycle are derived from these
          by the bot's own belief, never read from anywhere else).
plus `public_events`: D1 rows (seat, tick, kind, name, amount, x, y) of both seats.

Policies (documented, counted in `stats`):
- Body classes map through royalesim_vocab.json 'units' (RoyaleSim unit_type == game body name) and then a
  case-insensitive lookup of our troop/building tokens; a class with no public template is DROPPED (never guessed).
- Spells/projectiles are not in the perception schema, so in-flight spells and shots are absent from the root.
- Unit facing is unknown: 'dynamic' bodies get the owner's forward (or vx/vy if the record carries them).
- Deploy timers are unknown: the frozen R.root already sets deploy=0 for every body (template defaults).
- hp_abs is converted with our level-11 max HP (or the given level's, see levels.py); hp_frac is used as is.
- Non-C56 cards (e.g. Spear Goblins, Goblin Cage): unknown_card='drop' removes the play from the bot's event
  streams (opponent elixir is then OVER-estimated by its cost); 'proxy' substitutes a same-cost C56 card from
  PROXY (keeps the elixir ledger; identity is wrong). Own non-C56 hand cards become empty (unplayable) slots.
- More than 8 distinct C56 enemy cards (perception error) -> the 9th+ card's plays are dropped.
- Levels: the packet carries level 11 everywhere (R3a/it5s2 only ever saw 11); real levels go to the planner
  root (levels.py). Fair-information: nothing about the opponent other than the public board, tower HP and the
  card plays it made is read; see test_translate.py::test_invariance.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from bot.players.royalesim_translate import Translator, _unit, BOARD_W, BOARD_H, TICK_SECONDS

VOCAB_PATH = Path(__file__).resolve().parents[1] / 'players/royalesim_vocab.json'
REGULAR_S, OVERTIME_S = 180.0, 120.0
# Same-cost C56 stand-ins for common low-arena non-C56 cards (unknown_card='proxy').
PROXY = {'SpearGoblins': 'Goblins', 'GoblinCage': 'BombTower', 'Bomber': 'Musketeer', 'Barbarians': 'Valkyrie',
         'Mortar': 'Cannon', 'BattleRam': 'HogRider', 'Witch': 'Wizard', 'Tombstone': 'Cannon',
         'ElectroWizard': 'Wizard', 'IceWizard': 'Musketeer', 'MegaMinion': 'Musketeer', 'Furnace': 'BombTower',
         'Pekka': 'Golem', 'RoyalGiant': 'Giant', 'ThreeMusketeers': 'Golem', 'Clone': 'Arrows',
         'Freeze': 'Poison', 'Rage': 'Zap', 'GiantSkeleton': 'Giant', 'Bowler': 'Wizard', 'Executioner': 'Wizard',
         'DartGoblin': 'Princess', 'ElixirCollector': 'Tesla', 'Lumberjack': 'MiniPekka', 'Bandit': 'MiniPekka',
         'Fisherman': 'Valkyrie', 'MagicArcher': 'Musketeer', 'EliteBarbarians': 'MiniPekka',
         'GiantSnowball': 'Arrows', 'BarbarianBarrel': 'Log', 'HealSpirit': 'IceSpirit', 'Snowball': 'Arrows'}
TOWER_XY = {('king', None): (9.0, 3.0), ('princess', 'left'): (3.5, 6.5), ('princess', 'right'): (14.5, 6.5)}


def tick_from_clock(clock, phase):
    """Match tick (20/s) from the HUD clock: regulation counts 3:00 down, overtime 2:00 down."""
    if phase == 'overtime':
        return int(round((REGULAR_S + OVERTIME_S - float(clock))/TICK_SECONDS))
    return int(round((REGULAR_S - float(clock))/TICK_SECONDS))


def load_vocab(rt, path=VOCAB_PATH):
    vocab = json.loads(Path(path).read_text())
    names = rt.R.builder.token_names
    if vocab['meta']['token_sha256'] != hashlib.sha256('\n'.join(names).encode()).hexdigest():
        raise ValueError('royalesim_vocab.json was built for another token vocabulary')
    return vocab


class OwnTracker:
    """Own hand/cycle from the HUD plus own play order. Queue = [next] + never-played cards (initial order unknown:
    deck order) + played cards in play order; refill estimated from the last own play."""

    def __init__(self, deck):
        if len(deck) != 8 or len(set(deck)) != 8:
            raise ValueError('own deck must be 8 distinct cards')
        self.deck, self.played, self.last_play = list(deck), [], None

    def play(self, tick, card):
        if card in self.played:
            self.played.remove(card)
        self.played.append(card)
        self.last_play = tick

    def own(self, tick, elixir, hand, next_card):
        hand = [c if c in self.deck else None for c in list(hand)[:4]] + [None]*(4-len(list(hand)[:4]))
        held = set(c for c in hand if c)
        rest = [c for c in self.deck if c not in held]
        first = [next_card] if next_card in rest else []
        fresh = [c for c in self.deck if c in rest and c not in self.played and c not in first]
        old = [c for c in self.played if c in rest and c not in first]
        cycle = first + fresh + old
        refill = 0
        if None in hand and self.last_play is not None:
            refill = max(0, 1000 - 50*(tick - self.last_play)) if tick < 2400 else max(0, 500 - 50*(tick - self.last_play))
        return dict(elixir=float(elixir), hand=hand, cycle=cycle, refill=int(refill))


class LiveTranslator(Translator):
    """Perception records -> Information. One instance per match; feed records in time order."""

    def __init__(self, rt, own_deck, *, vocab=None, unknown_card='drop', proxy=None, seat=0, plays_from='births',
                 card_level=True, tracker_kw=None):
        if unknown_card not in ('drop', 'proxy'):
            raise ValueError(unknown_card)
        if seat != 0:
            raise ValueError('records are in our own frame: the live seat is always 0')
        # Translator.__init__ needs RoyaleSim; only the attributes observation()/_row() read are set here.
        self.rt, self.vocab = rt, vocab or load_vocab(rt)
        self.builder, self.costs = rt.R.builder, rt.R.costs
        self.templates = {(int(t), ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity').index(k))
                          for (t, k) in rt.R.templates}
        self.statics = {k: (v['cols'], v['level'], v['motion']) for k, v in self.vocab['statics'].items()}
        self.units = {k: tuple(v) for k, v in self.vocab['units'].items()}
        self.lower_units = {k.lower(): v for k, v in self.units.items()}
        self.champions = {c.lower() for c in self.vocab['champion_units']}
        self.lower_tokens = {n.lower(): n for n in self.builder.token_names if not n.startswith('<')}
        self.stats = Counter()
        self.seat, self.unknown_card = 0, unknown_card
        if plays_from not in ('births', 'events'):
            raise ValueError(plays_from)
        from bot.live.births import CardBodies, UnitTracker, ClockTracker
        self.plays_from, self.card_level = plays_from, card_level
        self.cards = CardBodies(rt)
        self.tracker = UnitTracker(self.cards, **(tracker_kw or {}))
        self.clock = ClockTracker()
        self.derived_plays = []          # (owner, card, x, y, tick) derived from unit births
        self.proxy = dict(PROXY if proxy is None else proxy)
        self.own_tracker = OwnTracker(own_deck)
        self.set_own_order(own_deck)
        self.plays = {0: [], 1: []}          # accepted public plays (tick, name) the bot sees
        self.events = []                     # PublicEvent stream of enemy plays
        self.public_events = []              # D1 rows of both seats
        self._seen = set()
        self.tick, self._floor = None, 0
        self._prev, self._cur = [], []

    # -- bodies -------------------------------------------------------------------------------
    def body(self, name):
        """Game body name -> (token, kind) or None."""
        mapped = self.units.get(name) or self.lower_units.get(name.lower())
        if mapped is not None:
            return tuple(mapped)
        canonical = self.lower_tokens.get(name.lower(), name)
        for ns, kind in (('troop_body', 0), ('building_body', 1)):
            token = int(self.builder.token_id(canonical, namespace=ns))
            if token > 1 and (token, kind) in self.templates:
                self.units[name] = (token, kind)
                return token, kind
        return None

    def max_hp(self, token, kind):
        t = self.rt.R.templates.get((token, ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')[kind]))
        return float(t['stats']['max_hp']) if t else None

    def _rows(self, record, seat):
        out = []
        S = 18000
        assigned = record.get('_assigned')
        for i, u in enumerate(record.get('units', ())):
            if assigned is not None:
                mapped, facing = assigned[i]
                if mapped is None:
                    continue
                u = dict(u, vx=facing[0], vy=facing[1])
            else:
                mapped = self.body(str(u.get('class', u.get('cls'))))
            if mapped is None:
                self.stats[f'unmapped_unit:{u.get("class", u.get("cls"))}'] += 1
                continue
            token, kind = mapped
            if (token, kind) not in self.templates:
                self.stats[f'no_template:{token}/{kind}'] += 1
                continue
            team = 0 if int(u['owner']) == 0 else 1
            hp = u.get('hp_frac')
            if hp is None and u.get('hp_abs') is not None:
                m = self.max_hp(token, kind)
                hp = float(u['hp_abs'])/m if m else 1.
            vx, vy = u.get('vx'), u.get('vy')
            if vx is None or vy is None:
                vx, vy = self.track(u, team)
            row, level = self._row(seat, token, kind, team, float(u['x'])*S, float(u['y'])*S,
                                   1. if hp is None else hp, (vx, vy))
            if math.hypot(vx, vy) < 1e-6 and self.statics.get(f'{token}/{kind}', (0, 0, 'dynamic'))[2] == 'dynamic':
                row[27], row[28] = 0., (1. if team == seat else -1.)   # facing unknown: owner's forward
            out.append(((kind, int(team != seat), token, round(float(row[1]), 5), round(float(row[0]), 5)),
                        token, row, level))
        self._prev, self._cur = self._cur, []
        king_token, king_kind = self.vocab['towers']['2']
        tower_token, tower_kind = self.vocab['towers']['3']
        for t in self.towers(record):
            if not t['alive']:
                continue
            x, y = TOWER_XY[(t['kind'], t['side'] if t['kind'] == 'princess' else None)]
            if t['owner'] == 1:
                y = BOARD_H - y          # sides are screen sides: the enemy's left tower is at x=3.5 too
            token, kind = (king_token, king_kind) if t['kind'] == 'king' else (tower_token, tower_kind)
            row, level = self._row(seat, token, kind, t['owner'], x*S, y*S, t['hp_frac'], (0, 0))
            out.append(((kind, int(t['owner'] != seat), token, round(float(row[1]), 5), round(float(row[0]), 5)),
                        token, row, level))
        return out

    def track(self, u, team, radius=1.5):
        """Facing from motion: nearest same-class same-owner unit of the previous record within `radius` tiles;
        a still unit keeps that track's facing; a new unit gets (0, 0) -> the owner's forward."""
        x, y = float(u['x']), float(u['y'])
        best, facing = radius, (0., 0.)
        for (cls, owner, px, py, f) in self._prev:
            if cls == u['class'] and owner == team:
                d = math.hypot(x-px, y-py)
                if d < best:
                    best = d
                    facing = (x-px, y-py) if d > .05 else f
        self._cur.append((u['class'], team, x, y, facing))
        return facing

    @staticmethod
    def towers(record):
        """Six towers; the enemy's 'left' is OUR left (x < 9), as on screen. Missing towers count as alive at 100%."""
        got = {(int(t['owner']), t['kind'], t.get('side') if t['kind'] == 'princess' else None): t
               for t in record.get('towers', ())}
        out = []
        for owner in (0, 1):
            for kind, side in (('king', None), ('princess', 'left'), ('princess', 'right')):
                t = got.get((owner, kind, side), {})
                hp = float(t.get('hp_frac', 1.))
                alive = bool(t.get('alive', hp > 0))
                out.append(dict(owner=owner, kind=kind, side=side, hp_frac=hp if alive else 0., alive=alive))
        return out

    # -- globals --------------------------------------------------------------------------------
    def globals(self, record, seat, own):
        tick = record['tick']
        start = max(0, tick-1)*TICK_SECONDS
        progress = _unit(tick*TICK_SECONDS/300.)
        t = {(x['owner'], x['kind'], x['side']): x for x in self.towers(record)}
        f = lambda o, k, s: _unit(t[(o, k, s)]['hp_frac'])
        crowns = {o: (3 if not t[(o, 'king', None)]['alive'] else
                      sum(not t[(o, 'princess', s)]['alive'] for s in ('left', 'right'))) for o in (0, 1)}
        return np.asarray([
            progress, 1.-progress, float(start >= 120.), float(start >= 240.), float(start >= 180.),
            _unit(own['elixir']/10.), crowns[1]/3., crowns[0]/3.,
            f(0, 'princess', 'left'), f(0, 'princess', 'right'), f(0, 'king', None),
            f(1, 'princess', 'left'), f(1, 'princess', 'right'), f(1, 'king', None),
            0., 0., _unit(own['refill']/1000.), float(t[(1, 'king', None)]['alive'])], dtype=np.float32)

    def champion_button(self, record, seat):
        return False      # no champions in our training; abilities are never pressed

    # -- events and HUD ---------------------------------------------------------------------------
    def set_own_order(self, order):
        """Own opening order (hand[:4] + queue), as given to the players' MatchContext. Resets the stream guard."""
        from imitation.evaluation.d1 import DerivedD1
        from own_cycle import OwnCycle
        if getattr(self, 'plays', None) and (self.plays[0] or self.plays[1]):
            raise ValueError('set the own order before any play is accepted')
        self.own_order = list(order)
        self._mirrors = {0: DerivedD1(self.costs), 1: DerivedD1(self.costs)}
        self._own_cycle = OwnCycle(self.own_order)

    def _consistent(self, seat, tick, name, x, y):
        """Stream guard: the frozen D1 trackers (both seats) and the own-cycle tracker the players run would accept
        this play. A missed earlier play (perception) makes a later play of a still-cycling card impossible for them;
        such a play is dropped (counted), so the pollers and the belief never break."""
        import copy
        from imitation.evaluation.d1 import PublicEvent as D1Event
        m = self._mirrors[seat]
        m.advance(tick)
        if name in m.queue or len(m.queue) >= 8 or len(m.revealed | {name}) > 8:
            return False
        if seat == 0:
            oc = copy.deepcopy(self._own_cycle)
            try:
                oc.play(tick, name)
            except ValueError:
                return False
            self._own_cycle = oc
        m.accept(D1Event(tick, 'card', name, 0., x, y))
        return True

    def card_name(self, card):
        if card in self.costs:
            return card
        if self.unknown_card == 'proxy' and self.proxy.get(card) in self.costs:
            self.stats[f'proxy_card:{card}'] += 1
            return self.proxy[card]
        self.stats[f'dropped_card:{card}'] += 1
        return None

    def tick_of(self, record):
        """Record tick: explicit 'tick', else the HUD clock (clock_s/clock + phase) refined by timestamp_ms."""
        phase = record.get('phase', 1)
        if isinstance(phase, str):      # legacy 'regular'/'overtime'
            return tick_from_clock(record.get('clock', record.get('clock_s')), phase)
        return self.clock(record.get('clock_s', record.get('clock')), phase, record.get('timestamp_ms'))

    @staticmethod
    def _event_tick(e, record):
        if 'score' in e and e.get('exec_ms') is None and e.get('tick') is not None:
            # perception temporal-head events carry the estimated execution time in ms under 'tick'
            # (sample-records README, 2026-10-15); frame_record() names it exec_ms.
            e = dict(e, exec_ms=e['tick'], tick=None)
        if e.get('tick') is None and e.get('exec_ms') is not None and record.get('timestamp_ms') is not None:
            return dict(e, tick=int(record['tick'] - max(0., record['timestamp_ms'] - e['exec_ms'])/50))
        return e

    def assign(self, record):
        """Card-level units -> [(body (token, kind) or None, facing)] via the UnitTracker; derived plays."""
        units, idx = [], []
        for i, u in enumerate(record.get('units', ())):
            card = u.get('card') or u.get('cls') or u.get('class')
            if not self.cards.is_card(card):
                proxy = self.proxy.get(card) if self.unknown_card == 'proxy' else None
                if proxy and self.cards.is_card(proxy):
                    card = proxy
                else:
                    self.stats[f'unmapped_card_unit:{card}'] += 1
                    continue
            units.append((card, 0 if int(u['owner']) == 0 else 1, float(u['x']), float(u['y']), u.get('score')))
            idx.append(i)
        own = {t['side']: t['alive'] for t in self.towers(record) if t['owner'] == 0 and t['kind'] == 'princess'}
        got, plays = self.tracker.update(record['tick'], units, own)
        assigned = [(None, (0., 0.))]*len(record.get('units', ()))
        for i, a in zip(idx, got):
            assigned[i] = a
        return assigned, plays

    def accept_events(self, record):
        from derived_public_state import PublicEvent
        for e in sorted(record.get('events', ()), key=lambda e: int(e['tick'])):
            key = (int(e['owner']), str(e['card']), int(e['tick']), round(float(e.get('x', 0)), 1),
                   round(float(e.get('y', 0)), 1))
            if key in self._seen:
                continue
            self._seen.add(key)
            seat, tick = 0 if int(e['owner']) == 0 else 1, int(e['tick'])
            if tick > record['tick']:
                self.stats['future_event_clamped'] += 1
                tick = record['tick']
            # The belief and D1 trackers have advanced to the previous record's tick: never go behind it.
            floor = max(self._floor, self.public_events[-1]['tick'] if self.public_events else 0)
            if tick < floor:
                self.stats['late_event_retimed'] += 1
                tick = floor
            name = self.card_name(str(e['card']))
            if name is not None and not self._consistent(seat, tick, name, float(e.get('x', 9.)), float(e.get('y', 16.))):
                self.stats[f'cycle_conflict_dropped:{seat}'] += 1
                if seat == 0 and str(e['card']) in self.own_tracker.deck:
                    self.own_tracker.play(tick, str(e['card']))
                continue
            if seat == 0:
                if str(e['card']) in self.own_tracker.deck:
                    self.own_tracker.play(tick, str(e['card']))
                if name is None:
                    continue
            else:
                if name is None:
                    continue
                distinct = {n for _, n in self.plays[1]}
                if name not in distinct and len(distinct) >= 8:
                    self.stats['ninth_enemy_card_dropped'] += 1
                    continue
                self.events.append(PublicEvent(tick, 'card', name))
            self.plays[seat].append((tick, name))
            # D1 rows use absolute tiles (seat-0 frame) = our frame.
            self.public_events.append(dict(seat=seat, tick=tick, kind='card', name=name, amount=0.,
                                           x=float(e.get('x', 9.)), y=float(e.get('y', 16.))))

    def hud(self, record):
        h = record.get('hand') or {}
        if isinstance(h, dict):
            cards, nxt = list(h.get('cards', ())), h.get('next')
        else:
            cards, nxt = list(h)[:4], record.get('next')
        for c in cards + [nxt]:
            if c is not None and c not in self.costs:
                self.stats[f'own_non_c56:{c}'] += 1
        return self.own_tracker.own(record['tick'], float(record.get('elixir', 0.)), cards, nxt)

    def information(self, record):
        """One frame -> fair_player.Information. Records must arrive in non-decreasing tick order."""
        from fair_player import Information
        record = dict(record)
        if record.get('tick') is None:
            record['tick'] = self.tick_of(record)
        if self.tick is not None and record['tick'] < self.tick:
            raise ValueError('perception time moved backwards')
        self._floor = self.tick or 0
        self.tick = record['tick']
        record.setdefault('game_over', record.get('phase') == 'ended')
        events = [self._event_tick(e, record) for e in record.get('events', ())]
        if self.card_level:
            record['_assigned'], plays = self.assign(record)
            for owner, card, x, y, tick in plays:
                if owner == 1 and self.plays_from == 'births':
                    events.append(dict(owner=1, card=card, x=x, y=y, tick=tick, derived=True))
                    self.derived_plays.append((owner, card, x, y, tick))
        if self.plays_from == 'births':   # opponent plays come only from births (no temporal head yet)
            events = [e for e in events if int(e['owner']) == 0 or e.get('derived')]
        record['events'] = events
        self.accept_events(record)
        own = self.hud(record)
        packet = self.observation(record, 0, own, self.plays)
        return Information(record['tick'], 0, packet, own, tuple(self.events))


class LiveSession:
    """The live loop's bot side: perception record -> PublicView -> LivePlayer -> action, with the own command
    channel (CommandQueue, capacity 1, reservation) as in bot/players/ours.py. The caller performs the tap for the
    returned action and keeps feeding records; the pending command is completed when the own HUD shows the
    reserved card left its slot (or an own play event arrives), and expires after `expire` ticks."""

    def __init__(self, rt, player, own_deck, *, seed=0, command_delay=27, expire=90, translator=None):
        from bot.players.base import MatchContext
        from clasher.analysis.loss_review.delay_fixes import CommandQueue
        self.rt, self.player = rt, player
        self.tr = translator or LiveTranslator(rt, own_deck)
        self.ch = CommandQueue(command_delay, 1)
        self.expire, self.wait_until, self.last_poll = expire, 0, None
        self.own_deck, self.seed, self.command_delay, self.started = list(own_deck), seed, command_delay, False
        self.log, self._buffer = [], []

    def _reconcile(self, info):
        if not self.ch.pending:
            return
        c = self.ch.pending[0]
        slot_card = info.own['hand'][c.action // 576]
        own_played = any(t >= c.submitted and n == c.card for t, n in self.tr.plays[0])
        if own_played or slot_card != c.card:
            self.ch.finish(True)
            if not own_played:            # our own play is known from our command: emit it (perception has no events)
                row, col = divmod(c.action % 576, 18)
                self._buffer.append(dict(owner=0, card=c.card, x=col+.5, y=row+.5, tick=info.tick))
        elif info.tick - c.submitted > self.expire:
            self.ch.finish(False)

    def step(self, record):
        """Feed every frame. Returns a Decision on poll ticks (every 5 ticks from 90), else None. Events seen on
        frames between polls are buffered and delivered (tick-clamped) with the next poll's record."""
        from bot.players.base import POLICY_INTERVAL, START_TICK
        tick = record.get('tick')
        if tick is None:
            tick = self.tr.tick_of(record)        # HUD clock + phase + timestamp (ClockTracker, monotonic)
        poll = tick - tick % POLICY_INTERVAL
        if not self.started:      # opening order = first HUD hand + next + the rest (their order is unknown)
            from bot.players.base import MatchContext
            h = record.get('hand') or {}
            cards, nxt = (list(h.get('cards', ())), h.get('next')) if isinstance(h, dict) else (list(h)[:4], record.get('next'))
            if len(cards) != 4 or set(cards) - set(self.own_deck) or None in cards:
                return None       # wait for a complete opening hand
            order = cards + ([nxt] if nxt in self.own_deck and nxt not in cards else [])
            order += [c for c in self.own_deck if c not in order]
            self.tr.set_own_order(order)
            self.ctx = MatchContext(seat=0, seed=self.seed, own_order=tuple(order),
                                    command_delay=self.command_delay, opponent_delay=self.command_delay)
            self.player.start(self.ctx)
            self.started = True
        self._buffer.extend(record.get('events', ()))
        if tick < START_TICK or poll == self.last_poll:
            return None
        if self.last_poll is not None and poll - self.last_poll > POLICY_INTERVAL:
            # A frame gap skipped polls (capture/perception stall > 250 ms). The frozen 5-tick pollers (D1 gate in
            # imitation/evaluation/standalone.py) raise on any gap and then fail on every later poll, which would end
            # the fast tier for the match. Catch up on the current record with can_act=False (no tap from it).
            for p in range(self.last_poll + POLICY_INTERVAL, poll, POLICY_INTERVAL):
                self.tr.stats['catchup_polls'] += 1
                self._poll(dict(record, tick=p, events=[]), p, catch_up=True)
        self.last_poll = poll
        record = dict(record, tick=poll, events=self._buffer)
        self._buffer = []
        return self._poll(record, poll)

    def _poll(self, record, poll, catch_up=False):
        from bot.players.base import PublicView, WAIT
        info = self.tr.information(record)
        if getattr(self.tr, 'resynced', False):   # resync translator rewrote the opponent history (bot/live/resync.py)
            from bot.live.resync import restart_if_resynced
            restart_if_resynced(self.tr, self.player, self.ctx)
        self._reconcile(info)
        reserved = self.ch.own_packet(info, self.rt.R.builder)
        can_act = self.ch.available and poll >= self.wait_until and not catch_up
        view = PublicView(poll, 0, info, reserved, self.tr.public_events, tuple(self.ch.pending), can_act)
        d = self.player.act(view)
        if can_act and d.action < WAIT:
            try:
                self.ch.submit(info, int(d.action), self.rt.R.costs, self.rt.R.builder)
            except ValueError as ex:      # HUD disagreement: do not tap
                self.tr.stats['submit_refused'] += 1
                d.stats = dict(d.stats or {}, submit_refused=repr(ex)[:200])
                d.action = WAIT
        if can_act and d.wait_ticks:
            self.wait_until = poll + d.wait_ticks
        self.log.append(dict(tick=poll, action=int(d.action), stats=d.stats, catch_up=catch_up))
        return d

    def close(self):
        self.player.close()
