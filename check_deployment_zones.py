#!/usr/bin/env python3
"""
Check deployment zones for both players
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.clasher.arena import TileGrid, Position

def main():
    """Check deployment zones"""
    arena = TileGrid()
    
    print("=== Deployment Zones ===")
    
    # Check zones for player 0 (blue, bottom half)
    blue_zones = arena.get_deploy_zones(0)
    print(f"Player 0 (Blue) deployment zones: {blue_zones}")
    
    # Check zones for player 1 (red, top half)  
    red_zones = arena.get_deploy_zones(1)
    print(f"Player 1 (Red) deployment zones: {red_zones}")
    
    print("\\n=== Testing Specific Positions ===")
    
    # Test the positions we're trying to deploy to
    test_positions = [
        Position(5.0, 10.0),  # Our side (should work for player 0)
        Position(5.0, 15.0),  # River (should fail)
        Position(5.0, 20.0),  # Enemy side (should fail for direct deployment)
        Position(5.0, 25.0),  # Deep enemy side (should fail)
        Position(9.0, 2.5),   # Blue king tower (should fail)
        Position(9.0, 29.5),  # Red king tower (should fail)
    ]
    
    for pos in test_positions:
        blue_valid = arena.can_deploy_at(pos, 0)
        red_valid = arena.can_deploy_at(pos, 1)
        print(f"Position ({pos.x}, {pos.y}): Blue={blue_valid}, Red={red_valid}")
    
    print("\\n=== Bridge Positions ===")
    print(f"Left bridge: ({arena.LEFT_BRIDGE.x}, {arena.LEFT_BRIDGE.y})")
    print(f"Right bridge: ({arena.RIGHT_BRIDGE.x}, {arena.RIGHT_BRIDGE.y})")
    print(f"River spans: y={arena.RIVER_Y1}-{arena.RIVER_Y2}")

if __name__ == "__main__":
    main()
