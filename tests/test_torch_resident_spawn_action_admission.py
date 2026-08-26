from __future__ import annotations

import copy
import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace

DEPLOY_SLOT_ZERO = 12 * 18 + 14


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _action_battle(card_name: str, *, seed: int = 810_000) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card("Knight")
    assert target_stats is not None
    battle._spawn_unit_at_position(
        Position(14.5, 15.0),
        1,
        target_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[1]
    target.hitpoints = 10_000
    target.max_hitpoints = 10_000
    target.stun_timer = 100.0
    target.attack_cooldown = 10.0
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    player = battle.players[0]
    player.hand = [card_name, "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle


def _active_battle(card_name: str) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(card_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(Troop, Position(9.0, 10.0), 0, source_stats)
    target = battle._spawn_entity(Troop, Position(9.0, 11.0), 1, target_stats)
    for entity in (source, target):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    source.target_id = target.id
    source.attack_cooldown = 0.0
    target.attack_cooldown = 10.0
    return battle


def _engine(battles: list[BattleState], device: str) -> TensorResidentEngine:
    return TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=8,
        max_objects=8,
        event_capacity=512,
    )


def _assert_public_state(oracle: BattleState, engine: TensorResidentEngine) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    slots = torch.where(active)[0]
    entity_ids = core.entity_id[0, slots].tolist()
    assert entity_ids == list(oracle.entities)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert core.time.item() == oracle.time
    assert core.tick.item() == oracle.tick
    assert core.rng.python_state(0) == oracle.rng.getstate()
    for slot, entity_id in zip(slots.tolist(), entity_ids, strict=True):
        entity = oracle.entities[entity_id]
        assert core.entity_x_units[0, slot].item() == round(entity.position.x * 1_000)
        assert core.entity_y_units[0, slot].item() == round(entity.position.y * 1_000)
        assert core.entity_hp[0, slot].item() == entity.hitpoints
        assert engine.runtime.status.stun_timer[0, slot].item() == entity.stun_timer


def test_ice_wizard_action_owner_matches_complete_real_interaction(
    tensor_device: str,
) -> None:
    source = _action_battle("IceWizard")
    oracle = copy.deepcopy(source)
    engine = _engine([source], tensor_device)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    owner = engine.mechanic_deployment.catalog.owner_index("spawn_area_deployment")
    initial_hp = oracle.entities[1].hitpoints
    interacted = False

    for tick in range(61):
        action = DEPLOY_SLOT_ZERO if tick == 0 else NO_OP_ACTION
        actions = (action, NO_OP_ACTION)
        player_order = [0, 1]
        oracle.rng.shuffle(player_order)
        for player_id in player_order:
            assert action_space.apply_action(oracle, player_id, actions[player_id])
        oracle.step_logic_ticks(1)

        result = engine.step(torch.tensor([actions], device=engine.device))

        assert result.committed.tolist() == [True]
        _assert_public_state(oracle, engine)
        if tick == 0:
            spawned = result.deployment.deployment.allocation
            spawned_id = int(spawned.entity_ids[0][spawned.valid[0]][0].item())
            spawned_slot = int(spawned.slots[0][spawned.valid[0]][0].item())
            assert spawned_id == 2
            assert (
                engine.mechanic_deployment.state.owner_entity_id[
                    owner, 0, spawned_slot
                ].item()
                == spawned_id
            )
        interacted |= engine.runtime.battle.entity_hp[0, 0].item() < initial_hp

    assert interacted


@pytest.mark.parametrize(
    ("card_name", "opcode"),
    (
        ("ElectroWizard", "MultipleTargetAttack"),
        ("MegaKnight", "MegaKnightSlam"),
    ),
)
def test_action_full_co_mechanic_closure_remains_fail_closed(
    tensor_device: str,
    card_name: str,
    opcode: str,
) -> None:
    engine = _engine([_action_battle(card_name)], tensor_device)
    actions = torch.tensor(
        [[DEPLOY_SLOT_ZERO, NO_OP_ACTION]],
        dtype=torch.int64,
        device=engine.device,
    )

    preflight = engine.preflight(actions)
    result = engine.step(
        actions, player_order=torch.tensor([[0, 1]], device=engine.device)
    )

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.ACTION_MECHANIC]
    assert preflight.mechanic_opcode_present[0, MECHANIC_OPCODE[opcode]].item()
    assert result.committed.tolist() == [False]
    assert engine.runtime.battle.entity_id[0, :2].tolist() == [1, 0]


def test_mixed_supported_and_rejected_actions_commit_atomically(
    tensor_device: str,
) -> None:
    supported = _action_battle("IceWizard", seed=810_001)
    rejected = _action_battle("ElectroWizard", seed=810_002)
    engine = _engine([supported, rejected], tensor_device)
    actions = torch.tensor(
        [[DEPLOY_SLOT_ZERO, NO_OP_ACTION], [DEPLOY_SLOT_ZERO, NO_OP_ACTION]],
        dtype=torch.int64,
        device=engine.device,
    )
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_rng = engine.runtime.battle.rng.python_state(1)
    owner = engine.mechanic_deployment.catalog.owner_index("spawn_area_deployment")

    preflight = engine.preflight(actions)
    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1], [0, 1]], device=engine.device),
    )

    assert preflight.supported.tolist() == [True, False]
    assert result.committed.tolist() == [True, False]
    assert engine.runtime.battle.entity_id[0, :3].tolist() == [1, 2, 0]
    assert engine.mechanic_deployment.state.owner_entity_id[owner, 0, 1].item() == 2
    assert engine.runtime.battle.time[1] == before_time[1]
    assert torch.equal(engine.runtime.battle.entity_id[1], before_ids[1])
    assert engine.runtime.battle.rng.python_state(1) == before_rng


def test_workspace_retains_spawn_area_deployment_owner(tensor_device: str) -> None:
    engine = _engine([_action_battle("IceWizard")], tensor_device)
    workspace = TensorResidentWorkspace(engine)
    actions = torch.tensor(
        [[DEPLOY_SLOT_ZERO, NO_OP_ACTION]],
        dtype=torch.int64,
        device=engine.device,
    )
    owner = engine.mechanic_deployment.catalog.owner_index("spawn_area_deployment")
    scratch_pointer = (
        workspace.scratch.mechanic_deployment.state.owner_entity_id.data_ptr()
    )

    result = workspace.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )

    assert result.committed.tolist() == [True]
    assert engine.mechanic_deployment.state.owner_entity_id[owner, 0, 1].item() == 2
    assert scratch_pointer == (
        workspace.scratch.mechanic_deployment.state.owner_entity_id.data_ptr()
    )
    assert scratch_pointer != (
        engine.mechanic_deployment.state.owner_entity_id.data_ptr()
    )
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.mechanic_deployment.state.owner_entity_id,
        engine.mechanic_deployment.state.owner_entity_id,
    )


def test_active_multiple_target_row_fails_closed_without_mutation(
    tensor_device: str,
) -> None:
    engine = _engine([_active_battle("ElectroWizard")], tensor_device)
    before_time = engine.runtime.battle.time.clone()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_hp = engine.runtime.battle.entity_hp.clone()
    before_status = engine.runtime.status.stun_timer.clone()
    before_events = engine.runtime.events.count.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)

    preflight = engine.preflight()
    result = engine.step(player_order=torch.tensor([[0, 1]], device=engine.device))

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.ACTIVE_MECHANIC]
    assert preflight.mechanic_opcode_present[
        0, MECHANIC_OPCODE["MultipleTargetAttack"]
    ].item()
    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.time, before_time)
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert torch.equal(engine.runtime.status.stun_timer, before_status)
    assert torch.equal(engine.runtime.events.count, before_events)
    assert engine.runtime.battle.rng.python_state(0) == before_rng
