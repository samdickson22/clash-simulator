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
        self.last_deploy_time = [-2.0, -1.0]  # Stagger initial spawns, start with delay
        self.deploy_cooldown = 1.0  # Seconds between deployments (more frequent)
        self.game_time = 0.0
        
        # Available troop cards for random deployment
        self.available_troops = [
            'Knight', 'Archer', 'Barbarians', 'Giant', 'Pekka', 
            'Goblins', 'Minions', 'MegaMinion', 'Skeleton Army', 'Valkyrie',
            'Wizard', 'BabyDragon', 'Musketeer', 'Balloon'
        ]
        
        print(f"🎮 Random Battle Simulator Started!")
        print(f"📋 Available troops: {', '.join(self.available_troops)}")
        print(f"⚡ Deploy cooldown: {self.deploy_cooldown}s per player")
        print(f"🎯 Controls: SPACE = pause/unpause, R = reset, ESC = quit")

    def get_random_deploy_position(self, player_id: int) -> Position:
        """Get a random valid deployment position for a player"""
        if player_id == 0:  # Blue player (bottom)
            x = random.uniform(2, 16)
            y = random.uniform(8, 14.5)  # Bottom half, before river
        else:  # Red player (top)
            x = random.uniform(2, 16) 
            y = random.uniform(17.5, 24)  # Top half, after river
        
        return Position(x, y)

    def should_deploy_troop(self, player_id: int) -> bool:
        """Check if it's time to deploy a random troop for this player"""
        time_since_last = self.game_time - self.last_deploy_time[player_id]
        
        # Random deployment with higher probability for more action
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
            
            # Add some cooldown variation (shorter for more action)
            self.deploy_cooldown = random.uniform(0.8, 1.5)

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
                        self.last_deploy_time = [0.0, 0.0]
                    elif event.key >= pygame.K_1 and event.key <= pygame.K_5:
                        # Set speed multiplier
                        self.speed = event.key - pygame.K_0
            
            # Update real-time game timer
            if not self.paused:
                self.game_time += frame_time
                
                # Random troop deployments
                for player_id in [0, 1]:
                    if self.should_deploy_troop(player_id):
                        self.deploy_random_troop(player_id)
            
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
        
        # Next deployment timers
        for player_id in [0, 1]:
            time_until_next = max(0, self.deploy_cooldown - (self.game_time - self.last_deploy_time[player_id]))
            player_name = "Blue" if player_id == 0 else "Red"
            color = (100, 100, 255) if player_id == 0 else (255, 100, 100)
            
            timer_text = self.small_font.render(f"{player_name} next: {time_until_next:.1f}s", True, color)
            self.screen.blit(timer_text, (ui_x, ui_y))
            ui_y += 20
        
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