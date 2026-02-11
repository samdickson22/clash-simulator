from dataclasses import dataclass, field
from typing import Optional, Sequence, Protocol, Literal, Callable, Any, List, Dict
from abc import ABC, abstractmethod

CardKind = Literal["troop", "building", "spell", "champion"]
Rarity = Literal["Common", "Rare", "Epic", "Legendary", "Champion"]


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
    speed_tiles_per_min: Optional[float] = None
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

    def on_attack_start(self, entity: Any, target: Any) -> None: ...

    def on_attack_hit(self, entity: Any, target: Any) -> None: ...

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
        projectile_data = char_data.get("projectileData") or raw.get("projectileData") or {}

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

        base_damage = (char_data.get("damage") or projectile_data.get("damage") or
                       (projectile_data.get("spawnProjectileData") or {}).get("damage") or
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
        self.speed = (troop_stats.speed_tiles_per_min if troop_stats and troop_stats.speed_tiles_per_min is not None
                      else coerce_float(char_data.get("speed")))
        self.hit_speed = (troop_stats.hit_speed_ms if troop_stats and troop_stats.hit_speed_ms is not None
                          else building_stats.hit_speed_ms if building_stats and building_stats.hit_speed_ms is not None
                          else char_data.get("hitSpeed"))
        self.load_time = (troop_stats.load_time_ms if troop_stats and troop_stats.load_time_ms is not None
                          else char_data.get("loadTime"))
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
        self.summon_radius = units_to_tiles(raw.get("summonRadius"))
        self.summon_deploy_delay = raw.get("summonDeployDelay")
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

        # Charging mechanics
        self.charge_range = char_data.get("chargeRange")
        self.charge_speed_multiplier = char_data.get("chargeSpeedMultiplier")
        self.damage_special = char_data.get("damageSpecial")

        # Death spawn mechanics
        death_spawn_data = char_data.get("deathSpawnCharacterData") or {}
        self.death_spawn_character = (death_spawn_data.get("name") or
                                      char_data.get("deathSpawnCharacter"))
        self.death_spawn_count = char_data.get("deathSpawnCount")
        self.kamikaze = bool(char_data.get("kamikaze"))
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

        # Projectile info
        self.projectile_speed = projectile_data.get("speed") or raw.get("projectileSpeed")
        self.projectile_data = projectile_data or raw.get("projectileData")

        # Evolution and misc metadata
        self.has_evolution = bool(raw.get("evolvedSpellsData"))
        self.evolution_data = raw.get("evolvedSpellsData")

        # Levels
        self.level = raw.get("level", 11)

        # Store reference to original card definition
        self.card_definition = card_def

    @classmethod
    def from_card_definition(cls, card_def: CardDefinition) -> 'CardStatsCompat':
        """Create CardStatsCompat from CardDefinition"""
        return cls(card_def)

    def get_scaled_stat(self, stat_value: Optional[int], level: int = None) -> Optional[int]:
        """Mirror legacy stat scaling to keep compatibility."""
        if stat_value is None:
            return None
        lvl = level if level is not None else self.level
        multiplier = 1.1 ** max(0, (lvl - 1))
        return int(stat_value * multiplier)

    @property
    def scaled_hitpoints(self):
        return self.get_scaled_stat(self.hitpoints)

    @property
    def scaled_damage(self):
        return self.get_scaled_stat(self.damage)

    @property
    def scaled_damage_special(self):
        return self.get_scaled_stat(self.damage_special)
