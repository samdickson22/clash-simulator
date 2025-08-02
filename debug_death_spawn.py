#!/usr/bin/env python3
"""
Debug death spawn mechanics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Debug death spawn"""
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
    
    # Simulate battle until golem dies
    for i in range(500):
        battle.step()
        
        if not golem.is_alive:
            print(f"Golem died at tick {i}")
            print(f"Golem final HP: {golem.hitpoints}")
            break
        
        if i % 100 == 0:
            print(f"Tick {i}: Golem HP={golem.hitpoints:.1f}")
    
    # Check all entities after death
    print(f"\\nEntities after Golem death:")
    for entity in battle.entities.values():
        print(f"  Entity {entity.id}: {entity.card_stats.name} (player {entity.player_id}) at ({entity.position.x:.1f}, {entity.position.y:.1f})")

if __name__ == "__main__":
    main()
