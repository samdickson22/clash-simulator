#!/usr/bin/env python3
# mypy: disable-error-code="import-untyped"
"""Collect public recurrent defense trajectories from a deterministic teacher."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from clasher.rl.public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_npz(path: Path, values: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **values)  # type: ignore[arg-type]
    temporary.replace(path)


def collect(
    *,
    checkpoint: Path,
    decks_path: Path,
    learner_decks_path: Path,
    opponent_decks_path: Path,
    scenarios: int,
    seed: int,
    teacher_name: str,
    minimum_elixir: int,
    maximum_elixir: int,
    horizon_ticks: int,
    corpus_path: Path,
    sidecar_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    if scenarios <= 0:
        raise ValueError("scenarios must be positive")
    if teacher_name not in STRATEGY_NAMES:
        raise ValueError("teacher must be a known deterministic strategy")
    loaded = load_policy_checkpoint(
        checkpoint,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    if not loaded.model.config.public_observation_confidence:
        raise ValueError("defense teacher collection requires confidence-aware policy")
    actor_domain = loaded.model.config.actor_observation_domain
    if actor_domain not in {"causal-vision-v1", "causal-frame-v1"}:
        raise ValueError("defense teacher collection requires a causal actor domain")
    teacher = StrategyBot(teacher_name)
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
    for episode_id in range(scenarios):
        scenario_seed = seed + episode_id * 1009
        learner = episode_id % 2
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
            seed=scenario_seed,
            canonical_perspective=True,
            canonical_lane_globals=loaded.model.config.canonical_lane_globals,
            engine_fast_path="on",
            reward_profile="objective-v1",
            defense_scenario_probability=1.0,
            defense_scenario_minimum_elixir=minimum_elixir,
            defense_scenario_maximum_elixir=maximum_elixir,
            defense_scenario_horizon_ticks=horizon_ticks,
        )
        env._structured_obs_builder = loaded.builder
        env.reset(seed=scenario_seed)
        assert env.battle is not None and env.defense_scenario is not None
        previous_action = env.action_space.no_op_action
        episode_start = True
        decisions = placements = 0
        done = False
        while not done:
            observation = env.get_structured_observation(
                learner,
                actor_observation_domain=actor_domain,
            )
            confidence_values = (
                observation.entity_id_confidence,
                observation.entity_feature_confidence,
                observation.hand_id_confidence,
                observation.global_feature_confidence,
            )
            if any(value is None for value in confidence_values):
                raise ValueError("causal defense observation omitted confidence")
            mask = env.get_action_mask(
                learner,
                actor_observation_domain=actor_domain,
                structured_observation=observation,
            )
            action = int(
                teacher.select_action(env, learner, action_mask=mask)
            )
            if not bool(mask[action]):
                raise ValueError("defense teacher selected a public-illegal action")
            is_placement = action < no_op
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
                "expert_actions": action,
                "expert_action_supervision_valid": True,
                "expert_card_supervision_valid": is_placement,
                "expert_tile_supervision_valid": is_placement,
                "episode_ids": episode_id,
                "source_frames": int(env.battle.tick),
            }
            for name, value in values.items():
                assert value is not None
                rows[name].append(value)
            opponent = 1 - learner
            opponent_mask = env.get_action_mask(opponent)
            _, done, _ = env.step(
                {learner: action, opponent: env.action_space.no_op_action},
                pre_action_masks={learner: mask, opponent: opponent_mask},
            )
            previous_action = action
            episode_start = False
            decisions += 1
            placements += int(is_placement)
        episode_summaries.append(
            {
                "episode_id": episode_id,
                "seed": scenario_seed,
                "learner_player": learner,
                "learner_deck": list(env.battle.players[learner].deck),
                "opponent_deck": list(env.battle.players[1 - learner].deck),
                "threat_cards": list(env.defense_scenario.threat_cards),
                "decisions": decisions,
                "placements": placements,
            }
        )

    arrays = {name: np.asarray(values) for name, values in rows.items()}
    samples = int(arrays["expert_actions"].shape[0])
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "decisions": samples,
        "seed": seed,
        "decision_interval": 8,
        "max_ticks": horizon_ticks,
        "planner_depth": 0,
        "planner_simulations": 0,
        "planner_action_samples": 0,
        "max_entities": loaded.builder.max_entities,
        "token_names": list(loaded.builder.token_names),
        "reward_profile": "objective-v1",
        "workers": 1,
        "expert_probability": 1.0,
        "stable_root_candidates": False,
        "behavior_checkpoint": None,
        "behavior_opponent": None,
        "label_source": "strategy",
        "label_strategy": f"strategy:{teacher_name}",
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
    corpus_values = {name: arrays[name] for name in base_names}
    corpus_values["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True))
    _atomic_npz(corpus_path, corpus_values)
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
    sidecar_values = {name: arrays[name] for name in sidecar_names}
    sidecar_values.update(
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
    _atomic_npz(sidecar_path, sidecar_values)
    payload = {
        "schema": "clasher.defense_teacher_corpus.v1",
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": _sha256(checkpoint),
        "corpus": str(corpus_path.resolve()),
        "corpus_sha256": _sha256(corpus_path),
        "public_sidecar": str(sidecar_path.resolve()),
        "public_sidecar_sha256": _sha256(sidecar_path),
        "scenarios": scenarios,
        "samples": samples,
        "placements": int(arrays["expert_tile_supervision_valid"].sum()),
        "actor_observation_domain": actor_domain,
        "minimum_elixir": minimum_elixir,
        "maximum_elixir": maximum_elixir,
        "horizon_ticks": horizon_ticks,
        "episodes": episode_summaries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--decks-path", default=Path("decks.json"), type=Path)
    parser.add_argument("--learner-decks-path", required=True, type=Path)
    parser.add_argument("--opponent-decks-path", required=True, type=Path)
    parser.add_argument("--scenarios", type=int, default=256)
    parser.add_argument("--seed", type=int, default=1071701)
    parser.add_argument("--teacher", choices=STRATEGY_NAMES, default="reactive-defense")
    parser.add_argument("--minimum-elixir", type=int, default=4)
    parser.add_argument("--maximum-elixir", type=int, default=7)
    parser.add_argument("--horizon-ticks", type=int, default=240)
    parser.add_argument("--corpus-out", required=True, type=Path)
    parser.add_argument("--sidecar-out", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    result = collect(
        checkpoint=args.checkpoint.resolve(),
        decks_path=args.decks_path.resolve(),
        learner_decks_path=args.learner_decks_path.resolve(),
        opponent_decks_path=args.opponent_decks_path.resolve(),
        scenarios=args.scenarios,
        seed=args.seed,
        teacher_name=args.teacher,
        minimum_elixir=args.minimum_elixir,
        maximum_elixir=args.maximum_elixir,
        horizon_ticks=args.horizon_ticks,
        corpus_path=args.corpus_out.resolve(),
        sidecar_path=args.sidecar_out.resolve(),
        manifest_path=args.manifest_out.resolve(),
    )
    print(json.dumps({key: result[key] for key in ("scenarios", "samples", "placements")}, sort_keys=True))


if __name__ == "__main__":
    main()
