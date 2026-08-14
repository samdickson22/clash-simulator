from __future__ import annotations

import json
import random
from collections import deque
from types import SimpleNamespace

import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import AreaEffect, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentRustBattle,
    RustBattleMode,
    _single_troop_capability_reasons,
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
from clasher.rust_runtime import (
    ResidentCompleteTickRuntime,
    _causal_boundary_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)

_MECHANIC_ACTION_CARDS = (
    "Golem",
    "Guards",
    "SkeletonWarriors",
    "IceGolem",
    "IceGolemite",
    "InfernoDragon",
    "InfernoTower",
)


def _set_mechanic_action_hands(battle: BattleState, card_name: str) -> None:
    for player in battle.players:
        player.hand = [card_name, "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _actions(action_space: DiscreteTileActionSpace) -> tuple[int, int]:
    return (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )


def _apply_python_actions(
    battle: BattleState,
    action_space: DiscreteTileActionSpace,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    order = [0, 1]
    battle.rng.shuffle(order)
    result = {
        player_id: action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
        for player_id in order
    }
    return result, (order[0], order[1])


def test_catalog_admits_only_exact_compiled_mechanic_action_closure() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    supported = set(resident.resident_supported_action_cards())

    assert {
        "Golem",
        "Guards",
        "SkeletonWarriors",
        "IceGolem",
        "IceGolemite",
        "InfernoDragon",
        "InfernoTower",
    } <= supported
    assert "formation_runtime_preflight" in resident.resident_action_card_capability_reasons(
        "RoyalRecruits"
    )
    assert "formation_runtime_preflight" in resident.resident_action_card_capability_reasons(
        "RoyalRecruits_Chess"
    )
    assert resident.resident_action_card_capability_reasons("DarkPrince")
    assert resident.resident_action_card_capability_reasons("LavaHound")


def test_python_capability_rejects_mixed_status_nova_and_death_mechanic_family() -> None:
    battle = BattleState()
    ice_stats = battle.card_loader.get_card("IceSpirit")
    ice_definition = battle.card_loader.get_card_definition("IceSpirit")
    guard_definition = battle.card_loader.get_card_definition("Guards")
    assert ice_stats is not None
    assert ice_definition is not None and guard_definition is not None
    mixed_definition = SimpleNamespace(
        kind="troop",
        mechanics=(ice_definition.mechanics[0], guard_definition.mechanics[0]),
    )

    assert "executable_mechanics" in _single_troop_capability_reasons(
        ice_stats, mixed_definition
    )


def test_native_catalog_rejects_mixed_status_nova_and_shield_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(150_901), fast_path=True)
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    ice = next(item for item in payload["cards"] if item["lookup_name"] == "IceSpirit")
    guards = next(item for item in payload["cards"] if item["lookup_name"] == "Guards")
    ice_mechanics = ice["template_snapshot"]["$object"]["fields"]["mechanics"]
    guard_mechanic = guards["template_snapshot"]["$object"]["fields"]["mechanics"][0]
    ice_mechanics.append(guard_mechanic)
    ice["template_fingerprint"] = rust_core._canonical_json_sha256(
        ice["template_snapshot"]
    )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
        rolling_spawn_recipes=bundle.rolling_spawn_recipes,
        rolling_projectile_recipes=bundle.rolling_projectile_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    _set_mechanic_action_hands(battle, "IceSpirit")
    resident = ResidentRustBattle.from_battle(battle)

    assert "native_single_troop_preflight" in (
        resident.resident_action_card_capability_reasons("IceSpirit")
    )


@pytest.mark.parametrize("card_name", ["Guards", "Golem"])
def test_compiled_mechanic_template_tamper_rejects_before_action_mutation(
    card_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(150_900), fast_path=True)
    data_path = battle.card_loader.data_file
    data_stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), data_stat.st_mtime_ns, data_stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(item for item in payload["cards"] if item["lookup_name"] == card_name)
    mechanics = card["template_snapshot"]["$object"]["fields"]["mechanics"]
    if card_name == "Guards":
        mechanics[0]["$object"]["fields"]["current_shield"] = 0
    else:
        mechanics[1]["$object"]["fields"]["radius_tiles"] = {
            "$float": "0x0.0p+0"
        }
    card["template_fingerprint"] = rust_core._canonical_json_sha256(
        card["template_snapshot"]
    )
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
        rolling_spawn_recipes=bundle.rolling_spawn_recipes,
        rolling_projectile_recipes=bundle.rolling_projectile_recipes,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    _set_mechanic_action_hands(battle, card_name)
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )
    action_space = DiscreteTileActionSpace()

    assert "native_single_troop_preflight" in (
        resident.resident_action_card_capability_reasons(card_name)
    )
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(
            action_space.encode_action(0, 8, 10, 0),
            action_space.no_op_action,
        )
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    ) == before


@pytest.mark.parametrize("card_name", _MECHANIC_ACTION_CARDS)
def test_compiled_mechanic_joint_actions_and_first_ticks_match_python(
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(151_000), fast_path=True)
    _set_mechanic_action_hands(battle, card_name)
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = _actions(action_space)

    expected_success, expected_order = _apply_python_actions(
        control, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    if card_name in {"InfernoDragon", "InfernoTower"}:
        ramp_entities = [
            entity
            for entity in control.entities.values()
            if getattr(entity.card_stats, "name", None) == card_name
        ]
        assert len(ramp_entities) == 2
        for entity in ramp_entities:
            ramp = next(
                mechanic
                for mechanic in entity.mechanics
                if type(mechanic).__name__ == "DamageRamp"
            )
            assert "_current_target_id" not in vars(ramp)
            assert "_current_target_ms" not in vars(ramp)
    for _ in range(8):
        assert resident.advance_complete_tick()
        control._step_logic_tick(refresh_fast_path_end=False)
        assert rust_resident_semantic_snapshot(resident) == (
            python_resident_semantic_snapshot(control)
        )


@pytest.mark.parametrize("card_name", _MECHANIC_ACTION_CARDS)
def test_compiled_mechanic_action_off_shadow_on_and_delta_continuation(
    card_name: str,
) -> None:
    base = BattleState(rng=random.Random(151_100), fast_path=True)
    _set_mechanic_action_hands(base, card_name)
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    action_space = DiscreteTileActionSpace()
    actions = _actions(action_space)
    expected_success, expected_order = _apply_python_actions(off, action_space, actions)
    assert off.step_logic_ticks(8) == 8
    shadow = ResidentCompleteTickRuntime(
        shadow_battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    on = ResidentCompleteTickRuntime(
        on_battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 8)
    on_result = on.apply_joint_actions_and_advance(*actions, 8)

    assert shadow_result.action_success == on_result.action_success == expected_success
    assert shadow_result.action_order == on_result.action_order == expected_order
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0

    assert off.step_logic_ticks(16) == 16
    assert shadow.advance_ticks(16) == on.advance_ticks(16) == 16
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0


@pytest.mark.parametrize("card_name", ["Golem", "Guards", "IceGolem"])
def test_action_created_compiled_mechanic_executes_on_first_tick(
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(151_150), fast_path=True)
    _set_mechanic_action_hands(battle, card_name)
    attacker_stats = battle.card_loader.get_card("Knight")
    assert attacker_stats is not None
    attacker = battle._spawn_entity(
        Troop,
        Position(9.0, 12.0),
        1,
        attacker_stats,
    )
    attacker.deploy_delay_remaining = 0.0
    attacker.placement_delay_total = 0.0
    attacker.placement_pending = False
    attacker._spawn_hook_pending = False
    attacker._spawn_hook_fired = True
    attacker.damage = 100_000
    attacker.attack_cooldown = 0.0
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )
    expected_success, expected_order = _apply_python_actions(
        control, action_space, actions
    )
    assert control.step_logic_ticks(1) == 1
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    result = runtime.apply_joint_actions_and_advance(*actions, 1)

    assert result.action_success == expected_success == {0: True, 1: True}
    assert result.action_order == expected_order
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    if card_name == "Golem":
        assert sum(
            type(entity) is Troop and str(entity.card_stats.name) == "Golemite"
            for entity in battle.entities.values()
        ) == 2
    elif card_name == "IceGolem":
        assert any(type(entity) is AreaEffect for entity in battle.entities.values())
    else:
        guards = [
            entity
            for entity in battle.entities.values()
            if type(entity) is Troop
            and str(entity.card_stats.name) == "SkeletonWarriors"
        ]
        assert len(guards) == 3
        assert any(entity._shield_break_count == 1 for entity in guards)
        broken = next(entity for entity in guards if entity._shield_break_count == 1)
        shield = next(
            mechanic
            for mechanic in broken.mechanics
            if hasattr(mechanic, "current_shield")
        )
        assert shield.current_shield == 0
        assert broken.hitpoints == broken.max_hitpoints


def test_action_born_golem_death_spawn_validates_full_and_delta_plans() -> None:
    battle = BattleState(rng=random.Random(151_175), fast_path=True)
    _set_mechanic_action_hands(battle, "Golem")
    attacker_stats = battle.card_loader.get_card("Knight")
    assert attacker_stats is not None
    attacker = battle._spawn_entity(Troop, Position(9.0, 12.0), 1, attacker_stats)
    attacker.deploy_delay_remaining = 0.0
    attacker.placement_delay_total = 0.0
    attacker.placement_pending = False
    attacker._spawn_hook_pending = False
    attacker._spawn_hook_fired = True
    attacker.damage = 100_000
    attacker.attack_cooldown = 0.0
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
        1,
    )
    assert success == {0: True, 1: True}
    assert advanced == 1
    registry = dict(battle.entities)

    full_raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    delta_raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )
    full_plan = _build_direct_publication_plan(
        full_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    delta_plan = _build_direct_delta_publication_plan(
        delta_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )

    assert sum(
        entity.raw["character_birth"] is not None
        and entity.raw["character_birth"]["kind"] == 1
        for entity in full_plan.entities
    ) == 2
    assert sum(
        item.full is not None
        and item.full.raw["character_birth"] is not None
        and item.full.raw["character_birth"]["kind"] == 1
        for item in delta_plan.entities
    ) == 2

@pytest.mark.parametrize("card_name", _MECHANIC_ACTION_CARDS)
def test_compiled_mechanic_action_birth_rollback_is_exact(
    card_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(151_200), fast_path=True)
    _set_mechanic_action_hands(battle, card_name)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    action_space = DiscreteTileActionSpace()
    candidate.apply_resident_joint_actions(
        action_space.encode_action(0, 8, 10, 0),
        action_space.no_op_action,
    )
    registry: dict[int, object] = dict(battle.entities)
    before = _causal_boundary_snapshot(battle)
    canonical_before = canonical_battle_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    registry_before = tuple(registry.items())
    card_cache_before = tuple(battle.card_loader._cards.items())

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected compiled-mechanic birth failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        reject_commit,
    )

    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert _causal_boundary_snapshot(battle) == before
    assert canonical_battle_snapshot(battle) == canonical_before
    assert tuple(battle.entities.items()) == entities_before
    assert tuple(registry.items()) == registry_before
    assert tuple(battle.card_loader._cards.items()) == card_cache_before
