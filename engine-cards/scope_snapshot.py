"""Read-only state export for the repaired engine-scope effect objects."""


def effect_state(e):
    if type(e).__name__ in ("DeathAreaEffectContainer", "DeathAreaStartAction", "BuffAreaEffect"):
        from death_area_snapshot import child_template
        child = child_template(e)
        if type(e).__name__ == "DeathAreaEffectContainer":
            return dict(kind="Container", delay=e.activation_delay,
                        complete=e.activation_complete, child=child)
        if type(e).__name__ == "DeathAreaStartAction":
            return dict(kind="StartAction", child=child)
        from clasher.logic_math import native_percent_damage
        return dict(kind="Haste", delay=e.activation_delay,
                    axes=(e.movement_multiplier, e.attack_speed_multiplier, e.spawn_speed_multiplier),
                    refresh=e.refresh_duration, cap=e.cap_buff_time_to_effect,
                    interval=e.effect_tick_interval, once=e.effect_on_spawn_only,
                    applied=e.effect_snapshot_applied, impact_applied=e.impact_applied,
                    impact=child, damage=e.impact_damage,
                    crown_damage=e.crown_tower_damage if e.crown_tower_damage is not None
                        else native_percent_damage(e.impact_damage, e.crown_tower_damage_multiplier),
                    next_scan=e.next_effect_time)
    if type(e).__name__ == "Graveyard":
        return dict(kind="Graveyard", interval=e.spawn_interval,
                    initial=e.initial_spawn_delay, deadlines=list(e.spawn_deadlines),
                    maximum=e.max_skeletons, offsets=list(e.spawn_offsets),
                    mirror_x=e.mirror_pattern_x_at_center, orient_y=e.orient_pattern_y_by_player,
                    spawned=e.skeletons_spawned, next_spawn=e.next_spawn_time,
                    radius=e.spawn_radius)
    if type(e).__name__ == "VinesArea":
        return dict(
            kind="Vines",
            select_delay=e.select_delay,
            action_delays=list(e.action_delays),
            snare_duration=e.snare_duration,
            damage=e.dot_damage,
            crown_damage=e.crown_dot_damage,
            interval=e.dot_interval,
            selected=e.selected,
            pending=[(time, target.id) for time, target in e.pending],
            grounded=[(time, target.id) for time, target in e.grounded],
        )
    if type(e).__name__ == "VoidArea":
        return dict(
            kind="Void",
            pulse_times=list(e.pulse_times),
            hit_delay=e.hit_delay,
            tier_max_units=list(e.tier_max_units),
            tier_damage=list(e.tier_damage),
            tier_crown_damage=list(e.tier_crown_damage),
            pulses_done=e.pulses_done,
            pending=[(time, target.id, damage) for time, target, damage in e.pending],
        )
    if type(e).__name__ == "GoblinCurseArea":
        return dict(
            kind="Curse",
            scan_interval=e.scan_interval,
            buff_time=e.buff_time,
            damage=e.dot_damage,
            crown_damage=e.crown_dot_damage,
            interval=e.dot_interval,
            next_scan=e.next_scan,
            cursed=[
                dict(
                    id=id,
                    expiry=expiry,
                    corpse=(
                        None
                        if target.is_alive
                        else (
                            target.position.x,
                            target.position.y,
                            bool(getattr(target, "_self_projectile_launched", False)),
                        )
                    ),
                )
                for id, (target, expiry) in e.cursed.items()
            ],
        )
    if type(e).__name__ == "HealPulse":
        return dict(
            kind="Heal",
            heal_per_tick=e.heal_per_tick,
            heal_interval=e.heal_interval,
            recipients=[target.id for target in e.recipients],
            snapshot_taken=e.snapshot_taken,
            ticks_done=e.ticks_done,
        )
    if (
        type(e).__name__ == "AreaEffect"
        and getattr(e, "effect_on_spawn_only", False)
    ):
        from clasher.logic_math import native_percent_damage

        return dict(
            kind="SpawnDamage",
            damage=float(e.damage),
            crown_damage=float(
                e.crown_tower_damage
                if e.crown_tower_damage is not None
                else native_percent_damage(e.damage, e.crown_tower_damage_multiplier)
            ),
            hits_air=e.hits_air,
            hits_ground=e.hits_ground,
            damage_done=e.max_damage_ticks == 0 or e.damage_ticks_applied > 0,
            buff_done=e.effect_snapshot_applied,
            buff_duration=e.slow_refresh_duration,
            axes=(e.speed_multiplier,
                  e.attack_speed_multiplier if e.attack_speed_multiplier is not None else e.speed_multiplier if e.slows_attack_speed else 1.0,
                  e.spawn_speed_multiplier if e.spawn_speed_multiplier is not None else e.speed_multiplier if e.slows_spawn_speed else 1.0),
        )
    return None
