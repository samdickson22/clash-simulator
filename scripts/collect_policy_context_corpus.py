#!/usr/bin/env python3
# mypy: disable-error-code="import-untyped"
"""Collect ordinary public Hog trajectories labeled by a frozen policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import _policy_step, load_policy_checkpoint
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import (
    STRATEGY_NAMES,
    BalancedStrategyConfig,
    StrategyBot,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save(path: Path, values: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **values)  # type: ignore[arg-type]
    temporary.replace(path)


def _component_supervision(
    *,
    expert_action: int,
    behavior_action: int,
    no_op_action: int,
    execute_policy_behavior: bool,
    trust_off_policy_teacher_spatial: bool = False,
) -> tuple[bool, bool, bool]:
    """Trust card/tile labels only at behavior-aligned play decisions."""

    expert_placement = expert_action < no_op_action
    behavior_placement = behavior_action < no_op_action
    spatial = expert_placement and (
        trust_off_policy_teacher_spatial
        or not execute_policy_behavior
        or behavior_placement
    )
    return True, spatial, spatial


def _contains_unknown_hand_token(hand_ids: np.ndarray) -> bool:
    """Empty slot zero is public and valid; token one is an unknown identity."""

    return bool(np.any(hand_ids[:NUM_HAND_SLOTS] == 1))


def collect(
    *,
    checkpoint: Path,
    decks_path: Path,
    learner_decks_path: Path,
    opponent_decks_path: Path,
    games: int,
    seed: int,
    corpus_path: Path,
    sidecar_path: Path,
    manifest_path: Path,
    teacher_strategy: str | None = None,
    teacher_checkpoint: Path | None = None,
    teacher_balanced_config: BalancedStrategyConfig | None = None,
    execute_policy_behavior: bool = False,
    trust_off_policy_teacher_spatial: bool = False,
) -> dict[str, Any]:
    if games <= 0:
        raise ValueError("games must be positive")
    if teacher_strategy is not None and teacher_checkpoint is not None:
        raise ValueError("use only one strategy or checkpoint teacher")
    if execute_policy_behavior and (
        teacher_strategy is None and teacher_checkpoint is None
    ):
        raise ValueError("policy behavior collection requires a teacher")
    if trust_off_policy_teacher_spatial and (
        teacher_checkpoint is None or not execute_policy_behavior
    ):
        raise ValueError(
            "off-policy spatial trust requires checkpoint-labeled policy behavior"
        )
    loaded = load_policy_checkpoint(
        checkpoint, device=torch.device("cpu"), decks_path=decks_path
    )
    actor_domain = loaded.model.config.actor_observation_domain
    if actor_domain not in {"causal-vision-v1", "causal-frame-v1"}:
        raise ValueError("policy context collection requires causal actor domain")
    checkpoint_teacher = (
        load_policy_checkpoint(
            teacher_checkpoint,
            device=torch.device("cpu"),
            decks_path=decks_path,
        )
        if teacher_checkpoint is not None
        else None
    )
    if checkpoint_teacher is not None:
        teacher_config = checkpoint_teacher.model.config
        if teacher_config.actor_observation_domain != actor_domain:
            raise ValueError("behavior and checkpoint teacher actor domains differ")
        if teacher_config.canonical_lane_globals != (
            loaded.model.config.canonical_lane_globals
        ):
            raise ValueError("behavior and checkpoint teacher lane contracts differ")
        if tuple(checkpoint_teacher.builder.token_names) != tuple(
            loaded.builder.token_names
        ):
            raise ValueError("behavior and checkpoint teacher vocabularies differ")
    rows: dict[str, list[np.ndarray | int | float | bool]] = {
        name: []
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_ids",
            "hand_id_confidence",
            "global_features",
            "global_feature_confidence",
            "action_masks",
            "previous_actions",
            "previous_rewards",
            "episode_starts",
            "expert_actions",
            "expert_action_supervision_valid",
            "expert_card_supervision_valid",
            "expert_tile_supervision_valid",
            "episode_ids",
            "source_frames",
        )
    }
    episode_summaries: list[dict[str, Any]] = []
    no_op = NUM_HAND_SLOTS * NUM_TILES
    for game in range(games):
        game_seed = seed + game * 1009
        learner = game % 2
        player_paths = (
            (learner_decks_path, opponent_decks_path)
            if learner == 0
            else (opponent_decks_path, learner_decks_path)
        )
        env = SelfPlayBattleEnv(
            decision_interval_ticks=8,
            max_ticks=6000,
            decks_path=decks_path,
            sampling_decks_path=opponent_decks_path,
            player0_sampling_decks_path=player_paths[0],
            player1_sampling_decks_path=player_paths[1],
            learner_player_id=learner,
            seed=game_seed,
            canonical_perspective=True,
            canonical_lane_globals=loaded.model.config.canonical_lane_globals,
            engine_fast_path="on",
            reward_profile="objective-v1",
        )
        env._structured_obs_builder = loaded.builder
        env.reset(seed=game_seed)
        assert env.battle is not None
        unknown_deck_cards = sorted(
            {
                card
                for player in env.battle.players
                for card in player.deck
                if loaded.builder.token_id(card) <= 1
            }
        )
        if unknown_deck_cards:
            raise ValueError(
                "policy-context deck cards are outside the policy vocabulary: "
                f"{unknown_deck_cards}"
            )
        opponent = 1 - learner
        opponent_bot = StrategyBot(STRATEGY_NAMES[game % len(STRATEGY_NAMES)])
        teacher_bot = None
        if teacher_strategy is not None:
            teacher_bot = StrategyBot(
                teacher_strategy,
                balanced_config=teacher_balanced_config
                or BalancedStrategyConfig(),
            )
        state = loaded.model.initial_state(1, device=torch.device("cpu"))
        teacher_state = (
            checkpoint_teacher.model.initial_state(1, device=torch.device("cpu"))
            if checkpoint_teacher is not None
            else None
        )
        previous_action = env.action_space.no_op_action
        episode_start = True
        decisions = placements = behavior_placements = 0
        done = False
        while not done:
            observation = env.get_structured_observation(
                learner, actor_observation_domain=actor_domain
            )
            if any(
                value is None
                for value in (
                    observation.entity_id_confidence,
                    observation.entity_feature_confidence,
                    observation.hand_id_confidence,
                    observation.global_feature_confidence,
                )
            ):
                raise ValueError("causal policy observation omitted confidence")
            if _contains_unknown_hand_token(observation.hand_ids):
                visible_hand = list(
                    env.battle.players[learner].hand[:NUM_HAND_SLOTS]
                )
                raise ValueError(
                    "policy-context current hand contains an unknown token: "
                    f"cards={visible_hand} "
                    f"ids={observation.hand_ids[:NUM_HAND_SLOTS].tolist()}"
                )
            policy_action: int | None = None
            next_state = state
            if (
                teacher_bot is None and checkpoint_teacher is None
            ) or execute_policy_behavior:
                policy_action, next_state, mask, _ = _policy_step(
                    loaded,
                    env,
                    learner,
                    state=state,
                    previous_action=previous_action,
                    previous_reward=0.0,
                    episode_start=episode_start,
                    deterministic=True,
                    device=torch.device("cpu"),
                )
            if checkpoint_teacher is not None:
                assert teacher_state is not None
                expert_action, teacher_state, teacher_mask, _ = _policy_step(
                    checkpoint_teacher,
                    env,
                    learner,
                    state=teacher_state,
                    previous_action=previous_action,
                    previous_reward=0.0,
                    episode_start=episode_start,
                    deterministic=True,
                    device=torch.device("cpu"),
                )
                if policy_action is not None and not np.array_equal(
                    mask, teacher_mask
                ):
                    raise ValueError("behavior and checkpoint teacher masks differ")
                mask = teacher_mask
            elif teacher_bot is not None:
                mask = env.get_action_mask(learner)
                expert_action = teacher_bot.select_action(
                    env, learner, action_mask=mask
                )
            else:
                assert policy_action is not None
                expert_action = policy_action
            behavior_action = (
                policy_action
                if execute_policy_behavior
                else expert_action
            )
            assert behavior_action is not None
            decision_valid, card_valid, tile_valid = _component_supervision(
                expert_action=expert_action,
                behavior_action=behavior_action,
                no_op_action=no_op,
                execute_policy_behavior=execute_policy_behavior,
                trust_off_policy_teacher_spatial=(
                    trust_off_policy_teacher_spatial
                ),
            )
            values = {
                "entity_ids": observation.entity_ids,
                "entity_features": observation.entity_features,
                "entity_mask": observation.entity_mask,
                "entity_id_confidence": observation.entity_id_confidence,
                "entity_feature_confidence": observation.entity_feature_confidence,
                "hand_ids": observation.hand_ids,
                "hand_id_confidence": observation.hand_id_confidence,
                "global_features": observation.global_features,
                "global_feature_confidence": observation.global_feature_confidence,
                "action_masks": mask,
                "previous_actions": previous_action,
                "previous_rewards": 0.0,
                "episode_starts": episode_start,
                "expert_actions": expert_action,
                "expert_action_supervision_valid": decision_valid,
                "expert_card_supervision_valid": card_valid,
                "expert_tile_supervision_valid": tile_valid,
                "episode_ids": game,
                "source_frames": int(env.battle.tick),
            }
            for name, value in values.items():
                assert value is not None
                rows[name].append(value)
            opponent_mask = env.get_action_mask(opponent)
            opponent_action = opponent_bot.select_action(
                env, opponent, action_mask=opponent_mask
            )
            _, done, _ = env.step(
                {learner: behavior_action, opponent: opponent_action},
                pre_action_masks={learner: mask, opponent: opponent_mask},
            )
            state = next_state
            previous_action = behavior_action
            episode_start = False
            decisions += 1
            placements += int(tile_valid)
            behavior_placements += int(behavior_action < no_op)
        episode_summaries.append(
            {
                "game": game,
                "seed": game_seed,
                "learner_player": learner,
                "opponent_strategy": opponent_bot.name,
                "learner_deck": list(env.battle.players[learner].deck),
                "opponent_deck": list(env.battle.players[opponent].deck),
                "decisions": decisions,
                "placements": placements,
                "behavior_placements": behavior_placements,
            }
        )
    arrays = {name: np.asarray(values) for name, values in rows.items()}
    samples = int(arrays["expert_actions"].size)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "decisions": samples,
        "seed": seed,
        "decision_interval": 8,
        "max_ticks": 6000,
        "planner_depth": 0,
        "planner_simulations": 0,
        "planner_action_samples": 0,
        "max_entities": loaded.builder.max_entities,
        "token_names": list(loaded.builder.token_names),
        "reward_profile": "objective-v1",
        "workers": 1,
        "behavior_checkpoint": str(checkpoint.resolve()),
        "expert_probability": 1.0,
        "stable_root_candidates": False,
        "behavior_opponent": None,
        "label_source": (
            "checkpoint"
            if teacher_checkpoint is not None
            else ("behavior" if teacher_strategy is None else "strategy")
        ),
        "label_strategy": teacher_strategy,
        "label_checkpoint": (
            str(teacher_checkpoint.resolve())
            if teacher_checkpoint is not None
            else None
        ),
        "label_checkpoint_sha256": (
            _sha(teacher_checkpoint) if teacher_checkpoint is not None else None
        ),
        "sampling_decks_path": str(opponent_decks_path.resolve()),
    }
    base_names = (
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
        "expert_action_supervision_valid",
        "expert_card_supervision_valid",
        "expert_tile_supervision_valid",
        "episode_ids",
        "source_frames",
    )
    corpus = {name: arrays[name] for name in base_names}
    corpus["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
    _save(corpus_path, corpus)
    sidecar_names = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_ids",
        "hand_id_confidence",
        "global_features",
        "global_feature_confidence",
        "action_masks",
        "expert_actions",
        "episode_ids",
        "source_frames",
    )
    sidecar = {name: arrays[name] for name in sidecar_names}
    sidecar.update(
        {
            "schema_version": np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
            "feature_contract_version": np.asarray(
                REAL_PLAY_FEATURE_CONTRACT_VERSION
            ),
            "action_mask_contract_version": np.asarray(
                PUBLIC_ACTION_MASK_CONTRACT_VERSION
            ),
            "expert_action_masked": np.zeros(samples, dtype=np.bool_),
        }
    )
    _save(sidecar_path, sidecar)
    result = {
        "schema": "clasher.policy_context_corpus.v1",
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": _sha(checkpoint),
        "corpus": str(corpus_path.resolve()),
        "corpus_sha256": _sha(corpus_path),
        "public_sidecar": str(sidecar_path.resolve()),
        "public_sidecar_sha256": _sha(sidecar_path),
        "games": games,
        "samples": samples,
        "placements": int(arrays["expert_tile_supervision_valid"].sum()),
        "actor_observation_domain": actor_domain,
        "teacher_strategy": teacher_strategy,
        "teacher_checkpoint": (
            str(teacher_checkpoint.resolve())
            if teacher_checkpoint is not None
            else None
        ),
        "teacher_checkpoint_sha256": (
            _sha(teacher_checkpoint) if teacher_checkpoint is not None else None
        ),
        "teacher_balanced_config": (
            asdict(teacher_balanced_config)
            if teacher_balanced_config is not None
            else None
        ),
        "execute_policy_behavior": execute_policy_behavior,
        "trust_off_policy_teacher_spatial": trust_off_policy_teacher_spatial,
        "episodes": episode_summaries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--decks-path", default=Path("decks.json"), type=Path)
    parser.add_argument("--learner-decks-path", required=True, type=Path)
    parser.add_argument("--opponent-decks-path", required=True, type=Path)
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1072301)
    parser.add_argument("--corpus-out", required=True, type=Path)
    parser.add_argument("--sidecar-out", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--teacher-strategy", choices=STRATEGY_NAMES)
    parser.add_argument("--teacher-checkpoint", type=Path)
    parser.add_argument("--teacher-balanced-config", type=Path)
    parser.add_argument("--execute-policy-behavior", action="store_true")
    parser.add_argument(
        "--trust-off-policy-teacher-spatial",
        action="store_true",
        help=(
            "trust legal card/tile recommendations from --teacher-checkpoint "
            "even when policy behavior waited"
        ),
    )
    args = parser.parse_args()
    teacher_balanced_config = None
    if args.teacher_balanced_config is not None:
        if args.teacher_strategy != "balanced":
            raise ValueError("balanced teacher config requires the balanced strategy")
        config_payload = json.loads(
            args.teacher_balanced_config.read_text(encoding="utf-8")
        )
        if not isinstance(config_payload, dict):
            raise TypeError("balanced teacher config must be a JSON object")
        teacher_balanced_config = BalancedStrategyConfig(**config_payload)
    result = collect(
        checkpoint=args.checkpoint.resolve(),
        decks_path=args.decks_path.resolve(),
        learner_decks_path=args.learner_decks_path.resolve(),
        opponent_decks_path=args.opponent_decks_path.resolve(),
        games=args.games,
        seed=args.seed,
        corpus_path=args.corpus_out.resolve(),
        sidecar_path=args.sidecar_out.resolve(),
        manifest_path=args.manifest_out.resolve(),
        teacher_strategy=args.teacher_strategy,
        teacher_checkpoint=(
            args.teacher_checkpoint.resolve()
            if args.teacher_checkpoint is not None
            else None
        ),
        teacher_balanced_config=teacher_balanced_config,
        execute_policy_behavior=args.execute_policy_behavior,
        trust_off_policy_teacher_spatial=(
            args.trust_off_policy_teacher_spatial
        ),
    )
    print(json.dumps({key: result[key] for key in ("games", "samples", "placements")}, sort_keys=True))


if __name__ == "__main__":
    main()
