import json
import time
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts.screen_hog26_training_family_outcomes import (
    fit_outcome_weights,
    run_outcome_screen,
)


def test_withheld_labels_do_not_affect_class_weights_or_fitting_prior():
    labels = torch.tensor([-1, 0, 1, -1])
    args = (torch.ones(4), labels, labels, np.arange(3), np.arange(3), [0.45, 0.1, 0.45])
    weights, prior = fit_outcome_weights(*args)
    labels[3] = 1
    changed_weights, changed_prior = fit_outcome_weights(*args)
    assert torch.equal(weights, changed_weights)
    assert torch.equal(prior, changed_prior)
    assert weights[3] == 0
    torch.testing.assert_close(weights[:3] / weights.sum(), torch.tensor([0.45, 0.1, 0.45]))
    torch.testing.assert_close(prior, torch.full((3,), 1 / 3))


def test_withheld_draw_cannot_supply_missing_fit_class():
    labels = torch.tensor([-1, 1, 0])
    with pytest.raises(ValueError, match="lacks a required outcome class"):
        fit_outcome_weights(torch.ones(3), labels, labels, np.arange(2), np.arange(2), [0.45, 0.1, 0.45])


def test_small_real_fit_reports_disjoint_family_predictions(tmp_path):
    labels = np.array([-1, 1, -1, 1, 0])
    public = np.zeros((15, 18), dtype=np.float32)
    public[:, 0] = np.tile([0.15, 0.5, 0.85], 5)
    corpus = SimpleNamespace(
        arrays={"global_features": public, "final_outcomes": np.repeat(labels, 3)},
        episode_arrays={"episode_final_outcomes": labels},
        episode_offsets=np.arange(0, 16, 3), row_count=15, episode_count=5,
    )
    plan = {
        "actor_feature_set": "public-globals", "epochs": 1, "batch_size": 8,
        "seeds": [71], "held_out_training_families": [["a"], ["b"]],
        "target_class_mass": [0.45, 0.1, 0.45], "hidden_size": 2,
        "learning_rate": 0.001, "weight_decay": 0.0001,
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    output = tmp_path / "report.json"
    run_outcome_screen(
        plan=plan, features=torch.tensor(public), loaded=[({}, corpus)],
        episode_families=np.array(["a", "a", "b", "b", "<auxiliary>"]),
        episode_offsets=corpus.episode_offsets, source_records=[],
        plan_path=plan_path, output=output, started=time.monotonic(),
    )
    result = json.loads(output.read_text())["results"][0]
    assert result["representative_overall"]["rows"] == 12
    assert all(f["fitting_games"] == 3 for f in result["folds"])
    assert all(f["out_of_fold_representatives"]["rows"] == 6 for f in result["folds"])
    assert all(p["rows"] == 4 for p in result["full_phase"].values())
