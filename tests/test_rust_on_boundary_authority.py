from __future__ import annotations

import copy
import hashlib
import random
from collections import deque
from typing import Any

import pytest

import clasher.rust_runtime as rust_runtime_module
from clasher.arena import Position, TileGrid
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, snapshot_bytes
from clasher.entities import Projectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_AUTHORITY,
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentPreparedPublication,
    ResidentRustBattle,
    RustBattleMode,
    rust_core_available,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    _build_direct_delta_publication_plan,
    _UndoJournal,
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime
from clasher.spells import SPELL_REGISTRY

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
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


def _runtime_with_troops(seed: int = 71_001) -> tuple[
    BattleState,
    ResidentCompleteTickRuntime,
    Troop,
    Troop,
]:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 16.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.resident is not None
    return battle, runtime, source, target


def _replace_relevant_card_definition(
    battle: BattleState,
    source: Troop,
    _target: Troop,
) -> None:
    name = source.card_stats._card_def.name
    battle.card_loader._card_definitions[name] = copy.copy(
        battle.card_loader._card_definitions[name]
    )


def _toggle_sparse_presence(
    _battle: BattleState,
    source: Troop,
    _target: Troop,
) -> None:
    if "_has_attacked_once" in source.__dict__:
        source.__dict__.pop("_has_attacked_once")
    else:
        source.__dict__["_has_attacked_once"] = False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda battle, source, target: setattr(source, "damage", source.damage + 1),
        lambda battle, source, target: setattr(
            source.position, "x", source.position.x + 0.25
        ),
        lambda battle, source, target: setattr(
            source.card_stats, "damage", source.card_stats.damage + 1
        ),
        lambda battle, source, target: source.card_stats._raw_entry.__setitem__(
            "guardMutation", 1
        ),
        _replace_relevant_card_definition,
        lambda battle, source, target: battle.players[0].hand.__setitem__(
            0, battle.players[0].hand[1]
        ),
        lambda battle, source, target: battle.players[0].cycle_queue.rotate(1),
        lambda battle, source, target: battle.rng.random(),
        lambda battle, source, target: setattr(battle.rng, "gauss_next", -0.0),
        _toggle_sparse_presence,
        lambda battle, source, target: battle.entities.__setitem__(
            source.id, copy.copy(source)
        ),
    ],
    ids=(
        "damage",
        "position",
        "card-stats",
        "raw-card-data",
        "card-definition",
        "hand",
        "cycle-queue",
        "rng",
        "rng-gauss-bits",
        "sparse-presence",
        "active-topology",
    ),
)
def test_direct_guard_rejects_external_python_causal_mutation(
    mutate: Any,
) -> None:
    battle, runtime, source, target = _runtime_with_troops()
    tick_before = battle.tick
    mutate(battle, source, target)

    with pytest.raises(RuntimeError, match="external Python state mutation.*path="):
        runtime.advance_ticks(1)

    assert battle.tick == tick_before
    assert runtime.poisoned_reason is None


def test_direct_guard_rejects_same_id_reference_and_group_alias_replacement() -> None:
    battle, runtime, source, target = _runtime_with_troops(71_002)
    source._create_projectile(target, battle)
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON

    projectile.primary_target = copy.copy(target)
    with pytest.raises(RuntimeError, match="external Python state mutation.*primary_target"):
        runtime.advance_ticks(1)

    battle = BattleState(rng=random.Random(71_003), fast_path=True)
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON
    assert projectile.damage_group_hit_entity_ids is not None
    projectile.damage_group_hit_entity_ids = set(projectile.damage_group_hit_entity_ids)

    with pytest.raises(
        RuntimeError, match="external Python state mutation.*damage_group_hit_entity_ids"
    ):
        runtime.advance_ticks(1)

    battle = BattleState(rng=random.Random(71_012), fast_path=True)
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, Position(9.5, 16.5))
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert projectile.damage_group_hit_entity_ids is not None
    projectile.damage_group_hit_entity_ids.add(999_999)
    with pytest.raises(
        RuntimeError, match="external Python state mutation.*membership"
    ):
        runtime.advance_ticks(1)


def test_direct_guard_rejects_card_definition_raw_value_mutation() -> None:
    _battle, runtime, source, _target = _runtime_with_troops(71_013)
    raw = source.card_stats._card_def.raw
    assert "guardMutation" not in raw
    raw["guardMutation"] = 1
    try:
        with pytest.raises(
            RuntimeError, match=r"external Python state mutation.*_card_def\.raw"
        ):
            runtime.advance_ticks(1)
    finally:
        raw.pop("guardMutation")


def test_direct_guard_rejects_dash_cooldown_raw_value_mutation() -> None:
    battle = BattleState(rng=random.Random(71_016), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    raw = source.card_stats._raw_entry
    character_data = dict(raw.get("summonCharacterData", {}))
    raw["summonCharacterData"] = character_data
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    character_data["dashCooldown"] = 123

    with pytest.raises(
        RuntimeError, match=r"external Python state mutation.*summonCharacterData"
    ):
        runtime.advance_ticks(1)


def test_direct_guard_resolves_alias_hand_to_authoritative_card_wrapper() -> None:
    battle = BattleState(rng=random.Random(71_018), fast_path=True)
    battle.players[0].hand[0] = "Archers"
    stats = battle.card_loader.get_card("Archers")
    assert stats is not None
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    stats.damage += 1

    with pytest.raises(RuntimeError, match=r"card_loader\._cards\['Archers'\]"):
        runtime.advance_ticks(1)


def test_direct_guard_compares_rng_gauss_float_bits() -> None:
    battle = BattleState(rng=random.Random(71_014), fast_path=True)
    battle.rng.gauss_next = 0.0
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    battle.rng.gauss_next = -0.0

    with pytest.raises(RuntimeError, match="external Python state mutation.*rng"):
        runtime.advance_ticks(1)


@pytest.mark.parametrize("geometry", ["river", "blocked", "tower"])
def test_direct_guard_rejects_class_level_arena_geometry_mutation(
    geometry: str,
) -> None:
    battle, runtime, _source, _target = _runtime_with_troops(71_004)
    if geometry == "river":
        original = TileGrid.RIVER_Y1
        TileGrid.RIVER_Y1 = original + 0.25
        restore = lambda: setattr(TileGrid, "RIVER_Y1", original)
    elif geometry == "blocked":
        TileGrid.BLOCKED_TILES.append((8, 8))
        restore = lambda: TileGrid.BLOCKED_TILES.pop()
    else:
        original = TileGrid.LEFT_BRIDGE.x
        TileGrid.LEFT_BRIDGE.x = original + 0.25
        restore = lambda: setattr(TileGrid.LEFT_BRIDGE, "x", original)
    try:
        with pytest.raises(RuntimeError, match="resident geometry"):
            runtime.advance_ticks(1)
    finally:
        restore()
    assert battle.tick == 0


def test_direct_guard_allows_only_known_derived_cache_refreshes() -> None:
    battle, runtime, _source, _target = _runtime_with_troops(71_005)
    action_space = DiscreteTileActionSpace()
    action_space.legal_action_mask(battle, 0, fast_path=True)

    assert runtime.advance_ticks(1) == 1


def test_guard_record_rebuilds_topology_stable_boundary_and_rejects_drift() -> None:
    battle = BattleState(rng=random.Random(71_019), fast_path=True)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    initial_guard = runtime._on_boundary_guard
    assert initial_guard is not None

    assert runtime.advance_ticks(1) == 1
    published_guard = runtime._on_boundary_guard
    assert published_guard is not None
    assert published_guard is not initial_guard
    initial_static = {
        (kind, path, id(owner)): expected
        for kind, path, owner, expected, static in initial_guard.entries
        if static
    }
    assert any(
        initial_static.get((kind, path, id(owner))) is expected
        for kind, path, owner, expected, static in published_guard.entries
        if static
    )

    battle.players[0].elixir -= 0.25
    with pytest.raises(RuntimeError, match=r"external Python state mutation.*elixir"):
        runtime.advance_ticks(1)


def test_guard_record_does_not_recompile_after_initial_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, runtime = _route_runtime(71_023)
    assert runtime.advance_ticks(8) == 8

    def reject_compile(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("full direct guard compiler was called")

    def reject_rebind(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("general direct guard rebind was called")

    monkeypatch.setattr(
        rust_runtime_module,
        "_compile_direct_causal_guard",
        reject_compile,
    )
    guard = runtime._on_boundary_guard
    assert guard is not None
    monkeypatch.setattr(type(guard), "refresh_or_rebind", reject_rebind)
    assert runtime.advance_ticks(8) == 8
    assert runtime.advance_ticks(8) == 8
    battle.players[0].elixir -= 0.25
    with pytest.raises(RuntimeError, match=r"external Python state mutation.*elixir"):
        runtime.advance_ticks(8)


@pytest.mark.parametrize(
    ("mutate", "expected_path"),
    (
        (lambda battle, mover: setattr(battle, "time", battle.time + 0.25), "time"),
        (
            lambda battle, mover: setattr(
                battle.players[0], "elixir", battle.players[0].elixir - 0.25
            ),
            "elixir",
        ),
        (
            lambda battle, mover: setattr(
                battle.entities[1],
                "last_attack_time",
                battle.entities[1].last_attack_time + 0.25,
            ),
            "last_attack_time",
        ),
        (
            lambda battle, mover: setattr(
                mover.position, "x", mover.position.x + 0.25
            ),
            "position",
        ),
        (
            lambda battle, mover: setattr(
                mover, "_pending_movement_x", mover._pending_movement_x + 1
            ),
            "pending_movement_x",
        ),
        (
            lambda battle, mover: setattr(
                mover, "attack_cooldown", mover.attack_cooldown + 0.25
            ),
            "attack_cooldown",
        ),
        (lambda battle, mover: battle.rng.random(), "rng"),
    ),
    ids=("root", "player", "tower", "position", "movement", "combat", "rng"),
)
def test_guard_write_through_updates_changed_owners_and_rejects_later_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Any,
    expected_path: str,
) -> None:
    battle, runtime = _route_runtime(71_030)
    assert runtime.advance_ticks(8) == 8
    previous_guard = runtime._on_boundary_guard
    assert previous_guard is not None
    previous_expected = tuple(entry[3] for entry in previous_guard.entries)

    def reject_rebind(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("general guard rebind was called")

    monkeypatch.setattr(type(previous_guard), "refresh_or_rebind", reject_rebind)
    assert runtime.advance_ticks(8) == 8
    published_guard = runtime._on_boundary_guard
    assert published_guard is not None
    assert published_guard is not previous_guard
    assert all(
        entry[3] is expected
        for entry, expected in zip(
            previous_guard.entries, previous_expected, strict=True
        )
    )
    assert all(
        published_guard.entries[index] is entry
        for index, entry in enumerate(previous_guard.entries)
        if entry[4]
    )
    assert published_guard.first_mismatch() is None
    mover = next(
        entity
        for entity in battle.entities.values()
        if getattr(getattr(entity, "card_stats", None), "name", None) == "Knight"
    )
    mutate(battle, mover)

    with pytest.raises(RuntimeError, match=rf"external Python state mutation.*{expected_path}"):
        runtime._assert_on_boundary_unchanged()


def test_guard_write_through_falls_back_for_sparse_route_and_birth_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = rust_runtime_module._DirectCausalBoundaryGuard.refresh_or_rebind

    def counted_rebind(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        rust_runtime_module._DirectCausalBoundaryGuard,
        "refresh_or_rebind",
        counted_rebind,
    )
    _battle, runtime = _route_runtime(71_031)
    assert runtime.advance_ticks(8) == 8
    route_calls = calls
    assert route_calls >= 1

    battle = BattleState(rng=random.Random(71_032), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 16.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.advance_ticks(1) == 1
    assert calls > route_calls


def test_guard_write_through_updates_rng_after_noop_action_ingress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(71_033), fast_path=True)
    for player in battle.players:
        player.deck = ["Knight"] * 8
        player.hand = ["Knight"] * 4
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
    )
    guard = runtime._on_boundary_guard
    assert guard is not None

    def reject_rebind(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("general guard rebind was called")

    monkeypatch.setattr(type(guard), "refresh_or_rebind", reject_rebind)
    no_op = DiscreteTileActionSpace().no_op_action
    result = runtime.apply_joint_actions_and_advance(no_op, no_op, 0)
    assert result.ticks_advanced == 0
    assert runtime._on_boundary_guard is not guard
    assert runtime._on_boundary_guard is not None
    assert runtime._on_boundary_guard.first_mismatch() is None

    battle.rng.random()
    with pytest.raises(RuntimeError, match=r"external Python state mutation.*rng"):
        runtime._assert_on_boundary_unchanged()


def test_guard_write_through_falls_back_for_pending_cast_identity_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(71_034), fast_path=True)
    for player in battle.players:
        player.deck = ["Fireball"] * 8
        player.hand = ["Fireball"] * 4
        player.cycle_queue = deque(["Fireball"] * 4)
        player.elixir = player.max_elixir
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
    )
    guard = runtime._on_boundary_guard
    assert guard is not None
    calls = 0
    original = type(guard).refresh_or_rebind

    def counted_rebind(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(type(guard), "refresh_or_rebind", counted_rebind)
    action_space = DiscreteTileActionSpace()
    fireball = action_space.encode_action(0, 8, 10, 0)
    result = runtime.apply_joint_actions_and_advance(
        fireball, action_space.no_op_action, 0
    )

    assert result.action_success[0]
    assert len(battle._pending_spell_casts) == 1
    assert calls == 1


def test_guard_write_through_rejects_and_rolls_back_static_receipt_owner() -> None:
    battle, runtime, source, _target = _runtime_with_troops(71_035)
    prior = runtime.resident
    guard = runtime._on_boundary_guard
    assert prior is not None
    assert guard is not None
    candidate = prior.fork()
    delta = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    plan = _build_direct_delta_publication_plan(
        delta,
        battle=battle,
        resident=candidate,
        entity_registry=runtime.entity_registry,
    )
    card_stats = source.card_stats
    static_rows = [
        entry
        for entry in guard.entries
        if entry[2] is card_stats and entry[4]
    ]
    assert static_rows
    static_row_ids = tuple(id(entry) for entry in static_rows)
    original_damage = card_stats.damage
    resident_authority = runtime._on_resident_authority
    python_authority = runtime._on_python_authority
    resident_before = runtime.resident
    undo = _UndoJournal()
    undo.watch_attrs(card_stats)
    card_stats.damage = original_damage + 1

    with pytest.raises(RuntimeError, match="statically guarded owner"):
        runtime._prepare_on_boundary_guard(plan, undo.guard_write_receipt())
    undo.rollback()

    assert source.card_stats is card_stats
    assert card_stats.damage == original_damage
    assert runtime.resident is resident_before
    assert runtime._on_boundary_guard is guard
    assert runtime._on_resident_authority is resident_authority
    assert runtime._on_python_authority is python_authority
    assert tuple(
        id(entry)
        for entry in guard.entries
        if entry[2] is card_stats and entry[4]
    ) == static_row_ids
    assert guard.first_mismatch() is None


def _route_runtime(seed: int) -> tuple[BattleState, ResidentCompleteTickRuntime]:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(7.0, 12.0))
    _spawn_ready(battle, "Knight", 1, Position(11.0, 20.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.active_mode is RustBattleMode.ON
    return battle, runtime


def test_guard_record_rebinds_sparse_presence_after_publication() -> None:
    battle, runtime = _route_runtime(71_020)
    assert "_win_conditions_dirty" not in battle.__dict__

    assert runtime.advance_ticks(8) == 8
    assert "_win_conditions_dirty" in battle.__dict__
    battle.__dict__.pop("_win_conditions_dirty")

    with pytest.raises(
        RuntimeError, match=r"external Python state mutation.*battle.__dict__"
    ):
        runtime.advance_ticks(8)


def test_guard_record_refreshes_route_list_in_place_after_publication() -> None:
    battle, runtime = _route_runtime(71_021)
    assert runtime.advance_ticks(8) == 8
    mover = next(
        entity
        for entity in battle.entities.values()
        if isinstance(getattr(entity, "_native_ground_route_cells", None), list)
    )
    first_route = mover._native_ground_route_cells

    assert runtime.advance_ticks(8) == 8
    published_route = mover._native_ground_route_cells
    assert published_route is first_route
    published_route.append((999, 999))

    with pytest.raises(
        RuntimeError, match=r"external Python state mutation.*route_cells"
    ):
        runtime.advance_ticks(8)


def test_guard_rebind_failure_rolls_back_route_identity_and_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, runtime = _route_runtime(71_024)
    assert runtime.advance_ticks(8) == 8
    mover = next(
        entity
        for entity in battle.entities.values()
        if isinstance(getattr(entity, "_native_ground_route_cells", None), list)
    )
    route = mover._native_ground_route_cells
    route_before = list(route)
    state_before = snapshot_bytes(canonical_battle_snapshot(battle))
    resident_before = runtime.resident

    def fail_guard_update(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected guard update failure")

    guard = runtime._on_boundary_guard
    assert guard is not None
    guard_before = guard
    monkeypatch.setattr(
        type(guard), "write_through_or_rebind", fail_guard_update
    )
    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(8)

    assert runtime.resident is resident_before
    assert runtime._on_boundary_guard is guard_before
    assert mover._native_ground_route_cells is route
    assert route == route_before
    assert snapshot_bytes(canonical_battle_snapshot(battle)) == state_before


def _birth_and_tombstone_runtime(
    seed: int,
) -> tuple[BattleState, ResidentCompleteTickRuntime, Troop]:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 11.0))
    killer = _spawn_ready(battle, "Knight", 0, Position(9.0, 13.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    killer.target_id = target.id
    killer.attack_cooldown = 0.0
    killer.damage = target.hitpoints + 1
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.advance_ticks(1) == 1
    return battle, runtime, target


@pytest.mark.parametrize("mutated_object", ["birth", "tombstone"])
def test_guard_record_binds_native_birth_and_inactive_tombstone(
    mutated_object: str,
) -> None:
    battle, runtime, target = _birth_and_tombstone_runtime(71_022)
    assert target.id not in battle.entities
    assert runtime.entity_registry[target.id] is target
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )

    if mutated_object == "birth":
        projectile.target_position.x += 0.25
        expected_path = "target_position"
    else:
        target.position.x += 0.25
        expected_path = "primary_target"

    with pytest.raises(
        RuntimeError, match=rf"external Python state mutation.*{expected_path}"
    ):
        runtime.advance_ticks(1)


def test_guard_rebinds_survivor_first_seen_through_retired_projectile() -> None:
    battle = BattleState(rng=random.Random(71_025), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 12.5))
    source._create_projectile(target, battle)
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )
    survivors = [
        (entity_id, entity)
        for entity_id, entity in battle.entities.items()
        if entity_id not in {projectile.id, target.id}
    ]
    battle.entities.clear()
    battle.entities.update((*survivors, (projectile.id, projectile), (target.id, target)))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    guard = runtime._on_boundary_guard
    assert guard is not None
    assert any(
        owner is target and "primary_target" in path
        for _kind, path, owner, _expected, _static in guard.entries
    )

    assert runtime.advance_ticks(1) == 1
    assert projectile.id not in battle.entities
    assert target.id in battle.entities
    target.hitpoints -= 1.0

    with pytest.raises(
        RuntimeError,
        match=rf"external Python state mutation.*battle.entities\[{target.id}\].hitpoints",
    ):
        runtime.advance_ticks(1)


@pytest.mark.parametrize("mutation", ["tick", "rng"])
def test_native_authority_rejects_external_resident_mutation(mutation: str) -> None:
    battle, runtime, _source, _target = _runtime_with_troops(71_006)
    resident = runtime.resident
    assert resident is not None
    if mutation == "tick":
        assert resident.advance_complete_tick()
    else:
        resident.rng_random()

    with pytest.raises(RuntimeError, match="external native state mutation"):
        runtime.advance_ticks(1)
    assert battle.tick == 0


def test_native_authority_ignores_instance_method_override() -> None:
    battle, runtime, _source, _target = _runtime_with_troops(71_017)
    resident = runtime.resident
    assert resident is not None
    expected = resident.publication_authority_token()
    resident.publication_authority_token = lambda: expected
    assert resident.advance_complete_tick()

    with pytest.raises(RuntimeError, match="external native state mutation"):
        runtime.advance_ticks(1)
    assert battle.tick == 0


def test_native_noop_and_rejected_calls_do_not_stale_boundary() -> None:
    _battle, runtime, _source, _target = _runtime_with_troops(71_007)
    resident = runtime.resident
    assert resident is not None
    authority = resident.publication_authority_token()

    assert resident.advance_complete_ticks(0) == 0
    with pytest.raises((RuntimeError, ValueError)):
        resident.rng_randrange(0)
    assert resident.publication_authority_token() == authority
    assert runtime.advance_ticks(1) == 1


@pytest.mark.parametrize("root", ["battle", "registry"])
def test_direct_guard_rejects_equal_python_root_replacement(root: str) -> None:
    battle, runtime, _source, _target = _runtime_with_troops(71_016)
    resident = runtime.resident
    assert resident is not None
    native_authority = resident.publication_authority_token()
    if root == "battle":
        runtime.battle = battle.clone()
    else:
        runtime._entity_registry = dict(runtime.entity_registry)

    with pytest.raises(
        RuntimeError, match="external Python state mutation.*Python root authority"
    ):
        runtime.advance_ticks(1)

    assert battle.tick == 0
    assert resident.publication_authority_token() == native_authority
    assert runtime.poisoned_reason is None


def test_raw_and_public_prepared_consumers_are_mutually_single_use() -> None:
    battle = BattleState(rng=random.Random(71_008), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()

    prepared = candidate.prepare_publication(prior)
    assert prepared.parts()["version"] == 1
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)

    prepared = candidate.prepare_publication(prior)
    raw = prepared._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)
    assert type(raw) is dict
    assert type(raw["binding"]) is dict
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()


def test_wrong_raw_authority_does_not_consume_public_projection() -> None:
    battle = BattleState(rng=random.Random(71_009), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    prepared = prior.fork().prepare_publication(prior)

    with pytest.raises(TypeError, match="runtime-owned"):
        prepared._consume_raw_parts(object())
    assert prepared.parts()["version"] == 1


@pytest.mark.parametrize("bad_section", ["root", "binding"])
def test_raw_consumer_rejects_mapping_subclasses_after_burning(
    bad_section: str,
) -> None:
    class MappingSubclass(dict[str, Any]):
        pass

    class FakeNative:
        def parts(self) -> dict[str, Any]:
            binding: dict[str, Any] = {
                "semantic_schema_version": 13,
            }
            if bad_section == "binding":
                binding = MappingSubclass(binding)
            value: dict[str, Any] = {"version": 1, "binding": binding}
            if bad_section == "root":
                value = MappingSubclass(value)
            return value

    prepared = ResidentPreparedPublication(
        FakeNative(),
        None,
        None,
        authority=_PREPARED_PUBLICATION_AUTHORITY,
    )
    with pytest.raises(TypeError, match="not a mapping"):
        prepared._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()


def test_raw_consumer_burns_before_native_crossing_failure() -> None:
    class FakeNative:
        def parts(self) -> dict[str, Any]:
            raise ValueError("injected native crossing failure")

    prepared = ResidentPreparedPublication(
        FakeNative(),
        None,
        None,
        authority=_PREPARED_PUBLICATION_AUTHORITY,
    )
    with pytest.raises(ValueError, match="injected native crossing failure"):
        prepared._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()


@pytest.mark.parametrize(
    "method_name",
    [
        "prepare_publication",
        "character_action_birth_recipe",
        "character_death_spawn_birth_recipe",
        "character_action_card_stats_are_current",
        "spawn_projectile_recipe",
        "character_spawn_projectile_birth_recipe",
    ],
)
def test_publication_rejects_instance_authority_overrides(
    method_name: str,
) -> None:
    battle = BattleState(rng=random.Random(71_010), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    before = canonical_battle_snapshot(battle)
    registry = dict(battle.entities)
    prior_authority = ResidentRustBattle.publication_authority_token(prior)
    candidate_authority = ResidentRustBattle.publication_authority_token(candidate)
    setattr(candidate, method_name, lambda *args, **kwargs: None)

    with pytest.raises(ResidentPublicationError, match="authority override"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=dict(battle.entities),
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(battle.entities.items()) == tuple(registry.items())
    assert ResidentRustBattle.publication_authority_token(prior) == prior_authority
    assert (
        ResidentRustBattle.publication_authority_token(candidate)
        == candidate_authority
    )


def test_publication_rejects_resident_wrapper_subclass_override() -> None:
    class ResidentSubclass(ResidentRustBattle):
        def prepare_publication(self, prior: ResidentRustBattle) -> Any:
            raise AssertionError("subclass authority override executed")

    battle = BattleState(rng=random.Random(71_017), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    subclass = ResidentSubclass(
        candidate._native,
        candidate._birth_catalog,
        candidate._action_card_stats,
    )
    before = tuple(battle.entities.items())

    with pytest.raises(ResidentPublicationError, match="exact resident wrapper types"):
        publish_complete_tick_state(
            battle,
            subclass,
            prior_resident=prior,
            entity_registry=dict(battle.entities),
        )

    assert tuple(battle.entities.items()) == before


def test_on_publication_uses_raw_path_without_recursive_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_core

    battle = BattleState(rng=random.Random(71_011), fast_path=True)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    monkeypatch.setattr(
        rust_core,
        "_freeze_prepared_value",
        lambda _value: (_ for _ in ()).throw(
            AssertionError("recursive prepared freeze used in production ON")
        ),
    )

    assert runtime.advance_ticks(8) == 8


def test_off_shadow_on_fixed_seed_digests_match_with_zero_shadow_mismatches() -> None:
    def fixture() -> BattleState:
        battle = BattleState(rng=random.Random(71_015), fast_path=True)
        _spawn_ready(battle, "Knight", 0, Position(8.0, 12.0))
        _spawn_ready(battle, "Musketeer", 1, Position(10.0, 20.0))
        return battle

    battles = {mode: fixture() for mode in RustBattleMode}
    runtimes = {
        mode: ResidentCompleteTickRuntime(battle, mode)
        for mode, battle in battles.items()
    }
    for mode, runtime in runtimes.items():
        for _ in range(4):
            assert runtime.advance_ticks(8) == 8, mode

    digests = {
        mode: hashlib.sha256(
            snapshot_bytes(canonical_battle_snapshot(battle))
        ).hexdigest()
        for mode, battle in battles.items()
    }
    assert len(set(digests.values())) == 1
    assert runtimes[RustBattleMode.SHADOW].status.shadow_mismatches == 0
