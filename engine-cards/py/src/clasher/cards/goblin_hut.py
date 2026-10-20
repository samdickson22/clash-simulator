"""Range-gated production from native ActionGoblinHutLifeState."""

from copy import deepcopy

from ..kinematics import tiles_to_logic_units
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
        self._target_vector = None
        self._facing = None

    def on_attach(self, entity) -> None:
        character = entity.card_stats.summon_character_data
        self.unit_data = deepcopy(character["deathSpawnCharacterData"])
        self.unit_data["deployTime"] = 500

    # Native T1 train recordings (calibration batch 2, huts (a); 345 GoblinHut plays,
    # 1,026 SpearGoblins): a goblin spawns 1200 units from the hut at the integer angle
    # towards the nearest enemy in wake range, shifted by 20 degrees. The shift's sign is
    # -facing * (-1)**wave, where facing is +1 while that enemy is right of the hut (dx > 0),
    # -1 while it is left, and keeps its last value at dx == 0 (initially +1 for side 0,
    # -1 for side 1). This fits 1003/1026 kids. Ours used to shift the hut's fixed
    # forward direction, which put every goblin at (-410, +-1128).
    def _radial_spawn_basis(self, entity) -> tuple[int, int, float]:
        if self._target_vector is None:
            return super()._radial_spawn_basis(entity)
        dx, dy = self._target_vector
        sign = -self._facing * (1 if self.spawns_created % 2 == 0 else -1)
        return dx, dy, sign * self.spawn_angle_shift_degrees

    def on_object_tick(self, entity, dt_ms: int) -> None:
        if self._facing is None:
            self._facing = 1 if entity.player_id == 0 else -1
        if entity.is_stunned():
            return
        reach = 6.0 + entity.get_collision_radius()
        nearest = None
        for target in entity.battle_state.entities.values():
            if target.entity_kind not in {0, 1} or not target.is_targetable_by(entity.player_id):
                continue
            distance = entity.position.distance_to(target.position)
            if distance <= reach + target.get_collision_radius() and (nearest is None or distance < nearest[0]):
                nearest = (distance, target)
        self._target_vector = None
        if nearest is not None:
            target = nearest[1]
            self._target_vector = (
                tiles_to_logic_units(target.position.x) - tiles_to_logic_units(entity.position.x),
                tiles_to_logic_units(target.position.y) - tiles_to_logic_units(entity.position.y),
            )
            if self._target_vector[0] != 0:
                self._facing = 1 if self._target_vector[0] > 0 else -1
        if nearest is None:
            # The clock keeps running while idle, and a due wave fires on the
            # tick an enemy comes in range (native: first goblin on the wake
            # tick, not one ActionDelay later). Idle time does not bank waves.
            threshold = self.first_spawn_delay_ms if self.spawns_created == 0 else self.spawn_interval_ms
            self.time_since_spawn_ms = min(float(threshold), self.time_since_spawn_ms + dt_ms)
            return
        super().on_object_tick(entity, dt_ms)
