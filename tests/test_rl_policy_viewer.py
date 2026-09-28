from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
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

    initial_tick = viewer.battle.tick
    viewer._advance_simulation(frame_seconds=1.0 / 60.0)
    viewer._advance_simulation(frame_seconds=1.0 / 60.0)
    assert viewer.battle.tick == initial_tick
    viewer._advance_simulation(frame_seconds=1.0 / 60.0)
    assert viewer.battle.tick == initial_tick + 1

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


def test_human_mode_queues_legal_actions_and_records_match(tmp_path: Path) -> None:
    pygame.init()
    root = Path(__file__).resolve().parents[1]
    record_out = tmp_path / "human-matches.jsonl"
    viewer = PolicyBattleVisualizer(
        checkpoint=str(root / "checkpoints/entity_selfplay/policy_v2_update_000140.pt"),
        decks_path=str(root / "decks.json"),
        decision_interval=8,
        device="cpu",
        deterministic=True,
        seed=23,
        human_player=0,
        record_out=str(record_out),
    )

    assert viewer.policies[0] is None
    assert viewer.policies[1] is not None
    assert viewer.human_controller is not None
    assert viewer.policy_identities[0] is None
    assert viewer.policy_identities[1] is not None
    assert viewer.speed == 1
    initial_human_hand = list(viewer.battle.players[0].hand)
    initial_candidate_hand = list(viewer.battle.players[1].hand)
    initial_human_queue = list(viewer.battle.players[0].cycle_queue)
    initial_candidate_queue = list(viewer.battle.players[1].cycle_queue)

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5))
    assert viewer.handle_events()
    assert viewer.speed == 1
    assert viewer.speed_index == 0

    viewer.draw_frame()
    previous_match = viewer.match_number
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    assert viewer.handle_events()
    assert viewer.match_number == previous_match
    assert viewer.human_controller.selected_slot == 3

    queued_action = None
    for slot in range(4):
        viewer.human_controller.select_slot(slot)
        legal = np.flatnonzero(viewer.human_controller.legal_tile_mask(viewer.battle))
        if legal.size:
            tile = int(legal[0])
            selection = viewer.action_space.decode_action(
                slot * 18 * 32 + tile, viewer.human_player
            )
            assert selection.position is not None
            assert viewer.human_controller.queue_world_tile(
                viewer.battle,
                int(selection.position.x),
                int(selection.position.y),
            )
            queued_action = viewer.human_controller.queued_action
            break
    assert queued_action is not None

    viewer.battle.tick = 8
    viewer._maybe_take_actions()
    assert viewer.previous_actions[0] == queued_action
    assert viewer.recurrent_states[1] is not None

    viewer.battle.game_over = True
    viewer.battle.winner = 1
    payload = viewer._record_completed_human_match()
    assert payload is not None
    assert payload["candidate_outcome"] == "win"
    assert payload["human_non_noop_actions"] == 1
    assert payload["pacing_mode"] == "wall_clock_logic_ticks"
    assert payload["speed_locked"] is True
    assert payload["logic_tick_seconds"] == 0.05
    written = json.loads(record_out.read_text(encoding="utf-8"))
    assert written["checkpoint_sha256"] == viewer.checkpoint_sha256
    assert viewer._record_completed_human_match() is None

    opposite_viewer = PolicyBattleVisualizer(
        checkpoint=str(root / "checkpoints/entity_selfplay/policy_v2_update_000140.pt"),
        decks_path=str(root / "decks.json"),
        decision_interval=8,
        device="cpu",
        deterministic=True,
        seed=23,
        human_player=1,
    )
    assert viewer.current_decks[0] == opposite_viewer.current_decks[1]
    assert viewer.current_decks[1] == opposite_viewer.current_decks[0]
    assert initial_human_hand == opposite_viewer.battle.players[1].hand
    assert initial_candidate_hand == opposite_viewer.battle.players[0].hand
    assert initial_human_queue == list(opposite_viewer.battle.players[1].cycle_queue)
    assert initial_candidate_queue == list(opposite_viewer.battle.players[0].cycle_queue)

    pygame.quit()
