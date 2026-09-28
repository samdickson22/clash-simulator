"""Compile serialized card definitions into dense, data-driven tensors."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from numbers import Real
from typing import Iterable

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units
from clasher.unit_traits import is_air_unit_card, is_hover_unit_card, unit_mass


class CardKindOpcode(IntEnum):
    PADDING = 0
    TROOP = 1
    BUILDING = 2
    SPELL = 3
    CHAMPION = 4


CARD_KIND_OPCODE = {
    "troop": CardKindOpcode.TROOP,
    "building": CardKindOpcode.BUILDING,
    "spell": CardKindOpcode.SPELL,
    "champion": CardKindOpcode.CHAMPION,
}

# Stable opcodes cover the complete mechanic/effect classes emitted by the
# current serialized factory. They identify generalized runtime operations,
# never cards. Adding a factory mechanic must add an opcode and tensor kernel.
MECHANIC_NAMES = (
    "ArcherQueenCloak",
    "AttackRecoil",
    "BanditDash",
    "BattleRamCharge",
    "CrownTowerScaling",
    "DamageRamp",
    "DeathAreaEffect",
    "DeathDamage",
    "DeathSpawn",
    "ElectroDragonChainLightning",
    "ElectroSpiritChain",
    "FishermanHook",
    "FreezeDebuff",
    "HideWhenIdle",
    "IceSpiritFreeze",
    "InvisibilityWhenNotAttacking",
    "MegaKnightSlam",
    "MultipleTargetAttack",
    "PeriodicSpawner",
    "SerializedOnHitBuff",
    "Shield",
    "SkeletonKingSoulCollector",
    "SpawnAreaEffect",
    "SpawnPushback",
    "Stun",
    "UndergroundDeployment",
    "WallBreakersDemolition",
)
MECHANIC_OPCODE = {name: index + 1 for index, name in enumerate(MECHANIC_NAMES)}

EFFECT_NAMES = ("PeriodicArea", "ProjectileLaunch")
EFFECT_OPCODE = {name: index + 1 for index, name in enumerate(EFFECT_NAMES)}


def _optional_number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Real):
        return float(value)
    raise TypeError(f"expected serialized numeric value, got {type(value).__name__}")


def _logic_units(value: object) -> int:
    return tiles_to_logic_units(_optional_number(value))


def _scalar_parameters(objects: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                name
                for item in objects
                for name, value in vars(item).items()
                if not name.startswith("_")
                and (value is None or isinstance(value, (bool, Real)))
            }
        )
    )


@dataclass(frozen=True)
class TensorCardCatalog:
    """Immutable card/mechanic tables shared by every tensor battle batch."""

    device: torch.device
    names: tuple[str, ...]
    name_to_id: dict[str, int]
    kind: torch.Tensor
    elixir: torch.Tensor
    hitpoints: torch.Tensor
    damage: torch.Tensor
    range_units: torch.Tensor
    sight_range_units: torch.Tensor
    collision_radius_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    hit_speed_ms: torch.Tensor
    load_time_ms: torch.Tensor
    deploy_time_ms: torch.Tensor
    lifetime_ms: torch.Tensor
    summon_count: torch.Tensor
    summon_radius_units: torch.Tensor
    deploy_w_tile_margin: torch.Tensor
    can_deploy_on_enemy_side: torch.Tensor
    attacks_air: torch.Tensor
    attacks_ground: torch.Tensor
    buildings_only: torch.Tensor
    is_air_unit: torch.Tensor
    is_hover_unit: torch.Tensor
    mass: torch.Tensor
    mechanic_opcode: torch.Tensor
    mechanic_count: torch.Tensor
    mechanic_parameter_names: tuple[str, ...]
    mechanic_parameters: torch.Tensor
    mechanic_nested_payload: torch.Tensor
    effect_opcode: torch.Tensor
    effect_count: torch.Tensor
    effect_parameter_names: tuple[str, ...]
    effect_parameters: torch.Tensor
    effect_nested_payload: torch.Tensor

    @property
    def card_count(self) -> int:
        return len(self.names) - 1

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorCardCatalog:
        definitions = loader.load_card_definitions()
        resolved_names = tuple(
            sorted({resolve_card_name(name, definitions) for name in card_names})
        )
        missing = [name for name in resolved_names if name not in definitions]
        if missing:
            raise ValueError(f"missing card definitions: {missing}")
        names = ("", *resolved_names)
        name_to_id = {name: index for index, name in enumerate(names)}
        cards = [loader.get_card(name) for name in resolved_names]
        if any(card is None for card in cards):
            raise ValueError("could not materialize every requested card")
        compat_cards = [card for card in cards if card is not None]
        mechanic_objects = [
            mechanic
            for name in resolved_names
            for mechanic in definitions[name].mechanics
        ]
        effect_objects = [
            effect for name in resolved_names for effect in definitions[name].effects
        ]
        unknown_mechanics = sorted(
            {
                type(mechanic).__name__
                for mechanic in mechanic_objects
                if type(mechanic).__name__ not in MECHANIC_OPCODE
            }
        )
        unknown_effects = sorted(
            {
                type(effect).__name__
                for effect in effect_objects
                if type(effect).__name__ not in EFFECT_OPCODE
            }
        )
        if unknown_mechanics or unknown_effects:
            raise ValueError(
                "unregistered serialized operations: "
                f"mechanics={unknown_mechanics}, effects={unknown_effects}"
            )

        torch_device = torch.device(device)
        size = len(names)
        max_mechanics = max(
            1,
            max(len(definitions[name].mechanics) for name in resolved_names),
        )
        max_effects = max(
            1,
            max(len(definitions[name].effects) for name in resolved_names),
        )
        mechanic_parameter_names = _scalar_parameters(mechanic_objects)
        effect_parameter_names = _scalar_parameters(effect_objects)
        mechanic_parameter_index = {
            name: index for index, name in enumerate(mechanic_parameter_names)
        }
        effect_parameter_index = {
            name: index for index, name in enumerate(effect_parameter_names)
        }

        def zeros(dtype: torch.dtype, *shape: int) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        kind = zeros(torch.int8, size)
        elixir = zeros(torch.int16, size)
        hitpoints = zeros(torch.float64, size)
        damage = zeros(torch.float64, size)
        range_units = zeros(torch.int32, size)
        sight_range_units = zeros(torch.int32, size)
        collision_radius_units = zeros(torch.int32, size)
        speed_units_per_tick = zeros(torch.int32, size)
        hit_speed_ms = zeros(torch.int32, size)
        load_time_ms = zeros(torch.int32, size)
        deploy_time_ms = zeros(torch.int32, size)
        lifetime_ms = zeros(torch.int32, size)
        summon_count = torch.ones(size, dtype=torch.int16, device=torch_device)
        summon_count[0] = 0
        summon_radius_units = zeros(torch.int32, size)
        deploy_w_tile_margin = zeros(torch.int8, size)
        can_deploy_on_enemy_side = zeros(torch.bool, size)
        attacks_air = zeros(torch.bool, size)
        attacks_ground = zeros(torch.bool, size)
        buildings_only = zeros(torch.bool, size)
        is_air_unit = zeros(torch.bool, size)
        is_hover_unit = zeros(torch.bool, size)
        mass_tensor = zeros(torch.float64, size)
        mechanic_opcode = zeros(torch.int16, size, max_mechanics)
        mechanic_count = zeros(torch.int8, size)
        mechanic_parameters = torch.full(
            (size, max_mechanics, len(mechanic_parameter_names)),
            math.nan,
            dtype=torch.float64,
            device=torch_device,
        )
        mechanic_nested_payload = zeros(torch.bool, size, max_mechanics)
        effect_opcode = zeros(torch.int16, size, max_effects)
        effect_count = zeros(torch.int8, size)
        effect_parameters = torch.full(
            (size, max_effects, len(effect_parameter_names)),
            math.nan,
            dtype=torch.float64,
            device=torch_device,
        )
        effect_nested_payload = zeros(torch.bool, size, max_effects)

        for card_id, (name, card) in enumerate(
            zip(resolved_names, compat_cards), start=1
        ):
            definition = definitions[name]
            kind[card_id] = int(CARD_KIND_OPCODE[definition.kind])
            elixir[card_id] = int(definition.elixir)
            hitpoints[card_id] = _optional_number(
                card.scaled_hitpoints,
                _optional_number(card.hitpoints),
            )
            damage[card_id] = _optional_number(
                card.scaled_damage,
                _optional_number(card.damage),
            )
            range_units[card_id] = _logic_units(card.range)
            sight_range_units[card_id] = _logic_units(card.sight_range)
            collision_radius_units[card_id] = _logic_units(card.collision_radius)
            speed_units_per_tick[card_id] = round(_optional_number(card.speed))
            hit_speed_ms[card_id] = round(_optional_number(card.hit_speed))
            load_time_ms[card_id] = round(_optional_number(card.load_time))
            deploy_time_ms[card_id] = round(_optional_number(card.deploy_time))
            lifetime_ms[card_id] = round(_optional_number(card.lifetime_ms))
            summon_count[card_id] = int(card.summon_count or 1)
            summon_radius_units[card_id] = _logic_units(card.summon_radius)
            deploy_w_tile_margin[card_id] = int(card.deploy_w_tile_margin or 0)
            can_deploy_on_enemy_side[card_id] = bool(card.can_deploy_on_enemy_side)
            target_type = str(getattr(card, "target_type", "") or "")
            attacks_air[card_id] = bool(getattr(card, "attacks_air", False))
            attacks_ground[card_id] = bool(getattr(card, "attacks_ground", False))
            buildings_only[card_id] = target_type == "TID_TARGETS_BUILDINGS"
            is_air_unit[card_id] = is_air_unit_card(card)
            is_hover_unit[card_id] = is_hover_unit_card(card)
            mass_tensor[card_id] = float(unit_mass(card))

            mechanic_count[card_id] = len(definition.mechanics)
            for slot, mechanic in enumerate(definition.mechanics):
                mechanic_opcode[card_id, slot] = MECHANIC_OPCODE[
                    type(mechanic).__name__
                ]
                for parameter_name, value in vars(mechanic).items():
                    if parameter_name.startswith("_"):
                        continue
                    parameter_slot = mechanic_parameter_index.get(parameter_name)
                    if parameter_slot is not None and (
                        value is None or isinstance(value, (bool, Real))
                    ):
                        mechanic_parameters[card_id, slot, parameter_slot] = (
                            math.nan if value is None else float(value)
                        )
                    elif not isinstance(value, (str, bytes)):
                        mechanic_nested_payload[card_id, slot] = True

            effect_count[card_id] = len(definition.effects)
            for slot, effect in enumerate(definition.effects):
                effect_opcode[card_id, slot] = EFFECT_OPCODE[type(effect).__name__]
                for parameter_name, value in vars(effect).items():
                    parameter_slot = effect_parameter_index.get(parameter_name)
                    if parameter_slot is not None and (
                        value is None or isinstance(value, (bool, Real))
                    ):
                        effect_parameters[card_id, slot, parameter_slot] = (
                            math.nan if value is None else float(value)
                        )
                    elif not isinstance(value, (str, bytes)):
                        effect_nested_payload[card_id, slot] = True

        return cls(
            device=torch_device,
            names=names,
            name_to_id=name_to_id,
            kind=kind,
            elixir=elixir,
            hitpoints=hitpoints,
            damage=damage,
            range_units=range_units,
            sight_range_units=sight_range_units,
            collision_radius_units=collision_radius_units,
            speed_units_per_tick=speed_units_per_tick,
            hit_speed_ms=hit_speed_ms,
            load_time_ms=load_time_ms,
            deploy_time_ms=deploy_time_ms,
            lifetime_ms=lifetime_ms,
            summon_count=summon_count,
            summon_radius_units=summon_radius_units,
            deploy_w_tile_margin=deploy_w_tile_margin,
            can_deploy_on_enemy_side=can_deploy_on_enemy_side,
            attacks_air=attacks_air,
            attacks_ground=attacks_ground,
            buildings_only=buildings_only,
            is_air_unit=is_air_unit,
            is_hover_unit=is_hover_unit,
            mass=mass_tensor,
            mechanic_opcode=mechanic_opcode,
            mechanic_count=mechanic_count,
            mechanic_parameter_names=mechanic_parameter_names,
            mechanic_parameters=mechanic_parameters,
            mechanic_nested_payload=mechanic_nested_payload,
            effect_opcode=effect_opcode,
            effect_count=effect_count,
            effect_parameter_names=effect_parameter_names,
            effect_parameters=effect_parameters,
            effect_nested_payload=effect_nested_payload,
        )
