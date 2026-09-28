"""Retained tensor lifecycle for serialized kamikaze charge carriers."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.cards.battle_ram import BattleRamCharge
from clasher.mechanics.shared import DeathSpawn

from .movement import integer_sqrt_tensor, movement_component_vector_units
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorChargeCarrierCatalog:
    supported: torch.Tensor
    base_speed_units: torch.Tensor
    charged_speed_units: torch.Tensor
    charge_range_units: torch.Tensor
    attack_range_units: torch.Tensor
    sight_range_units: torch.Tensor
    damage: torch.Tensor
    charged_damage: torch.Tensor
    kamikaze_delay_ms: torch.Tensor
    child_count: torch.Tensor
    child_deploy_ms: torch.Tensor
    child_spawn_radius_units: torch.Tensor
    child_terminal_knockback_units: torch.Tensor
    child_is_timed: torch.Tensor
    child_name: tuple[str, ...]


@dataclass(frozen=True)
class ChargeChildHandoff:
    valid: torch.Tensor
    parent_entity_id: torch.Tensor
    parent_slot: torch.Tensor
    parent_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    child_count: torch.Tensor
    child_deploy_ms: torch.Tensor
    child_spawn_radius_units: torch.Tensor
    child_terminal_knockback_units: torch.Tensor
    child_is_timed: torch.Tensor


@dataclass(frozen=True)
class ChargeCarrierStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    acquired_target_id: torch.Tensor
    moved: torch.Tensor
    impacted: torch.Tensor
    damage: torch.Tensor
    carrier_death: torch.Tensor
    handoff: ChargeChildHandoff


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    batch = destination.batch_size
    for left_owner, right_owner in (
        (destination.battle, source.battle),
        (destination.battle.rng, source.battle.rng),
        (destination.status, source.status),
        (destination.phases, source.phases),
        (destination.events, source.events),
    ):
        for descriptor in fields(left_owner):  # type: ignore[arg-type]
            left = getattr(left_owner, descriptor.name)
            right = getattr(right_owner, descriptor.name)
            if (
                isinstance(left, torch.Tensor)
                and isinstance(right, torch.Tensor)
                and left.shape == right.shape
                and left.ndim > 0
                and left.shape[0] == batch
            ):
                left[rows] = right[rows]
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


@dataclass
class TensorResidentChargeCarriers:
    catalog: TensorChargeCarrierCatalog
    tracked_entity_id: torch.Tensor
    charge_progress: torch.Tensor
    charging: torch.Tensor
    target_slot: torch.Tensor
    target_entity_id: torch.Tensor
    kamikaze_primed: torch.Tensor
    kamikaze_remaining_ms: torch.Tensor
    charge_used: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.tracked_entity_id.device

    @property
    def batch_size(self) -> int:
        return int(self.tracked_entity_id.shape[0])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorResidentChargeCarriers:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match charge-carrier runtime")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = plane(torch.bool)
        speed = plane(torch.int64)
        charged_speed = plane(torch.int64)
        charge_range = plane(torch.int64)
        attack_range = plane(torch.int64)
        sight_range = plane(torch.int64)
        damage = plane(torch.float64)
        special_damage = plane(torch.float64)
        kamikaze = plane(torch.int64)
        child_count = plane(torch.int64)
        child_deploy = plane(torch.int64)
        child_radius = plane(torch.int64)
        child_knockback = plane(torch.int64)
        child_timed = plane(torch.bool)
        child_names = [""] * size
        definitions = battles[0].card_loader.load_card_definitions()
        for card_id, name in enumerate(runtime.battle.card_names):
            stats = battles[0].card_loader.get_card(name) if name else None
            definition = definitions.get(name)
            if stats is None or definition is None:
                continue
            charges = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, BattleRamCharge)
            ]
            spawns = [
                mechanic
                for mechanic in definition.mechanics
                if isinstance(mechanic, DeathSpawn)
            ]
            if len(charges) != 1 or len(spawns) != 1:
                continue
            raw = getattr(stats, "_raw_entry", {}) or {}
            character = raw.get("summonCharacterData", {}) or {}
            child = spawns[0]
            base_speed = round(float(stats.speed or 0))
            multiplier = float(character.get("chargeSpeedMultiplier", 100) or 100)
            ordinary_damage = stats.scaled_damage or stats.damage or 0
            charged = (
                stats.scaled_damage_special or stats.damage_special or ordinary_damage
            )
            child_data = child.unit_data or {}
            supported[card_id] = True
            speed[card_id] = base_speed
            charged_speed[card_id] = round(base_speed * multiplier / 100.0)
            charge_range[card_id] = round(float(stats.charge_range or 0))
            attack_range[card_id] = round(float(stats.range or 0) * 1_000)
            sight_range[card_id] = round(float(stats.sight_range or 0) * 1_000)
            damage[card_id] = float(ordinary_damage)
            special_damage[card_id] = float(charged)
            kamikaze[card_id] = int(character.get("kamikazeTime", 0) or 0)
            child_count[card_id] = int(child.count)
            child_deploy[card_id] = int(child.deploy_time_ms)
            child_radius[card_id] = round(float(child.radius_tiles) * 1_000)
            child_knockback[card_id] = int(child_data.get("deathPushback", 0) or 0)
            child_timed[card_id] = bool(
                not child_data.get("hitpoints")
                and (
                    child_data.get("deathDamage") is not None
                    or child_data.get("deathAreaEffectData")
                )
            )
            child_names[card_id] = child.unit_name

        shape = runtime.battle.entity_id.shape
        core = runtime.battle
        cards = core.entity_card.clamp(0, size - 1)
        tracked = torch.where(
            runtime.entity_pool.active & core.entity_active & supported[cards],
            core.entity_id,
            0,
        )
        return cls(
            TensorChargeCarrierCatalog(
                supported,
                speed,
                charged_speed,
                charge_range,
                attack_range,
                sight_range,
                damage,
                special_damage,
                kamikaze,
                child_count,
                child_deploy,
                child_radius,
                child_knockback,
                child_timed,
                tuple(child_names),
            ),
            tracked,
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.full(shape, -1, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.bool, device=device),
        )

    def clone(self) -> TensorResidentChargeCarriers:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentChargeCarriers:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("charge-carrier fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentChargeCarriers,
        source_rows: torch.Tensor | list[int] | None = None,
    ) -> None:
        destination = torch.as_tensor(
            destination_rows, dtype=torch.int64, device=self.device
        )
        selected = (
            torch.arange(destination.numel(), dtype=torch.int64, device=self.device)
            if source_rows is None
            else torch.as_tensor(source_rows, dtype=torch.int64, device=self.device)
        )
        if destination.shape != selected.shape or source.device != self.device:
            raise ValueError("charge-carrier reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(
        self, source: TensorResidentChargeCarriers, rows: torch.Tensor
    ) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> ChargeCarrierStepResult:
        if dt_ms != 50:
            raise ValueError("charge-carrier runtime requires one 50ms logic tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("charge-carrier battle_mask must have shape [batch]")
        active_count = ((self.tracked_entity_id > 0) & selected[:, None]).sum(
            dim=1, dtype=torch.int64
        )
        event_free = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (active_count * 2 > event_free)
        supported = selected & ~capacity_rejected
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        core = working_runtime.battle
        rows = torch.arange(self.batch_size, device=self.device)
        cards = core.entity_card.clamp(0, len(self.catalog.supported) - 1)
        live_supported = (
            working_runtime.entity_pool.active
            & core.entity_active
            & working.catalog.supported[cards]
        )
        identity = working.tracked_entity_id == core.entity_id
        stale = (working.tracked_entity_id > 0) & ~(live_supported & identity)
        new = live_supported & ((working.tracked_entity_id == 0) | ~identity)
        deployed_before = (core.entity_deploy_delay <= 1e-9) & (
            ~core.entity_placement_pending
        )
        working.tracked_entity_id.masked_fill_(stale, 0)
        working.charge_progress.masked_fill_(stale, 0)
        working.charging.masked_fill_(stale, False)
        working.target_slot.masked_fill_(stale, -1)
        working.target_entity_id.masked_fill_(stale, 0)
        working.kamikaze_primed.masked_fill_(stale, False)
        working.kamikaze_remaining_ms.masked_fill_(stale, 0)
        working.charge_used.masked_fill_(stale, False)
        working.tracked_entity_id.copy_(
            torch.where(new, core.entity_id, working.tracked_entity_id)
        )

        carrier_order = working_runtime.entity_pool.id_order(
            live_supported & supported[:, None]
        )
        moved = torch.zeros_like(core.entity_active)
        impacted = torch.zeros_like(core.entity_active)
        carrier_death = torch.zeros_like(core.entity_active)
        damage_result = torch.zeros_like(core.entity_hp)
        handoff_valid = torch.zeros_like(core.entity_active)
        for rank in range(runtime.max_entities):
            carrier_valid = carrier_order.valid[:, rank]
            carrier_slot = carrier_order.slots[:, rank].clamp_min(0)
            card = cards.gather(1, carrier_slot[:, None])[:, 0]
            player = core.entity_player.gather(1, carrier_slot[:, None])[:, 0]
            deployed = deployed_before.gather(1, carrier_slot[:, None])[:, 0]
            candidates = (
                working_runtime.entity_pool.active
                & core.entity_active
                & (core.entity_player != player[:, None])
                & (core.entity_kind == 1)
            )
            carrier_x = core.entity_x_units.gather(1, carrier_slot[:, None])[:, 0].to(
                torch.int64
            )
            carrier_y = core.entity_y_units.gather(1, carrier_slot[:, None])[:, 0].to(
                torch.int64
            )
            dx = core.entity_x_units.to(torch.int64) - carrier_x[:, None]
            dy = core.entity_y_units.to(torch.int64) - carrier_y[:, None]
            distance_sq = dx * dx + dy * dy
            target_catalog = working_runtime.card_catalog_index[
                core.entity_card
            ].clamp_min(0)
            target_radius_all = working_runtime.catalog.collision_radius_units[
                target_catalog
            ].to(torch.int64)
            sight_reach = (
                working.catalog.sight_range_units[card, None] + target_radius_all
            )
            candidates &= distance_sq <= sight_reach * sight_reach
            key = torch.where(
                candidates,
                distance_sq * (core.entity_id.amax().clamp_min(1) + 1) + core.entity_id,
                torch.iinfo(torch.int64).max,
            )
            acquired = key.argmin(dim=1)
            found = candidates.any(dim=1) & carrier_valid & deployed
            retained_slot = working.target_slot.gather(1, carrier_slot[:, None])[:, 0]
            retained_id = working.target_entity_id.gather(1, carrier_slot[:, None])[
                :, 0
            ]
            retained_safe = retained_slot.clamp(0, runtime.max_entities - 1)
            retained_valid = (
                (retained_slot >= 0)
                & working_runtime.entity_pool.active[rows, retained_safe]
                & core.entity_active[rows, retained_safe]
                & (core.entity_id[rows, retained_safe] == retained_id)
                & (core.entity_kind[rows, retained_safe] == 1)
                & (core.entity_player[rows, retained_safe] != player)
            )
            target_slot = torch.where(retained_valid, retained_safe, acquired)
            target_valid = found | retained_valid
            selected_carrier = carrier_valid & deployed & target_valid
            working.target_slot[
                rows[selected_carrier], carrier_slot[selected_carrier]
            ] = target_slot[selected_carrier]
            working.target_entity_id[
                rows[selected_carrier], carrier_slot[selected_carrier]
            ] = core.entity_id[rows[selected_carrier], target_slot[selected_carrier]]
            target_x = core.entity_x_units[rows, target_slot].to(torch.int64)
            target_y = core.entity_y_units[rows, target_slot].to(torch.int64)
            delta = torch.stack((target_x - carrier_x, target_y - carrier_y), dim=-1)
            distance = integer_sqrt_tensor((delta * delta).sum(dim=-1))
            catalog_index = working_runtime.card_catalog_index[
                core.entity_card[rows, target_slot]
            ].clamp_min(0)
            target_radius = working_runtime.catalog.collision_radius_units[
                catalog_index
            ].to(torch.int64)
            reach = working.catalog.attack_range_units[card] + target_radius
            in_reach = selected_carrier & (distance <= reach)
            can_move = (
                selected_carrier
                & ~in_reach
                & ~working.kamikaze_primed[rows, carrier_slot]
            )
            was_charging = working.charging[rows, carrier_slot]
            speed = torch.where(
                was_charging,
                working.catalog.charged_speed_units[card],
                working.catalog.base_speed_units[card],
            )
            work = torch.minimum(speed, distance)
            displacement = movement_component_vector_units(delta, work)
            core.entity_x_units[rows[can_move], carrier_slot[can_move]] += displacement[
                can_move, 0
            ].to(torch.int32)
            core.entity_y_units[rows[can_move], carrier_slot[can_move]] += displacement[
                can_move, 1
            ].to(torch.int32)
            moved[rows[can_move], carrier_slot[can_move]] = True
            charge_range = working.catalog.charge_range_units[card]
            progress_add = torch.where(
                charge_range > 0,
                torch.div(
                    10_000 * torch.div(work, 10, rounding_mode="floor"),
                    charge_range.clamp_min(1),
                    rounding_mode="floor",
                ),
                0,
            )
            next_progress = working.charge_progress[rows, carrier_slot] + progress_add
            next_progress = torch.where(
                working.charge_progress[rows, carrier_slot] <= 9_999,
                next_progress,
                working.charge_progress[rows, carrier_slot],
            )
            working.charge_progress[rows[can_move], carrier_slot[can_move]] = (
                next_progress[can_move]
            )
            working.charging[rows[can_move], carrier_slot[can_move]] = (
                next_progress[can_move] >= 10_000
            ) & (charge_range[can_move] > 0)

            immediate = in_reach & (working.catalog.kamikaze_delay_ms[card] == 0)
            prime = (
                in_reach
                & (working.catalog.kamikaze_delay_ms[card] > 0)
                & ~working.kamikaze_primed[rows, carrier_slot]
            )
            working.kamikaze_primed[rows[prime], carrier_slot[prime]] = True
            working.kamikaze_remaining_ms[rows[prime], carrier_slot[prime]] = (
                working.catalog.kamikaze_delay_ms[card[prime]]
            )
            ticking = in_reach & working.kamikaze_primed[rows, carrier_slot] & ~prime
            remaining = working.kamikaze_remaining_ms[rows, carrier_slot] - dt_ms
            working.kamikaze_remaining_ms[rows[ticking], carrier_slot[ticking]] = (
                remaining[ticking].clamp_min(0)
            )
            delayed = ticking & (remaining <= 0)
            demolition = (immediate | delayed) & ~working.charge_used[
                rows, carrier_slot
            ]
            amount = torch.where(
                was_charging,
                working.catalog.charged_damage[card],
                working.catalog.damage[card],
            )
            damage_hit = demolition & (amount > 0)
            old_hp = core.entity_hp[rows, target_slot]
            applied = torch.minimum(old_hp, amount)
            next_hp = torch.clamp(old_hp - amount, min=0.0)
            core.entity_hp[rows[damage_hit], target_slot[damage_hit]] = next_hp[
                damage_hit
            ]
            core.entity_hp_integer_kind[rows[damage_hit], target_slot[damage_hit]] = (
                False
            )
            killed_target = damage_hit & (next_hp <= 0)
            core.entity_active[rows[killed_target], target_slot[killed_target]] = False
            damage_result[rows[damage_hit], target_slot[damage_hit]] = applied[
                damage_hit
            ]
            core.entity_hp[rows[demolition], carrier_slot[demolition]] = 0.0
            core.entity_hp_integer_kind[rows[demolition], carrier_slot[demolition]] = (
                False
            )
            core.entity_active[rows[demolition], carrier_slot[demolition]] = False
            working_runtime.phases.death_pending[
                rows[demolition], carrier_slot[demolition]
            ] = True
            working.charge_used[rows[demolition], carrier_slot[demolition]] = True
            impacted[rows[demolition], carrier_slot[demolition]] = True
            carrier_death[rows[demolition], carrier_slot[demolition]] = True
            handoff_valid[rows[demolition], carrier_slot[demolition]] = True
            event_valid = torch.stack((damage_hit, demolition), dim=1)
            working_runtime.events.append(
                phase=TickPhase.COMBAT,
                opcode=torch.stack(
                    (
                        torch.full_like(card, RuntimeEventOpcode.DAMAGE),
                        torch.full_like(card, RuntimeEventOpcode.DEATH),
                    ),
                    dim=1,
                ),
                valid=event_valid,
                source_id=core.entity_id[rows, carrier_slot, None].expand(-1, 2),
                target_id=torch.stack(
                    (
                        core.entity_id[rows, target_slot],
                        core.entity_id[rows, carrier_slot],
                    ),
                    dim=1,
                ),
                x_units=torch.stack((target_x, carrier_x), dim=1),
                y_units=torch.stack((target_y, carrier_y), dim=1),
                amount=torch.stack((applied, torch.zeros_like(applied)), dim=1),
                payload=card[:, None],
            )

        deploying = (
            live_supported & supported[:, None] & ~deployed_before & core.entity_active
        )
        deploy_after = torch.clamp(
            core.entity_deploy_delay - dt_ms / 1_000.0,
            min=0.0,
        )
        core.entity_deploy_delay.copy_(
            torch.where(deploying, deploy_after, core.entity_deploy_delay)
        )
        deploy_complete = deploying & (deploy_after <= 1e-9)
        core.entity_placement_pending &= ~deploy_complete
        core.entity_spawn_hook_pending &= ~deploy_complete
        core.entity_spawn_hook_fired |= deploy_complete

        committed = supported
        working_runtime.mark_dirty(committed, phase=TickPhase.COMBAT)
        _copy_runtime_rows_(runtime, working_runtime, committed)
        self._copy_rows_(working, committed)
        source_card = core.entity_card
        return ChargeCarrierStepResult(
            committed=~selected | committed,
            capacity_rejected=capacity_rejected,
            acquired_target_id=torch.where(
                committed[:, None], self.target_entity_id, 0
            ),
            moved=moved & committed[:, None],
            impacted=impacted & committed[:, None],
            damage=torch.where(committed[:, None], damage_result, 0.0),
            carrier_death=carrier_death & committed[:, None],
            handoff=ChargeChildHandoff(
                valid=handoff_valid & committed[:, None],
                parent_entity_id=runtime.battle.entity_id.clone(),
                parent_slot=torch.arange(runtime.max_entities, device=self.device)[
                    None, :
                ].expand(self.batch_size, -1),
                parent_card_id=source_card.clone(),
                x_units=runtime.battle.entity_x_units.clone(),
                y_units=runtime.battle.entity_y_units.clone(),
                child_count=self.catalog.child_count[source_card],
                child_deploy_ms=self.catalog.child_deploy_ms[source_card],
                child_spawn_radius_units=self.catalog.child_spawn_radius_units[
                    source_card
                ],
                child_terminal_knockback_units=(
                    self.catalog.child_terminal_knockback_units[source_card]
                ),
                child_is_timed=self.catalog.child_is_timed[source_card],
            ),
        )


__all__ = [
    "ChargeCarrierStepResult",
    "ChargeChildHandoff",
    "TensorChargeCarrierCatalog",
    "TensorResidentChargeCarriers",
]
