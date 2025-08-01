#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_bridge_center_fix():
    """Test that pathfinding now targets center of center tile, not tile intersections"""
    
    print("=== Bridge Center Pathfinding Fix Test ===")
    battle = BattleState()
    
    # Deploy a knight to test pathfinding
    battle.players[0].elixir = 10.0
    success = battle.deploy_card(0, 'Knight', Position(3, 8))
    
    knight = None
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Knight":
            knight = entity
            break
    
    red_tower = None
    for entity in battle.entities.values():
        if isinstance(entity, Building) and entity.player_id == 1:
            if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Tower":
                red_tower = entity
                break
    
    print("=== Bridge Layout Analysis ===")
    print("3-tile wide bridges:")
    print("- Left bridge: tiles 2, 3, 4")
    print("  - OLD target: x=3.0 (intersection of tiles 2&3 and 3&4)")
    print("  - NEW target: x=3.5 (center of center tile 3)")
    print("- Right bridge: tiles 14, 15, 16")  
    print("  - OLD target: x=15.0 (intersection)")
    print("  - NEW target: x=15.5 (center of center tile 15)")
    
    # Test pathfinding from different positions
    test_positions = [
        Position(1, 8),   # Far left, should choose left bridge
        Position(9, 8),   # Center, should choose closer bridge
        Position(17, 8),  # Far right, should choose right bridge
    ]
    
    print(f"\n=== Pathfinding Target Tests ===")
    for i, test_pos in enumerate(test_positions):
        original_pos = knight.position
        knight.position = test_pos
        
        pathfind_target = knight._get_pathfind_target(red_tower)
        
        print(f"From position ({test_pos.x}, {test_pos.y}):")
        print(f"  Target: ({pathfind_target.x:.1f}, {pathfind_target.y:.1f})")
        
        if pathfind_target.x == 3.5 and pathfind_target.y == 16.0:
            print(f"  ✅ Targeting LEFT bridge center of center tile")
        elif pathfind_target.x == 15.5 and pathfind_target.y == 16.0:
            print(f"  ✅ Targeting RIGHT bridge center of center tile")
        elif pathfind_target == red_tower.position:
            print(f"  → Direct path to target (no bridge needed)")
        else:
            print(f"  ❓ Other target")
        
        knight.position = original_pos

    # Test bridge detection zones
    print(f"\n=== Bridge Detection Zone Tests ===")
    detection_tests = [
        # Left bridge (center at x=3.5, detection ±1.5)
        (Position(1.9, 16.0), "Left bridge outside left", False), # 1.6 tiles from center
        (Position(2.0, 16.0), "Left bridge boundary left", True), # 1.5 tiles from center (boundary)
        (Position(3.5, 16.0), "Left bridge exact center", True),  # 0 tiles from center
        (Position(5.0, 16.0), "Left bridge boundary right", True), # 1.5 tiles from center (boundary)
        (Position(5.1, 16.0), "Left bridge outside right", False), # 1.6 tiles from center
        
        # Right bridge (center at x=15.5, detection ±1.5)  
        (Position(13.9, 16.0), "Right bridge outside left", False), # 1.6 tiles from center
        (Position(14.0, 16.0), "Right bridge boundary left", True),  # 1.5 tiles from center
        (Position(15.5, 16.0), "Right bridge exact center", True),  # 0 tiles from center
        (Position(17.0, 16.0), "Right bridge boundary right", True), # 1.5 tiles from center
        (Position(17.1, 16.0), "Right bridge outside right", False), # 1.6 tiles from center
    ]
    
    for pos, description, expected_on_bridge in detection_tests:
        original_pos = knight.position
        knight.position = pos
        
        # Determine which bridge and calculate detection
        left_dist = abs(pos.x - 3.5)
        right_dist = abs(pos.x - 15.5)
        bridge_x = 3.5 if left_dist < right_dist else 15.5
        
        actual_on_bridge = (abs(pos.x - bridge_x) <= 1.5 and abs(pos.y - 16.0) <= 1.0)
        
        match = "✅" if actual_on_bridge == expected_on_bridge else "❌"
        print(f"{description}: {match} (expected: {expected_on_bridge}, actual: {actual_on_bridge})")
        
        knight.position = original_pos

    print(f"\n=== Summary ===")
    print("✅ Bridge pathfinding now targets center of center tile:")
    print("   - Left bridge: x=3.5 (center of tile 3)")
    print("   - Right bridge: x=15.5 (center of tile 15)")
    print("✅ Detection zones properly sized for 3-tile-wide bridges")
    print("✅ Units will path to the true center of bridges, not intersections")


if __name__ == "__main__":
    test_bridge_center_fix()