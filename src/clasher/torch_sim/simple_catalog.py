"""Primitive card tables for the unified approximate Gym kernel.

The projection is deliberately mechanical: it consumes existing serialized
catalog tensors and never branches on card names or runtime Python classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json

from .catalog import (
    EFFECT_OPCODE,
    MECHANIC_OPCODE,
    CardKindOpcode,
    TensorCardCatalog,
)
from .simple_chain_topology import FAST_MAX_CHAIN_TARGETS
from .simple_effects import FAST_STATUS_NONE, FAST_STATUS_SLOW, FAST_STATUS_STUN
from .simple_fan_topology import FAST_FAN_MAX_RAYS
from .simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP

FAST_CARD_EFFECT_UNSUPPORTED = -1
FAST_CARD_EFFECT_DIRECT = 0
FAST_CARD_EFFECT_PROJECTILE = 1
FAST_CARD_EFFECT_AREA = 2
FAST_MAX_MULTI_TARGETS = 2


@dataclass(frozen=True)
class FastCardCatalog:
    """Only the ordinary deployment/combat scalars used by the fast kernel."""

    device: torch.device
    kind: torch.Tensor
    hitpoints: torch.Tensor
    damage: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hit_cooldown_ticks: torch.Tensor
    elixir_cost: torch.Tensor
    deploy_ticks: torch.Tensor
    collision_radius_units: torch.Tensor
    attacks_air: torch.Tensor
    attacks_ground: torch.Tensor
    buildings_only: torch.Tensor
    is_air: torch.Tensor
    is_hover: torch.Tensor
    mass: torch.Tensor
    summon_count: torch.Tensor
    summon_radius_units: torch.Tensor
    lifetime_ticks: torch.Tensor
    death_spawn_count: torch.Tensor
    death_spawn_card_id: torch.Tensor
    death_spawn_kind: torch.Tensor
    death_spawn_hp: torch.Tensor
    death_spawn_radius_units: torch.Tensor
    death_spawn_deploy_ticks: torch.Tensor
    shield_hitpoints: torch.Tensor
    charge_threshold_ticks: torch.Tensor
    charge_threshold_distance_units: torch.Tensor
    charge_ready_speed_multiplier: torch.Tensor
    charge_ready_damage_multiplier: torch.Tensor
    damage_ramp_enabled: torch.Tensor
    damage_ramp_stage_1_ticks: torch.Tensor
    damage_ramp_stage_2_ticks: torch.Tensor
    damage_ramp_stage_0_multiplier: torch.Tensor
    damage_ramp_stage_1_multiplier: torch.Tensor
    damage_ramp_stage_2_multiplier: torch.Tensor
    damage_ramp_retarget_grace_ticks: torch.Tensor
    deploy_w_tile_margin: torch.Tensor
    can_deploy_on_enemy_side: torch.Tensor
    effect_kind: torch.Tensor
    effect_damage: torch.Tensor
    effect_radius_units: torch.Tensor
    effect_center_on_source: torch.Tensor
    multi_target_count: torch.Tensor
    multi_repeat_primary: torch.Tensor
    chain_target_count: torch.Tensor
    chain_hop_radius_units: torch.Tensor
    line_range_units: torch.Tensor
    line_half_width_units: torch.Tensor
    fan_ray_count: torch.Tensor
    fan_range_units: torch.Tensor
    fan_radius_units: torch.Tensor
    fan_spread_degrees: torch.Tensor
    projectile_speed_units_per_tick: torch.Tensor
    rolling_enabled: torch.Tensor
    rolling_cast_speed_units_per_tick: torch.Tensor
    rolling_cast_min_distance_units: torch.Tensor
    rolling_travel_range_units: torch.Tensor
    rolling_speed_units_per_tick: torch.Tensor
    rolling_half_width_units: torch.Tensor
    rolling_half_length_units: torch.Tensor
    rolling_damage: torch.Tensor
    rolling_ground_only: torch.Tensor
    rolling_tower_damage_multiplier: torch.Tensor
    rolling_radial_push_units: torch.Tensor
    rolling_forward_push_units: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    slow_movement_multiplier: torch.Tensor
    slow_attack_multiplier: torch.Tensor
    effect_duration_ticks: torch.Tensor
    damage_interval_ticks: torch.Tensor
    initial_damage_delay_ticks: torch.Tensor
    damage_on_spawn: torch.Tensor
    max_damage_hits: torch.Tensor
    status_interval_ticks: torch.Tensor
    initial_status_delay_ticks: torch.Tensor
    max_status_scans: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    affects_hidden: torch.Tensor
    omits_displacement: torch.Tensor
    omits_recoil: torch.Tensor
    consume_source_on_impact: torch.Tensor
    kamikaze_prime_delay_ticks: torch.Tensor
    kamikaze_delay_ticks: torch.Tensor
    training_supported: torch.Tensor

    @classmethod
    def from_tensor_catalog(
        cls,
        catalog: TensorCardCatalog,
        *,
        loader: CardDataLoader | None = None,
    ) -> FastCardCatalog:
        # Serialized hit speed is milliseconds; the native Gym clock is 50 ms.
        cooldown = torch.div(
            catalog.hit_speed_ms.to(torch.int32) + 49,
            50,
            rounding_mode="floor",
        ).clamp(min=1)
        cooldown[0] = 0
        deploy_ticks = torch.div(
            catalog.deploy_time_ms.to(torch.int32) + 49,
            50,
            rounding_mode="floor",
        ).clamp(min=0)
        deploy_ticks[0] = 0
        summon_count = catalog.summon_count.to(torch.int16).clamp(min=0)
        # Native deployment uses the character collision radius when a card
        # does not serialize SummonRadius.  Keep that setup-time rule in the
        # dense table so the runtime formation remains entirely numeric.
        summon_radius_units = torch.where(
            catalog.summon_radius_units > 0,
            catalog.summon_radius_units,
            catalog.collision_radius_units,
        ).to(torch.int32)
        summon_radius_units[0] = 0
        lifetime_ticks = torch.div(
            catalog.lifetime_ms.to(torch.int32) + 49,
            50,
            rounding_mode="floor",
        ).clamp(min=0)
        lifetime_ticks[0] = 0
        death_spawn_count = torch.zeros_like(catalog.kind, dtype=torch.int32)
        death_spawn_card_id = torch.zeros_like(catalog.kind, dtype=torch.int64)
        death_spawn_kind = torch.zeros_like(catalog.kind, dtype=torch.int8)
        death_spawn_hp = torch.zeros_like(catalog.hitpoints, dtype=torch.float32)
        death_spawn_radius_units = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        death_spawn_deploy_ticks = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        shield_hitpoints = torch.zeros_like(catalog.hitpoints, dtype=torch.float32)
        charge_threshold_ticks = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        charge_threshold_distance_units = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        charge_ready_speed_multiplier = torch.ones_like(
            catalog.hitpoints, dtype=torch.float32
        )
        charge_ready_damage_multiplier = torch.ones_like(
            catalog.hitpoints, dtype=torch.float32
        )
        damage_ramp_enabled = torch.zeros_like(catalog.kind, dtype=torch.bool)
        damage_ramp_stage_1_ticks = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        damage_ramp_stage_2_ticks = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        damage_ramp_stage_0 = torch.zeros_like(catalog.hitpoints, dtype=torch.float32)
        damage_ramp_stage_1 = torch.zeros_like(catalog.hitpoints, dtype=torch.float32)
        damage_ramp_stage_2 = torch.zeros_like(catalog.hitpoints, dtype=torch.float32)
        damage_ramp_retarget_grace_ticks = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        shield_opcode = int(MECHANIC_OPCODE["Shield"])
        shield_slots = catalog.mechanic_opcode == shield_opcode
        if "shield_hp" in catalog.mechanic_parameter_names:
            shield_parameter = catalog.mechanic_parameter_names.index("shield_hp")
            shield_values = torch.nan_to_num(
                catalog.mechanic_parameters[:, :, shield_parameter], nan=0.0
            )
            shield_hitpoints = (
                torch.where(shield_slots, shield_values, 0.0)
                .amax(dim=1)
                .to(torch.float32)
            )
        ordinary_kind = torch.full_like(catalog.kind, -1, dtype=torch.int8)
        ordinary_kind = torch.where(
            (catalog.kind == int(CardKindOpcode.TROOP))
            | (catalog.kind == int(CardKindOpcode.CHAMPION)),
            FAST_KIND_TROOP,
            ordinary_kind,
        )
        ordinary_kind = torch.where(
            catalog.kind == int(CardKindOpcode.BUILDING),
            FAST_KIND_BUILDING,
            ordinary_kind,
        )

        # Start with the universally representable direct-attack primitive.
        # Richer projectile/spell data is overlaid below from serialized
        # fields. Unsupported or zero-damage shapes remain fail closed.
        effect_kind = torch.full_like(
            catalog.kind, FAST_CARD_EFFECT_UNSUPPORTED, dtype=torch.int8
        )
        ordinary = ordinary_kind >= 0
        effect_kind = torch.where(
            ordinary & (catalog.damage > 0),
            FAST_CARD_EFFECT_DIRECT,
            effect_kind,
        )
        effect_damage = catalog.damage.to(torch.float32).clone()
        effect_radius_units = torch.zeros_like(catalog.range_units)
        effect_center_on_source = torch.zeros_like(catalog.kind, dtype=torch.bool)
        multi_target_count = torch.ones_like(catalog.kind, dtype=torch.int16)
        multi_target_count[0] = 0
        multi_repeat_primary = torch.zeros_like(catalog.kind, dtype=torch.bool)
        chain_target_count = torch.zeros_like(catalog.kind, dtype=torch.int16)
        chain_hop_radius_units = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        line_range_units = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        line_half_width_units = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        fan_ray_count = torch.zeros_like(catalog.kind, dtype=torch.int16)
        fan_range_units = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        fan_radius_units = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        fan_spread_degrees = torch.zeros_like(catalog.damage, dtype=torch.float32)
        declares_fan = torch.zeros_like(catalog.kind, dtype=torch.bool)
        valid_fan = torch.zeros_like(catalog.kind, dtype=torch.bool)
        projectile_speed = torch.zeros_like(catalog.range_units)
        rolling_enabled = torch.zeros_like(catalog.kind, dtype=torch.bool)
        rolling_cast_speed = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_cast_min_distance = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_requires_spawn = torch.zeros_like(catalog.kind, dtype=torch.bool)
        rolling_travel_range = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_speed = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_half_width = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_half_length = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_damage = torch.zeros_like(catalog.damage, dtype=torch.float32)
        rolling_ground_only = torch.zeros_like(catalog.kind, dtype=torch.bool)
        rolling_tower_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        rolling_radial_push = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        rolling_forward_push = torch.zeros_like(catalog.range_units, dtype=torch.int32)
        tower_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        building_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        status_kind = torch.full_like(catalog.kind, FAST_STATUS_NONE, dtype=torch.int8)
        status_ticks = torch.zeros_like(catalog.range_units)
        slow_movement_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        slow_attack_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        effect_duration_ticks = torch.ones_like(catalog.range_units)
        damage_interval_ticks = torch.ones_like(catalog.range_units)
        initial_damage_delay_ticks = torch.zeros_like(catalog.range_units)
        damage_on_spawn_table = torch.ones_like(catalog.kind, dtype=torch.bool)
        max_damage_hits = torch.ones_like(catalog.range_units)
        status_interval_ticks = torch.ones_like(catalog.range_units)
        initial_status_delay_ticks = torch.zeros_like(catalog.range_units)
        max_status_scans = torch.ones_like(catalog.range_units)
        omits_displacement = torch.zeros_like(catalog.kind, dtype=torch.bool)
        omits_recoil = torch.zeros_like(catalog.kind, dtype=torch.bool)
        consume_source = torch.zeros_like(catalog.kind, dtype=torch.bool)
        kamikaze_delay_ticks = torch.zeros_like(catalog.range_units)
        kamikaze_prime_delay_ticks = torch.zeros_like(catalog.range_units)
        inverted_load = catalog.load_time_ms > catalog.hit_speed_ms
        first_hit_ms = torch.where(
            inverted_load,
            catalog.hit_speed_ms,
            (catalog.hit_speed_ms - catalog.load_time_ms).clamp_min(0),
        ).to(torch.int32)
        first_hit_ticks = torch.div(
            first_hit_ms + 49,
            50,
            rounding_mode="floor",
        )

        def compile_status_buff_(
            card_id: int,
            buff: dict[str, Any],
            duration_ms: int,
        ) -> None:
            """Compile serialized negative movement/attack axes without names."""

            movement_percent = float(buff.get("speedMultiplier", 0) or 0)
            attack_percent = float(buff.get("hitSpeedMultiplier", 0) or 0)
            has_slow = duration_ms > 0 and (movement_percent < 0 or attack_percent < 0)
            if not has_slow:
                return
            freezes_actions = movement_percent <= -100 and attack_percent <= -100
            status_kind[card_id] = (
                FAST_STATUS_STUN if freezes_actions else FAST_STATUS_SLOW
            )
            status_ticks[card_id] = (duration_ms + 49) // 50
            slow_movement_multiplier[card_id] = max(0.0, 1.0 + movement_percent / 100.0)
            slow_attack_multiplier[card_id] = max(0.0, 1.0 + attack_percent / 100.0)

        attacks_air = catalog.attacks_air.to(torch.bool).clone()
        attacks_ground = catalog.attacks_ground.to(torch.bool).clone()
        serialized_spell = catalog.kind == int(CardKindOpcode.SPELL)
        effect_hits_air = torch.where(
            serialized_spell, torch.ones_like(attacks_air), attacks_air
        )
        effect_hits_ground = torch.where(
            serialized_spell, torch.ones_like(attacks_ground), attacks_ground
        )
        effect_affects_hidden = torch.zeros_like(catalog.kind, dtype=torch.bool)
        buildings_only = catalog.buildings_only.to(torch.bool).clone()
        is_air = catalog.is_air_unit.to(torch.bool).clone()
        death_spawn_opcode = int(MECHANIC_OPCODE["DeathSpawn"])
        declares_death_spawn = (catalog.mechanic_opcode == death_spawn_opcode).any(
            dim=1
        )
        damage_ramp_opcode = int(MECHANIC_OPCODE["DamageRamp"])
        declares_damage_ramp = (catalog.mechanic_opcode == damage_ramp_opcode).any(
            dim=1
        )

        # ProjectileLaunch is itself a serialized primitive, so spell cards
        # can remain useful even when the optional source-data loader is not
        # supplied. The loader overlay adds character projectiles and shapes
        # (waves/grouped projectiles) not retained by TensorCardCatalog v1.
        projectile_opcode = int(EFFECT_OPCODE["ProjectileLaunch"])
        projectile_slots = catalog.effect_opcode == projectile_opcode
        has_projectile = projectile_slots.any(dim=1)

        def effect_parameter(name: str) -> torch.Tensor:
            try:
                parameter = catalog.effect_parameter_names.index(name)
            except ValueError:
                return torch.zeros_like(catalog.damage)
            values = torch.nan_to_num(
                catalog.effect_parameters[:, :, parameter], nan=0.0
            )
            return torch.where(projectile_slots, values, 0.0).amax(dim=1)

        serialized_damage = effect_parameter("damage")
        serialized_radius = effect_parameter("splash_radius_tiles")
        serialized_speed = effect_parameter("travel_speed")
        spell_projectile = (
            (catalog.kind == int(CardKindOpcode.SPELL))
            & has_projectile
            & (serialized_damage > 0)
        )
        effect_kind = torch.where(
            spell_projectile, FAST_CARD_EFFECT_PROJECTILE, effect_kind
        )
        effect_damage = torch.where(
            spell_projectile, serialized_damage.to(torch.float32), effect_damage
        )
        effect_radius_units = torch.where(
            spell_projectile,
            torch.round(serialized_radius * 1_000.0).to(torch.int32),
            effect_radius_units,
        )
        projectile_speed = torch.where(
            spell_projectile,
            torch.round(serialized_speed * 50.0).to(torch.int32),
            projectile_speed,
        )

        if loader is not None:
            # This is setup-time serialization only. Runtime kernels consume
            # the resulting tensors and never branch on card identities.
            definitions = loader.load_card_definitions()
            for card_id, name in enumerate(catalog.names[1:], start=1):
                card = loader.get_card(name)
                if card is None:
                    continue
                raw = card._raw_entry or {}
                target_type = str(getattr(card, "target_type", "") or "")
                attacks_air[card_id] = (
                    bool(getattr(card, "attacks_air", False))
                    or target_type == "TID_TARGETS_AIR_AND_GROUND"
                )
                attacks_ground[card_id] = bool(
                    getattr(card, "attacks_ground", False)
                ) or target_type in {
                    "TID_TARGETS_GROUND",
                    "TID_TARGETS_AIR_AND_GROUND",
                    "TID_TARGETS_BUILDINGS",
                }
                buildings_only[card_id] = target_type == "TID_TARGETS_BUILDINGS"
                charge_range = int(getattr(card, "charge_range", 0) or 0)
                if charge_range > 0:
                    # Serialized charge work is measured in ten-unit chunks;
                    # the simple mover accumulates absolute logic distance.
                    charge_threshold_distance_units[card_id] = charge_range * 10
                    charge_ready_speed_multiplier[card_id] = max(
                        0.0,
                        float(getattr(card, "charge_speed_multiplier", 100) or 100)
                        / 100.0,
                    )
                    base_damage = float(
                        getattr(card, "scaled_damage", 0.0)
                        or getattr(card, "damage", 0.0)
                        or 0.0
                    )
                    charged_damage = float(
                        getattr(card, "scaled_damage_special", 0.0)
                        or getattr(card, "damage_special", 0.0)
                        or base_damage
                    )
                    if base_damage > 0:
                        charge_ready_damage_multiplier[card_id] = max(
                            0.0, charged_damage / base_damage
                        )
                character = (
                    raw.get("summonCharacterData") or raw.get("summonSpellData") or {}
                )
                if bool(declares_damage_ramp[card_id]):
                    definition = definitions.get(name)
                    ramps = (
                        [
                            mechanic
                            for mechanic in definition.mechanics
                            if type(mechanic).__name__ == "DamageRamp"
                        ]
                        if definition is not None
                        else []
                    )
                    ramp_stages = (
                        tuple(getattr(ramps[0], "stages", ()))
                        if len(ramps) == 1
                        else ()
                    )
                    if len(ramp_stages) == 3:
                        stages = ramp_stages
                        times = tuple(int(stage[0]) for stage in stages)
                        scaler = getattr(card, "get_scaled_stat", None)
                        scaled = tuple(
                            float(scaler(stage[1]))
                            if callable(scaler)
                            else float(stage[1])
                            for stage in stages
                        )
                        valid_ramp = (
                            times[0] == 0
                            and 0 < times[1] <= times[2]
                            and all(value > 0.0 for value in scaled)
                        )
                        if valid_ramp:
                            damage_ramp_enabled[card_id] = True
                            damage_ramp_stage_1_ticks[card_id] = (times[1] + 49) // 50
                            damage_ramp_stage_2_ticks[card_id] = (times[2] + 49) // 50
                            damage_ramp_stage_0[card_id] = scaled[0]
                            damage_ramp_stage_1[card_id] = scaled[1]
                            damage_ramp_stage_2[card_id] = scaled[2]
                            retarget_ms = max(
                                0, int(getattr(card, "retarget_time", 0) or 0)
                            )
                            damage_ramp_retarget_grace_ticks[card_id] = (
                                retarget_ms + 49
                            ) // 50
                child_name = getattr(card, "death_spawn_character", None)
                if child_name:
                    declares_death_spawn[card_id] = True
                child_id = catalog.name_to_id.get(str(child_name), 0)
                if child_id > 0:
                    # Exact typed identity is mandatory. Internal-only child
                    # names absent from this catalog remain all-zero/fail closed.
                    death_spawn_count[card_id] = int(
                        getattr(card, "death_spawn_count", None) or 1
                    )
                    death_spawn_card_id[card_id] = child_id
                    death_spawn_kind[card_id] = ordinary_kind[child_id]
                    death_spawn_hp[card_id] = catalog.hitpoints[child_id]
                    death_spawn_radius_units[card_id] = round(
                        float(getattr(card, "death_spawn_radius", 0.0) or 0.0) * 1_000.0
                    )
                    death_spawn_deploy_ticks[card_id] = (
                        int(getattr(card, "death_spawn_deploy_time", 0) or 0) + 49
                    ) // 50
                projectile = character.get("projectileData") or {}
                spell_projectile_data = raw.get("projectileData") or {}
                area_data = raw.get("areaEffectObjectData") or {}
                rolling_projectile = (
                    spell_projectile_data.get("spawnProjectileData") or {}
                )
                effect_affects_hidden[card_id] = bool(
                    raw.get("affectsHidden", False)
                    or character.get("affectsHidden", False)
                    or projectile.get("affectsHidden", False)
                    or spell_projectile_data.get("affectsHidden", False)
                    or area_data.get("affectsHidden", False)
                    or rolling_projectile.get("affectsHidden", False)
                )
                if rolling_projectile and int(catalog.kind[card_id]) == int(
                    CardKindOpcode.SPELL
                ):
                    rolling_target = str(rolling_projectile.get("tidTarget", "") or "")
                    rolling_raw_damage = int(rolling_projectile.get("damage", 0) or 0)
                    rolling_scaled_damage = float(
                        card.get_scaled_stat(rolling_raw_damage) or 0.0
                    )
                    rolling_range = int(
                        rolling_projectile.get("projectileRange", 0) or 0
                    )
                    rolling_width = int(
                        rolling_projectile.get(
                            "projectileRadius",
                            rolling_projectile.get("radius", 0),
                        )
                        or 0
                    )
                    rolling_child_speed = int(rolling_projectile.get("speed", 0) or 0)
                    rolling_shape = (
                        rolling_scaled_damage > 0.0
                        and rolling_range > 0
                        and rolling_width > 0
                        and rolling_child_speed > 0
                        and "GROUND" in rolling_target
                    )
                    if rolling_shape:
                        rolling_spell = create_spell_from_json(raw)
                        rolling_cast_speed[card_id] = round(rolling_spell.casting_speed * 50)
                        rolling_cast_min_distance[card_id] = round(rolling_spell.casting_min_distance * 1000)
                        rolling_half_length[card_id] = round(rolling_spell.radius_y * 1000)
                        rolling_enabled[card_id] = True
                        rolling_requires_spawn[card_id] = bool(
                            rolling_projectile.get("spawnCharacterData")
                        )
                        rolling_travel_range[card_id] = rolling_range
                        rolling_speed[card_id] = rolling_child_speed
                        rolling_half_width[card_id] = rolling_width
                        rolling_damage[card_id] = rolling_scaled_damage
                        rolling_ground_only[card_id] = True
                        rolling_forward_push[card_id] = int(
                            rolling_projectile.get("pushback", 0) or 0
                        )
                        crown_percent = float(
                            rolling_projectile.get("crownTowerDamagePercent", 0) or 0
                        )
                        rolling_tower_multiplier[card_id] = max(
                            0.0, 1.0 + crown_percent / 100.0
                        )
                        effect_kind[card_id] = FAST_CARD_EFFECT_UNSUPPORTED
                        effect_damage[card_id] = 0.0
                if projectile:
                    effect_kind[card_id] = FAST_CARD_EFFECT_PROJECTILE
                    projectile_speed[card_id] = int(projectile.get("speed", 0) or 0)
                    effect_radius_units[card_id] = int(projectile.get("radius", 0) or 0)
                    # Finite non-homing projectiles with explicit swept-width
                    # and range fields compile to one line effect.  The two
                    # numeric tables are sufficient runtime dispatch; names
                    # and scalar projectile classes never enter the hot path.
                    projectile_range = int(projectile.get("projectileRange", 0) or 0)
                    projectile_width = int(projectile.get("projectileRadius", 0) or 0)
                    explicit_non_homing = projectile.get("homing") is False
                    if (
                        projectile_range > 1
                        and projectile_width > 0
                        and explicit_non_homing
                    ):
                        line_range_units[card_id] = projectile_range
                        line_half_width_units[card_id] = projectile_width
                        # Directional push remains an explicit fidelity flag.
                        # Line damage is useful for the practical Gym without
                        # pretending that displacement has been implemented.
                        omits_displacement[card_id] |= bool(
                            int(projectile.get("pushback", 0) or 0)
                        )
                    serialized_chain_count = int(
                        projectile.get("chainedHitCount", 0) or 0
                    )
                    serialized_chain_radius = int(
                        projectile.get("chainedHitRadius", 0) or 0
                    )
                    if serialized_chain_count > 1 and serialized_chain_radius > 0:
                        chain_target_count[card_id] = serialized_chain_count
                        chain_hop_radius_units[card_id] = serialized_chain_radius
                    projectile_buff = projectile.get("targetBuffData") or {}
                    projectile_buff_ms = int(projectile.get("buffTime", 0) or 0)
                    compile_status_buff_(card_id, projectile_buff, projectile_buff_ms)

                    # A projectile can serialize a second projectile payload
                    # emitted at its impact point. Compile that payload as one
                    # bounded fan primitive rather than materializing five
                    # independent effects or dispatching on the source card.
                    child_projectile = projectile.get("spawnProjectileData") or {}
                    if child_projectile:
                        declares_fan[card_id] = True
                        child_count = int(child_projectile.get("spawnCount", 0) or 0)
                        child_range = int(
                            child_projectile.get("projectileRange", 0) or 0
                        )
                        child_radius = int(
                            child_projectile.get(
                                "projectileRadius",
                                child_projectile.get("radius", 0),
                            )
                            or 0
                        )
                        child_spread = float(
                            child_projectile.get("spawnRadius", 0) or 0
                        )
                        raw_child_damage = int(child_projectile.get("damage", 0) or 0)
                        scaled_child_damage = float(
                            card.get_scaled_stat(raw_child_damage) or 0.0
                        )
                        child_valid = (
                            1 <= child_count <= FAST_FAN_MAX_RAYS
                            and child_range > 0
                            and child_radius >= 0
                            and child_spread >= 0.0
                            and scaled_child_damage > 0.0
                        )
                        valid_fan[card_id] = child_valid
                        if child_valid:
                            fan_ray_count[card_id] = child_count
                            fan_range_units[card_id] = child_range
                            fan_radius_units[card_id] = child_radius
                            fan_spread_degrees[card_id] = child_spread
                            effect_damage[card_id] = scaled_child_damage
                            # Fan topology replaces the carrier's ordinary
                            # primary/circle damage at impact.
                            effect_radius_units[card_id] = 0
                            child_target = str(
                                child_projectile.get("tidTarget", "") or ""
                            )
                            if "AIR_AND_GROUND" in child_target:
                                effect_hits_air[card_id] = True
                                effect_hits_ground[card_id] = True
                            elif "AIR" in child_target:
                                effect_hits_air[card_id] = True
                                effect_hits_ground[card_id] = False
                            elif "GROUND" in child_target:
                                effect_hits_air[card_id] = False
                                effect_hits_ground[card_id] = True
                            else:
                                effect_hits_air[card_id] = bool(
                                    child_projectile.get("hitsAir", True)
                                )
                                effect_hits_ground[card_id] = bool(
                                    child_projectile.get("hitsGround", True)
                                )
                        else:
                            effect_kind[card_id] = FAST_CARD_EFFECT_UNSUPPORTED
                            effect_damage[card_id] = 0.0

                # Attack pushback/recoil is deliberately outside fan damage.
                # Keep it visible as an explicit fidelity omission until the
                # movement owner gains a generalized recoil primitive.
                omits_recoil[card_id] = bool(
                    float(getattr(card, "attack_pushback", 0.0) or 0.0)
                )

                # Ordinary attack topology is fully serialized on the spawned
                # character.  A target-centered radius covers melee and ranged
                # splash; ``selfAsAoeCenter`` moves only the circle anchor.
                # ``multipleTargets`` is distinct from presentation-only
                # ``multipleProjectiles`` and may repeat the primary when the
                # payload explicitly requests ``allTargetsHit``.
                area_damage_radius = int(character.get("areaDamageRadius", 0) or 0)
                if area_damage_radius > 0:
                    effect_radius_units[card_id] = area_damage_radius
                    effect_center_on_source[card_id] = bool(
                        character.get("selfAsAoeCenter", False)
                    )
                target_count = max(
                    1,
                    int(character.get("multipleTargets", 1) or 1),
                )
                multi_target_count[card_id] = target_count
                multi_repeat_primary[card_id] = bool(
                    target_count > 1 and character.get("allTargetsHit", False)
                )

                # Reuse the existing status primitive for serialized on-hit
                # buffs.  This keeps multi-recipient effects compositionally
                # correct without adding an Electro-Wizard-specific branch.
                on_hit_buff = character.get("buffOnDamageData") or {}
                on_hit_buff_ms = int(character.get("buffOnDamageTime", 0) or 0)
                compile_status_buff_(card_id, on_hit_buff, on_hit_buff_ms)
                if (
                    spell_projectile_data
                    and int(catalog.kind[card_id]) == int(CardKindOpcode.SPELL)
                    and not bool(rolling_enabled[card_id])
                ):
                    waves = int(raw.get("projectileWaves", 1) or 1)
                    grouped = int(raw.get("multipleProjectiles", 1) or 1) > 1
                    effect_kind[card_id] = (
                        FAST_CARD_EFFECT_AREA
                        if waves > 1 or grouped
                        else FAST_CARD_EFFECT_PROJECTILE
                    )
                    effect_damage[card_id] = (
                        float(spell_projectile_data.get("damage", 0) or 0) * waves
                    )
                    effect_radius_units[card_id] = int(
                        (
                            raw.get("radius")
                            if waves > 1 or grouped
                            else spell_projectile_data.get("radius")
                        )
                        or 0
                    )
                    projectile_speed[card_id] = int(
                        spell_projectile_data.get("speed", 0) or 0
                    )
                    crown_percent = float(
                        spell_projectile_data.get("crownTowerDamagePercent", 0) or 0
                    )
                    tower_multiplier[card_id] = max(0.0, 1.0 + crown_percent / 100.0)
                    if waves == 1 and not grouped:
                        spell_payload = create_spell_from_json(raw)
                        effect_damage[card_id] = float(spell_payload.damage)
                        crown_damage = getattr(spell_payload, "crown_tower_damage", None)
                        if crown_damage is not None and spell_payload.damage > 0:
                            tower_multiplier[card_id] = float(crown_damage) / float(spell_payload.damage)
                    buff = spell_projectile_data.get("targetBuffData") or {}
                    compile_status_buff_(
                        card_id,
                        buff,
                        int(spell_projectile_data.get("buffTime", 0) or 0),
                    )

                # Compile center-targeted spell areas from their normalized
                # serialized payload. Complex spawn/action groups remain
                # closed: an AOE that silently omits its spawned unit is not a
                # truthful training primitive. Attraction is admitted as a
                # declared approximation because damage/cadence remain useful.
                if area_data and int(catalog.kind[card_id]) == int(
                    CardKindOpcode.SPELL
                ):
                    nested_action = area_data.get("onStartingActionData")
                    nested_projectile = area_data.get("projectileData") or {}
                    spawns_character = bool(
                        nested_projectile.get("spawnCharacterData")
                        or nested_projectile.get("spawnCharacterCount")
                    )
                    if nested_action or spawns_character:
                        effect_kind[card_id] = FAST_CARD_EFFECT_UNSUPPORTED
                        effect_damage[card_id] = 0.0
                        max_damage_hits[card_id] = 0
                        max_status_scans[card_id] = 0
                    else:
                        spell = create_spell_from_json(raw)
                        duration_s = max(
                            0.05,
                            float(getattr(spell, "duration", 0.0) or 0.05),
                        )
                        duration_ticks = max(1, round(duration_s / 0.05))
                        damage_per_hit = float(
                            getattr(spell, "damage_per_hit", 0.0)
                            or getattr(spell, "damage", 0.0)
                            or 0.0
                        )
                        interval_s = float(
                            getattr(spell, "damage_tick_interval", 0.0) or 0.0
                        )
                        interval = max(1, round(interval_s / 0.05))
                        damage_on_spawn = (
                            bool(getattr(spell, "damage_on_spawn", False))
                            or interval_s <= 0.0
                        )
                        delay_s = getattr(spell, "initial_damage_delay", None)
                        delay = (
                            max(0, round(float(delay_s) / 0.05))
                            if delay_s is not None
                            else (0 if damage_on_spawn else interval)
                        )
                        declared_hits = int(getattr(spell, "max_damage_ticks", 0) or 0)
                        hits = declared_hits or (
                            max(1, int(duration_s / interval_s + 1e-9))
                            if damage_per_hit > 0 and interval_s > 0
                            else int(damage_per_hit > 0)
                        )
                        buff = area_data.get("buffData") or {}
                        speed_percent = float(buff.get("speedMultiplier", 0) or 0)
                        buff_ms = int(area_data.get("buffTime", 0) or 0)
                        effect_interval_ms = int(area_data.get("hitSpeed", 50) or 50)
                        attack_percent = float(buff.get("hitSpeedMultiplier", 0) or 0)
                        has_status = (
                            speed_percent < 0 or attack_percent < 0
                        ) and buff_ms > 0
                        freeze_snapshot = (
                            speed_percent <= -100 and attack_percent <= -100
                        )
                        effect_kind[card_id] = FAST_CARD_EFFECT_AREA
                        effect_damage[card_id] = damage_per_hit
                        effect_radius_units[card_id] = int(
                            area_data.get("radius", raw.get("radius", 0)) or 0
                        )
                        effect_duration_ticks[card_id] = duration_ticks
                        damage_interval_ticks[card_id] = interval
                        # Allocation and the first effect advance share one
                        # native frame, so store the countdown after that
                        # frame. This keeps N-tick serialized deadlines N
                        # runtime steps apart without extending the area.
                        initial_damage_delay_ticks[card_id] = max(0, delay - 1)
                        damage_on_spawn_table[card_id] = damage_on_spawn
                        max_damage_hits[card_id] = hits
                        compile_status_buff_(card_id, buff, buff_ms)
                        status_interval_ticks[card_id] = max(
                            1, (effect_interval_ms + 49) // 50
                        )
                        initial_status_delay_ticks[card_id] = (
                            0
                            if freeze_snapshot
                            else max(0, int(status_interval_ticks[card_id]) - 1)
                        )
                        max_status_scans[card_id] = (
                            1
                            if freeze_snapshot
                            else (
                                max(
                                    1,
                                    duration_ticks
                                    // int(status_interval_ticks[card_id]),
                                )
                                if has_status
                                else 0
                            )
                        )
                        effect_hits_air[card_id] = bool(
                            getattr(spell, "hits_air", True)
                        )
                        effect_hits_ground[card_id] = bool(
                            getattr(spell, "hits_ground", True)
                        )
                        crown_damage = getattr(spell, "crown_tower_damage", None)
                        building_damage = getattr(spell, "building_damage", None)
                        tower_multiplier[card_id] = (
                            max(0.0, float(crown_damage) / damage_per_hit)
                            if crown_damage is not None and damage_per_hit > 0
                            else max(
                                0.0,
                                float(
                                    getattr(spell, "crown_tower_damage_multiplier", 1.0)
                                    or 0.0
                                ),
                            )
                        )
                        building_multiplier[card_id] = (
                            max(0.0, float(building_damage) / damage_per_hit)
                            if building_damage is not None and damage_per_hit > 0
                            else max(
                                0.0,
                                float(
                                    getattr(spell, "building_damage_multiplier", 1.0)
                                    or 0.0
                                ),
                            )
                        )
                        omits_displacement[card_id] = bool(
                            float(getattr(spell, "attract_percentage", 0.0) or 0.0)
                            or float(getattr(spell, "push_speed_factor", 0.0) or 0.0)
                        )

                is_kamikaze = bool(character.get("kamikaze", False))
                consume_source[card_id] = is_kamikaze
                if is_kamikaze:
                    delay_ms = int(character.get("kamikazeTime", 0) or 0)
                    kamikaze_delay_ticks[card_id] = (
                        (delay_ms + 49) // 50 if delay_ms > 0 else 0
                    )
                    if delay_ms > 0:
                        kamikaze_prime_delay_ticks[card_id] = first_hit_ticks[card_id]

                # Serialized attack mechanics can refine the generic payload
                # without card-name cases. Stun/freeze share the simple Gym's
                # movement-stopping primitive.
                mechanic_count = int(catalog.mechanic_count[card_id])
                for mechanic_slot in range(mechanic_count):
                    opcode = int(catalog.mechanic_opcode[card_id, mechanic_slot])
                    if opcode not in {
                        int(MECHANIC_OPCODE["Stun"]),
                        int(MECHANIC_OPCODE["IceSpiritFreeze"]),
                    }:
                        continue
                    status_kind[card_id] = FAST_STATUS_STUN
                    duration_name = (
                        "stun_duration_ms"
                        if opcode == int(MECHANIC_OPCODE["Stun"])
                        else "freeze_duration_ms"
                    )
                    if duration_name in catalog.mechanic_parameter_names:
                        parameter = catalog.mechanic_parameter_names.index(
                            duration_name
                        )
                        mechanic_duration = catalog.mechanic_parameters[
                            card_id, mechanic_slot, parameter
                        ]
                        if not bool(torch.isnan(mechanic_duration)):
                            status_ticks[card_id] = (
                                mechanic_duration.to(torch.int32) + 49
                            ) // 50
                    if opcode == int(MECHANIC_OPCODE["IceSpiritFreeze"]):
                        radius_parameter = catalog.mechanic_parameter_names.index(
                            "freeze_radius"
                        )
                        effect_radius_units[card_id] = torch.round(
                            catalog.mechanic_parameters[
                                card_id, mechanic_slot, radius_parameter
                            ]
                            * 1_000.0
                        ).to(torch.int32)
                        consume_source[card_id] = True
        is_spell = catalog.kind == int(CardKindOpcode.SPELL)
        # Character payload inspection above is more complete than the compact
        # TensorCardCatalog attack planes (notably splash attackers and
        # kamikaze units), so finalize ordinary effect planes after that pass.
        preserve_payload_planes = is_spell | declares_fan
        effect_hits_air = torch.where(
            preserve_payload_planes, effect_hits_air, attacks_air
        )
        effect_hits_ground = torch.where(
            preserve_payload_planes, effect_hits_ground, attacks_ground
        )
        # A ramp's first stage is the one ordinary effect payload. Later
        # stages remain multipliers composed immediately before allocation.
        # This preserves one damage path even if a future loader exposes a
        # presentation projectile with a different scalar damage field.
        effect_damage = torch.where(
            damage_ramp_enabled,
            damage_ramp_stage_0,
            effect_damage,
        )
        safe_ramp_base = damage_ramp_stage_0.clamp(min=torch.finfo(torch.float32).tiny)
        damage_ramp_stage_0_multiplier = torch.where(
            damage_ramp_enabled,
            damage_ramp_stage_0 / safe_ramp_base,
            torch.ones_like(damage_ramp_stage_0),
        )
        damage_ramp_stage_1_multiplier = torch.where(
            damage_ramp_enabled,
            damage_ramp_stage_1 / safe_ramp_base,
            torch.ones_like(damage_ramp_stage_1),
        )
        damage_ramp_stage_2_multiplier = torch.where(
            damage_ramp_enabled,
            damage_ramp_stage_2 / safe_ramp_base,
            torch.ones_like(damage_ramp_stage_2),
        )
        effectful = (effect_kind >= 0) & (effect_damage > 0)
        resolved_death_spawn = (
            (death_spawn_card_id > 0) & (death_spawn_count > 0) & (death_spawn_hp > 0)
        )
        # Allocation is intentionally a weaker condition than admission to
        # training. A zero-payload effect or unresolved defining death child
        # can execute structurally, but teaches a qualitatively false card.
        training_supported = torch.where(
            is_spell,
            effectful | (rolling_enabled & ~rolling_requires_spawn),
            ordinary & ((catalog.damage > 0) | effectful | resolved_death_spawn),
        )
        training_supported &= ~(declares_death_spawn & (death_spawn_card_id <= 0))
        training_supported &= multi_target_count <= FAST_MAX_MULTI_TARGETS
        training_supported &= chain_target_count <= FAST_MAX_CHAIN_TARGETS
        training_supported &= ~declares_fan | valid_fan
        training_supported &= ~declares_damage_ramp | damage_ramp_enabled
        training_supported[0] = False

        return cls(
            device=catalog.kind.device,
            kind=ordinary_kind,
            hitpoints=catalog.hitpoints.to(torch.float32),
            damage=catalog.damage.to(torch.float32),
            range_units=catalog.range_units.to(torch.int32),
            sight_range_units=catalog.sight_range_units.to(torch.int32),
            speed_units_per_tick=catalog.speed_units_per_tick.to(torch.int32),
            hit_cooldown_ticks=cooldown,
            elixir_cost=catalog.elixir.to(torch.float32),
            deploy_ticks=deploy_ticks,
            collision_radius_units=catalog.collision_radius_units.to(torch.int32),
            attacks_air=attacks_air,
            attacks_ground=attacks_ground,
            buildings_only=buildings_only,
            is_air=is_air,
            is_hover=catalog.is_hover_unit.to(torch.bool),
            mass=catalog.mass.to(torch.float32).clamp_min(0.1),
            summon_count=summon_count,
            summon_radius_units=summon_radius_units,
            lifetime_ticks=lifetime_ticks,
            death_spawn_count=death_spawn_count,
            death_spawn_card_id=death_spawn_card_id,
            death_spawn_kind=death_spawn_kind,
            death_spawn_hp=death_spawn_hp,
            death_spawn_radius_units=death_spawn_radius_units,
            death_spawn_deploy_ticks=death_spawn_deploy_ticks,
            shield_hitpoints=shield_hitpoints,
            charge_threshold_ticks=charge_threshold_ticks,
            charge_threshold_distance_units=charge_threshold_distance_units,
            charge_ready_speed_multiplier=charge_ready_speed_multiplier,
            charge_ready_damage_multiplier=charge_ready_damage_multiplier,
            damage_ramp_enabled=damage_ramp_enabled,
            damage_ramp_stage_1_ticks=damage_ramp_stage_1_ticks,
            damage_ramp_stage_2_ticks=damage_ramp_stage_2_ticks,
            damage_ramp_stage_0_multiplier=damage_ramp_stage_0_multiplier,
            damage_ramp_stage_1_multiplier=damage_ramp_stage_1_multiplier,
            damage_ramp_stage_2_multiplier=damage_ramp_stage_2_multiplier,
            damage_ramp_retarget_grace_ticks=(damage_ramp_retarget_grace_ticks),
            deploy_w_tile_margin=catalog.deploy_w_tile_margin.to(torch.int8),
            can_deploy_on_enemy_side=catalog.can_deploy_on_enemy_side.to(torch.bool),
            effect_kind=effect_kind,
            effect_damage=effect_damage,
            effect_radius_units=effect_radius_units,
            effect_center_on_source=effect_center_on_source,
            multi_target_count=multi_target_count,
            multi_repeat_primary=multi_repeat_primary,
            chain_target_count=chain_target_count,
            chain_hop_radius_units=chain_hop_radius_units,
            line_range_units=line_range_units,
            line_half_width_units=line_half_width_units,
            fan_ray_count=fan_ray_count,
            fan_range_units=fan_range_units,
            fan_radius_units=fan_radius_units,
            fan_spread_degrees=fan_spread_degrees,
            projectile_speed_units_per_tick=projectile_speed,
            rolling_enabled=rolling_enabled,
            rolling_cast_speed_units_per_tick=rolling_cast_speed,
            rolling_cast_min_distance_units=rolling_cast_min_distance,
            rolling_travel_range_units=rolling_travel_range,
            rolling_speed_units_per_tick=rolling_speed,
            rolling_half_width_units=rolling_half_width,
            rolling_half_length_units=rolling_half_length,
            rolling_damage=rolling_damage,
            rolling_ground_only=rolling_ground_only,
            rolling_tower_damage_multiplier=rolling_tower_multiplier,
            rolling_radial_push_units=rolling_radial_push,
            rolling_forward_push_units=rolling_forward_push,
            tower_damage_multiplier=tower_multiplier,
            building_damage_multiplier=building_multiplier,
            status_kind=status_kind,
            status_duration_ticks=status_ticks,
            slow_movement_multiplier=slow_movement_multiplier,
            slow_attack_multiplier=slow_attack_multiplier,
            effect_duration_ticks=effect_duration_ticks,
            damage_interval_ticks=damage_interval_ticks,
            initial_damage_delay_ticks=initial_damage_delay_ticks,
            damage_on_spawn=damage_on_spawn_table,
            max_damage_hits=max_damage_hits,
            status_interval_ticks=status_interval_ticks,
            initial_status_delay_ticks=initial_status_delay_ticks,
            max_status_scans=max_status_scans,
            hits_air=effect_hits_air,
            hits_ground=effect_hits_ground,
            affects_hidden=effect_affects_hidden,
            omits_displacement=omits_displacement,
            omits_recoil=omits_recoil,
            consume_source_on_impact=consume_source,
            kamikaze_prime_delay_ticks=kamikaze_prime_delay_ticks,
            kamikaze_delay_ticks=kamikaze_delay_ticks,
            training_supported=training_supported.to(torch.bool),
        )

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])
