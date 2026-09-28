import pytest
import torch

from scripts.hog26_public_effect_probe import project_visible_effects


def test_hidden_events_are_masked_even_with_native_coordinates():
    positions = torch.tensor([[[1800, 3200], [12000, 20000]]])
    owners = torch.tensor([[0, 1]])
    kinds = torch.tensor([[1, 2]])
    visible = torch.tensor([[[True, False], [True, False]]])
    expected, mask = project_visible_effects(positions, owners, kinds, visible)
    assert not mask[..., 1].any()
    assert not expected[..., 1, :].any()
    positions[:, 1] = 5000
    actual, _ = project_visible_effects(positions, owners, kinds, visible)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)


def test_canonical_seats_and_explicit_appearance():
    features, mask = project_visible_effects(
        torch.tensor([[[1800, 6400]]]), torch.tensor([[0]]),
        torch.tensor([[1]]), torch.ones((1, 2, 1), dtype=torch.bool),
    )
    torch.testing.assert_close(features[0, 0, 0], torch.tensor([.1, .2, 1, 0, 1, 0]))
    torch.testing.assert_close(features[0, 1, 0], torch.tensor([.9, .8, 0, 1, 1, 0]))
    assert mask.all()


def test_unknown_appearance_does_not_become_an_actor_event():
    features, mask = project_visible_effects(
        torch.zeros((1, 1, 2)), torch.zeros((1, 1), dtype=torch.long),
        torch.zeros((1, 1), dtype=torch.long), torch.ones((1, 2, 1), dtype=torch.bool),
    )
    assert not features.any()
    assert not mask.any()


def test_visibility_is_required_and_validated():
    with pytest.raises(ValueError, match="visibility"):
        project_visible_effects(torch.zeros((1, 1, 2)), torch.zeros((1, 1)),
                               torch.ones((1, 1)), torch.ones((1, 2, 1)))
