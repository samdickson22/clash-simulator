"""One actual scalar sequence crosses every M0 actor-input boundary without fitting."""
from copy import deepcopy
from dataclasses import fields

import numpy as np
import torch

from clasher.rl.eval import _policy_step, load_policy_checkpoint
from clasher.rl.imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata, _sequence_batch_inputs
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.parallel_rollout import build_policy_observation_builder
from clasher.rl.public_observation import REAL_PLAY_ENTITY_FEATURE_INDICES, REAL_PLAY_GLOBAL_FEATURE_INDICES
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.scripted_demonstrations import ScriptedGameDemonstration
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import collect_rollout, _index_policy_inputs, _sequence_inputs


DECK = ('HogRider', 'Musketeer', 'IceGolem', 'IceSpirit', 'Skeletons', 'Cannon', 'Fireball', 'Log')
DEVICE = torch.device('cpu')


def test_actual_scalar_sequence_survives_imitation_ppo_archive_and_eval(tmp_path, monkeypatch):
    torch.set_num_threads(1)
    torch.manual_seed(928)
    initial = StructuredObservationBuilder(card_vocab=DECK, max_entities=32, card_semantics_version=4)
    config = PolicyConfig(
        num_tokens=initial.spec.num_tokens, max_entities=32,
        public_contract_version=4, public_token_names=initial.token_names,
        public_observation_confidence=True, card_semantics_version=4,
        canonical_lane_globals=True, public_history_slots=4, public_seen_card_slots=8,
        d_model=32, num_heads=4, actor_layers=1, critic_layers=1, memory_size=48,
    )
    builder = build_policy_observation_builder(config, decks_path='decks.json', token_names=initial.token_names, card_vocab=DECK)
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    weights_before = {key: value.clone() for key, value in model.state_dict().items()}
    env = SelfPlayBattleEnv(
        public_contract_version=4, decision_interval_ticks=5, max_ticks=100, seed=928,
        card_levels=({name: 10+i%3 for i, name in enumerate(DECK)}, {}), tower_levels=(10,12),
    )
    env._structured_obs_builder = builder
    env.reset(ordered_decks=(DECK, DECK))
    observations, battles = [], []
    original_observation = env.get_structured_observation
    def capture(player_id, **kwargs):
        result = original_observation(player_id, **kwargs)
        if player_id == 0:
            observations.append(result)
            battles.append(deepcopy(env.battle))
        return result
    monkeypatch.setattr(env, 'get_structured_observation', capture)
    rollout, _, *_ = collect_rollout(
        envs=[env], builder=builder, model=model, device=DEVICE, rollout_steps=3,
        recurrent_state=model.initial_state(2), previous_actions=np.full(2,2304,dtype=np.int64),
        previous_rewards=np.array([99,-99],dtype=np.float32), episode_starts=np.ones(2,dtype=bool), quiet_engine=True,
    )
    monkeypatch.setattr(env, 'get_structured_observation', original_observation)
    assert [battle.tick for battle in battles[:3]] == [0,5,10]
    assert env.battle.tick == 15  # Actual scalar steps, not synthetic advance.
    public = PublicPolicySequence.from_observations(builder, observations[:3])
    # Use the real scripted adapter's transport and imitation input APIs, with
    # explicitly invalid labels. This partial untrained sequence is no corpus.
    controls = {name: getattr(rollout, name)[0].copy() for name in
                ('action_masks','previous_actions','previous_rewards','episode_starts')}
    controls.update(expert_actions=rollout.actions[0].copy(), episode_ids=np.zeros(3,dtype=np.int64),
                    expert_action_supervision_valid=np.zeros(3,dtype=bool))
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION, created_at='2026-09-28T00:00:00Z', seed=928,
        decisions=3, samples=3, decision_interval=5, max_ticks=100, planner_depth=0,
        planner_simulations=0, planner_action_samples=0, max_entities=32, token_names=builder.token_names,
        public_contract_version=4, public_history_slots=4, public_seen_card_slots=8,
        label_source='synthetic-transport-only', provenance='No expert labels, training or complete-game claim.',
    )
    demo = ScriptedGameDemonstration(public, controls, metadata, {})
    supervised = _sequence_batch_inputs(demo.imitation_arrays(), np.asarray([[0,1,2]]), DEVICE)
    packed_supervised = _sequence_batch_inputs(demo.imitation_arrays(), np.asarray([[0,1,2]]), DEVICE, trim_entity_padding=True)
    assert packed_supervised.entity_ids.shape[-1] < supervised.entity_ids.shape[-1]
    ppo = _index_policy_inputs(_sequence_inputs(rollout,slice(None),DEVICE),torch.tensor([0]))
    public_path = tmp_path/'public.npz'
    public.save(public_path)
    restored = PublicPolicySequence.load(public_path,token_names=builder.token_names)
    inference = restored.policy_inputs(action_mask=controls['action_masks'],previous_actions=controls['previous_actions'],
        previous_rewards=controls['previous_rewards'],episode_starts=controls['episode_starts'])
    for field in fields(PolicyInputs):
        if field.name.startswith('critic_') or field.name.startswith('opponent_play_event_'):
            continue
        expected = getattr(ppo,field.name)
        for candidate in (supervised,inference):
            actual = getattr(candidate,field.name)
            if expected is None:
                assert actual is None, field.name
            else:
                torch.testing.assert_close(actual,expected,rtol=0,atol=0,msg=field.name)
    assert set(ppo.hand_levels[0,0].tolist()) == {10,11,12}
    assert set(ppo.entity_levels[0,0][ppo.entity_mask[0,0]].tolist()) == {10,12}
    assert not ppo.previous_rewards.any()
    assert not ppo.entity_features[...,sorted(set(range(32))-REAL_PLAY_ENTITY_FEATURE_INDICES)].any()
    assert not ppo.global_features[...,sorted(set(range(18))-REAL_PLAY_GLOBAL_FEATURE_INDICES)].any()
    with torch.no_grad():
        ppo_output, supervised_output, inference_output = model(ppo),model(supervised),model(inference)
        packed_output = model(packed_supervised)
    torch.testing.assert_close(packed_output.joint_logits, ppo_output.joint_logits, rtol=2e-6, atol=2e-6)
    for actual, expected in zip(packed_output.next_state, ppo_output.next_state):
        torch.testing.assert_close(actual, expected, rtol=2e-6, atol=2e-6)
    for output in (supervised_output,inference_output):
        torch.testing.assert_close(output.joint_logits,ppo_output.joint_logits,rtol=0,atol=0)
        for actual,expected in zip(output.next_state,ppo_output.next_state):
            torch.testing.assert_close(actual,expected,rtol=0,atol=0)
    torch.testing.assert_close(ppo_output.distribution().log_prob(torch.from_numpy(rollout.actions[:1])),
                               torch.from_numpy(rollout.old_log_probs[:1]),rtol=2e-6,atol=2e-6)
    checkpoint=tmp_path/'untrained.pt'
    torch.save(dict(format_version=2,model_config=config.to_dict(),token_names=builder.token_names,model_state_dict=model.state_dict()),checkpoint)
    loaded=load_policy_checkpoint(checkpoint,device=DEVICE,decks_path='decks.json')
    state=loaded.model.initial_state(1)
    for step,battle in enumerate(battles[:3]):
        env.battle=deepcopy(battle)
        action,state,mask,output=_policy_step(loaded,env,0,state=state,
            previous_action=int(rollout.previous_actions[0,step]),previous_reward=999,
            episode_start=bool(rollout.episode_starts[0,step]),deterministic=False,device=DEVICE)
        np.testing.assert_array_equal(mask,rollout.action_masks[0,step])
        assert mask[action]
        torch.testing.assert_close(output.joint_logits,ppo_output.joint_logits[:,step:step+1],rtol=2e-6,atol=2e-6)
    for actual,expected in zip(state,ppo_output.next_state):
        torch.testing.assert_close(actual,expected,rtol=2e-6,atol=2e-6)
    for key,value in model.state_dict().items():
        torch.testing.assert_close(value,weights_before[key],rtol=0,atol=0)
