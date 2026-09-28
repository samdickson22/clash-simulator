from dataclasses import dataclass
from typing import Any

from ..mechanic_base import BaseMechanic
from ...arena import Position
from ...balance import TOURNAMENT_LEVEL, tournament_spell_stat
from ...gamedata_normalization import serialized_hit_planes
from ...kinematics import LOGIC_TICK_SECONDS


def _register_death_object(battle_state, entity):
    # Accepted commands outside step() become visible at the next boundary.
    # Objects created by component/object work belong to the current boundary.
    # Neither consumes an object tick on its own birth boundary.
    entity._native_object_birth_tick = battle_state.tick + int(
        not getattr(battle_state, "_logic_tick_active", False)
    )
    entity.battle_state = battle_state
    battle_state.entities[entity.id] = entity
    battle_state.next_entity_id += 1
    return entity


def _first_action_spawn(value: Any) -> dict | None:
    """Return the first structurally embedded ActionSpawn payload."""
    if isinstance(value, dict):
        spawn = value.get("spawnDataData")
        if isinstance(spawn, dict):
            return spawn
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


def _serialized_speed_multiplier(raw_value: Any, default: float = 1.0) -> float:
    """Decode the two native buff encodings used by current character data."""
    if raw_value is None:
        return default
    value = float(raw_value)
    # Debuffs serialize a signed delta (-30 => 70%), while positive haste
    # buffs serialize the final percentage (130 => 130%).
    return max(0.0, (100.0 + value if value <= 0.0 else value) / 100.0)


def spawn_death_area_object(
    battle_state,
    *,
    player_id: int,
    position: Position,
    card_stats,
    area_data: dict,
):
    """Materialize one resolved character DeathAreaEffect payload."""
    from ...entities import AreaEffect, BuffAreaEffect

    radius = float(area_data.get("radius", 0) or 0) / 1000.0
    # Native zero/one-millisecond objects still receive their first 50 ms
    # object tick. Preserve that one-shot opportunity in the continuous-time
    # representation instead of expiring before the payload can run.
    duration = max(
        0.001,
        float(area_data.get("lifeDuration", 0) or 0) / 1000.0,
    )
    hit_interval = max(
        0.0,
        float(area_data.get("hitSpeed", 0) or 0) / 1000.0,
    )
    buff_duration = max(
        0.0,
        float(area_data.get("buffTime", 0) or 0) / 1000.0,
    )
    buff = area_data.get("buffData") or {}
    movement_multiplier = _serialized_speed_multiplier(
        buff.get("speedMultiplier")
    )
    attack_multiplier = _serialized_speed_multiplier(
        buff.get("hitSpeedMultiplier")
    )
    spawn_multiplier = _serialized_speed_multiplier(
        buff.get("spawnSpeedMultiplier")
    )
    hits_air, hits_ground = serialized_hit_planes(area_data)
    scaler = getattr(card_stats, "get_scaled_stat", None)

    impact_data = area_data.get("spawnAreaEffectObjectData") or {}
    raw_impact_damage = float(impact_data.get("damage", 0) or 0)
    impact_damage = float(
        scaler(raw_impact_damage) if callable(scaler) else raw_impact_damage
    )
    # Balance overrides belong to the gameplay area-object identity, not to
    # the nested buff's presentation name. Distinct producers can share the
    # same Rage buff while retaining different impact modifiers and timings
    # (Rage vs. Lumberjack's BarbarianRage).
    area_name = str(area_data.get("name", "") or "")
    live_impact_damage = (
        tournament_spell_stat(area_name, "damage") if area_name else None
    )
    tournament_level = getattr(card_stats, "level", TOURNAMENT_LEVEL) == TOURNAMENT_LEVEL
    if live_impact_damage is not None and tournament_level:
        impact_damage = float(live_impact_damage)
    crown_tower_damage = (
        tournament_spell_stat(area_name, "crown_tower_damage")
        if area_name and tournament_level
        else None
    )
    crown_multiplier = max(
        0.0,
        1.0
        + float(impact_data.get("crownTowerDamagePercent", 0) or 0) / 100.0,
    )

    common = dict(
        id=battle_state.next_entity_id,
        position=Position(position.x, position.y),
        player_id=player_id,
        card_stats=card_stats,
        hitpoints=1,
        max_hitpoints=1,
        range=radius,
        sight_range=radius,
    )
    if max(movement_multiplier, attack_multiplier, spawn_multiplier) > 1.0:
        effect = BuffAreaEffect(
            **common,
            damage=0,
            duration=duration,
            radius=radius,
            movement_multiplier=movement_multiplier,
            attack_speed_multiplier=attack_multiplier,
            spawn_speed_multiplier=spawn_multiplier,
            refresh_duration=buff_duration,
            cap_buff_time_to_effect=bool(
                area_data.get("capBuffTimeToAreaEffectTime", False)
            ),
            effect_tick_interval=hit_interval,
            effect_on_spawn_only=hit_interval <= 0.0,
            impact_damage=impact_damage,
            impact_area_data=impact_data or None,
            impact_affects_hidden=bool(
                impact_data.get("affectsHidden", False)
            ),
            crown_tower_damage_multiplier=crown_multiplier,
            crown_tower_damage=(
                float(crown_tower_damage)
                if crown_tower_damage is not None
                else None
            ),
        )
    else:
        raw_damage = float(area_data.get("damage", 0) or 0)
        damage = float(scaler(raw_damage) if callable(scaler) else raw_damage)
        if damage > 0 and hit_interval > 0:
            max_damage_ticks = int(duration / hit_interval + 1e-9)
            initial_damage_delay = hit_interval
            damage_tick_interval = hit_interval
        elif damage > 0:
            max_damage_ticks = 1
            initial_damage_delay = 0.0
            damage_tick_interval = max(LOGIC_TICK_SECONDS, duration)
        else:
            max_damage_ticks = 0
            initial_damage_delay = None
            damage_tick_interval = 0.0
        effect = AreaEffect(
            **common,
            duration=duration,
            radius=radius,
            damage=damage,
            damage_on_spawn=damage > 0,
            max_damage_ticks=max_damage_ticks,
            initial_damage_delay=initial_damage_delay,
            damage_tick_interval=damage_tick_interval,
            speed_multiplier=movement_multiplier,
            attack_speed_multiplier=attack_multiplier,
            spawn_speed_multiplier=spawn_multiplier,
            slow_refresh_duration=buff_duration,
            effect_tick_interval=hit_interval,
            effect_on_spawn_only=hit_interval <= 0.0,
            hits_air=hits_air,
            hits_ground=hits_ground,
            affects_hidden=bool(area_data.get("affectsHidden", False)),
        )

    effect.spell_name = str(area_data.get("name", "") or "death-area")
    return _register_death_object(battle_state, effect)


def spawn_death_area_payload(
    battle_state,
    *,
    player_id: int,
    position: Position,
    card_stats,
    area_data: dict,
):
    """Resolve an arbitrary nested DeathAreaEffect action chain."""
    action_spawn = _first_action_spawn(area_data.get("onStartingActionData"))
    nested_area = (
        action_spawn.get("deathAreaEffectData")
        if isinstance(action_spawn, dict)
        else None
    )
    if not isinstance(nested_area, dict):
        return spawn_death_area_object(
            battle_state,
            player_id=player_id,
            position=position,
            card_stats=card_stats,
            area_data=area_data,
        )

    from ...entities import DeathAreaStartAction

    action = DeathAreaStartAction(
        id=battle_state.next_entity_id,
        position=Position(position.x, position.y),
        player_id=player_id,
        card_stats=card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        spawn_data=action_spawn,
        area_data=nested_area,
    )
    return _register_death_object(battle_state, action)


def spawn_death_area_container(
    battle_state, *, player_id, position, card_stats, spawn_data, area_data,
):
    """Materialize the starting action's delayed character container."""
    from ...entities import DeathAreaEffectContainer

    container = DeathAreaEffectContainer(
        id=battle_state.next_entity_id,
        position=Position(position.x, position.y),
        player_id=player_id,
        card_stats=card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        activation_delay=max(
            0.0,
            float(spawn_data.get("deployTime", 0) or 0) / 1000.0,
        ),
        area_data=area_data,
    )
    return _register_death_object(battle_state, container)


@dataclass
class DeathAreaEffect(BaseMechanic):
    """Resolve a character's data-driven death area or nested effect container."""

    area_data: dict

    def on_death(self, entity) -> None:
        if not hasattr(entity, "battle_state"):
            return
        spawn_death_area_payload(
            entity.battle_state,
            player_id=entity.player_id,
            position=entity.position,
            card_stats=entity.card_stats,
            area_data=self.area_data,
        )
