from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..card_types import Effect


@dataclass
class BaseEffect(Effect, ABC):
    """Base class for all effects"""

    @abstractmethod
    def apply(self, context) -> None:
        """Apply the effect with given context"""
        pass