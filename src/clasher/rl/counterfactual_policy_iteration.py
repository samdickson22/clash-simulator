"""KL-regularized policy improvement from terminal counterfactual branches."""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True)
class CandidatePolicyTarget:
    """A normalized improvement target over a finite legal candidate set."""

    actions: Tensor
    probabilities: Tensor
    valid: Tensor


@dataclass(frozen=True)
class CounterfactualPolicyLoss:
    """Separated policy-improvement and frozen-behavior anchor losses."""

    total: Tensor
    improvement: Tensor
    behavior_kl: Tensor


def _validate_candidate_rows(
    actions: Tensor,
    values: Tensor,
    valid: Tensor,
    *,
    action_count: int,
    behavior_actions: Tensor,
) -> None:
    if actions.ndim != 2 or values.shape != actions.shape or valid.shape != actions.shape:
        raise ValueError("candidate actions, values, and validity must be [rows, K]")
    if actions.dtype != torch.int64 or valid.dtype != torch.bool:
        raise ValueError("candidate actions must be int64 and validity must be bool")
    if behavior_actions.shape != actions.shape[:1] or behavior_actions.dtype != torch.int64:
        raise ValueError("behavior actions must be int64 [rows]")
    if not bool(valid.any(dim=-1).all()):
        raise ValueError("every root needs at least one valid candidate")
    selected = actions[valid]
    if bool(((selected < 0) | (selected >= action_count)).any()):
        raise ValueError("a valid candidate action is outside the policy support")
    if not bool(torch.isfinite(values[valid]).all()):
        raise ValueError("valid candidate values must be finite")
    for row in range(actions.shape[0]):
        row_actions = actions[row, valid[row]]
        if int(torch.unique(row_actions).numel()) != int(row_actions.numel()):
            raise ValueError("candidate actions must be unique within each root")
        if not bool((row_actions == behavior_actions[row]).any()):
            raise ValueError("every candidate set must retain the behavior action")


def kl_regularized_candidate_target(
    behavior_log_probs: Tensor,
    candidate_actions: Tensor,
    candidate_values: Tensor,
    candidate_valid: Tensor,
    behavior_actions: Tensor,
    *,
    beta: float,
) -> CandidatePolicyTarget:
    """Return ``pi_old(a) * exp(value(a) / beta)`` on each candidate set.

    Terminal outcome must already be the primary component of
    ``candidate_values``.  This function deliberately knows nothing about dense
    reward and cannot allow it to override the caller's outcome ordering.
    """

    if behavior_log_probs.ndim != 2:
        raise ValueError("behavior log probabilities must be [rows, actions]")
    if not math.isfinite(beta) or beta <= 0.0:
        raise ValueError("policy-improvement beta must be finite and positive")
    if behavior_log_probs.shape[0] != candidate_actions.shape[0]:
        raise ValueError("behavior policy and candidate roots differ")
    _validate_candidate_rows(
        candidate_actions,
        candidate_values,
        candidate_valid,
        action_count=behavior_log_probs.shape[1],
        behavior_actions=behavior_actions,
    )
    safe_actions = torch.where(
        candidate_valid, candidate_actions, torch.zeros_like(candidate_actions)
    )
    candidate_behavior = behavior_log_probs.gather(-1, safe_actions)
    if not bool(torch.isfinite(candidate_behavior[candidate_valid]).all()):
        raise ValueError("a counterfactual candidate has zero behavior support")
    target_logits = candidate_behavior + candidate_values / beta
    target_logits = target_logits.masked_fill(~candidate_valid, -torch.inf)
    target_probabilities = torch.softmax(target_logits, dim=-1)
    target_probabilities = torch.where(
        candidate_valid,
        target_probabilities,
        torch.zeros_like(target_probabilities),
    )
    return CandidatePolicyTarget(
        actions=candidate_actions,
        probabilities=target_probabilities.detach(),
        valid=candidate_valid,
    )


def forward_policy_kl(
    behavior_log_probs: Tensor, student_log_probs: Tensor
) -> Tensor:
    """Return mean ``KL(behavior || student)`` over the full legal support."""

    if student_log_probs.shape != behavior_log_probs.shape:
        raise ValueError("student and behavior policy supports differ")
    behavior_probability = behavior_log_probs.exp()
    support = behavior_probability > 0.0
    if not bool(torch.isfinite(student_log_probs[support]).all()):
        raise ValueError("student removed positive behavior-policy support")
    terms = torch.where(
        support,
        behavior_probability * (behavior_log_probs - student_log_probs),
        torch.zeros_like(behavior_probability),
    )
    return terms.sum(dim=-1).mean()


def counterfactual_policy_loss(
    student_log_probs: Tensor,
    behavior_log_probs: Tensor,
    target: CandidatePolicyTarget,
    *,
    behavior_kl_coefficient: float,
) -> CounterfactualPolicyLoss:
    """Fit the improved candidate target while anchoring the complete policy."""

    if not math.isfinite(behavior_kl_coefficient) or behavior_kl_coefficient < 0.0:
        raise ValueError("behavior KL coefficient must be finite and non-negative")
    if student_log_probs.ndim != 2 or student_log_probs.shape != behavior_log_probs.shape:
        raise ValueError("policy log probabilities must be matching [rows, actions]")
    if target.actions.shape[0] != student_log_probs.shape[0]:
        raise ValueError("candidate target roots differ from the policy batch")
    safe_actions = torch.where(
        target.valid, target.actions, torch.zeros_like(target.actions)
    )
    selected_student = student_log_probs.gather(-1, safe_actions)
    positive_target = target.probabilities > 0.0
    if not bool(torch.isfinite(selected_student[positive_target]).all()):
        raise ValueError("student removed positive improvement-target support")
    improvement = -torch.where(
        positive_target,
        target.probabilities * selected_student,
        torch.zeros_like(selected_student),
    ).sum(dim=-1).mean()
    behavior_kl = forward_policy_kl(behavior_log_probs, student_log_probs)
    return CounterfactualPolicyLoss(
        total=improvement + behavior_kl_coefficient * behavior_kl,
        improvement=improvement,
        behavior_kl=behavior_kl,
    )


__all__ = [
    "CandidatePolicyTarget",
    "CounterfactualPolicyLoss",
    "counterfactual_policy_loss",
    "forward_policy_kl",
    "kl_regularized_candidate_target",
]
