"""Check direction and paired-scenario dependence of reported intervals."""

import numpy as np
import pytest
from margin_metrics import paired, score


def test_paired_direction_identity_and_scenario_unit():
    target = np.array([0., 0., 0., 0.])
    before = np.array([.4, .2, .2, .4])
    after = np.array([.1, .3, .1, .1])
    clusters = np.array([0, 0, 1, 1])
    result = paired(target, before, after, clusters)
    assert result['point'] == pytest.approx(score(target, before) - score(target, after))
    reverse = paired(target, after, before, clusters)
    assert reverse['lower_95'] == pytest.approx(-result['upper_95'])
    assert reverse['upper_95'] == pytest.approx(-result['lower_95'])
    repeated = paired(*(np.repeat(x, 3) for x in (target, before, after, clusters)))
    for key in ('point', 'lower_95', 'upper_95'):
        assert repeated[key] == pytest.approx(result[key])
    assert repeated['clusters'] == result['clusters'] == 2
    identity = paired(target, before, before, clusters)
    assert identity['point'] == identity['lower_95'] == identity['upper_95'] == 0


def test_invalid_margin_rows_rejected():
    with pytest.raises(ValueError):
        paired(np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0))
    with pytest.raises(ValueError):
        paired(np.zeros(2), np.zeros(1), np.zeros(2), np.zeros(2))
    with pytest.raises(ValueError):
        paired(np.zeros(2), np.zeros(2), np.array([0., np.nan]), np.zeros(2))
