from __future__ import annotations

import copy
import inspect
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.resident_action_router import TensorResidentActionRouter
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.runtime_state import RuntimeEventOpcode


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _battle(character: str, spell: str = "Zap") -> BattleState:
    battle = BattleState(fast_path=False)
    battle.players[0].hand = [character, "Archer", "Skeletons", "Zap"]
    battle.players[0].deck = [character, "Archer", "Skeletons", "Zap"]
    battle.players[0].cycle_queue = deque(["Knight"])
    battle.players[0].elixir = 10.0
    battle.players[1].hand = [spell, "Knight", "Archer", "Skeletons"]
    battle.players[1].deck = [spell, "Knight", "Archer", "Skeletons"]
    battle.players[1].cycle_queue = deque(["Cannon"])
    battle.players[1].elixir = 10.0
    return battle


def _router(
    battle: BattleState,
    device: str,
) -> tuple[TensorResidentEngine, TensorResidentActionRouter]:
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=24,
        max_objects=8,
        event_capacity=256,
    )
    return engine, TensorResidentActionRouter(
        engine.runtime,
        engine.objects,
        engine.projectile_bridge,
        engine.deployment,
        engine.spell_ingress,
    )


def _actions() -> tuple[int, int]:
    space = DiscreteTileActionSpace(canonical_perspective=True)
    return (
        space.encode_action(0, 9, 10, 0),
        space.encode_action(0, 9, 10, 1),
    )


def _two_character_battle(character: str) -> BattleState:
    battle = BattleState(fast_path=False)
    for player in battle.players:
        player.hand = [character, "Archer", "Skeletons", "Zap"]
        player.deck = [character, "Archer", "Skeletons", "Zap"]
        player.cycle_queue = deque(["Knight"])
        player.elixir = 10.0
    return battle


def _two_character_actions() -> tuple[int, int]:
    space = DiscreteTileActionSpace(canonical_perspective=True)
    return (
        space.encode_action(0, 9, 10, 0),
        space.encode_action(0, 9, 20, 1),
    )


def _apply_oracle_immediately(
    battle: BattleState,
    order: list[int],
    actions: tuple[int, int],
) -> None:
    space = DiscreteTileActionSpace(canonical_perspective=True)
    for player_id in order:
        before = len(battle._pending_spell_casts)
        assert space.apply_action(battle, player_id, actions[player_id])
        if len(battle._pending_spell_casts) == before:
            continue
        cast = battle._pending_spell_casts.pop()
        SPELL_REGISTRY[cast.spell_name].cast(
            battle,
            cast.player_id,
            cast.position,
        )


def _assert_exact(oracle: BattleState, engine: TensorResidentEngine) -> None:
    core = engine.runtime.battle
    active = engine.runtime.entity_pool.active[0]
    ids = core.entity_id[0, active].tolist()
    assert ids == list(oracle.entities)
    assert engine.runtime.entity_pool.next_entity_id.item() == oracle.next_entity_id
    for slot, entity_id in enumerate(ids):
        entity = oracle.entities[entity_id]
        assert core.entity_player[0, slot].item() == entity.player_id
        assert core.entity_hp[0, slot].item() == entity.hitpoints
        assert core.entity_x_units[0, slot].item() == round(entity.position.x * 1_000)
        assert core.entity_y_units[0, slot].item() == round(entity.position.y * 1_000)
        assert engine.runtime.status.stun_timer[0, slot].item() == entity.stun_timer
    for player_id, player in enumerate(oracle.players):
        expected_hand = [core.card_to_id.get(card or "", 0) for card in player.hand]
        expected_cycle = [core.card_to_id[card] for card in player.cycle_queue]
        assert core.hand[0, player_id].tolist() == expected_hand
        assert core.cycle_queue_length[0, player_id].item() == len(expected_cycle)
        assert core.cycle_queue[0, player_id, : len(expected_cycle)].tolist() == (
            expected_cycle
        )
        assert core.elixir[0, player_id].item() == player.elixir
    assert core.rng.python_state(0) == oracle.rng.getstate()


@pytest.mark.parametrize("character", ("Knight", "Cannon"))
@pytest.mark.parametrize("order", ((0, 1), (1, 0)))
def test_mixed_spell_character_actions_match_python_in_shared_order(
    tensor_device: str,
    character: str,
    order: tuple[int, int],
) -> None:
    battle = _battle(character)
    oracle = copy.deepcopy(battle)
    engine, router = _router(battle, tensor_device)
    actions = _actions()
    _apply_oracle_immediately(oracle, list(order), actions)

    result = router.apply(
        torch.tensor([actions], device=engine.device),
        player_order=torch.tensor([order], device=engine.device),
    )

    assert result.committed.tolist() == [True]
    assert result.action_success.tolist() == [[True, True]]
    assert result.player_order[0].tolist() == list(order)
    _assert_exact(oracle, engine)
    spawned = oracle.entities[max(oracle.entities)]
    assert isinstance(spawned, Building if character == "Cannon" else Troop)
    event_count = int(engine.runtime.events.count[0].item())
    opcodes = engine.runtime.events.opcode[0, :event_count].tolist()
    if order == (0, 1):
        assert opcodes == [
            int(RuntimeEventOpcode.SPAWN),
            int(RuntimeEventOpcode.DAMAGE),
            int(RuntimeEventOpcode.STATUS),
        ]
    else:
        assert opcodes == [int(RuntimeEventOpcode.SPAWN)]


def test_router_consumes_exactly_one_default_shuffle_draw() -> None:
    battle = _battle("Knight")
    oracle = copy.deepcopy(battle)
    engine, router = _router(battle, "cpu")
    actions = _actions()
    order = [0, 1]
    oracle.rng.shuffle(order)
    _apply_oracle_immediately(oracle, order, actions)

    result = router.apply(torch.tensor([actions]))

    assert result.player_order[0].tolist() == order
    assert result.committed.tolist() == [True]
    _assert_exact(oracle, engine)


def test_unsupported_second_spell_rolls_back_first_character_atomically() -> None:
    battle = _battle("Knight", spell="Freeze")
    engine, router = _router(battle, "cpu")
    actions = _actions()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_hand = engine.runtime.battle.hand.clone()
    before_cycle = engine.runtime.battle.cycle_queue.clone()
    before_elixir = engine.runtime.battle.elixir.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)
    before_events = engine.runtime.events.count.clone()

    result = router.apply(
        torch.tensor([actions]),
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [False]
    assert result.action_success.tolist() == [[False, False]]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.battle.cycle_queue, before_cycle)
    assert torch.equal(engine.runtime.battle.elixir, before_elixir)
    assert engine.runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(engine.runtime.events.count, before_events)


def test_second_spell_capacity_failure_rolls_back_materialized_first_troop() -> None:
    battle = _battle("Knight", spell="GoblinBarrel")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=1, event_capacity=256
    )
    router = TensorResidentActionRouter(
        engine.runtime,
        engine.objects,
        engine.projectile_bridge,
        engine.deployment,
        engine.spell_ingress,
    )
    actions = _actions()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_active = engine.runtime.entity_pool.active.clone()
    before_next = engine.runtime.entity_pool.next_entity_id.clone()
    before_hand = engine.runtime.battle.hand.clone()
    before_events = engine.runtime.events.count.clone()

    result = router.apply(
        torch.tensor([actions]),
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.entity_pool.active, before_active)
    assert torch.equal(engine.runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.events.count, before_events)


@pytest.mark.parametrize("character", ("Knight", "Cannon"))
@pytest.mark.parametrize("capacity", ("entity", "event"))
def test_second_character_capacity_failure_rolls_back_rank0_materialization(
    character: str,
    capacity: str,
) -> None:
    battle = _two_character_battle(character)
    engine = TensorResidentEngine.from_battles(
        [battle],
        max_entities=7 if capacity == "entity" else 8,
        max_objects=1,
        event_capacity=8 if capacity == "entity" else 1,
    )
    router = TensorResidentActionRouter(
        engine.runtime,
        engine.objects,
        engine.projectile_bridge,
        engine.deployment,
        engine.spell_ingress,
    )
    actions = _two_character_actions()
    before_ids = engine.runtime.battle.entity_id.clone()
    before_active = engine.runtime.entity_pool.active.clone()
    before_next = engine.runtime.entity_pool.next_entity_id.clone()
    before_hand = engine.runtime.battle.hand.clone()
    before_events = engine.runtime.events.count.clone()

    result = router.apply(
        torch.tensor([actions]),
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [False]
    # Rank 0 genuinely materialized in the retained scratch transaction before
    # rank 1 exhausted the selected capacity plane.
    assert router._workspace.runtime.entity_pool.next_entity_id.item() == (
        before_next.item() + 1
    )
    assert router._workspace.runtime.events.count.tolist() == [1]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.entity_pool.active, before_active)
    assert torch.equal(engine.runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.events.count, before_events)


def test_router_source_is_data_driven_without_card_name_dispatch() -> None:
    source = inspect.getsource(TensorResidentActionRouter)
    for card_name in (
        "Zap",
        "Knight",
        "Cannon",
        "Fireball",
        "GoblinBarrel",
    ):
        assert card_name not in source
