from __future__ import annotations

import copy
import random
from collections import deque

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import ResidentOutputProjector

DEPLOY_DRAGON = 12 * 18 + 14
POSITION_TOLERANCE_UNITS = 250
STATUS_TOLERANCE_SECONDS = 0.05 + 1e-9


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle() -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(8_260_201))
    battle.entities.clear()
    battle.next_entity_id = 1
    target_stats = battle.card_loader.get_card("Knight")
    assert target_stats is not None
    for x in (14.5, 13.5, 12.5):
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
        target.attack_cooldown = 10.0
        target._spawn_hook_pending = False
        target._spawn_hook_fired = True
    player = battle.players[0]
    player.hand = ["ElectroDragon", "Knight", "Zap", "Cannon"]
    player.deck = [str(name) for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0
    return battle


def _assert_close_gameplay_state(
    oracle: BattleState,
    engine: TensorResidentEngine,
) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    resident_ids = {
        int(value) for value in core.entity_id[0, active].tolist() if int(value) > 0
    }
    oracle_character_ids = {
        entity_id
        for entity_id, entity in oracle.entities.items()
        if isinstance(entity, (Troop, Building))
    }
    assert oracle_character_ids <= resident_ids
    resident_id_list = core.entity_id[0].tolist()
    for entity_id in oracle_character_ids:
        entity = oracle.entities[entity_id]
        slot = resident_id_list.index(entity_id)
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


def test_electro_dragon_action_chain_is_native_and_policy_visible(
    tensor_device: str,
) -> None:
    boundary = _battle()
    oracle = copy.deepcopy(boundary)
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=tensor_device,
        max_entities=24,
        max_objects=24,
        event_capacity=2_048,
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        [boundary],
        structured_builder=StructuredObservationBuilder(max_entities=24),
        cv_builder=CvObservationBuilder(),
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, DEPLOY_DRAGON)
    target_ids = (1, 2, 3)
    initial_hp = {
        entity_id: oracle.entities[entity_id].hitpoints for entity_id in target_ids
    }
    resident_first_impact: int | None = None
    oracle_first_impact: int | None = None
    saw_chain_owner = False
    chain_projectile_owner = engine.mechanic_deployment.catalog.owner_index(
        "chain_projectile"
    )

    for tick in range(48):
        oracle.step_logic_ticks(1)
        action = DEPLOY_DRAGON if tick == 0 else NO_OP_ACTION
        actions = torch.tensor(
            [[action, NO_OP_ACTION]],
            dtype=torch.int64,
            device=engine.device,
        )
        assert engine.preflight(actions).supported.tolist() == [True]
        result = engine.step(
            actions,
            player_order=torch.tensor([[0, 1]], device=engine.device),
        )
        assert result.committed.tolist() == [True], engine.diagnose_preflight(actions)
        if tick == 0:
            allocation = result.deployment.deployment.allocation
            spawned_slot = int(allocation.slots[0][allocation.valid[0]][0])
            spawned_id = int(allocation.entity_ids[0][allocation.valid[0]][0])
            assert (
                engine.mechanic_deployment.state.owner_entity_id[
                    chain_projectile_owner, 0, spawned_slot
                ].item()
                == spawned_id
            )
        saw_chain_owner |= bool(
            result.chain_impacts and result.chain_impacts.materialized.any()
        )

        resident_ids = engine.runtime.battle.entity_id[0].tolist()
        resident_damage = {
            entity_id: initial_hp[entity_id]
            - float(engine.runtime.battle.entity_hp[0, resident_ids.index(entity_id)])
            for entity_id in target_ids
        }
        oracle_damage = {
            entity_id: initial_hp[entity_id] - oracle.entities[entity_id].hitpoints
            for entity_id in target_ids
        }
        if resident_first_impact is None and any(
            damage > 0 for damage in resident_damage.values()
        ):
            resident_first_impact = tick
        if oracle_first_impact is None and any(
            damage > 0 for damage in oracle_damage.values()
        ):
            oracle_first_impact = tick

        if (
            sum(damage > 0 for damage in resident_damage.values()) == 3
            and sum(damage > 0 for damage in oracle_damage.values()) == 3
            and not engine.chain_impacts.active.any()
        ):
            _assert_close_gameplay_state(oracle, engine)
            break
    else:
        pytest.fail("Electro Dragon did not complete its first three-target chain")

    assert resident_first_impact is not None
    assert oracle_first_impact is not None
    assert abs(resident_first_impact - oracle_first_impact) <= 1
    assert saw_chain_owner
    observation = projector.project_public_structured()
    enemy = observation.entity_features[0, 0]
    enemy = enemy[observation.entity_mask[0, 0] & (enemy[:, 3] > 0.5)]
    assert int((enemy[:, 9] < 0.9999).sum().item()) >= 3
    assert int((enemy[:, 14] > 0.0).sum().item()) >= 3
