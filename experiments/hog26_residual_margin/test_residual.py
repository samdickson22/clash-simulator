import numpy as np
import pytest
import torch
from residual_features import make_layout, numeric_features
from residual_training import (
    NumericResidualMargin,
    fit_residual,
    make_optimizer,
    predict_margin,
    training_step,
)
from scalar_features import build_game_features

torch.set_num_threads(1)


def public_fixture():
    rng = np.random.default_rng(31)
    time, entities = 24, 3
    features = rng.random((time, entities, 32), dtype=np.float32)
    features[..., 2:9] = 0
    features[..., 2] = 1
    features[..., 4] = 1
    hand = rng.choice([0, *range(2, 10)], size=(time, 4))
    hand[0, 0] = 0
    hand[1, 0] = 999
    hand_confidence = np.ones((time, 4), dtype=np.float32)
    hand_confidence[1, 0] = 0
    return {
        "entity_ids": np.full((time, entities), 2, dtype=np.int64),
        "entity_features": features,
        "entity_mask": np.ones((time, entities), dtype=bool),
        "entity_id_confidence": np.ones((time, entities), dtype=np.float32),
        "entity_feature_confidence": np.ones_like(features),
        "hand_ids": hand,
        "hand_id_confidence": hand_confidence,
        "global_features": rng.random((time, 18), dtype=np.float32),
        "global_feature_confidence": np.ones((time, 18), dtype=np.float32),
    }


def test_compaction_preserves_every_nonzero_original_feature():
    public = public_fixture()
    layout = make_layout(12, [0, *range(2, 10)])
    full = build_game_features(**public, vocabulary_size=12)
    compact = numeric_features(public, layout)
    restored = compact * np.asarray(layout.scales, dtype=np.float32)
    assert np.array_equal(restored, full[:, layout.columns])
    omitted = sorted(set(range(full.shape[1])) - set(layout.columns))
    assert not full[:, omitted].any()
    assert compact.shape == (24, 425)


def test_undeclared_visible_hand_card_refuses():
    public = public_fixture()
    public["hand_ids"][0, 0] = 10
    with pytest.raises(ValueError, match="outside the frozen learner deck"):
        numeric_features(public, make_layout(12, [0, *range(2, 10)]))


def test_features_are_causal_and_independent_of_entity_identity():
    public = public_fixture()
    layout = make_layout(12, [0, *range(2, 10)])
    expected = numeric_features(public, layout)
    prefix = {key: value[:10].copy() for key, value in public.items()}
    assert np.array_equal(numeric_features(prefix, layout), expected[:10])
    public["entity_ids"][:] = 9
    assert np.array_equal(numeric_features(public, layout), expected)


def test_initial_model_is_exactly_the_public_current_margin_baseline():
    public = public_fixture()
    x = numeric_features(public, make_layout(12, [0, *range(2, 10)]))
    g = public["global_features"]
    baseline = (g[:, 8:11].sum(1) - g[:, 11:14].sum(1)) / 3
    assert np.array_equal(predict_margin(NumericResidualMargin(), x, baseline), baseline)


def test_excluded_features_and_targets_do_not_enter_optimizer_updates():
    rng = np.random.default_rng(41)
    x = rng.normal(size=(16, 425)).astype(np.float32)
    y = rng.uniform(-.2, .2, size=16)
    rows = np.arange(8)
    weights = np.r_[np.full(8, 1 / 8), np.zeros(8)]
    expected = fit_residual(x, rows, y, weights, seed=19, epochs=2, batch_rows=4)
    x[8:] = np.nan
    y[8:] = np.nan
    actual = fit_residual(x, rows, y, weights, seed=19, epochs=2, batch_rows=4)
    for name, value in expected.state_dict().items():
        assert torch.equal(actual.state_dict()[name], value)


def test_synthetic_residual_step_has_finite_gradients_and_learns():
    torch.manual_seed(37)
    model = NumericResidualMargin()
    optimizer = make_optimizer(model)
    x = torch.ones(16, 425)
    target = torch.full((16,), .2)
    weights = torch.full((16,), 1 / 16)
    before = float((model(x) - target).abs().mean().detach())
    for _ in range(3):
        training_step(model, optimizer, x, target, weights, 16)
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert float((model(x) - target).abs().mean().detach()) < before


@pytest.mark.parametrize("field,value", [
    ("finite_gradients", False), ("optimizer_step", False),
    ("initial_baseline_max_abs_difference", .01), ("peak_rss_bytes", 20 * 1024**3),
    ("feature_shape", [618148, 425]), ("implementation", {}),
])
def test_memory_readiness_rejects_missing_evidence(tmp_path, field, value):
    import json
    from types import SimpleNamespace

    from residual_contract import runtime_signature, sha, source_inventory
    from residual_experiment import validate_memory

    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"synthetic": True}))
    plan = SimpleNamespace(data=SimpleNamespace(expected_audit={"games": 1536}))
    report = {"status": "passed-synthetic-memory-audit", "plan_sha256": sha(path),
              "implementation": source_inventory(), "runtime": runtime_signature(),
              "data_audit": plan.data.expected_audit, "feature_shape": [618149, 425],
              "feature_matrix_bytes": 618149 * 425 * 4, "peak_rss_bytes": 1024**3,
              "parameters": 14721, "synthetic_batch_rows": 512, "finite_gradients": True,
              "optimizer_step": True, "initial_baseline_max_abs_difference": 0.0,
              "outcome_fitting": False, "saved_model": False, "feature_matrix_sha256": "a" * 64}
    validate_memory(report, plan, path)
    report[field] = value
    with pytest.raises(ValueError, match="does not establish"):
        validate_memory(report, plan, path)


def test_unready_fit_refuses_before_corpus_access(tmp_path, monkeypatch):
    import residual_experiment

    path = tmp_path / "readiness.json"
    path.write_text('{"status":"not-ready"}')

    def forbidden(*args, **kwargs):
        raise AssertionError("unready fit accessed corpus")

    monkeypatch.setattr(residual_experiment, "prepare_data", forbidden)
    output = tmp_path / "fit"
    with pytest.raises(ValueError, match="readiness required"):
        residual_experiment.run_fit(None, tmp_path / "plan.json", path, output)
    assert not output.exists()


def test_readiness_requires_the_exact_underlying_memory_report(tmp_path):
    import json

    from residual_contract import sha
    from residual_experiment import validate_readiness

    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    memory = tmp_path / "memory.json"
    memory.write_text('{"status":"passed-synthetic-memory-audit"}')
    readiness = tmp_path / "readiness.json"
    readiness.write_text(json.dumps({"status": "passed", "plan_sha256": sha(plan),
                                     "memory_report_path": str(memory),
                                     "memory_report_sha256": sha(memory)}))
    memory.write_text('{"status":"changed"}')
    with pytest.raises(ValueError, match="underlying residual memory report changed"):
        validate_readiness(readiness, None, plan)
