from __future__ import annotations

import copy
import random
from collections import deque

import pytest

from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, snapshot_bytes
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.rust_oracle_planner import (
    RustBackendFixedDepthThompsonOracle,
)
from clasher.rust_core import ResidentRustBattle, rust_core_available

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _supported_unique_deck(battle: BattleState) -> list[str]:
    resident = ResidentRustBattle.from_battle(battle)
    historical_deck = [
        "BabyDragon",
        "Berserker",
        "BlowdartGoblin",
        "Bomber",
        "DartBarrell",
        "ElectroGiant",
        "Giant",
        "GiantBuffer",
    ]
    supported = set(resident.resident_supported_action_cards())
    assert all(name in supported for name in historical_deck)
    return historical_deck


def _supported_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    deck = _supported_unique_deck(battle)
    for player in battle.players:
        player.hand = list(deck[:4])
        player.deck = deck.copy()
        player.cycle_queue = deque(deck[4:])
        player.elixir = player.max_elixir
    return battle


def _production_deck_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    deck = [
        "Archers",
        "Arrows",
        "Fireball",
        "Giant",
        "Knight",
        "MiniPekka",
        "Minions",
        "Musketeer",
    ]
    resident = ResidentRustBattle.from_battle(battle)
    assert all(name in set(resident.resident_supported_action_cards()) for name in deck)
    for player in battle.players:
        player.hand = deck[:4]
        player.deck = deck.copy()
        player.cycle_queue = deque(deck[4:])
        player.elixir = player.max_elixir
    return battle


def test_production_deck_oracle_off_shadow_on_is_exact() -> None:
    outputs = []
    for mode in ("off", "shadow", "on"):
        battle = _production_deck_battle(9401)
        battle_before = snapshot_bytes(canonical_battle_snapshot(battle))
        battle_rng_before = battle.rng.getstate()
        planner = RustBackendFixedDepthThompsonOracle(
            decision_interval_ticks=8,
            plan_depth=3,
            num_simulations=8,
            rollout_action_samples=32,
            seed=901,
            reward_profile=DEFENSE_V2,
            stable_root_candidates=True,
            rust_mode=mode,
        )

        actions = planner.select_actions(battle)

        assert actions == {0: 204, 1: 1766}
        assert (
            planner.metrics.trace_sha256
            == "251c80d88e5228b13f34d699342020ce85f0dc3dbc0cc51e59177ab17a26610d"
        )
        assert snapshot_bytes(canonical_battle_snapshot(battle)) == battle_before
        assert battle.rng.getstate() == battle_rng_before
        outputs.append((actions, copy.deepcopy(planner.rng.bit_generator.state)))
        if mode == "shadow":
            assert planner.metrics.active_backend == "python+rust-shadow"
            assert planner.metrics.shadow_checks == 1
            assert planner.metrics.shadow_mismatches == 0
        elif mode == "on":
            assert planner.metrics.active_backend == "rust"
            assert planner.metrics.fallback_reason is None

    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize(
    ("stable_root", "expected_actions", "expected_trace_sha256"),
    [
        (
            False,
            {0: 11, 1: 69},
            "4116d1ac4084381af40058c8aff6cc89456c4d0ab346ff29c6595e3280d98251",
        ),
        (
            True,
            {0: 1387, 1: 1185},
            "7cbd38d96f57f394d3fae0ee4b8afa4227f9d703f3163f894f5051aca2a1337b",
        ),
    ],
)
def test_oracle_off_shadow_on_match_actions_backups_and_planner_rng(
    stable_root: bool,
    expected_actions: dict[int, int],
    expected_trace_sha256: str,
) -> None:
    outputs = []
    for mode in ("off", "shadow", "on"):
        battle = _supported_battle(9300 + int(stable_root))
        battle_before = snapshot_bytes(canonical_battle_snapshot(battle))
        battle_rng_before = battle.rng.getstate()
        planner = RustBackendFixedDepthThompsonOracle(
            decision_interval_ticks=2,
            plan_depth=2,
            num_simulations=4,
            rollout_action_samples=16,
            seed=901,
            reward_profile=DEFENSE_V2,
            stable_root_candidates=stable_root,
            rust_mode=mode,
        )

        actions = planner.select_actions(battle)

        assert actions == expected_actions
        assert planner.metrics.trace_sha256 == expected_trace_sha256
        assert snapshot_bytes(canonical_battle_snapshot(battle)) == battle_before
        assert battle.rng.getstate() == battle_rng_before
        outputs.append((actions, copy.deepcopy(planner.rng.bit_generator.state)))
        if mode == "shadow":
            assert planner.metrics.active_backend == "python+rust-shadow"
            assert planner.metrics.shadow_checks == 1
            assert planner.metrics.shadow_mismatches == 0
        elif mode == "on":
            assert planner.metrics.active_backend == "rust"
            assert planner.metrics.fallback_reason is None

    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize("mode", ["shadow", "on"])
def test_oracle_unsupported_root_falls_back_before_planner_rng(mode: str) -> None:
    battle = BattleState(rng=random.Random(99))
    reference = RustBackendFixedDepthThompsonOracle(
        plan_depth=1,
        num_simulations=1,
        rollout_action_samples=4,
        seed=4,
        rust_mode="off",
    )
    candidate = RustBackendFixedDepthThompsonOracle(
        plan_depth=1,
        num_simulations=1,
        rollout_action_samples=4,
        seed=4,
        rust_mode=mode,
    )

    reference_actions = reference.select_actions(battle)
    candidate_actions = candidate.select_actions(battle)

    assert candidate_actions == reference_actions == {0: 723, 1: 242}
    assert candidate.rng.bit_generator.state == reference.rng.bit_generator.state
    assert candidate.metrics.active_backend == "python"
    assert candidate.metrics.fallback_reason is not None
    assert "unsupported hand/cycle card" in candidate.metrics.fallback_reason
    assert candidate.metrics.trace_sha256 == reference.metrics.trace_sha256
    assert candidate.metrics.shadow_checks == 0
