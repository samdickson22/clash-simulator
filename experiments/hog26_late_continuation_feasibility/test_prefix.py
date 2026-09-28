"""The prefix changes only selected actions; release returns the original result."""

from types import SimpleNamespace

import torch
from prefix_policy import FrozenContinuation


class Model:
    def initial_state(self, count):
        return count

    def act(self, inputs, state, *, deterministic):
        self.result = (torch.tensor([[1], [2]]), object(), object(), state, object())
        return self.result


def inputs(tick):
    values = torch.zeros(2, 1, 18)
    values[:, 0, 0] = tick / 6000
    return SimpleNamespace(global_features=values, global_feature_confidence=torch.ones_like(values))


def test_prefix_actions_and_exact_release_identity():
    model = Model()
    wrapper = FrozenContinuation(model, 4000)
    state = wrapper.initial_state(2)
    for tick in range(0, 4008, 8):
        result = wrapper.act(inputs(tick), state, deterministic=True)
        if tick < 4000:
            assert torch.equal(result[0], torch.full((2, 1), 2304))
            assert all(a is b for a, b in zip(result[1:], model.result[1:], strict=True))
        else:
            assert result is model.result
    assert wrapper.calls == 501 and wrapper.prefix_calls == 500 and wrapper.changed_actions == 1000
    zero = FrozenContinuation(model, 0)
    zero.initial_state(2)
    assert zero.act(inputs(0), state, deterministic=True) is model.result
