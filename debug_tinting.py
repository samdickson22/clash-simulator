#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState

def debug_tinting():
    """Debug the tinting logic to see what's happening with King areas"""
    
    battle = BattleState()
    
    blue_zones = battle.arena.get_deploy_zones(0, battle)
    red_zones = battle.arena.get_deploy_zones(1, battle)
    
    print(f"Blue zones: {blue_zones}")
    print(f"Red zones: {red_zones}")
    
    # Simulate the tinting logic
    tile_ownership = {}
    
    # Mark blue zones
    for x1, y1, x2, y2 in blue_zones:
        print(f"Processing blue zone: x={x1}-{x2}, y={y1}-{y2}")
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set()
                tile_ownership[(x, y)].add(0)  # Blue player
    
    # Mark red zones  
    for x1, y1, x2, y2 in red_zones:
        print(f"Processing red zone: x={x1}-{x2}, y={y1}-{y2}")
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set()
                tile_ownership[(x, y)].add(1)  # Red player
    
    # Check King areas specifically
    print(f"\n=== King Area Ownership ===")
    
    # Blue King area (6-11, 1-6)
    print("Blue King area (x=6-11, y=1-6):")
    for y in range(1, 7):
        for x in range(6, 12):
            owners = tile_ownership.get((x, y), set())
            owner_list = list(owners)
            print(f"  ({x}, {y}): {owner_list}")
    
    # Red King area (6-11, 25-30)  
    print("\nRed King area (x=6-11, y=25-30):")
    for y in range(25, 31):
        for x in range(6, 12):
            owners = tile_ownership.get((x, y), set())
            owner_list = list(owners)
            print(f"  ({x}, {y}): {owner_list}")

if __name__ == "__main__":
    debug_tinting()