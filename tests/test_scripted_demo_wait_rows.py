"""Merge-plan item 4b: wait rows must carry the pre-decision hand.

ClashAI found 15% of its wait rows on a side's own play tick carrying the hand
from after the play. This contract test drives the real scripted collector
through the real engine for a bounded prefix (forced termination; not teacher
evidence, nothing is fitted) and checks every row against the hand recorded
immediately before the engine applied that row's decision.
"""

import json

import numpy as np
import pytest
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.rl.deck_curriculum import pilot_curriculum
from clasher.rl.imitation import _sequence_batch_inputs
from clasher.rl.scripted_demonstrations import collect_public_script_game
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder

NO_OP = 2304
PREFIX_DECISIONS = 240


def hand_label_violations(arrays, pre_step_hands, played_cards):
    """Rows whose stored hand is not the hand the decision was made from.

    ``pre_step_hands[i]`` holds the learner's four hand token ids captured
    just before step ``i``; ``played_cards[i]`` is the token that left the hand
    during step ``i`` (0 when nothing was deployed).
    """
    violations = []
    hands = arrays["hand_ids"][:, :4]
    actions = arrays["expert_actions"]
    valid = arrays["expert_action_supervision_valid"]
    for row, (expected, played) in enumerate(zip(pre_step_hands, played_cards)):
        if not np.array_equal(hands[row], expected):
            violations.append((row, "hand is not the pre-decision hand"))
        if valid[row] and actions[row] < NO_OP:
            if hands[row][actions[row] // 576] != played:
                violations.append((row, "labelled slot is not the executed card"))
        elif valid[row] and played:
            # A supervised wait whose own step deployed a card means the wait
            # label and the play were attached to the wrong rows.
            violations.append((row, "wait row but a card left the hand this step"))
    return violations


@pytest.fixture(scope="module", params=[0, 1], ids=["seat0", "seat1"])
def demonstration(request, tmp_path_factory):
    torch.set_num_threads(1)
    seat = request.param
    directory = tmp_path_factory.mktemp(f"demo-{seat}")
    decks = directory / "pilot.json"
    decks.write_text(json.dumps({"decks": [deck for decks in pilot_curriculum().values() for deck in decks]}))
    builder = StructuredObservationBuilder(
        decks_path=decks, max_entities=128, card_semantics_version=4,
        canonical_perspective=True, canonical_lane_globals=True,
        public_entity_levels=True, public_hand_levels=True,
        public_history_slots=4, public_seen_card_slots=8,
    )
    env = SelfPlayBattleEnv(
        decks_path=decks, decision_interval_ticks=5, seed=31 + seat,
        max_ticks=STANDARD_MATCH_TICKS, canonical_perspective=True,
        canonical_lane_globals=True, public_contract_version=4,
        tower_levels=(11, 11), card_levels=({}, {}),
    )
    env._structured_obs_builder = builder
    env.reset(seed=31 + seat)
    real_step = env.step
    pre_step_hands, played_cards = [], []

    def recording_step(actions, **kwargs):
        player = env.battle.players[seat]
        before = list(player.hand[:4]) + [None] * (4 - len(player.hand[:4]))
        # Same padding as the observation builder: an empty refill slot is 0.
        pre_step_hands.append([0 if name is None else builder.token_id(name) for name in before])
        result = real_step(actions, **kwargs)
        left = [name for name in before if name is not None and name not in player.hand[:4]]
        assert len(left) <= 1
        played_cards.append(builder.token_id(left[0]) if left else 0)
        rewards, done, info = result
        if len(pre_step_hands) >= PREFIX_DECISIONS and not done:
            env.battle.game_over = True  # bounded contract prefix, not a real result
            done = True
        return rewards, done, info

    env.step = recording_step
    game = collect_public_script_game(
        env, builder, seed=31 + seat, episode_id=seat, role="training",
        family_id="contract", learner_player_id=seat, styles=("pressure", "pressure"),
    )
    return game, np.asarray(pre_step_hands), np.asarray(played_cards)


def test_rows_carry_pre_decision_hand_and_labels_hit_executed_card(demonstration):
    game, pre_step_hands, played_cards = demonstration
    arrays = game.imitation_arrays()
    decisions = len(pre_step_hands)
    assert game.metadata.decisions == decisions
    assert len(arrays["expert_actions"]) == decisions + 1  # plus terminal context
    labels = arrays["expert_actions"][:decisions]
    valid = arrays["expert_action_supervision_valid"][:decisions]
    plays = int(np.count_nonzero(valid & (labels < NO_OP)))
    waits = int(np.count_nonzero(valid & (labels == NO_OP)))
    assert plays >= 5 and waits > plays  # the prefix exercises both label kinds
    # Every accepted placement deployed exactly the labelled card.
    assert int(np.count_nonzero(played_cards)) == plays
    assert hand_label_violations(arrays, pre_step_hands, played_cards) == []
    # The row after a play already shows the refreshed hand, so the hand
    # change is attributed to the play row's successor, never to the play row.
    for row in np.flatnonzero(played_cards):
        assert played_cards[row] in arrays["hand_ids"][row, :4]
        assert played_cards[row] not in arrays["hand_ids"][row + 1, :4]
    # The supervised warm-start batch keeps rows, hands and labels aligned.
    indices = np.arange(decisions + 1)[None]
    batch = _sequence_batch_inputs(arrays, indices, torch.device("cpu"))
    assert np.array_equal(batch.hand_ids[0].numpy(), arrays["hand_ids"])
    assert np.array_equal(arrays["previous_actions"][1:], arrays["expert_actions"][:-1])


def test_checker_detects_the_clashai_post_play_hand_shift(demonstration):
    game, pre_step_hands, played_cards = demonstration
    arrays = dict(game.imitation_arrays())
    shifted = arrays["hand_ids"].copy()
    shifted[:-1] = arrays["hand_ids"][1:]  # every row carries the next row's hand
    arrays["hand_ids"] = shifted
    violations = hand_label_violations(arrays, pre_step_hands, played_cards)
    assert any(reason == "labelled slot is not the executed card" for _, reason in violations)
    assert any(reason == "hand is not the pre-decision hand" for _, reason in violations)
