from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SCHEMA = "clasher.current_client.detector_upgrade_manifest.v1"
SPLIT_SCHEMA = "clasher.detector.video_group_split.v1"
CONTACT_SHEET_WIDTH = 576
CONTACT_SHEET_HEIGHT = 896
ARENA_REGION = (0.024, 0.196, 0.954, 0.659)
DETECTOR_NAMESPACES = {
    "area_effect",
    "building_body",
    "projectile",
    "tower",
    "troop_body",
}
UI_LABELS = {
    "bar",
    "bar-level",
    "clock",
    "dagger-duchess-tower-bar",
    "elixir",
    "emote",
    "evolution-symbol",
    "ice-spirit-evolution-symbol",
    "king-tower-bar",
    "selected",
    "skeleton-king-bar",
    "text",
    "tower-bar",
}
VISUAL_ALIASES = {
    "cannoneer-tower": ("tower:Tower",),
    "dagger-duchess-tower": ("tower:Tower",),
    "queen-tower": ("tower:Tower",),
    "golem-big": ("troop_body:Golem",),
    "golem-mid": ("troop_body:Golemite",),
    "golem-small": ("troop_body:Golemite",),
    "hog": ("troop_body:RoyalHog",),
    "phoenix-big": ("troop_body:Phoenix",),
    "phoenix-egg": ("troop_body:PhoenixEgg",),
    "phoenix-small": ("troop_body:PhoenixNoRespawn",),
    "skeleton-evolution": ("troop_body:Skeleton_EV1",),
    "the-log": ("projectile:LogProjectileRolling",),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _load_unit_labels(path: Path) -> list[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "unit_list"
            for target in node.targets
        ):
            values = ast.literal_eval(node.value)
            if isinstance(values, list) and all(
                isinstance(value, str) for value in values
            ):
                return values
    raise ValueError(f"unit_list not found in {path}")


def _split(group_id: str) -> str:
    bucket = (
        int.from_bytes(
            hashlib.sha256(f"{SPLIT_SCHEMA}\0{group_id}".encode()).digest()[:8], "big"
        )
        % 10_000
    )
    if bucket < 8_000:
        return "train"
    if bucket < 9_000:
        return "validation"
    return "test"


def _sequence_group(path: Path) -> str:
    stem = re.sub(r"_\d+$", "", path.stem)
    return f"katacr-segment:{path.parent.name}:{stem}"


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _card_template_label(path: Path) -> str:
    return re.sub(r"-\d+$", "", path.stem)


def _build_token_map(
    vocabulary: dict[str, Any], labels: list[str]
) -> list[dict[str, Any]]:
    entries = [
        row for row in vocabulary["entries"] if row.get("actor_token_id") is not None
    ]
    by_key = {row["stable_key"]: row for row in entries}
    direct_by_normalized: dict[str, list[str]] = defaultdict(list)
    for row in entries:
        direct_by_normalized[_normalize(row["canonical_name"])].append(
            row["stable_key"]
        )

    card_aliases: dict[str, set[str]] = defaultdict(set)
    for row in vocabulary["aliases"]:
        if row["context"] == "card_action":
            card_aliases[row["normalized_label"]].add(row["target_stable_key"])

    exact_labels_by_key: dict[str, set[str]] = defaultdict(set)
    family_labels_by_key: dict[str, set[str]] = defaultdict(set)
    for label in labels:
        for stable_key in direct_by_normalized.get(_normalize(label), ()):
            if by_key[stable_key]["namespace"] in DETECTOR_NAMESPACES:
                exact_labels_by_key[stable_key].add(label)
        for stable_key in VISUAL_ALIASES.get(label, ()):
            if stable_key in by_key:
                exact_labels_by_key[stable_key].add(label)
        aliased_cards = card_aliases.get(_normalize(label), set())
        for row in entries:
            if row["namespace"] not in DETECTOR_NAMESPACES:
                continue
            owner_keys = {f"card_action:{owner}" for owner in row["owner_root_cards"]}
            if owner_keys & aliased_cards:
                family_labels_by_key[row["stable_key"]].add(label)
            if any(
                _normalize(owner) == _normalize(label)
                for owner in row["owner_root_cards"]
            ):
                family_labels_by_key[row["stable_key"]].add(label)

    rows: list[dict[str, Any]] = [
        {
            "actor_token_id": 0,
            "stable_key": "<pad>",
            "namespace": "reserved",
            "katacr_relationship": "reserved_not_visual",
            "exact_visual_labels": [],
            "family_only_labels": [],
            "detector_annotation_eligible": False,
        },
        {
            "actor_token_id": 1,
            "stable_key": "<unknown>",
            "namespace": "reserved",
            "katacr_relationship": "reserved_not_visual",
            "exact_visual_labels": [],
            "family_only_labels": [],
            "detector_annotation_eligible": False,
        },
    ]
    for row in sorted(entries, key=lambda value: value["actor_token_id"]):
        key = row["stable_key"]
        exact = sorted(exact_labels_by_key[key])
        family = sorted(family_labels_by_key[key] - set(exact))
        detector_required = row["namespace"] in DETECTOR_NAMESPACES
        if not detector_required:
            relationship = "not_arena_detector_target"
        elif exact:
            relationship = "exact_or_explicit_visual_class"
        elif family:
            relationship = "root_family_only_do_not_autolabel"
        else:
            relationship = "missing_visual_class"
        rows.append(
            {
                "actor_token_id": row["actor_token_id"],
                "stable_key": key,
                "stable_id": row["stable_id"],
                "canonical_name": row["canonical_name"],
                "namespace": row["namespace"],
                "variant_kinds": row["variant_kinds"],
                "owner_root_cards": row["owner_root_cards"],
                "katacr_relationship": relationship,
                "exact_visual_labels": exact,
                "family_only_labels": family,
                "detector_annotation_eligible": bool(detector_required and exact),
            }
        )
    return rows


def _build_segment_assets(
    segment_root: Path, token_map: list[dict[str, Any]], repository_root: Path
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    keys_by_label: dict[str, list[str]] = defaultdict(list)
    for row in token_map:
        for label in row["exact_visual_labels"]:
            keys_by_label[label].append(row["stable_key"])
    assets: list[dict[str, Any]] = []
    for path in sorted(segment_root.glob("*/*")):
        if not path.is_file() or path.suffix.lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError(f"could not decode {path}")
        height, width = image.shape[:2]
        digest = _sha256(path)
        group = _sequence_group(path)
        seed = hashlib.sha256(f"synthetic-placement-v1\0{digest}".encode()).digest()
        world_x = 1.0 + int.from_bytes(seed[:4], "big") / (2**32 - 1) * 16.0
        world_y = 1.0 + int.from_bytes(seed[4:8], "big") / (2**32 - 1) * 30.0
        assets.append(
            {
                "path": _relative(path, repository_root),
                "sha256": digest,
                "visual_class": path.parent.name,
                "stable_key_candidates": sorted(keys_by_label[path.parent.name]),
                "annotation_eligible": len(keys_by_label[path.parent.name]) == 1,
                "width": width,
                "height": height,
                "source_group_id": group,
                "split": _split(group),
                "synthetic_plan": {
                    "canvas": "procedural_arena_grid_v1",
                    "world_position": [round(world_x, 6), round(world_y, 6)],
                    "alpha_composite": image.ndim == 3 and image.shape[2] == 4,
                    "label_source": "existing_human_segment_class",
                },
            }
        )
    return assets, dict(Counter(row["split"] for row in assets))


def _build_card_assets(
    card_root: Path, vocabulary: dict[str, Any], repository_root: Path
) -> list[dict[str, Any]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for row in vocabulary["aliases"]:
        if row["context"] == "card_action":
            aliases[row["normalized_label"]].add(row["target_stable_key"])
    rows: list[dict[str, Any]] = []
    for path in sorted(card_root.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }:
            continue
        label = _card_template_label(path)
        candidates = sorted(aliases.get(_normalize(label), ()))
        rows.append(
            {
                "path": _relative(path, repository_root),
                "sha256": _sha256(path),
                "template_label": label,
                "card_action_candidates": candidates,
                "hud_annotation_eligible": len(candidates) == 1,
                "arena_detector_annotation_eligible": False,
                "reason": "card-face template is HUD evidence, not an in-arena body sprite",
            }
        )
    return rows


def _load_neutral(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def _arena_frame(capture: cv2.VideoCapture, timestamp_ms: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp_ms))
    ok, frame = capture.read()
    if not ok:
        raise ValueError(f"could not decode video at {timestamp_ms} ms")
    frame = cv2.resize(frame, (frame.shape[1] // 2, frame.shape[0] // 2))
    height, width = frame.shape[:2]
    x, y, w, h = ARENA_REGION
    crop = frame[
        round(y * height) : round((y + h) * height),
        round(x * width) : round((x + w) * width),
    ]
    return cv2.resize(crop, (CONTACT_SHEET_WIDTH, CONTACT_SHEET_HEIGHT))


def _render_contact_sheet(
    video: Path, records: list[dict[str, Any]], output: Path
) -> dict[str, Any]:
    eligible: list[tuple[int, int, int, dict[str, Any]]] = []
    for row in records:
        entities = [
            entity
            for entity in row["public"]["entities"]
            if entity["world_position"] is not None and entity["identity"]["valid"]
        ]
        non_towers = sum(
            not entity["visual_class"].endswith("tower") for entity in entities
        )
        eligible.append((non_towers, len(entities), row["sample_index"], row))
    chosen: list[dict[str, Any]] = []
    maximum_timestamp = max(row[3]["timestamp_ms"] for row in eligible)
    for bucket in range(6):
        lower = bucket * (maximum_timestamp + 1) / 6
        upper = (bucket + 1) * (maximum_timestamp + 1) / 6
        candidates = [
            item for item in eligible if lower <= item[3]["timestamp_ms"] < upper
        ]
        # Moderate-density frames make box/center alignment legible.  The
        # ordering is deterministic and does not depend on model confidence.
        candidate = min(
            candidates,
            key=lambda item: (
                abs(item[0] - 4),
                abs(item[1] - 10),
                abs(item[3]["timestamp_ms"] - (lower + upper) / 2),
                item[2],
            ),
        )
        chosen.append(candidate[3])
    chosen.sort(key=lambda row: row["timestamp_ms"])
    if len(chosen) != 6:
        raise ValueError("could not choose six separated contact-sheet frames")

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"could not open {video}")
    panels: list[np.ndarray] = []
    audit_rows: list[dict[str, Any]] = []
    for row in chosen:
        frame = _arena_frame(capture, row["timestamp_ms"])
        for x in range(19):
            px = round(x / 18 * CONTACT_SHEET_WIDTH)
            cv2.line(frame, (px, 0), (px, CONTACT_SHEET_HEIGHT), (65, 65, 65), 1)
        for y in range(33):
            py = round(62 + y / 32 * (CONTACT_SHEET_HEIGHT - 7 - 62))
            cv2.line(frame, (0, py), (CONTACT_SHEET_WIDTH, py), (65, 65, 65), 1)
        entities = [
            entity
            for entity in row["public"]["entities"]
            if entity["world_position"] is not None and entity["identity"]["valid"]
        ]
        entities.sort(
            key=lambda entity: (
                entity["visual_class"].endswith("tower"),
                -entity["confidence"],
            )
        )
        displayed = entities[:10]
        for index, entity in enumerate(displayed):
            x1, y1, x2, y2 = entity["sprite_box_normalized"]
            box = (
                round(x1 * CONTACT_SHEET_WIDTH),
                round(y1 * CONTACT_SHEET_HEIGHT),
                round(x2 * CONTACT_SHEET_WIDTH),
                round(y2 * CONTACT_SHEET_HEIGHT),
            )
            color = (80, 220, 255) if entity["team_id"] == 0 else (255, 130, 80)
            cv2.rectangle(frame, box[:2], box[2:], color, 2)
            world_x, world_y = entity["world_position"]
            px = round(world_x / 18 * CONTACT_SHEET_WIDTH)
            source_y = 32 - world_y
            py = round(62 + source_y / 32 * (CONTACT_SHEET_HEIGHT - 7 - 62))
            cv2.circle(frame, (px, py), 5, (0, 255, 0), -1)
            cv2.putText(
                frame,
                f"{index}:{entity['visual_class']}",
                (max(0, box[0]), max(14, box[1] - 3)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )
        cv2.rectangle(frame, (0, 0), (CONTACT_SHEET_WIDTH, 28), (0, 0, 0), -1)
        cv2.putText(
            frame,
            f"t={row['timestamp_ms'] / 1000:.1f}s boxes=sprites dots=18x32 world centers",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        panels.append(cv2.resize(frame, (384, 597)))
        audit_rows.append(
            {
                "sample_index": row["sample_index"],
                "timestamp_ms": row["timestamp_ms"],
                "displayed_entities": [
                    {
                        "visual_class": entity["visual_class"],
                        "stable_key": entity["identity"]["stable_key"],
                        "world_position": entity["world_position"],
                    }
                    for entity in displayed
                ],
            }
        )
    capture.release()
    sheet = np.vstack((np.hstack(panels[:3]), np.hstack(panels[3:])))
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise ValueError(f"could not write {output}")
    return {
        "path": str(output.resolve()),
        "sha256": _sha256(output),
        "frames": audit_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--vocabulary",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument(
        "--katacr-labels",
        default="datasets/external/KataCR/katacr/constants/label_list.py",
    )
    parser.add_argument(
        "--segment-root",
        default="datasets/external/Clash-Royale-Detection-Dataset/images/segment",
    )
    parser.add_argument(
        "--card-root",
        default="datasets/external/CS541-Deep-Learning-Clash-Royale-Project/cr_detection/cards",
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
    parser.add_argument(
        "--output", default="reports/current_client_detector_upgrade_manifest_v1.json"
    )
    parser.add_argument(
        "--contact-sheet",
        default="reports/current_client_detector_upgrade_alignment_contact_sheet_v1.jpg",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.repository_root).resolve()
    vocabulary_path = (root / args.vocabulary).resolve()
    label_path = (root / args.katacr_labels).resolve()
    segment_root = (root / args.segment_root).resolve()
    card_root = (root / args.card_root).resolve()
    neutral_path = (root / args.neutral_sequence).resolve()
    video_path = (root / args.video).resolve()
    output_path = (root / args.output).resolve()
    contact_path = (root / args.contact_sheet).resolve()

    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
    labels = _load_unit_labels(label_path)
    token_map = _build_token_map(vocabulary, labels)
    segment_assets, synthetic_split_counts = _build_segment_assets(
        segment_root, token_map, root
    )
    card_assets = _build_card_assets(card_root, vocabulary, root)
    records = _load_neutral(neutral_path)
    contact = _render_contact_sheet(video_path, records, contact_path)

    relationship_counts = Counter(row["katacr_relationship"] for row in token_map)
    missing_by_namespace = Counter(
        row["namespace"]
        for row in token_map
        if row["katacr_relationship"] == "missing_visual_class"
    )
    family_by_namespace = Counter(
        row["namespace"]
        for row in token_map
        if row["katacr_relationship"] == "root_family_only_do_not_autolabel"
    )
    segment_class_counts = Counter(row["visual_class"] for row in segment_assets)
    resolved_segment_assets = sum(row["annotation_eligible"] for row in segment_assets)
    resolved_card_assets = sum(row["hud_annotation_eligible"] for row in card_assets)
    typed_entities = sum(
        entity["identity"]["valid"]
        for row in records
        for entity in row["public"]["entities"]
    )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "authorities": {
            "stable_vocabulary": {
                "path": _relative(vocabulary_path, root),
                "sha256": _sha256(vocabulary_path),
            },
            "katacr_label_list": {
                "path": _relative(label_path, root),
                "sha256": _sha256(label_path),
                "labels": len(labels),
                "non_ui_labels": len(set(labels) - UI_LABELS),
                "repository_revision": "36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8",
            },
            "real_segment_repository_revision": "31b4151fedb1b914e99c3c122c16dca61cb2b905",
            "current_card_template_repository_revision": "08aafd87cb3707b779804918cc65f4ae430d37ab",
            "current_youtube_canary": {
                "video_id": "hTG8dM4KtM4",
                "video_sha256": _sha256(video_path),
                "neutral_sequence_path": _relative(neutral_path, root),
                "neutral_sequence_sha256": _sha256(neutral_path),
                "split": "test",
                "forced_canary_holdout": True,
            },
        },
        "counts": {
            "actor_tokens_total": len(token_map),
            "actor_tokens_reserved": 2,
            "arena_detector_tokens": sum(
                row["namespace"] in DETECTOR_NAMESPACES for row in token_map
            ),
            "relationship_counts": dict(sorted(relationship_counts.items())),
            "missing_by_namespace": dict(sorted(missing_by_namespace.items())),
            "family_only_by_namespace": dict(sorted(family_by_namespace.items())),
            "katacr_segment_assets": len(segment_assets),
            "katacr_segment_classes": len(segment_class_counts),
            "katacr_segment_assets_unambiguous": resolved_segment_assets,
            "synthetic_split_counts": synthetic_split_counts,
            "current_card_templates": len(card_assets),
            "current_card_templates_unambiguous": resolved_card_assets,
            "current_canary_frames": len(records),
            "current_canary_typed_entities": typed_entities,
        },
        "split_contract": {
            "schema": SPLIT_SCHEMA,
            "algorithm": "sha256(schema + NUL + source_group_id) modulo 10000",
            "thresholds": {
                "train": [0, 8000],
                "validation": [8000, 9000],
                "test": [9000, 10000],
            },
            "real_video_group": "entire YouTube video ID, every frame, and both actor views",
            "segment_group": "visual class plus filename prefix after removing only the final frame-number suffix",
            "synthetic_group": "foreground source group; every augmentation and placement remains in that group's split",
            "card_template_group": "card template SHA; HUD-only and never an arena-body annotation",
            "hard_rules": [
                "no adjacent frames from one source video cross splits",
                "no player-0/player-1 actor projections from one video cross splits",
                "no crop sequence or augmentation descendants cross splits",
                "offline temporal identity labels never become live policy inputs",
                "family-only mappings are candidates for manual review, never automatic labels",
                "the sole current YouTube canary is forced wholly to test until multiple current videos exist",
            ],
        },
        "annotation_contract": {
            "real": {
                "source": "current YouTube neutral sequence",
                "initial_group": "youtube:hTG8dM4KtM4",
                "split": "test",
                "labels": "human-confirmed or detector-assisted boxes retain source video and timestamp",
            },
            "synthetic": {
                "source": "human-segmented KataCR arena crops",
                "canvas": "procedural_arena_grid_v1 only; held-out real frames are not backgrounds",
                "box": "tight decoded crop rectangle; sprite box explicitly is not a game hitbox",
                "position": "deterministic SHA-derived 18x32 world coordinate",
                "use": "bootstrap geometry and old-class retention only; not sufficient current-client evidence",
            },
            "hud": {
                "source": "CS541 card-face templates",
                "use": "card/variant identity head only",
                "arena_detector_use": "forbidden",
            },
        },
        "token_to_katacr": token_map,
        "observable_missing_tokens": [
            row
            for row in token_map
            if row["katacr_relationship"]
            in {"missing_visual_class", "root_family_only_do_not_autolabel"}
        ],
        "segment_class_counts": dict(sorted(segment_class_counts.items())),
        "segment_assets": segment_assets,
        "card_template_assets": card_assets,
        "contact_sheet": contact,
    }
    payload["content_sha256"] = _json_sha(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "sha256": _sha256(output_path),
                "counts": payload["counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
