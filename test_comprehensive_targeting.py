#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building

def test_comprehensive_targeting():
    """Comprehensive test of all targeting rules"""
    
    print("=== Comprehensive Targeting Test ===")
    battle = BattleState()
    
    # Set up a complex scenario
    deployments = [
        # Player 0 (bottom)
        ('Giant', Position(5, 10)),      # Building-only
        ('Minions', Position(7, 10)),    # Air unit
        ('Knight', Position(9, 10)),     # Ground unit
        
        # Player 1 (top) - closer to test proper targeting priorities
        ('Knight', Position(11, 20)),    # Ground unit
        ('BabyDragon', Position(13, 20)), # Air unit that can attack both
        ('Musketeer', Position(15, 20)),  # Ground unit that can attack air
    ]
    
    print("Deploying units...")
    deployed_units = {}
    for card_name, pos in deployments:
        player_id = 0 if pos.y < 16 else 1
        success = battle.deploy_card(player_id, card_name, pos)
        print(f"  {card_name} (P{player_id}): {'✅' if success else '❌'}")
        
        if success:
            # Find the deployed unit
            for entity in battle.entities.values():
                if (isinstance(entity, Troop) and entity.card_stats and 
                    entity.card_stats.name == card_name and entity.player_id == player_id):
                    if card_name not in deployed_units:
                        deployed_units[card_name] = []
                    deployed_units[card_name].append(entity)
                    break
    
    print(f"\nDeployed {sum(len(units) for units in deployed_units.values())} units")
    
    # Test targeting rules before movement
    print("\n=== Initial Targeting Analysis ===")
    
    for card_name, units in deployed_units.items():
        for i, unit in enumerate(units):
            target = unit.get_nearest_target(battle.entities)
            
            # Get unit properties
            is_air = unit.is_air_unit
            targets_only_buildings = getattr(unit.card_stats, 'targets_only_buildings', False)
            can_attack_air = (hasattr(unit, 'card_stats') and 
                             unit.card_stats and 
                             (getattr(unit.card_stats, 'target_type', None) in ['TID_TARGETS_AIR_AND_GROUND', 'TID_TARGETS_AIR']))
            
            unit_name = f"{card_name}#{i+1} (P{unit.player_id})"
            properties = []
            if is_air:
                properties.append("air")
            if targets_only_buildings:
                properties.append("buildings_only")
            if can_attack_air:
                properties.append("can_attack_air")
            
            print(f"{unit_name} [{', '.join(properties) if properties else 'ground'}]:")
            
            if target:
                if isinstance(target, Building):
                    print(f"  → Tower ✅")
                else:
                    target_name = target.card_stats.name if target.card_stats else "Unknown"
                    target_air = target.is_air_unit
                    
                    # Validate targeting rules
                    valid = True
                    issues = []
                    
                    # Check building-only rule
                    if targets_only_buildings and not isinstance(target, Building):
                        valid = False
                        issues.append("should only target buildings")
                    
                    # Check air targeting rule
                    if target_air and not can_attack_air:
                        valid = False
                        issues.append("cannot attack air units")
                    
                    status = "✅" if valid else "❌"
                    issue_text = f" ({'; '.join(issues)})" if issues else ""
                    air_text = " (air)" if target_air else ""
                    
                    print(f"  → {target_name}{air_text} {status}{issue_text}")
            else:
                print(f"  → No target")
    
    # Run simulation to see targeting in action
    print(f"\n=== Battle Simulation (10 steps) ===")
    
    for step in range(10):
        battle.step()
        
        if step == 4:  # Check targeting after some movement
            print(f"\nAfter {step+1} steps - Active targeting:")
            for card_name, units in deployed_units.items():
                for i, unit in enumerate(units):
                    if not unit.is_alive:
                        continue
                        
                    target = unit.get_nearest_target(battle.entities)
                    if target and not isinstance(target, Building):
                        target_name = target.card_stats.name if target.card_stats else "Unknown"
                        print(f"  {card_name}#{i+1} → {target_name}")

if __name__ == "__main__":
    test_comprehensive_targeting()