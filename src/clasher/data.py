from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import lru_cache
import json

from .card_types import CardDefinition, CardStatsCompat
from .card_aliases import alias_card_map, resolve_card_name
from .factory.card_factory import card_from_gamedata
from .paths import gamedata_path
from .balance import apply_entry_overrides
from .gamedata_normalization import build_object_registry


@lru_cache(maxsize=4)
def _load_definition_snapshot(
    data_file: str,
    modified_ns: int,
    file_size: int,
) -> Dict[str, CardDefinition]:
    """Parse and normalize one immutable game-data file revision.

    The v5 export is several megabytes. RL environments create many
    independent ``CardDataLoader`` instances, but their definition prototypes
    are immutable and entity mechanics are deep-copied on spawn. Cache the
    expensive source parse while each loader still materializes its own
    mutable compatibility wrappers.
    """
    del modified_ns, file_size  # They are cache-key revision tokens.
    with open(data_file, "r") as source:
        data = json.load(source)

    object_registry = build_object_registry(data)
    card_definitions: Dict[str, CardDefinition] = {}
    for entry in data.get("items", {}).get("spells", []):
        entry = apply_entry_overrides(entry, object_registry)
        card_name = entry.get("name", "")
        if not card_name or card_name.startswith("King_"):
            continue
        if "manaCost" not in entry:
            continue
        try:
            card_definitions[card_name] = card_from_gamedata(entry)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load card definition for {card_name}"
            ) from exc
    return alias_card_map(card_definitions)


class CardDataLoader:
    def __init__(self, data_file: str | Path | None = None):
        self.data_file = gamedata_path(data_file, must_exist=True)
        self._cards: Dict[str, CardStatsCompat] = {}
        self._card_definitions: Dict[str, CardDefinition] = {}

    def load_card_definitions(self) -> Dict[str, CardDefinition]:
        """Load card definitions using the factory system."""
        if self._card_definitions:
            return self._card_definitions

        file_stat = self.data_file.stat()
        # Copy the mapping so aliases can remain loader-local. CardDefinition
        # itself is frozen; its mechanic prototypes are copied per entity.
        self._card_definitions = dict(
            _load_definition_snapshot(
                str(self.data_file),
                file_stat.st_mtime_ns,
                file_stat.st_size,
            )
        )
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

    def clone_lazy(self) -> "CardDataLoader":
        """Return an independent loader sharing only frozen card definitions."""

        clone = object.__new__(CardDataLoader)
        clone.data_file = self.data_file
        clone._card_definitions = dict(self.load_card_definitions())
        clone._cards = {}
        return clone

    def get_card(self, name: str) -> Optional[CardStatsCompat]:
        """Get card stats by name using compatibility wrappers."""
        definitions = self.load_card_definitions()
        resolved_name = resolve_card_name(name, definitions)
        cached = self._cards.get(resolved_name)
        if cached is not None:
            return cached
        definition = definitions.get(resolved_name)
        if definition is None:
            return None
        card = CardStatsCompat.from_card_definition(definition)
        self._cards[resolved_name] = card
        return card

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
                print(f"  Speed: {card.speed} logic units/tick")
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
