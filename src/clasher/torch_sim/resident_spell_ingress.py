"""Atomic resident action ingress for bridge-supported spell commands."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState

from .actions import TensorIngressResult
from .catalog import CardKindOpcode, TensorCardCatalog
from .projectile_bridge import (
    BridgePayloadKind,
    TensorResidentProjectileSpellBridge,
)
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorResidentSpellIngressResult:
    committed: torch.Tensor
    unsupported: torch.Tensor
    unsupported_reasons: tuple[str | None, ...]
    action_success: torch.Tensor
    player_order: torch.Tensor
    spell_command: torch.Tensor


@dataclass(frozen=True)
class TensorResidentSpellPreflight:
    """Static episode-safe spell classification for one ingress queue."""

    command_spell: torch.Tensor
    command_supported: torch.Tensor
    row_has_spell: torch.Tensor
    row_mixed: torch.Tensor
    row_supported: torch.Tensor


def _clone_tensor_owner(value: object) -> object:
    cloned = copy.copy(value)
    for descriptor in fields(value):  # type: ignore[arg-type]
        item = getattr(value, descriptor.name)
        if isinstance(item, torch.Tensor):
            setattr(cloned, descriptor.name, item.clone())
    return cloned


def _clone_object_phase(phase: TensorRuntimeObjectPhase) -> TensorRuntimeObjectPhase:
    cloned = _clone_tensor_owner(phase)
    cloned.objects = _clone_tensor_owner(phase.objects)  # type: ignore[attr-defined]
    return cloned  # type: ignore[return-value]


def _copy_batch_rows(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.shape == right.shape
            and left.ndim > 0
            and left.shape[0] == batch
        ):
            left[rows] = right[rows]


def _copy_runtime_rows(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    _copy_batch_rows(destination.battle, source.battle, rows)
    _copy_batch_rows(destination.battle.rng, source.battle.rng, rows)
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    _copy_batch_rows(destination.status, source.status, rows)
    _copy_batch_rows(destination.phases, source.phases, rows)
    _copy_batch_rows(destination.events, source.events, rows)
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]
    destination.assert_invariants()


def _copy_phase_rows(
    destination: TensorRuntimeObjectPhase,
    source: TensorRuntimeObjectPhase,
    rows: torch.Tensor,
    blueprint_indices: torch.Tensor,
) -> None:
    _copy_batch_rows(destination, source, rows)
    _copy_batch_rows(destination.objects, source.objects, rows)
    for descriptor in fields(destination):
        if not descriptor.name.startswith("blueprint_"):
            continue
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and left.shape == right.shape:
            left[blueprint_indices] = right[blueprint_indices]


def _copy_bridge_rows(
    destination: TensorResidentProjectileSpellBridge,
    source: TensorResidentProjectileSpellBridge,
    rows: torch.Tensor,
) -> None:
    _copy_batch_rows(destination, source, rows)
    blueprint_indices = source.blueprint_for_slot[rows].flatten()
    for descriptor in fields(destination):
        if (
            not descriptor.name.startswith("blueprint_")
            or descriptor.name == "blueprint_for_slot"
        ):
            continue
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and left.shape == right.shape:
            left[blueprint_indices] = right[blueprint_indices]


class TensorResidentSpellActionIngress:
    """Commit simultaneous spell commands without partial row mutation."""

    def __init__(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
        cards: TensorCardCatalog,
        *,
        catalog_to_core: torch.Tensor | None = None,
        episode_supported_core: torch.Tensor | None = None,
    ) -> None:
        if runtime.catalog is not cards:
            raise ValueError("runtime and action catalog must share metadata")
        if runtime.device != bridge.catalog.device or runtime.device != objects.device:
            raise ValueError("spell ingress owners must share a device")
        self.runtime = runtime
        self.objects = objects
        self.bridge = bridge
        self.cards = cards
        self.device = runtime.device
        self.catalog_to_core = (
            torch.tensor(
                [
                    runtime.battle.card_to_id.get(name, -1) if name else 0
                    for name in cards.names
                ],
                dtype=torch.int64,
                device=self.device,
            )
            if catalog_to_core is None
            else catalog_to_core
        )
        if self.catalog_to_core.shape != (len(cards.names),):
            raise ValueError("spell catalog/core mapping has an invalid shape")
        if episode_supported_core is None:
            projectile = bridge.catalog.kind == int(BridgePayloadKind.PROJECTILE_SPELL)
            # The resident bridge now closes grouped-wave lifecycle and
            # ordinary one-tile knockback. Longer serialized knockback still
            # differs by one fixed-point unit for some impact geometries, so
            # those rows remain episode-level fallback until that kernel is
            # exact as well.
            unclosed_knockback = bridge.catalog.knockback_units > 1_000
            self.episode_supported_core = bridge.catalog.supported & ~(
                projectile & unclosed_knockback
            )
        else:
            self.episode_supported_core = episode_supported_core
        if self.episode_supported_core.shape != bridge.catalog.supported.shape:
            raise ValueError("episode spell support has an invalid shape")

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        battles: Sequence[BattleState],
        cards: TensorCardCatalog,
    ) -> TensorResidentSpellActionIngress:
        bridge = TensorResidentProjectileSpellBridge.from_battles(
            runtime, objects, battles
        )
        return cls(runtime, objects, bridge, cards)

    def fork(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
    ) -> TensorResidentSpellActionIngress:
        """Bind retained immutable spell metadata to cloned mutable owners."""

        return type(self)(
            runtime,
            objects,
            bridge,
            self.cards,
            catalog_to_core=self.catalog_to_core,
            episode_supported_core=self.episode_supported_core,
        )

    def preflight(self, ingress: TensorIngressResult) -> TensorResidentSpellPreflight:
        commands = ingress.commands
        command_spell = (
            self.cards.kind[commands.card_id] == int(CardKindOpcode.SPELL)
        ) & ~commands.is_ability
        core_card = self.catalog_to_core[commands.card_id]
        command_supported = (
            command_spell
            & (core_card >= 0)
            & self.episode_supported_core[core_card.clamp_min(0)]
        )
        spell_count = torch.zeros(
            self.runtime.batch_size, dtype=torch.int32, device=self.device
        )
        nonspell_count = torch.zeros_like(spell_count)
        unsupported_count = torch.zeros_like(spell_count)
        if commands.battle_index.numel():
            spell_count.scatter_add_(
                0, commands.battle_index, command_spell.to(torch.int32)
            )
            nonspell_count.scatter_add_(
                0, commands.battle_index, (~command_spell).to(torch.int32)
            )
            unsupported_count.scatter_add_(
                0, commands.battle_index, (~command_supported).to(torch.int32)
            )
        row_has_spell = spell_count > 0
        row_mixed = row_has_spell & (nonspell_count > 0)
        row_supported = row_has_spell & ~row_mixed & (unsupported_count == 0)
        return TensorResidentSpellPreflight(
            command_spell=command_spell,
            command_supported=command_supported,
            row_has_spell=row_has_spell,
            row_mixed=row_mixed,
            row_supported=row_supported,
        )

    def _commit_card_transition(
        self,
        runtime: TensorBattleRuntime,
        ingress: TensorIngressResult,
        rows: torch.Tensor,
        catalog_to_core: torch.Tensor,
    ) -> None:
        mapped_hand = catalog_to_core[ingress.hand_ids]
        mapped_cycle = catalog_to_core[ingress.cycle_ids]
        runtime.battle.hand[rows] = mapped_hand[rows]
        width = ingress.cycle_ids.shape[2]
        if width > runtime.battle.cycle_queue.shape[2]:
            raise OverflowError("runtime card-cycle capacity exhausted")
        runtime.battle.cycle_queue[rows] = 0
        runtime.battle.cycle_queue[rows, :, :width] = mapped_cycle[rows]
        runtime.battle.cycle_queue_length[rows] = ingress.cycle_length[rows].to(
            runtime.battle.cycle_queue_length.dtype
        )
        runtime.battle.elixir[rows] = ingress.elixir[rows]

    def apply(
        self,
        ingress: TensorIngressResult,
        *,
        player_order: torch.Tensor | None = None,
    ) -> TensorResidentSpellIngressResult:
        batch = self.runtime.batch_size
        commands = ingress.commands
        if ingress.hand_ids.shape[:2] != (batch, 2):
            raise ValueError("ingress batch differs from resident runtime")
        if commands.battle_index.numel() and bool(
            (
                (commands.battle_index < 0)
                | (commands.battle_index >= batch)
                | (commands.card_id < 0)
                | (commands.card_id >= len(self.cards.names))
            )
            .any()
            .item()
        ):
            raise ValueError("command index is outside resident spell catalog")

        speculative_runtime = self.runtime.clone()
        speculative_runtime.battle.rng = self.runtime.battle.rng.clone()
        speculative_objects = _clone_object_phase(self.objects)
        speculative_bridge = _clone_tensor_owner(self.bridge)
        assert isinstance(speculative_bridge, TensorResidentProjectileSpellBridge)

        if player_order is None:
            choice = speculative_runtime.battle.rng.randrange(2)
            order = torch.stack((1 - choice, choice), dim=1)
        else:
            order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
            if order.shape != (batch, 2) or not bool(
                (
                    torch.sort(order, dim=1).values
                    == torch.tensor([0, 1], dtype=torch.int64, device=self.device)
                )
                .all()
                .item()
            ):
                raise ValueError("player_order rows must be permutations of (0, 1)")

        catalog_to_core = self.catalog_to_core
        command_count = int(commands.card_id.numel())
        command_spell = (
            self.cards.kind[commands.card_id] == int(CardKindOpcode.SPELL)
        ) & ~commands.is_ability
        non_spell = ~command_spell
        bad_row = torch.zeros(batch, dtype=torch.bool, device=self.device)
        if command_count:
            bad_row.scatter_reduce_(
                0,
                commands.battle_index,
                non_spell,
                reduce="amax",
                include_self=True,
            )
        transition_known = (
            (catalog_to_core[ingress.hand_ids] >= 0).all(dim=2)
            & (catalog_to_core[ingress.cycle_ids] >= 0).all(dim=2)
        ).all(dim=1)
        row_supported = self.runtime.supported & ~bad_row & transition_known
        unsupported_reasons: list[str | None] = [None] * batch
        for row in (
            torch.nonzero(~self.runtime.supported, as_tuple=False).flatten().tolist()
        ):
            unsupported_reasons[row] = "resident runtime row is unsupported"
        for row in torch.nonzero(bad_row, as_tuple=False).flatten().tolist():
            unsupported_reasons[row] = "non-spell command requires another ingress"
        for row in torch.nonzero(~transition_known, as_tuple=False).flatten().tolist():
            unsupported_reasons[row] = "card transition references an unknown core card"

        for rank in range(2):
            player = order[:, rank]
            if command_count:
                matches = (
                    commands.battle_index[None, :]
                    == torch.arange(batch, device=self.device)[:, None]
                ) & (commands.player_id[None, :] == player[:, None])
                found = matches.any(dim=1)
                command_index = matches.to(torch.int64).argmax(dim=1)
                catalog_card = commands.card_id[command_index]
                core_card = catalog_to_core[catalog_card]
                x = commands.world_x_units[command_index]
                y = commands.world_y_units[command_index]
                valid = found & row_supported
            else:
                core_card = torch.zeros(batch, dtype=torch.int64, device=self.device)
                x = torch.zeros_like(core_card)
                y = torch.zeros_like(core_card)
                valid = torch.zeros(batch, dtype=torch.bool, device=self.device)
            supported = speculative_bridge.materialize_spell_actions_(
                speculative_runtime,
                speculative_objects,
                card_ids=core_card,
                player_ids=player,
                target_x_units=x,
                target_y_units=y,
                valid=valid,
            )
            failed = valid & ~supported
            row_supported &= ~failed
            for row in torch.nonzero(failed, as_tuple=False).flatten().tolist():
                card = int(core_card[row])
                unsupported_reasons[row] = (
                    speculative_bridge.catalog.unsupported_reason[card]
                    or "spell payload capacity is unavailable"
                )

        self._commit_card_transition(
            speculative_runtime, ingress, row_supported, catalog_to_core
        )
        _copy_runtime_rows(self.runtime, speculative_runtime, row_supported)
        blueprint_indices = speculative_bridge.blueprint_for_slot[
            row_supported
        ].flatten()
        _copy_phase_rows(
            self.objects,
            speculative_objects,
            row_supported,
            blueprint_indices,
        )
        _copy_bridge_rows(self.bridge, speculative_bridge, row_supported)
        action_success = ingress.accepted & row_supported[:, None]
        return TensorResidentSpellIngressResult(
            committed=row_supported,
            unsupported=~row_supported,
            unsupported_reasons=tuple(unsupported_reasons),
            action_success=action_success,
            player_order=order,
            spell_command=command_spell,
        )


__all__ = [
    "TensorResidentSpellActionIngress",
    "TensorResidentSpellIngressResult",
    "TensorResidentSpellPreflight",
]
