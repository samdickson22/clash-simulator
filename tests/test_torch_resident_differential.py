from __future__ import annotations

import random
from collections import deque
from dataclasses import replace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.oracle_event_capture import OraclePayloadKind
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
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6
EXPECTED_ENABLED_DIGEST = (
    "200a7e2b40e85b7ba57c84fc02655d0d747f09f20eb3926efdea1d3e4eb010ba"
)
EXPECTED_EVIDENCE = {
    "Bandit",
    "Cannon",
    "Knight",
    "Lumberjack",
    "MiniPekka",
    "Pekka",
    "Skeletons",
    "Tombstone",
    "Valkyrie",
}
EXPECTED_NO_INTERACTION = {
    "Archers",
    "Balloon",
    "Bowler",
    "DartGoblin",
    "Giant",
    "Golem",
    "HogRider",
    "IceGolem",
    "MegaMinion",
    "Musketeer",
    "Prince",
    "RoyalHogs",
}
EXPECTED_DIVERGED = {
    "Arrows",
    "BabyDragon",
    "BarbarianBarrel",
    "BattleRam",
    "Bats",
    "Bomber",
    "Earthquake",
    "Fireball",
    "Freeze",
    "GiantSnowball",
    "GoblinBarrel",
    "Graveyard",
    "Log",
    "Miner",
    "Minions",
    "NightWitch",
    "Poison",
    "Princess",
    "Rocket",
    "RoyalDelivery",
    "SkeletonBarrel",
    "SpearGoblins",
    "Tornado",
    "Xbow",
    "Zap",
}
EXPECTED_RUNTIME_FALLBACK: set[str] = set()
WRAPPER_CHILD_ALIASES = {
    "Archers": "Archer",
    "Bandit": "Assassin",
    "DartGoblin": "BlowdartGoblin",
    "Guards": "SkeletonWarriors",
    "IceGolem": "IceGolemite",
    "IceSpirit": "IceSpirits",
    "Lumberjack": "RageBarbarian",
    "MagicArcher": "EliteArcher",
    "NightWitch": "DarkWitch",
    "RoyalGhost": "Ghost",
    "SkeletonBarrel": "SkeletonBalloon",
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


def _active_projectile_battle(card_name: str, seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(card_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None
    assert target_stats is not None
    source_type = Building if card_name == "Xbow" else Troop
    source = battle._spawn_entity(source_type, Position(14.5, 11.5), 0, source_stats)
    target = battle._spawn_entity(Troop, Position(14.5, 14.5), 1, target_stats)
    for entity in (source, target):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    source.target_id = target.id
    source._movement_target_id = target.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    source.speed = 0.0
    target.target_id = source.id if card_name == "Xbow" else None
    target._movement_target_id = target.target_id
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    target.speed = 0.0
    target.damage = 0.0
    target.sight_range = 0.0
    target.range = 0.0
    player = battle.players[0]
    player.hand = [card_name, "Knight", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 10.0
    battle.overtime_start_time = 4.0
    battle.tiebreaker_time = 5.0
    return battle


def _spell_event_battle(spell_name: str, seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    player = battle.players[0]
    player.hand = [spell_name, "Knight", "Cannon", "Fireball"]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 20.0
    battle.overtime_start_time = 4.0
    battle.tiebreaker_time = 5.0
    return battle


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
def test_supported_deployment_combat_state_exposes_exact_event_identity_gap(
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

    divergence = report.divergence
    assert divergence is not None
    assert divergence.tick == 1
    assert divergence.path == "battle.events"
    assert divergence.state is None
    assert divergence.expected_rng == divergence.actual_rng
    assert divergence.expected_events != divergence.actual_events
    assert report.fallback_only_rows == ()


@pytest.mark.parametrize("card_name", ("Minions", "Xbow"))
def test_projectile_event_divergence_uses_exact_oracle_callsite_tuple(
    card_name: str,
) -> None:
    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=64
    ).run(
        [_active_projectile_battle(card_name, 425_000)],
        no_op_actions,
        max_ticks=2,
    )

    divergence = report.divergence
    assert divergence is not None
    assert divergence.path == "battle.events"
    assert divergence.state is None
    launch = divergence.expected_events[0]
    assert launch.phase == TickPhase.COMBAT
    assert launch.opcode == RuntimeEventOpcode.PROJECTILE
    assert launch.payload_kind == OraclePayloadKind.COMBAT_PROJECTILE
    assert launch.source_id == 1
    assert launch.target_id > 2
    assert launch.x_units == 14_500
    assert launch.y_units > 0
    if card_name == "Xbow":
        lifetime = next(
            event
            for event in divergence.expected_events
            if event.phase == TickPhase.BUILDING_LIFETIME
        )
        assert launch.sequence < lifetime.sequence
    assert divergence.actual_events != divergence.expected_events


@pytest.mark.parametrize(
    ("spell_name", "carrier_opcode", "payload_kind"),
    (
        (
            "BarbarianBarrel",
            RuntimeEventOpcode.SPAWN,
            OraclePayloadKind.OBJECT_CHARACTER,
        ),
        ("Log", RuntimeEventOpcode.SPAWN, OraclePayloadKind.OBJECT_CHARACTER),
        (
            "RoyalDelivery",
            RuntimeEventOpcode.PROJECTILE,
            OraclePayloadKind.SPELL_PROJECTILE,
        ),
    ),
)
def test_rolling_and_royal_event_divergence_preserves_command_allocation_order(
    spell_name: str,
    carrier_opcode: RuntimeEventOpcode,
    payload_kind: OraclePayloadKind,
) -> None:
    def actions(
        tick: int, rows: tuple[BattleState, ...]
    ) -> tuple[tuple[int, int], ...]:
        action = 12 * 18 + 14 if tick == 0 else NO_OP_ACTION
        return tuple((action, NO_OP_ACTION) for _ in rows)

    report = ResidentEpisodeDifferential(
        max_entities=16, max_objects=16, event_capacity=64
    ).run(
        [_spell_event_battle(spell_name, 426_000)],
        actions,
        max_ticks=21,
    )

    divergence = report.divergence
    assert divergence is not None
    assert divergence.path == "battle.events"
    assert divergence.state is None
    command, carrier = divergence.expected_events[:2]
    assert command.phase == carrier.phase == TickPhase.COMMANDS
    assert command.opcode == RuntimeEventOpcode.COMMAND
    assert command.payload_kind == OraclePayloadKind.SPELL_EXECUTION
    assert carrier.opcode == carrier_opcode
    assert carrier.payload_kind == payload_kind
    assert command.sequence < carrier.sequence
    assert carrier.source_id == 0
    assert carrier.target_id > 0
    assert divergence.actual_events != divergence.expected_events


def test_preflight_rejected_row_is_fallback_only_not_parity() -> None:
    supported = _inert_battle(430_000)
    rejected = _inert_battle(430_001)
    player = rejected.players[0]
    player.hand = ["ArcherQueen", "Zap", "Cannon", "Fireball"]
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
    assert matrix.evidence_cards == (
        "Bandit",
        "Cannon",
        "Knight",
        "Lumberjack",
        "MiniPekka",
        "Pekka",
        "Skeletons",
        "Tombstone",
        "Valkyrie",
    )
    assert all(
        matrix.require_evidence(name).interaction_observed
        for name in matrix.evidence_cards
    )
    # Classification reaches this state only from report.parity_rows
    # (resident AND configured-episode-completed) plus interaction attributed
    # to IDs allocated by the tested action. Bridge support alone cannot pass.
    for name in ("Cannon", "Skeletons"):
        assert matrix.require_evidence(name).interaction_observed
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
        == ("1ce3bbdcdc3c6dd9fc0552e4cf9f750d4fee39ac39c9454e170e4a387def6f8f")
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


def test_completed_shorter_row_is_not_reclassified_as_fallback() -> None:
    early = _inert_battle(451_000)
    late = _inert_battle(451_001)
    late.overtime_start_time = 0.10
    late.tiebreaker_time = 0.15
    report = ResidentEpisodeDifferential(
        max_entities=8, max_objects=8, event_capacity=32
    ).run([early, late], no_op_actions, max_ticks=4)
    assert report.completed_rows == (0, 1)
    assert report.parity_rows == (0, 1)
    assert report.preflight_rejected_rows == ()
    assert report.runtime_rejected_rows == ()


def test_wrapper_child_aliases_are_executed_not_forced_runtime_fallback() -> None:
    matrix = enumerate_enabled_resident_coverage(
        card_names=tuple(WRAPPER_CHILD_ALIASES)
    )
    assert tuple(entry.card_name for entry in matrix.entries) == tuple(
        sorted(WRAPPER_CHILD_ALIASES)
    )
    # Production and verification now compile the same recursive serialized
    # wrapper->child namespace. A row may still fail closed at a real engine
    # preflight, but it cannot be excluded before the differential executes.
    assert all(
        entry.classification is not ResidentCoverageClassification.RUNTIME_FALLBACK
        for entry in matrix.entries
    )


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
