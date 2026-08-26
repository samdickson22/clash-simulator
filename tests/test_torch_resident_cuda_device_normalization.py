from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim.mechanic_dispatcher import TensorMechanicDispatcher
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.runtime_state import TensorBattleRuntime


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


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_unindexed_cuda_runtime_uses_concrete_mechanic_device() -> None:
    battle = BattleState(fast_path=False)
    runtime = TensorBattleRuntime.from_battles(
        [battle],
        device="cuda",
        max_entities=16,
    )
    dispatcher = TensorMechanicDispatcher.from_battles(runtime, [battle])

    assert runtime.device == torch.device("cuda", torch.cuda.current_device())
    assert dispatcher.device == runtime.device
    assert dispatcher.mechanics.device == runtime.device
