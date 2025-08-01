#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position, TileGrid
from clasher.entities import Troop
from clasher.data import CardStats

def test_blocked_walkability():
    """Test that ground units cannot walk through blocked tiles"""
    
    print("=== TESTING BLOCKED TILE WALKABILITY ===")
    
    arena = TileGrid()
    
    # Test key blocked tiles
    test_tiles = [
        # River edge tiles
        (0, 14), (0, 17), (17, 14), (17, 17),
        # Top row fence tiles
        (0, 0), (5, 0), (12, 0), (17, 0),
        # Bottom row fence tiles
        (0, 31), (5, 31), (12, 31), (17, 31)
    ]
    
    print("Testing arena.is_walkable() for blocked tiles:")
    for x, y in test_tiles:
        pos = Position(x, y)
        walkable = arena.is_walkable(pos)
        is_blocked = arena.is_blocked_tile(x, y)
        print(f"  Tile ({x}, {y}): blocked={is_blocked}, walkable={walkable}")
        
        if is_blocked and walkable:
            print(f"    ❌ ERROR: Blocked tile should not be walkable!")
        elif is_blocked and not walkable:
            print(f"    ✅ CORRECT: Blocked tile is unwalkable")
    
    # Test that normal tiles are still walkable
    print("\nTesting normal tiles are still walkable:")
    normal_tiles = [(5, 5), (10, 10), (8, 20), (15, 25)]
    for x, y in normal_tiles:
        pos = Position(x, y)
        walkable = arena.is_walkable(pos)
        is_blocked = arena.is_blocked_tile(x, y)
        print(f"  Tile ({x}, {y}): blocked={is_blocked}, walkable={walkable}")
        
        if not is_blocked and not walkable:
            print(f"    ❌ ERROR: Normal tile should be walkable!")
        elif not is_blocked and walkable:
            print(f"    ✅ CORRECT: Normal tile is walkable")
    
    # Test king area tiles (should be walkable but not deployable for fence tiles)  
    print("\nTesting king area tiles:")
    king_tiles = [(6, 0), (9, 0), (11, 0), (6, 31), (9, 31), (11, 31)]
    for x, y in king_tiles:
        pos = Position(x, y)
        walkable = arena.is_walkable(pos)
        is_blocked = arena.is_blocked_tile(x, y)
        print(f"  King tile ({x}, {y}): blocked={is_blocked}, walkable={walkable}")
        
        if not walkable:
            print(f"    ❌ ERROR: King area should be walkable!")
        else:
            print(f"    ✅ CORRECT: King area is walkable")

def test_troop_movement_blocked():
    """Test that troops cannot move through blocked tiles"""
    
    print("\n=== TESTING TROOP MOVEMENT WITH BLOCKED TILES ===")
    
    battle = BattleState()
    
    # Create a test troop (ground unit)
    card_stats = CardStats(
        name="Knight",
        hit_speed=1200,
        speed=60,  # 1 tile per second  
        deploy_time=1000,
        range=1.0,
        target="Ground",
        cost=3,
        hitpoints=1400,
        damage=167,
        sight_range=5.5
    )
    
    # Place troop next to a blocked tile
    troop = Troop(
        id=1,
        position=Position(1.0, 14.0),  # Next to blocked tile (0, 14)
        player_id=0,
        card_stats=card_stats,
        hitpoints=1400,
        max_hitpoints=1400,
        damage=167,
        range=1.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False  # Ground unit
    )
    
    print(f"Initial troop position: ({troop.position.x}, {troop.position.y})")
    
    # Try to move the troop towards the blocked tile
    print(f"Attempting to move towards blocked tile (0, 14)...")
    
    # Simulate what happens in _move_towards_target when moving towards blocked tile
    target_pos = Position(0.0, 14.0)  # Blocked tile
    dx = target_pos.x - troop.position.x
    dy = target_pos.y - troop.position.y 
    distance = (dx * dx + dy * dy) ** 0.5
    
    if distance > 0:
        dt = 1.0  # 1 second timestep
        speed_tiles_per_second = troop.speed / 60.0  # Convert tiles/min to tiles/sec
        move_distance = speed_tiles_per_second * dt
        
        if move_distance > distance:
            move_distance = distance
        
        move_x = (dx / distance) * move_distance
        move_y = (dy / distance) * move_distance
        
        # Check if the new position would be walkable (this is the key test)
        new_position = Position(troop.position.x + move_x, troop.position.y + move_y)
        
        print(f"Attempting to move to: ({new_position.x}, {new_position.y})")
        print(f"Is new position walkable: {battle.arena.is_walkable(new_position)}")
        
        # This is the same logic as in entities.py
        if troop.is_air_unit or (battle and battle.arena.is_walkable(new_position)):
            troop.position.x += move_x
            troop.position.y += move_y
            print(f"✅ Movement allowed - new position: ({troop.position.x}, {troop.position.y})")
        else:
            print(f"❌ Movement blocked - position unchanged: ({troop.position.x}, {troop.position.y})")
            
    print(f"Final troop position: ({troop.position.x}, {troop.position.y})")

if __name__ == "__main__":
    test_blocked_walkability()
    test_troop_movement_blocked()