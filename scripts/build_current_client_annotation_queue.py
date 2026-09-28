from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SCHEMA = "clasher.current_client.annotation_queue.v1"
DECISION_SCHEMA = "clasher.current_client.annotation_decisions.v1"
SPLIT_SCHEMA = "clasher.detector.video_group_split.v1"
ARENA_WIDTH = 576
ARENA_HEIGHT = 896
ARENA_REGION = (0.024, 0.196, 0.954, 0.659)
NON_ORDINARY_MARKERS = ("event", "global", "party", "super")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _video_split(video_id: str, *, forced_test: set[str]) -> str:
    if video_id in forced_test:
        return "test"
    bucket = (
        int.from_bytes(
            hashlib.sha256(f"{SPLIT_SCHEMA}\0youtube:{video_id}".encode()).digest()[:8],
            "big",
        )
        % 10_000
    )
    if bucket < 8_000:
        return "train"
    if bucket < 9_000:
        return "validation"
    return "test"


def _load_neutral(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def _current_deck_hints(records: list[dict[str, Any]]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for player in (0, 1):
        counts: Counter[str] = Counter()
        for row in records:
            hud = row["offline_privileged_hud"][str(player)]
            for slot in [*hud["hand"], hud["next_card"]]:
                value = slot.get("value")
                if (
                    slot.get("valid")
                    and isinstance(value, str)
                    and value.startswith("card_action:")
                ):
                    counts[value] += 1
        # A one-frame template match is not deck evidence. This threshold is
        # intentionally tiny relative to a 3,204-frame video but removes the
        # known one-off false matches in the canary.
        result[player] = sorted(key for key, count in counts.items() if count >= 5)
    return result


def _ordinary(row: dict[str, Any]) -> bool:
    material = " ".join(
        [row.get("stable_key", ""), *row.get("owner_root_cards", ())]
    ).lower()
    return not any(marker in material for marker in NON_ORDINARY_MARKERS)


def _root_similarity(label: str, root: str) -> float:
    left, right = _normalize(label), _normalize(root)
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return min(len(left), len(right)) / max(len(left), len(right))
    # Deterministic character-bigram Jaccard handles singular/plural visual
    # labels without inventing an identity.
    a = {left[index : index + 2] for index in range(max(1, len(left) - 1))}
    b = {right[index : index + 2] for index in range(max(1, len(right) - 1))}
    return len(a & b) / max(1, len(a | b))


@dataclass
class ProposalTrack:
    track_id: int
    video_id: str
    team_id: int
    visual_class: str
    last_timestamp_ms: int
    last_world_position: tuple[float, float]
    observations: list[dict[str, Any]] = field(default_factory=list)


def _tracks(records: list[dict[str, Any]], video_id: str) -> list[ProposalTrack]:
    tracks: list[ProposalTrack] = []
    active: list[ProposalTrack] = []
    next_id = 0
    for row in records:
        timestamp = int(row["timestamp_ms"])
        active = [
            track for track in active if timestamp - track.last_timestamp_ms <= 500
        ]
        detections = [
            entity
            for entity in row["public"]["entities"]
            if entity.get("world_position") is not None
            and entity.get("team_id") in {0, 1}
            and not entity["visual_class"].endswith("tower")
        ]
        detections.sort(
            key=lambda entity: (
                entity["visual_class"],
                entity["team_id"],
                entity["world_position"][0],
                entity["world_position"][1],
            )
        )
        claimed: set[int] = set()
        for entity in detections:
            position = (
                float(entity["world_position"][0]),
                float(entity["world_position"][1]),
            )
            candidates = [
                track
                for track in active
                if track.track_id not in claimed
                and track.team_id == entity["team_id"]
                and track.visual_class == entity["visual_class"]
                and math.dist(track.last_world_position, position) <= 2.25
            ]
            if candidates:
                track = min(
                    candidates,
                    key=lambda value: (
                        math.dist(value.last_world_position, position),
                        value.track_id,
                    ),
                )
            else:
                track = ProposalTrack(
                    track_id=next_id,
                    video_id=video_id,
                    team_id=entity["team_id"],
                    visual_class=entity["visual_class"],
                    last_timestamp_ms=timestamp,
                    last_world_position=position,
                )
                next_id += 1
                tracks.append(track)
                active.append(track)
            observation = {
                "sample_index": row["sample_index"],
                "timestamp_ms": timestamp,
                "confidence": entity["confidence"],
                "sprite_box_normalized": entity["sprite_box_normalized"],
                "world_position": list(position),
            }
            track.observations.append(observation)
            track.last_timestamp_ms = timestamp
            track.last_world_position = position
            claimed.add(track.track_id)
    return tracks


def _candidate_rows(
    upgrade: dict[str, Any], deck_hints: dict[int, list[str]]
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[int, list[dict[str, Any]]],
]:
    exact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in upgrade["token_to_katacr"]:
        for label in row.get("exact_visual_labels", ()):
            exact[label].append(row)
        for label in row.get("family_only_labels", ()):
            family[label].append(row)
        if row.get("katacr_relationship") != "missing_visual_class" or not _ordinary(
            row
        ):
            continue
        owner_keys = {f"card_action:{owner}" for owner in row["owner_root_cards"]}
        for team, cards in deck_hints.items():
            if owner_keys & set(cards):
                missing_by_team[team].append(row)
    return exact, family, missing_by_team


def _queue_rows(
    tracks: list[ProposalTrack],
    upgrade: dict[str, Any],
    deck_hints: dict[int, list[str]],
    *,
    limit: int,
    split: str,
) -> list[dict[str, Any]]:
    exact, family, missing_by_team = _candidate_rows(upgrade, deck_hints)
    rows: list[dict[str, Any]] = []
    for track in tracks:
        if len(track.observations) < 3:
            continue
        representative = max(
            track.observations,
            key=lambda row: (row["confidence"], -row["sample_index"]),
        )
        exact_candidates = exact.get(track.visual_class, [])
        family_candidates = family.get(track.visual_class, [])
        missing_candidates = []
        for candidate in missing_by_team.get(track.team_id, []):
            if (
                "evolution" in candidate.get("variant_kinds", ())
                and "evolution" not in track.visual_class
            ):
                # A base deck card is not evidence that this particular body is
                # evolved. Evolution candidates require an evolution-specific
                # visual proposal (or a future explicit evolution cue).
                continue
            score = max(
                (
                    _root_similarity(track.visual_class, owner)
                    for owner in candidate["owner_root_cards"]
                ),
                default=0.0,
            )
            if score >= 0.45:
                missing_candidates.append((score, candidate))
        missing_candidates.sort(key=lambda item: (-item[0], item[1]["stable_key"]))
        candidate_choices: list[dict[str, Any]] = []
        for score, candidate in missing_candidates:
            candidate_choices.append(
                {
                    "stable_key": candidate["stable_key"],
                    "relationship": "missing_visual_class_deck_hint",
                    "hint_score": round(score, 6),
                    "may_accept_after_visual_review": True,
                }
            )
        for candidate in family_candidates:
            candidate_choices.append(
                {
                    "stable_key": candidate["stable_key"],
                    "relationship": "root_family_only",
                    "hint_score": None,
                    "may_accept_after_visual_review": False,
                }
            )
        for candidate in exact_candidates:
            owner_keys = {
                f"card_action:{owner}" for owner in candidate["owner_root_cards"]
            }
            candidate_choices.append(
                {
                    "stable_key": candidate["stable_key"],
                    "relationship": "existing_exact_retention",
                    "hint_score": 1.0,
                    "deck_hint_support": bool(
                        owner_keys & set(deck_hints[track.team_id])
                    ),
                    "may_accept_after_visual_review": True,
                }
            )
        if missing_candidates:
            priority_band = 0
        elif family_candidates:
            priority_band = 1
        elif exact_candidates:
            priority_band = 2
        else:
            priority_band = 3
        queue_id = hashlib.sha256(
            f"{SCHEMA}\0{track.video_id}\0{track.track_id}\0{representative['sample_index']}".encode()
        ).hexdigest()[:20]
        rows.append(
            {
                "queue_id": queue_id,
                "video_id": track.video_id,
                "source_group_id": f"youtube:{track.video_id}",
                "split": split,
                "track_id": track.track_id,
                "team_id": track.team_id,
                "detector_proposal": {
                    "visual_class": track.visual_class,
                    "observations": len(track.observations),
                    "first_timestamp_ms": track.observations[0]["timestamp_ms"],
                    "last_timestamp_ms": track.observations[-1]["timestamp_ms"],
                    "representative": representative,
                    "is_label": False,
                },
                "deck_hints": deck_hints[track.team_id],
                "candidate_choices": candidate_choices,
                "priority_band": priority_band,
                "review": {
                    "status": "pending",
                    "accepted_stable_key": None,
                    "reviewer": None,
                    "reason": None,
                },
            }
        )
    rows.sort(
        key=lambda row: (
            row["priority_band"],
            -row["detector_proposal"]["observations"],
            -row["detector_proposal"]["representative"]["confidence"],
            row["queue_id"],
        )
    )
    # Keep the visual audit useful rather than filling it with twelve long
    # tracks from one swarm class. Missing classes retain half the queue, then
    # family-only review and exact-class retention each receive a quarter.
    quotas = {0: max(1, limit // 2), 1: max(1, limit // 4), 2: max(1, limit // 4)}
    selected: list[dict[str, Any]] = []
    per_identity: Counter[tuple[int, str]] = Counter()
    for band in (0, 1, 2, 3):
        quota = quotas.get(band, max(0, limit - len(selected)))
        for row in rows:
            if row["priority_band"] != band:
                continue
            primary = (
                row["candidate_choices"][0]["stable_key"]
                if row["candidate_choices"]
                else row["detector_proposal"]["visual_class"]
            )
            key = (band, primary)
            if per_identity[key] >= 2:
                continue
            selected.append(row)
            per_identity[key] += 1
            if sum(item["priority_band"] == band for item in selected) >= quota:
                break
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_ids = {row["queue_id"] for row in selected}
        selected.extend(row for row in rows if row["queue_id"] not in selected_ids)
    return selected[:limit]


def _arena_frame(capture: cv2.VideoCapture, timestamp_ms: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp_ms))
    ok, frame = capture.read()
    if not ok:
        raise ValueError(f"could not decode at {timestamp_ms}ms")
    frame = cv2.resize(frame, (frame.shape[1] // 2, frame.shape[0] // 2))
    height, width = frame.shape[:2]
    x, y, w, h = ARENA_REGION
    crop = frame[
        round(y * height) : round((y + h) * height),
        round(x * width) : round((x + w) * width),
    ]
    return cv2.resize(crop, (ARENA_WIDTH, ARENA_HEIGHT))


def _render_queue_sheet(
    rows: list[dict[str, Any]], video: Path, output: Path
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"could not open {video}")
    panels: list[np.ndarray] = []
    for index, row in enumerate(rows[:12]):
        proposal = row["detector_proposal"]["representative"]
        frame = _arena_frame(capture, proposal["timestamp_ms"])
        x1, y1, x2, y2 = proposal["sprite_box_normalized"]
        box = (
            round(x1 * ARENA_WIDTH),
            round(y1 * ARENA_HEIGHT),
            round(x2 * ARENA_WIDTH),
            round(y2 * ARENA_HEIGHT),
        )
        cv2.rectangle(frame, box[:2], box[2:], (0, 255, 255), 4)
        choices = row["candidate_choices"]
        first = choices[0]["stable_key"] if choices else "NO STABLE CANDIDATE"
        header = np.zeros((100, ARENA_WIDTH, 3), dtype=np.uint8)
        lines = [
            f"Q{index:02d} {row['queue_id']} team={row['team_id']} split={row['split']}",
            f"proposal={row['detector_proposal']['visual_class']} track_n={row['detector_proposal']['observations']}",
            f"hint={first} status={row['review']['status']}",
        ]
        for line_index, line in enumerate(lines):
            cv2.putText(
                header,
                line,
                (8, 25 + line_index * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        panel = np.vstack((header, frame))
        panels.append(cv2.resize(panel, (288, 498)))
    capture.release()
    while len(panels) < 12:
        panels.append(np.zeros((498, 288, 3), dtype=np.uint8))
    sheet = np.vstack(
        [np.hstack(panels[offset : offset + 4]) for offset in range(0, 12, 4)]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise ValueError(f"could not write {output}")
    return {"path": str(output.resolve()), "sha256": _sha256(output)}


def _apply_decisions(
    rows: list[dict[str, Any]], decisions_path: Path | None
) -> dict[str, int]:
    if decisions_path is None:
        return {"pending": len(rows), "accepted": 0, "rejected": 0}
    payload = json.loads(decisions_path.read_text(encoding="utf-8"))
    if payload.get("schema") != DECISION_SCHEMA:
        raise ValueError("decision schema mismatch")
    decisions = {row["queue_id"]: row for row in payload["decisions"]}
    if len(decisions) != len(payload["decisions"]):
        raise ValueError("duplicate queue decision")
    counts: Counter[str] = Counter()
    for row in rows:
        decision = decisions.get(row["queue_id"])
        if decision is None:
            counts["pending"] += 1
            continue
        status = decision.get("status")
        if status not in {"accepted", "rejected", "pending"}:
            raise ValueError(f"invalid review status {status!r}")
        accepted = decision.get("accepted_stable_key")
        candidates = {item["stable_key"]: item for item in row["candidate_choices"]}
        if status == "accepted":
            if accepted not in candidates:
                raise ValueError(
                    f"accepted identity is not a candidate for {row['queue_id']}"
                )
            if not candidates[accepted]["may_accept_after_visual_review"]:
                raise ValueError(
                    f"family-only candidate cannot be accepted: {accepted}"
                )
            if not decision.get("reviewer") or not decision.get("reason"):
                raise ValueError("accepted decisions require reviewer and reason")
        elif accepted is not None:
            raise ValueError("non-accepted decision has accepted_stable_key")
        row["review"] = {
            "status": status,
            "accepted_stable_key": accepted,
            "reviewer": decision.get("reviewer"),
            "reason": decision.get("reason"),
        }
        counts[status] += 1
    return {key: counts[key] for key in ("pending", "accepted", "rejected")}


def _export_accepted(
    rows: list[dict[str, Any]], video: Path, output_root: Path
) -> dict[str, Any]:
    accepted = [row for row in rows if row["review"]["status"] == "accepted"]
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    classes = sorted({row["review"]["accepted_stable_key"] for row in accepted})
    class_index = {key: index for index, key in enumerate(classes)}
    capture = cv2.VideoCapture(str(video))
    artifacts: list[dict[str, Any]] = []
    for row in accepted:
        split = row["split"]
        image_dir = output_root / "images" / split
        label_dir = output_root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        proposal = row["detector_proposal"]["representative"]
        frame = _arena_frame(capture, proposal["timestamp_ms"])
        stem = f"{row['video_id']}_{proposal['sample_index']:06d}_{row['track_id']:06d}"
        image_path = image_dir / f"{stem}.jpg"
        label_path = label_dir / f"{stem}.txt"
        if not cv2.imwrite(str(image_path), frame):
            raise ValueError(f"could not write {image_path}")
        x1, y1, x2, y2 = proposal["sprite_box_normalized"]
        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
        width, height = x2 - x1, y2 - y1
        stable_key = row["review"]["accepted_stable_key"]
        label_path.write_text(
            f"{class_index[stable_key]} {center_x:.8f} {center_y:.8f} {width:.8f} {height:.8f}\n",
            encoding="utf-8",
        )
        artifacts.append(
            {
                "queue_id": row["queue_id"],
                "stable_key": stable_key,
                "image": str(image_path.resolve()),
                "image_sha256": _sha256(image_path),
                "label": str(label_path.resolve()),
                "label_sha256": _sha256(label_path),
            }
        )
    capture.release()
    classes_path = output_root / "classes.json"
    classes_path.write_text(json.dumps(classes, indent=2) + "\n", encoding="utf-8")
    return {
        "accepted": len(accepted),
        "classes": classes,
        "classes_sha256": _sha256(classes_path),
        "artifacts": artifacts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--upgrade-manifest",
        default="reports/current_client_detector_upgrade_manifest_v1.json",
    )
    parser.add_argument(
        "--neutral-sequence",
        default=(
            "datasets/derived/tv_royale_youtube_fullmatch_semantic_"
            "hTG8dM4KtM4_20260817/neutral_sequence.jsonl.gz"
        ),
    )
    parser.add_argument(
        "--video",
        default=(
            "datasets/external/tv_royale_youtube_fullmatch_20260817/"
            "hTG8dM4KtM4/source.webm"
        ),
    )
    parser.add_argument("--video-id", default="hTG8dM4KtM4")
    parser.add_argument("--forced-test-video", action="append", default=["hTG8dM4KtM4"])
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--decisions")
    parser.add_argument(
        "--output",
        default="reports/current_client_annotation_queue_hTG8dM4KtM4_v1.json",
    )
    parser.add_argument(
        "--contact-sheet",
        default="reports/current_client_annotation_queue_hTG8dM4KtM4_v1.jpg",
    )
    parser.add_argument(
        "--yolo-output",
        default="datasets/derived/current_client_annotation_queue_hTG8dM4KtM4_v1",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    upgrade_path = Path(args.upgrade_manifest).resolve()
    neutral_path = Path(args.neutral_sequence).resolve()
    video_path = Path(args.video).resolve()
    output_path = Path(args.output).resolve()
    sheet_path = Path(args.contact_sheet).resolve()
    decisions_path = Path(args.decisions).resolve() if args.decisions else None
    yolo_root = Path(args.yolo_output).resolve()
    upgrade = json.loads(upgrade_path.read_text(encoding="utf-8"))
    records = _load_neutral(neutral_path)
    deck_hints = _current_deck_hints(records)
    split = _video_split(args.video_id, forced_test=set(args.forced_test_video))
    tracks = _tracks(records, args.video_id)
    rows = _queue_rows(tracks, upgrade, deck_hints, limit=args.limit, split=split)
    decisions = _apply_decisions(rows, decisions_path)
    sheet = _render_queue_sheet(rows, video_path, sheet_path)
    export = _export_accepted(rows, video_path, yolo_root)
    payload = {
        "schema": SCHEMA,
        "source": {
            "video_id": args.video_id,
            "video_sha256": _sha256(video_path),
            "neutral_sequence_sha256": _sha256(neutral_path),
            "source_group_id": f"youtube:{args.video_id}",
            "split": split,
        },
        "upgrade_manifest": {
            "path": str(upgrade_path),
            "sha256": _sha256(upgrade_path),
            "wholly_missing_tokens": upgrade["counts"]["relationship_counts"][
                "missing_visual_class"
            ],
        },
        "contracts": {
            "detector_boxes_are_proposals_not_labels": True,
            "deck_hud_evidence_is_hint_only": True,
            "family_only_candidates_may_be_accepted": False,
            "accepted_review_required_for_yolo_export": True,
            "split_unit": "entire source video including every frame and actor view",
            "split_schema": SPLIT_SCHEMA,
        },
        "deck_hints": {str(key): value for key, value in deck_hints.items()},
        "counts": {
            "proposal_tracks": len(tracks),
            "queued": len(rows),
            "priority_bands": dict(Counter(str(row["priority_band"]) for row in rows)),
            "review": decisions,
        },
        "queue": rows,
        "contact_sheet": sheet,
        "yolo_export": export,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "sha256": _sha256(output_path),
                "counts": payload["counts"],
                "yolo": export,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
