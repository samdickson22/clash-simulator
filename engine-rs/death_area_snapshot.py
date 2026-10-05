"""Read-only templates for the oracle's nested death-area object chain."""


def child_template(e):
    from differential import entity, initial
    from clasher.mechanics.shared.death_area import (
        spawn_death_area_container, spawn_death_area_payload,
        spawn_death_area_object,
    )

    b = initial()
    common = dict(battle_state=b, player_id=e.player_id,
                  position=e.position, card_stats=e.card_stats)
    if type(e).__name__ == "DeathAreaStartAction":
        child = spawn_death_area_container(**common, spawn_data=e.spawn_data,
                                          area_data=e.area_data)
    elif type(e).__name__ == "DeathAreaEffectContainer":
        child = spawn_death_area_payload(**common, area_data=e.area_data)
    elif type(e).__name__ == "BuffAreaEffect" and e.impact_area_data is not None:
        child = spawn_death_area_object(**common, area_data=e.impact_area_data)
        child.damage = e.impact_damage
        child.crown_tower_damage_multiplier = e.crown_tower_damage_multiplier
        child.crown_tower_damage = e.crown_tower_damage
        child.affects_hidden = e.impact_affects_hidden
    else:
        return None
    return entity(child)
