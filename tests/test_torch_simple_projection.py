from __future__ import annotations

import torch

from clasher.torch_sim.simple_projection import (
    SimpleProjectionInputs,
    SimpleTensorProjector,
)
from clasher.torch_sim.simple_state import FastGymState


def test_mirrored_actor_views_are_canonical_and_private_state_stays_critic_only() -> (
    None
):
    state = FastGymState.empty(1, max_entities=2)
    state.active[0, 0] = True
    state.stable_id[0, 0] = 999_999
    state.kind[0, 0] = 0
    state.owner[0, 0] = 0
    state.card_id[0, 0] = 2
    state.x_units[0, 0] = 4_500
    state.y_units[0, 0] = 8_000
    state.hp[0, 0] = 300.0
    state.max_hp[0, 0] = 600.0
    entity_lookup = torch.zeros((2, 8), dtype=torch.int64)
    entity_lookup[0, 2] = 102
    hand_lookup = torch.arange(8, dtype=torch.int64) + 200
    inputs = SimpleProjectionInputs(
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        hand_card_ids=torch.tensor([[[1, 2, 3, 4, 5], [6, 5, 4, 3, 2]]]),
        public_visibility=torch.ones((1, 2, 2), dtype=torch.bool),
        elixir=torch.tensor([[2.0, 9.0]]),
        max_elixir=torch.tensor([[10.0, 10.0]]),
        tower_hp=torch.tensor([[[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]]]),
        tower_max_hp=torch.full((1, 2, 3), 1_000.0),
        double_elixir=torch.tensor([False]),
        triple_elixir=torch.tensor([False]),
        overtime=torch.tensor([False]),
        ability_cooldown=torch.zeros((1, 2)),
        ability_duration=torch.zeros((1, 2)),
        refill_cooldown_ms=torch.tensor([[100.0, 700.0]]),
        max_ticks=100,
    )

    projected = SimpleTensorProjector(
        state, inputs, include_privileged_critic=True
    ).project(torch.ones((1, 2, 9), dtype=torch.bool))

    actor = projected.actor
    assert actor.entity_ids[0, :, 0].tolist() == [102, 102]
    assert 999_999 not in actor.entity_ids
    assert actor.entity_features[0, 0, 0, 0].item() == 0.25
    assert actor.entity_features[0, 0, 0, 1].item() == 0.25
    assert actor.entity_features[0, 1, 0, 0].item() == 0.75
    assert actor.entity_features[0, 1, 0, 1].item() == 0.75
    assert actor.entity_features[0, :, 0, 9].tolist() == [0.5, 0.5]
    assert actor.hand_ids[0, 0].tolist() == [201, 202, 203, 204, 205]
    assert actor.hand_ids[0, 1].tolist() == [206, 205, 204, 203, 202]
    torch.testing.assert_close(
        actor.global_features[0, :, 5], torch.tensor([0.2, 0.9])
    )
    torch.testing.assert_close(
        actor.global_features[0, 0, 8:14],
        torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
    )
    torch.testing.assert_close(
        actor.global_features[0, 1, 8:14],
        torch.tensor([0.5, 0.4, 0.6, 0.2, 0.1, 0.3]),
    )
    assert projected.critic is not None
    assert projected.critic.card_ids[0, 0, 5:].tolist() == actor.hand_ids[0, 1].tolist()
    torch.testing.assert_close(
        projected.critic.global_features[0, :, 18], torch.tensor([0.9, 0.2])
    )
