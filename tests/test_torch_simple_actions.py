from __future__ import annotations

import inspect

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_TILES
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_actions import FastActionKernel, FastActionState
from clasher.torch_sim.simple_catalog import FastCardCatalog


CARD_NAMES = (
    "Knight",
    "Archers",
    "Giant",
    "Minions",
    "Musketeer",
    "BabyDragon",
    "Balloon",
    "Wizard",
)


def _fixture(device: str = "cpu") -> tuple[FastActionKernel, FastActionState, dict[str, int]]:
    battle = BattleState()
    full = TensorCardCatalog.compile(battle.card_loader, CARD_NAMES, device=device)
    catalog = FastCardCatalog.from_tensor_catalog(full)
    ids = {name: full.name_to_id[name] for name in CARD_NAMES}
    ordered = torch.tensor(
        [[[[ids[name] for name in CARD_NAMES]] * 2]],
        dtype=torch.int64,
        device=device,
    ).reshape(1, 2, 8)
    return FastActionKernel(catalog), FastActionState.from_decks(ordered), ids


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_fast_action_mask_is_affordability_and_identity_driven(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    kernel, state, _ = _fixture(device)
    state.elixir[0] = 0.0
    mask = kernel.legal_action_mask(state)
    assert mask.shape == (1, 2, NO_OP_ACTION + 2)
    assert not mask[:, :, :NO_OP_ACTION].any()
    assert mask[:, :, NO_OP_ACTION].all()
    assert not mask[:, :, ABILITY_ACTION].any()

    state.elixir[0] = 10.0
    state.hand_ids[0, 0, 0] = 0
    mask = kernel.legal_action_mask(state)
    assert not mask[0, 0, :NUM_TILES].any()
    assert mask[0, 0, NUM_TILES:NO_OP_ACTION].any()
    # Tower and blocked-board positions fail closed even with sufficient elixir.
    tower_tile = 6 * BOARD_WIDTH + 3
    blocked_tile = 14 * BOARD_WIDTH
    assert not mask[0, 0, NUM_TILES + tower_tile]
    assert not mask[0, 0, NUM_TILES + blocked_tile]


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_fast_ingress_rotates_next_spends_and_emits_player_ordered_requests(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    kernel, state, ids = _fixture(device)
    initial_hand = state.hand_ids.clone()
    initial_next = state.own_next.clone()
    initial_elixir = state.elixir.clone()
    tile = 10 * BOARD_WIDTH + 9
    actions = torch.tensor(
        [[tile, 2 * NUM_TILES + tile]], dtype=torch.int64, device=device
    )
    result = kernel.ingress(state, actions)

    assert result.deployment_accepted.tolist() == [[True, True]]
    assert [request.owner.tolist() for request in result.requests] == [[0], [1]]
    assert [request.valid.tolist() for request in result.requests] == [[True], [True]]
    assert result.requests[0].card_id.tolist() == [ids["Knight"]]
    assert result.requests[1].card_id.tolist() == [ids["Giant"]]
    assert state.hand_ids[0, 0, 0] == initial_next[0, 0]
    assert state.hand_ids[0, 1, 2] == initial_next[0, 1]
    assert state.cycle_head.tolist() == [[1, 1]]
    assert state.cycle_ids[0, 0, 0] == initial_hand[0, 0, 0]
    assert state.cycle_ids[0, 1, 0] == initial_hand[0, 1, 2]
    expected = initial_elixir - torch.tensor(
        [[3.0, 5.0]], dtype=torch.float32, device=device
    )
    torch.testing.assert_close(state.elixir, expected)

    # The next play deterministically consumes the next ring entry.
    next_before = state.own_next.clone()
    state.elixir[0, 0] = 10.0
    second = kernel.ingress(
        state,
        torch.tensor([[tile, NO_OP_ACTION]], dtype=torch.int64, device=device),
    )
    assert second.deployment_accepted.tolist() == [[True, False]]
    assert state.hand_ids[0, 0, 0] == next_before[0, 0]
    assert state.cycle_head.tolist() == [[2, 1]]


def test_fast_decode_mirrors_canonical_actor_one_and_rejects_invalid_input() -> None:
    kernel, _, _ = _fixture()
    tile = 7 * BOARD_WIDTH + 2
    decoded = kernel.decode(torch.tensor([[tile, tile,]]))
    assert decoded.slot.tolist() == [[0, 0]]
    assert decoded.tile.tolist() == [[tile, tile]]
    assert decoded.world_x_units.tolist() == [[2_500, 15_500]]
    assert decoded.world_y_units.tolist() == [[7_500, 24_500]]

    invalid = kernel.decode(torch.tensor([[-1, NO_OP_ACTION + 9]]))
    assert invalid.valid_input.tolist() == [[False, False]]
    assert invalid.is_no_op.tolist() == [[True, True]]
    assert invalid.slot.tolist() == [[-1, -1]]


def test_fast_fractional_elixir_regeneration_clamps_and_respects_live_mask() -> None:
    kernel, state, _ = _fixture()
    state.elixir[0] = torch.tensor([9.99, 3.0])
    kernel.regenerate_elixir_(
        state,
        ticks=2,
        multiplier=torch.tensor([[1.0, 2.0]]),
        live=torch.tensor([[True, False]]),
    )
    assert state.elixir[0, 0] == 10.0
    assert state.elixir[0, 1] == 3.0


def test_fast_action_hot_path_has_no_rng_host_sync_or_dynamic_compaction() -> None:
    source = inspect.getsource(FastActionKernel.decode)
    source += inspect.getsource(FastActionKernel.legal_action_mask)
    source += inspect.getsource(FastActionKernel.ingress)
    source += inspect.getsource(FastActionKernel.regenerate_elixir_)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "random.",
        "torch.rand",
    ):
        assert forbidden not in source
