#!/usr/bin/env python3

import pygame
import sys
import random
import time
import math
sys.path.append('src')

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.data import CardDataLoader

# Initialize pygame
pygame.init()

# Screen dimensions
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
ARENA_WIDTH = 600
ARENA_HEIGHT = 800
ARENA_X = 50
ARENA_Y = 50

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 100, 100)
BLUE = (100, 100, 255)
GREEN = (100, 255, 100)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
YELLOW = (255, 255, 100)
PURPLE = (255, 100, 255)
CYAN = (100, 255, 255)
BROWN = (139, 69, 19)
LIGHT_BLUE = (173, 216, 230)

class RandomSimulator:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Clash Royale - Random Battle Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        
        # Battle setup
        self.battle = BattleState()
        self.card_loader = CardDataLoader()
        self.cards = self.card_loader.load_cards()
        
        # Simulation settings
        self.tile_size = ARENA_HEIGHT // 32  # 32 tiles tall
        self.running = True
        self.paused = False
        self.game_time = 0.0
        self.last_deploy_time = [0.0, 0.0]  # Per player
        self.deploy_cooldown = 3.0  # Seconds between random deployments
        self.battle_steps = 0
        
        # Available troop cards for random deployment
        self.available_troops = [
            'Knight', 'Archer', 'Barbarians', 'Giant', 'Pekka', 
            'Goblins', 'Minions', 'Skeleton Army', 'Valkyrie'
        ]
        
        print(f"🎮 Random Battle Simulator Started!")
        print(f"📋 Available troops: {', '.join(self.available_troops)}")
        print(f"⚡ Deploy cooldown: {self.deploy_cooldown}s per player")
        print(f"🎯 Controls: SPACE = pause/unpause, ESC = quit")

    def get_random_deploy_position(self, player_id: int) -> Position:
        """Get a random valid deployment position for a player"""
        if player_id == 0:  # Blue player (bottom)
            x = random.uniform(1, 17)
            y = random.uniform(8, 14.5)  # Bottom half, before river
        else:  # Red player (top)
            x = random.uniform(1, 17)
            y = random.uniform(17.5, 24)  # Top half, after river
        
        return Position(x, y)

    def should_deploy_troop(self, player_id: int) -> bool:
        """Check if it's time to deploy a random troop for this player"""
        time_since_last = self.game_time - self.last_deploy_time[player_id]
        
        # Random deployment with some probability
        if time_since_last >= self.deploy_cooldown and random.random() < 0.8:
            return True
        return False

    def deploy_random_troop(self, player_id: int):
        """Deploy a random troop for the specified player"""
        # Choose random troop
        troop_name = random.choice(self.available_troops)
        
        # Get random position
        position = self.get_random_deploy_position(player_id)
        
        # Deploy
        success = self.battle.deploy_card(player_id, troop_name, position)
        if success:
            player_name = "Blue" if player_id == 0 else "Red"
            print(f"⚔️  {player_name} deployed {troop_name} at ({position.x:.1f}, {position.y:.1f})")
            self.last_deploy_time[player_id] = self.game_time
            
            # Add some cooldown variation
            self.deploy_cooldown = random.uniform(1.5, 3.5)

    def world_to_screen(self, x: float, y: float) -> tuple:
        """Convert world coordinates to screen coordinates"""
        screen_x = int(ARENA_X + x * self.tile_size)
        screen_y = int(ARENA_Y + y * self.tile_size)
        return screen_x, screen_y

    def draw_arena(self):
        """Draw the arena background with correct Clash Royale dimensions"""
        # Arena background
        arena_rect = pygame.Rect(ARENA_X, ARENA_Y, ARENA_WIDTH, ARENA_HEIGHT)
        pygame.draw.rect(self.screen, GREEN, arena_rect)
        pygame.draw.rect(self.screen, BLACK, arena_rect, 2)
        
        # River is 2 tiles tall, centered at y=15-16 (middle of 32-tile arena)
        river_y1 = ARENA_Y + 15 * self.tile_size
        river_y2 = ARENA_Y + 17 * self.tile_size
        river_rect = pygame.Rect(ARENA_X, river_y1, ARENA_WIDTH, river_y2 - river_y1)
        pygame.draw.rect(self.screen, CYAN, river_rect)
        pygame.draw.rect(self.screen, (0, 150, 200), river_rect, 2)
        
        # Bridges are 3 tiles wide
        bridge_width = 3 * self.tile_size
        bridge_height = river_y2 - river_y1
        
        # Left bridge at x=2,3,4 (3 tiles wide, centered at x=3)
        left_bridge_x = ARENA_X + 2 * self.tile_size
        left_bridge_rect = pygame.Rect(left_bridge_x, river_y1, bridge_width, bridge_height)
        pygame.draw.rect(self.screen, DARK_GRAY, left_bridge_rect)
        pygame.draw.rect(self.screen, BLACK, left_bridge_rect, 2)
        
        # Right bridge at x=14,15,16 (3 tiles wide, centered at x=15)
        right_bridge_x = ARENA_X + 14 * self.tile_size
        right_bridge_rect = pygame.Rect(right_bridge_x, river_y1, bridge_width, bridge_height)
        pygame.draw.rect(self.screen, DARK_GRAY, right_bridge_rect)
        pygame.draw.rect(self.screen, BLACK, right_bridge_rect, 2)
        
        # Mark unplayable areas (outer tiles on top/bottom rows)
        # Top row: only middle 6 tiles (x=6-11) are playable
        for x in range(18):
            if x < 6 or x > 11:  # Unplayable tiles
                unplay_rect = pygame.Rect(ARENA_X + x * self.tile_size, ARENA_Y, 
                                        self.tile_size, self.tile_size)
                pygame.draw.rect(self.screen, (180, 180, 180), unplay_rect)
                pygame.draw.rect(self.screen, DARK_GRAY, unplay_rect, 1)
        
        # Bottom row: only middle 6 tiles (x=6-11) are playable  
        for x in range(18):
            if x < 6 or x > 11:  # Unplayable tiles
                unplay_rect = pygame.Rect(ARENA_X + x * self.tile_size, 
                                        ARENA_Y + 31 * self.tile_size,
                                        self.tile_size, self.tile_size)
                pygame.draw.rect(self.screen, (180, 180, 180), unplay_rect)
                pygame.draw.rect(self.screen, DARK_GRAY, unplay_rect, 1)
        
        # Draw square tile grid
        for x in range(19):  # 0-18 vertical lines for 18 columns
            line_x = ARENA_X + x * self.tile_size
            pygame.draw.line(self.screen, (0, 150, 0), 
                           (line_x, ARENA_Y), (line_x, ARENA_Y + ARENA_HEIGHT), 1)
        
        for y in range(33):  # 0-32 horizontal lines for 32 rows
            line_y = ARENA_Y + y * self.tile_size
            pygame.draw.line(self.screen, (0, 150, 0), 
                           (ARENA_X, line_y), (ARENA_X + ARENA_WIDTH, line_y), 1)

    def draw_entities(self):
        """Draw all entities in the battle"""
        for entity in self.battle.entities.values():
            screen_x, screen_y = self.world_to_screen(entity.position.x, entity.position.y)
            
            # Entity color based on player
            if entity.player_id == 0:
                color = BLUE
            else:
                color = RED
            
            # Draw entity
            pygame.draw.circle(self.screen, color, (screen_x, screen_y), 12)
            pygame.draw.circle(self.screen, BLACK, (screen_x, screen_y), 12, 2)
            
            # Draw entity name
            if hasattr(entity, 'card_stats') and entity.card_stats:
                name = entity.card_stats.name[:3]  # Abbreviate
            else:
                name = "Bld"  # Building
            
            name_text = self.small_font.render(name, True, BLACK)
            name_rect = name_text.get_rect(center=(screen_x, screen_y))
            self.screen.blit(name_text, name_rect)
            
            # Draw health bar
            if hasattr(entity, 'hitpoints') and hasattr(entity, 'max_hitpoints'):
                health_ratio = entity.hitpoints / entity.max_hitpoints
                bar_width = 24
                bar_height = 4
                bar_x = screen_x - bar_width // 2
                bar_y = screen_y - 20
                
                # Background
                pygame.draw.rect(self.screen, BLACK, (bar_x-1, bar_y-1, bar_width+2, bar_height+2))
                # Health bar
                health_color = GREEN if health_ratio > 0.6 else YELLOW if health_ratio > 0.3 else RED
                pygame.draw.rect(self.screen, health_color, (bar_x, bar_y, int(bar_width * health_ratio), bar_height))
            
            # Draw targeting lines
            if hasattr(entity, 'target_id') and entity.target_id:
                target = self.battle.entities.get(entity.target_id)
                if target:
                    target_x, target_y = self.world_to_screen(target.position.x, target.position.y)
                    
                    # Thin yellow line to final target
                    pygame.draw.line(self.screen, YELLOW, (screen_x, screen_y), (target_x, target_y), 1)
                    
                    # Thick red pathfinding line
                    if hasattr(entity, '_get_pathfind_target'):
                        pathfind_target = entity._get_pathfind_target(target)
                        pf_x, pf_y = self.world_to_screen(pathfind_target.x, pathfind_target.y)
                        pygame.draw.line(self.screen, RED, (screen_x, screen_y), (pf_x, pf_y), 3)
                        # Circle at pathfind target
                        pygame.draw.circle(self.screen, RED, (pf_x, pf_y), 6, 2)

    def draw_ui(self):
        """Draw UI information"""
        ui_x = ARENA_X + ARENA_WIDTH + 20
        ui_y = ARENA_Y + 20
        line_height = 25
        
        # Time info
        time_text = self.font.render(f"Time: {self.game_time:.1f}s", True, BLACK)
        self.screen.blit(time_text, (ui_x, ui_y))
        ui_y += line_height
        
        # Pause status
        if self.paused:
            pause_text = self.font.render("PAUSED", True, RED)
            self.screen.blit(pause_text, (ui_x, ui_y))
        ui_y += line_height * 2
        
        # Entity counts
        blue_count = sum(1 for e in self.battle.entities.values() if e.player_id == 0)
        red_count = sum(1 for e in self.battle.entities.values() if e.player_id == 1)
        
        count_text = self.font.render(f"Blue Units: {blue_count}", True, BLUE)
        self.screen.blit(count_text, (ui_x, ui_y))
        ui_y += line_height
        
        count_text = self.font.render(f"Red Units: {red_count}", True, RED)
        self.screen.blit(count_text, (ui_x, ui_y))
        ui_y += line_height * 2
        
        # Next deployment timers
        for player_id in [0, 1]:
            time_until_next = max(0, self.deploy_cooldown - (self.game_time - self.last_deploy_time[player_id]))
            player_name = "Blue" if player_id == 0 else "Red"
            color = BLUE if player_id == 0 else RED
            
            timer_text = self.font.render(f"{player_name} deploys in: {time_until_next:.1f}s", True, color)
            self.screen.blit(timer_text, (ui_x, ui_y))
            ui_y += line_height
        
        ui_y += line_height
        
        # Controls
        controls = [
            "Controls:",
            "SPACE - Pause/Unpause", 
            "ESC - Quit",
            "",
            "Available Troops:",
        ]
        
        for line in controls:
            control_text = self.small_font.render(line, True, BLACK)
            self.screen.blit(control_text, (ui_x, ui_y))
            ui_y += 20
        
        # List available troops
        for i, troop in enumerate(self.available_troops):
            if i % 2 == 0 and i > 0:
                ui_y += 18
            troop_text = self.small_font.render(f"• {troop}", True, DARK_GRAY)
            self.screen.blit(troop_text, (ui_x + (i % 2) * 120, ui_y))
            if i % 2 == 1:
                ui_y += 18

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                    print(f"🎮 {'Paused' if self.paused else 'Resumed'}")

    def update(self, dt: float):
        """Update simulation"""
        if self.paused:
            return
            
        self.game_time += dt
        
        # Update battle (battle uses fixed 33ms timesteps)
        self.battle.step()
        
        # Random troop deployments
        for player_id in [0, 1]:
            if self.should_deploy_troop(player_id):
                self.deploy_random_troop(player_id)

    def run(self):
        """Main simulation loop"""
        while self.running:
            dt = self.clock.tick(60) / 1000.0  # 60 FPS, dt in seconds
            
            self.handle_events()
            self.update(dt)
            
            # Draw everything
            self.screen.fill(WHITE)
            self.draw_arena()
            self.draw_entities()
            self.draw_ui()
            
            pygame.display.flip()
        
        pygame.quit()
        print("🛑 Simulation ended")

if __name__ == "__main__":
    simulator = RandomSimulator()
    simulator.run()