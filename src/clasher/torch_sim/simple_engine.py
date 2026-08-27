"""Minimal unified tensor tick for the practical reinforcement-learning Gym."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import torch

from .simple_attack_locks import (
    FastAttackLockState,
    FastAttackTimingCatalog,
    advance_fast_attack_lock_clocks_,
    commit_fast_attack_locks_,
    step_fast_attack_locks_,
)
from .simple_catalog import FastCardCatalog
from .simple_navigation import FastArenaNavigation, FastNavigationState
from .simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP, FastGymState
from .simple_targeting import FastTargetTraits, select_nearest_targets


@dataclass(frozen=True)
class FastDeploymentRequest:
    """At most one atomic card deployment request per batch row."""

    valid: torch.Tensor
    owner: torch.Tensor
    card_id: torch.Tensor
    kind: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    hp: torch.Tensor
    deploy_ticks: torch.Tensor
    summon_count: torch.Tensor
    summon_radius_units: torch.Tensor


@dataclass(frozen=True)
class FastGymTickResult:
    """Fixed-shape result with no fallback or dynamic event collection."""

    committed: torch.Tensor
    action_success: torch.Tensor
    native_ticks: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    attack_ready: torch.Tensor
    target_in_attack_range: torch.Tensor
    moved_distance_units: torch.Tensor


@dataclass(frozen=True)
class FastTargetSnapshot:
    """One fixed-shape target observation for every dense source slot.

    Coordinates retain both the target center and the native stop point at the
    source's ordinary range from its hitbox. Every plane is ``[B, E]`` and
    remains on the state device.
    """

    found: torch.Tensor
    target_slot: torch.Tensor
    target_stable_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    destination_x_units: torch.Tensor
    destination_y_units: torch.Tensor
    center_distance_units: torch.Tensor
    edge_distance_units: torch.Tensor
    within_attack_range: torch.Tensor


class FastTensorGym:
    """Mutation-only tensor engine with deterministic lowest-slot allocation."""

    def __init__(
        self,
        state: FastGymState,
        catalog: FastCardCatalog | None = None,
        *,
        reserved_slot_floor: int = 0,
        attack_timings: FastAttackTimingCatalog | None = None,
        attack_locks: FastAttackLockState | None = None,
    ) -> None:
        self.state = state
        if catalog is not None and catalog.device != state.device:
            raise ValueError("catalog and state must use the same device")
        if not 0 <= reserved_slot_floor < state.max_entities:
            raise ValueError("reserved_slot_floor must identify an entity slot")
        if (attack_timings is None) != (attack_locks is None):
            raise ValueError(
                "attack_timings and attack_locks must be supplied together"
            )
        if attack_timings is not None:
            if catalog is None:
                raise ValueError("attack timings require a card catalog")
            if attack_timings.size != catalog.size:
                raise ValueError("attack timings must align with the card catalog")
            if attack_timings.device != state.device:
                raise ValueError("attack timings must use the state device")
            assert attack_locks is not None
            if attack_locks.device != state.device:
                raise ValueError("attack locks must use the state device")
            if tuple(attack_locks.source_stable_id.shape) != tuple(state.active.shape):
                raise ValueError("attack locks must have shape [batch, entities]")
        self.catalog = catalog
        self.reserved_slot_floor = int(reserved_slot_floor)
        self.attack_timings = attack_timings
        self.attack_locks = attack_locks
        self._slots = torch.arange(
            state.max_entities, dtype=torch.int64, device=state.device
        ).view(1, -1)
        # Destination-aligned hook for lifecycle/modifier initialization.
        # It is overwritten on every deployment call and contains every child
        # materialized by the most recent atomic request group.
        self.spawned_mask = torch.zeros_like(state.active)
        self._target_unavailable = torch.zeros_like(state.active)
        self.navigation = FastArenaNavigation(
            FastNavigationState.empty(
                state.batch_size,
                state.max_entities,
                device=state.device,
            )
        )

    def _target_traits(self) -> FastTargetTraits:
        """Project card tables onto dense slots without card dispatch."""

        state = self.state
        building = state.kind == FAST_KIND_BUILDING
        if self.catalog is None:
            # Preserve the former permissive plane behavior for catalog-free
            # structural fixtures. Production always supplies a catalog.
            return FastTargetTraits(
                airborne=torch.zeros_like(state.active),
                building=building,
                attacks_air=torch.ones_like(state.active),
                attacks_ground=torch.ones_like(state.active),
                buildings_only=torch.zeros_like(state.active),
                collision_radius=torch.zeros_like(state.x_units),
            )
        safe_card = state.card_id.clamp(0, self.catalog.size - 1)
        known = (state.card_id > 0) & (state.card_id < self.catalog.size)
        tower = (state.card_id == 0) & building
        return FastTargetTraits(
            airborne=self.catalog.is_air[safe_card] & known,
            building=building,
            attacks_air=(self.catalog.attacks_air[safe_card] & known) | tower,
            attacks_ground=(self.catalog.attacks_ground[safe_card] & known) | tower,
            buildings_only=self.catalog.buildings_only[safe_card] & known,
            collision_radius=torch.where(
                known,
                self.catalog.collision_radius_units[safe_card],
                0,
            ),
        )

    def has_attack_range_target(self) -> torch.Tensor:
        """Return range presence without requiring the source to be actionable.

        Idle-hide mechanics must sense a nearby enemy while their source is
        itself combat-blocked. Candidate targets still obey the shared
        unavailable plane, deployment state, target categories, and air/ground
        capabilities used by ordinary acquisition.
        """

        targets = select_nearest_targets(
            self.state,
            self._target_traits(),
            source_disabled=torch.zeros_like(self.state.active),
            target_unavailable=self._target_unavailable,
        )
        return targets.within_attack_range

    def target_snapshot(
        self,
        *,
        source_disabled: torch.Tensor | None = None,
    ) -> FastTargetSnapshot:
        """Expose the shared deterministic acquisition result as dense tensors."""

        state = self.state
        if source_disabled is None:
            source_disabled = torch.zeros_like(state.active)
        elif source_disabled.shape != state.active.shape:
            raise ValueError("source_disabled must have shape [batch, entities]")
        elif source_disabled.device != state.device:
            raise ValueError("source_disabled must use the state device")
        elif source_disabled.dtype != torch.bool:
            raise ValueError("source_disabled must be bool")
        traits = self._target_traits()
        selected = select_nearest_targets(
            state,
            traits,
            source_disabled=source_disabled,
            target_unavailable=self._target_unavailable,
        )
        safe_slot = selected.target_slot.clamp(min=0)
        target_x = state.x_units.gather(1, safe_slot)
        target_y = state.y_units.gather(1, safe_slot)
        target_radius = traits.collision_radius.gather(1, safe_slot).clamp(min=0)
        delta_x = target_x.to(torch.float32) - state.x_units.to(torch.float32)
        delta_y = target_y.to(torch.float32) - state.y_units.to(torch.float32)
        stop_distance = state.range_units.clamp(min=0).to(
            torch.float32
        ) + target_radius.to(torch.float32)
        travel_distance = (selected.center_distance - stop_distance).clamp(min=0.0)
        scale = travel_distance / selected.center_distance.clamp_min(1.0)
        destination_x = state.x_units + torch.round(delta_x * scale).to(torch.int32)
        destination_y = state.y_units + torch.round(delta_y * scale).to(torch.int32)
        zeros = torch.zeros_like(state.x_units)
        return FastTargetSnapshot(
            found=selected.found,
            target_slot=selected.target_slot,
            target_stable_id=selected.target_id,
            target_x_units=torch.where(selected.found, target_x, zeros),
            target_y_units=torch.where(selected.found, target_y, zeros),
            destination_x_units=torch.where(selected.found, destination_x, zeros),
            destination_y_units=torch.where(selected.found, destination_y, zeros),
            center_distance_units=torch.where(
                selected.found,
                torch.round(selected.center_distance).to(torch.int32),
                zeros,
            ),
            edge_distance_units=torch.where(
                selected.found,
                torch.round(selected.edge_distance).to(torch.int32),
                zeros,
            ),
            within_attack_range=selected.within_attack_range,
        )

    def _navigation_targets(
        self,
        can_act: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Choose an enemy reserved building when ordinary sight is empty."""

        state = self.state
        delta_x = state.x_units[:, :, None].to(torch.int64) - state.x_units[
            :, None, :
        ].to(torch.int64)
        delta_y = state.y_units[:, :, None].to(torch.int64) - state.y_units[
            :, None, :
        ].to(torch.int64)
        distance_sq = delta_x.square() + delta_y.square()
        reserved_building = (
            (self._slots < self.reserved_slot_floor)
            & state.active
            & (state.hp > 0)
            & (state.kind == FAST_KIND_BUILDING)
            & (state.stable_id > 0)
            & ~self._target_unavailable
        )
        candidate = (
            can_act[:, :, None]
            & (state.kind[:, :, None] == 0)
            & reserved_building[:, None, :]
            & (state.owner[:, :, None] != state.owner[:, None, :])
        )
        maximum = torch.iinfo(torch.int64).max
        nearest_distance = torch.where(
            candidate,
            distance_sq,
            torch.full_like(distance_sq, maximum),
        ).amin(dim=2)
        distance_tie = candidate & (distance_sq == nearest_distance[:, :, None])
        candidate_id = state.stable_id[:, None, :].expand_as(distance_sq)
        selected_id = torch.where(
            distance_tie,
            candidate_id,
            torch.full_like(candidate_id, maximum),
        ).amin(dim=2)
        found = distance_tie.any(dim=2)
        selected = distance_tie & (candidate_id == selected_id[:, :, None])
        slot = selected.to(torch.int64).argmax(dim=2)
        distance = torch.sqrt(
            distance_sq.gather(2, slot[:, :, None]).squeeze(2).to(torch.float32)
        )
        return (
            found,
            slot,
            torch.where(found, selected_id, 0),
            torch.where(found, distance, torch.inf),
        )

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
            "summon_count",
            "summon_radius_units",
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
        known_card = request.card_id > 0
        if self.catalog is not None:
            known_card &= request.card_id < self.catalog.size
            safe_card = request.card_id.clamp(0, self.catalog.size - 1)
            summon_count = self.catalog.summon_count[safe_card].to(torch.int64)
            summon_radius = self.catalog.summon_radius_units[safe_card].to(torch.int32)
        else:
            summon_count = request.summon_count.to(torch.int64)
            summon_radius = request.summon_radius_units.to(torch.int32)
        enough_slots = free.sum(dim=1) >= summon_count
        success = (
            request.valid
            & ~state.game_over
            & (request.owner >= 0)
            & (request.owner < 2)
            & known_card
            & (request.hp > 0)
            & (summon_count > 0)
            & (summon_count <= state.max_entities - self.reserved_slot_floor)
            & enough_slots
        )
        lanes = self._slots.expand(state.batch_size, -1)
        child_valid = (lanes < summon_count[:, None]) & success[:, None]
        free_rank = free.to(torch.int64).cumsum(dim=1) - 1
        destination = (
            free[:, None, :]
            & (free_rank[:, None, :] == lanes[:, :, None])
            & child_valid[:, :, None]
        )
        destination_slot = destination.any(dim=1)
        child_for_slot = destination.to(torch.int64).argmax(dim=1)

        # A single numeric ring serves every ordinary multi-summon.  The
        # first point is forward, subsequent points proceed counter-clockwise,
        # and the forward component mirrors by owner.  One-child cards remain
        # exactly on the requested anchor.
        count_float = summon_count.clamp(min=1).to(torch.float32)[:, None]
        angles = lanes.to(torch.float32) * (2.0 * math.pi) / count_float + math.pi / 2.0
        multi = summon_count[:, None] > 1
        offset_x = torch.where(
            multi,
            torch.round(torch.cos(angles) * summon_radius[:, None]),
            torch.zeros_like(angles),
        ).to(torch.int32)
        forward = torch.where(
            request.owner[:, None] == 0,
            torch.ones_like(offset_x),
            torch.full_like(offset_x, -1),
        )
        offset_y = torch.where(
            multi,
            torch.round(torch.sin(angles) * summon_radius[:, None]).to(torch.int32)
            * forward,
            torch.zeros_like(offset_x),
        )

        def write(field: torch.Tensor, child_value: torch.Tensor) -> None:
            value_for_slot = child_value.gather(1, child_for_slot)
            field.copy_(torch.where(destination_slot, value_for_slot, field))

        def repeat(value: torch.Tensor) -> torch.Tensor:
            return value[:, None].expand(-1, state.max_entities)

        write(state.active, torch.ones_like(child_valid))
        write(state.stable_id, state.next_stable_id[:, None] + lanes)
        write(state.kind, repeat(request.kind.to(torch.int8)))
        write(state.owner, repeat(request.owner.to(torch.int8)))
        write(state.card_id, repeat(request.card_id.to(torch.int64)))
        write(state.x_units, request.x_units[:, None].to(torch.int32) + offset_x)
        write(state.y_units, request.y_units[:, None].to(torch.int32) + offset_y)
        write(state.hp, repeat(request.hp.to(torch.float32)))
        write(state.max_hp, repeat(request.hp.to(torch.float32)))
        write(state.target_id, torch.zeros_like(lanes))
        if self.catalog is None:
            write(state.damage, torch.zeros_like(lanes, dtype=torch.float32))
            write(state.range_units, torch.zeros_like(lanes, dtype=torch.int32))
            write(
                state.sight_range_units,
                torch.zeros_like(lanes, dtype=torch.int32),
            )
            write(
                state.speed_units_per_tick,
                torch.zeros_like(lanes, dtype=torch.int32),
            )
            write(
                state.hit_cooldown_ticks,
                torch.zeros_like(lanes, dtype=torch.int32),
            )
        else:
            write(state.kind, repeat(self.catalog.kind[safe_card]))
            write(state.hp, repeat(self.catalog.hitpoints[safe_card]))
            write(state.max_hp, repeat(self.catalog.hitpoints[safe_card]))
            write(state.damage, repeat(self.catalog.damage[safe_card]))
            write(state.range_units, repeat(self.catalog.range_units[safe_card]))
            write(
                state.sight_range_units,
                repeat(self.catalog.sight_range_units[safe_card]),
            )
            write(
                state.speed_units_per_tick,
                repeat(self.catalog.speed_units_per_tick[safe_card]),
            )
            write(
                state.hit_cooldown_ticks,
                repeat(self.catalog.hit_cooldown_ticks[safe_card]),
            )
        write(
            state.deploy_ticks,
            repeat(request.deploy_ticks.clamp(min=0).to(torch.int32)),
        )
        write(state.cooldown_ticks, torch.zeros_like(lanes, dtype=torch.int32))
        state.next_stable_id.add_(
            torch.where(success, summon_count, torch.zeros_like(summon_count))
        )
        self.spawned_mask.copy_(destination_slot)
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
            self.spawned_mask.zero_()
            return torch.zeros(
                (self.state.batch_size, 0),
                dtype=torch.bool,
                device=self.state.device,
            )
        accepted: list[torch.Tensor] = []
        spawned = torch.zeros_like(self.state.active)
        for request in requests:
            accepted.append(self._deploy(request))
            spawned |= self.spawned_mask
        self.spawned_mask.copy_(spawned)
        return torch.stack(tuple(accepted), dim=1)

    def _ordinary_troop_phase(
        self,
        disabled: torch.Tensor,
        speed_multiplier: torch.Tensor,
        cooldown_decrement: torch.Tensor,
        cooldown_floor_ticks: torch.Tensor,
        clear_source_lock: torch.Tensor,
        reload_source_attack: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Acquire and approach, returning attacks ready for effect allocation.

        Disabled entities remain present as targets but cannot acquire a
        target, move, or attack during this phase. HP is not mutated here;
        attack work advances in the lock-owned clock, while a complete cycle
        is installed only after the unified runtime allocates an effect slot.
        """

        state = self.state
        present = state.active & (state.hp > 0) & (state.deploy_ticks == 0)
        can_act = present & ~disabled
        traits = self._target_traits()
        lock_step = None
        locked_source = torch.zeros_like(state.active)
        if self.attack_timings is not None:
            assert self.attack_locks is not None
            safe_card = state.card_id.clamp(0, self.attack_timings.size - 1)
            known = (state.card_id > 0) & (state.card_id < self.attack_timings.size)
            locked_source = (
                known & self.attack_timings.ordinary_attack_supported[safe_card]
            )
            same_generation = (
                self.attack_locks.source_stable_id == state.stable_id
            ) & (state.stable_id > 0)
            # ``FastGymState.cooldown_ticks`` remains the shared observation
            # and mechanic-facing plane.  A subsystem may impose a longer
            # cooldown between ticks; absorb only that monotonic extension
            # into the lock owner, never a shorter external overwrite.
            self.attack_locks.cooldown_ticks.copy_(
                torch.where(
                    same_generation & locked_source,
                    torch.maximum(
                        self.attack_locks.cooldown_ticks,
                        state.cooldown_ticks.clamp(min=0),
                    ),
                    self.attack_locks.cooldown_ticks,
                )
            )
            reloaded = (
                reload_source_attack
                & locked_source
                & same_generation
                & state.active
                & (state.hp > 0)
            )
            self.attack_locks.cooldown_ticks.copy_(
                torch.where(
                    reloaded,
                    torch.maximum(
                        self.attack_locks.cooldown_ticks,
                        self.attack_timings.hit_cycle_ticks[safe_card],
                    ),
                    self.attack_locks.cooldown_ticks,
                )
            )
            lock_step = step_fast_attack_locks_(
                self.attack_locks,
                self.attack_timings,
                state,
                traits,
                source_disabled=disabled,
                target_unavailable=self._target_unavailable,
                clear_source_lock=clear_source_lock,
                cooldown_decrement=torch.zeros_like(cooldown_decrement),
            )
        targets = select_nearest_targets(
            state,
            traits,
            source_disabled=disabled | locked_source,
            target_unavailable=self._target_unavailable,
        )
        # Reserved arena fixtures retain their stable-ID target while it
        # remains legal and in sight. Ordinary public-card sources will move
        # to the generalized attack-lock subsystem separately; keeping this
        # adapter tower-only avoids introducing a second broad lock policy.
        current_match = (
            state.active[:, None, :]
            & (state.hp[:, None, :] > 0)
            & (state.target_id[:, :, None] > 0)
            & (state.target_id[:, :, None] == state.stable_id[:, None, :])
        )
        current_found = current_match.any(dim=2)
        current_slot = current_match.to(torch.int8).argmax(dim=2).to(torch.int64)
        current_air = traits.airborne.gather(1, current_slot)
        current_building = traits.building.gather(1, current_slot)
        current_plane_allowed = torch.where(
            current_air,
            traits.attacks_air,
            traits.attacks_ground,
        )
        current_category_allowed = ~traits.buildings_only | current_building
        current_dx = state.x_units.gather(1, current_slot).to(
            torch.float32
        ) - state.x_units.to(torch.float32)
        current_dy = state.y_units.gather(1, current_slot).to(
            torch.float32
        ) - state.y_units.to(torch.float32)
        current_edge_distance = (
            torch.sqrt(current_dx.square() + current_dy.square())
            - traits.collision_radius.gather(1, current_slot)
            .clamp(min=0)
            .to(torch.float32)
        ).clamp_min(0.0)
        retain_current = (
            (self._slots < self.reserved_slot_floor)
            & can_act
            & current_found
            & ~self._target_unavailable.gather(1, current_slot)
            & (state.owner != state.owner.gather(1, current_slot))
            & current_plane_allowed
            & current_category_allowed
            & (current_edge_distance <= state.sight_range_units.clamp(min=0))
        )
        legacy_found = targets.found | retain_current
        legacy_target_slot = torch.where(
            retain_current,
            current_slot,
            targets.target_slot.clamp(min=0),
        )
        legacy_target_id = torch.where(
            retain_current,
            state.target_id,
            targets.target_id,
        )
        legacy_edge_distance = torch.where(
            retain_current,
            current_edge_distance,
            targets.edge_distance,
        )
        if lock_step is None:
            found = legacy_found
            selected_target_slot = legacy_target_slot
            selected_target_id = legacy_target_id
            selected_edge_distance = legacy_edge_distance
        else:
            safe_lock_slot = lock_step.target_slot.clamp(min=0)
            lock_dx = state.x_units.gather(1, safe_lock_slot).to(
                torch.float32
            ) - state.x_units.to(torch.float32)
            lock_dy = state.y_units.gather(1, safe_lock_slot).to(
                torch.float32
            ) - state.y_units.to(torch.float32)
            lock_edge_distance = (
                torch.sqrt(lock_dx.square() + lock_dy.square())
                - traits.collision_radius.gather(1, safe_lock_slot)
                .clamp(min=0)
                .to(torch.float32)
            ).clamp_min(0.0)
            found = torch.where(locked_source, lock_step.target_found, legacy_found)
            selected_target_slot = torch.where(
                locked_source,
                safe_lock_slot,
                legacy_target_slot,
            )
            selected_target_id = torch.where(
                locked_source,
                lock_step.target_stable_id,
                legacy_target_id,
            )
            selected_edge_distance = torch.where(
                locked_source,
                lock_edge_distance,
                legacy_edge_distance,
            )
        navigation_found, navigation_slot, navigation_id, _ = self._navigation_targets(
            can_act & ~found
        )
        has_destination = found | navigation_found
        nearest_slot = torch.where(
            found,
            selected_target_slot,
            navigation_slot,
        )
        state.target_id.copy_(torch.where(found, selected_target_id, navigation_id))

        target_x_units = state.x_units.gather(1, nearest_slot)
        target_y_units = state.y_units.gather(1, nearest_slot)
        target_owner = state.owner.gather(1, nearest_slot)
        route = self.navigation.route_(
            active=has_destination & can_act & (state.kind == FAST_KIND_TROOP),
            mover_stable_id=state.stable_id,
            owner=state.owner,
            airborne=traits.airborne,
            x_units=state.x_units,
            y_units=state.y_units,
            target_stable_id=state.target_id,
            target_owner=target_owner,
            target_x_units=target_x_units,
            target_y_units=target_y_units,
        )
        delta_x = route.waypoint_x_units.to(torch.float32) - state.x_units.to(
            torch.float32
        )
        delta_y = route.waypoint_y_units.to(torch.float32) - state.y_units.to(
            torch.float32
        )
        waypoint_distance = torch.sqrt(delta_x.square() + delta_y.square())
        attack_range = state.range_units.to(torch.float32).clamp(min=0)
        effective_speed = state.speed_units_per_tick.to(
            torch.float32
        ) * speed_multiplier.clamp(min=0.0)
        approach_travel = torch.minimum(
            effective_speed,
            (selected_edge_distance - attack_range).clamp(min=0),
        )
        travel = torch.where(
            found,
            approach_travel,
            effective_speed,
        )
        travel = torch.minimum(travel, waypoint_distance)
        mobile = (
            has_destination
            & can_act
            & (state.kind == FAST_KIND_TROOP)
            & (~found | (selected_edge_distance > attack_range))
            & (travel > 0)
        )
        denominator = waypoint_distance.clamp(min=1.0)
        move_x = torch.round(delta_x * travel / denominator).to(torch.int32)
        move_y = torch.round(delta_y * travel / denominator).to(torch.int32)
        state.x_units.add_(torch.where(mobile, move_x, 0))
        state.y_units.add_(torch.where(mobile, move_y, 0))
        moved_distance = torch.where(
            mobile,
            torch.round(
                torch.sqrt(
                    move_x.to(torch.float32).square()
                    + move_y.to(torch.float32).square()
                )
            ).to(torch.int32),
            0,
        )

        target_x = state.x_units.gather(1, nearest_slot).to(torch.float32)
        target_y = state.y_units.gather(1, nearest_slot).to(torch.float32)
        post_dx = target_x - state.x_units.to(torch.float32)
        post_dy = target_y - state.y_units.to(torch.float32)
        target_radius = traits.collision_radius.gather(1, nearest_slot).clamp(min=0)
        post_edge_distance = (
            torch.sqrt(post_dx.square() + post_dy.square()) - target_radius
        ).clamp_min(0.0)
        selected_in_attack_range = (
            found & can_act & (post_edge_distance <= attack_range) & (state.damage > 0)
        )
        idle_floor = torch.where(
            selected_in_attack_range,
            torch.zeros_like(cooldown_floor_ticks),
            cooldown_floor_ticks.clamp(min=0),
        )
        cooling = can_act & ~locked_source & (state.cooldown_ticks > idle_floor)
        state.cooldown_ticks.copy_(
            torch.where(
                cooling,
                torch.maximum(
                    state.cooldown_ticks - cooldown_decrement.clamp(min=0),
                    idle_floor,
                ),
                state.cooldown_ticks,
            )
        )
        legacy_attack_ready = selected_in_attack_range & (state.cooldown_ticks == 0)
        if lock_step is None:
            attack_ready = legacy_attack_ready
            target_in_attack_range = selected_in_attack_range
        else:
            assert self.attack_locks is not None
            assert self.attack_timings is not None
            lock_clock = advance_fast_attack_lock_clocks_(
                self.attack_locks,
                self.attack_timings,
                state,
                target_in_attack_range=selected_in_attack_range & locked_source,
                source_disabled=disabled,
                clear_source_lock=clear_source_lock,
                cooldown_decrement=cooldown_decrement,
            )
            state.cooldown_ticks.copy_(
                torch.where(
                    locked_source,
                    lock_clock.cooldown_ticks,
                    state.cooldown_ticks,
                )
            )
            attack_ready = torch.where(
                locked_source,
                lock_clock.attack_allowed,
                legacy_attack_ready,
            )
            target_in_attack_range = selected_in_attack_range
        return attack_ready, target_in_attack_range, moved_distance

    def commit_attacks_(
        self, attack_ready: torch.Tensor, effect_allocated: torch.Tensor
    ) -> torch.Tensor:
        """Start cooldown once for attacks that obtained an effect slot."""

        expected = self.state.active.shape
        for name, value in (
            ("attack_ready", attack_ready),
            ("effect_allocated", effect_allocated),
        ):
            if value.shape != expected:
                raise ValueError(f"{name} must have shape [batch, entities]")
            if value.device != self.state.device:
                raise ValueError(f"{name} must use the state device")
            if value.dtype != torch.bool:
                raise ValueError(f"{name} must be bool")
        locked_source = torch.zeros_like(self.state.active)
        locked_committed = torch.zeros_like(self.state.active)
        if self.attack_timings is not None:
            assert self.attack_locks is not None
            safe_card = self.state.card_id.clamp(0, self.attack_timings.size - 1)
            known = (self.state.card_id > 0) & (
                self.state.card_id < self.attack_timings.size
            )
            locked_source = (
                known & self.attack_timings.ordinary_attack_supported[safe_card]
            )
            locked_committed = commit_fast_attack_locks_(
                self.attack_locks,
                self.attack_timings,
                self.state,
                attack_allowed=attack_ready & locked_source,
                effect_allocated=effect_allocated,
            )
        legacy_committed = (
            attack_ready & effect_allocated & self.state.active & ~locked_source
        )
        committed = locked_committed | legacy_committed
        self.state.cooldown_ticks.copy_(
            torch.where(
                legacy_committed,
                self.state.hit_cooldown_ticks,
                self.state.cooldown_ticks,
            )
        )
        if self.attack_locks is not None:
            self.state.cooldown_ticks.copy_(
                torch.where(
                    locked_source,
                    self.attack_locks.cooldown_ticks,
                    self.state.cooldown_ticks,
                )
            )
        return committed

    def step_tick(
        self,
        request: FastDeploymentRequest | None = None,
        *,
        disabled: torch.Tensor | None = None,
        speed_multiplier: torch.Tensor | None = None,
        cooldown_decrement: torch.Tensor | None = None,
        cooldown_floor_ticks: torch.Tensor | None = None,
        clear_source_lock: torch.Tensor | None = None,
        reload_source_attack: torch.Tensor | None = None,
    ) -> FastGymTickResult:
        """Advance every live row once and optionally allocate one entity.

        The hot path has no ``item()``, ``nonzero()``, host transfer, clone, or
        per-card dispatch.  Full mechanics are intentionally layered onto this
        fixed-shape state instead of reproducing the oracle's event graph.
        """

        state = self.state
        if disabled is None:
            disabled = torch.zeros_like(state.active)
        elif disabled.shape != state.active.shape:
            raise ValueError("disabled must have shape [batch, entities]")
        elif disabled.device != state.device:
            raise ValueError("disabled must use the state device")
        elif disabled.dtype != torch.bool:
            raise ValueError("disabled must be bool")
        if speed_multiplier is None:
            speed_multiplier = torch.ones_like(state.damage)
        elif speed_multiplier.shape != state.active.shape:
            raise ValueError("speed_multiplier must have shape [batch, entities]")
        elif speed_multiplier.device != state.device:
            raise ValueError("speed_multiplier must use the state device")
        elif speed_multiplier.dtype != torch.float32:
            raise ValueError("speed_multiplier must be float32")
        if cooldown_decrement is None:
            cooldown_decrement = torch.ones_like(
                state.cooldown_ticks, dtype=torch.int32
            )
        elif cooldown_decrement.shape != state.active.shape:
            raise ValueError("cooldown_decrement must have shape [batch, entities]")
        elif cooldown_decrement.device != state.device:
            raise ValueError("cooldown_decrement must use the state device")
        elif cooldown_decrement.dtype != torch.int32:
            raise ValueError("cooldown_decrement must be int32")
        if cooldown_floor_ticks is None:
            cooldown_floor_ticks = torch.zeros_like(state.cooldown_ticks)
        elif cooldown_floor_ticks.shape != state.active.shape:
            raise ValueError("cooldown_floor_ticks must have shape [batch, entities]")
        elif cooldown_floor_ticks.device != state.device:
            raise ValueError("cooldown_floor_ticks must use the state device")
        elif cooldown_floor_ticks.dtype != torch.int32:
            raise ValueError("cooldown_floor_ticks must be int32")
        if clear_source_lock is None:
            clear_source_lock = torch.zeros_like(state.active)
        elif clear_source_lock.shape != state.active.shape:
            raise ValueError("clear_source_lock must have shape [batch, entities]")
        elif clear_source_lock.device != state.device:
            raise ValueError("clear_source_lock must use the state device")
        elif clear_source_lock.dtype != torch.bool:
            raise ValueError("clear_source_lock must be bool")
        if reload_source_attack is None:
            reload_source_attack = torch.zeros_like(state.active)
        elif reload_source_attack.shape != state.active.shape:
            raise ValueError("reload_source_attack must have shape [batch, entities]")
        elif reload_source_attack.device != state.device:
            raise ValueError("reload_source_attack must use the state device")
        elif reload_source_attack.dtype != torch.bool:
            raise ValueError("reload_source_attack must be bool")
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
        (
            attack_ready,
            target_in_attack_range,
            moved_distance,
        ) = self._ordinary_troop_phase(
            disabled,
            speed_multiplier,
            cooldown_decrement,
            cooldown_floor_ticks,
            clear_source_lock,
            reload_source_attack,
        )
        state.tick.add_(live.to(torch.int64))
        return FastGymTickResult(
            committed=live,
            action_success=success_by_player,
            native_ticks=live.to(torch.int64),
            done=state.game_over.clone(),
            winner=state.winner.clone(),
            attack_ready=attack_ready,
            target_in_attack_range=target_in_attack_range,
            moved_distance_units=moved_distance,
        )
