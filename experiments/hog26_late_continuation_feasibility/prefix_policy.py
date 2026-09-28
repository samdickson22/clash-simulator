"""Real pass actions before a declared clock; original policy afterward."""

import numpy as np
import torch

from clasher.torch_sim.actions import NO_OP_ACTION


class FrozenContinuation:
    def __init__(self, model, release_tick):
        if type(release_tick) is not int or release_tick not in (0, 4000, 4800):
            raise ValueError('fixed zero/late release ticks required')
        self.model, self.release_tick = model, release_tick
        self.calls = self.prefix_calls = self.changed_actions = 0

    def initial_state(self, *args, **kwargs):
        self.calls = self.prefix_calls = self.changed_actions = 0
        return self.model.initial_state(*args, **kwargs)

    def act(self, inputs, state, *, deterministic):
        if deterministic is not True:
            raise ValueError('deterministic original policy required')
        clock = inputs.global_features[:, 0, 0].detach().cpu().numpy()
        confidence = inputs.global_feature_confidence[:, 0, 0].detach().cpu().numpy()
        if clock.shape != (2,) or not np.isfinite(clock).all() or not np.all(clock == clock[0]) or not np.all(confidence == 1):
            raise ValueError('shared fully observed public clock required')
        tick = round(float(clock[0]) * 6000)
        if tick != self.calls * 8:
            raise ValueError('complete unchanged eight-tick decision stream required')
        result = self.model.act(inputs, state, deterministic=True)
        self.calls += 1
        if tick >= self.release_tick:
            return result
        self.prefix_calls += 1
        self.changed_actions += int((result[0] != NO_OP_ACTION).sum())
        selected = torch.full_like(result[0], NO_OP_ACTION)
        return (selected, *result[1:])
