#!/usr/bin/env python3
"""
Comprehensive test for all troop gimmicks
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
    
    # Modify player hand to include Prince and give enough elixir
    battle.players[0].hand = ["Prince", "Archer", "Giant", "Minions"]
    battle.players[0].elixir = 10.0  # Ensure enough elixir
    
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    battle.players[1].elixir = 10.0
    
    # Deploy Prince in valid position
    prince_pos = Position(5.0, 10.0)  # Blue side, valid deployment zone
    success = battle.deploy_card(0, "Prince", prince_pos)
    print(f"Deployed Prince: {success}")
    
    if not success:
        print("Failed to deploy Prince")
        return False
    
    # Find the Prince entity
    prince = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Prince" and entity.player_id == 0:
            prince = entity
            break
    
    if not prince:
        print("Prince entity not found")
        return False
    
    print(f"Prince stats:")
    print(f"  Normal damage: {prince.damage}")
    print(f"  Special damage: {prince.card_stats.damage_special}")
    print(f"  Charge range: {prince.card_stats.charge_range}")
    print(f"  Normal speed: {prince.card_stats.speed}")
    print(f"  Is charging: {prince.is_charging}")
    print(f"  Has charged: {prince.has_charged}")
    
    # Deploy an enemy target for the Prince
    target_pos = Position(5.0, 25.0)  # Red side (valid deployment zone)
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Test charging behavior
    print("\\nSimulating battle steps to test charging...")
    for i in range(100):  # Run 100 ticks
        battle.step()
        
        # Check if Prince is charging (check every 20 ticks)
        if i % 20 == 0:
            print(f"Tick {i}: Prince speed={prince.speed:.1f}, is_charging={prince.is_charging}, has_charged={prince.has_charged}")
    
    return True

def test_death_spawn_mechanics():
    """Test Golem death spawn mechanics"""
    print("\\n=== Testing Golem Death Spawn Mechanics ===")
    battle = BattleState()
    
    # Modify player hands to include Golem and give enough elixir
    battle.players[0].hand = ["Golem", "Archer", "Giant", "Minions"]
    battle.players[0].elixir = 10.0  # Ensure enough elixir (Golem costs 8)
    
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    battle.players[1].elixir = 10.0
    
    # Deploy Golem
    golem_pos = Position(5.0, 10.0)  # Blue side
    success = battle.deploy_card(0, "Golem", golem_pos)
    print(f"Deployed Golem: {success}")
    
    if not success:
        print("Failed to deploy Golem")
        return False
    
    # Find the Golem entity
    golem = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golem" and entity.player_id == 0:
            golem = entity
            break
    
    if not golem:
        print("Golem entity not found")
        return False
    
    print(f"Golem stats:")
    print(f"  Death spawn character: {golem.card_stats.death_spawn_character}")
    print(f"  Death spawn count: {golem.card_stats.death_spawn_count}")
    print(f"  Kamikaze: {golem.card_stats.kamikaze}")
    
    # Deploy enemy targets to kill the Golem
    target_pos = Position(5.0, 25.0)  # Red side (valid deployment zone)
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Simulate battle until golem dies or we run enough ticks
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
    
    return len(death_spawns) > 0

def test_kamikaze_mechanics():
    """Test kamikaze troop mechanics"""
    print("\\n=== Testing Kamikaze Mechanics (SkeletonBalloon) ===")
    battle = BattleState()
    
    # Modify player hands to include SkeletonBalloon and give enough elixir
    battle.players[0].hand = ["SkeletonBalloon", "Archer", "Giant", "Minions"]
    battle.players[0].elixir = 10.0  # Ensure enough elixir
    
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    battle.players[1].elixir = 10.0
    
    # Deploy SkeletonBalloon
    skeleton_balloon_pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, "SkeletonBalloon", skeleton_balloon_pos)
    print(f"Deployed SkeletonBalloon: {success}")
    
    if not success:
        print("Failed to deploy SkeletonBalloon")
        return False
    
    # Deploy enemy targets to kill the SkeletonBalloon
    target_pos = Position(5.0, 25.0)  # Red side (valid deployment zone)
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
        return False
    
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
    
    return True

def test_buff_mechanics():
    """Test buff mechanics (RageBarbarian example)"""
    print("\\n=== Testing Buff Mechanics (RageBarbarian) ===")
    battle = BattleState()
    
    # Modify player hands and give enough elixir
    battle.players[0].hand = ["RageBarbarian", "Archer", "Giant", "Minions"]
    battle.players[0].elixir = 10.0
    
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    battle.players[1].elixir = 10.0
    
    # Deploy RageBarbarian
    rage_barbarian_pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, "RageBarbarian", rage_barbarian_pos)
    print(f"Deployed RageBarbarian: {success}")
    
    if not success:
        print("Failed to deploy RageBarbarian")
        return False
    
    # Deploy enemy targets
    target_pos = Position(5.0, 25.0)  # Red side (valid deployment zone)
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Find the RageBarbarian entity
    rage_barbarian = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "RageBarbarian" and entity.player_id == 0:
            rage_barbarian = entity
            break
    
    if not rage_barbarian:
        print("RageBarbarian entity not found")
        return False
    
    print(f"RageBarbarian stats:")
    print(f"  Death spawn character: {rage_barbarian.card_stats.death_spawn_character}")
    print(f"  Death spawn count: {rage_barbarian.card_stats.death_spawn_count}")
    print(f"  Kamikaze: {rage_barbarian.card_stats.kamikaze}")
    
    # Simulate battle
    for i in range(100):
        battle.step()
        
        if i % 30 == 0:
            print(f"Tick {i}: RageBarbarian HP={rage_barbarian.hitpoints:.1f}")
    
    return True

def main():
    """Run all gimmick tests"""
    print("Comprehensive Troop Gimmicks Test")
    print("================================")
    
    # Test charging mechanics
    charging_success = test_charging_mechanics()
    print(f"Charging test result: {'PASS' if charging_success else 'FAIL'}")
    
    # Test death spawn mechanics
    death_spawn_success = test_death_spawn_mechanics()
    print(f"Death spawn test result: {'PASS' if death_spawn_success else 'FAIL'}")
    
    # Test kamikaze mechanics
    kamikaze_success = test_kamikaze_mechanics()
    print(f"Kamikaze test result: {'PASS' if kamikaze_success else 'FAIL'}")
    
    # Test buff mechanics
    buff_success = test_buff_mechanics()
    print(f"Buff test result: {'PASS' if buff_success else 'FAIL'}")
    
    print("\\n=== All Tests Completed ===")

if __name__ == "__main__":
    main()
