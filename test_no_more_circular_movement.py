#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building
from clasher.data import CardStats

def test_no_more_circular_movement():
    """Test that troops no longer move in circles around the bridge center"""
    
    print("=== TESTING NO MORE CIRCULAR MOVEMENT ===")
    
    battle = BattleState()
    
    # Simulate post-tower-destruction scenario
    battle.players[1].left_tower_hp = 0  # First tower destroyed
    
    card_stats = CardStats(
        name="Archer",
        id=1,
        mana_cost=3,
        rarity="Common",
        hitpoints=304,
        damage=90,
        speed=60,
        range=5.0,
        sight_range=5.5
    )
    
    # Create a target on the opposite side
    target = Building(
        id=999,
        position=Position(9.0, 25.0),  # Red side
        player_id=1,
        card_stats=card_stats,
        hitpoints=1000,
        max_hitpoints=1000,
        damage=100,
        range=5.0,
        sight_range=7.0
    )
    
    battle.entities[999] = target
    
    # Test a troop in the middle area where circular movement was happening
    problem_position = Position(9.0, 14.0)  # Near where troops were circling
    
    print(f"Testing troop at problematic position: ({problem_position.x}, {problem_position.y})")
    
    troop = Troop(
        id=1,
        position=problem_position,
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
    
    # Simulate pathfinding for several steps
    print(f"\nSimulating pathfinding movement:")
    
    for step in range(8):
        # Get pathfinding target
        pathfind_target = troop._get_pathfind_target(target, battle)
        
        print(f"Step {step + 1}:")
        print(f"  Troop at: ({troop.position.x:.1f}, {troop.position.y:.1f})")
        print(f"  Target: ({pathfind_target.x:.1f}, {pathfind_target.y:.1f})")
        
        # Check if target is walkable
        target_walkable = battle.arena.is_walkable(pathfind_target)
        print(f"  Target walkable: {target_walkable}")
        
        if not target_walkable:
            print(f"  ❌ PROBLEM: Targeting unwalkable position!")
            break
        
        # Simulate movement towards target
        dx = pathfind_target.x - troop.position.x
        dy = pathfind_target.y - troop.position.y
        distance = (dx * dx + dy * dy) ** 0.5
        
        if distance > 0:
            # Move 1 tile towards target
            move_distance = 1.0
            if move_distance > distance:
                move_distance = distance
            
            move_x = (dx / distance) * move_distance
            move_y = (dy / distance) * move_distance
            
            new_pos = Position(troop.position.x + move_x, troop.position.y + move_y)
            
            if battle.arena.is_walkable(new_pos):
                troop.position = new_pos
                print(f"  ✅ Moved to: ({troop.position.x:.1f}, {troop.position.y:.1f})")
            else:
                print(f"  ❌ Movement blocked, staying at: ({troop.position.x:.1f}, {troop.position.y:.1f})")
        
        # Check if we're making progress towards crossing the river
        if step == 0:
            initial_y = troop.position.y
        
        if step > 0:
            y_progress = troop.position.y - initial_y
            if y_progress > 0.5:
                print(f"  ✅ Making forward progress towards river!")
            elif abs(y_progress) < 0.1:
                print(f"  ⚠️  Not making vertical progress (might be moving sideways to bridge)")
            else:
                print(f"  ❌ Moving backwards or sideways only!")
        
        print()
        
        # Stop if we've reached a bridge or crossed the river
        if troop.position.y >= 15.0:
            print(f"✅ SUCCESS: Troop reached river area!")
            break
    
    # Final analysis
    final_y = troop.position.y
    total_progress = final_y - initial_y
    
    print(f"=== FINAL ANALYSIS ===")
    print(f"Initial Y position: {initial_y:.1f}")
    print(f"Final Y position: {final_y:.1f}")
    print(f"Total forward progress: {total_progress:.1f} tiles")
    
    if total_progress >= 1.0:
        print(f"✅ SUCCESS: Troop made significant forward progress!")
        print(f"✅ NO MORE CIRCULAR MOVEMENT - troops can cross the river!")
    else:
        print(f"❌ PROBLEM: Troop did not make forward progress")

if __name__ == "__main__":
    test_no_more_circular_movement()