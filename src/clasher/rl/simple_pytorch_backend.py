"""Isolated training adapter for the practical dense PyTorch Gym.

The simulator-facing legal mask and the actor-facing public mask are separate
contracts.  This module builds the latter only from projected public tensors,
adapts the recurrent policy without exposing simulator-private state, and
serializes the device-resident collector into the existing PPO rollout shape.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import torch

from clasher.arena import TileGrid
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.simple_reward_v2 import (
    SIMPLE_REWARD_V2_CONTRACT_ID,
    SimpleRewardV2Config,
    simple_reward_v2_metadata,
)
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_standard import (
    STANDARD_TIEBREAK_TICK,
    compile_standard_simple_setup,
)

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .model import ClasherPolicy, PolicyInputs
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .simple_tensor_collector import (
    SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
    SIMPLE_TENSOR_BACKEND_ID,
    SimplePublicActionMaskV2,
    SimpleTensorCollector,
    SimpleTensorDecisionBatch,
    SimpleTensorMaskRequest,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from .structured_obs import StructuredObservationBuilder

SIMPLE_PYTORCH_BACKEND: Final = "simple-pytorch"
SIMPLE_SUPPORTED_DECK_CONTRACT: Final = "clasher.simple_gym_supported_decks"
CURRENT_CLIENT_VOCABULARY_SCHEMA: Final = (
    "clasher.current_client.youtube_stable_vocabulary.v1"
)
DEFAULT_SIMPLE_SUPPORTED_DECKS: Final = Path(
    "training_decks/simple_gym_supported_v1.json"
)
DEFAULT_SIMPLE_TOKEN_VOCABULARY: Final = Path(
    "reports/current_client_youtube_stable_vocabulary_v1.json"
)


class SimplePytorchBackendError(RuntimeError):
    """Raised before collection when an integration contract is incomplete."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return _sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _read_json(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    try:
        raw = source.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SimplePytorchBackendError(f"cannot read {source}: {error}") from error
    if not isinstance(payload, dict):
        raise SimplePytorchBackendError(f"{source} must contain a JSON object")
    return payload, _sha256(raw)


@dataclass(frozen=True)
class CurrentClientTypedVocabulary:
    token_names: tuple[str, ...]
    token_by_key: Mapping[str, int]
    card_action_aliases: Mapping[str, str]
    ambiguous_card_action_aliases: frozenset[str]
    sha256: str

    @staticmethod
    def _normalize(label: str) -> str:
        return "".join(character for character in label.lower() if character.isalnum())

    def resolve(self, label: str, namespace: str) -> int:
        direct = self.token_by_key.get(f"{namespace}:{label}")
        if direct is not None:
            return int(direct)
        normalized = self._normalize(label)
        if normalized in self.ambiguous_card_action_aliases:
            return 0
        candidates: list[str] = []
        canonical = self.card_action_aliases.get(normalized)
        if canonical is not None:
            candidates.append(canonical)
        for candidate in candidates:
            token = self.token_by_key.get(f"{namespace}:{candidate}")
            if token is not None:
                return int(token)
        return 0


def load_current_client_typed_vocabulary(
    path: str | Path = DEFAULT_SIMPLE_TOKEN_VOCABULARY,
) -> CurrentClientTypedVocabulary:
    payload, digest = _read_json(path)
    if payload.get("schema") != CURRENT_CLIENT_VOCABULARY_SCHEMA:
        raise SimplePytorchBackendError("current-client vocabulary schema mismatch")
    counts = payload.get("counts")
    entries = payload.get("entries")
    aliases = payload.get("aliases")
    if not isinstance(counts, dict) or not isinstance(entries, list):
        raise SimplePytorchBackendError("current-client vocabulary is incomplete")
    if not isinstance(aliases, list):
        raise SimplePytorchBackendError("current-client aliases are missing")
    count = counts.get("actor_tokens_including_reserved")
    if not isinstance(count, int) or count < 2:
        raise SimplePytorchBackendError("invalid actor token count")
    names = [""] * count
    names[0] = "<pad>"
    names[1] = "<unknown>"
    token_by_key: dict[str, int] = {names[0]: 0, names[1]: 1}
    for row in entries:
        if not isinstance(row, dict) or row.get("actor_token_id") is None:
            continue
        token = row.get("actor_token_id")
        stable_key = row.get("stable_key")
        if (
            not isinstance(token, int)
            or not 2 <= token < count
            or not isinstance(stable_key, str)
            or not stable_key
            or names[token]
        ):
            raise SimplePytorchBackendError("invalid or duplicate actor token row")
        names[token] = stable_key
        token_by_key[stable_key] = token
    if any(not name for name in names):
        raise SimplePytorchBackendError("actor token IDs are not contiguous")
    action_aliases: dict[str, str] = {}
    ambiguous_aliases: set[str] = set()
    for row in aliases:
        if not isinstance(row, dict) or row.get("context") != "card_action":
            continue
        normalized = row.get("normalized_label")
        target = row.get("target_stable_key")
        if not isinstance(normalized, str) or not isinstance(target, str):
            raise SimplePytorchBackendError("invalid card-action alias row")
        namespace, separator, canonical = target.partition(":")
        if not separator or namespace != "card_action" or not canonical:
            raise SimplePytorchBackendError("card-action alias target is not typed")
        if normalized in ambiguous_aliases:
            continue
        previous = action_aliases.setdefault(normalized, canonical)
        if previous != canonical:
            action_aliases.pop(normalized, None)
            ambiguous_aliases.add(normalized)
    # Variant identity is mechanics-bearing. Its absence is a hard contract
    # failure; no base-family fallback is allowed here.
    for section in ("evolution_variants", "hero_variants"):
        rows = payload.get(section)
        if not isinstance(rows, list):
            raise SimplePytorchBackendError(f"{section} is missing")
        for row in rows:
            variant = row.get("variant") if isinstance(row, dict) else None
            if not isinstance(variant, str):
                raise SimplePytorchBackendError(f"invalid {section} row")
            if f"card_action:{variant}" not in token_by_key:
                raise SimplePytorchBackendError(
                    f"typed variant is absent from actor vocabulary: {variant}"
                )
    return CurrentClientTypedVocabulary(
        token_names=tuple(names),
        token_by_key=token_by_key,
        card_action_aliases=action_aliases,
        ambiguous_card_action_aliases=frozenset(ambiguous_aliases),
        sha256=digest,
    )


@dataclass(frozen=True)
class SimpleSupportedDeckArtifact:
    decks: tuple[tuple[str, ...], ...]
    public_cards: tuple[str, ...]
    sha256: str
    support_profile_sha256: str


def load_simple_supported_decks(
    path: str | Path = DEFAULT_SIMPLE_SUPPORTED_DECKS,
) -> SimpleSupportedDeckArtifact:
    payload, digest = _read_json(path)
    contract = payload.get("contract")
    profile = payload.get("support_profile")
    rows = payload.get("decks")
    if payload.get("schema_version") != 1 or not isinstance(contract, dict):
        raise SimplePytorchBackendError("supported-deck artifact schema mismatch")
    if contract.get("name") != SIMPLE_SUPPORTED_DECK_CONTRACT:
        raise SimplePytorchBackendError("supported-deck contract name mismatch")
    if contract.get("canonical_lane_globals") is not True:
        raise SimplePytorchBackendError("supported decks require canonical lanes")
    if contract.get("public_action_mask_contract_version") != 2:
        raise SimplePytorchBackendError("supported decks require public mask v2")
    if not isinstance(profile, dict) or not isinstance(rows, list) or not rows:
        raise SimplePytorchBackendError("supported-deck artifact is incomplete")
    public_cards = profile.get("supported_public_cards")
    profile_digest = profile.get("sha256")
    if not isinstance(public_cards, list) or not isinstance(profile_digest, str):
        raise SimplePytorchBackendError("supported-card profile is incomplete")
    supported = set(public_cards)
    decks: list[tuple[str, ...]] = []
    for index, row in enumerate(rows):
        cards = row.get("cards") if isinstance(row, dict) else None
        if (
            not isinstance(cards, list)
            or len(cards) != 8
            or len(set(cards)) != 8
            or any(not isinstance(card, str) or card not in supported for card in cards)
        ):
            raise SimplePytorchBackendError(
                f"supported-deck row {index} is invalid or out of profile"
            )
        decks.append(tuple(cards))
    return SimpleSupportedDeckArtifact(
        decks=tuple(decks),
        public_cards=tuple(str(name) for name in public_cards),
        sha256=digest,
        support_profile_sha256=profile_digest,
    )


class ReferenceSimplePublicMaskV2Adapter:
    """Host reference for trace-checking the tensor-native public mask."""

    def __init__(self, builder: StructuredObservationBuilder) -> None:
        self.builder = PublicActionMaskBuilder(builder)
        self.semantics: Mapping[str, Any] = {
            "schema": "clasher.simple-pytorch.public-mask-adapter.v1",
            "contract_version": PUBLIC_ACTION_MASK_CONTRACT_V2,
            "inputs": "projected-public-actor-only",
            "uses_expert_labels": False,
            "uses_privileged_critic": False,
            "uses_simulator_legal_mask": False,
            "canonical_lane_globals": True,
            "token_names_sha256": _sha256(
                "\0".join(builder.token_names).encode("utf-8")
            ),
        }

    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        actor = request.observation.actor
        entity_ids = actor.entity_ids.detach().cpu().numpy()
        entity_features = actor.entity_features.detach().cpu().numpy()
        entity_mask = actor.entity_mask.detach().cpu().numpy()
        hand_ids = actor.hand_ids.detach().cpu().numpy()
        global_features = actor.global_features.detach().cpu().numpy()
        batch, seats = hand_ids.shape[:2]
        rows: list[list[np.ndarray]] = []
        for batch_index in range(batch):
            seat_rows: list[np.ndarray] = []
            for seat in range(seats):
                visible = entity_mask[batch_index, seat]
                source = PublicActionMaskInput(
                    entity_ids=entity_ids[batch_index, seat],
                    entity_features=entity_features[batch_index, seat],
                    entity_mask=visible,
                    hand_ids=hand_ids[batch_index, seat],
                    global_features=global_features[batch_index, seat],
                    entity_id_confidence=visible.astype(np.float32, copy=False),
                    hand_id_confidence=np.ones(hand_ids.shape[-1], dtype=np.float32),
                    global_feature_confidence=np.ones(
                        global_features.shape[-1], dtype=np.float32
                    ),
                )
                seat_rows.append(self.builder.build(source))
            rows.append(seat_rows)
        masks = torch.as_tensor(
            np.asarray(rows, dtype=np.bool_),
            dtype=torch.bool,
            device=request.observation.legal_mask.device,
        )
        return SimplePublicActionMaskV2(
            masks=masks,
            semantics_id="public-action-mask-v2/actor-projection-v1",
            semantics=self.semantics,
        )


class SimplePublicMaskV2Adapter:
    """Tensor-native public-mask-v2 adapter over projected actor state.

    Card semantics are compiled once from the authoritative public builder.
    Runtime evaluation is fixed-shape Torch math and never consults labels,
    critic tensors, or the simulator legality mask.
    """

    def __init__(self, builder: StructuredObservationBuilder) -> None:
        self.builder = builder
        token_count = len(builder.token_names)
        definitions = builder.loader.load_card_definitions()
        tile_grid = TileGrid()

        valid = torch.zeros(token_count, dtype=torch.bool)
        cost = torch.zeros(token_count, dtype=torch.float64)
        is_spell = torch.zeros(token_count, dtype=torch.bool)
        non_rolling_spell = torch.zeros(token_count, dtype=torch.bool)
        is_building = torch.zeros(token_count, dtype=torch.bool)
        enemy_side = torch.zeros(token_count, dtype=torch.bool)
        margin = torch.zeros(token_count, dtype=torch.int64)
        deploy_radius = torch.full((token_count,), 0.5, dtype=torch.float64)
        building_half = torch.zeros(token_count, dtype=torch.float64)
        blocker_radius = torch.as_tensor(
            [float(value) * 3.0 for value in builder.card_stat_features[:, 12]],
            dtype=torch.float64,
        )
        blocker_radius.clamp_(min=0.5)

        for token in range(1, token_count):
            card_name = builder.card_name_for_token_id(token)
            if card_name is None:
                continue
            stats = builder.loader.get_card(card_name)
            if stats is None:
                continue
            raw_cost = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            if not math.isfinite(raw_cost):
                continue
            resolved = resolve_card_name(card_name, definitions)
            spell = resolved in SPELL_REGISTRY
            spell_object = SPELL_REGISTRY.get(resolved) if spell else None
            non_rolling = bool(
                spell
                and not tile_grid._requires_deploy_zone_spell(spell_object)
                and not getattr(spell_object, "requires_walkable_target", False)
            )
            building = bool(
                not spell
                and str(getattr(stats, "card_type", "") or "").lower()
                == "building"
            )
            radius = float(getattr(stats, "collision_radius", 0.5) or 0.5)
            valid[token] = True
            cost[token] = raw_cost
            is_spell[token] = spell
            non_rolling_spell[token] = non_rolling
            is_building[token] = building
            enemy_side[token] = bool(
                not spell and getattr(stats, "can_deploy_on_enemy_side", False)
            )
            margin[token] = int(getattr(stats, "deploy_w_tile_margin", 0) or 0)
            deploy_radius[token] = radius
            if building:
                building_half[token] = (
                    max(1, math.ceil(max(0.0, radius) * 2.0) + 1) / 2.0
                )

        tile_x = torch.arange(NUM_TILES, dtype=torch.int64) % BOARD_WIDTH
        tile_y = torch.arange(NUM_TILES, dtype=torch.int64) // BOARD_WIDTH
        center_x = tile_x.to(torch.float64) + 0.5
        center_y = tile_y.to(torch.float64) + 0.5
        non_blocked = torch.ones(NUM_TILES, dtype=torch.bool)
        for x, y in TileGrid.BLOCKED_TILES:
            if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT:
                non_blocked[y * BOARD_WIDTH + x] = False
        base_zone = (
            ((tile_y >= 1) & (tile_y < 15))
            | ((tile_x >= 6) & (tile_x < 12) & (tile_y < 6))
        )
        left_extension = (tile_x < 9) & (tile_y >= 17) & (tile_y < 21)
        right_extension = (tile_x >= 9) & (tile_y >= 17) & (tile_y < 21)

        self._cpu_tables = {
            "valid": valid,
            "cost": cost,
            "is_spell": is_spell,
            "non_rolling_spell": non_rolling_spell,
            "is_building": is_building,
            "enemy_side": enemy_side,
            "margin": margin,
            "deploy_radius": deploy_radius,
            "building_half": building_half,
            "blocker_radius": blocker_radius,
            "center_x": center_x,
            "center_y": center_y,
            "non_blocked": non_blocked,
            "base_zone": base_zone,
            "left_extension": left_extension,
            "right_extension": right_extension,
        }
        self._tables_by_device: dict[torch.device, Mapping[str, torch.Tensor]] = {}
        self.semantics: Mapping[str, Any] = {
            "schema": "clasher.simple-pytorch.tensor-public-mask-v2.v1",
            "contract_version": PUBLIC_ACTION_MASK_CONTRACT_V2,
            "inputs": "projected-public-actor-only",
            "uses_expert_labels": False,
            "uses_privileged_critic": False,
            "uses_simulator_legal_mask": False,
            "canonical_lane_globals": True,
            "authority": "PublicActionMaskBuilder trace-equivalent",
            "token_names_sha256": _sha256(
                "\0".join(builder.token_names).encode("utf-8")
            ),
        }

    def _tables(self, device: torch.device) -> Mapping[str, torch.Tensor]:
        canonical = torch.device(device)
        if canonical.type == "cuda" and canonical.index is None:
            canonical = torch.device("cuda", torch.cuda.current_device())
        cached = self._tables_by_device.get(canonical)
        if cached is None:
            cached = {
                name: value.to(device=canonical)
                for name, value in self._cpu_tables.items()
            }
            self._tables_by_device[canonical] = cached
        return cached

    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2:
        actor = request.observation.actor
        device = actor.hand_ids.device
        tables = self._tables(device)
        hand = actor.hand_ids[..., :NUM_HAND_SLOTS]
        safe_hand = hand.clamp(0, len(self.builder.token_names) - 1)
        known_hand = (hand > 0) & (hand < len(self.builder.token_names))
        valid_hand = known_hand & tables["valid"][safe_hand]
        elixir = actor.global_features[..., 5].to(torch.float64) * 10.0
        affordable = tables["cost"][safe_hand] <= elixir[..., None] + 1.0e-6

        left_dead = actor.global_features[..., 11] <= 1.0e-4
        right_dead = actor.global_features[..., 12] <= 1.0e-4
        zone = tables["base_zone"].view(1, 1, NUM_TILES).expand(
            *hand.shape[:2], -1
        )
        zone = zone | (
            left_dead[..., None] & tables["left_extension"].view(1, 1, -1)
        )
        zone = zone | (
            right_dead[..., None] & tables["right_extension"].view(1, 1, -1)
        )

        unrestricted = tables["non_rolling_spell"][safe_hand] | tables[
            "enemy_side"
        ][safe_hand]
        candidates = torch.where(
            unrestricted[..., None],
            tables["non_blocked"].view(1, 1, 1, -1),
            zone[:, :, None, :] & tables["non_blocked"].view(1, 1, 1, -1),
        )
        margin = tables["margin"][safe_hand]
        within_margin = (margin[..., None] == 0) | (
            (tables["center_x"].view(1, 1, 1, -1) >= margin[..., None])
            & (
                tables["center_x"].view(1, 1, 1, -1)
                < BOARD_WIDTH - margin[..., None]
            )
        )

        entity_token = actor.entity_ids
        safe_entity = entity_token.clamp(0, len(self.builder.token_names) - 1)
        blocker = (
            actor.entity_mask
            & (actor.entity_features[..., 5] > 0.5)
            & (entity_token >= 0)
            & (entity_token < len(self.builder.token_names))
        )
        blocker_x = actor.entity_features[..., 0].to(torch.float64) * BOARD_WIDTH
        blocker_y = actor.entity_features[..., 1].to(torch.float64) * BOARD_HEIGHT
        blocker_radius = tables["blocker_radius"][safe_entity]
        blocker_half = (
            torch.clamp(torch.ceil(torch.clamp(blocker_radius, min=0.0) * 2.0) + 1.0, min=1.0)
            / 2.0
            + 0.5
        )
        dx = torch.abs(
            tables["center_x"].view(1, 1, 1, NUM_TILES, 1)
            - blocker_x[:, :, None, None, :]
        )
        dy = torch.abs(
            tables["center_y"].view(1, 1, 1, NUM_TILES, 1)
            - blocker_y[:, :, None, None, :]
        )
        blocker_plane = blocker[:, :, None, None, :]
        building_card = tables["is_building"][safe_hand]
        building_occupied = (
            (dx < tables["building_half"][safe_hand][..., None, None] + blocker_half[:, :, None, None, :])
            & (dy < tables["building_half"][safe_hand][..., None, None] + blocker_half[:, :, None, None, :])
            & blocker_plane
        ).any(dim=-1)
        troop_circle = (
            dx.square() + dy.square()
            < (
                tables["deploy_radius"][safe_hand][..., None, None]
                + blocker_radius[:, :, None, None, :]
            ).square()
        )
        troop_square = (dx < blocker_half[:, :, None, None, :]) & (
            dy < blocker_half[:, :, None, None, :]
        )
        troop_occupied = ((troop_circle | troop_square) & blocker_plane).any(dim=-1)
        occupied = torch.where(
            building_card[..., None], building_occupied, troop_occupied
        )
        occupied &= ~tables["is_spell"][safe_hand][..., None]

        placements = (
            candidates
            & within_margin
            & ~occupied
            & valid_hand[..., None]
            & affordable[..., None]
        )
        mask = torch.zeros(
            (*hand.shape[:2], NUM_HAND_SLOTS * NUM_TILES + 2),
            dtype=torch.bool,
            device=device,
        )
        mask[..., : NUM_HAND_SLOTS * NUM_TILES] = placements.flatten(2)
        mask[..., NUM_HAND_SLOTS * NUM_TILES] = True
        return SimplePublicActionMaskV2(
            masks=mask,
            semantics_id="public-action-mask-v2/tensor-actor-projection-v1",
            semantics=self.semantics,
        )


class SimpleClasherPolicyAdapter:
    """Adapt two-seat simple-Gym boundaries to ``ClasherPolicy``."""

    def __init__(self, model: ClasherPolicy) -> None:
        self.model = model

    @staticmethod
    def _flatten(value: torch.Tensor) -> torch.Tensor:
        return value.reshape(value.shape[0] * value.shape[1], 1, *value.shape[2:])

    @staticmethod
    def _flatten_state(value: torch.Tensor) -> torch.Tensor:
        return value.reshape(value.shape[0] * value.shape[1], *value.shape[2:])

    def inputs(self, boundary: SimpleTensorPolicyBoundary) -> PolicyInputs:
        actor = boundary.actor
        critic = boundary.critic
        inputs = PolicyInputs(
            entity_ids=self._flatten(actor.entity_ids),
            entity_features=self._flatten(actor.entity_features),
            entity_mask=self._flatten(actor.entity_mask),
            hand_ids=self._flatten(actor.hand_ids),
            global_features=self._flatten(actor.global_features),
            action_mask=self._flatten(boundary.public_action_masks),
            previous_actions=self._flatten(boundary.previous_actions),
            previous_rewards=self._flatten(boundary.previous_rewards),
            episode_starts=self._flatten(boundary.episode_starts),
            critic_entity_ids=(
                None if critic is None else self._flatten(critic.entity_ids)
            ),
            critic_entity_features=(
                None if critic is None else self._flatten(critic.entity_features)
            ),
            critic_entity_mask=(
                None if critic is None else self._flatten(critic.entity_mask)
            ),
            critic_card_ids=(
                None if critic is None else self._flatten(critic.card_ids)
            ),
            critic_global_features=(
                None if critic is None else self._flatten(critic.global_features)
            ),
        )
        if self.model.config.public_observation_confidence:
            inputs = inputs.with_exact_actor_confidence()
        return inputs

    @staticmethod
    def state_from_mapping(
        values: Mapping[str, torch.Tensor] | None,
    ) -> tuple[torch.Tensor, torch.Tensor] | None:
        if values is None:
            return None
        if tuple(values) != ("hidden", "cell"):
            raise SimplePytorchBackendError("recurrent state must be hidden/cell")
        return (
            SimpleClasherPolicyAdapter._flatten_state(values["hidden"]),
            SimpleClasherPolicyAdapter._flatten_state(values["cell"]),
        )

    @staticmethod
    def state_to_mapping(
        state: tuple[torch.Tensor, torch.Tensor], batch_size: int
    ) -> Mapping[str, torch.Tensor]:
        return {
            "hidden": state[0].reshape(batch_size, 2, -1),
            "cell": state[1].reshape(batch_size, 2, -1),
        }

    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        self.model.eval()
        state = self.state_from_mapping(boundary.recurrent_inputs)
        actions, log_prob, values, next_state, _ = self.model.act(
            self.inputs(boundary), state, deterministic=False
        )
        batch = boundary.actor.entity_ids.shape[0]
        return SimpleTensorPolicyDecision(
            actions=actions[:, 0].reshape(batch, 2),
            next_recurrent_inputs=self.state_to_mapping(next_state, batch),
            storage={
                "log_prob": log_prob[:, 0].reshape(batch, 2),
                "value": values[:, 0].reshape(batch, 2),
            },
        )

    def bootstrap_values(self, boundary: SimpleTensorPolicyBoundary) -> torch.Tensor:
        output = self.model.forward(
            self.inputs(boundary), self.state_from_mapping(boundary.recurrent_inputs)
        )
        return output.values[:, 0]


def _primary_body_name(loader: CardDataLoader, root_name: str) -> str | None:
    stats = loader.get_card(root_name)
    raw = getattr(stats, "_raw_entry", {}) if stats is not None else {}
    child = raw.get("summonCharacterData") if isinstance(raw, dict) else None
    name = child.get("name") if isinstance(child, dict) else None
    return str(name) if name else None


def _typed_lookups(
    setup: Any,
    loader: CardDataLoader,
    vocabulary: CurrentClientTypedVocabulary,
) -> tuple[torch.Tensor, torch.Tensor]:
    size = len(setup.cards.names)
    device = setup.device
    entity = torch.zeros((5, size), dtype=torch.int64, device=device)
    hand = torch.zeros(size, dtype=torch.int64, device=device)
    for card_id, visible_name in enumerate(setup.spawn_blueprints.visible_names):
        if card_id == 0:
            tower = vocabulary.resolve("KingTower", "tower")
            if tower == 0:
                raise SimplePytorchBackendError("typed Crown tower token is missing")
            entity[:, card_id] = tower
            continue
        is_public = bool(setup.public_root_mask[card_id])
        if is_public:
            action_token = vocabulary.resolve(visible_name, "card_action")
            if action_token == 0:
                raise SimplePytorchBackendError(
                    f"public card lacks exact typed action identity: {visible_name}"
                )
            hand[card_id] = action_token
        kind = int(setup.spawn_blueprints.fast_cards.kind[card_id])
        if kind not in (0, 1):
            continue
        namespace = "troop_body" if kind == 0 else "building_body"
        candidates: list[str] = []
        if is_public:
            primary = _primary_body_name(loader, setup.cards.names[card_id])
            if primary is not None:
                candidates.append(primary)
        candidates.append(visible_name)
        body_token = next(
            (
                token
                for candidate in candidates
                if (token := vocabulary.resolve(candidate, namespace)) != 0
            ),
            0,
        )
        if body_token == 0:
            raise SimplePytorchBackendError(
                f"runtime card lacks exact typed body identity: {visible_name}"
            )
        entity[kind, card_id] = body_token
    return entity, hand


def _deck_rows(
    artifact: SimpleSupportedDeckArtifact,
    *,
    batch_size: int,
    mirror_match: bool,
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    result = []
    for index in range(batch_size):
        first = artifact.decks[(2 * index) % len(artifact.decks)]
        second = first if mirror_match else artifact.decks[(2 * index + 1) % len(artifact.decks)]
        result.append((first, second))
    return tuple(result)


@dataclass(frozen=True)
class SimplePytorchBackendMetadata:
    backend_id: str
    actor_semantics_id: str
    fresh_only: bool
    canonical_lane_globals: bool
    public_action_mask_contract_version: int
    supported_decks_sha256: str
    support_profile_sha256: str
    typed_vocabulary_sha256: str
    reward_contract_id: str
    reward_contract_digest: str
    reward_contract_metadata: Mapping[str, Any]


class SimplePytorchTrainingCollector:
    """One-process route from the dense Gym into the existing PPO batch."""

    def __init__(
        self,
        *,
        model: ClasherPolicy,
        builder: StructuredObservationBuilder,
        batch_size: int,
        device: torch.device,
        decision_interval: int,
        gamma: float,
        supported_decks_path: str | Path,
        typed_vocabulary_path: str | Path,
        mirror_match: bool,
    ) -> None:
        if batch_size < 1:
            raise SimplePytorchBackendError("simple backend needs at least one row")
        if not builder.canonical_lane_globals or not model.config.canonical_lane_globals:
            raise SimplePytorchBackendError("simple backend requires canonical lanes")
        if model.config.actor_observation_domain != "simulator-exact":
            raise SimplePytorchBackendError(
                "fresh simple backend uses its exact public projection domain"
            )
        if builder.public_history_slots or builder.public_seen_card_slots:
            raise SimplePytorchBackendError(
                "fresh simple backend does not consume legacy accumulated history"
            )
        vocabulary = load_current_client_typed_vocabulary(typed_vocabulary_path)
        if tuple(builder.token_names) != vocabulary.token_names:
            raise SimplePytorchBackendError("builder does not use the typed vocabulary")
        artifact = load_simple_supported_decks(supported_decks_path)
        loader = CardDataLoader()
        setup = compile_standard_simple_setup(
            loader,
            artifact.public_cards,
            device=device,
            canonical_lane_globals=True,
        )
        if set(setup.supported_public_root_names) != set(artifact.public_cards):
            raise SimplePytorchBackendError(
                "supported-deck artifact drifted from the current compiler"
            )
        entity_lookup, hand_lookup = _typed_lookups(setup, loader, vocabulary)
        runtime = setup.create_runtime(
            _deck_rows(artifact, batch_size=batch_size, mirror_match=mirror_match),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            canonical_lane_globals=True,
            max_entities=builder.max_entities,
            include_privileged_critic=True,
        )
        reward = SimpleRewardV2Config(gamma=gamma)
        bridge = SimpleGymRolloutBridge(
            runtime,
            decision_interval=decision_interval,
            reward_v2_config=reward,
            strict_reset_check=False,
        )
        self.policy = SimpleClasherPolicyAdapter(model)
        self.collector = SimpleTensorCollector(
            bridge,
            public_mask_provider=SimplePublicMaskV2Adapter(builder),
            policy=self.policy,
            strict_host_validation=False,
        )
        reward_metadata = simple_reward_v2_metadata(reward)
        self.metadata = SimplePytorchBackendMetadata(
            backend_id=SIMPLE_TENSOR_BACKEND_ID,
            actor_semantics_id=SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
            fresh_only=True,
            canonical_lane_globals=True,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
            supported_decks_sha256=artifact.sha256,
            support_profile_sha256=artifact.support_profile_sha256,
            typed_vocabulary_sha256=vocabulary.sha256,
            reward_contract_id=SIMPLE_REWARD_V2_CONTRACT_ID,
            reward_contract_digest=str(reward_metadata["reward_contract_digest"]),
            reward_contract_metadata=reward_metadata,
        )

    @property
    def batch_size(self) -> int:
        return self.collector.batch_size

    @staticmethod
    def _agent_major(value: torch.Tensor) -> np.ndarray:
        order = (1, 2, 0, *range(3, value.ndim))
        arranged = value.permute(order).reshape(
            value.shape[1] * value.shape[2], value.shape[0], *value.shape[3:]
        )
        return arranged.detach().cpu().numpy()

    @staticmethod
    def _confidence_arrays(batch: SimpleTensorDecisionBatch) -> tuple[np.ndarray, ...]:
        entity = batch.actor.entity_mask.to(torch.float32)
        entity_features = entity[..., None].expand_as(batch.actor.entity_features)
        hand = torch.ones_like(batch.actor.hand_ids, dtype=torch.float32)
        global_features = torch.ones_like(batch.actor.global_features)
        return tuple(
            SimplePytorchTrainingCollector._agent_major(value)
            for value in (entity, entity_features, hand, global_features)
        )

    @torch.no_grad()
    def collect(
        self,
        rollout_steps: int,
        recurrent_state: tuple[torch.Tensor, torch.Tensor],
    ) -> tuple[
        dict[str, Any],
        tuple[torch.Tensor, torch.Tensor],
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        batch = self.batch_size
        initial_hidden = recurrent_state[0].detach().cpu().numpy().copy()
        initial_cell = recurrent_state[1].detach().cpu().numpy().copy()
        recurrent_inputs = {
            "hidden": recurrent_state[0].reshape(batch, 2, -1),
            "cell": recurrent_state[1].reshape(batch, 2, -1),
        }
        decision = self.collector.collect(
            rollout_steps, recurrent_inputs=recurrent_inputs
        )
        if decision.critic is None:
            raise SimplePytorchBackendError("training collection requires a critic")
        confidence = self._confidence_arrays(decision)
        steps, rows, seats = decision.actions.shape
        agents = rows * seats
        history_slots = self.policy.model.config.public_history_slots
        seen_slots = self.policy.model.config.public_seen_card_slots
        zeros_history_i64 = np.zeros((agents, steps, history_slots), dtype=np.int64)
        zeros_history_f32 = np.zeros((agents, steps, history_slots), dtype=np.float32)
        zeros_seen = np.zeros((agents, steps, seen_slots), dtype=np.int64)
        bootstrap_values = self.policy.bootstrap_values(decision.bootstrap)
        storage = decision.policy_storage
        required_storage = {"log_prob", "value"}
        if set(storage) != required_storage:
            raise SimplePytorchBackendError("policy storage contract changed")
        winner = decision.winner.detach().cpu()
        done = decision.done.detach().cpu()
        terminal_winner = winner[done]
        arrays: dict[str, Any] = {
            "entity_ids": self._agent_major(decision.actor.entity_ids),
            "entity_features": self._agent_major(decision.actor.entity_features),
            "entity_mask": self._agent_major(decision.actor.entity_mask),
            "hand_ids": self._agent_major(decision.actor.hand_ids),
            "global_features": self._agent_major(decision.actor.global_features),
            "entity_id_confidence": confidence[0],
            "entity_feature_confidence": confidence[1],
            "hand_id_confidence": confidence[2],
            "global_feature_confidence": confidence[3],
            "opponent_history_ids": zeros_history_i64,
            "opponent_history_ages": zeros_history_f32,
            "opponent_seen_card_ids": zeros_seen,
            "opponent_play_event_ids": np.zeros((agents, steps), dtype=np.int64),
            "opponent_play_event_confidence": np.zeros(
                (agents, steps), dtype=np.float32
            ),
            "action_masks": self._agent_major(decision.public_action_masks),
            "previous_actions": self._agent_major(decision.previous_actions),
            "previous_rewards": self._agent_major(decision.previous_rewards),
            "episode_starts": self._agent_major(decision.episode_starts),
            "critic_entity_ids": self._agent_major(decision.critic.entity_ids),
            "critic_entity_features": self._agent_major(
                decision.critic.entity_features
            ),
            "critic_entity_mask": self._agent_major(decision.critic.entity_mask),
            "critic_card_ids": self._agent_major(decision.critic.card_ids),
            "critic_global_features": self._agent_major(
                decision.critic.global_features
            ),
            "actions": self._agent_major(decision.actions),
            "old_log_probs": self._agent_major(storage["log_prob"]),
            "old_values": self._agent_major(storage["value"]),
            "rewards": self._agent_major(decision.rewards),
            "dones": self._agent_major(
                decision.done[..., None].expand(-1, -1, 2)
            ),
            "initial_hidden": initial_hidden,
            "initial_cell": initial_cell,
            "bootstrap_values": bootstrap_values.detach().cpu().numpy(),
            "episodes_finished": int(done.sum().item()),
            "wins": int((terminal_winner == 0).sum().item()),
            "losses": int((terminal_winner == 1).sum().item()),
            "draws": int((terminal_winner < 0).sum().item()),
        }
        bootstrap_state = self.policy.state_from_mapping(
            decision.bootstrap.recurrent_inputs
        )
        if bootstrap_state is None:
            raise SimplePytorchBackendError("collector lost recurrent bootstrap state")
        previous_actions = decision.bootstrap.previous_actions.reshape(-1)
        previous_rewards = decision.bootstrap.previous_rewards.reshape(-1)
        episode_starts = decision.bootstrap.episode_starts.reshape(-1)
        return (
            arrays,
            (bootstrap_state[0].detach(), bootstrap_state[1].detach()),
            previous_actions.detach().cpu().numpy(),
            previous_rewards.detach().cpu().numpy(),
            episode_starts.detach().cpu().numpy(),
        )

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {
            **self.metadata.__dict__,
            "standard_tiebreak_tick": STANDARD_TIEBREAK_TICK,
            "metadata_digest": _canonical_digest(self.metadata.__dict__),
        }


__all__ = [
    "CURRENT_CLIENT_VOCABULARY_SCHEMA",
    "DEFAULT_SIMPLE_SUPPORTED_DECKS",
    "DEFAULT_SIMPLE_TOKEN_VOCABULARY",
    "SIMPLE_PYTORCH_BACKEND",
    "CurrentClientTypedVocabulary",
    "ReferenceSimplePublicMaskV2Adapter",
    "SimplePublicMaskV2Adapter",
    "SimplePytorchBackendError",
    "SimplePytorchBackendMetadata",
    "SimplePytorchTrainingCollector",
    "SimpleSupportedDeckArtifact",
    "load_current_client_typed_vocabulary",
    "load_simple_supported_decks",
]
