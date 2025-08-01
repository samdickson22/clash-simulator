#!/usr/bin/env python3
"""
Automatically take pathfinding debug screenshots at key moments
"""

import os
import pygame
import datetime
from src.clasher.engine import BattleEngine
from src.clasher.arena import Position

# Initialize pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)

class AutoDebugScreenshots:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Auto Debug Screenshots")
        
        self.font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 36)
        
        # Arena constants
        self.arena_width = 18
        self.arena_height = 32
        self.tile_size = 25
        self.arena_start_x = 50
        self.arena_start_y = 50
        
        # Create battle
        self.engine = BattleEngine()
        self.battle = self.engine.create_battle()
        self.setup_battle()
        
        # Create screenshots folder
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_folder = f"pathfinding_debug/{timestamp}"
        os.makedirs(self.screenshot_folder, exist_ok=True)
        print(f"📁 Screenshots will be saved to: {self.screenshot_folder}")
    
    def setup_battle(self):
        """Setup the battle with two knights"""
        self.battle.players[0].elixir = 10.0
        self.battle.players[1].elixir = 10.0
        
        # Deploy knights
        self.battle.deploy_card(0, 'Knight', Position(9, 12))
        self.battle.deploy_card(1, 'Knight', Position(9, 20))
        
        print("✅ Knights deployed at (9,12) and (9,20)")
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates"""
        screen_x = self.arena_start_x + world_x * self.tile_size + self.tile_size // 2
        screen_y = self.arena_start_y + world_y * self.tile_size + self.tile_size // 2
        return int(screen_x), int(screen_y)
    
    def draw_arena(self):
        """Draw the arena background"""
        # Arena bounds
        arena_rect = pygame.Rect(
            self.arena_start_x, 
            self.arena_start_y,
            self.arena_width * self.tile_size,
            self.arena_height * self.tile_size
        )
        pygame.draw.rect(self.screen, GRAY, arena_rect, 2)
        
        # River (y=15-16)
        river_y1 = self.arena_start_y + 15 * self.tile_size
        river_y2 = self.arena_start_y + 17 * self.tile_size
        river_rect = pygame.Rect(self.arena_start_x, river_y1, self.arena_width * self.tile_size, river_y2 - river_y1)
        pygame.draw.rect(self.screen, BLUE, river_rect)
        
        # Bridges
        bridge_width = 3 * self.tile_size
        bridge_height = 2 * self.tile_size
        
        # Left bridge (x=2-4, y=15-16)
        left_bridge = pygame.Rect(
            self.arena_start_x + 2 * self.tile_size, 
            river_y1, 
            bridge_width, 
            bridge_height
        )
        pygame.draw.rect(self.screen, GRAY, left_bridge)
        
        # Right bridge (x=14-16, y=15-16)
        right_bridge = pygame.Rect(
            self.arena_start_x + 14 * self.tile_size, 
            river_y1, 
            bridge_width, 
            bridge_height
        )
        pygame.draw.rect(self.screen, GRAY, right_bridge)
        
        # Bridge centers
        left_center_x, left_center_y = self.world_to_screen(3, 16)
        right_center_x, right_center_y = self.world_to_screen(15, 16)
        pygame.draw.circle(self.screen, YELLOW, (left_center_x, left_center_y), 8, 2)
        pygame.draw.circle(self.screen, YELLOW, (right_center_x, right_center_y), 8, 2)
    
    def draw_towers(self):
        """Draw towers"""
        # Tower positions from arena.py
        towers = [
            (3.5, 6.5, BLUE),   # BLUE_LEFT_TOWER
            (14.5, 6.5, BLUE),  # BLUE_RIGHT_TOWER  
            (9.0, 2.5, BLUE),   # BLUE_KING_TOWER
            (3.5, 25.5, RED),   # RED_LEFT_TOWER
            (14.5, 25.5, RED),  # RED_RIGHT_TOWER
            (9.0, 29.5, RED),   # RED_KING_TOWER
        ]
        
        for x, y, color in towers:
            screen_x, screen_y = self.world_to_screen(x, y)
            pygame.draw.rect(self.screen, color, (screen_x-10, screen_y-10, 20, 20))
            pygame.draw.rect(self.screen, BLACK, (screen_x-10, screen_y-10, 20, 20), 2)
    
    def draw_entities(self):
        """Draw entities with pathfinding debug info"""
        for entity in self.battle.entities.values():
            if not entity.is_alive:
                continue
                
            screen_x, screen_y = self.world_to_screen(entity.position.x, entity.position.y)
            
            # Draw entity
            color = BLUE if entity.player_id == 0 else RED
            pygame.draw.circle(self.screen, color, (screen_x, screen_y), 12)
            pygame.draw.circle(self.screen, BLACK, (screen_x, screen_y), 12, 2)
            
            # Draw sight range
            sight_radius = int(entity.sight_range * self.tile_size)
            pygame.draw.circle(self.screen, (*color[:3], 50), (screen_x, screen_y), sight_radius, 1)
            
            # Draw pathfinding debug info
            if hasattr(entity, '_get_pathfind_target') and hasattr(entity, 'target_id'):
                if entity.target_id:
                    target = self.battle.entities.get(entity.target_id)
                    if target:
                        # Get pathfind target
                        pathfind_target = entity._get_pathfind_target(target.position)
                        
                        # Draw pathfind target
                        pf_x, pf_y = self.world_to_screen(pathfind_target.x, pathfind_target.y)
                        pygame.draw.circle(self.screen, GREEN, (pf_x, pf_y), 8, 3)
                        
                        # Draw line to pathfind target
                        pygame.draw.line(self.screen, GREEN, (screen_x, screen_y), (pf_x, pf_y), 2)
                        
                        # Draw line to final target (dotted)
                        final_x, final_y = self.world_to_screen(target.position.x, target.position.y)
                        pygame.draw.line(self.screen, YELLOW, (screen_x, screen_y), (final_x, final_y), 1)
                        
                        # Debug text
                        current_side = 0 if entity.position.y < 16.0 else 1
                        target_side = 0 if target.position.y < 16.0 else 1
                        need_to_cross = current_side != target_side
                        distance_to_target = entity.position.distance_to(target.position)
                        on_bridge = (abs(entity.position.x - 3.0) <= 1.5 or abs(entity.position.x - 15.0) <= 1.5) and abs(entity.position.y - 16.0) <= 1.0
                        
                        debug_text = ""
                        if distance_to_target <= entity.sight_range:
                            debug_text = "DIRECT"
                        elif on_bridge:
                            debug_text = "TO_TOWER"  
                        elif need_to_cross:
                            debug_text = "TO_BRIDGE"
                        else:
                            debug_text = "DIRECT"
                            
                        text_surface = self.font.render(debug_text, True, GREEN)
                        self.screen.blit(text_surface, (screen_x + 15, screen_y - 10))
                        
                        # Target info
                        target_name = target.card_stats.name if target.card_stats else "Unknown"
                        target_text = self.font.render(f"→{target_name}", True, color)
                        self.screen.blit(target_text, (screen_x + 15, screen_y + 5))
    
    def draw_info(self, tick, step_info=""):
        """Draw battle info"""
        info_y = 20
        
        # Tick counter
        tick_text = self.large_font.render(f"Tick: {tick}", True, BLACK)
        self.screen.blit(tick_text, (SCREEN_WIDTH - 200, info_y))
        
        # Step info
        if step_info:
            step_text = self.font.render(step_info, True, BLACK)
            self.screen.blit(step_text, (SCREEN_WIDTH - 400, info_y + 40))
        
        # Knight positions and distances
        knights = []
        for entity in self.battle.entities.values():
            if (hasattr(entity, 'card_stats') and entity.card_stats and 
                entity.card_stats.name == 'Knight'):
                knights.append(entity)
        
        if len(knights) == 2:
            blue_knight = knights[0] if knights[0].player_id == 0 else knights[1]
            red_knight = knights[1] if knights[1].player_id == 1 else knights[0]
            
            distance = blue_knight.position.distance_to(red_knight.position)
            can_see = distance <= blue_knight.sight_range
            
            info_y += 80
            pos_text = self.font.render(f"Blue: ({blue_knight.position.x:.1f}, {blue_knight.position.y:.1f})", True, BLUE)
            self.screen.blit(pos_text, (SCREEN_WIDTH - 400, info_y))
            
            info_y += 25
            pos_text = self.font.render(f"Red:  ({red_knight.position.x:.1f}, {red_knight.position.y:.1f})", True, RED)
            self.screen.blit(pos_text, (SCREEN_WIDTH - 400, info_y))
            
            info_y += 25
            dist_text = self.font.render(f"Distance: {distance:.1f} ({'CAN SEE' if can_see else 'TOO FAR'})", True, GREEN if can_see else BLACK)
            self.screen.blit(dist_text, (SCREEN_WIDTH - 400, info_y))
    
    def take_screenshot(self, filename):
        """Take a screenshot"""
        pygame.image.save(self.screen, filename)
        print(f"📸 {filename}")
    
    def run_investigation(self):
        """Run the investigation with automatic screenshots"""
        print("🔍 Starting pathfinding investigation...")
        
        # Key moments to capture
        key_moments = [0, 10, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300]
        current_moment_idx = 0
        
        tick = 0
        while tick < 350 and current_moment_idx < len(key_moments):
            # Step battle
            self.battle.step(speed_factor=1.0)
            tick += 1
            
            # Check if this is a key moment
            should_screenshot = False
            step_info = ""
            
            if current_moment_idx < len(key_moments) and tick >= key_moments[current_moment_idx]:
                should_screenshot = True
                step_info = f"Key moment {current_moment_idx + 1}/{len(key_moments)}"
                current_moment_idx += 1
            
            # Also screenshot when knights start targeting each other
            knights = []
            for entity in self.battle.entities.values():
                if (hasattr(entity, 'card_stats') and entity.card_stats and 
                    entity.card_stats.name == 'Knight'):
                    knights.append(entity)
            
            if len(knights) == 2:
                distance = knights[0].position.distance_to(knights[1].position)
                if distance <= knights[0].sight_range:
                    target0 = knights[0].get_nearest_target(self.battle.entities)
                    target1 = knights[1].get_nearest_target(self.battle.entities)
                    
                    if (target0 and hasattr(target0, 'card_stats') and target0.card_stats and target0.card_stats.name == 'Knight' and
                        target1 and hasattr(target1, 'card_stats') and target1.card_stats and target1.card_stats.name == 'Knight'):
                        should_screenshot = True
                        step_info = f"Knights targeting each other! (distance: {distance:.1f})"
            
            if should_screenshot:
                # Draw everything
                self.screen.fill(WHITE)
                self.draw_arena()
                self.draw_towers()
                self.draw_entities()
                self.draw_info(tick, step_info)
                
                pygame.display.flip()
                
                # Take screenshot
                filename = f"{self.screenshot_folder}/tick_{tick:04d}_{step_info.replace(' ', '_')}.png"
                self.take_screenshot(filename)
        
        print(f"✅ Investigation complete! Screenshots saved to {self.screenshot_folder}")
        pygame.quit()
        return self.screenshot_folder

if __name__ == "__main__":
    debug = AutoDebugScreenshots()
    folder = debug.run_investigation()
    print(f"📁 All screenshots in: {folder}")