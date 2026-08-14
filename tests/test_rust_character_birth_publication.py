from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import fields
from typing import Any

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import _normalize
from clasher.entities import Troop
from clasher.mechanics.shared.death_effects import DeathSpawn
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rust_core import ResidentRustBattle, RustBattleMode, rust_core_available
from clasher.rust_differential import python_resident_semantic_snapshot
from clasher.rust_publication import (
    ResidentPublicationError,
    publish_complete_tick_state,
)
from clasher.rust_runtime import (
    ResidentCompleteTickRuntime,
    _causal_boundary_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn_ready(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _apply_python_joint_actions(
    battle: BattleState,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    successes = {
        player_id: action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
        for player_id in order
    }
    return successes, (order[0], order[1])


def _publish_action_interval(
    battle: BattleState,
    control: BattleState,
    *,
    action: int,
    ticks: int = 0,
) -> tuple[ResidentRustBattle, dict[int, object], dict[int, object]]:
    action_space = DiscreteTileActionSpace()
    actions = (action, action_space.no_op_action)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    control_registry: dict[int, object] = dict(control.entities)
    actual_success, actual_order = candidate.apply_resident_joint_actions(*actions)
    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    if ticks:
        assert candidate.advance_complete_ticks(ticks) == control.step_logic_ticks(
            ticks
        )
    registry: dict[int, object] = dict(battle.entities)
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    return candidate, registry, control_registry


def _assert_consumers_equal(control: BattleState, candidate: BattleState) -> None:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    action_space = DiscreteTileActionSpace()
    for player_id in (0, 1):
        expected = builder.build(control, player_id)
        actual = builder.build(candidate, player_id)
        for field in fields(expected):
            np.testing.assert_array_equal(
                getattr(actual, field.name),
                getattr(expected, field.name),
            )
        for fast_path in (False, True):
            np.testing.assert_array_equal(
                action_space.legal_action_mask(
                    candidate,
                    player_id,
                    fast_path=fast_path,
                ),
                action_space.legal_action_mask(
                    control,
                    player_id,
                    fast_path=fast_path,
                ),
            )


def _static_character_snapshot(entity: Troop) -> object:
    return _normalize(
        {
            "card_stats": entity.card_stats,
            "collision_radius": entity._collision_radius,
            "entity_kind": entity.entity_kind,
            "is_air_unit": entity.is_air_unit,
            "mechanics": entity.mechanics,
            "range": entity.range,
            "sight_range": entity.sight_range,
            "target_type": entity.target_type,
            "unit_mass": entity._unit_mass,
        }
    )


def _tamper_catalog_bundle(
    battle: BattleState,
    mutate: Callable[[dict[str, Any]], None],
) -> Any:
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()),
        data_stat.st_mtime_ns,
        data_stat.st_size,
    )
    payload = json.loads(bundle.payload)
    mutate(payload)
    return rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii"),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
    )


def test_native_catalog_rejects_action_template_fingerprint_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState()

    def mutate(payload: dict[str, object]) -> None:
        cards = payload["cards"]
        knight = next(card for card in cards if card["lookup_name"] == "Knight")
        knight["template_snapshot"]["$object"]["fields"]["damage"] += 1

    bundle = _tamper_catalog_bundle(battle, mutate)
    monkeypatch.setattr(
        rust_core,
        "_resident_card_catalog_bundle",
        lambda *_args: bundle,
    )

    resident = ResidentRustBattle.from_battle(battle)

    assert "template_fingerprint_mismatch" in (
        resident.resident_action_card_capability_reasons("Knight")
    )


def test_native_catalog_rejects_death_template_fingerprint_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState()
    _spawn_ready(battle, "Golem", 0, Position(9.0, 14.0))

    def mutate(payload: dict[str, object]) -> None:
        template = next(
            row
            for row in payload["death_spawn_templates"]
            if row["unit_name"] == "Golemite"
        )
        template["template_snapshot"]["$object"]["fields"]["damage"] += 1

    bundle = _tamper_catalog_bundle(battle, mutate)
    monkeypatch.setattr(
        rust_core,
        "_resident_card_catalog_bundle",
        lambda *_args: bundle,
    )

    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick


@pytest.mark.parametrize(
    ("card_name", "effective_name", "count"),
    [
        ("Knight", "Knight", 1),
        ("Archers", "Archer", 2),
        ("Minions", "Minions", 3),
        ("Skeletons", "Skeletons", 3),
    ],
)
def test_catalog_character_birth_publication_is_exact(
    card_name: str,
    effective_name: str,
    count: int,
) -> None:
    battle = BattleState(rng=random.Random(12_301), fast_path=True)
    battle.players[0].hand = [card_name, None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    first_id = battle.next_entity_id
    action = DiscreteTileActionSpace().encode_action(0, 8, 10, 0)

    _, registry, _ = _publish_action_interval(
        battle,
        control,
        action=action,
    )

    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)
    children = [registry[entity_id] for entity_id in range(first_id, first_id + count)]
    control_children = [
        control.entities[entity_id] for entity_id in range(first_id, first_id + count)
    ]
    assert all(type(child) is Troop for child in children)
    assert [child.card_stats.name for child in children] == [effective_name] * count
    assert all(child.card_stats is children[0].card_stats for child in children)
    assert children[0].card_stats is battle.card_loader.get_card(card_name)
    assert children[0].card_stats is not battle.card_loader.get_card(
        effective_name
    ) or (card_name == effective_name)
    assert all(
        child.position is not control_child.position
        for child, control_child in zip(children, control_children, strict=True)
    )
    assert all(child.battle_state is battle for child in children)
    assert all("_spawn_hook_pending" in vars(child) for child in children)
    assert all("_spawn_hook_fired" not in vars(child) for child in children)
    _assert_consumers_equal(control, battle)

    assert battle.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )


def test_compiled_golem_death_spawn_publishes_exact_identities_and_future_ticks() -> (
    None
):
    battle = BattleState(rng=random.Random(12_302), fast_path=True)
    attacker = _spawn_ready(battle, "Knight", 1, Position(3.0, 13.5))
    bystander = _spawn_ready(battle, "Knight", 1, Position(4.0, 14.0))
    golem = _spawn_ready(battle, "Golem", 0, Position(3.0, 14.0))
    attacker.target_id = golem.id
    attacker._last_combat_target_id = golem.id
    attacker.attack_cooldown = 0.0
    attacker.damage = golem.hitpoints + 1
    bystander.attack_cooldown = 10.0
    bystander.__dict__.pop("_has_attacked_once", None)
    death_spawn = next(
        mechanic for mechanic in golem.mechanics if isinstance(mechanic, DeathSpawn)
    )
    death_spawn.spawn_const_priority = True
    control = battle.clone()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)
    children = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Golemite"
    ]
    assert [child.id for child in children] == [golem.id + 1, golem.id + 2]
    assert runtime.entity_registry[golem.id] is golem
    assert golem.id not in battle.entities
    assert children[0].card_stats is children[1].card_stats
    assert children[0].mechanics is not children[1].mechanics
    assert children[0].position is not children[1].position
    assert [child._native_target_distance_discount_sq_units for child in children] == [
        0,
        80 * 80,
    ]
    assert bystander.__dict__["_has_attacked_once"] is False
    assert bystander._knockback_target is not None
    assert bystander.forced_movement_active
    _assert_consumers_equal(control, battle)

    for _ in range(7):
        assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
        assert python_resident_semantic_snapshot(battle) == (
            python_resident_semantic_snapshot(control)
        )
        assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)


def test_catalog_character_born_and_removed_inside_interval_keeps_tombstones() -> None:
    battle = BattleState(rng=random.Random(12_303), fast_path=True)
    musketeer = _spawn_ready(battle, "Musketeer", 1, Position(9.0, 17.0))
    musketeer.damage = 100_000.0
    musketeer.attack_cooldown = 0.0
    battle.players[0].hand = ["Skeletons", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    first_id = battle.next_entity_id
    action = DiscreteTileActionSpace().encode_action(0, 9, 13, 0)

    _, registry, control_registry = _publish_action_interval(
        battle,
        control,
        action=action,
        ticks=25,
    )

    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    children = [registry[entity_id] for entity_id in range(first_id, first_id + 3)]
    assert sum(child.is_alive for child in children) == 1
    assert sum(child.id in battle.entities for child in children) == 1
    assert all(child.card_stats is children[0].card_stats for child in children)
    assert all(child.battle_state is battle for child in children)
    for child in children:
        assert _static_character_snapshot(child) == _static_character_snapshot(
            control_registry[child.id]
        )
    _assert_consumers_equal(control, battle)


def test_corrupt_character_provenance_fails_before_live_mutation() -> None:
    battle = BattleState(rng=random.Random(12_304))
    battle.players[0].hand = ["Archers", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    actions = (action, action_space.no_op_action)
    _apply_python_joint_actions(control, actions)
    candidate.apply_resident_joint_actions(*actions)
    original_export = candidate.publication_entity_state_bytes
    rows = json.loads(original_export())
    next(row for row in rows if row["character_birth"] is not None)["character_birth"][
        "template_fingerprint"
    ] = "0" * 64
    candidate.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
    before = python_resident_semantic_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(
        ResidentPublicationError, match="legacy publication override rejected"
    ):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert python_resident_semantic_snapshot(battle) == before
    assert tuple(battle.entities.items()) == entities_before
    assert set(registry) == set(battle.entities)


@pytest.mark.parametrize("corruption", ["ordinal", "extra_field"])
def test_character_provenance_shape_fails_closed(corruption: str) -> None:
    battle = BattleState(rng=random.Random(12_306))
    battle.players[0].hand = ["Archers", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    candidate.apply_resident_joint_actions(action, action_space.no_op_action)
    rows = json.loads(candidate.publication_entity_state_bytes())
    provenance = next(
        row for row in rows if row["character_birth"] is not None
    )["character_birth"]
    if corruption == "ordinal":
        provenance["ordinal"] = 17
        expected = "legacy publication override rejected"
    else:
        provenance["unexpected"] = True
        expected = "legacy publication override rejected"
    candidate.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
    before = python_resident_semantic_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(ResidentPublicationError, match=expected):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert python_resident_semantic_snapshot(battle) == before
    assert set(registry) == set(battle.entities)


def test_malformed_publication_json_is_a_typed_publication_error() -> None:
    battle = BattleState(rng=random.Random(12_307))
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    candidate.publication_entity_state_bytes = lambda: b"{not-json"

    with pytest.raises(
        ResidentPublicationError, match="legacy publication override rejected"
    ):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=dict(battle.entities),
        )


def test_death_spawn_provenance_tamper_fails_before_live_mutation() -> None:
    battle = BattleState(rng=random.Random(12_308))
    attacker = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.5))
    golem = _spawn_ready(battle, "Golem", 0, Position(9.0, 14.0))
    attacker.damage = golem.hitpoints + 1
    attacker.attack_cooldown = 0.0
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    rows = json.loads(candidate.publication_entity_state_bytes())
    child = next(row for row in rows if row["character_birth"] is not None)
    child["character_birth"]["unit_data_fingerprint"] = "0" * 64
    candidate.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
    before = python_resident_semantic_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(
        ResidentPublicationError, match="legacy publication override rejected"
    ):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert python_resident_semantic_snapshot(battle) == before
    assert set(registry) == set(battle.entities)


def test_mutated_live_action_wrapper_and_recipe_prototype_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for mutation in ("live_stats", "prototype"):
        battle = BattleState(rng=random.Random(12_309))
        battle.players[0].hand = ["Archers", None, None, None]
        battle.players[0].elixir = battle.players[0].max_elixir
        prior = ResidentRustBattle.from_battle(battle)
        candidate = prior.fork()
        action_space = DiscreteTileActionSpace()
        action = action_space.encode_action(0, 8, 10, 0)
        candidate.apply_resident_joint_actions(action, action_space.no_op_action)
        if mutation == "live_stats":
            stats = battle.card_loader.get_card("Archers")
            assert stats is not None
            stats.damage += 1
        else:
            assert prior._birth_catalog is not None
            prototype = prior._birth_catalog.action_recipes["Archers"].prototype
            monkeypatch.setattr(prototype, "damage", prototype.damage + 1)
        before = python_resident_semantic_snapshot(battle)
        registry: dict[int, object] = dict(battle.entities)

        with pytest.raises(ResidentPublicationError, match="unknown catalog birth recipe"):
            publish_complete_tick_state(
                battle,
                candidate,
                prior_resident=prior,
                entity_registry=registry,
            )

        assert python_resident_semantic_snapshot(battle) == before
        assert set(registry) == set(battle.entities)


def test_character_birth_commit_failure_rolls_back_loader_and_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(12_305))
    battle.players[0].hand = ["Archers", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    actions = (action, action_space.no_op_action)
    _apply_python_joint_actions(control, actions)
    candidate.apply_resident_joint_actions(*actions)
    before = python_resident_semantic_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    cache_before = tuple(battle.card_loader._cards.items())
    registry: dict[int, object] = dict(battle.entities)
    def reject_commit(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise ResidentPublicationError("injected commit failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )

    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert python_resident_semantic_snapshot(battle) == before
    assert tuple(battle.entities.items()) == entities_before
    assert tuple(battle.card_loader._cards.items()) == cache_before
    assert set(registry) == set(battle.entities)
