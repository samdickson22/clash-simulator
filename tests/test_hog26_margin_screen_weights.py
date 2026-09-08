from __future__ import annotations

import numpy as np
import pytest
import torch

from scripts.screen_hog26_training_family_margin import fitting_phase_weights


def test_aggregate_phase_balance_uses_only_fitting_rows():
    phases = np.array([0, 0, 0, 1, 1, 2, 2, 0])
    weights = torch.tensor([1.0, 2.0, 3.0, 1.0, 2.0, 1.0, 1000.0, 1000.0])
    rows = np.arange(6)
    result = fitting_phase_weights(weights, phases, rows, aggregate_balance=True)
    assert result[6:].sum() == 0
    assert result[rows].mean() == pytest.approx(1.0)
    assert [result[phases == p].sum().item() for p in range(3)] == pytest.approx(
        [2.0, 2.0, 2.0]
    )
    changed = weights.clone()
    changed[6:] = 1e8
    torch.testing.assert_close(
        result, fitting_phase_weights(changed, phases, rows, aggregate_balance=True)
    )
    assert result[0] / result[1] == pytest.approx(0.5)


def test_legacy_weights_keep_their_fitting_row_ratios():
    weights = torch.tensor([1.0, 2.0, 3.0, 100.0])
    result = fitting_phase_weights(
        weights, np.array([0, 1, 2, 2]), np.arange(3), aggregate_balance=False
    )
    torch.testing.assert_close(result, torch.tensor([0.5, 1.0, 1.5, 0.0]))


def test_missing_fitting_phase_cannot_be_supplied_by_withheld_rows():
    with pytest.raises(ValueError, match="lacks"):
        fitting_phase_weights(
            torch.ones(3), np.array([0, 1, 2]), np.arange(2), aggregate_balance=True
        )


def test_withheld_family_is_removed_from_every_source_and_auxiliary_stays_fit():
    from scripts.screen_hog26_training_family_margin import family_fit_rows

    families = np.array(["family-000", "family-001", "family-000", "<auxiliary>"])
    rows, episodes, excluded = family_fit_rows(
        families, np.array([0, 2, 5, 6, 10]), ["family-000"]
    )
    np.testing.assert_array_equal(rows, [2, 3, 4, 6, 7, 8, 9])
    np.testing.assert_array_equal(episodes, [1, 3])
    assert excluded.sum() == 3


def test_source_roles_cannot_import_selection_or_calibration_into_fitting():
    from scripts.screen_hog26_training_family_margin import source_audit_path

    p = {
        "training": [{"output_corpus": "train", "audit_report": "train-audit"}],
        "primary_candidate_data": {
            "legacy_training_corpora": ["legacy"],
            "legacy_audit_reports": {
                "legacy": "legacy-audit",
                "selection": "selection-audit",
            },
        },
    }
    assert (
        source_audit_path({"path": "train", "role": "procedural"}, p) == "train-audit"
    )
    assert (
        source_audit_path({"path": "legacy", "role": "auxiliary"}, p) == "legacy-audit"
    )
    for path, role in [
        ("selection", "auxiliary"),
        ("train", "auxiliary"),
        ("legacy", "procedural"),
    ]:
        with pytest.raises(ValueError, match="training-only role"):
            source_audit_path({"path": path, "role": role}, p)
