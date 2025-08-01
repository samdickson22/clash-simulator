#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building
from clasher.data import CardStats

def debug_waypoint_logic():
    """Debug the waypoint logic in advanced pathfinding"""
    
    print("=== DEBUGGING WAYPOINT LOGIC ===")
    
    battle = BattleState()
    
    # Simulate post-tower-destruction
    battle.players[1].left_tower_hp = 0
    
    card_stats = CardStats(
        name="Archer", 
        id=1,
        mana_cost=3,
        rarity="Common"
    )
    
    target = Building(
        id=999,
        position=Position(9.0, 25.0),
        player_id=1,
        card_stats=card_stats,
        hitpoints=1000,
        max_hitpoints=1000,
        damage=100,
        range=5.0,
        sight_range=7.0
    )
    
    # Test troop at problematic position
    troop = Troop(
        id=1,
        position=Position(9.0, 14.0),
        player_id=0,
        card_stats=card_stats,
        hitpoints=304,
        max_hitpoints=304,
        damage=90,
        range=5.0,
        sight_range=5.5,
        speed=60,
        is_air_unit=False
    )
    
    print(f"Troop position: ({troop.position.x}, {troop.position.y})")
    print(f"Target position: ({target.position.x}, {target.position.y})")
    
    # Check if first tower is destroyed (should be True)
    first_tower_destroyed = troop._is_first_tower_destroyed(battle)
    print(f"First tower destroyed: {first_tower_destroyed}")
    
    if first_tower_destroyed:
        print(f"Using advanced pathfinding...")
        
        # Manually walk through the advanced pathfinding logic
        left_bridge = Position(3.5, 16.0)
        right_bridge = Position(14.5, 16.0)
        
        dist_to_left = troop.position.distance_to(left_bridge)
        dist_to_right = troop.position.distance_to(right_bridge)
        
        print(f"Distance to left bridge: {dist_to_left:.2f}")
        print(f"Distance to right bridge: {dist_to_right:.2f}")
        
        if dist_to_left <= dist_to_right:
            chosen_bridge = left_bridge
            bridge_name = "left"
        else:
            chosen_bridge = right_bridge
            bridge_name = "right"
        
        print(f"Chosen bridge: {bridge_name} at ({chosen_bridge.x}, {chosen_bridge.y})")
        
        # Check bridge detection
        on_left_bridge = (abs(troop.position.x - 3.5) <= 1.5 and abs(troop.position.y - 16.0) <= 1.0)
        on_right_bridge = (abs(troop.position.x - 14.5) <= 1.5 and abs(troop.position.y - 16.0) <= 1.0)
        on_bridge = on_left_bridge or on_right_bridge
        
        print(f"On left bridge: {on_left_bridge}")
        print(f"On right bridge: {on_right_bridge}")
        print(f"On any bridge: {on_bridge}")
        
        if not on_bridge:
            print(f"Not on bridge - using waypoint logic...")
            
            # Calculate waypoint logic
            if chosen_bridge.x == 3.5:  # Left bridge
                bridge_approach = Position(3.5, 14.0) if troop.player_id == 0 else Position(3.5, 18.0)
            else:  # Right bridge
                bridge_approach = Position(14.5, 14.0) if troop.player_id == 0 else Position(14.5, 18.0)
            
            print(f"Bridge approach waypoint: ({bridge_approach.x}, {bridge_approach.y})")
            
            approach_distance = troop.position.distance_to(bridge_approach)
            bridge_distance = troop.position.distance_to(chosen_bridge)
            
            print(f"Distance to approach waypoint: {approach_distance:.2f}")
            print(f"Distance to bridge: {bridge_distance:.2f}")
            print(f"Waypoint threshold: {bridge_distance * 0.8:.2f}")
            
            if approach_distance < bridge_distance * 0.8:
                recommended_target = bridge_approach
                print(f"→ Recommending approach waypoint")
            else:
                recommended_target = chosen_bridge
                print(f"→ Recommending direct bridge")
            
            print(f"Recommended target: ({recommended_target.x}, {recommended_target.y})")
    else:
        print(f"Using basic pathfinding...")
    
    # Compare with actual pathfinding result
    actual_target = troop._get_pathfind_target(target, battle)
    print(f"\nActual pathfind target: ({actual_target.x}, {actual_target.y})")
    
    if first_tower_destroyed:
        if actual_target.x == recommended_target.x and actual_target.y == recommended_target.y:
            print(f"✅ Pathfinding matches expected logic")
        else:
            print(f"❌ Pathfinding doesn't match expected logic!")

if __name__ == "__main__":
    debug_waypoint_logic()