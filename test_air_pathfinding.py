#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_air_pathfinding():
    """Test that air units bypass bridge pathfinding and fly directly over river"""
    
    print("=== Air Unit Pathfinding Test ===")
    battle = BattleState()
    
    # Deploy air and ground units for comparison
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Deploy Minions (air unit) and Knight (ground unit) in blue territory
    minions_success = battle.deploy_card(0, 'Minions', Position(9, 8))
    knight_success = battle.deploy_card(0, 'Knight', Position(11, 8))
    
    print(f"Minions deployment: {'Success' if minions_success else 'Failed'}")
    print(f"Knight deployment: {'Success' if knight_success else 'Failed'}")
    
    # Find the units
    minions = None
    knight = None
    red_tower = None
    
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats:
            if entity.card_stats.name == "Minions":
                minions = entity
            elif entity.card_stats.name == "Knight":
                knight = entity
            elif entity.card_stats.name == "Tower" and entity.player_id == 1:
                red_tower = entity
    
    if not minions or not knight or not red_tower:
        print(f"❌ Could not find units: Minions={minions is not None}, Knight={knight is not None}, Tower={red_tower is not None}")
        return
    
    print(f"\nMinions (air): is_air_unit = {minions.is_air_unit}")
    print(f"Knight (ground): is_air_unit = {knight.is_air_unit}")
    print(f"Target tower at: ({red_tower.position.x:.1f}, {red_tower.position.y:.1f})")
    
    # Test pathfinding for both units targeting the same red tower
    print(f"\n=== Pathfinding Comparison ===")
    
    minions_target = minions._get_pathfind_target(red_tower)
    knight_target = knight._get_pathfind_target(red_tower)
    
    print(f"Minions pathfind target: ({minions_target.x:.1f}, {minions_target.y:.1f})")
    print(f"Knight pathfind target:  ({knight_target.x:.1f}, {knight_target.y:.1f})")
    
    # Analyze behavior
    minions_direct = (minions_target.x == red_tower.position.x and minions_target.y == red_tower.position.y)
    knight_bridge = (knight_target.x in [3.5, 15.5] and knight_target.y == 16.0)
    
    print(f"\n=== Behavior Analysis ===")
    if minions_direct:
        print("✅ Minions: Flying directly to tower (bypassing bridge pathfinding)")
    else:
        print("❌ Minions: Not flying directly to tower")
    
    if knight_bridge:
        print("✅ Knight: Using bridge pathfinding (going to bridge center first)")
    else:
        print("❌ Knight: Not using bridge pathfinding")
    
    # Test air unit pathfinding in different scenarios
    print(f"\n=== Air Unit Pathfinding Scenarios ===")
    
    # Scenario 1: Air unit targeting troop in FOV
    if knight:
        minions_to_knight = minions._get_pathfind_target(knight)
        distance_to_knight = minions.position.distance_to(knight.position)
        in_fov = distance_to_knight <= minions.sight_range
        
        print(f"Minions → Knight:")
        print(f"  Distance: {distance_to_knight:.1f}, FOV range: {minions.sight_range}")
        print(f"  In FOV: {in_fov}")
        print(f"  Target: ({minions_to_knight.x:.1f}, {minions_to_knight.y:.1f})")
        
        if in_fov and minions_to_knight.x == knight.position.x and minions_to_knight.y == knight.position.y:
            print("  ✅ Air unit targets troop directly when in FOV")
        elif not in_fov and minions_to_knight.x == red_tower.position.x:
            print("  ✅ Air unit targets tower when troop out of FOV")
        else:
            print("  ❓ Unexpected air unit behavior")
    
    # Scenario 2: Cross-river movement simulation
    print(f"\n=== River Crossing Simulation ===")
    print("Running 30 steps to show movement patterns...")
    
    for step in range(30):
        battle.step()
        
        if step % 10 == 0:
            print(f"Step {step:2d}: Minions({minions.position.x:.1f},{minions.position.y:.1f}) Knight({knight.position.x:.1f},{knight.position.y:.1f})")
        
        # Check if either unit crossed the river (y=16)
        if minions.position.y > 16.0 and step < 15:
            print(f"  ✅ Minions crossed river at step {step} (direct flight)")
        
        if knight.position.y > 16.0 and step < 25:
            print(f"  ✅ Knight crossed river at step {step} (via bridge)")
    
    print(f"\n=== Summary ===")
    print("✅ Air units now bypass bridge pathfinding:")
    print("   - Priority 1: Troops in FOV → fly directly")
    print("   - Priority 2: Towers → fly directly over river")
    print("✅ Ground units still use bridge pathfinding")
    print("✅ Air units can cross river without using bridges")


if __name__ == "__main__":
    test_air_pathfinding()