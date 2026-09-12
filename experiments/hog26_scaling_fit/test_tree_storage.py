import numpy as np
import pytest
from scalar_features import build_game_features
from test_scalar_dataset import game
from tree_storage import fitting_features


def test_only_fitting_rows_same_values_and_order():
    games = [game(3),game(5),game(2)]
    games[1].public['global_features'][:,0] = .5
    reference = np.concatenate([build_game_features(**g.public,vocabulary_size=5) for g in games])
    actual = fitting_features(games,[0,2],5)
    np.testing.assert_array_equal(actual,reference[np.r_[0:3,8:10]].astype(np.float64))
    games[1].public['global_features'][:] = np.nan
    np.testing.assert_array_equal(actual,fitting_features(games,[0,2],5))


def test_capacity_and_duplicate_order_fail_before_allocation():
    with pytest.raises(MemoryError):
        fitting_features([game(3)],[0],5,max_bytes=1)
    with pytest.raises(ValueError):
        fitting_features([game(3)],[0,0],5)
