"""Generalized dense Champion ability state for the practical tensor Gym.

Ability profiles are compiled once from serialized ``abilityData`` and the
stable mechanic opcode emitted by :mod:`clasher.torch_sim.catalog`.  Runtime
code subsequently indexes numeric card tables only: no card names, Python
entities, hand mutation, or host synchronization participate in a tick.

The state is entity-slot aligned but bound to monotonic stable IDs.  Reusing a
physical entity slot therefore cannot inherit a dead Champion's ability.  A
single player button targets the newest live supported Champion for that
player, matching the native ownership rule without storing Python objects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.balance import LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader

from .catalog import MECHANIC_OPCODE, CardKindOpcode, TensorCardCatalog
from .simple_state import FastGymState

FAST_ABILITY_TICK_MS = 50


def _milliseconds_to_ticks(value: float) -> int:
    return math.ceil(value / FAST_ABILITY_TICK_MS)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class FastAbilityCatalog:
    """Dense typed ability profiles indexed by the ordinary card ID.

    ``supported=False`` is the only runtime admission signal.  ``malformed``
    and ``duplicate`` retain setup-time diagnostics while every numeric field
    stays zero/neutral, so bad serialized data fails closed rather than
    partially enabling an ability.
    """

    device: torch.device
    supported: torch.Tensor
    malformed: torch.Tensor
    duplicate: torch.Tensor
    profile_card_id: torch.Tensor
    mechanic_opcode: torch.Tensor
    elixir_cost: torch.Tensor
    trigger_delay_ticks: torch.Tensor
    cast_time_ticks: torch.Tensor
    duration_ticks: torch.Tensor
    cooldown_ticks: torch.Tensor
    attack_speed_multiplier: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    can_activate_while_stunned: torch.Tensor

    @property
    def card_capacity(self) -> int:
        return int(self.supported.shape[0])

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> FastAbilityCatalog:
        """Compile validated numeric profiles from serialized card data.

        Compilation is intentionally setup-only and may inspect Python data.
        The resulting tensors are immutable runtime authority.  Currently the
        serialized cloak opcode is the supported generalized multiplier
        profile; other Champion payload opcodes fail closed until their own
        numeric payload kernels exist.
        """

        # TensorCardCatalog may retain an unindexed accelerator alias
        # (``cuda``), while allocated tensors expose the concrete device
        # (``cuda:0``).  Runtime metadata follows an authoritative tensor so
        # strict same-device checks remain meaningful on accelerators.
        device = catalog.mechanic_opcode.device
        size = len(catalog.names)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        malformed = zeros(torch.bool)
        duplicate = zeros(torch.bool)
        profile_card_id = zeros(torch.int64)
        ability_opcode = zeros(torch.int16)
        elixir_cost = zeros(torch.int16)
        trigger_ticks = zeros(torch.int32)
        cast_ticks = zeros(torch.int32)
        duration_ticks = zeros(torch.int32)
        cooldown_ticks = zeros(torch.int32)
        attack_multiplier = torch.ones(size, dtype=torch.float32, device=device)
        movement_multiplier = torch.ones(size, dtype=torch.float32, device=device)
        stun_legal = zeros(torch.bool)

        cloak_opcode = int(MECHANIC_OPCODE["ArcherQueenCloak"])
        soul_opcode = int(MECHANIC_OPCODE["SkeletonKingSoulCollector"])
        recognized_opcodes = {cloak_opcode, soul_opcode}
        definitions = loader.load_card_definitions()

        # This loop is compilation, never runtime.  Keeping all name and host
        # inspection here leaves the hot path a pure numeric table lookup.
        for card_id, name in enumerate(catalog.names[1:], start=1):
            opcodes = catalog.mechanic_opcode[card_id].detach().cpu().tolist()
            ability_slots = [
                slot
                for slot, opcode in enumerate(opcodes)
                if int(opcode) in recognized_opcodes
            ]
            if not ability_slots:
                continue
            if len(ability_slots) != 1:
                duplicate[card_id] = True
                malformed[card_id] = True
                continue

            slot = ability_slots[0]
            opcode = int(opcodes[slot])
            ability_opcode[card_id] = opcode
            if opcode != cloak_opcode or int(catalog.kind[card_id].item()) != int(
                CardKindOpcode.CHAMPION
            ):
                malformed[card_id] = True
                continue

            resolved = resolve_card_name(name, definitions)
            definition = definitions.get(resolved)
            stats = loader.get_card(name)
            raw = {} if stats is None else getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {})
            ability = (
                character.get("abilityData", {}) if isinstance(character, dict) else {}
            )
            buff = ability.get("buffData", {}) if isinstance(ability, dict) else {}
            if (
                definition is None
                or not isinstance(ability, dict)
                or not isinstance(buff, dict)
            ):
                malformed[card_id] = True
                continue

            cost = _finite_number(ability.get("manaCost"))
            cooldown_ms = _finite_number(ability.get("cooldown"))
            duration_ms = _finite_number(ability.get("buffTime"))
            cast_ms = _finite_number(ability.get("castTime"))
            trigger_ms = _finite_number(ability.get("triggerDelay"))
            hit_percent = _finite_number(buff.get("hitSpeedMultiplier"))
            speed_percent = _finite_number(buff.get("speedMultiplier"))
            values = (
                cost,
                cooldown_ms,
                duration_ms,
                cast_ms,
                trigger_ms,
                hit_percent,
                speed_percent,
            )
            if any(value is None for value in values):
                malformed[card_id] = True
                continue

            assert cost is not None
            assert cooldown_ms is not None
            assert duration_ms is not None
            assert cast_ms is not None
            assert trigger_ms is not None
            assert hit_percent is not None
            assert speed_percent is not None
            attack = hit_percent / 100.0
            movement = 1.0 + speed_percent / 100.0
            valid = (
                cost == round(cost)
                and 0 < cost <= 10
                and cooldown_ms > 0
                and duration_ms > 0
                and 0 <= trigger_ms <= cast_ms
                and attack > 0
                and movement > 0
            )

            # Bind raw abilityData to the compiled mechanic slot.  This catches
            # stale/mismatched serialization instead of silently trusting one
            # of two authorities.
            parameter_names = catalog.mechanic_parameter_names
            expected_parameters = {
                "attack_speed_multiplier": attack,
                "movement_speed_multiplier": movement,
                "duration_ms": duration_ms,
                "cast_time_ms": cast_ms,
                "trigger_delay_ms": trigger_ms,
            }
            for parameter_name, expected in expected_parameters.items():
                if parameter_name not in parameter_names:
                    valid = False
                    continue
                parameter = parameter_names.index(parameter_name)
                actual = float(
                    catalog.mechanic_parameters[card_id, slot, parameter].item()
                )
                valid &= math.isfinite(actual) and math.isclose(
                    actual, expected, rel_tol=0.0, abs_tol=1e-6
                )
            if not valid:
                malformed[card_id] = True
                continue

            supported[card_id] = True
            profile_card_id[card_id] = card_id
            elixir_cost[card_id] = round(cost)
            trigger_ticks[card_id] = _milliseconds_to_ticks(trigger_ms)
            cast_ticks[card_id] = _milliseconds_to_ticks(cast_ms)
            duration_ticks[card_id] = _milliseconds_to_ticks(duration_ms)
            cooldown_ticks[card_id] = _milliseconds_to_ticks(cooldown_ms)
            attack_multiplier[card_id] = attack
            movement_multiplier[card_id] = movement
            stun_legal[card_id] = bool(LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN)

        return cls(
            device=device,
            supported=supported,
            malformed=malformed,
            duplicate=duplicate,
            profile_card_id=profile_card_id,
            mechanic_opcode=ability_opcode,
            elixir_cost=elixir_cost,
            trigger_delay_ticks=trigger_ticks,
            cast_time_ticks=cast_ticks,
            duration_ticks=duration_ticks,
            cooldown_ticks=cooldown_ticks,
            attack_speed_multiplier=attack_multiplier,
            movement_speed_multiplier=movement_multiplier,
            can_activate_while_stunned=stun_legal,
        )


@dataclass
class FastAbilityState:
    """Fixed entity-bound ability state and newest per-player owner."""

    device: torch.device
    bound_stable_id: torch.Tensor
    bound_card_id: torch.Tensor
    trigger_tick: torch.Tensor
    cast_end_tick: torch.Tensor
    duration_end_tick: torch.Tensor
    cooldown_end_tick: torch.Tensor
    cooldown_armed: torch.Tensor
    newest_owner_stable_id: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.bound_stable_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.bound_stable_id.shape[1])

    @classmethod
    def empty_like(cls, state: FastGymState) -> FastAbilityState:
        entity_shape = state.active.shape
        owner_shape = (state.batch_size, 2)
        return cls(
            device=state.device,
            bound_stable_id=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            bound_card_id=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            trigger_tick=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            cast_end_tick=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            duration_end_tick=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            cooldown_end_tick=torch.zeros(
                entity_shape, dtype=torch.int64, device=state.device
            ),
            cooldown_armed=torch.zeros(
                entity_shape, dtype=torch.bool, device=state.device
            ),
            newest_owner_stable_id=torch.zeros(
                owner_shape, dtype=torch.int64, device=state.device
            ),
        )

    def clone(self) -> FastAbilityState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def reset_rows_(self, rows: torch.Tensor) -> None:
        """Clear selected batch rows using a graph-safe boolean row mask."""

        rows = rows.to(device=self.device, dtype=torch.bool)
        if rows.shape != (self.batch_size,):
            raise ValueError("rows must have shape [batch]")
        entity_rows = rows[:, None]
        for descriptor in fields(self):
            if descriptor.name in {"device", "newest_owner_stable_id"}:
                continue
            getattr(self, descriptor.name).masked_fill_(entity_rows, 0)
        self.newest_owner_stable_id.masked_fill_(rows[:, None], 0)


@dataclass(frozen=True)
class FastAbilityRefreshResult:
    bound: torch.Tensor
    rebound: torch.Tensor
    owner_changed: torch.Tensor


@dataclass(frozen=True)
class FastAbilityPlayerView:
    """Own-player ability mask and normalized recurrent observation planes."""

    legal: torch.Tensor
    owner_stable_id: torch.Tensor
    owner_card_id: torch.Tensor
    cooldown_fraction: torch.Tensor
    duration_fraction: torch.Tensor


@dataclass(frozen=True)
class FastAbilityStepResult:
    """Entity-local ability effects plus the player-facing view."""

    pending: torch.Tensor
    cast_locked: torch.Tensor
    effect_active: torch.Tensor
    attack_speed_multiplier: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    player: FastAbilityPlayerView


@dataclass(frozen=True)
class FastAbilityActivationResult:
    """Accepted button presses and their elixir transaction intent.

    The caller applies ``elixir_delta`` to its private action state.  No hand,
    cycle, or deployment data is accepted or returned, so activating an
    ability cannot rotate a card.
    """

    activated: torch.Tensor
    elixir_delta: torch.Tensor
    owner_stable_id: torch.Tensor
    owner_card_id: torch.Tensor


def _validate_runtime(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
) -> None:
    entity_shape = state.active.shape
    if abilities.device != state.device or catalog.device != state.device:
        raise ValueError("Gym state, ability state, and catalog must share a device")
    for descriptor in fields(abilities):
        if descriptor.name == "device":
            continue
        value = getattr(abilities, descriptor.name)
        expected = (
            (state.batch_size, 2)
            if descriptor.name == "newest_owner_stable_id"
            else entity_shape
        )
        if value.shape != expected:
            raise ValueError(f"{descriptor.name} has an invalid shape")


def _entity_profile(
    state: FastGymState,
    catalog: FastAbilityCatalog,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    valid_card = (state.card_id > 0) & (state.card_id < catalog.card_capacity)
    safe_card = state.card_id.clamp(min=0, max=catalog.card_capacity - 1)
    supported = valid_card & catalog.supported[safe_card]
    live = state.active & (state.hp > 0)
    return safe_card, supported, live


def _owner_slot_mask(
    state: FastGymState,
    abilities: FastAbilityState,
) -> torch.Tensor:
    players = torch.arange(2, dtype=torch.int8, device=state.device)
    return (
        (
            abilities.bound_stable_id[:, None, :]
            == abilities.newest_owner_stable_id[:, :, None]
        )
        & (state.owner[:, None, :] == players.view(1, 2, 1))
        & (abilities.newest_owner_stable_id[:, :, None] > 0)
    )


def refresh_fast_abilities_(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
) -> FastAbilityRefreshResult:
    """Rebind reused slots and select each player's newest live Champion."""

    _validate_runtime(state, abilities, catalog)
    safe_card, supported, live = _entity_profile(state, catalog)
    bound = supported & live
    rebound = (abilities.bound_stable_id != state.stable_id) | (
        abilities.bound_card_id != safe_card
    )
    clear = ~bound | rebound
    for name in (
        "trigger_tick",
        "cast_end_tick",
        "duration_end_tick",
        "cooldown_end_tick",
        "cooldown_armed",
    ):
        getattr(abilities, name).masked_fill_(clear, 0)
    abilities.bound_stable_id.copy_(
        torch.where(bound, state.stable_id, torch.zeros_like(state.stable_id))
    )
    abilities.bound_card_id.copy_(
        torch.where(bound, safe_card, torch.zeros_like(safe_card))
    )

    players = torch.arange(2, dtype=torch.int8, device=state.device)
    candidate = bound[:, None, :] & (state.owner[:, None, :] == players.view(1, 2, 1))
    newest = torch.where(
        candidate,
        state.stable_id[:, None, :],
        torch.zeros_like(state.stable_id[:, None, :]),
    ).amax(dim=2)
    owner_changed = newest != abilities.newest_owner_stable_id
    abilities.newest_owner_stable_id.copy_(newest)

    # Ownership transfer resets only the returning/new owner's cooldown.  An
    # effect already running on that troop remains attached until its normal
    # deadline, exactly as the object verifier does.
    owner_slot = _owner_slot_mask(state, abilities)
    changed_slot = (owner_changed[:, :, None] & owner_slot).any(dim=1)
    abilities.cooldown_armed.masked_fill_(changed_slot, False)
    return FastAbilityRefreshResult(
        bound=bound,
        rebound=rebound & bound,
        owner_changed=owner_changed,
    )


def _player_view_after_refresh(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
    *,
    elixir: torch.Tensor,
    stunned: torch.Tensor,
    player_alive: torch.Tensor,
) -> FastAbilityPlayerView:
    owner_slot = _owner_slot_mask(state, abilities)
    slot_index = owner_slot.to(torch.int64).argmax(dim=2)
    owner_card = abilities.bound_card_id.gather(1, slot_index)
    owner_card = torch.where(
        abilities.newest_owner_stable_id > 0,
        owner_card,
        torch.zeros_like(owner_card),
    )
    cost = catalog.elixir_cost[owner_card].to(torch.float32)
    now = state.tick[:, None]
    duration_end = abilities.duration_end_tick.gather(1, slot_index)
    cooldown_end = abilities.cooldown_end_tick.gather(1, slot_index)
    armed = abilities.cooldown_armed.gather(1, slot_index)
    engaged = duration_end > now
    owner_stunned = stunned.gather(1, slot_index)
    legal = (
        (abilities.newest_owner_stable_id > 0)
        & player_alive
        & ~state.game_over[:, None]
        & (state.deploy_ticks.gather(1, slot_index) <= 0)
        & (elixir >= cost)
        & ~engaged
        & (~armed | (now >= cooldown_end))
        & (~owner_stunned | catalog.can_activate_while_stunned[owner_card])
    )

    duration = catalog.duration_ticks[owner_card].clamp(min=1).to(torch.float32)
    cooldown = catalog.cooldown_ticks[owner_card].clamp(min=1).to(torch.float32)
    trigger = abilities.trigger_tick.gather(1, slot_index)
    effect_active = (now >= trigger) & engaged & (duration_end > 0)
    duration_remaining = torch.where(
        effect_active,
        (duration_end - now).clamp(min=0).to(torch.float32),
        torch.zeros_like(duration),
    )
    cooldown_remaining = torch.where(
        armed & engaged,
        cooldown,
        torch.where(
            armed,
            (cooldown_end - now).clamp(min=0).to(torch.float32),
            torch.zeros_like(cooldown),
        ),
    )
    present = abilities.newest_owner_stable_id > 0
    return FastAbilityPlayerView(
        legal=legal,
        owner_stable_id=abilities.newest_owner_stable_id,
        owner_card_id=owner_card,
        cooldown_fraction=torch.where(
            present, (cooldown_remaining / cooldown).clamp(0.0, 1.0), 0.0
        ),
        duration_fraction=torch.where(
            present, (duration_remaining / duration).clamp(0.0, 1.0), 0.0
        ),
    )


def fast_ability_player_view(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
    *,
    elixir: torch.Tensor,
    stunned: torch.Tensor | None = None,
    player_alive: torch.Tensor | None = None,
) -> FastAbilityPlayerView:
    """Refresh ownership and return the public player-ordered ability view."""

    refresh_fast_abilities_(state, abilities, catalog)
    entity_shape = state.active.shape
    player_shape = (state.batch_size, 2)
    elixir = elixir.to(device=state.device, dtype=torch.float32)
    if elixir.shape != player_shape:
        raise ValueError("elixir must have shape [batch, 2]")
    if stunned is None:
        stunned = torch.zeros(entity_shape, dtype=torch.bool, device=state.device)
    else:
        stunned = stunned.to(device=state.device, dtype=torch.bool)
    if stunned.shape != entity_shape:
        raise ValueError("stunned must have shape [batch, entities]")
    if player_alive is None:
        player_alive = torch.ones(player_shape, dtype=torch.bool, device=state.device)
    else:
        player_alive = player_alive.to(device=state.device, dtype=torch.bool)
    if player_alive.shape != player_shape:
        raise ValueError("player_alive must have shape [batch, 2]")
    return _player_view_after_refresh(
        state,
        abilities,
        catalog,
        elixir=elixir,
        stunned=stunned,
        player_alive=player_alive,
    )


def activate_fast_abilities_(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
    requested_players: torch.Tensor,
    *,
    elixir: torch.Tensor,
    stunned: torch.Tensor | None = None,
    player_alive: torch.Tensor | None = None,
) -> FastAbilityActivationResult:
    """Atomically schedule legal ability requests and return spend intent."""

    requested_players = requested_players.to(device=state.device, dtype=torch.bool)
    if requested_players.shape != (state.batch_size, 2):
        raise ValueError("requested_players must have shape [batch, 2]")
    player = fast_ability_player_view(
        state,
        abilities,
        catalog,
        elixir=elixir,
        stunned=stunned,
        player_alive=player_alive,
    )
    activated = requested_players & player.legal
    owner_slot = _owner_slot_mask(state, abilities)
    activate_slot = (activated[:, :, None] & owner_slot).any(dim=1)
    card_id = abilities.bound_card_id
    now = state.tick[:, None]
    trigger = now + catalog.trigger_delay_ticks[card_id]
    cast_end = now + catalog.cast_time_ticks[card_id]
    duration_end = trigger + catalog.duration_ticks[card_id]
    cooldown_end = duration_end + catalog.cooldown_ticks[card_id]
    abilities.trigger_tick.copy_(
        torch.where(activate_slot, trigger, abilities.trigger_tick)
    )
    abilities.cast_end_tick.copy_(
        torch.where(activate_slot, cast_end, abilities.cast_end_tick)
    )
    abilities.duration_end_tick.copy_(
        torch.where(activate_slot, duration_end, abilities.duration_end_tick)
    )
    abilities.cooldown_end_tick.copy_(
        torch.where(activate_slot, cooldown_end, abilities.cooldown_end_tick)
    )
    abilities.cooldown_armed.copy_(abilities.cooldown_armed | activate_slot)
    cost = catalog.elixir_cost[player.owner_card_id].to(torch.float32)
    return FastAbilityActivationResult(
        activated=activated,
        elixir_delta=torch.where(activated, -cost, torch.zeros_like(cost)),
        owner_stable_id=player.owner_stable_id,
        owner_card_id=player.owner_card_id,
    )


def step_fast_abilities_(
    state: FastGymState,
    abilities: FastAbilityState,
    catalog: FastAbilityCatalog,
    *,
    elixir: torch.Tensor,
    stunned: torch.Tensor | None = None,
    player_alive: torch.Tensor | None = None,
) -> FastAbilityStepResult:
    """Resolve deadline views and return multiplier planes for this tick."""

    player = fast_ability_player_view(
        state,
        abilities,
        catalog,
        elixir=elixir,
        stunned=stunned,
        player_alive=player_alive,
    )
    now = state.tick[:, None]
    engaged = (abilities.duration_end_tick > now) & (abilities.bound_stable_id > 0)
    pending = engaged & (now < abilities.trigger_tick)
    effect_active = engaged & (now >= abilities.trigger_tick)
    cast_locked = engaged & (now < abilities.cast_end_tick)
    card_id = abilities.bound_card_id
    one = torch.ones_like(catalog.attack_speed_multiplier[card_id])
    return FastAbilityStepResult(
        pending=pending,
        cast_locked=cast_locked,
        effect_active=effect_active,
        attack_speed_multiplier=torch.where(
            effect_active, catalog.attack_speed_multiplier[card_id], one
        ),
        movement_speed_multiplier=torch.where(
            effect_active, catalog.movement_speed_multiplier[card_id], one
        ),
        player=player,
    )


__all__ = [
    "FAST_ABILITY_TICK_MS",
    "FastAbilityActivationResult",
    "FastAbilityCatalog",
    "FastAbilityPlayerView",
    "FastAbilityRefreshResult",
    "FastAbilityState",
    "FastAbilityStepResult",
    "activate_fast_abilities_",
    "fast_ability_player_view",
    "refresh_fast_abilities_",
    "step_fast_abilities_",
]
