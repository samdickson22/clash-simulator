from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class ElectroWizardSpawnZap(BaseMechanic):
    """Stuns and damages nearby enemies when the Electro Wizard enters the arena."""
    radius_tiles: float = 4.0  # Deploy zap radius
    stun_duration_ms: int = 500  # 0.5 seconds
    damage_scale: float = 0.5  # Deploy zap deals 50% of EWiz damage

    def on_attach(self, entity: 'Entity') -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) if hasattr(entity, "card_stats") else {}
        area_data = raw.get("areaEffectObjectData", {}) if isinstance(raw, dict) else {}
        if isinstance(area_data, dict):
            if area_data.get("radius") is not None:
                self.radius_tiles = area_data["radius"] / 1000.0
            if area_data.get("buffTime") is not None:
                self.stun_duration_ms = area_data["buffTime"]
            if area_data.get("damage") is not None and getattr(entity, "damage", 0):
                # Convert to a scale against current unit damage so level scaling is preserved.
                base_damage = float(getattr(entity, "damage", 1) or 1)
                self.damage_scale = float(area_data["damage"]) / base_damage

    def on_spawn(self, entity: 'Entity') -> None:
        """Zap on deploy - stuns and damages enemies"""
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        damage = (entity.damage or 0) * self.damage_scale

        for other in list(battle_state.entities.values()):
            if other.player_id == entity.player_id or not other.is_alive:
                continue
            distance = entity.position.distance_to(other.position)
            distance_tiles = distance / 1000.0 if distance > 100 else distance
            if distance_tiles <= self.radius_tiles:
                other.take_damage(damage)
                if hasattr(other, 'apply_stun'):
                    other.apply_stun(self.stun_duration_ms / 1000.0)


@dataclass
class ElectroWizardStunAttack(BaseMechanic):
    """Electro Wizard's attacks stun targets"""
    stun_duration_ms: int = 500  # 0.5 seconds
    chain_targets: int = 2  # Attack splits to 2 targets
    chain_damage_scale: float = 1.0

    def on_attack_hit(self, entity: 'Entity', target: 'Entity') -> None:
        """Apply stun when Electro Wizard hits a target"""
        if hasattr(target, 'apply_stun'):
            target.apply_stun(self.stun_duration_ms / 1000.0)

        # Find secondary target for chain lightning
        if hasattr(entity, 'battle_state') and self.chain_targets > 1:
            self._apply_chain_lightning(entity, target)

    def _apply_chain_lightning(self, entity: 'Entity', primary_target: 'Entity') -> None:
        """Apply chain lightning to secondary targets"""
        battle_state = entity.battle_state
        range_value = entity.range if hasattr(entity, 'range') else 3.0
        radius_tiles = range_value / 1000.0 if range_value > 100 else range_value

        # Find nearest secondary target
        secondary_target = None
        min_distance = float('inf')

        for other in list(battle_state.entities.values()):
            if (other == primary_target or
                other.player_id == entity.player_id or
                not other.is_alive):
                continue

            distance = primary_target.position.distance_to(other.position)
            distance_tiles = distance / 1000.0 if distance > 100 else distance
            if distance_tiles <= radius_tiles and distance_tiles < min_distance:
                secondary_target = other
                min_distance = distance_tiles

        # Apply damage and stun to secondary target
        if secondary_target:
            damage = (entity.damage or 0) * self.chain_damage_scale
            secondary_target.take_damage(damage)
            if hasattr(secondary_target, 'apply_stun'):
                secondary_target.apply_stun(self.stun_duration_ms / 1000.0)
