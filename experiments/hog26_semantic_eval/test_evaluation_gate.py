import json

import pytest
from evaluate_semantic import evaluate, prepare_pin
from semantic_authority import pin_completed_fits


def test_incomplete_fit_refuses_before_plan_or_diagnostic_access(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        pin_completed_fits(tmp_path)
    assert str(error.value.filename).endswith("hog26_semantic_margin_comparison_20260912/complete.json")


def test_partial_fitting_review_cannot_pin_diagnostic(tmp_path, monkeypatch):
    import evaluate_semantic

    monkeypatch.setattr(evaluate_semantic, "pin_completed_fits", lambda root: (None, None, {}))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"status": "partial"}))
    pin = tmp_path / "pin.json"
    with pytest.raises(ValueError, match="complete residual fitting review required"):
        prepare_pin(tmp_path, review, pin)
    assert not pin.exists()


def test_changed_source_refuses_before_fitting_or_diagnostic_access(tmp_path, monkeypatch):
    import evaluate_semantic

    def forbidden(root):
        raise AssertionError("invalid pin proceeded to fitting resources")

    monkeypatch.setattr(evaluate_semantic, "pin_completed_fits", forbidden)
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps({"schema": "clasher.hog26.fixed-semantic-diagnostic.v1",
                               "fits": 8, "evaluation_sources": {}, "fitting": False,
                               "acceptance": False, "bootstrap_replicates": 2000,
                               "bootstrap_seed": 1279511}))
    output = tmp_path / "evaluation"
    with pytest.raises(ValueError, match="contract changed"):
        evaluate(tmp_path, pin, output)
    assert not output.exists()
