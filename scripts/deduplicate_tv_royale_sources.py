"""Build a fail-closed cross-source TV Royale media deduplication index.

The YouTube side is an explicit, permission-preserving ten-video canary
manifest.  The Hugging Face side is reconstructed from existing raw-cascade
run/game manifests and their retained audit frames.  A perceptual match is
only a *candidate* until a human visual review confirms it.  Unresolved
candidate components are quarantined, and every confirmed component receives
one atomic split assignment.
"""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256

TARGET_FRACTIONS = (0.10, 0.50, 0.90)
NORMALIZED_SIZE = (288, 512)
PHASH_DISTANCE_THRESHOLD = 8
MAX_DURATION_DELTA_SECONDS = 2.0
HF_AUDIT_FRACTION_TOLERANCE = 0.12
_FRAME_NUMBER = re.compile(r"frame_(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class Artifact:
    key: str
    source: str
    source_id: str
    proposed_split: str
    duration_seconds: float | None
    players: tuple[str, ...]
    decks: tuple[tuple[str, ...], ...]
    permission_provenance: Mapping[str, Any]
    frames: Mapping[float, Mapping[str, Any]]


class _DisjointSet:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _normalized_players(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted(filter(None, (_normalized_text(str(item)) for item in value))))


def _normalized_decks(value: Any) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        return ()
    decks: list[tuple[str, ...]] = []
    for deck in value:
        if not isinstance(deck, list):
            continue
        normalized = tuple(
            sorted(filter(None, (_normalized_text(str(card)) for card in deck)))
        )
        if normalized:
            decks.append(normalized)
    return tuple(sorted(decks))


def _resolve_path(path: str, *, relative_to: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = relative_to / candidate
    return candidate.resolve()


def _crop_box(
    image: Image.Image, crop: Sequence[object] | None
) -> tuple[int, int, int, int]:
    if crop is None:
        return (0, 0, image.width, image.height)
    if len(crop) != 4:
        raise ValueError("arena_crop must contain four normalized coordinates")
    values = tuple(float(str(value)) for value in crop)
    if not (
        0.0 <= values[0] < values[2] <= 1.0
        and 0.0 <= values[1] < values[3] <= 1.0
    ):
        raise ValueError("arena_crop must be ordered within [0, 1]")
    left = round(values[0] * image.width)
    top = round(values[1] * image.height)
    right = round(values[2] * image.width)
    bottom = round(values[3] * image.height)
    if right <= left or bottom <= top:
        raise ValueError("arena_crop became empty after pixel conversion")
    return (left, top, right, bottom)


def _phash(rgb: np.ndarray) -> str:
    grayscale = np.asarray(
        Image.fromarray(rgb, mode="RGB").convert("L").resize(
            (32, 32), Image.Resampling.LANCZOS
        ),
        dtype=np.float64,
    )
    indices = np.arange(32, dtype=np.float64)
    basis = np.cos(math.pi / 32.0 * (indices[:, None] + 0.5) * indices[None, :])
    basis[:, 0] *= 1.0 / math.sqrt(2.0)
    dct = basis.T @ grayscale @ basis
    low = dct[:8, :8]
    median = float(np.median(low.reshape(-1)[1:]))
    bits = (low > median).reshape(-1)
    value = 0
    for bit in bits.tolist():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def fingerprint_frame(
    path: Path, *, arena_crop: Sequence[object] | None = None
) -> dict[str, Any]:
    """Return a deterministic decoded-pixel SHA and 64-bit perceptual hash."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as loaded:
        source_size = [loaded.width, loaded.height]
        box = _crop_box(loaded, arena_crop)
        cropped = np.asarray(loaded.convert("RGB").crop(box), dtype=np.uint8)
    fingerprint = fingerprint_rgb(cropped)
    return {
        "path": str(path),
        "file_sha256": file_sha256(path),
        "source_size": source_size,
        "arena_crop_normalized": list(arena_crop) if arena_crop is not None else None,
        **fingerprint,
    }


def fingerprint_rgb(rgb: np.ndarray) -> dict[str, Any]:
    """Fingerprint an already selected RGB arena crop."""
    values = np.asarray(rgb, dtype=np.uint8)
    if values.ndim != 3 or values.shape[2] != 3 or not values.size:
        raise ValueError("RGB fingerprint input must have shape [height, width, 3]")
    normalized = Image.fromarray(values, mode="RGB").resize(
        NORMALIZED_SIZE, Image.Resampling.LANCZOS
    )
    pixels = np.asarray(normalized, dtype=np.uint8)
    header = f"RGB:{NORMALIZED_SIZE[0]}x{NORMALIZED_SIZE[1]}\0".encode()
    return {
        "normalized_size": list(NORMALIZED_SIZE),
        "normalized_frame_sha256": hashlib.sha256(
            header + pixels.tobytes(order="C")
        ).hexdigest(),
        "phash64": _phash(pixels),
    }


def phash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return payload


def _required_target_frames(
    rows: Sequence[Mapping[str, Any]], *, relative_to: Path
) -> dict[float, Mapping[str, Any]]:
    by_fraction: dict[float, Mapping[str, Any]] = {}
    for row in rows:
        fraction = float(row.get("fraction", -1.0))
        target = next(
            (value for value in TARGET_FRACTIONS if abs(value - fraction) < 1e-6),
            None,
        )
        if target is None or target in by_fraction:
            raise ValueError("frames must contain one entry at each of 0.1, 0.5, 0.9")
        path = _resolve_path(str(row.get("path", "")), relative_to=relative_to)
        by_fraction[target] = {
            **dict(row),
            **fingerprint_frame(path, arena_crop=row.get("arena_crop")),
            "fraction": target,
        }
    if set(by_fraction) != set(TARGET_FRACTIONS):
        raise ValueError("frames must contain exactly 10%, 50%, and 90%")
    return by_fraction


def load_youtube_canary(path: Path) -> tuple[list[Artifact], dict[str, Any]]:
    payload = _read_json(path)
    videos = payload.get("videos")
    if not isinstance(videos, list) or len(videos) != 10:
        raise ValueError("YouTube canary manifest must contain exactly ten videos")
    root_permission = payload.get("permission_provenance")
    if not isinstance(root_permission, dict) or not root_permission:
        raise ValueError("YouTube canary permission_provenance is required")
    artifacts: list[Artifact] = []
    seen: set[str] = set()
    for row in videos:
        if not isinstance(row, dict):
            raise TypeError("YouTube video entry must be an object")
        source_id = str(row.get("id", ""))
        if not source_id or source_id in seen:
            raise ValueError("YouTube video IDs must be nonempty and unique")
        seen.add(source_id)
        permission = row.get("permission_provenance", root_permission)
        if not isinstance(permission, dict) or not permission:
            raise ValueError(f"video {source_id} has no permission provenance")
        frame_rows = row.get("frames")
        if not isinstance(frame_rows, list):
            raise TypeError(f"video {source_id} has no frame artifacts")
        duration = row.get("duration_seconds")
        artifacts.append(
            Artifact(
                key=f"youtube:{source_id}",
                source="youtube",
                source_id=source_id,
                proposed_split=str(row.get("split", "quarantine_unassigned")),
                duration_seconds=float(duration) if duration is not None else None,
                players=_normalized_players(row.get("players")),
                decks=_normalized_decks(row.get("decks")),
                permission_provenance=dict(permission),
                frames=_required_target_frames(
                    frame_rows, relative_to=path.resolve().parent
                ),
            )
        )
    provenance = {
        "manifest": str(path.resolve()),
        "manifest_sha256": file_sha256(path),
        "permission_provenance": dict(root_permission),
        "permission_provenance_preserved_verbatim": True,
        "permission_reclassified_as_creative_commons": False,
    }
    return artifacts, provenance


def _load_hf_split_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = _read_json(path)
    result: dict[str, str] = {}
    splits = payload.get("splits")
    if not isinstance(splits, dict):
        raise TypeError("HF split manifest has no splits object")
    for split, value in splits.items():
        if not isinstance(value, dict):
            continue
        replay_ids = value.get("replay_ids", [])
        if not isinstance(replay_ids, list):
            raise TypeError(f"HF split {split} replay_ids must be a list")
        for replay in replay_ids:
            replay_id = str(replay)
            previous = result.setdefault(replay_id, str(split))
            if previous != split:
                raise ValueError(f"HF replay {replay_id} crosses source splits")
    return result


def _game_manifest_path(record: Mapping[str, Any], run_manifest: Path) -> Path:
    corpus = record.get("corpus")
    if corpus:
        candidate = Path(str(corpus)).expanduser().resolve().parent / "manifest.json"
        if candidate.is_file():
            return candidate
    replay = str(record.get("replay", ""))
    arena = str(record.get("arena", ""))
    candidate = run_manifest.resolve().parent / "games" / arena / replay / "manifest.json"
    return candidate


def _audit_frame_number(path: Path) -> int | None:
    match = _FRAME_NUMBER.search(path.name)
    return int(match.group(1)) if match else None


def _hf_target_frame_rows(
    game: Mapping[str, Any], *, game_manifest_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit_paths = [
        _resolve_path(str(raw_path), relative_to=game_manifest_path.parent)
        for raw_path in game.get("audit_outputs", [])
    ]
    retained_audits = [path for path in audit_paths if path.is_file()]
    declared = game.get("deduplication_frames", [])
    if not isinstance(declared, list):
        raise TypeError("deduplication_frames must be a list when present")
    candidates: dict[float, dict[str, Any]] = {}
    for raw in declared:
        if not isinstance(raw, dict):
            raise TypeError("deduplication frame entry must be an object")
        fraction = float(raw.get("fraction", -1.0))
        target = next(
            (value for value in TARGET_FRACTIONS if abs(value - fraction) < 1e-6),
            None,
        )
        if target is None or target in candidates:
            raise ValueError("deduplication_frames must uniquely declare 0.1/0.5/0.9")
        candidates[target] = dict(raw)
    rows: list[dict[str, Any]] = []
    missing: list[float] = []
    for target in TARGET_FRACTIONS:
        candidate = candidates.get(target)
        if candidate is None:
            missing.append(target)
            continue
        rows.append({**candidate, "fraction": target})
    return rows, {
        "retained_audit_frames": len(retained_audits),
        "retained_audit_temporal_contract": (
            "event-preferred extraction audit; not 10/50/90 evidence"
        ),
        "declared_deduplication_frames": len(candidates),
        "target_fractions_available": [row["fraction"] for row in rows],
        "target_fractions_missing": missing,
        "complete_three_point_signature": not missing,
    }


def inventory_hf_evidence(
    run_manifests: Sequence[Path], *, split_manifest: Path | None = None
) -> dict[str, Any]:
    split_map = _load_hf_split_map(split_manifest)
    total = 0
    game_manifests = 0
    complete_three_point = 0
    availability: Counter[str] = Counter()
    missing_game_manifests = 0
    for run_manifest in run_manifests:
        payload = _read_json(run_manifest)
        for record in payload.get("records", []):
            if not isinstance(record, dict) or record.get("status") != "complete":
                continue
            total += 1
            game_path = _game_manifest_path(record, run_manifest)
            if not game_path.is_file():
                missing_game_manifests += 1
                continue
            game_manifests += 1
            _, evidence = _hf_target_frame_rows(
                _read_json(game_path), game_manifest_path=game_path
            )
            signature = tuple(evidence["target_fractions_available"])
            availability[str(signature)] += 1
            complete_three_point += int(evidence["complete_three_point_signature"])
    return {
        "run_manifests": [
            {"path": str(path.resolve()), "sha256": file_sha256(path)}
            for path in run_manifests
        ],
        "split_manifest": (
            {"path": str(split_manifest.resolve()), "sha256": file_sha256(split_manifest)}
            if split_manifest is not None
            else None
        ),
        "completed_records": total,
        "game_manifests_found": game_manifests,
        "missing_game_manifests": missing_game_manifests,
        "complete_three_point_signatures": complete_three_point,
        "target_availability_patterns": dict(sorted(availability.items())),
        "known_split_assignments": len(split_map),
        "permission_provenance": {
            "dataset_ids": sorted(
                {
                    str(_read_json(path).get("dataset"))
                    for path in run_manifests
                    if _read_json(path).get("dataset")
                }
            ),
            "explicit_media_license_evidence": None,
            "creative_commons_license_claimed": False,
            "note": "Existing local run manifests contain no permission grant.",
        },
    }


def load_hf_artifacts(
    run_manifests: Sequence[Path], *, split_manifest: Path | None = None
) -> tuple[list[Artifact], dict[str, Any]]:
    split_map = _load_hf_split_map(split_manifest)
    artifacts: list[Artifact] = []
    seen: set[str] = set()
    incomplete: list[dict[str, Any]] = []
    for run_manifest in run_manifests:
        run = _read_json(run_manifest)
        dataset_id = str(run.get("dataset", "unknown"))
        permission = {
            "dataset_id": dataset_id,
            "run_manifest": str(run_manifest.resolve()),
            "explicit_media_license_evidence": None,
            "creative_commons_license_claimed": False,
        }
        for record in run.get("records", []):
            if not isinstance(record, dict) or record.get("status") != "complete":
                continue
            replay = str(record.get("replay", ""))
            key = f"huggingface:{replay}"
            if not replay or key in seen:
                continue
            seen.add(key)
            game_path = _game_manifest_path(record, run_manifest)
            if not game_path.is_file():
                incomplete.append({"key": key, "reason": "missing_game_manifest"})
                continue
            game = _read_json(game_path)
            rows, evidence = _hf_target_frame_rows(game, game_manifest_path=game_path)
            if not evidence["complete_three_point_signature"]:
                incomplete.append({"key": key, **evidence})
                continue
            total_frames = int(game.get("frames", 0))
            artifacts.append(
                Artifact(
                    key=key,
                    source="huggingface",
                    source_id=replay,
                    proposed_split=split_map.get(replay, "quarantine_unassigned"),
                    duration_seconds=(total_frames / 10.0 if total_frames else None),
                    players=_normalized_players(game.get("players")),
                    decks=_normalized_decks([game.get("deck", [])]),
                    permission_provenance=permission,
                    frames=_required_target_frames(rows, relative_to=game_path.parent),
                )
            )
    return artifacts, {
        "inventory": inventory_hf_evidence(
            run_manifests, split_manifest=split_manifest
        ),
        "eligible_three_point_artifacts": len(artifacts),
        "incomplete_artifacts": incomplete,
        "incomplete_artifacts_count": len(incomplete),
    }


def load_hf_fingerprint_shards(
    paths: Sequence[Path],
    *,
    run_manifests: Sequence[Path],
    split_manifest: Path | None = None,
) -> tuple[list[Artifact], dict[str, Any]]:
    """Load exact three-point fingerprints reconstructed from source parquet."""
    split_map = _load_hf_split_map(split_manifest)
    expected: dict[str, tuple[str, str]] = {}
    for run_path in run_manifests:
        run = _read_json(run_path)
        dataset_id = str(run.get("dataset", "unknown"))
        for row in run.get("records", []):
            if isinstance(row, dict) and row.get("status") == "complete":
                expected[str(row.get("replay"))] = (str(row.get("sha256")), dataset_id)
    artifacts: list[Artifact] = []
    seen: set[str] = set()
    shard_provenance = []
    for path in paths:
        payload = _read_json(path)
        if payload.get("schema") != "tv-royale-hf-fingerprint-shard-v1":
            raise ValueError(f"unsupported HF fingerprint shard: {path}")
        shard_provenance.append({"path": str(path.resolve()), "sha256": file_sha256(path)})
        for row in payload.get("entries", []):
            if not isinstance(row, dict):
                raise TypeError("HF fingerprint entry must be an object")
            replay = str(row.get("replay", ""))
            expected_source = expected.get(replay)
            if expected_source is None:
                raise ValueError(f"fingerprint replay absent from source run: {replay}")
            if row.get("source_parquet_sha256") != expected_source[0]:
                raise ValueError(f"fingerprint source SHA mismatch for {replay}")
            if replay in seen:
                raise ValueError(f"duplicate replay across fingerprint shards: {replay}")
            seen.add(replay)
            frames = row.get("frames")
            if not isinstance(frames, list):
                raise TypeError(f"fingerprint frames must be a list for {replay}")
            by_fraction: dict[float, Mapping[str, Any]] = {}
            for frame in frames:
                if not isinstance(frame, dict):
                    raise TypeError("fingerprint frame must be an object")
                fraction = float(frame.get("fraction", -1.0))
                if fraction not in TARGET_FRACTIONS or fraction in by_fraction:
                    raise ValueError(f"invalid fingerprint fractions for {replay}")
                if not frame.get("normalized_frame_sha256") or not frame.get("phash64"):
                    raise ValueError(f"incomplete fingerprint for {replay} at {fraction}")
                by_fraction[fraction] = dict(frame)
            if set(by_fraction) != set(TARGET_FRACTIONS):
                raise ValueError(f"fingerprint shard lacks 10/50/90 for {replay}")
            artifacts.append(
                Artifact(
                    key=f"huggingface:{replay}",
                    source="huggingface",
                    source_id=replay,
                    proposed_split=split_map.get(replay, "quarantine_unassigned"),
                    duration_seconds=float(row["duration_seconds"]),
                    players=_normalized_players(row.get("players")),
                    decks=_normalized_decks(row.get("decks")),
                    permission_provenance=dict(row.get("permission_provenance", {})),
                    frames=by_fraction,
                )
            )
    return artifacts, {
        "shards": shard_provenance,
        "replays": len(artifacts),
        "source_run_replays": len(expected),
        "complete_source_coverage": len(artifacts) == len(expected),
    }


def _review_map(path: Path | None) -> tuple[dict[tuple[str, str], dict[str, Any]], Any]:
    if path is None:
        return {}, None
    payload = _read_json(path)
    reviews: dict[tuple[str, str], dict[str, Any]] = {}
    for row in payload.get("reviews", []):
        if not isinstance(row, dict):
            raise TypeError("dedup review entry must be an object")
        left = str(row.get("left", ""))
        right = str(row.get("right", ""))
        if not left or not right or left == right:
            raise ValueError("dedup review must identify two distinct artifacts")
        result = row.get("visual_confirmation")
        if result not in {"duplicate", "distinct"}:
            raise ValueError("visual_confirmation must be duplicate or distinct")
        if not row.get("reviewer"):
            raise ValueError("dedup visual confirmation requires a reviewer")
        key = (left, right) if left < right else (right, left)
        if key in reviews:
            raise ValueError(f"duplicate dedup review for {key}")
        reviews[key] = dict(row)
    return reviews, {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "reviews": len(reviews),
    }


def _compare_metadata(left: Artifact, right: Artifact) -> dict[str, Any]:
    duration_delta = (
        abs(left.duration_seconds - right.duration_seconds)
        if left.duration_seconds is not None and right.duration_seconds is not None
        else None
    )
    players_available = bool(left.players and right.players)
    decks_available = bool(left.decks and right.decks)
    return {
        "duration_seconds": [left.duration_seconds, right.duration_seconds],
        "duration_delta_seconds": duration_delta,
        "duration_within_threshold": (
            duration_delta <= MAX_DURATION_DELTA_SECONDS
            if duration_delta is not None
            else None
        ),
        "players_available_both": players_available,
        "players_match": left.players == right.players if players_available else None,
        "normalized_players": [list(left.players), list(right.players)],
        "decks_available_both": decks_available,
        "decks_match": left.decks == right.decks if decks_available else None,
        "normalized_decks": [
            [list(deck) for deck in left.decks],
            [list(deck) for deck in right.decks],
        ],
    }


def _compare_frames(left: Artifact, right: Artifact) -> dict[str, Any]:
    rows = []
    for fraction in TARGET_FRACTIONS:
        left_frame = left.frames[fraction]
        right_frame = right.frames[fraction]
        rows.append(
            {
                "fraction": fraction,
                "exact_normalized_sha256_match": left_frame[
                    "normalized_frame_sha256"
                ]
                == right_frame["normalized_frame_sha256"],
                "phash_distance": phash_distance(
                    str(left_frame["phash64"]), str(right_frame["phash64"])
                ),
                "left": dict(left_frame),
                "right": dict(right_frame),
            }
        )
    return {
        "points": rows,
        "exact_points": sum(row["exact_normalized_sha256_match"] for row in rows),
        "close_phash_points": sum(
            int(row["phash_distance"] <= PHASH_DISTANCE_THRESHOLD) for row in rows
        ),
    }


def _atomic_split(
    members: Sequence[Artifact], *, unresolved: bool, incomplete_hf_index: bool
) -> str:
    if unresolved:
        return "quarantine_dedup_review"
    if incomplete_hf_index and any(member.source == "youtube" for member in members):
        return "quarantine_incomplete_hf_index"
    priority = {
        "train": 0,
        "validation": 1,
        "archetype_test": 2,
        "chronology_test": 3,
        "final_test": 4,
        "quarantine_unassigned": 5,
    }
    return max(
        (artifact.proposed_split for artifact in members),
        key=lambda split: (priority.get(split, 6), split),
    )


def build_dedup_report(
    *,
    youtube_manifest: Path,
    hf_run_manifests: Sequence[Path],
    hf_split_manifest: Path | None = None,
    review_manifest: Path | None = None,
    hf_fingerprint_shards: Sequence[Path] = (),
) -> dict[str, Any]:
    youtube, youtube_provenance = load_youtube_canary(youtube_manifest)
    if hf_fingerprint_shards:
        huggingface, fingerprint_provenance = load_hf_fingerprint_shards(
            hf_fingerprint_shards,
            run_manifests=hf_run_manifests,
            split_manifest=hf_split_manifest,
        )
        hf_provenance = {
            "inventory": inventory_hf_evidence(
                hf_run_manifests, split_manifest=hf_split_manifest
            ),
            "fingerprint_index": fingerprint_provenance,
            "eligible_three_point_artifacts": len(huggingface),
            "incomplete_artifacts_count": (
                fingerprint_provenance["source_run_replays"] - len(huggingface)
            ),
        }
    else:
        huggingface, hf_provenance = load_hf_artifacts(
            hf_run_manifests, split_manifest=hf_split_manifest
        )
    reviews, review_provenance = _review_map(review_manifest)
    artifacts = youtube + huggingface
    incomplete_hf_index = hf_provenance["incomplete_artifacts_count"] > 0
    by_key = {artifact.key: artifact for artifact in artifacts}
    candidates: list[dict[str, Any]] = []
    disjoint = _DisjointSet(by_key)
    unresolved_pairs: set[tuple[str, str]] = set()
    confirmed_pairs: set[tuple[str, str]] = set()
    for left in youtube:
        for right in huggingface:
            metadata = _compare_metadata(left, right)
            frames = _compare_frames(left, right)
            duration_ok = metadata["duration_within_threshold"] is not False
            media_candidate = frames["close_phash_points"] >= 2 and duration_ok
            if not media_candidate:
                continue
            pair = (
                (left.key, right.key)
                if left.key < right.key
                else (right.key, left.key)
            )
            review = reviews.get(pair)
            status = "candidate_needs_visual_confirmation"
            if review and review["visual_confirmation"] == "duplicate":
                status = "confirmed_duplicate"
                confirmed_pairs.add(pair)
                disjoint.union(*pair)
            elif review and review["visual_confirmation"] == "distinct":
                status = "reviewed_distinct"
            else:
                unresolved_pairs.add(pair)
                disjoint.union(*pair)
            candidates.append(
                {
                    "left": left.key,
                    "right": right.key,
                    "status": status,
                    "metadata_evidence": metadata,
                    "frame_evidence": frames,
                    "visual_review": review,
                }
            )

    components: dict[str, list[Artifact]] = {}
    for artifact in artifacts:
        components.setdefault(disjoint.find(artifact.key), []).append(artifact)
    groups: list[dict[str, Any]] = []
    assignment: dict[str, dict[str, Any]] = {}
    for members in sorted(components.values(), key=lambda group: sorted(x.key for x in group)):
        keys = sorted(member.key for member in members)
        member_set = set(keys)
        unresolved = any(set(pair).issubset(member_set) for pair in unresolved_pairs)
        confirmed = any(set(pair).issubset(member_set) for pair in confirmed_pairs)
        split = _atomic_split(
            members,
            unresolved=unresolved,
            incomplete_hf_index=incomplete_hf_index,
        )
        group_id = "dedup-" + hashlib.sha256("\0".join(keys).encode()).hexdigest()[:16]
        if unresolved:
            status = "candidate_quarantine"
        elif incomplete_hf_index and any(
            member.source == "youtube" for member in members
        ):
            status = "incomplete_hf_index_quarantine"
        elif confirmed:
            status = "confirmed_duplicate"
        else:
            status = "singleton"
        groups.append(
            {
                "group_id": group_id,
                "status": status,
                "members": keys,
                "atomic_split": split,
                "eligible_for_training": not unresolved
                and split != "quarantine_unassigned",
            }
        )
        for member in members:
            assignment[member.key] = {
                "group_id": group_id,
                "source": member.source,
                "source_id": member.source_id,
                "proposed_split": member.proposed_split,
                "atomic_split": split,
                "group_status": status,
                "permission_provenance": dict(member.permission_provenance),
            }

    cross_split_groups = [
        group
        for group in groups
        if len({assignment[key]["atomic_split"] for key in group["members"]}) != 1
    ]
    if cross_split_groups:
        raise AssertionError("dedup groups crossed atomic split assignments")
    return {
        "schema": "tv-royale-cross-source-dedup-v1",
        "normalization_contract": {
            "decoded_mode": "RGB",
            "normalized_size": list(NORMALIZED_SIZE),
            "resize": "Pillow LANCZOS",
            "exact_hash": "SHA256(header || normalized RGB bytes)",
            "perceptual_hash": "64-bit DCT pHash",
            "target_fractions": list(TARGET_FRACTIONS),
            "phash_distance_threshold": PHASH_DISTANCE_THRESHOLD,
            "minimum_close_points": 2,
            "maximum_duration_delta_seconds": MAX_DURATION_DELTA_SECONDS,
            "visual_confirmation_required": True,
        },
        "provenance": {
            "youtube": youtube_provenance,
            "huggingface": hf_provenance,
            "review": review_provenance,
            "permission_provenance_preserved_not_relicensed": True,
        },
        "counts": {
            "youtube_artifacts": len(youtube),
            "hf_complete_three_point_artifacts": len(huggingface),
            "candidate_pairs": len(candidates),
            "confirmed_duplicate_pairs": len(confirmed_pairs),
            "unresolved_candidate_pairs": len(unresolved_pairs),
            "atomic_groups": len(groups),
        },
        "candidate_pairs": candidates,
        "groups": groups,
        "assignments": dict(sorted(assignment.items())),
        "invariants": {
            "dedup_group_cross_split_count": len(cross_split_groups),
            "unresolved_candidates_quarantined": all(
                group["atomic_split"] == "quarantine_dedup_review"
                for group in groups
                if group["status"] == "candidate_quarantine"
            ),
            "permission_inferred_as_creative_commons": False,
            "youtube_training_eligible_only_with_complete_hf_index": all(
                assignment[artifact.key]["atomic_split"]
                == "quarantine_incomplete_hf_index"
                for artifact in youtube
            )
            if incomplete_hf_index
            else True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--youtube-canary-manifest", type=Path)
    parser.add_argument("--hf-run-manifest", type=Path, action="append", required=True)
    parser.add_argument("--hf-split-manifest", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--hf-fingerprint-shard", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hf-inventory-only", action="store_true")
    args = parser.parse_args()
    if args.hf_inventory_only:
        inventory = inventory_hf_evidence(
            args.hf_run_manifest, split_manifest=args.hf_split_manifest
        )
        report = {
            "schema": "tv-royale-hf-dedup-evidence-inventory-v1",
            "status": (
                "complete"
                if inventory["complete_three_point_signatures"]
                == inventory["completed_records"]
                else "blocked_incomplete_hf_fingerprint_index"
            ),
            "hf": inventory,
        }
    else:
        if args.youtube_canary_manifest is None:
            parser.error("--youtube-canary-manifest is required outside inventory mode")
        report = build_dedup_report(
            youtube_manifest=args.youtube_canary_manifest,
            hf_run_manifests=args.hf_run_manifest,
            hf_split_manifest=args.hf_split_manifest,
            review_manifest=args.review_manifest,
            hf_fingerprint_shards=args.hf_fingerprint_shard,
        )
    atomic_write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
