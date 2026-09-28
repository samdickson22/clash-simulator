from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.hog26_public_slice_gates import clustered_mean_interval, evaluate_slices


def test_weighted_auc_counts_ties_as_half_and_respects_game_weights():
    from scripts.hog26_public_slice_gates import weighted_binary_auc

    assert weighted_binary_auc([False, True, False, True],
                               [0.1, 0.2, 0.2, 0.8], [1, 2, 3, 1]) == pytest.approx(0.75)
    assert weighted_binary_auc([True, True], [0.2, 0.3], [1, 2]) is None


def test_weighted_outcome_calibration_matches_hand_calculation():
    from scripts.hog26_public_slice_gates import weighted_outcome_metrics

    result = weighted_outcome_metrics([[0.8, 0.1, 0.1], [0.1, 0.1, 0.8]], [-1, 1], [1, 3])
    assert result["nll"] == pytest.approx(-np.log(0.8))
    assert result["ece_10"] == pytest.approx(0.2)
    assert result["classwise_ece_10"] == pytest.approx({"loss": 0.125, "draw": 0.1, "win": 0.175})
    assert result["decisive_auc"] == 1
    assert result["empirical_class_mass"] == {"loss": 0.25, "draw": 0, "win": 0.75}


def fixture():
    protocol = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json"
        ).read_text()
    )
    records = [
        (style, cluster, seat, phase)
        for style in ["a", "b", "c"]
        for cluster in range(8)
        for seat in (0, 1)
        for phase in ("early", "middle", "late")
    ]
    y = np.array([1 if c % 2 else -1 for _, c, _, _ in records])
    p = np.full((len(y), 3), 0.01)
    p[np.arange(len(y)), y + 1] = 0.98
    gates = dict(protocol["gates"], cluster_bootstrap_replicates=100)
    return {
        "probabilities": p,
        "predicted_margin": y * 0.2,
        "target_margin": y * 0.2,
        "current_margin": np.zeros(len(y)),
        "outcomes": y,
        "phases": np.array([v[3] for v in records]),
        "seats": np.array([v[2] for v in records]),
        "styles": np.array([v[0] for v in records]),
        "clusters": np.array([f"{v[0]}-{v[1]}" for v in records]),
        "expected_styles": ["a", "b", "c"],
        "prior": np.array([0.45, 0.1, 0.45]),
        "gates": gates,
        "design": protocol["generalization_evaluation"],
        "seed": 73,
    }


def test_complete_accurate_predictions_pass_every_slice():
    report = evaluate_slices(**fixture())
    assert report["passed"]
    assert report["slices"]["phase/late/seat/1/style/b"]["independent_clusters"] == 8


def test_missing_joint_slice_cannot_disappear_from_evaluation():
    data = fixture()
    missing = (
        (data["phases"] == "late") & (data["styles"] == "b") & (data["seats"] == 1)
    )
    for key in (
        "probabilities",
        "predicted_margin",
        "target_margin",
        "current_margin",
        "outcomes",
        "phases",
        "seats",
        "styles",
        "clusters",
    ):
        data[key] = data[key][~missing]
    report = evaluate_slices(**data)
    assert report["status"] == "inconclusive-reject"
    assert report["slices"]["overall"]["passed"]
    assert report["slices"]["phase/late/seat/1/style/b"]["rows"] == 0


def test_good_pooled_margin_does_not_hide_bad_opponent():
    data = fixture()
    bad = data["styles"] == "b"
    data["predicted_margin"][bad] = -data["target_margin"][bad]
    report = evaluate_slices(**data)
    assert report["slices"]["overall"]["passed"]
    assert not report["slices"]["style/b"]["passed"]
    assert not report["passed"]


def test_baseline_identity_does_not_pass_late_learning_gate():
    data = fixture()
    late = data["phases"] == "late"
    data["predicted_margin"][late] = 0
    report = evaluate_slices(**data)
    assert report["slices"]["overall"]["passed"]
    assert not report["slices"]["phase/late"]["checks"]["learned_phase_margin"]


def test_duplicate_rows_do_not_manufacture_independent_clusters():
    data = fixture()
    data["clusters"][:] = "one-physical-cluster"
    report = evaluate_slices(**data)
    assert report["status"] == "inconclusive-reject"
    assert report["slices"]["overall"]["independent_clusters"] == 1


def test_cluster_resampling_keeps_paired_observations_together():
    interval = clustered_mean_interval(
        np.tile([-1.0, 1.0], 8), np.repeat(np.arange(8), 2), replicates=100, seed=2
    )
    assert interval["lower_95"] == interval["upper_95"] == 0


def test_invalid_probabilities_fail_instead_of_reporting_metrics():
    data = fixture()
    data["probabilities"][0, 0] = np.nan
    with pytest.raises(ValueError, match="invalid public"):
        evaluate_slices(**data)


def test_loaded_adapter_excludes_controlled_draws_from_natural_metrics():
    from types import SimpleNamespace

    import torch

    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus
    from scripts.hog26_public_slice_gates import evaluate_loaded_public_slices

    data = fixture()
    n = len(data["outcomes"])
    public = np.zeros((n, 18), dtype=np.float32)
    public[:, 0] = np.tile([0.15, 0.5, 0.85], n // 3)
    public[:, 1] = data["outcomes"]
    episode = {
        "episode_final_outcomes": data["outcomes"][::3],
        "episode_terminal_tower_margins": data["target_margin"][::3],
        "episode_learner_players": data["seats"][::3],
        "episode_opponent_indices": np.repeat(np.arange(3), 16),
        "episode_opponent_deck_indices": np.tile(np.repeat(np.arange(8), 2), 3),
    }
    corpus = DirectSimpleBehaviorCorpus(
        arrays={"global_features": public},
        episode_offsets=np.arange(0, n + 1, 3),
        episode_stream_rows=np.arange(n // 3),
        episode_ordinals=np.tile(np.repeat(np.arange(8), 2), 3),
        initial_hidden=np.zeros((n // 3, 1)),
        initial_cell=np.zeros((n // 3, 1)),
        episode_arrays=episode,
    )
    metadata = {
        "seed": 1,
        "opponents": ["a", "b", "c"],
        "opponent_decks": [f"generated-{index}" for index in range(8)],
    }
    # A duplicate corpus with absurd margin labels must not improve or spoil natural scores.
    from dataclasses import replace

    control = replace(
        corpus,
        episode_arrays={
            **episode,
            "episode_terminal_tower_margins": np.full(n // 3, 100.0),
            "episode_final_outcomes": np.zeros(n // 3),
        },
    )
    control_meta = {
        **metadata,
        "seed": 2,
        "outcome_source": "controlled-symmetric-draws",
    }

    class Perfect:
        def __call__(self, features):
            labels = features[:, 1].long()
            p = torch.full((len(labels), 3), 0.01)
            p[torch.arange(len(labels)), labels + 1] = 0.98
            return SimpleNamespace(
                outcome_logits=p.log(), terminal_tower_margin=labels * 0.2
            )

    protocol = {
        "gates": data["gates"],
        "generalization_evaluation": data["design"],
        "development_selection": {"opponents": ["a", "b", "c"]},
    }
    result = evaluate_loaded_public_slices(
        Perfect(),
        torch.tensor(np.concatenate([public, public])),
        [(metadata, corpus), (control_meta, control)],
        torch.tensor(data["prior"]),
        protocol,
        stage="development",
        device="cpu",
        seed=1,
    )
    assert result["passed"]
    assert result["groups"]["development"]["slices"]["overall"]["rows"] == n
