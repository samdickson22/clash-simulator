"""Opt-in stored-state replay, with a reference captured before implementation."""
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path
import runpy

import numpy as np
import pytest
import torch

from clasher.rl.train_recurrent import collect_rollout, compute_gae, ppo_update, _sequence_inputs
from clasher.rl.tbptt import chunk_minibatches, rollout_chunk_state, select_steps

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'reports/strategy_council_20260928/learner-tbptt'


def assert_identical(actual, expected):
    if isinstance(expected, torch.Tensor):
        assert torch.equal(actual, expected)
    elif isinstance(expected, np.ndarray):
        np.testing.assert_array_equal(actual, expected)
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_identical(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_identical(a, b)
    else:
        assert actual == expected


def test_default_matches_unchanged_reference():
    reference = runpy.run_path(str(REPORT/'reference.py'))
    actual = reference['tiny_update']()
    expected = torch.load(REPORT/'results/default-reference.pt', weights_only=False)
    assert_identical(actual, expected)
    # torch.save with a stable archive name must produce identical bytes too.
    import io
    a, b = io.BytesIO(), io.BytesIO()
    torch.save(actual, a); torch.save(expected, b)
    assert a.getvalue() == b.getvalue()


def test_bc_default_matches_unchanged_reference(tmp_path):
    import clasher.rl.imitation as imitation
    reference = runpy.run_path(str(REPORT/'reference.py'))
    actual = reference['tiny_bc'](imitation, tmp_path)
    expected = torch.load(REPORT/'results/bc-default-reference.pt', weights_only=False)
    assert_identical(actual, expected)


@pytest.fixture
def collected(request):
    ns = runpy.run_path(str(ROOT/'tests/test_council_ppo_contract.py'))
    model, first, state, env, builder = ns['collected'].__wrapped__()
    # New collector from a reset, with meaningful synthetic action alternatives.
    from clasher.rl.selfplay_env import SelfPlayBattleEnv
    env = SelfPlayBattleEnv(seed=289, decision_interval_ticks=5, max_ticks=getattr(request, 'param', 100), public_contract_version=4)
    env._structured_obs_builder = builder
    env.reset()
    del model._council_rollout_history
    rollout, state, *_ = collect_rollout(envs=[env], builder=builder, model=model,
        device=torch.device('cpu'), rollout_steps=7, recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, 2304, dtype=np.int64), previous_rewards=np.zeros(2,dtype=np.float32),
        episode_starts=np.ones(2,dtype=bool), quiet_engine=True,
        recurrent_update_mode='stored-state', tbptt_burn_in=3)
    return model, rollout, state, env, builder


def update(model, rollout, **options):
    optimizer = torch.optim.SGD(model.parameters(), lr=0)
    adv = np.arange(rollout.transitions,dtype=np.float32).reshape(rollout.actions.shape)
    return ppo_update(model=model, optimizer=optimizer, rollout=rollout,
        advantages=adv, returns=adv*.01, device=torch.device('cpu'), epochs=1,
        sequence_batch_size=2, clip_ratio=.2, value_coef=.5, entropy_coef=.01,
        hand_aux_coef=.02, elixir_aux_coef=.05, target_kl=0, **options)


@pytest.mark.parametrize('collected', [35], indirect=True)
def test_whole_episode_loss_and_gradients_match(collected):
    original, rollout, *_ = collected
    assert rollout.dones[:, -1].all()
    assert not rollout.dones[:, :-1].any()
    rollout.action_masks[:,:,:4] = True
    rollout.actions[:] = np.arange(rollout.transitions).reshape(rollout.actions.shape) % 4
    with torch.no_grad():
        rollout.old_log_probs[:] = original(_sequence_inputs(rollout,slice(None),torch.device('cpu'))).distribution().log_prob(torch.from_numpy(rollout.actions)).numpy()
    rollout.recurrent_prefixes = (None, None)
    full, stored = deepcopy(original), deepcopy(original)
    np.random.seed(51); a = update(full,rollout)
    np.random.seed(51); b = update(stored,rollout,recurrent_update_mode='stored-state',tbptt_chunk=7,tbptt_burn_in=0)
    for key in a:
        assert a[key] == pytest.approx(b[key],abs=2e-6,rel=2e-6), key
    for p, q in zip(full.parameters(),stored.parameters()):
        if p.grad is None: assert q.grad is None
        else: torch.testing.assert_close(p.grad,q.grad,atol=2e-6,rtol=2e-6)
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in full.memory.parameters())


def test_chunks_cover_tails_without_tiny_reset_minibatches():
    starts = np.array([[1,0,0,1,0,0,0,0],[1,0,0,0,1,0,1,0]],dtype=bool)
    seen = np.zeros_like(starts,dtype=int)
    for batch in chunk_minibatches(starts,3,2):
        assert len({end-begin for _,begin,end in batch}) == 1
        for row,begin,end in batch:
            seen[row,begin:end] += 1
            assert begin % 3 == 0
            assert end == min(begin + 3, starts.shape[1])
    assert (seen == 1).all()


def test_internal_reset_blocks_state_and_gradient_leakage(collected):
    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout,slice(None),torch.device('cpu'))
    inputs.episode_starts[:] = False
    inputs.episode_starts[:, 3] = True
    state = tuple(torch.ones_like(x, requires_grad=True) for x in model.initial_state(2))
    whole = model(inputs, state)
    suffix = model(select_steps(inputs, slice(None), slice(3,None)))
    torch.testing.assert_close(whole.joint_logits[:, 3:], suffix.joint_logits, atol=2e-6, rtol=2e-6)
    for a,b in zip(whole.next_state, suffix.next_state):
        torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-6)
    gradients = torch.autograd.grad(sum(x.sum() for x in whole.next_state), state)
    for gradient in gradients:
        assert torch.count_nonzero(gradient) == 0


@pytest.mark.parametrize('chunk,batch_size', [(32,8),(64,4)])
def test_resets_preserve_256_loss_tokens_per_minibatch(chunk,batch_size):
    starts = np.zeros((8,128),dtype=bool)
    starts[:, 0] = True
    starts[np.arange(8),np.arange(8)*13+7] = True
    batches = list(chunk_minibatches(starts,chunk,batch_size))
    assert len(batches) == 4
    assert all(sum(end-begin for _,begin,end in batch) == 256 for batch in batches)


def test_burn_in_is_bounded_detached_and_refreshes_with_current_weights(collected):
    model, rollout, *_ = collected
    with torch.no_grad():
        for p in model.memory.parameters(): p.add_(.1)
    inputs = _sequence_inputs(rollout,slice(None),torch.device('cpu'))
    actual = rollout_chunk_state(model,rollout,inputs,[(0,5,7)],3,device=torch.device('cpu'))
    state = tuple(torch.from_numpy(x[0:1,2]) for x in (rollout.stored_hidden,rollout.stored_cell))
    with torch.no_grad(): expected = model(select_steps(inputs,slice(0,1),slice(2,5)),state).next_state
    for a,b in zip(actual,expected):
        assert not a.requires_grad
        torch.testing.assert_close(a,b)
    assert not torch.allclose(actual[0],torch.from_numpy(rollout.stored_hidden[0:1,5]))


def test_cross_rollout_burn_in_and_parallel_transport(collected):
    from clasher.rl.parallel_rollout import concatenate_rollouts
    model, first, state, env, builder = collected
    second, *_ = collect_rollout(envs=[env],builder=builder,model=model,
        device=torch.device('cpu'),rollout_steps=3,recurrent_state=state,
        previous_actions=first.actions[:,-1],previous_rewards=np.zeros(2,dtype=np.float32),
        episode_starts=np.zeros(2,dtype=bool),quiet_engine=True,
        recurrent_update_mode='stored-state',tbptt_burn_in=3)
    assert second.recurrent_prefixes is None
    assert [p.sequence_length for p in second.burn_in_prefixes] == [3,3]
    assert len(model._tbptt_history) == 3
    combined = concatenate_rollouts([second,second])
    assert combined.stored_hidden.shape[0] == 4
    assert len(combined.burn_in_prefixes) == 4
    inputs = _sequence_inputs(second,slice(None),torch.device('cpu'))
    for begin in (0,1,2):
        refreshed = rollout_chunk_state(model,second,inputs,[(0,begin,3)],3,device=torch.device('cpu'))
        for a,b in zip(refreshed,(second.stored_hidden[0:1,begin],second.stored_cell[0:1,begin])):
            torch.testing.assert_close(a,torch.from_numpy(b),atol=2e-6,rtol=2e-6)
    update(model,second,recurrent_update_mode='stored-state',tbptt_chunk=2,tbptt_burn_in=3)


def test_stored_state_requires_collection_receipt(collected):
    model, rollout, *_ = collected
    rollout.stored_hidden = None
    with pytest.raises(ValueError,match='captured during collection'):
        update(model,rollout,recurrent_update_mode='stored-state')


def test_bc_whole_episode_fit_matches_full_prefix(tmp_path):
    import clasher.rl.imitation as imitation
    ns = runpy.run_path(str(REPORT/'reference.py'))
    full_dir, stored_dir = tmp_path/'full', tmp_path/'stored'
    full_dir.mkdir(); stored_dir.mkdir()
    full = ns['tiny_bc'](imitation,full_dir,sequence_length=6)
    stored = ns['tiny_bc'](imitation,stored_dir,recurrent_update_mode='stored-state',tbptt_chunk=6,tbptt_burn_in=0)
    for name in ('checkpoint','control'):
        stored[name].pop('recurrent_update')
        for key, value in full[name]['model_state_dict'].items():
            torch.testing.assert_close(value,stored[name]['model_state_dict'][key],atol=2e-6,rtol=2e-6)
        for key, value in full[name]['metrics'].items():
            assert value == pytest.approx(stored[name]['metrics'][key],abs=2e-6,rel=2e-6)


def test_bc_cache_burn_in_matches_manual_refresh(collected):
    from clasher.rl.imitation import _sequence_batch_inputs
    from clasher.rl.tbptt import ImitationStateCache
    model,rollout,*_ = collected
    arrays = {f.name:getattr(rollout,f.name).reshape((14,*getattr(rollout,f.name).shape[2:]))
              for f in fields(rollout) if isinstance(getattr(rollout,f.name),np.ndarray)
              and getattr(rollout,f.name).shape[:2] == (2,7)}
    arrays['episode_ids'] = np.repeat(np.arange(2),7)
    chunks = np.array([[4,5,6],[11,12,13]])
    cache=ImitationStateCache(model,arrays,chunks,episode_offsets={0:0,1:7},burn_in=2,device=torch.device('cpu'))
    assert set(cache.states) == {2,9}
    with torch.no_grad():
        for p in model.memory.parameters(): p.add_(.02)
    actual=cache.initial_state(model,arrays,chunks,device=torch.device('cpu'))
    for row,(begin,end) in enumerate(((2,4),(9,11))):
        inputs=_sequence_batch_inputs(arrays,np.arange(begin,end)[None],torch.device('cpu'),trim_entity_padding=True,reset_memory=False)
        with torch.no_grad(): expected=model(inputs,cache.states[begin]).next_state
        for a,b in zip(actual,expected):
            assert not a.requires_grad
            torch.testing.assert_close(a[row:row+1],b,atol=2e-6,rtol=2e-6)


def test_toml_config_is_strict_and_cli_overrides_it(tmp_path):
    from argparse import Namespace
    from pydantic import ValidationError
    from clasher.rl.tbptt import RecurrentUpdateConfig, apply_cli_config
    path = tmp_path/'recurrent.toml'
    path.write_text('recurrent_update_mode = "stored-state"\ntbptt_chunk = 32\ntbptt_burn_in = 16\n')
    args = apply_cli_config(Namespace(recurrent_config=path, tbptt_chunk=64))
    assert (args.recurrent_update_mode, args.tbptt_chunk, args.tbptt_burn_in) == ('stored-state', 64, 16)
    assert vars(apply_cli_config(Namespace(recurrent_update_mode='full-prefix'))) == {}
    for invalid in ('tbptt_chunk = 0', 'tbptt_burn_in = -1', 'tbptt_chunk = "32"', 'unknown = 1'):
        path.write_text(invalid)
        with pytest.raises(ValidationError):
            RecurrentUpdateConfig.load(path)


def test_padding_crop_preserves_outputs_with_internal_holes(collected):
    from clasher.rl.tbptt import trim_entity_padding
    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout,slice(None),torch.device('cpu'))
    # Preserve interior indices: only trailing masked padding may be removed.
    inputs.entity_mask[:, :, 1] = False
    inputs.entity_levels[:, :, 1] = 0
    inputs.entity_level_confidence[:, :, 1] = 0
    inputs.critic_entity_mask[:, :, 1] = False
    cropped = trim_entity_padding(inputs)
    assert cropped.entity_mask.shape[2] < inputs.entity_mask.shape[2]
    assert not cropped.entity_mask[:, :, 1].any()
    with torch.no_grad():
        full, trimmed = model(inputs), model(cropped)
    for a, b in ((full.joint_logits, trimmed.joint_logits), (full.values, trimmed.values), *zip(full.next_state, trimmed.next_state)):
        torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-6)
