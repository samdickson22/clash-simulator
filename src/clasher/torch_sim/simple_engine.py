"""Minimal unified tensor tick for the practical reinforcement-learning Gym."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch.nn import functional

from .simple_state import FastGymState


@dataclass(frozen=True)
class FastDeploymentRequest:
    """At most one ordinary deployment request per batch row."""

    valid: torch.Tensor
    owner: torch.Tensor
    card_id: torch.Tensor
    kind: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    hp: torch.Tensor
    deploy_ticks: torch.Tensor


@dataclass(frozen=True)
class FastGymTickResult:
    """Fixed-shape result with no fallback or dynamic event collection."""

    committed: torch.Tensor
    action_success: torch.Tensor
    native_ticks: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor


class FastTensorGym:
    """Mutation-only tensor engine with deterministic lowest-slot allocation."""

    def __init__(self, state: FastGymState) -> None:
        self.state = state
        self._slots = torch.arange(
            state.max_entities, dtype=torch.int64, device=state.device
        ).view(1, -1)

    def _validate_request(self, request: FastDeploymentRequest) -> None:
        expected = (self.state.batch_size,)
        for name in (
            "valid",
            "owner",
            "card_id",
            "kind",
            "x_units",
            "y_units",
            "hp",
            "deploy_ticks",
        ):
            value = getattr(request, name)
            if value.shape != expected:
                raise ValueError(f"{name} must have shape [batch]")
            if value.device != self.state.device:
                raise ValueError(f"{name} is on a different device")

    def _deploy(self, request: FastDeploymentRequest) -> torch.Tensor:
        self._validate_request(request)
        state = self.state
        free = ~state.active
        first_free = torch.where(
            free,
            self._slots,
            torch.full_like(self._slots, state.max_entities),
        ).amin(dim=1)
        success = (
            request.valid
            & ~state.game_over
            & (request.owner >= 0)
            & (request.owner < 2)
            & (request.card_id > 0)
            & (request.hp > 0)
            & (first_free < state.max_entities)
        )
        safe_slot = first_free.clamp(max=state.max_entities - 1)
        destination = functional.one_hot(
            safe_slot, num_classes=state.max_entities
        ).to(torch.bool) & success[:, None]

        def write(field: torch.Tensor, value: torch.Tensor) -> None:
            field.copy_(torch.where(destination, value[:, None], field))

        write(state.active, torch.ones_like(success))
        write(state.stable_id, state.next_stable_id)
        write(state.kind, request.kind.to(torch.int8))
        write(state.owner, request.owner.to(torch.int8))
        write(state.card_id, request.card_id.to(torch.int64))
        write(state.x_units, request.x_units.to(torch.int32))
        write(state.y_units, request.y_units.to(torch.int32))
        write(state.hp, request.hp.to(torch.float32))
        write(state.max_hp, request.hp.to(torch.float32))
        write(state.deploy_ticks, request.deploy_ticks.clamp(min=0).to(torch.int32))
        write(state.cooldown_ticks, torch.zeros_like(request.deploy_ticks))
        state.next_stable_id.add_(success.to(torch.int64))
        return success

    def step_tick(
        self, request: FastDeploymentRequest | None = None
    ) -> FastGymTickResult:
        """Advance every live row once and optionally allocate one entity.

        The hot path has no ``item()``, ``nonzero()``, host transfer, clone, or
        per-card dispatch.  Full mechanics are intentionally layered onto this
        fixed-shape state instead of reproducing the oracle's event graph.
        """

        state = self.state
        live = ~state.game_over
        if request is None:
            success = torch.zeros(
                state.batch_size, dtype=torch.bool, device=state.device
            )
            success_by_player = torch.zeros(
                (state.batch_size, 2), dtype=torch.bool, device=state.device
            )
        else:
            success = self._deploy(request)
            success_by_player = torch.zeros(
                (state.batch_size, 2), dtype=torch.bool, device=state.device
            )
            success_by_player.scatter_(
                1,
                request.owner.to(torch.int64).clamp(0, 1)[:, None],
                success[:, None],
            )
        ready = state.active & (state.deploy_ticks > 0)
        state.deploy_ticks.sub_(ready.to(torch.int32)).clamp_(min=0)
        cooling = state.active & (state.cooldown_ticks > 0)
        state.cooldown_ticks.sub_(cooling.to(torch.int32)).clamp_(min=0)
        state.tick.add_(live.to(torch.int64))
        return FastGymTickResult(
            committed=live,
            action_success=success_by_player,
            native_ticks=live.to(torch.int64),
            done=state.game_over.clone(),
            winner=state.winner.clone(),
        )
