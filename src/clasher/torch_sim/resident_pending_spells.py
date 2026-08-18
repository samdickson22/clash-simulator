"""Retained delayed spell commands for the resident tensor engine.

Python accepts a spell action immediately (card transition and elixir spend),
then stores :class:`clasher.battle.PendingSpellCast` for the universal server
action delay.  Payload allocation, damage, and payload RNG happen only when
the command becomes due at the command phase of a later logic tick.

This owner is intentionally integration-neutral: it exposes enqueue and due
resolution APIs without editing ``TensorResidentEngine`` or its workspace.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import torch

from clasher.battle import BattleState
from clasher.kinematics import SERVER_ACTION_DELAY_SECONDS, tiles_to_logic_units

from .actions import TensorIngressResult
from .catalog import CardKindOpcode, TensorCardCatalog
from .projectile_bridge import TensorResidentProjectileSpellBridge
from .resident_spell_ingress import (
    _clone_object_phase,
    _clone_tensor_owner,
    _copy_bridge_rows,
    _copy_phase_rows,
    _copy_runtime_rows,
)
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime

PENDING_EPSILON = 1e-9


@dataclass(frozen=True)
class PendingSpellEnqueueResult:
    committed: torch.Tensor
    spell_rows: torch.Tensor
    action_success: torch.Tensor
    queued_count: torch.Tensor
    capacity_rejected: torch.Tensor
    unsupported_payload: torch.Tensor


@dataclass(frozen=True)
class PendingSpellResolveResult:
    committed: torch.Tensor
    due_rows: torch.Tensor
    resolved_count: torch.Tensor
    failed_rows: torch.Tensor


@dataclass
class TensorResidentPendingSpells:
    """Fixed-capacity pending spell commands ordered by deadline and sequence."""

    cards: TensorCardCatalog
    active: torch.Tensor
    execute_at: torch.Tensor
    sequence: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    next_sequence: torch.Tensor
    catalog_to_core: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.active.device

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        cards: TensorCardCatalog,
        *,
        capacity: int = 8,
    ) -> TensorResidentPendingSpells:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime")
        existing = max(
            (len(battle._pending_spell_casts) for battle in battles), default=0
        )
        if capacity < max(1, existing):
            raise ValueError("pending spell capacity is smaller than live commands")
        if cards.device != runtime.device:
            raise ValueError("pending spell catalog and runtime devices differ")
        shape = (runtime.batch_size, capacity)
        active = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        execute_at = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        sequence = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        card_id = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        player_id = torch.zeros(shape, dtype=torch.int8, device=runtime.device)
        x_units = torch.zeros(shape, dtype=torch.int32, device=runtime.device)
        y_units = torch.zeros(shape, dtype=torch.int32, device=runtime.device)
        next_sequence = torch.tensor(
            [battle._next_spell_cast_sequence for battle in battles],
            dtype=torch.int64,
            device=runtime.device,
        )
        for row, battle in enumerate(battles):
            for slot, pending in enumerate(battle._pending_spell_casts):
                core_card = runtime.battle.card_to_id.get(pending.spell_name)
                if core_card is None:
                    raise ValueError(
                        f"pending spell {pending.spell_name!r} is absent from runtime"
                    )
                active[row, slot] = True
                execute_at[row, slot] = pending.execute_at
                sequence[row, slot] = pending.sequence
                card_id[row, slot] = core_card
                player_id[row, slot] = pending.player_id
                x_units[row, slot] = tiles_to_logic_units(pending.position.x)
                y_units[row, slot] = tiles_to_logic_units(pending.position.y)
        catalog_to_core = torch.tensor(
            [
                runtime.battle.card_to_id.get(name, -1) if name else 0
                for name in cards.names
            ],
            dtype=torch.int64,
            device=runtime.device,
        )
        return cls(
            cards=cards,
            active=active,
            execute_at=execute_at,
            sequence=sequence,
            card_id=card_id,
            player_id=player_id,
            target_x_units=x_units,
            target_y_units=y_units,
            next_sequence=next_sequence,
            catalog_to_core=catalog_to_core,
        )

    def clone(self) -> TensorResidentPendingSpells:
        return type(self)(
            cards=self.cards,
            active=self.active.clone(),
            execute_at=self.execute_at.clone(),
            sequence=self.sequence.clone(),
            card_id=self.card_id.clone(),
            player_id=self.player_id.clone(),
            target_x_units=self.target_x_units.clone(),
            target_y_units=self.target_y_units.clone(),
            next_sequence=self.next_sequence.clone(),
            catalog_to_core=self.catalog_to_core,
        )

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentPendingSpells:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if indices.ndim != 1:
            raise ValueError("pending spell fork rows must be one-dimensional")
        if bool(((indices < 0) | (indices >= self.batch_size)).any().item()):
            raise IndexError("pending spell fork row is outside the batch")
        return type(self)(
            cards=self.cards,
            active=self.active[indices].clone(),
            execute_at=self.execute_at[indices].clone(),
            sequence=self.sequence[indices].clone(),
            card_id=self.card_id[indices].clone(),
            player_id=self.player_id[indices].clone(),
            target_x_units=self.target_x_units[indices].clone(),
            target_y_units=self.target_y_units[indices].clone(),
            next_sequence=self.next_sequence[indices].clone(),
            catalog_to_core=self.catalog_to_core,
        )

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentPendingSpells,
        source_rows: torch.Tensor | list[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(
            destination_rows, dtype=torch.int64, device=self.device
        )
        selected_source = (
            torch.arange(destination.numel(), dtype=torch.int64, device=self.device)
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        if destination.ndim != 1 or selected_source.shape != destination.shape:
            raise ValueError("pending spell reset rows must have equal vector shapes")
        if source.device != self.device or source.capacity != self.capacity:
            raise ValueError("pending spell reset source has a different layout")
        for name in (
            "active",
            "execute_at",
            "sequence",
            "card_id",
            "player_id",
            "target_x_units",
            "target_y_units",
            "next_sequence",
        ):
            destination_value = getattr(self, name)
            source_value = getattr(source, name)
            destination_value[destination] = source_value[selected_source]

    def enqueue_(
        self,
        runtime: TensorBattleRuntime,
        bridge: TensorResidentProjectileSpellBridge,
        ingress: TensorIngressResult,
        *,
        player_order: torch.Tensor,
    ) -> PendingSpellEnqueueResult:
        """Commit card transitions and enqueue commands without payload work."""

        if runtime.batch_size != self.batch_size or runtime.device != self.device:
            raise ValueError("pending spell owner and runtime layouts differ")
        order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
        expected = torch.tensor([0, 1], dtype=torch.int64, device=self.device)
        if order.shape != (self.batch_size, 2) or not bool(
            (torch.sort(order, dim=1).values == expected).all().item()
        ):
            raise ValueError("player_order rows must be permutations of (0, 1)")
        commands = ingress.commands
        command_count = int(commands.card_id.numel())
        command_spell = (
            self.cards.kind[commands.card_id] == int(CardKindOpcode.SPELL)
        ) & ~commands.is_ability
        core_card = self.catalog_to_core[commands.card_id]
        payload_supported = (
            command_spell
            & (core_card >= 0)
            & bridge.catalog.supported[core_card.clamp_min(0)]
        )
        spell_count = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        nonspell_count = torch.zeros_like(spell_count)
        unsupported_count = torch.zeros_like(spell_count)
        if command_count:
            spell_count.scatter_add_(
                0, commands.battle_index, command_spell.to(torch.int64)
            )
            nonspell_count.scatter_add_(
                0, commands.battle_index, (~command_spell).to(torch.int64)
            )
            unsupported_count.scatter_add_(
                0, commands.battle_index, (~payload_supported).to(torch.int64)
            )
        spell_rows = spell_count > 0
        free_count = (~self.active).sum(dim=1)
        capacity_rejected = spell_rows & (spell_count > free_count)
        unsupported_payload = spell_rows & (unsupported_count > 0)
        mixed = spell_rows & (nonspell_count > 0)
        transition_known = (
            (self.catalog_to_core[ingress.hand_ids] >= 0).all(dim=2)
            & (self.catalog_to_core[ingress.cycle_ids] >= 0).all(dim=2)
        ).all(dim=1)
        accepted_rows = (
            runtime.supported
            & spell_rows
            & ~capacity_rejected
            & ~unsupported_payload
            & ~mixed
            & transition_known
        )
        cycle_width = ingress.cycle_ids.shape[2]
        if cycle_width > runtime.battle.cycle_queue.shape[2]:
            raise OverflowError("runtime card-cycle capacity exhausted")

        working = self.clone()
        batch_rows = torch.arange(self.batch_size, device=self.device)
        queued_count = torch.zeros_like(spell_count)
        for rank in range(2):
            player = order[:, rank]
            if command_count:
                matches = (commands.battle_index[None, :] == batch_rows[:, None]) & (
                    commands.player_id[None, :] == player[:, None]
                )
                found = matches.any(dim=1)
                command_index = matches.to(torch.int64).argmax(dim=1)
                selected_core = core_card[command_index]
                x_units = commands.world_x_units[command_index]
                y_units = commands.world_y_units[command_index]
            else:
                found = torch.zeros(
                    self.batch_size, dtype=torch.bool, device=self.device
                )
                selected_core = torch.zeros(
                    self.batch_size, dtype=torch.int64, device=self.device
                )
                x_units = torch.zeros_like(selected_core)
                y_units = torch.zeros_like(selected_core)
            admitted = accepted_rows & found
            free = ~working.active
            slot = free.to(torch.int64).argmax(dim=1)
            rows = batch_rows[admitted]
            slots = slot[admitted]
            working.active[rows, slots] = True
            working.execute_at[rows, slots] = (
                runtime.battle.time[rows] + SERVER_ACTION_DELAY_SECONDS
            )
            working.sequence[rows, slots] = working.next_sequence[rows]
            working.card_id[rows, slots] = selected_core[rows]
            working.player_id[rows, slots] = player[rows].to(torch.int8)
            working.target_x_units[rows, slots] = x_units[rows].to(torch.int32)
            working.target_y_units[rows, slots] = y_units[rows].to(torch.int32)
            working.next_sequence[rows] += 1
            queued_count += admitted.to(torch.int64)

        for name in (
            "active",
            "execute_at",
            "sequence",
            "card_id",
            "player_id",
            "target_x_units",
            "target_y_units",
            "next_sequence",
        ):
            destination = getattr(self, name)
            source = getattr(working, name)
            destination[accepted_rows] = source[accepted_rows]

        mapped_hand = self.catalog_to_core[ingress.hand_ids]
        mapped_cycle = self.catalog_to_core[ingress.cycle_ids]
        runtime.battle.hand[accepted_rows] = mapped_hand[accepted_rows]
        runtime.battle.cycle_queue[accepted_rows] = 0
        runtime.battle.cycle_queue[accepted_rows, :, :cycle_width] = mapped_cycle[
            accepted_rows
        ]
        runtime.battle.cycle_queue_length[accepted_rows] = ingress.cycle_length[
            accepted_rows
        ].to(runtime.battle.cycle_queue_length.dtype)
        runtime.battle.elixir[accepted_rows] = ingress.elixir[accepted_rows]
        committed = ~spell_rows | accepted_rows
        return PendingSpellEnqueueResult(
            committed=committed,
            spell_rows=spell_rows,
            action_success=ingress.accepted & accepted_rows[:, None],
            queued_count=queued_count,
            capacity_rejected=capacity_rejected,
            unsupported_payload=unsupported_payload | mixed | ~transition_known,
        )

    def resolve_due_(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
    ) -> PendingSpellResolveResult:
        """Resolve due commands atomically in ``(execute_at, sequence)`` order."""

        due = self.active & (
            self.execute_at <= runtime.battle.time[:, None] + PENDING_EPSILON
        )
        due_rows = due.any(dim=1)
        if not bool(due_rows.any().item()):
            return PendingSpellResolveResult(
                committed=torch.ones(
                    self.batch_size, dtype=torch.bool, device=self.device
                ),
                due_rows=due_rows,
                resolved_count=torch.zeros(
                    self.batch_size, dtype=torch.int64, device=self.device
                ),
                failed_rows=torch.zeros_like(due_rows),
            )

        speculative_runtime = runtime.clone()
        speculative_runtime.battle.rng = runtime.battle.rng.clone()
        speculative_objects = _clone_object_phase(objects)
        speculative_bridge = cast(
            TensorResidentProjectileSpellBridge,
            _clone_tensor_owner(bridge),
        )
        working = self.clone()
        supported = runtime.supported.clone()
        processed = torch.zeros_like(due)
        resolved_count = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        rows = torch.arange(self.batch_size, device=self.device)
        maximum_sequence = torch.iinfo(torch.int64).max
        infinity = torch.full_like(self.execute_at, torch.inf)
        for _ in range(self.capacity):
            candidate = due & ~processed & supported[:, None]
            selected_time = torch.where(candidate, self.execute_at, infinity).amin(
                dim=1
            )
            at_time = candidate & (self.execute_at == selected_time[:, None])
            sequence = torch.where(
                at_time,
                self.sequence,
                torch.full_like(self.sequence, maximum_sequence),
            )
            selected_sequence, slot = sequence.min(dim=1)
            selected = selected_sequence != maximum_sequence
            cards = torch.gather(self.card_id, 1, slot[:, None])[:, 0]
            players = torch.gather(self.player_id.to(torch.int64), 1, slot[:, None])[
                :, 0
            ]
            x_units = torch.gather(
                self.target_x_units.to(torch.int64), 1, slot[:, None]
            )[:, 0]
            y_units = torch.gather(
                self.target_y_units.to(torch.int64), 1, slot[:, None]
            )[:, 0]
            materialized = speculative_bridge.materialize_spell_actions_(
                speculative_runtime,
                speculative_objects,
                card_ids=cards,
                player_ids=players,
                target_x_units=x_units,
                target_y_units=y_units,
                valid=selected,
            )
            failed = selected & ~materialized
            supported &= ~failed
            committed = selected & materialized
            selected_rows = rows[committed]
            selected_slots = slot[committed]
            working.active[selected_rows, selected_slots] = False
            working.execute_at[selected_rows, selected_slots] = 0.0
            working.sequence[selected_rows, selected_slots] = 0
            working.card_id[selected_rows, selected_slots] = 0
            working.player_id[selected_rows, selected_slots] = 0
            working.target_x_units[selected_rows, selected_slots] = 0
            working.target_y_units[selected_rows, selected_slots] = 0
            resolved_count += committed.to(torch.int64)
            processed[rows[selected], slot[selected]] = True

        commit_rows = due_rows & supported
        _copy_runtime_rows(runtime, speculative_runtime, commit_rows)
        blueprint_indices = speculative_bridge.blueprint_for_slot[commit_rows].flatten()
        _copy_phase_rows(
            objects,
            speculative_objects,
            commit_rows,
            blueprint_indices,
        )
        _copy_bridge_rows(
            bridge,
            speculative_bridge,
            commit_rows,
        )
        for name in (
            "active",
            "execute_at",
            "sequence",
            "card_id",
            "player_id",
            "target_x_units",
            "target_y_units",
            "next_sequence",
        ):
            destination = getattr(self, name)
            source = getattr(working, name)
            destination[commit_rows] = source[commit_rows]
        failed_rows = due_rows & ~supported
        return PendingSpellResolveResult(
            committed=~due_rows | commit_rows,
            due_rows=due_rows,
            resolved_count=torch.where(
                commit_rows, resolved_count, torch.zeros_like(resolved_count)
            ),
            failed_rows=failed_rows,
        )


__all__ = [
    "PendingSpellEnqueueResult",
    "PendingSpellResolveResult",
    "TensorResidentPendingSpells",
]
