#!/usr/bin/env python3

import sys
sys.path.append('src')
sys.path.append('.')

from visualize_battle import BattleVisualizer
from clasher.battle import BattleState
from clasher.arena import Position
import pygame
import time

def test_deployment_tints():
    """Test deployment zone tints in the correct visualizer"""
    
    print("=== Deployment Zone Tints Test ===") 
    print("This will show the battle visualizer with colored deployment zones.")
    print("Blue tint = Blue player deployment areas")
    print("Red tint = Red player deployment areas")
    print("Press ESC to exit, SPACE to continue phases")
    
    visualizer = BattleVisualizer()
    battle = BattleState()
    visualizer.battle = battle  # Set the battle reference
    
    # Set up elixir
    battle.players[0].elixir = 20.0
    battle.players[1].elixir = 20.0
    
    phase = 0
    running = True
    clock = pygame.time.Clock()
    
    print("\n=== Phase 1: Normal Deployment Zones ===")
    print("You should see blue tint in bottom half, red tint in top half")
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    phase += 1
                    if phase == 1:
                        print("\n=== Phase 2: Destroying Red Left Tower ===")
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
                        print("Red left tower destroyed - blue should get left bridge expansion")
                        
                        # Deploy in expanded zone to test
                        battle.deploy_card(0, 'Knight', Position(3, 18))
                        
                    elif phase == 2:
                        print("\n=== Phase 3: Destroying Red Right Tower ===")
                        # Destroy red right tower
                        battle.players[1].right_tower_hp = 0
                        destroyed_tower_id = None
                        for eid, entity in battle.entities.items():
                            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                                entity.card_stats.name == "Tower" and entity.player_id == 1 and 
                                entity.position.x > 9):
                                destroyed_tower_id = eid
                                entity.hitpoints = 0
                                break
                        if destroyed_tower_id:
                            del battle.entities[destroyed_tower_id]
                        print("Red right tower destroyed - blue should get right bridge expansion")
                        
                        # Deploy in right expanded zone
                        battle.deploy_card(0, 'Giant', Position(15, 19))
                        
                    elif phase == 3:
                        print("\n=== Phase 4: Destroying Red King Tower ===")
                        # Destroy red king tower
                        battle.players[1].king_tower_hp = 0
                        destroyed_tower_id = None
                        for eid, entity in battle.entities.items():
                            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                                entity.card_stats.name == "KingTower" and entity.player_id == 1):
                                destroyed_tower_id = eid
                                entity.hitpoints = 0
                                break
                        if destroyed_tower_id:
                            del battle.entities[destroyed_tower_id]
                        print("Red king tower destroyed - blue should get 6 tiles behind king area")
                        
                        # Deploy behind king tower
                        battle.deploy_card(0, 'Wizard', Position(9, 27))
                        
                    elif phase >= 4:
                        print("Test complete! You should see bridge areas + 6 tiles behind king with blue tint.")
        
        # Update battle
        battle.step()
        
        # Draw everything
        visualizer.screen.fill((255, 255, 255))
        visualizer.draw_arena()
        visualizer.draw_towers()
        visualizer.draw_entities()
        visualizer.draw_ui()
        
        # Show phase info
        phase_text = visualizer.font.render(f"Phase {phase + 1} - Press SPACE for next phase, ESC to exit", True, (0, 0, 0))
        visualizer.screen.blit(phase_text, (10, 10))
        
        # Show deployment zones info
        blue_zones = battle.arena.get_deploy_zones(0, battle)
        red_zones = battle.arena.get_deploy_zones(1, battle)
        
        zone_text = visualizer.small_font.render(f"Blue zones: {len(blue_zones)}, Red zones: {len(red_zones)}", True, (0, 0, 0))
        visualizer.screen.blit(zone_text, (10, 40))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
    print("✅ Deployment zone tints test complete")

if __name__ == "__main__":
    test_deployment_tints()