from dataclasses import dataclass, field
from typing import Optional, Sequence, Protocol, Literal, Callable, Any, List
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


# For backward compatibility during migration
class CardStatsCompat:
    """Compatibility wrapper to convert CardDefinition to legacy CardStats"""

    def __init__(self, card_def: CardDefinition):
        self._card_def = card_def

        # Extract stats based on card kind
        if card_def.troop_stats:
            stats = card_def.troop_stats
        elif card_def.building_stats:
            stats = card_def.building_stats
        else:
            stats = BaseStats()

        # Map to legacy CardStats fields
        self.name = card_def.name
        self.id = card_def.id
        self.mana_cost = card_def.elixir
        self.rarity = card_def.rarity
        self.hitpoints = stats.hitpoints
        self.damage = stats.damage
        self.range = stats.range_tiles
        self.sight_range = stats.sight_range_tiles
        self.collision_radius = stats.collision_radius_tiles

        # Card type based fields
        if card_def.troop_stats:
            self.speed = card_def.troop_stats.speed_tiles_per_min
            self.hit_speed = card_def.troop_stats.hit_speed_ms
            self.deploy_time = card_def.troop_stats.deploy_time_ms
            self.load_time = card_def.troop_stats.load_time_ms
            self.summon_count = card_def.troop_stats.summon_count

        # Legacy properties
        self.card_type = card_def.kind.capitalize()

        # Targeting properties
        if card_def.targeting:
            self.targets_only_buildings = card_def.targeting.buildings_only()
            # Could add more targeting logic here

        # Store reference to original card definition
        self.card_definition = card_def

    @classmethod
    def from_card_definition(cls, card_def: CardDefinition) -> 'CardStatsCompat':
        """Create CardStatsCompat from CardDefinition"""
        return cls(card_def)

    @property
    def scaled_hitpoints(self):
        return self.hitpoints

    @property
    def scaled_damage(self):
        return self.damage