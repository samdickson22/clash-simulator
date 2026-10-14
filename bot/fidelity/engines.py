"""Engine adapters for the replay-fidelity harness.

Each adapter plays a fixture's script through the engine's OWN deploy path (hand,
elixir, placement rules, formations) and reports units in native coordinates
(1000 per tile) with the ROOT card (native card id of the card whose play put the
unit there), so both engines are scored by one scorer.

Interventions that keep the script playable are counted, never hidden:
hand_forced (the card was not in the engine's hand), elixir_topped (ours only),
deploy_retried / deploy_dropped (the engine refused the tap).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, deque
from dataclasses import dataclass

from .fixture import Fixture, Play

# Clasher (recording) name -> RoyaleSim catalogue name, where they differ.
RSIM_NAME = {"Archers": "Archer", "IceGolem": "IceGolemite", "IceSpirit": "IceSpirits"}


@dataclass
class SimUnit:
    key: int
    side: int
    root: int  # native card id, -1 for towers
    tower_slot: int | None
    x: int
    y: int
    hp: int


def tower_slot_of(x_native: int) -> int:
    return 1 if x_native < 9000 else 2


class OursEngine:
    """Clasher's Python reference engine (src/clasher)."""

    name = "clasher"

    def __init__(self, name_to_id: dict[str, int], issue_offset: int = 0):
        from clasher.card_aliases import resolve_card_name  # noqa: F401
        self.name_to_id = name_to_id
        self.issue_offset = issue_offset
        self.counters = Counter()

    def _our_name(self, card: str) -> str:
        from clasher.card_aliases import resolve_card_name
        return resolve_card_name(card)

    def reset(self, fix: Fixture) -> None:
        from clasher.battle import BattleState
        from clasher.entities import Building, Troop
        self._Troop, self._Building = Troop, Building
        id_to_name = {v: k for k, v in self.name_to_id.items()}
        self.b = b = BattleState()
        self.id_of = {}
        for side in (0, 1):
            names = [self._our_name(id_to_name[i]) for i in fix.initial_order[side]]
            for i in fix.initial_order[side]:
                self.id_of[self._our_name(id_to_name[i])] = i
            p = b.players[side]
            p.deck = list(names)
            p.hand = list(names[:4])
            p.cycle_queue = deque(names[4:])
            p.set_card_levels({n: 11 for n in names})
        self.roots: dict[int, int] = {}
        self._install_root_tracking()
        for e in b.entities.values():
            self.roots[e.id] = -1
        while b.tick < fix.start_tick:
            if b.fast_forward_idle_ticks(fix.start_tick - b.tick) == 0:
                b.step()
        for side in (0, 1):
            b.players[side].elixir = fix.initial_elixir[side]

    def _install_root_tracking(self) -> None:
        engine = self
        from clasher.spells import Spell
        Entity = __import__("clasher.entities", fromlist=["Entity"]).Entity

        class RootDict(dict):
            def __setitem__(self, k, v):
                if k not in self:
                    engine.roots[getattr(v, "id", k)] = engine._infer_root(v, Entity, Spell)
                super().__setitem__(k, v)

        self.b.entities = RootDict(self.b.entities)

    def _infer_root(self, new, Entity, Spell) -> int:
        f = sys._getframe(2)
        while f is not None:
            loc = f.f_locals
            if f.f_code.co_name == "deploy_card" and "card_name" in loc:
                return self.id_of.get(self._our_name(loc["card_name"]), -2)
            s = loc.get("self")
            if isinstance(s, Spell):
                return self.id_of.get(self._our_name(s.name), -2)
            for var in ("self", "source_entity", "parent", "spawner", "source"):
                o = loc.get(var)
                if isinstance(o, Entity) and o is not new and o.id in self.roots:
                    return self.roots[o.id]
            f = f.f_back
        return -2  # unrooted

    def deploy(self, play: Play) -> bool:
        from clasher.arena import Position
        b = self.b
        if play.kind == "champion ability":
            ok = b.activate_champion_ability(play.side)
            self.counters["ability_ok" if ok else "ability_refused"] += 1
            return ok
        name = self._our_name(play.card)
        p = b.players[play.side]
        if name not in p.hand:
            self.counters["hand_forced"] += 1
            slot = play.slot if 0 <= play.slot < 4 else 0
            if name in p.cycle_queue:
                p.cycle_queue.remove(name)
            old = p.hand[slot]
            p.hand[slot] = name
            if old is not None:
                p.cycle_queue.appendleft(old)
        stats = b.card_loader.get_card(b.resolve_card_play(play.side, name)[0]) if b.resolve_card_play(play.side, name) else None
        cost = getattr(stats, "mana_cost", 0) or 0
        if p.elixir + 1e-9 < cost:
            self.counters["elixir_topped"] += 1
            p.elixir = float(cost)
        return b.deploy_card(play.side, name, Position(*play.tile))

    def step(self) -> None:
        self.b.step()

    @property
    def tick(self) -> int:
        return self.b.tick

    def units(self) -> list[SimUnit]:
        out = []
        for e in self.b.entities.values():
            if not isinstance(e, (self._Troop, self._Building)):
                continue
            if not e.is_alive or e.hitpoints <= 0:
                continue
            x, y = round(e.position.x * 1000), round(e.position.y * 1000)
            root = self.roots.get(e.id, -2)
            slot = None
            nm = getattr(e.card_stats, "name", "")
            if root == -1 and nm in ("KingTower", "Tower", "PrincessTower"):
                slot = 0 if nm == "KingTower" else tower_slot_of(x)
            elif root == -1:
                root = -2
            out.append(SimUnit(e.id, e.player_id, root, slot, x, y, int(round(e.hitpoints))))
        return out


class RsimEngine:
    """RoyaleSim (royalesim on PyPI) through its Python binding."""

    def __init__(self, name_to_id: dict[str, int], client: str = "15.535.29", issue_offset: int = 0):
        import royalesim
        self.rs = royalesim
        self.client = client
        self.name = f"royalesim-{client}"
        self.name_to_id = name_to_id
        self.issue_offset = issue_offset
        self.counters = Counter()
        overrides = royalesim.client_arms(client) if client != "16.402" else {}
        self.b = royalesim.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]], calibration_overrides=overrides)
        cat = json.loads(self.b.catalogue_json())
        self.cat_idx = {row[0]: i for i, row in enumerate(cat)}
        self.F = {f: i for i, f in enumerate(royalesim.ENTITY_FIELDS)}
        self.sub = royalesim.SUBTILE_PER_MILLITILE

    def _idx(self, card: str) -> int:
        return self.cat_idx[RSIM_NAME.get(card, card)]

    def reset(self, fix: Fixture) -> None:
        id_to_name = {v: k for k, v in self.name_to_id.items()}
        decks = [[self._idx(id_to_name[i]) for i in fix.initial_order[s]] for s in (0, 1)]
        self.idx_to_native = {}
        for s in (0, 1):
            for i in fix.initial_order[s]:
                self.idx_to_native[self._idx(id_to_name[i])] = i
        self.b.reset(seed=fix.start_tick, decks=decks, shuffle=0, start_tick=fix.start_tick,
                     elixir_milli=[int(round(e * 1000)) for e in fix.initial_elixir], tower_hp=None, spawns=[])
        self._tick = fix.start_tick
        self._pending: list[tuple] = []
        self._state = None

    def _st(self):
        if self._state is None:
            self._state = json.loads(self.b.state_json())
        return self._state

    def deploy(self, play: Play) -> bool:
        st = self._st()
        if play.kind == "champion ability":
            cmd = (play.side, self.rs.HAND_SIZE, 0, 0)
            reason = self.b.check_deploy(*cmd)
            self.counters["ability_ok" if reason == 0 else f"ability_refused_{self.rs.DEPLOY_REASONS[reason]}"] += 1
            if reason != 0:
                return False
            self._pending.append(cmd)
            return True
        hand = st["players"][play.side]["hand"]
        want = self._idx(play.card)
        if want not in hand:
            self.counters["hand_miss"] += 1
            return False
        cmd = (play.side, hand.index(want), int(play.tile[0] * 1000 * self.sub), int(play.tile[1] * 1000 * self.sub))
        reason = self.b.check_deploy(*cmd)
        if reason != 0:
            self.counters[f"refused_{self.rs.DEPLOY_REASONS[reason]}"] += 1
            return False
        self._pending.append(cmd)
        return True

    def step(self) -> None:
        cmds, self._pending = self._pending, []
        res = self.b.step(cmds, 1)
        for row in res:
            if row[1] != 0:
                self.counters[f"step_refused_{self.rs.DEPLOY_REASONS[row[1]]}"] += 1
        self._tick += 1
        self._state = None

    @property
    def tick(self) -> int:
        return self._st()["tick"]

    def units(self) -> list[SimUnit]:
        F = self.F
        out = []
        for u in self._st()["entities"]:
            hp = u[F["hp"]]
            if hp is None or hp <= 0:
                continue
            x, y = u[F["x"]] // self.sub, u[F["y"]] // self.sub
            cid = u[F["card_id"]]
            ts = u[F["tower_slot"]]
            if cid == -1 and ts is not None and ts >= 0:
                root, slot = -1, (0 if ts == 0 else tower_slot_of(x))
            else:
                root, slot = self.idx_to_native.get(cid, -2), None
            out.append(SimUnit(u[F["uid"]], u[F["team"]], root, slot, x, y, int(hp)))
        return out
