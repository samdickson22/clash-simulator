import copy
from dataclasses import dataclass, field
from typing import Optional, Sequence, Protocol, Literal, Callable, Any, List, Dict
from abc import ABC, abstractmethod

CardKind = Literal["troop", "building", "spell", "champion"]
Rarity = Literal["Common", "Rare", "Epic", "Legendary", "Champion"]
_DEEPCOPY_ATOMIC_TYPES = frozenset(
    {type(None), bool, int, float, complex, bytes, str}
)


@dataclass(frozen=True)
class BaseStats:
    hitpoints: Optional[int] = None
    damage: Optional[int] = None
    range_tiles: Optional[float] = None
    hit_speed_ms: Optional[int] = None
    sight_range_tiles: Optional[float] = None
    collision_radius_tiles: Optional[float] = None


@dataclass(frozen=True)
class TroopStats(BaseStats):
    speed_logic_units_per_tick: Optional[float] = None
    deploy_time_ms: Optional[int] = 1000
    load_time_ms: Optional[int] = None
    summon_count: Optional[int] = None


@dataclass(frozen=True)
class BuildingStats(BaseStats):
    lifetime_ms: Optional[int] = None
    deploy_time_ms: Optional[int] = 1000


@dataclass(frozen=True)
class SpellStats:
    radius_tiles: Optional[float] = None
    duration_ms: Optional[int] = None
    crown_tower_damage_scale: Optional[float] = None


class TargetingBehavior(Protocol):
    def can_target_air(self) -> bool: ...

    def can_target_ground(self) -> bool: ...

    def buildings_only(self) -> bool: ...

    def get_nearest_target(self, entity: Any, entities: dict) -> Optional[Any]: ...


class MovementBehavior(Protocol):
    def update(self, entity: Any, dt_ms: int) -> None: ...


class AttackBehavior(Protocol):
    def maybe_attack(self, entity: Any, dt_ms: int) -> None: ...


class Mechanic(Protocol):
    def on_attach(self, entity: Any) -> None: ...

    def on_spawn(self, entity: Any) -> None: ...

    def on_tick(self, entity: Any, dt_ms: int) -> None: ...

    def on_deploy_tick(self, entity: Any, dt_ms: int) -> None: ...

    def on_object_tick(self, entity: Any, dt_ms: int) -> None: ...

    def on_target_observed(
        self,
        entity: Any,
        target: Any | None,
        dt_ms: int,
    ) -> None: ...

    def on_attack_start(self, entity: Any, target: Any) -> None: ...

    def on_attack_committed(self, entity: Any, target: Any) -> None: ...

    def on_attack_hit(self, entity: Any, target: Any) -> None: ...

    def on_knockback(self, entity: Any) -> None: ...

    def blocks_combat_actions(self, entity: Any) -> bool: ...

    def modify_outgoing_damage(
        self,
        entity: Any,
        target: Any,
        damage: float,
    ) -> float: ...

    def projectile_crown_tower_damage(
        self,
        entity: Any,
        damage: float,
    ) -> float | None: ...

    def on_death(self, entity: Any) -> None: ...


class Effect(Protocol):
    def apply(self, context: Any) -> None: ...


@dataclass(frozen=True)
class CardDefinition:
    id: int
    name: str
    kind: CardKind
    rarity: Rarity
    elixir: int
    troop_stats: Optional[TroopStats] = None
    building_stats: Optional[BuildingStats] = None
    spell_stats: Optional[SpellStats] = None
    targeting: Optional[TargetingBehavior] = None
    movement: Optional[MovementBehavior] = None
    attack: Optional[AttackBehavior] = None
    mechanics: Sequence[Mechanic] = field(default_factory=tuple)
    effects: Sequence[Effect] = field(default_factory=tuple)
    tags: frozenset[str] = field(default_factory=frozenset)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


# For backward compatibility during migration
class CardStatsCompat:
    """Compatibility wrapper to convert CardDefinition to legacy CardStats"""

    def __init__(self, card_def: CardDefinition):
        self._card_def = card_def

        raw = dict(card_def.raw or {})
        self._raw_entry = raw

        # Basic metadata
        self.name = card_def.name
        self.id = raw.get("id", card_def.id)
        self.mana_cost = card_def.elixir
        self.rarity = card_def.rarity
        self.icon_file = raw.get("iconFile")
        self.unlock_arena = raw.get("unlockArena")
        self.tribe = raw.get("tribe")
        self.english_name = raw.get("englishName")
        self.card_type = card_def.kind.capitalize() if card_def.kind else None

        # Core character data (troops/buildings) and projectile data
        char_data = raw.get("summonCharacterData", {}) or raw.get("summonSpellData", {}) or {}
        self.allow_area_damage_when_invisible = bool(
            char_data.get("allowAreaDmgWhenInvisible", False)
        )
        # Character attack projectiles live on summonCharacterData.  A projectile
        # at the card root is a deployment payload (for example Mega Knight's
        # landing impact), not the troop's basic attack.  Treating the root
        # payload as an attack silently turns melee troops into ranged units.
        projectile_data = char_data.get("projectileData") or {}
        custom_first_projectile_data = char_data.get("customFirstProjectileData") or {}
        # Some units use a decoration-only projectile for the volley and put
        # the actual combat payload in customFirstProjectileData (Princess).
        # Prefer the payload that carries damage instead of silently creating
        # a zero-damage visual projectile.
        combat_projectile_data = projectile_data
        if custom_first_projectile_data.get("damage") is not None and projectile_data.get("damage") is None:
            combat_projectile_data = custom_first_projectile_data

        # Helper converters
        def units_to_tiles(value: Optional[float]) -> Optional[float]:
            if value is None:
                return None
            return value / 1000.0

        def coerce_float(value: Optional[Any]) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        # Combat stats
        troop_stats = card_def.troop_stats
        building_stats = card_def.building_stats

        base_hitpoints = None
        if troop_stats and troop_stats.hitpoints is not None:
            base_hitpoints = troop_stats.hitpoints
        elif building_stats and building_stats.hitpoints is not None:
            base_hitpoints = building_stats.hitpoints
        else:
            base_hitpoints = char_data.get("hitpoints")

        base_damage = (char_data.get("damage") or combat_projectile_data.get("damage") or
                       (combat_projectile_data.get("spawnProjectileData") or {}).get("damage") or
                       (troop_stats.damage if troop_stats and troop_stats.damage is not None else None) or
                       (building_stats.damage if building_stats and building_stats.damage is not None else None) or
                       raw.get("damage"))

        self.hitpoints = base_hitpoints
        self.damage = base_damage
        self.range = (troop_stats.range_tiles if troop_stats and troop_stats.range_tiles is not None
                      else building_stats.range_tiles if building_stats and building_stats.range_tiles is not None
                      else units_to_tiles(char_data.get("range"))
                      or units_to_tiles(raw.get("radius")))
        self.sight_range = (troop_stats.sight_range_tiles if troop_stats and troop_stats.sight_range_tiles is not None
                            else building_stats.sight_range_tiles if building_stats and building_stats.sight_range_tiles is not None
                            else units_to_tiles(char_data.get("sightRange")))
        self.speed = (troop_stats.speed_logic_units_per_tick if troop_stats and troop_stats.speed_logic_units_per_tick is not None
                      else coerce_float(char_data.get("speed")))
        self.hit_speed = (troop_stats.hit_speed_ms if troop_stats and troop_stats.hit_speed_ms is not None
                          else building_stats.hit_speed_ms if building_stats and building_stats.hit_speed_ms is not None
                          else char_data.get("hitSpeed"))
        self.load_time = (troop_stats.load_time_ms if troop_stats and troop_stats.load_time_ms is not None
                          else char_data.get("loadTime"))
        # LoadFirstHit is a distinct native weapon capability, not an alias
        # for having a nonzero LoadTime.  In the current character table it
        # is used by Sparky's persistent loaded-shot state; ordinary weapons
        # still use LoadTime to derive their finite idle preload.
        self.load_first_hit = bool(char_data.get("loadFirstHit", False))
        self.deploy_time = (troop_stats.deploy_time_ms if troop_stats and troop_stats.deploy_time_ms is not None
                            else building_stats.deploy_time_ms if building_stats and building_stats.deploy_time_ms is not None
                            else char_data.get("deployTime"))
        self.collision_radius = (troop_stats.collision_radius_tiles if troop_stats and troop_stats.collision_radius_tiles is not None
                                  else building_stats.collision_radius_tiles if building_stats and building_stats.collision_radius_tiles is not None
                                  else units_to_tiles(char_data.get("collisionRadius")))

        # Building specific
        self.lifetime_ms = (building_stats.lifetime_ms if building_stats and building_stats.lifetime_ms is not None
                            else char_data.get("lifeTime") or char_data.get("lifetime"))

        # Deployment / swarm data
        self.summon_count = (troop_stats.summon_count if troop_stats and troop_stats.summon_count is not None
                             else raw.get("summonNumber") or raw.get("summonCount") or char_data.get("summonNumber")
                             or char_data.get("count"))
        raw_summon_radius = raw.get("summonRadius")
        self.summon_radius = (
            None
            if raw_summon_radius is None
            else float(raw_summon_radius)
            if abs(float(raw_summon_radius)) <= 10
            else units_to_tiles(raw_summon_radius)
        )
        self.summon_deploy_delay = raw.get("summonDeployDelay")
        self.summon_formation = raw.get("summonFormation")
        self.summon_width = units_to_tiles(raw.get("summonWidth")) or 0.0
        self.deploy_w_tile_margin = int(raw.get("deployWTileMargin", 0) or 0)
        self.full_lane_deploy = bool(raw.get("fullLaneDeploy", False))
        self.can_deploy_on_enemy_side = bool(
            raw.get("canDeployOnEnemySide", False)
        )
        raw_summon_spacing = raw.get("summonSpacing")
        self.summon_spacing = (
            None
            if raw_summon_spacing is None
            else float(raw_summon_spacing)
            if abs(float(raw_summon_spacing)) <= 10
            else units_to_tiles(raw_summon_spacing)
        )
        self.summon_character_second_count = raw.get("summonCharacterSecondCount")
        self.summon_character_second_data = raw.get("summonCharacterSecondData")
        self.summon_character_data = raw.get("summonCharacterData") or char_data or None

        # Periodic spawner data
        self.spawner_spawn_number = char_data.get("spawnNumber")
        self.spawner_spawn_pause_time = char_data.get("spawnPauseTime")
        self.spawner_spawn_character_data = char_data.get("spawnCharacterData")

        # Targeting and special behaviors
        target_type = char_data.get("tidTarget") or raw.get("tidTarget")
        self.attacks_ground = char_data.get("attacksGround")
        self.attacks_air = char_data.get("attacksAir")
        self.targets_only_buildings = target_type == "TID_TARGETS_BUILDINGS"
        self.target_type = target_type
        # Native CharacterData has a separate BuildingTarget bit for moving
        # characters that building-only attackers are allowed to acquire.
        # It is distinct from the attacker's TargetOnlyBuildings setting and
        # from the entity's physical Building class.
        self.building_target = bool(
            char_data.get("buildingTarget", raw.get("buildingTarget", False))
        )

        # Charging mechanics
        self.charge_range = char_data.get("chargeRange")
        self.charge_speed_multiplier = char_data.get("chargeSpeedMultiplier")
        self.damage_special = char_data.get("damageSpecial")

        # Death spawn mechanics
        death_spawn_data = char_data.get("deathSpawnCharacterData") or {}
        self.death_spawn_character = (death_spawn_data.get("name") or
                                      char_data.get("deathSpawnCharacter"))
        self.death_spawn_count = char_data.get("deathSpawnCount")
        self.death_spawn_radius = float(
            char_data.get("deathSpawnRadius", 0) or 0
        ) / 1000.0
        self.death_spawn_min_radius = float(
            char_data.get("deathSpawnMinRadius", 0) or 0
        ) / 1000.0
        self.death_spawn_pushback = bool(
            char_data.get("deathSpawnPushback", False)
        )
        self.spawn_const_priority = bool(
            char_data.get("spawnConstPriority", False)
        )
        self.death_spawn_deploy_time = int(
            char_data.get("deathSpawnDeployTime", 0) or 0
        )
        self.kamikaze = bool(char_data.get("kamikaze"))
        self.kamikaze_time = int(char_data.get("kamikazeTime", 0) or 0)
        self.death_spawn_character_data = death_spawn_data or None

        # Buff modifiers
        self.buff_data = char_data.get("buffData")
        self.hit_speed_multiplier = char_data.get("hitSpeedMultiplier")
        self.speed_multiplier = char_data.get("speedMultiplier")
        self.spawn_speed_multiplier = char_data.get("spawnSpeedMultiplier")

        # Special timing mechanics
        self.special_load_time = char_data.get("specialLoadTime")
        self.special_range = char_data.get("specialRange")
        self.special_min_range = char_data.get("specialMinRange")
        # The native GameCharacter wrapper consumes AttackDashTime to render a
        # forward-and-return attack interpolation. It never changes the
        # LogicCharacter position, so retain it as presentation metadata only.
        self.attack_dash_time = int(char_data.get("attackDashTime", 0) or 0)
        self.spawn_angle_shift = float(char_data.get("spawnAngleShift", 0) or 0)
        self.override_attack_finish_time = bool(
            char_data.get("overrideAttackFinishTime")
        )
        if self.override_attack_finish_time:
            self.attack_finish_time = int(char_data.get("attackFinishTime", 0) or 0)
        else:
            from .balance import GLOBAL_ATTACK_FINISH_TIME_MS

            self.attack_finish_time = GLOBAL_ATTACK_FINISH_TIME_MS
        self.jump_height = char_data.get("jumpHeight")
        self.jump_speed = char_data.get("jumpSpeed")
        self.stop_movement_after_ms = int(
            char_data.get("stopMovementAfterMS", 0) or 0
        )
        self.wait_ms = int(char_data.get("waitMS", 0) or 0)
        self.sight_clip = units_to_tiles(char_data.get("sightClip")) or 0.0
        if self.sight_clip <= 0.0 and (self.speed or 0) > 0:
            self.sight_clip = 1.0
        self.sight_clip_side = (
            units_to_tiles(char_data.get("sightClipSide")) or 0.0
        )

        # Projectile info
        self.projectile_start_radius = units_to_tiles(char_data.get("projectileStartRadius")) or 0.0
        self.projectile_y_offset = units_to_tiles(char_data.get("projectileYOffset")) or 0.0
        self.projectile_speed = combat_projectile_data.get("speed") or raw.get("projectileSpeed")
        self.projectile_data = combat_projectile_data or None
        self.area_damage_radius = char_data.get("areaDamageRadius")
        self.self_as_aoe_center = bool(char_data.get("selfAsAoeCenter"))
        self.attack_pushback = units_to_tiles(char_data.get("attackPushback")) or 0.0
        self.projectile_splash_radius = combat_projectile_data.get("radius")

        # Evolution and misc metadata
        self.has_evolution = bool(raw.get("evolvedSpellsData"))
        self.evolution_data = raw.get("evolvedSpellsData")

        # Levels
        self.level = raw.get("level", 11)

        # Store reference to original card definition
        self.card_definition = card_def

    def __deepcopy__(self, memo: dict[int, Any]) -> 'CardStatsCompat':
        """Copy mutable wrapper state without generic reconstruction setup."""
        existing = memo.get(id(self))
        if isinstance(existing, CardStatsCompat):
            return existing
        cloned = object.__new__(type(self))
        memo[id(self)] = cloned
        for name, value in self.__dict__.items():
            cloned.__dict__[name] = (
                value
                if type(value) in _DEEPCOPY_ATOMIC_TYPES
                else copy.deepcopy(value, memo)
            )
        return cloned

    @property
    def first_hit_time(self) -> int:
        """Milliseconds from becoming active to the first attack.

        Clash serializes ``loadTime`` as the recovery portion of the complete
        hit-speed cycle.  Ordinary first-hit wind-up is therefore the
        remainder of that cycle.  A load time longer than the hit interval is
        the data-driven Inferno-style retarget form: its fully cooled first
        attack takes one hit interval instead of becoming a negative delay.
        """
        hit_speed = int(self.hit_speed or 0)
        load_time = int(self.load_time or 0)
        if load_time > hit_speed:
            return hit_speed
        return max(0, hit_speed - load_time)

    @property
    def retarget_time(self) -> int:
        """Milliseconds required after changing an established target.

        Most attacks share their ordinary first-hit delay.  Weapons whose
        serialized load time exceeds their hit interval invert that relation:
        the excess is the retarget penalty while a cooled first attack still
        takes one regular hit interval.
        """
        hit_speed = int(self.hit_speed or 0)
        load_time = int(self.load_time or 0)
        if load_time > hit_speed:
            return load_time - hit_speed
        return max(0, hit_speed - load_time)

    @classmethod
    def from_card_definition(cls, card_def: CardDefinition) -> 'CardStatsCompat':
        """Create CardStatsCompat from CardDefinition"""
        return cls(card_def)

    def get_scaled_stat(self, stat_value: Optional[int], level: int = None) -> Optional[int]:
        """Scale a base stat with Clash Royale's truncated level multipliers."""
        from .stat_scaling import scale_stat

        lvl = level if level is not None else self.level
        return scale_stat(stat_value, lvl)

    @property
    def scaled_hitpoints(self):
        from .balance import TOURNAMENT_LEVEL, tournament_stat

        if self.level == TOURNAMENT_LEVEL:
            current = tournament_stat(self.name, "hitpoints")
            if current is not None:
                return current
        return self.get_scaled_stat(self.hitpoints)

    @property
    def scaled_damage(self):
        from .balance import TOURNAMENT_LEVEL, tournament_stat

        if self.level == TOURNAMENT_LEVEL:
            current = tournament_stat(self.name, "damage")
            if current is not None:
                return current
        return self.get_scaled_stat(self.damage)

    @property
    def scaled_damage_special(self):
        from .balance import TOURNAMENT_LEVEL, tournament_stat

        if self.level == TOURNAMENT_LEVEL:
            current = tournament_stat(self.name, "damage_special")
            if current is not None:
                return current
        return self.get_scaled_stat(self.damage_special)
