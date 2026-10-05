"""Read-only Fisherman wind-up, hook flight and drag state."""

def hook(e):
    from clasher.kinematics import tiles_per_second_to_logic_speed
    m=next((m for m in e.mechanics if type(m).__name__=='FishermanHook'),None)
    if m is None:return None,None
    spec=dict(minimum=m.hook_min_range,maximum=m.hook_range,windup=m.hook_windup_ms,
              speed=tiles_per_second_to_logic_speed(m.projectile_speed),
              drag=tiles_per_second_to_logic_speed(m.drag_back_speed),
              self_drag=tiles_per_second_to_logic_speed(m.drag_self_speed),
              attractor=m.drag_back_as_attractor,margin=m.drag_margin)
    state=dict(phase=m.state,target=m.hook_target_id,remaining=m.windup_remaining_ms,
               position=None if m.hook_position is None else (m.hook_position.x,m.hook_position.y),
               consumed=bool(getattr(e,'_special_move_consumed_tick',False)))
    return spec,state
