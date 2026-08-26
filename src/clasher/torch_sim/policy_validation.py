"""Policy-facing resident Gym transition validation.

This module compares already-projected policy inputs and transition outputs. It
deliberately reuses :class:`ResidentOutputProjector` and
:class:`StructuredObservationBuilder`; it does not define another observation
projection.

The scope is narrower than simulator parity. CPython RNG state, unprojected
runtime/oracle event queues, event ordering, and future behavior-bearing state
are outside this comparator. A passing result must therefore be paired with the
strict resident differential before native Gym admission. Projected public
event tensors may be supplied as recurrent inputs and are then compared exactly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH
from clasher.rl.structured_obs import StructuredObservationBuilder

from .resident_outputs import (
    ResidentOutputProjector,
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)

PUBLIC_ACTION_MASK_CONTRACT_V2 = 2
PROJECTED_GYM_TRANSITION_PROFILE = "projected_gym_transition_v1"
ACTOR_POSITION_TOLERANCE_TILES = 0.25
_POSITION_FLOAT32_RESIDUE_TILES = (
    max(BOARD_WIDTH, BOARD_HEIGHT) * torch.finfo(torch.float32).eps
)
OUTSIDE_POLICY_TRANSITION_SCOPE = (
    "CPython RNG state and consumption",
    "unprojected oracle/runtime event payloads, ordering, and capacity",
    "future behavior-bearing simulator state not present in policy tensors",
)

TensorLike = torch.Tensor | np.ndarray


def _tensor(value: TensorLike) -> torch.Tensor:
    return torch.as_tensor(value).detach()


def _cpu(value: TensorLike) -> torch.Tensor:
    return _tensor(value).to(device="cpu")


def _shape(value: TensorLike) -> tuple[int, ...]:
    return tuple(int(part) for part in _tensor(value).shape)


@dataclass(frozen=True)
class ProjectedGymTransition:
    """One resident Gym decision boundary for both player seats."""

    actor: TensorPublicStructuredObservation
    action_success: TensorLike
    rewards: TensorLike
    done: TensorLike
    winner: TensorLike
    previous_actions: TensorLike
    previous_rewards: TensorLike
    episode_starts: TensorLike
    public_action_masks: TensorLike | None = None
    public_action_mask_contract_version: int | None = None
    critic: TensorPrivilegedCriticObservation | None = None
    recurrent_inputs: Mapping[str, TensorLike] | None = None

    def __post_init__(self) -> None:
        actor_ids = _shape(self.actor.entity_ids)
        if len(actor_ids) != 3 or actor_ids[1] != 2:
            raise ValueError("actor entity_ids must have shape [batch, 2, entities]")
        batch, seats, entities = actor_ids
        actor_shapes = {
            "entity_features": _shape(self.actor.entity_features),
            "entity_mask": _shape(self.actor.entity_mask),
            "hand_ids": _shape(self.actor.hand_ids),
            "global_features": _shape(self.actor.global_features),
        }
        if actor_shapes["entity_features"][:3] != (batch, seats, entities):
            raise ValueError(
                "actor entity_features must align with [batch, 2, entities]"
            )
        if actor_shapes["entity_mask"] != (batch, seats, entities):
            raise ValueError("actor entity_mask must align with entity_ids")
        for name in ("hand_ids", "global_features"):
            if len(actor_shapes[name]) != 3 or actor_shapes[name][:2] != (batch, seats):
                raise ValueError(f"actor {name} must have shape [batch, 2, features]")

        for name in (
            "action_success",
            "rewards",
            "previous_actions",
            "previous_rewards",
            "episode_starts",
        ):
            if _shape(getattr(self, name)) != (batch, seats):
                raise ValueError(f"{name} must have shape [batch, 2]")
        for name in ("done", "winner"):
            if _shape(getattr(self, name)) != (batch,):
                raise ValueError(f"{name} must have shape [batch]")

        if self.public_action_masks is None:
            if self.public_action_mask_contract_version is not None:
                raise ValueError("mask contract version requires public action masks")
        else:
            masks = _shape(self.public_action_masks)
            if len(masks) != 3 or masks[:2] != (batch, seats):
                raise ValueError(
                    "public_action_masks must have shape [batch, 2, actions]"
                )
            if (
                self.public_action_mask_contract_version
                != PUBLIC_ACTION_MASK_CONTRACT_V2
            ):
                raise ValueError(
                    "policy validation accepts public-mask contract v2 only"
                )

        if self.critic is not None:
            for descriptor in fields(self.critic):
                shape = _shape(getattr(self.critic, descriptor.name))
                if len(shape) < 2 or shape[:2] != (batch, seats):
                    raise ValueError(
                        f"critic {descriptor.name} must begin with [batch, 2]"
                    )
        for name, value in (self.recurrent_inputs or {}).items():
            shape = _shape(value)
            if len(shape) < 2 or shape[:2] != (batch, seats):
                raise ValueError(f"recurrent input {name!r} must begin with [batch, 2]")


@dataclass(frozen=True)
class ProjectedGymTransitionDivergence:
    field: str
    index: tuple[int, ...] | None
    expected: object
    actual: object
    reason: str

    def __str__(self) -> str:
        location = self.field
        if self.index is not None:
            location += "[" + ",".join(str(part) for part in self.index) + "]"
        return (
            f"policy transition divergence at {location}: expected "
            f"{self.expected!r}, got {self.actual!r} ({self.reason})"
        )


@dataclass(frozen=True)
class ProjectedGymTransitionComparison:
    divergence: ProjectedGymTransitionDivergence | None
    max_actor_position_error_tiles: float
    public_action_mask_contract_version: int | None
    critic_compared: bool
    recurrent_inputs_compared: tuple[str, ...]
    outside_scope: tuple[str, ...] = OUTSIDE_POLICY_TRANSITION_SCOPE
    profile: str = PROJECTED_GYM_TRANSITION_PROFILE

    @property
    def passed(self) -> bool:
        return self.divergence is None

    def require_passed(self) -> None:
        if self.divergence is not None:
            raise AssertionError(str(self.divergence))


def _value(tensor: torch.Tensor, index: tuple[int, ...]) -> object:
    return tensor[index].item()


def _first_exact_divergence(
    field: str,
    expected_value: TensorLike,
    actual_value: TensorLike,
) -> ProjectedGymTransitionDivergence | None:
    expected = _cpu(expected_value)
    actual = _cpu(actual_value)
    if expected.dtype != actual.dtype:
        return ProjectedGymTransitionDivergence(
            field,
            None,
            str(expected.dtype),
            str(actual.dtype),
            "dtype mismatch",
        )
    if expected.shape != actual.shape:
        return ProjectedGymTransitionDivergence(
            field,
            None,
            tuple(expected.shape),
            tuple(actual.shape),
            "shape mismatch",
        )
    equal = expected == actual
    if bool(equal.all().item()):
        return None
    flat = int(torch.nonzero((~equal).reshape(-1), as_tuple=False)[0, 0].item())
    index = tuple(int(part) for part in np.unravel_index(flat, tuple(expected.shape)))
    return ProjectedGymTransitionDivergence(
        field,
        index,
        _value(expected, index),
        _value(actual, index),
        "exact field mismatch",
    )


def _actor_feature_comparison(
    expected_value: TensorLike,
    actual_value: TensorLike,
) -> tuple[ProjectedGymTransitionDivergence | None, float]:
    expected = _cpu(expected_value)
    actual = _cpu(actual_value)
    if expected.dtype != actual.dtype:
        return (
            ProjectedGymTransitionDivergence(
                "actor.entity_features",
                None,
                str(expected.dtype),
                str(actual.dtype),
                "dtype mismatch",
            ),
            0.0,
        )
    if expected.shape != actual.shape:
        return (
            ProjectedGymTransitionDivergence(
                "actor.entity_features",
                None,
                tuple(expected.shape),
                tuple(actual.shape),
                "shape mismatch",
            ),
            0.0,
        )
    if expected.shape[-1] < 2:
        return (
            ProjectedGymTransitionDivergence(
                "actor.entity_features",
                None,
                "at least two feature columns",
                int(expected.shape[-1]),
                "projected position columns are unavailable",
            ),
            0.0,
        )

    non_position_equal = expected[..., 2:] == actual[..., 2:]
    if not bool(non_position_equal.all().item()):
        mismatch = torch.nonzero(~non_position_equal, as_tuple=False)[0]
        index = tuple(int(part) for part in mismatch.tolist())
        full_index = (*index[:-1], index[-1] + 2)
        return (
            ProjectedGymTransitionDivergence(
                "actor.entity_features",
                full_index,
                _value(expected, full_index),
                _value(actual, full_index),
                "non-position policy feature must be exact",
            ),
            0.0,
        )

    x_error_tiles = (actual[..., 0] - expected[..., 0]).abs() * BOARD_WIDTH
    y_error_tiles = (actual[..., 1] - expected[..., 1]).abs() * BOARD_HEIGHT
    position_errors = torch.stack((x_error_tiles, y_error_tiles), dim=-1)
    maximum = float(position_errors.max().item()) if position_errors.numel() else 0.0
    # The established structured projection stores normalized positions in
    # float32. Account only for its final normalization round-off, not another
    # behavioral tolerance beyond a quarter tile.
    outside = position_errors > (
        ACTOR_POSITION_TOLERANCE_TILES + _POSITION_FLOAT32_RESIDUE_TILES
    )
    if bool(outside.any().item()):
        mismatch = torch.nonzero(outside, as_tuple=False)[0]
        position_index = tuple(int(part) for part in mismatch.tolist())
        feature_index = position_index[-1]
        full_index = (*position_index[:-1], feature_index)
        return (
            ProjectedGymTransitionDivergence(
                "actor.entity_features",
                full_index,
                _value(expected, full_index),
                _value(actual, full_index),
                "projected position differs by more than 0.25 tile",
            ),
            maximum,
        )
    return None, maximum


def compare_projected_gym_transitions(
    expected: ProjectedGymTransition,
    actual: ProjectedGymTransition,
) -> ProjectedGymTransitionComparison:
    """Compare one paired projected transition without claiming simulator parity."""

    mask_version = expected.public_action_mask_contract_version
    if mask_version != actual.public_action_mask_contract_version:
        contract_divergence = ProjectedGymTransitionDivergence(
            "public_action_mask_contract_version",
            None,
            mask_version,
            actual.public_action_mask_contract_version,
            "contract mismatch",
        )
        return ProjectedGymTransitionComparison(
            contract_divergence, 0.0, mask_version, False, ()
        )

    for name in ("entity_ids", "entity_mask", "hand_ids", "global_features"):
        exact_divergence = _first_exact_divergence(
            f"actor.{name}",
            getattr(expected.actor, name),
            getattr(actual.actor, name),
        )
        if exact_divergence is not None:
            return ProjectedGymTransitionComparison(
                exact_divergence, 0.0, mask_version, False, ()
            )

    feature_divergence, maximum_position_error = _actor_feature_comparison(
        expected.actor.entity_features,
        actual.actor.entity_features,
    )
    if feature_divergence is not None:
        return ProjectedGymTransitionComparison(
            feature_divergence, maximum_position_error, mask_version, False, ()
        )

    expected_mask = expected.public_action_masks
    actual_mask = actual.public_action_masks
    if (expected_mask is None) != (actual_mask is None):
        mask_presence_divergence = ProjectedGymTransitionDivergence(
            "public_action_masks",
            None,
            expected_mask is not None,
            actual_mask is not None,
            "mask presence mismatch",
        )
        return ProjectedGymTransitionComparison(
            mask_presence_divergence,
            maximum_position_error,
            mask_version,
            False,
            (),
        )
    if expected_mask is not None and actual_mask is not None:
        mask_divergence = _first_exact_divergence(
            "public_action_masks", expected_mask, actual_mask
        )
        if mask_divergence is not None:
            return ProjectedGymTransitionComparison(
                mask_divergence, maximum_position_error, mask_version, False, ()
            )

    critic_compared = expected.critic is not None and actual.critic is not None
    if (expected.critic is None) != (actual.critic is None):
        critic_presence_divergence = ProjectedGymTransitionDivergence(
            "critic",
            None,
            expected.critic is not None,
            actual.critic is not None,
            "critic presence mismatch",
        )
        return ProjectedGymTransitionComparison(
            critic_presence_divergence,
            maximum_position_error,
            mask_version,
            False,
            (),
        )
    if expected.critic is not None and actual.critic is not None:
        for descriptor in fields(expected.critic):
            critic_divergence = _first_exact_divergence(
                f"critic.{descriptor.name}",
                getattr(expected.critic, descriptor.name),
                getattr(actual.critic, descriptor.name),
            )
            if critic_divergence is not None:
                return ProjectedGymTransitionComparison(
                    critic_divergence,
                    maximum_position_error,
                    mask_version,
                    True,
                    (),
                )

    for name in (
        "action_success",
        "rewards",
        "done",
        "winner",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
    ):
        transition_divergence = _first_exact_divergence(
            name, getattr(expected, name), getattr(actual, name)
        )
        if transition_divergence is not None:
            return ProjectedGymTransitionComparison(
                transition_divergence,
                maximum_position_error,
                mask_version,
                critic_compared,
                (),
            )

    expected_recurrent = expected.recurrent_inputs or {}
    actual_recurrent = actual.recurrent_inputs or {}
    expected_names = tuple(sorted(expected_recurrent))
    actual_names = tuple(sorted(actual_recurrent))
    if expected_names != actual_names:
        recurrent_presence_divergence = ProjectedGymTransitionDivergence(
            "recurrent_inputs.keys",
            None,
            expected_names,
            actual_names,
            "recurrent input presence mismatch",
        )
        return ProjectedGymTransitionComparison(
            recurrent_presence_divergence,
            maximum_position_error,
            mask_version,
            critic_compared,
            (),
        )
    for name in expected_names:
        recurrent_divergence = _first_exact_divergence(
            f"recurrent_inputs.{name}",
            expected_recurrent[name],
            actual_recurrent[name],
        )
        if recurrent_divergence is not None:
            return ProjectedGymTransitionComparison(
                recurrent_divergence,
                maximum_position_error,
                mask_version,
                critic_compared,
                expected_names,
            )

    return ProjectedGymTransitionComparison(
        None,
        maximum_position_error,
        mask_version,
        critic_compared,
        expected_names,
    )


def project_python_gym_transition(
    battles: Sequence[BattleState],
    *,
    structured_builder: StructuredObservationBuilder,
    action_success: TensorLike,
    rewards: TensorLike,
    done: TensorLike,
    winner: TensorLike,
    previous_actions: TensorLike,
    previous_rewards: TensorLike,
    episode_starts: TensorLike,
    public_action_masks: TensorLike | None = None,
    public_action_mask_contract_version: int | None = None,
    include_privileged_critic: bool = False,
    recurrent_inputs: Mapping[str, TensorLike] | None = None,
) -> ProjectedGymTransition:
    """Project a Python-oracle batch through the existing structured builder."""

    if not battles:
        raise ValueError("at least one Python battle is required")
    projected = [
        [structured_builder.build(battle, seat) for seat in range(2)]
        for battle in battles
    ]

    def stack(name: str) -> torch.Tensor:
        return torch.from_numpy(
            np.stack(
                [
                    np.stack([getattr(by_seat[seat], name) for seat in range(2)])
                    for by_seat in projected
                ]
            )
        )

    actor = TensorPublicStructuredObservation(
        entity_ids=stack("entity_ids"),
        entity_features=stack("entity_features"),
        entity_mask=stack("entity_mask"),
        hand_ids=stack("hand_ids"),
        global_features=stack("global_features"),
    )
    critic = (
        TensorPrivilegedCriticObservation(
            entity_ids=stack("critic_entity_ids"),
            entity_features=stack("critic_entity_features"),
            entity_mask=stack("critic_entity_mask"),
            card_ids=stack("critic_card_ids"),
            global_features=stack("critic_global_features"),
        )
        if include_privileged_critic
        else None
    )
    return ProjectedGymTransition(
        actor=actor,
        critic=critic,
        public_action_masks=public_action_masks,
        public_action_mask_contract_version=public_action_mask_contract_version,
        action_success=action_success,
        rewards=rewards,
        done=done,
        winner=winner,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=episode_starts,
        recurrent_inputs=recurrent_inputs,
    )


def project_resident_gym_transition(
    projector: ResidentOutputProjector,
    *,
    action_success: TensorLike,
    rewards: TensorLike,
    done: TensorLike,
    winner: TensorLike,
    previous_actions: TensorLike,
    previous_rewards: TensorLike,
    episode_starts: TensorLike,
    public_action_masks: TensorLike | None = None,
    public_action_mask_contract_version: int | None = None,
    include_privileged_critic: bool = False,
    recurrent_inputs: Mapping[str, TensorLike] | None = None,
) -> ProjectedGymTransition:
    """Project a resident batch through its already-bound output projector."""

    projected = projector.project_all(
        include_privileged_critic=include_privileged_critic
    )
    return ProjectedGymTransition(
        actor=projected.public_structured,
        critic=projected.privileged_critic,
        public_action_masks=public_action_masks,
        public_action_mask_contract_version=public_action_mask_contract_version,
        action_success=action_success,
        rewards=rewards,
        done=done,
        winner=winner,
        previous_actions=previous_actions,
        previous_rewards=previous_rewards,
        episode_starts=episode_starts,
        recurrent_inputs=recurrent_inputs,
    )


__all__ = [
    "ACTOR_POSITION_TOLERANCE_TILES",
    "OUTSIDE_POLICY_TRANSITION_SCOPE",
    "PROJECTED_GYM_TRANSITION_PROFILE",
    "PUBLIC_ACTION_MASK_CONTRACT_V2",
    "ProjectedGymTransition",
    "ProjectedGymTransitionComparison",
    "ProjectedGymTransitionDivergence",
    "compare_projected_gym_transitions",
    "project_python_gym_transition",
    "project_resident_gym_transition",
]
