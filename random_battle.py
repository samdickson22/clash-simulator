#!/usr/bin/env python3

import sys
import random
import time
sys.path.append('src')

from visualize_battle import BattleVisualizer
from clasher.arena import Position
from clasher.data import CardDataLoader

class RandomBattleSimulator(BattleVisualizer):
    def __init__(self):
        super().__init__()
        
        # Random deployment settings
        self.card_loader = CardDataLoader()
        self.cards = self.card_loader.load_cards()
        self.deploy_cooldown = 0.5  # Faster deployment for more chaos
        self.game_time = 0.0
        
        # Get all available cards (troops, buildings, spells)
        self.available_cards = list(self.cards.keys())
        
        # Remove tower cards that shouldn't be deployed
        excluded_cards = ['Tower', 'KingTower']
        self.available_cards = [card for card in self.available_cards if card not in excluded_cards]
        
        # Initialize players with full decks containing all available cards
        for player in self.battle.players:
            player.deck = self.available_cards.copy()
            # Start with 4 random cards from full deck
            player.hand = random.sample(self.available_cards, min(4, len(self.available_cards)))
        
        # Get all playable tiles
        self.playable_tiles = self.get_all_playable_tiles()
        
        print(f"🎮 Random Battle Simulator Started!")
        print(f"📋 Total cards in game: {len(self.cards)}")
        print(f"📋 Available cards for deployment: {len(self.available_cards)} total")
        print(f"🎯 Playable tiles: {len(self.playable_tiles)} total")
        print(f"⚡ Deploy cooldown: {self.deploy_cooldown}s")
        print(f"🎯 Controls: SPACE = pause/unpause, R = reset, ESC = quit")

    def get_all_playable_tiles(self):
        """Get all playable tile positions on the arena"""
        playable_tiles = []
        
        for x in range(18):  # 18 tiles wide
            for y in range(32):  # 32 tiles tall
                pos = Position(x + 0.5, y + 0.5)  # Center of tile
                
                # Check if tile is walkable (not blocked, not river unless on bridge)
                if self.battle.arena.is_walkable(pos):
                    playable_tiles.append(pos)
        
        return playable_tiles

    def should_deploy_card(self) -> bool:
        """Check if it's time to deploy a random card anywhere"""
        # Deploy cards frequently for chaos
        return random.random() < 0.1  # 10% chance per frame when not paused

    def play_card_at_full_elixir(self, player_id: int):
        """Play a random card when player reaches 10 elixir"""
        player = self.battle.players[player_id]
        
        # Only play if at full elixir and has cards in hand
        if player.elixir >= 10.0 and player.hand:
            # Choose random card from hand
            card_name = random.choice(player.hand)
            
            # Get card stats
            card_stats = self.cards.get(card_name)
            if not card_stats:
                return
            
            # Check if player can afford it (should always be true at 10 elixir)
            if player.elixir >= card_stats.mana_cost:
                # Choose random playable tile
                position = random.choice(self.playable_tiles)
                
                # Deploy
                success = self.battle.deploy_card(player_id, card_name, position)
                if success:
                    player_name = "Blue" if player_id == 0 else "Red"
                    card_type = card_stats.card_type if card_stats else "Unknown"
                    print(f"💰 {player_name} auto-played {card_name} ({card_type}) at ({position.x:.1f}, {position.y:.1f}) - Cost: {card_stats.mana_cost}")

    def ensure_player_has_full_hand(self, player_id: int):
        """Ensure player has 4 cards in hand, filling with random cards from deck"""
        player = self.battle.players[player_id]
        
        # Fill hand to 4 cards with random cards from deck
        while len(player.hand) < 4:
            if player.deck:
                # Choose random card from deck that's not already in hand
                available_cards = [card for card in player.deck if card not in player.hand]
                if available_cards:
                    random_card = random.choice(available_cards)
                    player.hand.append(random_card)
                else:
                    # If all deck cards are in hand, add a completely random card
                    random_card = random.choice(self.available_cards)
                    if random_card not in player.deck:
                        player.deck.append(random_card)
                    player.hand.append(random_card)
            else:
                # If deck is empty, add random cards
                random_card = random.choice(self.available_cards)
                player.deck.append(random_card)
                player.hand.append(random_card)

    def deploy_random_card(self):
        """Deploy a completely random card at a completely random playable tile"""
        # Choose completely random card
        card_name = random.choice(self.available_cards)
        
        # Choose completely random playable tile
        position = random.choice(self.playable_tiles)
        
        # Choose random player (50/50 chance)
        player_id = random.choice([0, 1])
        
        # Check if player can afford the card
        card_stats = self.cards.get(card_name)
        if not card_stats:
            return
            
        # Check if player has this card in their deck/hand
        if card_name not in self.battle.players[player_id].deck:
            # Add to deck if not present (for random battle chaos)
            self.battle.players[player_id].deck.append(card_name)
        
        # Ensure player has full hand
        self.ensure_player_has_full_hand(player_id)
        
        # Check if player can afford it
        if self.battle.players[player_id].elixir < card_stats.mana_cost:
            return  # Not enough elixir
        
        # Deploy
        success = self.battle.deploy_card(player_id, card_name, position)
        if success:
            player_name = "Blue" if player_id == 0 else "Red"
            card_type = card_stats.card_type if card_stats else "Unknown"
            print(f"⚔️  {player_name} deployed {card_name} ({card_type}) at ({position.x:.1f}, {position.y:.1f}) - Cost: {card_stats.mana_cost}")

    def run(self):
        """Main loop with proper real-time battle stepping"""
        import pygame
        import time
        
        print("🎮 Starting Battle Visualization")
        print("Controls:")
        print("  SPACE: Pause/Resume")
        print("  R: Reset Battle")
        print("  1-5: Speed multiplier (1x to 5x)")
        print("  I: Toggle investigation mode (auto screenshots)")
        print("  S: Take manual screenshot")
        print("  P: Take pathfinding debug screenshot")
        print("  ESC: Exit")
        
        self.paused = False
        self.speed = 1
        running = True
        
        # Real-time battle stepping at exactly 30 FPS (33.33ms per step)
        battle_accumulator = 0.0
        battle_timestep = 1.0 / 30.0  # Exactly 30 FPS for battle logic
        
        last_time = time.time()
        
        while running:
            current_time = time.time()
            frame_time = current_time - last_time
            last_time = current_time
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r:
                        # Reset battle
                        from clasher.battle import BattleState
                        self.battle = BattleState()
                        self.game_time = 0.0
                        # Reinitialize players with full decks
                        for player in self.battle.players:
                            player.deck = self.available_cards.copy()
                            # Start with 4 random cards from full deck
                            player.hand = random.sample(self.available_cards, min(4, len(self.available_cards)))
                        # Regenerate playable tiles for new battle
                        self.playable_tiles = self.get_all_playable_tiles()
                    elif event.key >= pygame.K_1 and event.key <= pygame.K_5:
                        # Set speed multiplier
                        self.speed = event.key - pygame.K_0
            
            # Update real-time game timer
            if not self.paused:
                self.game_time += frame_time
                
                # Random card deployments
                if self.should_deploy_card():
                    self.deploy_random_card()
                
                # Check if players have reached full elixir and auto-play
                for player_id in [0, 1]:
                    self.play_card_at_full_elixir(player_id)
            
            # Update battle at proper timestep
            if not self.paused and not self.battle.game_over:
                battle_accumulator += frame_time * self.speed
                
                while battle_accumulator >= battle_timestep:
                    self.battle.step(speed_factor=1.0)
                    battle_accumulator -= battle_timestep
            
            # Draw everything
            self.screen.fill((255, 255, 255))  # WHITE
            self.draw_arena()
            self.draw_towers()  
            self.draw_entities()
            self.draw_ui()
            
            # Show pause indicator
            if self.paused:
                pause_text = self.large_font.render("PAUSED", True, (255, 100, 100))  # RED
                pause_rect = pause_text.get_rect(center=(self.screen.get_width()//2, 30))
                self.screen.blit(pause_text, pause_rect)
            
            # Show speed indicator
            if self.speed > 1:
                speed_text = self.font.render(f"Speed: {self.speed}x", True, (255, 100, 255))  # PURPLE
                speed_rect = speed_text.get_rect(topleft=(10, 10))
                self.screen.blit(speed_text, speed_rect)
            
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS display
        
        pygame.quit()

    def get_card_color(self, card_stats):
        """Get color for card based on its rarity"""
        if not card_stats:
            return (128, 128, 128)  # Gray for unknown
        
        rarity = getattr(card_stats, 'rarity', 'Common')
        card_type = getattr(card_stats, 'card_type', 'Troop')
        
        # Color by card type first, then rarity
        if card_type == "Spell":
            return (255, 0, 255)  # Magenta for spells
        elif card_type == "Building":
            return (139, 69, 19)  # Brown for buildings
        else:  # Troops
            rarity_colors = {
                'Common': (128, 128, 128),      # Gray
                'Rare': (255, 165, 0),          # Orange  
                'Epic': (128, 0, 128),          # Purple
                'Legendary': (255, 215, 0),     # Gold
                'Champion': (255, 20, 147)      # Deep Pink
            }
            return rarity_colors.get(rarity, (0, 255, 0))  # Green for unknown

    def draw_entities(self):
        """Draw all entities with card names above them"""
        import pygame
        
        # Call parent method to draw entities
        super().draw_entities()
        
        # Draw card names above entities
        for entity in self.battle.entities.values():
            if not entity.is_alive:
                continue
                
            # Get screen position
            screen_x, screen_y = self.world_to_screen(entity.position.x, entity.position.y)
            
            # Get card name and color
            card_name = "Unknown"
            if hasattr(entity, 'card_stats') and entity.card_stats:
                card_name = entity.card_stats.name
                color = self.get_card_color(entity.card_stats)
            else:
                # For projectiles and other entities without card stats
                if hasattr(entity, 'target_position'):
                    card_name = "Projectile"
                    color = (255, 255, 0)  # Yellow for projectiles
                else:
                    color = (128, 128, 128)  # Gray for unknown
            
            # Player color tint
            if entity.player_id == 0:
                # Blue player - make colors cooler
                color = (max(0, color[0] - 50), max(0, color[1] - 30), min(255, color[2] + 50))
            else:
                # Red player - make colors warmer  
                color = (min(255, color[0] + 50), max(0, color[1] - 30), max(0, color[2] - 50))
            
            # Render text
            text_surface = self.small_font.render(card_name, True, color)
            text_rect = text_surface.get_rect()
            text_rect.centerx = screen_x
            text_rect.bottom = screen_y - 15  # Above the entity
            
            # Draw background for better readability
            bg_rect = text_rect.inflate(4, 2)
            pygame.draw.rect(self.screen, (255, 255, 255, 180), bg_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect, 1)
            
            # Draw text
            self.screen.blit(text_surface, text_rect)

    def draw_ui(self):
        """Draw UI with additional random battle info"""
        # Call parent UI drawing
        super().draw_ui()
        
        # Add additional UI for random battle
        ui_x = 920
        ui_y = 500
        line_height = 25
        
        # Game time
        time_text = self.font.render(f"Game Time: {self.game_time:.1f}s", True, (0, 0, 0))
        self.screen.blit(time_text, (ui_x, ui_y))
        ui_y += line_height
        
        # Random deployment info
        deploy_text = self.font.render(f"Random Deployments: 10% chance/frame", True, (0, 0, 0))
        self.screen.blit(deploy_text, (ui_x, ui_y))
        ui_y += line_height
        
        # Card count
        card_count_text = self.font.render(f"Available Cards: {len(self.available_cards)}", True, (0, 0, 0))
        self.screen.blit(card_count_text, (ui_x, ui_y))
        ui_y += line_height
        
        ui_y += 10
        
        # Timing verification
        timing_text = self.small_font.render("Timing Check:", True, (0, 0, 0))
        self.screen.blit(timing_text, (ui_x, ui_y))
        ui_y += 18
        
        timing_info = self.small_font.render("Knight: 1 tile/sec, 1.2s attacks", True, (64, 64, 64))
        self.screen.blit(timing_info, (ui_x, ui_y))
        ui_y += 16
        
        timing_info2 = self.small_font.render("Battle: 30 FPS, Display: 60 FPS", True, (64, 64, 64))
        self.screen.blit(timing_info2, (ui_x, ui_y))

if __name__ == "__main__":
    simulator = RandomBattleSimulator()
    simulator.run()
