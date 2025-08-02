#!/usr/bin/env python3
"""
Test every single card in the game individually
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

def test_card_deployment_and_basic_functionality(card_name, card_stats):
    """Test if a card can be deployed and functions correctly"""
    print(f"\\n{'='*60}")
    print(f"Testing: {card_name} ({card_stats.card_type})")
    print(f"{'='*60}")
    
    try:
        battle = BattleState()
        
        # Add card to player's hand
        battle.players[0].hand = [card_name]
        battle.players[0].elixir = 10.0  # Ensure enough elixir
        
        # Try to deploy the card
        pos = Position(5.0, 10.0)  # Valid deployment position
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
            print(f"❌ FAILED: Entity not found after deployment")
            return False
        
        print(f"✅ Entity created: ID {entity.id}")
        print(f"   - HP: {entity.hitpoints}")
        print(f"   - Damage: {entity.damage}")
        print(f"   - Speed: {entity.speed}")
        print(f"   - Range: {entity.range}")
        print(f"   - Position: ({entity.position.x:.1f}, {entity.position.y:.1f})")
        
        # Test basic movement
        initial_pos = (entity.position.x, entity.position.y)
        for i in range(10):
            battle.step()
        
        final_pos = (entity.position.x, entity.position.y)
        
        if initial_pos != final_pos:
            print(f"✅ Movement working: {initial_pos} -> {final_pos}")
        else:
            print(f"ℹ️  No movement detected (may be expected)")
        
        # Test if entity stays alive
        if entity.is_alive:
            print(f"✅ Entity stays alive")
        else:
            print(f"❌ Entity died unexpectedly")
            return False
        
        # Test targeting if it's a troop
        if card_stats.card_type == "Troop":
            # Deploy enemy target
            battle.players[1].hand = ["Knight"]
            battle.players[1].elixir = 10.0
            target_pos = Position(5.0, 25.0)
            battle.deploy_card(1, "Knight", target_pos)
            
            # Run a few ticks to see targeting
            for i in range(30):
                battle.step()
                if entity.target:
                    print(f"✅ Targeting working: targeting {entity.target.card_stats.name}")
                    break
            else:
                print(f"ℹ️  No target acquired (may be expected)")
        
        # Test special abilities
        special_abilities = []
        
        # Charging
        if hasattr(entity, 'is_charging') and entity.is_charging:
            special_abilities.append("charging")
        
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
        import traceback
        traceback.print_exc()
        return False

def test_spell_card(card_name, card_stats):
    """Test spell cards specifically"""
    print(f"\\n{'='*60}")
    print(f"Testing Spell: {card_name}")
    print(f"{'='*60}")
    
    try:
        battle = BattleState()
        battle.players[0].elixir = 10.0
        
        # Deploy spell
        pos = Position(9.0, 15.0)  # Center of arena
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
        
        # Run a few ticks
        for i in range(20):
            battle.step()
            if not entity.is_alive:
                print(f"✅ Spell completed/ended at tick {i}")
                break
        else:
            print(f"ℹ️  Spell still active after 20 ticks")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_building_card(card_name, card_stats):
    """Test building cards specifically"""
    print(f"\\n{'='*60}")
    print(f"Testing Building: {card_name}")
    print(f"{'='*60}")
    
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
        
        # Test if building stays alive and doesn't move
        initial_pos = (entity.position.x, entity.position.y)
        
        for i in range(30):
            battle.step()
        
        final_pos = (entity.position.x, entity.position.y)
        
        if initial_pos == final_pos:
            print(f"✅ Building doesn't move (as expected)")
        else:
            print(f"❌ Building moved unexpectedly")
        
        if entity.is_alive:
            print(f"✅ Building stays alive")
        else:
            print(f"❌ Building died unexpectedly")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Main function to test every card"""
    print("Testing Every Single Card in Clash Royale")
    print("=" * 60)
    
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
            print(f"\\n{'='*60}")
            print(f"SKIPPING: {card_name} (King Tower)")
            print(f"{'='*60}")
            results[card_name] = {"status": "SKIPPED", "type": "King Tower"}
            continue
        
        test_result = False
        
        if card_type == "Troop":
            test_result = test_card_deployment_and_basic_functionality(card_name, card_stats)
        elif card_type == "Spell":
            test_result = test_spell_card(card_name, card_stats)
        elif card_type == "Building":
            test_result = test_building_card(card_name, card_stats)
        else:
            print(f"\\n{'='*60}")
            print(f"Testing: {card_name} ({card_type})")
            print(f"{'='*60}")
            print(f"❌ UNKNOWN CARD TYPE: {card_type}")
            results[card_name] = {"status": "FAILED", "type": "Unknown", "error": "Unknown card type"}
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
        time.sleep(0.1)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Print summary
    print(f"\\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Total cards tested: {len(cards)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {len(results) - passed - failed}")
    print(f"Success rate: {passed/len(cards)*100:.1f}%")
    print(f"Total time: {total_time:.1f} seconds")
    
    # Print failed cards
    if failed > 0:
        print(f"\\nFAILED CARDS:")
        print(f"{'-'*40}")
        for card_name, result in results.items():
            if result["status"] == "FAILED":
                print(f"- {card_name} ({result['type']})")
    
    # Print cards with special abilities
    print(f"\\nCARDS WITH SPECIAL ABILITIES:")
    print(f"{'-'*40}")
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
                print(f"- {card_name}: {', '.join(abilities)}")

if __name__ == "__main__":
    main()
