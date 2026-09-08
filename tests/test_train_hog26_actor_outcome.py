from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.outcome_model import ActorOutcomeHead
from scripts.train_hog26_actor_outcome import (
    _binary_auc,
    _ece,
    _natural_metadata_values,
    _outcome_source,
    all_phase_auc_confidence_passed,
    all_phase_decisive_auc_passed,
    all_phase_margin_nonregression_passed,
    bootstrap_binary_auc,
    episode_balanced_row_weights,
    episode_class_balanced_row_weights,
    fit_probability_shrinkage,
    margin_epoch_selection_key,
    metrics,
    outcome_epoch_selection_key,
    phase_balanced_matchup_clusters,
    phase_balanced_row_indices,
)


def test_auc_and_ece_are_exact_on_separated_predictions() -> None:
    labels = torch.tensor([False, False, True, True])
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    assert _binary_auc(labels, scores) == 1.0
    probabilities = torch.tensor([[0.8, 0.2], [0.1, 0.9]])
    assert _ece(probabilities, torch.tensor([0, 1])) == pytest.approx(0.15)


def test_metrics_report_undiscounted_classes_and_margin() -> None:
    head = ActorOutcomeHead(18, hidden_size=2)
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
    result = metrics(
        head,
        torch.zeros(3, 18),
        torch.tensor([-1, 0, 1]),
        torch.tensor([-0.5, 0.0, 0.5]),
        device=torch.device("cpu"),
    )
    assert result["class_counts"] == {"loss": 1, "draw": 1, "win": 1}
    assert result["nll"] == pytest.approx((2.0 * np.log(4.0) + np.log(2.0)) / 3.0)
    assert result["brier"] == pytest.approx(17.0 / 24.0)
    assert result["tower_margin_mae"] == pytest.approx(1.0 / 3.0)
    assert result["decisive_win_loss_auc"] == pytest.approx(0.5)


def test_outcome_source_keeps_controlled_draws_separate() -> None:
    assert _outcome_source({"outcome_source": "natural-strategy-games"}) == (
        "natural-strategy-games"
    )
    assert _outcome_source({"symmetric_draw_source": True}) == (
        "controlled-symmetric-draws"
    )


def test_natural_metadata_values_excludes_controlled_draws() -> None:
    loaded = [
        (
            {"outcome_source": "natural-strategy-games", "opponents": ["balanced"]},
            object(),
        ),
        (
            {
                "outcome_source": "controlled-symmetric-draws",
                "opponents": ["symmetric-selfplay"],
            },
            object(),
        ),
    ]
    assert _natural_metadata_values(loaded, "opponents") == {"balanced"}  # type: ignore[arg-type]


def test_episode_class_balanced_weights_equalize_episodes_and_class_mass() -> None:
    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus

    corpus = DirectSimpleBehaviorCorpus(
        arrays={"final_outcomes": np.asarray([-1, -1, 1, 1, 1, 1], dtype=np.int8)},
        episode_offsets=np.asarray([0, 2, 6], dtype=np.int64),
        episode_stream_rows=np.asarray([0, 1], dtype=np.int64),
        episode_ordinals=np.asarray([0, 0], dtype=np.int64),
        initial_hidden=np.zeros((2, 1), dtype=np.float32),
        initial_cell=np.zeros((2, 1), dtype=np.float32),
    )
    weights = episode_class_balanced_row_weights(
        [({}, corpus)], target_class_mass=(0.5, 0.0, 0.5)
    ).numpy()
    assert weights[:2].sum() == pytest.approx(weights[2:].sum())
    assert weights[0] == pytest.approx(weights[1])
    assert weights[2] == pytest.approx(weights[5])
    regression = episode_balanced_row_weights([({}, corpus)]).numpy()
    assert regression[:2].sum() == pytest.approx(regression[2:].sum())
    assert regression.mean() == pytest.approx(1.0)


def test_phase_balanced_training_weights_equalize_reached_phases() -> None:
    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus

    progress = np.asarray(
        [0.01, 0.10, 0.20, 0.40, 0.60, 0.70, 0.80, 0.90], dtype=np.float32
    )
    globals_ = np.zeros((progress.size, 18), dtype=np.float32)
    globals_[:, 0] = progress
    corpus = DirectSimpleBehaviorCorpus(
        arrays={
            "final_outcomes": np.ones(progress.size, dtype=np.int8),
            "global_features": globals_,
        },
        episode_offsets=np.asarray([0, progress.size], dtype=np.int64),
        episode_stream_rows=np.asarray([0], dtype=np.int64),
        episode_ordinals=np.asarray([0], dtype=np.int64),
        initial_hidden=np.zeros((1, 1), dtype=np.float32),
        initial_cell=np.zeros((1, 1), dtype=np.float32),
    )
    weights = episode_balanced_row_weights([({}, corpus)], phase_balanced=True).numpy()
    assert weights[:3].sum() == pytest.approx(weights[3:5].sum())
    assert weights[3:5].sum() == pytest.approx(weights[5:].sum())
    assert weights.mean() == pytest.approx(1.0)


def test_epoch_selection_prefers_ranking_after_calibration_gate() -> None:
    def row(auc: float, nll: float, ece: float, draw_auc: float) -> dict[str, object]:
        return {
            "decisive_win_loss_auc": auc,
            "nll": nll,
            "ece_10": ece,
            "auc_one_vs_rest": {"draw": draw_auc},
        }

    def key(
        values: dict[str, object],
        *,
        acceptance_passed: bool,
        phases: tuple[float, float, float] = (0.7, 0.7, 0.7),
    ) -> tuple[int, float, float, float]:
        return outcome_epoch_selection_key(
            values,
            acceptance_passed=acceptance_passed,
            by_phase={
                phase: {"decisive_win_loss_auc": auc}
                for phase, auc in zip(("early", "middle", "late"), phases, strict=True)
            },
        )

    assert key(row(0.70, 0.95, 0.15, 0.85), acceptance_passed=True) > key(
        row(0.61, 0.78, 0.12, 0.95), acceptance_passed=True
    )
    assert key(row(0.61, 0.78, 0.12, 0.95), acceptance_passed=True) > key(
        row(0.90, 0.70, 0.30, 0.99), acceptance_passed=False
    )
    assert key(
        row(0.72, 0.8, 0.1, 0.9),
        acceptance_passed=True,
        phases=(0.68, 0.7, 0.95),
    ) > key(
        row(0.80, 0.7, 0.1, 0.9),
        acceptance_passed=True,
        phases=(0.56, 0.95, 1.0),
    )


def test_margin_epoch_selection_rejects_better_aggregate_with_phase_failure() -> None:
    passing = {
        "tower_margin_mae_improvement": 0.01,
        "tower_margin_mae": 0.18,
    }
    invalid = {
        "tower_margin_mae_improvement": 0.03,
        "tower_margin_mae": 0.16,
    }
    assert margin_epoch_selection_key(
        passing, acceptance_passed=True
    ) > margin_epoch_selection_key(invalid, acceptance_passed=False)


def test_probability_shrinkage_fit_repairs_overconfident_constant_scores() -> None:
    head = ActorOutcomeHead(18, hidden_size=2)
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
        head.decisive_win.bias.fill_(4.0)
    head.set_prior_calibration(
        torch.tensor([0.45, 0.1, 0.45]),
        torch.tensor([0.45, 0.1, 0.45]),
    )
    shrinkage = fit_probability_shrinkage(
        head,
        torch.zeros(4, 18),
        torch.tensor([-1, -1, 1, 1]),
        device=torch.device("cpu"),
    )
    assert shrinkage == pytest.approx(0.0)


def test_all_phase_auc_rejects_missing_or_below_chance_phase() -> None:
    passing = {
        phase: {"decisive_win_loss_auc": value}
        for phase, value in (("early", 0.56), ("middle", 0.7), ("late", 0.9))
    }
    assert all_phase_decisive_auc_passed(passing, 0.55)
    passing["early"]["decisive_win_loss_auc"] = 0.54
    assert not all_phase_decisive_auc_passed(passing, 0.55)
    passing.pop("late")
    assert not all_phase_decisive_auc_passed(passing, 0.55)


def test_phase_margin_gate_rejects_material_regression() -> None:
    phases = {
        phase: {"tower_margin_mae_improvement": value}
        for phase, value in (("early", 0.02), ("middle", 0.0), ("late", -0.009))
    }
    assert all_phase_margin_nonregression_passed(phases, 0.01)
    phases["late"]["tower_margin_mae_improvement"] = -0.011
    assert not all_phase_margin_nonregression_passed(phases, 0.01)


def test_phase_balanced_rows_select_one_nearest_midpoint_per_episode_phase() -> None:
    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus

    progress = np.asarray([0.01, 0.16, 0.31, 0.40, 0.51, 0.80, 0.90], dtype=np.float32)
    globals_ = np.zeros((progress.size, 18), dtype=np.float32)
    globals_[:, 0] = progress
    corpus = DirectSimpleBehaviorCorpus(
        arrays={"global_features": globals_},
        episode_offsets=np.asarray([0, 5, 7], dtype=np.int64),
        episode_stream_rows=np.asarray([0, 1], dtype=np.int64),
        episode_ordinals=np.asarray([0, 0], dtype=np.int64),
        initial_hidden=np.zeros((2, 1), dtype=np.float32),
        initial_cell=np.zeros((2, 1), dtype=np.float32),
    )
    assert phase_balanced_row_indices([({}, corpus)]).tolist() == [1, 4, 5]


def test_bootstrap_auc_interval_is_deterministic_and_rejects_one_class() -> None:
    labels = np.asarray([False, False, False, True, True, True])
    scores = np.asarray([0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
    first = bootstrap_binary_auc(labels, scores, seed=91, replicates=500)
    second = bootstrap_binary_auc(labels, scores, seed=91, replicates=500)
    assert first == second
    assert first is not None
    assert first["point"] == 1.0
    assert first["lower_95"] == 1.0
    assert (
        bootstrap_binary_auc(
            np.ones(4, dtype=np.bool_), np.arange(4), seed=1, replicates=100
        )
        is None
    )


def test_cluster_bootstrap_resamples_matchups_instead_of_mirrored_seats() -> None:
    labels = np.asarray([False, False, False, False, True, True, True, True])
    scores = np.asarray([0.1, 0.2, 0.15, 0.25, 0.8, 0.9, 0.85, 0.95])
    result = bootstrap_binary_auc(
        labels,
        scores,
        seed=17,
        replicates=500,
        clusters=np.asarray(
            ["loss-a", "loss-a", "loss-b", "loss-b", "win-a", "win-a", "win-b", "win-b"]
        ),
    )
    assert result is not None
    assert result["point"] == 1.0
    assert result["independent_clusters"] == 4


def test_phase_confidence_requires_enough_independent_clusters() -> None:
    intervals = {
        phase: {
            "lower_95": 0.6,
            "independent_clusters": 8,
        }
        for phase in ("early", "middle", "late")
    }
    assert all_phase_auc_confidence_passed(
        intervals, minimum_lower_95=0.5, minimum_clusters=8
    )
    intervals["late"]["independent_clusters"] = 7
    assert not all_phase_auc_confidence_passed(
        intervals, minimum_lower_95=0.5, minimum_clusters=8
    )


def test_phase_clusters_pair_mirrored_seats_within_matchup() -> None:
    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus

    globals_ = np.zeros((6, 18), dtype=np.float32)
    globals_[:, 0] = np.asarray([0.1, 0.5, 0.8, 0.1, 0.5, 0.8])
    corpus = DirectSimpleBehaviorCorpus(
        arrays={"global_features": globals_},
        episode_offsets=np.asarray([0, 3, 6], dtype=np.int64),
        episode_stream_rows=np.asarray([0, 1], dtype=np.int64),
        episode_ordinals=np.asarray([0, 0], dtype=np.int64),
        initial_hidden=np.zeros((2, 1), dtype=np.float32),
        initial_cell=np.zeros((2, 1), dtype=np.float32),
        episode_arrays={
            "episode_opponent_indices": np.asarray([0, 0]),
            "episode_opponent_deck_indices": np.asarray([0, 0]),
        },
    )
    metadata = {
        "seed": 9,
        "outcome_source": "natural-strategy-games",
        "opponents": ["balanced"],
        "opponent_decks": ["Giant"],
    }
    clusters = phase_balanced_matchup_clusters([(metadata, corpus)])
    assert clusters.shape == (6,)
    assert len(set(clusters.tolist())) == 1


def test_calibration_labels_cannot_change_epoch_selection(
    tmp_path, monkeypatch
) -> None:
    """Exercise the real optimizer/selector twice with opposite calibration labels."""
    import hashlib
    import json
    import sys

    from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus
    from scripts import train_hog26_actor_outcome as trainer

    def digest(path):
        return hashlib.sha256(str(path).encode()).hexdigest()

    def fixture(seed, episode_labels):
        labels = np.asarray(episode_labels, dtype=np.int8)
        n = len(labels)
        public = np.zeros((n * 3, 18), dtype=np.float32)
        public[:, 0] = np.tile([0.15, 0.5, 0.85], n)
        public[:, 8:14] = 0.8
        public[:, 1] = np.repeat(np.arange(n) / n, 3)
        outcomes = np.repeat(labels, 3)
        margins = outcomes.astype(np.float32) * 0.2
        metadata = {
            "schema": trainer.CORPUS_SCHEMA,
            "label_authority": "undiscounted-terminal-winner-and-post-action-public-tower-fractions-v1",
            "actor_input_excludes_outcome_labels": True,
            "checkpoint_sha256": digest(tmp_path / "base.pt"),
            "seed": seed,
            "opponents": ["balanced"],
            "opponent_decks": [f"deck-{seed}"],
        }
        corpus = DirectSimpleBehaviorCorpus(
            arrays={
                "global_features": public,
                "next_global_features": public.copy(),
                "terminal_winners": np.where(outcomes < 0, 1, 0),
                "final_outcomes": outcomes,
                "terminal_tower_margins": margins,
            },
            episode_offsets=np.arange(0, 3 * n + 1, 3),
            episode_stream_rows=np.arange(n),
            episode_ordinals=np.arange(n),
            initial_hidden=np.zeros((n, 1), dtype=np.float32),
            initial_cell=np.zeros((n, 1), dtype=np.float32),
            episode_arrays={
                "episode_opponent_indices": np.zeros(n, dtype=np.int64),
                "episode_opponent_deck_indices": np.zeros(n, dtype=np.int64),
                "episode_learner_players": np.zeros(n, dtype=np.int64),
                "episode_final_outcomes": labels,
                "episode_terminal_tower_margins": labels.astype(np.float32) * 0.2,
            },
        )
        return metadata, corpus

    corpora = {
        "train.npz": fixture(1, [-1, 0, 1, -1, 0, 1]),
        "validation.npz": fixture(2, [-1, 0, 1, 1, 0, -1]),
    }
    monkeypatch.setattr(trainer, "file_sha256", digest)
    monkeypatch.setattr(trainer, "load_model", lambda *args: ({}, torch.nn.Identity()))
    monkeypatch.setattr(
        trainer, "load_direct_simple_behavior_corpus", lambda path: corpora[path.name]
    )
    calls = []
    real_fit = trainer.fit_probability_shrinkage

    def fit(head, features, labels, **kwargs):
        calls.append(labels.clone())
        return real_fit(head, features, labels, **kwargs)

    monkeypatch.setattr(trainer, "fit_probability_shrinkage", fit)
    from pathlib import Path

    protocol = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json"
        ).read_text()
    )
    protocol["development_selection"]["opponents"] = ["balanced"]
    protocol["gates"]["cluster_bootstrap_replicates"] = 100
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    reports = []
    for index, label in enumerate((-1, 1)):
        corpora["calibration.npz"] = fixture(3, [label] * 6)
        report = tmp_path / f"report-{index}.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "trainer",
                "--base-checkpoint",
                str(tmp_path / "base.pt"),
                "--train-corpus",
                "train.npz",
                "--validation-corpus",
                "validation.npz",
                "--calibration-corpus",
                "calibration.npz",
                "--generalization-protocol",
                str(protocol_path),
                "--report",
                str(report),
                "--output-checkpoint",
                str(tmp_path / f"unused-{index}.pt"),
                "--seed",
                "123",
                "--device",
                "cpu",
                "--epochs",
                "3",
                "--feature-set",
                "public-globals",
                "--hidden-size",
                "4",
                "--batch-size",
                "9",
                "--phase-auc-bootstrap-replicates",
                "100",
            ],
        )
        with pytest.raises(SystemExit, match="failed development gates"):
            trainer.main()
        reports.append(json.loads(report.read_text()))
        assert reports[-1]["validation_public_slices"]["passed"] is False
        assert reports[-1]["generalization_protocol_sha256"] == digest(protocol_path)
    assert len(calls) == 2  # exactly once per run, after selection
    assert torch.all(calls[0] == -1) and torch.all(calls[1] == 1)
    for key in (
        "best_outcome_epoch",
        "best_margin_epoch",
        "history",
        "pre_calibration_selected_state_sha256",
    ):
        assert reports[0][key] == reports[1][key]
    assert all(row["probability_shrinkage"] == 1.0 for row in reports[0]["history"])
