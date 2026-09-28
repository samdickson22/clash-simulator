from __future__ import annotations

import numpy as np

from clasher.rl.common import NUM_TILES
from clasher.rl.deck_pool import apply_deck_to_player
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.reconstruct_tv_royale_simulator_corpus import (
    _forced_slot_action,
    _sync_human_public_state,
)


def test_public_state_sync_and_forced_slot_are_live_legal():
    deck = [
        "Knight",
        "Archers",
        "Giant",
        "Minions",
        "Musketeer",
        "BabyDragon",
        "Balloon",
        "Arrows",
    ]
    env = SelfPlayBattleEnv(seed=1048201, engine_fast_path="on")
    env.reset()
    assert env.battle is not None
    apply_deck_to_player(env.battle.players[0], deck, rng=env.rng)
    builder = StructuredObservationBuilder(decks_path="decks.json")
    hand_ids = np.asarray(
        [
            builder.token_id("Giant"),
            builder.token_id("Knight"),
            builder.token_id("Archers"),
            builder.token_id("Minions"),
            builder.token_id("Musketeer"),
        ],
        dtype=np.int64,
    )

    _sync_human_public_state(
        env,
        hand_ids=hand_ids,
        token_names=builder.token_names,
        deck=deck,
        elixir=7.5,
    )

    player = env.battle.players[0]
    assert player.hand == ["Giant", "Knight", "Archers", "Minions"]
    assert player.get_next_card() == "Musketeer"
    assert player.elixir == 7.5
    mask = env.get_action_mask(0)
    action = _forced_slot_action(
        slot=0,
        mask=mask,
        location_logits=np.tile(np.arange(NUM_TILES, dtype=np.float32), (4, 1)),
    )
    assert action is not None
    assert 0 <= action < NUM_TILES
    assert mask[action]
