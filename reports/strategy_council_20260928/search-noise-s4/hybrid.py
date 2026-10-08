"""Compose public-derived components; no engine state enters this boundary."""
import numpy as np
class Hybrid:
    def __init__(self,legacy,exact,repair_elixir,repair_hand,seed):
        self.legacy=legacy;self.exact=exact
        self.repair_elixir=repair_elixir;self.repair_hand=repair_hand
        self.cycle_rng=np.random.default_rng(seed)
    def __getattr__(self,name):return getattr(self.legacy,name)
    def sample(self,rng):
        if self.repair_elixir and self.repair_hand:return self.exact.sample(rng)
        sample=self.legacy.sample(rng)
        if self.repair_elixir:sample['elixir']=self.exact.elixir
        if self.repair_hand:
            exact=self.exact.sample(self.cycle_rng)
            for field in ('hand','cycle','refill'):sample[field]=exact[field]
        return sample
    def distribution(self):
        d=dict(self.legacy.distribution())
        if self.repair_elixir:d.update(elixir_mean=self.exact.elixir,elixir_interval_90=[self.exact.elixir]*2)
        if self.repair_hand:
            hand=self.exact.derived()['hand'];d.update(hand=hand,hand_probability=float(hand is not None))
        return d
