from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import replace

import pytest

from clasher import rust_core
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import ResidentRustBattle, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime, RustBattleMode

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)


def _spawn_ready(
    battle: BattleState, card_name: str, player_id: int, position: Position
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and type(entity) is Troop
    )
    troop.position = position
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def test_ordinary_charge_structural_catalog_closure() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    supported = set(resident.resident_supported_action_cards())

    assert {"Prince", "DarkPrince"} <= supported
    assert resident.resident_action_card_capability_reasons("Prince") == ()
    assert resident.resident_action_card_capability_reasons("DarkPrince") == ()
    for rejected in ("BattleRam", "Bandit", "SkeletonBarrel"):
        assert rejected not in supported
        assert resident.resident_action_card_capability_reasons(rejected)
    assert resident.resident_catalog_schema_version == 19


@pytest.mark.parametrize("card_name", ["Prince", "DarkPrince"])
@pytest.mark.parametrize("player_id", [0, 1])
def test_charge_action_ingress_and_initial_ticks_match_python(
    card_name: str, player_id: int
) -> None:
    battle = BattleState(rng=random.Random(211_000), fast_path=True)
    for player in battle.players:
        player.hand = [card_name, "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(
        0, 8, 10 if player_id == 0 else 21, player_id
    )
    actions = [action_space.no_op_action, action_space.no_op_action]
    actions[player_id] = action

    order = [0, 1]
    control.rng.shuffle(order)
    expected = {
        owner: action_space.apply_action(control, owner, actions[owner])
        for owner in order
    }
    actual, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == tuple(order)
    assert actual == expected
    assert actual[player_id]
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    for _ in range(8):
        control.step_logic_ticks(1)
        resident.advance_complete_tick()
        assert rust_resident_semantic_snapshot(resident) == (
            python_resident_semantic_snapshot(control)
        )


@pytest.mark.parametrize("card_name", ["Prince", "DarkPrince"])
def test_charge_progress_crossing_attack_reset_and_on_publication(
    card_name: str,
) -> None:
    battle = BattleState(rng=random.Random(211_001), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    _spawn_ready(battle, card_name, 0, Position(9.0, 10.0))
    _spawn_ready(battle, "Giant", 1, Position(9.0, 25.0))
    control = battle.clone()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)

    for _ in range(300):
        assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
        assert python_resident_semantic_snapshot(battle) == (
            python_resident_semantic_snapshot(control)
        )
        assert runtime.resident is not None
        assert rust_resident_semantic_snapshot(runtime.resident) == (
            python_resident_semantic_snapshot(control)
        )


@pytest.mark.parametrize("card_name", ["Prince", "DarkPrince"])
def test_charged_direct_payload_and_shield_reset_match_python(card_name: str) -> None:
    battle = BattleState(rng=random.Random(211_002), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    charger = _spawn_ready(battle, card_name, 0, Position(9.0, 10.0))
    _spawn_ready(battle, "Guards", 1, Position(9.0, 11.0))
    charger._native_charge_progress = 10_000
    charger.is_charging = True
    charger.attack_cooldown = 0.0
    control = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)

    control.step_logic_ticks(1)
    resident.advance_complete_tick()

    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )
    charged = next(entity for entity in control.entities.values() if entity.id == charger.id)
    assert not charged.is_charging
    assert charged._native_charge_progress == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("charge_range", {"$float": "0x1.f400000000000p+7"}),
        ("charge_speed_multiplier", "bad"),
        ("_native_charge_progress", -1),
        ("is_charging", True),
    ],
)
def test_charge_catalog_tamper_fails_closed_before_action_mutation(
    field: str, value: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    battle = BattleState(rng=random.Random(211_003), fast_path=True)
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(item for item in payload["cards"] if item["lookup_name"] == "Prince")
    fields = card["template_snapshot"]["$object"]["fields"]
    if field in fields:
        fields[field] = value
    else:
        fields["card_stats"]["$object"]["fields"][field] = value
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
    before = canonical_battle_snapshot(battle)

    with pytest.raises((RuntimeError, ValueError)):
        ResidentRustBattle.from_battle(battle)
    assert canonical_battle_snapshot(battle) == before
