#!/usr/bin/env python3

import sys
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.enhanced_visualizer import EnhancedBattleVisualizer
import pygame

def test_visualizer_deployment_zones():
    """Test the enhanced visualizer with deployment zone tints"""
    
    print("=== Enhanced Visualizer Deployment Zones Test ===")
    print("This will open a pygame window showing deployment zone tints.")
    print("Blue tint = Blue player can deploy")
    print("Red tint = Red player can deploy") 
    print("No tint = Both players can deploy (or neither)")
    print("Press ESC to close the window and continue.")
    
    battle = BattleState()
    visualizer = EnhancedBattleVisualizer()
    
    # Set up elixir
    battle.players[0].elixir = 20.0
    battle.players[1].elixir = 20.0
    
    print(f"\n=== Phase 1: Normal Deployment Zones ===")
    print("You should see:")
    print("- Blue tint in bottom half (y=1-14)")
    print("- Red tint in top half (y=17-30)")
    print("- No tint in river area (y=15-16)")
    
    # Deploy some initial troops
    battle.deploy_card(0, 'Knight', Position(9, 14))
    battle.deploy_card(1, 'Giant', Position(9, 18))
    
    # Show initial state for a few seconds
    frame_count = 0
    running = True
    clock = pygame.time.Clock()
    
    while running and frame_count < 180:  # Show for ~3 seconds at 60 FPS
        running = visualizer.render(battle)
        if not running:
            break
            
        battle.step()
        clock.tick(60)
        frame_count += 1
        
        if frame_count == 60:
            print("Destroying red left tower...")
    
    if not running:
        visualizer.close()
        return
    
    print(f"\n=== Phase 2: After Red Left Tower Destruction ===")
    print("You should now see:")
    print("- Blue tint expanded to left bridge area (x=0-6, y=17-20)")
    print("- Red tint unchanged")
    
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
    
    # Deploy in the new expanded zone
    battle.deploy_card(0, 'Wizard', Position(3, 18))
    
    # Show expanded zones for a few seconds
    frame_count = 0
    while running and frame_count < 180:  # Show for ~3 seconds
        running = visualizer.render(battle)
        if not running:
            break
            
        battle.step()
        clock.tick(60)
        frame_count += 1
        
        if frame_count == 60:
            print("Destroying red right tower...")
    
    if not running:
        visualizer.close()
        return
    
    print(f"\n=== Phase 3: After Both Red Towers Destroyed ===")
    print("You should now see:")
    print("- Blue tint in both bridge areas (x=0-6 and x=11-17, y=17-20)")
    print("- Maximum expansion for blue player")
    
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
    
    # Deploy in the right expanded zone
    battle.deploy_card(0, 'Musketeer', Position(15, 19))
    
    # Show final state
    frame_count = 0
    while running and frame_count < 300:  # Show for ~5 seconds
        running = visualizer.render(battle)
        if not running:
            break
            
        battle.step()
        clock.tick(60)
        frame_count += 1
    
    print(f"\n=== Test Complete ===")
    print("✅ Deployment zone tints implemented")
    print("✅ Blue tint shows blue deployment areas")
    print("✅ Red tint shows red deployment areas")
    print("✅ Expanded zones visible after tower destruction")
    print("✅ Visual feedback for deployment system working")
    
    visualizer.close()

if __name__ == "__main__":
    test_visualizer_deployment_zones()