import numpy as np
import pytest
import torch

from scripts.screen_hog26_training_family_margin import mix_representative_weights


def inputs():
    weights = torch.tensor([1., 1., 2., 2., 0., 0., 0., 0.])
    phases = np.array([0, 0, 1, 1, 0, 0, 1, 1])
    offsets = np.array([0, 4, 8])
    fit = np.array([0])
    reps = np.array([1, 3, 5, 7])
    return weights, phases, offsets, fit, reps


def test_preserves_game_phase_mass_and_excluded_rows():
    args = inputs()
    result = mix_representative_weights(*args, 0.5)
    torch.testing.assert_close(result, torch.tensor([.5, 1.5, 1., 3., 0., 0., 0., 0.]))
    assert result[:2].sum() == args[0][:2].sum()
    assert result[2:4].sum() == args[0][2:4].sum()


def test_excluded_representative_choices_cannot_affect_weights():
    weights, phases, offsets, fit, reps = inputs()
    expected = mix_representative_weights(weights, phases, offsets, fit, reps, .5)
    reps[2:] = [4, 6]
    actual = mix_representative_weights(weights, phases, offsets, fit, reps, .5)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)


def test_zero_mass_is_exact_original_control():
    args = inputs()
    torch.testing.assert_close(mix_representative_weights(*args, 0), args[0], rtol=0, atol=0)


@pytest.mark.parametrize("mass", [-.1, 1.1, float("nan")])
def test_invalid_mass_rejected(mass):
    with pytest.raises(ValueError, match="mass"):
        mix_representative_weights(*inputs(), mass)
