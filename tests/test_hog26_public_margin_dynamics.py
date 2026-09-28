import numpy as np
import pytest

from scripts.hog26_public_margin_dynamics import overtime_damage_race


def test_damage_race_matches_constant_rate_tower_loss():
    public = np.zeros((2, 18), dtype=np.float32)
    public[:, 0] = [0.7, 0.8]
    public[:, 1] = [0.3, 0.2]
    public[:, 4] = 1
    public[:, 8:14] = 1
    public[:, 8] = [0.6, 0.5]
    public[:, 11] = [0.6, 0.4]
    delta, horizon = overtime_damage_race(public, np.array([0, 2]))
    assert delta[0] == 0
    assert horizon[1] == pytest.approx(0.2)
    assert delta[1] == pytest.approx((0.4 - 0.2) / 3)


def test_damage_race_is_prefix_causal_and_resets_per_game():
    rng = np.random.default_rng(4)
    public = np.zeros((50, 18), dtype=np.float32)
    public[:, 0] = np.linspace(0.67, 0.99, 50)
    public[:, 1] = 1 - public[:, 0]
    public[:, 4] = 1
    public[:, 8:14] = np.sort(rng.uniform(0, 1, (50, 6)), axis=0)[::-1]
    full, _ = overtime_damage_race(public, np.array([0, 50]))
    prefix, _ = overtime_damage_race(public[:30], np.array([0, 30]))
    np.testing.assert_array_equal(full[:30], prefix)
    reset, _ = overtime_damage_race(public, np.array([0, 30, 50]))
    assert reset[30] == 0
    public[:, 4] = 0
    inactive, _ = overtime_damage_race(public, np.array([0, 50]))
    np.testing.assert_array_equal(inactive, np.zeros(50))
