from __future__ import annotations

import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.player import PlayerState


class AnnotatedPlayerState(PlayerState):
    pass


def test_specialized_player_deepcopy_matches_generic_and_isolates_state() -> None:
    source = AnnotatedPlayerState(0)
    source.hand[1] = None
    source.cycle_queue.append("Knight")
    source.metadata = {"history": ["Archer"]}
    method = PlayerState.__deepcopy__
    try:
        del PlayerState.__deepcopy__
        generic = copy.deepcopy(source)
    finally:
        PlayerState.__deepcopy__ = method
    specialized = copy.deepcopy(source)

    assert type(specialized) is type(generic) is AnnotatedPlayerState
    assert specialized.__dict__ == generic.__dict__
    assert specialized is not source
    assert specialized.hand is not source.hand
    assert specialized.deck is not source.deck
    assert specialized.cycle_queue is not source.cycle_queue
    assert specialized.metadata is not source.metadata
    assert specialized.metadata["history"] is not source.metadata["history"]

    specialized.hand[0] = "Wizard"
    specialized.deck.append("Tesla")
    specialized.cycle_queue.append("Giant")
    specialized.metadata["history"].append("Minions")
    assert specialized.hand != source.hand
    assert specialized.deck != source.deck
    assert specialized.cycle_queue != source.cycle_queue
    assert specialized.metadata != source.metadata


def test_specialized_player_deepcopy_preserves_container_aliases() -> None:
    source = PlayerState(0)
    source.deck = source.hand

    cloned = copy.deepcopy(source)

    assert cloned.hand is cloned.deck
    assert cloned.hand is not source.hand


def test_specialized_player_deepcopy_matches_generic_battle_clone() -> None:
    source = BattleState(fast_path=True)
    assert source.deploy_card(0, "Knight", Position(3.5, 10.5))
    method = PlayerState.__deepcopy__
    try:
        del PlayerState.__deepcopy__
        generic = source.clone()
    finally:
        PlayerState.__deepcopy__ = method
    specialized = source.clone()

    assert [player.__dict__ for player in specialized.players] == [
        player.__dict__ for player in generic.players
    ]
    assert specialized.rng.getstate() == generic.rng.getstate() == source.rng.getstate()
    for original, cloned in zip(source.players, specialized.players):
        assert cloned is not original
        assert cloned.hand is not original.hand
        assert cloned.deck is not original.deck
        assert cloned.cycle_queue is not original.cycle_queue

    specialized.players[0].hand[0] = "Wizard"
    assert specialized.players[0].hand != source.players[0].hand
