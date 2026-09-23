from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.kinematics import logic_speed_to_tiles_per_second

OBJECTIVE_V1 = "objective-v1"
DEFENSE_V2 = "defense-v2"
REWARD_PROFILES = (OBJECTIVE_V1, DEFENSE_V2)

@dataclass(frozen=True)
class PotentialBreakdown:
    """Signed public-state potential components from player zero's view."""

    crowns: float
    princess_pressure: float
    king_pressure: float
    tiebreak_edge: float
    early_king_penalty: float
    board_value: float
    tower_danger: float

    @property
    def objective_v1(self) -> float:
        return float(
            0.55 * self.crowns
            + 0.25 * self.princess_pressure
            + 0.10 * self.king_pressure
            + 0.10 * self.tiebreak_edge
            - 0.20 * self.early_king_penalty
        )

    @property
    def defense_v2(self) -> float:
        # Tower outcomes remain dominant. These small potential terms make
        # preserving a counterpush and removing immediate danger observable
        # before the consequence reaches a Crown Tower.
        return float(
            self.objective_v1 + 0.08 * self.board_value + 0.12 * self.tower_danger
        )


def _safe_frac(value: float, denom: float) -> float:
    return float(value) / max(1e-6, float(denom))


def _princess_alive_count(left_hp: float, right_hp: float) -> int:
    return int(left_hp > 0.0) + int(right_hp > 0.0)


def _king_active(battle: BattleState, player_id: int) -> bool:
    for entity in battle.entities.values():
        if not isinstance(entity, Building) or not entity.is_alive:
            continue
        if entity.player_id != player_id:
            continue
        name = getattr(getattr(entity, "card_stats", None), "name", "")
        if name == "KingTower" or bool(getattr(entity, "_is_king_tower", False)):
            return bool(getattr(entity, "_tower_active", False))
    return False


def _tower_fractions(
    battle: BattleState,
    player_id: int,
) -> tuple[float, float]:
    player = battle.players[player_id]
    start = battle._starting_tower_hps.get(player_id, {})
    start_left = float(start.get("left", max(1.0, player.left_tower_hp)))
    start_right = float(start.get("right", max(1.0, player.right_tower_hp)))
    start_king = float(start.get("king", max(1.0, player.king_tower_hp)))
    start_princess = max(1.0, 0.5 * (start_left + start_right))
    left_frac = np.clip(_safe_frac(player.left_tower_hp, start_princess), 0.0, 1.0)
    right_frac = np.clip(_safe_frac(player.right_tower_hp, start_princess), 0.0, 1.0)
    king_frac = np.clip(_safe_frac(player.king_tower_hp, start_king), 0.0, 1.0)
    princess_frac = np.clip((left_frac + right_frac) / 2.0, 0.0, 1.0)
    return float(princess_frac), float(king_frac)


def _tiebreak_edge_p0(battle: BattleState) -> float:
    """Return the signed in-game tiebreak edge on a shared HP scale.

    Destroyed towers are crowns, not zero-health tiebreak candidates.  The
    actual match rule compares the lowest *standing* Crown Tower by absolute
    hitpoints, so comparing per-tower health fractions would also be wrong for
    a King Tower versus a Princess Tower.
    """
    starting_hps = [
        float(hp)
        for towers in battle._starting_tower_hps.values()
        for hp in towers.values()
    ]
    scale = max([1.0, *starting_hps]) * 1000.0
    return float(
        (battle._lowest_remaining_tower_hp(0) - battle._lowest_remaining_tower_hp(1))
        / scale
    )


def _is_crown_tower(entity: Entity) -> bool:
    return bool(
        isinstance(entity, Building)
        and getattr(entity, "_crown_tower_slot", None) in {"left", "right", "king"}
    )


def _public_combat_entities(battle: BattleState, player_id: int) -> list[Entity]:
    return [
        entity
        for entity in battle.entities.values()
        if entity.is_alive
        and entity.player_id == player_id
        and isinstance(entity, (Troop, Building))
        and not _is_crown_tower(entity)
        and entity.is_visible_to(0)
        and entity.is_visible_to(1)
    ]


def _entity_remaining_value(entity: Entity) -> float:
    """Return a card-agnostic public estimate of remaining board value.

    The deployment cost is divided over the serialized formation size, then
    blended with HP and DPS so generated children with zero direct cost still
    retain value. No card identity or combo-specific rule is consulted.
    """

    stats = entity.card_stats
    max_hp = max(1.0, float(entity.max_hitpoints or 1.0))
    hp_fraction = float(np.clip(float(entity.hitpoints) / max_hp, 0.0, 1.0))
    formation_size = max(
        1,
        int(getattr(stats, "summon_count", 0) or 0)
        + int(getattr(stats, "summon_character_second_count", 0) or 0),
    )
    elixir_share = max(0.0, float(getattr(stats, "mana_cost", 0) or 0)) / formation_size

    hit_speed_seconds = max(0.25, float(getattr(stats, "hit_speed", 0) or 0) / 1000.0)
    dps = max(0.0, float(entity.damage)) / hit_speed_seconds
    hp_strength = float(np.clip(math.sqrt(max_hp / 1000.0), 0.25, 2.0))
    dps_strength = float(np.clip(dps / 180.0, 0.0, 2.0))
    intrinsic = 0.25 + 0.80 * hp_strength + 0.35 * dps_strength
    if elixir_share <= 0.0:
        elixir_share = intrinsic
    full_value = 0.75 * elixir_share + 0.25 * intrinsic
    return float(full_value * hp_fraction)


def _board_value_edge_p0(battle: BattleState) -> float:
    values = {
        player_id: sum(
            _entity_remaining_value(entity)
            for entity in _public_combat_entities(battle, player_id)
        )
        for player_id in (0, 1)
    }
    return float(np.clip((values[0] - values[1]) / 16.0, -1.0, 1.0))


def _standing_crown_towers(battle: BattleState, player_id: int) -> list[Building]:
    return [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.is_alive
        and entity.player_id == player_id
        and _is_crown_tower(entity)
        and entity.hitpoints > 0.0
    ]


def _entity_tower_danger(
    entity: Entity,
    towers: list[Building],
) -> float:
    if not towers or not entity._can_attack_ground():
        return 0.0

    tower = min(towers, key=entity.native_target_distance_to)
    distance_to_reach = max(
        0.0,
        float(entity.native_target_distance_to(tower)) - max(0.0, float(entity.range)),
    )
    if isinstance(entity, Troop):
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
        np.clip(float(tower.hitpoints) / max(1.0, float(tower.max_hitpoints)), 0.0, 1.0)
    )
    vulnerability = 0.60 + 0.40 * (1.0 - tower_hp_fraction)
    return float(_entity_remaining_value(entity) * proximity * vulnerability)


def _tower_danger_edge_p0(battle: BattleState) -> float:
    towers = {
        player_id: _standing_crown_towers(battle, player_id) for player_id in (0, 1)
    }
    danger_to_p0 = sum(
        _entity_tower_danger(entity, towers[0])
        for entity in _public_combat_entities(battle, 1)
    )
    danger_to_p1 = sum(
        _entity_tower_danger(entity, towers[1])
        for entity in _public_combat_entities(battle, 0)
    )
    return float(np.clip((danger_to_p1 - danger_to_p0) / 8.0, -1.0, 1.0))


def potential_breakdown_p0(battle: BattleState) -> PotentialBreakdown:
    """Compute all public, zero-sum-compatible potential components."""

    p0 = battle.players[0]
    p1 = battle.players[1]

    p0_princess_frac, p0_king_frac = _tower_fractions(battle, 0)
    p1_princess_frac, p1_king_frac = _tower_fractions(battle, 1)

    crown_diff = float(battle.get_crown_count(0) - battle.get_crown_count(1)) / 3.0
    princess_pressure = (1.0 - p1_princess_frac) - (1.0 - p0_princess_frac)

    p1_princess_alive = _princess_alive_count(p1.left_tower_hp, p1.right_tower_hp)
    p0_princess_alive = _princess_alive_count(p0.left_tower_hp, p0.right_tower_hp)
    p1_king_active = _king_active(battle, 1)
    p0_king_active = _king_active(battle, 0)

    p0_king_weight = (
        0.0
        if (p1_princess_alive == 2 and not p1_king_active)
        else (
            0.05
            if p1_princess_alive == 2
            else (0.25 if p1_princess_alive == 1 else 0.60)
        )
    )
    p1_king_weight = (
        0.0
        if (p0_princess_alive == 2 and not p0_king_active)
        else (
            0.05
            if p0_princess_alive == 2
            else (0.25 if p0_princess_alive == 1 else 0.60)
        )
    )

    king_pressure = p0_king_weight * (1.0 - p1_king_frac) - p1_king_weight * (
        1.0 - p0_king_frac
    )
    tiebreak_edge = _tiebreak_edge_p0(battle)

    # Penalize early king chip while both princess towers are still alive.
    p0_early_king_chip = (1.0 - p1_king_frac) if p1_princess_alive == 2 else 0.0
    p1_early_king_chip = (1.0 - p0_king_frac) if p0_princess_alive == 2 else 0.0
    early_king_penalty = p0_early_king_chip - p1_early_king_chip

    return PotentialBreakdown(
        crowns=crown_diff,
        princess_pressure=princess_pressure,
        king_pressure=king_pressure,
        tiebreak_edge=tiebreak_edge,
        early_king_penalty=early_king_penalty,
        board_value=_board_value_edge_p0(battle),
        tower_danger=_tower_danger_edge_p0(battle),
    )


def reward_potential_p0(battle: BattleState, profile: str = OBJECTIVE_V1) -> float:
    breakdown = potential_breakdown_p0(battle)
    if profile == OBJECTIVE_V1:
        potential = breakdown.objective_v1
    elif profile == DEFENSE_V2:
        potential = breakdown.defense_v2
    else:
        raise ValueError(
            f"unknown reward profile {profile!r}; expected one of {REWARD_PROFILES}"
        )
    return float(np.clip(potential, -1.5, 1.5))


def objective_potential_p0(battle: BattleState) -> float:
    """Legacy objective-v1 potential retained for checkpoint compatibility."""

    return reward_potential_p0(battle, OBJECTIVE_V1)


def objective_win_prob_p0(battle: BattleState) -> float:
    return reward_win_prob_p0(battle, OBJECTIVE_V1)


def reward_win_prob_p0(
    battle: BattleState,
    profile: str = OBJECTIVE_V1,
) -> float:
    if battle.game_over:
        if battle.winner is None:
            return 0.5
        return 1.0 if battle.winner == 0 else 0.0
    # Smooth squashing around 0.5 for planner bandit updates.
    potential = reward_potential_p0(battle, profile)
    return float(1.0 / (1.0 + np.exp(-2.5 * potential)))
