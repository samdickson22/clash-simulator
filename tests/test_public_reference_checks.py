"""Reference calibration rejects numerical and information-boundary errors."""

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from clasher.rl.native_public_observation import (
    NativePublicObservationAdapter,
    NativePublicScope,
)
from clasher.rl.public_reference_checks import check_reference_packet
from clasher.rl.structured_obs import StructuredObservationBuilder


@pytest.fixture
def reference():
    data = json.loads(
        (
            Path(__file__).parent / "fixtures/native_public_frames_15_535_86.json"
        ).read_text()
    )
    frame = data["cases"][0]["snapshot"]
    names = (
        "Knight",
        "IceGolem",
        "Archers",
        "Musketeer",
        "Cannon",
        "Fireball",
        "Log",
        "Skeletons",
        "HogRider",
        "IceSpirit",
        "Zap",
        "Tesla",
        "Mirror",
    )
    builder = StructuredObservationBuilder(
        card_vocab=list(names), canonical_lane_globals=True
    )
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope(
            "15.535.86",
            hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest(),
        ),
        card_names=names,
    )
    tokens = {
        builder.loader.get_card(n)._raw_entry["id"]: builder.token_id(
            n, namespace="card_action"
        )
        for n in names
    }
    return frame, adapter, tokens


@pytest.mark.parametrize("owner", [0, 1])
def test_both_perspectives_preserve_reference_numbers(reference, owner):
    frame, adapter, tokens = reference
    assert (
        check_reference_packet(
            frame, adapter.project(frame, owner), owner, card_tokens=tokens
        )
        == []
    )


@pytest.mark.parametrize(
    "fault",
    [
        "position",
        "hp",
        "elixir",
        "hand",
        "private",
        "confidence",
        "missing_body",
        "crown",
    ],
)
def test_corrupted_packet_is_rejected(reference, fault):
    frame, adapter, tokens = reference
    packet = copy.deepcopy(adapter.project(frame, 0))
    actor = packet.observation
    index = next(i for i, v in enumerate(actor.entity_mask) if v)
    if fault == "position":
        actor.entity_features[index, 0] += 1 / 18000
    elif fault == "hp":
        actor.entity_features[index, 9] -= 0.01
    elif fault == "elixir":
        actor.global_features[5] += 0.001
    elif fault == "hand":
        actor.hand_ids[0] = 0
    elif fault == "private":
        actor.entity_features[index, 21] = 1
    elif fault == "confidence":
        packet.entity_feature_confidence[index, 9] = 0
    elif fault == "missing_body":
        actor.entity_mask[index] = False
    else:
        actor.global_features[8] -= 0.01
    assert check_reference_packet(frame, packet, 0, card_tokens=tokens)


def test_conflicting_team_flags_are_rejected(reference):
    frame, adapter, tokens = reference
    packet = adapter.project(frame, 0)
    packet.observation.entity_features[0, 2:4] = 1
    assert "invalid ownership or entity-kind encoding" in check_reference_packet(
        frame, packet, 0, card_tokens=tokens
    )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "identity",
        "level",
        "level_confidence",
        "missing_effect",
        "duplicate_effect",
    ],
)
def test_entity_correspondence_detects_label_and_effect_errors(reference, fault):
    import numpy as np

    from clasher.rl.public_reference_checks import check_reference_entities

    frame, adapter, _ = reference
    frame = copy.deepcopy(frame)
    packet = copy.deepcopy(adapter.project(frame, 0))
    actor = packet.observation
    # Attach exact reference-level labels to the existing body rows. The fixture
    # scene has standard towers and one Knight; no native ID enters actor rows.
    actor = replace(
        actor,
        entity_levels=np.where(actor.entity_mask, 11, 0).astype(np.int64),
        entity_level_confidence=actor.entity_mask.astype(np.float32),
    )
    packet = replace(packet, observation=actor)
    levels = {o["nativeObjectId"]: 11 for o in frame["objects"]}
    certainty = {k: 1.0 for k in levels}
    towers = {
        n: adapter.builder.token_id(n, namespace="tower")
        for n in ("Tower", "KingTower")
    }
    bodies = {26000000: (0, adapter.builder.token_id("Knight", namespace="troop_body"))}
    effect_token = 999  # Independent declared reference token in this checker test.
    effect = {
        "nativeObjectId": 123456,
        "cardId": 28000000,
        "owner": 1,
        "x": 8000,
        "y": 12000,
        "hp": None,
        "maxHp": None,
        "dataGlobalId": 10000000,
    }
    frame["objects"].append(effect)
    index = int(actor.entity_mask.sum())
    actor.entity_mask[index] = True
    actor.entity_ids[index] = effect_token
    actor.entity_features[index, :] = 0
    actor.entity_features[index, 0:2] = [8000 / 18000, 12000 / 32000]
    actor.entity_features[index, 3] = 1
    actor.entity_features[index, 6] = 1
    if fault == "identity":
        actor.entity_ids[0] += 1
    elif fault == "level":
        actor.entity_levels[0] = 12
    elif fault == "level_confidence":
        actor.entity_level_confidence[0] = 0
    elif fault == "missing_effect":
        actor.entity_mask[index] = False
    elif fault == "duplicate_effect":
        actor.entity_mask[index + 1] = True
        actor.entity_ids[index + 1] = effect_token
        actor.entity_features[index + 1] = actor.entity_features[index]
    errors = check_reference_entities(
        frame,
        {"objects": frame["objects"]},
        packet,
        0,
        body_tokens=bodies,
        effect_tokens={10000000: (2, effect_token)},
        tower_tokens=towers,
        levels=levels,
        level_confidence=certainty,
    )
    assert bool(errors) == (fault is not None)
