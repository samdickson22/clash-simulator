from __future__ import annotations

import inspect
import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import (
    ABILITY_ACTION,
    NO_OP_ACTION,
    NUM_ACTIONS,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
    TensorIngressResult,
)
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.dense_actions import (
    TensorDenseActionIngress,
    TensorDenseIngressResult,
)

ENABLED_CARDS = unique_cards_from_decks(load_deck_pool())


@pytest.fixture(params=["cpu", "cuda"])
def action_stack(
    request: pytest.FixtureRequest,
) -> tuple[str, TensorActionCatalog, TensorActionKernel]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = BattleState()
    cards = TensorCardCatalog.compile(battle.card_loader, ENABLED_CARDS, device=device)
    catalog = TensorActionCatalog.compile(cards)
    return device, catalog, TensorActionKernel(catalog)


def _set_hand(
    battle: BattleState,
    player_id: int,
    cards: list[str | None],
    *,
    elixir: float = 20.0,
) -> None:
    player = battle.players[player_id]
    player.hand = cards
    player.deck = [card for card in cards if card is not None]
    player.cycle_queue = deque(
        card for card in ENABLED_CARDS[:6] if card not in player.deck
    )
    player.elixir = elixir


def _assert_selection_equal(actual: object, expected: object) -> None:
    for descriptor in fields(actual):  # type: ignore[arg-type]
        assert torch.equal(
            getattr(actual, descriptor.name), getattr(expected, descriptor.name)
        ), descriptor.name


def _assert_ingress_equal(
    dense: TensorDenseIngressResult,
    compact: TensorIngressResult,
) -> None:
    assert torch.equal(dense.accepted, compact.accepted)
    _assert_selection_equal(dense.selection, compact.selection)
    for name in ("hand_ids", "cycle_ids", "cycle_length", "elixir"):
        assert torch.equal(getattr(dense, name), getattr(compact, name)), name
    adapted = dense.to_tensor_ingress_diagnostic()
    for descriptor in fields(compact.commands):
        assert torch.equal(
            getattr(adapted.commands, descriptor.name),
            getattr(compact.commands, descriptor.name),
        ), descriptor.name


def _first_legal_actions(mask: torch.Tensor) -> torch.Tensor:
    placement = mask[:, :, :NO_OP_ACTION]
    first = placement.to(torch.int64).argmax(dim=2)
    has_placement = placement.any(dim=2)
    return torch.where(has_placement, first, torch.full_like(first, NO_OP_ACTION))


def test_dense_ingress_matches_every_enabled_card_and_compact_roundtrip(
    action_stack: tuple[str, TensorActionCatalog, TensorActionKernel],
) -> None:
    device, catalog, kernel = action_stack
    battles: list[BattleState] = []
    for card in ENABLED_CARDS:
        battle = BattleState()
        _set_hand(battle, 0, [card, "Knight", "Zap", "Cannon"])
        _set_hand(battle, 1, [card, "Knight", "Zap", "Cannon"])
        battles.append(battle)
    state = TensorActionState.from_battles(battles, catalog)
    dense_kernel = TensorDenseActionIngress(kernel, len(battles))
    mask = dense_kernel.legal_action_mask(state)
    actions = _first_legal_actions(mask)

    expected = kernel.ingress(state, actions, legal_mask=mask)
    actual = dense_kernel.ingress(state, actions, legal_mask=mask)
    recreated = dense_kernel.from_tensor_ingress_diagnostic(state, expected)

    _assert_ingress_equal(actual, expected)
    _assert_ingress_equal(recreated, expected)
    assert actual.commands.valid.shape == (len(battles), 2)
    assert actual.transitions.placement.all()
    assert actual.hand_ids.device.type == device


def test_dense_ingress_matches_randomized_crowded_and_rejected_masks(
    action_stack: tuple[str, TensorActionCatalog, TensorActionKernel],
) -> None:
    device, catalog, kernel = action_stack
    rng = random.Random(941_117)
    building_cards = ["Cannon", "Tesla", "BombTower", "GoblinCage", "Tombstone"]
    battles: list[BattleState] = []
    for row in range(12):
        battle = BattleState(rng=random.Random(942_000 + row))
        for player_id in (0, 1):
            _set_hand(
                battle,
                player_id,
                rng.sample(ENABLED_CARDS, 4),
                elixir=rng.uniform(0.0, 10.0),
            )
        for _ in range(rng.randrange(2, 6)):
            card = battle.card_loader.get_card(rng.choice(building_cards))
            assert card is not None
            battle._spawn_troop(
                Position(
                    rng.randrange(2, 16) + 0.5,
                    rng.choice((*range(7, 15), *range(17, 25))) + 0.5,
                ),
                rng.randrange(2),
                card,
            )
            entity = battle.entities[battle.next_entity_id - 1]
            entity.deploy_delay_remaining = 0.0
            entity.placement_pending = False
        battles.append(battle)

    state = TensorActionState.from_battles(battles, catalog)
    dense_kernel = TensorDenseActionIngress(kernel, len(battles))
    mask = dense_kernel.legal_action_mask(state)
    actions = _first_legal_actions(mask)
    actions[1::3, 0] = -1
    actions[2::3, 1] = NO_OP_ACTION

    expected = kernel.ingress(state, actions, legal_mask=mask)
    actual = dense_kernel.ingress(state, actions, legal_mask=mask)

    _assert_ingress_equal(actual, expected)
    assert actual.commands.valid.device.type == device


def test_dense_lanes_preserve_noop_ability_duplicate_hand_and_player_order(
    action_stack: tuple[str, TensorActionCatalog, TensorActionKernel],
) -> None:
    device, catalog, kernel = action_stack
    battles = [BattleState(), BattleState()]
    for battle in battles:
        _set_hand(battle, 0, ["Knight", "Knight", "Zap", "Cannon"])
        _set_hand(battle, 1, ["Zap", "Cannon", "Fireball", "Knight"])
    state = TensorActionState.from_battles(battles, catalog)
    state.ability_legal[1, 1] = True
    dense_kernel = TensorDenseActionIngress(kernel, 2)
    mask = dense_kernel.legal_action_mask(state)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [action_space.encode_action(1, 9, 10, 0), NO_OP_ACTION],
            [NO_OP_ACTION, ABILITY_ACTION],
        ],
        dtype=torch.int64,
        device=device,
    )

    expected = kernel.ingress(state, actions, legal_mask=mask)
    actual = dense_kernel.ingress(state, actions, legal_mask=mask)

    _assert_ingress_equal(actual, expected)
    knight_id = catalog.cards.name_to_id["Knight"]
    assert actual.transitions.cleared_hand_slot.tolist() == [[0, -1], [-1, -1]]
    assert actual.commands.valid.tolist() == [[True, False], [False, True]]
    assert actual.commands.card_id.tolist() == [[knight_id, 0], [0, 0]]
    assert actual.commands.is_ability.tolist() == [[False, False], [False, True]]
    ordered = actual.commands.ordered(
        torch.tensor([[1, 0], [0, 1]], dtype=torch.int64, device=device)
    )
    assert ordered.player_id.tolist() == [[1, 0], [0, 1]]
    assert ordered.valid.tolist() == [[False, True], [False, True]]


def test_dense_result_clone_fork_and_selective_reset_are_isolated(
    action_stack: tuple[str, TensorActionCatalog, TensorActionKernel],
) -> None:
    device, catalog, kernel = action_stack
    battles = [BattleState(), BattleState()]
    for battle in battles:
        _set_hand(battle, 0, ["Knight", "Zap", "Cannon", "Fireball"])
        _set_hand(battle, 1, ["Knight", "Zap", "Cannon", "Fireball"])
    state = TensorActionState.from_battles(battles, catalog)
    owner = TensorDenseActionIngress(kernel, 2)
    mask = owner.legal_action_mask(state)
    placements = _first_legal_actions(mask)
    noops = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
    first = owner.ingress(state, placements, legal_mask=mask)
    second = owner.ingress(state, noops, legal_mask=mask)

    cloned = first.clone()
    assert cloned.hand_ids.data_ptr() != first.hand_ids.data_ptr()
    forked = first.fork([1, 0, 1])
    assert torch.equal(forked.accepted[0], first.accepted[1])
    assert torch.equal(forked.accepted[2], first.accepted[1])
    assert forked.commands.battle_index.tolist() == [[0, 0], [1, 1], [2, 2]]
    assert forked.commands.player_id.tolist() == [[0, 1], [0, 1], [0, 1]]

    before_row_zero = cloned.hand_ids[0].clone()
    cloned.reset_rows_(second, torch.tensor([False, True], device=device))
    assert torch.equal(cloned.hand_ids[0], before_row_zero)
    assert torch.equal(cloned.hand_ids[1], second.hand_ids[1])
    assert torch.equal(cloned.commands.valid[1], second.commands.valid[1])
    assert cloned.commands.battle_index.tolist() == [[0, 0], [1, 1]]


def test_dense_production_ingress_has_no_dynamic_compaction_or_host_sync() -> None:
    source = inspect.getsource(TensorDenseActionIngress.ingress)
    assert "nonzero" not in source
    assert ".item(" not in source
    assert ".tolist(" not in source
    assert "TensorIngressResult" not in source
    assert NUM_ACTIONS > NO_OP_ACTION
