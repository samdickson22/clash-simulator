"""Primitive card tables for the unified approximate Gym kernel.

The projection is deliberately mechanical: it consumes existing serialized
catalog tensors and never branches on card names or runtime Python classes.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    projectile_speed_units_per_tick: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
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
    omits_displacement: torch.Tensor
    consume_source_on_impact: torch.Tensor
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
        line_half_width_units = torch.zeros_like(
            catalog.range_units, dtype=torch.int32
        )
        projectile_speed = torch.zeros_like(catalog.range_units)
        tower_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        building_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        status_kind = torch.full_like(catalog.kind, FAST_STATUS_NONE, dtype=torch.int8)
        status_ticks = torch.zeros_like(catalog.range_units)
        effect_duration_ticks = torch.ones_like(catalog.range_units)
        damage_interval_ticks = torch.ones_like(catalog.range_units)
        initial_damage_delay_ticks = torch.zeros_like(catalog.range_units)
        damage_on_spawn_table = torch.ones_like(catalog.kind, dtype=torch.bool)
        max_damage_hits = torch.ones_like(catalog.range_units)
        status_interval_ticks = torch.ones_like(catalog.range_units)
        initial_status_delay_ticks = torch.zeros_like(catalog.range_units)
        max_status_scans = torch.ones_like(catalog.range_units)
        omits_displacement = torch.zeros_like(catalog.kind, dtype=torch.bool)
        consume_source = torch.zeros_like(catalog.kind, dtype=torch.bool)
        attacks_air = catalog.attacks_air.to(torch.bool).clone()
        attacks_ground = catalog.attacks_ground.to(torch.bool).clone()
        serialized_spell = catalog.kind == int(CardKindOpcode.SPELL)
        effect_hits_air = torch.where(
            serialized_spell, torch.ones_like(attacks_air), attacks_air
        )
        effect_hits_ground = torch.where(
            serialized_spell, torch.ones_like(attacks_ground), attacks_ground
        )
        buildings_only = catalog.buildings_only.to(torch.bool).clone()
        is_air = catalog.is_air_unit.to(torch.bool).clone()
        death_spawn_opcode = int(MECHANIC_OPCODE["DeathSpawn"])
        declares_death_spawn = (catalog.mechanic_opcode == death_spawn_opcode).any(
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
                if projectile:
                    effect_kind[card_id] = FAST_CARD_EFFECT_PROJECTILE
                    projectile_speed[card_id] = int(projectile.get("speed", 0) or 0)
                    effect_radius_units[card_id] = int(projectile.get("radius", 0) or 0)
                    # Finite non-homing projectiles with explicit swept-width
                    # and range fields compile to one line effect.  The two
                    # numeric tables are sufficient runtime dispatch; names
                    # and scalar projectile classes never enter the hot path.
                    projectile_range = int(
                        projectile.get("projectileRange", 0) or 0
                    )
                    projectile_width = int(
                        projectile.get("projectileRadius", 0) or 0
                    )
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
                    if (
                        projectile_buff_ms > 0
                        and float(projectile_buff.get("speedMultiplier", 0) or 0)
                        <= -100
                        and float(projectile_buff.get("hitSpeedMultiplier", 0) or 0)
                        <= -100
                    ):
                        status_kind[card_id] = FAST_STATUS_STUN
                        status_ticks[card_id] = (projectile_buff_ms + 49) // 50

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
                if (
                    on_hit_buff_ms > 0
                    and float(on_hit_buff.get("speedMultiplier", 0) or 0) <= -100
                    and float(on_hit_buff.get("hitSpeedMultiplier", 0) or 0) <= -100
                ):
                    status_kind[card_id] = FAST_STATUS_STUN
                    status_ticks[card_id] = (on_hit_buff_ms + 49) // 50
                if spell_projectile_data and int(catalog.kind[card_id]) == int(
                    CardKindOpcode.SPELL
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
                    buff = spell_projectile_data.get("targetBuffData") or {}
                    if (
                        float(buff.get("speedMultiplier", 0) or 0) <= -100
                        and int(spell_projectile_data.get("buffTime", 0) or 0) > 0
                    ):
                        status_kind[card_id] = FAST_STATUS_STUN
                        status_ticks[card_id] = (
                            int(spell_projectile_data["buffTime"]) + 49
                        ) // 50

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
                        has_status = speed_percent < 0 and buff_ms > 0
                        freeze_snapshot = speed_percent <= -100
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
                        status_kind[card_id] = (
                            FAST_STATUS_STUN
                            if freeze_snapshot
                            else (FAST_STATUS_SLOW if has_status else FAST_STATUS_NONE)
                        )
                        status_ticks[card_id] = (
                            max(1, (buff_ms + 49) // 50) if has_status else 0
                        )
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

                consume_source[card_id] = bool(character.get("kamikaze", False))

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
        effect_hits_air = torch.where(is_spell, effect_hits_air, attacks_air)
        effect_hits_ground = torch.where(is_spell, effect_hits_ground, attacks_ground)
        effectful = (effect_kind >= 0) & (effect_damage > 0)
        resolved_death_spawn = (
            (death_spawn_card_id > 0) & (death_spawn_count > 0) & (death_spawn_hp > 0)
        )
        # Allocation is intentionally a weaker condition than admission to
        # training. A zero-payload effect or unresolved defining death child
        # can execute structurally, but teaches a qualitatively false card.
        training_supported = torch.where(
            is_spell,
            effectful,
            ordinary & ((catalog.damage > 0) | effectful | resolved_death_spawn),
        )
        training_supported &= ~(declares_death_spawn & (death_spawn_card_id <= 0))
        training_supported &= multi_target_count <= FAST_MAX_MULTI_TARGETS
        training_supported &= chain_target_count <= FAST_MAX_CHAIN_TARGETS
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
            projectile_speed_units_per_tick=projectile_speed,
            tower_damage_multiplier=tower_multiplier,
            building_damage_multiplier=building_multiplier,
            status_kind=status_kind,
            status_duration_ticks=status_ticks,
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
            omits_displacement=omits_displacement,
            consume_source_on_impact=consume_source,
            training_supported=training_supported.to(torch.bool),
        )

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])
