from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import copy
import gzip
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    StructuredObservationBuilder,
)
from scripts.extract_tv_royale_youtube_fullmatch import (
    _atomic_gzip_jsonl,
    _atomic_json,
    _sha256,
)

MASK_SCHEMA = "clasher.youtube.public_action_mask.v2"
MANIFEST_SCHEMA = "clasher.youtube.fullmatch.extraction_manifest.v3"
ACTOR_SCHEMA = "clasher.youtube.fullmatch.actor_trajectory.v1"
ACTOR_OVERLAY_SCHEMA = "clasher.youtube.fullmatch.actor_overlay.v1"
NOOP_ACTION = 4 * 18 * 32
CYCLE_EVENT_SCHEMA = "clasher.youtube.hud_cycle_events.v3"


def _rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _stage_input(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == destination:
        return destination
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        with source.open("rb") as input_file, temporary_path.open("wb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    if _sha256(source) != _sha256(destination):
        destination.unlink(missing_ok=True)
        raise ValueError("staged input artifact hash mismatch")
    return destination


def normalize_offline_events(payload: object) -> tuple[list[dict[str, Any]], str]:
    """Normalize legacy marker events or precision-gated visual cycle events.

    Cycle events become action targets only when every independent causal label
    gate passed.  The conversion never repairs a rejected label or changes its
    card, slot, or tile.
    """
    if isinstance(payload, list):
        if not all(isinstance(row, dict) for row in payload):
            raise ValueError("legacy offline events must be JSON objects")
        return [copy.deepcopy(row) for row in payload], "legacy_offline_play_events"
    if not isinstance(payload, dict) or payload.get("schema") != CYCLE_EVENT_SCHEMA:
        raise ValueError("unsupported offline event payload")
    rows = payload.get("events")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("cycle event payload must contain object rows")
    normalized: list[dict[str, Any]] = []
    for source in rows:
        row = copy.deepcopy(source)
        row["play_valid"] = bool(
            row.get("play_confirmed")
            and row.get("identity_valid")
            and row.get("placement_valid")
            and row.get("public_cost_valid")
            and row.get("offline_label_only")
        )
        normalized.append(row)
    return normalized, "precision_gated_hud_cycle_events_v3"


def compact_actor_record(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("schema") != ACTOR_SCHEMA:
        raise ValueError("only actor trajectory v1 rows can be compacted")
    return {
        "schema": ACTOR_OVERLAY_SCHEMA,
        "snapshot_id": row["snapshot_id"],
        "actor_id": row["actor_id"],
        "own_hud": copy.deepcopy(row["own_hud"]),
        "public_action_mask": copy.deepcopy(row["public_action_mask"]),
        "label_validity": copy.deepcopy(row["label_validity"]),
    }


def expand_actor_overlay(
    overlay: dict[str, Any], neutral: dict[str, Any]
) -> dict[str, Any]:
    if overlay.get("schema") != ACTOR_OVERLAY_SCHEMA:
        raise ValueError("unsupported actor overlay schema")
    actor_id = int(overlay["actor_id"])
    if overlay.get("snapshot_id") != neutral.get("snapshot_id"):
        raise ValueError("actor overlay snapshot does not match neutral state")
    return {
        "schema": ACTOR_SCHEMA,
        "match_id": neutral["match_id"],
        "split_group_id": neutral["split_group_id"],
        "snapshot_id": neutral["snapshot_id"],
        "output_pts": neutral["output_pts"],
        "output_time_base": neutral["output_time_base"],
        "source_time_base": neutral["source_time_base"],
        "timestamp_ms": neutral["timestamp_ms"],
        "actor_id": actor_id,
        "public": copy.deepcopy(neutral["public"]),
        "own_hud": copy.deepcopy(overlay["own_hud"]),
        "public_action_mask": copy.deepcopy(overlay["public_action_mask"]),
        "label_validity": copy.deepcopy(overlay["label_validity"]),
    }


def build_public_mask_builder(
    vocabulary_manifest: Path,
) -> tuple[StructuredObservationBuilder, PublicActionMaskBuilder]:
    vocabulary = json.loads(vocabulary_manifest.read_text())
    card_roots = sorted(
        row["canonical_name"]
        for row in vocabulary["entries"]
        if row["namespace"] == "card_action"
        and row["loader_definition"]
        and not row["not_visible"]
    )
    builder = StructuredObservationBuilder(card_vocab=card_roots, max_entities=128)
    return builder, PublicActionMaskBuilder(builder)


def _token_name(stable_key: object) -> str | None:
    if not isinstance(stable_key, str) or ":" not in stable_key:
        return None
    return stable_key.split(":", 1)[1]


def mask_input_from_actor_record(
    record: dict[str, Any],
    *,
    actor_id: int,
    builder: StructuredObservationBuilder,
) -> PublicActionMaskInput:
    if actor_id not in {0, 1}:
        raise ValueError("actor_id must be zero or one")
    own_hud = record["offline_privileged_hud"][str(actor_id)]
    hand_ids: np.ndarray = np.zeros((4,), dtype=np.int64)
    hand_confidence: np.ndarray = np.zeros((4,), dtype=np.float32)
    for slot, head in enumerate(own_hud["hand"]):
        name = _token_name(head.get("value")) if head.get("valid") else None
        token = builder.token_id(name)
        if name is None or token <= 1:
            continue
        hand_ids[slot] = token
        hand_confidence[slot] = float(head.get("score", 0.0))

    global_features = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
    global_confidence = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
    elixir = own_hud["elixir"]
    if elixir.get("valid") and isinstance(elixir.get("value"), int | float):
        global_features[5] = float(np.clip(float(elixir["value"]) / 10.0, 0.0, 1.0))
        global_confidence[5] = float(elixir.get("score", 0.0))

    entity_ids: np.ndarray = np.zeros((128,), dtype=np.int64)
    entity_features = np.zeros((128, ENTITY_FEATURE_SIZE), dtype=np.float32)
    entity_mask: np.ndarray = np.zeros((128,), dtype=np.bool_)
    entity_confidence: np.ndarray = np.zeros((128,), dtype=np.float32)
    cursor = 0
    kind_feature = {
        "troop_body": 4,
        "building_body": 5,
        "tower": 5,
        "projectile": 6,
        "area_effect": 7,
    }
    for entity in record["public"]["entities"]:
        if cursor >= 128:
            break
        identity = entity.get("identity", {})
        stable_key = identity.get("stable_key") if identity.get("valid") else None
        name = _token_name(stable_key)
        position = entity.get("world_position")
        if name is None or not isinstance(position, list) or len(position) != 2:
            continue
        token = builder.token_id(name)
        if token <= 1:
            continue
        namespace = str(stable_key).split(":", 1)[0]
        feature_index = kind_feature.get(namespace)
        if feature_index is None:
            continue
        world_x, world_y = float(position[0]), float(position[1])
        if actor_id == 1:
            world_x, world_y = 18.0 - world_x, 32.0 - world_y
        row = entity_features[cursor]
        row[0] = float(np.clip(world_x / 18.0, 0.0, 1.0))
        row[1] = float(np.clip(world_y / 32.0, 0.0, 1.0))
        own = int(entity.get("team_id", -1)) == actor_id
        row[2] = float(own)
        row[3] = float(not own)
        row[feature_index] = 1.0
        hp = entity.get("hp_fraction")
        if entity.get("hp_valid") and isinstance(hp, int | float):
            row[9] = float(np.clip(float(hp), 0.0, 1.0))
        entity_ids[cursor] = token
        entity_mask[cursor] = True
        entity_confidence[cursor] = float(entity.get("confidence", 0.0))
        cursor += 1

    return PublicActionMaskInput(
        entity_ids=entity_ids,
        entity_features=entity_features,
        entity_mask=entity_mask,
        hand_ids=hand_ids,
        global_features=global_features,
        entity_id_confidence=entity_confidence,
        hand_id_confidence=hand_confidence,
        global_feature_confidence=global_confidence,
    )


def build_actor_mask(
    record: dict[str, Any],
    *,
    actor_id: int,
    builder: StructuredObservationBuilder,
    mask_builder: PublicActionMaskBuilder,
) -> dict[str, Any]:
    source = mask_input_from_actor_record(record, actor_id=actor_id, builder=builder)
    mask = mask_builder.build(source)
    legal = np.flatnonzero(mask).astype(np.int64).tolist()
    return {
        "schema": MASK_SCHEMA,
        "contract": "label_independent_public_action_mask_v2",
        "contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "source": "current_public_frame_and_own_hud_only",
        "legal_action_indices": legal,
        "valid": True,
        "non_noop_legal_actions": sum(action != NOOP_ACTION for action in legal),
    }


def _attach_labels(
    actor_rows: dict[int, list[dict[str, Any]]], events: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    aligned = 0
    legal = 0
    unaligned = 0
    targets: list[dict[str, Any]] = []
    for event in events:
        if not event.get("play_valid"):
            continue
        actor_id = int(event["player_id"])
        event_time = int(event["timestamp_ms"])
        card = event["card_identity"]
        candidates = [
            row
            for row in actor_rows[actor_id]
            if event_time - 1_000 <= int(row["timestamp_ms"]) <= event_time
            and any(
                head.get("valid") and head.get("value") == card
                for head in row["own_hud"]["hand"]
            )
        ]
        if not candidates:
            unaligned += 1
            continue
        row = max(candidates, key=lambda item: int(item["timestamp_ms"]))
        slot = next(
            index
            for index, head in enumerate(row["own_hud"]["hand"])
            if head.get("valid") and head.get("value") == card
        )
        tile_x, tile_y = event["deployment_tile_actor_canonical"]
        action = slot * 18 * 32 + int(tile_y) * 18 + int(tile_x)
        in_mask = action in row["public_action_mask"]["legal_action_indices"]
        target = {
            "schema": "clasher.youtube.offline_action_target.v1",
            "match_id": row["match_id"],
            "snapshot_id": row["snapshot_id"],
            "split_group_id": row["split_group_id"],
            "actor_id": actor_id,
            "event_id": event["event_id"],
            "source_timestamp_ms": event_time,
            "card_identity": card,
            "hand_slot": slot,
            "deployment_tile_actor_canonical": [tile_x, tile_y],
            "expert_action": action,
            "expert_action_in_public_mask": in_mask,
            "offline_label_only": True,
        }
        targets.append(target)
        aligned += 1
        legal += int(in_mask)
    return (
        {
            "valid_events": aligned + unaligned,
            "aligned": aligned,
            "unaligned": unaligned,
            "expert_action_in_mask": legal,
        },
        targets,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild one YouTube match's public masks"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--neutral",
        type=Path,
        help="local neutral-sequence override for copied cloud manifests",
    )
    parser.add_argument(
        "--events",
        type=Path,
        help="offline event override; accepts legacy arrays or HUD cycle v3",
    )
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument(
        "--actor-storage", choices=("full", "compact"), default="full"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    output_manifest = args.output_manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    neutral_source_path = (
        Path(manifest["artifacts"]["neutral_sequence"]["path"])
        if args.neutral is None
        else args.neutral.resolve()
    )
    events_source_path = (
        Path(manifest["artifacts"]["offline_play_events"]["path"])
        if args.events is None
        else args.events.resolve()
    )
    neutral_path = _stage_input(
        neutral_source_path, output_manifest.parent / "neutral_sequence.jsonl.gz"
    )
    neutral = _rows(neutral_path)
    events, event_source = normalize_offline_events(
        json.loads(events_source_path.read_text())
    )
    events_path = output_manifest.parent / "offline_play_events_normalized.json"
    _atomic_json(events_path, events)
    builder, mask_builder = build_public_mask_builder(args.vocabulary.resolve())

    actor_rows: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for actor_id in (0, 1):
        for index, record in enumerate(neutral):
            if index % 2:
                continue
            own = copy.deepcopy(record["offline_privileged_hud"][str(actor_id)])
            row = {
                "schema": ACTOR_SCHEMA,
                "match_id": record["match_id"],
                "split_group_id": record["split_group_id"],
                "snapshot_id": record["snapshot_id"],
                "output_pts": record["output_pts"],
                "output_time_base": record["output_time_base"],
                "source_time_base": record["source_time_base"],
                "timestamp_ms": record["timestamp_ms"],
                "actor_id": actor_id,
                "public": copy.deepcopy(record["public"]),
                "own_hud": own,
                "public_action_mask": build_actor_mask(
                    record,
                    actor_id=actor_id,
                    builder=builder,
                    mask_builder=mask_builder,
                ),
                "label_validity": {
                    "hand": [bool(item["valid"]) for item in own["hand"]],
                    "next_card": bool(own["next_card"]["valid"]),
                    "elixir": bool(own["elixir"]["valid"]),
                    "clock": bool(record["public"]["clock"]["valid"]),
                    "entities": True,
                },
            }
            actor_rows[actor_id].append(row)

    label_counts, targets = _attach_labels(actor_rows, events)
    actor_artifacts = []
    mask_counts: dict[str, Any] = {}
    for actor_id in (0, 1):
        if args.actor_storage == "compact":
            stored_rows = [compact_actor_record(row) for row in actor_rows[actor_id]]
            path = output_manifest.parent / f"actor_{actor_id}_overlay_masks_v3.jsonl.gz"
            storage = "compact_overlay_v1"
        else:
            stored_rows = actor_rows[actor_id]
            path = output_manifest.parent / f"actor_{actor_id}_trajectory_masks_v3.jsonl.gz"
            storage = "full_trajectory_v1"
        _atomic_gzip_jsonl(path, stored_rows)
        eligible = [
            row for row in actor_rows[actor_id] if row["own_hud"]["complete_valid"]
        ]
        nontrivial = [
            row
            for row in eligible
            if row["public_action_mask"]["non_noop_legal_actions"] > 0
        ]
        legal_counts = [
            row["public_action_mask"]["non_noop_legal_actions"]
            for row in actor_rows[actor_id]
        ]
        mask_counts[str(actor_id)] = {
            "rows": len(actor_rows[actor_id]),
            "eligible_complete_hud_rows": len(eligible),
            "eligible_nontrivial_mask_rows": len(nontrivial),
            "all_nontrivial_mask_rows": sum(value > 0 for value in legal_counts),
            "total_non_noop_legal_actions": sum(legal_counts),
            "maximum_non_noop_legal_actions": max(legal_counts, default=0),
        }
        actor_artifacts.append(
            {
                "actor_id": actor_id,
                "path": str(path),
                "sha256": _sha256(path),
                "rows": len(stored_rows),
                "storage": storage,
                "neutral_join_key": "snapshot_id",
            }
        )

    output = copy.deepcopy(manifest)
    output["schema"] = MANIFEST_SCHEMA
    output["parent_manifest"] = {
        "path": str(manifest_path),
        "sha256": _sha256(manifest_path),
    }
    output["artifacts"]["actor_trajectories"] = actor_artifacts
    output["artifacts"]["neutral_sequence"] = {
        "path": str(neutral_path),
        "sha256": _sha256(neutral_path),
        "rows": len(neutral),
    }
    output["artifacts"]["offline_play_events"] = {
        "path": str(events_path),
        "sha256": _sha256(events_path),
        "rows": len(events),
        "source": event_source,
        "inference_eligible": False,
    }
    if event_source == "precision_gated_hud_cycle_events_v3":
        cycle_path = _stage_input(
            events_source_path, output_manifest.parent / "offline_cycle_events_v3.json"
        )
        output["artifacts"]["offline_cycle_events"] = {
            "path": str(cycle_path),
            "sha256": _sha256(cycle_path),
            "rows": len(events),
            "inference_eligible": False,
        }
    output["actor_storage"] = {
        "mode": args.actor_storage,
        "neutral_join_key": "snapshot_id",
        "public_state_stored_once": args.actor_storage == "compact",
    }
    target_path = output_manifest.parent / "offline_actor_targets_masks_v3.json"
    _atomic_json(target_path, targets)
    output["artifacts"]["offline_actor_targets"] = {
        "path": str(target_path),
        "sha256": _sha256(target_path),
        "rows": len(targets),
        "inference_eligible": False,
    }
    output["limitations"] = [
        (
            "public masks use current public evidence and remain conservative for "
            "unsupported ability or occupancy state; one of seven offline labels "
            "is independently rejected"
            if str(item).startswith("public masks fail closed to no-op")
            else item
        )
        for item in output.get("limitations", [])
    ]
    output["public_mask_v3"] = {
        "schema": MASK_SCHEMA,
        "contract": "label_independent_public_action_mask_v2",
        "contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "builder": "PublicActionMaskBuilder_current_public_frame",
        "label_independent": True,
        "exact_simulator_state_used": False,
        "counts": mask_counts,
        "offline_label_alignment": label_counts,
        "offline_event_source": event_source,
    }
    _atomic_json(output_manifest, output)
    print(
        json.dumps(
            {
                "manifest": str(output_manifest),
                "sha256": _sha256(output_manifest),
                "mask_counts": mask_counts,
                "labels": label_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
