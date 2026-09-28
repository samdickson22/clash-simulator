from __future__ import annotations

import contextlib
import io
from dataclasses import replace

import numpy as np

from clasher.rl.selfplay_env import SelfPlayBattleEnv


def test_public_mask_uses_accepted_hud_identity_at_measured_confidence() -> None:
    env = SelfPlayBattleEnv(seed=1801, max_ticks=64, engine_fast_path="on")
    env.reset()
    observation = env.get_structured_observation(
        0, actor_observation_domain="causal-vision-v1"
    )
    assert observation.hand_id_confidence is not None
    assert observation.global_feature_confidence is not None

    missing_elixir = replace(
        observation,
        global_feature_confidence=np.zeros_like(
            observation.global_feature_confidence
        ),
    )
    mask = env.get_action_mask(
        0,
        actor_observation_domain="causal-vision-v1",
        structured_observation=missing_elixir,
    )
    assert np.flatnonzero(mask).tolist() == [env.action_space.no_op_action]

    carried_hand_confidence = observation.hand_id_confidence.copy()
    carried_hand_confidence[:4] = 0.8
    carried_hand = replace(
        observation,
        hand_id_confidence=carried_hand_confidence,
    )
    mask = env.get_action_mask(
        0,
        actor_observation_domain="causal-vision-v1",
        structured_observation=carried_hand,
    )
    assert mask.sum() > 1

    missing_hand_confidence = observation.hand_id_confidence.copy()
    missing_hand_confidence[:4] = 0.0
    missing_hand = replace(
        observation,
        hand_id_confidence=missing_hand_confidence,
    )
    mask = env.get_action_mask(
        0,
        actor_observation_domain="causal-vision-v1",
        structured_observation=missing_hand,
    )
    assert np.flatnonzero(mask).tolist() == [env.action_space.no_op_action]


def test_public_mask_keeps_unobserved_champion_ability_unavailable() -> None:
    env = SelfPlayBattleEnv(seed=1802, max_ticks=64, engine_fast_path="on")
    env.reset()
    observation = env.get_structured_observation(
        0, actor_observation_domain="causal-vision-v1"
    )
    mask = env.get_action_mask(
        0,
        actor_observation_domain="causal-vision-v1",
        structured_observation=observation,
    )
    assert mask[env.action_space.no_op_action]
    assert not mask[env.action_space.ability_action]


def test_public_mask_is_conservative_across_seeded_battles() -> None:
    comparisons = 0
    public_legal = 0
    exact_legal = 0
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        for seed in range(1810, 1818):
            env = SelfPlayBattleEnv(
                seed=seed,
                max_ticks=256,
                decision_interval_ticks=8,
                engine_fast_path="on",
            )
            env.reset()
            rng = np.random.default_rng(seed + 100_000)
            for _ in range(12):
                actions: dict[int, int] = {}
                exact_masks: dict[int, np.ndarray] = {}
                for player_id in (0, 1):
                    observation = env.get_structured_observation(
                        player_id,
                        actor_observation_domain="causal-vision-v1",
                    )
                    public_mask = env.get_action_mask(
                        player_id,
                        actor_observation_domain="causal-vision-v1",
                        structured_observation=observation,
                    )
                    exact_mask = env.get_action_mask(player_id)
                    assert not np.any(public_mask & ~exact_mask)
                    public_legal += int(public_mask.sum())
                    exact_legal += int(exact_mask.sum())
                    comparisons += 1
                    actions[player_id] = int(
                        rng.choice(np.flatnonzero(exact_mask))
                    )
                    exact_masks[player_id] = exact_mask
                _, done, _ = env.step(actions, pre_action_masks=exact_masks)
                if done:
                    break

    assert comparisons == 8 * 12 * 2
    assert public_legal / exact_legal > 0.80


def test_elixir_affordability_tolerates_subnanosecond_float_drift() -> None:
    env = SelfPlayBattleEnv(seed=1803, max_ticks=64)
    env.reset()
    assert env.battle is not None
    player = env.battle.players[0]
    card_name = player.hand[0]
    assert card_name is not None
    card = env.battle.card_loader.get_card(card_name)
    assert card is not None
    cost = float(card.mana_cost)

    player.elixir = cost - 5e-10
    assert player.can_play_card(card_name, card)
    player.elixir = cost - 2e-9
    assert not player.can_play_card(card_name, card)
