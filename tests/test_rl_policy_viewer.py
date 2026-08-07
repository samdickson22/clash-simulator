from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from clasher.rl.watch_policy_battle import (
    PolicyBattleVisualizer,
    card_abbreviation,
    format_match_clock,
    humanize_card_name,
)


def test_viewer_text_helpers() -> None:
    assert humanize_card_name("MegaKnight") == "Mega Knight"
    assert humanize_card_name("Archer_Queen") == "Archer Queen"
    assert humanize_card_name(None) == "Empty"
    assert card_abbreviation("ArcherQueen") == "AQ"
    assert card_abbreviation("MegaKnight") == "MK"
    assert card_abbreviation(None) == "--"

    assert format_match_clock(0.0) == "3:00"
    assert format_match_clock(60.0) == "2:00"
    assert format_match_clock(179.9) == "0:01"
    assert format_match_clock(180.0) == "OT 2:00"
    assert format_match_clock(299.5) == "OT 0:01"
    assert format_match_clock(300.0) == "OT 0:00"


def test_v2_viewer_headless_render_actions_and_reset() -> None:
    root = Path(__file__).resolve().parents[1]
    checkpoint = root / "checkpoints/entity_selfplay/policy_v2_update_000140.pt"
    viewer = PolicyBattleVisualizer(
        checkpoint=str(checkpoint),
        decks_path=str(root / "decks.json"),
        decision_interval=8,
        device="cpu",
        deterministic=True,
        seed=17,
    )

    assert viewer.policy_identities[0] is not None
    assert viewer.policy_identities[0].update == 140
    assert viewer.policies[0] is viewer.policies[1]
    assert viewer.episode_starts == {0: True, 1: True}
    assert viewer.show_targets

    viewer.battle.tick = 8
    viewer._maybe_take_actions()
    assert viewer.episode_starts == {0: False, 1: False}
    assert viewer.recurrent_states[0] is not None
    assert viewer.recurrent_states[1] is not None
    assert viewer.last_action_labels[0] != "Waiting for first decision"
    assert viewer.last_action_labels[1] != "Waiting for first decision"

    viewer.draw_frame()
    assert viewer.screen.get_size() == (1200, 900)

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    assert viewer.handle_events()
    assert not viewer.show_targets
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    assert viewer.handle_events()
    assert viewer.show_targets

    previous_match = viewer.match_number
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    assert viewer.handle_events()
    assert viewer.match_number == previous_match + 1
    assert viewer.episode_starts == {0: True, 1: True}
    assert viewer.battle.tick == 0

    viewer.auto_reset_seconds = 0.01
    viewer.battle.game_over = True
    viewer.game_over_since = time.monotonic() - 1.0
    previous_match = viewer.match_number
    viewer._maybe_auto_reset()
    assert viewer.match_number == previous_match + 1
    assert not viewer.battle.game_over

    pygame.quit()
