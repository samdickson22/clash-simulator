from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.resident_engine import TensorResidentEngine


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_unindexed_cuda_request_uses_concrete_runtime_device() -> None:
    engine = TensorResidentEngine.from_battles(
        [BattleState(fast_path=False)],
        device="cuda",
        max_entities=16,
        max_objects=16,
    )

    assert engine.device == torch.device("cuda", torch.cuda.current_device())
    assert engine.mechanics.device == engine.device
    assert engine.deployment.device == engine.device
