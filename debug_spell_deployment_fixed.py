#!/usr/bin/env python3
"""
Debug spell deployment issues with proper setup
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position

def main():
    """Debug spell deployment"""
    print("Debugging Spell Deployment (Fixed)")
    print("=" * 50)
    
    battle = BattleState()
    
    # Test spell deployment
    spell_name = "Fireball"
    test_pos = Position(9.0, 15.0)
    
    # Set up player properly
    battle.players[0].elixir = 10.0
    battle.players[0].hand = [spell_name]
    
    print(f"Initial state:")
    print(f"  Player 0 elixir: {battle.players[0].elixir}")
    print(f"  Player 0 hand: {battle.players[0].hand}")
    print(f"  Can deploy at {test_pos}: {battle.arena.can_deploy_at(test_pos, 0, battle, is_spell=True)}")
    
    # Check card stats
    card_stats = battle.card_loader.get_card(spell_name)
    print(f"  Card stats found: {card_stats is not None}")
    if card_stats:
        print(f"    Mana cost: {card_stats.mana_cost}")
        print(f"    Card type: {card_stats.card_type}")
    
    # Check player can play card
    can_play = battle.players[0].can_play_card(spell_name, card_stats)
    print(f"  Player can play card: {can_play}")
    
    # Try deployment
    print(f"\\nAttempting deployment...")
    result = battle.deploy_card(0, spell_name, test_pos)
    print(f"Deployment result: {result}")
    
    print(f"\\nAfter deployment:")
    print(f"  Player 0 elixir: {battle.players[0].elixir}")
    print(f"  Player 0 hand: {battle.players[0].hand}")
    print(f"  Entities: {len(battle.entities)}")
    
    # Check if spell was cast
    spell_entities = [e for e in battle.entities.values() 
                     if hasattr(e, 'card_stats') and e.card_stats and e.card_stats.name == spell_name]
    projectile_entities = [e for e in battle.entities.values() if hasattr(e, 'target_position')]
    
    print(f"  Spell entities: {len(spell_entities)}")
    print(f"  Projectile entities: {len(projectile_entities)}")
    
    if projectile_entities:
        proj = projectile_entities[0]
        print(f"  Projectile: from ({proj.position.x:.1f}, {proj.position.y:.1f}) to ({proj.target_position.x:.1f}, {proj.target_position.y:.1f})")

if __name__ == "__main__":
    main()
