from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.resident_shield import (
    ShieldDamageInputs,
    ShieldLifecycleReason,
    TensorShieldLifecycleState,
    step_shield_lifecycle_,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime


def _battle(
    shield_name: str,
    *,
    deploy_delay: float = 0.0,
) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    for name, player, x in (("Knight", 0, 9.0), (shield_name, 1, 10.0)):
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        entity = battle._spawn_entity(Troop, Position(x, 12.0), player, stats)
        entity.deploy_delay_remaining = deploy_delay if player else 0.0
        entity.placement_pending = entity.deploy_delay_remaining > 0.0
        entity._spawn_hook_pending = entity.placement_pending
        entity._spawn_hook_fired = not entity.placement_pending
    attacker = battle.entities[1]
    target = battle.entities[2]
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    target.attack_cooldown = 10.0
    target.stun_timer = 100.0
    return battle


def _shield(entity: Troop) -> Any:
    return next(
        mechanic for mechanic in entity.mechanics if type(mechanic).__name__ == "Shield"
    )


@pytest.mark.parametrize("shield_name", ("DarkPrince", "Guards"))
def test_generated_direct_combat_whole_hit_break_and_clocks_exact(
    shield_name: str,
) -> None:
    candidate = _battle(shield_name)
    oracle = deepcopy(candidate)
    oracle_target = oracle.entities[2]
    assert isinstance(oracle_target, Troop)
    oracle_shield = _shield(oracle_target)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=128
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [candidate])

    for _ in range(2):
        oracle._step_logic_tick()
        result = step_shield_lifecycle_(state, runtime)
        assert result.committed.item()
        assert state.mechanics.shield_current[0, 1].item() == float(
            oracle_shield.current_shield
        )
        assert state.mechanics.shield_break_count[0, 1].item() == (
            oracle_target.__dict__.get("_shield_break_count", 0)
        )
        assert runtime.battle.entity_hp[0, 1].item() == float(oracle_target.hitpoints)
        oracle_attacker = oracle.entities[1]
        assert state.combat.attack_cooldown[0, 0].item() == pytest.approx(
            oracle_attacker.attack_cooldown, abs=1e-12
        )
        assert state.combat.target_slot[0, 0].item() == 1


def test_ordered_direct_and_area_ingress_preserve_whole_hit_and_scalar_kinds() -> None:
    candidate = _battle("DarkPrince")
    oracle = deepcopy(candidate)
    oracle_target = oracle.entities[2]
    assert isinstance(oracle_target, Troop)
    oracle_shield = _shield(oracle_target)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=128
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [candidate])
    state.combat.combat_enabled.zero_()
    incoming = ShieldDamageInputs.empty(1, 3)
    incoming.valid[:] = True
    incoming.source_slot[:] = 0
    incoming.target_slot[:] = 1
    incoming.amount[0] = torch.tensor([50.0, 500.0, 37.0])
    incoming.area[0] = torch.tensor([False, True, False])
    for amount in incoming.amount[0].tolist():
        oracle_target.take_damage(amount)

    result = step_shield_lifecycle_(state, runtime, incoming)

    assert result.committed.item()
    assert result.hits.shield_absorbed[0, :3].tolist() == [True, True, False]
    assert result.hits.shield_broken[0, :3].tolist() == [False, True, False]
    assert state.mechanics.shield_current[0, 1].item() == float(
        oracle_shield.current_shield
    )
    assert runtime.battle.entity_hp[0, 1].item() == float(oracle_target.hitpoints)
    assert not state.shield_integer_kind[0, 1]
    assert not runtime.battle.entity_hp_integer_kind[0, 1]


def test_deployment_crossing_initializes_and_delays_combat_exactly() -> None:
    candidate = _battle("Guards", deploy_delay=0.1)
    oracle = deepcopy(candidate)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=8, event_capacity=128
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [candidate])

    for tick in range(2):
        oracle._step_logic_tick()
        result = step_shield_lifecycle_(state, runtime)
        assert runtime.battle.entity_deploy_delay[0, 1].item() == pytest.approx(
            oracle.entities[2].deploy_delay_remaining, abs=1e-12
        )
        assert result.deployment_completed[0, 1].item() is (tick == 1)
        assert runtime.battle.entity_hp[0, 1].item() == float(
            oracle.entities[2].hitpoints
        )


def test_shield_source_target_and_attack_clocks_match_oracle() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    for name, player, x in (("Guards", 0, 9.0), ("Knight", 1, 10.0)):
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        entity = battle._spawn_entity(Troop, Position(x, 12.0), player, stats)
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    battle.entities[1].target_id = 2
    battle.entities[1].attack_cooldown = 0.0
    battle.entities[2].attack_cooldown = 10.0
    battle.entities[2].stun_timer = 100.0
    oracle = deepcopy(battle)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=128
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [battle])

    oracle._step_logic_tick()
    result = step_shield_lifecycle_(state, runtime)

    assert result.committed.item()
    assert result.generated_hits[0, 0]
    assert runtime.battle.entity_hp[0, 1].item() == float(oracle.entities[2].hitpoints)
    assert state.combat.attack_cooldown[0, 0].item() == pytest.approx(
        oracle.entities[1].attack_cooldown, abs=1e-12
    )
    assert state.combat.target_slot[0, 0].item() == 1


def test_slot_identity_reset_clone_fork_and_row_rollback() -> None:
    battle = _battle("Guards")
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=4, event_capacity=1
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [battle])
    state.mechanics.shield_current[0, 1] = 0.0
    before_runtime = runtime.clone()
    before_state = state.clone()

    rejected = step_shield_lifecycle_(state, runtime)

    assert not rejected.committed.item()
    assert rejected.reason.item() == int(ShieldLifecycleReason.EVENT_CAPACITY)
    assert torch.equal(runtime.battle.entity_hp, before_runtime.battle.entity_hp)
    assert torch.equal(
        state.mechanics.shield_current, before_state.mechanics.shield_current
    )
    clone = state.clone()
    clone.mechanics.shield_current.zero_()
    assert clone.mechanics.catalog is state.mechanics.catalog
    fork = state.fork([0, 0])
    assert fork.batch_size == 2
    state.reset_rows_([0], before_state, [0])
    assert torch.equal(
        state.mechanics.shield_current, before_state.mechanics.shield_current
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_multitick_shield_lifecycle() -> None:
    battle = _battle("Guards")
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=8, event_capacity=128
    )
    state = TensorShieldLifecycleState.from_battles(runtime, [battle])
    for _ in range(2):
        result = step_shield_lifecycle_(state, runtime)
    assert result.committed.device.type == "cuda"
    assert state.mechanics.shield_current.device.type == "cuda"
