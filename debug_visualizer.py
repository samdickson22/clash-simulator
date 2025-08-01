#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import TileGrid

def debug_visualizer_logic():
    """Debug the exact logic used in visualizer for deployment tints"""
    
    battle = BattleState()
    arena = TileGrid()
    
    print("=== SIMULATING VISUALIZER LOGIC ===")
    
    # Get deployment zones (same as visualizer)
    blue_zones = arena.get_deploy_zones(0, battle)
    red_zones = arena.get_deploy_zones(1, battle)
    
    print(f"Blue zones: {blue_zones}")
    print(f"Red zones: {red_zones}")
    
    # Create tile_ownership dictionary (same as visualizer)
    tile_ownership = {}  # (x, y) -> set of player_ids
    
    # Mark blue zones (same logic as visualizer)
    print("\n=== PROCESSING BLUE ZONES ===")
    for x1, y1, x2, y2 in blue_zones:
        print(f"Processing blue zone: ({x1}, {y1}, {x2}, {y2})")
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                print(f"  Checking tile ({x}, {y}): blocked={arena.is_blocked_tile(x, y)}")
                # Skip blocked tiles entirely - don't add them to tile_ownership
                if arena.is_blocked_tile(x, y):
                    print(f"    Skipping blocked tile ({x}, {y})")
                    continue
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set()
                tile_ownership[(x, y)].add(0)  # Blue player
                print(f"    Added ({x}, {y}) to blue ownership")
    
    # Mark red zones (same logic as visualizer) 
    print("\n=== PROCESSING RED ZONES ===")
    for x1, y1, x2, y2 in red_zones:
        print(f"Processing red zone: ({x1}, {y1}, {x2}, {y2})")
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                print(f"  Checking tile ({x}, {y}): blocked={arena.is_blocked_tile(x, y)}")
                # Skip blocked tiles entirely - don't add them to tile_ownership
                if arena.is_blocked_tile(x, y):
                    print(f"    Skipping blocked tile ({x}, {y})")
                    continue
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set()
                tile_ownership[(x, y)].add(1)  # Red player
                print(f"    Added ({x}, {y}) to red ownership")
    
    # Check river edge tiles specifically
    problem_tiles = [(0, 14), (0, 17), (17, 14), (17, 17)]
    
    print(f"\n=== FINAL TILE_OWNERSHIP CHECK ===")
    print(f"Tile ownership contains {len(tile_ownership)} tiles")
    
    for tile_x, tile_y in problem_tiles:
        in_ownership = (tile_x, tile_y) in tile_ownership
        is_blocked = arena.is_blocked_tile(tile_x, tile_y)
        print(f"Tile ({tile_x}, {tile_y}): in_ownership={in_ownership}, is_blocked={is_blocked}")
        
        if in_ownership:
            print(f"  ERROR: Blocked tile should not be in tile_ownership!")
        else:
            print(f"  CORRECT: Blocked tile properly excluded from tile_ownership")

if __name__ == "__main__":
    debug_visualizer_logic()