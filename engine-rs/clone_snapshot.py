"""Fresh clone capabilities from a separate oracle battle, never live mutation."""


def prototype(source):
    from differential import entity, initial, Position

    probe = initial()
    probe._spawn_unit_at_position(
        Position(9.0, 10.5), source.player_id, source.card_stats,
        deploy_delay_override=0.0, snap_to_valid=False,
        is_clone=True, clone_source=source,
    )
    child = probe.entities[max(probe.entities)]
    row = entity(child, clone_prototype=False)
    row['spawn_area_done'] = True
    row['spawn_push_done'] = True
    return row
