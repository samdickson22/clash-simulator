from __future__ import annotations

import json
import random
from collections import deque

import numpy as np
import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, first_snapshot_difference
from clasher.entities import Building, RollingProjectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentRustBattle,
    RustBattleMode,
    rust_core_available,
)
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    _build_direct_publication_plan,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime
from clasher.spells import SPELL_REGISTRY

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _assert_semantic_parity(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    expected = python_resident_semantic_snapshot(battle)
    actual = rust_resident_semantic_snapshot(resident)
    difference = first_snapshot_difference(expected, actual)
    assert difference is None, difference


def _advance_exact_tick(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _assert_semantic_parity(battle, resident)


def _apply_python_joint_actions(
    battle: BattleState,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    successes: dict[int, bool] = {}
    for player_id in order:
        successes[player_id] = action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
    return successes, (order[0], order[1])


def _prepare_single_card(
    battle: BattleState,
    player_id: int,
    card_name: str,
) -> None:
    for candidate in battle.players:
        if "Balloon" not in candidate.deck:
            continue
        candidate.hand = ["Knight"] * 4
        candidate.deck = ["Knight"] * 8
        candidate.cycle_queue = deque(["Knight"] * 4)
    player = battle.players[player_id]
    player.hand = [card_name] * 4
    player.deck = [card_name] * 8
    player.cycle_queue = deque(player.deck[4:])
    player.elixir = player.max_elixir


def _ready_building(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Building:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    entity = battle._spawn_entity(Building, position, player_id, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def test_rolling_spell_catalog_supports_canonical_names_and_aliases() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    supported = set(resident.resident_supported_action_cards())

    for card_name in ("Log", "The Log", "BarbLog", "BarbarianBarrel"):
        assert resident.resident_action_card_capability_reasons(card_name) == ()
        assert card_name in supported

    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    qualified = {
        card["lookup_name"]
        for card in payload["cards"]
        if card["action_kind"] == "rolling_projectile_spell"
    }
    assert qualified == {"Log", "The Log", "BarbLog", "BarbarianBarrel"}
    bowler = next(card for card in payload["cards"] if card["lookup_name"] == "Bowler")
    assert bowler["action_kind"] != "rolling_projectile_spell"


def test_rolling_catalog_rejects_noninteger_serialized_travel_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    log = next(card for card in payload["cards"] if card["lookup_name"] == "Log")
    log["rolling_projectile_spell"]["travel_speed"] = 200.0
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
        rolling_spawn_recipes=bundle.rolling_spawn_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)

    before = canonical_battle_snapshot(battle)
    with pytest.raises(ValueError, match="expected i64"):
        ResidentRustBattle.from_battle(battle)
    assert canonical_battle_snapshot(battle) == before


@pytest.mark.parametrize(
    ("player_id", "card_name"),
    [(0, "Log"), (0, "BarbarianBarrel"), (1, "Log"), (1, "BarbarianBarrel")],
)
def test_rolling_spell_legal_actions_match_scalar_and_fast_masks(
    player_id: int,
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(96_100 + player_id))
    _prepare_single_card(battle, player_id, card_name)
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()

    native = np.asarray(
        resident.resident_legal_action_ids(player_id),
        dtype=np.int64,
    )
    for fast_path in (False, True):
        mask = action_space.legal_action_mask(
            battle,
            player_id,
            fast_path=fast_path,
        )
        assert np.array_equal(native, np.flatnonzero(mask))


def test_joint_rolling_actions_preserve_queue_order_and_birth_frame() -> None:
    battle = BattleState(rng=random.Random(96_120))
    _prepare_single_card(battle, 0, "Log")
    _prepare_single_card(battle, 1, "BarbarianBarrel")
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )

    expected_success, expected_order = _apply_python_joint_actions(battle, actions)
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    _assert_semantic_parity(battle, resident)
    assert [cast.sequence for cast in battle._pending_spell_casts] == [0, 1]
    assert not any(isinstance(entity, RollingProjectile) for entity in battle.entities.values())

    for _ in range(19):
        _advance_exact_tick(battle, resident)
    assert len(battle._pending_spell_casts) == 2

    _advance_exact_tick(battle, resident)
    rollers = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, RollingProjectile)
    ]
    assert len(rollers) == 2
    assert all(projectile.time_alive == 0.0 for projectile in rollers)
    assert all(projectile.distance_traveled == 0.0 for projectile in rollers)

    _advance_exact_tick(battle, resident)
    assert all(projectile.time_alive == pytest.approx(0.05) for projectile in rollers)
    assert all(projectile.distance_traveled == 0.0 for projectile in rollers)


@pytest.mark.parametrize("card_name", ["Log", "BarbLog"])
@pytest.mark.parametrize("player_id", [0, 1])
def test_rolling_spell_complete_tick_trace_matches_both_players(
    card_name: str,
    player_id: int,
) -> None:
    battle = BattleState(rng=random.Random(96_140 + 10 * player_id))
    target = Position(9.5, 5.5 if player_id == 0 else 26.5)
    assert SPELL_REGISTRY[card_name].cast(battle, player_id, target)
    resident = ResidentRustBattle.from_battle(battle)

    _assert_semantic_parity(battle, resident)
    for _ in range(70):
        _advance_exact_tick(battle, resident)

    assert not any(isinstance(entity, RollingProjectile) for entity in battle.entities.values())


def test_log_hits_each_entity_only_once_while_footprints_keep_overlapping() -> None:
    battle = BattleState(rng=random.Random(96_180))
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.5, 16.0), 1, stats)
    target.hitpoints = target.max_hitpoints = 10_000.0
    target.deploy_delay_remaining = 100.0
    hitpoints_before = float(target.hitpoints)
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.5, 16.0))
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, RollingProjectile)
    )
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(40):
        _advance_exact_tick(battle, resident)
        if target.id in projectile.hit_entities:
            break
    assert target.id in projectile.hit_entities
    assert float(target.hitpoints) == hitpoints_before - 268.0

    for _ in range(5):
        _advance_exact_tick(battle, resident)
    assert float(target.hitpoints) == hitpoints_before - 268.0


@pytest.mark.parametrize(
    ("player_id", "target", "endpoint"),
    [
        (0, Position(6.5, 10.5), Position(6.5, 15.0)),
        (1, Position(11.5, 21.5), Position(11.5, 17.0)),
    ],
)
def test_barbarian_barrel_endpoint_child_is_published_in_the_landing_frame(
    player_id: int,
    target: Position,
    endpoint: Position,
) -> None:
    battle = BattleState(rng=random.Random(96_200 + player_id))
    projectile_id = battle.next_entity_id
    assert SPELL_REGISTRY["BarbLog"].cast(battle, player_id, target)
    resident = ResidentRustBattle.from_battle(battle)

    barbarian: Troop | None = None
    for _ in range(80):
        _advance_exact_tick(battle, resident)
        barbarian = next(
            (
                entity
                for entity in battle.entities.values()
                if isinstance(entity, Troop)
                and entity.player_id == player_id
                and entity.card_stats.name == "Barbarian"
            ),
            None,
        )
        if barbarian is not None:
            break

    assert barbarian is not None
    assert barbarian.id == projectile_id + 1
    assert barbarian.position == endpoint
    assert (barbarian.max_hitpoints, barbarian.damage) == (691, 192)
    assert barbarian.placement_pending
    assert barbarian.deploy_delay_remaining == pytest.approx(0.95)
    assert not any(isinstance(entity, RollingProjectile) for entity in battle.entities.values())
    assert resident.next_entity_id == battle.next_entity_id == projectile_id + 2


def test_on_publication_preserves_rolling_hit_set_identity_and_state() -> None:
    candidate = BattleState(rng=random.Random(96_220), fast_path=True)
    stats = candidate.card_loader.get_card("Knight")
    assert stats is not None
    target = candidate._spawn_entity(Troop, Position(9.5, 16.0), 1, stats)
    target.hitpoints = target.max_hitpoints = 10_000.0
    target.deploy_delay_remaining = 100.0
    assert SPELL_REGISTRY["Log"].cast(candidate, 0, Position(9.5, 16.0))
    projectile = next(
        entity
        for entity in candidate.entities.values()
        if type(entity) is RollingProjectile
    )
    hit_set = projectile.hit_entities
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    for _ in range(8):
        assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
        assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(
            control
        )
        if target.id in projectile.hit_entities:
            break

    assert target.id in projectile.hit_entities
    assert projectile.hit_entities is hit_set
    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)
    assert projectile.hit_entities is hit_set


def test_on_publication_materializes_barrel_child_and_keeps_roller_tombstone() -> None:
    candidate = BattleState(rng=random.Random(96_221), fast_path=True)
    projectile_id = candidate.next_entity_id
    assert SPELL_REGISTRY["BarbLog"].cast(candidate, 0, Position(9.0, 10.0))
    projectile = candidate.entities[projectile_id]
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    for _ in range(128):
        assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
        assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(
            control
        )
        if projectile_id + 1 in candidate.entities:
            break
    else:  # pragma: no cover - fixture invariant
        raise AssertionError("Barbarian Barrel child did not spawn")

    assert projectile_id not in candidate.entities
    assert runtime.entity_registry[projectile_id] is projectile
    child = candidate.entities[projectile_id + 1]
    assert type(child) is Troop
    assert child.card_stats.name == "Barbarian"
    assert child.deploy_delay_remaining == pytest.approx(0.95)

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)


@pytest.mark.parametrize(
    "tamper", ["legacy_exact", "unknown_hit_id", "child_fingerprint"]
)
def test_direct_rolling_publication_rejects_malformed_state_before_mutation(
    tamper: str,
) -> None:
    battle = BattleState(rng=random.Random(96_222), fast_path=True)
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    rolling = next(
        row["rolling_projectile_state"]
        for row in raw["entities"]
        if row["rolling_projectile_state"] is not None
    )
    if tamper == "legacy_exact":
        rolling["travel_speed"] = {"kind": "int", "value": 200}
    elif tamper == "child_fingerprint":
        rolling["spawn_character_data_fingerprint"] = "0" * 64
    else:
        rolling["hit_entity_ids"] = [raw["battle"]["next_entity_id"] + 100]
    before = canonical_battle_snapshot(battle)

    with pytest.raises(ResidentPublicationError):
        _build_direct_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert canonical_battle_snapshot(battle) == before


def test_rolling_publication_failure_restores_hit_set_identity_and_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(96_223), fast_path=True)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.0, 10.1), 1, stats)
    target.hitpoints = target.max_hitpoints = 10_000
    target.deploy_delay_remaining = 100.0
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    roller.time_alive = roller.spawn_delay
    hit_set = roller.hit_entities
    before = canonical_battle_snapshot(battle)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected rolling commit failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )
    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert canonical_battle_snapshot(battle) == before
    assert roller.hit_entities is hit_set
    assert roller.hit_entities == set()


@pytest.mark.parametrize(
    ("player_id", "target", "expected"),
    [
        (0, Position(9.0, 31.5), Position(9.0, 31.75)),
        (1, Position(9.0, 0.5), Position(9.0, 0.25)),
    ],
)
def test_barrel_endpoint_child_uses_outer_arena_clamp(
    player_id: int,
    target: Position,
    expected: Position,
) -> None:
    battle = BattleState(rng=random.Random(96_224 + player_id), fast_path=True)
    assert SPELL_REGISTRY["BarbLog"].cast(battle, player_id, target)
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(160):
        _advance_exact_tick(battle, resident)
        child = next(
            (
                entity
                for entity in battle.entities.values()
                if type(entity) is Troop and entity.card_stats.name == "Barbarian"
            ),
            None,
        )
        if child is not None:
            break
    else:  # pragma: no cover - fixture invariant
        raise AssertionError("Barbarian Barrel child did not spawn")

    assert child.position == expected


def test_rolling_spell_matches_python_for_preexisting_death_immunity_marker() -> None:
    battle = BattleState(rng=random.Random(96_226), fast_path=True)
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    roller.time_alive = roller.spawn_delay
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.0, 10.1), 1, stats)
    target.deploy_delay_remaining = 100.0
    target._death_spawn_target_immunity_elapsed_ms = 0
    resident = ResidentRustBattle.from_battle(battle)

    _advance_exact_tick(battle, resident)

    assert target.id in roller.hit_entities


@pytest.mark.parametrize("card_name", ["Log", "BarbLog"])
def test_rolling_fixed_seed_off_shadow_on_traces_match(card_name: str) -> None:
    seed = 96_230 if card_name == "Log" else 96_231
    battles: dict[RustBattleMode, BattleState] = {}
    runtimes: dict[RustBattleMode, ResidentCompleteTickRuntime] = {}
    traces: dict[RustBattleMode, list[object]] = {}
    for mode in (RustBattleMode.OFF, RustBattleMode.SHADOW, RustBattleMode.ON):
        battle = BattleState(rng=random.Random(seed), fast_path=True)
        assert SPELL_REGISTRY[card_name].cast(battle, 0, Position(9.0, 10.0))
        battles[mode] = battle
        runtimes[mode] = ResidentCompleteTickRuntime(battle, mode)
        traces[mode] = []

    for _ in range(10):
        for mode in (RustBattleMode.OFF, RustBattleMode.SHADOW, RustBattleMode.ON):
            assert runtimes[mode].advance_ticks(8) == 8
            traces[mode].append(canonical_battle_snapshot(battles[mode]))

    assert traces[RustBattleMode.SHADOW] == traces[RustBattleMode.OFF]
    assert traces[RustBattleMode.ON] == traces[RustBattleMode.OFF]
    assert runtimes[RustBattleMode.SHADOW].status.shadow_mismatches == 0


def test_barrel_child_allocation_headroom_is_preflighted() -> None:
    battle = BattleState(rng=random.Random(96_232), fast_path=True)
    assert SPELL_REGISTRY["BarbLog"].cast(battle, 0, Position(9.0, 10.0))
    battle.next_entity_id = (1 << 63) - 1
    before = canonical_battle_snapshot(battle)

    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick
    assert canonical_battle_snapshot(battle) == before


@pytest.mark.parametrize(
    ("next_entity_id", "succeeds"),
    [((1 << 63) - 3, True), ((1 << 63) - 2, False)],
)
def test_standalone_object_phase_preflights_terminal_barrel_child_headroom(
    next_entity_id: int,
    succeeds: bool,
) -> None:
    battle = BattleState(rng=random.Random(96_239), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    assert SPELL_REGISTRY["BarbLog"].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    roller.time_alive = roller.spawn_delay
    roller.distance_traveled = roller.projectile_range - 0.2
    roller.position.y += roller.projectile_range - 0.2
    battle.next_entity_id = next_entity_id
    resident = ResidentRustBattle.from_battle(battle)
    before = rust_resident_semantic_snapshot(resident)

    if succeeds:
        resident.advance_resident_object_phase()
        assert rust_resident_semantic_snapshot(resident)["next_entity_id"] == (1 << 63) - 2
    else:
        with pytest.raises(RuntimeError, match="allocation headroom"):
            resident.advance_resident_object_phase()
        assert rust_resident_semantic_snapshot(resident) == before


def test_standalone_point_helper_leaves_mixed_roller_unchanged() -> None:
    battle = BattleState(rng=random.Random(96_233), fast_path=True)
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    assert SPELL_REGISTRY["Fireball"].cast(battle, 0, Position(10.0, 12.0))
    resident = ResidentRustBattle.from_battle(battle)
    rolling_before = resident.rolling_projectile_state_bytes()
    point_before = resident.point_projectile_state_bytes()

    resident.advance_point_projectile_phase()

    assert resident.rolling_projectile_state_bytes() == rolling_before
    assert resident.point_projectile_state_bytes() != point_before


def test_complete_tick_mixes_combat_point_launch_and_rolling_object() -> None:
    battle = BattleState(rng=random.Random(96_238), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(Troop, Position(9.0, 12.0), 0, source_stats)
    target = battle._spawn_entity(Troop, Position(9.0, 14.0), 1, target_stats)
    for entity in (source, target):
        entity.deploy_delay_remaining = 0.0
        entity.placement_delay_total = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    source.target_id = target.id
    source.attack_cooldown = 0.0
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(5.0, 10.0))
    resident = ResidentRustBattle.from_battle(battle)

    _advance_exact_tick(battle, resident)

    assert any(type(entity) is RollingProjectile for entity in battle.entities.values())
    assert any(type(entity).__name__ == "Projectile" for entity in battle.entities.values())


@pytest.mark.parametrize(
    ("card_name", "field", "value"),
    [
        ("Log", "spawn_character_data", None),
        ("BarbLog", "spawn_character", None),
        ("BarbLog", "spawn_character_data", {}),
        ("BarbLog", "spawn_deploy_delay_override", None),
        ("BarbLog", "spawn_deploy_delay_override", 0.5),
    ],
)
def test_rolling_child_constructor_state_is_attested(
    card_name: str,
    field: str,
    value: object,
) -> None:
    battle = BattleState(rng=random.Random(96_234), fast_path=True)
    assert SPELL_REGISTRY[card_name].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    setattr(roller, field, value)
    before = canonical_battle_snapshot(battle)

    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick
    assert canonical_battle_snapshot(battle) == before


@pytest.mark.parametrize("card_name", ["Log", "BarbarianBarrel"])
def test_on_due_rolling_birth_preserves_exact_python_constructor_state(
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(96_235), fast_path=True)
    _prepare_single_card(battle, 0, card_name)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    assert action_space.apply_action(battle, 0, action)
    control = battle.clone()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    assert runtime.advance_ticks(20) == control.step_logic_ticks(20) == 20
    assert canonical_battle_snapshot(battle) == canonical_battle_snapshot(control)
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    if card_name == "Log":
        assert roller.spawn_character is None
        assert roller.spawn_character_data == {}
        assert roller.spawn_deploy_delay_override is None
    else:
        assert roller.spawn_character == "Barbarian"
        assert roller.spawn_character_data["name"] == "Barbarian"
        assert roller.spawn_deploy_delay_override == pytest.approx(1.0)


def test_historical_hit_id_survives_cleanup_rehydrate_and_on_publication() -> None:
    battle = BattleState(rng=random.Random(96_236), fast_path=True)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(Troop, Position(9.0, 10.1), 1, stats)
    target.hitpoints = target.max_hitpoints = 10_000
    target.deploy_delay_remaining = 100.0
    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    roller.time_alive = roller.spawn_delay
    battle._step_logic_tick(refresh_fast_path_end=False)
    assert target.id in roller.hit_entities
    target.is_alive = False
    battle._cleanup_dead_entities()
    assert target.id not in battle.entities
    assert target.id < battle.next_entity_id
    control = battle.clone()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    assert canonical_battle_snapshot(battle) == canonical_battle_snapshot(control)
    assert target.id in roller.hit_entities


def test_terminal_barrel_and_death_spawn_use_aggregate_id_headroom() -> None:
    battle = BattleState(rng=random.Random(96_237), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    assert SPELL_REGISTRY["BarbLog"].cast(battle, 0, Position(9.0, 10.0))
    roller = next(
        entity for entity in battle.entities.values() if type(entity) is RollingProjectile
    )
    roller.time_alive = roller.spawn_delay
    roller.distance_traveled = roller.projectile_range - 0.2
    roller.position.y += roller.projectile_range - 0.2
    stats = battle.card_loader.get_card("Golem")
    attacker_stats = battle.card_loader.get_card("Knight")
    assert stats is not None and attacker_stats is not None
    victim = battle._spawn_entity(Troop, Position(9.0, 14.0), 0, stats)
    attacker = battle._spawn_entity(Troop, Position(9.0, 13.5), 1, attacker_stats)
    for entity in (victim, attacker):
        entity.deploy_delay_remaining = 0.0
        entity.placement_delay_total = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    attacker.target_id = victim.id
    attacker.attack_cooldown = 0.0
    attacker.damage = victim.hitpoints + 1
    battle.next_entity_id = (1 << 63) - 2
    before = canonical_battle_snapshot(battle)

    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick
    assert canonical_battle_snapshot(battle) == before
