#!/usr/bin/env python3
"""Stress enabled-card interactions and scalar/accelerated state parity."""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from clasher.arena import Position
from clasher.battle import BattleState, STANDARD_MATCH_TICKS
from clasher.card_aliases import resolve_card_name
from clasher.card_types import CardStatsCompat
from clasher.entities import Building, Troop
from clasher.factory.card_factory import card_from_gamedata
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.kinematics import logic_units_to_tiles, tiles_to_logic_units
from clasher.spells import SPELL_REGISTRY
from clasher.rl.selfplay_env import SelfPlayBattleEnv


@dataclass
class RuntimeUnitSpec:
    """One combat entity reachable from an enabled base card."""

    label: str
    internal_name: str
    deck_card: str | None = None
    character_data: dict[str, Any] | None = None
    source_path: str | None = None

    @property
    def is_child(self) -> bool:
        return self.deck_card is None


def _enabled_cards(battle: BattleState) -> list[str]:
    decks = json.loads((REPO_ROOT / "decks.json").read_text())
    definitions = battle.card_loader.load_card_definitions()
    return sorted(
        {
            resolve_card_name(card, definitions)
            for deck in decks["decks"]
            for card in deck["cards"]
        }
    )


def _walk_character_payloads(
    value: Any,
    path: str,
) -> list[tuple[str, dict[str, Any], str]]:
    """Return combat characters nested below one enabled base card.

    Evolution and hero presentation branches are separate playable variants,
    not entities produced by a base-deck card, so they are intentionally not
    reachable from this audit scope.
    """
    found: list[tuple[str, dict[str, Any], str]] = []
    if isinstance(value, dict):
        source = str(value.get("source", ""))
        name = value.get("name")
        if (
            isinstance(name, str)
            and name
            and value.get("hitpoints") is not None
            and (
                source.startswith("characters")
                or source == "buildings"
            )
        ):
            found.append((name, value, path))
        for key, child in value.items():
            if key in {"evolvedSpellsData", "heroData"}:
                continue
            found.extend(
                _walk_character_payloads(child, f"{path}.{key}")
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(
                _walk_character_payloads(child, f"{path}[{index}]")
            )
    return found


def _runtime_unit_specs(
    battle: BattleState,
    *,
    include_reachable_children: bool,
) -> dict[str, RuntimeUnitSpec]:
    """Build deck-unit and nested-child specs from enabled normalized data."""
    enabled_cards = _enabled_cards(battle)
    direct_cards = [
        name for name in enabled_cards if name not in SPELL_REGISTRY
    ]
    specs: dict[str, RuntimeUnitSpec] = {}
    direct_internal_owners: dict[str, set[str]] = {}
    direct_payload_signatures: dict[str, set[str]] = {}

    for card_name in direct_cards:
        stats = battle.card_loader.get_card(card_name)
        if stats is None:
            raise AssertionError(f"enabled card has no stats: {card_name}")
        character_data = stats._raw_entry.get("summonCharacterData") or {}
        internal_name = character_data.get("name")
        if not isinstance(internal_name, str) or not internal_name:
            raise AssertionError(
                f"enabled unit has no normalized character name: {card_name}"
            )
        direct_internal_owners.setdefault(internal_name, set()).add(card_name)
        direct_payload_signatures.setdefault(internal_name, set()).add(
            json.dumps(
                character_data,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        specs[card_name] = RuntimeUnitSpec(
            label=card_name,
            internal_name=internal_name,
            deck_card=card_name,
            source_path=f"{card_name}.summonCharacterData",
        )

    if not include_reachable_children:
        return specs

    child_variants: dict[
        str,
        dict[str, tuple[dict[str, Any], str]],
    ] = {}
    for card_name in enabled_cards:
        stats = battle.card_loader.get_card(card_name)
        if stats is None:
            raise AssertionError(f"enabled card has no stats: {card_name}")
        for internal_name, character_data, source_path in _walk_character_payloads(
            stats._raw_entry,
            card_name,
        ):
            serialized = json.dumps(
                character_data,
                sort_keys=True,
                separators=(",", ":"),
            )
            # A normalized deployment action can contain a lean copy of its
            # own card's character payload, while other cards can legitimately
            # spawn a same-named variant. Suppress the former and suppress
            # byte-identical cross-card copies, but retain a distinct payload.
            if (
                card_name in direct_internal_owners.get(internal_name, set())
                or serialized in direct_payload_signatures.get(
                    internal_name,
                    set(),
                )
            ):
                continue
            child_variants.setdefault(internal_name, {})[serialized] = (
                character_data,
                source_path,
            )

    for internal_name in sorted(child_variants):
        variants = child_variants[internal_name]
        for index, (_, (character_data, source_path)) in enumerate(
            sorted(variants.items())
        ):
            label = (
                internal_name
                if len(variants) == 1
                else f"{internal_name}#{index + 1}"
            )
            if label in specs:
                label = f"{label} (child)"
            specs[label] = RuntimeUnitSpec(
                label=label,
                internal_name=internal_name,
                character_data=copy.deepcopy(character_data),
                source_path=source_path,
            )
    return dict(sorted(specs.items()))


def _child_card_stats(spec: RuntimeUnitSpec) -> CardStatsCompat:
    """Materialize a nested payload through the production data factories."""
    if spec.character_data is None:
        raise AssertionError(f"child unit has no character data: {spec.label}")
    character_data = copy.deepcopy(spec.character_data)
    rarity = character_data.get("rarity", "Common")
    if character_data.get("source") == "buildings":
        entry = {
            "id": 0,
            "name": spec.internal_name,
            "rarity": rarity,
            "manaCost": 0,
            "tidType": "TID_CARD_TYPE_BUILDING",
            "summonCharacterData": character_data,
        }
        return CardStatsCompat.from_card_definition(card_from_gamedata(entry))
    return troop_from_character_data(
        spec.internal_name,
        character_data,
        elixir=0,
        rarity=rarity,
    )


def _spawn_runtime_unit(
    battle: BattleState,
    spec: RuntimeUnitSpec,
    player_id: int,
    position: Position,
) -> None:
    if spec.deck_card is not None:
        _spawn(battle, spec.deck_card, player_id, position)
        return
    stats = _child_card_stats(spec)
    if str(stats.card_type).lower() == "building":
        battle._spawn_entity(Building, position, player_id, stats)
    else:
        battle._spawn_unit_at_position(
            position,
            player_id,
            stats,
            snap_to_valid=False,
        )


def _spawn(battle: BattleState, name: str, player_id: int, position: Position) -> None:
    if name in SPELL_REGISTRY:
        SPELL_REGISTRY[name].cast(battle, player_id, position)
        return
    stats = battle.card_loader.get_card(name)
    if stats is None:
        raise AssertionError(f"enabled card has no stats: {name}")
    if str(stats.card_type).lower() == "building":
        battle._spawn_entity(Building, position, player_id, stats)
    else:
        battle._spawn_troop(position, player_id, stats)


def _discrete_state(entity, mirrored: bool) -> tuple:
    ability_states = []
    for mechanic in getattr(entity, "mechanics", ()):
        ability = getattr(mechanic, "ability", None)
        if ability is None:
            continue
        ability_states.append(
            (
                ability.name,
                ability.elixir_cost,
                ability.cooldown_ms,
                ability.duration_ms,
                ability.last_use_time,
                ability.is_active,
                ability.activation_time,
                getattr(mechanic, "_cloak_pending_until", None),
                getattr(mechanic, "_cast_lock_until", None),
            )
        )
    return (
        type(entity).__name__,
        1 - entity.player_id if mirrored else entity.player_id,
        getattr(entity.card_stats, "name", ""),
        entity.is_alive,
        bool(getattr(entity, "placement_pending", False)),
        bool(getattr(entity, "is_visible", True)),
        tuple(ability_states),
    )


def _numeric_state(entity, mirrored: bool) -> tuple[float | None, ...]:
    x_units = tiles_to_logic_units(entity.position.x)
    y_units = tiles_to_logic_units(entity.position.y)
    if mirrored:
        x_units = 18_000 - x_units
        y_units = 32_000 - y_units
    return (
        logic_units_to_tiles(x_units),
        logic_units_to_tiles(y_units),
        getattr(entity, "hitpoints", None),
        getattr(entity, "max_hitpoints", None),
        getattr(entity, "deploy_delay_remaining", None),
        getattr(entity, "attack_cooldown", None),
        getattr(entity, "stun_timer", None),
        getattr(entity, "slow_timer", None),
        getattr(entity, "freeze_timer", None),
    )


def _numeric_states_match(
    first: tuple[float | None, ...],
    second: tuple[float | None, ...],
    position_tolerance: float,
) -> bool:
    for index, (left, right) in enumerate(zip(first, second)):
        if left is None or right is None:
            if left is not right:
                return False
            continue
        tolerance = position_tolerance if index < 2 else 1e-6
        if abs(float(left) - float(right)) > tolerance:
            return False
    return True


def _assert_invariants(battle: BattleState, context: str) -> None:
    if not math.isfinite(battle.time):
        raise AssertionError(f"{context}: non-finite battle time {battle.time}")
    if battle.tick < 0:
        raise AssertionError(f"{context}: negative battle tick {battle.tick}")
    expected_time = battle.tick * battle.dt
    if abs(battle.time - expected_time) > 1e-8:
        raise AssertionError(
            f"{context}: time/tick drift time={battle.time} "
            f"tick={battle.tick} dt={battle.dt}"
        )
    for player_id, player in enumerate(battle.players):
        for label, value in (
            ("elixir", player.elixir),
            ("king_tower_hp", player.king_tower_hp),
            ("left_tower_hp", player.left_tower_hp),
            ("right_tower_hp", player.right_tower_hp),
        ):
            if not math.isfinite(float(value)):
                raise AssertionError(
                    f"{context}: player {player_id} has non-finite "
                    f"{label}={value}"
                )
        if not -1e-9 <= player.elixir <= 10.0 + 1e-9:
            raise AssertionError(
                f"{context}: player {player_id} elixir out of bounds "
                f"{player.elixir}"
            )
        for label, value in (
            ("king_tower_hp", player.king_tower_hp),
            ("left_tower_hp", player.left_tower_hp),
            ("right_tower_hp", player.right_tower_hp),
        ):
            if value < -1e-9:
                raise AssertionError(
                    f"{context}: player {player_id} has negative "
                    f"{label}={value}"
                )
    for entity in battle.entities.values():
        for label, value in (
            ("x", entity.position.x),
            ("y", entity.position.y),
            ("hitpoints", entity.hitpoints),
            ("max_hitpoints", entity.max_hitpoints),
            ("damage", entity.damage),
            ("attack_cooldown", entity.attack_cooldown),
            ("deploy_delay_remaining", entity.deploy_delay_remaining),
            ("stun_timer", entity.stun_timer),
            ("slow_timer", entity.slow_timer),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise AssertionError(
                    f"{context}: entity {entity.id} has non-finite {label}={value}"
                )
        for label, value in (("x", entity.position.x), ("y", entity.position.y)):
            logic_value = float(value) * 1000.0
            if abs(logic_value - round(logic_value)) > 1e-8:
                raise AssertionError(
                    f"{context}: entity {entity.id} has off-grid {label}={value}"
                )
        if entity.hitpoints < -1e-9:
            raise AssertionError(
                f"{context}: entity {entity.id} has negative "
                f"hitpoints={entity.hitpoints}"
            )
        if entity.hitpoints > entity.max_hitpoints + 1e-6:
            raise AssertionError(
                f"{context}: entity {entity.id} exceeds max hitpoints "
                f"{entity.hitpoints}>{entity.max_hitpoints}"
            )
        target_id = getattr(entity, "target_id", None)
        if target_id is not None and (
            not isinstance(target_id, int) or target_id < 0
        ):
            raise AssertionError(
                f"{context}: entity {entity.id} has invalid target id "
                f"{target_id!r}"
            )
        if isinstance(entity, (Troop, Building)) and entity.is_alive:
            if not (
                0.25 - 1e-9
                <= entity.position.x
                <= battle.arena.width - 0.25 + 1e-9
                and 0.25 - 1e-9
                <= entity.position.y
                <= battle.arena.height - 0.25 + 1e-9
            ):
                raise AssertionError(
                    f"{context}: entity {entity.id} center violates native spawn bounds at "
                    f"({entity.position.x}, {entity.position.y})"
                )


def _canonical_value(value, depth: int = 0):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AssertionError(f"non-finite state value {value}")
        return round(value, 9)
    if isinstance(value, Position):
        return (round(value.x, 9), round(value.y, 9))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_value(item, depth + 1) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_canonical_value(item, depth + 1) for item in value))
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(key), _canonical_value(item, depth + 1))
                for key, item in value.items()
                if isinstance(key, (str, int))
            )
        )
    if depth < 2 and hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            tuple(
                sorted(
                    (key, _canonical_value(item, depth + 1))
                    for key, item in vars(value).items()
                    if key not in {"battle_state", "card_stats"}
                )
            ),
        )
    return type(value).__name__


def _canonical_entity(entity) -> tuple:
    return (
        type(entity).__name__,
        getattr(entity.card_stats, "name", ""),
        _canonical_value(
            {
                key: value
                for key, value in vars(entity).items()
                if key not in {"battle_state", "card_stats"}
            }
        ),
    )


def _defensive_entity_state(entity) -> tuple:
    """Return combat state that friendly offensive payloads cannot change."""
    shields = tuple(
        (
            type(mechanic).__name__,
            getattr(mechanic, "current_shield", None),
        )
        for mechanic in getattr(entity, "mechanics", ())
        if hasattr(mechanic, "current_shield")
    )
    return (
        entity.is_alive,
        entity.hitpoints,
        entity.max_hitpoints,
        entity.stun_timer,
        entity.slow_timer,
        entity.freeze_expiry_time,
        getattr(entity, "_knockback_target", None),
        getattr(entity, "_knockback_velocity_work", 0),
        shields,
    )


def _compare_scalar_fast(scalar: BattleState, fast: BattleState) -> str | None:
    scalar_battle = (
        scalar.time,
        scalar.tick,
        scalar.game_over,
        scalar.winner,
        scalar.double_elixir,
        scalar.triple_elixir,
        scalar.overtime,
        scalar.sudden_death,
        tuple(_canonical_value(vars(player)) for player in scalar.players),
    )
    fast_battle = (
        fast.time,
        fast.tick,
        fast.game_over,
        fast.winner,
        fast.double_elixir,
        fast.triple_elixir,
        fast.overtime,
        fast.sudden_death,
        tuple(_canonical_value(vars(player)) for player in fast.players),
    )
    if scalar_battle != fast_battle:
        return f"battle state differs: scalar={scalar_battle}; fast={fast_battle}"
    if scalar.entities.keys() != fast.entities.keys():
        return (
            f"entity ids differ: scalar={sorted(scalar.entities)} "
            f"fast={sorted(fast.entities)}"
        )
    for entity_id in scalar.entities:
        left = _canonical_entity(scalar.entities[entity_id])
        right = _canonical_entity(fast.entities[entity_id])
        if left != right:
            return f"entity {entity_id} differs: scalar={left}; fast={right}"
    return None


def _compare_states(
    normal: BattleState,
    mirrored: BattleState,
    position_tolerance: float,
) -> str | None:
    normal_core = (
        round(normal.time, 9),
        normal.tick,
        normal.game_over,
        normal.double_elixir,
        normal.triple_elixir,
        normal.overtime,
        normal.sudden_death,
    )
    mirrored_core = (
        round(mirrored.time, 9),
        mirrored.tick,
        mirrored.game_over,
        mirrored.double_elixir,
        mirrored.triple_elixir,
        mirrored.overtime,
        mirrored.sudden_death,
    )
    if normal_core != mirrored_core:
        return f"battle flags differ: normal={normal_core}; mirrored={mirrored_core}"
    expected_winner = None if normal.winner is None else 1 - normal.winner
    if mirrored.winner != expected_winner:
        return (
            f"winner differs: normal={normal.winner}; mirrored={mirrored.winner}; "
            f"expected={expected_winner}"
        )
    for player_id in range(2):
        player = normal.players[player_id]
        counterpart = mirrored.players[1 - player_id]
        normal_player = (
            round(player.elixir, 9),
            round(player.king_tower_hp, 6),
            round(player.left_tower_hp, 6),
            round(player.right_tower_hp, 6),
        )
        mirrored_player = (
            round(counterpart.elixir, 9),
            round(counterpart.king_tower_hp, 6),
            round(counterpart.right_tower_hp, 6),
            round(counterpart.left_tower_hp, 6),
        )
        if normal_player != mirrored_player:
            return (
                f"player {player_id} differs: normal={normal_player}; "
                f"mirrored={mirrored_player}"
            )
    unmatched = list(mirrored.entities.values())
    for entity in normal.entities.values():
        discrete = _discrete_state(entity, False)
        numeric = _numeric_state(entity, False)
        matches: list[tuple[float, int]] = []
        for index, candidate in enumerate(unmatched):
            candidate_numeric = _numeric_state(candidate, True)
            if (
                _discrete_state(candidate, True) == discrete
                and _numeric_states_match(numeric, candidate_numeric, position_tolerance)
            ):
                position_error = (numeric[0] - candidate_numeric[0]) ** 2 + (
                    numeric[1] - candidate_numeric[1]
                ) ** 2
                matches.append((position_error, index))
        if not matches:
            candidates = [
                (candidate.id, _numeric_state(candidate, True))
                for candidate in unmatched
                if _discrete_state(candidate, True) == discrete
            ][:6]
            return (
                f"no mirror for entity {entity.id}: {discrete} {numeric}; "
                f"candidates={candidates}"
            )
        unmatched.pop(min(matches)[1])
    if unmatched:
        extras = [
            (entity.id, _discrete_state(entity, True), _numeric_state(entity, True))
            for entity in unmatched[:6]
        ]
        return f"extra mirrored entities: {extras}"
    return None


def _activate_ready_champion_abilities(
    normal: BattleState,
    mirrored: BattleState,
    context: str,
) -> None:
    """Press corresponding Champion buttons at their first legal frame."""
    for player_id in (0, 1):
        normal_ready = normal.can_activate_champion_ability(player_id)
        mirrored_ready = mirrored.can_activate_champion_ability(1 - player_id)
        if normal_ready != mirrored_ready:
            raise AssertionError(
                f"{context}: champion ability readiness differs for player "
                f"{player_id}: normal={normal_ready}, mirrored={mirrored_ready}"
            )
        if normal_ready:
            normal_activated = normal.activate_champion_ability(player_id)
            mirrored_activated = mirrored.activate_champion_ability(1 - player_id)
            if not normal_activated or not mirrored_activated:
                raise AssertionError(
                    f"{context}: matched ready Champion abilities did not activate"
                )


def _activate_ready_champion_abilities_same_side(
    scalar: BattleState,
    fast: BattleState,
    context: str,
) -> None:
    """Press identical Champion buttons in scalar/accelerated simulations."""
    for player_id in (0, 1):
        scalar_ready = scalar.can_activate_champion_ability(player_id)
        fast_ready = fast.can_activate_champion_ability(player_id)
        if scalar_ready != fast_ready:
            raise AssertionError(
                f"{context}: Champion readiness differs for player {player_id}: "
                f"scalar={scalar_ready}, fast={fast_ready}"
            )
        if scalar_ready:
            if not scalar.activate_champion_ability(player_id):
                raise AssertionError(f"{context}: scalar Champion activation failed")
            if not fast.activate_champion_ability(player_id):
                raise AssertionError(f"{context}: fast Champion activation failed")


def run_audit(
    start_seed: int,
    seeds: int,
    events: int,
    max_ticks: int,
    position_tolerance: float,
    max_entities: int,
) -> None:
    # Native deployment reflects only the forward axis; left/right character
    # order and per-member deploy stagger are intentionally not a 180-degree
    # state transform. Random stress therefore compares the two production
    # execution paths for the identical command stream.
    run_fast_parity(
        start_seed,
        seeds,
        events,
        max_ticks,
        max_entities=max_entities,
    )


def _enabled_units(
    battle: BattleState,
    *,
    include_reachable_children: bool = False,
) -> list[str]:
    return list(
        _runtime_unit_specs(
            battle,
            include_reachable_children=include_reachable_children,
        )
    )


def _enabled_spells(battle: BattleState) -> list[str]:
    return [name for name in _enabled_cards(battle) if name in SPELL_REGISTRY]


def _empty_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._refresh_fast_path_caches()
    return battle


def run_pair_matrix(
    ticks: int,
    position_tolerance: float,
    pair_card: str | None = None,
    pair_scenario: str | None = None,
    include_reachable_children: bool = False,
    pair_start: int = 0,
    pair_stop: int | None = None,
) -> None:
    """Exercise every ordered enabled-unit matchup in both engine paths.

    The allied scenario exercises same-team collision and ownership effects.
    The same-bank scenario forces an immediate enemy combat interaction. The
    river scenario separately exercises crossing, bridge selection, and river
    jumps; using only that geometry lets slow ground pairs spend the whole
    audit pathing without ever exchanging a hit.
    """
    template_battle = BattleState()
    specs = _runtime_unit_specs(
        template_battle,
        include_reachable_children=include_reachable_children,
    )
    cards = list(specs)
    if pair_card is not None:
        normalized_pair_card = resolve_card_name(pair_card)
        matching_cards = [
            card
            for card in cards
            if card == pair_card
            or resolve_card_name(card) == normalized_pair_card
        ]
        if len(matching_cards) != 1:
            raise ValueError(f"--pair-card is not an enabled unit: {pair_card}")
        resolved_pair_card = matching_cards[0]
        pairs = [
            (first, second)
            for first in cards
            for second in cards
            if resolved_pair_card in {first, second}
        ]
    else:
        pairs = [(first, second) for first in cards for second in cards]
    pair_count = len(pairs)
    if pair_start < 0 or pair_start > pair_count:
        raise ValueError(
            f"--pair-start must be between 0 and {pair_count}, got {pair_start}"
        )
    if pair_stop is not None and (
        pair_stop < pair_start or pair_stop > pair_count
    ):
        raise ValueError(
            f"--pair-stop must be between {pair_start} and {pair_count}, "
            f"got {pair_stop}"
        )
    pairs = pairs[pair_start:pair_stop]
    scenarios = (
        (
            "allied",
            Position(8.5, 12.5),
            Position(9.0, 12.5),
            0,
            0,
        ),
        (
            "same-bank",
            Position(8.5, 12.5),
            Position(9.5, 14.5),
            0,
            1,
        ),
        (
            "river",
            Position(8.5, 14.5),
            Position(9.5, 17.5),
            0,
            1,
        ),
    )
    if pair_scenario is not None:
        scenarios = tuple(
            scenario for scenario in scenarios if scenario[0] == pair_scenario
        )
    total = len(pairs) * len(scenarios)
    checked = 0
    for (
        scenario_name,
        first_position,
        second_position,
        first_player_id,
        second_player_id,
    ) in scenarios:
        for first, second in pairs:
            scalar = _empty_battle(0)
            _spawn_runtime_unit(
                scalar,
                specs[first],
                first_player_id,
                Position(first_position.x, first_position.y),
            )
            _spawn_runtime_unit(
                scalar,
                specs[second],
                second_player_id,
                Position(second_position.x, second_position.y),
            )
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(
                    f"scenario={scenario_name} pair={first}/{second} "
                    f"spawn: {error}"
                )
            for tick in range(ticks):
                scalar.step()
                fast.step()
                context = (
                    f"scenario={scenario_name} pair={first}/{second} "
                    f"tick={tick}"
                )
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
            checked += 1
            if checked % len(cards) == 0:
                print(f"pair matrix: {checked}/{total}")
    print(
        f"pair matrix: {total}/{total} ok "
        f"({len(pairs)} ordered pairs x {len(scenarios)} scenarios; "
        f"pair slice {pair_start}:{pair_stop if pair_stop is not None else pair_count} "
        f"of {pair_count})"
    )


def run_contention_matrix(
    ticks: int,
    *,
    include_reachable_children: bool = False,
    pair_start: int = 0,
    pair_stop: int | None = None,
) -> None:
    """Stress two allied attack groups contending for lethal targets.

    Pair combat alone cannot expose a stale target cache created when an
    earlier combat component kills, cloaks, moves, or reserves a recipient in
    the same frame. This matrix gives every ordered enabled/reachable attacker
    pair two target choices on each serialized attack plane: ground
    characters, airborne characters, and buildings. The nearer recipient is
    deliberately one hitpoint so every successful attack immediately
    exercises the second target and any death/spawn side effects.
    """
    template = BattleState()
    specs = _runtime_unit_specs(
        template,
        include_reachable_children=include_reachable_children,
    )
    cards = list(specs)
    pairs = [(first, second) for first in cards for second in cards]
    pair_count = len(pairs)
    if pair_start < 0 or pair_start > pair_count:
        raise ValueError(
            f"--pair-start must be between 0 and {pair_count}, got {pair_start}"
        )
    if pair_stop is not None and (
        pair_stop < pair_start or pair_stop > pair_count
    ):
        raise ValueError(
            f"--pair-stop must be between {pair_start} and {pair_count}, "
            f"got {pair_stop}"
        )
    pairs = pairs[pair_start:pair_stop]
    target_scenarios = (
        ("ground", specs["Knight"]),
        ("air", specs["LavaPups"]),
        ("building", specs["Cannon"]),
    )
    total = len(pairs) * len(target_scenarios)
    checked = 0

    for first, second in pairs:
        for scenario_name, target_spec in target_scenarios:
            scalar = _empty_battle(0)
            _spawn_runtime_unit(
                scalar,
                specs[first],
                0,
                Position(8.5, 10.0),
            )
            _spawn_runtime_unit(
                scalar,
                specs[second],
                0,
                Position(9.5, 10.0),
            )
            _spawn_runtime_unit(
                scalar,
                target_spec,
                1,
                Position(9.0, 13.0),
            )
            first_target_ids = set(scalar.entities)
            _spawn_runtime_unit(
                scalar,
                target_spec,
                1,
                Position(10.5, 13.0),
            )
            first_target = next(
                entity
                for entity in scalar.entities.values()
                if entity.player_id == 1
                and entity.id in first_target_ids
            )
            first_target.hitpoints = min(first_target.hitpoints, 1.0)

            # Remove deployment timing from this audit dimension so the first
            # frame is a genuine shared-target contention frame for every
            # ordinary attack clock. Card-owned movement and attack states
            # still run through their production components.
            for entity in scalar.entities.values():
                if not isinstance(entity, (Troop, Building)):
                    continue
                entity.deploy_delay_remaining = 0.0
                entity.placement_pending = False
                if entity.player_id == 0:
                    entity.attack_cooldown = 0.0
                else:
                    entity.apply_stun(1000.0)

            scalar._refresh_fast_path_caches()
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(
                    f"contention={scenario_name} attackers={first}/{second} "
                    f"spawn: {error}"
                )
            for tick in range(ticks):
                scalar.step()
                fast.step()
                context = (
                    f"contention={scenario_name} attackers={first}/{second} "
                    f"tick={tick}"
                )
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
            checked += 1
            if checked % (len(cards) * len(target_scenarios)) == 0:
                print(f"contention matrix: {checked}/{total}")

    print(
        f"contention matrix: {total}/{total} ok "
        f"({len(pairs)} ordered attacker pairs x "
        f"{len(target_scenarios)} target planes; pair slice "
        f"{pair_start}:{pair_stop if pair_stop is not None else pair_count} "
        f"of {pair_count})"
    )


def run_spell_matrix(
    ticks: int,
    position_tolerance: float,
    include_reachable_children: bool = False,
) -> None:
    """Exercise every enabled spell/unit interaction in both engine paths."""
    battle = BattleState()
    spells = _enabled_spells(battle)
    specs = _runtime_unit_specs(
        battle,
        include_reachable_children=include_reachable_children,
    )
    units = list(specs)
    total = len(spells) * len(units)
    checked = 0
    for spell_name in spells:
        for unit_name in units:
            scalar = _empty_battle(0)
            unit_position = Position(8.5, 14.5)
            _spawn_runtime_unit(
                scalar,
                specs[unit_name],
                1,
                unit_position,
            )
            _spawn(scalar, spell_name, 0, unit_position)
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()
            for tick in range(ticks):
                scalar.step()
                fast.step()
                context = f"spell={spell_name}/{unit_name} tick={tick}"
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
            checked += 1
            if checked % len(units) == 0:
                print(f"spell matrix: {checked}/{total}")
    print(
        f"spell matrix: {total}/{total} ok "
        f"({len(spells)} spells x {len(units)} units)"
    )


def run_spell_crowd_matrix(
    ticks: int,
    include_reachable_children: bool = False,
) -> None:
    """Exercise every enabled spell against two copies of every unit."""
    template_battle = BattleState()
    spells = _enabled_spells(template_battle)
    specs = _runtime_unit_specs(
        template_battle,
        include_reachable_children=include_reachable_children,
    )
    total = len(spells) * len(specs)
    checked = 0
    for spell_name in spells:
        for target_label, target_spec in specs.items():
            scalar = _empty_battle(0)
            target_position = Position(9.0, 14.0)
            _spawn_runtime_unit(
                scalar,
                target_spec,
                1,
                Position(8.9, 14.0),
            )
            _spawn_runtime_unit(
                scalar,
                target_spec,
                1,
                Position(9.1, 14.0),
            )
            _spawn(scalar, spell_name, 0, target_position)
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()
            for tick in range(ticks):
                scalar.step()
                fast.step()
                context = (
                    f"spell-crowd spell={spell_name} "
                    f"target={target_label} tick={tick}"
                )
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
            checked += 1
            if checked % len(specs) == 0:
                print(f"spell crowd matrix: {checked}/{total}")
    print(
        f"spell crowd matrix: {total}/{total} ok "
        f"({len(spells)} spells x two copies of {len(specs)} units)"
    )


def run_allied_spell_matrix(
    ticks: int,
    include_reachable_children: bool = False,
    spell_start: int = 0,
    spell_stop: int | None = None,
) -> None:
    """Prove enabled spells cannot damage or debuff friendly combat units.

    The ordinary spell matrices cover enemy recipients. This complementary
    pass casts every spell directly on every enabled/reachable allied unit and
    compares that unit's defensive state with an otherwise-identical control
    battle. Spawn spells may still create friendly characters and collide
    with the unit; only offensive damage, shields, status, and knockback are
    required to remain identical.
    """
    template = BattleState()
    spells = _enabled_spells(template)
    specs = _runtime_unit_specs(
        template,
        include_reachable_children=include_reachable_children,
    )
    cases = [
        (spell_name, target_label, target_spec)
        for spell_name in spells
        for target_label, target_spec in specs.items()
    ]
    case_count = len(cases)
    if spell_start < 0 or spell_start > case_count:
        raise ValueError(
            f"--spell-start must be between 0 and {case_count}, "
            f"got {spell_start}"
        )
    if spell_stop is not None and (
        spell_stop < spell_start or spell_stop > case_count
    ):
        raise ValueError(
            f"--spell-stop must be between {spell_start} and {case_count}, "
            f"got {spell_stop}"
        )
    cases = cases[spell_start:spell_stop]
    total = len(cases)
    checked = 0

    for spell_name, target_label, target_spec in cases:
        scalar = _empty_battle(0)
        target_position = Position(9.0, 14.0)
        before_ids = set(scalar.entities)
        _spawn_runtime_unit(
            scalar,
            target_spec,
            0,
            target_position,
        )
        protected_ids = tuple(
            entity_id
            for entity_id in scalar.entities
            if entity_id not in before_ids
        )
        control = copy.deepcopy(scalar)
        _spawn(scalar, spell_name, 0, target_position)
        fast = copy.deepcopy(scalar)
        fast.fast_path = True
        fast._refresh_fast_path_caches()

        for tick in range(ticks):
            scalar.step()
            fast.step()
            control.step()
            context = (
                f"allied-spell={spell_name}/{target_label} tick={tick}"
            )
            _activate_ready_champion_abilities_same_side(
                scalar,
                fast,
                context,
            )
            _assert_invariants(scalar, context)
            _assert_invariants(fast, f"{context} fast")
            _assert_invariants(control, f"{context} control")
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(f"{context}: {error}")
            for entity_id in protected_ids:
                actual = scalar.entities.get(entity_id)
                expected = control.entities.get(entity_id)
                if actual is None or expected is None:
                    if actual is not expected:
                        raise AssertionError(
                            f"{context}: protected allied entity "
                            f"{entity_id} lifetime differs"
                        )
                    continue
                actual_state = _defensive_entity_state(actual)
                expected_state = _defensive_entity_state(expected)
                if actual_state != expected_state:
                    raise AssertionError(
                        f"{context}: protected allied entity {entity_id} "
                        f"changed: actual={actual_state}; "
                        f"control={expected_state}"
                    )
        checked += 1
        if checked % len(specs) == 0:
            print(f"allied spell matrix: {checked}/{total}")

    print(
        f"allied spell matrix: {total}/{total} ok "
        f"({len(cases)} spell/unit cases; case slice "
        f"{spell_start}:"
        f"{spell_stop if spell_stop is not None else case_count} "
        f"of {case_count})"
    )


def run_allied_attack_matrix(
    ticks: int,
    *,
    include_reachable_children: bool = False,
    pair_start: int = 0,
    pair_stop: int | None = None,
) -> None:
    """Prove every enabled attack family rejects friendly bystanders.

    Each attacker/protected-unit pair is exercised against ground, airborne,
    and building primaries. The protected ally is placed inside the primary's
    impact footprint while tiny collision radii prevent the deliberately
    overlapping probe geometry from drifting apart. Its defensive state is
    compared with a control battle that contains the same protected ally and
    primary but no attacker.
    """
    template = BattleState()
    specs = _runtime_unit_specs(
        template,
        include_reachable_children=include_reachable_children,
    )
    cards = list(specs)
    pairs = [
        (attacker_label, protected_label)
        for attacker_label in cards
        for protected_label in cards
    ]
    pair_count = len(pairs)
    if pair_start < 0 or pair_start > pair_count:
        raise ValueError(
            f"--pair-start must be between 0 and {pair_count}, got {pair_start}"
        )
    if pair_stop is not None and (
        pair_stop < pair_start or pair_stop > pair_count
    ):
        raise ValueError(
            f"--pair-stop must be between {pair_start} and {pair_count}, "
            f"got {pair_stop}"
        )
    pairs = pairs[pair_start:pair_stop]
    primary_scenarios = (
        ("ground", specs["Knight"]),
        ("air", specs["LavaPups"]),
        ("building", specs["Cannon"]),
    )
    total = len(pairs) * len(primary_scenarios)
    checked = 0

    for attacker_label, protected_label in pairs:
        for scenario_name, primary_spec in primary_scenarios:
            scalar = _empty_battle(0)
            _spawn_runtime_unit(
                scalar,
                specs[attacker_label],
                0,
                Position(9.0, 11.75),
            )
            attacker_owned_ids = tuple(scalar.entities)
            attacker_ids = tuple(
                entity_id
                for entity_id, entity in scalar.entities.items()
                if isinstance(entity, (Troop, Building))
            )
            before_protected_ids = set(scalar.entities)
            _spawn_runtime_unit(
                scalar,
                specs[protected_label],
                0,
                Position(9.01, 12.0),
            )
            protected_ids = tuple(
                entity_id
                for entity_id, entity in scalar.entities.items()
                if (
                    entity_id not in before_protected_ids
                    and isinstance(entity, (Troop, Building))
                )
            )
            before_primary_ids = set(scalar.entities)
            _spawn_runtime_unit(
                scalar,
                primary_spec,
                1,
                Position(9.0, 12.0),
            )
            primary_ids = tuple(
                entity_id
                for entity_id in scalar.entities
                if entity_id not in before_primary_ids
            )

            # Isolate allegiance from body pressure while keeping every
            # target inside even the smallest serialized impact footprint.
            for index, entity_id in enumerate(attacker_ids):
                attacker = scalar.entities[entity_id]
                attacker.card_stats = copy.deepcopy(attacker.card_stats)
                attacker.card_stats.collision_radius = 0.001
                attacker.position = Position(8.99 - index * 0.003, 11.75)
                attacker.deploy_delay_remaining = 0.0
                attacker.placement_pending = False
                attacker.attack_cooldown = 0.0
                attacker.speed = 0.0
                attacker.original_speed = 0.0
            for entity_id in protected_ids + primary_ids:
                entity = scalar.entities[entity_id]
                entity.card_stats = copy.deepcopy(entity.card_stats)
                entity.card_stats.collision_radius = 0.001
                entity.deploy_delay_remaining = 0.0
                entity.placement_pending = False
                entity.attack_cooldown = 999.0
                entity.speed = 0.0
                entity.original_speed = 0.0
            for entity_id in protected_ids:
                scalar.entities[entity_id].position = Position(9.01, 12.0)
            for entity_id in primary_ids:
                primary = scalar.entities[entity_id]
                primary.position = Position(9.0, 12.0)
                primary.max_hitpoints = max(primary.max_hitpoints, 1_000_000.0)
                primary.hitpoints = primary.max_hitpoints
                # The primary exists only as an enemy recipient. Spawn-time
                # stuns can legitimately reset an artificial long combat
                # cooldown, so zero its outgoing damage as well; otherwise a
                # control with the attacker removed can redirect the primary
                # onto the protected ally and masquerade as friendly fire.
                primary.damage = 0.0

            scalar._refresh_fast_path_caches()
            control = copy.deepcopy(scalar)
            for entity_id in attacker_owned_ids:
                control.entities.pop(entity_id, None)
            control._refresh_fast_path_caches()
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()

            for tick in range(ticks):
                scalar.step()
                fast.step()
                control.step()
                context = (
                    f"allied-attack={attacker_label}/{protected_label} "
                    f"primary={scenario_name} tick={tick}"
                )
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                _assert_invariants(control, f"{context} control")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
                for entity_id in protected_ids:
                    actual = scalar.entities.get(entity_id)
                    expected = control.entities.get(entity_id)
                    if actual is None or expected is None:
                        if actual is not expected:
                            raise AssertionError(
                                f"{context}: protected allied entity "
                                f"{entity_id} lifetime differs"
                            )
                        continue
                    actual_state = _defensive_entity_state(actual)
                    expected_state = _defensive_entity_state(expected)
                    if actual_state != expected_state:
                        raise AssertionError(
                            f"{context}: friendly attack affected allied "
                            f"entity {entity_id}: actual={actual_state}; "
                            f"control={expected_state}"
                        )
            checked += 1
            if checked % (len(cards) * len(primary_scenarios)) == 0:
                print(f"allied attack matrix: {checked}/{total}")

    print(
        f"allied attack matrix: {total}/{total} ok "
        f"({len(pairs)} attacker/ally pairs x "
        f"{len(primary_scenarios)} primary planes; pair slice "
        f"{pair_start}:{pair_stop if pair_stop is not None else pair_count} "
        f"of {pair_count})"
    )


def run_allied_death_payload_matrix(
    ticks: int,
    *,
    include_reachable_children: bool = False,
    pair_start: int = 0,
    pair_stop: int | None = None,
) -> None:
    """Prove enabled death payloads affect enemies without friendly fire."""
    template = BattleState()
    specs = _runtime_unit_specs(
        template,
        include_reachable_children=include_reachable_children,
    )
    death_sources: list[tuple[str, RuntimeUnitSpec]] = []
    for label, spec in specs.items():
        stats = (
            template.card_loader.get_card(spec.deck_card)
            if spec.deck_card is not None
            else _child_card_stats(spec)
        )
        if stats is None:
            continue
        character = stats._raw_entry.get("summonCharacterData") or {}
        if any(
            character.get(field)
            for field in (
                "deathDamage",
                "deathSpawnCharacterData",
                "deathAreaEffectData",
            )
        ):
            death_sources.append((label, spec))

    cases = [
        (source_label, source_spec, protected_label, protected_spec)
        for source_label, source_spec in death_sources
        for protected_label, protected_spec in specs.items()
    ]
    case_count = len(cases)
    if pair_start < 0 or pair_start > case_count:
        raise ValueError(
            f"--pair-start must be between 0 and {case_count}, got {pair_start}"
        )
    if pair_stop is not None and (
        pair_stop < pair_start or pair_stop > case_count
    ):
        raise ValueError(
            f"--pair-stop must be between {pair_start} and {case_count}, "
            f"got {pair_stop}"
        )
    cases = cases[pair_start:pair_stop]
    total = len(cases)
    checked = 0
    for (
        source_label,
        source_spec,
        protected_label,
        protected_spec,
    ) in cases:
            scalar = _empty_battle(0)
            _spawn_runtime_unit(
                scalar,
                source_spec,
                0,
                Position(9.0, 12.0),
            )
            source_owned_ids = tuple(scalar.entities)
            source_ids = tuple(
                entity_id
                for entity_id, entity in scalar.entities.items()
                if isinstance(entity, (Troop, Building))
            )
            before_protected_ids = set(scalar.entities)
            _spawn_runtime_unit(
                scalar,
                protected_spec,
                0,
                Position(9.01, 12.0),
            )
            protected_ids = tuple(
                entity_id
                for entity_id, entity in scalar.entities.items()
                if (
                    entity_id not in before_protected_ids
                    and isinstance(entity, (Troop, Building))
                )
            )
            before_primary_ids = set(scalar.entities)
            _spawn_runtime_unit(
                scalar,
                specs["Knight"],
                1,
                Position(9.0, 12.0),
            )
            primary_ids = tuple(
                entity_id
                for entity_id in scalar.entities
                if entity_id not in before_primary_ids
            )

            for entity_id in protected_ids + primary_ids:
                entity = scalar.entities[entity_id]
                entity.card_stats = copy.deepcopy(entity.card_stats)
                entity.card_stats.collision_radius = 0.001
                entity.deploy_delay_remaining = 0.0
                entity.placement_pending = False
                entity.attack_cooldown = 999.0
                entity.speed = 0.0
                entity.original_speed = 0.0
            for entity_id in protected_ids:
                scalar.entities[entity_id].position = Position(9.01, 12.0)
            for entity_id in primary_ids:
                primary = scalar.entities[entity_id]
                primary.position = Position(9.0, 12.0)
                primary.max_hitpoints = max(primary.max_hitpoints, 1_000_000.0)
                primary.hitpoints = primary.max_hitpoints
                # This enemy exists only to prove the death payload's hostile
                # branch. Target acquisition can replace the artificial
                # cooldown with native LoadTime; zero damage prevents a
                # source's spawned descendants from changing which protected
                # ally the control Knight eventually attacks.
                primary.damage = 0.0

            scalar._refresh_fast_path_caches()
            control = copy.deepcopy(scalar)
            for entity_id in source_owned_ids:
                control.entities.pop(entity_id, None)
            control._refresh_fast_path_caches()
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()

            for battle in (scalar, fast):
                for entity_id in source_ids:
                    source = battle.entities[entity_id]
                    source.take_damage(source.hitpoints)

            context = (
                f"allied-death={source_label}/{protected_label} immediate"
            )
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(f"{context}: {error}")
            for tick in range(ticks):
                scalar.step()
                fast.step()
                control.step()
                context = (
                    f"allied-death={source_label}/{protected_label} "
                    f"tick={tick}"
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                _assert_invariants(control, f"{context} control")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
                for entity_id in protected_ids:
                    actual = scalar.entities.get(entity_id)
                    expected = control.entities.get(entity_id)
                    if actual is None or expected is None:
                        if actual is not expected:
                            raise AssertionError(
                                f"{context}: protected allied entity "
                                f"{entity_id} lifetime differs"
                            )
                        continue
                    actual_state = _defensive_entity_state(actual)
                    expected_state = _defensive_entity_state(expected)
                    if actual_state != expected_state:
                        raise AssertionError(
                            f"{context}: friendly death payload affected "
                            f"allied entity {entity_id}: "
                            f"actual={actual_state}; control={expected_state}"
                        )
            checked += 1
            if checked % len(specs) == 0:
                print(f"allied death matrix: {checked}/{total}")

    print(
        f"allied death matrix: {total}/{total} ok "
        f"({len(cases)} death-source/allied-unit cases; case slice "
        f"{pair_start}:{pair_stop if pair_stop is not None else case_count} "
        f"of {case_count})"
    )


def run_tower_matrix(
    ticks: int,
    include_reachable_children: bool = False,
) -> None:
    """Exercise every enabled unit against the standard Crown Towers.

    The troop pair matrix deliberately removes arena towers so it can isolate
    unit interactions. This complementary pass keeps the full tower layout
    and runs each unit from both player orientations, covering tower targeting,
    activation, crown-damage rules, lane fallback, and match termination in
    both production engine paths.
    """
    template_battle = BattleState()
    specs = _runtime_unit_specs(
        template_battle,
        include_reachable_children=include_reachable_children,
    )
    total = len(specs) * 2
    checked = 0
    for player_id in (0, 1):
        for label, spec in specs.items():
            scalar = BattleState()
            spawn_position = Position(
                3.5,
                20.0 if player_id == 0 else 12.0,
            )
            _spawn_runtime_unit(
                scalar,
                spec,
                player_id,
                spawn_position,
            )
            fast = copy.deepcopy(scalar)
            fast.fast_path = True
            fast._refresh_fast_path_caches()
            for tick in range(ticks):
                scalar.step()
                fast.step()
                context = (
                    f"tower player={player_id} unit={label} tick={tick}"
                )
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    context,
                )
                _assert_invariants(scalar, context)
                _assert_invariants(fast, f"{context} fast")
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(f"{context}: {error}")
                if scalar.game_over:
                    break
            checked += 1
            if checked % len(specs) == 0:
                print(f"tower matrix: {checked}/{total}")
    print(
        f"tower matrix: {total}/{total} ok "
        f"({len(specs)} units x 2 orientations)"
    )


def run_crowd_matrix(
    attacker_card: str,
    ticks: int,
    include_reachable_children: bool = False,
) -> None:
    """Exercise one enabled attacker against two copies of every unit.

    Pair scenarios cannot expose recipient-snapshot bugs in splash, chained,
    piercing, or serialized multi-target attacks. Two nearby deployments also
    expand naturally into larger swarms, so this pass reaches the same
    production object ordering used by crowded battles without encoding any
    card-specific expected outcome.
    """
    template_battle = _empty_battle(0)
    specs = _runtime_unit_specs(
        template_battle,
        include_reachable_children=include_reachable_children,
    )
    normalized_attacker = resolve_card_name(attacker_card)
    matching_attackers = [
        label
        for label in specs
        if label == attacker_card
        or resolve_card_name(label) == normalized_attacker
    ]
    if len(matching_attackers) != 1:
        raise ValueError(
            f"--crowd-card must resolve to one enabled unit: {attacker_card}"
        )
    attacker_label = matching_attackers[0]
    total = len(specs)
    for checked, (target_label, target_spec) in enumerate(
        specs.items(),
        start=1,
    ):
        scalar = _empty_battle(0)
        _spawn_runtime_unit(
            scalar,
            specs[attacker_label],
            0,
            Position(9.0, 10.0),
        )
        _spawn_runtime_unit(
            scalar,
            target_spec,
            1,
            Position(8.9, 14.0),
        )
        _spawn_runtime_unit(
            scalar,
            target_spec,
            1,
            Position(9.1, 14.0),
        )
        fast = copy.deepcopy(scalar)
        fast.fast_path = True
        fast._refresh_fast_path_caches()
        for tick in range(ticks):
            scalar.step()
            fast.step()
            context = (
                f"crowd attacker={attacker_label} "
                f"target={target_label} tick={tick}"
            )
            _activate_ready_champion_abilities_same_side(
                scalar,
                fast,
                context,
            )
            _assert_invariants(scalar, context)
            _assert_invariants(fast, f"{context} fast")
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(f"{context}: {error}")
        if checked % len(specs) == 0:
            print(f"crowd matrix: {checked}/{total}")
    print(
        f"crowd matrix: {total}/{total} ok "
        f"({attacker_label} x two copies of {len(specs)} units)"
    )


def run_fast_parity(
    start_seed: int,
    seeds: int,
    events: int,
    max_ticks: int,
    *,
    max_entities: int = 256,
) -> None:
    """Stress identical command streams without unbounded swarm accumulation."""
    if max_entities <= 0:
        raise ValueError("--max-entities must be positive")
    cards = _enabled_cards(BattleState())
    for seed in range(start_seed, start_seed + seeds):
        action_rng = random.Random(seed)
        scalar = BattleState(rng=random.Random(seed + 1000))
        fast = copy.deepcopy(scalar)
        fast.fast_path = True
        fast._refresh_fast_path_caches()
        density_resets = 0
        for event in range(events):
            density_limit_reached = (
                len(scalar.entities) >= max_entities
                or len(fast.entities) >= max_entities
            )
            if scalar.game_over or fast.game_over or density_limit_reached:
                if scalar.game_over != fast.game_over:
                    raise AssertionError(
                        f"fast seed={seed} event={event}: terminal state differs"
                    )
                if density_limit_reached:
                    error = _compare_scalar_fast(scalar, fast)
                    if error is not None:
                        raise AssertionError(
                            f"fast seed={seed} event={event} density reset: "
                            f"{error}"
                        )
                    density_resets += 1
                reset_seed = (
                    seed * events
                    + event
                    + density_resets * 1_000_003
                    + 1000
                )
                scalar = BattleState(rng=random.Random(reset_seed))
                fast = copy.deepcopy(scalar)
                fast.fast_path = True
                fast._refresh_fast_path_caches()
            name = action_rng.choice(cards)
            player_id = action_rng.randrange(2)
            position = Position(
                action_rng.randint(0, 17) + 0.5,
                action_rng.randint(0, 31) + 0.5,
            )
            _spawn(scalar, name, player_id, position)
            _spawn(fast, name, player_id, position)
            _assert_invariants(scalar, f"fast seed={seed} event={event} spawn")
            _assert_invariants(fast, f"fast seed={seed} event={event} fast spawn")
            error = _compare_scalar_fast(scalar, fast)
            if error is not None:
                raise AssertionError(
                    f"fast seed={seed} event={event} card={name} spawn: {error}"
                )
            for tick in range(action_rng.randint(1, max_ticks)):
                scalar.step()
                fast.step()
                _activate_ready_champion_abilities_same_side(
                    scalar,
                    fast,
                    f"fast seed={seed} event={event} tick={tick}",
                )
                _assert_invariants(scalar, f"fast seed={seed} event={event} tick={tick}")
                _assert_invariants(
                    fast,
                    f"fast seed={seed} event={event} fast tick={tick}",
                )
                error = _compare_scalar_fast(scalar, fast)
                if error is not None:
                    raise AssertionError(
                        f"fast seed={seed} event={event} tick={tick} "
                        f"card={name}: {error}"
                    )
        print(
            f"fast seed {seed}: ok "
            f"({density_resets} density resets)"
        )


def _assert_observation_parity(
    scalar: SelfPlayBattleEnv,
    fast: SelfPlayBattleEnv,
    context: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Compare both player-facing RL states and return their legal masks."""
    masks: list[np.ndarray] = []
    for player_id in (0, 1):
        scalar_observation = scalar.get_observation(player_id)
        fast_observation = fast.get_observation(player_id)
        if not np.array_equal(
            scalar_observation.board,
            fast_observation.board,
        ):
            difference = np.argwhere(
                scalar_observation.board != fast_observation.board
            )
            raise AssertionError(
                f"{context}: player {player_id} board observation differs "
                f"at {difference[:8].tolist()}"
            )
        if not np.array_equal(
            scalar_observation.hud,
            fast_observation.hud,
        ):
            difference = np.argwhere(
                scalar_observation.hud != fast_observation.hud
            )
            raise AssertionError(
                f"{context}: player {player_id} HUD observation differs "
                f"at {difference[:8].tolist()}"
            )
        if (
            not np.isfinite(scalar_observation.board).all()
            or not np.isfinite(scalar_observation.hud).all()
        ):
            raise AssertionError(
                f"{context}: player {player_id} observation is non-finite"
            )

        scalar_mask = scalar.get_action_mask(player_id)
        fast_mask = fast.get_action_mask(player_id)
        if not np.array_equal(scalar_mask, fast_mask):
            difference = np.flatnonzero(scalar_mask != fast_mask)
            raise AssertionError(
                f"{context}: player {player_id} action mask differs at "
                f"{difference[:16].tolist()}"
            )
        if not bool(scalar_mask[scalar.action_space.no_op_action]):
            raise AssertionError(
                f"{context}: player {player_id} no-op action is illegal"
            )
        masks.append(scalar_mask)
    return masks[0], masks[1]


def _sample_legal_env_action(
    action_rng: random.Random,
    mask: np.ndarray,
    no_op_action: int,
    ability_action: int,
) -> int:
    """Sample legal play while deliberately exercising no-op and abilities."""
    legal = np.flatnonzero(mask)
    if not legal.size:
        raise AssertionError("legal action mask is empty")
    if bool(mask[ability_action]) and action_rng.random() < 0.35:
        return int(ability_action)
    non_noop = legal[legal != no_op_action]
    if not non_noop.size or action_rng.random() < 0.12:
        return int(no_op_action)
    return int(non_noop[action_rng.randrange(len(non_noop))])


def _assert_failed_env_actions_are_joint_conflicts(
    battle_before_actions: BattleState,
    action_space,
    actions: dict[int, int],
    action_success: dict[int, bool],
    context: str,
) -> None:
    """Distinguish a stale mask from a legitimate simultaneous conflict.

    Both players choose from the same pre-command state. In an overlapping
    deployment zone, either command can make the other's placement illegal
    before it is processed. A masked action may fail only when it succeeds in
    isolation and the opponent's accepted command is what invalidates it.
    """
    for player_id, action in actions.items():
        if action_success.get(player_id, False):
            continue

        isolated = copy.deepcopy(battle_before_actions)
        if not action_space.apply_action(isolated, player_id, action):
            raise AssertionError(
                f"{context}: action mask marked player {player_id} "
                f"action {action} legal but it failed in isolation"
            )

        opponent_id = 1 - player_id
        if not action_success.get(opponent_id, False):
            raise AssertionError(
                f"{context}: both pre-state-legal actions failed"
            )
        after_opponent = copy.deepcopy(battle_before_actions)
        if not action_space.apply_action(
            after_opponent,
            opponent_id,
            actions[opponent_id],
        ):
            raise AssertionError(
                f"{context}: reported-successful player {opponent_id} "
                "action failed during conflict replay"
            )
        if action_space.apply_action(after_opponent, player_id, action):
            raise AssertionError(
                f"{context}: action mask marked player {player_id} "
                f"action {action} legal but application failed without a "
                "reproducible joint-action conflict"
            )


def run_env_parity(
    start_seed: int,
    seeds: int,
    decisions: int,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
) -> None:
    """Run legal enabled-deck RL episodes in both production engine paths."""
    for seed in range(start_seed, start_seed + seeds):
        scalar = SelfPlayBattleEnv(
            decision_interval_ticks=decision_interval,
            max_ticks=max_ticks,
            decks_path=REPO_ROOT / "decks.json",
            seed=seed,
            mirror_match=mirror_match,
            canonical_perspective=True,
            engine_fast_path="off",
        )
        fast = SelfPlayBattleEnv(
            decision_interval_ticks=decision_interval,
            max_ticks=max_ticks,
            decks_path=REPO_ROOT / "decks.json",
            seed=seed,
            mirror_match=mirror_match,
            canonical_perspective=True,
            engine_fast_path="on",
        )
        action_rng = random.Random(seed + 2_000_003)
        episode = 0
        episode_seed = seed
        scalar.reset(seed=episode_seed)
        fast.reset(seed=episode_seed)

        for decision in range(decisions):
            assert scalar.battle is not None
            assert fast.battle is not None
            context = (
                f"env seed={seed} episode={episode} decision={decision} "
                f"tick={scalar.battle.tick}"
            )
            _assert_invariants(scalar.battle, context)
            _assert_invariants(fast.battle, f"{context} fast")
            error = _compare_scalar_fast(scalar.battle, fast.battle)
            if error is not None:
                raise AssertionError(f"{context}: {error}")

            mask0, mask1 = _assert_observation_parity(
                scalar,
                fast,
                context,
            )
            actions = {
                0: _sample_legal_env_action(
                    action_rng,
                    mask0,
                    scalar.action_space.no_op_action,
                    scalar.action_space.ability_action,
                ),
                1: _sample_legal_env_action(
                    action_rng,
                    mask1,
                    scalar.action_space.no_op_action,
                    scalar.action_space.ability_action,
                ),
            }

            battle_before_actions = copy.deepcopy(scalar.battle)
            scalar_rewards, scalar_done, scalar_info = scalar.step(actions)
            fast_rewards, fast_done, fast_info = fast.step(actions)
            _assert_failed_env_actions_are_joint_conflicts(
                battle_before_actions,
                scalar.action_space,
                actions,
                scalar_info.action_success,
                context,
            )
            if scalar_rewards != fast_rewards:
                raise AssertionError(
                    f"{context}: rewards differ scalar={scalar_rewards} "
                    f"fast={fast_rewards}"
                )
            if scalar_done != fast_done or scalar_info != fast_info:
                raise AssertionError(
                    f"{context}: step result differs "
                    f"scalar=({scalar_done}, {scalar_info}) "
                    f"fast=({fast_done}, {fast_info})"
                )

            assert scalar.battle is not None
            assert fast.battle is not None
            _assert_invariants(scalar.battle, f"{context} post-step")
            _assert_invariants(fast.battle, f"{context} fast post-step")
            error = _compare_scalar_fast(scalar.battle, fast.battle)
            if error is not None:
                raise AssertionError(f"{context} post-step: {error}")

            if scalar_done:
                episode += 1
                episode_seed = seed + episode * 1_000_003
                scalar.reset(seed=episode_seed)
                fast.reset(seed=episode_seed)
        print(
            f"env seed {seed}: ok "
            f"({decisions} decisions, {episode} complete episodes)"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--events", type=int, default=80)
    parser.add_argument("--max-ticks", type=int, default=30)
    parser.add_argument("--position-tolerance", type=float, default=0.0)
    parser.add_argument("--pair-matrix", action="store_true")
    parser.add_argument("--pair-ticks", type=int, default=240)
    parser.add_argument("--pair-card", type=str)
    parser.add_argument(
        "--pair-start",
        type=int,
        default=0,
        help="zero-based ordered-pair index to start at",
    )
    parser.add_argument(
        "--pair-stop",
        type=int,
        help="exclusive ordered-pair index to stop at",
    )
    parser.add_argument(
        "--pair-scenario",
        choices=["allied", "same-bank", "river"],
    )
    parser.add_argument("--contention-matrix", action="store_true")
    parser.add_argument("--contention-ticks", type=int, default=120)
    parser.add_argument(
        "--include-reachable-children",
        action="store_true",
        help=(
            "include distinct combat children produced by enabled base cards "
            "in pair and spell matrices"
        ),
    )
    parser.add_argument("--spell-matrix", action="store_true")
    parser.add_argument("--spell-ticks", type=int, default=240)
    parser.add_argument(
        "--spell-start",
        type=int,
        default=0,
        help="zero-based spell/unit case index to start at",
    )
    parser.add_argument(
        "--spell-stop",
        type=int,
        help="exclusive spell/unit case index to stop at",
    )
    parser.add_argument("--spell-crowd-matrix", action="store_true")
    parser.add_argument("--allied-spell-matrix", action="store_true")
    parser.add_argument("--allied-attack-matrix", action="store_true")
    parser.add_argument("--allied-attack-ticks", type=int, default=60)
    parser.add_argument("--allied-death-matrix", action="store_true")
    parser.add_argument("--allied-death-ticks", type=int, default=120)
    parser.add_argument("--tower-matrix", action="store_true")
    parser.add_argument("--tower-ticks", type=int, default=480)
    parser.add_argument("--crowd-card", type=str)
    parser.add_argument("--crowd-ticks", type=int, default=240)
    parser.add_argument("--fast-parity", action="store_true")
    parser.add_argument(
        "--max-entities",
        type=int,
        default=256,
        help=(
            "reset randomized stress before live entities grow beyond this "
            "count"
        ),
    )
    parser.add_argument("--env-parity", action="store_true")
    parser.add_argument("--env-decisions", type=int, default=1024)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--env-max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--mirror-match", action="store_true")
    args = parser.parse_args()
    if args.pair_matrix:
        run_pair_matrix(
            args.pair_ticks,
            args.position_tolerance,
            args.pair_card,
            args.pair_scenario,
            args.include_reachable_children,
            args.pair_start,
            args.pair_stop,
        )
        return
    if args.contention_matrix:
        run_contention_matrix(
            args.contention_ticks,
            include_reachable_children=args.include_reachable_children,
            pair_start=args.pair_start,
            pair_stop=args.pair_stop,
        )
        return
    if args.spell_matrix:
        run_spell_matrix(
            args.spell_ticks,
            args.position_tolerance,
            args.include_reachable_children,
        )
        return
    if args.spell_crowd_matrix:
        run_spell_crowd_matrix(
            args.spell_ticks,
            args.include_reachable_children,
        )
        return
    if args.allied_spell_matrix:
        run_allied_spell_matrix(
            args.spell_ticks,
            args.include_reachable_children,
            args.spell_start,
            args.spell_stop,
        )
        return
    if args.allied_attack_matrix:
        run_allied_attack_matrix(
            args.allied_attack_ticks,
            include_reachable_children=args.include_reachable_children,
            pair_start=args.pair_start,
            pair_stop=args.pair_stop,
        )
        return
    if args.allied_death_matrix:
        run_allied_death_payload_matrix(
            args.allied_death_ticks,
            include_reachable_children=args.include_reachable_children,
            pair_start=args.pair_start,
            pair_stop=args.pair_stop,
        )
        return
    if args.tower_matrix:
        run_tower_matrix(
            args.tower_ticks,
            args.include_reachable_children,
        )
        return
    if args.crowd_card is not None:
        run_crowd_matrix(
            args.crowd_card,
            args.crowd_ticks,
            args.include_reachable_children,
        )
        return
    if args.fast_parity:
        run_fast_parity(
            args.start_seed,
            args.seeds,
            args.events,
            args.max_ticks,
            max_entities=args.max_entities,
        )
        return
    if args.env_parity:
        run_env_parity(
            args.start_seed,
            args.seeds,
            args.env_decisions,
            args.decision_interval,
            args.env_max_ticks,
            args.mirror_match,
        )
        return
    run_audit(
        args.start_seed,
        args.seeds,
        args.events,
        args.max_ticks,
        args.position_tolerance,
        args.max_entities,
    )


if __name__ == "__main__":
    main()
