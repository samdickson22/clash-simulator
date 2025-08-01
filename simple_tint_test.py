#!/usr/bin/env python3

import sys
sys.path.append('src')
sys.path.append('.')

from visualize_battle import BattleVisualizer
from clasher.battle import BattleState
import pygame

def simple_tint_test():
    """Simple test to see if tints are visible"""
    
    print("=== Simple Tint Test ===")
    print("This should show blue tint behind the blue king and red tint behind red king")
    print("Press ESC to exit")
    
    visualizer = BattleVisualizer()
    battle = BattleState()
    visualizer.battle = battle
    
    # Print deployment zones
    blue_zones = battle.arena.get_deploy_zones(0, battle)
    red_zones = battle.arena.get_deploy_zones(1, battle)
    
    print(f"Blue zones: {blue_zones}")
    print(f"Red zones: {red_zones}")
    
    running = True
    clock = pygame.time.Clock()
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Draw everything
        visualizer.screen.fill((255, 255, 255))
        visualizer.draw_arena()
        
        # Add text showing what should be visible
        info_text = visualizer.font.render("Should see blue tint behind blue king, red tint behind red king", True, (0, 0, 0))
        visualizer.screen.blit(info_text, (10, 10))
        
        zones_text = visualizer.small_font.render(f"Blue zones: {len(blue_zones)}, Red zones: {len(red_zones)}", True, (0, 0, 0))
        visualizer.screen.blit(zones_text, (10, 40))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    simple_tint_test()