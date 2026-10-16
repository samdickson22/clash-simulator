"""Range-gated production from native ActionGoblinHutLifeState."""

from copy import deepcopy

from ..mechanics.shared.spawner import PeriodicSpawner


class GoblinHutProduction(PeriodicSpawner):
    def __init__(self) -> None:
        super().__init__(
            unit_name="SpearGoblin",
            spawn_interval_ms=2200,
            first_spawn_delay_ms=1000,
            spawn_with_deploy=True,
            spawn_radius_tiles=1.2,
            spawn_angle_shift_degrees=20,
        )

    def on_attach(self, entity) -> None:
        character = entity.card_stats.summon_character_data
        self.unit_data = deepcopy(character["deathSpawnCharacterData"])
        self.unit_data["deployTime"] = 500

    def on_object_tick(self, entity, dt_ms: int) -> None:
        if entity.is_stunned():
            return
        nearby = any(
            target.entity_kind in {0, 1}
            and target.is_targetable_by(entity.player_id)
            and entity.position.distance_to(target.position)
            <= 6.0 + target.get_collision_radius()
            for target in entity.battle_state.entities.values()
        )
        if not nearby:
            # A new encounter pays ActionDelay again. Sleep does not bank waves.
            self.time_since_spawn_ms = 0.0
            self.spawns_created = 0
            return
        super().on_object_tick(entity, dt_ms)
