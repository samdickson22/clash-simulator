from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from clasher.card_aliases import resolve_card_name
from clasher.entities import Building, Entity, Troop
from clasher.spells import SPELL_REGISTRY

from .common import BOARD_WIDTH, NUM_TILES
from .selfplay_env import SelfPlayBattleEnv

BRIDGE_PRESSURE = "bridge-pressure"
SLOW_PUSH = "slow-push"
SPELL_CONTROL = "spell-control"
REACTIVE_DEFENSE = "reactive-defense"
SPLIT_LANE = "split-lane"
BALANCED = "balanced"
STRATEGY_NAMES = (
    BRIDGE_PRESSURE,
    SLOW_PUSH,
    SPELL_CONTROL,
    REACTIVE_DEFENSE,
    SPLIT_LANE,
    BALANCED,
)

# Reference/benchmark switch. Legal placement action IDs already encode the
# canonical slot/tile geometry used by every strategy score.
_USE_DIRECT_CANONICAL_ACTION_GEOMETRY = True

# Reference/benchmark switch for reusing the exact defense/cluster geometry
# shared by the same canonical tile across legal hand slots.
_USE_CACHED_STRATEGY_TILE_FITS = True


def _canonical_xy(entity: Entity, player_id: int) -> tuple[float, float]:
    if player_id == 0:
        return float(entity.position.x), float(entity.position.y)
    return 18.0 - float(entity.position.x), 32.0 - float(entity.position.y)


def _canonical_position_xy(
    x: float,
    y: float,
    player_id: int,
) -> tuple[float, float]:
    if player_id == 0:
        return x, y
    return 18.0 - x, 32.0 - y


def _is_crown_tower(entity: Entity) -> bool:
    return bool(
        isinstance(entity, Building)
        and getattr(entity, "_crown_tower_slot", None) in {"left", "right", "king"}
    )


def _visible_combat_entities(
    env: SelfPlayBattleEnv,
    player_id: int,
    owner: int,
) -> list[Entity]:
    assert env.battle is not None
    return [
        entity
        for entity in env.battle.entities.values()
        if entity.is_alive
        and entity.player_id == owner
        and isinstance(entity, (Troop, Building))
        and not _is_crown_tower(entity)
        and (owner == player_id or entity.is_visible_to(player_id))
    ]


def _combat_strength(entity: Entity) -> float:
    hp = max(0.0, float(entity.hitpoints))
    max_hp = max(1.0, float(entity.max_hitpoints or 1.0))
    damage = max(0.0, float(entity.damage))
    hit_speed = max(250.0, float(getattr(entity.card_stats, "hit_speed", 0) or 0))
    dps = damage * 1000.0 / hit_speed
    return float((0.6 + hp / max_hp) * (0.5 + math.sqrt(max_hp / 900.0) + dps / 180.0))


@dataclass(frozen=True)
class PublicSituation:
    incoming_strength: float
    incoming_x: float
    incoming_y: float
    enemy_lane_strength: tuple[float, float]
    allied_lane_strength: tuple[float, float]
    enemy_cluster: tuple[float, float]
    enemy_cluster_strength: float
    allied_tank: tuple[float, float] | None


@dataclass(frozen=True)
class _CardFeatures:
    is_spell: bool
    is_building: bool
    cost: float
    hp: float
    speed: float
    attack_range: float
    efficiency: float


def _card_features(
    env: SelfPlayBattleEnv,
    player_id: int,
) -> tuple[_CardFeatures | None, ...]:
    assert env.battle is not None
    features: list[_CardFeatures | None] = []
    definitions = env.battle.card_loader.load_card_definitions()
    for card_name in env.battle.players[player_id].hand:
        if card_name is None:
            features.append(None)
            continue
        stats = env.battle.card_loader.get_card(card_name)
        if stats is None:
            features.append(None)
            continue
        resolved = resolve_card_name(card_name, definitions)
        is_spell = resolved in SPELL_REGISTRY
        card_type = str(getattr(stats, "card_type", "") or "").lower()
        cost = float(getattr(stats, "mana_cost", 0) or 0)
        hp = float(getattr(stats, "hitpoints", 0) or 0)
        damage = float(getattr(stats, "damage", 0) or 0)
        count = max(1.0, float(getattr(stats, "summon_count", 0) or 1))
        efficiency = (
            math.sqrt(max(0.0, hp) / 700.0) + damage / 170.0 + 0.2 * count
        ) / max(1.0, cost)
        features.append(
            _CardFeatures(
                is_spell=is_spell,
                is_building=card_type == "building" and not is_spell,
                cost=cost,
                hp=hp,
                speed=float(getattr(stats, "speed", 0) or 0),
                attack_range=float(getattr(stats, "range", 0) or 0),
                efficiency=efficiency,
            )
        )
    return tuple(features)


def _public_situation(env: SelfPlayBattleEnv, player_id: int) -> PublicSituation:
    assert env.battle is not None
    enemies = _visible_combat_entities(env, player_id, 1 - player_id)
    allies = _visible_combat_entities(env, player_id, player_id)

    incoming: list[tuple[Entity, float, float, float]] = []
    enemy_lanes = [0.0, 0.0]
    allied_lanes = [0.0, 0.0]
    for entity in enemies:
        x, y = _canonical_xy(entity, player_id)
        strength = _combat_strength(entity)
        enemy_lanes[int(x >= 9.0)] += strength
        if y < 16.5:
            proximity = math.exp(-max(0.0, y - 5.5) / 6.0)
            incoming.append((entity, x, y, strength * proximity))
    for entity in allies:
        x, _ = _canonical_xy(entity, player_id)
        allied_lanes[int(x >= 9.0)] += _combat_strength(entity)

    if incoming:
        total = sum(item[3] for item in incoming)
        incoming_x = sum(item[1] * item[3] for item in incoming) / max(total, 1e-9)
        incoming_y = sum(item[2] * item[3] for item in incoming) / max(total, 1e-9)
    else:
        total = 0.0
        incoming_x, incoming_y = 9.0, 10.0

    if enemies:
        weights = [_combat_strength(entity) for entity in enemies]
        weight_sum = max(1e-9, sum(weights))
        coordinates = [_canonical_xy(entity, player_id) for entity in enemies]
        cluster_x = sum(x * w for (x, _), w in zip(coordinates, weights)) / weight_sum
        cluster_y = sum(y * w for (_, y), w in zip(coordinates, weights)) / weight_sum
    else:
        cluster_x, cluster_y, weight_sum = 9.0, 23.5, 0.0

    tank: tuple[float, float] | None = None
    if allies:
        tank_entity = max(allies, key=lambda entity: float(entity.hitpoints))
        if float(tank_entity.max_hitpoints or 0.0) >= 900.0:
            tank = _canonical_xy(tank_entity, player_id)

    return PublicSituation(
        incoming_strength=float(total),
        incoming_x=float(incoming_x),
        incoming_y=float(incoming_y),
        enemy_lane_strength=(float(enemy_lanes[0]), float(enemy_lanes[1])),
        allied_lane_strength=(float(allied_lanes[0]), float(allied_lanes[1])),
        enemy_cluster=(float(cluster_x), float(cluster_y)),
        enemy_cluster_strength=float(weight_sum),
        allied_tank=tank,
    )


def _gaussian_distance(
    x: float, y: float, target_x: float, target_y: float, scale: float
) -> float:
    distance_sq = (x - target_x) ** 2 + (y - target_y) ** 2
    return math.exp(-distance_sq / max(1e-6, 2.0 * scale * scale))


@dataclass(frozen=True)
class StrategyBot:
    """Deterministic opponent using only information visible to its seat.

    The scorer intentionally has no card-name branches. It reads the acting
    player's hand and elixir, public card stats, legal actions, visible units,
    and public tower state. Hidden enemy hand, cycle, elixir, and target IDs
    are never consulted.
    """

    name: str

    def __post_init__(self) -> None:
        if self.name not in STRATEGY_NAMES:
            raise ValueError(f"unknown strategy {self.name!r}")

    def select_action(
        self,
        env: SelfPlayBattleEnv,
        player_id: int,
        *,
        action_mask: np.ndarray | None = None,
    ) -> int:
        if env.battle is None:
            raise ValueError("environment must be reset before selecting an action")
        mask = (
            env.get_action_mask(player_id)
            if action_mask is None
            else np.asarray(action_mask, dtype=np.bool_)
        )
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            return env.action_space.no_op_action

        situation = _public_situation(env, player_id)
        player = env.battle.players[player_id]
        features = _card_features(env, player_id)
        legal_actions = legal.tolist()
        tile_fit_cache: list[tuple[float, float] | None] | None = (
            [None] * NUM_TILES if _USE_CACHED_STRATEGY_TILE_FITS else None
        )
        best_action = int(legal_actions[0])
        best_score = self._score_action(
            env,
            player_id,
            best_action,
            situation,
            float(player.elixir),
            features,
            tile_fit_cache,
        )
        for action_id in legal_actions[1:]:
            score = self._score_action(
                env,
                player_id,
                action_id,
                situation,
                float(player.elixir),
                features,
                tile_fit_cache,
            )
            # Stable action-ID tie breaking makes the policy fully replayable.
            if score > best_score:
                best_score = score
                best_action = int(action_id)
        return best_action

    def _score_action(
        self,
        env: SelfPlayBattleEnv,
        player_id: int,
        action_id: int,
        situation: PublicSituation,
        elixir: float,
        card_features: tuple[_CardFeatures | None, ...],
        tile_fit_cache: list[tuple[float, float] | None] | None = None,
    ) -> float:
        assert env.battle is not None
        action_space = env.action_space
        if (
            _USE_DIRECT_CANONICAL_ACTION_GEOMETRY
            and action_space.canonical_perspective
        ):
            if action_id == action_space.no_op_action or not (
                0 <= action_id < action_space.num_actions
            ):
                return self._noop_score(situation, elixir)
            if action_id == action_space.ability_action:
                return 4.0 + min(3.0, situation.incoming_strength)
            slot = action_id // NUM_TILES
            tile = action_id % NUM_TILES
            x = float(tile % BOARD_WIDTH) + 0.5
            y = float(tile // BOARD_WIDTH) + 0.5
        else:
            decoded = action_space.decode_action(action_id, player_id)
            if decoded.is_no_op:
                return self._noop_score(situation, elixir)
            if decoded.is_ability:
                return 4.0 + min(3.0, situation.incoming_strength)
            assert decoded.slot is not None and decoded.position is not None
            slot = decoded.slot
            tile = action_id % NUM_TILES
            x, y = _canonical_position_xy(
                float(decoded.position.x),
                float(decoded.position.y),
                player_id,
            )

        features = card_features[slot]
        if features is None:
            return -1e9
        is_spell = features.is_spell
        is_building = features.is_building
        cost = features.cost
        hp = features.hp
        speed = features.speed
        attack_range = features.attack_range
        efficiency = features.efficiency
        lane = int(x >= 9.0)
        cached_fits = None if tile_fit_cache is None else tile_fit_cache[tile]
        if cached_fits is None:
            defense_fit = _gaussian_distance(
                x,
                y,
                situation.incoming_x,
                min(14.0, situation.incoming_y + 1.5),
                3.5,
            )
            cluster_fit = _gaussian_distance(
                x,
                y,
                situation.enemy_cluster[0],
                situation.enemy_cluster[1],
                3.0,
            )
            if tile_fit_cache is not None:
                tile_fit_cache[tile] = (defense_fit, cluster_fit)
        else:
            defense_fit, cluster_fit = cached_fits

        if self.name == BRIDGE_PRESSURE:
            return (
                4.2 * math.exp(-abs(y - 14.0) / 2.7)
                + 0.018 * speed
                + 0.6 * efficiency
                + 0.25 * (1.0 if lane == 0 else 0.0)
                - 0.55 * cost
                + (1.4 * cluster_fit if is_spell else 0.0)
            )
        if self.name == SLOW_PUSH:
            support = 0.0
            if situation.allied_tank is not None:
                support = _gaussian_distance(
                    x,
                    y,
                    situation.allied_tank[0],
                    max(2.0, situation.allied_tank[1] - 2.5),
                    3.5,
                )
            return (
                4.5 * math.exp(-abs(y - 4.5) / 2.7)
                + 0.0025 * hp
                + 1.5 * support
                + 0.35 * attack_range
                - (2.5 if is_spell else 0.0)
                - (1.5 if elixir < 7.0 else 0.0)
            )
        if self.name == SPELL_CONTROL:
            if is_spell:
                tower_zone = math.exp(-abs(y - 25.0) / 4.0)
                return (
                    2.0
                    + 5.0 * cluster_fit
                    + 0.5 * tower_zone
                    + 0.3 * situation.enemy_cluster_strength
                )
            return (
                3.2 * defense_fit
                + (1.5 if is_building and situation.incoming_strength > 0.2 else 0.0)
                + 0.7 * efficiency
                - 0.35 * cost
            )
        if self.name == REACTIVE_DEFENSE:
            if situation.incoming_strength > 0.08:
                return (
                    6.0 * defense_fit
                    + (1.5 if is_building else 0.0)
                    + 1.0 * efficiency
                    + (2.0 * cluster_fit if is_spell else 0.0)
                    - 0.28 * cost
                )
            return 1.2 * math.exp(-abs(y - 7.0) / 4.0) + 0.5 * efficiency - 0.5 * cost
        if self.name == SPLIT_LANE:
            desired_lane = int(
                situation.allied_lane_strength[1] - situation.enemy_lane_strength[1]
                > situation.allied_lane_strength[0] - situation.enemy_lane_strength[0]
            )
            lane_score = 3.0 if lane != desired_lane else 0.0
            return (
                lane_score
                + 3.2 * math.exp(-abs(y - 13.5) / 3.5)
                + 0.8 * efficiency
                - 0.4 * cost
                + (1.4 * cluster_fit if is_spell else 0.0)
            )

        # Balanced switches smoothly from defending visible pressure to a
        # measured bridge push, so it remains useful across arbitrary decks.
        threat = min(1.0, situation.incoming_strength / 1.5)
        defense = 5.0 * defense_fit + (1.2 if is_building else 0.0)
        offense = 3.5 * math.exp(-abs(y - 13.0) / 3.5) + 0.5 * efficiency
        spell_bonus = 2.5 * cluster_fit if is_spell else 0.0
        return threat * defense + (1.0 - threat) * offense + spell_bonus - 0.32 * cost

    def _noop_score(self, situation: PublicSituation, elixir: float) -> float:
        if self.name == SLOW_PUSH:
            return 5.0 if elixir < 7.0 and situation.incoming_strength < 0.08 else -0.5
        if self.name == SPELL_CONTROL:
            return (
                3.0 if situation.enemy_cluster_strength < 0.2 and elixir < 9.0 else 0.0
            )
        if self.name == REACTIVE_DEFENSE:
            return 4.0 if situation.incoming_strength <= 0.08 and elixir < 9.0 else -1.0
        if self.name == BALANCED:
            return 2.8 if situation.incoming_strength <= 0.08 and elixir < 7.0 else -0.5
        return 1.5 if elixir < 4.0 else -1.0


def pfsp_weights(
    candidate_score_rates: Mapping[str, float],
    *,
    power: float = 1.0,
    floor: float = 0.02,
) -> dict[str, float]:
    """Return prioritized-fictitious-self-play weights from score rates.

    Hard opponents receive more mass via ``(1 - score_rate) ** power``. A
    small floor retains coverage of already-mastered opponents. The function
    is pure so the exact league produced from an evaluation JSON is auditable.
    """

    if power <= 0.0:
        raise ValueError("power must be positive")
    if floor < 0.0:
        raise ValueError("floor cannot be negative")
    if not candidate_score_rates:
        raise ValueError("at least one opponent score is required")
    raw = {
        name: max(floor, (1.0 - float(np.clip(score, 0.0, 1.0))) ** power)
        for name, score in candidate_score_rates.items()
    }
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def allocate_pfsp_slots(
    weights: Mapping[str, float],
    slots: int,
) -> tuple[str, ...]:
    """Deterministically round normalized PFSP weights into worker slots."""

    if slots <= 0:
        raise ValueError("slots must be positive")
    if not weights:
        raise ValueError("at least one PFSP weight is required")
    if any(name not in STRATEGY_NAMES for name in weights):
        raise ValueError("PFSP weights contain an unknown strategy")
    if any(
        not math.isfinite(float(weight)) or float(weight) < 0.0
        for weight in weights.values()
    ):
        raise ValueError("PFSP weights must be finite and non-negative")
    total = sum(float(weight) for weight in weights.values())
    if total <= 0.0:
        raise ValueError("at least one PFSP weight must be positive")
    normalized = {name: float(weight) / total for name, weight in weights.items()}
    exact = {name: normalized[name] * slots for name in normalized}
    counts = {name: math.floor(value) for name, value in exact.items()}
    remainder = slots - sum(counts.values())
    order = sorted(
        exact,
        key=lambda name: (-(exact[name] - counts[name]), name),
    )
    for name in order[:remainder]:
        counts[name] += 1
    return tuple(name for name in STRATEGY_NAMES for _ in range(counts.get(name, 0)))


@dataclass
class PFSPTable:
    """Small serializable match table used to build the next league phase."""

    results: dict[str, list[int]] = field(default_factory=dict)

    def record(self, opponent: str, *, wins: int, draws: int, losses: int) -> None:
        if min(wins, draws, losses) < 0:
            raise ValueError("match counts cannot be negative")
        bucket = self.results.setdefault(opponent, [0, 0, 0])
        bucket[0] += int(wins)
        bucket[1] += int(draws)
        bucket[2] += int(losses)

    def score_rates(self) -> dict[str, float]:
        rates: dict[str, float] = {}
        for name, (wins, draws, losses) in self.results.items():
            games = wins + draws + losses
            rates[name] = (wins + 0.5 * draws) / games if games else 0.5
        return rates

    def weights(self, *, power: float = 1.0, floor: float = 0.02) -> dict[str, float]:
        return pfsp_weights(self.score_rates(), power=power, floor=floor)
