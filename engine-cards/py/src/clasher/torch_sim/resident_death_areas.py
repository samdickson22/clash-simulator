"""Retained consumer for serialized DeathArea descriptors.

``resident_death_payloads`` reserves object identities and emits compact area
descriptors during cleanup.  This owner claims those identities, retains any
nested activation container, advances the final slow/haste area, resolves
impact damage, and publishes rows atomically.  Missing impact and hit-plane
fields are joined from the serialized source mechanic at boundary compile.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any, cast

import torch

from clasher.balance import tournament_spell_stat
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.gamedata_normalization import serialized_hit_planes
from clasher.kinematics import tiles_to_logic_units
from clasher.logic_math import native_percent_damage
from clasher.unit_traits import is_airborne_target

from .resident_death_payloads import TensorDeathAreaDescriptors
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


@dataclass(frozen=True)
class TensorDeathAreaConsumerCatalog:
    supported_core: torch.Tensor
    reason: tuple[str, ...]
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    cap_buff_to_area: torch.Tensor
    impact_damage: torch.Tensor
    impact_affects_hidden: torch.Tensor
    impact_crown_damage: torch.Tensor


@dataclass(frozen=True)
class DeathAreaConsumeResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    capacity_rejected: torch.Tensor


@dataclass(frozen=True)
class DeathAreaStepResult:
    committed: torch.Tensor
    capacity_rejected: torch.Tensor
    container_activated: torch.Tensor
    expired: torch.Tensor
    damage: torch.Tensor
    deaths: torch.Tensor


def _first_action_spawn(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        spawn = value.get("spawnDataData")
        if isinstance(spawn, dict):
            return cast(dict[str, Any], spawn)
        for nested in value.values():
            found = _first_action_spawn(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_action_spawn(nested)
            if found is not None:
                return found
    return None


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


def _clear_slots_(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == mask.shape
                and not (owner is runtime.battle and descriptor.name == "entity_id")
            ):
                expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
                value.masked_fill_(expanded, 0)
    runtime.phases.target_slot.masked_fill_(mask, -1)
    runtime.battle.entity_tower_slot.masked_fill_(mask, -1)


def _first_free(mask: torch.Tensor) -> torch.Tensor:
    width = mask.shape[1]
    slots = torch.arange(width, dtype=torch.int64, device=mask.device)[None, :]
    return torch.where(mask, slots, width).amin(dim=1)


@dataclass
class TensorResidentDeathAreas:
    catalog: TensorDeathAreaConsumerCatalog
    active: torch.Tensor
    container: torch.Tensor
    entity_slot: torch.Tensor
    object_id: torch.Tensor
    source_id: torch.Tensor
    source_card: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    radius_units: torch.Tensor
    duration_ms: torch.Tensor
    activation_delay_ms: torch.Tensor
    interval_ms: torch.Tensor
    buff_duration_ms: torch.Tensor
    damage: torch.Tensor
    movement_multiplier: torch.Tensor
    attack_multiplier: torch.Tensor
    spawn_multiplier: torch.Tensor
    affects_hidden: torch.Tensor
    age_ms: torch.Tensor
    next_effect_ms: torch.Tensor
    effect_snapshot_applied: torch.Tensor
    impact_applied: torch.Tensor
    source_entity_id: torch.Tensor
    source_entity_card: torch.Tensor
    target_entity_id: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_building: torch.Tensor
    target_crown: torch.Tensor
    target_effect_receivable: torch.Tensor
    target_effect_receivable_hidden: torch.Tensor
    target_has_shield: torch.Tensor
    target_shield: torch.Tensor
    target_shield_integer_kind: torch.Tensor
    target_shield_break_count: torch.Tensor
    target_death_payload_supported: torch.Tensor

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
        capacity: int = 16,
    ) -> TensorResidentDeathAreas:
        if len(battles) != runtime.batch_size or capacity < 1:
            raise ValueError("invalid retained death-area dimensions")
        device = runtime.device
        size = len(runtime.battle.card_names)

        def card_plane(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(size, dtype=dtype, device=device)

        supported = card_plane(torch.bool)
        reasons = ["no serialized DeathAreaEffect"] * size
        hits_air = card_plane(torch.bool)
        hits_ground = card_plane(torch.bool)
        cap = card_plane(torch.bool)
        impact_damage = card_plane(torch.float64)
        impact_hidden = card_plane(torch.bool)
        impact_crown = card_plane(torch.float64)
        definitions = battles[0].card_loader.load_card_definitions()
        for card, name in enumerate(runtime.battle.card_names):
            definition = definitions.get(name)
            stats = battles[0].card_loader.get_card(name) if name else None
            if definition is None or stats is None:
                continue
            mechanics = [
                mechanic
                for mechanic in definition.mechanics
                if type(mechanic).__name__ == "DeathAreaEffect"
            ]
            if not mechanics:
                continue
            if len(mechanics) != 1:
                reasons[card] = "multiple DeathAreaEffect payloads are not retained"
                continue
            outer = cast(dict[str, Any], cast(Any, mechanics[0]).area_data)
            action = _first_action_spawn(outer.get("onStartingActionData"))
            raw = (
                cast(dict[str, Any], action.get("deathAreaEffectData"))
                if action is not None
                and isinstance(action.get("deathAreaEffectData"), dict)
                else outer
            )
            if action is not None and not isinstance(
                action.get("deathAreaEffectData"), dict
            ):
                reasons[card] = "death-area nested character actions are not retained"
                continue
            if float(raw.get("damage", 0) or 0) > 0.0:
                reasons[card] = "periodic death-area damage is not retained"
                continue
            buff = raw.get("buffData") or {}
            if not isinstance(buff, dict):
                reasons[card] = "death-area buff metadata is malformed"
                continue
            multipliers = tuple(
                max(
                    0.0,
                    (
                        100.0 + float(buff.get(field, 0) or 0)
                        if float(buff.get(field, 0) or 0) <= 0.0
                        else float(buff.get(field, 100) or 100)
                    )
                    / 100.0,
                )
                for field in (
                    "speedMultiplier",
                    "hitSpeedMultiplier",
                    "spawnSpeedMultiplier",
                )
            )
            if buff and min(multipliers) <= 0.0:
                reasons[card] = "death-area full freeze status is not retained"
                continue
            air, ground = serialized_hit_planes(raw)
            impact = raw.get("spawnAreaEffectObjectData") or {}
            if not isinstance(impact, dict):
                reasons[card] = "death-area impact metadata is malformed"
                continue
            raw_damage = float(impact.get("damage", 0) or 0)
            scaler = getattr(stats, "get_scaled_stat", None)
            actual_damage = float(
                scaler(raw_damage) if callable(scaler) else raw_damage
            )
            area_name = str(raw.get("name", "") or "")
            live_damage = (
                tournament_spell_stat(area_name, "damage") if area_name else None
            )
            if live_damage is not None:
                actual_damage = float(live_damage)
            explicit_crown = (
                tournament_spell_stat(area_name, "crown_tower_damage")
                if area_name
                else None
            )
            crown_multiplier = max(
                0.0,
                1.0 + float(impact.get("crownTowerDamagePercent", 0) or 0) / 100.0,
            )
            supported[card] = True
            reasons[card] = ""
            hits_air[card] = air
            hits_ground[card] = ground
            cap[card] = bool(raw.get("capBuffTimeToAreaEffectTime", False))
            impact_damage[card] = actual_damage
            impact_hidden[card] = bool(impact.get("affectsHidden", False))
            impact_crown[card] = float(
                explicit_crown
                if explicit_crown is not None
                else native_percent_damage(actual_damage, crown_multiplier)
            )

        owner_shape = (runtime.batch_size, capacity)
        entity_shape = runtime.battle.entity_id.shape

        def owner_zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(owner_shape, dtype=dtype, device=device)

        source_card = runtime.battle.entity_card.clone()
        collision = torch.zeros(entity_shape, dtype=torch.int64, device=device)
        airborne = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        building = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        crown = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        receiver = torch.ones(
            (runtime.batch_size, size, runtime.max_entities),
            dtype=torch.bool,
            device=device,
        )
        receiver_hidden = torch.ones_like(receiver)
        has_shield = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield = torch.zeros(entity_shape, dtype=torch.float64, device=device)
        shield_kind = torch.zeros(entity_shape, dtype=torch.bool, device=device)
        shield_break = torch.zeros(entity_shape, dtype=torch.int32, device=device)
        death_supported = torch.ones(entity_shape, dtype=torch.bool, device=device)
        for row, battle in enumerate(battles):
            slots = {
                int(entity_id): slot
                for slot, entity_id in enumerate(runtime.battle.entity_id[row].tolist())
                if int(entity_id) > 0
            }
            sources: dict[int, object] = {}
            for entity_id, entity in battle.entities.items():
                slot = slots[entity_id]
                card = int(runtime.battle.entity_card[row, slot].item())
                sources.setdefault(card, entity)
                collision[row, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                airborne[row, slot] = is_airborne_target(entity)
                building[row, slot] = isinstance(entity, Building)
                crown[row, slot] = isinstance(entity, Building) and getattr(
                    entity.card_stats, "name", ""
                ) in {"Tower", "KingTower"}
                shields = [
                    mechanic
                    for mechanic in entity.mechanics
                    if type(mechanic).__name__ == "Shield"
                ]
                if shields:
                    current = getattr(shields[0], "current_shield", 0)
                    has_shield[row, slot] = True
                    shield[row, slot] = float(current)
                    shield_kind[row, slot] = type(current) is int
                    shield_break[row, slot] = int(
                        getattr(entity, "_shield_break_count", 0)
                    )
                death_supported[row, slot] = not any(
                    type(mechanic).__name__
                    in {"DeathDamage", "DeathSpawn", "DeathAreaEffect"}
                    for mechanic in entity.mechanics
                )
            for source_card_id in torch.nonzero(supported).flatten().tolist():
                source = sources.get(source_card_id)
                source_name = runtime.battle.card_names[source_card_id]
                for target_id, target in battle.entities.items():
                    slot = slots[target_id]
                    receiver[row, source_card_id, slot] = (
                        target.can_receive_area_damage(
                            source_name,
                            source_entity=source,  # type: ignore[arg-type]
                        )
                    )
                    receiver_hidden[row, source_card_id, slot] = (
                        target.can_receive_area_damage(
                            source_name,
                            affects_hidden=True,
                            source_entity=source,  # type: ignore[arg-type]
                        )
                    )

        return cls(
            TensorDeathAreaConsumerCatalog(
                supported,
                tuple(reasons),
                hits_air,
                hits_ground,
                cap,
                impact_damage,
                impact_hidden,
                impact_crown,
            ),
            owner_zeros(torch.bool),
            owner_zeros(torch.bool),
            torch.full(owner_shape, -1, dtype=torch.int64, device=device),
            owner_zeros(torch.int64),
            owner_zeros(torch.int64),
            owner_zeros(torch.int64),
            owner_zeros(torch.int8),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.float64),
            torch.ones(owner_shape, dtype=torch.float64, device=device),
            torch.ones(owner_shape, dtype=torch.float64, device=device),
            torch.ones(owner_shape, dtype=torch.float64, device=device),
            owner_zeros(torch.bool),
            owner_zeros(torch.int32),
            owner_zeros(torch.int32),
            owner_zeros(torch.bool),
            owner_zeros(torch.bool),
            runtime.battle.entity_id.clone(),
            source_card,
            runtime.battle.entity_id.clone(),
            collision,
            airborne,
            building,
            crown,
            receiver,
            receiver_hidden,
            has_shield,
            shield,
            shield_kind,
            shield_break,
            death_supported,
        )

    def clone(self) -> TensorResidentDeathAreas:
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor):
                setattr(result, descriptor.name, value.clone())
        return result

    def fork(self, rows: torch.Tensor | Sequence[int]) -> TensorResidentDeathAreas:
        selected = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if selected.ndim != 1:
            raise ValueError("death-area fork rows must be one-dimensional")
        result = copy.copy(self)
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if isinstance(value, torch.Tensor) and value.shape[0] == self.batch_size:
                setattr(result, descriptor.name, value[selected].clone())
        return result

    def reset_rows_(
        self,
        destination_rows: torch.Tensor | Sequence[int],
        source: TensorResidentDeathAreas,
        source_rows: torch.Tensor | Sequence[int] | None = None,
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
            raise ValueError("death-area reset row layout differs")
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[destination] = right[selected]

    def _copy_rows_(self, source: TensorResidentDeathAreas, rows: torch.Tensor) -> None:
        for descriptor in fields(self):
            left = getattr(self, descriptor.name)
            right = getattr(source, descriptor.name)
            if isinstance(left, torch.Tensor) and left.shape[0] == self.batch_size:
                left[rows] = right[rows]

    def consume_descriptors_(
        self,
        runtime: TensorBattleRuntime,
        descriptors: TensorDeathAreaDescriptors,
        *,
        battle_mask: torch.Tensor | None = None,
    ) -> DeathAreaConsumeResult:
        if descriptors.valid.shape[0] != self.batch_size:
            raise ValueError("death-area descriptor batch differs")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        requested = descriptors.valid & selected[:, None]
        counts = requested.sum(dim=1, dtype=torch.int64)
        duplicate = (
            requested[:, :, None]
            & self.active[:, None, :]
            & (descriptors.object_id[:, :, None] == self.object_id[:, None, :])
        ).any(dim=(1, 2))
        live_id_conflict = (
            requested[:, :, None]
            & runtime.entity_pool.active[:, None, :]
            & (
                descriptors.object_id[:, :, None]
                == runtime.battle.entity_id[:, None, :]
            )
        ).any(dim=(1, 2))
        invalid_reserved_id = (
            requested
            & (
                (descriptors.object_id <= 0)
                | (descriptors.object_id >= runtime.entity_pool.next_entity_id[:, None])
            )
        ).any(dim=1)
        capacity_rejected = (
            (counts > (~self.active).sum(dim=1))
            | (counts > (~runtime.entity_pool.active).sum(dim=1))
            | duplicate
            | live_id_conflict
            | invalid_reserved_id
        )
        working_runtime = runtime.clone()
        working_runtime.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        rows = torch.arange(self.batch_size, device=self.device)
        supported = selected & ~capacity_rejected
        free_owner = ~working.active
        free_entity = ~working_runtime.entity_pool.active
        accepted = torch.zeros_like(requested)
        for lane in range(descriptors.valid.shape[1]):
            valid = requested[:, lane] & supported
            owner_slot = _first_free(free_owner).clamp_max(self.capacity - 1)
            entity_slot = _first_free(free_entity).clamp_max(runtime.max_entities - 1)
            source_match = self.source_entity_id == descriptors.source_id[:, lane, None]
            source_found = source_match.any(dim=1)
            source_slot = source_match.to(torch.int64).argmax(dim=1)
            source_card = self.source_entity_card[rows, source_slot]
            valid &= source_found & self.catalog.supported_core[source_card]
            supported &= ~(
                requested[:, lane]
                & (~source_found | ~self.catalog.supported_core[source_card])
            )
            index = (rows[valid], owner_slot[valid])
            working.active[index] = True
            working.container[index] = (
                descriptors.activation_delay_ms[rows[valid], lane] > 0
            )
            working.entity_slot[index] = entity_slot[valid]
            working.object_id[index] = descriptors.object_id[rows[valid], lane]
            working.source_id[index] = descriptors.source_id[rows[valid], lane]
            working.source_card[index] = source_card[valid]
            for name in (
                "owner",
                "x_units",
                "y_units",
                "radius_units",
                "duration_ms",
                "activation_delay_ms",
                "interval_ms",
                "buff_duration_ms",
                "damage",
                "movement_multiplier",
                "attack_multiplier",
                "spawn_multiplier",
                "affects_hidden",
            ):
                getattr(working, name)[index] = getattr(descriptors, name)[
                    rows[valid], lane
                ]
            working.next_effect_ms[index] = torch.maximum(
                descriptors.interval_ms[rows[valid], lane],
                torch.full_like(descriptors.interval_ms[rows[valid], lane], 50),
            )
            runtime_index = (rows[valid], entity_slot[valid])
            core = working_runtime.battle
            working_runtime.entity_pool.active[runtime_index] = True
            core.entity_id[runtime_index] = descriptors.object_id[rows[valid], lane]
            core.entity_active[runtime_index] = True
            core.entity_kind[runtime_index] = 3
            core.entity_player[runtime_index] = descriptors.owner[rows[valid], lane]
            core.entity_card[runtime_index] = source_card[valid]
            core.entity_x_units[runtime_index] = descriptors.x_units[rows[valid], lane]
            core.entity_y_units[runtime_index] = descriptors.y_units[rows[valid], lane]
            core.entity_hp[runtime_index] = 1.0
            core.entity_hp_integer_kind[runtime_index] = True
            core.entity_max_hp[runtime_index] = 1.0
            core.entity_tower_slot[runtime_index] = -1
            working_runtime.phases.target_slot[runtime_index] = -1
            free_owner[rows[valid], owner_slot[valid]] = False
            free_entity[rows[valid], entity_slot[valid]] = False
            accepted[rows[valid], lane] = True
        committed = supported
        _copy_runtime_rows_(runtime, working_runtime, committed)
        self._copy_rows_(working, committed)
        return DeathAreaConsumeResult(
            committed=~selected | committed,
            accepted=accepted & committed[:, None],
            capacity_rejected=capacity_rejected,
        )

    def _overlap(
        self,
        runtime: TensorBattleRuntime,
        area_slot: torch.Tensor,
    ) -> torch.Tensor:
        rows = torch.arange(self.batch_size, device=self.device)
        x = self.x_units.gather(1, area_slot[:, None])[:, 0].to(torch.int64)
        y = self.y_units.gather(1, area_slot[:, None])[:, 0].to(torch.int64)
        radius = self.radius_units.gather(1, area_slot[:, None])[:, 0].to(torch.int64)
        target_x = runtime.battle.entity_x_units.to(torch.int64)
        target_y = runtime.battle.entity_y_units.to(torch.int64)
        dx = target_x - x[:, None]
        dy = target_y - y[:, None]
        reach = radius[:, None] + self.target_collision_radius_units
        circle = dx.square() + dy.square() < reach.square()
        closest_x = torch.minimum(
            target_x + self.target_collision_radius_units,
            torch.maximum(target_x - self.target_collision_radius_units, x[:, None]),
        )
        closest_y = torch.minimum(
            target_y + self.target_collision_radius_units,
            torch.maximum(target_y - self.target_collision_radius_units, y[:, None]),
        )
        square = (closest_x - x[:, None]).square() + (
            closest_y - y[:, None]
        ).square() < radius[:, None].square()
        del rows
        return torch.where(self.target_building, square, circle)

    def _apply_impact_(
        self,
        runtime: TensorBattleRuntime,
        area_slot: torch.Tensor,
        valid: torch.Tensor,
        damage_result: torch.Tensor,
        death_result: torch.Tensor,
    ) -> torch.Tensor:
        rows = torch.arange(self.batch_size, device=self.device)
        core = runtime.battle
        card = self.source_card.gather(1, area_slot[:, None])[:, 0]
        owner = self.owner.gather(1, area_slot[:, None])[:, 0]
        area_id = self.object_id.gather(1, area_slot[:, None])[:, 0]
        public_source = torch.where(
            self.catalog.impact_damage[card] > 0.0,
            torch.zeros_like(area_id),
            area_id,
        )
        hidden = self.catalog.impact_affects_hidden[card]
        receiver = torch.where(
            hidden[:, None],
            self.target_effect_receivable_hidden[rows, card],
            self.target_effect_receivable[rows, card],
        )
        candidates = (
            valid[:, None]
            & runtime.entity_pool.active
            & core.entity_active
            & (core.entity_player != owner[:, None])
            & ((core.entity_kind == 0) | (core.entity_kind == 1))
            & receiver
            & self._overlap(runtime, area_slot)
            & (self.catalog.impact_damage[card, None] > 0.0)
        )
        order = runtime.entity_pool.id_order(candidates)
        unsupported = torch.zeros(self.batch_size, dtype=torch.bool, device=self.device)
        for rank in range(runtime.max_entities):
            target_valid = order.valid[:, rank]
            target_slot = order.slots[:, rank].clamp_min(0)
            target_id = order.entity_ids[:, rank]
            amount = torch.where(
                self.target_crown[rows, target_slot],
                self.catalog.impact_crown_damage[card],
                self.catalog.impact_damage[card],
            )
            shielded = (
                target_valid
                & self.target_has_shield[rows, target_slot]
                & (self.target_shield[rows, target_slot] > 0.0)
            )
            next_shield = torch.clamp(
                self.target_shield[rows, target_slot] - amount, min=0.0
            )
            self.target_shield[rows[shielded], target_slot[shielded]] = next_shield[
                shielded
            ]
            self.target_shield_integer_kind[rows[shielded], target_slot[shielded]] = (
                False
            )
            broken = shielded & (next_shield <= 0.0)
            self.target_shield_break_count[rows[broken], target_slot[broken]] += 1
            hp_damage = torch.where(shielded, 0.0, amount)
            before = core.entity_hp[rows, target_slot]
            after = torch.clamp(before - hp_damage, min=0.0)
            hit_index = (rows[target_valid], target_slot[target_valid])
            core.entity_hp[hit_index] = after[target_valid]
            core.entity_hp_integer_kind[hit_index] = False
            died = target_valid & core.entity_active[rows, target_slot] & (after <= 0)
            core.entity_active[rows[died], target_slot[died]] = False
            runtime.phases.death_pending[rows[died], target_slot[died]] = True
            dealt = torch.minimum(before, hp_damage)
            damage_result[hit_index] += dealt[target_valid]
            death_result[rows[died], target_slot[died]] = True
            runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DAMAGE,
                valid=target_valid[:, None],
                source_id=public_source[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                amount=dealt[:, None],
                payload=card[:, None],
            )
            runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.DEATH,
                valid=died[:, None],
                source_id=public_source[:, None],
                target_id=target_id[:, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                payload=card[:, None],
            )
            unsupported |= (
                died & ~self.target_death_payload_supported[rows, target_slot]
            )
        return unsupported

    def _apply_effect_(
        self,
        runtime: TensorBattleRuntime,
        area_slot: torch.Tensor,
        valid: torch.Tensor,
        effect_time_remaining_ms: torch.Tensor,
    ) -> torch.Tensor:
        rows = torch.arange(self.batch_size, device=self.device)
        core = runtime.battle
        card = self.source_card.gather(1, area_slot[:, None])[:, 0]
        owner = self.owner.gather(1, area_slot[:, None])[:, 0]
        movement = self.movement_multiplier.gather(1, area_slot[:, None])[:, 0]
        attack = self.attack_multiplier.gather(1, area_slot[:, None])[:, 0]
        spawn = self.spawn_multiplier.gather(1, area_slot[:, None])[:, 0]
        buff_ms = self.buff_duration_ms.gather(1, area_slot[:, None])[:, 0].to(
            torch.int64
        )
        refresh_ms = torch.where(
            self.catalog.cap_buff_to_area[card],
            torch.minimum(buff_ms, effect_time_remaining_ms),
            buff_ms,
        )
        overlap = self._overlap(runtime, area_slot)
        haste = torch.maximum(torch.maximum(movement, attack), spawn) > 1.0
        slow = torch.minimum(torch.minimum(movement, attack), spawn) < 1.0
        receiver = torch.where(
            self.affects_hidden.gather(1, area_slot[:, None])[:, 0, None],
            self.target_effect_receivable_hidden[rows, card],
            self.target_effect_receivable[rows, card],
        )
        targets = (
            valid[:, None]
            & runtime.entity_pool.active
            & core.entity_active
            & ((core.entity_kind == 0) | (core.entity_kind == 1))
            & overlap
            & (refresh_ms[:, None] > 0)
            & torch.where(
                haste[:, None],
                core.entity_player == owner[:, None],
                (core.entity_player != owner[:, None]) & receiver,
            )
        )
        slow_targets = targets & slow[:, None]
        haste_targets = targets & haste[:, None]
        slow_matches = (
            runtime.status.slow_active
            & (runtime.status.slow_movement == movement[:, None, None])
            & (runtime.status.slow_attack == attack[:, None, None])
            & (runtime.status.slow_spawn == spawn[:, None, None])
        ).any(dim=2)
        haste_matches = (
            runtime.status.haste_active
            & (runtime.status.haste_movement == movement[:, None, None])
            & (runtime.status.haste_attack == attack[:, None, None])
            & (runtime.status.haste_spawn == spawn[:, None, None])
        ).any(dim=2)
        slow_capacity = slow_matches | (~runtime.status.slow_active).any(dim=2)
        haste_capacity = haste_matches | (~runtime.status.haste_active).any(dim=2)
        unsupported = (slow_targets & ~slow_capacity).any(dim=1) | (
            haste_targets & ~haste_capacity
        ).any(dim=1)
        accepted = valid & ~unsupported
        runtime.status.apply_slow(
            refresh_ms[:, None].to(torch.float64) / 1_000.0,
            movement[:, None],
            attack_speed_multiplier=attack[:, None],
            spawn_speed_multiplier=spawn[:, None],
            mask=slow_targets & accepted[:, None],
        )
        runtime.status.apply_haste(
            refresh_ms[:, None].to(torch.float64) / 1_000.0,
            movement[:, None],
            attack[:, None],
            spawn_speed_multiplier=spawn[:, None],
            mask=haste_targets & accepted[:, None],
        )
        ordered_slow = runtime.entity_pool.id_order(slow_targets & accepted[:, None])
        area_id = self.object_id.gather(1, area_slot[:, None])[:, 0]
        for rank in range(runtime.max_entities):
            target_valid = ordered_slow.valid[:, rank]
            target_slot = ordered_slow.slots[:, rank].clamp_min(0)
            runtime.events.append(
                phase=TickPhase.OBJECTS,
                opcode=RuntimeEventOpcode.STATUS,
                valid=target_valid[:, None],
                source_id=area_id[:, None],
                target_id=ordered_slow.entity_ids[:, rank, None],
                x_units=core.entity_x_units[rows, target_slot][:, None],
                y_units=core.entity_y_units[rows, target_slot][:, None],
                amount=(refresh_ms.to(torch.float64) / 1_000.0)[:, None],
                payload=card[:, None],
            )
        return unsupported

    def step_(
        self,
        runtime: TensorBattleRuntime,
        *,
        dt_ms: int = 50,
        battle_mask: torch.Tensor | None = None,
    ) -> DeathAreaStepResult:
        if dt_ms != 50:
            raise ValueError("retained death-area lifecycle requires one 50ms tick")
        selected = (
            runtime.supported.clone()
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("death-area battle_mask must have shape [batch]")
        character = runtime.entity_pool.active & (
            (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
        )
        identity = (~character) | (self.target_entity_id == runtime.battle.entity_id)
        next_age = self.age_ms.to(torch.int64) + 50
        container_due = (
            self.active
            & self.container
            & (next_age >= self.activation_delay_ms.to(torch.int64))
        )
        process_area = self.active & (~self.container | container_due)
        area_age = torch.where(container_due, 50, next_age)
        cards = self.source_card.clamp(0, self.catalog.supported_core.numel() - 1)
        impact_due = (
            process_area
            & ~self.impact_applied
            & (self.catalog.impact_damage[cards] > 0.0)
        )
        effect_due = process_area & torch.where(
            self.interval_ms <= 0,
            ~self.effect_snapshot_applied,
            (self.next_effect_ms.to(torch.int64) <= area_age)
            & (self.next_effect_ms < self.duration_ms),
        )
        slow_due = effect_due & (
            torch.minimum(
                torch.minimum(self.movement_multiplier, self.attack_multiplier),
                self.spawn_multiplier,
            )
            < 1.0
        )
        capacity_events = (
            container_due.sum(dim=1, dtype=torch.int64)
            + impact_due.sum(dim=1, dtype=torch.int64) * runtime.max_entities * 2
            + slow_due.sum(dim=1, dtype=torch.int64) * runtime.max_entities
        )
        free_events = runtime.events.capacity - runtime.events.count.to(torch.int64)
        capacity_rejected = selected & (
            ~identity.all(dim=1) | (capacity_events > free_events)
        )
        supported = selected & ~capacity_rejected
        speculative = runtime.clone()
        speculative.battle.rng = runtime.battle.rng.clone()
        working = self.clone()
        rows = torch.arange(self.batch_size, device=self.device)
        damage = torch.zeros_like(runtime.battle.entity_hp)
        deaths = torch.zeros_like(runtime.battle.entity_active)
        activated = torch.zeros_like(working.active)
        expired = torch.zeros_like(working.active)
        unsupported = torch.zeros_like(supported)
        order = torch.argsort(
            torch.where(
                working.active,
                working.object_id,
                torch.iinfo(torch.int64).max,
            ),
            dim=1,
            stable=True,
        )
        cleanup = torch.zeros_like(speculative.entity_pool.active)
        for rank in range(self.capacity):
            area_slot = order[:, rank]
            active = working.active.gather(1, area_slot[:, None])[:, 0] & supported
            entity_slot = working.entity_slot.gather(1, area_slot[:, None])[
                :, 0
            ].clamp_min(0)
            object_id = working.object_id.gather(1, area_slot[:, None])[:, 0]
            valid_identity = speculative.entity_pool.active[rows, entity_slot] & (
                speculative.battle.entity_id[rows, entity_slot] == object_id
            )
            unsupported |= active & ~valid_identity
            active &= valid_identity
            age = working.age_ms.gather(1, area_slot[:, None])[:, 0].to(torch.int64)
            next_age = age + dt_ms
            is_container = working.container.gather(1, area_slot[:, None])[:, 0]
            delay = working.activation_delay_ms.gather(1, area_slot[:, None])[:, 0].to(
                torch.int64
            )
            due_container = active & is_container & (next_age >= delay)
            if due_container.any():
                allocation = speculative.entity_pool.allocate(
                    due_container.to(torch.int64)
                )
                new_slot = allocation.slots[:, 0].clamp_min(0)
                new_id = allocation.entity_ids[:, 0]
                allocated = torch.zeros_like(speculative.entity_pool.active)
                allocated.scatter_(1, new_slot[:, None], due_container[:, None])
                _clear_slots_(speculative, allocated)
                index = (rows[due_container], area_slot[due_container])
                old_id = object_id.clone()
                old_slot = entity_slot.clone()
                working.container[index] = False
                working.entity_slot[index] = new_slot[due_container]
                working.object_id[index] = new_id[due_container]
                working.age_ms[index] = 0
                working.activation_delay_ms[index] = 0
                working.next_effect_ms[index] = torch.maximum(
                    working.interval_ms[index],
                    torch.full_like(working.interval_ms[index], 50),
                )
                runtime_index = (rows[due_container], new_slot[due_container])
                core = speculative.battle
                core.entity_active[runtime_index] = True
                core.entity_kind[runtime_index] = 3
                core.entity_player[runtime_index] = working.owner[index]
                core.entity_card[runtime_index] = working.source_card[index]
                core.entity_x_units[runtime_index] = working.x_units[index]
                core.entity_y_units[runtime_index] = working.y_units[index]
                core.entity_hp[runtime_index] = 1.0
                core.entity_hp_integer_kind[runtime_index] = True
                core.entity_max_hp[runtime_index] = 1.0
                core.entity_tower_slot[runtime_index] = -1
                speculative.phases.target_slot[runtime_index] = -1
                speculative.events.append(
                    phase=TickPhase.OBJECTS,
                    opcode=RuntimeEventOpcode.SPAWN,
                    valid=due_container[:, None],
                    source_id=torch.zeros_like(old_id)[:, None],
                    target_id=new_id[:, None],
                    x_units=working.x_units.gather(1, area_slot[:, None]),
                    y_units=working.y_units.gather(1, area_slot[:, None]),
                    payload=working.source_card.gather(1, area_slot[:, None]),
                )
                cleanup[rows[due_container], old_slot[due_container]] = True
                activated[rows[due_container], area_slot[due_container]] = True
            working.age_ms[
                rows[active & is_container & ~due_container],
                area_slot[active & is_container & ~due_container],
            ] = next_age[active & is_container & ~due_container].to(torch.int32)

            process_area = active & (~is_container | due_container)
            area_age_before = torch.where(due_container, 0, age)
            area_age = area_age_before + dt_ms
            working.age_ms[rows[process_area], area_slot[process_area]] = area_age[
                process_area
            ].to(torch.int32)
            impact_done = working.impact_applied.gather(1, area_slot[:, None])[:, 0]
            impact_due = process_area & ~impact_done
            unsupported |= working._apply_impact_(
                speculative, area_slot, impact_due, damage, deaths
            )
            working.impact_applied[rows[impact_due], area_slot[impact_due]] = True
            interval = working.interval_ms.gather(1, area_slot[:, None])[:, 0].to(
                torch.int64
            )
            duration = working.duration_ms.gather(1, area_slot[:, None])[:, 0].to(
                torch.int64
            )
            next_effect = working.next_effect_ms.gather(1, area_slot[:, None])[:, 0].to(
                torch.int64
            )
            snapshot = (
                process_area
                & (interval <= 0)
                & ~working.effect_snapshot_applied.gather(1, area_slot[:, None])[:, 0]
            )
            effect_due = (
                process_area
                & (interval > 0)
                & (next_effect <= area_age)
                & (next_effect < duration)
            )
            effect_mask = snapshot | effect_due
            effect_time = torch.where(
                snapshot,
                (duration - area_age).clamp_min(0),
                (duration - next_effect).clamp_min(0),
            )
            unsupported |= working._apply_effect_(
                speculative, area_slot, effect_mask, effect_time
            )
            working.effect_snapshot_applied[rows[snapshot], area_slot[snapshot]] = True
            working.next_effect_ms[rows[effect_due], area_slot[effect_due]] = (
                next_effect[effect_due] + interval[effect_due]
            ).to(torch.int32)
            area_expired = process_area & (area_age >= duration)
            cleanup[
                rows[area_expired],
                working.entity_slot[rows[area_expired], area_slot[area_expired]],
            ] = True
            working.active[rows[area_expired], area_slot[area_expired]] = False
            expired[rows[area_expired], area_slot[area_expired]] = True

        speculative.entity_pool.cleanup(cleanup)
        _clear_slots_(speculative, cleanup)
        for name in (
            "container",
            "entity_slot",
            "object_id",
            "source_id",
            "source_card",
            "owner",
            "x_units",
            "y_units",
            "radius_units",
            "duration_ms",
            "activation_delay_ms",
            "interval_ms",
            "buff_duration_ms",
            "damage",
            "movement_multiplier",
            "attack_multiplier",
            "spawn_multiplier",
            "affects_hidden",
            "age_ms",
            "next_effect_ms",
            "effect_snapshot_applied",
            "impact_applied",
        ):
            value = getattr(working, name)
            mask = expired.reshape(
                *expired.shape, *((1,) * (value.ndim - expired.ndim))
            )
            value.masked_fill_(mask, -1 if name == "entity_slot" else 0)
        commit = supported & ~unsupported
        speculative.mark_dirty(commit, phase=TickPhase.OBJECTS)
        _copy_runtime_rows_(runtime, speculative, commit)
        self._copy_rows_(working, commit)
        return DeathAreaStepResult(
            committed=~selected | commit,
            capacity_rejected=capacity_rejected,
            container_activated=activated & commit[:, None],
            expired=expired & commit[:, None],
            damage=torch.where(commit[:, None], damage, 0.0),
            deaths=deaths & commit[:, None],
        )


__all__ = [
    "DeathAreaConsumeResult",
    "DeathAreaStepResult",
    "TensorDeathAreaConsumerCatalog",
    "TensorResidentDeathAreas",
]
