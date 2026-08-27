"""Read-only real-corpus calibration gate for the practical simple Gym.

The gate deliberately compares only shared, observable contracts.  It does not
replay detector rows as simulator truth and it never treats derived visual
labels as supervision for HP, projectiles, status, or outcomes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.torch_sim.actions import NO_OP_ACTION, NUM_ACTIONS
from clasher.torch_sim.simple_public_mask import (
    SIMPLE_PUBLIC_MASK_SEMANTICS_ID,
    SimplePublicMaskV2Provider,
)
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

CALIBRATION_SCHEMA = "clasher.simple_gym.real_corpus_calibration.v1"
MINIMUM_EXAMPLES = 30
MINIMUM_SUCCESS_RATE = 0.95
LOGIC_TICK_MS = 50
PUBLIC_SAMPLE_MS = 100


class CalibrationError(ValueError):
    """Raised when an input cannot be audited without guessing."""


@dataclass(frozen=True)
class EngineCalibrationContract:
    """Small immutable view of the simple engine contracts used by this gate."""

    manifest_path: str
    manifest_sha256: str
    supported_public_cards: tuple[str, ...]
    stable_action_keys: frozenset[str]
    canonical_lane_globals: bool
    public_mask_contract_version: int
    logic_tick_ms: int
    regulation_ticks: int
    tiebreak_ticks: int
    real_frame_public_mask_adapter: bool = False
    tensor_public_mask_provider: bool = True
    tensor_public_mask_semantics_id: str = SIMPLE_PUBLIC_MASK_SEMANTICS_ID


def _object(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CalibrationError(f"{context} must be a JSON object")
    return value


def _array(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise CalibrationError(f"{context} must be a JSON array")
    return value


def _integer(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CalibrationError(f"{context} must be an integer")
    return value


def _number(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError(f"{context} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise CalibrationError(f"{context} must be finite")
    return result


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"cannot read JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CalibrationError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _artifact_path(
    manifest_path: Path,
    artifact: Mapping[str, Any],
    *,
    context: str,
) -> Path:
    declared = artifact.get("path")
    if not isinstance(declared, str) or not declared:
        raise CalibrationError(f"{context}.path is missing")
    # Copied corpus manifests retain their source-machine absolute paths.  Use
    # only the local basename beside the manifest so the audit stays bounded
    # to the supplied read-only corpus root.
    local = manifest_path.parent / Path(declared).name
    if not local.is_file():
        raise CalibrationError(f"{context} is absent locally: {local}")
    return local


def _jsonl(path: Path) -> Iterable[tuple[int, Mapping[str, Any]]]:
    def rows(stream: TextIO) -> Iterable[tuple[int, Mapping[str, Any]]]:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CalibrationError(
                    f"invalid JSONL at {path}:{line_number}: {exc}"
                ) from exc
            yield line_number, _object(value, context=f"{path}:{line_number}")

    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                yield from rows(stream)
        else:
            with path.open("r", encoding="utf-8") as stream:
                yield from rows(stream)
    except OSError as exc:
        raise CalibrationError(f"cannot read JSONL {path}: {exc}") from exc


def _wilson_lower(successes: int, total: int) -> float | None:
    if total == 0:
        return None
    z = 1.959963984540054
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = rate + z * z / (2.0 * total)
    spread = z * math.sqrt((rate * (1.0 - rate) + z * z / (4.0 * total)) / total)
    return round((center - spread) / denominator, 6)


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 6)
    weight = position - lower
    return round(
        ordered[lower] * (1.0 - weight) + ordered[upper] * weight,
        6,
    )


def _rate_channel(
    successes: int,
    total: int,
    *,
    minimum_examples: int = MINIMUM_EXAMPLES,
    minimum_rate: float = MINIMUM_SUCCESS_RATE,
) -> dict[str, object]:
    lower = _wilson_lower(successes, total)
    if total < minimum_examples:
        status = "insufficient_evidence"
    elif lower is not None and lower >= minimum_rate:
        status = "pass"
    else:
        status = "fail"
    return {
        "status": status,
        "successes": successes,
        "total": total,
        "rate": None if total == 0 else round(successes / total, 6),
        "wilson_95_lower": lower,
        "minimum_examples": minimum_examples,
        "minimum_wilson_95_lower": minimum_rate,
    }


def _additional_successes_for_wilson(
    successes: int,
    total: int,
    *,
    minimum_rate: float = MINIMUM_SUCCESS_RATE,
) -> int:
    """Return the smallest all-success continuation meeting the confidence gate."""

    additional = 0
    while True:
        lower = _wilson_lower(successes + additional, total + additional)
        if lower is not None and lower >= minimum_rate:
            return additional
        additional += 1


def _resolved_corpus_roots(
    root: str | Path,
    additional_roots: Sequence[str | Path],
) -> tuple[Path, ...]:
    candidates = (root, *additional_roots)
    resolved = tuple(Path(value).expanduser().resolve() for value in candidates)
    if len(resolved) != len(set(resolved)):
        raise CalibrationError("corpus roots must be distinct")
    for corpus_root in resolved:
        if not corpus_root.is_dir():
            raise CalibrationError(f"corpus root does not exist: {corpus_root}")
    return resolved


def load_engine_contract(path: str | Path) -> EngineCalibrationContract:
    """Compile the manifest roots through the actual standard simple setup."""

    manifest_path = Path(path).expanduser().resolve()
    payload = _object(_load_json(manifest_path), context=str(manifest_path))
    contract = _object(payload.get("contract"), context="manifest.contract")
    profile = _object(
        payload.get("support_profile"), context="manifest.support_profile"
    )
    counts = _object(payload.get("counts"), context="manifest.counts")
    cards_raw = _array(
        profile.get("supported_public_cards"),
        context="manifest.support_profile.supported_public_cards",
    )
    if not cards_raw or not all(isinstance(card, str) and card for card in cards_raw):
        raise CalibrationError("supported_public_cards must be non-empty strings")
    cards = tuple(str(card) for card in cards_raw)
    if len(cards) != len(set(cards)):
        raise CalibrationError("supported_public_cards contains duplicates")
    if contract.get("canonical_lane_globals") is not True:
        raise CalibrationError("engine manifest does not require canonical lanes")
    mask_version = _integer(
        contract.get("public_action_mask_contract_version"),
        context="manifest.contract.public_action_mask_contract_version",
    )
    if mask_version != 2:
        raise CalibrationError("engine manifest does not require public mask v2")
    if _integer(
        counts.get("supported_public_cards"),
        context="manifest.counts.supported_public_cards",
    ) != len(cards):
        raise CalibrationError("engine manifest supported-card count is inconsistent")
    if (
        _integer(
            counts.get("unsupported_public_cards"),
            context="manifest.counts.unsupported_public_cards",
        )
        != 0
    ):
        raise CalibrationError("engine manifest still contains unsupported roots")

    setup = compile_standard_simple_setup(
        CardDataLoader(),
        cards,
        device="cpu",
        canonical_lane_globals=True,
    )
    if set(setup.supported_public_root_names) != set(cards):
        raise CalibrationError("compiled engine support differs from its manifest")
    stable_keys = frozenset(f"card_action:{resolve_card_name(card)}" for card in cards)
    if len(stable_keys) != len(cards):
        raise CalibrationError("engine public roots collapse to duplicate typed keys")
    return EngineCalibrationContract(
        manifest_path=str(manifest_path),
        manifest_sha256=_sha256(manifest_path),
        supported_public_cards=cards,
        stable_action_keys=stable_keys,
        canonical_lane_globals=setup.canonical_lane_globals,
        public_mask_contract_version=mask_version,
        logic_tick_ms=LOGIC_TICK_MS,
        regulation_ticks=setup.rules.regulation_ticks,
        tiebreak_ticks=setup.rules.tiebreak_ticks,
        tensor_public_mask_provider=callable(
            getattr(SimplePublicMaskV2Provider, "build", None)
        ),
    )


def audit_real_corpus(
    root: str | Path,
    engine: EngineCalibrationContract,
    *,
    additional_roots: Sequence[str | Path] = (),
    vocabulary_manifest: str | Path | None = None,
) -> dict[str, object]:
    """Compare locally materialized corpus contracts to the simple engine."""

    corpus_roots = _resolved_corpus_roots(root, additional_roots)
    manifests = sorted(
        (corpus_root, manifest)
        for corpus_root in corpus_roots
        for manifest in corpus_root.glob("*/manifest.json")
    )
    if not manifests:
        raise CalibrationError(
            "corpus roots contain no manifests: "
            + ", ".join(str(value) for value in corpus_roots)
        )

    integrity_errors: list[str] = []
    digest_records: list[str] = []
    match_ids: set[str] = set()
    row_intervals = 0
    exact_row_intervals = 0
    clock_rows = 0
    clock_pairs = 0
    clock_rate_success = 0
    clock_resets = 0
    clock_reset_success = 0
    clock_rate_errors: list[float] = []
    reset_time_errors: list[float] = []
    action_grid_total = 0
    action_grid_success = 0
    targets: list[Mapping[str, Any]] = []
    play_events: list[Mapping[str, Any]] = []
    public_mask_versions: Counter[int] = Counter()
    vocabulary_manifest_shas: Counter[str] = Counter()
    provider_semantics_ids: Counter[str] = Counter()
    provider_semantics_digests: Counter[str] = Counter()
    provider_lookup_digests: Counter[str] = Counter()
    actor_artifacts = 0
    actor_rows = 0
    actor_rows_with_join = 0
    actor_rows_with_stored_mask = 0
    actor_rows_with_tensor_projection = 0
    matches_by_root: Counter[str] = Counter()
    seen_manifest_match_ids: dict[str, str] = {}

    for corpus_root, manifest_path in manifests:
        match_label = f"{corpus_root.name}/{manifest_path.parent.name}"
        matches_by_root[str(corpus_root)] += 1
        manifest = _object(_load_json(manifest_path), context=str(manifest_path))
        artifacts = _object(
            manifest.get("artifacts"), context=f"{manifest_path}: artifacts"
        )
        sampling = _object(
            manifest.get("sampling"), context=f"{manifest_path}: sampling"
        )
        mask_contract = _object(
            manifest.get("public_mask_v3"),
            context=f"{manifest_path}: public_mask_v3",
        )
        version = _integer(
            mask_contract.get("contract_version"),
            context=f"{manifest_path}: public mask version",
        )
        public_mask_versions[version] += 1
        models = _object(manifest.get("models"), context=f"{manifest_path}: models")
        vocabulary_sha = models.get("vocabulary_manifest_sha256")
        if isinstance(vocabulary_sha, str) and len(vocabulary_sha) == 64:
            vocabulary_manifest_shas[vocabulary_sha] += 1
        else:
            integrity_errors.append(
                f"{match_label}: vocabulary manifest SHA-256 is missing"
            )
        for key, counter in (
            ("simple_provider_semantics_id", provider_semantics_ids),
            ("simple_provider_semantics_digest", provider_semantics_digests),
            ("simple_provider_lookup_digest", provider_lookup_digests),
        ):
            value = mask_contract.get(key)
            if isinstance(value, str) and value:
                counter[value] += 1
        if (
            version != engine.public_mask_contract_version
            or mask_contract.get("contract")
            != "label_independent_public_action_mask_v2"
            or mask_contract.get("label_independent") is not True
            or mask_contract.get("exact_simulator_state_used") is not False
        ):
            integrity_errors.append(
                f"{match_label}: public mask contract mismatch"
            )
        if sampling.get("output_time_base") != "1/10":
            integrity_errors.append(
                f"{match_label}: output time base is not 1/10"
            )

        resolved: dict[str, tuple[Path, Mapping[str, Any]]] = {}
        for name in (
            "neutral_sequence",
            "offline_actor_targets",
            "offline_play_events",
        ):
            descriptor = _object(
                artifacts.get(name), context=f"{manifest_path}: artifacts.{name}"
            )
            artifact_path = _artifact_path(
                manifest_path,
                descriptor,
                context=f"{manifest_path}: artifacts.{name}",
            )
            actual_sha = _sha256(artifact_path)
            declared_sha = descriptor.get("sha256")
            if actual_sha != declared_sha:
                integrity_errors.append(
                    f"{match_label}: {name} SHA-256 mismatch"
                )
            digest_records.append(f"{match_label}/{name}:{actual_sha}")
            resolved[name] = (artifact_path, descriptor)

        neutral_path, neutral_descriptor = resolved["neutral_sequence"]
        neutral_rows = 0
        neutral_snapshot_ids: set[str] = set()
        current_manifest_match_ids: set[str] = set()
        previous_timestamp: int | None = None
        previous_clock: tuple[int, int] | None = None
        for line_number, row in _jsonl(neutral_path):
            neutral_rows += 1
            match_id = row.get("match_id")
            if not isinstance(match_id, str) or not match_id:
                raise CalibrationError(
                    f"{neutral_path}:{line_number}: match_id is missing"
                )
            match_ids.add(match_id)
            current_manifest_match_ids.add(match_id)
            snapshot_id = row.get("snapshot_id")
            if isinstance(snapshot_id, str) and snapshot_id:
                neutral_snapshot_ids.add(snapshot_id)
            timestamp = _integer(
                row.get("timestamp_ms"),
                context=f"{neutral_path}:{line_number}: timestamp_ms",
            )
            if previous_timestamp is not None:
                row_intervals += 1
                exact_row_intervals += int(
                    timestamp - previous_timestamp == PUBLIC_SAMPLE_MS
                )
            previous_timestamp = timestamp
            public = _object(
                row.get("public"), context=f"{neutral_path}:{line_number}: public"
            )
            if public.get("coordinate_frame") != "absolute_world":
                integrity_errors.append(
                    f"{match_label}: non-absolute coordinate frame"
                )
            clock = _object(
                public.get("clock"),
                context=f"{neutral_path}:{line_number}: public.clock",
            )
            if clock.get("valid") is not True:
                continue
            value = _integer(
                clock.get("value"),
                context=f"{neutral_path}:{line_number}: public.clock.value",
            )
            clock_rows += 1
            if not 0 <= value <= 180:
                integrity_errors.append(
                    f"{match_label}: public clock outside 0..180"
                )
            if previous_clock is not None:
                clock_pairs += 1
                previous_clock_time, previous_value = previous_clock
                elapsed = (timestamp - previous_clock_time) / 1000.0
                if value > previous_value:
                    clock_resets += 1
                    reset_error = (
                        abs(timestamp - engine.regulation_ticks * engine.logic_tick_ms)
                        / 1000.0
                    )
                    reset_time_errors.append(reset_error)
                    clock_reset_success += int(
                        previous_value == 1 and value == 120 and reset_error <= 1.0
                    )
                else:
                    error = abs((previous_value - value) - elapsed)
                    clock_rate_errors.append(error)
                    clock_rate_success += int(error <= 1.0)
            previous_clock = (timestamp, value)
        declared_neutral_rows = _integer(
            neutral_descriptor.get("rows"),
            context=f"{manifest_path}: neutral rows",
        )
        if neutral_rows != declared_neutral_rows:
            integrity_errors.append(
                f"{match_label}: neutral rows "
                f"declared={declared_neutral_rows} observed={neutral_rows}"
            )
        if len(current_manifest_match_ids) != 1:
            integrity_errors.append(
                f"{match_label}: neutral rows do not contain exactly one match_id"
            )
        else:
            manifest_match_id = next(iter(current_manifest_match_ids))
            previous_source = seen_manifest_match_ids.get(manifest_match_id)
            if previous_source is not None:
                integrity_errors.append(
                    f"{match_label}: duplicate match_id also present in "
                    f"{previous_source}"
                )
            else:
                seen_manifest_match_ids[manifest_match_id] = match_label

        actor_descriptors = _array(
            artifacts.get("actor_trajectories"),
            context=f"{manifest_path}: artifacts.actor_trajectories",
        )
        observed_actor_ids: set[int] = set()
        for raw_descriptor in actor_descriptors:
            descriptor = _object(
                raw_descriptor,
                context=f"{manifest_path}: actor trajectory descriptor",
            )
            actor_id = _integer(
                descriptor.get("actor_id"),
                context=f"{manifest_path}: actor trajectory actor_id",
            )
            observed_actor_ids.add(actor_id)
            actor_path = _artifact_path(
                manifest_path,
                descriptor,
                context=f"{manifest_path}: actor trajectory {actor_id}",
            )
            actual_sha = _sha256(actor_path)
            if actual_sha != descriptor.get("sha256"):
                integrity_errors.append(
                    f"{match_label}: actor trajectory {actor_id} SHA-256 mismatch"
                )
            digest_records.append(
                f"{match_label}/actor_trajectory_{actor_id}:{actual_sha}"
            )
            if descriptor.get("neutral_join_key") != "snapshot_id":
                integrity_errors.append(
                    f"{match_label}: actor trajectory {actor_id} has no "
                    "snapshot_id join contract"
                )
            observed_rows = 0
            for line_number, actor_row in _jsonl(actor_path):
                observed_rows += 1
                actor_rows += 1
                row_actor_id = _integer(
                    actor_row.get("actor_id"),
                    context=f"{actor_path}:{line_number}: actor_id",
                )
                if row_actor_id != actor_id:
                    integrity_errors.append(
                        f"{match_label}: actor trajectory descriptor/row mismatch"
                    )
                snapshot_id = actor_row.get("snapshot_id")
                actor_rows_with_join += int(
                    isinstance(snapshot_id, str)
                    and snapshot_id in neutral_snapshot_ids
                )
                stored_mask = actor_row.get("public_action_mask")
                if isinstance(stored_mask, Mapping):
                    legal = stored_mask.get("legal_action_indices")
                    if (
                        stored_mask.get("schema")
                        == "clasher.youtube.public_action_mask.v2"
                        and stored_mask.get("contract_version") == version
                        and stored_mask.get("contract")
                        == "label_independent_public_action_mask_v2"
                        and stored_mask.get("valid") is True
                        and isinstance(legal, list)
                        and all(
                            isinstance(action, int)
                            and not isinstance(action, bool)
                            and 0 <= action < NUM_ACTIONS
                            for action in legal
                        )
                        and legal == sorted(set(legal))
                        and NO_OP_ACTION in legal
                        and stored_mask.get("non_noop_legal_actions")
                        == sum(action != NO_OP_ACTION for action in legal)
                    ):
                        actor_rows_with_stored_mask += 1
                projection = actor_row.get("tensor_public_structured_observation")
                if isinstance(projection, Mapping):
                    globals_raw = projection.get("global_features")
                    if isinstance(globals_raw, list) and len(globals_raw) > 12:
                        actor_rows_with_tensor_projection += 1
            actor_artifacts += 1
            declared_rows = _integer(
                descriptor.get("rows"),
                context=f"{manifest_path}: actor trajectory {actor_id} rows",
            )
            if observed_rows != declared_rows:
                integrity_errors.append(
                    f"{match_label}: actor trajectory {actor_id} rows "
                    f"declared={declared_rows} observed={observed_rows}"
                )
        if observed_actor_ids != {0, 1}:
            integrity_errors.append(
                f"{match_label}: actor trajectories must cover actors 0 and 1"
            )

        target_path, target_descriptor = resolved["offline_actor_targets"]
        target_rows = _array(_load_json(target_path), context=str(target_path))
        if len(target_rows) != _integer(
            target_descriptor.get("rows"), context=f"{manifest_path}: target rows"
        ):
            integrity_errors.append(
                f"{match_label}: target row count mismatch"
            )
        targets.extend(
            _object(row, context=f"{target_path}: target") for row in target_rows
        )

        event_path, event_descriptor = resolved["offline_play_events"]
        event_rows = _array(_load_json(event_path), context=str(event_path))
        if len(event_rows) != _integer(
            event_descriptor.get("rows"), context=f"{manifest_path}: event rows"
        ):
            integrity_errors.append(
                f"{match_label}: event row count mismatch"
            )
        for raw_event in event_rows:
            event = _object(raw_event, context=f"{event_path}: event")
            if event.get("play_valid") is True:
                timestamp = _integer(
                    event.get("timestamp_ms"),
                    context=f"{event_path}: event.timestamp_ms",
                )
                action_grid_total += 1
                action_grid_success += int(timestamp % PUBLIC_SAMPLE_MS == 0)
                play_events.append(event)

    target_encoding_success = 0
    typed_targets = 0
    engine_overlap = 0
    engine_identity_counts: Counter[str] = Counter()
    public_mask_legal = 0
    overlap_public_mask_legal = 0
    for target in targets:
        identity = target.get("card_identity")
        if isinstance(identity, str) and identity.startswith("card_action:"):
            typed_targets += 1
        actor = _integer(target.get("actor_id"), context="target.actor_id")
        slot = _integer(target.get("hand_slot"), context="target.hand_slot")
        tile = _array(
            target.get("deployment_tile_actor_canonical"),
            context="target.deployment_tile_actor_canonical",
        )
        if len(tile) != 2:
            raise CalibrationError("target canonical tile must have two coordinates")
        x = _integer(tile[0], context="target.tile.x")
        y = _integer(tile[1], context="target.tile.y")
        action = _integer(target.get("expert_action"), context="target.expert_action")
        expected_action = slot * NUM_TILES + y * BOARD_WIDTH + x
        encoded = (
            actor in (0, 1)
            and 0 <= slot < NUM_HAND_SLOTS
            and 0 <= x < BOARD_WIDTH
            and 0 <= y < BOARD_HEIGHT
            and 0 <= action < NO_OP_ACTION
            and action < NUM_ACTIONS
            and action == expected_action
        )
        target_encoding_success += int(encoded)
        legal = target.get("expert_action_in_public_mask")
        if not isinstance(legal, bool):
            raise CalibrationError("target public-mask membership must be boolean")
        public_mask_legal += int(legal)
        if identity in engine.stable_action_keys:
            engine_overlap += 1
            engine_identity_counts[str(identity)] += 1
            overlap_public_mask_legal += int(legal)

    orientation_success = 0
    placement_success = 0
    placement_distances: list[float] = []
    for event in play_events:
        actor = _integer(event.get("player_id"), context="event.player_id")
        absolute = _array(
            event.get("deployment_tile_absolute"),
            context="event.deployment_tile_absolute",
        )
        canonical = _array(
            event.get("deployment_tile_actor_canonical"),
            context="event.deployment_tile_actor_canonical",
        )
        world = _array(
            event.get("deployment_world_position"),
            context="event.deployment_world_position",
        )
        if len(absolute) != 2 or len(canonical) != 2 or len(world) != 2:
            raise CalibrationError("valid event coordinates must have two values")
        absolute_x = _integer(absolute[0], context="event.absolute.x")
        absolute_y = _integer(absolute[1], context="event.absolute.y")
        canonical_x = _integer(canonical[0], context="event.canonical.x")
        canonical_y = _integer(canonical[1], context="event.canonical.y")
        world_x = _number(world[0], context="event.world.x")
        world_y = _number(world[1], context="event.world.y")
        expected = (
            (absolute_x, absolute_y)
            if actor == 0
            else (BOARD_WIDTH - 1 - absolute_x, BOARD_HEIGHT - 1 - absolute_y)
        )
        orientation_success += int((canonical_x, canonical_y) == expected)
        distance = math.hypot(
            world_x - (absolute_x + 0.5), world_y - (absolute_y + 0.5)
        )
        placement_distances.append(distance)
        placement_success += int(distance <= 1.0)

    verified_vocabulary_path: str | None = None
    verified_vocabulary_sha: str | None = None
    if vocabulary_manifest is not None:
        vocabulary_path = Path(vocabulary_manifest).expanduser().resolve()
        if not vocabulary_path.is_file():
            raise CalibrationError(
                f"vocabulary manifest does not exist: {vocabulary_path}"
            )
        verified_vocabulary_path = str(vocabulary_path)
        verified_vocabulary_sha = _sha256(vocabulary_path)
        if verified_vocabulary_sha not in vocabulary_manifest_shas:
            integrity_errors.append(
                "local vocabulary manifest SHA-256 is absent from corpus manifests"
            )

    projection_mapping_complete = bool(
        actor_rows
        and actor_rows_with_join == actor_rows
        and actor_rows_with_stored_mask == actor_rows
        and actor_rows_with_tensor_projection == actor_rows
        and len(provider_semantics_ids) == 1
        and engine.tensor_public_mask_semantics_id in provider_semantics_ids
        and len(provider_semantics_digests) == 1
        and len(provider_lookup_digests) == 1
    )
    missing_mask_mapping_requirements: list[str] = []
    if actor_rows_with_tensor_projection != actor_rows:
        missing_mask_mapping_requirements.append(
            "actor.global_features[11:13] Crown Tower alive/HP state is not "
            "serialized; the source builder confidence-gated tower-zone "
            "extensions, while the tensor provider interprets zero HP as destroyed"
        )
    if not provider_semantics_ids:
        missing_mask_mapping_requirements.append(
            "manifests do not pin the tensor provider semantics_id"
        )
    if not provider_semantics_digests:
        missing_mask_mapping_requirements.append(
            "manifests do not pin the tensor provider semantics_digest"
        )
    if not provider_lookup_digests:
        missing_mask_mapping_requirements.append(
            "manifests do not pin the typed card/entity lookup_digest and card-data authority"
        )

    integrity: dict[str, object] = {
        "status": "pass" if not integrity_errors else "fail",
        "successes": int(not integrity_errors),
        "total": 1,
        "rate": float(not integrity_errors),
        "wilson_95_lower": None,
        "minimum_examples": 1,
        "minimum_wilson_95_lower": None,
    }
    cadence = _rate_channel(exact_row_intervals, row_intervals)
    clock_rate = _rate_channel(clock_rate_success, clock_pairs - clock_resets)
    clock_phase = _rate_channel(clock_reset_success, clock_resets)
    action_grid = _rate_channel(action_grid_success, action_grid_total)
    typed_identity = _rate_channel(engine_overlap, engine_overlap)
    action_encoding = _rate_channel(target_encoding_success, len(targets))
    orientation = _rate_channel(orientation_success, len(play_events))
    coarse_placement = _rate_channel(placement_success, len(play_events))
    phase_additional_successes = _additional_successes_for_wilson(
        clock_reset_success,
        clock_resets,
    )

    required_statuses = (
        integrity["status"],
        cadence["status"],
        clock_rate["status"],
        clock_phase["status"],
        action_grid["status"],
        typed_identity["status"],
        action_encoding["status"],
        orientation["status"],
        coarse_placement["status"],
    )
    if "fail" in required_statuses:
        decision = "fail"
    elif "insufficient_evidence" in required_statuses:
        decision = "insufficient_evidence"
    else:
        decision = "pass_bounded_channels"

    corpus_digest = hashlib.sha256(
        "\n".join(sorted(digest_records)).encode("utf-8")
    ).hexdigest()
    return {
        "schema": CALIBRATION_SCHEMA,
        "decision": decision,
        "scope": {
            "statement": (
                "Only 100-ms clock/phase, typed action geometry, canonical "
                "orientation, coarse placement encoding, and stored public-mask "
                "projection/provenance completeness are compared."
            ),
            "overall_real_game_calibration_complete": False,
            "minimum_examples": MINIMUM_EXAMPLES,
            "minimum_wilson_95_lower": MINIMUM_SUCCESS_RATE,
        },
        "engine": {
            "manifest_path": engine.manifest_path,
            "manifest_sha256": engine.manifest_sha256,
            "supported_public_cards": len(engine.supported_public_cards),
            "typed_action_keys": len(engine.stable_action_keys),
            "canonical_lane_globals": engine.canonical_lane_globals,
            "public_mask_contract_version": engine.public_mask_contract_version,
            "logic_tick_ms": engine.logic_tick_ms,
            "regulation_ticks": engine.regulation_ticks,
            "regulation_seconds": (
                engine.regulation_ticks * engine.logic_tick_ms / 1000.0
            ),
            "tiebreak_ticks": engine.tiebreak_ticks,
            "tiebreak_seconds": (engine.tiebreak_ticks * engine.logic_tick_ms / 1000.0),
            "real_frame_public_mask_adapter": (engine.real_frame_public_mask_adapter),
            "tensor_public_mask_provider": engine.tensor_public_mask_provider,
            "tensor_public_mask_semantics_id": (
                engine.tensor_public_mask_semantics_id
            ),
        },
        "corpus": {
            "root": str(corpus_roots[0]),
            "roots": [str(value) for value in corpus_roots],
            "matches_by_root": dict(sorted(matches_by_root.items())),
            "artifact_set_sha256": corpus_digest,
            "matches": len(manifests),
            "distinct_match_ids": len(match_ids),
            "neutral_rows": row_intervals + len(manifests),
            "clock_valid_rows": clock_rows,
            "valid_play_events": len(play_events),
            "actor_targets": len(targets),
            "actor_trajectory_artifacts": actor_artifacts,
            "actor_trajectory_rows": actor_rows,
            "vocabulary_manifest_sha256s": dict(
                sorted(vocabulary_manifest_shas.items())
            ),
            "verified_local_vocabulary_manifest_path": verified_vocabulary_path,
            "verified_local_vocabulary_manifest_sha256": verified_vocabulary_sha,
        },
        "channels": {
            "artifact_integrity": {
                **integrity,
                "errors": integrity_errors,
            },
            "sampling_100ms": cadence,
            "clock_local_rate_within_one_second": {
                **clock_rate,
                "maximum_error_seconds": (
                    None if not clock_rate_errors else max(clock_rate_errors)
                ),
                "p95_error_seconds": _percentile(clock_rate_errors, 0.95),
            },
            "regulation_to_overtime_phase": {
                **clock_phase,
                "observed_resets": clock_resets,
                "expected_transition": "1 -> 120 seconds",
                "maximum_media_time_error_seconds": (
                    None if not reset_time_errors else max(reset_time_errors)
                ),
                "minimum_example_count_met": clock_resets >= MINIMUM_EXAMPLES,
                "additional_all_success_examples_needed_for_confidence_gate": (
                    phase_additional_successes
                ),
                "selection_policy": (
                    "All manifests from every declared root and all observed "
                    "clock resets are counted; duplicate match IDs fail integrity."
                ),
                "limitation": (
                    f"Observed {clock_resets} reset examples; the count floor is "
                    f"{MINIMUM_EXAMPLES}, but the Wilson lower-bound gate also "
                    f"requires {phase_additional_successes} additional successful "
                    "examples at the current failure count."
                ),
            },
            "overtime_to_tiebreak_phase": {
                "status": "unavailable",
                "examples": 0,
                "reason": (
                    "The corpus has no independently labelled 5:00 terminal "
                    "boundary or tiebreak outcome."
                ),
            },
            "play_timestamp_100ms_grid": action_grid,
            "typed_action_identity": {
                **typed_identity,
                "typed_targets": typed_targets,
                "engine_overlap_targets": engine_overlap,
                "out_of_engine_scope_targets": len(targets) - engine_overlap,
                "represented_engine_keys": len(engine_identity_counts),
                "keys_with_at_least_30_examples": sum(
                    count >= MINIMUM_EXAMPLES
                    for count in engine_identity_counts.values()
                ),
                "claim_boundary": (
                    "Pass means exact typed-key compatibility for accepted labels, "
                    "not independent visual-classifier accuracy."
                ),
            },
            "hand_slot_action_encoding": action_encoding,
            "public_mask_v2": {
                "status": "contract_only",
                "manifest_versions": dict(sorted(public_mask_versions.items())),
                "targets_in_corpus_mask": public_mask_legal,
                "targets": len(targets),
                "engine_overlap_targets_in_corpus_mask": (overlap_public_mask_legal),
                "engine_overlap_targets": engine_overlap,
                "engine_equivalence": "unavailable",
                "tensor_provider_available": engine.tensor_public_mask_provider,
                "tensor_provider_semantics_id": (
                    engine.tensor_public_mask_semantics_id
                ),
                "actor_trajectory_artifacts": actor_artifacts,
                "actor_rows": actor_rows,
                "actor_rows_joinable_to_neutral_public_state": (
                    actor_rows_with_join
                ),
                "actor_rows_with_valid_stored_mask_contract": (
                    actor_rows_with_stored_mask
                ),
                "actor_rows_with_complete_tensor_projection": (
                    actor_rows_with_tensor_projection
                ),
                "manifests_with_vocabulary_sha256": sum(
                    vocabulary_manifest_shas.values()
                ),
                "declared_vocabulary_sha256s": dict(
                    sorted(vocabulary_manifest_shas.items())
                ),
                "verified_local_vocabulary_manifest_sha256": (
                    verified_vocabulary_sha
                ),
                "manifests_with_provider_semantics_id": sum(
                    provider_semantics_ids.values()
                ),
                "manifests_with_provider_semantics_digest": sum(
                    provider_semantics_digests.values()
                ),
                "manifests_with_provider_lookup_digest": sum(
                    provider_lookup_digests.values()
                ),
                "projection_mapping_complete": projection_mapping_complete,
                "missing_mapping_requirements": missing_mask_mapping_requirements,
                "reason": (
                    "The tensor provider is callable, but the corpus cannot be "
                    "losslessly projected into its inputs and does not pin its "
                    "semantics/lookup digests. Running it would require inventing "
                    "tower state or lookup authority, so stored label-independent "
                    "masks cannot prove engine equality."
                ),
            },
            "canonical_orientation": orientation,
            "coarse_placement_encoding": {
                **coarse_placement,
                "median_center_error_tiles": _percentile(placement_distances, 0.5),
                "p95_center_error_tiles": _percentile(placement_distances, 0.95),
                "maximum_center_error_tiles": (
                    None
                    if not placement_distances
                    else round(max(placement_distances), 6)
                ),
                "claim_boundary": (
                    "The tile and continuous point share a visual source; this is "
                    "an encoding sanity gate, not independent geometry accuracy."
                ),
            },
        },
        "unavailable_channels": {
            "play_onset_alignment": "100-ms quantization is not onset accuracy",
            "visible_entity_trajectory": (
                "no manually associated action-to-entity center tracks"
            ),
            "exact_hp_and_damage": "accepted HP detections are not value-calibrated",
            "projectile_source_target_and_flight": "zero calibrated labels",
            "status_onset_and_duration": "zero calibrated labels",
            "outcomes": (
                "no independent crowns, winner, terminal reason, or tiebreak labels"
            ),
            "hero_evolution_variant_accuracy": (
                "no independently reviewed variant-specific action labels"
            ),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a concise, non-upgrading handoff from a calibration result."""

    engine = _object(report["engine"], context="report.engine")
    corpus = _object(report["corpus"], context="report.corpus")
    channels = _object(report["channels"], context="report.channels")
    unavailable = _object(
        report["unavailable_channels"], context="report.unavailable_channels"
    )
    lines = [
        "# Simple Gym real-corpus calibration gate",
        "",
        f"Decision: `{report['decision']}`.",
        "",
        (
            f"The read-only gate covered {corpus['matches']} matches, "
            f"{corpus['neutral_rows']} neutral 10-Hz rows, "
            f"{corpus['valid_play_events']} valid visual play events, and "
            f"{corpus['actor_targets']} aligned actor targets."
        ),
        "",
        "## Engine boundary",
        "",
        (
            f"The actual CPU setup compiler accepted {engine['supported_public_cards']} "
            f"public roots with {engine['logic_tick_ms']}-ms ticks, "
            f"{engine['regulation_seconds']:.0f}-s regulation, and "
            f"{engine['tiebreak_seconds']:.0f}-s tiebreak. Canonical lanes are "
            f"`{str(engine['canonical_lane_globals']).lower()}` and the public-mask "
            f"contract is v{engine['public_mask_contract_version']}."
        ),
        "",
        "## Channel decisions",
        "",
        "| Channel | Status | Evidence boundary |",
        "| --- | --- | --- |",
    ]
    summaries = {
        "artifact_integrity": "declared SHA-256 and row counts",
        "sampling_100ms": "all materialized row intervals",
        "clock_local_rate_within_one_second": "accepted adjacent clock rows",
        "regulation_to_overtime_phase": "1-to-120 reset near 180 s",
        "overtime_to_tiebreak_phase": "no independent terminal label",
        "play_timestamp_100ms_grid": "valid visual play timestamps",
        "typed_action_identity": "engine-overlap typed keys only",
        "hand_slot_action_encoding": "slot x tile-index structure",
        "public_mask_v2": "stored contract; incomplete tensor input mapping",
        "canonical_orientation": "actor-1 180-degree rotation",
        "coarse_placement_encoding": "derived point to encoded tile center",
    }
    for name, summary in summaries.items():
        channel = _object(channels[name], context=f"report.channels.{name}")
        lines.append(f"| {name} | `{channel['status']}` | {summary} |")
    phase = _object(
        channels["regulation_to_overtime_phase"],
        context="report.channels.regulation_to_overtime_phase",
    )
    if phase["status"] == "insufficient_evidence":
        phase_sentence = (
            "The phase channel remains insufficient because the complete corpus "
            f"contains {phase['observed_resets']} regulation-to-overtime resets, "
            "below the configured example gate."
        )
    elif phase["status"] == "pass":
        phase_sentence = "The regulation-to-overtime phase channel passes."
    else:
        phase_sentence = (
            "The complete multi-root sample crosses the count floor but the "
            "regulation-to-overtime phase channel fails its configured Wilson "
            f"gate; it needs {phase['additional_all_success_examples_needed_for_confidence_gate']} "
            "additional successful examples at the current failure count."
        )
    mask = _object(channels["public_mask_v2"], context="report.channels.public_mask_v2")
    mask_sentence = (
        "The tensor public-mask-v2 provider is callable, but equality is unavailable "
        "because the corpus omits Crown Tower state and the provider "
        "semantics/lookup digests needed for a lossless input mapping."
        if mask["engine_equivalence"] == "unavailable"
        else "Public-mask v2 engine equivalence is available."
    )
    lines.extend(
        (
            "",
            f"{phase_sentence} {mask_sentence}",
            "",
            "## Public-mask mapping audit",
            "",
            (
                f"All {mask['actor_rows']} actor rows join to neutral public state "
                f"and {mask['actor_rows_with_valid_stored_mask_contract']} carry a "
                "structurally valid stored v2 mask. However, "
                f"{mask['actor_rows_with_complete_tensor_projection']} rows carry "
                "the complete tensor projection, and zero manifests pin each of "
                "the provider semantics ID, semantics digest, and typed lookup digest."
            ),
            "",
            "Missing requirements:",
            "",
        )
    )
    for requirement in _array(
        mask["missing_mapping_requirements"],
        context="report.channels.public_mask_v2.missing_mapping_requirements",
    ):
        lines.append(f"- {requirement}.")
    lines.extend(
        (
            "",
            "## Explicitly unavailable",
            "",
        )
    )
    for name, reason in unavailable.items():
        lines.append(f"- `{name}`: {reason}.")
    lines.extend(
        (
            "",
            (
                "These unavailable channels are not passes. In particular, the corpus "
                "does not calibrate HP/damage, projectiles, statuses, or outcomes."
            ),
            "",
            "## Reproducibility",
            "",
            f"- Corpus artifact-set SHA-256: `{corpus['artifact_set_sha256']}`",
            f"- Engine manifest SHA-256: `{engine['manifest_sha256']}`",
            "- The command opens corpus artifacts read-only and writes only stdout.",
            "",
        )
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare simple-Gym observable contracts to a real-match corpus."
    )
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument(
        "--additional-corpus-root",
        action="append",
        default=[],
        type=Path,
        help=(
            "include another complete, disjoint corpus root; may be repeated"
        ),
    )
    parser.add_argument(
        "--engine-manifest",
        type=Path,
        default=Path("training_decks/simple_gym_supported_v1.json"),
    )
    parser.add_argument(
        "--vocabulary-manifest",
        type=Path,
        help="optional local vocabulary artifact to verify against corpus SHA-256",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = parse_args(argv)
    try:
        engine = load_engine_contract(args.engine_manifest)
        report = audit_real_corpus(
            args.corpus_root,
            engine,
            additional_roots=args.additional_corpus_root,
            vocabulary_manifest=args.vocabulary_manifest,
        )
    except CalibrationError as exc:
        stderr.write(f"error: {exc}\n")
        return 2
    if args.format == "markdown":
        stdout.write(render_markdown(report))
    else:
        json.dump(report, stdout, indent=2, sort_keys=True)
        stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
