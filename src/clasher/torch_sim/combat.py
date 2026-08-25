"""Batched fixed-point targeting and stationary combat tensor kernels.

The kernels in this module are deliberately independent of Python ``Entity``
objects.  One tensor row is a battle and one column is a stable entity slot.
The only Python loop is over the fixed maximum entity capacity so direct hits
can retain the oracle's entity-id component order; every battle in that step is
processed together by PyTorch.

This layer covers the ordinary serialized combat component.  Callers must set
``combat_blocked`` for mechanics which currently own or suppress combat.  A
mechanic is never inferred from a card name here.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

GEOMETRY_EPSILON_TILES = 1e-8
TARGET_TIE_EPSILON_TILES = 1e-6
KEEP_TARGET_EXTENSION_UNITS = 25
STARTED_PROJECTILE_KEEP_EXTENSION_UNITS = 500
CROWN_SIGHT_EXTENSION_UNITS = 2_000
PENDING_DAMAGE_MAX_DURATION_MS = 600


@dataclass
class StationaryCombatState:
    """Dense mutable state consumed by :func:`step_stationary_combat_`.

    Geometry is expressed in native 1/1000-tile integer units.  Clocks and HP
    remain float64 because those are externally visible Python-oracle scalar
    kinds. ``building_target`` is the serialized target category and is true
    for physical buildings as well as moving objectives with that trait.
    """

    present: torch.Tensor
    entity_id: torch.Tensor
    encounter_order: torch.Tensor
    kind: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    collision_radius_units: torch.Tensor
    target_distance_discount_sq_units: torch.Tensor
    hp: torch.Tensor
    max_hp: torch.Tensor
    has_shield: torch.Tensor
    shield_hp: torch.Tensor
    shield_break_count: torch.Tensor
    shield_integer_kind: torch.Tensor
    damage: torch.Tensor
    alive: torch.Tensor
    targetable: torch.Tensor
    effect_receivable: torch.Tensor
    area_effect_receivable: torch.Tensor
    airborne: torch.Tensor
    building_target: torch.Tensor
    crown_slot: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    sight_clip_units: torch.Tensor
    sight_clip_side_units: torch.Tensor
    can_attack_air: torch.Tensor
    can_attack_ground: torch.Tensor
    buildings_only: torch.Tensor
    uses_projectile: torch.Tensor
    reserved_lethal: torch.Tensor
    target_slot: torch.Tensor
    deploy_remaining: torch.Tensor
    stunned: torch.Tensor
    forced_movement: torch.Tensor
    combat_blocked: torch.Tensor
    attack_start_special: torch.Tensor
    reveal_on_attack: torch.Tensor
    ordinary_combat_supported: torch.Tensor
    combat_enabled: torch.Tensor
    tower_active: torch.Tensor
    requires_activation: torch.Tensor
    activation_delay_remaining: torch.Tensor
    activation_delay_seconds: torch.Tensor
    activation_first_hit_delay_remaining: torch.Tensor
    activation_first_hit_delay_seconds: torch.Tensor
    attack_cooldown: torch.Tensor
    hit_speed_ms: torch.Tensor
    first_hit_ms: torch.Tensor
    attack_rate_multiplier: torch.Tensor
    attack_preload_blocked: torch.Tensor
    attack_windup_active: torch.Tensor
    started_projectile_hit_cycle: torch.Tensor
    area_radius_units: torch.Tensor
    self_as_aoe_center: torch.Tensor
    outgoing_damage_multiplier: torch.Tensor
    incoming_damage_multiplier: torch.Tensor
    last_attack_time: torch.Tensor
    has_attacked_once: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.present.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.present.shape[1])

    @property
    def device(self) -> torch.device:
        return self.present.device

    @classmethod
    def empty(
        cls,
        batch_size: int,
        max_entities: int,
        *,
        device: str | torch.device = "cpu",
    ) -> StationaryCombatState:
        """Allocate a neutral state with all gameplay defaults initialized."""

        shape = (batch_size, max_entities)
        torch_device = torch.device(device)
        if torch_device.type not in {"cpu", "cuda"}:
            raise ValueError(
                "exact stationary combat requires CPU/CUDA float64; "
                f"route device {torch_device.type!r} through fail-closed fallback"
            )

        def full(value: float | bool, dtype: torch.dtype) -> torch.Tensor:
            return torch.full(shape, value, dtype=dtype, device=torch_device)

        return cls(
            present=full(False, torch.bool),
            entity_id=full(0, torch.int64),
            encounter_order=torch.arange(
                max_entities, dtype=torch.int64, device=torch_device
            )
            .expand(batch_size, -1)
            .clone(),
            kind=full(0, torch.int8),
            owner=full(0, torch.int8),
            x_units=full(0, torch.int64),
            y_units=full(0, torch.int64),
            collision_radius_units=full(500, torch.int64),
            target_distance_discount_sq_units=full(0, torch.int64),
            hp=full(0.0, torch.float64),
            max_hp=full(0.0, torch.float64),
            has_shield=full(False, torch.bool),
            shield_hp=full(0.0, torch.float64),
            shield_break_count=full(0, torch.int64),
            shield_integer_kind=full(False, torch.bool),
            damage=full(0.0, torch.float64),
            alive=full(False, torch.bool),
            targetable=full(True, torch.bool),
            effect_receivable=full(True, torch.bool),
            area_effect_receivable=full(True, torch.bool),
            airborne=full(False, torch.bool),
            building_target=full(False, torch.bool),
            crown_slot=full(-1, torch.int8),
            range_units=full(0, torch.int64),
            sight_range_units=full(0, torch.int64),
            sight_clip_units=full(0, torch.int64),
            sight_clip_side_units=full(0, torch.int64),
            can_attack_air=full(False, torch.bool),
            can_attack_ground=full(True, torch.bool),
            buildings_only=full(False, torch.bool),
            uses_projectile=full(False, torch.bool),
            reserved_lethal=full(False, torch.bool),
            target_slot=full(-1, torch.int64),
            deploy_remaining=full(0.0, torch.float64),
            stunned=full(False, torch.bool),
            forced_movement=full(False, torch.bool),
            combat_blocked=full(False, torch.bool),
            attack_start_special=full(False, torch.bool),
            reveal_on_attack=full(False, torch.bool),
            ordinary_combat_supported=full(True, torch.bool),
            combat_enabled=full(True, torch.bool),
            tower_active=full(True, torch.bool),
            requires_activation=full(False, torch.bool),
            activation_delay_remaining=full(0.0, torch.float64),
            activation_delay_seconds=full(0.0, torch.float64),
            activation_first_hit_delay_remaining=full(0.0, torch.float64),
            activation_first_hit_delay_seconds=full(0.0, torch.float64),
            attack_cooldown=full(0.0, torch.float64),
            hit_speed_ms=full(1_000, torch.int64),
            first_hit_ms=full(0, torch.int64),
            attack_rate_multiplier=full(1.0, torch.float64),
            attack_preload_blocked=full(False, torch.bool),
            attack_windup_active=full(False, torch.bool),
            started_projectile_hit_cycle=full(False, torch.bool),
            area_radius_units=full(0, torch.int64),
            self_as_aoe_center=full(False, torch.bool),
            outgoing_damage_multiplier=full(1.0, torch.float64),
            incoming_damage_multiplier=full(1.0, torch.float64),
            last_attack_time=full(0.0, torch.float64),
            has_attacked_once=full(False, torch.bool),
        )

    def validate(self) -> None:
        expected = self.present.shape
        if len(expected) != 2:
            raise ValueError("combat tensors must have shape [batch, entity]")
        for descriptor in fields(self):
            tensor = getattr(self, descriptor.name)
            if tensor.shape != expected:
                raise ValueError(
                    f"{descriptor.name} has shape {tuple(tensor.shape)}, "
                    f"expected {tuple(expected)}"
                )
            if tensor.device != self.device:
                raise ValueError(f"{descriptor.name} is on a different device")


@dataclass(frozen=True)
class DirectHitLedger:
    """Exact direct-hit work keyed by attacker slot and recipient ordinal.

    ``target_slot == -1`` marks an unused lane.  For each attacker the primary
    recipient precedes secondary area recipients, which remain in stable
    entity-ID order. ``applied`` is actual HP loss rather than nominal damage.
    """

    target_slot: torch.Tensor
    applied: torch.Tensor
    lethal: torch.Tensor
    shield_absorbed: torch.Tensor
    shield_broken: torch.Tensor


@dataclass(frozen=True)
class CombatStepResult:
    """Per-entity mutations and emitted payloads from one combat frame."""

    attacked: torch.Tensor
    projectile_launched: torch.Tensor
    damage_received: torch.Tensor
    target_before: torch.Tensor
    target_after: torch.Tensor
    special_started: torch.Tensor | None = None
    attack_clock_in_range: torch.Tensor | None = None
    direct_hits: DirectHitLedger | None = None


class UnsupportedStationaryCombatError(RuntimeError):
    """Raised before mutation when a batch needs an unimplemented operation."""

    def __init__(self, batch_indices: list[int]):
        self.batch_indices = batch_indices
        super().__init__(
            "stationary tensor combat is unsupported for battle rows "
            f"{batch_indices}; route them through the Python fail-closed path"
        )


def stationary_combat_support_mask(
    state: StationaryCombatState,
) -> torch.Tensor:
    """Return rows whose ordinary combat semantics are represented exactly.

    The adapter which constructs this state owns mechanic classification. It
    sets ``ordinary_combat_supported`` false for an operation not yet covered
    by these generalized fields (for example attack-start movement). CPU and
    CUDA retain exact float64 state; Apple MPS does not implement float64 and
    therefore remains fail-closed for this integrated phase.
    """

    state.validate()
    per_entity = (~state.present) | state.ordinary_combat_supported
    supported = per_entity.all(dim=1)
    float_fields = (
        state.hp,
        state.max_hp,
        state.shield_hp,
        state.damage,
        state.deploy_remaining,
        state.activation_delay_remaining,
        state.activation_delay_seconds,
        state.activation_first_hit_delay_remaining,
        state.activation_first_hit_delay_seconds,
        state.attack_cooldown,
        state.attack_rate_multiplier,
        state.outgoing_damage_multiplier,
        state.incoming_damage_multiplier,
        state.last_attack_time,
    )
    exact_layout = state.device.type in {"cpu", "cuda"} and all(
        tensor.dtype == torch.float64 for tensor in float_fields
    )
    if not exact_layout:
        supported &= False
    return supported


def _gather(values: torch.Tensor, slots: torch.Tensor) -> torch.Tensor:
    return values.gather(1, slots.clamp(min=0).unsqueeze(1)).squeeze(1)


def _scatter_masked_(
    destination: torch.Tensor,
    slots: torch.Tensor,
    values: torch.Tensor,
    mask: torch.Tensor,
) -> None:
    rows = torch.arange(destination.shape[0], device=destination.device)
    destination[rows[mask], slots[mask]] = values[mask]


def _distance_tiles(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    attacker_x = _gather(state.x_units, attacker_slots)
    attacker_y = _gather(state.y_units, attacker_slots)
    dx = state.x_units - attacker_x.unsqueeze(1)
    dy = state.y_units - attacker_y.unsqueeze(1)
    raw_sq = dx * dx + dy * dy
    adjusted_sq = torch.clamp(
        raw_sq - state.target_distance_discount_sq_units,
        min=0,
    )
    return torch.sqrt(adjusted_sq.to(torch.float64)) / 1_000.0, dx, dy


def _target_base_valid(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
    *,
    current: bool,
) -> torch.Tensor:
    attacker_owner = _gather(state.owner, attacker_slots)
    attack_air = _gather(state.can_attack_air, attacker_slots)
    attack_ground = _gather(state.can_attack_ground, attacker_slots)
    projectile = _gather(state.uses_projectile, attacker_slots)
    plane = torch.where(
        state.airborne,
        attack_air.unsqueeze(1),
        attack_ground.unsqueeze(1),
    )
    valid = (
        state.present
        & state.alive
        & state.targetable
        & (state.owner != attacker_owner.unsqueeze(1))
        & ((state.kind == 0) | (state.kind == 1))
        & plane
    )
    # Current globals reject lethally reserved targets for projectile weapons,
    # including an already-retained target.
    if current:
        valid &= ~(projectile.unsqueeze(1) & state.reserved_lethal)
    else:
        valid &= ~(projectile.unsqueeze(1) & state.reserved_lethal)
    return valid


def _within_reach(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
    target_slots: torch.Tensor,
    *,
    keep: bool | torch.Tensor,
) -> torch.Tensor:
    target_ok = target_slots >= 0
    distance, _, _ = _distance_tiles(state, attacker_slots)
    distance_to_target = _gather(distance, target_slots)
    target_radius = _gather(state.collision_radius_units, target_slots)
    base_range = _gather(state.range_units, attacker_slots)
    keep_mask = torch.as_tensor(keep, dtype=torch.bool, device=state.device)
    keep_mask = torch.broadcast_to(keep_mask, base_range.shape)
    started = _gather(state.started_projectile_hit_cycle, attacker_slots)
    keep_extension = torch.where(
        started,
        torch.full_like(base_range, STARTED_PROJECTILE_KEEP_EXTENSION_UNITS),
        torch.full_like(base_range, KEEP_TARGET_EXTENSION_UNITS),
    )
    extension = torch.where(keep_mask, keep_extension, 0)
    reach = (base_range + target_radius + extension).to(torch.float64) / 1_000.0
    return target_ok & (distance_to_target <= reach + GEOMETRY_EPSILON_TILES)


def _lexicographic_min_mask(
    eligible: torch.Tensor,
    first: torch.Tensor,
    second: torch.Tensor,
    third: torch.Tensor,
) -> torch.Tensor:
    large = torch.iinfo(torch.int64).max
    first_min = torch.where(eligible, first, large).amin(dim=1)
    eligible &= first == first_min.unsqueeze(1)
    second_min = torch.where(eligible, second, large).amin(dim=1)
    eligible &= second == second_min.unsqueeze(1)
    third_min = torch.where(eligible, third, large).amin(dim=1)
    eligible &= third == third_min.unsqueeze(1)
    return eligible


def _nearest_candidate(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
    candidates: torch.Tensor,
    distance: torch.Tensor,
) -> torch.Tensor:
    """Choose the oracle's stable nearest candidate for every batch row."""

    infinity = torch.full_like(distance, torch.inf)
    minimum = torch.where(candidates, distance, infinity).amin(dim=1)
    exact_minimum = candidates & (distance == minimum.unsqueeze(1))

    # Scalar candidate collection visits character targets before native or
    # serialized building targets. Encounter order is retained for exact
    # ordinary ties.
    category = state.building_target.to(torch.int64)
    stable = _lexicographic_min_mask(
        exact_minimum.clone(),
        category,
        state.encounter_order,
        state.entity_id,
    )
    selected = torch.argmax(stable.to(torch.int64), dim=1)
    any_candidate = candidates.any(dim=1)

    # If the strictly closest candidate is a building, current globals rotate
    # equal-distance building iteration into the owner's arena perspective.
    selected_is_building = _gather(state.building_target, selected)
    building_ties = (
        candidates
        & state.building_target
        & (distance <= minimum.unsqueeze(1) + TARGET_TIE_EPSILON_TILES)
    )
    owner = _gather(state.owner, attacker_slots).to(torch.int64)
    direction = torch.where(owner == 0, 1, -1).unsqueeze(1)
    symmetric = _lexicographic_min_mask(
        building_ties.clone(),
        direction * (state.x_units - 9_000),
        direction * (state.y_units - 16_000),
        state.entity_id,
    )
    symmetric_selected = torch.argmax(symmetric.to(torch.int64), dim=1)
    selected = torch.where(selected_is_building, symmetric_selected, selected)
    return torch.where(any_candidate, selected, torch.full_like(selected, -1))


def select_stationary_targets(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Select targets for one attacker slot per batch without mutating state.

    Returns ``(target_slot, used_crown_fallback)``. Acquisition includes the
    serialized target category, air/ground planes, directional sight clips,
    stable character/building ties, and current Crown fallback globals.
    """

    if attacker_slots.shape != (state.batch_size,):
        raise ValueError("attacker_slots must have shape [batch]")
    distance, dx, dy = _distance_tiles(state, attacker_slots)
    valid = _target_base_valid(state, attacker_slots, current=False)
    only_buildings = _gather(state.buildings_only, attacker_slots)
    category_valid = (~only_buildings.unsqueeze(1)) | state.building_target

    sight = _gather(state.sight_range_units, attacker_slots).unsqueeze(1)
    crown_extension = torch.where(
        state.crown_slot >= 0,
        torch.full_like(state.collision_radius_units, CROWN_SIGHT_EXTENSION_UNITS),
        torch.zeros_like(state.collision_radius_units),
    )
    sight_reach = sight + state.collision_radius_units + crown_extension
    in_sight = (
        distance <= sight_reach.to(torch.float64) / 1_000.0 + GEOMETRY_EPSILON_TILES
    )

    attacker_is_crown = _gather(state.crown_slot, attacker_slots) >= 0
    clip_exempt = attacker_is_crown.unsqueeze(1) | (state.crown_slot >= 0)
    side_clip = _gather(state.sight_clip_side_units, attacker_slots).unsqueeze(1)
    backward_clip = _gather(state.sight_clip_units, attacker_slots).unsqueeze(1)
    side_limit = torch.clamp(sight_reach - side_clip, min=0)
    in_sight &= clip_exempt | (side_clip <= 0) | (dx.abs() <= side_limit)
    owner = _gather(state.owner, attacker_slots)
    forward_delta = torch.where(owner.unsqueeze(1) == 0, dy, -dy)
    backward_limit = -torch.clamp(sight_reach - backward_clip, min=0)
    in_sight &= clip_exempt | (backward_clip <= 0) | (forward_delta >= backward_limit)

    ordinary = valid & category_valid & in_sight
    selected_ordinary = _nearest_candidate(state, attacker_slots, ordinary, distance)
    has_ordinary = ordinary.any(dim=1)

    crowns = valid & (state.crown_slot >= 0)
    princess = crowns & (state.crown_slot != 2)
    has_princess = princess.any(dim=1)
    x_distance = (
        state.x_units - _gather(state.x_units, attacker_slots).unsqueeze(1)
    ).abs()
    large = torch.iinfo(torch.int64).max
    princess_min_x = torch.where(princess, x_distance, large).amin(dim=1)
    preferred_princess = princess & (x_distance == princess_min_x.unsqueeze(1))
    preferred_crowns = torch.where(
        has_princess.unsqueeze(1),
        preferred_princess,
        crowns & (state.crown_slot == 2),
    )
    selected_crown = _nearest_candidate(
        state, attacker_slots, preferred_crowns, distance
    )

    attacker_is_building = _gather(state.kind, attacker_slots) == 1
    building_fallback_allowed = (
        _gather(state.range_units, attacker_slots)
        > _gather(state.sight_range_units, attacker_slots) + CROWN_SIGHT_EXTENSION_UNITS
    )
    fallback_allowed = (~attacker_is_building) | building_fallback_allowed
    use_fallback = (~has_ordinary) & fallback_allowed & (selected_crown >= 0)
    selected = torch.where(use_fallback, selected_crown, selected_ordinary)

    # A building's selector performs a final exact attack-range check. Mobile
    # characters may retain an out-of-range Crown fallback as a path target.
    building_reach = _within_reach(state, attacker_slots, selected, keep=False)
    selected = torch.where(
        attacker_is_building & ~building_reach,
        torch.full_like(selected, -1),
        selected,
    )
    use_fallback &= selected >= 0
    return selected, use_fallback


def _current_target_status(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    current = _gather(state.target_slot, attacker_slots)
    in_bounds = (current >= 0) & (current < state.max_entities)
    valid_matrix = _target_base_valid(state, attacker_slots, current=True)
    valid = in_bounds & _gather(valid_matrix, current)
    only_buildings = _gather(state.buildings_only, attacker_slots)
    valid &= (~only_buildings) | _gather(state.building_target, current)
    keep = valid & _within_reach(state, attacker_slots, current, keep=True)
    return current, valid, keep


def _resolve_target_for_attackers(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
) -> torch.Tensor:
    current, current_valid, current_keep = _current_target_status(state, attacker_slots)
    selected, used_fallback = select_stationary_targets(state, attacker_slots)
    attacker_is_building = _gather(state.kind, attacker_slots) == 1

    # Buildings clear an invalid/out-of-keep lock before acquisition. Troops
    # preserve an out-of-keep lock unless a Crown fallback was used or a newly
    # observed target is strictly closer by the native switching epsilon.
    building_target = torch.where(current_keep, current, selected)
    distance, _, _ = _distance_tiles(state, attacker_slots)
    current_distance = _gather(distance, current)
    selected_distance = _gather(distance, selected)
    switch = (selected >= 0) & (
        used_fallback
        | (~current_valid)
        | (selected_distance < current_distance - TARGET_TIE_EPSILON_TILES)
    )
    troop_target = torch.where(
        current_keep,
        current,
        torch.where(switch, selected, torch.where(current_valid, current, selected)),
    )
    return torch.where(attacker_is_building, building_target, troop_target)


def _area_recipient_mask(
    state: StationaryCombatState,
    attacker_slots: torch.Tensor,
    primary_slots: torch.Tensor,
) -> torch.Tensor:
    """Snapshot direct-hit recipients for one attacker per batch."""

    attacker_owner = _gather(state.owner, attacker_slots)
    attack_air = _gather(state.can_attack_air, attacker_slots)
    attack_ground = _gather(state.can_attack_ground, attacker_slots)
    plane = torch.where(
        state.airborne,
        attack_air.unsqueeze(1),
        attack_ground.unsqueeze(1),
    )
    eligible = (
        state.present
        & state.alive
        & state.area_effect_receivable
        & (state.owner != attacker_owner.unsqueeze(1))
        & ((state.kind == 0) | (state.kind == 1))
        & plane
    )
    radius = _gather(state.area_radius_units, attacker_slots)
    has_area = radius > 0
    self_center = _gather(state.self_as_aoe_center, attacker_slots)
    origin_slots = torch.where(self_center, attacker_slots, primary_slots)
    origin_x = _gather(state.x_units, origin_slots)
    origin_y = _gather(state.y_units, origin_slots)
    dx = state.x_units - origin_x.unsqueeze(1)
    dy = state.y_units - origin_y.unsqueeze(1)

    combined = radius.unsqueeze(1) + state.collision_radius_units
    troop_intersects = dx * dx + dy * dy < combined * combined
    closest_dx = torch.clamp(dx.abs() - state.collision_radius_units, min=0)
    closest_dy = torch.clamp(dy.abs() - state.collision_radius_units, min=0)
    building_intersects = (
        closest_dx * closest_dx + closest_dy * closest_dy
        < radius.unsqueeze(1) * radius.unsqueeze(1)
    )
    intersects = torch.where(state.kind == 1, building_intersects, troop_intersects)
    primary_one_hot = torch.nn.functional.one_hot(
        primary_slots.clamp(min=0), num_classes=state.max_entities
    ).to(torch.bool)
    area = eligible & intersects & has_area.unsqueeze(1) & ~primary_one_hot
    primary = (
        primary_one_hot
        & (primary_slots >= 0).unsqueeze(1)
        & state.effect_receivable
        & state.alive
    )
    return primary | area


def step_stationary_combat_(
    state: StationaryCombatState,
    dt_seconds: float = 0.05,
) -> CombatStepResult:
    """Advance one stationary combat-component frame in-place.

    Direct damage is resolved in stable entity-id component order, matching
    the Python battle manager. Projectile attacks emit ``projectile_launched``
    and install their cooldown but intentionally leave HP untouched for the
    projectile object-phase kernel.
    """

    support = stationary_combat_support_mask(state)
    if not bool(torch.all(support).item()):
        unsupported = torch.nonzero(~support, as_tuple=False).flatten().tolist()
        raise UnsupportedStationaryCombatError(unsupported)
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be non-negative")
    batch, capacity = state.present.shape
    target_before = state.target_slot.clone()
    attacked = torch.zeros_like(state.present)
    projectile_launched = torch.zeros_like(state.present)
    special_started = torch.zeros_like(state.present)
    damage_received = torch.zeros_like(state.hp)
    attack_clock_in_range = torch.zeros_like(state.present)
    direct_hit_target_slot = torch.full(
        (batch, capacity, capacity),
        -1,
        dtype=torch.int64,
        device=state.device,
    )
    direct_hit_applied = torch.zeros(
        (batch, capacity, capacity),
        dtype=torch.float64,
        device=state.device,
    )
    direct_hit_lethal = torch.zeros(
        (batch, capacity, capacity),
        dtype=torch.bool,
        device=state.device,
    )
    direct_hit_shield_absorbed = torch.zeros_like(direct_hit_lethal)
    direct_hit_shield_broken = torch.zeros_like(direct_hit_lethal)

    maximum_id = torch.iinfo(torch.int64).max
    update_order = torch.argsort(
        torch.where(state.present, state.entity_id, maximum_id), dim=1
    )
    rows = torch.arange(batch, device=state.device)

    for rank in range(capacity):
        attacker_slots = update_order[:, rank]
        present = _gather(state.present, attacker_slots)
        kind = _gather(state.kind, attacker_slots)
        component_available = (
            present
            & _gather(state.alive, attacker_slots)
            & ((kind == 0) | (kind == 1))
            & _gather(state.combat_enabled, attacker_slots)
            & (_gather(state.deploy_remaining, attacker_slots) <= 0.0)
            & ~_gather(state.forced_movement, attacker_slots)
            & ~_gather(state.combat_blocked, attacker_slots)
            & ((kind != 1) | _gather(state.tower_active, attacker_slots))
        )
        component_dt = torch.full(
            (batch,), dt_seconds, dtype=torch.float64, device=state.device
        )

        # Building activation is component-owned work which runs before stun,
        # targeting, and the ordinary attack clock. An activation delay that
        # consumes the entire frame returns immediately; the distinct
        # first-hit delay may cross to zero at the boundary and still enter
        # ordinary combat with a zero-duration remainder.
        activation_delay = _gather(state.activation_delay_remaining, attacker_slots)
        delay_running = component_available & (kind == 1) & (activation_delay > 0.0)
        delay_work = torch.minimum(component_dt, activation_delay)
        next_activation_delay = torch.clamp(activation_delay - delay_work, min=0.0)
        _scatter_masked_(
            state.activation_delay_remaining,
            attacker_slots,
            next_activation_delay,
            delay_running,
        )
        component_dt = torch.where(
            delay_running, component_dt - delay_work, component_dt
        )
        activation_delay_return = delay_running & (component_dt <= 1e-9)

        first_delay = _gather(
            state.activation_first_hit_delay_remaining, attacker_slots
        )
        first_running = (
            component_available
            & (kind == 1)
            & ~activation_delay_return
            & (first_delay > 0.0)
        )
        first_work = torch.minimum(component_dt, first_delay)
        next_first_delay = torch.clamp(first_delay - first_work, min=0.0)
        _scatter_masked_(
            state.activation_first_hit_delay_remaining,
            attacker_slots,
            next_first_delay,
            first_running,
        )
        component_dt = torch.where(
            first_running, component_dt - first_work, component_dt
        )
        first_delay_return = first_running & (next_first_delay > 1e-9)
        first_delay_completed = first_running & ~first_delay_return
        _scatter_masked_(
            state.attack_cooldown,
            attacker_slots,
            torch.zeros(batch, dtype=torch.float64, device=state.device),
            first_delay_completed,
        )
        _scatter_masked_(
            state.attack_preload_blocked,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            first_delay_completed,
        )
        base_actionable = (
            component_available & ~activation_delay_return & ~first_delay_return
        )

        resolved = _resolve_target_for_attackers(state, attacker_slots)
        old_target = _gather(state.target_slot, attacker_slots)
        _scatter_masked_(
            state.target_slot,
            attacker_slots,
            resolved,
            base_actionable & (resolved != old_target),
        )
        current = torch.where(base_actionable, resolved, old_target)

        previous_last_attack = _gather(state.last_attack_time, attacker_slots)
        _scatter_masked_(
            state.last_attack_time,
            attacker_slots,
            previous_last_attack + component_dt,
            base_actionable,
        )
        can_advance = base_actionable & ~_gather(state.stunned, attacker_slots)
        keep_attack_clock = _gather(
            state.attack_windup_active, attacker_slots
        ) | _gather(state.started_projectile_hit_cycle, attacker_slots)
        target_in_range = can_advance & _within_reach(
            state,
            attacker_slots,
            current,
            keep=keep_attack_clock,
        )
        attack_clock_in_range[rows[can_advance], attacker_slots[can_advance]] = (
            target_in_range[can_advance]
        )

        cooldown = _gather(state.attack_cooldown, attacker_slots)
        rate = torch.clamp(
            _gather(state.attack_rate_multiplier, attacker_slots), min=0.05
        )
        work = component_dt * rate
        preload_floor = (
            _gather(state.first_hit_ms, attacker_slots).to(torch.float64) / 1_000.0
        )
        positive = cooldown > 0.0
        engaged_clock = torch.clamp(cooldown - work, min=0.0)
        idle_clock = torch.maximum(preload_floor, cooldown - work)
        clock_advanced = torch.where(
            target_in_range,
            engaged_clock,
            torch.where(
                ~_gather(state.attack_preload_blocked, attacker_slots),
                idle_clock,
                cooldown,
            ),
        )
        new_cooldown = torch.where(can_advance & positive, clock_advanced, cooldown)
        _scatter_masked_(
            state.attack_cooldown,
            attacker_slots,
            new_cooldown,
            can_advance & positive,
        )

        windup = _gather(state.attack_windup_active, attacker_slots)
        new_windup = torch.where(
            target_in_range,
            windup | (new_cooldown <= preload_floor + 1e-12),
            torch.zeros_like(windup),
        )
        _scatter_masked_(
            state.attack_windup_active,
            attacker_slots,
            new_windup,
            can_advance,
        )

        ready = target_in_range & (new_cooldown <= 0.0) & (current >= 0)
        projectile = _gather(state.uses_projectile, attacker_slots)
        special = ready & _gather(state.attack_start_special, attacker_slots)
        direct = ready & ~projectile & ~special
        launches = ready & projectile & ~special
        ordinary_ready = ready & ~special

        # Inactivity stealth is removed by the serialized on-attack-start
        # callback.  Publish that visibility transition inside the same
        # stable entity-ID component iteration so later attackers in this
        # frame validate/acquire against the now-visible source.
        revealed = ready & _gather(state.reveal_on_attack, attacker_slots)
        _scatter_masked_(
            state.targetable,
            attacker_slots,
            torch.ones(batch, dtype=torch.bool, device=state.device),
            revealed,
        )
        _scatter_masked_(
            state.effect_receivable,
            attacker_slots,
            torch.ones(batch, dtype=torch.bool, device=state.device),
            revealed,
        )
        _scatter_masked_(
            state.area_effect_receivable,
            attacker_slots,
            torch.ones(batch, dtype=torch.bool, device=state.device),
            revealed,
        )

        # Some serialized attack-start callbacks turn the attacker into its
        # own committed projectile. This transition occurs inside stable-ID
        # combat order, before a later component can target or affect it.
        _scatter_masked_(
            state.targetable,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            special,
        )
        _scatter_masked_(
            state.effect_receivable,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            special,
        )
        _scatter_masked_(
            state.area_effect_receivable,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            special,
        )
        _scatter_masked_(
            state.combat_blocked,
            attacker_slots,
            torch.ones(batch, dtype=torch.bool, device=state.device),
            special,
        )

        recipients = _area_recipient_mask(state, attacker_slots, current)
        recipients &= direct.unsqueeze(1)
        attack_damage = (
            _gather(state.damage, attacker_slots)
            * _gather(state.outgoing_damage_multiplier, attacker_slots)
        ).unsqueeze(1)
        nominal_damage = (
            attack_damage
            * state.incoming_damage_multiplier
            * recipients.to(torch.float64)
        ).clamp(min=0.0)
        shield_absorbed = (
            recipients
            & (nominal_damage > 0.0)
            & state.has_shield
            & (state.shield_hp > 0.0)
        )
        shield_after = torch.clamp(state.shield_hp - nominal_damage, min=0.0)
        shield_broken = shield_absorbed & (shield_after <= 0.0)
        state.shield_hp.copy_(
            torch.where(shield_absorbed, shield_after, state.shield_hp)
        )
        state.shield_break_count.add_(shield_broken.to(torch.int64))
        state.shield_integer_kind &= ~shield_absorbed
        applied = torch.where(shield_absorbed, 0.0, nominal_damage)
        hp_before = state.hp.clone()
        activates = (applied > 0.0) & state.requires_activation & ~state.tower_active
        state.tower_active |= activates
        state.activation_delay_remaining.copy_(
            torch.where(
                activates,
                torch.maximum(
                    state.activation_delay_remaining,
                    state.activation_delay_seconds,
                ),
                state.activation_delay_remaining,
            )
        )
        state.activation_first_hit_delay_remaining.copy_(
            torch.where(
                activates,
                torch.maximum(
                    state.activation_first_hit_delay_remaining,
                    state.activation_first_hit_delay_seconds,
                ),
                state.activation_first_hit_delay_remaining,
            )
        )
        state.hp.copy_(torch.clamp(state.hp - applied, min=0.0))
        state.alive &= (~recipients) | (state.hp > 0.0)
        hit_applied = hp_before - state.hp
        damage_received += hit_applied
        hit_valid = (hit_applied > 0.0) | shield_absorbed
        target_lanes = torch.arange(capacity, device=state.device)[None, :]
        primary = target_lanes == current[:, None]
        recipient_key = torch.where(
            primary,
            torch.full_like(state.entity_id, -1),
            state.entity_id,
        )
        recipient_key = torch.where(
            hit_valid,
            recipient_key,
            torch.full_like(recipient_key, maximum_id),
        )
        recipient_order = torch.argsort(recipient_key, dim=1, stable=True)
        ordered_valid = torch.gather(hit_valid, 1, recipient_order)
        ordered_applied = torch.gather(hit_applied, 1, recipient_order)
        ordered_lethal = torch.gather(
            hit_valid & (hp_before > 0.0) & (state.hp <= 0.0),
            1,
            recipient_order,
        )
        ordered_shield_absorbed = torch.gather(
            shield_absorbed,
            1,
            recipient_order,
        )
        ordered_shield_broken = torch.gather(
            shield_broken,
            1,
            recipient_order,
        )
        direct_hit_target_slot[rows, attacker_slots] = torch.where(
            ordered_valid,
            recipient_order,
            -1,
        )
        direct_hit_applied[rows, attacker_slots] = torch.where(
            ordered_valid,
            ordered_applied,
            0.0,
        )
        direct_hit_lethal[rows, attacker_slots] = ordered_lethal & ordered_valid
        direct_hit_shield_absorbed[rows, attacker_slots] = (
            ordered_shield_absorbed & ordered_valid
        )
        direct_hit_shield_broken[rows, attacker_slots] = (
            ordered_shield_broken & ordered_valid
        )

        attacked[rows[ready], attacker_slots[ready]] = True
        projectile_launched[rows[launches], attacker_slots[launches]] = True
        special_started[rows[special], attacker_slots[special]] = True
        post_cooldown = torch.where(
            _gather(state.hit_speed_ms, attacker_slots) > 0,
            _gather(state.hit_speed_ms, attacker_slots).to(torch.float64) / 1_000.0,
            torch.ones(batch, dtype=torch.float64, device=state.device),
        )
        _scatter_masked_(
            state.attack_cooldown, attacker_slots, post_cooldown, ordinary_ready
        )
        _scatter_masked_(
            state.attack_windup_active,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            ordinary_ready,
        )
        _scatter_masked_(
            state.attack_preload_blocked,
            attacker_slots,
            torch.zeros(batch, dtype=torch.bool, device=state.device),
            ordinary_ready,
        )
        _scatter_masked_(
            state.has_attacked_once,
            attacker_slots,
            torch.ones(batch, dtype=torch.bool, device=state.device),
            ordinary_ready,
        )
        _scatter_masked_(
            state.last_attack_time,
            attacker_slots,
            torch.zeros(batch, dtype=torch.float64, device=state.device),
            ordinary_ready,
        )

    return CombatStepResult(
        attacked=attacked,
        projectile_launched=projectile_launched,
        damage_received=damage_received,
        target_before=target_before,
        target_after=state.target_slot.clone(),
        special_started=special_started,
        attack_clock_in_range=attack_clock_in_range,
        direct_hits=DirectHitLedger(
            target_slot=direct_hit_target_slot,
            applied=direct_hit_applied,
            lethal=direct_hit_lethal,
            shield_absorbed=direct_hit_shield_absorbed,
            shield_broken=direct_hit_shield_broken,
        ),
    )


def projectile_lethal_reservations(
    *,
    target_hp: torch.Tensor,
    target_alive: torch.Tensor,
    target_shield_hp: torch.Tensor,
    prior_max_duration_ms: torch.Tensor,
    projectile_active: torch.Tensor,
    projectile_reserves_damage: torch.Tensor,
    projectile_target_slot: torch.Tensor,
    projectile_expected_damage: torch.Tensor,
    projectile_duration_ms: torch.Tensor,
) -> torch.Tensor:
    """Aggregate native pending projectile damage into target reservations.

    Projectile tensors have shape ``[batch, projectile]`` and target tensors
    have shape ``[batch, entity]``. The greatest registered duration gates the
    complete target aggregate; a live shield suppresses lethal reservation.
    """

    if target_hp.ndim != 2:
        raise ValueError("target tensors must have shape [batch, entity]")
    if projectile_active.ndim != 2:
        raise ValueError("projectile tensors must have shape [batch, projectile]")
    batch, entities = target_hp.shape
    if target_alive.shape != target_hp.shape:
        raise ValueError("target_alive shape mismatch")
    if target_shield_hp.shape != target_hp.shape:
        raise ValueError("target_shield_hp shape mismatch")
    if prior_max_duration_ms.shape != target_hp.shape:
        raise ValueError("prior_max_duration_ms shape mismatch")
    projectile_shape = projectile_active.shape
    for tensor in (
        projectile_reserves_damage,
        projectile_target_slot,
        projectile_expected_damage,
        projectile_duration_ms,
    ):
        if tensor.shape != projectile_shape:
            raise ValueError("projectile tensor shape mismatch")
    if projectile_shape[0] != batch:
        raise ValueError("projectile batch mismatch")

    valid_slot = (projectile_target_slot >= 0) & (projectile_target_slot < entities)
    valid = (
        projectile_active
        & projectile_reserves_damage
        & valid_slot
        & (projectile_expected_damage > 0)
    )
    slots = projectile_target_slot.clamp(min=0, max=max(0, entities - 1))
    pending = torch.zeros_like(target_hp)
    pending.scatter_add_(
        1,
        slots,
        torch.where(valid, projectile_expected_damage, 0.0),
    )
    duration = prior_max_duration_ms.clone()
    duration.scatter_reduce_(
        1,
        slots,
        torch.where(valid, projectile_duration_ms, 0),
        reduce="amax",
        include_self=True,
    )
    return (
        target_alive
        & (target_shield_hp <= 0.0)
        & (duration <= PENDING_DAMAGE_MAX_DURATION_MS)
        & (pending >= target_hp)
        & (pending > 0.0)
    )
