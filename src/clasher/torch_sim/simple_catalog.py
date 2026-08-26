"""Primitive card tables for the unified approximate Gym kernel.

The projection is deliberately mechanical: it consumes existing serialized
catalog tensors and never branches on card names or runtime Python classes.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from clasher.data import CardDataLoader

from .catalog import (
    EFFECT_OPCODE,
    MECHANIC_OPCODE,
    CardKindOpcode,
    TensorCardCatalog,
)
from .simple_effects import FAST_STATUS_NONE, FAST_STATUS_STUN
from .simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP

FAST_CARD_EFFECT_UNSUPPORTED = -1
FAST_CARD_EFFECT_DIRECT = 0
FAST_CARD_EFFECT_PROJECTILE = 1
FAST_CARD_EFFECT_AREA = 2


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
    deploy_w_tile_margin: torch.Tensor
    can_deploy_on_enemy_side: torch.Tensor
    effect_kind: torch.Tensor
    effect_damage: torch.Tensor
    effect_radius_units: torch.Tensor
    projectile_speed_units_per_tick: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    consume_source_on_impact: torch.Tensor

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
        projectile_speed = torch.zeros_like(catalog.range_units)
        tower_multiplier = torch.ones_like(catalog.damage, dtype=torch.float32)
        status_kind = torch.full_like(catalog.kind, FAST_STATUS_NONE, dtype=torch.int8)
        status_ticks = torch.zeros_like(catalog.range_units)
        consume_source = torch.zeros_like(catalog.kind, dtype=torch.bool)
        attacks_air = catalog.attacks_air.to(torch.bool).clone()
        attacks_ground = catalog.attacks_ground.to(torch.bool).clone()
        buildings_only = catalog.buildings_only.to(torch.bool).clone()
        is_air = catalog.is_air_unit.to(torch.bool).clone()

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
                character = (
                    raw.get("summonCharacterData") or raw.get("summonSpellData") or {}
                )
                child_name = getattr(card, "death_spawn_character", None)
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
                if projectile:
                    effect_kind[card_id] = FAST_CARD_EFFECT_PROJECTILE
                    projectile_speed[card_id] = int(projectile.get("speed", 0) or 0)
                    effect_radius_units[card_id] = int(projectile.get("radius", 0) or 0)
                if spell_projectile_data:
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
                        duration = catalog.mechanic_parameters[
                            card_id, mechanic_slot, parameter
                        ]
                        if not bool(torch.isnan(duration)):
                            status_ticks[card_id] = (
                                duration.to(torch.int32) + 49
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
            deploy_w_tile_margin=catalog.deploy_w_tile_margin.to(torch.int8),
            can_deploy_on_enemy_side=catalog.can_deploy_on_enemy_side.to(torch.bool),
            effect_kind=effect_kind,
            effect_damage=effect_damage,
            effect_radius_units=effect_radius_units,
            projectile_speed_units_per_tick=projectile_speed,
            tower_damage_multiplier=tower_multiplier,
            status_kind=status_kind,
            status_duration_ticks=status_ticks,
            consume_source_on_impact=consume_source,
        )

    @property
    def size(self) -> int:
        return int(self.kind.shape[0])
