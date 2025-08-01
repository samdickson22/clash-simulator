"""
Enhanced Clash Royale Visualizer

More authentic visual representation matching the real game:
- Proper tower positioning and appearance
- Realistic arena colors and textures
- Better bridge and river visualization
- Crown display and UI elements
"""

import pygame
import sys
import math
from typing import Dict, Optional, Tuple

from .battle import BattleState
from .entities import Entity, Troop, Building, Projectile
from .arena import Position


class EnhancedBattleVisualizer:
    """Enhanced visualizer matching real Clash Royale appearance"""
    
    def __init__(self, width: int = 900, height: int = 800):
        pygame.init()
        
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Clash Royale Battle Engine - Enhanced")
        
        # Authentic Clash Royale colors
        self.colors = {
            'grass': (88, 142, 47),          # Arena grass
            'grass_dark': (76, 122, 40),     # Darker grass areas
            'river': (41, 128, 185),         # River blue
            'bridge': (165, 118, 76),        # Wooden bridge
            'bridge_dark': (140, 100, 65),   # Bridge shadows
            'tower_blue': (52, 152, 219),    # Blue player towers
            'tower_red': (231, 76, 60),      # Red player towers
            'tower_neutral': (149, 165, 166), # Neutral tower color
            'crown': (241, 196, 15),         # Crown/level indicators
            'health_full': (46, 204, 113),   # Full health
            'health_medium': (241, 196, 15), # Medium health
            'health_low': (231, 76, 60),     # Low health
            'elixir': (155, 89, 182),        # Elixir purple
            'text': (255, 255, 255),         # White text
            'text_dark': (44, 62, 80),       # Dark text
            'ui_bg': (52, 73, 94),           # UI background
            'card_bg': (236, 240, 241),      # Card background
            'outline': (44, 62, 80),         # Outlines
        }
        
        # Fonts
        self.font_small = pygame.font.Font(None, 18)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 32)
        self.font_title = pygame.font.Font(None, 40)
        
        # Layout - Square tiles (1:1 ratio)
        tile_size = 20  # Each tile is 20x20 pixels (perfect squares)
        arena_width = 18 * tile_size   # 18 * 20 = 360 pixels wide
        arena_height = 32 * tile_size  # 32 * 20 = 640 pixels tall
        self.arena_rect = pygame.Rect(50, 30, arena_width, arena_height)
        self.ui_rect = pygame.Rect(430, 30, 400, 700)     # UI panel to the right
        
        # Scale factors - now each tile is perfectly square
        self.scale_x = tile_size   # 20 pixels per tile (width)
        self.scale_y = tile_size   # 20 pixels per tile (height)
        
        # Card display area (moved down to accommodate taller arena)
        self.card_rect = pygame.Rect(50, 680, 360, 80)
        
        self.clock = pygame.time.Clock()
        self.running = True
    
    def world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        # Entities use tile coordinates (0-18, 0-32)
        # Convert directly using square tile size
        screen_x = self.arena_rect.x + world_pos.x * self.scale_x
        screen_y = self.arena_rect.y + world_pos.y * self.scale_y
        return int(screen_x), int(screen_y)
    
    def draw_arena_background(self, battle_state=None):
        """Draw the authentic-looking arena with deployment zone tints"""
        # Main grass background
        pygame.draw.rect(self.screen, self.colors['grass'], self.arena_rect)
        
        # Add subtle checkerboard texture pattern first
        tile_size = int(self.scale_x)  # 20 pixels
        for i in range(0, self.arena_rect.width, tile_size):
            for j in range(0, self.arena_rect.height, tile_size):
                # Create subtle checkerboard pattern
                tile_x = i // tile_size
                tile_y = j // tile_size
                if (tile_x + tile_y) % 2 == 0:
                    texture_rect = pygame.Rect(
                        self.arena_rect.x + i, 
                        self.arena_rect.y + j, 
                        tile_size, tile_size
                    )
                    # Make checkerboard subtle
                    grass_dark = (*self.colors['grass_dark'], 64)  # More transparent
                    s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                    s.fill(grass_dark)
                    self.screen.blit(s, texture_rect)
                    
        # Add deployment zone tints on top of checkerboard
        if battle_state:
            self.draw_deployment_zones(battle_state)
        
        # River (horizontal across middle)
        river_y = self.arena_rect.y + self.arena_rect.height // 2
        river_height = 30
        river_rect = pygame.Rect(
            self.arena_rect.x, 
            river_y - river_height//2, 
            self.arena_rect.width, 
            river_height
        )
        pygame.draw.rect(self.screen, self.colors['river'], river_rect)
        
        # River banks (darker edges)
        pygame.draw.rect(self.screen, self.colors['bridge_dark'], 
                        (river_rect.x, river_rect.y, river_rect.width, 3))
        pygame.draw.rect(self.screen, self.colors['bridge_dark'], 
                        (river_rect.x, river_rect.bottom-3, river_rect.width, 3))
        
        # Left bridge
        bridge_width = 80
        bridge_x = self.arena_rect.x + self.arena_rect.width * 0.25 - bridge_width//2
        left_bridge = pygame.Rect(bridge_x, river_y - river_height//2, bridge_width, river_height)
        pygame.draw.rect(self.screen, self.colors['bridge'], left_bridge)
        pygame.draw.rect(self.screen, self.colors['bridge_dark'], left_bridge, 2)
        
        # Right bridge  
        bridge_x = self.arena_rect.x + self.arena_rect.width * 0.69 - bridge_width//2
        right_bridge = pygame.Rect(bridge_x, river_y - river_height//2, bridge_width, river_height)
        pygame.draw.rect(self.screen, self.colors['bridge'], right_bridge)
        pygame.draw.rect(self.screen, self.colors['bridge_dark'], right_bridge, 2)
        
        # Arena border
        pygame.draw.rect(self.screen, self.colors['outline'], self.arena_rect, 3)
    
    def draw_deployment_zones(self, battle_state):
        """Draw colored tints for deployment zones"""
        tile_size = int(self.scale_x)  # 20 pixels per tile
        
        # Get deployment zones for both players
        blue_zones = battle_state.arena.get_deploy_zones(0, battle_state)
        red_zones = battle_state.arena.get_deploy_zones(1, battle_state)
        
        # Create a grid to track which tiles belong to which player
        arena_width_tiles = 18
        arena_height_tiles = 32
        tile_ownership = {}  # (x, y) -> set of player_ids
        
        # Mark blue zones (excluding blocked tiles)
        for x1, y1, x2, y2 in blue_zones:
            for x in range(int(x1), int(x2)):
                for y in range(int(y1), int(y2)):
                    # Skip blocked tiles entirely - don't add them to tile_ownership
                    if battle_state.arena.is_blocked_tile(x, y):
                        continue
                    if (x, y) not in tile_ownership:
                        tile_ownership[(x, y)] = set()
                    tile_ownership[(x, y)].add(0)  # Blue player
        
        # Mark red zones (excluding blocked tiles)
        for x1, y1, x2, y2 in red_zones:
            for x in range(int(x1), int(x2)):
                for y in range(int(y1), int(y2)):
                    # Skip blocked tiles entirely - don't add them to tile_ownership
                    if battle_state.arena.is_blocked_tile(x, y):
                        continue
                    if (x, y) not in tile_ownership:
                        tile_ownership[(x, y)] = set()
                    tile_ownership[(x, y)].add(1)  # Red player
        
        # Draw tints based on ownership
        for (tile_x, tile_y), owners in tile_ownership.items():
            # Skip blocked tiles - they will be drawn gray instead
            if battle_state.arena.is_blocked_tile(tile_x, tile_y):
                continue
                
            # Skip if both players can deploy (no tint)
            if len(owners) > 1:
                continue
                
            # Determine tint color
            if 0 in owners:  # Blue only
                tint_color = (52, 152, 219, 80)  # More visible blue tint
            elif 1 in owners:  # Red only
                tint_color = (231, 76, 60, 80)   # More visible red tint
            else:
                continue
            
            # Draw the tint
            screen_x = self.arena_rect.x + tile_x * tile_size
            screen_y = self.arena_rect.y + tile_y * tile_size
            
            tint_rect = pygame.Rect(screen_x, screen_y, tile_size, tile_size)
            s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            s.fill(tint_color)
            self.screen.blit(s, tint_rect)
        
        # Draw blocked tiles in gray (no red/blue tints)
        for tile_x in range(arena_width_tiles):
            for tile_y in range(arena_height_tiles):
                if battle_state.arena.is_blocked_tile(tile_x, tile_y):
                    screen_x = self.arena_rect.x + tile_x * tile_size
                    screen_y = self.arena_rect.y + tile_y * tile_size
                    
                    # Draw gray blocked tile
                    blocked_rect = pygame.Rect(screen_x, screen_y, tile_size, tile_size)
                    s = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                    s.fill((128, 128, 128, 160))  # Semi-transparent gray
                    self.screen.blit(s, blocked_rect)
                    
                    # Add darker border to make it more visible
                    pygame.draw.rect(self.screen, (64, 64, 64), blocked_rect, 1)
    
    def draw_tower(self, entity: Building):
        """Draw towers with authentic appearance"""
        screen_x, screen_y = self.world_to_screen(entity.position)
        
        # Determine tower type and color
        is_king = "King" in entity.card_stats.name
        color = self.colors['tower_blue'] if entity.player_id == 0 else self.colors['tower_red']
        
        # Tower size based on exact hitbox data from hitboxes.json
        # King's Tower: 1.4 tile radius, Princess Tower: 1.0 tile radius
        if is_king:
            radius_tiles = 1.4
        else:
            radius_tiles = 1.0
        
        # Convert tile radius to screen pixels
        size = int(radius_tiles * 2 * self.scale_x)  # diameter in pixels
        
        # Tower base (square)
        tower_rect = pygame.Rect(
            screen_x - size//2, 
            screen_y - size//2, 
            size, size
        )
        pygame.draw.rect(self.screen, color, tower_rect)
        pygame.draw.rect(self.screen, self.colors['outline'], tower_rect, 2)
        
        # Tower crown/top
        crown_size = size // 3
        crown_rect = pygame.Rect(
            screen_x - crown_size//2,
            screen_y - size//2 - crown_size//2,
            crown_size, crown_size
        )
        pygame.draw.rect(self.screen, self.colors['crown'], crown_rect)
        pygame.draw.rect(self.screen, self.colors['outline'], crown_rect, 1)
        
        # Health bar above tower
        self.draw_health_bar(entity, screen_x, screen_y - size//2 - 15, 40)
        
        # Tower level indicator
        level_text = "12" if is_king else "11"  # Common tower levels
        level_surface = self.font_small.render(level_text, True, self.colors['text'])
        level_rect = level_surface.get_rect(center=(screen_x, screen_y + size//2 + 10))
        
        # Level background
        bg_rect = pygame.Rect(level_rect.x - 2, level_rect.y - 1, level_rect.width + 4, level_rect.height + 2)
        pygame.draw.rect(self.screen, self.colors['crown'], bg_rect)
        pygame.draw.rect(self.screen, self.colors['outline'], bg_rect, 1)
        
        self.screen.blit(level_surface, level_rect)
    
    def draw_troop(self, entity: Troop):
        """Draw troops with better appearance"""
        screen_x, screen_y = self.world_to_screen(entity.position)
        
        # Troop color based on player
        color = self.colors['tower_blue'] if entity.player_id == 0 else self.colors['tower_red']
        
        # Troop size based on exact hitbox data from hitboxes.json
        hitbox_sizes = {
            "Knight": 0.5, "Archers": 0.5, "Giant": 0.75, "Wizard": 0.5,
            "Musketeer": 0.5, "Mini P.E.K.K.A.": 0.45, "P.E.K.K.A.": 0.75,
            "Golem": 0.75, "Valkyrie": 0.5, "Hog Rider": 0.6
        }
        
        # Get hitbox radius for this troop (default to 0.5 if not found)
        radius_tiles = hitbox_sizes.get(entity.card_stats.name, 0.5)
        
        # Convert tile radius to screen pixels
        size = int(radius_tiles * self.scale_x)
        
        # Draw troop as circle with outline
        pygame.draw.circle(self.screen, color, (screen_x, screen_y), size)
        pygame.draw.circle(self.screen, self.colors['outline'], (screen_x, screen_y), size, 2)
        
        # Health bar above troop
        self.draw_health_bar(entity, screen_x, screen_y - size - 8, 24)
        
        # Troop name below
        name = entity.card_stats.name
        if len(name) > 8:
            name = name[:8]
        text = self.font_small.render(name, True, self.colors['text'])
        text_rect = text.get_rect(center=(screen_x, screen_y + size + 12))
        
        # Text background for readability
        bg_rect = pygame.Rect(text_rect.x - 2, text_rect.y, text_rect.width + 4, text_rect.height)
        pygame.draw.rect(self.screen, (0, 0, 0, 128), bg_rect)
        
        self.screen.blit(text, text_rect)
    
    def draw_health_bar(self, entity: Entity, x: int, y: int, width: int):
        """Draw health bar with authentic colors"""
        if entity.max_hitpoints <= 0:
            return
        
        health_pct = entity.hitpoints / entity.max_hitpoints
        height = 6
        
        # Background (dark)
        bg_rect = pygame.Rect(x - width//2, y, width, height)
        pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect)
        
        # Health color based on percentage
        if health_pct > 0.6:
            health_color = self.colors['health_full']
        elif health_pct > 0.3:
            health_color = self.colors['health_medium']
        else:
            health_color = self.colors['health_low']
        
        # Health bar
        health_width = int(width * health_pct)
        if health_width > 0:
            health_rect = pygame.Rect(x - width//2, y, health_width, height)
            pygame.draw.rect(self.screen, health_color, health_rect)
        
        # Health bar outline
        pygame.draw.rect(self.screen, self.colors['outline'], bg_rect, 1)
    
    def draw_enhanced_ui(self, battle_state: BattleState):
        """Draw enhanced UI panel"""
        # UI background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.ui_rect)
        pygame.draw.rect(self.screen, self.colors['outline'], self.ui_rect, 2)
        
        y_pos = self.ui_rect.y + 20
        
        # Battle timer (like in game)
        time_text = f"{int(battle_state.time // 60)}:{int(battle_state.time % 60):02d}"
        time_surface = self.font_title.render(time_text, True, self.colors['text'])
        time_rect = time_surface.get_rect(centerx=self.ui_rect.centerx)
        time_rect.y = y_pos
        
        # Timer background
        timer_bg = pygame.Rect(time_rect.x - 10, time_rect.y - 5, time_rect.width + 20, time_rect.height + 10)
        pygame.draw.rect(self.screen, (0, 0, 0, 200), timer_bg)
        pygame.draw.rect(self.screen, self.colors['outline'], timer_bg, 2)
        
        self.screen.blit(time_surface, time_rect)
        y_pos += 60
        
        # Player sections
        for i, player in enumerate(battle_state.players):
            player_color = self.colors['tower_blue'] if i == 0 else self.colors['tower_red']
            
            # Player header with crown count
            crowns = player.get_crown_count()
            header_text = f"Player {i} 👑 {crowns}"
            header_surface = self.font_large.render(header_text, True, player_color)
            self.screen.blit(header_surface, (self.ui_rect.x + 15, y_pos))
            y_pos += 40
            
            # Elixir display
            elixir_text = f"Elixir: {player.elixir:.1f}"
            elixir_surface = self.font_medium.render(elixir_text, True, self.colors['text'])
            self.screen.blit(elixir_surface, (self.ui_rect.x + 20, y_pos))
            y_pos += 25
            
            # Enhanced elixir bar
            bar_width = 280
            bar_height = 20
            elixir_pct = min(player.elixir / 10.0, 1.0)
            
            # Elixir bar background
            bar_rect = pygame.Rect(self.ui_rect.x + 20, y_pos, bar_width, bar_height)
            pygame.draw.rect(self.screen, (0, 0, 0, 150), bar_rect)
            
            # Elixir segments (like in game)
            segment_width = bar_width // 10
            for seg in range(10):
                seg_rect = pygame.Rect(
                    self.ui_rect.x + 20 + seg * segment_width,
                    y_pos,
                    segment_width - 2,
                    bar_height
                )
                
                if seg < player.elixir:
                    pygame.draw.rect(self.screen, self.colors['elixir'], seg_rect)
                else:
                    pygame.draw.rect(self.screen, (100, 100, 100), seg_rect)
                
                pygame.draw.rect(self.screen, self.colors['outline'], seg_rect, 1)
            
            y_pos += 35
            
            # Tower HP with icons
            towers = [
                ("👑", player.king_tower_hp, 4824),
                ("🏰", player.left_tower_hp, 3631),
                ("🏰", player.right_tower_hp, 3631)
            ]
            
            for icon, hp, max_hp in towers:
                hp_text = f"{icon} {int(hp)}/{int(max_hp)}"
                hp_surface = self.font_small.render(hp_text, True, self.colors['text'])
                self.screen.blit(hp_surface, (self.ui_rect.x + 25, y_pos))
                y_pos += 22
            
            y_pos += 20
        
        # Game mode indicators
        if battle_state.overtime:
            overtime_text = "⚡ OVERTIME ⚡"
            overtime_surface = self.font_large.render(overtime_text, True, self.colors['health_low'])
            overtime_rect = overtime_surface.get_rect(centerx=self.ui_rect.centerx)
            overtime_rect.y = y_pos
            
            # Flashing background
            flash_intensity = int(128 + 127 * math.sin(battle_state.time * 10))
            flash_color = (flash_intensity, 0, 0)
            flash_rect = pygame.Rect(overtime_rect.x - 10, overtime_rect.y - 5, 
                                   overtime_rect.width + 20, overtime_rect.height + 10)
            pygame.draw.rect(self.screen, flash_color, flash_rect)
            
            self.screen.blit(overtime_surface, overtime_rect)
            y_pos += 50
        
        elif battle_state.triple_elixir:
            mode_text = "⚡⚡⚡ 3X ELIXIR ⚡⚡⚡"
            mode_surface = self.font_medium.render(mode_text, True, self.colors['elixir'])
            mode_rect = mode_surface.get_rect(centerx=self.ui_rect.centerx)
            mode_rect.y = y_pos
            self.screen.blit(mode_surface, mode_rect)
            y_pos += 35
        
        elif battle_state.double_elixir:
            mode_text = "⚡⚡ 2X ELIXIR ⚡⚡"
            mode_surface = self.font_medium.render(mode_text, True, self.colors['elixir'])
            mode_rect = mode_surface.get_rect(centerx=self.ui_rect.centerx)
            mode_rect.y = y_pos
            self.screen.blit(mode_surface, mode_rect)
            y_pos += 35
    
    def draw_cards_ui(self, battle_state: BattleState):
        """Draw card hand UI at bottom"""
        # Card area background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.card_rect)
        pygame.draw.rect(self.screen, self.colors['outline'], self.card_rect, 2)
        
        # Player 0's hand
        hand = battle_state.players[0].hand
        card_width = 120
        card_height = 80
        spacing = 20
        start_x = self.card_rect.x + 40
        
        for i, card_name in enumerate(hand):
            card_x = start_x + i * (card_width + spacing)
            card_y = self.card_rect.y + 20
            
            # Card background
            card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
            pygame.draw.rect(self.screen, self.colors['card_bg'], card_rect)
            pygame.draw.rect(self.screen, self.colors['outline'], card_rect, 2)
            
            # Card name
            name_surface = self.font_medium.render(card_name, True, self.colors['text_dark'])
            name_rect = name_surface.get_rect(center=(card_x + card_width//2, card_y + 20))
            self.screen.blit(name_surface, name_rect)
            
            # Elixir cost (mock)
            costs = {"Knight": "3", "Archers": "3", "Arrows": "3", "Fireball": "4", 
                    "Giant": "5", "Wizard": "5", "Musketeer": "4"}
            cost = costs.get(card_name, "?")
            
            # Elixir cost circle
            cost_center = (card_x + card_width - 15, card_y + 15)
            pygame.draw.circle(self.screen, self.colors['elixir'], cost_center, 12)
            pygame.draw.circle(self.screen, self.colors['outline'], cost_center, 12, 2)
            
            cost_surface = self.font_small.render(cost, True, self.colors['text'])
            cost_rect = cost_surface.get_rect(center=cost_center)
            self.screen.blit(cost_surface, cost_rect)
    
    def render(self, battle_state: BattleState):
        """Render the enhanced battle visualization"""
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
        
        # Clear screen with dark background
        self.screen.fill((34, 34, 34))
        
        # Draw components
        self.draw_arena_background(battle_state)
        
        # Draw entities with enhanced appearance
        for entity in battle_state.entities.values():
            if entity.is_alive:
                if isinstance(entity, Building):
                    self.draw_tower(entity)
                elif isinstance(entity, Troop):
                    self.draw_troop(entity)
                elif isinstance(entity, Projectile):
                    screen_x, screen_y = self.world_to_screen(entity.position)
                    pygame.draw.circle(self.screen, (255, 140, 0), (screen_x, screen_y), 6)
                    pygame.draw.circle(self.screen, self.colors['outline'], (screen_x, screen_y), 6, 2)
        
        self.draw_enhanced_ui(battle_state)
        self.draw_cards_ui(battle_state)
        
        pygame.display.flip()
        return True
    
    def close(self):
        """Close the visualizer"""
        pygame.quit()
        self.running = False