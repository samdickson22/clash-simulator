"""Atomic action ingress and deployment for the retained tensor runtime.

The command materializer owns exact formation/allocation mechanics.  This
module supplies the production transaction around it: derive action legality
from retained tensors, run ingress, speculate (including RNG) on an isolated
runtime fork, and publish only rows whose complete simultaneous command set is
supported.  No supported-path operation enters ``BattleState.deploy_card``.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .actions import (
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
    TensorIngressResult,
)
from .deployment import TensorCommandMaterializer, TensorDeploymentResult
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorRuntimeDeploymentResult:
    """Complete action/deployment transaction diagnostics."""

    action_state: TensorActionState
    legal_mask: torch.Tensor
    ingress: TensorIngressResult
    deployment: TensorDeploymentResult
    committed: torch.Tensor
    unsupported_capacity: torch.Tensor


def _copy_tensor_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch_size = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape[0] == batch_size
            and right.shape == left.shape
        ):
            left[rows] = right[rows]


def _commit_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    """Publish speculative rows without breaking canonical identity aliases."""

    if not bool(rows.any().item()):
        return
    _copy_tensor_rows_(destination.battle, source.battle, rows)
    _copy_tensor_rows_(destination.battle.rng, source.battle.rng, rows)
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    # entity_pool.entity_id aliases battle.entity_id in both runtimes and was
    # already copied with the core state above.
    _copy_tensor_rows_(destination.status, source.status, rows)
    _copy_tensor_rows_(destination.phases, source.phases, rows)
    _copy_tensor_rows_(destination.events, source.events, rows)
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]
    destination.assert_invariants()


class TensorRuntimeDeployment:
    """Compose action legality, ingress, and command materialization."""

    def __init__(
        self,
        action_catalog: TensorActionCatalog,
        materializer: TensorCommandMaterializer,
    ) -> None:
        if action_catalog.cards is not materializer.catalog.cards:
            raise ValueError("action and deployment catalogs must share card metadata")
        self.catalog = action_catalog
        self.kernel = TensorActionKernel(action_catalog)
        self.materializer = materializer
        self.device = action_catalog.cards.device

    def prepare_runtime(self, runtime: TensorBattleRuntime) -> None:
        """Install the materializer's stable card-name namespace once."""

        self._validate_runtime(runtime)
        self.materializer.prepare_runtime(runtime)
        runtime.assert_invariants()

    def _validate_runtime(self, runtime: TensorBattleRuntime) -> None:
        if runtime.device != self.device:
            raise ValueError("runtime and deployment driver must share a device")
        if runtime.catalog is not self.catalog.cards:
            raise ValueError("runtime and deployment driver must share card metadata")

    def action_state(self, runtime: TensorBattleRuntime) -> TensorActionState:
        """Project action inputs from retained tensors without Python objects."""

        self.prepare_runtime(runtime)
        battle = runtime.battle
        catalog_index = runtime.card_catalog_index
        hand_ids = catalog_index[battle.hand]
        cycle_ids = catalog_index[battle.cycle_queue]
        hand_known = (hand_ids >= 0).all(dim=2)
        cycle_slots = torch.arange(
            battle.cycle_queue.shape[2], device=self.device
        ).view(1, 1, -1)
        cycle_live = cycle_slots < battle.cycle_queue_length[:, :, None]
        cycle_known = ((cycle_ids >= 0) | ~cycle_live).all(dim=2)
        hand_ids = hand_ids.clamp_min(0)
        cycle_ids = cycle_ids.clamp_min(0)

        active = runtime.entity_pool.active & battle.entity_active
        entity_catalog = catalog_index[battle.entity_card]
        building = active & (battle.entity_kind == 1)
        crown_tower = building & (battle.entity_tower_slot >= 0)
        known_building = ~building | crown_tower | (entity_catalog >= 0)
        unsupported_object = active & ~(
            (battle.entity_kind == 0) | (battle.entity_kind == 1)
        )
        row_supported = (
            runtime.supported
            & known_building.all(dim=1)
            & ~unsupported_object.any(dim=1)
        )
        player_supported = row_supported[:, None] & hand_known & cycle_known

        safe_card = entity_catalog.clamp_min(0)
        building_alive = building & (crown_tower | (entity_catalog >= 0))
        building_radius = self.catalog.cards.collision_radius_units[safe_card].to(
            torch.int32
        )
        building_radius = torch.where(
            building_radius > 0,
            building_radius,
            torch.full_like(building_radius, 500),
        )
        building_half = self.catalog.building_footprint_half_units[safe_card].to(
            torch.int32
        )
        # Static Crown cards are arena support characters rather than playable
        # catalog entries. Their stable tower-slot schema supplies the same
        # serialized collision/footprint values used by the Python adapter.
        tower_slot = battle.entity_tower_slot.clamp(min=0).to(torch.int64)
        tower_radius_by_slot = torch.tensor(
            (1_000, 1_000, 1_400), dtype=torch.int32, device=self.device
        )
        tower_half_by_slot = torch.tensor(
            (1_500, 1_500, 2_000), dtype=torch.int32, device=self.device
        )
        building_radius = torch.where(
            crown_tower,
            tower_radius_by_slot[tower_slot],
            building_radius,
        )
        building_half = torch.where(
            crown_tower,
            tower_half_by_slot[tower_slot],
            building_half,
        )

        # Character-only retained rows contain no deployment-blocking payload
        # object. A live kind-2/3 object makes the entire row unsupported above.
        blocker_shape = (runtime.batch_size, 1)
        blocker_alive = torch.zeros(blocker_shape, dtype=torch.bool, device=self.device)
        blocker_units = torch.zeros(
            blocker_shape, dtype=torch.int32, device=self.device
        )
        return TensorActionState(
            hand_ids=hand_ids,
            cycle_ids=cycle_ids,
            cycle_length=battle.cycle_queue_length.to(torch.int64),
            elixir=battle.elixir,
            player_alive=battle.tower_hp[:, :, 2] > 0.0,
            tower_alive=battle.tower_hp > 0.0,
            ability_legal=torch.zeros(
                (runtime.batch_size, 2), dtype=torch.bool, device=self.device
            ),
            building_alive=building_alive,
            building_x_units=battle.entity_x_units,
            building_y_units=battle.entity_y_units,
            building_collision_radius_units=building_radius,
            building_footprint_half_units=building_half,
            blocker_alive=blocker_alive,
            blocker_x_units=blocker_units.clone(),
            blocker_y_units=blocker_units.clone(),
            blocker_radius_units=blocker_units,
            supported=player_supported,
        )

    def _capacity_support(
        self,
        runtime: TensorBattleRuntime,
        ingress: TensorIngressResult,
    ) -> torch.Tensor:
        commands = ingress.commands
        counts = torch.zeros(runtime.batch_size, dtype=torch.int64, device=self.device)
        if commands.battle_index.numel():
            command_counts = self.materializer.catalog.summon_count[
                commands.card_id
            ].to(torch.int64)
            counts.scatter_add_(0, commands.battle_index, command_counts)
        available_slots = (~runtime.entity_pool.active).sum(dim=1, dtype=torch.int64)
        available_events = runtime.events.capacity - runtime.events.count.to(
            torch.int64
        )
        return (counts <= available_slots) & (counts <= available_events)

    def apply(
        self,
        runtime: TensorBattleRuntime,
        action_ids: torch.Tensor,
        *,
        player_order: torch.Tensor | None = None,
    ) -> TensorRuntimeDeploymentResult:
        """Run one atomic simultaneous-deployment transaction."""

        self._validate_runtime(runtime)
        actions = torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        if actions.shape != (runtime.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        state = self.action_state(runtime)
        legal = self.kernel.legal_action_mask(state)
        ingress = self.kernel.ingress(state, actions, legal_mask=legal)
        capacity_supported = self._capacity_support(runtime, ingress)

        speculative = runtime.clone()
        # TensorBattleRuntime.fork currently shares the nested RNG owner even
        # though its other retained tensors are independent. Replace it before
        # the speculative player-order draw so rejected rows remain atomic.
        speculative.battle.rng = runtime.battle.rng.clone()
        speculative.supported &= capacity_supported
        speculative.phases.supported[~capacity_supported] = False
        deployment = self.materializer.materialize(
            speculative,
            ingress,
            player_order=player_order,
        )
        committed = deployment.battle_supported & capacity_supported
        _commit_runtime_rows_(runtime, speculative, committed)
        return TensorRuntimeDeploymentResult(
            action_state=state,
            legal_mask=legal,
            ingress=ingress,
            deployment=deployment,
            committed=committed,
            unsupported_capacity=~capacity_supported,
        )


__all__ = ["TensorRuntimeDeployment", "TensorRuntimeDeploymentResult"]
