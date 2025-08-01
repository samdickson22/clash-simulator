#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position

def demo_bridge_pathfinding():
    """Demonstrate the tighter bridge pathfinding in action"""
    
    print("=== Bridge Pathfinding Demo ===")
    battle = BattleState()
    
    # Deploy knight near bridge edge that would previously be considered "on bridge"
    battle.players[0].elixir = 10.0
    
    # Deploy at position that was inside old detection (1.5) but outside new detection (1.0)
    # Position (4.2, 16.0) is in the river zone, so let's use valid blue territory
    knight_pos = Position(4.2, 14.0)  # 1.2 tiles from left bridge center, valid blue territory
    success = battle.deploy_card(0, 'Knight', knight_pos)
    print(f"Knight deployed at ({knight_pos.x}, {knight_pos.y}): {'Success' if success else 'Failed'}")
    
    # Find the knight
    knight = None
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Knight":
            knight = entity
            break
    
    if not knight:
        print("❌ Could not find knight - checking all entities:")
        for eid, entity in battle.entities.items():
            print(f"  Entity {eid}: {entity.card_stats.name if entity.card_stats else 'No name'}")
        return
    
    print(f"Distance from left bridge center (3.0): {abs(knight.position.x - 3.0):.1f} tiles")
    print(f"OLD behavior (±1.5): Would be considered ON bridge")
    print(f"NEW behavior (±1.0): NOT on bridge, must path to bridge center first")
    
    # Find target
    red_tower = None
    for entity in battle.entities.values():
        if hasattr(entity, 'card_stats') and entity.card_stats and entity.card_stats.name == "Tower":
            if entity.player_id == 1:  # Red tower
                red_tower = entity
                break
    
    # Show pathfinding decision
    pathfind_target = knight._get_pathfind_target(red_tower)
    print(f"\nPathfinding target: ({pathfind_target.x:.1f}, {pathfind_target.y:.1f})")
    
    if pathfind_target.x == 3.0 and pathfind_target.y == 16.0:
        print("✅ Correct: Knight will move to bridge center first")
    else:
        print("❌ Unexpected: Knight not moving to bridge center")
    
    # Run a few steps to show movement
    print(f"\n=== Movement Simulation ===")
    print(f"Step 0: Position ({knight.position.x:.2f}, {knight.position.y:.2f})")
    
    for step in range(10):
        battle.step()
        print(f"Step {step+1}: Position ({knight.position.x:.2f}, {knight.position.y:.2f})")
        
        # Check if knight reached bridge center
        if abs(knight.position.x - 3.0) < 0.1 and abs(knight.position.y - 16.0) < 0.1:
            print("✅ Knight reached bridge center!")
            break
    
    print(f"\n=== Effect Summary ===")
    print("The 0.5 tile inward adjustment means:")
    print("• Units at bridge edges (like x=4.2) now path to center first")
    print("• Tighter pathfinding creates more predictable bridge crossing")
    print("• Units funnel through a narrower zone, similar to real Clash Royale")


if __name__ == "__main__":
    demo_bridge_pathfinding()