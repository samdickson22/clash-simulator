"""RoyaleSim state_json -> the fair public view our players consume (contract-v5 packet + own HUD).

Our players read `fair_player.Information(tick, seat, packet, own, events)`:
- packet: a ConfidenceAwareActorObservation (contract v5), which our engine builds with
  `ContractV5ObservationBuilder.build_public(battle, seat)`. Here the same ActorObservation
  arrays are filled from RoyaleSim's public rows and the SAME `project_public_v5` projection
  runs, so every non-v5 column is zeroed and validated exactly as in our harness.
- own: dict(elixir, hand, cycle, refill), the player's own HUD, from RoyaleSim's
  `players[seat]` (elixir, hand) plus the own-cycle tracker (deck order is own information).
- events: accepted ENEMY card plays as derived_public_state.PublicEvent, from the commands
  the harness itself applied (never from RoyaleSim's opponent player record).

Fair-information rule: from `players[1-seat]` only crowns, tower_hp and tower_max_hp (public)
are read. The opponent's hand, next_card, deck, pending, elixir_milli are never read.
Enemy units RoyaleSim flags underground (bit 0) or invisible (bit 1) are dropped, as contract
v5 `hidden_from_enemy` drops a tunnelling Miner or a cloaked Ghost; a hidden Tesla (bit 2)
stays visible as its trapdoor, as in our engine.

Field map (our entity row <- RoyaleSim):
  0,1 x,y           <- x,y subtiles / 18000 tiles (/18, /32), rotated 180 deg for seat 1
  2,3 own/enemy     <- team == seat
  4-8 kind          <- vocabulary (units by unit_type name, spells by card+motion, shots by firer)
  9   hp_fraction   <- hp/max_hp (units, towers); our engine's constant for effects/shots
  23-26,30 statics  <- our engine's value for the same body (card data; royalesim_vocab.json)
  27,28 motion      <- as our engine fills it for that body (vocab 'motion'): unit `facing`
                       (normalised) for 'dynamic' bodies, the owner's forward for 'forward' ones
                       (our spells/shots), 0 for 'none'; flight direction (aim - pos) only if a
                       shot/spell body were dynamic
  levels            <- our engine's public level for that body (11, towers their publicLevel)
Globals: 0,1 progress = tick/6000; 2 double (>=120 s), 3 triple (>=240 s), 4 overtime (>=180 s),
  each from the start of the current tick as in our engine; 5 own elixir/10; 6,7 crowns;
  8-13 tower HP fractions (own left/right/king, enemy left/right/king; lanes mirrored for
  seat 1); 16 own refill/1000; 17 enemy king alive. 14,15 champion clocks are 0 (abilities are
  never pressed on either side) and exposed only while an own champion stands, as v5 does.
Not mappable, documented defaults (all outside v5, so zeroed by the projection anyway):
  10 shield, 11 airborne, 12-22 status flags/timers, 29 effect progress, 31 tower_active.
Dropped rows (counted in `stats`): RoyaleSim bodies with no counterpart in our engine
(the Goblin Hut's garrison sprite), shots whose firer has no projectile in our engine, any
row whose (token, kind) has no public template in Resources (would make R.root fail closed).
"""
from __future__ import annotations

from collections import Counter
import math

import numpy as np

SUBTILES_PER_TILE = 18000
BOARD_W, BOARD_H = 18, 32
TICK_SECONDS = 0.05
DOUBLE_S, OVERTIME_S, TRIPLE_S, TIEBREAKER_S = 120.0, 180.0, 240.0, 300.0
UNDERGROUND, INVISIBLE = 1, 2
MOVING_SPELL_MOTIONS = (0, 1, 2)    # FLIGHT, AIRBORNE, ROLLING


def _unit(v):
    return min(1.0, max(0.0, float(v)))


class OwnCycleView:
    """Own hand/cycle/refill: frozen OwnCycle fed with own accepted plays, reconciled
    against RoyaleSim's own hand (authoritative) and next card each observation."""

    def __init__(self, ordered_deck):
        from imitation.evaluation.paths import setup
        setup()                                  # puts the frozen runtime_dependencies (own_cycle) on sys.path
        from own_cycle import OwnCycle
        self.tracker = OwnCycle(list(ordered_deck))
        self.mismatch = Counter()

    def play(self, tick, name):
        self.tracker.play(tick, name)

    def own(self, tick, elixir, hand, next_card):
        t = self.tracker
        t.advance(tick)
        if list(hand) != list(t.hand):
            self.mismatch['hand'] += 1
        # Cards the tracker still holds but RoyaleSim's hand does not are next in the queue.
        held = [c for c in t.hand if c is not None and c not in hand]
        cycle = held + [c for c in t.queue if c not in hand]
        if cycle and next_card is not None and cycle[0] != next_card:
            self.mismatch['next'] += 1
            cycle.remove(next_card)
            cycle.insert(0, next_card)
        if len(cycle) + sum(c is not None for c in hand) != 8:
            raise AssertionError(f'own cycle lost a card: hand={hand} cycle={cycle}')
        return dict(elixir=float(elixir), hand=list(hand), cycle=cycle, refill=int(t.refill))


def complete_vocab(rt, vocab):
    """Add runtime object rows absent from the external-simulator vocabulary.

    Preserve every measured row and mapping. These defaults name engine
    objects even when an external perception schema cannot produce them yet.
    """
    import copy
    vocab = copy.deepcopy(vocab)
    kinds = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
    objects = vocab.setdefault('objects', {})
    for (token, kind), template in rt.R.templates.items():
        index = kinds.index(kind)
        objects.setdefault(f'{token}/{index}', [token, index])
        cols = template.get('public_static')
        if cols is not None:
            vocab['statics'].setdefault(f'{token}/{index}', dict(cols=cols, level=11, motion='dynamic',
                                        name=rt.R.builder.token_names[token], kind=kind))
        if index < 2:
            vocab['units'].setdefault(rt.R.builder.token_names[token], [token, index])
    def identity(template):
        for ns, names in template.get('public_identity', ()):
            token = next((rt.R.builder.token_id(n, namespace=ns) for n in names
                          if rt.R.builder.token_id(n, namespace=ns) > 1), 1)
            kind = template['entity_kind']
            if (token, kinds[kind]) in rt.R.templates:
                return [token, kind]
        return None
    # External rows provide a source card and a motion rather than an exact
    # payload ID. For previously unmapped rows, use that card's deterministic
    # primary public carrier. The exact-ID registry above retains every child.
    for card, cfg in rt.R.config['cards'].items():
        if card.startswith('level12:'):
            continue
        primary = next((identity(t) for group in cfg['units'] for t in group
                        if t['entity_kind'] >= 2 and identity(t) is not None), None)
        if primary:
            for motion in range(7):
                vocab['spells'].setdefault(f'{card}/{motion}', primary)
        stats = rt.R.builder.loader.get_card(card)
        shot = getattr(stats, 'projectile_data', None) or {}
        token = rt.R.builder.token_id(shot.get('name'), namespace='projectile')
        if (token, 'Projectile') in rt.R.templates:
            vocab['projectiles'].setdefault(card, token)
    for table in ('death_areas', 'death_objects', 'spirit_areas', 'spawn_areas'):
        for card, template in rt.R.config.get(table, {}).items():
            if card.startswith('level12:'):
                continue
            primary = identity(template)
            if primary:
                for motion in range(7):
                    vocab['spells'].setdefault(f'{card}/{motion}', primary)
    return vocab


class Translator:
    def __init__(self, rt, vocab, catalogue):
        import royalesim as rs
        from .royalesim_adapter import our_card
        vocab = complete_vocab(rt, vocab)
        self.rt, self.vocab = rt, vocab
        self.builder = rt.R.builder
        self.costs = rt.R.costs
        self.card_of = [our_card(row[0]) for row in catalogue]     # RoyaleSim card id -> our name
        self.F = {f: i for i, f in enumerate(rs.ENTITY_FIELDS)}
        self.types = None
        self.templates = {(int(t), ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity').index(k))
                          for (t, k) in rt.R.templates}
        self.statics = {k: (v['cols'], v['level'], v['motion']) for k, v in vocab['statics'].items()}
        self.units = {k: tuple(v) for k, v in vocab['units'].items()}
        self.lower_units = {k.lower(): v for k, v in self.units.items()}
        self.champions = {c.lower() for c in vocab['champion_units']}
        self.lower_tokens = {n.lower(): n for n in self.builder.token_names if not n.startswith('<')}
        self.stats = Counter()

    def bind(self, battle):
        import json
        self.types = json.loads(battle.unit_types_json())

    # -- entity rows ---------------------------------------------------------------------
    def _row(self, seat, token, kind, team, x, y, hp_fraction, motion):
        from clasher.rl.public_observation import ENTITY_FEATURE_NAMES
        row = np.zeros(len(ENTITY_FEATURE_NAMES), dtype=np.float32)
        x, y = x/SUBTILES_PER_TILE, y/SUBTILES_PER_TILE
        mx, my = motion
        if seat == 1:
            x, y, mx, my = BOARD_W-x, BOARD_H-y, -mx, -my
        row[0], row[1] = _unit(x/BOARD_W), _unit(y/BOARD_H)
        row[2], row[3] = float(team == seat), float(team != seat)
        row[4+kind] = 1.
        cols, level, mode = self.statics.get(f'{token}/{kind}', (None, 0, 'dynamic'))
        if cols is None:
            self.stats['static_default'] += 1
            cols = {}
        for c, v in cols.items():
            row[int(c)] = v
        if hp_fraction is not None:
            row[9] = _unit(hp_fraction)
        if mode == 'forward':       # our engine: the owner's forward, whatever the flight
            row[27], row[28] = 0., (1. if team == seat else -1.)
        elif mode == 'dynamic':
            magnitude = math.hypot(mx, my)
            if magnitude > 1e-6:
                row[27], row[28] = max(-1., min(1., mx/magnitude)), max(-1., min(1., my/magnitude))
        return row, level

    def _rows(self, state, seat):
        F, rows = self.F, []
        towers = {0: [], 1: []}
        for e in state['entities']:
            team, kind = e[F['team']], e[F['kind']]
            if kind in (2, 3):
                towers[team].append((e[F['x']], e[F['y']], kind))
        for e in state['entities']:
            team, kind = e[F['team']], e[F['kind']]
            if team != seat and e[F['status_flags']] & (UNDERGROUND | INVISIBLE):
                self.stats['hidden_enemy'] += 1
                continue
            if kind in (2, 3):
                token, ours = self.vocab['towers'][str(kind)]
            else:
                name = self.types[e[F['unit_type']]]
                mapped = self.units.get(name) or self.lower_units.get(name.lower()) or self._lazy_unit(name, kind)
                if mapped is None:
                    self.stats[f'unmapped_unit:{name}'] += 1
                    continue
                token, ours = mapped
            hp = e[F['hp']] / max(1, e[F['max_hp']])
            fx, fy = e[F['facing']]
            rows.append((token, ours, team, e[F['x']], e[F['y']], hp, (fx, fy)))
        for sp in state['spells']:
            team, card, motion = sp[0], sp[1], sp[2]
            key = f'{self.card_of[card] if card >= 0 else card}/{motion}'
            mapped = self.vocab['spells'].get(key)
            if mapped is None:
                self.stats[f'unmapped_spell:{key}'] += 1
                continue
            x, y, ax, ay = sp[3], sp[4], sp[5], sp[6]
            direction = (ax-x, ay-y) if motion in MOVING_SPELL_MOTIONS else (0, 0)
            rows.append((mapped[0], mapped[1], team, x, y, None, direction))
        for p in state['projectiles']:
            team, x, y, ax, ay, firer = p[0], p[1], p[2], p[3], p[4], p[7]
            if firer == -1:
                key = self._tower_firer(towers[team], x, y, ax, ay)
            else:
                key = self.card_of[firer] if firer >= 0 else None
            token = self.vocab['projectiles'].get(key) if key else None
            if token is None:
                label = 'no_counterpart' if key in self.vocab.get('no_counterpart_firers', ()) else 'unmapped'
                self.stats[f'{label}_projectile:{key}'] += 1
                continue
            rows.append((token, 2, team, x, y, None, (ax-x, ay-y)))
        return self._resolved_rows(rows, seat)

    def _resolved_rows(self, rows, seat):
        """Format resolved public carriers through the same object registry.

        Source-card/motion schemas may alias several engine child objects;
        exact public carriers and source mappings share this final lookup.
        """
        out = []
        for token, kind, team, x, y, hp, motion in rows:
            if (token, kind) not in self.templates or f'{token}/{kind}' not in self.vocab['objects']:
                self.stats[f'no_template:{token}/{kind}'] += 1
                continue
            row, level = self._row(seat, token, kind, team, x, y, hp, motion)
            key = (kind, int(team != seat), token, round(float(row[1]), 5), round(float(row[0]), 5))
            out.append((key, token, row, level))
        return out

    def _lazy_unit(self, name, kind):
        """A body the vocabulary demos never showed: the same-named troop/building token of ours."""
        if name in self.vocab.get('no_counterpart_units', ()):
            return None
        ns, ours = ('troop_body', 0) if kind == 0 else ('building_body', 1)
        canonical = self.lower_tokens.get(name.lower(), name)
        token = int(self.builder.token_id(canonical, namespace=ns))
        if token <= 1 or (token, ours) not in self.templates:
            return None
        self.units[name] = (token, ours)
        self.stats[f'lazy_unit:{name}'] += 1
        return self.units[name]

    @staticmethod
    def _tower_firer(towers, x, y, ax, ay):
        """A crown-tower shot: the own tower on whose line to the aim the shot lies."""
        if not towers:
            return 'princess'
        def slack(t):
            tx, ty, _ = t
            return math.hypot(tx-x, ty-y) + math.hypot(ax-x, ay-y) - math.hypot(ax-tx, ay-ty)
        return 'king' if min(towers, key=slack)[2] == 2 else 'princess'

    # -- observation -----------------------------------------------------------------------
    def observation(self, state, seat, own, plays):
        """plays: {seat: [(tick, card_name), ...]} accepted public plays of both seats."""
        from clasher.rl.structured_obs import ActorObservation
        from clasher.rl.own_card_history import AcceptedOwnPlay
        from clasher.rl.contract_v5 import project_public_v5
        b = self.builder
        tick = state['tick']
        rows = self._rows(state, seat)
        rows.sort(key=lambda item: item[0])
        ids, features, mask = b._pack_entity_rows([(k, t, r) for k, t, r, _ in rows])
        levels = np.zeros(b.max_entities, dtype=np.int64)
        for i, (_, _, _, level) in enumerate(rows):
            levels[i] = level
        hand_names = list(own['hand'][:4]) + [None]*(4-len(own['hand'][:4]))
        hand_names.append(own['cycle'][0] if own['cycle'] else None)
        hand_ids = np.asarray([0 if n is None else b.token_id(n) for n in hand_names], dtype=np.int64)
        hand_levels = np.asarray([0 if n is None else 11 for n in hand_names], dtype=np.int64)
        enemy = plays[1-seat]
        history_ids = np.zeros(b.public_history_slots, dtype=np.int64)
        history_ages = np.zeros(b.public_history_slots, dtype=np.float32)
        for i, (played, name) in enumerate(reversed(enemy[-b.public_history_slots:])):
            history_ids[i] = b.token_id(name)
            history_ages[i] = _unit(max(0, tick-played)*TICK_SECONDS/60.)
        seen_ids = np.zeros(b.public_seen_card_slots, dtype=np.int64)
        seen = []
        for _, name in enemy:
            if name not in seen and len(seen) < b.public_seen_card_slots:
                seen_ids[len(seen)] = b.token_id(name)
                seen.append(name)
        last = plays[seat][-1][1] if plays[seat] else None
        obs = ActorObservation(
            entity_ids=ids, entity_features=features, entity_mask=mask, hand_ids=hand_ids,
            global_features=self.globals(state, seat, own),
            opponent_history_ids=history_ids, opponent_history_ages=history_ages,
            opponent_seen_card_ids=seen_ids,
            own_last_play=AcceptedOwnPlay(last, int(self.costs[last])) if last else None,
            terminal=bool(state['game_over']), board_rotated=seat == 1,
            entity_levels=levels, entity_level_confidence=(levels != 0).astype(np.float32),
            hand_levels=hand_levels, hand_level_confidence=(hand_levels > 0).astype(np.float32))
        return project_public_v5(obs, champion_button=self.champion_button(state, seat))

    def champion_button(self, state, seat):
        if state['game_over']:
            return False
        F = self.F
        return any(e[F['team']] == seat and e[F['deploy_ticks']] == 0 and e[F['hp']] > 0
                   and self.types[e[F['unit_type']]].lower() in self.champions for e in state['entities'])

    def globals(self, state, seat, own):
        tick = state['tick']
        start = max(0, tick-1)*TICK_SECONDS      # phases from the start of the current tick
        progress = _unit(tick*TICK_SECONDS/TIEBREAKER_S)
        me, them = state['players'][seat], state['players'][1-seat]

        def frac(p, slot):
            return _unit(p['tower_hp'][slot]/max(1, p['tower_max_hp'][slot]))
        left, right = (1, 2) if seat == 0 else (2, 1)
        return np.asarray([
            progress, 1.-progress, float(start >= DOUBLE_S), float(start >= TRIPLE_S),
            float(start >= OVERTIME_S), _unit(own['elixir']/10.), me['crowns']/3., them['crowns']/3.,
            frac(me, left), frac(me, right), frac(me, 0), frac(them, left), frac(them, right), frac(them, 0),
            0., 0., _unit(own['refill']/1000.), float(them['tower_hp'][0] > 0)], dtype=np.float32)

    def information(self, state, seat, own, plays, events):
        from fair_player import Information
        return Information(state['tick'], seat, self.observation(state, seat, own, plays), own, tuple(events))
