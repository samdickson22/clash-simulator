from __future__ import annotations

import random
from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import AreaEffect, Building, Projectile, Troop
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
    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)


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
    assert all(
        field not in vars(projectile)
        for field in (
            "_permanent_homing_disabled_by_temporary",
            "_temporary_homing_remaining_ms",
            "_temporary_homing_target",
        )
    )

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    _assert_exact(control, candidate)
    assert projectile_id not in candidate.entities
    assert runtime.entity_registry[projectile_id] is projectile
    assert not projectile.is_alive
    _assert_consumers_equal(control, candidate)

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)


def test_surviving_point_projectile_preserves_integer_target_position() -> None:
    candidate = BattleState(rng=random.Random(9987), fast_path=True)
    source = _spawn_ready(candidate, "Musketeer", 0, Position(9.0, 12.0))
    source._create_projectile(
        None,
        candidate,
        target_position=Position(9, 30),
    )
    projectile = next(
        entity for entity in candidate.entities.values() if type(entity) is Projectile
    )
    assert type(projectile.target_position.x) is int
    assert type(projectile.target_position.y) is int
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    _assert_exact(control, candidate)
    assert candidate.entities[projectile.id] is projectile
    assert type(projectile.target_position.x) is int
    assert type(projectile.target_position.y) is int
    assert projectile.target_position == Position(9, 30)


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
    assert all(
        field not in vars(projectile)
        for projectile in projectiles
        for field in (
            "_permanent_homing_disabled_by_temporary",
            "_temporary_homing_remaining_ms",
            "_temporary_homing_target",
        )
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


def test_partial_group_cleanup_preserves_aliases_across_on_boundaries() -> None:
    candidate = BattleState(rng=random.Random(9993), fast_path=True)
    stats = candidate.card_loader.get_card("Cannon")
    assert stats is not None
    target = candidate._spawn_entity(
        Building,
        Position(9.5, 16.5),
        1,
        stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    assert SPELL_REGISTRY["Arrows"].cast(candidate, 0, Position(9.5, 16.5))
    projectiles = [
        entity for entity in candidate.entities.values() if type(entity) is Projectile
    ]
    groups: dict[int, tuple[set[int], set[int]]] = {}
    for projectile in projectiles:
        hit_ids = projectile.damage_group_hit_entity_ids
        assert hit_ids is not None
        group = groups.setdefault(id(hit_ids), (hit_ids, set()))
        group[1].add(projectile.id)
    assert len(groups) == 3
    control = candidate.clone()
    control_projectiles = {
        entity.id: entity
        for entity in control.entities.values()
        if type(entity) is Projectile
    }
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON

    assert runtime.advance_ticks(15) == control.step_logic_ticks(15) == 15
    _assert_exact(control, candidate)
    active_ids = set(candidate.entities)
    assert any(
        member_ids & active_ids and member_ids - active_ids
        for _, member_ids in groups.values()
    )

    for expected_set, member_ids in groups.values():
        assert all(
            runtime.entity_registry[entity_id].damage_group_hit_entity_ids
            is expected_set
            for entity_id in member_ids
        )
        control_set = control_projectiles[min(member_ids)].damage_group_hit_entity_ids
        assert expected_set == control_set

    assert runtime.advance_ticks(5) == control.step_logic_ticks(5) == 5
    _assert_exact(control, candidate)
    for expected_set, member_ids in groups.values():
        assert all(
            runtime.entity_registry[entity_id].damage_group_hit_entity_ids
            is expected_set
            for entity_id in member_ids
        )
        control_set = control_projectiles[min(member_ids)].damage_group_hit_entity_ids
        assert expected_set == control_set


def test_staged_registry_rejects_split_active_projectile_group_alias() -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(9994), fast_path=True)
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    projectiles = [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    first = projectiles[0]
    second = next(
        projectile
        for projectile in projectiles[1:]
        if projectile.damage_group_hit_entity_ids
        is first.damage_group_hit_entity_ids
    )
    staged = battle.clone()
    staged.entities[second.id].damage_group_hit_entity_ids = set()

    with pytest.raises(ResidentPublicationError, match="split a shared group set"):
        rust_publication._clone_registry(battle, staged, dict(battle.entities))


def test_last_group_member_cleanup_publishes_shared_tombstone_set_contents() -> None:
    candidate = BattleState(rng=random.Random(9992), fast_path=True)
    stats = candidate.card_loader.get_card("Cannon")
    assert stats is not None
    target = candidate._spawn_entity(
        Building,
        Position(9.5, 16.5),
        1,
        stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    assert SPELL_REGISTRY["Arrows"].cast(candidate, 0, Position(9.5, 16.5))
    projectiles = [
        entity for entity in candidate.entities.values() if type(entity) is Projectile
    ]
    groups: dict[int, tuple[set[int], list[Projectile]]] = {}
    for projectile in projectiles:
        hit_ids = projectile.damage_group_hit_entity_ids
        assert hit_ids is not None
        group = groups.setdefault(id(hit_ids), (hit_ids, []))
        group[1].append(projectile)
    assert len(groups) == 3
    original_sets = {
        min(projectile.id for projectile in members): (
            hit_ids,
            {projectile.id for projectile in members},
        )
        for hit_ids, members in groups.values()
    }
    control = candidate.clone()
    control_projectiles = [
        entity for entity in control.entities.values() if type(entity) is Projectile
    ]
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON

    assert runtime.advance_ticks(25) == control.step_logic_ticks(25) == 25
    _assert_exact(control, candidate)
    assert not any(type(entity) is Projectile for entity in candidate.entities.values())
    assert not any(type(entity) is Projectile for entity in control.entities.values())

    for group_id, (original_set, member_ids) in original_sets.items():
        assert group_id == min(member_ids)
        candidate_members = [
            projectile
            for projectile in projectiles
            if projectile.id in member_ids
        ]
        control_members = [
            projectile
            for projectile in control_projectiles
            if projectile.id in member_ids
        ]
        assert len(candidate_members) == len(control_members) == 10
        assert all(
            runtime.entity_registry[projectile.id] is projectile
            for projectile in candidate_members
        )
        assert all(
            projectile.damage_group_hit_entity_ids is original_set
            for projectile in candidate_members
        )
        control_set = control_members[0].damage_group_hit_entity_ids
        assert control_set == {target.id}
        assert original_set == control_set
        assert all(
            projectile.damage_group_hit_entity_ids is control_set
            for projectile in control_members
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
    def fail_live_commit(*args: object, **kwargs: object) -> None:
        raise ResidentPublicationError("injected structural commit failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    assert tuple(battle.entities.items()) == active_items
    assert tuple(runtime.entity_registry.items()) == registry_items


def test_group_cleanup_commit_failure_restores_position_and_set_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(9983), fast_path=True)
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    target = battle._spawn_entity(
        Building,
        Position(9.5, 16.5),
        1,
        stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    projectiles = [
        entity for entity in battle.entities.values() if type(entity) is Projectile
    ]
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON
    before = canonical_battle_snapshot(battle)
    position_ids = {projectile.id: id(projectile.position) for projectile in projectiles}
    group_sets = {
        projectile.id: projectile.damage_group_hit_entity_ids
        for projectile in projectiles
    }
    group_contents = {
        projectile.id: set(projectile.damage_group_hit_entity_ids or ())
        for projectile in projectiles
    }
    def fail_live_commit(*args: object, **kwargs: object) -> None:
        raise ResidentPublicationError("injected grouped commit failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", fail_live_commit
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(25)

    assert canonical_battle_snapshot(battle) == before
    assert {
        projectile.id: id(projectile.position) for projectile in projectiles
    } == position_ids
    assert all(
        projectile.damage_group_hit_entity_ids is group_sets[projectile.id]
        for projectile in projectiles
    )
    assert {
        projectile.id: set(projectile.damage_group_hit_entity_ids or ())
        for projectile in projectiles
    } == group_contents
