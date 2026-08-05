from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..arena import Position
from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class LumberjackRage(BaseMechanic):
    """Drops a rage aura when the Lumberjack dies."""
    rage_radius: float = 3.0
    speed_multiplier: float = 1.35
    duration_ms: int = 5500
    activation_delay_ms: int = 500
    effect_tick_interval_ms: int = 300
    impact_damage: float = 58.0
    crown_tower_damage_multiplier: float = 0.3

    def on_attach(self, entity: 'Entity') -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        bottle = char_data.get("deathSpawnCharacterData", {}) or {}
        area = bottle.get("deathAreaEffectData", {}) or {}
        buff = area.get("buffData", {}) or {}
        impact = area.get("spawnAreaEffectObjectData", {}) or {}
        self.rage_radius = float(area.get("radius", self.rage_radius * 1000)) / 1000.0
        self.duration_ms = int(area.get("lifeDuration", self.duration_ms))
        self.activation_delay_ms = int(bottle.get("deployTime", self.activation_delay_ms))
        self.effect_tick_interval_ms = int(
            area.get("hitSpeed", self.effect_tick_interval_ms)
        )
        self.speed_multiplier = float(buff.get("speedMultiplier", self.speed_multiplier * 100)) / 100.0
        self.impact_damage = float(impact.get("damage", self.impact_damage))
        crown_percent = float(impact.get("crownTowerDamagePercent", -70))
        self.crown_tower_damage_multiplier = max(0.0, 1.0 + crown_percent / 100.0)

    def on_death(self, entity: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        from ..entities import BuffAreaEffect

        scaler = getattr(entity.card_stats, "get_scaled_stat", None)
        impact_damage = (
            float(scaler(self.impact_damage))
            if callable(scaler)
            else self.impact_damage
        )
        rage = BuffAreaEffect(
            id=battle_state.next_entity_id,
            position=Position(entity.position.x, entity.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=0,
            range=0,
            sight_range=0,
            duration=self.duration_ms / 1000.0,
            radius=self.rage_radius,
            activation_delay=self.activation_delay_ms / 1000.0,
            effect_tick_interval=self.effect_tick_interval_ms / 1000.0,
            movement_multiplier=self.speed_multiplier,
            attack_speed_multiplier=self.speed_multiplier,
            spawn_speed_multiplier=self.speed_multiplier,
            impact_damage=impact_damage,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            # Lumberjack owns a distinct BarbarianRageDamage payload. Its
            # serialized Crown Tower modifier must remain independent of the
            # separately playable Rage spell's live-balance override.
            crown_tower_damage=None,
        )
        rage.battle_state = battle_state
        battle_state.entities[rage.id] = rage
        battle_state.next_entity_id += 1
