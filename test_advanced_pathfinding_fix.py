#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Troop, Building
from clasher.data import CardStats

def test_advanced_pathfinding_fix():
    """Test that advanced pathfinding no longer targets unreachable positions"""
    
    print("=== TESTING ADVANCED PATHFINDING FIX ===")
    
    battle = BattleState()
    
    # Simulate tower destruction to activate advanced pathfinding
    battle.players[1].left_tower_hp = 0  # Destroy red left tower
    
    # Create a test troop
    card_stats = CardStats(
        name="Knight",
        id=1,
        mana_cost=3,
        rarity="Common",
        hitpoints=1400,
        damage=167,
        speed=60,
        range=1.0,
        sight_range=5.5
    )
    
    # Create a target building
    target_building = Building(
        id=999,
        position=Position(9.0, 25.0),  # Red side building
        player_id=1,  # Enemy
        card_stats=card_stats,
        hitpoints=1000,
        max_hitpoints=1000,
        damage=100,
        range=5.0,
        sight_range=7.0,
        is_air_unit=False
    )
    
    battle.entities[999] = target_building
    
    # Test troops at different positions
    test_positions = [
        {"pos": Position(5.0, 10.0), "desc": "Blue troop on left side"},
        {"pos": Position(12.0, 10.0), "desc": "Blue troop on right side"},
        {"pos": Position(3.5, 16.0), "desc": "Blue troop on left bridge"},
        {"pos": Position(14.5, 16.0), "desc": "Blue troop on right bridge"},
    ]
    
    for i, test in enumerate(test_positions):
        pos = test["pos"]
        desc = test["desc"]
        
        print(f"\n--- Test {i+1}: {desc} ---")
        print(f"Troop position: ({pos.x}, {pos.y})")
        
        # Create troop at test position
        troop = Troop(
            id=i+1,
            position=pos,
            player_id=0,  # Blue player
            card_stats=card_stats,
            hitpoints=1400,
            max_hitpoints=1400,
            damage=167,
            range=1.0,
            sight_range=5.5,
            speed=60,
            is_air_unit=False
        )
        
        # Get pathfinding target using the fixed advanced logic
        pathfind_target = troop._get_advanced_pathfind_target(target_building)
        
        print(f"Pathfind target: ({pathfind_target.x}, {pathfind_target.y})")
        
        # Check if the target is walkable
        target_walkable = battle.arena.is_walkable(pathfind_target)
        print(f"Target walkable: {target_walkable}")
        
        if target_walkable:
            print(f"✅ Target is reachable")
        else:
            print(f"❌ Target is NOT reachable!")
        
        # Check if target is reasonable (not the old problematic center)
        if pathfind_target.x == 9.0 and pathfind_target.y == 16.0:
            print(f"❌ Still targeting problematic center bridge!")
        elif pathfind_target.x in [3.5, 14.5] or pathfind_target.y in [12.0, 20.0]:
            print(f"✅ Using proper bridge-based pathfinding")
        else:
            print(f"ℹ️  Using different pathfinding logic")

def test_bridge_selection():
    """Test that troops choose the nearest bridge correctly"""
    
    print(f"\n=== TESTING BRIDGE SELECTION ===")
    
    battle = BattleState()
    
    # Destroy a tower to activate advanced pathfinding
    battle.players[1].left_tower_hp = 0
    
    card_stats = CardStats(
        name="Knight",
        id=1,
        mana_cost=3,
        rarity="Common"
    )
    
    target = Building(
        id=999,
        position=Position(9.0, 25.0),
        player_id=1,
        card_stats=card_stats,
        hitpoints=1000,
        max_hitpoints=1000,
        damage=100,
        range=5.0,
        sight_range=7.0,
        is_air_unit=False
    )
    
    # Test bridge selection based on troop position
    bridge_tests = [
        {"pos": Position(2.0, 10.0), "expected_bridge": "left", "desc": "Far left position"},
        {"pos": Position(8.0, 10.0), "expected_bridge": "left", "desc": "Center-left position"},
        {"pos": Position(10.0, 10.0), "expected_bridge": "right", "desc": "Center-right position"},
        {"pos": Position(16.0, 10.0), "expected_bridge": "right", "desc": "Far right position"},
    ]
    
    for test in bridge_tests:
        pos = test["pos"]
        expected = test["expected_bridge"]
        desc = test["desc"]
        
        print(f"\n{desc}: ({pos.x}, {pos.y})")
        
        troop = Troop(
            id=1,
            position=pos,
            player_id=0,
            card_stats=card_stats,
            hitpoints=1400,
            max_hitpoints=1400,
            damage=167,
            range=1.0,
            sight_range=5.5,
            speed=60,
            is_air_unit=False
        )
        
        pathfind_target = troop._get_advanced_pathfind_target(target)
        
        # Determine which bridge was chosen
        if pathfind_target.x == 3.5:
            chosen_bridge = "left"
        elif pathfind_target.x == 14.5:
            chosen_bridge = "right"
        else:
            chosen_bridge = "unknown"
        
        print(f"  Target: ({pathfind_target.x}, {pathfind_target.y})")
        print(f"  Chosen bridge: {chosen_bridge}")
        print(f"  Expected bridge: {expected}")
        
        if chosen_bridge == expected:
            print(f"  ✅ Correct bridge selection")
        else:
            print(f"  ❌ Wrong bridge selection")

if __name__ == "__main__":
    test_advanced_pathfinding_fix()
    test_bridge_selection()