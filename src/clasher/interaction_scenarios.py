from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .arena import Position
from .battle import BattleState
from .differential import DifferentialResult, python_lockstep
from .entities import Entity, Troop
from .interaction_matrix import GeometryName, InteractionCase


@dataclass(frozen=True)
class InteractionSetup:
    case: InteractionCase
    battle: BattleState
    spawned_entity_ids: tuple[int, ...]
    event_applied: bool


_GEOMETRY_POSITIONS: dict[
    GeometryName,
    tuple[tuple[Position, Position], tuple[Position, Position]],
] = {
    "center": (
        (Position(8.25, 14.0), Position(9.75, 14.0)),
        (Position(8.25, 18.0), Position(9.75, 18.0)),
    ),
    "left_lane": (
        (Position(3.25, 13.5), Position(4.75, 14.5)),
        (Position(3.25, 18.5), Position(4.75, 17.5)),
    ),
    "right_lane": (
        (Position(13.25, 13.5), Position(14.75, 14.5)),
        (Position(13.25, 18.5), Position(14.75, 17.5)),
    ),
    "river_left": (
        (Position(5.25, 15.0), Position(6.25, 14.0)),
        (Position(5.25, 17.0), Position(6.25, 18.0)),
    ),
    "river_right": (
        (Position(11.75, 15.0), Position(12.75, 14.0)),
        (Position(11.75, 17.0), Position(12.75, 18.0)),
    ),
    "split_lane": (
        (Position(4.0, 14.0), Position(14.0, 14.0)),
        (Position(4.0, 18.0), Position(14.0, 18.0)),
    ),
}


def _mirror_position(position: Position, arena_width: int) -> Position:
    return Position(float(arena_width) - position.x, position.y)


def _spawn_team(
    battle: BattleState,
    *,
    player_id: int,
    cards: tuple[str, ...],
    positions: tuple[Position, Position],
    reversed_order: bool,
) -> list[int]:
    indexed_cards = list(enumerate(cards))
    if reversed_order:
        indexed_cards.reverse()
    spawned_ids: list[int] = []
    for position_index, card_name in indexed_cards:
        stats = battle.card_loader.get_card(card_name)
        if stats is None:
            raise ValueError(f"missing interaction card {card_name!r}")
        before = set(battle.entities)
        battle._spawn_troop(positions[position_index], player_id, stats)
        spawned_ids.extend(sorted(set(battle.entities) - before))
    return spawned_ids


def _activate_spawned(battle: BattleState, spawned_ids: list[int]) -> None:
    # Work from the stable list of card-spawned characters. on_spawn hooks may
    # themselves add area/projectile objects to the battle dictionary.
    for entity_id in spawned_ids:
        entity = battle.entities.get(entity_id)
        if entity is None:
            continue
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity.on_spawn()


def _spawned_combat_entities(
    battle: BattleState,
    spawned_ids: tuple[int, ...],
) -> list[Entity]:
    return [
        entity
        for entity_id in spawned_ids
        if (entity := battle.entities.get(entity_id)) is not None
        and isinstance(entity, Entity)
        and entity.is_alive
    ]


def _nearest_enemy(
    entity: Entity,
    entities: list[Entity],
    *,
    reverse_id: bool = False,
) -> Entity | None:
    candidates = [
        candidate
        for candidate in entities
        if candidate.player_id != entity.player_id and candidate.is_alive
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            entity.position.distance_to(candidate.position),
            -candidate.id if reverse_id else candidate.id,
        ),
    )


def _arm_attackers(entities: list[Entity], *, reverse_id: bool = False) -> bool:
    applied = False
    for entity in entities:
        if not isinstance(entity, Troop):
            continue
        target = _nearest_enemy(entity, entities, reverse_id=reverse_id)
        if target is None:
            continue
        entity.target_id = target.id
        entity.attack_cooldown = 0.0
        entity._attack_windup_active = False
        applied = True
    return applied


def _has_death_payload(entity: Entity) -> bool:
    stats = getattr(entity, "card_stats", None)
    if getattr(stats, "death_spawn_character", None):
        return True
    raw_character = getattr(stats, "summon_character_data", None) or {}
    return any(
        raw_character.get(field)
        for field in (
            "deathAreaEffectData",
            "deathSpawnCharacterData",
            "deathSpawnProjectileData",
        )
    )


def _has_projectile(entity: Entity) -> bool:
    return bool(getattr(getattr(entity, "card_stats", None), "projectile_data", None))


def _apply_event(
    battle: BattleState,
    spawned_ids: tuple[int, ...],
    event_family: str,
) -> bool:
    entities = _spawned_combat_entities(battle, spawned_ids)
    if event_family == "ordinary":
        return True
    if event_family == "target_order":
        return _arm_attackers(entities, reverse_id=True)
    if event_family == "simultaneous_attack":
        return _arm_attackers(entities)
    if event_family == "simultaneous_death":
        applied = _arm_attackers(entities)
        for player_id in (0, 1):
            victim = next(
                (entity for entity in entities if entity.player_id == player_id),
                None,
            )
            if victim is not None:
                victim.hitpoints = min(float(victim.hitpoints), 1.0)
                applied = True
        return applied
    if event_family == "stun":
        for entity in entities:
            entity.apply_stun(0.75, source_kind="differential-status")
        return bool(entities)
    if event_family == "slow":
        for entity in entities:
            entity.apply_slow(
                1.25,
                0.7,
                source_kind="differential-status",
            )
        return bool(entities)
    if event_family == "rage":
        for entity in entities:
            entity.apply_haste(1.25, 1.3, 1.3, 1.3)
        return bool(entities)
    if event_family == "death_payload":
        candidates = [entity for entity in entities if _has_death_payload(entity)]
        for entity in candidates:
            entity.take_damage(float(entity.hitpoints) + 1.0)
        return bool(candidates)
    if event_family == "projectile":
        candidates = [entity for entity in entities if _has_projectile(entity)]
        return _arm_attackers(candidates)
    if event_family == "retarget":
        applied = _arm_attackers(entities)
        for player_id in (0, 1):
            candidates = [
                entity for entity in entities if entity.player_id == player_id
            ]
            if len(candidates) >= 2:
                candidates[0].take_damage(float(candidates[0].hitpoints) + 1.0)
                applied = True
                break
        return applied
    if event_family == "allied_collision":
        applied = False
        for player_id in (0, 1):
            allies = [
                entity
                for entity in entities
                if entity.player_id == player_id and isinstance(entity, Troop)
            ]
            if len(allies) < 2:
                continue
            anchor = allies[0].position
            for entity in allies[1:]:
                entity.position = Position(anchor.x + 0.05, anchor.y + 0.05)
                entity.quantize_logic_position()
            applied = True
        return applied
    raise ValueError(f"unknown interaction event family {event_family!r}")


def build_interaction_battle(
    case: InteractionCase,
    *,
    seed: int = 0xC1A5_0000,
) -> InteractionSetup:
    battle = BattleState(rng=random.Random(seed + case.index), fast_path=case.fast_path)
    team_positions = _GEOMETRY_POSITIONS[case.geometry]
    if case.mirrored:
        team_positions = (
            (
                _mirror_position(team_positions[0][0], battle.arena.width),
                _mirror_position(team_positions[0][1], battle.arena.width),
            ),
            (
                _mirror_position(team_positions[1][0], battle.arena.width),
                _mirror_position(team_positions[1][1], battle.arena.width),
            ),
        )
    spawned = _spawn_team(
        battle,
        player_id=0,
        cards=case.team_0,
        positions=team_positions[0],
        reversed_order=case.team_0_spawn_reversed,
    )
    spawned.extend(
        _spawn_team(
            battle,
            player_id=1,
            cards=case.team_1,
            positions=team_positions[1],
            reversed_order=case.team_1_spawn_reversed,
        )
    )
    _activate_spawned(battle, spawned)
    spawned_ids = tuple(spawned)
    event_applied = _apply_event(
        battle,
        spawned_ids,
        case.event_family,
    )
    if case.fast_path:
        battle._refresh_fast_path_caches()
    return InteractionSetup(
        case=case,
        battle=battle,
        spawned_entity_ids=spawned_ids,
        event_applied=event_applied,
    )


def run_python_interaction_case(
    case: InteractionCase,
    *,
    ticks: int,
    seed: int = 0xC1A5_0000,
    dump_directory: str | None = None,
) -> tuple[InteractionSetup, DifferentialResult]:
    setup = build_interaction_battle(case, seed=seed)
    result = python_lockstep(
        setup.battle,
        ticks=ticks,
        scenario=case.case_id,
        dump_directory=dump_directory,
    )
    return setup, result


def interaction_case_summary(setup: InteractionSetup) -> dict[str, Any]:
    return {
        **setup.case.as_dict(),
        "spawned_entity_count": len(setup.spawned_entity_ids),
        "event_applied": setup.event_applied,
    }
