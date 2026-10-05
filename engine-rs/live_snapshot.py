"""Read-only export of live pilot-engine state into the native representation."""


def position(value, default=(0.0, 0.0)):
    if value is None:
        return default
    if isinstance(value, (tuple, list)):
        return tuple(value)
    return (value.x, value.y)


def live_entity(e, b):
    from differential import entity

    out = entity(e)
    s = e.card_stats
    if type(e).__name__ == "Troop":
        out["stats"]["speed"] = round(getattr(s, "speed", 0) or 0)
    clock = e._ordinary_clock
    interval = out["stats"]["interval"]
    load = out["stats"]["load"]
    force_due = bool(getattr(e, "_ordinary_force_due", False))
    if clock is not None:
        timeline = clock.hit_timeline_ms
        remaining = clock.load_remaining_ms
    else:
        timeline = remaining = 0
        if out["stats"]["ordinary"]:
            remaining_ms = max(0, round(e.attack_cooldown * 1000))
            first = interval - load
            force_due = remaining_ms == 0
            if 0 < remaining_ms < first:
                timeline = interval - remaining_ms
            else:
                remaining = min(load, max(0, remaining_ms - first))
    key = getattr(e, "_ground_path_cache_key", None)
    single = key is not None and key[0] == "single"
    out.update(
        spell_name=getattr(e, "spell_name", ""),
        strikes_elapsed=int(getattr(e, "strikes_elapsed", 0)),
        damage_ticks=int(getattr(e, "damage_ticks_applied", 0)),
        next_damage=getattr(e, "next_damage_time", None),
        next_effect=getattr(e, "next_effect_time", None),
        area_slows=[list(v) for v in e._slow_effects if v[1:] != (0.7, 0.7, 0.7)],
        controlled_vector=[
            e._movement_vector_x_units,
            e._movement_vector_y_units,
            e._movement_vector_count,
        ],
        controlled_bypass=e._movement_vector_bypasses_cap,
        periodic=[
            dict(
                source_id=v.source_id,
                remaining=v.remaining,
                interval=v.hit_interval,
                next_hit=v.time_to_next_hit,
                damage=v.damage,
                hard=v.hard_remaining,
                affects_hidden=v.affects_hidden,
            )
            for v in e._periodic_damage_effects.values()
        ],
        clock=dict(
            interval=interval,
            load=load,
            timeline=timeline,
            remaining=remaining,
            finish=e._attack_finish_elapsed_ms,
        ),
        force_due=force_due,
        clock_reseed=round(e.attack_cooldown*1000)
        if clock is not None and abs(e.attack_cooldown-e._ordinary_clock_projection)>1e-8
        else None,
        route=list(getattr(e, "_native_ground_route_cells", None) or []),
        direction=tuple(getattr(e, "_native_ground_route_direction", None) or (0, 0)),
        goal=key[1] if single else key[0] if key else None,
        route_occupied=[y * 36 + x for x, y in key[1]] if key and not single else [],
        route_friendly=list(
            getattr(e, "_native_friendly_building_signature", None) or []
        ),
        route_backwards=bool(getattr(e, "_ground_path_cache_backwards", False)),
        move_target=getattr(e, "_movement_target_id", None),
        last_target=getattr(e, "_last_combat_target_id", None),
        preload_blocked=bool(getattr(e, "_attack_preload_blocked", False)),
        moving=bool(getattr(e, "_native_natural_movement_active", False)),
        move_clock=int(getattr(e, "movement_phase_elapsed_ms", 0)),
        avoidance=int(getattr(e, "_native_avoidance", 0)),
        started=bool(
            getattr(e, "_has_attacked_once", False) or e._attack_windup_active
        ),
        windup=bool(e._attack_windup_active),
        finish_tick=int(getattr(e, "_attack_finish_tick", -1)),
        activation_remaining=float(getattr(e, "activation_delay_remaining", 0)),
        activation_hit_remaining=float(
            getattr(e, "activation_first_hit_delay_remaining", 0)
        ),
        pending_ms=int(e._pending_projectile_max_duration_ms),
        pending_lethal=bool(e._combat_target_pending_lethal),
        attacked_current=bool(e._has_attacked_current_target),
        resume_pending=bool(e._resume_pending_hit),
        decay_work=int(getattr(e, "lifetime_decay_work", 0)),
        stun=float(e.stun_timer),
        frozen_moving=bool(e._native_moving_when_frozen),
        slow_ms=round(
            max((v[0] for v in e._slow_effects if v[1:] == (0.7, 0.7, 0.7)), default=0)
            * 1000
        ),
        push=position(e._knockback_target, None),
        push_velocity=int(e._knockback_velocity_work),
        push_reset=bool(e._knockback_reset_hit_on_movement),
        push_preserve=not e._knockback_interrupts_combat,
        push_tick=int(getattr(e, "_native_knockback_movement_tick", -1)),
        nav_target=getattr(e, "_native_navigation_target_id", None),
        jump=position(getattr(e, "_river_jump_target", None), None)
        if getattr(e, "_river_jump_active", False)
        else None,
        landed_tick=int(getattr(e, "_river_landed_tick", -1)),
        charge=int(getattr(e, "_native_charge_progress", 0)),
        hidden=bool(getattr(e, "_hidden_building", False)),
        hide_phase=round(
            next(
                (
                    m._phase_ms
                    for m in e.mechanics
                    if type(m).__name__ == "HideWhenIdle"
                ),
                0,
            )
        ),
        birth=int(
            b.tick - 1
            if getattr(e, "_native_object_birth_tick", None) is None
            else e._native_object_birth_tick
        ),
        effect_age=float(getattr(e, "time_alive", 0)),
        effect_applied=bool(getattr(e, "freeze_targets_applied", False) if getattr(e, "freeze_effect", False) else getattr(e, "effect_snapshot_applied", False)),
        traveled=float(getattr(e, "distance_traveled", 0)),
        hit_ids=sorted(getattr(e, "hit_entities", [])),
    )
    if (
        type(e).__name__ == "AreaEffect"
        and out["scope"] is None
        and s is not None
        and str(s.card_type).lower() != "spell"
    ):
        # Character death payload labels (e.g. FreezeIceGolemite) identify
        # their source, not a card in the playable-spell configuration.
        out["spell_name"] = ""
    if type(e).__name__ == "Graveyard":
        out["spell_name"] = "Graveyard"
    if type(e).__name__ == "RankedStrikeArea":
        out["hit_ids"] = sorted(e.struck_ids)
    if type(e).__name__ in ("Projectile", "SpawnProjectile"):
        out['temporary_remaining'] = e._temporary_homing_remaining_ms
        out['temporary_target'] = getattr(e._temporary_homing_target, 'id', None)
        out['temporary_aim'] = position(getattr(e._temporary_homing_target, 'position', None))
        out["piercing"] = e.pierces
        out["projectile_origin"] = position(e.launch_position)
        out["hit_ids"] = sorted(e.hit_entity_ids)
        out["stats"]["speed"] = round(e.travel_speed * 50)
        out["spell_name"] = getattr(e, "spell_name", "")
        out["shot_target"] = getattr(e.primary_target, "id", None)
        out["aim"] = position(
            e.primary_target.position
            if e.primary_target is not None and e.tracks_target
            else e.target_position
        )
        out["launch_delay"] = e.launch_delay
        group = e.damage_group_hit_entity_ids
        if group is not None:
            out["damage_group"] = min(
                body.id
                for body in b.entities.values()
                if getattr(body, "damage_group_hit_entity_ids", None) is group
            )
            out["hit_ids"] = sorted(group)
    if type(e).__name__ == "RollingProjectile":
        out['roll_direction'] = (round(e.target_direction_x or 0),round(e.target_direction_y or 0))
        out["stats"]["speed"] = round(e.travel_speed)
        out["spell_name"] = getattr(e, "spell_name", "")
    if getattr(e, "_self_projectile_launched", False):
        electro = out["stats"]["electro_chain"]
        out.update(
            spirit=True,
            spirit_launch=e._self_projectile_launch_tick,
            shot_target=e._electro_spirit_jump_target_id
            if electro
            else e._ice_spirit_jump_target,
            aim=position(
                e._electro_spirit_jump_destination
                if electro
                else e._ice_spirit_jump_destination
            ),
        )
    if type(e).__name__ == "ChainLightning":
        out["stats"]["speed"] = round(e.travel_speed * 50)
        out.update(
            chain_origin=position(e.origin),
            chain_remaining=e.remaining_bounces,
            chain_time=e.hop_time_remaining,
            shot_target=e.current_target_id,
            hit_ids=sorted(e.visited_ids),
        )
    saved = getattr(e, "_native_frozen_stop_route", None)
    if saved is not None:
        cache = saved["cache_key"]
        saved_single = cache is not None and cache[0] == "single"
        out["frozen_stop"] = dict(
            target_id=saved["target_id"],
            route=saved["route"],
            goal=cache[1] if saved_single else cache[0] if cache else None,
            occupied=[y * 36 + x for x, y in cache[1]]
            if cache and not saved_single
            else [],
            direction=saved["direction"],
            position=position(saved["position"]),
            cell=saved["cell"],
            frozen=saved["frozen"],
            reacquired=saved["reacquired"],
            resumable=saved["resumable"],
        )
    return out


def pending_casts(b):
    return [
        dict(player=c.player_id, name=c.spell_name, x=c.position.x, y=c.position.y)
        for c in sorted(
            b._pending_spell_casts, key=lambda c: (c.execute_at, c.sequence)
        )
    ]
