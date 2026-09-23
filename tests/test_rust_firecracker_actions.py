from __future__ import annotations

import json
import random
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from clasher import rust_core
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentRustBattle,
    rust_core_available,
)
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    _build_direct_delta_publication_plan,
    _build_direct_publication_plan,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, RustBattleMode

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
    prior = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    entity = next(
        value
        for entity_id, value in battle.entities.items()
        if entity_id not in prior and isinstance(value, Troop)
    )
    entity.position = position
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 0.0
    return entity


def _fixture(*, mirrored: bool = False) -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(rng=random.Random(192_000), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    owner = int(mirrored)
    direction = -1.0 if mirrored else 1.0
    firecracker = _spawn_ready(
        battle, "Firecracker", owner, Position(9.0, 16.0 - 6.0 * direction)
    )
    target = _spawn_ready(
        battle, "Knight", 1 - owner, Position(9.0, 16.0 - direction)
    )
    target.attack_cooldown = 10.0
    return battle, firecracker, target


def _resident_with_firecracker_catalog_mutation(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None],
) -> ResidentRustBattle:
    battle = BattleState(rng=random.Random(192_009), fast_path=True)
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "Firecracker"
    )
    fields = card["template_snapshot"]["$object"]["fields"]
    card_fields = fields["card_stats"]["$object"]["fields"]
    projectile_value = card_fields["projectile_data"]
    projectile = dict(projectile_value["$mapping"])
    child_value = projectile["spawnProjectileData"]
    child = dict(child_value["$mapping"])
    mutate(fields, projectile, child)
    child_value["$mapping"] = list(child.items())
    projectile["spawnProjectileData"] = child_value
    projectile_value["$mapping"] = list(projectile.items())
    card_fields["projectile_data"] = projectile_value
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    monkeypatch.setattr(
        rust_core,
        "_resident_card_catalog_bundle",
        lambda *_args: replace(
            bundle,
            payload=json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("ascii"),
        ),
    )
    return ResidentRustBattle.from_battle(battle)


def test_firecracker_is_the_structural_attack_recoil_action() -> None:
    battle = BattleState(rng=random.Random(192_001), fast_path=True)
    resident = ResidentRustBattle.from_battle(battle)

    assert "Firecracker" in resident.resident_supported_action_cards()
    assert resident.resident_action_card_capability_reasons("Firecracker") == ()
    assert resident.resident_catalog_schema_version == 19


@pytest.mark.parametrize("player_id", [0, 1])
def test_firecracker_both_player_action_ingress_matches_python(
    player_id: int,
) -> None:
    battle = BattleState(rng=random.Random(192_003), fast_path=True)
    for player in battle.players:
        player.deck = ["Firecracker"] * 8
        player.hand = ["Firecracker"] * 4
        player.cycle_queue = deque(["Firecracker"] * 4)
        player.elixir = player.max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(
        0, 8, 10 if player_id == 0 else 21, player_id
    )
    actions = [action_space.no_op_action, action_space.no_op_action]
    actions[player_id] = action
    assert action in resident.resident_legal_action_ids(player_id)

    order = [0, 1]
    battle.rng.shuffle(order)
    expected: dict[int, bool] = {}
    for owner in order:
        expected[owner] = action_space.apply_action(battle, owner, actions[owner])
    actual, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == tuple(order)
    assert actual == expected == {0: True, 1: True}
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(battle)
    )


@pytest.mark.parametrize("mirrored", [False, True])
def test_firecracker_recoil_shards_and_on_publication_match_python(
    mirrored: bool,
) -> None:
    candidate, firecracker, _ = _fixture(mirrored=mirrored)
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    for _ in range(20):
        assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
        assert python_resident_semantic_snapshot(candidate) == (
            python_resident_semantic_snapshot(control)
        )
        assert runtime.resident is not None
        assert rust_resident_semantic_snapshot(runtime.resident) == (
            python_resident_semantic_snapshot(control)
        )

    projectiles = [
        entity
        for entity in runtime.entity_registry.values()
        if type(entity) is Projectile
    ]
    carrier = min(projectiles, key=lambda entity: entity.id)
    shards = [entity for entity in projectiles if entity.id != carrier.id]
    assert not carrier.is_alive
    assert len(shards) == 5
    assert [entity.id for entity in shards] == list(
        range(carrier.id + 1, carrier.id + 6)
    )
    assert all(entity.source_entity is None for entity in shards)
    assert all(entity.source_name == "Firecracker" for entity in shards)
    assert all(entity.card_stats is firecracker.card_stats for entity in shards)
    assert all(type(entity.damage) is float and entity.damage == 64.0 for entity in shards)
    assert all(entity.pierces and entity.projectile_range == 0.0 for entity in shards)
    assert all(entity.start_extra_radius == 0.65 for entity in shards)


@pytest.mark.parametrize("mode", [RustBattleMode.OFF, RustBattleMode.SHADOW])
def test_firecracker_off_and_shadow_match_python(mode: RustBattleMode) -> None:
    candidate, _, _ = _fixture()
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, mode)

    assert runtime.advance_ticks(20) == control.step_logic_ticks(20) == 20
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_firecracker_publication_failure_restores_recoil_and_projectile_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle, firecracker, target = _fixture()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    assert runtime.advance_ticks(9) == 9
    resident = runtime.resident
    assert resident is not None
    semantic_before = python_resident_semantic_snapshot(battle)
    active_before = tuple(battle.entities.items())
    registry_before = tuple(runtime.entity_registry.items())
    rng_before = battle.rng.getstate()
    next_id_before = battle.next_entity_id
    identities = tuple(map(id, (firecracker, target, firecracker.mechanics[0])))

    def fail_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected Firecracker commit failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", fail_commit
    )
    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == semantic_before
    assert tuple(battle.entities.items()) == active_before
    assert tuple(runtime.entity_registry.items()) == registry_before
    assert battle.rng.getstate() == rng_before
    assert battle.next_entity_id == next_id_before
    assert tuple(map(id, (firecracker, target, firecracker.mechanics[0]))) == identities
    assert runtime.resident is resident


def test_firecracker_nested_child_damage_tamper_rejects_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(192_002), fast_path=True)
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "Firecracker"
    )
    fields = card["template_snapshot"]["$object"]["fields"]
    projectile_data = dict(fields["card_stats"]["$object"]["fields"])[
        "projectile_data"
    ]
    child = dict(projectile_data["$mapping"])["spawnProjectileData"]
    child_mapping = dict(child["$mapping"])
    child_mapping["damage"] = {"$int": 26}
    child["$mapping"] = list(child_mapping.items())
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    monkeypatch.setattr(
        rust_core,
        "_resident_card_catalog_bundle",
        lambda *_args: replace(
            bundle,
            payload=json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("ascii"),
        ),
    )

    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )
    assert "template_parse" in " ".join(
        resident.resident_action_card_capability_reasons("Firecracker")
    )
    assert before == (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )


@pytest.mark.parametrize("outer_damage", [0, 25])
def test_firecracker_carrier_raw_damage_must_be_absent(
    monkeypatch: pytest.MonkeyPatch,
    outer_damage: int,
) -> None:
    resident = _resident_with_firecracker_catalog_mutation(
        monkeypatch,
        lambda _fields, projectile, _child: projectile.__setitem__(
            "damage", outer_damage
        ),
    )

    assert "native_single_troop_preflight" in " ".join(
        resident.resident_action_card_capability_reasons("Firecracker")
    )


def test_firecracker_carrier_explicit_null_raw_damage_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resident = _resident_with_firecracker_catalog_mutation(
        monkeypatch,
        lambda _fields, projectile, _child: projectile.__setitem__(
            "damage", None
        ),
    )

    assert resident.resident_action_card_capability_reasons("Firecracker") == ()


def test_firecracker_child_explicit_planes_override_tid_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mutate(
        fields: dict[str, Any],
        _projectile: dict[str, Any],
        child: dict[str, Any],
    ) -> None:
        fields["_can_attack_air_cached"] = False
        fields["_can_attack_ground_cached"] = True
        child["hitsAir"] = True
        child["hitsGround"] = True
        child["tidTarget"] = "TID_TARGETS_GROUND"

    resident = _resident_with_firecracker_catalog_mutation(monkeypatch, mutate)

    assert resident.resident_action_card_capability_reasons("Firecracker") == ()


@pytest.mark.parametrize("plane_source", ["explicit", "inherited"])
def test_firecracker_child_one_plane_near_match_rejects(
    monkeypatch: pytest.MonkeyPatch,
    plane_source: str,
) -> None:
    def mutate(
        fields: dict[str, Any],
        _projectile: dict[str, Any],
        child: dict[str, Any],
    ) -> None:
        if plane_source == "explicit":
            child["hitsAir"] = False
            child["hitsGround"] = True
            child["tidTarget"] = "TID_TARGETS_AIR_AND_GROUND"
        else:
            child.pop("tidTarget", None)
            fields["_can_attack_air_cached"] = False
            fields["_can_attack_ground_cached"] = True

    resident = _resident_with_firecracker_catalog_mutation(monkeypatch, mutate)

    assert "native_single_troop_preflight" in " ".join(
        resident.resident_action_card_capability_reasons("Firecracker")
    )


def test_firecracker_start_collision_death_spawn_interleaves_ids_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    def build() -> BattleState:
        battle = BattleState(rng=random.Random(192_010), fast_path=True)
        battle.entities.clear()
        battle.next_entity_id = 1
        _spawn_ready(battle, "Firecracker", 0, Position(9.0, 10.0))
        golem = _spawn_ready(battle, "Golem", 1, Position(9.0, 15.0))
        golem.hitpoints = 1.0
        golem.attack_cooldown = 10.0
        return battle

    battle = build()
    control = battle.clone()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    for _ in range(10):
        assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
        assert python_resident_semantic_snapshot(battle) == (
            python_resident_semantic_snapshot(control)
        )
        assert runtime.resident is not None
        assert rust_resident_semantic_snapshot(runtime.resident) == (
            python_resident_semantic_snapshot(control)
        )
    assert battle.rng.getstate() == control.rng.getstate()
    assert [
        (entity_id, type(entity).__name__)
        for entity_id, entity in runtime.entity_registry.items()
        if 4 <= entity_id <= 10
    ] == [
        (4, "Projectile"),
        (5, "Troop"),
        (6, "Troop"),
        (7, "Projectile"),
        (8, "Projectile"),
        (9, "Projectile"),
        (10, "Projectile"),
    ]
    assert 2 not in battle.entities and not runtime.entity_registry[2].is_alive
    assert 3 not in battle.entities and not runtime.entity_registry[3].is_alive
    shards = [
        entity
        for entity in runtime.entity_registry.values()
        if type(entity) is Projectile and entity.id in {4, 7, 8, 9, 10}
    ]
    assert all(entity.start_collision_resolved for entity in shards)
    assert set(shards[0].hit_entity_ids) == {2, 5, 6}

    rollback_battle = build()
    rollback_runtime = ResidentCompleteTickRuntime(
        rollback_battle, RustBattleMode.ON
    )
    assert rollback_runtime.advance_ticks(9) == 9
    before = python_resident_semantic_snapshot(rollback_battle)
    registry_before = tuple(rollback_runtime.entity_registry.items())
    rng_before = rollback_battle.rng.getstate()

    def fail_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected interleaved-impact failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", fail_commit
    )
    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        rollback_runtime.advance_ticks(1)
    assert python_resident_semantic_snapshot(rollback_battle) == before
    assert tuple(rollback_runtime.entity_registry.items()) == registry_before
    assert rollback_battle.rng.getstate() == rng_before


def test_firecracker_impact_child_headroom_rejects_before_mutation() -> None:
    battle, _, _ = _fixture()
    assert battle.step_logic_ticks(9) == 9
    battle.next_entity_id = (1 << 63) - 4
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.entity_state_bytes(),
        resident.rng_state_bytes(),
        resident.next_entity_id,
    )

    with pytest.raises(RuntimeError, match="allocation headroom"):
        resident.advance_complete_tick()

    assert before == (
        resident.entity_state_bytes(),
        resident.rng_state_bytes(),
        resident.next_entity_id,
    )


@pytest.mark.parametrize("delta", [False, True])
def test_firecracker_impact_provenance_tamper_rejects_pre_live(
    delta: bool,
) -> None:
    battle, _, target = _fixture()
    target.attack_cooldown = 10.0
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(10) == 10
    registry = dict(battle.entities)
    before = python_resident_semantic_snapshot(battle)

    if delta:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        row = next(
            change["full"]
            for change in raw["entities"]
            if change["full"] is not None
            and change["full"]["point_projectile_state"] is not None
            and change["full"]["point_projectile_state"][
                "impact_child_provenance"
            ]
        )
        row["point_projectile_state"]["start_extra_radius"] = 0.0
        with pytest.raises(ResidentPublicationError, match="impact provenance"):
            _build_direct_delta_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=registry,
            )
    else:
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        row = next(
            entity
            for entity in raw["entities"]
            if entity["point_projectile_state"] is not None
            and entity["point_projectile_state"]["impact_child_provenance"]
        )
        row["point_projectile_state"]["start_extra_radius"] = 0.0
        with pytest.raises(ResidentPublicationError, match="impact provenance"):
            _build_direct_publication_plan(
                raw,
                battle=battle,
                resident=candidate,
                entity_registry=registry,
            )
    assert python_resident_semantic_snapshot(battle) == before
