#!/usr/bin/env python3
"""
Test script for troop gimmicks - charging mechanics and death spawns
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def test_charging_mechanics():
    """Test Prince charging mechanics"""
    print("=== Testing Prince Charging Mechanics ===")
    battle = BattleState()
    
    # Modify player hand to include Prince
    battle.players[0].hand = ["Prince", "Archer", "Giant", "Minions"]
    
    # Deploy Prince in valid position
    prince_pos = Position(5.0, 10.0)  # Blue side, valid deployment zone
    success = battle.deploy_card(0, "Prince", prince_pos)
    print(f"Deployed Prince: {success}")
    
    if not success:
        print("Failed to deploy Prince")
        return
    
    # Find the Prince entity
    prince = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Prince" and entity.player_id == 0:
            prince = entity
            break
    
    if not prince:
        print("Prince entity not found")
        return
    
    print(f"Prince stats:")
    print(f"  Normal damage: {prince.damage}")
    print(f"  Special damage: {prince.card_stats.damage_special}")
    print(f"  Charge range: {prince.card_stats.charge_range}")
    print(f"  Normal speed: {prince.card_stats.speed}")
    print(f"  Is charging: {prince.is_charging}")
    print(f"  Has charged: {prince.has_charged}")
    
    # Deploy an enemy target for the Prince
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    target_pos = Position(5.0, 20.0)  # Red side
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Test charging behavior
    print("\\nSimulating battle steps to test charging...")
    for i in range(100):  # Run 100 ticks
        battle.step()
        
        # Check if Prince is charging
        if i % 20 == 0:  # Print every 20 ticks
            print(f"Tick {i}: Prince speed={prince.speed:.1f}, is_charging={prince.is_charging}, has_charged={prince.has_charged}")

def test_death_spawn_mechanics():
    """Test Golem death spawn mechanics"""
    print("\\n=== Testing Golem Death Spawn Mechanics ===")
    battle = BattleState()
    
    # Modify player hands to include Golem
    battle.players[0].hand = ["Golem", "Archer", "Giant", "Minions"]
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    
    # Deploy Golem
    golem_pos = Position(5.0, 10.0)  # Blue side
    success = battle.deploy_card(0, "Golem", golem_pos)
    print(f"Deployed Golem: {success}")
    
    if not success:
        print("Failed to deploy Golem")
        return
    
    # Find the Golem entity
    golem = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golem" and entity.player_id == 0:
            golem = entity
            break
    
    if not golem:
        print("Golem entity not found")
        return
    
    print(f"Golem stats:")
    print(f"  Death spawn character: {golem.card_stats.death_spawn_character}")
    print(f"  Death spawn count: {golem.card_stats.death_spawn_count}")
    print(f"  Kamikaze: {golem.card_stats.kamikaze}")
    
    # Deploy enemy targets
    target_pos1 = Position(5.0, 15.0)  # Red side
    target_pos2 = Position(5.0, 20.0)  # Red side
    target_success1 = battle.deploy_card(1, "Knight", target_pos1)
    target_success2 = battle.deploy_card(1, "Archer", target_pos2)
    print(f"Deployed enemy targets: Knight={target_success1}, Archer={target_success2}")
    
    # Simulate battle until golem dies
    initial_entity_count = len(battle.entities)
    print(f"Initial entities: {initial_entity_count}")
    
    for i in range(300):  # Run more ticks to let golem reach targets
        battle.step()
        
        if not golem.is_alive:
            print(f"Golem died at tick {i}")
            break
        
        if i % 50 == 0:
            print(f"Tick {i}: Golem HP={golem.hitpoints:.1f}")
    
    # Check if death spawns were created
    final_entity_count = len(battle.entities)
    print(f"Final entities: {final_entity_count}")
    
    death_spawns = []
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golemite":
            death_spawns.append(entity)
    
    print(f"Death spawns created: {len(death_spawns)}")
    for spawn in death_spawns:
        print(f"  Death spawn at ({spawn.position.x:.1f}, {spawn.position.y:.1f})")

def test_kamikaze_mechanics():
    """Test kamikaze troop mechanics"""
    print("\\n=== Testing Kamikaze Mechanics (SkeletonBalloon) ===")
    battle = BattleState()
    
    # Modify player hands to include SkeletonBalloon
    battle.players[0].hand = ["SkeletonBalloon", "Archer", "Giant", "Minions"]
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    
    # Deploy SkeletonBalloon
    skeleton_balloon_pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, "SkeletonBalloon", skeleton_balloon_pos)
    print(f"Deployed SkeletonBalloon: {success}")
    
    if not success:
        print("Failed to deploy SkeletonBalloon")
        return
    
    # Deploy enemy targets to kill the SkeletonBalloon
    target_pos = Position(5.0, 15.0)  # Red side
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Find the SkeletonBalloon entity
    skeleton_balloon = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "SkeletonBalloon" and entity.player_id == 0:
            skeleton_balloon = entity
            break
    
    if not skeleton_balloon:
        print("SkeletonBalloon entity not found")
        return
    
    print(f"SkeletonBalloon stats:")
    print(f"  Death spawn character: {skeleton_balloon.card_stats.death_spawn_character}")
    print(f"  Death spawn count: {skeleton_balloon.card_stats.death_spawn_count}")
    print(f"  Kamikaze: {skeleton_balloon.card_stats.kamikaze}")
    
    # Simulate battle until SkeletonBalloon dies
    for i in range(200):
        battle.step()
        
        if not skeleton_balloon.is_alive:
            print(f"SkeletonBalloon died at tick {i}")
            break
        
        if i % 50 == 0:
            print(f"Tick {i}: SkeletonBalloon HP={skeleton_balloon.hitpoints:.1f}")

def main():
    """Run all gimmick tests"""
    print("Testing Troop Gimmicks Implementation")
    print("=====================================")
    
    test_charging_mechanics()
    test_death_spawn_mechanics()
    test_kamikaze_mechanics()
    
    print("\\n=== All Tests Completed ===")

if __name__ == "__main__":
    main()
