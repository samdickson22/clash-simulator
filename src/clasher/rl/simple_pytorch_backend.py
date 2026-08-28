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
from typing import Any, Final, cast

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

from .model import ClasherPolicy, PolicyInputs
from .simple_tensor_collector import (
    SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
    SIMPLE_TENSOR_BACKEND_ID,
    SimpleTensorCollector,
    SimpleTensorDecisionBatch,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
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


@dataclass(frozen=True)
class SimplePytorchBackendMetadata:
    backend_id: str
    execution_mode: str
    actor_semantics_id: str
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
        _execution_mode_override: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise SimplePytorchBackendError("simple backend needs at least one row")
        if (
            not builder.canonical_lane_globals
            or not model.config.canonical_lane_globals
        ):
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
        execution_mode = self._resolve_execution_mode(
            runtime.device,
            override=_execution_mode_override,
        )
        rollout_runtime = runtime
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
        recurrent_inputs = {
            "hidden": recurrent_state[0].reshape(batch, 2, -1),
            "cell": recurrent_state[1].reshape(batch, 2, -1),
        }
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
        device_exports = {
            "entity_ids": self._agent_major(decision.actor.entity_ids),
            "entity_features": self._agent_major(decision.actor.entity_features),
            "entity_mask": self._agent_major(decision.actor.entity_mask),
            "hand_ids": self._agent_major(decision.actor.hand_ids),
            "global_features": self._agent_major(decision.actor.global_features),
            "entity_id_confidence": self._agent_major(confidence[0]),
            "entity_feature_confidence": self._agent_major(confidence[1]),
            "hand_id_confidence": self._agent_major(confidence[2]),
            "global_feature_confidence": self._agent_major(confidence[3]),
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
            "dones": self._agent_major(decision.done[..., None].expand(-1, -1, 2)),
            "initial_hidden": initial_hidden,
            "initial_cell": initial_cell,
            "bootstrap_values": bootstrap_values.detach(),
            "_done_rows": decision.done.detach(),
            "_winner_rows": decision.winner.detach(),
            "_bootstrap_previous_actions": (
                decision.bootstrap.previous_actions.reshape(-1)
            ),
            "_bootstrap_previous_rewards": (
                decision.bootstrap.previous_rewards.reshape(-1)
            ),
            "_bootstrap_episode_starts": (
                decision.bootstrap.episode_starts.reshape(-1)
            ),
        }
        staged = _CoalescedCpuStaging(device_exports).finish()
        done = staged.pop("_done_rows")
        winner = staged.pop("_winner_rows")
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
            "wins": int(np.count_nonzero(terminal_winner == 0)),
            "losses": int(np.count_nonzero(terminal_winner == 1)),
            "draws": int(np.count_nonzero(terminal_winner < 0)),
        }
        bootstrap_state = self.policy.state_from_mapping(
            decision.bootstrap.recurrent_inputs
        )
        if bootstrap_state is None:
            raise SimplePytorchBackendError("collector lost recurrent bootstrap state")
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
