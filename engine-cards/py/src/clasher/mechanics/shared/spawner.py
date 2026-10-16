import copy
from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic
from ...factory.dynamic_factory import troop_from_character_data
from ...formations import native_radial_spawn_offset


@dataclass
class PeriodicSpawner(BaseMechanic):
    """Mechanic that periodically spawns units"""
    unit_name: str
    spawn_interval_ms: int
    first_spawn_delay_ms: int | None = None
    intra_spawn_interval_ms: int = 0
    count: int = 1
    spawn_with_deploy: bool = False
    spawn_angle_shift_degrees: float = 0.0
    max_spawns: int = -1  # -1 for unlimited
    spawn_radius_tiles: float = 0.0
    unit_data: dict | None = None

    # Internal state
    time_since_spawn_ms: float = field(init=False, default=0.0)
    spawns_created: int = field(init=False, default=0)
    pending_units: int = field(init=False, default=0)
    time_since_unit_spawn_ms: float = field(init=False, default=0.0)
    current_wave_spawned: int = field(init=False, default=0)

    def on_object_tick(self, entity, dt_ms: int) -> None:
        """Check if it's time to spawn units"""
        if not hasattr(entity, 'battle_state'):
            return

        # Freeze and ice effects pause/slow production only when their payload
        # includes spawnSpeedMultiplier.  Movement-only effects such as Poison
        # and Earthquake leave this rate at 1.0.
        if entity.is_stunned():
            return
        get_spawn_rate = getattr(entity, "get_spawn_rate_multiplier", None)
        spawn_rate = float(get_spawn_rate()) if callable(get_spawn_rate) else 1.0
        # Preserve fractional milliseconds. Truncating each simulation tick
        # causes unbounded drift (for example, 50ms * 1.30 is 65ms, not
        # 42ms) and changes long-running Witch/Tombstone wave deadlines.
        budget_ms = float(dt_ms) * max(0.0, spawn_rate)
        if budget_ms <= 0:
            return

        # Consume the whole time budget so coarse simulation steps preserve
        # both the pause between waves and serialized gaps within a wave.
        while budget_ms >= 0:
            if self.pending_units > 0:
                needed = max(
                    0,
                    self.intra_spawn_interval_ms - self.time_since_unit_spawn_ms,
                )
                if budget_ms < needed:
                    self.time_since_unit_spawn_ms += budget_ms
                    return
                budget_ms -= needed
                self.time_since_unit_spawn_ms = 0
                self._spawn_units(
                    entity,
                    count=1,
                    start_index=self.current_wave_spawned,
                    wave_size=max(1, self.count),
                )
                self.current_wave_spawned += 1
                self.pending_units -= 1
                if self.pending_units == 0:
                    self.spawns_created += 1
                    self.current_wave_spawned = 0
                    self.time_since_spawn_ms = 0
                if budget_ms == 0:
                    return
                continue

            if self.max_spawns != -1 and self.spawns_created >= self.max_spawns:
                return
            threshold_ms = (
                self.first_spawn_delay_ms
                if self.spawns_created == 0 and self.first_spawn_delay_ms is not None
                else self.spawn_interval_ms
            )
            needed = max(0, threshold_ms - self.time_since_spawn_ms)
            if budget_ms < needed:
                self.time_since_spawn_ms += budget_ms
                return
            budget_ms -= needed
            self.time_since_spawn_ms = 0

            battle_state = entity.battle_state
            if getattr(battle_state, "debug_logs", False):
                print(
                    f"[Mechanic] PeriodicSpawner tick on {getattr(entity.card_stats, 'name', 'Unknown')} "
                    f"interval={self.spawn_interval_ms}ms count={self.count}"
                )
            wave_size = max(1, self.count)
            if self.intra_spawn_interval_ms > 0 and wave_size > 1:
                self._spawn_units(entity, count=1, start_index=0, wave_size=wave_size)
                self.current_wave_spawned = 1
                self.pending_units = wave_size - 1
                self.time_since_unit_spawn_ms = 0
            else:
                self._spawn_units(entity, count=wave_size, start_index=0, wave_size=wave_size)
                self.spawns_created += 1
            if budget_ms == 0:
                return

    def _spawn_units(
        self,
        entity,
        *,
        count: int,
        start_index: int,
        wave_size: int,
    ) -> None:
        """Spawn a contiguous portion of one stable formation wave."""
        battle_state = entity.battle_state

        spawn_stats = None
        if self.unit_data:
            spawn_stats = troop_from_character_data(
                self.unit_name,
                self.unit_data,
                elixir=0,
                raw_overrides={"level": getattr(entity.card_stats, "level", 11)},
                rarity=self.unit_data.get("rarity", "Common"),
            )

        # Fall back to canonical card loader entry when raw spawn data is unavailable.
        if not spawn_stats:
            spawn_stats = battle_state.card_loader.get_card(self.unit_name)
            if spawn_stats is not None:
                spawn_stats = copy.copy(spawn_stats)
                spawn_stats.level = getattr(entity.card_stats, "level", 11)

        if not spawn_stats:
            raise ValueError(
                f"Missing periodic-spawn character data for {self.unit_name}"
            )

        if getattr(battle_state, "debug_logs", False):
            print(
                f"[Mechanic] Spawning {self.count}x {self.unit_name} around "
                f"{getattr(entity.card_stats, 'name', 'Unknown')}"
            )

        spawn_distance = max(0.0, float(self.spawn_radius_tiles))

        for index in range(start_index, start_index + count):
            if spawn_distance > 0.0:
                facing_x_units, facing_y_units = entity.native_facing_units()
                offset_x, offset_y = native_radial_spawn_offset(
                    index,
                    wave_size,
                    spawn_distance,
                    self.spawn_angle_shift_degrees,
                    facing_x_units=facing_x_units,
                    facing_y_units=facing_y_units,
                )
                from ...arena import Position

                spawn_position = Position(
                    entity.position.x + offset_x,
                    entity.position.y + offset_y,
                )
            else:
                # A missing/zero SpawnRadius uses the native four-candidate
                # terrain search. It is intentionally recomputed per child:
                # the routine does not treat an earlier member of this wave
                # as an obstruction.
                spawn_position = battle_state._native_child_position_without_radius(
                    entity,
                    spawn_stats,
                )

            battle_state._spawn_unit_at_position(
                spawn_position,
                entity.player_id,
                spawn_stats,
                deploy_delay_override=None if self.spawn_with_deploy else 0.0,
                is_clone=getattr(entity, "is_clone", False),
                # The zero-radius branch has already performed its native
                # terrain check; the radial branch performs no such check.
                snap_to_valid=False,
            )
