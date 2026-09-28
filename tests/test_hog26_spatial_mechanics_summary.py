from __future__ import annotations

from types import SimpleNamespace

import torch

from scripts.train_hog26_actor_outcome import (
    spatial_mechanics_summary,
    structured_actor_summary,
)


def fixture():
    model = SimpleNamespace(
        actor_encoder=SimpleNamespace(
            card_stat_features=torch.tensor([[0.0, 0.0], [1.0, 0.2], [0.1, 1.0]]),
            semantic_card_features=torch.tensor([[0.0], [0.2], [0.8]]),
        )
    )
    entity = torch.zeros(1, 1, 4, 24)
    entity[0, 0, 0, :2] = torch.tensor([0.2, 0.3])
    entity[0, 0, 1, :2] = torch.tensor([0.8, 0.7])
    entity[0, 0, :2, 3] = 1
    inputs = SimpleNamespace(
        entity_features=entity,
        entity_ids=torch.tensor([[[1, 2, 0, 0]]]),
        entity_mask=torch.tensor([[[True, True, False, False]]]),
        hand_ids=torch.tensor([[[1, 2, 1, 2, 1]]]),
        global_features=torch.zeros(1, 1, 18),
    )
    return model, inputs


def test_spatial_summary_resolves_position_stat_collision():
    model, inputs = fixture()
    changed = SimpleNamespace(**vars(inputs))
    changed.entity_features = inputs.entity_features.clone()
    changed.entity_features[0, 0, [0, 1], :2] = inputs.entity_features[0, 0, [1, 0], :2]
    torch.testing.assert_close(
        structured_actor_summary(model, inputs),
        structured_actor_summary(model, changed),
    )
    assert (
        spatial_mechanics_summary(model, inputs)
        - spatial_mechanics_summary(model, changed)
    ).abs().max() > 0.01


def test_joint_entity_permutation_is_invariant_and_public_globals_stay_last():
    model, inputs = fixture()
    changed = SimpleNamespace(**vars(inputs))
    order = torch.tensor([3, 1, 0, 2])
    for key in ["entity_features", "entity_ids", "entity_mask"]:
        setattr(changed, key, getattr(inputs, key)[:, :, order])
    result = spatial_mechanics_summary(model, inputs)
    torch.testing.assert_close(result, spatial_mechanics_summary(model, changed))
    torch.testing.assert_close(result[..., -18:], inputs.global_features)


def test_empty_sets_are_finite_and_duplicate_counts_remain_visible():
    model, inputs = fixture()
    empty = SimpleNamespace(**vars(inputs))
    empty.entity_mask = torch.zeros_like(inputs.entity_mask)
    assert torch.isfinite(spatial_mechanics_summary(model, empty)).all()
    doubled = SimpleNamespace(**vars(inputs))
    doubled.entity_features = inputs.entity_features[:, :, [0, 1, 0, 1]]
    doubled.entity_ids = inputs.entity_ids[:, :, [0, 1, 0, 1]]
    doubled.entity_mask = torch.ones_like(inputs.entity_mask)
    torch.testing.assert_close(
        structured_actor_summary(model, inputs),
        structured_actor_summary(model, doubled),
    )
    assert (
        spatial_mechanics_summary(model, inputs)
        - spatial_mechanics_summary(model, doubled)
    ).abs().max() > 0.1
