from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import gzip
import json
import subprocess
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import IO, Any

import numpy as np

from clasher.rl.tv_royale_replay import TVRoyalePlacementConverter
from scripts.build_tv_royale_hud_cluster_gallery import _card_art_region
from scripts.extract_tv_royale_youtube_fullmatch import (
    HUD_ROIS,
    StableIdentityResolver,
    _atomic_json,
    _crop_relative,
    _event_rows,
    _sha256,
    _vector,
)
from scripts.join_tv_royale_hud_clusters_to_actions import (
    _mode,
    select_cycle_transition,
)

SCHEMA = "clasher.youtube.hud_cycle_events.v3"
PREPLAY_IDENTITY_OFFSETS_MS = (-1_100, -800, -500)
MAXIMUM_PUBLIC_COST_ERROR = 1.5


@dataclass(frozen=True)
class CycleCandidate:
    player_id: int
    frame_index: int
    selected_slot: int
    selected_cluster: int
    confidence: float
    transition_evidence: str


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _classify_slots(
    frame: np.ndarray,
    *,
    player_id: int,
    centroids: np.ndarray,
    clusters_per_player: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    boxes = [*HUD_ROIS[player_id]["hand"], HUD_ROIS[player_id]["next"]]
    vectors = np.stack(
        [_vector(_card_art_region(_crop_relative(frame, box)), (32, 32)) for box in boxes]
    )
    first = player_id * clusters_per_player
    player_centroids = centroids[first : first + clusters_per_player]
    scores = vectors @ player_centroids.T
    local = np.argmax(scores, axis=1)
    return (
        (local + first).astype(np.int16),
        scores[np.arange(5), local],
        vectors,
    )


def decode_slot_states(
    *,
    video: Path,
    sample_hz: int,
    centroids: np.ndarray,
    clusters_per_player: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={sample_hz},scale=591:1280:flags=lanczos",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    frame_bytes = 591 * 1280 * 3
    states: list[np.ndarray] = []
    similarities: list[np.ndarray] = []
    vectors: list[np.ndarray] = []
    frame_index = 0
    while True:
        raw = _read_exact(process.stdout, frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            raise ValueError(f"short decoded frame {frame_index}")
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(1280, 591, 3)
        frame_states = []
        frame_scores = []
        frame_vectors = []
        for player_id in (0, 1):
            state, score, vector = _classify_slots(
                frame,
                player_id=player_id,
                centroids=centroids,
                clusters_per_player=clusters_per_player,
            )
            frame_states.append(state)
            frame_scores.append(score)
            frame_vectors.append(vector)
        states.append(np.stack(frame_states))
        similarities.append(np.stack(frame_scores))
        vectors.append(np.stack(frame_vectors).astype(np.float16))
        frame_index += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr[-1000:]}")
    return np.stack(states), np.stack(similarities), np.stack(vectors)


def _window_modes(
    states: np.ndarray,
    similarities: np.ndarray,
    indices: range,
    player_id: int,
) -> tuple[list[int], list[float], list[float]]:
    clusters: list[int] = []
    scores: list[float] = []
    support: list[float] = []
    for slot in range(5):
        observations = [
            (int(states[index, player_id, slot]), float(similarities[index, player_id, slot]))
            for index in indices
        ]
        cluster, score = _mode(observations)
        clusters.append(cluster)
        scores.append(score)
        support.append(
            sum(value == cluster for value, _score in observations) / len(observations)
        )
    return clusters, scores, support


def detect_cycle_candidates(
    states: np.ndarray,
    similarities: np.ndarray,
    *,
    sample_hz: int,
    context_start_frames: int = 5,
    context_end_frames: int = 2,
    minimum_mode_support: float = 0.75,
    minimum_similarity: float = 0.40,
    refractory_ms: int = 1_500,
) -> list[CycleCandidate]:
    if states.shape != similarities.shape or states.ndim != 3 or states.shape[1:] != (2, 5):
        raise ValueError("slot states and similarities must have shape [frames, 2, 5]")
    if context_start_frames < context_end_frames or context_end_frames <= 0:
        raise ValueError("context frames must satisfy start >= end > 0")
    raw: list[CycleCandidate] = []
    for center in range(context_start_frames, len(states) - context_start_frames):
        before_range = range(center - context_start_frames, center - context_end_frames + 1)
        after_range = range(center + context_end_frames, center + context_start_frames + 1)
        for player_id in (0, 1):
            before, before_scores, before_support = _window_modes(
                states, similarities, before_range, player_id
            )
            after, after_scores, after_support = _window_modes(
                states, similarities, after_range, player_id
            )
            transition = select_cycle_transition(before, after)
            if transition is None:
                continue
            if min(*before_support, *after_support) < minimum_mode_support:
                continue
            if min(*before_scores, *after_scores) < minimum_similarity:
                continue
            slot = transition[0]
            confidence = min(
                before_support[slot],
                after_support[slot],
                before_support[4],
                before_scores[slot],
                after_scores[slot],
                before_scores[4],
            )
            raw.append(
                CycleCandidate(
                    player_id=player_id,
                    frame_index=center,
                    selected_slot=slot,
                    selected_cluster=before[slot],
                    confidence=float(confidence),
                    transition_evidence=transition[1],
                )
            )
    merged_by_player: dict[int, list[CycleCandidate]] = {0: [], 1: []}
    refractory_frames = round(refractory_ms * sample_hz / 1000)
    for candidate in raw:
        merged = merged_by_player[candidate.player_id]
        if (
            merged
            and candidate.selected_cluster == merged[-1].selected_cluster
            and candidate.frame_index - merged[-1].frame_index <= refractory_frames
        ):
            if candidate.confidence > merged[-1].confidence:
                merged[-1] = candidate
            continue
        merged.append(candidate)
    return sorted(
        [candidate for rows in merged_by_player.values() for candidate in rows],
        key=lambda candidate: (candidate.frame_index, candidate.player_id),
    )


def detect_visual_cycle_candidates(
    states: np.ndarray,
    vectors: np.ndarray,
    *,
    sample_hz: int,
    context_start_frames: int = 5,
    context_end_frames: int = 2,
    minimum_next_similarity: float = 0.09,
    minimum_next_margin: float = 0.04,
    maximum_played_slot_self_similarity: float = 0.50,
    refractory_ms: int = 1_000,
) -> list[CycleCandidate]:
    if states.ndim != 3 or states.shape[1:] != (2, 5):
        raise ValueError("slot states must have shape [frames, 2, 5]")
    if vectors.shape[:3] != states.shape:
        raise ValueError("slot vectors must begin with shape [frames, 2, 5]")
    if context_start_frames < context_end_frames or context_end_frames <= 0:
        raise ValueError("context frames must satisfy start >= end > 0")
    raw: list[CycleCandidate] = []
    for center in range(context_start_frames, len(states) - context_start_frames):
        before_indices = range(
            center - context_start_frames, center - context_end_frames + 1
        )
        after_indices = range(
            center + context_end_frames, center + context_start_frames + 1
        )
        for player_id in (0, 1):
            before_vectors = np.asarray(
                vectors[list(before_indices), player_id], dtype=np.float32
            ).mean(axis=0)
            after_vectors = np.asarray(
                vectors[list(after_indices), player_id], dtype=np.float32
            ).mean(axis=0)
            before_vectors /= np.maximum(
                np.linalg.norm(before_vectors, axis=1, keepdims=True), 1e-12
            )
            after_vectors /= np.maximum(
                np.linalg.norm(after_vectors, axis=1, keepdims=True), 1e-12
            )
            next_similarities = after_vectors[:4] @ before_vectors[4]
            selected_slot = int(np.argmax(next_similarities))
            ordered = np.sort(next_similarities)
            next_similarity = float(next_similarities[selected_slot])
            next_margin = float(ordered[-1] - ordered[-2])
            self_similarity = float(
                after_vectors[selected_slot] @ before_vectors[selected_slot]
            )
            if (
                next_similarity < minimum_next_similarity
                or next_margin < minimum_next_margin
                or self_similarity > maximum_played_slot_self_similarity
            ):
                continue
            before_clusters = [
                _mode(
                    [
                        (int(states[index, player_id, slot]), 1.0)
                        for index in before_indices
                    ]
                )[0]
                for slot in range(5)
            ]
            confidence = min(
                next_similarity,
                next_margin * 2.0,
                max(0.0, 1.0 - self_similarity),
            )
            raw.append(
                CycleCandidate(
                    player_id=player_id,
                    frame_index=center,
                    selected_slot=selected_slot,
                    selected_cluster=before_clusters[selected_slot],
                    confidence=confidence,
                    transition_evidence="direct_next_art_to_hand_slot",
                )
            )
    merged_by_player: dict[int, list[CycleCandidate]] = {0: [], 1: []}
    refractory_frames = round(refractory_ms * sample_hz / 1000)
    for candidate in raw:
        merged = merged_by_player[candidate.player_id]
        if merged and candidate.frame_index - merged[-1].frame_index <= refractory_frames:
            if candidate.confidence > merged[-1].confidence:
                merged[-1] = candidate
            continue
        merged.append(candidate)
    return sorted(
        [candidate for rows in merged_by_player.values() for candidate in rows],
        key=lambda candidate: (candidate.frame_index, candidate.player_id),
    )


def _associate_placement(
    candidate: CycleCandidate,
    placements: list[dict[str, Any]],
    *,
    sample_hz: int,
    maximum_delta_ms: int = 1_000,
) -> tuple[dict[str, Any] | None, str | None]:
    timestamp_ms = round(candidate.frame_index * 1000 / sample_hz)
    nearby = [
        row
        for row in placements
        if int(row["player_id"]) == candidate.player_id
        and abs(int(row["timestamp_ms"]) - timestamp_ms) <= maximum_delta_ms
        and bool(row["placement_valid"])
    ]
    if not nearby:
        return None, "no_unique_in_grid_marker_within_window"
    nearest_delta = min(abs(int(row["timestamp_ms"]) - timestamp_ms) for row in nearby)
    nearest = [
        row
        for row in nearby
        if abs(int(row["timestamp_ms"]) - timestamp_ms) == nearest_delta
    ]
    if len(nearest) != 1:
        return None, "ambiguous_equidistant_in_grid_markers"
    return nearest[0], None


def _play_confirmed(
    candidate: CycleCandidate,
    placement: dict[str, Any] | None,
    *,
    elixir_drop_valid: bool = True,
) -> bool:
    if not elixir_drop_valid:
        return False
    return candidate.transition_evidence in {
        "unique_next_enters_changed_slot",
        "direct_next_art_to_hand_slot",
    } or (
        candidate.transition_evidence == "unique_changed_slot_without_next_confirmation"
        and placement is not None
    )


def _observed_elixir_drop(
    records: list[dict[str, Any]],
    *,
    player_id: int,
    timestamp_ms: int,
) -> float:
    values = [
        (
            int(record["timestamp_ms"]),
            float(record["offline_privileged_hud"][str(player_id)]["elixir"]["value"]),
        )
        for record in records
        if abs(int(record["timestamp_ms"]) - timestamp_ms) <= 1_600
        and record["offline_privileged_hud"][str(player_id)]["elixir"]["valid"]
    ]
    drops = [
        (abs(new_time - timestamp_ms), old_value - new_value)
        for (_old_time, old_value), (new_time, new_value) in pairwise(values)
        if old_value - new_value >= 0.5 and abs(new_time - timestamp_ms) <= 1_000
    ]
    return min(drops, key=lambda item: (item[0], -item[1]))[1] if drops else 0.0


def _unanimous_preplay_identity(
    records: list[dict[str, Any]],
    candidate: CycleCandidate,
    *,
    sample_hz: int,
) -> tuple[str | None, list[dict[str, Any]]]:
    timestamp_ms = round(candidate.frame_index * 1_000 / sample_hz)
    evidence: list[dict[str, Any]] = []
    values: list[str] = []
    for offset_ms in PREPLAY_IDENTITY_OFFSETS_MS:
        frame_index = round((timestamp_ms + offset_ms) * sample_hz / 1_000)
        if not 0 <= frame_index < len(records):
            return None, evidence
        head = records[frame_index]["offline_privileged_hud"][
            str(candidate.player_id)
        ]["hand"][candidate.selected_slot]
        value = head.get("candidate")
        evidence.append(
            {
                "offset_ms": offset_ms,
                "frame_index": frame_index,
                "candidate": value,
                "single_frame_valid": bool(head.get("valid")),
                "score": float(head.get("score", 0.0)),
                "margin": float(head.get("margin", 0.0)),
            }
        )
        if not isinstance(value, str) or not value or value == "empty":
            return None, evidence
        values.append(value)
    return (values[0] if len(set(values)) == 1 else None), evidence


def _load_reviewed_decks(
    path: Path, *, video_sha256: str
) -> dict[int, frozenset[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "clasher.youtube.reviewed_public_decks.v1":
        raise ValueError("unsupported reviewed deck manifest")
    if payload.get("video_sha256") != video_sha256:
        raise ValueError("reviewed deck manifest does not bind the source video")
    output: dict[int, frozenset[str]] = {}
    for player_id in (0, 1):
        identities = payload["players"][str(player_id)]["card_identities"]
        if len(identities) != 8 or len(set(identities)) != 8:
            raise ValueError("each reviewed deck must contain eight unique identities")
        output[player_id] = frozenset(str(value) for value in identities)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--neutral", type=Path, required=True)
    parser.add_argument("--cluster-manifest", type=Path, required=True)
    parser.add_argument("--cluster-arrays", type=Path, required=True)
    parser.add_argument("--reviewed-deck-manifest", type=Path)
    parser.add_argument(
        "--vocabulary-manifest",
        type=Path,
        default=Path("reports/current_client_youtube_stable_vocabulary_v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-start-frames", type=int, default=5)
    parser.add_argument("--context-end-frames", type=int, default=2)
    args = parser.parse_args()

    source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    sample_hz = int(str(source["decode"]["output_time_base"]).split("/", 1)[1])
    cluster_manifest = json.loads(args.cluster_manifest.read_text(encoding="utf-8"))
    if cluster_manifest.get("schema") != "clasher.youtube.hud_cluster_gallery.v1":
        raise ValueError("unsupported cluster manifest")
    clusters_per_player = int(cluster_manifest["clusters_per_player"])
    arrays = np.load(args.cluster_arrays)
    centroids = np.asarray(arrays["centroids"], dtype=np.float32)
    centroids /= np.maximum(np.linalg.norm(centroids, axis=1, keepdims=True), 1e-12)
    video_sha256 = _sha256(args.video)
    reviewed_decks = (
        None
        if args.reviewed_deck_manifest is None
        else _load_reviewed_decks(
            args.reviewed_deck_manifest, video_sha256=video_sha256
        )
    )
    identity_resolver = StableIdentityResolver(
        args.vocabulary_manifest,
        TVRoyalePlacementConverter(source_frame_hz=sample_hz),
    )
    states, _similarities, vectors = decode_slot_states(
        video=args.video.resolve(),
        sample_hz=sample_hz,
        centroids=centroids,
        clusters_per_player=clusters_per_player,
    )
    candidates = detect_visual_cycle_candidates(
        states,
        vectors,
        sample_hz=sample_hz,
        context_start_frames=args.context_start_frames,
        context_end_frames=args.context_end_frames,
    )
    with gzip.open(args.neutral, "rt", encoding="utf-8") as stream:
        neutral = [json.loads(line) for line in stream if line.strip()]
    if len(neutral) != len(states):
        raise ValueError("neutral rows do not match decoded slot-state rows")
    placements = _event_rows(neutral, identity_resolver=None)

    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        placement, placement_reason = _associate_placement(
            candidate, placements, sample_hz=sample_hz
        )
        timestamp_ms = round(candidate.frame_index * 1000 / sample_hz)
        observed_elixir_drop = _observed_elixir_drop(
            neutral,
            player_id=candidate.player_id,
            timestamp_ms=timestamp_ms,
        )
        unanimous_identity, identity_evidence = _unanimous_preplay_identity(
            neutral,
            candidate,
            sample_hz=sample_hz,
        )
        play_confirmed = _play_confirmed(
            candidate,
            placement,
            elixir_drop_valid=observed_elixir_drop >= 0.5,
        )
        identity_in_deck = bool(
            unanimous_identity is not None
            and (
                reviewed_decks is None
                or unanimous_identity in reviewed_decks[candidate.player_id]
            )
        )
        expected_public_cost = (
            None
            if unanimous_identity is None
            else identity_resolver.card_mana_cost(unanimous_identity)
        )
        public_cost_error = (
            None
            if expected_public_cost is None
            else abs(observed_elixir_drop - expected_public_cost)
        )
        public_cost_valid = bool(
            public_cost_error is not None
            and public_cost_error <= MAXIMUM_PUBLIC_COST_ERROR
        )
        identity = (
            unanimous_identity
            if play_confirmed and identity_in_deck and public_cost_valid
            else None
        )
        rows.append(
            {
                "event_id": f"cycle-{index:05d}",
                "timestamp_ms": timestamp_ms,
                "player_id": candidate.player_id,
                "selected_slot": candidate.selected_slot,
                "selected_cluster": candidate.selected_cluster,
                "cycle_confidence": candidate.confidence,
                "cycle_transition_evidence": candidate.transition_evidence,
                "play_confirmed": play_confirmed,
                "observed_public_elixir_drop": observed_elixir_drop,
                "elixir_drop_valid": observed_elixir_drop >= 0.5,
                "card_identity": identity,
                "identity_valid": identity is not None,
                "identity_evidence": identity_evidence,
                "expected_public_cost": expected_public_cost,
                "public_cost_error": public_cost_error,
                "public_cost_valid": public_cost_valid,
                "identity_reason": (
                    None
                    if identity is not None
                    else (
                        "cycle_or_elixir_confirmation_failed"
                        if unanimous_identity is not None
                        and identity_in_deck
                        and public_cost_valid
                        else "outside_reviewed_public_deck"
                        if unanimous_identity is not None and not identity_in_deck
                        else "public_elixir_cost_mismatch"
                        if unanimous_identity is not None and not public_cost_valid
                        else "preplay_candidates_not_unanimous"
                    )
                ),
                "deployment_tile_absolute": (
                    None if placement is None else placement["deployment_tile_absolute"]
                ),
                "deployment_tile_actor_canonical": (
                    None
                    if placement is None
                    else placement["deployment_tile_actor_canonical"]
                ),
                "deployment_world_position": (
                    None if placement is None else placement["deployment_world_position"]
                ),
                "placement_valid": placement is not None,
                "placement_reason": placement_reason,
                "offline_label_only": True,
                "evidence": "public_four_hand_plus_next_unique_cycle_transition",
            }
        )

    counts = {
        "cycle_candidates": len(rows),
        "play_confirmed": sum(int(row["play_confirmed"]) for row in rows),
        "identity_valid": sum(int(row["identity_valid"]) for row in rows),
        "placement_valid": sum(int(row["placement_valid"]) for row in rows),
        "complete_identity_and_placement": sum(
            int(row["identity_valid"] and row["placement_valid"]) for row in rows
        ),
    }
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "video_sha256": video_sha256,
        "source_manifest_sha256": _sha256(args.source_manifest),
        "neutral_sha256": _sha256(args.neutral),
        "cluster_manifest_sha256": _sha256(args.cluster_manifest),
        "cluster_arrays_sha256": _sha256(args.cluster_arrays),
        "vocabulary_manifest_sha256": _sha256(args.vocabulary_manifest),
        "reviewed_deck_manifest_sha256": (
            None
            if args.reviewed_deck_manifest is None
            else _sha256(args.reviewed_deck_manifest)
        ),
        "sample_hz": sample_hz,
        "contract": {
            "card_play_source": "public_four_hand_plus_next_cycle",
            "visual_transition": "direct_next_art_to_hand_slot",
            "minimum_public_elixir_drop": 0.5,
            "maximum_public_cost_error": MAXIMUM_PUBLIC_COST_ERROR,
            "deployment_source": "independent_in_grid_marker_only",
            "marker_can_create_card_play": False,
            "unique_changed_slot_without_next_requires_marker": True,
            "identity_scope": "offline_temporal_consensus_from_current_frame_head",
            "identity_source": "three_unanimous_preplay_current_frame_candidates",
            "identity_offsets_ms": list(PREPLAY_IDENTITY_OFFSETS_MS),
            "deck_closure": (
                "unconstrained_diagnostic"
                if reviewed_decks is None
                else "exactly_eight_reviewed_public_identities_per_player"
            ),
            "inference_eligible": False,
        },
        "counts": counts,
        "events": rows,
    }
    _atomic_json(args.output, payload)
    print(json.dumps({"output": str(args.output), **counts}, indent=2))


if __name__ == "__main__":
    main()
