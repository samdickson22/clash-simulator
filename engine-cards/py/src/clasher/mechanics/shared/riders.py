"""Attached riders (Goblin Giant's Spear Goblins).

Ported from RoyaleSim (MIT), state.rs ``spawn_riders`` / ``carry_riders`` /
``dismount_point`` / ``riders_die_with_their_mounts`` and formation.rs
``rider_arc_offset`` (calibration rider.OFFSET_LAW = arc_behind_mount,
rider.POSITION = mount_previous_tick_position, rider.TARGETABLE_WHILE_ATTACHED =
untargetable_immune, rider.DISMOUNT_POINT = mount_position_plus_offset; measured
on client 15.535.29 Goblin Giants). A mount whose character row carries
SpawnAttach creates SpawnNumber riders of its SpawnCharacter right after
itself. A rider attacks with its own weapon but never walks, is never pushed,
pushes nothing and nothing may target or touch it while its mount lives. It
stands on its mount's position (as the mount's combat left it) plus an arc
offset at the mount's start-of-tick heading. When the mount dies each rider
dies with it and its own death spawn comes down at the mount's position plus
the rider's offset under the mount's final heading.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..mechanic_base import BaseMechanic


def rider_arc_offset_units(radius_units, facing, number, rank, shift_deg, max_angle_deg):
    """formation.rs rider_arc_offset in this engine's integer trigonometry."""
    from ...logic_math import logic_cos, logic_sin, logic_vector_angle

    number = max(1, int(number))
    angle = 180 + int(shift_deg) + (number - 1 - int(rank)) * int(max_angle_deg) // number
    degrees = logic_vector_angle(int(facing[0]), int(facing[1])) + angle
    return logic_cos(degrees, int(radius_units)), logic_sin(degrees, int(radius_units))


def mounted(entity) -> bool:
    """An attached rider whose mount lives."""
    mount = getattr(entity, "_rider_mount", None)
    return mount is not None and mount.is_alive


@dataclass
class RiderOnMount(BaseMechanic):
    """A rider's immunity while its mount lives (rider.TARGETABLE_WHILE_ATTACHED)."""

    def allows_effect(self, entity, source_kind=None, *, affects_hidden=False):
        return not mounted(entity)

    def blocks_targeting(self, entity):
        return mounted(entity)

    def allows_forced_movement(self, entity, source_kind, movement_kind):
        return False if mounted(entity) else None


@dataclass
class AttachedRiders(BaseMechanic):
    """A mount's SpawnAttach block: SpawnNumber riders on an arc behind it."""

    rider_data: dict
    number: int
    radius_units: int
    riders: list = field(default_factory=list, repr=False)

    def rider_offset(self, rider, facing):
        data = self.rider_data
        return rider_arc_offset_units(
            self.radius_units, facing, self.number, getattr(rider, "_rider_rank", 0),
            int(data.get("spawnAngleShift", 0) or 0), int(data.get("spawnMaxAngle", 0) or 0),
        )

    def on_created(self, entity) -> None:
        battle = getattr(entity, "battle_state", None)
        if battle is None or self.riders:
            return
        from ...arena import Position
        from ...factory.dynamic_factory import troop_from_character_data
        from ...kinematics import logic_units_to_tiles, tiles_to_logic_units

        stats = troop_from_character_data(
            self.rider_data.get("name", "Rider"), self.rider_data, elixir=0,
            raw_overrides={"level": getattr(entity.card_stats, "level", 11)},
            rarity=self.rider_data.get("rarity", "Common"),
        )
        facing = entity.native_facing_units()
        for rank in range(self.number):
            dx, dy = rider_arc_offset_units(
                self.radius_units, facing, self.number, rank,
                int(self.rider_data.get("spawnAngleShift", 0) or 0),
                int(self.rider_data.get("spawnMaxAngle", 0) or 0),
            )
            rider_id = battle.next_entity_id
            battle._spawn_unit_at_position(
                Position(
                    logic_units_to_tiles(tiles_to_logic_units(entity.position.x) + dx),
                    logic_units_to_tiles(tiles_to_logic_units(entity.position.y) + dy),
                ),
                entity.player_id, stats,
                deploy_delay_override=entity.deploy_delay_remaining,
                snap_to_valid=False, is_clone=getattr(entity, "is_clone", False),
            )
            rider = battle.entities.get(rider_id)
            if rider is None:
                continue
            rider._rider_mount = entity
            rider._rider_rank = rank
            entity._rider_mechanic = self
            rider.spawn_stagger_remaining = entity.spawn_stagger_remaining
            rider.mechanics.append(RiderOnMount())
            self.riders.append(rider)

    def carry(self, entity, facing) -> None:
        """rider.POSITION: each rider onto its mount, after the combat phase."""
        from ...arena import Position
        from ...kinematics import logic_units_to_tiles, tiles_to_logic_units

        for rider in self.riders:
            if not rider.is_alive or not mounted(rider):
                continue
            dx, dy = self.rider_offset(rider, facing)
            rider.position = Position(
                logic_units_to_tiles(tiles_to_logic_units(entity.position.x) + dx),
                logic_units_to_tiles(tiles_to_logic_units(entity.position.y) + dy),
            )

    def on_death(self, entity) -> None:
        """rider.DIES_WITH_MOUNT and rider.DISMOUNT_POINT."""
        from ...arena import Position
        from ...kinematics import logic_units_to_tiles, tiles_to_logic_units

        facing = entity.native_facing_units()
        for rider in self.riders:
            if not rider.is_alive or getattr(rider, "_rider_mount", None) is not entity:
                continue
            dx, dy = self.rider_offset(rider, facing)
            rider._rider_mount = None
            rider.position = Position(
                logic_units_to_tiles(tiles_to_logic_units(entity.position.x) + dx),
                logic_units_to_tiles(tiles_to_logic_units(entity.position.y) + dy),
            )
            rider.take_damage(rider.hitpoints)
