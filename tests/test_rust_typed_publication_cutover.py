from __future__ import annotations

import json
import random
from typing import Any

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
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
    _typed_publication_projection,
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime

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


def _prepared_scenarios() -> list[
    tuple[BattleState, ResidentRustBattle, ResidentRustBattle]
]:
    scenarios: list[tuple[BattleState, ResidentRustBattle, ResidentRustBattle]] = []

    baseline = BattleState(rng=random.Random(70_001), fast_path=True)
    prior = ResidentRustBattle.from_battle(baseline)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(8) == 8
    scenarios.append((baseline, prior, candidate))

    projectile = BattleState(rng=random.Random(70_002), fast_path=True)
    projectile.entities.clear()
    projectile.next_entity_id = 1
    source = _spawn_ready(projectile, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(projectile, "Knight", 1, Position(9.0, 15.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    prior = ResidentRustBattle.from_battle(projectile)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    scenarios.append((projectile, prior, candidate))

    area = BattleState(rng=random.Random(70_003), fast_path=True)
    area.entities.clear()
    area.next_entity_id = 1
    source = _spawn_ready(area, "IceGolem", 0, Position(9.0, 12.0))
    killer = _spawn_ready(area, "Knight", 1, Position(9.0, 13.0))
    killer.target_id = source.id
    killer.attack_cooldown = 0.0
    killer.damage = source.hitpoints + 1
    prior = ResidentRustBattle.from_battle(area)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    scenarios.append((area, prior, candidate))

    shields = BattleState(rng=random.Random(70_004), fast_path=True)
    shields.entities.clear()
    shields.next_entity_id = 1
    _spawn_ready(shields, "Guards", 0, Position(9.0, 12.0))
    _spawn_ready(shields, "Golem", 1, Position(9.0, 20.0))
    prior = ResidentRustBattle.from_battle(shields)
    candidate = prior.fork()
    scenarios.append((shields, prior, candidate))

    action = BattleState(rng=random.Random(70_007), fast_path=True)
    action.players[0].hand[0] = "Minions"
    action.players[0].elixir = 10.0
    prior = ResidentRustBattle.from_battle(action)
    no_op = 4 * 18 * 32
    minions = 10 * 18 + 8
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        minions, no_op, 0
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    scenarios.append((action, prior, candidate))

    arrows = BattleState(rng=random.Random(70_008), fast_path=True)
    arrows.players[0].hand[0] = "Arrows"
    arrows.players[0].elixir = 10.0
    prior = ResidentRustBattle.from_battle(arrows)
    arrow_action = 10 * 18 + 8
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        arrow_action, no_op, 22
    )
    assert success == {0: True, 1: True}
    assert advanced == 22
    scenarios.append((arrows, prior, candidate))

    death_spawn = BattleState(rng=random.Random(70_009), fast_path=True)
    death_spawn.entities.clear()
    death_spawn.next_entity_id = 1
    golem = _spawn_ready(death_spawn, "Golem", 0, Position(9.0, 14.0))
    attacker = _spawn_ready(death_spawn, "Knight", 1, Position(9.0, 13.5))
    attacker.target_id = golem.id
    attacker.attack_cooldown = 0.0
    attacker.damage = golem.hitpoints + 1
    prior = ResidentRustBattle.from_battle(death_spawn)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    scenarios.append((death_spawn, prior, candidate))

    return scenarios


def test_typed_projection_matches_every_legacy_publication_section() -> None:
    for _battle, prior, candidate in _prepared_scenarios():
        projection = _typed_publication_projection(
            candidate.prepare_publication(prior).parts()
        )
        assert projection.snapshot == rust_resident_semantic_snapshot(candidate)
        assert projection.publication_rows == json.loads(
            candidate.publication_entity_state_bytes()
        )
        assert projection.battle_presence == json.loads(
            candidate.publication_battle_attribute_presence_bytes()
        )
        assert projection.player_rows == json.loads(
            candidate.publication_player_state_bytes()
        )


def test_direct_plan_publication_matches_normalized_typed_projection() -> None:
    for battle, prior, candidate in _prepared_scenarios():
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        expected = _typed_publication_projection(raw)
        plan = _build_direct_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )
        assert plan.active_entity_ids == tuple(
            row["id"] for row in expected.snapshot["entities"]
        )

        registry = dict(battle.entities)
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )
        assert python_resident_semantic_snapshot(battle) == expected.snapshot


def test_on_publication_uses_one_typed_crossing_and_no_legacy_or_clone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(70_005), fast_path=True)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    native_type = type(resident._native)
    prepared = resident.fork().prepare_publication(resident)
    prepared_type = type(prepared._native)
    native_parts = prepared_type.parts
    crossings = 0

    def counted_parts(native: Any) -> Any:
        nonlocal crossings
        crossings += 1
        return native_parts(native)

    monkeypatch.setattr(prepared_type, "parts", counted_parts)
    for name in (
        "publication_entity_state_bytes",
        "publication_player_state_bytes",
        "publication_battle_attribute_presence_bytes",
        "publication_exactness_sha256",
        "entity_state_bytes",
        "rng_state_bytes",
    ):
        monkeypatch.setattr(
            native_type,
            name,
            lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"legacy exporter called: {_name}")
            ),
        )
    monkeypatch.setattr(
        rust_publication,
        "python_resident_semantic_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Python semantic snapshot called")
        ),
    )
    monkeypatch.setattr(
        rust_publication,
        "rust_resident_semantic_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Rust semantic snapshot called")
        ),
    )
    monkeypatch.setattr(
        rust_publication,
        "_typed_publication_projection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("diagnostic typed projection called")
        ),
    )
    monkeypatch.setattr(
        BattleState,
        "clone",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("BattleState.clone called")
        ),
    )

    assert runtime.advance_ticks(8) == 8
    assert crossings == 1


def test_typed_decoder_rejects_bool_exact_scalar() -> None:
    _battle, prior, candidate = _prepared_scenarios()[0]
    parts = candidate.prepare_publication(prior).parts()
    modified = dict(parts)
    entities = list(parts["entities"])
    entity = dict(entities[0])
    entity["hitpoints"] = (True, 1, 0)
    entities[0] = entity
    modified["entities"] = tuple(entities)

    with pytest.raises(ResidentPublicationError, match="exact scalar"):
        _typed_publication_projection(modified)


def test_typed_binding_rejects_wrong_registry_before_mutation() -> None:
    battle = BattleState(rng=random.Random(70_006), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    registry = dict(battle.entities)
    registry.pop(next(iter(registry)))
    before = tuple(battle.entities.items())

    with pytest.raises(ResidentPublicationError, match="registry disagrees"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert tuple(battle.entities.items()) == before


def test_direct_raw_structural_tampering_fails_before_live_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    def reject_mutation(
        battle: BattleState,
        prior: ResidentRustBattle,
        candidate: ResidentRustBattle,
        mutate: Any,
    ) -> None:
        original_build = rust_publication._build_direct_publication_plan

        def mutate_then_build(raw: Any, **kwargs: Any) -> Any:
            mutate(raw)
            return original_build(raw, **kwargs)

        monkeypatch.setattr(
            rust_publication,
            "_build_direct_publication_plan",
            mutate_then_build,
        )
        before = tuple(battle.entities.items())
        with pytest.raises(ResidentPublicationError):
            publish_complete_tick_state(
                battle,
                candidate,
                prior_resident=prior,
                entity_registry=dict(battle.entities),
            )
        assert tuple(battle.entities.items()) == before
        monkeypatch.setattr(
            rust_publication, "_build_direct_publication_plan", original_build
        )

    projectile = BattleState(rng=random.Random(70_010), fast_path=True)
    projectile.entities.clear()
    projectile.next_entity_id = 1
    source = _spawn_ready(projectile, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(projectile, "Knight", 1, Position(9.0, 15.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    prior = ResidentRustBattle.from_battle(projectile)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()

    def replace_exact_with_legacy_dict(raw: dict[str, Any]) -> None:
        row = next(
            row for row in raw["entities"] if row["point_projectile_state"] is not None
        )
        row["point_projectile_state"]["constructor_range"] = {
            "bits": "0000000000000000",
            "kind": "float",
        }

    reject_mutation(projectile, prior, candidate, replace_exact_with_legacy_dict)

    area = BattleState(rng=random.Random(70_011), fast_path=True)
    area.entities.clear()
    area.next_entity_id = 1
    source = _spawn_ready(area, "IceGolem", 0, Position(9.0, 12.0))
    killer = _spawn_ready(area, "Knight", 1, Position(9.0, 13.0))
    killer.target_id = source.id
    killer.attack_cooldown = 0.0
    killer.damage = source.hitpoints + 1
    prior = ResidentRustBattle.from_battle(area)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()

    def break_area_source(raw: dict[str, Any]) -> None:
        row = next(
            row for row in raw["entities"] if row["area_effect_state"] is not None
        )
        row["area_effect_state"]["birth_source_entity_id"] = None

    reject_mutation(area, prior, candidate, break_area_source)

    action = BattleState(rng=random.Random(70_012), fast_path=True)
    action.players[0].hand[0] = "Minions"
    action.players[0].elixir = 10.0
    prior = ResidentRustBattle.from_battle(action)
    no_op = 4 * 18 * 32
    candidate, _success, _order, _advanced = (
        prior.preview_resident_joint_action_interval(10 * 18 + 8, no_op, 0)
    )

    def break_provenance(raw: dict[str, Any]) -> None:
        row = next(row for row in raw["entities"] if row["character_birth"] is not None)
        row["character_birth"]["ordinal"] = 17

    reject_mutation(action, prior, candidate, break_provenance)

    def break_birth_name(raw: dict[str, Any]) -> None:
        row = next(row for row in raw["entities"] if row["character_birth"] is not None)
        row["card_name"] = f"{row['card_name']}-tampered"

    reject_mutation(action, prior, candidate, break_birth_name)

    topology, topology_prior, topology_candidate = _prepared_scenarios()[0]

    def break_movement_combat_topology(raw: dict[str, Any]) -> None:
        row = next(row for row in raw["entities"] if row["movement_state"] is not None)
        row["locked_combat_state"] = None

    reject_mutation(
        topology,
        topology_prior,
        topology_candidate,
        break_movement_combat_topology,
    )
