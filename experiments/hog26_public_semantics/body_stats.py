"""Public physical descriptors for individual visible bodies, never parent cards."""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from clasher.balance import apply_character_overrides
from clasher.card_types import CardStatsCompat
from clasher.data import CardDataLoader
from clasher.factory.card_factory import card_from_gamedata
from clasher.gamedata_normalization import build_object_registry
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.rl.structured_obs import _crown_tower_observation_stats

STAT_NAMES = ("base_hp", "base_direct_dps", "base_attack_rate", "base_flying",
              "targets_air", "targets_ground", "targets_buildings_only", "base_shield_hp")
STATIC_INDICES = (23, 24, 25, 26, 30)


@dataclass(frozen=True)
class BodyTable:
    vocabulary: tuple[str, ...]
    values: np.ndarray
    confidence: np.ndarray
    expected_static: np.ndarray
    resolved: np.ndarray
    crown_ids: tuple[int, int]
    records: tuple[dict, ...]
    source_hashes: dict[str, str]


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def descriptor(stats, character):
    """Read one body's primary properties; do not walk spawned children."""
    hp = number(getattr(stats, "hitpoints", None))
    damage = number(getattr(stats, "damage", None))
    period = number(getattr(stats, "hit_speed", None))
    period_known = period is not None and period > 0
    dps = damage * 1000 / period if damage is not None and period_known else None
    rate = 1000 / period if period_known else None
    flying = number(character.get("flyingHeight", 0))
    shield = number(character.get("shieldHitpoints", 0))
    targeting = getattr(getattr(stats, "_card_def", None), "targeting", None)
    planes = (None, None, None) if targeting is None else (
        float(targeting.can_target_air()), float(targeting.can_target_ground()),
        float(targeting.buildings_only()),
    )
    raw = (hp, dps, rate, None if flying is None else float(flying > 0), *planes, shield)
    scales = (10000.0, 1000.0, 4.0, 1.0, 1.0, 1.0, 1.0, 1000.0)
    values = np.array([0.0 if value is None else np.clip(value / scale, 0, 1)
                       for value, scale in zip(raw, scales, strict=True)], dtype=np.float32)
    confidence = np.array([value is not None for value in raw], dtype=np.float32)
    clipped = [name for name, value, scale in zip(STAT_NAMES, raw, scales, strict=True)
               if value is not None and value > scale]
    return values, confidence, {"raw": dict(zip(STAT_NAMES, raw, strict=True)), "clipped_fields": clipped}


def static_projection(stats):
    speed = float(getattr(stats, "speed", 0) or 0)
    return np.array([
        np.clip(math.log1p(abs(speed)) / math.log1p(1000), 0, 1),
        np.clip(float(getattr(stats, "range", 0) or 0) / 12, 0, 1),
        np.clip(float(getattr(stats, "sight_range", 0) or 0) / 12, 0, 1),
        np.clip(float(getattr(stats, "collision_radius", 0) or 0) / 3, 0, 1),
        np.clip(math.log1p(max(0, float(getattr(stats, "damage", 0) or 0))) / 8, 0, 1),
    ], dtype=np.float32)


def compile_body_table(vocabulary):
    vocabulary = tuple(vocabulary)
    base = load_current_client_typed_vocabulary()
    if vocabulary[:len(base.token_names)] != tuple(base.token_names):
        raise ValueError("body table vocabulary prefix differs")
    loader = CardDataLoader()
    definitions = {d.name: d for d in loader.load_card_definitions().values()}
    registry = build_object_registry({"cards": [d.raw for d in definitions.values()]})
    lookup = {name: i for i, name in enumerate(vocabulary)}
    candidates = {}
    for name, payload in registry.items():
        namespace = "building_body" if str(payload.get("source", "")).startswith("buildings") else "troop_body"
        token = lookup.get(namespace + ":" + name, base.resolve(name, namespace))
        if token > 1:
            candidates.setdefault(token, []).append(name)
    towers = _crown_tower_observation_stats()
    values = np.zeros((len(vocabulary), len(STAT_NAMES)), dtype=np.float32)
    confidence = np.zeros_like(values)
    expected = np.zeros((len(vocabulary), len(STATIC_INDICES)), dtype=np.float32)
    resolved = np.zeros(len(vocabulary), dtype=bool)
    records = []
    for token, name in enumerate(vocabulary):
        namespace, separator, canonical = name.partition(":")
        if not separator or namespace not in {"troop_body", "building_body", "tower"}:
            continue
        origins = candidates.get(token, [])
        if namespace == "tower" and canonical in towers:
            stats = towers[canonical]
            character = getattr(stats, "summon_character_data", None) or {}
            origin = "existing crown-tower helper"
        elif len(origins) == 1:
            character = apply_character_overrides(canonical, dict(registry[origins[0]]))
            entry = {"id": 0, "name": canonical, "manaCost": 0, "rarity": "Common",
                     "tidType": "TID_CARD_TYPE_BUILDING" if namespace == "building_body" else "TID_CARD_TYPE_CHARACTER",
                     "summonCharacterData": character}
            stats = CardStatsCompat.from_card_definition(card_from_gamedata(entry))
            origin = origins[0]
        else:
            records.append({"token_id": token, "token": name, "resolved": False,
                            "reason": "ambiguous-public-object" if origins else "missing-public-object",
                            "candidates": origins})
            continue
        vector, known, details = descriptor(stats, character)
        values[token], confidence[token], expected[token] = vector, known, static_projection(stats)
        resolved[token] = True
        records.append({"token_id": token, "token": name, "resolved": True, "origin": origin, **details})
    for array in (values, confidence, expected, resolved):
        array.flags.writeable = False
    root = Path(__file__).resolve().parents[2]
    paths = [loader.data_file, Path(__file__), *(root / p for p in (
        "src/clasher/data.py", "src/clasher/balance.py", "src/clasher/card_types.py",
        "src/clasher/gamedata_normalization.py", "src/clasher/factory/card_factory.py",
        "src/clasher/factory/mechanic_detector.py", "src/clasher/rl/structured_obs.py",
        "src/clasher/rl/simple_pytorch_backend.py"))]
    hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    hashes["typed_vocabulary_digest"] = base.sha256
    return BodyTable(vocabulary, values, confidence, expected, resolved,
                     (lookup["tower:Tower"], lookup["tower:KingTower"]), tuple(records), hashes)
