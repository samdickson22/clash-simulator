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
from typing import Any

import torch

from clasher.card_types import CardStatsCompat
from clasher.data import CardDataLoader
from clasher.factory.card_factory import card_from_gamedata
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.mechanics.shared.death_effects import DeathSpawn
from clasher.mechanics.shared.spawner import PeriodicSpawner

from .catalog import TensorCardCatalog
from .simple_catalog import FastCardCatalog
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
            if any(
                isinstance(value, dict)
                and (value.get("spawnCharacter") or value.get("spawnCharacterData"))
                for value in subactions
            ):
                first = next(value for value in subactions if isinstance(value, dict))
                child = first.get("spawnCharacterData")
                requirements.append(
                    _SpawnRequirement(
                        root_name=root_name,
                        trigger=FastSpawnTrigger.SCHEDULED_ACTION,
                        child_name=str(
                            (child or {}).get("name")
                            or first.get("spawnCharacter")
                            or ""
                        ),
                        child_data=(
                            copy.deepcopy(child) if isinstance(child, dict) else None
                        ),
                        count=len(subactions),
                        radius_units=max(0, int(area.get("radius", 0) or 0)),
                        deploy_ticks=_ticks(first.get("deployTime")),
                        first_delay_ticks=0,
                        interval_ticks=0,
                        max_waves=1,
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
            if not isinstance(data, dict) or data.get("hitpoints") is None:
                continue
            key = _payload_key(requirement.child_name, data)
            payloads[key] = data

        label_by_key: dict[tuple[str, str], str] = {}
        visible_by_label: dict[str, str] = {}
        for (name, serialized), data in sorted(payloads.items()):
            label = _payload_label(name, serialized)
            label_by_key[(name, serialized)] = label
            visible_by_label[label] = name
            overlay.add_character(label, name, data)

        expanded_names = tuple(sorted({*roots, *visible_by_label}))
        cards = TensorCardCatalog.compile(
            overlay,
            expanded_names,
            device=base_cards.device,
        )
        fast_cards = FastCardCatalog.from_tensor_catalog(cards, loader=overlay)
        visible_names = tuple(visible_by_label.get(name, name) for name in cards.names)

        def tensor(values: Iterable[object], dtype: torch.dtype) -> torch.Tensor:
            return torch.tensor(tuple(values), dtype=dtype, device=cards.device)

        child_ids: list[int] = []
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
                    and not child_definition.card_definition.mechanics
                )
            trigger_supported = requirement.trigger in {
                FastSpawnTrigger.DEATH,
                FastSpawnTrigger.PROJECTILE_IMPACT,
            }
            child_ids.append(child_id)
            supported.append(
                trigger_supported and child_supported and requirement.count > 0
            )

        root_required = torch.zeros(
            cards.size if hasattr(cards, "size") else len(cards.names),
            dtype=torch.bool,
            device=cards.device,
        )
        root_supported = torch.zeros_like(root_required)
        root_rows: dict[int, list[int]] = {}
        for row, requirement in enumerate(requirements):
            root_id = cards.name_to_id[requirement.root_name]
            root_required[root_id] = True
            root_rows.setdefault(root_id, []).append(row)
        for root_id, operation_rows in root_rows.items():
            root_supported[root_id] = all(supported[row] for row in operation_rows)

        return cls(
            device=cards.device,
            cards=cards,
            fast_cards=fast_cards,
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
]
