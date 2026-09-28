"""Versioned public metadata repairs without changing prior feature contracts."""

import numpy as np
import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

CARDS = ["Archers", "Musketeer", "Cannon", "Tesla", "IceSpirit", "Giant", "Mirror"]


def builder(version):
    return StructuredObservationBuilder(
        card_vocab=CARDS,
        card_semantics_version=version,
        max_entities=16,
        public_entity_levels=True,
    )


@pytest.mark.parametrize(
    "name,planes,mass",
    [
        ("Archers", [1, 1], 3),
        ("Musketeer", [1, 1], 5),
        ("Cannon", [1, 0], 13),
        ("Tesla", [1, 1], 8),
        ("IceSpirit", [1, 1], 1),
        ("Giant", [1, 0], 18),
    ],
)
@pytest.mark.parametrize("namespace", ["card_action", "unit"])
def test_compact_target_flags_and_character_mass(name, planes, mass, namespace):
    b = builder(4)
    # Body tokens use the builder's default namespace; actions have typed IDs.
    token = (
        b.token_id(name)
        if namespace == "unit"
        else b.token_id(name, namespace="card_action")
    )
    row = b.card_stat_features[token]
    np.testing.assert_array_equal(row[14:16], planes)
    assert row[-1] == pytest.approx(mass / 20)


def test_v4_preserves_layout_and_unrelated_features():
    old, new = builder(3), builder(4)
    assert old.token_names == new.token_names
    assert old.card_stat_features.shape == new.card_stat_features.shape
    keep = [
        i
        for i in range(old.card_stat_features.shape[1])
        if i not in (14, 15, old.card_stat_features.shape[1] - 1)
    ]
    np.testing.assert_array_equal(
        old.card_stat_features[:, keep], new.card_stat_features[:, keep]
    )
    # Prior contracts retain their original values for existing checkpoints.
    for version in (1, 3):
        b = builder(version)
        np.testing.assert_array_equal(
            b.card_stat_features[b.token_id("Tesla"), 14:16], [0, 0]
        )
    b = builder(2)
    assert b.card_stat_features[b.token_id("Cannon"), -1] == 0


def test_v4_reaches_level_aware_public_recurrent_model_without_training():
    b = builder(4)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=b.spec.num_tokens,
            max_entities=16,
            card_semantics_version=4,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=24,
            public_contract_version=3,
            public_token_names=b.token_names,
        ),
        b.card_stat_features,
    ).eval()
    sequence = PublicPolicySequence.from_observations(
        b, [b.build_actor(BattleState(), 0)]
    )
    mask = np.zeros((1, 2306), dtype=bool)
    mask[:, 2304] = True
    inputs = sequence.policy_inputs(
        action_mask=mask,
        previous_actions=np.zeros(1, dtype=np.int64),
        previous_rewards=np.zeros(1, dtype=np.float32),
        episode_starts=np.ones(1, dtype=bool),
    )
    with torch.no_grad():
        output = model(inputs)
    assert torch.isfinite(output.values).all()
    assert output.distribution().probs[..., 2304].item() == pytest.approx(1)
