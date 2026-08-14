from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from clasher.entities import Building, Troop
from clasher.kinematics import logic_speed_to_tiles_per_second

from .reward_model import (
    DEFENSE_V2,
    DEFENSE_V3,
    OBJECTIVE_V1,
    REWARD_PROFILES,
    PotentialBreakdown,
)

if TYPE_CHECKING:
    from clasher.battle import BattleState


@dataclass(frozen=True)
class LeafPlayer:
    player_id: int
    current_hp: tuple[float, float, float]
    starting_hp: tuple[float, float, float]
    lowest_standing_hp_milli: int


@dataclass(frozen=True)
class LeafCrown:
    encounter_index: int
    player_id: int
    slot: str
    alive: bool
    tower_active: bool
    hp: float
    max_hp: float
    x: float
    y: float
    target_distance_discount_sq_units: int


@dataclass(frozen=True)
class LeafCombat:
    encounter_index: int
    player_id: int
    kind: int
    alive: bool
    is_crown: bool
    visible_to_p0: bool
    visible_to_p1: bool
    x: float
    y: float
    hp: float
    max_hp: float
    damage: float
    attack_range: float
    speed: float
    can_attack_ground: bool
    mana_cost: float
    summon_count: int
    summon_character_second_count: int
    hit_speed_ms: float


@dataclass(frozen=True)
class LeafProjection:
    game_over: bool
    winner: int | None
    players: tuple[LeafPlayer, LeafPlayer]
    crowns: tuple[LeafCrown, ...]
    combat: tuple[LeafCombat, ...]


def projection_from_native_parts(parts: tuple[Any, ...]) -> LeafProjection:
    game_over, winner, player_rows, crown_rows, combat_rows, trait_rows = parts
    players = tuple(
        LeafPlayer(
            player_id=int(row[0]),
            current_hp=(float(row[1][0]), float(row[1][1]), float(row[1][2])),
            starting_hp=(float(row[2][0]), float(row[2][1]), float(row[2][2])),
            lowest_standing_hp_milli=int(row[3]),
        )
        for row in player_rows
    )
    if len(players) != 2:
        raise RuntimeError("resident oracle leaf returned an invalid player count")
    crowns = tuple(
        LeafCrown(
            encounter_index=int(row[0]),
            player_id=int(row[1]),
            slot=str(row[2]),
            alive=bool(row[3]),
            tower_active=bool(row[4]),
            hp=float(row[5]),
            max_hp=float(row[6]),
            x=float(row[7]),
            y=float(row[8]),
            target_distance_discount_sq_units=int(row[9]),
        )
        for row in crown_rows
    )
    if len(combat_rows) != len(trait_rows):
        raise RuntimeError("resident oracle leaf returned misaligned combat rows")
    combat: list[LeafCombat] = []
    for state, traits in zip(combat_rows, trait_rows, strict=True):
        if int(state[0]) != int(traits[0]):
            raise RuntimeError("resident oracle leaf combat row identity mismatch")
        combat.append(
            LeafCombat(
                encounter_index=int(state[0]),
                player_id=int(state[1]),
                kind=int(state[2]),
                alive=bool(state[3]),
                is_crown=bool(state[4]),
                visible_to_p0=bool(traits[1]),
                visible_to_p1=bool(traits[2]),
                x=float(state[5]),
                y=float(state[6]),
                hp=float(state[7]),
                max_hp=float(state[8]),
                damage=float(state[9]),
                can_attack_ground=bool(traits[3]),
                attack_range=float(traits[4]),
                speed=float(traits[5]),
                mana_cost=float(traits[6]),
                summon_count=int(traits[7]),
                summon_character_second_count=int(traits[8]),
                hit_speed_ms=float(traits[9]),
            )
        )
    return LeafProjection(
        game_over=bool(game_over),
        winner=None if winner is None else int(winner),
        players=(players[0], players[1]),
        crowns=crowns,
        combat=tuple(combat),
    )


def projection_from_battle(battle: BattleState) -> LeafProjection:
    players: list[LeafPlayer] = []
    for player_id, player in enumerate(battle.players):
        current = (
            float(player.left_tower_hp),
            float(player.right_tower_hp),
            float(player.king_tower_hp),
        )
        starting = battle._starting_tower_hps[player_id]
        standing = [hp for hp in current if hp > 0.0]
        players.append(
            LeafPlayer(
                player_id=player_id,
                current_hp=current,
                starting_hp=(
                    float(starting["left"]),
                    float(starting["right"]),
                    float(starting["king"]),
                ),
                lowest_standing_hp_milli=(
                    round(min(standing) * 1000.0) if standing else 0
                ),
            )
        )
    crowns: list[LeafCrown] = []
    combat: list[LeafCombat] = []
    for encounter_index, entity in enumerate(battle.entities.values()):
        if not isinstance(entity, (Troop, Building)):
            continue
        slot = getattr(entity, "_crown_tower_slot", None)
        is_crown = isinstance(entity, Building) and slot in {"left", "right", "king"}
        if is_crown:
            crowns.append(
                LeafCrown(
                    encounter_index=encounter_index,
                    player_id=int(entity.player_id),
                    slot=str(slot),
                    alive=bool(entity.is_alive),
                    tower_active=bool(getattr(entity, "_tower_active", False)),
                    hp=float(entity.hitpoints),
                    max_hp=float(entity.max_hitpoints),
                    x=float(entity.position.x),
                    y=float(entity.position.y),
                    target_distance_discount_sq_units=int(
                        getattr(
                            entity,
                            "_native_target_distance_discount_sq_units",
                            0,
                        )
                        or 0
                    ),
                )
            )
        stats = entity.card_stats
        combat.append(
            LeafCombat(
                encounter_index=encounter_index,
                player_id=int(entity.player_id),
                kind=0 if isinstance(entity, Troop) else 1,
                alive=bool(entity.is_alive),
                is_crown=is_crown,
                visible_to_p0=bool(entity.is_visible_to(0)),
                visible_to_p1=bool(entity.is_visible_to(1)),
                x=float(entity.position.x),
                y=float(entity.position.y),
                hp=float(entity.hitpoints),
                max_hp=float(entity.max_hitpoints),
                damage=float(entity.damage),
                attack_range=float(entity.range),
                speed=float(entity.speed),
                can_attack_ground=bool(entity._can_attack_ground()),
                mana_cost=float(getattr(stats, "mana_cost", 0) or 0),
                summon_count=int(getattr(stats, "summon_count", 0) or 0),
                summon_character_second_count=int(
                    getattr(stats, "summon_character_second_count", 0) or 0
                ),
                hit_speed_ms=float(getattr(stats, "hit_speed", 0) or 0),
            )
        )
    return LeafProjection(
        game_over=bool(battle.game_over),
        winner=battle.winner,
        players=(players[0], players[1]),
        crowns=tuple(crowns),
        combat=tuple(combat),
    )


def _safe_frac(value: float, denom: float) -> float:
    return float(value) / max(1e-6, float(denom))


def _tower_fractions(player: LeafPlayer) -> tuple[float, float]:
    left, right, king = player.current_hp
    start_left, start_right, start_king = player.starting_hp
    start_princess = max(1.0, 0.5 * (start_left + start_right))
    left_frac = np.clip(_safe_frac(left, start_princess), 0.0, 1.0)
    right_frac = np.clip(_safe_frac(right, start_princess), 0.0, 1.0)
    king_frac = np.clip(_safe_frac(king, start_king), 0.0, 1.0)
    princess_frac = np.clip((left_frac + right_frac) / 2.0, 0.0, 1.0)
    return float(princess_frac), float(king_frac)


def _crown_count(player: LeafPlayer) -> int:
    left, right, king = player.current_hp
    if king <= 0.0:
        return 3
    return int(left <= 0.0) + int(right <= 0.0)


def _king_active(projection: LeafProjection, player_id: int) -> bool:
    for tower in projection.crowns:
        if tower.alive and tower.player_id == player_id and tower.slot == "king":
            return tower.tower_active
    return False


def _public_combat_entities(
    projection: LeafProjection,
    player_id: int,
) -> list[LeafCombat]:
    return [
        entity
        for entity in projection.combat
        if entity.alive
        and entity.player_id == player_id
        and not entity.is_crown
        and entity.visible_to_p0
        and entity.visible_to_p1
    ]


def _entity_remaining_value(entity: LeafCombat) -> float:
    max_hp = max(1.0, float(entity.max_hp or 1.0))
    hp_fraction = float(np.clip(float(entity.hp) / max_hp, 0.0, 1.0))
    formation_size = max(
        1,
        int(entity.summon_count or 0)
        + int(entity.summon_character_second_count or 0),
    )
    elixir_share = max(0.0, float(entity.mana_cost or 0)) / formation_size
    hit_speed_seconds = max(0.25, float(entity.hit_speed_ms or 0) / 1000.0)
    dps = max(0.0, float(entity.damage)) / hit_speed_seconds
    hp_strength = float(np.clip(math.sqrt(max_hp / 1000.0), 0.25, 2.0))
    dps_strength = float(np.clip(dps / 180.0, 0.0, 2.0))
    intrinsic = 0.25 + 0.80 * hp_strength + 0.35 * dps_strength
    if elixir_share <= 0.0:
        elixir_share = intrinsic
    full_value = 0.75 * elixir_share + 0.25 * intrinsic
    return float(full_value * hp_fraction)


def _board_value_edge_p0(projection: LeafProjection) -> float:
    values = {
        player_id: float(
            sum(
                _entity_remaining_value(entity)
                for entity in _public_combat_entities(projection, player_id)
            )
        )
        for player_id in (0, 1)
    }
    return float(np.clip((values[0] - values[1]) / 16.0, -1.0, 1.0))


def _standing_crowns(
    projection: LeafProjection,
    player_id: int,
) -> list[LeafCrown]:
    return [
        tower
        for tower in projection.crowns
        if tower.alive and tower.player_id == player_id and tower.hp > 0.0
    ]


def _target_distance(entity: LeafCombat, tower: LeafCrown) -> float:
    dx = tower.x - entity.x
    dy = tower.y - entity.y
    distance_sq = dx * dx + dy * dy
    discount = max(0, int(tower.target_distance_discount_sq_units or 0))
    return math.sqrt(max(0.0, distance_sq - discount / 1_000_000.0))


def _entity_tower_danger(entity: LeafCombat, towers: list[LeafCrown]) -> float:
    if not towers or not entity.can_attack_ground:
        return 0.0
    tower = min(towers, key=lambda candidate: _target_distance(entity, candidate))
    distance_to_reach = max(
        0.0,
        float(_target_distance(entity, tower)) - max(0.0, float(entity.attack_range)),
    )
    if entity.kind == 0:
        speed = logic_speed_to_tiles_per_second(max(0.0, float(entity.speed)))
        if speed <= 1e-9 and distance_to_reach > 0.0:
            return 0.0
        eta_seconds = distance_to_reach / max(speed, 1e-9)
    else:
        if distance_to_reach > 0.0:
            return 0.0
        eta_seconds = 0.0
    proximity = math.exp(-min(30.0, eta_seconds) / 4.0)
    tower_hp_fraction = float(
        np.clip(float(tower.hp) / max(1.0, float(tower.max_hp)), 0.0, 1.0)
    )
    vulnerability = 0.60 + 0.40 * (1.0 - tower_hp_fraction)
    return float(_entity_remaining_value(entity) * proximity * vulnerability)


def _tower_danger_sum_to_player(projection: LeafProjection, player_id: int) -> float:
    towers = _standing_crowns(projection, player_id)
    return float(
        sum(
            _entity_tower_danger(entity, towers)
            for entity in _public_combat_entities(projection, 1 - player_id)
        )
    )


def potential_breakdown_from_projection(
    projection: LeafProjection,
) -> PotentialBreakdown:
    player0, player1 = projection.players
    p0_princess_frac, p0_king_frac = _tower_fractions(player0)
    p1_princess_frac, p1_king_frac = _tower_fractions(player1)
    crown_diff = float(_crown_count(player0) - _crown_count(player1)) / 3.0
    princess_pressure = (1.0 - p1_princess_frac) - (1.0 - p0_princess_frac)
    p1_princess_alive = int(player1.current_hp[0] > 0.0) + int(
        player1.current_hp[1] > 0.0
    )
    p0_princess_alive = int(player0.current_hp[0] > 0.0) + int(
        player0.current_hp[1] > 0.0
    )
    p1_king_active = _king_active(projection, 1)
    p0_king_active = _king_active(projection, 0)
    p0_king_weight = (
        0.0
        if (p1_princess_alive == 2 and not p1_king_active)
        else (0.05 if p1_princess_alive == 2 else (0.25 if p1_princess_alive == 1 else 0.60))
    )
    p1_king_weight = (
        0.0
        if (p0_princess_alive == 2 and not p0_king_active)
        else (0.05 if p0_princess_alive == 2 else (0.25 if p0_princess_alive == 1 else 0.60))
    )
    king_pressure = p0_king_weight * (1.0 - p1_king_frac) - p1_king_weight * (
        1.0 - p0_king_frac
    )
    starting_hps = [hp for player in projection.players for hp in player.starting_hp]
    tiebreak_scale = max([1.0, *starting_hps]) * 1000.0
    tiebreak_edge = float(
        (
            player0.lowest_standing_hp_milli
            - player1.lowest_standing_hp_milli
        )
        / tiebreak_scale
    )
    p0_early_king_chip = (1.0 - p1_king_frac) if p1_princess_alive == 2 else 0.0
    p1_early_king_chip = (1.0 - p0_king_frac) if p0_princess_alive == 2 else 0.0
    early_king_penalty = p0_early_king_chip - p1_early_king_chip
    danger_to_p0 = _tower_danger_sum_to_player(projection, 0)
    danger_to_p1 = _tower_danger_sum_to_player(projection, 1)
    tower_danger = float(np.clip((danger_to_p1 - danger_to_p0) / 8.0, -1.0, 1.0))
    return PotentialBreakdown(
        crowns=crown_diff,
        princess_pressure=princess_pressure,
        king_pressure=king_pressure,
        tiebreak_edge=tiebreak_edge,
        early_king_penalty=early_king_penalty,
        board_value=_board_value_edge_p0(projection),
        tower_danger=tower_danger,
    )


def reward_potential_from_projection(
    projection: LeafProjection,
    profile: str = OBJECTIVE_V1,
) -> float:
    breakdown = potential_breakdown_from_projection(projection)
    if profile == OBJECTIVE_V1:
        potential = breakdown.objective_v1
    elif profile == DEFENSE_V2:
        potential = breakdown.defense_v2
    elif profile == DEFENSE_V3:
        potential = breakdown.defense_v3
    else:
        raise ValueError(
            f"unknown reward profile {profile!r}; expected one of {REWARD_PROFILES}"
        )
    return float(np.clip(potential, -1.5, 1.5))


def reward_win_prob_from_projection(
    projection: LeafProjection,
    profile: str = OBJECTIVE_V1,
) -> float:
    if projection.game_over:
        if projection.winner is None:
            return 0.5
        return 1.0 if projection.winner == 0 else 0.0
    potential = reward_potential_from_projection(projection, profile)
    return float(1.0 / (1.0 + np.exp(-2.5 * potential)))
