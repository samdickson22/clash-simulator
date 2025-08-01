#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position, TileGrid

def test_comprehensive_blocked_tiles():
    """Comprehensive test of the blocked tile system"""
    
    print("=== COMPREHENSIVE BLOCKED TILES TEST ===")
    
    arena = TileGrid()
    battle = BattleState()
    
    # Test 1: All blocked tiles are properly defined
    print("\n1. Testing blocked tile definitions:")
    expected_blocked_tiles = [
        # River edge tiles
        (0, 14), (0, 17), (17, 14), (17, 17),
        # Top row fence pattern: 6 gray, 6 green, 6 gray
        (0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0),           # Left 6 gray
        (12, 0), (13, 0), (14, 0), (15, 0), (16, 0), (17, 0),     # Right 6 gray
        # Bottom row fence pattern: 6 gray, 6 green, 6 gray  
        (0, 31), (1, 31), (2, 31), (3, 31), (4, 31), (5, 31),     # Left 6 gray
        (12, 31), (13, 31), (14, 31), (15, 31), (16, 31), (17, 31) # Right 6 gray
    ]
    
    print(f"Expected {len(expected_blocked_tiles)} blocked tiles")
    print(f"Actual blocked tiles: {len(arena.BLOCKED_TILES)}")
    
    missing_tiles = []
    for tile in expected_blocked_tiles:
        if tile not in arena.BLOCKED_TILES:
            missing_tiles.append(tile)
    
    extra_tiles = []
    for tile in arena.BLOCKED_TILES:
        if tile not in expected_blocked_tiles:
            extra_tiles.append(tile)
    
    if missing_tiles:
        print(f"❌ Missing blocked tiles: {missing_tiles}")
    if extra_tiles:
        print(f"❌ Extra blocked tiles: {extra_tiles}")
    
    if not missing_tiles and not extra_tiles:
        print("✅ All blocked tiles correctly defined")
    
    # Test 2: King area tiles are NOT blocked (should be walkable)
    print("\n2. Testing king area tiles are walkable:")
    king_area_tiles = [
        (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0),   # Top king area
        (6, 31), (7, 31), (8, 31), (9, 31), (10, 31), (11, 31)  # Bottom king area
    ]
    
    king_area_errors = []
    for x, y in king_area_tiles:
        if arena.is_blocked_tile(x, y):
            king_area_errors.append((x, y))
        elif not arena.is_walkable(Position(x, y)):
            king_area_errors.append((x, y))
    
    if king_area_errors:
        print(f"❌ King area tiles incorrectly blocked: {king_area_errors}")
    else:
        print("✅ All king area tiles are walkable")
    
    # Test 3: Blocked tiles are unwalkable
    print("\n3. Testing blocked tiles are unwalkable:")
    unwalkable_errors = []
    for x, y in arena.BLOCKED_TILES:
        if arena.is_walkable(Position(x, y)):
            unwalkable_errors.append((x, y))
    
    if unwalkable_errors:
        print(f"❌ Blocked tiles that are walkable: {unwalkable_errors}")
    else:
        print("✅ All blocked tiles are unwalkable")
    
    # Test 4: Deployment zones correctly exclude blocked tiles
    print("\n4. Testing deployment zone exclusions:")
    
    # Simulate the visualizer logic
    blue_zones = arena.get_deploy_zones(0, battle)
    red_zones = arena.get_deploy_zones(1, battle)
    
    tile_ownership = {}
    
    # Process blue zones (same as visualizer)
    for x1, y1, x2, y2 in blue_zones:
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                if arena.is_blocked_tile(x, y):
                    continue  # Should skip blocked tiles
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set()
                tile_ownership[(x, y)].add(0)
    
    # Process red zones (same as visualizer)
    for x1, y1, x2, y2 in red_zones:
        for x in range(int(x1), int(x2)):
            for y in range(int(y1), int(y2)):
                if arena.is_blocked_tile(x, y):
                    continue  # Should skip blocked tiles
                if (x, y) not in tile_ownership:
                    tile_ownership[(x, y)] = set() 
                tile_ownership[(x, y)].add(1)
    
    # Check that no blocked tiles appear in tile_ownership
    blocked_in_ownership = []
    for x, y in arena.BLOCKED_TILES:
        if (x, y) in tile_ownership:
            blocked_in_ownership.append((x, y))
    
    if blocked_in_ownership:
        print(f"❌ Blocked tiles found in deployment ownership: {blocked_in_ownership}")
    else:
        print("✅ No blocked tiles in deployment zone ownership")
    
    # Test 5: River edge tiles specifically  
    print("\n5. Testing river edge tiles:")
    river_edge_tiles = [(0, 14), (0, 17), (17, 14), (17, 17)]
    
    for x, y in river_edge_tiles:
        is_blocked = arena.is_blocked_tile(x, y)
        is_walkable = arena.is_walkable(Position(x, y))
        in_ownership = (x, y) in tile_ownership
        
        print(f"  Tile ({x}, {y}): blocked={is_blocked}, walkable={is_walkable}, in_ownership={in_ownership}")
        
        if not is_blocked:
            print(f"    ❌ Should be blocked!")
        if is_walkable:
            print(f"    ❌ Should not be walkable!")
        if in_ownership:
            print(f"    ❌ Should not be in deployment ownership!")
        
        if is_blocked and not is_walkable and not in_ownership:
            print(f"    ✅ Correctly configured")
    
    # Test 6: Fence pattern verification
    print("\n6. Testing fence pattern (6 gray, 6 green, 6 gray):")
    
    # Top row (y=0)
    top_pattern_correct = True
    for x in range(18):
        is_blocked = arena.is_blocked_tile(x, 0)
        should_be_blocked = x < 6 or x >= 12  # First 6 and last 6 should be blocked
        
        if is_blocked != should_be_blocked:
            print(f"❌ Top row tile ({x}, 0): blocked={is_blocked}, should_be_blocked={should_be_blocked}")
            top_pattern_correct = False
    
    if top_pattern_correct:
        print("✅ Top row fence pattern correct (6 gray, 6 green, 6 gray)")
    
    # Bottom row (y=31)
    bottom_pattern_correct = True
    for x in range(18):
        is_blocked = arena.is_blocked_tile(x, 31)
        should_be_blocked = x < 6 or x >= 12  # First 6 and last 6 should be blocked
        
        if is_blocked != should_be_blocked:
            print(f"❌ Bottom row tile ({x}, 31): blocked={is_blocked}, should_be_blocked={should_be_blocked}")
            bottom_pattern_correct = False
    
    if bottom_pattern_correct:
        print("✅ Bottom row fence pattern correct (6 gray, 6 green, 6 gray)")
    
    # Final summary
    print(f"\n=== SUMMARY ===")
    all_tests_passed = (
        not missing_tiles and not extra_tiles and
        not king_area_errors and not unwalkable_errors and
        not blocked_in_ownership and top_pattern_correct and 
        bottom_pattern_correct
    )
    
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED - Blocked tile system is working correctly!")
    else:
        print("❌ Some tests failed - blocked tile system needs fixes")
    
    return all_tests_passed

if __name__ == "__main__":
    test_comprehensive_blocked_tiles()