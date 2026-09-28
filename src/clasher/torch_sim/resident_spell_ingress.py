"""Atomic resident action ingress for bridge-supported spell commands."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState

from .actions import TensorIngressResult
from .catalog import CardKindOpcode, TensorCardCatalog
from .projectile_bridge import TensorResidentProjectileSpellBridge
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime
from .tensor_ops import scatter_any_


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


def _copy_tensor_fields(destination: object, source: object) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
            if left.shape != right.shape or left.dtype != right.dtype:
                raise ValueError(
                    f"spell transaction plane {descriptor.name!r} changed layout"
                )
            left.copy_(right)


def _refresh_runtime(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
) -> None:
    _copy_tensor_fields(destination.battle, source.battle)
    _copy_tensor_fields(destination.battle.rng, source.battle.rng)
    destination.battle.card_names = source.battle.card_names
    destination.battle.card_to_id = source.battle.card_to_id
    destination.card_catalog_index.copy_(source.card_catalog_index)
    destination.entity_pool.active.copy_(source.entity_pool.active)
    destination.entity_pool.next_entity_id.copy_(source.entity_pool.next_entity_id)
    _copy_tensor_fields(destination.status, source.status)
    _copy_tensor_fields(destination.phases, source.phases)
    _copy_tensor_fields(destination.events, source.events)
    destination.supported.copy_(source.supported)
    destination.dirty.copy_(source.dirty)


class _TensorResidentSpellTransactionWorkspace:
    """One retained speculative owner set shared by bound engine clones."""

    def __init__(self) -> None:
        self.runtime: TensorBattleRuntime | None = None
        self.objects: TensorRuntimeObjectPhase | None = None
        self.bridge: TensorResidentProjectileSpellBridge | None = None

    def acquire(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
    ) -> tuple[
        TensorBattleRuntime,
        TensorRuntimeObjectPhase,
        TensorResidentProjectileSpellBridge,
    ]:
        if self.runtime is None:
            self.runtime = runtime.clone()
            self.runtime.battle.rng = runtime.battle.rng.clone()
            self.objects = _clone_object_phase(objects)
            cloned_bridge = _clone_tensor_owner(bridge)
            assert isinstance(cloned_bridge, TensorResidentProjectileSpellBridge)
            self.bridge = cloned_bridge
        else:
            assert self.objects is not None and self.bridge is not None
            _refresh_runtime(self.runtime, runtime)
            _copy_tensor_fields(self.objects, objects)
            _copy_tensor_fields(self.objects.objects, objects.objects)
            _copy_tensor_fields(self.bridge, bridge)
        assert self.objects is not None and self.bridge is not None
        return self.runtime, self.objects, self.bridge


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
        transaction_workspace: _TensorResidentSpellTransactionWorkspace | None = None,
        collect_diagnostics: bool = False,
        validate_inputs: bool = False,
        batch_rows: torch.Tensor | None = None,
        expected_player_order: torch.Tensor | None = None,
        empty_reasons: tuple[str | None, ...] | None = None,
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
        self._transaction_workspace = (
            _TensorResidentSpellTransactionWorkspace()
            if transaction_workspace is None
            else transaction_workspace
        )
        self.collect_diagnostics = collect_diagnostics
        self.validate_inputs = validate_inputs
        self._batch_rows = (
            torch.arange(runtime.batch_size, dtype=torch.int64, device=self.device)
            if batch_rows is None
            else batch_rows
        )
        self._expected_player_order = (
            torch.tensor([0, 1], dtype=torch.int64, device=self.device)
            if expected_player_order is None
            else expected_player_order
        )
        self._empty_reasons = (
            (None,) * runtime.batch_size if empty_reasons is None else empty_reasons
        )
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
            self.episode_supported_core = bridge.catalog.supported
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
        return cls(
            runtime,
            objects,
            bridge,
            cards,
            collect_diagnostics=True,
            validate_inputs=True,
        )

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
            transaction_workspace=self._transaction_workspace,
            collect_diagnostics=self.collect_diagnostics,
            validate_inputs=self.validate_inputs,
            batch_rows=self._batch_rows,
            expected_player_order=self._expected_player_order,
            empty_reasons=self._empty_reasons,
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

    def _validate_apply_inputs(
        self,
        ingress: TensorIngressResult,
        player_order: torch.Tensor | None,
    ) -> None:
        batch = self.runtime.batch_size
        commands = ingress.commands
        if ingress.hand_ids.shape[:2] != (batch, 2):
            raise ValueError("ingress batch differs from resident runtime")
        invalid_command = (
            (commands.battle_index < 0)
            | (commands.battle_index >= batch)
            | (commands.card_id < 0)
            | (commands.card_id >= len(self.cards.names))
        )
        if commands.battle_index.numel() and bool(invalid_command.any().item()):
            raise ValueError("command index is outside resident spell catalog")
        if player_order is None:
            return
        order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
        valid_order = order.shape == (batch, 2) and bool(
            (torch.sort(order, dim=1).values == self._expected_player_order)
            .all()
            .item()
        )
        if not valid_order:
            raise ValueError("player_order rows must be permutations of (0, 1)")

    def _diagnostic_reasons(
        self,
        *,
        runtime_supported: torch.Tensor,
        bad_row: torch.Tensor,
        transition_known: torch.Tensor,
        failed_card: torch.Tensor,
    ) -> tuple[str | None, ...]:
        reasons: list[str | None] = [None] * self.runtime.batch_size
        unsupported_rows = (
            torch.nonzero(~runtime_supported, as_tuple=False).flatten().tolist()
        )
        bad_rows = torch.nonzero(bad_row, as_tuple=False).flatten().tolist()
        transition_rows = (
            torch.nonzero(~transition_known, as_tuple=False).flatten().tolist()
        )
        failed_rows = torch.nonzero(failed_card >= 0, as_tuple=False).flatten().tolist()
        for row in unsupported_rows:
            reasons[row] = "resident runtime row is unsupported"
        for row in bad_rows:
            reasons[row] = "non-spell command requires another ingress"
        for row in transition_rows:
            reasons[row] = "card transition references an unknown core card"
        for row in failed_rows:
            card = int(failed_card[row].item())
            reasons[row] = (
                self.bridge.catalog.unsupported_reason[card]
                or "spell payload capacity is unavailable"
            )
        return tuple(reasons)

    def apply(
        self,
        ingress: TensorIngressResult,
        *,
        player_order: torch.Tensor | None = None,
    ) -> TensorResidentSpellIngressResult:
        batch = self.runtime.batch_size
        commands = ingress.commands
        if self.validate_inputs:
            self._validate_apply_inputs(ingress, player_order)
        speculative_runtime, speculative_objects, speculative_bridge = (
            self._transaction_workspace.acquire(
                self.runtime,
                self.objects,
                self.bridge,
            )
        )

        if player_order is None:
            choice = speculative_runtime.battle.rng.randrange(2)
            order = torch.stack((1 - choice, choice), dim=1)
        else:
            order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)

        catalog_to_core = self.catalog_to_core
        command_count = int(commands.card_id.numel())
        command_spell = (
            self.cards.kind[commands.card_id] == int(CardKindOpcode.SPELL)
        ) & ~commands.is_ability
        non_spell = ~command_spell
        bad_row = torch.zeros(batch, dtype=torch.bool, device=self.device)
        if command_count:
            scatter_any_(bad_row, 0, commands.battle_index, non_spell)
        transition_known = (
            (catalog_to_core[ingress.hand_ids] >= 0).all(dim=2)
            & (catalog_to_core[ingress.cycle_ids] >= 0).all(dim=2)
        ).all(dim=1)
        row_supported = self.runtime.supported & ~bad_row & transition_known
        failed_card = torch.full((batch,), -1, dtype=torch.int64, device=self.device)

        for rank in range(2):
            player = order[:, rank]
            if command_count:
                matches = (
                    commands.battle_index[None, :] == self._batch_rows[:, None]
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
            failed_card.copy_(torch.where(failed, core_card, failed_card))

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
        if self.validate_inputs:
            self.runtime.assert_invariants()
        action_success = ingress.accepted & row_supported[:, None]
        unsupported_reasons = (
            self._diagnostic_reasons(
                runtime_supported=self.runtime.supported,
                bad_row=bad_row,
                transition_known=transition_known,
                failed_card=failed_card,
            )
            if self.collect_diagnostics
            else self._empty_reasons
        )
        return TensorResidentSpellIngressResult(
            committed=row_supported,
            unsupported=~row_supported,
            unsupported_reasons=unsupported_reasons,
            action_success=action_success,
            player_order=order,
            spell_command=command_spell,
        )


__all__ = [
    "TensorResidentSpellActionIngress",
    "TensorResidentSpellIngressResult",
    "TensorResidentSpellPreflight",
]
