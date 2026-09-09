"""Standalone damage-only grouped projectile pool; no runtime integration.

A cast reserves every wave/member atomically. Destinations are supplied after
admission by the caller's geometry/RNG owners. Eligibility is supplied per cast
from the scalar-compatible area-effect guard, including source-specific immunity.
This primitive does not implement status, displacement, payload, or death hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .movement import integer_sqrt_tensor, trunc_div_tensor
from .simple_modifiers import FastModifierState, intercept_fast_shield_hits_
from .simple_rolling_spells import _record_fast_rolling_hits_
from .simple_state import FAST_KIND_BUILDING, FastGymState


@dataclass
class FastGroupedProjectileState:
    device: torch.device
    active: torch.Tensor  # [B,C]
    cast_id: torch.Tensor
    next_cast_id: torch.Tensor  # [B]
    owner: torch.Tensor
    source_card_id: torch.Tensor
    damage: torch.Tensor
    crown_damage: torch.Tensor
    radius_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    member_active: torch.Tensor  # [B,C,W,M]
    launch_delay_ticks: torch.Tensor
    position_units: torch.Tensor  # [B,C,W,M,2]
    destination_units: torch.Tensor
    hit_stable_ids: torch.Tensor  # [B,C,W,H]

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_casts: int = 4,
        waves: int = 3,
        members: int = 10,
        max_hit_records: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastGroupedProjectileState:
        if min(batch_size, max_casts, waves, members, max_hit_records) < 1:
            raise ValueError("pool dimensions must be positive")
        device = torch.empty(0, device=device).device
        cast = (batch_size, max_casts)
        member = (*cast, waves, members)

        def zeros(shape, dtype=torch.int64):
            return torch.zeros(shape, dtype=dtype, device=device)

        return cls(
            device,
            zeros(cast, torch.bool),
            zeros(cast),
            torch.ones(batch_size, dtype=torch.int64, device=device),
            zeros(cast),
            zeros(cast),
            zeros(cast, torch.float32),
            zeros(cast, torch.float32),
            zeros(cast),
            zeros(cast),
            zeros(cast, torch.bool),
            zeros(cast, torch.bool),
            zeros(member, torch.bool),
            zeros(member),
            zeros((*member, 2)),
            zeros((*member, 2)),
            zeros((*cast, waves, max_hit_records)),
        )

    def reset_rows_(self, mask: torch.Tensor) -> None:
        if (
            mask.shape != self.next_cast_id.shape
            or mask.dtype != torch.bool
            or mask.device != self.device
        ):
            raise ValueError("reset mask must be bool [batch] on pool device")
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                value[mask] = 1 if descriptor.name == "next_cast_id" else 0


@dataclass(frozen=True)
class FastGroupedCastCommands:
    ready: torch.Tensor  # [B,K]
    owner: torch.Tensor
    source_card_id: torch.Tensor
    damage: torch.Tensor
    crown_damage: torch.Tensor
    radius_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    origin_units: torch.Tensor  # [B,K,2]
    destination_units: torch.Tensor  # [B,K,W,M,2]
    launch_delay_ticks: torch.Tensor  # [B,K,W,M]


@dataclass(frozen=True)
class FastGroupedAdmission:
    accepted: torch.Tensor
    capacity_rejected: torch.Tensor
    cast_slot: torch.Tensor


def admit_fast_grouped_casts(
    pool: FastGroupedProjectileState, ready: torch.Tensor
) -> FastGroupedAdmission:
    """Pure capacity preflight; call before drawing accepted cast angles."""
    if (
        ready.ndim != 2
        or ready.shape[0] != pool.active.shape[0]
        or ready.dtype != torch.bool
        or ready.device != pool.device
    ):
        raise ValueError("ready must be bool [batch, commands] on pool device")
    rank = ready.long().cumsum(1) - 1
    free = ~pool.active
    free_rank = free.long().cumsum(1) - 1
    accepted = ready & (rank < free.sum(1)[:, None])
    claims = (
        accepted[:, :, None]
        & free[:, None, :]
        & (rank[:, :, None] == free_rank[:, None, :])
    )
    slot = torch.where(accepted, claims.long().argmax(2), -1)
    return FastGroupedAdmission(accepted, ready & ~accepted, slot)


def allocate_fast_grouped_casts_(
    pool: FastGroupedProjectileState, commands: FastGroupedCastCommands
) -> FastGroupedAdmission:
    """Allocate complete casts, rejecting malformed input before mutation."""
    b, k = commands.ready.shape
    w, m = pool.member_active.shape[2:]
    for descriptor in fields(commands):
        value = getattr(commands, descriptor.name)
        shape = (b, k)
        if descriptor.name == "origin_units":
            shape += (2,)
        elif descriptor.name == "destination_units":
            shape += (w, m, 2)
        elif descriptor.name == "launch_delay_ticks":
            shape += (w, m)
        dtype = (
            torch.bool
            if descriptor.name in ("ready", "hits_air", "hits_ground")
            else torch.float32
            if descriptor.name in ("damage", "crown_damage")
            else torch.int64
        )
        if value.shape != shape or value.dtype != dtype or value.device != pool.device:
            raise ValueError(
                f"{descriptor.name} must be {dtype} {shape} on pool device"
            )
    invalid = (
        (commands.owner < 0)
        | (commands.owner > 1)
        | (commands.source_card_id <= 0)
        | ~torch.isfinite(commands.damage)
        | (commands.damage <= 0)
        | ~torch.isfinite(commands.crown_damage)
        | (commands.crown_damage < 0)
        | (commands.radius_units <= 0)
        | (commands.speed_units_per_tick <= 0)
        | (commands.launch_delay_ticks < 0).flatten(2).any(2)
    )
    # Bound squared geometry and signed products safely in int64.
    invalid |= (
        (
            (commands.destination_units < -1_000_000)
            | (commands.destination_units > 1_000_000)
        )
        .flatten(2)
        .any(2)
    )
    invalid |= (
        (commands.origin_units < -1_000_000) | (commands.origin_units > 1_000_000)
    ).any(2)
    invalid |= (commands.speed_units_per_tick > 1_000_000) | (
        commands.radius_units > 1_000_000
    )
    if bool((commands.ready & invalid).any().item()):
        raise ValueError("invalid ready grouped cast")
    admission = admit_fast_grouped_casts(pool, commands.ready)
    # Commands are processed in admission order; every member shares one slot.
    rows = torch.arange(b, device=pool.device)
    for command in range(k):
        accepted = admission.accepted[:, command]
        slot = admission.cast_slot[:, command].clamp_min(0)

        def write(destination, source, slot=slot, accepted=accepted):
            old = destination[rows, slot]
            mask = accepted.view(b, *((1,) * (old.ndim - 1)))
            destination[rows, slot] = torch.where(mask, source, old)

        for name in (
            "owner",
            "source_card_id",
            "damage",
            "crown_damage",
            "radius_units",
            "speed_units_per_tick",
            "hits_air",
            "hits_ground",
            "destination_units",
            "launch_delay_ticks",
        ):
            write(getattr(pool, name), getattr(commands, name)[:, command])
        write(
            pool.position_units,
            commands.origin_units[:, command, None, None, :].expand(b, w, m, 2),
        )
        write(
            pool.member_active,
            torch.ones((b, w, m), dtype=torch.bool, device=pool.device),
        )
        write(pool.hit_stable_ids, torch.zeros_like(pool.hit_stable_ids[:, 0]))
        write(pool.cast_id, pool.next_cast_id)
        write(pool.active, torch.ones(b, dtype=torch.bool, device=pool.device))
        pool.next_cast_id.add_(accepted.long())
    return admission


@dataclass(frozen=True)
class FastGroupedStepResult:
    impact: torch.Tensor
    hit: torch.Tensor  # [B,C,W,M,E], before shield
    hit_capacity_rejected: torch.Tensor
    damage_by_entity: torch.Tensor


def step_fast_grouped_projectiles_(
    gym: FastGymState,
    pool: FastGroupedProjectileState,
    *,
    entity_collision_radius_units: torch.Tensor,
    entity_is_air: torch.Tensor,
    entity_is_crown_tower: torch.Tensor,
    entity_area_receivable: torch.Tensor,  # [B,C,E], source-specific scalar guard
    modifiers: FastModifierState | None = None,
) -> FastGroupedStepResult:
    """Advance one 50ms frame and resolve damage-only committed impacts.

    The caller supplies live hitboxes and source-specific area eligibility.
    Stable IDs must be unique positive identities; dead/reused slots cannot
    inherit a previous victim's group membership. Death callbacks remain the
    owning runtime's responsibility after the returned HP change.
    """
    b, c, w, m = pool.member_active.shape
    e = gym.max_entities
    if pool.hit_stable_ids.shape[-1] != e:
        raise ValueError("hit ledger records must match gym entity capacity")
    if gym.hp.device != pool.device or gym.batch_size != b:
        raise ValueError("gym and pool must share batch/device")
    for name, value, shape, dtype in (
        ("radii", entity_collision_radius_units, (b, e), torch.int64),
        ("air", entity_is_air, (b, e), torch.bool),
        ("crown", entity_is_crown_tower, (b, e), torch.bool),
        ("eligibility", entity_area_receivable, (b, c, e), torch.bool),
    ):
        if value.shape != shape or value.dtype != dtype or value.device != pool.device:
            raise ValueError(f"invalid {name} shape/dtype/device")
    alive = pool.member_active & ~gym.game_over[:, None, None, None]
    waiting = alive & (pool.launch_delay_ticks > 0)
    pool.launch_delay_ticks.sub_(waiting.long())
    moving = alive & ~waiting
    delta = pool.destination_units - pool.position_units
    distance = integer_sqrt_tensor(delta.square().sum(-1))
    speed = pool.speed_units_per_tick[:, :, None, None]
    impact = moving & (distance <= speed)
    displacement = trunc_div_tensor(
        delta * speed[..., None], distance.clamp_min(1)[..., None]
    )
    # Scalar resolves at target but retains its last flight coordinate.
    pool.position_units.add_(
        torch.where((moving & ~impact)[..., None], displacement, 0)
    )
    dx = (
        gym.x_units.long()[:, None, None, None, :]
        - pool.destination_units[..., 0, None]
    )
    dy = (
        gym.y_units.long()[:, None, None, None, :]
        - pool.destination_units[..., 1, None]
    )
    radius = entity_collision_radius_units[:, None, None, None, :].clamp_min(0)
    splash = pool.radius_units[:, :, None, None, None]
    circular = dx.square() + dy.square() < (radius + splash).square()
    square_dx = (dx.abs() - radius).clamp_min(0)
    square_dy = (dy.abs() - radius).clamp_min(0)
    square = square_dx.square() + square_dy.square() < splash.square()
    overlaps = torch.where(
        (gym.kind == FAST_KIND_BUILDING)[:, None, None, None, :], square, circular
    )
    target_plane = torch.where(
        entity_is_air[:, None, :],
        pool.hits_air[:, :, None],
        pool.hits_ground[:, :, None],
    )
    eligible = (
        gym.active[:, None, :]
        & (gym.hp[:, None, :] > 0)
        & (gym.stable_id[:, None, :] > 0)
        & (gym.owner[:, None, :].long() != pool.owner[:, :, None])
        & ((gym.kind == 0) | (gym.kind == 1))[:, None, :]
        & target_plane
        & entity_area_receivable
    )
    candidate = impact[..., None] & overlaps & eligible[:, :, None, None, :]
    hits, rejected = [], []
    ledger = pool.hit_stable_ids.reshape(b, c * w, -1)
    for member in range(m):
        prior = (gym.stable_id[:, None, :, None] == ledger[:, :, None, :]).any(-1)
        new = candidate[:, :, :, member].reshape(b, c * w, e) & ~prior
        hit, overflow = _record_fast_rolling_hits_(new, gym.stable_id, ledger)
        hits.append(hit.reshape(b, c, w, e))
        rejected.append(overflow.reshape(b, c, w, e))
    hit = torch.stack(hits, dim=3)
    overflow = torch.stack(rejected, dim=3)
    damage = torch.where(
        entity_is_crown_tower[:, None, :],
        pool.crown_damage[:, :, None],
        pool.damage[:, :, None],
    )
    weighted = hit.float() * damage[:, :, None, None, :]
    if modifiers is None:
        damage_by_entity = weighted.sum((1, 2, 3))
    else:
        # Slot reuse must not reorder separate casts' committed shield hits.
        order = pool.cast_id.argsort(dim=1)
        hit = hit.gather(1, order[:, :, None, None, None].expand_as(hit))
        weighted = weighted.gather(1, order[:, :, None, None, None].expand_as(weighted))
        slots = (
            torch.arange(e, device=pool.device)
            .view(1, 1, 1, 1, e)
            .expand(b, c, w, m, e)
        )
        shield = intercept_fast_shield_hits_(
            modifiers,
            valid=hit.reshape(b, -1),
            target_slot=slots.reshape(b, -1),
            damage=weighted.reshape(b, -1),
        )
        damage_by_entity = shield.hp_damage
        # Return physical pool-slot order for telemetry.
        hit = hit.gather(1, order.argsort(1)[:, :, None, None, None].expand_as(hit))
    gym.hp.sub_(damage_by_entity).clamp_min_(0)
    pool.member_active &= ~impact
    pool.active.copy_(pool.member_active.any(dim=(2, 3)))
    return FastGroupedStepResult(impact, hit, overflow, damage_by_entity)
