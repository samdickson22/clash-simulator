from __future__ import annotations

import json
import random
import sys
from collections import deque
from typing import Any

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.electro_spirit import ElectroSpiritChain
from clasher.cards.tesla import HideWhenIdle
from clasher.entities import Building, ChainLightning, Troop
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
    _typed_publication_projection,
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, _causal_boundary_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)


def _spawn_ready(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    card = battle.card_loader.get_card(card_name)
    assert card is not None
    prior_ids = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, card)
    entity = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in prior_ids and type(entity) is Troop
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 0.0
    entity._attack_windup_active = True
    return entity


def _chain_fixture() -> tuple[BattleState, Troop, tuple[Troop, Troop, Troop]]:
    battle = BattleState(rng=random.Random(115_000), fast_path=True)
    spirit = _spawn_ready(battle, "ElectroSpirit", 0, Position(9.0, 12.0))
    targets = (
        _spawn_ready(battle, "Knight", 1, Position(9.0, 13.2)),
        _spawn_ready(battle, "Knight", 1, Position(11.0, 13.2)),
        _spawn_ready(battle, "Knight", 1, Position(13.0, 13.2)),
    )
    return battle, spirit, targets


def _commit_electro_jump(spirit: Troop, target: Troop | Building) -> None:
    spirit.update_combat_component(spirit.battle_state.dt, spirit.battle_state)
    assert spirit.target_id == target.id
    assert spirit._special_move_active is True


def _ready_building(building: Building) -> None:
    building.deploy_delay_remaining = 0.0
    building.placement_delay_total = 0.0
    building.placement_pending = False
    building._spawn_hook_pending = False
    building._spawn_hook_fired = True
    building.on_spawn()


def test_electro_spirit_catalog_and_legal_masks_are_data_driven() -> None:
    battle = BattleState(fast_path=True)
    for player in battle.players:
        player.hand = ["ElectroSpirit", "Knight", "Archers", "Minions"]
        player.cycle_queue = deque(("Musketeer", "Giant", "MiniPekka", "Arrows"))
        player.elixir = player.max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()

    assert resident.resident_action_card_capability_reasons("ElectroSpirit") == ()
    for near_match in ("FireSpirits", "Heal", "BattleRam"):
        assert resident.resident_action_card_capability_reasons(near_match)
    for player_id in (0, 1):
        native = np.asarray(resident.resident_legal_action_ids(player_id))
        scalar = np.flatnonzero(
            action_space.legal_action_mask(battle, player_id, fast_path=False)
        )
        fast = np.flatnonzero(
            action_space.legal_action_mask(battle, player_id, fast_path=True)
        )
        np.testing.assert_array_equal(fast, scalar)
        np.testing.assert_array_equal(native, scalar)


@pytest.mark.parametrize("player_id", [0, 1])
def test_electro_action_ingress_matches_python_exactly(player_id: int) -> None:
    battle = BattleState(rng=random.Random(115_100 + player_id), fast_path=True)
    battle.players[player_id].hand = ["ElectroSpirit", None, None, None]
    battle.players[player_id].cycle_queue.clear()
    battle.players[player_id].elixir = battle.players[player_id].max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    world_y = 10 if player_id == 0 else 21
    action = action_space.encode_action(0, 8, world_y, player_id)
    actions = [action_space.no_op_action, action_space.no_op_action]
    actions[player_id] = action
    order = [0, 1]
    battle.rng.shuffle(order)
    expected = {
        ordered_player: action_space.apply_action(
            battle, ordered_player, actions[ordered_player]
        )
        for ordered_player in order
    }

    actual, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == tuple(order)
    assert actual == expected == {0: True, 1: True}
    assert resident.entity_state_bytes() == ResidentRustBattle.from_battle(
        battle
    ).entity_state_bytes()
    assert resident.rng_state_bytes() == ResidentRustBattle.from_battle(
        battle
    ).rng_state_bytes()


def test_electro_jump_and_chain_complete_tick_trace_matches_python() -> None:
    control, spirit, targets = _chain_fixture()
    resident = ResidentRustBattle.from_battle(control)
    original_hp = tuple(target.hitpoints for target in targets)
    saw_jump = False
    saw_chain = False

    for tick in range(1, 12):
        assert control.step_logic_ticks(1) == 1
        assert resident.advance_complete_ticks(1) == 1
        assert (
            python_resident_semantic_snapshot(control)
            == rust_resident_semantic_snapshot(resident)
        ), tick
        control_spirit = next(
            entity
            for entity in control.entities.values()
            if type(entity) is Troop and entity.id == spirit.id
        ) if spirit.id in control.entities else None
        if control_spirit is not None and control_spirit._special_move_active:
            saw_jump = True
            assert vars(control_spirit)["_electro_spirit_jump_origin"] == (
                9.0,
                12.0,
            )
        chains = [
            entity
            for entity in control.entities.values()
            if type(entity) is ChainLightning
        ]
        if chains:
            saw_chain = True
            chain = chains[0]
            assert chain.card_stats is spirit.card_stats

    assert saw_jump
    assert saw_chain
    assert all(target.hitpoints < hp for target, hp in zip(targets, original_hp))
    assert all(target.stun_timer > 0.0 for target in targets[1:])


def test_electro_hidden_tesla_blocks_primary_but_not_chain_birth() -> None:
    battle = BattleState(rng=random.Random(115_025), fast_path=True)
    spirit = _spawn_ready(battle, "ElectroSpirit", 0, Position(9.0, 12.0))
    tesla_stats = battle.card_loader.get_card("Tesla")
    assert tesla_stats is not None
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 12.5),
        1,
        tesla_stats,
    )
    assert type(tesla) is Building
    _ready_building(tesla)
    secondary = _spawn_ready(battle, "Knight", 1, Position(11.0, 12.5))
    secondary.apply_stun(1.0)
    tesla_target = _spawn_ready(battle, "Knight", 0, Position(9.0, 15.0))
    tesla_target.apply_stun(1.0)
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic) is HideWhenIdle
    )
    _commit_electro_jump(spirit, tesla)
    hide._phase_ms = float(hide.hide_delay_ms)
    tesla._hidden_building = True
    tesla._special_move_active = True
    tesla.target_id = None
    before_hp = tesla.hitpoints
    before_stun = tesla.stun_timer
    before_next_id = battle.next_entity_id
    resident = ResidentRustBattle.from_battle(battle)

    assert battle.step_logic_ticks(1) == resident.advance_complete_ticks(1) == 1

    assert python_resident_semantic_snapshot(battle) == (
        rust_resident_semantic_snapshot(resident)
    )
    # Tesla's intrinsic lifetime still costs two HP this frame; the committed
    # Electro primary payload contributes no additional damage while hidden.
    assert tesla.hitpoints == before_hp - 2
    assert tesla.stun_timer == before_stun
    assert spirit.id not in battle.entities
    assert battle.next_entity_id == before_next_id + 1
    chain = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is ChainLightning
    )
    assert chain.visited_ids == {tesla.id}
    assert chain.hits_air is True
    assert chain.hits_ground is True


def test_electro_fractional_dt_jump_uses_raw_duration() -> None:
    battle = BattleState(rng=random.Random(115_026), fast_path=True)
    battle.dt = 0.0333
    spirit = _spawn_ready(battle, "ElectroSpirit", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    target.apply_stun(1.0)
    _commit_electro_jump(spirit, target)
    resident = ResidentRustBattle.from_battle(battle)

    assert battle.step_logic_ticks(1) == resident.advance_complete_ticks(1) == 1

    assert python_resident_semantic_snapshot(battle) == (
        rust_resident_semantic_snapshot(resident)
    )
    assert spirit.position == Position(9.0, 12.666)
    assert vars(spirit)["_electro_spirit_jump_elapsed"] == pytest.approx(33.3)


@pytest.mark.parametrize("player_id", [0, 1])
def test_electro_chain_near_tie_uses_owner_relative_key(player_id: int) -> None:
    battle = BattleState(rng=random.Random(115_027 + player_id), fast_path=True)
    enemy_id = 1 - player_id
    if player_id == 0:
        preferred_x, nearer_x = 8.0, 9.9999995
    else:
        preferred_x, nearer_x = 10.0, 8.0000005
    preferred = _spawn_ready(
        battle,
        "Knight",
        enemy_id,
        Position(preferred_x, 12.0),
    )
    nearer = _spawn_ready(
        battle,
        "Knight",
        enemy_id,
        Position(nearer_x, 12.0),
    )
    for target in (preferred, nearer):
        target.apply_stun(1.0)
        target._native_target_distance_discount_sq_units = 0
    stats = battle.card_loader.get_card("ElectroSpirit")
    assert stats is not None
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(9.0, 12.0),
        player_id=player_id,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0,
        sight_range=0,
        origin=Position(9.0, 12.0),
        remaining_bounces=1,
        fixed_hop_duration=0.25,
    )
    battle.entities[chain.id] = chain
    battle.next_entity_id += 1
    resident = ResidentRustBattle.from_battle(battle)

    chain.update(battle.dt, battle)
    resident.advance_resident_object_phase()

    assert python_resident_semantic_snapshot(battle) == (
        rust_resident_semantic_snapshot(resident)
    )
    assert chain.current_target_id == preferred.id


@pytest.mark.parametrize(
    ("supports_name", "advance_name", "error"),
    [
        (
            "supports_ground_movement_phase",
            "advance_ground_movement_phase",
            "ground movement preflight",
        ),
        (
            "supports_flying_movement_phase",
            "advance_flying_movement_phase",
            "flying movement preflight",
        ),
    ],
)
def test_electro_standalone_movement_rejects_chain_allocation_overflow(
    supports_name: str,
    advance_name: str,
    error: str,
) -> None:
    battle = BattleState(rng=random.Random(115_029), fast_path=True)
    spirit = _spawn_ready(battle, "ElectroSpirit", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 12.5))
    _commit_electro_jump(spirit, target)
    spirit._special_move_consumed_tick = False
    battle.next_entity_id = sys.maxsize - 1
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not getattr(resident, supports_name)
    with pytest.raises(RuntimeError, match=error):
        getattr(resident, advance_name)()

    assert resident.entity_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize("mutation", ["range", "plane"])
def test_electro_source_payload_tamper_rejects_before_hydration(
    mutation: str,
) -> None:
    battle = BattleState(rng=random.Random(115_030), fast_path=True)
    spirit = _spawn_ready(battle, "ElectroSpirit", 0, Position(9.0, 12.0))
    if mutation == "range":
        mechanic = next(
            mechanic
            for mechanic in spirit.mechanics
            if type(mechanic) is ElectroSpiritChain
        )
        mechanic.chain_range = 4.0004
    else:
        spirit._can_attack_air_cached = False
    before = _causal_boundary_snapshot(battle)

    with pytest.raises(ValueError, match="Electro Spirit chain mechanic payload"):
        ResidentRustBattle.from_battle(battle)

    assert _causal_boundary_snapshot(battle) == before


def test_electro_chain_birth_one_plane_tamper_fails_before_live_mutation() -> None:
    battle, _spirit, _targets = _chain_fixture()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(2) == 2
    raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    row = next(row for row in raw["entities"] if row["chain_lightning_state"])
    row["chain_lightning_state"]["hits_air"] = False
    before = _causal_boundary_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="chain lightning"):
        _build_direct_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert _causal_boundary_snapshot(battle) == before


def test_electro_on_publication_preserves_chain_identity_and_causal_state() -> None:
    battle, _spirit, _targets = _chain_fixture()
    control = battle.clone()
    prior = ResidentRustBattle.from_battle(battle)
    registry: dict[int, Any] = dict(battle.entities)

    first = prior.fork()
    assert control.step_logic_ticks(2) == first.advance_complete_ticks(2) == 2
    publish_complete_tick_state(
        battle, first, prior_resident=prior, entity_registry=registry
    )
    assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)
    chain = next(entity for entity in battle.entities.values() if type(entity) is ChainLightning)
    origin = chain.origin
    visited = chain.visited_ids
    position = chain.position

    second = first.fork()
    assert control.step_logic_ticks(4) == second.advance_complete_ticks(4) == 4
    publish_complete_tick_state(
        battle, second, prior_resident=first, entity_registry=registry
    )
    assert _causal_boundary_snapshot(battle) == _causal_boundary_snapshot(control)
    assert registry[chain.id] is chain
    assert chain.origin is origin
    assert chain.visited_ids is visited
    assert chain.position is position
    assert len(visited) == 2


def test_electro_prepared_full_projection_matches_legacy_diagnostics() -> None:
    battle, _spirit, _targets = _chain_fixture()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(2) == 2
    parts = candidate.prepare_publication(prior).parts()

    projection = _typed_publication_projection(parts)
    assert projection.snapshot == rust_resident_semantic_snapshot(candidate)
    assert projection.publication_rows == json.loads(
        candidate.publication_entity_state_bytes()
    )
    chain_rows = projection.snapshot["chain_lightnings"]
    assert len(chain_rows) == 1
    assert chain_rows[0]["visited_ids"] == [8]
    assert chain_rows[0]["current_target_id"] == 9


def test_electro_chain_unknown_reference_fails_before_live_mutation() -> None:
    battle, _spirit, _targets = _chain_fixture()
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(2) == 2
    raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    row = next(row for row in raw["entities"] if row["chain_lightning_state"])
    row["chain_lightning_state"]["current_target_id"] = 99_999_999
    before = _causal_boundary_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="unknown reference"):
        _build_direct_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=dict(battle.entities),
        )

    assert _causal_boundary_snapshot(battle) == before


def test_electro_delta_unknown_reference_fails_before_live_mutation() -> None:
    battle, _spirit, _targets = _chain_fixture()
    prior = ResidentRustBattle.from_battle(battle)
    active = prior.fork()
    assert active.advance_complete_ticks(2) == 2
    registry: dict[int, Any] = dict(battle.entities)
    publish_complete_tick_state(
        battle, active, prior_resident=prior, entity_registry=registry
    )
    candidate = active.fork()
    assert candidate.advance_complete_ticks(1) == 1
    raw = candidate.prepare_publication(active)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    change = next(
        change
        for change in raw["entities"]
        if change["chain_lightning_state"] is not None
    )
    change["chain_lightning_state"]["current_target_id"] = 99_999_999
    before = _causal_boundary_snapshot(battle)

    with pytest.raises(ResidentPublicationError, match="unknown reference"):
        _build_direct_delta_publication_plan(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=registry,
        )

    assert _causal_boundary_snapshot(battle) == before


def test_electro_chain_publication_failure_rolls_back_exact_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle, _spirit, _targets = _chain_fixture()
    prior = ResidentRustBattle.from_battle(battle)
    active = prior.fork()
    assert active.advance_complete_ticks(2) == 2
    registry: dict[int, Any] = dict(battle.entities)
    publish_complete_tick_state(
        battle, active, prior_resident=prior, entity_registry=registry
    )
    chain = next(entity for entity in battle.entities.values() if type(entity) is ChainLightning)
    candidate = active.fork()
    assert candidate.advance_complete_ticks(4) == 4
    before = _causal_boundary_snapshot(battle)
    registry_items = tuple(registry.items())
    identities = (chain.position, chain.origin, chain.visited_ids, chain.card_stats)
    origin_coords = (chain.origin.x, chain.origin.y)
    position_coords = (chain.position.x, chain.position.y)
    visited_values = set(chain.visited_ids)

    def reject_commit(*_args: Any, **_kwargs: Any) -> None:
        raise ResidentPublicationError("injected Electro publication failure")

    monkeypatch.setattr(
        rust_publication, "_after_typed_publication_commit", reject_commit
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=active,
            entity_registry=registry,
        )

    assert _causal_boundary_snapshot(battle) == before
    assert tuple(registry.items()) == registry_items
    assert (chain.position, chain.origin, chain.visited_ids, chain.card_stats) == identities
    assert (chain.origin.x, chain.origin.y) == origin_coords
    assert (chain.position.x, chain.position.y) == position_coords
    assert chain.visited_ids == visited_values


def test_electro_off_shadow_on_fixed_episode_matches() -> None:
    battles = {mode: _chain_fixture()[0] for mode in RustBattleMode}
    runtimes = {
        mode: ResidentCompleteTickRuntime(battle, mode)
        for mode, battle in battles.items()
    }

    for runtime in runtimes.values():
        assert runtime.advance_ticks(11) == 11

    snapshots = {
        mode: python_resident_semantic_snapshot(battle)
        for mode, battle in battles.items()
    }
    assert snapshots[RustBattleMode.OFF] == snapshots[RustBattleMode.SHADOW]
    assert snapshots[RustBattleMode.OFF] == snapshots[RustBattleMode.ON]
    assert runtimes[RustBattleMode.SHADOW].status.shadow_mismatches == 0
