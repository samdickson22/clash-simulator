#!/usr/bin/env python3
"""
Force Golem death to test death spawn mechanics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Force Golem death test"""
    battle = BattleState()
    
    # Give both players enough elixir and add Golem to hand
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    battle.players[0].hand = ["Golem", "Knight", "Archer", "Giant", "Minions"]
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    
    # Deploy Golem and enemy Knight very close to each other
    golem_pos = Position(9.0, 14.0)  # Blue side, near river
    knight_pos = Position(9.0, 17.0)  # Red side, near river (will move toward each other)
    
    # Deploy Golem
    golem_success = battle.deploy_card(0, "Golem", golem_pos)
    print(f"Deployed Golem: {golem_success}")
    
    # Deploy enemy Knight
    knight_success = battle.deploy_card(1, "Knight", knight_pos)
    print(f"Deployed enemy Knight: {knight_success}")
    
    if not golem_success or not knight_success:
        print("Failed to deploy units")
        return
    
    # Find entities
    golem = None
    knight = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golem" and entity.player_id == 0:
            golem = entity
        elif entity.card_stats.name == "Knight" and entity.player_id == 1:
            knight = entity
    
    print(f"\\nInitial HP - Golem: {golem.hitpoints}, Knight: {knight.hitpoints}")
    
    # Run battle until one dies
    for i in range(3000):
        battle.step()
        
        # Check if either unit died
        if not golem.is_alive:
            print(f"Golem died at tick {i}")
            print(f"Final HP - Golem: {golem.hitpoints}, Knight: {knight.hitpoints}")
            break
        
        if not knight.is_alive:
            print(f"Knight died at tick {i}")
            print(f"Final HP - Golem: {golem.hitpoints}, Knight: {knight.hitpoints}")
            # Continue to let Golem die from tower attacks or spawn another enemy
        
        if i % 100 == 0:
            print(f"Tick {i} - Golem: {golem.hitpoints:.1f}, Knight: {knight.hitpoints:.1f}")
    
    # Count death spawns
    death_spawns = []
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golemite":
            death_spawns.append(entity)
    
    print(f"\\nDeath spawns created: {len(death_spawns)}")
    for spawn in death_spawns:
        print(f"  Golemite at ({spawn.position.x:.1f}, {spawn.position.y:.1f})")

if __name__ == "__main__":
    main()
