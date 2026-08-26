from __future__ import annotations

import copy
import random
from collections import deque
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.mechanics.shared.multi_target import MultipleTargetAttack
from clasher.mechanics.shared.on_hit_buff import SerializedOnHitBuff
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.mechanic_dispatcher import TensorMechanicDispatcher
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_multi_target import TensorResidentMultiTargetAttacks
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.resident_spawn_area import TensorResidentSpawnAreas
from clasher.torch_sim.runtime_state import TensorBattleRuntime

DEPLOY_ELECTRO_WIZARD = 12 * 18 + 14


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        position,
        player_id,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    result = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    result.deploy_delay_remaining = 0.0
    result.placement_pending = False
    result.attack_cooldown = 0.0
    return result


def _boundary() -> tuple[BattleState, Troop, tuple[Troop, Troop]]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    targets = (
        _spawn(battle, "Knight", 1, Position(8.0, 13.0)),
        _spawn(battle, "Knight", 1, Position(10.0, 13.0)),
    )
    source = _spawn(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    source.target_id = targets[0].id
    source._spawn_hook_pending = True
    source._spawn_hook_fired = False
    for mechanic in source.mechanics:
        if type(mechanic).__name__ == "SpawnAreaEffect":
            mechanic._applied = False  # type: ignore[attr-defined]
    return battle, source, targets


def _action_boundary() -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(8_260_202))
    battle.entities.clear()
    battle.next_entity_id = 1
    targets = (
        _spawn(battle, "Knight", 1, Position(13.5, 15.0)),
        _spawn(battle, "Knight", 1, Position(15.5, 15.0)),
    )
    for target in targets:
        target.hitpoints = 10_000
        target.max_hitpoints = 10_000
        target.attack_cooldown = 10.0
        target._spawn_hook_pending = False
        target._spawn_hook_fired = True
    player = battle.players[0]
    player.hand = ["ElectroWizard", "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle


def _mechanic(entity: Entity, kind: type[object]) -> object:
    return next(item for item in entity.mechanics if isinstance(item, kind))


def _resolve_scalar_attack(
    battle: BattleState,
    source_id: int,
    primary_id: int,
) -> None:
    source = battle.entities[source_id]
    primary = battle.entities[primary_id]
    multiple = cast(MultipleTargetAttack, _mechanic(source, MultipleTargetAttack))
    on_hit = cast(SerializedOnHitBuff, _mechanic(source, SerializedOnHitBuff))
    multiple.on_attack_start(source, primary)
    primary.take_damage(source.damage)
    multiple.resolve_secondary_attack_hits(source, primary, source.damage, battle)
    on_hit.on_attack_hit(source, primary)


def test_landing_zap_then_two_target_attack_updates_policy_visible_state(
    tensor_device: str,
) -> None:
    """The production closure is a composition of two generic owners.

    This deliberately gates gameplay state instead of Python diagnostic event
    details: landing damage/stun, two-target damage/stun, and the next attack
    cooldown are the semantics that can affect a policy transition.
    """

    boundary, source, targets = _boundary()
    oracle = copy.deepcopy(boundary)
    runtime = TensorBattleRuntime.from_battles(
        [boundary],
        device=tensor_device,
        max_entities=8,
        event_capacity=128,
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [boundary])
    spawn_areas = TensorResidentSpawnAreas.from_battles(runtime, [boundary])
    multiple = TensorResidentMultiTargetAttacks.from_battles(dispatcher, [boundary])
    slots = {
        int(entity_id): slot
        for slot, entity_id in enumerate(runtime.battle.entity_id[0].tolist())
        if entity_id
    }
    source_slot = slots[source.id]

    oracle_source = cast(Troop, oracle.entities[source.id])
    oracle_source.on_spawn()
    oracle_area = oracle.entities[oracle.next_entity_id - 1]
    oracle_area.update(oracle.dt, oracle)
    materialized = spawn_areas.materialize_spawns_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    landing = spawn_areas.step_(runtime)
    assert materialized.committed.tolist() == [True]
    assert landing.committed.tolist() == [True]

    _resolve_scalar_attack(oracle, source.id, targets[0].id)
    started = torch.zeros_like(runtime.battle.entity_active)
    primary = torch.zeros_like(runtime.battle.entity_id)
    damage = torch.zeros_like(runtime.battle.entity_hp)
    started[0, source_slot] = True
    primary[0, source_slot] = slots[targets[0].id]
    damage[0, source_slot] = source.damage
    candidates = torch.zeros(
        (1, runtime.max_entities, runtime.max_entities),
        dtype=torch.bool,
        device=runtime.device,
    )
    for target in targets:
        candidates[0, source_slot, slots[target.id]] = source.can_attack_target(target)
    attack = multiple.commit_attacks_(
        runtime,
        dispatcher.mechanics,
        dispatcher.combat_world,
        attack_started=started,
        primary_target_slot=primary,
        damage=damage,
        damage_integer_kind=True,
        cooldown_after_seconds=1.8,
        candidate_mask=candidates,
    )
    assert attack.committed.tolist() == [True]
    assert attack.accepted[0, source_slot].item()
    assert attack.target_id[0, source_slot, :2].tolist() == [
        targets[0].id,
        targets[1].id,
    ]
    assert multiple.state.cooldown_seconds[0, source_slot].item() == 1.8

    for target in targets:
        slot = slots[target.id]
        expected = oracle.entities[target.id]
        assert runtime.battle.entity_hp[0, slot].item() == expected.hitpoints
        assert runtime.status.stun_timer[0, slot].item() == pytest.approx(
            expected.stun_timer
        )

    projector = TensorObservationProjector.from_battles(
        [boundary],
        state=runtime.battle,
        structured_builder=StructuredObservationBuilder(max_entities=8),
        cv_builder=CvObservationBuilder(),
    )
    projector.entity_stun.copy_(runtime.status.stun_timer)
    observation = projector.project_structured()
    enemy = observation.entity_features[0, 0]
    enemy = enemy[observation.entity_mask[0, 0] & (enemy[:, 3] > 0.5)]
    assert int((enemy[:, 9] < 0.9999).sum().item()) == 2
    assert int((enemy[:, 14] > 0.0).sum().item()) == 2


def test_full_action_lands_and_commits_first_dual_attack_without_fallback(
    tensor_device: str,
) -> None:
    boundary = _action_boundary()
    oracle = copy.deepcopy(boundary)
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=tensor_device,
        max_entities=16,
        max_objects=16,
        event_capacity=2_048,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        [boundary],
        structured_builder=StructuredObservationBuilder(max_entities=16),
        cv_builder=CvObservationBuilder(),
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    target_ids = (1, 2)
    initial_hp = {
        entity_id: oracle.entities[entity_id].hitpoints for entity_id in target_ids
    }
    landing_damage = 192.0
    attack_damage = 117.0
    saw_landing = False
    saw_dual_attack = False

    for tick in range(48):
        action = DEPLOY_ELECTRO_WIZARD if tick == 0 else NO_OP_ACTION
        actions = (action, NO_OP_ACTION)
        player_order = [0, 1]
        oracle.rng.shuffle(player_order)
        for player_id in player_order:
            assert action_space.apply_action(
                oracle,
                player_id,
                actions[player_id],
            )
        oracle.step_logic_ticks(1)

        action_tensor = torch.tensor(
            [actions], dtype=torch.int64, device=engine.device
        )
        assert engine.preflight(action_tensor).supported.tolist() == [True]
        result = engine.step(
            action_tensor,
            player_order=torch.tensor([player_order], device=engine.device),
        )
        assert result.committed.tolist() == [True], engine.diagnose_preflight(
            action_tensor
        )

        resident_ids = engine.runtime.battle.entity_id[0].tolist()
        for entity_id in target_ids:
            slot = resident_ids.index(entity_id)
            assert float(engine.runtime.battle.entity_hp[0, slot]) == pytest.approx(
                float(oracle.entities[entity_id].hitpoints), abs=1e-6
            )
            assert float(engine.runtime.status.stun_timer[0, slot]) == pytest.approx(
                float(oracle.entities[entity_id].stun_timer), abs=0.05 + 1e-9
            )
        damage = {
            entity_id: initial_hp[entity_id] - oracle.entities[entity_id].hitpoints
            for entity_id in target_ids
        }
        saw_landing |= all(value >= landing_damage for value in damage.values())
        saw_dual_attack |= all(
            value >= landing_damage + attack_damage for value in damage.values()
        )
        if saw_dual_attack:
            break
    else:
        pytest.fail("Electro Wizard did not complete its first two-target attack")

    assert saw_landing
    observation = projector.project_public_structured()
    enemy = observation.entity_features[0, 0]
    enemy = enemy[observation.entity_mask[0, 0] & (enemy[:, 3] > 0.5)]
    assert int((enemy[:, 9] < 0.9999).sum().item()) >= 2
    assert int((enemy[:, 14] > 0.0).sum().item()) >= 2
