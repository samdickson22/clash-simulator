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
    for card_name in cards:
        card = loader.get_card(card_name)
        if card:
            print(f"{card_name}:")

        else:
            print(f"{card_name}: NOT FOUND")

if __name__ == "__main__":
    main()
