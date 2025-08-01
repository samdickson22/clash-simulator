#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import TileGrid

def debug_deployment_tints():
    """Debug which tiles get tints and why"""
    
    battle = BattleState()
    arena = TileGrid()
    
    print("=== DEBUGGING DEPLOYMENT TINTS ===")
    
    # Get deployment zones
    blue_zones = arena.get_deploy_zones(0, battle)
    red_zones = arena.get_deploy_zones(1, battle)
    
    print(f"Blue zones: {blue_zones}")
    print(f"Red zones: {red_zones}")
    
    print(f"Blocked tiles: {arena.BLOCKED_TILES}")
    
    # Check specifically the problematic river edge tiles
    problem_tiles = [(0, 14), (0, 17), (17, 14), (17, 17)]
    
    print("\n=== RIVER EDGE TILES ANALYSIS ===")
    
    for tile_x, tile_y in problem_tiles:
        print(f"\nTile ({tile_x}, {tile_y}):")
        print(f"  Is blocked: {arena.is_blocked_tile(tile_x, tile_y)}")
        
        # Check which zones include this tile
        in_blue = False
        in_red = False
        
        for x1, y1, x2, y2 in blue_zones:
            if x1 <= tile_x < x2 and y1 <= tile_y < y2:
                in_blue = True
                print(f"  In blue zone: ({x1}, {y1}, {x2}, {y2})")
        
        for x1, y1, x2, y2 in red_zones:
            if x1 <= tile_x < x2 and y1 <= tile_y < y2:
                in_red = True
                print(f"  In red zone: ({x1}, {y1}, {x2}, {y2})")
        
        if not in_blue and not in_red:
            print("  Not in any deployment zone")
        
        # This simulates what happens in the visualizer
        would_get_tint = (in_blue or in_red) and not arena.is_blocked_tile(tile_x, tile_y)
        print(f"  Would get tint: {would_get_tint}")

if __name__ == "__main__":
    debug_deployment_tints()