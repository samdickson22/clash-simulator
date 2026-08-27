"""Fixed-lane tensor action ingress for resident CUDA execution.

The ordinary path keeps exactly one lane per ``[battle, player]`` and uses a
boolean command-valid plane instead of compacting commands with
``torch.nonzero``.  Compact :class:`~clasher.torch_sim.actions.TensorIngressResult`
objects are created only by the explicitly named diagnostic adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields

import torch

from clasher.rl.common import NUM_HAND_SLOTS
from clasher.torch_sim.actions import (
    NO_OP_ACTION,
    NUM_ACTIONS,
    TensorActionKernel,
    TensorActionSelection,
    TensorActionState,
    TensorCommandQueue,
    TensorIngressResult,
)


def _map_selection(
    selection: TensorActionSelection,
    transform: Callable[[torch.Tensor], torch.Tensor],
) -> TensorActionSelection:
    return TensorActionSelection(
        action_ids=transform(selection.action_ids),
        valid_input=transform(selection.valid_input),
        is_no_op=transform(selection.is_no_op),
        is_ability=transform(selection.is_ability),
        slot=transform(selection.slot),
        tile=transform(selection.tile),
        world_x_units=transform(selection.world_x_units),
        world_y_units=transform(selection.world_y_units),
    )


@dataclass
class TensorDenseCommandLanes:
    """One stable command lane per battle and player.

    ``valid`` is the only command-presence authority.  The second dimension is
    player identity unless :meth:`ordered` is explicitly used at a downstream
    simultaneous-execution boundary.
    """

    valid: torch.Tensor
    sequence: torch.Tensor
    battle_index: torch.Tensor
    player_id: torch.Tensor
    action_id: torch.Tensor
    card_id: torch.Tensor
    card_kind: torch.Tensor
    slot: torch.Tensor
    world_x_units: torch.Tensor
    world_y_units: torch.Tensor
    is_ability: torch.Tensor

    def clone(self) -> TensorDenseCommandLanes:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorDenseCommandLanes:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.valid.device)
        forked = type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, indices)
                .clone()
                for descriptor in fields(self)
            }
        )
        forked.battle_index.copy_(
            torch.arange(indices.numel(), device=self.valid.device)
            .view(-1, 1)
            .expand(-1, 2)
        )
        return forked

    def ordered(self, player_order: torch.Tensor) -> TensorDenseCommandLanes:
        """Return lanes gathered into an explicit simultaneous player order."""

        order = torch.as_tensor(
            player_order, dtype=torch.int64, device=self.valid.device
        )
        if order.shape != self.valid.shape:
            raise ValueError("player_order must have shape [batch, 2]")
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).gather(1, order)
                for descriptor in fields(self)
            }
        )


@dataclass
class TensorDenseTransitionPlanes:
    """Per-player card transition facts retained alongside resulting state."""

    placement: torch.Tensor
    cleared_hand_slot: torch.Tensor
    cycle_appended: torch.Tensor
    cycle_append_index: torch.Tensor
    elixir_cost: torch.Tensor

    def clone(self) -> TensorDenseTransitionPlanes:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorDenseTransitionPlanes:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.placement.device)
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, indices)
                .clone()
                for descriptor in fields(self)
            }
        )


@dataclass
class TensorDenseIngressResult:
    """Dense ingress selection, command, transition, and post-action planes."""

    accepted: torch.Tensor
    selection: TensorActionSelection
    commands: TensorDenseCommandLanes
    transitions: TensorDenseTransitionPlanes
    hand_ids: torch.Tensor
    cycle_ids: torch.Tensor
    cycle_length: torch.Tensor
    elixir: torch.Tensor

    def clone(self) -> TensorDenseIngressResult:
        return type(self)(
            accepted=self.accepted.clone(),
            selection=_map_selection(self.selection, torch.Tensor.clone),
            commands=self.commands.clone(),
            transitions=self.transitions.clone(),
            hand_ids=self.hand_ids.clone(),
            cycle_ids=self.cycle_ids.clone(),
            cycle_length=self.cycle_length.clone(),
            elixir=self.elixir.clone(),
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorDenseIngressResult:
        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.accepted.device)

        def select(value: torch.Tensor) -> torch.Tensor:
            return value.index_select(0, indices).clone()

        return type(self)(
            accepted=select(self.accepted),
            selection=_map_selection(self.selection, select),
            commands=self.commands.fork(indices),
            transitions=self.transitions.fork(indices),
            hand_ids=select(self.hand_ids),
            cycle_ids=select(self.cycle_ids),
            cycle_length=select(self.cycle_length),
            elixir=select(self.elixir),
        )

    def reset_rows_(
        self,
        source: TensorDenseIngressResult,
        reset_mask: torch.Tensor,
    ) -> TensorDenseIngressResult:
        """Replace selected rows in-place from an equal-shaped dense result."""

        rows = torch.as_tensor(
            reset_mask, dtype=torch.bool, device=self.accepted.device
        )
        if rows.shape != (self.accepted.shape[0],):
            raise ValueError("reset_mask must have shape [batch]")
        if source.accepted.shape != self.accepted.shape:
            raise ValueError("source dense result must have the same batch shape")
        for name in ("accepted", "hand_ids", "cycle_ids", "cycle_length", "elixir"):
            destination = getattr(self, name)
            replacement = getattr(source, name)
            destination[rows] = replacement[rows]
        for destination_owner, source_owner in (
            (self.selection, source.selection),
            (self.commands, source.commands),
            (self.transitions, source.transitions),
        ):
            for descriptor in fields(destination_owner):
                if destination_owner is self.commands and descriptor.name in {
                    "battle_index",
                    "player_id",
                }:
                    continue
                destination = getattr(destination_owner, descriptor.name)
                replacement = getattr(source_owner, descriptor.name)
                destination[rows] = replacement[rows]
        return self

    def to_tensor_ingress_diagnostic(self) -> TensorIngressResult:
        """Compact valid lanes for legacy diagnostics/public boundaries only."""

        flat_indices = torch.nonzero(
            self.commands.valid.reshape(-1), as_tuple=False
        ).squeeze(-1)

        def compact(value: torch.Tensor) -> torch.Tensor:
            return value.reshape(-1)[flat_indices]

        commands = TensorCommandQueue(
            sequence=compact(self.commands.sequence),
            battle_index=compact(self.commands.battle_index),
            player_id=compact(self.commands.player_id),
            action_id=compact(self.commands.action_id),
            card_id=compact(self.commands.card_id),
            card_kind=compact(self.commands.card_kind),
            slot=compact(self.commands.slot),
            world_x_units=compact(self.commands.world_x_units),
            world_y_units=compact(self.commands.world_y_units),
            is_ability=compact(self.commands.is_ability),
        )
        return TensorIngressResult(
            accepted=self.accepted,
            selection=self.selection,
            commands=commands,
            hand_ids=self.hand_ids,
            cycle_ids=self.cycle_ids,
            cycle_length=self.cycle_length,
            elixir=self.elixir,
        )


class TensorDenseActionIngress:
    """Fixed-batch action ingress without dynamic command compaction."""

    def __init__(self, kernel: TensorActionKernel, batch_size: int) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.kernel = kernel
        self.catalog = kernel.catalog
        self.device = kernel.device
        self.batch_size = int(batch_size)
        self._hand_slots = torch.arange(NUM_HAND_SLOTS, device=self.device).view(
            1, 1, -1
        )
        self._battle_index = (
            torch.arange(self.batch_size, device=self.device).view(-1, 1).expand(-1, 2)
        )
        self._player_id = (
            torch.arange(2, device=self.device).view(1, 2).expand(self.batch_size, -1)
        )

    def legal_action_mask(self, state: TensorActionState) -> torch.Tensor:
        self._validate_state(state)
        return self.kernel.legal_action_mask(state)

    def _validate_state(self, state: TensorActionState) -> None:
        if state.batch_size != self.batch_size:
            raise ValueError("action state batch size changed after dense construction")
        if state.device != self.device:
            raise ValueError("action state is on a different device")

    def ingress(
        self,
        state: TensorActionState,
        action_ids: torch.Tensor,
        *,
        legal_mask: torch.Tensor | None = None,
    ) -> TensorDenseIngressResult:
        """Apply exact card transitions and retain commands in fixed lanes."""

        self._validate_state(state)
        selection = self.kernel.decode(action_ids)
        if selection.action_ids.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        if legal_mask is None:
            legal_mask = self.kernel.legal_action_mask(state)
        if legal_mask.shape != (self.batch_size, 2, NUM_ACTIONS):
            raise ValueError("legal_mask must have shape [batch, 2, NUM_ACTIONS]")
        safe_action = selection.action_ids.clamp(0, NUM_ACTIONS - 1)
        selected_legal = legal_mask.gather(2, safe_action.unsqueeze(-1)).squeeze(-1)
        accepted = selection.valid_input & selected_legal
        placement = accepted & (selection.action_ids < NO_OP_ACTION)

        safe_slot = selection.slot.clamp(min=0)
        card_ids = state.hand_ids.gather(2, safe_slot.unsqueeze(-1)).squeeze(-1)
        hand = state.hand_ids.clone()
        cycle = state.cycle_ids.clone()
        cycle_length = state.cycle_length.clone()
        elixir = state.elixir.clone()

        matches = hand == card_ids.unsqueeze(-1)
        first_slot = torch.where(matches, self._hand_slots, NUM_HAND_SLOTS).amin(dim=-1)
        clear = placement.unsqueeze(-1) & (self._hand_slots == first_slot.unsqueeze(-1))
        hand = torch.where(clear, torch.zeros_like(hand), hand)
        cost = self.catalog.cards.elixir[card_ids].to(torch.float64)
        applied_cost = torch.where(placement, cost, torch.zeros_like(cost))
        elixir = elixir - applied_cost

        append_index = cycle_length.clamp(max=cycle.shape[-1] - 1)
        append_mask = placement & (cycle_length < cycle.shape[-1])
        cycle.scatter_(
            2,
            append_index.unsqueeze(-1),
            torch.where(
                append_mask,
                card_ids,
                cycle.gather(2, append_index.unsqueeze(-1)).squeeze(-1),
            ).unsqueeze(-1),
        )
        cycle_length = cycle_length + append_mask.to(torch.int64)

        command_valid = placement | (accepted & selection.is_ability)
        command_sequence = (
            torch.cumsum(command_valid.reshape(-1).to(torch.int64), dim=0).reshape(
                self.batch_size, 2
            )
            - 1
        )
        command_sequence = torch.where(
            command_valid, command_sequence, torch.full_like(command_sequence, -1)
        )
        command_card = torch.where(placement, card_ids, torch.zeros_like(card_ids))
        commands = TensorDenseCommandLanes(
            valid=command_valid,
            sequence=command_sequence,
            battle_index=self._battle_index,
            player_id=self._player_id,
            action_id=torch.where(
                command_valid,
                selection.action_ids,
                torch.full_like(selection.action_ids, -1),
            ),
            card_id=command_card,
            card_kind=self.catalog.cards.kind[command_card],
            slot=torch.where(
                command_valid, selection.slot, torch.full_like(selection.slot, -1)
            ),
            world_x_units=torch.where(
                command_valid,
                selection.world_x_units,
                torch.zeros_like(selection.world_x_units),
            ),
            world_y_units=torch.where(
                command_valid,
                selection.world_y_units,
                torch.zeros_like(selection.world_y_units),
            ),
            is_ability=command_valid & selection.is_ability,
        )
        transitions = TensorDenseTransitionPlanes(
            placement=placement,
            cleared_hand_slot=torch.where(
                placement, first_slot, torch.full_like(first_slot, -1)
            ),
            cycle_appended=append_mask,
            cycle_append_index=torch.where(
                append_mask, append_index, torch.full_like(append_index, -1)
            ),
            elixir_cost=applied_cost,
        )
        return TensorDenseIngressResult(
            accepted=accepted,
            selection=selection,
            commands=commands,
            transitions=transitions,
            hand_ids=hand,
            cycle_ids=cycle,
            cycle_length=cycle_length,
            elixir=elixir,
        )

    def from_tensor_ingress_diagnostic(
        self,
        state: TensorActionState,
        ingress: TensorIngressResult,
    ) -> TensorDenseIngressResult:
        """Recreate fixed lanes from a current compact ingress boundary value."""

        legal = torch.zeros(
            (self.batch_size, 2, NUM_ACTIONS),
            dtype=torch.bool,
            device=self.device,
        )
        safe_action = ingress.selection.action_ids.clamp(0, NUM_ACTIONS - 1)
        legal.scatter_(2, safe_action.unsqueeze(-1), ingress.accepted.unsqueeze(-1))
        return self.ingress(
            state,
            ingress.selection.action_ids,
            legal_mask=legal,
        )


__all__ = [
    "TensorDenseActionIngress",
    "TensorDenseCommandLanes",
    "TensorDenseIngressResult",
    "TensorDenseTransitionPlanes",
]
