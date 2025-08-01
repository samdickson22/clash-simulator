#!/usr/bin/env python3
"""
Debug script to check red knight pathfinding
"""

from src.clasher.engine import BattleEngine
from src.clasher.arena import Position

def debug_red_knight():
    """Debug red knight pathfinding across bridge"""
    print("=== Red Knight Pathfinding Debug ===")
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    # Deploy red knight
    battle.players[1].elixir = 10.0
    result = battle.deploy_card(1, 'Knight', Position(9, 20))
    print(f"Red knight deployment: {result}")
    
    # Find the red knight
    red_knight = None
    for entity in battle.entities.values():
        if (hasattr(entity, 'card_stats') and entity.card_stats and 
            entity.card_stats.name == 'Knight' and entity.player_id == 1):
            red_knight = entity
            break
    
    if not red_knight:
        print("ERROR: Red knight not found!")
        return
    
    print(f"\nRed Knight State:")
    print(f"  Position: ({red_knight.position.x:.2f}, {red_knight.position.y:.2f})")
    print(f"  Player ID: {red_knight.player_id}")
    print(f"  Speed: {red_knight.speed}")
    print(f"  Range: {red_knight.range:.2f}")
    
    # Find target
    target = red_knight.get_nearest_target(battle.entities)
    if target:
        print(f"\nTarget: {target.card_stats.name} (Player {target.player_id})")
        print(f"  Target position: ({target.position.x:.2f}, {target.position.y:.2f})")
        distance = red_knight.position.distance_to(target.position)
        print(f"  Distance: {distance:.2f}")
        
        # Check sides
        knight_side = 0 if red_knight.position.y < 16.0 else 1
        target_side = 0 if target.position.y < 16.0 else 1
        print(f"  Knight side: {knight_side} (y={red_knight.position.y:.2f})")
        print(f"  Target side: {target_side} (y={target.position.y:.2f})")
        print(f"  Need to cross river: {knight_side != target_side}")
        
        # Check bridge selection logic
        if knight_side != target_side:
            left_bridge_dist = abs(red_knight.position.x - 3.0)
            right_bridge_dist = abs(red_knight.position.x - 15.0)
            print(f"  Distance to left bridge (x=3): {left_bridge_dist:.2f}")
            print(f"  Distance to right bridge (x=15): {right_bridge_dist:.2f}")
            
            if left_bridge_dist < right_bridge_dist:
                chosen_bridge = "left (x=3)"
            else:
                chosen_bridge = "right (x=15)"
            print(f"  Would choose: {chosen_bridge}")
    
    # Simulate movement to see what happens
    print(f"\nSimulating movement...")
    for step in range(20):
        old_pos = (red_knight.position.x, red_knight.position.y)
        battle.step(speed_factor=1.0)
        new_pos = (red_knight.position.x, red_knight.position.y)
        
        moved = abs(old_pos[0] - new_pos[0]) > 0.01 or abs(old_pos[1] - new_pos[1]) > 0.01
        
        # Check current side
        current_side = 0 if red_knight.position.y < 16.0 else 1
        at_river = abs(red_knight.position.y - 16.0) < 0.5
        
        print(f"  Step {step+1:2d}: ({new_pos[0]:.2f}, {new_pos[1]:.2f}) "
              f"Side: {current_side} AtRiver: {at_river} "
              f"{'MOVED' if moved else 'STUCK'}")
        
        if not moved:
            print(f"    >>> STUCK! Investigating...")
            if target:
                # Manual pathfinding check
                dx = target.position.x - red_knight.position.x
                dy = target.position.y - red_knight.position.y
                distance = (dx * dx + dy * dy) ** 0.5
                
                knight_side = 0 if red_knight.position.y < 16.0 else 1
                target_side = 0 if target.position.y < 16.0 else 1
                
                print(f"    Target vector: dx={dx:.2f}, dy={dy:.2f}, dist={distance:.2f}")
                print(f"    Knight side: {knight_side}, Target side: {target_side}")
                print(f"    At river check: {abs(red_knight.position.y - 16.0)} < 0.5 = {abs(red_knight.position.y - 16.0) < 0.5}")
                
                if knight_side != target_side and abs(red_knight.position.y - 16.0) < 0.5:
                    print(f"    Should be going to bridge...")
                    if abs(red_knight.position.x - 3.0) < abs(red_knight.position.x - 15.0):
                        bridge_x = 3.0
                        bridge_name = "left"
                    else:
                        bridge_x = 15.0
                        bridge_name = "right"
                    
                    bridge_dx = bridge_x - red_knight.position.x
                    bridge_dy = 16.0 - red_knight.position.y
                    print(f"    Bridge {bridge_name}: dx={bridge_dx:.2f}, dy={bridge_dy:.2f}")
            break

if __name__ == "__main__":
    debug_red_knight()