from __future__ import annotations

import copy
import hashlib
import json
import random
from collections import deque
from typing import Any

import numpy as np
import pytest

from clasher import rust_core
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import (
    canonical_battle_snapshot,
    first_snapshot_difference,
    snapshot_bytes,
)
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
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
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, _causal_boundary_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)

SUPPORTED_DECK = (
    "IceSpirit",
    "Knight",
    "Archers",
    "Minions",
    "Musketeer",
    "Giant",
    "MiniPekka",
    "Arrows",
)


def _set_supported_decks(battle: BattleState) -> None:
    for player in battle.players:
        player.hand = list(SUPPORTED_DECK[:4])
        player.cycle_queue = deque(SUPPORTED_DECK[4:])
        player.elixir = player.max_elixir


def _spawn_ready(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    card = battle.card_loader.get_card(card_name)
    assert card is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, card)
    entity = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and type(entity) is Troop
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 0.0
    entity._attack_windup_active = True
    return entity


def _ready_interaction() -> BattleState:
    battle = BattleState(rng=random.Random(12345), fast_path=True)
    _spawn_ready(battle, "IceSpirit", 0, Position(9, 12))
    _spawn_ready(battle, "Knight", 1, Position(9, 14))
    return battle


def _river_status_interaction() -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(rng=random.Random(20_001), fast_path=True)
    jumper = _spawn_ready(battle, "HogRider", 0, Position(9, 14.9))
    spirit = _spawn_ready(battle, "IceSpirit", 1, Position(9, 16.0))
    jumper.target_id = 6
    jumper._last_combat_target_id = 6
    jumper.attack_cooldown = 0.25
    jumper._attack_windup_active = True
    assert jumper._try_start_river_jump(
        battle.entities[6].position,
        Position(9, battle.arena.RIVER_Y1),
        battle,
    )
    spirit.target_id = jumper.id
    spirit._last_combat_target_id = jumper.id
    return battle, jumper, spirit


def test_status_nova_catalog_qualification_is_data_driven() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())

    assert resident.resident_action_card_capability_reasons("IceSpirit") == ()
    assert resident.resident_action_card_capability_reasons("IceSpirits") == ()
    for card_name in ("ElectroSpirit", "FireSpirits", "Heal", "Wallbreakers"):
        assert resident.resident_action_card_capability_reasons(card_name)


def test_status_nova_catalog_rejects_nonhoming_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "IceSpirit"
    )
    fields = card["template_snapshot"]["$object"]["fields"]
    projectile = fields["card_stats"]["$object"]["fields"]["projectile_data"]
    next(
        item for item in projectile["$mapping"] if item[0] == "homing"
    )[1] = False
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)

    _set_supported_decks(battle)
    battle.players[0].hand[0] = "IceSpirit"
    resident = ResidentRustBattle.from_battle(battle)

    reasons = resident.resident_action_card_capability_reasons("IceSpirit")
    assert any(reason.startswith("template_parse:") for reason in reasons)
    state_before = rust_resident_semantic_snapshot(resident)
    rng_before = resident.rng_state_bytes()
    action = DiscreteTileActionSpace().encode_action(0, 8, 10, 0)
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(
            action, DiscreteTileActionSpace().no_op_action
        )
    assert rust_resident_semantic_snapshot(resident) == state_before
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize("affects_hidden", [None, True])
def test_status_nova_catalog_accepts_strict_affects_hidden_payload(
    monkeypatch: pytest.MonkeyPatch,
    affects_hidden: bool | None,
) -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "IceSpirit"
    )
    fields = card["template_snapshot"]["$object"]["fields"]
    projectile = fields["card_stats"]["$object"]["fields"]["projectile_data"]
    projectile["$mapping"].append(["affectsHidden", affects_hidden])
    projectile["$mapping"].sort(key=lambda item: item[0])
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)

    resident = ResidentRustBattle.from_battle(battle)

    assert resident.resident_action_card_capability_reasons("IceSpirit") == ()


@pytest.mark.parametrize("invalid_value", [1, "true"])
def test_status_nova_catalog_rejects_nonboolean_affects_hidden(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: object,
) -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "IceSpirit"
    )
    fields = card["template_snapshot"]["$object"]["fields"]
    projectile = fields["card_stats"]["$object"]["fields"]["projectile_data"]
    projectile["$mapping"].append(["affectsHidden", invalid_value])
    projectile["$mapping"].sort(key=lambda item: item[0])
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)

    _set_supported_decks(battle)
    battle.players[0].hand[0] = "IceSpirit"
    resident = ResidentRustBattle.from_battle(battle)

    reasons = resident.resident_action_card_capability_reasons("IceSpirit")
    assert any(reason.startswith("template_parse:") for reason in reasons)
    state_before = rust_resident_semantic_snapshot(resident)
    rng_before = resident.rng_state_bytes()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 10, 0)
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(action, action_space.no_op_action)
    assert rust_resident_semantic_snapshot(resident) == state_before
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize("player_id", [0, 1])
def test_status_nova_action_legal_ids_match_scalar_and_fast(player_id: int) -> None:
    battle = BattleState(fast_path=True)
    _set_supported_decks(battle)
    battle.players[player_id].hand[0] = "IceSpirit"
    action_space = DiscreteTileActionSpace()
    resident = ResidentRustBattle.from_battle(battle)

    scalar = np.flatnonzero(
        action_space.legal_action_mask(battle, player_id, fast_path=False)
    )
    fast = np.flatnonzero(
        action_space.legal_action_mask(battle, player_id, fast_path=True)
    )
    native = np.asarray(resident.resident_legal_action_ids(player_id))

    np.testing.assert_array_equal(fast, scalar)
    np.testing.assert_array_equal(native, scalar)


def test_status_nova_complete_tick_trace_matches_python() -> None:
    battle = _ready_interaction()
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for tick in range(1, 10):
        assert control.step_logic_ticks(1) == 1
        assert resident.advance_complete_ticks(1) == 1
        difference = first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        )
        assert difference is None, f"tick {tick}: {difference}"

    target = next(
        entity
        for entity in control.entities.values()
        if type(entity) is Troop and entity.player_id == 1
    )
    assert target.hitpoints < target.max_hitpoints
    assert target.stun_timer > 0.0
    assert all(
        not (
            type(entity) is Troop
            and entity.player_id == 0
            and entity.card_stats.name == "IceSpirits"
        )
        for entity in control.entities.values()
    )


def test_status_nova_action_ingress_and_continuation_match_python() -> None:
    battle = BattleState(rng=random.Random(95100), fast_path=True)
    _set_supported_decks(battle)
    _spawn_ready(battle, "Knight", 1, Position(8.5, 14.5))
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )
    resident = ResidentRustBattle.from_battle(battle)
    order = [0, 1]
    control.rng.shuffle(order)
    expected = {
        player_id: action_space.apply_action(
            control, player_id, actions[player_id]
        )
        for player_id in order
    }

    actual, actual_order = resident.apply_resident_joint_actions(*actions)
    assert actual == expected == {0: True, 1: True}
    assert actual_order == tuple(order)
    for tick in range(1, 36):
        assert control.step_logic_ticks(1) == 1
        assert resident.advance_complete_ticks(1) == 1
        difference = first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        )
        assert difference is None, f"tick {tick}: {difference}"


def test_status_nova_retains_destination_after_primary_cleanup() -> None:
    battle = BattleState(rng=random.Random(99), fast_path=True)
    spirit = _spawn_ready(battle, "IceSpirit", 0, Position(9, 12))
    killer = _spawn_ready(battle, "Knight", 0, Position(9, 13.5))
    primary = _spawn_ready(battle, "Knight", 1, Position(9, 14))
    secondary = _spawn_ready(battle, "Knight", 1, Position(10, 14))
    killer.damage = primary.hitpoints
    killer.target_id = primary.id
    killer._last_combat_target_id = primary.id
    spirit_id = spirit.id
    primary_id = primary.id
    secondary_id = secondary.id
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for tick in range(1, 8):
        control.step_logic_ticks(1)
        resident.advance_complete_ticks(1)
        difference = first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        )
        assert difference is None, f"tick {tick}: {difference}"

    assert primary_id not in control.entities
    assert spirit_id not in control.entities
    surviving_secondary = control.entities[secondary_id]
    assert surviving_secondary.hitpoints < surviving_secondary.max_hitpoints
    assert surviving_secondary.stun_timer > 0.0


def test_status_nova_damage_pass_precedes_death_spawn_status_pass() -> None:
    battle = BattleState(rng=random.Random(888), fast_path=True)
    spirit = _spawn_ready(battle, "IceSpirit", 0, Position(9, 12))
    golem = _spawn_ready(battle, "Golem", 1, Position(9, 14))
    golem.hitpoints = spirit.damage
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for tick in range(1, 9):
        control.step_logic_ticks(1)
        resident.advance_complete_ticks(1)
        difference = first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        )
        assert difference is None, f"tick {tick}: {difference}"

    golemites = [
        entity
        for entity in control.entities.values()
        if type(entity) is Troop and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(entity.stun_timer == 0.0 for entity in golemites)


@pytest.mark.parametrize("allow_invisible", [False, True])
def test_status_nova_affects_hidden_does_not_bypass_troop_stealth(
    allow_invisible: bool,
) -> None:
    battle = BattleState(rng=random.Random(889), fast_path=True)
    spirit = _spawn_ready(battle, "IceSpirit", 0, Position(9, 12))
    primary = _spawn_ready(battle, "Knight", 1, Position(9, 14))
    invisible = _spawn_ready(battle, "Knight", 1, Position(10, 14))
    spirit.card_stats = copy.deepcopy(spirit.card_stats)
    spirit.card_stats.projectile_data["affectsHidden"] = True
    invisible.card_stats = copy.deepcopy(invisible.card_stats)
    invisible.card_stats.allow_area_damage_when_invisible = allow_invisible
    invisible._stealth_until = 100_000
    spirit.target_id = primary.id
    spirit._last_combat_target_id = primary.id
    invisible_hp = invisible.hitpoints
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for tick in range(1, 10):
        assert control.step_logic_ticks(1) == 1
        assert resident.advance_complete_ticks(1) == 1
        assert first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        ) is None, tick

    control_invisible = control.entities[invisible.id]
    if allow_invisible:
        assert control_invisible.hitpoints < invisible_hp
        assert control_invisible.stun_timer > 0.0
    else:
        assert control_invisible.hitpoints == invisible_hp
        assert control_invisible.stun_timer == 0.0


def test_status_nova_on_publication_preserves_causal_state_each_tick() -> None:
    battle = _ready_interaction()
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    registry: dict[int, object] = dict(battle.entities)

    for tick in range(1, 10):
        candidate = prior.fork()
        assert control.step_logic_ticks(1) == 1
        assert candidate.advance_complete_ticks(1) == 1
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )
        difference = first_snapshot_difference(
            _causal_boundary_snapshot(control),
            _causal_boundary_snapshot(battle),
        )
        assert difference is None, f"tick {tick}: {difference}"
        prior = candidate


def test_status_nova_action_birth_publishes_mid_jump_exactly() -> None:
    battle = BattleState(rng=random.Random(95100), fast_path=True)
    _set_supported_decks(battle)
    _spawn_ready(battle, "Knight", 1, Position(8.5, 14.5))
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    order = [0, 1]
    control.rng.shuffle(order)
    expected = {
        player_id: action_space.apply_action(
            control, player_id, actions[player_id]
        )
        for player_id in order
    }
    actual, actual_order = candidate.apply_resident_joint_actions(*actions)
    assert actual == expected == {0: True, 1: True}
    assert actual_order == tuple(order)
    assert candidate.advance_complete_ticks(28) == control.step_logic_ticks(28)
    registry: dict[int, object] = dict(battle.entities)

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert first_snapshot_difference(
        _causal_boundary_snapshot(control), _causal_boundary_snapshot(battle)
    ) is None
    published = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Troop and entity.player_id == 0
    )
    assert published._special_move_active
    assert published._ice_spirit_jump_target is not None
    assert published._ice_spirit_jump_origin is not None


def test_status_nova_off_shadow_on_fixed_seed_digests_match() -> None:
    battles = {mode: _ready_interaction() for mode in RustBattleMode}
    runtimes = {
        mode: ResidentCompleteTickRuntime(battle, mode)
        for mode, battle in battles.items()
    }

    for mode, runtime in runtimes.items():
        assert runtime.advance_ticks(9) == 9, mode

    digests = {
        mode: hashlib.sha256(
            snapshot_bytes(canonical_battle_snapshot(battle))
        ).hexdigest()
        for mode, battle in battles.items()
    }
    assert len(set(digests.values())) == 1
    assert runtimes[RustBattleMode.SHADOW].status.shadow_mismatches == 0


def test_status_nova_defers_river_jumper_stun_interruption_until_landing() -> None:
    battle, jumper, _spirit = _river_status_interaction()
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    registry: dict[int, Any] = dict(battle.entities)
    expected_rng = control.rng.getstate()
    saw_deferred = False
    saw_landing = False

    for tick in range(1, 31):
        candidate = prior.fork()
        assert control.step_logic_ticks(1) == 1
        assert candidate.advance_complete_ticks(1) == 1
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )
        assert first_snapshot_difference(
            _causal_boundary_snapshot(control), _causal_boundary_snapshot(battle)
        ) is None, tick
        assert battle.rng.getstate() == control.rng.getstate() == expected_rng
        if jumper._stun_interrupt_deferred_until_landing:
            saw_deferred = True
            assert jumper._river_jump_active
            assert jumper.target_id == 6
            assert jumper.attack_cooldown == 0.25
            assert jumper._attack_windup_active
        if saw_deferred and not jumper._river_jump_active:
            saw_landing = True
            assert not jumper._stun_interrupt_deferred_until_landing
            assert jumper.target_id is None
            assert not jumper._attack_windup_active
            break
        prior = candidate

    assert saw_deferred
    assert saw_landing


def test_expired_river_stun_remains_deferred_until_landing() -> None:
    battle = BattleState(rng=random.Random(20_003), fast_path=True)
    jumper = _spawn_ready(battle, "HogRider", 0, Position(9, 14.9))
    jumper.target_id = 6
    jumper._last_combat_target_id = 6
    jumper.attack_cooldown = 0.25
    jumper._attack_windup_active = True
    assert jumper._try_start_river_jump(
        battle.entities[6].position,
        Position(9, battle.arena.RIVER_Y1),
        battle,
    )
    jumper.apply_stun(0.1, source_kind="test")
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    saw_expired_deferred = False

    for tick in range(1, 31):
        assert control.step_logic_ticks(1) == 1
        assert resident.advance_complete_ticks(1) == 1
        assert first_snapshot_difference(
            python_resident_semantic_snapshot(control),
            rust_resident_semantic_snapshot(resident),
        ) is None, tick
        control_jumper = control.entities[jumper.id]
        if (
            control_jumper._river_jump_active
            and control_jumper.stun_timer == 0.0
            and control_jumper._stun_interrupt_deferred_until_landing
        ):
            saw_expired_deferred = True
        if not control_jumper._river_jump_active:
            assert not control_jumper._stun_interrupt_deferred_until_landing
            assert control_jumper.target_id == 6
            assert control_jumper.attack_cooldown == 0.25
            assert control_jumper._attack_windup_active
            break

    assert saw_expired_deferred


def test_status_nova_river_publication_failure_rolls_back_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle, _jumper, _spirit = _river_status_interaction()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(6) == 6
    registry: dict[int, Any] = dict(battle.entities)
    before = _causal_boundary_snapshot(battle)
    before_items = tuple(registry.items())
    before_rng = battle.rng.getstate()

    def reject_commit(*_args: Any, **_kwargs: Any) -> None:
        raise ResidentPublicationError("injected river-status publication failure")

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

    assert _causal_boundary_snapshot(battle) == before
    assert tuple(registry.items()) == before_items
    assert battle.rng.getstate() == before_rng


def test_status_nova_lethal_mover_skips_later_dead_movement_and_publishes_tombstone() -> None:
    battle = BattleState(rng=random.Random(20_002), fast_path=True)
    spirit = _spawn_ready(battle, "IceSpirit", 0, Position(9, 12))
    victim = _spawn_ready(battle, "Knight", 1, Position(9, 12.4))
    spirit.target_id = victim.id
    spirit._last_combat_target_id = victim.id
    victim.hitpoints = spirit.damage
    victim.attack_cooldown = 1.0
    victim._movement_target_id = 3
    victim._native_avoidance = 100
    victim.accumulate_movement_vector_units(200, 100)
    victim_id = victim.id
    victim_movement = (
        victim.position.x,
        victim.position.y,
        victim._movement_vector_x_units,
        victim._movement_vector_y_units,
        victim._native_avoidance,
    )
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    registry: dict[int, Any] = dict(battle.entities)

    assert control.step_logic_ticks(1) == 1
    assert candidate.advance_complete_ticks(1) == 1
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert first_snapshot_difference(
        _causal_boundary_snapshot(control), _causal_boundary_snapshot(battle)
    ) is None
    assert victim_id not in battle.entities
    assert registry[victim_id] is victim
    assert not victim.is_alive
    assert (
        victim.position.x,
        victim.position.y,
        victim._movement_vector_x_units,
        victim._movement_vector_y_units,
        victim._native_avoidance,
    ) == victim_movement


def test_status_nova_unknown_jump_target_fails_before_live_mutation() -> None:
    battle = _ready_interaction()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(1) == 1
    raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    row = next(row for row in raw["entities"] if row["status_nova_jump"])
    row["status_nova_jump"]["jump_target_id"] = max(battle.entities) + 10_000
    before = tuple(battle.entities.items())
    before_rng = battle.rng.getstate()

    with pytest.raises(ResidentPublicationError, match="unknown reference"):
        _build_direct_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert tuple(battle.entities.items()) == before
    assert battle.rng.getstate() == before_rng


def test_status_nova_delta_unknown_jump_target_fails_before_live_mutation() -> None:
    battle = _ready_interaction()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(1) == 1
    raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    change = next(
        change
        for change in raw["entities"]
        if change["base"] is not None
        and change["base"]["status_nova_jump"] is not None
    )
    change["base"]["status_nova_jump"]["jump_target_id"] = (
        max(battle.entities) + 10_000
    )
    before = tuple(battle.entities.items())
    before_rng = battle.rng.getstate()

    with pytest.raises(ResidentPublicationError, match="unknown reference"):
        _build_direct_delta_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert tuple(battle.entities.items()) == before
    assert battle.rng.getstate() == before_rng
