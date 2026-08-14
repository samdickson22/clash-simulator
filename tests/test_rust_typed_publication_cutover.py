from __future__ import annotations

import copy
import json
import random
import struct
from typing import Any

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.pathfinding import ground_path_waypoint
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_BEST_CONSUMER,
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
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
    _build_direct_delta_publication_plan,
    _build_direct_publication_plan,
    _require_live_application_shape,
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


def _advance_python_movement(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if not isinstance(entity, (Troop, Building)) or not entity.is_alive:
            continue
        if isinstance(entity, Troop):
            battle._accumulate_troop_collision_for(entity)
        entity.begin_movement_tick()
        try:
            entity.update_movement_component(battle.dt, battle)
        finally:
            entity.finish_movement_tick(battle)
            entity.quantize_logic_position()


def _identity_projection(value: Any) -> Any:
    if type(value) is float:
        return ("float", struct.pack(">d", value))
    if type(value) in (str, int, bool, type(None), bytes):
        return (type(value), value)
    if isinstance(value, np.ndarray):
        return ("array", id(value), value.dtype.str, value.shape, value.tobytes())
    if type(value) is list:
        return ("list", id(value), tuple(_identity_projection(item) for item in value))
    if type(value) is tuple:
        return ("tuple", tuple(_identity_projection(item) for item in value))
    if type(value) is dict:
        return (
            "dict",
            id(value),
            tuple(
                (_identity_projection(key), _identity_projection(item))
                for key, item in value.items()
            ),
        )
    if type(value) is set:
        return ("set", id(value), frozenset(_identity_projection(item) for item in value))
    return ("object", id(value))


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


def test_private_delta_reconstructs_full_parts_for_prepared_scenario_matrix() -> None:
    for _battle, prior, candidate in _prepared_scenarios():
        prior_full = (
            prior.fork()
            .prepare_publication(prior)
            ._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)
        )
        candidate_full = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        delta = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )

        reconstructed, idle_eligible = _reconstruct_prepared_publication_delta(
            prior_full,
            delta,
            prior_idle_eligible=prior.supports_idle_ticks,
        )
        _assert_bit_exact(reconstructed, candidate_full)
        assert idle_eligible is candidate.supports_idle_ticks


def _full_parts(
    resident: ResidentRustBattle, prior: ResidentRustBattle
) -> dict[str, Any]:
    return resident.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )


def _delta_parts(
    resident: ResidentRustBattle, prior: ResidentRustBattle
) -> dict[str, Any]:
    return resident.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )


def _assert_bit_exact(actual: Any, expected: Any, path: str = "$") -> None:
    assert type(actual) is type(expected), path
    if type(expected) is float:
        assert struct.pack(">d", actual) == struct.pack(">d", expected), path
        return
    if type(expected) is dict:
        assert set(actual) == set(expected), path
        for key in expected:
            _assert_bit_exact(actual[key], expected[key], f"{path}.{key}")
        return
    if type(expected) in (list, tuple):
        assert len(actual) == len(expected), path
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=True)
        ):
            _assert_bit_exact(actual_item, expected_item, f"{path}[{index}]")
        return
    assert actual == expected, path


def _reconstruct_prepared_publication_delta(
    prior: dict[str, Any],
    delta: dict[str, Any],
    *,
    prior_idle_eligible: bool,
) -> tuple[dict[str, Any], bool]:
    """Test-only reconstruction of full v1 parts plus private idle eligibility."""
    if type(prior) is not dict or type(delta) is not dict:
        raise TypeError("prepared publication reconstruction requires builtin mappings")
    if prior.get("version") != 1 or delta.get("version") != 1:
        raise ValueError("unsupported prepared publication reconstruction version")
    if type(prior_idle_eligible) is not bool:
        raise TypeError("prepared publication prior idle eligibility is malformed")
    prior_binding = prior.get("binding")
    binding = delta.get("binding")
    if type(prior_binding) is not dict or type(binding) is not dict:
        raise TypeError("prepared publication reconstruction binding is malformed")
    binding_keys = {
        "semantic_schema_version",
        "lineage_id",
        "prior_node_id",
        "prior_epoch",
        "candidate_node_id",
        "candidate_epoch",
        "parent_node_id",
        "parent_epoch",
        "prior_next_entity_id",
        "prior_entity_ids",
        "checkpoint_schema_version",
        "checkpoint_generation",
        "catalog_schema_version",
        "catalog_fingerprint",
        "catalog_source_fingerprint",
    }
    if set(prior_binding) != binding_keys or set(binding) != binding_keys:
        raise ValueError(
            "prepared publication reconstruction binding shape is malformed"
        )
    integer_binding_fields = binding_keys - {
        "prior_entity_ids",
        "catalog_fingerprint",
        "catalog_source_fingerprint",
    }
    if any(type(binding[name]) is not int for name in integer_binding_fields):
        raise TypeError("prepared publication delta binding integer is malformed")
    if (
        binding["semantic_schema_version"] != 7
        or binding["checkpoint_schema_version"] != 2
        or binding["catalog_schema_version"] != 4
        or binding["lineage_id"] != prior_binding["lineage_id"]
        or binding["prior_node_id"] != prior_binding["prior_node_id"]
        or binding["prior_epoch"] != prior_binding["prior_epoch"]
        or binding["parent_node_id"] != binding["prior_node_id"]
        or binding["parent_epoch"] != binding["prior_epoch"]
        or prior_binding["parent_node_id"] != prior_binding["prior_node_id"]
        or prior_binding["parent_epoch"] != prior_binding["prior_epoch"]
        or binding["checkpoint_schema_version"]
        != prior_binding["checkpoint_schema_version"]
        or binding["checkpoint_generation"] != prior_binding["checkpoint_generation"]
        or binding["catalog_schema_version"] != prior_binding["catalog_schema_version"]
        or binding["catalog_fingerprint"] != prior_binding["catalog_fingerprint"]
        or binding["catalog_source_fingerprint"]
        != prior_binding["catalog_source_fingerprint"]
    ):
        raise ValueError("prepared publication delta binding does not match its prior")
    for name in ("catalog_fingerprint", "catalog_source_fingerprint"):
        fingerprint = binding[name]
        if (
            type(fingerprint) is not str
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise ValueError(
                "prepared publication delta catalog fingerprint is malformed"
            )

    prior_entities = prior.get("entities")
    if type(prior_entities) is not list or any(
        type(row) is not dict for row in prior_entities
    ):
        raise TypeError("prepared publication prior entities are malformed")
    prior_ids = [row.get("id") for row in prior_entities]
    if any(type(entity_id) is not int for entity_id in prior_ids) or len(
        set(prior_ids)
    ) != len(prior_ids):
        raise ValueError("prepared publication prior entity allocation is malformed")
    binding_prior_ids = binding.get("prior_entity_ids")
    if type(binding_prior_ids) is not list or binding_prior_ids != prior_ids:
        raise ValueError("prepared publication delta prior entity binding is malformed")
    prior_next_id = binding.get("prior_next_entity_id")
    next_entity_id = delta.get("next_entity_id")
    if (
        type(prior_next_id) is not int
        or type(next_entity_id) is not int
        or prior.get("battle", {}).get("next_entity_id") != prior_next_id
        or next_entity_id < prior_next_id
    ):
        raise ValueError("prepared publication delta next entity ID is malformed")

    result = copy.deepcopy(prior)
    result["binding"] = copy.deepcopy(binding)
    dirty_mask = delta.get("dirty_mask")
    if type(dirty_mask) is not int or dirty_mask < 0 or dirty_mask & ~0x3F:
        raise ValueError("prepared publication delta has an unknown root dirty bit")
    sections = (
        (1 << 0, "battle"),
        (1 << 1, "players"),
        (1 << 2, "towers"),
        (1 << 3, "rng"),
        (1 << 4, "pending_spells"),
        (1 << 5, "projectile_groups"),
    )
    for bit, name in sections:
        payload = delta.get(name)
        if bool(dirty_mask & bit) != (payload is not None):
            raise ValueError(
                f"prepared publication delta {name} payload disagrees with mask"
            )
        if payload is not None:
            result[name] = copy.deepcopy(payload)
    idle_eligible = delta.get("idle_eligible")
    if bool(dirty_mask & (1 << 0)) != (type(idle_eligible) is bool):
        raise ValueError("prepared publication idle eligibility disagrees with mask")
    reconstructed_idle = (
        idle_eligible if type(idle_eligible) is bool else prior_idle_eligible
    )

    prior_rows = {row["id"]: copy.deepcopy(row) for row in prior_entities}
    rows = dict(prior_rows)
    known_entity_mask = (1 << 11) - 1
    changes = delta.get("entities")
    if type(changes) is not list:
        raise TypeError("prepared publication entity deltas are not a list")
    changed_ids: set[int] = set()
    for change in changes:
        if type(change) is not dict:
            raise TypeError("prepared publication entity delta is not a mapping")
        entity_id = change.get("id")
        mask = change.get("dirty_mask")
        if (
            type(entity_id) is not int
            or type(mask) is not int
            or mask <= 0
            or mask & ~known_entity_mask
            or entity_id in changed_ids
        ):
            raise ValueError("prepared publication entity delta is malformed")
        changed_ids.add(entity_id)
        if mask & (1 << 10):
            if (
                mask != 1 << 10
                or type(change.get("full")) is not dict
                or change["full"].get("id") != entity_id
                or entity_id in prior_rows
            ):
                raise ValueError("prepared publication full entity delta is malformed")
            rows[entity_id] = copy.deepcopy(change["full"])
            continue
        if entity_id not in prior_rows or change.get("full") is not None:
            raise ValueError("prepared publication prefix entity delta is malformed")
        row = rows[entity_id]
        sparse = change.get("sparse_attribute_presence")
        base = change.get("base")
        shields = change.get("shields")
        shield_break_count = change.get("shield_break_count")
        if (sparse is not None) != bool(mask & (1 << 0)):
            raise ValueError(
                "prepared publication entity presence payload disagrees with mask"
            )
        if (base is not None) != bool(mask & (1 << 1)):
            raise ValueError(
                "prepared publication entity base payload disagrees with mask"
            )
        if bool(mask & (1 << 1)) and type(base) is not dict:
            raise TypeError("prepared publication entity base payload is not a mapping")
        if bool(mask & (1 << 2)) != (
            type(shields) is list and type(shield_break_count) is int
        ):
            raise ValueError(
                "prepared publication entity shield payload disagrees with mask"
            )
        if mask & (1 << 0):
            row["sparse_attribute_presence"] = sparse
        if mask & (1 << 1):
            row.update(copy.deepcopy(base))
        if mask & (1 << 2):
            row["shields"] = copy.deepcopy(shields)
            row["shield_break_count"] = shield_break_count
        optional_sections = (
            (1 << 3, "modifier_state", "modifier_present"),
            (1 << 4, "movement_state", "movement_present"),
            (1 << 5, "locked_combat_state", "locked_combat_present"),
            (1 << 6, "building_lifetime_state", "building_lifetime_present"),
            (1 << 7, "building_impact_state", "building_impact_present"),
            (1 << 8, "point_projectile_state", "point_projectile_present"),
            (1 << 9, "area_effect_state", "area_effect_present"),
        )
        for bit, field, present_field in optional_sections:
            present = change.get(present_field)
            value = change.get(field)
            if type(present) is not bool:
                raise TypeError(
                    f"prepared publication entity {present_field} is not a boolean"
                )
            if not mask & bit and (present or value is not None):
                raise ValueError(
                    f"prepared publication entity {field} payload disagrees with mask"
                )
            if mask & bit:
                if present != (value is not None):
                    raise ValueError(
                        f"prepared publication entity {field} disagrees with presence"
                    )
                if value is not None and type(value) is not dict:
                    raise TypeError(
                        f"prepared publication entity {field} is not a mapping"
                    )
                row[field] = copy.deepcopy(value)
        rows[entity_id] = row
    all_ids = delta.get("all_entity_ids")
    if (
        type(all_ids) is not list
        or any(type(entity_id) is not int for entity_id in all_ids)
        or len(set(all_ids)) != len(all_ids)
        or all_ids[: len(prior_ids)] != prior_ids
        or all_ids[len(prior_ids) :] != list(range(prior_next_id, next_entity_id))
    ):
        raise TypeError("prepared publication delta entity IDs are malformed")
    if set(rows) != set(all_ids):
        raise ValueError("prepared publication delta entity allocation is incomplete")
    result["entities"] = [rows[entity_id] for entity_id in all_ids]
    active_ids = delta.get("active_entity_ids")
    if (
        type(active_ids) is not list
        or any(type(entity_id) is not int for entity_id in active_ids)
        or len(set(active_ids)) != len(active_ids)
        or [
            row["id"]
            for row in sorted(
                (row for row in result["entities"] if row["active"]),
                key=lambda row: row["encounter_index"],
            )
        ]
        != active_ids
    ):
        raise ValueError("prepared publication delta active order is malformed")
    if result["battle"]["next_entity_id"] != next_entity_id:
        raise ValueError("prepared publication delta next entity ID is malformed")
    return result, reconstructed_idle


def test_private_delta_preserves_precision_route_status_pending_and_rng() -> None:
    battle = BattleState(rng=random.Random(70_011), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_ready(battle, "Knight", 0, Position(9, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 18.0))
    mover.hitpoints = int(mover.hitpoints)
    mover.max_hitpoints = float(mover.max_hitpoints)
    mover.initial_position = Position(9, -0.0)
    mover.stun_timer = -0.0
    mover._movement_target_id = target.id
    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
        backwards_reference=target.position,
    )
    battle._queue_spell_cast("Fireball", 0, Position(9.5, 16.5))
    battle.rng.gauss(0.0, 1.0)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()

    prior_full = _full_parts(prior.fork(), prior)
    candidate_full = _full_parts(candidate, prior)
    delta = _delta_parts(candidate, prior)
    reconstructed, idle_eligible = _reconstruct_prepared_publication_delta(
        prior_full,
        delta,
        prior_idle_eligible=prior.supports_idle_ticks,
    )
    _assert_bit_exact(reconstructed, candidate_full)
    assert idle_eligible is candidate.supports_idle_ticks

    row = next(row for row in candidate_full["entities"] if row["id"] == mover.id)
    assert row["hitpoints"][0] == 0
    assert row["max_hitpoints"][0] == 1
    assert row["modifier_state"]["stun_timer"] == -0.0
    assert struct.pack(">d", row["modifier_state"]["stun_timer"]) == bytes.fromhex(
        "8000000000000000"
    )
    assert row["movement_state"]["route_cache_kind"] == 2
    assert row["movement_state"]["route_goal"] is not None
    assert row["locked_combat_state"]["initial_position"] == (
        (0, 9, 0),
        (1, 0, 0x8000000000000000),
    )
    assert candidate_full["pending_spells"]["next_sequence"] == 1
    assert len(candidate_full["pending_spells"]["casts"]) == 1
    assert candidate_full["rng"]["gauss_next"] is not None


def test_private_delta_preserves_born_and_removed_character_suffix() -> None:
    battle = BattleState(rng=random.Random(12_303), fast_path=True)
    musketeer = _spawn_ready(battle, "Musketeer", 1, Position(9.0, 17.0))
    musketeer.damage = 100_000.0
    musketeer.attack_cooldown = 0.0
    battle.players[0].hand = ["Skeletons", None, None, None]
    battle.players[0].elixir = battle.players[0].max_elixir
    first_id = battle.next_entity_id
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 13, 0)
    prior = ResidentRustBattle.from_battle(battle)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action,
        action_space.no_op_action,
        25,
    )
    assert success == {0: True, 1: True}
    assert advanced == 25

    prior_full = _full_parts(prior.fork(), prior)
    candidate_full = _full_parts(candidate, prior)
    delta = _delta_parts(candidate, prior)
    reconstructed, idle_eligible = _reconstruct_prepared_publication_delta(
        prior_full,
        delta,
        prior_idle_eligible=prior.supports_idle_ticks,
    )
    _assert_bit_exact(reconstructed, candidate_full)
    assert idle_eligible is candidate.supports_idle_ticks

    assert delta["all_entity_ids"][-(delta["next_entity_id"] - first_id) :] == list(
        range(first_id, delta["next_entity_id"])
    )
    suffix = [row for row in delta["entities"] if row["id"] >= first_id]
    assert suffix
    assert all(row["dirty_mask"] == 1 << 10 for row in suffix)
    character_rows = [
        row["full"] for row in suffix if row["full"]["character_birth"] is not None
    ]
    assert [row["id"] for row in character_rows] == list(range(first_id, first_id + 3))
    assert sum(row["active"] and row["is_alive"] for row in character_rows) == 1
    assert sum(not row["active"] and not row["is_alive"] for row in character_rows) == 2


def test_private_delta_consumer_is_authorized_and_mutually_single_use() -> None:
    battle = BattleState(rng=random.Random(70_012), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    prepared = prior.fork().prepare_publication(prior)

    with pytest.raises(TypeError, match="runtime-owned"):
        prepared._consume_delta_parts(object())
    assert prepared.parts()["version"] == 1
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared._consume_delta_parts(_PREPARED_PUBLICATION_DELTA_CONSUMER)

    prepared = prior.fork().prepare_publication(prior)
    assert (
        prepared._consume_delta_parts(_PREPARED_PUBLICATION_DELTA_CONSUMER)["version"]
        == 1
    )
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared._consume_raw_parts(_PREPARED_PUBLICATION_RAW_CONSUMER)


def test_private_delta_carries_idle_eligibility_when_action_disables_idle() -> None:
    battle = BattleState(rng=random.Random(70_014), fast_path=True)
    battle.players[0].hand[0] = "Minions"
    battle.players[0].elixir = battle.players[0].max_elixir
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 10, 8, 0)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action,
        action_space.no_op_action,
        0,
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    assert prior.supports_idle_ticks
    assert not candidate.supports_idle_ticks

    prior_full = _full_parts(prior.fork(), prior)
    candidate_full = _full_parts(candidate, prior)
    delta = _delta_parts(candidate, prior)
    assert delta["dirty_mask"] & 1
    assert delta["idle_eligible"] is False
    reconstructed, idle_eligible = _reconstruct_prepared_publication_delta(
        prior_full,
        delta,
        prior_idle_eligible=prior.supports_idle_ticks,
    )
    _assert_bit_exact(reconstructed, candidate_full)
    assert idle_eligible is False


@pytest.mark.parametrize(
    "field",
    [
        "lineage_id",
        "prior_node_id",
        "prior_epoch",
        "checkpoint_generation",
        "catalog_fingerprint",
        "prior_entity_ids",
        "prior_next_entity_id",
    ],
)
def test_private_delta_reconstructor_rejects_wrong_prior_binding(field: str) -> None:
    battle = BattleState(rng=random.Random(70_015), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    prior_full = _full_parts(prior.fork(), prior)
    delta = _delta_parts(candidate, prior)
    value = delta["binding"][field]
    if field == "catalog_fingerprint":
        delta["binding"][field] = "0" * 64
    elif field == "prior_entity_ids":
        delta["binding"][field] = list(reversed(value))
    else:
        delta["binding"][field] = value + 1

    with pytest.raises(ValueError, match="binding|next entity"):
        _reconstruct_prepared_publication_delta(
            prior_full,
            delta,
            prior_idle_eligible=prior.supports_idle_ticks,
        )


def test_bit_exact_assertion_rejects_nan_payload_and_signed_zero_drift() -> None:
    nan_a = struct.unpack(">d", bytes.fromhex("7ff8000000000001"))[0]
    nan_b = struct.unpack(">d", bytes.fromhex("7ff8000000000002"))[0]
    _assert_bit_exact(
        {"dynamic": [nan_a, 0.0], "static": (nan_a, None)},
        {"dynamic": [nan_a, 0.0], "static": (nan_a, None)},
    )
    with pytest.raises(AssertionError):
        _assert_bit_exact(
            {"dynamic": [nan_b, 0.0], "static": (nan_a, None)},
            {"dynamic": [nan_a, 0.0], "static": (nan_a, None)},
        )
    with pytest.raises(AssertionError):
        _assert_bit_exact(
            {"dynamic": [nan_a, -0.0], "static": (nan_a, None)},
            {"dynamic": [nan_a, 0.0], "static": (nan_a, None)},
        )


def test_private_delta_reconstructor_rejects_malformed_entity_payload() -> None:
    battle = BattleState(rng=random.Random(70_013), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    prior_full = _full_parts(prior.fork(), prior)
    delta = _delta_parts(candidate, prior)
    change = next(row for row in delta["entities"] if row["dirty_mask"] & (1 << 5))
    change["locked_combat_state"] = None

    with pytest.raises(ValueError, match="disagrees with presence"):
        _reconstruct_prepared_publication_delta(
            prior_full,
            delta,
            prior_idle_eligible=prior.supports_idle_ticks,
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
    native_best_parts = prepared_type.best_parts
    crossings = 0

    def counted_parts(native: Any) -> Any:
        nonlocal crossings
        crossings += 1
        return native_best_parts(native)

    monkeypatch.setattr(prepared_type, "best_parts", counted_parts)
    monkeypatch.setattr(
        prepared_type,
        "parts",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("full prepared parts called")
        ),
    )
    monkeypatch.setattr(
        prepared_type,
        "delta_parts",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("standalone delta parts called")
        ),
    )
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


def test_native_best_selector_uses_delta_for_common_and_full_for_arrows() -> None:
    scenarios = _prepared_scenarios()
    common = [scenarios[0]]
    battle32 = BattleState(rng=random.Random(70_020), fast_path=True)
    prior32 = ResidentRustBattle.from_battle(battle32)
    candidate32 = prior32.fork()
    assert candidate32.advance_complete_ticks(32) == 32
    common.append((battle32, prior32, candidate32))
    for _battle, prior, candidate in common:
        envelope = candidate.prepare_publication(prior)._consume_best_parts(
            _PREPARED_PUBLICATION_BEST_CONSUMER
        )
        assert envelope["kind"] == 1
        assert envelope["full"] is None
        assert type(envelope["delta"]) is dict

    _battle, prior, candidate = scenarios[5]
    envelope = candidate.prepare_publication(prior)._consume_best_parts(
        _PREPARED_PUBLICATION_BEST_CONSUMER
    )
    assert envelope["kind"] == 0
    assert type(envelope["full"]) is dict
    assert envelope["delta"] is None
    standalone_full = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    _assert_bit_exact(envelope["full"], standalone_full)


def test_native_best_delta_matches_standalone_shared_selection() -> None:
    battle, prior, candidate = _prepared_scenarios()[0]
    envelope = candidate.prepare_publication(prior)._consume_best_parts(
        _PREPARED_PUBLICATION_BEST_CONSUMER
    )
    standalone = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    assert envelope["kind"] == 1
    _assert_bit_exact(envelope["delta"], standalone)

    plan = _build_direct_delta_publication_plan(
        envelope["delta"],
        battle=battle,
        resident=candidate,
        entity_registry=dict(battle.entities),
    )
    assert plan.active_entity_ids == tuple(battle.entities)


def test_empty_delta_publication_does_not_touch_clean_identity_graph() -> None:
    battle = BattleState(rng=random.Random(70_021), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    registry = dict(battle.entities)
    identities = {
        "entities": id(battle.entities),
        "rng": id(battle.rng),
        "pending": id(battle._pending_spell_casts),
        "hands": tuple(id(player.hand) for player in battle.players),
        "queues": tuple(id(player.cycle_queue) for player in battle.players),
        "positions": tuple(id(entity.position) for entity in registry.values()),
    }
    rng_state = battle.rng.getstate()

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert id(battle.entities) == identities["entities"]
    assert id(battle.rng) == identities["rng"]
    assert id(battle._pending_spell_casts) == identities["pending"]
    assert tuple(id(player.hand) for player in battle.players) == identities["hands"]
    assert tuple(id(player.cycle_queue) for player in battle.players) == identities["queues"]
    assert tuple(id(entity.position) for entity in registry.values()) == identities[
        "positions"
    ]
    assert battle.rng.getstate() == rng_state


def test_movement_only_river_jump_refreshes_air_cache_and_continues_exactly() -> None:
    battle = BattleState(rng=random.Random(70_023), fast_path=True)
    jumper = _spawn_ready(battle, "HogRider", 0, Position(9.0, 14.0))
    jumper._movement_target_id = 6
    battle._refresh_fast_path_caches()
    control = battle.clone()
    registry = dict(battle.entities)
    prior = ResidentRustBattle.from_battle(battle)

    for _ in range(11):
        candidate = prior.fork()
        candidate.advance_ground_movement_phase()
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )
        _advance_python_movement(control)
        assert python_resident_semantic_snapshot(battle) == (
            python_resident_semantic_snapshot(control)
        )
        prior = candidate

    before_position = (jumper.position.x, jumper.position.y)
    candidate = prior.fork()
    candidate.advance_ground_movement_phase()
    delta = _delta_parts(candidate, prior)
    change = next(row for row in delta["entities"] if row["id"] == jumper.id)
    assert change["dirty_mask"] & (1 << 4)
    assert not change["dirty_mask"] & (1 << 1)
    plan = _build_direct_delta_publication_plan(
        delta,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    assert plan.battle is None
    assert plan.cache_dirty

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    _advance_python_movement(control)
    assert (jumper.position.x, jumper.position.y) == before_position
    assert jumper._river_jump_active
    target_index = battle._target_index_by_id[jumper.id]
    assert bool(battle._target_is_air[target_index])
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )

    prior = candidate
    candidate = prior.fork()
    candidate.advance_ground_movement_phase()
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    _advance_python_movement(control)
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    target_index = battle._target_index_by_id[jumper.id]
    assert bool(battle._target_is_air[target_index])


def test_combat_delta_refreshes_distance_discount_cache() -> None:
    battle = BattleState(rng=random.Random(70_024), fast_path=True)
    tower = battle.entities[1]
    tower._native_target_distance_discount_sq_units = 6_400
    battle.sync_fast_target_static_entity(tower)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(8) == 8
    delta = _delta_parts(candidate, prior)
    change = next(row for row in delta["entities"] if row["id"] == tower.id)
    assert change["dirty_mask"] & (1 << 5)
    assert not change["dirty_mask"] & (1 << 1)
    registry = dict(battle.entities)
    plan = _build_direct_delta_publication_plan(
        delta,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    assert plan.cache_dirty

    target_index = battle._target_index_by_id[tower.id]
    battle._target_distance_discount_sq[target_index] = 123.0
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    target_index = battle._target_index_by_id[tower.id]
    assert battle._target_distance_discount_sq[target_index] == pytest.approx(0.0064)


def test_spawn_angle_is_static_prefix_and_rejected_from_delta_base() -> None:
    battle = BattleState(rng=random.Random(70_025), fast_path=True)
    troop = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    troop.card_stats.spawn_angle_shift = 0.125
    troop._movement_target_id = 6
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    candidate.advance_ground_movement_phase()
    full = _full_parts(candidate, prior)
    full_row = next(row for row in full["entities"] if row["id"] == troop.id)
    assert struct.pack(">d", full_row["spawn_angle_shift"]) == struct.pack(
        ">d", 0.125
    )

    delta = _delta_parts(candidate, prior)
    change = next(row for row in delta["entities"] if row["id"] == troop.id)
    assert change["base"] is not None
    assert "spawn_angle_shift" not in change["base"]
    change["base"]["spawn_angle_shift"] = 0.125
    with pytest.raises(ResidentPublicationError, match="keys|delta base|malformed"):
        _build_direct_delta_publication_plan(
            delta,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    action_battle, action_prior, action_candidate = _prepared_scenarios()[4]
    action_delta = _delta_parts(action_candidate, action_prior)
    births = [
        row["full"]
        for row in action_delta["entities"]
        if row["dirty_mask"] == 1 << 10
    ]
    assert births
    assert all(type(row["spawn_angle_shift"]) is float for row in births)
    assert action_battle.next_entity_id == action_prior.next_entity_id


def test_delta_next_entity_id_requires_battle_payload_and_is_always_postchecked() -> None:
    battle, prior, candidate = _prepared_scenarios()[4]
    delta = _delta_parts(candidate, prior)
    assert delta["next_entity_id"] > delta["binding"]["prior_next_entity_id"]
    assert delta["dirty_mask"] & 1
    delta["dirty_mask"] &= ~1
    delta["battle"] = None
    delta["idle_eligible"] = None
    with pytest.raises(ResidentPublicationError, match="next id.*battle payload"):
        _build_direct_delta_publication_plan(
            delta,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    empty_battle = BattleState(rng=random.Random(70_026), fast_path=True)
    empty_prior = ResidentRustBattle.from_battle(empty_battle)
    empty_candidate = empty_prior.fork()
    empty_plan = _build_direct_delta_publication_plan(
        _delta_parts(empty_candidate, empty_prior),
        battle=empty_battle,
        resident=empty_candidate,
        entity_registry=dict(empty_battle.entities),
    )
    empty_battle.next_entity_id += 1
    with pytest.raises(ResidentPublicationError, match="root state was not applied"):
        _require_live_application_shape(
            empty_battle, empty_plan, dict(empty_battle.entities)
        )


def test_cache_dirty_root_clean_failure_restores_exact_battle_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(70_027), fast_path=True)
    troop = _spawn_ready(battle, "HogRider", 0, Position(9.0, 14.0))
    troop._movement_target_id = 6
    battle._refresh_fast_path_caches()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    candidate.advance_ground_movement_phase()
    delta = _delta_parts(candidate, prior)
    registry = dict(battle.entities)
    plan = _build_direct_delta_publication_plan(
        delta,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    assert plan.battle is None
    assert plan.cache_dirty
    before_battle = _identity_projection(vars(battle))
    before_entities = {
        entity_id: _identity_projection(vars(entity))
        for entity_id, entity in registry.items()
    }
    before_semantic = python_resident_semantic_snapshot(battle)

    def reject_commit(*_args: Any, **_kwargs: Any) -> None:
        raise ResidentPublicationError("injected cache-dirty commit failure")

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

    assert _identity_projection(vars(battle)) == before_battle
    assert {
        entity_id: _identity_projection(vars(entity))
        for entity_id, entity in registry.items()
    } == before_entities
    assert python_resident_semantic_snapshot(battle) == before_semantic


@pytest.mark.parametrize(
    "tamper",
    (
        "root_unknown_bit",
        "root_missing_players",
        "entity_unknown_bit",
        "entity_missing_combat",
        "entity_bool_exact",
    ),
)
def test_direct_delta_plan_rejects_category_tamper_before_live_mutation(
    tamper: str,
) -> None:
    battle = BattleState(rng=random.Random(70_022), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(8) == 8
    delta = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    before = tuple(battle.entities.items())
    if tamper == "root_unknown_bit":
        delta["dirty_mask"] |= 1 << 63
    elif tamper == "root_missing_players":
        assert delta["dirty_mask"] & (1 << 1)
        delta["players"] = None
    else:
        change = next(row for row in delta["entities"] if row["dirty_mask"] & (1 << 5))
        if tamper == "entity_unknown_bit":
            change["dirty_mask"] |= 1 << 63
        elif tamper == "entity_missing_combat":
            change["locked_combat_state"] = None
        else:
            change["locked_combat_state"]["attack_cooldown"] = True

    with pytest.raises(ResidentPublicationError, match="delta|mask|combat|publication"):
        _build_direct_delta_publication_plan(
            delta,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )
    assert tuple(battle.entities.items()) == before


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
        prepared_type = type(candidate.prepare_publication(prior)._native)
        native_best = prepared_type.best_parts
        native_full = prepared_type.parts

        def mutate_then_build(raw: Any, **kwargs: Any) -> Any:
            mutate(raw)
            return original_build(raw, **kwargs)

        monkeypatch.setattr(
            rust_publication,
            "_build_direct_publication_plan",
            mutate_then_build,
        )
        monkeypatch.setattr(
            prepared_type,
            "best_parts",
            lambda native: {
                "version": 1,
                "kind": 0,
                "full": native_full(native),
                "delta": None,
            },
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
        monkeypatch.setattr(prepared_type, "best_parts", native_best)

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
