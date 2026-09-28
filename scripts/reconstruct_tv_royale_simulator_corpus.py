# mypy: disable-error-code="import-untyped"
"""Rebuild TV Royale timing/card labels on simulator-native trajectories.

This intentionally does not claim to reconstruct the source match. The source
provides the lower player's public hand, elixir, play clock, and selected hand
slot. Clasher supplies a native board trajectory and a deterministic legal
placement for that selected card against a rotating public-information bot.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.deck_pool import (
    apply_deck_to_player,
    load_deck_pool,
    unique_cards_from_decks,
)
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.train_recurrent import _stack_step_inputs
from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter


def _manifest_decks(
    root: Path, importer: TVRoyalePlacementConverter
) -> dict[str, list[str]]:
    decks: dict[str, list[str]] = {}
    for path in sorted(root.glob("*/*/manifest.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        replay = str(payload.get("replay", ""))
        raw_deck = payload.get("deck", [])
        resolved = [importer.source_card_name(value) for value in raw_deck]
        deck = list(dict.fromkeys(str(card) for card in resolved if card is not None))
        if not replay or not deck:
            continue
        decks[replay] = deck
    return decks


def _names_for_ids(ids: np.ndarray, token_names: tuple[str, ...]) -> list[str | None]:
    return [
        None if int(token_id) == 0 else token_names[int(token_id)]
        for token_id in ids
    ]


def _sync_human_public_state(
    env: SelfPlayBattleEnv,
    *,
    hand_ids: np.ndarray,
    token_names: tuple[str, ...],
    deck: list[str],
    elixir: float,
) -> None:
    assert env.battle is not None
    player = env.battle.players[0]
    names = _names_for_ids(hand_ids, token_names)
    hand = names[:NUM_HAND_SLOTS]
    player.deck = list(deck)
    player.hand = list(hand)
    remaining = [card for card in deck if card not in {value for value in hand if value}]
    next_card = names[NUM_HAND_SLOTS]
    if next_card in remaining:
        remaining.remove(next_card)
        remaining.insert(0, str(next_card))
    player.cycle_queue = deque(remaining)
    player.next_card_refill_cooldown_ms = 0
    player.elixir = float(np.clip(elixir, 0.0, player.max_elixir))


def _forced_slot_action(
    *,
    slot: int,
    mask: np.ndarray,
    location_logits: np.ndarray,
) -> int | None:
    start = slot * NUM_TILES
    stop = start + NUM_TILES
    if not np.any(mask[start:stop]):
        return None
    legal = mask[start:stop]
    scores = np.asarray(location_logits[slot], dtype=np.float32)
    tile = int(np.argmax(np.where(legal, scores, -np.inf)))
    return int(start + tile)


def _placement_policy_step(
    loaded: LoadedPolicy,
    env: SelfPlayBattleEnv,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
) -> tuple[Any, tuple[torch.Tensor, torch.Tensor], Any]:
    assert env.battle is not None
    observation = loaded.builder.build(env.battle, 0)
    inputs = _stack_step_inputs(
        [observation],
        action_mask[None, :],
        np.asarray([previous_action]),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        policy_output = loaded.model(inputs, state)
    return observation, policy_output.next_state, policy_output


def _append_observation(
    output: dict[str, list[Any]],
    observation: Any,
    *,
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    expert_action: int,
    episode_id: int,
    replay: str,
    source_frame: int,
    source_action: int,
) -> None:
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    ):
        output[name].append(getattr(observation, name))
    output["action_masks"].append(action_mask)
    output["previous_actions"].append(previous_action)
    output["previous_rewards"].append(previous_reward)
    output["episode_starts"].append(episode_start)
    output["expert_actions"].append(expert_action)
    output["episode_ids"].append(episode_id)
    output["source_replays"].append(replay)
    output["source_frames"].append(source_frame)
    output["source_actions"].append(source_action)


def reconstruct_corpus(
    *,
    input_path: Path,
    manifest_root: Path,
    output_path: Path,
    report_path: Path,
    decks_path: Path,
    opponent_decks_path: Path | None,
    placement_checkpoint: Path,
    seed: int,
    max_replays: int | None,
) -> dict[str, Any]:
    with np.load(input_path, allow_pickle=False) as source:
        source_arrays = {name: source[name].copy() for name in source.files}
    source_metadata = json.loads(str(source_arrays["metadata_json"].item()))
    token_names = tuple(source_metadata["token_names"])
    max_entities = int(source_metadata["max_entities"])
    loaded = load_policy_checkpoint(
        placement_checkpoint,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    builder = loaded.builder
    if tuple(builder.token_names) != token_names or builder.max_entities != max_entities:
        raise ValueError("placement checkpoint observation schema differs from source")
    importer = TVRoyalePlacementConverter(
        decks_path=str(decks_path),
        max_entities=max_entities,
        token_names=token_names,
    )
    decks_by_replay = _manifest_decks(manifest_root, importer)
    vocabulary_decks = load_deck_pool(decks_path)
    fallback_cards = unique_cards_from_decks(vocabulary_decks)
    opponent_decks = (
        load_deck_pool(opponent_decks_path)
        if opponent_decks_path is not None
        else []
    )
    replays = np.asarray(source_arrays["source_replays"]).astype(str)
    frames = np.asarray(source_arrays["source_frames"], dtype=np.int64)
    source_actions = np.asarray(source_arrays["expert_actions"], dtype=np.int64)
    unique_replays = list(dict.fromkeys(replays.tolist()))
    if max_replays is not None:
        unique_replays = unique_replays[:max_replays]

    names = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
        "action_masks",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
        "expert_actions",
        "episode_ids",
        "source_replays",
        "source_frames",
        "source_actions",
    )
    output: dict[str, list[Any]] = {name: [] for name in names}
    no_op = NUM_HAND_SLOTS * NUM_TILES
    rng = random.Random(seed)
    opponent_rng = random.Random(seed ^ 0x5EED_C1A5)
    opponent_order = list(range(len(opponent_decks)))
    opponent_rng.shuffle(opponent_order)
    statistics: dict[str, int] = {
        "source_replays_requested": len(unique_replays),
        "replays_missing_deck": 0,
        "replays_completed": 0,
        "replays_truncated_by_game_end": 0,
        "source_rows": 0,
        "recorded_rows": 0,
        "recorded_plays": 0,
        "rows_without_legal_forced_slot": 0,
        "human_action_failures_after_legal_mask": 0,
        "hidden_clock_steps": 0,
        "public_state_syncs": 0,
    }

    episode_id = -1
    for replay_index, replay in enumerate(unique_replays):
        if (
            opponent_order
            and replay_index > 0
            and replay_index % len(opponent_order) == 0
        ):
            opponent_rng.shuffle(opponent_order)
        manifest_deck = decks_by_replay.get(replay, [])
        indices = np.flatnonzero(replays == replay)
        indices = indices[np.argsort(frames[indices], kind="stable")]
        observed_deck = list(
            dict.fromkeys(
                name
                for index in indices
                for name in _names_for_ids(
                    np.asarray(source_arrays["hand_ids"])[index, :NUM_HAND_SLOTS],
                    token_names,
                )
                if name is not None
            )
        )
        deck = list(dict.fromkeys([*observed_deck, *manifest_deck, *fallback_cards]))[
            :8
        ]
        if len(observed_deck) > 8 or len(deck) < 8:
            statistics["replays_missing_deck"] += 1
            continue
        statistics["source_rows"] += len(indices)
        if not len(indices):
            continue

        replay_seed = rng.randrange(2**31)
        env = SelfPlayBattleEnv(
            decision_interval_ticks=8,
            max_ticks=6000,
            decks_path=decks_path,
            seed=replay_seed,
            mirror_match=True,
            engine_fast_path="on",
            reward_profile=DEFENSE_V2,
        )
        env.reset()
        assert env.battle is not None
        env._structured_obs_builder = builder
        apply_deck_to_player(env.battle.players[0], deck, rng=env.rng)
        if opponent_order:
            opponent_deck = opponent_decks[
                opponent_order[replay_index % len(opponent_order)]
            ]
        else:
            opponent_deck = deck
        apply_deck_to_player(env.battle.players[1], opponent_deck, rng=env.rng)
        opponent = StrategyBot(STRATEGY_NAMES[(replay_index + 3) % len(STRATEGY_NAMES)])
        episode_id += 1
        previous_action = no_op
        previous_reward = 0.0
        episode_start = True
        placement_state = loaded.model.initial_state(1, device="cpu")
        next_frame = 0
        truncated = False

        for index in indices:
            target_frame = int(frames[index])
            while next_frame < target_frame:
                human_mask = env.get_action_mask(0)
                _, placement_state, _ = _placement_policy_step(
                    loaded,
                    env,
                    state=placement_state,
                    action_mask=human_mask,
                    previous_action=previous_action,
                    previous_reward=previous_reward,
                    episode_start=episode_start,
                )
                opponent_mask = env.get_action_mask(1)
                opponent_action = opponent.select_action(
                    env, 1, action_mask=opponent_mask
                )
                rewards, done, _ = env.step(
                    {0: no_op, 1: opponent_action},
                    pre_action_masks={0: env.get_action_mask(0), 1: opponent_mask},
                )
                previous_action = no_op
                previous_reward = float(rewards[0])
                episode_start = False
                next_frame += 4
                statistics["hidden_clock_steps"] += 1
                if done:
                    truncated = True
                    break
            if truncated:
                break

            _sync_human_public_state(
                env,
                hand_ids=np.asarray(source_arrays["hand_ids"])[index],
                token_names=token_names,
                deck=deck,
                elixir=float(source_arrays["global_features"][index, 5]) * 10.0,
            )
            statistics["public_state_syncs"] += 1
            human_mask = env.get_action_mask(0)
            observation, placement_state, policy_output = _placement_policy_step(
                loaded,
                env,
                state=placement_state,
                action_mask=human_mask,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
            )
            source_action = int(source_actions[index])
            if source_action == no_op:
                expert_action = no_op
            elif source_action < no_op:
                slot = source_action // NUM_TILES
                selected = _forced_slot_action(
                    slot=slot,
                    mask=human_mask,
                    location_logits=(
                        policy_output.location_logits[0, 0].detach().cpu().numpy()
                    ),
                )
                if selected is None:
                    statistics["rows_without_legal_forced_slot"] += 1
                    continue
                expert_action = selected
            else:
                expert_action = source_action
                if not human_mask[expert_action]:
                    statistics["rows_without_legal_forced_slot"] += 1
                    continue

            _append_observation(
                output,
                observation,
                action_mask=human_mask,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
                expert_action=expert_action,
                episode_id=episode_id,
                replay=replay,
                source_frame=target_frame,
                source_action=source_action,
            )
            statistics["recorded_rows"] += 1
            statistics["recorded_plays"] += int(expert_action < no_op)
            opponent_mask = env.get_action_mask(1)
            opponent_action = opponent.select_action(env, 1, action_mask=opponent_mask)
            rewards, done, info = env.step(
                {0: expert_action, 1: opponent_action},
                pre_action_masks={0: human_mask, 1: opponent_mask},
            )
            if expert_action != no_op and not info.action_success[0]:
                statistics["human_action_failures_after_legal_mask"] += 1
            previous_action = expert_action
            previous_reward = float(rewards[0])
            episode_start = False
            next_frame = max(next_frame, target_frame) + 4
            if done:
                truncated = True
                break

        if truncated:
            statistics["replays_truncated_by_game_end"] += 1
        else:
            statistics["replays_completed"] += 1

    if not output["expert_actions"]:
        raise ValueError("simulator reconstruction produced no rows")
    payload = {name: np.asarray(values) for name, values in output.items()}
    samples = len(payload["expert_actions"])
    legal = payload["action_masks"][np.arange(samples), payload["expert_actions"]]
    if not np.all(legal):
        raise RuntimeError("simulator reconstruction emitted an illegal expert action")
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        decisions=samples,
        samples=samples,
        decision_interval=8,
        max_ticks=6000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=max_entities,
        token_names=token_names,
        reward_profile=DEFENSE_V2,
        label_source="tv-royale-simulator-native-teacher-forcing-v1",
    )
    provenance = {
        "schema_version": 1,
        "source": str(input_path.resolve()),
        "source_sha256": file_sha256(input_path),
        "manifest_root": str(manifest_root.resolve()),
        "decks_path": str(decks_path.resolve()),
        "opponent_decks_path": (
            str(opponent_decks_path.resolve())
            if opponent_decks_path is not None
            else None
        ),
        "opponent_decks_sha256": (
            file_sha256(opponent_decks_path)
            if opponent_decks_path is not None
            else None
        ),
        "opponent_deck_mode": (
            "deterministic shuffled cycling" if opponent_order else "mirror"
        ),
        "placement_checkpoint": str(placement_checkpoint.resolve()),
        "placement_checkpoint_sha256": file_sha256(placement_checkpoint),
        "seed": seed,
        "max_replays": max_replays,
        "human_location_policy": "forced observed slot, checkpoint spatial argmax",
        "opponent_strategies": list(STRATEGY_NAMES),
        "claim": "native-state teacher forcing, not source-match reconstruction",
        "statistics": statistics,
    }
    atomic_save_npz(
        output_path,
        {
            **payload,
            "metadata_json": np.asarray(metadata.to_json()),
            "teacher_forcing_json": np.asarray(
                json.dumps(provenance, sort_keys=True, separators=(",", ":"))
            ),
        },
    )
    report = {
        **provenance,
        "output": str(output_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "expert_actions_all_legal": bool(np.all(legal)),
        "play_rate": float(np.mean(payload["expert_actions"] < no_op)),
    }
    atomic_write_json(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--manifest-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument(
        "--opponent-decks-path",
        type=Path,
        default=None,
        help=(
            "optional diverse opponent deck pool; decks are deterministically "
            "shuffled and cycled instead of mirroring the observed human deck"
        ),
    )
    parser.add_argument("--placement-checkpoint", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=1048201)
    parser.add_argument("--max-replays", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite an existing output or report")
    report = reconstruct_corpus(
        input_path=args.input,
        manifest_root=args.manifest_root,
        output_path=args.output,
        report_path=args.report,
        decks_path=args.decks_path,
        opponent_decks_path=args.opponent_decks_path,
        placement_checkpoint=args.placement_checkpoint,
        seed=args.seed,
        max_replays=args.max_replays,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
