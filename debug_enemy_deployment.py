#!/usr/bin/env python3
"""
Debug enemy deployment issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Debug enemy deployment"""
    battle = BattleState()
    
    # Give both players enough elixir
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    print("=== Debugging Enemy Deployment ===")
    
    # Try to deploy enemy Knight
    target_pos = Position(5.0, 15.0)  # Red side
    print(f"Trying to deploy Knight at ({target_pos.x}, {target_pos.y}) for player 1")
    
    # Check if position is valid for player 1
    is_valid = battle.arena.can_deploy_at(target_pos, 1, battle)
    print(f"Position valid for player 1 deployment: {is_valid}")
    
    # Check player 1 state
    player1 = battle.players[1]
    print(f"Player 1 hand: {player1.hand}")
    print(f"Player 1 elixir: {player1.elixir}")
    
    # Try deployment
    success = battle.deploy_card(1, "Knight", target_pos)
    print(f"Knight deployment success: {success}")
    
    if not success:
        # Check each condition
        knight_card = battle.card_loader.get_card("Knight")
        if knight_card:
            can_play = player1.can_play_card("Knight", knight_card)
            in_hand = "Knight" in player1.hand
            enough_elixir = player1.elixir >= knight_card.mana_cost
            is_alive = player1.is_alive()
            print(f"  Knight card found: True")
            print(f"  In hand: {in_hand}")
            print(f"  Enough elixir: {enough_elixir} (elixir: {player1.elixir}, cost: {knight_card.mana_cost})")
            print(f"  Player alive: {is_alive}")
            print(f"  Can play card: {can_play}")
        else:
            print("  Knight card NOT FOUND")

if __name__ == "__main__":
    main()
