from __future__ import annotations

import copy
from dataclasses import fields
from functools import lru_cache
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, TimedExplosive, Troop
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.resident_terminal_pipeline import (
    TensorResidentTerminalPipeline,
    TensorTerminalPipelineTargets,
    TerminalPipelineReason,
)
from clasher.torch_sim.resident_timed_terminal_payloads import (
    TensorTimedTerminalCatalog,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime

DEATH_SPAWN_ROOTS = (
    "Balloon",
    "BattleRam",
    "BombTower",
    "Golem",
    "LavaHound",
    "NightWitch",
    "SkeletonBarrel",
    "Tombstone",
)


@lru_cache(maxsize=2)
def _catalog(device: str) -> TensorTimedTerminalCatalog:
    loader = BattleState().card_loader
    enabled = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    cards = TensorCardCatalog.compile(loader, enabled, device=device)
    return TensorTimedTerminalCatalog.compile(loader, cards, list(enabled))


def _battle(root: str) -> tuple[BattleState, Entity]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(root)
    assert stats is not None
    entity_type = Building if str(stats.card_type).casefold() == "building" else Troop
    parent = battle._spawn_entity(entity_type, Position(9.0, 10.0), 0, stats)
    parent.deploy_delay_remaining = 0.0
    parent.placement_pending = False
    parent._spawn_hook_pending = False
    parent._spawn_hook_fired = True
    parent._facing_x_units = 300
    parent._facing_y_units = 400
    parent.freeze_expiry_time = 2.0
    return battle, parent


def _pipeline(
    battle: BattleState,
    *,
    device: str,
    max_entities: int = 32,
    event_capacity: int = 256,
) -> tuple[
    TensorBattleRuntime,
    TensorResidentTerminalPipeline,
    TensorTimedTerminalCatalog,
]:
    catalog = _catalog(device)
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
        catalog=catalog.terminal.cards,
    )
    catalog.prepare_runtime(runtime)
    state = catalog.create_state(1, 16)
    targets = TensorTerminalPipelineTargets.from_battles(runtime, [battle], catalog)
    return runtime, TensorResidentTerminalPipeline(catalog, state, targets), catalog


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    match = torch.nonzero(runtime.battle.entity_id[0] == entity_id).flatten()
    assert match.numel() == 1
    return int(match.item())


def _mark_dead(
    runtime: TensorBattleRuntime,
    entity_id: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    slot = _slot(runtime, entity_id)
    runtime.battle.entity_hp[0, slot] = 0.0
    runtime.battle.entity_active[0, slot] = False
    runtime.phases.death_pending[0, slot] = True
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, slot] = True
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    facing_x[0, slot] = 300
    facing_y[0, slot] = 400
    return dead, facing_x, facing_y


def _oracle_object_tick(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._run_object_phase(battle.dt, ids, ids)
    battle._cleanup_dead_entities()


def _represented(
    runtime: TensorBattleRuntime,
) -> list[tuple[int, str, int, int, int, float]]:
    rows: list[tuple[int, str, int, int, int, float]] = []
    for slot in range(runtime.max_entities):
        if not bool(runtime.entity_pool.active[0, slot].item()):
            continue
        entity_id = int(runtime.battle.entity_id[0, slot].item())
        card = runtime.battle.card_names[
            int(runtime.battle.entity_card[0, slot].item())
        ]
        rows.append(
            (
                entity_id,
                card,
                int(runtime.battle.entity_player[0, slot].item()),
                int(runtime.battle.entity_x_units[0, slot].item()),
                int(runtime.battle.entity_y_units[0, slot].item()),
                float(runtime.battle.entity_hp[0, slot].item()),
            )
        )
    return sorted(rows)


def _oracle_represented(
    battle: BattleState,
) -> list[tuple[int, str, int, int, int, float]]:
    return [
        (
            entity_id,
            str(getattr(entity.card_stats, "name", "")),
            entity.player_id,
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            float(entity.hitpoints),
        )
        for entity_id, entity in sorted(battle.entities.items())
    ]


@pytest.mark.parametrize("root", DEATH_SPAWN_ROOTS)
@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_all_enabled_death_spawn_roots_match_complete_scalar_lifecycle(
    root: str,
    device: str,
) -> None:
    source, parent = _battle(root)
    oracle = copy.deepcopy(source)
    oracle_parent = oracle.entities[parent.id]
    oracle_parent.take_damage(oracle_parent.hitpoints)
    oracle._cleanup_dead_entities()
    runtime, pipeline, _ = _pipeline(source, device=device)
    dead, facing_x, facing_y = _mark_dead(runtime, parent.id)

    result = pipeline.step(
        runtime,
        dead,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )
    assert result.committed.tolist() == [True]
    if root in {"Balloon", "BombTower", "SkeletonBarrel"}:
        active_objects = (
            pipeline.state.objects.allocated & pipeline.state.objects.active
        )
        assert pipeline.state.objects.age_ms[active_objects].tolist() == [0]

    empty_dead = torch.zeros_like(dead)
    for _ in range(80):
        if not any(
            isinstance(entity, TimedExplosive) for entity in oracle.entities.values()
        ):
            break
        _oracle_object_tick(oracle)
        runtime.events.clear()
        result = pipeline.step(
            runtime,
            empty_dead,
            facing_x_units=torch.zeros_like(facing_x),
            facing_y_units=torch.zeros_like(facing_y),
        )
        assert result.committed.tolist() == [True]

    assert _represented(runtime) == _oracle_represented(oracle)
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id


def _snapshot(
    runtime: TensorBattleRuntime,
    pipeline: TensorResidentTerminalPipeline,
) -> dict[str, torch.Tensor]:
    values: dict[str, torch.Tensor] = {}
    for owner_name, owner in (
        ("battle", runtime.battle),
        ("pool", runtime.entity_pool),
        ("status", runtime.status),
        ("phases", runtime.phases),
        ("events", runtime.events),
        ("objects", pipeline.state.objects),
    ):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if isinstance(value, torch.Tensor):
                values[f"{owner_name}.{descriptor.name}"] = value.clone()
    return values


def test_synchronous_explosion_victim_death_payload_rolls_back_whole_row() -> None:
    battle, parent = _battle("Balloon")
    golem_stats = battle.card_loader.get_card("Golem")
    assert golem_stats is not None
    victim = cast(
        Troop,
        battle._spawn_entity(Troop, Position(9.0, 10.0), 1, golem_stats),
    )
    victim.hitpoints = 1.0
    runtime, pipeline, _ = _pipeline(battle, device="cpu")
    dead, facing_x, facing_y = _mark_dead(runtime, parent.id)
    assert pipeline.step(
        runtime, dead, facing_x_units=facing_x, facing_y_units=facing_y
    ).committed.tolist() == [True]
    empty = torch.zeros_like(dead)

    for _ in range(80):
        before = _snapshot(runtime, pipeline)
        result = pipeline.step(
            runtime,
            empty,
            facing_x_units=torch.zeros_like(facing_x),
            facing_y_units=torch.zeros_like(facing_y),
        )
        if not result.committed.item():
            assert result.reason.tolist() == [TerminalPipelineReason.EXPLOSION]
            after = _snapshot(runtime, pipeline)
            for name, value in before.items():
                assert torch.equal(after[name], value), name
            break
        runtime.events.clear()
    else:
        raise AssertionError("timed explosion did not reach fail-closed victim")


def test_pipeline_preserves_shield_damage_death_and_knockback_outputs() -> None:
    battle, parent = _battle("SkeletonBarrel")
    guard_stats = battle.card_loader.get_card("Guards")
    knight_stats = battle.card_loader.get_card("Knight")
    assert guard_stats is not None and knight_stats is not None
    guard = cast(
        Troop,
        battle._spawn_entity(Troop, Position(9.0, 10.0), 1, guard_stats),
    )
    knight = cast(
        Troop,
        battle._spawn_entity(Troop, Position(10.0, 10.0), 1, knight_stats),
    )
    runtime, pipeline, _ = _pipeline(battle, device="cpu")
    dead, facing_x, facing_y = _mark_dead(runtime, parent.id)
    pipeline.step(runtime, dead, facing_x_units=facing_x, facing_y_units=facing_y)
    empty = torch.zeros_like(dead)

    terminal_result = None
    for _ in range(80):
        runtime.events.clear()
        result = pipeline.step(
            runtime,
            empty,
            facing_x_units=torch.zeros_like(facing_x),
            facing_y_units=torch.zeros_like(facing_y),
        )
        assert result.committed.tolist() == [True]
        if result.terminal_events.object_id.numel():
            terminal_result = result
            break
    assert terminal_result is not None
    assert terminal_result.explosion.shield_absorbed.any()
    assert (
        runtime.battle.entity_hp[0, _slot(runtime, guard.id)].item() == guard.hitpoints
    )
    assert runtime.battle.entity_hp[0, _slot(runtime, knight.id)] < knight.hitpoints
    assert terminal_result.explosion.knockback.valid.any()


def test_mixed_direct_and_timed_parents_allocate_in_id_order_after_slot_permutation() -> (
    None
):
    battle, timed_parent = _battle("Balloon")
    golem_stats = battle.card_loader.get_card("Golem")
    assert golem_stats is not None
    direct_parent = battle._spawn_entity(Troop, Position(12.0, 10.0), 0, golem_stats)
    direct_parent.deploy_delay_remaining = 0.0
    direct_parent.placement_pending = False
    oracle = copy.deepcopy(battle)
    for entity_id in (timed_parent.id, direct_parent.id):
        entity = oracle.entities[entity_id]
        entity.take_damage(entity.hitpoints)
    oracle._cleanup_dead_entities()

    runtime, pipeline, _ = _pipeline(battle, device="cpu")
    permutation = torch.tensor([1, 0, *range(2, runtime.max_entities)])
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.entity_pool.active.shape
            ):
                value.copy_(value[:, permutation])
    runtime.entity_pool.active.copy_(runtime.entity_pool.active[:, permutation])
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, timed_parent.id)] = True
    dead[0, _slot(runtime, direct_parent.id)] = True
    runtime.battle.entity_active[dead] = False
    runtime.battle.entity_hp[dead] = 0.0

    result = pipeline.step(
        runtime,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.ones_like(runtime.battle.entity_y_units),
    )

    assert result.committed.tolist() == [True]
    assert _represented(runtime) == _oracle_represented(oracle)
    assert runtime.entity_pool.next_entity_id.item() == 6


def test_lethal_ordinary_explosion_victim_is_removed_in_same_cleanup() -> None:
    battle, parent = _battle("Balloon")
    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None
    victim = cast(
        Troop,
        battle._spawn_entity(Troop, Position(9.0, 10.0), 1, knight_stats),
    )
    victim.hitpoints = 1.0
    runtime, pipeline, _ = _pipeline(battle, device="cpu")
    dead, facing_x, facing_y = _mark_dead(runtime, parent.id)
    pipeline.step(runtime, dead, facing_x_units=facing_x, facing_y_units=facing_y)
    empty = torch.zeros_like(dead)

    for _ in range(80):
        runtime.events.clear()
        result = pipeline.step(
            runtime,
            empty,
            facing_x_units=torch.zeros_like(facing_x),
            facing_y_units=torch.zeros_like(facing_y),
        )
        assert result.committed.tolist() == [True]
        if result.terminal_events.object_id.numel():
            assert result.explosion.died.any()
            assert not (runtime.battle.entity_id == victim.id).any()
            break
    else:
        raise AssertionError("timed explosion did not resolve")
