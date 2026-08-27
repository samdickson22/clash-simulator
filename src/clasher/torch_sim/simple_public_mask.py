"""Tensor-native public-action-mask-v2 provider for the practical Gym.

The hot path consumes only :class:`TensorPublicStructuredObservation`. Card
semantics and typed token identities are explicit setup inputs; simulator
legality, critic state, labels, and Python game objects are not accepted by the
runtime API. This keeps the provider model-neutral and CUDA-capture compatible.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any, Final

import torch

from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.simple_tensor_collector import (
    SimplePublicActionMaskV2,
    SimpleTensorMaskRequest,
)

from .policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from .resident_outputs import TensorPublicStructuredObservation

SIMPLE_PUBLIC_MASK_SEMANTICS_ID: Final = (
    "public-action-mask-v2/tensor-actor-projection-v2"
)
SIMPLE_PUBLIC_MASK_SCHEMA: Final = "clasher.simple-public-mask.tensor-v2"
SIMPLE_PUBLIC_MASK_ACTIONS: Final = NUM_HAND_SLOTS * NUM_TILES + 2
SIMPLE_PUBLIC_MASK_NO_OP: Final = NUM_HAND_SLOTS * NUM_TILES
SIMPLE_PUBLIC_MASK_ABILITY: Final = SIMPLE_PUBLIC_MASK_NO_OP + 1


class SimplePublicMaskContractError(ValueError):
    """Raised at setup when typed public-mask metadata is incomplete."""


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _tensor_digest(
    token_keys: Sequence[str], tensors: Mapping[str, torch.Tensor]
) -> str:
    digest = hashlib.sha256()
    digest.update("\0".join(token_keys).encode("utf-8"))
    for name in sorted(tensors):
        tensor = tensors[name].detach().contiguous()
        if tensor.device.type != "cpu":
            raise SimplePublicMaskContractError(
                "lookup digest must be compiled from CPU tensors"
            )
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(str(tuple(tensor.shape)).encode("ascii"))
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def _cpu_tensor(
    value: torch.Tensor | Sequence[bool] | Sequence[int] | Sequence[float],
    *,
    dtype: torch.dtype,
) -> torch.Tensor:
    tensor = torch.as_tensor(value, dtype=dtype)
    if tensor.device.type != "cpu":
        raise SimplePublicMaskContractError(
            "compile lookup metadata on CPU, then call tables.to(device)"
        )
    return tensor.contiguous()


@dataclass(frozen=True)
class SimplePublicMaskTypedTables:
    """Immutable typed lookup tables for public-mask-v2 evaluation.

    The token vocabulary is shared by hand and visible entity projections.
    Playable hand rows must use ``card_action:`` keys. Every non-reserved token
    must be namespaced so Hero/Evolution variants cannot silently collapse to a
    bare or base-family identity.
    """

    token_keys: tuple[str, ...]
    hand_playable: torch.Tensor
    elixir_cost: torch.Tensor
    is_spell: torch.Tensor
    non_rolling_spell: torch.Tensor
    is_building: torch.Tensor
    can_deploy_enemy_side: torch.Tensor
    deploy_margin_tiles: torch.Tensor
    deploy_radius_tiles: torch.Tensor
    blocker_radius_tiles: torch.Tensor
    ability_supported: torch.Tensor
    ability_elixir_cost: torch.Tensor
    tile_center_x: torch.Tensor
    tile_center_y: torch.Tensor
    non_blocked_tiles: torch.Tensor
    base_deploy_zone: torch.Tensor
    left_tower_extension: torch.Tensor
    right_tower_extension: torch.Tensor
    lookup_digest: str
    semantics_id: str
    semantics: Mapping[str, Any]
    semantics_digest: str

    def __post_init__(self) -> None:
        token_count = len(self.token_keys)
        if token_count < 2 or self.token_keys[:2] != ("<pad>", "<unknown>"):
            raise SimplePublicMaskContractError(
                "token_keys must begin with <pad>, <unknown>"
            )
        for token in self.token_keys[2:]:
            namespace, separator, identity = token.partition(":")
            if not separator or not namespace or not identity:
                raise SimplePublicMaskContractError(
                    f"non-reserved token is not explicitly typed: {token!r}"
                )
        token_fields = (
            "hand_playable",
            "elixir_cost",
            "is_spell",
            "non_rolling_spell",
            "is_building",
            "can_deploy_enemy_side",
            "deploy_margin_tiles",
            "deploy_radius_tiles",
            "blocker_radius_tiles",
            "ability_supported",
            "ability_elixir_cost",
        )
        expected_dtypes = {
            "hand_playable": torch.bool,
            "elixir_cost": torch.float64,
            "is_spell": torch.bool,
            "non_rolling_spell": torch.bool,
            "is_building": torch.bool,
            "can_deploy_enemy_side": torch.bool,
            "deploy_margin_tiles": torch.int64,
            "deploy_radius_tiles": torch.float64,
            "blocker_radius_tiles": torch.float64,
            "ability_supported": torch.bool,
            "ability_elixir_cost": torch.float64,
            "tile_center_x": torch.float64,
            "tile_center_y": torch.float64,
            "non_blocked_tiles": torch.bool,
            "base_deploy_zone": torch.bool,
            "left_tower_extension": torch.bool,
            "right_tower_extension": torch.bool,
        }
        device: torch.device | None = None
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if not isinstance(value, torch.Tensor):
                continue
            if device is None:
                device = value.device
            elif value.device != device:
                raise SimplePublicMaskContractError(
                    "all public-mask lookup tensors must share one device"
                )
            expected_dtype = expected_dtypes.get(descriptor.name)
            if expected_dtype is not None and value.dtype != expected_dtype:
                raise SimplePublicMaskContractError(
                    f"{descriptor.name} must use {expected_dtype}"
                )
        for name in token_fields:
            if tuple(getattr(self, name).shape) != (token_count,):
                raise SimplePublicMaskContractError(
                    f"{name} must have shape [token_count]"
                )
        for name in (
            "tile_center_x",
            "tile_center_y",
            "non_blocked_tiles",
            "base_deploy_zone",
            "left_tower_extension",
            "right_tower_extension",
        ):
            if tuple(getattr(self, name).shape) != (NUM_TILES,):
                raise SimplePublicMaskContractError(
                    f"{name} must have shape [{NUM_TILES}]"
                )
        for token, playable in zip(self.token_keys, self.hand_playable.tolist()):
            if playable and not token.startswith("card_action:"):
                raise SimplePublicMaskContractError(
                    f"playable hand token is not card_action typed: {token!r}"
                )
        supported_ability = self.ability_supported
        if bool((supported_ability & self.hand_playable).any()):
            raise SimplePublicMaskContractError(
                "ability-supported token must identify an entity, not a hand action"
            )
        invalid_ability_cost = supported_ability & (
            (self.ability_elixir_cost <= 0.0) | (self.ability_elixir_cost > 10.0)
        )
        if bool(invalid_ability_cost.any()):
            raise SimplePublicMaskContractError(
                "supported ability cost must be in (0, 10]"
            )
        if bool(((~supported_ability) & (self.ability_elixir_cost != 0.0)).any()):
            raise SimplePublicMaskContractError(
                "unsupported ability tokens must have zero cost"
            )
        if self.semantics.get("contract_version") != PUBLIC_ACTION_MASK_CONTRACT_V2:
            raise SimplePublicMaskContractError("public-mask contract v2 is required")
        if hashlib.sha256(_canonical_json(self.semantics)).hexdigest() != (
            self.semantics_digest
        ):
            raise SimplePublicMaskContractError("semantics digest mismatch")

    @property
    def device(self) -> torch.device:
        return self.hand_playable.device

    @classmethod
    def compile(
        cls,
        *,
        token_keys: Sequence[str],
        hand_playable: torch.Tensor | Sequence[bool],
        elixir_cost: torch.Tensor | Sequence[float],
        is_spell: torch.Tensor | Sequence[bool],
        non_rolling_spell: torch.Tensor | Sequence[bool],
        is_building: torch.Tensor | Sequence[bool],
        can_deploy_enemy_side: torch.Tensor | Sequence[bool],
        deploy_margin_tiles: torch.Tensor | Sequence[int],
        deploy_radius_tiles: torch.Tensor | Sequence[float],
        blocker_radius_tiles: torch.Tensor | Sequence[float],
        ability_supported: torch.Tensor | Sequence[bool],
        ability_elixir_cost: torch.Tensor | Sequence[float],
        blocked_tiles: Sequence[tuple[int, int]],
        authority: str,
        semantics_id: str = SIMPLE_PUBLIC_MASK_SEMANTICS_ID,
    ) -> SimplePublicMaskTypedTables:
        """Compile explicit typed lookup inputs into immutable CPU tables."""

        typed_keys = tuple(str(value) for value in token_keys)
        token_tensors = {
            "hand_playable": _cpu_tensor(hand_playable, dtype=torch.bool),
            "elixir_cost": _cpu_tensor(elixir_cost, dtype=torch.float64),
            "is_spell": _cpu_tensor(is_spell, dtype=torch.bool),
            "non_rolling_spell": _cpu_tensor(non_rolling_spell, dtype=torch.bool),
            "is_building": _cpu_tensor(is_building, dtype=torch.bool),
            "can_deploy_enemy_side": _cpu_tensor(
                can_deploy_enemy_side, dtype=torch.bool
            ),
            "deploy_margin_tiles": _cpu_tensor(deploy_margin_tiles, dtype=torch.int64),
            "deploy_radius_tiles": _cpu_tensor(
                deploy_radius_tiles, dtype=torch.float64
            ),
            "blocker_radius_tiles": _cpu_tensor(
                blocker_radius_tiles, dtype=torch.float64
            ).clamp_min(0.5),
            "ability_supported": _cpu_tensor(ability_supported, dtype=torch.bool),
            "ability_elixir_cost": _cpu_tensor(
                ability_elixir_cost, dtype=torch.float64
            ),
        }
        lookup_digest = _tensor_digest(typed_keys, token_tensors)
        tile_index = torch.arange(NUM_TILES, dtype=torch.int64)
        tile_x = tile_index % BOARD_WIDTH
        tile_y = tile_index // BOARD_WIDTH
        non_blocked = torch.ones(NUM_TILES, dtype=torch.bool)
        for x, y in blocked_tiles:
            if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                non_blocked[y * BOARD_WIDTH + x] = False
        grid_tensors = {
            "tile_center_x": tile_x.to(torch.float64) + 0.5,
            "tile_center_y": tile_y.to(torch.float64) + 0.5,
            "non_blocked_tiles": non_blocked,
            "base_deploy_zone": (
                ((tile_y >= 1) & (tile_y < 15))
                | ((tile_x >= 6) & (tile_x < 12) & (tile_y < 6))
            ),
            "left_tower_extension": ((tile_x < 9) & (tile_y >= 17) & (tile_y < 21)),
            "right_tower_extension": ((tile_x >= 9) & (tile_y >= 17) & (tile_y < 21)),
        }
        semantics: Mapping[str, Any] = {
            "schema": SIMPLE_PUBLIC_MASK_SCHEMA,
            "contract_version": PUBLIC_ACTION_MASK_CONTRACT_V2,
            "semantics_id": semantics_id,
            "authority": str(authority),
            "inputs": "simple-actor-projection-only",
            "uses_critic": False,
            "uses_simulator_legal_mask": False,
            "uses_labels": False,
            "typed_tokens_required": True,
            "ability_policy": "actor-visible-supported-champion-v1",
            "ability_inputs": (
                "own-visible-live-typed-entity,deploy-ready,elixir,"
                "cooldown-ready,duration-ready"
            ),
            "ability_owner_selection": "exactly-one-supported-own-live-entity",
            "ability_multiple_owner_policy": (
                "fail-closed-without-public-stable-owner-id"
            ),
            "ability_stun_policy": "not-a-legality-gate",
            "canonical_lane_globals": True,
            "numeric_profile": "float64-authoritative-comparison-v1",
            "lookup_digest": lookup_digest,
            "token_count": len(typed_keys),
        }
        return cls(
            token_keys=typed_keys,
            **token_tensors,
            **grid_tensors,
            lookup_digest=lookup_digest,
            semantics_id=semantics_id,
            semantics=semantics,
            semantics_digest=hashlib.sha256(_canonical_json(semantics)).hexdigest(),
        )

    def to(self, device: str | torch.device) -> SimplePublicMaskTypedTables:
        """Move immutable tables before entering a CUDA capture or hot loop."""

        target = torch.device(device)
        if target.type == "cuda" and target.index is None:
            target = torch.device("cuda", torch.cuda.current_device())
        values: dict[str, Any] = {}
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            values[descriptor.name] = (
                value.to(device=target) if isinstance(value, torch.Tensor) else value
            )
        return type(self)(**values)


@dataclass(frozen=True)
class SimplePublicMaskV2Result:
    """One public-mask-v2 boundary and its stable semantics metadata."""

    masks: torch.Tensor
    semantics_id: str
    semantics: Mapping[str, Any]
    semantics_digest: str
    contract_version: int = PUBLIC_ACTION_MASK_CONTRACT_V2


class SimplePublicMaskV2Provider:
    """Pure Torch mask evaluation over the actor projection."""

    def __init__(self, tables: SimplePublicMaskTypedTables) -> None:
        self.tables = tables

    def build(
        self, actor: TensorPublicStructuredObservation
    ) -> SimplePublicMaskV2Result:
        """Build masks without host synchronization or privileged inputs."""

        tables = self.tables
        if actor.hand_ids.device != tables.device:
            raise SimplePublicMaskContractError(
                "actor and public-mask tables must share one device"
            )
        if actor.hand_ids.ndim != 3 or actor.hand_ids.shape[1:] != (2, 5):
            raise SimplePublicMaskContractError("actor hand_ids must be [batch, 2, 5]")
        if actor.entity_ids.ndim != 3 or actor.entity_ids.shape[:2] != (
            actor.hand_ids.shape[0],
            2,
        ):
            raise SimplePublicMaskContractError(
                "actor entity_ids must begin with [batch, 2]"
            )
        if actor.entity_mask.shape != actor.entity_ids.shape:
            raise SimplePublicMaskContractError("actor entity mask shape mismatch")
        if actor.entity_features.shape[:3] != actor.entity_ids.shape:
            raise SimplePublicMaskContractError("actor entity feature shape mismatch")
        if actor.entity_features.shape[-1] <= 5:
            raise SimplePublicMaskContractError("actor entity features are incomplete")
        if actor.global_features.shape[:2] != actor.hand_ids.shape[:2]:
            raise SimplePublicMaskContractError("actor global feature shape mismatch")
        if actor.global_features.shape[-1] <= 15:
            raise SimplePublicMaskContractError("actor global features are incomplete")

        token_count = len(tables.token_keys)
        hand = actor.hand_ids[..., :NUM_HAND_SLOTS]
        safe_hand = hand.clamp(0, token_count - 1)
        known_hand = (hand > 0) & (hand < token_count)
        valid_hand = known_hand & tables.hand_playable[safe_hand]
        elixir = actor.global_features[..., 5].to(torch.float64) * 10.0
        affordable = tables.elixir_cost[safe_hand] <= elixir[..., None] + 1.0e-6

        left_dead = actor.global_features[..., 11] <= 1.0e-4
        right_dead = actor.global_features[..., 12] <= 1.0e-4
        zone = tables.base_deploy_zone.view(1, 1, NUM_TILES).expand(*hand.shape[:2], -1)
        zone = zone | (
            left_dead[..., None] & tables.left_tower_extension.view(1, 1, -1)
        )
        zone = zone | (
            right_dead[..., None] & tables.right_tower_extension.view(1, 1, -1)
        )
        unrestricted = (
            tables.non_rolling_spell[safe_hand]
            | (tables.can_deploy_enemy_side[safe_hand])
        )
        non_blocked = tables.non_blocked_tiles.view(1, 1, 1, -1)
        candidates = torch.where(
            unrestricted[..., None],
            non_blocked,
            zone[:, :, None, :] & non_blocked,
        )

        margin = tables.deploy_margin_tiles[safe_hand]
        tile_x = tables.tile_center_x.view(1, 1, 1, -1)
        within_margin = (margin[..., None] == 0) | (
            (tile_x >= margin[..., None]) & (tile_x < BOARD_WIDTH - margin[..., None])
        )

        entity_token = actor.entity_ids
        safe_entity = entity_token.clamp(0, token_count - 1)
        blocker = (
            actor.entity_mask
            & (actor.entity_features[..., 5] > 0.5)
            & (entity_token >= 0)
            & (entity_token < token_count)
        )
        blocker_x = actor.entity_features[..., 0].to(torch.float64) * BOARD_WIDTH
        blocker_y = actor.entity_features[..., 1].to(torch.float64) * BOARD_HEIGHT
        blocker_radius = tables.blocker_radius_tiles[safe_entity]
        blocker_half = (
            torch.clamp(
                torch.ceil(torch.clamp(blocker_radius, min=0.0) * 2.0) + 1.0,
                min=1.0,
            )
            / 2.0
            + 0.5
        )
        dx = torch.abs(
            tables.tile_center_x.view(1, 1, 1, NUM_TILES, 1)
            - blocker_x[:, :, None, None, :]
        )
        dy = torch.abs(
            tables.tile_center_y.view(1, 1, 1, NUM_TILES, 1)
            - blocker_y[:, :, None, None, :]
        )
        blocker_plane = blocker[:, :, None, None, :]
        building_half = (
            torch.clamp(
                torch.ceil(
                    torch.clamp(tables.deploy_radius_tiles[safe_hand], min=0.0) * 2.0
                )
                + 1.0,
                min=1.0,
            )
            / 2.0
        )
        building_occupied = (
            (dx < building_half[..., None, None] + blocker_half[:, :, None, None, :])
            & (dy < building_half[..., None, None] + blocker_half[:, :, None, None, :])
            & blocker_plane
        ).any(dim=-1)
        troop_circle = (
            dx.square() + dy.square()
            < (
                tables.deploy_radius_tiles[safe_hand][..., None, None]
                + blocker_radius[:, :, None, None, :]
            ).square()
        )
        troop_square = (dx < blocker_half[:, :, None, None, :]) & (
            dy < blocker_half[:, :, None, None, :]
        )
        troop_occupied = ((troop_circle | troop_square) & blocker_plane).any(dim=-1)
        occupied = torch.where(
            tables.is_building[safe_hand][..., None],
            building_occupied,
            troop_occupied,
        )
        occupied &= ~tables.is_spell[safe_hand][..., None]

        placements = (
            candidates
            & within_margin
            & ~occupied
            & valid_hand[..., None]
            & affordable[..., None]
        )
        masks = torch.zeros(
            (*hand.shape[:2], SIMPLE_PUBLIC_MASK_ACTIONS),
            dtype=torch.bool,
            device=tables.device,
        )
        masks[..., :SIMPLE_PUBLIC_MASK_NO_OP] = placements.flatten(2)
        masks[..., SIMPLE_PUBLIC_MASK_NO_OP] = True

        ability_candidate = (
            actor.entity_mask
            & (actor.entity_features[..., 2] > 0.5)
            & (actor.entity_features[..., 9] > 0.0)
            & (actor.entity_features[..., 12] <= 0.5)
            & (entity_token > 0)
            & (entity_token < token_count)
            & tables.ability_supported[safe_entity]
        )
        ability_candidate_count = ability_candidate.to(torch.int64).sum(dim=-1)
        ability_cost = torch.where(
            ability_candidate,
            tables.ability_elixir_cost[safe_entity],
            torch.zeros_like(blocker_radius),
        ).sum(dim=-1)
        ability_ready = (
            (ability_candidate_count == 1)
            & (actor.global_features[..., 14] <= 1.0e-4)
            & (actor.global_features[..., 15] <= 1.0e-4)
            & (ability_cost <= elixir + 1.0e-6)
        )
        masks[..., SIMPLE_PUBLIC_MASK_ABILITY] = ability_ready
        return SimplePublicMaskV2Result(
            masks=masks,
            semantics_id=tables.semantics_id,
            semantics=tables.semantics,
            semantics_digest=tables.semantics_digest,
        )


class SimpleCollectorPublicMaskV2Provider:
    """Collector protocol adapter that reads only ``request.observation.actor``."""

    def __init__(self, provider: SimplePublicMaskV2Provider) -> None:
        self.provider = provider

    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        result = self.provider.build(request.observation.actor)
        return SimplePublicActionMaskV2(
            masks=result.masks,
            semantics_id=result.semantics_id,
            semantics=result.semantics,
            contract_version=result.contract_version,
        )


__all__ = [
    "SIMPLE_PUBLIC_MASK_ABILITY",
    "SIMPLE_PUBLIC_MASK_ACTIONS",
    "SIMPLE_PUBLIC_MASK_NO_OP",
    "SIMPLE_PUBLIC_MASK_SCHEMA",
    "SIMPLE_PUBLIC_MASK_SEMANTICS_ID",
    "SimpleCollectorPublicMaskV2Provider",
    "SimplePublicMaskContractError",
    "SimplePublicMaskTypedTables",
    "SimplePublicMaskV2Provider",
    "SimplePublicMaskV2Result",
]
