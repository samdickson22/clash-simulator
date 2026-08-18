from __future__ import annotations

import random
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.combat_mechanics import CombatMechanicOpcode
from clasher.torch_sim.resident_damage_ramp import TensorResidentDamageRamp
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


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
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    kind = Building if str(stats.card_type).lower() == "building" else Troop
    entity = battle._spawn_entity(kind, position, player, stats)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.attack_cooldown = 0.0
    entity.on_spawn()
    return entity


def _battle(attacker_name: str, seed: int) -> tuple[BattleState, Entity, Troop]:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, attacker_name, 0, Position(9.0, 14.0))
    target = _spawn(battle, "Golem", 1, Position(9.0, 16.0))
    assert isinstance(target, Troop)
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    return battle, attacker, target


def _owners(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 128,
) -> tuple[TensorBattleRuntime, TensorResidentDamageRamp]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=12,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentDamageRamp.from_battles(runtime, [battle])


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _ramp(entity: Entity) -> Any:
    return cast(
        Any,
        next(
            mechanic
            for mechanic in entity.mechanics
            if type(mechanic).__name__ == "DamageRamp"
        ),
    )


@pytest.mark.parametrize(
    ("attacker_name", "stages"),
    [
        ("InfernoDragon", (35.0, 120.0, 422.0)),
        ("InfernoTower", (43.0, 158.0, 847.0)),
    ],
)
def test_multi_tick_damage_ramp_clocks_stages_hits_and_kinds_match_scalar(
    tensor_device: str,
    attacker_name: str,
    stages: tuple[float, float, float],
) -> None:
    source, _, _ = _battle(attacker_name, 996_100)
    oracle = source.clone()
    scalar_attacker = oracle.entities[1]
    scalar_target = oracle.entities[2]
    runtime, owner = _owners(source, tensor_device)
    attacker_slot = _slot(runtime, 1)
    target_slot = _slot(runtime, 2)
    card = runtime.battle.entity_card[0, attacker_slot]
    combat_card = owner.catalog.core_to_combat[card]
    mechanic_slot, present = owner.catalog.combat.mechanic_slot(
        combat_card,
        opcode=CombatMechanicOpcode.DAMAGE_RAMP,
    )
    del mechanic_slot
    assert present.item()
    assert owner.catalog.supported[card].item()
    assert owner.catalog.hit_speed_ms[card].item() == 400
    assert owner.catalog.uses_projectile[card].item() is False

    fired_amounts: list[float] = []
    scalar_ramp = _ramp(scalar_attacker)
    for _ in range(90):
        hp_before = scalar_target.hitpoints
        cast(Any, scalar_attacker).update_combat_component(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert (
            result.target_id[0, attacker_slot].item() == scalar_attacker.target_id == 2
        )
        assert result.connected[0, attacker_slot].item()
        assert owner.ramp.target_id[0, attacker_slot].item() == (
            scalar_ramp._current_target_id
        )
        assert owner.ramp.target_time_ms[0, attacker_slot].item() == pytest.approx(
            scalar_ramp._current_target_ms
        )
        assert owner.attack_cooldown[0, attacker_slot].item() == pytest.approx(
            scalar_attacker.attack_cooldown
        )
        assert (
            runtime.battle.entity_hp[0, target_slot].item() == scalar_target.hitpoints
        )
        if result.fired[0, attacker_slot].item():
            fired_amounts.append(result.damage[0, target_slot].item())
            assert (
                hp_before - scalar_target.hitpoints
                == result.damage[0, target_slot].item()
            )
            assert (
                result.stage_damage[0, attacker_slot].item() == scalar_attacker.damage
            )

    assert stages[0] in fired_amounts
    assert stages[1] in fired_amounts
    assert stages[2] in fired_amounts
    assert not runtime.battle.entity_hp_integer_kind[0, target_slot].item()
    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.DAMAGE
    ] * len(fired_amounts)
    assert runtime.events.target_id[0, :count].tolist() == [2] * len(fired_amounts)


@pytest.mark.parametrize("attacker_name", ["InfernoDragon", "InfernoTower"])
def test_target_death_reacquires_and_resets_ramp_and_retarget_clock(
    tensor_device: str,
    attacker_name: str,
) -> None:
    battle, _, first = _battle(attacker_name, 996_110)
    second = _spawn(battle, "Giant", 1, Position(10.0, 16.0))
    assert isinstance(second, Troop)
    second.stun_timer = 100.0
    oracle = battle.clone()
    scalar_attacker = oracle.entities[1]
    runtime, owner = _owners(battle, tensor_device)
    attacker_slot = _slot(runtime, 1)
    first_slot = _slot(runtime, first.id)

    for _ in range(45):
        cast(Any, scalar_attacker).update_combat_component(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
    assert owner.ramp.target_time_ms[0, attacker_slot].item() > 2_000

    oracle.entities[first.id].is_alive = False
    oracle._cleanup_dead_entities()
    oracle._rebuild_target_cache()
    runtime.battle.entity_hp[0, first_slot] = 0.0
    runtime.battle.entity_active[0, first_slot] = False
    cast(Any, scalar_attacker).update_combat_component(oracle.dt, oracle)
    result = owner.step_(runtime)

    assert scalar_attacker.target_id == second.id
    assert result.target_id[0, attacker_slot].item() == second.id
    assert owner.ramp.target_id[0, attacker_slot].item() == second.id
    assert owner.ramp.target_time_ms[0, attacker_slot].item() == pytest.approx(50.0)
    assert owner.ramp.target_time_ms[0, attacker_slot].item() == pytest.approx(
        _ramp(scalar_attacker)._current_target_ms
    )
    assert owner.ramp.damage[0, attacker_slot].item() < 200
    assert owner.attack_cooldown[0, attacker_slot].item() == pytest.approx(
        scalar_attacker.attack_cooldown
    )


def test_clone_fork_reset_and_event_capacity_rollback(tensor_device: str) -> None:
    battle, _, _ = _battle("InfernoTower", 996_120)
    runtime, owner = _owners(battle, tensor_device, event_capacity=1)
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.battle.entity_hp, runtime_before.battle.entity_hp)
    assert torch.equal(runtime.events.count, runtime_before.events.count)
    for descriptor in fields(owner):
        actual = getattr(owner, descriptor.name)
        expected = getattr(owner_before, descriptor.name)
        if isinstance(actual, torch.Tensor):
            assert torch.equal(actual, expected), descriptor.name
    assert torch.equal(owner.ramp.target_id, owner_before.ramp.target_id)
    assert torch.equal(owner.ramp.target_time_ms, owner_before.ramp.target_time_ms)

    clone = owner.clone()
    clone.ramp.target_time_ms[0, 0] = 123.0
    assert owner.ramp.target_time_ms[0, 0].item() == 0.0
    fork = clone.fork([0])
    assert fork.ramp.target_time_ms[0, 0].item() == 123.0
    clone.reset_rows_([0], owner, [0])
    assert clone.ramp.target_time_ms[0, 0].item() == 0.0


def test_lethal_direct_hit_emits_stable_damage_then_death(tensor_device: str) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(996_130))
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "InfernoTower", 0, Position(9.0, 14.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 16.0))
    target.hitpoints = 43
    target.max_hitpoints = 43
    oracle = battle.clone()
    scalar_attacker = oracle.entities[attacker.id]
    runtime, owner = _owners(battle, tensor_device)
    target_slot = _slot(runtime, target.id)

    cast(Any, scalar_attacker).update_combat_component(oracle.dt, oracle)
    result = owner.step_(runtime)

    assert result.committed.tolist() == [True]
    assert result.deaths[0, target_slot].item()
    assert not runtime.battle.entity_active[0, target_slot].item()
    assert runtime.battle.entity_hp[0, target_slot].item() == 0
    assert not runtime.battle.entity_hp_integer_kind[0, target_slot].item()
    assert not oracle.entities[target.id].is_alive
    assert runtime.events.opcode[0, :2].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.target_id[0, :2].tolist() == [target.id, target.id]
