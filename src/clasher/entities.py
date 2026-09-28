from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import Optional, List, Dict, Any
from enum import Enum
from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .battle import BattleState

from .arena import Position
from .attack_clock import OrdinaryAttackClock
from .card_types import CardStatsCompat, Mechanic
from .factory.dynamic_factory import troop_from_character_data
from .unit_traits import (
    is_above_ground_surface,
    is_airborne_target,
    is_hover_unit_card,
    is_native_building_target,
    uses_air_collision_plane,
)
from .native_tilemap import clamp_native_object_axis
from .kinematics import (
    LOGIC_TICK_SECONDS,
    NATIVE_MOVEMENT_SUBSTEP_UNITS,
    logic_time_milliseconds,
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    movement_component_vector_logic_units,
    normalized_vector_logic_units,
    pending_projectile_duration_ms,
    speed_work_for_duration,
    tiles_to_logic_units,
    tiles_per_second_to_logic_speed,
    trunc_div,
    vector_towards_logic_units,
)
from .logic_math import (
    logic_vector_angle,
    native_percent_damage,
    rotate_logic_vector,
    spawn_target_distance_discount_sq_units,
)
from .gamedata_normalization import serialized_hit_planes
from .balance import (
    ADD_CHARACTER_RANGE_TO_RADIUS,
    COMBAT_CMP_USE_HIT_STARTED,
    CURRENT_TARGET_IGNORES_PENDING_DAMAGE,
    EXTRA_SIGHT_RANGE_TO_BUILDING,
    EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS,
    GLOBAL_ATTACK_FINISH_TIME_MS,
    LOGIC_ALLOW_DISCARD_HIT_ON_AREA_DAMAGE,
    LOGIC_CANCEL_HIT_FROM_LONG_DISTANCE,
    LOGIC_CANCEL_HIT_FROM_LONG_DISTANCE_RANGE,
    LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK,
    LOGIC_INFERNO_RESET_ON_SHIELD_LOST,
    LOGIC_LOAD_FIRST_HIT_KEEP_LOADED_AFTER_DISCARD,
    LOGIC_LOAD_FIRST_HIT_RESET_TIMER_WHEN_ZAPPED,
    LOGIC_PENDING_DAMAGE_IGNORE_IF_DURATION_LESS,
    LOGIC_PATHFIND_BACKWARDS_TRY_KEEP_TARGET,
    LOGIC_PRESERVE_TARGET_IF_HIT_STARTED,
    LOGIC_RANGE_EXTENSION_TO_KEEP_TARGET,
    LOGIC_SYMMETRIC_CLOSEST_BUILDING_ITERATION,
    LOGIC_XPOS_BASED_TOWER_TARGETING,
)


class EntityType(Enum):
    TROOP = "troop"
    BUILDING = "building"
    PROJECTILE = "projectile"
    AURA = "aura"


class TargetType(Enum):
    GROUND = "ground"
    AIR = "air" 
    BOTH = "both"


@dataclass
class PeriodicDamageEffect:
    """One source-owned damage buff running on a target's component clock."""

    source_id: int
    source_kind: str | None
    remaining: float
    hit_interval: float
    time_to_next_hit: float
    damage: float
    hard_remaining: float | None = None
    affects_hidden: bool = False


# Collision positions are quantized after each 50 ms logic frame. Derived
# Euclidean distances can therefore straddle an exact range boundary by a few
# floating-point ULPs after a 180-degree arena transform, even when the game
# state is the same. Keep all acquisition/reach boundary decisions inside one
# sub-logic-unit tolerance so those predicates behave like native fixed-point
# comparisons.
GEOMETRY_BOUNDARY_EPSILON = 1e-8
TARGET_DISTANCE_TIE_EPSILON = 1e-6
# Current native globals, expressed in tiles. These extend only an existing
# combat lock; acquisition and the actual hit/clock boundary still use the
# card's exact serialized range.
STARTED_ATTACK_KEEP_RANGE_EXTENSION = 0.5


@dataclass
class Entity(ABC):
    id: int
    position: Position
    player_id: int
    card_stats: CardStatsCompat

    # Combat stats
    hitpoints: float
    max_hitpoints: float
    damage: float
    range: float
    sight_range: float

    # Timing
    attack_cooldown: float = 0.0
    load_time: float = 0.0
    _attack_finish_elapsed_ms: int = field(default=0, repr=False)
    _resume_pending_hit: bool = field(default=False, repr=False)
    _ordinary_clock: OrdinaryAttackClock | None = field(default=None, repr=False)
    _ordinary_clock_projection: float = field(default=0.0, repr=False)
    _ordinary_clock_due: bool = field(default=False, repr=False)
    _ordinary_force_due: bool = field(default=False, repr=False)
    _native_object_birth_tick: int | None = field(default=None, repr=False)
    _native_deployed_elapsed_ms: int = field(default=0, repr=False)
    _freeze_target_pause_remaining: float = field(default=0.0, repr=False)
    # True once an in-range target has started the active hit timeline, including
    # its remaining load work. It distinguishes committed wind-up
    # state from ordinary preloading when a target becomes invalid.
    _attack_windup_active: bool = field(default=False, repr=False)
    # Knockback can consume the one-time preload for an interrupted attack.
    # It becomes available again only after an attack is successfully made.
    _attack_preload_blocked: bool = field(default=False, repr=False)
    deploy_delay_remaining: float = 0.0
    spawn_stagger_remaining: float = 0.0
    placement_delay_total: float = 0.0
    # True while a troop/building is in its pre-deployment action. It is
    # already present in the arena and can be targeted, damaged, affected,
    # and collided with; only its own actions remain blocked until deployment
    # finishes.
    placement_pending: bool = False
    # External displacement sequences such as Fisherman's hook own movement
    # for several ticks. Interrupting displacement also blocks combat; a
    # serialized non-interrupting self-recoil can keep its combat clock.
    forced_movement_active: bool = False
    _knockback_target: Optional[Position] = field(default=None, repr=False)
    _knockback_velocity_work: int = field(default=0, repr=False)
    _knockback_interrupts_combat: bool = field(default=True, repr=False)
    _knockback_reset_hit_on_movement: bool = field(default=False, repr=False)
    # CharacterData::DeathSpawnPushback uses a dedicated movement-component
    # state. The child is created at its radial destination, that coordinate
    # is retained here, and its live position is reset to the parent's death
    # origin. Unlike ordinary knockback this travel does not interrupt the
    # child's combat component.
    _death_spawn_travel_target: Optional[Position] = field(
        default=None,
        repr=False,
    )
    _death_spawn_travel_ticks_remaining: int = field(default=0, repr=False)
    
    # State
    target_id: Optional[int] = None
    _combat_target_pending_lethal: bool = field(default=False, repr=False)
    _has_attacked_current_target: bool = field(default=False, repr=False)
    is_alive: bool = True
    is_clone: bool = False
    is_air_unit: bool = False  # True for flying troops like Minions, Balloon, Dragon
    _is_hover_unit: bool = field(default=False, init=False, repr=False)
    entity_kind: int = 0  # 0=troop,1=building,2=projectile,3=aura/effect,4=other
    # Native death spawns carry a source-dependent target-eligibility marker.
    # LogicCharacter::tick advances it in integer milliseconds and clears it
    # only after crossing the shared attack-finish duration. ``-1`` is the
    # inactive sentinel; zero is installed by the parent's death-spawn path.
    _death_spawn_target_immunity_elapsed_ms: int = field(default=-1, repr=False)
    # Pending damage keeps the greatest remaining registered duration.
    # Launches raise it, capped at 1000 ms; character object ticks subtract
    # 50 ms. Removing a projectile subtracts damage without resetting it.
    _pending_projectile_max_duration_ms: int = field(default=0, repr=False)
    # Updated by the native-grid route planner during movement and consumed
    # by the next combat component's target fallback decision.
    _ground_path_backwards: bool = field(default=False, repr=False)
    _native_ground_route_direction: tuple[int, int] | None = field(default=None, repr=False)
    _native_navigation_target_id: int | None = field(default=None, repr=False)
    _attack_finish_tick: int = field(default=-1, repr=False)
    _native_friendly_building_signature: tuple[int, ...] | None = field(default=None, repr=False)
    
    # Status effects
    stun_timer: float = 0.0
    _native_moving_when_frozen: bool = field(default=False, repr=False)
    _stun_interrupt_deferred_until_landing: bool = field(
        default=False,
        repr=False,
    )
    # Absolute battle time used only for Freeze inheritance across a death
    # spawn. Ordinary overlapping stuns continue to compose through
    # ``stun_timer`` and are never inherited.
    freeze_expiry_time: float = 0.0
    slow_timer: float = 0.0
    slow_multiplier: float = 1.0
    original_speed: Optional[float] = None
    # Character-owned temporary movement buffs (for example Archer Queen's
    # Cloak) have an independent lifetime but occupy the same strongest-
    # negative native lane as external slows.
    movement_mode_multiplier: float = 1.0
    attack_speed_debuff_multiplier: float = 1.0
    spawn_speed_debuff_multiplier: float = 1.0
    attack_speed_buff_multiplier: float = 1.0
    # Intrinsic attack modes (for example Archer Queen's Cloak) occupy the
    # same strongest-positive-modifier lane as Rage, but have an independent
    # lifetime. Keeping the clocks separate prevents one effect from
    # restoring or erasing another when their expiry order overlaps.
    attack_mode_multiplier: float = 1.0
    movement_speed_buff_multiplier: float = 1.0
    spawn_speed_buff_multiplier: float = 1.0
    haste_timer: float = 0.0
    last_attack_time: float = 0.0  # For visualization tracking
    _slow_effects: List[tuple[float, float, float, float]] = field(
        default_factory=list,
        repr=False,
    )
    _haste_effects: List[tuple[float, float, float, float]] = field(
        default_factory=list,
        repr=False,
    )
    _periodic_damage_effects: Dict[int, PeriodicDamageEffect] = field(
        default_factory=dict,
        repr=False,
    )

    # Native movement components collect collision/attraction vectors in a
    # shared accumulator.  The average is consumed by the next movement
    # update; ordinary collision pressure is capped, while controlled pulls
    # such as Tornado explicitly bypass that cap.  Keep this on Entity rather
    # than Troop because movable effect containers use the same engine path.
    _movement_vector_x_units: int = field(default=0, repr=False)
    _movement_vector_y_units: int = field(default=0, repr=False)
    _movement_vector_count: int = field(default=0, repr=False)
    _movement_vector_bypasses_cap: bool = field(default=False, repr=False)
    _pending_movement_x: float = field(default=0.0, repr=False)
    _pending_movement_y: float = field(default=0.0, repr=False)
    _pending_movement_consumed: bool = field(default=True, repr=False)
    # Native characters retain a fixed-point facing vector independently of
    # displacement. Child-spawn rings consult it only when the parent's
    # SpawnAngleShift is nonzero.
    _facing_x_units: int = field(default=0, repr=False)
    _facing_y_units: int = field(default=0, repr=False)
    # SpawnConstPriority assigns child n the permanent squared-distance
    # allowance ``(n * 80)^2`` and subtracts it from center-distance squared
    # during target acquisition/reach checks. It is independent of the
    # DeathSpawnPushback travel state above.
    _native_target_distance_discount_sq_units: int = field(default=0, repr=False)
    # Native Character::laneID is selected from the arena path grid when the
    # object is spawned. Ground default-target selection keeps using this
    # stored lane even after collision or displacement moves the character.
    _native_lane_id: int = field(default=0, repr=False)

    # Mechanics system
    mechanics: List[Mechanic] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_hitpoints == 0:
            self.max_hitpoints = self.hitpoints
        self._is_hover_unit = is_hover_unit_card(self.card_stats)
        # Classify by the gameplay base type, not the concrete class name.
        # Exact-name checks silently turn specialized/custom subclasses into
        # ``other`` entities, which makes targeting, collision, and effects
        # disagree with their parent type.
        if isinstance(self, Troop):
            self.entity_kind = 0
        elif isinstance(self, Building):
            self.entity_kind = 1
        elif isinstance(self, (Projectile, RollingProjectile)):
            self.entity_kind = 2
        elif isinstance(
            self,
            (
                AreaEffect,
                BuffAreaEffect,
                TimedExplosive,
                DeathAreaEffectContainer,
                DeathAreaStartAction,
                Graveyard,
                ChainLightning,
            ),
        ):
            self.entity_kind = 3
        else:
            self.entity_kind = 4
        if self._facing_x_units == 0 and self._facing_y_units == 0:
            self._facing_y_units = 1000 if self.player_id == 0 else -1000
        # Call on_attach for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_attach(self)

    def face_towards(self, position: Position) -> None:
        """Update the retained native direction from a world-space point."""
        dx_units = tiles_to_logic_units(position.x - self.position.x)
        dy_units = tiles_to_logic_units(position.y - self.position.y)
        if dx_units != 0 or dy_units != 0:
            self._facing_x_units = dx_units
            self._facing_y_units = dy_units

    def native_facing_units(self) -> tuple[int, int]:
        return self._facing_x_units, self._facing_y_units
    
    @abstractmethod
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update entity state each tick"""
        pass

    def accumulate_movement_vector(
        self,
        dx: float,
        dy: float,
        *,
        bypasses_cap: bool = False,
    ) -> None:
        """Add one native external-movement contribution for a later tick."""
        self.accumulate_movement_vector_units(
            tiles_to_logic_units(dx),
            tiles_to_logic_units(dy),
            bypasses_cap=bypasses_cap,
        )

    def accumulate_movement_vector_units(
        self,
        dx_units: int,
        dy_units: int,
        *,
        bypasses_cap: bool = False,
    ) -> None:
        """Add one already-quantized movement contribution in logic units."""
        if not self.is_alive:
            return
        self._movement_vector_x_units += int(dx_units)
        self._movement_vector_y_units += int(dy_units)
        self._movement_vector_count += 1
        self._movement_vector_bypasses_cap = (
            self._movement_vector_bypasses_cap or bool(bypasses_cap)
        )

    def begin_movement_tick(self) -> None:
        """Consume the shared vector accumulator into this frame's movement."""
        count = self._movement_vector_count
        if count <= 0:
            self._pending_movement_x = 0.0
            self._pending_movement_y = 0.0
            self._pending_movement_consumed = True
            return

        move_x_units = trunc_div(self._movement_vector_x_units, count)
        move_y_units = trunc_div(self._movement_vector_y_units, count)
        magnitude_squared = move_x_units * move_x_units + move_y_units * move_y_units
        # The movement component normalizes ordinary accumulated pressure to
        # 150 logic units (0.15 tiles). Attraction marks the accumulator as
        # controlled and therefore skips this cap.
        if (
            not self._movement_vector_bypasses_cap
            and magnitude_squared >= 150 * 150 + 1
        ):
            magnitude_units = max(1, math.isqrt(magnitude_squared))
            move_x_units = trunc_div(move_x_units * 150, magnitude_units)
            move_y_units = trunc_div(move_y_units * 150, magnitude_units)

        self._pending_movement_x = logic_units_to_tiles(move_x_units)
        self._pending_movement_y = logic_units_to_tiles(move_y_units)
        self._pending_movement_consumed = False
        self._movement_vector_x_units = 0
        self._movement_vector_y_units = 0
        self._movement_vector_count = 0
        self._movement_vector_bypasses_cap = False

    def take_pending_movement_vector(self) -> tuple[float, float]:
        """Return this frame's external vector for composition with movement."""
        if self._pending_movement_consumed:
            return (0.0, 0.0)
        self._pending_movement_consumed = True
        return (self._pending_movement_x, self._pending_movement_y)

    def finish_movement_tick(self, battle_state: 'BattleState') -> None:
        """Apply an external vector when no card-specific movement consumed it."""
        previous_position = Position(self.position.x, self.position.y)
        move_x, move_y = self.take_pending_movement_vector()
        self._pending_movement_x = 0.0
        self._pending_movement_y = 0.0
        frozen_waypoint = None
        if isinstance(self, Troop) and self.is_stunned() and self._native_moving_when_frozen:
            route = getattr(self, "_native_ground_route_cells", None)
            if route:
                from .pathfinding import advance_native_ground_route

                frozen_waypoint = Position(
                    route[0][0] * 0.5 + 0.25, route[0][1] * 0.5 + 0.25,
                )
                self.face_towards(frozen_waypoint)
        if abs(move_x) <= 1e-15 and abs(move_y) <= 1e-15:
            # Frozen walking still services the retained route without travel
            # or body pressure, including its heading and reached-node work.
            if frozen_waypoint is not None:
                advance_native_ground_route(self, frozen_waypoint, previous_position)
            return

        x_units = tiles_to_logic_units(self.position.x)
        y_units = tiles_to_logic_units(self.position.y)
        dx_units, dy_units = tiles_to_logic_units(move_x), tiles_to_logic_units(move_y)
        moved_x_units, moved_y_units = x_units + dx_units, y_units + dy_units
        # Native moveObject forces terrain clipping for deployment state 4
        # (0x115dc28..0x115dc4c), even without a controlled-vector flag.
        # Ordinary deployed body pressure does not take this override.
        if isinstance(self, Troop) and self.deploy_delay_remaining > 0:
            from .native_tilemap import clip_native_ground_pressure
            from .unit_traits import is_hover_unit_card, uses_air_collision_plane

            if not uses_air_collision_plane(self) and not is_hover_unit_card(self.card_stats):
                moved_x_units, moved_y_units = clip_native_ground_pressure(
                    x_units, y_units, dx_units, dy_units,
                )
        moved_x = logic_units_to_tiles(moved_x_units)
        moved_y = logic_units_to_tiles(moved_y_units)
        self.position.x = clamp_native_object_axis(
            moved_x,
            battle_state.arena.width,
        )
        self.position.y = clamp_native_object_axis(
            moved_y,
            battle_state.arena.height,
        )
        battle_state.sync_fast_target_entity(self)
        if frozen_waypoint is not None:
            advance_native_ground_route(self, frozen_waypoint, previous_position)

    def begin_knockback(
        self,
        target: Position,
        distance_units: int,
        *,
        source_kind: str | None,
        interrupts_combat: bool = True,
        reset_hit_on_movement: bool = False,
    ) -> bool:
        """Install the native movement-component pushback state."""
        if self._knockback_target is not None:
            return False
        distance_units = max(0, min(10_000, int(distance_units)))
        velocity_work = 0
        accumulated_work = 0
        while accumulated_work < distance_units:
            velocity_work += 25
            accumulated_work += velocity_work
        self._knockback_target = Position(target.x, target.y)
        self._knockback_velocity_work = velocity_work
        self._knockback_interrupts_combat = bool(interrupts_combat)
        self._knockback_reset_hit_on_movement = reset_hit_on_movement
        self.forced_movement_active = True
        if interrupts_combat:
            self.interrupt_by_forced_movement(
                source_kind=source_kind,
                movement_kind="knockback",
            )
        else:
            self._notify_forced_movement(source_kind, "knockback")
        return True

    def begin_death_spawn_travel(self, origin: Position) -> None:
        """Install native radial death-spawn travel from ``origin``.

        LogicMovementComponent retains the child's already-computed ring
        coordinate, moves the object back to the parent's death coordinate,
        and services the retained destination for ``distance / 250`` frames.
        The division truncates, so diagonal fixed-point ring coordinates can
        deliberately stop short of their nominal destination.
        """
        target_x_units = tiles_to_logic_units(self.position.x)
        target_y_units = tiles_to_logic_units(self.position.y)
        origin_x_units = tiles_to_logic_units(origin.x)
        origin_y_units = tiles_to_logic_units(origin.y)
        dx_units = target_x_units - origin_x_units
        dy_units = target_y_units - origin_y_units
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)

        self.position = Position(
            logic_units_to_tiles(origin_x_units),
            logic_units_to_tiles(origin_y_units),
        )
        ticks = distance_units // NATIVE_MOVEMENT_SUBSTEP_UNITS
        if ticks > 0:
            self._death_spawn_travel_target = Position(
                logic_units_to_tiles(target_x_units),
                logic_units_to_tiles(target_y_units),
            )
            self._death_spawn_travel_ticks_remaining = ticks
        else:
            self._death_spawn_travel_target = None
            self._death_spawn_travel_ticks_remaining = 0

    def quantize_logic_position(self) -> None:
        """Commit position to the client's integer 1/1000-tile grid."""
        self.position.x = logic_units_to_tiles(tiles_to_logic_units(self.position.x))
        self.position.y = logic_units_to_tiles(tiles_to_logic_units(self.position.y))

    def _projectile_launch_geometry(self, target: 'Entity') -> tuple[Position, int, int]:
        """Return the serialized projectile muzzle position and aim vector."""
        return self._projectile_launch_geometry_at(target.position)

    def _projectile_launch_geometry_at(
        self,
        target_position: Position,
    ) -> tuple[Position, int, int]:
        """Return projectile geometry for an explicit aim point."""
        dx_units = tiles_to_logic_units(target_position.x - self.position.x)
        dy_units = tiles_to_logic_units(target_position.y - self.position.y)
        start_radius = float(
            getattr(self.card_stats, "projectile_start_radius", 0.0) or 0.0
        )
        muzzle_x_units, muzzle_y_units = normalized_vector_logic_units(
            dx_units,
            dy_units,
            tiles_to_logic_units(start_radius),
        )
        # ProjectileYOffset is owner-relative in the game data: positive Y
        # points toward the opponent for player 0 and is inverted for player 1.
        owner_y_offset = float(
            getattr(self.card_stats, "projectile_y_offset", 0.0) or 0.0
        ) * (1.0 if self.player_id == 0 else -1.0)
        return (
            Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.x) + muzzle_x_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y)
                    + muzzle_y_units
                    + tiles_to_logic_units(owner_y_offset)
                ),
            ),
            dx_units,
            dy_units,
        )
    
    def take_damage(
        self,
        amount: float,
        *,
        source_kind: str | None = None,
        affects_hidden: bool = False,
    ) -> None:
        """Apply damage to entity"""
        if not self.can_receive_effect(
            source_kind,
            affects_hidden=affects_hidden,
        ):
            return
        incoming = float(amount)
        for mechanic in getattr(self, "mechanics", []):
            guard = getattr(mechanic, "take_damage_during_dash", None)
            if callable(guard):
                should_take_damage = guard(self, incoming)
                if not should_take_damage:
                    return
            modifier = getattr(mechanic, "modify_incoming_damage", None)
            if callable(modifier):
                incoming = float(modifier(self, incoming))

        if incoming <= 0:
            return

        # Dormant defensive buildings (the standard arena's King Tower) begin
        # their activation sequence when damaged rather than attacking at once.
        activate = getattr(self, "activate", None)
        if incoming > 0 and callable(activate) and getattr(self, "requires_activation", False):
            activate()
        self.hitpoints = max(0, self.hitpoints - incoming)
        if self.hitpoints <= 0 and self.is_alive:
            self.is_alive = False
            self.on_death()  # Trigger death mechanics

    def broadcast_shield_lost(self) -> None:
        """Notify every live combat object that this entity lost its shield.

        Native routes shield loss through the battle object manager.  The
        callback is global rather than damage-source-owned, which lets a
        connected variable-damage weapon react when a different ally breaks
        its target's shield.
        """
        if not LOGIC_INFERNO_RESET_ON_SHIELD_LOST:
            return
        battle_state = getattr(self, "battle_state", None)
        if battle_state is None:
            return
        for observer in tuple(battle_state.entities.values()):
            if not observer.is_alive:
                continue
            for mechanic in getattr(observer, "mechanics", []):
                mechanic.on_shield_lost(observer, self)

    def can_receive_effect(
        self,
        source_kind: str | None = None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        # Group members waiting for their spawn stagger have no active
        # effect recipient yet. Deployment delay after that boundary is hitable.
        if self.spawn_stagger_remaining > 1e-9:
            return False
        for mechanic in getattr(self, "mechanics", []):
            allows = getattr(mechanic, "allows_effect", None)
            if callable(allows) and not allows(
                self,
                source_kind,
                affects_hidden=affects_hidden,
            ):
                return False
        return True

    def can_receive_area_damage(
        self,
        source_kind: str | None = None,
        *,
        affects_hidden: bool = False,
        source_entity: Optional['Entity'] = None,
    ) -> bool:
        """Return whether an area-damage query may include this entity.

        Invisibility and hidden-building state are separate native concepts.
        A committed direct projectile can still hit a troop that cloaks while
        it is in flight, while an area scan includes a cloaked character only
        when its character payload explicitly opts in.
        """
        if (
            self._has_death_spawn_target_immunity()
            and source_entity is not None
            and getattr(source_entity, "entity_kind", 4) in {0, 1}
        ):
            return False
        stealth_until = int(getattr(self, "_stealth_until", 0) or 0)
        battle_state = getattr(self, "battle_state", None)
        now_ms = logic_time_milliseconds(getattr(battle_state, "time", 0.0))
        if (
            stealth_until > now_ms
            and not bool(
                getattr(
                    getattr(self, "card_stats", None),
                    "allow_area_damage_when_invisible",
                    False,
                )
            )
        ):
            return False
        return self.can_receive_effect(
            source_kind,
            affects_hidden=affects_hidden,
        )

    def can_receive_forced_movement(
        self,
        source_kind: str | None = None,
        movement_kind: str = "knockback",
    ) -> bool:
        """Return whether a typed physical displacement can affect this entity.

        Most displacement shares the ordinary damage/status effect guard. A
        mechanic may provide an explicit decision when the game treats one
        physical interaction differently from damage immunity.
        """
        explicitly_allowed = False
        for mechanic in getattr(self, "mechanics", []):
            allows = getattr(mechanic, "allows_forced_movement", None)
            if not callable(allows):
                continue
            decision = allows(self, source_kind, movement_kind)
            if decision is False:
                return False
            explicitly_allowed = explicitly_allowed or decision is True
        return explicitly_allowed or self.can_receive_effect(source_kind)

    def is_visible_to(self, player_id: int) -> bool:
        """Return whether this entity is present in a player's visual state.

        Cloak/invisibility prevents troops and buildings from acquiring a
        target; it does not hide the card from either human player. A
        retracted Tesla likewise remains visible as its arena trapdoor.
        Movement phases such as jumps and dashes remain visible unless a
        mechanic explicitly declares otherwise.
        """
        if self.player_id == player_id:
            return True
        for mechanic in getattr(self, "mechanics", []):
            blocks_visibility = getattr(mechanic, "blocks_visibility", None)
            if callable(blocks_visibility) and blocks_visibility(self, player_id):
                return False
        return True

    def is_targetable_by(
        self,
        player_id: int,
        *,
        allow_hidden_building_path: bool = False,
    ) -> bool:
        """Return shared lock eligibility for attacks and secondary chains."""
        if (
            not self.is_alive
            or self.player_id == player_id
            or self.entity_kind in {2, 3}
            or self.spawn_stagger_remaining > 1e-9
            or self._has_death_spawn_target_immunity()
        ):
            return False
        hidden = bool(getattr(self, "_hidden_building", False))
        if hidden and not allow_hidden_building_path:
            return False
        for mechanic in getattr(self, "mechanics", []):
            blocks_targeting = getattr(mechanic, "blocks_targeting", None)
            if callable(blocks_targeting) and blocks_targeting(self):
                return False
        stealth_until = int(getattr(self, "_stealth_until", 0) or 0)
        battle_state = getattr(self, "battle_state", None)
        now_ms = logic_time_milliseconds(getattr(battle_state, "time", 0.0))
        return stealth_until <= now_ms

    def is_secondary_effect_targetable_by(self, player_id: int) -> bool:
        """Return eligibility for target-seeking secondary attack payloads.

        Chained attacks can jump onto invisible units even though ordinary
        troop/building locks cannot acquire them. Characters in their ordinary
        deployment state are already arena residents and remain eligible.
        Actual arena-absence states, hidden buildings, and mechanics that
        explicitly block targeting are not valid chain nodes.
        """
        if (
            not self.is_alive
            or self.player_id == player_id
            or self.entity_kind in {2, 3}
            or getattr(self, "_hidden_building", False)
            or self._has_death_spawn_target_immunity()
        ):
            return False
        for mechanic in getattr(self, "mechanics", []):
            blocks_targeting = getattr(mechanic, "blocks_targeting", None)
            if callable(blocks_targeting) and blocks_targeting(self):
                return False
        return True

    def _has_death_spawn_target_immunity(self) -> bool:
        """Return whether native character-source targeting is still gated."""
        return bool(
            LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK
            and self._death_spawn_target_immunity_elapsed_ms >= 0
        )

    def _activate_death_spawn_target_immunity(self) -> None:
        """Install the native death-spawn marker only while its global is on."""
        self._death_spawn_target_immunity_elapsed_ms = (
            0 if LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK else -1
        )

    def _tick_death_spawn_target_immunity(self, dt: float) -> None:
        """Advance the native death-spawn marker in the character object phase."""
        if not self._has_death_spawn_target_immunity():
            return
        self._death_spawn_target_immunity_elapsed_ms += max(
            0,
            logic_time_milliseconds(dt),
        )
        if (
            GLOBAL_ATTACK_FINISH_TIME_MS
            < self._death_spawn_target_immunity_elapsed_ms
        ):
            self._death_spawn_target_immunity_elapsed_ms = -1
            battle_state = getattr(self, "battle_state", None)
            sync_target = getattr(battle_state, "sync_fast_target_entity", None)
            if callable(sync_target):
                sync_target(self)

    def on_spawn(self) -> None:
        """Run deployment-complete hooks exactly once.

        Entities are inserted into the arena at card placement time, while
        spawn payloads such as Electro Wizard's zap and Mega Knight's landing
        resolve only after their deploy timer.  Keeping that distinction here
        prevents every spawn mechanic from growing its own timer.
        """
        if getattr(self, "_spawn_hook_fired", False):
            return
        if self.deploy_delay_remaining > 1e-9:
            self._spawn_hook_pending = True
            return
        self._spawn_hook_pending = False
        self._spawn_hook_fired = True
        battle_state = getattr(self, "battle_state", None)
        if getattr(battle_state, "debug_logs", False):
            print(f"[Lifecycle] on_spawn {getattr(self.card_stats, 'name', 'Unknown')} id={self.id}")
        for mechanic in self.mechanics:
            mechanic.on_spawn(self)

    def on_death(self) -> None:
        """Called when entity dies"""
        battle_state = getattr(self, "battle_state", None)
        if getattr(battle_state, "debug_logs", False):
            print(f"[Lifecycle] on_death {getattr(self.card_stats, 'name', 'Unknown')} id={self.id}")
        for mechanic in self.mechanics:
            mechanic.on_death(self)
    
    def _deal_attack_damage(
        self,
        primary_target: 'Entity',
        damage: float,
        battle_state: 'BattleState',
        *,
        exclude_hit_mechanic=None,
    ) -> None:
        """Resolve a direct combat hit in the attacker's component turn.

        Native melee/building attacks call ``takeDamage`` and install their
        on-hit buff before the manager advances to the next combat component.
        Only a separately created projectile defers damage until its own
        object-phase tick.
        """
        # Earlier combat components can kill the committed primary target.
        # Its aim point still anchors splash against the surviving neighbors.
        if not primary_target.is_alive and self._attack_area_damage_radius() <= 0:
            return
        committed_targets = self._snapshot_attack_damage_targets(
            primary_target,
            battle_state,
        )
        self._resolve_attack_damage(
            primary_target,
            damage,
            battle_state,
            committed_targets=committed_targets,
            exclude_hit_mechanic=exclude_hit_mechanic,
        )

    def _snapshot_attack_damage_targets(
        self,
        primary_target: 'Entity',
        battle_state: 'BattleState',
    ) -> tuple['Entity', ...]:
        """Capture every target overlapped by one committed direct attack."""
        source_kind = getattr(getattr(self, "card_stats", None), "name", None)
        primary_receives_hit = (
            primary_target.is_alive
            and primary_target.can_receive_effect(source_kind)
        )
        area_damage_radius = self._attack_area_damage_radius()
        if not area_damage_radius or area_damage_radius <= 0:
            return (primary_target,) if primary_receives_hit else ()

        area_origin = (
            self.position
            if getattr(self.card_stats, "self_as_aoe_center", False)
            else primary_target.position
        )
        source_radius = 0.0
        for mechanic in getattr(self, "mechanics", []):
            geometry = getattr(mechanic, "attack_area_geometry", None)
            if not callable(geometry):
                continue
            override = geometry(self, primary_target)
            if override is not None:
                area_origin, source_radius = override
                break

        targets = [primary_target] if primary_receives_hit else []
        targets.extend(
            self._snapshot_attack_area_targets_at(
                area_origin,
                area_damage_radius,
                battle_state,
                source_radius=source_radius,
                excluded_target=primary_target,
            )
        )
        return tuple(targets)

    def _attack_area_damage_radius(self) -> float:
        """Return the serialized radius used by this attack's area payload."""
        radius_units = getattr(self.card_stats, "area_damage_radius", None)
        if not radius_units:
            radius_units = getattr(
                self.card_stats,
                "projectile_splash_radius",
                None,
            )
        return max(0.0, float(radius_units or 0.0) / 1000.0)

    def _snapshot_attack_area_targets_at(
        self,
        area_origin: Position,
        area_damage_radius: float,
        battle_state: 'BattleState',
        *,
        source_radius: float = 0.0,
        excluded_target: Optional['Entity'] = None,
    ) -> tuple['Entity', ...]:
        """Capture living recipients around a committed area aim point."""
        source_kind = getattr(getattr(self, "card_stats", None), "name", None)
        targets: list[Entity] = []
        for entity in battle_state.entities.values():
            if (
                entity is excluded_target
                or entity.player_id == self.player_id
                or not entity.is_alive
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue
            if is_airborne_target(entity) and not self._can_attack_air():
                continue
            if (not is_airborne_target(entity)) and not self._can_attack_ground():
                continue
            if not entity.can_receive_area_damage(
                source_kind,
                source_entity=self,
            ):
                continue
            if entity.intersects_native_area(
                area_origin,
                area_damage_radius + source_radius,
            ):
                targets.append(entity)
        return tuple(targets)

    def _resolve_attack_damage(
        self,
        primary_target: 'Entity',
        damage: float,
        battle_state: 'BattleState',
        *,
        committed_targets: tuple['Entity', ...] | None = None,
        exclude_hit_mechanic=None,
    ) -> None:
        """Resolve a previously committed direct hit and its on-hit hooks."""

        # Record attack time for AoE visualization
        self.last_attack_time = battle_state.time

        targets = (
            committed_targets
            if committed_targets is not None
            else self._snapshot_attack_damage_targets(primary_target, battle_state)
        )
        for target in targets:
            target_damage = float(damage)
            for mechanic in self.mechanics:
                modifier = getattr(mechanic, "modify_outgoing_damage", None)
                if callable(modifier):
                    target_damage = float(modifier(self, target, target_damage))
            target.take_damage(target_damage)
        # Multi-recipient direct attacks use the same committed attack damage
        # and outgoing-modifier pipeline as the primary. The shared mechanic
        # snapshots recipient IDs at attack start, so death spawns or movement
        # caused by the first recipient cannot retarget an already-fired hit.
        for mechanic in self.mechanics:
            resolve_secondary = getattr(
                mechanic,
                "resolve_secondary_attack_hits",
                None,
            )
            if callable(resolve_secondary):
                resolve_secondary(
                    self,
                    primary_target,
                    damage,
                    battle_state,
                )

        # Hit hooks describe the committed attack, not only primary-target
        # damage. Multi-bolt attacks still resolve their other bolt when an
        # invulnerable primary nullifies its own hit. Individual payloads
        # enforce the recipient's effect guard themselves.
        for mechanic in self.mechanics:
            if mechanic is not exclude_hit_mechanic:
                mechanic.on_attack_hit(self, primary_target)
    
    def apply_stun(
        self,
        duration: float,
        *,
        source_kind: str | None = None,
        affects_hidden: bool = False,
        interrupt_combat: bool = True,
    ) -> None:
        """Apply stun effect for specified duration"""
        if not self.can_receive_effect(
            source_kind,
            affects_hidden=affects_hidden,
        ):
            return
        for mechanic in getattr(self, "mechanics", []):
            blocks_status = getattr(mechanic, "blocks_status_effect", None)
            if callable(blocks_status) and blocks_status(self):
                return
        if self.stun_timer <= 1e-9:
            self._native_moving_when_frozen = bool(
                getattr(self, "_native_natural_movement_active", False)
                or getattr(self, "_movement_target_id", None) is not None
            )
        self.stun_timer = max(self.stun_timer, duration)
        from .ordinary_combat_clock import supported

        pause_ordinary = interrupt_combat and supported(self)
        # Crown towers retain their loaded attack through Zap as well.
        pause_crown = getattr(self, "_crown_tower_slot", None) is not None
        if not interrupt_combat or pause_ordinary or pause_crown:
            # The ordinary native Zap control and Freeze controls drop the
            # lock until thaw while preserving the load and hit timelines.
            self._freeze_target_pause_remaining = max(
                self._freeze_target_pause_remaining, duration,
            )
            # Zap clears the ready-hit latch even when a river jump keeps
            # its charge bank. Landing must not restore an interrupted hit.
            if self._ordinary_force_due:
                self._ordinary_force_due = False
                if self._ordinary_clock is not None:
                    from .ordinary_combat_clock import publish

                    publish(self, self._ordinary_clock)
            if getattr(self, "_has_attacked_once", False) and not getattr(
                self, "_native_natural_movement_active", False,
            ):
                self._attack_windup_active = True
            self.target_id = None
            self._last_combat_target_id = None
            self._movement_target_id = None
            self._combat_target_pending_lethal = False
            if pause_ordinary:
                for mechanic in self.mechanics:
                    handler = getattr(mechanic, "handle_stun", None)
                    if callable(handler):
                        handler(self)
            return
        # River jumpers can be damaged and visually stunned by air-capable
        # payloads, but their in-flight movement state cannot be interrupted.
        # Unsupported weapons defer their legacy interruption until landing.
        # Ordinary weapons already took the clock-preserving pause above.
        if getattr(self, "_river_jump_active", False):
            self._stun_interrupt_deferred_until_landing = True
            return
        self._interrupt_combat_by_stun()

    def _interrupt_combat_by_stun(self) -> None:
        """Reset combat state once stun can interrupt the active movement."""
        # Legacy adapter for special weapons and deferred river-jump stun.
        # Supported ordinary weapons take the clock-preserving pause path.
        # LoadFirstHit uses the serialized reset-when-zapped switch here.
        load_first_hit = bool(
            getattr(getattr(self, "card_stats", None), "load_first_hit", False)
        )
        reload_attack_clock = (
            not load_first_hit
            or LOGIC_LOAD_FIRST_HIT_RESET_TIMER_WHEN_ZAPPED
        )
        self.target_id = None
        self._last_combat_target_id = None
        self._attack_finish_elapsed_ms = 0
        self.reset_attack_windup(
            replacement_cooldown_seconds=(
                self.get_base_attack_interval_seconds()
                if reload_attack_clock
                else self.attack_cooldown
            ),
        )
        self._attack_windup_active = False
        reset_charge = getattr(self, "reset_charge", None)
        if callable(reset_charge):
            reset_charge(interrupted=True)

        # Allow card mechanics to react to stun (e.g., Sparky charge reset).
        for mechanic in getattr(self, "mechanics", []):
            handler = getattr(mechanic, "handle_stun", None)
            if callable(handler):
                handler(self)

    def inherit_freeze_until(
        self,
        expiry_time: float,
        current_time: float,
    ) -> None:
        """Copy one existing Freeze buff onto a newly created character."""
        remaining = max(0.0, float(expiry_time) - float(current_time))
        if remaining <= 1e-9:
            return
        # Freeze is one buff with movement, hit-speed, and spawn-speed axes.
        # A child born after the area's one-time target snapshot inherits the
        # complete remaining buff, not only its combat-stun symptom.
        self.apply_stun(
            remaining,
            source_kind="Freeze",
            affects_hidden=True,
        )
        self.apply_slow(
            remaining,
            0.0,
            source_kind="Freeze",
            affects_hidden=True,
        )
        self.freeze_expiry_time = max(
            self.freeze_expiry_time,
            float(expiry_time),
        )
        
    def apply_slow(
        self,
        duration: float,
        multiplier: float,
        *,
        attack_speed_multiplier: float | None = None,
        spawn_speed_multiplier: float | None = None,
        source_kind: str | None = None,
        affects_hidden: bool = False,
    ) -> None:
        """Apply independently composable movement/attack/spawn slow axes.

        Existing callers pass one multiplier and therefore slow all three
        axes, matching ice effects.  Effects such as Poison and Earthquake can
        explicitly leave attack and spawn speeds unchanged.
        """
        if not self.can_receive_effect(
            source_kind,
            affects_hidden=affects_hidden,
        ):
            return
        for mechanic in getattr(self, "mechanics", []):
            blocks_status = getattr(mechanic, "blocks_status_effect", None)
            if callable(blocks_status) and blocks_status(self):
                return
        movement = max(0.0, float(multiplier))
        attack = movement if attack_speed_multiplier is None else max(0.0, float(attack_speed_multiplier))
        spawn = movement if spawn_speed_multiplier is None else max(0.0, float(spawn_speed_multiplier))
        if hasattr(self, 'speed') and self.original_speed is None:
            self.original_speed = self._unslowed_movement_speed()
        signature = (movement, attack, spawn)
        for index, (remaining, old_movement, old_attack, old_spawn) in enumerate(self._slow_effects):
            if (old_movement, old_attack, old_spawn) == signature:
                self._slow_effects[index] = (
                    max(remaining, float(duration)),
                    old_movement,
                    old_attack,
                    old_spawn,
                )
                break
        else:
            self._slow_effects.append((float(duration), movement, attack, spawn))
        self._recompute_slow_state()

    def apply_periodic_damage(
        self,
        *,
        source_id: int,
        source_kind: str | None,
        duration: float,
        hit_interval: float,
        damage: float,
        hard_duration: float | None = None,
        affects_hidden: bool = False,
    ) -> None:
        """Apply or refresh a periodic buff without resetting its hit phase.

        Native area objects repeatedly refresh one CharacterBuff on each
        target. Reapplication extends that buff's lifetime but preserves its
        target-local hit counter; independently cast areas use distinct source
        IDs and therefore stack.
        """
        if (
            duration <= 0
            or hit_interval <= 0
            or damage <= 0
            or not self.can_receive_effect(
                source_kind,
                affects_hidden=affects_hidden,
            )
        ):
            return
        current = self._periodic_damage_effects.get(source_id)
        if current is None:
            self._periodic_damage_effects[source_id] = PeriodicDamageEffect(
                source_id=source_id,
                source_kind=source_kind,
                remaining=float(duration),
                hit_interval=float(hit_interval),
                time_to_next_hit=float(hit_interval),
                damage=float(damage),
                hard_remaining=(
                    None
                    if hard_duration is None
                    else max(0.0, float(hard_duration))
                ),
                affects_hidden=affects_hidden,
            )
            return

        current.remaining = max(current.remaining, float(duration))
        current.damage = float(damage)
        current.source_kind = source_kind
        current.affects_hidden = affects_hidden
        if hard_duration is not None:
            hard_duration = max(0.0, float(hard_duration))
            current.hard_remaining = (
                hard_duration
                if current.hard_remaining is None
                else min(current.hard_remaining, hard_duration)
            )

    def _update_periodic_damage_effects(self, dt: float) -> None:
        """Tick target-local damage buffs before their source area object."""
        if not self._periodic_damage_effects:
            return
        expired: list[int] = []
        for source_id, effect in list(self._periodic_damage_effects.items()):
            effect.remaining = max(0.0, effect.remaining - dt)
            if effect.hard_remaining is not None:
                effect.hard_remaining = max(0.0, effect.hard_remaining - dt)
            effect.time_to_next_hit -= dt

            # Damage resolves before the zero-duration destruct check on the
            # same component frame, so a hit exactly on either expiry boundary
            # is still committed.
            while effect.time_to_next_hit <= 1e-9 and self.is_alive:
                self.take_damage(
                    effect.damage,
                    source_kind=effect.source_kind,
                    affects_hidden=effect.affects_hidden,
                )
                effect.time_to_next_hit += effect.hit_interval

            if (
                effect.remaining <= 1e-9
                or (
                    effect.hard_remaining is not None
                    and effect.hard_remaining <= 1e-9
                )
                or not self.is_alive
            ):
                expired.append(source_id)

        for source_id in expired:
            self._periodic_damage_effects.pop(source_id, None)

    def _recompute_slow_state(self) -> None:
        self.slow_timer = max((effect[0] for effect in self._slow_effects), default=0.0)
        self.slow_multiplier = min((effect[1] for effect in self._slow_effects), default=1.0)
        self.attack_speed_debuff_multiplier = min(
            (effect[2] for effect in self._slow_effects),
            default=1.0,
        )
        self.spawn_speed_debuff_multiplier = min(
            (effect[3] for effect in self._slow_effects),
            default=1.0,
        )
        if hasattr(self, 'speed') and self.original_speed is not None:
            self.speed = (
                self.original_speed
                * self._movement_debuff_multiplier()
            )
    
    def update_status_effects(self, dt: float) -> None:
        """Update status effect timers"""
        self._update_periodic_damage_effects(dt)
        self._freeze_target_pause_remaining = max(
            0.0, self._freeze_target_pause_remaining - dt,
        )
        if self._freeze_target_pause_remaining <= 1e-9:
            self._freeze_target_pause_remaining = 0.0

        # Update stun timer
        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            if self.stun_timer <= 1e-9:
                self.stun_timer = 0.0

        # Update independently timed slows and recompute the strongest active
        # modifier on each axis.  This prevents a short slow from cancelling a
        # longer overlapping one when it expires.
        if self._slow_effects:
            self._slow_effects = [
                (remaining - dt, movement, attack, spawn)
                for remaining, movement, attack, spawn in self._slow_effects
                if remaining - dt > 1e-9
            ]
            self._recompute_slow_state()
            if not self._slow_effects and hasattr(self, 'speed') and self.original_speed is not None:
                self.speed = self.original_speed * self.movement_mode_multiplier
                self.original_speed = None

        if self._haste_effects:
            self._haste_effects = [
                (remaining - dt, movement, attack, spawn)
                for remaining, movement, attack, spawn in self._haste_effects
                if remaining - dt > 1e-9
            ]
            self._recompute_haste_state()
        elif self.haste_timer > 0:
            # Compatibility for entities restored from older snapshots that
            # predate independently tracked haste sources.
            self.haste_timer = max(0.0, self.haste_timer - dt)
            if self.haste_timer <= 0:
                self.movement_speed_buff_multiplier = 1.0
                self.attack_speed_buff_multiplier = 1.0
                self.spawn_speed_buff_multiplier = 1.0

        # Handle temporary buffs that adjust speed/damage
        if getattr(self, '_buff_active', False):
            if hasattr(self, 'battle_state'):
                if self.battle_state.time >= getattr(self, '_buff_end_time', 0):
                    if hasattr(self, '_original_speed') and self._original_speed is not None:
                        if hasattr(self, 'speed'):
                            self.speed = self._original_speed
                        self._original_speed = None
                    if hasattr(self, '_original_damage') and self._original_damage is not None:
                        self.damage = self._original_damage
                        self._original_damage = None
                    self.attack_speed_buff_multiplier = 1.0
                    self._buff_active = False
                    self._buff_end_time = None

    def get_attack_rate_multiplier(self) -> float:
        """Effective attack rate around the unmodified 100% baseline."""
        return self._native_combat_tick_rate(
            self.attack_speed_debuff_multiplier,
            max(
                self.attack_speed_buff_multiplier,
                self.attack_mode_multiplier,
            ),
        )

    def get_movement_rate_multiplier(self) -> float:
        """Return the composed movement-rate multiplier."""
        return self._compose_speed_modifiers(
            self._movement_debuff_multiplier(),
            self.movement_speed_buff_multiplier,
        )

    def _movement_debuff_multiplier(self) -> float:
        """Return the strongest native negative movement modifier."""
        return min(
            max(0.0, float(self.slow_multiplier)),
            max(0.0, float(self.movement_mode_multiplier)),
        )

    def _unslowed_movement_speed(self) -> float:
        """Recover the active normal/charge speed before character buffs."""
        if self.original_speed is not None:
            return float(self.original_speed)
        debuff = self._movement_debuff_multiplier()
        if debuff > 1e-9:
            return float(self.speed) / debuff
        return float(
            getattr(getattr(self, "card_stats", None), "speed", 0.0)
            or self.speed
        )

    def get_spawn_rate_multiplier(self) -> float:
        """Return the composed production/spawn-rate multiplier."""
        debuff_percent = round(self.spawn_speed_debuff_multiplier * 100.0)
        buff_percent = round(self.spawn_speed_buff_multiplier * 100.0)
        # Native spawners first compose an integer percentage, then consume
        # half of it from their millisecond clock on each 50 ms logic tick.
        combined_percent = max(0, debuff_percent * buff_percent // 100)
        return (combined_percent // 2) / 50.0

    @staticmethod
    def _compose_speed_modifiers(debuff: float, buff: float) -> float:
        """Compose the strongest native positive and negative modifiers.

        Character buffs serialize positive factors (Rage stores 130) and
        negative reductions (ice slow stores -30) separately. The combat
        component clamps the reduction, then multiplies both axes; equal
        30% effects therefore produce 0.70 * 1.30 = 0.91 of base speed.
        """
        return max(0.0, float(debuff) * float(buff))

    @staticmethod
    def _native_scaled_speed(base: float, debuff: float, buff: float) -> int:
        """Apply native integer buff arithmetic to a serialized speed value."""
        base_value = max(0, round(float(base)))
        debuff_percent = max(0, round(float(debuff) * 100.0))
        buff_percent = max(0, round(float(buff) * 100.0))
        buffed = base_value * buff_percent // 100
        return buffed * debuff_percent // 100

    @classmethod
    def _native_combat_tick_rate(cls, debuff: float, buff: float) -> float:
        """Rate produced by the client's integer 50 ms combat-clock update."""
        return cls._native_scaled_speed(50, debuff, buff) / 50.0

    def apply_haste(
        self,
        duration: float,
        movement_multiplier: float,
        attack_speed_multiplier: float,
        spawn_speed_multiplier: float | None = None,
    ) -> None:
        remaining = max(0.0, float(duration))
        if remaining <= 0.0:
            return
        movement = max(0.0, float(movement_multiplier))
        attack = max(0.0, float(attack_speed_multiplier))
        spawn = max(
            0.0,
            float(
                attack_speed_multiplier
                if spawn_speed_multiplier is None
                else spawn_speed_multiplier
            ),
        )
        signature = (movement, attack, spawn)
        for index, (old_remaining, old_movement, old_attack, old_spawn) in enumerate(
            self._haste_effects
        ):
            if (old_movement, old_attack, old_spawn) == signature:
                self._haste_effects[index] = (
                    max(old_remaining, remaining),
                    old_movement,
                    old_attack,
                    old_spawn,
                )
                break
        else:
            self._haste_effects.append((remaining, movement, attack, spawn))
        self._recompute_haste_state()

    def _recompute_haste_state(self) -> None:
        """Expose the strongest live positive modifier on each native axis."""
        self.haste_timer = max(
            (effect[0] for effect in self._haste_effects),
            default=0.0,
        )
        self.movement_speed_buff_multiplier = max(
            (effect[1] for effect in self._haste_effects),
            default=1.0,
        )
        self.attack_speed_buff_multiplier = max(
            (effect[2] for effect in self._haste_effects),
            default=1.0,
        )
        self.spawn_speed_buff_multiplier = max(
            (effect[3] for effect in self._haste_effects),
            default=1.0,
        )

    def get_attack_interval_seconds(self) -> float:
        """Current time between attacks after attack-speed modifiers."""
        hit_speed_ms = getattr(getattr(self, "card_stats", None), "hit_speed", None)
        if not hit_speed_ms:
            return 1.0
        rate_multiplier = max(0.05, self.get_attack_rate_multiplier())
        return (hit_speed_ms / 1000.0) / rate_multiplier

    def get_base_attack_interval_seconds(self) -> float:
        """Return unmodified cooldown work consumed by the attack clock."""
        hit_speed_ms = getattr(getattr(self, "card_stats", None), "hit_speed", None)
        return (hit_speed_ms / 1000.0) if hit_speed_ms else 1.0

    def get_preloaded_attack_time_seconds(self) -> float:
        """Return the smallest attack clock reachable without a target."""
        first_hit_ms = getattr(
            getattr(self, "card_stats", None),
            "first_hit_time",
            0,
        ) or 0
        return first_hit_ms / 1000.0

    def get_post_attack_cooldown_seconds(
        self,
        *,
        payload_discarded: bool = False,
    ) -> float:
        """Return the native cooldown installed after an attack attempt.

        A connected attack resets the full hit cycle.  Native gates retained
        load after a late distance discard behind CharacterData::LoadFirstHit;
        a nonzero LoadTime alone does not opt an ordinary weapon into that
        behavior.  A load-first-hit weapon leaves its already-ready timer
        untouched when the current global is enabled.
        """
        if (
            payload_discarded
            and bool(getattr(self.card_stats, "load_first_hit", False))
            and LOGIC_LOAD_FIRST_HIT_KEEP_LOADED_AFTER_DISCARD
        ):
            return max(0.0, self.attack_cooldown)
        return self.get_base_attack_interval_seconds()

    def advance_attack_clock(self, dt: float, *, target_in_range: bool) -> None:
        """Advance attack work, respecting Clash's finite idle preload.

        An engaged attacker can finish its complete clock.  While walking or
        idle it may only preload the serialized load portion, so it stops at
        the card's first-hit remainder instead of banking an instant attack.
        """
        from .ordinary_combat_clock import advance

        if advance(self, dt, engaged=target_in_range):
            return
        if self.attack_cooldown <= 0:
            return
        if not target_in_range and self._attack_preload_blocked:
            return
        # Native load work uses the component's unscaled time input; attack
        # speed modifiers scale the active hit timeline only. Stun/Freeze
        # guards pause the entire component before this method is called.
        work = dt * self.get_attack_rate_multiplier() if target_in_range else dt
        if target_in_range:
            self.attack_cooldown -= work
            if self.attack_cooldown <= 1e-9:
                # Crown hit timelines retain work beyond a firing boundary.
                # Dropping a slowed shot's remainder can delay a later shot
                # by a frame when the slow expires.
                self.attack_cooldown = (
                    min(0.0, self.attack_cooldown)
                    if self.card_stats and self.card_stats.name in {"Tower", "KingTower"}
                    else 0.0
                )
            return
        self.attack_cooldown = max(
            self.get_preloaded_attack_time_seconds(),
            self.attack_cooldown - work,
        )

    def reset_attack_windup(
        self,
        *,
        retarget: bool = False,
        replacement_cooldown_seconds: float | None = None,
    ) -> None:
        """Restore attack work for a first lock, retarget, or interruption."""
        if self._ordinary_clock is not None:
            from .ordinary_combat_clock import get_clock

            get_clock(self)
        self._attack_finish_elapsed_ms = 0
        self._attack_windup_active = False
        self._resume_pending_hit = False
        timing_field = "retarget_time" if retarget else "first_hit_time"
        first_hit_ms = getattr(getattr(self, "card_stats", None), timing_field, 0) or 0
        self.attack_cooldown = (
            max(0.0, float(replacement_cooldown_seconds))
            if replacement_cooldown_seconds is not None
            else max(self.attack_cooldown, first_hit_ms / 1000.0)
        )
        self._has_attacked_once = False
        if self._ordinary_clock is not None:
            from .ordinary_combat_clock import publish, seed_remaining

            if replacement_cooldown_seconds is not None:
                seed_remaining(self, self._ordinary_clock, self.attack_cooldown)
            else:
                self._ordinary_clock.stop_hit()
                self._ordinary_force_due = False
                self._ordinary_clock.load_remaining_ms = max(
                    self._ordinary_clock.load_remaining_ms,
                    max(0, int(first_hit_ms) - self._ordinary_clock.hit_interval_ms + self._ordinary_clock.load_time_ms),
                )
            publish(self, self._ordinary_clock)

    def _attack_is_due(self) -> bool:
        return self.attack_cooldown <= 0 and (
            self._ordinary_clock is None or self._ordinary_clock_due
        )

    def _complete_attack_clock_cycle(self, *, discarded: bool = False) -> None:
        if self._ordinary_clock is not None:
            from .ordinary_combat_clock import publish

            publish(self, self._ordinary_clock)
        else:
            carry = (
                min(0.0, self.attack_cooldown)
                if self.card_stats and self.card_stats.name in {"Tower", "KingTower"}
                else 0.0
            )
            self.attack_cooldown = self.get_post_attack_cooldown_seconds(
                payload_discarded=discarded,
            ) + carry

    def _advance_acquisition_load(self, target: Optional['Entity'], dt: float) -> None:
        """Finish this frame's passive load before starting a newly acquired hit.

        Native keeps load work separate from its active hit timeline. When a
        target is acquired before loading finishes, both counters advance on
        that transition frame. Fully loaded attacks receive no extra work.
        """
        from .ordinary_combat_clock import get_clock

        if get_clock(self) is not None:
            return
        if (
            target is not None
            and not self._attack_windup_active
            and self.is_within_attack_engagement_reach(target)
            and self.attack_cooldown > self.get_preloaded_attack_time_seconds()
        ):
            self.advance_attack_clock(dt, target_in_range=False)

    def interrupt_by_knockback(self) -> None:
        """Apply the combat interruption shared by all physical pushes."""
        self.interrupt_by_forced_movement(movement_kind="knockback")

    def interrupt_by_forced_movement(
        self,
        *,
        source_kind: str | None = None,
        movement_kind: str,
    ) -> None:
        """Apply combat and special-movement interruption for displacement."""
        charged_attack_was_ready = bool(getattr(self, "is_charging", False))
        if movement_kind == "knockback" and not charged_attack_was_ready:
            from .ordinary_combat_clock import get_clock, stop_hit

            if get_clock(self) is not None:
                # Native physical push stops the hit on its first movement
                # frame, preserving load. Loading continues during the push.
                self._attack_preload_blocked = False
                if self._knockback_target is not None:
                    self._knockback_reset_hit_on_movement = True
                else:
                    self._attack_finish_elapsed_ms = 0
                    self._attack_windup_active = False
                    self._has_attacked_once = False
                    stop_hit(self)
                reset_charge = getattr(self, "reset_charge", None)
                if callable(reset_charge):
                    reset_charge()
                self._notify_forced_movement(source_kind, movement_kind)
                return
        self._attack_finish_elapsed_ms = 0
        self._attack_windup_active = False
        # Physical displacement removes any banked load.  The clock starts at
        # a full hit interval and can preload again only while out of reach.
        # Interrupted charges are the exception: since the October 2025 game
        # fix, their next regular attack uses the card's ordinary first-hit
        # wind-up rather than retaining the charge's instant readiness.
        if charged_attack_was_ready:
            reset_charge = getattr(self, "reset_charge", None)
            if callable(reset_charge):
                reset_charge(interrupted=True)
        else:
            self.attack_cooldown = max(
                self.attack_cooldown,
                self.get_base_attack_interval_seconds(),
            )
            self._attack_preload_blocked = True
        self._has_attacked_once = False
        if not charged_attack_was_ready:
            reset_charge = getattr(self, "reset_charge", None)
            if callable(reset_charge):
                reset_charge()
        self._notify_forced_movement(source_kind, movement_kind)

    def _notify_forced_movement(self, source_kind: str | None, movement_kind: str) -> None:
        """Interrupt special movement even when ordinary weapon load survives."""
        for mechanic in getattr(self, "mechanics", []):
            handler = getattr(mechanic, "on_forced_movement", None)
            if callable(handler):
                handler(self, source_kind, movement_kind)
            if movement_kind != "knockback":
                continue
            handler = getattr(mechanic, "on_knockback", None)
            if callable(handler):
                handler(self)

    def on_combat_target_removed(self, target_id: int) -> None:
        """Release a removed target and preserve native attack-finish work."""
        if self.target_id != target_id:
            return
        self.target_id = None
        self._movement_target_id = None
        retained_pending_target = self._combat_target_pending_lethal
        self._combat_target_pending_lethal = False
        if retained_pending_target:
            # Native attack+0x18 bypasses finish work on target removal.
            # Retained cooldown is preload, not an active hit cycle that may
            # grant the next target the started-projectile range extension.
            self._last_combat_target_id = None
            self._resume_pending_hit = True
            self._attack_windup_active = False
            self._has_attacked_once = False
            if self._ordinary_clock is not None:
                from .ordinary_combat_clock import publish

                self._ordinary_clock.finish_elapsed_ms = 0
                publish(self, self._ordinary_clock)
            return
        stats = self.card_stats
        timeline_started = (
            self._ordinary_clock.hit_timeline_ms > 0
            if self._ordinary_clock is not None
            else self._attack_windup_active or getattr(self, "_has_attacked_once", False)
        )
        if (
            timeline_started
            and int(getattr(stats, "hit_speed", 0) or 0) > 1
            and GLOBAL_ATTACK_FINISH_TIME_MS > 0
            and not getattr(stats, "load_first_hit", False)
            and not getattr(stats, "override_attack_finish_time", False)
            and not getattr(stats, "attack_sequence", None)
        ):
            # Native removal callback installs 1; following ticks add 50 ms.
            self._attack_finish_elapsed_ms = 1
        if self._attack_finish_elapsed_ms == 0:
            self._attack_windup_active = False
            self._has_attacked_once = False
        if self._ordinary_clock is not None:
            from .ordinary_combat_clock import publish

            self._ordinary_clock.finish_elapsed_ms = self._attack_finish_elapsed_ms
            if not self._attack_finish_elapsed_ms:
                self._ordinary_clock.stop_hit()
            publish(self, self._ordinary_clock)

    def _tick_attack_finish(self, dt: float) -> bool:
        if self._attack_finish_elapsed_ms <= 0:
            return False
        self._attack_finish_tick = getattr(self.battle_state, "tick", -1)
        from .ordinary_combat_clock import get_clock, publish

        clock = get_clock(self)
        if clock is None:
            self._attack_finish_elapsed_ms += max(0, logic_time_milliseconds(dt))
            self.advance_attack_clock(dt, target_in_range=False)
        else:
            clock.finish_elapsed_ms = self._attack_finish_elapsed_ms
            clock.advance(
                max(0, logic_time_milliseconds(dt)), 0,
                engaged=False, frozen=self.is_stunned(),
            )
            self._attack_finish_elapsed_ms = clock.finish_elapsed_ms
            publish(self, clock)
        self._movement_target_id = None
        if self._attack_finish_elapsed_ms == 0 or self._attack_finish_elapsed_ms >= GLOBAL_ATTACK_FINISH_TIME_MS:
            self._attack_finish_elapsed_ms = 0
            self._attack_windup_active = False
            self._has_attacked_once = False
            self._last_combat_target_id = None
        # Expiry consumes its own frame; acquisition resumes next frame.
        return True

    def _note_combat_target(self, target: Optional['Entity'], *, preserve_hit: bool = False) -> None:
        """Apply the data-driven delay when an established lock is broken."""
        preserve_hit = bool(
            preserve_hit
            and target is not None
            and self.is_within_attack_engagement_reach(target)
        )
        self._combat_target_pending_lethal = False
        previous = getattr(self, "_last_combat_target_id", None)
        if (
            previous is None
            and target is not None
            and self._ordinary_clock is not None
            and not self.is_within_attack_engagement_reach(target)
        ):
            # Thaw and pending-target removal can retain hit work without a
            # lock. A newly acquired distant target cannot inherit that hit.
            self.reset_attack_windup(retarget=True)
        if self._resume_pending_hit:
            self._resume_pending_hit = False
            if target is not None and self.is_within_attack_engagement_reach(target):
                self._attack_windup_active = True
                preserve_hit = True
        if target is None or previous != target.id:
            self._has_attacked_current_target = False
        if target is None:
            if previous is not None:
                self.reset_attack_windup(retarget=True)
            # Clearing the remembered id lets an idle retarget clock preload;
            # acquiring the eventual target must preserve that progress.
            self._last_combat_target_id = None
            return
        if previous is not None and previous != target.id:
            # Native f5c92c preserves ordinary hit work when the replacement
            # is already in engagement range. Out-of-range replacements still
            # clear the hit; special weapons keep their separate adapters.
            if (
                self._ordinary_clock is not None
                and self.is_within_attack_engagement_reach(target)
            ):
                preserve_hit = True
            # A completed charge can release against a newly acquired target
            # immediately; ordinary retarget wind-up must not erase that hit.
            charged_hit_ready = bool(
                getattr(self, "is_charging", False)
                and self.attack_cooldown <= 0
            )
            if not charged_hit_ready and not preserve_hit:
                self.reset_attack_windup(retarget=True)
        self._last_combat_target_id = target.id
        self._combat_target_pending_lethal = bool(
            self._keeps_target_with_pending_damage()
            and target.is_expected_to_die_from_projectiles()
        )
    
    def is_stunned(self) -> bool:
        """Check if entity is currently stunned"""
        return self.stun_timer > 0

    def get_collision_radius(self) -> float:
        """Return this entity's gameplay collision radius in arena tiles."""
        radius = getattr(getattr(self, "card_stats", None), "collision_radius", None)
        return float(radius or 0.5)

    def intersects_native_area(
        self,
        area_center: Position,
        area_radius: float,
    ) -> bool:
        """Return whether this object's native hitbox intersects a round area.

        ``LogicGameObject::intersects`` performs this test in logic units and
        excludes an exactly tangent perimeter. Characters use a circular
        hitbox. Physical buildings use an axis-aligned square with rounded
        corners, obtained by testing the area's circle against the closest
        point of the building's collision square.
        """
        center_x_units = tiles_to_logic_units(area_center.x)
        center_y_units = tiles_to_logic_units(area_center.y)
        object_x_units = tiles_to_logic_units(self.position.x)
        object_y_units = tiles_to_logic_units(self.position.y)
        area_radius_units = max(0, tiles_to_logic_units(area_radius))
        object_radius_units = max(
            0,
            tiles_to_logic_units(self.get_collision_radius()),
        )

        if getattr(self, "entity_kind", 4) == 1:
            closest_x_units = min(
                object_x_units + object_radius_units,
                max(
                    object_x_units - object_radius_units,
                    center_x_units,
                ),
            )
            closest_y_units = min(
                object_y_units + object_radius_units,
                max(
                    object_y_units - object_radius_units,
                    center_y_units,
                ),
            )
            dx_units = closest_x_units - center_x_units
            dy_units = closest_y_units - center_y_units
            return (
                dx_units * dx_units + dy_units * dy_units
                < area_radius_units * area_radius_units
            )

        dx_units = object_x_units - center_x_units
        dy_units = object_y_units - center_y_units
        combined_radius_units = area_radius_units + object_radius_units
        return (
            dx_units * dx_units + dy_units * dy_units
            < combined_radius_units * combined_radius_units
        )

    def reach_distance_to(self, target: 'Entity', base_range: float) -> float:
        """Center distance at which serialized range reaches a target hitbox."""
        target_radius = (
            target.get_collision_radius()
            if ADD_CHARACTER_RANGE_TO_RADIUS
            else 0.0
        )
        return float(base_range) + target_radius

    def get_effective_attack_range(self) -> float:
        """Native attack range before the target's hitbox is included."""
        attacker_radius = (
            self.get_collision_radius() if ADD_CHARACTER_RANGE_TO_RADIUS else 0.0
        )
        return float(self.range) + attacker_radius

    def get_effective_sight_range(self) -> float:
        """Native sight radius includes the observing character's body."""
        radius = (
            self.get_collision_radius()
            if ADD_CHARACTER_RANGE_TO_RADIUS
            else 0.0
        )
        return float(self.sight_range) + radius

    @staticmethod
    def native_target_distance_from(
        origin: Position,
        target: 'Entity',
    ) -> float:
        """Return native target distance from an arbitrary planar origin."""
        dx = target.position.x - origin.x
        dy = target.position.y - origin.y
        distance_sq = dx * dx + dy * dy
        discount_sq_units = max(
            0,
            int(
                getattr(
                    target,
                    "_native_target_distance_discount_sq_units",
                    0,
                )
                or 0
            ),
        )
        return math.sqrt(
            max(0.0, distance_sq - discount_sq_units / 1_000_000.0)
        )

    def native_target_distance_to(self, target: 'Entity') -> float:
        """Return native target distance from this entity's current center."""
        return self.native_target_distance_from(self.position, target)

    def native_dash_range_edge_distance(
        self,
        target: 'Entity',
        minimum_range: float,
        maximum_range: float,
    ) -> float | None:
        """Return target-edge distance inside the native dash range band.

        ``LogicCombatComponent::canDashToTarget`` passes ``DashMaxRange`` as
        the outer radius to ``isInRangeAccurate``. For the inner radius it
        passes ``DashMinRange + attacker CollisionRadius``; the shared range
        helper then adds the target radius to both bounds. Consequently the
        maximum is measured from the attacker center to the target hitbox,
        while the minimum is the true edge-to-edge gap between both bodies.
        Native compares the squared integer distances inclusively.
        """
        self_x_units = tiles_to_logic_units(self.position.x)
        self_y_units = tiles_to_logic_units(self.position.y)
        target_x_units = tiles_to_logic_units(target.position.x)
        target_y_units = tiles_to_logic_units(target.position.y)
        dx_units = target_x_units - self_x_units
        dy_units = target_y_units - self_y_units
        distance_sq_units = max(
            0,
            dx_units * dx_units
            + dy_units * dy_units
            - max(
                0,
                int(
                    getattr(
                        target,
                        "_native_target_distance_discount_sq_units",
                        0,
                    )
                    or 0
                ),
            ),
        )
        target_radius_units = tiles_to_logic_units(target.get_collision_radius())
        inner_radius_units = (
            tiles_to_logic_units(minimum_range)
            + tiles_to_logic_units(self.get_collision_radius())
            + target_radius_units
        )
        outer_radius_units = (
            tiles_to_logic_units(maximum_range)
            + target_radius_units
        )
        if not (
            inner_radius_units * inner_radius_units
            <= distance_sq_units
            <= outer_radius_units * outer_radius_units
        ):
            return None
        return self.native_target_distance_to(target) - target.get_collision_radius()

    def is_within_sight(self, target: 'Entity') -> bool:
        target_name = getattr(getattr(target, "card_stats", None), "name", "")
        is_crown_tower = (
            target_name in {"Tower", "KingTower"}
            or bool(getattr(target, "_is_king_tower", False))
        )
        target_visibility_extension_units = (
            EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS
            if is_crown_tower
            else (
                EXTRA_SIGHT_RANGE_TO_BUILDING
                if isinstance(target, Building)
                else 0
            )
        )
        target_visibility_extension = (
            target_visibility_extension_units / 1000.0
        )
        sight_reach = (
            self.reach_distance_to(target, self.get_effective_sight_range())
            + target_visibility_extension
        )
        if (
            self.native_target_distance_to(target)
            > sight_reach + GEOMETRY_BOUNDARY_EPSILON
        ):
            return False

        self_name = getattr(getattr(self, "card_stats", None), "name", "")
        if self_name in {"Tower", "KingTower"} or target_name in {
            "Tower",
            "KingTower",
        }:
            return True

        # Moving characters use a directionally clipped circle. SightClip
        # cuts the rear (with a native one-tile default) while SightClipSide
        # cuts both lateral edges; forward sight retains the radial reach.
        card_stats = getattr(self, "card_stats", None)
        backward_clip = float(getattr(card_stats, "sight_clip", 0.0) or 0.0)
        side_clip = float(getattr(card_stats, "sight_clip_side", 0.0) or 0.0)
        dx = target.position.x - self.position.x
        dy = target.position.y - self.position.y
        if (
            side_clip > 0.0
            and abs(dx)
            > max(0.0, sight_reach - side_clip) + GEOMETRY_BOUNDARY_EPSILON
        ):
            return False
        if backward_clip > 0.0:
            forward_delta = dy if self.player_id == 0 else -dy
            if (
                forward_delta
                < -max(0.0, sight_reach - backward_clip)
                - GEOMETRY_BOUNDARY_EPSILON
            ):
                return False
        return True

    def is_within_attack_reach(self, target: 'Entity') -> bool:
        return self.native_target_distance_to(target) <= (
            self.reach_distance_to(target, self.get_effective_attack_range())
            + GEOMETRY_BOUNDARY_EPSILON
        )

    def get_attack_approach_range_reduction(self, target: 'Entity') -> float:
        """Return the data-driven range reduction used while approaching.

        Native combat asks mechanics with a continuous damage channel to walk
        500 logic units closer before entering their attack state. Once the
        channel is connected, the ordinary serialized range applies again.
        Keeping this as a mechanic capability also covers future mobile
        continuous-damage characters without naming Inferno Dragon here.
        """
        reduction = 0.0
        for mechanic in self.mechanics:
            resolver = getattr(
                mechanic,
                "attack_approach_range_reduction",
                None,
            )
            if callable(resolver):
                reduction = max(
                    reduction,
                    float(resolver(self, target) or 0.0),
                )
        return reduction

    def is_within_attack_engagement_reach(self, target: 'Entity') -> bool:
        """Return whether combat may enter or remain in its attack state."""
        effective_range = max(
            0.0,
            self.get_effective_attack_range() - self.get_attack_approach_range_reduction(target),
        )
        return self.native_target_distance_to(target) <= (
            self.reach_distance_to(target, effective_range)
            + GEOMETRY_BOUNDARY_EPSILON
        )

    def has_attack_projectile_definition(self) -> bool:
        """Return whether serialized character data defines an attack projectile.

        Native target preservation checks the character's projectile pointer
        directly.  It does not depend on the Python attack implementation:
        payload troops may resolve that projectile through a mechanic while
        still receiving the same in-progress target leash.
        """
        return bool(
            getattr(getattr(self, "card_stats", None), "projectile_data", None)
        )

    def has_started_projectile_hit_cycle(self) -> bool:
        """Return the native projectile target-preservation phase.

        LogicCharacter checks ``hitTimer % HitSpeed > 50``.  The simulator
        stores remaining attack work instead of the accumulated native timer,
        so negating the remaining milliseconds modulo HitSpeed recovers the
        same phase.  Retarget clocks longer than one cycle consequently map
        back to phase zero, matching the native integer remainder.
        """
        # An interrupted ordinary cycle may retain cooldown work after its
        # hit timeline resets. That work must not grant a started-hit leash.
        if self._ordinary_clock is not None and self._ordinary_clock.hit_timeline_ms == 0:
            return False
        # A finite first-hit remainder is an idle preload, not a started
        # native hit timeline. The reference keeps that timeline at zero
        # while initially approaching (e.g. Baby Dragon ticks112..132).
        if not (
            getattr(self, "_attack_windup_active", False)
            or getattr(self, "_has_attacked_once", False)
        ):
            return False
        if (
            not COMBAT_CMP_USE_HIT_STARTED
            or not self.has_attack_projectile_definition()
        ):
            return False
        hit_speed_ms = int(
            getattr(getattr(self, "card_stats", None), "hit_speed", 0) or 0
        )
        if hit_speed_ms <= 0:
            return False
        remaining_ms = logic_time_milliseconds(
            max(0.0, float(self.attack_cooldown))
        )
        hit_phase_ms = (-remaining_ms) % hit_speed_ms
        return hit_phase_ms > 50

    def is_within_target_keep_reach(self, target: 'Entity') -> bool:
        """Return whether native combat retains its existing target lock."""
        # The 25-unit global applies to ordinary character objects with a
        # hitpoint component. Ephemeral zero-HP combat objects do not receive
        # it.
        extension = (
            LOGIC_RANGE_EXTENSION_TO_KEEP_TARGET / 1000.0
            if self.max_hitpoints > 0 and self.entity_kind != 1
            else 0.0
        )
        # LOGIC_PRESERVE_TARGET_IF_HIT_STARTED replaces that margin with 500
        # units only when character data has an attack projectile and the
        # current hit cycle has already started.
        if (
            LOGIC_PRESERVE_TARGET_IF_HIT_STARTED
            and self.has_started_projectile_hit_cycle()
        ):
            extension = STARTED_ATTACK_KEEP_RANGE_EXTENSION
        return self.native_target_distance_to(target) <= (
            self.reach_distance_to(target, self.get_effective_attack_range())
            + extension
            + GEOMETRY_BOUNDARY_EPSILON
        )

    def is_within_attack_clock_reach(self, target: 'Entity') -> bool:
        """Return whether the current native attack cycle may keep advancing.

        A new attack must enter the ordinary engagement boundary. Native
        combat lets a started hit continue outside that boundary; target
        validation and the final payload-distance guard remain independent.
        """
        if self._attack_windup_active:
            clock = self._ordinary_clock
            # Native f617c0..f617d0 tests hitTimer % HitSpeed > 50.
            # A prior cycle's windup latch must not commit the next cycle
            # at phase0/50. Load remaining is an independent clock.
            if clock is None or clock.hit_timeline_ms % clock.hit_interval_ms > 50:
                return True
        if (
            LOGIC_PRESERVE_TARGET_IF_HIT_STARTED
            and self.has_started_projectile_hit_cycle()
        ):
            return self.is_within_target_keep_reach(target)
        return self.is_within_attack_engagement_reach(target)

    def should_cancel_committed_hit(self, target: 'Entity') -> bool:
        """Return whether the native hit-frame distance guard drops payload.

        This is separate from target retention. A target may be valid when
        the attack clock commits and then move during attack-start mechanics;
        the shared combat component performs one final, wider intersection
        test immediately before creating direct damage or a projectile.
        """
        if not LOGIC_CANCEL_HIT_FROM_LONG_DISTANCE:
            return False

        # Native consults this compatibility global only in the no-projectile
        # branch and only for CharacterData::AreaDamageRadius.  A projectile's
        # own splash radius must not exempt its launch from the ordinary
        # committed-hit discard when the global is disabled.
        direct_area_radius_units = float(
            getattr(getattr(self, "card_stats", None), "area_damage_radius", 0)
            or 0
        )
        if (
            direct_area_radius_units > 0.0
            and not self.has_attack_projectile_definition()
            and not LOGIC_ALLOW_DISCARD_HIT_ON_AREA_DAMAGE
        ):
            return False

        stats = getattr(self, "card_stats", None)
        serialized_speed = float(getattr(stats, "speed", 0.0) or 0.0)
        if serialized_speed <= 0.0:
            return False

        raw = getattr(stats, "_raw_entry", {}) or {}
        character_data = raw.get("summonCharacterData", {}) or {}
        if float(character_data.get("dashCooldown", 0.0) or 0.0) > 0.0:
            return False

        # Native f5f298 uses f5d6a4, whose range already includes the
        # attacker's collision radius under ADD_CHARACTER_RANGE_TO_RADIUS.
        effective_range = max(
            0.0,
            self.get_effective_attack_range() - self.get_attack_approach_range_reduction(target),
        )
        hit_reach = (
            effective_range
            + LOGIC_CANCEL_HIT_FROM_LONG_DISTANCE_RANGE / 1000.0
            + target.get_collision_radius()
        )
        return self.position.distance_to(target.position) > (
            hit_reach + GEOMETRY_BOUNDARY_EPSILON
        )

    def can_attack_target(
        self,
        target: 'Entity',
        *,
        is_current_target: bool = False,
    ) -> bool:
        """Check if this entity can attack the target"""
        if getattr(target, "_hidden_building", False):
            return False
        if not self._is_valid_target(
            target,
            is_current_target=is_current_target,
        ):
            return False
        if (
            bool(
                getattr(
                    getattr(self, "card_stats", None),
                    "targets_only_buildings",
                    False,
                )
            )
            and not is_native_building_target(target)
        ):
            return False

        if is_airborne_target(target) and not self._can_attack_air():
            return False
        if (not is_airborne_target(target)) and not self._can_attack_ground():
            return False

        return self.is_within_attack_reach(target)

    def can_affect_target_plane(self, target: 'Entity') -> bool:
        """Check attack allegiance/type/plane eligibility without range or lockability.

        Splash and secondary payloads can hit cloaked units and extend beyond
        the attacker's acquisition range.  They still obey the original
        attack's air/ground plane, while the recipient's own effect guards
        decide invulnerability (for example a dashing Bandit or hidden Tesla).
        """
        if (
            target.player_id == self.player_id
            or not target.is_alive
            or getattr(target, "entity_kind", 4) in {2, 3}
        ):
            return False
        if is_airborne_target(target):
            return self._can_attack_air()
        return self._can_attack_ground()

    def is_expected_to_die_from_projectiles(self) -> bool:
        """Return whether committed, homing damage already defeats this unit.

        Clash reserves lethal projectile damage before impact so towers and
        troops can move to another target instead of wasting attacks. Native
        LogicObject bookkeeping aggregates the committed damage, but gates
        the entire aggregate on the greatest remaining projectile duration.
        A live shield makes HitpointComponent::isEnoughToKill false regardless
        of how many shield-breaking hits are already in flight.
        """
        battle_state = getattr(self, "battle_state", None)
        if battle_state is None:
            return False

        # A depleted target remains resident through the component phase.
        # Its committed arrows still count: clearing this result at zero HP
        # loses the observer's pending-target latch before removal cleanup.
        # LOGIC_PENDING_DAMAGE_IGNORE_IF_DURATION_LESS is 600 ms in the
        # current globals. Native target validation uses an inclusive <=
        # comparison against the target-owned remaining duration value.
        if (
            self._pending_projectile_max_duration_ms
            > LOGIC_PENDING_DAMAGE_IGNORE_IF_DURATION_LESS
        ):
            return False

        pending_damage = 0.0
        for entity in battle_state.entities.values():
            if entity.is_alive and getattr(entity, "_self_projectile_launched", False):
                for mechanic in entity.mechanics:
                    reservation = getattr(mechanic, "pending_damage_against", None)
                    if callable(reservation):
                        pending_damage += reservation(entity, self)
            expected_damage = getattr(entity, "expected_damage_against", None)
            if not callable(expected_damage) or not entity.is_alive:
                continue
            if not bool(getattr(entity, "reserves_pending_damage", False)):
                continue
            if getattr(entity, "primary_target", None) is not self:
                continue
            damage = expected_damage(self)
            if damage <= 0:
                continue
            pending_damage += damage
        if pending_damage <= 0:
            return False

        for mechanic in getattr(self, "mechanics", []):
            if float(getattr(mechanic, "current_shield", 0.0) or 0.0) > 0:
                return False
        return pending_damage >= float(self.hitpoints)

    def ignores_targets_with_pending_projectile_damage(self) -> bool:
        """Whether this attacker's weapon skips lethally reserved targets.

        Clash gates pending-damage target rejection on the attacking
        character having a projectile definition.  Melee units therefore
        keep their current victim even when an allied shot is already in
        flight, while ranged attackers can commit their next shot elsewhere.
        """
        return bool(getattr(getattr(self, "card_stats", None), "projectile_data", None))

    def _tick_pending_projectile_duration(self, dt: float) -> None:
        # LogicCharacter::tick, f1a778-f1a794 in the pinned native engine.
        self._pending_projectile_max_duration_ms = max(
            0,
            self._pending_projectile_max_duration_ms
            - max(0, logic_time_milliseconds(dt)),
        )

    def _keeps_target_with_pending_damage(self) -> bool:
        return bool(
            CURRENT_TARGET_IGNORES_PENDING_DAMAGE
            and self._has_attacked_current_target
            and getattr(self.card_stats, "keep_target_with_pending_damage", True)
            and self.ignores_targets_with_pending_projectile_damage()
        )

    def _retains_depleted_combat_target(self, target: 'Entity') -> bool:
        """Retain engaged locks through death or launch until phase cleanup."""
        # Lethal projectile reservations still reject a resident depleted
        # target when this observer has not earned the keep-target latch.
        if (
            self.ignores_targets_with_pending_projectile_damage()
            and not self._keeps_target_with_pending_damage()
            and target.is_expected_to_die_from_projectiles()
        ):
            return False
        battle = getattr(self, "battle_state", None)
        return bool(
            target.id == self.target_id
            and (
                not target.is_alive
                or (
                    getattr(target, "_self_projectile_launched", False)
                    and getattr(target, "_self_projectile_launch_tick", -1)
                    == getattr(battle, "tick", -2)
                )
            )
            and self.id in getattr(battle, "_combat_phase_eligible_ids", ())
            and getattr(battle, "entities", {}).get(target.id) is target
            and (
                self.entity_kind == 1
                or (
                    self.has_attack_projectile_definition()
                    and (
                        self._ordinary_clock is None
                        or self._ordinary_clock.hit_timeline_ms > 0
                    )
                )
                # Native Goblins keep both due and non-due cycles when their
                # depleted victim remains in range. The out-of-range Skeleton
                # observer instead releases its lock during this component.
                or self.is_within_target_keep_reach(target)
            )
        )

    def _pending_damage_retargets_hit(self, target: Optional['Entity']) -> bool:
        return bool(
            target is not None
            and target.is_targetable_by(self.player_id)
            and self.ignores_targets_with_pending_projectile_damage()
            and not self._keeps_target_with_pending_damage()
            and target.is_expected_to_die_from_projectiles()
        )

    def _is_valid_target(
        self,
        entity: 'Entity',
        *,
        is_current_target: bool = False,
    ) -> bool:
        """Check if entity can be targeted (excludes spell entities)"""
        if is_current_target and self._retains_depleted_combat_target(entity):
            return True
        if not entity.is_targetable_by(self.player_id):
            return False
        if (
            self.ignores_targets_with_pending_projectile_damage()
            and entity.is_expected_to_die_from_projectiles()
            and not (is_current_target and self._keeps_target_with_pending_damage())
        ):
            return False
        for mechanic in self.mechanics:
            allows_target = getattr(mechanic, "allows_target", None)
            if callable(allows_target) and allows_target(self, entity) is False:
                return False
        return True

    def get_nearest_target(
        self,
        entities: Dict[int, 'Entity'],
        *,
        include_crown_fallback: bool = True,
    ) -> Optional['Entity']:
        """Find nearest valid target with priority rules"""

        # Eligible targets in sight compete by distance.  Crown towers are an
        # infinite-sight fallback objective, not a category preference.
        building_targets = []
        troop_targets = []

        # Check if this unit can only target buildings
        targets_only_buildings = (hasattr(self, 'card_stats') and
                                self.card_stats and
                                getattr(self.card_stats, 'targets_only_buildings', False))

        # Check what this unit can attack
        can_attack_air = self._can_attack_air()
        can_attack_ground = self._can_attack_ground()

        battle_state = getattr(self, "battle_state", None)
        if (
            battle_state is not None
            and getattr(battle_state, "fast_path", False)
            and getattr(battle_state, "entities", None) is entities
            and hasattr(battle_state, "get_fast_target_cache")
        ):
            fast_target = self._get_nearest_target_vectorized(
                battle_state=battle_state,
                targets_only_buildings=targets_only_buildings,
                can_attack_air=can_attack_air,
                can_attack_ground=can_attack_ground,
                # The live-object cache omits depleted Crowns. Resolve
                # fallback navigation through the resident collection below.
                include_crown_fallback=False,
            )
            if fast_target is not None and self._is_valid_target(fast_target):
                return fast_target

        candidate_entities = entities.values()
        if (
            battle_state is not None
            and getattr(battle_state, "fast_path", False)
            and getattr(battle_state, "entities", None) is entities
            and hasattr(battle_state, "iter_entities_in_radius")
        ):
            query_radius = (
                self.get_effective_sight_range()
                + getattr(battle_state, "_max_target_collision_radius", 0.5)
                + 1.0
            )
            candidate_entities = battle_state.iter_entities_in_radius(self.position, query_radius)

        for entity in candidate_entities:
            # Only check if entity is valid target (excludes spell entities)
            if not self._is_valid_target(entity):
                continue

            # Additional safety: never target spell entities explicitly by class types
            if getattr(entity, "entity_kind", 4) in {2, 3}:
                continue
                
            distance = self.native_target_distance_to(entity)
            
            # Check air targeting rules
            if is_airborne_target(entity) and not can_attack_air:
                continue  # Skip air units if we can't attack air
            if (not is_airborne_target(entity)) and not can_attack_ground:
                continue  # Skip ground units if we can't attack ground
            
            # Only consider targets within sight range for troops vs troops
            if is_native_building_target(entity):
                # Buildings primarily require sight-range aggro.
                # Crown towers are kept as fallback objectives so building-targeting
                # troops still path across the map when nothing is in sight.
                if self.is_within_sight(entity):
                    building_targets.append((entity, distance))
            else:
                # For troop targets, only consider if within sight range
                if self.is_within_sight(entity):
                    # Skip troops if we only target buildings
                    if not targets_only_buildings:
                        troop_targets.append((entity, distance))
        
        def _fallback_crown_targets() -> list[tuple[Entity, float]]:
            towers: list[tuple[Entity, float]] = []
            # Native fallback Crown slots survive HP depletion until object
            # removal. Normal in-sight selection above still requires a live
            # target. This distinction matters when a preceding attacker
            # destroys a Crown during the current combat phase.
            candidates = entities.values()
            for entity in candidates:
                # The accelerated building cache is owned by the live
                # BattleState, while callers may intentionally ask this
                # entity to select from a smaller/replaced collection (state
                # restoration and isolated interaction probes both do this).
                # A cached object is eligible only when that exact object is
                # still present in the collection being queried. Comparing
                # identity also prevents an old tower with a reused ID from
                # leaking into the restored state.
                if entities.get(entity.id) is not entity:
                    continue
                if not isinstance(entity, Building):
                    continue
                resident_crown = (
                    entity.player_id != self.player_id
                    and not entity.is_alive
                    and getattr(entity.card_stats, "name", None) in {"Tower", "KingTower"}
                    and battle_state is not None
                    and self.id in getattr(battle_state, "_combat_phase_eligible_ids", ())
                    and battle_state.entities.get(entity.id) is entity
                )
                if not self._is_valid_target(entity) and not resident_crown:
                    continue
                if is_airborne_target(entity) and not can_attack_air:
                    continue
                if (not is_airborne_target(entity)) and not can_attack_ground:
                    continue
                building_name = getattr(getattr(entity, "card_stats", None), "name", "")
                is_crown_tower = (
                    building_name in {"Tower", "KingTower"}
                    or bool(getattr(entity, "_is_king_tower", False))
                )
                if not is_crown_tower:
                    continue
                towers.append((entity, self.native_target_distance_to(entity)))
            preferred = self._preferred_fallback_crown_targets(
                [entity for entity, _ in towers]
            )
            preferred_ids = {entity.id for entity in preferred}
            return [item for item in towers if item[0].id in preferred_ids]

        # Choose targets based on targeting rules
        if targets_only_buildings:
            in_sight_targets = building_targets
        else:
            in_sight_targets = troop_targets + building_targets
        targets = (
            in_sight_targets
            if in_sight_targets
            else (
                _fallback_crown_targets()
                if include_crown_fallback
                else []
            )
        )
        
        if not targets:
            return None
        return self._select_first_nearest_target(targets)

    def _preferred_fallback_crown_targets(
        self,
        crown_towers: list['Entity'],
    ) -> list['Entity']:
        """Choose native fallback Crown objectives from current globals."""
        princess_towers = [
            tower
            for tower in crown_towers
            if getattr(getattr(tower, "card_stats", None), "name", "") == "Tower"
        ]
        king_towers = [
            tower
            for tower in crown_towers
            if (
                getattr(getattr(tower, "card_stats", None), "name", "")
                == "KingTower"
                or bool(getattr(tower, "_is_king_tower", False))
            )
        ]
        if not princess_towers:
            return king_towers
        if not king_towers:
            return princess_towers

        if LOGIC_XPOS_BASED_TOWER_TARGETING:
            # Standard battle f5df40 starts with the enemy King. f5e74c
            # chooses one Princess by x, subject to lane/age guards, then
            # f5e5a4 compares its approximate distance against the King's
            # exact squared distance. The Princess-default flag does not
            # remove the King from consideration.
            x = tiles_to_logic_units(self.position.x)
            y = tiles_to_logic_units(self.position.y)

            def squared_distance(tower):
                dx = tiles_to_logic_units(tower.position.x) - x
                dy = tiles_to_logic_units(tower.position.y) - y
                return dx * dx + dy * dy

            king = min(king_towers, key=squared_distance)
            lane = int(getattr(self, "_native_lane_id", 0) or 0)
            princess = None
            closest_x = (1 << 31) - 1
            for tower in princess_towers:
                same_lane = lane == int(getattr(tower, "_native_lane_id", 0) or 0)
                if not same_lane and (
                    self._native_deployed_elapsed_ms < 500
                    or len(princess_towers) == 1
                ):
                    continue
                dx = abs(tiles_to_logic_units(tower.position.x) - x)
                if dx < closest_x:
                    closest_x, princess = dx, tower
            if princess is not None:
                dx = abs(tiles_to_logic_units(princess.position.x) - x)
                dy = abs(tiles_to_logic_units(princess.position.y) - y)
                distance = max(dx, dy) + ((53 * min(dx, dy)) >> 7)
                if distance * distance < squared_distance(king):
                    return [princess]
            return [king]

        # Compatibility path for non-current globals. The standard pinned
        # runtime exercises the x-based branch above.
        fallback_kings = king_towers

        lane_id = int(getattr(self, "_native_lane_id", 0) or 0)
        if lane_id <= 0:
            return princess_towers + fallback_kings
        same_lane = [
            tower
            for tower in princess_towers
            if int(getattr(tower, "_native_lane_id", 0) or 0) == lane_id
        ]
        if same_lane:
            return same_lane + fallback_kings
        return princess_towers + fallback_kings

    def _target_tie_break_key(self, target: 'Entity') -> tuple[float, float, int]:
        """Return a deterministic player-relative order for non-combat effects."""
        direction = 1.0 if self.player_id == 0 else -1.0
        return (
            direction * (target.position.x - 9.0),
            direction * (target.position.y - 16.0),
            target.id,
        )

    def _select_nearest_target(
        self,
        candidates: list[tuple['Entity', float]],
    ) -> Optional['Entity']:
        """Choose a nearest target for effect mechanics with symmetric ties."""
        if not candidates:
            return None
        minimum = min(distance for _, distance in candidates)
        tied = [
            target
            for target, distance in candidates
            if distance <= minimum + TARGET_DISTANCE_TIE_EPSILON
        ]
        return min(tied, key=self._target_tie_break_key)

    def _select_spatial_character_tie(
        self, candidates: list[tuple['Entity', float]], selected: 'Entity',
    ) -> 'Entity':
        """Resolve exact character ties in native spatial-query order."""
        minimum = next(distance for entity, distance in candidates if entity is selected)
        tied = {
            entity.id: entity for entity, distance in candidates
            if distance == minimum and not is_native_building_target(entity)
        }
        battle = getattr(self, "battle_state", None)
        if len(tied) < 2 or battle is None:
            return selected
        from .native_spatial import NativeAvoidanceGrid

        grid = getattr(battle, "_native_avoidance_grid", None)
        if grid is None:
            grid = NativeAvoidanceGrid(battle.entities.values())
        radius = tiles_to_logic_units(self.get_effective_sight_range()) + max(
            EXTRA_SIGHT_RANGE_TO_BUILDING, EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS,
        )
        for entity in grid.query(
            tiles_to_logic_units(self.position.x),
            tiles_to_logic_units(self.position.y), radius,
        ):
            if entity.id in tied:
                return tied[entity.id]
        return selected

    def _select_first_nearest_target(
        self,
        candidates: list[tuple['Entity', float]],
    ) -> Optional['Entity']:
        """Choose the combat target with the current native tie rules."""
        if not candidates:
            return None
        # LogicCombatComponent replaces its current best only for a strictly
        # smaller adjusted distance at the same target priority. Ordinary
        # character ties therefore retain spatial-query encounter order. Current globals
        # make the closest-building iterator owner-relative, however, so an
        # equal building tie rotates with the player's arena perspective.
        selected, minimum = min(candidates, key=lambda item: item[1])
        if not is_native_building_target(selected):
            return self._select_spatial_character_tie(candidates, selected)
        if not LOGIC_SYMMETRIC_CLOSEST_BUILDING_ITERATION:
            return selected
        tied_buildings = [
            target
            for target, distance in candidates
            if (
                is_native_building_target(target)
                and distance <= minimum + TARGET_DISTANCE_TIE_EPSILON
            )
        ]
        return min(tied_buildings, key=self._target_tie_break_key)

    def _get_nearest_target_vectorized(
        self,
        *,
        battle_state: "BattleState",
        targets_only_buildings: bool,
        can_attack_air: bool,
        can_attack_ground: bool,
        include_crown_fallback: bool = True,
    ) -> Optional["Entity"]:
        (
            target_entities,
            pos_x,
            pos_y,
            player,
            is_air,
            is_building,
            is_building_target,
            is_crown,
            is_targetable,
            stealth_until,
            collision_radius,
            target_distance_discount_sq,
        ) = battle_state.get_fast_target_cache()
        if len(target_entities) == 0:
            return None

        valid = (player != self.player_id) & is_targetable
        if not can_attack_air:
            valid &= ~is_air
        if not can_attack_ground:
            valid &= is_air

        if self.ignores_targets_with_pending_projectile_damage():
            pending_valid = np.fromiter(
                (
                    not entity.is_expected_to_die_from_projectiles()
                    for entity in target_entities
                ),
                dtype=np.bool_,
                count=len(target_entities),
            )
            valid &= pending_valid

        now_ms = logic_time_milliseconds(battle_state.time)
        if stealth_until.size:
            valid &= stealth_until <= now_ms
        if not np.any(valid):
            return None

        dx = pos_x - float(self.position.x)
        dy = pos_y - float(self.position.y)
        dist2 = np.maximum(
            0.0,
            dx * dx + dy * dy - target_distance_discount_sq,
        )
        # Match the scalar distance calculation and native first-candidate
        # retention. ``argmin`` returns the first minimum in cache order.
        distance = np.sqrt(dist2)
        target_radius = (
            collision_radius
            if ADD_CHARACTER_RANGE_TO_RADIUS
            else np.zeros_like(collision_radius)
        )
        building_extension = np.where(
            is_crown,
            EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS,
            np.where(is_building, EXTRA_SIGHT_RANGE_TO_BUILDING, 0),
        ).astype(np.float64) / 1000.0
        sight_reach = self.get_effective_sight_range() + target_radius + building_extension
        in_sight = distance <= sight_reach + GEOMETRY_BOUNDARY_EPSILON
        card_stats = getattr(self, "card_stats", None)
        backward_clip = float(getattr(card_stats, "sight_clip", 0.0) or 0.0)
        side_clip = float(getattr(card_stats, "sight_clip_side", 0.0) or 0.0)
        if side_clip > 0.0:
            in_sight &= is_crown | (
                np.abs(dx)
                <= np.maximum(0.0, sight_reach - side_clip)
                + GEOMETRY_BOUNDARY_EPSILON
            )
        if backward_clip > 0.0:
            forward_delta = dy if self.player_id == 0 else -dy
            in_sight &= is_crown | (
                forward_delta
                >= -np.maximum(0.0, sight_reach - backward_clip)
                - GEOMETRY_BOUNDARY_EPSILON
            )
        troop_targets = valid & (~is_building) & in_sight
        building_targets = valid & is_building_target & in_sight
        fallback_crown_targets = valid & is_building & is_crown

        in_sight_targets = (
            building_targets
            if targets_only_buildings
            else (troop_targets | building_targets)
        )
        chosen = np.zeros_like(valid)
        ordered_candidates: np.ndarray | None = None
        if np.any(in_sight_targets):
            chosen = in_sight_targets
            # The scalar/native candidate collection visits targetable
            # characters before targetable buildings. At an exactly equal
            # adjusted distance, stable first-candidate retention therefore
            # chooses the character even when an older building occupies an
            # earlier object/cache slot.
            if not targets_only_buildings:
                ordered_candidates = np.concatenate(
                    (
                        np.flatnonzero(troop_targets),
                        np.flatnonzero(building_targets),
                    )
                )
        elif include_crown_fallback:
            fallback_indices = np.flatnonzero(fallback_crown_targets)
            preferred = self._preferred_fallback_crown_targets(
                [target_entities[int(index)] for index in fallback_indices]
            )
            preferred_ids = {entity.id for entity in preferred}
            chosen = np.zeros_like(fallback_crown_targets)
            for index in fallback_indices:
                if target_entities[int(index)].id in preferred_ids:
                    chosen[int(index)] = True
        if not np.any(chosen):
            return None

        candidates = (
            ordered_candidates
            if ordered_candidates is not None
            else np.flatnonzero(chosen)
        )
        idx = int(candidates[int(np.argmin(distance[candidates]))])
        selected = target_entities[idx]
        if not is_native_building_target(selected):
            tied_candidates = [
                (target_entities[int(i)], float(distance[int(i)]))
                for i in candidates if distance[int(i)] == distance[idx]
            ]
            return self._select_spatial_character_tie(tied_candidates, selected)
        if (
            LOGIC_SYMMETRIC_CLOSEST_BUILDING_ITERATION
            and is_native_building_target(selected)
        ):
            minimum = float(distance[idx])
            tied_indices = [
                int(candidate_index)
                for candidate_index in candidates
                if (
                    is_native_building_target(
                        target_entities[int(candidate_index)]
                    )
                    and float(distance[int(candidate_index)])
                    <= minimum + TARGET_DISTANCE_TIE_EPSILON
                )
            ]
            idx = min(
                tied_indices,
                key=lambda candidate_index: self._target_tie_break_key(
                    target_entities[candidate_index]
                ),
            )
        return target_entities[idx]
    
    def _should_switch_target(self, current_target: 'Entity', new_target: 'Entity') -> bool:
        """Determine if we should switch from current target to new target"""
        if (
            getattr(self.card_stats, 'targets_only_buildings', False)
            and not is_native_building_target(new_target)
        ):
            return False
        # Normal targeters have no troop-over-building category priority. The
        # closest eligible target wins while pathing; established attack locks
        # are preserved by ``update`` before this method is consulted.
        current_distance = self.native_target_distance_to(current_target)
        new_distance = self.native_target_distance_to(new_target)
        # Building-to-building retargets should only happen when the new building
        # is actually in aggro/sight range; otherwise troops can snap across lanes.
        if (
            is_native_building_target(current_target)
            and is_native_building_target(new_target)
        ):
            if not self.is_within_sight(new_target):
                return False

        return (
            new_distance
            < current_distance - TARGET_DISTANCE_TIE_EPSILON
        )

    def _can_attack_air(self) -> bool:
        """Return True if this entity can attack air units."""
        card_stats = getattr(self, "card_stats", None)
        if not card_stats:
            return True
        target_type = getattr(card_stats, "target_type", None)
        if target_type in {"TID_TARGETS_AIR", "TID_TARGETS_AIR_AND_GROUND"}:
            return True
        return bool(getattr(card_stats, "attacks_air", False))

    def _can_attack_ground(self) -> bool:
        """Return True if this entity can attack ground units."""
        card_stats = getattr(self, "card_stats", None)
        if not card_stats:
            return True
        target_type = getattr(card_stats, "target_type", None)
        if target_type in {
            "TID_TARGETS_GROUND",
            "TID_TARGETS_AIR_AND_GROUND",
            "TID_TARGETS_BUILDINGS",
            "TID_TARGETS_GROUND_AND_BUILDINGS",
            "TID_TARGETS_BUILDINGS_AND_GROUND",
        }:
            return True
        return bool(getattr(card_stats, "attacks_ground", True))


@dataclass
class Troop(Entity):
    speed: float = 1.0
    target_type: TargetType = TargetType.BOTH
    # LogicMovementComponent::avoidance is a persistent signed steering
    # amount. It is initialized to +/-200 by an impending contact, adjusted
    # only by static obstacles while active, and decays ten units per frame.
    _native_avoidance: int = field(default=0, repr=False)

    # Charging mechanics
    is_charging: bool = False
    has_charged: bool = False  # Track if first charge attack has been used
    charge_target_position: Optional[Position] = None
    # LogicMovementComponent stores charge as a 0..10000 integer. Movement
    # work is quantized into ten-unit chunks before it is divided by the
    # serialized ChargeRange, so a float distance threshold drifts under
    # Rage, slowdown, and short final movement calls.
    _native_charge_progress: int = field(default=0, repr=False)
    # Retained as useful telemetry: this is intended natural-movement work,
    # not displacement from collision, attraction, or avoidance rotation.
    distance_traveled: float = 0.0
    initial_position: Position = None  # Store initial position for distance calculation
    _movement_target_id: Optional[int] = field(default=None, repr=False)
    _native_natural_movement_active: bool = field(default=False, repr=False)
    movement_phase_elapsed_ms: int = 0
    _native_knockback_movement_tick: int = field(default=-1, repr=False)
    kamikaze_primed: bool = False
    kamikaze_timer_remaining: float = 0.0

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Advance one troop directly, preserving the public one-call API."""
        self.update_components(dt, battle_state)
        self.tick_character_object_phase(dt)

    def update_components(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run this troop's component phases for direct-call compatibility."""
        self.update_combat_component(dt, battle_state)
        self.update_movement_component(dt, battle_state)
        self.update_buff_component(dt)

    def update_combat_component(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run the troop combat component without committing natural movement."""
        if not self.is_alive and self.id not in getattr(
            battle_state, "_combat_phase_eligible_ids", ()
        ):
            return
        self._movement_target_id = None

        if self.deploy_delay_remaining > 0:
            return

        if getattr(self, "_spawn_hook_pending", False):
            self.on_spawn()

        self._update_active_combat(dt, battle_state)

    def update_movement_component(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run deployment transport, special travel, and natural movement."""
        if not self.is_alive:
            return
        if self.spawn_stagger_remaining > 1e-9:
            return
        target = battle_state.entities.get(self._movement_target_id)
        if (
            target is not None
            and self.deploy_delay_remaining <= 0
            and self._knockback_target is None
            and self._death_spawn_travel_ticks_remaining <= 0
            and not self.is_stunned()
            and not self.forced_movement_active
            and not getattr(self, "_river_jump_active", False)
            and not getattr(self, "_special_move_active", False)
            and not getattr(self, "_special_move_consumed_tick", False)
        ):
            # Native f65790 refreshes the walking route before f65dcc scans
            # avoidance. A static body can remove the newly selected first
            # node; scanning the previous target's route changes this step.
            self._native_movement_waypoint(target, battle_state)
        # Native checks avoidance before collision/pushback and before this
        # frame's target vector replaces the retained character direction.
        # Installed pushback branches before native checkAvoidance. It uses
        # the retained steering value without scanning or decaying it.
        if self._knockback_target is None:
            self._update_native_avoidance(battle_state)
        # Radial death-spawn travel owns the movement component before normal
        # pushback, deployment transport, and natural movement state checks.
        if self._death_spawn_travel_ticks_remaining > 0:
            self._update_death_spawn_travel(battle_state)
            return
        # Native movement components service an installed pushback before
        # checking the character's ordinary deployment/movement state.
        if self._knockback_target is not None:
            self._update_knockback_movement(battle_state)
            return
        if self.deploy_delay_remaining > 0:
            self._native_natural_movement_active = False
            # Deployment-specific transport consumes this component frame
            # while the old character-state timer remains visible.
            for mechanic in self.mechanics:
                mechanic.on_deploy_tick(self, dt * 1000)
            return
        # River travel is already the movement component's committed special
        # state. Its shared flag must not make the generic special-movement
        # adapter skip the jump itself.
        if getattr(self, "_river_jump_active", False):
            self._native_natural_movement_active = False
            self._update_river_jump(dt, battle_state)
            return
        for mechanic in self.mechanics:
            mechanic.on_movement_tick(self, dt * 1000)
        if not self.is_alive:
            return
        if getattr(self, "_special_move_active", False):
            self._native_natural_movement_active = False
            return
        if getattr(self, "_special_move_consumed_tick", False):
            self._native_natural_movement_active = False
            # A special movement that lands in this phase consumes the frame
            # but must not suppress the next frame's combat component.
            self._special_move_consumed_tick = False
            return
        if self.is_stunned():
            # A charged Zap control preserves the bank at the object boundary;
            # the following stopped movement component clears it.
            self.reset_charge()
            self._native_natural_movement_active = False
            return
        movement_target_id = getattr(self, "_movement_target_id", None)
        if movement_target_id is None:
            # Reaching charge speed is not enough: a subsequent movement call
            # must arm the ready hit. Stopping on the threshold clears that
            # unarmed bank instead of granting special damage to a normal hit.
            if not self.is_charging or self.attack_cooldown > 0:
                self.reset_charge()
            if self._native_natural_movement_active or getattr(
                self, "_native_ground_route_cells", None
            ):
                # Stopping clears the native route even when an immediate
                # charged hit cleared its windup latch or a preceding stun
                # cleared the moving flag while retaining the walking route.
                self._native_ground_route_cells = []
                self._ground_path_cache_key = None
            self._native_natural_movement_active = False
            return
        target = battle_state.entities.get(movement_target_id)
        if (
            target is None
            or (
                target.is_alive
                and not getattr(target, "_self_projectile_launched", False)
                and not self._is_valid_target(target, is_current_target=True)
            )
            or self.is_stunned()
            or self.forced_movement_active
            or getattr(self, "_special_move_active", False)
        ):
            self._native_natural_movement_active = False
            return
        # Combat committed this movement goal earlier in the same frame.
        # A later attacker can deplete its HP, or a Spirit can launch before
        # movement runs. Native still spends this frame's committed travel.
        if not self._native_natural_movement_active:
            # LogicMovementComponent::start clears its serialized charge
            # field. Stopping to attack preserves the bank for that hit, but
            # losing the lock and starting toward another target does not.
            self.reset_charge()
            from .ordinary_combat_clock import stop_hit

            stop_hit(self)
            # Restarting movement rebuilds an exhausted route, even when the
            # target's goal cell is unchanged. Reusing the empty cache skips
            # the first intermediate node after a stationary attack.
            if not getattr(self, "_native_ground_route_cells", None):
                self._ground_path_cache_key = None
            self._native_natural_movement_active = True
        self._move_towards_target(target, dt, battle_state)

    def _native_movement_component_stopped(self) -> bool:
        """Return the serialized movement component's stop-byte equivalent."""
        # Later avoidance scans still see movement on the final push frame,
        # even after its rebound has cleared the active knockback target.
        if self._knockback_target is not None or (
            self._native_knockback_movement_tick
            == getattr(self.battle_state, "tick", -2)
        ):
            return False
        if self.is_stunned() and self._native_moving_when_frozen:
            return False
        if self._death_spawn_travel_ticks_remaining > 0:
            # The radial child path owns the movement component before
            # deployment, stun, or ordinary target-state checks.
            return False
        return bool(
            (
                self._movement_target_id is None
                and not getattr(self, "_river_jump_active", False)
            )
            or self.deploy_delay_remaining > 0
            or self.is_stunned()
            or self.kamikaze_primed
        )

    def _decay_native_avoidance(self) -> None:
        if self._native_avoidance < 0:
            self._native_avoidance = min(0, self._native_avoidance + 10)
        elif self._native_avoidance > 0:
            self._native_avoidance = max(0, self._native_avoidance - 10)

    def _update_native_avoidance(self, battle_state: 'BattleState') -> None:
        """Run one native pre-contact steering scan from the retained heading."""
        from .unit_traits import unit_mass

        # Mega Knight's leap uses the client's generic jump state, whose
        # avoidance branch clears the accumulator rather than decaying it.
        if getattr(self, "_mk_leap_phase", None) in {"airborne", "landing"}:
            self._native_avoidance = 0
            return

        facing_x, facing_y = normalized_vector_logic_units(
            self._facing_x_units,
            self._facing_y_units,
            256,
        )
        # Deployment suppresses travel but still accumulates steering. Other
        # movers can inherit that bank after their own avoidance decays to zero.
        if (
            (
                self._native_movement_component_stopped()
                and not (self.deploy_delay_remaining > 0 and not self.is_stunned())
            )
            or (facing_x == 0 and facing_y == 0)
        ):
            self._decay_native_avoidance()
            return

        own_x = tiles_to_logic_units(self.position.x)
        own_y = tiles_to_logic_units(self.position.y)
        probe_x = own_x + facing_x
        probe_y = own_y + facing_y
        probe_radius = min(
            500,
            max(0, tiles_to_logic_units(self.get_collision_radius())),
        )
        own_air_collision = uses_air_collision_plane(self)
        moving_count = 0
        static_count = 0
        moving_side = 1
        static_side = 1
        own_mass = unit_mass(self.card_stats)

        from .native_spatial import NativeAvoidanceGrid

        grid = getattr(battle_state, "_native_avoidance_grid", None)
        if grid is None:
            grid = NativeAvoidanceGrid(battle_state.entities.values())
        for other in grid.query(probe_x, probe_y, probe_radius):
            launched_spirit = getattr(other, "_self_projectile_launched", False)
            if (
                other is self
                or (not other.is_alive and not isinstance(other, Troop))
                or not isinstance(other, (Troop, Building))
                or (
                    launched_spirit
                    and other._self_projectile_launch_tick != battle_state.tick
                )
                or uses_air_collision_plane(other) != own_air_collision
            ):
                continue

            other_x = tiles_to_logic_units(other.position.x)
            other_y = tiles_to_logic_units(other.position.y)
            other_radius = max(
                0,
                tiles_to_logic_units(other.get_collision_radius()),
            )
            query_radius = probe_radius + other_radius
            probe_dx = other_x - probe_x
            probe_dy = other_y - probe_y
            if (
                probe_dx * probe_dx + probe_dy * probe_dy
                > query_radius * query_radius
            ):
                continue

            relative_x = other_x - own_x
            relative_y = other_y - own_y
            cross = facing_y * relative_x - facing_x * relative_y
            geometric_side = 1 if cross < 0 else 0

            # A defeated character loses its movement component before object
            # cleanup. Its resident body still enters this scan as stationary;
            # physical collision eligibility is a separate predicate.
            # The departing Spirit body remains a stationary avoidance
            # obstacle until the launch interval ends, without body pressure.
            if isinstance(other, Troop) and other.is_alive and not launched_spirit and other.spawn_stagger_remaining <= 1e-9:
                # Native states 0/2/8/10 zero the direction dot product;
                # freeze preserves the prior walking versus attacking state.
                if (
                    other.deploy_delay_remaining <= 0
                    and other._native_movement_component_stopped()
                ):
                    direction_dot = 0
                else:
                    other_facing_x, other_facing_y = normalized_vector_logic_units(
                        other._facing_x_units, other._facing_y_units, 256,
                    )
                    direction_dot = (
                        other_facing_x * facing_x + other_facing_y * facing_y
                    )
                approaching = direction_dot <= 0
                if self.is_charging:
                    approaching = (
                        approaching
                        and own_mass <= unit_mass(other.card_stats)
                    )
                if not approaching:
                    continue
                moving_count += 1
                if other._native_avoidance != 0:
                    moving_side = 1 if other._native_avoidance > 0 else 0
                else:
                    moving_side = geometric_side
            else:
                from .pathfinding import (
                    skip_native_ground_route_node_inside_static,
                )

                skip_native_ground_route_node_inside_static(self, other)
                static_count += 1
                static_side = geometric_side

        selected_side = static_side if static_count > 0 else moving_side
        if moving_count + static_count > 0:
            if self._native_avoidance == 0:
                self._native_avoidance = 200 if selected_side else -200
            elif static_count > 0:
                self._native_avoidance += 20 if selected_side else -20
                self._native_avoidance = max(
                    -200,
                    min(200, self._native_avoidance),
                )
        self._decay_native_avoidance()

    def _apply_native_avoidance(
        self,
        move_x_units: int,
        move_y_units: int,
        movement_magnitude_units: int,
    ) -> tuple[int, int]:
        """Rotate intended movement with the client's signed 8-bit blend."""
        avoidance = max(-256, min(256, int(self._native_avoidance)))
        if avoidance == 0:
            return int(move_x_units), int(move_y_units)
        retained = 256 - abs(avoidance)
        rotated_x = (
            (retained * int(move_x_units) >> 8)
            + (avoidance * int(move_y_units) >> 8)
        )
        rotated_y = (
            (retained * int(move_y_units) >> 8)
            + (-int(move_x_units) * avoidance >> 8)
        )
        return normalized_vector_logic_units(
            rotated_x,
            rotated_y,
            movement_magnitude_units,
        )

    def _update_knockback_movement(self, battle_state: 'BattleState') -> None:
        """Advance one fixed 25-work native pushback step."""
        target = self._knockback_target
        if target is None:
            return
        self._native_knockback_movement_tick = battle_state.tick
        if self._knockback_reset_hit_on_movement and self._attack_finish_elapsed_ms > 0:
            # A push cannot cancel recovery installed by target removal.
            self._knockback_reset_hit_on_movement = False
        if self._knockback_reset_hit_on_movement:
            self._knockback_reset_hit_on_movement = False
            self._attack_finish_elapsed_ms = 0
            self._attack_windup_active = False
            self._has_attacked_once = False
            self._attack_preload_blocked = False
            from .ordinary_combat_clock import stop_hit

            stop_hit(self)
            if not self._native_natural_movement_active:
                combat_target = battle_state.entities.get(self.target_id)
                if combat_target is not None and not self.is_air_unit:
                    from .pathfinding import ground_path_waypoint

                    ground_path_waypoint(
                        battle_state,
                        self,
                        combat_target.position,
                        target_entity=combat_target,
                        backwards_reference=combat_target.position,
                    )
                    self._native_natural_movement_active = True
        if (
            self._movement_target_id is not None
            and (
                not self._native_natural_movement_active
                or self._native_navigation_target_id != self._movement_target_id
            )
        ):
            combat_target = battle_state.entities.get(self._movement_target_id)
            if combat_target is not None and not self.is_air_unit:
                # A new walking target needs a route. An unchanged target
                # keeps its exhausted route until physical push work ends.
                # Physical push work still owns this frame's displacement.
                self._native_movement_waypoint(combat_target, battle_state)
                self._native_natural_movement_active = True
        # Native f65818-f658cc recovers blocked ground before spending positive
        # push work. Collision vectors have already been accumulated at the
        # original position; the zero/rebound frames do not perform recovery.
        from .unit_traits import uses_air_collision_plane

        if self._knockback_velocity_work > 0 and not uses_air_collision_plane(self):
            from .native_tilemap import recover_native_ground_position

            x_units, y_units = recover_native_ground_position(
                tiles_to_logic_units(self.position.x),
                tiles_to_logic_units(self.position.y),
            )
            self.position = Position(
                logic_units_to_tiles(x_units), logic_units_to_tiles(y_units)
            )
        self._knockback_velocity_work -= 25
        dx_units = tiles_to_logic_units(target.x - self.position.x)
        dy_units = tiles_to_logic_units(target.y - self.position.y)
        remaining_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        movement_units = min(
            self._knockback_velocity_work,
            250,
            remaining_units,
        )
        if (
            movement_units >= 10
            and self._native_natural_movement_active
            and self._movement_target_id is not None
        ):
            self._advance_native_charge(movement_units)
        if movement_units < 10:
            # Log preserves charge during positive push work. Native clears
            # the bank on the zero-work boundary before the final rebound.
            self.reset_charge()
        move_x_units = 0
        move_y_units = 0
        if movement_units != 0:
            # The final -25 work frame moves back along the retained vector
            # before native clears the pushback state.
            direction_x = trunc_div(dx_units << 8, max(1, remaining_units))
            direction_y = trunc_div(dy_units << 8, max(1, remaining_units))
            move_x_units = trunc_div(direction_x * movement_units, 256)
            move_y_units = trunc_div(direction_y * movement_units, 256)
            if self._native_avoidance:
                # Native updateMovementTowards also steers physical pushes
                # before adding the independently accumulated collision work.
                move_x_units, move_y_units = self._apply_native_avoidance(
                    move_x_units, move_y_units, abs(movement_units),
                )
                # The native steering normalizer accepts the signed work
                # value, including the final negative-work frame.
                if movement_units < 0:
                    move_x_units, move_y_units = -move_x_units, -move_y_units
        external_x, external_y = self.take_pending_movement_vector()
        combined_x_units = move_x_units + tiles_to_logic_units(external_x)
        combined_y_units = move_y_units + tiles_to_logic_units(external_y)
        if combined_x_units != 0 or combined_y_units != 0:
            candidate = Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.x) + combined_x_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y) + combined_y_units
                ),
            )
            # LogicTileMap::moveObject only constrains the arena's outer axes.
            # Water, blocked terrain, and static bodies do not veto controlled
            # movement: pathing and the collision vector accumulated for this
            # component handle those separately.
            candidate.x = clamp_native_object_axis(
                candidate.x,
                battle_state.arena.width,
            )
            candidate.y = clamp_native_object_axis(
                candidate.y,
                battle_state.arena.height,
            )
            self.position = candidate
            if getattr(self, "_river_jump_active", False):
                landing = self._river_jump_target
                jump_speed = max(
                    1,
                    round(
                        float(
                            getattr(self.card_stats, "jump_speed", 0)
                            or 0
                        )
                    ),
                )
                landing_dx = tiles_to_logic_units(
                    landing.x - candidate.x
                )
                landing_dy = tiles_to_logic_units(
                    landing.y - candidate.y
                )
                self._river_jump_origin = Position(
                    candidate.x,
                    candidate.y,
                )
                self._river_jump_elapsed = 0.0
                self._river_jump_duration = max(
                    battle_state.dt,
                    math.isqrt(
                        landing_dx * landing_dx
                        + landing_dy * landing_dy
                    )
                    / jump_speed
                    * LOGIC_TICK_SECONDS,
                )

        # Native keeps byte488 set at exactly zero and clears only after the
        # following component frame subtracts another 25 work units.
        if self._knockback_velocity_work < 0:
            self._knockback_target = None
            self._knockback_velocity_work = 0
            self._knockback_interrupts_combat = True
            self.forced_movement_active = False

    def _update_death_spawn_travel(self, battle_state: 'BattleState') -> None:
        """Advance one native 250-unit radial child-travel frame."""
        target = self._death_spawn_travel_target
        if target is None or self._death_spawn_travel_ticks_remaining <= 0:
            self._death_spawn_travel_target = None
            self._death_spawn_travel_ticks_remaining = 0
            return

        dx_units = tiles_to_logic_units(target.x - self.position.x)
        dy_units = tiles_to_logic_units(target.y - self.position.y)
        remaining_units = max(
            1,
            math.isqrt(dx_units * dx_units + dy_units * dy_units),
        )
        movement_units = min(
            NATIVE_MOVEMENT_SUBSTEP_UNITS,
            remaining_units,
        )
        # LogicMovementComponent::moveTo first creates an 8-bit normalized
        # direction and only then scales it by the per-frame movement budget.
        # These two signed truncations are observably different from one
        # full-precision division on diagonal rings.
        direction_x = trunc_div(dx_units * 256, remaining_units)
        direction_y = trunc_div(dy_units * 256, remaining_units)
        move_x_units = trunc_div(direction_x * movement_units, 256)
        move_y_units = trunc_div(direction_y * movement_units, 256)
        if self._native_avoidance:
            move_x_units, move_y_units = self._apply_native_avoidance(
                move_x_units,
                move_y_units,
                movement_units,
            )

        external_x, external_y = self.take_pending_movement_vector()
        combined_x_units = move_x_units + tiles_to_logic_units(external_x)
        combined_y_units = move_y_units + tiles_to_logic_units(external_y)
        if combined_x_units != 0 or combined_y_units != 0:
            self.position = Position(
                clamp_native_object_axis(
                    logic_units_to_tiles(
                        tiles_to_logic_units(self.position.x) + combined_x_units
                    ),
                    battle_state.arena.width,
                ),
                clamp_native_object_axis(
                    logic_units_to_tiles(
                        tiles_to_logic_units(self.position.y) + combined_y_units
                    ),
                    battle_state.arena.height,
                ),
            )

        self._death_spawn_travel_ticks_remaining -= 1
        if self._death_spawn_travel_ticks_remaining == 0:
            self._death_spawn_travel_target = None

    def update_buff_component(self, dt: float) -> None:
        """Run the character buff/status component after movement."""
        if not self.is_alive:
            return
        self.update_status_effects(dt)

    def tick_character_object_phase(self, dt: float) -> None:
        """Run only ``LogicCharacter::tick`` for the current server frame."""
        if not self.is_alive:
            return
        self.spawn_stagger_remaining = max(0.0, self.spawn_stagger_remaining - dt)
        self._tick_death_spawn_target_immunity(dt)
        self._tick_pending_projectile_duration(dt)
        if self.deploy_delay_remaining > 0:
            self.deploy_delay_remaining = max(
                0.0,
                self.deploy_delay_remaining - dt,
            )
            if self.deploy_delay_remaining > 1e-9:
                return
            self.deploy_delay_remaining = 0.0
            self.placement_pending = False
            if self.is_stunned():
                # Deployment exits into native walking state even under Zap.
                # Preserve its avoidance scan while natural travel is frozen.
                self._native_moving_when_frozen = True
            if getattr(self, "_spawn_hook_pending", False):
                self.on_spawn()
            # Character-owned clocks continue on the deployment zero-crossing
            # frame even though combat and movement components already passed.
            for mechanic in self.mechanics:
                mechanic.on_object_tick(self, dt * 1000)
            return
        if getattr(self, "_spawn_hook_pending", False):
            self.on_spawn()
        if not getattr(self, "_river_jump_active", False):
            self._native_deployed_elapsed_ms += max(0, logic_time_milliseconds(dt))
        for mechanic in self.mechanics:
            mechanic.on_object_tick(self, dt * 1000)

    def _update_active_combat(self, dt: float, battle_state: 'BattleState') -> None:
        """Run troop combat/movement components before buff/object components."""
        if self._freeze_target_pause_remaining > 0:
            return
        if self._tick_attack_finish(dt):
            return

        if getattr(self, "_river_jump_active", False):
            # River travel suspends attacks, but the weapon keeps loading.
            from .ordinary_combat_clock import get_clock, publish

            clock = get_clock(self)
            if clock is not None:
                clock.advance(
                    max(0, logic_time_milliseconds(dt)), 0,
                    engaged=False, frozen=self.is_stunned(),
                )
                publish(self, clock)
            return

        push_blocks_attack = bool(
            self._knockback_target is not None and self._knockback_interrupts_combat
        )
        if self.forced_movement_active and self._knockback_target is None:
            return

        # Call on_tick for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_tick(self, dt * 1000)  # Convert to ms

        if any(
            mechanic.blocks_combat_actions(self)
            for mechanic in self.mechanics
        ):
            return

        if getattr(self, "_special_move_active", False) or getattr(
            self, "_special_move_consumed_tick", False
        ):
            self._special_move_consumed_tick = False
            return

        # Store initial position for distance tracking
        if self.initial_position is None:
            self.initial_position = Position(self.position.x, self.position.y)
        
        # Update last attack time for visualization tracking
        self.last_attack_time += dt
        
        # Always re-evaluate targets every tick to switch to higher priority enemies.
        current_target = None
        pending_retarget = False
        if self.target_id is not None:
            current_target = battle_state.entities.get(self.target_id)
            pending_retarget = self._pending_damage_retargets_hit(current_target)
            if (
                not current_target
                or not self._is_valid_target(
                    current_target,
                    is_current_target=True,
                )
                or (
                    not self._retains_depleted_combat_target(current_target)
                    and not self.can_affect_target_plane(current_target)
                )
            ):
                self.target_id = None
                current_target = None
        
        # Re-evaluate while pathing, but preserve an established attack lock.
        # A troop already in reach keeps hitting that target until it dies,
        # becomes untargetable, or leaves the native keep-target extension;
        # newly deployed distractions cannot peel a P.E.K.K.A./Knight off a
        # connected target at the fixed-point boundary.
        if (
            current_target is None
            or not self.is_within_target_keep_reach(current_target)
        ):
            using_crown_fallback = False
            best_target = self.get_nearest_target(
                battle_state.entities,
                include_crown_fallback=False,
            )
            if (
                best_target is None
                and not (
                    current_target is not None
                    and LOGIC_PATHFIND_BACKWARDS_TRY_KEEP_TARGET
                    and self._ground_path_backwards
                    # A cached route may outlive a stationary attack cycle.
                    # Only active backward walking retains this distant lock.
                    and self._native_natural_movement_active
                )
            ):
                best_target = self.get_nearest_target(
                    battle_state.entities,
                )
                using_crown_fallback = best_target is not None
            if best_target and (
                using_crown_fallback
                or not current_target
                or (
                    self.ignores_targets_with_pending_projectile_damage()
                    and current_target.is_expected_to_die_from_projectiles()
                )
                # A nearer troop outside sight cannot veto the newly chosen
                # visible target. Crown navigation remains an infinite-sight
                # fallback, so its existing switching rules still apply.
                or (
                    getattr(current_target, "_crown_tower_slot", None) is None
                    and not self.is_within_sight(current_target)
                )
                or self._should_switch_target(current_target, best_target)
            ):
                current_target = best_target
                self.target_id = current_target.id

        acquired_from_idle = getattr(self, "_last_combat_target_id", None) is None
        self._note_combat_target(current_target, preserve_hit=pending_retarget)
        if (
            current_target is not None
            and self.is_within_attack_clock_reach(current_target)
        ):
            # Retargeting must clear the old hit latch before this decision.
            # Otherwise an out-of-range new target replaces the retained
            # heading and reverses the following avoidance scan.
            self.face_towards(current_target.position)
        for mechanic in self.mechanics:
            mechanic.on_target_observed(
                self,
                current_target,
                dt * 1000,
            )

        # Target observation precedes the native stun-state early return.
        # Stunned units therefore retain or update their combat lock as the
        # battlefield changes, even though they cannot advance their attack
        # clock or move until the effect expires.
        if self.is_stunned():
            return

        if push_blocks_attack:
            # Interrupting pushback pauses hits, not target observation or
            # preparation of the next walking route.
            from .ordinary_combat_clock import get_clock, publish

            clock = get_clock(self)
            if clock is not None:
                clock.advance(max(0, logic_time_milliseconds(dt)), 0, engaged=False)
                publish(self, clock)
            if current_target is not None and not self.is_within_attack_clock_reach(current_target):
                self._movement_target_id = current_target.id
            return

        # Delayed kamikaze attacks become committed once primed: the unit
        # stops moving but remains alive/damageable until its serialized
        # countdown expires. Stun pauses the countdown because the native
        # combat state has already returned above.
        if self.kamikaze_primed:
            self.kamikaze_timer_remaining = max(
                0.0,
                self.kamikaze_timer_remaining - dt,
            )
            if self.kamikaze_timer_remaining <= 1e-9:
                self.take_damage(self.hitpoints)
            return

        # A deployed troop enters with its Load Time already preloaded. Full
        # cycles may preload while walking, but only down to the same finite
        # first-hit remainder rather than all the way to an instant attack.
        if acquired_from_idle or (
            not self._attack_windup_active and self._native_natural_movement_active
        ):
            self._advance_acquisition_load(current_target, dt)
        target_in_range = bool(
            current_target is not None
            and self.is_within_attack_clock_reach(current_target)
        )
        self.advance_attack_clock(dt, target_in_range=target_in_range)
        if not target_in_range:
            self._attack_windup_active = False
        else:
            self._attack_windup_active = True
        
        if current_target:
            # Move towards target if out of range
            if not target_in_range:
                self._movement_target_id = current_target.id
            elif self._attack_is_due():
                alive_before_attack_start = self.is_alive
                # Call on_attack_start for all mechanics
                for mechanic in self.mechanics:
                    mechanic.on_attack_start(self, current_target)

                # Kamikaze mechanics may consume the attack by killing the
                # attacker (and possibly the target) during attack start.
                if alive_before_attack_start and not self.is_alive:
                    return
                if getattr(self, "_special_move_active", False) or getattr(
                    self, "_special_move_consumed_tick", False
                ):
                    self._special_move_consumed_tick = False
                    return
                if self.should_cancel_committed_hit(current_target):
                    # The attack attempt is consumed even though its payload
                    # is rejected. Native preserves the already-loaded portion
                    # of the next hit instead of installing a full cycle.
                    self._complete_attack_clock_cycle(discarded=True)
                    self._attack_windup_active = False
                    self._has_attacked_once = True
                    self._has_attacked_current_target = True
                    self._attack_preload_blocked = False
                    self.last_attack_time = 0.0
                    self._on_attack()
                    return
                if (
                    getattr(self.card_stats, "kamikaze", False)
                    and getattr(self.card_stats, "damage", None) is None
                ):
                    delay = max(
                        0.0,
                        float(getattr(self.card_stats, "kamikaze_time", 0) or 0)
                        / 1000.0,
                    )
                    if delay > 0.0:
                        self.kamikaze_primed = True
                        self.kamikaze_timer_remaining = delay
                        self._attack_windup_active = False
                        return
                    # Payload-only kamikaze troops with no explicit delay
                    # break on the committed attack frame.
                    self.take_damage(self.hitpoints)
                    return

                # Check if this troop uses projectiles
                uses_projectile = self._uses_projectiles()
                if uses_projectile:
                    self._create_projectile(current_target, battle_state)
                else:
                    # Direct attack with special charging damage if applicable
                    attack_damage = self._get_attack_damage()
                    self._deal_attack_damage(
                        current_target,
                        attack_damage,
                        battle_state,
                    )

                # This lifecycle point is deliberately after projectile
                # creation.  Mechanics such as recoil must not move the
                # launch origin before the payload has been committed.
                for mechanic in self.mechanics:
                    mechanic.on_attack_committed(self, current_target)

                self._complete_attack_clock_cycle()
                self._attack_windup_active = False
                self._has_attacked_once = True
                self._has_attacked_current_target = True
                self._attack_preload_blocked = False
                self.last_attack_time = 0.0  # Reset for visualization
                self._on_attack()  # Handle post-attack mechanics

    def _get_attack_damage(self) -> float:
        """Get the appropriate damage value based on charging state"""
        if getattr(self.card_stats, 'charge_range', None) and not self.has_charged and self.is_charging:
            # Use special damage for first charge attack
            return float(
                (getattr(self.card_stats, 'scaled_damage_special', None)
                 or getattr(self.card_stats, 'damage_special', None)
                 or self.damage)
            )
        return float(self.damage)

    def _uses_projectiles(self) -> bool:
        """Check if this troop uses projectiles for attacks"""
        if getattr(self, '_force_melee_attack', False):
            return False
        return (self.card_stats and 
                hasattr(self.card_stats, 'projectile_data') and 
                self.card_stats.projectile_data is not None)
    
    def _create_projectile(
        self,
        target: Optional['Entity'],
        battle_state: 'BattleState',
        *,
        target_position: Optional[Position] = None,
    ) -> None:
        """Create a projectile toward a live target or explicit aim point."""
        if not self.card_stats or not self.card_stats.projectile_data:
            # Fallback to direct attack if no projectile data
            if target is None:
                return
            attack_damage = self._get_attack_damage()
            target.take_damage(attack_damage)
            return

        aim_position = target_position or (
            target.position if target is not None else self.position
        )
        
        # Get projectile properties
        projectile_data = self.card_stats.projectile_data
        projectile_damage = self.damage  # Use entity's scaled damage instead of base projectile damage
        if projectile_data.get("spawnProjectileData") and projectile_data.get("damage") is None:
            # Carrier projectiles such as Firecracker's firework only choose
            # the burst point. Their spawned projectiles are the damage hits.
            projectile_damage = 0.0
        projectile_speed = logic_speed_to_tiles_per_second(
            projectile_data.get('speed', 500)
        )
        splash_radius = projectile_data.get('radius', 0) / 1000.0 if projectile_data.get('radius') else 0.0
        target_buff_data = projectile_data.get("targetBuffData") or {}
        slow_duration = projectile_data.get("buffTime", 0) / 1000.0
        slow_multiplier = 1.0 + (target_buff_data.get("speedMultiplier", 0) / 100.0)
        stun_duration = 0.0
        if (
            target_buff_data.get("speedMultiplier") == -100
            and target_buff_data.get("hitSpeedMultiplier") == -100
            and slow_duration > 0
        ):
            stun_duration = slow_duration
            slow_duration = 0.0
            slow_multiplier = 1.0
        hits_air, hits_ground = serialized_hit_planes(
            projectile_data,
            default_air=self._can_attack_air(),
            default_ground=self._can_attack_ground(),
        )
        crown_tower_damage_multiplier = max(
            0.0, 1.0 + (projectile_data.get("crownTowerDamagePercent", 0) / 100.0)
        )
        launch_position, direction_x, direction_y = (
            self._projectile_launch_geometry_at(aim_position)
        )
        
        # Use charging damage if applicable
        if self.is_charging and self.card_stats.damage_special:
            projectile_damage = (
                getattr(self.card_stats, "scaled_damage_special", None)
                or self.card_stats.damage_special
            )

        # Target-specific payloads must be derived from the final committed
        # projectile damage. A charge/special attack may replace the ordinary
        # damage immediately above, so resolving Crown Tower damage earlier
        # would pair one launch with two different base attacks.
        crown_tower_damage = None
        for mechanic in self.mechanics:
            resolver = getattr(mechanic, "projectile_crown_tower_damage", None)
            if not callable(resolver):
                continue
            candidate = resolver(self, projectile_damage)
            if candidate is not None:
                crown_tower_damage = float(candidate)

        # Rolling payloads are identified by their serialized swept hitbox,
        # finite travel range, and push.  This covers Bowler without binding
        # the projectile engine to a parent card name.
        is_rolling_projectile = bool(
            projectile_data.get("projectileRadius")
            and projectile_data.get("projectileRange")
            and projectile_data.get("pushback")
        )
        projectile_range = float(projectile_data.get("projectileRange", 0) or 0) / 1000.0
        if is_rolling_projectile:
            rolling_radius = float(
                projectile_data.get("projectileRadius", projectile_data.get("radius", 0)) or 0
            ) / 1000.0
            # Create rolling projectile (Bowler boulder) with target direction
            rolling_projectile = RollingProjectile(
                id=battle_state.next_entity_id,
                position=launch_position,
                player_id=self.player_id,
                card_stats=self.card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=projectile_damage,
                range=rolling_radius,
                sight_range=0,
                # RollingProjectile retains the serialized per-tick speed.
                travel_speed=projectile_data.get('speed', 500),
                projectile_range=projectile_range,
                spawn_delay=0.0,  # No spawn delay for Bowler
                spawn_character=None,  # Bowler doesn't spawn units
                spawn_character_data=None,
                knockback_distance=projectile_data.get("pushback", 1000) / 1000.0,
                impact_radius=splash_radius,
                target_direction_x=direction_x,
                target_direction_y=direction_y,
                crown_tower_damage_multiplier=crown_tower_damage_multiplier,
                crown_tower_damage=crown_tower_damage,
                source_entity=self,
                primary_target=(
                    target if target is not None and target.is_alive else None
                ),
            )
            
            battle_state.entities[rolling_projectile.id] = rolling_projectile
        else:
            # Create regular projectile
            is_piercing = projectile_range > 0
            projectile_target_position = Position(
                aim_position.x,
                aim_position.y,
            )
            if is_piercing:
                if direction_x or direction_y:
                    range_x_units, range_y_units = normalized_vector_logic_units(
                        direction_x,
                        direction_y,
                        tiles_to_logic_units(projectile_range),
                    )
                    projectile_target_position = Position(
                        logic_units_to_tiles(
                            tiles_to_logic_units(launch_position.x) + range_x_units
                        ),
                        logic_units_to_tiles(
                            tiles_to_logic_units(launch_position.y) + range_y_units
                        ),
                    )
            projectile = Projectile(
                id=battle_state.next_entity_id,
                position=launch_position,
                player_id=self.player_id,
                card_stats=self.card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=projectile_damage,
                range=self.range,
                sight_range=1.0,
                target_position=projectile_target_position,
                travel_speed=projectile_speed,
                splash_radius=splash_radius,
                source_name=self.card_stats.name if self.card_stats else "Unknown",
                stun_duration=stun_duration,
                slow_duration=slow_duration,
                slow_multiplier=max(0.0, slow_multiplier),
                knockback_distance=projectile_data.get("pushback", 0) / 1000.0,
                hits_air=hits_air,
                hits_ground=hits_ground,
                crown_tower_damage_multiplier=crown_tower_damage_multiplier,
                crown_tower_damage=crown_tower_damage,
                source_entity=self,
                primary_target=(
                    target if target is not None and target.is_alive else None
                ),
                tracks_target=bool(projectile_data.get("homing", True))
                and not bool(is_piercing or projectile_data.get("spawnProjectileData")),
                pierces=is_piercing,
                projectile_range=projectile_range,
                homing_time_ms=int(projectile_data.get("homingTime", 0) or 0),
                homing_min_distance=float(
                    projectile_data.get("homingMinDistance", 0) or 0
                ) / 1000.0,
                start_extra_radius=float(
                    projectile_data.get("projectileStartExtraRadius", 0) or 0
                ) / 1000.0,
                spawn_projectile_data=projectile_data.get("spawnProjectileData"),
            )

            battle_state.entities[projectile.id] = projectile

        # Reserve the object's ID before any synchronous impact callback.
        # Piercing projectiles can kill a death-spawner in their enlarged
        # launch hitbox, and its children allocate from the same shared ID
        # sequence.
        battle_state.next_entity_id += 1
        if not is_rolling_projectile:
            projectile.resolve_start_collision(battle_state)

    def _on_attack(self) -> None:
        """Handle post-attack mechanics like charging state reset"""
        if self.card_stats.charge_range:
            self.reset_charge()

    def reset_charge(self, *, interrupted: bool = False) -> None:
        """Reset charge state and restore first-hit timing when interrupted."""
        if not self.card_stats.charge_range:
            return
        was_charging = self.is_charging
        if was_charging:
            from .ordinary_combat_clock import get_clock, publish

            clock = get_clock(self)
            if clock is not None and self._ordinary_force_due:
                self._ordinary_force_due = False
                publish(self, clock)
        self.has_charged = False
        self.is_charging = False
        self._native_charge_progress = 0
        self.charge_target_position = None
        self.distance_traveled = 0.0
        self._set_unslowed_movement_speed(self.card_stats.speed or 60.0)
        if interrupted and was_charging:
            self.reset_attack_windup()
            self._attack_preload_blocked = False

    def _set_unslowed_movement_speed(self, speed: float) -> None:
        """Change movement mode without discarding an active slow.

        ``original_speed`` is the unslowed speed for the current mode. Charge
        transitions therefore update that baseline and let the shared status
        stack keep applying its strongest movement modifier.
        """
        speed = float(speed)
        if self.original_speed is not None:
            self.original_speed = speed
            self.speed = (
                speed * self._movement_debuff_multiplier()
            )
        else:
            self.speed = speed * self._movement_debuff_multiplier()

    def set_movement_mode_multiplier(self, multiplier: float) -> None:
        """Update one independently timed modifier in the negative lane."""
        unslowed_speed = self._unslowed_movement_speed()
        self.movement_mode_multiplier = max(0.0, float(multiplier))
        self.speed = (
            unslowed_speed
            * self._movement_debuff_multiplier()
        )

    def _native_charge_speed(self) -> float:
        configured = self.card_stats.charge_speed_multiplier
        # Character data stores charged speed as an absolute percentage of
        # base speed (200 means 2x), not an additive bonus.
        speed_multiplier = (
            2.0
            if configured is None
            else max(0.0, float(configured) / 100.0)
        )
        return (self.card_stats.speed or 60.0) * speed_multiplier

    def _update_charging_state(
        self,
        battle_state: Optional['BattleState'] = None,
    ) -> None:
        """Expose the movement component's serialized charge threshold."""
        del battle_state
        self.is_charging = bool(
            self.card_stats.charge_range
            and self._native_charge_progress >= 10000
        )

    def _prepare_native_charge_movement(self) -> None:
        """Select the movement speed used at the start of this native call."""
        if not self.card_stats.charge_range:
            return
        self._update_charging_state()
        self._set_unslowed_movement_speed(
            self._native_charge_speed()
            if self.is_charging
            else (self.card_stats.speed or 60.0)
        )

    def _advance_native_charge(
        self,
        movement_work_units: int,
        *,
        ordinary_movement_state: bool = True,
    ) -> None:
        """Consume one updateMovementTowards call exactly like the client."""
        charge_range = int(self.card_stats.charge_range or 0)
        if charge_range <= 0:
            return

        work_units = max(0, int(movement_work_units))
        if work_units < 1 or not ordinary_movement_state:
            self.reset_charge()
            return

        self.distance_traveled += logic_units_to_tiles(work_units)
        if self._native_charge_progress <= 9999:
            self._native_charge_progress += (
                1000 * work_units // charge_range
            )
            self._update_charging_state()
            return

        # The combat component's one-shot "fully loaded" byte is armed only
        # on a movement call that begins fully charged. Crossing 10000 at the
        # end of the preceding call changes avoidance immediately, but does
        # not make the attack connect one component frame too early.
        self.is_charging = True
        self.attack_cooldown = 0.0
        self._attack_preload_blocked = False

    def _native_movement_waypoint(self, target_entity: 'Entity', battle_state=None) -> Position:
        """Prepare a route without replacing the retained facing direction."""
        self._native_navigation_target_id = target_entity.id
        route_goal = target_entity.position
        # Flying characters still select the native required-range goal cell,
        # but store only that single node instead of invoking LogicPathFinder.
        if self.is_air_unit:
            from .pathfinding import native_single_node_waypoint

            pathfind_target = native_single_node_waypoint(
                self,
                target_entity,
            )
        else:
            # LogicPathFinder owns bridge and river selection through the
            # immutable arena's lane/water costs. Hovering characters travel
            # directly but remain on the ground collision plane.
            pathfind_target = route_goal
            if battle_state is not None:
                from .pathfinding import ground_path_waypoint

                pathfind_target = ground_path_waypoint(
                    battle_state,
                    self,
                    pathfind_target,
                    target_entity=target_entity,
                    backwards_reference=target_entity.position,
                )
        return pathfind_target

    def _move_towards_target(self, target_entity: 'Entity', dt: float, battle_state=None) -> None:
        """Move toward the next native-grid route waypoint."""
        self._prepare_native_charge_movement()
        previous_position = Position(self.position.x, self.position.y)
        pathfind_target = self._native_movement_waypoint(target_entity, battle_state)

        self.face_towards(pathfind_target)
        dx = pathfind_target.x - self.position.x
        dy = pathfind_target.y - self.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        external_x, external_y = self.take_pending_movement_vector()
        external_x_units = tiles_to_logic_units(external_x)
        external_y_units = tiles_to_logic_units(external_y)
        self_movement = 0.0
        if distance > 0:
            # ``speed`` mirrors the debuffed value for observations and legacy
            # callers. Movement starts from the current unslowed mode (normal
            # or charging) so haste and slow compose around the base rate.
            # Character-owned modifiers and external slows share the native
            # strongest-negative lane while retaining independent lifetimes.
            unslowed_speed = self._unslowed_movement_speed()
            movement_debuff = self._movement_debuff_multiplier()
            effective_speed = self._native_scaled_speed(
                unslowed_speed,
                movement_debuff,
                self.movement_speed_buff_multiplier,
            )
            speed_tiles_per_second = logic_speed_to_tiles_per_second(effective_speed)
            stop_after_ms = float(
                getattr(self.card_stats, "stop_movement_after_ms", 0) or 0
            )
            wait_ms = float(getattr(self.card_stats, "wait_ms", 0) or 0)
            if stop_after_ms > 0 and wait_ms > 0:
                # Native f66288..f663ec scales 100 by the buff component,
                # then halves it for the 50ms clock. Do not recover this
                # modifier from rounded stride speed: slowed Giant uses
                # 35 clock units despite its 36-unit stride (52 * 70%).
                self.movement_phase_elapsed_ms += trunc_div(
                    logic_time_milliseconds(dt) * self._native_scaled_speed(
                        100, movement_debuff, self.movement_speed_buff_multiplier,
                    ),
                    100,
                )
                cycle_ms = round(stop_after_ms + wait_ms)
                if self.movement_phase_elapsed_ms >= cycle_ms:
                    self.movement_phase_elapsed_ms %= cycle_ms
                elif self.movement_phase_elapsed_ms > stop_after_ms:
                    speed_tiles_per_second = 0.0
            movement_work_units = speed_work_for_duration(effective_speed, dt)
            if speed_tiles_per_second <= 0.0:
                movement_work_units = 0
            target_distance_units = max(
                1,
                math.isqrt(
                    tiles_to_logic_units(dx) ** 2
                    + tiles_to_logic_units(dy) ** 2
                ),
            )
            intended_movement_units = min(
                movement_work_units,
                target_distance_units,
            )
            move_x_units, move_y_units = movement_component_vector_logic_units(
                tiles_to_logic_units(dx),
                tiles_to_logic_units(dy),
                intended_movement_units,
            )
            if self._native_avoidance:
                move_x_units, move_y_units = self._apply_native_avoidance(
                    move_x_units,
                    move_y_units,
                    intended_movement_units,
                )
            move_distance = logic_units_to_tiles(intended_movement_units)

            combined_x_units = move_x_units + external_x_units
            combined_y_units = move_y_units + external_y_units

            new_position = Position(
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.x) + combined_x_units
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y) + combined_y_units
                ),
            )
            if battle_state is not None:
                # LogicTileMap::moveObject clips every movement result to the
                # outer object-center boundary before terrain handling. This
                # also matters for natural movement from an unwalkable spawn
                # point: avoidance may rotate the first step back toward the
                # edge while the unit is still allowed to egress that point.
                new_position.x = clamp_native_object_axis(
                    new_position.x,
                    battle_state.arena.width,
                )
                new_position.y = clamp_native_object_axis(
                    new_position.y,
                    battle_state.arena.height,
                )

            # LogicTileMap::moveObject clips at the arena boundary but does
            # not reject water, tower tiles, or other static terrain. Native
            # path selection keeps ordinary ground movement on valid nodes;
            # rechecking the continuous endpoint here creates a second,
            # non-native steering system at tile boundaries.
            has_external = abs(external_x) > 1e-15 or abs(external_y) > 1e-15
            if has_external and battle_state is not None:
                self.position.x = new_position.x
                self.position.y = new_position.y
                self_movement = move_distance
            elif self.is_air_unit:
                self.position = new_position
                self_movement = move_distance
            else:
                self.position = new_position
                self_movement = move_distance

        elif abs(external_x) > 1e-15 or abs(external_y) > 1e-15:
            moved_x = logic_units_to_tiles(
                tiles_to_logic_units(self.position.x) + external_x_units
            )
            moved_y = logic_units_to_tiles(
                tiles_to_logic_units(self.position.y) + external_y_units
            )
            self.position.x = clamp_native_object_axis(
                moved_x,
                battle_state.arena.width,
            )
            self.position.y = clamp_native_object_axis(
                moved_y,
                battle_state.arena.height,
            )

        if (
            battle_state is not None
            and not getattr(self, "_river_jump_active", False)
        ):
            from .native_tilemap import native_spawn_tile_blocked
            from .pathfinding import advance_native_ground_route

            consumed = advance_native_ground_route(
                self,
                pathfind_target,
                previous_position,
            )
            route = getattr(self, "_native_ground_route_cells", None)
            if consumed and route and native_spawn_tile_blocked(*route[0]):
                # Native movement starts the jump after consuming a node,
                # even while the character is still on dry land.
                next_x, next_y = route[0]
                self._try_start_river_jump(
                    target_entity.position,
                    Position(next_x * 0.5 + 0.25, next_y * 0.5 + 0.25),
                    battle_state,
                    target_entity=target_entity,
                )

        if getattr(self.card_stats, "charge_range", None):
            # Collision and attraction do not charge Prince/Battle Ram. The
            # native clock consumes requested work even when tile-map
            # collision prevents equivalent physical displacement.
            self._advance_native_charge(
                intended_movement_units if distance > 0 else 0
            )

    def _try_start_river_jump(
        self,
        pathfind_target: Position,
        blocked_position: Position,
        battle_state: 'BattleState',
        *,
        target_entity: Optional['Entity'] = None,
    ) -> bool:
        if not getattr(self.card_stats, "jump_height", None):
            return False
        # The two outer river edges map onto each other under the arena's
        # 180-degree player transform (15.0 <-> 17.0). Both are valid jump
        # initiation boundaries; a half-open upper edge makes an otherwise
        # identical jumper walk around the river in only one direction.
        if not (
            battle_state.arena.RIVER_Y1
            <= blocked_position.y
            <= battle_state.arena.RIVER_Y2 + 1.0
        ):
            return False

        from .pathfinding import native_jump_landing_waypoint

        landing = native_jump_landing_waypoint(
            battle_state,
            self,
            pathfind_target,
            target_entity=target_entity,
        )
        if landing is None:
            self._river_jump_blocked = True
            return False

        origin_x_units = tiles_to_logic_units(self.position.x)
        origin_y_units = tiles_to_logic_units(self.position.y)
        landing_dx_units = tiles_to_logic_units(landing.x) - origin_x_units
        landing_dy_units = tiles_to_logic_units(landing.y) - origin_y_units
        distance_units = math.isqrt(
            landing_dx_units * landing_dx_units
            + landing_dy_units * landing_dy_units
        )
        jump_speed = round(float(getattr(self.card_stats, "jump_speed", 0) or 0))
        if jump_speed <= 0:
            return False
        self._river_jump_origin = Position(self.position.x, self.position.y)
        self._river_jump_target = landing
        self._river_jump_elapsed = 0.0
        self._river_jump_duration = max(
            battle_state.dt,
            distance_units / jump_speed * LOGIC_TICK_SECONDS,
        )
        self._river_jump_active = True
        # The native jump replaces the route endpoint with the landing cell.
        # Its next ordinary movement therefore rebuilds the target route.
        self._ground_path_cache_key = None
        self._special_move_active = True
        return True

    def _update_river_jump(self, dt: float, battle_state: 'BattleState') -> None:
        self._river_jump_elapsed += dt
        target = self._river_jump_target
        self.face_towards(target)
        dx_units = tiles_to_logic_units(target.x - self.position.x)
        dy_units = tiles_to_logic_units(target.y - self.position.y)
        remaining_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        jump_speed = round(float(getattr(self.card_stats, "jump_speed", 0) or 0))
        work_units = speed_work_for_duration(jump_speed, dt)
        # River travel suspends ordinary charge work, preserving its bank.
        move_x_units, move_y_units = movement_component_vector_logic_units(
            dx_units,
            dy_units,
            work_units,
        )
        if self._native_avoidance:
            move_x_units, move_y_units = self._apply_native_avoidance(
                move_x_units,
                move_y_units,
                min(work_units, remaining_units),
            )
        self.position = Position(
            logic_units_to_tiles(
                tiles_to_logic_units(self.position.x) + move_x_units
            ),
            logic_units_to_tiles(
                tiles_to_logic_units(self.position.y) + move_y_units
            ),
        )
        after_dx = tiles_to_logic_units(target.x - self.position.x)
        after_dy = tiles_to_logic_units(target.y - self.position.y)
        after_distance = math.isqrt(after_dx * after_dx + after_dy * after_dy)
        # Native state 5 returns to walking when integer remaining travel
        # is at most one tick (distance / speed), without snapping to the node.
        if work_units <= 0 or after_distance // work_units > 1:
            return
        self._river_jump_active = False
        # Later movement components still see the airborne collision plane
        # on the landing frame. Ground targeting resumes immediately.
        self._river_landed_tick = battle_state.tick
        self._native_natural_movement_active = True
        self._special_move_active = False
        self._river_jump_blocked = False
        if self._stun_interrupt_deferred_until_landing:
            self._stun_interrupt_deferred_until_landing = False
            if self.stun_timer > 0.0:
                self._interrupt_combat_by_stun()

    def _get_pathfind_target(self, target_entity: 'Entity', battle_state=None) -> Position:
        """Return the next waypoint on a shortest legal route to ``target_entity``.

        Ground units crossing the river first align with a bridge on their
        current bank, then cross to the opposite bank.  The direction comes
        from the unit and target positions rather than unit ownership, so the
        same rule also handles units displaced onto the opponent's side.
        """
        final_target = target_entity.position

        from .unit_traits import is_hover_unit_card

        if self.is_air_unit or is_hover_unit_card(self.card_stats):
            return final_target

        def arena_side(y: float, owner_id: int) -> int:
            if y < 16.0 - 1e-9:
                return 0
            if y > 16.0 + 1e-9:
                return 1
            # The centerline maps onto itself under the player transform. Its
            # side therefore has to come from state that also transforms; the
            # occupying entity's owner is the stable player-relative tie-break.
            return owner_id

        current_side = arena_side(self.position.y, self.player_id)
        target_side = arena_side(final_target.y, target_entity.player_id)
        if current_side == target_side:
            return final_target

        if (
            getattr(self.card_stats, "jump_height", None)
            and not getattr(self, "_river_jump_blocked", False)
        ):
            return final_target

        travel_direction = 1 if target_side > current_side else -1
        near_y = 14.5 if travel_direction > 0 else 17.5
        far_y = 17.5 if travel_direction > 0 else 14.5
        bridge_x = self._choose_crossing_bridge_x(final_target, near_y, far_y)

        # Once inside a bridge corridor, finish that crossing rather than
        # switching bridges as target movement changes the route estimate.
        if 15.0 - 1e-9 <= self.position.y <= 17.0 + 1e-9:
            if 2.0 - 1e-9 <= self.position.x <= 5.0 + 1e-9:
                bridge_x = 3.5
            elif 13.0 - 1e-9 <= self.position.x <= 16.0 + 1e-9:
                bridge_x = 14.5

        reached_near_bank_y = (
            self.position.y >= near_y - 1e-9
            if travel_direction > 0
            else self.position.y <= near_y + 1e-9
        )
        aligned_with_bridge = abs(self.position.x - bridge_x) <= 1.5 + 1e-9
        reached_near_bank = reached_near_bank_y and aligned_with_bridge
        return Position(bridge_x, far_y if reached_near_bank else near_y)

    def _choose_crossing_bridge_x(
        self,
        final_target: Position,
        near_y: float,
        far_y: float,
    ) -> float:
        """Choose the shortest bank-to-bank route with a symmetric tie-break."""
        left_near = Position(3.5, near_y)
        left_far = Position(3.5, far_y)
        right_near = Position(14.5, near_y)
        right_far = Position(14.5, far_y)
        left_distance = self.position.distance_to(left_near) + left_far.distance_to(
            final_target
        )
        right_distance = self.position.distance_to(right_near) + right_far.distance_to(
            final_target
        )
        if math.isclose(left_distance, right_distance, rel_tol=0.0, abs_tol=1e-9):
            return 3.5 if self.player_id == 0 else 14.5
        return 3.5 if left_distance < right_distance else 14.5
  

@dataclass
class Building(Entity):
    speed: float = 0.0  # Buildings don't move
    lifetime_elapsed: float = 0.0
    lifetime_decay_work: int = 0
    lifetime_tick_carry_ms: float = 0.0
    requires_activation: bool = False
    activation_delay_seconds: float = 0.0
    activation_delay_remaining: float = 0.0
    activation_first_hit_delay_seconds: float = 0.0
    activation_first_hit_delay_remaining: float = 0.0
    _crown_tower_slot: Optional[str] = field(default=None, repr=False)

    def activate(self) -> None:
        """Start this building's one-time activation sequence."""
        if not self.requires_activation or getattr(self, "_tower_active", True):
            return
        self._tower_active = True
        self.activation_delay_remaining = max(
            self.activation_delay_remaining,
            self.activation_delay_seconds,
        )
        self.activation_first_hit_delay_remaining = max(
            self.activation_first_hit_delay_remaining,
            self.activation_first_hit_delay_seconds,
        )
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Advance one building directly, preserving the public one-call API."""
        self.update_components(dt, battle_state)
        self.tick_character_object_phase(dt)

    def update_components(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run building component phases for direct-call compatibility."""
        self.update_combat_component(dt, battle_state)
        self.update_movement_component(dt, battle_state)
        self.update_hitpoint_component(dt)
        self.update_buff_component(dt)

    def update_combat_component(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run the building combat component."""
        if not self.is_alive and self.id not in getattr(
            battle_state, "_combat_phase_eligible_ids", ()
        ):
            return

        if self.deploy_delay_remaining > 0:
            return

        if getattr(self, "_spawn_hook_pending", False):
            self.on_spawn()

        self._update_active_combat(dt, battle_state)

    def update_movement_component(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run deployment-only building movement mechanics, when present."""
        if not self.is_alive or self.deploy_delay_remaining <= 0:
            return
        for mechanic in self.mechanics:
            mechanic.on_deploy_tick(self, dt * 1000)

    def update_hitpoint_component(self, dt: float) -> None:
        """Run intrinsic lifetime decay after combat and movement."""
        if not self.is_alive:
            return
        # The native deployment phase keeps lifetime health intact. Decay
        # starts on the first hitpoint frame after construction completes.
        self._update_intrinsic_lifetime(dt)

    def update_buff_component(self, dt: float) -> None:
        """Run building status expiry after lifetime decay."""
        if not self.is_alive:
            return
        self.update_status_effects(dt)

    def tick_character_object_phase(self, dt: float) -> None:
        """Run only the building character's object-owned phase."""
        if not self.is_alive:
            return
        deployment_combat = self.deploy_delay_remaining > 0 and any(
            mechanic.allows_deployment_combat(self, dt * 1000.0)
            for mechanic in self.mechanics
        )
        self._tick_death_spawn_target_immunity(dt)
        self._tick_pending_projectile_duration(dt)
        if self.deploy_delay_remaining > 0:
            self.deploy_delay_remaining = max(
                0.0,
                self.deploy_delay_remaining - dt,
            )
            if self.deploy_delay_remaining > 1e-9:
                return
            self.deploy_delay_remaining = 0.0
            self.placement_pending = False
            if getattr(self, "_spawn_hook_pending", False):
                self.on_spawn()
            if deployment_combat:
                # Native activation combat precedes the character hide timer.
                self._update_active_combat(dt, self.battle_state)
            for mechanic in self.mechanics:
                mechanic.on_object_tick(self, dt * 1000)
            return
        if getattr(self, "_spawn_hook_pending", False):
            self.on_spawn()
        self._native_deployed_elapsed_ms += max(0, logic_time_milliseconds(dt))
        for mechanic in self.mechanics:
            mechanic.on_object_tick(self, dt * 1000)

    def _update_active_combat(self, dt: float, battle_state: 'BattleState') -> None:
        """Run the building combat component before lifetime and buff ticks."""
        if self._freeze_target_pause_remaining > 0:
            return
        if self._tick_attack_finish(dt):
            return

        if getattr(self, "_is_king_tower", False) and not getattr(self, "_tower_active", True):
            return

        activation_completed = False
        if self.activation_delay_remaining > 0:
            activation_work = min(dt, self.activation_delay_remaining)
            self.activation_delay_remaining = max(
                0.0,
                self.activation_delay_remaining - activation_work,
            )
            if self.activation_delay_remaining <= 1e-9:
                self.activation_delay_remaining = 0.0
            dt -= activation_work
            if dt <= 1e-9:
                return

        if self.activation_first_hit_delay_remaining > 0:
            # This is the building action's one-time post-aim phase, not an
            # ordinary attack wind-up. Native stun resets combat timers but
            # does not rewind or pause an activation action (notably, a King
            # Tower completes its wake-up while Frozen). Keep the phase on its
            # own clock so every status source gets the same behavior.
            activation_hit_work = min(
                dt,
                self.activation_first_hit_delay_remaining,
            )
            self.activation_first_hit_delay_remaining = max(
                0.0,
                self.activation_first_hit_delay_remaining - activation_hit_work,
            )
            dt -= activation_hit_work
            if self.activation_first_hit_delay_remaining > 1e-9:
                return
            # Completion is an event, not a nearly-zero timer. Leaving the
            # floating remainder positive re-arms this shot on the next tick.
            self.activation_first_hit_delay_remaining = 0.0
            activation_completed = True
            # Completion arms the one-time activation shot. If the building is
            # still stunned, the normal stunned branch below retains this
            # readiness until the first legal combat frame after thaw.
            self.attack_cooldown = 0.0
            self._attack_preload_blocked = False
            dt = max(0.0, dt)

        # Call on_tick for all mechanics
        for mechanic in self.mechanics:
            mechanic.on_tick(self, dt * 1000)  # Convert to ms

        # Update last attack time for visualization tracking
        self.last_attack_time += dt
        
        # Buildings use the same keep-target range extension as troops. A
        # newly closer unit does not steal an established Crown
        # Tower/building lock at the fixed-point attack boundary.
        target = (
            battle_state.entities.get(self.target_id)
            if self.target_id is not None
            else None
        )
        pending_retarget = self._pending_damage_retargets_hit(target)
        if (
            target is None
            or not self._is_valid_target(target, is_current_target=True)
            or (
                not self._retains_depleted_combat_target(target)
                and not self.can_affect_target_plane(target)
            )
            or not self.is_within_target_keep_reach(target)
        ):
            self.target_id = None
            target = self.get_nearest_target(battle_state.entities)
            if target is not None and not self.can_attack_target(target):
                target = None
            self.target_id = target.id if target else None
        if activation_completed and target is None:
            # An activation with no available target does not bank an instant
            # shot. A later acquisition uses the ordinary preloaded first hit.
            self.attack_cooldown = max(
                self.attack_cooldown, self.get_preloaded_attack_time_seconds(),
            )
        acquired_from_idle = getattr(self, "_last_combat_target_id", None) is None
        self._note_combat_target(target, preserve_hit=pending_retarget)
        for mechanic in self.mechanics:
            mechanic.on_target_observed(
                self,
                target,
                dt * 1000,
            )
        # Native buildings observe targets before entering their stunned
        # state, just like mobile characters. Keep acquisition live while
        # pausing the attack clock itself.
        if self.is_stunned():
            return
        if acquired_from_idle:
            self._advance_acquisition_load(target, dt)
        target_in_range = bool(
            target is not None
            and self.is_within_attack_clock_reach(target)
        )
        if not target_in_range:
            # A retained pending-damage hit can transfer to an immediate
            # replacement, but an idle building clears that hit timeline.
            # Native Cannon3072 resets2150 to0 while retaining its loaded work.
            from .ordinary_combat_clock import stop_hit

            stop_hit(self)
        self.advance_attack_clock(dt, target_in_range=target_in_range)
        if not target_in_range:
            self._attack_windup_active = False
        else:
            self._attack_windup_active = True
        if target_in_range and self._attack_is_due():
            # Call on_attack_start for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_start(self, target)

            if self.should_cancel_committed_hit(target):
                self._complete_attack_clock_cycle(discarded=True)
                self._attack_windup_active = False
                self._has_attacked_once = True
                self._has_attacked_current_target = True
                self._attack_preload_blocked = False
                self.last_attack_time = 0.0
                return

            # Check if this building uses projectiles
            uses_projectile = self._uses_projectiles()
            if uses_projectile:
                self._create_projectile(target, battle_state)
            else:
                # Direct attack
                self._deal_attack_damage(target, self.damage, battle_state)

            for mechanic in self.mechanics:
                mechanic.on_attack_committed(self, target)

            self._complete_attack_clock_cycle()
            self._attack_windup_active = False
            self._has_attacked_once = True
            self._has_attacked_current_target = True
            self._attack_preload_blocked = False
            self.last_attack_time = 0.0  # Reset for visualization

    def _update_intrinsic_lifetime(self, dt: float) -> None:
        """Tick the native hitpoint component after the combat component."""
        # Lifetime loss is intrinsic hitpoint-component work rather than
        # combat damage. It starts after deployment, continues while a Tesla
        # is underground, and bypasses shields and effect immunities.
        if self.deploy_delay_remaining > 0:
            return
        lifetime_ms = getattr(self.card_stats, 'lifetime_ms', None)
        if lifetime_ms and lifetime_ms > 0:
            self.lifetime_elapsed += dt
            total_tick_ms = self.lifetime_tick_carry_ms + max(0.0, dt * 1000.0)
            native_ticks = int((total_tick_ms + 1e-9) // 50.0)
            self.lifetime_tick_carry_ms = total_tick_ms - native_ticks * 50.0
            # LogicHitpointComponent::setLifeTime stores hundredths of HP
            # consumed per 50 ms tick:
            #   floor(5000 * maxHitpoints / lifetimeMs)
            # The component carries the remainder and removes only whole HP.
            decay_rate = int(
                5000 * int(round(self.max_hitpoints)) // int(lifetime_ms)
            )
            self.lifetime_decay_work += decay_rate * native_ticks
            whole_hp_loss, self.lifetime_decay_work = divmod(
                self.lifetime_decay_work,
                100,
            )
            if whole_hp_loss > 0:
                self.hitpoints = max(0.0, self.hitpoints - whole_hp_loss)
            if self.hitpoints <= 0 and self.is_alive:
                self.is_alive = False
                self.on_death()
    
    def _uses_projectiles(self) -> bool:
        """Check if this building uses projectiles for attacks"""
        return (self.card_stats and 
                hasattr(self.card_stats, 'projectile_data') and 
                self.card_stats.projectile_data is not None)
    
    def _create_projectile(
        self,
        target: Optional['Entity'],
        battle_state: 'BattleState',
        *,
        target_position: Optional[Position] = None,
    ) -> None:
        """Create a projectile toward a live target or explicit aim point."""
        if not self.card_stats or not self.card_stats.projectile_data:
            # Fallback to direct attack if no projectile data
            if target is None:
                return
            # Call on_attack_start for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_start(self, target)

            target.take_damage(self.damage)

            # Call on_attack_hit for all mechanics
            for mechanic in self.mechanics:
                mechanic.on_attack_hit(self, target)
            return

        aim_position = target_position or (
            target.position if target is not None else self.position
        )
        
        # Get projectile properties
        projectile_data = self.card_stats.projectile_data
        projectile_damage = self.damage  # Use entity's scaled damage instead of base projectile damage
        projectile_speed = logic_speed_to_tiles_per_second(
            projectile_data.get('speed', 500)
        )
        splash_radius = projectile_data.get('radius', 0) / 1000.0 if projectile_data.get('radius') else 0.0
        target_buff_data = projectile_data.get("targetBuffData") or {}
        slow_duration = projectile_data.get("buffTime", 0) / 1000.0
        slow_multiplier = 1.0 + (target_buff_data.get("speedMultiplier", 0) / 100.0)
        stun_duration = 0.0
        if (
            target_buff_data.get("speedMultiplier") == -100
            and target_buff_data.get("hitSpeedMultiplier") == -100
            and slow_duration > 0
        ):
            stun_duration = slow_duration
            slow_duration = 0.0
            slow_multiplier = 1.0
        hits_air, hits_ground = serialized_hit_planes(
            projectile_data,
            default_air=self._can_attack_air(),
            default_ground=self._can_attack_ground(),
        )
        crown_tower_damage_multiplier = max(
            0.0, 1.0 + (projectile_data.get("crownTowerDamagePercent", 0) / 100.0)
        )
        crown_tower_damage = None
        for mechanic in self.mechanics:
            resolver = getattr(mechanic, "projectile_crown_tower_damage", None)
            if not callable(resolver):
                continue
            candidate = resolver(self, projectile_damage)
            if candidate is not None:
                crown_tower_damage = float(candidate)
        launch_position, _, _ = self._projectile_launch_geometry_at(
            aim_position
        )
        
        # Create projectile entity
        projectile = Projectile(
            id=battle_state.next_entity_id,
            position=launch_position,
            player_id=self.player_id,
            card_stats=self.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=projectile_damage,
            range=self.range,
            sight_range=1.0,
            target_position=Position(aim_position.x, aim_position.y),
            travel_speed=projectile_speed,
            splash_radius=splash_radius,
            source_name=self.card_stats.name if self.card_stats else "Unknown",
            stun_duration=stun_duration,
            slow_duration=slow_duration,
            slow_multiplier=max(0.0, slow_multiplier),
            knockback_distance=projectile_data.get("pushback", 0) / 1000.0,
            hits_air=hits_air,
            hits_ground=hits_ground,
            crown_tower_damage_multiplier=crown_tower_damage_multiplier,
            crown_tower_damage=crown_tower_damage,
            source_entity=self,
            primary_target=(
                target if target is not None and target.is_alive else None
            ),
            tracks_target=bool(projectile_data.get("homing", True)),
            projectile_range=float(
                projectile_data.get("projectileRange", 0) or 0
            ) / 1000.0,
            homing_time_ms=int(projectile_data.get("homingTime", 0) or 0),
            homing_min_distance=float(
                projectile_data.get("homingMinDistance", 0) or 0
            ) / 1000.0,
            start_extra_radius=float(
                projectile_data.get("projectileStartExtraRadius", 0) or 0
            ) / 1000.0,
            spawn_projectile_data=projectile_data.get("spawnProjectileData"),
        )

        battle_state.entities[projectile.id] = projectile
        battle_state.next_entity_id += 1
        projectile.resolve_start_collision(battle_state)


@dataclass
class Projectile(Entity):
    _pending_damage_registered: bool = field(default=False, init=False, repr=False)
    _pending_damage_launch_duration_ms: int = field(default=0, init=False, repr=False)
    target_position: Position = field(default_factory=lambda: Position(0, 0))
    travel_speed: float = 5.0
    splash_radius: float = 0.0
    source_name: str = "Unknown"  # Name of unit that fired this projectile
    stun_duration: float = 0.0
    slow_duration: float = 0.0
    slow_multiplier: float = 1.0
    knockback_distance: float = 0.0
    knockback_ignores_mass: bool = False
    hits_air: bool = True
    hits_ground: bool = True
    ignore_buildings: bool = False
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: Optional[float] = None
    damage_waves: int = 1
    damage_wave_interval: float = 0.0
    launch_delay: float = 0.0
    damage_group_hit_entity_ids: Optional[set[int]] = field(
        default=None,
        repr=False,
    )
    source_entity: Optional[Entity] = field(default=None, repr=False)
    primary_target: Optional[Entity] = field(default=None, repr=False)
    tracks_target: bool = True
    pierces: bool = False
    projectile_range: float = 0.0
    homing_time_ms: int = 0
    homing_min_distance: float = 0.0
    _temporary_homing_remaining_ms: int = field(default=0, init=False, repr=False)
    _temporary_homing_target: Optional[Entity] = field(
        default=None,
        init=False,
        repr=False,
    )
    _permanent_homing_disabled_by_temporary: bool = field(
        default=False,
        init=False,
        repr=False,
    )
    hit_entity_ids: set[int] = field(default_factory=set, repr=False)
    launch_position: Optional[Position] = field(default=None, repr=False)
    start_extra_radius: float = 0.0
    start_collision_resolved: bool = field(default=False, repr=False)
    spawn_projectile_data: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.launch_position is None:
            self.launch_position = Position(self.position.x, self.position.y)
        self._initialize_temporary_homing()
        target_battle = getattr(self.primary_target, "battle_state", None)
        if not getattr(target_battle, "_logic_tick_active", False):
            self.activate_pending_damage()

    def _initialize_temporary_homing(self) -> None:
        """Install native HomingTime only beyond its strict launch distance."""
        target = self.primary_target
        homing_time_ms = max(0, int(self.homing_time_ms))
        if target is None or homing_time_ms <= 0:
            return
        dx_units = (
            tiles_to_logic_units(target.position.x)
            - tiles_to_logic_units(self.position.x)
        )
        dy_units = (
            tiles_to_logic_units(target.position.y)
            - tiles_to_logic_units(self.position.y)
        )
        launch_distance_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        minimum_units = tiles_to_logic_units(self.homing_min_distance)
        if launch_distance_units <= minimum_units:
            return
        self._temporary_homing_remaining_ms = homing_time_ms
        self._temporary_homing_target = target

    def _update_homing_for_logic_tick(self) -> None:
        """Apply native temporary steering before ordinary projectile motion."""
        if self._temporary_homing_remaining_ms > 0:
            target = self._temporary_homing_target
            if target is None:
                self._temporary_homing_remaining_ms = 0
            else:
                target_x_units = tiles_to_logic_units(target.position.x)
                target_y_units = tiles_to_logic_units(target.position.y)
                current_x_units = tiles_to_logic_units(self.position.x)
                current_y_units = tiles_to_logic_units(self.position.y)
                endpoint_x_units = target_x_units
                endpoint_y_units = target_y_units
                projectile_range_units = tiles_to_logic_units(
                    self.projectile_range
                )
                if projectile_range_units > 0:
                    ray_x_units, ray_y_units = normalized_vector_logic_units(
                        target_x_units - current_x_units,
                        target_y_units - current_y_units,
                        projectile_range_units,
                    )
                    endpoint_x_units = current_x_units + ray_x_units
                    endpoint_y_units = current_y_units + ray_y_units
                    # LogicProjectile::setTargetPosition clears its ordinary
                    # homing pointer after installing a finite directed ray.
                    self._permanent_homing_disabled_by_temporary = True
                self.target_position = Position(
                    logic_units_to_tiles(endpoint_x_units),
                    logic_units_to_tiles(endpoint_y_units),
                )
                self._temporary_homing_remaining_ms -= 50
            return

        if (
            self.tracks_target
            and not self._permanent_homing_disabled_by_temporary
            and self.primary_target is not None
        ):
            self.target_position = Position(
                self.primary_target.position.x,
                self.primary_target.position.y,
            )

    @property
    def reserves_pending_damage(self) -> bool:
        """Whether native Homing bookkeeping reserves the primary target."""
        return self.tracks_target and self._pending_damage_registered

    def _native_pending_damage_duration_ms(self) -> int:
        """Return the launch duration recorded by LogicProjectile::init."""
        target = self.primary_target
        if target is None:
            return 0
        dx_units = tiles_to_logic_units(target.position.x - self.position.x)
        dy_units = tiles_to_logic_units(target.position.y - self.position.y)
        distance_units = math.isqrt(dx_units * dx_units + dy_units * dy_units)
        speed_units = tiles_per_second_to_logic_speed(self.travel_speed)
        # LogicProjectile first truncates distance * 50 / serialized speed.
        # LogicObject then rounds that duration up to the next 50 ms frame and
        # caps the remembered maximum at one second.
        return pending_projectile_duration_ms(distance_units, speed_units)

    def _register_pending_damage_duration(self) -> None:
        target = self.primary_target
        if target is None or not self.reserves_pending_damage:
            return
        target._pending_projectile_max_duration_ms = max(
            int(target._pending_projectile_max_duration_ms),
            self._pending_damage_launch_duration_ms,
        )

    def activate_pending_damage(self) -> None:
        """Publish a new shot after the current combat component phase."""
        if self._pending_damage_registered:
            return
        # Registration follows character movement on the launch frame.
        # Measure here so that movement across a duration boundary is visible.
        self._pending_damage_launch_duration_ms = self._native_pending_damage_duration_ms()
        self._pending_damage_registered = True
        self._register_pending_damage_duration()

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update projectile - move towards target"""
        if not self.is_alive:
            return

        if self.launch_delay > 0.0:
            if dt <= self.launch_delay + 1e-12:
                self.launch_delay = max(0.0, self.launch_delay - dt)
                return
            dt -= self.launch_delay
            self.launch_delay = 0.0

        if self.pierces:
            self._update_piercing(dt, battle_state)
            return

        self._update_homing_for_logic_tick()

        if self._reaches_target_this_update(dt):
            # Commit every impact that reaches on this server frame before
            # resolving damage, so reciprocal projectiles can still trade.
            hit_targets = self._collect_splash_targets(battle_state)
            if getattr(battle_state, "_defer_projectile_impacts", False):
                battle_state.queue_projectile_impact(self, hit_targets)
            else:
                self._resolve_impact(battle_state, hit_targets)
        else:
            self._move_towards(self.target_position, dt)

    def _reaches_target_this_update(self, dt: float) -> bool:
        """Use native integer distance and speed work for an arrival frame."""
        dx_units = tiles_to_logic_units(
            self.target_position.x - self.position.x
        )
        dy_units = tiles_to_logic_units(
            self.target_position.y - self.position.y
        )
        remaining_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        travel_units = speed_work_for_duration(
            tiles_per_second_to_logic_speed(self.travel_speed),
            dt,
        )
        return remaining_units <= travel_units

    def _update_piercing(self, dt: float, battle_state: 'BattleState') -> None:
        """Advance a line projectile through native 50 ms collision samples."""
        self.resolve_start_collision(battle_state)
        remaining_dt = max(0.0, float(dt))
        while self.is_alive and remaining_dt > 1e-12:
            step_dt = min(LOGIC_TICK_SECONDS, remaining_dt)
            self._update_piercing_tick(step_dt, battle_state)
            remaining_dt -= step_dt

    def resolve_start_collision(self, battle_state: 'BattleState') -> None:
        """Apply a juggernaut projectile's one-time enlarged launch hitbox."""
        if self.start_collision_resolved:
            return
        self.start_collision_resolved = True
        if (
            not self.is_alive
            or not self.pierces
            or self.splash_radius <= 0.0
            or self.start_extra_radius <= 0.0
        ):
            return
        hit_targets = self._damage_piercing_targets_at(
            battle_state,
            self.position,
            self.splash_radius + self.start_extra_radius,
        )
        if self.source_entity is not None:
            for hit_target in hit_targets:
                self._notify_source_hit(hit_target)

    def _update_piercing_tick(
        self,
        dt: float,
        battle_state: 'BattleState',
    ) -> None:
        """Run one native projectile movement and endpoint collision check."""
        self._update_homing_for_logic_tick()
        dx_units = tiles_to_logic_units(
            self.target_position.x - self.position.x
        )
        dy_units = tiles_to_logic_units(
            self.target_position.y - self.position.y
        )
        remaining_units = math.isqrt(
            dx_units * dx_units + dy_units * dy_units
        )
        travel_units = speed_work_for_duration(
            tiles_per_second_to_logic_speed(self.travel_speed),
            dt,
        )
        reached_endpoint = remaining_units <= travel_units
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            travel_units,
        )
        self.position = Position(
            logic_units_to_tiles(
                tiles_to_logic_units(self.position.x) + move_x_units
            ),
            logic_units_to_tiles(
                tiles_to_logic_units(self.position.y) + move_y_units
            ),
        )
        hit_targets = self._damage_piercing_targets_at(
            battle_state,
            self.position,
            self.splash_radius,
        )
        if self.source_entity is not None:
            for hit_target in hit_targets:
                self._notify_source_hit(hit_target)
        if reached_endpoint:
            self.is_alive = False

    def _damage_piercing_targets_at(
        self,
        battle_state: 'BattleState',
        position: Position,
        projectile_radius: float,
    ) -> List['Entity']:
        """Damage each eligible object intersecting one projectile sample."""
        hit_targets: List[Entity] = []
        source_kind = getattr(self, "spell_name", None) or self.source_name
        for entity in list(battle_state.entities.values()):
            if (
                entity.id in self.hit_entity_ids
                or not self._can_damage(entity)
                or not entity.can_receive_area_damage(
                    source_kind,
                    source_entity=self.source_entity,
                )
            ):
                continue
            if entity.intersects_native_area(position, projectile_radius):
                self.hit_entity_ids.add(entity.id)
                self._damage_target(entity, battle_state)
                hit_targets.append(entity)
        return hit_targets

    def _notify_source_hit(self, target: 'Entity') -> None:
        """Run hit hooks with the immutable launch geometry in scope."""
        source = self.source_entity
        if source is None:
            return
        source._attack_impact_origin = Position(
            self.launch_position.x,
            self.launch_position.y,
        )
        source._attack_impact_position = Position(
            target.position.x,
            target.position.y,
        )
        try:
            for mechanic in source.mechanics:
                mechanic.on_attack_hit(source, target)
        finally:
            source.__dict__.pop("_attack_impact_origin", None)
            source.__dict__.pop("_attack_impact_position", None)

    def _move_towards(self, target_pos: Position, dt: float) -> None:
        """Move toward a target using integer logic-unit components."""
        dx_units = tiles_to_logic_units(target_pos.x - self.position.x)
        dy_units = tiles_to_logic_units(target_pos.y - self.position.y)
        speed = tiles_per_second_to_logic_speed(self.travel_speed)
        move_x_units, move_y_units = vector_towards_logic_units(
            dx_units,
            dy_units,
            speed_work_for_duration(speed, dt),
        )
        self.position.x = logic_units_to_tiles(
            tiles_to_logic_units(self.position.x) + move_x_units
        )
        self.position.y = logic_units_to_tiles(
            tiles_to_logic_units(self.position.y) + move_y_units
        )

    def _collect_splash_targets(self, battle_state: 'BattleState') -> List['Entity']:
        """Snapshot eligible entities overlapped by this committed impact."""
        hit_targets: List[Entity] = []
        if self.splash_radius <= 0 and self.primary_target is not None:
            target = self.primary_target
            if self._can_damage(target):
                hit_targets.append(target)
            return hit_targets

        for entity in list(battle_state.entities.values()):
            if not self._can_damage(entity):
                continue
            source_kind = getattr(self, "spell_name", None) or self.source_name
            if not entity.can_receive_area_damage(
                source_kind,
                source_entity=self.source_entity,
            ):
                continue
            if (
                self.damage_group_hit_entity_ids is not None
                and entity.id in self.damage_group_hit_entity_ids
            ):
                continue

            # Use hitbox-based collision detection for more accurate splash damage
            if self._hitbox_overlaps_with_splash(entity):
                hit_targets.append(entity)
                if self.damage_group_hit_entity_ids is not None:
                    self.damage_group_hit_entity_ids.add(entity.id)
        return hit_targets

    def _deal_splash_damage(self, battle_state: 'BattleState') -> List['Entity']:
        """Resolve splash immediately for carrier-projectile subclasses."""
        hit_targets = self._collect_splash_targets(battle_state)
        for target in hit_targets:
            self._damage_target(
                target,
                battle_state,
                apply_status=self.splash_radius <= 0.0,
            )
        if self.splash_radius > 0.0:
            self._apply_splash_statuses(battle_state)
        return hit_targets

    def _resolve_impact(
        self,
        battle_state: 'BattleState',
        hit_targets: List['Entity'] | tuple['Entity', ...],
    ) -> None:
        """Apply a previously committed impact to its snapshotted targets."""
        for target in hit_targets:
            self._damage_target(
                target,
                battle_state,
                apply_status=self.splash_radius <= 0.0,
            )
        if self.splash_radius > 0.0:
            self._apply_splash_statuses(battle_state)
        impact_target = self.primary_target
        if impact_target is None or impact_target not in hit_targets:
            impact_target = hit_targets[0] if hit_targets else None
        if self.source_entity is not None and impact_target is not None:
            self._notify_source_hit(impact_target)
        self._spawn_impact_projectiles(battle_state)
        self._schedule_remaining_damage_waves(battle_state)
        self.is_alive = False

    def _spawn_impact_projectiles(self, battle_state: 'BattleState') -> None:
        """Create serialized child projectiles at this projectile's endpoint."""
        data = self.spawn_projectile_data or {}
        count = int(data.get("spawnCount", 0) or 0)
        projectile_range = float(data.get("projectileRange", 0) or 0) / 1000.0
        travel_speed = logic_speed_to_tiles_per_second(
            float(data.get("speed", 0) or 0)
        )
        if count <= 0 or projectile_range <= 0 or travel_speed <= 0:
            return

        base_damage = float(data.get("damage", 0) or 0)
        scaler = getattr(getattr(self.source_entity, "card_stats", None), "get_scaled_stat", None)
        damage = float(scaler(base_damage)) if callable(scaler) else base_damage
        if damage <= 0:
            return

        dx_units = tiles_to_logic_units(
            self.target_position.x - self.launch_position.x
        )
        dy_units = tiles_to_logic_units(
            self.target_position.y - self.launch_position.y
        )
        base_angle = logic_vector_angle(dx_units, dy_units)
        spawn_radius = int(data.get("spawnRadius", 0) or 0)
        projectile_range_units = tiles_to_logic_units(projectile_range)

        hit_radius = float(
            data.get("projectileRadius", data.get("radius", 0)) or 0
        ) / 1000.0
        hits_air, hits_ground = serialized_hit_planes(
            data,
            default_air=self.hits_air,
            default_ground=self.hits_ground,
        )
        crown_tower_damage_multiplier = max(
            0.0, 1.0 + float(data.get("crownTowerDamagePercent", 0) or 0) / 100.0
        )

        for index in range(count):
            angle_offset_degrees = 0
            if count > 1 and spawn_radius:
                angle_offset_degrees = trunc_div(
                    (index - count // 2) * spawn_radius,
                    count,
                )
            offset_x_units, offset_y_units = rotate_logic_vector(
                projectile_range_units,
                0,
                base_angle + angle_offset_degrees,
            )
            endpoint = Position(
                self.target_position.x
                + logic_units_to_tiles(offset_x_units),
                self.target_position.y
                + logic_units_to_tiles(offset_y_units),
            )
            child = Projectile(
                id=battle_state.next_entity_id,
                position=Position(self.target_position.x, self.target_position.y),
                player_id=self.player_id,
                card_stats=self.card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=damage,
                range=projectile_range,
                sight_range=0.0,
                target_position=endpoint,
                travel_speed=travel_speed,
                splash_radius=hit_radius,
                source_name=self.source_name,
                hits_air=hits_air,
                hits_ground=hits_ground,
                crown_tower_damage_multiplier=crown_tower_damage_multiplier,
                tracks_target=False,
                pierces=True,
                start_extra_radius=float(
                    data.get("projectileStartExtraRadius", 0) or 0
                ) / 1000.0,
            )
            battle_state.entities[child.id] = child
            battle_state.next_entity_id += 1
            # Reserve the projectile's ID before resolving a start collision.
            # A lethal collision can synchronously create death-spawned
            # characters; those callbacks must not overwrite this projectile.
            child.resolve_start_collision(battle_state)

    def _can_damage(self, entity: 'Entity') -> bool:
        if entity.player_id == self.player_id or not entity.is_alive:
            return False
        if getattr(entity, "entity_kind", 4) in {2, 3}:
            return False
        if self.ignore_buildings and isinstance(entity, Building):
            return False
        # A direct shot committed before a river jump still reaches its target.
        # Fresh area queries retain their plane filter; effect immunity is
        # checked separately when the hit is applied.
        if (
            self.primary_target is entity
            and self.splash_radius == 0
            and not self.pierces
            and getattr(entity, "_river_jump_active", False)
            and self.hits_ground
        ):
            return True
        is_air = is_airborne_target(entity)
        return self.hits_air if is_air else self.hits_ground

    def expected_damage_against(self, entity: 'Entity') -> float:
        """Return this projectile's committed direct damage for reservation."""
        damage = float(self.damage)
        if isinstance(entity, Building) and getattr(entity.card_stats, 'name', None) in {"Tower", "KingTower"}:
            damage = (
                float(self.crown_tower_damage)
                if self.crown_tower_damage is not None
                else native_percent_damage(
                    damage,
                    self.crown_tower_damage_multiplier,
                )
            )
        return max(0.0, damage)

    def _damage_target(
        self,
        entity: 'Entity',
        battle_state: 'BattleState',
        *,
        apply_status: bool = True,
    ) -> None:
        source_kind = getattr(self, "spell_name", None) or self.source_name
        # A stored homing target does not bypass impact-time effect immunity.
        affects_hidden = False
        if not entity.can_receive_effect(
            source_kind,
            affects_hidden=affects_hidden,
        ):
            return
        damage = self.expected_damage_against(entity)
        entity.take_damage(
            damage,
            source_kind=source_kind,
            affects_hidden=affects_hidden,
        )
        if apply_status:
            self._apply_status_to_target(
                entity,
                source_kind,
                affects_hidden=affects_hidden,
            )
        if self.knockback_distance > 0 and not isinstance(entity, Building):
            self._apply_knockback(entity, battle_state)

    def _apply_status_to_target(
        self,
        entity: 'Entity',
        source_kind: str,
        *,
        affects_hidden: bool = False,
    ) -> None:
        if self.stun_duration > 0:
            entity.apply_stun(
                self.stun_duration,
                source_kind=source_kind,
                affects_hidden=affects_hidden,
            )
        if self.slow_duration > 0 and self.slow_multiplier < 1.0:
            entity.apply_slow(
                self.slow_duration,
                self.slow_multiplier,
                source_kind=source_kind,
                affects_hidden=affects_hidden,
            )

    def _apply_splash_statuses(self, battle_state: 'BattleState') -> None:
        """Run the projectile's fresh post-damage area-buff query."""
        if self.stun_duration <= 0 and (
            self.slow_duration <= 0 or self.slow_multiplier >= 1.0
        ):
            return
        source_kind = getattr(self, "spell_name", None) or self.source_name
        for entity in list(battle_state.entities.values()):
            if not self._can_damage(entity):
                continue
            if (
                not self._hitbox_overlaps_with_splash(entity)
                or not entity.can_receive_area_damage(
                    source_kind,
                    source_entity=self.source_entity,
                )
            ):
                continue
            self._apply_status_to_target(entity, source_kind)

    def _schedule_remaining_damage_waves(self, battle_state: 'BattleState') -> None:
        remaining = max(0, int(self.damage_waves) - 1)
        if remaining <= 0 or self.damage_wave_interval <= 0:
            return
        pulse = AreaEffect(
            id=battle_state.next_entity_id,
            position=Position(self.target_position.x, self.target_position.y),
            player_id=self.player_id,
            card_stats=None,
            hitpoints=1,
            max_hitpoints=1,
            damage=self.damage,
            range=self.splash_radius,
            sight_range=self.splash_radius,
            duration=self.damage_wave_interval * remaining,
            radius=self.splash_radius,
            hits_air=self.hits_air,
            hits_ground=self.hits_ground,
            crown_tower_damage_multiplier=self.crown_tower_damage_multiplier,
            crown_tower_damage=self.crown_tower_damage,
            damage_tick_interval=self.damage_wave_interval,
            max_damage_ticks=remaining,
            damage_on_spawn=False,
        )
        pulse.spell_name = getattr(self, "spell_name", self.source_name)
        battle_state.entities[pulse.id] = pulse
        battle_state.next_entity_id += 1

    def _apply_knockback(self, entity: 'Entity', battle_state: 'BattleState') -> None:
        """Push entity away from impact center."""
        from .mechanics.shared.knockback import apply_radial_knockback

        apply_radial_knockback(
            entity,
            battle_state,
            self.target_position,
            self.knockback_distance,
            source_kind=getattr(self, "spell_name", None) or self.source_name,
            ignores_mass=self.knockback_ignores_mass,
            fallback_direction=(
                self.target_position.x - self.position.x,
                self.target_position.y - self.position.y,
            ),
        )

    def _hitbox_overlaps_with_splash(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with splash damage radius"""
        return entity.intersects_native_area(
            self.target_position,
            self.splash_radius,
        )


@dataclass
class ChainLightning(Entity):
    """A travelling chain bolt that chooses the nearest unvisited target."""

    origin: Position = field(default_factory=lambda: Position(0, 0))
    remaining_bounces: int = 0
    chain_range: float = 4.0
    travel_speed: float = logic_speed_to_tiles_per_second(2000.0)
    fixed_hop_duration: Optional[float] = None
    hop_time_remaining: float = 0.0
    stun_duration: float = 0.5
    visited_ids: set[int] = field(default_factory=set)
    hits_air: bool = True
    hits_ground: bool = True
    current_target_id: Optional[int] = None

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        if not self.is_alive:
            return

        remaining_time = max(0.0, dt)
        while self.remaining_bounces > 0:
            target = (
                battle_state.entities.get(self.current_target_id)
                if self.current_target_id is not None
                else None
            )
            if target is None:
                target = self._find_next_target(battle_state)
                if target is None:
                    self.is_alive = False
                    return
                self.current_target_id = target.id
                if self.fixed_hop_duration is not None:
                    self.hop_time_remaining = max(0.0, self.fixed_hop_duration)

            if not self._can_chain_to(target):
                # A chosen target that disappears or becomes untargetable while
                # the bolt is in flight terminates that branch. It must not
                # teleport back to the last impact and select a replacement.
                self.is_alive = False
                return

            target_position = Position(target.position.x, target.position.y)
            dx_units = tiles_to_logic_units(
                target_position.x - self.position.x
            )
            dy_units = tiles_to_logic_units(
                target_position.y - self.position.y
            )
            distance_units = math.isqrt(
                dx_units * dx_units + dy_units * dy_units
            )
            time_to_impact = (
                self.hop_time_remaining
                if self.fixed_hop_duration is not None
                else (
                    distance_units
                    * LOGIC_TICK_SECONDS
                    / max(
                        tiles_per_second_to_logic_speed(self.travel_speed),
                        1,
                    )
                )
            )
            if remaining_time + 1e-12 < time_to_impact:
                if self.fixed_hop_duration is not None:
                    # Fixed-time links interpolate each integer logic
                    # component by the fraction of hop time consumed. Avoid
                    # deriving a float Euclidean speed here: mirrored negative
                    # vectors can otherwise straddle a half-unit ``round`` and
                    # place the two bolts one logic unit apart.
                    duration_units = max(
                        1,
                        round(time_to_impact * 1_000_000_000),
                    )
                    consumed_units = max(
                        0,
                        min(
                            duration_units,
                            round(remaining_time * 1_000_000_000),
                        ),
                    )
                    move_x_units = trunc_div(
                        dx_units * consumed_units,
                        duration_units,
                    )
                    move_y_units = trunc_div(
                        dy_units * consumed_units,
                        duration_units,
                    )
                    self.hop_time_remaining = max(
                        0.0,
                        self.hop_time_remaining - remaining_time,
                    )
                    self.position.x = logic_units_to_tiles(
                        tiles_to_logic_units(self.position.x) + move_x_units
                    )
                    self.position.y = logic_units_to_tiles(
                        tiles_to_logic_units(self.position.y) + move_y_units
                    )
                    return
                else:
                    speed = tiles_per_second_to_logic_speed(self.travel_speed)
                move_x_units, move_y_units = vector_towards_logic_units(
                    tiles_to_logic_units(target_position.x - self.position.x),
                    tiles_to_logic_units(target_position.y - self.position.y),
                    speed_work_for_duration(speed, remaining_time),
                )
                self.position.x = logic_units_to_tiles(
                    tiles_to_logic_units(self.position.x) + move_x_units
                )
                self.position.y = logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y) + move_y_units
                )
                return

            self.position = target_position
            remaining_time = max(0.0, remaining_time - time_to_impact)
            self.hop_time_remaining = 0.0
            source_kind = getattr(getattr(self, "card_stats", None), "name", None)
            self.visited_ids.add(target.id)
            if target.can_receive_effect(source_kind):
                target.take_damage(self.damage, source_kind=source_kind)
                target.apply_stun(self.stun_duration, source_kind=source_kind)
            self.origin = Position(target.position.x, target.position.y)
            self.remaining_bounces -= 1
            self.current_target_id = None
            if remaining_time <= 0:
                break
        if self.remaining_bounces <= 0:
            self.is_alive = False

    def _can_chain_to(self, entity: Entity) -> bool:
        if (
            entity.id in self.visited_ids
            or entity.player_id == self.player_id
            or not entity.is_alive
            or getattr(entity, "entity_kind", 4) in {2, 3}
            or not entity.is_secondary_effect_targetable_by(self.player_id)
        ):
            return False
        is_air = is_airborne_target(entity)
        return self.hits_air if is_air else self.hits_ground

    def _find_next_target(self, battle_state: 'BattleState') -> Optional[Entity]:
        candidates: list[tuple[Entity, float]] = []
        for entity in battle_state.entities.values():
            if not self._can_chain_to(entity):
                continue
            distance = self.native_target_distance_from(self.origin, entity)
            if distance <= self.chain_range + 1e-9:
                candidates.append((entity, distance))
        if not candidates:
            return None
        return self._select_nearest_target(candidates)




@dataclass
class AreaEffect(Entity):
    """Area effect spells that stay on the ground for a duration"""
    duration: float = 4.0
    freeze_effect: bool = False
    speed_multiplier: float = 1.0
    attack_speed_multiplier: Optional[float] = None
    spawn_speed_multiplier: Optional[float] = None
    radius: float = 3.0
    time_alive: float = 0.0
    hits_air: bool = True
    hits_ground: bool = True
    affects_hidden: bool = False
    crown_tower_damage_multiplier: float = 1.0
    building_damage_multiplier: float = 1.0
    crown_tower_damage: Optional[float] = None
    building_damage: Optional[float] = None
    damage_tick_interval: float = 0.0
    initial_damage_delay: Optional[float] = None
    max_damage_ticks: int = 0
    damage_on_spawn: bool = False
    slows_attack_speed: bool = True
    slows_spawn_speed: bool = True
    slow_refresh_duration: float = 0.25
    effect_tick_interval: float = 0.05
    effect_on_spawn_only: bool = False
    effect_snapshot_applied: bool = False
    cap_buff_time_to_effect: bool = False
    target_local_damage: bool = False
    periodic_damage_buff_duration: float = 0.0
    periodic_damage_controlled_by_parent: bool = False
    damage_ticks_applied: int = 0
    next_damage_time: Optional[float] = None
    next_effect_time: Optional[float] = None
    freeze_targets_applied: bool = False
    
    # Controlled attraction fields from CharacterBuffData. Tornado currently
    # derives its vector entirely from each target's serialized base speed;
    # its PushMassFactor is unset.
    attract_percentage: float = 0.0
    push_speed_factor: float = 0.0
    is_tornado: bool = False
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update area effect - apply effects and check duration"""
        if not self.is_alive:
            return
        
        previous_time = self.time_alive
        active_dt = min(dt, max(0.0, self.duration - previous_time))
        self.time_alive += dt
        
        if self.next_damage_time is None and self.max_damage_ticks > 0:
            self.next_damage_time = (
                self.initial_damage_delay
                if self.initial_damage_delay is not None
                else (
                    0.0
                    if self.damage_on_spawn
                    else self.damage_tick_interval
                )
            )

        # LogicAreaEffectObject completes every damage/knockback iteration
        # before it asks the manager for buff targets. The second query sees
        # children created by lethal damage on this same object tick.
        if self.max_damage_ticks > 0 and self.next_damage_time is not None:
            while (
                self.damage_ticks_applied < self.max_damage_ticks
                and self.next_damage_time <= min(self.time_alive, self.duration) + 1e-9
            ):
                self._apply_damage_tick(battle_state, self.damage)
                self.damage_ticks_applied += 1
                self.next_damage_time += self.damage_tick_interval
        elif (
            not self.target_local_damage
            and self.damage > 0
            and self.time_alive <= self.duration + 1e-9
        ):
            # Compatibility for non-scheduled auras: damage is serialized as
            # damage-per-second and integrated over the simulation step.
            self._apply_damage_tick(battle_state, self.damage * active_dt)

        # Freeze snapshots targets once at impact. Its visual area remains for
        # the duration, but troops deployed or moved into it later are not
        # affected. Pulls and slows from other area effects remain continuous.
        if self.freeze_effect and not self.freeze_targets_applied:
            self._apply_freeze_snapshot(battle_state)
            self.freeze_targets_applied = True
        elif (
            active_dt > 0
            and not self.freeze_effect
            and self.effect_on_spawn_only
            and not self.effect_snapshot_applied
        ):
            self._apply_continuous_effects(
                active_dt,
                battle_state,
                effect_time_remaining=max(0.0, self.duration - self.time_alive),
            )
            self.effect_snapshot_applied = True
        elif active_dt > 0 and not self.freeze_effect and not self.effect_on_spawn_only:
            # Serialized negative sentinels and zero intervals must not make
            # a recurring deadline stand still or move backward.
            effect_interval = (
                self.effect_tick_interval
                if self.effect_tick_interval > 0
                else LOGIC_TICK_SECONDS
            )
            if self.next_effect_time is None:
                self.next_effect_time = max(
                    LOGIC_TICK_SECONDS,
                    effect_interval,
                )
            effect_deadline = min(self.time_alive, self.duration)
            while (
                self.next_effect_time <= effect_deadline + 1e-9
                and self.next_effect_time < self.duration - 1e-9
            ):
                self._apply_continuous_effects(
                    effect_interval,
                    battle_state,
                    effect_time_remaining=max(
                        0.0,
                        self.duration - self.next_effect_time,
                    ),
                )
                self.next_effect_time += effect_interval

        if self.time_alive >= self.duration - 1e-9:
            self.is_alive = False

    def _apply_freeze_snapshot(self, battle_state: 'BattleState') -> None:
        source_kind = getattr(self, "spell_name", None)
        expiry_time = battle_state.time + self.duration
        for entity in list(battle_state.entities.values()):
            effect_container = getattr(entity, "entity_kind", 4) in {2, 3}
            freeze_carrier = bool(
                effect_container
                and getattr(entity, "carries_freeze_to_children", False)
            )
            if (
                entity.player_id == self.player_id
                or not entity.is_alive
                or (effect_container and not freeze_carrier)
            ):
                continue
            if self.hits_ground and not self.hits_air and is_above_ground_surface(entity):
                continue
            is_air = is_airborne_target(entity)
            if (is_air and not self.hits_air) or ((not is_air) and not self.hits_ground):
                continue
            if not self._hitbox_overlaps_with_radius(entity):
                continue
            if not entity.can_receive_effect(
                source_kind,
                affects_hidden=self.affects_hidden,
            ):
                continue
            if freeze_carrier:
                # Character-carrying containers preserve the snapshot for
                # their children without pausing the serialized fall/open
                # countdown.
                entity.freeze_expiry_time = max(
                    entity.freeze_expiry_time,
                    expiry_time,
                )
                continue
            entity.apply_stun(
                self.duration,
                source_kind=source_kind,
                affects_hidden=self.affects_hidden,
            )
            entity.apply_slow(
                self.duration,
                0.0,
                source_kind=source_kind,
                affects_hidden=self.affects_hidden,
            )
            entity.freeze_expiry_time = max(entity.freeze_expiry_time, expiry_time)

    def _apply_continuous_effects(
        self,
        dt: float,
        battle_state: 'BattleState',
        *,
        effect_time_remaining: float,
    ) -> None:
        from .unit_traits import is_in_transit

        for entity in list(battle_state.entities.values()):
            effect_container = getattr(entity, "entity_kind", 4) in {2, 3}
            area_displaceable = bool(
                self.is_tornado
                and getattr(entity, "area_displaceable", False)
            )
            if (
                entity.player_id == self.player_id
                or not entity.is_alive
                or (effect_container and not area_displaceable)
                or (
                    self.is_tornado
                    and is_in_transit(entity)
                    and not getattr(entity, "_river_jump_active", False)
                )
            ):
                continue

            if self.hits_ground and not self.hits_air and is_above_ground_surface(entity):
                continue

            is_air = is_airborne_target(entity)
            if is_air and not self.hits_air:
                continue
            if (not is_air) and not self.hits_ground:
                continue
            
            # Use hitbox-based collision detection  
            if self._hitbox_overlaps_with_radius(entity):
                distance = entity.position.distance_to(self.position)
                source_kind = getattr(self, "spell_name", None)
                if not entity.can_receive_effect(
                    source_kind,
                    affects_hidden=self.affects_hidden,
                ):
                    continue
                
                # Apply tornado pull effect
                if (
                    self.is_tornado
                    and self.attract_percentage > 0
                ):
                    self._apply_tornado_pull(entity, distance, dt, battle_state)

                # A displaceable effect container participates only in the
                # pull. It is still not a combat/status target.
                if effect_container:
                    continue

                if (
                    self.target_local_damage
                    and self.damage > 0
                    and self.damage_tick_interval > 0
                    and entity.can_receive_area_damage(
                        source_kind,
                        affects_hidden=self.affects_hidden,
                    )
                ):
                    entity.apply_periodic_damage(
                        source_id=self.id,
                        source_kind=source_kind,
                        duration=self.periodic_damage_buff_duration,
                        hit_interval=self.damage_tick_interval,
                        damage=self._damage_for_target(entity, self.damage),
                        hard_duration=(
                            effect_time_remaining
                            if self.periodic_damage_controlled_by_parent
                            else None
                        ),
                        affects_hidden=self.affects_hidden,
                    )
                
                attack_multiplier = (
                    self.attack_speed_multiplier
                    if self.attack_speed_multiplier is not None
                    else (
                        self.speed_multiplier
                        if self.slows_attack_speed
                        else 1.0
                    )
                )
                spawn_multiplier = (
                    self.spawn_speed_multiplier
                    if self.spawn_speed_multiplier is not None
                    else (
                        self.speed_multiplier
                        if self.slows_spawn_speed
                        else 1.0
                    )
                )
                if min(
                    self.speed_multiplier,
                    attack_multiplier,
                    spawn_multiplier,
                ) < 1.0:
                    refresh_duration = max(dt, self.slow_refresh_duration)
                    if self.cap_buff_time_to_effect:
                        refresh_duration = min(
                            refresh_duration,
                            effect_time_remaining,
                        )
                    if refresh_duration > 1e-9:
                        if (
                            self.speed_multiplier == 0.0
                            and attack_multiplier == 0.0
                            and spawn_multiplier == 0.0
                        ):
                            entity.apply_stun(
                                refresh_duration,
                                source_kind=source_kind,
                                affects_hidden=self.affects_hidden,
                            )
                        else:
                            entity.apply_slow(
                                refresh_duration,
                                self.speed_multiplier,
                                attack_speed_multiplier=attack_multiplier,
                                spawn_speed_multiplier=spawn_multiplier,
                                source_kind=source_kind,
                                affects_hidden=self.affects_hidden,
                            )

    def _damage_for_target(self, entity: Entity, amount: float) -> float:
        if not isinstance(entity, Building):
            return amount
        if getattr(entity.card_stats, 'name', None) in {"Tower", "KingTower"}:
            return (
                self.crown_tower_damage
                if self.crown_tower_damage is not None
                else native_percent_damage(
                    amount,
                    self.crown_tower_damage_multiplier,
                )
            )
        return (
            self.building_damage
            if self.building_damage is not None
            else native_percent_damage(
                amount,
                self.building_damage_multiplier,
            )
        )

    def _apply_damage_tick(self, battle_state: 'BattleState', amount: float) -> None:
        if amount <= 0:
            return
        source_kind = getattr(self, "spell_name", None)
        targets: list[tuple[Entity, float]] = []
        for entity in list(battle_state.entities.values()):
            if (
                entity.player_id == self.player_id
                or not entity.is_alive
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue
            if self.hits_ground and not self.hits_air and is_above_ground_surface(entity):
                continue
            is_air = is_airborne_target(entity)
            if (is_air and not self.hits_air) or ((not is_air) and not self.hits_ground):
                continue
            if not self._hitbox_overlaps_with_radius(
                entity
            ) or not entity.can_receive_area_damage(
                source_kind,
                affects_hidden=self.affects_hidden,
            ):
                continue
            targets.append((entity, self._damage_for_target(entity, amount)))

        # A pulse commits its complete footprint at one instant. Resolving an
        # early victim's death effect must not move a later victim out of that
        # already-committed pulse merely because it had a larger entity id.
        for entity, damage in targets:
            entity.take_damage(
                damage,
                source_kind=source_kind,
                affects_hidden=self.affects_hidden,
            )

    def _apply_tornado_pull(self, entity: 'Entity', distance: float, dt: float, battle_state: 'BattleState') -> None:
        """Queue the serialized controlled-attraction vector."""
        if distance == 0 or isinstance(entity, Building):
            return
        
        # Calculate pull vector towards tornado center
        dx = self.position.x - entity.position.x
        dy = self.position.y - entity.position.y
        
        # CharacterBuffData uses the target character's base Speed, not its
        # current slowed/raged movement value. Native Speed is logic units per
        # 50 ms frame, with 1000 units per arena tile.
        base_speed = float(
            getattr(getattr(entity, "card_stats", None), "speed", 0.0) or 0.0
        )
        pull_units_per_tick = int(
            int(base_speed * self.push_speed_factor / 100.0)
            * self.attract_percentage
            / 100.0
        )
        pull_units = speed_work_for_duration(pull_units_per_tick, dt)
        if pull_units <= 0:
            return

        dx_units = tiles_to_logic_units(dx)
        dy_units = tiles_to_logic_units(dy)
        distance_units = max(
            1,
            math.isqrt(dx_units * dx_units + dy_units * dy_units),
        )

        entity.accumulate_movement_vector_units(
            trunc_div(dx_units * pull_units, distance_units),
            trunc_div(dy_units * pull_units, distance_units),
            bypasses_cap=True,
        )
    
    def _hitbox_overlaps_with_radius(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with area effect radius"""
        return entity.intersects_native_area(self.position, self.radius)


@dataclass
class RankedStrikeArea(AreaEffect):
    """Timed strikes against distinct enemies ranked by current hitpoints."""

    max_targets: int = 3
    strike_interval: float = 0.46
    stun_duration: float = 0.5
    struck_ids: set[int] = field(default_factory=set)
    strikes_elapsed: int = 0

    def update(self, dt: float, battle_state: "BattleState") -> None:
        if not self.is_alive:
            return
        self.time_alive += max(0.0, dt)
        deadline = min(self.time_alive, self.duration)
        while (
            self.strikes_elapsed < self.max_targets
            and (self.strikes_elapsed + 1) * self.strike_interval <= deadline + 1e-9
        ):
            self.strikes_elapsed += 1
            targets = [
                target
                for target in battle_state.entities.values()
                if isinstance(target, (Troop, Building))
                and target.player_id != self.player_id
                and target.is_alive
                and target.id not in self.struck_ids
                and target.intersects_native_area(self.position, self.radius)
                and (self.hits_air if is_airborne_target(target) else self.hits_ground)
                and target.can_receive_area_damage(
                    getattr(self, "spell_name", None),
                    affects_hidden=self.affects_hidden,
                )
            ]
            if not targets:
                continue
            # Entity ID gives a reproducible tie order; external tie behavior
            # remains a separate validation case.
            target = min(targets, key=lambda entity: (-entity.hitpoints, entity.id))
            self.struck_ids.add(target.id)
            damage = self.damage
            if isinstance(target, Building) and target.card_stats.name in {
                "Tower",
                "KingTower",
            }:
                damage = (
                    self.crown_tower_damage
                    if self.crown_tower_damage is not None
                    else native_percent_damage(
                        damage, self.crown_tower_damage_multiplier
                    )
                )
            target.take_damage(damage, source_kind=getattr(self, "spell_name", None))
            if target.is_alive:
                target.apply_stun(
                    self.stun_duration, source_kind=getattr(self, "spell_name", None)
                )
        if self.time_alive >= self.duration - 1e-9:
            self.is_alive = False


@dataclass
class BuffAreaEffect(Entity):
    """Persistent friendly haste area with an optional delayed impact."""

    duration: float = 5.5
    radius: float = 3.0
    activation_delay: float = 0.0
    movement_multiplier: float = 1.35
    attack_speed_multiplier: float = 1.35
    spawn_speed_multiplier: float = 1.35
    refresh_duration: float = 1.0
    cap_buff_time_to_effect: bool = False
    effect_tick_interval: float = 0.3
    effect_on_spawn_only: bool = False
    effect_snapshot_applied: bool = False
    impact_damage: float = 0.0
    impact_affects_hidden: bool = False
    crown_tower_damage_multiplier: float = 0.3
    crown_tower_damage: Optional[float] = None
    time_alive: float = 0.0
    impact_applied: bool = False
    impact_area_data: dict | None = None
    next_effect_time: float | None = None

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        if not self.is_alive:
            return
        self.time_alive += dt
        if self.time_alive + 1e-9 < self.activation_delay:
            return
        active_time = self.time_alive - self.activation_delay
        if not self.impact_applied:
            if self.impact_area_data is None:
                self._apply_impact(battle_state)
            else:
                from .mechanics.shared.death_area import spawn_death_area_object

                impact = spawn_death_area_object(
                    battle_state,
                    player_id=self.player_id,
                    position=self.position,
                    card_stats=self.card_stats,
                    area_data=self.impact_area_data,
                )
                impact.damage = self.impact_damage
                impact.crown_tower_damage_multiplier = self.crown_tower_damage_multiplier
                impact.crown_tower_damage = self.crown_tower_damage
                impact.affects_hidden = self.impact_affects_hidden
            self.impact_applied = True

        if self.effect_on_spawn_only:
            if not self.effect_snapshot_applied:
                self._apply_haste_scan(
                    battle_state,
                    effect_time_remaining=max(0.0, self.duration - active_time),
                )
                self.effect_snapshot_applied = True
            if active_time >= self.duration - 1e-9:
                self.is_alive = False
            return

        effect_tick_interval = max(
            LOGIC_TICK_SECONDS,
            self.effect_tick_interval,
        )
        if self.next_effect_time is None:
            self.next_effect_time = effect_tick_interval
        effect_deadline = min(active_time, self.duration)
        while (
            self.next_effect_time <= effect_deadline + 1e-9
            and self.next_effect_time < self.duration - 1e-9
        ):
            self._apply_haste_scan(
                battle_state,
                effect_time_remaining=max(
                    0.0,
                    self.duration - self.next_effect_time,
                ),
            )
            self.next_effect_time += effect_tick_interval

        if active_time >= self.duration - 1e-9:
            self.is_alive = False

    def _apply_haste_scan(
        self,
        battle_state: 'BattleState',
        *,
        effect_time_remaining: float,
    ) -> None:
        for entity in list(battle_state.entities.values()):
            if (
                entity.player_id != self.player_id
                or not entity.is_alive
                or entity is self
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue
            if entity.intersects_native_area(self.position, self.radius):
                # BuffTime is the recipient-owned falloff after its most
                # recent area scan.  It can outlive the area object unless
                # CapBuffTimeToAreaEffectTime explicitly opts this payload
                # into truncating the final refresh (the same rule used by
                # negative AreaEffect buffs such as Earthquake).
                refresh_duration = self.refresh_duration
                if self.cap_buff_time_to_effect:
                    refresh_duration = min(
                        refresh_duration,
                        effect_time_remaining,
                    )
                if refresh_duration > 1e-9:
                    entity.apply_haste(
                        refresh_duration,
                        self.movement_multiplier,
                        self.attack_speed_multiplier,
                        self.spawn_speed_multiplier,
                    )

    def _apply_impact(self, battle_state: 'BattleState') -> None:
        if self.impact_damage <= 0:
            return
        targets: list[tuple[Entity, float]] = []
        for entity in list(battle_state.entities.values()):
            if (
                entity.player_id == self.player_id
                or not entity.is_alive
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue
            if not entity.intersects_native_area(self.position, self.radius):
                continue
            if not entity.can_receive_area_damage(
                getattr(self, "spell_name", None),
                affects_hidden=self.impact_affects_hidden,
            ):
                continue
            damage = self.impact_damage
            if isinstance(entity, Building) and getattr(entity.card_stats, "name", "") in {
                "Tower",
                "KingTower",
            }:
                damage = (
                    float(self.crown_tower_damage)
                    if self.crown_tower_damage is not None
                    else native_percent_damage(
                        damage,
                        self.crown_tower_damage_multiplier,
                    )
                )
            targets.append((entity, damage))
        for entity, damage in targets:
            entity.take_damage(
                damage,
                source_kind=getattr(self, "spell_name", None),
                affects_hidden=self.impact_affects_hidden,
            )


@dataclass
class DeathAreaStartAction(Entity):
    """The death area's first object update dispatches its starting action."""

    spawn_data: dict = field(default_factory=dict)
    area_data: dict = field(default_factory=dict)

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        if not self.is_alive:
            return
        from .mechanics.shared.death_area import spawn_death_area_container

        spawn_death_area_container(
            battle_state,
            player_id=self.player_id,
            position=self.position,
            card_stats=self.card_stats,
            spawn_data=self.spawn_data,
            area_data=self.area_data,
        )
        self.is_alive = False


@dataclass
class DeathAreaEffectContainer(Entity):
    """A delayed zero-hitpoint-style object that creates a death area."""

    activation_delay: float = 0.0
    area_data: dict = field(default_factory=dict)
    time_alive: float = 0.0
    blocks_deployment: bool = False
    area_displaceable: bool = False
    activation_complete: bool = False

    def update(self, dt: float, battle_state: 'BattleState') -> None:
        if not self.is_alive:
            return
        if self.activation_complete:
            self.is_alive = False
            return
        self.time_alive += max(0.0, dt)
        if self.time_alive + 1e-9 < self.activation_delay:
            return
        from .mechanics.shared.death_area import spawn_death_area_payload

        spawn_death_area_payload(
            battle_state,
            player_id=self.player_id,
            position=self.position,
            card_stats=self.card_stats,
            area_data=self.area_data,
        )
        # Native keeps the spent character container through the boundary
        # that publishes its death area, then removes it on its next tick.
        self.activation_complete = True


@dataclass
class SpawnProjectile(Projectile):
    """Projectile that spawns units when it reaches target"""
    spawn_level: int = field(default=11, kw_only=True)
    spawn_count: int = 3
    spawn_character: str = "Goblin"
    spawn_character_data: dict = None
    spawn_radius: float | None = None
    activation_delay: float = 0.0
    spawn_deploy_delay_override: float | None = None
    spawn_const_priority: bool = False
    time_alive: float = 0.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update projectile - move towards target and spawn units on impact"""
        if not self.is_alive:
            return

        self.time_alive += dt
        if self.time_alive + 1e-9 < self.activation_delay:
            return
        
        # Carrier projectiles use the same integer component work as damaging
        # projectiles. A floating-point distance check can otherwise delay a
        # diagonal landing by one 50 ms server frame.
        if self._reaches_target_this_update(dt):
            # Native projectile impact resolves damage (and any synchronous
            # victim death effects) before its SpawnCharacter payload. A
            # recruit or barrel troop therefore cannot be hit by a death nova
            # caused by the impact that creates it.
            self._deal_splash_damage(battle_state)
            self._spawn_units(battle_state)
            self.is_alive = False
        else:
            self._move_towards(self.target_position, dt)
    
    def _spawn_units(self, battle_state: 'BattleState') -> None:
        """Spawn units at target position"""
        if not self.spawn_character_data:
            return

        from .formations import formation_offset
        
        spawn_stats = troop_from_character_data(
            self.spawn_character,
            self.spawn_character_data,
            elixir=0,
            raw_overrides={"level": getattr(self.card_stats, "level", self.spawn_level)},
            rarity=self.spawn_character_data.get("rarity", "Common"),
        )
        
        spacing = (
            float(self.spawn_radius)
            if self.spawn_radius is not None
            else float(getattr(spawn_stats, "collision_radius", 0.5) or 0.5)
        )
        for index in range(self.spawn_count):
            offset_x, offset_y = formation_offset(
                index,
                self.spawn_count,
                spacing,
                self.player_id,
                float(getattr(spawn_stats, "spawn_angle_shift", 0) or 0),
                lane_id=battle_state.arena.native_path_id_at(
                    self.target_position
                ),
            )
            spawn_x = self.target_position.x + offset_x
            spawn_y = self.target_position.y + offset_y
            
            # Create and spawn the unit.  Payload-specific action delays are
            # resolved by the common spawn primitive before hooks fire.
            spawned_id = battle_state.next_entity_id
            battle_state._spawn_unit_at_position(
                Position(spawn_x, spawn_y),
                self.player_id,
                spawn_stats,
                deploy_delay_override=self.spawn_deploy_delay_override,
                is_clone=self.is_clone,
                snap_to_valid=False,
            )
            spawned = battle_state.entities.get(spawned_id)
            if spawned is not None and self.spawn_const_priority:
                spawned._native_target_distance_discount_sq_units = (
                    spawn_target_distance_discount_sq_units(index)
                )


@dataclass
class RollingProjectile(Entity):
    """Rolling projectiles that spawn at location and roll forward (Log, Barbarian Barrel)"""
    spawn_level: int = field(default=11, kw_only=True)
    travel_speed: float = 200.0
    projectile_range: float = 10.0  # tiles
    spawn_delay: float = 0.65  # seconds
    spawn_character: str = None
    spawn_character_data: dict = None
    spawn_deploy_delay_override: float | None = None
    radius_y: float = 0.6  # Height of rolling hitbox
    impact_radius: Optional[float] = None
    knockback_distance: float = 1.5
    knockback_ignores_mass: bool = False
    radial_knockback: bool = False
    crown_tower_damage_multiplier: float = 1.0
    crown_tower_damage: Optional[float] = None
    # Optional custom direction vector; used by Bowler boulder. Its magnitude
    # is irrelevant because all displacement normalizes in logic units.
    target_direction_x: Optional[float] = None
    target_direction_y: Optional[float] = None
    source_entity: Optional[Entity] = field(default=None, repr=False)
    primary_target: Optional[Entity] = field(default=None, repr=False)
    
    def __post_init__(self):
        super().__post_init__()
        # Use range field from Entity as rolling radius
        self.rolling_radius = self.range
    
    # State tracking
    time_alive: float = 0.0
    distance_traveled: float = 0.0
    hit_entities: set = field(default_factory=set)  # Track entities hit (can only hit once)
    has_spawned_character: bool = False
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update rolling projectile - wait for spawn delay, then roll forward"""
        if not self.is_alive:
            return
        
        previous_time_alive = self.time_alive
        self.time_alive += dt

        # The parent's arrival frame creates the child at its landing point;
        # rolling starts on the following frame. Zero-delay troop projectiles
        # retain their ordinary first update.
        if previous_time_alive + 1e-9 < self.spawn_delay:
            if self.time_alive + 1e-9 >= self.spawn_delay:
                self._deal_rolling_damage(battle_state)
            return
        
        # Roll forward at constant speed
        roll_units = min(
            speed_work_for_duration(self.travel_speed, dt),
            max(
                0,
                tiles_to_logic_units(
                    self.projectile_range - self.distance_traveled
                ),
            ),
        )
        roll_distance = logic_units_to_tiles(roll_units)
        self.distance_traveled += roll_distance
        
        # Determine roll direction
        if self.target_direction_x is not None and self.target_direction_y is not None:
            # Use custom direction (for Bowler)
            direction_scale = 1_000_000
            move_x_units, move_y_units = vector_towards_logic_units(
                round(self.target_direction_x * direction_scale),
                round(self.target_direction_y * direction_scale),
                roll_units,
            )
            self.position.x = logic_units_to_tiles(
                tiles_to_logic_units(self.position.x) + move_x_units
            )
            self.position.y = logic_units_to_tiles(
                tiles_to_logic_units(self.position.y) + move_y_units
            )
        else:
            # Default direction (towards enemy side for Log/Barbarian Barrel)
            if self.player_id == 0:  # Blue player rolls towards red side (positive Y)
                self.position.y = logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y) + roll_units
                )
            else:  # Red player rolls towards blue side (negative Y)
                self.position.y = logic_units_to_tiles(
                    tiles_to_logic_units(self.position.y) - roll_units
                )
        
        # Resolve the final occupied segment before expiring. Otherwise an
        # endpoint target is skipped on the tick that reaches max range.
        self._deal_rolling_damage(battle_state)

        if self.distance_traveled >= self.projectile_range - 1e-9:
            # Juggernaut-style projectiles use their smaller physical radius
            # while travelling, then their ordinary damage radius when they
            # resolve at the terminal projectile-range endpoint.
            if self.impact_radius is not None and self.impact_radius > self.rolling_radius:
                rolling_radius = self.rolling_radius
                self.rolling_radius = self.impact_radius
                try:
                    self._deal_rolling_damage(battle_state)
                finally:
                    self.rolling_radius = rolling_radius
            # Spawn character if applicable (Barbarian Barrel)
            if self.spawn_character and not self.has_spawned_character:
                self._spawn_character(battle_state)
            self.is_alive = False
            return
    
    def _deal_rolling_damage(self, battle_state: 'BattleState') -> None:
        """Deal damage to ground units in rolling path (rectangular hitbox)"""
        # Create a copy of entities list to avoid RuntimeError when dictionary changes during iteration
        entities_copy = list(battle_state.entities.values())
        for entity in entities_copy:
            if (entity.player_id == self.player_id or 
                not entity.is_alive or 
                entity.id in self.hit_entities or
                entity == self or
                getattr(entity, "entity_kind", 4) in {2, 3}):
                continue
            source_kind = getattr(self, "spell_name", None) or "rolling-projectile"
            if (
                self.target_direction_x is None
                and self.target_direction_y is None
                and entity.spawn_stagger_remaining > 1e-9
                and not is_above_ground_surface(entity)
                and self._hitbox_overlaps_with_rolling_path(entity)
            ):
                # Rectangular rolling spells consume contact with a pending
                # group member, even though it cannot receive the payload yet.
                self.hit_entities.add(entity.id)
                continue
            if not entity.can_receive_area_damage(
                source_kind,
                source_entity=self.source_entity,
            ):
                continue
            
            # Skip air units (Log only hits ground)
            if is_above_ground_surface(entity):
                continue
            
            # Check if entity is in rectangular rolling hitbox with entity collision radius
            if self._hitbox_overlaps_with_rolling_path(entity):
                # Hit the entity
                source_kind = getattr(self, "spell_name", None) or "rolling-projectile"
                if not entity.can_receive_effect(source_kind):
                    continue
                damage = self.damage
                if isinstance(entity, Building) and getattr(entity.card_stats, 'name', None) in {"Tower", "KingTower"}:
                    damage = (
                        self.crown_tower_damage
                        if self.crown_tower_damage is not None
                        else native_percent_damage(
                            damage,
                            self.crown_tower_damage_multiplier,
                        )
                    )
                entity.take_damage(damage, source_kind=source_kind)
                self.hit_entities.add(entity.id)
                
                # Apply knockback effect (Log pushes units backward)
                self._apply_knockback(entity, battle_state)

    def _apply_knockback(self, entity: 'Entity', battle_state: 'BattleState') -> None:
        """Schedule the rolling payload's directional native pushback."""
        from .mechanics.shared.knockback import apply_directional_knockback, apply_radial_knockback

        if self.radial_knockback:
            apply_radial_knockback(
                entity,
                battle_state,
                self.position,
                self.knockback_distance,
                source_kind=getattr(self, "spell_name", None) or "rolling-projectile",
                ignores_mass=self.knockback_ignores_mass,
                interrupts_combat=False,
                reset_hit_on_movement=True,
            )
            return

        if self.target_direction_x is not None and self.target_direction_y is not None:
            direction_x_units = round(self.target_direction_x)
            direction_y_units = round(self.target_direction_y)
        else:
            direction_x_units = 0
            direction_y_units = 1 if self.player_id == 0 else -1

        source_kind = getattr(self, "spell_name", None) or (
            getattr(getattr(self, "source_entity", None), "card_stats", None)
            and getattr(self.source_entity.card_stats, "name", None)
        )
        apply_directional_knockback(
            entity,
            battle_state,
            direction_x_units,
            direction_y_units,
            self.knockback_distance,
            source_kind=source_kind or "rolling-projectile",
            ignores_mass=self.knockback_ignores_mass,
        )

    def expected_damage_against(self, entity: Entity) -> float:
        """Return the committed primary boulder damage for target reservation."""
        damage = float(self.damage)
        if isinstance(entity, Building) and getattr(entity.card_stats, "name", None) in {
            "Tower",
            "KingTower",
        }:
            damage = (
                float(self.crown_tower_damage)
                if self.crown_tower_damage is not None
                else native_percent_damage(
                    damage,
                    self.crown_tower_damage_multiplier,
                )
            )
        return max(0.0, damage)
    
    def _hitbox_overlaps_with_rolling_path(self, entity: 'Entity') -> bool:
        """Intersect the target's hitbox with the rolling projectile footprint."""
        # Unit-fired rolling projectiles such as Bowler's boulder use a
        # circular projectile radius and may travel at any angle. Log-family
        # spells use the serialized, travel-oriented rectangular footprint.
        if self.target_direction_x is not None and self.target_direction_y is not None:
            return entity.intersects_native_area(
                self.position,
                self.rolling_radius,
            )

        x = tiles_to_logic_units(entity.position.x)
        y = tiles_to_logic_units(entity.position.y)
        cx = tiles_to_logic_units(self.position.x)
        cy = tiles_to_logic_units(self.position.y)
        rx = tiles_to_logic_units(self.rolling_radius)
        ry = tiles_to_logic_units(self.radius_y)
        radius = tiles_to_logic_units(entity.get_collision_radius())
        if entity.entity_kind == 1:
            # Native f2ebf4: square buildings include the lower rectangle
            # boundary and exclude its upper boundary on each world axis.
            return (
                x + radius >= cx - rx and y + radius >= cy - ry
                and x - radius < cx + rx and y - radius < cy + ry
            )
        # Native f2ea30: circle versus rectangle, including rounded corners.
        # Strict squared contact excludes tangency (Log/Prince interval527).
        dx = x - min(cx + rx, max(cx - rx, x))
        dy = y - min(cy + ry, max(cy - ry, y))
        return dx * dx + dy * dy < radius * radius
    
    def _spawn_character(self, battle_state: 'BattleState') -> None:
        """Spawn character at end of roll (Barbarian Barrel)"""
        if not self.spawn_character_data:
            return
        
        spawn_stats = troop_from_character_data(
            self.spawn_character,
            self.spawn_character_data,
            elixir=0,
            raw_overrides={"level": getattr(self.card_stats, "level", self.spawn_level)},
            rarity=self.spawn_character_data.get("rarity", "Common"),
        )
        
        # Projectile child payloads use getSpawnOffset and then the common
        # quarter-tile spawnObject clamp. They do not enter the character
        # spawner's terrain-candidate routine.
        battle_state._spawn_unit_at_position(
            Position(self.position.x, self.position.y),
            self.player_id,
            spawn_stats,
            deploy_delay_override=self.spawn_deploy_delay_override,
            is_clone=self.is_clone,
            snap_to_valid=False,
        )
        self.has_spawned_character = True


@dataclass
class TimedExplosive(Entity):
    """Entity that explodes after a countdown timer (death bombs, balloon bombs)"""
    explosion_timer: float = 3.0
    explosion_radius: float = 1.5
    explosion_damage: float = 600.0
    knockback_distance: float = 0.0
    knockback_ignores_mass: bool = False
    death_spawn_name: Optional[str] = None
    death_spawn_count: int = 0
    death_spawn_data: Optional[dict] = None
    death_spawn_radius: float = 0.7
    death_spawn_deploy_time: float = 0.0
    death_spawn_pushback: bool = False
    spawn_const_priority: bool = False
    # A timed payload that releases characters can carry a one-time Freeze
    # snapshot through its fall/opening animation. Ordinary death bombs have
    # no children and therefore remain unaffected effect containers.
    carries_freeze_to_children: bool = field(init=False)
    # Falling/death payloads occupy their landing spot for card placement even
    # though they are not combat targets or ground-pathing obstacles.
    blocks_deployment: bool = True
    deployment_collision_radius: float = 0.5
    area_displaceable: bool = False
    time_alive: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.carries_freeze_to_children = bool(
            self.death_spawn_name and self.death_spawn_count > 0
        )
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update timed explosive - countdown and explode"""
        if not self.is_alive:
            return
            
        self.time_alive += dt
        
        # Check if timer expired
        if self.time_alive >= self.explosion_timer - 1e-9:
            self._explode(battle_state)
            self.is_alive = False
    
    def _explode(self, battle_state: 'BattleState') -> None:
        """Deal explosion damage to entities in radius using hitbox collision"""
        from .mechanics.shared.knockback import apply_radial_knockback

        source_kind = getattr(self.card_stats, "name", None)
        impact_position = Position(self.position.x, self.position.y)
        targets = []
        for entity in list(battle_state.entities.values()):
            if (
                entity.player_id == self.player_id
                or not entity.is_alive
                or getattr(entity, "entity_kind", 4) in {2, 3}
            ):
                continue
            
            if (
                entity.intersects_native_area(
                    impact_position,
                    self.explosion_radius,
                )
                and entity.can_receive_area_damage(source_kind)
            ):
                targets.append(entity)

        for entity in targets:
            entity.take_damage(self.explosion_damage, source_kind=source_kind)
            if entity.is_alive and self.knockback_distance > 0:
                apply_radial_knockback(
                    entity,
                    battle_state,
                    impact_position,
                    self.knockback_distance,
                    source_kind=source_kind,
                    ignores_mass=self.knockback_ignores_mass,
                )

        # Optional chained death spawn (e.g. Skeleton Barrel container -> Skeletons).
        if self.death_spawn_name and self.death_spawn_count > 0:
            self._spawn_death_units(battle_state)

    def _spawn_death_units(self, battle_state: 'BattleState') -> None:
        """Spawn units around this explosive when configured."""
        from .factory.dynamic_factory import troop_from_character_data
        from .formations import native_radial_spawn_offset

        inherited_freeze_remaining = (
            max(0.0, self.freeze_expiry_time - battle_state.time)
            if self.carries_freeze_to_children
            else 0.0
        )

        spawn_stats = None
        if self.death_spawn_data:
            spawn_stats = troop_from_character_data(
                self.death_spawn_name,
                self.death_spawn_data,
                elixir=0,
                raw_overrides={"level": getattr(self.card_stats, "level", 11)},
                rarity=self.death_spawn_data.get("rarity", "Common"),
            )
        if not spawn_stats:
            spawn_stats = battle_state.card_loader.get_card(self.death_spawn_name)
        if not spawn_stats:
            raise ValueError(
                f"Missing explosive death-spawn data for {self.death_spawn_name}"
            )

        facing_x_units, facing_y_units = self.native_facing_units()
        angle_shift = float(
            getattr(self.card_stats, "spawn_angle_shift", 0) or 0
        )
        for index in range(self.death_spawn_count):
            offset_x, offset_y = native_radial_spawn_offset(
                index,
                self.death_spawn_count,
                self.death_spawn_radius,
                angle_shift,
                facing_x_units=facing_x_units,
                facing_y_units=facing_y_units,
                flip_x=(
                    self.spawn_const_priority
                    and battle_state.arena.native_path_id_at(self.position) == 1
                ),
                flip_y=self.spawn_const_priority and self.player_id == 1,
            )
            spawn_x = self.position.x + offset_x
            spawn_y = self.position.y + offset_y
            # Death payloads do not inherit the child card's ordinary deploy
            # time. A parent may nevertheless serialize its own explicit
            # DeathSpawnDeployTime (Skeleton Barrel uses 500 ms).
            spawned_id = battle_state.next_entity_id
            battle_state._spawn_unit_at_position(
                Position(spawn_x, spawn_y),
                self.player_id,
                spawn_stats,
                deploy_delay_override=self.death_spawn_deploy_time,
                is_clone=self.is_clone,
                snap_to_valid=False,
                death_spawn=True,
                death_spawn_travel_origin=(
                    self.position
                    if self.death_spawn_pushback and self.death_spawn_radius > 0.0
                    else None
                ),
            )
            spawned = battle_state.entities.get(spawned_id)
            if spawned is not None and self.spawn_const_priority:
                spawned._native_target_distance_discount_sq_units = (
                    spawn_target_distance_discount_sq_units(index)
                )
            if spawned is not None and (
                (
                    self.death_spawn_pushback
                    and self.death_spawn_radius > 0.0
                )
                or self.spawn_const_priority
            ):
                battle_state.sync_fast_target_entity(spawned)
            if spawned is not None and inherited_freeze_remaining > 1e-9:
                # The container itself is not stunned: its fall/open timer
                # continues normally. It carries the original snapshot so
                # children born after that snapshot receive only its
                # remaining duration.
                spawned.inherit_freeze_until(
                    self.freeze_expiry_time,
                    battle_state.time,
                )
    
    def _hitbox_overlaps_with_explosion(self, entity: 'Entity') -> bool:
        """Check if entity's hitbox overlaps with explosion radius"""
        return entity.intersects_native_area(
            self.position,
            self.explosion_radius,
        )


@dataclass
class Graveyard(Entity):
    """Entity that periodically spawns skeletons in an area"""
    spawn_level: int = field(default=11, kw_only=True)
    spawn_interval: float = 0.5
    initial_spawn_delay: float = 1.2
    spawn_deadlines: tuple[float, ...] = ()
    max_skeletons: int = 12
    spawn_radius: float = 3.3
    duration: float = 9.0
    spawn_offsets: tuple[tuple[float, float], ...] = ()
    mirror_pattern_x_at_center: bool = False
    orient_pattern_y_by_player: bool = False
    spawn_deploy_delay_override: float | None = 0.5
    spawn_character: str = "Skeleton"
    skeleton_data: dict = None
    time_alive: float = 0.0
    next_spawn_time: float = 1.2
    skeletons_spawned: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.spawn_deadlines:
            self.next_spawn_time = self.spawn_deadlines[0]
        else:
            self.next_spawn_time = self.initial_spawn_delay
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update graveyard - spawn skeletons periodically"""
        if not self.is_alive:
            return
            
        self.time_alive += dt

        # Absolute deadlines preserve exact timing and count under both the
        # normal 30 Hz step and large fast-forward steps.
        active_until = min(self.time_alive, self.duration)
        while (
            self.next_spawn_time <= active_until + 1e-9
            and self.skeletons_spawned < self.max_skeletons
        ):
            self._spawn_skeleton(battle_state)
            self.skeletons_spawned += 1
            if self.skeletons_spawned < len(self.spawn_deadlines):
                self.next_spawn_time = self.spawn_deadlines[self.skeletons_spawned]
            else:
                self.next_spawn_time = self.initial_spawn_delay + (
                    self.skeletons_spawned * self.spawn_interval
                )

        if self.time_alive >= self.duration - 1e-9:
            self.is_alive = False
    
    def _spawn_skeleton(self, battle_state: 'BattleState') -> None:
        """Spawn the next skeleton at its fixed, player-relative location."""
        if not self.skeleton_data:
            return
        
        # Create skeleton stats
        skeleton_stats = troop_from_character_data(
            self.spawn_character,
            self.skeleton_data,
            elixir=0,
            raw_overrides={"level": getattr(self.card_stats, "level", self.spawn_level)},
            rarity=self.skeleton_data.get("rarity", "Common"),
        )
        
        if self.spawn_offsets:
            offset_x, offset_y = self.spawn_offsets[
                self.skeletons_spawned % len(self.spawn_offsets)
            ]
            if (
                self.mirror_pattern_x_at_center
                and self.position.x > battle_state.arena.width / 2.0
            ):
                offset_x = -offset_x
            if self.orient_pattern_y_by_player and self.player_id == 1:
                offset_y = -offset_y
            elif (
                not self.mirror_pattern_x_at_center
                and not self.orient_pattern_y_by_player
                and self.player_id == 1
            ):
                # Backward-compatible transform for custom fixed patterns.
                offset_x = -offset_x
                offset_y = -offset_y
            spawn_x = self.position.x + offset_x
            spawn_y = self.position.y + offset_y
        else:
            # A deterministic ring fallback supports custom game data without
            # reintroducing RNG into the live Graveyard implementation.
            angle = (2.0 * math.pi * self.skeletons_spawned) / max(1, self.max_skeletons)
            spawn_x = self.position.x + self.spawn_radius * math.cos(angle)
            spawn_y = self.position.y + self.spawn_radius * math.sin(angle)

        # The Graveyard deadline is the Skeleton's complete deploy delay.  The
        # nested Skeleton data's native deploy time applies when the Skeleton
        # card itself is played, not again after this payload has materialized.
        battle_state._spawn_unit_at_position(
            Position(spawn_x, spawn_y),
            self.player_id,
            skeleton_stats,
            deploy_delay_override=self.spawn_deploy_delay_override,
            is_clone=self.is_clone,
            # Projectile-created characters go through LogicBattle::spawnObject:
            # their center is clamped to the outer quarter-tile boundary, but
            # terrain, tower footprints, and neighboring objects do not
            # relocate the requested spawn point.
            snap_to_valid=False,
        )
