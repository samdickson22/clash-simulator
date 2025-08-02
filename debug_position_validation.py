#!/usr/bin/env python3
"""
Debug position validation issues
"""

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def debug_position_validation():
    """Debug why position (9, 8) is causing units to spawn at boundaries"""
    
    print("=== Debugging Position Validation ===")
    
    battle = BattleState()
    deploy_pos = Position(9, 8)
    player_id = 0
    
    print(f"Testing deploy position: ({deploy_pos.x}, {deploy_pos.y})")
    
    # Test arena validation
    print(f"is_valid_position: {battle.arena.is_valid_position(deploy_pos)}")
    print(f"is_walkable: {battle.arena.is_walkable(deploy_pos)}")
    print(f"can_deploy_at: {battle.arena.can_deploy_at(deploy_pos, player_id, battle, False, None)}")
    
    # Test deployment zones
    zones = battle.arena.get_deploy_zones(player_id, battle)
    print(f"Deployment zones for player {player_id}: {zones}")
    
    # Check if position is in any zone
    in_zone = False
    for x1, y1, x2, y2 in zones:
        if x1 <= deploy_pos.x < x2 and y1 <= deploy_pos.y < y2:
            in_zone = True
            print(f"Position is in zone: ({x1}, {y1}) to ({x2}, {y2})")
            break
    
    if not in_zone:
        print("Position is NOT in any deployment zone")
    
    # Test snap_to_valid_position
    snapped_pos = battle._snap_to_valid_position(deploy_pos, player_id)
    print(f"Snapped position: ({snapped_pos.x}, {snapped_pos.y})")
    print(f"Distance moved: {deploy_pos.distance_to(snapped_pos):.2f}")
    
    # Test a few positions around the deploy position
    print("\nTesting nearby positions:")
    for x_offset in [-1, 0, 1]:
        for y_offset in [-1, 0, 1]:
            test_pos = Position(deploy_pos.x + x_offset, deploy_pos.y + y_offset)
            walkable = battle.arena.is_walkable(test_pos)
            valid = battle.arena.is_valid_position(test_pos)
            can_deploy = battle.arena.can_deploy_at(test_pos, player_id, battle, False, None)
            print(f"  ({test_pos.x}, {test_pos.y}): valid={valid}, walkable={walkable}, can_deploy={can_deploy}")

if __name__ == "__main__":
    debug_position_validation()