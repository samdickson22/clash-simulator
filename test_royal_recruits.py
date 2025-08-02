#!/usr/bin/env python3
"""
Test Royal Recruits horizontal line deployment
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.entities import Building

def test_royal_recruits_deployment():
    """Test Royal Recruits special horizontal line deployment"""
    
    print("=== Testing Royal Recruits Deployment ===")
    
    # Create battle state
    battle = BattleState()
    
    # Load cards
    card_loader = CardDataLoader()
    cards = card_loader.load_cards()
    
    # Give player full elixir
    battle.players[0].elixir = 50.0
    
    # Test Royal Recruits deployment
    card_name = 'RoyalRecruits'
    if card_name not in cards:
        print(f"❌ {card_name} not found in database")
        return
    
    card_stats = cards[card_name]
    print(f"Card: {card_stats.name}")
    print(f"Summon count: {getattr(card_stats, 'summon_count', None)}")
    print(f"Expected: 6 units in horizontal line, spaced 2.5 tiles apart")
    
    # Test 1: Deploy in center (should work)
    print(f"\n--- Test 1: Deploy at center (9, 8) ---")
    battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
    battle.entities = {k: v for k, v in battle.entities.items() if isinstance(v, Building)}
    
    deploy_pos = Position(9, 8)  # Center of allowed zone
    success = battle.deploy_card(0, card_name, deploy_pos)
    
    if success:
        # Analyze spawned units
        spawned_units = []
        for entity in battle.entities.values():
            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                getattr(entity, 'player_id', -1) == 0 and
                entity.card_stats.name == card_name):
                spawned_units.append(entity)
        
        print(f"✅ Deployed successfully: {len(spawned_units)} units")
        
        # Check positions
        positions = [(unit.position.x, unit.position.y) for unit in spawned_units]
        positions.sort()  # Sort by x coordinate
        
        print(f"Unit positions (x, y):")
        for i, (x, y) in enumerate(positions):
            print(f"  Unit {i+1}: ({x:.2f}, {y:.2f})")
        
        # Check spacing
        if len(positions) >= 2:
            spacings = []
            for i in range(1, len(positions)):
                spacing = positions[i][0] - positions[i-1][0]
                spacings.append(spacing)
            
            avg_spacing = sum(spacings) / len(spacings)
            print(f"Average spacing: {avg_spacing:.2f} tiles (expected: 2.5)")
            
            if 2.4 <= avg_spacing <= 2.6:
                print("✅ Correct spacing")
            else:
                print("❌ Incorrect spacing")
        
        # Check line formation (all units should have same Y coordinate)
        y_coords = [pos[1] for pos in positions]
        if len(set(y_coords)) == 1:
            print("✅ All units in horizontal line")
        else:
            print("❌ Units not in horizontal line")
        
        # Check if line is centered on deploy position
        if positions:
            leftmost_x = positions[0][0]
            rightmost_x = positions[-1][0]
            line_center = (leftmost_x + rightmost_x) / 2
            center_offset = abs(line_center - deploy_pos.x)
            print(f"Line center: {line_center:.2f}, Deploy center: {deploy_pos.x}, Offset: {center_offset:.2f}")
            
            if center_offset <= 0.1:
                print("✅ Line correctly centered on deploy position")
            else:
                print("❌ Line not centered on deploy position")
    else:
        print("❌ Deployment failed")
    
    # Test 2: Deploy outside center 6 tiles (should fail)
    print(f"\n--- Test 2: Deploy outside center 6 tiles (5, 8) ---")
    battle.entities = {k: v for k, v in battle.entities.items() if isinstance(v, Building)}
    battle.players[0].elixir = 50.0
    battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
    
    invalid_pos = Position(5, 8)  # Outside center 6 tiles (6-11)
    success = battle.deploy_card(0, card_name, invalid_pos)
    
    if success:
        print("❌ Deployment should have failed outside center 6 tiles")
    else:
        print("✅ Deployment correctly failed outside center 6 tiles")
    
    # Test 3: Deploy at edge of center zone (should work)
    print(f"\n--- Test 3: Deploy at edge of center zone (6, 8) ---")
    battle.entities = {k: v for k, v in battle.entities.items() if isinstance(v, Building)}
    battle.players[0].elixir = 50.0
    battle.players[0].hand = [card_name, 'Knight', 'Fireball', 'Arrows']
    
    edge_pos = Position(6, 8)  # Edge of center 6 tiles
    success = battle.deploy_card(0, card_name, edge_pos)
    
    if success:
        spawned_units = []
        for entity in battle.entities.values():
            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                getattr(entity, 'player_id', -1) == 0 and
                entity.card_stats.name == card_name):
                spawned_units.append(entity)
        
        print(f"✅ Deployed at edge: {len(spawned_units)} units")
        
        # Check that no units are outside arena bounds
        out_of_bounds = 0
        for unit in spawned_units:
            if unit.position.x < 0.5 or unit.position.x > 17.5:
                out_of_bounds += 1
        
        if out_of_bounds == 0:
            print("✅ All units within arena bounds")
        else:
            print(f"❌ {out_of_bounds} units outside arena bounds")
    else:
        print("❌ Deployment failed at valid edge position")

if __name__ == "__main__":
    test_royal_recruits_deployment()