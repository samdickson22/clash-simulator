from __future__ import annotations

import copy
import json
import random
from dataclasses import replace

import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.tesla import HideWhenIdle
from clasher.differential import canonical_battle_snapshot
from clasher.entities import Building, Troop
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
    _ENTITY_SPARSE_ATTRIBUTE_NAMES,
    ResidentPublicationError,
    _build_direct_delta_publication_plan,
    _build_direct_publication_plan,
    publish_complete_tick_state,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)


def _spawn_tesla(
    battle: BattleState,
    position: Position | None = None,
    *,
    player_id: int = 0,
) -> Building:
    if position is None:
        position = Position(9.0, 16.0)
    stats = battle.card_loader.get_card("Tesla")
    assert stats is not None
    entity = battle._spawn_entity(Building, position, player_id, stats)
    assert type(entity) is Building
    return entity


def _ready(entity: Building | Troop) -> None:
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.on_spawn()


def _hide(entity: Building) -> HideWhenIdle:
    return next(
        mechanic
        for mechanic in entity.mechanics
        if type(mechanic) is HideWhenIdle
    )


def _advance_and_publish(
    battle: BattleState,
    control: BattleState,
    resident: ResidentRustBattle,
    ticks: int,
) -> ResidentRustBattle:
    prior = resident
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(ticks) == ticks
    assert control.step_logic_ticks(ticks) == ticks
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=dict(battle.entities),
    )
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert rust_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    return candidate


def test_hide_when_idle_catalog_closure_is_structural_and_exact() -> None:
    battle = BattleState()
    definitions = battle.card_loader.load_card_definitions()
    hide_lookups = {
        name
        for name, definition in definitions.items()
        if any(type(mechanic) is HideWhenIdle for mechanic in definition.mechanics)
    }
    resident = ResidentRustBattle.from_battle(battle)

    assert hide_lookups == {"Tesla"}
    assert hide_lookups <= set(resident.resident_supported_action_cards())

    prototype = _spawn_tesla(BattleState())
    mechanic = _hide(prototype)
    assert (mechanic.hide_delay_ms, mechanic.rise_time_ms, mechanic._phase_ms) == (
        800,
        800,
        0.0,
    )
    assert prototype.__dict__["_hidden_building"] is False
    assert prototype._special_move_active is False

    stats = battle.card_loader.get_card("Tesla")
    assert stats is not None
    for timing_field in ("hide_delay_ms", "rise_time_ms"):
        near_match = copy.deepcopy(definitions["Tesla"])
        setattr(_hide(near_match), timing_field, 0)
        assert "invalid_hide_when_idle" in rust_core._ordinary_building_capability_reasons(
            stats, near_match
        )


def test_hide_when_idle_deploy_crossing_and_boundaries_publish_in_place() -> None:
    battle = BattleState(rng=random.Random(181_001), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn_tesla(battle)
    tesla.deploy_delay_remaining = battle.dt
    tesla.placement_delay_total = battle.dt
    tesla.placement_pending = True
    tesla._spawn_hook_pending = True
    tesla._spawn_hook_fired = False
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    mechanic = _hide(tesla)
    mechanic_identity = id(mechanic)

    resident = _advance_and_publish(battle, control, resident, 1)
    assert _hide(battle.entities[tesla.id])._phase_ms == 50.0
    assert battle.entities[tesla.id]._hidden_building is False

    resident = _advance_and_publish(battle, control, resident, 15)
    assert _hide(battle.entities[tesla.id])._phase_ms == 800.0
    assert battle.entities[tesla.id]._hidden_building is True
    assert battle.entities[tesla.id]._special_move_active is True
    assert battle.entities[tesla.id].target_id is None
    assert id(_hide(battle.entities[tesla.id])) == mechanic_identity

    # A target in strict attack reach is acquired in combat and causes the
    # exact hidden boundary to advance into Tesla's rise half in object phase.
    target_stats = battle.card_loader.get_card("Knight")
    assert target_stats is not None
    control_target_stats = control.card_loader.get_card("Knight")
    assert control_target_stats is not None
    target = battle._spawn_entity(
        Troop,
        Position(tesla.position.x, tesla.position.y + 2.0),
        1,
        target_stats,
    )
    control_target = control._spawn_entity(
        Troop,
        Position(tesla.position.x, tesla.position.y + 2.0),
        1,
        control_target_stats,
    )
    assert target.id == control_target.id
    _ready(target)
    _ready(control_target)

    # Recompile the resident because the target was intentionally added at the
    # Python boundary; this test's publication assertion starts from that state.
    resident = ResidentRustBattle.from_battle(battle)
    resident = _advance_and_publish(battle, control, resident, 1)
    assert battle.entities[tesla.id]._hidden_building is False
    assert _hide(battle.entities[tesla.id])._phase_ms == 850.0
    assert id(_hide(battle.entities[tesla.id])) == mechanic_identity

    resident = _advance_and_publish(battle, control, resident, 15)
    assert _hide(battle.entities[tesla.id])._phase_ms == 0.0
    assert battle.entities[tesla.id]._hidden_building is False


def test_hide_when_idle_preserves_raw_nonintegral_tick_work() -> None:
    battle = BattleState(rng=random.Random(181_006), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    battle.dt = 0.0333
    tesla = _spawn_tesla(battle)
    _ready(tesla)
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_tick()
    control._step_logic_tick(refresh_fast_path_end=False)

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    assert _hide(control.entities[tesla.id])._phase_ms == pytest.approx(33.3)


@pytest.mark.parametrize("attribute", ["_hidden_building", "_special_move_active"])
def test_hide_when_idle_hydration_requires_sparse_attributes(attribute: str) -> None:
    battle = BattleState(rng=random.Random(181_007), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn_tesla(battle)
    _ready(tesla)
    del tesla.__dict__[attribute]

    with pytest.raises(ValueError, match="requires explicit hidden and special-move"):
        ResidentRustBattle.from_battle(battle)


@pytest.mark.parametrize("attribute", ["_hidden_building", "_special_move_active"])
@pytest.mark.parametrize("payload_kind", ["full", "delta"])
def test_hide_when_idle_publication_rejects_sparse_mask_tamper_before_live_write(
    attribute: str,
    payload_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(181_008), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn_tesla(battle)
    _ready(tesla)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_tick()
    registry = dict(battle.entities)
    before = canonical_battle_snapshot(battle)
    bit = 1 << _ENTITY_SPARSE_ATTRIBUTE_NAMES.index(attribute)
    full = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    full_row = next(row for row in full["entities"] if row["id"] == tesla.id)

    if payload_kind == "full":
        raw = copy.deepcopy(full)
        row = next(row for row in raw["entities"] if row["id"] == tesla.id)
        row["sparse_attribute_presence"] &= ~bit
        builder = _build_direct_publication_plan
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        raw = copy.deepcopy(raw)
        change = next(row for row in raw["entities"] if row["id"] == tesla.id)
        change["dirty_mask"] |= 1
        change["sparse_attribute_presence"] = (
            full_row["sparse_attribute_presence"] & ~bit
        )
        builder = _build_direct_delta_publication_plan

    with pytest.raises(ResidentPublicationError, match="sparse topology"):
        builder(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=registry,
        )
    assert canonical_battle_snapshot(battle) == before


def test_hidden_tesla_rejects_zap_damage_and_status() -> None:
    battle = BattleState(rng=random.Random(181_002), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn_tesla(battle, Position(9.5, 21.5), player_id=1)
    _ready(tesla)
    # Isolate spell immunity from Tesla's independent intrinsic lifetime loss.
    tesla.card_stats.lifetime_ms = None
    mechanic = _hide(tesla)
    mechanic._phase_ms = float(mechanic.hide_delay_ms)
    tesla._hidden_building = True
    tesla._special_move_active = True
    tesla.target_id = None
    battle.players[0].hand[0] = "Zap"
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 21, 0)

    order = [0, 1]
    control.rng.shuffle(order)
    control_successes: dict[int, bool] = {}
    actions = (action, action_space.no_op_action)
    for player_id in order:
        control_successes[player_id] = action_space.apply_action(
            control, player_id, actions[player_id]
        )
    successes, _order = resident.apply_resident_joint_actions(
        action, action_space.no_op_action
    )
    assert successes == control_successes
    hp_before = tesla.hitpoints

    candidate = resident.fork()
    assert candidate.advance_complete_ticks(20) == 20
    assert control.step_logic_ticks(20) == 20
    assert rust_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    current = control.entities[tesla.id]
    assert current.hitpoints == hp_before
    assert current.stun_timer == 0.0


def test_tesla_action_ingress_and_deploy_tick_match_and_publish() -> None:
    battle = BattleState(rng=random.Random(181_005), fast_path=True)
    battle.players[0].hand[0] = "Tesla"
    battle.players[0].elixir = battle.players[0].max_elixir
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )
    order = [0, 1]
    control.rng.shuffle(order)
    control_successes: dict[int, bool] = {}
    for player_id in order:
        control_successes[player_id] = action_space.apply_action(
            control, player_id, actions[player_id]
        )

    successes, native_order = candidate.apply_resident_joint_actions(*actions)
    assert successes == control_successes
    assert native_order == tuple(order)
    assert candidate.advance_complete_ticks(20) == 20
    assert control.step_logic_ticks(20) == 20
    assert rust_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )

    registry = dict(battle.entities)
    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    born = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id >= prior.next_entity_id
        and type(entity) is Building
        and entity.card_stats.name == "Tesla"
    )
    assert _hide(born)._phase_ms == 50.0
    assert born._hidden_building is False
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )


@pytest.mark.parametrize("timing_field", ["hide_delay_ms", "rise_time_ms"])
def test_hide_when_idle_catalog_tamper_rejects_before_action_mutation(
    monkeypatch: pytest.MonkeyPatch,
    timing_field: str,
) -> None:
    battle = BattleState(rng=random.Random(181_003), fast_path=True)
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(item for item in payload["cards"] if item["lookup_name"] == "Tesla")
    mechanic = next(
        row
        for row in card["template_snapshot"]["$object"]["fields"]["mechanics"]
        if row["$object"]["type"] == "clasher.cards.tesla.HideWhenIdle"
    )
    mechanic["$object"]["fields"][timing_field] = 0
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
    battle.players[0].hand[0] = "Tesla"
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )

    assert any(
        reason.startswith("template_parse")
        for reason in resident.resident_action_card_capability_reasons("Tesla")
    )
    action = DiscreteTileActionSpace().encode_action(0, 8, 10, 0)
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(action, 2304)
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    ) == before


def test_hide_when_idle_delta_failure_restores_mechanic_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(181_004), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = _spawn_tesla(battle)
    _ready(tesla)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(8) == 8
    mechanic = _hide(tesla)
    mechanic_before = dict(vars(mechanic))
    canonical_before = canonical_battle_snapshot(battle)
    registry = dict(battle.entities)

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected HideWhenIdle commit failure")

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

    assert canonical_battle_snapshot(battle) == canonical_before
    assert _hide(battle.entities[tesla.id]) is mechanic
    assert vars(mechanic) == mechanic_before
