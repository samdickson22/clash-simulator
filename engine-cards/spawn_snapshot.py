"""Read-only normalized production metadata and live spawner clocks."""


def spawner(e):
    m = next(
        (
            m
            for m in e.mechanics
            if type(m).__name__ in ("PeriodicSpawner", "GoblinHutProduction")
        ),
        None,
    )
    if m is None:
        return None, None
    return (
        dict(
            interval=m.spawn_interval_ms,
            first=m.first_spawn_delay_ms,
            intra=m.intra_spawn_interval_ms,
            count=m.count,
            angle=int(m.spawn_angle_shift_degrees),
            maximum=m.max_spawns,
            radius=m.spawn_radius_tiles,
            gated=type(m).__name__ == "GoblinHutProduction",
        ),
        dict(
            elapsed=m.time_since_spawn_ms,
            waves=m.spawns_created,
            pending=m.pending_units,
            unit_elapsed=m.time_since_unit_spawn_ms,
            wave_spawned=m.current_wave_spawned,
        ),
    )
