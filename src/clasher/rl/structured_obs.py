from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from clasher.arena import TileGrid
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.entities import Building
from clasher.kinematics import logic_time_milliseconds
from clasher.unit_traits import is_airborne_target

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .deck_pool import load_deck_pool, unique_cards_from_decks


ENTITY_FEATURE_SIZE = 32
ACTOR_GLOBAL_SIZE = 18
CRITIC_GLOBAL_SIZE = 20
VISIBLE_CARD_SLOTS = NUM_HAND_SLOTS + 1
PRIVILEGED_CARD_SLOTS = 2 * VISIBLE_CARD_SLOTS
DEFAULT_MAX_ENTITIES = 128


class EntityCapacityError(RuntimeError):
    """Raised instead of silently discarding a visible combat object."""


@dataclass(frozen=True)
class StructuredObservationSpec:
    token_names: tuple[str, ...]
    max_entities: int
    entity_feature_size: int = ENTITY_FEATURE_SIZE
    actor_global_size: int = ACTOR_GLOBAL_SIZE
    critic_global_size: int = CRITIC_GLOBAL_SIZE

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


@dataclass(frozen=True)
class ActorObservation:
    """Public policy inputs without the unused privileged critic payload."""

    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray
    hand_ids: np.ndarray
    global_features: np.ndarray


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
        card_vocab: Sequence[str] | None = None,
        max_entities: int = DEFAULT_MAX_ENTITIES,
        canonical_perspective: bool = True,
        token_names: Sequence[str] | None = None,
    ) -> None:
        if max_entities <= 0:
            raise ValueError("max_entities must be positive")
        self.max_entities = int(max_entities)
        self.canonical_perspective = bool(canonical_perspective)
        self.loader = CardDataLoader()
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
        for name in tuple(self._name_to_id):
            if name.startswith("<"):
                continue
            resolved = resolve_card_name(name, definitions)
            self._name_to_id.setdefault(resolved, self._name_to_id[name])

        self.spec = StructuredObservationSpec(
            token_names=self.token_names,
            max_entities=self.max_entities,
        )
        self.card_stat_features = self._build_card_stat_features()

    def token_id(self, name: str | None) -> int:
        if not name:
            return self._name_to_id[self.UNKNOWN_TOKEN]
        direct = self._name_to_id.get(str(name))
        if direct is not None:
            return direct
        resolved = resolve_card_name(str(name), self.loader.load_card_definitions())
        return self._name_to_id.get(resolved, self._name_to_id[self.UNKNOWN_TOKEN])

    def _build_card_stat_features(self) -> np.ndarray:
        # Public, immutable card metadata helps the shared action head transfer
        # placement concepts between cards instead of memorizing IDs alone.
        features = np.zeros((len(self.token_names), 16), dtype=np.float32)
        kind_index = {"troop": 0, "building": 1, "spell": 2, "champion": 3}
        for token_id, name in enumerate(self.token_names):
            if name.startswith("<"):
                continue
            stats = self.loader.get_card(name)
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
        return features

    @staticmethod
    def _visible_entity_name(entity: Any) -> str:
        stats_name = getattr(getattr(entity, "card_stats", None), "name", "")
        if stats_name:
            return str(stats_name)
        for attribute in ("spell_name", "source_name", "spawn_character"):
            value = getattr(entity, attribute, "")
            if value not in {None, "", "Unknown"}:
                return str(value)
        return ""

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
        name = self._visible_entity_name(entity)
        token_id = self.token_id(name)
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
        row[4 + kind] = 1.0
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
            if not privileged and not entity.is_visible_to(player_id):
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
            if entity.is_visible_to(player_id):
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
                self._tower_fraction(battle, player_id, "left"),
                self._tower_fraction(battle, player_id, "right"),
                self._tower_fraction(battle, player_id, "king"),
                self._tower_fraction(battle, enemy_id, "left"),
                self._tower_fraction(battle, enemy_id, "right"),
                self._tower_fraction(battle, enemy_id, "king"),
                _unit_clip(ability_cooldown),
                _unit_clip(ability_duration),
                _unit_clip(own.next_card_refill_cooldown_ms / 1000.0),
                float(enemy.king_tower_hp > 0.0),
            ],
            dtype=np.float32,
        )

    def build(self, battle: BattleState, player_id: int) -> StructuredObservation:
        actor_entities, critic_entities = self._build_actor_and_critic_entities(
            battle, player_id
        )
        entity_ids, entity_features, entity_mask = actor_entities
        critic_entity_ids, critic_entity_features, critic_entity_mask = critic_entities
        hand_ids = self._card_ids_for_player(battle, player_id)
        enemy_ids = self._card_ids_for_player(battle, 1 - player_id)
        actor_globals = self._actor_globals(battle, player_id)
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
        )

    def build_actor(self, battle: BattleState, player_id: int) -> ActorObservation:
        """Build only public tensors used by actor inference and imitation data."""
        entity_ids, entity_features, entity_mask = self._build_entities(
            battle,
            player_id,
            privileged=False,
        )
        return ActorObservation(
            entity_ids=entity_ids,
            entity_features=entity_features,
            entity_mask=entity_mask,
            hand_ids=self._card_ids_for_player(battle, player_id),
            global_features=self._actor_globals(battle, player_id),
        )


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
