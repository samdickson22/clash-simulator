import math

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import featurize as F
from bot.pretrain_v1.model import PolicyV1
from bot.pretrain_v1.policy import Session
from bot.pretrain_v1.policy_trace import PolicyTrace
from bot.pretrain_v1.tests.test_featurize import rec


def test_trace_preserves_session_and_samples_exact_captured_probability():
    torch.set_num_threads(1); torch.manual_seed(1)
    model = PolicyV1(d=24, layers=1, heads=3, ffn=48).eval()
    traced = PolicyTrace(model)
    ordinary, captured = Session(model, 9), Session(traced, 9)
    seen = set()
    for i in range(100):
        traced.clear()
        a, b = ordinary.step(rec(100+i*5)), captured.step(rec(100+i*5))
        assert (a.action, a.p_wait, a.value, a.status) == (b.action, b.p_wait, b.value, b.status)
        assert F.feature_bytes(ordinary.last_feat) == F.feature_bytes(captured.last_feat)
        seen.add(a.status)
        lp = traced.log_probability(b)
        from bot.pretrain_v1.rl_math import joint_terms
        tiles = torch.zeros(1, 4, F.NTILE)
        if b.status == 'play':
            tiles[0, b.slot] = traced._tile_logits[0]
        learned_lp, _ = joint_terms(traced._gate_logits, tiles, torch.tensor([b.action]), torch.tensor([5]))
        assert abs(float(learned_lp[0])-lp) < 2e-6
        if b.status == 'play':
            g = traced._gate_logits[0].softmax(-1).double().numpy()
            t = traced._tile_logits[0].softmax(-1).double().numpy()
            expected = (1-g[0])*(g[1:]/g[1:].sum())[b.slot]*(t/t.sum())[b.tile]
            assert lp == math.log(expected)
            ordinary.accepted(a); captured.accepted(b)
        elif b.status == 'wait':
            assert lp == math.log(b.p_wait)
        else:
            assert b.status == 'forced' and lp == 0.
    assert {'play', 'wait', 'forced'} <= seen


def test_trace_refuses_stale_and_wrong_cadence():
    torch.set_num_threads(1); torch.manual_seed(3)
    model = PolicyV1(d=24, layers=1, heads=3, ffn=48).eval()
    traced = PolicyTrace(model); session = Session(traced, 1)
    good = session.step(rec(100))
    with pytest.raises(ValueError, match='five-tick'):
        traced.log_probability(good, gap=10)
    stale = session.step(rec(200))
    with pytest.raises(ValueError, match='declined stale'):
        traced.log_probability(stale)
