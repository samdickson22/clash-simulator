from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter

SPLIT_NAMES = ("train", "validation", "archetype_test", "chronology_test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Put sparse TV Royale labels on Clasher's fixed decision clock"
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--source-fps", type=float, default=10.0)
    parser.add_argument("--decision-seconds", type=float, default=0.4)
    parser.add_argument("--max-observation-staleness-seconds", type=float, default=2.0)
    return parser.parse_args()


def _metadata(value: np.ndarray) -> dict[str, Any]:
    result = json.loads(str(np.asarray(value).item()))
    if not isinstance(result, dict):
        raise TypeError("metadata_json must encode an object")
    return result


def _regen_period(seconds: float) -> float:
    if seconds >= 240.0:
        return 0.93
    if seconds >= 120.0:
        return 1.4
    return 2.8


def _advance_elixir(elixir: float, start_frame: int, end_frame: int, fps: float) -> float:
    if end_frame <= start_frame:
        return elixir
    current = float(start_frame) / fps
    end = float(end_frame) / fps
    value = float(elixir)
    for boundary in (120.0, 240.0, end):
        segment_end = min(end, boundary)
        if segment_end > current:
            value = min(10.0, value + (segment_end - current) / _regen_period(current))
            current = segment_end
        if current >= end:
            break
    return value


def _timing_globals(base: np.ndarray, *, frame: int, fps: float, elixir: float) -> np.ndarray:
    result: np.ndarray = np.asarray(base, dtype=np.float32).copy()
    seconds = max(0.0, float(frame) / fps)
    progress = float(np.clip(seconds / 300.0, 0.0, 1.0))
    result[0] = progress
    result[1] = 1.0 - progress
    result[2] = float(seconds >= 120.0)
    result[3] = float(seconds >= 240.0)
    result[4] = float(seconds >= 180.0)
    result[5] = float(np.clip(elixir / 10.0, 0.0, 1.0))
    return result


def _assign_play_steps(
    frames: np.ndarray,
    actions: np.ndarray,
    *,
    frame_stride: int,
    no_op_action: int,
) -> tuple[dict[int, int], int, int]:
    assigned: dict[int, int] = {}
    shifted = 0
    maximum_shift = 0
    for index in np.flatnonzero(actions != no_op_action):
        source_frame = int(frames[index])
        natural = int(math.ceil(source_frame / frame_stride) * frame_stride)
        target = natural
        while target in assigned:
            target += frame_stride
        assigned[target] = int(index)
        shift = target - natural
        shifted += int(shift > 0)
        maximum_shift = max(maximum_shift, shift)
    return assigned, shifted, maximum_shift


def _names_for_hand(hand_ids: np.ndarray, token_names: tuple[str, ...]) -> list[str | None]:
    return [
        None if int(token_id) == 0 else token_names[int(token_id)]
        for token_id in hand_ids[:NUM_HAND_SLOTS]
    ]


def _infer_next_cards(
    frames: np.ndarray,
    actions: np.ndarray,
    hand_ids: np.ndarray,
    *,
    no_op_action: int,
    maximum_transition_frames: int,
) -> dict[int, int]:
    inferred: dict[int, int] = {}
    for play_local in np.flatnonzero(actions != no_op_action):
        before = {int(value) for value in hand_ids[play_local, :NUM_HAND_SLOTS]}
        target_slot = int(actions[play_local]) // NUM_TILES
        target_card = int(hand_ids[play_local, target_slot])
        for later in range(int(play_local) + 1, len(frames)):
            if int(frames[later] - frames[play_local]) > maximum_transition_frames:
                break
            after = {int(value) for value in hand_ids[later, :NUM_HAND_SLOTS]}
            new_cards = after.difference(before)
            if len(new_cards) == 1 and target_card not in after:
                candidate = next(iter(new_cards))
                if candidate != 0:
                    inferred[int(play_local)] = candidate
                break
            if int(actions[later]) != no_op_action or len(new_cards) > 1:
                break
    return inferred


def _repair_visual_entity_features(
    entity_ids: np.ndarray,
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    *,
    speed_by_token: np.ndarray,
) -> np.ndarray:
    result: np.ndarray = np.asarray(entity_features).copy()
    valid = np.asarray(entity_mask, dtype=np.bool_)
    result[valid, 23] = speed_by_token[np.asarray(entity_ids, dtype=np.int64)[valid]]
    troops = valid & (result[:, 4] > 0.5)
    result[troops, 27] = 0.0
    result[troops, 28] = np.where(result[troops, 2] > 0.5, 1.0, -1.0)
    return result


def densify_split(
    input_path: Path,
    output_path: Path,
    *,
    decks_path: Path,
    source_fps: float,
    decision_seconds: float,
    max_observation_staleness_seconds: float,
) -> dict[str, Any]:
    with np.load(input_path, allow_pickle=False) as source:
        source_arrays = {name: np.asarray(source[name]) for name in source.files}
    metadata = _metadata(source_arrays["metadata_json"])
    token_names = tuple(str(name) for name in metadata["token_names"])
    converter = TVRoyalePlacementConverter(
        decks_path=str(decks_path),
        max_entities=int(metadata["max_entities"]),
        token_names=token_names,
        source_frame_hz=source_fps,
    )
    speed_by_token = np.zeros((len(token_names),), dtype=np.float32)
    for token_id, token_name in enumerate(token_names):
        if token_name.startswith("<"):
            continue
        stats = converter.builder.loader.get_card(token_name)
        speed = float(getattr(stats, "speed", 0.0) or 0.0)
        speed_by_token[token_id] = float(
            np.clip(math.log1p(abs(speed)) / math.log1p(1000.0), 0.0, 1.0)
        )
    frame_stride_float = source_fps * decision_seconds
    frame_stride = round(frame_stride_float)
    if frame_stride <= 0 or not math.isclose(
        frame_stride_float, frame_stride, abs_tol=1e-9
    ):
        raise ValueError("source FPS times decision seconds must be a positive integer")
    maximum_staleness_frames = round(source_fps * max_observation_staleness_seconds)
    if maximum_staleness_frames < 0:
        raise ValueError("maximum observation staleness must be non-negative")

    no_op_action = NUM_HAND_SLOTS * NUM_TILES
    output: dict[str, list[Any]] = {
        "entity_ids": [],
        "entity_features": [],
        "entity_mask": [],
        "hand_ids": [],
        "global_features": [],
        "action_masks": [],
        "previous_actions": [],
        "previous_rewards": [],
        "episode_starts": [],
        "expert_actions": [],
        "episode_ids": [],
        "source_replays": [],
        "source_frames": [],
        "source_arenas": [],
        "observation_source_frames": [],
    }
    source_rows = 0
    source_plays = 0
    shifted_plays = 0
    maximum_play_shift = 0
    exact_event_observations = 0
    inferred_next_card_plays = 0
    known_next_card_rows = 0
    skipped_stale_decisions = 0
    stale_observation_age: list[int] = []
    dense_episode_id = -1
    episode_ids = np.asarray(source_arrays["episode_ids"], dtype=np.int64)
    for episode_id in np.unique(episode_ids):
        episode_indices = np.flatnonzero(episode_ids == episode_id)
        order = np.argsort(
            np.asarray(source_arrays["source_frames"])[episode_indices],
            kind="stable",
        )
        episode_indices = episode_indices[order]
        frames = np.asarray(source_arrays["source_frames"])[episode_indices].astype(
            np.int64
        )
        actions = np.asarray(source_arrays["expert_actions"])[episode_indices].astype(
            np.int64
        )
        if np.any(frames[1:] < frames[:-1]):
            raise ValueError(f"episode {episode_id} source frames are not ordered")
        assigned, shifted, max_shift = _assign_play_steps(
            frames,
            actions,
            frame_stride=frame_stride,
            no_op_action=no_op_action,
        )
        episode_hand_ids = np.asarray(source_arrays["hand_ids"])[episode_indices]
        inferred_next_cards = _infer_next_cards(
            frames,
            actions,
            episode_hand_ids,
            no_op_action=no_op_action,
            maximum_transition_frames=round(source_fps * 4.0),
        )
        inferred_next_card_plays += len(inferred_next_cards)
        assigned_steps = sorted(assigned)
        source_rows += len(episode_indices)
        source_plays += int(np.count_nonzero(actions != no_op_action))
        shifted_plays += shifted
        maximum_play_shift = max(maximum_play_shift, max_shift)
        start_frame = int(math.floor(int(frames[0]) / frame_stride) * frame_stride)
        end_frame = max(
            int(math.ceil(int(frames[-1]) / frame_stride) * frame_stride),
            max(assigned, default=start_frame),
        )
        previous_action = no_op_action
        segment_open = False
        current_elixir = float(source_arrays["global_features"][episode_indices[0], 5]) * 10.0
        current_hand = np.asarray(source_arrays["hand_ids"][episode_indices[0]]).copy()
        last_frame = start_frame
        last_observation_local = -1
        for frame in range(start_frame, end_frame + 1, frame_stride):
            current_elixir = _advance_elixir(current_elixir, last_frame, frame, source_fps)
            eligible = np.flatnonzero(frames <= frame)
            if eligible.size == 0:
                observation_local = 0
            else:
                observation_local = int(eligible[-1])
                # A play shifted by a collision cannot influence an earlier
                # decision. Fall back until its assigned step arrives.
                while observation_local > 0:
                    source_action = int(actions[observation_local])
                    if source_action == no_op_action:
                        break
                    source_play_step = next(
                        key
                        for key, value in assigned.items()
                        if value == observation_local
                    )
                    if source_play_step <= frame:
                        break
                    observation_local -= 1
            action_local = assigned.get(frame)
            if action_local is not None:
                observation_local = action_local
                exact_event_observations += 1
            observation_index = int(episode_indices[observation_local])
            if observation_local != last_observation_local:
                current_elixir = (
                    float(source_arrays["global_features"][observation_index, 5]) * 10.0
                )
                current_hand = np.asarray(source_arrays["hand_ids"][observation_index]).copy()
                last_observation_local = observation_local

            observation_age = max(0, frame - int(frames[observation_local]))
            if action_local is None and observation_age > maximum_staleness_frames:
                skipped_stale_decisions += 1
                segment_open = False
                previous_action = no_op_action
                last_frame = frame
                continue
            episode_start = not segment_open
            if episode_start:
                dense_episode_id += 1
                segment_open = True

            expert_action = (
                no_op_action if action_local is None else int(actions[action_local])
            )
            current_hand[NUM_HAND_SLOTS] = 0
            upcoming_steps = [step for step in assigned_steps if step >= frame]
            if upcoming_steps:
                upcoming_local = assigned[upcoming_steps[0]]
                inferred_next = inferred_next_cards.get(upcoming_local)
                if inferred_next is not None:
                    current_hand[NUM_HAND_SLOTS] = inferred_next
            known_next_card_rows += int(current_hand[NUM_HAND_SLOTS] != 0)
            hand_names = _names_for_hand(current_hand, token_names)
            action_mask = converter._action_mask(hand_names, elixir=current_elixir)
            if not action_mask[expert_action]:
                raise ValueError(
                    f"episode {episode_id} frame {frame}: expert action {expert_action} "
                    "is illegal after dense clock reconstruction"
                )
            output["entity_ids"].append(source_arrays["entity_ids"][observation_index])
            output["entity_features"].append(
                _repair_visual_entity_features(
                    source_arrays["entity_ids"][observation_index],
                    source_arrays["entity_features"][observation_index],
                    source_arrays["entity_mask"][observation_index],
                    speed_by_token=speed_by_token,
                )
            )
            output["entity_mask"].append(source_arrays["entity_mask"][observation_index])
            output["hand_ids"].append(current_hand.copy())
            output["global_features"].append(
                _timing_globals(
                    source_arrays["global_features"][observation_index],
                    frame=frame,
                    fps=source_fps,
                    elixir=current_elixir,
                )
            )
            output["action_masks"].append(action_mask)
            output["previous_actions"].append(previous_action)
            output["previous_rewards"].append(0.0)
            output["episode_starts"].append(episode_start)
            output["expert_actions"].append(expert_action)
            output["episode_ids"].append(dense_episode_id)
            output["source_replays"].append(
                str(source_arrays["source_replays"][observation_index])
            )
            output["source_frames"].append(frame)
            output["source_arenas"].append(
                str(source_arrays["source_arenas"][observation_index])
            )
            output["observation_source_frames"].append(int(frames[observation_local]))
            stale_observation_age.append(observation_age)
            previous_action = expert_action
            if expert_action < no_op_action:
                slot = expert_action // NUM_TILES
                card_name = hand_names[slot]
                if card_name is None:
                    raise ValueError("play action selected an empty hand slot")
                stats = converter.builder.loader.get_card(card_name)
                current_elixir = max(
                    0.0,
                    current_elixir - float(getattr(stats, "mana_cost", 0.0) or 0.0),
                )
                current_hand[slot] = 0
            last_frame = frame

    payload: dict[str, np.ndarray] = {
        "entity_ids": np.stack(output["entity_ids"]),
        "entity_features": np.stack(output["entity_features"]),
        "entity_mask": np.stack(output["entity_mask"]),
        "hand_ids": np.stack(output["hand_ids"]),
        "global_features": np.stack(output["global_features"]),
        "action_masks": np.stack(output["action_masks"]),
        "previous_actions": np.asarray(output["previous_actions"], dtype=np.int64),
        "previous_rewards": np.asarray(output["previous_rewards"], dtype=np.float32),
        "episode_starts": np.asarray(output["episode_starts"], dtype=np.bool_),
        "expert_actions": np.asarray(output["expert_actions"], dtype=np.int64),
        "episode_ids": np.asarray(output["episode_ids"], dtype=np.int64),
        "source_replays": np.asarray(output["source_replays"], dtype=np.str_),
        "source_frames": np.asarray(output["source_frames"], dtype=np.int64),
        "source_arenas": np.asarray(output["source_arenas"], dtype=np.str_),
        "observation_source_frames": np.asarray(
            output["observation_source_frames"], dtype=np.int64
        ),
    }
    metadata["decisions"] = len(payload["expert_actions"])
    metadata["samples"] = len(payload["expert_actions"])
    metadata["decision_interval"] = round(decision_seconds / 0.05)
    metadata["label_source"] = f"{metadata['label_source']}-dense-clock-v1"
    dense_clock_provenance = {
        "source_fps": source_fps,
        "decision_seconds": decision_seconds,
        "frame_stride": frame_stride,
        "maximum_observation_staleness_seconds": max_observation_staleness_seconds,
        "maximum_observation_staleness_frames": maximum_staleness_frames,
        "state_fill": "latest-public-visual-observation",
        "elixir": "observed-resync-plus-official-phase-regen-and-known-spend",
        "post_play_hand_slot": "empty-until-next-observed-hand",
        "next_card_preview": (
            "strict-one-card-hand-transition-within-four-seconds-and-no-intervening-play"
        ),
        "visual_feature_repair": "live-speed-scaling-and-canonical-lane-facing-prior",
        "play_bucket": "ceil-with-greedy-collision-shift",
    }
    payload["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
    payload["dense_clock_json"] = np.asarray(
        json.dumps(dense_clock_provenance, sort_keys=True)
    )
    legal = payload["action_masks"][
        np.arange(len(payload["expert_actions"])), payload["expert_actions"]
    ]
    if not bool(np.all(legal)):
        raise AssertionError("dense corpus contains illegal expert actions")
    atomic_save_npz(output_path, payload)
    play_rate = float(np.mean(payload["expert_actions"] != no_op_action))
    return {
        "input": str(input_path),
        "input_sha256": file_sha256(input_path),
        "output": str(output_path),
        "output_sha256": file_sha256(output_path),
        "source_rows": source_rows,
        "source_plays": source_plays,
        "dense_rows": len(payload["expert_actions"]),
        "dense_play_rate": play_rate,
        "episodes": int(np.count_nonzero(payload["episode_starts"])),
        "shifted_collision_plays": shifted_plays,
        "maximum_play_shift_frames": maximum_play_shift,
        "exact_event_observations": exact_event_observations,
        "inferred_next_card_plays": inferred_next_card_plays,
        "inferred_next_card_play_coverage": (
            float(inferred_next_card_plays / source_plays) if source_plays else 0.0
        ),
        "known_next_card_row_rate": float(known_next_card_rows / len(payload["hand_ids"])),
        "skipped_stale_decisions": skipped_stale_decisions,
        "expert_actions_all_legal": bool(np.all(legal)),
        "observation_staleness_frames": {
            "mean": float(np.mean(stale_observation_age)),
            "median": float(np.median(stale_observation_age)),
            "p90": float(np.quantile(stale_observation_age, 0.9)),
            "maximum": int(max(stale_observation_age)),
        },
    }


def main() -> None:
    args = parse_args()
    if (
        args.source_fps <= 0.0
        or args.decision_seconds <= 0.0
        or args.max_observation_staleness_seconds < 0.0
    ):
        raise ValueError("clock rates must be positive")
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    decks_path = Path(args.decks_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    splits: dict[str, Any] = {}
    for split in SPLIT_NAMES:
        splits[split] = densify_split(
            input_dir / f"{split}.npz",
            output_dir / f"{split}.npz",
            decks_path=decks_path,
            source_fps=args.source_fps,
            decision_seconds=args.decision_seconds,
            max_observation_staleness_seconds=(
                args.max_observation_staleness_seconds
            ),
        )
    manifest = {
        "schema": "tv-royale-dense-decision-clock-v1",
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "decks_path": str(decks_path),
        "decks_sha256": file_sha256(decks_path),
        "source_fps": args.source_fps,
        "decision_seconds": args.decision_seconds,
        "maximum_observation_staleness_seconds": (
            args.max_observation_staleness_seconds
        ),
        "splits": splits,
    }
    manifest_path = Path(args.manifest_out).resolve()
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
