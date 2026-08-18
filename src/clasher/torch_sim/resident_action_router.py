"""Atomic shared-order routing for simultaneous resident card commands."""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .actions import TensorCommandQueue, TensorIngressResult
from .catalog import CardKindOpcode
from .deployment import TensorDeploymentResult
from .entity_pool import EntityAllocation
from .projectile_bridge import TensorResidentProjectileSpellBridge
from .resident_pending_spells import TensorResidentPendingSpells
from .resident_spell_ingress import (
    TensorResidentSpellActionIngress,
    TensorResidentSpellIngressResult,
    _clone_object_phase,
    _clone_tensor_owner,
    _copy_bridge_rows,
    _copy_phase_rows,
    _copy_runtime_rows,
    _copy_tensor_fields,
    _refresh_runtime,
)
from .runtime_deployment import (
    TensorRuntimeDeployment,
    TensorRuntimeDeploymentResult,
)
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorResidentActionRouterResult:
    committed: torch.Tensor
    action_success: torch.Tensor
    player_order: torch.Tensor
    ingress: TensorIngressResult
    spell_command: torch.Tensor
    deployment: TensorRuntimeDeploymentResult
    spell_ingress: TensorResidentSpellIngressResult


@dataclass
class _RouterWorkspace:
    runtime: TensorBattleRuntime
    objects: TensorRuntimeObjectPhase
    bridge: TensorResidentProjectileSpellBridge
    spells: TensorResidentSpellActionIngress
    pending_spells: TensorResidentPendingSpells

    @classmethod
    def create(
        cls,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
        spells: TensorResidentSpellActionIngress,
        pending_spells: TensorResidentPendingSpells,
    ) -> _RouterWorkspace:
        scratch_runtime = runtime.clone()
        scratch_runtime.battle.rng = runtime.battle.rng.clone()
        scratch_objects = _clone_object_phase(objects)
        scratch_bridge = _clone_tensor_owner(bridge)
        assert isinstance(scratch_bridge, TensorResidentProjectileSpellBridge)
        scratch_spells = TensorResidentSpellActionIngress(
            scratch_runtime,
            scratch_objects,
            scratch_bridge,
            spells.cards,
            catalog_to_core=spells.catalog_to_core,
            episode_supported_core=spells.episode_supported_core,
            collect_diagnostics=False,
            validate_inputs=False,
            batch_rows=spells._batch_rows,
            expected_player_order=spells._expected_player_order,
            empty_reasons=spells._empty_reasons,
        )
        return cls(
            runtime=scratch_runtime,
            objects=scratch_objects,
            bridge=scratch_bridge,
            spells=scratch_spells,
            pending_spells=pending_spells.clone(),
        )

    def refresh(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
        pending_spells: TensorResidentPendingSpells,
    ) -> None:
        _refresh_runtime(self.runtime, runtime)
        _copy_tensor_fields(self.objects, objects)
        _copy_tensor_fields(self.objects.objects, objects.objects)
        _copy_tensor_fields(self.bridge, bridge)
        rows = torch.arange(
            pending_spells.batch_size,
            dtype=torch.int64,
            device=pending_spells.device,
        )
        self.pending_spells.reset_rows_(rows, pending_spells, rows)


@dataclass
class _RouterAggregationBuffers:
    physical_slots: torch.Tensor
    allocation_slots: torch.Tensor
    valid: torch.Tensor
    entity_ids: torch.Tensor
    spawned_command: torch.Tensor
    spawned_card: torch.Tensor
    command_supported: torch.Tensor
    unsupported_spell: torch.Tensor
    unsupported_mechanic: torch.Tensor
    unsupported_payload: torch.Tensor
    unsupported_ability: torch.Tensor
    unsupported_conflict: torch.Tensor
    unsupported_capacity: torch.Tensor
    has_character: torch.Tensor
    has_spell: torch.Tensor

    @classmethod
    def create(
        cls,
        runtime: TensorBattleRuntime,
    ) -> _RouterAggregationBuffers:
        physical_slots = torch.arange(
            runtime.max_entities, dtype=torch.int64, device=runtime.device
        )[None, :].expand(runtime.batch_size, -1)
        command_shape = (runtime.batch_size * 2,)
        return cls(
            physical_slots=physical_slots,
            allocation_slots=torch.full_like(physical_slots, -1),
            valid=torch.zeros_like(physical_slots, dtype=torch.bool),
            entity_ids=torch.zeros_like(physical_slots),
            spawned_command=torch.full_like(physical_slots, -1),
            spawned_card=torch.zeros_like(physical_slots),
            command_supported=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_spell=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_mechanic=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_payload=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_ability=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_conflict=torch.zeros(
                command_shape, dtype=torch.bool, device=runtime.device
            ),
            unsupported_capacity=torch.zeros(
                runtime.batch_size, dtype=torch.bool, device=runtime.device
            ),
            has_character=torch.zeros(
                runtime.batch_size, dtype=torch.bool, device=runtime.device
            ),
            has_spell=torch.zeros(
                runtime.batch_size, dtype=torch.bool, device=runtime.device
            ),
        )

    def reset(self, command_count: int) -> None:
        self.valid.zero_()
        self.allocation_slots.fill_(-1)
        self.entity_ids.zero_()
        self.spawned_command.fill_(-1)
        self.spawned_card.zero_()
        for value in (
            self.command_supported,
            self.unsupported_spell,
            self.unsupported_mechanic,
            self.unsupported_payload,
            self.unsupported_ability,
            self.unsupported_conflict,
        ):
            value[:command_count].zero_()
        self.unsupported_capacity.zero_()
        self.has_character.zero_()
        self.has_spell.zero_()


def _select_commands(
    commands: TensorCommandQueue,
    selected: torch.Tensor,
) -> TensorCommandQueue:
    values = {
        descriptor.name: getattr(commands, descriptor.name)[selected]
        for descriptor in fields(commands)
    }
    return TensorCommandQueue(**values)


def _rank_ingress(
    full: TensorIngressResult,
    current_hand: torch.Tensor,
    current_cycle: torch.Tensor,
    current_cycle_length: torch.Tensor,
    current_elixir: torch.Tensor,
    commands: TensorCommandQueue,
    transition_player: torch.Tensor,
) -> TensorIngressResult:
    player_mask = transition_player[:, :, None]
    return TensorIngressResult(
        accepted=full.accepted & transition_player,
        selection=full.selection,
        commands=commands,
        hand_ids=torch.where(player_mask, full.hand_ids, current_hand),
        cycle_ids=torch.where(player_mask, full.cycle_ids, current_cycle),
        cycle_length=torch.where(
            transition_player,
            full.cycle_length,
            current_cycle_length,
        ),
        elixir=torch.where(transition_player, full.elixir, current_elixir),
    )


class TensorResidentActionRouter:
    """Execute spell and character commands in one simultaneous order."""

    def __init__(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
        deployment: TensorRuntimeDeployment,
        spells: TensorResidentSpellActionIngress,
        pending_spells: TensorResidentPendingSpells,
        spell_payload_supported_core: torch.Tensor | None = None,
    ) -> None:
        if spells.runtime is not runtime or spells.objects is not objects:
            raise ValueError("router spell ingress must own the routed state")
        if spells.bridge is not bridge:
            raise ValueError("router spell ingress must own the routed bridge")
        if deployment.catalog.cards is not runtime.catalog:
            raise ValueError("router deployment must share resident card metadata")
        self.runtime = runtime
        self.objects = objects
        self.bridge = bridge
        self.deployment = deployment
        self.spells = spells
        self.pending_spells = pending_spells
        self.spell_payload_supported_core = (
            bridge.catalog.supported
            if spell_payload_supported_core is None
            else spell_payload_supported_core
        )
        if self.spell_payload_supported_core.shape != bridge.catalog.supported.shape:
            raise ValueError("router spell support plane has an invalid shape")
        self.device = runtime.device
        self._rows = torch.arange(
            runtime.batch_size, dtype=torch.int64, device=self.device
        )
        self._players = torch.arange(2, dtype=torch.int64, device=self.device)[None, :]
        self._workspace = _RouterWorkspace.create(
            runtime, objects, bridge, spells, pending_spells
        )
        self._aggregation = _RouterAggregationBuffers.create(runtime)

    def _commit(self, source: _RouterWorkspace, rows: torch.Tensor) -> None:
        _copy_runtime_rows(self.runtime, source.runtime, rows)
        blueprint_indices = source.bridge.blueprint_for_slot[rows].flatten()
        _copy_phase_rows(
            self.objects,
            source.objects,
            rows,
            blueprint_indices,
        )
        _copy_bridge_rows(self.bridge, source.bridge, rows)
        selected = torch.nonzero(rows, as_tuple=False).flatten()
        self.pending_spells.reset_rows_(selected, source.pending_spells, selected)

    def apply(
        self,
        action_ids: torch.Tensor,
        *,
        player_order: torch.Tensor | None = None,
    ) -> TensorResidentActionRouterResult:
        actions = torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        if actions.shape != (self.runtime.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        initial_state = self.deployment.action_state(self.runtime)
        initial_legal = self.deployment.kernel.legal_action_mask(initial_state)
        ingress = self.deployment.kernel.ingress(
            initial_state,
            actions,
            legal_mask=initial_legal,
        )
        workspace = self._workspace
        workspace.refresh(
            self.runtime,
            self.objects,
            self.bridge,
            self.pending_spells,
        )
        if player_order is None:
            choice = workspace.runtime.battle.rng.randrange(2)
            order = torch.stack((1 - choice, choice), dim=1)
        else:
            order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
            if order.shape != (self.runtime.batch_size, 2):
                raise ValueError("player_order must have shape [batch, 2]")
            torch._assert_async(
                (torch.sort(order, dim=1).values == self._players).all(),
                "player_order rows must be permutations of (0, 1)",
            )

        commands = ingress.commands
        command_spell = (
            self.runtime.catalog.kind[commands.card_id] == int(CardKindOpcode.SPELL)
        ) & ~commands.is_ability
        spell_static = self.spells.preflight(ingress)
        command_supported = torch.where(
            command_spell,
            spell_static.command_supported,
            ~commands.is_ability,
        )
        command_count = int(commands.card_id.numel())
        aggregation = self._aggregation
        aggregation.reset(command_count)
        aggregate_command_supported = aggregation.command_supported[:command_count]
        aggregate_command_supported.copy_(command_supported)
        physical_slots = aggregation.physical_slots
        aggregate_valid = aggregation.valid
        aggregate_entity_ids = aggregation.entity_ids
        aggregate_spawned_command = aggregation.spawned_command
        aggregate_spawned_card = aggregation.spawned_card
        unsupported_spell = aggregation.unsupported_spell[:command_count]
        unsupported_mechanic = aggregation.unsupported_mechanic[:command_count]
        unsupported_payload = aggregation.unsupported_payload[:command_count]
        unsupported_ability = aggregation.unsupported_ability[:command_count]
        unsupported_ability.copy_(commands.is_ability)
        unsupported_conflict = aggregation.unsupported_conflict[:command_count]
        unsupported_capacity = aggregation.unsupported_capacity
        row_supported = self.runtime.supported.clone()
        if commands.battle_index.numel():
            rejected = torch.zeros_like(row_supported)
            rejected.scatter_reduce_(
                0,
                commands.battle_index,
                ~command_supported,
                reduce="amax",
                include_self=True,
            )
            row_supported &= ~rejected
        workspace.runtime.supported &= row_supported
        prior_character = torch.zeros_like(row_supported)

        for rank in range(2):
            player = order[:, rank]
            if command_count:
                matches = (commands.battle_index[None, :] == self._rows[:, None]) & (
                    commands.player_id[None, :] == player[:, None]
                )
                found = matches.any(dim=1)
                command_index = matches.to(torch.int64).argmax(dim=1)
                rank_spell = found & command_spell[command_index]
                rank_character = found & ~command_spell[command_index]
            else:
                found = torch.zeros_like(row_supported)
                rank_spell = torch.zeros_like(row_supported)
                rank_character = torch.zeros_like(row_supported)

            current_state = self.deployment.action_state(workspace.runtime)
            current_legal = self.deployment.kernel.legal_action_mask(current_state)
            safe_action = (
                actions.gather(1, player[:, None])
                .squeeze(1)
                .clamp(0, current_legal.shape[2] - 1)
            )
            dynamically_legal = current_legal[self._rows, player, safe_action]
            rank_valid = ~found | ~prior_character | dynamically_legal
            row_supported &= rank_valid
            workspace.runtime.supported &= row_supported

            selected_player = self._players == player[:, None]
            spell_transition = selected_player & rank_spell[:, None]
            character_transition = selected_player & rank_character[:, None]
            command_rank = commands.player_id == order[commands.battle_index, rank]
            spell_commands = _select_commands(
                commands,
                command_rank & command_spell & row_supported[commands.battle_index],
            )
            character_commands = _select_commands(
                commands,
                command_rank & ~command_spell & row_supported[commands.battle_index],
            )
            character_full_index = torch.nonzero(
                command_rank & ~command_spell & row_supported[commands.battle_index],
                as_tuple=False,
            ).flatten()
            spell_ingress = _rank_ingress(
                ingress,
                current_state.hand_ids,
                current_state.cycle_ids,
                current_state.cycle_length,
                current_state.elixir,
                spell_commands,
                spell_transition,
            )
            pending_result = workspace.pending_spells.enqueue_(
                workspace.runtime,
                workspace.bridge,
                spell_ingress,
                player_order=order,
                payload_supported_core=self.spell_payload_supported_core,
                _prevalidated_order=True,
            )
            row_supported &= pending_result.committed
            workspace.runtime.supported &= row_supported

            after_spell = self.deployment.action_state(workspace.runtime)
            character_ingress = _rank_ingress(
                ingress,
                after_spell.hand_ids,
                after_spell.cycle_ids,
                after_spell.cycle_length,
                after_spell.elixir,
                character_commands,
                character_transition,
            )
            character_capacity = self.deployment._capacity_support(
                workspace.runtime,
                character_ingress,
            )
            unsupported_capacity |= rank_character & ~character_capacity
            row_supported &= ~rank_character | character_capacity
            workspace.runtime.supported &= row_supported
            deployment_result: TensorDeploymentResult = (
                self.deployment.materializer.materialize(
                    workspace.runtime,
                    character_ingress,
                    player_order=order,
                    _prevalidated=True,
                    _prevalidated_order=True,
                )
            )
            if character_full_index.numel():
                aggregate_command_supported[character_full_index] &= (
                    deployment_result.command_supported
                )
                unsupported_spell[character_full_index] |= (
                    deployment_result.unsupported_spell
                )
                unsupported_mechanic[character_full_index] |= (
                    deployment_result.unsupported_mechanic
                )
                unsupported_payload[character_full_index] |= (
                    deployment_result.unsupported_payload
                )
                unsupported_ability[character_full_index] |= (
                    deployment_result.unsupported_ability
                )
                unsupported_conflict[character_full_index] |= (
                    deployment_result.unsupported_conflict
                )
            allocation = deployment_result.allocation
            allocation_rows = self._rows[:, None].expand_as(allocation.valid)
            allocation_slots = allocation.slots.clamp_min(0)
            valid_rows = allocation_rows[allocation.valid]
            valid_slots = allocation_slots[allocation.valid]
            aggregate_valid[valid_rows, valid_slots] = True
            aggregate_entity_ids[valid_rows, valid_slots] = allocation.entity_ids[
                allocation.valid
            ]
            spawned_local = deployment_result.spawned_command_index
            spawned = spawned_local >= 0
            if character_full_index.numel():
                spawned_global = character_full_index[spawned_local.clamp_min(0)]
                aggregate_spawned_command.copy_(
                    torch.where(
                        spawned,
                        spawned_global,
                        aggregate_spawned_command,
                    )
                )
            aggregate_spawned_card.copy_(
                torch.where(
                    spawned,
                    deployment_result.spawned_card_id,
                    aggregate_spawned_card,
                )
            )
            rank_committed = torch.where(
                rank_spell,
                pending_result.committed,
                torch.where(
                    rank_character,
                    deployment_result.battle_supported,
                    torch.ones_like(row_supported),
                ),
            )
            row_supported &= rank_committed
            workspace.runtime.supported &= row_supported
            prior_character |= rank_character & row_supported

        self._commit(workspace, row_supported)
        aggregate_command_supported &= row_supported[commands.battle_index]
        has_character = aggregation.has_character
        has_spell = aggregation.has_spell
        if commands.battle_index.numel():
            has_character.scatter_reduce_(
                0,
                commands.battle_index,
                ~command_spell,
                reduce="amax",
                include_self=True,
            )
            has_spell.scatter_reduce_(
                0,
                commands.battle_index,
                command_spell,
                reduce="amax",
                include_self=True,
            )
        aggregation.allocation_slots.copy_(
            torch.where(
                aggregate_valid,
                physical_slots,
                torch.full_like(physical_slots, -1),
            )
        )
        allocation = EntityAllocation(
            slots=aggregation.allocation_slots,
            entity_ids=aggregate_entity_ids,
            valid=aggregate_valid,
        )
        deployment_details = TensorDeploymentResult(
            player_order=order,
            allocation=allocation,
            command_supported=aggregate_command_supported,
            battle_supported=row_supported,
            unsupported_spell=unsupported_spell,
            unsupported_mechanic=unsupported_mechanic,
            unsupported_payload=unsupported_payload,
            unsupported_ability=unsupported_ability,
            unsupported_conflict=unsupported_conflict,
            spawned_command_index=aggregate_spawned_command,
            spawned_card_id=aggregate_spawned_card,
        )
        deployment = TensorRuntimeDeploymentResult(
            action_state=initial_state,
            legal_mask=initial_legal,
            ingress=ingress,
            deployment=deployment_details,
            committed=row_supported & has_character,
            unsupported_capacity=unsupported_capacity,
        )
        aggregate_spell_result = TensorResidentSpellIngressResult(
            committed=row_supported & has_spell,
            unsupported=has_spell & ~row_supported,
            unsupported_reasons=self.spells._empty_reasons,
            action_success=(
                ingress.accepted & row_supported[:, None] & has_spell[:, None]
            ),
            player_order=order,
            spell_command=command_spell,
        )
        return TensorResidentActionRouterResult(
            committed=row_supported,
            action_success=ingress.accepted & row_supported[:, None],
            player_order=order,
            ingress=ingress,
            spell_command=command_spell,
            deployment=deployment,
            spell_ingress=aggregate_spell_result,
        )


__all__ = ["TensorResidentActionRouter", "TensorResidentActionRouterResult"]
