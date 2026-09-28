from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from clasher.rl.tv_royale_ui import (
    NEXT_CARD_ORIGIN,
    NEXT_CARD_SIZE,
    CardTemplate,
    TVRoyaleUIExtractor,
    UIFrameState,
    UIPlayEvent,
    _best_match,
    choose_sparse_noop_frames,
    infer_offline_next_card_labels,
)


def test_card_template_costs_come_from_authoritative_card_data(
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "templates"
    card_root = template_root / "cr_detection" / "cards"
    elixir_root = template_root / "cr_detection" / "elixir"
    card_root.mkdir(parents=True)
    elixir_root.mkdir(parents=True)
    card_image = np.full((81, 66, 3), (20, 80, 160), dtype=np.uint8)
    elixir_image = np.full((25, 30, 3), (80, 70, 130), dtype=np.uint8)
    # Cannon's upstream asset metadata is stale (1); Knight is the valid
    # control. Neither suffix may determine the runtime cost.
    assert cv2.imwrite(str(card_root / "cannon-1.png"), card_image)
    assert cv2.imwrite(str(card_root / "knight-3.png"), card_image)
    assert cv2.imwrite(str(elixir_root / "0.png"), elixir_image)
    converter = TVRoyalePlacementConverter(decks_path="decks.json", max_entities=8)

    extractor = TVRoyaleUIExtractor(
        template_root,
        card_cost_resolver=converter.source_card_cost,
    )

    assert extractor.cards["cannon"].cost == 3
    assert extractor.cards["knight"].cost == 3
    assert converter.source_card_cost("evo_cannon") == 3


def test_best_match_handles_zero_shear_without_empty_slice() -> None:
    query = np.zeros((12, 12, 3), dtype=np.uint8)
    query[3:8, 4:9] = 255
    score, name = _best_match(query, {"same": query.copy()}, shearing=(0, 0))
    assert name == "same"
    assert score == pytest.approx(1.0)


def test_sparse_noops_are_complete_and_far_from_plays() -> None:
    states = [
        UIFrameState(
            frame=frame,
            hand=("a", "b", "c", "d")
            if frame != 40
            else ("a", None, "c", "d"),
            elixir=5.0,
        )
        for frame in range(0, 101, 10)
    ]
    events = [UIPlayEvent(frame=20, card="a"), UIPlayEvent(frame=80, card="b")]
    assert choose_sparse_noop_frames(
        states,
        events,
        stride_frames=20,
        exclusion_frames=5,
        terminal_exclusion_frames=0,
    ) == [0, 60, 100]


def test_sparse_noop_parameters_fail_closed() -> None:
    with pytest.raises(ValueError, match="stride"):
        choose_sparse_noop_frames([], [], stride_frames=0)


def test_sparse_noops_exclude_terminal_overlay_window() -> None:
    states = [
        UIFrameState(frame=frame, hand=("a", "b", "c", "d"), elixir=5.0)
        for frame in range(0, 121, 20)
    ]
    assert choose_sparse_noop_frames(
        states, [], stride_frames=20, terminal_exclusion_frames=50
    ) == [0, 20, 40, 60]


def test_future_refill_is_offline_label_for_preplay_visible_next_only() -> None:
    states = [
        UIFrameState(
            frame=10,
            hand=("hog_rider", "log", "cannon", "musketeer"),
            elixir=8.0,
            hand_confidence=(0.9, 0.9, 0.9, 0.9),
            elixir_confidence=0.9,
        ),
        UIFrameState(
            frame=12,
            hand=("empty", "log", "cannon", "musketeer"),
            elixir=4.0,
            hand_confidence=(0.0, 0.9, 0.9, 0.9),
            elixir_confidence=0.8,
        ),
        UIFrameState(
            frame=18,
            hand=("fireball", "log", "cannon", "musketeer"),
            elixir=4.2,
            hand_confidence=(0.75, 0.9, 0.9, 0.9),
            elixir_confidence=0.8,
        ),
    ]
    events = [UIPlayEvent(frame=10, card="hog_rider", confidence=0.8)]

    labels = infer_offline_next_card_labels(states, events)

    assert len(labels) == 1
    assert labels[0].source_frame == 10
    assert labels[0].card == "fireball"
    assert labels[0].evidence_frame == 18
    assert labels[0].confidence == pytest.approx(0.75)
    # Future-derived truth is a label only; it is not written back into the
    # current-frame runtime state.
    assert states[0].next_card is None


def test_offline_next_label_fails_closed_when_played_slot_is_ambiguous() -> None:
    states = [
        UIFrameState(
            frame=10,
            hand=("skeletons", "skeletons", "log", "cannon"),
            elixir=8.0,
        ),
        UIFrameState(
            frame=15,
            hand=("fireball", "skeletons", "log", "cannon"),
            elixir=7.0,
        ),
    ]
    assert infer_offline_next_card_labels(
        states,
        [UIPlayEvent(frame=10, card="skeletons")],
    ) == []


def test_current_frame_next_icon_keeps_match_and_margin_confidence() -> None:
    first = np.zeros((81, 66, 3), dtype=np.uint8)
    first[8:60, 9:31] = (20, 180, 240)
    first[25:72, 35:61] = (220, 45, 70)
    second = np.zeros_like(first)
    second[5:45, 30:58] = (220, 220, 35)
    second[48:78, 4:30] = (25, 80, 200)
    deck = {
        "first": CardTemplate("first", 3, first, cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)),
        "second": CardTemplate(
            "second", 4, second, cv2.cvtColor(second, cv2.COLOR_BGR2GRAY)
        ),
    }
    image = np.zeros((960, 540, 3), dtype=np.uint8)
    x, y = NEXT_CARD_ORIGIN
    width, height = NEXT_CARD_SIZE
    image[y : y + height, x : x + width] = cv2.resize(
        first, NEXT_CARD_SIZE, interpolation=cv2.INTER_AREA
    )
    extractor = object.__new__(TVRoyaleUIExtractor)

    observation = extractor.next_card_observation(image, deck)

    assert observation is not None
    assert observation.card == "first"
    assert observation.match_score == pytest.approx(1.0)
    assert observation.match_score > observation.runner_up_score
    assert 0.0 < observation.confidence <= 1.0


def test_current_frame_next_icon_fails_closed_without_clear_margin() -> None:
    card = np.zeros((81, 66, 3), dtype=np.uint8)
    card[10:70, 12:54] = (40, 160, 230)
    template = CardTemplate("same", 3, card, cv2.cvtColor(card, cv2.COLOR_BGR2GRAY))
    image = np.zeros((960, 540, 3), dtype=np.uint8)
    x, y = NEXT_CARD_ORIGIN
    width, height = NEXT_CARD_SIZE
    image[y : y + height, x : x + width] = cv2.resize(
        card, NEXT_CARD_SIZE, interpolation=cv2.INTER_AREA
    )
    extractor = object.__new__(TVRoyaleUIExtractor)

    assert extractor.next_card_observation(
        image,
        {"same-a": template, "same-b": template},
    ) is None
