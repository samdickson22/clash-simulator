"""Fresh-training reward contract for the practical tensor Gym.

``objective-v1-gamma-v1`` keeps the public, win-condition-oriented potential
used by the newer policy stack, but applies it as policy-invariant shaping at
one *policy decision* boundary::

    gamma * Phi(s_next) - Phi(s)

Terminal transitions use an absorbing state with ``Phi=0`` and add the game
result once.  The implementation is a pure tensor transform over dense Gym
state: it has no event ledger, action attribution, card-name dispatch, elixir
leak incentive, or invalid-action shaping.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Final

import torch

from .simple_outcomes import (
    FAST_TOWER_KING,
    FAST_TOWER_SLOT_COUNT,
    FAST_TOWER_SLOTS_PER_PLAYER,
    crown_tower_hp,
    crowns_for_players,
)
from .simple_state import FastGymState

SIMPLE_REWARD_V2_CONTRACT_ID: Final = "objective-v1-gamma-v1"
SIMPLE_REWARD_V2_SCHEMA_VERSION: Final = 1
_TIEBREAK_FIXED_POINT_SCALE: Final = 1_000


class SimpleRewardV2ContractError(ValueError):
    """Raised when reward inputs or persisted metadata are incompatible."""


@dataclass(frozen=True)
class SimpleRewardV2Config:
    """Immutable numeric semantics for fresh-policy Gym training.

    ``gamma`` is the PPO discount for one policy transition, not a native
    50 ms simulator-tick discount.  A resumed run must match the complete
    serialized spec and digest; matching only the human-readable ID is not
    sufficient.
    """

    gamma: float
    crown_weight: float = 0.55
    princess_pressure_weight: float = 0.25
    king_pressure_weight: float = 0.10
    tiebreak_edge_weight: float = 0.10
    early_king_chip_penalty_weight: float = 0.20
    potential_clip: float = 1.50
    terminal_weight: float = 1.00

    def __post_init__(self) -> None:
        numeric = asdict(self)
        if not all(math.isfinite(float(value)) for value in numeric.values()):
            raise ValueError("simple reward v2 values must be finite")
        if not 0.0 < float(self.gamma) <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        if (
            min(
                self.crown_weight,
                self.princess_pressure_weight,
                self.king_pressure_weight,
                self.tiebreak_edge_weight,
                self.early_king_chip_penalty_weight,
                self.potential_clip,
                self.terminal_weight,
            )
            < 0.0
        ):
            raise ValueError("simple reward v2 weights must be non-negative")
        if self.potential_clip == 0.0:
            raise ValueError("potential_clip must be positive")

    def to_spec(self) -> dict[str, Any]:
        """Return the complete JSON-safe contract hashed into checkpoints."""

        return {
            "contract_id": SIMPLE_REWARD_V2_CONTRACT_ID,
            "schema_version": SIMPLE_REWARD_V2_SCHEMA_VERSION,
            **asdict(self),
            "evaluation_boundary": "policy-decision",
            "terminal_potential": "absorbing-zero",
            "zero_sum": True,
            "invalid_action_penalty": 0.0,
            "elixir_leak_penalty_scale": 0.0,
            "king_activation_inference": (
                "live-king-and-hp-below-initial-or-princess-destroyed-v1"
            ),
            "tiebreak_fixed_point_scale": _TIEBREAK_FIXED_POINT_SCALE,
        }


@dataclass(frozen=True)
class SimpleObjectiveV1Breakdown:
    """Batched player-zero potential components and clipped total."""

    crowns: torch.Tensor
    princess_pressure: torch.Tensor
    king_pressure: torch.Tensor
    tiebreak_edge: torch.Tensor
    early_king_penalty: torch.Tensor
    potential: torch.Tensor


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def simple_reward_v2_digest(config: SimpleRewardV2Config) -> str:
    """Return a stable SHA-256 digest of every reward semantic."""

    return hashlib.sha256(_canonical_json(config.to_spec()).encode("utf-8")).hexdigest()


def simple_reward_v2_metadata(config: SimpleRewardV2Config) -> dict[str, Any]:
    """Build the checkpoint/run metadata that must survive a resume."""

    spec = config.to_spec()
    return {
        "reward_contract_id": SIMPLE_REWARD_V2_CONTRACT_ID,
        "reward_contract_digest": simple_reward_v2_digest(config),
        "reward_contract_spec": spec,
    }


def validate_simple_reward_v2_metadata(
    metadata: Mapping[str, Any],
    expected: SimpleRewardV2Config,
) -> None:
    """Fail closed unless persisted metadata exactly matches ``expected``."""

    required = (
        "reward_contract_id",
        "reward_contract_digest",
        "reward_contract_spec",
    )
    missing = [name for name in required if name not in metadata]
    if missing:
        raise SimpleRewardV2ContractError(
            f"missing simple reward v2 metadata: {', '.join(missing)}"
        )
    if metadata["reward_contract_id"] != SIMPLE_REWARD_V2_CONTRACT_ID:
        raise SimpleRewardV2ContractError("reward contract ID mismatch")
    persisted_spec = metadata["reward_contract_spec"]
    if not isinstance(persisted_spec, Mapping):
        raise SimpleRewardV2ContractError("reward contract spec must be a mapping")
    expected_spec = expected.to_spec()
    try:
        persisted_json = _canonical_json(persisted_spec)
    except (TypeError, ValueError) as exc:
        raise SimpleRewardV2ContractError(
            "reward contract spec is not canonical JSON"
        ) from exc
    if persisted_json != _canonical_json(expected_spec):
        raise SimpleRewardV2ContractError("reward contract spec mismatch")
    persisted_digest = metadata["reward_contract_digest"]
    if not isinstance(persisted_digest, str):
        raise SimpleRewardV2ContractError("reward contract digest must be a string")
    actual_persisted_digest = hashlib.sha256(persisted_json.encode("utf-8")).hexdigest()
    if persisted_digest != actual_persisted_digest:
        raise SimpleRewardV2ContractError("reward contract digest is corrupt")
    if persisted_digest != simple_reward_v2_digest(expected):
        raise SimpleRewardV2ContractError("reward contract digest mismatch")


def _validate_state_pair(
    pre_state: FastGymState,
    post_state: FastGymState,
    initial_tower_hp: torch.Tensor,
    done: torch.Tensor,
    winner: torch.Tensor,
) -> None:
    if pre_state.batch_size != post_state.batch_size:
        raise SimpleRewardV2ContractError("pre/post batch sizes differ")
    if pre_state.device != post_state.device:
        raise SimpleRewardV2ContractError("pre/post devices differ")
    if min(pre_state.max_entities, post_state.max_entities) < FAST_TOWER_SLOT_COUNT:
        raise SimpleRewardV2ContractError("pre/post state must contain six towers")
    batch = pre_state.batch_size
    if tuple(initial_tower_hp.shape) != (
        batch,
        2,
        FAST_TOWER_SLOTS_PER_PLAYER,
    ):
        raise SimpleRewardV2ContractError(
            "initial_tower_hp must have shape [batch, 2, 3]"
        )
    if initial_tower_hp.device != pre_state.device:
        raise SimpleRewardV2ContractError("initial_tower_hp device differs")
    if not initial_tower_hp.is_floating_point():
        raise SimpleRewardV2ContractError("initial_tower_hp must be floating point")
    if tuple(done.shape) != (batch,) or done.dtype != torch.bool:
        raise SimpleRewardV2ContractError("done must be bool [batch]")
    if tuple(winner.shape) != (batch,) or winner.dtype not in (
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
    ):
        raise SimpleRewardV2ContractError("winner must be integer [batch]")
    if done.device != pre_state.device or winner.device != pre_state.device:
        raise SimpleRewardV2ContractError("done/winner device differs")


def _objective_v1_breakdown_from_hp(
    tower_hp: torch.Tensor,
    initial_tower_hp: torch.Tensor,
    config: SimpleRewardV2Config,
) -> SimpleObjectiveV1Breakdown:
    initial = initial_tower_hp.to(dtype=tower_hp.dtype)
    start_princess = (0.5 * (initial[:, :, 0] + initial[:, :, 1])).clamp_min(1.0)
    left_fraction = (tower_hp[:, :, 0] / start_princess).clamp(0.0, 1.0)
    right_fraction = (tower_hp[:, :, 1] / start_princess).clamp(0.0, 1.0)
    princess_fraction = (0.5 * (left_fraction + right_fraction)).clamp(0.0, 1.0)
    king_fraction = (
        tower_hp[:, :, FAST_TOWER_KING]
        / initial[:, :, FAST_TOWER_KING].clamp_min(1.0e-6)
    ).clamp(0.0, 1.0)

    crowns_by_player = crowns_for_players(tower_hp)
    crown_edge = (
        crowns_by_player[:, 0].to(tower_hp.dtype)
        - crowns_by_player[:, 1].to(tower_hp.dtype)
    ) / 3.0
    princess_pressure = (1.0 - princess_fraction[:, 1]) - (
        1.0 - princess_fraction[:, 0]
    )

    princess_alive = (tower_hp[:, :, :FAST_TOWER_KING] > 0.0).sum(dim=2)
    king_alive = tower_hp[:, :, FAST_TOWER_KING] > 0.0
    king_activated = king_alive & (
        (tower_hp[:, :, FAST_TOWER_KING] < initial[:, :, FAST_TOWER_KING])
        | (princess_alive < 2)
    )

    def king_weight(owner: int) -> torch.Tensor:
        alive = princess_alive[:, owner]
        active = king_activated[:, owner]
        return torch.where(
            (alive == 2) & ~active,
            torch.zeros_like(king_fraction[:, owner]),
            torch.where(
                alive == 2,
                torch.full_like(king_fraction[:, owner], 0.05),
                torch.where(
                    alive == 1,
                    torch.full_like(king_fraction[:, owner], 0.25),
                    torch.full_like(king_fraction[:, owner], 0.60),
                ),
            ),
        )

    king_pressure = king_weight(1) * (1.0 - king_fraction[:, 1]) - king_weight(0) * (
        1.0 - king_fraction[:, 0]
    )

    standing = torch.where(
        tower_hp > 0.0,
        tower_hp,
        torch.full_like(tower_hp, torch.inf),
    )
    lowest = standing.amin(dim=2)
    lowest = torch.where(torch.isfinite(lowest), lowest, torch.zeros_like(lowest))
    lowest_fixed = torch.round(lowest * _TIEBREAK_FIXED_POINT_SCALE).to(torch.int64)
    tiebreak_scale = (
        initial.amax(dim=(1, 2)).clamp_min(1.0) * _TIEBREAK_FIXED_POINT_SCALE
    )
    tiebreak_edge = (lowest_fixed[:, 0] - lowest_fixed[:, 1]).to(
        tower_hp.dtype
    ) / tiebreak_scale

    early_king_penalty = torch.where(
        princess_alive[:, 1] == 2,
        1.0 - king_fraction[:, 1],
        torch.zeros_like(king_fraction[:, 1]),
    ) - torch.where(
        princess_alive[:, 0] == 2,
        1.0 - king_fraction[:, 0],
        torch.zeros_like(king_fraction[:, 0]),
    )

    potential = (
        config.crown_weight * crown_edge
        + config.princess_pressure_weight * princess_pressure
        + config.king_pressure_weight * king_pressure
        + config.tiebreak_edge_weight * tiebreak_edge
        - config.early_king_chip_penalty_weight * early_king_penalty
    ).clamp(-config.potential_clip, config.potential_clip)
    return SimpleObjectiveV1Breakdown(
        crowns=crown_edge,
        princess_pressure=princess_pressure,
        king_pressure=king_pressure,
        tiebreak_edge=tiebreak_edge,
        early_king_penalty=early_king_penalty,
        potential=potential,
    )


def simple_objective_v1_breakdown(
    state: FastGymState,
    initial_tower_hp: torch.Tensor,
    config: SimpleRewardV2Config,
) -> SimpleObjectiveV1Breakdown:
    """Compute the public ``objective-v1`` potential from dense tower state."""

    dummy_done = torch.zeros(state.batch_size, dtype=torch.bool, device=state.device)
    dummy_winner = torch.full(
        (state.batch_size,), -2, dtype=torch.int8, device=state.device
    )
    _validate_state_pair(state, state, initial_tower_hp, dummy_done, dummy_winner)
    return _objective_v1_breakdown_from_hp(
        crown_tower_hp(state), initial_tower_hp, config
    )


def simple_objective_v1_potential_from_tower_hp(
    tower_hp: torch.Tensor,
    initial_tower_hp: torch.Tensor,
    config: SimpleRewardV2Config,
) -> torch.Tensor:
    """Return objective-v1 potential directly from ``[batch, 2, 3]`` HP.

    Rollout collectors use this boundary to capture decision-level pre/post
    potentials without cloning the much larger mutable ``FastGymState``.
    """

    if tower_hp.ndim != 3 or tuple(tower_hp.shape[1:]) != (
        2,
        FAST_TOWER_SLOTS_PER_PLAYER,
    ):
        raise SimpleRewardV2ContractError("tower_hp must have shape [batch, 2, 3]")
    if tuple(initial_tower_hp.shape) != tuple(tower_hp.shape):
        raise SimpleRewardV2ContractError("initial_tower_hp must match tower_hp shape")
    if tower_hp.device != initial_tower_hp.device:
        raise SimpleRewardV2ContractError("tower HP devices differ")
    if not tower_hp.is_floating_point() or not initial_tower_hp.is_floating_point():
        raise SimpleRewardV2ContractError("tower HP tensors must be floating point")
    return _objective_v1_breakdown_from_hp(tower_hp, initial_tower_hp, config).potential


def simple_reward_v2_from_potentials(
    pre_potential: torch.Tensor,
    post_potential: torch.Tensor,
    done: torch.Tensor,
    winner: torch.Tensor,
    config: SimpleRewardV2Config,
) -> torch.Tensor:
    """Return objective-v1-gamma-v1 reward from decision potentials."""

    if pre_potential.ndim != 1 or post_potential.shape != pre_potential.shape:
        raise SimpleRewardV2ContractError(
            "pre/post potential must be matching [batch] tensors"
        )
    batch = int(pre_potential.shape[0])
    if tuple(done.shape) != (batch,) or done.dtype != torch.bool:
        raise SimpleRewardV2ContractError("done must be bool [batch]")
    if tuple(winner.shape) != (batch,) or winner.dtype not in (
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
    ):
        raise SimpleRewardV2ContractError("winner must be integer [batch]")
    if not pre_potential.is_floating_point() or not post_potential.is_floating_point():
        raise SimpleRewardV2ContractError("potentials must be floating point")
    if not (
        pre_potential.device == post_potential.device == done.device == winner.device
    ):
        raise SimpleRewardV2ContractError("reward tensors use different devices")
    shaped_p0 = torch.where(
        done,
        -pre_potential,
        config.gamma * post_potential - pre_potential,
    )
    terminal_sign = torch.where(
        winner == 0,
        torch.ones_like(shaped_p0),
        torch.where(
            winner == 1,
            -torch.ones_like(shaped_p0),
            torch.zeros_like(shaped_p0),
        ),
    )
    reward_p0 = shaped_p0 + (
        config.terminal_weight * terminal_sign * done.to(shaped_p0.dtype)
    )
    return torch.stack((reward_p0, -reward_p0), dim=1)


def simple_reward_v2(
    pre_state: FastGymState,
    post_state: FastGymState,
    initial_tower_hp: torch.Tensor,
    done: torch.Tensor,
    winner: torch.Tensor,
    config: SimpleRewardV2Config,
) -> torch.Tensor:
    """Return gamma-correct, terminal-absorbing rewards as ``[batch, 2]``.

    ``done`` means that this transition newly reached a terminal boundary.
    Callers must not replay a terminal transition; the rollout bridge already
    enforces reset-before-step for completed rows.
    """

    _validate_state_pair(pre_state, post_state, initial_tower_hp, done, winner)
    pre = simple_objective_v1_potential_from_tower_hp(
        crown_tower_hp(pre_state), initial_tower_hp, config
    )
    post = simple_objective_v1_potential_from_tower_hp(
        crown_tower_hp(post_state), initial_tower_hp, config
    )
    return simple_reward_v2_from_potentials(pre, post, done, winner, config)


__all__ = [
    "SIMPLE_REWARD_V2_CONTRACT_ID",
    "SIMPLE_REWARD_V2_SCHEMA_VERSION",
    "SimpleObjectiveV1Breakdown",
    "SimpleRewardV2Config",
    "SimpleRewardV2ContractError",
    "simple_objective_v1_breakdown",
    "simple_objective_v1_potential_from_tower_hp",
    "simple_reward_v2",
    "simple_reward_v2_digest",
    "simple_reward_v2_from_potentials",
    "simple_reward_v2_metadata",
    "validate_simple_reward_v2_metadata",
]
