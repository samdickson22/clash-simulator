from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Graveyard, Troop
from clasher.spells import SPELL_REGISTRY, GraveyardSpell
from clasher.torch_sim.resident_graveyard import (
    TensorGraveyardCatalog,
    TensorResidentGraveyards,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _battle() -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    battle.players[0].hand = ["Graveyard", "Skeleton", None, None]
    battle.players[0].deck = ["Graveyard", "Skeleton"]
    battle.players[0].cycle_queue = deque()
    battle.players[1].hand = ["Graveyard", "Skeleton", None, None]
    battle.players[1].deck = ["Graveyard", "Skeleton"]
    battle.players[1].cycle_queue = deque()
    return battle


def _runtime_owner(
    battles: list[BattleState],
    *,
    device: str = "cpu",
    max_entities: int = 32,
    event_capacity: int = 256,
    graveyard_capacity: int = 2,
) -> tuple[TensorBattleRuntime, TensorResidentGraveyards]:
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
    )
    owner = TensorResidentGraveyards.from_battles(
        runtime, battles, capacity=graveyard_capacity
    )
    return runtime, owner


def test_catalog_uses_serialized_deadlines_offsets_and_child_payload() -> None:
    battle = _battle()
    runtime, _ = _runtime_owner([battle])
    catalog = TensorGraveyardCatalog.compile(runtime)
    card = runtime.battle.card_to_id["Graveyard"]
    child = runtime.battle.card_to_id["Skeleton"]
    spell = SPELL_REGISTRY["Graveyard"]
    assert isinstance(spell, GraveyardSpell)

    assert catalog.supported[card].item() is True
    assert catalog.reason[card] == ""
    assert catalog.duration_ms[card].item() == 9_000
    assert catalog.spawn_count[card].item() == 12
    assert catalog.deadlines_ms[card, :12].tolist() == [
        round(value * 1_000) for value in spell.spawn_deadlines
    ]
    assert catalog.offsets_units[card, :12].tolist() == [
        [round(x * 1_000), round(y * 1_000)] for x, y in spell.spawn_offsets
    ]
    assert catalog.child_card_id[card].item() == child
    assert catalog.child_hitpoints[card].item() == 81
    assert catalog.child_hp_integer_kind[card].item() is True
    assert catalog.child_deploy_ms[card].item() == 500


def test_due_handoff_capacity_failure_is_atomic_and_rng_neutral() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner(
        [battle], max_entities=1, event_capacity=1, graveyard_capacity=1
    )
    runtime.events.count.fill_(runtime.events.capacity)
    card = runtime.battle.card_to_id["Graveyard"]
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_events = runtime.events.count.clone()
    before_rng = runtime.battle.rng.python_state(0)

    supported = owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )

    assert supported.tolist() == [False]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(runtime.events.count, before_events)
    assert runtime.battle.rng.python_state(0) == before_rng
    assert not owner.active.any()


def test_scheduled_spawn_capacity_failure_rolls_back_area_clock_and_ids() -> None:
    battle = _battle()
    runtime, owner = _runtime_owner(
        [battle], max_entities=1, event_capacity=32, graveyard_capacity=1
    )
    card = runtime.battle.card_to_id["Graveyard"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    for _ in range(23):
        assert owner.step_(runtime).committed.tolist() == [True]
    before_age = owner.age_ms.clone()
    before_index = owner.next_spawn_index.clone()
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_events = runtime.events.count.clone()
    before_rng = runtime.battle.rng.python_state(0)

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert torch.equal(owner.age_ms, before_age)
    assert torch.equal(owner.next_spawn_index, before_index)
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(runtime.events.count, before_events)
    assert runtime.battle.rng.python_state(0) == before_rng


def test_clone_fork_and_selective_reset_are_independent() -> None:
    battles = [_battle(), _battle()]
    runtime, owner = _runtime_owner(battles)
    card = runtime.battle.card_to_id["Graveyard"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card, card]),
        player_ids=torch.tensor([0, 1]),
        target_x_units=torch.tensor([9_000, 8_000]),
        target_y_units=torch.tensor([14_000, 18_000]),
        valid=torch.tensor([True, True]),
    ).all()
    clone = owner.clone()
    fork = owner.fork([1])
    assert clone.active.data_ptr() != owner.active.data_ptr()
    assert fork.player_id[:, 0].tolist() == [1]
    clone.age_ms[0, 0] = 1_200
    clone.next_spawn_index[0, 0] = 1
    owner.reset_rows_([0], clone, [0])
    assert owner.age_ms[:, 0].tolist() == [1_200, 0]
    assert owner.next_spawn_index[:, 0].tolist() == [1, 0]


def test_large_tick_spawns_every_crossed_deadline_in_stable_order() -> None:
    seed = _battle()
    oracle = copy.deepcopy(seed)
    runtime, owner = _runtime_owner([seed])
    spell = SPELL_REGISTRY["Graveyard"]
    assert isinstance(spell, GraveyardSpell)
    assert spell.cast(oracle, 0, Position(9, 14))
    card = runtime.battle.card_to_id["Graveyard"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    graveyard = oracle.entities[1]
    assert type(graveyard) is Graveyard
    graveyard.update(2.4, oracle)
    runtime.battle.dt.fill_(2.4)
    runtime.battle.tick_milliseconds.fill_(2_400)

    result = owner.step_(runtime)

    assert result.committed.tolist() == [True]
    assert result.spawned_ids[0, result.spawned[0]].tolist() == [2, 3, 4]
    assert runtime.battle.entity_x_units[0, 1:4].tolist() == [
        round(oracle.entities[entity_id].position.x * 1_000) for entity_id in (2, 3, 4)
    ]
    assert runtime.battle.entity_y_units[0, 1:4].tolist() == [
        round(oracle.entities[entity_id].position.y * 1_000) for entity_id in (2, 3, 4)
    ]
    assert owner.next_spawn_index[0, 0].item() == 3


@pytest.mark.parametrize(
    ("player_id", "center"),
    ((0, Position(17.5, 14.0)), (1, Position(0.5, 18.0))),
)
def test_complete_graveyard_lifecycle_matches_python_without_rng_or_terrain_snap(
    tensor_device: str,
    player_id: int,
    center: Position,
) -> None:
    seed = _battle()
    oracle = copy.deepcopy(seed)
    runtime, owner = _runtime_owner(
        [seed], device=tensor_device, max_entities=32, event_capacity=256
    )
    spell = SPELL_REGISTRY["Graveyard"]
    assert isinstance(spell, GraveyardSpell)
    assert spell.cast(oracle, player_id, center)
    graveyard = oracle.entities[1]
    assert type(graveyard) is Graveyard
    # Graveyard is an ordinary non-carrier effect container. Even an invalid
    # synthetic expiry on it must not leak Freeze onto scheduled children.
    graveyard.freeze_expiry_time = 100.0
    card = runtime.battle.card_to_id["Graveyard"]
    assert owner.materialize_due_spell_actions_(
        runtime,
        card_ids=torch.tensor([card], device=runtime.device),
        player_ids=torch.tensor([player_id], device=runtime.device),
        target_x_units=torch.tensor([round(center.x * 1_000)], device=runtime.device),
        target_y_units=torch.tensor([round(center.y * 1_000)], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    ).all()
    assert runtime.events.phase[0, 0].item() == TickPhase.COMMANDS
    assert runtime.events.opcode[0, 0].item() == RuntimeEventOpcode.SPAWN
    assert runtime.events.source_id[0, 0].item() == 0
    assert runtime.events.target_id[0, 0].item() == graveyard.id
    assert runtime.events.x_units[0, 0].item() == round(center.x * 1_000)
    assert runtime.events.y_units[0, 0].item() == round(center.y * 1_000)
    assert runtime.events.payload[0, 0].item() == card
    spawn_event_count = 1

    for _ in range(181):
        before_ids = set(oracle.entities)
        event_start = int(runtime.events.count[0].item())
        oracle.time += oracle.dt
        oracle.tick += 1
        live = [
            entity for entity in oracle.entities.values() if type(entity) is Graveyard
        ]
        for entity in live:
            entity.update(oracle.dt, oracle)
        oracle._cleanup_dead_entities()
        runtime.battle.time += runtime.battle.dt
        runtime.battle.tick += 1
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()

        new_ids = sorted(set(oracle.entities) - before_ids)
        spawned_ids = result.spawned_ids[0, result.spawned[0]].tolist()
        assert spawned_ids == new_ids
        for entity_id in new_ids:
            spawned_entity = oracle.entities[entity_id]
            assert isinstance(spawned_entity, Troop)
            slot = int(
                torch.where(runtime.battle.entity_id[0] == entity_id)[0][0].item()
            )
            assert runtime.battle.entity_x_units[0, slot].item() == round(
                spawned_entity.position.x * 1_000
            )
            assert runtime.battle.entity_y_units[0, slot].item() == round(
                spawned_entity.position.y * 1_000
            )
            assert runtime.battle.entity_hp[0, slot].item() == spawned_entity.hitpoints
            assert runtime.battle.entity_hp_integer_kind[0, slot].item() is (
                type(spawned_entity.hitpoints) is int
            )
            assert runtime.battle.entity_deploy_delay[0, slot].item() == (
                spawned_entity.deploy_delay_remaining
            )
            assert runtime.battle.entity_placement_pending[0, slot].item() is (
                spawned_entity.placement_pending
            )
            assert runtime.battle.entity_spawn_hook_pending[0, slot].item() is (
                spawned_entity._spawn_hook_pending
            )
            assert runtime.battle.entity_spawn_hook_fired[0, slot].item() is (
                getattr(spawned_entity, "_spawn_hook_fired", False)
            )
            assert runtime.status.freeze_expiry_time[0, slot].item() == 0.0
            assert owner.target_distance_discount_sq_units[0, slot].item() == (
                spawned_entity._native_target_distance_discount_sq_units
            )

        removed_area = 1 in before_ids and 1 not in oracle.entities
        expected = [
            (TickPhase.COMMANDS, RuntimeEventOpcode.SPAWN, entity_id, 0)
            for entity_id in new_ids
        ]
        if removed_area:
            expected.extend(
                (
                    (TickPhase.COMBAT, RuntimeEventOpcode.DAMAGE, 0, 1),
                    (TickPhase.COMBAT, RuntimeEventOpcode.DEATH, 0, 1),
                )
            )
        stop = int(runtime.events.count[0].item())
        actual = [
            (
                int(runtime.events.phase[0, slot].item()),
                int(runtime.events.opcode[0, slot].item()),
                int(runtime.events.source_id[0, slot].item()),
                int(runtime.events.target_id[0, slot].item()),
            )
            for slot in range(event_start, stop)
        ]
        assert actual == expected
        expected_payloads = [runtime.battle.card_to_id["Skeleton"] for _ in new_ids] + (
            [0, 0] if removed_area else []
        )
        assert runtime.events.payload[0, event_start:stop].tolist() == expected_payloads
        spawn_event_count += len(new_ids)

        retained = owner.active[0]
        scalar_live = [
            entity for entity in oracle.entities.values() if type(entity) is Graveyard
        ]
        assert int(retained.sum().item()) == len(scalar_live)
        if scalar_live:
            lane = int(torch.where(retained)[0][0].item())
            assert owner.age_ms[0, lane].item() == round(
                scalar_live[0].time_alive * 1_000
            )
            assert owner.next_spawn_index[0, lane].item() == (
                scalar_live[0].skeletons_spawned
            )

    assert not owner.active.any()
    assert sorted(oracle.entities) == list(range(2, 14))
    active = runtime.entity_pool.active[0]
    assert runtime.battle.entity_id[0, active].tolist() == list(range(2, 14))
    assert runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id == 14
    assert spawn_event_count == 13
