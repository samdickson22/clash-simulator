#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_tower_air_targeting():
    """Test that towers can attack air units"""
    
    print("=== Tower Air Targeting Test ===")
    battle = BattleState()
    
    # Deploy BLUE Minions (player 0) that will move toward RED towers
    # This way Red towers can test their air targeting when Minions get in range
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Deploy Blue Minions in blue territory 
    # Player 0 can deploy from y=1 to y=14 (excluding river at y=15-16)
    # Red right tower at (14.5, 25.5). Deploy minions at (14, 14) in blue territory
    minions_pos = Position(14, 14)  # Blue territory, near river
    success = battle.deploy_card(0, 'Minions', minions_pos)  # Player 0 (blue)
    print(f"Blue Minions deployment at {minions_pos.x}, {minions_pos.y}: {'Success' if success else 'Failed'}")
    
    # Find Entity 7 specifically (the Minions)
    entity_7 = battle.entities.get(7)
    if entity_7:
        print(f"Entity 7 details:")
        print(f"  Type: {type(entity_7).__name__}")
        print(f"  Card name: {entity_7.card_stats.name if entity_7.card_stats else 'None'}")
        print(f"  Player: {entity_7.player_id}")
        print(f"  Position: ({entity_7.position.x}, {entity_7.position.y})")
        print(f"  Is air unit: {entity_7.is_air_unit}")
        print(f"  Is Troop: {isinstance(entity_7, Troop)}")
        print(f"  Is Building: {isinstance(entity_7, Building)}")
    
    # Find the minions and a red tower
    minions = None
    red_tower = None
    
    # Look for any entity with Minions name regardless of type
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Minions":
            minions = entity
            print(f"Found Minions entity: {type(entity).__name__}")
        if isinstance(entity, Building) and entity.player_id == 1:  # Red player
            if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Tower":
                red_tower = entity
    
    if not minions:
        print("❌ ERROR: Could not find deployed Minions")
        return
    
    if not red_tower:
        print("❌ ERROR: Could not find red tower")
        return
    
    print(f"Minions position: ({minions.position.x:.1f}, {minions.position.y:.1f})")
    print(f"Red tower position: ({red_tower.position.x:.1f}, {red_tower.position.y:.1f})")
    print(f"Distance: {minions.position.distance_to(red_tower.position):.1f}")
    print(f"Tower range: {red_tower.range}")
    print(f"Minions is_air_unit: {minions.is_air_unit}")
    print(f"Tower attacks_air: {getattr(red_tower.card_stats, 'attacks_air', 'Not set')}")
    print(f"Tower target_type: {getattr(red_tower.card_stats, 'target_type', 'Not set')}")
    
    # Test tower targeting logic
    target = red_tower.get_nearest_target(battle.entities)
    print(f"\nTower targeting test:")
    if target == minions:
        print(f"  ✅ SUCCESS: Tower correctly targets air Minions")
    else:
        print(f"  ❌ ERROR: Tower does not target air Minions")
        if target:
            print(f"    Tower targets: {target.card_stats.name if target.card_stats else 'Unknown'}")
        else:
            print(f"    Tower has no target")
    
    # Test attack capability
    can_attack = red_tower.can_attack_target(minions)
    print(f"Tower can_attack_target(minions): {can_attack}")
    
    # Run battle steps to see if Minions move closer and get targeted/attacked
    print(f"\n=== Running 200 battle steps to see movement ===")
    minions_initial_hp = minions.hitpoints
    
    for step in range(200):
        battle.step()
        if not minions.is_alive:
            print(f"Step {step+1}: Minions destroyed!")
            break
        
        # Check position and targeting every 20 steps
        if step % 20 == 0:
            distance = minions.position.distance_to(red_tower.position)
            target = red_tower.get_nearest_target(battle.entities)
            in_range = distance <= red_tower.range
            is_targeted = target == minions
            
            print(f"Step {step+1}: Pos({minions.position.x:.1f}, {minions.position.y:.1f}), Distance: {distance:.1f}, HP: {minions.hitpoints:.1f}, In range: {in_range}, Targeted: {is_targeted}")
    
    if minions.is_alive:
        damage_taken = minions_initial_hp - minions.hitpoints
        print(f"\nFinal: Minions took {damage_taken:.1f} damage over 200 steps")
        if damage_taken > 0:
            print("  ✅ SUCCESS: Tower successfully attacked air unit!")
        else:
            print("  ❌ Minions never got in range or tower didn't attack")
    else:
        print("  ✅ SUCCESS: Minions destroyed - tower can attack air units!")
    

if __name__ == "__main__":
    test_tower_air_targeting()