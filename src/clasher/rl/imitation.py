from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path

from .model import ClasherPolicy, PolicyConfig, PolicyInputs
from .oracle_corpus import (
    CorpusShardSpec,
    atomic_save_npz,
    corpus_fingerprint,
    file_sha256,
    load_shard,
    publish_manifest,
    publish_shard,
    reusable_shard,
    shard_path,
)
from .oracle_planner import FixedDepthThompsonOracle
from .reward_model import DEFENSE_V2, REWARD_PROFILES
from .selfplay_env import SelfPlayBattleEnv
from .structured_obs import StructuredObservation, StructuredObservationBuilder
from .train_recurrent import maybe_silence_stdio, resolve_learner_device

CORPUS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CorpusMetadata:
    schema_version: int
    created_at: str
    seed: int
    decisions: int
    samples: int
    decision_interval: int
    max_ticks: int
    planner_depth: int
    planner_simulations: int
    planner_action_samples: int
    max_entities: int
    token_names: tuple[str, ...]
    reward_profile: str = DEFENSE_V2
    workers: int = 1

    def to_json(self) -> str:
        payload = self.__dict__.copy()
        payload["token_names"] = list(self.token_names)
        return json.dumps(payload, sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> CorpusMetadata:
        values = json.loads(payload)
        values["token_names"] = tuple(values["token_names"])
        values.setdefault("reward_profile", DEFENSE_V2)
        values.setdefault("workers", 1)
        return cls(**values)


@dataclass(frozen=True)
class _CorpusShardConfig:
    decks_path: Path
    decisions: int
    seed: int
    decision_interval: int
    max_ticks: int
    planner_depth: int
    planner_simulations: int
    planner_action_samples: int
    max_entities: int
    quiet_engine: bool
    reward_profile: str
    shard_spec: CorpusShardSpec
    shard_path: Path


def _append_observation(
    arrays: dict[str, list[np.ndarray | int | float | bool]],
    observation: StructuredObservation,
    action_mask: np.ndarray,
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    expert_action: int,
    episode_id: int,
) -> None:
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    ):
        arrays[name].append(getattr(observation, name).copy())
    arrays["action_masks"].append(action_mask.astype(np.bool_, copy=True))
    arrays["previous_actions"].append(int(previous_action))
    arrays["previous_rewards"].append(float(previous_reward))
    arrays["episode_starts"].append(bool(episode_start))
    arrays["expert_actions"].append(int(expert_action))
    arrays["episode_ids"].append(int(episode_id))


def _collect_oracle_shard(
    config: _CorpusShardConfig,
) -> dict[str, np.ndarray]:
    builder = StructuredObservationBuilder(
        decks_path=config.decks_path,
        max_entities=config.max_entities,
    )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=config.decision_interval,
        max_ticks=config.max_ticks,
        decks_path=config.decks_path,
        seed=config.seed,
        canonical_perspective=True,
        reward_profile=config.reward_profile,
    )
    env._structured_obs_builder = builder
    with maybe_silence_stdio(config.quiet_engine):
        env.reset(seed=config.seed)
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=config.decision_interval,
        plan_depth=config.planner_depth,
        num_simulations=config.planner_simulations,
        rollout_action_samples=config.planner_action_samples,
        seed=config.seed + 7919,
        reward_profile=config.reward_profile,
    )
    arrays: dict[str, list[np.ndarray | int | float | bool]] = {
        name: []
        for name in (
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
        )
    }
    previous_actions = [env.action_space.no_op_action] * 2
    previous_rewards = [0.0, 0.0]
    episode_starts = [True, True]
    episode_id = 0
    for _ in range(config.decisions):
        assert env.battle is not None
        with maybe_silence_stdio(config.quiet_engine):
            expert_actions = planner.select_actions(env.battle)
        for player_id in (0, 1):
            _append_observation(
                arrays,
                builder.build(env.battle, player_id),
                env.get_action_mask(player_id),
                previous_actions[player_id],
                previous_rewards[player_id],
                episode_starts[player_id],
                expert_actions[player_id],
                episode_id,
            )
        with maybe_silence_stdio(config.quiet_engine):
            rewards, done, _ = env.step(expert_actions)
        previous_actions = [expert_actions[0], expert_actions[1]]
        previous_rewards = [float(rewards[0]), float(rewards[1])]
        episode_starts = [False, False]
        if done:
            episode_id += 1
            with maybe_silence_stdio(config.quiet_engine):
                env.reset(seed=config.seed + episode_id * 1009)
            previous_actions = [env.action_space.no_op_action] * 2
            previous_rewards = [0.0, 0.0]
            episode_starts = [True, True]

    return {name: np.asarray(values) for name, values in arrays.items()}  # type: ignore[arg-type]


def _collect_and_publish_oracle_shard(config: _CorpusShardConfig) -> str:
    if not reusable_shard(config.shard_path, config.shard_spec):
        publish_shard(
            config.shard_path,
            config.shard_spec,
            _collect_oracle_shard(config),
        )
    return str(config.shard_path)


def collect_oracle_corpus(
    *,
    output_path: Path,
    decks_path: Path,
    decisions: int,
    seed: int,
    decision_interval: int,
    max_ticks: int,
    planner_depth: int,
    planner_simulations: int,
    planner_action_samples: int,
    max_entities: int,
    quiet_engine: bool,
    reward_profile: str = DEFENSE_V2,
    workers: int = 1,
) -> CorpusMetadata:
    if decisions <= 0:
        raise ValueError("decisions must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if reward_profile not in REWARD_PROFILES:
        raise ValueError(f"unknown reward profile {reward_profile!r}")
    worker_count = min(workers, decisions)
    base_decisions, remainder = divmod(decisions, worker_count)
    fingerprint = corpus_fingerprint(
        {
            "schema_version": CORPUS_SCHEMA_VERSION,
            "decks_sha256": file_sha256(decks_path),
            "decisions": decisions,
            "seed": seed,
            "decision_interval": decision_interval,
            "max_ticks": max_ticks,
            "planner_depth": planner_depth,
            "planner_simulations": planner_simulations,
            "planner_action_samples": planner_action_samples,
            "max_entities": max_entities,
            "reward_profile": reward_profile,
            "workers": worker_count,
        }
    )
    shards = [
        _CorpusShardConfig(
            decks_path=decks_path,
            decisions=base_decisions + int(shard_index < remainder),
            seed=seed + shard_index * 1_000_003,
            decision_interval=decision_interval,
            max_ticks=max_ticks,
            planner_depth=planner_depth,
            planner_simulations=planner_simulations,
            planner_action_samples=planner_action_samples,
            max_entities=max_entities,
            quiet_engine=quiet_engine,
            reward_profile=reward_profile,
            shard_spec=CorpusShardSpec(
                corpus_fingerprint=fingerprint,
                shard_index=shard_index,
                shard_count=worker_count,
                decisions=base_decisions + int(shard_index < remainder),
                seed=seed + shard_index * 1_000_003,
            ),
            shard_path=shard_path(output_path, shard_index, worker_count),
        )
        for shard_index in range(worker_count)
    ]
    completed = [
        shard.shard_spec.shard_index
        for shard in shards
        if reusable_shard(shard.shard_path, shard.shard_spec)
    ]
    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=completed,
        complete=False,
    )
    if worker_count == 1:
        published_paths = [_collect_and_publish_oracle_shard(shards[0])]
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            published_paths = list(
                executor.map(_collect_and_publish_oracle_shard, shards)
            )

    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=list(range(worker_count)),
        complete=False,
    )
    shard_arrays = [
        load_shard(Path(published_path), shard.shard_spec)
        for published_path, shard in zip(published_paths, shards, strict=True)
    ]

    episode_offset = 0
    merged_chunks: dict[str, list[np.ndarray]] = {name: [] for name in shard_arrays[0]}
    for arrays in shard_arrays:
        episode_ids = arrays["episode_ids"].copy()
        episode_ids += episode_offset
        arrays["episode_ids"] = episode_ids
        episode_offset = int(episode_ids.max()) + 1
        for name, values in arrays.items():
            merged_chunks[name].append(values)
    merged = {
        name: np.concatenate(chunks, axis=0) for name, chunks in merged_chunks.items()
    }

    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=max_entities,
    )
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        decisions=decisions,
        samples=2 * decisions,
        decision_interval=decision_interval,
        max_ticks=max_ticks,
        planner_depth=planner_depth,
        planner_simulations=planner_simulations,
        planner_action_samples=planner_action_samples,
        max_entities=max_entities,
        token_names=builder.token_names,
        reward_profile=reward_profile,
        workers=worker_count,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_save_npz(
        output_path,
        {
            **merged,
            "metadata_json": np.asarray(metadata.to_json()),
        },
    )
    publish_manifest(
        output_path,
        corpus_fingerprint=fingerprint,
        shard_count=worker_count,
        completed_shards=list(range(worker_count)),
        complete=True,
    )
    return metadata


def load_corpus(path: Path) -> tuple[CorpusMetadata, dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as payload:
        metadata = CorpusMetadata.from_json(str(payload["metadata_json"].item()))
        if metadata.schema_version != CORPUS_SCHEMA_VERSION:
            raise ValueError(f"unsupported corpus schema {metadata.schema_version}")
        arrays = {
            name: payload[name].copy()
            for name in (
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
            )
        }
    if arrays["expert_actions"].shape[0] != metadata.samples:
        raise ValueError("corpus sample count does not match metadata")
    legal = arrays["action_masks"][
        np.arange(metadata.samples), arrays["expert_actions"]
    ]
    if not np.all(legal):
        raise ValueError("corpus contains an illegal expert action")
    return metadata, arrays


def split_indices(
    episode_ids: np.ndarray,
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between zero and one")
    count = int(episode_ids.shape[0])
    if count < 2:
        raise ValueError("corpus needs at least two samples")
    rng = np.random.default_rng(seed)
    unique_episodes = np.unique(episode_ids)
    if unique_episodes.size >= 2:
        shuffled = rng.permutation(unique_episodes)
        validation_episodes = set(
            shuffled[
                : max(1, round(unique_episodes.size * validation_fraction))
            ].tolist()
        )
        validation = np.asarray(
            [
                index
                for index, episode in enumerate(episode_ids)
                if episode in validation_episodes
            ],
            dtype=np.int64,
        )
        training = np.asarray(
            [
                index
                for index, episode in enumerate(episode_ids)
                if episode not in validation_episodes
            ],
            dtype=np.int64,
        )
        if training.size and validation.size:
            return training, validation
    permutation = rng.permutation(count)
    validation_count = max(1, min(count - 1, round(count * validation_fraction)))
    return permutation[validation_count:], permutation[:validation_count]


def _batch_inputs(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    device: torch.device,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(
            arrays[name][indices], dtype=dtype, device=device
        ).unsqueeze(1)

    return PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        # Single-example batches deliberately reset memory. This trains the
        # exact V2 actor architecture without smuggling privileged sequence
        # state into a shuffled demonstration baseline.
        episode_starts=torch.ones((len(indices), 1), dtype=torch.bool, device=device),
    )


@torch.no_grad()
def evaluate_imitation(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    *,
    batch_size: int,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    loss_sum = correct = samples = 0.0
    for start in range(0, len(indices), batch_size):
        batch_indices = indices[start : start + batch_size]
        inputs = _batch_inputs(arrays, batch_indices, device)
        targets = torch.as_tensor(
            arrays["expert_actions"][batch_indices], dtype=torch.long, device=device
        )
        logits = model(inputs).joint_logits[:, 0]
        loss_sum += float(nn.functional.cross_entropy(logits, targets, reduction="sum"))
        correct += float((logits.argmax(dim=-1) == targets).sum())
        samples += len(batch_indices)
    return {
        "loss": loss_sum / max(1.0, samples),
        "accuracy": correct / max(1.0, samples),
        "samples": samples,
    }


def _checkpoint_payload(
    *,
    model: ClasherPolicy,
    metadata: CorpusMetadata,
    corpus_path: Path,
    metrics: dict[str, float],
    seed: int,
    trained: bool,
) -> dict[str, Any]:
    return {
        "format_version": 2,
        "model_type": "entity_spatial_recurrent",
        "model_config": model.config.to_dict(),
        "token_names": metadata.token_names,
        "model_state_dict": model.state_dict(),
        "args": {
            "initialization": "oracle_imitation"
            if trained
            else "matched_random_control",
            "corpus": str(corpus_path),
            "seed": seed,
        },
        "update": 0,
        "total_transitions": 0,
        "metrics": metrics,
        "imitation": {
            "schema_version": 1,
            "corpus": str(corpus_path),
            "corpus_samples": metadata.samples,
            "reward_profile": metadata.reward_profile,
            "trained": trained,
        },
    }


def fit_imitation_corpus(
    *,
    corpus_path: Path,
    output_checkpoint: Path,
    control_checkpoint: Path,
    decks_path: Path,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    validation_fraction: float,
    device: torch.device,
    d_model: int,
    num_heads: int,
    actor_layers: int,
    critic_layers: int,
    memory_size: int,
) -> dict[str, Any]:
    if epochs <= 0 or batch_size <= 0:
        raise ValueError("epochs and batch_size must be positive")
    metadata, arrays = load_corpus(corpus_path)
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=metadata.max_entities,
        token_names=metadata.token_names,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.max_entities,
        d_model=d_model,
        num_heads=num_heads,
        actor_layers=actor_layers,
        critic_layers=critic_layers,
        memory_size=memory_size,
    )
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    training, validation = split_indices(
        arrays["episode_ids"], validation_fraction=validation_fraction, seed=seed
    )

    control_metrics = evaluate_imitation(
        model, arrays, validation, batch_size=batch_size, device=device
    )
    control_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            model=model,
            metadata=metadata,
            corpus_path=corpus_path,
            metrics={
                f"validation_{key}": value for key, value in control_metrics.items()
            },
            seed=seed,
            trained=False,
        ),
        control_checkpoint,
    )

    rng = np.random.default_rng(seed + 1)
    for _ in range(epochs):
        model.train()
        shuffled_training = rng.permutation(training)
        for start in range(0, len(training), batch_size):
            batch_indices = shuffled_training[start : start + batch_size]
            inputs = _batch_inputs(arrays, batch_indices, device)
            targets = torch.as_tensor(
                arrays["expert_actions"][batch_indices], dtype=torch.long, device=device
            )
            logits = model(inputs).joint_logits[:, 0]
            loss = nn.functional.cross_entropy(logits, targets)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()

    train_metrics = evaluate_imitation(
        model, arrays, training, batch_size=batch_size, device=device
    )
    validation_metrics = evaluate_imitation(
        model, arrays, validation, batch_size=batch_size, device=device
    )
    metrics = {
        **{f"train_{key}": value for key, value in train_metrics.items()},
        **{f"validation_{key}": value for key, value in validation_metrics.items()},
        "control_validation_loss": control_metrics["loss"],
        "control_validation_accuracy": control_metrics["accuracy"],
    }
    output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            model=model,
            metadata=metadata,
            corpus_path=corpus_path,
            metrics=metrics,
            seed=seed,
            trained=True,
        ),
        output_checkpoint,
    )
    return {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "imitation_checkpoint": str(output_checkpoint),
        "matched_control_checkpoint": str(control_checkpoint),
        "seed": seed,
        "train_samples": len(training),
        "validation_samples": len(validation),
        "epochs": epochs,
        "metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build fixed oracle corpora and matched V2 imitation warm starts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--output", required=True)
    collect.add_argument("--decks-path", default="decks.json")
    collect.add_argument("--decisions", type=int, default=5000)
    collect.add_argument("--seed", type=int, default=4401)
    collect.add_argument("--decision-interval", type=int, default=8)
    collect.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    collect.add_argument("--planner-depth", type=int, default=6)
    collect.add_argument("--planner-simulations", type=int, default=32)
    collect.add_argument("--planner-action-samples", type=int, default=64)
    collect.add_argument("--max-entities", type=int, default=128)
    collect.add_argument("--workers", type=int, default=1)
    collect.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=DEFENSE_V2
    )
    collect.add_argument("--quiet-engine", action="store_true", default=True)
    collect.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")

    fit = subparsers.add_parser("fit")
    fit.add_argument("--corpus", required=True)
    fit.add_argument("--output-checkpoint", required=True)
    fit.add_argument("--control-checkpoint", required=True)
    fit.add_argument("--manifest-out", required=True)
    fit.add_argument("--decks-path", default="decks.json")
    fit.add_argument("--seed", type=int, default=5501)
    fit.add_argument("--epochs", type=int, default=10)
    fit.add_argument("--batch-size", type=int, default=32)
    fit.add_argument("--learning-rate", type=float, default=2.5e-4)
    fit.add_argument("--validation-fraction", type=float, default=0.2)
    fit.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    fit.add_argument("--d-model", type=int, default=128)
    fit.add_argument("--num-heads", type=int, default=4)
    fit.add_argument("--actor-layers", type=int, default=4)
    fit.add_argument("--critic-layers", type=int, default=2)
    fit.add_argument("--memory-size", type=int, default=256)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    if args.command == "collect":
        metadata = collect_oracle_corpus(
            output_path=resolve_path(args.output),
            decks_path=decks_path,
            decisions=args.decisions,
            seed=args.seed,
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            planner_depth=args.planner_depth,
            planner_simulations=args.planner_simulations,
            planner_action_samples=args.planner_action_samples,
            max_entities=args.max_entities,
            quiet_engine=args.quiet_engine,
            reward_profile=args.reward_profile,
            workers=args.workers,
        )
        print(metadata.to_json())
        return

    device = resolve_learner_device(args.device)
    manifest = fit_imitation_corpus(
        corpus_path=resolve_path(args.corpus, must_exist=True),
        output_checkpoint=resolve_path(args.output_checkpoint),
        control_checkpoint=resolve_path(args.control_checkpoint),
        decks_path=decks_path,
        seed=args.seed,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        validation_fraction=args.validation_fraction,
        device=device,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
    )
    manifest_path = resolve_path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
