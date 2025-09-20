from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..card_types import Mechanic


@dataclass
class BaseMechanic(Mechanic, ABC):
    """Base class for all mechanics with default implementations"""

    def on_attach(self, entity) -> None:
        """Called when mechanic is attached to entity"""
        pass

    def on_spawn(self, entity) -> None:
        """Called when entity is spawned in battle"""
        pass

    def on_tick(self, entity, dt_ms: int) -> None:
        """Called each update tick"""
        pass

    def on_attack_start(self, entity, target) -> None:
        """Called before entity attacks"""
        pass

    def on_attack_hit(self, entity, target) -> None:
        """Called when entity attack hits target"""
        pass

    def on_death(self, entity) -> None:
        """Called when entity dies"""
        pass