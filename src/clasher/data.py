from typing import Dict, Any, Optional, List
import json

from .card_types import CardDefinition, CardStatsCompat
from .card_aliases import alias_card_map, resolve_card_name
from .factory.card_factory import card_from_gamedata


class CardDataLoader:
    def __init__(self, data_file: str = "gamedata.json"):
        self.data_file = data_file
        self._cards: Dict[str, CardStatsCompat] = {}
        self._card_definitions: Dict[str, CardDefinition] = {}

    def load_card_definitions(self) -> Dict[str, CardDefinition]:
        """Load card definitions using the factory system."""
        if self._card_definitions:
            return self._card_definitions

        with open(self.data_file, 'r') as f:
            data = json.load(f)

        card_definitions: Dict[str, CardDefinition] = {}

        for entry in data.get("items", {}).get("spells", []):
            card_name = entry.get("name", "")
            if not card_name or card_name.startswith("King_"):
                continue
            if "manaCost" not in entry:
                continue

            try:
                # card_from_gamedata will preserve the raw entry for compat usage
                card_definitions[card_name] = card_from_gamedata(entry)
            except Exception as exc:
                print(f"Warning: Could not load card definition for {card_name}: {exc}")

        self._card_definitions = alias_card_map(card_definitions)
        return self._card_definitions

    def load_cards(self) -> Dict[str, CardStatsCompat]:
        """Materialize compatibility stats from card definitions."""
        definitions = self.load_card_definitions()
        cards = {
            name: CardStatsCompat.from_card_definition(card_def)
            for name, card_def in definitions.items()
        }
        self._cards = cards
        return cards

    def get_card(self, name: str) -> Optional[CardStatsCompat]:
        """Get card stats by name using compatibility wrappers."""
        if not self._cards:
            self.load_cards()
        resolved_name = resolve_card_name(name, self._cards)
        return self._cards.get(resolved_name)

    def get_card_definition(self, name: str) -> Optional[CardDefinition]:
        """Get card definition by name."""
        if not self._card_definitions:
            self.load_card_definitions()
        resolved_name = resolve_card_name(name, self._card_definitions)
        return self._card_definitions.get(resolved_name)

    def get_card_compat(self, name: str) -> Optional[CardStatsCompat]:
        """Alias for get_card to preserve API compatibility."""
        return self.get_card(name)
    
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
