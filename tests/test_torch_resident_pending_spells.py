from __future__ import annotations

import copy
import random
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Projectile, SpawnProjectile, TargetType, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import (
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
)
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.projectile_bridge import (
    TensorResidentProjectileSpellBridge,
)
from clasher.torch_sim.resident_engine import _resident_deployment_catalog_closure
from clasher.torch_sim.resident_pending_spells import TensorResidentPendingSpells
from clasher.torch_sim.runtime_objects import TensorRuntimeObjectPhase
from clasher.torch_sim.runtime_state import TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _troop(
    battle: BattleState,
    name: str,
    entity_id: int,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = Troop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=2_000,
        max_hitpoints=2_000,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=0,
        target_type=TargetType.BOTH,
    )
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.battle_state = battle  # type: ignore[attr-defined]
    return entity


def _battle(spell_name: str, *, simultaneous: bool = False) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(730_000))
    first = _troop(battle, "Knight", 1, 1, Position(9.5, 14.5))
    entities: dict[int, Entity] = {1: first}
    if simultaneous:
        entities[2] = _troop(battle, "Knight", 2, 0, Position(8.5, 17.5))
    battle.entities = entities
    battle.next_entity_id = max(entities) + 1
    for player in battle.players:
        player.hand = [spell_name, "Knight", "Archer", "Zap"]
        player.deck = [name for name in player.hand if name is not None]
        player.cycle_queue = deque()
        player.elixir = 20.0
    return battle


def _owners(
    battles: list[BattleState],
    spell_names: set[str],
    *,
    device: str,
    max_entities: int = 128,
    max_objects: int = 64,
    pending_capacity: int = 8,
) -> tuple[
    TensorActionKernel,
    TensorActionState,
    TensorBattleRuntime,
    TensorRuntimeObjectPhase,
    TensorResidentProjectileSpellBridge,
    TensorResidentPendingSpells,
]:
    names = {"Knight", "Archer", "Zap", *spell_names}
    loader, closure = _resident_deployment_catalog_closure(
        battles[0].card_loader, names
    )
    cards = TensorCardCatalog.compile(loader, closure, device=device)
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=max_entities,
        max_cards=16,
        event_capacity=4_096,
        catalog=cards,
    )
    objects = TensorRuntimeObjectPhase.from_battles(
        runtime, battles, max_objects=max_objects
    )
    bridge = TensorResidentProjectileSpellBridge.from_battles(runtime, objects, battles)
    action_catalog = TensorActionCatalog.compile(cards)
    kernel = TensorActionKernel(action_catalog)
    state = TensorActionState.from_battles(battles, action_catalog)
    pending = TensorResidentPendingSpells.from_battles(
        runtime, battles, cards, capacity=pending_capacity
    )
    return kernel, state, runtime, objects, bridge, pending


def _action(spell_name: str, player_id: int) -> int:
    del spell_name
    x, y = (9, 14) if player_id == 0 else (8, 17)
    return DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, x, y, player_id
    )


def _hand_names(runtime: TensorBattleRuntime, player: int) -> list[str | None]:
    return [
        None if int(card) == 0 else runtime.battle.card_names[int(card)]
        for card in runtime.battle.hand[0, player].tolist()
    ]


def _cycle_names(runtime: TensorBattleRuntime, player: int) -> list[str]:
    length = int(runtime.battle.cycle_queue_length[0, player].item())
    return [
        runtime.battle.card_names[int(card)]
        for card in runtime.battle.cycle_queue[0, player, :length].tolist()
    ]


def _advance_to_due(
    oracle: BattleState,
    runtime: TensorBattleRuntime,
    objects: TensorRuntimeObjectPhase,
    bridge: TensorResidentProjectileSpellBridge,
    pending: TensorResidentPendingSpells,
) -> None:
    for tick in range(20):
        oracle.step_logic_ticks(1)
        runtime.battle.time.add_(runtime.battle.dt)
        runtime.battle.tick.add_(1)
        before_id = runtime.entity_pool.next_entity_id.clone()
        before_rng = runtime.battle.rng.python_state(0)
        result = pending.resolve_due_(runtime, objects, bridge)
        assert result.committed.tolist() == [True]
        if tick < 19:
            assert torch.equal(runtime.entity_pool.next_entity_id, before_id)
            assert runtime.battle.rng.python_state(0) == before_rng
            assert pending.active.any()
    assert not pending.active.any()
    assert oracle._pending_spell_casts == []


@pytest.mark.parametrize(
    "spell_name",
    ("Arrows", "Fireball", "GiantSnowball", "GoblinBarrel", "Rocket", "Zap"),
)
def test_delayed_spell_action_and_due_payload_match_python(
    tensor_device: str,
    spell_name: str,
) -> None:
    seed = _battle(spell_name)
    oracle = copy.deepcopy(seed)
    tensor_battle = copy.deepcopy(seed)
    kernel, state, runtime, objects, bridge, pending = _owners(
        [tensor_battle], {spell_name}, device=tensor_device
    )
    action = _action(spell_name, 0)
    ingress = kernel.ingress(
        state,
        torch.tensor([[action, NO_OP_ACTION]], device=runtime.device),
    )
    before_id = runtime.entity_pool.next_entity_id.clone()
    before_hp = runtime.battle.entity_hp.clone()
    before_rng = runtime.battle.rng.python_state(0)

    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        oracle, 0, action
    )
    result = pending.enqueue_(
        runtime,
        bridge,
        ingress,
        player_order=torch.tensor([[0, 1]], device=runtime.device),
    )

    assert result.committed.tolist() == [True]
    assert result.queued_count.tolist() == [1]
    assert _hand_names(runtime, 0) == oracle.players[0].hand
    assert _cycle_names(runtime, 0) == list(oracle.players[0].cycle_queue)
    assert runtime.battle.elixir[0, 0].item() == oracle.players[0].elixir
    assert torch.equal(runtime.entity_pool.next_entity_id, before_id)
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert runtime.battle.rng.python_state(0) == before_rng
    assert pending.execute_at[pending.active].tolist() == [1.0]
    assert pending.sequence[pending.active].tolist() == [0]
    assert pending.next_sequence.tolist() == [1]
    oracle_pending = oracle._pending_spell_casts[0]
    assert runtime.battle.card_names[int(pending.card_id[pending.active][0])] == (
        oracle_pending.spell_name
    )
    assert pending.player_id[pending.active].tolist() == [oracle_pending.player_id]
    assert pending.target_x_units[pending.active].tolist() == [
        round(oracle_pending.position.x * 1_000)
    ]
    assert pending.target_y_units[pending.active].tolist() == [
        round(oracle_pending.position.y * 1_000)
    ]

    _advance_to_due(oracle, runtime, objects, bridge, pending)

    assert runtime.entity_pool.next_entity_id.tolist() == [oracle.next_entity_id]
    assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    assert runtime.battle.entity_hp[0, 0].item() == oracle.entities[1].hitpoints
    python_objects = sorted(
        (
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, (Projectile, SpawnProjectile))
        ),
        key=lambda entity: entity.id,
    )
    allocated = objects.objects.allocated[0]
    assert objects.objects.object_id[0, allocated].tolist() == [
        entity.id for entity in python_objects
    ]
    assert objects.objects.target_x_units[0, allocated].tolist() == [
        round(entity.target_position.x * 1_000) for entity in python_objects
    ]
    assert objects.objects.target_y_units[0, allocated].tolist() == [
        round(entity.target_position.y * 1_000) for entity in python_objects
    ]


def test_simultaneous_fireballs_due_order_rng_and_ids_match_python(
    tensor_device: str,
) -> None:
    seed = _battle("Fireball", simultaneous=True)
    oracle = copy.deepcopy(seed)
    tensor_battle = copy.deepcopy(seed)
    kernel, state, runtime, objects, bridge, pending = _owners(
        [tensor_battle],
        {"Fireball"},
        device=tensor_device,
        max_entities=16,
        max_objects=4,
    )
    actions = torch.tensor(
        [[_action("Fireball", 0), _action("Fireball", 1)]], device=runtime.device
    )
    ingress = kernel.ingress(state, actions)
    order = (1, 0)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    for player in order:
        assert action_space.apply_action(oracle, player, int(actions[0, player]))
    result = pending.enqueue_(
        runtime,
        bridge,
        ingress,
        player_order=torch.tensor([order], device=runtime.device),
    )

    assert result.committed.tolist() == [True]
    active_slots = pending.active[0]
    assert pending.player_id[0, active_slots].tolist() == [1, 0]
    assert pending.sequence[0, active_slots].tolist() == [0, 1]
    _advance_to_due(oracle, runtime, objects, bridge, pending)

    python_objects = sorted(
        (
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    allocated = objects.objects.allocated[0]
    assert len(python_objects) == 2
    assert objects.objects.object_id[0, allocated].tolist() == [
        entity.id for entity in python_objects
    ]
    assert objects.objects.player[0, allocated].tolist() == [
        entity.player_id for entity in python_objects
    ]
    assert runtime.entity_pool.next_entity_id.tolist() == [oracle.next_entity_id]
    assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()


def test_enqueue_capacity_failure_rolls_back_whole_row() -> None:
    battle = _battle("Fireball", simultaneous=True)
    kernel, state, runtime, _, bridge, pending = _owners(
        [battle], {"Fireball"}, device="cpu", pending_capacity=1
    )
    actions = torch.tensor([[_action("Fireball", 0), _action("Fireball", 1)]])
    ingress = kernel.ingress(state, actions)
    before_hand = runtime.battle.hand.clone()
    before_elixir = runtime.battle.elixir.clone()
    before_rng = runtime.battle.rng.python_state(0)
    result = pending.enqueue_(
        runtime, bridge, ingress, player_order=torch.tensor([[0, 1]])
    )
    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert not pending.active.any()
    assert torch.equal(runtime.battle.hand, before_hand)
    assert torch.equal(runtime.battle.elixir, before_elixir)
    assert runtime.battle.rng.python_state(0) == before_rng


def test_enqueue_capacity_failure_rolls_back_only_rejected_row() -> None:
    battles = [_battle("Fireball", simultaneous=True), _battle("Fireball")]
    kernel, state, runtime, _, bridge, pending = _owners(
        battles, {"Fireball"}, device="cpu", pending_capacity=1
    )
    actions = torch.tensor(
        [
            [_action("Fireball", 0), _action("Fireball", 1)],
            [_action("Fireball", 0), NO_OP_ACTION],
        ]
    )
    ingress = kernel.ingress(state, actions)
    before_hand = runtime.battle.hand.clone()
    result = pending.enqueue_(
        runtime,
        bridge,
        ingress,
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )
    assert result.committed.tolist() == [False, True]
    assert result.capacity_rejected.tolist() == [True, False]
    assert pending.active.tolist() == [[False], [True]]
    assert torch.equal(runtime.battle.hand[0], before_hand[0])
    assert not torch.equal(runtime.battle.hand[1], before_hand[1])


def test_from_battles_restores_live_python_pending_cast() -> None:
    battle = _battle("Zap")
    action = _action("Zap", 0)
    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        battle, 0, action
    )
    _, _, runtime, _, _, pending = _owners(
        [battle], {"Zap"}, device="cpu", pending_capacity=2
    )
    python_pending = battle._pending_spell_casts[0]
    assert pending.active.tolist() == [[True, False]]
    assert pending.execute_at[0, 0].item() == python_pending.execute_at
    assert pending.sequence[0, 0].item() == python_pending.sequence
    assert runtime.battle.card_names[int(pending.card_id[0, 0].item())] == (
        python_pending.spell_name
    )
    assert pending.player_id[0, 0].item() == python_pending.player_id
    assert pending.next_sequence.tolist() == [battle._next_spell_cast_sequence]


def test_due_capacity_failure_rolls_back_first_materialization() -> None:
    battle = _battle("Fireball", simultaneous=True)
    kernel, state, runtime, objects, bridge, pending = _owners(
        [battle],
        {"Fireball"},
        device="cpu",
        max_objects=1,
        pending_capacity=2,
    )
    actions = torch.tensor([[_action("Fireball", 0), _action("Fireball", 1)]])
    ingress = kernel.ingress(state, actions)
    assert pending.enqueue_(
        runtime, bridge, ingress, player_order=torch.tensor([[0, 1]])
    ).committed.all()
    runtime.battle.time.fill_(1.0)
    before_id = runtime.entity_pool.next_entity_id.clone()
    before_rng = runtime.battle.rng.python_state(0)
    before_pending = pending.active.clone()
    result = pending.resolve_due_(runtime, objects, bridge)
    assert result.committed.tolist() == [False]
    assert result.failed_rows.tolist() == [True]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_id)
    assert runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(pending.active, before_pending)
    assert not objects.objects.allocated.any()


def test_clone_fork_and_selective_reset_isolate_pending_rows() -> None:
    battles = [_battle("Zap"), _battle("Fireball")]
    _, _, runtime, _, _, pending = _owners(
        battles, {"Zap", "Fireball"}, device="cpu", pending_capacity=4
    )
    pending.active[0, 0] = True
    pending.card_id[0, 0] = runtime.battle.card_to_id["Zap"]
    pending.sequence[0, 0] = 4
    pending.next_sequence[0] = 5
    pending.active[1, 1] = True
    pending.card_id[1, 1] = runtime.battle.card_to_id["Fireball"]
    pending.sequence[1, 1] = 8
    pending.next_sequence[1] = 9

    cloned = pending.clone()
    cloned.active[0, 0] = False
    assert pending.active[0, 0]
    forked = pending.fork([1, 0, 1])
    assert forked.sequence[:, :2].tolist() == [[0, 8], [4, 0], [0, 8]]
    replacement = pending.fork([1])
    pending.reset_rows_([0], replacement)
    assert pending.sequence[0].tolist() == replacement.sequence[0].tolist()
    assert pending.next_sequence.tolist() == [9, 9]
