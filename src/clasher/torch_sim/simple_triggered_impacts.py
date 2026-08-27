"""Serialized triggered area and radial-impulse commands for the fast Gym.

This module is deliberately split at the production seam.  Setup compiles
Python game data into a bounded numeric table; runtime resolves a fixed event
tensor into commands and adapts those commands to :mod:`simple_effects` and
:mod:`simple_impulse`.  No card identity or Python mechanic object enters the
runtime path.

Signed radial displacement follows :mod:`simple_impulse`: positive values
push away from the selected center and negative values pull toward it.  A
target-speed attraction descriptor retains the two serialized percentages
separately because native truncates after each multiplication.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from numbers import Real
from typing import Any

import torch

from clasher.balance import tournament_spell_stat
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.gamedata_normalization import serialized_hit_planes

from .catalog import EFFECT_OPCODE, MECHANIC_OPCODE, CardKindOpcode, TensorCardCatalog
from .simple_effects import (
    FAST_EFFECT_AREA,
    FAST_STATUS_NONE,
    FAST_STATUS_SLOW,
    FAST_STATUS_STUN,
    FastEffectState,
)
from .simple_impulse import FastRadialImpulseInputs

FAST_TRIGGER_NONE = 0
FAST_TRIGGER_DEPLOY_COMPLETE = 1
FAST_TRIGGER_ATTACK_COMMIT = 2
FAST_TRIGGER_IMPACT = 3
FAST_TRIGGER_DEATH = 4

FAST_CENTER_NONE = 0
FAST_CENTER_SOURCE = 1
FAST_CENTER_TARGET = 2
FAST_CENTER_SELF = 3

FAST_RECIPIENT_NONE = 0
FAST_RECIPIENT_ENEMY_AREA = 1
FAST_RECIPIENT_SELF = 2

FAST_ORIGIN_NONE = 0
FAST_ORIGIN_RAW_PROJECTILE = 1
FAST_ORIGIN_MECHANIC = 2
FAST_ORIGIN_EFFECT = 3

FAST_TRIGGER_TICK_MS = 50


def _ticks(milliseconds: float, *, minimum: int = 0) -> int:
    return max(minimum, math.ceil(milliseconds / FAST_TRIGGER_TICK_MS))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _integer(value: object) -> int | None:
    number = _number(value)
    if number is None or number != round(number):
        return None
    return round(number)


def _scaled_damage(card: object, raw_damage: object) -> float | None:
    damage = _integer(raw_damage)
    scaler = getattr(card, "get_scaled_stat", None)
    if damage is None or damage < 0 or not callable(scaler):
        return None
    scaled = scaler(damage)
    result = _number(scaled)
    return result if result is not None and result >= 0.0 else None


def _percent_multiplier(payload: dict[str, Any], field: str) -> float | None:
    value = _number(payload.get(field, 0.0))
    if value is None:
        return None
    return max(0.0, 1.0 + value / 100.0)


def _building_multiplier(payload: dict[str, Any]) -> float | None:
    if "buildingDamagePercent" not in payload:
        return 1.0
    value = _number(payload.get("buildingDamagePercent"))
    return None if value is None else max(0.0, value / 100.0)


def _tower_multiplier(
    card_name: str,
    payload: dict[str, Any],
    damage: float,
) -> float | None:
    explicit = tournament_spell_stat(card_name, "crown_tower_damage")
    if explicit is not None and damage > 0.0:
        return max(0.0, float(explicit) / damage)
    return _percent_multiplier(payload, "crownTowerDamagePercent")


def _status(payload: dict[str, Any], duration_ms: object) -> tuple[int, int] | None:
    duration = _integer(duration_ms)
    if duration is None or duration < 0:
        return None
    speed = _number(payload.get("speedMultiplier", 0.0))
    attack = _number(payload.get("hitSpeedMultiplier", 0.0))
    spawn = _number(payload.get("spawnSpeedMultiplier", 0.0))
    if speed is None or attack is None or spawn is None:
        return None
    if duration == 0 or min(speed, attack, spawn) >= 0.0:
        return FAST_STATUS_NONE, 0
    kind = (
        FAST_STATUS_STUN
        if speed <= -100.0 and attack <= -100.0 and spawn <= -100.0
        else FAST_STATUS_SLOW
    )
    return kind, _ticks(duration, minimum=1)


@dataclass(frozen=True)
class _Descriptor:
    trigger: int
    center: int
    recipient: int
    origin: int
    origin_opcode: int
    damage: float = 0.0
    radius_units: int = 0
    status_kind: int = FAST_STATUS_NONE
    status_duration_ticks: int = 0
    lifetime_ticks: int = 1
    damage_interval_ticks: int = 1
    initial_damage_delay_ticks: int = 0
    damage_on_spawn: bool = True
    max_damage_hits: int = 1
    status_interval_ticks: int = 1
    initial_status_delay_ticks: int = 0
    max_status_scans: int = 1
    hits_air: bool = True
    hits_ground: bool = True
    affects_hidden: bool = False
    tower_damage_multiplier: float = 1.0
    building_damage_multiplier: float = 1.0
    impulse_units: int = 0
    impulse_push_speed_factor: int = 0
    impulse_attract_percentage: int = 0
    impulse_interval_ticks: int = 1
    impulse_scan_count: int = 1


def _valid_descriptor(value: _Descriptor) -> bool:
    valid_codes = (
        value.trigger
        in {
            FAST_TRIGGER_DEPLOY_COMPLETE,
            FAST_TRIGGER_ATTACK_COMMIT,
            FAST_TRIGGER_IMPACT,
            FAST_TRIGGER_DEATH,
        }
        and value.center in {FAST_CENTER_SOURCE, FAST_CENTER_TARGET, FAST_CENTER_SELF}
        and value.recipient in {FAST_RECIPIENT_ENEMY_AREA, FAST_RECIPIENT_SELF}
    )
    has_payload = (
        value.damage > 0.0
        or value.status_kind != FAST_STATUS_NONE
        or value.impulse_units != 0
        or (
            value.impulse_push_speed_factor > 0 and value.impulse_attract_percentage > 0
        )
    )
    area_valid = value.recipient == FAST_RECIPIENT_SELF or value.radius_units > 0
    return bool(
        valid_codes
        and has_payload
        and area_valid
        and value.damage >= 0.0
        and value.status_duration_ticks >= 0
        and value.lifetime_ticks > 0
        and value.damage_interval_ticks > 0
        and value.initial_damage_delay_ticks >= 0
        and value.max_damage_hits >= 0
        and value.status_interval_ticks > 0
        and value.initial_status_delay_ticks >= 0
        and value.max_status_scans >= 0
        and (
            value.hits_air
            or value.hits_ground
            or value.recipient == FAST_RECIPIENT_SELF
        )
        and value.tower_damage_multiplier >= 0.0
        and value.building_damage_multiplier >= 0.0
        and value.impulse_interval_ticks > 0
        and value.impulse_scan_count > 0
    )


def _area_descriptor(
    *,
    card_name: str,
    card: object,
    area: dict[str, Any],
    trigger: int,
    center: int,
    origin: int,
    origin_opcode: int,
    spell_raw: dict[str, Any] | None = None,
) -> _Descriptor | None:
    radius = _integer(area.get("radius"))
    life_ms = _integer(area.get("lifeDuration", 1))
    effect_ms = _integer(area.get("hitSpeed", FAST_TRIGGER_TICK_MS))
    buff_ms = _integer(area.get("buffTime", 0))
    buff = area.get("buffData") or {}
    if (
        radius is None
        or life_ms is None
        or effect_ms is None
        or buff_ms is None
        or not isinstance(buff, dict)
        or radius <= 0
        or life_ms < 0
        or effect_ms <= 0
    ):
        raise ValueError("malformed serialized area payload")

    status = _status(buff, buff_ms)
    if status is None:
        raise ValueError("malformed serialized status payload")
    status_kind, status_ticks = status
    hits_air, hits_ground = serialized_hit_planes(area)
    duration_ticks = _ticks(max(1, life_ms), minimum=1)
    effect_interval = _ticks(effect_ms, minimum=1)
    status_scans = max(1, duration_ticks // effect_interval)
    impulse_scans = max(1, (max(1, life_ms) - 1) // effect_ms)

    raw_damage = area.get("damage", 0)
    damage = _scaled_damage(card, raw_damage)
    if damage is None:
        raise ValueError("malformed serialized area damage")
    damage_interval = 1
    initial_damage_delay = 0
    damage_on_spawn = damage > 0.0
    max_damage_hits = int(damage > 0.0)
    tower_payload: dict[str, Any] = area
    building_payload: dict[str, Any] = area

    attract = _integer(buff.get("attractPercentage", 0))
    push_factor = _integer(buff.get("pushSpeedFactor", 0))
    if attract is None or push_factor is None or attract < 0 or push_factor < 0:
        raise ValueError("malformed serialized attraction payload")

    if spell_raw is not None:
        spell = create_spell_from_json(spell_raw)
        spell_damage = _number(
            getattr(spell, "damage_per_hit", 0.0)
            or getattr(spell, "damage", 0.0)
            or 0.0
        )
        if spell_damage is None or spell_damage < 0.0:
            raise ValueError("malformed serialized spell area damage")
        damage = spell_damage
        interval_s = _number(getattr(spell, "damage_tick_interval", 0.0))
        delay_s = _number(getattr(spell, "initial_damage_delay", 0.0))
        declared_hits = _integer(getattr(spell, "max_damage_ticks", 0))
        if interval_s is None or delay_s is None or declared_hits is None:
            raise ValueError("malformed serialized spell area timing")
        damage_interval = _ticks(round(interval_s * 1000.0), minimum=1)
        # Allocation and the first effect advance share a native frame.
        initial_damage_delay = max(
            0,
            _ticks(round(delay_s * 1000.0)) - 1,
        )
        max_damage_hits = declared_hits
        damage_on_spawn = bool(getattr(spell, "damage_on_spawn", False))
        tower_payload = buff
        building_payload = buff

    tower = _tower_multiplier(card_name, tower_payload, damage)
    building = _building_multiplier(building_payload)
    if tower is None or building is None:
        raise ValueError("malformed serialized area damage scale")
    descriptor = _Descriptor(
        trigger=trigger,
        center=center,
        recipient=FAST_RECIPIENT_ENEMY_AREA,
        origin=origin,
        origin_opcode=origin_opcode,
        damage=damage,
        radius_units=radius,
        status_kind=status_kind,
        status_duration_ticks=status_ticks,
        lifetime_ticks=duration_ticks,
        damage_interval_ticks=damage_interval,
        initial_damage_delay_ticks=initial_damage_delay,
        damage_on_spawn=damage_on_spawn,
        max_damage_hits=max_damage_hits,
        status_interval_ticks=effect_interval,
        initial_status_delay_ticks=0,
        max_status_scans=status_scans if status_kind != FAST_STATUS_NONE else 0,
        hits_air=hits_air,
        hits_ground=hits_ground,
        affects_hidden=bool(area.get("affectsHidden", False)),
        tower_damage_multiplier=tower,
        building_damage_multiplier=building,
        impulse_push_speed_factor=push_factor,
        impulse_attract_percentage=attract,
        impulse_interval_ticks=effect_interval,
        impulse_scan_count=impulse_scans,
    )
    return descriptor if _valid_descriptor(descriptor) else None


def _projectile_descriptor(
    *,
    card_name: str,
    card: object,
    projectile: dict[str, Any],
    trigger: int,
    origin: int,
    origin_opcode: int,
) -> _Descriptor | None:
    push = _integer(projectile.get("pushback", 0))
    if push is None or push < 0:
        raise ValueError("malformed serialized projectile pushback")
    if push == 0:
        return None
    radius = _integer(projectile.get("radius", 0))
    damage = _scaled_damage(card, projectile.get("damage", 0))
    buff = projectile.get("targetBuffData") or {}
    buff_ms = _integer(projectile.get("buffTime", 0))
    if (
        radius is None
        or radius <= 0
        or damage is None
        or not isinstance(buff, dict)
        or buff_ms is None
    ):
        raise ValueError("malformed serialized projectile payload")
    status = _status(buff, buff_ms)
    tower = _tower_multiplier(card_name, projectile, damage)
    building = _building_multiplier(projectile)
    if status is None or tower is None or building is None:
        raise ValueError("malformed serialized projectile modifiers")
    hits_air, hits_ground = serialized_hit_planes(projectile)
    descriptor = _Descriptor(
        trigger=trigger,
        center=FAST_CENTER_TARGET,
        recipient=FAST_RECIPIENT_ENEMY_AREA,
        origin=origin,
        origin_opcode=origin_opcode,
        damage=damage,
        radius_units=radius,
        status_kind=status[0],
        status_duration_ticks=status[1],
        hits_air=hits_air,
        hits_ground=hits_ground,
        affects_hidden=bool(projectile.get("affectsHidden", False)),
        tower_damage_multiplier=tower,
        building_damage_multiplier=building,
        impulse_units=push,
    )
    if not _valid_descriptor(descriptor):
        raise ValueError("invalid serialized projectile descriptor")
    return descriptor


def _parameter(
    catalog: TensorCardCatalog,
    card_id: int,
    slot: int,
    name: str,
) -> float | None:
    if name not in catalog.mechanic_parameter_names:
        return None
    parameter = catalog.mechanic_parameter_names.index(name)
    return _number(catalog.mechanic_parameters[card_id, slot, parameter].item())


@dataclass(frozen=True)
class FastTriggeredImpactCatalog:
    """Bounded descriptor table indexed by ``[card, descriptor]``.

    Malformed or duplicate cards retain diagnostics but have zero descriptor
    count and neutral payload tensors.  ``supported`` is the sole runtime
    admission signal.
    """

    device: torch.device
    supported: torch.Tensor
    malformed: torch.Tensor
    duplicate: torch.Tensor
    descriptor_count: torch.Tensor
    trigger: torch.Tensor
    center: torch.Tensor
    recipient: torch.Tensor
    origin: torch.Tensor
    origin_opcode: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    lifetime_ticks: torch.Tensor
    damage_interval_ticks: torch.Tensor
    initial_damage_delay_ticks: torch.Tensor
    damage_on_spawn: torch.Tensor
    max_damage_hits: torch.Tensor
    status_interval_ticks: torch.Tensor
    initial_status_delay_ticks: torch.Tensor
    max_status_scans: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    impulse_units: torch.Tensor
    impulse_push_speed_factor: torch.Tensor
    impulse_attract_percentage: torch.Tensor
    impulse_interval_ticks: torch.Tensor
    impulse_scan_count: torch.Tensor

    @property
    def card_capacity(self) -> int:
        return int(self.supported.shape[0])

    @property
    def max_descriptors(self) -> int:
        return int(self.trigger.shape[1])

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> FastTriggeredImpactCatalog:
        definitions = loader.load_card_definitions()
        per_card: list[list[_Descriptor]] = [[] for _ in catalog.names]
        malformed_cards = [False] * len(catalog.names)
        duplicate_cards = [False] * len(catalog.names)
        recognized_mechanics = {
            int(MECHANIC_OPCODE[name])
            for name in (
                "AttackRecoil",
                "DeathAreaEffect",
                "DeathDamage",
                "MegaKnightSlam",
                "SpawnAreaEffect",
                "SpawnPushback",
            )
        }

        for card_id, catalog_name in enumerate(catalog.names[1:], start=1):
            resolved = resolve_card_name(catalog_name, definitions)
            definition = definitions.get(resolved)
            card = loader.get_card(catalog_name)
            raw = {} if card is None else getattr(card, "_raw_entry", {}) or {}
            character = (
                raw.get("summonCharacterData") or raw.get("summonSpellData") or {}
            )
            if definition is None or card is None or not isinstance(character, dict):
                malformed_cards[card_id] = True
                continue

            tensor_opcodes = [
                int(value)
                for value in catalog.mechanic_opcode[card_id].detach().cpu().tolist()
                if int(value) in recognized_mechanics
            ]
            if len(tensor_opcodes) != len(set(tensor_opcodes)):
                duplicate_cards[card_id] = True
                malformed_cards[card_id] = True
                continue
            slots_by_opcode = {
                opcode: [
                    slot
                    for slot, value in enumerate(
                        catalog.mechanic_opcode[card_id].detach().cpu().tolist()
                    )
                    if int(value) == opcode
                ]
                for opcode in recognized_mechanics
            }
            candidates: list[_Descriptor] = []
            try:
                for mechanic in definition.mechanics:
                    mechanic_name = type(mechanic).__name__
                    opcode = MECHANIC_OPCODE.get(mechanic_name)
                    if opcode is None or int(opcode) not in recognized_mechanics:
                        continue
                    slots = slots_by_opcode[int(opcode)]
                    if len(slots) != 1:
                        raise ValueError("mechanic/catalog source mismatch")
                    slot = slots[0]
                    nested = bool(catalog.mechanic_nested_payload[card_id, slot].item())

                    if mechanic_name == "AttackRecoil":
                        raw_units = _integer(character.get("attackPushback"))
                        parameter = _parameter(
                            catalog, card_id, slot, "recoil_distance"
                        )
                        if (
                            raw_units is None
                            or raw_units <= 0
                            or parameter is None
                            or not math.isclose(
                                parameter, raw_units / 1000.0, abs_tol=1e-9
                            )
                        ):
                            raise ValueError("malformed recoil source")
                        candidates.append(
                            _Descriptor(
                                trigger=FAST_TRIGGER_ATTACK_COMMIT,
                                center=FAST_CENTER_TARGET,
                                recipient=FAST_RECIPIENT_SELF,
                                origin=FAST_ORIGIN_MECHANIC,
                                origin_opcode=int(opcode),
                                impulse_units=raw_units,
                            )
                        )
                    elif mechanic_name == "SpawnAreaEffect":
                        if not nested:
                            raise ValueError("spawn area lost nested payload")
                        area = getattr(mechanic, "area_data", None)
                        if not isinstance(area, dict):
                            raise ValueError("malformed spawn area")
                        descriptor = _area_descriptor(
                            card_name=catalog_name,
                            card=card,
                            area=area,
                            trigger=FAST_TRIGGER_DEPLOY_COMPLETE,
                            center=FAST_CENTER_SELF,
                            origin=FAST_ORIGIN_MECHANIC,
                            origin_opcode=int(opcode),
                        )
                        if descriptor is not None:
                            candidates.append(descriptor)
                    elif mechanic_name == "DeathAreaEffect":
                        if not nested:
                            raise ValueError("death area lost nested payload")
                        area = getattr(mechanic, "area_data", None)
                        if not isinstance(area, dict):
                            raise ValueError("malformed death area")
                        # Action graphs can delay an effect through a spawned
                        # container.  They are well-formed but belong to the
                        # scheduled-spawn owner, not this immediate trigger.
                        if area.get("onStartingActionData"):
                            continue
                        descriptor = _area_descriptor(
                            card_name=catalog_name,
                            card=card,
                            area=area,
                            trigger=FAST_TRIGGER_DEATH,
                            center=FAST_CENTER_SELF,
                            origin=FAST_ORIGIN_MECHANIC,
                            origin_opcode=int(opcode),
                        )
                        if descriptor is not None:
                            candidates.append(descriptor)
                    elif mechanic_name == "DeathDamage":
                        radius = _number(getattr(mechanic, "radius_tiles", None))
                        raw_damage = _integer(getattr(mechanic, "damage", None))
                        push = _number(getattr(mechanic, "knockback_distance", None))
                        damage = _scaled_damage(card, raw_damage)
                        if (
                            radius is None
                            or radius <= 0.0
                            or raw_damage is None
                            or damage is None
                            or push is None
                            or push < 0.0
                        ):
                            raise ValueError("malformed death damage")
                        descriptor = _Descriptor(
                            trigger=FAST_TRIGGER_DEATH,
                            center=FAST_CENTER_SELF,
                            recipient=FAST_RECIPIENT_ENEMY_AREA,
                            origin=FAST_ORIGIN_MECHANIC,
                            origin_opcode=int(opcode),
                            damage=damage,
                            radius_units=round(radius * 1000.0),
                            hits_air=bool(getattr(mechanic, "hits_air", True)),
                            hits_ground=bool(getattr(mechanic, "hits_ground", True)),
                            impulse_units=round(push * 1000.0),
                        )
                        if not _valid_descriptor(descriptor):
                            raise ValueError("invalid death damage descriptor")
                        candidates.append(descriptor)
                    elif mechanic_name == "SpawnPushback":
                        radius = _number(getattr(mechanic, "radius_tiles", None))
                        distance = _number(getattr(mechanic, "distance_tiles", None))
                        if (
                            radius is None
                            or distance is None
                            or radius <= 0.0
                            or distance <= 0.0
                        ):
                            raise ValueError("malformed spawn pushback")
                        descriptor = _Descriptor(
                            trigger=FAST_TRIGGER_DEPLOY_COMPLETE,
                            center=FAST_CENTER_SELF,
                            recipient=FAST_RECIPIENT_ENEMY_AREA,
                            origin=FAST_ORIGIN_MECHANIC,
                            origin_opcode=int(opcode),
                            radius_units=round(radius * 1000.0),
                            hits_air=bool(getattr(mechanic, "hits_air", False)),
                            hits_ground=bool(getattr(mechanic, "hits_ground", True)),
                            impulse_units=round(distance * 1000.0),
                        )
                        if not _valid_descriptor(descriptor):
                            raise ValueError("invalid spawn pushback descriptor")
                        candidates.append(descriptor)
                    elif mechanic_name == "MegaKnightSlam":
                        projectile = raw.get("projectileData") or {}
                        if not isinstance(projectile, dict):
                            raise ValueError("malformed deploy projectile")
                        descriptor = _projectile_descriptor(
                            card_name=catalog_name,
                            card=card,
                            projectile=projectile,
                            trigger=FAST_TRIGGER_DEPLOY_COMPLETE,
                            origin=FAST_ORIGIN_MECHANIC,
                            origin_opcode=int(opcode),
                        )
                        if descriptor is None:
                            raise ValueError("deploy projectile lacks pushback")
                        candidates.append(
                            _Descriptor(
                                **{
                                    **vars(descriptor),
                                    "center": FAST_CENTER_SELF,
                                }
                            )
                        )

                if int(catalog.kind[card_id].item()) == int(CardKindOpcode.SPELL):
                    raw_projectile = raw.get("projectileData") or {}
                    if isinstance(raw_projectile, dict):
                        spell_projectile = raw_projectile
                        if int(spell_projectile.get("pushback", 0) or 0) > 0:
                            slots = [
                                slot
                                for slot, value in enumerate(
                                    catalog.effect_opcode[card_id]
                                    .detach()
                                    .cpu()
                                    .tolist()
                                )
                                if int(value) == int(EFFECT_OPCODE["ProjectileLaunch"])
                            ]
                            if len(slots) != 1:
                                raise ValueError("projectile effect source mismatch")
                            descriptor = _projectile_descriptor(
                                card_name=catalog_name,
                                card=card,
                                projectile=spell_projectile,
                                trigger=FAST_TRIGGER_IMPACT,
                                origin=FAST_ORIGIN_EFFECT,
                                origin_opcode=int(EFFECT_OPCODE["ProjectileLaunch"]),
                            )
                            if descriptor is not None:
                                candidates.append(descriptor)
                    area = raw.get("areaEffectObjectData") or {}
                    if isinstance(area, dict):
                        buff = area.get("buffData") or {}
                        if isinstance(buff, dict) and (
                            int(buff.get("attractPercentage", 0) or 0) > 0
                            or int(buff.get("pushSpeedFactor", 0) or 0) > 0
                        ):
                            effect_slots = [
                                slot
                                for slot, value in enumerate(
                                    catalog.effect_opcode[card_id]
                                    .detach()
                                    .cpu()
                                    .tolist()
                                )
                                if int(value) == int(EFFECT_OPCODE["PeriodicArea"])
                            ]
                            if len(effect_slots) != 1:
                                raise ValueError("periodic area source mismatch")
                            descriptor = _area_descriptor(
                                card_name=catalog_name,
                                card=card,
                                area=area,
                                trigger=FAST_TRIGGER_IMPACT,
                                center=FAST_CENTER_TARGET,
                                origin=FAST_ORIGIN_EFFECT,
                                origin_opcode=int(EFFECT_OPCODE["PeriodicArea"]),
                                spell_raw=raw,
                            )
                            if descriptor is not None:
                                candidates.append(descriptor)
                else:
                    raw_projectile = character.get("projectileData") or {}
                    if (
                        isinstance(raw_projectile, dict)
                        and int(raw_projectile.get("pushback", 0) or 0) > 0
                    ):
                        descriptor = _projectile_descriptor(
                            card_name=catalog_name,
                            card=card,
                            projectile=raw_projectile,
                            trigger=FAST_TRIGGER_IMPACT,
                            origin=FAST_ORIGIN_RAW_PROJECTILE,
                            origin_opcode=0,
                        )
                        if descriptor is not None:
                            candidates.append(descriptor)
            except (TypeError, ValueError, OverflowError):
                malformed_cards[card_id] = True
                continue

            if any(not _valid_descriptor(item) for item in candidates):
                malformed_cards[card_id] = True
                continue
            if len(candidates) != len(set(candidates)):
                duplicate_cards[card_id] = True
                malformed_cards[card_id] = True
                continue
            per_card[card_id] = candidates

        maximum = max(1, max(len(value) for value in per_card))
        size = len(catalog.names)
        shape = (size, maximum)
        device = catalog.device

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=device)

        values: dict[str, torch.Tensor] = {
            "trigger": zeros(torch.int8),
            "center": zeros(torch.int8),
            "recipient": zeros(torch.int8),
            "origin": zeros(torch.int8),
            "origin_opcode": zeros(torch.int16),
            "damage": zeros(torch.float32),
            "radius_units": zeros(torch.int32),
            "status_kind": zeros(torch.int8),
            "status_duration_ticks": zeros(torch.int32),
            "lifetime_ticks": zeros(torch.int32),
            "damage_interval_ticks": zeros(torch.int32),
            "initial_damage_delay_ticks": zeros(torch.int32),
            "damage_on_spawn": zeros(torch.bool),
            "max_damage_hits": zeros(torch.int32),
            "status_interval_ticks": zeros(torch.int32),
            "initial_status_delay_ticks": zeros(torch.int32),
            "max_status_scans": zeros(torch.int32),
            "hits_air": zeros(torch.bool),
            "hits_ground": zeros(torch.bool),
            "affects_hidden": zeros(torch.bool),
            "tower_damage_multiplier": torch.ones(
                shape, dtype=torch.float32, device=device
            ),
            "building_damage_multiplier": torch.ones(
                shape, dtype=torch.float32, device=device
            ),
            "impulse_units": zeros(torch.int32),
            "impulse_push_speed_factor": zeros(torch.int32),
            "impulse_attract_percentage": zeros(torch.int32),
            "impulse_interval_ticks": zeros(torch.int32),
            "impulse_scan_count": zeros(torch.int32),
        }
        descriptor_fields = tuple(field.name for field in fields(_Descriptor))
        for card_id, descriptors in enumerate(per_card):
            if malformed_cards[card_id]:
                continue
            for slot, descriptor in enumerate(descriptors):
                for name in descriptor_fields:
                    values[name][card_id, slot] = getattr(descriptor, name)

        supported = torch.tensor(
            [
                bool(value) and not malformed_cards[index]
                for index, value in enumerate(per_card)
            ],
            dtype=torch.bool,
            device=device,
        )
        malformed = torch.tensor(malformed_cards, dtype=torch.bool, device=device)
        duplicate = torch.tensor(duplicate_cards, dtype=torch.bool, device=device)
        descriptor_count = torch.tensor(
            [
                0 if malformed_cards[index] else len(value)
                for index, value in enumerate(per_card)
            ],
            dtype=torch.int16,
            device=device,
        )
        return cls(
            device=device,
            supported=supported,
            malformed=malformed,
            duplicate=duplicate,
            descriptor_count=descriptor_count,
            **values,
        )


@dataclass(frozen=True)
class FastTriggeredImpactEvents:
    """Fixed-shape trigger events; every tensor has shape ``[B, Q]``."""

    active: torch.Tensor
    card_id: torch.Tensor
    trigger: torch.Tensor
    source_owner: torch.Tensor
    source_entity_id: torch.Tensor
    target_entity_id: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    self_x_units: torch.Tensor
    self_y_units: torch.Tensor
    repeat_count: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_events: int,
        device: str | torch.device = "cpu",
    ) -> FastTriggeredImpactEvents:
        if batch_size < 1 or max_events < 1:
            raise ValueError("batch_size and max_events must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_events)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            active=zeros(torch.bool),
            card_id=zeros(torch.int64),
            trigger=zeros(torch.int8),
            source_owner=zeros(torch.int8),
            source_entity_id=zeros(torch.int64),
            target_entity_id=zeros(torch.int64),
            source_x_units=zeros(torch.int32),
            source_y_units=zeros(torch.int32),
            target_x_units=zeros(torch.int32),
            target_y_units=zeros(torch.int32),
            self_x_units=zeros(torch.int32),
            self_y_units=zeros(torch.int32),
            repeat_count=torch.ones(shape, dtype=torch.int32, device=tensor_device),
        )


@dataclass(frozen=True)
class FastTriggeredImpactCommands:
    """Resolved descriptor lanes with shape ``[B, Q * descriptors]``."""

    active: torch.Tensor
    card_id: torch.Tensor
    trigger: torch.Tensor
    center: torch.Tensor
    recipient: torch.Tensor
    source_owner: torch.Tensor
    source_entity_id: torch.Tensor
    target_entity_id: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    repeat_count: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    lifetime_ticks: torch.Tensor
    damage_interval_ticks: torch.Tensor
    initial_damage_delay_ticks: torch.Tensor
    damage_on_spawn: torch.Tensor
    max_damage_hits: torch.Tensor
    status_interval_ticks: torch.Tensor
    initial_status_delay_ticks: torch.Tensor
    max_status_scans: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    impulse_units: torch.Tensor
    impulse_push_speed_factor: torch.Tensor
    impulse_attract_percentage: torch.Tensor
    impulse_interval_ticks: torch.Tensor
    impulse_scan_count: torch.Tensor


def _validate_events(
    catalog: FastTriggeredImpactCatalog,
    events: FastTriggeredImpactEvents,
) -> tuple[int, int]:
    shape = tuple(events.active.shape)
    if len(shape) != 2:
        raise ValueError("event tensors must have shape [batch, events]")
    device = events.active.device
    if device != catalog.device or events.active.dtype != torch.bool:
        raise ValueError("events and catalog must share a device")
    expected_dtypes = {
        "card_id": torch.int64,
        "trigger": torch.int8,
        "source_owner": torch.int8,
        "source_entity_id": torch.int64,
        "target_entity_id": torch.int64,
        "source_x_units": torch.int32,
        "source_y_units": torch.int32,
        "target_x_units": torch.int32,
        "target_y_units": torch.int32,
        "self_x_units": torch.int32,
        "self_y_units": torch.int32,
        "repeat_count": torch.int32,
    }
    for name, dtype in expected_dtypes.items():
        value = getattr(events, name)
        if (
            tuple(value.shape) != shape
            or value.device != device
            or value.dtype != dtype
        ):
            raise ValueError(f"{name} has the wrong shape, device, or dtype")
    return shape


def resolve_fast_triggered_impacts(
    catalog: FastTriggeredImpactCatalog,
    events: FastTriggeredImpactEvents,
) -> FastTriggeredImpactCommands:
    """Resolve fixed events into numeric command lanes without host dispatch."""

    batch, event_count = _validate_events(catalog, events)
    descriptor_count = catalog.max_descriptors
    valid_card = (events.card_id > 0) & (events.card_id < catalog.card_capacity)
    safe_card = events.card_id.clamp(min=0, max=catalog.card_capacity - 1)

    def lookup(name: str) -> torch.Tensor:
        return getattr(catalog, name)[safe_card]

    trigger = lookup("trigger")
    center = lookup("center")
    supported = catalog.supported[safe_card]
    active = (
        events.active[:, :, None]
        & valid_card[:, :, None]
        & supported[:, :, None]
        & (
            (events.source_owner[:, :, None] == 0)
            | (events.source_owner[:, :, None] == 1)
        )
        & (events.repeat_count[:, :, None] > 0)
        & (trigger == events.trigger[:, :, None])
    )
    source_x = events.source_x_units[:, :, None].expand(-1, -1, descriptor_count)
    source_y = events.source_y_units[:, :, None].expand(-1, -1, descriptor_count)
    center_x = torch.where(
        center == FAST_CENTER_SOURCE,
        source_x,
        torch.where(
            center == FAST_CENTER_TARGET,
            events.target_x_units[:, :, None],
            events.self_x_units[:, :, None],
        ),
    )
    center_y = torch.where(
        center == FAST_CENTER_SOURCE,
        source_y,
        torch.where(
            center == FAST_CENTER_TARGET,
            events.target_y_units[:, :, None],
            events.self_y_units[:, :, None],
        ),
    )
    flat_shape = (batch, event_count * descriptor_count)

    def flatten(value: torch.Tensor) -> torch.Tensor:
        return value.expand(batch, event_count, descriptor_count).reshape(flat_shape)

    return FastTriggeredImpactCommands(
        active=active.reshape(flat_shape),
        card_id=flatten(events.card_id[:, :, None]),
        trigger=trigger.reshape(flat_shape),
        center=center.reshape(flat_shape),
        recipient=lookup("recipient").reshape(flat_shape),
        source_owner=flatten(events.source_owner[:, :, None]),
        source_entity_id=flatten(events.source_entity_id[:, :, None]),
        target_entity_id=flatten(events.target_entity_id[:, :, None]),
        source_x_units=source_x.reshape(flat_shape),
        source_y_units=source_y.reshape(flat_shape),
        center_x_units=center_x.reshape(flat_shape),
        center_y_units=center_y.reshape(flat_shape),
        repeat_count=flatten(events.repeat_count[:, :, None]),
        damage=lookup("damage").reshape(flat_shape),
        radius_units=lookup("radius_units").reshape(flat_shape),
        status_kind=lookup("status_kind").reshape(flat_shape),
        status_duration_ticks=lookup("status_duration_ticks").reshape(flat_shape),
        lifetime_ticks=lookup("lifetime_ticks").reshape(flat_shape),
        damage_interval_ticks=lookup("damage_interval_ticks").reshape(flat_shape),
        initial_damage_delay_ticks=lookup("initial_damage_delay_ticks").reshape(
            flat_shape
        ),
        damage_on_spawn=lookup("damage_on_spawn").reshape(flat_shape),
        max_damage_hits=lookup("max_damage_hits").reshape(flat_shape),
        status_interval_ticks=lookup("status_interval_ticks").reshape(flat_shape),
        initial_status_delay_ticks=lookup("initial_status_delay_ticks").reshape(
            flat_shape
        ),
        max_status_scans=lookup("max_status_scans").reshape(flat_shape),
        hits_air=lookup("hits_air").reshape(flat_shape),
        hits_ground=lookup("hits_ground").reshape(flat_shape),
        affects_hidden=lookup("affects_hidden").reshape(flat_shape),
        tower_damage_multiplier=lookup("tower_damage_multiplier").reshape(flat_shape),
        building_damage_multiplier=lookup("building_damage_multiplier").reshape(
            flat_shape
        ),
        impulse_units=lookup("impulse_units").reshape(flat_shape),
        impulse_push_speed_factor=lookup("impulse_push_speed_factor").reshape(
            flat_shape
        ),
        impulse_attract_percentage=lookup("impulse_attract_percentage").reshape(
            flat_shape
        ),
        impulse_interval_ticks=lookup("impulse_interval_ticks").reshape(flat_shape),
        impulse_scan_count=lookup("impulse_scan_count").reshape(flat_shape),
    )


def triggered_commands_to_effect_state(
    commands: FastTriggeredImpactCommands,
) -> FastEffectState:
    """Materialize command lanes as a fixed :class:`FastEffectState` pool."""

    batch, command_count = commands.active.shape
    effects = FastEffectState.empty(
        batch,
        max_effects=command_count,
        device=commands.active.device,
    )
    has_effect = (commands.damage > 0.0) | (commands.status_kind != FAST_STATUS_NONE)
    effects.active.copy_(commands.active & has_effect)
    effects.kind.fill_(FAST_EFFECT_AREA)
    effects.source_owner.copy_(commands.source_owner)
    effects.source_card_id.copy_(commands.card_id)
    effects.source_x_units.copy_(commands.source_x_units)
    effects.source_y_units.copy_(commands.source_y_units)
    effects.x_units.copy_(commands.center_x_units)
    effects.y_units.copy_(commands.center_y_units)
    effects.target_id.copy_(commands.target_entity_id)
    effects.target_x_units.copy_(commands.center_x_units)
    effects.target_y_units.copy_(commands.center_y_units)
    effects.tracks_target.zero_()
    effects.damage.copy_(commands.damage)
    effects.tower_damage_multiplier.copy_(commands.tower_damage_multiplier)
    effects.building_damage_multiplier.copy_(commands.building_damage_multiplier)
    effects.radius_units.copy_(commands.radius_units)
    effects.status_kind.copy_(commands.status_kind)
    effects.status_duration_ticks.copy_(commands.status_duration_ticks)
    effects.lifetime_ticks.copy_(commands.lifetime_ticks)
    effects.damage_interval_ticks.copy_(commands.damage_interval_ticks.clamp_min(1))
    effects.next_damage_tick.copy_(commands.initial_damage_delay_ticks)
    effects.damage_on_spawn.copy_(commands.damage_on_spawn)
    effects.damage_hits_remaining.copy_(commands.max_damage_hits)
    effects.status_interval_ticks.copy_(commands.status_interval_ticks.clamp_min(1))
    effects.next_status_tick.copy_(commands.initial_status_delay_ticks)
    effects.status_scans_remaining.copy_(commands.max_status_scans)
    effects.hits_air.copy_(commands.hits_air)
    effects.hits_ground.copy_(commands.hits_ground)
    effects.affects_hidden.copy_(commands.affects_hidden)
    return effects


@dataclass(frozen=True)
class FastTriggeredImpactTargets:
    """Entity geometry and eligibility used by the radial adapter."""

    active: torch.Tensor
    stable_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    collision_radius_units: torch.Tensor
    base_speed_units_per_tick: torch.Tensor
    is_air: torch.Tensor
    is_building: torch.Tensor
    area_receivable: torch.Tensor
    effect_receivable_affects_hidden: torch.Tensor
    max_displacement_units: torch.Tensor


def _validate_targets(
    commands: FastTriggeredImpactCommands,
    targets: FastTriggeredImpactTargets,
) -> tuple[int, int, int]:
    command_shape = tuple(commands.active.shape)
    target_shape = tuple(targets.active.shape)
    if len(command_shape) != 2 or len(target_shape) != 2:
        raise ValueError("commands and targets must be rank two")
    batch, commands_count = command_shape
    if target_shape[0] != batch:
        raise ValueError("commands and targets must share a batch size")
    expected = {
        "active": torch.bool,
        "stable_id": torch.int64,
        "owner": torch.int8,
        "x_units": torch.int32,
        "y_units": torch.int32,
        "collision_radius_units": torch.int32,
        "base_speed_units_per_tick": torch.int32,
        "is_air": torch.bool,
        "is_building": torch.bool,
        "area_receivable": torch.bool,
        "effect_receivable_affects_hidden": torch.bool,
        "max_displacement_units": torch.int32,
    }
    for name, dtype in expected.items():
        value = getattr(targets, name)
        if (
            tuple(value.shape) != target_shape
            or value.device != commands.active.device
            or value.dtype != dtype
        ):
            raise ValueError(f"{name} has the wrong shape, device, or dtype")
    return batch, commands_count, target_shape[1]


def triggered_commands_to_impulse_inputs(
    commands: FastTriggeredImpactCommands,
    targets: FastTriggeredImpactTargets,
    *,
    max_expanded_impulses: int = 65_536,
) -> FastRadialImpulseInputs:
    """Adapt radial commands to the existing exact integer impulse kernel.

    Attraction magnitude is retained as ``[batch, commands, targets]`` while
    the shared impulse kernel fuses normalization and reduction. The explicit
    logical-pair ceiling fails before allocation if a caller proposes a
    production-unreasonable event pool.
    """

    _, command_count, entity_count = _validate_targets(commands, targets)
    expanded_count = command_count * entity_count
    if expanded_count < 1 or expanded_count > max_expanded_impulses:
        raise ValueError("expanded impulse pool exceeds the configured bound")
    command_active = commands.active[:, :, None]
    impulse_active = (commands.impulse_units[:, :, None] != 0) | (
        (commands.impulse_push_speed_factor[:, :, None] > 0)
        & (commands.impulse_attract_percentage[:, :, None] > 0)
    )
    plane = torch.where(
        targets.is_air[:, None, :],
        commands.hits_air[:, :, None],
        commands.hits_ground[:, :, None],
    )
    receivable = torch.where(
        commands.affects_hidden[:, :, None],
        targets.effect_receivable_affects_hidden[:, None, :],
        targets.area_receivable[:, None, :],
    )
    dx = targets.x_units[:, None, :].to(torch.int64) - commands.center_x_units[
        :, :, None
    ].to(torch.int64)
    dy = targets.y_units[:, None, :].to(torch.int64) - commands.center_y_units[
        :, :, None
    ].to(torch.int64)
    reach = commands.radius_units[:, :, None].to(torch.int64).clamp_min(
        0
    ) + targets.collision_radius_units[:, None, :].to(torch.int64).clamp_min(0)
    enemy = (
        targets.active[:, None, :]
        & (targets.stable_id[:, None, :] > 0)
        & (targets.owner[:, None, :] != commands.source_owner[:, :, None])
        & ~targets.is_building[:, None, :]
        & plane
        & receivable
        & (dx.square() + dy.square() <= reach.square())
    )
    self_target = (
        targets.active[:, None, :]
        & (targets.stable_id[:, None, :] > 0)
        & (targets.stable_id[:, None, :] == commands.source_entity_id[:, :, None])
        & ~targets.is_building[:, None, :]
        & ((dx != 0) | (dy != 0))
    )
    eligible_by_target = (
        command_active
        & impulse_active
        & torch.where(
            commands.recipient[:, :, None] == FAST_RECIPIENT_SELF,
            self_target,
            enemy,
        )
    )

    speed_stage = torch.div(
        targets.base_speed_units_per_tick[:, None, :].to(torch.int64)
        * commands.impulse_push_speed_factor[:, :, None].to(torch.int64),
        100,
        rounding_mode="trunc",
    )
    pull_units = torch.div(
        speed_stage * commands.impulse_attract_percentage[:, :, None].to(torch.int64),
        100,
        rounding_mode="trunc",
    )
    repeat = commands.repeat_count[:, :, None].to(torch.int64).clamp_min(0)
    magnitude = (
        commands.impulse_units[:, :, None].to(torch.int64) - pull_units
    ) * repeat
    int32 = torch.iinfo(torch.int32)
    magnitude = magnitude.clamp(min=int32.min, max=int32.max).to(torch.int32)

    return FastRadialImpulseInputs(
        center_x_units=commands.center_x_units,
        center_y_units=commands.center_y_units,
        target_x_units=targets.x_units,
        target_y_units=targets.y_units,
        target_stable_id=targets.stable_id,
        eligible=eligible_by_target,
        magnitude_units=magnitude,
        distance_percentage=None,
        max_displacement_units=targets.max_displacement_units,
    )


def clone_fast_triggered_events(
    events: FastTriggeredImpactEvents,
) -> FastTriggeredImpactEvents:
    """Clone an event tensor for deterministic replay fixtures."""

    return type(events)(
        **{field.name: getattr(events, field.name).clone() for field in fields(events)}
    )
