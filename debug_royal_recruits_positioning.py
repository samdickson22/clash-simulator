#!/usr/bin/env python3
"""
Debug Royal Recruits positioning algorithm
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def debug_royal_recruits_positioning():
    """Debug the safe positioning algorithm for Royal Recruits"""
    
    print("=== Debugging Royal Recruits Positioning Algorithm ===")
    
    # Create battle state
    battle = BattleState()
    
    # Test the positioning algorithm directly
    center_pos = Position(9.0, 6.5)  # Y intersects with princess towers
    count = 6
    spacing = 2.5
    
    print(f"Center position: ({center_pos.x}, {center_pos.y})")
    print(f"Count: {count}, Spacing: {spacing}")
    
    # Get blocked ranges
    blocked_ranges = battle.arena.get_tower_blocked_x_ranges(center_pos.y, battle)
    print(f"Blocked X ranges: {blocked_ranges}")
    
    # Test the safe positioning function
    positions = battle._find_safe_recruit_positions(center_pos, count, spacing, blocked_ranges)
    print(f"Generated positions: {positions}")
    
    # Check for duplicates
    unique_positions = set(positions)
    if len(unique_positions) != len(positions):
        print(f"❌ Found {len(positions) - len(unique_positions)} duplicate positions!")
        position_counts = {}
        for pos in positions:
            position_counts[pos] = position_counts.get(pos, 0) + 1
        print(f"Position counts: {position_counts}")
    else:
        print("✅ All positions are unique")
    
    # Test different scenarios
    print(f"\n--- Testing different Y coordinates ---")
    
    test_cases = [
        (2.5, "King tower level"),
        (6.5, "Princess tower level"), 
        (10.0, "Safe middle area"),
        (25.5, "Enemy princess towers"),
        (29.5, "Enemy king tower")
    ]
    
    for y, description in test_cases:
        print(f"\nY={y} ({description}):")
        test_pos = Position(9.0, y)
        blocked = battle.arena.get_tower_blocked_x_ranges(y, battle)
        positions = battle._find_safe_recruit_positions(test_pos, 6, 2.5, blocked)
        print(f"  Blocked ranges: {blocked}")
        print(f"  Positions: {positions}")
        print(f"  Unique: {len(set(positions)) == len(positions)}")

if __name__ == "__main__":
    debug_royal_recruits_positioning()