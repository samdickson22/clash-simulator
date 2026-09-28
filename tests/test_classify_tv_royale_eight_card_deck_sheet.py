from __future__ import annotations

from scripts.classify_tv_royale_eight_card_deck_sheet import auto_close_player


def test_auto_close_requires_eight_unique_strict_cards() -> None:
    rows = [
        {"identity": f"card_action:Card{index}", "auto_valid": True}
        for index in range(8)
    ]
    assert auto_close_player(rows)
    assert not auto_close_player(rows[:-1])
    rows[-1]["identity"] = rows[0]["identity"]
    assert not auto_close_player(rows)
    rows[-1]["identity"] = "card_action:Card7"
    rows[-1]["auto_valid"] = False
    assert not auto_close_player(rows)
