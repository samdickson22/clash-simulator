"""Retained tensor runtime for serialized Royal Delivery payloads.

The universal pending-spell owner hands due commands to this module.  A due
command allocates the falling carrier immediately; object ticks retain its
2050 ms fall, resolve ID-ordered impact damage, then allocate the serialized
Recruit after damage/death state is visible.  No Python entity is stepped on
the runtime path.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.kinematics import tiles_per_second_to_logic_speed, tiles_to_logic_units
from clasher.spells import SPELL_REGISTRY, RoyalDeliverySpell
from clasher.unit_traits import is_knockback_immune

from .movement import normalized_vector_units
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorRoyalDeliveryCatalog:
    supported: torch.Tensor
    impact_delay_ms: torch.Tensor
    travel_speed_units: torch.Tensor
    radius_units: torch.Tensor
    damage: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    ignore_buildings: torch.Tensor
    pushback_units: torch.Tensor
    pushback_ignores_mass: torch.Tensor
    spawn_count: torch.Tensor
    child_core_card: torch.Tensor
    child_hitpoints: torch.Tensor
    child_damage: torch.Tensor
    child_collision_radius_units: torch.Tensor
    child_deploy_delay: torch.Tensor
    child_shield_hitpoints: torch.Tensor
    knockback_immune_catalog: torch.Tensor


@dataclass(frozen=True)
class RoyalDeliveryMaterializeResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    carrier_entity_id: torch.Tensor
    capacity_rejected: torch.Tensor
    unsupported: torch.Tensor


@dataclass(frozen=True)
class RoyalDeliveryStepResult:
    committed: torch.Tensor
    impacted: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor
    spawned_count: torch.Tensor
    pushback_active: torch.Tensor


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


def _clear_entity_slots_(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
    core = runtime.battle
    for descriptor in fields(core):
        value = getattr(core, descriptor.name)
        if (
            isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == mask.shape
            and descriptor.name.startswith("entity_")
            and descriptor.name != "entity_id"
        ):
            expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
            if descriptor.name == "entity_tower_slot":
                value.masked_fill_(expanded, -1)
            else:
                value.masked_fill_(expanded, 0)
    for owner in (runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == mask.shape
            ):
                expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
                if descriptor.name == "target_slot":
                    value.masked_fill_(expanded, -1)
                else:
                    value.masked_fill_(expanded, 0)
    core.entity_id.copy_(runtime.entity_pool.entity_id)


@dataclass
class TensorResidentRoyalDelivery:
    """Mutable falling carriers and impact-owned child/effect state."""

    catalog: TensorRoyalDeliveryCatalog
    active: torch.Tensor
    entity_slot: torch.Tensor
    entity_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    remaining_ms: torch.Tensor
    elapsed_ms: torch.Tensor
    travel_work_units: torch.Tensor
    shield_hitpoints: torch.Tensor
    pushback_active: torch.Tensor
    pushback_target_units: torch.Tensor
    pushback_velocity_work: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.active.device

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        capacity: int = 4,
    ) -> TensorResidentRoyalDelivery:
        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match Royal Delivery runtime")
        if capacity < 1:
            raise ValueError("Royal Delivery capacity must be positive")
        device = runtime.device
        child_names = {
            spell.spawn_character
            for name in runtime.battle.card_names
            if isinstance((spell := SPELL_REGISTRY.get(name)), RoyalDeliverySpell)
        }
        current_names = runtime.battle.card_names
        expanded_names = ("", *sorted(set(current_names[1:]) | child_names))
        if expanded_names != current_names:
            expanded_to_id = {name: index for index, name in enumerate(expanded_names)}
            old_to_new = torch.tensor(
                [expanded_to_id[name] for name in current_names],
                dtype=torch.int64,
                device=device,
            )
            for name in ("hand", "deck", "cycle_queue", "entity_card"):
                value = getattr(runtime.battle, name)
                value.copy_(old_to_new[value])
            runtime.battle.card_names = expanded_names
            runtime.battle.card_to_id = expanded_to_id
            runtime.card_catalog_index = torch.tensor(
                [
                    runtime.catalog.name_to_id.get(name, -1) if name else 0
                    for name in expanded_names
                ],
                dtype=torch.int64,
                device=device,
            )
        core_count = len(runtime.battle.card_names)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(core_count, dtype=dtype, device=device)

        supported = zeros(torch.bool)
        delay = zeros(torch.int64)
        speed = zeros(torch.int64)
        radius = zeros(torch.int64)
        damage = zeros(torch.float64)
        hits_air = zeros(torch.bool)
        hits_ground = zeros(torch.bool)
        ignore_buildings = zeros(torch.bool)
        pushback = zeros(torch.int64)
        pushback_all = zeros(torch.bool)
        spawn_count = zeros(torch.int64)
        child_core = torch.full((core_count,), -1, dtype=torch.int64, device=device)
        child_hp = zeros(torch.float64)
        child_damage = zeros(torch.float64)
        child_radius = zeros(torch.int64)
        child_delay = zeros(torch.float64)
        child_shield = zeros(torch.float64)

        for core_id, name in enumerate(runtime.battle.card_names):
            spell = SPELL_REGISTRY.get(name)
            if not isinstance(spell, RoyalDeliverySpell):
                continue
            child_id = runtime.battle.card_to_id.get(spell.spawn_character, -1)
            if child_id < 0 or not spell.spawn_character_data:
                continue
            child_stats = troop_from_character_data(
                spell.spawn_character,
                spell.spawn_character_data,
                elixir=0,
                rarity=str(spell.spawn_character_data.get("rarity", "Common")),
            )
            raw = getattr(child_stats, "card_definition", None)
            shield = 0.0
            if raw is not None:
                for mechanic in raw.mechanics:
                    raw_shield = getattr(mechanic, "shield_hp", None)
                    if raw_shield is not None:
                        scaled_shield = child_stats.get_scaled_stat(raw_shield)
                        shield = 0.0 if scaled_shield is None else float(scaled_shield)
                        break
            raw_entry = battles[0].card_loader.get_card(name)
            area_data = (
                getattr(raw_entry, "_raw_entry", {}).get("areaEffectObjectData", {})
                if raw_entry is not None
                else {}
            )
            projectile = area_data.get("projectileData", {})
            supported[core_id] = True
            delay[core_id] = round(spell.impact_delay * 1_000.0)
            speed[core_id] = tiles_per_second_to_logic_speed(spell.travel_speed)
            radius[core_id] = tiles_to_logic_units(spell.radius)
            damage[core_id] = float(spell.damage)
            hits_air[core_id] = bool(projectile.get("hitsAir", True))
            hits_ground[core_id] = bool(projectile.get("hitsGround", True))
            ignore_buildings[core_id] = bool(spell.ignore_buildings)
            pushback[core_id] = int(projectile.get("pushback", 0) or 0)
            pushback_all[core_id] = bool(projectile.get("pushbackAll", False))
            spawn_count[core_id] = int(spell.spawn_count)
            child_core[core_id] = child_id
            child_hp[core_id] = float(child_stats.scaled_hitpoints)
            child_damage[core_id] = float(child_stats.scaled_damage)
            child_radius[core_id] = tiles_to_logic_units(
                float(child_stats.collision_radius or 0.5)
            )
            child_delay[core_id] = float(spell.spawn_deploy_delay)
            child_shield[core_id] = shield

        immune = torch.zeros(
            len(runtime.catalog.names), dtype=torch.bool, device=device
        )
        loader = battles[0].card_loader
        for catalog_id, name in enumerate(runtime.catalog.names):
            stats = loader.get_card(name) if name else None
            immune[catalog_id] = bool(stats and is_knockback_immune(stats))

        shape = (runtime.batch_size, capacity)
        entity_shape = (runtime.batch_size, runtime.max_entities)
        return cls(
            catalog=TensorRoyalDeliveryCatalog(
                supported=supported,
                impact_delay_ms=delay,
                travel_speed_units=speed,
                radius_units=radius,
                damage=damage,
                hits_air=hits_air,
                hits_ground=hits_ground,
                ignore_buildings=ignore_buildings,
                pushback_units=pushback,
                pushback_ignores_mass=pushback_all,
                spawn_count=spawn_count,
                child_core_card=child_core,
                child_hitpoints=child_hp,
                child_damage=child_damage,
                child_collision_radius_units=child_radius,
                child_deploy_delay=child_delay,
                child_shield_hitpoints=child_shield,
                knockback_immune_catalog=immune,
            ),
            active=torch.zeros(shape, dtype=torch.bool, device=device),
            entity_slot=torch.full(shape, -1, dtype=torch.int64, device=device),
            entity_id=torch.zeros(shape, dtype=torch.int64, device=device),
            card_id=torch.zeros(shape, dtype=torch.int64, device=device),
            player_id=torch.zeros(shape, dtype=torch.int8, device=device),
            target_x_units=torch.zeros(shape, dtype=torch.int32, device=device),
            target_y_units=torch.zeros(shape, dtype=torch.int32, device=device),
            remaining_ms=torch.zeros(shape, dtype=torch.int64, device=device),
            elapsed_ms=torch.zeros(shape, dtype=torch.int64, device=device),
            travel_work_units=torch.zeros(shape, dtype=torch.int64, device=device),
            shield_hitpoints=torch.zeros(
                entity_shape, dtype=torch.float64, device=device
            ),
            pushback_active=torch.zeros(entity_shape, dtype=torch.bool, device=device),
            pushback_target_units=torch.zeros(
                (*entity_shape, 2), dtype=torch.int64, device=device
            ),
            pushback_velocity_work=torch.zeros(
                entity_shape, dtype=torch.int64, device=device
            ),
        )

    def clone(self) -> TensorResidentRoyalDelivery:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | list[int]) -> TensorResidentRoyalDelivery:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("Royal Delivery fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | list[int],
        source: TensorResidentRoyalDelivery,
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
        if selected.shape != destination.shape or source.device != self.device:
            raise ValueError("Royal Delivery reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(
        self, source: TensorResidentRoyalDelivery, rows: torch.Tensor
    ) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def materialize_due_spell_actions_(
        self,
        runtime: TensorBattleRuntime,
        *,
        card_ids: torch.Tensor,
        player_ids: torch.Tensor,
        target_x_units: torch.Tensor,
        target_y_units: torch.Tensor,
        valid: torch.Tensor,
    ) -> RoyalDeliveryMaterializeResult:
        """Consume one due command per row with whole-row rollback."""

        shape = (self.batch_size,)
        values = (card_ids, player_ids, target_x_units, target_y_units, valid)
        if any(value.shape != shape for value in values):
            raise ValueError("Royal Delivery due planes must have shape [batch]")
        raw_cards = card_ids.to(self.device, torch.int64)
        card_in_range = (raw_cards >= 0) & (raw_cards < len(self.catalog.supported))
        cards = raw_cards.clamp(0, len(self.catalog.supported) - 1)
        requested = valid.to(self.device, torch.bool)
        unsupported = requested & (~card_in_range | ~self.catalog.supported[cards])
        carrier_free = (~self.active).any(dim=1)
        entity_free = (~runtime.entity_pool.active).sum(dim=1) >= 1
        event_free = runtime.events.count.to(torch.int64) < runtime.events.capacity
        capacity_rejected = requested & ~(carrier_free & entity_free & event_free)
        accepted = requested & ~unsupported & ~capacity_rejected

        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        allocation = working_runtime.entity_pool.allocate(accepted.to(torch.int64))
        runtime_slot = allocation.slots[:, 0].clamp_min(0)
        allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
        allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
        _clear_entity_slots_(working_runtime, allocated_mask)
        carrier_slot = (~working.active).to(torch.int64).argmax(dim=1)
        rows = torch.arange(self.batch_size, device=self.device)
        selected_rows = rows[accepted]
        selected_carriers = carrier_slot[accepted]
        selected_runtime = runtime_slot[accepted]
        selected_cards = cards[accepted]
        selected_ids = allocation.entity_ids[:, 0][accepted]
        working.active[selected_rows, selected_carriers] = True
        working.entity_slot[selected_rows, selected_carriers] = selected_runtime
        working.entity_id[selected_rows, selected_carriers] = selected_ids
        working.card_id[selected_rows, selected_carriers] = selected_cards
        working.player_id[selected_rows, selected_carriers] = player_ids[accepted].to(
            torch.int8
        )
        working.target_x_units[selected_rows, selected_carriers] = target_x_units[
            accepted
        ].to(torch.int32)
        working.target_y_units[selected_rows, selected_carriers] = target_y_units[
            accepted
        ].to(torch.int32)
        working.remaining_ms[selected_rows, selected_carriers] = (
            self.catalog.impact_delay_ms[selected_cards]
        )
        core = working_runtime.battle
        index = (selected_rows, selected_runtime)
        working.shield_hitpoints[index] = 0.0
        working.pushback_active[index] = False
        working.pushback_target_units[index] = 0
        working.pushback_velocity_work[index] = 0
        core.entity_active[index] = True
        core.entity_kind[index] = 2
        core.entity_player[index] = player_ids[accepted].to(torch.int8)
        # SpawnProjectile carriers have no public card_stats in the scalar
        # runtime.  The retained owner keeps the serialized spell blueprint in
        # ``working.card_id`` until impact and child materialization.
        core.entity_card[index] = 0
        core.entity_x_units[index] = target_x_units[accepted].to(torch.int32)
        core.entity_y_units[index] = target_y_units[accepted].to(torch.int32)
        core.entity_hp[index] = 1.0
        core.entity_hp_integer_kind[index] = True
        core.entity_max_hp[index] = 1.0
        working_runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.PROJECTILE,
            valid=allocation.valid,
            source_id=torch.zeros_like(allocation.entity_ids),
            target_id=allocation.entity_ids,
            x_units=core.entity_x_units.gather(1, allocation.slots.clamp_min(0)),
            y_units=core.entity_y_units.gather(1, allocation.slots.clamp_min(0)),
            payload=cards[:, None],
        )
        working_runtime.mark_dirty(accepted, phase=TickPhase.COMMANDS)
        _copy_runtime_rows_(runtime, working_runtime, accepted)
        self._copy_rows_(working, accepted)
        return RoyalDeliveryMaterializeResult(
            committed=~requested | accepted,
            accepted=accepted,
            carrier_entity_id=torch.where(
                accepted, allocation.entity_ids[:, 0], torch.zeros_like(cards)
            ),
            capacity_rejected=capacity_rejected,
            unsupported=unsupported,
        )

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: torch.Tensor | int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> RoyalDeliveryStepResult:
        """Advance falling carriers and resolve due impacts atomically by row."""

        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("Royal Delivery battle_mask must have shape [batch]")
        dt = torch.as_tensor(dt_ms, dtype=torch.int64, device=self.device)
        if dt.ndim == 0:
            dt = dt.expand(self.batch_size)
        if dt.shape != (self.batch_size,) or bool((dt < 0).any().item()):
            raise ValueError("Royal Delivery dt_ms must be non-negative [batch]")

        decremented = torch.clamp(self.remaining_ms - dt[:, None], min=0)
        due = self.active & selected[:, None] & (decremented == 0)
        impact_rows = due.any(dim=1)
        core = runtime.battle
        catalog_index = runtime.card_catalog_index[core.entity_card].clamp_min(0)
        target_radius = runtime.catalog.collision_radius_units[catalog_index].to(
            torch.int64
        )
        target_air = runtime.catalog.is_air_unit[catalog_index]
        maximum_hits = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        for carrier_rank in range(self.capacity):
            card = self.card_id[:, carrier_rank].clamp_min(0)
            dx = (
                core.entity_x_units.to(torch.int64)
                - self.target_x_units[:, carrier_rank, None]
            )
            dy = (
                core.entity_y_units.to(torch.int64)
                - self.target_y_units[:, carrier_rank, None]
            )
            reach = self.catalog.radius_units[card, None] + target_radius
            eligible = (
                due[:, carrier_rank, None]
                & runtime.entity_pool.active
                & core.entity_active
                & (core.entity_player != self.player_id[:, carrier_rank, None])
                & (
                    (core.entity_kind == 0)
                    | (
                        ~self.catalog.ignore_buildings[card, None]
                        & (core.entity_kind == 1)
                    )
                )
                & torch.where(
                    target_air,
                    self.catalog.hits_air[card, None],
                    self.catalog.hits_ground[card, None],
                )
                & (dx * dx + dy * dy < reach * reach)
            )
            maximum_hits += eligible.sum(dim=1, dtype=torch.int64)
        spawn_needed = torch.zeros_like(maximum_hits)
        for carrier_rank in range(self.capacity):
            spawn_needed += (
                due[:, carrier_rank].to(torch.int64)
                * self.catalog.spawn_count[self.card_id[:, carrier_rank].clamp_min(0)]
            )
        free_entities = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = impact_rows & (
            (spawn_needed > free_entities)
            | (maximum_hits * 2 + spawn_needed > free_events)
        )
        supported = selected & ~capacity_rejected
        committed = ~selected | supported

        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        working.remaining_ms.copy_(
            torch.where(
                (working.active & supported[:, None]), decremented, working.remaining_ms
            )
        )
        working.elapsed_ms.add_(
            torch.where(working.active & supported[:, None], dt[:, None], 0)
        )
        speed = self.catalog.travel_speed_units[working.card_id.clamp_min(0)]
        working.travel_work_units.add_(
            torch.where(working.active & supported[:, None], speed, 0)
        )
        damage_result = torch.zeros_like(core.entity_hp)
        death_result = torch.zeros_like(core.entity_active)
        spawned_count = torch.zeros(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        rows = torch.arange(self.batch_size, device=self.device)

        order_keys = torch.where(
            working.active, working.entity_id, torch.iinfo(torch.int64).max
        )
        carrier_order = torch.argsort(order_keys, dim=1, stable=True)
        carrier_cleanup = torch.zeros_like(working_runtime.entity_pool.active)
        for rank in range(self.capacity):
            carrier_slot = carrier_order[:, rank]
            card = working.card_id.gather(1, carrier_slot[:, None])[:, 0].clamp_min(0)
            carrier_due = due.gather(1, carrier_slot[:, None])[:, 0] & supported
            player = working.player_id.to(torch.int64).gather(1, carrier_slot[:, None])[
                :, 0
            ]
            x = working.target_x_units.to(torch.int64).gather(1, carrier_slot[:, None])[
                :, 0
            ]
            y = working.target_y_units.to(torch.int64).gather(1, carrier_slot[:, None])[
                :, 0
            ]
            carrier_entity_slot = working.entity_slot.gather(1, carrier_slot[:, None])[
                :, 0
            ].clamp_min(0)
            carrier_entity_id = working.entity_id.gather(1, carrier_slot[:, None])[:, 0]
            core_work = working_runtime.battle
            catalog_index = working_runtime.card_catalog_index[
                core_work.entity_card
            ].clamp_min(0)
            radius = working_runtime.catalog.collision_radius_units[catalog_index].to(
                torch.int64
            )
            airborne = working_runtime.catalog.is_air_unit[catalog_index]
            dx = core_work.entity_x_units.to(torch.int64) - x[:, None]
            dy = core_work.entity_y_units.to(torch.int64) - y[:, None]
            reach = self.catalog.radius_units[card, None] + radius
            eligible = (
                carrier_due[:, None]
                & working_runtime.entity_pool.active
                & core_work.entity_active
                & (core_work.entity_player != player[:, None])
                & (
                    (core_work.entity_kind == 0)
                    | (
                        ~self.catalog.ignore_buildings[card, None]
                        & (core_work.entity_kind == 1)
                    )
                )
                & torch.where(
                    airborne,
                    self.catalog.hits_air[card, None],
                    self.catalog.hits_ground[card, None],
                )
                & (dx * dx + dy * dy < reach * reach)
            )
            ordered_targets = working_runtime.entity_pool.id_order(eligible)
            target_slots = ordered_targets.slots.clamp_min(0)
            target_hp = core_work.entity_hp.gather(1, target_slots)
            amount = self.catalog.damage[card, None].expand_as(target_hp)
            applied = torch.minimum(target_hp, amount) * ordered_targets.valid
            updated_hp = torch.clamp(target_hp - amount, min=0.0)
            killed = ordered_targets.valid & (updated_hp <= 0.0)
            target_rows = rows[:, None].expand_as(ordered_targets.valid)
            valid_rows = target_rows[ordered_targets.valid]
            valid_slots = target_slots[ordered_targets.valid]
            core_work.entity_hp[valid_rows, valid_slots] = updated_hp[
                ordered_targets.valid
            ]
            dead_rows = target_rows[killed]
            dead_slots = target_slots[killed]
            core_work.entity_active[dead_rows, dead_slots] = False
            damage_result[valid_rows, valid_slots] += applied[ordered_targets.valid]
            death_result[dead_rows, dead_slots] = True
            working_runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=ordered_targets.valid,
                source_id=carrier_entity_id[:, None],
                target_id=ordered_targets.entity_ids,
                x_units=core_work.entity_x_units.gather(1, target_slots),
                y_units=core_work.entity_y_units.gather(1, target_slots),
                amount=applied,
                payload=card[:, None],
            )
            working_runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DEATH,
                valid=killed,
                source_id=carrier_entity_id[:, None],
                target_id=ordered_targets.entity_ids,
                x_units=core_work.entity_x_units.gather(1, target_slots),
                y_units=core_work.entity_y_units.gather(1, target_slots),
                payload=card[:, None],
            )

            push_distance = self.catalog.pushback_units[card]
            push_targets = (
                eligible
                & core_work.entity_active
                & (core_work.entity_kind == 0)
                & (push_distance[:, None] > 0)
            )
            immune = self.catalog.knockback_immune_catalog[catalog_index]
            push_targets &= self.catalog.pushback_ignores_mass[card, None] | ~immune
            direction = torch.stack((dx, dy), dim=-1)
            fallback_x = torch.where(core_work.entity_player == 0, 1, -1)
            direction[..., 0] = torch.where(
                torch.any(direction != 0, dim=-1), direction[..., 0], fallback_x
            )
            displacement = normalized_vector_units(direction, push_distance[:, None])
            push_endpoint = (
                torch.stack(
                    (core_work.entity_x_units, core_work.entity_y_units), dim=-1
                ).to(torch.int64)
                + displacement
            )
            working.pushback_active |= push_targets
            working.pushback_target_units.copy_(
                torch.where(
                    push_targets.unsqueeze(-1),
                    push_endpoint,
                    working.pushback_target_units,
                )
            )
            velocity = torch.zeros_like(push_distance)
            accumulated = torch.zeros_like(push_distance)
            for _ in range(32):
                advance = accumulated < push_distance
                velocity = torch.where(advance, velocity + 25, velocity)
                accumulated = torch.where(advance, accumulated + velocity, accumulated)
            working.pushback_velocity_work.copy_(
                torch.where(
                    push_targets, velocity[:, None], working.pushback_velocity_work
                )
            )

            child_counts = carrier_due.to(torch.int64) * self.catalog.spawn_count[card]
            allocation = working_runtime.entity_pool.allocate(child_counts)
            child_slot = allocation.slots[:, 0].clamp_min(0)
            child_valid = allocation.valid[:, 0]
            allocated_mask = torch.zeros_like(working_runtime.entity_pool.active)
            allocated_mask.scatter_(1, allocation.slots.clamp_min(0), allocation.valid)
            _clear_entity_slots_(working_runtime, allocated_mask)
            child_card = self.catalog.child_core_card[card]
            child_index = (rows[child_valid], child_slot[child_valid])
            selected_card = card[child_valid]
            working.pushback_active[child_index] = False
            working.pushback_target_units[child_index] = 0
            working.pushback_velocity_work[child_index] = 0
            core_work.entity_active[child_index] = True
            core_work.entity_kind[child_index] = 0
            core_work.entity_player[child_index] = player[child_valid].to(torch.int8)
            core_work.entity_card[child_index] = child_card[child_valid]
            core_work.entity_x_units[child_index] = x[child_valid].to(torch.int32)
            core_work.entity_y_units[child_index] = y[child_valid].to(torch.int32)
            core_work.entity_hp[child_index] = self.catalog.child_hitpoints[
                selected_card
            ]
            core_work.entity_hp_integer_kind[child_index] = True
            core_work.entity_max_hp[child_index] = self.catalog.child_hitpoints[
                selected_card
            ]
            remaining_delay = torch.clamp(
                self.catalog.child_deploy_delay[selected_card]
                - dt[child_valid].to(torch.float64) / 1_000.0,
                min=0.0,
            )
            core_work.entity_deploy_delay[child_index] = remaining_delay
            pending = remaining_delay > 1e-9
            core_work.entity_placement_pending[child_index] = pending
            core_work.entity_spawn_hook_pending[child_index] = pending
            core_work.entity_spawn_hook_fired[child_index] = ~pending
            working.shield_hitpoints[child_index] = self.catalog.child_shield_hitpoints[
                selected_card
            ]
            working_runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.SPAWN,
                valid=allocation.valid,
                source_id=allocation.entity_ids,
                x_units=core_work.entity_x_units.gather(
                    1, allocation.slots.clamp_min(0)
                ),
                y_units=core_work.entity_y_units.gather(
                    1, allocation.slots.clamp_min(0)
                ),
                payload=core_work.entity_card.gather(1, allocation.slots.clamp_min(0)),
            )
            spawned_count += child_counts
            carrier_cleanup[rows[carrier_due], carrier_entity_slot[carrier_due]] = True
            working.active[rows[carrier_due], carrier_slot[carrier_due]] = False
            for name in (
                "entity_id",
                "card_id",
                "player_id",
                "target_x_units",
                "target_y_units",
                "remaining_ms",
                "elapsed_ms",
                "travel_work_units",
            ):
                getattr(working, name)[rows[carrier_due], carrier_slot[carrier_due]] = 0
            working.entity_slot[rows[carrier_due], carrier_slot[carrier_due]] = -1

        working_runtime.entity_pool.cleanup(carrier_cleanup)
        _clear_entity_slots_(working_runtime, carrier_cleanup)
        working_runtime.mark_dirty(impact_rows & supported, phase=TickPhase.OBJECTS)
        commit_rows = selected & supported
        _copy_runtime_rows_(runtime, working_runtime, commit_rows)
        self._copy_rows_(working, commit_rows)
        return RoyalDeliveryStepResult(
            committed=committed,
            impacted=impact_rows & supported,
            damage=damage_result,
            deaths=death_result,
            spawned_count=spawned_count,
            pushback_active=self.pushback_active.clone(),
        )


__all__ = [
    "RoyalDeliveryMaterializeResult",
    "RoyalDeliveryStepResult",
    "TensorResidentRoyalDelivery",
    "TensorRoyalDeliveryCatalog",
]
