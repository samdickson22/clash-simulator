import copy
import json
from pathlib import Path

import pytest

from scripts.freeze_hog26_outcome_cohort import (
    freeze_cohort,
    require_unopened_final_paths,
    validate_cohort_reports,
)
from scripts.train_hog26_actor_outcome import file_sha256


@pytest.fixture
def protocol():
    return json.loads((Path(__file__).parents[1] / "reports" /
        "hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())


def reports_for(protocol, root):
    p = protocol["primary_candidate"]
    data = protocol["primary_candidate_data"]
    report = {key: p[key] for key in (
        "hidden_size", "margin_residual_scale", "margin_feature_set",
        "margin_progress_power", "epochs", "batch_size", "sequence_steps",
        "learning_rate", "margin_coefficient", "calibration_timing",
    )}
    report.update(
        actor_feature_contract=p["feature_set"], actor_input_critic_fields=False,
        actor_input_previous_reward="forced-zero-unavailable-at-live-inference",
        state_size=398, separate_draw_trunk=True, structured_residual_scale=0.0,
        target_class_mass={"loss": 0.45, "draw": 0.1, "win": 0.45},
        outcome_training_weighting="equal-episode-equal-reached-phase-then-declared-class-mass-v1",
        margin_training_weighting="equal-episode-equal-reached-phase-v1",
        train_class_prior=[0.4, 0.1, 0.5],
        epoch_selection="maximin-phase-then-decisive-auc-among-point-gate-passes-v1",
        margin_epoch_selection="maximum-mae-improvement-among-all-phase-gate-passes-v1",
    )
    roles = {
        "train": [*data["legacy_training_corpora"],
                  *(row["output_corpus"] for row in protocol["training"])],
        "validation": [protocol["development_selection"]["output_corpus"],
                       data["validation_corpora"][1]],
        "calibration": [protocol["probability_calibration"]["output_corpus"]],
    }
    for role, paths in roles.items():
        for name in paths:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        report[f"{role}_corpora"] = [str((root / name).resolve()) for name in paths]
        report[f"{role}_corpus_sha256"] = [file_sha256(root / name) for name in paths]
    return [dict(copy.deepcopy(report), seed=seed) for seed in
            [p["seed"], *protocol["replication"]["seeds"]]]


def test_complete_cohort_requires_same_declared_design_and_bytes(protocol, tmp_path):
    reports = reports_for(protocol, tmp_path)
    validate_cohort_reports(protocol, reports, tmp_path)
    reports[1]["train_corpus_sha256"][0] = "c" * 64
    with pytest.raises(ValueError, match="fitting sources"):
        validate_cohort_reports(protocol, reports, tmp_path)


@pytest.mark.parametrize("change", ["missing", "duplicate", "design", "prior"])
def test_cohort_cannot_select_best_seed_or_mix_designs(protocol, tmp_path, change):
    reports = reports_for(protocol, tmp_path)
    if change == "missing":
        reports.pop()
    elif change == "duplicate":
        reports[1]["seed"] = reports[0]["seed"]
    elif change == "design":
        reports[1]["margin_progress_power"] = 0
    else:
        reports[1]["train_class_prior"] = [0.3, 0.1, 0.6]
    with pytest.raises(ValueError):
        validate_cohort_reports(protocol, reports, tmp_path)


def test_partial_final_collection_prevents_late_freeze(protocol, tmp_path):
    require_unopened_final_paths(protocol, tmp_path)
    partial = tmp_path / protocol["final_holdout"]["generated"]["output_corpus"]
    partial.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exist"):
        require_unopened_final_paths(protocol, tmp_path)


def test_matching_but_undeclared_weighting_is_rejected(protocol, tmp_path):
    reports = reports_for(protocol, tmp_path)
    for report in reports:
        report["margin_training_weighting"] = "all-rows-equal"
    with pytest.raises(ValueError, match="declared design"):
        validate_cohort_reports(protocol, reports, tmp_path)


def test_current_under_review_protocol_cannot_publish_freeze(protocol, tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    output = tmp_path / "freeze.json"
    with pytest.raises(ValueError, match="not cleared"):
        freeze_cohort(path, [], output, root=tmp_path)
    assert not output.exists()
