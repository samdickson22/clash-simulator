#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState

def debug_deployment_zones():
    """Debug the deployment zones to see exactly what tiles are covered"""
    
    battle = BattleState()
    
    print("=== Deployment Zones Debug ===")
    
    blue_zones = battle.arena.get_deploy_zones(0, battle)
    red_zones = battle.arena.get_deploy_zones(1, battle)
    
    print(f"Blue zones: {blue_zones}")
    print(f"Red zones: {red_zones}")
    
    print(f"\n=== Blue Zone Coverage ===")
    for x1, y1, x2, y2 in blue_zones:
        print(f"Zone: x={x1}-{x2-1}, y={y1}-{y2-1}")
        print(f"  Width: {x2-x1} tiles, Height: {y2-y1} tiles")
        print(f"  Total tiles: {(x2-x1) * (y2-y1)}")
    
    print(f"\n=== Red Zone Coverage ===")
    for x1, y1, x2, y2 in red_zones:
        print(f"Zone: x={x1}-{x2-1}, y={y1}-{y2-1}")
        print(f"  Width: {x2-x1} tiles, Height: {y2-y1} tiles")
        print(f"  Total tiles: {(x2-x1) * (y2-y1)}")
    
    print(f"\n=== Specific Tile Tests Behind Kings ===")
    
    # Test specific tiles that should be behind kings
    test_tiles = [
        # Blue king area
        (3, 1), (9, 1), (14, 1),  # y=1 (back row)
        (3, 2), (9, 2), (14, 2),  # y=2 
        (3, 6), (9, 6), (14, 6),  # y=6 (front of king area)
        # Red king area  
        (3, 25), (9, 25), (14, 25),  # y=25 (front of king area)
        (3, 29), (9, 29), (14, 29),  # y=29
        (3, 30), (9, 30), (14, 30),  # y=30 (back row)
    ]
    
    for x, y in test_tiles:
        blue_can = battle.arena.can_deploy_at(battle.arena.tile_to_world(x, y), 0, battle)
        red_can = battle.arena.can_deploy_at(battle.arena.tile_to_world(x, y), 1, battle)
        
        status = []
        if blue_can:
            status.append("BLUE")
        if red_can:
            status.append("RED")
        if not status:
            status.append("BLOCKED")
            
        print(f"Tile ({x}, {y}): {' + '.join(status)}")

if __name__ == "__main__":
    debug_deployment_zones()