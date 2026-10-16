"""Tensor kernels for serialized shield and Champion ability mechanics.

The functions in this module operate only on dense tensors.  Python battle
objects remain an adapter/oracle concern: serialized factory output is compiled
once into :class:`TensorShieldChampionCatalog`, while mutable per-entity state
is supplied by the caller.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader

from .catalog import MECHANIC_OPCODE

NEVER_USED_TIME_MS = -(10**12)


def _number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Real):
        return float(value)
    raise TypeError(f"expected numeric serialized value, got {type(value).__name__}")


@dataclass(frozen=True)
class TensorShieldChampionCatalog:
    """Dense shield and Champion parameters aligned with card/mechanic slots."""

    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    mechanic_opcode: torch.Tensor
    shield_hitpoints: torch.Tensor
    ability_elixir_cost: torch.Tensor
    ability_cooldown_ms: torch.Tensor
    ability_duration_ms: torch.Tensor
    ability_effect_count: torch.Tensor
    attack_speed_multiplier: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    cast_time_ms: torch.Tensor
    trigger_delay_ms: torch.Tensor

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorShieldChampionCatalog:
        """Compile factory-emitted mechanics without card-identity switches."""

        definitions = loader.load_card_definitions()
        resolved_names = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        missing = [name for name in resolved_names if name not in definitions]
        if missing:
            raise ValueError(f"missing card definitions: {missing}")

        names = ("", *resolved_names)
        name_to_id = {name: index for index, name in enumerate(names)}
        max_mechanics = max(
            1,
            max(len(definitions[name].mechanics) for name in resolved_names),
        )
        shape = (len(names), max_mechanics)
        torch_device = torch.device(device)

        mechanic_opcode = torch.zeros(shape, dtype=torch.int16, device=torch_device)
        shield_hitpoints = torch.zeros(shape, dtype=torch.float64, device=torch_device)
        ability_elixir_cost = torch.zeros(shape, dtype=torch.int16, device=torch_device)
        ability_cooldown_ms = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        ability_duration_ms = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        ability_effect_count = torch.zeros(
            shape, dtype=torch.int16, device=torch_device
        )
        attack_speed_multiplier = torch.ones(
            shape, dtype=torch.float64, device=torch_device
        )
        movement_speed_multiplier = torch.ones(
            shape, dtype=torch.float64, device=torch_device
        )
        cast_time_ms = torch.zeros(shape, dtype=torch.int64, device=torch_device)
        trigger_delay_ms = torch.zeros(shape, dtype=torch.int64, device=torch_device)

        for card_id, name in enumerate(resolved_names, start=1):
            stats = loader.get_card(name)
            if stats is None:
                raise ValueError(f"could not materialize card {name!r}")
            scale = getattr(stats, "get_scaled_stat", None)
            for mechanic_slot, mechanic in enumerate(definitions[name].mechanics):
                opcode = MECHANIC_OPCODE[type(mechanic).__name__]
                mechanic_opcode[card_id, mechanic_slot] = opcode

                raw_shield = getattr(mechanic, "shield_hp", None)
                if raw_shield is not None:
                    shield_hitpoints[card_id, mechanic_slot] = (
                        _number(scale(raw_shield))
                        if callable(scale)
                        else _number(raw_shield)
                    )

                ability = getattr(mechanic, "ability", None)
                if ability is not None:
                    elixir_cost = int(_number(getattr(ability, "elixir_cost", 0)))
                    cooldown = int(_number(getattr(ability, "cooldown_ms", 0)))
                    duration = int(_number(getattr(ability, "duration_ms", 0)))
                    attack_multiplier = _number(
                        getattr(mechanic, "attack_speed_multiplier", 1.0), 1.0
                    )
                    movement_multiplier = _number(
                        getattr(mechanic, "movement_speed_multiplier", 1.0), 1.0
                    )
                    cast_time = int(_number(getattr(mechanic, "cast_time_ms", 0)))
                    trigger_delay = int(
                        _number(getattr(mechanic, "trigger_delay_ms", 0))
                    )

                    # Cloak-like mechanics hydrate these fields in on_attach.
                    # Use the same capability gate and serialized paths here;
                    # this avoids both card identity switches and coincidental
                    # agreement with constructor defaults.
                    serialized_buff_ability = all(
                        hasattr(mechanic, field_name)
                        for field_name in (
                            "attack_speed_multiplier",
                            "movement_speed_multiplier",
                            "duration_ms",
                            "cast_time_ms",
                            "trigger_delay_ms",
                        )
                    )
                    if serialized_buff_ability:
                        raw = getattr(stats, "_raw_entry", {}) or {}
                        character_data = raw.get("summonCharacterData", {}) or {}
                        ability_data = character_data.get("abilityData", {}) or {}
                        buff_data = ability_data.get("buffData", {}) or {}
                        elixir_cost = int(ability_data.get("manaCost", elixir_cost))
                        cooldown = int(ability_data.get("cooldown", cooldown))
                        duration = int(ability_data.get("buffTime", duration))
                        cast_time = int(ability_data.get("castTime", cast_time))
                        trigger_delay = int(
                            ability_data.get("triggerDelay", trigger_delay)
                        )
                        hit_speed_percent = buff_data.get("hitSpeedMultiplier")
                        if hit_speed_percent is not None:
                            attack_multiplier = float(hit_speed_percent) / 100.0
                        speed_percent = buff_data.get("speedMultiplier")
                        if speed_percent is not None:
                            movement_multiplier = max(
                                0.0, 1.0 + float(speed_percent) / 100.0
                            )

                    ability_elixir_cost[card_id, mechanic_slot] = elixir_cost
                    ability_cooldown_ms[card_id, mechanic_slot] = cooldown
                    ability_duration_ms[card_id, mechanic_slot] = duration
                    ability_effect_count[card_id, mechanic_slot] = len(
                        getattr(ability, "effects", ())
                    )
                    attack_speed_multiplier[card_id, mechanic_slot] = attack_multiplier
                    movement_speed_multiplier[card_id, mechanic_slot] = (
                        movement_multiplier
                    )
                    cast_time_ms[card_id, mechanic_slot] = cast_time
                    trigger_delay_ms[card_id, mechanic_slot] = trigger_delay

        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            mechanic_opcode=mechanic_opcode,
            shield_hitpoints=shield_hitpoints,
            ability_elixir_cost=ability_elixir_cost,
            ability_cooldown_ms=ability_cooldown_ms,
            ability_duration_ms=ability_duration_ms,
            ability_effect_count=ability_effect_count,
            attack_speed_multiplier=attack_speed_multiplier,
            movement_speed_multiplier=movement_speed_multiplier,
            cast_time_ms=cast_time_ms,
            trigger_delay_ms=trigger_delay_ms,
        )


@dataclass(frozen=True)
class ShieldDamageResult:
    """Resolved HP damage plus the event plane consumed by shield observers."""

    hitpoint_damage: torch.Tensor
    shield_broken: torch.Tensor


def apply_shield_damage_(
    current_shield: torch.Tensor,
    shield_break_count: torch.Tensor,
    incoming_damage: torch.Tensor,
    has_shield: torch.Tensor,
) -> ShieldDamageResult:
    """Apply one simultaneous damage lane with exact whole-hit shield absorb.

    Mutable shield/count tensors are updated in place.  ``shield_broken`` is
    deliberately returned as an event plane because the oracle broadcasts
    that transition to connected damage-ramp mechanics.
    """

    if not (
        current_shield.shape
        == shield_break_count.shape
        == incoming_damage.shape
        == has_shield.shape
    ):
        raise ValueError("shield damage tensors must have identical shapes")
    positive = incoming_damage > 0
    absorbs = has_shield & positive & (current_shield > 0)
    next_shield = torch.clamp(current_shield - incoming_damage, min=0.0)
    broken = absorbs & (next_shield <= 0)
    current_shield.copy_(torch.where(absorbs, next_shield, current_shield))
    shield_break_count.add_(broken.to(shield_break_count.dtype))
    hitpoint_damage = torch.where(
        positive & ~absorbs,
        incoming_damage,
        torch.zeros_like(incoming_damage),
    )
    return ShieldDamageResult(hitpoint_damage=hitpoint_damage, shield_broken=broken)


def champion_owner_mask(
    entity_id: torch.Tensor,
    entity_player: torch.Tensor,
    ability_key: torch.Tensor,
    alive: torch.Tensor,
    has_ability: torch.Tensor,
) -> torch.Tensor:
    """Select the newest live copy for each player/serialized ability key."""

    shape = entity_id.shape
    if any(
        value.shape != shape
        for value in (entity_player, ability_key, alive, has_ability)
    ):
        raise ValueError("Champion ownership tensors must have identical shapes")
    candidates = alive & has_ability & (entity_id > 0) & (ability_key > 0)
    same_group = (entity_player[:, :, None] == entity_player[:, None, :]) & (
        ability_key[:, :, None] == ability_key[:, None, :]
    )
    newer_exists = (
        candidates[:, None, :]
        & same_group
        & (entity_id[:, None, :] > entity_id[:, :, None])
    ).any(dim=2)
    return candidates & ~newer_exists


@dataclass(frozen=True)
class ChampionOwnershipResult:
    owner: torch.Tensor
    transferred: torch.Tensor


def refresh_champion_ownership_(
    *,
    entity_id: torch.Tensor,
    entity_player: torch.Tensor,
    ability_key: torch.Tensor,
    alive: torch.Tensor,
    has_ability: torch.Tensor,
    recorded_owner_id: torch.Tensor,
    last_use_time_ms: torch.Tensor,
) -> ChampionOwnershipResult:
    """Refresh owner groups and reset only a newly selected owner's cooldown.

    ``recorded_owner_id`` has shape ``[battle, 2, ability_key_count]``.  This
    is the tensor equivalent of the oracle's mapping keyed by player and
    resolved Champion identity; zero represents an absent group.
    """

    if recorded_owner_id.ndim != 3 or recorded_owner_id.shape[1] != 2:
        raise ValueError(
            "recorded_owner_id must have shape [battle, 2, ability_key_count]"
        )
    if recorded_owner_id.shape[0] != entity_id.shape[0]:
        raise ValueError("ownership batch size mismatch")
    key_count = int(recorded_owner_id.shape[2])
    if bool(
        (has_ability & ((ability_key <= 0) | (ability_key >= key_count))).any().item()
    ):
        raise ValueError("live ability key is outside recorded owner capacity")

    owner = champion_owner_mask(
        entity_id, entity_player, ability_key, alive, has_ability
    )
    group_index = entity_player.to(torch.int64) * key_count + ability_key.to(
        torch.int64
    )
    safe_group_index = group_index.clamp(min=0, max=2 * key_count - 1)
    previous = recorded_owner_id.reshape(entity_id.shape[0], -1).gather(
        1, safe_group_index
    )
    transferred = owner & (previous != entity_id)
    last_use_time_ms.copy_(
        torch.where(
            transferred,
            torch.full_like(last_use_time_ms, NEVER_USED_TIME_MS),
            last_use_time_ms,
        )
    )

    selected = torch.zeros(
        (entity_id.shape[0], 2 * key_count),
        dtype=recorded_owner_id.dtype,
        device=recorded_owner_id.device,
    )
    selected.scatter_reduce_(
        1,
        safe_group_index,
        torch.where(owner, entity_id, torch.zeros_like(entity_id)),
        reduce="amax",
        include_self=True,
    )
    recorded_owner_id.copy_(selected.reshape_as(recorded_owner_id))
    return ChampionOwnershipResult(owner=owner, transferred=transferred)


def champion_button_owner_mask(
    owner_mask: torch.Tensor,
    entity_id: torch.Tensor,
    entity_player: torch.Tensor,
) -> torch.Tensor:
    """Resolve the single Champion button to the newest owned ability/player."""

    result = torch.zeros_like(owner_mask)
    for player_id in (0, 1):
        candidates = owner_mask & (entity_player == player_id)
        newest_id = (
            torch.where(
                candidates,
                entity_id,
                torch.zeros_like(entity_id),
            )
            .max(dim=1)
            .values
        )
        result |= (
            candidates & (entity_id == newest_id[:, None]) & (newest_id[:, None] > 0)
        )
    return result


def champion_can_activate(
    *,
    now_ms: torch.Tensor,
    player_elixir: torch.Tensor,
    entity_player: torch.Tensor,
    button_owner: torch.Tensor,
    alive: torch.Tensor,
    placement_pending: torch.Tensor,
    deploy_delay_seconds: torch.Tensor,
    stunned: torch.Tensor,
    can_execute_while_frozen: bool,
    last_use_time_ms: torch.Tensor,
    is_active: torch.Tensor,
    activation_time_ms: torch.Tensor,
    elixir_cost: torch.Tensor,
    cooldown_ms: torch.Tensor,
    duration_ms: torch.Tensor,
) -> torch.Tensor:
    """Return the exact per-entity availability predicate for the ability."""

    player_cost_available = (
        player_elixir.gather(1, entity_player.to(torch.int64)) >= elixir_cost
    )
    never_used = last_use_time_ms <= -(10**11)
    cooldown_ready = never_used | (
        now_ms[:, None] >= activation_time_ms + duration_ms + cooldown_ms
    )
    frozen_ready = torch.ones_like(stunned) if can_execute_while_frozen else ~stunned
    return (
        button_owner
        & player_cost_available
        & alive
        & frozen_ready
        & ~placement_pending
        & (deploy_delay_seconds <= 1e-9)
        & cooldown_ready
        & ~is_active
    )


def activate_champion_abilities_(
    *,
    requested_players: torch.Tensor,
    can_activate: torch.Tensor,
    now_ms: torch.Tensor,
    player_elixir: torch.Tensor,
    entity_player: torch.Tensor,
    last_use_time_ms: torch.Tensor,
    is_active: torch.Tensor,
    activation_time_ms: torch.Tensor,
    elixir_cost: torch.Tensor,
    cloak_mask: torch.Tensor,
    trigger_delay_ms: torch.Tensor,
    cast_time_ms: torch.Tensor,
    cloak_pending_until_ms: torch.Tensor,
    cast_lock_until_ms: torch.Tensor,
) -> torch.Tensor:
    """Activate requested available abilities and schedule cloak deadlines."""

    requested = requested_players.gather(1, entity_player.to(torch.int64))
    activated = requested & can_activate
    cost = torch.where(activated, elixir_cost, torch.zeros_like(elixir_cost))
    spent = torch.zeros_like(player_elixir)
    spent.scatter_add_(1, entity_player.to(torch.int64), cost.to(spent.dtype))
    player_elixir.sub_(spent)

    now = now_ms[:, None]
    last_use_time_ms.copy_(torch.where(activated, now, last_use_time_ms))
    is_active |= activated
    activation_time_ms.copy_(torch.where(activated, now, activation_time_ms))

    activated_cloak = activated & cloak_mask
    pending = now + trigger_delay_ms
    cast_lock = now + cast_time_ms
    cloak_pending_until_ms.copy_(
        torch.where(activated_cloak, pending, cloak_pending_until_ms)
    )
    cast_lock_until_ms.copy_(
        torch.where(activated_cloak, cast_lock, cast_lock_until_ms)
    )
    # Cloak duration/cooldown start at the trigger, not the button press.
    activation_time_ms.copy_(torch.where(activated_cloak, pending, activation_time_ms))
    return activated


@dataclass(frozen=True)
class ChampionTickResult:
    cloak_started: torch.Tensor
    cloak_ended: torch.Tensor
    cast_lock_ended: torch.Tensor
    died: torch.Tensor
    cancelled_before_effect: torch.Tensor


def tick_champion_abilities_(
    *,
    now_ms: torch.Tensor,
    alive: torch.Tensor,
    cancel_before_effect: torch.Tensor,
    last_use_time_ms: torch.Tensor,
    is_active: torch.Tensor,
    activation_time_ms: torch.Tensor,
    duration_ms: torch.Tensor,
    cloak_mask: torch.Tensor,
    cloak_pending_until_ms: torch.Tensor,
    cast_lock_until_ms: torch.Tensor,
    attack_speed_multiplier: torch.Tensor,
    movement_speed_multiplier: torch.Tensor,
    attack_mode_multiplier: torch.Tensor,
    movement_mode_multiplier: torch.Tensor,
    original_movement_mode_multiplier: torch.Tensor,
    stealth_until_ms: torch.Tensor,
) -> ChampionTickResult:
    """Advance generic duration and cloak trigger/cast/expiry deadlines.

    Death is distinct from an interrupted pre-effect cast. Archer Queen death
    clears the pending/cast/active cloak state but leaves its historical use
    timestamp alone; ``cancel_before_effect`` additionally restores the never-
    used cooldown sentinel and zero activation time, matching ``ActiveAbility``.
    """

    now = now_ms[:, None]
    died = (
        cloak_mask
        & ~alive
        & (
            is_active
            | (cloak_pending_until_ms >= 0)
            | (cast_lock_until_ms >= 0)
            | ~torch.isnan(original_movement_mode_multiplier)
        )
    )
    cancelled = cancel_before_effect & is_active
    explicit_or_death_abort = cancel_before_effect | died
    cloak_abort = cloak_mask & explicit_or_death_abort
    is_active &= ~explicit_or_death_abort
    activation_time_ms.copy_(
        torch.where(
            cancel_before_effect,
            torch.zeros_like(activation_time_ms),
            activation_time_ms,
        )
    )
    last_use_time_ms.copy_(
        torch.where(
            cancel_before_effect,
            torch.full_like(last_use_time_ms, NEVER_USED_TIME_MS),
            last_use_time_ms,
        )
    )
    cloak_pending_until_ms.copy_(
        torch.where(
            cloak_abort,
            torch.full_like(cloak_pending_until_ms, -1),
            cloak_pending_until_ms,
        )
    )
    cast_lock_until_ms.copy_(
        torch.where(
            cloak_abort,
            torch.full_like(cast_lock_until_ms, -1),
            cast_lock_until_ms,
        )
    )

    expired = is_active & (now - activation_time_ms >= duration_ms)
    is_active &= ~expired

    cloak_started = (
        cloak_mask & (cloak_pending_until_ms >= 0) & (now >= cloak_pending_until_ms)
    )
    original_movement_mode_multiplier.copy_(
        torch.where(
            cloak_started,
            movement_mode_multiplier,
            original_movement_mode_multiplier,
        )
    )
    attack_mode_multiplier.copy_(
        torch.where(cloak_started, attack_speed_multiplier, attack_mode_multiplier)
    )
    movement_mode_multiplier.copy_(
        torch.where(
            cloak_started,
            original_movement_mode_multiplier * movement_speed_multiplier,
            movement_mode_multiplier,
        )
    )
    stealth_until_ms.copy_(
        torch.where(cloak_started, now + duration_ms, stealth_until_ms)
    )
    cloak_pending_until_ms.copy_(
        torch.where(
            cloak_started,
            torch.full_like(cloak_pending_until_ms, -1),
            cloak_pending_until_ms,
        )
    )

    cast_lock_ended = (
        cloak_mask & (cast_lock_until_ms >= 0) & (now >= cast_lock_until_ms)
    )
    cast_lock_until_ms.copy_(
        torch.where(
            cast_lock_ended,
            torch.full_like(cast_lock_until_ms, -1),
            cast_lock_until_ms,
        )
    )

    has_applied_cloak = ~torch.isnan(original_movement_mode_multiplier)
    cloak_ended = cloak_mask & ~is_active & has_applied_cloak
    movement_mode_multiplier.copy_(
        torch.where(
            cloak_ended,
            original_movement_mode_multiplier,
            movement_mode_multiplier,
        )
    )
    attack_mode_multiplier.copy_(
        torch.where(
            cloak_ended, torch.ones_like(attack_mode_multiplier), attack_mode_multiplier
        )
    )
    stealth_until_ms.copy_(
        torch.where(cloak_ended, torch.zeros_like(stealth_until_ms), stealth_until_ms)
    )
    original_movement_mode_multiplier.copy_(
        torch.where(
            cloak_ended,
            torch.full_like(original_movement_mode_multiplier, math.nan),
            original_movement_mode_multiplier,
        )
    )
    return ChampionTickResult(
        cloak_started=cloak_started,
        cloak_ended=cloak_ended,
        cast_lock_ended=cast_lock_ended,
        died=died,
        cancelled_before_effect=cancelled,
    )
