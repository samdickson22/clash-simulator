import itertools
import json

import numpy as np
import pytest
import torch
from weighted_model import batch_loss, fit, make_model, predict_margin

torch.set_num_threads(1)


def test_weighted_draws_preserve_expected_absolute_loss_and_gradient():
    weights = torch.tensor([.1, .2, .7], dtype=torch.float64)
    target = torch.tensor([.1, -.3, .2], dtype=torch.float64)
    prediction = torch.tensor([-.2, .1, -.1], dtype=torch.float64, requires_grad=True)
    intended = (weights * (prediction - target).abs()).sum()
    expected = torch.zeros((), dtype=torch.float64)
    for left, right in itertools.product(range(3), repeat=2):
        indices = [left, right]
        expected = expected + weights[left] * weights[right] * batch_loss(prediction[indices], target[indices])
    torch.testing.assert_close(expected, intended, rtol=1e-14, atol=1e-14)
    torch.testing.assert_close(torch.autograd.grad(expected, prediction, retain_graph=True)[0],
                               torch.autograd.grad(intended, prediction)[0], rtol=1e-14, atol=1e-14)


@pytest.mark.parametrize("kind,width,parameters", [("numeric", 425, 14721), ("semantic", 809, 27009)])
def test_initial_baseline_and_excluded_row_isolation(kind, width, parameters):
    x = np.random.default_rng(9).random((16, width), dtype=np.float32)
    target = np.linspace(-.2, .2, 16)
    current = np.linspace(-1, 1, 16)
    model = make_model(kind)
    assert sum(p.numel() for p in model.parameters()) == parameters
    np.testing.assert_array_equal(predict_margin(model, x, current), current)
    weights = np.r_[np.full(8, .125), np.zeros(8)]
    expected = fit(x, target, np.arange(8), weights, kind=kind, seed=41, epochs=2, batch=4)
    x[8:], target[8:] = np.nan, np.nan
    actual = fit(x, target, np.arange(8), weights, kind=kind, seed=41, epochs=2, batch=4)
    for name, tensor in expected.state_dict().items():
        assert torch.equal(tensor, actual.state_dict()[name])


def test_no_readiness_refuses_before_data(tmp_path, monkeypatch):
    import weighted_experiment

    path = tmp_path / "readiness.json"
    path.write_text(json.dumps({"status": "not-ready"}))

    def forbidden(plan):
        raise AssertionError("unready weighted margin fit accessed corpus")

    monkeypatch.setattr(weighted_experiment, "prepare", forbidden)
    with pytest.raises(ValueError, match="readiness required"):
        weighted_experiment.run_fit(None, tmp_path / "plan.json", path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
