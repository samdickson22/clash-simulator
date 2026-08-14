from __future__ import annotations

import json
import random
from dataclasses import replace

import pytest

from clasher import rust_core, rust_publication
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import Building, Troop
from clasher.mechanics.shared.damage_ramp import DamageRamp
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    publish_complete_tick_state,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)


def _spawn_ready(
    battle: BattleState,
    name: str,
    player_id: int,
    position: Position,
) -> Troop | Building:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(
        Building if str(stats.card_type).casefold() == "building" else Troop,
        position,
        player_id,
        stats,
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_delay_total = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.on_spawn()
    return entity


def _ramp(entity: Troop | Building) -> DamageRamp:
    return next(mechanic for mechanic in entity.mechanics if type(mechanic) is DamageRamp)


def _connected_battle(card_name: str) -> tuple[BattleState, Troop | Building, Troop]:
    battle = BattleState(rng=random.Random(171_001), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_ready(battle, card_name, 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Golem", 1, Position(9.0, 14.0))
    assert type(target) is Troop
    target.hitpoints = 100_000.0
    target.max_hitpoints = 100_000.0
    return battle, attacker, target


def test_damage_ramp_catalog_closure_is_structural_and_exact() -> None:
    battle = BattleState()
    resident = ResidentRustBattle.from_battle(battle)
    definitions = battle.card_loader.load_card_definitions()
    ramp_lookups = {
        name
        for name, definition in definitions.items()
        if any(type(mechanic) is DamageRamp for mechanic in definition.mechanics)
    }

    supported = set(resident.resident_supported_action_cards())
    assert ramp_lookups & supported == {"InfernoDragon", "InfernoTower"}
    assert {"MightyMiner", "Monk"} <= ramp_lookups - supported


@pytest.mark.parametrize(
    ("card_name", "expected_stages"),
    [
        ("InfernoDragon", [(0, 35), (2000, 120), (4000, 422)]),
        ("InfernoTower", [(0, 43), (2000, 158), (4000, 847)]),
    ],
)
def test_damage_ramp_complete_tick_and_on_publication_match_python(
    card_name: str,
    expected_stages: list[tuple[int, int]],
) -> None:
    battle, attacker, _target = _connected_battle(card_name)
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    ramp = _ramp(attacker)
    ramp_identity = id(ramp)

    assert ramp.stages == expected_stages
    for ticks in (1, 8, 32, 40):
        prior = resident
        candidate = prior.fork()
        assert candidate.advance_complete_ticks(ticks) == ticks
        assert control.step_logic_ticks(ticks) == ticks
        registry = dict(battle.entities)
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )
        resident = candidate
        assert python_resident_semantic_snapshot(battle) == (
            python_resident_semantic_snapshot(control)
        )
        assert rust_resident_semantic_snapshot(resident) == (
            python_resident_semantic_snapshot(control)
        )
        assert id(_ramp(battle.entities[attacker.id])) == ramp_identity
    final_ramp = _ramp(battle.entities[attacker.id])
    assert final_ramp._current_target_ms == 4_050.0
    assert battle.entities[attacker.id].damage == expected_stages[-1][1]


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_damage_ramp_shield_break_resets_connected_stage_exactly(
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(171_002), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_ready(battle, card_name, 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Guards", 1, Position(9.0, 14.0))
    assert type(target) is Troop
    shield = next(
        mechanic for mechanic in target.mechanics if type(mechanic).__name__ == "Shield"
    )
    shield.current_shield = 1
    ramp = _ramp(attacker)
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    attacker.attack_cooldown = 0.0
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4_000.0
    attacker.damage = ramp.stages[-1][1]
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    control._step_logic_tick(refresh_fast_path_end=False)
    assert resident.advance_complete_tick()
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    control_attacker = control.entities[attacker.id]
    control_ramp = _ramp(control_attacker)
    assert control_attacker.target_id == target.id
    assert control_ramp._current_target_id == target.id
    assert control_ramp._current_target_ms == 0.0
    assert control_attacker.damage == control_ramp.stages[0][1]


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_damage_ramp_stun_observation_resets_before_attack_clock(card_name: str) -> None:
    battle, attacker, target = _connected_battle(card_name)
    ramp = _ramp(attacker)
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    attacker.attack_cooldown = 0.01
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4_000.0
    attacker.damage = ramp.stages[-1][1]
    attacker.apply_stun(0.5, source_kind="Zap")
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    control._step_logic_tick(refresh_fast_path_end=False)
    assert resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    current = control.entities[attacker.id]
    current_ramp = _ramp(current)
    assert current_ramp._current_target_id is None
    assert current_ramp._current_target_ms == 0.0
    assert current.damage == current_ramp.stages[0][1]


def test_mobile_damage_ramp_approaches_500_units_before_connecting() -> None:
    battle = BattleState(rng=random.Random(171_004), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_ready(
        battle, "InfernoDragon", 0, Position(9.0, 10.0)
    )
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.501))
    assert type(attacker) is Troop and type(target) is Troop
    attacker.target_id = target.id
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(2):
        control._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    assert control.entities[attacker.id].position.y > 10.0
    assert _ramp(control.entities[attacker.id])._current_target_id is None


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_damage_ramp_mid_windup_drift_resets_channel_but_completes_hit(
    card_name: str,
) -> None:
    battle, attacker, target = _connected_battle(card_name)
    ramp = _ramp(attacker)
    target.position = Position(
        attacker.position.x,
        attacker.position.y
        + attacker.range
        + target.get_collision_radius()
        + 0.020,
    )
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    attacker._attack_windup_active = True
    attacker.attack_cooldown = 0.01
    if type(attacker) is Building:
        attacker.activation_delay_remaining = 0.0
        attacker.activation_first_hit_delay_remaining = 0.0
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4_000.0
    attacker.damage = ramp.stages[-1][1]
    target_hp_before = target.hitpoints
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    control._step_logic_tick(refresh_fast_path_end=False)
    assert resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    current = control.entities[attacker.id]
    current_ramp = _ramp(current)
    assert control.entities[target.id].hitpoints == (
        target_hp_before - current_ramp.stages[0][1]
    )
    assert current_ramp._current_target_id == target.id
    assert current_ramp._current_target_ms == 0.0
    assert current.damage == current_ramp.stages[0][1]


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_damage_ramp_lethal_retarget_resets_channel(card_name: str) -> None:
    battle = BattleState(rng=random.Random(171_005), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_ready(battle, card_name, 0, Position(9.0, 12.0))
    first = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_ready(battle, "Knight", 1, Position(10.0, 14.0))
    assert type(first) is Troop and type(second) is Troop
    first.hitpoints = _ramp(attacker).stages[0][1]
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(24):
        control._step_logic_tick(refresh_fast_path_end=False)
        assert resident.advance_complete_tick()
        assert rust_resident_semantic_snapshot(resident) == (
            python_resident_semantic_snapshot(control)
        )

    current = control.entities[attacker.id]
    current_ramp = _ramp(current)
    assert current.target_id == second.id
    assert current_ramp._current_target_id == second.id
    assert current_ramp._current_target_ms < 2_000.0
    assert current.damage == current_ramp.stages[0][1]


def test_damage_ramp_catalog_tamper_rejects_before_action_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(171_003), fast_path=True)
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(
        item for item in payload["cards"] if item["lookup_name"] == "InfernoDragon"
    )
    mechanic = card["template_snapshot"]["$object"]["fields"]["mechanics"][0]
    mechanic["$object"]["fields"]["stages"][1]["$tuple"][0] = -1
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
    battle.players[0].hand[0] = "InfernoDragon"
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    )

    assert "template_parse" in " ".join(
        resident.resident_action_card_capability_reasons("InfernoDragon")
    )
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(0, 2304)
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        resident.entity_state_bytes(),
        resident.next_entity_id,
    ) == before


def test_damage_ramp_delta_commit_failure_rolls_back_mechanic_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle, attacker, _target = _connected_battle("InfernoDragon")
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(8) == 8
    registry = dict(battle.entities)
    mechanic = _ramp(attacker)
    mechanic_before = dict(vars(mechanic))
    canonical_before = canonical_battle_snapshot(battle)

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected DamageRamp commit failure")

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
    assert _ramp(battle.entities[attacker.id]) is mechanic
    assert vars(mechanic) == mechanic_before
