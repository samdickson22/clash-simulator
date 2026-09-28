from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.live_inference_contract import PublicVisionFrame, VisionEntity
from clasher.rl.public_action_mask import PublicActionMaskBuilder
from clasher.rl.structured_live_adapter import StructuredLiveInferenceAdapter
from scripts.verify_structured_live_trace_equivalence import (
    DEFAULT_CHECKPOINT,
    DEFAULT_SEED,
    run_gate,
)


def _asymmetric_tower_frame() -> PublicVisionFrame:
    rows = (
        ("p0-left", "Tower", 0, 3.5, 6.5, 0.43),
        ("p0-right", "Tower", 0, 14.5, 6.5, 0.74),
        ("p0-king", "KingTower", 0, 9.0, 2.5, 0.55),
        ("p1-left", "Tower", 1, 3.5, 25.5, 0.61),
        ("p1-right", "Tower", 1, 14.5, 25.5, 0.82),
        ("p1-king", "KingTower", 1, 9.0, 29.5, 0.93),
    )
    return PublicVisionFrame(
        episode_id="asymmetric-lanes",
        frame_id="frame-0",
        timestamp_ms=0,
        visible_clock_seconds=12.0,
        clock_confidence=1.0,
        own_elixir=7.0,
        own_elixir_confidence=1.0,
        own_hand=("Knight", "Archers", "Fireball", "HogRider"),
        own_hand_confidence=(1.0, 1.0, 1.0, 1.0),
        own_next_card="Skeletons",
        own_next_card_confidence=1.0,
        entities=tuple(
            VisionEntity(
                track_id=track_id,
                card=card,
                kind="building",
                player_id=player_id,
                x_tiles=x,
                y_tiles=y,
                confidence=1.0,
                hp_fraction=hp,
                hp_confidence=1.0,
            )
            for track_id, card, player_id, x, y, hp in rows
        ),
        play_events=(),
    )


@pytest.mark.parametrize(
    ("canonical_lane_globals", "expected"),
    (
        (False, [0.61, 0.82, 0.93, 0.43, 0.74, 0.55]),
        (True, [0.82, 0.61, 0.93, 0.74, 0.43, 0.55]),
    ),
)
def test_actor_one_tower_globals_follow_checkpoint_lane_contract(
    canonical_lane_globals: bool, expected: list[float]
) -> None:
    if not DEFAULT_CHECKPOINT.is_file():
        pytest.skip("accepted structured checkpoint is unavailable")
    loaded = load_policy_checkpoint(
        DEFAULT_CHECKPOINT, device=torch.device("cpu"), decks_path="decks.json"
    )
    model = copy.copy(loaded.model)
    model.config = replace(
        loaded.model.config, canonical_lane_globals=canonical_lane_globals
    )
    adapter = StructuredLiveInferenceAdapter(
        model=model,
        token_names=list(loaded.builder.token_names),
        public_action_mask_builder=PublicActionMaskBuilder(loaded.builder),
        actor_id=1,
        deterministic=True,
        device="cpu",
    )

    values, confidence, diagnostics = adapter._globals(_asymmetric_tower_frame())

    assert values[8:14].tolist() == pytest.approx(expected)
    assert confidence[8:14].tolist() == [1.0] * 6
    assert diagnostics["observed_tower_global_indices"] == list(range(8, 14))


def test_four_trace_smoke_covers_every_phase_and_both_seats() -> None:
    if not DEFAULT_CHECKPOINT.is_file():
        pytest.skip("accepted structured checkpoint is unavailable")
    result = run_gate(
        checkpoint=DEFAULT_CHECKPOINT,
        decks_path=Path("decks.json"),
        trace_count=4,
        seed=DEFAULT_SEED,
        device=torch.device("cpu"),
    )

    assert result["passed"] is True
    assert result["failures"] == []
    counters = result["counters"]
    assert counters["completed_traces"] == 4
    assert counters["seat_0_traces"] == counters["seat_1_traces"] == 2
    assert counters["regulation_traces"] == 1
    assert counters["overtime_traces"] == 1
    assert counters["triple_elixir_traces"] == 1
    assert counters["tiebreak_traces"] == 1
    assert counters["duplicate_frame_checks"] > 0
    assert counters["duplicate_timestamp_checks"] > 0
    assert counters["before_cadence_checks"] > 0
    assert counters["dropped_interval_checks"] > 0
    assert counters["repeated_cue_steps"] > 0
    assert counters["unknown_hand_steps"] > 0
    assert counters["unknown_entity_steps"] > 0
    assert counters["confidence_failure_checks"] > 0
    assert counters["mask_independence_checks"] == counters["accepted_steps"]
    assert counters["action_comparisons"] == counters["accepted_steps"]
    assert counters["recurrent_hidden_comparisons"] == counters["accepted_steps"]
    assert counters["recurrent_cell_comparisons"] == counters["accepted_steps"]
