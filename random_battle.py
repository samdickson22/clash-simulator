#!/usr/bin/env python3

import sys
import random
import time
sys.path.append('src')

from visualize_battle import BattleVisualizer
from clasher.arena import Position
from clasher.data import CardDataLoader
import json
import os

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
        
        # Remove cards that shouldn't be in hands/deck (case-sensitive)
        # Also exclude any "tower troop" variants (tidType == TID_TYPE_TOWER_TROOP)
        excluded_cards = {
            'Tower', 'KingTower', 'GoblinRocketSilo', 'MergeMaiden',
            'King_CannonTowers', 'King_KnifeTowers', 'King_PrincessTowers',
            'TriWizards', 'TriWizard'  # remove multi-unit special cycles per request
        }
        self.available_cards = [card for card in self.available_cards if card not in excluded_cards]
        
        # Initialize per-player cycle structures (filled by assign_random_decks_to_players)
        self.player_cycles = {0: [], 1: []}
        self.player_cycle_indices = {0: 0, 1: 0}
        
        # Load curated decks and assign randomly per player, then build cycle from that deck
        self.decks = self.load_curated_decks()
        self.assign_random_decks_to_players()
        
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
        """Play the next card in cycle when a player reaches 10 elixir."""
        player = self.battle.players[player_id]
        if player.elixir < 10.0:
            return
        # Ensure full hand from cycle
        self.ensure_player_has_full_hand(player_id)
        if not player.hand:
            return

        # The next card to play is the first in hand to respect cycle order
        excluded = {
            'Tower', 'KingTower', 'GoblinRocketSilo', 'MergeMaiden',
            'King_CannonTowers', 'King_KnifeTowers', 'King_PrincessTowers',
            'TriWizards', 'TriWizard'
        }
        # Skip excluded if present for any reason
        while player.hand and player.hand[0] in excluded:
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)
        if not player.hand:
            return

        card_name = player.hand[0]
        card_stats = self.cards.get(card_name)
        if not card_stats:
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)
            return

        if player.elixir < card_stats.mana_cost:
            return

        # Choose random playable tile
        position = random.choice(self.playable_tiles)

        success = self.battle.deploy_card(player_id, card_name, position)
        if success:
            # Simulate cycle: remove from hand and refill
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)

            player_name = "Blue" if player_id == 0 else "Red"
            card_type = card_stats.card_type if card_stats else "Unknown"
            print(f"💰 {player_name} auto-played {card_name} ({card_type}) at ({position.x:.1f}, {position.y:.1f}) - Cost: {card_stats.mana_cost}")

    def _draw_next_from_cycle(self, player_id: int) -> str:
        """Get next card in the player's fixed shuffled cycle."""
        cycle = self.player_cycles[player_id]
        if not cycle:
            return None
        idx = self.player_cycle_indices[player_id]
        card = cycle[idx % len(cycle)]
        self.player_cycle_indices[player_id] = (idx + 1) % len(cycle)
        return card

    def ensure_player_has_full_hand(self, player_id: int):
        """Ensure player has 4 cards in hand, filling from the player's fixed cycle order."""
        player = self.battle.players[player_id]
        # Maintain a 4-card hand by drawing from the cycle (no randomness)
        while len(player.hand) < 4:
            next_card = self._draw_next_from_cycle(player_id)
            if next_card is None:
                break
            if next_card not in player.hand:
                player.hand.append(next_card)
            else:
                # If duplicate in hand, advance until we get something different or give up after len(cycle)
                attempts = 0
                while attempts < len(self.player_cycles[player_id]) and next_card in player.hand:
                    next_card = self._draw_next_from_cycle(player_id)
                    attempts += 1
                if next_card and next_card not in player.hand:
                    player.hand.append(next_card)

    def deploy_random_card(self):
        """Deploy the next card in a player's fixed shuffled cycle at a random playable tile."""
        # Choose random player (50/50 chance)
        player_id = random.choice([0, 1])

        # Ensure player has a full hand from their cycle
        self.ensure_player_has_full_hand(player_id)

        player = self.battle.players[player_id]
        if not player.hand:
            return

        # Take the first card in hand to simulate cycle play (like top of hand)
        card_name = player.hand[0]

        # Guards for exclusions
        excluded = {
            'Tower', 'KingTower', 'GoblinRocketSilo', 'MergeMaiden',
            'King_CannonTowers', 'King_KnifeTowers', 'King_PrincessTowers',
            'TriWizards', 'TriWizard'
        }
        if card_name in excluded:
            # Remove it from hand if it got in somehow and refill
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)
            return

        # Choose completely random playable tile
        position = random.choice(self.playable_tiles)

        # Check if player can afford the card
        card_stats = self.cards.get(card_name)
        if not card_stats:
            # Drop and refill from cycle if stats missing
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)
            return

        if player.elixir < card_stats.mana_cost:
            return  # Not enough elixir

        # Deploy
        success = self.battle.deploy_card(player_id, card_name, position)
        if success:
            # Simulate cycling: remove the played card from hand and refill from the player's cycle
            player.hand.pop(0)
            self.ensure_player_has_full_hand(player_id)

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
                        # Reassign random curated decks and rebuild cycles
                        self.assign_random_decks_to_players()
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
                    # Use actual spell name if available
                    card_name = getattr(entity, 'spell_name', 'Projectile')
                    color = (255, 255, 0)  # Yellow for projectiles
                elif hasattr(entity, 'spell_name'):
                    # For area effects and other spell entities
                    card_name = entity.spell_name
                    color = (255, 0, 255)  # Magenta for area effects
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
        
        import pygame
        
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
        
        # Player deck names only
        header = self.font.render("Player Decks", True, (0, 0, 0))
        self.screen.blit(header, (ui_x, ui_y))
        ui_y += line_height

        # Blue player
        p0_color = (60, 100, 255)
        blue_name = "Blue Player"
        deck_name0 = self._chosen_deck_names.get(0, "Custom Deck")
        title_text = f"{blue_name}: {deck_name0}"
        self.screen.blit(self.font.render(title_text, True, p0_color), (ui_x, ui_y))
        ui_y += line_height

        # Red player
        p1_color = (255, 100, 100)
        red_name = "Red Player"
        deck_name1 = self._chosen_deck_names.get(1, "Custom Deck")
        title_text = f"{red_name}: {deck_name1}"
        self.screen.blit(self.font.render(title_text, True, p1_color), (ui_x, ui_y))
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

    def load_curated_decks(self):
        """Load curated decks from decks.json, filter invalid/excluded cards, and store reasons if skipped."""
        path = os.path.join(os.getcwd(), "decks.json")
        if not os.path.exists(path):
            return []

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            return []

        decks = data.get("decks", [])
        # Exclusions matching simulator constraints
        excluded = {
            'Tower', 'KingTower', 'GoblinRocketSilo', 'MergeMaiden',
            'King_CannonTowers', 'King_KnifeTowers', 'King_PrincessTowers',
            'TriWizards', 'TriWizard', 'ThreeMusketeers'
        }

        # Comprehensive alias map for names commonly seen in meta lists
        alias = {
            "The Log": "Log",
            "Log": "Log",
            "Hog Rider": "HogRider",
            "Hog": "HogRider",
            "X-Bow": "Xbow",
            "Mini P.E.K.K.A": "MiniPekka",
            "Mini P.E.K.K.A.": "MiniPekka",
            "Mini Pekka": "MiniPekka",
            "P.E.K.K.A": "Pekka",
            "P.E.K.K.A.": "Pekka",
            "Royal Delivery": "RoyalDelivery",
            "Royal Ghost": "RoyalGhost",
            "Skeleton Barrel": "SkeletonBarrel",
            "Giant Snowball": "GiantSnowball",
            "Wall Breakers": "Wallbreakers",
            "Electro Wizard": "ElectroWizard",
            "Ice Wizard": "IceWizard",
            "Dart Goblin": "DartGoblin",
            "Magic Archer": "MagicArcher",
            "Mega Knight": "MegaKnight",
            "Inferno Dragon": "InfernoDragon",
            "Electro Dragon": "ElectroDragon",
            "Archer Queen": "ArcherQueen",
            "Barbarian Barrel": "BarbarianBarrel",
            "Bomb Tower": "BombTower",
            "Ice Golem": "IceGolem",
            "Ice Spirit": "IceSpirit",
            "Electro Spirit": "ElectroSpirit",
            "Royal Hogs": "RoyalHogs",
            "Cannon Cart": "CannonCart",  # just in case
            "Skeleton King": "SkeletonKing",
            "Tomb Stone": "Tombstone",
            # Additions based on resolution report
            # Canonical mappings to your dataset internal IDs
            "Archers": "Archer",
            "Ice Spirit": "IceSpirits",
            "IceSpirit": "IceSpirits",
            "Fire Spirit": "FireSpirits",
            "FireSpirit": "FireSpirits",
            "Ice Golem": "IceGolemite",
            "IceGolem": "IceGolemite",
            "Dart Goblin": "BlowdartGoblin",
            "DartGoblin": "BlowdartGoblin",
            "Giant Snowball": "Snowball",
            "GiantSnowball": "Snowball",
            "Barbarian Barrel": "BarbLog",
            "BarbarianBarrel": "BarbLog",
            "Skeleton Barrel": "SkeletonBalloon",
            "SkeletonBarrel": "SkeletonBalloon",
            "Royal Ghost": "Ghost",
            "RoyalGhost": "Ghost",
            # Proxy mappings requested
            "Bandit": "Assassin",
            "Lumberjack": "AxeMan",
            # Keepers / already matching internal keys
            "Skeletons": "Skeletons",
            "Princess": "Princess",
            "InfernoTower": "InfernoTower",
            "BattleRam": "BattleRam",
            "Wallbreakers": "Wallbreakers",
            "SpearGoblins": "SpearGoblins",
            "RoyalRecruits": "RoyalRecruits",
            "RoyalGiant": "RoyalGiant",
            "MagicArcher": "EliteArcher",  # optional proxy to resolve those decks
            "Guards": "SkeletonWarriors"   # optional proxy to resolve those decks
        }

        normalized = []
        self._skipped_decks_debug = []  # keep for debugging
        for deck in decks:
            cards = deck.get("cards", [])
            filtered = []
            skipped = []
            for c in cards:
                name = alias.get(c, c)
                if name in excluded:
                    skipped.append((c, "excluded"))
                    continue
                if name not in self.cards:
                    skipped.append((c, "unknown"))
                    continue
                filtered.append(name)
            # Accept only if exactly 8 valid cards
            if len(filtered) == 8:
                normalized.append({
                    "name": deck.get("name", "Deck"),
                    "cards": filtered
                })
            else:
                self._skipped_decks_debug.append({
                    "name": deck.get("name", "Deck"),
                    "reason": f"only {len(filtered)}/8 valid",
                    "skipped": skipped,
                    "after_alias": filtered
                })
        # Print diagnostics
        try:
            print("==== Curated Decks Resolution Report ====")
            print(f"Total decks in JSON: {len(decks)}")
            print(f"Resolved decks: {len(normalized)}")
            for d in normalized:
                print(f"  ✓ {d['name']}: {', '.join(d['cards'])}")
            unresolved = len(self._skipped_decks_debug)
            print(f"Unresolved decks: {unresolved}")
            for d in self._skipped_decks_debug:
                print(f"  ✗ {d['name']} -> {d['reason']}")
                if d.get("skipped"):
                    print("     Problem cards:")
                    for original, why in d["skipped"]:
                        print(f"       - {original} ({why})")
                if d.get("after_alias") is not None:
                    print(f"     After alias valid subset ({len(d['after_alias'])}): {', '.join(d['after_alias'])}")
            print("==== End Decks Resolution Report ====")
        except Exception as e:
            print(f"[Deck Debug] Failed to print resolution report: {e}")
        return normalized

    def assign_random_decks_to_players(self):
        """Pick a random curated deck for each player and build a fixed cycle, storing the chosen name for UI."""
        # Fallback: if no curated decks available, do nothing (keep previous behavior)
        if not self.decks:
            # Build cycles from available_cards as fallback
            self.player_cycles = {0: [], 1: []}
            self.player_cycle_indices = {0: 0, 1: 0}
            self._chosen_deck_names = {0: "Custom Deck", 1: "Custom Deck"}
            for pid, player in enumerate(self.battle.players):
                pool = list(self.available_cards)
                random.shuffle(pool)
                self.player_cycles[pid] = pool
                self.player_cycle_indices[pid] = 0
                player.deck = pool.copy()
                player.hand = player.deck[:4] if len(player.deck) >= 4 else player.deck.copy()
            return

        self.player_cycles = {0: [], 1: []}
        self.player_cycle_indices = {0: 0, 1: 0}
        self._chosen_deck_names = {0: "", 1: ""}

        for pid, player in enumerate(self.battle.players):
            chosen = random.choice(self.decks)
            deck = chosen["cards"][:]  # 8 cards
            # Build a repeated cycle from this fixed deck by shuffling a copy once
            cycle = deck[:]  # curated 8
            random.shuffle(cycle)  # randomize starting order
            self.player_cycles[pid] = cycle
            self.player_cycle_indices[pid] = 0
            player.deck = deck[:]  # deck contents for debug
            player.hand = cycle[:4]  # first four in cycle
            self._chosen_deck_names[pid] = chosen.get("name", "Deck")
            # Print assignment for debugging
            try:
                print(f"[Deck Assignment] Player {pid} assigned '{self._chosen_deck_names[pid]}' -> {', '.join(deck)}")
            except Exception:
                pass

if __name__ == "__main__":
    simulator = RandomBattleSimulator()
    simulator.run()
