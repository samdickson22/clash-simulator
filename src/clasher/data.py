from dataclasses import dataclass
from typing import Dict, Any, Optional
import json


@dataclass
class CardStats:
    # Basic card info
    name: str
    id: int
    mana_cost: int
    rarity: str
    
    # Card metadata
    icon_file: Optional[str] = None
    unlock_arena: Optional[str] = None
    tribe: Optional[str] = None
    english_name: Optional[str] = None
    card_type: Optional[str] = None
    
    # Combat stats
    hitpoints: Optional[int] = None
    damage: Optional[int] = None
    range: Optional[float] = None  # tiles
    sight_range: Optional[float] = None  # tiles
    speed: Optional[float] = None  # tiles/min
    hit_speed: Optional[int] = None  # milliseconds
    load_time: Optional[int] = None  # milliseconds
    deploy_time: Optional[int] = None  # milliseconds
    collision_radius: Optional[float] = None  # tiles
    
    # Deployment properties
    summon_count: Optional[int] = None
    summon_radius: Optional[float] = None  # tiles
    summon_deploy_delay: Optional[int] = None  # milliseconds
    
    # Targeting
    attacks_ground: Optional[bool] = None
    attacks_air: Optional[bool] = None
    targets_only_buildings: bool = False  # True for Giant, Balloon, etc.
    target_type: Optional[str] = None  # Raw tidTarget value
    
    # Spell-specific
    projectile_data: Optional[Dict[str, Any]] = None
    
    # Evolution data
    has_evolution: bool = False
    evolution_data: Optional[Dict[str, Any]] = None
    
    # Card level (1-14, standard gameplay uses level 11)
    level: int = 11
    
    def get_scaled_stat(self, stat_value: Optional[int], level: int = None) -> Optional[int]:
        """Scale a stat value based on card level (1.1x multiplier per level)"""
        if stat_value is None:
            return None
        if level is None:
            level = self.level
        # Each level multiplies by 1.1, so level N = base * (1.1^(N-1))
        multiplier = 1.1 ** (level - 1)
        return int(stat_value * multiplier)
    
    @property
    def scaled_hitpoints(self) -> Optional[int]:
        """Get hitpoints scaled to current level"""
        return self.get_scaled_stat(self.hitpoints)
    
    @property 
    def scaled_damage(self) -> Optional[int]:
        """Get damage scaled to current level"""
        return self.get_scaled_stat(self.damage)


class CardDataLoader:
    def __init__(self, data_file: str = "gamedata.json"):
        self.data_file = data_file
        self._cards: Dict[str, CardStats] = {}
        
    def load_cards(self) -> Dict[str, CardStats]:
        """Load card data from gamedata.json"""
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        cards = {}
        
        for spell in data.get("items", {}).get("spells", []):
            card_name = spell.get("name", "")
            card_id = spell.get("id", 0)
            mana_cost = spell.get("manaCost", 0)
            rarity = spell.get("rarity", "")
            
            # Check multiple sources for character data
            char_data = spell.get("summonCharacterData", {})
            if not char_data:
                char_data = spell.get("summonSpellData", {})
            
            hitpoints = char_data.get("hitpoints")
            damage = char_data.get("damage")
            range_val = char_data.get("range")
            sight_range = char_data.get("sightRange")
            speed = char_data.get("speed") 
            load_time = char_data.get("loadTime")
            count = char_data.get("count")
            
            # Handle projectile data for spell cards
            projectile_data = char_data.get("projectileData", {})
            if projectile_data and not damage:
                damage = projectile_data.get("damage")
            
            # Direct spell data (like Arrows, Fireball)
            if not damage and spell.get("damage"):
                damage = spell.get("damage")
            if not range_val and spell.get("radius"):
                range_val = spell.get("radius")
            
            # Convert game units to proper units
            # Distances: game units ÷ 1000 = tiles
            # Speed: raw value = tiles/min
            converted_range = range_val / 1000.0 if range_val else None
            converted_sight_range = sight_range / 1000.0 if sight_range else None
            converted_collision_radius = char_data.get("collisionRadius", 0) / 1000.0 if char_data.get("collisionRadius") else None
            converted_summon_radius = spell.get("summonRadius", 0) / 1000.0 if spell.get("summonRadius") else None
            converted_speed = float(speed) if speed else None  # Already in tiles/min
            
            # Determine card type
            card_type = None
            tid_type = spell.get("tidType")
            if tid_type == "TID_CARD_TYPE_CHARACTER":
                card_type = "Troop"
            elif tid_type == "TID_CARD_TYPE_SPELL":
                card_type = "Spell"
            elif tid_type == "TID_CARD_TYPE_BUILDING":
                card_type = "Building"
            
            card = CardStats(
                # Basic info
                name=card_name,
                id=card_id,
                mana_cost=mana_cost,
                rarity=rarity,
                
                # Metadata
                icon_file=spell.get("iconFile"),
                unlock_arena=spell.get("unlockArena"),
                tribe=spell.get("tribe"),
                english_name=spell.get("englishName"),
                card_type=card_type,
                
                # Combat stats
                hitpoints=hitpoints,
                damage=damage,
                range=converted_range,
                sight_range=converted_sight_range,
                speed=converted_speed,
                hit_speed=char_data.get("hitSpeed"),
                load_time=load_time,
                deploy_time=char_data.get("deployTime"),
                collision_radius=converted_collision_radius,
                
                # Deployment
                summon_count=spell.get("summonNumber"),
                summon_radius=converted_summon_radius,
                summon_deploy_delay=spell.get("summonDeployDelay"),
                
                # Targeting
                attacks_ground=char_data.get("attacksGround"),
                attacks_air=char_data.get("attacksAir"),
                target_type=char_data.get("tidTarget"),
                targets_only_buildings=(char_data.get("tidTarget") == "TID_TARGETS_BUILDINGS"),
                
                # Spell data
                projectile_data=spell.get("projectileData"),
                
                # Evolution
                has_evolution=bool(spell.get("evolvedSpellsData")),
                evolution_data=spell.get("evolvedSpellsData")
            )
            
            cards[card_name] = card
        
        self._cards = cards
        return cards
    
    def get_card(self, name: str) -> Optional[CardStats]:
        """Get card stats by name"""
        if not self._cards:
            self.load_cards()
        return self._cards.get(name)
    
    def print_card_summary(self, name: str) -> None:
        """Print a detailed summary of a card's attributes"""
        card = self.get_card(name)
        if not card:
            print(f"Card '{name}' not found")
            return
            
        print(f"=== {card.name} ===")
        print(f"Type: {card.card_type} | Rarity: {card.rarity} | Cost: {card.mana_cost} elixir")
        if card.tribe:
            print(f"Tribe: {card.tribe}")
        if card.unlock_arena:
            print(f"Unlocks: {card.unlock_arena}")
            
        if card.hitpoints or card.damage:
            print(f"\\nCombat:")
            if card.hitpoints:
                print(f"  HP: {card.hitpoints}")
            if card.damage:
                print(f"  Damage: {card.damage}")
            if card.hit_speed:
                print(f"  Attack Speed: {card.hit_speed}ms")
                
        if card.range or card.sight_range or card.speed:
            print(f"\\nMovement & Range:")
            if card.range:
                print(f"  Attack Range: {card.range} tiles")
            if card.sight_range:
                print(f"  Sight Range: {card.sight_range} tiles")
            if card.speed:
                print(f"  Speed: {card.speed} tiles/min")
            if card.collision_radius:
                print(f"  Collision Radius: {card.collision_radius} tiles")
                
        if card.summon_count:
            print(f"\\nDeployment:")
            print(f"  Units Spawned: {card.summon_count}")
            if card.summon_radius:
                print(f"  Spawn Radius: {card.summon_radius} tiles")
            if card.summon_deploy_delay:
                print(f"  Spawn Delay: {card.summon_deploy_delay}ms")
                
        if card.attacks_ground is not None or card.attacks_air is not None:
            print(f"\\nTargeting:")
            if card.attacks_ground:
                print(f"  Attacks Ground: Yes")
            if card.attacks_air:
                print(f"  Attacks Air: Yes")
                
        if card.has_evolution:
            print(f"\\nEvolution: Available")
            
        if card.deploy_time or card.load_time:
            print(f"\\nTiming:")
            if card.deploy_time:
                print(f"  Deploy Time: {card.deploy_time}ms")
            if card.load_time:
                print(f"  Load Time: {card.load_time}ms")


SPEED_VALUES = {
    "Slow": 0.7,
    "Medium": 1.0, 
    "Fast": 1.4,
    "VeryFast": 1.8
}