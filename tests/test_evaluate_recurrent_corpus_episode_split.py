import numpy as np
import pytest

from scripts.evaluate_recurrent_corpus import _select_episode_ids


def test_episode_complement_is_disjoint_and_complete() -> None:
    episode_ids = np.repeat(np.arange(116), 2)
    development = _select_episode_ids(
        episode_ids,
        max_episodes=64,
        episode_seed=1068604,
        exclude_max_episodes=None,
        exclude_episode_seed=None,
    )
    complement = _select_episode_ids(
        episode_ids,
        max_episodes=None,
        episode_seed=0,
        exclude_max_episodes=64,
        exclude_episode_seed=1068604,
    )
    assert development.size == 64
    assert complement.size == 52
    assert not np.intersect1d(development, complement).size
    np.testing.assert_array_equal(
        np.union1d(development, complement), np.arange(116)
    )


def test_episode_exclusion_arguments_require_each_other() -> None:
    with pytest.raises(ValueError, match="require each other"):
        _select_episode_ids(
            np.arange(4),
            max_episodes=None,
            episode_seed=0,
            exclude_max_episodes=2,
            exclude_episode_seed=None,
        )


def test_explicit_episode_ids_are_exact_and_reject_unknowns() -> None:
    episode_ids = np.asarray([1, 1, 2, 3, 3], dtype=np.int64)
    selected = _select_episode_ids(
        episode_ids,
        max_episodes=None,
        episode_seed=1,
        exclude_max_episodes=None,
        exclude_episode_seed=None,
        explicit_episode_ids=[3, 1, 3],
    )
    np.testing.assert_array_equal(selected, np.asarray([1, 3]))
    with pytest.raises(ValueError, match="unknown explicit episode IDs"):
        _select_episode_ids(
            episode_ids,
            max_episodes=None,
            episode_seed=1,
            exclude_max_episodes=None,
            exclude_episode_seed=None,
            explicit_episode_ids=[4],
        )
