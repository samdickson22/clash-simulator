#!/usr/bin/env python3
"""
Focused test for building cards
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader
from src.clasher.battle import BattleState
from src.clasher.arena import Position

def test_single_building(building_name):
    """Test a single building"""
    print(f"\\n{'='*50}")
    print(f"Testing: {building_name}")
    print(f"{'='*50}")
    
    try:
        battle = BattleState()
        battle.players[0].hand = [building_name]
        battle.players[0].elixir = 10.0
        
        # Deploy building
        pos = Position(5.0, 10.0)
        success = battle.deploy_card(0, building_name, pos)
        
        print(f"Deploy result: {success}")
        
        if not success:
            print(f"❌ FAILED: Could not deploy {building_name}")
            return False
        
        # Find the entity
        entity = None
        for ent in battle.entities.values():
            if ent.card_stats.name == building_name and ent.player_id == 0:
                entity = ent
                break
        
        if not entity:
            print(f"❌ FAILED: Entity not found")
            return False
        
        print(f"✅ Building created successfully!")
        print(f"   - HP: {entity.hitpoints}")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test all building cards"""
    print("Focused Building Test")
    print("=" * 50)
    
    # Load all cards
    loader = CardDataLoader()
    cards = loader.load_cards()
    
    # Get building cards
    building_cards = [name for name, stats in cards.items() 
                     if stats.card_type == "Building"]
    
    print(f"Found {len(building_cards)} building cards")
    
    # Test each building
    passed = 0
    failed = 0
    
    for building_name in building_cards:
        if test_single_building(building_name):
            passed += 1
            print(f"✅ {building_name} TEST PASSED")
        else:
            failed += 1
            print(f"❌ {building_name} TEST FAILED")
        
        # Small delay
        import time
        time.sleep(0.05)
    
    print(f"\\n{'='*50}")
    print("BUILDING TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Total buildings: {len(building_cards)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {passed/len(building_cards)*100:.1f}%")

if __name__ == "__main__":
    main()
