import numpy as np
import pytest
from scalar_evaluation import (
    cluster_bootstrap,
    coverage,
    empirical_prior,
    evaluation_weights,
    fitting_weights,
    fold_masks,
    metrics,
    phase_ids,
    raw_wdl_to_class_index,
    representatives,
    slice_masks,
)


def test_writer_order_conversion():
    assert raw_wdl_to_class_index(np.eye(3, dtype=int)).tolist() == [2, 1, 0]
    with pytest.raises(ValueError):
        raw_wdl_to_class_index([0.4, 0.2, 0.4])


def test_phase_boundaries_and_representative_tie():
    assert phase_ids([0, 1 / 3, 2 / 3, 1.4]).tolist() == [0, 1, 2, 2]
    assert representatives([0] * 4, [0.125, 0.125, 0.5, 0.9]).tolist() == [
        True,
        False,
        True,
        True,
    ]


def test_equal_game_phase_weights_and_exact_exclusion():
    games = np.array([0, 0, 0, 0, 1, 1, 2, 2])
    progress = np.array([0.1, 0.2, 0.4, 0.8, 0.1, 0.2, 0.5, 0.9])
    fit = games != 2
    wdl, margin = fitting_weights(games, progress, fit)
    assert wdl[games == 0].sum() == pytest.approx(0.5)
    assert wdl[games == 1].sum() == pytest.approx(0.5)
    assert wdl[:2].sum() == pytest.approx(1 / 6)
    assert np.all(wdl[~fit] == 0) and np.all(margin[~fit] == 0)
    for phase in range(3):
        assert margin[phase_ids(progress) == phase].sum() == pytest.approx(1 / 3)
    assert margin[4] + margin[5] == pytest.approx(0.25)
    assert margin[5] == pytest.approx(
        3 * margin[4]
    )  # nearer center gets uniform + rep mass
    assert margin.sum() == pytest.approx(1)


def test_no_partial_game_exclusion_or_unknown_family():
    with pytest.raises(ValueError):
        fitting_weights([0, 0], [0.1, 0.2], [True, False])
    with pytest.raises(ValueError):
        fold_masks([0, 1], ["family-000", "family-008"], 0)
    fit, excluded = fold_masks([0, 0, 1, 1], ["family-000"] * 2 + ["family-002"] * 2, 0)
    assert fit.tolist() == [False, False, True, True]
    assert np.all(fit != excluded)


def test_evaluation_equal_games_inside_phase():
    games, progress = [0, 0, 0, 1, 1], [0.1, 0.2, 0.5, 0.1, 0.2]
    w = evaluation_weights(games, progress)
    np.testing.assert_allclose(w, [0.125, 0.125, 0.5, 0.125, 0.125])
    r = evaluation_weights(games, progress, representative=True)
    assert np.count_nonzero(r) == 3
    assert r.sum() == pytest.approx(1)


def test_prior_counts_games_not_rows_and_excludes_labels():
    prior = empirical_prior([0, 0, 0, 1, 2], np.array([2, 2, 2, 0, 1]), [1, 1, 1, 1, 0])
    np.testing.assert_array_equal(prior, [0.5, 0, 0.5])


def fixture():
    p = np.array([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8], [0.7, 0.1, 0.2], [0.2, 0.1, 0.7]])
    labels = np.array([0, 2, 0, 2])
    pred, target, baseline = (
        np.array([-0.8, 0.8, -0.7, 0.7]),
        np.array([-1, 1, -1, 1]),
        np.zeros(4),
    )
    return p, labels, pred, target, baseline, np.full(4, 0.25), np.array([0.5, 0, 0.5])


def test_metrics_order_auc_and_margin_gain():
    result = metrics(*fixture())
    assert result["decisive_auc"] == 1
    assert result["margin_mae"] == pytest.approx(0.25)
    assert result["margin_gain"] == pytest.approx(0.75)
    assert result["observed_mass_draw"] == 0
    assert result["nll_gain"] > 0
    args = list(fixture())
    args[0] = np.full((4, 3), 1 / 3)
    assert metrics(*args)["decisive_auc"] == pytest.approx(0.5)


def test_paired_seats_cluster_together_and_repeats_not_independent():
    result = cluster_bootstrap(
        *fixture(),
        ["scenario-a", "scenario-a", "scenario-b", "scenario-b"],
        replicates=50,
    )
    assert result["scenario_clusters"] == 2
    assert result["intervals"]["decisive_auc"]["undefined_replicates"] == 0
    info = coverage([0, 1, 2, 3], fixture()[1], ["a", "a", "b", "b"], np.ones(4))
    assert info["scenario_clusters"] == 2
    assert info["clusters_containing_loss"] == info["clusters_containing_win"] == 2
    args = fixture()
    repeated = tuple(
        np.tile(a, (2, 1)) if a.ndim == 2 else np.tile(a, 2) for a in args[:6]
    ) + (args[6],)
    repeated_result = cluster_bootstrap(
        *repeated, ["a", "a", "b", "b"] * 2, replicates=50
    )
    for key in result["intervals"]:
        assert repeated_result["intervals"][key] == pytest.approx(
            result["intervals"][key]
        )


def test_undefined_auc_bootstrap_reported():
    args = list(fixture())
    args[1] = np.zeros(4, dtype=int)
    result = cluster_bootstrap(*args, ["a", "a", "b", "b"], replicates=10)
    assert result["point"]["decisive_auc"] is None
    assert result["intervals"]["decisive_auc"]["undefined_replicates"] == 10


def test_row_aligned_oof_priors():
    args = list(fixture())
    args[-1] = np.tile(args[-1], (4, 1))
    assert metrics(*args) == metrics(*fixture())


def test_slices_keep_missing_coverage():
    masks = slice_masks([0.1, 0.9], [0, 1], ["balanced", "random"], [0, 1])
    assert len(masks) == 52
    assert not masks["phase/middle/seat/0/style/balanced"].any()


def test_optimized_bootstrap_matches_direct_resampling():
    rng = np.random.default_rng(7)
    p = rng.dirichlet([1, 1, 1], size=20)
    labels = np.tile([0, 1, 2, 2], 5)
    pred, target, base = rng.uniform(-1, 1, (3, 20))
    w = rng.uniform(0.01, 1, 20)
    prior = np.tile([0.3, 0.2, 0.5], (20, 1))
    clusters = np.repeat(np.arange(5), 4)
    actual = cluster_bootstrap(
        p, labels, pred, target, base, w, prior, clusters, replicates=40, seed=8
    )
    counts = np.random.default_rng(8).multinomial(5, np.full(5, 0.2), size=40)
    naive = [
        metrics(p, labels, pred, target, base, w * count[clusters], prior)
        for count in counts
    ]
    for key, interval in actual["intervals"].items():
        vals = [r[key] for r in naive if r[key] is not None]
        assert interval["lower_95"] == pytest.approx(
            np.quantile(vals, 0.025), abs=1e-13
        )
        assert interval["upper_95"] == pytest.approx(
            np.quantile(vals, 0.975), abs=1e-13
        )


def _reference_representatives(games, progress):
    phases = phase_ids(progress)
    result = np.zeros(len(progress), bool)
    for game in np.unique(games):
        for phase, center in enumerate((1 / 6, 0.5, 5 / 6)):
            rows = np.flatnonzero((games == game) & (phases == phase))
            if len(rows):
                result[rows[np.argmin(np.abs(progress[rows] - center))]] = True
    return result


def _reference_evaluation_weights(games, progress, mask, representative):
    phases = phase_ids(progress)
    if representative:
        mask = mask & _reference_representatives(games, progress)
    result = np.zeros(len(progress))
    reached = np.unique(phases[mask])
    for phase in reached:
        phase_games = np.unique(games[mask & (phases == phase)])
        for game in phase_games:
            rows = mask & (phases == phase) & (games == game)
            result[rows] = 1 / (len(reached) * len(phase_games) * rows.sum())
    return result


def test_vectorized_index_matches_reference_unordered_arbitrary_masks():
    from scalar_evaluation import EvaluationIndex

    rng = np.random.default_rng(925)
    games = rng.integers(0, 47, 5000)
    progress = rng.uniform(0, 1.3, len(games))
    progress[::5] = 0.5  # exact ties, preserve incoming row order
    index = EvaluationIndex(games, progress)
    np.testing.assert_array_equal(
        representatives(games, progress, index=index),
        _reference_representatives(games, progress),
    )
    for _ in range(20):
        mask = rng.random(len(games)) < rng.uniform(0.01, 1)
        for rep in (False, True):
            actual = evaluation_weights(
                games, progress, mask, representative=rep, index=index
            )
            expected = _reference_evaluation_weights(games, progress, mask, rep)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-13)


def test_index_empty_slices_validation_and_independent_outputs():
    from scalar_evaluation import EvaluationIndex

    index = EvaluationIndex([0, 0, 1], [0.1, 0.5, 0.8])
    a = representatives([0, 0, 1], [0.1, 0.5, 0.8], index=index)
    a[:] = False
    assert representatives([0, 0, 1], [0.1, 0.5, 0.8], index=index).all()
    assert not evaluation_weights(
        [0, 0, 1], [0.1, 0.5, 0.8], [False] * 3, index=index
    ).any()
    assert not representatives([], []).any()
    assert not evaluation_weights([], []).any()
    with pytest.raises(ValueError):
        evaluation_weights([0, 0, 1], [0.1, 0.5, 0.9], index=index)
    with pytest.raises(ValueError):
        evaluation_weights([0, 0, 1], [0.1, 0.5, 0.8], [[True] * 3], index=index)
