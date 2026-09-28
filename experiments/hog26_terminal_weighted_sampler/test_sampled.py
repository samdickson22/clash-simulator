import itertools
import json

import numpy as np
import pytest
import torch
from sampled_model import batch_loss, fit

torch.set_num_threads(1)


def test_sampling_estimator_has_the_same_expected_loss_and_gradient():
    weights = torch.tensor([.1, .2, .7], dtype=torch.float64)
    labels = torch.tensor([0., 1., 1.], dtype=torch.float64)
    logits = torch.tensor([-.4, .6, -.1], dtype=torch.float64, requires_grad=True)
    intended = (weights * torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, reduction="none")).sum()
    expected = torch.zeros((), dtype=torch.float64)
    for left, right in itertools.product(range(3), repeat=2):
        indices = [left, right]
        expected = expected + weights[left] * weights[right] * batch_loss(logits[indices], labels[indices])
    torch.testing.assert_close(expected, intended, rtol=1e-14, atol=1e-14)
    torch.testing.assert_close(torch.autograd.grad(expected, logits, retain_graph=True)[0],
                               torch.autograd.grad(intended, logits)[0], rtol=1e-14, atol=1e-14)


def test_sampler_and_prior_never_use_excluded_rows():
    x = np.random.default_rng(9).random((16, 809), dtype=np.float32)
    y = np.tile([0., 1.], 8)
    weights = np.r_[np.full(8, .125), np.zeros(8)]
    expected, prior = fit(x, y, np.arange(8), weights, 41, epochs=3, batch=4)
    x[8:], y[8:] = np.nan, np.nan
    actual, actual_prior = fit(x, y, np.arange(8), weights, 41, epochs=3, batch=4)
    assert prior == actual_prior == .5
    for name, value in expected.state_dict().items():
        assert torch.equal(value, actual.state_dict()[name])


def test_sampled_fitting_requires_its_own_readiness(tmp_path, monkeypatch):
    import sampled_experiment

    path = tmp_path / "readiness.json"
    path.write_text(json.dumps({"status": "not-ready"}))

    def forbidden(plan):
        raise AssertionError("unready sampled fit accessed corpus")

    monkeypatch.setattr(sampled_experiment, "prepare", forbidden)
    with pytest.raises(ValueError, match="readiness required"):
        sampled_experiment.run_fit(None, tmp_path / "plan.json", path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
