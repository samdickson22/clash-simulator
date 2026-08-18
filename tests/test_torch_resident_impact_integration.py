from __future__ import annotations

from copy import deepcopy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.combat import (
    StationaryCombatState,
    step_stationary_combat_,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace


def _battle(
    source_name: str,
    target_positions: tuple[float, ...],
    *,
    source_x: float = 9.0,
    source_deploy: float = 0.0,
) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(source_name)
    assert source_stats is not None
    battle._spawn_unit_at_position(
        Position(source_x, 12.0),
        0,
        source_stats,
        deploy_delay_override=source_deploy,
        snap_to_valid=False,
    )
    for x in target_positions:
        target_stats = battle.card_loader.get_card("Knight")
        assert target_stats is not None
        battle._spawn_unit_at_position(
            Position(x, 12.0),
            1,
            target_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
    source = battle.entities[1]
    source.attack_cooldown = 0.0
    if target_positions:
        source.target_id = 2
    for entity_id in tuple(battle.entities)[1:]:
        target = battle.entities[entity_id]
        target.attack_cooldown = 10.0
        # The integration slice conservatively skips other mobile components;
        # the source mechanic/status/object lifecycle remains fully active.
        target.stun_timer = 100.0
    return battle


def _assert_runtime_matches(
    oracle: BattleState,
    engine: TensorResidentEngine,
) -> None:
    runtime = engine.runtime
    tensor_ids = set(
        runtime.battle.entity_id[0, runtime.entity_pool.active[0]].tolist()
    )
    assert tensor_ids == set(oracle.entities)
    for entity_id, entity in oracle.entities.items():
        match = torch.nonzero(
            runtime.battle.entity_id[0] == entity_id, as_tuple=False
        ).flatten()
        assert match.numel() == 1
        slot = int(match.item())
        assert runtime.battle.entity_x_units[0, slot].item() == tiles_to_logic_units(
            entity.position.x
        )
        assert runtime.battle.entity_y_units[0, slot].item() == tiles_to_logic_units(
            entity.position.y
        )
        assert runtime.battle.entity_hp[0, slot].item() == float(entity.hitpoints)
        assert runtime.battle.entity_hp_integer_kind[0, slot].item() == (
            type(entity.hitpoints) is int
        )
        assert runtime.status.stun_timer[0, slot].item() == pytest.approx(
            entity.stun_timer, abs=1e-12
        )
        assert runtime.status.slow_timer[0, slot].item() == pytest.approx(
            entity.slow_timer, abs=1e-12
        )
    assert runtime.entity_pool.next_entity_id[0].item() == oracle.next_entity_id


@pytest.mark.parametrize("source_name", ("IceWizard", "ElectroWizard"))
def test_spawn_area_deployment_completion_full_engine_exact(
    source_name: str,
) -> None:
    battle = _battle(source_name, (10.0,), source_deploy=0.05)
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, event_capacity=512
    )
    assert engine.preflight().supported.item()

    oracle.step_logic_ticks(1)
    result = engine.step()

    assert result.committed.item()
    assert result.spawn_area_materialization is not None
    assert result.spawn_area_materialization.accepted.item()
    assert result.spawn_areas is not None
    assert result.spawn_areas.damage_targets.any().item()
    assert not engine.spawn_areas.active.any().item()
    _assert_runtime_matches(oracle, engine)


def test_electro_dragon_primary_and_all_same_frame_chain_hops_exact() -> None:
    battle = _battle("ElectroDragon", (12.0, 13.0, 14.0))
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, event_capacity=1_024
    )
    assert engine.preflight().supported.item()

    oracle.step_logic_ticks(1)
    result = engine.step()

    assert result.committed.item()
    assert result.chain_impacts is not None
    assert result.chain_impacts.materialized.any().item()
    assert result.chain_impacts.impacted.any().item()
    _assert_runtime_matches(oracle, engine)


def test_electro_spirit_jump_contact_and_retained_chain_exact() -> None:
    battle = _battle("ElectroSpirit", (10.0, 11.0, 12.0))
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, event_capacity=1_024
    )
    assert engine.preflight().supported.item()

    for _ in range(6):
        oracle.step_logic_ticks(1)
        result = engine.step()
        assert result.committed.item()
        _assert_runtime_matches(oracle, engine)


def test_ice_spirit_jump_landing_freeze_and_cleanup_exact() -> None:
    battle = _battle("IceSpirit", (10.0,))
    oracle = deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, event_capacity=512
    )
    assert engine.preflight().supported.item()

    saw_jump = False
    saw_landing = False
    for _ in range(4):
        oracle.step_logic_ticks(1)
        result = engine.step()
        assert result.committed.item()
        assert result.ice_spirit is not None
        saw_jump = saw_jump or bool(result.ice_spirit.jumped.any().item())
        saw_landing = saw_landing or bool(result.ice_spirit.landed.any().item())
        _assert_runtime_matches(oracle, engine)
    assert saw_jump and saw_landing


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_stable_id_special_attack_start_is_immediately_immune(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = StationaryCombatState.empty(1, 3, device=device)
    state.present[0] = True
    state.alive[0] = True
    state.entity_id[0] = torch.tensor([1, 2, 3], device=device)
    state.owner[0] = torch.tensor([0, 1, 1], dtype=torch.int8, device=device)
    state.x_units[0] = torch.tensor([9_000, 9_500, 8_500], device=device)
    state.y_units[0] = 12_000
    state.hp[0] = 100.0
    state.max_hp[0] = 100.0
    state.damage[0] = 50.0
    state.range_units[0] = 1_000
    state.sight_range_units[0] = 5_500
    state.attack_cooldown[0] = 0.0
    state.target_slot[0] = torch.tensor([1, -1, 0], device=device)
    state.attack_start_special[0, 0] = True

    result = step_stationary_combat_(state)

    assert result.special_started is not None
    assert result.special_started[0, 0]
    assert result.attacked[0, 0]
    assert not result.attacked[0, 2]
    assert state.hp[0, 0].item() == 100.0
    assert not state.targetable[0, 0]
    assert not state.effect_receivable[0, 0]
    assert state.attack_cooldown[0, 0].item() == 0.0


def test_landing_event_capacity_failure_rolls_back_engine_and_owner() -> None:
    battle = _battle("IceSpirit", (10.0,))
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, event_capacity=2
    )
    first = engine.step()
    assert first.committed.item()
    result = first
    for _ in range(4):
        before_battle = engine.runtime.battle.entity_id.clone()
        before_hp = engine.runtime.battle.entity_hp.clone()
        before_jump = engine.ice_spirit.jump_active.clone()
        before_position = engine.runtime.battle.entity_x_units.clone()
        result = engine.step()
        if not result.committed.item():
            break
    assert not result.committed.item()
    assert torch.equal(engine.runtime.battle.entity_id, before_battle)
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert torch.equal(engine.ice_spirit.jump_active, before_jump)
    assert torch.equal(engine.runtime.battle.entity_x_units, before_position)


def test_workspace_owns_and_refreshes_all_impact_states() -> None:
    battle = _battle("ElectroDragon", (12.0, 13.0, 14.0))
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, event_capacity=1_024
    )
    workspace = TensorResidentWorkspace(engine)
    assert workspace.scratch.spawn_areas.catalog is engine.spawn_areas.catalog
    assert workspace.scratch.chain_impacts.catalog is engine.chain_impacts.catalog
    assert workspace.scratch.ice_spirit.catalog is engine.ice_spirit.catalog
    assert workspace.scratch.chain_impacts.active.data_ptr() != (
        engine.chain_impacts.active.data_ptr()
    )
    workspace.scratch.chain_impacts.active.fill_(True)
    workspace.refresh()
    assert torch.equal(
        workspace.scratch.chain_impacts.active, engine.chain_impacts.active
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
@pytest.mark.parametrize(
    "source_name,target_positions,source_deploy",
    (
        ("IceWizard", (10.0,), 0.05),
        ("ElectroWizard", (10.0,), 0.05),
        ("ElectroDragon", (12.0, 13.0, 14.0), 0.0),
        ("ElectroSpirit", (10.0, 11.0), 0.0),
        ("IceSpirit", (10.0,), 0.0),
    ),
)
def test_cuda_full_engine_impact_family_smoke(
    source_name: str,
    target_positions: tuple[float, ...],
    source_deploy: float,
) -> None:
    battle = _battle(
        source_name,
        target_positions,
        source_deploy=source_deploy,
    )
    engine = TensorResidentEngine.from_battles(
        [battle],
        device="cuda",
        max_entities=32,
        event_capacity=1_024,
    )
    result = engine.step()
    assert result.committed.device.type == "cuda"
