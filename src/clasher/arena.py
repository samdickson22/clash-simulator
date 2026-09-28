from dataclasses import dataclass
import math
from typing import Tuple, List, Optional

from .kinematics import tiles_to_logic_units
from .native_tilemap import nearest_native_path_id


@dataclass 
class Position:
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class TileGrid:
    width: int = 18  # 18 tiles wide (x-axis)
    height: int = 32  # 32 tiles tall (y-axis) 
    tile_size: float = 100.0  
    
    # Tower positions for 18x32 arena (authentic CR layout)
    # Player 0 (bottom)
    BLUE_KING_TOWER = Position(9.0, 3.0)     # King tower centered at x=9 (middle of 18-wide arena)
    BLUE_LEFT_TOWER = Position(3.5, 6.5)     # Left princess tower
    BLUE_RIGHT_TOWER = Position(14.5, 6.5)   # Right princess tower (corrected for better symmetry)
    
    # Player 1 (top) 
    RED_KING_TOWER = Position(9.0, 29.0)     # King tower centered at x=9
    RED_LEFT_TOWER = Position(3.5, 25.5)     # Left princess tower  
    RED_RIGHT_TOWER = Position(14.5, 25.5)   # Right princess tower (corrected for better symmetry)
    
    # Bridge positions across river (3 tiles wide each)
    LEFT_BRIDGE = Position(3.5, 16.0)   # Left bridge center of center tile (tiles 2,3,4 -> center at 3.5)
    RIGHT_BRIDGE = Position(14.5, 16.0) # Right bridge center of center tile (tiles 13,14,15 -> center at 14.5)
    
    # River spans y=15-16 (2 tiles tall)
    RIVER_Y1 = 15.0
    RIVER_Y2 = 16.0
    
    # Blocked tiles (unplayable and unwalkable areas) - these appear as gray fences/barriers
    # Pattern from real Clash Royale: 6 gray, 6 green, 6 gray on top/bottom rows
    BLOCKED_TILES = [
        # Edge tiles next to river
        (0, 14),   # Left edge of arena, bottom land next to river
        (0, 17),   # Left edge of arena, top land next to river
        (17, 14),  # Right edge of arena, bottom land next to river  
        (17, 17),  # Right edge of arena, top land next to river
        
        # Top row (y=0): 6 gray fences (0-5), 6 green king area (6-11), 6 gray fences (12-17)
        (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),           # Left 6 gray fence tiles
        (12, 0), (13, 0), (14, 0), (15, 0), (16, 0), (17, 0),     # Right 6 gray fence tiles
        
        # Bottom row (y=31): 6 gray fences (0-5), 6 green king area (6-11), 6 gray fences (12-17)
        (0, 31), (1, 31), (2, 31), (3, 31), (4, 31), (5, 31),     # Left 6 gray fence tiles
        (12, 31), (13, 31), (14, 31), (15, 31), (16, 31), (17, 31), # Right 6 gray fence tiles
    ]
    
    def is_valid_position(self, pos: Position) -> bool:
        """Check if position is within arena bounds"""
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height
    
    def is_blocked_tile(self, x: int, y: int) -> bool:
        """Check if a tile coordinate is blocked (unplayable)"""
        return (x, y) in self.BLOCKED_TILES

    def native_path_id_at(
        self,
        pos: Position,
        other_x: Optional[float] = None,
    ) -> int:
        """Return the lane selected by the standard arena's native path grid."""

        return nearest_native_path_id(
            tiles_to_logic_units(pos.x),
            tiles_to_logic_units(pos.y),
            (
                -1
                if other_x is None
                else tiles_to_logic_units(other_x)
            ),
        )

    @staticmethod
    def _touching_tiles(value: float, limit: int) -> tuple[int, ...]:
        """Return every tile touched by one continuous coordinate."""
        rounded = round(value)
        if math.isclose(value, rounded, abs_tol=1e-9):
            return tuple(
                tile
                for tile in (rounded - 1, rounded)
                if 0 <= tile < limit
            )
        tile = math.floor(value)
        return (tile,) if 0 <= tile < limit else ()

    def is_blocked_position(self, pos: Position) -> bool:
        """Return whether a point touches any blocked arena tile."""
        touching_x = self._touching_tiles(pos.x, self.width)
        touching_y = self._touching_tiles(pos.y, self.height)
        return any(
            self.is_blocked_tile(tile_x, tile_y)
            for tile_x in touching_x
            for tile_y in touching_y
        )
    
    def is_walkable(self, pos: Position) -> bool:
        """Check if a position is walkable (not river, not blocked tiles)"""
        # Check bounds
        if not self.is_valid_position(pos):
            return False
        
        # A point exactly on a tile edge touches both adjacent tiles. Treat it
        # as blocked if either tile is blocked; assigning boundaries with
        # ``int`` makes the upper/right arena behave differently after a 180°
        # rotation and can place an entity center on the edge of a fence.
        if self.is_blocked_position(pos):
            return False
        
        # Check if it's in the river (y=15-16), unless it's on a bridge
        if self.RIVER_Y1 <= pos.y <= self.RIVER_Y2 + 1.0:
            # Check if on bridge (3 tiles wide each, allowing fractional positions within tiles)
            on_left_bridge = 2.0 <= pos.x <= 5.0
            on_right_bridge = 13.0 <= pos.x <= 16.0
            return on_left_bridge or on_right_bridge
        
        return True
    
    def get_deploy_zones(self, player_id: int, battle_state=None) -> List[Tuple[float, float, float, float]]:
        """Get valid deployment zones for a player (x1, y1, x2, y2)
        Expands to include bridge areas and 4 tiles back when towers are destroyed"""
        zones = []
        
        if player_id == 0:  # Player 0 (bottom half)
            # Basic deployment zone (bottom half, excluding river)
            zones.append((0, 1, self.width, self.RIVER_Y1))  # y=1 to y=14
            
            # Always include the 6 blocks behind own king tower (including row 0)
            zones.append((6, 0, 12, 6))  # Behind blue king: x=6-11, y=0-5 (6 tiles behind own king, including edge row)
            
            # Check for expanded zones based on destroyed enemy towers
            if battle_state:
                # If red left tower is destroyed, blue player can spawn on left half of arena and 4 tiles back
                if battle_state.players[1].left_tower_hp <= 0:
                    zones.append((0, self.RIVER_Y2 + 1, 9, self.RIVER_Y2 + 5))  # Left half: x=0-8, y=17-20
                    zones.append((2.5, self.RIVER_Y1, 4.5, self.RIVER_Y2 + 1))
                
                # If red right tower is destroyed, blue player can spawn on right half of arena and 4 tiles back  
                if battle_state.players[1].right_tower_hp <= 0:
                    zones.append((9, self.RIVER_Y2 + 1, self.width, self.RIVER_Y2 + 5))  # Right half: x=9-17, y=17-20
                    zones.append((13.5, self.RIVER_Y1, 15.5, self.RIVER_Y2 + 1))
                    
        else:  # Player 1 (top half)  
            # Basic deployment zone (top half, excluding river)
            zones.append((0, self.RIVER_Y2 + 1, self.width, 31))  # y=17 to y=30
            
            # Always include the 6 blocks behind own king tower (including row 31)
            zones.append((6, 26, 12, 32))  # Behind red king: x=6-11, y=26-31 (6 tiles behind own king, including edge row)
            
            # Check for expanded zones based on destroyed enemy towers
            if battle_state:
                # If blue left tower is destroyed, red player can spawn on left half of arena and 4 tiles back
                if battle_state.players[0].left_tower_hp <= 0:
                    zones.append((0, self.RIVER_Y1 - 4, 9, self.RIVER_Y1))  # Left half: x=0-8, y=11-14
                    zones.append((2.5, self.RIVER_Y1, 4.5, self.RIVER_Y2 + 1))
                
                # If blue right tower is destroyed, red player can spawn on right half of arena and 4 tiles back
                if battle_state.players[0].right_tower_hp <= 0:
                    zones.append((9, self.RIVER_Y1 - 4, self.width, self.RIVER_Y1))  # Right half: x=9-17, y=11-14
                    zones.append((13.5, self.RIVER_Y1, 15.5, self.RIVER_Y2 + 1))
        
        return zones
    
    def can_deploy_at(self, pos: Position, player_id: int, battle_state=None, is_spell=False, spell_obj=None) -> bool:
        """Check if position is valid for deployment"""
        # Check basic bounds
        if not self.is_valid_position(pos):
            return False
        
        # Check if this is a blocked tile (gray, unplayable)
        tile_pos = (int(pos.x), int(pos.y))
        if tile_pos in self.BLOCKED_TILES:
            return False
        
        # Check if position overlaps with living tower area (troops cannot deploy on towers)
        if not is_spell and self.is_tower_tile(pos, battle_state):
            return False
        
        # Most spells can be deployed anywhere.  Payloads serialized as
        # spellAsDeploy (Log, Barbarian Barrel, Royal Delivery, etc.) follow
        # the player's current troop deployment territory.
        if is_spell:
            if (
                getattr(spell_obj, "requires_walkable_target", False)
                and not self.is_walkable(pos)
            ):
                return False
            if self._requires_deploy_zone_spell(spell_obj):
                pass  # Continue to deployment zone validation below
            else:
                # Regular spells can be deployed anywhere
                return True
        
        # Special restriction: only middle 6 tiles (x=6-11) playable on rows 0 and 31
        if pos.y == 0 or pos.y == 31:
            if not (6 <= pos.x <= 11):
                return False
        
        # Check deployment zones (including expanded zones after tower destruction)
        zones = self.get_deploy_zones(player_id, battle_state)
        for x1, y1, x2, y2 in zones:
            if x1 <= pos.x < x2 and y1 <= pos.y < y2:
                return True
        
        # Special case: allow middle 6 tiles on edge rows for respective players
        if player_id == 0 and pos.y == 0 and 6 <= pos.x <= 11:
            return True
        elif player_id == 1 and pos.y == 31 and 6 <= pos.x <= 11:
            return True
            
        return False
    
    def _is_rolling_projectile_spell(self, spell_obj) -> bool:
        """Check if spell is a rolling projectile that requires territory validation"""
        if not spell_obj:
            return False
        
        # Import here to avoid circular imports
        from .spells import RollingProjectileSpell
        return isinstance(spell_obj, RollingProjectileSpell)

    def _requires_deploy_zone_spell(self, spell_obj) -> bool:
        if not spell_obj:
            return False
        return bool(
            getattr(spell_obj, "requires_territory", False)
            or self._is_rolling_projectile_spell(spell_obj)
        )
    
    def world_to_tile(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to tile coordinates"""
        return int(x / self.tile_size), int(y / self.tile_size)
    
    def tile_to_world(self, tile_x: int, tile_y: int) -> Position:
        """Convert tile coordinates to world position"""
        return Position(
            tile_x * self.tile_size + self.tile_size / 2,
            tile_y * self.tile_size + self.tile_size / 2
        )
    
    def is_tower_tile(self, pos: Position, battle_state=None) -> bool:
        """Check if position overlaps with any living tower's occupied area"""
        # Princess towers: 3x3 area (1.5 tiles radius from center)
        # King towers: 4x4 area (2.0 tiles radius from center)
        
        # Check all tower positions
        towers = [
            (self.BLUE_LEFT_TOWER, 1.5, 0),    # Princess tower, 3x3
            (self.BLUE_RIGHT_TOWER, 1.5, 0),   # Princess tower, 3x3  
            (self.BLUE_KING_TOWER, 2.0, 0),    # King tower, 4x4
            (self.RED_LEFT_TOWER, 1.5, 1),     # Princess tower, 3x3
            (self.RED_RIGHT_TOWER, 1.5, 1),    # Princess tower, 3x3
            (self.RED_KING_TOWER, 2.0, 1)      # King tower, 4x4
        ]
        
        for tower_pos, radius, player_id in towers:
            # Check if tower is still alive (if battle_state provided)
            if battle_state:
                tower_alive = self._is_tower_alive(tower_pos, player_id, battle_state)
                if not tower_alive:
                    continue  # Skip dead towers
            
            # Check if position is within tower's area
            dx = abs(pos.x - tower_pos.x)
            dy = abs(pos.y - tower_pos.y)
            
            if dx <= radius + 1e-9 and dy <= radius + 1e-9:
                return True
        
        return False
    
    def _is_tower_alive(self, tower_pos: Position, player_id: int, battle_state) -> bool:
        """Check if tower at given position is still alive"""
        if not battle_state:
            return True  # Assume alive if no battle state

        cached = getattr(battle_state, "_is_tower_alive_cached", None)
        if callable(cached):
            return bool(cached(tower_pos, player_id))
        
        # Find tower entity at this position
        for entity in battle_state.entities.values():
            if (hasattr(entity, 'position') and 
                entity.position.x == tower_pos.x and 
                entity.position.y == tower_pos.y and
                getattr(entity, 'player_id', -1) == player_id):
                return entity.is_alive
        
        return False  # Tower not found, assume dead
    
    def get_tower_blocked_x_ranges(self, y: float, battle_state=None) -> List[Tuple[float, float]]:
        """Get X coordinate ranges blocked by towers at a specific Y coordinate"""
        blocked_ranges = []
        
        # Check all towers
        towers = [
            (self.BLUE_LEFT_TOWER, 1.5, 0),    # Princess tower, 3x3
            (self.BLUE_RIGHT_TOWER, 1.5, 0),   # Princess tower, 3x3  
            (self.BLUE_KING_TOWER, 2.0, 0),    # King tower, 4x4
            (self.RED_LEFT_TOWER, 1.5, 1),     # Princess tower, 3x3
            (self.RED_RIGHT_TOWER, 1.5, 1),    # Princess tower, 3x3
            (self.RED_KING_TOWER, 2.0, 1)      # King tower, 4x4
        ]
        
        for tower_pos, radius, player_id in towers:
            # Check if tower is still alive
            if battle_state:
                tower_alive = self._is_tower_alive(tower_pos, player_id, battle_state)
                if not tower_alive:
                    continue
            
            # Check if Y coordinate intersects with tower area
            dy = abs(y - tower_pos.y)
            if dy <= radius + 1e-9:
                # Y coordinate overlaps with tower, add X range to blocked list
                x_min = tower_pos.x - radius
                x_max = tower_pos.x + radius
                blocked_ranges.append((x_min, x_max))
        
        return blocked_ranges
