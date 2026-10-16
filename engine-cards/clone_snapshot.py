"""Fresh clone capabilities from a separate oracle battle, never live mutation."""


def prototype(source):
    from differential import entity, initial, Position

    probe = initial()
    parent_id = probe.next_entity_id
    probe._spawn_unit_at_position(
        Position(9.0, 10.5), source.player_id, source.card_stats,
        deploy_delay_override=0.0, snap_to_valid=False,
        is_clone=True, clone_source=source,
    )
    child = probe.entities[parent_id]
    row = entity(child, clone_prototype=False)
    row['spawn_area_done'] = True
    row['spawn_push_done'] = True
    # on_created may append attached bodies. Keep their immutable graph with
    # the parent; native Clone allocates all IDs before remapping mount links.
    children = [entity(e, clone_prototype=False) for e in probe.entities.values()
                if e.id > parent_id and getattr(e, '_rider_mount', None) is not None]
    if children:
        row['clone_children'] = children
    return row
