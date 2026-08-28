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
        entity_special=torch.tensor([[True, False]]),
        entity_invisible=torch.tensor([[True, False]]),
        entity_hidden=torch.tensor([[False, False]]),
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
    assert actor.entity_features[0, :, 0, 17].tolist() == [1.0, 1.0]
    assert actor.entity_features[0, :, 0, 18].tolist() == [1.0, 1.0]
    assert actor.entity_features[0, :, 0, 19].tolist() == [0.0, 0.0]
    assert actor.hand_ids[0, 0].tolist() == [201, 202, 203, 204, 205]
    assert actor.hand_ids[0, 1].tolist() == [206, 205, 204, 203, 202]
    torch.testing.assert_close(actor.global_features[0, :, 5], torch.tensor([0.2, 0.9]))
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


def test_python_canonical_entity_order_uses_distinct_crown_tower_tokens() -> None:
    state = FastGymState.empty(1, max_entities=8)
    state.active[:] = True
    state.stable_id[0] = torch.arange(1, 9)
    state.kind[0, :6] = 1
    state.kind[0, 6:] = 0
    state.owner[0] = torch.tensor([0, 0, 0, 1, 1, 1, 0, 1])
    state.card_id[0, 6:] = torch.tensor([2, 3])
    state.x_units[0] = torch.tensor(
        [3_500, 14_500, 9_000, 14_500, 3_500, 9_000, 8_000, 10_000]
    )
    state.y_units[0] = torch.tensor(
        [6_000, 6_000, 3_000, 26_000, 26_000, 29_000, 10_000, 22_000]
    )
    state.hp[:] = 100.0
    state.max_hp[:] = 100.0
    entity_lookup = torch.zeros((5, 8), dtype=torch.int64)
    entity_lookup[0, 2] = 100
    entity_lookup[0, 3] = 99
    inputs = SimpleProjectionInputs(
        entity_token_lookup=entity_lookup,
        hand_token_lookup=torch.arange(8, dtype=torch.int64) + 200,
        hand_card_ids=torch.tensor([[[1, 2, 3, 4, 5], [6, 5, 4, 3, 2]]]),
        public_visibility=torch.ones((1, 2, 8), dtype=torch.bool),
        elixir=torch.full((1, 2), 5.0),
        max_elixir=torch.full((1, 2), 10.0),
        tower_hp=torch.full((1, 2, 3), 100.0),
        tower_max_hp=torch.full((1, 2, 3), 100.0),
        double_elixir=torch.tensor([False]),
        triple_elixir=torch.tensor([False]),
        overtime=torch.tensor([False]),
        ability_cooldown=torch.zeros((1, 2)),
        ability_duration=torch.zeros((1, 2)),
        refill_cooldown_ms=torch.zeros((1, 2)),
        entity_special=torch.zeros((1, 8), dtype=torch.bool),
        entity_invisible=torch.zeros((1, 8), dtype=torch.bool),
        entity_hidden=torch.zeros((1, 8), dtype=torch.bool),
        max_ticks=100,
        tower_token_lookup=torch.tensor([351, 352]),
        canonical_entity_order=True,
    )

    actor = (
        SimpleTensorProjector(state, inputs)
        .project(torch.ones((1, 2, 9), dtype=torch.bool))
        .actor
    )

    assert actor.entity_ids[0, 0].tolist() == [
        100,
        99,
        351,
        352,
        352,
        351,
        352,
        352,
    ]
    assert actor.entity_ids[0, 1].tolist() == [
        99,
        100,
        351,
        352,
        352,
        351,
        352,
        352,
    ]
    # Viewer one mirrors the world, so its own princess towers retain
    # canonical left-to-right order (physical slots three then four).
    torch.testing.assert_close(
        actor.entity_features[0, 1, 3:5, 0],
        torch.tensor([3.5 / 18.0, 14.5 / 18.0]),
    )
