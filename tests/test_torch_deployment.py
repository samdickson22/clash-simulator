from __future__ import annotations

import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import (
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
)
from clasher.torch_sim.catalog import MECHANIC_OPCODE, CardKindOpcode, TensorCardCatalog
from clasher.torch_sim.deployment import (
    TensorCommandMaterializer,
    TensorDeploymentCatalog,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime

ENABLED_CARDS = unique_cards_from_decks(load_deck_pool())


@pytest.fixture(scope="module")
def deployment_stack() -> tuple[
    TensorCardCatalog,
    TensorActionCatalog,
    TensorActionKernel,
    TensorDeploymentCatalog,
    TensorCommandMaterializer,
]:
    battle = BattleState()
    cards = TensorCardCatalog.compile(battle.card_loader, ENABLED_CARDS)
    actions = TensorActionCatalog.compile(cards)
    deployment = TensorDeploymentCatalog.compile(battle.card_loader, cards)
    return (
        cards,
        actions,
        TensorActionKernel(actions),
        deployment,
        TensorCommandMaterializer(deployment),
    )


def _set_hand(battle: BattleState, player_id: int, first: str) -> None:
    fillers = [name for name in ("Knight", "Zap", "Cannon") if name != first]
    hand = [first, *fillers]
    while len(hand) < 4:
        hand.append("Fireball")
    player = battle.players[player_id]
    player.hand = hand[:4]
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 20.0


def _first_slot_action(
    kernel: TensorActionKernel,
    state: TensorActionState,
    batch_index: int,
    player_id: int,
) -> int:
    mask = kernel.legal_action_mask(state)
    legal = torch.nonzero(mask[batch_index, player_id, : 18 * 32], as_tuple=False)
    assert legal.numel()
    action = int(legal[0, 0])
    assert action // (18 * 32) == 0
    return action


def _oracle_ingress(
    battles: list[BattleState], actions: torch.Tensor
) -> list[list[int]]:
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    orders: list[list[int]] = []
    for battle, row in zip(battles, actions):
        order = [0, 1]
        battle.rng.shuffle(order)
        for player_id in order:
            assert action_space.apply_action(battle, player_id, int(row[player_id]))
        orders.append(order)
    return orders


def _assert_runtime_representation_exact(
    actual: TensorBattleRuntime,
    battles: list[BattleState],
    materializer: TensorCommandMaterializer,
) -> None:
    expected = TensorBattleRuntime.from_battles(
        battles,
        catalog=actual.catalog,
        max_entities=actual.max_entities,
        max_cards=actual.battle.cycle_queue.shape[2],
        event_capacity=actual.events.capacity,
    )
    materializer.prepare_runtime(expected)
    assert actual.battle.card_names == expected.battle.card_names
    for state in fields(actual.battle):
        if state.name in {"device", "rng", "card_names", "card_to_id"}:
            continue
        left = getattr(actual.battle, state.name)
        right = getattr(expected.battle, state.name)
        assert torch.equal(left, right), state.name
    assert [
        actual.battle.rng.python_state(row) for row in range(actual.batch_size)
    ] == [battle.rng.getstate() for battle in battles]
    assert torch.equal(actual.entity_pool.active, expected.entity_pool.active)
    assert torch.equal(
        actual.entity_pool.next_entity_id, expected.entity_pool.next_entity_id
    )
    for state in fields(actual.status):
        assert torch.equal(
            getattr(actual.status, state.name), getattr(expected.status, state.name)
        ), state.name
    for state in fields(actual.phases):
        if state.name in {"dirty"}:
            continue
        assert torch.equal(
            getattr(actual.phases, state.name), getattr(expected.phases, state.name)
        ), state.name


def _plan(
    battles: list[BattleState],
    cards: TensorCardCatalog,
    action_catalog: TensorActionCatalog,
    kernel: TensorActionKernel,
    actions: torch.Tensor,
):
    state = TensorActionState.from_battles(battles, action_catalog)
    return kernel.ingress(state, actions)


def test_every_enabled_mechanic_free_supported_troop_and_building_is_exact(
    deployment_stack,
) -> None:
    cards, action_catalog, kernel, deployment, materializer = deployment_stack
    supported_names = [
        name
        for card_id, name in enumerate(cards.names[1:], start=1)
        if int(cards.kind[card_id])
        in {int(CardKindOpcode.TROOP), int(CardKindOpcode.BUILDING)}
        and int(cards.mechanic_count[card_id]) == 0
        and bool(deployment.supported_payload[card_id])
    ]
    assert {"Knight", "Archers", "Bats", "RoyalHogs", "Cannon", "Xbow"} <= set(
        supported_names
    )

    for card_index, card_name in enumerate(supported_names):
        source = BattleState(rng=random.Random(91_000 + card_index))
        _set_hand(source, 0, card_name)
        _set_hand(source, 1, "Knight")
        expected = source.clone()
        runtime = TensorBattleRuntime.from_battles(
            [source], catalog=cards, max_entities=64
        )
        action_state = TensorActionState.from_battles([source], action_catalog)
        action = _first_slot_action(kernel, action_state, 0, 0)
        actions = torch.tensor([[action, NO_OP_ACTION]])
        ingress = kernel.ingress(action_state, actions)

        expected_order = _oracle_ingress([expected], actions)
        result = materializer.materialize(runtime, ingress)

        assert result.battle_supported.tolist() == [True], card_name
        assert result.command_supported.tolist() == [True], card_name
        assert result.player_order.tolist() == expected_order, card_name
        _assert_runtime_representation_exact(runtime, [expected], materializer)


def test_twelve_battle_mixed_formations_preserve_rng_ids_slots_and_state(
    deployment_stack,
) -> None:
    cards, action_catalog, kernel, _, materializer = deployment_stack
    names = [
        "Knight",
        "Archers",
        "Bats",
        "Cannon",
        "RoyalHogs",
        "Skeletons",
        "Musketeer",
        "Xbow",
        "Minions",
        "SpearGoblins",
        "BabyDragon",
        "Valkyrie",
    ]
    sources = [BattleState(rng=random.Random(120_000 + row)) for row in range(12)]
    for row, battle in enumerate(sources):
        _set_hand(battle, 0, names[row])
        _set_hand(battle, 1, names[-1 - row])
    expected = [battle.clone() for battle in sources]
    runtime = TensorBattleRuntime.from_battles(
        sources, catalog=cards, max_entities=64, event_capacity=128
    )
    action_state = TensorActionState.from_battles(sources, action_catalog)
    actions = torch.tensor(
        [
            [
                _first_slot_action(kernel, action_state, row, player_id)
                for player_id in (0, 1)
            ]
            for row in range(12)
        ]
    )
    ingress = kernel.ingress(action_state, actions)

    expected_orders = _oracle_ingress(expected, actions)
    result = materializer.materialize(runtime, ingress)

    assert result.battle_supported.all()
    assert result.command_supported.all()
    assert result.player_order.tolist() == expected_orders
    assert runtime.events.count.tolist() == [
        int(runtime.entity_pool.next_entity_id[row] - 7) for row in range(12)
    ]
    _assert_runtime_representation_exact(runtime, expected, materializer)


def test_spell_and_mechanic_fallbacks_remain_atomic_beside_mixed_deployment(
    deployment_stack,
) -> None:
    cards, action_catalog, kernel, _, materializer = deployment_stack
    names = ["Fireball", "Golem", "GoblinGang"]
    sources = [BattleState(rng=random.Random(140_000 + row)) for row in range(3)]
    for battle, name in zip(sources, names):
        _set_hand(battle, 0, name)
        _set_hand(battle, 1, "Knight")
    runtime = TensorBattleRuntime.from_battles(sources, catalog=cards, max_entities=64)
    materializer.prepare_runtime(runtime)
    before_hand = runtime.battle.hand.clone()
    before_cycle = runtime.battle.cycle_queue.clone()
    before_elixir = runtime.battle.elixir.clone()
    before_ids = runtime.battle.entity_id.clone()
    action_state = TensorActionState.from_battles(sources, action_catalog)
    actions = torch.tensor(
        [
            [_first_slot_action(kernel, action_state, row, 0), NO_OP_ACTION]
            for row in range(3)
        ]
    )
    ingress = kernel.ingress(action_state, actions)

    result = materializer.materialize(runtime, ingress)

    assert result.unsupported_spell.tolist() == [True, False, False]
    assert result.unsupported_mechanic.tolist() == [False, True, False]
    assert result.unsupported_payload.tolist() == [True, False, False]
    assert result.command_supported.tolist() == [False, False, True]
    assert result.battle_supported.tolist() == [False, False, True]
    assert torch.equal(runtime.battle.hand[:2], before_hand[:2])
    assert torch.equal(runtime.battle.cycle_queue[:2], before_cycle[:2])
    assert torch.equal(runtime.battle.elixir[:2], before_elixir[:2])
    assert torch.equal(runtime.battle.entity_id[:2], before_ids[:2])
    assert not torch.equal(runtime.battle.hand[2], before_hand[2])
    assert not torch.equal(runtime.battle.entity_id[2], before_ids[2])


def test_mechanic_admission_is_opcode_driven_and_default_remains_fail_closed(
    deployment_stack,
) -> None:
    cards, action_catalog, kernel, deployment, default_materializer = deployment_stack
    sources = [
        BattleState(rng=random.Random(151_000)),
        BattleState(rng=random.Random(151_001)),
    ]
    _set_hand(sources[0], 0, "Bandit")
    _set_hand(sources[1], 0, "DarkPrince")
    for battle in sources:
        _set_hand(battle, 1, "Knight")
    state = TensorActionState.from_battles(sources, action_catalog)
    actions = torch.tensor(
        [[_first_slot_action(kernel, state, row, 0), NO_OP_ACTION] for row in range(2)]
    )
    ingress = kernel.ingress(state, actions)

    default_runtime = TensorBattleRuntime.from_battles(
        sources, catalog=cards, max_entities=32
    )
    default_result = default_materializer.materialize(
        default_runtime,
        ingress,
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )
    assert default_result.unsupported_mechanic.tolist() == [True, True]
    assert not default_result.battle_supported.any()

    admitted = TensorCommandMaterializer(
        deployment,
        admitted_mechanic_opcodes=(MECHANIC_OPCODE["BanditDash"],),
    )
    runtime = TensorBattleRuntime.from_battles(sources, catalog=cards, max_entities=32)
    result = admitted.materialize(
        runtime,
        ingress,
        player_order=torch.tensor([[0, 1], [0, 1]]),
    )

    assert result.unsupported_mechanic.tolist() == [False, True]
    assert result.battle_supported.tolist() == [True, False]
    assert (result.spawned_card_id[0] == cards.name_to_id["Bandit"]).sum() == 1
    assert runtime.entity_pool.next_entity_id.tolist() == [8, 7]


def test_supported_materialization_never_calls_python_deploy_card(
    deployment_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards, action_catalog, kernel, _, materializer = deployment_stack
    source = BattleState(rng=random.Random(155_001))
    _set_hand(source, 0, "Archers")
    _set_hand(source, 1, "Cannon")
    runtime = TensorBattleRuntime.from_battles([source], catalog=cards, max_entities=32)
    action_state = TensorActionState.from_battles([source], action_catalog)
    actions = torch.tensor(
        [
            [
                _first_slot_action(kernel, action_state, 0, 0),
                _first_slot_action(kernel, action_state, 0, 1),
            ]
        ]
    )
    ingress = kernel.ingress(action_state, actions)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Python deploy_card entered the supported tensor path")

    monkeypatch.setattr(BattleState, "deploy_card", forbidden)
    result = materializer.materialize(
        runtime,
        ingress,
        player_order=torch.tensor([[1, 0]]),
    )

    assert result.battle_supported.tolist() == [True]
    assert runtime.entity_pool.next_entity_id.tolist() == [10]
