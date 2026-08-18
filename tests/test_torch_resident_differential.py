from __future__ import annotations

import random
from collections import deque
from dataclasses import replace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_differential import (
    ResidentCoverageClassification,
    ResidentCoverageDigestMismatch,
    ResidentEpisodeDifferential,
    ResidentImplementationTopology,
    classify_resident_coverage_row,
    compare_resident_coverage_topologies,
    enumerate_enabled_resident_coverage,
    no_op_actions,
)

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6
EXPECTED_ENABLED_DIGEST = (
    "9b61ece2b25a1bed606524d99afc6c0674bfb5f90734b13e7a67f54b754052a0"
)
EXPECTED_EVIDENCE = {"Knight", "MiniPekka", "Pekka", "Valkyrie"}
EXPECTED_NO_INTERACTION = {"Bats", "Giant", "HogRider", "Prince", "RoyalHogs"}
EXPECTED_DIVERGED = {"Skeletons"}
EXPECTED_RUNTIME_FALLBACK = {
    "Archers",
    "Bandit",
    "DartGoblin",
    "Guards",
    "IceGolem",
    "IceSpirit",
    "Lumberjack",
    "MagicArcher",
    "NightWitch",
    "RoyalGhost",
    "SkeletonBarrel",
}


def _accelerate_episode(battle: BattleState) -> None:
    battle.overtime_start_time = 0.05
    battle.tiebreaker_time = 0.10


def _inert_battle(seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    _accelerate_episode(battle)
    return battle


def _combat_battle(seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(14.5, 14.5),
        1,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[1]
    target.hitpoints = 100.0
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    battle._spawn_unit_at_position(
        Position(14.5, 12.76),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    attacker = battle.entities[2]
    attacker.target_id = 1
    attacker._movement_target_id = 1
    attacker.attack_cooldown = 0.0
    player = battle.players[0]
    player.hand = ["Knight", "Zap", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0
    _accelerate_episode(battle)
    return battle


def _combat_actions(
    tick: int, battles: tuple[BattleState, ...]
) -> tuple[tuple[int, int], ...]:
    action = DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION
    return tuple((action, NO_OP_ACTION) for _ in battles)


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_full_inert_episodes_match_the_represented_resident_subset(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sources = [_inert_battle(410_000 + row) for row in range(4)]
    source_rng = [battle.rng.getstate() for battle in sources]
    report = ResidentEpisodeDifferential(
        device=device, max_entities=8, max_objects=8, event_capacity=32
    ).run(
        sources,
        no_op_actions,
        max_ticks=4,
    )

    assert report.divergence is None
    assert report.ticks_executed == 2
    assert report.resident_rows == (0, 1, 2, 3)
    assert report.completed_rows == (0, 1, 2, 3)
    assert report.parity_rows == (0, 1, 2, 3)
    assert report.fallback_only_rows == ()
    assert report.parity_passed
    assert report.oracle_topology is ResidentImplementationTopology.PYTHON_ORACLE
    assert report.candidate_topology is (
        ResidentImplementationTopology.PYTORCH_RESIDENT_BATCHED
    )
    assert [battle.tick for battle in sources] == [0, 0, 0, 0]
    assert [battle.rng.getstate() for battle in sources] == source_rng


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_supported_deployment_combat_episode_matches_represented_subset(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    report = ResidentEpisodeDifferential(
        device=device, max_entities=16, max_objects=16, event_capacity=64
    ).run(
        [_combat_battle(420_000 + row) for row in range(3)],
        _combat_actions,
        max_ticks=4,
    )

    assert report.divergence is None
    assert report.ticks_executed == 2
    assert report.parity_rows == (0, 1, 2)
    assert report.fallback_only_rows == ()


def test_preflight_rejected_row_is_fallback_only_not_parity() -> None:
    supported = _inert_battle(430_000)
    rejected = _inert_battle(430_001)
    player = rejected.players[0]
    player.hand = ["Golem", "Zap", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0

    def actions(tick: int, _battles: tuple[BattleState, ...]):
        return (
            (NO_OP_ACTION, NO_OP_ACTION),
            (
                DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION,
                NO_OP_ACTION,
            ),
        )

    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=32
    ).run([supported, rejected], actions, max_ticks=4)

    assert report.divergence is None
    assert report.preflight_rejected_rows == (1,)
    assert report.fallback_only_rows == (1,)
    assert report.parity_rows == (0,)
    assert 1 not in report.parity_rows


def test_cross_phase_rejected_row_is_fallback_only_not_parity() -> None:
    supported = _inert_battle(435_000)
    overflow = _combat_battle(435_001)

    def actions(tick: int, _battles: tuple[BattleState, ...]):
        combat_action = DEPLOY_KNIGHT_FAR_FROM_COMBAT if tick == 0 else NO_OP_ACTION
        return (
            (NO_OP_ACTION, NO_OP_ACTION),
            (combat_action, NO_OP_ACTION),
        )

    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=1
    ).run([supported, overflow], actions, max_ticks=4)

    assert report.divergence is None
    assert report.runtime_rejected_rows == (1,)
    assert report.fallback_only_rows == (1,)
    assert report.parity_rows == (0,)


def test_first_divergence_captures_tick_action_rng_and_event_context() -> None:
    def corrupt(_tick: int, engine) -> None:
        engine.runtime.battle.elixir[0, 0] += 1.0

    report = ResidentEpisodeDifferential(
        max_entities=8, max_objects=8, event_capacity=32
    ).run(
        [_inert_battle(440_000)],
        no_op_actions,
        max_ticks=4,
        resident_mutator=corrupt,
    )

    divergence = report.divergence
    assert divergence is not None
    assert divergence.row == 0
    assert divergence.tick == 0
    assert divergence.action == (NO_OP_ACTION, NO_OP_ACTION)
    assert divergence.path == "rows[0].players[0].elixir"
    assert divergence.expected_rng == divergence.actual_rng
    assert divergence.expected_events == divergence.actual_events == ()


@pytest.fixture(scope="module")
def enabled_coverage_matrix():
    return enumerate_enabled_resident_coverage()


def test_enabled_card_matrix_has_reviewed_stable_digest_and_strict_evidence(
    enabled_coverage_matrix,
) -> None:
    matrix = enabled_coverage_matrix
    enabled = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    assert tuple(entry.card_name for entry in matrix.entries) == enabled
    assert len(matrix.entries) == 66
    # This digest is accepted together with its reviewed classification
    # partition. A change must pass through assert_digest so card/opcode deltas
    # are visible; replacing only the hash is deliberately insufficient.
    expected_classifications = {
        name: ResidentCoverageClassification.PREFLIGHT_FALLBACK.value
        for name in enabled
    }
    for names, classification in (
        (
            EXPECTED_EVIDENCE,
            ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY,
        ),
        (
            EXPECTED_NO_INTERACTION,
            ResidentCoverageClassification.RESIDENT_NO_INTERACTION,
        ),
        (EXPECTED_DIVERGED, ResidentCoverageClassification.DIVERGED),
        (
            EXPECTED_RUNTIME_FALLBACK,
            ResidentCoverageClassification.RUNTIME_FALLBACK,
        ),
    ):
        for name in names:
            expected_classifications[name] = classification.value
    matrix.assert_digest(EXPECTED_ENABLED_DIGEST, expected_classifications)
    assert matrix.evidence_cards == ("Knight", "MiniPekka", "Pekka", "Valkyrie")
    assert all(
        matrix.require_evidence(name).interaction_observed
        for name in matrix.evidence_cards
    )
    entries = {entry.card_name: entry for entry in matrix.entries}
    # Their same-tick SPAWN + BUILDING_LIFETIME/DAMAGE event streams match.
    # Both then fail closed when their active projectile combat reaches the
    # next immutable preflight; fallback is not parity evidence.
    for name in ("Cannon", "Xbow"):
        assert (
            entries[name].classification
            is ResidentCoverageClassification.PREFLIGHT_FALLBACK
        )
        assert entries[name].divergence_path is None
        assert not entries[name].is_evidence
    with pytest.raises(ValueError, match="not represented"):
        matrix.require_evidence("Golem")


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_small_card_matrix_digest_is_device_stable(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    comparison = compare_resident_coverage_topologies(
        ("Knight", "Golem", "Fireball"), device=device
    )
    assert comparison.semantic_digest_matches
    assert comparison.deltas == ()
    assert (
        comparison.batched.digest
        == comparison.scalar_exact.digest
        == ("4d2eb7a2c6c0b03905d4faee19c09b50ed5b3684b41ff998b33a1ef0707cf1d3")
    )


def test_background_activity_cannot_count_as_tested_card_interaction() -> None:
    report = ResidentEpisodeDifferential(
        max_entities=8, max_objects=8, event_capacity=32
    ).run([_inert_battle(450_000)], no_op_actions, max_ticks=4)
    background_only = replace(
        report,
        interaction_rows=(0,),
        interaction_entity_ids=((1,),),
    )
    classification, attributed = classify_resident_coverage_row(
        background_only, 0, deployed_entity_ids=(2,)
    )
    assert classification is ResidentCoverageClassification.RESIDENT_NO_INTERACTION
    assert not attributed


def test_digest_and_reviewed_partition_report_card_and_opcode_deltas(
    enabled_coverage_matrix,
) -> None:
    matrix = enabled_coverage_matrix
    expected = {entry.card_name: entry.classification.value for entry in matrix.entries}
    expected["Golem"] = (
        ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value
    )
    with pytest.raises(ResidentCoverageDigestMismatch) as exc_info:
        # Even the current digest cannot bypass a stale/unreviewed per-card
        # classification partition.
        matrix.assert_digest(matrix.digest, expected)
    delta = next(item for item in exc_info.value.deltas if item.card_name == "Golem")
    assert delta.mechanic_opcodes
    assert "Golem" in str(exc_info.value)


def test_enabled_2v2_coverage_is_explicitly_unsupported() -> None:
    with pytest.raises(NotImplementedError, match="does not support 2v2"):
        enumerate_enabled_resident_coverage(card_names=("Knight",), team_size=2)
