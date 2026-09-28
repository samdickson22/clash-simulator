from __future__ import annotations

from pathlib import Path

import cv2

from scripts.extract_tv_royale_youtube_hud_semantics import _semantics

ATLAS = Path(
    "reports/tv_royale_youtube_hud_semantics_atlas_hTG8dM4KtM4_20260817"
)


def _image(name: str):  # type: ignore[no-untyped-def]
    image = cv2.imread(str(ATLAS / name), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _head(candidate: str, cost: int) -> dict[str, object]:
    return {
        "candidate": candidate,
        "displayed_cost": {
            "value": cost,
            "valid": True,
            "confidence": 1.0,
        },
    }


def test_detects_evolution_ready_and_progress_separately() -> None:
    ready = _semantics(
        _image("t215000_p1_hand2.png"), _head("card_action:MiniSparkys", 4)
    )
    progress = _semantics(
        _image("t076800_p1_hand2.png"), _head("card_action:MiniSparkys", 4)
    )

    assert ready["variant_visual_state"]["value"] == "evolution_ready"
    assert ready["evolution_ready"]["value"] is True
    assert progress["variant_visual_state"]["value"] == "evolution_progress"
    assert progress["evolution_progress_diamonds"]["value"] == 2


def test_disabled_and_base_state_are_current_frame_visual_heads() -> None:
    disabled = _semantics(
        _image("t025800_p1_hand1.png"), _head("card_action:RoyalRecruits", 7)
    )
    ordinary = _semantics(
        _image("t025800_p1_hand0.png"), _head("card_action:Arrows", 3)
    )

    assert disabled["disabled_visual"]["value"] is True
    assert ordinary["disabled_visual"]["value"] is False
    assert ordinary["variant_visual_state"]["value"] == "base_or_ordinary"


def test_unproven_hero_art_never_becomes_exact_variant_identity() -> None:
    hero = _semantics(
        _image("t076800_p0_hand0.png"), _head("card_action:Barbarians", 2)
    )

    assert hero["variant_visual_state"]["candidate"] == "hero_variant"
    assert hero["variant_visual_state"]["valid"] is False
    assert hero["variant_visual_state"]["value"] is None
    assert hero["variant_visual_state"]["exact_card_identity_separate"] is True
