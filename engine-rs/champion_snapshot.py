"""Read-only champion ability configuration and live timer export."""


def champion(e):
    from clasher.balance import LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN
    from clasher.battle import BattleState

    m = next(
        (
            m
            for m in e.mechanics
            if type(m).__name__
            in ("ArcherQueenCloak", "MightyMinerSwitch", "GoblinsteinTether", "SkeletonKingSoulCollector")
        ),
        None,
    )
    if m is None:
        return None
    if type(m).__name__ == "SkeletonKingSoulCollector":
        import math
        spawn = m.ability.effects[0]
        effect = dict(kind="Skeleton", threshold=m.souls_per_activation,
                      offsets=[(spawn.radius_tiles * math.cos(2 * math.pi * i / spawn.count),
                                spawn.radius_tiles * math.sin(2 * math.pi * i / spawn.count))
                               for i in range(spawn.count)])
    elif type(m).__name__ == "MightyMinerSwitch":
        effect = dict(kind="Mighty", pending=m.pending_ms, cast_until=m.cast_until_ms)
    elif type(m).__name__ == "GoblinsteinTether":
        effect = dict(
            kind="Goblin",
            monster=m.monster_id,
            anchor=[m.anchor.x, m.anchor.y] if m.anchor is not None else None,
            next_hit=m.next_hit_ms,
            cast_until=m.cast_until_ms,
            damage=e.card_stats.get_scaled_stat(37),
            crown_damage=e.card_stats.get_scaled_stat(9),
        )
    else:
        effect = dict(
            kind="Queen",
            attack=m.attack_speed_multiplier,
            movement=m.movement_speed_multiplier,
            cast=m.cast_time_ms,
            delay=m.trigger_delay_ms,
            original_move=m._original_movement_mode_multiplier,
            pending=m._cloak_pending_until,
            cast_until=m._cast_lock_until,
        )
    a = m.ability
    return dict(
        key=BattleState._champion_ability_key(e),
        ability=dict(
            cost=a.elixir_cost,
            cooldown=a.cooldown_ms,
            duration=a.duration_ms,
            last_use=a.last_use_time,
            active=a.is_active,
            start=a.activation_time,
            frozen_allowed=LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN,
        ),
        effect=effect,
    )
