from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports" / "hog26_procedural_outcome_protocol_seed1278401.json"


def test_procedural_outcome_protocol_is_split_safe_and_pinned() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    for authority in ("base_policy", "procedural_decks", "original_decks"):
        row = protocol[authority]
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]

    manifest = json.loads((ROOT / protocol["procedural_decks"]["path"]).read_text())
    actual_families: dict[str, set[str]] = {}
    for row in manifest["decks"]:
        if row.get("family_id") is not None:
            actual_families.setdefault(row["split"], set()).add(row["family_id"])

    train_rows = protocol["training"]
    train_families = set(train_rows[0]["family_ids"])
    assert all(set(row["family_ids"]) == train_families for row in train_rows)
    assert train_families == actual_families["train"]
    selection = set(protocol["development_selection"]["family_ids"])
    calibration = set(protocol["probability_calibration"]["family_ids"])
    holdout = set(protocol["final_holdout"]["generated"]["family_ids"])
    assert selection | calibration == actual_families["development"]
    assert holdout == actual_families["holdout"]
    assert not selection & calibration
    assert not train_families & (selection | calibration | holdout)
    assert not (selection | calibration) & holdout

    for row in [
        *train_rows,
        protocol["development_selection"],
        protocol["probability_calibration"],
        protocol["final_holdout"]["generated"],
    ]:
        assert row["expected_games"] == (
            len(row["family_ids"])
            * 4
            * len(row["opponents"])
            * 2
            * row["episodes_per_seat"]
        )
    reserved = protocol["final_holdout"]["reserved_original"]
    assert reserved["expected_games"] == (
        len(reserved["opponents"]) * 2 * reserved["episodes_per_seat"]
    )

    seeds = [row["seed"] for row in train_rows]
    seeds.extend(
        [
            protocol["development_selection"]["seed"],
            protocol["probability_calibration"]["seed"],
            protocol["final_holdout"]["generated"]["seed"],
            protocol["final_holdout"]["reserved_original"]["seed"],
        ]
    )
    assert len(seeds) == len(set(seeds))
    train_opponents = {opponent for row in train_rows for opponent in row["opponents"]}
    assert set(protocol["development_selection"]["opponents"]) <= train_opponents
    assert set(protocol["probability_calibration"]["opponents"]) <= train_opponents
    assert "split-lane" not in train_opponents
    assert protocol["final_holdout"]["generated"]["opponents"] == ["split-lane"]
    assert protocol["final_holdout"]["reserved_original"]["opponents"] == ["split-lane"]
    candidate = protocol["primary_candidate"]
    assert candidate["feature_set"] == "structured-summary"
    assert candidate["margin_progress_power"] == 6.0
    assert candidate["selection_uses_only_development_selection"] is True
    assert candidate["probability_shrinkage_uses_only_probability_calibration"] is True
    assert candidate["final_holdout_forbidden_until_state_sha_frozen"] is True
    assert sum(candidate["target_class_mass_loss_draw_win"]) == 1.0
    candidate_data = protocol["primary_candidate_data"]
    assert all(
        (ROOT / path).is_file() for path in candidate_data["legacy_training_corpora"]
    )
    assert candidate_data["new_training_corpora"] == (
        "all three training rows in this protocol"
    )
    assert candidate_data["validation_corpora"][0] == (
        "development_selection.output_corpus"
    )
    assert candidate_data["calibration_corpora"] == [
        "probability_calibration.output_corpus"
    ]
    assert candidate_data["holdout_corpora"] == []
    assert candidate_data["opened_historical_holdout_forbidden"] is True


def test_amended_protocol_filters_actual_legacy_episodes_and_scopes_exposure() -> None:
    protocol = json.loads(
        (
            ROOT
            / "reports"
            / "hog26_procedural_outcome_protocol_reassessed_20260908.json"
        ).read_text()
    )
    assert (
        protocol["amendment"]["supersedes_sha256"]
        == hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    )
    data = protocol["historical_pre_range_fix_candidate_data"]
    for path in data["legacy_training_corpora"]:
        with np.load(ROOT / path, allow_pickle=False) as archive:
            metadata = json.loads(str(archive["metadata_json"]))
            episode_styles = np.asarray(metadata["opponents"])[
                archive["episode_opponent_indices"]
            ]
            assert "split-lane" not in episode_styles
            if not metadata.get("symmetric_draw_source"):
                assert (
                    metadata["source_corpus_sha256"]
                    == hashlib.sha256(
                        Path(metadata["source_corpus"]).read_bytes()
                    ).hexdigest()
                )
                with np.load(metadata["source_corpus"], allow_pickle=False) as source:
                    original = json.loads(str(source["metadata_json"]))
                    assert "split-lane" in original["opponents"]
    scope = protocol["opponent_generalization"]
    assert scope["head_held_out_styles"] == ["split-lane"]
    assert "split-lane" in scope["base_policy_training_exposure"]
    assert protocol["final_holdout"]["controlled_draw"]["actor_views"] == 16
    assert protocol["replication"]["seeds"] == [1278802, 1278803]



def test_corrected_refresh_excludes_pre_fix_fitting_data():
    protocol = json.loads((ROOT / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    old = {row["output_corpus"] for row in protocol["historical_pre_range_fix_training"]}
    old.update(protocol["historical_pre_range_fix_candidate_data"]["legacy_training_corpora"])
    current = {row["output_corpus"] for row in protocol["training"]}
    current.update(protocol["primary_candidate_data"]["legacy_training_corpora"])
    assert not old & current
    assert sum(row["expected_games"] for row in protocol["training"]) == 384
    assert all(row["opening_schedule"] == "seeded-ordered-decks-v1" for row in protocol["training"])
    assert protocol["training_readiness"]["status"] == "under-review"
    controls = protocol["corrected_draw_controls"]
    assert controls["training"]["seed"] != controls["validation"]["seed"]
