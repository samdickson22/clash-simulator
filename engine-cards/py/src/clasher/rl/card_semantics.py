from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from clasher.data import CardDataLoader

SEMANTIC_FEATURE_NAMES = (
    "elixir_cost",
    "is_troop",
    "is_building",
    "is_spell",
    "is_champion",
    "hitpoints",
    "damage",
    "dps",
    "attack_range",
    "sight_range",
    "movement_speed",
    "attack_frequency",
    "deploy_time",
    "collision_radius",
    "summon_count",
    "targets_ground",
    "targets_air",
    "targets_buildings_only",
    "is_flying",
    "has_projectile",
    "has_area_damage",
    "area_radius",
    "has_death_damage",
    "has_death_spawn",
    "has_charge_or_dash",
    "has_shield",
    "effect_duration",
    "spell_damage",
    "spell_radius",
    "has_stun_or_freeze",
    "has_slow",
    "has_knockback",
    "has_heal",
    "spawns_units",
    "has_building_damage_modifier",
    "mass",
)

# Semantic-v3 preserves the complete legacy 16-feature path and adds only
# mechanics that legacy metadata cannot express. DPS is retained because the
# legacy schema exposes damage and hit speed separately but not their product.
SEMANTIC_EXTRA_FEATURE_NAMES = (
    "dps",
    *SEMANTIC_FEATURE_NAMES[17:],
)
SEMANTIC_EXTRA_FEATURE_INDICES = tuple(
    SEMANTIC_FEATURE_NAMES.index(name) for name in SEMANTIC_EXTRA_FEATURE_NAMES
)


def _unit(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _walk_payload(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, list):
        for child in value:
            yield from _walk_payload(child)
        return
    if not isinstance(value, Mapping):
        return
    yield value
    for key, child in value.items():
        if key in {"evolvedSpellsData", "heroData"}:
            continue
        yield from _walk_payload(child)


def _max_payload_number(payloads: tuple[Mapping[str, Any], ...], *keys: str) -> float:
    return max(
        (abs(_number(payload.get(key))) for payload in payloads for key in keys),
        default=0.0,
    )


def _has_payload_key(payloads: tuple[Mapping[str, Any], ...], *fragments: str) -> bool:
    lowered = tuple(fragment.lower() for fragment in fragments)
    return any(
        any(fragment in str(key).lower() for fragment in lowered)
        and value not in {None, False, "", ()}
        for payload in payloads
        for key, value in payload.items()
        if not isinstance(value, (dict, list))
    )


def _payload_text_contains(
    payloads: tuple[Mapping[str, Any], ...], *fragments: str
) -> bool:
    lowered = tuple(fragment.lower() for fragment in fragments)
    return any(
        any(fragment in str(value).lower() for fragment in lowered)
        for payload in payloads
        for value in payload.values()
        if isinstance(value, str)
    )


@dataclass(frozen=True)
class CardSemanticProfile:
    name: str
    card_type: str
    role: str
    mana_cost: float
    vector: np.ndarray


def semantic_card_profile(
    name: str,
    *,
    loader: CardDataLoader | None = None,
) -> CardSemanticProfile:
    loader = loader or CardDataLoader()
    stats = loader.get_card(name)
    if stats is None:
        raise ValueError(f"unknown card {name!r}")
    raw = getattr(stats, "_raw_entry", {}) or {}
    payloads = tuple(_walk_payload(raw))
    kind = str(getattr(stats, "card_type", "") or "").lower()
    mana = _number(getattr(stats, "mana_cost", 0))
    hp = max(0.0, _number(getattr(stats, "hitpoints", 0)))
    damage = max(0.0, _number(getattr(stats, "damage", 0)))
    hit_speed = max(0.0, _number(getattr(stats, "hit_speed", 0)))
    summon_count = max(
        1.0,
        _number(getattr(stats, "summon_count", 0)),
        _max_payload_number(payloads, "summonNumber", "spawnCharacterCount"),
    )
    target_type = str(getattr(stats, "target_type", "") or "").upper()
    targets_air = "AIR" in target_type
    targets_buildings = "BUILDINGS" in target_type
    targets_ground = targets_buildings or "GROUND" in target_type
    flying_height = _max_payload_number(payloads, "flyingHeight")
    projectile_speed = max(
        _number(getattr(stats, "projectile_speed", 0)),
        _max_payload_number(payloads, "projectileSpeed"),
    )
    area_radius = max(
        _number(getattr(stats, "area_damage_radius", 0)),
        _number(getattr(stats, "projectile_splash_radius", 0)),
        _max_payload_number(
            payloads,
            "radius",
            "damageRadius",
            "deathDamageRadius",
            "projectileRadius",
        )
        / 1000.0,
    )
    duration_ms = _max_payload_number(
        payloads,
        "lifeDuration",
        "duration",
        "buffTime",
    )
    spell_damage = _max_payload_number(
        payloads,
        "damage",
        "damagePerSecond",
        "deathDamage",
    )
    spell_radius = _max_payload_number(
        payloads,
        "radius",
        "damageRadius",
        "projectileRadius",
    )
    mass = _max_payload_number(payloads, "mass")
    has_spawn = _has_payload_key(
        payloads,
        "spawncharacter",
        "deathspawn",
        "summonnumber",
    )
    has_unit_spawn = _has_payload_key(
        payloads,
        "spawncharactercount",
        "spawncharacterdata",
        "spawncharacter",
    )
    has_death_spawn = _has_payload_key(payloads, "deathspawn")
    has_area = area_radius > 0.0 and (
        kind == "spell"
        or _has_payload_key(payloads, "areadamage", "damageradius", "radius")
    )
    has_hard_control = _has_payload_key(
        payloads,
        "stun",
        "freeze",
        "pushback",
        "attract",
    ) or _payload_text_contains(payloads, "stun", "freeze")

    if kind == "spell":
        if has_unit_spawn:
            role = "spawn_spell"
        elif has_hard_control and duration_ms >= 1000.0:
            role = "control_spell"
        elif mana <= 2.0:
            role = "small_spell"
        else:
            role = "damage_spell"
    elif kind == "building":
        role = "siege" if _number(getattr(stats, "range", 0)) >= 8.0 else "building"
    elif targets_buildings:
        role = "building_target"
    elif hp >= 900.0:
        role = "tank"
    elif summon_count >= 3.0:
        role = "swarm"
    elif _number(getattr(stats, "range", 0)) >= 3.0:
        role = "ranged_support"
    else:
        role = "melee_support"

    dps = damage * 1000.0 / max(250.0, hit_speed) * summon_count
    vector = np.asarray(
        [
            _unit(mana / 10.0),
            float(kind == "troop"),
            float(kind == "building"),
            float(kind == "spell"),
            float(kind == "champion"),
            _unit(math.log1p(hp) / 9.0),
            _unit(math.log1p(damage) / 8.0),
            _unit(math.log1p(max(0.0, dps)) / 9.0),
            _unit(_number(getattr(stats, "range", 0)) / 12.0),
            _unit(_number(getattr(stats, "sight_range", 0)) / 12.0),
            _unit(_number(getattr(stats, "speed", 0)) / 200.0),
            _unit(1000.0 / max(250.0, hit_speed) / 4.0) if hit_speed else 0.0,
            _unit(_number(getattr(stats, "deploy_time", 0)) / 5000.0),
            _unit(_number(getattr(stats, "collision_radius", 0)) / 3.0),
            _unit(summon_count / 20.0),
            float(targets_ground),
            float(targets_air),
            float(targets_buildings),
            float(flying_height > 0.0),
            float(projectile_speed > 0.0),
            float(has_area),
            _unit(area_radius / 6.0),
            float(_has_payload_key(payloads, "deathdamage")),
            float(has_death_spawn),
            float(_has_payload_key(payloads, "charge", "jump", "dash")),
            float(_has_payload_key(payloads, "shield")),
            _unit(duration_ms / 10000.0),
            _unit(math.log1p(spell_damage) / 8.0),
            _unit(spell_radius / 6000.0),
            float(_has_payload_key(payloads, "stun", "freeze")),
            float(_has_payload_key(payloads, "slow", "speedmultiplier")),
            float(_has_payload_key(payloads, "pushback", "attract")),
            float(_has_payload_key(payloads, "heal")),
            float(has_spawn),
            float(_has_payload_key(payloads, "buildingdamagepercent")),
            _unit(mass / 20.0),
        ],
        dtype=np.float32,
    )
    if vector.shape != (len(SEMANTIC_FEATURE_NAMES),):
        raise AssertionError("semantic card feature schema mismatch")
    return CardSemanticProfile(
        name=name,
        card_type=kind,
        role=role,
        mana_cost=mana,
        vector=vector,
    )


def semantic_distance(first: CardSemanticProfile, second: CardSemanticProfile) -> float:
    if first.role != second.role:
        return math.inf
    return float(np.linalg.norm(first.vector - second.vector))


def building_target_pressure_score(stats: Any) -> float:
    """Estimate offensive tower pressure from public card mechanics only.

    This is intentionally card-name agnostic. It distinguishes primary tower
    threats from low-damage building-targeting utility bodies while preserving
    a continuous relationship among Hog Rider, Giants, Balloon, Rams, and new
    cards with comparable mechanics.
    """

    if not bool(getattr(stats, "targets_only_buildings", False)):
        return 0.0
    damage = max(0.0, _number(getattr(stats, "damage", 0)))
    hit_speed = max(250.0, _number(getattr(stats, "hit_speed", 0)))
    hitpoints = max(0.0, _number(getattr(stats, "hitpoints", 0)))
    speed = max(0.0, _number(getattr(stats, "speed", 0)))
    attack_range = max(0.0, _number(getattr(stats, "range", 0)))
    dps = damage * 1000.0 / hit_speed
    survivability = 0.5 + hitpoints / 1000.0
    approach = 0.5 + speed / 60.0
    reach = 1.0 + attack_range / 10.0
    return float(dps * survivability * approach * reach)
