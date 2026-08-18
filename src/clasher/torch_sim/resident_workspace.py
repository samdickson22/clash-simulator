"""Preallocated speculative workspace for atomic resident battle ticks.

``TensorResidentEngine.step`` intentionally clones a complete engine before
each transaction.  ``TensorResidentWorkspace`` preserves the same phase and
whole-row commit contract while allocating that speculative engine once.
Every step refreshes its mutable planes with batched copies, executes in the
scratch buffer, and publishes only fully supported rows to the front engine.
Immutable catalogs, deployment kernels, and the deterministic path cache are
shared.
"""

from __future__ import annotations

from dataclasses import fields

import torch

from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import (
    ResidentTickResult,
    TensorResidentEngine,
)


def _copy_tensor_fields_(destination: object, source: object) -> None:
    """Copy equal-shaped tensor fields without indexing or replacement."""

    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
            if left.shape != right.shape or left.dtype != right.dtype:
                raise ValueError(f"workspace plane {descriptor.name!r} changed layout")
            left.copy_(right)


class TensorResidentWorkspace:
    """One committed engine plus one reusable speculative engine buffer."""

    def __init__(self, engine: TensorResidentEngine) -> None:
        self.engine = engine
        self.scratch = engine.clone()
        self._no_op_actions = torch.full(
            (engine.batch_size, 2),
            NO_OP_ACTION,
            dtype=torch.int64,
            device=engine.device,
        )
        self._assert_layout()

    @property
    def device(self) -> torch.device:
        return self.engine.device

    @property
    def batch_size(self) -> int:
        return self.engine.batch_size

    def _assert_layout(self) -> None:
        if self.scratch.batch_size != self.engine.batch_size:
            raise ValueError("scratch and committed engine batches differ")
        if self.scratch.device != self.engine.device:
            raise ValueError("scratch and committed engines use different devices")
        if self.scratch.runtime.catalog is not self.engine.runtime.catalog:
            raise ValueError("speculative engines must share the card catalog")
        if self.scratch.deployment is not self.engine.deployment:
            raise ValueError("speculative engines must share deployment kernels")
        if self.scratch.path_cache is not self.engine.path_cache:
            raise ValueError("speculative engines must share the path cache")
        if (
            self.scratch.projectile_bridge.catalog
            is not self.engine.projectile_bridge.catalog
        ):
            raise ValueError("speculative engines must share the projectile catalog")
        for owner in (self.engine, self.scratch):
            if owner.spell_ingress.runtime is not owner.runtime:
                raise ValueError("spell ingress must own its engine runtime")
            if owner.spell_ingress.objects is not owner.objects:
                raise ValueError("spell ingress must own its engine object phase")
            if owner.spell_ingress.bridge is not owner.projectile_bridge:
                raise ValueError("spell ingress must own its engine projectile bridge")
            if owner.action_router.runtime is not owner.runtime:
                raise ValueError("action router must own its engine runtime")
            if owner.action_router.objects is not owner.objects:
                raise ValueError("action router must own its engine object phase")
            if owner.action_router.bridge is not owner.projectile_bridge:
                raise ValueError("action router must own its engine projectile bridge")
            if owner.action_router.spells is not owner.spell_ingress:
                raise ValueError("action router must own its engine spell ingress")
            if owner.action_router.pending_spells is not owner.pending_spells:
                raise ValueError("action router must own its engine pending spells")
        if (
            self.scratch.spell_ingress.catalog_to_core.data_ptr()
            != self.engine.spell_ingress.catalog_to_core.data_ptr()
        ):
            raise ValueError("speculative engines must share immutable spell metadata")
        if (
            self.scratch.action_router._workspace
            is not self.engine.action_router._workspace
        ):
            raise ValueError("speculative engines must share retained router buffers")
        if self.scratch.pending_spells.active.data_ptr() == (
            self.engine.pending_spells.active.data_ptr()
        ):
            raise ValueError("speculative pending spells must own mutable storage")
        if (
            self.scratch.dispatcher.passive_catalog
            is not self.engine.dispatcher.passive_catalog
        ):
            raise ValueError("speculative engines must share dispatcher catalogs")
        if self.scratch.dispatcher.runtime is not self.scratch.runtime:
            raise ValueError("scratch dispatcher must own the scratch runtime")
        if self.scratch.dispatcher.mechanics is not self.scratch.mechanics:
            raise ValueError("scratch dispatcher must share resident mechanics")

    def refresh(self) -> None:
        """Reset every mutable scratch row without allocating another engine."""

        destination = self.scratch
        source = self.engine
        _copy_tensor_fields_(destination.runtime.battle, source.runtime.battle)
        _copy_tensor_fields_(destination.runtime.battle.rng, source.runtime.battle.rng)
        destination.runtime.entity_pool.active.copy_(source.runtime.entity_pool.active)
        destination.runtime.entity_pool.next_entity_id.copy_(
            source.runtime.entity_pool.next_entity_id
        )
        _copy_tensor_fields_(destination.runtime.status, source.runtime.status)
        _copy_tensor_fields_(destination.runtime.phases, source.runtime.phases)
        _copy_tensor_fields_(destination.runtime.events, source.runtime.events)
        destination.runtime.supported.copy_(source.runtime.supported)
        destination.runtime.dirty.copy_(source.runtime.dirty)
        destination.combat_target_entity_id.copy_(source.combat_target_entity_id)
        pending_rows = torch.arange(
            self.batch_size, dtype=torch.int64, device=self.device
        )
        destination.pending_spells.reset_rows_(
            pending_rows,
            source.pending_spells,
            pending_rows,
        )
        for left, right in (
            (destination.combat, source.combat),
            (destination.movement, source.movement),
            (destination.status, source.status),
            (destination.mechanics, source.mechanics),
            (destination.objects, source.objects),
            (destination.objects.objects, source.objects.objects),
            (destination.projectile_bridge, source.projectile_bridge),
            (destination.dispatcher.passive, source.dispatcher.passive),
            (destination.dispatcher.combat_world, source.dispatcher.combat_world),
            (destination.dispatcher.damage_ramp, source.dispatcher.damage_ramp),
            (destination.dispatcher.dash, source.dispatcher.dash),
            (destination.dispatcher.leap, source.dispatcher.leap),
            (destination.dispatcher.hook, source.dispatcher.hook),
        ):
            _copy_tensor_fields_(left, right)
        for name in (
            "special_triggered",
            "forced_movement",
            "knockback_target_units",
            "knockback_velocity_work",
            "initialized_entity_id",
            "multiple_target_ids",
            "multiple_target_valid",
            "underground_active",
        ):
            getattr(destination.dispatcher, name).copy_(
                getattr(source.dispatcher, name)
            )
        destination.dispatcher.runtime = destination.runtime
        destination.dispatcher.mechanics = destination.mechanics
        destination.runtime.battle.entity_id.copy_(source.runtime.battle.entity_id)
        destination.facing_x_units.copy_(source.facing_x_units)
        destination.facing_y_units.copy_(source.facing_y_units)
        destination.pending_projectile_max_duration_ms.copy_(
            source.pending_projectile_max_duration_ms
        )
        destination.projectile_duration_ms.copy_(source.projectile_duration_ms)
        destination.path_cache = source.path_cache
        destination.runtime.assert_invariants()

    def step(
        self,
        action_ids: torch.Tensor | None = None,
        *,
        player_order: torch.Tensor | None = None,
    ) -> ResidentTickResult:
        """Run the exact resident tick in scratch and atomically publish rows."""

        actions = (
            self._no_op_actions
            if action_ids is None
            else torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        )
        if actions.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        self.refresh()
        return self.engine._step_transaction(
            self.scratch,
            actions,
            player_order=player_order,
        )


__all__ = ["TensorResidentWorkspace"]
