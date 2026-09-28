from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped"
import argparse
import gzip
import hashlib
import json
import math
import os
import re
import resource
import subprocess
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import torch
import torchvision
from PIL import Image
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from torchvision.transforms import functional as transform_functional

from clasher.rl.tv_royale_public_state import associate_health_to_entities
from clasher.rl.tv_royale_replay import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    TVRoyaleDetection,
    TVRoyalePlacementConverter,
)
from scripts.import_tv_royale_placements import (
    _combined_detections,
    _load_detector_models,
)

SCHEMA = "clasher.youtube.fullmatch.neutral_sequence.v1"
ACTOR_SCHEMA = "clasher.youtube.fullmatch.actor_trajectory.v1"
MANIFEST_SCHEMA = "clasher.youtube.fullmatch.extraction_manifest.v1"
SAMPLE_HZ = 10.0
ACTOR_HZ = 5.0
ARENA_REGION = (0.024, 0.196, 0.954, 0.659)
CLOCK_REGION = (0.805, 0.165, 0.195, 0.075)

# These are measured spectator-layout ROIs, not logical hitboxes. They are
# deliberately independent for the two HUDs because the broadcast layout is
# asymmetric.
HUD_ROIS: dict[int, dict[str, Any]] = {
    0: {
        "hand": tuple((x, 0.868, 0.145, 0.090) for x in (0.105, 0.252, 0.397, 0.532)),
        "next": (0.030, 0.862, 0.070, 0.075),
        "elixir": (0.030, 0.952, 0.070, 0.042),
    },
    1: {
        "hand": tuple((x, 0.098, 0.132, 0.085) for x in (0.130, 0.262, 0.394, 0.526)),
        "next": (0.030, 0.120, 0.065, 0.050),
        "elixir": (0.030, 0.058, 0.072, 0.045),
    },
}
ELIXIR_BAR_ROIS = {
    0: (0.085, 0.951, 0.880, 0.019),
    1: (0.085, 0.076, 0.880, 0.019),
}

# Detector support primitives are useful for HP association and event decoding,
# but they are not independently meaningful arena entities for the policy.
NON_ENTITY_VISUAL_CLASSES = frozenset(
    {
        "bar",
        "bar-level",
        "dagger-duchess-tower-bar",
        "elixir",
        "emote",
        "evolution-symbol",
        "ice-spirit-evolution-symbol",
        "king-tower-bar",
        "tower-bar",
    }
)


def _is_public_entity_visual_class(visual_class: str) -> bool:
    return visual_class.casefold() not in NON_ENTITY_VISUAL_CLASSES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _atomic_gzip_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    try:
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as output:
            for row in rows:
                output.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
                output.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _crop_relative(
    image: np.ndarray, box: tuple[float, float, float, float]
) -> np.ndarray:
    height, width = image.shape[:2]
    x, y, box_width, box_height = box
    x1 = max(0, min(width, round(x * width)))
    y1 = max(0, min(height, round(y * height)))
    x2 = max(x1 + 1, min(width, round((x + box_width) * width)))
    y2 = max(y1 + 1, min(height, round((y + box_height) * height)))
    return image[y1:y2, x1:x2]


def _vector(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    resized = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB).astype(np.float32)
    value = lab.reshape(-1)
    value -= float(value.mean())
    norm = float(np.linalg.norm(value))
    return cast(np.ndarray, np.asarray(value / max(norm, 1e-8), dtype=np.float32))


class HudRecognizer:
    """Current-frame-only spectator HUD matcher with conservative validity."""

    def __init__(
        self,
        template_root: Path,
        identity_resolver: StableIdentityResolver,
        *,
        device: str,
        card_weight_path: Path | None = None,
        card_preprocess_backend: str = "pil",
        card_preprocess_workers: int = 8,
    ) -> None:
        self.identity_resolver = identity_resolver
        self.device = torch.device(device)
        self.card_weights = MobileNet_V3_Small_Weights.DEFAULT
        if card_weight_path is None:
            self.card_model = mobilenet_v3_small(weights=self.card_weights)
        else:
            self.card_model = mobilenet_v3_small(weights=None)
            state = torch.load(card_weight_path, map_location="cpu", weights_only=True)
            self.card_model.load_state_dict(state)
        self.card_model = self.card_model.to(self.device).eval()
        if card_preprocess_backend not in {"pil", "pil-batched", "tensor"}:
            raise ValueError(
                "card_preprocess_backend must be 'pil', 'pil-batched', or 'tensor'"
            )
        self.card_preprocess_backend = card_preprocess_backend
        if card_preprocess_workers <= 0:
            raise ValueError("card_preprocess_workers must be positive")
        self.card_preprocess_workers = min(
            card_preprocess_workers, os.cpu_count() or card_preprocess_workers
        )
        self._pil_pool = ThreadPoolExecutor(max_workers=self.card_preprocess_workers)
        card_rows: list[tuple[str, np.ndarray]] = []
        for path in sorted((template_root / "cr_detection/cards").glob("*.png")):
            name = path.stem.rsplit("-", 1)[0]
            stable_key = (
                "empty"
                if name == "empty"
                else identity_resolver.resolve_card_label(name)
            )
            if stable_key is None:
                continue
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is not None:
                card_rows.append((stable_key, image))
        if not card_rows:
            raise ValueError("card template library is empty")
        self.card_names = [row[0] for row in card_rows]
        self.card_families = [
            identity_resolver.card_family_key(name) for name in self.card_names
        ]
        self.card_vectors = self._embed_cards([row[1] for row in card_rows])

    @staticmethod
    def _decision(
        scores: np.ndarray,
        labels: list[Any],
        *,
        minimum: float,
        minimum_margin: float,
    ) -> dict[str, Any]:
        order = np.argsort(scores)
        best_index = int(order[-1])
        runner_index = int(order[-2]) if len(order) > 1 else best_index
        score = float(scores[best_index])
        runner = float(scores[runner_index])
        margin = score - runner
        valid = bool(score >= minimum and margin >= minimum_margin)
        return {
            "value": labels[best_index] if valid else None,
            "candidate": labels[best_index],
            "score": score,
            "runner_up_score": runner,
            "margin": margin,
            "valid": valid,
            "reason": None if valid else "uncalibrated_or_ambiguous_template_match",
        }

    def _embed_cards(self, crops: list[np.ndarray]) -> np.ndarray:
        rows: list[np.ndarray] = []
        transform = self.card_weights.transforms()
        for start in range(0, len(crops), 128):
            batch = crops[start : start + 128]
            if self.card_preprocess_backend == "pil":
                tensors = torch.stack(
                    [
                        transform(
                            Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                        )
                        for crop in batch
                    ]
                ).to(self.device)
            elif self.card_preprocess_backend == "pil-batched":
                tensors = self._pil_batched_preprocess(batch, transform)
            else:
                tensors = self._tensor_preprocess(batch, transform)
            with torch.inference_mode():
                features = self.card_model.avgpool(
                    self.card_model.features(tensors)
                ).flatten(1)
                features = torch.nn.functional.normalize(features, dim=1)
            rows.append(features.detach().cpu().numpy())
        return cast(np.ndarray, np.concatenate(rows, axis=0))

    def _pil_batched_preprocess(
        self,
        crops: list[np.ndarray],
        transform: Any,
    ) -> torch.Tensor:
        """Preserve PIL interpolation while batching tensor work on-device."""

        def resize_and_crop(crop: np.ndarray) -> np.ndarray:
            image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            image = transform_functional.resize(
                image,
                transform.resize_size,
                interpolation=transform.interpolation,
                antialias=transform.antialias,
            )
            image = transform_functional.center_crop(image, transform.crop_size)
            return np.array(image, dtype=np.uint8, copy=True)

        pixels = np.stack(list(self._pil_pool.map(resize_and_crop, crops)), axis=0)
        tensors = torch.from_numpy(pixels).permute(0, 3, 1, 2)
        tensors = transform_functional.convert_image_dtype(tensors, torch.float32)
        tensors = transform_functional.normalize(tensors, transform.mean, transform.std)
        return cast(torch.Tensor, tensors.contiguous().to(self.device))

    def _tensor_preprocess(
        self,
        crops: list[np.ndarray],
        transform: torch.nn.Module,
    ) -> torch.Tensor:
        """Batch fixed-shape HUD crops before resizing them on the model device."""

        output = torch.empty(
            (len(crops), 3, 224, 224), dtype=torch.float32, device=self.device
        )
        groups: dict[tuple[int, int, int], list[int]] = {}
        for index, crop in enumerate(crops):
            groups.setdefault(tuple(crop.shape), []).append(index)
        for indices in groups.values():
            # The decoder emits BGR. Reversing the last axis once for the whole
            # shape bucket avoids hundreds of independent PIL objects.
            rgb = np.ascontiguousarray(
                np.stack([crops[index] for index in indices], axis=0)[..., ::-1]
            )
            tensor = torch.from_numpy(rgb).permute(0, 3, 1, 2).to(self.device)
            prepared = transform(tensor)
            output[torch.tensor(indices, dtype=torch.long, device=self.device)] = prepared
        return output

    def cards(self, crops: list[np.ndarray]) -> list[dict[str, Any]]:
        score_rows = self._embed_cards(crops) @ self.card_vectors.T
        output: list[dict[str, Any]] = []
        for index, scores in enumerate(score_rows):
            family_scores: dict[str, float] = {}
            best_variant: dict[str, tuple[float, str]] = {}
            for score, variant, family in zip(
                scores, self.card_names, self.card_families, strict=True
            ):
                value = float(score)
                family_scores[family] = max(family_scores.get(family, -1.0), value)
                if family not in best_variant or value > best_variant[family][0]:
                    best_variant[family] = (value, variant)
            families = sorted(family_scores, key=lambda family: family_scores[family])
            best_family = families[-1]
            runner = family_scores[families[-2]] if len(families) > 1 else -1.0
            score = family_scores[best_family]
            margin = score - runner
            minimum = 0.70 if index % 5 == 4 else 0.72
            valid = bool(score >= minimum and margin >= 0.035)
            variant_score, variant = best_variant[best_family]
            output.append(
                {
                    "value": best_family if valid else None,
                    "candidate": best_family,
                    "score": score,
                    "runner_up_score": runner,
                    "margin": margin,
                    "valid": valid,
                    "reason": (
                        None
                        if valid
                        else "uncalibrated_or_ambiguous_card_family_embedding"
                    ),
                    "variant_candidate": variant,
                    "variant_score": variant_score,
                    "variant_label_only": True,
                }
            )
        return output

    @staticmethod
    def _elixir_bar(image: np.ndarray, player_id: int) -> dict[str, Any]:
        crop = _crop_relative(image, ELIXIR_BAR_ROIS[player_id])
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        magenta = (
            (hsv[:, :, 0] >= 135)
            & (hsv[:, :, 0] <= 175)
            & (hsv[:, :, 1] >= 100)
            & (hsv[:, :, 2] >= 80)
        )
        columns = np.flatnonzero(magenta.mean(axis=0) >= 0.10)
        dark_fraction = float(np.mean(hsv[:, :, 2] <= 100))
        if not len(columns) and dark_fraction < 0.15:
            return {
                "value": None,
                "candidate": None,
                "score": 0.0,
                "runner_up_score": 0.0,
                "margin": 0.0,
                "valid": False,
                "reason": "elixir_bar_not_visible",
                "evidence": "current_frame_public_color_bar",
            }
        last = int(columns[-1]) if len(columns) else 0
        continuity = float(len(columns)) / float(last + 1) if len(columns) else 1.0
        value = float(np.clip(last / max(1, crop.shape[1] - 1) * 10.0, 0.0, 10.0))
        valid = bool(continuity >= 0.90)
        return {
            "value": value if valid else None,
            "candidate": value,
            "score": continuity,
            "runner_up_score": 0.0,
            "margin": continuity,
            "valid": valid,
            "reason": None if valid else "elixir_fill_not_contiguous",
            "evidence": "current_frame_public_color_bar",
        }

    def prepare_frame(self, image: np.ndarray) -> dict[int, dict[str, Any]]:
        prepared: dict[int, dict[str, Any]] = {}
        for player_id in (0, 1):
            layout = HUD_ROIS[player_id]
            prepared[player_id] = {
                "card_crops": [
                    *[_crop_relative(image, box) for box in layout["hand"]],
                    _crop_relative(image, layout["next"]),
                ],
                "elixir": self._elixir_bar(image, player_id),
            }
        return prepared

    def resolve_batch(
        self, prepared_frames: list[dict[int, dict[str, Any]]]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        crops = [
            crop
            for prepared in prepared_frames
            for player_id in (0, 1)
            for crop in prepared[player_id]["card_crops"]
        ]
        decisions = iter(self.cards(crops))
        output: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for prepared in prepared_frames:
            player_rows: list[dict[str, Any]] = []
            for player_id in (0, 1):
                cards = [next(decisions) for _ in range(5)]
                hands = cards[:4]
                next_card = cards[4]
                elixir = prepared[player_id]["elixir"]
                player_rows.append(
                    {
                        "hand": hands,
                        "next_card": next_card,
                        "elixir": elixir,
                        "all_hand_valid": all(item["valid"] for item in hands),
                        "complete_valid": bool(
                            all(item["valid"] for item in hands)
                            and next_card["valid"]
                            and elixir["valid"]
                        ),
                    }
                )
            output.append((player_rows[0], player_rows[1]))
        return output


class StableIdentityResolver:
    def __init__(self, manifest: Path, converter: TVRoyalePlacementConverter) -> None:
        payload = json.loads(manifest.read_text())
        self.manifest_sha256 = _sha256(manifest)
        self.converter = converter
        self.by_key = {row["stable_key"]: row for row in payload["entries"]}
        self.card_family_by_key = {
            str(row["stable_key"]): str(row["stable_key"])
            for row in payload["entries"]
            if row["namespace"] == "card_action"
        }
        for pair in [*payload["evolution_variants"], *payload["hero_variants"]]:
            variant_key = f"card_action:{pair['variant']}"
            base_key = f"card_action:{pair['base']}"
            if variant_key in self.card_family_by_key and base_key in self.by_key:
                self.card_family_by_key[variant_key] = base_key
        self.by_normalized: dict[str, list[str]] = {}
        self.card_by_normalized: dict[str, set[str]] = {}
        for row in payload["entries"]:
            if row["namespace"] not in {
                "troop_body",
                "building_body",
                "projectile",
                "area_effect",
                "tower",
            }:
                continue
            normalized = self._normalize(str(row["canonical_name"]))
            self.by_normalized.setdefault(normalized, []).append(str(row["stable_key"]))
        for alias in payload["aliases"]:
            if alias.get("context") != "card_action":
                continue
            normalized = str(alias["normalized_label"])
            self.card_by_normalized.setdefault(normalized, set()).add(
                str(alias["target_stable_key"])
            )
        for pair in payload["evolution_variants"]:
            base_normalized = self._normalize(str(pair["base"]))
            variant_key = f"card_action:{pair['variant']}"
            if variant_key in self.by_key:
                self.card_by_normalized.setdefault(f"evo{base_normalized}", set()).add(
                    variant_key
                )

        # Dataset asset abbreviations are recognition labels only. They never
        # become primary IDs and are resolved in card-action context.
        template_aliases = {
            "barbs": "Barbarians",
            "ebarbs": "AngryBarbarians",
            "ewiz": "ElectroWizard",
            "skelebarrel": "SkeletonBalloon",
            "teslacoil": "Tesla",
            "valk": "Valkyrie",
            "snowball": "Snowball",
            "barbbarrel": "BarbLog",
        }
        for source, target in template_aliases.items():
            key = f"card_action:{target}"
            if key in self.by_key:
                self.card_by_normalized.setdefault(source, set()).add(key)

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(
            character for character in value.casefold() if character.isalnum()
        )

    def resolve(self, detection: TVRoyaleDetection) -> dict[str, Any]:
        normalized = self._normalize(detection.class_name)
        if normalized in {"queentower", "cannoneertower", "daggerduchesstower"}:
            candidates = ["tower:Tower"]
        elif normalized == "kingtower":
            candidates = ["tower:KingTower"]
        else:
            mapped = self.converter.unit_token(detection.class_name)
            mapped_name = None if mapped is None else mapped[1]
            candidate_names = {normalized}
            if mapped_name and mapped_name != self.converter.builder.UNKNOWN_TOKEN:
                candidate_names.add(self._normalize(mapped_name))
            candidates = sorted(
                {
                    key
                    for name in candidate_names
                    for key in self.by_normalized.get(name, [])
                }
            )
        valid = len(candidates) == 1
        return {
            "stable_key": candidates[0] if valid else None,
            "candidates": candidates,
            "valid": valid,
            "reason": None
            if valid
            else (
                "unknown_visual_class" if not candidates else "typed_identity_ambiguous"
            ),
        }

    def resolve_card_label(self, raw_label: str) -> str | None:
        normalized = self._normalize(raw_label)
        targets = sorted(self.card_by_normalized.get(normalized, set()))
        visible_targets = [
            target
            for target in targets
            if self.by_key[target]["policy_token_eligible"]
            and not self.by_key[target]["not_visible"]
        ]
        if len(visible_targets) == 1:
            return visible_targets[0]
        return targets[0] if len(targets) == 1 else None

    def card_family_key(self, stable_key: str) -> str:
        if stable_key == "empty":
            return stable_key
        return self.card_family_by_key.get(stable_key, stable_key)

    def card_mana_cost(self, stable_key: str) -> float | None:
        row = self.by_key.get(self.card_family_key(stable_key))
        if row is None:
            return None
        value = row.get("mana_cost")
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)


def _world_position(detection: TVRoyaleDetection) -> tuple[float, float]:
    center_x = (detection.x1 + detection.x2) * 0.5
    center_y = (detection.y1 + detection.y2) * 0.5
    grid_top = 62.0
    grid_bottom = IMAGE_HEIGHT - 7.0
    x = float(np.clip(center_x / IMAGE_WIDTH * 18.0, 0.0, 18.0))
    source_y = float(
        np.clip((center_y - grid_top) / (grid_bottom - grid_top) * 32.0, 0.0, 32.0)
    )
    return x, 32.0 - source_y


def _world_position_inside_grid(
    detection: TVRoyaleDetection,
) -> tuple[float, float] | None:
    center_x = (detection.x1 + detection.x2) * 0.5
    center_y = (detection.y1 + detection.y2) * 0.5
    grid_top = 62.0
    grid_bottom = IMAGE_HEIGHT - 7.0
    if not 0.0 <= center_x <= IMAGE_WIDTH or not grid_top <= center_y <= grid_bottom:
        return None
    return (
        center_x / IMAGE_WIDTH * 18.0,
        32.0 - (center_y - grid_top) / (grid_bottom - grid_top) * 32.0,
    )


def _public_mask(hud: dict[str, Any]) -> dict[str, Any]:
    # This conservative mask is derived only from current public HUD evidence.
    # It never inspects the demonstrated action or simulator state. If any
    # required HUD head is missing, fail closed to the no-op action.
    noop = 4 * 18 * 32
    if not hud["complete_valid"]:
        return {
            "contract": "label_independent_public_fail_closed_v1",
            "legal_action_indices": [noop],
            "valid": True,
            "degraded_reason": "incomplete_current_frame_hud",
        }
    # A complete HUD still lacks a proven camera-only occupancy/ability gate in
    # this canary. Preserve no-op-only rather than fabricate legality.
    return {
        "contract": "label_independent_public_fail_closed_v1",
        "legal_action_indices": [noop],
        "valid": True,
        "degraded_reason": "camera_only_full_legality_not_yet_proven",
    }


def _serialize_detection(
    detection: TVRoyaleDetection,
    identity: dict[str, Any],
    health: dict[int, Any],
    index: int,
) -> dict[str, Any]:
    world_x, world_y = _world_position(detection)
    hp = health.get(index)
    normalized = StableIdentityResolver._normalize(detection.class_name)
    is_ui = normalized in {
        "bar",
        "barlevel",
        "towerbar",
        "kingtowerbar",
        "clock",
        "elixir",
        "text",
        "selected",
    }
    return {
        "visual_class": detection.class_name,
        "team_id": detection.belonging if detection.belonging in {0, 1} else None,
        "confidence": detection.confidence,
        "sprite_box_normalized": [
            detection.x1 / IMAGE_WIDTH,
            detection.y1 / IMAGE_HEIGHT,
            detection.x2 / IMAGE_WIDTH,
            detection.y2 / IMAGE_HEIGHT,
        ],
        "sprite_box_is_hitbox": False,
        "world_position": [world_x, world_y] if not is_ui else None,
        "identity": identity,
        "hp_fraction": None if hp is None else hp.fill_fraction,
        "hp_confidence": 0.0 if hp is None else hp.confidence,
        "hp_valid": hp is not None,
        "status": {
            "valid": False,
            "confidence": 0.0,
            "reason": "no_calibrated_status_head",
        },
        "projectile_target": {
            "valid": False,
            "confidence": 0.0,
            "reason": "no_projectile_target_head",
        },
    }


def _event_rows(
    records: list[dict[str, Any]],
    *,
    identity_resolver: StableIdentityResolver | None = None,
    maximum_gap_ms: int = 1_500,
    minimum_deck_observations: int = 100,
    maximum_cost_error: float = 1.0,
) -> list[dict[str, Any]]:
    def complete_hand(row: dict[str, Any], team: int) -> set[str] | None:
        hud = row["offline_privileged_hud"][str(team)]
        if not hud["all_hand_valid"]:
            return None
        values = [item["value"] for item in hud["hand"]]
        if any(not isinstance(value, str) or not value for value in values):
            return None
        return set(values)

    deck_counts: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
    for row in records:
        for team in (0, 1):
            for item in row["offline_privileged_hud"][str(team)]["hand"]:
                value = item.get("value")
                if item.get("valid") and isinstance(value, str) and value != "empty":
                    deck_counts[team][value] += 1

    events: list[dict[str, Any]] = []
    recent: dict[int, list[tuple[int, float, float]]] = {0: [], 1: []}
    for record_index, record in enumerate(records):
        timestamp = int(record["timestamp_ms"])
        entities = record["public"]["entities"]
        markers = [
            row
            for row in entities
            if StableIdentityResolver._normalize(row["visual_class"]) == "clock"
            and row["team_id"] in {0, 1}
        ]
        bodies = [
            row
            for row in entities
            if row["world_position"] is not None and row["identity"]["valid"]
        ]
        for marker in markers:
            team = int(marker["team_id"])
            position = _world_position_inside_grid(
                TVRoyaleDetection(
                    class_name="clock",
                    belonging=team,
                    confidence=float(marker["confidence"]),
                    x1=float(marker["sprite_box_normalized"][0]) * IMAGE_WIDTH,
                    y1=float(marker["sprite_box_normalized"][1]) * IMAGE_HEIGHT,
                    x2=float(marker["sprite_box_normalized"][2]) * IMAGE_WIDTH,
                    y2=float(marker["sprite_box_normalized"][3]) * IMAGE_HEIGHT,
                )
            )
            if position is None:
                continue
            mx, my = position
            recent[team] = [
                item for item in recent[team] if timestamp - item[0] <= maximum_gap_ms
            ]
            if recent[team]:
                continue
            recent[team].append((timestamp, mx, my))
            nearby = [
                row
                for row in bodies
                if row["team_id"] == team
                and math.dist(row["world_position"], [mx, my]) <= 3.0
                and not str(row["identity"]["stable_key"]).startswith("tower:")
            ]
            body_identities = sorted({row["identity"]["stable_key"] for row in nearby})
            before_hand = next(
                (
                    hand
                    for candidate in reversed(
                        records[max(0, record_index - 12) : record_index]
                    )
                    if (hand := complete_hand(candidate, team)) is not None
                ),
                None,
            )
            after_hand = next(
                (
                    hand
                    for candidate in records[record_index : record_index + 17]
                    if (hand := complete_hand(candidate, team)) is not None
                ),
                None,
            )
            disappeared = (
                sorted(before_hand.difference(after_hand))
                if before_hand is not None and after_hand is not None
                else []
            )
            hud_card = disappeared[0] if len(disappeared) == 1 else None
            identity_rejections: list[str] = []
            if (
                hud_card is not None
                and deck_counts[team][hud_card] < minimum_deck_observations
            ):
                identity_rejections.append("insufficient_stable_deck_support")
            expected_cost = None
            if hud_card is not None and identity_resolver is not None:
                expected_cost = identity_resolver.card_mana_cost(hud_card)
            window = records[
                max(0, record_index - 15) : min(len(records), record_index + 16)
            ]
            elixir_values = [
                (
                    int(candidate["timestamp_ms"]),
                    float(
                        candidate["offline_privileged_hud"][str(team)]["elixir"][
                            "value"
                        ]
                    ),
                )
                for candidate in window
                if candidate["offline_privileged_hud"][str(team)]["elixir"]["valid"]
            ]
            drop_candidates = [
                (
                    abs(new_time - timestamp),
                    old_value - new_value,
                )
                for (_old_time, old_value), (new_time, new_value) in pairwise(
                    elixir_values
                )
                if old_value - new_value >= 0.5 and abs(new_time - timestamp) <= 1_000
            ]
            observed_drop = (
                min(drop_candidates, key=lambda item: (item[0], -item[1]))[1]
                if drop_candidates
                else 0.0
            )
            if (
                expected_cost is not None
                and abs(observed_drop - expected_cost) > maximum_cost_error
            ):
                identity_rejections.append("public_elixir_cost_mismatch")
            if identity_rejections:
                hud_card = None
            absolute_tile = [
                max(0, min(17, math.floor(mx))),
                max(0, min(31, math.floor(my))),
            ]
            canonical_tile = (
                absolute_tile
                if team == 0
                else [17 - absolute_tile[0], 31 - absolute_tile[1]]
            )
            events.append(
                {
                    "event_id": f"event-{len(events):05d}",
                    "timestamp_ms": timestamp,
                    "player_id": team,
                    "deployment_world_position": [mx, my],
                    "deployment_tile_absolute": absolute_tile,
                    "deployment_tile_actor_canonical": canonical_tile,
                    "placement_valid": True,
                    "card_identity": hud_card,
                    "identity_candidates": disappeared,
                    "identity_valid": hud_card is not None,
                    "body_identity_candidates": body_identities,
                    "hud_identity_crosscheck_valid": hud_card is not None,
                    "hud_identity_crosscheck_reason": (
                        None
                        if hud_card is not None
                        else (
                            identity_rejections[0]
                            if identity_rejections
                            else "no_unique_complete_hand_disappearance"
                        )
                    ),
                    "identity_rejections": identity_rejections,
                    "stable_deck_observations": (
                        0 if not disappeared else deck_counts[team][disappeared[0]]
                    ),
                    "expected_public_cost": expected_cost,
                    "observed_max_elixir_drop": observed_drop,
                    "play_valid": hud_card is not None,
                    "evidence": (
                        "public_hand_disappearance_plus_temporally_deduplicated_"
                        "deployment_marker"
                    ),
                    "offline_label_only": True,
                }
            )
    return events


def _actor_row(record: dict[str, Any], actor_id: int) -> dict[str, Any]:
    own = record["offline_privileged_hud"][str(actor_id)]
    return {
        "schema": ACTOR_SCHEMA,
        "match_id": record["match_id"],
        "split_group_id": record["split_group_id"],
        "snapshot_id": record["snapshot_id"],
        "output_pts": record["output_pts"],
        "output_time_base": record["output_time_base"],
        "source_time_base": record["source_time_base"],
        "timestamp_ms": record["timestamp_ms"],
        "actor_id": actor_id,
        "public": record["public"],
        "own_hud": own,
        "public_action_mask": _public_mask(own),
        "label_validity": {
            "hand": [bool(item["valid"]) for item in own["hand"]],
            "next_card": bool(own["next_card"]["valid"]),
            "elixir": bool(own["elixir"]["valid"]),
            "clock": bool(record["public"]["clock"]["valid"]),
            "entities": True,
        },
    }


def _write_raw_actor_trajectories(
    output: Path,
    records: list[dict[str, Any]],
    *,
    actor_stride: int,
    mode: str,
) -> tuple[list[Path], dict[str, int]]:
    if mode == "deferred":
        return [], {}
    if mode != "full":
        raise ValueError(f"unsupported raw actor mode: {mode}")
    actor_paths: list[Path] = []
    actor_counts: dict[str, int] = {}
    for actor_id in (0, 1):
        rows = [
            _actor_row(record, actor_id)
            for index, record in enumerate(records)
            if index % actor_stride == 0
        ]
        actor_path = output / f"actor_{actor_id}_trajectory.jsonl.gz"
        _atomic_gzip_jsonl(actor_path, rows)
        actor_paths.append(actor_path)
        actor_counts[str(actor_id)] = len(rows)
    return actor_paths, actor_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract one full permissioned YouTube match"
    )
    parser.add_argument("--input-video", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--vocabulary-manifest",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument(
        "--template-root",
        default="datasets/external/CS541-Deep-Learning-Clash-Royale-Project",
    )
    parser.add_argument(
        "--card-embedding-weight",
        type=Path,
        help="Pinned local MobileNetV3-Small state dict; prevents runtime download",
    )
    parser.add_argument("--katacr-root", default="datasets/external/KataCR")
    parser.add_argument("--detector-weight", action="append", required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--card-preprocess-backend",
        choices=("pil", "pil-batched", "tensor"),
        default="pil",
        help="Use the reference PIL path or batched tensor preprocessing.",
    )
    parser.add_argument("--card-preprocess-workers", type=int, default=8)
    parser.add_argument(
        "--detection-nms-backend",
        choices=("auto", "cpu", "native", "shadow"),
        default="auto",
        help=(
            "Keep cross-model NMS on CUDA when possible; cpu forces the "
            "reference device and shadow fails on native/reference divergence."
        ),
    )
    parser.add_argument(
        "--raw-actor-mode",
        choices=("full", "deferred"),
        default="full",
        help=(
            "Write standalone actor rows or defer them when the next pipeline "
            "stage deterministically rebuilds actors from the neutral sequence."
        ),
    )
    parser.add_argument("--sample-hz", type=float, default=SAMPLE_HZ)
    parser.add_argument("--actor-hz", type=float, default=ACTOR_HZ)
    parser.add_argument(
        "--clock-provider-mode",
        choices=("macos-vision", "deferred"),
        default="macos-vision",
        help=(
            "Use the local macOS Vision OCR head or leave clocks invalid for a "
            "pinned external Linux clock adapter to publish in a later stage."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_hz <= 0 or args.actor_hz <= 0 or args.sample_hz % args.actor_hz != 0:
        raise ValueError("sample-hz must be a positive integer multiple of actor-hz")
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    source = Path(args.input_video).resolve()
    source_manifest = Path(args.source_manifest).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not source.is_file() or not source_manifest.is_file():
        raise FileNotFoundError("input video and source manifest are required")
    acquisition = json.loads(source_manifest.read_text())
    source_row = acquisition.get("source", {})
    source_id = str(source_row.get("video_id") or source_row.get("id") or source.stem)
    match_id = f"youtube-{source_id}"
    split_group = match_id

    converter = TVRoyalePlacementConverter(source_frame_hz=args.sample_hz)
    identity = StableIdentityResolver(
        Path(args.vocabulary_manifest).resolve(), converter
    )
    hud_load_start = time.perf_counter()
    hud = HudRecognizer(
        Path(args.template_root).resolve(),
        identity,
        device=args.device,
        card_weight_path=(
            None
            if args.card_embedding_weight is None
            else args.card_embedding_weight.resolve()
        ),
        card_preprocess_backend=args.card_preprocess_backend,
        card_preprocess_workers=args.card_preprocess_workers,
    )
    hud_model_load_seconds = time.perf_counter() - hud_load_start
    weights = [Path(value).resolve() for value in args.detector_weight]
    load_start = time.perf_counter()
    models = _load_detector_models(weights, Path(args.katacr_root).resolve())
    model_load_seconds = time.perf_counter() - load_start

    acquisition_decode = acquisition["decode"]
    expected_samples = int(acquisition_decode["sample_count"])
    source_media = acquisition["source_media"]
    source_fps = float(source_media["nominal_frames_per_second"])
    source_frames = int(source_media["video_packet_count"])
    duration_seconds = float(source_media["probed_duration_seconds"])
    semantic_width = int(source_media["width"]) // 2
    semantic_height = int(source_media["height"]) // 2
    ffmpeg_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        (
            f"fps={args.sample_hz:g},"
            f"scale={semantic_width}:{semantic_height}:flags=lanczos"
        ),
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    decoder = subprocess.Popen(
        ffmpeg_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decoder.stdout is not None
    decoded_source_frames = 0
    sampled_frames = 0
    decode_seconds = 0.0
    hud_seconds = 0.0
    detector_seconds = 0.0
    raw_detector_proposals = 0
    filtered_non_entity_proposals = 0
    records: list[dict[str, Any]] = []
    batch_images: list[np.ndarray] = []
    batch_meta: list[tuple[int, int, dict[int, dict[str, Any]], np.ndarray]] = []
    mps_peak = 0
    clock_temporary = tempfile.TemporaryDirectory(prefix="clasher-fullmatch-clock-")
    clock_root = Path(clock_temporary.name)
    clock_paths: dict[int, Path] = {}

    def flush() -> None:
        nonlocal detector_seconds, hud_seconds, mps_peak
        nonlocal filtered_non_entity_proposals, raw_detector_proposals
        if not batch_images:
            return
        hud_start = time.perf_counter()
        resolved_hud = hud.resolve_batch([row[2] for row in batch_meta])
        hud_seconds += time.perf_counter() - hud_start
        detect_start = time.perf_counter()
        per_model = [
            model.predict(
                batch_images,
                device=args.device,
                verbose=False,
                conf=0.4,
                iou=0.6,
                imgsz=(896, 576),
            )
            for model in models
        ]
        if args.device == "mps":
            torch.mps.synchronize()
            mps_peak = max(mps_peak, int(torch.mps.current_allocated_memory()))
        elif args.device == "cuda":
            torch.cuda.synchronize()
        detector_seconds += time.perf_counter() - detect_start
        for local, (sample_index, timestamp, _prepared, arena) in enumerate(batch_meta):
            hud0, hud1 = resolved_hud[local]
            detections = _combined_detections(
                [rows[local] for rows in per_model],
                models,
                nms_iou=0.6,
                nms_backend=args.detection_nms_backend,
            )
            raw_detector_proposals += len(detections)
            health = {
                item.entity_index: item
                for item in associate_health_to_entities(
                    arena,
                    detections,
                    body_class_predicate=converter.is_supported_public_body_class,
                )
            }
            entities = []
            for index, row in enumerate(detections):
                if not _is_public_entity_visual_class(row.class_name):
                    filtered_non_entity_proposals += 1
                    continue
                entities.append(
                    _serialize_detection(row, identity.resolve(row), health, index)
                )
            records.append(
                {
                    "schema": SCHEMA,
                    "match_id": match_id,
                    "split_group_id": split_group,
                    "snapshot_id": f"{match_id}-{sample_index:06d}",
                    "sample_index": sample_index,
                    "output_pts": sample_index,
                    "output_time_base": f"1/{round(args.sample_hz)}",
                    "source_time_base": acquisition["source_media"]["source_time_base"],
                    "timestamp_ms": timestamp,
                    "public": {
                        "coordinate_frame": "absolute_world",
                        "clock": {
                            "value": None,
                            "valid": False,
                            "confidence": 0.0,
                            "reason": "image_to_text_clock_head_not_available",
                            "media_elapsed_ms_label_only": timestamp,
                        },
                        "entities": entities,
                        "current_frame_deployment_markers": [
                            row
                            for row in entities
                            if StableIdentityResolver._normalize(row["visual_class"])
                            == "clock"
                        ],
                    },
                    "offline_privileged_hud": {"0": hud0, "1": hud1},
                    "offline_evidence": {
                        "raw_frame_exported": False,
                        "simulator_state_used": False,
                        "exact_simulator_action_mask_used": False,
                    },
                }
            )
        batch_images.clear()
        batch_meta.clear()

    frame_bytes = semantic_width * semantic_height * 3
    for output_pts in range(expected_samples):
        decode_start = time.perf_counter()
        chunks: list[bytes] = []
        remaining = frame_bytes
        while remaining:
            chunk = decoder.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        decode_seconds += time.perf_counter() - decode_start
        if remaining:
            stderr = (
                decoder.stderr.read().decode("utf-8", errors="replace")
                if decoder.stderr is not None
                else ""
            )
            raise ValueError(
                f"ffmpeg ended at output PTS {output_pts}; missing {remaining} "
                f"raw bytes: {stderr[-1000:]}"
            )
        frame = np.frombuffer(b"".join(chunks), dtype=np.uint8).reshape(
            semantic_height, semantic_width, 3
        )
        decoded_source_frames += 1
        # Exact acquisition fps-filter contract: output PTS is the zero-based
        # sample index in a 1/10 time base. Do not relabel rows from OpenCV's
        # estimate of a selected source frame's time.
        timestamp = round(output_pts / args.sample_hz * 1000.0)
        arena = cv2.resize(
            _crop_relative(frame, ARENA_REGION),
            (IMAGE_WIDTH, IMAGE_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )
        if args.clock_provider_mode == "macos-vision" and output_pts % 5 == 0:
            clock_path = clock_root / f"clock_{output_pts:06d}.png"
            if not cv2.imwrite(str(clock_path), _crop_relative(frame, CLOCK_REGION)):
                raise ValueError(f"could not write temporary clock crop {clock_path}")
            clock_paths[output_pts] = clock_path
        hud_start = time.perf_counter()
        prepared_hud = hud.prepare_frame(frame)
        hud_seconds += time.perf_counter() - hud_start
        batch_images.append(arena)
        batch_meta.append((sampled_frames, timestamp, prepared_hud, arena))
        sampled_frames += 1
        if len(batch_images) >= args.batch_size:
            flush()
    decoder.stdout.close()
    stderr = (
        decoder.stderr.read().decode("utf-8", errors="replace")
        if decoder.stderr is not None
        else ""
    )
    decoder_return = decoder.wait()
    if decoder_return != 0:
        raise ValueError(f"ffmpeg decode failed ({decoder_return}): {stderr[-1000:]}")
    flush()
    if sampled_frames != expected_samples:
        raise ValueError(
            f"semantic sample count {sampled_frames} does not match "
            f"acquisition fps-filter count {expected_samples}"
        )

    clock_started = time.perf_counter()
    clock_tool_source = Path("tools/recognize_public_text.swift").resolve()
    clock_anchors: dict[int, dict[str, Any]] = {}
    if args.clock_provider_mode == "macos-vision":
        clock_tool = clock_root / "recognize_public_text"
        try:
            compile_result = subprocess.run(
                ["swiftc", str(clock_tool_source), "-o", str(clock_tool)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "macos-vision clock mode requires swiftc; use "
                "--clock-provider-mode deferred on Linux"
            ) from error
    else:
        compile_result = None
    if compile_result is not None and compile_result.returncode == 0:
        ocr_result = subprocess.run(
            [str(clock_tool), *[str(clock_paths[key]) for key in sorted(clock_paths)]],
            capture_output=True,
            text=True,
            check=False,
        )
        if ocr_result.returncode == 0:
            for line in ocr_result.stdout.splitlines():
                payload = json.loads(line)
                match = re.search(r"clock_(\d+)\.png$", str(payload.get("path", "")))
                if match is None:
                    continue
                output_pts = int(match.group(1))
                candidates = payload.get("candidates", [])
                texts = [
                    str(item.get("text", ""))
                    for item in candidates
                    if isinstance(item, dict)
                ]
                parsed = None
                parsed_confidence = 0.0
                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    time_match = re.search(
                        r"\b(\d):([0-5]\d)\b", str(item.get("text", ""))
                    )
                    if time_match is None:
                        continue
                    parsed = int(time_match.group(1)) * 60 + int(time_match.group(2))
                    parsed_confidence = float(item.get("confidence", 0.0))
                    break
                if parsed is not None and parsed_confidence > 0.0:
                    clock_anchors[output_pts] = {
                        "seconds_remaining": parsed,
                        "confidence": parsed_confidence,
                        "raw_text": texts,
                    }
    for record in records:
        output_pts = int(record["output_pts"])
        anchor_pts = output_pts - output_pts % 5
        anchor = clock_anchors.get(anchor_pts)
        if anchor is None:
            continue
        propagated = output_pts != anchor_pts
        record["public"]["clock"] = {
            "value": int(anchor["seconds_remaining"]),
            "valid": True,
            "confidence": float(anchor["confidence"]) * (0.98 if propagated else 1.0),
            "raw_text": anchor["raw_text"],
            "evidence": (
                "native_vision_current_clock_crop"
                if not propagated
                else "native_vision_anchor_within_same_half_second"
            ),
            "anchor_output_pts": anchor_pts,
            "media_elapsed_ms_label_only": record["timestamp_ms"],
        }
    clock_seconds = time.perf_counter() - clock_started
    clock_temporary.cleanup()

    events = _event_rows(records, identity_resolver=identity)
    events_by_timestamp: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        events_by_timestamp.setdefault(int(event["timestamp_ms"]), []).append(event)
    for record in records:
        record["offline_evidence"]["play_events"] = events_by_timestamp.get(
            int(record["timestamp_ms"]), []
        )

    neutral_path = output / "neutral_sequence.jsonl.gz"
    _atomic_gzip_jsonl(neutral_path, records)
    actor_stride = round(args.sample_hz / args.actor_hz)
    actor_paths, actor_counts = _write_raw_actor_trajectories(
        output,
        records,
        actor_stride=actor_stride,
        mode=args.raw_actor_mode,
    )
    events_path = output / "offline_play_events.json"
    _atomic_json(events_path, events)

    hud_counts: Counter[str] = Counter()
    detection_counts: Counter[str] = Counter()
    identity_valid = 0
    hp_valid = 0
    for record in records:
        for player in ("0", "1"):
            state = record["offline_privileged_hud"][player]
            hud_counts[f"p{player}_complete"] += int(state["complete_valid"])
            hud_counts[f"p{player}_hand_slots_valid"] += sum(
                int(item["valid"]) for item in state["hand"]
            )
            hud_counts[f"p{player}_next_valid"] += int(state["next_card"]["valid"])
            hud_counts[f"p{player}_elixir_valid"] += int(state["elixir"]["valid"])
        for entity in record["public"]["entities"]:
            detection_counts[entity["visual_class"]] += 1
            identity_valid += int(entity["identity"]["valid"])
            hp_valid += int(entity["hp_valid"])

    total_wall = time.perf_counter() - started_wall
    total_cpu = time.process_time() - started_cpu
    clock_valid_frames = sum(
        int(record["public"]["clock"]["valid"]) for record in records
    )
    card_weight_path = (
        args.card_embedding_weight.resolve()
        if args.card_embedding_weight is not None
        else Path(torch.hub.get_dir())
        / "checkpoints"
        / "mobilenet_v3_small-047dcff4.pth"
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "source": {
            "video_id": source_id,
            "video_path": str(source),
            "video_bytes": source.stat().st_size,
            "video_sha256": _sha256(source),
            "acquisition_manifest": str(source_manifest),
            "acquisition_manifest_sha256": _sha256(source_manifest),
            "permission_basis": "user_attested_channel_owner_approval",
            "permission_attested_on": "2026-08-17",
        },
        "sampling": {
            "source_fps": source_fps,
            "source_frames": source_frames,
            "duration_seconds": duration_seconds,
            "detector_and_event_hz": args.sample_hz,
            "actor_trajectory_hz": args.actor_hz,
            "sampled_frames": sampled_frames,
            "decoded_source_frames": decoded_source_frames,
            "output_time_base": acquisition_decode["output_time_base"],
            "source_time_base": acquisition["source_media"]["source_time_base"],
            "first_output_pts": 0,
            "last_output_pts": sampled_frames - 1,
            "output_pts_contiguous": True,
            "acquisition_frame_index_sha256": acquisition_decode["index"]["sha256"],
        },
        "artifacts": {
            "neutral_sequence": {
                "path": str(neutral_path),
                "sha256": _sha256(neutral_path),
                "rows": len(records),
            },
            "actor_trajectories": [
                {
                    "actor_id": actor_id,
                    "path": str(path),
                    "sha256": _sha256(path),
                    "rows": actor_counts[str(actor_id)],
                }
                for actor_id, path in enumerate(actor_paths)
            ],
            "offline_play_events": {
                "path": str(events_path),
                "sha256": _sha256(events_path),
                "rows": len(events),
            },
        },
        "coverage": {
            "hud": dict(sorted(hud_counts.items())),
            "hud_denominators": {
                "frames_per_player": len(records),
                "hand_slots_per_player": len(records) * 4,
            },
            "clock_valid_frames": clock_valid_frames,
            "detections": sum(detection_counts.values()),
            "raw_detector_proposals": raw_detector_proposals,
            "filtered_non_entity_proposals": filtered_non_entity_proposals,
            "detection_class_counts": dict(sorted(detection_counts.items())),
            "typed_identity_valid": identity_valid,
            "hp_valid": hp_valid,
            "status_valid": 0,
            "projectile_target_valid": 0,
            "play_events": len(events),
            "play_events_valid": sum(int(row["play_valid"]) for row in events),
            "play_event_identity_valid": sum(
                int(row["identity_valid"]) for row in events
            ),
            "play_event_placement_valid": sum(
                int(row["placement_valid"]) for row in events
            ),
        },
        "leakage_contract": {
            "raw_frames_in_actor_artifacts": 0,
            "opponent_hud_in_actor_artifacts": 0,
            "simulator_state_inputs": 0,
            "exact_simulator_masks": 0,
            "event_labels_are_offline_only": True,
            "public_masks_depend_on_labels": False,
            "same_split_group_for_both_actors": True,
        },
        "models": {
            "detector_weights": [
                {"path": str(path), "sha256": _sha256(path)} for path in weights
            ],
            "vocabulary_manifest_sha256": identity.manifest_sha256,
            "device": args.device,
            "batch_size": args.batch_size,
            "card_identity_head": {
                "architecture": "torchvision_mobilenet_v3_small_imagenet_embedding",
                "torchvision_version": torchvision.__version__,
                "weights_path": str(card_weight_path),
                "weights_sha256": _sha256(card_weight_path),
                "hand_decision_minimum_cosine": 0.72,
                "next_decision_minimum_cosine": 0.70,
                "decision_minimum_margin": 0.035,
                "preprocess_backend": args.card_preprocess_backend,
                "preprocess_workers": hud.card_preprocess_workers,
            },
            "raw_actor_mode": args.raw_actor_mode,
            "elixir_head": "current_frame_public_magenta_bar_fill",
            "clock_head": (
                {
                    "implementation": "macos_vision_accurate_text_recognition",
                    "source_path": str(clock_tool_source),
                    "source_sha256": _sha256(clock_tool_source),
                    "anchor_stride_frames": 5,
                    "anchors_valid": len(clock_anchors),
                }
                if args.clock_provider_mode == "macos-vision"
                else {
                    "implementation": "external_linux_adapter_deferred",
                    "anchor_stride_frames": 5,
                    "anchors_valid": 0,
                    "requires_postprocess_before_publication": True,
                }
            ),
            "status_head": "unavailable_fail_closed",
            "projectile_target_head": "unavailable_fail_closed",
        },
        "timing_seconds": {
            "acquisition_download": acquisition["acquisition"]["performance"][
                "wall_seconds"
            ],
            "acquisition_standalone_10hz_decode_reference": acquisition_decode[
                "performance"
            ]["wall_seconds"],
            "detector_model_load": model_load_seconds,
            "hud_model_load": hud_model_load_seconds,
            "video_decode": decode_seconds,
            "hud_current_frame_matching": hud_seconds,
            "clock_provider": clock_seconds,
            "arena_detector": detector_seconds,
            "serialization_and_other": max(
                0.0,
                total_wall
                - model_load_seconds
                - hud_model_load_seconds
                - decode_seconds
                - hud_seconds
                - clock_seconds
                - detector_seconds,
            ),
            "total_wall": total_wall,
            "total_cpu": total_cpu,
        },
        "resources": {
            "max_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "mps_peak_current_allocated_bytes": mps_peak,
        },
        "throughput": {
            "sampled_frames_per_second": sampled_frames / total_wall,
            "detector_frames_per_second": sampled_frames / detector_seconds,
            "end_to_end_games_per_hour": 3600.0 / total_wall,
            "download_plus_semantic_games_per_hour": 3600.0
            / (
                total_wall
                + float(acquisition["acquisition"]["performance"]["wall_seconds"])
            ),
            "detector_limited_games_per_hour": 3600.0 / detector_seconds,
            "decode_limited_games_per_hour": 3600.0
            / float(acquisition_decode["performance"]["wall_seconds"]),
            "hud_limited_games_per_hour": 3600.0 / hud_seconds,
        },
        "limitations": [
            "spectator HUD card-family embeddings have bounded canary validation but no held-out calibration",
            (
                "clock OCR uses 2 Hz native Vision anchors with within-half-second "
                "propagation; missing anchors fail closed"
                if args.clock_provider_mode == "macos-vision"
                else "clock head is deferred and this intermediate artifact is not publishable"
            ),
            "detector visual vocabulary is April 2024 and lacks current-client coverage",
            "status durations and projectile targets fail closed",
            "deployment events are offline temporal labels, not actor inputs",
            "public masks fail closed to no-op until complete camera-only legality is proven",
        ],
    }
    manifest_path = output / "manifest.json"
    _atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "sha256": _sha256(manifest_path),
                "throughput": manifest["throughput"],
                "coverage": manifest["coverage"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
