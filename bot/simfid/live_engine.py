"""Our Python match engine as a segment simulator for LIVE fidelity (simfid, exploration).

The engine is whichever `clasher` package is first on sys.path (src/clasher, engine-cards/py/src or a runtime root's
src), with CLASHER_ROOT selecting its gamedata. Levels go through bot.levels.match exactly as play_match's
level-aware true game does: PlayerState(card_levels, tower_level), install_engine_levels(), tower_curve().

A segment starts on a QUIET public record (no troops or buildings on the board, towers only): the battle is
fast-forwarded idle to t0, crown towers get the observed HP (fraction x the level's max HP; dead towers destroyed,
the king activated when damaged or a princess is down). Every play then goes through the engine's own deploy path
(hand, placement, formations, levels) at its tick. Interventions are counted, never hidden: hand_forced (card
not in hand: moved there), elixir_topped, deploy_retried / deploy_dropped (refused for 10 ticks).
"""
from __future__ import annotations

import random
import sys
from collections import Counter, deque

from bot.simfid.live_data import Game, Play, Record


def _root_tracking(battle, roots, Entity, Spell):
    """Tag each new entity with (root card, main?) at insertion: main = put down by deploy_card itself."""

    def infer(new):
        f = sys._getframe(2)
        while f is not None:
            loc = f.f_locals
            if f.f_code.co_name == 'deploy_card' and 'card_name' in loc:
                return loc['card_name'], True
            s = loc.get('self')
            if isinstance(s, Spell):
                return s.name, False
            for var in ('self', 'source_entity', 'parent', 'spawner', 'source'):
                o = loc.get(var)
                if isinstance(o, Entity) and o is not new and o.id in roots:
                    return roots[o.id][0], False
            f = f.f_back
        return None, False

    class RootDict(dict):
        def __setitem__(self, k, v):
            if k not in self:
                roots[getattr(v, 'id', k)] = infer(v)
            super().__setitem__(k, v)

    battle.entities = RootDict(battle.entities)


W, H = 18.0, 32.0


class LiveSim:
    """Seats: we play in our NATIVE seat (game.seat). Records are in OUR frame (us at the bottom); when we were
    natively seat 1 the engine's frame is that rotated by 180 degrees (x -> 18 - x, y -> 32 - y), so seat-asymmetric
    rules (e.g. the side-1 back-row deploy bound) apply to the right player."""

    seat = 0

    def _to_engine(self, x, y):
        return (W - x, H - y) if self.seat == 1 else (x, y)

    _to_ours = _to_engine

    def _pid(self, side):        # our-frame owner (0 us, 1 opponent) -> engine player id
        return self.seat if side == 0 else 1 - self.seat

    def _owner(self, pid):       # engine player id -> our-frame owner
        return 0 if pid == self.seat else 1

    def __init__(self):
        import os
        crown = os.environ.get('SIMFID_CROWN_FROM_GAMEDATA', '')
        if crown:   # live16402 runtime pin, as bot.players.runtime.Runtime (before install_engine_levels copies pins)
            from clasher.balance import TOURNAMENT_SPELL_OVERRIDES
            for card in crown.split(','):
                TOURNAMENT_SPELL_OVERRIDES.get(card, {}).pop('crown_tower_damage', None)
        from bot.levels.match import install_engine_levels
        install_engine_levels()
        self.counters = Counter()

    # -- construction ------------------------------------------------------------------------------------------
    def battle(self, decks, levels, tower_levels, seed=0):
        from bot.levels.match import tower_curve
        from clasher.battle import BattleState
        from clasher.player import PlayerState
        players = [PlayerState(s, deck=list(decks[s]), hand=list(decks[s][:4]), cycle_queue=deque(decks[s][4:]),
                               card_levels=dict(levels[s]), tower_level=int(tower_levels[s])) for s in (0, 1)]
        with tower_curve():
            return BattleState(players=players, rng=random.Random(seed))

    def start(self, game: Game, rec: Record, opp_deck, opp_levels, opp_tower_level, seed=0):
        from clasher.entities import Building, Entity, Troop
        from clasher.spells import Spell
        self.Troop, self.Building = Troop, Building
        self.seat = S = int(getattr(game, 'seat', 0) or 0)
        decks, lv, tl = [None, None], [None, None], [None, None]
        decks[S], lv[S], tl[S] = list(game.deck), dict(game.levels), game_own_tower_level(game)
        decks[1 - S], lv[1 - S], tl[1 - S] = list(opp_deck), dict(opp_levels), opp_tower_level
        b = self.b = self.battle(decks, lv, tl, seed)
        self.roots = {}
        _root_tracking(b, self.roots, Entity, Spell)
        for e in b.entities.values():
            self.roots[e.id] = (None, False)
        while b.tick < rec.tick:
            if b.fast_forward_idle_ticks(rec.tick - b.tick) == 0:
                b.step()
        # own hand from the HUD (own information); the opponent's is unknown (forced on demand, counted)
        p = b.players[S]
        if rec.hand and all(c in game.deck for c in rec.hand) and len(set(rec.hand)) == 4:
            rest = [c for c in game.deck if c not in rec.hand]
            if rec.next in rest:
                rest.remove(rec.next)
                rest.insert(0, rec.next)
            p.hand, p.cycle_queue = list(rec.hand), deque(rest)
        for pid in (0, 1):
            b.players[pid].elixir = float(rec.elixir) if (pid == S and rec.elixir is not None) else 10.0
        self._set_towers(rec)

    def _set_towers(self, rec):
        b = self.b
        king_active = set()
        for e in list(b.entities.values()):
            nm = getattr(e.card_stats, 'name', '')
            if nm not in ('KingTower', 'Tower'):
                continue
            kind = 'king' if nm == 'KingTower' else 'princess'
            x, _ = self._to_ours(e.position.x, e.position.y)
            side = None if kind == 'king' else ('left' if x < 9 else 'right')
            frac, alive = rec.towers.get((self._owner(e.player_id), kind, side), (1.0, True))
            if not alive or frac is None or frac <= 0:
                e.hitpoints = 0
                king_active.add(e.player_id)
                self.counters['tower_dead_at_t0'] += 1
            else:
                e.hitpoints = int(round(float(frac) * e.max_hitpoints))
                if kind == 'king' and frac < 1:
                    king_active.add(e.player_id)
        for s in king_active:
            try:
                b._activate_king_tower(s)
            except Exception:   # noqa: BLE001 - signature differs across engine trees
                self.counters['king_activate_failed'] += 1

    # -- plays --------------------------------------------------------------------------------------------------
    def deploy(self, play: Play) -> bool:
        from clasher.arena import Position
        b = self.b
        pid = self._pid(play.side)
        p = b.players[pid]
        name = play.card
        if name not in p.deck:
            self.counters['card_not_in_deck'] += 1
            return False
        if name not in p.hand:
            self.counters['hand_forced'] += 1
            if name in p.cycle_queue:
                p.cycle_queue.remove(name)
            old = p.hand[0]
            p.hand[0] = name
            if old is not None:
                p.cycle_queue.appendleft(old)
        resolved = b.resolve_card_play(pid, name)
        stats = b.card_loader.get_card(resolved[0]) if resolved else None
        cost = getattr(stats, 'mana_cost', 0) or 0
        if p.elixir + 1e-9 < cost:
            self.counters['elixir_topped'] += 1
            p.elixir = float(cost)
        try:
            return bool(b.deploy_card(pid, name, Position(*self._to_engine(play.x, play.y))))
        except Exception:   # noqa: BLE001 - an engine refusal by exception is a dropped play
            self.counters['deploy_exception'] += 1
            return False

    def step(self):
        self.b.step()

    @property
    def tick(self):
        return self.b.tick

    @property
    def over(self):
        return bool(getattr(self.b, 'game_over', False))

    def units(self):
        """-> [(owner, card, main, x, y, hp_frac)] for live troops/buildings, and {(owner, kind, side): hp_frac}."""
        out, towers = [], {}
        for e in self.b.entities.values():
            if not isinstance(e, (self.Troop, self.Building)):
                continue
            nm = getattr(e.card_stats, 'name', '')
            alive = e.is_alive and e.hitpoints > 0
            x, y = self._to_ours(e.position.x, e.position.y)
            owner = self._owner(e.player_id)
            if nm in ('KingTower', 'Tower'):
                kind = 'king' if nm == 'KingTower' else 'princess'
                side = None if kind == 'king' else ('left' if x < 9 else 'right')
                towers[owner, kind, side] = (e.hitpoints / e.max_hitpoints) if alive else 0.0
                continue
            if not alive:
                continue
            card, main = self.roots.get(e.id, (None, False))
            out.append((owner, card, main, x, y, e.hitpoints / max(1, e.max_hitpoints)))
        for key in [(o, 'king', None) for o in (0, 1)] + [(o, 'princess', s) for o in (0, 1) for s in ('left', 'right')]:
            towers.setdefault(key, 0.0)
        return out, towers


def game_own_tower_level(game):
    from bot.simfid.live_data import OWN_TOWER_LEVEL
    return OWN_TOWER_LEVEL


# -- level probes (engine max HP per card/level; tower max HP per level) -----------------------------------------
def probe_card_max_hp(card, levels=range(1, 17), ticks=3):
    """{level: sorted max HPs of the bodies deploy_card puts down} (empty when the card has no body)."""
    from clasher.arena import Position
    from clasher.entities import Building, Troop
    sim = LiveSim()
    out = {}
    filler = [c for c in ('Knight', 'Archers', 'Zap', 'Fireball', 'Cannon', 'Musketeer', 'Valkyrie', 'Giant', 'Arrows')
              if c != card][:7]
    deck = [card] + filler
    for L in levels:
        try:
            b = sim.battle([list(deck), list(deck)], [{c: L for c in deck}] * 2, [11, 11])
            p = b.players[1]
            p.elixir = 10
            before = set(b.entities)
            from clasher.arena import Position as P
            b.deploy_card(1, card, P(9.5, 24.5))
            for _ in range(ticks):
                b.step()
            hp = sorted({int(round(e.max_hitpoints)) for k, e in b.entities.items()
                         if k not in before and isinstance(e, (Troop, Building))})
            out[L] = hp
        except Exception:   # noqa: BLE001 - a level the engine refuses for this card
            out[L] = []
    return out


def probe_tower_max_hp(levels=range(1, 17)):
    sim = LiveSim()
    deck = ['Knight', 'Archers', 'Zap', 'Fireball', 'Cannon', 'Musketeer', 'Valkyrie', 'Giant']
    out = {}
    for L in levels:
        b = sim.battle([deck, deck], [{c: 11 for c in deck}] * 2, [L, L])
        k = [e.max_hitpoints for e in b.entities.values() if e.player_id == 1 and e.card_stats.name == 'KingTower']
        t = [e.max_hitpoints for e in b.entities.values() if e.player_id == 1 and e.card_stats.name == 'Tower']
        out[L] = dict(king=int(k[0]), princess=int(t[0]))
    return out
