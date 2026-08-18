from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields

import numpy as np
import pytest
import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.reward_model import objective_potential_p0, objective_win_prob_p0
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.observations import (
    TensorCvObservation,
    TensorStructuredObservation,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import (
    ResidentOutputProjector,
    tensor_objective_potential_p0,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase

DEPLOY_KNIGHT_FAR_FROM_COMBAT = 1 * 18 + 6


def _assert_structured_exact(
    actual: TensorStructuredObservation,
    battles: Sequence[BattleState],
    builder: StructuredObservationBuilder,
) -> None:
    for row, battle in enumerate(battles):
        for player in range(2):
            expected = builder.build(battle, player)
            for descriptor in fields(expected):
                np.testing.assert_array_equal(
                    getattr(actual, descriptor.name)[row, player].cpu().numpy(),
                    getattr(expected, descriptor.name),
                )


def _assert_cv_exact(
    actual: TensorCvObservation,
    battles: Sequence[BattleState],
    builder: CvObservationBuilder,
) -> None:
    for row, battle in enumerate(battles):
        for player in range(2):
            expected = builder.build(battle, player)
            np.testing.assert_array_equal(
                actual.board[row, player].cpu().numpy(), expected.board
            )
            np.testing.assert_array_equal(
                actual.hud[row, player].cpu().numpy(), expected.hud
            )


def _projection(
    battles: list[BattleState],
    *,
    device: str = "cpu",
) -> tuple[TensorResidentEngine, ResidentOutputProjector]:
    engine = TensorResidentEngine.from_battles(
        battles, device=device, max_entities=16, max_objects=16
    )
    structured = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    cv = CvObservationBuilder(card_vocab=[])
    projection = ResidentOutputProjector.from_engine(
        engine,
        battles,
        structured_builder=structured,
        cv_builder=cv,
    )
    return engine, projection


def test_initial_and_supported_resident_segments_match_both_oracles_exactly() -> None:
    sources = [BattleState(), BattleState(time=119.9)]
    expected = [battle.clone() for battle in sources]
    engine, projection = _projection(sources)
    _assert_structured_exact(
        projection.project_structured(),
        expected,
        projection.observations.structured_builder,
    )
    _assert_cv_exact(
        projection.project_cv(), expected, projection.observations.cv_builder
    )

    for _ in range(4):
        assert engine.step().committed.tolist() == [True, True]
        for battle in expected:
            assert battle.step_logic_ticks(1) == 1
        _assert_structured_exact(
            projection.project_structured(),
            expected,
            projection.observations.structured_builder,
        )
        _assert_cv_exact(
            projection.project_cv(), expected, projection.observations.cv_builder
        )
        outcome = projection.project_reward_outcome()
        expected_potential = torch.tensor(
            [objective_potential_p0(battle) for battle in expected],
            dtype=torch.float64,
        )
        assert torch.equal(outcome.potential_p0.cpu(), expected_potential)
        assert outcome.reward.sum(dim=1).tolist() == [0.0, 0.0]


def test_shortened_full_inert_episodes_project_terminal_outcomes_once() -> None:
    sources = [
        BattleState(
            overtime_start_time=0.10,
            tiebreaker_time=0.20,
        ),
        BattleState(
            overtime_start_time=0.15,
            tiebreaker_time=0.25,
        ),
    ]
    expected = [battle.clone() for battle in sources]
    engine, projection = _projection(sources)
    latest = None
    for _ in range(5):
        active_before = [not battle.game_over for battle in expected]
        committed = engine.step().committed
        for index, battle in enumerate(expected):
            if active_before[index]:
                battle.step_logic_ticks(1)
            assert bool(committed[index].item()) is active_before[index]
        latest = projection.project_reward_outcome()
        if bool(latest.done.all().item()):
            break
    assert latest is not None and latest.done.tolist() == [True, True]
    assert latest.winner.tolist() == [-1, -1]
    assert latest.win_probability_p0.tolist() == [0.5, 0.5]
    assert latest.outcome.tolist() == [[0.0, 0.0], [0.0, 0.0]]
    assert [objective_win_prob_p0(battle) for battle in expected] == [0.5, 0.5]
    repeated = projection.project_reward_outcome()
    assert repeated.reward.tolist() == [[0.0, -0.0], [0.0, -0.0]]


def test_projection_clone_and_duplicate_row_fanout_are_tensor_only_and_isolated() -> (
    None
):
    sources = [BattleState(), BattleState(time=119.9)]
    engine, projection = _projection(sources)
    assert engine.step().committed.all()
    cloned = projection.clone()
    children = projection.fork([1, 0, 1])

    parent_structured = projection.project_structured()
    child_structured = children.project_structured()
    assert torch.equal(child_structured.entity_ids[0], parent_structured.entity_ids[1])
    assert torch.equal(child_structured.entity_ids[1], parent_structured.entity_ids[0])
    assert torch.equal(child_structured.entity_ids[2], parent_structured.entity_ids[1])
    assert children.runtime.battle.entity_id is children.runtime.entity_pool.entity_id
    assert (
        children.runtime.battle.time.data_ptr() != engine.runtime.battle.time.data_ptr()
    )
    assert (
        cloned.runtime.battle.time.data_ptr() != engine.runtime.battle.time.data_ptr()
    )

    children.runtime.battle.time[0] += 5.0
    children.rewards.previous_potential_p0[0] += 1.0
    assert children.runtime.battle.time[0] != children.runtime.battle.time[2]
    assert (
        projection.rewards.previous_potential_p0[1]
        != (children.rewards.previous_potential_p0[0])
    )


def test_projection_does_not_call_python_builders_after_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = [BattleState()]
    _, projection = _projection(sources)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("resident projection called a Python observation builder")

    monkeypatch.setattr(projection.observations.structured_builder, "build", forbidden)
    monkeypatch.setattr(projection.observations.cv_builder, "build", forbidden)
    projection.project_structured()
    projection.project_cv()
    projection.project_reward_outcome(commit=False)


def test_reward_potential_groups_asymmetric_king_activation_by_row_and_player() -> None:
    battles = [BattleState() for _ in range(3)]
    activation = ((False, True), (True, False), (True, True))
    for row, battle in enumerate(battles):
        for entity in battle.entities.values():
            slot = getattr(entity, "_crown_tower_slot", None)
            if slot == "king":
                assert isinstance(entity, Building)
                entity._tower_active = activation[row][entity.player_id]
        battle.players[0].king_tower_hp -= 25.0 + row
        battle.players[1].king_tower_hp -= 70.0 + row
        for entity in battle.entities.values():
            if getattr(entity, "_crown_tower_slot", None) == "king":
                entity.hitpoints = battle.players[entity.player_id].king_tower_hp

    engine, projection = _projection(battles)
    actual = tensor_objective_potential_p0(
        engine.runtime, projection.rewards.starting_tower_hp
    )
    expected = torch.tensor(
        [objective_potential_p0(battle) for battle in battles],
        dtype=torch.float64,
    )
    assert torch.equal(actual, expected)


def test_dense_reward_terminal_bonus_and_outcome_are_exact_and_one_shot() -> None:
    battles = [BattleState(), BattleState()]
    engine, projection = _projection(battles)
    runtime = engine.runtime
    runtime.battle.tower_hp[0, 1, 0] -= 123.0
    battles[0].players[1].left_tower_hp -= 123.0
    runtime.battle.game_over[1] = True
    runtime.battle.winner[1] = 1
    battles[1].game_over = True
    battles[1].winner = 1

    result = projection.project_reward_outcome()
    expected_potential = torch.tensor(
        [objective_potential_p0(battle) for battle in battles],
        dtype=torch.float64,
    )
    assert torch.equal(result.potential_p0, expected_potential)
    assert result.dense_reward[0].tolist() == [
        expected_potential[0],
        -expected_potential[0],
    ]
    assert result.reward[1].tolist() == [-1.0, 1.0]
    assert result.outcome.tolist() == [[0.0, 0.0], [-1.0, 1.0]]
    assert result.win_probability_p0.tolist() == [
        objective_win_prob_p0(battles[0]),
        0.0,
    ]

    repeated = projection.project_reward_outcome()
    assert repeated.reward.tolist() == [[0.0, -0.0], [0.0, -0.0]]


def test_public_projection_separates_critic_and_exposes_card_play_timeline() -> None:
    battle = BattleState(time=12.5)
    battle.players[0].elixir = 10.0
    battle.players[0].hand = ["Knight", "Zap", "Cannon", "Fireball"]
    sources = [battle]
    engine, projection = _projection(sources)
    result = projection.step_and_capture(
        torch.tensor([[DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    assert result.committed.tolist() == [True]
    command = result.deployment.ingress.commands
    command_x = int(command.world_x_units[0].item())
    command_y = int(command.world_y_units[0].item())

    public = projection.project_public()
    critic = projection.project_privileged_critic()
    assert not hasattr(public.structured, "critic_card_ids")
    assert hasattr(critic, "card_ids")
    assert public.events.clock_seconds.tolist() == [[12.55, 12.55]]
    assert public.events.valid[:, :, 0].tolist() == [[True, True]]
    assert public.events.play_time_seconds[:, :, 0].tolist() == [[12.55, 12.55]]
    assert public.events.owner[:, :, 0].tolist() == [[0, 0]]
    assert public.events.own[:, :, 0].tolist() == [[True, False]]
    np.testing.assert_array_equal(
        public.events.deployment_x[:, :, 0].numpy(),
        np.asarray(
            [[command_x / 18_000.0, (18_000 - command_x) / 18_000.0]],
            dtype=np.float32,
        ),
    )
    np.testing.assert_array_equal(
        public.events.deployment_y[:, :, 0].numpy(),
        np.asarray(
            [[command_y / 32_000.0, (32_000 - command_y) / 32_000.0]],
            dtype=np.float32,
        ),
    )
    expected_token = projection.observations.structured_builder.token_id("Knight")
    assert public.events.card_ids[:, :, 0].tolist() == [
        [expected_token, expected_token]
    ]

    engine.runtime.battle.time += 0.5
    aged = projection.project_public_events()
    assert aged.age_seconds[:, :, 0].tolist() == [[0.5, 0.5]]
    assert engine.runtime.events.count.tolist() == [0]


def test_captured_public_event_owner_survives_source_cleanup() -> None:
    battle = BattleState()
    battle.players[0].elixir = 10.0
    battle.players[0].hand = ["Knight", "Zap", "Cannon", "Fireball"]
    engine, projection = _projection([battle])
    result = projection.step_and_capture(
        torch.tensor([[DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    spawned = result.deployment.deployment.allocation
    knight_id = int(spawned.entity_ids[0][spawned.valid[0]][0].item())
    runtime = engine.runtime
    slot = int(
        runtime.entity_pool.slots_for_ids(torch.tensor([[knight_id]]))[0, 0].item()
    )
    before = projection.project_public_events()
    assert before.owner[:, :, 0].tolist() == [[0, 0]]

    runtime.entity_pool.active[0, slot] = False
    runtime.battle.entity_id[0, slot] = 0
    after = projection.project_public_events()
    assert after.owner[:, :, 0].tolist() == [[0, 0]]
    assert after.valid[:, :, 0].tolist() == [[True, True]]


def test_tick_capture_does_not_clear_rejected_row_state() -> None:
    supported = BattleState()
    rejected = BattleState()
    rejected.players[0].elixir = 10.0
    rejected.players[0].hand = ["ArcherQueen", "Zap", "Cannon", "Fireball"]
    engine, projection = _projection([supported, rejected])
    engine.runtime.events.append(
        phase=TickPhase.STATUS,
        opcode=RuntimeEventOpcode.STATUS,
        valid=torch.tensor([[False], [True]]),
        payload=torch.tensor([[0], [77]]),
    )

    result = projection.step_and_capture(
        torch.tensor(
            [
                [NO_OP_ACTION, NO_OP_ACTION],
                [DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION],
            ]
        ),
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )

    assert result.committed.tolist() == [True, False]
    assert engine.runtime.events.count.tolist() == [0, 1]
    assert engine.runtime.events.payload[1, 0].item() == 77


def test_first_tick_card_play_time_survives_eight_tick_decision_interval() -> None:
    battle = BattleState()
    battle.players[0].elixir = 10.0
    battle.players[0].hand = ["Knight", "Zap", "Cannon", "Fireball"]
    _, projection = _projection([battle])
    first = projection.step_and_capture(
        torch.tensor([[DEPLOY_KNIGHT_FAR_FROM_COMBAT, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    assert first.committed.tolist() == [True]
    first_time = float(projection.project_public_events().play_time_seconds[0, 0, 0])
    for _ in range(7):
        result = projection.step_and_capture(
            torch.tensor([[NO_OP_ACTION, NO_OP_ACTION]]),
            player_order=torch.tensor([[0, 1]]),
        )
        assert result.committed.tolist() == [True]
    events = projection.consume_public_events()
    assert float(events.play_time_seconds[0, 0, 0]) == first_time == 0.05
    assert float(events.age_seconds[0, 0, 0]) == 0.35
    assert projection.public_event_count.tolist() == [0]


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_resident_outputs_are_cuda_resident_and_cpu_exact() -> None:
    cpu_sources = [BattleState(), BattleState(time=119.9)]
    cuda_sources = [battle.clone() for battle in cpu_sources]
    cpu_engine, cpu = _projection(cpu_sources)
    cuda_engine, cuda = _projection(cuda_sources, device="cuda")
    assert cpu_engine.step().committed.all()
    assert cuda_engine.step().committed.all()

    cpu_structured = cpu.project_structured()
    cuda_structured = cuda.project_structured()
    assert cuda_structured.entity_features.device.type == "cuda"
    assert torch.equal(
        cuda_structured.entity_features.cpu(), cpu_structured.entity_features
    )
    cpu_cv = cpu.project_cv()
    cuda_cv = cuda.project_cv()
    assert cuda_cv.board.device.type == "cuda"
    assert torch.equal(cuda_cv.board.cpu(), cpu_cv.board)
    assert torch.equal(
        cuda.project_reward_outcome().reward.cpu(),
        cpu.project_reward_outcome().reward,
    )
