"""Compile and dispatch serialized status-mechanic payloads.

``TensorCardCatalog`` identifies the shared mechanic opcode, but mechanics whose
runtime ``on_attach`` method decodes nested character data cannot be executed
from its scalar parameter plane alone.  This module resolves those nested
status payloads once, by mechanic class and serialized field path, and exposes
card-aligned tensors for the status component kernels.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from numbers import Real

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units

from .status import TensorStatusState


class StatusTriggerOpcode(IntEnum):
    """Component hook that supplies a serialized status payload."""

    PADDING = 0
    ATTACK_HIT = 1
    AURA_TICK = 2


class StatusEffectOpcode(IntEnum):
    """Target-local status operation selected by serialized parameters."""

    PADDING = 0
    STUN = 1
    SLOW = 2


@dataclass(frozen=True)
class TensorStatusPayloadCatalog:
    """Card-aligned nested status payloads for shared mechanic hooks."""

    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    trigger: torch.Tensor
    effect: torch.Tensor
    count: torch.Tensor
    duration_ms: torch.Tensor
    duration_from_tick: torch.Tensor
    movement_multiplier: torch.Tensor
    attack_multiplier: torch.Tensor
    spawn_multiplier: torch.Tensor
    chance: torch.Tensor
    radius_units: torch.Tensor

    @property
    def max_payloads(self) -> int:
        return int(self.trigger.shape[1])

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorStatusPayloadCatalog:
        definitions = loader.load_card_definitions()
        resolved_names = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        missing = [name for name in resolved_names if name not in definitions]
        if missing:
            raise ValueError(f"missing card definitions: {missing}")

        names = ("", *resolved_names)
        name_to_id = {name: index for index, name in enumerate(names)}
        status_mechanics = {
            "SerializedOnHitBuff",
            "Stun",
            "FreezeDebuff",
        }
        per_card = [
            [
                mechanic
                for mechanic in definitions[name].mechanics
                if type(mechanic).__name__ in status_mechanics
            ]
            for name in resolved_names
        ]
        max_payloads = max(1, max((len(items) for items in per_card), default=0))
        size = len(names)
        torch_device = torch.device(device)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros((size, max_payloads), dtype=dtype, device=torch_device)

        trigger = zeros(torch.int8)
        effect = zeros(torch.int8)
        count = torch.zeros(size, dtype=torch.int8, device=torch_device)
        duration_ms = zeros(torch.int32)
        duration_from_tick = zeros(torch.bool)
        movement = torch.ones(
            (size, max_payloads), dtype=torch.float64, device=torch_device
        )
        attack = torch.ones_like(movement)
        spawn = torch.ones_like(movement)
        chance = torch.ones_like(movement)
        radius_units = zeros(torch.int32)

        for card_id, (name, mechanics) in enumerate(
            zip(resolved_names, per_card), start=1
        ):
            count[card_id] = len(mechanics)
            stats = loader.get_card(name)
            if stats is None:
                raise ValueError(f"could not materialize card {name!r}")
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}

            for slot, mechanic in enumerate(mechanics):
                mechanic_name = type(mechanic).__name__
                if mechanic_name == "SerializedOnHitBuff":
                    buff = character.get("buffOnDamageData", {}) or {}
                    duration_ms[card_id, slot] = max(
                        0,
                        int(
                            character.get(
                                "buffOnDamageTime",
                                getattr(mechanic, "duration_ms", 0),
                            )
                            or 0
                        ),
                    )
                    movement[card_id, slot] = _percent_to_multiplier(
                        buff.get("speedMultiplier")
                    )
                    attack[card_id, slot] = _percent_to_multiplier(
                        buff.get("hitSpeedMultiplier")
                    )
                    spawn[card_id, slot] = _percent_to_multiplier(
                        buff.get("spawnSpeedMultiplier")
                    )
                    trigger[card_id, slot] = StatusTriggerOpcode.ATTACK_HIT
                    effect[card_id, slot] = (
                        StatusEffectOpcode.STUN
                        if max(
                            movement[card_id, slot].item(),
                            attack[card_id, slot].item(),
                            spawn[card_id, slot].item(),
                        )
                        <= 0.0
                        else StatusEffectOpcode.SLOW
                    )
                elif mechanic_name == "Stun":
                    trigger[card_id, slot] = StatusTriggerOpcode.ATTACK_HIT
                    effect[card_id, slot] = StatusEffectOpcode.STUN
                    duration_ms[card_id, slot] = max(
                        0,
                        round(
                            _number(
                                getattr(mechanic, "stun_duration_ms", None),
                                "stun_duration_ms",
                            )
                        ),
                    )
                    chance[card_id, slot] = _number(
                        getattr(mechanic, "stun_chance", None),
                        "stun_chance",
                    )
                elif mechanic_name == "FreezeDebuff":
                    if bool(getattr(mechanic, "aura_effect", True)):
                        trigger[card_id, slot] = StatusTriggerOpcode.AURA_TICK
                    effect[card_id, slot] = StatusEffectOpcode.SLOW
                    duration_from_tick[card_id, slot] = True
                    movement[card_id, slot] = max(
                        0.0,
                        _number(
                            getattr(mechanic, "slow_multiplier", None),
                            "slow_multiplier",
                        ),
                    )
                    attack[card_id, slot] = movement[card_id, slot]
                    spawn[card_id, slot] = movement[card_id, slot]
                    radius_units[card_id, slot] = tiles_to_logic_units(
                        _number(
                            getattr(mechanic, "radius_tiles", None),
                            "radius_tiles",
                        )
                    )

        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            trigger=trigger,
            effect=effect,
            count=count,
            duration_ms=duration_ms,
            duration_from_tick=duration_from_tick,
            movement_multiplier=movement,
            attack_multiplier=attack,
            spawn_multiplier=spawn,
            chance=chance,
            radius_units=radius_units,
        )


def _percent_to_multiplier(value: object) -> float:
    if value is None:
        return 1.0
    return max(0.0, 1.0 + _number(value, "status multiplier") / 100.0)


def _number(value: object, name: str) -> float:
    if not isinstance(value, Real):
        raise TypeError(f"{name} must be a serialized numeric value")
    return float(value)


def apply_status_payloads(
    state: TensorStatusState,
    catalog: TensorStatusPayloadCatalog,
    source_card: torch.Tensor,
    *,
    trigger: StatusTriggerOpcode,
    eligible: bool | torch.Tensor = True,
    tick_duration_seconds: float | torch.Tensor | None = None,
    random_rolls: torch.Tensor | None = None,
) -> None:
    """Apply one serialized mechanic-hook pass to aligned target slots.

    ``source_card`` is ``[battle, target-entity]``.  Callers build it from the
    already ordered hit/aura event stream, so multiple sources affecting the
    same target retain oracle ordering by invoking this kernel per event wave.
    Geometry, effect immunity, and hidden-target filtering stay at the event
    producer boundary and are represented by ``eligible`` here.
    """

    if catalog.device != state.device:
        raise ValueError("status state and payload catalog must use the same device")
    card_ids = torch.as_tensor(source_card, dtype=torch.int64, device=state.device)
    if card_ids.shape != state.entity_shape:
        raise ValueError("source_card must have shape [batch, entity]")
    if bool(((card_ids < 0) | (card_ids >= len(catalog.names))).any().item()):
        raise ValueError("source_card contains an out-of-range catalog ID")
    selected = state._mask(eligible)
    payload_trigger = catalog.trigger[card_ids]
    payload_effect = catalog.effect[card_ids]
    payload_duration = catalog.duration_ms[card_ids].to(torch.float64) / 1000.0
    from_tick = catalog.duration_from_tick[card_ids]

    needs_tick_duration = (
        selected[:, :, None] & (payload_trigger == int(trigger)) & from_tick
    )
    if bool(needs_tick_duration.any().item()):
        if tick_duration_seconds is None:
            raise ValueError("tick_duration_seconds is required for aura payloads")
        tick_duration = state._entity_tensor(
            tick_duration_seconds,
            dtype=torch.float64,
            name="tick_duration_seconds",
        )
        payload_duration = torch.where(
            needs_tick_duration,
            tick_duration[:, :, None],
            payload_duration,
        )

    if random_rolls is None:
        rolls = torch.zeros_like(catalog.chance[card_ids])
        probabilistic = (
            selected[:, :, None]
            & (payload_trigger == int(trigger))
            & (catalog.chance[card_ids] < 1.0)
        )
        if bool(probabilistic.any().item()):
            raise ValueError(
                "random_rolls is required for probabilistic status payloads"
            )
    else:
        rolls = torch.as_tensor(random_rolls, dtype=torch.float64, device=state.device)
        if rolls.shape != payload_trigger.shape:
            raise ValueError("random_rolls must have shape [batch, entity, payload]")

    active_slot = (
        selected[:, :, None]
        & (payload_trigger == int(trigger))
        & (payload_duration > 0.0)
        & (rolls <= catalog.chance[card_ids])
    )
    for slot in range(catalog.max_payloads):
        slot_active = active_slot[:, :, slot]
        stun = slot_active & (
            payload_effect[:, :, slot] == int(StatusEffectOpcode.STUN)
        )
        slow = slot_active & (
            payload_effect[:, :, slot] == int(StatusEffectOpcode.SLOW)
        )
        state.apply_stun(payload_duration[:, :, slot], mask=stun)
        state.apply_slow(
            payload_duration[:, :, slot],
            catalog.movement_multiplier[card_ids, slot],
            attack_speed_multiplier=catalog.attack_multiplier[card_ids, slot],
            spawn_speed_multiplier=catalog.spawn_multiplier[card_ids, slot],
            mask=slow,
        )
