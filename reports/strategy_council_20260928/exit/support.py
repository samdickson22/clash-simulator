"""Oracle-planner qualification harness (evaluation games only; no fitting, no labels).

Mirrors ``clasher.rl.eval.evaluate`` game setup (paired seats, matchup seeds,
asymmetric deck pools, public-script opponent on the council public packet,
decision interval 5, max ticks 6001) but lets a non-network "player" occupy the
candidate seat. Adapted setup only; runs in the canonical workspace.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl import eval as cl_eval
from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import reward_potential_p0, reward_win_prob_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv, resolve_match_horizon
from clasher.rl.train_recurrent import maybe_silence_stdio

OQ_DIR = Path(__file__).resolve().parent
COUNCIL = OQ_DIR.parent
TRAIN_DECKS = COUNCIL / "m0/data/roles_v2/training.json"
DEV_DECKS = COUNCIL / "m0/data/roles_v2/development.json"
HOG_DECKS = COUNCIL / "pilot/hog26-deployment.json"
CHECKPOINT = (
    COUNCIL
    / "pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt"
)
ROLE_DECKS = {"holdout": DEV_DECKS, "hog26": HOG_DECKS}
# Seeds of the pilot one-million diagnostic cells (council_pilot.evaluation_commands,
# evaluation_seed 9413, slots 12-23). Using them gives common matchups with the pilot.
PILOT_CELL_SEEDS = {
    ("holdout", "balanced"): 12009449,
    ("holdout", "pressure"): 13009452,
    ("holdout", "defense"): 14009455,
    ("hog26", "balanced"): 18009467,
    ("hog26", "pressure"): 19009470,
    ("hog26", "defense"): 20009473,
}
DECISION_INTERVAL = 5
MAX_TICKS = 6001


class Context:
    """Per-process shared objects (checkpoint builder, pools, envs)."""

    def __init__(self, checkpoint: Path = CHECKPOINT) -> None:
        torch.set_num_threads(1)
        self.device = torch.device("cpu")
        self.loaded = cl_eval.load_policy_checkpoint(
            Path(checkpoint), device=self.device, decks_path=TRAIN_DECKS
        )
        self.config = self.loaded.model.config
        self.max_ticks = resolve_match_horizon(
            MAX_TICKS, self.config.public_contract_version
        )
        self._envs: dict[str, dict[int, SelfPlayBattleEnv]] = {}
        self._pools: dict[str, tuple] = {}
        self._bots: dict[str, Any] = {}

    def envs(self, role: str, seed: int) -> dict[int, SelfPlayBattleEnv]:
        if role not in self._envs:
            self._envs[role] = cl_eval._make_evaluation_envs(
                candidate=self.loaded,
                decks_path=TRAIN_DECKS,
                sampling_decks_path=None,
                candidate_sampling_decks_path=ROLE_DECKS[role],
                opponent_sampling_decks_path=TRAIN_DECKS,
                decision_interval=DECISION_INTERVAL,
                max_ticks=self.max_ticks,
                seed=seed,
                mirror_match=False,
                reward_profile="objective-v1",
            )
            for env in self._envs[role].values():
                env._structured_obs_builder = self.loaded.builder
                env._public_action_mask_builder = None
                env.public_contract_version = self.config.public_contract_version
        return self._envs[role]

    def pools(self, role: str):
        if role not in self._pools:
            self._pools[role] = (
                load_deck_pool(ROLE_DECKS[role]),
                load_deck_pool(TRAIN_DECKS),
            )
        return self._pools[role]

    def strategy_bot(self, name: str):
        key = "sb:" + name
        if key not in self._bots:
            from clasher.rl.strategy_bots import StrategyBot

            self._bots[key] = StrategyBot(name)
        return self._bots[key]

    def bot(self, style: str):
        if style not in self._bots:
            from clasher.rl.public_scripted_opponent import PublicScriptedOpponent

            self._bots[style] = PublicScriptedOpponent(self.loaded.builder, style=style)
        return self._bots[style]

