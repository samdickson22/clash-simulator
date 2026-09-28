from __future__ import annotations

from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import (
    FAST_WINNER_DRAW,
    FastMatchRules,
    FastTowerSpec,
)
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _tiebreak_runtime(device_name: str) -> SimpleGymRuntime:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    full = TensorCardCatalog.compile(
        BattleState().card_loader,
        ["Knight"],
        device=device,
    )
    catalog = FastCardCatalog.from_tensor_catalog(full)
    knight = full.name_to_id["Knight"]
    decks = torch.full((2, 2, 8), knight, dtype=torch.int64, device=device)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), knight, dtype=torch.int64, device=device),
        x_units=torch.tensor(
            [[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]], device=device
        ),
        y_units=torch.tensor(
            [[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]], device=device
        ),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]],
            device=device,
        ),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7_500, device=device),
        sight_range_units=torch.full((2, 3), 9_500, device=device),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    entity_lookup = torch.zeros((2, catalog.size), dtype=torch.int64, device=device)
    entity_lookup[0, knight] = 101
    entity_lookup[1, knight] = 201
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64, device=device) + 100
    return SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=5, tiebreak_ticks=10),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=12,
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_seedless_noop_match_replays_through_overtime_and_tiebreak(
    device_name: str,
) -> None:
    first = _tiebreak_runtime(device_name)
    replay = _tiebreak_runtime(device_name)
    noop = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=first.device)

    for tick in range(10):
        first_step = first.step_tick(noop)
        replay_step = replay.step_tick(noop)
        assert first_step.committed.tolist() == [True, True]
        assert first_step.native_ticks.tolist() == [1, 1]
        assert first_step.done.tolist() == replay_step.done.tolist()
        if tick == 4:
            assert first.outcomes.overtime.tolist() == [True, True]
            assert first_step.done.tolist() == [False, False]

    assert first_step.done.tolist() == [True, True]
    assert first_step.winner.tolist() == [FAST_WINNER_DRAW, FAST_WINNER_DRAW]
    assert first.state.tick.tolist() == [10, 10]
    for descriptor in fields(first.state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(first.state, descriptor.name),
                getattr(replay.state, descriptor.name),
            )
    torch.testing.assert_close(
        first_step.observation.actor.global_features,
        replay_step.observation.actor.global_features,
    )
