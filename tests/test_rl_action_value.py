from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import torch

from clasher.rl.action_value import (
    ActionValueConfig,
    LoadedPublicActionValueEnsemble,
    LoadedPublicActionValueHead,
    PublicActionValueHead,
    load_public_action_value_controller,
    load_public_action_value_ensemble,
    load_public_action_value_head,
    public_action_value_checkpoint,
)
from clasher.rl.counterfactual_corpus import CandidateContext
from scripts.calibrate_public_action_value_ensemble import (
    evaluate_selection,
    select_controller,
)
from scripts.fit_public_action_value import (
    CROWN_PRIORITY,
    DAMAGE_PRIORITY,
    OUTCOME_PRIORITY,
    PreferenceRows,
    _calibrate_score_gain,
    _score_pair_batch,
    base_relative_preferences,
    bootstrap_pair_indices_by_state,
    build_preferences,
    priority_balanced_pairwise_loss,
    root_priority_normalized_weights,
)


def test_action_value_head_is_candidate_permutation_equivariant() -> None:
    torch.manual_seed(2301)
    config = ActionValueConfig(
        state_size=7,
        card_feature_size=5,
        tile_feature_size=3,
        state_hidden_size=8,
        action_hidden_size=8,
        hidden_size=8,
    )
    head = PublicActionValueHead(config).eval()
    state = torch.randn(2, 7)
    cards = torch.randn(2, 4, 5)
    tiles = torch.randn(2, 4, 3)
    kinds = torch.tensor([[0, 1, 2, 0], [2, 0, 1, 0]])
    policy = torch.randn(2, 4).clamp_max(0.0)
    type_policy = torch.randn(2, 4).clamp_max(0.0)
    permutation = torch.tensor([2, 0, 3, 1])

    expected = head(state, cards, tiles, kinds, policy, type_policy)
    actual = head(
        state,
        cards[:, permutation],
        tiles[:, permutation],
        kinds[:, permutation],
        policy[:, permutation],
        type_policy[:, permutation],
    )

    torch.testing.assert_close(actual, expected[:, permutation])


def test_base_relative_action_value_head_anchors_base_and_permutes_alternatives() -> None:
    torch.manual_seed(2302)
    config = ActionValueConfig(
        state_size=7,
        card_feature_size=5,
        tile_feature_size=3,
        state_hidden_size=8,
        action_hidden_size=8,
        hidden_size=8,
        base_relative_interactions=True,
    )
    head = PublicActionValueHead(config).eval()
    state = torch.randn(2, 7)
    cards = torch.randn(2, 4, 5)
    tiles = torch.randn(2, 4, 3)
    kinds = torch.tensor([[1, 0, 2, 0], [1, 0, 0, 2]])
    policy = torch.randn(2, 4).clamp_max(0.0)
    type_policy = torch.randn(2, 4).clamp_max(0.0)
    permutation = torch.tensor([0, 3, 1, 2])

    expected = head(state, cards, tiles, kinds, policy, type_policy)
    actual = head(
        state,
        cards[:, permutation],
        tiles[:, permutation],
        kinds[:, permutation],
        policy[:, permutation],
        type_policy[:, permutation],
    )

    torch.testing.assert_close(expected[:, 0], torch.zeros(2))
    torch.testing.assert_close(actual, expected[:, permutation])


def test_pair_scoring_preserves_true_base_for_relative_interactions() -> None:
    torch.manual_seed(2303)
    head = PublicActionValueHead(
        ActionValueConfig(
            state_size=7,
            card_feature_size=5,
            tile_feature_size=3,
            state_hidden_size=8,
            action_hidden_size=8,
            hidden_size=8,
            base_relative_interactions=True,
        )
    ).eval()
    payload = {
        "features": np.random.default_rng(17).normal(size=(2, 7)).astype(np.float32),
        "candidate_card_features": np.random.default_rng(18)
        .normal(size=(2, 4, 5))
        .astype(np.float32),
        "candidate_tile_features": np.random.default_rng(19)
        .normal(size=(2, 4, 3))
        .astype(np.float32),
        "candidate_kinds": np.asarray([[1, 0, 0, 0], [1, 0, 0, 0]]),
        "candidate_policy_log_probabilities": np.zeros((2, 4), dtype=np.float32),
        "candidate_policy_type_log_probabilities": np.zeros(
            (2, 4), dtype=np.float32
        ),
    }
    preferences = PreferenceRows(
        state_indices=np.asarray([0, 1]),
        positive_indices=np.asarray([2, 0]),
        negative_indices=np.asarray([0, 3]),
        priorities=np.asarray([OUTCOME_PRIORITY, OUTCOME_PRIORITY]),
        weights=np.ones(2, dtype=np.float32),
    )

    positive, negative = _score_pair_batch(
        head,
        payload,
        preferences,
        np.asarray([0, 1]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        full = head(
            torch.as_tensor(payload["features"]),
            torch.as_tensor(payload["candidate_card_features"]),
            torch.as_tensor(payload["candidate_tile_features"]),
            torch.as_tensor(payload["candidate_kinds"]),
            torch.as_tensor(payload["candidate_policy_log_probabilities"]),
            torch.as_tensor(payload["candidate_policy_type_log_probabilities"]),
        )

    torch.testing.assert_close(positive, torch.stack((full[0, 2], full[1, 0])))
    torch.testing.assert_close(negative, torch.stack((full[0, 0], full[1, 3])))


def test_action_value_checkpoint_round_trip(tmp_path: Path) -> None:
    config = ActionValueConfig(7, 5, 3, 8, 8, 8)
    head = PublicActionValueHead(config)
    path = tmp_path / "action_value.pt"
    torch.save(
        public_action_value_checkpoint(
            head=head,
            source_policy="policy.pt",
            corpus_sha256="abc123",
        ),
        path,
    )

    loaded = load_public_action_value_head(path, device=torch.device("cpu"))

    assert loaded.head.config == config
    assert loaded.source_policy == "policy.pt"
    assert loaded.source_policy_sha256 is None
    assert loaded.corpus_sha256 == "abc123"
    assert loaded.minimum_score_gain == 0.0
    for expected, actual in zip(
        head.parameters(),
        loaded.head.parameters(),
        strict=True,
    ):
        torch.testing.assert_close(expected, actual)


@dataclass(frozen=True)
class _FakeActionValueMember:
    scores: np.ndarray
    source_policy: str = "policy.pt"
    source_policy_sha256: str | None = "policy-sha"
    corpus_sha256: str = "corpus"

    def score_candidates(
        self,
        _state_features: torch.Tensor,
        _context: CandidateContext,
    ) -> np.ndarray:
        return self.scores.copy()


def _candidate_context() -> CandidateContext:
    return CandidateContext(
        valid=np.asarray([True, True, True]),
        kinds=np.asarray([1, 0, 0], dtype=np.int8),
        card_ids=np.zeros(3, dtype=np.int64),
        card_features=np.zeros((3, 2), dtype=np.float32),
        tile_features=np.zeros((3, 2), dtype=np.float32),
        policy_logits=np.zeros(3, dtype=np.float32),
        policy_log_probabilities=np.zeros(3, dtype=np.float32),
        policy_type_log_probabilities=np.zeros(3, dtype=np.float32),
    )


def test_action_value_ensemble_uses_paired_dispersion_lower_bound() -> None:
    members = cast(
        tuple[LoadedPublicActionValueHead, ...],
        (
            _FakeActionValueMember(np.asarray([0.0, 2.0, 1.0])),
            _FakeActionValueMember(np.asarray([1.0, 3.0, 3.0])),
            _FakeActionValueMember(np.asarray([-1.0, 2.0, 0.0])),
        ),
    )
    ensemble = LoadedPublicActionValueEnsemble(
        members=members,
        dispersion_scale=1.0,
        minimum_lower_bound_gain=0.0,
        member_gain_scales=(1.0, 1.0, 1.0),
    )

    selected, means, dispersion, lower = ensemble.select_candidate(
        torch.zeros(4),
        _candidate_context(),
    )

    assert selected == 1
    np.testing.assert_allclose(means, np.asarray([0.0, 7.0 / 3.0, 4.0 / 3.0]))
    np.testing.assert_allclose(
        dispersion,
        np.asarray([0.0, np.std([2.0, 2.0, 3.0], ddof=1), np.std([1.0, 2.0, 1.0], ddof=1)]),
    )
    assert lower[1] > lower[2] > 0.0


def test_action_value_ensemble_normalizes_arbitrary_member_score_scales() -> None:
    members = cast(
        tuple[LoadedPublicActionValueHead, ...],
        tuple(
            _FakeActionValueMember(np.asarray([0.0, scale, 0.0]))
            for scale in (1.0, 10.0, 100.0)
        ),
    )
    ensemble = LoadedPublicActionValueEnsemble(
        members=members,
        dispersion_scale=1.0,
        minimum_lower_bound_gain=0.0,
        member_gain_scales=(1.0, 10.0, 100.0),
    )

    selected, means, dispersion, lower = ensemble.select_candidate(
        torch.zeros(4),
        _candidate_context(),
    )

    assert selected == 1
    np.testing.assert_allclose(means, [0.0, 1.0, 0.0])
    np.testing.assert_allclose(dispersion, 0.0)
    np.testing.assert_allclose(lower, [0.0, 1.0, 0.0])


def test_action_value_median_ensemble_rejects_one_member_outlier() -> None:
    members = cast(
        tuple[LoadedPublicActionValueHead, ...],
        (
            _FakeActionValueMember(np.asarray([0.0, 1.0, 0.0])),
            _FakeActionValueMember(np.asarray([0.0, 1.0, 2.0])),
            _FakeActionValueMember(np.asarray([0.0, 100.0, 2.0])),
        ),
    )
    ensemble = LoadedPublicActionValueEnsemble(
        members=members,
        dispersion_scale=0.0,
        minimum_lower_bound_gain=0.0,
        member_gain_scales=(1.0, 1.0, 1.0),
        aggregation="median",
    )

    selected, aggregate, dispersion, lower = ensemble.select_candidate(
        torch.zeros(4),
        _candidate_context(),
    )

    assert selected == 2
    np.testing.assert_allclose(aggregate, [0.0, 1.0, 2.0])
    assert dispersion[1] > dispersion[2]
    np.testing.assert_allclose(lower, aggregate)


def test_action_value_ensemble_manifest_loads_relative_members(
    tmp_path: Path,
) -> None:
    config = ActionValueConfig(7, 5, 3, 8, 8, 8)
    member_names = []
    for index in range(3):
        path = tmp_path / f"member_{index}.pt"
        torch.save(
            public_action_value_checkpoint(
                head=PublicActionValueHead(config),
                source_policy="policy.pt",
                source_policy_sha256="policy-sha",
                corpus_sha256="corpus",
            ),
            path,
        )
        member_names.append(path.name)
    manifest = tmp_path / "ensemble.json"
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "schema": "clasher.public_action_value_ensemble_calibration.v1",
                "passed": True,
                "members": [str((tmp_path / name).resolve()) for name in member_names],
                "member_sha256": [
                    hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
                    for name in member_names
                ],
                "source_policy_sha256": "policy-sha",
                "member_gain_scales": [1.0, 1.0, 1.0],
                "selected": {
                    "dispersion_scale": 1.5,
                    "minimum_lower_bound_gain": 0.25,
                },
                "selected_controller": {
                    "kind": "ensemble",
                    "metrics": {},
                },
            }
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "schema": "clasher.public_action_value_ensemble.v1",
                "members": member_names,
                "dispersion_scale": 1.5,
                "minimum_lower_bound_gain": 0.25,
                "member_gain_scales": [1.0, 1.0, 1.0],
                "calibration_report": calibration.name,
                "calibration_report_sha256": hashlib.sha256(
                    calibration.read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    loaded = load_public_action_value_ensemble(
        manifest,
        device=torch.device("cpu"),
    )

    assert len(loaded.members) == 3
    assert loaded.source_policy == "policy.pt"
    assert loaded.source_policy_sha256 == "policy-sha"
    assert loaded.corpus_sha256 == "corpus"
    assert loaded.dispersion_scale == 1.5
    assert loaded.minimum_lower_bound_gain == 0.25

    controller_path = tmp_path / "controller.json"
    controller_path.write_text(
        json.dumps(
            {
                "schema": "clasher.public_action_value_controller.v1",
                "kind": "ensemble",
                "artifact": manifest.name,
                "artifact_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "source_policy_sha256": "policy-sha",
                "calibration_report": calibration.name,
                "calibration_report_sha256": hashlib.sha256(
                    calibration.read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    controller = load_public_action_value_controller(
        controller_path,
        device=torch.device("cpu"),
    )
    assert isinstance(controller, LoadedPublicActionValueEnsemble)

    calibration.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_public_action_value_ensemble(
            manifest,
            device=torch.device("cpu"),
        )


def test_action_value_controller_loads_calibrated_single_member(
    tmp_path: Path,
) -> None:
    member = tmp_path / "member.pt"
    torch.save(
        public_action_value_checkpoint(
            head=PublicActionValueHead(ActionValueConfig(7, 5, 3, 8, 8, 8)),
            source_policy="policy.pt",
            source_policy_sha256="policy-sha",
            corpus_sha256="corpus",
        ),
        member,
    )
    member_sha = hashlib.sha256(member.read_bytes()).hexdigest()
    calibration = tmp_path / "calibration.json"
    calibration.write_text(
        json.dumps(
            {
                "schema": "clasher.public_action_value_ensemble_calibration.v1",
                "passed": True,
                "source_policy_sha256": "policy-sha",
                "single_members": [{"checkpoint_sha256": member_sha}],
                "selected_controller": {
                    "kind": "single",
                    "member_index": 0,
                    "metrics": {},
                },
            }
        ),
        encoding="utf-8",
    )
    controller_path = tmp_path / "controller.json"
    controller_path.write_text(
        json.dumps(
            {
                "schema": "clasher.public_action_value_controller.v1",
                "kind": "single",
                "artifact": member.name,
                "artifact_sha256": member_sha,
                "source_policy_sha256": "policy-sha",
                "calibration_report": calibration.name,
                "calibration_report_sha256": hashlib.sha256(
                    calibration.read_bytes()
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    loaded = load_public_action_value_controller(
        controller_path,
        device=torch.device("cpu"),
    )

    assert isinstance(loaded, LoadedPublicActionValueHead)
    assert loaded.source_policy_sha256 == "policy-sha"


def test_preferences_use_outcome_then_crowns_then_tower_damage() -> None:
    payload = {
        "candidate_valid": np.asarray([[True, True, True, True]]),
        "candidate_scores": np.asarray([[0.0, 1.0, 1.0, 1.0]], dtype=np.float32),
        "candidate_crown_differences": np.asarray([[3, 0, 1, 1]], dtype=np.int8),
        "candidate_tower_damage_differences": np.asarray(
            [[5000.0, 0.0, 10.0, 20.0]],
            dtype=np.float32,
        ),
    }

    preferences = build_preferences(payload)

    assert len(preferences.state_indices) == 6
    assert np.count_nonzero(preferences.priorities == OUTCOME_PRIORITY) == 3
    assert np.count_nonzero(preferences.priorities == CROWN_PRIORITY) == 2
    assert np.count_nonzero(preferences.priorities == DAMAGE_PRIORITY) == 1
    final_pair = np.flatnonzero(preferences.priorities == DAMAGE_PRIORITY)[0]
    assert preferences.positive_indices[final_pair] == 3
    assert preferences.negative_indices[final_pair] == 2


def test_base_relative_preferences_remove_candidate_only_pairs() -> None:
    payload = {
        "candidate_valid": np.asarray([[True, True, True, True]]),
        "candidate_scores": np.asarray([[0.0, 1.0, 1.0, 1.0]], dtype=np.float32),
        "candidate_crown_differences": np.asarray([[3, 0, 1, 1]], dtype=np.int8),
        "candidate_tower_damage_differences": np.asarray(
            [[5000.0, 0.0, 10.0, 20.0]],
            dtype=np.float32,
        ),
    }

    preferences = base_relative_preferences(build_preferences(payload))

    assert len(preferences.state_indices) == 3
    assert bool(
        np.all(
            (preferences.positive_indices == 0)
            | (preferences.negative_indices == 0)
        )
    )
    assert np.count_nonzero(preferences.priorities == OUTCOME_PRIORITY) == 3


def test_action_value_bootstrap_keeps_all_pairs_from_sampled_roots() -> None:
    payload = {
        "candidate_valid": np.asarray(
            [[True, True, True], [True, True, False]], dtype=np.bool_
        ),
        "candidate_scores": np.asarray(
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.zeros((2, 3), dtype=np.int8),
        "candidate_tower_damage_differences": np.asarray(
            [[0.0, 0.0, -1.0], [0.0, 0.0, 0.0]], dtype=np.float32
        ),
    }
    preferences = build_preferences(payload)
    original = np.arange(len(preferences.state_indices), dtype=np.int64)

    sampled_pairs, sampled_states = bootstrap_pair_indices_by_state(
        preferences,
        original,
        np.random.default_rng(17),
    )

    for state in np.unique(sampled_states):
        original_count = np.count_nonzero(preferences.state_indices == state)
        draw_count = np.count_nonzero(sampled_states == state)
        sampled_count = np.count_nonzero(
            preferences.state_indices[sampled_pairs] == state
        )
        assert sampled_count == original_count * draw_count


def test_action_value_priority_loss_normalizes_each_terminal_level() -> None:
    margins = torch.zeros(4, requires_grad=True)
    loss = priority_balanced_pairwise_loss(
        margins,
        torch.tensor([4.0, 4.0, 1.0, 1.0]),
        torch.tensor(
            [OUTCOME_PRIORITY, OUTCOME_PRIORITY, DAMAGE_PRIORITY, DAMAGE_PRIORITY]
        ),
    )

    assert loss.item() == pytest.approx(np.log(2.0))
    loss.backward()
    assert margins.grad is not None
    assert bool((margins.grad != 0.0).all())


def test_action_value_pair_weights_have_unit_mass_per_root_and_priority() -> None:
    payload = {
        "candidate_valid": np.asarray(
            [[True, True, True], [True, True, True]], dtype=np.bool_
        ),
        "candidate_scores": np.asarray(
            [[0.0, 1.0, 1.0], [1.0, 0.0, 1.0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.asarray(
            [[0, 0, 1], [0, 0, 0]], dtype=np.int8
        ),
        "candidate_tower_damage_differences": np.asarray(
            [[0.0, 0.0, 1.0], [0.0, 0.0, -2.0]], dtype=np.float32
        ),
    }
    preferences = build_preferences(payload)
    weights = root_priority_normalized_weights(preferences)

    for state in np.unique(preferences.state_indices):
        for priority in (OUTCOME_PRIORITY, CROWN_PRIORITY, DAMAGE_PRIORITY):
            selected = (preferences.state_indices == state) & (
                preferences.priorities == priority
            )
            if np.any(selected):
                assert weights[selected].sum() == pytest.approx(1.0)


def test_calibration_selects_zero_regression_score_threshold() -> None:
    scores = np.asarray([[0.0, 0.5], [0.0, 0.2]], dtype=np.float32)
    payload = {
        "candidate_valid": np.asarray([[True, True], [True, True]]),
        "candidate_scores": np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        "candidate_crown_differences": np.zeros((2, 2), dtype=np.int8),
        "candidate_tower_damage_differences": np.zeros((2, 2), dtype=np.float32),
    }

    threshold, sweep = _calibrate_score_gain(
        scores=scores,
        payload=payload,
        state_indices=np.asarray([0, 1]),
    )

    assert threshold == np.float32(0.2)
    selected = next(row for row in sweep if row["threshold"] == threshold)
    assert selected["improvements"]["outcome"] == 1
    assert sum(selected["regressions"].values()) == 0


def test_ensemble_selection_reports_terminal_regret_and_archetype_safety() -> None:
    member_scores = np.asarray(
        [
            [[0.0, 2.0], [2.0, 0.0]],
            [[0.0, 3.0], [3.0, 0.0]],
            [[0.0, 2.5], [2.5, 0.0]],
        ],
        dtype=np.float32,
    )
    payload = {
        "candidate_valid": np.ones((2, 2), dtype=np.bool_),
        "candidate_scores": np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        "candidate_crown_differences": np.zeros((2, 2), dtype=np.int8),
        "candidate_tower_damage_differences": np.zeros((2, 2), dtype=np.float32),
    }

    result = evaluate_selection(
        member_scores=member_scores,
        payload=payload,
        archetypes=np.asarray(["cycle", "control"]),
        dispersion_scale=1.0,
        minimum_lower_bound_gain=0.0,
    )

    assert result["pairwise_accuracy"] == 1.0
    assert result["outcome_pairwise_accuracy"] == 1.0
    assert result["overrides"] == 1
    assert result["improvements"] == 1
    assert result["regressions"] == 0
    assert result["ordinal_regret_reduction"] == 1.0
    assert result["minimum_archetype_mean_rank_delta"] == 0.0
    np.testing.assert_array_equal(result["selected_indices"], [1, 0])


def test_controller_selection_keeps_better_single_member() -> None:
    common = {
        "passes": True,
        "outcome_pairwise_accuracy": 0.8,
        "pairwise_accuracy": 0.8,
        "positive_override_precision_wilson_lower": 0.8,
    }
    single = {**common, "ordinal_regret_reduction": 0.5}
    ensemble = {**common, "ordinal_regret_reduction": 0.4}

    selected = select_controller([single], ensemble)

    assert selected is not None
    assert selected["kind"] == "single"
    assert selected["member_index"] == 0
