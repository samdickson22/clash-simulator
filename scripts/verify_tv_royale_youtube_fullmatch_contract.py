from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "clasher.youtube.fullmatch.semantic_contract_report.v1"
NEUTRAL_SCHEMA = "clasher.youtube.fullmatch.neutral_sequence.v1"
ACTOR_SCHEMA = "clasher.youtube.fullmatch.actor_trajectory.v1"
MANIFEST_SCHEMA = "clasher.youtube.fullmatch.extraction_manifest.v1"
MANIFEST_SCHEMAS = frozenset(
    {
        MANIFEST_SCHEMA,
        "clasher.youtube.fullmatch.extraction_manifest.v2",
        "clasher.youtube.fullmatch.extraction_manifest.v3",
    }
)
NOOP_ACTION = 4 * 18 * 32
NUM_ACTIONS = NOOP_ACTION + 2


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TypeError(f"{path}:{line_number}: row is not an object")
            yield row


def _resolved_artifact(extraction_dir: Path, value: object) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = extraction_dir / path
    path = path.resolve()
    if extraction_dir.resolve() not in (path, *path.parents):
        raise ValueError(f"artifact is outside extraction directory: {path}")
    return path


def _head_contract(head: object) -> bool:
    if not isinstance(head, dict) or not isinstance(head.get("valid"), bool):
        return False
    confidence = head.get("confidence", head.get("score"))
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        return False
    if head["valid"]:
        return head.get("value") is not None
    return head.get("value") is None and isinstance(head.get("reason"), str)


def _status_contract(head: object) -> bool:
    return _head_contract(head)


def _clock_value(clock: dict[str, Any]) -> object:
    return clock.get("value_seconds", clock.get("value"))


def _source_timing_valid(
    row: dict[str, Any], *, expected_pts: int, output_time_base: str, source_time_base: str
) -> bool:
    timing = row.get("source_timing")
    # The extractor may keep timing at the record root to make alignment keys
    # cheap to scan, or in a typed subrecord. Both forms must carry the exact
    # acquisition fps-filter PTS and time bases.
    if not isinstance(timing, dict):
        timing = row
    if timing.get("output_pts") != expected_pts:
        return False
    if timing.get("output_time_base") != output_time_base:
        return False
    if timing.get("source_time_base") != source_time_base:
        return False
    decoded_index = timing.get("decoded_sample_index", row.get("sample_index"))
    if decoded_index != expected_pts:
        return False
    seconds = timing.get("target_source_time_seconds")
    if seconds is None and row.get("timestamp_ms") == expected_pts * 100:
        seconds = expected_pts / 10.0
    expected_seconds = expected_pts / 10.0
    return isinstance(seconds, (int, float)) and math.isclose(
        float(seconds), expected_seconds, abs_tol=1e-9
    )


def _event_has_complete_play_and_tile(event: object) -> bool:
    if not isinstance(event, dict):
        return False
    tile = event.get("deployment_tile_absolute", event.get("deployment_tile"))
    tile_valid = (
        isinstance(tile, list)
        and len(tile) == 2
        and all(isinstance(value, int) and not isinstance(value, bool) for value in tile)
        and 0 <= tile[0] < 18
        and 0 <= tile[1] < 32
    )
    identity = event.get("card_identity")
    explicit_play_valid = event.get("play_valid")
    public_marker_play = event.get("evidence") in {
        "temporally_deduplicated_public_deployment_marker",
        "current_or_past_public_deployment_marker",
    }
    return bool(
        (explicit_play_valid is True or public_marker_play)
        and event.get("placement_valid") is True
        and event.get("identity_valid") is True
        and isinstance(identity, str)
        and identity
        and tile_valid
    )


def verify(
    *,
    extraction_dir: Path,
    source_manifest_path: Path,
    extraction_manifest_path: Path | None = None,
) -> dict[str, Any]:
    extraction_dir = extraction_dir.resolve()
    source_manifest_path = source_manifest_path.resolve()
    manifest_path = (
        extraction_dir / "manifest.json"
        if extraction_manifest_path is None
        else extraction_manifest_path.resolve()
    )
    if extraction_dir not in (manifest_path, *manifest_path.parents):
        raise ValueError("extraction manifest is outside extraction directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    gates: list[dict[str, Any]] = []

    def gate(name: str, passed: bool, evidence: object) -> None:
        gates.append({"name": name, "passed": bool(passed), "evidence": evidence})

    gate("manifest_schema", manifest.get("schema") in MANIFEST_SCHEMAS, manifest.get("schema"))
    declared_source = manifest.get("source", {})
    acquisition_media = source_manifest.get("source_media", {})
    gate(
        "source_manifest_hash",
        declared_source.get("acquisition_manifest_sha256")
        == file_sha256(source_manifest_path),
        declared_source.get("acquisition_manifest_sha256"),
    )
    gate(
        "source_video_hash",
        declared_source.get("video_sha256") == acquisition_media.get("sha256"),
        declared_source.get("video_sha256"),
    )

    artifacts = manifest.get("artifacts", {})
    neutral_artifact = artifacts.get("neutral_sequence", {})
    neutral_path = _resolved_artifact(extraction_dir, neutral_artifact.get("path"))
    actor_artifacts = artifacts.get("actor_trajectories", [])
    event_artifact = artifacts.get("offline_play_events", {})
    target_artifact = artifacts.get("offline_actor_targets")
    event_path = _resolved_artifact(extraction_dir, event_artifact.get("path"))
    artifact_rows = [neutral_artifact, *actor_artifacts, event_artifact]
    artifact_paths = [
        neutral_path,
        *[
            _resolved_artifact(extraction_dir, artifact.get("path"))
            for artifact in actor_artifacts
        ],
        event_path,
    ]
    if isinstance(target_artifact, dict):
        artifact_rows.append(target_artifact)
        artifact_paths.append(
            _resolved_artifact(extraction_dir, target_artifact.get("path"))
        )
    hash_results = [
        path.is_file() and artifact.get("sha256") == file_sha256(path)
        for path, artifact in zip(artifact_paths, artifact_rows, strict=True)
    ]
    gate("artifact_content_hashes", all(hash_results), hash_results)

    neutral_rows = list(jsonl_rows(neutral_path))
    expected_samples = int(source_manifest.get("decode", {}).get("sample_count", -1))
    output_time_base = str(
        source_manifest.get("decode", {}).get("output_time_base", "")
    )
    source_time_base = str(acquisition_media.get("source_time_base", ""))
    gate(
        "neutral_row_count",
        len(neutral_rows) == expected_samples == neutral_artifact.get("rows"),
        {"actual": len(neutral_rows), "expected": expected_samples},
    )
    gate(
        "neutral_schema_and_contiguous_indices",
        all(
            row.get("schema") == NEUTRAL_SCHEMA and row.get("sample_index") == index
            for index, row in enumerate(neutral_rows)
        ),
        {"rows": len(neutral_rows)},
    )
    timing_valid = sum(
        _source_timing_valid(
            row,
            expected_pts=index,
            output_time_base=output_time_base,
            source_time_base=source_time_base,
        )
        for index, row in enumerate(neutral_rows)
    )
    gate(
        "published_pts_and_timebase_lineage",
        timing_valid == len(neutral_rows) and bool(neutral_rows),
        {"valid_rows": timing_valid, "rows": len(neutral_rows)},
    )

    match_ids = {str(row.get("match_id")) for row in neutral_rows}
    split_groups = {str(row.get("split_group_id")) for row in neutral_rows}
    coordinate_frames = {
        str(row.get("public", {}).get("coordinate_frame")) for row in neutral_rows
    }
    gate("one_match", len(match_ids) == 1 and "" not in match_ids, sorted(match_ids))
    gate(
        "one_split_group",
        len(split_groups) == 1 and "" not in split_groups,
        sorted(split_groups),
    )
    gate(
        "absolute_world_coordinates",
        coordinate_frames == {"absolute_world"},
        sorted(coordinate_frames),
    )

    both_huds = 0
    hud_head_rows = 0
    complete_hud_by_player: Counter[int] = Counter()
    clock_valid = 0
    entity_count = 0
    entity_head_contract = 0
    hp_valid = 0
    typed_towers = 0
    typed_projectiles = 0
    typed_effects = 0
    accepted_snapshots = 0
    neutral_simulator_clean = 0
    for row in neutral_rows:
        private = row.get("offline_privileged_hud")
        row_huds_complete = False
        if isinstance(private, dict) and set(private) == {"0", "1"}:
            both_huds += 1
            player_complete: list[bool] = []
            for player_id in (0, 1):
                hud = private[str(player_id)]
                if not isinstance(hud, dict):
                    continue
                hand = hud.get("hand")
                valid_heads = (
                    isinstance(hand, list)
                    and len(hand) == 4
                    and all(_head_contract(head) for head in hand)
                    and _head_contract(hud.get("next_card"))
                    and _head_contract(hud.get("elixir"))
                )
                hud_head_rows += int(valid_heads)
                complete_hud_by_player[player_id] += int(
                    valid_heads and hud.get("complete_valid") is True
                )
                player_complete.append(
                    bool(valid_heads and hud.get("complete_valid") is True)
                )
            row_huds_complete = len(player_complete) == 2 and all(player_complete)
        evidence = row.get("offline_evidence")
        neutral_simulator_clean += int(
            isinstance(evidence, dict)
            and evidence.get("simulator_state_used") is False
            and evidence.get("exact_simulator_action_mask_used") is False
        )
        public = row.get("public", {})
        clock = public.get("clock") if isinstance(public, dict) else None
        row_clock_valid = False
        if isinstance(clock, dict) and _head_contract(
            {**clock, "value": _clock_value(clock)}
        ):
            clock_valid += int(clock.get("valid") is True)
            row_clock_valid = clock.get("valid") is True
        entities = public.get("entities", []) if isinstance(public, dict) else []
        if not isinstance(entities, list):
            continue
        accepted_snapshots += int(row_huds_complete and row_clock_valid and bool(entities))
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_count += 1
            confidence = entity.get("confidence")
            identity = entity.get("identity")
            head_ok = bool(
                isinstance(confidence, (int, float))
                and not isinstance(confidence, bool)
                and 0.0 <= float(confidence) <= 1.0
                and isinstance(identity, dict)
                and isinstance(identity.get("valid"), bool)
                and isinstance(entity.get("hp_valid"), bool)
                and isinstance(entity.get("hp_confidence"), (int, float))
                and _status_contract(entity.get("status"))
                and _status_contract(entity.get("projectile_target"))
            )
            entity_head_contract += int(head_ok)
            hp_valid += int(entity.get("hp_valid") is True)
            stable_key = str(identity.get("stable_key") if isinstance(identity, dict) else "")
            typed_towers += int(stable_key.startswith("tower:"))
            typed_projectiles += int(stable_key.startswith("projectile:"))
            typed_effects += int(stable_key.startswith("area_effect:"))

    gate("both_huds_present", both_huds == len(neutral_rows), both_huds)
    gate(
        "hud_per_head_validity_and_confidence",
        hud_head_rows == len(neutral_rows) * 2,
        {"valid_player_rows": hud_head_rows, "expected": len(neutral_rows) * 2},
    )
    gate(
        "complete_decoded_hud_exists_for_both_players",
        all(complete_hud_by_player[player] > 0 for player in (0, 1)),
        dict(complete_hud_by_player),
    )
    gate("visible_clock_decoded", clock_valid > 0, {"valid_rows": clock_valid})
    gate("arena_entities_decoded", entity_count > 0, entity_count)
    gate(
        "entity_per_head_validity_and_confidence",
        entity_head_contract == entity_count and entity_count > 0,
        {"valid": entity_head_contract, "entities": entity_count},
    )
    gate("hp_decoded", hp_valid > 0, hp_valid)
    gate("towers_typed", typed_towers > 0, typed_towers)
    gate("projectiles_typed", typed_projectiles > 0, typed_projectiles)
    gate("effects_typed", typed_effects > 0, typed_effects)
    gate(
        "at_least_one_actor_ready_neutral_snapshot",
        accepted_snapshots > 0,
        accepted_snapshots,
    )
    gate(
        "neutral_records_declare_no_simulator_inputs",
        neutral_simulator_clean == len(neutral_rows),
        {"clean": neutral_simulator_clean, "rows": len(neutral_rows)},
    )

    events = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise TypeError("offline play-event artifact must contain a list")
    complete_events = sum(_event_has_complete_play_and_tile(event) for event in events)
    gate(
        "play_events_with_card_and_deployment_tile",
        complete_events > 0,
        {"complete": complete_events, "events": len(events)},
    )

    neutral_by_snapshot = {
        str(row.get("snapshot_id")): row for row in neutral_rows
    }
    actor_counts: Counter[int] = Counter()
    mask_eligible_counts: Counter[int] = Counter()
    nontrivial_mask_counts: Counter[int] = Counter()
    actor_projection_ok = True
    mask_ok = True
    no_future_or_offline_fields = True
    deterministic_mask_by_input: dict[str, str] = {}
    mask_deterministic_from_observation = True
    exact_recompute_rows = 0
    exact_recompute_mismatches = 0
    counterfactual_rows = 0
    counterfactual_mismatches = 0
    actor_masks_by_key: dict[tuple[int, str], set[int]] = {}
    recompute_bundle: tuple[Any, Any, Any] | None = None
    expand_overlay: Any | None = None
    if manifest.get("schema") == "clasher.youtube.fullmatch.extraction_manifest.v3":
        from scripts.build_tv_royale_youtube_fullmatch_masks import (
            build_actor_mask,
            build_public_mask_builder,
            expand_actor_overlay,
        )

        vocabulary_path = (
            Path(__file__).resolve().parents[1]
            / "reports/current_client_youtube_stable_vocabulary_v1.json"
        )
        builder, public_mask_builder = build_public_mask_builder(vocabulary_path)
        recompute_bundle = (build_actor_mask, builder, public_mask_builder)
        expand_overlay = expand_actor_overlay
    for artifact in actor_artifacts:
        actor_id = int(artifact.get("actor_id", -1))
        path = _resolved_artifact(extraction_dir, artifact.get("path"))
        rows = list(jsonl_rows(path))
        actor_counts[actor_id] += len(rows)
        if artifact.get("rows") != len(rows):
            actor_projection_ok = False
        storage = str(artifact.get("storage", "full_trajectory_v1"))
        for stored_actor in rows:
            neutral = neutral_by_snapshot.get(str(stored_actor.get("snapshot_id")))
            if storage == "compact_overlay_v1":
                if (
                    expand_overlay is None
                    or neutral is None
                    or set(stored_actor)
                    != {
                        "schema",
                        "snapshot_id",
                        "actor_id",
                        "own_hud",
                        "public_action_mask",
                        "label_validity",
                    }
                ):
                    actor_projection_ok = False
                    continue
                actor = expand_overlay(stored_actor, neutral)
            elif storage == "full_trajectory_v1":
                actor = stored_actor
            else:
                actor_projection_ok = False
                continue
            if (
                neutral is None
                or actor.get("schema") != ACTOR_SCHEMA
                or actor.get("actor_id") != actor_id
                or actor.get("split_group_id") != neutral.get("split_group_id")
                or actor.get("output_pts") != neutral.get("output_pts")
                or actor.get("output_time_base") != neutral.get("output_time_base")
                or actor.get("source_time_base") != neutral.get("source_time_base")
                or actor.get("timestamp_ms") != neutral.get("timestamp_ms")
                or actor.get("public") != neutral.get("public")
                or actor.get("own_hud")
                != neutral.get("offline_privileged_hud", {}).get(str(actor_id))
            ):
                actor_projection_ok = False
            observation_surface = {
                key: value
                for key, value in actor.items()
                if key != "offline_label_only_targets"
            }
            serialized = json.dumps(observation_surface, sort_keys=True).casefold()
            forbidden = (
                "offline_privileged_hud",
                "offline_evidence",
                "opponent_hud",
                "evidence_frame",
                "future_frame",
                "simulator_state",
                "expert_action",
            )
            if any(token in serialized for token in forbidden):
                no_future_or_offline_fields = False
            mask = actor.get("public_action_mask")
            legal = mask.get("legal_action_indices") if isinstance(mask, dict) else None
            v3_manifest = (
                manifest.get("schema")
                == "clasher.youtube.fullmatch.extraction_manifest.v3"
            )
            legacy_contract = bool(
                not v3_manifest
                and isinstance(mask, dict)
                and isinstance(mask.get("contract"), str)
                and "label_independent" in mask["contract"]
            )
            v3_contract = bool(
                isinstance(mask, dict)
                and mask.get("schema") == "clasher.youtube.public_action_mask.v2"
                and mask.get("contract") == "label_independent_public_action_mask_v2"
                and mask.get("contract_version") == 2
                and mask.get("source") == "current_public_frame_and_own_hud_only"
            )
            if not (
                isinstance(mask, dict)
                and mask.get("valid") is True
                and (legacy_contract or v3_contract)
                and isinstance(legal, list)
                and legal
                and NOOP_ACTION in legal
                and all(isinstance(value, int) and 0 <= value < NUM_ACTIONS for value in legal)
            ):
                mask_ok = False
                continue
            if legal != sorted(set(legal)):
                mask_ok = False
            if (
                isinstance(mask, dict)
                and "non_noop_legal_actions" in mask
                and mask["non_noop_legal_actions"]
                != sum(value != NOOP_ACTION for value in legal)
            ):
                mask_ok = False
            actor_masks_by_key[(actor_id, str(actor.get("snapshot_id")))] = set(legal)
            own_hud = actor.get("own_hud")
            eligible = bool(
                isinstance(own_hud, dict)
                and own_hud.get("complete_valid") is True
                and isinstance(own_hud.get("elixir"), dict)
                and own_hud["elixir"].get("valid") is True
            )
            if eligible:
                mask_eligible_counts[actor_id] += 1
                nontrivial_mask_counts[actor_id] += int(
                    any(value != NOOP_ACTION for value in legal)
                )
            input_payload = {
                "public": actor.get("public"),
                "own_hud": own_hud,
            }
            input_digest = hashlib.sha256(
                json.dumps(
                    input_payload, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            serialized_mask = json.dumps(mask, sort_keys=True, separators=(",", ":"))
            prior_mask = deterministic_mask_by_input.setdefault(
                input_digest, serialized_mask
            )
            if prior_mask != serialized_mask:
                mask_deterministic_from_observation = False
            if recompute_bundle is not None and neutral is not None:
                build_actor_mask, builder, public_mask_builder = recompute_bundle
                recomputed = build_actor_mask(
                    neutral,
                    actor_id=actor_id,
                    builder=builder,
                    mask_builder=public_mask_builder,
                )
                exact_recompute_rows += 1
                exact_recompute_mismatches += int(recomputed != mask)
                poisoned = copy.deepcopy(neutral)
                poisoned["offline_evidence"] = {
                    "expert_action": 17,
                    "play_events": [{"target_action": 2305}],
                    "future_frame": 999999,
                }
                poisoned["offline_label_only_targets"] = [
                    {"expert_action": 2305, "offline_label_only": True}
                ]
                counterfactual = build_actor_mask(
                    poisoned,
                    actor_id=actor_id,
                    builder=builder,
                    mask_builder=public_mask_builder,
                )
                counterfactual_rows += 1
                counterfactual_mismatches += int(counterfactual != recomputed)

    gate(
        "two_same_split_private_safe_actor_projections",
        actor_projection_ok and set(actor_counts) == {0, 1} and min(actor_counts.values()) > 0,
        dict(actor_counts),
    )
    gate("mandatory_label_independent_action_masks", mask_ok, dict(actor_counts))
    eligible_total = sum(mask_eligible_counts.values())
    nontrivial_total = sum(nontrivial_mask_counts.values())
    minimum_by_actor = {
        actor_id: max(1, math.ceil(mask_eligible_counts[actor_id] * 0.05))
        for actor_id in (0, 1)
    }
    nontrivial_coverage = (
        nontrivial_total / eligible_total if eligible_total else 0.0
    )
    nontrivial_ok = bool(
        eligible_total > 0
        and nontrivial_coverage >= 0.10
        and all(
            nontrivial_mask_counts[actor_id] >= minimum_by_actor[actor_id]
            for actor_id in (0, 1)
        )
    )
    gate(
        "nontrivial_masks_on_complete_hud_elixir_rows",
        nontrivial_ok,
        {
            "eligible_by_actor": dict(mask_eligible_counts),
            "nontrivial_by_actor": dict(nontrivial_mask_counts),
            "minimum_by_actor": minimum_by_actor,
            "eligible_total": eligible_total,
            "nontrivial_total": nontrivial_total,
            "nontrivial_fraction": nontrivial_coverage,
        },
    )
    target_label_independent = bool(
        mask_ok
        and no_future_or_offline_fields
        and mask_deterministic_from_observation
        and (
            recompute_bundle is None
            or (
                exact_recompute_rows == sum(actor_counts.values())
                and exact_recompute_mismatches == 0
                and counterfactual_rows == sum(actor_counts.values())
                and counterfactual_mismatches == 0
            )
        )
    )
    gate(
        "mask_target_label_independence",
        target_label_independent,
        {
            "actor_target_fields_absent": no_future_or_offline_fields,
            "deterministic_for_identical_public_and_own_hud": (
                mask_deterministic_from_observation
            ),
            "unique_observation_inputs": len(deterministic_mask_by_input),
            "exact_recompute_rows": exact_recompute_rows,
            "exact_recompute_mismatches": exact_recompute_mismatches,
            "offline_target_counterfactual_rows": counterfactual_rows,
            "offline_target_counterfactual_mismatches": counterfactual_mismatches,
        },
    )
    gate("no_future_simulator_or_opponent_leakage", no_future_or_offline_fields, True)
    leakage = manifest.get("leakage_contract", {})
    leakage_ok = bool(
        leakage.get("raw_frames_in_actor_artifacts") == 0
        and leakage.get("opponent_hud_in_actor_artifacts") == 0
        and leakage.get("simulator_state_inputs") == 0
        and leakage.get("exact_simulator_masks") == 0
        and leakage.get("event_labels_are_offline_only") is True
        and leakage.get("public_masks_depend_on_labels") is False
        and leakage.get("same_split_group_for_both_actors") is True
    )
    gate("manifest_leakage_contract", leakage_ok, leakage)

    offline_target_rows = 0
    offline_targets_in_mask = 0
    offline_targets_valid = True
    if isinstance(target_artifact, dict):
        target_path = _resolved_artifact(extraction_dir, target_artifact.get("path"))
        targets = json.loads(target_path.read_text(encoding="utf-8"))
        if not isinstance(targets, list):
            offline_targets_valid = False
            targets = []
        offline_target_rows = len(targets)
        if (
            target_artifact.get("inference_eligible") is not False
            or target_artifact.get("rows") != offline_target_rows
        ):
            offline_targets_valid = False
        for target in targets:
            if not isinstance(target, dict):
                offline_targets_valid = False
                continue
            target_actor_id = target.get("actor_id")
            tile = target.get("deployment_tile_actor_canonical")
            slot = target.get("hand_slot")
            action = target.get("expert_action")
            legal = actor_masks_by_key.get(
                (
                    int(target_actor_id)
                    if isinstance(target_actor_id, int)
                    else -1,
                    str(target.get("snapshot_id")),
                )
            )
            expected_action = (
                slot * 18 * 32 + tile[1] * 18 + tile[0]
                if isinstance(slot, int)
                and 0 <= slot < 4
                and isinstance(tile, list)
                and len(tile) == 2
                and all(isinstance(value, int) for value in tile)
                and 0 <= tile[0] < 18
                and 0 <= tile[1] < 32
                else None
            )
            in_mask = legal is not None and action in legal
            offline_targets_in_mask += int(in_mask)
            if not (
                target.get("schema") == "clasher.youtube.offline_action_target.v1"
                and target.get("offline_label_only") is True
                and action == expected_action
                and target.get("expert_action_in_public_mask") is in_mask
            ):
                offline_targets_valid = False
        gate(
            "offline_targets_separate_and_consistent",
            offline_targets_valid,
            {
                "rows": offline_target_rows,
                "expert_actions_in_public_mask": offline_targets_in_mask,
                "inference_eligible": target_artifact.get("inference_eligible"),
            },
        )

    timing = manifest.get("timing_seconds", {})
    resources = manifest.get("resources", {})
    required_stages = (
        "video_decode",
        "hud_current_frame_matching",
        "arena_detector",
        "serialization_and_other",
        "total_wall",
    )
    timing_ok = all(
        isinstance(timing.get(name), (int, float))
        and not isinstance(timing.get(name), bool)
        and math.isfinite(float(timing[name]))
        and float(timing[name]) >= 0.0
        for name in required_stages
    )
    load_ok = bool(
        (
            isinstance(timing.get("model_load"), (int, float))
            and float(timing["model_load"]) >= 0.0
        )
        or (
            isinstance(timing.get("detector_model_load"), (int, float))
            and float(timing["detector_model_load"]) >= 0.0
            and isinstance(timing.get("hud_model_load"), (int, float))
            and float(timing["hud_model_load"]) >= 0.0
        )
    )
    resource_ok = isinstance(resources.get("max_rss_bytes"), int) and resources[
        "max_rss_bytes"
    ] > 0
    gate(
        "stage_benchmarks_and_peak_rss",
        timing_ok and load_ok and resource_ok,
        {"timing": timing, "resources": resources},
    )

    failed = [item["name"] for item in gates if not item["passed"]]
    return {
        "schema": REPORT_SCHEMA,
        "status": "passed" if not failed else "failed",
        "source_manifest": str(source_manifest_path),
        "source_manifest_sha256": file_sha256(source_manifest_path),
        "extraction_manifest": str(manifest_path),
        "extraction_manifest_sha256": file_sha256(manifest_path),
        "counts": {
            "source_seconds": acquisition_media.get("probed_duration_seconds"),
            "decoded_frames": manifest.get("sampling", {}).get(
                "decoded_source_frames"
            ),
            "hud_frames": len(neutral_rows) * 2,
            "detector_frames": len(neutral_rows),
            "neutral_snapshots": len(neutral_rows),
            "accepted_snapshots": accepted_snapshots,
            "actor_rows": dict(actor_counts),
            "mask_eligible_rows": dict(mask_eligible_counts),
            "nontrivial_mask_rows": dict(nontrivial_mask_counts),
            "nontrivial_mask_fraction": nontrivial_coverage,
            "mask_exact_recompute_rows": exact_recompute_rows,
            "mask_exact_recompute_mismatches": exact_recompute_mismatches,
            "mask_counterfactual_rows": counterfactual_rows,
            "mask_counterfactual_mismatches": counterfactual_mismatches,
            "offline_target_rows": offline_target_rows,
            "offline_targets_in_mask": offline_targets_in_mask,
            "entities": entity_count,
            "hp_valid": hp_valid,
            "typed_towers": typed_towers,
            "typed_projectiles": typed_projectiles,
            "typed_effects": typed_effects,
            "clock_valid": clock_valid,
            "events": len(events),
            "complete_events": complete_events,
        },
        "gates": gates,
        "failed_gates": failed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the full-match YouTube semantic extraction contract"
    )
    parser.add_argument("--extraction-dir", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument(
        "--extraction-manifest",
        help="defaults to <extraction-dir>/manifest.json",
    )
    parser.add_argument("--report-out", required=True)
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="write a failed proof report and exit successfully",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = verify(
        extraction_dir=Path(args.extraction_dir),
        source_manifest_path=Path(args.source_manifest),
        extraction_manifest_path=(
            None
            if args.extraction_manifest is None
            else Path(args.extraction_manifest)
        ),
    )
    report_path = Path(args.report_out).resolve()
    atomic_json(report_path, report)
    print(
        json.dumps(
            {
                "report": str(report_path),
                "sha256": file_sha256(report_path),
                "status": report["status"],
                "failed_gates": report["failed_gates"],
                "counts": report["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if report["status"] != "passed" and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
