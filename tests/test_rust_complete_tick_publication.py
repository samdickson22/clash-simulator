from __future__ import annotations

import copy
import random
from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, snapshot_bytes
from clasher.entities import AreaEffect, Projectile, Troop
from clasher.mechanics.shared.death_area import (
    DeathAreaEffect,
    spawn_death_area_object,
)
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rust_core import RustBattleMode, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import ResidentPublicationError
from clasher.rust_runtime import ResidentCompleteTickRuntime

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


def _assert_observations_equal(control: BattleState, candidate: BattleState) -> None:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for player_id in (0, 1):
        expected = builder.build(control, player_id)
        actual = builder.build(candidate, player_id)
        for field in fields(expected):
            np.testing.assert_array_equal(
                getattr(actual, field.name),
                getattr(expected, field.name),
            )


def _assert_action_masks_equal(control: BattleState, candidate: BattleState) -> None:
    action_space = DiscreteTileActionSpace()
    for player_id in (0, 1):
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


def test_on_publication_preserves_identity_observation_mask_and_future_tick() -> None:
    candidate = BattleState(rng=random.Random(9961), fast_path=True)
    _spawn_ready(candidate, "Knight", 0, Position(8.0, 12.0))
    _spawn_ready(candidate, "Knight", 1, Position(10.0, 20.0))
    control = candidate.clone()

    entities_identity = id(candidate.entities)
    players_identity = id(candidate.players)
    rng_identity = id(candidate.rng)
    player_identities = [id(player) for player in candidate.players]
    hand_identities = [id(player.hand) for player in candidate.players]
    queue_identities = [id(player.cycle_queue) for player in candidate.players]
    entity_identities = {
        entity_id: id(entity) for entity_id, entity in candidate.entities.items()
    }
    position_identities = {
        entity_id: id(entity.position)
        for entity_id, entity in candidate.entities.items()
    }
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities) == entities_identity
    assert id(candidate.players) == players_identity
    assert id(candidate.rng) == rng_identity
    assert [id(player) for player in candidate.players] == player_identities
    assert [id(player.hand) for player in candidate.players] == hand_identities
    assert [id(player.cycle_queue) for player in candidate.players] == queue_identities
    assert {
        entity_id: id(entity) for entity_id, entity in candidate.entities.items()
    } == entity_identities
    assert {
        entity_id: id(entity.position)
        for entity_id, entity in candidate.entities.items()
    } == position_identities
    _assert_observations_equal(control, candidate)
    _assert_action_masks_equal(control, candidate)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    _assert_observations_equal(control, candidate)
    _assert_action_masks_equal(control, candidate)

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_updates_existing_projectile_and_references_in_place() -> None:
    candidate = BattleState(rng=random.Random(9962), fast_path=True)
    target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 20.0))
    stats = candidate.card_loader.get_card("Knight")
    assert stats is not None
    projectile = Projectile(
        id=candidate.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=42,
        range=5.0,
        sight_range=1.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=1.0,
        source_name="publication-fixture",
        primary_target=target,
        tracks_target=True,
    )
    candidate.entities[projectile.id] = projectile
    candidate.next_entity_id += 1
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    projectile_identity = id(projectile)
    target_identity = id(target)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities[projectile.id]) == projectile_identity
    assert id(candidate.entities[target.id]) == target_identity
    assert projectile.primary_target is target

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_updates_supported_area_effect_in_place() -> None:
    candidate = BattleState(rng=random.Random(9965), fast_path=True)
    source = _spawn_ready(candidate, "IceGolem", 0, Position(5.0, 5.0))
    mechanic = next(
        mechanic
        for mechanic in source.mechanics
        if isinstance(mechanic, DeathAreaEffect)
    )
    area = spawn_death_area_object(
        candidate,
        player_id=0,
        position=Position(5.0, 5.0),
        card_stats=source.card_stats,
        area_data=copy.deepcopy(mechanic.area_data),
    )
    assert isinstance(area, AreaEffect)
    candidate.entities.pop(source.id)
    candidate.invalidate_target_cache()
    candidate.invalidate_alive_buildings_cache()
    candidate._refresh_fast_path_caches(trust_target_cache_dirty=True)
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    area_identity = id(area)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities[area.id]) == area_identity

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_preserves_pending_spell_list_and_survivor_identity() -> None:
    candidate = BattleState(rng=random.Random(9966), fast_path=True)
    candidate._queue_spell_cast("Fireball", 0, Position(9.5, 16.5))
    control = candidate.clone()
    pending_list_identity = id(candidate._pending_spell_casts)
    pending_cast_identity = id(candidate._pending_spell_casts[0])
    pending_position_identity = id(candidate._pending_spell_casts[0].position)
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate._pending_spell_casts) == pending_list_identity
    assert id(candidate._pending_spell_casts[0]) == pending_cast_identity
    assert id(candidate._pending_spell_casts[0].position) == pending_position_identity


def test_on_publication_rejects_birth_before_mutating_python() -> None:
    battle = BattleState(rng=random.Random(9963), fast_path=True)
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    before = python_resident_semantic_snapshot(battle)
    control = battle.clone()
    entity_identities = {
        entity_id: id(entity) for entity_id, entity in battle.entities.items()
    }

    with pytest.raises(RuntimeError, match="publication rejected"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    _assert_observations_equal(control, battle)
    _assert_action_masks_equal(control, battle)
    assert {
        entity_id: id(entity) for entity_id, entity in battle.entities.items()
    } == entity_identities
    assert rust_resident_semantic_snapshot(resident) == before
    assert runtime.resident is resident
    assert runtime.poisoned_reason is not None
    with pytest.raises(RuntimeError, match="runtime is poisoned"):
        runtime.advance_ticks(1)


def test_on_publication_rejects_cleanup_before_mutating_python() -> None:
    battle = BattleState(rng=random.Random(9964), fast_path=True)
    source = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    source.damage = target.hitpoints + 1
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    before = python_resident_semantic_snapshot(battle)
    canonical_before = snapshot_bytes(canonical_battle_snapshot(battle))

    with pytest.raises(RuntimeError, match="publication rejected"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    assert snapshot_bytes(canonical_battle_snapshot(battle)) == canonical_before


def test_on_boundary_rejects_unpublished_causal_python_mutation() -> None:
    battle = BattleState(rng=random.Random(9967), fast_path=True)
    troop = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    resident_before = rust_resident_semantic_snapshot(resident)
    troop.damage += 1

    with pytest.raises(RuntimeError, match="external Python state mutation"):
        runtime.advance_ticks(1)

    assert battle.tick == 0
    assert runtime.resident is resident
    assert rust_resident_semantic_snapshot(resident) == resident_before
    assert runtime.poisoned_reason is None


def test_on_commit_failure_rolls_back_and_poisons_runtime(monkeypatch) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(9968), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(8.0, 12.0))
    _spawn_ready(battle, "Knight", 1, Position(10.0, 20.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    before = python_resident_semantic_snapshot(battle)
    control = battle.clone()
    require_exact = rust_publication._require_exact_projection

    def fail_live_commit(*args, stage: str, **kwargs) -> None:
        if stage == "commit":
            raise ResidentPublicationError("injected live commit failure")
        require_exact(*args, stage=stage, **kwargs)

    monkeypatch.setattr(
        rust_publication,
        "_require_exact_projection",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    _assert_observations_equal(control, battle)
    _assert_action_masks_equal(control, battle)
    assert runtime.resident is resident
    assert rust_resident_semantic_snapshot(resident) == before
    assert runtime.poisoned_reason is not None
    with pytest.raises(RuntimeError, match="runtime is poisoned"):
        runtime.advance_ticks(1)
