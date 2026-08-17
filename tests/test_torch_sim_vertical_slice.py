import json
from collections import deque
from pathlib import Path

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.torch_sim import (
    TensorBattleState,
    TorchBattleExecutor,
    first_divergence,
)
from clasher.torch_sim.diagnostics import battle_snapshot


def _assert_exact_battle_match(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(
        battle_snapshot(expected),
        battle_snapshot(actual),
    )
    assert mismatch is None, str(mismatch)


def _battle_with_deployed_card(
    card_name: str,
    *,
    fast_path: bool = False,
    dt: float = 0.05,
) -> BattleState:
    battle = BattleState(fast_path=fast_path, dt=dt)
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = [card_name, None, None, None]
    player.deck = [card_name]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, card_name, Position(9.0, 10.0))
    return battle


@pytest.mark.parametrize(
    ("start_time", "ticks"),
    [
        (0.0, 1),
        (0.0, 100),
        (119.9, 5),
        (179.9, 5),
        (239.9, 5),
        (299.9, 5),
    ],
)
def test_pytorch_idle_complete_ticks_match_python_exactly(
    start_time: float,
    ticks: int,
) -> None:
    expected = BattleState()
    actual = expected.clone()
    expected.time = start_time
    actual.time = start_time

    expected.players[0].hand[1] = None
    actual.players[0].hand[1] = None
    expected.players[0].cycle_queue = deque(["Musketeer"])
    actual.players[0].cycle_queue = deque(["Musketeer"])
    expected.players[0].next_card_refill_cooldown_ms = 50
    actual.players[0].next_card_refill_cooldown_ms = 50

    expected.step_logic_ticks(ticks)
    executor = TorchBattleExecutor("pytorch")
    advanced = executor.step_logic_ticks(actual, ticks)

    _assert_exact_battle_match(expected, actual)
    assert advanced == min(ticks, expected.tick)
    assert executor.metrics_dict()["tensor_ticks"] == advanced
    assert executor.metrics_dict()["python_ticks"] == 0


def test_tensor_state_is_dense_batched_and_uses_native_coordinates() -> None:
    first = BattleState()
    second = BattleState()
    state = TensorBattleState.from_battles([first, second], max_entities=16)

    assert state.tick.shape == (2,)
    assert state.elixir.shape == (2, 2)
    assert state.entity_id.shape == (2, 16)
    assert state.entity_id[0, :6].tolist() == [1, 2, 3, 4, 5, 6]
    assert state.entity_x_units[0, :6].tolist() == [
        3500,
        14500,
        9000,
        3500,
        14500,
        9000,
    ]
    assert state.entity_y_units[0, :6].tolist() == [
        6500,
        6500,
        2500,
        25500,
        25500,
        29500,
    ]


def test_shadow_mode_runs_exact_differential_check() -> None:
    battle = BattleState()
    executor = TorchBattleExecutor("pytorch-shadow")

    assert executor.step_logic_ticks(battle, 8) == 8
    assert executor.metrics_dict() == {
        "tensor_ticks": 8.0,
        "python_ticks": 8.0,
        "shadow_checks": 1.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_twelve_battles_advance_in_one_exact_tensor_batch(backend: str) -> None:
    starts = [
        0.0,
        1.25,
        119.9,
        120.0,
        179.9,
        180.0,
        239.9,
        240.0,
        299.9,
        0.05,
        42.0,
        118.0,
    ]
    actual = [BattleState() for _ in starts]
    expected = [battle.clone() for battle in actual]
    for start, reference, candidate in zip(starts, expected, actual):
        reference.time = start
        candidate.time = start
        reference.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    advanced = executor.step_battles(actual, 8)

    for reference, candidate in zip(expected, actual):
        _assert_exact_battle_match(reference, candidate)
    assert advanced == [8, 8, 8, 8, 8, 8, 8, 8, 2, 8, 8, 8]
    assert executor.metrics_dict()["tensor_ticks"] == sum(advanced)
    if backend == "pytorch-shadow":
        assert executor.metrics_dict()["shadow_checks"] == 12


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_mechanic_free_deployment_frames_match_exactly(backend: str) -> None:
    battle = _battle_with_deployed_card("Knight")
    expected = battle.clone()
    expected.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 8) == 8

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 8
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_deployment_window_continues_in_python_at_first_actionable_frame(
    backend: str,
) -> None:
    battle = _battle_with_deployed_card("Knight")
    expected = battle.clone()
    expected.step_logic_ticks(25)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 25) == 25

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 20
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1
    expected_python_ticks = 25 if backend == "pytorch-shadow" else 5
    assert executor.metrics_dict()["python_ticks"] == expected_python_ticks


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
@pytest.mark.parametrize("card_name", ["Cannon", "Xbow"])
@pytest.mark.parametrize("fast_path", [False, True])
def test_mechanic_free_building_deployment_lifetime_matches_exactly(
    backend: str,
    card_name: str,
    fast_path: bool,
) -> None:
    battle = _battle_with_deployed_card(card_name, fast_path=fast_path)
    building = max(battle.entities.values(), key=lambda entity: entity.id)
    expected = battle.clone()
    expected.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 8) == 8

    _assert_exact_battle_match(expected, battle)
    assert building.lifetime_elapsed == pytest.approx(0.4)
    assert building.hitpoints < building.max_hitpoints
    assert executor.metrics_dict()["tensor_ticks"] == 8
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_every_enabled_mechanic_free_building_deployment_is_covered() -> None:
    inventory = []
    definitions = BattleState().card_loader.load_card_definitions()
    enabled_names = {
        card_name
        for deck in json.loads(Path("decks.json").read_text())["decks"]
        for card_name in deck["cards"]
    }
    for card_name in sorted(enabled_names):
        definition = definitions[card_name]
        if definition.kind != "building":
            continue
        battle = _battle_with_deployed_card(card_name)
        building = max(battle.entities.values(), key=lambda entity: entity.id)
        if not building.mechanics:
            inventory.append(card_name)

    assert inventory
    for backend in ("pytorch-shadow", "pytorch"):
        for card_name in inventory:
            battle = _battle_with_deployed_card(card_name)
            expected = battle.clone()
            expected.step_logic_ticks(8)
            executor = TorchBattleExecutor(backend)

            assert executor.step_logic_ticks(battle, 8) == 8
            _assert_exact_battle_match(expected, battle)
            assert executor.metrics_dict()["tensor_ticks"] == 8
            assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("hp_as_float", [False, True])
def test_building_lifetime_preserves_hitpoint_scalar_kind(
    hp_as_float: bool,
) -> None:
    battle = _battle_with_deployed_card("Cannon")
    building = max(battle.entities.values(), key=lambda entity: entity.id)
    if hp_as_float:
        building.hitpoints = float(building.hitpoints) - 0.25
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert type(building.hitpoints) is type(
        max(expected.entities.values(), key=lambda entity: entity.id).hitpoints
    )
    assert executor.metrics_dict()["tensor_ticks"] == 1
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_nonzero_building_lifetime_carry_matches_exactly(backend: str) -> None:
    battle = _battle_with_deployed_card("Cannon")
    building = max(battle.entities.values(), key=lambda entity: entity.id)
    building.lifetime_tick_carry_ms = 25.0
    building.lifetime_decay_work = 99
    expected = battle.clone()
    expected.step_logic_ticks(3)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    assert building.lifetime_tick_carry_ms == 25.0
    assert executor.metrics_dict()["tensor_ticks"] == 3
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_mixed_troop_and_building_batch_matches_exactly(backend: str) -> None:
    actual = [
        _battle_with_deployed_card("Knight"),
        _battle_with_deployed_card("Cannon"),
    ]
    expected = [battle.clone() for battle in actual]
    for battle in expected:
        battle.step_logic_ticks(8)

    executor = TorchBattleExecutor(backend)
    assert executor.step_battles(actual, 8) == [8, 8]

    for reference, candidate in zip(expected, actual):
        _assert_exact_battle_match(reference, candidate)
    assert executor.metrics_dict()["tensor_ticks"] == 16
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
@pytest.mark.parametrize("fast_path", [False, True])
def test_building_deployment_continues_in_python_when_actionable(
    backend: str,
    fast_path: bool,
) -> None:
    battle = _battle_with_deployed_card("Cannon", fast_path=fast_path)
    expected = battle.clone()
    expected.step_logic_ticks(25)

    executor = TorchBattleExecutor(backend)
    assert executor.step_logic_ticks(battle, 25) == 25

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 20
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1
    expected_python_ticks = 25 if backend == "pytorch-shadow" else 5
    assert executor.metrics_dict()["python_ticks"] == expected_python_ticks


def test_mechanic_bearing_building_deployment_fails_closed() -> None:
    battle = _battle_with_deployed_card("Tesla")
    expected = battle.clone()
    expected.step_logic_ticks(3)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 3
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


def test_deploying_building_death_uses_complete_runtime() -> None:
    battle = _battle_with_deployed_card("Cannon")
    building = max(battle.entities.values(), key=lambda entity: entity.id)
    building.hitpoints = 1
    building.lifetime_decay_work = 99
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 1
    assert executor.metrics_dict()["python_ticks"] == 0
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_deployment_in_crown_tower_sight_uses_complete_runtime() -> None:
    battle = BattleState()
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    battle._spawn_entity(
        Building,
        Position(9.0, 24.0),
        0,
        stats,
    )
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 1
    assert executor.metrics_dict()["python_ticks"] == 0
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_custom_tick_duration_building_lifetime_matches_exactly() -> None:
    battle = _battle_with_deployed_card("Cannon", dt=0.1)
    expected = battle.clone()
    expected.step_logic_ticks(3)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    building = max(battle.entities.values(), key=lambda entity: entity.id)
    assert building.lifetime_elapsed == pytest.approx(0.3)
    assert executor.metrics_dict()["tensor_ticks"] == 3
    assert executor.metrics_dict()["python_ticks"] == 0
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_mixed_batch_falls_back_only_for_unsupported_member() -> None:
    idle = BattleState()
    combat = _battle_with_deployed_card("ArcherQueen")
    expected_idle = idle.clone()
    expected_combat = combat.clone()
    expected_idle.step_logic_ticks(4)
    expected_combat.step_logic_ticks(4)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_battles([idle, combat], 4) == [4, 4]

    _assert_exact_battle_match(expected_idle, idle)
    _assert_exact_battle_match(expected_combat, combat)
    assert executor.metrics_dict()["tensor_ticks"] == 4
    assert executor.metrics_dict()["python_ticks"] == 4
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


def test_pytorch_on_fails_closed_for_mechanic_bearing_deployment() -> None:
    battle = _battle_with_deployed_card("ArcherQueen")
    expected = battle.clone()

    expected.step_logic_ticks(3)
    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 3) == 3

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 3
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


def test_deployment_at_exact_body_contact_fails_closed() -> None:
    battle = _battle_with_deployed_card("Knight")
    knight = max(battle.entities.values(), key=lambda entity: entity.id)
    tower = battle.entities[1]
    contact_distance = knight.get_collision_radius() + tower.get_collision_radius()
    knight.position = Position(tower.position.x + contact_distance, tower.position.y)
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 1
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


@pytest.mark.parametrize("backend", ["python", "pytorch-shadow", "pytorch"])
def test_training_environment_selects_simulation_backend(backend: str) -> None:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=2,
        max_ticks=4,
        simulation_backend=backend,
    )
    env.reset(seed=2301)
    no_op = env.action_space.no_op_action

    _, _, info = env.step({0: no_op, 1: no_op})

    assert info.ticks_advanced == 2
    metrics = env.simulator_backend_metrics()
    if backend == "python":
        # The existing Python idle fast-forward remains outside the executor.
        assert metrics["tensor_ticks"] == 0
    else:
        assert metrics["tensor_ticks"] == 2


def test_training_environment_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="simulation_backend must be one of"):
        SelfPlayBattleEnv(simulation_backend="unknown")


def test_training_environment_routes_simulation_device_through_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    env = SelfPlayBattleEnv(
        simulation_backend="pytorch",
        simulation_device="cuda",
    )

    assert env.simulation_device == "cuda"
    assert env._simulator.device == torch.device("cuda")
    env.reset(seed=2301)
    assert env._simulator.device == torch.device("cuda")


def test_training_environment_simulation_device_defaults_cpu() -> None:
    env = SelfPlayBattleEnv(simulation_backend="pytorch")
    assert env.simulation_device == "cpu"
    assert env._simulator.device == torch.device("cpu")


def test_training_environment_rejects_unavailable_or_unknown_simulation_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA simulation device"):
        SelfPlayBattleEnv(simulation_device="cuda")
    with pytest.raises(ValueError, match="simulation device must be one of"):
        SelfPlayBattleEnv(simulation_device="meta")


def test_custom_tick_duration_matches_oracle_exactly() -> None:
    expected = BattleState(dt=0.1)
    actual = expected.clone()
    expected.step_logic_ticks(4)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(actual, 4) == 4

    _assert_exact_battle_match(expected, actual)
    assert actual.time == 0.4
    assert executor.metrics_dict()["tensor_ticks"] == 4


def test_custom_phase_thresholds_match_oracle_exactly() -> None:
    expected = BattleState(
        double_elixir_start_time=0.05,
        overtime_start_time=0.1,
        triple_elixir_start_time=0.15,
        tiebreaker_time=0.2,
    )
    actual = expected.clone()
    expected.step_logic_ticks(3)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(actual, 3) == 3

    _assert_exact_battle_match(expected, actual)
    assert actual.double_elixir
    assert actual.overtime
    assert actual.triple_elixir


def test_same_clock_python_mutation_refreshes_retained_tensor_storage() -> None:
    expected = BattleState()
    actual = expected.clone()
    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(actual, 1) == 1
    expected.step_logic_ticks(1)
    _assert_exact_battle_match(expected, actual)

    expected.players[0].elixir = 1.0
    actual.players[0].elixir = 1.0
    expected.step_logic_ticks(1)
    assert executor.step_logic_ticks(actual, 1) == 1

    _assert_exact_battle_match(expected, actual)
    assert actual.players[0].elixir < 2.0


@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="Apple MPS is unavailable",
)
def test_complete_executor_fails_closed_on_mps_float64_state() -> None:
    expected = BattleState()
    actual = expected.clone()
    expected.step_logic_ticks(2)

    executor = TorchBattleExecutor("pytorch", device="mps")
    assert executor.step_logic_ticks(actual, 2) == 2

    _assert_exact_battle_match(expected, actual)
    assert executor.metrics_dict()["tensor_ticks"] == 0
    assert executor.metrics_dict()["python_ticks"] == 2
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_complete_executor_runs_exact_tensor_batch_on_cuda() -> None:
    expected = BattleState()
    actual = expected.clone()
    expected.step_logic_ticks(8)

    executor = TorchBattleExecutor("pytorch", device="cuda")
    assert executor.step_logic_ticks(actual, 8) == 8

    _assert_exact_battle_match(expected, actual)
    assert executor.metrics_dict()["tensor_ticks"] == 8
    assert executor.metrics_dict()["python_ticks"] == 0
    assert executor.metrics_dict()["unsupported_fallbacks"] == 0


def test_deploying_troop_in_enemy_tower_sight_uses_complete_combat_tick() -> None:
    battle = BattleState(fast_path=False)
    tower = battle.entities[4]
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    troop = battle._spawn_entity(
        Troop,
        Position(tower.position.x, tower.position.y - 3.0),
        0,
        stats,
    )
    troop.speed = 0.0
    troop.deploy_delay_remaining = 1.0
    troop.placement_delay_total = 1.0
    troop.placement_pending = True
    troop._spawn_hook_pending = True
    expected = battle.clone()
    expected.step_logic_ticks(1)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(battle, 1) == 1

    _assert_exact_battle_match(expected, battle)
    assert battle.entities[4].target_id == troop.id
    assert executor.metrics_dict()["tensor_ticks"] == 1
    assert executor.metrics_dict()["python_ticks"] == 0
