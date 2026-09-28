import json

import numpy as np
import pytest
import torch
from terminal_metrics import binary_auc, measure
from terminal_model import TerminalPredictor, fit, predict

torch.set_num_threads(1)


def test_prior_initialization_and_parameter_count():
    model = TerminalPredictor(.2)
    assert sum(p.numel() for p in model.parameters()) == 27009
    p = predict(model, np.ones((8, 809), dtype=np.float32))
    np.testing.assert_allclose(p, .2, atol=1e-7)


def test_excluded_targets_do_not_change_fit_or_prior():
    x = np.random.default_rng(3).random((16, 809), dtype=np.float32)
    y = np.tile([0., 1.], 8)
    w = np.r_[np.full(8, 1 / 8), np.zeros(8)]
    expected, prior = fit(x, y, np.arange(8), w, 41, epochs=2, batch=4)
    x[8:], y[8:] = np.nan, np.nan
    actual, actual_prior = fit(x, y, np.arange(8), w, 41, epochs=2, batch=4)
    assert prior == actual_prior == .5
    for name, tensor in expected.state_dict().items():
        assert torch.equal(tensor, actual.state_dict()[name])


def test_binary_prior_identity_and_cluster_repeat_invariance():
    p = np.array([.1, .8, .3, .6])
    y = np.array([0, 1, 0, 1])
    weights = np.full(4, .25)
    clusters = np.array(["a", "a", "b", "b"])
    expected = measure(p, y, p, weights, clusters, intervals=True)
    assert expected["metrics"]["nll_gain"] == 0
    assert expected["intervals"]["nll_gain"] == {"lower_95": 0, "upper_95": 0}
    repeated = measure(np.repeat(p, 3), np.repeat(y, 3), np.repeat(p, 3),
                       np.repeat(weights / 3, 3), np.repeat(clusters, 3), intervals=True)
    for metric in expected["metrics"]:
        assert np.isclose(expected["metrics"][metric], repeated["metrics"][metric])
    assert binary_auc(p, y, weights) == 1
    assert binary_auc(np.ones(4), y, weights) == .5


def test_invalid_readiness_refuses_before_data(tmp_path, monkeypatch):
    import terminal_experiment

    p = tmp_path / "readiness.json"
    p.write_text(json.dumps({"status": "not-ready"}))

    def forbidden(plan):
        raise AssertionError("unready fit accessed corpus")

    monkeypatch.setattr(terminal_experiment, "prepare", forbidden)
    with pytest.raises(ValueError, match="readiness required"):
        terminal_experiment.run_fit(None, tmp_path / "plan.json", p, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_terminal_label_rejects_truncated_or_ambiguous_game(tmp_path):
    from terminal_labels import load_labels, sha

    p = tmp_path / "game.npz"
    np.savez(p, tick=np.array([0, 10]), terminal_tick=50,
             decision_interval_ticks=10, actual_terminal=True)
    with pytest.raises(ValueError, match="ambiguous"):
        load_labels([{"path": str(p), "sha256": sha(p)}])
