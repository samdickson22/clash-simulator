"""Small configuration layer over the copied public search player."""
from dataclasses import dataclass
import json

import numpy as np

from public_planner import PublicPlanner


@dataclass(frozen=True)
class Config:
    name: str = 'current'
    horizon: int = 160
    interval: int = 10
    k: int = 1
    policy_top: int = 8
    script_top: int = 4
    opponent: str = 'sb-balanced'
    tower_weight: float = 0.0
    terminal: float = 2.0


CURRENT = Config()


class Planner(PublicPlanner):
    def __init__(self, resources, prior, config=CURRENT, *, seed=0):
        super().__init__(resources, prior, k=config.k, seed=seed, policy=True)
        self.config = config

    def score(self, root, seat, action, opponent, style):
        r, c = self.resources, self.config
        if c.tower_weight == 0:
            value = r.native.rollout(root, seat, action, opponent,
                                     'balanced', style, c.horizon, c.interval, 1.0)[0]
            return value * c.terminal / 2 if abs(value) == 2 else value
        # Same native transitions/scripts, exposing the final model state to the
        # alternative leaf without changing the native extension or engine.
        sim = root.clone()
        r.native.apply_discrete(sim, seat, action)
        r.native.apply_discrete(sim, 1-seat, opponent)
        ticks = 0
        while ticks < c.horizon:
            sim.step(min(c.interval, c.horizon-ticks))
            ticks += min(c.interval, c.horizon-ticks)
            value = r.native.evaluate(sim, seat, 1.0)
            if abs(value) == 2:
                return value * c.terminal / 2
            if value == 0 and json.loads(sim.snapshot())['game_over']:
                return 0.0
            if ticks < c.horizon:
                for actor, controller in ((seat, 'balanced'), (1-seat, style)):
                    a = r.native.select_action(sim, actor, controller)
                    r.native.apply_discrete(sim, actor, a)
        # Mean princess HP difference already exposed by the native leaf.
        parts = r.native.evaluation_parts(sim)
        return value + c.tower_weight * parts[1] * (1 if seat == 0 else -1)


def configurations():
    return [Config('h320', horizon=320),
            Config('h600-i20', horizon=600, interval=20),
            Config('h160-i20', interval=20),
            Config('h320-i20', horizon=320, interval=20),
            Config('h600-i10', horizon=600),
            Config('k2', k=2),
            Config('k4-i20', k=4, interval=20),
            Config('policy16', policy_top=16),
            Config('script8', script_top=8),
            Config('wide', policy_top=16, script_top=8),
            Config('mixture', opponent='mixture'),
            Config('tower', tower_weight=.5),
            Config('h320-tower', horizon=320, interval=20, tower_weight=.5),
            Config('terminal4', terminal=4.0)]
