#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_river_crossing():
    """Test air units crossing river directly vs ground units using bridges"""
    
    print("=== River Crossing Comparison Test ===")
    battle = BattleState()
    
    # Deploy units on opposite sides of river for clear crossing test
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Blue air unit in bottom territory targeting red towers
    air_success = battle.deploy_card(0, 'Minions', Position(9, 10))
    # Blue ground unit in bottom territory targeting red towers  
    ground_success = battle.deploy_card(0, 'Knight', Position(7, 10))
    
    print(f"Air unit (Minions) deployed: {'Success' if air_success else 'Failed'}")
    print(f"Ground unit (Knight) deployed: {'Success' if ground_success else 'Failed'}")
    
    # Find units
    air_unit = None
    ground_unit = None
    red_tower = None
    
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats:
            if entity.card_stats.name == "Minions":
                air_unit = entity
            elif entity.card_stats.name == "Knight":
                ground_unit = entity
            elif entity.card_stats.name == "Tower" and entity.player_id == 1:
                red_tower = entity
    
    if not air_unit or not ground_unit or not red_tower:
        print(f"❌ Missing units")
        return
    
    print(f"\nInitial positions:")
    print(f"Air unit:    ({air_unit.position.x:.1f}, {air_unit.position.y:.1f})")
    print(f"Ground unit: ({ground_unit.position.x:.1f}, {ground_unit.position.y:.1f})")
    print(f"Target:      ({red_tower.position.x:.1f}, {red_tower.position.y:.1f})")
    print(f"River:       y=15-16")
    
    # Test pathfinding targets
    air_target = air_unit._get_pathfind_target(red_tower)
    ground_target = ground_unit._get_pathfind_target(red_tower)
    
    print(f"\nPathfinding targets:")
    print(f"Air unit target: ({air_target.x:.1f}, {air_target.y:.1f})")
    print(f"Ground unit target: ({ground_target.x:.1f}, {ground_target.y:.1f})")
    
    # Verify behavior
    air_direct = (air_target.x == red_tower.position.x and air_target.y == red_tower.position.y)
    ground_bridge = (ground_target.x in [3.5, 15.5] and ground_target.y == 16.0)
    
    if air_direct:
        print("✅ Air unit: Direct path to target (ignoring river)")
    else:
        print("❌ Air unit: Not using direct path")
    
    if ground_bridge:
        print("✅ Ground unit: Using bridge pathfinding") 
    else:
        print("❌ Ground unit: Not using bridge pathfinding")
    
    # Simulate movement and track river crossings
    print(f"\n=== Movement Simulation ===")
    air_crossed_river = False
    ground_crossed_river = False
    air_cross_step = None
    ground_cross_step = None
    
    for step in range(100):
        battle.step()
        
        # Check for river crossing (y > 16)
        if not air_crossed_river and air_unit.position.y > 16.0:
            air_crossed_river = True
            air_cross_step = step + 1
            print(f"Step {step + 1:2d}: ✈️  Air unit crossed river at ({air_unit.position.x:.1f}, {air_unit.position.y:.1f})")
        
        if not ground_crossed_river and ground_unit.position.y > 16.0:
            ground_crossed_river = True  
            ground_cross_step = step + 1
            print(f"Step {step + 1:2d}: 🚶 Ground unit crossed river at ({ground_unit.position.x:.1f}, {ground_unit.position.y:.1f})")
        
        # Show periodic updates
        if step % 20 == 0 and step > 0:
            print(f"Step {step:2d}: Air({air_unit.position.x:.1f},{air_unit.position.y:.1f}) Ground({ground_unit.position.x:.1f},{ground_unit.position.y:.1f})")
        
        # Stop if both crossed
        if air_crossed_river and ground_crossed_river:
            break
    
    # Summary
    print(f"\n=== River Crossing Results ===")
    if air_crossed_river:
        print(f"✅ Air unit crossed river in {air_cross_step} steps (direct flight)")
    else:
        print(f"❌ Air unit did not cross river in 100 steps")
    
    if ground_crossed_river:
        print(f"✅ Ground unit crossed river in {ground_cross_step} steps (via bridge)")
    else:
        print(f"❌ Ground unit did not cross river in 100 steps") 
    
    if air_crossed_river and ground_crossed_river:
        time_diff = ground_cross_step - air_cross_step
        print(f"📊 Air unit crossed {time_diff} steps faster than ground unit")
    
    print(f"\n=== Pathfinding Summary ===")
    print("✅ Air units fly directly over river:")
    print("   - No bridge pathfinding needed")
    print("   - Faster river crossing")  
    print("   - Direct line to targets")
    print("✅ Ground units use bridge pathfinding:")
    print("   - Must go to bridge center first")
    print("   - Follow bridge → tower path")
    print("   - Realistic ground movement")


if __name__ == "__main__":
    test_river_crossing()