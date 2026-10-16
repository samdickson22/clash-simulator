"""Fixed-shape policy-visible mechanics for the practical tensor Gym.

This module is deliberately smaller than the exact resident mechanic graph.
Serialized mechanic opcodes are compiled once into card-aligned numeric planes;
the production tick then consumes only dense tensors.  Card names and Python
entity classes never enter the runtime path.

The first integrated family is visibility/availability.  Inactivity stealth
and idle-hide share one state owner because both change the same downstream
contracts: ordinary target acquisition, secondary targeting, effect
receivability, combat availability, and structured-observation features.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from numbers import Real

import torch

from clasher.data import CardDataLoader

from .catalog import MECHANIC_OPCODE, TensorCardCatalog

FAST_VISIBILITY_UNSUPPORTED = -1
FAST_VISIBILITY_NONE = 0
FAST_VISIBILITY_FADE_WHEN_IDLE = 1
FAST_VISIBILITY_HIDE_WHEN_IDLE = 2

_LOGIC_TICK_MS = 50


def _optional_milliseconds(value: object) -> int | None:
    if value is None or isinstance(value, bool) or not isinstance(value, Real):
        return None
    milliseconds = int(float(value))
    return milliseconds if milliseconds >= 0 else None


def _ticks_ceil(milliseconds: int) -> int:
    return (milliseconds + _LOGIC_TICK_MS - 1) // _LOGIC_TICK_MS


@dataclass(frozen=True)
class FastPolicyMechanicCatalog:
    """Card-aligned numeric profiles for policy-visible mechanic families."""

    device: torch.device
    visibility_kind: torch.Tensor
    declares_visibility: torch.Tensor
    profile_supported: torch.Tensor
    fade_delay_ticks: torch.Tensor
    fade_use_attack_range: torch.Tensor
    hide_delay_ticks: torch.Tensor
    rise_time_ticks: torch.Tensor
    area_receivable_while_invisible: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.visibility_kind.shape[0])

    @classmethod
    def empty(
        cls,
        size: int,
        *,
        device: str | torch.device,
    ) -> FastPolicyMechanicCatalog:
        """Return an all-ordinary profile for direct low-level runtimes."""

        if size < 1:
            raise ValueError("size must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        return cls(
            device=tensor_device,
            visibility_kind=torch.zeros(
                size, dtype=torch.int8, device=tensor_device
            ),
            declares_visibility=torch.zeros(
                size, dtype=torch.bool, device=tensor_device
            ),
            profile_supported=torch.ones(
                size, dtype=torch.bool, device=tensor_device
            ),
            fade_delay_ticks=torch.zeros(
                size, dtype=torch.int32, device=tensor_device
            ),
            fade_use_attack_range=torch.zeros(
                size, dtype=torch.bool, device=tensor_device
            ),
            hide_delay_ticks=torch.zeros(
                size, dtype=torch.int32, device=tensor_device
            ),
            rise_time_ticks=torch.zeros(
                size, dtype=torch.int32, device=tensor_device
            ),
            area_receivable_while_invisible=torch.zeros(
                size, dtype=torch.bool, device=tensor_device
            ),
        )

    @classmethod
    def compile(
        cls,
        catalog: TensorCardCatalog,
        loader: CardDataLoader,
    ) -> FastPolicyMechanicCatalog:
        """Compile visibility profiles from mechanic opcodes and raw scalars.

        A declared profile is supported only when exactly one operation in the
        family has every defining serialized scalar.  Constructor defaults do
        not fill absent production data: malformed declarations remain visible
        as ``FAST_VISIBILITY_UNSUPPORTED`` and can be rejected by admission.
        """

        # Use an accelerator's concrete tensor device (for example ``cuda:0``)
        # rather than retaining a potentially index-free construction alias.
        device = catalog.mechanic_opcode.device
        size = len(catalog.names)
        visibility_kind = torch.zeros(size, dtype=torch.int8, device=device)
        declares = torch.zeros(size, dtype=torch.bool, device=device)
        supported = torch.ones(size, dtype=torch.bool, device=device)
        fade_delay = torch.zeros(size, dtype=torch.int32, device=device)
        fade_use_range = torch.zeros(size, dtype=torch.bool, device=device)
        hide_delay = torch.zeros(size, dtype=torch.int32, device=device)
        rise_time = torch.zeros(size, dtype=torch.int32, device=device)
        area_while_invisible = torch.zeros(size, dtype=torch.bool, device=device)

        fade_opcode = int(MECHANIC_OPCODE["InvisibilityWhenNotAttacking"])
        hide_opcode = int(MECHANIC_OPCODE["HideWhenIdle"])
        for card_id, card_name in enumerate(catalog.names[1:], start=1):
            count = int(catalog.mechanic_count[card_id].item())
            operations = catalog.mechanic_opcode[card_id, :count]
            fade_count = int((operations == fade_opcode).sum().item())
            hide_count = int((operations == hide_opcode).sum().item())
            family_count = fade_count + hide_count
            if family_count == 0:
                continue

            declares[card_id] = True
            stats = loader.get_card(card_name)
            raw = {} if stats is None else (getattr(stats, "_raw_entry", {}) or {})
            character = (
                raw.get("summonCharacterData", {})
                or raw.get("summonSpellData", {})
                or {}
            )
            valid = stats is not None and family_count == 1

            if fade_count == 1 and hide_count == 0:
                delay_ms = _optional_milliseconds(
                    character.get("buffWhenNotAttackingTime")
                )
                valid &= delay_ms is not None and delay_ms > 0
                if valid and delay_ms is not None:
                    visibility_kind[card_id] = FAST_VISIBILITY_FADE_WHEN_IDLE
                    fade_delay[card_id] = _ticks_ceil(delay_ms)
                    fade_use_range[card_id] = bool(
                        character.get("buffWhenNotAttackingUseAttackRange", False)
                    )
                    area_while_invisible[card_id] = bool(
                        getattr(stats, "allow_area_damage_when_invisible", False)
                    )
            elif hide_count == 1 and fade_count == 0:
                raw_hide = character.get("hideTimeMS")
                if raw_hide is None:
                    raw_hide = character.get("hideTimeMs")
                raw_rise = character.get("upTimeMS")
                if raw_rise is None:
                    raw_rise = character.get("upTimeMs")
                hide_ms = _optional_milliseconds(raw_hide)
                rise_ms = _optional_milliseconds(raw_rise)
                valid &= (
                    hide_ms is not None
                    and rise_ms is not None
                    and hide_ms > 0
                    and rise_ms > 0
                )
                if valid and hide_ms is not None and rise_ms is not None:
                    visibility_kind[card_id] = FAST_VISIBILITY_HIDE_WHEN_IDLE
                    hide_delay[card_id] = _ticks_ceil(hide_ms)
                    rise_time[card_id] = _ticks_ceil(rise_ms)
            else:
                valid = False

            if not valid:
                supported[card_id] = False
                visibility_kind[card_id] = FAST_VISIBILITY_UNSUPPORTED
                fade_delay[card_id] = 0
                fade_use_range[card_id] = False
                hide_delay[card_id] = 0
                rise_time[card_id] = 0
                area_while_invisible[card_id] = False

        return cls(
            device=device,
            visibility_kind=visibility_kind,
            declares_visibility=declares,
            profile_supported=supported,
            fade_delay_ticks=fade_delay,
            fade_use_attack_range=fade_use_range,
            hide_delay_ticks=hide_delay,
            rise_time_ticks=rise_time,
            area_receivable_while_invisible=area_while_invisible,
        )


@dataclass(frozen=True)
class FastPolicyMechanicInitialization:
    initialized: torch.Tensor
    invalid_identity: torch.Tensor
    profile_rejected: torch.Tensor


@dataclass(frozen=True)
class FastPolicyVisibilityView:
    current: torch.Tensor
    profile_rejected: torch.Tensor
    invisible: torch.Tensor
    hidden: torch.Tensor
    special_active: torch.Tensor
    target_unavailable: torch.Tensor
    secondary_targetable: torch.Tensor
    direct_effect_receivable: torch.Tensor
    area_receivable: torch.Tensor
    effect_receivable_affects_hidden: torch.Tensor
    combat_blocked: torch.Tensor
    movement_blocked: torch.Tensor


@dataclass(frozen=True)
class FastPolicyVisibilityStep:
    view: FastPolicyVisibilityView
    stale_cleared: torch.Tensor
    became_invisible: torch.Tensor
    became_visible: torch.Tensor
    became_hidden: torch.Tensor
    became_revealed: torch.Tensor
    target_became_unavailable: torch.Tensor
    clear_source_target: torch.Tensor


@dataclass
class FastPolicyMechanicState:
    """Stable-ID-bound mutable visibility state with shape ``[B, E]``."""

    device: torch.device
    bound_stable_id: torch.Tensor
    bound_card_id: torch.Tensor
    visibility_kind: torch.Tensor
    fade_elapsed_ticks: torch.Tensor
    hide_phase_ticks: torch.Tensor
    invisible: torch.Tensor
    hidden: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.bound_stable_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.bound_stable_id.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int,
        device: str | torch.device = "cpu",
    ) -> FastPolicyMechanicState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_entities < 1:
            raise ValueError("max_entities must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_entities)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            bound_stable_id=zeros(torch.int64),
            bound_card_id=zeros(torch.int64),
            visibility_kind=zeros(torch.int8),
            fade_elapsed_ticks=zeros(torch.int32),
            hide_phase_ticks=zeros(torch.int32),
            invisible=zeros(torch.bool),
            hidden=zeros(torch.bool),
        )

    def clone(self) -> FastPolicyMechanicState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def _validate_entity_planes(
        self,
        stable_id: torch.Tensor,
        card_id: torch.Tensor,
        mask: torch.Tensor,
    ) -> None:
        expected = (self.batch_size, self.max_entities)
        for name, value, dtype in (
            ("stable_id", stable_id, torch.int64),
            ("card_id", card_id, torch.int64),
            ("mask", mask, torch.bool),
        ):
            if tuple(value.shape) != expected:
                raise ValueError(f"{name} must have shape [batch, entities]")
            if value.device != self.device:
                raise ValueError(f"{name} must use the state device")
            if value.dtype != dtype:
                raise ValueError(f"{name} must use {dtype}")

    def clear_(self, mask: torch.Tensor) -> None:
        expected = (self.batch_size, self.max_entities)
        if tuple(mask.shape) != expected:
            raise ValueError("mask must have shape [batch, entities]")
        if mask.device != self.device or mask.dtype != torch.bool:
            raise ValueError("mask must be bool on the state device")
        self.bound_stable_id.masked_fill_(mask, 0)
        self.bound_card_id.masked_fill_(mask, 0)
        self.visibility_kind.masked_fill_(mask, FAST_VISIBILITY_NONE)
        self.fade_elapsed_ticks.masked_fill_(mask, 0)
        self.hide_phase_ticks.masked_fill_(mask, 0)
        self.invisible.masked_fill_(mask, False)
        self.hidden.masked_fill_(mask, False)

    def reset_rows_(self, reset_mask: torch.Tensor) -> None:
        if tuple(reset_mask.shape) != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool on the state device")
        self.clear_(reset_mask[:, None].expand(-1, self.max_entities))

    def initialize_spawned_(
        self,
        catalog: FastPolicyMechanicCatalog,
        *,
        stable_id: torch.Tensor,
        card_id: torch.Tensor,
        spawned: torch.Tensor,
    ) -> FastPolicyMechanicInitialization:
        """Bind newly occupied slots and initialize their serialized profile."""

        self._validate_entity_planes(stable_id, card_id, spawned)
        if catalog.device != self.device:
            raise ValueError("catalog and mechanic state must share a device")
        known = (card_id > 0) & (card_id < catalog.size) & (stable_id > 0)
        selected = spawned & known
        invalid = spawned & ~known
        safe_card = card_id.clamp(0, catalog.size - 1)
        kind = catalog.visibility_kind[safe_card]
        rejected = selected & ~catalog.profile_supported[safe_card]
        fade = selected & (kind == FAST_VISIBILITY_FADE_WHEN_IDLE) & ~rejected

        self.bound_stable_id.copy_(
            torch.where(selected, stable_id, self.bound_stable_id)
        )
        self.bound_card_id.copy_(torch.where(selected, card_id, self.bound_card_id))
        self.visibility_kind.copy_(torch.where(selected, kind, self.visibility_kind))
        self.fade_elapsed_ticks.copy_(
            torch.where(
                selected,
                torch.where(fade, catalog.fade_delay_ticks[safe_card], 0),
                self.fade_elapsed_ticks,
            )
        )
        self.hide_phase_ticks.masked_fill_(selected, 0)
        self.invisible.copy_(torch.where(selected, fade, self.invisible))
        self.hidden.masked_fill_(selected, False)
        self.clear_(invalid)
        return FastPolicyMechanicInitialization(
            initialized=selected,
            invalid_identity=invalid,
            profile_rejected=rejected,
        )

    def refresh_identity_(
        self,
        *,
        active: torch.Tensor,
        stable_id: torch.Tensor,
        card_id: torch.Tensor,
    ) -> torch.Tensor:
        """Clear dead, vacated, or reused slots before mechanics advance."""

        self._validate_entity_planes(stable_id, card_id, active)
        occupied = self.bound_stable_id > 0
        current = (
            active
            & occupied
            & (stable_id == self.bound_stable_id)
            & (card_id == self.bound_card_id)
        )
        stale = occupied & ~current
        self.clear_(stale)
        return stale


def _validate_step_plane(
    state: FastPolicyMechanicState,
    name: str,
    value: torch.Tensor,
    dtype: torch.dtype,
) -> None:
    if tuple(value.shape) != (state.batch_size, state.max_entities):
        raise ValueError(f"{name} must have shape [batch, entities]")
    if value.device != state.device:
        raise ValueError(f"{name} must use the state device")
    if value.dtype != dtype:
        raise ValueError(f"{name} must use {dtype}")


def fast_policy_visibility_view(
    catalog: FastPolicyMechanicCatalog,
    state: FastPolicyMechanicState,
    *,
    active: torch.Tensor,
    stable_id: torch.Tensor,
    card_id: torch.Tensor,
) -> FastPolicyVisibilityView:
    """Derive common target/effect/observation planes without mutation."""

    for name, value, dtype in (
        ("active", active, torch.bool),
        ("stable_id", stable_id, torch.int64),
        ("card_id", card_id, torch.int64),
    ):
        _validate_step_plane(state, name, value, dtype)
    if catalog.device != state.device:
        raise ValueError("catalog and mechanic state must share a device")

    bound_current = (
        active
        & (state.bound_stable_id > 0)
        & (state.bound_stable_id == stable_id)
        & (state.bound_card_id == card_id)
    )
    # Card row zero is the intentional neutral identity used by reserved Crown
    # towers and some test/runtime-internal bodies.  It has no declared policy
    # mechanic and therefore follows ordinary target/effect semantics.
    input_known = (stable_id > 0) & (card_id >= 0) & (card_id < catalog.size)
    safe_input_card = card_id.clamp(0, catalog.size - 1)
    declares = catalog.declares_visibility[safe_input_card]
    # Ordinary entities have no retained visibility state to bind.  They must
    # remain targetable and effect-receivable even when a test harness or
    # reserved-tower initializer did not pass through a spawn callback.  A
    # declared visibility profile, by contrast, fails closed until it is bound
    # to the exact stable entity identity.
    ordinary_current = active & input_known & ~declares
    current = bound_current | ordinary_current
    rejected = (
        bound_current & (state.visibility_kind == FAST_VISIBILITY_UNSUPPORTED)
    ) | (active & input_known & declares & ~bound_current)
    invisible = bound_current & state.invisible & ~rejected
    hidden = bound_current & state.hidden & ~rejected
    safe_card = torch.where(
        bound_current,
        state.bound_card_id,
        safe_input_card,
    ).clamp(0, catalog.size - 1)
    direct = current & ~hidden & ~rejected
    area = direct & (~invisible | catalog.area_receivable_while_invisible[safe_card])
    unavailable = invisible | hidden | rejected
    return FastPolicyVisibilityView(
        current=current,
        profile_rejected=rejected,
        invisible=invisible,
        hidden=hidden,
        special_active=hidden,
        target_unavailable=unavailable,
        secondary_targetable=direct,
        direct_effect_receivable=direct,
        area_receivable=area,
        effect_receivable_affects_hidden=current & ~rejected,
        combat_blocked=hidden | rejected,
        movement_blocked=hidden | rejected,
    )


def step_fast_policy_visibility_(
    catalog: FastPolicyMechanicCatalog,
    state: FastPolicyMechanicState,
    *,
    active: torch.Tensor,
    stable_id: torch.Tensor,
    card_id: torch.Tensor,
    deployed: torch.Tensor,
    attack_started: torch.Tensor,
    has_attack_range_target: torch.Tensor,
    has_attack_target: torch.Tensor,
    stunned: torch.Tensor,
) -> FastPolicyVisibilityStep:
    """Advance one 50 ms visibility frame using fixed entity-shaped tensors."""

    for name, value, dtype in (
        ("active", active, torch.bool),
        ("stable_id", stable_id, torch.int64),
        ("card_id", card_id, torch.int64),
        ("deployed", deployed, torch.bool),
        ("attack_started", attack_started, torch.bool),
        ("has_attack_range_target", has_attack_range_target, torch.bool),
        ("has_attack_target", has_attack_target, torch.bool),
        ("stunned", stunned, torch.bool),
    ):
        _validate_step_plane(state, name, value, dtype)

    stale = state.refresh_identity_(
        active=active,
        stable_id=stable_id,
        card_id=card_id,
    )
    before_invisible = state.invisible.clone()
    before_hidden = state.hidden.clone()
    current = (
        active
        & (state.bound_stable_id > 0)
        & (state.bound_stable_id == stable_id)
        & (state.bound_card_id == card_id)
    )
    safe_card = state.bound_card_id.clamp(0, catalog.size - 1)

    fade = (
        current & deployed & (state.visibility_kind == FAST_VISIBILITY_FADE_WHEN_IDLE)
    )
    started = fade & attack_started
    held = fade & catalog.fade_use_attack_range[safe_card] & has_attack_range_target
    state.fade_elapsed_ticks.copy_(
        torch.where(started | held, 0, state.fade_elapsed_ticks)
    )
    state.invisible.copy_(torch.where(started, False, state.invisible))
    advancing_fade = fade & ~started & ~held
    next_fade = state.fade_elapsed_ticks + advancing_fade.to(torch.int32)
    state.fade_elapsed_ticks.copy_(
        torch.where(advancing_fade, next_fade, state.fade_elapsed_ticks)
    )
    fade_complete = fade & (
        state.fade_elapsed_ticks >= catalog.fade_delay_ticks[safe_card]
    )
    state.invisible.copy_(torch.where(fade_complete, True, state.invisible))

    hide = (
        current & deployed & (state.visibility_kind == FAST_VISIBILITY_HIDE_WHEN_IDLE)
    )
    hide_delay = catalog.hide_delay_ticks[safe_card]
    rise_time = catalog.rise_time_ticks[safe_card]
    cycle = (hide_delay + rise_time).clamp(min=1)
    old_phase = state.hide_phase_ticks
    work = (hide & ~stunned).to(torch.int32)
    next_phase = old_phase + work
    no_target = hide & ~has_attack_target & ~stunned
    exact_hide = no_target & (next_phase >= hide_delay) & (old_phase <= hide_delay)
    no_target_phase = torch.where(
        exact_hide,
        hide_delay,
        torch.remainder(next_phase, cycle),
    )
    reverse = has_attack_target & (old_phase < hide_delay)
    target_next = torch.where(reverse, (old_phase - work).clamp(min=0), next_phase)
    fully_up = has_attack_target & ((target_next > cycle) | (old_phase == 0))
    target_phase = torch.where(
        fully_up,
        0,
        torch.remainder(target_next, cycle),
    )
    updated_phase = torch.where(has_attack_target, target_phase, no_target_phase)
    state.hide_phase_ticks.copy_(torch.where(hide & ~stunned, updated_phase, old_phase))
    state.hidden.copy_(
        torch.where(
            current & (state.visibility_kind == FAST_VISIBILITY_HIDE_WHEN_IDLE),
            state.hide_phase_ticks == hide_delay,
            state.hidden,
        )
    )

    view = fast_policy_visibility_view(
        catalog,
        state,
        active=active,
        stable_id=stable_id,
        card_id=card_id,
    )
    became_invisible = view.invisible & ~before_invisible
    became_visible = ~view.invisible & before_invisible & current
    became_hidden = view.hidden & ~before_hidden
    became_revealed = ~view.hidden & before_hidden & current
    became_unavailable = became_invisible | became_hidden | view.profile_rejected
    return FastPolicyVisibilityStep(
        view=view,
        stale_cleared=stale,
        became_invisible=became_invisible,
        became_visible=became_visible,
        became_hidden=became_hidden,
        became_revealed=became_revealed,
        target_became_unavailable=became_unavailable,
        clear_source_target=view.hidden | view.profile_rejected,
    )


__all__ = [
    "FAST_VISIBILITY_FADE_WHEN_IDLE",
    "FAST_VISIBILITY_HIDE_WHEN_IDLE",
    "FAST_VISIBILITY_NONE",
    "FAST_VISIBILITY_UNSUPPORTED",
    "FastPolicyMechanicCatalog",
    "FastPolicyMechanicInitialization",
    "FastPolicyMechanicState",
    "FastPolicyVisibilityStep",
    "FastPolicyVisibilityView",
    "fast_policy_visibility_view",
    "step_fast_policy_visibility_",
]
