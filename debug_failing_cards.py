#!/usr/bin/env python3
"""
Debug which cards are failing and why
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader

def debug_failing_cards():
    """Debug why certain cards are failing to deploy"""
    
    print("=== Debugging Failing Cards ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 20.0
    
    # Cards that failed in the test
    failing_cards = ['Archer', 'Minions', 'SkeletonArmy', 'RoyalRecruits', 'GoblinGang', 'ThreeMusketeers', 'Wallbreakers']
    
    for card_name in failing_cards:
        print(f"\n--- Debugging {card_name} ---")
        
        # Check if card exists in data
        if card_name not in cards:
            print(f"❌ {card_name} not found in card database")
            continue
        
        card_stats = cards[card_name]
        print(f"✅ {card_name} found in database")
        print(f"   Mana cost: {card_stats.mana_cost}")
        print(f"   Card type: {card_stats.card_type}")
        print(f"   Summon count: {getattr(card_stats, 'summon_count', None)}")
        print(f"   Second count: {getattr(card_stats, 'summon_character_second_count', None)}")
        
        # Check if player can afford it
        if battle.players[0].elixir < card_stats.mana_cost:
            print(f"❌ Not enough elixir: {battle.players[0].elixir}/{card_stats.mana_cost}")
            continue
        
        # Check if card is in hand
        battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
        if card_name not in battle.players[0].hand:
            print(f"❌ {card_name} not in hand")
            continue
        
        print(f"✅ {card_name} in hand and affordable")
        
        # Check deployment position
        deploy_pos = Position(9, 8)  # Blue territory
        
        # Try to deploy
        original_entities = len(battle.entities)
        success = battle.deploy_card(0, card_name, deploy_pos)
        new_entities = len(battle.entities)
        
        if success:
            spawned_count = new_entities - original_entities
            print(f"✅ {card_name} deployed successfully: {spawned_count} entities spawned")
        else:
            print(f"❌ {card_name} deployment failed")
            
            # Additional debugging
            can_play = battle.players[0].can_play_card(card_name, card_stats)
            print(f"   Can play card: {can_play}")
            
            can_deploy_here = battle.arena.can_deploy_at(deploy_pos, 0, battle, False, None)
            print(f"   Can deploy at position: {can_deploy_here}")

if __name__ == "__main__":
    debug_failing_cards()