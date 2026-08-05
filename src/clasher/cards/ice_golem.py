from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class IceGolemChill(BaseMechanic):
    """Applies the Ice Golem's slowing death nova."""
    slow_radius: float = 2.0
    slow_multiplier: float = 0.70
    slow_duration_ms: int = 2000
    field_duration_ms: int = 1000
    hits_air: bool = True
    hits_ground: bool = True
    damage_scale: float = 1.0

    def on_attach(self, entity: 'Entity') -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        char_data = raw.get("summonCharacterData", {}) or {}
        area = char_data.get("deathAreaEffectData", {}) or {}
        buff = area.get("buffData", {}) or {}
        if area.get("radius") is not None:
            self.slow_radius = area["radius"] / 1000.0
        if area.get("buffTime") is not None:
            self.slow_duration_ms = int(area["buffTime"])
        if area.get("lifeDuration") is not None:
            self.field_duration_ms = int(area["lifeDuration"])
        self.hits_air = bool(area.get("hitsAir", self.hits_air))
        self.hits_ground = bool(area.get("hitsGround", self.hits_ground))
        if buff.get("speedMultiplier") is not None:
            self.slow_multiplier = max(0.0, 1.0 + buff["speedMultiplier"] / 100.0)

    def on_death(self, entity: 'Entity') -> None:
        if not hasattr(entity, 'battle_state'):
            return
        battle_state = entity.battle_state
        from ..arena import Position
        from ..entities import AreaEffect

        field = AreaEffect(
            id=battle_state.next_entity_id,
            position=Position(entity.position.x, entity.position.y),
            player_id=entity.player_id,
            card_stats=entity.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=0,
            range=self.slow_radius,
            sight_range=self.slow_radius,
            duration=max(0.0, self.field_duration_ms / 1000.0),
            radius=self.slow_radius,
            speed_multiplier=self.slow_multiplier,
            hits_air=self.hits_air,
            hits_ground=self.hits_ground,
            slow_refresh_duration=max(0.0, self.slow_duration_ms / 1000.0),
        )
        field.spell_name = getattr(entity.card_stats, "name", "IceGolemite")
        battle_state.entities[field.id] = field
        battle_state.next_entity_id += 1
