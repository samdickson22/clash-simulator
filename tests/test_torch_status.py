from __future__ import annotations

import random
from collections.abc import Sequence
from typing import cast

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.status import TensorStatusState, tick_building_lifetime


def _spawn_troop(battle: BattleState, index: int) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return cast(
        Troop,
        battle._spawn_entity(
            Troop,
            Position(2.0 + index, 12.0),
            index % 2,
            stats,
        ),
    )


def _assert_status_matches(
    tensor: TensorStatusState,
    entities: Sequence[Sequence[Entity]],
) -> None:
    for batch_index, row in enumerate(entities):
        for entity_index, entity in enumerate(row):
            index = (batch_index, entity_index)
            assert tensor.stun_timer[index].item() == entity.stun_timer
            assert tensor.freeze_expiry_time[index].item() == entity.freeze_expiry_time
            assert tensor.slow_timer[index].item() == entity.slow_timer
            assert tensor.slow_multiplier[index].item() == entity.slow_multiplier
            assert (
                tensor.attack_speed_debuff_multiplier[index].item()
                == entity.attack_speed_debuff_multiplier
            )
            assert (
                tensor.spawn_speed_debuff_multiplier[index].item()
                == entity.spawn_speed_debuff_multiplier
            )
            assert tensor.haste_timer[index].item() == entity.haste_timer
            assert (
                tensor.movement_speed_buff_multiplier[index].item()
                == entity.movement_speed_buff_multiplier
            )
            assert (
                tensor.attack_speed_buff_multiplier[index].item()
                == entity.attack_speed_buff_multiplier
            )
            assert (
                tensor.spawn_speed_buff_multiplier[index].item()
                == entity.spawn_speed_buff_multiplier
            )
            tensor_slows = sorted(
                zip(
                    tensor.slow_remaining[index][tensor.slow_active[index]].tolist(),
                    tensor.slow_movement[index][tensor.slow_active[index]].tolist(),
                    tensor.slow_attack[index][tensor.slow_active[index]].tolist(),
                    tensor.slow_spawn[index][tensor.slow_active[index]].tolist(),
                )
            )
            assert tensor_slows == sorted(entity._slow_effects)
            tensor_hastes = sorted(
                zip(
                    tensor.haste_remaining[index][tensor.haste_active[index]].tolist(),
                    tensor.haste_movement[index][tensor.haste_active[index]].tolist(),
                    tensor.haste_attack[index][tensor.haste_active[index]].tolist(),
                    tensor.haste_spawn[index][tensor.haste_active[index]].tolist(),
                )
            )
            assert tensor_hastes == sorted(entity._haste_effects)


def test_freeze_uses_absolute_expiry_but_ticks_stun_and_slow_symptoms() -> None:
    battle = BattleState()
    troop = _spawn_troop(battle, 0)
    tensor = TensorStatusState.empty(1, 1)

    troop.inherit_freeze_until(8.0, 5.25)
    tensor.apply_freeze_until(8.0, 5.25)
    _assert_status_matches(tensor, [[troop]])

    for _ in range(55):
        troop.update_buff_component(0.05)
        tensor.tick(0.05)
    _assert_status_matches(tensor, [[troop]])
    assert troop.stun_timer == 0.0
    assert troop.slow_timer == 0.0
    assert tensor.freeze_expiry_time.item() == troop.freeze_expiry_time == 8.0


def test_randomized_overlapping_stun_slow_and_haste_match_entities() -> None:
    rng = random.Random(884_231)
    battles = [BattleState() for _ in range(3)]
    entities: list[list[Troop]] = [
        [_spawn_troop(battle, index) for index in range(4)] for battle in battles
    ]
    tensor = TensorStatusState.empty(3, 4, max_slow_sources=6, max_haste_sources=6)
    slow_signatures = ((0.7, 0.7, 0.7), (0.5, 1.0, 1.0), (0.8, 0.6, 0.9))
    haste_signatures = ((1.3, 1.3, 1.3), (1.1, 1.4, 1.2), (0.9, 0.8, 1.1))

    for _ in range(120):
        operation = rng.randrange(4)
        mask = torch.tensor(
            [[rng.random() < 0.45 for _ in range(4)] for _ in range(3)],
            dtype=torch.bool,
        )
        if operation == 0:
            duration = rng.choice((0.05, 0.1, 0.3, 0.75))
            tensor.apply_stun(duration, mask=mask)
            for batch_index, row in enumerate(entities):
                for entity_index, entity in enumerate(row):
                    if mask[batch_index, entity_index]:
                        entity.apply_stun(duration)
        elif operation == 1:
            duration = rng.choice((0.05, 0.15, 0.4, 0.9))
            movement, attack, spawn = rng.choice(slow_signatures)
            tensor.apply_slow(
                duration,
                movement,
                attack_speed_multiplier=attack,
                spawn_speed_multiplier=spawn,
                mask=mask,
            )
            for batch_index, row in enumerate(entities):
                for entity_index, entity in enumerate(row):
                    if mask[batch_index, entity_index]:
                        entity.apply_slow(
                            duration,
                            movement,
                            attack_speed_multiplier=attack,
                            spawn_speed_multiplier=spawn,
                        )
        elif operation == 2:
            duration = rng.choice((0.05, 0.2, 0.55, 1.0))
            movement, attack, spawn = rng.choice(haste_signatures)
            tensor.apply_haste(
                duration,
                movement,
                attack,
                spawn_speed_multiplier=spawn,
                mask=mask,
            )
            for batch_index, row in enumerate(entities):
                for entity_index, entity in enumerate(row):
                    if mask[batch_index, entity_index]:
                        entity.apply_haste(duration, movement, attack, spawn)
        else:
            dt = rng.choice((0.01, 0.05, 0.1, 0.17))
            tensor.tick(dt, component_mask=mask)
            for batch_index, row in enumerate(entities):
                for entity_index, entity in enumerate(row):
                    if mask[batch_index, entity_index]:
                        entity.update_buff_component(dt)
        _assert_status_matches(tensor, entities)


def test_periodic_target_local_deadlines_refresh_and_expire_exactly() -> None:
    battle = BattleState()
    troop = _spawn_troop(battle, 0)
    troop.hitpoints = 1_000_000.0
    troop.max_hitpoints = 1_000_000.0
    tensor = TensorStatusState.empty(1, 1, max_periodic_sources=5)
    source_kind_codes = {101: 4, 207: 8, 350: 2}

    for source_id, interval, damage, hard in (
        (101, 0.2, 17.0, None),
        (207, 0.35, 9.0, 1.1),
        (350, 0.1, 3.0, None),
    ):
        troop.apply_periodic_damage(
            source_id=source_id,
            source_kind=None,
            duration=0.6,
            hit_interval=interval,
            damage=damage,
            hard_duration=hard,
        )
        tensor.apply_periodic_damage(
            source_id=source_id,
            source_kind=source_kind_codes[source_id],
            duration=0.6,
            hit_interval=interval,
            damage=damage,
            hard_duration=hard,
        )

    for step, dt in enumerate((0.05, 0.15, 0.2, 0.1, 0.1, 0.25)):
        if step == 2:
            troop.apply_periodic_damage(
                source_id=101,
                source_kind=None,
                duration=0.7,
                # Refresh does not reset or replace the existing hit phase or
                # interval, even if the refreshing area carries new metadata.
                hit_interval=0.45,
                damage=23.0,
            )
            tensor.apply_periodic_damage(
                source_id=101,
                source_kind=source_kind_codes[101],
                duration=0.7,
                hit_interval=0.45,
                damage=23.0,
            )
        hp_before = troop.hitpoints
        troop.update_buff_component(dt)
        schedule = tensor.tick(dt)
        assert (
            schedule.total_damage_if_all_committed.item() == hp_before - troop.hitpoints
        )

        tensor_effects = {
            int(tensor.periodic_source_id[0, 0, slot]): (
                tensor.periodic_remaining[0, 0, slot].item(),
                tensor.periodic_next_hit[0, 0, slot].item(),
                tensor.periodic_damage[0, 0, slot].item(),
                (
                    tensor.periodic_hard_remaining[0, 0, slot].item()
                    if tensor.periodic_hard_active[0, 0, slot]
                    else None
                ),
            )
            for slot in torch.where(tensor.periodic_active[0, 0])[0].tolist()
        }
        oracle_effects = {
            source_id: (
                effect.remaining,
                effect.time_to_next_hit,
                effect.damage,
                effect.hard_remaining,
            )
            for source_id, effect in troop._periodic_damage_effects.items()
        }
        assert tensor_effects == oracle_effects


def test_periodic_exact_expiry_boundary_still_schedules_hit() -> None:
    tensor = TensorStatusState.empty(1, 1)
    tensor.apply_periodic_damage(
        source_id=7,
        source_kind=3,
        duration=0.05,
        hit_interval=0.05,
        damage=12.0,
    )
    schedule = tensor.tick(0.05)
    assert schedule.valid[0, 0, 0]
    assert schedule.hit_counts[0, 0, 0].item() == 1
    assert schedule.total_damage_if_all_committed.item() == 12.0
    assert not tensor.periodic_active.any()


def test_periodic_reused_physical_slot_retains_insertion_order() -> None:
    tensor = TensorStatusState.empty(1, 1, max_periodic_sources=3)
    tensor.apply_periodic_damage(
        source_id=10,
        source_kind=1,
        duration=0.1,
        hit_interval=0.1,
        damage=1.0,
    )
    tensor.apply_periodic_damage(
        source_id=20,
        source_kind=2,
        duration=1.0,
        hit_interval=0.3,
        damage=2.0,
    )
    tensor.tick(0.1)
    tensor.apply_periodic_damage(
        source_id=30,
        source_kind=3,
        duration=1.0,
        hit_interval=0.2,
        damage=3.0,
    )

    schedule = tensor.tick(0.2)
    assert schedule.source_ids[0, 0][schedule.valid[0, 0]].tolist() == [20, 30]
    assert schedule.source_slots[0, 0][schedule.valid[0, 0]].tolist() == [1, 0]


def test_randomized_fixed_point_building_lifetime_matches_oracle() -> None:
    rng = random.Random(921_475)
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    card_names = ("Cannon", "Tesla", "BombTower", "Tombstone")
    buildings: list[Building] = []
    for index, card_name in enumerate(card_names):
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None and stats.lifetime_ms
        building = cast(
            Building,
            battle._spawn_entity(
                Building, Position(3.0 + index * 3.0, 12.0), index % 2, stats
            ),
        )
        buildings.append(building)

    shape = (1, len(buildings))
    hitpoints = torch.tensor(
        [[building.hitpoints for building in buildings]], dtype=torch.float64
    )
    max_hitpoints = torch.tensor(
        [[building.max_hitpoints for building in buildings]], dtype=torch.float64
    )
    lifetime_ms = torch.tensor(
        [[building.card_stats.lifetime_ms for building in buildings]],
        dtype=torch.int64,
    )
    elapsed = torch.zeros(shape, dtype=torch.float64)
    work = torch.zeros(shape, dtype=torch.int64)
    carry = torch.zeros(shape, dtype=torch.float64)
    alive = torch.ones(shape, dtype=torch.bool)

    saw_death = False
    for _ in range(1_600):
        dt = rng.choice((0.0, 0.01, 0.025, 0.05, 0.075, 0.13))
        mask = torch.tensor(
            [[rng.random() < 0.85 for _ in buildings]], dtype=torch.bool
        )
        result = tick_building_lifetime(
            hitpoints=hitpoints,
            max_hitpoints=max_hitpoints,
            lifetime_ms=lifetime_ms,
            lifetime_elapsed=elapsed,
            lifetime_decay_work=work,
            lifetime_tick_carry_ms=carry,
            is_alive=alive,
            dt=dt,
            component_mask=mask,
        )
        for index, building in enumerate(buildings):
            if mask[0, index]:
                building.update_hitpoint_component(dt)
            assert result.hitpoints[0, index].item() == building.hitpoints
            assert result.lifetime_elapsed[0, index].item() == building.lifetime_elapsed
            assert (
                result.lifetime_decay_work[0, index].item()
                == building.lifetime_decay_work
            )
            assert (
                result.lifetime_tick_carry_ms[0, index].item()
                == building.lifetime_tick_carry_ms
            )
            assert result.is_alive[0, index].item() is building.is_alive
        hitpoints = result.hitpoints
        elapsed = result.lifetime_elapsed
        work = result.lifetime_decay_work
        carry = result.lifetime_tick_carry_ms
        alive = result.is_alive
        saw_death = saw_death or bool(result.died.any())
        if not alive.any():
            break
    assert saw_death
    assert not alive.any()
