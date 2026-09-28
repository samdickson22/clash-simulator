"""RL package exports without eagerly importing the battle simulator.

Live inference modules must be importable in a process that never constructs or
imports ``BattleState``.  Keep the historical package-level names, but resolve
them only when a caller explicitly asks for one.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .action_space import DiscreteTileActionSpace
    from .gym_env import ClasherSelfPlayGymEnv
    from .inference_server import InferenceServer
    from .model import MaskedPolicyValueNet
    from .obs_cv import CvObservationBuilder
    from .oracle_planner import FixedDepthThompsonOracle
    from .selfplay_env import SelfPlayBattleEnv

__all__ = [
    "ClasherSelfPlayGymEnv",
    "CvObservationBuilder",
    "DiscreteTileActionSpace",
    "FixedDepthThompsonOracle",
    "InferenceServer",
    "MaskedPolicyValueNet",
    "SelfPlayBattleEnv",
]

_LAZY_EXPORTS = {
    "DiscreteTileActionSpace": (".action_space", "DiscreteTileActionSpace"),
    "CvObservationBuilder": (".obs_cv", "CvObservationBuilder"),
    "SelfPlayBattleEnv": (".selfplay_env", "SelfPlayBattleEnv"),
    "MaskedPolicyValueNet": (".model", "MaskedPolicyValueNet"),
    "ClasherSelfPlayGymEnv": (".gym_env", "ClasherSelfPlayGymEnv"),
    "FixedDepthThompsonOracle": (".oracle_planner", "FixedDepthThompsonOracle"),
    "InferenceServer": (".inference_server", "InferenceServer"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
