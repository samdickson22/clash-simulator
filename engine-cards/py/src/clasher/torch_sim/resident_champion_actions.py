"""Policy-action bridge for retained serialized Champion abilities.

The action kernel deliberately treats an ability button as a mechanic-owned
command: it neither rotates cards nor spends elixir.  This module connects
that command to :class:`TensorRuntimeMechanics` without inspecting card names.
It is intentionally independent from the resident engine transaction so the
engine can run it on the same speculative rows used by deployment and spells.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .actions import TensorActionState, TensorCommandQueue
from .runtime_mechanics import MechanicActivationResult, TensorRuntimeMechanics
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class ResidentChampionActionResult:
    """Policy-visible result of routing zero or more ability commands."""

    requested_players: torch.Tensor
    legal_before: torch.Tensor
    command_success: torch.Tensor
    activation: MechanicActivationResult | None


def champion_player_legality(
    mechanics: TensorRuntimeMechanics,
    runtime: TensorBattleRuntime,
) -> torch.Tensor:
    """Reduce serialized per-entity ability availability to one button/player."""

    entity_legal = mechanics.can_activate(runtime)
    counts = torch.zeros(
        (runtime.batch_size, 2), dtype=torch.int16, device=runtime.device
    )
    counts.scatter_add_(
        1,
        runtime.battle.entity_player.to(torch.int64),
        entity_legal.to(torch.int16),
    )
    # TensorRuntimeMechanics resolves one Champion button owner per player.  A
    # boolean reduction keeps this adapter valid if another serialized
    # Champion ability opcode is added later.
    return counts > 0


def publish_champion_legality_(
    action_state: TensorActionState,
    mechanics: TensorRuntimeMechanics,
    runtime: TensorBattleRuntime,
) -> torch.Tensor:
    """Publish retained Champion-button legality into an action snapshot."""

    expected = (runtime.batch_size, 2)
    if action_state.ability_legal.shape != expected:
        raise ValueError("ability_legal must have shape [batch, 2]")
    legal = champion_player_legality(mechanics, runtime)
    action_state.ability_legal.copy_(legal & action_state.supported)
    return action_state.ability_legal


def route_champion_commands_(
    mechanics: TensorRuntimeMechanics,
    runtime: TensorBattleRuntime,
    commands: TensorCommandQueue,
) -> ResidentChampionActionResult:
    """Apply accepted ability commands through the serialized mechanic owner.

    Non-ability commands are ignored.  The caller owns transactionality; the
    resident action router can therefore invoke this on its speculative
    workspace and publish only rows whose entire joint action commits.
    """

    ability = commands.is_ability
    requested = torch.zeros(
        (runtime.batch_size, 2), dtype=torch.bool, device=runtime.device
    )
    command_success = torch.zeros_like(ability)
    legal_before = champion_player_legality(mechanics, runtime)
    if not bool(ability.any().item()):
        return ResidentChampionActionResult(
            requested_players=requested,
            legal_before=legal_before,
            command_success=command_success,
            activation=None,
        )

    rows = commands.battle_index[ability].to(torch.int64)
    players = commands.player_id[ability].to(torch.int64)
    if bool(((rows < 0) | (rows >= runtime.batch_size)).any().item()):
        raise ValueError("ability command battle index is out of range")
    if bool(((players < 0) | (players >= 2)).any().item()):
        raise ValueError("ability command player id is out of range")
    flat_group = rows * 2 + players
    if torch.unique(flat_group).numel() != flat_group.numel():
        raise ValueError("at most one ability command is allowed per player and row")
    requested[rows, players] = True

    activation = mechanics.activate_(runtime, requested)
    activated_players = torch.zeros_like(requested, dtype=torch.int16)
    activated_players.scatter_add_(
        1,
        runtime.battle.entity_player.to(torch.int64),
        activation.activated.to(torch.int16),
    )
    ability_success = activated_players[rows, players] > 0
    command_success[ability] = ability_success
    return ResidentChampionActionResult(
        requested_players=requested,
        legal_before=legal_before,
        command_success=command_success,
        activation=activation,
    )


__all__ = [
    "ResidentChampionActionResult",
    "champion_player_legality",
    "publish_champion_legality_",
    "route_champion_commands_",
]
