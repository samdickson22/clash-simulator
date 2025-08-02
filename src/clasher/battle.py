from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import math
import random

from .entities import Entity, Troop, Building
from .player import PlayerState
from .arena import TileGrid, Position
from .data import CardDataLoader, CardStats
from .spells import SPELL_REGISTRY


@dataclass
class BattleState:
    # Core state
    entities: Dict[int, Entity] = field(default_factory=dict)
    players: List[PlayerState] = field(default_factory=lambda: [PlayerState(0), PlayerState(1)])
    arena: TileGrid = field(default_factory=TileGrid)
    
    # Timing
    time: float = 0.0
    tick: int = 0
    dt: float = 0.033  # 33ms per tick (~30 FPS)
    
    # Game state
    double_elixir: bool = False
    triple_elixir: bool = False
    overtime: bool = False
    game_over: bool = False
    winner: Optional[int] = None
    
    # Data
    card_loader: CardDataLoader = field(default_factory=CardDataLoader)
    next_entity_id: int = 1
    
    def __post_init__(self) -> None:
        """Initialize battle state"""
        self.card_loader.load_cards()
        self._create_towers()
    
    def _create_towers(self) -> None:
        """Create tower entities for both players"""
        tower_stats = CardStats(
            name="Tower",
            id=0,
            mana_cost=0,
            rarity="",
            hitpoints=1400,  # Level 1 from JSON: "hitpoints": 1400
            damage=50,       # Level 1 from JSON: projectileData "damage": 50
            range=7.5,       # From JSON: "range": 7500 (7.5 tiles)
            sight_range=7.5, # From JSON: "sightRange": 7500 (7.5 tiles)
            load_time=800,
            hit_speed=800,   # From JSON: "hitSpeed": 800
            attacks_air=True,  # Towers can attack air units
            target_type="TID_TARGETS_AIR_AND_GROUND",  # From JSON: "tidTarget": "TID_TARGETS_AIR_AND_GROUND"
            level=11  # Standard tournament level
        )
        
        king_stats = CardStats(
            name="KingTower", 
            id=0,
            mana_cost=0,
            rarity="",
            hitpoints=4824,     # King tower HP
            damage=109,         # King tower damage
            range=7.0,          # King tower range (7 tiles)
            sight_range=7.0,    # King tower sight range
            load_time=1000,
            hit_speed=1000,     # King tower attacks once per second (1000ms)
            attacks_air=True,   # King tower can attack air units
            target_type="TID_TARGETS_AIR_AND_GROUND",  # Explicit air targeting
            level=1   # Base level stats (no scaling needed)
        )
        
        # Player 0 towers (blue) - create new Position objects to avoid sharing references
        blue_left = Position(self.arena.BLUE_LEFT_TOWER.x, self.arena.BLUE_LEFT_TOWER.y)
        blue_right = Position(self.arena.BLUE_RIGHT_TOWER.x, self.arena.BLUE_RIGHT_TOWER.y)
        blue_king = Position(self.arena.BLUE_KING_TOWER.x, self.arena.BLUE_KING_TOWER.y)
        self._spawn_entity(Building, blue_left, 0, tower_stats)
        self._spawn_entity(Building, blue_right, 0, tower_stats)
        self._spawn_entity(Building, blue_king, 0, king_stats)
        
        # Player 1 towers (red) - create new Position objects to avoid sharing references
        red_left = Position(self.arena.RED_LEFT_TOWER.x, self.arena.RED_LEFT_TOWER.y)
        red_right = Position(self.arena.RED_RIGHT_TOWER.x, self.arena.RED_RIGHT_TOWER.y)
        red_king = Position(self.arena.RED_KING_TOWER.x, self.arena.RED_KING_TOWER.y)
        self._spawn_entity(Building, red_left, 1, tower_stats)
        self._spawn_entity(Building, red_right, 1, tower_stats)
        self._spawn_entity(Building, red_king, 1, king_stats)
    
    def step(self, speed_factor: float = 1.0) -> None:
        """Advance battle by one tick"""
        if self.game_over:
            return
        
        dt = self.dt * speed_factor
        self.time += dt
        self.tick += 1
        
        # Update elixir modes
        if self.time >= 120.0 and not self.double_elixir:
            self.double_elixir = True
        
        # Regenerate elixir
        base_regen = 2.8
        if self.triple_elixir:
            base_regen = 0.9
        elif self.double_elixir:
            base_regen = 1.4
        
        for player in self.players:
            player.regenerate_elixir(dt, base_regen)
        
        # Update all entities
        for entity in list(self.entities.values()):
            entity.update(dt, self)
        
        # Remove dead entities
        self._cleanup_dead_entities()
        
        # Check win conditions
        self._check_win_conditions()
    
    def deploy_card(self, player_id: int, card_name: str, position: Position) -> bool:
        """Deploy a card at the given position"""
        player = self.players[player_id]
        card_stats = self.card_loader.get_card(card_name)
        
        if not card_stats or not player.can_play_card(card_name, card_stats):
            return False
        
        is_spell = card_name in SPELL_REGISTRY
        if not self.arena.can_deploy_at(position, player_id, self, is_spell):
            return False
        
        # Play the card
        if not player.play_card(card_name, card_stats):
            return False
        
        # Check if it's a spell
        if card_name in SPELL_REGISTRY:
            spell = SPELL_REGISTRY[card_name]
            spell.cast(self, player_id, position)
        else:
            # Spawn troop or building based on card type (robust to missing/None fields)
            card_type = getattr(card_stats, "card_type", None)
            card_type_str = str(card_type).lower() if card_type is not None else ""
            if card_type_str == "building":
                self._spawn_entity(Building, position, player_id, card_stats)
            else:
                self._spawn_troop(position, player_id, card_stats)
        
        return True
    
    def _spawn_troop(self, position: Position, player_id: int, card_stats: CardStats) -> None:
        """Spawn a troop entity"""
        # Guard: if this card is actually a building, route to building spawner
        ctype = getattr(card_stats, "card_type", None)
        ctype_str = str(ctype).lower() if ctype is not None else ""
        if ctype_str == "building":
            self._spawn_entity(Building, position, player_id, card_stats)
            return
        
        # Get speed value (tiles/min from card stats)
        speed = card_stats.speed or 60.0  # Default to 60 tiles/min if not specified
        
        # Determine if this is an air unit
        air_units = ['Minions', 'MinionHorde', 'Balloon', 'SkeletonBalloon', 'BabyDragon', 
                    'InfernoDragon', 'ElectroDragon', 'SkeletonDragons', 'MegaMinion']
        is_air_unit = card_stats.name in air_units
        
        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints or 100
        scaled_damage = card_stats.scaled_damage or 10
        
        troop = Troop(
            id=self.next_entity_id,
            position=position,
            player_id=player_id,
            card_stats=card_stats,
            hitpoints=scaled_hp,
            max_hitpoints=scaled_hp,
            damage=scaled_damage,
            range=card_stats.range or 100,
            sight_range=card_stats.sight_range or 500,
            speed=speed,
            is_air_unit=is_air_unit
        )
        
        self.entities[self.next_entity_id] = troop
        self.next_entity_id += 1
    
    def _spawn_entity(self, entity_class, position: Position, player_id: int, card_stats: CardStats) -> Entity:
        """Spawn any type of entity"""
        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints or 100
        scaled_damage = card_stats.scaled_damage or 10
        
        entity = entity_class(
            id=self.next_entity_id,
            position=position,
            player_id=player_id,
            card_stats=card_stats,
            hitpoints=scaled_hp,
            max_hitpoints=scaled_hp,
            damage=scaled_damage,
            range=card_stats.range or 100,
            sight_range=card_stats.sight_range or 500
        )
        
        self.entities[self.next_entity_id] = entity
        self.next_entity_id += 1
        return entity
    
    def _cleanup_dead_entities(self) -> None:
        """Remove dead entities from the game and handle death spawns"""
        dead_ids = [eid for eid, entity in self.entities.items() if not entity.is_alive]
        
        # Handle death spawns before removing entities
        for eid in dead_ids:
            entity = self.entities[eid]
            if isinstance(entity, Troop) and entity.card_stats.death_spawn_character:
                self._spawn_death_units(entity)
        
        # Update player state for dead towers before removing entities
        for eid in dead_ids:
            entity = self.entities[eid]
            if isinstance(entity, Building):
                player = self.players[entity.player_id]
                pos = entity.position
                
                # Set tower HP to 0 when entity dies
                if entity.player_id == 0:  # Blue player
                    if (pos.x == self.arena.BLUE_KING_TOWER.x and 
                        pos.y == self.arena.BLUE_KING_TOWER.y):
                        player.king_tower_hp = 0
                    elif (pos.x == self.arena.BLUE_LEFT_TOWER.x and 
                          pos.y == self.arena.BLUE_LEFT_TOWER.y):
                        player.left_tower_hp = 0
                    elif (pos.x == self.arena.BLUE_RIGHT_TOWER.x and 
                          pos.y == self.arena.BLUE_RIGHT_TOWER.y):
                        player.right_tower_hp = 0
                else:  # Red player
                    if (pos.x == self.arena.RED_KING_TOWER.x and 
                        pos.y == self.arena.RED_KING_TOWER.y):
                        player.king_tower_hp = 0
                    elif (pos.x == self.arena.RED_LEFT_TOWER.x and 
                          pos.y == self.arena.RED_LEFT_TOWER.y):
                        player.left_tower_hp = 0
                    elif (pos.x == self.arena.RED_RIGHT_TOWER.x and 
                          pos.y == self.arena.RED_RIGHT_TOWER.y):
                        player.right_tower_hp = 0
        
        # Remove dead entities
        for eid in dead_ids:
            del self.entities[eid]
    
    def _spawn_death_units(self, troop: Troop) -> None:
        """Spawn death units when a troop dies"""
        death_spawn_name = troop.card_stats.death_spawn_character
        death_spawn_count = troop.card_stats.death_spawn_count or 1
        
        # Get death spawn card stats
        death_spawn_stats = self.card_loader.get_card(death_spawn_name)
        
        # If death spawn card doesn't exist, create minimal stats from the troop's death spawn data
        if not death_spawn_stats and hasattr(troop.card_stats, 'death_spawn_character_data') and troop.card_stats.death_spawn_character_data:
            # Create basic card stats for the death spawn unit
            death_spawn_stats = CardStats(
                name=death_spawn_name,
                id=0,
                mana_cost=0,
                rarity="Common",
                hitpoints=troop.card_stats.death_spawn_character_data.get("hitpoints", 100),
                damage=troop.card_stats.death_spawn_character_data.get("damage", 10),
                speed=float(troop.card_stats.death_spawn_character_data.get("speed", 60)),
                range=troop.card_stats.death_spawn_character_data.get("range", 1000) / 1000.0,
                sight_range=troop.card_stats.death_spawn_character_data.get("sightRange", 5000) / 1000.0,
                hit_speed=troop.card_stats.death_spawn_character_data.get("hitSpeed", 1000),
                deploy_time=troop.card_stats.death_spawn_character_data.get("deployTime", 1000),
                load_time=troop.card_stats.death_spawn_character_data.get("loadTime", 1000),
                collision_radius=troop.card_stats.death_spawn_character_data.get("collisionRadius", 500) / 1000.0,
                attacks_ground=troop.card_stats.death_spawn_character_data.get("attacksGround", True),
                attacks_air=False,
                targets_only_buildings=(troop.card_stats.death_spawn_character_data.get("tidTarget") == "TID_TARGETS_BUILDINGS"),
                target_type=troop.card_stats.death_spawn_character_data.get("tidTarget")
            )
        
        if not death_spawn_stats:
            return
        
        # Spawn multiple units in a small radius around the death position
        spawn_radius = 0.5  # tiles
        
        for _ in range(death_spawn_count):
            # Random position around the death location
            angle = random.random() * 2 * 3.14159
            distance = random.random() * spawn_radius
            spawn_x = troop.position.x + distance * math.cos(angle)
            spawn_y = troop.position.y + distance * math.sin(angle)
            
            # Create and spawn the death unit
            self._spawn_troop(Position(spawn_x, spawn_y), troop.player_id, death_spawn_stats)
    
    def _check_win_conditions(self) -> None:
        """Check if game should end"""
        # Update player tower HP from entities
        self._update_tower_hp()
        
        # Check if king towers are destroyed
        for i, player in enumerate(self.players):
            if not player.is_alive():
                self.game_over = True
                self.winner = 1 - i
                return
        
        # Check overtime conditions (5 minutes)
        if self.time >= 300.0:
            if not self.overtime:
                self.overtime = True
                self.triple_elixir = True
            
            # First tower destroyed wins in overtime
            player0_crowns = self.players[0].get_crown_count()
            player1_crowns = self.players[1].get_crown_count()
            
            if player0_crowns > player1_crowns:
                self.game_over = True
                self.winner = 0
            elif player1_crowns > player0_crowns:
                self.game_over = True
                self.winner = 1
            
            # After 6 minutes, crown count determines winner
            if self.time >= 360.0:
                if player0_crowns > player1_crowns:
                    self.winner = 0
                elif player1_crowns > player0_crowns:
                    self.winner = 1
                else:
                    self.winner = None  # Draw
                self.game_over = True
    
    def _update_tower_hp(self) -> None:
        """Update player tower HP from building entities"""
        for entity in self.entities.values():
            if isinstance(entity, Building):
                player = self.players[entity.player_id]
                pos = entity.position
                
                # Update HP based on tower position (compare coordinates)
                if entity.player_id == 0:  # Blue player
                    if (pos.x == self.arena.BLUE_KING_TOWER.x and 
                        pos.y == self.arena.BLUE_KING_TOWER.y):
                        player.king_tower_hp = entity.hitpoints
                    elif (pos.x == self.arena.BLUE_LEFT_TOWER.x and 
                          pos.y == self.arena.BLUE_LEFT_TOWER.y):
                        player.left_tower_hp = entity.hitpoints
                    elif (pos.x == self.arena.BLUE_RIGHT_TOWER.x and 
                          pos.y == self.arena.BLUE_RIGHT_TOWER.y):
                        player.right_tower_hp = entity.hitpoints
                else:  # Red player
                    if (pos.x == self.arena.RED_KING_TOWER.x and 
                        pos.y == self.arena.RED_KING_TOWER.y):
                        player.king_tower_hp = entity.hitpoints
                    elif (pos.x == self.arena.RED_LEFT_TOWER.x and 
                          pos.y == self.arena.RED_LEFT_TOWER.y):
                        player.left_tower_hp = entity.hitpoints
                    elif (pos.x == self.arena.RED_RIGHT_TOWER.x and 
                          pos.y == self.arena.RED_RIGHT_TOWER.y):
                        player.right_tower_hp = entity.hitpoints
    
    def get_state_summary(self) -> Dict:
        """Get current battle state summary"""
        return {
            "time": self.time,
            "tick": self.tick,
            "entities": len(self.entities),
            "players": [
                {
                    "elixir": p.elixir,
                    "crowns": p.get_crown_count(),
                    "king_hp": p.king_tower_hp,
                    "left_hp": p.left_tower_hp,
                    "right_hp": p.right_tower_hp
                }
                for p in self.players
            ],
            "game_over": self.game_over,
            "winner": self.winner
        }
