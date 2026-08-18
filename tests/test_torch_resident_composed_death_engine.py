from __future__ import annotations

import copy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building, DeathAreaEffectContainer, Troop
from clasher.torch_sim.resident_engine import TensorResidentEngine

ROOTS = ("Golem", "IceGolem", "Lumberjack", "BattleRam", "SkeletonBarrel")


def _battle(root: str) -> tuple[BattleState, Troop, list[Troop]]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(root)
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(9.0, 10.0),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    source = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    targets = []
    knight = battle.card_loader.get_card("Knight")
    assert knight is not None
    for x in (8.0, 10.0):
        battle._spawn_unit_at_position(
            Position(x, 10.0),
            1,
            knight,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        target = battle.entities[battle.next_entity_id - 1]
        assert isinstance(target, Troop)
        target.stun_timer = 100.0
        target.attack_cooldown = 100.0
        targets.append(target)
    return battle, source, targets


def _characters(engine: TensorResidentEngine) -> list[tuple[int, str, float, float]]:
    core = engine.runtime.battle
    return sorted(
        (
            int(core.entity_id[0, slot]),
            core.card_names[int(core.entity_card[0, slot])],
            float(core.entity_hp[0, slot]),
            float(core.entity_deploy_delay[0, slot]),
        )
        for slot in range(engine.runtime.max_entities)
        if bool(engine.runtime.entity_pool.active[0, slot])
        and int(core.entity_kind[0, slot]) in {0, 1}
    )


def _scalar_characters(battle: BattleState) -> list[tuple[int, str, float, float]]:
    return sorted(
        (
            entity_id,
            str(entity.card_stats.name),
            float(entity.hitpoints),
            float(entity.deploy_delay_remaining),
        )
        for entity_id, entity in battle.entities.items()
        if getattr(entity, "entity_kind", 4) in {0, 1} and entity.is_alive
    )


@pytest.mark.parametrize("root", ROOTS)
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
def test_composed_dead_root_matches_scalar_cleanup_and_payloads(
    root: str,
    device: str,
) -> None:
    boundary, source, _ = _battle(root)
    oracle = copy.deepcopy(boundary)
    oracle_source = oracle.entities[source.id]
    oracle_source.take_damage(oracle_source.hitpoints)
    oracle._cleanup_dead_entities()
    source.hitpoints = 0.0
    source.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=device,
        max_entities=32,
        max_objects=16,
        event_capacity=512,
    )

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.death_payloads is not None
    assert _characters(engine) == _scalar_characters(oracle)
    scalar_areas = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, (AreaEffect, DeathAreaEffectContainer))
    ]
    assert int(engine.death_payloads.areas.valid.sum().item()) == len(scalar_areas)
    if scalar_areas:
        area_slot = int(torch.where(engine.death_payloads.areas.valid[0])[0][0])
        assert engine.death_payloads.areas.object_id[0, area_slot].item() == (
            scalar_areas[0].id
        )


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
def test_battle_ram_demolition_handoff_ticks_new_children_same_frame(
    device: str,
) -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    ram = battle.card_loader.get_card("BattleRam")
    cannon = battle.card_loader.get_card("Cannon")
    assert ram is not None and cannon is not None
    battle._spawn_unit_at_position(
        Position(9.0, 13.5), 0, ram, deploy_delay_override=0.0, snap_to_valid=False
    )
    source = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    target = battle._spawn_entity(Building, Position(9.0, 14.0), 1, cannon)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    engine = TensorResidentEngine.from_battles(
        [battle], device=device, max_entities=16, max_objects=8, event_capacity=128
    )

    result = engine.step()

    assert result.committed.tolist() == [True]
    assert result.charge_carriers is not None
    assert result.charge_carriers.carrier_death.any()
    children = [
        slot
        for slot in range(engine.runtime.max_entities)
        if bool(engine.runtime.entity_pool.active[0, slot])
        and engine.runtime.battle.card_names[
            int(engine.runtime.battle.entity_card[0, slot])
        ]
        == "Barbarian"
    ]
    assert len(children) == 2
    assert [
        engine.runtime.battle.entity_deploy_delay[0, slot].item() for slot in children
    ] == [
        0.95,
        0.95,
    ]


def test_mixed_capacity_failure_is_row_atomic() -> None:
    golem, golem_source, _ = _battle("Golem")
    lumberjack, lumberjack_source, _ = _battle("Lumberjack")
    for source in (golem_source, lumberjack_source):
        source.hitpoints = 0.0
        source.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [golem, lumberjack], max_entities=16, max_objects=8, event_capacity=1
    )
    before_hp = engine.runtime.battle.entity_hp.clone()

    result = engine.step()

    assert result.committed.tolist() == [False, True]
    assert torch.equal(engine.runtime.battle.entity_hp[0], before_hp[0])
    assert engine.death_payloads.areas.valid[1].any()
