from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic
from ..logic_math import native_percent_damage

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroWizardSpawnZap(BaseMechanic):
    """Stuns and damages nearby enemies when the Electro Wizard enters the arena."""
    radius_tiles: float = 4.0  # Deploy zap radius
    stun_duration_ms: int = 500  # 0.5 seconds
    damage_scale: float = 0.5  # Deploy zap deals 50% of EWiz damage
    spawn_damage: float = 0.0
    crown_tower_damage_multiplier: float = 1.0

    def on_attach(self, entity: 'Entity') -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) if hasattr(entity, "card_stats") else {}
        area_data = raw.get("areaEffectObjectData", {}) if isinstance(raw, dict) else {}
        if isinstance(area_data, dict):
            if area_data.get("radius") is not None:
                self.radius_tiles = area_data["radius"] / 1000.0
            if area_data.get("buffTime") is not None:
                self.stun_duration_ms = area_data["buffTime"]
            if area_data.get("damage") is not None:
                scaler = getattr(entity.card_stats, "get_scaled_stat", None)
                raw_damage = area_data["damage"]
                self.spawn_damage = float(scaler(raw_damage) if callable(scaler) else raw_damage)
            if area_data.get("crownTowerDamagePercent") is not None:
                self.crown_tower_damage_multiplier = max(
                    0.0,
                    1.0 + area_data["crownTowerDamagePercent"] / 100.0,
                )

    def on_spawn(self, entity: 'Entity') -> None:
        """Zap on deploy - stuns and damages enemies"""
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        damage = self.spawn_damage or (entity.damage or 0) * self.damage_scale

        from ..entities import Building

        # Both spawn bolts are committed from the landing position at once.
        # Snapshot targets before a killed unit's death effect can displace the
        # Wizard and alter who receives the same spawn zap.
        impact_position = type(entity.position)(entity.position.x, entity.position.y)
        targets = []
        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            if getattr(other, "entity_kind", 4) in {2, 3}:
                continue
            if other.intersects_native_area(
                impact_position,
                self.radius_tiles,
            ) and other.can_receive_area_damage(
                "ElectroWizard",
                source_entity=entity,
            ):
                targets.append(other)

        for other in targets:
            target_damage = damage
            if isinstance(other, Building) and getattr(other.card_stats, "name", None) in {
                "Tower",
                "KingTower",
            }:
                target_damage = native_percent_damage(
                    target_damage,
                    self.crown_tower_damage_multiplier,
                )
            other.take_damage(target_damage)
            if other.is_alive and hasattr(other, 'apply_stun'):
                other.apply_stun(self.stun_duration_ms / 1000.0)
