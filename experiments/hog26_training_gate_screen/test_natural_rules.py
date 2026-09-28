"""Duplicating states cannot manufacture game mass or independent coverage."""

import numpy as np
import pytest
from natural_rules import full_phase_rules


def protocol():
    return {'gates': {'cluster_bootstrap_replicates': 2000, 'maximum_ece': .2, 'minimum_natural_phase_auc': .55,
                      'maximum_natural_draw_probability': .1},
            'generalization_evaluation': {'full_phase_margin_gate': {'weighting': 'equal-game-within-phase-v1'},
                'minimum_independent_matchup_clusters_per_slice': 8, 'minimum_clusters_with_each_decisive_outcome_per_slice': 2,
                'phase_margin_learning_gate': {'minimum_mae_improvement': .001, 'minimum_cluster_bootstrap_lower_95_improvement': 0.},
                'full_phase_classification_gate': {'required': True}}}


def test_game_mass_and_cluster_coverage_survive_row_duplication():
    ids = np.array([0, 0, 1])
    p = np.array([[.9, 0, .1], [.8, 0, .2], [.1, 0, .9]])
    prediction = np.array([-.3, -.1, .3])
    target = np.array([-.4, -.4, .4])
    current = np.zeros(3)
    outcomes = np.array([-1, -1, 1])
    clusters = np.array([7, 7, 8])
    phases = np.zeros(3, dtype=int)
    mask = np.ones(3, dtype=bool)
    arrays = (ids, p, prediction, target, current, outcomes, clusters, phases, mask)
    expected = full_phase_rules(*arrays, protocol(), 42)
    order = np.array([0, 1, 0, 1, 0, 1, 2])
    repeated = full_phase_rules(*(x[order] for x in arrays), protocol(), 42)
    for key in ('mae', 'baseline_mae'):
        assert repeated['early'][key] == pytest.approx(expected['early'][key])
    assert repeated['early']['independent_clusters'] == expected['early']['independent_clusters'] == 2
    assert not repeated['early']['coverage_passed']
    for key in ('point', 'lower_95', 'upper_95'):
        assert repeated['early']['margin_interval'][key] == pytest.approx(expected['early']['margin_interval'][key])
    assert expected['middle']['games'] == 0 and not expected['middle']['passed']
    assert repeated['late'] == expected['late']
