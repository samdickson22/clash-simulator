#!/usr/bin/env python3
"""
Test all swarm cards to ensure they work correctly
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader

def test_swarm_card_sample():
    """Test a representative sample of swarm cards"""
    
    print("=== Testing Sample of All Swarm Cards ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0  # Extra elixir for expensive cards
    
    # Test cases: representative sample of different swarm types
    test_cases = [
        # Small swarms (2-3 units)
        ('Skeletons', 3, "Small swarm"),
        ('Archer', 2, "Archers (2 units)"),
        ('Minions', 3, "Flying swarm"),
        
        # Medium swarms (4-6 units) 
        ('Goblins', 4, "Medium swarm"),
        ('Barbarians', 5, "Heavy units"),
        ('MinionHorde', 6, "Large flying swarm"),
        
        # Large swarms (7+ units)
        ('SkeletonArmy', 15, "Massive swarm"),
        ('RoyalRecruits', 6, "Shield units"),
        
        # Mixed swarm
        ('GoblinGang', 6, "Mixed melee/ranged"),
        
        # Special cases
        ('ThreeMusketeers', 3, "Heavy ranged"),
        ('Wallbreakers', 2, "Kamikaze units"),
    ]
    
    successful_tests = 0
    failed_tests = 0
    
    for card_name, expected_count, description in test_cases:
        print(f"\n--- Testing {card_name} ({description}) ---")
        
        if card_name not in cards:
            print(f"❌ {card_name} not available in game")
            failed_tests += 1
            continue
        
        card_stats = cards[card_name]
        
        # Add card to hand
        battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
        
        # Clear previous entities (keep towers and buildings)
        entities_before = len(battle.entities)
        
        # Deploy the card
        deploy_pos = Position(9, 8)  # Blue territory
        success = battle.deploy_card(0, card_name, deploy_pos)
        
        if success:
            # Count new entities spawned near deploy position
            spawned_units = []
            
            # Special case for Royal Recruits (line formation spans wide area)
            search_radius = 7.0 if card_name in ['RoyalRecruits', 'RoyalRecruits_Chess'] else 4.0
            
            for entity in battle.entities.values():
                # Only count troops/units spawned near the deploy position
                if (hasattr(entity, 'card_stats') and entity.card_stats and 
                    entity.position.distance_to(deploy_pos) <= search_radius and
                    getattr(entity, 'player_id', -1) == 0):  # Player 0's units
                    # Exclude towers by checking if they're at tower positions
                    pos = entity.position
                    is_tower = (
                        (pos.x == 3.5 and pos.y == 6.5) or   # Blue left tower
                        (pos.x == 14.5 and pos.y == 6.5) or  # Blue right tower  
                        (pos.x == 9.0 and pos.y == 2.5) or   # Blue king tower
                        (pos.x == 3.5 and pos.y == 25.5) or  # Red left tower
                        (pos.x == 14.5 and pos.y == 25.5) or # Red right tower
                        (pos.x == 9.0 and pos.y == 29.5)     # Red king tower
                    )
                    if not is_tower:
                        spawned_units.append(entity)
            
            spawned_count = len(spawned_units)
            
            print(f"✅ {card_name} deployed: {spawned_count} units")
            
            # Verify count
            if spawned_count == expected_count:
                print(f"✅ Correct count: {spawned_count}/{expected_count}")
                successful_tests += 1
            else:
                print(f"❌ Wrong count: {spawned_count}/{expected_count}")
                failed_tests += 1
            
            # Check unit positioning
            all_valid = True
            for unit in spawned_units:
                pos = unit.position
                if not (battle.arena.is_valid_position(pos) and battle.arena.is_walkable(pos)):
                    all_valid = False
                    break
            
            if all_valid:
                print(f"✅ All units in valid positions")
            else:
                print(f"❌ Some units in invalid positions")
            
            # Show formation details for special cases
            if card_name in ['RoyalRecruits', 'RoyalRecruits_Chess']:
                # Check horizontal line formation
                positions = [(unit.position.x, unit.position.y) for unit in spawned_units]
                positions.sort()
                
                if len(positions) >= 2:
                    # Check if all units are on same Y coordinate (horizontal line)
                    y_coords = [pos[1] for pos in positions]
                    if len(set(y_coords)) == 1:
                        print(f"✅ Units in horizontal line")
                        
                        # Check spacing
                        spacings = []
                        for i in range(1, len(positions)):
                            spacing = positions[i][0] - positions[i-1][0]
                            spacings.append(spacing)
                        
                        if spacings:
                            avg_spacing = sum(spacings) / len(spacings)
                            print(f"✅ Average spacing: {avg_spacing:.1f} tiles")
                    else:
                        print(f"❌ Units not in horizontal line")
            
            # Show unit types for mixed swarms
            elif card_name == 'GoblinGang':
                unit_types = {}
                for unit in spawned_units:
                    unit_name = unit.card_stats.name
                    unit_types[unit_name] = unit_types.get(unit_name, 0) + 1
                
                print(f"Unit composition: {dict(unit_types)}")
                expected_composition = {'Goblin_Stab': 3, 'SpearGoblin': 3}
                if unit_types == expected_composition:
                    print(f"✅ Correct mixed composition")
                else:
                    print(f"❌ Wrong mixed composition")
            
            # Clear non-tower entities for next test
            from clasher.entities import Building
            battle.entities = {k: v for k, v in battle.entities.items() 
                             if isinstance(v, Building)}  # Keep only towers
            
            # Reset elixir for next test
            battle.players[0].elixir = 50.0
        else:
            print(f"❌ {card_name} deployment failed")
            failed_tests += 1
    
    print(f"\n=== Test Summary ===")
    total_tests = successful_tests + failed_tests
    print(f"Successful: {successful_tests}/{total_tests}")
    print(f"Failed: {failed_tests}/{total_tests}")
    
    if failed_tests == 0:
        print("✅ All swarm cards working correctly!")
    else:
        print("❌ Some swarm cards need attention")

def test_edge_case_swarms():
    """Test edge cases like very large swarms"""
    
    print(f"\n=== Testing Edge Case Swarms ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    # Test large swarms that might have positioning issues
    edge_cases = [
        ('SkeletonArmy', 15, "Massive 15-unit swarm"),
        ('RoyalRecruits_Chess', 8, "8-unit chess variant"),
    ]
    
    for card_name, expected_count, description in edge_cases:
        print(f"\n--- {description} ---")
        
        if card_name not in cards:
            print(f"❌ {card_name} not available")
            continue
        
        battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
        
        deploy_pos = Position(9, 8)
        success = battle.deploy_card(0, card_name, deploy_pos)
        
        if success:
            # Count and analyze spawned units  
            spawned_units = []
            for entity in battle.entities.values():
                if (hasattr(entity, 'card_stats') and entity.card_stats and 
                    entity.position.distance_to(deploy_pos) <= 5.0 and
                    getattr(entity, 'player_id', -1) == 0):  # Player 0's units
                    # Exclude towers by checking if they're at tower positions
                    pos = entity.position
                    is_tower = (
                        (pos.x == 3.5 and pos.y == 6.5) or   # Blue left tower
                        (pos.x == 14.5 and pos.y == 6.5) or  # Blue right tower  
                        (pos.x == 9.0 and pos.y == 2.5) or   # Blue king tower
                        (pos.x == 3.5 and pos.y == 25.5) or  # Red left tower
                        (pos.x == 14.5 and pos.y == 25.5) or # Red right tower
                        (pos.x == 9.0 and pos.y == 29.5)     # Red king tower
                    )
                    if not is_tower:
                        spawned_units.append(entity)
            
            print(f"✅ Spawned {len(spawned_units)} units")
            
            # Check for overlapping positions
            positions = [(unit.position.x, unit.position.y) for unit in spawned_units]
            unique_positions = set(positions)
            
            if len(unique_positions) == len(positions):
                print(f"✅ No overlapping positions")
            else:
                overlaps = len(positions) - len(unique_positions)
                print(f"⚠️  {overlaps} overlapping positions")
            
            # Check spread
            if spawned_units:
                distances = [unit.position.distance_to(deploy_pos) for unit in spawned_units]
                max_distance = max(distances)
                avg_distance = sum(distances) / len(distances)
                print(f"Spread: max {max_distance:.2f}, avg {avg_distance:.2f} tiles")
            
            # Check all positions are valid
            invalid_count = 0
            for unit in spawned_units:
                pos = unit.position
                if not (battle.arena.is_valid_position(pos) and battle.arena.is_walkable(pos)):
                    invalid_count += 1
            
            if invalid_count == 0:
                print(f"✅ All positions valid")
            else:
                print(f"❌ {invalid_count} invalid positions")
        else:
            print(f"❌ Deployment failed")

if __name__ == "__main__":
    test_swarm_card_sample()
    test_edge_case_swarms()