import random

import numpy as np
import pytest
import torch

from scripts.hog26_scalar_public_random_opponent import ScalarPublicRandomOpponent


def test_exact_uniform_reference_including_noop_and_ability():
    sampler = ScalarPublicRandomOpponent(seed=1279052, opponent_seat=1)
    oracle = random.Random(1279052)
    allowed = [0, 400, 2304, 2305]
    masks = np.zeros((2, 2306), dtype=bool)
    masks[1, allowed] = True
    before = masks.copy()
    actual = [sampler.sample(masks) for _ in range(100)]
    expected = [allowed[oracle.randrange(len(allowed))] for _ in range(100)]
    assert actual == expected and set(actual) == set(allowed)
    assert sampler.getstate() == oracle.getstate()
    assert np.array_equal(masks, before)


def test_other_seat_and_other_rng_work_do_not_change_opponent_stream():
    a = ScalarPublicRandomOpponent(seed=57, opponent_seat=0)
    b = ScalarPublicRandomOpponent(seed=57, opponent_seat=1)
    masks_a = np.zeros((2, 2306), dtype=bool)
    masks_b = np.ones((2, 2306), dtype=bool)
    masks_a[0, [2, 2304]] = True
    masks_b[1] = masks_a[0]
    unrelated = random.Random(901)
    for _ in range(80):
        unrelated.shuffle(list(range(20)))
        assert a.sample(masks_a) == b.sample(masks_b)
        assert a.getstate() == b.getstate()
    # Empty learner row in a and fully legal learner row in b are irrelevant.


def test_no_global_python_numpy_or_torch_rng_changes():
    sampler = ScalarPublicRandomOpponent(seed=57, opponent_seat=0)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    torch_state = torch.random.get_rng_state().clone()
    masks = torch.ones((2, 2306), dtype=torch.bool)
    for _ in range(20):
        sampler.sample(masks)
    assert random.getstate() == python_state
    numpy_after = np.random.get_state()
    assert numpy_after[0] == numpy_state[0]
    assert np.array_equal(numpy_after[1], numpy_state[1])
    assert numpy_after[2:] == numpy_state[2:]
    assert torch.equal(torch.random.get_rng_state(), torch_state)


@pytest.mark.parametrize(
    "invalid",
    [
        np.zeros((2, 2306), dtype=bool),
        np.ones((1, 2306), dtype=bool),
        np.ones((2, 2306), dtype=np.float32),
    ],
)
def test_invalid_or_empty_opponent_rejected_before_rng_change(invalid):
    sampler = ScalarPublicRandomOpponent(seed=57, opponent_seat=1)
    before = sampler.getstate()
    with pytest.raises(ValueError):
        sampler.sample(invalid)
    assert sampler.getstate() == before


def test_state_restore_replays_and_invalid_restore_is_atomic():
    sampler = ScalarPublicRandomOpponent(seed=57, opponent_seat=1)
    masks = np.ones((2, 2306), dtype=bool)
    sampler.sample(masks)
    saved = sampler.getstate()
    expected = [sampler.sample(masks) for _ in range(40)]
    sampler.setstate(saved)
    assert [sampler.sample(masks) for _ in range(40)] == expected
    before = sampler.getstate()
    with pytest.raises((TypeError, ValueError)):
        sampler.setstate((3, (), None))
    assert sampler.getstate() == before


@pytest.mark.parametrize(
    "seed,exception", [(True, TypeError), (1.5, TypeError), (-1, ValueError)]
)
def test_seed_must_be_nonnegative_integer(seed, exception):
    with pytest.raises(exception):
        ScalarPublicRandomOpponent(seed=seed, opponent_seat=1)
