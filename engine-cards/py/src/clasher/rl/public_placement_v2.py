"""Opt-in placement geometry from public appearances and static card data.

No BattleState, opponent hand, deck, RNG, combat clock or deployment timer is
accepted here. Effect identity PLUS visible entity kind distinguishes a timed
payload from its living parent. Coordinates are decoded to the game's public
millitile grid; uncertain/truncated observations cannot promise exact parity.
"""
from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace

import numpy as np

from clasher.arena import Position, TileGrid
from clasher.placement import building_anchor, ground_spawn_tile_clear
from clasher.unit_traits import is_air_unit_card

_X = np.arange(576) % 18 + 0.5
_Y = np.arange(576) // 18 + 0.5


@lru_cache(maxsize=32)
def _anchors(size: int, rotated: bool) -> tuple[np.ndarray, np.ndarray]:
    positions = [building_anchor(Position(18-x, 32-y) if rotated else Position(x, y), size)
                 for x, y in zip(_X, _Y)]
    x = np.array([p.x for p in positions])
    y = np.array([p.y for p in positions])
    return (18-x, 32-y) if rotated else (x, y)


def payload_radii(builder) -> dict[int, float]:
    """Compile DeathSpawn's static route and MightyMiner's visible bomb route.

    The scalar engine retains the source card_stats on TimedExplosive. Resolve
    the sensor's token exactly as structured_obs does, rather than assuming
    that the token always names the child bomb.
    """
    result = {}
    for name in builder.loader.load_card_definitions():
        stats = builder.loader.get_card(name)
        if stats is None:
            continue
        body = (getattr(stats, "_raw_entry", {}) or {}).get("summonCharacterData") or {}
        child = body.get("deathSpawnCharacterData") or {}
        radius = None
        if child.get("deathDamage") is not None and not child.get("hitpoints"):
            radius = float(child.get("collisionRadius", 500) or 500) / 1000
        if name == "MightyMiner":
            radius = 0.5  # c56_champions.MightyMinerSwitch's public bomb type.
        if radius is None:
            continue
        entity = SimpleNamespace(card_stats=stats)
        for namespace in ("building_body", "troop_body"):
            token = builder._runtime_entity_token_id(entity, namespace)
            if token > 1:
                previous = result.setdefault(token, radius)
                if previous != radius:
                    raise ValueError("ambiguous public deployment payload identity")
                break
    return result


def building_radii(builder) -> dict[int, float]:
    """Resolve serialized body aliases before looking up static geometry.

    Several v5 body tokens (GoblinHut_Rework, ElixirCollector) have zero model
    descriptors although their source cards declare a one-tile radius. Model
    feature tables are not an authoritative geometry catalog.
    """
    result = {}
    for name in builder.loader.load_card_definitions():
        stats = builder.loader.get_card(name)
        if stats is None or str(getattr(stats, "card_type", "")).lower() != "building":
            continue
        token = builder._runtime_entity_token_id(SimpleNamespace(card_stats=stats), "building_body")
        if token > 1:
            raw = getattr(stats, "collision_radius", None)
            radius = max(0, float(1.0 if raw is None else raw))
            previous = result.setdefault(token, radius)
            if previous != radius:
                raise ValueError("ambiguous public building geometry")
    return result


class PublicPlacementV2:
    def __init__(self, builder):
        self.builder = builder
        self.payloads = payload_radii(builder)
        self.building_radii = building_radii(builder)
        self.grid = TileGrid()
        self.walkable = np.array([self.grid.is_walkable(Position(x, y)) for x, y in zip(_X, _Y)])
        self.spawn_clear = np.array([ground_spawn_tile_clear(Position(x, y)) for x, y in zip(_X, _Y)])

    def board(self, observation):
        return PlacementBoard(self, observation)


class PlacementBoard:
    def __init__(self, rules, observation):
        self.rules = rules
        self.rotated = observation.board_rotated
        self.buildings = []
        self.payloads = []
        self.crowns = np.zeros(576, dtype=np.bool_)
        for i in np.flatnonzero(observation.entity_mask):
            if observation.entity_id_confidence is not None and observation.entity_id_confidence[i] <= 0:
                continue
            token = int(observation.entity_ids[i])
            if not 1 < token < len(rules.builder.token_names):
                continue
            row = observation.entity_features[i]
            x, y = round(float(row[0])*18, 3), round(float(row[1])*32, 3)
            if row[5] > 0.5:
                # Static serialized hitbox; float32 descriptors must not add a
                # footprint tile at integral diameters.
                radius = rules.building_radii.get(token,
                    round(float(rules.builder.card_stat_features[token, 12])*3, 4))
                half = max(1, int(np.ceil(2*radius))+1)/2
                self.buildings.append((x, y, radius or 1.0, half))
                name = rules.builder.token_names[token].split(":")[-1]
                if name in {"Tower", "KingTower"}:
                    crown_half = 2.0 if name == "KingTower" else 1.5
                    self.crowns |= (abs(_X-x) <= crown_half+1e-9) & (abs(_Y-y) <= crown_half+1e-9)
            elif row[7] > 0.5 and token in rules.payloads:
                self.payloads.append((x, y, rules.payloads[token]))

    def _footprints(self, x, y, half):
        blocked = np.zeros(576, dtype=np.bool_)
        for bx, by, _, bh in self.buildings:
            blocked |= (abs(x-bx) < half+bh) & (abs(y-by) < half+bh)
        return blocked

    def _payloads(self, x, y, radius, half=None):
        blocked = np.zeros(576, dtype=np.bool_)
        for px, py, pr in self.payloads:
            dx, dy = abs(x-px), abs(y-py)
            if half is not None:
                dx, dy = np.maximum(dx-half, 0), np.maximum(dy-half, 0)
                limit = pr
            else:
                limit = pr+radius
            blocked |= dx*dx+dy*dy <= (limit+1e-9)**2
        return blocked

    def legal(self, stats, spell, zone, non_blocked):
        if self.rotated is None:
            raise ValueError("mask v2 requires public board orientation")
        is_spell = spell is not None
        anywhere = not is_spell and bool(getattr(stats, "can_deploy_on_enemy_side", False))
        unrestricted = anywhere or (is_spell and not self.rules.grid._requires_deploy_zone_spell(spell))
        legal = non_blocked.copy() if unrestricted else (non_blocked & zone)
        margin = int(getattr(stats, "deploy_w_tile_margin", 0) or 0)
        legal &= (_X >= margin) & (_X < 18-margin)
        # Static terrain must be queried in world space (bridge-edge asymmetry).
        walkable = self.rules.walkable[::-1] if self.rotated else self.rules.walkable
        if is_spell:
            if getattr(spell, "requires_walkable_target", False):
                legal &= walkable
            return legal
        legal &= ~self.crowns
        radius = float(getattr(stats, "collision_radius", 0.5) or 0.5)
        if str(getattr(stats, "card_type", "")).lower() == "building":
            raw = getattr(stats, "collision_radius", None)
            size = max(1, int(np.ceil(2*max(0, 1.0 if raw is None else float(raw))))+1)
            ax, ay = _anchors(size, self.rotated)
            return legal & ~self._footprints(ax, ay, size/2) & ~self._payloads(ax, ay, 0, size/2)
        legal &= ~self._payloads(_X, _Y, radius)
        if is_air_unit_card(stats):
            for bx, by, br, _ in self.buildings:
                dx, dy = np.rint((_X-bx)*1000), np.rint((_Y-by)*1000)
                legal &= dx*dx+dy*dy >= round((radius+br)*1000)**2
            return legal
        # The engine relocates ordinary ground troops; occupancy at the
        # requested anchor is not itself a rejection (payloads above are).
        clear = self.rules.spawn_clear[::-1] if self.rotated else self.rules.spawn_clear
        valid = non_blocked & walkable & clear & ~self._footprints(_X, _Y, 0.5)
        valid &= ~self._payloads(_X, _Y, radius)
        if not anywhere:
            valid &= zone & ~self.crowns
        # Native searches Chebyshev rings 0..30. Keep the exact bound even
        # for arena-wide cards and artificially saturated boards.
        candidates = np.flatnonzero(valid)
        if not len(candidates):
            return np.zeros(576, dtype=np.bool_)
        reachable = np.zeros(576, dtype=np.bool_)
        for j in candidates:
            reachable |= (abs(_X-_X[j]) <= 30) & (abs(_Y-_Y[j]) <= 30)
            if reachable.all():
                break
        return legal & reachable
