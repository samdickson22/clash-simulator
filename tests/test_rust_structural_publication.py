from __future__ import annotations

import random
from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Projectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rust_core import RustBattleMode, rust_core_available
from clasher.rust_differential import python_resident_semantic_snapshot
from clasher.rust_publication import ResidentPublicationError
from clasher.rust_runtime import ResidentCompleteTickRuntime
from clasher.spells import SPELL_REGISTRY

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


def _assert_exact(control: BattleState, candidate: BattleState) -> None:
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


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


def test_projectile_birth_survival_impact_cleanup_and_future_python_tick() -> None:
    candidate = BattleState(rng=random.Random(9971), fast_path=True)
    source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 15.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    control = candidate.clone()
    projectile_id = candidate.next_entity_id
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)
    projectile = candidate.entities[projectile_id]
    assert type(projectile) is Projectile
    assert projectile.source_entity is source
    assert projectile.primary_target is target
    assert projectile.card_stats is source.card_stats

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    _assert_exact(control, candidate)
    assert projectile_id not in candidate.entities
    assert runtime.entity_registry[projectile_id] is projectile
    assert not projectile.is_alive
    _assert_consumers_equal(control, candidate)

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)


@pytest.mark.parametrize("dead_reference", ["source", "primary_target"])
def test_surviving_projectile_keeps_inactive_reference_tombstone(
    dead_reference: str,
) -> None:
    candidate = BattleState(rng=random.Random(9972), fast_path=True)
    if dead_reference == "source":
        source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 12.0))
        killer = _spawn_ready(candidate, "Knight", 1, Position(9.0, 13.0))
        target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 15.0))
        killer.target_id = source.id
        killer.damage = source.hitpoints + 1
        dead = source
    else:
        source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 11.0))
        killer = _spawn_ready(candidate, "Knight", 0, Position(9.0, 13.0))
        target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 14.0))
        killer.target_id = target.id
        killer.damage = target.hitpoints + 1
        dead = target
    source.target_id = target.id
    source.attack_cooldown = 0.0
    killer.attack_cooldown = 0.0
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)
    projectile = next(
        entity for entity in candidate.entities.values() if type(entity) is Projectile
    )
    assert dead.id not in candidate.entities
    assert runtime.entity_registry[dead.id] is dead
    assert not dead.is_alive
    if dead_reference == "source":
        assert projectile.source_entity is dead
    else:
        assert projectile.primary_target is dead

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)


def test_on_boundary_guard_detects_external_tombstone_mutation() -> None:
    candidate = BattleState(rng=random.Random(9978), fast_path=True)
    source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 11.0))
    killer = _spawn_ready(candidate, "Knight", 0, Position(9.0, 13.0))
    target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 14.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    killer.target_id = target.id
    killer.attack_cooldown = 0.0
    killer.damage = target.hitpoints + 1
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == 1
    assert target.id not in candidate.entities
    assert runtime.entity_registry[target.id] is target
    target.position.x += 0.25

    with pytest.raises(RuntimeError, match="external Python state mutation"):
        runtime.advance_ticks(1)


def test_projectile_born_and_removed_inside_one_native_interval_is_registered() -> None:
    candidate = BattleState(rng=random.Random(9973), fast_path=True)
    source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 12.5))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    control = candidate.clone()
    projectile_id = candidate.next_entity_id
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)
    assert projectile_id not in candidate.entities
    projectile = runtime.entity_registry[projectile_id]
    assert type(projectile) is Projectile
    assert not projectile.is_alive
    assert projectile.source_entity is source
    assert projectile.primary_target is target


def test_death_area_birth_expiry_and_card_stats_provenance() -> None:
    candidate = BattleState(rng=random.Random(9974), fast_path=True)
    source = _spawn_ready(candidate, "IceGolem", 0, Position(9.0, 12.0))
    killer = _spawn_ready(candidate, "Knight", 1, Position(9.0, 13.0))
    killer.target_id = source.id
    killer.attack_cooldown = 0.0
    killer.damage = source.hitpoints + 1
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)
    area = next(
        entity for entity in candidate.entities.values() if type(entity) is AreaEffect
    )
    assert source.id not in candidate.entities
    assert runtime.entity_registry[source.id] is source
    assert area.card_stats is source.card_stats
    assert area.position is not source.position
    assert area.battle_state is candidate

    assert runtime.advance_ticks(20) == control.step_logic_ticks(20) == 20
    _assert_exact(control, candidate)
    assert area.id not in candidate.entities
    assert runtime.entity_registry[area.id] is area
    assert not area.is_alive
    _assert_consumers_equal(control, candidate)

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)


def test_pending_arrows_births_preserve_spell_recipe_and_group_aliases() -> None:
    candidate = BattleState(rng=random.Random(9976), fast_path=True)
    candidate._queue_spell_cast("Arrows", 0, Position(9.5, 16.5))
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(20) == control.step_logic_ticks(20) == 20
    _assert_exact(control, candidate)
    projectiles = [
        entity
        for entity in candidate.entities.values()
        if type(entity) is Projectile
    ]
    assert len(projectiles) == 30
    assert all(projectile.card_stats is None for projectile in projectiles)
    assert all(projectile.source_name == "Unknown" for projectile in projectiles)
    assert all(projectile.spell_name == "Arrows" for projectile in projectiles)
    assert (
        len(
            {
                id(projectile.damage_group_hit_entity_ids)
                for projectile in projectiles
            }
        )
        == 3
    )
    assert all(
        projectile.position is not projectile.target_position
        and projectile.position is not projectile.launch_position
        and projectile.target_position is not projectile.launch_position
        for projectile in projectiles
    )

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)


def test_group_cleanup_remap_preserves_surviving_shared_set_identities() -> None:
    candidate = BattleState(rng=random.Random(9977), fast_path=True)
    assert SPELL_REGISTRY["Arrows"].cast(candidate, 0, Position(9.5, 16.5))
    initial_projectiles = [
        entity
        for entity in candidate.entities.values()
        if type(entity) is Projectile
    ]
    initial_ids = {projectile.id for projectile in initial_projectiles}
    group_set_id_by_projectile = {
        projectile.id: id(projectile.damage_group_hit_entity_ids)
        for projectile in initial_projectiles
    }
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(15) == control.step_logic_ticks(15) == 15
    _assert_exact(control, candidate)
    survivors = [
        entity
        for entity in candidate.entities.values()
        if type(entity) is Projectile
    ]
    survivor_ids = {projectile.id for projectile in survivors}
    assert survivor_ids
    assert survivor_ids < initial_ids
    assert min(initial_ids) not in survivor_ids
    assert all(
        id(projectile.damage_group_hit_entity_ids)
        == group_set_id_by_projectile[projectile.id]
        for projectile in survivors
    )
    assert all(
        runtime.entity_registry[entity_id].id == entity_id
        for entity_id in initial_ids - survivor_ids
    )


def test_structural_commit_failure_restores_registry_and_active_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(9975), fast_path=True)
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 15.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    before = python_resident_semantic_snapshot(battle)
    active_items = tuple(battle.entities.items())
    registry_items = tuple(runtime.entity_registry.items())
    require_exact = rust_publication._require_exact_projection

    def fail_live_commit(*args: object, stage: str, **kwargs: object) -> None:
        if stage == "commit":
            raise ResidentPublicationError("injected structural commit failure")
        require_exact(*args, stage=stage, **kwargs)

    monkeypatch.setattr(
        rust_publication,
        "_require_exact_projection",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    assert tuple(battle.entities.items()) == active_items
    assert tuple(runtime.entity_registry.items()) == registry_items
