from __future__ import annotations

import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity


def _entity_public_signature(entity: Entity) -> tuple[object, ...]:
    return (
        type(entity),
        entity.id,
        entity.player_id,
        entity.position.x,
        entity.position.y,
        entity.hitpoints,
        entity.target_id,
        entity.is_alive,
        tuple(type(mechanic) for mechanic in entity.mechanics),
        tuple(sorted(entity.__dict__)),
    )


def test_specialized_entity_deepcopy_matches_generic_and_isolates_state() -> None:
    source = BattleState(fast_path=True)
    assert source.deploy_card(0, "Knight", Position(3.5, 10.5))
    source.players[0].hand[0] = "Tesla"
    source.players[0].elixir = 10.0
    assert source.deploy_card(0, "Tesla", Position(9.5, 10.5))
    method = Entity.__deepcopy__
    try:
        del Entity.__deepcopy__
        generic = copy.deepcopy(source)
    finally:
        Entity.__deepcopy__ = method
    specialized = copy.deepcopy(source)

    assert tuple(map(_entity_public_signature, specialized.entities.values())) == tuple(
        map(_entity_public_signature, generic.entities.values())
    )
    for entity_id, cloned in specialized.entities.items():
        original = source.entities[entity_id]
        assert cloned is not original
        assert cloned.position is not original.position
        assert cloned.card_stats is not original.card_stats
        assert cloned.mechanics is not original.mechanics
        assert all(
            cloned_mechanic is not original_mechanic
            for cloned_mechanic, original_mechanic in zip(
                cloned.mechanics,
                original.mechanics,
            )
        )
        assert cloned.battle_state is specialized

    deployed_id = max(source.entities)
    specialized_deployed = specialized.entities[deployed_id]
    specialized_deployed.position.x += 1.0
    specialized_deployed.hitpoints -= 1.0
    specialized_deployed.mechanics.append(object())
    assert specialized_deployed.position.x != source.entities[deployed_id].position.x
    assert specialized_deployed.hitpoints != source.entities[deployed_id].hitpoints
    assert len(specialized_deployed.mechanics) != len(
        source.entities[deployed_id].mechanics
    )
