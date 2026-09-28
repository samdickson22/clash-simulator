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

    def on_deploy_tick(self, entity, dt_ms: int) -> None:
        """Called while an entity is moving through its deployment sequence."""
        pass

    def on_movement_tick(self, entity, dt_ms: int) -> None:
        """Called from the native movement-component phase."""
        pass

    def on_object_tick(self, entity, dt_ms: int) -> None:
        """Called in the character/object phase, after native buff components."""
        pass

    def on_target_observed(self, entity, target, dt_ms: int) -> None:
        """Called after the combat component has selected its frame target."""
        pass

    def allows_target(self, entity, target) -> bool | None:
        """Optionally filter one target for this attacker's mechanic.

        Target-owned visibility and targetability remain the shared first
        gate.  Attacker-owned weapon rules can reject a target that is still
        globally targetable, such as a continuous-damage channel trying to
        connect to a character that currently rejects its effect.
        """
        return None

    def on_attack_start(self, entity, target) -> None:
        """Called before entity attacks"""
        pass

    def on_attack_committed(self, entity, target) -> None:
        """Called after an attack payload has been launched or resolved."""
        pass

    def on_attack_hit(self, entity, target) -> None:
        """Called when entity attack hits target"""
        pass

    def on_shield_lost(self, entity, shielded_entity) -> None:
        """Called when any live battle object loses its protection shield."""
        pass

    def on_knockback(self, entity) -> None:
        """Called after physical displacement interrupts the entity."""
        pass

    def allows_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> bool | None:
        """Optionally override whether a specific displacement can affect an entity.

        ``None`` leaves the ordinary effect guard in control.  A mechanic can
        return ``True`` for a native exception (for example Fisherman's hook
        interrupting an otherwise invulnerable dash) or ``False`` to block a
        displacement independently of damage/status immunity.
        """
        return None

    def on_forced_movement(
        self,
        entity,
        source_kind: str | None,
        movement_kind: str,
    ) -> None:
        """Called when an accepted displacement interrupts special movement."""
        pass

    def blocks_combat_actions(self, entity) -> bool:
        """Return whether this mechanic currently owns the action state.

        Committed casts can pause movement and the attack clock without
        pretending that the entity is stunned. Status effects and mechanic
        ticks still advance, so the cast can complete or be interrupted.
        """
        return False

    def allows_deployment_combat(self, entity, dt_ms: float) -> bool:
        """Whether deployment completion runs combat in the object update."""
        return False

    def modify_outgoing_damage(self, entity, target, damage: float) -> float:
        """Modify one attack payload for one recipient."""
        return damage

    def projectile_crown_tower_damage(
        self,
        entity,
        damage: float,
    ) -> float | None:
        """Return an exact Crown Tower payload for a launched projectile."""
        return None

    def on_death(self, entity) -> None:
        """Called when entity dies"""
        pass
