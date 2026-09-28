from __future__ import annotations

import math

import numpy as np
import pytest

from clasher.rl.common import NUM_TILES
from clasher.rl.tv_royale_replay import (
    TVRoyaleDetection,
    TVRoyalePlacementConverter,
    recover_deployment_cost_bubble,
    recover_deployment_clock,
)


def test_tv_royale_converter_builds_public_canonical_placement() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    converted = converter.convert(
        raw_card="hog_rider",
        raw_hand=["gray_fireball", "hog_rider", "ice_spirit", "cannon"],
        elixir=7.5,
        frame=600,
        x=90,
        y=500,
        detections=[
            TVRoyaleDetection("knight", 0, 0.9, 80.0, 400.0, 120.0, 460.0),
            TVRoyaleDetection("queen-tower", 1, 0.95, 45.0, 100.0, 120.0, 210.0),
            TVRoyaleDetection("tower-bar", 1, 0.99, 45.0, 90.0, 120.0, 105.0),
        ],
    )

    assert converted is not None
    assert converted.target_card == "HogRider"
    assert converted.target_slot == 1
    assert converted.expert_action // NUM_TILES == 1
    assert converted.action_mask[converted.expert_action]
    assert converted.action_mask[converter.noop_action]
    assert converted.global_features[5] == np.float32(0.75)
    assert converted.entity_mask.sum() == 2
    # Bottom-player detections become own entities after canonical rotation.
    assert converted.entity_features[0, 2] == np.float16(1.0)
    knight_speed = float(converter.builder.loader.get_card("Knight").speed)
    assert converted.entity_features[0, 23] == np.float16(
        math.log1p(knight_speed) / math.log1p(1000.0)
    )
    assert converted.entity_features[0, 27] == np.float16(0.0)
    assert converted.entity_features[0, 28] == np.float16(1.0)
    # Top-left source coordinates rotate to the canonical top-right.
    tower_rows = np.flatnonzero(converted.entity_features[:, 31] > 0)
    assert tower_rows.size == 1
    tower = converted.entity_features[tower_rows[0]]
    assert tower[0] > np.float16(0.5)
    assert tower[1] > np.float16(0.5)
    assert tower[3] == np.float16(1.0)
    # Detector width/height are visual sprite bounds, never gameplay geometry.
    # The imported tower receives the live simulator's separate 1.0-tile
    # collision radius regardless of the supplied pixel box dimensions.
    assert tower[26] == np.float16(1.0 / 3.0)


def test_tv_royale_tower_geometry_does_not_depend_on_detector_box() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    common = {
        "raw_card": "knight",
        "raw_hand": ["knight", "fireball", "ice_spirit", "cannon"],
        "elixir": 5.0,
        "frame": 10,
        "x": 90,
        "y": 500,
    }
    small = converter.convert(
        detections=[
            TVRoyaleDetection("queen-tower", 1, 0.95, 80.0, 120.0, 100.0, 150.0)
        ],
        **common,
    )
    large = converter.convert(
        detections=[
            TVRoyaleDetection("queen-tower", 1, 0.95, 30.0, 45.0, 150.0, 225.0)
        ],
        **common,
    )

    assert small is not None and large is not None
    small_tower = small.entity_features[np.flatnonzero(small.entity_mask)[0]]
    large_tower = large.entity_features[np.flatnonzero(large.entity_mask)[0]]
    assert small_tower[26] == large_tower[26] == np.float16(1.0 / 3.0)


def test_tv_royale_public_schema_uses_measured_hp_and_missingness() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    image = np.full((683, 428, 3), (65, 65, 80), dtype=np.uint8)
    # Unit bar: half-filled blue, directly above the Hog Rider body.
    image[100:108, 41:60] = (235, 190, 70)
    # Own Princess Tower bar: half-filled in the detector's upper colour strip.
    image[534:538, 68:92] = (235, 190, 70)
    detections = [
        TVRoyaleDetection("bar", 0, 0.95, 40, 99, 80, 109),
        TVRoyaleDetection("hog-rider", 0, 0.90, 42, 112, 78, 170),
        TVRoyaleDetection("knight", 1, 0.88, 250, 180, 285, 235),
        TVRoyaleDetection("tower-bar", 0, 0.94, 50, 530, 120, 550),
        TVRoyaleDetection("queen-tower", 0, 0.96, 45, 560, 125, 650),
        TVRoyaleDetection("poison", 1, 0.91, 150, 180, 280, 320),
        # Out-of-vocabulary effects fail closed in v2 instead of becoming a
        # fabricated generic troop.
        TVRoyaleDetection("clone", 0, 0.99, 180, 200, 260, 300),
    ]

    public = converter.public_observation(
        image_bgr=image,
        raw_hand=["hog_rider", "knight", "fireball", "cannon"],
        elixir=7.0,
        frame=600,
        detections=detections,
        previous_detections=[
            TVRoyaleDetection("hog-rider", 0, 0.92, 32, 107, 68, 165),
        ],
        previous_frame=599,
        raw_next_card="ice_spirit",
    )
    observation = public.observation
    hog_id = converter.builder.token_id("HogRider")
    knight_id = converter.builder.token_id("Knight")
    hog_row = int(np.flatnonzero(observation.entity_ids == hog_id)[0])
    knight_row = int(np.flatnonzero(observation.entity_ids == knight_id)[0])

    assert int(observation.entity_mask.sum()) == 4
    assert not np.any(
        observation.entity_ids[observation.entity_mask]
        == converter.builder.token_id(None)
    )
    assert observation.entity_features[hog_row, 9] == pytest.approx(0.5, abs=0.06)
    assert public.entity_feature_confidence[hog_row, 9] > 0.5
    assert observation.entity_features[hog_row, 27] == pytest.approx(
        -10.0 / math.sqrt(125.0), abs=0.02
    )
    assert observation.entity_features[hog_row, 28] == pytest.approx(
        -5.0 / math.sqrt(125.0), abs=0.02
    )
    assert public.entity_feature_confidence[hog_row, 27] > 0.3
    assert observation.entity_features[knight_row, 9] == 0.0
    assert public.entity_feature_confidence[knight_row, 9] == 0.0
    poison_id = converter.builder.token_id("Poison")
    poison_row = int(np.flatnonzero(observation.entity_ids == poison_id)[0])
    assert observation.entity_features[poison_row, 7] == 1.0
    assert public.entity_feature_confidence[poison_row, 7] > 0.8
    assert public.entity_feature_confidence[poison_row, 9] == 0.0
    # The source-left lower tower rotates to canonical right (global slot 9).
    assert observation.global_features[9] == pytest.approx(0.5, abs=0.08)
    assert public.global_feature_confidence[9] > 0.4
    assert observation.global_features[8] == 0.0
    assert public.global_feature_confidence[8] == 0.0
    assert public.hand_id_confidence.tolist() == [1.0, 1.0, 1.0, 1.0, 1.0]
    assert observation.hand_ids[4] == converter.builder.token_id("IceSpirit")

    legacy = converter.convert_noop(
        raw_card="None",
        raw_hand=["hog_rider", "knight", "fireball", "cannon"],
        elixir=7.0,
        frame=600,
        detections=detections,
    )
    assert legacy is not None
    legacy_knight = int(np.flatnonzero(legacy.entity_ids == knight_id)[0])
    # Existing v1 corpora keep their historical semantics; v2 is opt-in.
    assert legacy.entity_features[legacy_knight, 9] == 1.0


def test_tv_royale_converter_rejects_unusable_labels() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    common = {
        "raw_hand": ["knight", "fireball", "ice_spirit", "cannon"],
        "elixir": 5.0,
        "frame": 10,
        "detections": [],
    }
    assert converter.convert(raw_card="wizard", x=10, y=500, **common) is None
    assert converter.convert(raw_card="knight", x=-1, y=-1, **common) is None
    assert (
        converter.convert(
            raw_card="hog_rider",
            x=10,
            y=500,
            **common,
        )
        is None
    )
    # Ordinary troops cannot be supervised onto the opponent's side.
    assert converter.convert(raw_card="knight", x=90, y=100, **common) is None


def test_tv_royale_converter_builds_explicit_noop_training_row() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    converted = converter.convert_noop(
        raw_card="None",
        raw_hand=["gray_fireball", "hog_rider", "ice_spirit", "cannon"],
        elixir=8.5,
        frame=900,
        detections=[
            TVRoyaleDetection("knight", 0, 0.9, 80.0, 400.0, 120.0, 460.0),
        ],
    )

    assert converted is not None
    assert converted.target_card == "<noop>"
    assert converted.target_slot == -1
    assert converted.expert_action == converter.noop_action
    assert converted.action_mask[converter.noop_action]
    assert converted.global_features[5] == np.float32(0.85)
    assert converted.entity_mask.sum() == 1


def test_tv_royale_action_mask_respects_observed_elixir() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    converted = converter.convert_noop(
        raw_card="None",
        raw_hand=["knight", "fireball", "ice_spirit", "cannon"],
        elixir=2.0,
        frame=10,
        detections=[],
    )

    assert converted is not None
    slot_masks = converted.action_mask[: 4 * NUM_TILES].reshape(4, NUM_TILES)
    assert not slot_masks[0].any()
    assert not slot_masks[1].any()
    assert slot_masks[2].any()
    assert not slot_masks[3].any()
    assert converted.action_mask[converter.noop_action]
    assert (
        converter.convert_type_only(
            raw_card="knight",
            raw_hand=["knight", "fireball", "ice_spirit", "cannon"],
            elixir=2.0,
            frame=10,
            detections=[],
        )
        is None
    )


def test_tv_royale_converter_rejects_ambiguous_noop_rows() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    valid_hand = ["knight", "fireball", "ice_spirit", "cannon"]

    assert converter.is_noop_training_candidate(
        raw_card="None", raw_hand=valid_hand
    ) == (True, None)
    assert converter.is_noop_training_candidate(
        raw_card="knight", raw_hand=valid_hand
    ) == (False, "not_explicit_noop")
    assert converter.is_noop_training_candidate(
        raw_card="None", raw_hand=valid_hand[:3]
    ) == (False, "incomplete_hand")
    assert converter.is_noop_training_candidate(
        raw_card="None", raw_hand=["knight", "wizard", "ice_spirit", "cannon"]
    ) == (False, "outside_enabled_vocabulary")
    assert (
        converter.convert_noop(
            raw_card="knight",
            raw_hand=valid_hand,
            elixir=5.0,
            frame=10,
            detections=[],
        )
        is None
    )


def test_tv_royale_converter_honors_enemy_side_deployment_data() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    common = {
        "raw_hand": ["miner", "fireball", "ice_spirit", "cannon"],
        "elixir": 5.0,
        "frame": 10,
        "x": 90,
        "y": 100,
        "detections": [],
    }
    miner = converter.convert(raw_card="miner", **common)
    spell = converter.convert(raw_card="fireball", **common)
    assert miner is not None
    assert spell is not None
    assert miner.action_mask[miner.expert_action]
    assert spell.action_mask[spell.expert_action]


def test_tv_royale_type_only_conversion_carries_slot_without_location_claim() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    converted = converter.convert_type_only(
        raw_card="ice_spirit",
        raw_hand=["knight", "fireball", "ice_spirit", "cannon"],
        elixir=5.0,
        frame=10,
        detections=[],
    )
    assert converted is not None
    assert converted.target_slot == 2
    assert converted.expert_action // (18 * 32) == 2
    assert converted.action_mask[converted.expert_action]


def test_tv_royale_location_training_candidate_matches_upstream_filters() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    common = {
        "raw_card": "knight",
        "raw_hand": ["knight", "fireball", "ice_spirit", "cannon"],
        "elixir": 5.0,
        "x": 90,
        "y": 500,
    }
    assert converter.is_location_training_candidate(**common) == (True, None)
    assert converter.is_location_training_candidate(
        **{**common, "raw_card": "fireball"}
    ) == (False, "spell_location_label")
    assert converter.is_location_training_candidate(
        **{**common, "y": 200}
    ) == (False, "non_lower_side")
    assert converter.is_location_training_candidate(
        **{**common, "raw_hand": common["raw_hand"][:3]}
    ) == (False, "incomplete_hand")
    assert converter.is_location_training_candidate(
        **{**common, "raw_hand": ["knight", "wizard", "ice_spirit", "cannon"]}
    ) == (False, "outside_enabled_vocabulary")


def test_tv_royale_spell_location_candidate_requires_supported_complete_hand() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    common = {
        "raw_card": "poison",
        "raw_hand": ["poison", "knight", "ice_spirit", "cannon"],
        "elixir": 5.0,
        "x": 90,
        "y": 200,
    }
    assert converter.is_spell_location_training_candidate(**common) == (True, None)
    assert converter.is_spell_location_training_candidate(
        **{**common, "raw_card": "knight"}
    ) == (False, "not_spell_location_label")
    assert converter.is_spell_location_training_candidate(
        **{**common, "raw_hand": common["raw_hand"][:3]}
    ) == (False, "incomplete_hand")
    assert converter.is_spell_location_training_candidate(
        **{**common, "raw_hand": ["poison", "wizard", "ice_spirit", "cannon"]}
    ) == (False, "outside_enabled_vocabulary")


def test_tv_royale_card_aliases_and_tile_rotation() -> None:
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)
    assert converter.source_card_name("gray_e_wiz") == "ElectroWizard"
    assert converter.source_card_name("evo_tesla_coil") == "Tesla"
    top_left = converter.source_pixel_to_canonical_tile(0, 62)
    assert top_left == (32 - 1) * 18 + 17


def test_recover_deployment_clock_accepts_one_new_cluster() -> None:
    before = [TVRoyaleDetection("clock", 0, 0.9, 40.0, 390.0, 50.0, 400.0)]
    after = [
        TVRoyaleDetection("clock", 0, 0.92, 40.5, 390.0, 50.5, 400.0),
        TVRoyaleDetection("clock", 0, 0.95, 195.0, 495.0, 205.0, 505.0),
        TVRoyaleDetection("clock", 0, 0.80, 198.0, 496.0, 208.0, 506.0),
    ]
    recovered = recover_deployment_clock(before, after)
    assert recovered is not None
    assert 200.0 <= recovered.x <= 203.0
    assert 500.0 <= recovered.y <= 501.0
    assert recovered.confidence == 0.95
    assert recovered.support == 2


def test_recover_deployment_clock_fails_closed_on_ambiguity() -> None:
    assert (
        recover_deployment_clock(
            [],
            [
                TVRoyaleDetection("clock", 0, 0.9, 95.0, 395.0, 105.0, 405.0),
                TVRoyaleDetection("clock", 0, 0.9, 295.0, 495.0, 305.0, 505.0),
            ],
        )
        is None
    )
    assert (
        recover_deployment_clock(
            [TVRoyaleDetection("clock", 0, 0.9, 95.0, 395.0, 105.0, 405.0)],
            [TVRoyaleDetection("clock", 0, 0.9, 96.0, 395.0, 106.0, 405.0)],
        )
        is None
    )
    assert (
        recover_deployment_clock(
            [],
            [
                TVRoyaleDetection("clock", 1, 0.99, 95.0, 395.0, 105.0, 405.0),
                TVRoyaleDetection("clock", 0, 0.50, 195.0, 495.0, 205.0, 505.0),
            ],
        )
        is None
    )


def test_recover_deployment_cost_bubble_uses_novel_bottom_center() -> None:
    before = [TVRoyaleDetection("elixir", 0, 0.99, 40, 400, 60, 430)]
    after = [
        TVRoyaleDetection("elixir", 0, 0.99, 40, 400, 60, 430),
        TVRoyaleDetection("elixir", 0, 0.91, 180, 470, 220, 504),
        TVRoyaleDetection("elixir", 1, 0.99, 300, 100, 340, 140),
    ]

    recovered = recover_deployment_cost_bubble(before, after)

    assert recovered is not None
    assert recovered.x == pytest.approx(200.0)
    assert recovered.y == pytest.approx(500.1625)
    assert recovered.confidence == pytest.approx(0.91)


def test_recover_deployment_cost_bubble_fails_closed_on_two_novel_clusters() -> None:
    assert (
        recover_deployment_cost_bubble(
            [],
            [
                TVRoyaleDetection("elixir", 0, 0.9, 80, 470, 100, 504),
                TVRoyaleDetection("elixir", 0, 0.9, 300, 470, 320, 504),
            ],
        )
        is None
    )
