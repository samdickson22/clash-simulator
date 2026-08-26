from __future__ import annotations

import math
import random
from collections import deque
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.deployment import TensorDeploymentCatalog
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_firecracker import TensorResidentBurstProjectiles
from clasher.torch_sim.resident_mechanic_deployment import (
    TensorMechanicDeploymentCatalog,
    TensorResidentMechanicDeployment,
)
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.runtime_state import TensorBattleRuntime

DEPLOY_FIRECRACKER = 10 * 18 + 3


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
    *,
    hitpoints: float,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = cast(Troop, battle._spawn_entity(Troop, position, player, stats))
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.stun_timer = 100.0
    entity.attack_cooldown = 100.0
    entity.hitpoints = hitpoints
    entity.max_hitpoints = max(hitpoints, 1.0)
    return entity


def _battle() -> tuple[BattleState, tuple[int, int, int]]:
    battle = BattleState(fast_path=False, rng=random.Random(8_260_401))
    battle.entities.clear()
    battle.next_entity_id = 1
    primary = _spawn(
        battle,
        "Knight",
        1,
        Position(3.5, 15.5),
        hitpoints=64.0,
    )
    center = _spawn(
        battle,
        "Knight",
        1,
        Position(3.5, 19.5),
        hitpoints=1_000.0,
    )
    angle = math.radians(32.0)
    outer = _spawn(
        battle,
        "Knight",
        1,
        Position(
            3.5 + math.sin(angle) * 4.0,
            15.5 + math.cos(angle) * 4.0,
        ),
        hitpoints=64.0,
    )
    player = battle.players[0]
    player.hand = ["Firecracker", "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle, (primary.id, center.id, outer.id)


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    slots = torch.nonzero(
        runtime.battle.entity_id[0] == entity_id,
        as_tuple=False,
    ).flatten()
    assert slots.numel() == 1
    return int(slots.item())


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
        event_capacity=4_096,
    )
    deployment_catalog = TensorDeploymentCatalog.compile(battle.card_loader, cards)
    capabilities = TensorMechanicDeploymentCatalog.compile(
        cards,
        {"burst_projectile": (MECHANIC_OPCODE["AttackRecoil"],)},
        loader=battle.card_loader,
    )
    return runtime, TensorResidentMechanicDeployment(
        capabilities,
        deployment_catalog,
        runtime,
    )


def test_firecracker_action_to_burst_is_native_and_policy_visible(
    tensor_device: str,
) -> None:
    boundary, target_ids = _battle()
    action_boundary = boundary.clone()
    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        action_boundary,
        0,
        DEPLOY_FIRECRACKER,
    )
    source_id = max(action_boundary.entities)
    source = cast(Troop, action_boundary.entities[source_id])
    assert source.card_stats.name == "Firecracker"

    runtime, deployment = _deployment_stack(boundary, tensor_device)
    actions = torch.tensor(
        [[DEPLOY_FIRECRACKER, NO_OP_ACTION]],
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
    assert deployed.owner_mask(deployment.catalog, "burst_projectile").sum().item() == 1
    allocation = deployed.deployment.deployment.allocation
    assert allocation.entity_ids[0][allocation.valid[0]].tolist() == [source_id]
    source_slot = _slot(runtime, source_id)
    deployed_x = round(source.position.x * 1_000)
    deployed_y = round(source.position.y * 1_000)
    assert runtime.battle.entity_x_units[0, source_slot].item() == deployed_x
    assert runtime.battle.entity_y_units[0, source_slot].item() == deployed_y

    owner = TensorResidentBurstProjectiles.from_battles(
        runtime,
        [action_boundary],
        parent_capacity=4,
        child_capacity=12,
    )
    source_card = runtime.battle.card_to_id["Firecracker"]
    assert owner.catalog.supported[source_card].item()
    assert owner.catalog.child_count[source_card].item() == 5
    assert owner.catalog.child_range_units[source_card].item() == 5_000
    assert owner.catalog.recoil_distance_units[source_card].item() == 1_000

    primary_slot, center_slot, outer_slot = (
        _slot(runtime, entity_id) for entity_id in target_ids
    )
    committed = owner.commit_attacks_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        target_slots=torch.tensor(
            [[primary_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert committed.committed.tolist() == [True]
    assert committed.accepted.tolist() == [True]
    assert committed.recoil_started.tolist() == [[True]]

    starting_y = int(runtime.battle.entity_y_units[0, source_slot].item())
    maximum_children = 0
    saw_fan_out = False
    for _ in range(32):
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert not result.capacity_rejected.any()
        maximum_children = max(maximum_children, int(owner.child_active.sum().item()))
        saw_fan_out |= bool(result.spawned_children.item() == 5)
        if (
            saw_fan_out
            and not owner.parent_active.any()
            and not owner.child_active.any()
            and not owner.recoil_active.any()
        ):
            break
    else:
        pytest.fail("Firecracker retained projectile lifecycle did not settle")

    core = runtime.battle
    assert runtime.supported.tolist() == [True]
    assert saw_fan_out
    assert maximum_children == 5
    assert core.entity_x_units[0, source_slot].item() == deployed_x
    recoil_y = int(core.entity_y_units[0, source_slot].item())
    assert starting_y - 1_050 <= recoil_y <= starting_y - 800
    assert not core.entity_active[0, primary_slot].item()
    assert core.entity_hp[0, primary_slot].item() == 0.0
    assert core.entity_active[0, center_slot].item()
    assert core.entity_hp[0, center_slot].item() == 936.0
    assert not core.entity_active[0, outer_slot].item()
    assert core.entity_hp[0, outer_slot].item() == 0.0

    projector = TensorObservationProjector.from_battles(
        [action_boundary],
        state=core,
        structured_builder=StructuredObservationBuilder(max_entities=24),
        cv_builder=CvObservationBuilder(),
    )
    projected = projector.project_structured()
    actor_mask = projected.entity_mask[0, 0]
    actor_features = projected.entity_features[0, 0][actor_mask]
    assert int((actor_features[:, 2] > 0.5).sum().item()) == 1
    assert int((actor_features[:, 3] > 0.5).sum().item()) == 1
    own = actor_features[actor_features[:, 2] > 0.5]
    enemy = actor_features[actor_features[:, 3] > 0.5]
    assert own[0, 1].item() == pytest.approx(recoil_y / 32_000.0, abs=1e-6)
    assert enemy[0, 9].item() == pytest.approx(0.936, abs=1e-6)


def test_full_engine_firecracker_attack_recoil_and_fan_out_are_resident(
    tensor_device: str,
) -> None:
    boundary, target_ids = _battle()
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=tensor_device,
        max_entities=24,
        max_objects=16,
        event_capacity=4_096,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        [boundary],
        structured_builder=StructuredObservationBuilder(max_entities=24),
        cv_builder=CvObservationBuilder(),
    )
    deploy = torch.tensor(
        [[DEPLOY_FIRECRACKER, NO_OP_ACTION]],
        dtype=torch.int64,
        device=engine.device,
    )
    assert engine.preflight(deploy).supported.tolist() == [True]
    first = engine.step(
        deploy, player_order=torch.tensor([[0, 1]], device=engine.device)
    )
    assert first.committed.tolist() == [True]
    allocation = first.deployment.deployment.allocation
    source_id = int(allocation.entity_ids[0][allocation.valid[0]][0].item())
    source_slot = _slot(engine.runtime, source_id)
    deployed_y = int(engine.runtime.battle.entity_y_units[0, source_slot].item())
    primary_slot, center_slot, outer_slot = (
        _slot(engine.runtime, entity_id) for entity_id in target_ids
    )

    no_op = torch.full(
        (1, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=engine.device,
    )
    saw_parent = False
    saw_five_children = False
    for _ in range(96):
        assert engine.preflight(no_op).supported.tolist() == [True]
        result = engine.step(
            no_op, player_order=torch.tensor([[0, 1]], device=engine.device)
        )
        assert result.committed.tolist() == [True]
        saw_parent |= bool(engine.burst_projectiles.parent_active.any().item())
        saw_five_children |= (
            int(engine.burst_projectiles.child_active.sum().item()) == 5
        )
        settled = (
            saw_five_children
            and not engine.burst_projectiles.parent_active.any()
            and not engine.burst_projectiles.child_active.any()
            and not engine.burst_projectiles.recoil_active.any()
        )
        if settled:
            break
    else:
        pytest.fail("full-engine Firecracker burst did not settle")

    core = engine.runtime.battle
    assert engine.runtime.supported.tolist() == [True]
    assert saw_parent
    assert saw_five_children
    recoil_y = int(core.entity_y_units[0, source_slot].item())
    assert deployed_y - 1_050 <= recoil_y <= deployed_y - 800
    assert not core.entity_active[0, primary_slot].item()
    assert core.entity_hp[0, primary_slot].item() == 0.0
    assert core.entity_active[0, center_slot].item()
    assert core.entity_hp[0, center_slot].item() == 936.0
    assert not core.entity_active[0, outer_slot].item()
    assert core.entity_hp[0, outer_slot].item() == 0.0

    projected = projector.project_public_structured()
    actor = projected.entity_features[0, 0][projected.entity_mask[0, 0]]
    assert int((actor[:, 2] > 0.5).sum().item()) == 1
    assert int((actor[:, 3] > 0.5).sum().item()) == 1
    own = actor[actor[:, 2] > 0.5]
    enemy = actor[actor[:, 3] > 0.5]
    assert own[0, 1].item() == pytest.approx(recoil_y / 32_000.0, abs=1e-6)
    assert enemy[0, 9].item() == pytest.approx(0.936, abs=1e-6)
