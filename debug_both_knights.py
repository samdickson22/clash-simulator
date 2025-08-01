#!/usr/bin/env python3
"""
Debug script to check both knights pathfinding and interaction
"""

from src.clasher.engine import BattleEngine
from src.clasher.arena import Position

def debug_both_knights():
    """Debug both knights pathfinding and interaction"""
    print("=== Both Knights Pathfinding Debug ===")
    
    engine = BattleEngine()
    battle = engine.create_battle()
    
    # Deploy both knights
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Blue knight (player 0)
    result1 = battle.deploy_card(0, 'Knight', Position(9, 12))
    print(f"Blue knight deployment: {result1}")
    
    # Red knight (player 1) 
    result2 = battle.deploy_card(1, 'Knight', Position(9, 20))
    print(f"Red knight deployment: {result2}")
    
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
        print("ERROR: Knights not found!")
        return
    
    print(f"\nInitial State:")
    print(f"Blue Knight: ({blue_knight.position.x:.2f}, {blue_knight.position.y:.2f}) Player {blue_knight.player_id}")
    print(f"Red Knight:  ({red_knight.position.x:.2f}, {red_knight.position.y:.2f}) Player {red_knight.player_id}")
    
    distance = blue_knight.position.distance_to(red_knight.position)
    print(f"Distance between knights: {distance:.2f}")
    print(f"Knight sight range: {blue_knight.sight_range}")
    print(f"Can see each other: {distance <= blue_knight.sight_range}")
    
    # Check what each knight is targeting
    blue_target = blue_knight.get_nearest_target(battle.entities)
    red_target = red_knight.get_nearest_target(battle.entities)
    
    print(f"\nTargeting:")
    if blue_target:
        print(f"Blue knight targeting: {blue_target.card_stats.name if blue_target.card_stats else 'Unknown'} (Player {blue_target.player_id})")
        print(f"  Distance: {blue_knight.position.distance_to(blue_target.position):.2f}")
    else:
        print("Blue knight has no target")
        
    if red_target:
        print(f"Red knight targeting: {red_target.card_stats.name if red_target.card_stats else 'Unknown'} (Player {red_target.player_id})")
        print(f"  Distance: {red_knight.position.distance_to(red_target.position):.2f}")
    else:
        print("Red knight has no target")
    
    # Simulate movement
    print(f"\nSimulating movement (first 30 steps)...")
    for step in range(30):
        old_blue_pos = (blue_knight.position.x, blue_knight.position.y)
        old_red_pos = (red_knight.position.x, red_knight.position.y)
        
        battle.step(speed_factor=1.0)
        
        new_blue_pos = (blue_knight.position.x, blue_knight.position.y)
        new_red_pos = (red_knight.position.x, red_knight.position.y)
        
        distance = blue_knight.position.distance_to(red_knight.position)
        can_see = distance <= blue_knight.sight_range
        
        # Check if targets changed
        blue_target_now = blue_knight.get_nearest_target(battle.entities)
        red_target_now = red_knight.get_nearest_target(battle.entities)
        
        blue_target_name = blue_target_now.card_stats.name if blue_target_now and blue_target_now.card_stats else "None"
        red_target_name = red_target_now.card_stats.name if red_target_now and red_target_now.card_stats else "None"
        
        blue_moved = abs(old_blue_pos[0] - new_blue_pos[0]) > 0.01 or abs(old_blue_pos[1] - new_blue_pos[1]) > 0.01
        red_moved = abs(old_red_pos[0] - new_red_pos[0]) > 0.01 or abs(old_red_pos[1] - new_red_pos[1]) > 0.01
        
        print(f"  Step {step+1:2d}: Dist={distance:.2f} CanSee={can_see} "
              f"Blue->({new_blue_pos[0]:.1f},{new_blue_pos[1]:.1f}){' MOVED' if blue_moved else ''} "
              f"Red->({new_red_pos[0]:.1f},{new_red_pos[1]:.1f}){' MOVED' if red_moved else ''} "
              f"Targets: B->{blue_target_name} R->{red_target_name}")
        
        # Check if they can see each other now and switched targets
        if can_see and (blue_target_name == "Knight" or red_target_name == "Knight"):
            print(f"    >>> Knights can now see each other and switched targets!")
        
        # Stop if both stopped moving
        if not blue_moved and not red_moved:
            print(f"    >>> Both knights stopped moving")
            break

if __name__ == "__main__":
    debug_both_knights()