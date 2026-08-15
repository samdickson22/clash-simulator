"""Exact state snapshots and first-divergence diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clasher.battle import BattleState, PendingSpellCast
from clasher.entities import Entity


@dataclass(frozen=True)
class StateDivergence:
    path: str
    expected: Any
    actual: Any
    expected_type: str
    actual_type: str

    def __str__(self) -> str:
        return (
            f"first divergence at {self.path}: expected "
            f"{self.expected!r} ({self.expected_type}), got "
            f"{self.actual!r} ({self.actual_type})"
        )


class TorchParityError(AssertionError):
    """Raised when PyTorch shadow execution differs from the Python oracle."""

    def __init__(self, divergence: StateDivergence):
        self.divergence = divergence
        super().__init__(str(divergence))


def _entity_snapshot(entity: Entity) -> dict[str, Any]:
    """Return behavior-bearing entity state without derived Python caches."""

    return {
        "class": type(entity).__name__,
        "id": entity.id,
        "player_id": entity.player_id,
        "card": getattr(entity.card_stats, "name", None),
        "position": (entity.position.x, entity.position.y),
        "hitpoints": entity.hitpoints,
        "max_hitpoints": entity.max_hitpoints,
        "damage": entity.damage,
        "range": entity.range,
        "sight_range": entity.sight_range,
        "attack_cooldown": entity.attack_cooldown,
        "load_time": entity.load_time,
        "deploy_delay_remaining": entity.deploy_delay_remaining,
        "placement_delay_total": entity.placement_delay_total,
        "placement_pending": entity.placement_pending,
        "forced_movement_active": entity.forced_movement_active,
        "target_id": entity.target_id,
        "is_alive": entity.is_alive,
        "is_air_unit": entity.is_air_unit,
        "entity_kind": entity.entity_kind,
        "stun_timer": entity.stun_timer,
        "freeze_expiry_time": entity.freeze_expiry_time,
        "slow_timer": entity.slow_timer,
        "slow_multiplier": entity.slow_multiplier,
        "haste_timer": entity.haste_timer,
        "last_attack_time": entity.last_attack_time,
        "movement_vector": (
            entity._movement_vector_x_units,
            entity._movement_vector_y_units,
            entity._movement_vector_count,
            entity._movement_vector_bypasses_cap,
        ),
        "facing": (entity._facing_x_units, entity._facing_y_units),
        "lane_id": entity._native_lane_id,
        "death_spawn_immunity_ms": entity._death_spawn_target_immunity_elapsed_ms,
        "pending_projectile_max_duration_ms": entity._pending_projectile_max_duration_ms,
        "mechanics": tuple(type(mechanic).__name__ for mechanic in entity.mechanics),
        "speed": getattr(entity, "speed", None),
        "lifetime_elapsed": getattr(entity, "lifetime_elapsed", None),
        "lifetime_decay_work": getattr(entity, "lifetime_decay_work", None),
        "lifetime_tick_carry_ms": getattr(entity, "lifetime_tick_carry_ms", None),
        "requires_activation": getattr(entity, "requires_activation", None),
        "activation_delay_remaining": getattr(
            entity, "activation_delay_remaining", None
        ),
        "activation_first_hit_delay_remaining": getattr(
            entity, "activation_first_hit_delay_remaining", None
        ),
        "tower_slot": getattr(entity, "_crown_tower_slot", None),
        "tower_active": getattr(entity, "_tower_active", None),
    }


def battle_snapshot(battle: BattleState) -> dict[str, Any]:
    """Capture externally visible and behavior-bearing mutable battle state.

    Values are deliberately not coerced.  ``first_divergence`` therefore
    catches both value changes and scalar-kind changes (for example int to
    float), which are part of the simulator contract.
    """

    return {
        "time": battle.time,
        "tick": battle.tick,
        "dt": battle.dt,
        "double_elixir": battle.double_elixir,
        "triple_elixir": battle.triple_elixir,
        "overtime": battle.overtime,
        "sudden_death": battle.sudden_death,
        "game_over": battle.game_over,
        "winner": battle.winner,
        "next_entity_id": battle.next_entity_id,
        "step_tick_remainder": battle._step_tick_remainder,
        "next_spell_cast_sequence": battle._next_spell_cast_sequence,
        "pending_spell_casts": tuple(
            (
                cast.execute_at,
                cast.sequence,
                cast.spell_name,
                cast.player_id,
                cast.position.x,
                cast.position.y,
            )
            for cast in battle._pending_spell_casts
            if isinstance(cast, PendingSpellCast)
        ),
        "rng_state": battle.rng.getstate(),
        "players": tuple(
            {
                "player_id": player.player_id,
                "elixir": player.elixir,
                "max_elixir": player.max_elixir,
                "next_card_refill_cooldown_ms": player.next_card_refill_cooldown_ms,
                "hand": tuple(player.hand),
                "deck": tuple(player.deck),
                "cycle_queue": tuple(player.cycle_queue),
                "king_tower_hp": player.king_tower_hp,
                "left_tower_hp": player.left_tower_hp,
                "right_tower_hp": player.right_tower_hp,
            }
            for player in battle.players
        ),
        "entities": tuple(
            _entity_snapshot(entity)
            for entity in sorted(battle.entities.values(), key=lambda value: value.id)
        ),
    }


def first_divergence(
    expected: Any,
    actual: Any,
    *,
    path: str = "battle",
) -> StateDivergence | None:
    """Return the first deterministic structural, type, or value mismatch."""

    if type(expected) is not type(actual):
        return StateDivergence(
            path,
            expected,
            actual,
            type(expected).__name__,
            type(actual).__name__,
        )
    if isinstance(expected, dict):
        expected_keys = tuple(expected)
        actual_keys = tuple(actual)
        if expected_keys != actual_keys:
            return StateDivergence(
                f"{path}.keys",
                expected_keys,
                actual_keys,
                type(expected_keys).__name__,
                type(actual_keys).__name__,
            )
        for key in expected_keys:
            mismatch = first_divergence(
                expected[key], actual[key], path=f"{path}.{key}"
            )
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(expected, (tuple, list)):
        if len(expected) != len(actual):
            return StateDivergence(
                f"{path}.length",
                len(expected),
                len(actual),
                "int",
                "int",
            )
        for index, (left, right) in enumerate(zip(expected, actual)):
            mismatch = first_divergence(left, right, path=f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None
    if expected != actual:
        return StateDivergence(
            path,
            expected,
            actual,
            type(expected).__name__,
            type(actual).__name__,
        )
    return None
