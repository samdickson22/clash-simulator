import numpy as np
import pytest

from scripts.hog26_scalar_reference_episode import ScalarReferenceEpisode

DECK = ("Knight", "Archer", "Giant", "Minions", "Musketeer", "Fireball", "Log", "Cannon")


def create(seat=0):
    return ScalarReferenceEpisode.create([DECK, tuple(reversed(DECK))], seed=1279017,
                                         learner_seat=seat)


def test_explicit_openings_and_replay_action_order_without_private_masks(monkeypatch):
    first, second = create(), create()
    for episode in (first, second):
        assert episode.battle.players[0].hand == list(episode.battle.players[0].deck[:4])
        assert list(episode.battle.players[0].cycle_queue) == episode.battle.players[0].deck[4:]

        def forbidden(*args, **kwargs):
            raise AssertionError("private legality mask called")

        monkeypatch.setattr(episode.action_space, "legal_action_mask", forbidden)
    masks = np.zeros((2, 2306), dtype=bool)
    masks[:, 2304] = True
    for _ in range(5):
        assert first.step([2304, 2304], masks) == second.step([2304, 2304], masks)
        assert first.battle.tick == second.battle.tick
        assert first.battle.rng.getstate() == second.battle.rng.getstate()
        assert [p.elixir for p in first.battle.players] == [p.elixir for p in second.battle.players]
    assert first.battle.tick == 40


def test_unauthorized_action_rejected_before_any_episode_mutation():
    episode = create()
    order_state = episode.action_order_rng.getstate()
    with pytest.raises(ValueError, match="supplied public mask"):
        episode.step([2304, 2304], np.zeros((2, 2306), dtype=bool))
    assert episode.battle.tick == 0
    assert episode.action_order_rng.getstate() == order_state


def test_terminal_has_no_automatic_reset_and_order_is_learner_relative():
    first, second = create(0), create(1)
    masks = np.ones((2, 2306), dtype=bool)
    a = first.step([2304, 2304], masks)
    b = second.step([2304, 2304], masks)
    assert a["action_order"] == tuple(1 - seat for seat in b["action_order"])
    first.battle.game_over = True
    with pytest.raises(RuntimeError, match="already terminal"):
        first.step([2304, 2304], masks)
    assert first.battle.tick == 8
