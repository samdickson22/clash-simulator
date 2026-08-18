from __future__ import annotations

import copy
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity
from clasher.mechanics.shared.multi_target import MultipleTargetAttack
from clasher.mechanics.shared.on_hit_buff import SerializedOnHitBuff
from clasher.torch_sim.mechanic_dispatcher import TensorMechanicDispatcher
from clasher.torch_sim.resident_multi_target import TensorResidentMultiTargetAttacks
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


def _spawn(
    battle: BattleState,
    name: str,
    owner: int,
    position: Position,
) -> Entity:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        position,
        owner,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = next(
        candidate
        for entity_id, candidate in battle.entities.items()
        if entity_id not in before
        and str(getattr(candidate.card_stats, "name", "")) == str(stats.name)
    )
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _battle(
    *, one_target: bool = False
) -> tuple[BattleState, Entity, Entity, Entity | None]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    primary = _spawn(battle, "Knight", 1, Position(8.0, 13.0))
    secondary = (
        None if one_target else _spawn(battle, "Knight", 1, Position(10.0, 13.0))
    )
    source.target_id = primary.id
    return battle, source, primary, secondary


def _mechanic(entity: Entity, kind: type[object]) -> object:
    return next(item for item in entity.mechanics if isinstance(item, kind))


def _oracle_resolve(battle: BattleState, source_id: int, primary_id: int) -> None:
    source = battle.entities[source_id]
    primary = battle.entities[primary_id]
    multiple = cast(MultipleTargetAttack, _mechanic(source, MultipleTargetAttack))
    on_hit = cast(SerializedOnHitBuff, _mechanic(source, SerializedOnHitBuff))
    multiple.on_attack_start(source, primary)
    primary.take_damage(source.damage)
    multiple.resolve_secondary_attack_hits(source, primary, source.damage, battle)
    on_hit.on_attack_hit(source, primary)


def _setup(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 128,
) -> tuple[
    TensorBattleRuntime,
    TensorMechanicDispatcher,
    TensorResidentMultiTargetAttacks,
    dict[int, int],
    torch.Tensor,
]:
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=8,
        event_capacity=event_capacity,
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])
    owner = TensorResidentMultiTargetAttacks.from_battles(dispatcher, [battle])
    slots = {
        int(entity_id): slot
        for slot, entity_id in enumerate(runtime.battle.entity_id[0].tolist())
        if entity_id
    }
    candidate = torch.zeros(
        (1, runtime.max_entities, runtime.max_entities),
        dtype=torch.bool,
        device=runtime.device,
    )
    for source_id, source_slot in slots.items():
        source = battle.entities[source_id]
        for target_id, target_slot in slots.items():
            target = battle.entities[target_id]
            candidate[0, source_slot, target_slot] = source.can_attack_target(target)
    return runtime, dispatcher, owner, slots, candidate


def _attack_planes(
    runtime: TensorBattleRuntime,
    source_slot: int,
    primary_slot: int,
    damage: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    started = torch.zeros_like(runtime.battle.entity_active)
    primary = torch.zeros_like(runtime.battle.entity_id)
    amount = torch.zeros_like(runtime.battle.entity_hp)
    started[0, source_slot] = True
    primary[0, source_slot] = primary_slot
    amount[0, source_slot] = damage
    return started, primary, amount


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
@pytest.mark.parametrize("one_target", (False, True))
def test_direct_snapshot_damage_status_and_order_match_scalar(
    device: str,
    one_target: bool,
) -> None:
    battle, source, primary, secondary = _battle(one_target=one_target)
    oracle = copy.deepcopy(battle)
    _oracle_resolve(oracle, source.id, primary.id)
    runtime, dispatcher, owner, slots, candidate = _setup(battle, device)
    source_slot = slots[source.id]
    started, target, damage = _attack_planes(
        runtime, source_slot, slots[primary.id], source.damage
    )

    result = owner.commit_attacks_(
        runtime,
        dispatcher.mechanics,
        dispatcher.combat_world,
        attack_started=started,
        primary_target_slot=target,
        damage=damage,
        damage_integer_kind=True,
        cooldown_after_seconds=1.8,
        candidate_mask=candidate,
    )

    assert result.committed.tolist() == [True]
    for entity in (primary, secondary):
        if entity is None:
            continue
        slot = slots[entity.id]
        expected = oracle.entities[entity.id]
        assert runtime.battle.entity_hp[0, slot].item() == expected.hitpoints
        assert runtime.status.stun_timer[0, slot].item() == expected.stun_timer
        assert not runtime.battle.entity_hp_integer_kind[0, slot]
    count = int(runtime.events.count[0].item())
    opcodes = runtime.events.opcode[0, :count].tolist()
    targets = runtime.events.target_id[0, :count].tolist()
    assert opcodes[0] == int(RuntimeEventOpcode.DAMAGE)
    if secondary is not None:
        assert targets[:4] == [primary.id, secondary.id, secondary.id, primary.id]
        assert opcodes[:4] == [
            int(RuntimeEventOpcode.DAMAGE),
            int(RuntimeEventOpcode.DAMAGE),
            int(RuntimeEventOpcode.STATUS),
            int(RuntimeEventOpcode.STATUS),
        ]
    assert owner.state.target_entity_id[0, source_slot].item() == primary.id
    assert owner.state.cooldown_seconds[0, source_slot].item() == 1.8
    owner.tick_cooldowns_(
        torch.tensor([0.05], dtype=torch.float64, device=runtime.device)
    )
    assert owner.state.cooldown_seconds[0, source_slot].item() == 1.75


def test_projectile_commit_retains_snapshot_identity_until_later_impact() -> None:
    battle, source, primary, secondary = _battle()
    assert secondary is not None
    oracle = copy.deepcopy(battle)
    runtime, dispatcher, owner, slots, candidate = _setup(battle, "cpu")
    source_slot = slots[source.id]
    started, target, damage = _attack_planes(
        runtime, source_slot, slots[primary.id], source.damage
    )
    before_hp = runtime.battle.entity_hp.clone()

    launch = owner.commit_attacks_(
        runtime,
        dispatcher.mechanics,
        dispatcher.combat_world,
        attack_started=started,
        primary_target_slot=target,
        damage=damage,
        projectile=True,
        damage_integer_kind=True,
        candidate_mask=candidate,
    )

    assert launch.committed.tolist() == [True]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert launch.projectile_queued.sum().item() == 2
    assert owner.state.pending_target_id[0, source_slot, :2].tolist() == [
        primary.id,
        secondary.id,
    ]
    cloned = owner.clone()
    forked = owner.fork([0, 0])
    assert (
        cloned.state.pending_active.data_ptr() != owner.state.pending_active.data_ptr()
    )
    assert forked.state.pending_active.shape[0] == 2

    _oracle_resolve(oracle, source.id, primary.id)
    impact = owner.resolve_projectiles_(runtime, dispatcher.mechanics)

    assert impact.committed.tolist() == [True]
    assert impact.resolved.sum().item() == 2
    for entity in (primary, secondary):
        slot = slots[entity.id]
        assert runtime.battle.entity_hp[0, slot].item() == (
            oracle.entities[entity.id].hitpoints
        )
        assert runtime.status.stun_timer[0, slot].item() == (
            oracle.entities[entity.id].stun_timer
        )
    assert not owner.state.pending_active.any()


def test_event_capacity_failure_rolls_back_runtime_mechanics_and_snapshot() -> None:
    battle, source, primary, _ = _battle()
    runtime, dispatcher, owner, slots, candidate = _setup(
        battle, "cpu", event_capacity=1
    )
    source_slot = slots[source.id]
    started, target, damage = _attack_planes(
        runtime, source_slot, slots[primary.id], source.damage
    )
    hp_before = runtime.battle.entity_hp.clone()
    status_before = runtime.status.stun_timer.clone()

    result = owner.commit_attacks_(
        runtime,
        dispatcher.mechanics,
        dispatcher.combat_world,
        attack_started=started,
        primary_target_slot=target,
        damage=damage,
        candidate_mask=candidate,
    )

    assert result.committed.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, hp_before)
    assert torch.equal(runtime.status.stun_timer, status_before)
    assert not owner.state.source_entity_id.any()
    assert not owner.state.pending_active.any()


def test_reset_clears_only_selected_sources() -> None:
    battle, source, primary, _ = _battle()
    runtime, dispatcher, owner, slots, candidate = _setup(battle, "cpu")
    source_slot = slots[source.id]
    started, target, damage = _attack_planes(
        runtime, source_slot, slots[primary.id], source.damage
    )
    owner.commit_attacks_(
        runtime,
        dispatcher.mechanics,
        dispatcher.combat_world,
        attack_started=started,
        primary_target_slot=target,
        damage=damage,
        projectile=True,
        candidate_mask=candidate,
    )
    selected = torch.zeros_like(runtime.battle.entity_active)
    selected[0, source_slot] = True

    owner.reset_(selected)

    assert not owner.state.pending_active[0, source_slot].any()
    assert owner.state.source_entity_id[0, source_slot].item() == 0
