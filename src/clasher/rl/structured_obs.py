from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from clasher.arena import TileGrid
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.entities import Building, ChainLightning, RollingProjectile, TimedExplosive
from clasher.kinematics import logic_speed_to_tiles_per_second, logic_time_milliseconds
from clasher.unit_traits import is_airborne_target, unit_mass

from .card_semantics import (
    SEMANTIC_EXTRA_FEATURE_INDICES,
    SEMANTIC_FEATURE_NAMES,
    semantic_card_profile,
)
from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .deck_pool import load_deck_pool, unique_cards_from_decks
from .own_card_history import AcceptedOwnPlay

ENTITY_FEATURE_SIZE = 32
ACTOR_GLOBAL_SIZE = 18
CRITIC_GLOBAL_SIZE = 20
VISIBLE_CARD_SLOTS = NUM_HAND_SLOTS + 1
PRIVILEGED_CARD_SLOTS = 2 * VISIBLE_CARD_SLOTS
DEFAULT_MAX_ENTITIES = 128
DEFAULT_PUBLIC_HISTORY_SLOTS = 4
TYPED_TOKEN_NAMESPACES = frozenset(
    {
        "card_action",
        "troop_body",
        "building_body",
        "projectile",
        "area_effect",
        "tower",
    }
)


def _canonical_card_token_name(name: str, definitions: dict[str, Any]) -> str:
    """Resolve deck aliases even though the loader also exposes alias keys."""

    aliased = resolve_card_name(name)
    return resolve_card_name(aliased, definitions)


@lru_cache(maxsize=1)
def _crown_tower_observation_stats() -> dict[str, Any]:
    """Return the same tower stat payloads used by live simulator entities.

    Crown Towers are arena entities rather than playable catalog cards, so
    ``CardDataLoader.get_card`` cannot supply their static observation fields.
    Build the authoritative runtime payloads once instead of leaving imported
    replay towers with zero range, damage, and collision radius.
    """

    battle = BattleState()
    stats_by_name: dict[str, Any] = {}
    for entity in battle.entities.values():
        stats = getattr(entity, "card_stats", None)
        name = str(getattr(stats, "name", ""))
        if name in {"Tower", "KingTower"}:
            stats_by_name.setdefault(name, stats)
    if set(stats_by_name) != {"Tower", "KingTower"}:
        raise RuntimeError("Live battle did not provide both Crown Tower stat payloads")
    return stats_by_name


class EntityCapacityError(RuntimeError):
    """Raised instead of silently discarding a visible combat object."""


@dataclass(frozen=True)
class StructuredObservationSpec:
    token_names: tuple[str, ...]
    max_entities: int
    entity_feature_size: int = ENTITY_FEATURE_SIZE
    actor_global_size: int = ACTOR_GLOBAL_SIZE
    critic_global_size: int = CRITIC_GLOBAL_SIZE
    public_history_slots: int = 0
    public_seen_card_slots: int = 0
    public_entity_levels: bool = False
    public_hand_levels: bool = False

    @property
    def num_tokens(self) -> int:
        return len(self.token_names)


@dataclass(frozen=True)
class StructuredObservation:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    critic_entity_ids: np.ndarray
    critic_entity_features: np.ndarray
    critic_entity_mask: np.ndarray
    critic_card_ids: np.ndarray
    critic_global_features: np.ndarray
    opponent_history_ids: np.ndarray
    opponent_history_ages: np.ndarray
    opponent_seen_card_ids: np.ndarray
    entity_id_confidence: np.ndarray | None = None
    entity_feature_confidence: np.ndarray | None = None
    hand_id_confidence: np.ndarray | None = None
    global_feature_confidence: np.ndarray | None = None
    own_last_play: AcceptedOwnPlay | None = None
    # None means the current source cannot establish match lifecycle.
    terminal: bool | None = None
    # Whether public coordinates were rotated 180 degrees from arena coordinates.
    board_rotated: bool | None = None
    entity_levels: np.ndarray | None = None
    entity_level_confidence: np.ndarray | None = None
    hand_levels: np.ndarray | None = None
    hand_level_confidence: np.ndarray | None = None


@dataclass(frozen=True)
class ActorObservation:
    """Public policy inputs without the unused privileged critic payload."""

    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray
    opponent_history_ids: np.ndarray
    opponent_history_ages: np.ndarray
    opponent_seen_card_ids: np.ndarray
    own_last_play: AcceptedOwnPlay | None = None
    # None means the current source cannot establish match lifecycle.
    terminal: bool | None = None
    # Whether public coordinates were rotated 180 degrees from arena coordinates.
    board_rotated: bool | None = None
    entity_levels: np.ndarray | None = None
    entity_level_confidence: np.ndarray | None = None
    hand_levels: np.ndarray | None = None
    hand_level_confidence: np.ndarray | None = None


def _walk_named_payloads(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        for child in value:
            yield from _walk_named_payloads(child)
        return
    if not isinstance(value, dict):
        return
    name = value.get("name")
    if isinstance(name, str) and name:
        yield name
    for key, child in value.items():
        # Enabled decks use their base payloads. Evolution/hero alternates
        # would create identities the actor can never observe in this gym.
        if key in {"evolvedSpellsData", "heroData"}:
            continue
        yield from _walk_named_payloads(child)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _unit_clip_numpy(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _unit_clip(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _range_clip_numpy(value: float, lower: float, upper: float) -> float:
    return float(np.clip(value, lower, upper))


def _range_clip_scalar(value: float, lower: float, upper: float) -> float:
    if value < lower:
        return float(lower)
    if value > upper:
        return float(upper)
    return float(value)


_range_clip = _range_clip_scalar


class StructuredObservationBuilder:
    """Build actor-public and critic-privileged entity observations.

    The actor side intentionally excludes the opponent's hand, cycle, elixir,
    internal target IDs, and invisible enemy objects. The critic side is used
    only while training and receives the full Markov state.
    """

    PAD_TOKEN = "<pad>"
    UNKNOWN_TOKEN = "<unknown>"

    def __init__(
        self,
        *,
        decks_path: str | Path = "decks.json",
        card_loader: CardDataLoader | None = None,
        card_vocab: Sequence[str] | None = None,
        max_entities: int = DEFAULT_MAX_ENTITIES,
        canonical_perspective: bool = True,
        canonical_lane_globals: bool = False,
        token_names: Sequence[str] | None = None,
        card_semantics_version: int = 1,
        public_history_slots: int = 0,
        public_seen_card_slots: int = 0,
        public_entity_levels: bool = False,
        public_hand_levels: bool = False,
    ) -> None:
        if max_entities <= 0:
            raise ValueError("max_entities must be positive")
        if card_semantics_version not in {1, 2, 3, 4}:
            raise ValueError("card_semantics_version must be 1, 2, 3, or 4")
        if public_history_slots < 0:
            raise ValueError("public_history_slots must be non-negative")
        if public_seen_card_slots < 0:
            raise ValueError("public_seen_card_slots must be non-negative")
        if public_hand_levels and not public_entity_levels:
            raise ValueError("public hand levels require public entity levels")
        self.public_hand_levels = bool(public_hand_levels)
        self.public_entity_levels = bool(public_entity_levels)
        self.max_entities = int(max_entities)
        self.canonical_perspective = bool(canonical_perspective)
        self.canonical_lane_globals = bool(canonical_lane_globals)
        self.card_semantics_version = int(card_semantics_version)
        self.public_history_slots = int(public_history_slots)
        self.public_seen_card_slots = int(public_seen_card_slots)
        self.loader = card_loader if card_loader is not None else CardDataLoader()
        definitions = self.loader.load_card_definitions()

        if card_vocab is None:
            card_vocab = unique_cards_from_decks(load_deck_pool(decks_path))
        self.card_vocab = tuple(card_vocab)

        if token_names is None:
            names = {"Tower", "KingTower", *self.card_vocab}
            for card_name in self.card_vocab:
                stats = self.loader.get_card(card_name)
                if stats is None:
                    continue
                names.update(_walk_named_payloads(getattr(stats, "_raw_entry", {}) or {}))
            # Keep both deck-facing aliases and canonical data names. They are
            # semantically related through public stat features, but distinct
            # IDs avoid accidental collisions between genuinely different
            # spawned payloads.
            names.update(resolve_card_name(name, definitions) for name in tuple(names))
            ordered = [self.PAD_TOKEN, self.UNKNOWN_TOKEN, *sorted(name for name in names if name)]
        else:
            ordered = list(token_names)
            if len(ordered) < 2 or ordered[:2] != [self.PAD_TOKEN, self.UNKNOWN_TOKEN]:
                raise ValueError("token_names must begin with <pad>, <unknown>")

        self.token_names = tuple(ordered)
        self._name_to_id = {name: idx for idx, name in enumerate(self.token_names)}
        self._uses_typed_tokens = any(
            self._typed_token_parts(name) is not None for name in self.token_names[2:]
        )
        for name in tuple(self._name_to_id):
            if name.startswith("<"):
                continue
            typed = self._typed_token_parts(name)
            if typed is None:
                resolved = _canonical_card_token_name(name, definitions)
                self._name_to_id.setdefault(resolved, self._name_to_id[name])
            elif typed[0] == "card_action":
                resolved = _canonical_card_token_name(typed[1], definitions)
                self._name_to_id.setdefault(
                    f"card_action:{resolved}", self._name_to_id[name]
                )

        self.spec = StructuredObservationSpec(
            token_names=self.token_names,
            max_entities=self.max_entities,
            public_history_slots=self.public_history_slots,
            public_seen_card_slots=self.public_seen_card_slots,
            public_entity_levels=self.public_entity_levels,
            public_hand_levels=self.public_hand_levels,
        )
        self.card_stat_features = self._build_card_stat_features()

    @staticmethod
    def _typed_token_parts(name: str) -> tuple[str, str] | None:
        namespace, separator, canonical = str(name).partition(":")
        if separator and namespace in TYPED_TOKEN_NAMESPACES and canonical:
            return namespace, canonical
        return None

    def token_id(
        self,
        name: str | None,
        *,
        namespace: str | None = None,
    ) -> int:
        if not name:
            return self._name_to_id[self.UNKNOWN_TOKEN]
        direct = self._name_to_id.get(str(name))
        if direct is not None:
            return direct
        resolved = _canonical_card_token_name(
            str(name), self.loader.load_card_definitions()
        )
        if self._uses_typed_tokens:
            selected_namespace = namespace or "card_action"
            if selected_namespace not in TYPED_TOKEN_NAMESPACES:
                raise ValueError(f"unknown typed token namespace {selected_namespace!r}")
            for canonical in (str(name), resolved):
                typed = self._name_to_id.get(f"{selected_namespace}:{canonical}")
                if typed is not None:
                    return typed
            return self._name_to_id[self.UNKNOWN_TOKEN]
        return self._name_to_id.get(resolved, self._name_to_id[self.UNKNOWN_TOKEN])

    def card_name_for_token_id(self, token_id: int) -> str | None:
        """Return a loader-facing card name only for playable card tokens."""

        if not 0 < token_id < len(self.token_names):
            return None
        token_name = self.token_names[token_id]
        typed = self._typed_token_parts(token_name)
        if typed is None:
            return token_name
        namespace, canonical = typed
        return canonical if namespace == "card_action" else None

    def _build_card_stat_features(self) -> np.ndarray:
        semantic_features: np.ndarray | None = None
        if self.card_semantics_version in {2, 3, 4}:
            semantic_features = np.zeros(
                (len(self.token_names), len(SEMANTIC_FEATURE_NAMES)),
                dtype=np.float32,
            )
            for token_id, name in enumerate(self.token_names):
                if name.startswith("<"):
                    continue
                typed = self._typed_token_parts(name)
                if typed is not None:
                    name = typed[1]
                try:
                    semantic_features[token_id] = semantic_card_profile(
                        name,
                        loader=self.loader,
                    ).vector
                except ValueError:
                    # Some transient spawned payload names have no standalone
                    # public card definition. Their learned token remains usable.
                    continue
            if self.card_semantics_version == 2:
                return semantic_features

        # Public, immutable card metadata helps the shared action head transfer
        # placement concepts between cards instead of memorizing IDs alone.
        features = np.zeros((len(self.token_names), 16), dtype=np.float32)
        kind_index = {"troop": 0, "building": 1, "spell": 2, "champion": 3}
        for token_id, name in enumerate(self.token_names):
            if name.startswith("<"):
                continue
            typed = self._typed_token_parts(name)
            if typed is not None:
                name = typed[1]
            stats = self.loader.get_card(name)
            if stats is None and name in {"Tower", "KingTower"}:
                stats = _crown_tower_observation_stats()[name]
            if stats is None:
                continue
            kind = str(getattr(stats, "card_type", "") or "").lower()
            features[token_id, 0] = _unit_clip(_safe_float(getattr(stats, "mana_cost", 0)) / 10.0)
            if kind in kind_index:
                features[token_id, 1 + kind_index[kind]] = 1.0
            features[token_id, 5] = _unit_clip(math.log1p(max(0.0, _safe_float(getattr(stats, "hitpoints", 0)))) / 9.0)
            features[token_id, 6] = _unit_clip(math.log1p(max(0.0, _safe_float(getattr(stats, "damage", 0)))) / 8.0)
            features[token_id, 7] = _unit_clip(_safe_float(getattr(stats, "range", 0)) / 12.0)
            features[token_id, 8] = _unit_clip(_safe_float(getattr(stats, "sight_range", 0)) / 12.0)
            features[token_id, 9] = _unit_clip(_safe_float(getattr(stats, "speed", 0)) / 200.0)
            features[token_id, 10] = _unit_clip(_safe_float(getattr(stats, "hit_speed", 0)) / 5000.0)
            features[token_id, 11] = _unit_clip(_safe_float(getattr(stats, "deploy_time", 0)) / 5000.0)
            features[token_id, 12] = _unit_clip(_safe_float(getattr(stats, "collision_radius", 0)) / 3.0)
            features[token_id, 13] = _unit_clip(_safe_float(getattr(stats, "summon_count", 0)) / 20.0)
            features[token_id, 14] = float(bool(getattr(stats, "attacks_ground", False)))
            features[token_id, 15] = float(bool(getattr(stats, "attacks_air", False)))
            if self.card_semantics_version == 4:
                # Compact exports encode these flags in the target category.
                # Keep v1-v3 byte-compatible with their existing checkpoints.
                target_type = str(getattr(stats, "target_type", "") or "").upper()
                if target_type:
                    features[token_id, 14] = float(
                        "GROUND" in target_type or "BUILDINGS" in target_type
                    )
                    features[token_id, 15] = float("AIR" in target_type)
                assert semantic_features is not None
                if kind in {"troop", "building", "champion"}:
                    semantic_features[token_id, SEMANTIC_FEATURE_NAMES.index("mass")] = (
                        _unit_clip(unit_mass(stats) / 20.0)
                    )
        if self.card_semantics_version in {3, 4}:
            assert semantic_features is not None
            return np.concatenate(
                (
                    features,
                    semantic_features[:, SEMANTIC_EXTRA_FEATURE_INDICES],
                ),
                axis=1,
            )
        return features

    @staticmethod
    def _payload_name(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        name = value.get("name")
        return str(name) if isinstance(name, str) and name else None

    def _typed_identity_candidates(
        self,
        entity: Any,
        namespace: str,
    ) -> tuple[str, ...]:
        """Return serialized runtime identities in semantic priority order."""

        stats = getattr(entity, "card_stats", None)
        raw = getattr(stats, "_raw_entry", None) or {}
        candidates: list[str] = []

        def add(value: Any) -> None:
            name = self._payload_name(value) if isinstance(value, dict) else value
            if name not in {None, "", "Unknown"} and str(name) not in candidates:
                candidates.append(str(name))

        def add_projectiles(value: Any, *, rolling: bool) -> None:
            if not isinstance(value, dict):
                return
            child = value.get("spawnProjectileData")
            if rolling:
                add(child)
                add(value)
            else:
                add(value)
                add(child)

        if namespace in {"troop_body", "building_body"}:
            add(getattr(stats, "summon_character_data", None))
            add(raw.get("summonCharacterData"))
        elif namespace == "projectile":
            rolling = isinstance(entity, RollingProjectile)
            add(getattr(entity, "spawn_projectile_data", None))
            add_projectiles(getattr(stats, "projectile_data", None), rolling=rolling)
            add_projectiles(raw.get("projectileData"), rolling=rolling)
            source = getattr(entity, "source_entity", None)
            source_stats = getattr(source, "card_stats", None)
            source_raw = getattr(source_stats, "_raw_entry", None) or {}
            add_projectiles(
                getattr(source_stats, "projectile_data", None),
                rolling=rolling,
            )
            add_projectiles(source_raw.get("projectileData"), rolling=rolling)
        elif namespace == "area_effect":
            add(getattr(entity, "area_data", None))
            add(getattr(entity, "buff_data", None))
            add(getattr(stats, "buff_data", None))
            add(raw.get("buffData"))

        for attribute in ("spell_name", "source_name", "spawn_character"):
            add(getattr(entity, attribute, None))
        add(getattr(stats, "name", None))

        source_names = tuple(candidates)
        for source_name in source_names:
            try:
                source_stats = self.loader.get_card(source_name)
            except (KeyError, ValueError):
                source_stats = None
            if source_stats is None:
                continue
            source_raw = getattr(source_stats, "_raw_entry", None) or {}
            if namespace in {"troop_body", "building_body"}:
                add(getattr(source_stats, "summon_character_data", None))
                add(source_raw.get("summonCharacterData"))
            elif namespace == "projectile":
                add_projectiles(
                    getattr(source_stats, "projectile_data", None),
                    rolling=isinstance(entity, RollingProjectile),
                )
                add_projectiles(
                    source_raw.get("projectileData"),
                    rolling=isinstance(entity, RollingProjectile),
                )
            elif namespace == "area_effect":
                add(getattr(source_stats, "buff_data", None))
                add(source_raw.get("buffData"))
            for payload_name in _walk_named_payloads(source_raw):
                add(payload_name)

        for payload_name in _walk_named_payloads(raw):
            add(payload_name)
        return tuple(candidates)

    def _runtime_entity_token_id(self, entity: Any, namespace: str) -> int:
        for candidate in self._typed_identity_candidates(entity, namespace):
            token_id = self.token_id(candidate, namespace=namespace)
            if token_id > 1:
                return token_id
        return self.token_id(None, namespace=namespace)

    def _actor_visible(self, entity: Any, player_id: int) -> bool:
        """Whether an entity is present in the player's public actor state.

        Contract v1-v4 use the engine's visual-state rule unchanged. Later
        contracts may hide more (for example enemy stealth) by overriding this.
        """
        return bool(entity.is_visible_to(player_id))

    def _canonical_position(self, x: float, y: float, player_id: int) -> tuple[float, float]:
        if self.canonical_perspective and player_id == 1:
            return BOARD_WIDTH - x, BOARD_HEIGHT - y
        return x, y

    def _canonical_vector(self, x: float, y: float, player_id: int) -> tuple[float, float]:
        if self.canonical_perspective and player_id == 1:
            return -x, -y
        return x, y

    @staticmethod
    def _shield_fraction(entity: Any) -> float:
        result = 0.0
        for mechanic in getattr(entity, "mechanics", ()):
            maximum = _safe_float(getattr(mechanic, "max_shield", 0))
            if maximum > 0.0:
                result = max(
                    result,
                    _safe_float(getattr(mechanic, "current_shield", 0)) / maximum,
                )
        return _unit_clip(result)

    @staticmethod
    def _effect_progress(entity: Any) -> float:
        elapsed = _safe_float(getattr(entity, "time_alive", 0))
        duration = _safe_float(getattr(entity, "duration", 0))
        if duration <= 0.0:
            duration = _safe_float(getattr(entity, "explosion_timer", 0))
        if duration <= 0.0:
            return 0.0
        return _unit_clip(elapsed / duration)

    def _entity_row(self, entity: Any, perspective_player: int) -> tuple[int, np.ndarray]:
        row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)

        x, y = self._canonical_position(
            _safe_float(entity.position.x),
            _safe_float(entity.position.y),
            perspective_player,
        )
        row[0] = _unit_clip(x / BOARD_WIDTH)
        row[1] = _unit_clip(y / BOARD_HEIGHT)
        own = int(entity.player_id) == perspective_player
        row[2] = float(own)
        row[3] = float(not own)
        kind = int(_range_clip(int(getattr(entity, "entity_kind", 4)), 0, 4))
        stats_name = str(getattr(getattr(entity, "card_stats", None), "name", ""))
        namespaces: tuple[str, ...]
        if stats_name in {"Tower", "KingTower"}:
            namespaces = ("tower",)
        elif isinstance(entity, TimedExplosive):
            # Timed payloads execute in the area/effect phase. Bombs expose a
            # typed building child; falling troop containers instead retain
            # their serialized source-body identity.
            namespaces = ("building_body", "troop_body")
        elif isinstance(entity, ChainLightning):
            # Chained hit controllers execute in the effect phase while
            # retaining their serialized projectile identity.
            namespaces = ("projectile",)
        else:
            namespaces = (
                (
                    "troop_body",
                    "building_body",
                    "projectile",
                    "area_effect",
                    "card_action",
                )[kind],
            )
        token_id = 1
        for namespace in namespaces:
            token_id = self._runtime_entity_token_id(entity, namespace)
            if token_id > 1:
                break
        row[4 + kind] = 1.0
        if getattr(entity, "_self_projectile_launched", False):
            # The remaining Troop object only carries the flight callback.
            # Native removed its character body at launch: HP, shields,
            # collision, deployment and character status clocks are absent.
            # Encode only the projectile's visible type/position and public
            # serialized payload metadata, never the carrier's stale fields.
            projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
            speed = logic_speed_to_tiles_per_second(_safe_float(projectile.get("speed", 0)))
            row[23] = _unit_clip(math.log1p(abs(speed)) / math.log1p(1000.0))
            row[30] = _unit_clip(
                math.log1p(max(0.0, _safe_float(getattr(entity, "damage", 0)))) / 8.0
            )
            return token_id, row
        row[9] = _unit_clip(
            _safe_float(getattr(entity, "hitpoints", 0))
            / max(1.0, _safe_float(getattr(entity, "max_hitpoints", 1), 1.0))
        )
        row[10] = self._shield_fraction(entity)
        row[11] = float(is_airborne_target(entity))
        row[12] = float(bool(getattr(entity, "placement_pending", False)))
        deploy_total = _safe_float(getattr(entity, "placement_delay_total", 0))
        deploy_remaining = _safe_float(getattr(entity, "deploy_delay_remaining", 0))
        row[13] = _unit_clip(deploy_remaining / deploy_total) if deploy_total > 0 else 0.0
        row[14] = _unit_clip(_safe_float(getattr(entity, "stun_timer", 0)) / 6.0)
        row[15] = _unit_clip(_safe_float(getattr(entity, "slow_timer", 0)) / 6.0)
        row[16] = _unit_clip(_safe_float(getattr(entity, "haste_timer", 0)) / 6.0)
        row[17] = float(
            bool(getattr(entity, "_special_move_active", False))
            or bool(getattr(entity, "is_charging", False))
            or bool(getattr(entity, "_river_jump_active", False))
        )
        stealth_until = int(getattr(entity, "_stealth_until", 0) or 0)
        battle = getattr(entity, "battle_state", None)
        battle_time = _safe_float(getattr(battle, "time", 0))
        row[18] = float(stealth_until > logic_time_milliseconds(battle_time))
        row[19] = float(bool(getattr(entity, "_hidden_building", False)))
        row[20] = float(bool(getattr(entity, "forced_movement_active", False)))
        row[21] = float(bool(getattr(entity, "_attack_windup_active", False)))
        row[22] = float(bool(getattr(entity, "is_charging", False)))
        speed = _safe_float(
            getattr(entity, "speed", getattr(entity, "travel_speed", 0))
        )
        row[23] = _unit_clip(math.log1p(abs(speed)) / math.log1p(1000.0))
        row[24] = _unit_clip(_safe_float(getattr(entity, "range", 0)) / 12.0)
        row[25] = _unit_clip(_safe_float(getattr(entity, "sight_range", 0)) / 12.0)
        collision_radius = _safe_float(
            getattr(getattr(entity, "card_stats", None), "collision_radius", 0)
        )
        row[26] = _unit_clip(collision_radius / 3.0)
        facing_x, facing_y = getattr(entity, "native_facing_units", lambda: (0, 0))()
        facing_x, facing_y = self._canonical_vector(
            _safe_float(facing_x), _safe_float(facing_y), perspective_player
        )
        magnitude = max(1.0, math.hypot(facing_x, facing_y))
        row[27] = _range_clip(facing_x / magnitude, -1.0, 1.0)
        row[28] = _range_clip(facing_y / magnitude, -1.0, 1.0)
        row[29] = self._effect_progress(entity)
        row[30] = _unit_clip(
            math.log1p(max(0.0, _safe_float(getattr(entity, "damage", 0)))) / 8.0
        )
        row[31] = float(isinstance(entity, Building) and getattr(entity, "_tower_active", True))
        return token_id, row

    def _build_entities(
        self,
        battle: BattleState,
        player_id: int,
        *,
        privileged: bool,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows: list[tuple[tuple[Any, ...], int, np.ndarray]] = []
        for entity in battle.entities.values():
            if not entity.is_alive:
                continue
            if not privileged and not self._actor_visible(entity, player_id):
                continue
            token_id, features = self._entity_row(entity, player_id)
            # Spatial/semantic order is deterministic but carries no private
            # simulator identifier into the network.
            sort_key = (
                int(getattr(entity, "entity_kind", 4)),
                int(entity.player_id != player_id),
                token_id,
                round(float(features[1]), 5),
                round(float(features[0]), 5),
            )
            rows.append((sort_key, token_id, features))
        return self._pack_entity_rows(rows)

    def _pack_entity_rows(
        self,
        rows: list[tuple[tuple[Any, ...], int, np.ndarray]],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows.sort(key=lambda item: item[0])
        if len(rows) > self.max_entities:
            raise EntityCapacityError(
                f"alive entity count {len(rows)} exceeds configured max_entities={self.max_entities}"
            )

        ids = np.zeros((self.max_entities,), dtype=np.int64)
        features = np.zeros((self.max_entities, ENTITY_FEATURE_SIZE), dtype=np.float32)
        mask = np.zeros((self.max_entities,), dtype=np.bool_)
        for index, (_, token_id, row) in enumerate(rows):
            ids[index] = token_id
            features[index] = row
            mask[index] = True
        return ids, features, mask

    def _build_actor_and_critic_entities(
        self,
        battle: BattleState,
        player_id: int,
    ) -> tuple[
        tuple[np.ndarray, np.ndarray, np.ndarray],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ]:
        """Build public and privileged entity tables with one feature pass."""

        public_rows: list[tuple[tuple[Any, ...], int, np.ndarray]] = []
        privileged_rows: list[tuple[tuple[Any, ...], int, np.ndarray]] = []
        for entity in battle.entities.values():
            if not entity.is_alive:
                continue
            token_id, features = self._entity_row(entity, player_id)
            sort_key = (
                int(getattr(entity, "entity_kind", 4)),
                int(entity.player_id != player_id),
                token_id,
                round(float(features[1]), 5),
                round(float(features[0]), 5),
            )
            row = (sort_key, token_id, features)
            privileged_rows.append(row)
            if self._actor_visible(entity, player_id):
                public_rows.append(row)
        return (
            self._pack_entity_rows(public_rows),
            self._pack_entity_rows(privileged_rows),
        )

    def _card_ids_for_player(self, battle: BattleState, player_id: int) -> np.ndarray:
        player = battle.players[player_id]
        names = list(player.hand[:NUM_HAND_SLOTS])
        while len(names) < NUM_HAND_SLOTS:
            names.append(None)
        names.append(player.cycle_queue[0] if player.cycle_queue else None)
        return np.asarray(
            [0 if name is None else self.token_id(name) for name in names],
            dtype=np.int64,
        )

    @staticmethod
    def _tower_fraction(battle: BattleState, player_id: int, slot: str) -> float:
        player = battle.players[player_id]
        value = _safe_float(getattr(player, f"{slot}_tower_hp"))
        start = _safe_float(
            battle._starting_tower_hps.get(player_id, {}).get(slot, max(1.0, value)),
            max(1.0, value),
        )
        return _unit_clip(value / max(1.0, start))

    def _actor_globals(self, battle: BattleState, player_id: int) -> np.ndarray:
        own = battle.players[player_id]
        enemy_id = 1 - player_id
        enemy = battle.players[enemy_id]
        ability_cooldown = 0.0
        ability_duration = 0.0
        found = battle._champion_ability_mechanic(player_id)
        if found is not None:
            _, mechanic = found
            ability = mechanic.ability
            ability_cooldown = ability.get_cooldown_remaining(battle) / max(
                1.0, float(ability.cooldown_ms)
            )
            ability_duration = ability.get_duration_remaining(battle) / max(
                1.0, float(ability.duration_ms)
            )

        progress = _unit_clip(battle.time / max(1.0, battle.tiebreaker_time))
        own_left = "left"
        own_right = "right"
        enemy_left = "left"
        enemy_right = "right"
        if (
            self.canonical_perspective
            and self.canonical_lane_globals
            and player_id == 1
        ):
            own_left, own_right = own_right, own_left
            enemy_left, enemy_right = enemy_right, enemy_left
        return np.asarray(
            [
                progress,
                1.0 - progress,
                float(battle.double_elixir),
                float(battle.triple_elixir),
                float(battle.overtime),
                _unit_clip(own.elixir / max(1.0, own.max_elixir)),
                battle.get_crown_count(player_id) / 3.0,
                battle.get_crown_count(enemy_id) / 3.0,
                self._tower_fraction(battle, player_id, own_left),
                self._tower_fraction(battle, player_id, own_right),
                self._tower_fraction(battle, player_id, "king"),
                self._tower_fraction(battle, enemy_id, enemy_left),
                self._tower_fraction(battle, enemy_id, enemy_right),
                self._tower_fraction(battle, enemy_id, "king"),
                _unit_clip(ability_cooldown),
                _unit_clip(ability_duration),
                _unit_clip(own.next_card_refill_cooldown_ms / 1000.0),
                float(enemy.king_tower_hp > 0.0),
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _own_last_play(battle: BattleState, player_id: int) -> AcceptedOwnPlay | None:
        player = battle.players[player_id]
        if player.last_played_card is None or player.last_played_card_cost is None:
            return None
        return AcceptedOwnPlay(player.last_played_card, player.last_played_card_cost)

    def _public_levels(self, battle, player_id):
        if not self.public_entity_levels:
            return {}
        rows = []
        for entity in battle.entities.values():
            if not entity.is_alive or not self._actor_visible(entity, player_id):
                continue
            token, features = self._entity_row(entity, player_id)
            kind = int(entity.entity_kind)
            key = (kind, int(entity.player_id != player_id), token,
                   round(float(features[1]), 5), round(float(features[0]), 5))
            stats = entity.card_stats
            # Pre-scaled Crown stats declare their public level separately from
            # the level1 multiplier placeholder. Effects have no unit label.
            known = (kind in (0, 1) and stats is not None
                     and not getattr(entity, '_self_projectile_launched', False))
            level = int(stats.level) if known else 0
            if known and stats.name in {'Tower', 'KingTower'}:
                level = int(stats._raw_entry.get('publicLevel', 0))
                known = level > 0
            if known and not 1 <= level <= 127:
                raise ValueError('public unit level outside supported range')
            rows.append((key, level))
        rows.sort(key=lambda row: row[0])
        levels = np.zeros(self.max_entities, dtype=np.int64)
        confidence = np.zeros(self.max_entities, dtype=np.float32)
        for index, (_, level) in enumerate(rows):
            levels[index] = level
            confidence[index] = float(level != 0)
        result = {'entity_levels': levels, 'entity_level_confidence': confidence}
        if self.public_hand_levels:
            player = battle.players[player_id]
            names = list(player.hand[:NUM_HAND_SLOTS])
            names.extend([None] * (NUM_HAND_SLOTS - len(names)))
            names.append(player.cycle_queue[0] if player.cycle_queue else None)
            hand_levels = np.asarray(
                [0 if name is None else player.card_level(name) for name in names],
                dtype=np.int64,
            )
            result.update(
                hand_levels=hand_levels,
                hand_level_confidence=(hand_levels > 0).astype(np.float32),
            )
        return result

    def build(self, battle: BattleState, player_id: int) -> StructuredObservation:
        actor_entities, critic_entities = self._build_actor_and_critic_entities(
            battle, player_id
        )
        entity_ids, entity_features, entity_mask = actor_entities
        critic_entity_ids, critic_entity_features, critic_entity_mask = critic_entities
        hand_ids = self._card_ids_for_player(battle, player_id)
        enemy_ids = self._card_ids_for_player(battle, 1 - player_id)
        actor_globals = self._actor_globals(battle, player_id)
        opponent_history_ids, opponent_history_ages = self._opponent_history(
            battle,
            player_id,
        )
        opponent_seen_card_ids = self._opponent_seen_cards(battle, player_id)
        enemy = battle.players[1 - player_id]
        critic_globals = np.concatenate(
            [
                actor_globals,
                np.asarray(
                    [
                        _unit_clip(enemy.elixir / max(1.0, enemy.max_elixir)),
                        _unit_clip(enemy.next_card_refill_cooldown_ms / 1000.0),
                    ],
                    dtype=np.float32,
                ),
            ]
        ).astype(np.float32, copy=False)
        return StructuredObservation(
            **self._public_levels(battle, player_id),
            terminal=bool(battle.game_over),
            board_rotated=bool(self.canonical_perspective and player_id == 1),
            own_last_play=self._own_last_play(battle, player_id),
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=hand_ids,
            global_features=actor_globals,
            critic_entity_ids=critic_entity_ids,
            critic_entity_features=critic_entity_features,
            critic_entity_mask=critic_entity_mask,
            critic_card_ids=np.concatenate([hand_ids, enemy_ids]).astype(np.int64, copy=False),
            critic_global_features=critic_globals,
            opponent_history_ids=opponent_history_ids,
            opponent_history_ages=opponent_history_ages,
            opponent_seen_card_ids=opponent_seen_card_ids,
        )

    def build_actor(self, battle: BattleState, player_id: int) -> ActorObservation:
        """Build only public tensors used by actor inference and imitation data."""
        entity_ids, entity_features, entity_mask = self._build_entities(
            battle,
            player_id,
            privileged=False,
        )
        opponent_history_ids, opponent_history_ages = self._opponent_history(
            battle,
            player_id,
        )
        return ActorObservation(
            **self._public_levels(battle, player_id),
            terminal=bool(battle.game_over),
            board_rotated=bool(self.canonical_perspective and player_id == 1),
            own_last_play=self._own_last_play(battle, player_id),
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=self._card_ids_for_player(battle, player_id),
            global_features=self._actor_globals(battle, player_id),
            opponent_history_ids=opponent_history_ids,
            opponent_history_ages=opponent_history_ages,
            opponent_seen_card_ids=self._opponent_seen_cards(battle, player_id),
        )

    def _opponent_history(
        self,
        battle: BattleState,
        player_id: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        ids = np.zeros((self.public_history_slots,), dtype=np.int64)
        ages = np.zeros((self.public_history_slots,), dtype=np.float32)
        if self.public_history_slots == 0:
            return ids, ages
        history = battle.public_card_play_history[1 - player_id]
        recent = reversed(history[-self.public_history_slots :])
        for index, (played_tick, card_name) in enumerate(recent):
            ids[index] = self.token_id(card_name)
            elapsed_seconds = max(0, battle.tick - played_tick) * battle.dt
            ages[index] = _unit_clip(elapsed_seconds / 60.0)
        return ids, ages

    def _opponent_seen_cards(
        self,
        battle: BattleState,
        player_id: int,
    ) -> np.ndarray:
        ids = np.zeros((self.public_seen_card_slots,), dtype=np.int64)
        if self.public_seen_card_slots == 0:
            return ids
        discovered: set[str] = set()
        output_index = 0
        for _played_tick, card_name in battle.public_card_play_history[1 - player_id]:
            if card_name in discovered:
                continue
            discovered.add(card_name)
            ids[output_index] = self.token_id(card_name)
            output_index += 1
            if output_index == self.public_seen_card_slots:
                break
        return ids


def build_canonical_tile_features() -> np.ndarray:
    """Return public static features for each canonical action tile."""
    features = np.zeros((NUM_TILES, 12), dtype=np.float32)
    blocked = set(TileGrid.BLOCKED_TILES)
    for y in range(BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            index = y * BOARD_WIDTH + x
            xf = (x + 0.5) / BOARD_WIDTH
            yf = (y + 0.5) / BOARD_HEIGHT
            on_river = 15.0 <= y + 0.5 < 17.0
            on_bridge = on_river and (2.0 <= x + 0.5 < 5.0 or 13.0 <= x + 0.5 < 16.0)
            features[index] = np.asarray(
                [
                    xf,
                    yf,
                    2.0 * xf - 1.0,
                    2.0 * yf - 1.0,
                    math.sin(math.pi * xf),
                    math.cos(math.pi * xf),
                    math.sin(math.pi * yf),
                    math.cos(math.pi * yf),
                    float((x, y) in blocked),
                    float(on_river),
                    float(on_bridge),
                    float(x < BOARD_WIDTH / 2),
                ],
                dtype=np.float32,
            )
    return features
