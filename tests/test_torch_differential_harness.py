from collections import deque

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.torch_sim.diagnostics import (
    StateDivergence,
    TorchParityError,
    battle_snapshot,
)
from clasher.torch_sim.differential import (
    CoverageRequirement,
    DifferentialConfig,
    DifferentialHarness,
    InteractionManifest,
    build_interaction_fixture,
    build_randomized_crowded_fixture,
    evaluate_coverage,
    exact_first_divergence,
    interaction_manifest_count,
    iter_interaction_manifests,
    verify_battle_fixture,
)
from clasher.torch_sim.executor import SimulatorBackend


def _always_noop(context):
    return {0: context.no_op_action, 1: context.no_op_action}


def test_exact_comparator_reports_array_dtype_scalar_kind_and_index() -> None:
    left = {"value": 1, "array": np.asarray([[1.0, 2.0]], dtype=np.float32)}
    wrong_scalar = {"value": 1.0, "array": left["array"].copy()}
    mismatch = exact_first_divergence(left, wrong_scalar)
    assert mismatch is not None
    assert mismatch.path == "verification['value']"
    assert mismatch.expected_type == "builtins.int"
    assert mismatch.actual_type == "builtins.float"

    wrong_value = {
        "value": 1,
        "array": np.asarray([[1.0, 3.0]], dtype=np.float32),
    }
    mismatch = exact_first_divergence(left, wrong_value)
    assert mismatch is not None
    assert mismatch.path == "verification['array'][0][1]"
    assert mismatch.expected_type == "numpy.float32"

    wrong_dtype = {
        "value": 1,
        "array": np.asarray([[1.0, 2.0]], dtype=np.float64),
    }
    mismatch = exact_first_divergence(left, wrong_dtype)
    assert mismatch is not None
    assert mismatch.path == "verification['array'].dtype"


def test_complete_idle_episode_checks_full_surface_and_has_tensor_coverage() -> None:
    harness = DifferentialHarness(
        DifferentialConfig(
            backend="pytorch",
            decision_interval_ticks=2,
            max_ticks=4,
            coverage=CoverageRequirement(
                min_tensor_ticks=4,
                min_tensor_fraction=1.0,
                max_unsupported_fallbacks=0,
            ),
        )
    )

    report = harness.run_episode(2301, action_provider=_always_noop)

    assert report.parity_passed
    assert report.complete_episode
    assert report.claim_passed
    assert report.divergence is None
    assert report.decisions == 2
    assert report.final_tick == 4
    assert report.coverage.tensor_ticks == 4
    assert report.coverage.tensor_fraction == 1.0
    assert not report.coverage.fallback_only
    assert len(report.actions) == 2


def test_shadow_exception_is_annotated_with_seed_tick_and_actions(monkeypatch) -> None:
    harness = DifferentialHarness(
        DifferentialConfig(backend="pytorch-shadow", max_ticks=2)
    )
    original_make_env = harness._make_env

    class DivergingExecutor:
        def step_logic_ticks(self, battle, ticks):
            raise TorchParityError(
                StateDivergence(
                    path="battle.entities[7].hitpoints",
                    expected=100,
                    actual=99,
                    expected_type="int",
                    actual_type="int",
                )
            )

        def metrics_dict(self):
            return {
                "tensor_ticks": 1.0,
                "python_ticks": 1.0,
                "shadow_checks": 1.0,
                "shadow_mismatches": 1.0,
                "unsupported_fallbacks": 0.0,
            }

    def make_env(*, seed, backend):
        env = original_make_env(seed=seed, backend=backend)
        if backend is not SimulatorBackend.PYTHON:
            env._simulator = DivergingExecutor()
        return env

    monkeypatch.setattr(harness, "_make_env", make_env)
    report = harness.run_episode(812, action_provider=_always_noop)

    assert not report.parity_passed
    assert report.divergence is not None
    assert report.divergence.seed == 812
    assert report.divergence.tick == 0
    assert report.divergence.actions
    assert report.divergence.phase == "tensor_shadow"
    assert report.divergence.mismatch.path == "battle.entities[7].hitpoints"


def test_fallback_only_parity_is_explicitly_rejected_as_tensor_evidence() -> None:
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = ["ArcherQueen", None, None, None]
    player.deck = ["ArcherQueen"]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, "ArcherQueen", Position(9.0, 10.0))

    report = verify_battle_fixture(
        battle,
        seed=77,
        name="mechanic-bearing-deployment",
        ticks=2,
        backend="pytorch",
        compare_structured_observations=False,
    )

    assert report.parity_passed
    assert not report.claim_passed
    assert report.coverage.fallback_only
    assert report.coverage.tensor_ticks == 0
    assert report.coverage.unsupported_fallbacks == 1
    assert "all requested ticks used the Python fallback" in (
        report.coverage.rejection_reasons
    )


def test_coverage_policy_can_require_fraction_and_fallback_limit() -> None:
    evidence = evaluate_coverage(
        executed_ticks=100,
        metrics={
            "tensor_ticks": 20.0,
            "python_ticks": 100.0,
            "unsupported_fallbacks": 3.0,
        },
        requirement=CoverageRequirement(
            min_tensor_ticks=10,
            min_tensor_fraction=0.5,
            max_unsupported_fallbacks=2,
        ),
    )

    assert not evidence.accepted
    assert not evidence.fallback_only
    assert evidence.tensor_fraction == 0.2
    assert any("tensor fraction" in reason for reason in evidence.rejection_reasons)
    assert any(
        "unsupported fallbacks" in reason for reason in evidence.rejection_reasons
    )


def test_exhaustive_manifests_have_exact_cardinality_and_lossless_shards() -> None:
    cards = ("Knight", "Archers", "Fireball")
    one_card_per_owner = tuple(iter_interaction_manifests(cards, cards_per_owner=1))
    two_cards_per_owner = tuple(iter_interaction_manifests(cards, cards_per_owner=2))

    assert len(one_card_per_owner) == interaction_manifest_count(3, 1) == 9
    assert len(two_cards_per_owner) == interaction_manifest_count(3, 2) == 36
    assert len({manifest.name for manifest in two_cards_per_owner}) == 36
    assert any(
        manifest.player0_cards == ("Knight", "Knight")
        for manifest in two_cards_per_owner
    )
    assert all("2v2" not in manifest.name for manifest in two_cards_per_owner)

    shards = [
        tuple(
            iter_interaction_manifests(
                cards,
                cards_per_owner=2,
                shard_index=shard,
                shard_count=5,
            )
        )
        for shard in range(5)
    ]
    ordinals = [manifest.ordinal for shard in shards for manifest in shard]
    assert sorted(ordinals) == list(range(36))
    assert len(ordinals) == len(set(ordinals))


def test_interaction_fixture_records_public_deployments_for_both_sides() -> None:
    manifest = InteractionManifest(
        ordinal=0,
        cards_per_owner=2,
        player0_cards=("Knight", "Fireball"),
        player1_cards=("Archers", "Zap"),
    )

    battle = build_interaction_fixture(manifest, seed=991)

    names = [
        getattr(entity.card_stats, "name", "")
        for entity in battle.entities.values()
        if entity.id > 6
    ]
    assert "Knight" in names
    assert names.count("Archer") == 2
    assert len(battle._pending_spell_casts) == 2


def test_randomized_crowded_fixture_is_reproducible_and_actually_crowded() -> None:
    first = build_randomized_crowded_fixture(seed=41, deployment_rounds=8)
    second = build_randomized_crowded_fixture(seed=41, deployment_rounds=8)

    assert first.tick == second.tick == 8
    assert sum(entity.is_alive for entity in first.entities.values()) >= 12
    assert (
        exact_first_divergence(battle_snapshot(first), battle_snapshot(second)) is None
    )
