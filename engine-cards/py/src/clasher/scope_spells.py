"""Engine-scope spells whose native action graphs the generic loader cannot express.

These cards sit outside the 16-card pilot and the C56 actor scope; they are needed so
human-replay re-simulation of S122 opponents is not silently wrong (scope-expansion
PLAN section 2a). Numbers come from the serialized gamedata entry where it carries
them and otherwise from the native decoded-logic catalog
(``~/.cache/clasher-native-reference/decoded-logic-1e505767/characters/*.toml``):

* Vines (``vines.toml``): after 900 ms select up to 3 enemy characters/buildings in a
  2.5-tile circle by highest current HP incl. shields (action delays 0/50/150 ms);
  each gets a 2000 ms snare (move/attack/spawn speed -100%, DoT 60 DPS base at
  1000 ms frequency, 14 base per hit on crown towers) and is pulled to the ground
  plane for 2000 ms.
* Void / DarkMagic (``dark_magic.toml`` + gamedata ActionLaserBall): 4000 ms field,
  laser starts at 500 ms, first hit 1000 ms later, then every 1000 ms (3 pulses).
  Each pulse counts the enemies inside 2.5 tiles: 1 -> heavy, 2-4 -> medium, 5+ ->
  light per-target damage, applied by a 100 ms single-hit buff.
* Goblin Curse (``goblin_curse.toml``): 6000 ms, 3-tile field refreshing every 50 ms
  a 100 ms curse buff (DoT 14 DPS base at 1000 ms, 4 base per hit on crown towers);
  a cursed troop (not building) that dies spawns one Goblin for the caster at its
  location. This catalog revision has no damage-amplification buff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .arena import Position
from .entities import AreaEffect, Building, Entity, Troop
from .spells import Spell
from .stat_scaling import scale_stat
from .unit_traits import is_airborne_target

if TYPE_CHECKING:
    from .battle import BattleState


SCOPE_SPELL_NAMES = frozenset({"Vines", "DarkMagic", "GoblinCurse"})
_CROWN_TOWER_NAMES = frozenset({"Tower", "KingTower"})


def _is_crown_tower(entity: Entity) -> bool:
    return isinstance(entity, Building) and getattr(entity.card_stats, "name", None) in _CROWN_TOWER_NAMES


def _shield_hp(entity: Entity) -> float:
    return float(sum(
        max(0, int(getattr(mechanic, "current_shield", 0) or 0))
        for mechanic in getattr(entity, "mechanics", [])
    ))


def _enemy_characters_in_area(
    battle_state: "BattleState",
    owner: int,
    center: Position,
    radius: float,
    source_kind: str,
    *,
    include_buildings: bool = True,
) -> list[Entity]:
    found = []
    for entity in list(battle_state.entities.values()):
        if (
            not isinstance(entity, (Troop, Building))
            or entity.player_id == owner
            or not entity.is_alive
            or (not include_buildings and isinstance(entity, Building))
            or getattr(entity, "_self_projectile_launched", False)
            or getattr(entity, "_underground_deployment", False)
            or not entity.intersects_native_area(center, radius)
            or not entity.can_receive_area_damage(source_kind)
        ):
            continue
        found.append(entity)
    return found


def _register(battle_state: "BattleState", effect: Entity, name: str) -> None:
    effect.spell_name = name
    effect.battle_state = battle_state
    battle_state.entities[effect.id] = effect
    battle_state.next_entity_id += 1


# --------------------------------------------------------------------------- Vines
@dataclass
class VinesArea(AreaEffect):
    select_delay: float = 0.9
    action_delays: tuple[float, ...] = (0.0, 0.05, 0.15)
    snare_duration: float = 2.0
    dot_damage: float = 0.0
    dot_interval: float = 1.0
    crown_dot_damage: float = 0.0
    selected: bool = False
    pending: list = field(default_factory=list)  # (apply_time, entity)
    grounded: list = field(default_factory=list)  # (restore_time, entity)

    def update(self, dt: float, battle_state: "BattleState") -> None:
        if not self.is_alive:
            return
        self.time_alive += max(0.0, dt)
        name = getattr(self, "spell_name", "Vines")
        if not self.selected and self.time_alive >= self.select_delay - 1e-9:
            self.selected = True
            candidates = _enemy_characters_in_area(
                battle_state, self.player_id, self.position, self.radius, name,
            )
            candidates.sort(key=lambda e: (-(e.hitpoints + _shield_hp(e)), e.id))
            for delay, target in zip(self.action_delays, candidates):
                self.pending.append((self.select_delay + delay, target))
        while self.pending and self.pending[0][0] <= self.time_alive + 1e-9:
            _, target = self.pending.pop(0)
            if target.is_alive and target.id in battle_state.entities:
                self._snare(target, battle_state, name)
        still = []
        for restore_time, target in self.grounded:
            if restore_time <= self.time_alive + 1e-9:
                target._vines_grounded = False
                if target.id in battle_state.entities:
                    battle_state.sync_fast_target_entity(target)
            else:
                still.append((restore_time, target))
        self.grounded = still
        if self.selected and not self.pending and not self.grounded and self.time_alive >= self.duration - 1e-9:
            self.is_alive = False

    def _snare(self, target: Entity, battle_state: "BattleState", name: str) -> None:
        if is_airborne_target(target) and getattr(target, "is_air_unit", False):
            target._vines_grounded = True
            self.grounded.append((self.time_alive + self.snare_duration, target))
            battle_state.sync_fast_target_entity(target)
        target.apply_stun(self.snare_duration, source_kind=name)
        target.apply_slow(self.snare_duration, 0.0, source_kind=name)
        target.freeze_expiry_time = max(
            getattr(target, "freeze_expiry_time", 0.0), battle_state.time + self.snare_duration,
        )
        damage = self.crown_dot_damage if _is_crown_tower(target) else self.dot_damage
        target.apply_periodic_damage(
            source_id=self.id,
            source_kind=name,
            duration=self.snare_duration,
            hit_interval=self.dot_interval,
            damage=damage,
        )


@dataclass
class VinesSpell(Spell):
    duration: float = 2.0
    dot_damage: float = 0.0
    crown_dot_damage: float = 0.0
    dot_interval: float = 1.0

    def cast(self, battle_state: "BattleState", player_id: int, target_pos: Position) -> bool:
        effect = VinesArea(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id, card_stats=None, hitpoints=1, max_hitpoints=1,
            damage=0, range=self.radius, sight_range=self.radius,
            radius=self.radius, duration=self.duration,
            dot_damage=self.dot_damage, crown_dot_damage=self.crown_dot_damage,
            dot_interval=self.dot_interval,
        )
        _register(battle_state, effect, self.name)
        return True


# ---------------------------------------------------------------------- Void
@dataclass
class VoidArea(AreaEffect):
    pulse_times: tuple[float, ...] = (1.5, 2.5, 3.5)
    hit_delay: float = 0.1
    tier_max_units: tuple[int, ...] = (1, 4)
    tier_damage: tuple[float, ...] = ()
    tier_crown_damage: tuple[float, ...] = ()
    pulses_done: int = 0
    pending: list = field(default_factory=list)  # (hit_time, entity, damage)

    def update(self, dt: float, battle_state: "BattleState") -> None:
        if not self.is_alive:
            return
        self.time_alive += max(0.0, dt)
        name = getattr(self, "spell_name", "DarkMagic")
        while (
            self.pulses_done < len(self.pulse_times)
            and self.pulse_times[self.pulses_done] <= min(self.time_alive, self.duration) + 1e-9
        ):
            pulse_time = self.pulse_times[self.pulses_done]
            self.pulses_done += 1
            targets = _enemy_characters_in_area(
                battle_state, self.player_id, self.position, self.radius, name,
            )
            if not targets:
                continue
            tier = len(self.tier_max_units)
            for index, limit in enumerate(self.tier_max_units):
                if len(targets) <= limit:
                    tier = index
                    break
            for target in sorted(targets, key=lambda e: e.id):
                damage = self.tier_crown_damage[tier] if _is_crown_tower(target) else self.tier_damage[tier]
                self.pending.append((pulse_time + self.hit_delay, target, damage))
        remaining = []
        for hit_time, target, damage in self.pending:
            if hit_time <= self.time_alive + 1e-9:
                if target.is_alive and target.id in battle_state.entities:
                    target.take_damage(damage, source_kind=name)
            else:
                remaining.append((hit_time, target, damage))
        self.pending = remaining
        if self.time_alive >= self.duration - 1e-9 and not self.pending:
            self.is_alive = False


@dataclass
class VoidSpell(Spell):
    duration: float = 4.0
    pulse_times: tuple[float, ...] = (1.5, 2.5, 3.5)
    hit_delay: float = 0.1
    tier_max_units: tuple[int, ...] = (1, 4)
    tier_damage: tuple[float, ...] = ()
    tier_crown_damage: tuple[float, ...] = ()

    def cast(self, battle_state: "BattleState", player_id: int, target_pos: Position) -> bool:
        effect = VoidArea(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id, card_stats=None, hitpoints=1, max_hitpoints=1,
            damage=0, range=self.radius, sight_range=self.radius,
            radius=self.radius, duration=self.duration,
            pulse_times=self.pulse_times, hit_delay=self.hit_delay,
            tier_max_units=self.tier_max_units, tier_damage=self.tier_damage,
            tier_crown_damage=self.tier_crown_damage,
        )
        _register(battle_state, effect, self.name)
        return True


# ---------------------------------------------------------------- Goblin Curse
@dataclass
class GoblinCurseArea(AreaEffect):
    scan_interval: float = 0.05
    buff_time: float = 0.1
    dot_damage: float = 0.0
    crown_dot_damage: float = 0.0
    dot_interval: float = 1.0
    goblin_data: dict | None = None
    spell_level: int = 11
    next_scan: float = 0.0
    cursed: dict = field(default_factory=dict)  # id -> [entity, expiry_time]

    def update(self, dt: float, battle_state: "BattleState") -> None:
        if not self.is_alive:
            return
        self.time_alive += max(0.0, dt)
        name = getattr(self, "spell_name", "GoblinCurse")
        self._convert_dead(battle_state)
        while self.next_scan <= min(self.time_alive, self.duration) + 1e-9:
            self.next_scan += self.scan_interval
            expiry = battle_state.time + self.buff_time
            for target in _enemy_characters_in_area(
                battle_state, self.player_id, self.position, self.radius, name,
            ):
                damage = self.crown_dot_damage if _is_crown_tower(target) else self.dot_damage
                target.apply_periodic_damage(
                    source_id=self.id, source_kind=name, duration=self.buff_time,
                    hit_interval=self.dot_interval, damage=damage,
                )
                if isinstance(target, Troop):
                    entry = self.cursed.get(target.id)
                    if entry is None:
                        self.cursed[target.id] = [target, expiry]
                    else:
                        entry[1] = max(entry[1], expiry)
        if self.time_alive >= self.duration - 1e-9:
            # The buffs outlive the field by their own 100 ms timer.
            if all(expiry < battle_state.time - 1e-9 for _, expiry in self.cursed.values()):
                self.is_alive = False

    def _convert_dead(self, battle_state: "BattleState") -> None:
        for target_id, (target, expiry) in list(self.cursed.items()):
            if target.is_alive:
                if expiry < battle_state.time - 1e-9:
                    del self.cursed[target_id]
                continue
            del self.cursed[target_id]
            # Death is observed at most one logic frame late; the buff must
            # still have been active when the target died.
            if expiry + battle_state.dt + 1e-9 < battle_state.time:
                continue
            if getattr(target, "_self_projectile_launched", False):
                continue
            self._spawn_goblin(battle_state, Position(target.position.x, target.position.y))

    def _spawn_goblin(self, battle_state: "BattleState", position: Position) -> None:
        if not self.goblin_data:
            return
        from .factory.dynamic_factory import troop_from_character_data

        stats = troop_from_character_data(
            "Goblin", self.goblin_data, elixir=0,
            raw_overrides={"level": self.spell_level},
            rarity=self.goblin_data.get("rarity", "Common"),
        )
        battle_state._spawn_unit_at_position(position, self.player_id, stats, snap_to_valid=True)


@dataclass
class GoblinCurseSpell(Spell):
    duration: float = 6.0
    scan_interval: float = 0.05
    buff_time: float = 0.1
    dot_damage: float = 0.0
    crown_dot_damage: float = 0.0
    dot_interval: float = 1.0
    goblin_data: dict | None = None

    def cast(self, battle_state: "BattleState", player_id: int, target_pos: Position) -> bool:
        effect = GoblinCurseArea(
            id=battle_state.next_entity_id,
            position=Position(target_pos.x, target_pos.y),
            player_id=player_id, card_stats=None, hitpoints=1, max_hitpoints=1,
            damage=0, range=self.radius, sight_range=self.radius,
            radius=self.radius, duration=self.duration,
            scan_interval=self.scan_interval, buff_time=self.buff_time,
            dot_damage=self.dot_damage, crown_dot_damage=self.crown_dot_damage,
            dot_interval=self.dot_interval, goblin_data=self.goblin_data,
            spell_level=self.level,
        )
        _register(battle_state, effect, self.name)
        return True


# ------------------------------------------------------------------- builders
def _periodic_hit(dps: float, interval_s: float, level: int) -> float:
    return float(int((scale_stat(dps, level) or 0) * interval_s + 1e-9))


def _find_dicts(value: Any, predicate) -> list[dict]:
    found, stack = [], [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if predicate(item):
                found.append(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(reversed(item))
    return found


def build_scope_spell(spell_data: dict[str, Any], level: int) -> Spell | None:
    """Return the special spell for the engine-scope cards, else ``None``."""
    name = str(spell_data.get("name", ""))
    if name not in SCOPE_SPELL_NAMES:
        return None
    mana_cost = int(spell_data.get("manaCost", 1) or 1)
    area = spell_data.get("areaEffectObjectData", {}) or {}
    if name == "Vines":
        # Snare buff values are only in the native catalog (vines.toml):
        # DamagePerSecond 60, CrownTowerDamagePerHit 14, HitFrequency 1000.
        return VinesSpell(
            name=name, mana_cost=mana_cost, level=level,
            radius=float(area.get("radius", spell_data.get("radius", 2500))) / 1000.0,
            duration=float(area.get("lifeDuration", 2000)) / 1000.0,
            dot_damage=_periodic_hit(60, 1.0, level),
            crown_dot_damage=float(scale_stat(14, level) or 0),
            dot_interval=1.0,
        )
    if name == "DarkMagic":
        laser = (_find_dicts(area, lambda d: d.get("classType") == "ActionLaserBall") or [{}])[0]
        group = area.get("onStartingAction", {}) or {}
        delays = list(group.get("subActionsDelay", [0, 500]) or [0, 500])
        start = float(delays[-1]) / 1000.0
        first = float(laser.get("firstHitDelay", 1000)) / 1000.0
        freq = float(laser.get("hitFrequency", 1000)) / 1000.0
        life = float(area.get("lifeDuration", 4000)) / 1000.0
        pulses = []
        t = start + first
        while t <= life + 1e-9:
            pulses.append(round(t, 6))
            t += freq
        tiers = [a.get("spawnData", {}) for a in laser.get("onDetectedUnitActionList", [])]
        if len(tiers) != 3:
            tiers = [
                {"damagePerSecond": 1330, "crownTowerDamagePerHit": 19, "hitFrequency": 100},
                {"damagePerSecond": 625, "crownTowerDamagePerHit": 10, "hitFrequency": 100},
                {"damagePerSecond": 297, "crownTowerDamagePerHit": 7, "hitFrequency": 100},
            ]
        hit_delay = float(
            (laser.get("onDetectedUnitActionList") or [{}])[0].get("spawnTime", 100)
        ) / 1000.0
        return VoidSpell(
            name=name, mana_cost=mana_cost, level=level,
            radius=float(laser.get("detectionRadius", area.get("radius", 2500))) / 1000.0,
            duration=life,
            pulse_times=tuple(pulses),
            hit_delay=hit_delay,
            tier_max_units=tuple(int(x) for x in laser.get("maxUnitPerActionList", [1, 4])),
            tier_damage=tuple(
                _periodic_hit(t["damagePerSecond"], float(t.get("hitFrequency", 100)) / 1000.0, level)
                for t in tiers
            ),
            tier_crown_damage=tuple(float(scale_stat(t.get("crownTowerDamagePerHit", 0), level) or 0) for t in tiers),
        )
    # GoblinCurse
    base = (_find_dicts(area, lambda d: d.get("name") == "GoblinCurseBase") or [{}])[0]
    damage_buff = (_find_dicts(area, lambda d: d.get("name") == "GoblinCurseDamage") or [{}])[0]
    goblin = (_find_dicts(area, lambda d: d.get("name") == "GoblinCurseGoblin") or [None])[0]
    if goblin is not None:
        goblin = dict(goblin.get("baseData", {}) or {}, **{
            k: v for k, v in goblin.items() if k not in ("baseData", "statsTags", "name", "source")
        })
        goblin["name"] = "Goblin"
    freq = float(damage_buff.get("hitFrequency", 1000) or 1000) / 1000.0
    return GoblinCurseSpell(
        name=name, mana_cost=mana_cost, level=level,
        radius=float(base.get("radius", area.get("radius", 3000))) / 1000.0,
        duration=float(base.get("lifeDuration", area.get("lifeDuration", 6000))) / 1000.0,
        scan_interval=max(0.05, float(base.get("hitSpeed", 50) or 50) / 1000.0),
        buff_time=0.1,
        dot_damage=_periodic_hit(damage_buff.get("damagePerSecond", 14), freq, level),
        # goblin_curse.toml: CrownTowerDamagePerHit = 4 (absent from the export).
        crown_dot_damage=float(scale_stat(damage_buff.get("crownTowerDamagePerHit", 4), level) or 0),
        dot_interval=freq,
        goblin_data=goblin,
    )


# ------------------------------------------------------------------ Heal Spirit
@dataclass
class HealPulse(AreaEffect):
    """HealSpirit area: one snapshot of own troops, healed every 250 ms for 1 s."""

    heal_per_tick: float = 0.0
    heal_interval: float = 0.25
    recipients: list = field(default_factory=list)
    snapshot_taken: bool = False
    ticks_done: int = 0

    def update(self, dt: float, battle_state: "BattleState") -> None:
        if not self.is_alive:
            return
        if not self.snapshot_taken:
            self.snapshot_taken = True
            self.recipients = [
                e for e in battle_state.entities.values()
                if isinstance(e, Troop) and e.player_id == self.player_id and e.is_alive
                and not getattr(e, "_self_projectile_launched", False)
                and e.intersects_native_area(self.position, self.radius)
            ]
        self.time_alive += max(0.0, dt)
        total = max(1, int(round(self.duration / self.heal_interval)))
        while self.ticks_done < total and (self.ticks_done + 1) * self.heal_interval <= self.time_alive + 1e-9:
            self.ticks_done += 1
            for target in self.recipients:
                if target.is_alive and target.id in battle_state.entities:
                    target.hitpoints = min(target.max_hitpoints, target.hitpoints + self.heal_per_tick)
        if self.ticks_done >= total:
            self.is_alive = False
