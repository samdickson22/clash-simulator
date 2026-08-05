import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, RollingProjectile
from clasher.kinematics import (
    tiles_per_second_to_logic_speed,
    tiles_to_logic_units,
)

from scripts.audit_enabled_mirror import (
    RuntimeUnitSpec,
    _child_card_stats,
    _runtime_unit_specs,
)


# These attacks resolve their serialized projectile through a card-owned
# movement state instead of Entity._create_projectile.
_SPECIAL_ATTACK_PAYLOADS = {
    "ElectroSpirit",
    "IceSpirit",
    "Wallbreakers",
}


def _stats(battle: BattleState, spec: RuntimeUnitSpec):
    if spec.deck_card is not None:
        stats = battle.card_loader.get_card(spec.deck_card)
        assert stats is not None
        return stats
    return _child_card_stats(spec)


def _spawn_single(
    battle: BattleState,
    spec: RuntimeUnitSpec,
    player_id: int,
    position: Position,
):
    stats = _stats(battle, spec)
    if str(stats.card_type).lower() == "building":
        entity = battle._spawn_entity(
            Building,
            position,
            player_id,
            stats,
        )
    else:
        entity_id = battle.next_entity_id
        battle._spawn_unit_at_position(
            position,
            player_id,
            stats,
            snap_to_valid=False,
        )
        entity = battle.entities[entity_id]
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.on_spawn()
    return entity


def _ordinary_projectile_specs(battle: BattleState):
    specs = _runtime_unit_specs(
        battle,
        include_reachable_children=True,
    )
    return specs, {
        label: spec
        for label, spec in specs.items()
        if label not in _SPECIAL_ATTACK_PAYLOADS
        and _stats(battle, spec).projectile_data
    }


@pytest.mark.parametrize(
    ("delta_x", "delta_y"),
    (
        (5.0, 0.0),
        (4.0, 3.0),
        (3.0, 4.0),
        (0.0, 5.0),
        (-3.0, 4.0),
        (-4.0, -3.0),
        (3.0, -4.0),
        (-5.0, 0.0),
    ),
)
def test_every_enabled_projectile_uses_exact_fixed_point_flight_ticks(
    delta_x,
    delta_y,
):
    template = BattleState()
    specs, projectile_specs = _ordinary_projectile_specs(template)

    for label, spec in projectile_specs.items():
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        attacker = _spawn_single(
            battle,
            spec,
            0,
            Position(9.0, 14.0),
        )
        target = _spawn_single(
            battle,
            specs["Knight"],
            1,
            Position(9.0 + delta_x, 14.0 + delta_y),
        )
        existing_ids = set(battle.entities)

        attacker._create_projectile(target, battle)

        created = [
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in existing_ids
        ]
        assert len(created) == 1, label
        projectile = created[0]
        assert isinstance(projectile, (Projectile, RollingProjectile)), label

        if isinstance(projectile, RollingProjectile):
            distance_units = tiles_to_logic_units(
                projectile.projectile_range
            )
            speed_units = round(projectile.travel_speed)
        else:
            dx_units = tiles_to_logic_units(
                projectile.target_position.x - projectile.position.x
            )
            dy_units = tiles_to_logic_units(
                projectile.target_position.y - projectile.position.y
            )
            distance_units = math.isqrt(
                dx_units * dx_units + dy_units * dy_units
            )
            speed_units = tiles_per_second_to_logic_speed(
                projectile.travel_speed
            )
        expected_ticks = max(
            1,
            (distance_units + speed_units - 1) // speed_units,
        )

        ticks = 0
        while projectile.is_alive and ticks <= expected_ticks:
            projectile.update(battle.dt, battle)
            ticks += 1

        assert not projectile.is_alive, label
        assert ticks == expected_ticks, label


def test_every_enabled_projectile_obeys_serialized_homing_after_target_moves():
    template = BattleState()
    specs, projectile_specs = _ordinary_projectile_specs(template)

    for label, spec in projectile_specs.items():
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        attacker = _spawn_single(
            battle,
            spec,
            0,
            Position(7.0, 10.0),
        )
        target = _spawn_single(
            battle,
            specs["Knight"],
            1,
            Position(7.0, 14.0),
        )
        target.hitpoints = target.max_hitpoints = 1_000_000.0
        hitpoints_before = target.hitpoints
        existing_ids = set(battle.entities)

        attacker._create_projectile(target, battle)
        projectile = next(
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in existing_ids
        )
        assert isinstance(projectile, (Projectile, RollingProjectile)), label

        target.position = Position(15.0, 14.0)
        for _ in range(1_000):
            if not projectile.is_alive:
                break
            projectile.update(battle.dt, battle)
        assert not projectile.is_alive, label

        # Finish any impact-created child projectiles, notably Firecracker's
        # five non-homing shrapnel rays.
        for _ in range(200):
            live_projectiles = [
                entity
                for entity in list(battle.entities.values())
                if isinstance(entity, (Projectile, RollingProjectile))
                and entity.is_alive
            ]
            if not live_projectiles:
                break
            for live_projectile in live_projectiles:
                live_projectile.update(battle.dt, battle)

        projectile_data = _stats(battle, spec).projectile_data or {}
        expected_hit = (
            bool(projectile_data.get("homing", True))
            and not bool(projectile_data.get("projectileRange"))
            and not bool(projectile_data.get("spawnProjectileData"))
        )
        assert (target.hitpoints < hitpoints_before) is expected_hit, label
