"""Independent loader-helper checks on writer-produced synthetic NPZ only.

These fixtures establish validation behavior, not real-game provenance or
completeness of the 384-game pilot. No plan/opening/NPZ validator is mocked.
"""

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import scalar_dataset

from scripts.hog26_scalar_corpus import ScalarGameCorpusWriter, validate_scalar_corpus


def synthetic_game(tmp_path):
    seat = 1
    path = tmp_path / "synthetic-game.npz"
    policy = ["<pad>", "<unknown>", "tower_body:Tower"] + [
        f"card_action:{c}" for c in "ABCDEFGH"
    ]
    expected_hand = np.arange(3, 8)
    metadata = {
        "schema": "clasher.scalar-pilot-game-metadata.v1",
        "mode": "collect",
        "source_authority_sha256": "synthetic-source",
        "plan_sha256": "synthetic-plan",
        "opening_metadata": {"fixture": "synthetic-only"},
        "opening_authority": {"fixture": "synthetic-only"},
        "scenario_id": "synthetic-scenario",
        "cluster_id": "synthetic-cluster",
        "ordinal": 0,
        "learner_seat": seat,
        "family_id": "family-000",
        "style": "balanced",
        "outcome_token_names": policy
        + [
            "projectile:TowerPrincessProjectile",
            "public_tower_shot:king",
            "public_effect:chain_bolt",
            "building_body:SkeletonContainerNew",
        ],
        "policy_token_names": policy,
        "mask_semantics_digest": "synthetic-mask",
        "retention": "all predecision learner rows through first actual terminal; no filtering by success/outcome",
    }
    features = np.zeros((1, 32), np.float32)
    features[0, 5] = 1
    actor = SimpleNamespace(
        entity_ids=np.array([2]),
        entity_features=features,
        entity_mask=np.array([True]),
        hand_ids=expected_hand.copy(),
        global_features=np.zeros(18, np.float32),
        opponent_history_ids=np.zeros(0, int),
        opponent_history_ages=np.zeros(0, np.float32),
        opponent_seen_card_ids=np.zeros(0, int),
    )
    inputs = SimpleNamespace(
        entity_id_confidence=np.ones((2, 1, 1)),
        entity_feature_confidence=np.ones((2, 1, 1, 32)),
        hand_id_confidence=np.ones((2, 1, 5)),
        global_feature_confidence=np.ones((2, 1, 18)),
        action_mask=np.ones((2, 1, 2306), bool),
        previous_actions=np.full((2, 1), 2304),
        episode_starts=np.ones((2, 1), bool),
    )
    writer = ScalarGameCorpusWriter(path, metadata)
    writer.append(actor, inputs, learner_seat=seat, tick=0, action=2304, success=False)
    inputs.episode_starts[:] = False
    writer.append(actor, inputs, learner_seat=seat, tick=8, action=2304, success=False)
    audit = writer.finish(
        terminal_tick=16,
        winner=seat,
        learner_seat=seat,
        terminal_tower_hp=[[0, 100, 400], [100, 100, 400]],
        initial_tower_hp=[[100, 100, 400], [100, 100, 400]],
        actual_terminal=True,
    )
    with np.load(path, allow_pickle=False) as archive:
        data = dict(archive)
    record = {
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **{
            key: metadata[key]
            for key in (
                "family_id",
                "style",
                "learner_seat",
                "scenario_id",
                "cluster_id",
            )
        },
        **{key: value for key, value in audit.items() if key != "metadata"},
    }
    return path, data, audit, record, metadata, expected_hand, seat


def call_helper(fixture):
    _, data, audit, record, metadata, hand, seat = fixture
    return scalar_dataset._validate_game_record(
        data, audit, record, metadata, hand, seat
    )


def test_valid_synthetic_game_passes_independent_loader_helper(tmp_path):
    fixture = synthetic_game(tmp_path)
    assert validate_scalar_corpus(fixture[0])["outcome_wdl"] == [1, 0, 0]
    call_helper(fixture)


@pytest.mark.parametrize(
    "field",
    [
        "family_id",
        "style",
        "learner_seat",
        "scenario_id",
        "cluster_id",
        "rows",
        "rejected_card_actions",
        "noop_false_results",
        "failed_ability_actions",
        "outcome_wdl",
        "terminal_tower_margin",
    ],
)
def test_record_fields_cannot_diverge_from_recomputed_audit(tmp_path, field):
    fixture = synthetic_game(tmp_path)
    fixture[3][field] = "wrong-value"
    with pytest.raises(ValueError):
        call_helper(fixture)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_metadata",
        "missing_retention",
        "wrong_mask",
        "wrong_first_hand",
        "wrong_scalar_seat",
    ],
)
def test_metadata_and_payload_are_bound_to_external_expected_values(tmp_path, mutation):
    fixture = synthetic_game(tmp_path)
    path, data, _, record, expected, _, _ = fixture
    metadata = json.loads(data["metadata_json"].item())
    if mutation == "extra_metadata":
        metadata["future_label_hint"] = "forbidden-extra"
    elif mutation == "missing_retention":
        metadata.pop("retention")
    elif mutation == "wrong_mask":
        metadata["mask_semantics_digest"] = "different-mask"
    elif mutation == "wrong_first_hand":
        data["hand_ids"][0, [0, 1]] = data["hand_ids"][0, [1, 0]]
    elif mutation == "wrong_scalar_seat":
        data["learner_seat"] = np.array(0)
        data["outcome_wdl"] = data["outcome_wdl"][::-1]
        data["terminal_tower_margin"] = -data["terminal_tower_margin"]
    data["metadata_json"] = np.array(json.dumps(metadata))
    np.savez_compressed(path, **data)
    audit = validate_scalar_corpus(path)  # mutation still meets generic storage schema
    record.update({key: value for key, value in audit.items() if key != "metadata"})
    record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    updated = (path, data, audit, record, expected, fixture[5], fixture[6])
    with pytest.raises(ValueError):
        call_helper(updated)


@pytest.mark.parametrize("invalid_token", [1, 2, 9999])
def test_unresolved_noncard_and_out_of_range_hands_fail_both_boundaries(
    tmp_path, invalid_token
):
    fixture = synthetic_game(tmp_path)
    path, data, *_ = fixture
    data["hand_ids"][1, -1] = invalid_token
    np.savez_compressed(path, **data)
    with pytest.raises(ValueError, match="unresolved or non-card public identity"):
        validate_scalar_corpus(path)
    # Defense in depth: loader helper also refuses a mutated payload even when
    # supplied the earlier valid audit. This is not a replacement corpus audit.
    with pytest.raises(ValueError, match="hand identity"):
        call_helper(fixture)
