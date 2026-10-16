"""Read-only Bandit mechanic serialization, including live anticipation/travel."""


def dash(e):
    m = next((m for m in e.mechanics if type(m).__name__ == 'BanditDash'), None)
    if m is None:
        return None, None
    spec = dict(minimum=m.dash_min_range, maximum=m.dash_max_range,
                windup=m.dash_duration_ms, speed=round(m.jump_speed),
                damage=float(e.card_stats.get_scaled_stat(m.dash_damage))
                    if m.dash_damage > 0 else e.damage*2.0,
                tail=m.post_dash_immunity_ms)
    state = dict(phase='travel' if e._bandit_dashing else 'charging' if e._bandit_charging else 'idle',
                 timer=e._bandit_dash_timer, target=e._bandit_dash_target_id,
                 destination=e._bandit_dash_target,
                 immunity=int(e._bandit_invulnerable_until),
                 consumed=bool(getattr(e,'_special_move_consumed_tick',False)))
    return spec, state
