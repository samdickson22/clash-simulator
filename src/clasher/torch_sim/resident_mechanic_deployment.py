"""Transactional deployment admission for represented mechanic families."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields

import torch

from clasher.data import CardDataLoader

from .actions import TensorActionCatalog
from .catalog import MECHANIC_OPCODE, TensorCardCatalog
from .deployment import TensorCommandMaterializer, TensorDeploymentCatalog
from .movement import integer_sqrt_tensor
from .runtime_deployment import TensorRuntimeDeployment, TensorRuntimeDeploymentResult
from .runtime_state import TensorBattleRuntime
from .tensor_ops import scatter_any_


@dataclass(frozen=True)
class TensorMechanicDeploymentCatalog:
    cards: TensorCardCatalog
    owner_names: tuple[str, ...]
    owner_opcode_capability: torch.Tensor
    owner_card_supported: torch.Tensor
    card_owner: torch.Tensor
    card_supported: torch.Tensor
    admitted_opcode: torch.Tensor
    underground_deployment: torch.Tensor
    underground_speed_units: torch.Tensor

    @classmethod
    def compile(
        cls,
        cards: TensorCardCatalog,
        owner_opcodes: Mapping[str, Sequence[int]],
        *,
        owner_card_supported: Mapping[str, torch.Tensor] | None = None,
        loader: CardDataLoader | None = None,
    ) -> TensorMechanicDeploymentCatalog:
        if not owner_opcodes:
            raise ValueError("at least one retained owner capability is required")
        names = tuple(owner_opcodes)
        maximum_opcode = max(
            int(cards.mechanic_opcode.max().item()),
            max(
                (int(code) for values in owner_opcodes.values() for code in values),
                default=0,
            ),
        )
        owner_opcode = torch.zeros(
            (len(names), maximum_opcode + 1),
            dtype=torch.bool,
            device=cards.device,
        )
        for owner_index, name in enumerate(names):
            for raw in owner_opcodes[name]:
                opcode = int(raw)
                if opcode <= 0 or opcode > maximum_opcode:
                    raise ValueError(
                        f"invalid mechanic opcode {opcode} for owner {name!r}"
                    )
                owner_opcode[owner_index, opcode] = True
        supported = torch.ones(
            (len(names), len(cards.names)), dtype=torch.bool, device=cards.device
        )
        if owner_card_supported is not None:
            unknown = set(owner_card_supported) - set(names)
            if unknown:
                raise ValueError(
                    f"card support supplied for unknown owners: {sorted(unknown)}"
                )
            for owner_index, name in enumerate(names):
                if name not in owner_card_supported:
                    continue
                value = torch.as_tensor(
                    owner_card_supported[name], dtype=torch.bool, device=cards.device
                )
                if value.shape != (len(cards.names),):
                    raise ValueError("owner card support must have shape [card]")
                supported[owner_index] = value

        opcodes = cards.mechanic_opcode.to(torch.int64)
        present = opcodes > 0
        in_range = opcodes <= maximum_opcode
        safe = opcodes.clamp(0, maximum_opcode)
        represented = owner_opcode[:, safe].permute(1, 2, 0) & supported.T[:, None, :]
        opcode_supported = represented.any(dim=2) & in_range
        card_supported = (~present | opcode_supported).all(dim=1)
        card_owner = (represented & present[..., None]).any(dim=1).T & card_supported[
            None, :
        ]
        admitted = owner_opcode.any(dim=0)
        underground_opcode = MECHANIC_OPCODE.get("UndergroundDeployment", -1)
        underground = (opcodes == underground_opcode).any(dim=1)
        underground_speed = torch.zeros(
            len(cards.names), dtype=torch.int64, device=cards.device
        )
        if underground.any():
            if loader is None:
                raise ValueError(
                    "serialized loader is required for UndergroundDeployment"
                )
            for card_id, name in enumerate(cards.names[1:], start=1):
                if not bool(underground[card_id].item()):
                    continue
                stats = loader.get_card(name)
                entry = {} if stats is None else getattr(stats, "_raw_entry", {}) or {}
                raw_entry: Mapping[str, object] = (
                    entry if isinstance(entry, Mapping) else {}
                )
                character_entry = raw_entry.get("summonCharacterData", {})
                character: Mapping[str, object] = (
                    character_entry if isinstance(character_entry, Mapping) else {}
                )
                speed_value = character.get("spawnPathfindSpeed", 0) or 0
                if not isinstance(speed_value, (int, float, str)):
                    speed_value = 0
                underground_speed[card_id] = max(
                    1,
                    round(float(speed_value)),
                )
        return cls(
            cards,
            names,
            owner_opcode,
            supported,
            card_owner,
            card_supported,
            admitted,
            underground,
            underground_speed,
        )

    def owner_index(self, name: str) -> int:
        try:
            return self.owner_names.index(name)
        except ValueError as exc:
            raise KeyError(name) from exc


@dataclass
class TensorMechanicDeploymentState:
    owner_entity_id: torch.Tensor

    @classmethod
    def empty(
        cls,
        catalog: TensorMechanicDeploymentCatalog,
        runtime: TensorBattleRuntime,
    ) -> TensorMechanicDeploymentState:
        return cls(
            torch.zeros(
                (len(catalog.owner_names), runtime.batch_size, runtime.max_entities),
                dtype=torch.int64,
                device=runtime.device,
            )
        )

    def clone(self) -> TensorMechanicDeploymentState:
        return type(self)(self.owner_entity_id.clone())

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorMechanicDeploymentState:
        index = torch.as_tensor(
            rows, dtype=torch.int64, device=self.owner_entity_id.device
        )
        return type(self)(self.owner_entity_id.index_select(1, index).clone())

    def reset_rows_(
        self,
        rows: Sequence[int] | torch.Tensor,
        source: TensorMechanicDeploymentState,
        source_rows: Sequence[int] | torch.Tensor | None = None,
    ) -> None:
        destination = torch.as_tensor(
            rows, dtype=torch.int64, device=self.owner_entity_id.device
        )
        selected = (
            destination
            if source_rows is None
            else torch.as_tensor(
                source_rows, dtype=torch.int64, device=self.owner_entity_id.device
            )
        )
        if destination.shape != selected.shape:
            raise ValueError("source and destination rows must align")
        self.owner_entity_id[:, destination] = source.owner_entity_id[:, selected]


@dataclass(frozen=True)
class MechanicDeploymentResult:
    deployment: TensorRuntimeDeploymentResult
    committed: torch.Tensor
    capability_rejected: torch.Tensor
    spawned: torch.Tensor
    owner_spawn_mask: torch.Tensor
    owner_entity_id: torch.Tensor
    underground_destination_units: torch.Tensor
    underground_travel_duration_seconds: torch.Tensor

    def owner_mask(
        self, catalog: TensorMechanicDeploymentCatalog, name: str
    ) -> torch.Tensor:
        return self.owner_spawn_mask[catalog.owner_index(name)]


def _copy_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape == right.shape
            and left.shape[0] == batch
        ):
            left[rows] = right[rows]


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    for left, right in (
        (destination.battle, source.battle),
        (destination.battle.rng, source.battle.rng),
        (destination.status, source.status),
        (destination.phases, source.phases),
        (destination.events, source.events),
    ):
        _copy_rows_(left, right, rows)
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


class TensorResidentMechanicDeployment:
    """Admit complete mechanic sets and publish owner-specific spawn handoffs."""

    def __init__(
        self,
        catalog: TensorMechanicDeploymentCatalog,
        deployment_catalog: TensorDeploymentCatalog,
        runtime: TensorBattleRuntime,
    ) -> None:
        if deployment_catalog.cards is not catalog.cards:
            raise ValueError("mechanic and deployment catalogs must share cards")
        admitted = torch.nonzero(catalog.admitted_opcode, as_tuple=False).flatten()
        self.catalog = catalog
        self.materializer = TensorCommandMaterializer(
            deployment_catalog,
            admitted_mechanic_opcodes=admitted.tolist(),
        )
        self.driver = TensorRuntimeDeployment(
            TensorActionCatalog.compile(catalog.cards), self.materializer
        )
        self.driver.prepare_runtime(runtime)
        self.state = TensorMechanicDeploymentState.empty(catalog, runtime)

    @property
    def device(self) -> torch.device:
        return self.catalog.cards.device

    def apply(
        self,
        runtime: TensorBattleRuntime,
        action_ids: torch.Tensor,
        *,
        player_order: torch.Tensor | None = None,
    ) -> MechanicDeploymentResult:
        if runtime.device != self.device or runtime.catalog is not self.catalog.cards:
            raise ValueError("runtime and mechanic deployment layouts differ")
        actions = torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        if actions.shape != (runtime.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        speculative = runtime.clone()
        speculative.battle.rng = runtime.battle.rng.clone()
        deployment = self.driver.apply(
            speculative,
            actions,
            player_order=player_order,
        )
        commands = deployment.ingress.commands
        command_supported = self.catalog.card_supported[commands.card_id]
        rejected = torch.zeros(runtime.batch_size, dtype=torch.bool, device=self.device)
        if commands.card_id.numel():
            scatter_any_(rejected, 0, commands.battle_index, ~command_supported)
        committed = deployment.committed & ~rejected
        spawned = torch.zeros_like(runtime.entity_pool.active)
        scatter_any_(
            spawned,
            1,
            deployment.deployment.allocation.slots.clamp_min(0),
            deployment.deployment.allocation.valid & committed[:, None],
        )
        spawned_card = deployment.deployment.spawned_card_id.clamp(
            0, len(self.catalog.cards.names) - 1
        )
        underground = self.catalog.underground_deployment[spawned_card] & spawned
        destination = torch.stack(
            (
                speculative.battle.entity_x_units,
                speculative.battle.entity_y_units,
            ),
            dim=-1,
        ).to(torch.int64)
        origin_x = torch.full_like(speculative.battle.entity_x_units, 9_000)
        origin_y = torch.where(
            speculative.battle.entity_player == 0,
            torch.full_like(speculative.battle.entity_y_units, 2_500),
            torch.full_like(speculative.battle.entity_y_units, 29_500),
        )
        origin = torch.stack((origin_x, origin_y), dim=-1).to(torch.int64)
        delta = destination - origin
        distance = integer_sqrt_tensor((delta * delta).sum(dim=-1))
        speed = self.catalog.underground_speed_units[spawned_card].clamp_min(1)
        ticks = torch.div(
            torch.clamp(distance - speed, min=0) + speed - 1,
            speed,
            rounding_mode="floor",
        ).clamp_min(1)
        ticks = torch.where(distance > 0, ticks, 0)
        travel_duration = ticks.to(torch.float64) * 0.05
        speculative.battle.entity_x_units.copy_(
            torch.where(underground, origin_x, speculative.battle.entity_x_units)
        )
        speculative.battle.entity_y_units.copy_(
            torch.where(underground, origin_y, speculative.battle.entity_y_units)
        )
        speculative.battle.entity_deploy_delay.copy_(
            torch.where(
                underground,
                speculative.battle.entity_deploy_delay + travel_duration,
                speculative.battle.entity_deploy_delay,
            )
        )
        speculative.battle.entity_placement_pending |= underground
        event_match = (
            speculative.events.source_id[:, :, None]
            == speculative.battle.entity_id[:, None, :]
        ) & underground[:, None, :]
        event_underground = event_match.any(dim=2)
        event_slot = event_match.to(torch.int64).argmax(dim=2)
        speculative.events.x_units.copy_(
            torch.where(
                event_underground,
                speculative.battle.entity_x_units.gather(1, event_slot),
                speculative.events.x_units,
            )
        )
        speculative.events.y_units.copy_(
            torch.where(
                event_underground,
                speculative.battle.entity_y_units.gather(1, event_slot),
                speculative.events.y_units,
            )
        )
        owner_spawn = self.catalog.card_owner[:, spawned_card] & spawned[None, :, :]
        owner_ids = speculative.battle.entity_id[None, :, :].expand_as(owner_spawn)
        owner_ids = torch.where(owner_spawn, owner_ids, 0)
        preview = self.state.clone()
        preview.owner_entity_id.masked_fill_(spawned[None, :, :], 0)
        preview.owner_entity_id.copy_(
            torch.where(owner_spawn, owner_ids, preview.owner_entity_id)
        )
        _copy_runtime_rows_(runtime, speculative, committed)
        selected = torch.nonzero(committed, as_tuple=False).flatten()
        self.state.reset_rows_(selected, preview, selected)
        return MechanicDeploymentResult(
            deployment,
            committed,
            rejected,
            spawned,
            owner_spawn,
            owner_ids,
            torch.where(underground[..., None], destination, 0),
            torch.where(underground, travel_duration, 0.0),
        )


__all__ = [
    "MechanicDeploymentResult",
    "TensorMechanicDeploymentCatalog",
    "TensorMechanicDeploymentState",
    "TensorResidentMechanicDeployment",
]
