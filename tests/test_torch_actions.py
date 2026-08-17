from __future__ import annotations

import copy
import random
from collections import deque

import numpy as np
import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import (
    ABILITY_ACTION,
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
)
from clasher.torch_sim.catalog import TensorCardCatalog

ENABLED_CARDS = unique_cards_from_decks(load_deck_pool())


@pytest.fixture(scope="module")
def tensor_actions() -> tuple[TensorActionCatalog, TensorActionKernel]:
    battle = BattleState()
    cards = TensorCardCatalog.compile(battle.card_loader, ENABLED_CARDS)
    action_catalog = TensorActionCatalog.compile(cards)
    return action_catalog, TensorActionKernel(action_catalog)


def _set_hand(
    battle: BattleState,
    player_id: int,
    cards: list[str | None],
    *,
    elixir: float,
) -> None:
    player = battle.players[player_id]
    player.hand = cards
    player.elixir = elixir
    player.deck = [card for card in cards if card is not None]
    player.cycle_queue = deque(
        card for card in ENABLED_CARDS[:4] if card not in player.deck
    )


def _oracle_masks(battles: list[BattleState]) -> np.ndarray:
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    return np.stack(
        [
            np.stack(
                [
                    action_space.legal_action_mask(battle, player_id, fast_path=False)
                    for player_id in (0, 1)
                ]
            )
            for battle in battles
        ]
    )


def test_vector_decode_matches_oracle_for_both_perspectives(tensor_actions):
    _, kernel = tensor_actions
    oracle = DiscreteTileActionSpace(canonical_perspective=True)
    ids = torch.tensor(
        [
            [-1, 0],
            [oracle.encode_action(2, 3, 25, 1), NO_OP_ACTION],
            [ABILITY_ACTION, 10_000_000],
        ]
    )
    decoded = kernel.decode(ids)

    for batch in range(ids.shape[0]):
        for player in (0, 1):
            expected = oracle.decode_action(int(ids[batch, player]), player)
            assert bool(decoded.is_no_op[batch, player]) == expected.is_no_op
            assert bool(decoded.is_ability[batch, player]) == expected.is_ability
            if expected.position is None:
                assert int(decoded.slot[batch, player]) == -1
            else:
                assert int(decoded.slot[batch, player]) == expected.slot
                assert int(decoded.world_x_units[batch, player]) == round(
                    expected.position.x * 1000
                )
                assert int(decoded.world_y_units[batch, player]) == round(
                    expected.position.y * 1000
                )


def test_every_enabled_card_matches_oracle_empty_arena_both_players(tensor_actions):
    catalog, kernel = tensor_actions
    battles: list[BattleState] = []
    for offset in range(0, len(ENABLED_CARDS), 4):
        battle = BattleState()
        hand = ENABLED_CARDS[offset : offset + 4]
        hand += [None] * (4 - len(hand))
        _set_hand(battle, 0, hand, elixir=20.0)
        _set_hand(battle, 1, hand, elixir=20.0)
        battles.append(battle)

    state = TensorActionState.from_battles(battles, catalog)
    actual = kernel.legal_action_mask(state).cpu().numpy()
    np.testing.assert_array_equal(actual, _oracle_masks(battles))


def test_randomized_crowded_masks_match_oracle(tensor_actions):
    catalog, kernel = tensor_actions
    rng = random.Random(913_117)
    battles: list[BattleState] = []
    building_cards = ["Cannon", "Tesla", "BombTower", "GoblinCage", "Tombstone"]
    for _ in range(24):
        battle = BattleState()
        for player_id in (0, 1):
            hand = rng.sample(ENABLED_CARDS, 4)
            if rng.random() < 0.2:
                hand[rng.randrange(4)] = None
            _set_hand(battle, player_id, hand, elixir=rng.uniform(0.0, 10.0))
            if rng.random() < 0.35:
                battle.players[1 - player_id].left_tower_hp = 0.0
            if rng.random() < 0.35:
                battle.players[1 - player_id].right_tower_hp = 0.0

        for _ in range(rng.randrange(1, 5)):
            name = rng.choice(building_cards)
            stats = battle.card_loader.get_card(name)
            assert stats is not None
            x = rng.randrange(2, 16) + 0.5
            y = rng.choice((*range(7, 15), *range(17, 25))) + 0.5
            battle._spawn_troop(Position(x, y), rng.randrange(2), stats)
            entity = battle.entities[battle.next_entity_id - 1]
            entity.deploy_delay_remaining = 0.0
            entity.placement_pending = False
        battle._update_tower_hp()
        battles.append(battle)

    state = TensorActionState.from_battles(battles, catalog)
    actual = kernel.legal_action_mask(state).cpu().numpy()
    np.testing.assert_array_equal(actual, _oracle_masks(battles))


def test_deployment_payload_occupancy_matches_oracle(tensor_actions):
    catalog, kernel = tensor_actions
    battle = BattleState()
    _set_hand(battle, 0, ["Knight", "Cannon", "Fireball", "Miner"], elixir=10.0)
    _set_hand(battle, 1, ["Knight", "Cannon", "Fireball", "Miner"], elixir=10.0)
    balloon = battle.card_loader.get_card("Balloon")
    assert balloon is not None
    battle._spawn_troop(Position(9.5, 10.5), 1, balloon)
    payload = battle.entities[battle.next_entity_id - 1]
    payload.deploy_delay_remaining = 0.0
    payload.placement_pending = False
    payload.take_damage(payload.hitpoints)

    state = TensorActionState.from_battles([battle], catalog)
    actual = kernel.legal_action_mask(state).cpu().numpy()
    np.testing.assert_array_equal(actual, _oracle_masks([battle]))


def test_destroyed_towers_expand_deploy_zone_exactly(tensor_actions):
    catalog, kernel = tensor_actions
    battles: list[BattleState] = []
    for destroyed_player, destroyed_slot in (
        (0, "left"),
        (0, "right"),
        (1, "left"),
        (1, "right"),
    ):
        battle = BattleState()
        tower = next(
            entity
            for entity in battle.entities.values()
            if entity.player_id == destroyed_player
            and getattr(entity, "_crown_tower_slot", None) == destroyed_slot
        )
        tower.take_damage(tower.hitpoints)
        battle._update_tower_hp()
        for player_id in (0, 1):
            _set_hand(
                battle,
                player_id,
                ["Knight", "Cannon", "Log", "Miner"],
                elixir=10.0,
            )
        battles.append(battle)

    state = TensorActionState.from_battles(battles, catalog)
    actual = kernel.legal_action_mask(state).cpu().numpy()
    np.testing.assert_array_equal(actual, _oracle_masks(battles))


def test_elixir_empty_hand_dead_player_and_fail_closed_unknown_card(tensor_actions):
    catalog, kernel = tensor_actions
    battle = BattleState()
    _set_hand(battle, 0, ["Golem", None, "Knight", "Zap"], elixir=2.0)
    _set_hand(battle, 1, ["Knight", "Zap", "Cannon", "Fireball"], elixir=10.0)
    battle.players[1].king_tower_hp = 0.0

    state = TensorActionState.from_battles([battle], catalog)
    np.testing.assert_array_equal(
        kernel.legal_action_mask(state).cpu().numpy(), _oracle_masks([battle])
    )

    state.supported[0, 0] = False
    mask = kernel.legal_action_mask(state)
    assert mask[0, 0, NO_OP_ACTION]
    assert not mask[0, 0, :NO_OP_ACTION].any()
    assert not mask[0, 0, ABILITY_ACTION]


def test_ingress_updates_card_cycle_and_emits_stable_commands(tensor_actions):
    catalog, kernel = tensor_actions
    battles = [BattleState(), BattleState()]
    for battle in battles:
        for player_id in (0, 1):
            _set_hand(
                battle,
                player_id,
                ["Knight", "Fireball", "Cannon", "Zap"],
                elixir=10.0,
            )
    state = TensorActionState.from_battles(battles, catalog)
    oracle = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [oracle.encode_action(0, 9, 10, 0), NO_OP_ACTION],
            [oracle.encode_action(1, 9, 20, 0), oracle.encode_action(2, 8, 21, 1)],
        ]
    )
    result = kernel.ingress(state, actions)

    assert result.accepted.tolist() == [[True, True], [True, True]]
    assert result.commands.battle_index.tolist() == [0, 1, 1]
    assert result.commands.player_id.tolist() == [0, 0, 1]
    assert result.commands.sequence.tolist() == [0, 1, 2]
    assert result.commands.card_id.tolist() == [
        catalog.cards.name_to_id["Knight"],
        catalog.cards.name_to_id["Fireball"],
        catalog.cards.name_to_id["Cannon"],
    ]
    assert result.elixir.tolist() == [[7.0, 10.0], [6.0, 7.0]]
    assert int(result.hand_ids[0, 0, 0]) == 0
    assert (
        int(result.cycle_ids[0, 0, state.cycle_length[0, 0]])
        == catalog.cards.name_to_id["Knight"]
    )


def test_ingress_hand_cycle_elixir_transition_matches_player_oracle(tensor_actions):
    catalog, kernel = tensor_actions
    battle = BattleState()
    _set_hand(battle, 0, ["Knight", "Knight", "Fireball", "Cannon"], elixir=10.0)
    _set_hand(battle, 1, ["Zap", "Cannon", "Fireball", "Knight"], elixir=10.0)
    state = TensorActionState.from_battles([battle], catalog)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    action = action_space.encode_action(1, 9, 10, 0)
    result = kernel.ingress(state, torch.tensor([[action, NO_OP_ACTION]]))

    oracle = copy.deepcopy(battle.players[0])
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    assert oracle.play_card("Knight", stats)
    expected_hand = [
        0 if name is None else catalog.cards.name_to_id[name] for name in oracle.hand
    ]
    expected_cycle = [catalog.cards.name_to_id[name] for name in oracle.cycle_queue]
    assert result.hand_ids[0, 0].tolist() == expected_hand
    assert result.cycle_ids[0, 0, : len(expected_cycle)].tolist() == expected_cycle
    assert int(result.cycle_length[0, 0]) == len(expected_cycle)
    assert float(result.elixir[0, 0]) == oracle.elixir


def test_ingress_transition_matches_player_oracle_for_enabled_manifest(tensor_actions):
    catalog, kernel = tensor_actions
    for card_name in ENABLED_CARDS:
        battle = BattleState()
        _set_hand(battle, 0, [card_name, "Knight", "Zap", "Cannon"], elixir=20.0)
        _set_hand(battle, 1, ["Knight", "Zap", "Cannon", "Fireball"], elixir=20.0)
        state = TensorActionState.from_battles([battle], catalog)
        mask = kernel.legal_action_mask(state)
        legal = torch.nonzero(mask[0, 0, :NO_OP_ACTION], as_tuple=False)
        assert legal.numel(), card_name
        result = kernel.ingress(
            state,
            torch.tensor([[int(legal[0, 0]), NO_OP_ACTION]]),
            legal_mask=mask,
        )

        oracle = copy.deepcopy(battle.players[0])
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        assert oracle.play_card(card_name, stats)
        expected_hand = [
            0 if name is None else catalog.cards.name_to_id[name]
            for name in oracle.hand
        ]
        expected_cycle = [catalog.cards.name_to_id[name] for name in oracle.cycle_queue]
        assert result.hand_ids[0, 0].tolist() == expected_hand
        assert result.cycle_ids[0, 0, : len(expected_cycle)].tolist() == expected_cycle
        assert int(result.cycle_length[0, 0]) == len(expected_cycle)
        assert float(result.elixir[0, 0]) == oracle.elixir


def test_ingress_rejects_malformed_and_illegal_without_mutation(tensor_actions):
    catalog, kernel = tensor_actions
    battle = BattleState()
    _set_hand(battle, 0, ["Golem", "Knight", "Zap", "Cannon"], elixir=0.0)
    _set_hand(battle, 1, ["Knight", "Zap", "Cannon", "Fireball"], elixir=10.0)
    state = TensorActionState.from_battles([battle], catalog)
    before_hand = state.hand_ids.clone()
    before_cycle = state.cycle_ids.clone()
    before_elixir = state.elixir.clone()
    result = kernel.ingress(state, torch.tensor([[-1, NO_OP_ACTION]]))

    assert result.accepted.tolist() == [[False, True]]
    assert torch.equal(result.hand_ids, before_hand)
    assert torch.equal(result.cycle_ids, before_cycle)
    assert torch.equal(result.elixir, before_elixir)


def test_tensor_projection_does_not_mutate_battle(tensor_actions):
    catalog, _ = tensor_actions
    battle = BattleState()
    before = copy.deepcopy(battle)
    TensorActionState.from_battles([battle], catalog)
    assert battle.players == before.players
    assert tuple(battle.entities) == tuple(before.entities)
