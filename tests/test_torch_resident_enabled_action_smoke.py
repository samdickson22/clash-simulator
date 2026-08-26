from __future__ import annotations

import pytest
import torch

from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_differential import _coverage_fixture
from clasher.torch_sim.resident_engine import TensorResidentEngine

DEPLOY_SLOT_ZERO = 12 * 18 + 14


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_every_enabled_card_preflights_and_commits_first_native_action(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    names = sorted(unique_cards_from_decks(load_deck_pool()))
    battles = [
        _coverage_fixture(name, 881_000 + row, episode_end_time=0.1)
        for row, name in enumerate(names)
    ]
    engine = TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=64,
        max_objects=64,
        event_capacity=512,
    )
    actions = torch.tensor(
        [[DEPLOY_SLOT_ZERO, NO_OP_ACTION] for _ in names],
        dtype=torch.int64,
        device=engine.device,
    )
    player_order = torch.tensor(
        [[0, 1] for _ in names],
        dtype=torch.int64,
        device=engine.device,
    )

    preflight = engine.preflight(actions)
    result = engine.step(actions, player_order=player_order)

    assert len(names) == 66
    assert preflight.supported.all(), {
        name: int(preflight.reason_code[row])
        for row, name in enumerate(names)
        if not bool(preflight.supported[row])
    }
    assert result.committed.all(), {
        name: engine.runtime.phases.supported[row].tolist()
        for row, name in enumerate(names)
        if not bool(result.committed[row])
    }
    assert result.action_router.action_success[:, 0].all()
