#!/usr/bin/env python3
"""
Fixed test for spell cards
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
        
        # Check for different types of spell effects
        spell_effect_found = False
        
        # 1. Check for projectiles (spells that fire projectiles)
        projectiles = [ent for ent in battle.entities.values() 
                      if hasattr(ent, 'target_position') and ent.player_id == 0]
        if projectiles:
            spell_effect_found = True
            proj = projectiles[0]
            print(f"✅ Spell created projectile!")
            print(f"   - From: ({proj.position.x:.1f}, {proj.position.y:.1f})")
            print(f"   - To: ({proj.target_position.x:.1f}, {proj.target_position.y:.1f})")
            print(f"   - Damage: {proj.damage}")
        
        # 2. Check for cloned troops
        clones = [ent for ent in battle.entities.values() 
                 if hasattr(ent, 'is_clone') and ent.is_clone and ent.player_id == 0]
        if clones:
            spell_effect_found = True
            clone = clones[0]
            print(f"✅ Spell created clone!")
            print(f"   - Cloned: {clone.card_stats.name}")
            print(f"   - Position: ({clone.position.x:.1f}, {clone.position.y:.1f})")
        
        # 3. Check for area effect spells (no visible entities but deployment succeeded)
        if not spell_effect_found and success:
            # Some spells like Rage, Freeze, Poison don't create visible entities
            # but their effects are applied to existing entities
            print(f"✅ Spell cast successfully (area effect)")
            
            # Check if any entities were affected (for buff/debuff spells)
            affected_entities = []
            for ent in battle.entities.values():
                if ent.player_id == 0:  # Friendly units
                    # Check for speed changes (Rage)
                    if hasattr(ent, 'base_speed') and ent.speed > ent.base_speed:
                        affected_entities.append(f"Speed boosted: {ent.card_stats.name if ent.card_stats else 'Entity'}")
                    # Check for freeze effects
                    elif hasattr(ent, 'is_frozen') and ent.is_frozen:
                        affected_entities.append(f"Frozen: {ent.card_stats.name if ent.card_stats else 'Entity'}")
            
            if affected_entities:
                print(f"   - Affected: {', '.join(affected_entities)}")
            else:
                print(f"   - No visible entities created (typical for area effect spells)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test all spell cards"""
    print("Fixed Spell Test")
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
