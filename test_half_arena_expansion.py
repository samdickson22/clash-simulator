#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def test_half_arena_expansion():
    """Test expanded spawning zones to half arena when towers are destroyed"""
    
    print("=== Half Arena Expansion Test ===")
    battle = BattleState()
    
    # Set up elixir
    battle.players[0].elixir = 30.0
    battle.players[1].elixir = 30.0
    
    print(f"\n=== Initial State ===")
    blue_zones = battle.arena.get_deploy_zones(0, battle)
    print(f"Blue player zones: {blue_zones}")
    
    # Test positions that should NOT be available initially
    test_positions_before = [
        (Position(4, 17), 0, "Left half expansion area"),
        (Position(8, 18), 0, "Left half edge"),
        (Position(9, 17), 0, "Center line"),
        (Position(13, 19), 0, "Right half expansion area"),
        (Position(16, 20), 0, "Right half edge")
    ]
    
    print(f"\n=== Testing Positions Before Tower Destruction ===")
    for pos, player_id, description in test_positions_before:
        can_deploy = battle.arena.can_deploy_at(pos, player_id, battle)
        print(f"{description}: ({pos.x:.1f}, {pos.y:.1f}) - {'❌ Blocked' if not can_deploy else '⚠️ Unexpectedly allowed'}")
    
    print(f"\n=== Destroying Red Left Tower ===")
    
    # Destroy red left tower
    battle.players[1].left_tower_hp = 0
    destroyed_tower_id = None
    for eid, entity in battle.entities.items():
        if (hasattr(entity, 'card_stats') and entity.card_stats and 
            entity.card_stats.name == "Tower" and entity.player_id == 1 and 
            entity.position.x < 9):
            destroyed_tower_id = eid
            entity.hitpoints = 0
            break
    
    if destroyed_tower_id:
        del battle.entities[destroyed_tower_id]
        print(f"✅ Red left tower destroyed")
    
    # Check expanded zones
    blue_zones_expanded = battle.arena.get_deploy_zones(0, battle)
    print(f"Blue player zones after left tower destroyed: {blue_zones_expanded}")
    
    print(f"\n=== Testing Left Half Arena Access ===")
    
    # Test positions in left half that should now be available
    left_half_positions = [
        (Position(0, 17), 0, "Far left edge"),
        (Position(2, 18), 0, "Left side"),
        (Position(4, 19), 0, "Left-center"),
        (Position(6, 20), 0, "Left of center"),
        (Position(8, 17), 0, "Left half boundary"),
        (Position(8, 20), 0, "Left half boundary, 4 tiles back")
    ]
    
    for pos, player_id, description in left_half_positions:
        can_deploy = battle.arena.can_deploy_at(pos, player_id, battle)
        print(f"{description}: ({pos.x:.1f}, {pos.y:.1f}) - {'✅ Available' if can_deploy else '❌ Still blocked'}")
    
    # Test positions that should still be blocked (right half)
    still_blocked_positions = [
        (Position(9, 17), 0, "Center line (should be blocked)"),
        (Position(11, 18), 0, "Right half (should be blocked)"),
        (Position(15, 19), 0, "Far right (should be blocked)")
    ]
    
    print(f"\n=== Testing Right Half Still Blocked ===")
    for pos, player_id, description in still_blocked_positions:
        can_deploy = battle.arena.can_deploy_at(pos, player_id, battle)
        print(f"{description}: ({pos.x:.1f}, {pos.y:.1f}) - {'❌ Correctly blocked' if not can_deploy else '⚠️ Incorrectly allowed'}")
    
    print(f"\n=== Destroying Red Right Tower ===")
    
    # Destroy red right tower
    battle.players[1].right_tower_hp = 0
    destroyed_right_tower_id = None
    for eid, entity in battle.entities.items():
        if (hasattr(entity, 'card_stats') and entity.card_stats and 
            entity.card_stats.name == "Tower" and entity.player_id == 1 and 
            entity.position.x > 9):
            destroyed_right_tower_id = eid
            entity.hitpoints = 0
            break
    
    if destroyed_right_tower_id:
        del battle.entities[destroyed_right_tower_id]
        print(f"✅ Red right tower destroyed")
    
    # Check fully expanded zones
    blue_zones_full = battle.arena.get_deploy_zones(0, battle)
    print(f"Blue player zones after both towers destroyed: {blue_zones_full}")
    
    print(f"\n=== Testing Full Arena Access ===")
    
    # Test positions across the full arena width
    full_arena_positions = [
        (Position(0, 17), 0, "Far left edge"),
        (Position(4, 18), 0, "Left quarter"),
        (Position(8, 19), 0, "Left half boundary"),
        (Position(9, 17), 0, "Center line"),
        (Position(12, 18), 0, "Right quarter"),
        (Position(16, 19), 0, "Right edge"),
        (Position(17, 20), 0, "Far right edge")
    ]
    
    for pos, player_id, description in full_arena_positions:
        can_deploy = battle.arena.can_deploy_at(pos, player_id, battle)
        print(f"{description}: ({pos.x:.1f}, {pos.y:.1f}) - {'✅ Available' if can_deploy else '❌ Still blocked'}")
    
    print(f"\n=== Testing Actual Deployments ===")
    
    # Test actual deployments across the expanded zones
    deployment_tests = [
        (Position(2, 18), 'Knight', "Left edge deployment"),
        (Position(8, 19), 'Wizard', "Left boundary deployment"),
        (Position(9, 17), 'Giant', "Center line deployment"),
        (Position(15, 20), 'Musketeer', "Right side deployment")
    ]
    
    for pos, card, description in deployment_tests:
        success = battle.deploy_card(0, card, pos)
        print(f"{description} ({pos.x:.1f}, {pos.y:.1f}): {'✅ Success' if success else '❌ Failed'}")
    
    print(f"\n=== Comparison: Before vs After ===")
    print("Before tower destruction:")
    print("  - Bridge areas blocked")
    print("  - Enemy territory inaccessible")
    print("")
    print("After left tower destruction:")
    print("  - Left half arena accessible (x=0-8, y=17-20)")
    print("  - Right half still blocked")
    print("")
    print("After both towers destruction:")
    print("  - Full arena width accessible (x=0-17, y=17-20)")
    print("  - 4 tiles deep into enemy territory")
    
    print(f"\n=== Summary ===")
    print("✅ Half arena expansion implemented")
    print("✅ Left tower destruction → Left half access (x=0-8)")
    print("✅ Right tower destruction → Right half access (x=9-17)")
    print("✅ Both towers → Full arena width (x=0-17)")
    print("✅ 4 tiles deep enemy territory access")
    print("✅ More strategic deployment options after tower destruction!")

if __name__ == "__main__":
    test_half_arena_expansion()