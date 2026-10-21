"""pretrain-v1 decision session: one forward pass per poll, fully sampled gate / slot / tile, no search.

The integration point for the simulator actor and (later, separately approved) the live loop. Per poll:

    d = session.step(record, extras, frame_age_ms=None)    # featurize.observe + network + masks + sampling
    ... the command channel submits d.action (or not) ...
    session.accepted(d)   or   session.rejected(tick)       # the channel's verdict drives History, as offline

Sampling (DESIGN "Action timing"): at the reference 5-tick cadence p_wait = softmax(masked gate logits)[no-op];
for an irregular gap dt the survival form P(wait over dt) = p_wait**(dt/5), dt clipped to [1, 10]; a Bernoulli draw
picks wait / play, then the slot (conditional on play) and the tile are sampled at temperature 1. Gaps over 10
ticks or inputs older than 350 ms are declined (logged as stale, never a WAIT label). No argmax anywhere; no search
fallback; no timed holds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time

import numpy as np
import torch

from . import featurize as F
from .model import PolicyV1, collate, tiles_ok_np

STALE_GAP = 10
STALE_MS = 350


@dataclass
class Decision:
    action: int                      # NOOP or slot*576 + tile
    tick: int
    p_wait: float                    # survival-scaled probability of no command over this gap
    p_wait5: float                   # reference-cadence probability
    value: float                     # P(win) - P(loss)
    status: str                      # 'wait' | 'play' | 'forced' (no legal play) | 'stale'
    slot: int = -1
    tile: int = -1
    card: str = ''
    ms: dict = field(default_factory=dict)


def load(path, map_location='cpu'):
    ck = torch.load(path, map_location=map_location, weights_only=False)
    if ck.get('feature_hash') != F.feature_hash():
        raise RuntimeError(f"checkpoint feature hash {ck.get('feature_hash')} != this featurizer {F.feature_hash()}")
    m = PolicyV1(**{k: v for k, v in ck['cfg'].items() if k in ('d', 'layers', 'heads', 'ffn', 'n_cards', 'n_bodies')})
    m.load_state_dict(ck['model'])
    m.eval()
    return m, ck


class Session:
    """One battle perspective. Not thread-safe; one per seat per battle."""

    def __init__(self, model, seed, temperature=1.0):
        self.m = model
        self.rng = np.random.default_rng(seed)
        self.T = float(temperature)
        self.hist = F.History()
        self.last_tick = None
        self.last_feat = None

    @torch.inference_mode()
    def step(self, record, extras=None, frame_age_ms=None):
        t0 = time.perf_counter()
        feat = F.observe(record, extras, self.hist)
        t1 = time.perf_counter()
        tick = int(feat['glob'][F.G_TICK])
        gap = tick - self.last_tick if self.last_tick is not None else F.POLL
        self.last_tick = tick
        self.last_feat = feat
        b = collate([feat])
        cls, hand = self.m.trunk(b)
        gate = self.m.gate_logits(cls, hand, b['slot_ok'])[0]
        v = torch.softmax(self.m.value(cls)[0], -1)
        value = float(v[2] - v[0])
        t2 = time.perf_counter()
        ms = dict(features=1e3*(t1 - t0), network=1e3*(t2 - t1))
        if not feat['slot_ok'].any():
            return Decision(F.NOOP, tick, 1., 1., value, 'forced', ms=ms)
        if gap > STALE_GAP or (frame_age_ms is not None and frame_age_ms > STALE_MS):
            return Decision(F.NOOP, tick, 1., 1., value, 'stale', ms=ms)
        p = torch.softmax(gate/self.T, -1).double().numpy()
        p_wait5 = float(p[0])
        p_wait = p_wait5**(min(max(gap, 1), STALE_GAP)/F.POLL)
        if self.rng.random() < p_wait:
            ms['decode'] = 1e3*(time.perf_counter() - t2)
            return Decision(F.NOOP, tick, p_wait, p_wait5, value, 'wait', ms=ms)
        ps = p[1:]/p[1:].sum()
        slot = int(self.rng.choice(4, p=ps))
        tiles_ok = torch.from_numpy(tiles_ok_np(feat['hand'][None], feat['slot_ok'][None], feat['alive'][None]))
        z = self.m.tile_logits(cls, hand, torch.tensor([slot]), tiles_ok[:, slot])[0]
        pt = torch.softmax(z/self.T, -1).double().numpy()
        tile = int(self.rng.choice(F.NTILE, p=pt/pt.sum()))
        ms['decode'] = 1e3*(time.perf_counter() - t2)
        card = record['hand']['cards'][slot]
        return Decision(F.encode(slot, tile), tick, p_wait, p_wait5, value, 'play', slot, tile, card, ms)

    def accepted(self, d):
        """The channel accepted d's command (it is now the one outstanding command)."""
        self.hist.submit(d.tick, d.slot, d.card, d.tile)

    def rejected(self, tick):
        self.hist.reject(tick)
