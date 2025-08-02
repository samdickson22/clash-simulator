#!/usr/bin/env python3
"""
Check what cards are available in the card loader
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader

def main():
    """Check available cards"""
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    print(f"Total cards loaded: {len(cards)}")
    
    # Check specific cards
    test_cards = ["Prince", "Balloon", "SkeletonBalloon", "Giant", "Golem"]
    
    for card_name in test_cards:
        card = loader.get_card(card_name)
        if card:
            print(f"\\n{card_name}:")
            print(f"  Type: {card.card_type}")
            print(f"  Cost: {card.mana_cost}")
            print(f"  Charge range: {card.charge_range}")
            print(f"  Damage special: {card.damage_special}")
            print(f"  Death spawn: {card.death_spawn_character}")
            print(f"  Death spawn count: {card.death_spawn_count}")
            print(f"  Kamikaze: {card.kamikaze}")
        else:
            print(f"\\n{card_name}: NOT FOUND")

if __name__ == "__main__":
    main()
