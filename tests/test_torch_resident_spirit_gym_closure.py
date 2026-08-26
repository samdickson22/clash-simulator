from __future__ import annotations

import copy
import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace

DEPLOY_SPIRIT = 12 * 18 + 14
POSITION_TOLERANCE_UNITS = 250
STATUS_TOLERANCE_SECONDS = 0.05 + 1e-9


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle(
    card_name: str,
    target_x: tuple[float, ...],
    *,
    target_name: str = "Knight",
    seed: int = 8_260_101,
) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card(target_name)
    assert target_stats is not None
    for x in target_x:
        battle._spawn_unit_at_position(
            Position(x, 15.0),
            1,
            target_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        target = battle.entities[battle.next_entity_id - 1]
        target.hitpoints = 10_000.0
        target.max_hitpoints = 10_000.0
        target.stun_timer = 0.0
        target.attack_cooldown = 10.0
        target._spawn_hook_pending = False
        target._spawn_hook_fired = True
    player = battle.players[0]
    player.hand = [card_name, "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle


def _engine(battles: list[BattleState], device: str) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=16,
        max_objects=16,
        event_capacity=1_024,
    )


def _projector(
    engine: TensorResidentEngine,
    battles: list[BattleState],
) -> ResidentOutputProjector:
    return ResidentOutputProjector.from_engine(
        engine,
        battles,
        structured_builder=StructuredObservationBuilder(max_entities=16),
        cv_builder=CvObservationBuilder(),
    )


def _assert_high_fidelity_public_state(
    oracle: BattleState,
    engine: TensorResidentEngine,
) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    tensor_ids = {
        int(value) for value in core.entity_id[0, active].tolist() if int(value) > 0
    }
    assert tensor_ids == set(oracle.entities)
    all_ids = core.entity_id[0].tolist()
    for entity_id, entity in oracle.entities.items():
        slot = all_ids.index(entity_id)
        assert (
            abs(int(core.entity_x_units[0, slot]) - round(entity.position.x * 1_000))
            <= POSITION_TOLERANCE_UNITS
        )
        assert (
            abs(int(core.entity_y_units[0, slot]) - round(entity.position.y * 1_000))
            <= POSITION_TOLERANCE_UNITS
        )
        assert float(core.entity_hp[0, slot]) == pytest.approx(
            float(entity.hitpoints), abs=1e-6
        )
        assert float(engine.runtime.status.stun_timer[0, slot]) == pytest.approx(
            float(entity.stun_timer), abs=STATUS_TOLERANCE_SECONDS
        )


def _enemy_policy_features(projector: ResidentOutputProjector) -> torch.Tensor:
    observation = projector.project_public_structured()
    features = observation.entity_features[0, 0]
    valid = observation.entity_mask[0, 0] & (features[:, 3] > 0.5)
    return features[valid]


@pytest.mark.parametrize(
    ("card_name", "target_x", "minimum_damaged"),
    (
        ("IceSpirit", (14.5,), 1),
        ("ElectroSpirit", (14.5, 13.5, 12.5), 3),
    ),
)
def test_action_to_real_first_impact_is_policy_visible_within_one_tick(
    tensor_device: str,
    card_name: str,
    target_x: tuple[float, ...],
    minimum_damaged: int,
) -> None:
    boundary = _battle(card_name, target_x)
    oracle = copy.deepcopy(boundary)
    engine = _engine([boundary], tensor_device)
    projector = _projector(engine, [boundary])
    target_ids = tuple(oracle.entities)
    initial_hp = {
        entity_id: oracle.entities[entity_id].hitpoints for entity_id in target_ids
    }
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, DEPLOY_SPIRIT)
    tensor_first_impact: int | None = None
    oracle_first_impact: int | None = None
    previous_policy_stun = float(_enemy_policy_features(projector)[:, 14].amax())
    policy_saw_impact = False
    saw_owner_signal = False

    for tick in range(40):
        oracle.step_logic_ticks(1)
        action = DEPLOY_SPIRIT if tick == 0 else NO_OP_ACTION
        result = engine.step(
            torch.tensor([[action, NO_OP_ACTION]], device=engine.device),
            player_order=torch.tensor([[0, 1]], device=engine.device),
        )
        assert result.committed.tolist() == [True], engine.diagnose_preflight()
        _assert_high_fidelity_public_state(oracle, engine)

        tensor_ids = engine.runtime.battle.entity_id[0].tolist()
        tensor_damage = {
            entity_id: initial_hp[entity_id]
            - float(engine.runtime.battle.entity_hp[0, tensor_ids.index(entity_id)])
            for entity_id in target_ids
        }
        oracle_damage = {
            entity_id: initial_hp[entity_id] - oracle.entities[entity_id].hitpoints
            for entity_id in target_ids
        }
        if tensor_first_impact is None and any(
            value > 0 for value in tensor_damage.values()
        ):
            tensor_first_impact = tick
            policy = _enemy_policy_features(projector)
            policy_saw_impact = bool((policy[:, 9] < 0.9999).any())
            policy_stun = float(policy[:, 14].amax())
            assert policy_stun > previous_policy_stun
        if oracle_first_impact is None and any(
            value > 0 for value in oracle_damage.values()
        ):
            oracle_first_impact = tick
        previous_policy_stun = float(_enemy_policy_features(projector)[:, 14].amax())

        if card_name == "IceSpirit":
            saw_owner_signal |= bool(
                result.ice_spirit and result.ice_spirit.landed.any()
            )
        else:
            saw_owner_signal |= bool(
                result.chain_impacts and result.chain_impacts.materialized.any()
            )
        damaged = sum(value > 0 for value in tensor_damage.values())
        chain_finished = (
            card_name == "IceSpirit" or not engine.chain_impacts.active.any()
        )
        if damaged >= minimum_damaged and chain_finished:
            break

    assert tensor_first_impact is not None
    assert oracle_first_impact is not None
    assert abs(tensor_first_impact - oracle_first_impact) <= 1
    assert policy_saw_impact
    assert saw_owner_signal
    final_ids = engine.runtime.battle.entity_id[0].tolist()
    final_damage = sum(
        float(engine.runtime.battle.entity_hp[0, final_ids.index(entity_id)])
        < initial_hp[entity_id]
        for entity_id in target_ids
    )
    assert final_damage >= minimum_damaged


def test_workspace_commits_supported_spirit_and_rolls_back_unsafe_peer() -> None:
    supported = _battle("IceSpirit", (14.5,), seed=8_260_102)
    unsafe = _battle(
        "ElectroSpirit",
        (14.5,),
        target_name="Guards",
        seed=8_260_103,
    )
    engine = _engine([supported, unsafe], "cpu")
    workspace = TensorResidentWorkspace(engine)
    actions = torch.tensor(
        [[DEPLOY_SPIRIT, NO_OP_ACTION], [DEPLOY_SPIRIT, NO_OP_ACTION]],
        dtype=torch.int64,
    )
    before_ids = engine.runtime.battle.entity_id[1].clone()
    before_ice = engine.ice_spirit.entity_card[1].clone()
    before_chain = engine.chain_impacts.entity_card[1].clone()
    before_electro = engine.electro_jump_active[1].clone()
    before_owner = engine.mechanic_deployment.state.owner_entity_id[:, 1].clone()

    preflight = engine.preflight(actions)
    result = workspace.step(
        actions,
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )

    assert preflight.supported.tolist() == [True, False]
    assert preflight.reason_code[1].item() == int(
        ResidentUnsupportedReason.ACTION_MECHANIC
    )
    assert result.committed.tolist() == [True, False]
    assert torch.equal(engine.runtime.battle.entity_id[1], before_ids)
    assert torch.equal(engine.ice_spirit.entity_card[1], before_ice)
    assert torch.equal(engine.chain_impacts.entity_card[1], before_chain)
    assert torch.equal(engine.electro_jump_active[1], before_electro)
    assert torch.equal(
        engine.mechanic_deployment.state.owner_entity_id[:, 1], before_owner
    )
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.electro_jump_active,
        engine.electro_jump_active,
    )


def test_spirit_consumes_only_itself_while_ordinary_friendly_keeps_moving() -> None:
    boundary = _battle("IceSpirit", (14.5,), seed=8_260_104)
    # Keep the hostile anchor stationary so this test isolates whether the
    # unrelated friendly mover is incorrectly frozen by spirit ownership.
    boundary.entities[1].stun_timer = 100.0
    knight = boundary.card_loader.get_card("Knight")
    assert knight is not None
    boundary._spawn_unit_at_position(
        Position(13.0, 10.0),
        0,
        knight,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    mover_id = boundary.next_entity_id - 1
    boundary.entities[mover_id]._spawn_hook_pending = False
    boundary.entities[mover_id]._spawn_hook_fired = True
    start_y = boundary.entities[mover_id].position.y
    oracle = copy.deepcopy(boundary)
    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        oracle, 0, DEPLOY_SPIRIT
    )
    engine = _engine([boundary], "cpu")

    saw_impact = False
    for tick in range(40):
        oracle.step_logic_ticks(1)
        action = DEPLOY_SPIRIT if tick == 0 else NO_OP_ACTION
        result = engine.step(
            torch.tensor([[action, NO_OP_ACTION]]),
            player_order=torch.tensor([[0, 1]]),
        )
        assert result.committed.tolist() == [True], engine.diagnose_preflight()
        _assert_high_fidelity_public_state(oracle, engine)
        saw_impact |= oracle.entities[1].hitpoints < 10_000.0
        if saw_impact:
            break

    assert saw_impact
    assert oracle.entities[mover_id].position.y > start_y
