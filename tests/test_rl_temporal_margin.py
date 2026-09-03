from __future__ import annotations

import pytest
import torch

from clasher.rl.temporal_margin import ActorTemporalMarginHead


def test_temporal_margin_starts_at_public_baseline_and_is_causal() -> None:
    torch.manual_seed(7)
    head = ActorTemporalMarginHead(32, projection_size=8, memory_size=4)
    state = torch.rand(2, 5, 32)
    first, _ = head(state)
    public = state[..., -18:]
    baseline = (public[..., 8:11].sum(-1) - public[..., 11:14].sum(-1)) / 3.0
    torch.testing.assert_close(first, baseline)

    with torch.no_grad():
        head.residual.weight.fill_(0.5)
    changed = state.clone()
    changed[:, 3:] = torch.rand_like(changed[:, 3:])
    original, _ = head(state)
    counterfactual, _ = head(changed)
    torch.testing.assert_close(original[:, :3], counterfactual[:, :3])


def test_temporal_margin_correction_is_exactly_zero_at_terminal_progress() -> None:
    head = ActorTemporalMarginHead(18, projection_size=4, memory_size=3)
    with torch.no_grad():
        head.residual.bias.fill_(10.0)
    state = torch.zeros(1, 2, 18)
    state[:, 1, 0] = 1.0
    prediction, _ = head(state)
    assert prediction[0, 0] > 0.0
    assert prediction[0, 1] == 0.0


def test_temporal_margin_contracts_fail_closed() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        ActorTemporalMarginHead(17)
    with pytest.raises(ValueError, match="progress power"):
        ActorTemporalMarginHead(18, progress_power=0.0)
    head = ActorTemporalMarginHead(18)
    with pytest.raises(ValueError, match="batch, time"):
        head(torch.zeros(2, 18))
