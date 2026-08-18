from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Projectile, SpawnProjectile, TargetType, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.actions import (
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
)
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_spell_ingress import TensorResidentSpellActionIngress
from clasher.torch_sim.runtime_state import RuntimeEventOpcode
from clasher.torch_sim.state import WINNER_DRAW, WINNER_IN_PROGRESS


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _battle(spell_name: str, *, simultaneous: bool = False) -> BattleState:
    battle = BattleState(fast_path=False)
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = Troop(
        id=1,
        position=Position(9.5, 14.5),
        player_id=1,
        card_stats=stats,
        hitpoints=5_000,
        max_hitpoints=5_000,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=0,
        target_type=TargetType.BOTH,
    )
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    targets = [target]
    if simultaneous:
        reverse_target = copy.copy(target)
        reverse_target.id = 2
        reverse_target.player_id = 0
        reverse_target.position = Position(8.5, 17.5)
        targets.append(reverse_target)
    battle.entities = {entity.id: entity for entity in targets}
    battle.next_entity_id = len(targets) + 1
    for entity in targets:
        entity.battle_state = battle  # type: ignore[attr-defined]
    for player in battle.players:
        player.hand = [spell_name, "Knight", None, None]
        player.deck = [spell_name, "Knight", "Archer"]
        player.cycle_queue = deque(["Archer"])
        player.elixir = 10.0
    return battle


def _cast_at_command_boundary(battle: BattleState, spell_name: str) -> None:
    stats = battle.card_loader.get_card(spell_name)
    assert stats is not None
    assert battle.players[0].play_card(spell_name, stats)
    assert SPELL_REGISTRY[spell_name].cast(battle, 0, Position(9.5, 14.5))


def _compose(
    battle: BattleState,
    spell_name: str,
    *,
    device: str,
    max_entities: int,
    max_objects: int,
) -> tuple[BattleState, TensorResidentEngine]:
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=max_entities,
        max_objects=max_objects,
        event_capacity=4_096,
    )
    action_catalog = TensorActionCatalog.compile(engine.runtime.catalog)
    action_state = TensorActionState.from_battles([battle], action_catalog)
    kernel = TensorActionKernel(action_catalog)
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    ingress = kernel.ingress(
        action_state,
        torch.tensor([[action, NO_OP_ACTION]], device=engine.device),
    )
    spells = TensorResidentSpellActionIngress(
        engine.runtime,
        engine.objects,
        engine.projectile_bridge,
        engine.runtime.catalog,
    )
    result = spells.apply(
        ingress,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )
    assert result.committed.tolist() == [True]
    _cast_at_command_boundary(oracle, spell_name)
    return oracle, engine


def _assert_card_state(oracle: BattleState, engine: TensorResidentEngine) -> None:
    core = engine.runtime.battle
    for player_id in (0, 1):
        player = oracle.players[player_id]
        expected_hand = [core.card_to_id.get(name or "", 0) for name in player.hand]
        expected_cycle = [core.card_to_id[name] for name in player.cycle_queue]
        assert core.hand[0, player_id].tolist() == expected_hand
        assert core.cycle_queue_length[0, player_id].item() == len(expected_cycle)
        assert core.cycle_queue[0, player_id, : len(expected_cycle)].tolist() == (
            expected_cycle
        )
        assert core.elixir[0, player_id].item() == player.elixir


def _assert_event_ledger(
    oracle: BattleState,
    engine: TensorResidentEngine,
) -> None:
    events = engine.runtime.events
    count = int(events.count[0].item())
    assert events.sequence[0, :count].tolist() == list(range(count))
    opcodes = events.opcode[0, :count]
    target_ids = events.target_id[0, :count]
    amounts = events.amount[0, :count]
    for entity_id, entity in oracle.entities.items():
        if not isinstance(entity, Troop):
            continue
        target_damage = amounts[
            (opcodes == int(RuntimeEventOpcode.DAMAGE)) & (target_ids == entity_id)
        ].sum()
        assert target_damage.item() == entity.max_hitpoints - entity.hitpoints
    status = opcodes == int(RuntimeEventOpcode.STATUS)
    if bool(status.any().item()):
        assert set(target_ids[status].tolist()).issubset(oracle.entities)


def _assert_episode_state(
    oracle: BattleState,
    engine: TensorResidentEngine,
) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    active_slots = torch.where(active)[0]
    tensor_ids = core.entity_id[0, active_slots].tolist()
    assert tensor_ids == list(oracle.entities)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    assert core.time.item() == oracle.time
    assert core.tick.item() == oracle.tick
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    assert core.game_over.item() is oracle.game_over
    expected_winner = (
        WINNER_IN_PROGRESS
        if not oracle.game_over
        else WINNER_DRAW
        if oracle.winner is None
        else oracle.winner
    )
    assert core.winner.item() == expected_winner
    _assert_card_state(oracle, engine)

    for slot, entity_id in zip(active_slots.tolist(), tensor_ids, strict=True):
        entity = oracle.entities[entity_id]
        assert core.entity_hp[0, slot].item() == entity.hitpoints
        assert core.entity_x_units[0, slot].item() == round(entity.position.x * 1_000)
        assert core.entity_y_units[0, slot].item() == round(entity.position.y * 1_000)
        assert engine.runtime.status.stun_timer[0, slot].item() == entity.stun_timer

    python_objects = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, (AreaEffect, Projectile, SpawnProjectile))
    ]
    allocated = engine.objects.objects.allocated[0]
    assert engine.objects.objects.object_id[0, allocated].tolist() == [
        entity.id for entity in python_objects
    ]
    assert engine.objects.objects.x_units[0, allocated].tolist() == [
        round(entity.position.x * 1_000) for entity in python_objects
    ]
    assert engine.objects.objects.y_units[0, allocated].tolist() == [
        round(entity.position.y * 1_000) for entity in python_objects
    ]
    _assert_event_ledger(oracle, engine)


def _advance_exact_episode(
    oracle: BattleState,
    engine: TensorResidentEngine,
    *,
    ticks: int,
) -> None:
    _assert_episode_state(oracle, engine)
    no_op_order = torch.tensor([[0, 1]], device=engine.device)
    for _ in range(ticks):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=no_op_order)
        assert result.committed.tolist() == [True]
        _assert_episode_state(oracle, engine)


def test_zap_ingress_composes_with_complete_resident_ticks(
    tensor_device: str,
) -> None:
    battle = _battle("Zap")
    oracle, engine = _compose(
        battle,
        "Zap",
        device=tensor_device,
        max_entities=8,
        max_objects=4,
    )
    _advance_exact_episode(oracle, engine, ticks=20)


def test_simultaneous_zap_order_and_rng_survive_resident_ticks(
    tensor_device: str,
) -> None:
    battle = _battle("Zap", simultaneous=True)
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=8,
        max_objects=4,
        event_capacity=256,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [
                action_space.encode_action(0, 9, 14, 0),
                action_space.encode_action(0, 8, 17, 1),
            ]
        ],
        device=engine.device,
    )

    oracle_order = [0, 1]
    oracle.rng.shuffle(oracle_order)
    for player_id in oracle_order:
        stats = oracle.card_loader.get_card("Zap")
        assert stats is not None
        assert oracle.players[player_id].play_card("Zap", stats)
        target = Position(9.5, 14.5) if player_id == 0 else Position(8.5, 17.5)
        assert SPELL_REGISTRY["Zap"].cast(oracle, player_id, target)
    oracle.step_logic_ticks(1)
    result = engine.step(actions)

    assert result.committed.tolist() == [True]
    assert result.spell_ingress.player_order[0].tolist() == oracle_order
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    _assert_episode_state(oracle, engine)
    _advance_exact_episode(oracle, engine, ticks=4)


def test_rejected_second_spell_leaves_engine_safe_for_scalar_episode_fallback(
    tensor_device: str,
) -> None:
    battle = _battle("Zap", simultaneous=True)
    battle.players[1].hand[0] = "Freeze"
    battle.players[1].deck[0] = "Freeze"
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=8,
        max_objects=4,
        event_capacity=256,
    )
    action_catalog = TensorActionCatalog.compile(engine.runtime.catalog)
    state = TensorActionState.from_battles([battle], action_catalog)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    ingress = TensorActionKernel(action_catalog).ingress(
        state,
        torch.tensor(
            [
                [
                    action_space.encode_action(0, 9, 14, 0),
                    action_space.encode_action(0, 8, 17, 1),
                ]
            ],
            device=engine.device,
        ),
    )
    spells = TensorResidentSpellActionIngress(
        engine.runtime,
        engine.objects,
        engine.projectile_bridge,
        engine.runtime.catalog,
    )
    before_hand = engine.runtime.battle.hand.clone()
    before_elixir = engine.runtime.battle.elixir.clone()
    before_hp = engine.runtime.battle.entity_hp.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)
    before_objects = engine.objects.objects.allocated.clone()
    result = spells.apply(
        ingress,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )

    assert result.committed.tolist() == [False]
    assert result.unsupported_reasons == (
        "continuous freeze/slow area is not retained",
    )
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.battle.elixir, before_elixir)
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(engine.objects.objects.allocated, before_objects)
    _advance_exact_episode(oracle, engine, ticks=5)


@pytest.mark.parametrize(
    ("spell_name", "ticks", "max_entities", "max_objects"),
    (
        ("Fireball", 40, 12, 4),
        ("Arrows", 50, 40, 32),
        pytest.param(
            "GoblinBarrel",
            50,
            16,
            4,
        ),
        pytest.param(
            "GlobalLightning",
            110,
            8,
            4,
        ),
    ),
)
def test_object_spell_ingress_composes_through_complete_resident_lifecycle(
    tensor_device: str,
    spell_name: str,
    ticks: int,
    max_entities: int,
    max_objects: int,
) -> None:
    battle = _battle(spell_name)
    oracle, engine = _compose(
        battle,
        spell_name,
        device=tensor_device,
        max_entities=max_entities,
        max_objects=max_objects,
    )
    _advance_exact_episode(oracle, engine, ticks=ticks)


@pytest.mark.parametrize(
    ("spell_name", "ticks", "max_entities", "max_objects"),
    (
        ("Zap", 20, 8, 4),
        ("Fireball", 40, 12, 4),
        ("Arrows", 50, 40, 32),
        ("GoblinBarrel", 50, 16, 4),
        ("GlobalLightning", 110, 8, 4),
    ),
)
def test_engine_step_admits_episode_safe_spell_actions_exactly(
    tensor_device: str,
    spell_name: str,
    ticks: int,
    max_entities: int,
    max_objects: int,
) -> None:
    battle = _battle(spell_name)
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=max_entities,
        max_objects=max_objects,
        event_capacity=4_096,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    order = torch.tensor([[0, 1]], device=engine.device)
    assert engine.preflight(actions).supported.tolist() == [True]

    _cast_at_command_boundary(oracle, spell_name)
    oracle.step_logic_ticks(1)
    result = engine.step(actions, player_order=order)
    assert result.committed.tolist() == [True]
    assert result.spell_ingress.committed.tolist() == [True]
    assert result.deployment.committed.tolist() == [False]
    _assert_episode_state(oracle, engine)

    for _ in range(ticks - 1):
        oracle.step_logic_ticks(1)
        result = engine.step(player_order=order)
        assert result.committed.tolist() == [True]
        _assert_episode_state(oracle, engine)


@pytest.mark.parametrize(
    "spell_name",
    ("Rocket", "GiantSnowball"),
)
def test_engine_step_fails_closed_before_known_unsafe_projectile_spell_episode(
    tensor_device: str,
    spell_name: str,
) -> None:
    battle = _battle(spell_name)
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=tensor_device,
        max_entities=48,
        max_objects=32,
        event_capacity=4_096,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    before_hand = engine.runtime.battle.hand.clone()
    before_elixir = engine.runtime.battle.elixir.clone()
    before_hp = engine.runtime.battle.entity_hp.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)
    before_objects = engine.objects.objects.allocated.clone()

    preflight = engine.preflight(actions)
    result = engine.step(actions)

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [
        int(ResidentUnsupportedReason.SPELL_ACTION)
    ]
    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.battle.elixir, before_elixir)
    assert torch.equal(engine.runtime.battle.entity_hp, before_hp)
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(engine.objects.objects.allocated, before_objects)
    assert engine.runtime.battle.tick.tolist() == [0]


def test_engine_step_fails_closed_for_mixed_spell_and_troop_row() -> None:
    battle = _battle("Zap", simultaneous=True)
    battle.players[1].hand[0] = "Knight"
    battle.players[1].deck[0] = "Knight"
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=12, max_objects=4, event_capacity=256
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [
                action_space.encode_action(0, 9, 14, 0),
                action_space.encode_action(0, 9, 20, 1),
            ]
        ]
    )
    before_rng = engine.runtime.battle.rng.python_state(0)
    before_hand = engine.runtime.battle.hand.clone()
    preflight = engine.preflight(actions)
    result = engine.step(actions)

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [
        int(ResidentUnsupportedReason.MIXED_PAYLOAD)
    ]
    assert result.committed.tolist() == [False]
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert engine.runtime.battle.tick.tolist() == [0]
