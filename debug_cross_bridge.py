#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def debug_bridge_crossing():
    """Test various bridge crossing scenarios"""
    
    print("=== Bridge Crossing Debug ===")
    
    # Test case 1: Knights at different x positions requiring bridge crossing
    battle = BattleState()
    
    # Deploy blue knight on left side, red knight on right side - both should cross
    blue_result = battle.deploy_card(0, 'Knight', Position(2, 12))  # Left side, bottom
    red_result = battle.deploy_card(1, 'Knight', Position(16, 20))  # Right side, top
    
    print(f"Blue knight (left) deployment: {blue_result}")
    print(f"Red knight (right) deployment: {red_result}")
    
    # Find both knights
    blue_knight = None
    red_knight = None
    for entity in battle.entities.values():
        if (hasattr(entity, 'card_stats') and entity.card_stats and 
            entity.card_stats.name == 'Knight'):
            if entity.player_id == 0:
                blue_knight = entity
            else:
                red_knight = entity
    
    if not blue_knight or not red_knight:
        print("Could not find both knights!")
        return
    
    print(f"\nInitial positions:")
    print(f"Blue Knight: ({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) Player {blue_knight.player_id}")
    print(f"Red Knight:  ({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) Player {red_knight.player_id}")
    
    # Check their targets and pathfinding
    blue_target = blue_knight.get_nearest_target(battle.entities)
    red_target = red_knight.get_nearest_target(battle.entities)
    
    print(f"\nTargeting:")
    if blue_target:
        target_type = "Knight" if hasattr(blue_target, 'card_stats') else "Tower"
        blue_pathfind = blue_knight._get_pathfind_target(blue_target)
        print(f"Blue knight -> {target_type} at ({blue_target.position.x:.2f}, {blue_target.position.y:.2f})")
        print(f"  Pathfind target: ({blue_pathfind.x:.2f}, {blue_pathfind.y:.2f})")
        
        # Check side detection
        current_side = 0 if blue_knight.position.y < 16.0 else 1
        target_side = 0 if blue_target.position.y < 16.0 else 1
        need_to_cross = current_side != target_side
        print(f"  Current side: {current_side}, Target side: {target_side}, Need to cross: {need_to_cross}")
    
    if red_target:
        target_type = "Knight" if hasattr(red_target, 'card_stats') else "Tower"
        red_pathfind = red_knight._get_pathfind_target(red_target)
        print(f"Red knight -> {target_type} at ({red_target.position.x:.2f}, {red_target.position.y:.2f})")
        print(f"  Pathfind target: ({red_pathfind.x:.2f}, {red_pathfind.y:.2f})")
        
        # Check side detection
        current_side = 0 if red_knight.position.y < 16.0 else 1
        target_side = 0 if red_target.position.y < 16.0 else 1
        need_to_cross = current_side != target_side
        print(f"  Current side: {current_side}, Target side: {target_side}, Need to cross: {need_to_cross}")

    print(f"\nRunning simulation...")
    # Simulate a few steps
    for step in range(1, 10):
        battle.update(0.033)  # 33ms per tick
        
        blue_pos = (blue_knight.position.x, blue_knight.position.y)
        red_pos = (red_knight.position.x, red_knight.position.y)
        
        # Check new targets
        blue_target_now = blue_knight.get_nearest_target(battle.entities)
        red_target_now = red_knight.get_nearest_target(battle.entities)
        
        blue_target_type = "Knight" if (blue_target_now and hasattr(blue_target_now, 'card_stats')) else "Tower"
        red_target_type = "Knight" if (red_target_now and hasattr(red_target_now, 'card_stats')) else "Tower"
        
        print(f"  Step {step:2d}: Blue->({blue_pos[0]:.1f},{blue_pos[1]:.1f}) Red->({red_pos[0]:.1f},{red_pos[1]:.1f}) Targets: B->{blue_target_type} R->{red_target_type}")

if __name__ == "__main__":
    debug_bridge_crossing()