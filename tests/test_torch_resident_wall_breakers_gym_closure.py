from __future__ import annotations

import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.deployment import TensorDeploymentCatalog
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_mechanic_deployment import (
    TensorMechanicDeploymentCatalog,
    TensorResidentMechanicDeployment,
)
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.resident_wall_breakers import TensorResidentDemolition
from clasher.torch_sim.runtime_state import TensorBattleRuntime

DEPLOY_WALL_BREAKERS = 14 * 18 + 9


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle() -> tuple[BattleState, int]:
    battle = BattleState(fast_path=False, rng=random.Random(8_260_301))
    target_stats = battle.card_loader.get_card("Cannon")
    assert target_stats is not None
    target = battle._spawn_entity(
        Building,
        Position(9.5, 15.5),
        1,
        target_stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    player = battle.players[0]
    player.hand = ["Wallbreakers", "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle, target.id


def _deployment_stack(
    battle: BattleState,
    device: str,
) -> tuple[TensorBattleRuntime, TensorResidentMechanicDeployment]:
    cards = TensorCardCatalog.compile(
        battle.card_loader,
        unique_cards_from_decks(load_deck_pool()),
        device=device,
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        catalog=cards,
        max_entities=24,
        event_capacity=512,
    )
    deployment_catalog = TensorDeploymentCatalog.compile(battle.card_loader, cards)
    capabilities = TensorMechanicDeploymentCatalog.compile(
        cards,
        {"demolition": (MECHANIC_OPCODE["WallBreakersDemolition"],)},
        loader=battle.card_loader,
    )
    return runtime, TensorResidentMechanicDeployment(
        capabilities,
        deployment_catalog,
        runtime,
    )


def test_wall_breakers_action_to_demolition_is_native_and_policy_visible(
    tensor_device: str,
) -> None:
    boundary, target_id = _battle()
    oracle_action_boundary = boundary.clone()
    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        oracle_action_boundary,
        0,
        DEPLOY_WALL_BREAKERS,
    )
    spawned_ids = tuple(
        entity_id
        for entity_id in oracle_action_boundary.entities
        if entity_id >= boundary.next_entity_id
    )
    assert len(spawned_ids) == 2

    runtime, deployment = _deployment_stack(boundary, tensor_device)
    actions = torch.tensor(
        [[DEPLOY_WALL_BREAKERS, NO_OP_ACTION]],
        dtype=torch.int64,
        device=runtime.device,
    )
    deployed = deployment.apply(
        runtime,
        actions,
        player_order=torch.tensor([[0, 1]], device=runtime.device),
    )

    assert deployed.committed.tolist() == [True]
    assert not deployed.capability_rejected.any()
    assert not deployed.deployment.unsupported_capacity.any()
    assert not deployed.deployment.deployment.unsupported_spell.any()
    allocation = deployed.deployment.deployment.allocation
    spawned_slots = allocation.slots[0][allocation.valid[0]]
    assert allocation.entity_ids[0][allocation.valid[0]].tolist() == list(spawned_ids)
    core = runtime.battle
    assert [
        core.card_names[int(core.entity_card[0, slot])]
        for slot in spawned_slots.tolist()
    ] == ["Wallbreakers", "Wallbreakers"]
    assert torch.equal(
        torch.stack(
            (
                core.entity_x_units[0, spawned_slots],
                core.entity_y_units[0, spawned_slots],
            ),
            dim=1,
        ).cpu(),
        torch.tensor([[8_750, 14_500], [10_250, 14_500]], dtype=torch.int32),
    )
    assert core.entity_hp[0, spawned_slots].tolist() == [330.0, 330.0]
    assert deployed.owner_mask(deployment.catalog, "demolition")[
        0, spawned_slots
    ].tolist() == [True, True]

    owner = TensorResidentDemolition.from_battles(
        runtime,
        [oracle_action_boundary],
    )
    before_target_hp = float(
        core.entity_hp[0, core.entity_id[0].tolist().index(target_id)].item()
    )

    # The shared character phase owns these clocks. The lifecycle owner must
    # remain inert until both bombers are actually deployed.
    pending = owner.step_(runtime)
    assert pending.committed.tolist() == [True]
    assert not pending.acquired_target_id[0, spawned_slots].any()
    assert not pending.moved[0, spawned_slots].any()
    assert not pending.primed[0, spawned_slots].any()
    assert not pending.detonated[0, spawned_slots].any()

    core.entity_deploy_delay[0, spawned_slots] = 0.0
    core.entity_placement_pending[0, spawned_slots] = False
    waypoints = torch.zeros(
        (1, runtime.max_entities, 2), dtype=torch.int64, device=runtime.device
    )
    waypoint_valid = torch.zeros(
        (1, runtime.max_entities), dtype=torch.bool, device=runtime.device
    )
    target_slot = core.entity_id[0].tolist().index(target_id)
    waypoints[0, spawned_slots] = torch.stack(
        (
            core.entity_x_units[0, target_slot].expand(spawned_slots.numel()),
            core.entity_y_units[0, target_slot].expand(spawned_slots.numel()),
        ),
        dim=1,
    ).to(torch.int64)
    waypoint_valid[0, spawned_slots] = True
    for _ in range(32):
        result = owner.step_(
            runtime,
            waypoint_units=waypoints,
            waypoint_valid=waypoint_valid,
        )
        if result.detonated[0, spawned_slots].all():
            break
    else:
        pytest.fail("both Wall Breakers did not reach and detonate on the building")

    assert result.committed.tolist() == [True]
    assert runtime.supported.tolist() == [True]
    assert result.acquired_target_id[0, spawned_slots].tolist() == [
        target_id,
        target_id,
    ]
    assert result.detonated[0, spawned_slots].tolist() == [True, True]
    assert not core.entity_active[0, spawned_slots].any()
    assert core.entity_hp[0, spawned_slots].tolist() == [0.0, 0.0]
    assert before_target_hp - float(core.entity_hp[0, target_slot].item()) == 700.0

    projector = TensorObservationProjector.from_battles(
        [oracle_action_boundary],
        state=core,
        structured_builder=StructuredObservationBuilder(max_entities=24),
        cv_builder=CvObservationBuilder(),
    )
    projected = projector.project_structured()
    actor_ids = projected.entity_ids[0, 0]
    actor_mask = projected.entity_mask[0, 0]
    wall_breaker_token = int(projector.entity_token[0, spawned_slots[0]].item())
    assert wall_breaker_token not in actor_ids[actor_mask].tolist()
    target_token = int(projector.entity_token[0, target_slot].item())
    target_index = actor_ids.tolist().index(target_token)
    expected_fraction = float(core.entity_hp[0, target_slot]) / float(
        core.entity_max_hp[0, target_slot]
    )
    assert projected.entity_features[0, 0, target_index, 9].item() == pytest.approx(
        expected_fraction,
        abs=1e-6,
    )


def test_engine_runs_dual_wall_breakers_to_policy_visible_demolition(
    tensor_device: str,
) -> None:
    boundary, target_id = _battle()
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=tensor_device,
        max_entities=12,
        max_objects=8,
        event_capacity=512,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        [boundary],
        structured_builder=StructuredObservationBuilder(max_entities=12),
        cv_builder=CvObservationBuilder(),
    )
    actions = torch.tensor(
        [[DEPLOY_WALL_BREAKERS, NO_OP_ACTION]],
        dtype=torch.int64,
        device=engine.device,
    )
    target_slot = engine.runtime.battle.entity_id[0].tolist().index(target_id)
    target_hp_before = float(engine.runtime.battle.entity_hp[0, target_slot].item())
    spawned_slots: torch.Tensor | None = None
    spawned_ids: list[int] = []
    detonation_count = 0
    demolition_damage = 0.0

    for tick in range(32):
        tick_actions = actions if tick == 0 else None
        assert engine.preflight(tick_actions).supported.tolist() == [True]
        result = engine.step(
            tick_actions,
            player_order=torch.tensor([[0, 1]], device=engine.device),
        )
        assert result.committed.tolist() == [True]
        assert result.demolition is not None
        if tick == 0:
            allocation = result.deployment.deployment.allocation
            spawned_slots = allocation.slots[0][allocation.valid[0]]
            spawned_ids = allocation.entity_ids[0][allocation.valid[0]].tolist()
            assert spawned_slots.numel() == 2
            assert torch.equal(
                torch.stack(
                    (
                        engine.runtime.battle.entity_x_units[0, spawned_slots],
                        engine.runtime.battle.entity_y_units[0, spawned_slots],
                    ),
                    dim=1,
                ).cpu(),
                torch.tensor(
                    [[8_750, 14_500], [10_250, 14_500]],
                    dtype=torch.int32,
                ),
            )
        detonation_count += int(result.demolition.detonated.sum().item())
        demolition_damage += float(result.demolition.damage[0, target_slot].item())
        if spawned_slots is not None and not engine.runtime.battle.entity_active[
            0, spawned_slots
        ].any():
            break
    else:
        pytest.fail("resident engine did not finish both Wall Breakers")

    assert detonation_count == 2
    assert engine.runtime.supported.tolist() == [True]
    assert spawned_slots is not None
    assert engine.runtime.battle.entity_hp[0, spawned_slots].tolist() == [0.0, 0.0]
    target_hp_after = float(engine.runtime.battle.entity_hp[0, target_slot].item())
    assert demolition_damage == 700.0
    # The building's ordinary lifetime decay continues during the approach;
    # the policy-visible total loss therefore includes more than demolition.
    assert target_hp_before - target_hp_after >= demolition_damage

    public = projector.project_public_structured()
    active_tokens = public.entity_ids[0, 0][public.entity_mask[0, 0]].tolist()
    wall_breaker_token = int(
        projector.observations.entity_token[0, spawned_slots[0]].item()
    )
    assert wall_breaker_token not in active_tokens
    target_token = int(projector.observations.entity_token[0, target_slot].item())
    target_index = public.entity_ids[0, 0].tolist().index(target_token)
    assert public.entity_features[0, 0, target_index, 9].item() == pytest.approx(
        target_hp_after
        / float(engine.runtime.battle.entity_max_hp[0, target_slot].item()),
        abs=1e-6,
    )
    assert len(spawned_ids) == 2
