"""Build recurrent imitation tensors from verified TV Royale public records.

The conversion is intentionally one-way: current-frame public measurements and
the actor's own HUD become policy inputs, while reviewed play labels remain a
separate supervision stream.  No label is ever used to repair a public action
mask.  Rows whose reviewed action is outside the camera-derived mask stay in
the recurrent sequence but are explicitly unsupervised.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .eval import load_policy_checkpoint
from .imitation import (
    CORPUS_SCHEMA_VERSION,
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    CorpusMetadata,
)
from .live_inference_contract import PublicVisionFrame, VisionEntity
from .oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from .public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
)
from .public_observation import REAL_PLAY_FEATURE_CONTRACT_VERSION
from .structured_live_adapter import StructuredLiveInferenceAdapter

CORPUS_MANIFEST_SCHEMA = "clasher.youtube.causal_imitation_corpus.v1"
NO_OP_ACTION = 4 * 18 * 32
_KIND_BY_NAMESPACE = {
    "troop_body": "troop",
    "building_body": "building",
    "tower": "building",
    "projectile": "projectile",
    "area_effect": "area_effect",
}


@dataclass(frozen=True)
class CausalCorpusBuildConfig:
    audit_path: Path
    schema_checkpoint: Path
    decks_path: Path
    output_corpus: Path
    output_sidecar: Path
    output_manifest: Path
    seed: int
    maximum_replays: int | None = None


def _json_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _artifact_path(manifest_path: Path, value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _unit(value: object) -> float:
    try:
        result = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(result):
        return 0.0
    return float(np.clip(result, 0.0, 1.0))


def _accepted_hud_card(head: object) -> tuple[str, float]:
    if not isinstance(head, dict) or head.get("valid") is not True:
        return "<unknown>", 0.0
    value = head.get("value")
    if not isinstance(value, str) or not value or value == "empty":
        return "<unknown>", 0.0
    confidence = _unit(head.get("score", 0.0))
    if confidence <= 0.0:
        return "<unknown>", 0.0
    return value, confidence


def public_frame_from_records(
    neutral: dict[str, Any],
    overlay: dict[str, Any],
    *,
    actor_id: int,
) -> PublicVisionFrame:
    """Project one neutral snapshot plus one private-safe actor HUD.

    The portable clock currently recognizes the displayed countdown but has no
    replay-disjoint current-frame overtime-phase head.  It is therefore used
    only as a supervision-validity gate by the corpus builder and is not
    converted into a fabricated elapsed-time input here.  The policy's clock is
    model-owned until that missing visual phase contract is proven.
    """

    if actor_id not in {0, 1}:
        raise ValueError("actor_id must be zero or one")
    if overlay.get("snapshot_id") != neutral.get("snapshot_id"):
        raise ValueError("actor overlay does not match neutral snapshot")
    if int(overlay.get("actor_id", -1)) != actor_id:
        raise ValueError("actor overlay perspective changed")
    hud = overlay.get("own_hud")
    if not isinstance(hud, dict):
        raise TypeError("actor overlay has no own HUD")
    raw_hand = hud.get("hand")
    if not isinstance(raw_hand, list) or len(raw_hand) != 4:
        raise ValueError("actor HUD must retain four physical hand slots")
    hand = [_accepted_hud_card(head) for head in raw_hand]
    next_card, next_confidence = _accepted_hud_card(hud.get("next_card"))
    elixir = hud.get("elixir")
    if (
        isinstance(elixir, dict)
        and elixir.get("valid") is True
        and isinstance(elixir.get("value"), int | float)
    ):
        own_elixir: float | None = float(np.clip(float(elixir["value"]), 0.0, 10.0))
        own_elixir_confidence = _unit(elixir.get("score", 0.0))
        if own_elixir_confidence <= 0.0:
            own_elixir = None
    else:
        own_elixir = None
        own_elixir_confidence = 0.0

    entities: list[VisionEntity] = []
    public = neutral.get("public")
    if not isinstance(public, dict):
        raise TypeError("neutral row has no public state")
    raw_entities = public.get("entities")
    if not isinstance(raw_entities, list):
        raise TypeError("neutral public entities must be a list")
    for index, raw in enumerate(raw_entities):
        if not isinstance(raw, dict):
            continue
        identity = raw.get("identity")
        position = raw.get("world_position")
        if not isinstance(identity, dict) or identity.get("valid") is not True:
            continue
        stable_key = identity.get("stable_key")
        if not isinstance(stable_key, str) or ":" not in stable_key:
            continue
        namespace, card = stable_key.split(":", 1)
        kind = _KIND_BY_NAMESPACE.get(namespace)
        if kind is None or not isinstance(position, list) or len(position) != 2:
            continue
        try:
            x_tiles = float(position[0])
            y_tiles = float(position[1])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(x_tiles) or not np.isfinite(y_tiles):
            continue
        confidence = _unit(raw.get("confidence", 0.0))
        if confidence <= 0.0:
            continue
        hp = raw.get("hp_fraction")
        if raw.get("hp_valid") is True and isinstance(hp, int | float):
            hp_fraction: float | None = _unit(hp)
            hp_confidence = _unit(raw.get("hp_confidence", 0.0))
            if hp_confidence <= 0.0:
                hp_fraction = None
        else:
            hp_fraction = None
            hp_confidence = 0.0
        team_id = int(raw.get("team_id", -1))
        if team_id not in {0, 1}:
            continue
        entities.append(
            VisionEntity(
                track_id=f"{neutral['snapshot_id']}:entity:{index}",
                card=card,
                kind=kind,
                player_id=team_id,
                x_tiles=x_tiles,
                y_tiles=y_tiles,
                confidence=confidence,
                hp_fraction=hp_fraction,
                hp_confidence=hp_confidence,
                statuses=(),
            )
        )

    return PublicVisionFrame(
        episode_id=f"{neutral['split_group_id']}:actor:{actor_id}",
        frame_id=str(neutral["snapshot_id"]),
        timestamp_ms=int(neutral["timestamp_ms"]),
        visible_clock_seconds=None,
        clock_confidence=0.0,
        own_elixir=own_elixir,
        own_elixir_confidence=own_elixir_confidence,
        own_hand=tuple(card for card, _ in hand),
        own_hand_confidence=tuple(confidence for _, confidence in hand),
        own_next_card=None if next_confidence <= 0.0 else next_card,
        own_next_card_confidence=next_confidence,
        entities=tuple(entities),
        play_events=(),
    )


def _stack(values: list[np.ndarray], *, name: str) -> np.ndarray:
    if not values:
        raise ValueError(f"causal corpus has no {name} rows")
    return np.stack(values, axis=0)


def _read_actor_rows(
    manifest_path: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    artifacts = manifest["artifacts"]
    neutral_path = _artifact_path(manifest_path, artifacts["neutral_sequence"]["path"])
    neutral_rows = _json_rows(neutral_path)
    neutral = {str(row["snapshot_id"]): row for row in neutral_rows}
    actors: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for artifact in artifacts["actor_trajectories"]:
        actor_id = int(artifact["actor_id"])
        if actor_id not in actors:
            raise ValueError("actor artifact has invalid perspective")
        actors[actor_id] = _json_rows(
            _artifact_path(manifest_path, artifact["path"])
        )
    return neutral, actors


def build_causal_imitation_corpus(config: CausalCorpusBuildConfig) -> dict[str, Any]:
    audit = json.loads(config.audit_path.read_text(encoding="utf-8"))
    if audit.get("decision") != "ready_for_fresh_causal_bc":
        raise ValueError("causal corpus audit has not passed its collection gate")
    matches = list(audit.get("matches", ()))
    if config.maximum_replays is not None:
        if config.maximum_replays <= 0:
            raise ValueError("maximum_replays must be positive")
        matches = matches[: config.maximum_replays]
    if not matches:
        raise ValueError("causal corpus audit contains no matches")

    loaded = load_policy_checkpoint(
        config.schema_checkpoint,
        device=torch.device("cpu"),
        decks_path=config.decks_path,
    )
    mask_builder = PublicActionMaskBuilder(loaded.builder)
    adapters = {
        actor_id: StructuredLiveInferenceAdapter(
            model=loaded.model,
            token_names=loaded.builder.token_names,
            public_action_mask_builder=mask_builder,
            actor_id=actor_id,
            cadence_ms=200,
            maximum_gap_intervals=2,
            deterministic=True,
            device="cpu",
        )
        for actor_id in (0, 1)
    }

    base_lists: dict[str, list[Any]] = {
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
            "expert_action_supervision_valid",
            "source_frames",
            "source_replays",
            "source_actor_ids",
            "source_snapshots",
        )
    }
    confidence_lists: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
        )
    }
    expert_action_masked: list[bool] = []
    target_mask_disagreement_examples: list[dict[str, Any]] = []
    legacy_mask_disagreement_examples: list[dict[str, Any]] = []
    episode_id = -1
    counts: dict[str, int] = {
        "replays": 0,
        "actor_episodes": 0,
        "recurrent_segments": 0,
        "rows": 0,
        "clock_valid_rows": 0,
        "nontrivial_mask_rows": 0,
        "reviewed_targets": 0,
        "supervised_play_targets": 0,
        "masked_play_targets": 0,
        "clock_missing_play_targets": 0,
        "supervised_wait_targets": 0,
        "unsupervised_context_rows": 0,
        "unaligned_public_plays": 0,
        "legacy_mask_row_mismatches": 0,
        "legacy_mask_bit_mismatches": 0,
        "typed_target_mask_disagreements": 0,
        "unknown_entity_tracks": 0,
        "cadence_resets": 0,
    }

    for match in matches:
        manifest_path = Path(match["manifest"]["path"]).resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        neutral, actor_rows = _read_actor_rows(manifest_path, manifest)
        artifacts = manifest["artifacts"]
        targets = json.loads(
            _artifact_path(
                manifest_path, artifacts["offline_actor_targets"]["path"]
            ).read_text(encoding="utf-8")
        )
        events = json.loads(
            _artifact_path(
                manifest_path, artifacts["offline_play_events"]["path"]
            ).read_text(encoding="utf-8")
        )
        target_by_key: dict[tuple[int, str], dict[str, Any]] = {}
        target_event_ids: set[str] = set()
        for target in targets:
            key = (int(target["actor_id"]), str(target["snapshot_id"]))
            if key in target_by_key:
                raise ValueError("multiple reviewed actions share one actor snapshot")
            target_by_key[key] = target
            target_event_ids.add(str(target["event_id"]))
        unaligned_times: dict[int, list[int]] = {0: [], 1: []}
        for event in events:
            if not event.get("play_valid"):
                continue
            if str(event.get("event_id")) in target_event_ids:
                continue
            actor_id = int(event["player_id"])
            unaligned_times[actor_id].append(int(event["timestamp_ms"]))
        counts["replays"] += 1
        counts["reviewed_targets"] += len(targets)
        counts["unaligned_public_plays"] += sum(
            len(values) for values in unaligned_times.values()
        )

        for actor_id in (0, 1):
            rows = actor_rows[actor_id]
            rows.sort(key=lambda row: int(neutral[str(row["snapshot_id"])]["timestamp_ms"]))
            if not rows:
                continue
            counts["actor_episodes"] += 1
            adapter = adapters[actor_id]
            adapter.reset(f"{manifest['source']['video_sha256']}:actor:{actor_id}")
            previous_action = NO_OP_ACTION
            last_timestamp: int | None = None
            pending_unaligned = sorted(unaligned_times[actor_id])
            episode_start = True
            episode_id += 1
            counts["recurrent_segments"] += 1

            for overlay in rows:
                snapshot_id = str(overlay["snapshot_id"])
                current_neutral = neutral[snapshot_id]
                timestamp = int(current_neutral["timestamp_ms"])
                crossed_unknown_play = bool(
                    pending_unaligned
                    and (last_timestamp is None or pending_unaligned[0] > last_timestamp)
                    and pending_unaligned[0] <= timestamp
                )
                while pending_unaligned and pending_unaligned[0] <= timestamp:
                    pending_unaligned.pop(0)
                cadence_gap = (
                    last_timestamp is not None and timestamp - last_timestamp > 400
                )
                if not episode_start and (crossed_unknown_play or cadence_gap):
                    episode_id += 1
                    counts["recurrent_segments"] += 1
                    counts["cadence_resets"] += 1
                    previous_action = NO_OP_ACTION
                    episode_start = True
                frame = public_frame_from_records(
                    current_neutral, overlay, actor_id=actor_id
                )
                # The adapter requires its own episode identifier.  Its state is
                # not advanced during corpus projection, so reset only changes
                # the boundary validation metadata.
                frame = PublicVisionFrame(
                    episode_id=f"{manifest['source']['video_sha256']}:actor:{actor_id}",
                    frame_id=frame.frame_id,
                    timestamp_ms=frame.timestamp_ms,
                    visible_clock_seconds=frame.visible_clock_seconds,
                    clock_confidence=frame.clock_confidence,
                    own_elixir=frame.own_elixir,
                    own_elixir_confidence=frame.own_elixir_confidence,
                    own_hand=frame.own_hand,
                    own_hand_confidence=frame.own_hand_confidence,
                    own_next_card=frame.own_next_card,
                    own_next_card_confidence=frame.own_next_card_confidence,
                    entities=frame.entities,
                    play_events=frame.play_events,
                )
                prepared = adapter.prepare_current_frame(frame)
                inputs = prepared.inputs
                if (
                    inputs.entity_id_confidence is None
                    or inputs.entity_feature_confidence is None
                    or inputs.hand_id_confidence is None
                    or inputs.global_feature_confidence is None
                ):
                    raise ValueError("live adapter omitted required confidence tensors")
                action_mask = prepared.action_mask.astype(np.bool_, copy=True)
                stored_mask = np.zeros_like(action_mask)
                stored_mask[
                    np.asarray(
                        overlay["public_action_mask"]["legal_action_indices"],
                        dtype=np.int64,
                    )
                ] = True
                differing_bits = int(np.count_nonzero(action_mask != stored_mask))
                if differing_bits:
                    counts["legacy_mask_row_mismatches"] += 1
                    counts["legacy_mask_bit_mismatches"] += differing_bits
                    if len(legacy_mask_disagreement_examples) < 16:
                        legacy_mask_disagreement_examples.append(
                            {
                                "video_sha256": manifest["source"]["video_sha256"],
                                "actor_id": actor_id,
                                "snapshot_id": snapshot_id,
                                "differing_bits": differing_bits,
                                "typed_legal_actions": int(np.count_nonzero(action_mask)),
                                "legacy_legal_actions": int(np.count_nonzero(stored_mask)),
                            }
                        )

                target = target_by_key.get((actor_id, snapshot_id))
                if target is None:
                    expert_action = NO_OP_ACTION
                else:
                    expert_action = int(target["expert_action"])
                    if not 0 <= expert_action < action_mask.size:
                        raise ValueError("reviewed expert action is outside action space")
                    if bool(target["expert_action_in_public_mask"]) != bool(
                        action_mask[expert_action]
                    ):
                        counts["typed_target_mask_disagreements"] += 1
                        target_mask_disagreement_examples.append(
                            {
                                "video_sha256": manifest["source"]["video_sha256"],
                                "actor_id": actor_id,
                                "snapshot_id": snapshot_id,
                                "event_id": target["event_id"],
                                "card_identity": target["card_identity"],
                                "expert_action": expert_action,
                                "legacy_in_mask": bool(
                                    target["expert_action_in_public_mask"]
                                ),
                                "typed_in_mask": bool(action_mask[expert_action]),
                            }
                        )
                clock_valid = bool(current_neutral["public"]["clock"]["valid"])
                nontrivial = int(np.count_nonzero(action_mask)) > 1
                if target is not None:
                    supervision_valid = bool(action_mask[expert_action] and clock_valid)
                    if supervision_valid:
                        counts["supervised_play_targets"] += 1
                    elif not action_mask[expert_action]:
                        counts["masked_play_targets"] += 1
                    else:
                        counts["clock_missing_play_targets"] += 1
                else:
                    supervision_valid = bool(clock_valid and nontrivial)
                    if supervision_valid:
                        counts["supervised_wait_targets"] += 1
                if not supervision_valid:
                    counts["unsupervised_context_rows"] += 1
                counts["clock_valid_rows"] += int(clock_valid)
                counts["nontrivial_mask_rows"] += int(nontrivial)
                counts["unknown_entity_tracks"] += len(
                    prepared.diagnostics["unknown_entity_track_ids"]
                )

                tensor_arrays = {
                    "entity_ids": inputs.entity_ids[0, 0].detach().cpu().numpy(),
                    "entity_features": inputs.entity_features[0, 0].detach().cpu().numpy(),
                    "entity_mask": inputs.entity_mask[0, 0].detach().cpu().numpy(),
                    "hand_ids": inputs.hand_ids[0, 0].detach().cpu().numpy(),
                    "global_features": inputs.global_features[0, 0].detach().cpu().numpy(),
                    "entity_id_confidence": inputs.entity_id_confidence[0, 0].detach().cpu().numpy(),
                    "entity_feature_confidence": inputs.entity_feature_confidence[0, 0].detach().cpu().numpy(),
                    "hand_id_confidence": inputs.hand_id_confidence[0, 0].detach().cpu().numpy(),
                    "global_feature_confidence": inputs.global_feature_confidence[0, 0].detach().cpu().numpy(),
                }
                for name in (
                    "entity_ids",
                    "entity_features",
                    "entity_mask",
                    "hand_ids",
                    "global_features",
                ):
                    base_lists[name].append(tensor_arrays[name].copy())
                base_lists["action_masks"].append(action_mask)
                base_lists["previous_actions"].append(previous_action)
                base_lists["previous_rewards"].append(0.0)
                base_lists["episode_starts"].append(episode_start)
                base_lists["expert_actions"].append(expert_action)
                base_lists["episode_ids"].append(episode_id)
                base_lists["expert_action_supervision_valid"].append(
                    supervision_valid
                )
                base_lists["source_frames"].append(int(current_neutral["sample_index"]))
                base_lists["source_replays"].append(str(manifest["source"]["video_sha256"]))
                base_lists["source_actor_ids"].append(actor_id)
                base_lists["source_snapshots"].append(snapshot_id)
                for name, values in confidence_lists.items():
                    values.append(tensor_arrays[name].copy())
                expert_action_masked.append(not bool(action_mask[expert_action]))
                counts["rows"] += 1
                previous_action = expert_action if target is not None else NO_OP_ACTION
                episode_start = False
                last_timestamp = timestamp

    base_arrays: dict[str, np.ndarray] = {
        "entity_ids": _stack(base_lists["entity_ids"], name="entity_ids").astype(np.int64),
        "entity_features": _stack(base_lists["entity_features"], name="entity_features").astype(np.float32),
        "entity_mask": _stack(base_lists["entity_mask"], name="entity_mask").astype(np.bool_),
        "hand_ids": _stack(base_lists["hand_ids"], name="hand_ids").astype(np.int64),
        "global_features": _stack(base_lists["global_features"], name="global_features").astype(np.float32),
        "action_masks": _stack(base_lists["action_masks"], name="action_masks").astype(np.bool_),
        "previous_actions": np.asarray(base_lists["previous_actions"], dtype=np.int64),
        "previous_rewards": np.asarray(base_lists["previous_rewards"], dtype=np.float32),
        "episode_starts": np.asarray(base_lists["episode_starts"], dtype=np.bool_),
        "expert_actions": np.asarray(base_lists["expert_actions"], dtype=np.int64),
        "episode_ids": np.asarray(base_lists["episode_ids"], dtype=np.int64),
        "expert_action_supervision_valid": np.asarray(
            base_lists["expert_action_supervision_valid"], dtype=np.bool_
        ),
        "source_frames": np.asarray(base_lists["source_frames"], dtype=np.int64),
        "source_replays": np.asarray(base_lists["source_replays"], dtype=np.str_),
        "source_actor_ids": np.asarray(
            base_lists["source_actor_ids"], dtype=np.int8
        ),
        "source_snapshots": np.asarray(
            base_lists["source_snapshots"], dtype=np.str_
        ),
    }
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=config.seed,
        decisions=counts["rows"],
        samples=counts["rows"],
        decision_interval=4,
        max_ticks=6000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=int(loaded.model.config.max_entities),
        token_names=tuple(loaded.builder.token_names),
        workers=1,
        behavior_checkpoint=None,
        expert_probability=1.0,
        stable_root_candidates=False,
        behavior_opponent=None,
        label_source="youtube-human",
        label_strategy=None,
        sampling_decks_path=None,
    )
    atomic_save_npz(
        config.output_corpus,
        {**base_arrays, "metadata_json": np.asarray(metadata.to_json())},
    )
    sidecar: dict[str, np.ndarray] = {
        "schema_version": np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION),
        "feature_contract_version": np.asarray(REAL_PLAY_FEATURE_CONTRACT_VERSION),
        "action_mask_contract_version": np.asarray(
            PUBLIC_ACTION_MASK_CONTRACT_VERSION
        ),
        "entity_ids": base_arrays["entity_ids"],
        "entity_features": base_arrays["entity_features"],
        "entity_mask": base_arrays["entity_mask"],
        "entity_id_confidence": _stack(
            confidence_lists["entity_id_confidence"], name="entity_id_confidence"
        ).astype(np.float32),
        "entity_feature_confidence": _stack(
            confidence_lists["entity_feature_confidence"],
            name="entity_feature_confidence",
        ).astype(np.float32),
        "hand_ids": base_arrays["hand_ids"],
        "hand_id_confidence": _stack(
            confidence_lists["hand_id_confidence"], name="hand_id_confidence"
        ).astype(np.float32),
        "global_features": base_arrays["global_features"],
        "global_feature_confidence": _stack(
            confidence_lists["global_feature_confidence"],
            name="global_feature_confidence",
        ).astype(np.float32),
        "action_masks": base_arrays["action_masks"],
        "expert_action_masked": np.asarray(expert_action_masked, dtype=np.bool_),
        "expert_actions": base_arrays["expert_actions"],
        "episode_ids": base_arrays["episode_ids"],
        "source_frames": base_arrays["source_frames"],
    }
    atomic_save_npz(config.output_sidecar, sidecar)
    manifest_payload: dict[str, Any] = {
        "schema": CORPUS_MANIFEST_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": config.seed,
        "source_audit": {
            "path": str(config.audit_path.resolve()),
            "sha256": file_sha256(config.audit_path),
            "decision": audit["decision"],
            "selected_replays": len(matches),
        },
        "schema_checkpoint": {
            "path": str(config.schema_checkpoint.resolve()),
            "sha256": file_sha256(config.schema_checkpoint),
            "token_count": len(loaded.builder.token_names),
            "max_entities": int(loaded.model.config.max_entities),
        },
        "artifacts": {
            "corpus": {
                "path": str(config.output_corpus.resolve()),
                "sha256": file_sha256(config.output_corpus),
                "rows": counts["rows"],
            },
            "public_observation_sidecar": {
                "path": str(config.output_sidecar.resolve()),
                "sha256": file_sha256(config.output_sidecar),
                "rows": counts["rows"],
            },
        },
        "counts": counts,
        "diagnostics": {
            "target_mask_disagreement_examples": target_mask_disagreement_examples,
            "legacy_mask_disagreement_examples": legacy_mask_disagreement_examples,
        },
        "contracts": {
            "actor_inputs": "current_public_frame_plus_own_hud_only",
            "mask": "typed_current_client_label_independent_public_mask_v2",
            "masked_reviewed_actions": "recurrent_context_only_unsupervised",
            "previous_actions": "past_reviewed_executed_action_or_noop",
            "previous_rewards": "always_zero",
            "unknown_public_play": "typed_recurrent_reset",
            "clock_input": "model_owned_only_until_current_frame_overtime_phase_is_proven",
            "offline_targets_in_actor_input": False,
            "exact_simulator_state_used": False,
            "opponent_private_hud_used": False,
        },
    }
    atomic_write_json(config.output_manifest, manifest_payload)
    return manifest_payload
