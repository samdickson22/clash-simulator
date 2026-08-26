"""Minimal unified tensor tick for the practical reinforcement-learning Gym."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch
from torch.nn import functional

from .simple_catalog import FastCardCatalog
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

    def __init__(
        self,
        state: FastGymState,
        catalog: FastCardCatalog | None = None,
        *,
        reserved_slot_floor: int = 0,
    ) -> None:
        self.state = state
        if catalog is not None and catalog.device != state.device:
            raise ValueError("catalog and state must use the same device")
        if not 0 <= reserved_slot_floor < state.max_entities:
            raise ValueError("reserved_slot_floor must identify an entity slot")
        self.catalog = catalog
        self.reserved_slot_floor = int(reserved_slot_floor)
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
        free = ~state.active & (self._slots >= self.reserved_slot_floor)
        first_free = torch.where(
            free,
            self._slots,
            torch.full_like(self._slots, state.max_entities),
        ).amin(dim=1)
        known_card = request.card_id > 0
        if self.catalog is not None:
            known_card &= request.card_id < self.catalog.size
        success = (
            request.valid
            & ~state.game_over
            & (request.owner >= 0)
            & (request.owner < 2)
            & known_card
            & (request.hp > 0)
            & (first_free < state.max_entities)
        )
        safe_slot = first_free.clamp(max=state.max_entities - 1)
        destination = (
            functional.one_hot(safe_slot, num_classes=state.max_entities).to(torch.bool)
            & success[:, None]
        )

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
        write(state.target_id, torch.zeros_like(request.card_id))
        if self.catalog is None:
            write(state.damage, torch.zeros_like(request.hp))
            write(state.range_units, torch.zeros_like(request.x_units))
            write(state.sight_range_units, torch.zeros_like(request.x_units))
            write(state.speed_units_per_tick, torch.zeros_like(request.x_units))
            write(state.hit_cooldown_ticks, torch.zeros_like(request.deploy_ticks))
        else:
            safe_card = request.card_id.clamp(0, self.catalog.size - 1)
            write(state.kind, self.catalog.kind[safe_card])
            write(state.hp, self.catalog.hitpoints[safe_card])
            write(state.max_hp, self.catalog.hitpoints[safe_card])
            write(state.damage, self.catalog.damage[safe_card])
            write(state.range_units, self.catalog.range_units[safe_card])
            write(
                state.sight_range_units,
                self.catalog.sight_range_units[safe_card],
            )
            write(
                state.speed_units_per_tick,
                self.catalog.speed_units_per_tick[safe_card],
            )
            write(
                state.hit_cooldown_ticks,
                self.catalog.hit_cooldown_ticks[safe_card],
            )
        write(state.deploy_ticks, request.deploy_ticks.clamp(min=0).to(torch.int32))
        write(state.cooldown_ticks, torch.zeros_like(request.deploy_ticks))
        state.next_stable_id.add_(success.to(torch.int64))
        return success

    def deploy_many_once(
        self, requests: Sequence[FastDeploymentRequest]
    ) -> torch.Tensor:
        """Allocate each request once, in caller-provided deterministic order.

        This is separate from :meth:`step_tick` so both players' simultaneous
        policy requests can be resolved before combat advances.  The returned
        tensor is player/request-major with shape ``[batch, requests]``.
        """

        if not requests:
            return torch.zeros(
                (self.state.batch_size, 0),
                dtype=torch.bool,
                device=self.state.device,
            )
        return torch.stack(tuple(self._deploy(request) for request in requests), dim=1)

    def _ordinary_troop_phase(self) -> None:
        """Acquire, approach, and directly hit the nearest visible enemy."""

        state = self.state
        present = state.active & (state.hp > 0) & (state.deploy_ticks == 0)
        dx = state.x_units[:, None, :].to(torch.int64) - state.x_units[:, :, None].to(
            torch.int64
        )
        dy = state.y_units[:, None, :].to(torch.int64) - state.y_units[:, :, None].to(
            torch.int64
        )
        distance_sq = dx.square() + dy.square()
        sight_sq = state.sight_range_units.to(torch.int64).square()[:, :, None]
        candidate = (
            present[:, :, None]
            & present[:, None, :]
            & (state.owner[:, :, None] != state.owner[:, None, :])
            & (distance_sq <= sight_sq)
        )
        maximum = torch.iinfo(torch.int64).max
        unreachable = torch.full_like(distance_sq, maximum)
        nearest_distance = torch.where(candidate, distance_sq, unreachable).amin(dim=2)
        found = candidate.any(dim=2)
        distance_tie = candidate & (distance_sq == nearest_distance[:, :, None])
        candidate_id = state.stable_id[:, None, :].expand_as(distance_sq)
        selected_id = torch.where(
            distance_tie,
            candidate_id,
            torch.full_like(candidate_id, maximum),
        ).amin(dim=2)
        selected_slot = distance_tie & (candidate_id == selected_id[:, :, None])
        nearest_slot = selected_slot.to(torch.int64).argmax(dim=2)
        state.target_id.copy_(torch.where(found, selected_id, 0))

        target_x = state.x_units.gather(1, nearest_slot).to(torch.float32)
        target_y = state.y_units.gather(1, nearest_slot).to(torch.float32)
        delta_x = target_x - state.x_units.to(torch.float32)
        delta_y = target_y - state.y_units.to(torch.float32)
        distance = torch.sqrt(delta_x.square() + delta_y.square())
        attack_range = state.range_units.to(torch.float32).clamp(min=0)
        travel = torch.minimum(
            state.speed_units_per_tick.to(torch.float32).clamp(min=0),
            (distance - attack_range).clamp(min=0),
        )
        mobile = (
            found
            & present
            & (state.kind == 0)
            & (distance > attack_range)
            & (travel > 0)
        )
        denominator = distance.clamp(min=1.0)
        move_x = torch.round(delta_x * travel / denominator).to(torch.int32)
        move_y = torch.round(delta_y * travel / denominator).to(torch.int32)
        state.x_units.add_(torch.where(mobile, move_x, 0))
        state.y_units.add_(torch.where(mobile, move_y, 0))

        target_x = state.x_units.gather(1, nearest_slot).to(torch.float32)
        target_y = state.y_units.gather(1, nearest_slot).to(torch.float32)
        post_dx = target_x - state.x_units.to(torch.float32)
        post_dy = target_y - state.y_units.to(torch.float32)
        post_distance_sq = post_dx.square() + post_dy.square()
        attack = (
            found
            & present
            & (state.cooldown_ticks == 0)
            & (post_distance_sq <= attack_range.square())
            & (state.damage > 0)
        )
        hp_delta = torch.zeros_like(state.hp).scatter_add(
            1,
            nearest_slot,
            torch.where(attack, -state.damage, 0.0),
        )
        state.hp.add_(hp_delta).clamp_(min=0.0)
        state.cooldown_ticks.copy_(
            torch.where(attack, state.hit_cooldown_ticks, state.cooldown_ticks)
        )
        died = state.active & (state.hp <= 0)
        state.active.logical_and_(~died)
        state.stable_id.masked_fill_(died, 0)
        state.target_id.masked_fill_(died, 0)

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
        self._ordinary_troop_phase()
        state.tick.add_(live.to(torch.int64))
        return FastGymTickResult(
            committed=live,
            action_success=success_by_player,
            native_ticks=live.to(torch.int64),
            done=state.game_over.clone(),
            winner=state.winner.clone(),
        )
