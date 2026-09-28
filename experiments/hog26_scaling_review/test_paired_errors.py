import numpy as np
import pytest
from paired_errors import paired_error_intervals


def fixture():
    return {
        "old_probability": np.array([[.8, .0, .2], [.7, .0, .3], [.4, .0, .6], [.2, .0, .8]]),
        "new_probability": np.array([[.9, .0, .1], [.8, .0, .2], [.3, .0, .7], [.1, .0, .9]]),
        "old_margin": np.array([-.5, -.3, .2, .5]), "new_margin": np.array([-.7, -.5, .4, .7]),
        "labels": np.array([0, 0, 2, 2]), "terminal_margin": np.array([-1., -1., 1., 1.]),
        "weights": np.array([.1, .2, .3, .4]), "clusters": np.array(["a", "b", "a", "b"]),
    }


def test_identical_models_have_exact_zero_change():
    data = fixture()
    data["new_probability"] = data["old_probability"].copy()
    data["new_margin"] = data["old_margin"].copy()
    result = paired_error_intervals(**data)
    assert all(v == 0 for metric in result["metrics"].values() for v in metric.values())


def test_repeating_rows_does_not_create_independent_scenarios():
    data = fixture()
    expected = paired_error_intervals(**data)
    repeated = {k: np.repeat(v, 5, axis=0) for k, v in data.items()}
    repeated["weights"] /= 5
    actual = paired_error_intervals(**repeated)
    assert actual["scenario_clusters"] == expected["scenario_clusters"] == 2
    for name, metric in expected["metrics"].items():
        for field, value in metric.items():
            assert actual["metrics"][name][field] == pytest.approx(value)


def test_swapping_models_reverses_the_paired_interval():
    data = fixture()
    expected = paired_error_intervals(**data)
    for kind in ("probability", "margin"):
        data["old_" + kind], data["new_" + kind] = data["new_" + kind], data["old_" + kind]
    actual = paired_error_intervals(**data)
    for name, metric in expected["metrics"].items():
        assert actual["metrics"][name]["point"] == pytest.approx(-metric["point"])
        assert actual["metrics"][name]["lower_95"] == pytest.approx(-metric["upper_95"])
        assert actual["metrics"][name]["upper_95"] == pytest.approx(-metric["lower_95"])


def test_constant_margin_improvement_and_empty_slice():
    data = fixture()
    result = paired_error_intervals(**data)
    assert result["metrics"]["margin_mae_reduction"]["point"] == pytest.approx(.2)
    assert result["metrics"]["margin_mae_reduction"]["lower_95"] == pytest.approx(.2)
    data["weights"] *= 0
    assert paired_error_intervals(**data)["status"] == "inconclusive-empty"


def test_invalid_pair_refuses():
    data = fixture()
    data["new_probability"][0, 0] = np.nan
    with pytest.raises(ValueError, match="invalid probabilities"):
        paired_error_intervals(**data)


def test_float32_checkpoints_use_report_precision_for_log_loss():
    data = fixture()
    for name in ("old_probability", "new_probability"):
        data[name] = data[name].astype(np.float32)
    rows, labels = np.arange(4), data["labels"]
    old = data["old_probability"].astype(np.float64)[rows, labels]
    new = data["new_probability"].astype(np.float64)[rows, labels]
    expected = np.average(np.log(new) - np.log(old), weights=data["weights"])
    actual = paired_error_intervals(**data)["metrics"]["nll_reduction"]["point"]
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
