from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity

from .reward_model import incoming_tower_danger, public_combat_value


@dataclass(frozen=True)
class DefenseScenarioSpec:
    learner_player: int
    tower_slot: str
    threat_cards: tuple[str, ...]
    initial_danger: float
    initial_tower_fraction: float
    initial_defender_resources: float
    start_tick: int


def _crown_tower(
    battle: BattleState,
    player_id: int,
    slot: str,
) -> Building:
    for entity in battle.entities.values():
        if (
            isinstance(entity, Building)
            and entity.is_alive
            and entity.player_id == player_id
            and getattr(entity, "_crown_tower_slot", None) == slot
        ):
            return entity
    raise ValueError(f"missing player {player_id} {slot} Crown Tower")


def tower_fraction(battle: BattleState, player_id: int, slot: str) -> float:
    if slot not in {"left", "right", "king"}:
        raise ValueError("tower slot must be left, right, or king")
    current = float(getattr(battle.players[player_id], f"{slot}_tower_hp"))
    starting = float(
        battle._starting_tower_hps.get(player_id, {}).get(slot, max(1.0, current))
    )
    return float(
        np.clip(
            current / max(1.0, starting),
            0.0,
            1.0,
        )
    )


def eligible_threat_cards(battle: BattleState, player_id: int) -> tuple[str, ...]:
    """Return troop cards in the player's actual eight-card deck."""

    if player_id not in (0, 1):
        raise ValueError("player_id must be 0 or 1")
    cards: list[str] = []
    for card_name in battle.players[player_id].deck:
        stats = battle.card_loader.get_card(card_name)
        if stats is not None and str(getattr(stats, "card_type", "")) == "Troop":
            cards.append(card_name)
    return tuple(cards)


def _sample_threat_cards(
    battle: BattleState,
    attacker: int,
    *,
    rng: random.Random,
    minimum_elixir: int,
    maximum_elixir: int,
) -> tuple[str, ...]:
    eligible = list(eligible_threat_cards(battle, attacker))
    if not eligible:
        raise ValueError("opponent deck contains no troop cards")
    rng.shuffle(eligible)
    selected: list[str] = []
    total = 0
    for card_name in eligible:
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        cost = max(1, int(getattr(stats, "mana_cost", 0) or 0))
        if selected and total + cost > maximum_elixir:
            continue
        selected.append(card_name)
        total += cost
        if total >= minimum_elixir:
            break
    if total < minimum_elixir:
        # Use the strongest actual troop once more rather than injecting a card
        # absent from the sampled deck. Repeated cards are legal across a real
        # cycle and keep the scenario generator deck-general.
        strongest = max(
            eligible,
            key=lambda name: int(
                getattr(battle.card_loader.get_card(name), "mana_cost", 0) or 0
            ),
        )
        strongest_stats = battle.card_loader.get_card(strongest)
        assert strongest_stats is not None
        strongest_cost = max(1, int(getattr(strongest_stats, "mana_cost", 0) or 0))
        while total < minimum_elixir and total + strongest_cost <= maximum_elixir:
            selected.append(strongest)
            total += strongest_cost
    return tuple(selected)


def apply_defense_scenario(
    battle: BattleState,
    learner_player: int,
    *,
    rng: random.Random,
    minimum_elixir: int = 8,
    maximum_elixir: int = 12,
    tower_slot: str | None = None,
) -> DefenseScenarioSpec:
    """Spawn an immediate, deck-derived enemy push toward one Princess Tower."""

    if learner_player not in (0, 1):
        raise ValueError("learner_player must be 0 or 1")
    if not 1 <= minimum_elixir <= maximum_elixir:
        raise ValueError("scenario elixir bounds are invalid")
    chosen_slot = tower_slot or rng.choice(("left", "right"))
    if chosen_slot not in {"left", "right"}:
        raise ValueError("tower_slot must be left or right")
    attacker = 1 - learner_player
    cards = _sample_threat_cards(
        battle,
        attacker,
        rng=rng,
        minimum_elixir=minimum_elixir,
        maximum_elixir=maximum_elixir,
    )
    tower = _crown_tower(battle, learner_player, chosen_slot)
    direction_to_center = 1.0 if learner_player == 0 else -1.0
    base_y = float(tower.position.y) + 5.5 * direction_to_center

    for index, card_name in enumerate(cards):
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        before = set(battle.entities)
        x_offset = 0.35 * (index - 0.5 * (len(cards) - 1))
        battle._spawn_unit_at_position(
            Position(float(tower.position.x) + x_offset, base_y + 0.25 * index),
            attacker,
            stats,
        )
        for entity_id in set(battle.entities) - before:
            entity: Entity = battle.entities[entity_id]
            entity.deploy_delay_remaining = 0.0
            entity.placement_pending = False

    # The defender gets a full hand/elixir response. The initial push is an
    # episode condition, so reset-time reward bookkeeping happens after this.
    battle.players[learner_player].elixir = battle.players[learner_player].max_elixir
    return DefenseScenarioSpec(
        learner_player=learner_player,
        tower_slot=chosen_slot,
        threat_cards=cards,
        initial_danger=incoming_tower_danger(battle, learner_player),
        initial_tower_fraction=tower_fraction(battle, learner_player, chosen_slot),
        initial_defender_resources=(
            float(battle.players[learner_player].elixir)
            + public_combat_value(battle, learner_player)
        ),
        start_tick=int(battle.tick),
    )


def defense_scenario_resource_loss(
    battle: BattleState,
    scenario: DefenseScenarioSpec,
) -> float:
    """Return net defensive resources consumed, crediting surviving material.

    Elixir regenerated during the response and public remaining troop/building
    value both count toward the defender's terminal resources.  This prevents
    a clear-at-any-cost policy from receiving the same target as an efficient
    defense that leaves elixir or a counterpush on the board.
    """

    current_resources = (
        float(battle.players[scenario.learner_player].elixir)
        + public_combat_value(battle, scenario.learner_player)
    )
    return float(
        np.clip(
            (
                scenario.initial_defender_resources
                - current_resources
            )
            / max(1.0, scenario.initial_defender_resources),
            0.0,
            1.0,
        )
    )


def defense_scenario_outcome(
    battle: BattleState,
    scenario: DefenseScenarioSpec,
    *,
    tower_loss_weight: float = 6.0,
    resource_loss_weight: float = 1.0,
) -> float:
    """Score clearance, tower preservation, and net defensive efficiency."""

    if tower_loss_weight < 0.0 or resource_loss_weight < 0.0:
        raise ValueError("defense scenario outcome weights must be non-negative")

    remaining_ratio = float(
        np.clip(
            incoming_tower_danger(battle, scenario.learner_player)
            / max(0.05, scenario.initial_danger),
            0.0,
            1.0,
        )
    )
    clearance = 1.0 - remaining_ratio
    tower_loss = max(
        0.0,
        scenario.initial_tower_fraction
        - tower_fraction(battle, scenario.learner_player, scenario.tower_slot),
    )
    resource_loss = defense_scenario_resource_loss(battle, scenario)
    return float(
        np.clip(
            2.0 * clearance
            - 1.0
            - tower_loss_weight * tower_loss
            - resource_loss_weight * resource_loss,
            -1.0,
            1.0,
        )
    )
