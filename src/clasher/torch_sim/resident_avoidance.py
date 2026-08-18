"""Tensor-native pre-contact steering in stable entity-ID order.

The kernel ports ``Troop._update_native_avoidance``.  Physical slots may be
reused or scrambled; mover and candidate visitation always follows ascending
public entity identity.  Each fixed lane iteration operates over every battle
row at once and never calls a Python entity.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from clasher.native_tilemap import HALF_TILE_LOGIC_UNITS
from clasher.torch_sim.movement import normalized_vector_units
from clasher.torch_sim.movement_adapter import TensorMovementAdapter

_ID_SENTINEL = torch.iinfo(torch.int64).max


@dataclass
class TensorAvoidanceState:
    """Retained avoidance inputs aligned with movement-adapter slots."""

    entity_id: torch.Tensor
    present: torch.Tensor
    alive: torch.Tensor
    kind: torch.Tensor
    owner: torch.Tensor
    position_units: torch.Tensor
    facing_units: torch.Tensor
    collision_radius_units: torch.Tensor
    mass_milliunits: torch.Tensor
    air_collision: torch.Tensor
    stopped: torch.Tensor
    charging: torch.Tensor
    leap_clear: torch.Tensor
    route_cells: torch.Tensor
    route_count: torch.Tensor
    waypoint_units: torch.Tensor
    avoidance: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.entity_id.device

    @property
    def batch_size(self) -> int:
        return int(self.entity_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.entity_id.shape[1])

    @classmethod
    def from_movement_adapter(
        cls,
        adapter: TensorMovementAdapter,
        *,
        stopped: torch.Tensor,
        charging: torch.Tensor | None = None,
        leap_clear: torch.Tensor | None = None,
    ) -> TensorAvoidanceState:
        shape = adapter.entity_id.shape

        def boolean(value: torch.Tensor | None) -> torch.Tensor:
            if value is None:
                return torch.zeros(shape, dtype=torch.bool, device=adapter.device)
            result = torch.as_tensor(value, dtype=torch.bool, device=adapter.device)
            if result.shape != shape:
                raise ValueError("avoidance flags must have shape [batch, entity]")
            return result

        stopped_tensor = boolean(stopped)
        return cls(
            entity_id=adapter.entity_id,
            present=adapter.slot_present,
            alive=adapter.entity_active,
            kind=adapter.entity_kind,
            owner=adapter.player_id,
            position_units=adapter.position_units,
            facing_units=adapter.facing_units,
            collision_radius_units=adapter.collision_radius_units,
            mass_milliunits=adapter.mass_milliunits,
            air_collision=adapter.air_collision,
            stopped=stopped_tensor,
            charging=boolean(charging),
            leap_clear=boolean(leap_clear),
            route_cells=adapter.route_cells,
            route_count=adapter.route_count,
            waypoint_units=adapter.waypoint_units,
            avoidance=adapter.avoidance,
        )

    def validate(self) -> torch.Tensor:
        shape = self.entity_id.shape
        if len(shape) != 2:
            raise ValueError("avoidance entity tensors must have shape [batch, entity]")
        vector_names = {"position_units", "facing_units", "waypoint_units"}
        route_names = {"route_cells"}
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            expected = (
                (*shape, 2)
                if descriptor.name in vector_names
                else (*shape, value.shape[2], 2)
                if descriptor.name in route_names
                else shape
            )
            if value.shape != expected:
                raise ValueError(
                    f"{descriptor.name} has shape {tuple(value.shape)}, expected {expected}"
                )
            if value.device != self.device:
                raise ValueError("avoidance tensors use different devices")
        if self.device.type not in {"cpu", "cuda"}:
            return torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        active = self.present & self.alive
        valid_id = ~active | (self.entity_id > 0)
        keys = torch.where(active, self.entity_id, _ID_SENTINEL)
        ordered = torch.sort(keys, dim=1, stable=True).values
        duplicate = (ordered[:, 1:] == ordered[:, :-1]) & (
            ordered[:, 1:] != _ID_SENTINEL
        )
        return valid_id.all(dim=1) & ~duplicate.any(dim=1)


@dataclass(frozen=True)
class AvoidanceStepResult:
    supported_batch: torch.Tensor
    contacted: torch.Tensor
    moving_contacts: torch.Tensor
    static_contacts: torch.Tensor
    route_nodes_popped: torch.Tensor
    avoidance_before: torch.Tensor
    avoidance_after: torch.Tensor


def _decay(value: torch.Tensor) -> torch.Tensor:
    return torch.where(
        value < 0,
        torch.minimum(value + 10, torch.zeros_like(value)),
        torch.maximum(value - 10, torch.zeros_like(value)),
    )


def step_precontact_avoidance_(
    state: TensorAvoidanceState,
    *,
    battle_mask: torch.Tensor | None = None,
) -> AvoidanceStepResult:
    """Advance retained avoidance and static route-node removal one frame."""

    structural = state.validate()
    selected = (
        torch.ones(state.batch_size, dtype=torch.bool, device=state.device)
        if battle_mask is None
        else torch.as_tensor(battle_mask, dtype=torch.bool, device=state.device)
    )
    if selected.shape != (state.batch_size,):
        raise ValueError("battle_mask must have shape [batch]")
    supported = structural & selected
    before = state.avoidance.clone()
    contacted = torch.zeros_like(state.present)
    moving_contacts = torch.zeros_like(state.avoidance, dtype=torch.int32)
    static_contacts = torch.zeros_like(state.avoidance, dtype=torch.int32)
    route_popped = torch.zeros_like(state.route_count, dtype=torch.int32)

    active_object = (
        state.present & state.alive & ((state.kind == 0) | (state.kind == 1))
    )
    keys = torch.where(active_object, state.entity_id, _ID_SENTINEL)
    order = torch.argsort(keys, dim=1, stable=True)
    ordered_valid = torch.gather(active_object, 1, order)
    rows = torch.arange(state.batch_size, device=state.device)

    for mover_rank in range(state.max_entities):
        mover_slot = order[:, mover_rank]
        mover_index = (rows, mover_slot)
        mover = (
            supported & ordered_valid[:, mover_rank] & (state.kind[mover_index] == 0)
        )
        leap = mover & state.leap_clear[mover_index]
        leap_rows = rows[leap]
        state.avoidance[leap_rows, mover_slot[leap]] = 0

        facing = normalized_vector_units(state.facing_units[mover_index], 256)
        facing_nonzero = torch.any(facing != 0, dim=1)
        scan = mover & ~leap & ~state.stopped[mover_index] & facing_nonzero
        decay_only = mover & ~leap & ~scan
        moving_count = torch.zeros(
            state.batch_size, dtype=torch.int32, device=state.device
        )
        static_count = torch.zeros_like(moving_count)
        moving_side = torch.ones(
            state.batch_size, dtype=torch.bool, device=state.device
        )
        static_side = torch.ones_like(moving_side)

        own_position = state.position_units[mover_index]
        probe = own_position + facing
        own_radius = state.collision_radius_units[mover_index].clamp(0, 500)
        own_plane = state.air_collision[mover_index]
        own_mass = state.mass_milliunits[mover_index]

        for other_rank in range(state.max_entities):
            other_slot = order[:, other_rank]
            other_index = (rows, other_slot)
            candidate = (
                scan
                & ordered_valid[:, other_rank]
                & (other_slot != mover_slot)
                & (state.air_collision[other_index] == own_plane)
            )
            other_position = state.position_units[other_index]
            other_radius = state.collision_radius_units[other_index].clamp_min(0)
            probe_delta = other_position - probe
            query_radius = own_radius + other_radius
            candidate &= (probe_delta * probe_delta).sum(
                dim=1
            ) <= query_radius * query_radius
            relative = other_position - own_position
            cross = facing[:, 1] * relative[:, 0] - facing[:, 0] * relative[:, 1]
            geometric_side = cross < 0

            other_troop = candidate & (state.kind[other_index] == 0)
            other_facing = normalized_vector_units(state.facing_units[other_index], 256)
            direction_dot = (other_facing * facing).sum(dim=1)
            direction_dot = torch.where(
                state.stopped[other_index],
                torch.zeros_like(direction_dot),
                direction_dot,
            )
            approaching = direction_dot <= 0
            approaching &= ~state.charging[mover_index] | (
                own_mass <= state.mass_milliunits[other_index]
            )
            moving = other_troop & approaching
            moving_count += moving.to(torch.int32)
            inherited_side = state.avoidance[other_index] > 0
            candidate_side = torch.where(
                state.avoidance[other_index] != 0,
                inherited_side,
                geometric_side,
            )
            moving_side = torch.where(moving, candidate_side, moving_side)

            building = candidate & (state.kind[other_index] == 1)
            static_count += building.to(torch.int32)
            static_side = torch.where(building, geometric_side, static_side)

            can_pop = building & (state.route_count[mover_index] >= 2)
            head = state.route_cells[rows, mover_slot, 0]
            waypoint = head * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2
            delta = waypoint - other_position
            inside = (delta * delta).sum(dim=1) < other_radius * other_radius
            pop = can_pop & inside
            pop_rows = rows[pop]
            pop_slots = mover_slot[pop]
            if pop_rows.numel():
                current = state.route_cells[pop_rows, pop_slots]
                shifted = torch.roll(current, shifts=-1, dims=1)
                shifted[:, -1] = 0
                state.route_cells[pop_rows, pop_slots] = shifted
                state.route_count[pop_rows, pop_slots] -= 1
                route_popped[pop_rows, pop_slots] += 1

        has_contact = (moving_count + static_count) > 0
        side = torch.where(static_count > 0, static_side, moving_side)
        current = state.avoidance[mover_index]
        initialized = torch.where(
            side, torch.full_like(current, 200), torch.full_like(current, -200)
        )
        adjusted = (current + torch.where(side, 20, -20)).clamp(-200, 200)
        updated = torch.where(
            has_contact & (current == 0),
            initialized,
            torch.where(has_contact & (static_count > 0), adjusted, current),
        )
        updated = _decay(updated)
        write = scan | decay_only
        write_rows = rows[write]
        write_slots = mover_slot[write]
        state.avoidance[write_rows, write_slots] = updated[write]
        contacted[write_rows, write_slots] = has_contact[write]
        moving_contacts[write_rows, write_slots] = moving_count[write]
        static_contacts[write_rows, write_slots] = static_count[write]

        route_changed = route_popped[mover_index] > 0
        remaining = state.route_count[mover_index] > 0
        update_waypoint = mover & route_changed & remaining
        waypoint_rows = rows[update_waypoint]
        waypoint_slots = mover_slot[update_waypoint]
        if waypoint_rows.numel():
            head = state.route_cells[waypoint_rows, waypoint_slots, 0]
            state.waypoint_units[waypoint_rows, waypoint_slots] = (
                head * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2
            )

    return AvoidanceStepResult(
        supported_batch=supported,
        contacted=contacted,
        moving_contacts=moving_contacts,
        static_contacts=static_contacts,
        route_nodes_popped=route_popped,
        avoidance_before=before,
        avoidance_after=state.avoidance.clone(),
    )


__all__ = [
    "AvoidanceStepResult",
    "TensorAvoidanceState",
    "step_precontact_avoidance_",
]
