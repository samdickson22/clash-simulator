"""Synthetic fixtures only: never a substitute for the T3-qualified shakedown."""
import numpy as np
import torch
from .features import build_row, collate_features
from .network import ModelConfig, SetPolicy


def packet(entities=10, seed=1):
    rng = np.random.default_rng(seed)
    mask = np.zeros(2306, bool)
    mask[:2304] = rng.random(2304) > .3
    mask[2304:] = True
    p = {"hand_ids": np.arange(1, 6), "hand_levels": np.full(5, 11),
         "opponent_seen_card_ids": np.arange(10, 18), "global_features": rng.random(18).astype(np.float32),
         "champion_button": True, "entity_ids": rng.integers(1, 360, entities),
         "entity_levels": np.full(entities, 11), "entity_features": rng.random((entities, 17)).astype(np.float32),
         "entity_mask": np.ones(entities, bool), "action_mask": mask}
    history = np.array([[i+1, .01*i, .25, .5] for i in range(8)], np.float32)
    d = {"own_deck": np.arange(1, 9), "own_queue": np.arange(5, 9),
         "opp_hand_known": np.array([9, 10, 0, 0]), "opp_next_card": 11,
         "opp_queue": np.arange(11, 15), "opp_history": history,
         "own_history": history, "opp_abilities": np.array([[15, .1]], np.float32),
         "opp_elixir": 5., "opp_refill_remaining": 0., "own_refill_remaining": 0.,
         "opp_cards_revealed": 6, "elixir_exact": True}
    return p, d


def model(config=None):
    c = config or ModelConfig()
    return SetPolicy(c, torch.zeros(c.vocab, c.descriptors), torch.zeros(576, 12), torch.ones(360)*3)


def batch(n=4, entities=4):
    rows, actions = [], []
    for i in range(n):
        p, d = packet(entities, i)
        p["action_mask"][0] = True
        actions.append(0 if i%3 == 0 else 2304 if i%3 == 1 else 2305)
        rows.append(build_row(p, d, np.full(360, 3.)))
    b = collate_features(rows)
    y = {"action": torch.tensor(actions), "supervised": torch.ones(n, dtype=torch.bool),
         "weight": torch.ones(n), "intent_card": torch.zeros(n, dtype=torch.long),
         "intent_bin": torch.ones(n, dtype=torch.long), "intent_observed": torch.ones(n, dtype=torch.bool),
         "intent_valid": torch.ones(n, dtype=torch.bool)}
    return b, y
