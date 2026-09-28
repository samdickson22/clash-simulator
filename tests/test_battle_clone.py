import copy

import numpy as np

from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.rl.action_space import DiscreteTileActionSpace


def _battle_signature(battle: BattleState):
    players = tuple(
        (
            player.elixir,
            tuple(player.hand),
            tuple(player.deck),
            tuple(player.cycle_queue),
            player.next_card_refill_cooldown_ms,
            player.left_tower_hp,
            player.right_tower_hp,
            player.king_tower_hp,
        )
        for player in battle.players
    )
    entities = tuple(
        (
            type(entity).__name__,
            entity.id,
            entity.player_id,
            entity.card_stats.name,
            entity.position.x,
            entity.position.y,
            entity.hitpoints,
            entity.target_id,
            entity.attack_cooldown,
            entity.deploy_delay_remaining,
            entity.placement_pending,
            entity.is_alive,
        )
        for entity in battle.entities.values()
    )
    return (
        battle.tick,
        battle.time,
        battle.game_over,
        battle.winner,
        battle.next_entity_id,
        players,
        entities,
    )


def test_lazy_loader_clone_has_independent_mutable_card_cache():
    source = CardDataLoader()
    source.load_cards()
    clone = source.clone_lazy()

    assert clone is not source
    assert clone._cards == {}
    assert next(iter(clone._card_definitions.values())) is next(
        iter(source._card_definitions.values())
    )

    source_knight = source.get_card("Knight")
    clone_knight = clone.get_card("Knight")
    assert source_knight is not None and clone_knight is not None
    assert clone_knight is not source_knight
    assert clone_knight.damage == source_knight.damage
    clone_knight.damage += 1
    assert clone_knight.damage != source_knight.damage


def test_battle_clone_matches_deepcopy_through_deploy_and_ticks():
    source = BattleState(fast_path=True)
    expected = copy.deepcopy(source)
    cloned = source.clone()
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    assert cloned.card_loader is not source.card_loader
    assert cloned.card_loader._cards == {}
    assert cloned.rng.getstate() == source.rng.getstate()
    assert _battle_signature(cloned) == _battle_signature(expected)
    assert cloned.players[0] is not source.players[0]
    assert cloned.rng is not source.rng
    assert not np.shares_memory(
        cloned._tower_tile_mask_world,
        source._tower_tile_mask_world,
    )
    assert not np.shares_memory(cloned._target_pos_x, source._target_pos_x)
    for entity_id, source_entity in source.entities.items():
        cloned_entity = cloned.entities[entity_id]
        assert cloned_entity is not source_entity
        assert cloned_entity.card_stats is not source_entity.card_stats
        assert cloned_entity.mechanics is not source_entity.mechanics
    for bucket in cloned._entity_buckets.values():
        for entity in bucket:
            assert entity is cloned.entities[entity.id]

    for player_id in (0, 1):
        expected_mask = action_space.legal_action_mask(
            expected,
            player_id,
            fast_path=True,
        )
        cloned_mask = action_space.legal_action_mask(
            cloned,
            player_id,
            fast_path=True,
        )
        np.testing.assert_array_equal(cloned_mask, expected_mask)
        legal = np.flatnonzero(expected_mask[: action_space.no_op_action])
        action = int(legal[0])
        assert action_space.apply_action(expected, player_id, action)
        assert action_space.apply_action(cloned, player_id, action)

    for _ in range(16):
        expected.step()
        cloned.step()
        assert _battle_signature(cloned) == _battle_signature(expected)

    cloned.players[0].elixir -= 1.0
    next(iter(cloned.entities.values())).hitpoints -= 1.0
    assert cloned.players[0].elixir != source.players[0].elixir
    assert next(iter(cloned.entities.values())).hitpoints != next(
        iter(source.entities.values())
    ).hitpoints
