"""Tensor-native exact path planning on the serialized standard arena.

The planner ports the native first-discovery binary heap rather than replacing
it with a relaxed shortest-path algorithm. Equal priorities therefore retain
the heap topology and neighbor insertion order observed by the Python oracle.
All mutable search state is dense tensor storage; no ``Entity``, ``Position``,
or Python route objects enter the production path.

The exact heap is deliberately a correctness implementation: a miss may run
``CELL_COUNT * len(NATIVE_NEIGHBORS) * heap_depth`` tensor operations. That is
parity evidence, not a production-throughput claim. Resident callers should
retain :class:`TensorResidentPathCache` so repeated keys use its bounded exact
lookup and bypass the heap.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import torch

from clasher.native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_BLOCKED_RIVER_ROWS,
    STANDARD_BRIDGE_CELL_RANGES,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
)

from .movement import integer_sqrt_tensor, stable_entity_order_mask

CELL_COUNT = STANDARD_PATH_WIDTH * STANDARD_PATH_HEIGHT
CELL_CENTER_OFFSET = HALF_TILE_LOGIC_UNITS // 2
ARENA_WIDTH_UNITS = STANDARD_PATH_WIDTH * HALF_TILE_LOGIC_UNITS
ARENA_HEIGHT_UNITS = STANDARD_PATH_HEIGHT * HALF_TILE_LOGIC_UNITS
NATIVE_NEIGHBORS = (
    (0, -1, 10),
    (0, 1, 10),
    (-1, 0, 10),
    (1, 0, 10),
    (-1, -1, 14),
    (-1, 1, 14),
    (1, 1, 14),
    (1, -1, 14),
)


def validate_resident_path_device(device: str | torch.device) -> torch.device:
    result = torch.device(device)
    if result.type not in {"cpu", "cuda"}:
        raise RuntimeError(
            "resident route planning supports exact CPU/CUDA int64 only; "
            f"device type {result.type!r} is unsupported"
        )
    return result


@lru_cache(maxsize=4)
def _static_map(
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    cell_x = torch.arange(STANDARD_PATH_WIDTH, device=device).repeat(
        STANDARD_PATH_HEIGHT
    )
    cell_y = torch.arange(STANDARD_PATH_HEIGHT, device=device).repeat_interleave(
        STANDARD_PATH_WIDTH
    )
    lane = torch.tensor(
        [ord(value) - ord("0") for row in STANDARD_PATH_ROWS for value in row],
        dtype=torch.int64,
        device=device,
    )
    blocked = torch.zeros(CELL_COUNT, dtype=torch.bool, device=device)
    for river_y in STANDARD_BLOCKED_RIVER_ROWS:
        for x in range(STANDARD_PATH_WIDTH):
            if not any(start <= x <= end for start, end in STANDARD_BRIDGE_CELL_RANGES):
                blocked[river_y * STANDARD_PATH_WIDTH + x] = True
    return cell_x, cell_y, lane, blocked


def _cell_for_position(position_units: torch.Tensor) -> torch.Tensor:
    cell = torch.div(position_units, HALF_TILE_LOGIC_UNITS, rounding_mode="trunc")
    x = torch.clamp(cell[..., 0], 0, STANDARD_PATH_WIDTH - 1)
    y = torch.clamp(cell[..., 1], 0, STANDARD_PATH_HEIGHT - 1)
    return torch.stack((x, y), dim=-1)


def tensor_route_goal_cells(
    mover_position_units: torch.Tensor,
    target_position_units: torch.Tensor,
    required_range_units: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the exact y-major/x-minor native route goal for every lane."""

    if mover_position_units.shape != target_position_units.shape:
        raise ValueError("mover and target position shapes differ")
    if mover_position_units.shape[-1] != 2:
        raise ValueError("positions must end in an (x, y) axis")
    device = validate_resident_path_device(mover_position_units.device)
    prefix = mover_position_units.shape[:-1]
    mover = mover_position_units.reshape(-1, 2).to(torch.int64)
    target = target_position_units.reshape(-1, 2).to(torch.int64)
    required = torch.clamp(required_range_units.reshape(-1).to(torch.int64), min=0)
    cell_x, cell_y, _, _ = _static_map(device)
    center_x = cell_x * HALF_TILE_LOGIC_UNITS + CELL_CENTER_OFFSET
    center_y = cell_y * HALF_TILE_LOGIC_UNITS + CELL_CENTER_OFFSET
    target_dx = center_x[None, :] - target[:, 0, None]
    target_dy = center_y[None, :] - target[:, 1, None]
    inside = target_dx * target_dx + target_dy * target_dy <= required[:, None] ** 2
    mover_dx = center_x[None, :] - mover[:, 0, None]
    mover_dy = center_y[None, :] - mover[:, 1, None]
    distance = mover_dx * mover_dx + mover_dy * mover_dy
    sentinel = torch.iinfo(torch.int64).max
    selected = torch.argmin(torch.where(inside, distance, sentinel), dim=1)
    valid = inside.any(dim=1)
    goal = torch.stack(
        (selected % STANDARD_PATH_WIDTH, selected // STANDARD_PATH_WIDTH), dim=-1
    )
    goal = torch.where(valid[:, None], goal, -1)
    return goal.reshape(*prefix, 2), valid.reshape(*prefix)


def _terrain_costs(
    lane_id: torch.Tensor,
    jump_height: torch.Tensor,
    lane_map: torch.Tensor,
    blocked_map: torch.Tensor,
) -> torch.Tensor:
    same_lane = lane_map[None, :] == lane_id[:, None]
    labeled = lane_map[None, :] > 0
    land = torch.where(
        ~labeled,
        20,
        torch.where(same_lane, 1, 5),
    )
    water = torch.where(jump_height[:, None], 20, 800)
    return torch.where(blocked_map[None, :], water, land).to(torch.int64)


def _heap_priority(
    heap: torch.Tensor,
    priorities: torch.Tensor,
    index: torch.Tensor,
) -> torch.Tensor:
    row = torch.arange(heap.shape[0], device=heap.device)
    cell = heap[row, torch.clamp(index, 0, heap.shape[1] - 1)]
    return priorities[row, torch.clamp(cell, min=0)]


def _heap_pop(
    heap: torch.Tensor,
    heap_size: torch.Tensor,
    priorities: torch.Tensor,
    active: torch.Tensor,
) -> torch.Tensor:
    rows = torch.arange(heap.shape[0], device=heap.device)
    root = heap[:, 0].clone()
    old_size = heap_size.clone()
    new_size = torch.where(active, torch.clamp(old_size - 1, min=0), old_size)
    last_index = torch.clamp(old_size - 1, min=0)
    last = heap[rows, last_index]
    current_root = heap[:, 0]
    heap[rows, last_index] = torch.where(active, -1, heap[rows, last_index])
    install = active & (new_size > 0)
    heap[:, 0] = torch.where(install, last, current_root)
    heap_size.copy_(new_size)

    index = torch.zeros_like(heap_size)
    for _ in range(12):
        right = index * 2 + 2
        left = index * 2 + 1
        chosen = index.clone()
        chosen_priority = _heap_priority(heap, priorities, chosen)
        right_valid = install & (right < new_size)
        right_priority = _heap_priority(heap, priorities, right)
        choose_right = right_valid & (right_priority < chosen_priority)
        chosen = torch.where(choose_right, right, chosen)
        chosen_priority = torch.where(choose_right, right_priority, chosen_priority)
        left_valid = install & (left < new_size)
        left_priority = _heap_priority(heap, priorities, left)
        choose_left = left_valid & (left_priority < chosen_priority)
        chosen = torch.where(choose_left, left, chosen)
        swap = install & (chosen != index)
        current_value = heap[rows, index].clone()
        chosen_value = heap[rows, chosen].clone()
        heap[rows, index] = torch.where(swap, chosen_value, heap[rows, index])
        heap[rows, chosen] = torch.where(swap, current_value, heap[rows, chosen])
        index = torch.where(swap, chosen, index)
        install &= swap
    return torch.where(active, root, -1)


def _heap_push(
    heap: torch.Tensor,
    heap_size: torch.Tensor,
    priorities: torch.Tensor,
    cell: torch.Tensor,
    active: torch.Tensor,
) -> None:
    rows = torch.arange(heap.shape[0], device=heap.device)
    insert = torch.clamp(heap_size, 0, heap.shape[1] - 1)
    heap[rows, insert] = torch.where(active, cell, heap[rows, insert])
    heap_size.add_(active.to(torch.int64))
    index = insert
    moving = active.clone()
    for _ in range(12):
        parent = torch.div(torch.clamp(index - 1, min=0), 2, rounding_mode="floor")
        current_priority = _heap_priority(heap, priorities, index)
        parent_priority = _heap_priority(heap, priorities, parent)
        swap = moving & (index > 0) & (parent_priority > current_priority)
        current_value = heap[rows, index].clone()
        parent_value = heap[rows, parent].clone()
        heap[rows, index] = torch.where(swap, parent_value, heap[rows, index])
        heap[rows, parent] = torch.where(swap, current_value, heap[rows, parent])
        index = torch.where(swap, parent, index)
        moving &= swap


def _native_heap_routes(
    start_cell: torch.Tensor,
    goal_cell: torch.Tensor,
    lane_id: torch.Tensor,
    jump_height: torch.Tensor,
    active: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return parent tables and found flags for flattened route queries."""

    route_count = start_cell.shape[0]
    device = start_cell.device
    _, _, lane_map, blocked_map = _static_map(device)
    costs = _terrain_costs(lane_id, jump_height, lane_map, blocked_map)
    start = start_cell[:, 1] * STANDARD_PATH_WIDTH + start_cell[:, 0]
    goal = goal_cell[:, 1] * STANDARD_PATH_WIDTH + goal_cell[:, 0]
    parents = torch.full(
        (route_count, CELL_COUNT), -1, dtype=torch.int64, device=device
    )
    priorities = torch.zeros(
        (route_count, CELL_COUNT), dtype=torch.int64, device=device
    )
    discovered = torch.zeros((route_count, CELL_COUNT), dtype=torch.bool, device=device)
    heap = torch.full((route_count, CELL_COUNT), -1, dtype=torch.int64, device=device)
    heap[:, 0] = torch.where(active, start, -1)
    heap_size = active.to(torch.int64)
    discovered.scatter_(1, start[:, None], active[:, None])
    found = torch.zeros(route_count, dtype=torch.bool, device=device)
    rows = torch.arange(route_count, device=device)

    for _ in range(CELL_COUNT):
        expanding = active & ~found & (heap_size > 0)
        if device.type == "cpu" and not bool(expanding.any().item()):
            break
        current = _heap_pop(heap, heap_size, priorities, expanding)
        reached = expanding & (current == goal)
        found |= reached
        expand = expanding & ~reached
        current_x = current % STANDARD_PATH_WIDTH
        current_y = torch.div(current, STANDARD_PATH_WIDTH, rounding_mode="floor")
        current_priority = priorities[rows, torch.clamp(current, min=0)]
        goal_x = goal_cell[:, 0]
        goal_y = goal_cell[:, 1]
        for delta_x, delta_y, step_cost in NATIVE_NEIGHBORS:
            neighbor_x = current_x + delta_x
            neighbor_y = current_y + delta_y
            in_bounds = (
                (neighbor_x >= 0)
                & (neighbor_x < STANDARD_PATH_WIDTH)
                & (neighbor_y >= 0)
                & (neighbor_y < STANDARD_PATH_HEIGHT)
            )
            neighbor = neighbor_y * STANDARD_PATH_WIDTH + neighbor_x
            safe_neighbor = torch.clamp(neighbor, 0, CELL_COUNT - 1)
            fresh = expand & in_bounds & ~discovered[rows, safe_neighbor]
            discovered[rows, safe_neighbor] |= fresh
            parents[rows, safe_neighbor] = torch.where(
                fresh, current, parents[rows, safe_neighbor]
            )
            heuristic = 10 * torch.maximum(
                torch.abs(goal_x - neighbor_x),
                torch.abs(goal_y - neighbor_y),
            )
            candidate_priority = (
                current_priority
                + int(step_cost) * costs[rows, safe_neighbor]
                + heuristic
            )
            priorities[rows, safe_neighbor] = torch.where(
                fresh,
                candidate_priority,
                priorities[rows, safe_neighbor],
            )
            _heap_push(heap, heap_size, priorities, safe_neighbor, fresh)
    return parents, found


@dataclass(frozen=True)
class TensorResidentPathCacheLookup:
    hit: torch.Tensor
    route_cells: torch.Tensor
    route_count: torch.Tensor


@dataclass
class TensorResidentPathCache:
    """Bounded open-addressed cache for exact retained standard-arena routes."""

    valid: torch.Tensor
    keys: torch.Tensor
    route_cells: torch.Tensor
    route_count: torch.Tensor
    max_probe: int

    @property
    def device(self) -> torch.device:
        return self.keys.device

    @property
    def capacity(self) -> int:
        return int(self.keys.shape[0])

    @property
    def route_capacity(self) -> int:
        return int(self.route_cells.shape[1])

    @classmethod
    def create(
        cls,
        *,
        capacity: int = 4_096,
        route_capacity: int = 128,
        max_probe: int = 16,
        device: str | torch.device = "cpu",
    ) -> TensorResidentPathCache:
        torch_device = validate_resident_path_device(device)
        if capacity <= 0:
            raise ValueError("cache capacity must be positive")
        if route_capacity <= 0 or route_capacity > CELL_COUNT:
            raise ValueError("invalid cached route capacity")
        if max_probe <= 0 or max_probe > capacity:
            raise ValueError("max_probe must fit within cache capacity")
        return cls(
            valid=torch.zeros(capacity, dtype=torch.bool, device=torch_device),
            keys=torch.full((capacity, 4), -1, dtype=torch.int64, device=torch_device),
            route_cells=torch.full(
                (capacity, route_capacity, 2),
                -1,
                dtype=torch.int64,
                device=torch_device,
            ),
            route_count=torch.zeros(capacity, dtype=torch.int64, device=torch_device),
            max_probe=int(max_probe),
        )

    def _hash(self, keys: torch.Tensor) -> torch.Tensor:
        mixed = (
            keys[:, 0] * 1_000_003
            + keys[:, 1] * 97_409
            + keys[:, 2] * 193
            + keys[:, 3] * 389
        )
        return torch.remainder(mixed, self.capacity)

    def lookup(self, keys: torch.Tensor) -> TensorResidentPathCacheLookup:
        if keys.ndim != 2 or keys.shape[1] != 4:
            raise ValueError("route cache keys must have shape [query, 4]")
        if keys.device != self.device:
            raise ValueError("route cache query device differs")
        query_count = keys.shape[0]
        hit = torch.zeros(query_count, dtype=torch.bool, device=self.device)
        selected = torch.zeros(query_count, dtype=torch.int64, device=self.device)
        base = self._hash(keys)
        for probe in range(self.max_probe):
            slot = torch.remainder(base + probe, self.capacity)
            match = self.valid[slot] & torch.all(self.keys[slot] == keys, dim=1)
            choose = ~hit & match
            selected = torch.where(choose, slot, selected)
            hit |= match
        cells = self.route_cells[selected]
        count = self.route_count[selected]
        cells = torch.where(hit[:, None, None], cells, -1)
        count = torch.where(hit, count, 0)
        return TensorResidentPathCacheLookup(hit, cells, count)

    def insert_(
        self,
        keys: torch.Tensor,
        route_cells: torch.Tensor,
        route_count: torch.Tensor,
        eligible: torch.Tensor,
    ) -> torch.Tensor:
        """Insert misses with tensor-only stable lowest-query conflict wins."""

        if keys.ndim != 2 or keys.shape[1] != 4:
            raise ValueError("route cache keys must have shape [query, 4]")
        if route_cells.shape != (keys.shape[0], self.route_capacity, 2):
            raise ValueError("cached route shape differs from cache capacity")
        pending = eligible.to(torch.bool).clone()
        # A batch can contain many entities requesting the same route. Keep
        # only the lowest query as the insertion candidate so one miss cannot
        # occupy several probe slots with duplicate keys.
        query = torch.arange(keys.shape[0], device=self.device)
        same_key = torch.all(keys[:, None, :] == keys[None, :, :], dim=2)
        prior = query[None, :] < query[:, None]
        duplicate = (same_key & prior & pending[None, :]).any(dim=1)
        pending &= ~duplicate
        inserted = torch.zeros_like(pending)
        base = self._hash(keys)
        sentinel = keys.shape[0]
        for probe in range(self.max_probe):
            slot = torch.remainder(base + probe, self.capacity)
            occupied = self.valid[slot]
            match = occupied & torch.all(self.keys[slot] == keys, dim=1)
            pending &= ~match
            candidate = pending & ~occupied
            lowest = torch.full(
                (self.capacity,),
                sentinel,
                dtype=torch.int64,
                device=self.device,
            )
            lowest.scatter_reduce_(
                0,
                slot,
                torch.where(candidate, query, sentinel),
                reduce="amin",
                include_self=True,
            )
            winner = candidate & (lowest[slot] == query)
            winner_slots = slot[winner]
            self.valid[winner_slots] = True
            self.keys[winner_slots] = keys[winner]
            self.route_cells[winner_slots] = route_cells[winner]
            self.route_count[winner_slots] = route_count[winner]
            inserted |= winner
            pending &= ~winner
        return inserted


@dataclass(frozen=True)
class TensorResidentRoutePlan:
    supported: torch.Tensor
    stable_order: torch.Tensor
    goal_cell: torch.Tensor
    head_units: torch.Tensor
    route_cells: torch.Tensor
    route_count: torch.Tensor
    route_moves_backwards: torch.Tensor
    river_landing_cell: torch.Tensor
    river_landing_valid: torch.Tensor


def plan_standard_routes(
    *,
    entity_id: torch.Tensor,
    active: torch.Tensor,
    mover_position_units: torch.Tensor,
    target_position_units: torch.Tensor,
    required_range_units: torch.Tensor,
    lane_id: torch.Tensor,
    jump_height: torch.Tensor,
    direct_single_node: torch.Tensor,
    route_capacity: int = 128,
    cache: TensorResidentPathCache | None = None,
) -> TensorResidentRoutePlan:
    """Plan exact retained routes for a stable batched entity table.

    ``direct_single_node`` is the serialized FlyingHeight/hover path profile;
    it retains only the native goal cell and does not invoke the arena heap.
    """

    device = validate_resident_path_device(entity_id.device)
    if entity_id.shape != active.shape:
        raise ValueError("entity_id and active shapes differ")
    expected_positions = (*entity_id.shape, 2)
    if mover_position_units.shape != expected_positions:
        raise ValueError("mover positions do not match entity table")
    if target_position_units.shape != expected_positions:
        raise ValueError("target positions do not match entity table")
    for value in (
        required_range_units,
        lane_id,
        jump_height,
        direct_single_node,
    ):
        if value.shape != entity_id.shape:
            raise ValueError("route trait shape does not match entity table")
    if route_capacity <= 0 or route_capacity > CELL_COUNT:
        raise ValueError("route_capacity must be within the standard cell count")
    if cache is not None and (
        cache.device != device or cache.route_capacity != route_capacity
    ):
        raise ValueError("route cache device/capacity differs from planner")

    stable = stable_entity_order_mask(active, entity_id)
    geometry = (
        (mover_position_units[..., 0] >= 0)
        & (mover_position_units[..., 0] < ARENA_WIDTH_UNITS)
        & (mover_position_units[..., 1] >= 0)
        & (mover_position_units[..., 1] < ARENA_HEIGHT_UNITS)
        & (target_position_units[..., 0] >= 0)
        & (target_position_units[..., 0] < ARENA_WIDTH_UNITS)
        & (target_position_units[..., 1] >= 0)
        & (target_position_units[..., 1] < ARENA_HEIGHT_UNITS)
        & (required_range_units >= 0)
        & (lane_id >= 0)
        & (lane_id <= 2)
    )
    goal_cell, goal_valid = tensor_route_goal_cells(
        mover_position_units,
        target_position_units,
        required_range_units,
    )
    # Physical pool slots can become ID-unsorted after lowest-slot reuse.
    # Queries are independent, so order remains diagnostic rather than a gate.
    initial_support = active & geometry & goal_valid
    prefix = entity_id.shape
    flattened = math_prod(prefix)
    start = _cell_for_position(mover_position_units).reshape(flattened, 2)
    goal = goal_cell.reshape(flattened, 2)
    lane = lane_id.reshape(flattened).to(torch.int64)
    jump = jump_height.reshape(flattened).to(torch.bool)
    direct = direct_single_node.reshape(flattened).to(torch.bool)
    supported_flat = initial_support.reshape(flattened)
    ground = supported_flat & ~direct
    start_index = start[:, 1] * STANDARD_PATH_WIDTH + start[:, 0]
    goal_index = goal[:, 1] * STANDARD_PATH_WIDTH + goal[:, 0]
    cache_keys = torch.stack(
        (start_index, goal_index, lane, jump.to(torch.int64)), dim=1
    )
    if cache is None:
        cached = TensorResidentPathCacheLookup(
            hit=torch.zeros(flattened, dtype=torch.bool, device=device),
            route_cells=torch.full(
                (flattened, route_capacity, 2),
                -1,
                dtype=torch.int64,
                device=device,
            ),
            route_count=torch.zeros(flattened, dtype=torch.int64, device=device),
        )
    else:
        cached = cache.lookup(cache_keys)
    cache_hit = ground & cached.hit
    ground_miss = ground & ~cache_hit
    # One scalar miss check avoids launching the much larger exact heap on a
    # complete cache hit. A compiled conditional/custom op can replace this
    # synchronization later, but unconditional CUDA heap work is substantially
    # worse and has no measured production justification.
    if bool(ground_miss.any().item()):
        parents, heap_found = _native_heap_routes(start, goal, lane, jump, ground_miss)
    else:
        parents = torch.full(
            (flattened, CELL_COUNT), -1, dtype=torch.int64, device=device
        )
        heap_found = torch.zeros(flattened, dtype=torch.bool, device=device)
    found = heap_found | cache_hit | (supported_flat & direct)

    reverse = torch.full((flattened, CELL_COUNT), -1, dtype=torch.int64, device=device)
    current = goal_index.clone()
    tracing = ground_miss & heap_found
    length = torch.zeros(flattened, dtype=torch.int64, device=device)
    rows = torch.arange(flattened, device=device)
    for trace_index in range(CELL_COUNT):
        valid = tracing & (current >= 0)
        reverse[:, trace_index] = torch.where(valid, current, reverse[:, trace_index])
        length += valid.to(torch.int64)
        done = valid & (current == start_index)
        tracing &= ~done
        current = parents[rows, torch.clamp(current, min=0)]
    path_valid = direct | cache_hit | ((length > 0) & ~tracing)
    retained_count = torch.where(
        cache_hit,
        cached.route_count,
        torch.where(direct, 1, torch.clamp(length - 1, min=0)),
    )
    capacity_ok = retained_count <= route_capacity
    supported_flat &= found & path_valid & capacity_ok
    retained_count = torch.where(supported_flat, retained_count, 0)

    output_index = torch.arange(route_capacity, device=device)[None, :]
    output_reverse_index = torch.clamp(length[:, None] - 2 - output_index, min=0)
    ground_indices = reverse.gather(1, output_reverse_index)
    direct_indices = goal_index[:, None].expand(-1, route_capacity)
    route_index = torch.where(direct[:, None], direct_indices, ground_indices)
    slot_valid = output_index < retained_count[:, None]
    route_index = torch.where(slot_valid, route_index, -1)
    route_cells = torch.stack(
        (
            torch.where(slot_valid, route_index % STANDARD_PATH_WIDTH, -1),
            torch.where(
                slot_valid,
                torch.div(route_index, STANDARD_PATH_WIDTH, rounding_mode="floor"),
                -1,
            ),
        ),
        dim=-1,
    )
    route_cells = torch.where(cache_hit[:, None, None], cached.route_cells, route_cells)
    slot_valid = output_index < retained_count[:, None]
    route_index = route_cells[..., 1] * STANDARD_PATH_WIDTH + route_cells[..., 0]
    route_index = torch.where(slot_valid, route_index, -1)
    first_cell = torch.where((retained_count > 0)[:, None], route_cells[:, 0], goal)
    head = first_cell * HALF_TILE_LOGIC_UNITS + CELL_CENTER_OFFSET

    origin_delta = mover_position_units.reshape(
        flattened, 2
    ) - target_position_units.reshape(flattened, 2)
    origin_distance = integer_sqrt_tensor(
        torch.sum(origin_delta * origin_delta, dim=-1)
    )
    route_center = route_cells * HALF_TILE_LOGIC_UNITS + CELL_CENTER_OFFSET
    route_delta = route_center - target_position_units.reshape(flattened, 1, 2)
    route_distance = integer_sqrt_tensor(torch.sum(route_delta * route_delta, dim=-1))
    backwards = torch.any(
        slot_valid & (route_distance > origin_distance[:, None]), dim=1
    )

    _, _, _, blocked_map = _static_map(device)
    safe_route_index = torch.clamp(route_index, min=0)
    blocked = slot_valid & blocked_map[safe_route_index]
    lane_index = torch.arange(route_capacity, device=device)[None, :]
    blocked_sentinel = torch.full_like(lane_index, route_capacity)
    first_blocked = torch.min(
        torch.where(blocked, lane_index, blocked_sentinel), dim=1
    ).values
    after_blocked_land = slot_valid & ~blocked & (lane_index > first_blocked[:, None])
    first_land = torch.min(
        torch.where(after_blocked_land, lane_index, blocked_sentinel), dim=1
    ).values
    landing_valid = supported_flat & (first_land < route_capacity)
    landing_index = route_index.gather(
        1, torch.clamp(first_land, max=route_capacity - 1)[:, None]
    ).squeeze(1)
    landing = torch.stack(
        (landing_index % STANDARD_PATH_WIDTH, landing_index // STANDARD_PATH_WIDTH),
        dim=-1,
    )
    landing = torch.where(landing_valid[:, None], landing, -1)

    if cache is not None:
        cache.insert_(
            cache_keys,
            route_cells,
            retained_count,
            supported_flat & ground_miss,
        )

    return TensorResidentRoutePlan(
        supported=supported_flat.reshape(prefix),
        stable_order=stable,
        goal_cell=goal.reshape(*prefix, 2),
        head_units=head.reshape(*prefix, 2),
        route_cells=route_cells.reshape(*prefix, route_capacity, 2),
        route_count=retained_count.reshape(prefix),
        route_moves_backwards=backwards.reshape(prefix),
        river_landing_cell=landing.reshape(*prefix, 2),
        river_landing_valid=landing_valid.reshape(prefix),
    )


def math_prod(shape: tuple[int, ...]) -> int:
    result = 1
    for value in shape:
        result *= int(value)
    return result
