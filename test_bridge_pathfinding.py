#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_bridge_pathfinding():
    """Test the updated bridge pathfinding with 0.5 tile inward adjustment"""
    
    print("=== Bridge Pathfinding Test ===")
    battle = BattleState()
    
    # Deploy a Blue Knight that needs to cross to Red territory
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Deploy knight in blue territory that will need to cross left bridge
    knight_pos = Position(3, 8)  # Near left bridge, blue side
    success = battle.deploy_card(0, 'Knight', knight_pos)
    print(f"Knight deployment at {knight_pos.x}, {knight_pos.y}: {'Success' if success else 'Failed'}")
    
    # Find the knight
    knight = None
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Knight":
            knight = entity
            break
    
    if not knight:
        print("❌ ERROR: Could not find deployed Knight")
        return
    
    print(f"Knight initial position: ({knight.position.x:.1f}, {knight.position.y:.1f})")
    
    # Test pathfinding at different positions around the bridge
    test_positions = [
        Position(3.0, 14),  # Approaching bridge center
        Position(2.5, 16),  # 0.5 tiles left of bridge center
        Position(3.0, 16),  # Exactly at bridge center  
        Position(3.5, 16),  # 0.5 tiles right of bridge center
        Position(4.0, 16),  # 1.0 tiles right of bridge center (should not be "on bridge")
        Position(2.0, 16),  # 1.0 tiles left of bridge center (should not be "on bridge")
        Position(3.0, 18),  # Past bridge, in red territory
    ]
    
    # Find a target in red territory
    red_tower = None
    for entity in battle.entities.values():
        if isinstance(entity, Building) and entity.player_id == 1:
            if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Tower":
                red_tower = entity
                break
    
    if not red_tower:
        print("❌ ERROR: Could not find red tower")
        return

    print(f"Target: Red tower at ({red_tower.position.x:.1f}, {red_tower.position.y:.1f})")
    print(f"\n=== Testing Bridge Detection at Various Positions ===")
    
    for i, test_pos in enumerate(test_positions):
        # Temporarily move knight to test position
        original_pos = knight.position
        knight.position = test_pos
        
        # Get pathfinding target
        pathfind_target = knight._get_pathfind_target(red_tower)
        
        # Determine what pathfinding decided
        distance_to_target = test_pos.distance_to(red_tower.position)
        distance_to_bridge_center = abs(test_pos.x - 3.0)
        
        # Check if position is considered "on bridge" 
        on_bridge = (abs(test_pos.x - 3.0) <= 1.0 and abs(test_pos.y - 16.0) <= 1.0)
        
        print(f"Pos {i+1}: ({test_pos.x:.1f}, {test_pos.y:.1f})")
        print(f"  Distance to bridge center: {distance_to_bridge_center:.1f}")  
        print(f"  On bridge: {on_bridge}")
        print(f"  Pathfind target: ({pathfind_target.x:.1f}, {pathfind_target.y:.1f})")
        
        # Determine pathfinding behavior
        if pathfind_target.x == red_tower.position.x and pathfind_target.y == red_tower.position.y:
            behavior = "Direct to target"
        elif pathfind_target.x == 3.0 and pathfind_target.y == 16.0:
            behavior = "To bridge center"  
        elif pathfind_target.y == 25.5:  # Red tower y position
            behavior = "To princess tower"
        else:
            behavior = "Other"
        
        print(f"  Behavior: {behavior}")
        print()
        
        # Restore original position
        knight.position = original_pos

    print("=== Bridge Width Analysis ===")
    print("With the 0.5 tile inward adjustment:")
    print("- Bridge center: x=3.0")
    print("- Old detection zone: x=1.5 to x=4.5 (3 tiles wide)")
    print("- NEW detection zone: x=2.0 to x=4.0 (2 tiles wide)")  
    print("- This means units must be closer to bridge center to be considered 'on bridge'")


if __name__ == "__main__":
    test_bridge_pathfinding()