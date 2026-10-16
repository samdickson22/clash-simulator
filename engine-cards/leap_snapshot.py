"""Read-only Mega Knight timed-dash serialization: stand, travel to the blow, post-blow hold (Batch C1)."""


def leap(e):
    m=next((m for m in e.mechanics if type(m).__name__=='MegaKnightSlam'),None)
    if m is None:return None,None
    scale=e.card_stats.get_scaled_stat
    spec=dict(minimum=m.jump_min_range,maximum=m.jump_max_range,windup=m.leap_duration_ms,
              speed=round(m.jump_speed),airborne=m.airborne_duration_ms,landing=m.landing_duration_ms,
              damage=float(scale(m.jump_damage)),radius=m.slam_radius,push=m.jump_knockback,
              spawn_damage=float(scale(m.spawn_damage)),spawn_radius=m.spawn_radius,spawn_push=m.spawn_knockback)
    state=dict(phase=e._mk_leap_phase or 'idle',wait=int(e._mk_wait),mark=int(e._mk_mark),
               target=e._mk_leap_target_id,seen=e._mk_seen_target,blocked=bool(e._mk_blocked),
               goal=None if e._mk_goal is None else list(e._mk_goal),
               consumed=bool(getattr(e,'_special_move_consumed_tick',False)),
               spawned=not bool(getattr(e,'_spawn_hook_pending',False)))
    return spec,state
