import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.rl.train_selfplay import split_rollout_steps


def test_split_rollout_steps_even():
    assert split_rollout_steps(16, 4) == [4, 4, 4, 4]


def test_split_rollout_steps_with_remainder():
    assert split_rollout_steps(10, 3) == [4, 3, 3]


def test_split_rollout_steps_more_workers_than_steps():
    assert split_rollout_steps(3, 8) == [1, 1, 1]
