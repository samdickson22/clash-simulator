"""Match lifecycle survives public projection and controls command eligibility."""
import json
from dataclasses import replace

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.causal_vision import CausalVisionTracker
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import (
    PublicObservationDegradationProfile,
    degrade_simulator_public_observation,
    exact_public_observation,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


@pytest.mark.parametrize('owner', [0, 1])
@pytest.mark.parametrize('deadline', [3600, 6000])
def test_public_mask_keeps_last_submission_then_closes(owner, deadline):
    battle = BattleState()
    if deadline == 3600:
        battle.entities[4].take_damage(battle.entities[4].hitpoints)
        battle._cleanup_dead_entities()
    battle.tick = deadline
    battle.time = deadline * battle.dt
    battle.players[owner].hand = ['Zap']
    battle.players[owner].elixir = 10
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    masks = PublicActionMaskBuilder(builder)
    battle._check_win_conditions()
    active = builder.build_actor(battle, owner)
    assert active.terminal is False
    mask = masks.build(PublicActionMaskInput.from_confidence_observation(exact_public_observation(active)))
    assert mask[:masks.no_op_action].any()
    battle.step()
    ended = builder.build_actor(battle, owner)
    assert ended.terminal is True
    assert builder.build(battle, owner).terminal is True
    mask = masks.build(PublicActionMaskInput.from_confidence_observation(exact_public_observation(ended)))
    assert np.flatnonzero(mask).tolist() == [masks.no_op_action]


@pytest.mark.parametrize('terminal', [False, True, None])
def test_lifecycle_projection_tracker_archive_and_policy_mask(tmp_path, terminal):
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    battle = BattleState()
    battle.players[0].hand = ['Zap']
    battle.players[0].elixir = 10
    view = replace(builder.build_actor(battle, 0), terminal=terminal)
    projected = degrade_simulator_public_observation(
        view, profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(0)
    )
    tracked = CausalVisionTracker().update(projected, frame=1)
    assert tracked.observation.terminal is terminal
    masks = PublicActionMaskBuilder(builder)
    mask = masks.build(PublicActionMaskInput.from_confidence_observation(tracked))
    sequence = PublicPolicySequence.from_observations(builder, [tracked])
    path = tmp_path / 'observations.npz'
    sequence.save(path)
    restored = PublicPolicySequence.load(path, token_names=builder.token_names)
    assert restored.arrays['terminal_status'].tolist() == [-1 if terminal is None else int(terminal)]
    restored.validate_action_mask(mask[None])
    controls = {'action_mask': mask[None], 'previous_actions': np.zeros(1, dtype=np.int64),
                    'previous_rewards': np.zeros(1, dtype=np.float32), 'episode_starts': np.ones(1, dtype=bool)}
    restored.policy_inputs(**controls)
    if terminal is not False:
        assert np.flatnonzero(mask).tolist() == [masks.no_op_action]
        invalid = mask.copy()
        invalid[0] = True
        with pytest.raises(ValueError, match='wait-only'):
            restored.policy_inputs(**(controls | {'action_mask': invalid[None]}))
    else:
        assert mask[:masks.no_op_action].any()


def test_legacy_archive_cannot_silently_gain_active_status(tmp_path):
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    sequence = PublicPolicySequence.from_observations(builder, [builder.build_actor(BattleState(), 0)])
    old_arrays = {k: v for k, v in sequence.arrays.items() if k != 'terminal_status'}
    path = tmp_path / 'legacy.npz'
    np.savez(path, metadata=np.asarray(json.dumps({'schema': 'clasher.public-policy.v2', 'token_names': builder.token_names})), **old_arrays)
    with pytest.raises(ValueError, match='schema'):
        PublicPolicySequence.load(path, token_names=builder.token_names)


def test_tracker_does_not_reuse_stale_active_status():
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    view = builder.build_actor(BattleState(), 0)
    tracker = CausalVisionTracker()
    def project(terminal):
        return degrade_simulator_public_observation(replace(view, terminal=terminal),
            profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(0))
    assert tracker.update(project(False), frame=1).observation.terminal is False
    assert tracker.update(project(None), frame=2).observation.terminal is None


@pytest.mark.parametrize('terminal', [0, 1, 'active', np.bool_(False)])
def test_terminal_status_rejects_ambiguous_types(terminal):
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    view = replace(builder.build_actor(BattleState(), 0), terminal=terminal)
    with pytest.raises(ValueError, match='terminal status'):
        exact_public_observation(view)
    with pytest.raises(ValueError, match='terminal status'):
        PublicPolicySequence.from_observations(builder, [view])


@pytest.mark.parametrize('owner', [0, 1])
def test_sudden_death_closes_public_mask_before_clock_deadline(owner):
    builder = StructuredObservationBuilder(card_vocab=['Zap'])
    battle = BattleState()
    battle.tick = 4000
    battle.time = battle.tick * battle.dt
    battle.players[owner].hand = ['Zap']
    battle.players[owner].elixir = 10
    tower = battle.entities[4 if owner == 0 else 1]
    tower.take_damage(tower.hitpoints)
    battle._cleanup_dead_entities()
    battle._check_win_conditions()
    assert battle.game_over
    mask_builder = PublicActionMaskBuilder(builder)
    view = exact_public_observation(builder.build_actor(battle, owner))
    mask = mask_builder.build(PublicActionMaskInput.from_confidence_observation(view))
    assert np.flatnonzero(mask).tolist() == [mask_builder.no_op_action]
