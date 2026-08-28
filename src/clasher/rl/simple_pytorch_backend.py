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
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np
import torch

from clasher.arena import TileGrid
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_public_mask import (
    SimpleCollectorPublicMaskV2Provider,
    SimplePublicMaskTypedTables,
    SimplePublicMaskV2Provider,
)
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

from .card_semantics import building_target_pressure_score
from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_TILES
from .model import ClasherPolicy, PolicyInputs
from .simple_tensor_collector import (
    SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
    SIMPLE_TENSOR_BACKEND_ID,
    SimpleTensorCollector,
    SimpleTensorDecisionBatch,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from .strategy_bots import (
    BRIDGE_PRESSURE,
    REACTIVE_DEFENSE,
    SLOW_PUSH,
    SPELL_CONTROL,
    SPLIT_LANE,
    STRATEGY_NAMES,
    BalancedStrategyConfig,
)
from .structured_obs import StructuredObservationBuilder

SIMPLE_PYTORCH_BACKEND: Final = "simple-pytorch"
SIMPLE_PYTORCH_EXECUTION_EAGER: Final = "eager"
SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH: Final = "cuda-graph"
SIMPLE_PYTORCH_EXECUTION_MODES: Final = frozenset(
    (SIMPLE_PYTORCH_EXECUTION_EAGER, SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH)
)
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
SIMPLE_LEAGUE_RANDOM: Final = 0
SIMPLE_LEAGUE_STRATEGY: Final = 1
SIMPLE_LEAGUE_CHECKPOINT: Final = 2
SimpleLeagueKind = Literal["random", "strategy", "checkpoint"]
SimpleLeagueSpec = tuple[SimpleLeagueKind, str | None]


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


def _synchronize_cuda_stream(stream: torch.cuda.Stream) -> None:
    """Complete one coalesced rollout handoff after every copy is enqueued."""

    stream.synchronize()


class _CoalescedCpuStaging:
    """Stage heterogeneous rollout tensors into pinned dtype-group slabs.

    All CUDA copies are non-blocking and issued on the current actor stream.
    Calling :meth:`finish` performs the sole explicit synchronization, after
    which NumPy views retain their Torch storage owners. CPU collection uses
    independent ordinary CPU clones and requires no synchronization.
    """

    def __init__(self, values: Mapping[str, torch.Tensor]) -> None:
        if not values:
            raise SimplePytorchBackendError("rollout handoff cannot be empty")
        devices = {value.device for value in values.values()}
        if len(devices) != 1:
            raise SimplePytorchBackendError(
                "rollout handoff tensors must share one device"
            )
        self.device = next(iter(devices))
        self._cpu: dict[str, torch.Tensor] = {}
        self._device_slabs: list[torch.Tensor] = []
        self._stream: torch.cuda.Stream | None = None
        if self.device.type != "cuda":
            self._cpu = {
                name: value.detach().to(device="cpu").clone()
                for name, value in values.items()
            }
            return

        self._stream = torch.cuda.current_stream(self.device)
        by_dtype: dict[torch.dtype, list[tuple[str, torch.Tensor]]] = defaultdict(list)
        for name, value in values.items():
            by_dtype[value.dtype].append((name, value.detach()))
        for dtype, entries in by_dtype.items():
            device_slab = torch.cat(
                tuple(value.reshape(-1) for _name, value in entries),
                dim=0,
            )
            slab = torch.empty(
                device_slab.numel(),
                dtype=dtype,
                device="cpu",
                pin_memory=True,
            )
            slab.copy_(device_slab, non_blocking=True)
            self._device_slabs.append(device_slab)
            offset = 0
            for name, value in entries:
                count = value.numel()
                destination = slab.narrow(0, offset, count).view(value.shape)
                self._cpu[name] = destination
                offset += count

    def finish(self) -> dict[str, np.ndarray]:
        if self._stream is not None:
            _synchronize_cuda_stream(self._stream)
        return {
            name: cast(np.ndarray, value.numpy()) for name, value in self._cpu.items()
        }


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
    deck_names: tuple[str, ...]
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
    deck_names: list[str] = []
    decks: list[tuple[str, ...]] = []
    for index, row in enumerate(rows):
        name = row.get("name") if isinstance(row, dict) else None
        cards = row.get("cards") if isinstance(row, dict) else None
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(cards, list)
            or len(cards) != 8
            or len(set(cards)) != 8
            or any(not isinstance(card, str) or card not in supported for card in cards)
        ):
            raise SimplePytorchBackendError(
                f"supported-deck row {index} is invalid or out of profile"
            )
        deck_names.append(name)
        decks.append(tuple(cards))
    if len(set(deck_names)) != len(deck_names):
        raise SimplePytorchBackendError("supported-deck names must be unique")
    return SimpleSupportedDeckArtifact(
        deck_names=tuple(deck_names),
        decks=tuple(decks),
        public_cards=tuple(str(name) for name in public_cards),
        sha256=digest,
        support_profile_sha256=profile_digest,
    )


def _compile_public_mask_v2_tables(
    builder: StructuredObservationBuilder,
    setup: Any,
    entity_token_lookup: torch.Tensor,
) -> SimplePublicMaskTypedTables:
    """Compile the committed actor-v2 authority from setup-only metadata."""

    token_count = len(builder.token_names)
    definitions = builder.loader.load_card_definitions()
    tile_grid = TileGrid()
    hand_playable = torch.zeros(token_count, dtype=torch.bool)
    elixir_cost = torch.zeros(token_count, dtype=torch.float64)
    is_spell = torch.zeros(token_count, dtype=torch.bool)
    non_rolling_spell = torch.zeros(token_count, dtype=torch.bool)
    is_building = torch.zeros(token_count, dtype=torch.bool)
    can_deploy_enemy_side = torch.zeros(token_count, dtype=torch.bool)
    deploy_margin_tiles = torch.zeros(token_count, dtype=torch.int64)
    deploy_radius_tiles = torch.full((token_count,), 0.5, dtype=torch.float64)
    blocker_radius_tiles = torch.as_tensor(
        [float(value) * 3.0 for value in builder.card_stat_features[:, 12]],
        dtype=torch.float64,
    ).clamp_min(0.5)

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
        building = bool(
            not spell
            and str(getattr(stats, "card_type", "") or "").lower() == "building"
        )
        hand_playable[token] = True
        elixir_cost[token] = raw_cost
        is_spell[token] = spell
        non_rolling_spell[token] = bool(
            spell
            and not tile_grid._requires_deploy_zone_spell(spell_object)
            and not getattr(spell_object, "requires_walkable_target", False)
        )
        is_building[token] = building
        can_deploy_enemy_side[token] = bool(
            not spell and getattr(stats, "can_deploy_on_enemy_side", False)
        )
        deploy_margin_tiles[token] = int(getattr(stats, "deploy_w_tile_margin", 0) or 0)
        deploy_radius_tiles[token] = float(
            getattr(stats, "collision_radius", 0.5) or 0.5
        )

    ability_supported = torch.zeros(token_count, dtype=torch.bool)
    ability_elixir_cost = torch.zeros(token_count, dtype=torch.float64)
    supported = setup.ability_catalog.supported.detach().cpu().tolist()
    costs = setup.ability_catalog.elixir_cost.detach().cpu().tolist()
    kinds = setup.spawn_blueprints.fast_cards.kind.detach().cpu().tolist()
    entity_tokens = entity_token_lookup.detach().cpu()
    for card_id, enabled in enumerate(supported):
        if not enabled:
            continue
        kind = int(kinds[card_id])
        token = int(entity_tokens[kind, card_id])
        cost = float(costs[card_id])
        if not 0 < token < token_count:
            raise SimplePytorchBackendError(
                "supported ability lacks an exact typed entity identity: "
                f"{setup.cards.names[card_id]}"
            )
        if ability_supported[token] and ability_elixir_cost[token] != cost:
            raise SimplePytorchBackendError(
                "typed ability identity maps to conflicting serialized costs"
            )
        ability_supported[token] = True
        ability_elixir_cost[token] = cost

    return SimplePublicMaskTypedTables.compile(
        token_keys=builder.token_names,
        hand_playable=hand_playable,
        elixir_cost=elixir_cost,
        is_spell=is_spell,
        non_rolling_spell=non_rolling_spell,
        is_building=is_building,
        can_deploy_enemy_side=can_deploy_enemy_side,
        deploy_margin_tiles=deploy_margin_tiles,
        deploy_radius_tiles=deploy_radius_tiles,
        blocker_radius_tiles=blocker_radius_tiles,
        ability_supported=ability_supported,
        ability_elixir_cost=ability_elixir_cost,
        blocked_tiles=tuple(TileGrid.BLOCKED_TILES),
        authority="serialized-card-data-and-current-client-typed-vocabulary-v1",
    ).to(setup.device)


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


class SimpleTensorStrategyOpponent:
    """Vectorized public-state port of the existing data-driven StrategyBot."""

    def __init__(
        self,
        builder: StructuredObservationBuilder,
        *,
        strategy_name: str,
        device: torch.device,
        balanced_config: BalancedStrategyConfig | None = None,
    ) -> None:
        if strategy_name not in STRATEGY_NAMES:
            raise SimplePytorchBackendError(
                f"unknown tensor strategy {strategy_name!r}"
            )
        self.strategy_name = strategy_name
        self.config = balanced_config or BalancedStrategyConfig()
        features = torch.as_tensor(
            builder.card_stat_features[:, :16],
            dtype=torch.float32,
            device=device,
        )
        self.cost = features[:, 0] * 10.0
        self.is_building = features[:, 2] > 0.5
        self.is_spell = features[:, 3] > 0.5
        self.card_hp = torch.expm1(features[:, 5] * 9.0)
        self.damage = torch.expm1(features[:, 6] * 8.0)
        self.attack_range = features[:, 7] * 12.0
        self.speed = features[:, 9] * 200.0
        self.hit_speed = (features[:, 10] * 5000.0).clamp_min(250.0)
        self.summon_count = (features[:, 13] * 20.0).clamp_min(1.0)
        tower = [
            bool(name.startswith("tower:") or name in {"Tower", "KingTower"})
            for name in builder.token_names
        ]
        self.is_tower = torch.as_tensor(tower, dtype=torch.bool, device=device)
        pressure = torch.zeros(len(builder.token_names), dtype=torch.float32)
        entity_max_hp = torch.zeros(
            len(builder.token_names), dtype=torch.float32
        )
        for token in range(len(builder.token_names)):
            token_name = builder.token_names[token]
            typed = builder._typed_token_parts(token_name)
            name = typed[1] if typed is not None else token_name
            stats = builder.loader.get_card(name)
            if stats is not None:
                pressure[token] = float(building_target_pressure_score(stats))
                entity_max_hp[token] = float(
                    stats.scaled_hitpoints or stats.hitpoints or 0.0
                )
        self.entity_max_hp = entity_max_hp.to(device)
        self.tower_pressure = (
            torch.log1p(pressure.to(device)) / math.log1p(400.0)
        )
        tiles = torch.arange(NUM_TILES, device=device, dtype=torch.float32)
        tile_x = torch.remainder(tiles, BOARD_WIDTH) + 0.5
        tile_y = torch.floor(tiles / BOARD_WIDTH) + 0.5
        self.action_x = tile_x.repeat(4)
        self.action_y = tile_y.repeat(4)

    @staticmethod
    def _gaussian(
        x: torch.Tensor,
        y: torch.Tensor,
        target_x: torch.Tensor,
        target_y: torch.Tensor,
        scale: float,
    ) -> torch.Tensor:
        distance_sq = (x - target_x) ** 2 + (y - target_y) ** 2
        return torch.exp(-distance_sq / (2.0 * scale * scale))

    def _situation(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> dict[str, torch.Tensor]:
        ids = boundary.actor.entity_ids.reshape(
            -1, boundary.actor.entity_ids.shape[-1]
        )
        features = boundary.actor.entity_features.reshape(
            -1,
            boundary.actor.entity_features.shape[-2],
            boundary.actor.entity_features.shape[-1],
        )
        visible = boundary.actor.entity_mask.reshape(-1, ids.shape[-1])
        x = features[..., 0] * BOARD_WIDTH
        y = features[..., 1] * BOARD_HEIGHT
        own = features[..., 2] > 0.5
        enemy = features[..., 3] > 0.5
        combat = (
            visible
            & ((features[..., 4] > 0.5) | (features[..., 5] > 0.5))
            & ~self.is_tower[ids]
        )
        max_hp = self.entity_max_hp[ids].clamp_min(1.0)
        current_hp = max_hp * features[..., 9].clamp(0.0, 1.0)
        damage = torch.expm1(features[..., 30].clamp_min(0.0) * 8.0)
        dps = damage * 1000.0 / self.hit_speed[ids]
        strength = (0.6 + current_hp / max_hp) * (
            0.5 + torch.sqrt(max_hp / 900.0) + dps / 180.0
        )
        enemy_mask = combat & enemy
        allied_mask = combat & own
        enemy_strength = strength * enemy_mask
        allied_strength = strength * allied_mask
        incoming_weight = enemy_strength * (y < 16.5) * torch.exp(
            -torch.clamp_min(y - 5.5, 0.0) / 6.0
        )
        incoming_strength = incoming_weight.sum(dim=1)
        incoming_denominator = incoming_strength.clamp_min(1e-9)
        incoming_x = torch.where(
            incoming_strength > 0,
            (x * incoming_weight).sum(dim=1) / incoming_denominator,
            torch.full_like(incoming_strength, 9.0),
        )
        incoming_y = torch.where(
            incoming_strength > 0,
            (y * incoming_weight).sum(dim=1) / incoming_denominator,
            torch.full_like(incoming_strength, 10.0),
        )
        cluster_strength = enemy_strength.sum(dim=1)
        cluster_denominator = cluster_strength.clamp_min(1e-9)
        cluster_x = torch.where(
            cluster_strength > 0,
            (x * enemy_strength).sum(dim=1) / cluster_denominator,
            torch.full_like(cluster_strength, 9.0),
        )
        cluster_y = torch.where(
            cluster_strength > 0,
            (y * enemy_strength).sum(dim=1) / cluster_denominator,
            torch.full_like(cluster_strength, 23.5),
        )
        enemy_left = (enemy_strength * (x < 9.0)).sum(dim=1)
        enemy_right = (enemy_strength * (x >= 9.0)).sum(dim=1)
        allied_left = (allied_strength * (x < 9.0)).sum(dim=1)
        allied_right = (allied_strength * (x >= 9.0)).sum(dim=1)

        tank_index = (current_hp * allied_mask).argmax(dim=1)
        row = torch.arange(ids.shape[0], device=ids.device)
        tank_x = x[row, tank_index]
        tank_y = y[row, tank_index]
        tank_valid = allied_mask.any(dim=1) & (max_hp[row, tank_index] >= 900.0)
        return {
            "incoming_strength": incoming_strength,
            "incoming_x": incoming_x,
            "incoming_y": incoming_y,
            "enemy_left": enemy_left,
            "enemy_right": enemy_right,
            "allied_left": allied_left,
            "allied_right": allied_right,
            "cluster_x": cluster_x,
            "cluster_y": cluster_y,
            "cluster_strength": cluster_strength,
            "tank_x": tank_x,
            "tank_y": tank_y,
            "tank_valid": tank_valid,
        }

    def __call__(self, boundary: SimpleTensorPolicyBoundary) -> torch.Tensor:
        batch = boundary.actor.entity_ids.shape[0]
        situation = self._situation(boundary)
        count = batch * 2
        x = self.action_x[None, :].expand(count, -1)
        y = self.action_y[None, :].expand(count, -1)
        hand = boundary.actor.hand_ids[..., :4].reshape(count, 4)
        card_ids = hand[..., None].expand(-1, -1, NUM_TILES).reshape(count, -1)
        cost = self.cost[card_ids]
        hp = self.card_hp[card_ids]
        damage = self.damage[card_ids]
        speed = self.speed[card_ids]
        attack_range = self.attack_range[card_ids]
        summon_count = self.summon_count[card_ids]
        is_spell = self.is_spell[card_ids]
        is_building = self.is_building[card_ids] & ~is_spell
        efficiency = (
            torch.sqrt(torch.clamp_min(hp, 0.0) / 700.0)
            + damage / 170.0
            + 0.2 * summon_count
        ) / cost.clamp_min(1.0)
        lane = x >= 9.0

        incoming_x = situation["incoming_x"][:, None]
        incoming_y = situation["incoming_y"][:, None]
        defense_fit = self._gaussian(
            x,
            y,
            incoming_x,
            torch.minimum(torch.full_like(incoming_y, 14.0), incoming_y + 1.5),
            3.5,
        )
        cluster_fit = self._gaussian(
            x,
            y,
            situation["cluster_x"][:, None],
            situation["cluster_y"][:, None],
            3.0,
        )
        incoming_strength = situation["incoming_strength"][:, None]
        elixir = (
            boundary.actor.global_features[..., 5].reshape(count, 1) * 10.0
        )

        if self.strategy_name == BRIDGE_PRESSURE:
            placement = (
                4.2 * torch.exp(-torch.abs(y - 14.0) / 2.7)
                + 0.018 * speed
                + 0.6 * efficiency
                + 0.25 * (~lane)
                - 0.55 * cost
                + torch.where(is_spell, 1.4 * cluster_fit, 0.0)
            )
            noop = torch.where(elixir[:, 0] < 4.0, 1.5, -1.0)
        elif self.strategy_name == SLOW_PUSH:
            support = self._gaussian(
                x,
                y,
                situation["tank_x"][:, None],
                torch.clamp_min(situation["tank_y"][:, None] - 2.5, 2.0),
                3.5,
            ) * situation["tank_valid"][:, None]
            placement = (
                4.5 * torch.exp(-torch.abs(y - 4.5) / 2.7)
                + 0.0025 * hp
                + 1.5 * support
                + 0.35 * attack_range
                - 2.5 * is_spell
                - 1.5 * (elixir < 7.0)
            )
            noop = torch.where(
                (elixir[:, 0] < 7.0)
                & (situation["incoming_strength"] < 0.08),
                5.0,
                -0.5,
            )
        elif self.strategy_name == SPELL_CONTROL:
            tower_zone = torch.exp(-torch.abs(y - 25.0) / 4.0)
            spell_score = (
                2.0
                + 5.0 * cluster_fit
                + 0.5 * tower_zone
                + 0.3 * situation["cluster_strength"][:, None]
            )
            unit_score = (
                3.2 * defense_fit
                + 1.5 * (is_building & (incoming_strength > 0.2))
                + 0.7 * efficiency
                - 0.35 * cost
            )
            placement = torch.where(is_spell, spell_score, unit_score)
            noop = torch.where(
                (situation["cluster_strength"] < 0.2) & (elixir[:, 0] < 9.0),
                3.0,
                0.0,
            )
        elif self.strategy_name == REACTIVE_DEFENSE:
            pressured = incoming_strength > 0.08
            defense = (
                6.0 * defense_fit
                + 1.5 * is_building
                + efficiency
                + torch.where(is_spell, 2.0 * cluster_fit, 0.0)
                - 0.28 * cost
            )
            quiet = (
                1.2 * torch.exp(-torch.abs(y - 7.0) / 4.0)
                + 0.5 * efficiency
                - 0.5 * cost
            )
            placement = torch.where(pressured, defense, quiet)
            noop = torch.where(
                (situation["incoming_strength"] <= 0.08)
                & (elixir[:, 0] < 9.0),
                4.0,
                -1.0,
            )
        elif self.strategy_name == SPLIT_LANE:
            desired_lane = (
                situation["allied_right"] - situation["enemy_right"]
                > situation["allied_left"] - situation["enemy_left"]
            )[:, None]
            placement = (
                3.0 * (lane != desired_lane)
                + 3.2 * torch.exp(-torch.abs(y - 13.5) / 3.5)
                + 0.8 * efficiency
                - 0.4 * cost
                + torch.where(is_spell, 1.4 * cluster_fit, 0.0)
            )
            noop = torch.where(elixir[:, 0] < 4.0, 1.5, -1.0)
        else:
            config = self.config
            threat = torch.clamp(
                incoming_strength / config.threat_scale,
                0.0,
                1.0,
            )
            defense = config.defense_fit_weight * defense_fit + (
                config.defensive_building_bonus * is_building
            )
            offense = (
                config.offense_position_weight
                * torch.exp(
                    -torch.abs(y - config.offense_y) / config.offense_y_scale
                )
                + config.efficiency_weight * efficiency
                + config.tower_pressure_weight * self.tower_pressure[card_ids]
            )
            placement = (
                threat * defense
                + 2.0 * (1.0 - threat) * offense
                + torch.where(
                    is_spell,
                    config.spell_cluster_weight * cluster_fit,
                    0.0,
                )
                - config.cost_weight * cost
            )
            noop = torch.where(
                (situation["incoming_strength"] <= config.noop_threat_threshold)
                & (elixir[:, 0] < config.noop_elixir_threshold),
                config.noop_score,
                -0.5,
            )

        scores = torch.full(
            (count, NO_OP_ACTION + 2),
            -1e9,
            dtype=torch.float32,
            device=boundary.public_action_masks.device,
        )
        scores[:, :NO_OP_ACTION] = placement
        scores[:, NO_OP_ACTION] = noop
        scores[:, NO_OP_ACTION + 1] = 4.0 + torch.clamp_max(
            situation["incoming_strength"], 3.0
        )
        legal = boundary.public_action_masks.reshape(count, -1)
        scores = scores.masked_fill(~legal, -1e9)
        return scores.argmax(dim=1).reshape(batch, 2)


class SimpleTensorStrategyLeagueOpponent:
    """Dispatch row-sharded tensor strategies without duplicating simulator work."""

    def __init__(
        self,
        builder: StructuredObservationBuilder,
        *,
        strategy_names: tuple[str, ...],
        device: torch.device,
    ) -> None:
        if not strategy_names:
            raise SimplePytorchBackendError("strategy league cannot be empty")
        if any(name not in STRATEGY_NAMES for name in strategy_names):
            raise SimplePytorchBackendError("strategy league contains an unknown name")
        self.strategy_names = strategy_names
        self.controllers = {
            name: SimpleTensorStrategyOpponent(
                builder,
                strategy_name=name,
                device=device,
            )
            for name in dict.fromkeys(strategy_names)
        }
        self.rows = {
            name: torch.as_tensor(
                [index for index, value in enumerate(strategy_names) if value == name],
                dtype=torch.int64,
                device=device,
            )
            for name in self.controllers
        }

    @staticmethod
    def _slice_public(
        value: Any,
        rows: torch.Tensor,
    ) -> Any:
        return type(value)(
            **{
                field_name: getattr(value, field_name).index_select(0, rows)
                for field_name in value.__dataclass_fields__
            }
        )

    def __call__(self, boundary: SimpleTensorPolicyBoundary) -> torch.Tensor:
        if len(self.strategy_names) != boundary.actor.entity_ids.shape[0]:
            raise SimplePytorchBackendError(
                "strategy schedule must have one entry per battle row"
            )
        result = torch.empty(
            boundary.actor.entity_ids.shape[:2],
            dtype=torch.int64,
            device=boundary.actor.entity_ids.device,
        )
        for name, controller in self.controllers.items():
            rows = self.rows[name]
            sub_boundary = SimpleTensorPolicyBoundary(
                actor=self._slice_public(boundary.actor, rows),
                critic=(
                    None
                    if boundary.critic is None
                    else self._slice_public(boundary.critic, rows)
                ),
                legal_mask=boundary.legal_mask.index_select(0, rows),
                public_action_masks=boundary.public_action_masks.index_select(
                    0, rows
                ),
                previous_actions=boundary.previous_actions.index_select(0, rows),
                previous_rewards=boundary.previous_rewards.index_select(0, rows),
                episode_starts=boundary.episode_starts.index_select(0, rows),
                recurrent_inputs=None,
                decision_index=boundary.decision_index,
            )
            result.index_copy_(0, rows, controller(sub_boundary))
        return result


class SimpleAsymmetricClasherPolicyAdapter(SimpleClasherPolicyAdapter):
    """Joint two-seat controller with PPO storage only for learner seats."""

    def __init__(
        self,
        model: ClasherPolicy,
        *,
        learner_players: torch.Tensor,
        opponent_mode: Literal[
            "noop", "random", "strategy", "checkpoint", "league"
        ],
        opponent_model: ClasherPolicy | None = None,
        opponent_strategy: (
            SimpleTensorStrategyOpponent
            | SimpleTensorStrategyLeagueOpponent
            | None
        ) = None,
        opponent_league_kinds: torch.Tensor | None = None,
    ) -> None:
        super().__init__(model)
        if learner_players.ndim != 1 or learner_players.dtype != torch.int64:
            raise SimplePytorchBackendError(
                "learner players must be one int64 seat per battle row"
            )
        if bool(((learner_players < 0) | (learner_players > 1)).any().item()):
            raise SimplePytorchBackendError("learner player seats must be 0 or 1")
        checkpoint_required = opponent_mode == "checkpoint" or (
            opponent_mode == "league"
            and opponent_league_kinds is not None
            and bool((opponent_league_kinds == SIMPLE_LEAGUE_CHECKPOINT).any().item())
        )
        strategy_required = opponent_mode == "strategy" or (
            opponent_mode == "league"
            and opponent_league_kinds is not None
            and bool((opponent_league_kinds == SIMPLE_LEAGUE_STRATEGY).any().item())
        )
        if checkpoint_required and opponent_model is None:
            raise SimplePytorchBackendError(
                "checkpoint opponent requires a loaded policy"
            )
        if not checkpoint_required and opponent_model is not None:
            raise SimplePytorchBackendError(
                f"{opponent_mode} opponent cannot own a policy"
            )
        if strategy_required and opponent_strategy is None:
            raise SimplePytorchBackendError(
                "strategy opponent requires a tensor strategy"
            )
        if not strategy_required and opponent_strategy is not None:
            raise SimplePytorchBackendError(
                f"{opponent_mode} opponent cannot own a tensor strategy"
            )
        if opponent_mode == "league":
            if opponent_league_kinds is None:
                raise SimplePytorchBackendError(
                    "league opponent requires one kind per battle row"
                )
            if opponent_league_kinds.shape != learner_players.shape:
                raise SimplePytorchBackendError(
                    "league kind schedule must match the battle rows"
                )
            if opponent_league_kinds.dtype != torch.int64:
                raise SimplePytorchBackendError(
                    "league kind schedule must use int64 codes"
                )
            known = (
                (opponent_league_kinds == SIMPLE_LEAGUE_RANDOM)
                | (opponent_league_kinds == SIMPLE_LEAGUE_STRATEGY)
                | (opponent_league_kinds == SIMPLE_LEAGUE_CHECKPOINT)
            )
            if not bool(known.all().item()):
                raise SimplePytorchBackendError(
                    "league kind schedule contains an unknown code"
                )
        elif opponent_league_kinds is not None:
            raise SimplePytorchBackendError(
                f"{opponent_mode} opponent cannot own a league kind schedule"
            )
        self.learner_players = learner_players
        self.opponent_mode = opponent_mode
        self.opponent_model = opponent_model
        self.opponent_adapter = (
            SimpleClasherPolicyAdapter(opponent_model)
            if opponent_model is not None
            else None
        )
        self.opponent_strategy = opponent_strategy
        self.opponent_league_kinds = opponent_league_kinds
        self._league_rows = (
            {
                kind: torch.nonzero(opponent_league_kinds == kind).flatten()
                for kind in (
                    SIMPLE_LEAGUE_RANDOM,
                    SIMPLE_LEAGUE_STRATEGY,
                    SIMPLE_LEAGUE_CHECKPOINT,
                )
            }
            if opponent_league_kinds is not None
            else {}
        )

    def _seat_mask(self, *, trailing: int = 0) -> torch.Tensor:
        seats = torch.arange(2, device=self.learner_players.device)
        mask = seats[None, :] == self.learner_players[:, None]
        return mask.reshape(*mask.shape, *(1 for _ in range(trailing)))

    @staticmethod
    def _state_from_prefixed_mapping(
        values: Mapping[str, torch.Tensor] | None,
        prefix: str,
    ) -> tuple[torch.Tensor, torch.Tensor] | None:
        if values is None:
            return None
        hidden = values.get(f"{prefix}_hidden")
        cell = values.get(f"{prefix}_cell")
        if hidden is None or cell is None:
            raise SimplePytorchBackendError(
                f"recurrent state must contain {prefix}_hidden/{prefix}_cell"
            )
        return (
            SimpleClasherPolicyAdapter._flatten_state(hidden),
            SimpleClasherPolicyAdapter._flatten_state(cell),
        )

    @staticmethod
    def _prefixed_state_mapping(
        prefix: str,
        state: tuple[torch.Tensor, torch.Tensor],
        batch_size: int,
    ) -> dict[str, torch.Tensor]:
        return {
            f"{prefix}_hidden": state[0].reshape(batch_size, 2, -1),
            f"{prefix}_cell": state[1].reshape(batch_size, 2, -1),
        }

    @staticmethod
    def _slice_boundary(
        boundary: SimpleTensorPolicyBoundary,
        rows: torch.Tensor,
    ) -> SimpleTensorPolicyBoundary:
        return SimpleTensorPolicyBoundary(
            actor=SimpleTensorStrategyLeagueOpponent._slice_public(
                boundary.actor, rows
            ),
            critic=(
                None
                if boundary.critic is None
                else SimpleTensorStrategyLeagueOpponent._slice_public(
                    boundary.critic, rows
                )
            ),
            legal_mask=boundary.legal_mask.index_select(0, rows),
            public_action_masks=boundary.public_action_masks.index_select(0, rows),
            previous_actions=boundary.previous_actions.index_select(0, rows),
            previous_rewards=boundary.previous_rewards.index_select(0, rows),
            episode_starts=boundary.episode_starts.index_select(0, rows),
            recurrent_inputs=(
                None
                if boundary.recurrent_inputs is None
                else {
                    name: value.index_select(0, rows)
                    for name, value in boundary.recurrent_inputs.items()
                }
            ),
            decision_index=boundary.decision_index,
        )

    def _opponent_actions(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> tuple[
        torch.Tensor,
        tuple[torch.Tensor, torch.Tensor] | None,
    ]:
        batch = boundary.actor.entity_ids.shape[0]
        if self.opponent_mode == "noop":
            return (
                torch.full(
                    (batch, 2),
                    NO_OP_ACTION,
                    dtype=torch.int64,
                    device=self.learner_players.device,
                ),
                None,
            )
        if self.opponent_mode == "random":
            weights = boundary.public_action_masks.to(torch.float32).reshape(
                batch * 2, -1
            )
            sampled = torch.multinomial(weights, 1).reshape(batch, 2)
            return sampled, None
        if self.opponent_mode == "strategy":
            assert self.opponent_strategy is not None
            return self.opponent_strategy(boundary), None
        if self.opponent_mode == "league":
            assert self.opponent_league_kinds is not None
            result = torch.full(
                (batch, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=self.learner_players.device,
            )
            random_rows = self._league_rows[SIMPLE_LEAGUE_RANDOM]
            if random_rows.numel():
                random_boundary = self._slice_boundary(boundary, random_rows)
                random_weights = random_boundary.public_action_masks.to(
                    torch.float32
                ).reshape(random_rows.numel() * 2, -1)
                random_actions = torch.multinomial(random_weights, 1).reshape(
                    random_rows.numel(), 2
                )
                result.index_copy_(0, random_rows, random_actions)
            if self.opponent_strategy is not None:
                strategy_rows = self._league_rows[SIMPLE_LEAGUE_STRATEGY]
                strategy_boundary = self._slice_boundary(
                    boundary, strategy_rows
                )
                strategy_actions = self.opponent_strategy(strategy_boundary)
                result.index_copy_(0, strategy_rows, strategy_actions)
            checkpoint_next: tuple[torch.Tensor, torch.Tensor] | None = None
            if self.opponent_model is not None:
                assert self.opponent_adapter is not None
                self.opponent_model.eval()
                checkpoint_rows = self._league_rows[SIMPLE_LEAGUE_CHECKPOINT]
                checkpoint_boundary = self._slice_boundary(
                    boundary, checkpoint_rows
                )
                state = self._state_from_prefixed_mapping(
                    checkpoint_boundary.recurrent_inputs, "opponent"
                )
                (
                    checkpoint_actions,
                    _log_prob,
                    _values,
                    checkpoint_next,
                    _,
                ) = self.opponent_model.act(
                    self.opponent_adapter.inputs(checkpoint_boundary),
                    state,
                    deterministic=True,
                )
                result.index_copy_(
                    0,
                    checkpoint_rows,
                    checkpoint_actions[:, 0].reshape(
                        checkpoint_rows.numel(), 2
                    ),
                )
                checkpoint_hidden, checkpoint_cell = checkpoint_next

                def scatter_checkpoint_state(value: torch.Tensor) -> torch.Tensor:
                    return (
                        torch.zeros(
                            (batch, 2, value.shape[-1]),
                            dtype=value.dtype,
                            device=value.device,
                        )
                        .index_copy(
                            0,
                            checkpoint_rows,
                            value.reshape(checkpoint_rows.numel(), 2, -1),
                        )
                        .reshape(batch * 2, -1)
                    )

                checkpoint_next = (
                    scatter_checkpoint_state(checkpoint_hidden),
                    scatter_checkpoint_state(checkpoint_cell),
                )
            return result, checkpoint_next
        assert self.opponent_model is not None
        assert self.opponent_adapter is not None
        self.opponent_model.eval()
        state = self._state_from_prefixed_mapping(
            boundary.recurrent_inputs, "opponent"
        )
        actions, _log_prob, _values, next_state, _ = self.opponent_model.act(
            self.opponent_adapter.inputs(boundary),
            state,
            deterministic=True,
        )
        return actions[:, 0].reshape(batch, 2), next_state

    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        self.model.eval()
        batch = boundary.actor.entity_ids.shape[0]
        learner_state = self._state_from_prefixed_mapping(
            boundary.recurrent_inputs, "learner"
        )
        actions, log_prob, values, learner_next, _ = self.model.act(
            self.inputs(boundary), learner_state, deterministic=False
        )
        learner_actions = actions[:, 0].reshape(batch, 2)
        opponent_actions, opponent_next = self._opponent_actions(boundary)
        seat_mask = self._seat_mask()
        joint_actions = torch.where(seat_mask, learner_actions, opponent_actions)

        next_mapping = self._prefixed_state_mapping(
            "learner", learner_next, batch
        )
        learner_state_mask = self._seat_mask(trailing=1)
        for name in ("learner_hidden", "learner_cell"):
            next_mapping[name] = torch.where(
                learner_state_mask,
                next_mapping[name],
                torch.zeros_like(next_mapping[name]),
            )
        if opponent_next is not None:
            next_mapping.update(
                self._prefixed_state_mapping("opponent", opponent_next, batch)
            )
            for name in ("opponent_hidden", "opponent_cell"):
                next_mapping[name] = torch.where(
                    ~learner_state_mask,
                    next_mapping[name],
                    torch.zeros_like(next_mapping[name]),
                )
                if self.opponent_mode == "league":
                    assert self.opponent_league_kinds is not None
                    checkpoint_rows = (
                        self.opponent_league_kinds == SIMPLE_LEAGUE_CHECKPOINT
                    )[:, None, None]
                    next_mapping[name] = torch.where(
                        checkpoint_rows,
                        next_mapping[name],
                        torch.zeros_like(next_mapping[name]),
                    )
        return SimpleTensorPolicyDecision(
            actions=joint_actions,
            next_recurrent_inputs=next_mapping,
            storage={
                "log_prob": log_prob[:, 0].reshape(batch, 2),
                "value": values[:, 0].reshape(batch, 2),
            },
        )

    def bootstrap_values(self, boundary: SimpleTensorPolicyBoundary) -> torch.Tensor:
        output = self.model.forward(
            self.inputs(boundary),
            self._state_from_prefixed_mapping(
                boundary.recurrent_inputs, "learner"
            ),
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
        second = (
            first
            if mirror_match
            else artifact.decks[(2 * index + 1) % len(artifact.decks)]
        )
        result.append((first, second))
    return tuple(result)


def _learner_deck_rows(
    artifact: SimpleSupportedDeckArtifact,
    *,
    batch_size: int,
    learner_deck_name: str,
    opponent_deck_name_by_row: tuple[str | None, ...] = (),
) -> tuple[
    tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
    tuple[int, ...],
    tuple[str, ...],
]:
    try:
        learner_index = artifact.deck_names.index(learner_deck_name)
    except ValueError as error:
        raise SimplePytorchBackendError(
            f"unknown learner deck {learner_deck_name!r}"
        ) from error
    learner_deck = artifact.decks[learner_index]
    opponents = tuple(
        (name, deck)
        for index, (name, deck) in enumerate(
            zip(artifact.deck_names, artifact.decks, strict=True)
        )
        if index != learner_index
    )
    if not opponents:
        raise SimplePytorchBackendError(
            "stationary training requires at least one opponent deck"
        )
    if opponent_deck_name_by_row and len(opponent_deck_name_by_row) != batch_size:
        raise SimplePytorchBackendError(
            "opponent deck override must have one entry per battle row"
        )
    rows: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    learner_players: list[int] = []
    opponent_names: list[str] = []
    for row in range(batch_size):
        learner_player = row % 2
        override_name = (
            opponent_deck_name_by_row[row]
            if opponent_deck_name_by_row
            else None
        )
        if override_name is None:
            opponent_name, opponent_deck = opponents[(row // 2) % len(opponents)]
        else:
            try:
                override_index = artifact.deck_names.index(override_name)
            except ValueError as error:
                raise SimplePytorchBackendError(
                    f"unknown checkpoint opponent deck {override_name!r}"
                ) from error
            opponent_name = artifact.deck_names[override_index]
            opponent_deck = artifact.decks[override_index]
        rows.append(
            (learner_deck, opponent_deck)
            if learner_player == 0
            else (opponent_deck, learner_deck)
        )
        learner_players.append(learner_player)
        opponent_names.append(opponent_name)
    return tuple(rows), tuple(learner_players), tuple(opponent_names)


@dataclass(frozen=True)
class SimplePytorchBackendMetadata:
    backend_id: str
    execution_mode: str
    actor_semantics_id: str
    opponent_mode: str
    learner_only: bool
    learner_deck_name: str | None
    learner_players: tuple[int, ...]
    opponent_deck_names: tuple[str, ...]
    opponent_checkpoint_sha256: str | None
    checkpoint_opponent_deck_name: str | None
    opponent_strategy: str | None
    opponent_strategy_schedule: tuple[str, ...]
    opponent_league_schedule: tuple[str, ...]
    opponent_schedule_unit: str | None
    fresh_only: bool
    canonical_lane_globals: bool
    public_action_mask_contract_version: int
    public_action_mask_semantics_id: str
    public_action_mask_semantics_digest: str
    public_action_mask_semantics: Mapping[str, Any]
    supported_decks_sha256: str
    support_profile_sha256: str
    typed_vocabulary_sha256: str
    reward_contract_id: str
    reward_contract_digest: str
    reward_contract_metadata: Mapping[str, Any]
    max_entities: int
    max_effects: int


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
        opponent_mode: Literal[
            "selfplay", "noop", "random", "strategy", "league", "checkpoint"
        ] = "selfplay",
        opponent_model: ClasherPolicy | None = None,
        opponent_checkpoint_sha256: str | None = None,
        opponent_strategy: str | None = None,
        opponent_strategy_schedule: tuple[str, ...] = (),
        opponent_league_schedule: tuple[SimpleLeagueSpec, ...] = (),
        learner_deck_name: str = "Hog 2.6 Cycle",
        checkpoint_opponent_deck_name: str | None = None,
        max_effects: int = 128,
        _execution_mode_override: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise SimplePytorchBackendError("simple backend needs at least one row")
        if max_effects < 1:
            raise SimplePytorchBackendError(
                "simple backend effect capacity must be positive"
            )
        if opponent_mode not in {
            "selfplay",
            "noop",
            "random",
            "strategy",
            "league",
            "checkpoint",
        }:
            raise SimplePytorchBackendError(
                f"unsupported simple opponent mode: {opponent_mode!r}"
            )
        if opponent_mode != "selfplay" and mirror_match:
            raise SimplePytorchBackendError(
                "stationary simple opponents require asymmetric deck rows"
            )
        normalized_league = (
            opponent_league_schedule
            if opponent_league_schedule
            else tuple(("strategy", name) for name in opponent_strategy_schedule)
        )
        if opponent_mode == "checkpoint" and opponent_model is None:
            raise SimplePytorchBackendError(
                "checkpoint simple opponent requires a loaded policy"
            )
        league_checkpoint_values = {
            value for kind, value in normalized_league if kind == "checkpoint"
        }
        if opponent_mode == "league" and len(league_checkpoint_values) > 1:
            raise SimplePytorchBackendError(
                "simple mixed league supports one unique checkpoint policy"
            )
        checkpoint_required = opponent_mode == "checkpoint" or bool(
            league_checkpoint_values
        )
        if checkpoint_required and opponent_model is None:
            raise SimplePytorchBackendError(
                "checkpoint simple opponent requires a loaded policy"
            )
        if not checkpoint_required and opponent_model is not None:
            raise SimplePytorchBackendError(
                f"{opponent_mode} simple opponent cannot own a policy"
            )
        if bool(opponent_checkpoint_sha256) != (opponent_model is not None):
            raise SimplePytorchBackendError(
                "opponent checkpoint identity must accompany its policy"
            )
        if opponent_mode == "strategy" and opponent_strategy not in STRATEGY_NAMES:
            raise SimplePytorchBackendError(
                "strategy simple opponent requires a known strategy"
            )
        if opponent_mode != "strategy" and opponent_strategy is not None:
            raise SimplePytorchBackendError(
                f"{opponent_mode} simple opponent cannot name a strategy"
            )
        if opponent_mode == "league":
            if batch_size % 2:
                raise SimplePytorchBackendError(
                    "simple league requires an even batch for paired seats"
                )
            if len(set(normalized_league)) < 2:
                raise SimplePytorchBackendError(
                    "simple league requires at least two distinct opponents"
                )
            if any(
                kind not in {"random", "strategy", "checkpoint"}
                for kind, _value in normalized_league
            ):
                raise SimplePytorchBackendError(
                    "simple league contains an unknown opponent kind"
                )
            if any(
                kind == "strategy" and value not in STRATEGY_NAMES
                for kind, value in normalized_league
            ):
                raise SimplePytorchBackendError(
                    "simple league contains an unknown strategy"
                )
            if any(
                (kind == "random" and value is not None)
                or (kind != "random" and value is None)
                for kind, value in normalized_league
            ):
                raise SimplePytorchBackendError(
                    "simple league opponent payload is malformed"
                )
        elif normalized_league:
            raise SimplePytorchBackendError(
                f"{opponent_mode} simple opponent cannot own a league schedule"
            )
        if checkpoint_opponent_deck_name is not None and not checkpoint_required:
            raise SimplePytorchBackendError(
                "checkpoint opponent deck requires a checkpoint policy"
            )
        row_league_schedule = (
            tuple(
                normalized_league[(index // 2) % len(normalized_league)]
                for index in range(batch_size)
            )
            if opponent_mode == "league"
            else ()
        )
        if (
            not builder.canonical_lane_globals
            or not model.config.canonical_lane_globals
        ):
            raise SimplePytorchBackendError("simple backend requires canonical lanes")
        if model.config.actor_observation_domain not in {
            "simulator-exact",
            "causal-frame-v1",
        }:
            raise SimplePytorchBackendError(
                "simple backend requires simulator-exact or causal-frame policy input"
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
        learner_only = opponent_mode != "selfplay"
        if learner_only:
            deck_rows, learner_players_tuple, opponent_deck_names = (
                _learner_deck_rows(
                    artifact,
                    batch_size=batch_size,
                    learner_deck_name=learner_deck_name,
                    opponent_deck_name_by_row=(
                        tuple(
                            checkpoint_opponent_deck_name
                            if kind == "checkpoint"
                            else None
                            for kind, _value in row_league_schedule
                        )
                        if opponent_mode == "league"
                        and checkpoint_opponent_deck_name is not None
                        else tuple(
                            checkpoint_opponent_deck_name
                            for _index in range(batch_size)
                        )
                        if opponent_mode == "checkpoint"
                        and checkpoint_opponent_deck_name is not None
                        else ()
                    ),
                )
            )
        else:
            deck_rows = _deck_rows(
                artifact,
                batch_size=batch_size,
                mirror_match=mirror_match,
            )
            learner_players_tuple = ()
            opponent_deck_names = ()
        runtime = setup.create_runtime(
            deck_rows,
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            canonical_lane_globals=True,
            max_entities=builder.max_entities,
            max_effects=max_effects,
            include_privileged_critic=True,
        )
        execution_mode = self._resolve_execution_mode(
            runtime.device,
            override=_execution_mode_override,
        )
        rollout_runtime: Any = runtime
        if execution_mode == SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH:
            example_actions = torch.full(
                (batch_size, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=runtime.device,
            )
            # Capture failure is a hard construction failure. Production must
            # never silently fall back to the eager CUDA path, whose thousands
            # of per-tick submissions violate this backend's execution contract.
            rollout_runtime = SimpleCudaGraphRunner(runtime, example_actions)
        reward = SimpleRewardV2Config(gamma=gamma)
        bridge = SimpleGymRolloutBridge(
            rollout_runtime,
            decision_interval=decision_interval,
            reward_v2_config=reward,
            strict_reset_check=False,
        )
        self.public_mask_tables = _compile_public_mask_v2_tables(
            builder, setup, entity_lookup
        )
        public_mask_provider = SimpleCollectorPublicMaskV2Provider(
            SimplePublicMaskV2Provider(self.public_mask_tables)
        )
        self.learner_players = torch.as_tensor(
            learner_players_tuple,
            dtype=torch.int64,
            device=device,
        )
        self.learner_only = learner_only
        self.opponent_model = opponent_model
        self.policy: SimpleClasherPolicyAdapter
        if learner_only:
            row_strategy_schedule = tuple(
                cast(str, value)
                for kind, value in row_league_schedule
                if kind == "strategy"
            )
            tensor_strategy = (
                SimpleTensorStrategyLeagueOpponent(
                    builder,
                    strategy_names=row_strategy_schedule,
                    device=device,
                )
                if opponent_mode == "league" and row_strategy_schedule
                else SimpleTensorStrategyOpponent(
                    builder,
                    strategy_name=cast(str, opponent_strategy),
                    device=device,
                )
                if opponent_mode == "strategy"
                else None
            )
            self.policy = SimpleAsymmetricClasherPolicyAdapter(
                model,
                learner_players=self.learner_players,
                opponent_mode=cast(
                    Literal[
                        "noop", "random", "strategy", "checkpoint", "league"
                    ],
                    opponent_mode,
                ),
                opponent_model=opponent_model,
                opponent_strategy=tensor_strategy,
                opponent_league_kinds=(
                    torch.as_tensor(
                        [
                            {
                                "random": SIMPLE_LEAGUE_RANDOM,
                                "strategy": SIMPLE_LEAGUE_STRATEGY,
                                "checkpoint": SIMPLE_LEAGUE_CHECKPOINT,
                            }[kind]
                            for kind, _value in row_league_schedule
                        ],
                        dtype=torch.int64,
                        device=device,
                    )
                    if opponent_mode == "league"
                    else None
                ),
            )
        else:
            self.policy = SimpleClasherPolicyAdapter(model)
        self.collector = SimpleTensorCollector(
            bridge,
            public_mask_provider=public_mask_provider,
            policy=self.policy,
            strict_host_validation=False,
        )
        reward_metadata = simple_reward_v2_metadata(reward)
        self.metadata = SimplePytorchBackendMetadata(
            backend_id=SIMPLE_TENSOR_BACKEND_ID,
            execution_mode=execution_mode,
            actor_semantics_id=SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
            opponent_mode=opponent_mode,
            learner_only=learner_only,
            learner_deck_name=learner_deck_name if learner_only else None,
            learner_players=learner_players_tuple,
            opponent_deck_names=opponent_deck_names,
            opponent_checkpoint_sha256=opponent_checkpoint_sha256,
            checkpoint_opponent_deck_name=checkpoint_opponent_deck_name,
            opponent_strategy=opponent_strategy,
            opponent_strategy_schedule=(
                row_strategy_schedule
                if opponent_mode == "league"
                and all(kind == "strategy" for kind, _value in row_league_schedule)
                else ()
            ),
            opponent_league_schedule=(
                tuple(
                    "random"
                    if kind == "random"
                    else f"strategy:{value}"
                    if kind == "strategy"
                    else f"checkpoint:{opponent_checkpoint_sha256}"
                    for kind, value in row_league_schedule
                )
                if opponent_mode == "league"
                else ()
            ),
            opponent_schedule_unit=(
                "logical-matchup-pair" if opponent_mode == "league" else None
            ),
            fresh_only=True,
            canonical_lane_globals=True,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
            public_action_mask_semantics_id=self.public_mask_tables.semantics_id,
            public_action_mask_semantics_digest=(
                self.public_mask_tables.semantics_digest
            ),
            public_action_mask_semantics=self.public_mask_tables.semantics,
            supported_decks_sha256=artifact.sha256,
            support_profile_sha256=artifact.support_profile_sha256,
            typed_vocabulary_sha256=vocabulary.sha256,
            reward_contract_id=SIMPLE_REWARD_V2_CONTRACT_ID,
            reward_contract_digest=str(reward_metadata["reward_contract_digest"]),
            reward_contract_metadata=reward_metadata,
            max_entities=builder.max_entities,
            max_effects=max_effects,
        )
        self._opponent_recurrent_state = (
            opponent_model.initial_state(batch_size, device=device)
            if opponent_model is not None
            else None
        )

    @staticmethod
    def _resolve_execution_mode(
        device: torch.device,
        *,
        override: str | None,
    ) -> str:
        """Select one explicit execution contract without fallback."""

        requested = (
            SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH
            if override is None and device.type == "cuda"
            else SIMPLE_PYTORCH_EXECUTION_EAGER
            if override is None
            else override
        )
        if requested not in SIMPLE_PYTORCH_EXECUTION_MODES:
            raise SimplePytorchBackendError(
                f"unsupported simple-pytorch execution mode: {requested!r}"
            )
        if requested == SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH and device.type != "cuda":
            raise SimplePytorchBackendError(
                "cuda-graph execution requires a CUDA actor device"
            )
        return requested

    def _assert_execution_mode(self) -> None:
        runtime = self.collector.bridge.runtime
        actual = (
            SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH
            if isinstance(runtime, SimpleCudaGraphRunner)
            else SIMPLE_PYTORCH_EXECUTION_EAGER
        )
        if self.metadata.execution_mode != actual:
            raise SimplePytorchBackendError(
                "simple-pytorch execution mode metadata does not match the runtime"
            )

    @property
    def batch_size(self) -> int:
        return cast(int, self.collector.batch_size)

    @staticmethod
    def _agent_major(value: torch.Tensor) -> torch.Tensor:
        order = (1, 2, 0, *range(3, value.ndim))
        return value.permute(order).reshape(
            value.shape[1] * value.shape[2], value.shape[0], *value.shape[3:]
        )

    def _learner_major(self, value: torch.Tensor) -> torch.Tensor:
        if not self.learner_only:
            raise SimplePytorchBackendError(
                "learner-major projection requires stationary opponents"
            )
        order = (1, 2, 0, *range(3, value.ndim))
        row_major = value.permute(order)
        rows = torch.arange(self.batch_size, device=value.device)
        return row_major[rows, self.learner_players]

    def _learner_boundary(self, value: torch.Tensor) -> torch.Tensor:
        rows = torch.arange(self.batch_size, device=value.device)
        return value[rows, self.learner_players]

    def _agent_state_to_joint(
        self,
        value: torch.Tensor,
        *,
        players: torch.Tensor,
    ) -> torch.Tensor:
        if value.shape[0] != self.batch_size:
            raise SimplePytorchBackendError(
                "stationary recurrent state must have one row per battle"
            )
        joint = torch.zeros(
            (self.batch_size, 2, *value.shape[1:]),
            dtype=value.dtype,
            device=value.device,
        )
        rows = torch.arange(self.batch_size, device=value.device)
        joint[rows, players] = value
        return joint

    def _joint_recurrent_inputs(
        self,
        recurrent_state: tuple[torch.Tensor, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        learner = {
            "learner_hidden": self._agent_state_to_joint(
                recurrent_state[0], players=self.learner_players
            ),
            "learner_cell": self._agent_state_to_joint(
                recurrent_state[1], players=self.learner_players
            ),
        }
        if self._opponent_recurrent_state is not None:
            opponent_players = 1 - self.learner_players
            learner.update(
                {
                    "opponent_hidden": self._agent_state_to_joint(
                        self._opponent_recurrent_state[0],
                        players=opponent_players,
                    ),
                    "opponent_cell": self._agent_state_to_joint(
                        self._opponent_recurrent_state[1],
                        players=opponent_players,
                    ),
                }
            )
        return learner

    def _extract_agent_state(
        self,
        mapping: Mapping[str, torch.Tensor] | None,
        *,
        prefix: str,
        players: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if mapping is None:
            raise SimplePytorchBackendError("collector lost recurrent bootstrap state")
        rows = torch.arange(self.batch_size, device=players.device)
        try:
            hidden = mapping[f"{prefix}_hidden"][rows, players]
            cell = mapping[f"{prefix}_cell"][rows, players]
        except KeyError as error:
            raise SimplePytorchBackendError(
                f"collector lost {prefix} recurrent bootstrap state"
            ) from error
        return hidden, cell

    @staticmethod
    def _confidence_tensors(
        batch: SimpleTensorDecisionBatch,
    ) -> tuple[torch.Tensor, ...]:
        entity = batch.actor.entity_mask.to(torch.float32)
        entity_features = entity[..., None].expand_as(batch.actor.entity_features)
        hand = torch.ones_like(batch.actor.hand_ids, dtype=torch.float32)
        global_features = torch.ones_like(batch.actor.global_features)
        return entity, entity_features, hand, global_features

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
        initial_hidden = recurrent_state[0].detach().clone()
        initial_cell = recurrent_state[1].detach().clone()
        recurrent_inputs = (
            self._joint_recurrent_inputs(recurrent_state)
            if self.learner_only
            else {
                "hidden": recurrent_state[0].reshape(batch, 2, -1),
                "cell": recurrent_state[1].reshape(batch, 2, -1),
            }
        )
        decision = self.collector.collect(
            rollout_steps, recurrent_inputs=recurrent_inputs
        )
        if decision.critic is None:
            raise SimplePytorchBackendError("training collection requires a critic")
        confidence = self._confidence_tensors(decision)
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
        project = self._learner_major if self.learner_only else self._agent_major
        bootstrap_values_full = bootstrap_values.reshape(batch, 2)
        device_exports = {
            "entity_ids": project(decision.actor.entity_ids),
            "entity_features": project(decision.actor.entity_features),
            "entity_mask": project(decision.actor.entity_mask),
            "hand_ids": project(decision.actor.hand_ids),
            "global_features": project(decision.actor.global_features),
            "entity_id_confidence": project(confidence[0]),
            "entity_feature_confidence": project(confidence[1]),
            "hand_id_confidence": project(confidence[2]),
            "global_feature_confidence": project(confidence[3]),
            "action_masks": project(decision.public_action_masks),
            "previous_actions": project(decision.previous_actions),
            "previous_rewards": project(decision.previous_rewards),
            "episode_starts": project(decision.episode_starts),
            "critic_entity_ids": project(decision.critic.entity_ids),
            "critic_entity_features": project(decision.critic.entity_features),
            "critic_entity_mask": project(decision.critic.entity_mask),
            "critic_card_ids": project(decision.critic.card_ids),
            "critic_global_features": project(decision.critic.global_features),
            "actions": project(decision.actions),
            "old_log_probs": project(storage["log_prob"]),
            "old_values": project(storage["value"]),
            "rewards": project(decision.rewards),
            "dones": project(decision.done[..., None].expand(-1, -1, 2)),
            "initial_hidden": initial_hidden,
            "initial_cell": initial_cell,
            "bootstrap_values": (
                self._learner_boundary(bootstrap_values_full)
                if self.learner_only
                else bootstrap_values.detach()
            ),
            "_done_rows": decision.done.detach(),
            "_winner_rows": decision.winner.detach(),
            "_learner_players": self.learner_players,
            "_bootstrap_previous_actions": (
                self._learner_boundary(decision.bootstrap.previous_actions)
                if self.learner_only
                else decision.bootstrap.previous_actions.reshape(-1)
            ),
            "_bootstrap_previous_rewards": (
                self._learner_boundary(decision.bootstrap.previous_rewards)
                if self.learner_only
                else decision.bootstrap.previous_rewards.reshape(-1)
            ),
            "_bootstrap_episode_starts": (
                self._learner_boundary(decision.bootstrap.episode_starts)
                if self.learner_only
                else decision.bootstrap.episode_starts.reshape(-1)
            ),
        }
        staged = _CoalescedCpuStaging(device_exports).finish()
        done = staged.pop("_done_rows")
        winner = staged.pop("_winner_rows")
        learner_players = staged.pop("_learner_players")
        terminal_winner = winner[done]
        previous_actions = staged.pop("_bootstrap_previous_actions")
        previous_rewards = staged.pop("_bootstrap_previous_rewards")
        episode_starts = staged.pop("_bootstrap_episode_starts")
        arrays: dict[str, Any] = {
            **staged,
            "opponent_history_ids": zeros_history_i64,
            "opponent_history_ages": zeros_history_f32,
            "opponent_seen_card_ids": zeros_seen,
            "opponent_play_event_ids": np.zeros((agents, steps), dtype=np.int64),
            "opponent_play_event_confidence": np.zeros(
                (agents, steps), dtype=np.float32
            ),
            "episodes_finished": int(np.count_nonzero(done)),
            "wins": int(
                np.count_nonzero(
                    terminal_winner
                    == (
                        np.broadcast_to(learner_players, done.shape)[done]
                        if self.learner_only
                        else 0
                    )
                )
            ),
            "losses": int(
                np.count_nonzero(
                    terminal_winner
                    == (
                        1 - np.broadcast_to(learner_players, done.shape)[done]
                        if self.learner_only
                        else 1
                    )
                )
            ),
            "draws": int(np.count_nonzero(terminal_winner < 0)),
        }
        if self.learner_only:
            bootstrap_state = self._extract_agent_state(
                decision.bootstrap.recurrent_inputs,
                prefix="learner",
                players=self.learner_players,
            )
            if self.opponent_model is not None:
                self._opponent_recurrent_state = self._extract_agent_state(
                    decision.bootstrap.recurrent_inputs,
                    prefix="opponent",
                    players=1 - self.learner_players,
                )
        else:
            mapped_state = self.policy.state_from_mapping(
                decision.bootstrap.recurrent_inputs
            )
            if mapped_state is None:
                raise SimplePytorchBackendError(
                    "collector lost recurrent bootstrap state"
                )
            bootstrap_state = mapped_state
        return (
            arrays,
            (bootstrap_state[0].detach(), bootstrap_state[1].detach()),
            previous_actions,
            previous_rewards,
            episode_starts,
        )

    def checkpoint_metadata(self) -> dict[str, Any]:
        self._assert_execution_mode()
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
    "SIMPLE_PYTORCH_EXECUTION_CUDA_GRAPH",
    "SIMPLE_PYTORCH_EXECUTION_EAGER",
    "SIMPLE_PYTORCH_EXECUTION_MODES",
    "CurrentClientTypedVocabulary",
    "SimplePytorchBackendError",
    "SimplePytorchBackendMetadata",
    "SimplePytorchTrainingCollector",
    "SimpleSupportedDeckArtifact",
    "load_current_client_typed_vocabulary",
    "load_simple_supported_decks",
]
