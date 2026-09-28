from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.tv_royale_replay import TVRoyaleDetection, TVRoyalePlacementConverter
from clasher.rl.tv_royale_ui import UIPlayEvent


def _module():
    path = Path("scripts/extract_tv_royale_raw_cascade.py")
    spec = importlib.util.spec_from_file_location("extract_tv_royale_raw_cascade", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_frame_selection_prioritizes_accepted_labels() -> None:
    module = _module()
    frames = [0, 20, 40, 60, 80, 100]
    labels = {20: ["noop"], 80: ["type:arrows"]}

    assert module._select_audit_frames(frames, labels, samples=2) == [20, 80]


def test_audit_frame_selection_uses_temporal_fallback_without_labels() -> None:
    module = _module()
    frames = [0, 20, 40, 60, 80, 100]

    assert module._select_audit_frames(frames, {}, samples=2) == [0, 100]
    assert module._select_audit_frames(frames, {}, samples=0) == []


def _clock(x: float, y: float, confidence: float = 0.9) -> TVRoyaleDetection:
    return TVRoyaleDetection("clock", 0, confidence, x - 2, y - 2, x + 2, y + 2)


def test_consistent_adjacent_clocks_recover_one_legal_tile() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    event = UIPlayEvent(frame=20, card="knight")
    detections = {
        20: [],
        21: [_clock(200, 500, 0.85)],
        22: [_clock(202, 501, 0.95)],
    }

    recovered, reason = module._recover_consistent_location(
        event, detections, converter
    )

    assert reason is None
    assert recovered is not None
    assert recovered.confidence == 0.95


def test_missing_adjacent_clock_frame_fails_closed() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    event = UIPlayEvent(frame=20, card="knight")

    recovered, reason = module._recover_consistent_location(
        event,
        {20: [], 21: [_clock(200, 500, 0.85)], 22: []},
        converter,
    )

    assert recovered is None
    assert reason == "clock_missing_followup"


def test_inconsistent_adjacent_clock_tiles_fail_closed() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    event = UIPlayEvent(frame=20, card="knight")
    detections = {
        20: [],
        21: [_clock(50, 500)],
        22: [_clock(350, 500)],
    }

    recovered, reason = module._recover_consistent_location(
        event, detections, converter
    )

    assert recovered is None
    assert reason == "inconsistent_clock_tiles"


def test_spell_location_clock_is_not_claimed() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")

    recovered, reason = module._recover_consistent_location(
        UIPlayEvent(frame=20, card="arrows"),
        {20: [], 21: [_clock(200, 500)]},
        converter,
    )

    assert recovered is None
    assert reason == "spell_clock_not_expected"


def test_spell_detection_windows_are_diagnostic_and_spell_class_only() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    fireball = TVRoyaleDetection("fireball", 0, 0.91, 100, 200, 120, 220)
    knight = TVRoyaleDetection("knight", 1, 0.99, 140, 240, 180, 300)

    windows = module._spell_detection_windows(
        [UIPlayEvent(frame=20, card="fireball"), UIPlayEvent(frame=40, card="knight")],
        {20: [fireball, knight], 21: [knight], 22: [fireball]},
        converter,
    )

    assert set(windows) == {"20"}
    assert windows["20"]["card"] == "fireball"
    assert windows["20"]["frames"]["20"] == [
        {
            "class_name": "fireball",
            "belonging": 0,
            "confidence": 0.91,
            "xyxy": [100, 200, 120, 220],
        }
    ]
    assert windows["20"]["frames"]["21"] == []
    assert windows["20"]["frames"]["22"][0]["class_name"] == "fireball"


def _spell_box(
    name: str, x: float, y: float, confidence: float = 0.9
) -> TVRoyaleDetection:
    return TVRoyaleDetection(
        name, 1, confidence, x - 30, y - 30, x + 30, y + 30
    )


def test_persistent_area_spell_recovers_stable_new_visual_center() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    event = UIPlayEvent(frame=20, card="poison")
    detections = {
        20: [_spell_box("earthquake", 80, 180)],
        21: [
            _spell_box("earthquake", 80, 180),
            _spell_box("poison", 210, 270, 0.85),
        ],
        22: [
            _spell_box("earthquake", 81, 180),
            _spell_box("earthquake", 211, 271, 0.95),
        ],
    }

    recovered, reason = module._recover_consistent_spell_location(
        event, detections, converter
    )

    assert reason is None
    assert recovered is not None
    assert recovered.support == 2
    assert 210 <= recovered.x <= 211
    assert 270 <= recovered.y <= 271


def test_persistent_area_spell_rejects_inconsistent_tiles() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    recovered, reason = module._recover_consistent_spell_location(
        UIPlayEvent(frame=20, card="earthquake"),
        {
            20: [],
            21: [_spell_box("earthquake", 80, 200)],
            22: [_spell_box("poison", 320, 400)],
        },
        converter,
    )

    assert recovered is None
    assert reason == "inconsistent_spell_visual_tiles"


def test_projectile_spell_visual_never_becomes_location_label() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json")
    recovered, reason = module._recover_consistent_spell_location(
        UIPlayEvent(frame=20, card="fireball"),
        {
            20: [],
            21: [_spell_box("fireball", 200, 500)],
            22: [_spell_box("fireball", 200, 500)],
        },
        converter,
    )

    assert recovered is None
    assert reason == "spell_visual_not_persistent_area"


def test_audit_saves_each_accepted_location_kind(tmp_path: Path) -> None:
    module = _module()
    frames = [10, 20, 21, 30, 31]
    crops = {
        frame: np.zeros((683, 428, 3), dtype=np.uint8) for frame in frames
    }
    states = {
        frame: module.UIFrameState(
            frame=frame,
            hand=("knight", "poison", "cannon", "ice_spirit"),
            elixir=5.0,
        )
        for frame in frames
    }
    locations = {
        20: module.RecoveredTVRoyaleLocation(100, 500, 0.9, 2),
        30: module.RecoveredTVRoyaleLocation(200, 200, 0.9, 2),
    }

    outputs = module._render_audit(
        tmp_path,
        crops,
        {frame: [] for frame in frames},
        {10: ["noop"], 20: ["location:knight@1"], 30: ["location:poison@2"]},
        states,
        locations,
        {20: "deployment-clock", 30: "persistent-area-center"},
        {20: 21, 30: 31},
        samples=1,
    )

    assert len(outputs) == 3
    assert any("frame_00020" in output for output in outputs)
    assert any("frame_00030" in output for output in outputs)


def test_public_state_v2_sidecar_is_aligned_and_confidence_aware() -> None:
    module = _module()
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=4)
    image = np.full((683, 428, 3), (65, 65, 80), dtype=np.uint8)
    image[100:108, 41:60] = (235, 190, 70)
    detections = {
        10: [
            TVRoyaleDetection("bar", 0, 0.95, 40, 99, 80, 109),
            TVRoyaleDetection("hog-rider", 0, 0.90, 42, 112, 78, 170),
        ]
    }
    state = module.UIFrameState(
        frame=10,
        hand=("hog_rider", "knight", "fireball", "cannon"),
        elixir=7.0,
    )

    payload, statistics = module._build_public_state_v2_sidecar(
        corpus_payload={
            "source_indices": np.asarray([3], dtype=np.int64),
            "source_frames": np.asarray([10], dtype=np.int64),
            "expert_actions": np.asarray([7], dtype=np.int64),
        },
        rows=[{"source_index": 3, "frame": 10}],
        converter=converter,
        state_by_frame={10: state},
        crops={10: image},
        detections=detections,
    )

    assert payload["schema_version"].item() == 2
    assert payload["source_indices"].tolist() == [3]
    assert payload["expert_actions"].tolist() == [7]
    assert payload["action_masks"].shape == (1, 2306)
    assert payload["action_masks"][0, 7]
    assert payload["action_masks"][0, 2304]
    hog_id = converter.builder.token_id("HogRider")
    hog_row = int(np.flatnonzero(payload["entity_ids"][0] == hog_id)[0])
    assert payload["entity_features"][0, hog_row, 9] == pytest.approx(
        0.5, abs=0.06
    )
    assert payload["entity_feature_confidence"][0, hog_row, 9] > 0.5
    assert statistics["entities_with_measured_hp"] == 1
    assert statistics["expert_mask_recoveries"] == 0
    assert statistics["label_conditioned_mask_mutations"] == 0
    assert payload["expert_action_masked"].shape == (1,)
    assert statistics["legacy_corpus_mutated"] is False
