#!/usr/bin/env python3
"""
Test which spells are actually implemented
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader
from src.clasher.battle import BattleState
from src.clasher.arena import Position
from src.clasher.spells import SPELL_REGISTRY

def main():
    """Test spell implementation"""
    print("Testing Spell Implementation")
    print("=" * 50)
    
    # Load all cards
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    # Get spell cards
    spell_cards = [name for name, stats in cards.items() 
                   if stats.card_type == "Spell"]
    
    print(f"Total spells in game data: {len(spell_cards)}")
    print(f"Total spells implemented: {len(SPELL_REGISTRY)}")
    print(f"Implemented spells: {list(SPELL_REGISTRY.keys())}")
    
    print(f"\\n{'='*50}")
    print("SPELL IMPLEMENTATION CHECK")
    print(f"{'='*50}")
    
    implemented = []
    not_implemented = []
    
    for spell_name in spell_cards:
        if spell_name in SPELL_REGISTRY:
            implemented.append(spell_name)
            print(f"✅ {spell_name} - IMPLEMENTED")
        else:
            not_implemented.append(spell_name)
            print(f"❌ {spell_name} - NOT IMPLEMENTED")
    
    print(f"\\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Implemented: {len(implemented)}")
    print(f"Not implemented: {len(not_implemented)}")
    print(f"Implementation rate: {len(implemented)/len(spell_cards)*100:.1f}%")
    
    if not_implemented:
        print(f"\\nMissing spells:")
        for spell in not_implemented:
            print(f"  - {spell}")

if __name__ == "__main__":
    main()
