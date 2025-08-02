#!/usr/bin/env python3
"""
Focused test for spell cards
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader
from src.clasher.battle import BattleState
from src.clasher.arena import Position

def test_single_spell(spell_name):
    """Test a single spell"""
    print(f"\\n{'='*50}")
    print(f"Testing: {spell_name}")
    print(f"{'='*50}")
    
    try:
        battle = BattleState()
        battle.players[0].hand = [spell_name]
        battle.players[0].elixir = 10.0
        
        # Deploy spell
        pos = Position(9.0, 15.0)  # Center of arena
        success = battle.deploy_card(0, spell_name, pos)
        
        print(f"Deploy result: {success}")
        
        if not success:
            print(f"❌ FAILED: Could not deploy spell {spell_name}")
            return False
        
        # Find the entity
        entity = None
        for ent in battle.entities.values():
            if ent.card_stats.name == spell_name and ent.player_id == 0:
                entity = ent
                break
        
        if not entity:
            print(f"❌ FAILED: Spell entity not found")
            return False
        
        print(f"✅ Spell created successfully!")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test all spell cards"""
    print("Focused Spell Test")
    print("=" * 50)
    
    # Load all cards
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    # Get spell cards
    spell_cards = [name for name, stats in cards.items() 
                   if stats.card_type == "Spell"]
    
    print(f"Found {len(spell_cards)} spell cards")
    
    # Test each spell
    passed = 0
    failed = 0
    
    for spell_name in spell_cards:
        if test_single_spell(spell_name):
            passed += 1
            print(f"✅ {spell_name} TEST PASSED")
        else:
            failed += 1
            print(f"❌ {spell_name} TEST FAILED")
        
        # Small delay
        import time
        time.sleep(0.05)
    
    print(f"\\n{'='*50}")
    print("SPELL TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Total spells: {len(spell_cards)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {passed/len(spell_cards)*100:.1f}%")

if __name__ == "__main__":
    main()
