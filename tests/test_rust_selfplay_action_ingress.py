from __future__ import annotations

import random
from collections import deque
from dataclasses import fields
from typing import Any

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rust_core import ResidentRustBattle, RustBattleMode, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import ResidentPublicationError
from clasher.rust_runtime import ResidentCompleteTickRuntime

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _install_knight_decks(battle: BattleState) -> None:
    for player in battle.players:
        player.deck = ["Knight"] * 8
        player.hand = ["Knight"] * 4
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir


def _apply_python_joint_actions(
    battle: BattleState,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    action_space = DiscreteTileActionSpace()
    order = [0, 1]
    battle.rng.shuffle(order)
    success: dict[int, bool] = {}
    for player_id in order:
        success[player_id] = action_space.apply_action(
            battle,
            player_id,
            actions[player_id],
        )
    return success, (order[0], order[1])


def _joint_knight_actions(action_space: DiscreteTileActionSpace) -> tuple[int, int]:
    return (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )


def _assert_fast_cache_consumers_equal(
    expected: BattleState,
    actual: BattleState,
) -> None:
    assert actual._target_cache_dirty is expected._target_cache_dirty is False
    for name in (
        "_target_collision_radius",
        "_target_distance_discount_sq",
        "_target_is_air",
        "_target_is_building",
        "_target_is_building_target",
        "_target_is_crown",
        "_target_is_targetable",
        "_target_player",
        "_target_pos_x",
        "_target_pos_y",
        "_target_requires_targetability_check",
        "_target_stealth_until",
    ):
        np.testing.assert_array_equal(getattr(actual, name), getattr(expected, name))

    action_space = DiscreteTileActionSpace()
    for player_id in (0, 1):
        np.testing.assert_array_equal(
            action_space.legal_action_mask(actual, player_id, fast_path=True),
            action_space.legal_action_mask(expected, player_id, fast_path=True),
        )


def _assert_consumers_equal(
    expected: SelfPlayBattleEnv,
    actual: SelfPlayBattleEnv,
) -> None:
    for player_id in (0, 1):
        expected_obs = expected.get_structured_observation(player_id)
        actual_obs = actual.get_structured_observation(player_id)
        for field in fields(expected_obs):
            np.testing.assert_array_equal(
                getattr(actual_obs, field.name),
                getattr(expected_obs, field.name),
            )
        np.testing.assert_array_equal(
            actual.get_action_mask(player_id),
            expected.get_action_mask(player_id),
        )


@pytest.mark.parametrize("ticks", [0, 8])
def test_on_joint_action_interval_matches_python_without_python_action_calls(
    ticks: int,
) -> None:
    battle = BattleState(rng=random.Random(13_001 + ticks), fast_path=True)
    _install_knight_decks(battle)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = _joint_knight_actions(action_space)
    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    expected_ticks = control.step_logic_ticks(ticks)
    rng_identity = battle.rng

    def reject_python_action(_battle: Any, _player_id: int, _action: int) -> bool:
        raise AssertionError("on mode called the Python action applier")

    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=reject_python_action,
    )

    result = runtime.apply_joint_actions_and_advance(*actions, ticks)

    assert result.action_success == expected_success == {0: True, 1: True}
    assert tuple(result.action_success) == expected_order
    assert result.action_order == expected_order
    assert result.ticks_advanced == expected_ticks == ticks
    assert battle.rng is rng_identity
    assert battle.rng.getstate() == control.rng.getstate()
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert runtime.poisoned_reason is None


def test_shadow_joint_action_compares_before_exact_per_tick_lockstep() -> None:
    battle = BattleState(rng=random.Random(13_010), fast_path=True)
    _install_knight_decks(battle)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = _joint_knight_actions(action_space)
    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    assert control.step_logic_ticks(8) == 8
    action_calls: list[tuple[int, int]] = []

    def apply_python_action(
        candidate: BattleState,
        player_id: int,
        action: int,
    ) -> bool:
        action_calls.append((player_id, action))
        return action_space.apply_action(candidate, player_id, action)

    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=apply_python_action,
    )

    result = runtime.apply_joint_actions_and_advance(*actions, 8)

    assert result.action_success == expected_success
    assert result.action_order == expected_order
    assert result.ticks_advanced == 8
    assert tuple(player_id for player_id, _ in action_calls) == expected_order
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert runtime.status.shadow_checks == 9
    assert runtime.status.shadow_mismatches == 0
    _assert_fast_cache_consumers_equal(control, battle)


def test_selfplay_on_matches_off_and_preserves_shared_rng_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control = SelfPlayBattleEnv(
        seed=13_020,
        max_ticks=64,
        engine_fast_path="on",
        resident_complete_tick_mode="off",
    )
    candidate = SelfPlayBattleEnv(
        seed=13_020,
        max_ticks=64,
        engine_fast_path="on",
        resident_complete_tick_mode="on",
    )
    control.decks = [["Knight"] * 8]
    candidate.decks = [["Knight"] * 8]

    def reject_python_action(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("self-play on mode called Python action application")

    monkeypatch.setattr(candidate.action_space, "apply_action", reject_python_action)
    control.reset()
    candidate.reset()
    assert control.battle is not None
    assert candidate.battle is not None
    rng_identity = candidate.rng
    assert candidate.battle.rng is rng_identity
    actions = _joint_knight_actions(control.action_space)

    expected = control.step({0: actions[0], 1: actions[1]})
    actual = candidate.step({0: actions[0], 1: actions[1]})

    assert actual == expected
    assert candidate.battle.rng is rng_identity
    assert candidate.rng.getstate() == control.rng.getstate()
    assert python_resident_semantic_snapshot(candidate.battle) == (
        python_resident_semantic_snapshot(control.battle)
    )
    status = candidate.resident_runtime_status
    assert status is not None
    assert status.active_mode is RustBattleMode.ON
    assert status.fallback_reason is None
    _assert_consumers_equal(control, candidate)


def test_reset_unsupported_deck_falls_back_without_rng_drift_and_retries() -> None:
    probe_battle = BattleState()
    supported = set(
        ResidentRustBattle.from_battle(probe_battle).resident_supported_action_cards()
    )
    unsupported = next(
        name
        for name in sorted(probe_battle.card_loader.load_card_definitions())
        if probe_battle.card_loader.get_card(name) is not None and name not in supported
    )
    control = SelfPlayBattleEnv(
        seed=13_030,
        resident_complete_tick_mode="off",
    )
    candidate = SelfPlayBattleEnv(
        seed=13_030,
        resident_complete_tick_mode="on",
    )
    control.decks = [[unsupported] * 8]
    candidate.decks = [[unsupported] * 8]

    control.reset()
    candidate.reset()
    assert control.battle is not None
    assert candidate.battle is not None

    status = candidate.resident_runtime_status
    assert status is not None
    assert status.active_mode is RustBattleMode.OFF
    assert status.fallback_reason is not None
    assert "unsupported hand/cycle card" in status.fallback_reason
    assert candidate.rng.getstate() == control.rng.getstate()
    assert python_resident_semantic_snapshot(candidate.battle) == (
        python_resident_semantic_snapshot(control.battle)
    )

    candidate.decks = [["Knight"] * 8]
    candidate.reset(seed=13_031)
    retried = candidate.resident_runtime_status
    assert retried is not None
    assert retried.active_mode is RustBattleMode.ON
    assert retried.fallback_reason is None


def test_initial_preflight_rejects_unsupported_cycle_card_before_rng() -> None:
    battle = BattleState(rng=random.Random(13_035))
    _install_knight_decks(battle)
    probe = ResidentRustBattle.from_battle(battle)
    supported = set(probe.resident_supported_action_cards())
    unsupported = next(
        name
        for name in sorted(battle.card_loader.load_card_definitions())
        if battle.card_loader.get_card(name) is not None and name not in supported
    )
    battle.players[1].cycle_queue[2] = unsupported
    rng_before = battle.rng.getstate()

    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=DiscreteTileActionSpace().apply_action,
    )

    assert runtime.active_mode is RustBattleMode.OFF
    assert runtime.fallback_reason is not None
    assert "unsupported hand/cycle card" in runtime.fallback_reason
    assert runtime.resident is None
    assert battle.rng.getstate() == rng_before


def test_noncanonical_action_perspective_falls_back_before_action_rng() -> None:
    env = SelfPlayBattleEnv(
        seed=13_040,
        canonical_perspective=False,
        resident_complete_tick_mode="on",
    )
    env.decks = [["Knight"] * 8]
    env.reset()
    rng_before = env.rng.getstate()

    status = env.resident_runtime_status

    assert status is not None
    assert status.active_mode is RustBattleMode.OFF
    assert status.fallback_reason == (
        "resident action ingress requires canonical action perspective"
    )
    assert env.rng.getstate() == rng_before


@pytest.mark.parametrize("ability_player", [0, 1])
@pytest.mark.parametrize("other_action_kind", ["no_op", "valid"])
def test_native_ability_action_consumes_shuffle_and_matches_python_false(
    ability_player: int,
    other_action_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(13_050 + ability_player))
    _install_knight_decks(battle)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    other_player = 1 - ability_player
    other_x, other_y = ((8, 10) if other_player == 0 else (9, 21))
    other_action = (
        action_space.no_op_action
        if other_action_kind == "no_op"
        else action_space.encode_action(0, other_x, other_y, other_player)
    )
    mutable_actions = [action_space.no_op_action, action_space.no_op_action]
    mutable_actions[ability_player] = action_space.ability_action
    mutable_actions[other_player] = other_action
    actions = (mutable_actions[0], mutable_actions[1])
    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = battle.rng.getstate()

    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == expected_order
    assert actual_success == expected_success
    assert actual_success[ability_player] is False
    assert actual_success[other_player] is True
    assert control.rng.getstate() != rng_before
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_ability_action_matches_python_and_remains_usable() -> None:
    battle = BattleState(rng=random.Random(13_055))
    _install_knight_decks(battle)
    control = battle.clone()
    action_space = DiscreteTileActionSpace()
    actions = (action_space.ability_action, action_space.no_op_action)
    expected_success, expected_order = _apply_python_joint_actions(control, actions)
    assert control.step_logic_ticks(8) == 8
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    result = runtime.apply_joint_actions_and_advance(
        *actions,
        8,
    )

    assert result.action_success == expected_success == {0: False, 1: True}
    assert result.action_order == expected_order
    assert result.ticks_advanced == 8
    assert battle.rng.getstate() == control.rng.getstate()
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert runtime.status.poisoned_reason is None


def test_post_action_tick_failure_poisons_without_publishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(13_057))
    _install_knight_decks(battle)
    action_space = DiscreteTileActionSpace()
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    resident = runtime.resident
    assert resident is not None
    battle_before = python_resident_semantic_snapshot(battle)
    resident_before = rust_resident_semantic_snapshot(resident)
    registry_before = tuple(runtime.entity_registry.items())

    def reject_ticks(_self: ResidentRustBattle, _ticks: int) -> int:
        raise RuntimeError("injected post-action capability failure")

    monkeypatch.setattr(ResidentRustBattle, "advance_complete_ticks", reject_ticks)

    with pytest.raises(RuntimeError, match="now poisoned"):
        runtime.apply_joint_actions_and_advance(
            *_joint_knight_actions(action_space),
            8,
        )

    assert python_resident_semantic_snapshot(battle) == battle_before
    assert rust_resident_semantic_snapshot(resident) == resident_before
    assert runtime.resident is resident
    assert tuple(runtime.entity_registry.items()) == registry_before
    assert runtime.poisoned_reason == (
        "post-action complete-tick capability failure: "
        "injected post-action capability failure"
    )
    assert runtime.status.poisoned_reason == runtime.poisoned_reason
    with pytest.raises(RuntimeError, match="runtime is poisoned"):
        runtime.apply_joint_actions_and_advance(
            action_space.no_op_action,
            action_space.no_op_action,
            0,
        )


def test_action_interval_publication_failure_keeps_root_and_live_state_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(13_060))
    _install_knight_decks(battle)
    action_space = DiscreteTileActionSpace()
    runtime = ResidentCompleteTickRuntime(
        battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    resident = runtime.resident
    assert resident is not None
    battle_before = python_resident_semantic_snapshot(battle)
    resident_before = rust_resident_semantic_snapshot(resident)
    registry_before = tuple(runtime.entity_registry.items())

    def reject_publication(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected action publication failure")

    monkeypatch.setattr(
        rust_publication,
        "publish_complete_tick_state",
        reject_publication,
    )
    actions = _joint_knight_actions(action_space)

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.apply_joint_actions_and_advance(*actions, 8)

    assert python_resident_semantic_snapshot(battle) == battle_before
    assert rust_resident_semantic_snapshot(resident) == resident_before
    assert runtime.resident is resident
    assert tuple(runtime.entity_registry.items()) == registry_before
    assert runtime.poisoned_reason == "injected action publication failure"
    assert runtime.status.poisoned_reason == runtime.poisoned_reason
