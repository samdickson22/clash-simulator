#!/usr/bin/env python3
"""Generate on-policy Hog trajectories labeled by the retained hazard parent."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from scripts.probe_simple_counterfactual_teacher import (
    ForcedLearnerRootPolicy,
    load_collector,
)

ARRAY_KEYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_id_confidence",
    "global_feature_confidence",
    "action_masks",
    "previous_actions",
    "previous_rewards",
    "episode_starts",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pack_entities(arrays: dict[str, np.ndarray]) -> None:
    ids = arrays["entity_ids"]
    features = arrays["entity_features"]
    mask = arrays["entity_mask"]
    packed_ids = np.zeros_like(ids)
    packed_features = np.zeros_like(features)
    packed_mask = np.zeros_like(mask)
    for batch in range(mask.shape[0]):
        for step in range(mask.shape[1]):
            selected = np.flatnonzero(mask[batch, step])
            count = int(selected.size)
            packed_ids[batch, step, :count] = ids[batch, step, selected]
            packed_features[batch, step, :count] = features[
                batch, step, selected
            ]
            packed_mask[batch, step, :count] = True
    arrays["entity_ids"] = packed_ids
    arrays["entity_features"] = packed_features
    arrays["entity_mask"] = packed_mask


def step_inputs(
    arrays: dict[str, np.ndarray],
    step: int,
    device: torch.device,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(
            arrays[name][:, step : step + 1],
            dtype=dtype,
            device=device,
        )

    return PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
        entity_id_confidence=tensor("entity_id_confidence", torch.float32),
        entity_feature_confidence=tensor(
            "entity_feature_confidence", torch.float32
        ),
        hand_id_confidence=tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=tensor(
            "global_feature_confidence", torch.float32
        ),
    )


def load_teacher(
    checkpoint: Path,
    *,
    token_names: tuple[str, ...],
    device: torch.device,
) -> ClasherPolicy:
    payload = torch.load(checkpoint, map_location=device, weights_only=False)
    if tuple(payload["token_names"]) != token_names:
        raise ValueError("teacher and student vocabularies differ")
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(PolicyConfig.from_dict(payload["model_config"]), card_stats).to(
        device
    )
    model.load_state_dict(payload["model_state_dict"], strict=True)
    return model.eval()


@torch.no_grad()
def label_teacher_actions(
    teacher: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    *,
    device: torch.device,
) -> np.ndarray:
    batch, steps = arrays["previous_actions"].shape
    state = teacher.initial_state(batch, device=device)
    actions = np.empty((batch, steps), dtype=np.int64)
    for step in range(steps):
        inputs = step_inputs(arrays, step, device)
        selected, _log_prob, _value, state, _output = teacher.act(
            inputs,
            state,
            deterministic=True,
        )
        actions[:, step] = selected[:, 0].cpu().numpy()
    return actions


def flatten_batch(
    arrays: dict[str, np.ndarray],
    teacher_actions: np.ndarray,
    *,
    episode_base: int,
) -> dict[str, np.ndarray]:
    batch, steps = teacher_actions.shape
    flattened = {
        key: arrays[key].reshape(batch * steps, *arrays[key].shape[2:])
        for key in ARRAY_KEYS
    }
    expert = teacher_actions.reshape(-1)
    placement = expert < 4 * NUM_TILES
    flattened.update(
        expert_actions=expert,
        expert_action_supervision_valid=np.ones(expert.shape, dtype=np.bool_),
        expert_card_supervision_valid=placement,
        expert_tile_supervision_valid=placement,
        episode_ids=np.repeat(
            np.arange(episode_base, episode_base + batch, dtype=np.int64),
            steps,
        ),
        source_frames=np.tile(np.arange(steps, dtype=np.int64), batch),
    )
    return flattened


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--student-checkpoint", type=Path, required=True)
    parser.add_argument("--teacher-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--steps", type=int, default=96)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument(
        "--opponents",
        default=(
            "balanced,bridge-pressure,reactive-defense,spell-control,"
            "slow-push,split-lane,random"
        ),
    )
    args = parser.parse_args()
    if args.output.exists() or args.manifest.exists():
        raise SystemExit("refusing to overwrite DAgger output")
    if args.batch_size < 1 or args.steps < 2:
        raise ValueError("batch size and steps are invalid")
    opponents = tuple(value.strip() for value in args.opponents.split(",") if value)
    if not opponents:
        raise ValueError("at least one opponent is required")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    parts: dict[str, list[np.ndarray]] = {}
    diagnostics: list[dict[str, Any]] = []
    episode_base = 0
    student_payload = torch.load(
        args.student_checkpoint, map_location="cpu", weights_only=False
    )
    token_names = tuple(student_payload["token_names"])
    teacher: ClasherPolicy | None = None
    max_entities = int(student_payload["model_config"]["max_entities"])

    for index, opponent in enumerate(opponents):
        collector_args = argparse.Namespace(
            checkpoint=args.student_checkpoint,
            output=Path("unused.json"),
            seed=args.seed + index,
            batch_size=args.batch_size,
            warmup_steps=0,
            horizon_steps=1,
            action_samples=args.batch_size,
            random_candidate_fraction=0.25,
            opponent_strategy=opponent,
            device=args.device,
            state_output=None,
        )
        torch.manual_seed(args.seed + index)
        collector = load_collector(collector_args, batch_size=args.batch_size)
        base_policy = collector.collector.policy
        collector.collector.policy = ForcedLearnerRootPolicy(
            base_policy,
            learner_players=collector.learner_players,
            root_actions=None,
        )
        state = collector.policy.model.initial_state(
            args.batch_size, device=device
        )
        arrays, *_tail = collector.collect(args.steps, state)
        selected = {key: np.asarray(arrays[key]).copy() for key in ARRAY_KEYS}
        pack_entities(selected)
        if teacher is None:
            teacher = load_teacher(
                args.teacher_checkpoint,
                token_names=token_names,
                device=device,
            )
        teacher_actions = label_teacher_actions(teacher, selected, device=device)
        student_actions = np.asarray(arrays["actions"])
        legal = selected["action_masks"].reshape(-1, teacher.num_actions)
        if not bool(
            legal[np.arange(legal.shape[0]), teacher_actions.reshape(-1)].all()
        ):
            raise RuntimeError("teacher emitted an action outside the public mask")
        flat = flatten_batch(
            selected,
            teacher_actions,
            episode_base=episode_base,
        )
        episode_base += args.batch_size
        for key, value in flat.items():
            parts.setdefault(key, []).append(value)
        diagnostics.append(
            {
                "opponent": opponent,
                "rows": int(teacher_actions.size),
                "teacher_student_disagreement": float(
                    (teacher_actions != student_actions).mean()
                ),
                "teacher_play_rate": float((teacher_actions < 4 * NUM_TILES).mean()),
                "student_play_rate": float((student_actions < 4 * NUM_TILES).mean()),
            }
        )

    combined = {key: np.concatenate(values, axis=0) for key, values in parts.items()}
    metadata = {
        "schema_version": 1,
        "created_at": "2026-08-30T00:00:00+00:00",
        "seed": args.seed,
        "decisions": int(combined["expert_actions"].size),
        "samples": int(combined["expert_actions"].size),
        "decision_interval": 8,
        "max_ticks": 6000,
        "planner_depth": 0,
        "planner_simulations": 0,
        "planner_action_samples": 0,
        "max_entities": max_entities,
        "token_names": list(token_names),
        "reward_profile": "objective-v1",
        "workers": 1,
        "behavior_checkpoint": str(args.student_checkpoint.resolve()),
        "expert_probability": 1.0,
        "stable_root_candidates": False,
        "behavior_opponent": "mixed-strategy-and-random",
        "label_source": "on-policy-dagger-hazard-parent",
        "label_strategy": None,
        "label_checkpoint": str(args.teacher_checkpoint.resolve()),
        "label_checkpoint_sha256": file_sha256(args.teacher_checkpoint),
        "sampling_decks_path": None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        **combined,
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
    )
    manifest = {
        "schema": "clasher.hog26.playgate-dagger-corpus.v1",
        "student_checkpoint": str(args.student_checkpoint.resolve()),
        "student_checkpoint_sha256": file_sha256(args.student_checkpoint),
        "teacher_checkpoint": str(args.teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": file_sha256(args.teacher_checkpoint),
        "seed": args.seed,
        "batch_size": args.batch_size,
        "steps": args.steps,
        "opponents": list(opponents),
        "rows": int(combined["expert_actions"].size),
        "episodes": episode_base,
        "diagnostics": diagnostics,
        "corpus": str(args.output.resolve()),
        "corpus_sha256": file_sha256(args.output),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
