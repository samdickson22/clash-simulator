from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque

from .card_types import CardStatsCompat
from .balance import DEFAULT_BATTLE_TIMELINE_STARTING_ELIXIR

ELIXIR_ROUNDOFF_TOLERANCE = 1e-9


@dataclass
class PlayerState:
    player_id: int
    elixir: float = DEFAULT_BATTLE_TIMELINE_STARTING_ELIXIR
    max_elixir: float = 10.0
    next_card_refill_cooldown_ms: int = 0
    
    # Card system
    hand: List[Optional[str]] = field(default_factory=lambda: ["Knight", "Archer", "Giant", "Minions"])
    deck: List[str] = field(default_factory=lambda: ["Knight", "Archer", "Giant", "Minions", "Musketeer", "BabyDragon", "Balloon", "Wizard"])
    cycle_queue: Deque[str] = field(default_factory=deque)
    
    # Tower HP 
    king_tower_hp: float = 4824.0      # King tower HP
    left_tower_hp: float = 3052.0      # Level 11 Tower Princess HP
    right_tower_hp: float = 3052.0     # Level 11 Tower Princess HP
    
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
                self.elixir + ELIXIR_ROUNDOFF_TOLERANCE >= card_stats.mana_cost and
                self.is_alive())
    
    def play_card(self, card_name: str, card_stats: CardStatsCompat) -> bool:
        """Play a card from hand, updating elixir and cycling"""
        if not self.can_play_card(card_name, card_stats):
            return False
        
        # Spend elixir
        self.elixir = max(0.0, self.elixir - card_stats.mana_cost)
        
        # Native leaves the played slot empty until the player tick refills it.
        # The used card joins the back of the cycle immediately.
        hand_index = self.hand.index(card_name)
        self.hand[hand_index] = None
        # Since the October 2025 Champion-cycle rework, Champions rotate
        # through the ordinary four-card cycle just like every other card.
        self.cycle_queue.append(card_name)
        
        return True

    def tick_card_refill(self, cooldown_ms: int, tick_ms: int = 50) -> None:
        """Advance the native delayed hand-refill state by one player tick."""
        if self.next_card_refill_cooldown_ms > 0:
            self.next_card_refill_cooldown_ms = max(
                0,
                self.next_card_refill_cooldown_ms - tick_ms,
            )

        if self.next_card_refill_cooldown_ms != 0 or not self.cycle_queue:
            return

        for slot, card_name in enumerate(self.hand):
            if card_name is None:
                self.hand[slot] = self.cycle_queue.popleft()
                self.next_card_refill_cooldown_ms = cooldown_ms
                return

    def get_next_card(self) -> Optional[str]:
        """Return the next card in cycle, if known."""
        if self.cycle_queue:
            return self.cycle_queue[0]
        return None
    
    def is_alive(self) -> bool:
        """Check if player still has towers standing"""
        return self.king_tower_hp > 0
    
    def get_towers_lost(self) -> int:
        """Return this player's destroyed Crown Towers as a crown count."""
        if self.king_tower_hp <= 0:
            return 3
        crowns = 0
        if self.left_tower_hp <= 0:
            crowns += 1
        if self.right_tower_hp <= 0:
            crowns += 1
        return crowns

    def get_crown_count(self) -> int:
        """Legacy alias for this player's towers lost.

        Crowns earned require both players and are exposed by
        ``BattleState.get_crown_count(player_id)``.
        """
        return self.get_towers_lost()
