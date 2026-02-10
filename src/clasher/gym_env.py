"""
Gymnasium environment for Clash Royale 1v1 battles.

Observation space: flat vector of game state
Action space: Discrete (card_index * grid_positions) + no-op

The agent controls Player 0. Player 1 uses a simple rule-based opponent.
"""

import json
import math
import random
from typing import Optional, Tuple, Dict, Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .battle import BattleState
from .arena import Position
from .name_map import resolve_name


# Grid resolution for placement
GRID_X = 18
GRID_Y = 32
NUM_CARDS_IN_HAND = 4
# Actions: 4 cards × 18×32 grid + 1 no-op
NUM_ACTIONS = NUM_CARDS_IN_HAND * GRID_X * GRID_Y + 1
NO_OP = NUM_ACTIONS - 1

# Observation dimensions
MAX_ENTITIES = 50
ENTITY_FEATURES = 8  # x, y, hp_frac, player_id, is_air, damage, range, speed
PLAYER_FEATURES = 8  # elixir, king_hp, left_hp, right_hp, hand (4 card indices)
GLOBAL_FEATURES = 4  # time_frac, double_elixir, triple_elixir, overtime
OBS_SIZE = GLOBAL_FEATURES + 2 * PLAYER_FEATURES + MAX_ENTITIES * ENTITY_FEATURES


class ClashRoyaleEnv(gym.Env):
    """Clash Royale 1v1 Gymnasium environment."""
    
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        deck_file: str = "decks.json",
        gamedata_file: str = "gamedata.json",
        max_ticks: int = 11000,
        opponent: str = "random",  # "random" or "cycle"
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        self.deck_file = deck_file
        self.gamedata_file = gamedata_file
        self.max_ticks = max_ticks
        self.opponent_type = opponent
        self.render_mode = render_mode

        # Load decks
        with open(deck_file) as f:
            self.all_decks = json.load(f)["decks"]

        # Build card name → index mapping from all decks
        all_cards = sorted(set(c for d in self.all_decks for c in d["cards"]))
        self.card_to_idx: Dict[str, int] = {c: i for i, c in enumerate(all_cards)}
        self.idx_to_card: Dict[int, str] = {i: c for c, i in self.card_to_idx.items()}
        self.num_unique_cards = len(all_cards)

        # Spaces
        self.action_space = spaces.Discrete(NUM_ACTIONS)
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(OBS_SIZE,), dtype=np.float32
        )

        self.battle: Optional[BattleState] = None
        self._tick = 0

    # ------------------------------------------------------------------
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)

        # Pick random decks (or use options to specify)
        rng = self.np_random
        if options and "deck0" in options:
            deck0 = options["deck0"]
        else:
            deck0 = self.all_decks[rng.integers(len(self.all_decks))]["cards"]
        if options and "deck1" in options:
            deck1 = options["deck1"]
        else:
            deck1 = self.all_decks[rng.integers(len(self.all_decks))]["cards"]

        self.battle = BattleState()
        self.battle.card_loader.data_file = self.gamedata_file

        for pid, deck in enumerate([deck0, deck1]):
            p = self.battle.players[pid]
            p.deck = list(deck)
            p.hand = list(deck[:4])
            p.cycle_queue.clear()
            for c in deck[4:]:
                p.cycle_queue.append(c)

        self._tick = 0
        self._deck0 = deck0
        self._deck1 = deck1

        obs = self._get_obs()
        info = {"deck0": deck0, "deck1": deck1}
        return obs, info

    # ------------------------------------------------------------------
    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        assert self.battle is not None, "Call reset() first"

        reward = 0.0

        # Decode and execute agent action (Player 0)
        if action != NO_OP:
            card_idx = action // (GRID_X * GRID_Y)
            remainder = action % (GRID_X * GRID_Y)
            gx = remainder // GRID_Y
            gy = remainder % GRID_Y
            x = gx + 0.5
            y = gy + 0.5

            p = self.battle.players[0]
            if card_idx < len(p.hand):
                card_name = p.hand[card_idx]
                self.battle.deploy_card(0, card_name, Position(x, y))

        # Opponent action (simple rule-based)
        self._opponent_step()

        # Advance simulation several ticks (faster training)
        for _ in range(10):
            self.battle.step()
            self._tick += 1
            if self.battle.game_over:
                break

        # Compute reward
        # Crown-based reward
        p0_crowns = self.battle.players[1].get_crown_count()
        p1_crowns = self.battle.players[0].get_crown_count()
        reward = (p0_crowns - p1_crowns) * 0.1

        # Tower damage differential
        p0_dmg = (
            max(0, 3631 - self.battle.players[1].left_tower_hp)
            + max(0, 3631 - self.battle.players[1].right_tower_hp)
            + max(0, 4824 - self.battle.players[1].king_tower_hp)
        )
        p1_dmg = (
            max(0, 3631 - self.battle.players[0].left_tower_hp)
            + max(0, 3631 - self.battle.players[0].right_tower_hp)
            + max(0, 4824 - self.battle.players[0].king_tower_hp)
        )
        reward += (p0_dmg - p1_dmg) * 0.0001

        terminated = self.battle.game_over
        truncated = self._tick >= self.max_ticks

        if terminated:
            if self.battle.winner == 0:
                reward += 1.0
            elif self.battle.winner == 1:
                reward -= 1.0

        obs = self._get_obs()
        info = {
            "time": self.battle.time,
            "p0_crowns": p0_crowns,
            "p1_crowns": p1_crowns,
            "winner": self.battle.winner,
        }

        return obs, reward, terminated, truncated, info

    # ------------------------------------------------------------------
    def _opponent_step(self) -> None:
        """Simple opponent: play cheapest affordable card at random valid position."""
        p = self.battle.players[1]
        cards_by_cost = sorted(
            p.hand,
            key=lambda c: getattr(
                self.battle.card_loader.get_card(c)
                or self.battle.card_loader.get_card_compat(c),
                "mana_cost",
                99,
            ),
        )
        for card in cards_by_cost:
            stats = self.battle.card_loader.get_card(card) or self.battle.card_loader.get_card_compat(card)
            if stats and p.elixir >= getattr(stats, "mana_cost", 99):
                x = random.uniform(3, 15)
                y = random.uniform(17, 30)
                if self.battle.deploy_card(1, card, Position(x, y)):
                    break

    # ------------------------------------------------------------------
    def _get_obs(self) -> np.ndarray:
        """Build flat observation vector."""
        obs = np.zeros(OBS_SIZE, dtype=np.float32)
        b = self.battle
        idx = 0

        # Global features
        obs[idx] = b.time / 360.0  # normalized time
        obs[idx + 1] = float(b.double_elixir)
        obs[idx + 2] = float(b.triple_elixir)
        obs[idx + 3] = float(b.overtime)
        idx += GLOBAL_FEATURES

        # Player features (both players)
        for pid in [0, 1]:
            p = b.players[pid]
            obs[idx] = p.elixir / 10.0
            obs[idx + 1] = p.king_tower_hp / 4824.0
            obs[idx + 2] = p.left_tower_hp / 3631.0
            obs[idx + 3] = p.right_tower_hp / 3631.0
            # Hand card indices (normalized)
            for hi, card in enumerate(p.hand[:4]):
                card_idx = self.card_to_idx.get(card, 0)
                obs[idx + 4 + hi] = card_idx / max(1, self.num_unique_cards)
            idx += PLAYER_FEATURES

        # Entity features (up to MAX_ENTITIES)
        entities = list(b.entities.values())[:MAX_ENTITIES]
        for ei, ent in enumerate(entities):
            base = idx + ei * ENTITY_FEATURES
            obs[base] = ent.position.x / 18.0
            obs[base + 1] = ent.position.y / 32.0
            obs[base + 2] = ent.hitpoints / max(1, ent.max_hitpoints)
            obs[base + 3] = 1.0 if ent.player_id == 0 else -1.0
            obs[base + 4] = float(getattr(ent, "is_air_unit", False))
            obs[base + 5] = min(1.0, ent.damage / 500.0)
            obs[base + 6] = min(1.0, ent.range / 12.0)
            obs[base + 7] = min(1.0, getattr(ent, "speed", 0) / 120.0)

        return obs

    # ------------------------------------------------------------------
    def render(self) -> None:
        if self.render_mode == "human" and self.battle:
            s = self.battle.get_state_summary()
            print(
                f"t={s['time']:.1f}s  ents={s['entities']}  "
                f"P0: {s['players'][0]['crowns']}cr  "
                f"P1: {s['players'][1]['crowns']}cr  "
                f"go={s['game_over']} w={s['winner']}"
            )
