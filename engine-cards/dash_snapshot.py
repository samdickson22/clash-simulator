"""Read-only Bandit-family dash serialization: stand, travel and the damage-only landing tail (Batch C1)."""


def dash(e):
    m = next((m for m in e.mechanics if type(m).__name__ == 'BanditDash'), None)
    if m is None:
        return None, None
    spec = dict(minimum=m.dash_min_range, maximum=m.dash_max_range,
                windup=m.dash_duration_ms, speed=round(m.jump_speed),
                damage=float(e.card_stats.get_scaled_stat(m.dash_damage))
                    if m.dash_damage > 0 else e.damage*2.0,
                tail=m.post_dash_immunity_ms)
    state = dict(phase=e._bandit_state, wait=int(e._bandit_wait), target=e._bandit_seen_target,
                 blocked=bool(e._bandit_blocked),
                 goal=None if e._bandit_goal is None else list(e._bandit_goal),
                 immunity=int(e._bandit_invulnerable_until),
                 consumed=bool(getattr(e,'_special_move_consumed_tick',False)))
    return spec, state
