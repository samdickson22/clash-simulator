from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
import time
import math
import random
import copy
import json
from operator import attrgetter
import numpy as np
try:
    from numba import njit
except Exception:  # pragma: no cover - optional accelerator
    njit = None

from .entities import Entity, Troop, Building, Projectile
from .player import PlayerState
from .arena import TileGrid, Position
from .card_aliases import resolve_card_name
from .data import CardDataLoader
from .card_types import CardStatsCompat
from .factory.dynamic_factory import (
    building_from_values,
    troop_from_character_data,
)
from .spells import SPELL_REGISTRY
from .mechanics.shared.death_effects import DeathSpawn
from .native_tilemap import (
    OUTERMOST_OBJECT_CENTER_TILES,
    native_spawn_tile_blocked,
)
from .unit_traits import (
    is_air_unit_card,
    is_airborne_target,
    is_native_building_target,
)
from .kinematics import (
    LOGIC_TICK_SECONDS,
    SERVER_ACTION_DELAY_SECONDS,
    logic_units_to_tiles,
    tiles_to_logic_units,
    trunc_div,
)
from .logic_math import spawn_target_distance_discount_sq_units
from .balance import (
    DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS,
    LOGIC_SYMMETRICAL_DEPLOY_SNAP,
)


# Clash's deterministic logic update advances in fixed 50 ms quanta. Visual
# rendering may interpolate at a higher frame rate, but combat, movement,
# buffs, projectiles, and deployment all share this 20 Hz simulation clock.
DEFAULT_TICK_SECONDS = LOGIC_TICK_SECONDS
STANDARD_MATCH_DURATION_SECONDS = 300.0
STANDARD_MATCH_TICKS = math.ceil(STANDARD_MATCH_DURATION_SECONDS / DEFAULT_TICK_SECONDS)

# Reference/benchmark switch for allocation-free integer bucket indexing.
_USE_DENSE_ENTITY_BUCKETS = True

# Reference/benchmark switch for exact spatial collision candidate pruning.
_USE_COLLISION_BUCKET_CANDIDATES = True

# Reference/benchmark switch for restoring bucket candidates to exact entity
# encounter order without allocating a second result list and lambda.
_USE_INPLACE_BUCKET_ID_SORT = True
_ENTITY_ID_KEY = attrgetter("id")

# Reference/benchmark switch for scanning the dense row-major bucket grid in
# storage order and computing its row offset once per queried row.
_USE_ROW_MAJOR_BUCKET_SCAN = True

# Reference/benchmark switch for reusing the exact geometry published by the
# rebuild that created the current entity bucket grid.
_USE_CACHED_BUCKET_GEOMETRY = True

# Reference/benchmark switch for targetability predicates that cannot change
# after an ordinary target has joined the battle. Stealth remains a separate
# timestamp array in the vectorized selector, while hidden/death-immunity and
# mechanic-owned gates retain the full dynamic predicate.
_USE_STATIC_TARGETABILITY_CLASSIFICATION = True

@dataclass(frozen=True)
class PendingSpellCast:
    """A spell command waiting for the server's universal action delay."""

    execute_at: float
    sequence: int
    spell_name: str
    player_id: int
    position: Position


@dataclass(frozen=True)
class PendingProjectileImpact:
    """A projectile impact and the targets overlapped on its arrival frame."""

    projectile: Projectile
    targets: tuple[Entity, ...]


if njit is not None:
    @njit(cache=True)
    def _build_blocked_mask_numba(
        height: int,
        width: int,
        half_size: float,
        bounds: np.ndarray,
    ) -> np.ndarray:
        mask = np.zeros((height, width), dtype=np.bool_)
        for ty in range(height):
            y = ty + 0.5
            y1 = y - half_size
            y2 = y + half_size
            for tx in range(width):
                x = tx + 0.5
                x1 = x - half_size
                x2 = x + half_size
                blocked = False
                for i in range(bounds.shape[0]):
                    ex1 = bounds[i, 0]
                    ex2 = bounds[i, 1]
                    ey1 = bounds[i, 2]
                    ey2 = bounds[i, 3]
                    if x1 < ex2 and x2 > ex1 and y1 < ey2 and y2 > ey1:
                        blocked = True
                        break
                if blocked:
                    mask[ty, tx] = True
        return mask


@dataclass
class BattleState:
    # Core state
    entities: Dict[int, Entity] = field(default_factory=dict)
    players: List[PlayerState] = field(default_factory=lambda: [PlayerState(0), PlayerState(1)])
    arena: TileGrid = field(default_factory=TileGrid)
    
    # Timing
    time: float = 0.0
    tick: int = 0
    dt: float = DEFAULT_TICK_SECONDS  # 50 ms native logic tick (20 Hz)
    
    # Game state
    double_elixir: bool = False
    triple_elixir: bool = False
    overtime: bool = False
    sudden_death: bool = False
    game_over: bool = False
    winner: Optional[int] = None
    double_elixir_start_time: float = 120.0
    overtime_start_time: float = 180.0
    triple_elixir_start_time: float = 240.0
    tiebreaker_time: float = 300.0
    
    # Data
    card_loader: CardDataLoader = field(default_factory=CardDataLoader)
    rng: random.Random = field(default_factory=random.Random, repr=False)
    next_entity_id: int = 1
    _starting_total_tower_hp: Dict[int, float] = field(default_factory=dict, init=False)
    _starting_tower_hps: Dict[int, Dict[str, float]] = field(default_factory=dict, init=False)
    _sudden_death_crowns: Tuple[int, int] = field(default=(0, 0), init=False)
    debug_logs: bool = False
    fast_path: bool = False
    _bucket_cell_size: float = 2.0
    _entity_buckets: Dict[Tuple[int, int], List[Entity]] = field(default_factory=dict, init=False)
    _entity_bucket_grid: List[Optional[List[Entity]]] = field(
        default_factory=list,
        init=False,
    )
    _entity_bucket_grid_width: int = field(default=0, init=False)
    _entity_bucket_grid_height: int = field(default=0, init=False, repr=False)
    _entity_bucket_inverse_cell_size: float = field(
        default=0.5,
        init=False,
        repr=False,
    )
    _entity_bucket_max_dimension: float = field(
        default=32.0,
        init=False,
        repr=False,
    )
    _entity_bucket_entity_count: int = field(default=-1, init=False)
    _alive_buildings: List[Building] = field(default_factory=list, init=False)
    _tower_tile_mask_world: np.ndarray = field(
        default_factory=lambda: np.zeros((32, 18), dtype=np.bool_), init=False
    )
    _building_placement_blocked_masks: Dict[int, np.ndarray] = field(default_factory=dict, init=False)
    _troop_placement_blocked_masks: dict[float, np.ndarray] = field(
        default_factory=dict, init=False
    )
    _building_cache_signature: Tuple[int, ...] = field(default_factory=tuple, init=False)
    _cached_tower_alive_flags: Tuple[bool, bool, bool, bool, bool, bool] = field(
        default_factory=lambda: (False, False, False, False, False, False), init=False
    )
    _target_entities: List[Entity] = field(default_factory=list, init=False)
    _target_index_by_id: Dict[int, int] = field(default_factory=dict, init=False)
    _target_cache_entity_count: int = field(default=-1, init=False)
    _target_pos_x: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float64), init=False)
    _target_pos_y: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float64), init=False)
    _target_player: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.int8), init=False)
    _target_is_air: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False)
    _target_is_building: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False)
    _target_is_building_target: np.ndarray = field(
        default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False
    )
    _target_is_crown: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False)
    _target_is_targetable: np.ndarray = field(
        default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False
    )
    _target_requires_targetability_check: np.ndarray = field(
        default_factory=lambda: np.zeros((0,), dtype=np.bool_), init=False
    )
    _crown_target_entities_by_player: Tuple[List[Entity], List[Entity]] = field(
        default_factory=lambda: ([], []), init=False
    )
    _target_stealth_until: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.int32), init=False)
    _target_collision_radius: np.ndarray = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64), init=False
    )
    _target_distance_discount_sq: np.ndarray = field(
        default_factory=lambda: np.zeros((0,), dtype=np.float64), init=False
    )
    _max_target_collision_radius: float = field(default=0.5, init=False)
    _pending_spell_casts: List[PendingSpellCast] = field(default_factory=list, init=False)
    _next_spell_cast_sequence: int = field(default=0, init=False)
    _pending_projectile_impacts: List[PendingProjectileImpact] = field(
        default_factory=list,
        init=False,
    )
    _defer_projectile_impacts: bool = field(default=False, init=False)
    _step_tick_remainder: float = field(default=0.0, init=False)
    _champion_ability_owner_ids: Dict[Tuple[int, str], int] = field(
        default_factory=dict,
        init=False,
    )
    
    def __post_init__(self) -> None:
        """Initialize battle state"""
        self.card_loader.load_cards()
        self._create_towers()
        # PlayerState is also used as the public tower-health view.  Seed it
        # from the actual tower entities so level/balance data and the public
        # state cannot disagree before the first simulation tick (including
        # when an idle segment is fast-forwarded without entity updates).
        self._update_tower_hp()
        self._starting_total_tower_hp = {
            0: self.players[0].king_tower_hp + self.players[0].left_tower_hp + self.players[0].right_tower_hp,
            1: self.players[1].king_tower_hp + self.players[1].left_tower_hp + self.players[1].right_tower_hp,
        }
        self._starting_tower_hps = {
            0: {
                "left": float(self.players[0].left_tower_hp),
                "right": float(self.players[0].right_tower_hp),
                "king": float(self.players[0].king_tower_hp),
            },
            1: {
                "left": float(self.players[1].left_tower_hp),
                "right": float(self.players[1].right_tower_hp),
                "king": float(self.players[1].king_tower_hp),
            },
        }
        self._refresh_fast_path_caches()

    def clone(self) -> "BattleState":
        """Clone mutable battle state without copying the full card catalog."""

        loader = self.card_loader.clone_lazy()
        memo: dict[int, Any] = {id(self.card_loader): loader}
        for definition in self.card_loader.load_card_definitions().values():
            # CardDefinition is frozen and its normalized source snapshot is
            # process-global. Mutable CardStatsCompat wrappers are still copied.
            memo[id(definition)] = definition
        return copy.deepcopy(self, memo)
    
    def _create_towers(self) -> None:
        """Create tower entities for both players"""
        from .balance import tournament_tower_stat

        princess_data = self._load_princess_tower_character_data()
        princess_hitpoints = tournament_tower_stat("PrincessTower", "hitpoints") or 3052
        princess_range_tiles = princess_data["range"] / 1000.0
        princess_sight_tiles = princess_data["sightRange"] / 1000.0
        princess_hit_speed_ms = princess_data["hitSpeed"]
        # Arena towers already exist when the match begins; the compact
        # support payload therefore does not serialize a placement delay.
        princess_deploy_ms = 0
        princess_collision_tiles = princess_data["collisionRadius"] / 1000.0
        princess_projectile = princess_data["projectileData"]
        princess_damage = tournament_tower_stat("PrincessTower", "damage") or 109
        princess_projectile_speed = princess_projectile.get("speed", 600)
        princess_projectile_start_radius = tournament_tower_stat(
            "PrincessTower",
            "projectile_start_radius",
        )
        if princess_projectile_start_radius is None:
            raise ValueError("Missing PrincessTower projectile muzzle data")
        princess_target_type = princess_data["tidTarget"]

        tower_stats = building_from_values(
            name="Tower",
            hitpoints=princess_hitpoints,
            damage=princess_damage,
            range_tiles=princess_range_tiles,
            sight_range_tiles=princess_sight_tiles,
            hit_speed_ms=princess_hit_speed_ms,
            deploy_time_ms=princess_deploy_ms,
            collision_radius_tiles=princess_collision_tiles,
            lifetime_ms=None,
            elixir=0,
            rarity="Common",
            projectile_speed=princess_projectile_speed,
            projectile_damage=princess_damage,
            projectile_start_radius=princess_projectile_start_radius,
            target_type=princess_target_type,
            raw_overrides={"level": 1},
        )

        king_hitpoints = tournament_tower_stat("KingTower", "hitpoints") or 4824
        king_damage = tournament_tower_stat("KingTower", "damage") or 109
        king_load_time = tournament_tower_stat("KingTower", "load_time")
        king_activation_duration = tournament_tower_stat(
            "KingTower",
            "activation_duration",
        )
        if king_load_time is None or king_activation_duration is None:
            raise ValueError("Missing KingTower native timing data")
        king_stats = building_from_values(
            name="KingTower",
            hitpoints=king_hitpoints,
            damage=king_damage,
            range_tiles=7.0,
            sight_range_tiles=7.0,
            hit_speed_ms=1000,
            deploy_time_ms=1000,
            load_time_ms=king_load_time,
            collision_radius_tiles=1.4,
            lifetime_ms=None,
            elixir=0,
            rarity="Common",
            projectile_speed=1000,
            projectile_damage=king_damage,
            projectile_start_radius=750,
            projectile_y_offset=400,
            target_type="TID_TARGETS_AIR_AND_GROUND",
            raw_overrides={"level": 1},
        )
        
        # Player 0 towers (blue) - create new Position objects to avoid sharing references
        blue_left = Position(self.arena.BLUE_LEFT_TOWER.x, self.arena.BLUE_LEFT_TOWER.y)
        blue_right = Position(self.arena.BLUE_RIGHT_TOWER.x, self.arena.BLUE_RIGHT_TOWER.y)
        blue_king = Position(self.arena.BLUE_KING_TOWER.x, self.arena.BLUE_KING_TOWER.y)
        blue_towers = (
            self._spawn_entity(Building, blue_left, 0, tower_stats),
            self._spawn_entity(Building, blue_right, 0, tower_stats),
            self._spawn_entity(Building, blue_king, 0, king_stats),
        )
        
        # Player 1 towers (red) - create new Position objects to avoid sharing references
        red_left = Position(self.arena.RED_LEFT_TOWER.x, self.arena.RED_LEFT_TOWER.y)
        red_right = Position(self.arena.RED_RIGHT_TOWER.x, self.arena.RED_RIGHT_TOWER.y)
        red_king = Position(self.arena.RED_KING_TOWER.x, self.arena.RED_KING_TOWER.y)
        red_towers = (
            self._spawn_entity(Building, red_left, 1, tower_stats),
            self._spawn_entity(Building, red_right, 1, tower_stats),
            self._spawn_entity(Building, red_king, 1, king_stats),
        )
        for towers in (blue_towers, red_towers):
            for tower, slot in zip(towers, ("left", "right", "king")):
                tower._crown_tower_slot = slot
        # Arena towers exist before the match begins. Their serialized deploy
        # animation time is an attack-animation datum, not a battle placement
        # window.
        for tower in blue_towers + red_towers:
            tower.deploy_delay_remaining = 0.0
            tower.on_spawn()

    def _load_princess_tower_character_data(self) -> dict:
        """Load Princess Tower baseline stats from support-card data in gamedata."""
        with open(self.card_loader.data_file, "r") as f:
            spells = json.load(f).get("items", {}).get("spells", [])
        for entry in spells:
            if entry.get("name") == "King_PrincessTowers":
                data = entry.get("statCharacterData")
                if isinstance(data, dict):
                    return data
                raise ValueError("King_PrincessTowers has no statCharacterData")
        raise ValueError("King_PrincessTowers is missing from game data")

    def _refresh_fast_path_caches(self) -> None:
        """Refresh caches used by fast-path queries."""
        self._refresh_alive_buildings_cache()
        self._refresh_tower_mask_if_needed()
        self._rebuild_entity_buckets()
        self._refresh_target_cache()

    def _refresh_alive_buildings_cache(self) -> None:
        """Publish live building membership to every accelerated query.

        Player commands can create or destroy a building between two action
        validations, before the next logic tick refreshes the broader fast
        caches. Placement queries must observe that mutation immediately.
        """
        alive_buildings = [
            e for e in self.entities.values() if isinstance(e, Building) and e.is_alive
        ]
        building_sig = tuple(sorted(e.id for e in alive_buildings))
        if building_sig != self._building_cache_signature:
            self._alive_buildings = alive_buildings
            self._building_cache_signature = building_sig
            self._building_placement_blocked_masks.clear()
            self._troop_placement_blocked_masks.clear()

    def _rebuild_target_cache(self) -> None:
        self._target_cache_entity_count = len(self.entities)
        targets: List[Entity] = []
        for entity in self.entities.values():
            if not entity.is_alive:
                continue
            if getattr(entity, "entity_kind", 4) in {2, 3}:
                continue
            targets.append(entity)
        self._target_entities = targets
        self._target_index_by_id = {entity.id: index for index, entity in enumerate(targets)}
        n = len(targets)
        if n == 0:
            self._target_pos_x = np.zeros((0,), dtype=np.float64)
            self._target_pos_y = np.zeros((0,), dtype=np.float64)
            self._target_player = np.zeros((0,), dtype=np.int8)
            self._target_is_air = np.zeros((0,), dtype=np.bool_)
            self._target_is_building = np.zeros((0,), dtype=np.bool_)
            self._target_is_building_target = np.zeros((0,), dtype=np.bool_)
            self._target_is_crown = np.zeros((0,), dtype=np.bool_)
            self._target_is_targetable = np.zeros((0,), dtype=np.bool_)
            self._target_requires_targetability_check = np.zeros(
                (0,), dtype=np.bool_
            )
            self._crown_target_entities_by_player = ([], [])
            self._target_stealth_until = np.zeros((0,), dtype=np.int32)
            self._target_collision_radius = np.zeros((0,), dtype=np.float64)
            self._target_distance_discount_sq = np.zeros((0,), dtype=np.float64)
            self._max_target_collision_radius = 0.5
            return

        pos_x = np.empty((n,), dtype=np.float64)
        pos_y = np.empty((n,), dtype=np.float64)
        player = np.empty((n,), dtype=np.int8)
        is_air = np.empty((n,), dtype=np.bool_)
        is_building = np.empty((n,), dtype=np.bool_)
        is_building_target = np.empty((n,), dtype=np.bool_)
        is_crown = np.empty((n,), dtype=np.bool_)
        is_targetable = np.empty((n,), dtype=np.bool_)
        requires_targetability_check = np.empty((n,), dtype=np.bool_)
        stealth_until = np.empty((n,), dtype=np.int32)
        collision_radius = np.empty((n,), dtype=np.float64)
        target_distance_discount_sq = np.empty((n,), dtype=np.float64)
        crown_targets_by_player: Tuple[List[Entity], List[Entity]] = ([], [])

        for i, entity in enumerate(targets):
            pos_x[i] = float(entity.position.x)
            pos_y[i] = float(entity.position.y)
            player[i] = int(entity.player_id)
            is_air[i] = is_airborne_target(entity)
            building = bool(getattr(entity, "entity_kind", 4) == 1)
            is_building[i] = building
            is_building_target[i] = is_native_building_target(entity)
            if building:
                name = getattr(getattr(entity, "card_stats", None), "name", "")
                is_crown[i] = name in {"Tower", "KingTower"} or bool(getattr(entity, "_is_king_tower", False))
            else:
                is_crown[i] = False
            if is_crown[i] and entity.player_id in {0, 1}:
                crown_targets_by_player[entity.player_id].append(entity)
            requires_check = self._requires_targetability_check(entity)
            requires_targetability_check[i] = requires_check
            is_targetable[i] = (
                entity.is_targetable_by(1 - entity.player_id)
                if requires_check or not _USE_STATIC_TARGETABILITY_CLASSIFICATION
                else True
            )
            stealth_until[i] = int(getattr(entity, "_stealth_until", 0) or 0)
            collision_radius[i] = entity.get_collision_radius()
            target_distance_discount_sq[i] = (
                max(
                    0,
                    int(
                        getattr(
                            entity,
                            "_native_target_distance_discount_sq_units",
                            0,
                        )
                        or 0
                    ),
                )
                / 1_000_000.0
            )

        self._target_pos_x = pos_x
        self._target_pos_y = pos_y
        self._target_player = player
        self._target_is_air = is_air
        self._target_is_building = is_building
        self._target_is_building_target = is_building_target
        self._target_is_crown = is_crown
        self._target_is_targetable = is_targetable
        self._target_requires_targetability_check = requires_targetability_check
        self._crown_target_entities_by_player = crown_targets_by_player
        self._target_stealth_until = stealth_until
        self._target_collision_radius = collision_radius
        self._target_distance_discount_sq = target_distance_discount_sq
        self._max_target_collision_radius = float(np.max(collision_radius))

    def _refresh_target_cache(self) -> None:
        """Refresh target values in place when cache membership is unchanged.

        Entity insertion order is stable, so an identity scan detects every
        structural change, including a remove/add pair that leaves the entity
        dictionary at the same size. Reusing the arrays avoids rebuilding the
        ID index and allocating eleven target-property arrays each logic tick.
        Dynamic properties are still republished so this remains exact for
        movement, target-plane, stealth, and targetability changes. Static
        properties are published at structural rebuilds and their explicit
        post-spawn mutation sites.
        """
        target_index = 0
        cached_count = len(self._target_entities)
        for entity in self.entities.values():
            if not self._eligible_fast_target(entity):
                continue
            if (
                target_index >= cached_count
                or self._target_entities[target_index] is not entity
            ):
                self._rebuild_target_cache()
                return
            self._refresh_fast_target_dynamic_values(target_index, entity)
            target_index += 1

        if target_index != cached_count:
            self._rebuild_target_cache()
            return
        self._target_cache_entity_count = len(self.entities)

    def _refresh_fast_target_dynamic_values(
        self,
        index: int,
        entity: Entity,
    ) -> None:
        """Publish target properties that can change after insertion."""
        self._target_pos_x[index] = float(entity.position.x)
        self._target_pos_y[index] = float(entity.position.y)
        self._target_is_air[index] = is_airborne_target(entity)
        if (
            not _USE_STATIC_TARGETABILITY_CLASSIFICATION
            or self._target_requires_targetability_check[index]
        ):
            self._target_is_targetable[index] = entity.is_targetable_by(
                1 - entity.player_id
            )
        self._target_stealth_until[index] = int(
            getattr(entity, "_stealth_until", 0) or 0
        )

    def _refresh_fast_target_static_values(
        self,
        index: int,
        entity: Entity,
    ) -> None:
        """Publish target properties that are immutable after spawn setup."""
        self._target_player[index] = int(entity.player_id)
        building = bool(getattr(entity, "entity_kind", 4) == 1)
        self._target_is_building[index] = building
        self._target_is_building_target[index] = is_native_building_target(entity)
        if building:
            name = getattr(getattr(entity, "card_stats", None), "name", "")
            self._target_is_crown[index] = name in {"Tower", "KingTower"} or bool(
                getattr(entity, "_is_king_tower", False)
            )
        else:
            self._target_is_crown[index] = False
        self._target_collision_radius[index] = entity.get_collision_radius()
        self._target_distance_discount_sq[index] = (
            max(
                0,
                int(
                    getattr(
                        entity,
                        "_native_target_distance_discount_sq_units",
                        0,
                    )
                    or 0
                ),
            )
            / 1_000_000.0
        )

    def sync_fast_target_static_entity(self, entity: Entity) -> None:
        """Publish rare post-insertion setup of an otherwise static target."""
        if not self.fast_path:
            return
        index = self._target_index_by_id.get(entity.id)
        if index is None:
            self._rebuild_target_cache()
            index = self._target_index_by_id.get(entity.id)
        if index is not None:
            was_crown = bool(self._target_is_crown[index])
            self._refresh_fast_target_static_values(index, entity)
            if bool(self._target_is_crown[index]) != was_crown:
                self._rebuild_target_cache()
                return
            self._max_target_collision_radius = float(
                np.max(self._target_collision_radius)
            )

    @staticmethod
    def _eligible_fast_target(entity: Entity) -> bool:
        return bool(
            entity.is_alive
            and getattr(entity, "entity_kind", 4) not in {2, 3}
        )

    @staticmethod
    def _requires_targetability_check(entity: Entity) -> bool:
        """Return whether non-stealth targetability can change after insert.

        The vectorized selector applies stealth timestamps independently.
        Every other mutable gate in ``Entity.is_targetable_by`` is represented
        by one of these data/mechanic-owned states. Mechanics are attached
        before manager insertion and remain stable for the entity lifetime.
        """
        return bool(
            entity._has_death_spawn_target_immunity()
            or hasattr(entity, "_hidden_building")
            or any(
                callable(getattr(mechanic, "blocks_targeting", None))
                for mechanic in entity.mechanics
            )
        )

    def _sync_fast_target_entity(self, entity: Entity) -> bool:
        """Keep one updated unit coherent in the vectorized target cache.

        Returns ``False`` when membership changed and a structural cache
        rebuild is required. Position and stealth changes are updated in
        place, preserving fast-path targeting without tick-order drift from
        the scalar engine.
        """
        index = self._target_index_by_id.get(entity.id)
        eligible = self._eligible_fast_target(entity)
        if eligible != (index is not None):
            return False
        if index is None:
            return True
        self._target_pos_x[index] = float(entity.position.x)
        self._target_pos_y[index] = float(entity.position.y)
        self._target_is_air[index] = is_airborne_target(entity)
        if (
            not _USE_STATIC_TARGETABILITY_CLASSIFICATION
            or self._target_requires_targetability_check[index]
        ):
            self._target_is_targetable[index] = entity.is_targetable_by(
                1 - entity.player_id
            )
        self._target_stealth_until[index] = int(
            getattr(entity, "_stealth_until", 0) or 0
        )
        return True

    def sync_fast_target_entity(self, entity: Entity) -> None:
        """Publish an out-of-turn movement/state change to fast targeting."""
        if self.fast_path and not self._sync_fast_target_entity(entity):
            self._rebuild_target_cache()

    def get_fast_target_cache(self) -> tuple[
        List[Entity],
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        # Death hooks and other combat callbacks can synchronously append
        # targetable characters before the current combat component returns.
        # Publish that structural change at the next target query, rather than
        # waiting for the end-of-component refresh and making fast targeting
        # observe a different object list from the scalar engine.
        if (
            self.fast_path
            and self._target_cache_entity_count != len(self.entities)
        ):
            self._refresh_fast_path_caches()
        return (
            self._target_entities,
            self._target_pos_x,
            self._target_pos_y,
            self._target_player,
            self._target_is_air,
            self._target_is_building,
            self._target_is_building_target,
            self._target_is_crown,
            self._target_is_targetable,
            self._target_stealth_until,
            self._target_collision_radius,
            self._target_distance_discount_sq,
        )

    def get_fast_crown_target_entities(self, player_id: int) -> List[Entity]:
        """Return exact live Crown fallback membership for one owner."""
        if (
            self.fast_path
            and self._target_cache_entity_count != len(self.entities)
        ):
            self._refresh_fast_path_caches()
        if player_id not in {0, 1}:
            return []
        return self._crown_target_entities_by_player[player_id]

    def _refresh_tower_mask_if_needed(self) -> None:
        alive_flags = self._tower_alive_flags()
        if alive_flags != self._cached_tower_alive_flags:
            self._update_tower_tile_mask_world()

    def _rebuild_entity_buckets(self) -> None:
        self._entity_bucket_entity_count = len(self.entities)
        inv = 1.0 / max(0.25, self._bucket_cell_size)
        self._entity_bucket_inverse_cell_size = inv
        self._entity_bucket_max_dimension = float(
            max(self.arena.width, self.arena.height)
        )
        if not self.fast_path:
            self._entity_buckets = {}
            self._entity_bucket_grid = []
            self._entity_bucket_grid_width = 0
            self._entity_bucket_grid_height = 0
            return
        if _USE_DENSE_ENTITY_BUCKETS:
            width = int((self.arena.width - 1e-6) * inv) + 1
            height = int((self.arena.height - 1e-6) * inv) + 1
            bucket_grid: List[Optional[List[Entity]]] = [None] * (width * height)
            populated = False
            for entity in self.entities.values():
                if not entity.is_alive:
                    continue
                bx = int(entity.position.x * inv)
                by = int(entity.position.y * inv)
                if 0 <= bx < width and 0 <= by < height:
                    bucket_index = by * width + bx
                    bucket = bucket_grid[bucket_index]
                    if bucket is None:
                        bucket = []
                        bucket_grid[bucket_index] = bucket
                    bucket.append(entity)
                    populated = True
            self._entity_buckets = {}
            self._entity_bucket_grid = bucket_grid if populated else []
            self._entity_bucket_grid_width = width
            self._entity_bucket_grid_height = height
            return

        buckets: Dict[Tuple[int, int], List[Entity]] = defaultdict(list)
        for entity in self.entities.values():
            if not entity.is_alive:
                continue
            bx = int(entity.position.x * inv)
            by = int(entity.position.y * inv)
            buckets[(bx, by)].append(entity)
        self._entity_buckets = dict(buckets)
        self._entity_bucket_grid = []
        self._entity_bucket_grid_width = 0
        self._entity_bucket_grid_height = 0

    def iter_entities_in_radius(self, position: Position, radius: float) -> List[Entity]:
        """Return candidate entities near position for fast target selection."""
        if (
            self.fast_path
            and self._entity_bucket_entity_count != len(self.entities)
        ):
            self._refresh_fast_path_caches()
        if not self.fast_path:
            return list(self.entities.values())
        if _USE_DENSE_ENTITY_BUCKETS:
            if not self._entity_bucket_grid:
                return list(self.entities.values())
        elif not self._entity_buckets:
            return list(self.entities.values())
        if _USE_CACHED_BUCKET_GEOMETRY:
            inv = self._entity_bucket_inverse_cell_size
            max_dim = self._entity_bucket_max_dimension
        else:
            inv = 1.0 / max(0.25, self._bucket_cell_size)
            max_dim = float(max(self.arena.width, self.arena.height))
        if radius >= max_dim:
            return list(self.entities.values())
        pad = max(0.5, min(radius + 2.0, max_dim))
        if _USE_CACHED_BUCKET_GEOMETRY and _USE_DENSE_ENTITY_BUCKETS:
            max_bx_bound = self._entity_bucket_grid_width - 1
            max_by_bound = self._entity_bucket_grid_height - 1
        else:
            max_bx_bound = int((self.arena.width - 1e-6) * inv)
            max_by_bound = int((self.arena.height - 1e-6) * inv)
        min_bx = max(0, int((position.x - pad) * inv))
        max_bx = min(max_bx_bound, int((position.x + pad) * inv))
        min_by = max(0, int((position.y - pad) * inv))
        max_by = min(max_by_bound, int((position.y + pad) * inv))
        out: List[Entity] = []
        if _USE_DENSE_ENTITY_BUCKETS and _USE_ROW_MAJOR_BUCKET_SCAN:
            width = self._entity_bucket_grid_width
            for by in range(min_by, max_by + 1):
                row_offset = by * width
                for bx in range(min_bx, max_bx + 1):
                    bucket = self._entity_bucket_grid[
                        row_offset + bx
                    ]
                    if bucket is not None:
                        out.extend(bucket)
        else:
            for bx in range(min_bx, max_bx + 1):
                for by in range(min_by, max_by + 1):
                    if _USE_DENSE_ENTITY_BUCKETS:
                        bucket = self._entity_bucket_grid[
                            by * self._entity_bucket_grid_width + bx
                        ]
                        if bucket is not None:
                            out.extend(bucket)
                    else:
                        out.extend(self._entity_buckets.get((bx, by), []))
        # Target ties retain native object encounter order. Bucket traversal
        # is spatial rather than object ordered, so restore ID order before a
        # scalar fallback scans this reduced candidate set.
        if _USE_INPLACE_BUCKET_ID_SORT:
            out.sort(key=_ENTITY_ID_KEY)
            return out
        return sorted(out, key=lambda entity: entity.id)

    def _tower_alive_flags(self) -> Tuple[bool, bool, bool, bool, bool, bool]:
        return (
            self.players[0].left_tower_hp > 0.0,
            self.players[0].right_tower_hp > 0.0,
            self.players[0].king_tower_hp > 0.0,
            self.players[1].left_tower_hp > 0.0,
            self.players[1].right_tower_hp > 0.0,
            self.players[1].king_tower_hp > 0.0,
        )

    def _is_tower_alive_cached(self, tower_pos: Position, player_id: int) -> bool:
        """Fast tower alive lookup by fixed arena position."""
        if player_id == 0:
            if tower_pos.x == self.arena.BLUE_LEFT_TOWER.x and tower_pos.y == self.arena.BLUE_LEFT_TOWER.y:
                return self.players[0].left_tower_hp > 0.0
            if tower_pos.x == self.arena.BLUE_RIGHT_TOWER.x and tower_pos.y == self.arena.BLUE_RIGHT_TOWER.y:
                return self.players[0].right_tower_hp > 0.0
            return self.players[0].king_tower_hp > 0.0
        if tower_pos.x == self.arena.RED_LEFT_TOWER.x and tower_pos.y == self.arena.RED_LEFT_TOWER.y:
            return self.players[1].left_tower_hp > 0.0
        if tower_pos.x == self.arena.RED_RIGHT_TOWER.x and tower_pos.y == self.arena.RED_RIGHT_TOWER.y:
            return self.players[1].right_tower_hp > 0.0
        return self.players[1].king_tower_hp > 0.0

    def _update_tower_tile_mask_world(self) -> None:
        """Build world-tile mask blocked by living towers."""
        alive_flags = self._tower_alive_flags()
        mask = np.zeros((self.arena.height, self.arena.width), dtype=np.bool_)
        towers = [
            (self.arena.BLUE_LEFT_TOWER, 1.5, 0),
            (self.arena.BLUE_RIGHT_TOWER, 1.5, 0),
            (self.arena.BLUE_KING_TOWER, 2.0, 0),
            (self.arena.RED_LEFT_TOWER, 1.5, 1),
            (self.arena.RED_RIGHT_TOWER, 1.5, 1),
            (self.arena.RED_KING_TOWER, 2.0, 1),
        ]
        for tower_pos, radius, player_id in towers:
            if not self._is_tower_alive_cached(tower_pos, player_id):
                continue
            x_min = max(0, int(math.floor(tower_pos.x - radius)))
            x_max = min(self.arena.width - 1, int(math.floor(tower_pos.x + radius)))
            y_min = max(0, int(math.floor(tower_pos.y - radius)))
            y_max = min(self.arena.height - 1, int(math.floor(tower_pos.y + radius)))
            for ty in range(y_min, y_max + 1):
                cy = ty + 0.5
                if abs(cy - tower_pos.y) > radius + 1e-9:
                    continue
                for tx in range(x_min, x_max + 1):
                    cx = tx + 0.5
                    if abs(cx - tower_pos.x) <= radius + 1e-9:
                        mask[ty, tx] = True
        self._tower_tile_mask_world = mask
        self._cached_tower_alive_flags = alive_flags

    def get_tower_tile_mask_world(self) -> np.ndarray:
        self._refresh_tower_mask_if_needed()
        if self._tower_tile_mask_world.shape != (self.arena.height, self.arena.width):
            self._update_tower_tile_mask_world()
        return self._tower_tile_mask_world

    def get_building_placement_blocked_mask_world(self, size_tiles: int) -> np.ndarray:
        """Return world-tile mask where a building of size_tiles cannot be centered."""
        self._refresh_alive_buildings_cache()
        cached = self._building_placement_blocked_masks.get(size_tiles)
        if cached is not None:
            return cached
        half = float(size_tiles) / 2.0
        if self._alive_buildings:
            bounds = np.empty((len(self._alive_buildings), 4), dtype=np.float32)
            for i, entity in enumerate(self._alive_buildings):
                ex1, ex2, ey1, ey2 = self._footprint_bounds(entity.position, entity.card_stats)
                bounds[i, 0] = ex1
                bounds[i, 1] = ex2
                bounds[i, 2] = ey1
                bounds[i, 3] = ey2
            if njit is not None:
                mask = _build_blocked_mask_numba(
                    self.arena.height,
                    self.arena.width,
                    half,
                    bounds,
                )
            else:
                mask = np.zeros((self.arena.height, self.arena.width), dtype=np.bool_)
                for ty in range(self.arena.height):
                    y = ty + 0.5
                    y1, y2 = y - half, y + half
                    for tx in range(self.arena.width):
                        x = tx + 0.5
                        x1, x2 = x - half, x + half
                        for i in range(bounds.shape[0]):
                            ex1 = bounds[i, 0]
                            ex2 = bounds[i, 1]
                            ey1 = bounds[i, 2]
                            ey2 = bounds[i, 3]
                            if x1 < ex2 and x2 > ex1 and y1 < ey2 and y2 > ey1:
                                mask[ty, tx] = True
                                break
        else:
            mask = np.zeros((self.arena.height, self.arena.width), dtype=np.bool_)
        self._building_placement_blocked_masks[size_tiles] = mask
        return mask

    def get_troop_placement_blocked_mask_world(
        self, mover_radius: float
    ) -> np.ndarray:
        """Return world tiles where a troop radius overlaps a live building."""
        self._refresh_alive_buildings_cache()
        radius = float(mover_radius)
        cached = self._troop_placement_blocked_masks.get(radius)
        if cached is not None:
            return cached

        mask = np.zeros((self.arena.height, self.arena.width), dtype=np.bool_)
        for entity in self._alive_buildings:
            building_radius = (
                getattr(entity.card_stats, "collision_radius", 1.0) or 1.0
            )
            collision_units = tiles_to_logic_units(float(building_radius) + radius)
            collision_sq = collision_units * collision_units
            for ty in range(self.arena.height):
                dy_units = tiles_to_logic_units(ty + 0.5 - entity.position.y)
                dy_sq = dy_units * dy_units
                if dy_sq >= collision_sq:
                    continue
                for tx in range(self.arena.width):
                    if mask[ty, tx]:
                        continue
                    dx_units = tiles_to_logic_units(tx + 0.5 - entity.position.x)
                    if dx_units * dx_units + dy_sq < collision_sq:
                        mask[ty, tx] = True

        self._troop_placement_blocked_masks[radius] = mask
        return mask
    
    def step(self, speed_factor: float = 1.0) -> None:
        """Advance by fixed native ticks, batching only the Python call."""
        factor = float(speed_factor)
        if not math.isfinite(factor) or factor < 0.0:
            raise ValueError("speed_factor must be a finite non-negative number")
        if self.game_over or factor == 0.0:
            return

        self._step_tick_remainder += factor
        ticks_to_advance = int(math.floor(self._step_tick_remainder + 1e-12))
        self._step_tick_remainder = max(
            0.0,
            self._step_tick_remainder - ticks_to_advance,
        )
        for _ in range(ticks_to_advance):
            if self.game_over:
                break
            self._step_logic_tick()

    def step_logic_ticks(self, ticks: int) -> int:
        """Advance an integer tick window with one final cache publication.

        Each tick retains its start-of-frame refresh and every explicit
        in-component synchronization. The end refresh is externally visible
        only after control returns to the caller, so a closed multi-tick
        decision window can publish it once after its final frame.
        """
        requested = max(0, int(ticks))
        advanced = 0
        for _ in range(requested):
            if self.game_over:
                break
            self._step_logic_tick(refresh_fast_path_end=False)
            advanced += 1
        if advanced and self.fast_path:
            self._refresh_fast_path_caches()
        return advanced

    def _step_logic_tick(self, *, refresh_fast_path_end: bool = True) -> None:
        """Advance exactly one 50 ms native logic frame."""
        if self.game_over:
            return
        
        dt = self.dt
        self.time += dt
        self.tick += 1
        
        self._update_battle_phases()
        
        # Regenerate elixir
        base_regen = 2.8
        if self.triple_elixir:
            base_regen = 0.93
        elif self.double_elixir:
            base_regen = 1.4
        
        for player in self.players:
            player.regenerate_elixir(dt, base_regen)
            player.tick_card_refill(
                self._next_card_refill_cooldown_ms(),
                round(dt * 1000.0),
            )

        # Commands become visible at this tick boundary. Entities created by
        # those commands did not exist during the elapsed 50 ms interval and
        # must not receive an update for it; time-based payloads begin ticking
        # next frame while immediate cast methods still resolve synchronously.
        entities_to_update = list(self.entities.values())
        initial_object_phase_ids = {
            entity.id for entity in entities_to_update
        }
        self._resolve_pending_spell_casts()
        post_command_ids = set(self.entities)

        if self.fast_path:
            self._refresh_fast_path_caches()
        
        # Target reservations are a start-of-tick snapshot. This makes
        # simultaneous attacks commute: a projectile launched by an entity
        # earlier in Python's iteration order cannot change another entity's
        # targeting decision until the next server tick.
        self._projectile_lethal_reservations = None
        reservation_targets = {
            primary_target.id: primary_target
            for projectile in self.entities.values()
            if callable(getattr(projectile, "expected_damage_against", None))
            and bool(getattr(projectile, "reserves_pending_damage", False))
            and projectile.is_alive
            and (primary_target := getattr(projectile, "primary_target", None)) is not None
            and primary_target.is_alive
        }
        self._projectile_lethal_reservations = frozenset(
            target.id
            for target in reservation_targets.values()
            if target.is_expected_to_die_from_projectiles()
        )
        self._pending_projectile_impacts = []
        self._defer_projectile_impacts = False
        try:
            # Component type 0: combat components run in object-ID order
            # against the same start-of-frame positions. Direct damage,
            # death state, and on-hit buffs are visible to every later
            # component, exactly as in LogicCombatComponent::tick.
            cached_entity_count = len(self.entities)
            for entity in entities_to_update:
                if not isinstance(entity, (Troop, Building)):
                    continue
                entity.update_combat_component(dt, self)
                # A few serialized special states currently commit their
                # travel inside the combat hook. Preserve the native grid at
                # this component boundary while their phase adapters remain
                # card-owned.
                entity.quantize_logic_position()
                if self.fast_path:
                    if len(self.entities) != cached_entity_count:
                        cached_entity_count = len(self.entities)
                        self._rebuild_entity_buckets()
                        self._rebuild_target_cache()
                    elif not self._sync_fast_target_entity(entity):
                        self._rebuild_target_cache()
        finally:
            self._defer_projectile_impacts = False
            self._projectile_lethal_reservations = None

        # Component type 1: movement and deployment-specific transport.
        for entity in entities_to_update:
            if not isinstance(entity, (Troop, Building)) or not entity.is_alive:
                continue
            if isinstance(entity, Troop):
                # Each native movement component scans positions at its own
                # boundary, so earlier movers affect later body pressure.
                # updatePushback skips checkCollisions on its final zero-work
                # frame, although already-queued controlled vectors (such as
                # Tornado attraction) can still be consumed.
                if not (
                    entity._knockback_target is not None
                    and entity._knockback_velocity_work < 1
                ):
                    self._accumulate_troop_collision_for(entity)
            entity.begin_movement_tick()
            try:
                entity.update_movement_component(dt, self)
            finally:
                entity.finish_movement_tick(self)
                entity.quantize_logic_position()
            if self.fast_path and not self._sync_fast_target_entity(entity):
                self._rebuild_target_cache()

        # Component type 2: building lifetime/hitpoint work.
        for entity in entities_to_update:
            if isinstance(entity, Building):
                entity.update_hitpoint_component(dt)

        # Component type 3: status clocks expire only after their final
        # combat and movement frame has consumed the modifier.
        for entity in entities_to_update:
            if isinstance(entity, (Troop, Building)):
                entity.update_buff_component(dt)

        self._run_object_phase(
            dt,
            initial_object_phase_ids,
            post_command_ids,
        )

        # Remove dead entities
        self._cleanup_dead_entities()

        if self.fast_path and refresh_fast_path_end:
            self._refresh_fast_path_caches()
        
        # Check win conditions
        self._check_win_conditions()

    def _run_object_phase(
        self,
        dt: float,
        initial_ids: set[int],
        post_command_ids: set[int],
    ) -> None:
        """Run the ID-ordered, dynamically growing native object phase.

        The native manager refreshes its object-list length while iterating.
        A projectile created by a combat component therefore receives its
        ``LogicProjectile::tick`` later in that same frame, as do chained
        projectile/area/explosive payloads appended by an earlier object tick.

        Characters use a dedicated object-phase entry point so a Witch spawn,
        death spawn, or Graveyard Skeleton consumes deployment time without
        replaying combat, movement, hitpoint, or buff components whose global
        phases have already passed.

        Objects materialized by a command at this tick boundary are excluded:
        they did not exist during the elapsed interval. Objects appended later
        by component/object work are included, matching the manager's growing
        list.
        """
        processed_ids = set(post_command_ids - initial_ids)
        while True:
            new_objects = sorted(
                (
                    entity
                    for entity_id, entity in self.entities.items()
                    if entity_id not in processed_ids
                ),
                key=lambda entity: entity.id,
            )
            if not new_objects:
                return
            for entity in new_objects:
                processed_ids.add(entity.id)
                if not entity.is_alive:
                    continue
                if isinstance(entity, (Troop, Building)):
                    entity.tick_character_object_phase(dt)
                else:
                    entity.begin_movement_tick()
                    try:
                        entity.update(dt, self)
                    finally:
                        entity.finish_movement_tick(self)
                entity.quantize_logic_position()

    def _is_static_tower_entity(self, entity: Entity) -> bool:
        return bool(
            isinstance(entity, Building)
            and getattr(entity, "_crown_tower_slot", None)
            in {"left", "right", "king"}
        )

    def can_fast_forward_idle(self) -> bool:
        if self.game_over:
            return False
        if self._pending_spell_casts:
            return False
        for entity in self.entities.values():
            if not entity.is_alive:
                continue
            if not self._is_static_tower_entity(entity):
                return False
            # The tower-only shortcut is valid only when a normal component
            # frame has no stateful work beyond the visualization clock.
            # Status expiry, King activation, and attack recovery all affect
            # the tower's next interaction.
            if (
                entity.mechanics
                or entity.deploy_delay_remaining > 1e-9
                or entity.target_id is not None
                or entity._attack_windup_active
                or entity.attack_cooldown
                > entity.get_preloaded_attack_time_seconds() + 1e-9
                or entity.stun_timer > 1e-9
                or entity.slow_timer > 1e-9
                or entity.haste_timer > 1e-9
                or entity.freeze_expiry_time > self.time + 1e-9
                or entity._slow_effects
                or entity._haste_effects
                or entity._periodic_damage_effects
                or entity.forced_movement_active
                or entity._knockback_target is not None
                or entity._death_spawn_travel_ticks_remaining > 0
                or entity.activation_delay_remaining > 1e-9
                or entity.activation_first_hit_delay_remaining > 1e-9
            ):
                return False
        return True

    def _update_battle_phases(self) -> None:
        """Update standard 1v1 timer and elixir phases for the current time."""
        if self.time >= self.double_elixir_start_time:
            self.double_elixir = True
        if self.time >= self.overtime_start_time:
            self.overtime = True
        if self.time >= self.triple_elixir_start_time:
            self.triple_elixir = True

    def fast_forward_idle_ticks(self, ticks: int) -> int:
        """Advance multiple idle ticks when only static towers remain."""
        if ticks <= 0 or not self.can_fast_forward_idle():
            return 0
        advanced = 0
        for _ in range(ticks):
            if self.game_over:
                break
            dt = self.dt
            self.time += dt
            self.tick += 1
            self._update_battle_phases()

            base_regen = 2.8
            if self.triple_elixir:
                base_regen = 0.93
            elif self.double_elixir:
                base_regen = 1.4
            for player in self.players:
                player.regenerate_elixir(dt, base_regen)
                player.tick_card_refill(
                    self._next_card_refill_cooldown_ms(),
                    round(dt * 1000.0),
                )
            # In an otherwise inert frame, active Crown Towers still advance
            # this visualization-only clock in their combat component.
            for entity in self.entities.values():
                if (
                    entity.is_alive
                    and self._is_static_tower_entity(entity)
                    and getattr(entity, "_tower_active", True)
                ):
                    entity.last_attack_time += dt
            advanced += 1
            self._check_win_conditions()
            if self.game_over:
                break
        return advanced

    def _queue_spell_cast(self, spell_name: str, player_id: int, position: Position) -> None:
        """Queue a played spell until the server accepts the action one second later."""
        self._pending_spell_casts.append(
            PendingSpellCast(
                execute_at=self.time + SERVER_ACTION_DELAY_SECONDS,
                sequence=self._next_spell_cast_sequence,
                spell_name=spell_name,
                player_id=player_id,
                position=Position(position.x, position.y),
            )
        )
        self._next_spell_cast_sequence += 1

    def _resolve_pending_spell_casts(self) -> None:
        if not self._pending_spell_casts:
            return

        due = [
            cast
            for cast in self._pending_spell_casts
            if cast.execute_at <= self.time + 1e-9
        ]
        if not due:
            return

        self._pending_spell_casts = [
            cast
            for cast in self._pending_spell_casts
            if cast.execute_at > self.time + 1e-9
        ]
        for cast in sorted(due, key=lambda item: (item.execute_at, item.sequence)):
            spell = SPELL_REGISTRY.get(cast.spell_name)
            if spell is not None:
                spell.cast(self, cast.player_id, cast.position)

    def queue_projectile_impact(
        self,
        projectile: Projectile,
        targets: List[Entity],
    ) -> None:
        """Queue an arrived projectile against its current overlap snapshot."""
        self._pending_projectile_impacts.append(
            PendingProjectileImpact(projectile, tuple(targets))
        )

    def _resolve_pending_projectile_impacts(self) -> None:
        pending = self._pending_projectile_impacts
        self._pending_projectile_impacts = []
        for impact in pending:
            impact.projectile._resolve_impact(self, impact.targets)

    def _next_card_refill_cooldown_ms(self) -> int:
        """Return the Default timeline's current empty-slot refill delay."""
        for segment_end_seconds, cooldown_ms in DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS:
            if self.time < segment_end_seconds - 1e-9:
                return cooldown_ms
        return DEFAULT_BATTLE_TIMELINE_NEXT_CARD_REFILL_COOLDOWN_MS[-1][1]
    
    def deploy_card(self, player_id: int, card_name: str, position: Position) -> bool:
        """Deploy a card at the given position"""
        player = self.players[player_id]
        resolved_name = resolve_card_name(card_name, self.card_loader.load_card_definitions())
        # Fetch card stats from the factory-backed loader
        card_stats = self.card_loader.get_card(resolved_name)

        if not card_stats or not player.can_play_card(card_name, card_stats):
            return False

        is_spell = resolved_name in SPELL_REGISTRY
        spell_obj = SPELL_REGISTRY.get(resolved_name) if is_spell else None
        # Troops whose card data permits enemy-side placement still obey the
        # arena's terrain and live tower footprints. Miner is currently the
        # enabled card using this capability, but the rule is data-driven.
        if (
            not is_spell
            and bool(getattr(card_stats, "can_deploy_on_enemy_side", False))
        ):
            tile_pos = (int(position.x), int(position.y))
            if not self.arena.is_valid_position(position):
                return False
            if tile_pos in self.arena.BLOCKED_TILES:
                return False
            if self.arena.is_tower_tile(position, self):
                return False
        else:
            if not self.arena.can_deploy_at(position, player_id, self, is_spell, spell_obj):
                return False

        # Wide formations serialize the number of edge columns where their
        # placement anchor is forbidden. Apply this to the tile index rather
        # than card names so Royal Hogs, Recruits, and future wide formations
        # share the native placement rule.
        deploy_w_margin = int(
            getattr(card_stats, "deploy_w_tile_margin", 0) or 0
        )
        if deploy_w_margin > 0:
            tile_x = int(position.x)
            if not (
                deploy_w_margin
                <= tile_x
                < self.arena.width - deploy_w_margin
            ):
                return False

        if not is_spell:
            # Buildings are solid obstacles; do not allow overlapping deployment.
            card_type = str(getattr(card_stats, "card_type", "") or "").lower()
            is_building_card = card_type == "building"
            if is_building_card:
                if self.is_building_placement_occupied(
                    position, card_stats
                ) or self.is_deployment_payload_occupied(
                    position,
                    card_stats=card_stats,
                ):
                    return False
            else:
                probe_radius = getattr(card_stats, "collision_radius", 0.5) or 0.5
                if self.is_position_occupied_by_building(
                    position, probe_radius
                ) or self.is_deployment_payload_occupied(
                    position,
                    mover_radius=probe_radius,
                ):
                    return False

        # Play the card
        if not player.play_card(card_name, card_stats):
            return False

        # Check if it's a spell
        if resolved_name in SPELL_REGISTRY:
            self._queue_spell_cast(resolved_name, player_id, position)
        else:
            entity_ids_before = set(self.entities)
            # Spawn troop or building based on card type (robust to missing/None fields)
            card_type = getattr(card_stats, "card_type", None)
            card_type_str = str(card_type).lower() if card_type is not None else ""
            if card_type_str == "building":
                self._spawn_entity(Building, position, player_id, card_stats)
            else:
                deploy_position = self._apply_symmetric_deploy_snap(
                    position,
                    player_id,
                    card_stats,
                )
                self._spawn_troop(deploy_position, player_id, card_stats)
            for entity_id in self.entities.keys() - entity_ids_before:
                entity = self.entities[entity_id]
                if isinstance(entity, (Troop, Building)) and entity.deploy_delay_remaining > 1e-9:
                    entity.placement_pending = True
        
        return True

    def _apply_symmetric_deploy_snap(
        self,
        position: Position,
        player_id: int,
        card_stats: CardStatsCompat,
    ) -> Position:
        """Apply LogicSummoner's post-search one-unit anchor adjustment."""
        if not LOGIC_SYMMETRICAL_DEPLOY_SNAP:
            return position

        card_type = str(getattr(card_stats, "card_type", "") or "").lower()
        character_data = (
            getattr(card_stats, "summon_character_data", None) or {}
        )
        if (
            card_type == "building"
            or is_air_unit_card(card_stats)
            or float(getattr(card_stats, "speed", 0) or 0) <= 0.0
            or int(character_data.get("dashCooldown", 0) or 0) > 0
        ):
            return position

        x_units = tiles_to_logic_units(position.x)
        y_units = tiles_to_logic_units(position.y)
        if x_units < tiles_to_logic_units(self.arena.width) // 2:
            x_units -= 1
        # Native findPositionForSpell receives player_id == 0 as this side
        # flag and decrements y only when it is false.
        if player_id != 0:
            y_units -= 1
        return Position(
            logic_units_to_tiles(x_units),
            logic_units_to_tiles(y_units),
        )

    @staticmethod
    def _champion_ability_pair(
        entity: Entity,
    ) -> Optional[Tuple[Troop, Any]]:
        if not isinstance(entity, Troop):
            return None
        for mechanic in entity.mechanics:
            can_activate = getattr(mechanic, "can_activate_ability", None)
            activate = getattr(mechanic, "activate_ability", None)
            if callable(can_activate) and callable(activate):
                return entity, mechanic
        return None

    @staticmethod
    def _champion_ability_key(entity: Entity) -> str:
        """Return the identity shared by duplicate copies of one Champion."""
        name = str(getattr(entity.card_stats, "name", "") or "")
        return str(resolve_card_name(name)).casefold()

    def _refresh_champion_ability_owner(
        self,
        player_id: int,
        ability_key: str,
    ) -> Optional[Tuple[Troop, Any]]:
        """Select the newest live copy and apply ownership-transfer rules."""
        candidates: List[Tuple[Troop, Any]] = []
        for entity in self.entities.values():
            if (
                entity.player_id != player_id
                or not entity.is_alive
                or self._champion_ability_key(entity) != ability_key
            ):
                continue
            pair = self._champion_ability_pair(entity)
            if pair is not None:
                candidates.append(pair)

        owner_key = (player_id, ability_key)
        if not candidates:
            self._champion_ability_owner_ids.pop(owner_key, None)
            return None

        entity, mechanic = max(candidates, key=lambda pair: pair[0].id)
        previous_owner_id = self._champion_ability_owner_ids.get(owner_key)
        if previous_owner_id != entity.id:
            ability = getattr(mechanic, "ability", None)
            reset_cooldown = getattr(ability, "reset_cooldown", None)
            if callable(reset_cooldown):
                reset_cooldown()
            self._champion_ability_owner_ids[owner_key] = entity.id
        return entity, mechanic

    def is_champion_ability_owner(self, entity: Entity) -> bool:
        """Return whether this is the newest live copy of its Champion."""
        pair = self._champion_ability_pair(entity)
        if pair is None or not entity.is_alive:
            return False
        owner = self._refresh_champion_ability_owner(
            entity.player_id,
            self._champion_ability_key(entity),
        )
        return owner is not None and owner[0].id == entity.id

    def _champion_ability_mechanic(
        self,
        player_id: int,
    ) -> Optional[Tuple[Troop, Any]]:
        # Enabled decks contain one Champion type. Selecting the newest
        # ability owner also preserves the existing single-button RL action
        # contract while duplicate copies coexist.
        candidates: List[Tuple[Troop, Any]] = []
        seen_keys: set[str] = set()
        for entity in sorted(self.entities.values(), key=lambda item: item.id, reverse=True):
            if entity.player_id != player_id or not entity.is_alive:
                continue
            if self._champion_ability_pair(entity) is None:
                continue
            ability_key = self._champion_ability_key(entity)
            if ability_key in seen_keys:
                continue
            seen_keys.add(ability_key)
            owner = self._refresh_champion_ability_owner(player_id, ability_key)
            if owner is not None:
                candidates.append(owner)
        if not candidates:
            return None
        return max(candidates, key=lambda pair: pair[0].id)

    def can_activate_champion_ability(self, player_id: int) -> bool:
        found = self._champion_ability_mechanic(player_id)
        if found is None:
            return False
        entity, mechanic = found
        return bool(mechanic.can_activate_ability(entity))

    def activate_champion_ability(self, player_id: int) -> bool:
        found = self._champion_ability_mechanic(player_id)
        if found is None:
            return False
        entity, mechanic = found
        return bool(mechanic.activate_ability(entity))
    
    def _spawn_troop(self, position: Position, player_id: int, card_stats: CardStatsCompat) -> None:
        """Spawn a troop entity (handles both single troops and swarms)"""
        # Guard: if this card is actually a building, route to building spawner
        ctype = getattr(card_stats, "card_type", None)
        ctype_str = str(ctype).lower() if ctype is not None else ""
        if ctype_str == "building":
            self._spawn_entity(Building, position, player_id, card_stats)
            return
        
        # Check if this is a swarm card (spawns multiple units)
        summon_count = getattr(card_stats, 'summon_count', None) or 1
        serialized_summon_radius = getattr(card_stats, 'summon_radius', None)
        # Native getSpawnOffset receives SummonRadius when serialized and
        # otherwise the primary character's collision radius. It performs
        # the polygon/ring conversion itself.
        summon_radius = (
            float(serialized_summon_radius)
            if serialized_summon_radius is not None
            else float(getattr(card_stats, "collision_radius", 0.5) or 0.5)
        )
        
        # Check for mixed swarms (like Goblin Gang)
        second_count = getattr(card_stats, 'summon_character_second_count', None) or 0
        second_data = getattr(card_stats, 'summon_character_second_data', None)
        
        if summon_count > 1 or second_count > 0:
            # Spawn swarm units in a circle around the target position
            # summon_radius is already converted to tiles in data loading
            self._spawn_swarm_troops(position, player_id, card_stats, summon_count, summon_radius, second_count, second_data)
        else:
            # Spawn single unit at exact position
            self._spawn_single_troop(position, player_id, card_stats)
    
    def _spawn_single_troop(self, position: Position, player_id: int, card_stats: CardStatsCompat) -> None:
        """Spawn a single troop entity through the common spawn primitive."""
        # The deployment anchor has already been validated by ``deploy_card``.
        # Native deployment resolves that one anchor and then creates every
        # character at its exact formation offset; it does not independently
        # search for a walkable point for each character.
        self._spawn_unit_at_position(
            position,
            player_id,
            card_stats,
            snap_to_valid=False,
        )
    
    def _spawn_swarm_troops(self, center_pos: Position, player_id: int, card_stats: CardStatsCompat, count: int, radius: float, second_count: int = 0, second_data: dict = None) -> None:
        """Spawn multiple troop entities in a circle around center position"""
        # Check for data-selected deployment patterns.
        is_royal_recruits = card_stats.name in ['RoyalRecruits', 'RoyalRecruits_Chess']
        summon_width = float(getattr(card_stats, "summon_width", 0.0) or 0.0)
        
        # Check if this is a mixed swarm with front/back positioning (like Goblin Gang)
        has_front_back = (count > 0 and second_count > 0 and 
                         getattr(card_stats, 'summon_character_data', None) and
                         getattr(card_stats, 'summon_character_second_data', None))
        
        if is_royal_recruits:
            # Royal Recruits spawn in a horizontal line across battlefield
            self._spawn_royal_recruits_line(center_pos, player_id, card_stats, count)
        elif summon_width > 0.0:
            self._spawn_horizontal_formation(
                center_pos,
                player_id,
                card_stats,
                count,
                radius,
            )
        elif has_front_back:
            # Spawn in front/back formation for mixed swarms
            self._spawn_front_back_formation(center_pos, player_id, card_stats, count, second_count, second_data, radius)
        else:
            # Regular circular formation
            # Spawn primary units 
            for i in range(count):
                self._spawn_unit_at_angle(
                    center_pos,
                    player_id,
                    card_stats,
                    i,
                    count,
                    radius,
                    secondary_count=second_count,
                )
            
            # Spawn secondary units if available
            if second_count > 0 and second_data:
                unit_name = second_data.get("name", card_stats.name + "_Secondary")
                second_card_stats = self._create_card_stats_from_data(second_data, unit_name)

                for i in range(second_count):
                    self._spawn_unit_at_angle(
                        center_pos,
                        player_id,
                        second_card_stats,
                        count + i,
                        count,
                        radius,
                        secondary_count=second_count,
                        angle_shift_degrees=float(
                            getattr(card_stats, "spawn_angle_shift", 0) or 0
                        ),
                    )
    
    def _spawn_unit_at_angle(
        self,
        center_pos: Position,
        player_id: int,
        card_stats: CardStatsCompat,
        index: int,
        primary_count: int,
        radius: float,
        *,
        secondary_count: int = 0,
        angle_shift_degrees: float | None = None,
    ) -> None:
        """Spawn a single unit at a specific angle in the swarm formation"""
        from .formations import formation_offset

        # Use mirrored, deterministic formation geometry. Deployment layouts
        # are game state, not RNG: identical card placements must not jitter.
        offset_x, offset_y = formation_offset(
            index,
            primary_count,
            radius,
            player_id,
            angle_shift_degrees=float(
                getattr(card_stats, "spawn_angle_shift", 0) or 0
                if angle_shift_degrees is None
                else angle_shift_degrees
            ),
            secondary_count=secondary_count,
            lane_id=self.arena.native_path_id_at(center_pos),
        )
        deploy_delay_offset = (
            index * (getattr(card_stats, "summon_deploy_delay", 0) or 0) / 1000.0
        )
        self._spawn_unit_at_position(
            Position(center_pos.x + offset_x, center_pos.y + offset_y),
            player_id,
            card_stats,
            deploy_delay_offset=deploy_delay_offset,
            snap_to_valid=False,
        )
    
    def _spawn_front_back_formation(self, center_pos: Position, player_id: int, card_stats: CardStatsCompat, front_count: int, back_count: int, back_data: dict, radius: float) -> None:
        """Spawn a mixed swarm ring with its primary block facing forward."""
        from .formations import mixed_ring_offset
        
        # Create card stats for both unit types
        # Primary units (front) - use actual name from summonCharacterData
        primary_data = getattr(card_stats, 'summon_character_data', {})
        primary_name = primary_data.get("name", card_stats.name)
        front_card_stats = self._create_card_stats_from_data(primary_data, primary_name)
        
        # Secondary units (back) - use actual name from summonCharacterSecondData  
        back_name = back_data.get("name", card_stats.name + "_Secondary")
        back_card_stats = self._create_card_stats_from_data(back_data, back_name)
        lane_id = self.arena.native_path_id_at(center_pos)
        
        # Spawn primary units on the forward arc.
        for i in range(front_count):
            offset_x, offset_y = mixed_ring_offset(
                i,
                front_count,
                back_count,
                radius,
                player_id,
                float(getattr(card_stats, "spawn_angle_shift", 0) or 0),
                lane_id=lane_id,
            )
            front_pos = Position(center_pos.x + offset_x, center_pos.y + offset_y)
            
            stagger = i * (getattr(card_stats, "summon_deploy_delay", 0) or 0) / 1000.0
            self._spawn_unit_at_position(
                front_pos,
                player_id,
                front_card_stats,
                deploy_delay_offset=stagger,
                snap_to_valid=False,
            )
        
        # Spawn secondary units on the remaining rear arc.
        for i in range(back_count):
            stagger_index = front_count + i
            offset_x, offset_y = mixed_ring_offset(
                stagger_index,
                front_count,
                back_count,
                radius,
                player_id,
                float(getattr(card_stats, "spawn_angle_shift", 0) or 0),
                lane_id=lane_id,
            )
            back_pos = Position(center_pos.x + offset_x, center_pos.y + offset_y)

            stagger = stagger_index * (
                getattr(card_stats, "summon_deploy_delay", 0) or 0
            ) / 1000.0
            self._spawn_unit_at_position(
                back_pos,
                player_id,
                back_card_stats,
                deploy_delay_offset=stagger,
                snap_to_valid=False,
            )

    def _spawn_horizontal_formation(
        self,
        center_pos: Position,
        player_id: int,
        card_stats: CardStatsCompat,
        count: int,
        radius: float,
    ) -> None:
        """Spawn a data-selected native wide formation."""
        from .formations import horizontal_line_offset

        lane_id = self.arena.native_path_id_at(center_pos)
        for index in range(count):
            offset_x, offset_y = horizontal_line_offset(
                index,
                count,
                getattr(card_stats, "summon_width", 0.0) or 0.0,
                radius,
                player_id,
                lane_id=lane_id,
            )
            position = Position(center_pos.x + offset_x, center_pos.y + offset_y)
            stagger = index * (
                getattr(card_stats, "summon_deploy_delay", 0) or 0
            ) / 1000.0
            self._spawn_unit_at_position(
                position,
                player_id,
                card_stats,
                deploy_delay_offset=stagger,
                snap_to_valid=False,
            )
    
    def _spawn_royal_recruits_line(self, center_pos: Position, player_id: int, card_stats: CardStatsCompat, count: int) -> None:
        """Spawn Royal Recruits in a horizontal line across the battlefield, avoiding towers"""
        # Royal Recruits: 6 units spaced 2.5 tiles apart, center at deploy position
        spacing = 2.5  # tiles between each recruit
        
        # Get tower-blocked X ranges for this Y coordinate
        blocked_ranges = self.arena.get_tower_blocked_x_ranges(center_pos.y, self)
        
        # Calculate initial line positions
        total_width = (count - 1) * spacing
        leftmost_x = center_pos.x - (total_width / 2)
        
        # Generate all recruit X positions
        recruit_positions = []
        for i in range(count):
            recruit_x = leftmost_x + (i * spacing)
            recruit_positions.append(recruit_x)
        
        # Check if any positions would overlap with towers
        needs_adjustment = False
        for recruit_x in recruit_positions:
            for x_min, x_max in blocked_ranges:
                if x_min <= recruit_x <= x_max:
                    needs_adjustment = True
                    break
            if needs_adjustment:
                break
        
        # If line overlaps with towers, find alternative positioning
        if needs_adjustment:
            recruit_positions = self._find_safe_recruit_positions(center_pos, count, spacing, blocked_ranges)
        
        # Ensure all positions are within arena bounds
        recruit_positions = [max(0.5, min(17.5, x)) for x in recruit_positions]
        
        # Spawn each recruit
        for recruit_x in recruit_positions:
            recruit_pos = Position(recruit_x, center_pos.y)
            recruit_pos = self._snap_to_valid_position(recruit_pos, player_id)
            self._spawn_unit_at_position(recruit_pos, player_id, card_stats)
    
    def _find_safe_recruit_positions(self, center_pos: Position, count: int, spacing: float, blocked_ranges: List[Tuple[float, float]]) -> List[float]:
        """Find safe X positions for Royal Recruits that avoid tower collisions"""
        
        # Create list of all blocked X coordinates
        blocked_x_coords = set()
        for x_min, x_max in blocked_ranges:
            # Add all positions in blocked range with 0.5 precision
            x = x_min
            while x <= x_max:
                blocked_x_coords.add(round(x * 2) / 2)  # Round to nearest 0.5
                x += 0.5
        
        # Find all safe X positions across the arena
        safe_positions = []
        for x_half in range(1, 36):  # 0.5 to 17.5 in 0.5 increments
            x = x_half / 2.0
            if x not in blocked_x_coords and 0.5 <= x <= 17.5:
                safe_positions.append(x)
        
        # If we have enough safe positions, try to maintain spacing
        if len(safe_positions) >= count:
            # Try to find positions with good spacing starting from center
            selected_positions = []
            
            # Find safe position closest to center
            center_candidates = [pos for pos in safe_positions if abs(pos - center_pos.x) <= 1.0]
            if not center_candidates:
                center_candidates = safe_positions
            
            center_safe = min(center_candidates, key=lambda x: abs(x - center_pos.x))
            selected_positions.append(center_safe)
            
            # For remaining positions, try to maintain spacing while staying safe
            while len(selected_positions) < count:
                best_candidate = None
                best_score = float('inf')
                
                for candidate in safe_positions:
                    if candidate in selected_positions:
                        continue
                    
                    # Score based on distance from ideal spacing positions
                    min_spacing_score = float('inf')
                    for existing_pos in selected_positions:
                        spacing_distance = abs(abs(candidate - existing_pos) - spacing)
                        min_spacing_score = min(min_spacing_score, spacing_distance)
                    
                    # Prefer positions that maintain good spacing
                    if min_spacing_score < best_score:
                        best_score = min_spacing_score
                        best_candidate = candidate
                
                if best_candidate is not None:
                    selected_positions.append(best_candidate)
                else:
                    # If no good candidate, just pick the first available
                    for pos in safe_positions:
                        if pos not in selected_positions:
                            selected_positions.append(pos)
                            break
            
            positions = selected_positions
        else:
            # Not enough safe positions, use what we have
            positions = safe_positions[:count]
        
        # Ensure we have exactly the right count
        while len(positions) < count:
            # Add fallback positions at arena edges
            for x in [0.5, 1.0, 17.0, 17.5, 16.5, 16.0]:
                if x not in positions and x not in blocked_x_coords:
                    positions.append(x)
                    if len(positions) >= count:
                        break
        
        # Sort and return exact count
        positions.sort()
        return positions[:count]
    
    def _spawn_unit_at_position(
        self,
        position: Position,
        player_id: int,
        card_stats: CardStatsCompat,
        *,
        deploy_delay_override: float | None = None,
        deploy_delay_offset: float = 0.0,
        snap_to_valid: bool = True,
        death_spawn: bool = False,
        death_spawn_travel_origin: Position | None = None,
    ) -> None:
        """Spawn a single unit at a specific position"""
        # Get unit properties
        speed = card_stats.speed or 60.0
        
        is_air_unit = is_air_unit_card(card_stats)
        mover_radius = getattr(card_stats, "collision_radius", 0.5) or 0.5
        # LogicBattle::spawnObject clamps every character center to the
        # innermost half-pathing-cell boundary (250 logic units), independently
        # of collision radius. Terrain validation is a separate caller choice.
        def canonical_grid_coordinate(value: float) -> float:
            half_tile = round(value * 2.0) / 2.0
            return half_tile if abs(value - half_tile) <= 1e-9 else value

        spawn_position = Position(
            canonical_grid_coordinate(
                max(0.25, min(self.arena.width - 0.25, position.x))
            ),
            canonical_grid_coordinate(
                max(0.25, min(self.arena.height - 0.25, position.y))
            ),
        )
        if not is_air_unit and snap_to_valid:
            spawn_position = self._snap_to_valid_position(spawn_position, player_id, mover_radius=mover_radius)
        # Characters are born on the same integer logic grid used by every
        # subsequent movement component. This matters for diagonal formations
        # before their first update (targeting and spawn-area payloads can
        # already observe them during deployment).
        spawn_position = Position(
            logic_units_to_tiles(tiles_to_logic_units(spawn_position.x)),
            logic_units_to_tiles(tiles_to_logic_units(spawn_position.y)),
        )
        
        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints
        if scaled_hp is None:
            scaled_hp = card_stats.hitpoints
        if scaled_hp is None:
            scaled_hp = 100
        scaled_damage = card_stats.scaled_damage
        if scaled_damage is None:
            scaled_damage = card_stats.damage
        if scaled_damage is None:
            scaled_damage = 0
        
        troop = Troop(
            id=self.next_entity_id,
            position=spawn_position,
            player_id=player_id,
            card_stats=card_stats,
            hitpoints=scaled_hp,
            max_hitpoints=scaled_hp,
            damage=scaled_damage,
            range=card_stats.range if card_stats.range is not None else 0.5,
            sight_range=card_stats.sight_range if card_stats.sight_range is not None else 5.5,
            speed=speed,
            is_air_unit=is_air_unit
        )
        troop._native_lane_id = self.arena.native_path_id_at(spawn_position)

        native_deploy_delay = max(
            0.0,
            (getattr(card_stats, "deploy_time", 0) or 0) / 1000.0,
        )
        troop.deploy_delay_remaining = (
            native_deploy_delay
            if deploy_delay_override is None
            else max(0.0, deploy_delay_override)
        )
        troop.deploy_delay_remaining += max(0.0, deploy_delay_offset)
        troop.placement_delay_total = troop.deploy_delay_remaining
        troop.placement_pending = troop.deploy_delay_remaining > 1e-9
        troop.attack_cooldown = max(
            troop.attack_cooldown,
            (getattr(card_stats, "first_hit_time", 0) or 0) / 1000.0,
        )
        troop.battle_state = self
        if death_spawn:
            troop._activate_death_spawn_target_immunity()

        self._attach_card_mechanics(troop, card_stats)

        self.entities[self.next_entity_id] = troop
        self.next_entity_id += 1
        if death_spawn_travel_origin is not None:
            # Native retains the ring coordinate as movement state and resets
            # the live object to its parent's death origin before spawn hooks
            # or manager insertion can expose the child to gameplay.
            troop.begin_death_spawn_travel(death_spawn_travel_origin)
        troop.on_spawn()

    def _native_child_position_without_radius(
        self,
        parent: Entity,
        child_stats: CardStatsCompat,
        *,
        direct: bool = False,
    ) -> Position:
        """Resolve the four native terrain candidates for a child spawn."""
        parent_radius = float(parent.get_collision_radius())
        child_radius = float(
            getattr(child_stats, "collision_radius", 0.5) or 0.5
        )
        distance_units = (
            0
            if direct
            else tiles_to_logic_units(parent_radius + child_radius)
        )
        origin_x = tiles_to_logic_units(parent.position.x)
        origin_y = tiles_to_logic_units(parent.position.y)
        arena_midpoint = self.arena.width / 2.0

        # Native starts along local +y and tries 90-degree rotations. It
        # mirrors local x on the arena's right half and local y for player 1.
        for offset_x, offset_y in (
            (0, distance_units),
            (-distance_units, 0),
            (0, -distance_units),
            (distance_units, 0),
        ):
            if parent.position.x > arena_midpoint:
                offset_x = -offset_x
            if parent.player_id == 1:
                offset_y = -offset_y
            candidate = Position(
                logic_units_to_tiles(origin_x + offset_x),
                logic_units_to_tiles(origin_y + offset_y),
            )
            if self._is_native_child_spawn_point(candidate, child_stats):
                return candidate

        # This is one logic unit in the native code. Our coordinate grid uses
        # 1000 logic units per tile.
        return Position(
            logic_units_to_tiles(origin_x + 1),
            logic_units_to_tiles(origin_y),
        )

    def _is_native_child_spawn_point(
        self,
        position: Position,
        child_stats: CardStatsCompat,
    ) -> bool:
        """Match LogicTileMap::isValidSpawnPoint's footprint tile scan."""
        x_units = tiles_to_logic_units(position.x)
        y_units = tiles_to_logic_units(position.y)
        radius_units = tiles_to_logic_units(
            float(getattr(child_stats, "collision_radius", 0.5) or 0.5)
        )
        width_units = tiles_to_logic_units(self.arena.width)
        height_units = tiles_to_logic_units(self.arena.height)
        if (
            x_units - radius_units < 0
            or y_units - radius_units < 0
            or x_units + radius_units >= width_units
            or y_units + radius_units >= height_units
        ):
            return False

        # Native pathing tiles are half a displayed arena tile (500 logic
        # units). The validator scans the child's full axis-aligned collision
        # footprint, rejecting it if any touched tile is blocked.
        min_tile_x = (x_units - radius_units) // 500
        max_tile_x = (x_units + radius_units - 1) // 500
        min_tile_y = (y_units - radius_units) // 500
        max_tile_y = (y_units + radius_units - 1) // 500
        for tile_x in range(min_tile_x, max_tile_x + 1):
            for tile_y in range(min_tile_y, max_tile_y + 1):
                if native_spawn_tile_blocked(tile_x, tile_y):
                    return False
        return True
    
    def _snap_to_valid_position(self, position: Position, player_id: int, mover_radius: float = 0.5) -> Position:
        """Snap position to nearest valid playable area"""
        # Check if position is already valid (walkable and not on a tower)
        if (
            self.is_entity_position_in_bounds(position)
            and self.arena.is_walkable(position)
            and not self.arena.is_tower_tile(position, self)
            and not self.is_position_occupied_by_building(position, mover_radius=mover_radius)
        ):
            return position

        # Formation and death-spawn offsets can land exactly in non-bridge
        # water. At the arena center the two banks are otherwise an ambiguous
        # nearest-position tie; resolve it toward the owner's side, matching
        # the 180-degree player transform instead of always choosing the upper
        # world bank because of half-open tile bounds.
        in_river = self.arena.RIVER_Y1 <= position.y <= self.arena.RIVER_Y2 + 1.0
        on_bridge = 2.0 <= position.x <= 5.0 or 13.0 <= position.x <= 16.0
        if in_river and not on_bridge:
            bank_y = (
                self.arena.RIVER_Y1 - 0.5
                if player_id == 0
                else self.arena.RIVER_Y2 + 1.5
            )
            bank_position = Position(position.x, bank_y)
            if (
                self.is_entity_position_in_bounds(bank_position)
                and self.arena.is_walkable(bank_position)
                and not self.arena.is_tower_tile(bank_position, self)
                and not self.is_position_occupied_by_building(
                    bank_position,
                    mover_radius=mover_radius,
                )
            ):
                return bank_position
        
        # Try to find nearest valid position within reasonable distance
        search_radius = 2.0  # tiles
        best_position = position
        min_distance = float('inf')
        
        # Search in owner-relative order.  Equal-distance candidates must rotate
        # with the player perspective; a fixed world-space ordering makes a
        # mirrored overlap choose the same compass direction for both players.
        base_offsets = [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]
        owner_rotation = 1.0 if player_id == 0 else -1.0
        search_offsets = [offset * owner_rotation for offset in base_offsets]
        for x_offset in search_offsets:
            for y_offset in search_offsets:
                test_x = position.x + x_offset
                test_y = position.y + y_offset
                test_pos = Position(test_x, test_y)
                
                # Check bounds first
                if not self.is_entity_position_in_bounds(test_pos):
                    continue
                
                # Check if walkable and not on tower
                if (
                    self.arena.is_walkable(test_pos)
                    and not self.arena.is_tower_tile(test_pos, self)
                    and not self.is_position_occupied_by_building(test_pos, mover_radius=mover_radius)
                ):
                    distance = position.distance_to(test_pos)
                    if distance < min_distance - 1e-9:
                        min_distance = distance
                        best_position = test_pos
        
        # If no valid position found nearby, clamp to arena bounds and find closest walkable
        if min_distance == float('inf'):
            # Clamp to arena bounds
            clamped_x = max(0.5, min(17.5, position.x))
            clamped_y = max(0.5, min(31.5, position.y))
            clamped_pos = Position(clamped_x, clamped_y)
            
            # If clamped position is walkable and not on tower, use it
            if (
                self.is_entity_position_in_bounds(clamped_pos)
                and self.arena.is_walkable(clamped_pos)
                and not self.arena.is_tower_tile(clamped_pos, self)
                and not self.is_position_occupied_by_building(clamped_pos, mover_radius=mover_radius)
            ):
                best_position = clamped_pos
            else:
                # Fallback: move towards arena center until we find walkable area
                center_x, center_y = 9.0, 16.0
                dx = center_x - clamped_x
                dy = center_y - clamped_y
                
                for step in [0.5, 1.0, 1.5, 2.0]:
                    fallback_x = clamped_x + dx * step * 0.1
                    fallback_y = clamped_y + dy * step * 0.1
                    fallback_pos = Position(fallback_x, fallback_y)
                    
                    if (
                        self.is_entity_position_in_bounds(fallback_pos)
                        and self.arena.is_walkable(fallback_pos)
                        and not self.arena.is_tower_tile(fallback_pos, self)
                        and not self.is_position_occupied_by_building(fallback_pos, mover_radius=mover_radius)
                    ):
                        best_position = fallback_pos
                        break
        
        return best_position
    
    def _create_card_stats_from_data(self, unit_data: dict, name: str) -> CardStatsCompat:
        """Create CardStatsCompat from raw unit data (for secondary units in mixed swarms)."""
        if not unit_data:
            raise ValueError(f"Missing serialized character data for {name}")
        rarity = unit_data.get("rarity", "Common")
        return troop_from_character_data(name, unit_data, elixir=0, rarity=rarity)

    def _attach_card_mechanics(self, entity: Entity, card_stats: CardStatsCompat) -> None:
        """Attach canonical or nested data mechanics exactly once."""
        defn_name = getattr(card_stats, "name", None)
        loader_def = self.card_loader.get_card_definition(defn_name) if defn_name else None
        own_def = getattr(card_stats, "card_definition", None)
        card_def = loader_def if loader_def and loader_def.mechanics else own_def
        mechanics = getattr(card_def, "mechanics", ()) if card_def else ()
        entity.mechanics = [copy.deepcopy(mechanic) for mechanic in mechanics]
        for mechanic in entity.mechanics:
            mechanic.on_attach(entity)
        if entity.mechanics and self.debug_logs:
            print(f"[Attach] {defn_name}: {len(entity.mechanics)} mechanic(s)")
    
    def _spawn_entity(self, entity_class, position: Position, player_id: int, card_stats: CardStatsCompat) -> Entity:
        """Spawn any type of entity"""
        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints
        if scaled_hp is None:
            scaled_hp = 100
        scaled_damage = card_stats.scaled_damage
        if scaled_damage is None:
            scaled_damage = 0

        entity = entity_class(
            id=self.next_entity_id,
            position=position,
            player_id=player_id,
            card_stats=card_stats,
            hitpoints=scaled_hp,
            max_hitpoints=scaled_hp,
            damage=scaled_damage,
            range=card_stats.range if card_stats.range is not None else 0.5,
            sight_range=card_stats.sight_range if card_stats.sight_range is not None else 5.5,
        )
        entity._native_lane_id = self.arena.native_path_id_at(position)

        is_crown_tower = getattr(card_stats, "name", "") in {"Tower", "KingTower"}
        entity.deploy_delay_remaining = (
            0.0
            if is_crown_tower
            else max(0.0, (getattr(card_stats, "deploy_time", 0) or 0) / 1000.0)
        )
        entity.placement_delay_total = entity.deploy_delay_remaining
        entity.placement_pending = entity.deploy_delay_remaining > 1e-9
        entity.attack_cooldown = max(
            entity.attack_cooldown,
            (getattr(card_stats, "first_hit_time", 0) or 0) / 1000.0,
        )

        # Add battle_state reference for mechanics
        entity.battle_state = self

        self._attach_card_mechanics(entity, card_stats)

        self.entities[self.next_entity_id] = entity
        self.next_entity_id += 1

        if isinstance(entity, Building) and getattr(card_stats, "name", "") == "KingTower":
            from .balance import tournament_tower_stat

            activation_duration_ms = tournament_tower_stat(
                "KingTower",
                "activation_duration",
            )
            activation_first_hit_delay_ms = tournament_tower_stat(
                "KingTower",
                "activation_first_hit_delay",
            )
            if (
                activation_duration_ms is None
                or activation_first_hit_delay_ms is None
            ):
                raise ValueError("Missing KingTower activation timing data")
            entity._tower_active = False
            entity._is_king_tower = True
            entity.requires_activation = True
            entity.activation_delay_seconds = activation_duration_ms / 1000.0
            entity.activation_first_hit_delay_seconds = (
                activation_first_hit_delay_ms / 1000.0
            )
        elif isinstance(entity, Building):
            entity._tower_active = True
            entity._is_king_tower = False

        # Call on_spawn for all mechanics
        entity.on_spawn()
        pair = self._champion_ability_pair(entity)
        if pair is not None:
            self._refresh_champion_ability_owner(
                entity.player_id,
                self._champion_ability_key(entity),
            )
        return entity
    
    def _cleanup_dead_entities(self) -> None:
        """Remove dead entities from the game and handle death spawns"""
        dead_ids = [eid for eid, entity in self.entities.items() if not entity.is_alive]
        
        # Handle death spawns before removing entities (skip if handled by mechanics)
        for eid in dead_ids:
            entity = self.entities[eid]
            if isinstance(entity, Troop) and getattr(entity.card_stats, 'death_spawn_character', None):
                has_mechanic_spawn = any(isinstance(m, DeathSpawn) for m in getattr(entity, 'mechanics', []))
                spawn_data = getattr(
                    entity.card_stats,
                    "death_spawn_character_data",
                    None,
                ) or {}
                effect_only_container = bool(
                    not spawn_data.get("hitpoints")
                    and spawn_data.get("deathAreaEffectData")
                    and spawn_data.get("deathDamage") is None
                )
                if not has_mechanic_spawn and not effect_only_container:
                    self._spawn_death_units(entity)
        # Update player state for dead towers before removing entities
        for eid in dead_ids:
            entity = self.entities[eid]
            if self._is_static_tower_entity(entity):
                player = self.players[entity.player_id]
                slot = entity._crown_tower_slot
                setattr(player, f"{slot}_tower_hp", 0)
                if slot != "king":
                    self._activate_king_tower(entity.player_id)

        affected_champion_groups = {
            (entity.player_id, self._champion_ability_key(entity))
            for eid, entity in self.entities.items()
            if eid in dead_ids and self._champion_ability_pair(entity) is not None
        }

        # Remove dead entities
        for eid in dead_ids:
            del self.entities[eid]

        # If an older copy remains alive, it regains the crown/ability and its
        # cooldown resets just as it does in the live game on Champion death.
        for player_id, ability_key in affected_champion_groups:
            self._refresh_champion_ability_owner(player_id, ability_key)
    
    def _spawn_death_units(self, troop: Troop) -> None:
        """Spawn death units when a troop dies"""
        death_spawn_name = troop.card_stats.death_spawn_character
        death_spawn_count = troop.card_stats.death_spawn_count or 1
        
        death_spawn_stats = None
        if getattr(troop.card_stats, 'death_spawn_character_data', None):
            death_spawn_stats = troop_from_character_data(
                death_spawn_name,
                troop.card_stats.death_spawn_character_data,
                elixir=0,
                rarity="Common",
            )
        if not death_spawn_stats:
            # Fall back to canonical card loader entry when raw spawn data is unavailable.
            death_spawn_stats = self.card_loader.get_card(death_spawn_name)

        if not death_spawn_stats:
            raise ValueError(
                f"Missing death-spawn character data for {death_spawn_name}"
            )
        
        from .formations import native_radial_spawn_offset

        spawn_radius = max(
            0.0,
            float(getattr(troop.card_stats, "death_spawn_radius", 0.0) or 0.0),
        )
        angle_shift = float(
            getattr(troop.card_stats, "spawn_angle_shift", 0) or 0
        )
        facing_x_units, facing_y_units = troop.native_facing_units()
        deploy_time = max(
            0.0,
            float(getattr(troop.card_stats, "death_spawn_deploy_time", 0) or 0)
            / 1000.0,
        )
        for index in range(death_spawn_count):
            if spawn_radius > 0.0:
                offset_x, offset_y = native_radial_spawn_offset(
                    index,
                    death_spawn_count,
                    spawn_radius,
                    angle_shift,
                    facing_x_units=facing_x_units,
                    facing_y_units=facing_y_units,
                    flip_x=(
                        bool(
                            getattr(
                                troop.card_stats,
                                "death_spawn_pushback",
                                False,
                            )
                        )
                        and self.arena.native_path_id_at(troop.position) == 1
                    ),
                    flip_y=(
                        bool(
                            getattr(
                                troop.card_stats,
                                "death_spawn_pushback",
                                False,
                            )
                        )
                        and troop.player_id == 1
                    ),
                )
                spawn_position = Position(
                    troop.position.x + offset_x,
                    troop.position.y + offset_y,
                )
            else:
                spawn_position = self._native_child_position_without_radius(
                    troop,
                    death_spawn_stats,
                    direct=death_spawn_count == 1,
                )
            spawned_id = self.next_entity_id
            self._spawn_unit_at_position(
                spawn_position,
                troop.player_id,
                death_spawn_stats,
                deploy_delay_override=deploy_time,
                snap_to_valid=False,
                death_spawn=True,
            )
            spawned = self.entities.get(spawned_id)
            if (
                spawned is not None
                and bool(
                    getattr(
                        troop.card_stats,
                        "death_spawn_pushback",
                        False,
                    )
                )
            ):
                spawned._native_target_distance_discount_sq_units = (
                    spawn_target_distance_discount_sq_units(index)
                )
                self.sync_fast_target_static_entity(spawned)
    
    def _check_win_conditions(self) -> None:
        """Check if game should end"""
        # Update player tower HP from entities
        self._update_tower_hp()
        
        # Check both King Towers as one simultaneous resolution. Effects from
        # the same simulation tick can destroy both; iteration order must not
        # turn that legitimate draw into a win for whichever player is checked
        # second.
        king_alive = (self.players[0].is_alive(), self.players[1].is_alive())
        if not all(king_alive):
            self.game_over = True
            if king_alive == (False, False):
                self.winner = None
            else:
                self.winner = 0 if king_alive[0] else 1
            return
        
        player0_crowns = self.get_crown_count(0)
        player1_crowns = self.get_crown_count(1)

        # Regulation ends at 3:00. A crown advantage wins; a crown tie enters
        # two minutes of sudden-death overtime.
        if self.time >= self.overtime_start_time and not self.sudden_death:
            if player0_crowns != player1_crowns:
                self.game_over = True
                self.winner = 0 if player0_crowns > player1_crowns else 1
                return
            self.sudden_death = True
            self._sudden_death_crowns = (player0_crowns, player1_crowns)

        # Sudden death: first crown advantage wins instantly.
        if self.sudden_death:
            if player0_crowns != player1_crowns:
                self.game_over = True
                self.winner = 0 if player0_crowns > player1_crowns else 1
                return

            # At 5:00, the lowest-health remaining Crown Tower is the
            # tiebreaker. Exact equality is a real draw.
            if self.time >= self.tiebreaker_time:
                p0_lowest = self._lowest_remaining_tower_hp(0)
                p1_lowest = self._lowest_remaining_tower_hp(1)
                if p0_lowest > p1_lowest:
                    self.winner = 0
                elif p1_lowest > p0_lowest:
                    self.winner = 1
                else:
                    self.winner = None
                self.game_over = True
    
    def _update_tower_hp(self) -> None:
        """Update player tower HP from building entities"""
        for entity in self.entities.values():
            if not self._is_static_tower_entity(entity):
                continue
            player = self.players[entity.player_id]
            slot = entity._crown_tower_slot
            setattr(player, f"{slot}_tower_hp", entity.hitpoints)
    
    def get_state_summary(self) -> Dict:
        """Get current battle state summary"""
        return {
            "time": self.time,
            "tick": self.tick,
            "entities": len(self.entities),
            "players": [
                {
                    "elixir": p.elixir,
                    "crowns": self.get_crown_count(player_id),
                    "king_hp": p.king_tower_hp,
                    "left_hp": p.left_tower_hp,
                    "right_hp": p.right_tower_hp,
                    "next_card": p.get_next_card(),
                }
                for player_id, p in enumerate(self.players)
            ],
            "game_over": self.game_over,
            "winner": self.winner
        }

    def get_crown_count(self, player_id: int) -> int:
        """Return crowns earned by ``player_id`` from enemy towers destroyed."""
        return self.players[1 - player_id].get_towers_lost()

    def _get_king_tower_entity(self, player_id: int) -> Optional[Building]:
        for entity in self.entities.values():
            if (
                self._is_static_tower_entity(entity)
                and entity.player_id == player_id
                and entity._crown_tower_slot == "king"
            ):
                return entity
        return None

    def _activate_king_tower(self, player_id: int) -> None:
        king = self._get_king_tower_entity(player_id)
        if king is not None:
            king.activate()

    def _tower_damage_dealt_by_player(self, player_id: int) -> float:
        enemy_id = 1 - player_id
        current_enemy_hp = (
            self.players[enemy_id].king_tower_hp
            + self.players[enemy_id].left_tower_hp
            + self.players[enemy_id].right_tower_hp
        )
        start_enemy_hp = self._starting_total_tower_hp.get(enemy_id, current_enemy_hp)
        return max(0.0, start_enemy_hp - current_enemy_hp)

    def _lowest_remaining_tower_hp(self, player_id: int) -> int:
        """Return the lowest standing Crown Tower HP in fixed-point units."""
        p = self.players[player_id]
        standing = [
            hp
            for hp in (p.left_tower_hp, p.right_tower_hp, p.king_tower_hp)
            if hp > 0.0
        ]
        if not standing:
            return 0
        return int(round(min(standing) * 1000.0))

    def is_position_occupied_by_building(
        self,
        position: Position,
        mover_radius: float = 0.5,
        ignore_building_id: Optional[int] = None,
        movement_collision: bool = False,
    ) -> bool:
        """Return True when a position overlaps any live building footprint."""
        effective_mover_radius = min(float(mover_radius), 0.5) if movement_collision else float(mover_radius)
        if self.fast_path:
            self._refresh_alive_buildings_cache()
            buildings = self._alive_buildings
        else:
            buildings = self.entities.values()
        for entity in buildings:
            if not isinstance(entity, Building):
                continue
            if (not entity.is_alive) or (ignore_building_id is not None and entity.id == ignore_building_id):
                continue
            building_radius = getattr(entity.card_stats, "collision_radius", 1.0) or 1.0
            collision_units = tiles_to_logic_units(
                float(building_radius) + effective_mover_radius
            )
            dx_units = tiles_to_logic_units(position.x - entity.position.x)
            dy_units = tiles_to_logic_units(position.y - entity.position.y)
            if dx_units * dx_units + dy_units * dy_units < collision_units * collision_units:
                return True
        return False

    def is_deployment_payload_occupied(
        self,
        position: Position,
        *,
        mover_radius: float = 0.5,
        card_stats: CardStatsCompat | None = None,
    ) -> bool:
        """Return whether a live effect payload blocks card placement here.

        Timed death containers are not buildings and do not obstruct normal
        movement, but the game reserves their landing footprint until they
        resolve. The entity capability keeps this general for future payload
        types without teaching deployment code individual card names.
        """
        for entity in self.entities.values():
            if not entity.is_alive or not getattr(entity, "blocks_deployment", False):
                continue
            payload_radius = float(
                getattr(entity, "deployment_collision_radius", 0.5) or 0.5
            )
            if card_stats is None:
                if position.distance_to(entity.position) <= (
                    float(mover_radius) + payload_radius
                ) + 1e-9:
                    return True
                continue

            x1, x2, y1, y2 = self._footprint_bounds(position, card_stats)
            closest_x = max(x1, min(entity.position.x, x2))
            closest_y = max(y1, min(entity.position.y, y2))
            if entity.position.distance_to(Position(closest_x, closest_y)) <= (
                payload_radius + 1e-9
            ):
                return True
        return False

    def _building_footprint_size_tiles(self, card_stats: CardStatsCompat) -> int:
        """Return the integer placement columns touched by the hitbox."""
        raw_radius = getattr(card_stats, "collision_radius", None)
        radius = max(
            0.0,
            float(1.0 if raw_radius is None else raw_radius),
        )
        # Buildings are placed at tile centers. A radius that ends exactly on
        # a tile boundary touches both adjacent placement cells, matching the
        # native footprint scan (0.5 -> 2 cells, 0.6/1.0 -> 3 cells).
        return max(1, math.ceil(radius * 2.0) + 1)

    def _footprint_bounds(
        self,
        position: Position,
        card_stats: CardStatsCompat,
    ) -> tuple[float, float, float, float]:
        size = float(self._building_footprint_size_tiles(card_stats))
        half = size / 2.0
        return (position.x - half, position.x + half, position.y - half, position.y + half)

    def is_building_placement_occupied(
        self,
        position: Position,
        card_stats: CardStatsCompat,
    ) -> bool:
        """Return True when a new building footprint overlaps any live building footprint."""
        if self.fast_path:
            size = self._building_footprint_size_tiles(card_stats)
            tx = int(position.x)
            ty = int(position.y)
            if 0 <= tx < self.arena.width and 0 <= ty < self.arena.height:
                return bool(self.get_building_placement_blocked_mask_world(size)[ty, tx])
        x1, x2, y1, y2 = self._footprint_bounds(position, card_stats)
        buildings = self._alive_buildings if self.fast_path else self.entities.values()
        for entity in buildings:
            if not isinstance(entity, Building) or not entity.is_alive:
                continue
            ex1, ex2, ey1, ey2 = self._footprint_bounds(entity.position, entity.card_stats)
            overlap_x = x1 < ex2 and x2 > ex1
            overlap_y = y1 < ey2 and y2 > ey1
            if overlap_x and overlap_y:
                return True
        return False

    def is_ground_position_walkable(
        self,
        position: Position,
        mover: Optional[Entity] = None,
        *,
        ignore_building_id: Optional[int] = None,
    ) -> bool:
        """Ground movement validator including arena terrain and building footprints."""
        from .unit_traits import is_hover_unit_card

        if not self.is_entity_position_in_bounds(position, mover):
            return False
        hovering = bool(
            mover is not None and is_hover_unit_card(getattr(mover, "card_stats", None))
        )
        if hovering:
            # Hovering characters ignore water and dynamic ground bodies, but
            # still respect the arena's permanent blocked boundary cells.
            return bool(
                self.arena.is_valid_position(position)
                and not self.arena.is_blocked_position(position)
            )
        elif not self.arena.is_walkable(position):
            return False
        mover_radius = 0.5
        if mover is not None:
            mover_radius = getattr(mover.card_stats, "collision_radius", 0.5) or 0.5
        return not self.is_position_occupied_by_building(
            position,
            mover_radius,
            ignore_building_id=ignore_building_id,
            movement_collision=True,
        )

    def is_entity_position_in_bounds(
        self,
        position: Position,
        mover: Optional[Entity] = None,
    ) -> bool:
        """Return whether a moving entity center stays within native bounds."""
        epsilon = 1e-9
        edge = OUTERMOST_OBJECT_CENTER_TILES
        return (
            edge - epsilon <= position.x <= self.arena.width - edge + epsilon
            and edge - epsilon <= position.y <= self.arena.height - edge + epsilon
        )

    def _resolve_troop_collisions(self) -> None:
        """Accumulate one collision scan for every active movement component.

        This compatibility helper intentionally does not consume vectors;
        production ticks call ``_accumulate_troop_collision_for`` immediately
        before each individual troop update.
        """
        for entity in list(self.entities.values()):
            if isinstance(entity, Troop):
                self._accumulate_troop_collision_for(entity)

    @staticmethod
    def _collision_vector_units(
        entity: Troop,
        other_position: Position,
        collision_distance: float,
        other_mass: float,
        own_mass: float,
    ) -> tuple[int, int] | None:
        dx_units = tiles_to_logic_units(entity.position.x - other_position.x)
        dy_units = tiles_to_logic_units(entity.position.y - other_position.y)
        collision_units = tiles_to_logic_units(collision_distance)
        if abs(dx_units) > collision_units or abs(dy_units) > collision_units:
            return None
        distance_squared = dx_units * dx_units + dy_units * dy_units
        if distance_squared > collision_units * collision_units:
            return None
        if distance_squared == 0:
            dy_units = 1 if entity.player_id == 0 else -1
            distance_units = 1
        else:
            distance_units = max(1, math.isqrt(distance_squared))
        overlap_units = min(300, max(0, collision_units - distance_units))
        own_mass_units = max(1, round(own_mass))
        magnitude_units = min(
            300,
            int(overlap_units * other_mass / own_mass_units) + 1,
        )
        return (
            trunc_div(dx_units * magnitude_units, distance_units),
            trunc_div(dy_units * magnitude_units, distance_units),
        )

    def _accumulate_troop_collision_for(self, troop: Troop) -> None:
        """Queue body pressure seen by one native movement component."""
        from .unit_traits import is_in_transit, unit_mass, uses_air_collision_plane

        river_jumping = bool(getattr(troop, "_river_jump_active", False))
        death_spawn_traveling = bool(
            troop._death_spawn_travel_ticks_remaining > 0
        )
        mega_knight_airborne = (
            getattr(troop, "_mk_leap_phase", None) == "airborne"
        )
        if (
            not troop.is_alive
            or (
                troop.is_stunned()
                and not river_jumping
                and not death_spawn_traveling
            )
            or (
                is_in_transit(troop)
                and not river_jumping
                and not mega_knight_airborne
            )
        ):
            return

        own_radius = max(
            0.2,
            getattr(troop.card_stats, "collision_radius", 0.5) or 0.5,
        )
        own_mass = max(1e-9, unit_mass(troop.card_stats))
        own_air_collision = uses_air_collision_plane(troop)
        collision_candidates: Iterable[Entity] = self.entities.values()
        if self.fast_path and _USE_COLLISION_BUCKET_CANDIDATES:
            collision_candidates = self.iter_entities_in_radius(
                troop.position,
                own_radius + self._max_target_collision_radius,
            )
        for other in collision_candidates:
            other_airborne_leap = (
                getattr(other, "_mk_leap_phase", None) == "airborne"
            )
            if (
                other is troop
                or not isinstance(other, Troop)
                or not other.is_alive
                or (
                    is_in_transit(other)
                    and not getattr(other, "_river_jump_active", False)
                    and not other_airborne_leap
                )
                or own_air_collision != uses_air_collision_plane(other)
            ):
                continue
            other_radius = max(
                0.2,
                getattr(other.card_stats, "collision_radius", 0.5) or 0.5,
            )
            vector = self._collision_vector_units(
                troop,
                other.position,
                own_radius + other_radius,
                max(1e-9, unit_mass(other.card_stats)),
                own_mass,
            )
            if vector is not None:
                troop.accumulate_movement_vector_units(*vector)

        if own_air_collision:
            return
        # Static objects do not receive a reciprocal vector. Native supplies
        # mass 20 and caps the moving character's radius contribution at 0.5.
        static_radius = min(own_radius, 0.5)
        for building in collision_candidates:
            if (
                not isinstance(building, Building)
                or not building.is_alive
            ):
                continue
            building_radius = max(
                0.0,
                getattr(building.card_stats, "collision_radius", 0.0) or 0.0,
            )
            vector = self._collision_vector_units(
                troop,
                building.position,
                static_radius + building_radius,
                20.0,
                own_mass,
            )
            if vector is not None:
                troop.accumulate_movement_vector_units(*vector)
