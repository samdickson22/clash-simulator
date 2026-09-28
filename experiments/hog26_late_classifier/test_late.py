"""Late comparison must give equal game mass despite unequal trajectory lengths."""

import numpy as np
from review_late import paired_nll


def test_game_weight_and_scenario_interval_survive_row_duplication():
    ids = np.array([0, 0, 1, 2])
    clusters = np.array([0, 0, 0, 1])
    labels = np.array([0, 0, 2, 0])
    before = np.array([[.5, 0, .5], [.4, 0, .6], [.4, 0, .6], [.7, 0, .3]])
    after = np.array([[.6, 0, .4], [.7, 0, .3], [.5, 0, .5], [.8, 0, .2]])
    mask = np.ones(4, dtype=bool)
    args = ids, clusters, labels, before, after, mask
    expected = paired_nll(*args, representatives=False)
    order = np.array([0, 1, 0, 1, 2, 3])
    actual = paired_nll(*(a[order] for a in args), representatives=False)
    assert actual == expected
    assert actual['independent_clusters'] == 2
