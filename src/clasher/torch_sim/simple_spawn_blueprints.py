"""Setup-time serialized spawn blueprints for the practical tensor Gym.

This module deliberately has no card-name dispatch.  It expands ordinary
character payloads into private catalog rows at setup and compiles every
reachable spawn requirement into a small numeric table.  Unsupported trigger
shapes remain visible in that table so public-card admission can fail closed.

The allocation kernel is shared by death, impact, and future periodic/scheduled
callers.  It mutates only :class:`FastGymState`; callers remain responsible for
initializing aligned lifecycle and modifier planes from ``spawned_mask``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from itertools import pairwise
from typing import Any

import torch

from clasher.card_types import CardStatsCompat
from clasher.data import CardDataLoader
from clasher.factory.card_factory import card_from_gamedata
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.mechanics.shared.death_effects import DeathDamage, DeathSpawn
from clasher.mechanics.shared.spawner import PeriodicSpawner

from .catalog import TensorCardCatalog
from .simple_catalog import FAST_CARD_EFFECT_AREA, FastCardCatalog
from .simple_death_burst import FastDeathBurstCatalog
from .simple_effects import FastEffectState
from .simple_payload_containers import (
    FastPayloadContainerCommands,
    FastPayloadEffectCommands,
    FastPayloadSpawnTriggers,
)
from .simple_positive_buffs import FastPositiveBuffAreaAllocationCommands
from .simple_rolling_spells import FastRollingSpawnTriggers
from .simple_state import FastGymState


class FastSpawnTrigger(IntEnum):
    """Serialized event that requests a spawn blueprint."""

    DEATH = 1
    PROJECTILE_IMPACT = 2
    PERIODIC = 3
    ROLLING_IMPACT = 4
    DELAYED_IMPACT = 5
    SCHEDULED_ACTION = 6


@dataclass(frozen=True)
class _SpawnRequirement:
    root_name: str
    trigger: FastSpawnTrigger
    child_name: str
    child_data: dict[str, Any] | None
    count: int
    radius_units: int
    deploy_ticks: int
    first_delay_ticks: int
    interval_ticks: int
    max_waves: int
    source_path: str


class _SpawnCatalogLoader(CardDataLoader):
    """Loader overlay retaining setup-only internal character definitions."""

    def __init__(self, source: CardDataLoader) -> None:
        self.data_file = source.data_file
        self._card_definitions = dict(source.load_card_definitions())
        self._cards: dict[str, CardStatsCompat] = {}

    def add_character(
        self,
        label: str,
        internal_name: str,
        data: dict[str, Any],
    ) -> None:
        if label in self._card_definitions:
            return
        payload = copy.deepcopy(data)
        rarity = str(payload.get("rarity", "Common"))
        if str(payload.get("source", "")) == "buildings":
            entry = {
                "id": 0,
                "name": internal_name,
                "rarity": rarity,
                "manaCost": 0,
                "tidType": "TID_CARD_TYPE_BUILDING",
                "summonCharacterData": payload,
            }
            stats = CardStatsCompat.from_card_definition(card_from_gamedata(entry))
        else:
            stats = troop_from_character_data(
                internal_name,
                payload,
                elixir=0,
                rarity=rarity,
            )
        # TensorCardCatalog uses the mapping key as the stable row identity and
        # the already-materialized wrapper for current stats/balance overlays.
        self._card_definitions[label] = stats.card_definition
        self._cards[label] = stats


def _ticks(milliseconds: Any) -> int:
    try:
        value = int(milliseconds or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, (value + 49) // 50)


def _payload_key(name: str, data: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return name, serialized


def _payload_label(name: str, serialized: str) -> str:
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:12]
    return f"@child/{name}/{digest}"


def _spawn_requirements(
    loader: CardDataLoader,
    root_names: Iterable[str],
) -> tuple[_SpawnRequirement, ...]:
    definitions = loader.load_card_definitions()
    requirements: list[_SpawnRequirement] = []

    for root_name in sorted(set(root_names)):
        definition = definitions[root_name]
        mechanic_death_children: set[str] = set()
        for slot, mechanic in enumerate(definition.mechanics):
            if isinstance(mechanic, DeathSpawn):
                mechanic_death_children.add(str(mechanic.unit_name))
                requirements.append(
                    _SpawnRequirement(
                        root_name=root_name,
                        trigger=FastSpawnTrigger.DEATH,
                        child_name=str(mechanic.unit_name),
                        child_data=(
                            copy.deepcopy(mechanic.unit_data)
                            if isinstance(mechanic.unit_data, dict)
                            else None
                        ),
                        count=max(0, int(mechanic.count)),
                        radius_units=round(max(0.0, mechanic.radius_tiles) * 1_000),
                        deploy_ticks=_ticks(mechanic.deploy_time_ms),
                        first_delay_ticks=0,
                        interval_ticks=0,
                        max_waves=1,
                        source_path=f"{root_name}.mechanics[{slot}].unit_data",
                    )
                )
            elif isinstance(mechanic, PeriodicSpawner):
                requirements.append(
                    _SpawnRequirement(
                        root_name=root_name,
                        trigger=FastSpawnTrigger.PERIODIC,
                        child_name=str(mechanic.unit_name),
                        child_data=(
                            copy.deepcopy(mechanic.unit_data)
                            if isinstance(mechanic.unit_data, dict)
                            else None
                        ),
                        count=max(1, int(mechanic.count)),
                        radius_units=round(
                            max(0.0, mechanic.spawn_radius_tiles) * 1_000
                        ),
                        deploy_ticks=0,
                        first_delay_ticks=_ticks(mechanic.first_spawn_delay_ms),
                        interval_ticks=_ticks(mechanic.spawn_interval_ms),
                        max_waves=int(mechanic.max_spawns),
                        source_path=f"{root_name}.mechanics[{slot}].unit_data",
                    )
                )

        raw = definition.raw or {}
        character = raw.get("summonCharacterData") or raw.get("summonSpellData") or {}
        raw_death_child = character.get("deathSpawnCharacterData") or {}
        raw_death_name = str(
            raw_death_child.get("name") or character.get("deathSpawnCharacter") or ""
        )
        # Some serialized containers are compiled directly into a terminal
        # area mechanic rather than a DeathSpawn object (Lumberjack's bottle).
        # Retain the child requirement anyway so root admission stays closed
        # until the no-HP payload-container trigger is implemented.
        if raw_death_name and raw_death_name not in mechanic_death_children:
            requirements.append(
                _SpawnRequirement(
                    root_name=root_name,
                    trigger=FastSpawnTrigger.DEATH,
                    child_name=raw_death_name,
                    child_data=(
                        copy.deepcopy(raw_death_child)
                        if isinstance(raw_death_child, dict)
                        else None
                    ),
                    count=max(1, int(character.get("deathSpawnCount", 1) or 1)),
                    radius_units=max(0, int(character.get("deathSpawnRadius", 0) or 0)),
                    deploy_ticks=_ticks(character.get("deathSpawnDeployTime")),
                    first_delay_ticks=0,
                    interval_ticks=0,
                    max_waves=1,
                    source_path=(
                        f"{root_name}.summonCharacterData.deathSpawnCharacterData"
                    ),
                )
            )
        projectile = raw.get("projectileData") or {}
        direct_child = projectile.get("spawnCharacterData")
        if isinstance(direct_child, dict) and direct_child.get("name"):
            requirements.append(
                _SpawnRequirement(
                    root_name=root_name,
                    trigger=FastSpawnTrigger.PROJECTILE_IMPACT,
                    child_name=str(direct_child["name"]),
                    child_data=copy.deepcopy(direct_child),
                    count=max(1, int(projectile.get("spawnCharacterCount", 1) or 1)),
                    radius_units=max(0, int(projectile.get("spawnRadius", 0) or 0)),
                    deploy_ticks=_ticks(projectile.get("spawnCharacterDeployTime")),
                    first_delay_ticks=0,
                    interval_ticks=0,
                    max_waves=1,
                    source_path=f"{root_name}.projectileData.spawnCharacterData",
                )
            )

        rolling = projectile.get("spawnProjectileData") or {}
        rolling_child = rolling.get("spawnCharacterData")
        if isinstance(rolling_child, dict) and rolling_child.get("name"):
            requirements.append(
                _SpawnRequirement(
                    root_name=root_name,
                    trigger=FastSpawnTrigger.ROLLING_IMPACT,
                    child_name=str(rolling_child["name"]),
                    child_data=copy.deepcopy(rolling_child),
                    count=max(1, int(rolling.get("spawnCharacterCount", 1) or 1)),
                    radius_units=max(0, int(rolling.get("spawnRadius", 0) or 0)),
                    deploy_ticks=_ticks(rolling.get("spawnCharacterDeployTime")),
                    first_delay_ticks=0,
                    interval_ticks=0,
                    max_waves=1,
                    source_path=(
                        f"{root_name}.projectileData.spawnProjectileData."
                        "spawnCharacterData"
                    ),
                )
            )

        area = raw.get("areaEffectObjectData") or {}
        area_projectile = area.get("projectileData") or {}
        area_child = area_projectile.get("spawnCharacterData")
        if isinstance(area_child, dict) and area_child.get("name"):
            requirements.append(
                _SpawnRequirement(
                    root_name=root_name,
                    trigger=FastSpawnTrigger.DELAYED_IMPACT,
                    child_name=str(area_child["name"]),
                    child_data=copy.deepcopy(area_child),
                    count=max(
                        1,
                        int(area_projectile.get("spawnCharacterCount", 1) or 1),
                    ),
                    radius_units=max(
                        0, int(area_projectile.get("spawnRadius", 0) or 0)
                    ),
                    deploy_ticks=_ticks(area.get("spawnTime")),
                    first_delay_ticks=_ticks(
                        area.get("spawnInitialDelay", area.get("lifeDuration", 0))
                    ),
                    interval_ticks=0,
                    max_waves=1,
                    source_path=(
                        f"{root_name}.areaEffectObjectData.projectileData."
                        "spawnCharacterData"
                    ),
                )
            )
        action = area.get("onStartingActionData")
        if isinstance(action, dict):
            subactions = action.get("subActionsData") or []
            spawn_actions = [
                value
                for value in subactions
                if isinstance(value, dict)
                and (value.get("spawnCharacter") or value.get("spawnCharacterData"))
            ]
            if spawn_actions:
                first = spawn_actions[0]
                child = first.get("spawnCharacterData")
                delays = action.get("subActionsDelay") or []
                delay_ticks = [_ticks(value) for value in delays]
                same_child = all(
                    str(
                        ((value.get("spawnCharacterData") or {}).get("name"))
                        or value.get("spawnCharacter")
                        or ""
                    )
                    == str(
                        (child or {}).get("name")
                        or first.get("spawnCharacter")
                        or ""
                    )
                    for value in spawn_actions
                )
                regular_schedule = bool(
                    len(delay_ticks) == len(spawn_actions)
                    and delay_ticks
                    and all(
                        right > left
                        for left, right in pairwise(delay_ticks)
                    )
                )
                interval = (
                    max(
                        1,
                        round(
                            (delay_ticks[-1] - delay_ticks[0])
                            / max(1, len(delay_ticks) - 1)
                        ),
                    )
                    if len(delay_ticks) > 1
                    else 0
                )
                schedule_child = str(
                    (child or {}).get("name")
                    or first.get("spawnCharacter")
                    or ""
                )
                # The production scheduler is a deliberately compact cadence
                # approximation. Fail closed unless every serialized action
                # is the same typed child and has an ordered deadline.
                if not same_child or not regular_schedule or not schedule_child:
                    continue
                requirements.append(
                    _SpawnRequirement(
                        root_name=root_name,
                        trigger=FastSpawnTrigger.SCHEDULED_ACTION,
                        child_name=schedule_child,
                        child_data=(
                            copy.deepcopy(child) if isinstance(child, dict) else None
                        ),
                        count=1,
                        radius_units=max(0, int(area.get("radius", 0) or 0)),
                        deploy_ticks=_ticks(first.get("deployTime")),
                        first_delay_ticks=delay_ticks[0],
                        interval_ticks=interval,
                        max_waves=len(spawn_actions),
                        source_path=(
                            f"{root_name}.areaEffectObjectData."
                            "onStartingActionData.subActionsData"
                        ),
                    )
                )
    return tuple(requirements)


@dataclass(frozen=True)
class FastSpawnBlueprintCatalog:
    """Dense setup-time spawn descriptors and their expanded card tables."""

    device: torch.device
    cards: TensorCardCatalog
    fast_cards: FastCardCatalog
    death_burst_catalog: FastDeathBurstCatalog
    visible_names: tuple[str, ...]
    root_names: tuple[str, ...]
    source_paths: tuple[str, ...]
    trigger: torch.Tensor
    root_card_id: torch.Tensor
    child_card_id: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor
    first_delay_ticks: torch.Tensor
    interval_ticks: torch.Tensor
    max_waves: torch.Tensor
    blueprint_supported: torch.Tensor
    root_payload_required: torch.Tensor
    root_payload_supported: torch.Tensor
    impact_blueprint_by_card: torch.Tensor
    rolling_blueprint_by_card: torch.Tensor
    container_blueprint_by_card: torch.Tensor
    container_lifetime_ticks: torch.Tensor
    container_damage: torch.Tensor
    container_radius_units: torch.Tensor
    container_tower_damage_multiplier: torch.Tensor
    container_building_damage_multiplier: torch.Tensor
    container_hits_air: torch.Tensor
    container_hits_ground: torch.Tensor
    container_nested_child_card_id: torch.Tensor
    container_nested_count: torch.Tensor
    container_nested_radius_units: torch.Tensor
    container_nested_deploy_ticks: torch.Tensor
    container_positive_area_enabled: torch.Tensor
    container_positive_area_lifetime_ticks: torch.Tensor
    container_positive_area_radius_units: torch.Tensor
    container_positive_area_scan_interval_ticks: torch.Tensor
    container_positive_area_recipient_duration_ticks: torch.Tensor
    container_positive_area_movement_multiplier: torch.Tensor
    container_positive_area_attack_multiplier: torch.Tensor
    container_positive_area_damage: torch.Tensor
    container_positive_area_damage_radius_units: torch.Tensor
    container_positive_area_tower_damage_multiplier: torch.Tensor
    container_positive_area_building_damage_multiplier: torch.Tensor
    container_positive_area_damage_hits_air: torch.Tensor
    container_positive_area_damage_hits_ground: torch.Tensor
    scheduled_blueprint_by_card: torch.Tensor
    scheduled_initial_damage: torch.Tensor
    scheduled_initial_radius_units: torch.Tensor
    scheduled_tower_damage_multiplier: torch.Tensor
    scheduled_building_damage_multiplier: torch.Tensor
    scheduled_hits_air: torch.Tensor
    scheduled_hits_ground: torch.Tensor
    public_card_mask: torch.Tensor

    @property
    def blueprint_count(self) -> int:
        return len(self.root_names)

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        base_cards: TensorCardCatalog,
    ) -> FastSpawnBlueprintCatalog:
        roots = tuple(base_cards.names[1:])
        requirements = _spawn_requirements(loader, roots)
        overlay = _SpawnCatalogLoader(loader)

        payloads: dict[tuple[str, str], dict[str, Any]] = {}
        for requirement in requirements:
            data = requirement.child_data
            if not isinstance(data, dict):
                continue
            if data.get("hitpoints") is not None:
                key = _payload_key(requirement.child_name, data)
                payloads[key] = data
            nested = data.get("deathSpawnCharacterData") or {}
            nested_name = str(
                nested.get("name") or data.get("deathSpawnCharacter") or ""
            )
            if (
                nested_name
                and isinstance(nested, dict)
                and nested.get("hitpoints") is not None
            ):
                key = _payload_key(nested_name, nested)
                payloads[key] = nested

        label_by_key: dict[tuple[str, str], str] = {}
        visible_by_label: dict[str, str] = {}
        for (name, serialized), data in sorted(payloads.items()):
            label = _payload_label(name, serialized)
            label_by_key[(name, serialized)] = label
            visible_by_label[label] = name
            overlay.add_character(label, name, data)

        referenced_names = {
            requirement.child_name
            for requirement in requirements
            if requirement.child_data is None
            and loader.get_card(requirement.child_name) is not None
        }
        expanded_names = tuple(
            sorted({*roots, *visible_by_label, *referenced_names})
        )
        cards = TensorCardCatalog.compile(
            overlay,
            expanded_names,
            device=base_cards.device,
        )
        fast_cards = FastCardCatalog.from_tensor_catalog(cards, loader=overlay)
        visible_names = tuple(visible_by_label.get(name, name) for name in cards.names)

        death_burst_catalog = FastDeathBurstCatalog.empty(
            len(cards.names), device=cards.device
        )
        for label, card_id in cards.name_to_id.items():
            if not label:
                continue
            stats = overlay.get_card(label)
            if stats is None:
                continue
            bursts = [
                mechanic
                for mechanic in stats.card_definition.mechanics
                if isinstance(mechanic, DeathDamage)
            ]
            if len(bursts) != 1:
                continue
            burst = bursts[0]
            death_burst_catalog.enabled[card_id] = True
            death_burst_catalog.damage[card_id] = float(
                stats.get_scaled_stat(burst.damage) or 0
            )
            death_burst_catalog.radius_units[card_id] = round(
                max(0.0, burst.radius_tiles) * 1_000
            )
            death_burst_catalog.hits_air[card_id] = bool(burst.hits_air)
            death_burst_catalog.hits_ground[card_id] = bool(burst.hits_ground)

        def tensor(values: Iterable[object], dtype: torch.dtype) -> torch.Tensor:
            return torch.tensor(tuple(values), dtype=dtype, device=cards.device)

        child_ids: list[int] = []
        container_rows: list[bool] = []
        container_lifetime: list[int] = []
        container_damage: list[float] = []
        container_radius: list[int] = []
        container_tower_scale: list[float] = []
        container_building_scale: list[float] = []
        container_hits_air: list[bool] = []
        container_hits_ground: list[bool] = []
        nested_child_ids: list[int] = []
        nested_counts: list[int] = []
        nested_radii: list[int] = []
        nested_deploy: list[int] = []
        positive_area_enabled: list[bool] = []
        positive_area_lifetime: list[int] = []
        positive_area_radius: list[int] = []
        positive_area_interval: list[int] = []
        positive_area_recipient_duration: list[int] = []
        positive_area_movement: list[float] = []
        positive_area_attack: list[float] = []
        positive_area_damage: list[float] = []
        positive_area_damage_radius: list[int] = []
        positive_area_tower_scale: list[float] = []
        positive_area_building_scale: list[float] = []
        positive_area_damage_hits_air: list[bool] = []
        positive_area_damage_hits_ground: list[bool] = []
        scheduled_damage: list[float] = []
        scheduled_effect_radius: list[int] = []
        scheduled_tower_scale: list[float] = []
        scheduled_building_scale: list[float] = []
        scheduled_hits_air: list[bool] = []
        scheduled_hits_ground: list[bool] = []
        supported: list[bool] = []
        for requirement in requirements:
            data = requirement.child_data
            child_id = 0
            child_supported = False
            if isinstance(data, dict) and data.get("hitpoints") is not None:
                key = _payload_key(requirement.child_name, data)
                label = label_by_key[key]
                child_id = cards.name_to_id[label]
                child_definition = overlay.get_card(label)
                child_supported = bool(
                    child_definition is not None
                    and child_definition.scaled_hitpoints
                    and fast_cards.kind[child_id] >= 0
                    and fast_cards.training_supported[child_id]
                )
            elif requirement.child_name in cards.name_to_id:
                child_id = cards.name_to_id[requirement.child_name]
                child_definition = overlay.get_card(requirement.child_name)
                child_supported = bool(
                    child_definition is not None
                    and child_definition.scaled_hitpoints
                    and fast_cards.kind[child_id] >= 0
                    and fast_cards.training_supported[child_id]
                )
            death_area: dict[str, Any] = {}
            if isinstance(data, dict):
                raw_death_area = data.get("deathAreaEffectData")
                if isinstance(raw_death_area, dict):
                    death_area = raw_death_area
            container = bool(
                requirement.trigger == FastSpawnTrigger.DEATH
                and isinstance(data, dict)
                and data.get("hitpoints") is None
                and (
                    data.get("deathDamage") is not None
                    or bool(death_area)
                )
            )
            timer = _ticks(data.get("deployTime")) if container and data else 0
            radius = (
                max(
                    0,
                    int(data.get("deathDamageRadius") or data.get("deathRadius") or 0),
                )
                if container and data
                else 0
            )
            raw_damage = (
                int(data.get("deathDamage", 0) or 0) if container and data else 0
            )
            root_stats = loader.get_card(requirement.root_name)
            scaled_damage = (
                float(root_stats.get_scaled_stat(raw_damage) or 0)
                if container and root_stats is not None
                else float(raw_damage)
            )
            target = str(data.get("tidTarget", "") if data else "")
            hits_air = "AIR" in target or not target
            hits_ground = "GROUND" in target or not target
            nested = (
                (data.get("deathSpawnCharacterData") or {})
                if container and data
                else {}
            )
            nested_name = str(
                (nested.get("name") if isinstance(nested, dict) else "")
                or (data.get("deathSpawnCharacter") if data else "")
                or ""
            )
            nested_count = (
                max(0, int(data.get("deathSpawnCount", 0) or 0))
                if container and data
                else 0
            )
            nested_id = 0
            nested_supported = not nested_name and nested_count == 0
            if (
                nested_name
                and nested_count > 0
                and isinstance(nested, dict)
                and nested.get("hitpoints") is not None
            ):
                nested_label = label_by_key[_payload_key(nested_name, nested)]
                nested_id = cards.name_to_id[nested_label]
                nested_definition = overlay.get_card(nested_label)
                nested_supported = bool(
                    nested_definition is not None
                    and nested_definition.scaled_hitpoints
                    and not nested_definition.card_definition.mechanics
                )
            trigger_supported = requirement.trigger in {
                FastSpawnTrigger.DEATH,
                FastSpawnTrigger.PROJECTILE_IMPACT,
                FastSpawnTrigger.ROLLING_IMPACT,
            } or (
                requirement.trigger == FastSpawnTrigger.PERIODIC
                and requirement.first_delay_ticks >= 0
                and requirement.interval_ticks > 0
                and (requirement.max_waves == -1 or requirement.max_waves > 0)
            )
            child_ids.append(child_id)
            container_rows.append(container)
            container_lifetime.append(timer)
            container_damage.append(scaled_damage)
            container_radius.append(radius)
            container_tower_scale.append(1.0)
            container_building_scale.append(1.0)
            container_hits_air.append(hits_air)
            container_hits_ground.append(hits_ground)
            nested_child_ids.append(nested_id)
            nested_counts.append(nested_count)
            nested_radii.append(
                max(0, int(data.get("deathSpawnRadius", 0) or 0))
                if container and data
                else 0
            )
            nested_deploy.append(
                _ticks(data.get("deathSpawnDeployTime")) if container and data else 0
            )
            buff_data: dict[str, Any] = {}
            raw_buff_data = death_area.get("buffData")
            if isinstance(raw_buff_data, dict):
                buff_data = raw_buff_data
            nested_area_damage: dict[str, Any] = {}
            raw_nested_area_damage = death_area.get("spawnAreaEffectObjectData")
            if isinstance(raw_nested_area_damage, dict):
                nested_area_damage = raw_nested_area_damage
            area_lifetime = _ticks(death_area.get("lifeDuration"))
            area_radius = max(0, int(death_area.get("radius", 0) or 0))
            area_interval = _ticks(death_area.get("hitSpeed"))
            area_recipient_duration = _ticks(death_area.get("buffTime"))
            movement_multiplier = max(
                0.0, float(buff_data.get("speedMultiplier", 0) or 0) / 100.0
            )
            attack_multiplier = max(
                0.0,
                float(buff_data.get("hitSpeedMultiplier", 0) or 0) / 100.0,
            )
            nested_raw_damage = int(nested_area_damage.get("damage", 0) or 0)
            nested_scaled_damage = (
                float(root_stats.get_scaled_stat(nested_raw_damage) or 0)
                if root_stats is not None and nested_raw_damage > 0
                else 0.0
            )
            nested_area_radius = max(
                0, int(nested_area_damage.get("radius", 0) or 0)
            )
            crown_percent = float(
                nested_area_damage.get("crownTowerDamagePercent", 0) or 0
            )
            positive_complete = bool(
                death_area
                and buff_data
                and area_lifetime > 0
                and area_radius > 0
                and area_interval > 0
                and area_recipient_duration > 0
                and (movement_multiplier > 1.0 or attack_multiplier > 1.0)
                and nested_scaled_damage > 0
                and nested_area_radius > 0
                and nested_area_damage.get("onlyEnemies") is True
            )
            positive_area_enabled.append(positive_complete)
            positive_area_lifetime.append(area_lifetime)
            positive_area_radius.append(area_radius)
            positive_area_interval.append(area_interval)
            positive_area_recipient_duration.append(area_recipient_duration)
            positive_area_movement.append(movement_multiplier)
            positive_area_attack.append(attack_multiplier)
            positive_area_damage.append(nested_scaled_damage)
            positive_area_damage_radius.append(nested_area_radius)
            positive_area_tower_scale.append(max(0.0, 1.0 + crown_percent / 100.0))
            positive_area_building_scale.append(1.0)
            positive_area_damage_hits_air.append(
                bool(nested_area_damage.get("hitsAir", False))
            )
            positive_area_damage_hits_ground.append(
                bool(nested_area_damage.get("hitsGround", False))
            )
            scheduled = requirement.trigger in {
                FastSpawnTrigger.DELAYED_IMPACT,
                FastSpawnTrigger.SCHEDULED_ACTION,
            }
            root_raw = root_stats._raw_entry if root_stats is not None else {}
            scheduled_area = root_raw.get("areaEffectObjectData") or {}
            scheduled_projectile = scheduled_area.get("projectileData") or {}
            scheduled_raw_damage = (
                int(scheduled_projectile.get("damage", 0) or 0)
                if requirement.trigger == FastSpawnTrigger.DELAYED_IMPACT
                else 0
            )
            scheduled_scaled_damage = (
                float(root_stats.get_scaled_stat(scheduled_raw_damage) or 0)
                if root_stats is not None and scheduled_raw_damage > 0
                else 0.0
            )
            scheduled_radius = (
                max(
                    0,
                    int(
                        scheduled_projectile.get(
                            "radius", scheduled_area.get("radius", 0)
                        )
                        or 0
                    ),
                )
                if scheduled
                else 0
            )
            scheduled_target = str(
                scheduled_projectile.get("tidTarget", "") if scheduled else ""
            )
            scheduled_damage.append(scheduled_scaled_damage)
            scheduled_effect_radius.append(scheduled_radius)
            crown_percent = float(
                scheduled_projectile.get("crownTowerDamagePercent", 0) or 0
            )
            scheduled_tower_scale.append(max(0.0, 1.0 + crown_percent / 100.0))
            scheduled_building_scale.append(1.0)
            scheduled_hits_air.append(
                bool(scheduled_area.get("hitsAir", False))
                or "AIR" in scheduled_target
                or not scheduled_target
            )
            scheduled_hits_ground.append(
                bool(scheduled_area.get("hitsGround", False))
                or "GROUND" in scheduled_target
                or not scheduled_target
            )
            supported.append(
                (
                    container
                    and requirement.count == 1
                    and timer > 0
                    and (
                        (
                            scaled_damage > 0
                            and radius > 0
                            and nested_supported
                        )
                        or positive_complete
                    )
                )
                or (trigger_supported and child_supported and requirement.count > 0)
                or (
                    scheduled
                    and child_supported
                    and requirement.count > 0
                    and requirement.first_delay_ticks >= 0
                    and (
                        requirement.max_waves == 1
                        or (
                            requirement.max_waves > 1
                            and requirement.interval_ticks > 0
                        )
                    )
                    and (
                        requirement.trigger != FastSpawnTrigger.DELAYED_IMPACT
                        or (
                            scheduled_scaled_damage > 0
                            and scheduled_radius > 0
                        )
                    )
                )
            )

        root_required = torch.zeros(
            len(cards.names),
            dtype=torch.bool,
            device=fast_cards.device,
        )
        root_supported = torch.zeros_like(root_required)
        public_card_mask = torch.zeros_like(root_required)
        public_card_mask[
            torch.tensor(
                [cards.name_to_id[name] for name in roots],
                dtype=torch.int64,
                device=cards.device,
            )
        ] = True
        root_rows: dict[int, list[int]] = {}
        for row, requirement in enumerate(requirements):
            root_id = cards.name_to_id[requirement.root_name]
            root_required[root_id] = True
            root_rows.setdefault(root_id, []).append(row)
        for root_id, operation_rows in root_rows.items():
            root_supported[root_id] = all(supported[row] for row in operation_rows)

        impact_by_card = torch.full(
            (len(cards.names),), -1, dtype=torch.int64, device=cards.device
        )
        rolling_by_card = torch.full_like(impact_by_card, -1)
        container_by_card = torch.full_like(impact_by_card, -1)
        scheduled_by_card = torch.full_like(impact_by_card, -1)
        for root_id, operation_rows in root_rows.items():
            if not bool(root_supported[root_id]):
                continue
            for row in operation_rows:
                requirement = requirements[row]
                child_id = child_ids[row]
                if container_rows[row]:
                    container_by_card[root_id] = row
                elif requirement.trigger == FastSpawnTrigger.DEATH:
                    fast_cards.death_spawn_count[root_id] = requirement.count
                    fast_cards.death_spawn_card_id[root_id] = child_id
                    fast_cards.death_spawn_kind[root_id] = fast_cards.kind[child_id]
                    fast_cards.death_spawn_hp[root_id] = fast_cards.hitpoints[child_id]
                    fast_cards.death_spawn_radius_units[root_id] = (
                        requirement.radius_units
                    )
                    fast_cards.death_spawn_deploy_ticks[root_id] = (
                        requirement.deploy_ticks
                    )
                elif requirement.trigger == FastSpawnTrigger.PROJECTILE_IMPACT:
                    impact_by_card[root_id] = row
                elif requirement.trigger == FastSpawnTrigger.ROLLING_IMPACT:
                    rolling_by_card[root_id] = row
                elif requirement.trigger in {
                    FastSpawnTrigger.DELAYED_IMPACT,
                    FastSpawnTrigger.SCHEDULED_ACTION,
                }:
                    if scheduled_by_card[root_id] >= 0:
                        root_supported[root_id] = False
                        scheduled_by_card[root_id] = -1
                    else:
                        scheduled_by_card[root_id] = row

        scheduled_root = scheduled_by_card >= 0
        fast_cards.effect_kind.copy_(
            torch.where(
                scheduled_root & root_supported,
                torch.full_like(fast_cards.effect_kind, FAST_CARD_EFFECT_AREA),
                fast_cards.effect_kind,
            )
        )

        # Public cards with defining spawn payloads are admitted iff their
        # entire reachable payload shape is one of the deliberately bounded
        # runtime triggers above. Internal child rows are never hand-facing.
        fast_cards.training_supported.copy_(
            torch.where(
                root_required,
                root_supported,
                fast_cards.training_supported,
            )
        )

        return cls(
            device=cards.device,
            cards=cards,
            fast_cards=fast_cards,
            death_burst_catalog=death_burst_catalog,
            visible_names=visible_names,
            root_names=tuple(value.root_name for value in requirements),
            source_paths=tuple(value.source_path for value in requirements),
            trigger=tensor((int(value.trigger) for value in requirements), torch.int8),
            root_card_id=tensor(
                (cards.name_to_id[value.root_name] for value in requirements),
                torch.int64,
            ),
            child_card_id=tensor(child_ids, torch.int64),
            count=tensor((value.count for value in requirements), torch.int16),
            radius_units=tensor(
                (value.radius_units for value in requirements), torch.int32
            ),
            deploy_ticks=tensor(
                (value.deploy_ticks for value in requirements), torch.int32
            ),
            first_delay_ticks=tensor(
                (value.first_delay_ticks for value in requirements), torch.int32
            ),
            interval_ticks=tensor(
                (value.interval_ticks for value in requirements), torch.int32
            ),
            max_waves=tensor((value.max_waves for value in requirements), torch.int32),
            blueprint_supported=tensor(supported, torch.bool),
            root_payload_required=root_required,
            root_payload_supported=root_supported,
            impact_blueprint_by_card=impact_by_card,
            rolling_blueprint_by_card=rolling_by_card,
            container_blueprint_by_card=container_by_card,
            container_lifetime_ticks=tensor(container_lifetime, torch.int32),
            container_damage=tensor(container_damage, torch.float32),
            container_radius_units=tensor(container_radius, torch.int32),
            container_tower_damage_multiplier=tensor(
                container_tower_scale, torch.float32
            ),
            container_building_damage_multiplier=tensor(
                container_building_scale, torch.float32
            ),
            container_hits_air=tensor(container_hits_air, torch.bool),
            container_hits_ground=tensor(container_hits_ground, torch.bool),
            container_nested_child_card_id=tensor(nested_child_ids, torch.int64),
            container_nested_count=tensor(nested_counts, torch.int32),
            container_nested_radius_units=tensor(nested_radii, torch.int32),
            container_nested_deploy_ticks=tensor(nested_deploy, torch.int32),
            container_positive_area_enabled=tensor(
                positive_area_enabled, torch.bool
            ),
            container_positive_area_lifetime_ticks=tensor(
                positive_area_lifetime, torch.int32
            ),
            container_positive_area_radius_units=tensor(
                positive_area_radius, torch.int32
            ),
            container_positive_area_scan_interval_ticks=tensor(
                positive_area_interval, torch.int32
            ),
            container_positive_area_recipient_duration_ticks=tensor(
                positive_area_recipient_duration, torch.int32
            ),
            container_positive_area_movement_multiplier=tensor(
                positive_area_movement, torch.float32
            ),
            container_positive_area_attack_multiplier=tensor(
                positive_area_attack, torch.float32
            ),
            container_positive_area_damage=tensor(
                positive_area_damage, torch.float32
            ),
            container_positive_area_damage_radius_units=tensor(
                positive_area_damage_radius, torch.int32
            ),
            container_positive_area_tower_damage_multiplier=tensor(
                positive_area_tower_scale, torch.float32
            ),
            container_positive_area_building_damage_multiplier=tensor(
                positive_area_building_scale, torch.float32
            ),
            container_positive_area_damage_hits_air=tensor(
                positive_area_damage_hits_air, torch.bool
            ),
            container_positive_area_damage_hits_ground=tensor(
                positive_area_damage_hits_ground, torch.bool
            ),
            scheduled_blueprint_by_card=scheduled_by_card,
            scheduled_initial_damage=tensor(scheduled_damage, torch.float32),
            scheduled_initial_radius_units=tensor(
                scheduled_effect_radius, torch.int32
            ),
            scheduled_tower_damage_multiplier=tensor(
                scheduled_tower_scale, torch.float32
            ),
            scheduled_building_damage_multiplier=tensor(
                scheduled_building_scale, torch.float32
            ),
            scheduled_hits_air=tensor(scheduled_hits_air, torch.bool),
            scheduled_hits_ground=tensor(scheduled_hits_ground, torch.bool),
            public_card_mask=public_card_mask,
        )


@dataclass(frozen=True)
class FastSpawnCommands:
    """Fixed-shape materialization commands with shape ``[batch, commands]``."""

    ready: torch.Tensor
    owner: torch.Tensor
    child_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor


@dataclass(frozen=True)
class FastSpawnAllocationResult:
    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    spawned_mask: torch.Tensor
    source_command: torch.Tensor


def death_payload_container_commands(
    catalog: FastSpawnBlueprintCatalog,
    state: FastGymState,
) -> FastPayloadContainerCommands:
    """Decode dead entity rows into stable-ordered timed-container requests."""

    if state.device != catalog.device:
        raise ValueError("state and blueprints must use the same device")
    shape = tuple(state.active.shape)
    if catalog.blueprint_count == 0:
        ready = torch.zeros(shape, dtype=torch.bool, device=state.device)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=state.device)
        zeros_i32 = torch.zeros(shape, dtype=torch.int32, device=state.device)
        zeros_i8 = torch.zeros(shape, dtype=torch.int8, device=state.device)
        zeros_f32 = torch.zeros(shape, dtype=torch.float32, device=state.device)
        return FastPayloadContainerCommands(
            ready=ready,
            source_id=zeros_i64,
            owner=zeros_i8,
            x_units=zeros_i32,
            y_units=zeros_i32,
            lifetime_ticks=zeros_i32,
            effect_card_id=zeros_i64,
            effect_damage=zeros_f32,
            effect_radius_units=zeros_i32,
            effect_status_kind=zeros_i8,
            effect_status_duration_ticks=zeros_i32,
            tower_damage_multiplier=zeros_f32,
            building_damage_multiplier=zeros_f32,
            hits_air=ready,
            hits_ground=ready,
            nested_spawn_blueprint_id=zeros_i64,
        )

    known_card = (state.card_id > 0) & (state.card_id < len(catalog.cards.names))
    safe_card = state.card_id.clamp(0, len(catalog.cards.names) - 1)
    blueprint = catalog.container_blueprint_by_card[safe_card]
    candidate = (
        state.active
        & (state.hp <= 0)
        & known_card
        & (blueprint >= 0)
        & ~state.game_over[:, None]
    )
    safe_blueprint = blueprint.clamp(0, catalog.blueprint_count - 1)

    # Stable IDs, not physical entity slots, define simultaneous creation
    # order. The padded command plane remains fixed at entity capacity.
    capacity = state.max_entities
    slots = torch.arange(capacity, dtype=torch.int64, device=state.device)
    id_i = state.stable_id[:, :, None]
    id_j = state.stable_id[:, None, :]
    slot_i = slots.view(1, capacity, 1)
    slot_j = slots.view(1, 1, capacity)
    predecessor = candidate[:, None, :] & (
        (id_j < id_i) | ((id_j == id_i) & (slot_j < slot_i))
    )
    rank = predecessor.sum(dim=2, dtype=torch.int64)
    output = slots.view(1, capacity)
    ready = output < candidate.sum(dim=1, dtype=torch.int64)[:, None]
    claims = (
        ready[:, :, None]
        & candidate[:, None, :]
        & (output[:, :, None] == rank[:, None, :])
    )
    source_slot = claims.to(torch.int64).argmax(dim=2)

    def ordered(value: torch.Tensor) -> torch.Tensor:
        gathered = value.gather(1, source_slot)
        return torch.where(ready, gathered, torch.zeros_like(gathered))

    ordered_blueprint = ordered(safe_blueprint)
    nested_child = catalog.container_nested_child_card_id[ordered_blueprint]
    positive_area = catalog.container_positive_area_enabled[ordered_blueprint]
    return FastPayloadContainerCommands(
        ready=ready,
        source_id=ordered(state.stable_id),
        owner=ordered(state.owner),
        x_units=ordered(state.x_units),
        y_units=ordered(state.y_units),
        lifetime_ticks=catalog.container_lifetime_ticks[ordered_blueprint],
        effect_card_id=ordered(state.card_id),
        effect_damage=catalog.container_damage[ordered_blueprint],
        effect_radius_units=catalog.container_radius_units[ordered_blueprint],
        effect_status_kind=torch.zeros_like(ready, dtype=torch.int8),
        effect_status_duration_ticks=torch.zeros_like(ready, dtype=torch.int32),
        tower_damage_multiplier=(
            catalog.container_tower_damage_multiplier[ordered_blueprint]
        ),
        building_damage_multiplier=(
            catalog.container_building_damage_multiplier[ordered_blueprint]
        ),
        hits_air=catalog.container_hits_air[ordered_blueprint],
        hits_ground=catalog.container_hits_ground[ordered_blueprint],
        nested_spawn_blueprint_id=torch.where(
            ready & ((nested_child > 0) | positive_area),
            ordered_blueprint + 1,
            torch.zeros_like(ordered_blueprint),
        ),
    )


def payload_spawn_commands(
    catalog: FastSpawnBlueprintCatalog,
    triggers: FastPayloadSpawnTriggers,
) -> FastSpawnCommands:
    """Decode stable-ordered container terminals into ordinary spawn waves."""

    shape = tuple(triggers.ready.shape)
    if len(shape) != 2:
        raise ValueError("payload spawn triggers must have shape [batch, commands]")
    for name, dtype in (
        ("ready", torch.bool),
        ("payload_stable_id", torch.int64),
        ("source_id", torch.int64),
        ("owner", torch.int8),
        ("blueprint_id", torch.int64),
        ("x_units", torch.int32),
        ("y_units", torch.int32),
    ):
        value = getattr(triggers, name)
        if tuple(value.shape) != shape or value.device != catalog.device:
            raise ValueError(f"{name} must match trigger shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if catalog.blueprint_count == 0:
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=catalog.device)
        zeros_i32 = torch.zeros(shape, dtype=torch.int32, device=catalog.device)
        return FastSpawnCommands(
            ready=torch.zeros(shape, dtype=torch.bool, device=catalog.device),
            owner=triggers.owner,
            child_card_id=zeros_i64,
            x_units=triggers.x_units,
            y_units=triggers.y_units,
            count=zeros_i32,
            radius_units=zeros_i32,
            deploy_ticks=zeros_i32,
        )
    known = (triggers.blueprint_id > 0) & (
        triggers.blueprint_id <= catalog.blueprint_count
    )
    row = (triggers.blueprint_id - 1).clamp(0, catalog.blueprint_count - 1)
    child = catalog.container_nested_child_card_id[row]
    ready = triggers.ready & known & (child > 0)
    raw_radius = catalog.container_nested_radius_units[row]
    child_radius = catalog.fast_cards.collision_radius_units[
        child.clamp(0, catalog.fast_cards.size - 1)
    ]
    return FastSpawnCommands(
        ready=ready,
        owner=triggers.owner,
        child_card_id=child,
        x_units=triggers.x_units,
        y_units=triggers.y_units,
        count=catalog.container_nested_count[row],
        radius_units=torch.where(raw_radius > 0, raw_radius, child_radius).to(
            torch.int32
        ),
        deploy_ticks=catalog.container_nested_deploy_ticks[row],
    )


def positive_area_activation_commands(
    catalog: FastSpawnBlueprintCatalog,
    triggers: FastPayloadSpawnTriggers,
) -> tuple[FastPositiveBuffAreaAllocationCommands, FastPayloadEffectCommands]:
    """Decode a delayed payload terminal into a field and enemy damage nova."""

    shape = tuple(triggers.ready.shape)
    if len(shape) != 2:
        raise ValueError("payload spawn triggers must have shape [batch, commands]")
    for name, dtype in (
        ("ready", torch.bool),
        ("payload_stable_id", torch.int64),
        ("source_id", torch.int64),
        ("owner", torch.int8),
        ("blueprint_id", torch.int64),
        ("x_units", torch.int32),
        ("y_units", torch.int32),
    ):
        value = getattr(triggers, name)
        if tuple(value.shape) != shape or value.device != catalog.device:
            raise ValueError(f"{name} must match trigger shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if catalog.blueprint_count == 0:
        ready = torch.zeros(shape, dtype=torch.bool, device=catalog.device)
        zeros_i8 = torch.zeros(shape, dtype=torch.int8, device=catalog.device)
        zeros_i32 = torch.zeros(shape, dtype=torch.int32, device=catalog.device)
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=catalog.device)
        zeros_f32 = torch.zeros(shape, dtype=torch.float32, device=catalog.device)
        ones_f32 = torch.ones(shape, dtype=torch.float32, device=catalog.device)
        return (
            FastPositiveBuffAreaAllocationCommands(
                ready=ready,
                stable_id=triggers.payload_stable_id,
                owner=triggers.owner,
                center_x_units=triggers.x_units,
                center_y_units=triggers.y_units,
                radius_units=zeros_i32,
                lifetime_ticks=zeros_i32,
                scan_interval_ticks=zeros_i32,
                recipient_duration_ticks=zeros_i32,
                movement_speed_multiplier=ones_f32,
                attack_cooldown_multiplier=ones_f32,
            ),
            FastPayloadEffectCommands(
                ready=ready,
                payload_stable_id=triggers.payload_stable_id,
                source_id=zeros_i64,
                owner=triggers.owner,
                effect_card_id=zeros_i64,
                x_units=triggers.x_units,
                y_units=triggers.y_units,
                damage=zeros_f32,
                radius_units=zeros_i32,
                status_kind=zeros_i8,
                status_duration_ticks=zeros_i32,
                tower_damage_multiplier=ones_f32,
                building_damage_multiplier=ones_f32,
                hits_air=ready,
                hits_ground=ready,
            ),
        )
    known = (triggers.blueprint_id > 0) & (
        triggers.blueprint_id <= catalog.blueprint_count
    )
    row = (triggers.blueprint_id - 1).clamp(0, catalog.blueprint_count - 1)
    ready = (
        triggers.ready
        & known
        & catalog.container_positive_area_enabled[row]
    )
    zeros_i8 = torch.zeros(shape, dtype=torch.int8, device=catalog.device)
    zeros_i32 = torch.zeros(shape, dtype=torch.int32, device=catalog.device)
    return (
        FastPositiveBuffAreaAllocationCommands(
            ready=ready,
            stable_id=triggers.payload_stable_id,
            owner=triggers.owner,
            center_x_units=triggers.x_units,
            center_y_units=triggers.y_units,
            radius_units=catalog.container_positive_area_radius_units[row],
            lifetime_ticks=(
                catalog.container_positive_area_lifetime_ticks[row]
            ),
            scan_interval_ticks=(
                catalog.container_positive_area_scan_interval_ticks[row]
            ),
            recipient_duration_ticks=(
                catalog.container_positive_area_recipient_duration_ticks[row]
            ),
            movement_speed_multiplier=(
                catalog.container_positive_area_movement_multiplier[row]
            ),
            attack_cooldown_multiplier=(
                catalog.container_positive_area_attack_multiplier[row]
            ),
        ),
        FastPayloadEffectCommands(
            ready=ready,
            payload_stable_id=triggers.payload_stable_id,
            source_id=torch.zeros_like(triggers.source_id),
            owner=triggers.owner,
            effect_card_id=catalog.root_card_id[row],
            x_units=triggers.x_units,
            y_units=triggers.y_units,
            damage=catalog.container_positive_area_damage[row],
            radius_units=(
                catalog.container_positive_area_damage_radius_units[row]
            ),
            status_kind=zeros_i8,
            status_duration_ticks=zeros_i32,
            tower_damage_multiplier=(
                catalog.container_positive_area_tower_damage_multiplier[row]
            ),
            building_damage_multiplier=(
                catalog.container_positive_area_building_damage_multiplier[row]
            ),
            hits_air=catalog.container_positive_area_damage_hits_air[row],
            hits_ground=catalog.container_positive_area_damage_hits_ground[row],
        ),
    )


def impact_spawn_commands(
    catalog: FastSpawnBlueprintCatalog,
    effects: FastEffectState,
    impacted: torch.Tensor,
) -> FastSpawnCommands:
    """Decode supported projectile impacts into fixed-shape spawn commands."""

    expected = (effects.batch_size, effects.max_effects)
    if tuple(impacted.shape) != expected:
        raise ValueError("impacted must have shape [batch, effects]")
    if impacted.device != catalog.device or impacted.dtype != torch.bool:
        raise ValueError("impacted must be bool on the blueprint device")
    if effects.device != catalog.device:
        raise ValueError("effects and blueprints must use the same device")
    if catalog.blueprint_count == 0:
        shape = (effects.batch_size, effects.max_effects)
        return FastSpawnCommands(
            ready=torch.zeros(shape, dtype=torch.bool, device=catalog.device),
            owner=effects.source_owner,
            child_card_id=torch.zeros(shape, dtype=torch.int64, device=catalog.device),
            x_units=effects.x_units,
            y_units=effects.y_units,
            count=torch.zeros(shape, dtype=torch.int32, device=catalog.device),
            radius_units=torch.zeros(shape, dtype=torch.int32, device=catalog.device),
            deploy_ticks=torch.zeros(shape, dtype=torch.int32, device=catalog.device),
        )

    source_card = effects.source_card_id
    known_source = (source_card > 0) & (source_card < len(catalog.cards.names))
    safe_source = source_card.clamp(0, len(catalog.cards.names) - 1)
    blueprint = catalog.impact_blueprint_by_card[safe_source]
    has_blueprint = known_source & (blueprint >= 0)
    safe_blueprint = blueprint.clamp(0, max(0, catalog.blueprint_count - 1))
    child = catalog.child_card_id[safe_blueprint]
    raw_radius = catalog.radius_units[safe_blueprint]
    child_radius = catalog.fast_cards.collision_radius_units[
        child.clamp(0, catalog.fast_cards.size - 1)
    ]
    return FastSpawnCommands(
        ready=impacted & has_blueprint,
        owner=effects.source_owner,
        child_card_id=child,
        x_units=effects.x_units,
        y_units=effects.y_units,
        count=catalog.count[safe_blueprint].to(torch.int32),
        radius_units=torch.where(raw_radius > 0, raw_radius, child_radius).to(
            torch.int32
        ),
        deploy_ticks=catalog.deploy_ticks[safe_blueprint],
    )


def rolling_spawn_commands(
    catalog: FastSpawnBlueprintCatalog,
    triggers: FastRollingSpawnTriggers,
) -> FastSpawnCommands:
    """Resolve rolling terminal triggers through the typed child catalog."""

    shape = tuple(triggers.ready.shape)
    if len(shape) != 2:
        raise ValueError("rolling spawn triggers must have shape [batch, commands]")
    if triggers.ready.device != catalog.device:
        raise ValueError("rolling triggers and blueprints must share a device")
    if catalog.blueprint_count == 0:
        return FastSpawnCommands(
            ready=torch.zeros_like(triggers.ready),
            owner=triggers.owner,
            child_card_id=torch.zeros_like(triggers.source_card_id),
            x_units=triggers.x_units,
            y_units=triggers.y_units,
            count=torch.zeros_like(triggers.count),
            radius_units=torch.zeros_like(triggers.x_units),
            deploy_ticks=torch.zeros_like(triggers.deploy_ticks),
        )
    known = (triggers.blueprint_id >= 0) & (
        triggers.blueprint_id < catalog.blueprint_count
    )
    row = triggers.blueprint_id.clamp(0, max(0, catalog.blueprint_count - 1))
    child = catalog.child_card_id[row]
    raw_radius = catalog.radius_units[row]
    child_radius = catalog.fast_cards.collision_radius_units[
        child.clamp(0, catalog.fast_cards.size - 1)
    ]
    return FastSpawnCommands(
        ready=triggers.ready & known & catalog.blueprint_supported[row],
        owner=triggers.owner,
        child_card_id=child,
        x_units=triggers.x_units,
        y_units=triggers.y_units,
        count=triggers.count,
        radius_units=torch.where(raw_radius > 0, raw_radius, child_radius).to(
            torch.int32
        ),
        deploy_ticks=triggers.deploy_ticks,
    )


def allocate_fast_spawns_(
    state: FastGymState,
    catalog: FastCardCatalog,
    commands: FastSpawnCommands,
    *,
    reserved_slot_floor: int = 0,
) -> FastSpawnAllocationResult:
    """Atomically materialize numeric spawn commands in command order."""

    shape = tuple(commands.ready.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("spawn commands must have shape [batch, commands]")
    if catalog.device != state.device:
        raise ValueError("state and catalog must use the same device")
    for name, dtype in (
        ("ready", torch.bool),
        ("owner", torch.int8),
        ("child_card_id", torch.int64),
        ("x_units", torch.int32),
        ("y_units", torch.int32),
        ("count", torch.int32),
        ("radius_units", torch.int32),
        ("deploy_ticks", torch.int32),
    ):
        value = getattr(commands, name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{name} must match command shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if not 0 <= reserved_slot_floor <= state.max_entities:
        raise ValueError("reserved_slot_floor must be within entity capacity")

    slots = torch.arange(state.max_entities, device=state.device).view(1, -1)
    free = ~state.active & (slots >= reserved_slot_floor)
    known = (commands.child_card_id > 0) & (commands.child_card_id < catalog.size)
    safe_card = commands.child_card_id.clamp(0, catalog.size - 1)
    valid = (
        commands.ready
        & known
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.count > 0)
        & (catalog.kind[safe_card] >= 0)
        & (catalog.hitpoints[safe_card] > 0)
        & ~state.game_over[:, None]
    )
    requested = torch.where(valid, commands.count, 0).to(torch.int64)
    start = requested.cumsum(dim=1) - requested
    available = free.sum(dim=1, dtype=torch.int64)
    accepted = valid & (start + requested <= available[:, None])
    accepted_count = torch.where(accepted, requested, 0)
    accepted_start = accepted_count.cumsum(dim=1) - accepted_count
    total = accepted_count.sum(dim=1)

    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    spawned = free & (free_rank >= 0) & (free_rank < total[:, None])
    claims = (
        spawned[:, :, None]
        & accepted[:, None, :]
        & (free_rank[:, :, None] >= accepted_start[:, None, :])
        & (
            free_rank[:, :, None]
            < accepted_start[:, None, :] + accepted_count[:, None, :]
        )
    )
    source_command = claims.to(torch.int64).argmax(dim=2)
    source_start = accepted_start.gather(1, source_command)
    child_index = (free_rank - source_start).clamp(min=0)
    source_count = commands.count.gather(1, source_command).clamp(min=1)
    source_card = commands.child_card_id.gather(1, source_command)
    safe_source_card = source_card.clamp(0, catalog.size - 1)
    source_radius = commands.radius_units.gather(1, source_command).clamp(min=0)
    phase = child_index.to(torch.float32) * (2.0 * torch.pi) / source_count
    offset_x = torch.round(torch.cos(phase) * source_radius).to(torch.int32)
    offset_y = torch.round(torch.sin(phase) * source_radius).to(torch.int32)
    offset_x.masked_fill_(source_count == 1, 0)
    offset_y.masked_fill_(source_count == 1, 0)

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source_command)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(spawned, value.to(field.dtype), field))

    write(state.active, torch.ones_like(spawned))
    write(state.stable_id, state.next_stable_id[:, None] + free_rank)
    write(state.kind, catalog.kind[safe_source_card])
    write(state.owner, gather(commands.owner))
    write(state.card_id, source_card)
    write(state.x_units, gather(commands.x_units) + offset_x)
    write(state.y_units, gather(commands.y_units) + offset_y)
    write(state.hp, catalog.hitpoints[safe_source_card])
    write(state.max_hp, catalog.hitpoints[safe_source_card])
    write(state.target_id, torch.zeros_like(free_rank))
    write(state.damage, catalog.damage[safe_source_card])
    write(state.range_units, catalog.range_units[safe_source_card])
    write(state.sight_range_units, catalog.sight_range_units[safe_source_card])
    write(
        state.speed_units_per_tick,
        catalog.speed_units_per_tick[safe_source_card],
    )
    write(
        state.hit_cooldown_ticks,
        catalog.hit_cooldown_ticks[safe_source_card],
    )
    write(state.deploy_ticks, gather(commands.deploy_ticks).clamp(min=0))
    write(state.cooldown_ticks, torch.zeros_like(free_rank))
    state.next_stable_id.add_(total)
    return FastSpawnAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=valid & ~accepted,
        spawned_mask=spawned,
        source_command=torch.where(spawned, source_command, -1),
    )


__all__ = [
    "FastSpawnAllocationResult",
    "FastSpawnBlueprintCatalog",
    "FastSpawnCommands",
    "FastSpawnTrigger",
    "allocate_fast_spawns_",
    "death_payload_container_commands",
    "impact_spawn_commands",
    "payload_spawn_commands",
    "positive_area_activation_commands",
    "rolling_spawn_commands",
]
