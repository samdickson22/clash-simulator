#!/usr/bin/env python3
"""
Debug spell casting issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.battle import BattleState
from src.clasher.arena import Position
from src.clasher.spells import SPELL_REGISTRY

def main():
    """Debug spell casting"""
    print("Debugging Spell Casting")
    print("=" * 50)
    
    battle = BattleState()
    
    # Test a simple spell
    spell_name = "Fireball"
    spell = SPELL_REGISTRY.get(spell_name)
    
    if not spell:
        print(f"❌ Spell {spell_name} not found in registry")
        return
    
    print(f"✅ Found spell {spell_name}")
    print(f"   Mana cost: {spell.mana_cost}")
    print(f"   Radius: {spell.radius}")
    print(f"   Damage: {spell.damage}")
    
    # Set up player
    battle.players[0].elixir = 10.0
    battle.players[0].hand = [spell_name]
    
    # Test position
    test_pos = Position(9.0, 15.0)
    
    print(f"\\nTesting spell cast...")
    print(f"Player elixir: {battle.players[0].elixir}")
    print(f"Player hand: {battle.players[0].hand}")
    
    # Try to cast the spell directly
    result = spell.cast(battle, 0, test_pos)
    print(f"Spell cast result: {result}")
    
    # Check if any entities were created
    print(f"Entities after cast: {len(battle.entities)}")
    for entity_id, entity in battle.entities.items():
        print(f"  Entity {entity_id}: {entity.card_stats.name if entity.card_stats else 'Projectile'} (player {entity.player_id})")

if __name__ == "__main__":
    main()
