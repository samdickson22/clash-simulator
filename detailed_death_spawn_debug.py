#!/usr/bin/env python3
"""
Detailed debug of death spawn mechanics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Detailed death spawn debug"""
    battle = BattleState()
    
    # Modify player hands and give enough elixir
    battle.players[0].hand = ["Golem", "Archer", "Giant", "Minions"]
    battle.players[0].elixir = 10.0
    
    battle.players[1].hand = ["Knight", "Archer", "Giant", "Minions"]
    battle.players[1].elixir = 10.0
    
    # Deploy Golem
    golem_pos = Position(5.0, 10.0)
    success = battle.deploy_card(0, "Golem", golem_pos)
    print(f"Deployed Golem: {success}")
    
    # Deploy enemy targets
    target_pos = Position(5.0, 25.0)
    target_success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Deployed enemy Knight: {target_success}")
    
    # Find the Golem entity
    golem = None
    for entity in battle.entities.values():
        if entity.card_stats.name == "Golem" and entity.player_id == 0:
            golem = entity
            break
    
    if not golem:
        print("Golem entity not found")
        return
    
    print(f"Golem initial HP: {golem.hitpoints}")
    print(f"Golem death spawn: {golem.card_stats.death_spawn_character}")
    print(f"Golem death spawn count: {golem.card_stats.death_spawn_count}")
    
    # Check if death spawn card exists
    death_spawn_card = battle.card_loader.get_card(golem.card_stats.death_spawn_character)
    print(f"Death spawn card exists: {death_spawn_card is not None}")
    if death_spawn_card:
        print(f"Death spawn card HP: {death_spawn_card.hitpoints}")
        print(f"Death spawn card damage: {death_spawn_card.damage}")
    
    # Simulate battle with detailed logging
    for i in range(500):
        # Log before step
        if i % 50 == 0:
            print(f"\\n--- Tick {i} ---")
            print(f"Golem HP: {golem.hitpoints:.1f}")
            print(f"Golem alive: {golem.is_alive}")
            print(f"Total entities: {len(battle.entities)}")
        
        battle.step()
        
        # Check if Golem just died
        if not golem.is_alive and i > 0:
            print(f"\\n*** Golem died at tick {i}! ***")
            print(f"Final HP: {golem.hitpoints}")
            print(f"Entities after death: {len(battle.entities)}")
            
            # List all entities
            for entity in battle.entities.values():
                print(f"  Entity {entity.id}: {entity.card_stats.name} (player {entity.player_id}) at ({entity.position.x:.1f}, {entity.position.y:.1f})")
            
            break
    
    print("\\nBattle completed")

if __name__ == "__main__":
    main()
