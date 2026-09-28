import json

import numpy as np
import pytest
import torch
from semantic_training import SemanticResidualMargin, fit_residual, predict_margin

torch.set_num_threads(1)


def test_initial_output_is_exact_baseline_with_physical_inputs():
    x = np.random.default_rng(31).random((32, 809), dtype=np.float32)
    baseline = np.linspace(-1, 1, 32)
    model = SemanticResidualMargin()
    assert sum(p.numel() for p in model.parameters()) == 27009
    np.testing.assert_array_equal(predict_margin(model, x, baseline), baseline)


def test_excluded_rows_cannot_change_optimizer_updates():
    rng = np.random.default_rng(41)
    x = rng.normal(size=(16, 809)).astype(np.float32)
    y = rng.uniform(-.2, .2, 16)
    weights = np.r_[np.full(8, 1 / 8), np.zeros(8)]
    expected = fit_residual(x, np.arange(8), y, weights, seed=37, epochs=2, batch_rows=4)
    x[8:] = np.nan
    y[8:] = np.nan
    actual = fit_residual(x, np.arange(8), y, weights, seed=37, epochs=2, batch_rows=4)
    for name, tensor in expected.state_dict().items():
        assert torch.equal(tensor, actual.state_dict()[name])


def test_no_memory_readiness_refuses_before_data_access(tmp_path, monkeypatch):
    import semantic_experiment

    readiness = tmp_path / "readiness.json"
    readiness.write_text(json.dumps({"status": "not-ready"}))

    def forbidden(*args, **kwargs):
        raise AssertionError("unready fit accessed data")

    monkeypatch.setattr(semantic_experiment, "prepare_data", forbidden)
    with pytest.raises(ValueError, match="readiness required"):
        semantic_experiment.run_fit(None, tmp_path / "plan.json", readiness, tmp_path / "fit")
    assert not (tmp_path / "fit").exists()


def test_semantic_optimizer_can_learn_a_physical_signal():
    x = np.zeros((32, 809), dtype=np.float32)
    x[16:, 425:] = 1
    target = np.r_[np.zeros(16), np.full(16, .2)]
    model = fit_residual(x, np.arange(32), target, np.full(32, 1 / 32),
                         seed=37, epochs=30, batch_rows=16)
    prediction = predict_margin(model, x, np.zeros(32))
    assert prediction[16:].mean() > prediction[:16].mean() + .05
    assert np.abs(prediction - target).mean() < .05
