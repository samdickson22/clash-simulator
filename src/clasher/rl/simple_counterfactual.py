"""Batched exact terminal continuations for the practical Simple Gym.

One source decision boundary expands into a fixed resident candidate batch.
The first action differs per candidate; subsequent actions come from the same
model-neutral policy and public-mask-v2 contract used by production rollouts.
The source rollout is never mutated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields

import torch

from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_outcomes import crown_tower_hp, crowns_for_players
from clasher.torch_sim.simple_rollout import (
    SimpleGymRolloutBridge,
    SimpleGymRolloutObservation,
)

from .simple_tensor_collector import (
    SimplePublicActionMaskV2,
    SimplePublicMaskProvider,
    SimpleTensorMaskRequest,
    SimpleTensorPolicy,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)


class SimpleCounterfactualError(RuntimeError):
    """Raised when a candidate batch cannot produce exact terminal labels."""


@dataclass(frozen=True)
class SimpleTerminalCounterfactualBatch:
    """Terminal labels and exact public roots for a flattened candidate batch."""

    source_rows: torch.Tensor
    candidate_index: torch.Tensor
    learner_players: torch.Tensor
    first_actions: torch.Tensor
    first_action_success: torch.Tensor
    root_actor: TensorPublicStructuredObservation
    root_legal_masks: torch.Tensor
    root_public_action_masks: torch.Tensor
    terminal_winner: torch.Tensor
    terminal_value: torch.Tensor
    terminal_crowns: torch.Tensor
    terminal_tower_hp: torch.Tensor
    terminal_tower_damage_received: torch.Tensor
    decision_count: torch.Tensor
    native_ticks: torch.Tensor
    committed: torch.Tensor
    fallback_rows: torch.Tensor
    all_rows_admitted: torch.Tensor
    recurrent_inputs: Mapping[str, torch.Tensor] | None

    @property
    def flat_candidates(self) -> int:
        return int(self.first_actions.shape[0])


def _clone_public(
    value: TensorPublicStructuredObservation,
) -> TensorPublicStructuredObservation:
    return TensorPublicStructuredObservation(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(TensorPublicStructuredObservation)
        }
    )


def _fork_mapping(
    values: Mapping[str, torch.Tensor] | None,
    source_rows: torch.Tensor,
    *,
    source_batch_size: int,
) -> dict[str, torch.Tensor] | None:
    if values is None:
        return None
    result: dict[str, torch.Tensor] = {}
    for name, value in values.items():
        if value.ndim < 2 or value.shape[:2] != (source_batch_size, 2):
            raise ValueError(
                f"recurrent input {name!r} must begin with [source batch, 2]"
            )
        if value.device != source_rows.device:
            raise ValueError(f"recurrent input {name!r} must use the Gym device")
        result[name] = value.index_select(0, source_rows)
    return result


def _merge_recurrent_rows(
    previous: Mapping[str, torch.Tensor] | None,
    current: Mapping[str, torch.Tensor] | None,
    selected: torch.Tensor,
) -> dict[str, torch.Tensor] | None:
    if previous is None and current is None:
        return None
    if previous is None or current is None or tuple(previous) != tuple(current):
        raise SimpleCounterfactualError(
            "continuation recurrent-state structure changed"
        )
    result: dict[str, torch.Tensor] = {}
    for name, previous_value in previous.items():
        current_value = current[name]
        if (
            current_value.shape != previous_value.shape
            or current_value.device != previous_value.device
            or current_value.dtype != previous_value.dtype
        ):
            raise SimpleCounterfactualError(
                f"continuation recurrent state changed for {name!r}"
            )
        row_mask = selected.view(selected.shape[0], *((1,) * (current_value.ndim - 1)))
        result[name] = torch.where(row_mask, current_value, previous_value)
    return result


class SimpleTerminalCounterfactualEvaluator:
    """Evaluate fixed candidate actions through exact terminal continuations."""

    def __init__(
        self,
        bridge: SimpleGymRolloutBridge,
        *,
        public_mask_provider: SimplePublicMaskProvider,
        policy: SimpleTensorPolicy,
        terminal_check_interval: int = 0,
        strict_host_validation: bool = False,
    ) -> None:
        if bridge.strict_reset_check:
            raise ValueError("counterfactual bridge requires strict_reset_check=False")
        if terminal_check_interval < 0:
            raise ValueError("terminal_check_interval must be non-negative")
        self.bridge = bridge
        self.public_mask_provider = public_mask_provider
        self.policy = policy
        self.terminal_check_interval = int(terminal_check_interval)
        self.strict_host_validation = bool(strict_host_validation)

    def _mask(
        self,
        observation: SimpleGymRolloutObservation,
        *,
        decision_index: int,
        expected: tuple[str, str] | None,
    ) -> tuple[SimplePublicActionMaskV2, tuple[str, str]]:
        packet = self.public_mask_provider(
            SimpleTensorMaskRequest(
                observation=observation,
                decision_index=decision_index,
                bootstrap=False,
            )
        )
        if packet.contract_version != PUBLIC_ACTION_MASK_CONTRACT_V2:
            raise SimpleCounterfactualError("counterfactual masks must use contract v2")
        if packet.masks.shape[:2] != (self.bridge.batch_size, 2):
            raise SimpleCounterfactualError(
                "counterfactual public masks must begin with [batch, 2]"
            )
        if (
            packet.masks.dtype != torch.bool
            or packet.masks.device != self.bridge.device
        ):
            raise SimpleCounterfactualError(
                "counterfactual public masks must be bool on the Gym device"
            )
        semantics = (packet.semantics_id, packet.semantics_digest)
        if expected is not None and semantics != expected:
            raise SimpleCounterfactualError(
                "public-mask-v2 semantics changed during a continuation"
            )
        return packet, semantics

    @staticmethod
    def _boundary(
        observation: SimpleGymRolloutObservation,
        packet: SimplePublicActionMaskV2,
        recurrent_inputs: Mapping[str, torch.Tensor] | None,
        decision_index: int,
    ) -> SimpleTensorPolicyBoundary:
        return SimpleTensorPolicyBoundary(
            actor=observation.actor,
            critic=observation.critic,
            legal_mask=observation.legal_mask,
            public_action_masks=packet.masks,
            previous_actions=observation.previous_actions,
            previous_rewards=observation.previous_rewards,
            episode_starts=observation.episode_starts,
            recurrent_inputs=recurrent_inputs,
            decision_index=decision_index,
        )

    def _policy_decision(
        self,
        boundary: SimpleTensorPolicyBoundary,
        packet: SimplePublicActionMaskV2,
    ) -> tuple[SimpleTensorPolicyDecision, torch.Tensor]:
        decision = self.policy(boundary)
        actions = decision.actions
        if (
            actions.shape != (self.bridge.batch_size, 2)
            or actions.dtype != torch.int64
            or actions.device != self.bridge.device
        ):
            raise SimpleCounterfactualError(
                "continuation actions must be int64 [batch, 2] on the Gym device"
            )
        action_count = packet.masks.shape[2]
        in_bounds = (actions >= 0) & (actions < action_count)
        selected = packet.masks.gather(
            2,
            actions.clamp(0, action_count - 1)[..., None],
        ).squeeze(2)
        valid = in_bounds & selected
        if self.strict_host_validation and not bool(valid.all().item()):
            raise SimpleCounterfactualError("continuation policy action is invalid")
        return decision, valid

    @torch.no_grad()
    def evaluate(
        self,
        source: SimpleGymRolloutBridge,
        candidate_actions: torch.Tensor,
        *,
        learner_players: torch.Tensor,
        recurrent_inputs: Mapping[str, torch.Tensor] | None,
        max_decisions: int,
    ) -> SimpleTerminalCounterfactualBatch:
        """Fork ``source`` and evaluate ``[source, candidate, two seats]`` actions."""

        if candidate_actions.ndim != 3 or candidate_actions.shape[2] != 2:
            raise ValueError("candidate_actions must have shape [source, candidate, 2]")
        source_batch, candidate_count, _seats = candidate_actions.shape
        if source_batch != source.batch_size or candidate_count < 1:
            raise ValueError("candidate actions do not match the source batch")
        if source_batch * candidate_count != self.bridge.batch_size:
            raise ValueError("speculative bridge batch must equal source*candidates")
        if (
            candidate_actions.dtype != torch.int64
            or candidate_actions.device != self.bridge.device
            or source.device != self.bridge.device
        ):
            raise ValueError("candidate actions must be int64 on the Gym device")
        if learner_players.shape != (source_batch,):
            raise ValueError("learner_players must have shape [source]")
        if (
            learner_players.dtype != torch.int64
            or learner_players.device != source.device
        ):
            raise ValueError("learner_players must be int64 on the Gym device")
        learner_players_valid = (learner_players >= 0) & (learner_players <= 1)
        if self.strict_host_validation and not bool(learner_players_valid.all().item()):
            raise ValueError("learner_players must contain only 0 or 1")
        if max_decisions < 1:
            raise ValueError("max_decisions must be positive")

        source_rows = torch.arange(
            source_batch, dtype=torch.int64, device=source.device
        ).repeat_interleave(candidate_count)
        candidate_index = torch.arange(
            candidate_count, dtype=torch.int64, device=source.device
        ).repeat(source_batch)
        flat_actions = candidate_actions.reshape(self.bridge.batch_size, 2)
        flat_learner = learner_players.index_select(0, source_rows)
        current_recurrent: Mapping[str, torch.Tensor] | None = _fork_mapping(
            recurrent_inputs,
            source_rows,
            source_batch_size=source_batch,
        )
        self.bridge.copy_rows_from_(source, source_rows)

        root = self.bridge.observe()
        root_actor = _clone_public(root.actor)
        root_legal = root.legal_mask.clone()
        root_packet, mask_semantics = self._mask(
            root,
            decision_index=0,
            expected=None,
        )
        root_public_masks = root_packet.masks.clone()
        action_count = root_packet.masks.shape[2]
        candidate_in_bounds = (flat_actions >= 0) & (flat_actions < action_count)
        candidate_legal = root_packet.masks.gather(
            2,
            flat_actions.clamp(0, action_count - 1)[..., None],
        ).squeeze(2)
        policy_actions_valid = candidate_in_bounds & candidate_legal
        if self.strict_host_validation and not bool(policy_actions_valid.all().item()):
            raise SimpleCounterfactualError("candidate action is invalid")

        root_decision, root_policy_valid = self._policy_decision(
            self._boundary(root, root_packet, current_recurrent, 0),
            root_packet,
        )
        policy_actions_valid &= root_policy_valid
        root_recurrent = current_recurrent
        current_recurrent = root_decision.next_recurrent_inputs
        step = self.bridge.step(
            flat_actions,
            recurrent_inputs=root_recurrent,
            public_action_masks=root_packet.masks,
            public_action_mask_contract_version=root_packet.contract_version,
            pre_action_boundary=root,
        )
        first_action_success = step.action_success.clone()
        done = step.done.clone()
        winner = step.winner.clone()
        native_ticks = step.native_ticks.clone()
        committed = step.committed.clone()
        fallback_rows = step.fallback_rows.clone()
        all_rows_admitted = step.all_rows_admitted.clone()
        decision_count = torch.ones(
            self.bridge.batch_size, dtype=torch.int32, device=self.bridge.device
        )

        for decision_index in range(1, max_decisions):
            if (
                self.terminal_check_interval > 0
                and decision_index % self.terminal_check_interval == 0
                and bool(done.all().item())
            ):
                break
            observation = self.bridge.observe()
            packet, mask_semantics = self._mask(
                observation,
                decision_index=decision_index,
                expected=mask_semantics,
            )
            decision, decision_valid = self._policy_decision(
                self._boundary(
                    observation,
                    packet,
                    current_recurrent,
                    decision_index,
                ),
                packet,
            )
            policy_actions_valid &= done[:, None] | decision_valid
            actions = torch.where(
                done[:, None],
                torch.full_like(decision.actions, self.bridge.adapter.no_op_action),
                decision.actions,
            )
            live = ~done
            step = self.bridge.step(
                actions,
                recurrent_inputs=current_recurrent,
                public_action_masks=packet.masks,
                public_action_mask_contract_version=packet.contract_version,
                pre_action_boundary=observation,
            )
            current_recurrent = _merge_recurrent_rows(
                current_recurrent,
                decision.next_recurrent_inputs,
                live,
            )
            decision_count.add_(live.to(torch.int32))
            native_ticks.add_(torch.where(live, step.native_ticks, 0))
            committed &= (~live) | step.committed
            fallback_rows |= live & step.fallback_rows
            all_rows_admitted &= (~live) | step.all_rows_admitted
            winner = torch.where(live & step.done, step.winner, winner)
            done |= live & step.done

        invalid = torch.stack(
            (
                (~done).any(),
                (~learner_players_valid).any(),
                (~policy_actions_valid).any(),
                fallback_rows.any(),
                (~all_rows_admitted).any(),
                (~committed).any(),
            )
        ).any()
        if self.strict_host_validation or invalid.device.type in {"cpu", "mps"}:
            if bool(invalid.item()):
                raise SimpleCounterfactualError(
                    "counterfactual terminal-admission contract failed"
                )
        else:
            torch._assert_async(
                ~invalid,
                "counterfactual terminal-admission contract failed",
            )
        hp = crown_tower_hp(self.bridge.runtime.state)
        crowns = crowns_for_players(hp)
        damage_received = (self.bridge.initial_tower_hp - hp).clamp_min(0.0).sum(2)
        learner_won = winner.to(torch.int64) == flat_learner
        draw = winner.to(torch.int64) < 0
        terminal_value = torch.where(
            draw,
            torch.zeros_like(hp[:, 0, 0]),
            torch.where(
                learner_won,
                torch.ones_like(hp[:, 0, 0]),
                -torch.ones_like(hp[:, 0, 0]),
            ),
        )
        return SimpleTerminalCounterfactualBatch(
            source_rows=source_rows,
            candidate_index=candidate_index,
            learner_players=flat_learner,
            first_actions=flat_actions.clone(),
            first_action_success=first_action_success,
            root_actor=root_actor,
            root_legal_masks=root_legal,
            root_public_action_masks=root_public_masks,
            terminal_winner=winner,
            terminal_value=terminal_value,
            terminal_crowns=crowns,
            terminal_tower_hp=hp.clone(),
            terminal_tower_damage_received=damage_received,
            decision_count=decision_count,
            native_ticks=native_ticks,
            committed=committed,
            fallback_rows=fallback_rows,
            all_rows_admitted=all_rows_admitted,
            recurrent_inputs=current_recurrent,
        )


__all__ = [
    "SimpleCounterfactualError",
    "SimpleTerminalCounterfactualBatch",
    "SimpleTerminalCounterfactualEvaluator",
]
