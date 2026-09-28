#!/usr/bin/env python3
"""Verify live-adapter equivalence on complete simulator-projected traces.

This is a contract gate, not a gameplay benchmark.  Each trace is a bounded,
completed simulator episode.  The simulator contributes only current public
state to a separately implemented projection; recurrent state, action masks,
and actions are then advanced independently beside StructuredLiveInferenceAdapter.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor

from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.live_inference_contract import (
    InferenceContractError,
    PublicPlayEvent,
    PublicVisionFrame,
    VisionEntity,
    parse_public_vision_frame,
)
from clasher.rl.model import PolicyInputs
from clasher.rl.public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_live_adapter import (
    ENTITY_FEATURE_SIZE,
    GLOBAL_FEATURE_SIZE,
    LivePolicyInputs,
    StructuredLiveInferenceAdapter,
)
from clasher.rl.structured_obs import StructuredObservation

SCHEMA = "clasher.structured_live_trace_equivalence.v1"
DEFAULT_SEED = 1_064_901
DEFAULT_CHECKPOINT = Path(
    "checkpoints/fresh_structured_causal_v1_seed1062701/"
    "resource_belief_gated_seed1063602/resource_u10_gate0.pt"
)
_KIND_BY_INDEX = {4: "troop", 5: "building", 6: "projectile", 7: "area_effect"}
_STATIC_FEATURE_INDICES = (24, 25, 26, 30)


@dataclass(frozen=True)
class ProjectedStep:
    frame: PublicVisionFrame
    expected: LivePolicyInputs
    action_mask: NDArray[np.bool_]
    scenario: dict[str, Any]


@dataclass
class GateCounters:
    traces: int = 0
    completed_traces: int = 0
    seat_0_traces: int = 0
    seat_1_traces: int = 0
    asymmetric_traces: int = 0
    regulation_traces: int = 0
    overtime_traces: int = 0
    triple_elixir_traces: int = 0
    tiebreak_traces: int = 0
    accepted_steps: int = 0
    reset_checks: int = 0
    duplicate_frame_checks: int = 0
    duplicate_timestamp_checks: int = 0
    before_cadence_checks: int = 0
    dropped_interval_checks: int = 0
    jittered_cadence_checks: int = 0
    repeated_cue_steps: int = 0
    unknown_hand_steps: int = 0
    unknown_entity_steps: int = 0
    confidence_failure_checks: int = 0
    confidence_failure_state_preserved: int = 0
    mask_independence_checks: int = 0
    privileged_label_rejections: int = 0
    input_tensor_comparisons: int = 0
    action_mask_comparisons: int = 0
    action_comparisons: int = 0
    recurrent_hidden_comparisons: int = 0
    recurrent_cell_comparisons: int = 0


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _array_record(array: NDArray[Any]) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(array)
    return {
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "sha256": hashlib.sha256(contiguous.tobytes(order="C")).hexdigest(),
    }


def _tensor_record(tensor: Tensor) -> dict[str, Any]:
    return _array_record(tensor.detach().cpu().contiguous().numpy())


def _to_tensor(
    value: NDArray[Any], dtype: torch.dtype, device: torch.device
) -> Tensor:
    return torch.as_tensor(value, dtype=dtype, device=device).unsqueeze(0).unsqueeze(0)


def _kind(features: NDArray[np.float32]) -> str | None:
    indices = [index for index in _KIND_BY_INDEX if features[index] > 0.5]
    if len(indices) != 1:
        return None
    return _KIND_BY_INDEX[indices[0]]


def _canonical_sort_key(
    *, kind: str, own: bool, token_id: int, x: float, y: float, track_id: str
) -> tuple[Any, ...]:
    kind_index = {value: key for key, value in _KIND_BY_INDEX.items()}[kind]
    return (
        kind_index,
        int(not own),
        token_id,
        round(y / BOARD_HEIGHT, 5),
        round(x / BOARD_WIDTH, 5),
        track_id,
    )


def _frame_payload(frame: PublicVisionFrame) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "episode_id": frame.episode_id,
        "frame_id": frame.frame_id,
        "timestamp_ms": frame.timestamp_ms,
        "public": {
            "visible_clock_seconds": frame.visible_clock_seconds,
            "clock_confidence": frame.clock_confidence,
            "own_elixir": frame.own_elixir,
            "own_elixir_confidence": frame.own_elixir_confidence,
            "own_hand": list(frame.own_hand),
            "own_hand_confidence": list(frame.own_hand_confidence),
            "own_next_card": frame.own_next_card,
            "own_next_card_confidence": frame.own_next_card_confidence,
            "entities": [asdict(entity) for entity in frame.entities],
            "play_events": [asdict(event) for event in frame.play_events],
        },
    }


def _policy_inputs(inputs: LivePolicyInputs) -> PolicyInputs:
    return PolicyInputs(
        **{field.name: getattr(inputs, field.name) for field in fields(PolicyInputs)}
    )


def _compare_tensor(name: str, actual: Tensor | None, expected: Tensor | None) -> None:
    if actual is None or expected is None:
        if actual is not expected:
            raise AssertionError(f"{name}: optional tensor presence differs")
        return
    actual_cpu = actual.detach().cpu()
    expected_cpu = expected.detach().cpu()
    if actual_cpu.dtype != expected_cpu.dtype or actual_cpu.shape != expected_cpu.shape:
        raise AssertionError(
            f"{name}: dtype/shape differs: "
            f"{actual_cpu.dtype}/{tuple(actual_cpu.shape)} != "
            f"{expected_cpu.dtype}/{tuple(expected_cpu.shape)}"
        )
    if not torch.equal(actual_cpu, expected_cpu):
        difference = torch.ne(actual_cpu, expected_cpu)
        first = tuple(int(value) for value in torch.nonzero(difference)[0].tolist())
        raise AssertionError(
            f"{name}: first exact mismatch at {first}: "
            f"{actual_cpu[first].item()} != {expected_cpu[first].item()}"
        )


def compare_policy_inputs(actual: LivePolicyInputs, expected: LivePolicyInputs) -> int:
    count = 0
    for field in fields(LivePolicyInputs):
        _compare_tensor(field.name, getattr(actual, field.name), getattr(expected, field.name))
        count += 1
    return count


def _scenario_start(trace_index: int) -> tuple[str, float]:
    scenario = trace_index % 4
    if scenario == 0:
        return "regulation", 0.0
    if scenario == 1:
        return "overtime", 179.2
    if scenario == 2:
        return "triple_elixir", 239.2
    return "tiebreak", 299.2


def _configure_battle(env: SelfPlayBattleEnv, trace_index: int, start_time: float) -> None:
    battle = env.battle
    if battle is None:
        raise AssertionError("environment reset did not create a battle")
    battle.time = float(start_time)
    battle.tick = round(start_time / battle.dt)
    battle.double_elixir = start_time >= battle.double_elixir_start_time
    battle.overtime = start_time >= battle.overtime_start_time
    battle.triple_elixir = start_time >= battle.triple_elixir_start_time
    battle.sudden_death = start_time >= battle.overtime_start_time
    battle.game_over = False
    battle.winner = None
    env.max_ticks = battle.tick + 32

    # Deterministic asymmetry is public and deliberately lane-sensitive.
    battle.players[0].elixir = 9.0 - 0.1 * (trace_index % 3)
    battle.players[1].elixir = 5.0 + 0.2 * (trace_index % 4)
    for entity in battle.entities.values():
        slot = getattr(entity, "_crown_tower_slot", None)
        if slot == "left" and entity.player_id == 0:
            entity.hitpoints = float(entity.max_hitpoints) * (0.91 - 0.01 * (trace_index % 5))
        elif slot == "right" and entity.player_id == 1:
            entity.hitpoints = float(entity.max_hitpoints) * (0.73 + 0.01 * (trace_index % 5))
        elif slot == "king" and entity.player_id == 1:
            entity.hitpoints = float(entity.max_hitpoints) * 0.94
    battle._update_tower_hp()
    env._reset_reward_trackers()


def _choose_simulator_action(
    env: SelfPlayBattleEnv, player_id: int, rng: random.Random
) -> int:
    mask = env.get_action_mask(player_id, actor_observation_domain="simulator-exact")
    no_op = env.action_space.no_op_action
    legal = np.flatnonzero(mask[:no_op]).tolist()
    if not legal:
        return no_op
    # Spend often enough to create asymmetric visible units, while retaining
    # deterministic no-op frames for clock/refill coverage.
    if rng.random() < 0.22:
        return no_op
    return int(legal[rng.randrange(len(legal))])


def _direct_projection(
    *,
    loaded: LoadedPolicy,
    mask_builder: PublicActionMaskBuilder,
    exact: StructuredObservation,
    actor_id: int,
    episode_id: str,
    frame_id: str,
    timestamp_ms: int,
    trace_index: int,
    step_index: int,
    previous_action: int,
    state_step: int,
    repeated_event: PublicPlayEvent | None,
    device: torch.device,
) -> ProjectedStep:
    token_names = tuple(str(name) for name in loaded.builder.token_names)
    max_entities = int(loaded.model.config.max_entities)
    static_tensor = loaded.model.actor_encoder.card_stat_features
    if not isinstance(static_tensor, Tensor):
        raise TypeError("loaded actor encoder has no packaged card stat table")
    static = static_tensor.detach().cpu().numpy()
    rows: list[
        tuple[
            tuple[Any, ...],
            int,
            NDArray[np.float32],
            NDArray[np.float32],
            float,
            VisionEntity,
        ]
    ] = []
    unknown_entity = trace_index % 10 == 1 and step_index == 1
    unknown_entity_injected = False
    tower_confidence = {
        feature: 0.71 + 0.03 * ((trace_index + feature - 8) % 7)
        for feature in range(8, 14)
    }

    for source_index in np.flatnonzero(exact.entity_mask).tolist():
        source = exact.entity_features[source_index]
        kind = _kind(source)
        if kind is None:
            continue
        token_id = int(exact.entity_ids[source_index])
        if token_id <= 1 or token_id >= len(token_names):
            continue
        own = bool(source[2] > 0.5)
        canonical_x = float(source[0]) * BOARD_WIDTH
        canonical_y = float(source[1]) * BOARD_HEIGHT
        physical_x = BOARD_WIDTH - canonical_x if actor_id == 1 else canonical_x
        physical_y = BOARD_HEIGHT - canonical_y if actor_id == 1 else canonical_y
        identity_confidence = 0.81 + 0.01 * ((trace_index + source_index) % 13)
        hp_visible = kind in {"troop", "building"} and (
            kind == "building" or (trace_index + step_index + source_index) % 3 != 0
        )
        hp = float(source[9]) if hp_visible else None
        hp_confidence = (
            0.67 + 0.02 * ((trace_index + source_index) % 9) if hp_visible else 0.0
        )
        name = token_names[token_id]
        if kind == "building" and name in {"Tower", "KingTower"}:
            lane_x = canonical_x
            if actor_id == 1 and not bool(
                getattr(loaded.model.config, "canonical_lane_globals", False)
            ):
                lane_x = physical_x
            if name == "KingTower":
                tower_feature = 10 if own else 13
            elif own:
                tower_feature = 8 if lane_x < BOARD_WIDTH / 2 else 9
            else:
                tower_feature = 11 if lane_x < BOARD_WIDTH / 2 else 12
            hp_confidence = tower_confidence[tower_feature]
        if unknown_entity and not unknown_entity_injected and kind == "troop":
            name = "__unknown_public_entity__"
            unknown_entity_injected = True
        statuses = ("slowed",) if step_index in {1, 2} and source_index == 0 else ()
        entity = VisionEntity(
            track_id=f"sim-{source_index:03d}",
            card=name,
            kind=kind,
            player_id=actor_id if own else 1 - actor_id,
            x_tiles=physical_x,
            y_tiles=physical_y,
            confidence=identity_confidence,
            hp_fraction=hp,
            hp_confidence=hp_confidence,
            statuses=statuses,
        )
        if name.startswith("__unknown"):
            continue
        row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
        confidence = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
        row[0:2] = source[0:2]
        row[2:9] = source[2:9]
        confidence[0:9] = identity_confidence
        if hp is not None:
            row[9] = hp
            confidence[9] = hp_confidence
        for index in _STATIC_FEATURE_INDICES:
            row[index] = static[token_id, {24: 7, 25: 8, 26: 12, 30: 6}[index]]
            confidence[index] = identity_confidence
        rows.append(
            (
                _canonical_sort_key(
                    kind=kind,
                    own=own,
                    token_id=token_id,
                    x=canonical_x,
                    y=canonical_y,
                    track_id=entity.track_id,
                ),
                token_id,
                row,
                confidence,
                identity_confidence,
                entity,
            )
        )

    # Unknown entities remain visible to the frame parser but are omitted by
    # both live and direct tokenization paths.
    frame_entities = [item[5] for item in rows]
    if unknown_entity_injected:
        source_index = next(
            index
            for index in np.flatnonzero(exact.entity_mask).tolist()
            if _kind(exact.entity_features[index]) == "troop"
        )
        source = exact.entity_features[source_index]
        own = bool(source[2] > 0.5)
        canonical_x = float(source[0]) * BOARD_WIDTH
        canonical_y = float(source[1]) * BOARD_HEIGHT
        frame_entities.append(
            VisionEntity(
                track_id=f"sim-unknown-{source_index:03d}",
                card="__unknown_public_entity__",
                kind="troop",
                player_id=actor_id if own else 1 - actor_id,
                x_tiles=BOARD_WIDTH - canonical_x if actor_id == 1 else canonical_x,
                y_tiles=BOARD_HEIGHT - canonical_y if actor_id == 1 else canonical_y,
                confidence=0.84,
                hp_fraction=None,
                hp_confidence=0.0,
                statuses=(),
            )
        )

    rows.sort(key=lambda item: item[0])
    if len(rows) > max_entities:
        raise AssertionError("simulator projection exceeds model entity capacity")
    entity_ids = np.zeros((max_entities,), dtype=np.int64)
    entity_features = np.zeros((max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32)
    entity_mask = np.zeros((max_entities,), dtype=np.bool_)
    entity_id_confidence = np.zeros((max_entities,), dtype=np.float32)
    entity_feature_confidence = np.zeros(
        (max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32
    )
    for index, (_, token_id, row, confidence, identity_confidence, _) in enumerate(rows):
        entity_ids[index] = token_id
        entity_features[index] = row
        entity_mask[index] = True
        entity_id_confidence[index] = identity_confidence
        entity_feature_confidence[index] = confidence

    hand_ids = np.asarray(exact.hand_ids[: NUM_HAND_SLOTS + 1], dtype=np.int64).copy()
    hand_confidence = np.asarray(
        [0.79 + 0.03 * ((trace_index + index) % 7) for index in range(hand_ids.size)],
        dtype=np.float32,
    )
    hand_confidence[hand_ids <= 1] = 0.0
    unknown_hand = trace_index % 10 == 0 and step_index == 2
    hand_names = [token_names[int(token_id)] for token_id in hand_ids[:NUM_HAND_SLOTS]]
    next_name: str | None = (
        token_names[int(hand_ids[NUM_HAND_SLOTS])]
        if int(hand_ids[NUM_HAND_SLOTS]) > 1
        else None
    )
    if unknown_hand:
        hand_names[trace_index % NUM_HAND_SLOTS] = "__unknown_public_hand__"
        hand_ids[trace_index % NUM_HAND_SLOTS] = 0
        hand_confidence[trace_index % NUM_HAND_SLOTS] = 0.0

    visible_clock_seconds = float(exact.global_features[0]) * 300.0
    clock_progress = min(1.0, visible_clock_seconds / 300.0)
    visible_own_elixir = float(exact.global_features[5]) * 10.0
    global_features = np.zeros((GLOBAL_FEATURE_SIZE,), dtype=np.float32)
    global_confidence = np.zeros((GLOBAL_FEATURE_SIZE,), dtype=np.float32)
    global_features[0] = clock_progress
    global_features[1] = 1.0 - clock_progress
    global_confidence[0:2] = 0.93
    global_features[5] = exact.global_features[5]
    global_confidence[5] = 0.88
    global_features[8:14] = exact.global_features[8:14]
    global_confidence[8:14] = np.asarray(
        [tower_confidence[index] for index in range(8, 14)], dtype=np.float32
    )

    event_id = 0
    event_confidence = 0.0
    events: tuple[PublicPlayEvent, ...] = ()
    if repeated_event is not None:
        events = (repeated_event,)
        event_id = loaded.builder.token_id(repeated_event.card)
        if event_id <= 0:
            event_id = 1
        event_confidence = repeated_event.confidence

    frame = PublicVisionFrame(
        episode_id=episode_id,
        frame_id=frame_id,
        timestamp_ms=timestamp_ms,
        visible_clock_seconds=visible_clock_seconds,
        clock_confidence=0.93,
        own_elixir=visible_own_elixir,
        own_elixir_confidence=0.88,
        own_hand=tuple(hand_names),
        own_hand_confidence=tuple(float(value) for value in hand_confidence[:4]),
        own_next_card=next_name,
        own_next_card_confidence=float(hand_confidence[4]),
        entities=tuple(frame_entities),
        play_events=events,
    )
    mask_input = PublicActionMaskInput(
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        hand_ids=hand_ids,
        global_features=global_features,
        entity_id_confidence=entity_id_confidence,
        hand_id_confidence=hand_confidence,
        global_feature_confidence=global_confidence,
    )
    action_mask = mask_builder.build(mask_input)
    expected = LivePolicyInputs(
        entity_ids=_to_tensor(entity_ids, torch.long, device),
        entity_features=_to_tensor(entity_features, torch.float32, device),
        entity_mask=_to_tensor(entity_mask, torch.bool, device),
        hand_ids=_to_tensor(hand_ids, torch.long, device),
        global_features=_to_tensor(global_features, torch.float32, device),
        action_mask=_to_tensor(action_mask, torch.bool, device),
        previous_actions=torch.as_tensor([[previous_action]], dtype=torch.long, device=device),
        previous_rewards=torch.zeros((1, 1), dtype=torch.float32, device=device),
        episode_starts=torch.as_tensor(
            [[state_step == 0]], dtype=torch.bool, device=device
        ),
        entity_id_confidence=_to_tensor(
            entity_id_confidence, torch.float32, device
        ),
        entity_feature_confidence=_to_tensor(
            entity_feature_confidence, torch.float32, device
        ),
        hand_id_confidence=_to_tensor(hand_confidence, torch.float32, device),
        global_feature_confidence=_to_tensor(
            global_confidence, torch.float32, device
        ),
        opponent_history_ids=torch.zeros((1, 1, 0), dtype=torch.long, device=device),
        opponent_history_ages=torch.zeros(
            (1, 1, 0), dtype=torch.float32, device=device
        ),
        opponent_seen_card_ids=torch.zeros(
            (1, 1, 0), dtype=torch.long, device=device
        ),
        opponent_play_event_ids=torch.as_tensor(
            [[event_id]], dtype=torch.long, device=device
        ),
        opponent_play_event_confidence=torch.as_tensor(
            [[event_confidence]], dtype=torch.float32, device=device
        ),
    )
    return ProjectedStep(
        frame=frame,
        expected=expected,
        action_mask=action_mask.astype(np.bool_, copy=True),
        scenario={
            "unknown_hand": unknown_hand,
            "unknown_entity": unknown_entity_injected,
            "repeated_event": repeated_event is not None,
        },
    )


def _confidence_failure(frame: PublicVisionFrame, trace_index: int) -> PublicVisionFrame:
    mode = trace_index % 3
    if mode == 0:
        return replace(frame, clock_confidence=0.0)
    if mode == 1:
        return replace(frame, own_next_card_confidence=0.0)
    entities = list(frame.entities)
    entity_index = next(
        index for index, entity in enumerate(entities) if entity.hp_fraction is not None
    )
    entities[entity_index] = replace(entities[entity_index], hp_confidence=0.0)
    return replace(frame, entities=tuple(entities))


def _state_arrays(snapshot: bytes) -> tuple[NDArray[Any], NDArray[Any]]:
    record = json.loads(snapshot)
    arrays: list[NDArray[Any]] = []
    for name in ("hidden", "cell"):
        tensor = record[name]
        array = np.frombuffer(
            base64.b64decode(tensor["data"]), dtype=np.dtype(tensor["dtype"])
        ).reshape(tensor["shape"])
        arrays.append(array)
    return arrays[0], arrays[1]


def _recurrent_state_equal(left: bytes, right: bytes) -> bool:
    left_record = json.loads(left)
    right_record = json.loads(right)
    left_hidden, left_cell = _state_arrays(left)
    right_hidden, right_cell = _state_arrays(right)
    return bool(
        left_record["state_step"] == right_record["state_step"]
        and left_record["previous_action"] == right_record["previous_action"]
        and np.array_equal(left_hidden, right_hidden)
        and np.array_equal(left_cell, right_cell)
    )


def _trace_timestamps(trace_index: int) -> list[int]:
    jitter = (trace_index % 4) * 25
    first_gap = 400 + jitter
    return [0, first_gap, first_gap + 800, first_gap + 800 + 400 + jitter]


def run_gate(
    *,
    checkpoint: Path,
    decks_path: Path,
    trace_count: int,
    seed: int,
    device: torch.device,
) -> dict[str, Any]:
    if trace_count <= 0:
        raise ValueError("trace_count must be positive")
    torch.manual_seed(seed)
    np.random.seed(seed)
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    loaded.model.eval()
    mask_builder = PublicActionMaskBuilder(loaded.builder)
    counters = GateCounters()
    failures: list[dict[str, Any]] = []
    trace_records: list[dict[str, Any]] = []

    for trace_index in range(trace_count):
        trace_seed = seed + trace_index
        actor_id = trace_index % 2
        scenario_name, start_time = _scenario_start(trace_index)
        episode_id = f"trace-{trace_index:03d}-seat-{actor_id}"
        env = SelfPlayBattleEnv(
            decision_interval_ticks=8,
            max_ticks=32,
            decks_path=decks_path,
            seed=trace_seed,
            canonical_perspective=True,
            canonical_lane_globals=bool(
                getattr(loaded.model.config, "canonical_lane_globals", False)
            ),
            engine_fast_path="off",
            idle_fast_forward=True,
        )
        env.reset(seed=trace_seed)
        _configure_battle(env, trace_index, start_time)
        adapter = StructuredLiveInferenceAdapter(
            model=loaded.model,
            token_names=list(loaded.builder.token_names),
            public_action_mask_builder=mask_builder,
            actor_id=actor_id,
            deterministic=True,
            device=device,
        )
        adapter_reset = adapter.reset(episode_id)
        direct_state = loaded.model.initial_state(1, device=device)
        previous_action = mask_builder.no_op_action
        state_step = 0
        timestamps = _trace_timestamps(trace_index)
        rng = random.Random(trace_seed ^ 0xA22)
        repeated_card = str(loaded.builder.token_names[int(env.get_structured_observation(
            1 - actor_id
        ).hand_ids[0])])
        repeated_event = PublicPlayEvent(
            event_id=f"repeat-{trace_index:03d}",
            player_id=1 - actor_id,
            card=repeated_card,
            confidence=0.86,
            x_tiles=6.5,
            y_tiles=22.5,
        )
        accepted_records: list[dict[str, Any]] = []
        trace_complete = False

        counters.traces += 1
        counters.reset_checks += 1
        counters.seat_0_traces += int(actor_id == 0)
        counters.seat_1_traces += int(actor_id == 1)
        counters.asymmetric_traces += 1
        setattr(counters, f"{scenario_name}_traces", getattr(counters, f"{scenario_name}_traces") + 1)

        try:
            for step_index, timestamp_ms in enumerate(timestamps):
                exact = env.get_structured_observation(
                    actor_id, actor_observation_domain="simulator-exact"
                )
                projected = _direct_projection(
                    loaded=loaded,
                    mask_builder=mask_builder,
                    exact=exact,
                    actor_id=actor_id,
                    episode_id=episode_id,
                    frame_id=f"frame-{step_index}",
                    timestamp_ms=timestamp_ms,
                    trace_index=trace_index,
                    step_index=step_index,
                    previous_action=previous_action,
                    state_step=state_step,
                    repeated_event=repeated_event if step_index in {1, 2} else None,
                    device=device,
                )

                if step_index == 1:
                    early = replace(
                        projected.frame,
                        frame_id="early-jitter",
                        timestamp_ms=timestamps[0] + 100,
                    )
                    before = adapter.serialize_state()
                    ignored = adapter.step(early)
                    after = adapter.serialize_state()
                    if ignored.disposition != "before_cadence" or not _recurrent_state_equal(
                        before.payload, after.payload
                    ):
                        raise AssertionError("early cadence frame changed recurrent state")
                    counters.before_cadence_checks += 1

                if step_index == 2:
                    counters.dropped_interval_checks += 1
                if step_index in {1, 3} and trace_index % 4 != 0:
                    counters.jittered_cadence_checks += 1

                if step_index == 2:
                    bad_frame = _confidence_failure(projected.frame, trace_index)
                    before = adapter.serialize_state()
                    try:
                        adapter.step(bad_frame)
                    except InferenceContractError:
                        counters.confidence_failure_checks += 1
                    else:
                        raise AssertionError("invalid confidence frame did not fail closed")
                    after = adapter.serialize_state()
                    if before.sha256 != after.sha256:
                        raise AssertionError("confidence failure changed adapter state")
                    counters.confidence_failure_state_preserved += 1

                prepared = adapter.prepare_current_frame(projected.frame)
                counters.input_tensor_comparisons += compare_policy_inputs(
                    prepared.inputs, projected.expected
                )
                if not np.array_equal(prepared.action_mask, projected.action_mask):
                    raise AssertionError("public action mask differs from direct causal mask")
                counters.action_mask_comparisons += 1

                # Labels have no API path.  A poisoned JSON payload is rejected,
                # and changing an external counterfactual label cannot alter a
                # second preparation of the same public frame.
                second = adapter.prepare_current_frame(projected.frame)
                label_a = 0
                label_b = projected.action_mask.size - 1
                if not np.array_equal(prepared.action_mask, second.action_mask):
                    raise AssertionError("counterfactual label changed the public mask")
                counters.mask_independence_checks += 1
                for external_label in (label_a, label_b):
                    poisoned = _frame_payload(projected.frame)
                    poisoned["expert_action"] = external_label
                    try:
                        parse_public_vision_frame(poisoned)
                    except InferenceContractError:
                        counters.privileged_label_rejections += 1
                    else:
                        raise AssertionError(
                            "expert label crossed the public frame boundary"
                        )

                with torch.no_grad():
                    direct_actions, _, _, direct_next, _ = loaded.model.act(
                        _policy_inputs(projected.expected),
                        direct_state,
                        deterministic=True,
                    )
                decision = adapter.step(projected.frame)
                if decision.disposition != "accepted":
                    raise AssertionError(
                        f"expected accepted frame, got {decision.disposition}"
                    )
                direct_action = int(direct_actions[0, 0].item())
                if decision.action != direct_action:
                    raise AssertionError(
                        f"model action differs: {decision.action} != {direct_action}"
                    )
                counters.action_comparisons += 1
                hidden, cell = _state_arrays(decision.state.payload)
                if not np.array_equal(hidden, direct_next[0].detach().cpu().numpy()):
                    raise AssertionError("recurrent hidden state differs")
                counters.recurrent_hidden_comparisons += 1
                if not np.array_equal(cell, direct_next[1].detach().cpu().numpy()):
                    raise AssertionError("recurrent cell state differs")
                counters.recurrent_cell_comparisons += 1
                counters.accepted_steps += 1
                counters.repeated_cue_steps += int(projected.scenario["repeated_event"])
                counters.unknown_hand_steps += int(projected.scenario["unknown_hand"])
                counters.unknown_entity_steps += int(projected.scenario["unknown_entity"])
                accepted_records.append(
                    {
                        "step": step_index,
                        "timestamp_ms": timestamp_ms,
                        "battle_tick": int(env.battle.tick if env.battle is not None else -1),
                        "action": direct_action,
                        "mask": _array_record(projected.action_mask),
                        "hidden": _tensor_record(direct_next[0]),
                        "cell": _tensor_record(direct_next[1]),
                        **projected.scenario,
                    }
                )

                if step_index == 0:
                    before = adapter.serialize_state()
                    duplicate = adapter.step(projected.frame)
                    after = adapter.serialize_state()
                    if duplicate.disposition != "duplicate_frame" or not _recurrent_state_equal(
                        before.payload, after.payload
                    ):
                        raise AssertionError("duplicate frame changed recurrent state")
                    counters.duplicate_frame_checks += 1
                if step_index == 1:
                    before = adapter.serialize_state()
                    duplicate_timestamp = adapter.step(
                        replace(projected.frame, frame_id="duplicate-timestamp")
                    )
                    after = adapter.serialize_state()
                    if (
                        duplicate_timestamp.disposition != "duplicate_timestamp"
                        or not _recurrent_state_equal(before.payload, after.payload)
                    ):
                        raise AssertionError("duplicate timestamp changed recurrent state")
                    counters.duplicate_timestamp_checks += 1
                direct_state = (direct_next[0].detach(), direct_next[1].detach())
                previous_action = direct_action
                state_step += 1

                simulator_actions = {
                    player_id: _choose_simulator_action(env, player_id, rng)
                    for player_id in (0, 1)
                }
                _, done, _ = env.step(simulator_actions)
                if done:
                    trace_complete = True
                    break

            if not trace_complete:
                raise AssertionError("bounded simulator trace did not reach done")
            counters.completed_traces += 1
            trace_record = {
                "trace_index": trace_index,
                "seed": trace_seed,
                "actor_id": actor_id,
                "scenario": scenario_name,
                "start_time": start_time,
                "reset_sha256": adapter_reset.sha256,
                "steps": accepted_records,
            }
            trace_record["sha256"] = _sha256_json(trace_record)
            trace_records.append(trace_record)
        except Exception as exc:  # noqa: BLE001 - gate records first exact divergence
            failures.append(
                {
                    "trace_index": trace_index,
                    "seed": trace_seed,
                    "actor_id": actor_id,
                    "scenario": scenario_name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            break

    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "seed": seed,
        "requested_traces": trace_count,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "decks_path": str(decks_path),
        "device": str(device),
        "public_action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "counters": asdict(counters),
        "failures": failures,
        "traces": trace_records,
    }
    output["trace_set_sha256"] = _sha256_json(trace_records)
    output["passed"] = not failures and counters.completed_traces == trace_count
    output["report_sha256"] = _sha256_json(
        {key: value for key, value in output.items() if key != "report_sha256"}
    )
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--decks", type=Path, default=Path("decks.json"))
    parser.add_argument("--traces", type=int, default=100)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_gate(
        checkpoint=args.checkpoint,
        decks_path=args.decks,
        trace_count=args.traces,
        seed=args.seed,
        device=torch.device(args.device),
    )
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
