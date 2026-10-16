from dataclasses import dataclass

from ..mechanic_base import BaseMechanic
from .knockback import apply_radial_knockback


@dataclass
class SpawnPushback(BaseMechanic):
    """Apply a character's serialized push-only deployment payload."""

    distance_tiles: float
    radius_tiles: float
    hits_air: bool = False
    hits_ground: bool = True

    def on_spawn(self, entity) -> None:
        battle_state = getattr(entity, "battle_state", None)
        if battle_state is None or self.distance_tiles <= 0 or self.radius_tiles <= 0:
            return

        source_kind = getattr(getattr(entity, "card_stats", None), "name", None)
        impact_position = type(entity.position)(entity.position.x, entity.position.y)
        for other in list(battle_state.entities.values()):
            if other is entity or other.player_id == entity.player_id or not other.is_alive:
                continue
            # SpawnPushback is a character query. Buildings and other
            # non-character objects do not expose a movement component in the
            # native path. Its plane test reads CharacterData::FlyingHeight,
            # so temporary jump/leap phases retain the unit's serialized
            # ground plane here.
            if getattr(other, "entity_kind", 4) != 0:
                continue
            if bool(getattr(other, "is_air_unit", False)):
                if not self.hits_air:
                    continue
            elif not self.hits_ground:
                continue
            if not other.intersects_native_area(impact_position, self.radius_tiles):
                continue
            apply_radial_knockback(
                other,
                battle_state,
                impact_position,
                self.distance_tiles,
                source_kind=source_kind,
                # The native SpawnPushback call sets the pushback-all
                # argument, bypassing CharacterData::IgnorePushback. This is
                # distinct from the mass-limited deployment damage wave.
                ignores_mass=True,
            )
