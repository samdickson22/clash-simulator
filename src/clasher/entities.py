from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from .arena import Position
from .data import CardStats


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
class Entity(ABC):
    id: int
    position: Position
    player_id: int
    card_stats: CardStats
    
    # Combat stats
    hitpoints: float
    max_hitpoints: float
    damage: float
    range: float
    sight_range: float
    
    # Timing
    attack_cooldown: float = 0.0
    load_time: float = 0.0
    
    # State
    target_id: Optional[int] = None
    is_alive: bool = True
    is_air_unit: bool = False  # True for flying troops like Minions, Balloon, Dragon
    
    def __post_init__(self) -> None:
        if self.max_hitpoints == 0:
            self.max_hitpoints = self.hitpoints
    
    @abstractmethod
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update entity state each tick"""
        pass
    
    def take_damage(self, amount: float) -> None:
        """Apply damage to entity"""
        self.hitpoints = max(0, self.hitpoints - amount)
        if self.hitpoints <= 0:
            self.is_alive = False
    
    def can_attack_target(self, target: 'Entity') -> bool:
        """Check if this entity can attack the target"""
        if not target.is_alive or target.player_id == self.player_id:
            return False
        
        distance = self.position.distance_to(target.position)
        return distance <= self.range
    
    def get_nearest_target(self, entities: Dict[int, 'Entity']) -> Optional['Entity']:
        """Find nearest valid target with priority rules"""
        nearest = None
        min_distance = float('inf')
        
        # Priority: Troops > Buildings (authentic Clash Royale behavior)
        building_targets = []
        troop_targets = []
        
        # Check if this unit can only target buildings
        targets_only_buildings = (hasattr(self, 'card_stats') and 
                                self.card_stats and 
                                getattr(self.card_stats, 'targets_only_buildings', False))
        
        # Check what this unit can attack
        can_attack_air = (hasattr(self, 'card_stats') and 
                         self.card_stats and 
                         (getattr(self.card_stats, 'target_type', None) in ['TID_TARGETS_AIR_AND_GROUND', 'TID_TARGETS_AIR']))
        
        for entity in entities.values():
            # Only check if entity is valid enemy (alive and different player)
            if not entity.is_alive or entity.player_id == self.player_id:
                continue
                
            distance = self.position.distance_to(entity.position)
            
            # Check air targeting rules
            if entity.is_air_unit and not can_attack_air:
                continue  # Skip air units if we can't attack air
            
            # Only consider targets within sight range for troops vs troops
            if isinstance(entity, Building):
                building_targets.append((entity, distance))
            else:
                # For troop targets, only consider if within sight range
                if distance <= self.sight_range:
                    # Skip troops if we only target buildings
                    if not targets_only_buildings:
                        troop_targets.append((entity, distance))
        
        # Choose targets based on targeting rules
        if targets_only_buildings:
            targets = building_targets  # Only consider buildings
        else:
            targets = troop_targets if troop_targets else building_targets  # Troops first, then buildings
        
        for entity, distance in targets:
            if distance < min_distance:
                min_distance = distance
                nearest = entity
        
        return nearest
    
    def _should_switch_target(self, current_target: 'Entity', new_target: 'Entity') -> bool:
        """Determine if we should switch from current target to new target"""
        # Always switch to troops in sight range (higher priority than buildings)
        is_current_building = isinstance(current_target, Building)
        is_new_troop = not isinstance(new_target, Building)
        
        if is_new_troop and is_current_building:
            # Switch from building to troop if troop is in sight range
            distance_to_new = self.position.distance_to(new_target.position)
            if distance_to_new <= self.sight_range:
                return True
        
        # Don't switch if current target is closer and same type
        current_distance = self.position.distance_to(current_target.position)
        new_distance = self.position.distance_to(new_target.position)
        
        # If both are same type (both troops or both buildings), keep closer one
        if isinstance(current_target, Building) == isinstance(new_target, Building):
            return new_distance < current_distance
        
        return False


@dataclass 
class Troop(Entity):
    speed: float = 1.0
    target_type: TargetType = TargetType.BOTH
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update troop - move and attack"""
        if not self.is_alive:
            return
        
        # Update attack cooldown
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        
        # Always re-evaluate targets every tick to switch to higher priority enemies
        current_target = None
        if self.target_id:
            current_target = battle_state.entities.get(self.target_id)
            if not current_target or not current_target.is_alive:
                self.target_id = None
                current_target = None
        
        # Always check for better targets (troops in FOV take priority over buildings)
        best_target = self.get_nearest_target(battle_state.entities)
        if best_target and (not current_target or self._should_switch_target(current_target, best_target)):
            current_target = best_target
            self.target_id = current_target.id
        
        if current_target:
            # Move towards target if out of range
            distance = self.position.distance_to(current_target.position)
            if distance > self.range:
                self._move_towards_target(current_target, dt, battle_state)
            elif self.attack_cooldown <= 0:
                # Attack
                current_target.take_damage(self.damage)
                self.attack_cooldown = self.card_stats.hit_speed / 1000.0 if self.card_stats.hit_speed else 1.0
    
    def _move_towards_target(self, target_entity: 'Entity', dt: float, battle_state=None) -> None:
        """Move towards target entity with 3-priority pathfinding system"""
        # Get pathfinding target using priority system
        pathfind_target = self._get_pathfind_target(target_entity, battle_state)
        
        dx = pathfind_target.x - self.position.x
        dy = pathfind_target.y - self.position.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            # Normalize and scale by speed
            # self.speed is in tiles/min, convert to tiles/second, then multiply by dt
            speed_tiles_per_second = self.speed / 60.0  # Convert tiles/min to tiles/sec
            move_distance = speed_tiles_per_second * dt
            
            
            # Don't overshoot the target
            if move_distance > distance:
                move_distance = distance
            
            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance
            
            # Check if the new position would be walkable (for ground units)
            new_position = Position(self.position.x + move_x, self.position.y + move_y)
            
            # Air units ignore walkability checks, ground units must check
            if self.is_air_unit or (battle_state and battle_state.arena.is_walkable(new_position)):
                self.position.x += move_x
                self.position.y += move_y
            else:
                # If direct path is blocked, try to find a way around the obstacle
                alternative_move = self._find_alternative_move(move_x, move_y, battle_state)
                if alternative_move:
                    alt_x, alt_y = alternative_move
                    self.position.x += alt_x
                    self.position.y += alt_y
                # If no alternative found, unit remains stuck (this should be rare)
    
    def _find_alternative_move(self, original_move_x: float, original_move_y: float, battle_state) -> Optional[tuple]:
        """Find an alternative movement direction when the direct path is blocked.
        Returns (move_x, move_y) tuple or None if no alternative found."""
        
        if not battle_state:
            return None
        
        # Try different angles around the blocked direction
        import math
        
        # Calculate the original angle
        original_angle = math.atan2(original_move_y, original_move_x)
        move_distance = math.sqrt(original_move_x * original_move_x + original_move_y * original_move_y)
        
        # Try angles offset by 45°, 90°, -45°, -90° from the original direction
        angle_offsets = [math.pi/4, math.pi/2, -math.pi/4, -math.pi/2, 3*math.pi/4, -3*math.pi/4]
        
        for angle_offset in angle_offsets:
            # Calculate new direction
            new_angle = original_angle + angle_offset
            new_move_x = math.cos(new_angle) * move_distance
            new_move_y = math.sin(new_angle) * move_distance
            
            # Check if this alternative direction is walkable
            alt_position = Position(self.position.x + new_move_x, self.position.y + new_move_y)
            
            if battle_state.arena.is_walkable(alt_position):
                return (new_move_x, new_move_y)
        
        # If no angular alternatives work, try smaller steps in perpendicular directions
        # This helps units "slide" along walls
        perpendicular_directions = [
            (original_move_y, -original_move_x),  # 90° rotation
            (-original_move_y, original_move_x)   # -90° rotation
        ]
        
        for perp_x, perp_y in perpendicular_directions:
            # Normalize to same distance
            perp_distance = math.sqrt(perp_x * perp_x + perp_y * perp_y)
            if perp_distance > 0:
                perp_x = (perp_x / perp_distance) * move_distance
                perp_y = (perp_y / perp_distance) * move_distance
                
                # Try this perpendicular direction
                perp_position = Position(self.position.x + perp_x, self.position.y + perp_y)
                if battle_state.arena.is_walkable(perp_position):
                    return (perp_x, perp_y)
        
        return None  # No alternative found
    
    def _get_pathfind_target(self, target_entity: 'Entity', battle_state=None) -> Position:
        """Get pathfinding target using priority system with advanced post-tower-destruction logic:
        Air units: 1) Targets in FOV, 2) Towers (fly directly over river)
        Ground units: 
        - Before first tower destroyed: 1) Troops in sight range, 2) Bridge center, 3) Princess towers
        - After first tower destroyed: 1) Troops in FOV, 2) Center bridge, 3) Cross bridge if clear, 4) Target buildings
        """
        from .battle import BattleState
        
        final_target = target_entity.position
        
        # Air units bypass bridge pathfinding - they fly directly to targets
        if self.is_air_unit:
            distance_to_target = self.position.distance_to(final_target)
            is_troop = not isinstance(target_entity, Building)
            
            # Priority 1: If target is a troop within sight range, go directly
            if is_troop and distance_to_target <= self.sight_range:
                return final_target
            
            # Priority 2: Go directly to any target (towers, etc.) - air units ignore bridges
            return final_target
        
        # Ground units use bridge pathfinding
        # Check if we need to cross the river (river at y=16)
        current_side = 0 if self.position.y < 16.0 else 1
        target_side = 0 if final_target.y < 16.0 else 1
        need_to_cross = current_side != target_side
        
        # Priority 1: If target is a troop within sight range, go directly
        distance_to_target = self.position.distance_to(final_target)
        is_troop = not isinstance(target_entity, Building)
        
        # For troop targets within sight range, still check if we need bridge pathfinding
        if is_troop and distance_to_target <= self.sight_range:
            # If we don't need to cross the river, go directly
            if not need_to_cross:
                return final_target
            # If we need to cross, continue with bridge logic even for troops
        
        # If we don't need to cross, go directly to target
        if not need_to_cross:
            return final_target
        
        # Check if first tower has been destroyed to determine pathfinding mode
        first_tower_destroyed = self._is_first_tower_destroyed(battle_state)
        
        if first_tower_destroyed:
            return self._get_advanced_pathfind_target(target_entity)
        else:
            return self._get_basic_pathfind_target(target_entity)
    
    def _is_first_tower_destroyed(self, battle_state) -> bool:
        """Check if the first tower (any princess tower) has been destroyed"""
        if not battle_state:
            return False
            
        # Check if any princess towers are destroyed by looking at player tower HP
        total_princess_towers_alive = 0
        
        for player in battle_state.players:
            if player.left_tower_hp > 0:
                total_princess_towers_alive += 1
            if player.right_tower_hp > 0:
                total_princess_towers_alive += 1
        
        # If we have less than 4 princess towers alive, at least one has been destroyed
        return total_princess_towers_alive < 4
    
    def _get_basic_pathfind_target(self, target_entity: 'Entity') -> Position:
        """Original pathfinding logic before first tower is destroyed"""
        final_target = target_entity.position
        
        # We need to cross the river - use bridge logic
        # Determine which bridge to use (left at x=3.5, right at x=14.5)
        left_bridge_dist = abs(self.position.x - 3.5)
        right_bridge_dist = abs(self.position.x - 14.5)
        
        if left_bridge_dist < right_bridge_dist:
            bridge_x = 3.5  # Left bridge center of center tile
        else:
            bridge_x = 14.5  # Right bridge center of center tile
        
        # Bridge center is at the actual center of the bridge structure
        bridge_y = 16.0  # Dead center of the bridge spanning the river
        bridge_center = Position(bridge_x, bridge_y)
        
        # Check if we're on the bridge (within 1.5 tiles of bridge center)
        # Bridge is 3 tiles wide, pathfinder targets center of center tile
        on_bridge = (abs(self.position.x - bridge_x) <= 1.5 and 
                    abs(self.position.y - 16.0) <= 1.0)
        
        if on_bridge:
            # Priority 3: On bridge - go to appropriate princess tower
            if self.player_id == 0:  # Blue player going to red side
                if bridge_x == 3.5:  # Left bridge -> left tower
                    return Position(3.5, 25.5)  # RED_LEFT_TOWER
                else:  # Right bridge -> right tower  
                    return Position(14.5, 25.5)  # RED_RIGHT_TOWER
            else:  # Red player going to blue side
                if bridge_x == 3.5:  # Left bridge -> left tower
                    return Position(3.5, 6.5)  # BLUE_LEFT_TOWER
                else:  # Right bridge -> right tower
                    return Position(14.5, 6.5)  # BLUE_RIGHT_TOWER
        else:
            # Priority 2: Behind bridge - go to bridge center
            return bridge_center
    
    def _get_advanced_pathfind_target(self, target_entity: 'Entity') -> Position:
        """Advanced pathfinding logic after first tower is destroyed"""
        final_target = target_entity.position
        
        # Choose the nearest actual bridge (left at x=3.5 or right at x=14.5)
        left_bridge = Position(3.5, 16.0)
        right_bridge = Position(14.5, 16.0)
        
        # Determine which bridge is closer
        dist_to_left = self.position.distance_to(left_bridge)
        dist_to_right = self.position.distance_to(right_bridge)
        
        if dist_to_left <= dist_to_right:
            chosen_bridge = left_bridge
        else:
            chosen_bridge = right_bridge
        
        # Check if we're on either bridge
        on_left_bridge = (abs(self.position.x - 3.5) <= 1.5 and abs(self.position.y - 16.0) <= 1.0)
        on_right_bridge = (abs(self.position.x - 14.5) <= 1.5 and abs(self.position.y - 16.0) <= 1.0)
        on_bridge = on_left_bridge or on_right_bridge
        
        if on_bridge:
            # On center bridge - decide whether to cross or target what's visible
            
            # Check if target is a building (tower or other structure)
            is_building = isinstance(target_entity, Building)
            
            if is_building:
                # Check if we can see the building (it's in line of sight)
                distance_to_target = self.position.distance_to(final_target)
                if distance_to_target <= self.sight_range:
                    # Building is in line of sight - go directly to it
                    return final_target
                else:
                    # Building not in sight - cross the bridge and move forward
                    if self.player_id == 0:  # Blue player crossing to red side
                        # Move forward from bridge towards red side
                        if on_left_bridge:
                            return Position(3.5, 20.0)  # Forward from left bridge
                        else:
                            return Position(14.5, 20.0)  # Forward from right bridge
                    else:  # Red player crossing to blue side
                        # Move forward from bridge towards blue side
                        if on_left_bridge:
                            return Position(3.5, 12.0)  # Forward from left bridge
                        else:
                            return Position(14.5, 12.0)  # Forward from right bridge
            else:
                # Target is a troop - if in line of sight, go directly
                distance_to_target = self.position.distance_to(final_target)
                if distance_to_target <= self.sight_range:
                    return final_target
                else:
                    # Cross bridge to get closer to target
                    if self.player_id == 0:
                        if on_left_bridge:
                            return Position(3.5, 20.0)  # Move from left bridge towards red side
                        else:
                            return Position(14.5, 20.0)  # Move from right bridge towards red side
                    else:
                        if on_left_bridge:
                            return Position(3.5, 12.0)  # Move from left bridge towards blue side
                        else:
                            return Position(14.5, 12.0)  # Move from right bridge towards blue side
        else:
            # Not on bridge yet - check if we need to route around river
            # Direct path to bridge might cross river, so use intermediate waypoint
            
            # Check if we're on the same side as the chosen bridge
            if chosen_bridge.x == 3.5:  # Left bridge
                # For left bridge, approach from left side on land
                bridge_approach = Position(3.5, 14.0) if self.player_id == 0 else Position(3.5, 18.0)
            else:  # Right bridge
                # For right bridge, approach from right side on land  
                bridge_approach = Position(14.5, 14.0) if self.player_id == 0 else Position(14.5, 18.0)
            
            # Check if we can reach the bridge approach position directly
            approach_distance = self.position.distance_to(bridge_approach)
            bridge_distance = self.position.distance_to(chosen_bridge)
            
            # Always use approach waypoint if we're not already close to the bridge
            # This prevents diagonal paths through the river
            if bridge_distance > 2.0:  # If more than 2 tiles away from bridge
                return bridge_approach
            else:
                return chosen_bridge


@dataclass
class Building(Entity):
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update building - only attack, no movement"""
        if not self.is_alive:
            return
        
        # Update attack cooldown
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        
        # Find and attack target
        target = self.get_nearest_target(battle_state.entities)
        if target and self.can_attack_target(target) and self.attack_cooldown <= 0:
            target.take_damage(self.damage)
            self.attack_cooldown = self.card_stats.hit_speed / 1000.0 if self.card_stats.hit_speed else 1.0


@dataclass
class Projectile(Entity):
    target_position: Position = field(default_factory=lambda: Position(0, 0))
    travel_speed: float = 5.0
    splash_radius: float = 0.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update projectile - move towards target"""
        if not self.is_alive:
            return
        
        # Move towards target
        distance = self.position.distance_to(self.target_position)
        if distance <= self.travel_speed * dt:
            # Reached target - deal damage
            self._deal_splash_damage(battle_state)
            self.is_alive = False
        else:
            self._move_towards(self.target_position, dt)
    
    def _move_towards(self, target_pos: Position, dt: float) -> None:
        """Move towards target position"""
        dx = target_pos.x - self.position.x
        dy = target_pos.y - self.position.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            move_distance = self.travel_speed * dt
            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance
            
            self.position.x += move_x
            self.position.y += move_y
    
    def _deal_splash_damage(self, battle_state: 'BattleState') -> None:
        """Deal damage to entities in splash radius"""
        for entity in battle_state.entities.values():
            if entity.player_id == self.player_id or not entity.is_alive:
                continue
            
            distance = entity.position.distance_to(self.target_position)
            if distance <= self.splash_radius:
                entity.take_damage(self.damage)


@dataclass 
class Aura(Entity):
    radius: float = 3.0
    effect_type: str = "damage_boost"
    effect_value: float = 0.0
    
    def update(self, dt: float, battle_state: 'BattleState') -> None:
        """Update aura - apply effects to nearby friendly units"""
        if not self.is_alive:
            return