from __future__ import annotations

from scripts.rerank_tv_royale_youtube_hud_by_visible_cost import _decision


def _cost(value: int) -> dict[str, object]:
    return {
        "value": value,
        "valid": True,
        "confidence": 1.0,
        "evidence": "current_frame_printed_card_cost",
    }


def test_cost_conditioning_reranks_only_within_visible_cost() -> None:
    decision = _decision(
        {
            "card_action:WrongFive": 0.90,
            "card_action:RightTwo": 0.84,
            "card_action:OtherTwo": 0.75,
        },
        _cost(2),
        {
            "card_action:WrongFive": 5,
            "card_action:RightTwo": 2,
            "card_action:OtherTwo": 2,
        },
        is_next=False,
        unsupported_families=set(),
    )

    assert decision["valid"] is True
    assert decision["value"] == "card_action:RightTwo"
    assert decision["displayed_cost"]["value"] == 2


def test_unsupported_current_client_variant_art_fails_closed() -> None:
    decision = _decision(
        {
            "card_action:Barbarians": 0.90,
            "card_action:Bats": 0.84,
            "card_action:BarbLog": 0.75,
        },
        _cost(2),
        {
            "card_action:Barbarians": 5,
            "card_action:Bats": 2,
            "card_action:BarbLog": 2,
        },
        is_next=False,
        unsupported_families={"card_action:Barbarians"},
    )

    assert decision["valid"] is False
    assert decision["value"] is None
    assert decision["candidate"] == "card_action:Bats"
    assert decision["reason"] == (
        "current_client_hero_or_variant_art_not_in_template_authority"
    )
