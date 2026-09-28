from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.models import MobileNet_V3_Small_Weights

from clasher.rl.tv_royale_replay import TVRoyaleDetection, TVRoyalePlacementConverter
from scripts.extract_tv_royale_youtube_fullmatch import (
    ACTOR_SCHEMA,
    NON_ENTITY_VISUAL_CLASSES,
    SCHEMA,
    HudRecognizer,
    StableIdentityResolver,
    _actor_row,
    _event_rows,
    _is_public_entity_visual_class,
    _public_mask,
    _write_raw_actor_trajectories,
)

ROOT = Path(__file__).resolve().parents[1]


def test_detector_support_primitives_are_not_public_entities() -> None:
    assert NON_ENTITY_VISUAL_CLASSES
    assert all(
        not _is_public_entity_visual_class(name)
        for name in NON_ENTITY_VISUAL_CLASSES
    )
    assert not _is_public_entity_visual_class("BAR-LEVEL")
    assert _is_public_entity_visual_class("clock")
    assert _is_public_entity_visual_class("hog-rider")


def test_tensor_card_preprocess_batches_mixed_crop_shapes_deterministically() -> None:
    recognizer = HudRecognizer.__new__(HudRecognizer)
    recognizer.device = torch.device("cpu")
    transform = MobileNet_V3_Small_Weights.DEFAULT.transforms()
    crops = [
        np.full((37, 29, 3), 20, dtype=np.uint8),
        np.full((37, 29, 3), 120, dtype=np.uint8),
        np.full((19, 13, 3), 220, dtype=np.uint8),
    ]

    first = recognizer._tensor_preprocess(crops, transform)
    second = recognizer._tensor_preprocess(crops, transform)

    assert first.shape == (3, 3, 224, 224)
    assert torch.isfinite(first).all()
    assert torch.equal(first, second)


def test_pil_batched_card_preprocess_is_bit_exact_to_reference() -> None:
    recognizer = HudRecognizer.__new__(HudRecognizer)
    recognizer.device = torch.device("cpu")
    recognizer._pil_pool = ThreadPoolExecutor(max_workers=2)
    transform = MobileNet_V3_Small_Weights.DEFAULT.transforms()
    crops = [
        np.arange(37 * 29 * 3, dtype=np.uint8).reshape(37, 29, 3),
        np.arange(19 * 13 * 3, dtype=np.uint8).reshape(19, 13, 3),
    ]
    try:
        expected = torch.stack(
            [
                transform(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
                for crop in crops
            ]
        )
        actual = recognizer._pil_batched_preprocess(crops, transform)
    finally:
        recognizer._pil_pool.shutdown()

    assert torch.equal(actual, expected)


def _invalid_hud(candidate: str = "Knight") -> dict[str, object]:
    card = {
        "value": None,
        "candidate": candidate,
        "score": 0.5,
        "runner_up_score": 0.49,
        "margin": 0.01,
        "valid": False,
        "reason": "uncalibrated_or_ambiguous_template_match",
    }
    return {
        "hand": [dict(card) for _ in range(4)],
        "next_card": dict(card),
        "elixir": {
            **card,
            "candidate": 5,
        },
        "all_hand_valid": False,
        "complete_valid": False,
    }


def _record() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "match_id": "youtube-test",
        "split_group_id": "youtube-test",
        "snapshot_id": "youtube-test-000001",
        "sample_index": 1,
        "output_pts": 1,
        "output_time_base": "1/10",
        "source_time_base": "1/1000",
        "timestamp_ms": 100,
        "public": {
            "coordinate_frame": "absolute_world",
            "clock": {"value": None, "valid": False},
            "entities": [],
            "current_frame_deployment_markers": [],
        },
        "offline_privileged_hud": {
            "0": _invalid_hud("Knight"),
            "1": _invalid_hud("RoyalGiant"),
        },
        "offline_evidence": {"play_events": []},
    }


def test_actor_projection_contains_only_own_hud_and_public_state() -> None:
    record = _record()
    actor0 = _actor_row(record, 0)
    actor1 = _actor_row(record, 1)
    assert actor0["schema"] == ACTOR_SCHEMA
    assert actor1["schema"] == ACTOR_SCHEMA
    assert actor0["split_group_id"] == actor1["split_group_id"] == "youtube-test"
    assert actor0["output_pts"] == actor1["output_pts"] == 1
    assert actor0["output_time_base"] == actor1["output_time_base"] == "1/10"
    assert actor0["own_hud"]["hand"][0]["candidate"] == "Knight"
    assert actor1["own_hud"]["hand"][0]["candidate"] == "RoyalGiant"
    serialized0 = json.dumps(actor0, sort_keys=True)
    serialized1 = json.dumps(actor1, sort_keys=True)
    assert "offline_privileged_hud" not in serialized0
    assert "offline_privileged_hud" not in serialized1
    assert "RoyalGiant" not in serialized0
    assert "Knight" not in serialized1


def test_public_mask_fails_closed_without_using_a_label() -> None:
    mask = _public_mask(_invalid_hud())
    assert mask["valid"] is True
    assert mask["legal_action_indices"] == [4 * 18 * 32]
    assert mask["degraded_reason"] == "incomplete_current_frame_hud"


def test_deferred_raw_actor_mode_skips_redundant_trajectory_writes(
    tmp_path: Path,
) -> None:
    paths, counts = _write_raw_actor_trajectories(
        tmp_path,
        [_record(), _record()],
        actor_stride=2,
        mode="deferred",
    )

    assert paths == []
    assert counts == {}
    assert list(tmp_path.iterdir()) == []


def test_stable_resolver_keeps_typed_towers_and_rejects_ui() -> None:
    converter = TVRoyalePlacementConverter()
    resolver = StableIdentityResolver(
        ROOT / "reports/current_client_youtube_stable_vocabulary_v1.json",
        converter,
    )
    tower = resolver.resolve(
        TVRoyaleDetection("queen-tower", 0, 0.9, 0.0, 0.0, 10.0, 10.0)
    )
    ui = resolver.resolve(TVRoyaleDetection("bar", 0, 0.9, 0.0, 0.0, 10.0, 10.0))
    assert tower == {
        "stable_key": "tower:Tower",
        "candidates": ["tower:Tower"],
        "valid": True,
        "reason": None,
    }
    assert ui["stable_key"] is None
    assert ui["valid"] is False
    assert resolver.resolve_card_label("royal_recruits") == "card_action:RoyalRecruits"
    assert resolver.resolve_card_label("zappies") == "card_action:MiniSparkys"


def test_temporal_deployment_markers_are_deduplicated_per_team() -> None:
    def marker(timestamp: int, x: float) -> dict[str, object]:
        row = _record()
        row["timestamp_ms"] = timestamp
        row["public"]["entities"] = [
            {
                "visual_class": "clock",
                "team_id": 0,
                "confidence": 0.9,
                "sprite_box_normalized": [x, 0.5, x + 0.02, 0.53],
                "world_position": None,
                "identity": {
                    "stable_key": None,
                    "candidates": [],
                    "valid": False,
                },
            }
        ]
        return row

    events = _event_rows([marker(0, 0.25), marker(100, 0.251), marker(2_000, 0.25)])
    assert len(events) == 2
    assert all(event["offline_label_only"] for event in events)
    assert all(event["placement_valid"] for event in events)
    assert all(len(event["deployment_tile_absolute"]) == 2 for event in events)


def test_deployment_marker_above_grid_is_rejected_before_clamping() -> None:
    row = _record()
    row["public"]["entities"] = [
        {
            "visual_class": "clock",
            "team_id": 1,
            "confidence": 0.9,
            "sprite_box_normalized": [0.84, 0.0, 0.90, 0.04],
            "world_position": None,
            "identity": {
                "stable_key": None,
                "candidates": [],
                "valid": False,
            },
        }
    ]

    assert _event_rows([row]) == []
