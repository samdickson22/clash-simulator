#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_targeting():
    """Test targeting rules for air units and building-only troops"""
    
    print("=== Air Unit Targeting Test ===")
    battle = BattleState()
    
    # Deploy Minions (air unit)
    success = battle.deploy_card(0, 'Minions', Position(5, 10))
    print(f"Minions deployment: {'Success' if success else 'Failed'}")
    
    # Deploy Musketeer (can attack air)  
    success = battle.deploy_card(1, 'Musketeer', Position(13, 24))
    print(f"Musketeer deployment: {'Success' if success else 'Failed'}")
    
    # Deploy Knight (ground-only attacker)
    success = battle.deploy_card(1, 'Knight', Position(15, 24))
    print(f"Knight deployment: {'Success' if success else 'Failed'}")
    
    # Check what got deployed
    troops = [e for e in battle.entities.values() if isinstance(e, Troop)]
    print(f"Deployed {len(troops)} troops")
    
    # Get troops before updates
    minions = None
    knight = None
    for entity in battle.entities.values():
        if isinstance(entity, Troop) and entity.card_stats:
            if entity.card_stats.name == "Minions":
                minions = entity
            elif entity.card_stats.name == "Knight":
                knight = entity
    
    # Test targeting: Knight should NOT target air Minions (can't attack air)
    if knight and minions:
        knight_target = knight.get_nearest_target(battle.entities)
        print(f"Knight targeting test:")
        if knight_target == minions:
            print(f"  ❌ ERROR: Knight is targeting Minions (air unit)")
        else:
            print(f"  ✅ CORRECT: Knight ignores air Minions, targets tower instead")
    
    # Test air unit seeing ground unit - it should be able to target it
    if minions and knight:
        minions_target = minions.get_nearest_target(battle.entities)
        print(f"Minions targeting test:")
        if minions_target == knight:
            print(f"  ✅ CORRECT: Minions can target ground Knight")
        else:
            print(f"  → Minions targets tower (may be closer)")
    
    # Step the battle a few times to see targeting in action
    for i in range(10):
        battle.step()
        if i == 5:  # Check targeting after some movement
            print(f"\nAfter {i+1} steps:")
            for entity in battle.entities.values():
                if isinstance(entity, Troop) and entity.card_stats:
                    target = entity.get_nearest_target(battle.entities)
                    if target and not isinstance(target, Building):
                        target_name = target.card_stats.name if target.card_stats else "Unknown"
                        print(f"  {entity.card_stats.name} -> {target_name}")
    
    print("\n=== Building-Only Targeting Test ===")
    battle2 = BattleState()
    
    # Deploy Giant (building-only)
    success = battle2.deploy_card(0, 'Giant', Position(5, 10))
    print(f"Giant deployment: {'Success' if success else 'Failed'}")
    
    # Deploy Knight (troop)
    success = battle2.deploy_card(1, 'Knight', Position(13, 24))
    print(f"Knight deployment: {'Success' if success else 'Failed'}")
    
    # Get troops before testing
    giant = None
    knight = None
    for entity in battle2.entities.values():
        if isinstance(entity, Troop) and entity.card_stats:
            if entity.card_stats.name == "Giant":
                giant = entity
            elif entity.card_stats.name == "Knight":
                knight = entity
    
    # Test Giant targeting - should ignore Knight and target tower
    if giant and knight:
        giant_target = giant.get_nearest_target(battle2.entities)
        print(f"Giant targeting test:")
        if giant_target == knight:
            print(f"  ❌ ERROR: Giant is targeting Knight (should only target buildings)")
        else:
            print(f"  ✅ CORRECT: Giant ignores Knight, targets tower")
    
    # Test Knight targeting - should be able to target Giant
    if knight and giant:
        knight_target = knight.get_nearest_target(battle2.entities)
        print(f"Knight targeting test:")
        if knight_target == giant:
            print(f"  ✅ CORRECT: Knight can target Giant")
        else:
            print(f"  → Knight targets tower (may be closer)")
    
    # Run battle and check targeting continues to work
    for i in range(10):
        battle2.step()
        if i == 5:
            print(f"\nAfter {i+1} steps:")
            for entity in battle2.entities.values():
                if isinstance(entity, Troop) and entity.card_stats:
                    target = entity.get_nearest_target(battle2.entities)
                    targets_only = getattr(entity.card_stats, 'targets_only_buildings', False)
                    if target and not isinstance(target, Building):
                        target_name = target.card_stats.name if target.card_stats else "Unknown"
                        if targets_only:
                            print(f"  ❌ {entity.card_stats.name} -> {target_name} (should only target buildings!)")
                        else:
                            print(f"  ✅ {entity.card_stats.name} -> {target_name}")
                    elif target:
                        print(f"  ✅ {entity.card_stats.name} -> Tower")

if __name__ == "__main__":
    test_targeting()