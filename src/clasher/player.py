from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque

from .card_types import CardStatsCompat


@dataclass
class PlayerState:
    player_id: int
    elixir: float = 5.0
    max_elixir: float = 10.0
    
    # Card system
    hand: List[str] = field(default_factory=lambda: ["Knight", "Archer", "Giant", "Minions"])
    deck: List[str] = field(default_factory=lambda: ["Knight", "Archer", "Giant", "Minions", "Musketeer", "BabyDragon", "Balloon", "Wizard"])
    cycle_queue: Deque[str] = field(default_factory=deque)
    
    # Tower HP 
    king_tower_hp: float = 4824.0      # King tower HP
    left_tower_hp: float = 3631.0      # Level 11 Princess tower HP (1400 * 2.594)  
    right_tower_hp: float = 3631.0     # Level 11 Princess tower HP (1400 * 2.594)
    
    def __post_init__(self) -> None:
        """Initialize cycle queue with remaining deck cards"""
        if not self.cycle_queue:
            remaining = [card for card in self.deck if card not in self.hand]
            self.cycle_queue = deque(remaining)
    
    def regenerate_elixir(self, dt: float, base_regen_time: float = 2.8) -> None:
        """Regenerate elixir over time"""
        if self.elixir < self.max_elixir:
            elixir_per_second = 1.0 / base_regen_time
            self.elixir = min(self.max_elixir, self.elixir + elixir_per_second * dt)
    
    def can_play_card(self, card_name: str, card_stats: CardStatsCompat) -> bool:
        """Check if player can afford to play this card"""
        return (card_name in self.hand and 
                self.elixir >= card_stats.mana_cost and
                self.is_alive())
    
    def play_card(self, card_name: str, card_stats: CardStatsCompat) -> bool:
        """Play a card from hand, updating elixir and cycling"""
        if not self.can_play_card(card_name, card_stats):
            return False
        
        # Spend elixir
        self.elixir -= card_stats.mana_cost
        
        # Remove from hand and add next card from cycle
        hand_index = self.hand.index(card_name)
        if self.cycle_queue:
            next_card = self.cycle_queue.popleft()
            self.hand[hand_index] = next_card
            self.cycle_queue.append(card_name)
        
        return True

    def get_next_card(self) -> Optional[str]:
        """Return the next card in cycle, if known."""
        if self.cycle_queue:
            return self.cycle_queue[0]
        return None
    
    def is_alive(self) -> bool:
        """Check if player still has towers standing"""
        return self.king_tower_hp > 0
    
    def get_crown_count(self) -> int:
        """Get number of crowns (destroyed towers)"""
        if self.king_tower_hp <= 0:
            return 3
        crowns = 0
        if self.left_tower_hp <= 0:
            crowns += 1
        if self.right_tower_hp <= 0:
            crowns += 1
        return crowns
