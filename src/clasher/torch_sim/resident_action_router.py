"""Atomic shared-order routing for simultaneous resident card commands."""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .actions import TensorCommandQueue, TensorIngressResult
from .catalog import CardKindOpcode
from .deployment import TensorDeploymentResult
from .projectile_bridge import TensorResidentProjectileSpellBridge
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
from .runtime_deployment import TensorRuntimeDeployment
from .runtime_objects import TensorRuntimeObjectPhase
from .runtime_state import TensorBattleRuntime


@dataclass(frozen=True)
class TensorResidentActionRouterResult:
    committed: torch.Tensor
    action_success: torch.Tensor
    player_order: torch.Tensor
    ingress: TensorIngressResult
    spell_command: torch.Tensor


@dataclass
class _RouterWorkspace:
    runtime: TensorBattleRuntime
    objects: TensorRuntimeObjectPhase
    bridge: TensorResidentProjectileSpellBridge
    spells: TensorResidentSpellActionIngress

    @classmethod
    def create(
        cls,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
        spells: TensorResidentSpellActionIngress,
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
        )

    def refresh(
        self,
        runtime: TensorBattleRuntime,
        objects: TensorRuntimeObjectPhase,
        bridge: TensorResidentProjectileSpellBridge,
    ) -> None:
        _refresh_runtime(self.runtime, runtime)
        _copy_tensor_fields(self.objects, objects)
        _copy_tensor_fields(self.objects.objects, objects.objects)
        _copy_tensor_fields(self.bridge, bridge)


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
        self.device = runtime.device
        self._rows = torch.arange(
            runtime.batch_size, dtype=torch.int64, device=self.device
        )
        self._players = torch.arange(2, dtype=torch.int64, device=self.device)[None, :]
        self._workspace = _RouterWorkspace.create(runtime, objects, bridge, spells)

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
        workspace.refresh(self.runtime, self.objects, self.bridge)
        if player_order is None:
            choice = workspace.runtime.battle.rng.randrange(2)
            order = torch.stack((1 - choice, choice), dim=1)
        else:
            order = torch.as_tensor(player_order, dtype=torch.int64, device=self.device)
            valid_order = order.shape == (self.runtime.batch_size, 2) and bool(
                (torch.sort(order, dim=1).values == self._players).all().item()
            )
            if not valid_order:
                raise ValueError("player_order rows must be permutations of (0, 1)")

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
            matches = (commands.battle_index[None, :] == self._rows[:, None]) & (
                commands.player_id[None, :] == player[:, None]
            )
            found = matches.any(dim=1)
            command_index = matches.to(torch.int64).argmax(dim=1)
            rank_spell = found & command_spell[command_index]
            rank_character = found & ~command_spell[command_index]

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
            spell_ingress = _rank_ingress(
                ingress,
                current_state.hand_ids,
                current_state.cycle_ids,
                current_state.cycle_length,
                current_state.elixir,
                spell_commands,
                spell_transition,
            )
            spell_result: TensorResidentSpellIngressResult = workspace.spells.apply(
                spell_ingress,
                player_order=order,
            )

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
            row_supported &= ~rank_character | character_capacity
            workspace.runtime.supported &= row_supported
            deployment_result: TensorDeploymentResult = (
                self.deployment.materializer.materialize(
                    workspace.runtime,
                    character_ingress,
                    player_order=order,
                    _prevalidated=True,
                )
            )
            rank_committed = torch.where(
                rank_spell,
                spell_result.committed,
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
        return TensorResidentActionRouterResult(
            committed=row_supported,
            action_success=ingress.accepted & row_supported[:, None],
            player_order=order,
            ingress=ingress,
            spell_command=command_spell,
        )


__all__ = ["TensorResidentActionRouter", "TensorResidentActionRouterResult"]
