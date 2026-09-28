import json

import pytest
from evaluate_weighted import evaluate, prepare_pin
from fit_authority_weighted import pin_fits


def test_incomplete_fitting_refuses_before_diagnostic_access(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        pin_fits(tmp_path)
    assert str(error.value.filename).endswith("hog26_weighted_margin_comparison_20260913/complete.json")


def test_partial_review_cannot_pin(tmp_path, monkeypatch):
    import evaluate_weighted

    monkeypatch.setattr(evaluate_weighted, "pin_fits", lambda root: (None, None, None, {}))
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"status": "partial"}))
    with pytest.raises(ValueError, match="complete weighted fitting review required"):
        prepare_pin(tmp_path, path, tmp_path / "pin.json")
    assert not (tmp_path / "pin.json").exists()


def test_changed_source_refuses_before_fitting_or_diagnostic_load(tmp_path, monkeypatch):
    import evaluate_weighted

    def forbidden(root):
        raise AssertionError("changed evaluator proceeded to fitting resources")

    monkeypatch.setattr(evaluate_weighted, "pin_fits", forbidden)
    path = tmp_path / "pin.json"
    path.write_text(json.dumps({"schema": "clasher.hog26.fixed-weighted-margin-diagnostic.v1", "fits": 16,
                                "evaluation_sources": {}, "fitting": False, "acceptance": False,
                                "bootstrap_replicates": 2000, "bootstrap_seed": 1279511}))
    with pytest.raises(ValueError, match="contract changed"):
        evaluate(tmp_path, path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
