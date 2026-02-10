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
from .mechanics.shared.death_effects import DeathSpawn
from .name_map import resolve_name

# Canonical set of air unit names (internal JSON names)
AIR_UNITS = frozenset([
    'Minions', 'MinionHorde', 'Balloon', 'SkeletonBalloon', 'BabyDragon',
    'InfernoDragon', 'ElectroDragon', 'SkeletonDragons', 'MegaMinion',
    'Bats', 'LavaHound', 'LavaPups',
])


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
        # Preload factory card definitions to enable mechanic detection/prints
        try:
            self.card_loader.load_card_definitions()
        except Exception as e:
            pass  # print(f"[Warn] load_card_definitions failed: {e}")
        self._create_towers()

    def _create_towers(self) -> None:
        """Create tower entities for both players"""
        tower_stats = CardStats(
            name="Tower",
            id=0,
            mana_cost=0,
            rarity="",
            hitpoints=1400,  # Level 1 base stats - will be scaled to level 11
            damage=50,       # Level 1 base stats - will be scaled to level 11
            range=7.5,       # From JSON: "range": 7500 (7.5 tiles)
            sight_range=7.5, # From JSON: "sightRange": 7500 (7.5 tiles)
            load_time=800,
            hit_speed=800,   # From JSON: "hitSpeed": 800
            attacks_air=True,  # Towers can attack air units
            target_type="TID_TARGETS_AIR_AND_GROUND",  # From JSON: "tidTarget": "TID_TARGETS_AIR_AND_GROUND"
            projectile_speed=600,  # From JSON: projectileData "speed": 600
            projectile_data={'speed': 600, 'damage': 50},  # Tower projectile data (will be scaled to level 11)
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
            projectile_speed=600,  # Same as Princess Tower
            projectile_data={'speed': 600, 'damage': 109},  # King tower projectile data (base level 1)
            level=1   # Base level stats (no scaling needed)
        )

        # Player 0 towers (blue) - create new Position objects to avoid sharing references
        blue_left = Position(self.arena.BLUE_LEFT_TOWER.x, self.arena.BLUE_LEFT_TOWER.y)
        blue_right = Position(self.arena.BLUE_RIGHT_TOWER.x, self.arena.BLUE_RIGHT_TOWER.y)
        blue_king = Position(self.arena.BLUE_KING_TOWER.x, self.arena.BLUE_KING_TOWER.y)
        self._spawn_entity(Building, blue_left, 0, tower_stats)
        self._spawn_entity(Building, blue_right, 0, tower_stats)
        king_0 = self._spawn_entity(Building, blue_king, 0, king_stats)
        if king_0:
            king_0.is_king_tower = True

        # Player 1 towers (red) - create new Position objects to avoid sharing references
        red_left = Position(self.arena.RED_LEFT_TOWER.x, self.arena.RED_LEFT_TOWER.y)
        red_right = Position(self.arena.RED_RIGHT_TOWER.x, self.arena.RED_RIGHT_TOWER.y)
        red_king = Position(self.arena.RED_KING_TOWER.x, self.arena.RED_KING_TOWER.y)
        self._spawn_entity(Building, red_left, 1, tower_stats)
        self._spawn_entity(Building, red_right, 1, tower_stats)
        king_1 = self._spawn_entity(Building, red_king, 1, king_stats)
        if king_1:
            king_1.is_king_tower = True

    def step(self, speed_factor: float = 1.0) -> None:
        """Advance battle by one tick"""
        if self.game_over:
            return

        dt = self.dt * speed_factor
        self.time += dt
        self.tick += 1

        # Update elixir modes
        # 0:00-3:00 regular, 3:00-4:00 double, 4:00-5:00 triple/overtime
        if self.time >= 240.0 and not self.triple_elixir:
            self.triple_elixir = True
            self.double_elixir = True
        elif self.time >= 180.0 and not self.double_elixir:
            self.double_elixir = True

        # Regenerate elixir
        base_regen = 2.8
        if self.triple_elixir:
            base_regen = 0.93
        elif self.double_elixir:
            base_regen = 1.4

        for player in self.players:
            player.regenerate_elixir(dt, base_regen)

        # Update all entities (snapshot keys to avoid dict-changed-size errors)
        for eid in list(self.entities.keys()):
            entity = self.entities.get(eid)
            if entity and entity.is_alive:
                entity.update(dt, self)

        # Remove dead entities
        self._cleanup_dead_entities()

        # Check win conditions
        self._check_win_conditions()

    def deploy_card(self, player_id: int, card_name: str, position: Position) -> bool:
        """Deploy a card at the given position"""
        player = self.players[player_id]
        # Resolve alias for data lookup
        internal_name = resolve_name(card_name)
        # Prefer legacy stats for full compatibility; fall back to compat wrapper
        card_stats = self.card_loader.get_card(card_name) or self.card_loader.get_card_compat(card_name)

        if not card_stats or not player.can_play_card(card_name, card_stats):
            return False

        # Check spell registry with both deck name and internal name
        is_spell = card_name in SPELL_REGISTRY or internal_name in SPELL_REGISTRY
        spell_obj = SPELL_REGISTRY.get(card_name) or SPELL_REGISTRY.get(internal_name) if is_spell else None
        if not self.arena.can_deploy_at(position, player_id, self, is_spell, spell_obj):
            return False

        # Special deployment validation for Royal Recruits (center 6 tiles only)
        if card_name in ['RoyalRecruits', 'RoyalRecruits_Chess']:
            if not (6 <= position.x <= 11):
                return False  # Royal Recruits can only be deployed in center 6 tiles

        # Play the card
        if not player.play_card(card_name, card_stats):
            return False

        # Check if it's a spell
        if card_name in SPELL_REGISTRY or internal_name in SPELL_REGISTRY:
            spell = SPELL_REGISTRY.get(card_name) or SPELL_REGISTRY.get(internal_name)
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
        """Spawn a troop entity (handles both single troops and swarms)"""
        # Guard: if this card is actually a building, route to building spawner
        ctype = getattr(card_stats, "card_type", None)
        ctype_str = str(ctype).lower() if ctype is not None else ""
        if ctype_str == "building":
            self._spawn_entity(Building, position, player_id, card_stats)
            return

        # Check if this is a swarm card (spawns multiple units)
        summon_count = getattr(card_stats, 'summon_count', None) or 1
        summon_radius = getattr(card_stats, 'summon_radius', None) or 0.5  # Default 0.5 tiles

        # Check for mixed swarms (like Goblin Gang)
        second_count = getattr(card_stats, 'summon_character_second_count', None) or 0
        second_data = getattr(card_stats, 'summon_character_second_data', None)

        if summon_count > 1 or second_count > 0:
            # Spawn swarm units in a circle around the target position
            # summon_radius is already converted to tiles in data loading
            self._spawn_swarm_troops(position, player_id, card_stats, summon_count, summon_radius, second_count, second_data)
        else:
            # Spawn single unit at exact position
            self._spawn_single_troop(position, player_id, card_stats)

    def _spawn_single_troop(self, position: Position, player_id: int, card_stats: CardStats) -> None:
        """Spawn a single troop entity"""
        # Get speed value (tiles/min from card stats)
        speed = card_stats.speed or 60.0  # Default to 60 tiles/min if not specified

        # Determine if this is an air unit (based on target_type or known list)
        is_air_unit = (getattr(card_stats, 'name', '') in AIR_UNITS) or (
            getattr(card_stats, 'target_type', '') == 'TID_TARGETS_AIR'
        )

        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints or 100
        scaled_damage = card_stats.scaled_damage or 10

        troop = Troop(
            id=self.next_entity_id,
            position=Position(position.x, position.y),  # Create new position object
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

        # Set battle reference
        troop.battle_state = self

        # Attach mechanics from factory definition if available
        try:
            defn_name = getattr(card_stats, 'name', None)
            card_def = self.card_loader.get_card_definition(defn_name) if defn_name else None
            if card_def and getattr(card_def, 'mechanics', None):
                troop.mechanics = list(card_def.mechanics)
                for mech in troop.mechanics:
                    mech.on_attach(troop)
                if troop.mechanics:
                    pass  # print(f"[Attach] {defn_name}: {len(troop.mechanics)} mechanic(s)")
        except Exception as e:
            pass  # print(f"[Warn] Failed attaching mechanics for {getattr(card_stats, 'name', 'Unknown')}: {e}")

        self.entities[self.next_entity_id] = troop
        self.next_entity_id += 1

        # Fire spawn hooks
        troop.on_spawn()

    def _spawn_swarm_troops(self, center_pos: Position, player_id: int, card_stats: CardStats, count: int, radius: float, second_count: int = 0, second_data: dict = None) -> None:
        """Spawn multiple troop entities in a circle around center position"""
        import math
        import random

        total_units = count + second_count

        # Check for special deployment patterns
        is_royal_recruits = card_stats.name in ['RoyalRecruits', 'RoyalRecruits_Chess']

        # Check if this is a mixed swarm with front/back positioning (like Goblin Gang)
        has_front_back = (count > 0 and second_count > 0 and
                         getattr(card_stats, 'summon_character_data', None) and
                         getattr(card_stats, 'summon_character_second_data', None))

        if is_royal_recruits:
            # Royal Recruits spawn in a horizontal line across battlefield
            self._spawn_royal_recruits_line(center_pos, player_id, card_stats, count)
        elif has_front_back:
            # Spawn in front/back formation for mixed swarms
            self._spawn_front_back_formation(center_pos, player_id, card_stats, count, second_count, second_data, radius)
        else:
            # Regular circular formation
            # Spawn primary units
            for i in range(count):
                self._spawn_unit_at_angle(center_pos, player_id, card_stats, i, total_units, radius)

            # Spawn secondary units if available
            if second_count > 0 and second_data:
                unit_name = second_data.get("name", card_stats.name + "_Secondary")
                second_card_stats = self._create_card_stats_from_data(second_data, unit_name)

                for i in range(second_count):
                    self._spawn_unit_at_angle(center_pos, player_id, second_card_stats, count + i, total_units, radius)

    def _spawn_unit_at_angle(self, center_pos: Position, player_id: int, card_stats: CardStats, index: int, total_count: int, radius: float) -> None:
        """Spawn a single unit at a specific angle in the swarm formation"""
        import math
        import random

        # Calculate position in circle
        if total_count == 1:
            # Single unit at center
            spawn_x = center_pos.x
            spawn_y = center_pos.y
        else:
            angle = (2 * math.pi * index) / total_count
            # Add some randomness to avoid perfect circles
            angle_variance = random.uniform(-0.3, 0.3)
            radius_variance = random.uniform(0.7, 1.3)

            spawn_x = center_pos.x + (radius * radius_variance) * math.cos(angle + angle_variance)
            spawn_y = center_pos.y + (radius * radius_variance) * math.sin(angle + angle_variance)

        # Validate and snap position to playable area
        spawn_position = Position(spawn_x, spawn_y)
        spawn_position = self._snap_to_valid_position(spawn_position, player_id)

        # Get unit properties
        speed = card_stats.speed or 60.0

        # Determine if this is an air unit
        is_air_unit = card_stats.name in AIR_UNITS

        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints or card_stats.hitpoints or 100
        scaled_damage = card_stats.scaled_damage or card_stats.damage or 10
        
        troop = Troop(
            id=self.next_entity_id,
            position=spawn_position,
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

        # Attach mechanics if using compat wrapper with card_definition
        if hasattr(card_stats, 'card_definition') and card_stats.card_definition:
            troop.mechanics = list(card_stats.card_definition.mechanics)
        # Set battle reference
        troop.battle_state = self

        # Attach mechanics from factory definition if available
        try:
            defn_name = getattr(card_stats, 'name', None)
            card_def = self.card_loader.get_card_definition(defn_name) if defn_name else None
            if card_def and getattr(card_def, 'mechanics', None):
                troop.mechanics = list(card_def.mechanics)
                for mech in troop.mechanics:
                    mech.on_attach(troop)
                if troop.mechanics:
                    pass  # print(f"[Attach] {defn_name}: {len(troop.mechanics)} mechanic(s)")
        except Exception as e:
            pass  # print(f"[Warn] Failed attaching mechanics for {getattr(card_stats, 'name', 'Unknown')}: {e}")

        self.entities[self.next_entity_id] = troop
        self.next_entity_id += 1

        # Fire spawn hooks
        troop.on_spawn()

    def _spawn_front_back_formation(self, center_pos: Position, player_id: int, card_stats: CardStats, front_count: int, back_count: int, back_data: dict, radius: float) -> None:
        """Spawn units in front/back formation (melee in front, ranged in back)"""
        import math
        import random

        # Create card stats for both unit types
        # Primary units (front) - use actual name from summonCharacterData
        primary_data = getattr(card_stats, 'summon_character_data', {})
        primary_name = primary_data.get("name", card_stats.name)
        front_card_stats = self._create_card_stats_from_data(primary_data, primary_name)

        # Secondary units (back) - use actual name from summonCharacterSecondData
        back_name = back_data.get("name", card_stats.name + "_Secondary")
        back_card_stats = self._create_card_stats_from_data(back_data, back_name)

        # Determine formation based on player direction
        # Blue player (0): front = towards enemy (positive Y), back = towards own side (negative Y)
        # Red player (1): front = towards enemy (negative Y), back = towards own side (positive Y)

        front_offset = 0.6  # tiles in front of center
        back_offset = 0.8   # tiles behind center

        if player_id == 0:  # Blue player
            front_y = center_pos.y + front_offset  # Towards red side
            back_y = center_pos.y - back_offset    # Towards blue side
        else:  # Red player
            front_y = center_pos.y - front_offset  # Towards blue side
            back_y = center_pos.y + back_offset    # Towards red side

        # Spawn front units (melee) in a line
        for i in range(front_count):
            # Spread horizontally across the front
            if front_count == 1:
                front_x = center_pos.x
            else:
                spread = radius * 1.2  # Slightly wider spread for front line
                front_x = center_pos.x + (i - (front_count - 1) / 2) * (spread * 2 / (front_count - 1))

            # Add slight randomness
            front_x += random.uniform(-0.2, 0.2)
            front_y_final = front_y + random.uniform(-0.1, 0.1)

            front_pos = Position(front_x, front_y_final)
            front_pos = self._snap_to_valid_position(front_pos, player_id)

            self._spawn_unit_at_position(front_pos, player_id, front_card_stats)

        # Spawn back units (ranged) in a line
        for i in range(back_count):
            # Spread horizontally across the back
            if back_count == 1:
                back_x = center_pos.x
            else:
                spread = radius * 1.2
                back_x = center_pos.x + (i - (back_count - 1) / 2) * (spread * 2 / (back_count - 1))

            # Add slight randomness
            back_x += random.uniform(-0.2, 0.2)
            back_y_final = back_y + random.uniform(-0.1, 0.1)

            back_pos = Position(back_x, back_y_final)
            back_pos = self._snap_to_valid_position(back_pos, player_id)

            self._spawn_unit_at_position(back_pos, player_id, back_card_stats)

    def _spawn_royal_recruits_line(self, center_pos: Position, player_id: int, card_stats: CardStats, count: int) -> None:
        """Spawn Royal Recruits in a horizontal line across the battlefield, avoiding towers"""
        # Royal Recruits: 6 units spaced 2.5 tiles apart, center at deploy position
        spacing = 2.5  # tiles between each recruit

        # Get tower-blocked X ranges for this Y coordinate
        blocked_ranges = self.arena.get_tower_blocked_x_ranges(center_pos.y, self)

        # Calculate initial line positions
        total_width = (count - 1) * spacing
        leftmost_x = center_pos.x - (total_width / 2)

        # Generate all recruit X positions
        recruit_positions = []
        for i in range(count):
            recruit_x = leftmost_x + (i * spacing)
            recruit_positions.append(recruit_x)

        # Check if any positions would overlap with towers
        needs_adjustment = False
        for recruit_x in recruit_positions:
            for x_min, x_max in blocked_ranges:
                if x_min <= recruit_x <= x_max:
                    needs_adjustment = True
                    break
            if needs_adjustment:
                break

        # If line overlaps with towers, find alternative positioning
        if needs_adjustment:
            recruit_positions = self._find_safe_recruit_positions(center_pos, count, spacing, blocked_ranges)

        # Ensure all positions are within arena bounds
        recruit_positions = [max(0.5, min(17.5, x)) for x in recruit_positions]

        # Spawn each recruit
        for recruit_x in recruit_positions:
            recruit_pos = Position(recruit_x, center_pos.y)
            recruit_pos = self._snap_to_valid_position(recruit_pos, player_id)
            self._spawn_unit_at_position(recruit_pos, player_id, card_stats)

    def _find_safe_recruit_positions(self, center_pos: Position, count: int, spacing: float, blocked_ranges: List[Tuple[float, float]]) -> List[float]:
        """Find safe X positions for Royal Recruits that avoid tower collisions"""

        # Create list of all blocked X coordinates
        blocked_x_coords = set()
        for x_min, x_max in blocked_ranges:
            # Add all positions in blocked range with 0.5 precision
            x = x_min
            while x <= x_max:
                blocked_x_coords.add(round(x * 2) / 2)  # Round to nearest 0.5
                x += 0.5

        # Find all safe X positions across the arena
        safe_positions = []
        for x_half in range(1, 36):  # 0.5 to 17.5 in 0.5 increments
            x = x_half / 2.0
            if x not in blocked_x_coords and 0.5 <= x <= 17.5:
                safe_positions.append(x)

        # If we have enough safe positions, try to maintain spacing
        if len(safe_positions) >= count:
            # Try to find positions with good spacing starting from center
            selected_positions = []

            # Find safe position closest to center
            center_candidates = [pos for pos in safe_positions if abs(pos - center_pos.x) <= 1.0]
            if not center_candidates:
                center_candidates = safe_positions

            center_safe = min(center_candidates, key=lambda x: abs(x - center_pos.x))
            selected_positions.append(center_safe)

            # For remaining positions, try to maintain spacing while staying safe
            while len(selected_positions) < count:
                best_candidate = None
                best_score = float('inf')

                for candidate in safe_positions:
                    if candidate in selected_positions:
                        continue

                    # Score based on distance from ideal spacing positions
                    min_spacing_score = float('inf')
                    for existing_pos in selected_positions:
                        spacing_distance = abs(abs(candidate - existing_pos) - spacing)
                        min_spacing_score = min(min_spacing_score, spacing_distance)

                    # Prefer positions that maintain good spacing
                    if min_spacing_score < best_score:
                        best_score = min_spacing_score
                        best_candidate = candidate

                if best_candidate is not None:
                    selected_positions.append(best_candidate)
                else:
                    # If no good candidate, just pick the first available
                    for pos in safe_positions:
                        if pos not in selected_positions:
                            selected_positions.append(pos)
                            break

            positions = selected_positions
        else:
            # Not enough safe positions, use what we have
            positions = safe_positions[:count]

        # Ensure we have exactly the right count
        while len(positions) < count:
            # Add fallback positions at arena edges
            for x in [0.5, 1.0, 17.0, 17.5, 16.5, 16.0]:
                if x not in positions and x not in blocked_x_coords:
                    positions.append(x)
                    if len(positions) >= count:
                        break

        # Sort and return exact count
        positions.sort()
        return positions[:count]

    def _spawn_unit_at_position(self, position: Position, player_id: int, card_stats: CardStats) -> None:
        """Spawn a single unit at a specific position"""
        # Get unit properties
        speed = card_stats.speed or 60.0

        # Determine if this is an air unit
        is_air_unit = card_stats.name in AIR_UNITS

        # Use level-scaled stats for hitpoints and damage
        scaled_hp = card_stats.scaled_hitpoints or card_stats.hitpoints or 100
        scaled_damage = card_stats.scaled_damage or card_stats.damage or 10

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

    def _snap_to_valid_position(self, position: Position, player_id: int) -> Position:
        """Snap position to nearest valid playable area"""
        # Check if position is already valid (walkable and not on a tower)
        if self.arena.is_walkable(position) and not self.arena.is_tower_tile(position, self):
            return position

        # Try to find nearest valid position within reasonable distance
        search_radius = 2.0  # tiles
        best_position = position
        min_distance = float('inf')

        # Search in a grid around the original position
        for x_offset in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]:
            for y_offset in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]:
                test_x = position.x + x_offset
                test_y = position.y + y_offset
                test_pos = Position(test_x, test_y)

                # Check bounds first
                if not self.arena.is_valid_position(test_pos):
                    continue

                # Check if walkable and not on tower
                if self.arena.is_walkable(test_pos) and not self.arena.is_tower_tile(test_pos, self):
                    distance = position.distance_to(test_pos)
                    if distance < min_distance:
                        min_distance = distance
                        best_position = test_pos

        # If no valid position found nearby, clamp to arena bounds and find closest walkable
        if min_distance == float('inf'):
            # Clamp to arena bounds
            clamped_x = max(0.5, min(17.5, position.x))
            clamped_y = max(0.5, min(31.5, position.y))
            clamped_pos = Position(clamped_x, clamped_y)

            # If clamped position is walkable and not on tower, use it
            if self.arena.is_walkable(clamped_pos) and not self.arena.is_tower_tile(clamped_pos, self):
                best_position = clamped_pos
            else:
                # Fallback: move towards arena center until we find walkable area
                center_x, center_y = 9.0, 16.0
                dx = center_x - clamped_x
                dy = center_y - clamped_y

                for step in [0.5, 1.0, 1.5, 2.0]:
                    fallback_x = clamped_x + dx * step * 0.1
                    fallback_y = clamped_y + dy * step * 0.1
                    fallback_pos = Position(fallback_x, fallback_y)

                    if (self.arena.is_valid_position(fallback_pos) and
                        self.arena.is_walkable(fallback_pos) and
                        not self.arena.is_tower_tile(fallback_pos, self)):
                        best_position = fallback_pos
                        break

        return best_position

    def _create_card_stats_from_data(self, unit_data: dict, name: str) -> CardStats:
        """Create CardStats from raw unit data (for secondary units in mixed swarms)"""
        # Handle projectile damage for ranged units (like Spear Goblins)
        base_damage = unit_data.get("damage", 10)
        projectile_data = unit_data.get("projectileData", {})
        if projectile_data and "damage" in projectile_data:
            base_damage = projectile_data["damage"]

        return CardStats(
            name=name,
            id=0,  # Temporary ID
            mana_cost=0,  # Secondary units don't have mana cost
            rarity=unit_data.get("rarity", "Common"),
            card_type="Troop",

            # Combat stats
            hitpoints=unit_data.get("hitpoints", 100),
            damage=base_damage,
            range=(unit_data.get("range", 1000) / 1000.0) if unit_data.get("range") else 1.0,
            sight_range=(unit_data.get("sightRange", 5000) / 1000.0) if unit_data.get("sightRange") else 5.0,
            speed=unit_data.get("speed", 60),
            hit_speed=unit_data.get("hitSpeed", 1000),
            load_time=unit_data.get("loadTime", 1000),
            deploy_time=unit_data.get("deployTime", 1000),
            collision_radius=(unit_data.get("collisionRadius", 500) / 1000.0) if unit_data.get("collisionRadius") else 0.5,

            # Targeting
            attacks_ground=unit_data.get("attacksGround", True),
            attacks_air=unit_data.get("attacksAir", False),
            target_type=unit_data.get("tidTarget", "TID_TARGETS_GROUND")
        )

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

        # Add battle_state reference for mechanics
        entity.battle_state = self

        # Attach mechanics if using compat wrapper with card_definition
        if hasattr(card_stats, 'card_definition') and getattr(card_stats, 'card_definition'):
            entity.mechanics = list(card_stats.card_definition.mechanics)
            for mech in entity.mechanics:
                mech.on_attach(entity)
            if entity.mechanics:
                pass  # print(f"[Attach] {getattr(card_stats, 'name', 'Building')}: {len(entity.mechanics)} mechanic(s)")
        else:
            # Try to attach mechanics from factory card definition
            try:
                defn_name = getattr(card_stats, 'name', None)
                card_def = self.card_loader.get_card_definition(defn_name) if defn_name else None
                if card_def and getattr(card_def, 'mechanics', None):
                    entity.mechanics = list(card_def.mechanics)
                    for mech in entity.mechanics:
                        mech.on_attach(entity)
                    if entity.mechanics:
                        pass  # print(f"[Attach] {defn_name}: {len(entity.mechanics)} mechanic(s)")
            except Exception as e:
                pass  # print(f"[Warn] Failed attaching mechanics for {getattr(card_stats, 'name', 'Unknown')}: {e}")

        self.entities[self.next_entity_id] = entity
        self.next_entity_id += 1

        # Call on_spawn for all mechanics
        entity.on_spawn()
        return entity

    def _cleanup_dead_entities(self) -> None:
        """Remove dead entities from the game and handle death spawns"""
        dead_ids = [eid for eid, entity in self.entities.items() if not entity.is_alive]

        # Handle death spawns before removing entities (skip if handled by mechanics)
        for eid in dead_ids:
            entity = self.entities[eid]
            if isinstance(entity, Troop) and getattr(entity.card_stats, 'death_spawn_character', None):
                has_mechanic_spawn = any(isinstance(m, DeathSpawn) for m in getattr(entity, 'mechanics', []))
                if not has_mechanic_spawn:
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
                        self._activate_king_tower(entity.player_id)
                    elif (pos.x == self.arena.BLUE_RIGHT_TOWER.x and
                          pos.y == self.arena.BLUE_RIGHT_TOWER.y):
                        player.right_tower_hp = 0
                        self._activate_king_tower(entity.player_id)
                else:  # Red player
                    if (pos.x == self.arena.RED_KING_TOWER.x and
                        pos.y == self.arena.RED_KING_TOWER.y):
                        player.king_tower_hp = 0
                    elif (pos.x == self.arena.RED_LEFT_TOWER.x and
                          pos.y == self.arena.RED_LEFT_TOWER.y):
                        player.left_tower_hp = 0
                        self._activate_king_tower(entity.player_id)
                    elif (pos.x == self.arena.RED_RIGHT_TOWER.x and
                          pos.y == self.arena.RED_RIGHT_TOWER.y):
                        player.right_tower_hp = 0
                        self._activate_king_tower(entity.player_id)

        # Remove dead non-tower entities to prevent unbounded growth
        for eid in dead_ids:
            entity = self.entities[eid]
            if not isinstance(entity, Building) or not self._is_tower(entity):
                del self.entities[eid]

    def _activate_king_tower(self, player_id: int) -> None:
        """Activate king tower for a player (when princess tower destroyed or king hit)"""
        self.players[player_id].king_tower_active = True
        for entity in self.entities.values():
            if (isinstance(entity, Building) and entity.player_id == player_id 
                and entity.is_king_tower and entity.is_alive):
                entity.king_tower_active = True

    def _is_tower(self, entity: Entity) -> bool:
        """Check if entity is a Princess or King tower."""
        return (isinstance(entity, Building) and
                entity.card_stats and
                entity.card_stats.name in ('Tower', 'KingTower'))

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

            # Crowns = enemy towers destroyed
            # P0's crowns = P1's destroyed towers, and vice versa
            p0_crowns = self.players[1].get_crown_count()  # P0 earned by destroying P1's towers
            p1_crowns = self.players[0].get_crown_count()  # P1 earned by destroying P0's towers

            if p0_crowns > p1_crowns:
                self.game_over = True
                self.winner = 0
            elif p1_crowns > p0_crowns:
                self.game_over = True
                self.winner = 1

            # After 6 minutes, crown count determines winner
            if self.time >= 360.0:
                if p0_crowns > p1_crowns:
                    self.winner = 0
                elif p1_crowns > p0_crowns:
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
