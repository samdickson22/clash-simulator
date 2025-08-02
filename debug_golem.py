#!/usr/bin/env python3
"""
Debug Golem deployment issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position
from src.clasher.data import CardDataLoader

def main():
    """Debug Golem deployment"""
    loader = CardDataLoader()
    loader.load_cards()
    
    golem_card = loader.get_card("Golem")
    if golem_card:
        print("Golem card found:")
        print(f"  Name: {golem_card.name}")
        print(f"  Type: {golem_card.card_type}")
        print(f"  Cost: {golem_card.mana_cost}")
        print(f"  Death spawn: {golem_card.death_spawn_character}")
        print(f"  Death spawn count: {golem_card.death_spawn_count}")
    else:
        print("Golem card NOT FOUND")
        return
    
    battle = BattleState()
    
    # Check player state
    player = battle.players[0]
    print(f"\\nPlayer hand: {player.hand}")
    print(f"Player elixir: {player.elixir}")
    
    # Try to deploy Golem
    golem_pos = Position(5.0, 10.0)
    print(f"\\nTrying to deploy Golem at ({golem_pos.x}, {golem_pos.y})")
    
    # Check if position is valid
    is_valid = battle.arena.can_deploy_at(golem_pos, 0, battle)
    print(f"Position valid for deployment: {is_valid}")
    
    # Check if player can play the card
    can_play = player.can_play_card("Golem", golem_card)
    print(f"Player can play Golem: {can_play}")
    
    if "Golem" in player.hand:
        print("Golem is in player hand")
    else:
        print("Golem is NOT in player hand")
        # Add it to hand for testing
        player.hand[0] = "Golem"
        print(f"Modified hand: {player.hand}")
    
    # Try deployment again
    success = battle.deploy_card(0, "Golem", golem_pos)
    print(f"Golem deployment success: {success}")
    
    if not success:
        print("Deployment failed - checking why...")
        # Check each condition
        in_hand = "Golem" in player.hand
        enough_elixir = player.elixir >= golem_card.mana_cost
        is_alive = player.is_alive()
        print(f"  In hand: {in_hand}")
        print(f"  Enough elixir: {enough_elixir} (elixir: {player.elixir}, cost: {golem_card.mana_cost})")
        print(f"  Player alive: {is_alive}")

if __name__ == "__main__":
    main()
