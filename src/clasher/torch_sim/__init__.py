"""Batched PyTorch battle simulator and parity tooling.

The package is intentionally separate from the Python oracle.  The oracle is
never imported by tensor kernels; adapters at the boundary translate state and
perform fail-closed parity checks.
"""

from .catalog import CardKindOpcode, TensorCardCatalog
from .diagnostics import StateDivergence, TorchParityError, first_divergence
from .executor import SimulatorBackend, TorchBattleExecutor
from .rng import TensorPythonRandom
from .state import TensorBattleState

__all__ = [
    "CardKindOpcode",
    "SimulatorBackend",
    "StateDivergence",
    "TensorBattleState",
    "TensorCardCatalog",
    "TensorPythonRandom",
    "TorchBattleExecutor",
    "TorchParityError",
    "first_divergence",
]
