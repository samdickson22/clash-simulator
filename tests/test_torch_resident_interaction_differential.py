from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.deployment import TensorDeploymentCatalog
from clasher.torch_sim.resident_differential import (
    RESIDENT_COMPARISON_SCOPE,
    ResidentActionProvider,
    ResidentCoverageClassification,
    ResidentEpisodeDifferential,
    ResidentEpisodeReport,
    classify_resident_coverage_row,
)
from clasher.torch_sim.resident_engine import (
    TensorResidentEngine,
    _resident_deployment_catalog_closure,
)

INTERACTION_CARDS = (
    "Archers",
    "Bowler",
    "DartGoblin",
    "Giant",
    "HogRider",
    "MegaMinion",
    "Musketeer",
    "Prince",
    "RoyalHogs",
)


@dataclass(frozen=True)
class InteractionScenario:
    card_name: str
    deployed_ids: tuple[int, ...]
    building_target: bool
    target_y: float
    episode_end_time: float


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _scenario_battle(
    card_name: str,
    *,
    building_target: bool,
    target_y: float,
    episode_end_time: float,
    seed: int,
) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    if building_target:
        target_stats = battle.card_loader.get_card("Cannon")
        assert target_stats is not None
        target = battle._spawn_entity(
            Building,
            Position(14.5, target_y),
            1,
            target_stats,
        )
    else:
        target_stats = battle.card_loader.get_card("Knight")
        assert target_stats is not None
        battle._spawn_unit_at_position(
            Position(14.5, target_y),
            1,
            target_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        target = battle.entities[1]
    target.hitpoints = 10_000
    target.max_hitpoints = 10_000
    target.deploy_delay_remaining = 0.0
    target.placement_delay_total = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0

    fillers = [
        name
        for name in ("Knight", "Zap", "Cannon", "Fireball", "Archers")
        if name != card_name
    ]
    player = battle.players[0]
    player.hand = [card_name, *fillers[:3]]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    battle.overtime_start_time = episode_end_time - battle.dt
    battle.tiebreaker_time = episode_end_time
    return battle


def _scenarios() -> tuple[tuple[BattleState, ...], tuple[InteractionScenario, ...]]:
    loader = CardDataLoader()
    overlay, closure = _resident_deployment_catalog_closure(
        loader, set(INTERACTION_CARDS)
    )
    catalog = TensorCardCatalog.compile(overlay, closure)
    deployment = TensorDeploymentCatalog.compile(overlay, catalog)
    battles: list[BattleState] = []
    scenarios: list[InteractionScenario] = []
    for index, card_name in enumerate(INTERACTION_CARDS):
        card_id = catalog.name_to_id[card_name]
        summon_count = int(catalog.summon_count[card_id].item())
        delay_count = max(1, int(deployment.summon_count[card_id].item()))
        deploy_delay = float(
            deployment.deploy_delay_seconds[card_id, :delay_count].max().item()
        )
        episode_end = max(1.05, deploy_delay + 3.0)
        building_target = bool(catalog.buildings_only[card_id].item())
        range_units = int(catalog.range_units[card_id].item())
        target_y = (
            19.0
            if building_target
            else 12.5 + max(1.25, min(3.5, range_units * 0.0006))
        )
        battles.append(
            _scenario_battle(
                card_name,
                building_target=building_target,
                target_y=target_y,
                episode_end_time=episode_end,
                seed=740_000 + index,
            )
        )
        scenarios.append(
            InteractionScenario(
                card_name=card_name,
                deployed_ids=tuple(range(2, 2 + summon_count)),
                building_target=building_target,
                target_y=target_y,
                episode_end_time=episode_end,
            )
        )
    return tuple(battles), tuple(scenarios)


def _actions(
    tick: int,
    rows: Sequence[BattleState],
) -> tuple[tuple[int, int], ...]:
    action = 12 * 18 + 14 if tick == 0 else NO_OP_ACTION
    return tuple((action, NO_OP_ACTION) for _ in rows)


def _run(device: str) -> tuple[ResidentEpisodeReport, tuple[InteractionScenario, ...]]:
    battles, scenarios = _scenarios()
    max_ticks = max(
        math.ceil((scenario.episode_end_time - 1e-9) / battles[0].dt)
        for scenario in scenarios
    )
    report = ResidentEpisodeDifferential(
        device=device,
        max_entities=64,
        max_objects=64,
        event_capacity=2_048,
    ).run(
        battles,
        cast(ResidentActionProvider, _actions),
        max_ticks=max_ticks + 1,
        stop_on_first_divergence=False,
    )
    return report, scenarios


def test_action_owned_entities_reach_real_post_deployment_interactions(
    tensor_device: str,
) -> None:
    report, scenarios = _run(tensor_device)
    assert report.semantic_scope == RESIDENT_COMPARISON_SCOPE
    assert report.fallback_only_rows == ()
    classifications: dict[str, ResidentCoverageClassification] = {}
    for row, scenario in enumerate(scenarios):
        interacted = set(report.interaction_entity_ids[row])
        assert set(scenario.deployed_ids) <= interacted, (
            scenario.card_name,
            scenario.deployed_ids,
            tuple(sorted(interacted)),
        )
        classification, attributed = classify_resident_coverage_row(
            report,
            row,
            scenario.deployed_ids,
        )
        assert attributed
        assert classification in {
            ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY,
            ResidentCoverageClassification.DIVERGED,
        }
        classifications[scenario.card_name] = classification

    expected = {
        "Archers": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "Bowler": ResidentCoverageClassification.DIVERGED.value,
        "DartGoblin": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "Giant": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "HogRider": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "MegaMinion": ResidentCoverageClassification.DIVERGED.value,
        "Musketeer": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "Prince": ResidentCoverageClassification.REPRESENTED_INTERACTION_PARITY.value,
        "RoyalHogs": ResidentCoverageClassification.DIVERGED.value,
    }
    assert {name: value.value for name, value in classifications.items()} == expected

    divergence_by_row = {item.row: item for item in report.divergences}
    for row, scenario in enumerate(scenarios):
        classification = classifications[scenario.card_name]
        if classification is ResidentCoverageClassification.DIVERGED:
            divergence = divergence_by_row[row]
            assert divergence.expected_rng == divergence.actual_rng or (
                divergence.path == "battle.rng_state"
            )
        else:
            assert row in report.completed_rows
            assert row in report.parity_rows


def test_royal_hogs_combat_facing_drives_sequential_avoidance_exactly(
    tensor_device: str,
) -> None:
    source = _scenario_battle(
        "RoyalHogs",
        building_target=True,
        target_y=19.0,
        episode_end_time=4.3,
        seed=740_008,
    )
    oracle = source.clone()
    engine = TensorResidentEngine.from_battles(
        [source.clone()],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=256,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    result = None

    for tick in range(61):
        actions = _actions(tick, (oracle,))[0]
        order = [0, 1]
        oracle.rng.shuffle(order)
        for player in order:
            assert action_space.apply_action(oracle, player, actions[player])
        oracle.step_logic_ticks(1)
        result = engine.step(
            torch.tensor([actions], dtype=torch.int64, device=tensor_device)
        )
        assert result.committed.tolist() == [True]

    assert result is not None
    runtime_ids = engine.movement.entity_id[0].tolist()
    hog_slot = runtime_ids.index(4)
    earlier_slot = runtime_ids.index(2)
    expected = oracle.entities[4]
    assert isinstance(expected, Troop)
    assert (
        engine.movement.position_units[0, hog_slot].tolist()
        == [
            round(expected.position.x * 1_000),
            round(expected.position.y * 1_000),
        ]
        == [15_068, 17_578]
    )
    assert (
        engine.movement.avoidance[0, hog_slot].item()
        == (expected._native_avoidance)
        == 190
    )
    assert result.movement.collision.accumulated_vector_units[0, hog_slot].tolist() == [
        17,
        16,
    ]
    assert result.movement.collision.contact_count[0, hog_slot].item() == 1
    assert result.movement.collision_only_moved[0, earlier_slot].item()
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
