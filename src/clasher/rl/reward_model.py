from __future__ import annotations

from typing import Tuple

import numpy as np

from clasher.battle import BattleState
from clasher.entities import Building


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
) -> Tuple[float, float, float, float]:
    player = battle.players[player_id]
    start = battle._starting_tower_hps.get(player_id, {})
    start_left = float(start.get("left", max(1.0, player.left_tower_hp)))
    start_right = float(start.get("right", max(1.0, player.right_tower_hp)))
    start_king = float(start.get("king", max(1.0, player.king_tower_hp)))
    start_princess = max(1.0, 0.5 * (start_left + start_right))
    start_total = max(1.0, start_left + start_right + start_king)

    left_frac = np.clip(_safe_frac(player.left_tower_hp, start_princess), 0.0, 1.0)
    right_frac = np.clip(_safe_frac(player.right_tower_hp, start_princess), 0.0, 1.0)
    king_frac = np.clip(_safe_frac(player.king_tower_hp, start_king), 0.0, 1.0)
    princess_frac = np.clip((left_frac + right_frac) / 2.0, 0.0, 1.0)
    lowest_frac = float(min(left_frac, right_frac, king_frac))
    return float(princess_frac), float(king_frac), float(lowest_frac), float(start_total)


def objective_potential_p0(battle: BattleState) -> float:
    """Potential aligned with win condition, discouraging early king chip exploits."""
    p0 = battle.players[0]
    p1 = battle.players[1]

    p0_princess_frac, p0_king_frac, p0_lowest_frac, _ = _tower_fractions(battle, 0)
    p1_princess_frac, p1_king_frac, p1_lowest_frac, _ = _tower_fractions(battle, 1)

    crown_diff = float(p0.get_crown_count() - p1.get_crown_count()) / 3.0
    princess_pressure = (1.0 - p1_princess_frac) - (1.0 - p0_princess_frac)

    p1_princess_alive = _princess_alive_count(p1.left_tower_hp, p1.right_tower_hp)
    p0_princess_alive = _princess_alive_count(p0.left_tower_hp, p0.right_tower_hp)
    p1_king_active = _king_active(battle, 1)
    p0_king_active = _king_active(battle, 0)

    p0_king_weight = 0.0 if (p1_princess_alive == 2 and not p1_king_active) else (0.05 if p1_princess_alive == 2 else (0.25 if p1_princess_alive == 1 else 0.60))
    p1_king_weight = 0.0 if (p0_princess_alive == 2 and not p0_king_active) else (0.05 if p0_princess_alive == 2 else (0.25 if p0_princess_alive == 1 else 0.60))

    king_pressure = p0_king_weight * (1.0 - p1_king_frac) - p1_king_weight * (1.0 - p0_king_frac)
    tiebreak_edge = p0_lowest_frac - p1_lowest_frac

    # Penalize early king chip while both princess towers are still alive.
    p0_early_king_chip = (1.0 - p1_king_frac) if p1_princess_alive == 2 else 0.0
    p1_early_king_chip = (1.0 - p0_king_frac) if p0_princess_alive == 2 else 0.0
    early_king_penalty = p0_early_king_chip - p1_early_king_chip

    potential = (
        0.55 * crown_diff
        + 0.25 * princess_pressure
        + 0.10 * king_pressure
        + 0.10 * tiebreak_edge
        - 0.20 * early_king_penalty
    )
    return float(np.clip(potential, -1.5, 1.5))


def objective_win_prob_p0(battle: BattleState) -> float:
    if battle.game_over:
        if battle.winner is None:
            return 0.5
        return 1.0 if battle.winner == 0 else 0.0
    # Smooth squashing around 0.5 for planner bandit updates.
    potential = objective_potential_p0(battle)
    return float(1.0 / (1.0 + np.exp(-2.5 * potential)))
