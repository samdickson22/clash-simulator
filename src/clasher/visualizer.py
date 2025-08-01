"""
Real-time Battle Visualizer for Clash Royale Engine

Provides live visualization of battles with:
- Arena grid and towers
- Troop movements and combat
- Health bars and elixir display
- Card hands and spell effects
"""

import pygame
import sys
from typing import Dict, Optional, Tuple
import math

from .battle import BattleState
from .entities import Entity, Troop, Building, Projectile
from .arena import Position


class BattleVisualizer:
    """Real-time battle visualizer using pygame"""
    
    def __init__(self, width: int = 1200, height: int = 800):
        pygame.init()
        
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Clash Royale Battle Engine")
        
        # Colors
        self.colors = {
            'background': (34, 139, 34),     # Forest green
            'river': (70, 130, 180),         # Steel blue
            'bridge': (139, 69, 19),         # Saddle brown
            'grid': (0, 100, 0),             # Dark green
            'tower_blue': (65, 105, 225),    # Royal blue
            'tower_red': (220, 20, 60),      # Crimson
            'troop_blue': (100, 149, 237),   # Cornflower blue
            'troop_red': (255, 99, 71),      # Tomato
            'spell': (255, 215, 0),          # Gold
            'projectile': (255, 140, 0),     # Dark orange
            'health_bar': (0, 255, 0),       # Green
            'health_bg': (255, 0, 0),        # Red
            'text': (255, 255, 255),         # White
            'ui_bg': (50, 50, 50),           # Dark gray
        }
        
        # Fonts
        self.font_small = pygame.font.Font(None, 20)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_large = pygame.font.Font(None, 36)
        
        # Layout
        self.arena_rect = pygame.Rect(50, 50, 800, 450)  # Main arena area
        self.ui_rect = pygame.Rect(870, 50, 300, 700)    # UI panel
        
        # Scale factors for 18x32 arena
        self.scale_x = self.arena_rect.width / 18   # 18 tiles wide
        self.scale_y = self.arena_rect.height / 32  # 32 tiles tall
        
        self.clock = pygame.time.Clock()
        self.running = True
    
    def world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        screen_x = self.arena_rect.x + (world_pos.x / 100.0) * self.scale_x
        screen_y = self.arena_rect.y + (world_pos.y / 100.0) * self.scale_y
        return int(screen_x), int(screen_y)
    
    def draw_arena(self):
        """Draw the arena background and grid"""
        # Background
        pygame.draw.rect(self.screen, self.colors['background'], self.arena_rect)
        
        # River (horizontal line at y=16)
        river_y = self.arena_rect.y + 16 * self.scale_y
        pygame.draw.rect(self.screen, self.colors['river'], 
                        (self.arena_rect.x, river_y - 10, self.arena_rect.width, 20))
        
        # Bridges
        bridge_width = 3 * self.scale_x
        bridge_height = 20
        
        # Left bridge (x=4)
        left_bridge_x = self.arena_rect.x + 4 * self.scale_x - bridge_width//2
        pygame.draw.rect(self.screen, self.colors['bridge'],
                        (left_bridge_x, river_y - bridge_height//2, bridge_width, bridge_height))
        
        # Right bridge (x=14) 
        right_bridge_x = self.arena_rect.x + 14 * self.scale_x - bridge_width//2
        pygame.draw.rect(self.screen, self.colors['bridge'],
                        (right_bridge_x, river_y - bridge_height//2, bridge_width, bridge_height))
        
        # Grid lines (optional) - for 18x32 arena
        for x in range(0, 19, 3):  # 18 tiles wide
            line_x = self.arena_rect.x + x * self.scale_x
            pygame.draw.line(self.screen, self.colors['grid'], 
                           (line_x, self.arena_rect.y), 
                           (line_x, self.arena_rect.bottom), 1)
        
        for y in range(0, 33, 4):  # 32 tiles tall
            line_y = self.arena_rect.y + y * self.scale_y
            pygame.draw.line(self.screen, self.colors['grid'],
                           (self.arena_rect.x, line_y),
                           (self.arena_rect.right, line_y), 1)
    
    def draw_entity(self, entity: Entity):
        """Draw an entity on the arena"""
        screen_x, screen_y = self.world_to_screen(entity.position)
        
        # Determine color and size based on entity type
        if isinstance(entity, Building):
            color = self.colors['tower_blue'] if entity.player_id == 0 else self.colors['tower_red']
            size = 20 if "King" in entity.card_stats.name else 15
            pygame.draw.rect(self.screen, color, 
                           (screen_x - size//2, screen_y - size//2, size, size))
        
        elif isinstance(entity, Troop):
            color = self.colors['troop_blue'] if entity.player_id == 0 else self.colors['troop_red']
            size = 8
            pygame.draw.circle(self.screen, color, (screen_x, screen_y), size)
        
        elif isinstance(entity, Projectile):
            pygame.draw.circle(self.screen, self.colors['projectile'], (screen_x, screen_y), 4)
        
        # Health bar
        if entity.is_alive and entity.max_hitpoints > 0:
            bar_width = 20
            bar_height = 4
            health_pct = entity.hitpoints / entity.max_hitpoints
            
            # Background (red)
            bar_rect = (screen_x - bar_width//2, screen_y - 15, bar_width, bar_height)
            pygame.draw.rect(self.screen, self.colors['health_bg'], bar_rect)
            
            # Health (green)
            health_width = int(bar_width * health_pct)
            if health_width > 0:
                health_rect = (screen_x - bar_width//2, screen_y - 15, health_width, bar_height)
                pygame.draw.rect(self.screen, self.colors['health_bar'], health_rect)
        
        # Entity name
        if hasattr(entity, 'card_stats') and entity.card_stats.name:
            name = entity.card_stats.name
            if len(name) > 8:
                name = name[:8] + "..."
            text = self.font_small.render(name, True, self.colors['text'])
            text_rect = text.get_rect(center=(screen_x, screen_y + 25))
            self.screen.blit(text, text_rect)
    
    def draw_ui(self, battle_state: BattleState):
        """Draw the UI panel"""
        # Background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.ui_rect)
        
        y_offset = self.ui_rect.y + 20
        
        # Battle info
        time_text = f"Time: {battle_state.time:.1f}s"
        tick_text = f"Tick: {battle_state.tick}"
        entities_text = f"Entities: {len(battle_state.entities)}"
        
        for text in [time_text, tick_text, entities_text]:
            surface = self.font_medium.render(text, True, self.colors['text'])
            self.screen.blit(surface, (self.ui_rect.x + 10, y_offset))
            y_offset += 30
        
        y_offset += 20
        
        # Player info
        for i, player in enumerate(battle_state.players):
            player_color = self.colors['troop_blue'] if i == 0 else self.colors['troop_red']
            
            # Player header
            player_text = f"Player {i}"
            surface = self.font_large.render(player_text, True, player_color)
            self.screen.blit(surface, (self.ui_rect.x + 10, y_offset))
            y_offset += 35
            
            # Elixir
            elixir_text = f"Elixir: {player.elixir:.1f}/10"
            surface = self.font_medium.render(elixir_text, True, self.colors['text'])
            self.screen.blit(surface, (self.ui_rect.x + 20, y_offset))
            y_offset += 25
            
            # Elixir bar
            bar_width = 200
            bar_height = 15
            elixir_pct = min(player.elixir / 10.0, 1.0)
            
            # Background
            bar_rect = (self.ui_rect.x + 20, y_offset, bar_width, bar_height)
            pygame.draw.rect(self.screen, self.colors['health_bg'], bar_rect)
            
            # Elixir
            elixir_width = int(bar_width * elixir_pct)
            if elixir_width > 0:
                elixir_rect = (self.ui_rect.x + 20, y_offset, elixir_width, bar_height)
                pygame.draw.rect(self.screen, (148, 0, 211), elixir_rect)  # Purple
            
            y_offset += 30
            
            # Tower HP
            king_text = f"King: {player.king_tower_hp:.0f}"
            left_text = f"Left: {player.left_tower_hp:.0f}"  
            right_text = f"Right: {player.right_tower_hp:.0f}"
            crowns_text = f"Crowns: {player.get_crown_count()}"
            
            for text in [king_text, left_text, right_text, crowns_text]:
                surface = self.font_small.render(text, True, self.colors['text'])
                self.screen.blit(surface, (self.ui_rect.x + 20, y_offset))
                y_offset += 22
            
            # Hand
            hand_text = "Hand:"
            surface = self.font_medium.render(hand_text, True, self.colors['text'])
            self.screen.blit(surface, (self.ui_rect.x + 20, y_offset))
            y_offset += 25
            
            for j, card in enumerate(player.hand):
                card_text = f"{j}: {card}"
                surface = self.font_small.render(card_text, True, self.colors['text'])
                self.screen.blit(surface, (self.ui_rect.x + 30, y_offset))
                y_offset += 20
            
            y_offset += 30
        
        # Game state
        if battle_state.double_elixir:
            mode_text = "2x Elixir" if not battle_state.triple_elixir else "3x Elixir"
            surface = self.font_medium.render(mode_text, True, (255, 215, 0))
            self.screen.blit(surface, (self.ui_rect.x + 10, y_offset))
            y_offset += 30
        
        if battle_state.overtime:
            overtime_text = "OVERTIME"
            surface = self.font_large.render(overtime_text, True, (255, 0, 0))
            self.screen.blit(surface, (self.ui_rect.x + 10, y_offset))
            y_offset += 40
        
        if battle_state.game_over:
            if battle_state.winner is not None:
                winner_text = f"Player {battle_state.winner} WINS!"
                color = self.colors['troop_blue'] if battle_state.winner == 0 else self.colors['troop_red']
            else:
                winner_text = "DRAW!"
                color = self.colors['text']
            
            surface = self.font_large.render(winner_text, True, color)
            self.screen.blit(surface, (self.ui_rect.x + 10, y_offset))
    
    def handle_events(self) -> bool:
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_SPACE:
                    # Pause/unpause (could be implemented)
                    pass
        return True
    
    def render(self, battle_state: BattleState):
        """Render the complete battle state"""
        # Clear screen
        self.screen.fill((0, 0, 0))
        
        # Draw components
        self.draw_arena()
        
        # Draw all entities
        for entity in battle_state.entities.values():
            if entity.is_alive:
                self.draw_entity(entity)
        
        self.draw_ui(battle_state)
        
        # Instructions
        instructions = [
            "ESC: Quit",
            "SPACE: Pause",
            "",
            "Towers: Squares",
            "Troops: Circles", 
            "Blue: Player 0",
            "Red: Player 1"
        ]
        
        y_pos = self.height - 180
        for instruction in instructions:
            surface = self.font_small.render(instruction, True, self.colors['text'])
            self.screen.blit(surface, (self.ui_rect.x + 10, y_pos))
            y_pos += 20
        
        # Update display
        pygame.display.flip()
        return self.handle_events()
    
    def close(self):
        """Clean up and close visualizer"""
        pygame.quit()
        self.running = False