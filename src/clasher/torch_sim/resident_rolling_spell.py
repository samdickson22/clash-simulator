"""Retained rolling-projectile spell lifecycle for pending due commands."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.spells import SPELL_REGISTRY, RollingProjectileSpell
from clasher.unit_traits import is_above_ground_surface, is_knockback_immune

from .entity_pool import EntityAllocation
from .resident_pending_spells import TensorResidentPendingSpells
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class RollingSpellReason(IntEnum):
    NONE = 0
    ROLLER_CAPACITY = 1
    ENTITY_CAPACITY = 2
    EVENT_CAPACITY = 3
    UNSUPPORTED_TARGET_DEATH = 4
    UNKNOWN_CHILD = 5


@dataclass(frozen=True)
class TensorRollingDueHandoff:
    batch_index: torch.Tensor
    pending_slot: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    sequence: torch.Tensor

    @classmethod
    def from_pending(
        cls,
        runtime: TensorBattleRuntime,
        pending: TensorResidentPendingSpells,
        catalog: TensorRollingSpellCatalog,
    ) -> TensorRollingDueHandoff:
        due = pending.active & (
            pending.execute_at <= runtime.battle.time[:, None] + 1e-9
        )
        rolling = catalog.supported[pending.card_id.clamp_min(0)]
        selected = due & rolling
        coordinates = torch.nonzero(selected, as_tuple=False)
        if coordinates.numel() == 0:
            empty = torch.zeros(0, dtype=torch.int64, device=runtime.device)
            return cls(empty, empty, empty, empty, empty, empty, empty)
        batch = coordinates[:, 0]
        slot = coordinates[:, 1]
        sequence = pending.sequence[batch, slot]
        key = batch * (torch.iinfo(torch.int32).max + 1) + sequence
        order = torch.argsort(key, stable=True)
        batch = batch[order]
        slot = slot[order]
        return cls(
            batch,
            slot,
            pending.card_id[batch, slot],
            pending.player_id[batch, slot].to(torch.int64),
            pending.target_x_units[batch, slot].to(torch.int64),
            pending.target_y_units[batch, slot].to(torch.int64),
            pending.sequence[batch, slot],
        )


@dataclass
class TensorRollingSpellCatalog:
    supported: torch.Tensor
    damage: torch.Tensor
    rolling_radius_units: torch.Tensor
    radius_y_units: torch.Tensor
    casting_speed_units_per_second: torch.Tensor
    casting_min_distance_units: torch.Tensor
    travel_speed_units_per_tick: torch.Tensor
    range_units: torch.Tensor
    knockback_units: torch.Tensor
    knockback_ignores_mass: torch.Tensor
    crown_damage: torch.Tensor
    child_core_id: torch.Tensor
    child_hp: torch.Tensor
    child_hp_integer_kind: torch.Tensor
    child_deploy_delay: torch.Tensor
    child_name: tuple[str, ...]

    @classmethod
    def compile(
        cls,
        runtime: TensorBattleRuntime,
        battle: BattleState,
    ) -> TensorRollingSpellCatalog:
        size = len(runtime.battle.card_names)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=runtime.device)

        supported = zeros(torch.bool)
        damage = zeros(torch.float64)
        rolling_radius = zeros(torch.int64)
        radius_y = zeros(torch.int64)
        casting_speed = zeros(torch.float64)
        casting_min = zeros(torch.int64)
        travel_speed = zeros(torch.int64)
        range_units = zeros(torch.int64)
        knockback = zeros(torch.int64)
        ignores_mass = zeros(torch.bool)
        crown_damage = zeros(torch.float64)
        child_core = torch.full((size,), -1, dtype=torch.int64, device=runtime.device)
        child_hp = zeros(torch.float64)
        child_integer = zeros(torch.bool)
        child_delay = zeros(torch.float64)
        children = [""] * size
        required_children: dict[str, dict[str, object]] = {}
        for core_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            spell = SPELL_REGISTRY.get(name)
            if not isinstance(spell, RollingProjectileSpell):
                continue
            supported[core_id] = True
            damage[core_id] = spell.damage
            rolling_radius[core_id] = round(spell.radius * 1_000)
            radius_y[core_id] = round(spell.radius_y * 1_000)
            casting_speed[core_id] = spell.casting_speed * 1_000
            casting_min[core_id] = round(spell.casting_min_distance * 1_000)
            travel_speed[core_id] = round(spell.travel_speed)
            range_units[core_id] = round(spell.projectile_range * 1_000)
            knockback[core_id] = round(spell.knockback_distance * 1_000)
            ignores_mass[core_id] = spell.knockback_ignores_mass
            crown_damage[core_id] = (
                spell.damage
                if spell.crown_tower_damage is None
                else spell.crown_tower_damage
            )
            if spell.spawn_character and spell.spawn_character_data:
                children[core_id] = spell.spawn_character
                required_children[spell.spawn_character] = spell.spawn_character_data

        if required_children:
            new_children = sorted(
                set(required_children) - set(runtime.battle.card_names)
            )
            names = (*runtime.battle.card_names, *new_children)
            if names != runtime.battle.card_names:
                mapping = {name: index for index, name in enumerate(names)}
                old_to_new = torch.tensor(
                    [mapping[name] for name in runtime.battle.card_names],
                    dtype=torch.int64,
                    device=runtime.device,
                )
                for field in ("hand", "deck", "cycle_queue", "entity_card"):
                    value = getattr(runtime.battle, field)
                    value.copy_(old_to_new[value])
                runtime.battle.card_names = names
                runtime.battle.card_to_id = mapping
                runtime.card_catalog_index = torch.cat(
                    (
                        runtime.card_catalog_index,
                        torch.full(
                            (len(names) - runtime.card_catalog_index.numel(),),
                            -1,
                            dtype=torch.int64,
                            device=runtime.device,
                        ),
                    )
                )
            for core_id, child in enumerate(children):
                if not child:
                    continue
                stats = troop_from_character_data(
                    child,
                    required_children[child],
                    elixir=0,
                    rarity=str(required_children[child].get("rarity", "Common")),
                )
                child_core[core_id] = runtime.battle.card_to_id[child]
                hp = stats.scaled_hitpoints or stats.hitpoints or 100
                child_hp[core_id] = hp
                child_integer[core_id] = type(hp) is int
                spell = SPELL_REGISTRY.get(runtime.battle.card_names[core_id])
                assert isinstance(spell, RollingProjectileSpell)
                child_delay[core_id] = (
                    float(stats.deploy_time or 0) / 1_000.0
                    if spell.spawn_deploy_delay is None
                    else spell.spawn_deploy_delay
                )
        return cls(
            supported,
            damage,
            rolling_radius,
            radius_y,
            casting_speed,
            casting_min,
            travel_speed,
            range_units,
            knockback,
            ignores_mass,
            crown_damage,
            child_core,
            child_hp,
            child_integer,
            child_delay,
            tuple(children),
        )


@dataclass
class TensorRollingProjectileState:
    active: torch.Tensor
    entity_id: torch.Tensor
    card_id: torch.Tensor
    player_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    age_ms: torch.Tensor
    spawn_delay_ms: torch.Tensor
    distance_units: torch.Tensor
    hit_entity_ids: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        hit_capacity: int,
        *,
        device: str | torch.device,
    ) -> TensorRollingProjectileState:
        shape = (batch_size, capacity)
        return cls(
            torch.zeros(shape, dtype=torch.bool, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros(shape, dtype=torch.int8, device=device),
            torch.zeros(shape, dtype=torch.int32, device=device),
            torch.zeros(shape, dtype=torch.int32, device=device),
            torch.zeros(shape, dtype=torch.float64, device=device),
            torch.zeros(shape, dtype=torch.float64, device=device),
            torch.zeros(shape, dtype=torch.int64, device=device),
            torch.zeros((*shape, hit_capacity), dtype=torch.int64, device=device),
        )

    def clone(self) -> TensorRollingProjectileState:
        return type(self)(
            **{field.name: getattr(self, field.name).clone() for field in fields(self)}
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorRollingProjectileState:
        index = torch.as_tensor(rows, dtype=torch.int64, device=self.active.device)
        return type(self)(
            **{
                field.name: getattr(self, field.name).index_select(0, index).clone()
                for field in fields(self)
            }
        )

    def reset_(self, mask: torch.Tensor) -> None:
        selected = torch.as_tensor(mask, dtype=torch.bool, device=self.active.device)
        if selected.shape != self.active.shape:
            raise ValueError("roller reset mask must match [batch, roller]")
        for field in fields(self):
            value = getattr(self, field.name)
            expanded = selected.reshape(*selected.shape, *((1,) * (value.ndim - 2)))
            value.masked_fill_(expanded, 0)


@dataclass
class TensorRollingTargets:
    collision_radius_units: torch.Tensor
    above_ground: torch.Tensor
    crown: torch.Tensor
    area_receivable: torch.Tensor
    effect_receivable: torch.Tensor
    knockback_receivable: torch.Tensor
    knockback_immune: torch.Tensor
    death_payload_supported: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        catalog: TensorRollingSpellCatalog,
    ) -> TensorRollingTargets:
        shape = runtime.battle.entity_id.shape
        size = len(runtime.battle.card_names)
        collision = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        above = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        crown = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        area = torch.ones((size, *shape), dtype=torch.bool, device=runtime.device)
        effect = torch.ones_like(area)
        knock = torch.ones_like(area)
        immune = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
        death_supported = torch.ones(shape, dtype=torch.bool, device=runtime.device)
        rolling_ids = torch.nonzero(catalog.supported).flatten().tolist()
        for row, battle in enumerate(battles):
            slot_by_id = {
                int(value): slot
                for slot, value in enumerate(runtime.battle.entity_id[row].tolist())
                if value
            }
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                collision[row, slot] = round(entity.get_collision_radius() * 1_000)
                above[row, slot] = is_above_ground_surface(entity)
                crown[row, slot] = bool(
                    isinstance(entity, Building)
                    and getattr(entity.card_stats, "name", None)
                    in {"Tower", "KingTower"}
                )
                immune[row, slot] = is_knockback_immune(entity.card_stats)
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
                for card in rolling_ids:
                    source_kind = runtime.battle.card_names[card]
                    area[card, row, slot] = entity.can_receive_area_damage(source_kind)
                    effect[card, row, slot] = entity.can_receive_effect(source_kind)
                    knock[card, row, slot] = entity.can_receive_forced_movement(
                        source_kind, "knockback"
                    )
        return cls(
            collision, above, crown, area, effect, knock, immune, death_supported
        )


@dataclass(frozen=True)
class TensorRollingKnockback:
    valid: torch.Tensor
    source_id: torch.Tensor
    target_id: torch.Tensor
    target_slot: torch.Tensor
    direction_y: torch.Tensor
    distance_units: torch.Tensor


@dataclass(frozen=True)
class TensorRollingStepResult:
    committed: torch.Tensor
    reason: torch.Tensor
    hit: torch.Tensor
    damage: torch.Tensor
    died: torch.Tensor
    spawned_child: EntityAllocation
    knockback: TensorRollingKnockback


def _copy_rows(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for field in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, field.name)
        right = getattr(source, field.name)
        if isinstance(left, torch.Tensor) and left.ndim > 0 and left.shape[0] == batch:
            left[rows] = right[rows]


def _empty_allocation(runtime: TensorBattleRuntime) -> EntityAllocation:
    valid = torch.zeros_like(runtime.entity_pool.active)
    return EntityAllocation(
        torch.full_like(runtime.battle.entity_id, -1),
        torch.zeros_like(runtime.battle.entity_id),
        valid,
    )


def _clear_entity_slots(
    runtime: TensorBattleRuntime,
    rows: torch.Tensor,
    slots: torch.Tensor,
) -> None:
    index = (rows, slots)
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for field in fields(owner):
            value = getattr(owner, field.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.entity_pool.active.shape
                and not (owner is runtime.battle and field.name == "entity_id")
            ):
                value[index] = 0
    runtime.phases.target_slot[index] = -1
    runtime.battle.entity_tower_slot[index] = -1


class TensorResidentRollingSpells:
    def __init__(
        self,
        catalog: TensorRollingSpellCatalog,
        state: TensorRollingProjectileState,
        targets: TensorRollingTargets,
    ) -> None:
        self.catalog = catalog
        self.state = state
        self.targets = targets

    def consume_due_(
        self,
        runtime: TensorBattleRuntime,
        pending: TensorResidentPendingSpells,
        handoff: TensorRollingDueHandoff,
    ) -> torch.Tensor:
        if handoff.batch_index.numel() == 0:
            return torch.ones(
                runtime.batch_size, dtype=torch.bool, device=runtime.device
            )
        counts = torch.bincount(handoff.batch_index, minlength=runtime.batch_size)
        roller_free = (~self.state.active).sum(dim=1)
        entity_free = (~runtime.entity_pool.active).sum(dim=1)
        event_free = runtime.events.capacity - runtime.events.count.to(torch.int64)
        committed = (
            runtime.supported
            & (counts <= roller_free)
            & (counts <= entity_free)
            & (counts <= event_free)
        )
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working_state = self.state.clone()
        effective = committed[handoff.batch_index]
        effective_rows = handoff.batch_index[effective]
        effective_cards = handoff.card_id[effective]
        effective_players = handoff.player_id[effective]
        effective_x = handoff.x_units[effective]
        effective_y = handoff.y_units[effective]
        effective_pending = handoff.pending_slot[effective]
        allocation = working_runtime.entity_pool.allocate(
            torch.where(committed, counts, 0)
        )
        free_order = torch.argsort(
            torch.where(
                ~working_state.active,
                torch.arange(working_state.active.shape[1], device=runtime.device),
                working_state.active.shape[1],
            ),
            dim=1,
        )
        ordinal = torch.arange(handoff.batch_index.numel(), device=runtime.device)
        prior = (handoff.batch_index[:, None] == handoff.batch_index[None, :]) & (
            ordinal[:, None] > ordinal[None, :]
        )
        local = prior.sum(dim=1)[effective]
        roller_slot = free_order[effective_rows, local]
        entity_slot = allocation.slots[effective_rows, local]
        entity_id = allocation.entity_ids[effective_rows, local]
        launch_y = torch.where(effective_players == 0, 2_500, 29_500)
        dx = effective_x - 9_000
        dy = effective_y - launch_y
        distance = torch.sqrt((dx * dx + dy * dy).to(torch.float64))
        distance = torch.maximum(
            distance, self.catalog.casting_min_distance_units[effective_cards]
        )
        delay = (
            distance
            * 1_000.0
            / self.catalog.casting_speed_units_per_second[effective_cards].clamp_min(
                1.0
            )
        )
        index = (effective_rows, roller_slot)
        working_state.active[index] = True
        working_state.entity_id[index] = entity_id
        working_state.card_id[index] = effective_cards
        working_state.player_id[index] = effective_players.to(torch.int8)
        working_state.x_units[index] = effective_x.to(torch.int32)
        working_state.y_units[index] = effective_y.to(torch.int32)
        working_state.spawn_delay_ms[index] = delay
        runtime_index = (effective_rows, entity_slot)
        _clear_entity_slots(working_runtime, effective_rows, entity_slot)
        working_runtime.battle.entity_active[runtime_index] = True
        # The scalar RollingProjectile is an object carrier with no public
        # card_stats.  Keep its serialized spell identity only in
        # ``working_state.card_id`` for retained lifecycle resolution.
        working_runtime.battle.entity_kind[runtime_index] = 2
        working_runtime.battle.entity_player[runtime_index] = effective_players.to(
            torch.int8
        )
        working_runtime.battle.entity_card[runtime_index] = 0
        working_runtime.battle.entity_x_units[runtime_index] = effective_x.to(
            torch.int32
        )
        working_runtime.battle.entity_y_units[runtime_index] = effective_y.to(
            torch.int32
        )
        working_runtime.battle.entity_hp[runtime_index] = 1.0
        working_runtime.battle.entity_hp_integer_kind[runtime_index] = True
        working_runtime.battle.entity_max_hp[runtime_index] = 1.0
        working_runtime.battle.entity_id.copy_(working_runtime.entity_pool.entity_id)
        source = torch.zeros_like(allocation.entity_ids)
        payload = torch.zeros_like(allocation.entity_ids)
        payload[effective_rows, local] = effective_cards
        working_runtime.events.append(
            phase=TickPhase.COMMANDS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=source,
            target_id=allocation.entity_ids,
            payload=payload,
        )
        working_runtime.mark_dirty(committed, phase=TickPhase.COMMANDS)
        pending.active[effective_rows, effective_pending] = False
        for name in (
            "execute_at",
            "sequence",
            "card_id",
            "player_id",
            "target_x_units",
            "target_y_units",
        ):
            getattr(pending, name)[effective_rows, effective_pending] = 0
        _copy_rows(runtime.battle, working_runtime.battle, committed)
        _copy_rows(runtime.status, working_runtime.status, committed)
        _copy_rows(runtime.phases, working_runtime.phases, committed)
        _copy_rows(runtime.events, working_runtime.events, committed)
        runtime.entity_pool.active[committed] = working_runtime.entity_pool.active[
            committed
        ]
        runtime.entity_pool.next_entity_id[committed] = (
            working_runtime.entity_pool.next_entity_id[committed]
        )
        runtime.dirty[committed] = working_runtime.dirty[committed]
        _copy_rows(self.state, working_state, committed)
        return committed

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: float = 50.0,
    ) -> TensorRollingStepResult:
        working = runtime.clone()
        working.battle.rng = runtime.battle.rng.clone()
        state = self.state.clone()
        hit = torch.zeros(
            (runtime.batch_size, runtime.max_entities),
            dtype=torch.bool,
            device=runtime.device,
        )
        damage_total = torch.zeros_like(working.battle.entity_hp)
        died_total = torch.zeros_like(working.battle.entity_active)
        knock_valid = torch.zeros_like(hit)
        knock_source = torch.zeros_like(working.battle.entity_id)
        hit_source = torch.zeros_like(working.battle.entity_id)
        knock_distance = torch.zeros_like(working.battle.entity_id)
        direction_y = torch.zeros_like(working.battle.entity_id, dtype=torch.int8)
        event_additions = torch.zeros(
            runtime.batch_size, dtype=torch.int64, device=runtime.device
        )
        supported = runtime.supported.clone()
        terminal = torch.zeros_like(state.active)

        for roller_slot in range(state.active.shape[1]):
            active = state.active[:, roller_slot] & supported
            card = state.card_id[:, roller_slot]
            state.age_ms[:, roller_slot] += torch.where(active, dt_ms, 0.0)
            rolling = active & (
                state.age_ms[:, roller_slot] + 1e-9
                >= state.spawn_delay_ms[:, roller_slot]
            )
            remaining = (
                self.catalog.range_units[card] - state.distance_units[:, roller_slot]
            ).clamp_min(0)
            work = torch.full_like(remaining, round(dt_ms / 50.0)).clamp_min(0)
            work *= self.catalog.travel_speed_units_per_tick[card]
            move = torch.minimum(work, remaining)
            state.distance_units[:, roller_slot] += torch.where(rolling, move, 0)
            sign = torch.where(state.player_id[:, roller_slot] == 0, 1, -1)
            state.y_units[:, roller_slot] += (torch.where(rolling, move, 0) * sign).to(
                torch.int32
            )
            roller_id = state.entity_id[:, roller_slot]
            roller_matches = working.entity_pool.active & (
                working.battle.entity_id == roller_id[:, None]
            )
            roller_entity_slot = roller_matches.to(torch.int64).argmax(dim=1)
            rows = torch.arange(runtime.batch_size, device=runtime.device)
            active_rows = rows[active]
            working.battle.entity_y_units[active_rows, roller_entity_slot[active]] = (
                state.y_units[active, roller_slot]
            )
            target_order = working.entity_pool.id_order()
            slots = target_order.slots.clamp_min(0)
            target_ids = target_order.entity_ids
            already = (
                state.hit_entity_ids[:, roller_slot, :, None] == target_ids[:, None, :]
            ).any(dim=1)
            target_player = working.battle.entity_player.gather(1, slots)
            target_x = working.battle.entity_x_units.gather(1, slots)
            target_y = working.battle.entity_y_units.gather(1, slots)
            radius = self.targets.collision_radius_units.gather(1, slots)
            eligible = (
                rolling[:, None]
                & target_order.valid
                & working.battle.entity_active.gather(1, slots)
                & (target_player != state.player_id[:, roller_slot, None])
                & ~self.targets.above_ground.gather(1, slots)
                & ~already
                & self.targets.area_receivable[card[:, None], rows[:, None], slots]
                & self.targets.effect_receivable[card[:, None], rows[:, None], slots]
                & (
                    (target_x - state.x_units[:, roller_slot, None]).abs()
                    <= self.catalog.rolling_radius_units[card, None] + radius
                )
                & (
                    (target_y - state.y_units[:, roller_slot, None]).abs()
                    <= self.catalog.radius_y_units[card, None] + radius
                )
            )
            target_damage = torch.where(
                self.targets.crown.gather(1, slots),
                self.catalog.crown_damage[card, None],
                self.catalog.damage[card, None],
            )
            before = working.battle.entity_hp.gather(1, slots)
            after = (before - torch.where(eligible, target_damage, 0.0)).clamp_min(0.0)
            new_death = (
                eligible & (after <= 0) & working.battle.entity_active.gather(1, slots)
            )
            unsupported_death = (
                new_death & ~self.targets.death_payload_supported.gather(1, slots)
            )
            valid_batch, valid_order = torch.where(target_order.valid)
            physical = slots[valid_batch, valid_order]
            target_index = (valid_batch, physical)
            working.battle.entity_hp[target_index] = after[valid_batch, valid_order]
            working.battle.entity_active[target_index] = (
                working.battle.entity_active[target_index]
                & ~new_death[valid_batch, valid_order]
            )
            hit[target_index] |= eligible[valid_batch, valid_order]
            hit_source[target_index] = torch.where(
                eligible[valid_batch, valid_order],
                roller_id[valid_batch],
                hit_source[target_index],
            )
            damage_total[target_index] += torch.where(
                eligible[valid_batch, valid_order],
                before[valid_batch, valid_order] - after[valid_batch, valid_order],
                0.0,
            )
            died_total[target_index] |= new_death[valid_batch, valid_order]
            count_before = (state.hit_entity_ids[:, roller_slot] > 0).sum(dim=1)
            for target_ordinal in range(runtime.max_entities):
                selected = eligible[:, target_ordinal]
                insertion = count_before + eligible[:, :target_ordinal].sum(dim=1)
                selected_rows = rows[selected]
                state.hit_entity_ids[
                    selected_rows, roller_slot, insertion[selected]
                ] = target_ids[selected, target_ordinal]
            knock = (
                eligible
                & ~new_death
                & (self.catalog.knockback_units[card, None] > 0)
                & self.targets.knockback_receivable[card[:, None], rows[:, None], slots]
                & (
                    self.catalog.knockback_ignores_mass[card, None]
                    | ~self.targets.knockback_immune.gather(1, slots)
                )
            )
            knock_valid[target_index] |= knock[valid_batch, valid_order]
            knock_source[target_index] = torch.where(
                knock[valid_batch, valid_order],
                roller_id[valid_batch],
                knock_source[target_index],
            )
            knock_distance[target_index] = torch.where(
                knock[valid_batch, valid_order],
                self.catalog.knockback_units[card[valid_batch]],
                knock_distance[target_index],
            )
            direction_y[target_index] = torch.where(
                knock[valid_batch, valid_order],
                sign[valid_batch],
                direction_y[target_index],
            ).to(torch.int8)
            event_additions += eligible.sum(dim=1) + new_death.sum(dim=1)
            terminal[:, roller_slot] = rolling & (
                state.distance_units[:, roller_slot] >= self.catalog.range_units[card]
            )
            event_additions += terminal[:, roller_slot].to(torch.int64)
            unsupported_row = unsupported_death.any(dim=1)
            supported &= ~unsupported_row

        child_needed = terminal & (self.catalog.child_core_id[state.card_id] >= 0)
        child_counts = child_needed.sum(dim=1, dtype=torch.int64)
        event_additions += child_counts
        event_overflow = (
            runtime.events.count.to(torch.int64) + event_additions
            > runtime.events.capacity
        )
        committed = supported & ~event_overflow
        reason = torch.where(
            ~supported,
            int(RollingSpellReason.UNSUPPORTED_TARGET_DEATH),
            torch.where(event_overflow, int(RollingSpellReason.EVENT_CAPACITY), 0),
        ).to(torch.int16)
        # Remove terminal rollers before child allocation so their physical slots are reusable.
        terminal_effective = terminal & committed[:, None]
        terminal_ids = torch.where(terminal_effective, state.entity_id, 0)
        terminal_card = state.card_id.clone()
        terminal_player = state.player_id.clone()
        terminal_x = state.x_units.clone()
        terminal_y = state.y_units.clone()
        dead = (
            (working.battle.entity_id[:, :, None] == terminal_ids[:, None, :])
            & terminal_effective[:, None, :]
        ).any(dim=2)
        working.entity_pool.cleanup(dead)
        working.battle.entity_active.masked_fill_(dead, False)
        working.battle.entity_id.copy_(working.entity_pool.entity_id)
        state.reset_(terminal_effective)
        allocation = working.entity_pool.allocate(
            torch.where(committed, child_counts, 0)
        )
        # Child payload installation is intentionally dense but only one child exists per roller.
        child_event = torch.nonzero(child_needed & committed[:, None], as_tuple=False)
        if child_event.numel():
            rows = child_event[:, 0]
            rollers = child_event[:, 1]
            local = torch.arange(child_event.shape[0], device=runtime.device)
            prior = (rows[:, None] == rows[None, :]) & (local[:, None] > local[None, :])
            ordinal = prior.sum(dim=1)
            slots = allocation.slots[rows, ordinal]
            card = terminal_card[rows, rollers]
            _clear_entity_slots(working, rows, slots)
            index = (rows, slots)
            working.battle.entity_active[index] = True
            working.battle.entity_kind[index] = 0
            working.battle.entity_player[index] = terminal_player[rows, rollers]
            working.battle.entity_card[index] = self.catalog.child_core_id[card]
            working.battle.entity_x_units[index] = terminal_x[rows, rollers]
            working.battle.entity_y_units[index] = terminal_y[rows, rollers]
            working.battle.entity_hp[index] = self.catalog.child_hp[card]
            working.battle.entity_hp_integer_kind[index] = (
                self.catalog.child_hp_integer_kind[card]
            )
            working.battle.entity_max_hp[index] = self.catalog.child_hp[card]
            deploy = self.catalog.child_deploy_delay[card]
            working.battle.entity_deploy_delay[index] = deploy
            working.battle.entity_placement_pending[index] = deploy > 1e-9
            working.battle.entity_spawn_hook_pending[index] = deploy > 1e-9
            working.battle.entity_spawn_hook_fired[index] = deploy <= 1e-9
            working.battle.entity_id.copy_(working.entity_pool.entity_id)
        target_id = working.battle.entity_id
        working.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.DAMAGE,
            valid=hit & committed[:, None],
            source_id=hit_source,
            target_id=target_id,
            x_units=working.battle.entity_x_units,
            y_units=working.battle.entity_y_units,
            amount=damage_total,
        )
        working.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.DEATH,
            valid=died_total & committed[:, None],
            source_id=hit_source,
            target_id=target_id,
        )
        working.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.DEATH,
            valid=terminal_effective,
            source_id=terminal_ids,
        )
        child_source = torch.zeros_like(allocation.entity_ids)
        if child_event.numel():
            child_source[rows, ordinal] = terminal_ids[rows, rollers]
        working.events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=allocation.valid,
            source_id=child_source,
            target_id=allocation.entity_ids,
        )
        working.phases.death_pending |= died_total & committed[:, None]
        _copy_rows(runtime.battle, working.battle, committed)
        _copy_rows(runtime.status, working.status, committed)
        _copy_rows(runtime.phases, working.phases, committed)
        _copy_rows(runtime.events, working.events, committed)
        runtime.entity_pool.active[committed] = working.entity_pool.active[committed]
        runtime.entity_pool.next_entity_id[committed] = (
            working.entity_pool.next_entity_id[committed]
        )
        _copy_rows(self.state, state, committed)
        return TensorRollingStepResult(
            committed,
            reason,
            hit,
            damage_total,
            died_total,
            allocation,
            TensorRollingKnockback(
                knock_valid,
                knock_source,
                working.battle.entity_id,
                torch.arange(runtime.max_entities, device=runtime.device)[
                    None, :
                ].expand(runtime.batch_size, -1),
                direction_y,
                knock_distance,
            ),
        )


__all__ = [
    "RollingSpellReason",
    "TensorResidentRollingSpells",
    "TensorRollingDueHandoff",
    "TensorRollingProjectileState",
    "TensorRollingSpellCatalog",
    "TensorRollingStepResult",
    "TensorRollingTargets",
]
