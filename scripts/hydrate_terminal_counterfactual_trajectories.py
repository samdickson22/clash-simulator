"""Replay counterfactual source games into recurrent actor-training trajectories.

The terminal counterfactual corpus intentionally stored only frozen policy
features.  That is sufficient for a post-hoc head, but not for training a new
actor end to end.  This tool deterministically replays each source game,
retains every public actor observation needed to reach an intervention root,
and verifies the root against the original action, mask, hand, and frozen
feature vector before publishing it.
"""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch

ACTOR_ARRAY_NAMES = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
)
CONFIDENCE_ARRAY_NAMES = (
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_id_confidence",
    "global_feature_confidence",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def report_sidecar(shard: Path) -> Path:
    return shard.with_suffix(".json")


def _empty_lists() -> dict[str, list[Any]]:
    return {
        **{name: [] for name in (*ACTOR_ARRAY_NAMES, *CONFIDENCE_ARRAY_NAMES)},
        "action_masks": [],
        "previous_actions": [],
        "previous_rewards": [],
        "episode_starts": [],
        "expert_actions": [],
        "episode_ids": [],
        "ticks": [],
    }


def _append_actor_row(
    rows: dict[str, list[Any]],
    *,
    observation: Any,
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    expert_action: int,
    episode_id: int,
    tick: int,
) -> None:
    for name in ACTOR_ARRAY_NAMES:
        rows[name].append(getattr(observation, name).copy())
    entity_confidence = observation.entity_mask.astype(np.float32, copy=True)
    rows["entity_id_confidence"].append(entity_confidence)
    rows["entity_feature_confidence"].append(
        np.broadcast_to(
            entity_confidence[:, None], observation.entity_features.shape
        ).copy()
    )
    rows["hand_id_confidence"].append(
        np.ones(observation.hand_ids.shape, dtype=np.float32)
    )
    rows["global_feature_confidence"].append(
        np.ones(observation.global_features.shape, dtype=np.float32)
    )
    rows["action_masks"].append(action_mask.astype(np.bool_, copy=True))
    rows["previous_actions"].append(int(previous_action))
    rows["previous_rewards"].append(float(previous_reward))
    rows["episode_starts"].append(bool(episode_start))
    rows["expert_actions"].append(int(expert_action))
    rows["episode_ids"].append(int(episode_id))
    rows["ticks"].append(int(tick))


def _stack_trajectory_rows(rows: dict[str, list[Any]]) -> dict[str, np.ndarray]:
    if not rows["expert_actions"]:
        raise ValueError("hydration produced no trajectory rows")
    result = {
        name: np.stack(rows[name])
        for name in (
            *ACTOR_ARRAY_NAMES,
            *CONFIDENCE_ARRAY_NAMES,
            "action_masks",
        )
    }
    result.update(
        {
            "previous_actions": np.asarray(rows["previous_actions"], dtype=np.int64),
            "previous_rewards": np.asarray(rows["previous_rewards"], dtype=np.float32),
            "episode_starts": np.asarray(rows["episode_starts"], dtype=np.bool_),
            "expert_actions": np.asarray(rows["expert_actions"], dtype=np.int64),
            "episode_ids": np.asarray(rows["episode_ids"], dtype=np.int64),
            "ticks": np.asarray(rows["ticks"], dtype=np.int64),
        }
    )
    # Match the existing imitation corpus storage contract and avoid paying
    # double precision/storage for exact normalized public observations.
    result["entity_features"] = result["entity_features"].astype(np.float16, copy=False)
    return result


def _load_root_payload(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name].copy() for name in archive.files}


def _verify_root(
    *,
    root: dict[str, np.ndarray],
    root_index: int,
    base_action: int,
    action_mask: np.ndarray,
    hand_ids: np.ndarray,
    repair_features: np.ndarray,
    tick: int,
) -> None:
    if int(root["ticks"][root_index]) != tick:
        raise ValueError("counterfactual root tick mismatch")
    if int(root["base_actions"][root_index]) != base_action:
        raise ValueError("counterfactual root base action mismatch")
    if not np.array_equal(root["action_masks"][root_index], action_mask):
        raise ValueError("counterfactual root action mask mismatch")
    if not np.array_equal(root["hand_ids"][root_index], hand_ids):
        raise ValueError("counterfactual root hand mismatch")
    if not np.allclose(
        root["features"][root_index],
        repair_features,
        rtol=1e-5,
        atol=2e-5,
    ):
        maximum = float(np.max(np.abs(root["features"][root_index] - repair_features)))
        raise ValueError(
            f"counterfactual root frozen feature mismatch (max_abs={maximum})"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-report", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--max-shards", type=int, default=None)
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite hydration output or report")
    if args.torch_threads <= 0 or args.decision_interval <= 0 or args.max_ticks <= 0:
        raise ValueError("thread, interval, and tick counts must be positive")

    torch.set_num_threads(args.torch_threads)
    combined_report = json.loads(args.corpus_report.read_text())
    source_shards = [Path(value) for value in combined_report["source_shards"]]
    if args.max_shards is not None:
        if args.max_shards <= 0:
            raise ValueError("max shards must be positive")
        source_shards = source_shards[: args.max_shards]
    if not source_shards:
        raise ValueError("counterfactual report contains no source shards")

    policy_path = Path(combined_report["policy"])
    device = torch.device(args.device)
    loaded = load_policy_checkpoint(
        policy_path,
        device=device,
        decks_path=args.decks_path,
    )
    search = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=None,
        device=device,
        max_candidates=1,
    )
    rows = _empty_lists()
    root_rows: list[int] = []
    root_payloads: list[dict[str, np.ndarray]] = []
    replay_rows: list[dict[str, Any]] = []
    started = time.monotonic()
    hydrated_episode = 0

    for source_position, shard_path in enumerate(source_shards):
        root = _load_root_payload(shard_path)
        root_count = int(root["base_actions"].shape[0])
        if root_count == 0:
            continue
        sidecar = report_sidecar(shard_path)
        shard_report = json.loads(sidecar.read_text())
        if Path(shard_report["policy"]).resolve() != policy_path.resolve():
            raise ValueError("source shard policy does not match combined authority")
        games = shard_report["games"]
        if len(games) != 1:
            raise ValueError("hydration requires one source game per shard")
        game = games[0]
        controlled_player = int(game["controlled_player"])
        opponent = 1 - controlled_player
        strategy_name = str(game["strategy"])
        game_seed = int(game["seed"])
        bot = StrategyBot(strategy_name)
        shared_sampling = shard_report.get("sampling_decks_path")
        learner_sampling = shard_report.get("learner_sampling_decks_path")
        opponent_sampling = shard_report.get("opponent_sampling_decks_path")
        if (learner_sampling is None) != (opponent_sampling is None):
            raise ValueError("source shard has incomplete separate deck authority")
        if shared_sampling is None and learner_sampling is None:
            raise ValueError("source shard has no replayable deck authority")
        common_sampling = Path(
            shared_sampling if shared_sampling is not None else opponent_sampling
        )
        player_sampling_paths: tuple[Path | None, Path | None] = (None, None)
        if learner_sampling is not None:
            learner_path = Path(learner_sampling)
            opponent_path = Path(opponent_sampling)
            player_sampling_paths = (
                (learner_path, opponent_path)
                if controlled_player == 0
                else (opponent_path, learner_path)
            )
        env = SelfPlayBattleEnv(
            decision_interval_ticks=args.decision_interval,
            max_ticks=args.max_ticks,
            decks_path=args.decks_path,
            sampling_decks_path=common_sampling,
            player0_sampling_decks_path=player_sampling_paths[0],
            player1_sampling_decks_path=player_sampling_paths[1],
            seed=game_seed,
            canonical_perspective=True,
            canonical_lane_globals=loaded.model.config.canonical_lane_globals,
            engine_fast_path="on",
            reward_profile=DEFENSE_V2,
        )
        env._structured_obs_builder = loaded.builder
        env.reset(seed=game_seed)
        assert env.battle is not None
        actual_decks = [list(player.deck) for player in env.battle.players]
        if actual_decks != game["decks"]:
            raise ValueError("replayed source decks do not match shard report")

        states = {
            player: loaded.model.initial_state(1, device=device) for player in (0, 1)
        }
        previous_actions = {player: env.action_space.no_op_action for player in (0, 1)}
        previous_rewards = {0: 0.0, 1: 0.0}
        episode_start = True
        root_index = 0
        first_trajectory_row = len(rows["expert_actions"])
        done = False
        while not done and root_index < root_count:
            tick = int(env.battle.tick)
            observation = loaded.builder.build(env.battle, controlled_player)
            policy_actions, next_states, outputs, masks = search.observe_policy_pair(
                env,
                states=states,
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_start=episode_start,
            )
            base_action = int(policy_actions[controlled_player])
            controlled_mask = masks[controlled_player]
            _append_actor_row(
                rows,
                observation=observation,
                action_mask=controlled_mask,
                previous_action=previous_actions[controlled_player],
                previous_reward=previous_rewards[controlled_player],
                episode_start=episode_start,
                expert_action=base_action,
                episode_id=hydrated_episode,
                tick=tick,
            )

            expected_tick = int(root["ticks"][root_index])
            if tick == expected_tick:
                repair = outputs[controlled_player].repair_features
                if repair is None:
                    raise ValueError("policy does not expose intervention features")
                repair_array = repair[0, 0].detach().cpu().numpy()
                _verify_root(
                    root=root,
                    root_index=root_index,
                    base_action=base_action,
                    action_mask=controlled_mask,
                    hand_ids=observation.hand_ids[:4],
                    repair_features=repair_array,
                    tick=tick,
                )
                root_rows.append(len(rows["expert_actions"]) - 1)
                root_payloads.append(
                    {name: value[root_index].copy() for name, value in root.items()}
                )
                root_index += 1
                if root_index == root_count:
                    break
            elif tick > expected_tick:
                raise ValueError(
                    f"replay skipped counterfactual root tick {expected_tick} at {tick}"
                )

            policy_actions[opponent] = int(
                bot.select_action(env, opponent, action_mask=masks[opponent])
            )
            rewards, done, _ = env.step(
                policy_actions,
                pre_action_masks=masks,
            )
            states = next_states
            previous_actions = policy_actions
            previous_rewards = {player: float(rewards[player]) for player in (0, 1)}
            episode_start = False

        if root_index != root_count:
            raise ValueError("replay ended before every counterfactual root")
        replay_rows.append(
            {
                "source_position": source_position,
                "source_shard": str(shard_path.resolve()),
                "source_shard_sha256": file_sha256(shard_path),
                "game": int(game["game"]),
                "seed": game_seed,
                "strategy": strategy_name,
                "controlled_player": controlled_player,
                "trajectory_rows": len(rows["expert_actions"]) - first_trajectory_row,
                "root_rows": root_count,
                "last_root_tick": int(root["ticks"][-1]),
            }
        )
        hydrated_episode += 1
        print(
            json.dumps(
                {
                    "hydrated_episodes": hydrated_episode,
                    "source_shards_seen": source_position + 1,
                    "trajectory_rows": len(rows["expert_actions"]),
                    "counterfactual_roots": len(root_rows),
                    "elapsed_seconds": time.monotonic() - started,
                }
            ),
            flush=True,
        )

    trajectory = _stack_trajectory_rows(rows)
    if not root_payloads:
        raise ValueError("hydration found no non-empty counterfactual roots")
    root_names = tuple(root_payloads[0])
    for payload in root_payloads:
        if tuple(payload) != root_names:
            raise ValueError("counterfactual root schemas differ across shards")
    root_arrays = {
        f"root_{name}": np.stack([payload[name] for payload in root_payloads])
        for name in root_names
    }
    root_arrays["counterfactual_root_rows"] = np.asarray(root_rows, dtype=np.int64)

    # A full run must reproduce the combined source ordering exactly.  Bounded
    # smoke runs intentionally validate only a prefix.
    if args.max_shards is None:
        combined_npz = Path(combined_report["output"])
        with np.load(combined_npz, allow_pickle=False) as combined:
            for name in combined.files:
                hydrated = root_arrays[f"root_{name}"]
                if not np.array_equal(hydrated, combined[name], equal_nan=True):
                    raise ValueError(
                        f"hydrated root order differs from combined array {name}"
                    )

    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=int(combined_report.get("seed", 0)),
        decisions=int(trajectory["expert_actions"].shape[0]),
        samples=int(trajectory["expert_actions"].shape[0]),
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=loaded.builder.max_entities,
        token_names=tuple(loaded.builder.token_names),
        reward_profile=DEFENSE_V2,
        workers=1,
        behavior_checkpoint=str(policy_path.resolve()),
        expert_probability=1.0,
        stable_root_candidates=True,
        behavior_opponent="mixed-strategy",
        label_source="terminal-counterfactual-trajectory",
        sampling_decks_path=None,
    )
    output_arrays = {
        **trajectory,
        **root_arrays,
        "metadata_json": np.asarray(metadata.to_json()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        np.savez_compressed(stream, **output_arrays)  # type: ignore[arg-type]

    report = {
        "schema_version": 1,
        "source_report": str(args.corpus_report.resolve()),
        "source_report_sha256": file_sha256(args.corpus_report),
        "source_combined_corpus": str(Path(combined_report["output"]).resolve()),
        "policy": str(policy_path.resolve()),
        "policy_sha256": file_sha256(policy_path),
        "output": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "trajectory_rows": int(trajectory["expert_actions"].shape[0]),
        "episodes": hydrated_episode,
        "counterfactual_roots": len(root_rows),
        "source_shards_considered": len(source_shards),
        "full_combined_order_verified": args.max_shards is None,
        "elapsed_seconds": time.monotonic() - started,
        "array_shapes": {
            name: list(value.shape)
            for name, value in output_arrays.items()
            if name != "metadata_json"
        },
        "array_sha256": {
            name: array_sha256(value)
            for name, value in output_arrays.items()
            if name != "metadata_json"
        },
        "replays": replay_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "trajectory_rows",
                    "episodes",
                    "counterfactual_roots",
                    "output_sha256",
                    "elapsed_seconds",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
