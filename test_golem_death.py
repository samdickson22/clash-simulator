#!/usr/bin/env python3
"""
Test Golem death spawn mechanics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Test Golem death"""
    battle = BattleState()
    
    # Give player 0 enough elixir to deploy Golem
    battle.players[0].elixir = 10.0
    battle.players[0].hand = ["Golem"]
    
    # Deploy Golem
    golem_pos = Position(5.0, 10.0)
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
    
    print(f"Golem HP: {golem.hitpoints}")
    print(f"Golem death spawn: {golem.card_stats.death_spawn_character}")
    print(f"Golem death spawn data exists: {golem.card_stats.death_spawn_character_data is not None}")
    
    if golem.card_stats.death_spawn_character_data:
        print("Death spawn data:")
        for key, value in golem.card_stats.death_spawn_character_data.items():
            print(f"  {key}: {value}")
    
    # Manually kill the Golem to test death spawn
    print("\\nManually killing Golem...")
    golem.hitpoints = 0
    golem.is_alive = False
    
    # Check if death spawn would be triggered
    print(f"Golem alive: {golem.is_alive}")
    print(f"Golem has death spawn: {golem.card_stats.death_spawn_character is not None}")
    
    # Simulate cleanup to see if death spawns are created
    initial_entities = len(battle.entities)
    battle._cleanup_dead_entities()
    final_entities = len(battle.entities)
    
    print(f"Entities before cleanup: {initial_entities}")
    print(f"Entities after cleanup: {final_entities}")
    
    # List all entities
    print("\\nAll entities:")
    for entity in battle.entities.values():
        print(f"  Entity {entity.id}: {entity.card_stats.name} (player {entity.player_id}) at ({entity.position.x:.1f}, {entity.position.y:.1f})")

if __name__ == "__main__":
    main()
