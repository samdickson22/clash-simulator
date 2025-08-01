#!/usr/bin/env python3
"""
Test blocked tiles visualization
"""

import pygame
import sys
import time
sys.path.append('src')

from src.clasher.engine import BattleEngine
from src.clasher.arena import Position

# Initialize Pygame
pygame.init()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 100, 100)
BLUE = (100, 100, 255)
GREEN = (100, 255, 100)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)

# Screen settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 700
TILE_SIZE = 20
ARENA_WIDTH = 18 * TILE_SIZE
ARENA_HEIGHT = 32 * TILE_SIZE
ARENA_X = 50
ARENA_Y = 50

def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Blocked Tiles Visualization Test")
    clock = pygame.time.Clock()
    
    # Create battle engine
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    print("=== Blocked Tiles Visualization Test ===")
    print("Blocked tiles should appear as gray squares at:")
    print("- (0, 14) - Left edge, bottom land next to river")
    print("- (0, 17) - Left edge, top land next to river") 
    print("- (17, 14) - Right edge, bottom land next to river")
    print("- (17, 17) - Right edge, top land next to river")
    print("Press ESC to exit")
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Clear screen
        screen.fill(BLACK)
        
        # Draw arena background
        arena_rect = pygame.Rect(ARENA_X, ARENA_Y, ARENA_WIDTH, ARENA_HEIGHT)
        pygame.draw.rect(screen, GREEN, arena_rect)
        
        # Draw grid
        for i in range(19):  # 0 to 18
            x = ARENA_X + i * TILE_SIZE
            pygame.draw.line(screen, DARK_GRAY, (x, ARENA_Y), (x, ARENA_Y + ARENA_HEIGHT))
        for j in range(33):  # 0 to 32
            y = ARENA_Y + j * TILE_SIZE
            pygame.draw.line(screen, DARK_GRAY, (ARENA_X, y), (ARENA_X + ARENA_WIDTH, y))
        
        # Draw river
        river_y1 = ARENA_Y + 15 * TILE_SIZE
        river_y2 = ARENA_Y + 17 * TILE_SIZE
        river_rect = pygame.Rect(ARENA_X, river_y1, ARENA_WIDTH, river_y2 - river_y1)
        pygame.draw.rect(screen, BLUE, river_rect)
        
        # Draw blocked tiles as gray
        blocked_tiles = [(0, 14), (0, 17), (17, 14), (17, 17)]
        for tile_x, tile_y in blocked_tiles:
            if battle.arena.is_blocked_tile(tile_x, tile_y):
                screen_x = ARENA_X + tile_x * TILE_SIZE
                screen_y = ARENA_Y + tile_y * TILE_SIZE
                
                # Draw gray blocked tile
                blocked_rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(screen, GRAY, blocked_rect)
                pygame.draw.rect(screen, DARK_GRAY, blocked_rect, 2)
                
                print(f"Drawing blocked tile at screen position ({screen_x}, {screen_y}) for tile ({tile_x}, {tile_y})")
        
        # Draw labels
        font = pygame.font.Font(None, 24)
        title = font.render("Blocked Tiles Test - Gray squares should be visible", True, WHITE)
        screen.blit(title, (50, 10))
        
        info = font.render("ESC to exit", True, WHITE)
        screen.blit(info, (50, ARENA_Y + ARENA_HEIGHT + 10))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    main()