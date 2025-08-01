#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.arena import Position, TileGrid
from clasher.battle import BattleState

def debug_advanced_pathfinding():
    """Debug the advanced pathfinding logic after tower destruction"""
    
    print("=== DEBUGGING ADVANCED PATHFINDING ===")
    
    arena = TileGrid()
    
    # Test the problematic "center bridge" position
    center_bridge = Position(9.0, 16.0)
    print(f"Center bridge position: ({center_bridge.x}, {center_bridge.y})")
    print(f"Center bridge walkable: {arena.is_walkable(center_bridge)}")
    
    # Check actual bridge positions
    print(f"\nActual bridge positions:")
    print(f"Left bridge center: ({arena.LEFT_BRIDGE.x}, {arena.LEFT_BRIDGE.y})")
    print(f"Left bridge walkable: {arena.is_walkable(arena.LEFT_BRIDGE)}")
    print(f"Right bridge center: ({arena.RIGHT_BRIDGE.x}, {arena.RIGHT_BRIDGE.y})")
    print(f"Right bridge walkable: {arena.is_walkable(arena.RIGHT_BRIDGE)}")
    
    # Test the "on_center_bridge" detection logic
    print(f"\nTesting 'on_center_bridge' detection:")
    
    test_positions = [
        Position(9.0, 16.0),   # Exact "center bridge" position
        Position(8.0, 16.0),   # 1 tile left of center
        Position(10.0, 16.0),  # 1 tile right of center
        Position(9.0, 15.0),   # 1 tile below center
        Position(9.0, 17.0),   # 1 tile above center
        Position(3.5, 16.0),   # Actual left bridge center
        Position(14.5, 16.0),  # Actual right bridge center
    ]
    
    for pos in test_positions:
        # Simulate the on_center_bridge check from entities.py
        on_center_bridge = (abs(pos.x - 9.0) <= 1.0 and abs(pos.y - 16.0) <= 1.0)
        walkable = arena.is_walkable(pos)
        
        print(f"  Position ({pos.x}, {pos.y}): on_center_bridge={on_center_bridge}, walkable={walkable}")
        
        if on_center_bridge and not walkable:
            print(f"    ❌ PROBLEM: Detected as 'on center bridge' but not walkable!")
        elif not on_center_bridge and pos.x in [3.5, 14.5] and pos.y == 16.0:
            print(f"    ❌ PROBLEM: Actual bridge not detected as 'center bridge'!")
    
    # Show what happens when troops try to path to the center bridge
    print(f"\nWhat happens when troops target the center bridge:")
    print(f"Target position: (9.0, 16.0)")
    print(f"Is river tile: {arena.RIVER_Y1 <= 16.0 <= arena.RIVER_Y2}")
    print(f"On left bridge: {2.0 <= 9.0 < 5.0}")
    print(f"On right bridge: {13.0 <= 9.0 < 16.0}")
    print(f"Should be walkable: {arena.is_walkable(center_bridge)}")
    
    if not arena.is_walkable(center_bridge):
        print(f"🚨 MAJOR ISSUE: Advanced pathfinding targets unreachable position!")
        print(f"This explains why troops circle around - they can't reach their target!")

def test_better_bridge_targets():
    """Test what better bridge targets would be"""
    
    print(f"\n=== TESTING BETTER BRIDGE TARGETS ===")
    
    arena = TileGrid()
    
    # Test both actual bridges as potential targets
    bridges = [
        {"name": "Left Bridge", "pos": arena.LEFT_BRIDGE},
        {"name": "Right Bridge", "pos": arena.RIGHT_BRIDGE}
    ]
    
    for bridge in bridges:
        name = bridge["name"]
        pos = bridge["pos"]
        walkable = arena.is_walkable(pos)
        
        print(f"{name}: ({pos.x}, {pos.y}) - walkable: {walkable}")
        
        if walkable:
            print(f"  ✅ This would be a good pathfinding target")
        else:
            print(f"  ❌ This would NOT be a good pathfinding target")
    
    # Suggest a fix
    print(f"\n💡 SUGGESTED FIX:")
    print(f"Instead of targeting unreachable center bridge (9.0, 16.0),")
    print(f"troops should choose the nearest actual bridge:")
    print(f"- Left bridge: (3.5, 16.0)")
    print(f"- Right bridge: (14.5, 16.0)")

if __name__ == "__main__":
    debug_advanced_pathfinding()
    test_better_bridge_targets()