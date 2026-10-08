"""Fresh feed-forward public-information imitation model (T4)."""
from .network import ModelConfig, SetPolicy
from .inference import Policy, load_policy

__all__ = ["ModelConfig", "SetPolicy", "Policy", "load_policy"]
