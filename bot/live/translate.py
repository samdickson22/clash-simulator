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
  own     dict(elixir, hand, cycle, refill): elixir from the HUD; hand/cycle/refill TRACKED by OwnTracker from the
          opening order and our own plays (own information), the HUD only resolving what those leave open;
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
- Card consistency (card-level records): an own unit of a card outside our deck, or an opponent unit of a 9th
  distinct card, is dropped (board_card_ok; counted), so every unit reaching search is a card its owner can have.
- Own hand/cycle (OwnTracker): always an engine-valid state (own_invariant_breaks): 4 slots of distinct deck cards
  or None, next = cycle[0] not held, hand + cycle = the 8 deck cards. A HUD slot/next that disagrees with the
  tracked state (duplicate, off-deck, next held, unread, plausible but wrong) is overridden, counted in own_fix:*.
- Levels: the packet carries level 11 everywhere (R3a/it5s2 only ever saw 11); real levels go to the planner
  root (levels.py). Fair-information: nothing about the opponent other than the public board, tower HP and the
  card plays it made is read; see test_translate.py::test_invariance.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import os
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
_COMPAT_UNSET = object()
OBSERVATION_CONTRACT = 'canonical-body-v1'


@lru_cache(maxsize=1)
def engine_body_aliases():
    """Frozen reviewed body-equivalence data, not card/provenance/placement policy."""
    raw = Path(__file__).with_name('engine_body_aliases.json').read_bytes()
    data = json.loads(raw)
    if data.get('schema') != 'canonical-engine-body-aliases-v1':
        raise ValueError('invalid engine body alias schema')
    return data, hashlib.sha256(raw).hexdigest()


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
    from bot.players.royalesim_translate import complete_vocab
    return complete_vocab(rt, vocab)


class _Cycle:
    """The engine's own hand/cycle dynamics (src/clasher/player.py; frozen own_cycle.OwnCycle, same refill rule):
    a play empties its slot and appends the card to the queue; when the refill cooldown is 0 the first empty slot
    takes the queue head and the cooldown restarts. Invariant: hand cards + queue = the 8 deck cards, each once."""
    __slots__ = ('hand', 'queue', 'tick', 'refill')

    def __init__(self, hand, queue, tick=0, refill=0):
        self.hand, self.queue, self.tick, self.refill = list(hand), list(queue), tick, refill

    def copy(self):
        return _Cycle(self.hand, self.queue, self.tick, self.refill)

    def advance(self, tick):
        while self.tick < tick:
            self.tick += 1
            self.refill = max(0, self.refill - 50)
            if not self.refill and None in self.hand and self.queue:
                self.hand[self.hand.index(None)] = self.queue.pop(0)
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350

    def play(self, card):
        self.hand[self.hand.index(card)] = None
        self.queue.append(card)


def own_invariant_breaks(own, deck):
    """[] when `own` is a state the engine can hold for this deck: 4 hand slots of distinct deck cards or None, the
    cycle = exactly the other deck cards (4 with a full hand; the played card waits at its back during a refill),
    next = cycle[0] not in the hand. Else the list of broken rules."""
    hand, cycle, out = list(own['hand']), list(own['cycle']), []
    held = [c for c in hand if c is not None]
    if len(hand) != 4:
        out.append('hand_slots')
    if len(set(held)) != len(held):
        out.append('hand_duplicate')
    if set(held) - set(deck) or set(cycle) - set(deck):
        out.append('off_deck')
    if len(set(cycle)) != len(cycle) or set(cycle) & set(held) or len(cycle) + len(held) != 8:
        out.append('cycle')
    if cycle and cycle[0] in held:
        out.append('next_in_hand')
    return out


def deck_state_breaks(state):
    """The same structural rules for any player dict a search root receives (the opponent's belief sample has no
    deck to compare with): distinct hand cards, cycle disjoint from them, hand + cycle = 8 cards."""
    hand, cycle = list(state.get('hand') or ()), list(state.get('cycle') or ())
    held = [c for c in hand if c is not None]
    out = []
    if len(hand) != 4:
        out.append('hand_slots')
    if len(set(held)) != len(held):
        out.append('hand_duplicate')
    if len(set(cycle)) != len(cycle) or set(cycle) & set(held) or len(cycle) + len(held) != 8:
        out.append('cycle')
    return out


class OwnTracker:
    """Own hand/next/cycle: TRACKED exactly from the opening order and our own plays (own information), with the HUD
    used only where the tracker is genuinely uncertain. Every information() gets a state the engine can hold
    (own_invariant_breaks == []), whatever perception reads.

    - The prior hand and our own plays are known, so a slot changes only after our own play of that slot (engine
      dynamics, _Cycle). A HUD reading that disagrees (a duplicated card, an off-deck card, next = a held card, an
      empty/unread slot, a plausible but wrong card) is overridden by the tracked state; each overridden slot and
      next is counted in stats (own_fix:*).
    - The order of the opening queue past `known` (LiveSession: hand + next = 5 known; the other 3 come from the
      deck order) is unknown. Each ordering is a hypothesis; every HUD reading scores them (a mismatch costs the
      slot's confidence, min(prob, .98); no prob = .98) and the lowest cumulative cost wins (ties: the given
      order). So the HUD only decides what the play history cannot: which unknown card is next / was drawn.
    - Recovery when the tracker itself is wrong (a mid-match start with a guessed order, a missed own play):
      (a) an own play of a card no hypothesis holds re-anchors on the HUD (own_reanchor_play); (b) a VALID HUD state
      (4 distinct deck cards, next not held) that differs from the tracked one and reads the same on
      `reanchor_polls` consecutive calls re-anchors on it (own_reanchor_hud). Under the measured noise (1.2% per
      slot per frame, a random other deck card) (b) essentially never fires on a correct tracker.
    Fair information: reads only our deck, our HUD and our own plays."""
    reanchor_polls = 4
    cap = .98

    def __init__(self, deck, stats=None, order=None, known=5):
        if len(deck) != 8 or len(set(deck)) != 8:
            raise ValueError('own deck must be 8 distinct cards')
        self.deck, self.played, self.last_play = list(deck), [], None
        self.stats = Counter() if stats is None else stats
        self.reset(order or deck, known)

    def reset(self, order, known=5):
        """Opening order (hand[:4] + queue); entries past `known` have unknown relative order."""
        order = list(order)
        if sorted(order) != sorted(self.deck):
            raise ValueError('own order must be a permutation of the deck')
        self._reset_from(order[:4], order[4:], 0, 0, max(0, known - 4))

    def _reset_from(self, hand, queue, tick, refill, known_queue):
        """Hypotheses: the slots exactly as given; queue[:known_queue] fixed, every ordering of the rest."""
        import itertools
        head, tail = list(queue[:known_queue]), list(queue[known_queue:])
        perms = [list(p) for p in itertools.permutations(tail)] if len(tail) <= 4 else [tail]
        self.hyps = [_Cycle(hand, head + p, tick, refill) for p in perms]
        self.cost = [0.]*len(self.hyps)
        self.best, self._streak, self._last_valid = 0, 0, None

    @property
    def hand(self):
        return list(self.hyps[self.best].hand)

    def play(self, tick, card):
        if card in self.played:
            self.played.remove(card)
        self.played.append(card)
        self.last_play = tick
        for h in self.hyps:
            h.advance(max(tick, h.tick))
        keep = [i for i, h in enumerate(self.hyps) if card in h.hand]
        if not keep:
            # The tracker lost this card (mid-match start / missed play): put it into the hand where the HUD last
            # saw it (else the first slot the HUD disagreed on, else an empty slot, else slot 0), then play it.
            b = self.hyps[self.best].copy()
            raw = self._last_raw or [None]*4
            slot = next((i for i, c in enumerate(raw) if c == card), None)
            if slot is None:
                slot = next((i for i in range(4) if raw[i] is not None and raw[i] != b.hand[i]),
                            b.hand.index(None) if None in b.hand else 0)
            out = b.hand[slot]
            b.queue = [out if c == card else c for c in b.queue] if out is not None else [c for c in b.queue if c != card]
            b.hand[slot] = card
            self._reset_from(b.hand, b.queue, b.tick, b.refill, len(b.queue))
            self.stats['own_reanchor_play'] += 1
            keep = [0]
        elif len(keep) < len(self.hyps):
            self.stats['own_order_pruned_by_play'] += len(self.hyps) - len(keep)
        self.hyps = [self.hyps[i] for i in keep]
        self.cost = [self.cost[i] for i in keep]
        self.best = min(range(len(self.hyps)), key=lambda i: (self.cost[i], i))
        for h in self.hyps:
            h.play(card)

    _last_raw = None

    def own(self, tick, elixir, hand, next_card, probs=None, next_prob=None):
        raw = [c for c in list(hand)[:4]] + [None]*(4-len(list(hand)[:4]))
        probs = list(probs or [])[:4] + [None]*(4-len(list(probs or [])[:4]))
        self._last_raw = raw
        for h in self.hyps:
            h.advance(tick)
        w = [self.cap if p is None else min(float(p), self.cap) for p in probs]
        wn = self.cap if next_prob is None else min(float(next_prob), self.cap)
        for k, h in enumerate(self.hyps):
            c = sum(w[i] for i in range(4) if raw[i] is not None and raw[i] != h.hand[i])
            if next_card is not None and h.queue and next_card != h.queue[0]:
                c += wn
            self.cost[k] += c
        best = min(range(len(self.hyps)), key=lambda i: (self.cost[i], i))
        if best != self.best:
            self.stats['own_order_switch'] += 1
            self.best = best
        b = self.hyps[best]
        # (b) re-anchor on a persistent valid HUD state the tracker contradicts
        valid = (None not in raw and len(set(raw)) == 4 and not set(raw) - set(self.deck)
                 and next_card in self.deck and next_card not in raw)
        state = (tuple(raw), next_card) if valid else None
        if state is not None and state != (tuple(b.hand), b.queue[0] if b.queue else None):
            self._streak = self._streak + 1 if state == self._last_valid else 1
        else:
            self._streak = 0
        self._last_valid = state
        if self._streak >= self.reanchor_polls:
            queue = [next_card] + [c for c in b.queue if c not in raw and c != next_card]
            queue += [c for c in self.deck if c not in raw and c not in queue]
            self._reset_from(raw, queue, b.tick, b.refill, 1)
            self.stats['own_reanchor_hud'] += 1
            b = self.hyps[0]
        out_hand, cycle = list(b.hand), list(b.queue)
        self._count(raw, next_card, out_hand, cycle)
        own = dict(elixir=float(elixir), hand=out_hand, cycle=cycle, refill=int(b.refill))
        if own_invariant_breaks(own, self.deck):      # by construction never; counted so a regression shows
            self.stats['own_invariant_break'] += 1
        return own

    def _count(self, raw, next_card, hand, cycle):
        s, fixed = self.stats, 0
        s['own_hud_frames'] += 1
        for i, c in enumerate(raw):
            if c == hand[i]:
                continue
            kind = ('missing' if c is None else 'off_deck' if c not in self.deck else
                    'duplicate' if raw.count(c) > 1 else 'empty' if hand[i] is None else 'slot')
            s[f'own_fix:{kind}'] += 1
            fixed += 1
        nxt = cycle[0] if cycle else None
        if next_card != nxt:
            kind = ('next_missing' if next_card is None else 'next_off_deck' if next_card not in self.deck else
                    'next_in_hand' if next_card in raw or next_card in hand else 'next')
            s[f'own_fix:{kind}'] += 1
            fixed += 1
        if fixed:
            s['own_fix'] += fixed
            s['own_fix_frames'] += 1


class LiveTranslator(Translator):
    """Perception records -> Information. One instance per match; feed records in time order."""
    sanitize = True       # card-level units must be cards their owner can have (board_card_ok)

    def __init__(self, rt, own_deck, *, vocab=None, unknown_card='drop', proxy=None, seat=0, plays_from='births',
                 card_level=True, tracker_kw=None, legacy_mapping_compat=_COMPAT_UNSET):
        if unknown_card not in ('drop', 'proxy'):
            raise ValueError(unknown_card)
        if seat != 0:
            raise ValueError('records are in our own frame: the live seat is always 0')
        # Translator.__init__ needs RoyaleSim; only the attributes observation()/_row() read are set here.
        from bot.players.royalesim_translate import complete_vocab
        self.rt, self.vocab = rt, complete_vocab(rt, vocab or load_vocab(rt))
        self.builder, self.costs = rt.R.builder, rt.R.costs
        self.templates = {(int(t), ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity').index(k))
                          for (t, k) in rt.R.templates}
        self.statics = {k: (v['cols'], v['level'], v['motion']) for k, v in self.vocab['statics'].items()}
        self.units = {k: tuple(v) for k, v in self.vocab['units'].items()}
        self.lower_units = {k.lower(): v for k, v in self.units.items()}
        self.champions = {c.lower() for c in self.vocab['champion_units']}
        self.lower_tokens = {n.lower(): n for n in self.builder.token_names if not n.startswith('<')}
        self.stats = Counter()
        # A reviewed launch may opt in without changing the driver's interface.
        # Explicit None overrides the environment. Observation data cannot select policy.
        from_env = legacy_mapping_compat is _COMPAT_UNSET
        if from_env:
            legacy_mapping_compat = os.environ.get('CLASHER_LIVE_LEGACY_MAPPING_COMPAT') or None
        if legacy_mapping_compat not in (None, 'v1'):
            raise ValueError(f'unknown legacy_mapping_compat: {legacy_mapping_compat!r}')
        self.legacy_mapping_compat = legacy_mapping_compat
        selected_by = ('environment' if os.environ.get('CLASHER_LIVE_LEGACY_MAPPING_COMPAT') else 'default') if from_env else 'constructor'
        self.projection_policy = dict(legacy_mapping_compat=legacy_mapping_compat, selected_by=selected_by,
                                      exact_body_tracking='strict', legacy_proxy_tracking='original_family_relabel_v1')
        if legacy_mapping_compat:
            self.stats['projection_policy:legacy_mapping_compat:v1'] = 1
        self.last_projections, self.last_play_projections, self.derived_play_projections = [], [], []
        self._projection_sources = {}
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
        self.own_tracker = OwnTracker(own_deck, stats=self.stats)
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

    def configured_body(self, name, card, kind):
        """Resolve a canonical body against this card's public same-kind templates.

        Config stat names cover cases like GoblinHut_Rework without inventing a
        spelling rule. Ambiguous/unavailable identities remain unplaced.
        """
        if not self.cards.is_card(card) or not isinstance(name, str):
            return None
        aliases, digest = engine_body_aliases()
        self.projection_policy['engine_body_aliases_sha256'] = digest
        names = {name}
        alias_kind = aliases.get('kind_constraints', {}).get(name)
        if alias_kind in (None, ('Troop', 'Building')[kind]):
            names.update(aliases.get('aliases', {}).get(name, ()))
        preferred = self.body(name)
        candidates = []
        for b in sorted(self.cards.bodies_of(card)):
            if b[1] != kind or b not in self.templates:
                continue
            template = self.rt.R.templates.get((b[0], ('Troop', 'Building')[b[1]])) or {}
            if b == preferred or self.builder.token_names[b[0]] in names or template.get('stats', {}).get('name') in names:
                candidates.append(b)
        if len(candidates) == 1:
            return candidates[0]
        return preferred if preferred in candidates else None

    def project_unit(self, u):
        """Canonical observation -> separate backend capability projection, never a rewritten observation.

        The detector family is not spawn/deployment provenance. Templates alone do
        not make a card playable: its config must declare this body as main/child/death.
        Legacy stand-ins come only from explicit reviewed mapping data and opt-in policy.
        """
        result = dict(observed_body=u.get('cls'), observed_family=u.get('card'),
                      owner=u.get('owner'), x=u.get('x'), y=u.get('y'), observed_score=u.get('score'),
                      rawdetector=dict(u.get('rawdetector') or {}), disposition='unplaced',
                      reason=None, backend_card=None, backend_body=None, body_constraint=None,
                      tracking_semantics=None, effective_assigned_body=None, effective_tracked_body=None,
                      effective_track_id=None, effective_tracked_label=None, effective_deployment_card=None,
                      requested_proxy_body=None, requested_proxy_card=None)
        if u.get('observation_contract') != OBSERVATION_CONTRACT:
            result['reason'] = 'unsupported_observation_contract'
            return result
        def capable(body, card):
            return (body is not None and body in self.templates and self.cards.is_card(card)
                    and body in self.cards.bodies_of(card))
        expected_kind = {'troop': 0, 'building': 1}.get(u.get('kind'))
        if u.get('body_resolution') != 'resolved':
            result['reason'] = 'unresolved_observed_body'
        elif not isinstance(u.get('cls'), str) or not u['cls'].strip():
            result['reason'] = 'invalid_observed_body'
        elif expected_kind is None:
            result['reason'] = 'invalid_observed_kind'
        else:
            card = u.get('card')
            body = self.configured_body(u.get('cls'), card, expected_kind)
            if capable(body, card) and body[1] == expected_kind:
                result.update(disposition='exact', reason='verified_card_body', backend_card=card,
                              backend_body=body, body_constraint=body, tracking_semantics='exact_body')
                return result
            result['reason'] = 'unsupported_card_body'
            proxy = u.get('legacy_backend_proxy')
            if self.legacy_mapping_compat == 'v1' and isinstance(proxy, dict):
                pc = proxy.get('card')
                pb = self.configured_body(proxy.get('body'), pc, expected_kind)
                if not proxy.get('origin'):
                    result['reason'] = 'missing_proxy_origin'
                elif capable(pb, pc) and pb[1] == expected_kind:
                    result.update(disposition='legacy_proxy', reason='explicit_legacy_mapping_compat_v1',
                                  backend_card=pc, backend_body=pb, proxy_origin=proxy['origin'],
                                  tracking_semantics='legacy_mapping_compat_v1',
                                  requested_proxy_body=pb, requested_proxy_card=pc)
                    return result
                else:
                    result['reason'] = 'invalid_proxy_card_body_or_kind'
            elif proxy is not None:
                result['reason'] = 'legacy_mapping_compat_disabled'
        return result

    def _note_projection(self, p):
        self.stats[f'projection:{p["disposition"]}:{p["reason"]}'] += 1

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
            elif u.get('observation_contract') is not None:
                projection = self.project_unit(u)
                projection.update(input_index=i, tick=record['tick'], capture=record.get('capture', record.get('timestamp_ms')))
                self._note_projection(projection)
                self.last_projections.append(projection)
                mapped = projection['backend_body']
                projection.update(tracking_path='direct_body', effective_assigned_body=mapped)
                # Direct-body mode tracks facing by backend identity internally.
                if mapped is not None:
                    u = dict(u, **{'class': self.builder.token_names[mapped[0]]})
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
    def set_own_order(self, order, known=5):
        """Own opening order (hand[:4] + queue), as given to the players' MatchContext. Resets the stream guard and
        the own tracker; order[known:] has unknown relative order (scored by the HUD, OwnTracker)."""
        from imitation.evaluation.d1 import DerivedD1
        from own_cycle import OwnCycle
        if getattr(self, 'plays', None) and (self.plays[0] or self.plays[1]):
            raise ValueError('set the own order before any play is accepted')
        self.own_order = list(order)
        self.own_tracker.reset(self.own_order, known)
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
        self.last_projections, self.last_play_projections = [], []
        for i, u in enumerate(record.get('units', ())):
            if u.get('observation_contract') is not None:
                projection = self.project_unit(u)
                projection.update(input_index=i, tick=record['tick'], capture=record.get('capture', record.get('timestamp_ms')))
                self.last_projections.append(projection)
                card, body = projection['backend_card'], projection['backend_body']
                if body is None:
                    self._note_projection(projection)
                    continue
                owner = 0 if int(u['owner']) == 0 else 1
                if self.sanitize and not self.board_card_ok(card, owner):
                    projection.update(disposition='unplaced', reason='board_card_guard', backend_body=None,
                                      body_constraint=None)
                    self._note_projection(projection)
                    continue
                self._note_projection(projection)
                # A proxy requests a backend label, not a truthful observed body.
                # Its explicit v1 policy retains original family/relabel/composition
                # tracking, whose effective assigned body can differ from that request.
                # Only exact observations impose a body constraint. Field 6 remains
                # independently supplied provenance, never inferred from either body.
                units.append((card, owner, float(u['x']), float(u['y']), u.get('score'),
                              u.get('spawn_card'), projection['body_constraint']))
                idx.append(i)
                continue
            card = u.get('card') or u.get('cls') or u.get('class')
            if not self.cards.is_card(card):
                proxy = self.proxy.get(card) if self.unknown_card == 'proxy' else None
                if proxy and self.cards.is_card(proxy):
                    card = proxy
                else:
                    self.stats[f'unmapped_card_unit:{card}'] += 1
                    continue
            owner = 0 if int(u['owner']) == 0 else 1
            if self.sanitize and not self.board_card_ok(card, owner):
                continue
            units.append((card, owner, float(u['x']), float(u['y']), u.get('score')))
            idx.append(i)
        own = {t['side']: t['alive'] for t in self.towers(record) if t['owner'] == 0 and t['kind'] == 'princess'}
        got, plays = self.tracker.update(record['tick'], units, own)
        assigned = [(None, (0., 0.))]*len(record.get('units', ()))
        for i, a in zip(idx, got):
            assigned[i] = a
        # Retain observed source independently of the legacy backend play/card.
        alive = {t.id for t in self.tracker.live + self.tracker.dead}
        self._projection_sources = {k: v for k, v in self._projection_sources.items() if k in alive}
        by_index = {}
        cursor = iter(self.last_projections)
        for i, u in enumerate(record.get('units', ())):
            if u.get('observation_contract') is not None:
                by_index[i] = next(cursor)
        for i, tid in zip(idx, self.tracker.last_tracks):
            if tid is not None and i in by_index:
                p = by_index[i]
                identity = self.tracker.identity(tid)
                p.update(tracking_path='births', effective_assigned_body=assigned[i][0],
                         effective_track_id=tid, effective_tracked_body=identity.body,
                         effective_tracked_label=identity.label, effective_deployment_card=identity.card)
                if p['disposition'] == 'legacy_proxy' and p['backend_body'] != assigned[i][0]:
                    self.stats['projection:legacy_proxy:effective_assigned_body_differs'] += 1
                key = (p['observed_body'], p['observed_family'], p['disposition'], p['backend_card'])
                self._projection_sources.setdefault(tid, {})[key] = dict(p)
        for owner, card, x, y, tick in plays:
            sources = {}
            for deployment in self.tracker.played:
                if (deployment['owner'], deployment['card'], deployment['t0']) == (owner, card, tick):
                    for tid in deployment['ids']:
                        sources.update(self._projection_sources.get(tid, {}))
            self.last_play_projections.append(dict(owner=owner, backend_card=card, tick=tick,
                                                   sources=list(sources.values())))
        return assigned, plays

    def board_card_ok(self, card, owner):
        """Card-consistency guard (the deck rule; fair information): an on-board unit must be a card its owner can
        have. Own units: our own 8-card deck (exact). Opponent units: a card it has been seen playing, or any card
        while fewer than 8 distinct opponent cards are known. Anything else is a perception error (card confusion or
        a false positive) and is DROPPED, counted in stats['board_dropped:<owner>:<card>']. Not flipped to the other
        owner: perception reads the owner from the health-bar colour, and the measured channel's errors are in the
        card, so a flip would put a phantom enemy where our own unit stands. A one-frame misread of a tracked unit
        leaves that track alive for `ttl` ticks. Without this, an off-deck unit reaches the search root with no
        entry in a deck-card config (lopp_fast 'fc') and the native panics (c56.rs electro_land, Electro Spirit).
        Reads only our deck and the accepted public plays."""
        if owner == 0:
            ok = card in self.own_tracker.deck
        else:
            revealed = {n for _, n in self.plays[1]}
            ok = card in revealed or len(revealed) < 8
            if ok and card not in revealed:
                self.stats['board_unrevealed_opp_kept'] += 1
        if not ok:
            self.stats[f'board_dropped:{owner}:{card}'] += 1
            self.stats['board_dropped'] += 1
        return ok

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
        probs = next_prob = None
        if isinstance(h, dict):
            cards, nxt = list(h.get('cards', ())), h.get('next')
            probs, next_prob = h.get('probs'), h.get('next_prob')
        else:
            cards, nxt = list(h)[:4], record.get('next')
        for c in cards + [nxt]:
            if c is not None and c not in self.costs:
                self.stats[f'own_non_c56:{c}'] += 1
        return self.own_tracker.own(record['tick'], float(record.get('elixir', 0.)), cards, nxt, probs, next_prob)

    def information(self, record):
        """One frame -> fair_player.Information. Records must arrive in non-decreasing tick order."""
        from fair_player import Information
        record = dict(record)
        if not self.card_level:
            self.last_projections, self.last_play_projections = [], []
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
            for n, (owner, card, x, y, tick) in enumerate(plays):
                if owner == 1 and self.plays_from == 'births':
                    events.append(dict(owner=1, card=card, x=x, y=y, tick=tick, derived=True))
                    self.derived_plays.append((owner, card, x, y, tick))
                    self.derived_play_projections.append(self.last_play_projections[n])
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
    returned action and keeps feeding records; the pending command is completed when the raw own HUD shows the
    reserved card left its slot on `confirm_polls` polls (or an own play event arrives), and expires after `expire`
    ticks. The bot sees the TRACKED own hand (OwnTracker), never the raw HUD."""
    confirm_polls = 2

    def __init__(self, rt, player, own_deck, *, seed=0, command_delay=27, expire=90, translator=None):
        from bot.players.base import MatchContext
        from clasher.analysis.loss_review.delay_fixes import CommandQueue
        self.rt, self.player = rt, player
        self.tr = translator or LiveTranslator(rt, own_deck)
        self.ch = CommandQueue(command_delay, 1)
        self.expire, self.wait_until, self.last_poll = expire, 0, None
        self.own_deck, self.seed, self.command_delay, self.started = list(own_deck), seed, command_delay, False
        self.log, self._buffer, self._evidence = [], [], 0

    def _reconcile(self, info):
        if not self.ch.pending:
            return
        c = self.ch.pending[0]
        # done when our play was accepted, or the TRACKED slot no longer holds the card (the tracker took the play
        # although the stream guard dropped it from the public rows, or re-anchored): the tracked hand moves only on
        # our plays, never on a single misread, so this cannot fire on HUD noise.
        if (any(t >= c.submitted and n == c.card for t, n in self.tr.plays[0])
                or info.own['hand'][c.action // 576] != c.card):
            self.ch.finish(True)
        elif info.tick - c.submitted > self.expire:
            self.ch.finish(False)

    def _confirm_pending(self, record, poll):
        """Our play of the pending command is known from the command itself once the RAW HUD shows the reserved card
        left its slot: the slot reads empty or a card the tracked hand does not hold elsewhere, on `confirm_polls`
        consecutive polls (a single misread slot, ~1% per frame, does not complete a command). Then the own play
        event is added to THIS poll's record, so the tracked hand, the own mirrors and the D1 rows all take it before
        the bot decides (the sanitised hand never shows a card that already left its slot)."""
        if not self.ch.pending:
            self._evidence = 0
            return
        c = self.ch.pending[0]
        slot = c.action // 576
        h = record.get('hand') or {}
        cards = list(h.get('cards', ())) if isinstance(h, dict) else list(h)[:4]
        raw = (cards + [None]*4)[slot]
        held = [x for i, x in enumerate(self.tr.own_tracker.hand) if i != slot and x is not None]
        if any(t >= c.submitted and n == c.card for t, n in self.tr.plays[0]):
            return
        self._evidence = self._evidence + 1 if raw != c.card and raw not in held else 0
        if self._evidence >= self.confirm_polls:
            self._evidence = 0
            row, col = divmod(c.action % 576, 18)
            record['events'] = list(record.get('events', ())) + [dict(owner=0, card=c.card, x=col+.5, y=row+.5,
                                                                      tick=poll)]
            self.tr.stats['own_play_confirmed_by_hud'] += 1

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
            if len(cards) != 4 or set(cards) - set(self.own_deck) or None in cards or len(set(cards)) != 4:
                self.tr.stats['opening_hand_waits'] += 1
                return None       # wait for a complete opening hand of 4 distinct deck cards
            order = cards + ([nxt] if nxt in self.own_deck and nxt not in cards else [])
            known = len(order)
            order += [c for c in self.own_deck if c not in order]
            self.tr.set_own_order(order, known=known)
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
        self._confirm_pending(record, poll)
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
