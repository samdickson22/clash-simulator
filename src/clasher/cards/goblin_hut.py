"""Range-gated production from native ActionGoblinHutLifeState."""

from copy import deepcopy

from ..mechanics.shared.spawner import PeriodicSpawner


class GoblinHutProduction(PeriodicSpawner):
    def __init__(self) -> None:
        super().__init__(
            unit_name="SpearGoblin",
            spawn_interval_ms=2200,
            # Native T1 train recordings (calibration batch 1 #4b): with an
            # enemy in range, the first SpearGoblin appears 20 ticks after the
            # play, i.e. as the 1000 ms deploy ends. Our clock starts after
            # deploy and lands one tick late, so 100 ms here.
            first_spawn_delay_ms=100,
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
            <= 6.0 + entity.get_collision_radius() + target.get_collision_radius()
            for target in entity.battle_state.entities.values()
        )
        if not nearby:
            # The clock keeps running while idle, and a due wave fires on the
            # tick an enemy comes in range (native: first goblin on the wake
            # tick, not one ActionDelay later). Idle time does not bank waves.
            threshold = self.first_spawn_delay_ms if self.spawns_created == 0 else self.spawn_interval_ms
            self.time_since_spawn_ms = min(float(threshold), self.time_since_spawn_ms + dt_ms)
            return
        super().on_object_tick(entity, dt_ms)
