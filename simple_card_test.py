#!/usr/bin/env python3
"""
Simple test for every card focusing on core functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.data import CardDataLoader
from src.clasher.battle import BattleState
from src.clasher.arena import Position
import time

def load_all_cards():
    """Load all cards from gamedata.json"""
    loader = CardDataLoader()
    cards = loader.load_cards()
    return cards

def test_card_basic_functionality(card_name, card_stats):
    """Test basic card functionality"""
    print(f"\\n{'='*50}")
    print(f"Testing: {card_name} ({card_stats.card_type})")
    print(f"{'='*50}")
    
    try:
        battle = BattleState()
        
        # Add card to player's hand
        battle.players[0].hand = [card_name]
        battle.players[0].elixir = 10.0
        
        # Try to deploy the card
        pos = Position(5.0, 10.0)
        success = battle.deploy_card(0, card_name, pos)
        
        if not success:
            print(f"❌ FAILED: Could not deploy {card_name}")
            return False
        
        print(f"✅ Deployed successfully")
        
        # Find the entity
        entity = None
        for ent in battle.entities.values():
            if ent.card_stats.name == card_name and ent.player_id == 0:
                entity = ent
                break
        
        if not entity:
            print(f"❌ FAILED: Entity not found")
            return False
        
        print(f"✅ Entity created")
        print(f"   - HP: {entity.hitpoints}")
        print(f"   - Damage: {entity.damage}")
        print(f"   - Speed: {entity.speed}")
        print(f"   - Range: {entity.range}")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        # Test if entity stays alive
        if entity.is_alive:
            print(f"✅ Entity stays alive")
        else:
            print(f"❌ Entity died unexpectedly")
            return False
        
        # Test special abilities (if they exist)
        special_abilities = []
        
        # Charging
        if hasattr(entity, 'is_charging'):
            special_abilities.append(f"charging: {entity.is_charging}")
        
        # Death spawn
        if card_stats.death_spawn_character:
            special_abilities.append(f"death_spawn: {card_stats.death_spawn_character}")
        
        # Kamikaze
        if card_stats.kamikaze:
            special_abilities.append("kamikaze")
        
        # Summon
        if card_stats.summon_count:
            special_abilities.append(f"summon: {card_stats.summon_count}")
        
        if special_abilities:
            print(f"✅ Special abilities: {', '.join(special_abilities)}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_spell_basic(card_name, card_stats):
    """Test basic spell functionality"""
    print(f"\\n{'='*50}")
    print(f"Testing Spell: {card_name}")
    print(f"{'='*50}")
    
    try:
        battle = BattleState()
        battle.players[0].elixir = 10.0
        
        # Try to deploy spell
        pos = Position(9.0, 15.0)
        success = battle.deploy_card(0, card_name, pos)
        
        if not success:
            print(f"❌ FAILED: Could not deploy spell {card_name}")
            return False
        
        print(f"✅ Spell deployed successfully")
        
        # Find the entity
        entity = None
        for ent in battle.entities.values():
            if ent.card_stats.name == card_name and ent.player_id == 0:
                entity = ent
                break
        
        if not entity:
            print(f"❌ FAILED: Spell entity not found")
            return False
        
        print(f"✅ Spell entity created")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_building_basic(card_name, card_stats):
    """Test basic building functionality"""
    print(f"\\n{'='*50}")
    print(f"Testing Building: {card_name}")
    print(f"{'='*50}")
    
    try:
        battle = BattleState()
        battle.players[0].elixir = 10.0
        
        # Deploy building
        pos = Position(5.0, 10.0)
        success = battle.deploy_card(0, card_name, pos)
        
        if not success:
            print(f"❌ FAILED: Could not deploy building {card_name}")
            return False
        
        print(f"✅ Building deployed successfully")
        
        # Find the entity
        entity = None
        for ent in battle.entities.values():
            if ent.card_stats.name == card_name and ent.player_id == 0:
                entity = ent
                break
        
        if not entity:
            print(f"❌ FAILED: Building entity not found")
            return False
        
        print(f"✅ Building entity created")
        print(f"   - HP: {entity.hitpoints}")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Main function to test every card"""
    print("Simple Card Test - Every Single Card")
    print("=" * 50)
    
    # Load all cards
    cards = load_all_cards()
    print(f"Loaded {len(cards)} cards")
    
    # Track results
    results = {}
    passed = 0
    failed = 0
    
    # Test each card
    start_time = time.time()
    
    for card_name, card_stats in cards.items():
        card_type = card_stats.card_type
        
        # Skip king towers
        if "King" in card_name:
            print(f"\\n{'='*50}")
            print(f"SKIPPING: {card_name} (King Tower)")
            print(f"{'='*50}")
            results[card_name] = {"status": "SKIPPED", "type": "King Tower"}
            continue
        
        test_result = False
        
        if card_type == "Troop":
            test_result = test_card_basic_functionality(card_name, card_stats)
        elif card_type == "Spell":
            test_result = test_spell_basic(card_name, card_stats)
        elif card_type == "Building":
            test_result = test_building_basic(card_name, card_stats)
        else:
            print(f"\\n{'='*50}")
            print(f"Testing: {card_name} ({card_type})")
            print(f"{'='*50}")
            print(f"❌ UNKNOWN CARD TYPE: {card_type}")
            results[card_name] = {"status": "FAILED", "type": "Unknown"}
            failed += 1
            continue
        
        if test_result:
            results[card_name] = {"status": "PASSED", "type": card_type}
            passed += 1
            print(f"✅ {card_name} TEST PASSED")
        else:
            results[card_name] = {"status": "FAILED", "type": card_type}
            failed += 1
            print(f"❌ {card_name} TEST FAILED")
        
        # Small delay between tests
        time.sleep(0.05)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Print summary
    print(f"\\n{'='*50}")
    print("FINAL SUMMARY")
    print(f"{'='*50}")
    print(f"Total cards tested: {len(cards)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {len(results) - passed - failed}")
    print(f"Success rate: {passed/len(cards)*100:.1f}%")
    print(f"Total time: {total_time:.1f} seconds")
    
    # Print failed cards
    if failed > 0:
        print(f"\\nFAILED CARDS:")
        print(f"{'-'*30}")
        for card_name, result in results.items():
            if result["status"] == "FAILED":
                print(f"- {card_name} ({result['type']})")
    
    # Print cards with special abilities
    print(f"\\nCARDS WITH SPECIAL ABILITIES:")
    print(f"{'-'*30}")
    special_cards = []
    for card_name, result in results.items():
        if result["status"] == "PASSED":
            card_stats = cards[card_name]
            abilities = []
            
            if card_stats.charge_range:
                abilities.append(f"charge:{card_stats.charge_range}")
            if card_stats.death_spawn_character:
                abilities.append(f"death:{card_stats.death_spawn_character}")
            if card_stats.kamikaze:
                abilities.append("kamikaze")
            if card_stats.summon_count:
                abilities.append(f"summon:{card_stats.summon_count}")
            
            if abilities:
                special_cards.append(f"- {card_name}: {', '.join(abilities)}")
    
    if special_cards:
        for card in special_cards:
            print(card)
    else:
        print("No special abilities found")

if __name__ == "__main__":
    main()
