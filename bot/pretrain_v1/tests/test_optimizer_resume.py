"""CPU fixtures for the completed-update AdamW resume contract, never RL jobs."""
import copy

import numpy as np
import pytest
import torch

from bot.pretrain_v1.rl_learner import ContractError
from bot.pretrain_v1.tests.test_rl_learner import (
    admitted, boundary_chunk, chunk, cpu_threads, learner, state,
)


def sample(l, pattern):
    if pattern == 'boundary':
        return boundary_chunk(l)
    return chunk(l, forced=pattern == 'forced', eligible_rows={0} if pattern == 'sparse' else None,
                 accept_plays=False)


def assert_optimizer_equal(a, b):
    a, b = a.optimizer.state_dict(), b.optimizer.state_dict()
    assert a['param_groups'] == b['param_groups']
    assert a['state'].keys() == b['state'].keys()
    for pid, values in a['state'].items():
        for key, value in values.items():
            assert torch.equal(value, b['state'][pid][key])


@pytest.mark.parametrize('precision', ['float32', 'float64'])
@pytest.mark.parametrize('completed', [0, 1, 3, 4])
@pytest.mark.parametrize('pattern', ['eligible', 'sparse', 'forced', 'boundary'])
def test_actual_stage_gradients_counters_and_bitwise_continuation(admitted, tmp_path, precision, completed, pattern):
    a = learner(admitted, precision=precision)
    observed = []
    original_step = a.optimizer.step

    def step(*args, **kwargs):
        observed.append({name for name, p in a.model.named_parameters() if p.grad is not None})
        return original_step(*args, **kwargs)

    a.optimizer.step = step
    for _ in range(completed):
        a.update([sample(a, pattern)])
    named = dict(a.model.named_parameters())
    value = {name for name in named if name.startswith('value.')}
    heads = {name for name in named if name.startswith(('noop.', 'ptr.', 'tile.'))}
    trunk = named.keys()-value-heads
    assert all(names == value for names in observed[:12])
    if completed == 4:
        assert all(trunk | value <= names for names in observed[12:])
        # One eligible row is in exactly one optimizer minibatch per epoch.
        head_steps = {'eligible': 4, 'boundary': 0, 'sparse': 2, 'forced': 0}[pattern]
        assert sum(heads <= names for names in observed[12:]) == head_steps
        # Absent event tokens still have a graph and dense zero gradients.
        src = named['src.weight']
        assert src.grad is not None and not bool(src.grad.any())
    for name, p in named.items():
        count = sum(name in names for names in observed)
        if count:
            assert float(a.optimizer.state[p]['step']) == count
        else:
            assert p not in a.optimizer.state
    path = tmp_path/'resume.pt'
    a.save_checkpoint(path)
    before = torch.load(path, weights_only=False)
    assert len(before['optimizer_resume']['ppo_actor_masks']) == max(0, completed-3)
    b = learner(admitted, precision=precision)
    b.load_checkpoint(path)
    assert_optimizer_equal(a, b)
    expected = a.update([sample(a, pattern)])
    actual = b.update([sample(b, pattern)])
    assert actual == expected
    assert all(torch.equal(t, b.model.state_dict()[name]) for name, t in state(a.model).items())
    assert_optimizer_equal(a, b)
    assert a.shuffle_rng.bit_generator.state == b.shuffle_rng.bit_generator.state
    assert a._ppo_actor_masks == b._ppo_actor_masks


@pytest.mark.parametrize('precision', ['float32', 'float64'])
@pytest.mark.parametrize('completed', [0, 1, 3, 4])
def test_corruption_fails_closed_at_each_stage(admitted, tmp_path, precision, completed):
    l = learner(admitted, precision=precision)
    for _ in range(completed):
        l.update([chunk(l)])
    path = tmp_path/'resume.pt'
    l.save_checkpoint(path)
    clean = torch.load(path, weights_only=False)

    def reject(ck, match):
        torch.save(ck, path)
        fresh = learner(admitted, precision=precision)
        with pytest.raises(ContractError, match=match):
            fresh.load_checkpoint(path)
        assert fresh.halted_reason

    if completed:
        ids = list(clean['optimizer']['state'])
        for removed in (ids, ids[:1], ids[:2]):
            ck = copy.deepcopy(clean)
            for pid in removed:
                del ck['optimizer']['state'][pid]
            reject(ck, 'initialized parameter set')
        # Every parameter group is checked, including trunk and each policy head.
        for prefix in ('value.', 'cls', 'noop.', 'ptr.', 'tile.'):
            candidates = [pid for pid, (name, _) in enumerate(l.model.named_parameters())
                          if name.startswith(prefix) and pid in clean['optimizer']['state']]
            if not candidates:
                continue
            pid = candidates[0]
            expected = float(clean['optimizer']['state'][pid]['step'])
            for wrong in (0., expected-1, expected+1, .5, -1., float('nan'), float('inf'), -float('inf')):
                ck = copy.deepcopy(clean)
                ck['optimizer']['state'][pid]['step'].fill_(wrong)
                reject(ck, 'step counter mismatch|nonfinite')
    else:
        ck = copy.deepcopy(clean)
        p = next(l.model.parameters())
        ck['optimizer']['state'][0] = dict(step=torch.tensor(1.), exp_avg=torch.zeros_like(p),
                                          exp_avg_sq=torch.zeros_like(p))
        reject(ck, 'initialized parameter set')

    for mutation in ('duplicate', 'permutation', 'subset', 'relabel'):
        ck = copy.deepcopy(clean)
        ids = ck['optimizer']['param_groups'][0]['params']
        if mutation == 'duplicate':
            ids[1] = ids[0]
        elif mutation == 'permutation':
            ids[0], ids[1] = ids[1], ids[0]
        elif mutation == 'subset':
            ids.pop()
        else:
            ck['optimizer']['param_groups'][0]['params'] = [i+100 for i in ids]
            ck['optimizer']['state'] = {i+100: v for i, v in ck['optimizer']['state'].items()}
        reject(ck, 'parameter mapping')
    ck = copy.deepcopy(clean)
    del ck['optimizer_resume']
    reject(ck, 'evidence missing')
    ck = copy.deepcopy(clean)
    ck['optimizer_resume']['ppo_actor_masks'].append(b'\xff')
    reject(ck, 'eligibility history')
    if completed == 4:
        ck = copy.deepcopy(clean)
        ck['optimizer_resume']['ppo_actor_masks'].clear()
        heads = {pid for pid, (name, _) in enumerate(l.model.named_parameters())
                 if name.startswith(('noop.', 'ptr.', 'tile.'))}
        ck['optimizer']['state'] = {i: v for i, v in ck['optimizer']['state'].items() if i not in heads}
        reject(ck, 'eligibility history')
        for invalid in (b'', b'\x00\x00', np.array([True]*8), '11111111'):
            ck = copy.deepcopy(clean)
            ck['optimizer_resume']['ppo_actor_masks'][0] = invalid
            reject(ck, 'eligibility mask')
    for counter in ('optimizer_steps', 'trained_steps'):
        ck = copy.deepcopy(clean)
        ck[counter] += 1
        ck['halted_reason'] = 'diagnostic partial update'
        reject(ck, 'training counters')


@pytest.mark.parametrize('precision', ['float32', 'float64'])
def test_history_spans_forced_and_sparse_ppo_updates(admitted, tmp_path, precision):
    l = learner(admitted, precision=precision)
    for pattern in ('forced', 'eligible', 'forced', 'forced', 'sparse', 'eligible'):
        l.update([sample(l, pattern)])
    # 24 global steps, 12 PPO trunk steps, 0+2+4 policy-head steps.
    for name, p in l.model.named_parameters():
        expected = 24 if name.startswith('value.') else 6 if name.startswith(('noop.', 'ptr.', 'tile.')) else 12
        assert float(l.optimizer.state[p]['step']) == expected
    path = tmp_path/'history.pt'
    l.save_checkpoint(path)
    restored = learner(admitted, precision=precision)
    restored.load_checkpoint(path)
    assert_optimizer_equal(l, restored)
    ck = torch.load(path, weights_only=False)
    # Neither a deleted middle witness nor an emptied head state can redefine history.
    ck['optimizer_resume']['ppo_actor_masks'].pop(1)
    torch.save(ck, path)
    with pytest.raises(ContractError, match='eligibility history'):
        learner(admitted, precision=precision).load_checkpoint(path)


@pytest.mark.parametrize('precision', ['float32', 'float64'])
@pytest.mark.parametrize('completed', [0, 3])
@pytest.mark.parametrize('failure', ['after_step', 'before_step'])
def test_halted_partial_update_is_diagnostic_only(admitted, tmp_path, monkeypatch, precision, completed, failure):
    l = learner(admitted, precision=precision)
    for _ in range(completed):
        l.update([chunk(l)])
    original = l.optimizer.step
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if failure == 'before_step' or calls == 2:
            raise RuntimeError('injected mid-update failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(l.optimizer, 'step', fail)
    with pytest.raises(RuntimeError, match='injected'):
        l.update([chunk(l)])
    path = tmp_path/'partial.pt'
    l.save_checkpoint(path)
    assert l.halted_reason and l.update_index == completed
    # Even before a first step, a consumed permutation is not a proven boundary.
    with pytest.raises(ContractError, match='training counters|shuffle RNG'):
        learner(admitted, precision=precision).load_checkpoint(path)


def test_nonbyte_aligned_eligibility_padding_is_canonical(admitted, tmp_path):
    l = learner(admitted, microbatch=1, steps_per_update=6, batch_size=3)
    for _ in range(4):
        l.update([chunk(l, n=6, forced=True)])
    path = tmp_path/'padding.pt'
    l.save_checkpoint(path)
    restored = learner(admitted, microbatch=1, steps_per_update=6, batch_size=3)
    restored.load_checkpoint(path)
    assert_optimizer_equal(l, restored)
    ck = torch.load(path, weights_only=False)
    ck['optimizer_resume']['ppo_actor_masks'][0] = b'\x80'
    torch.save(ck, path)
    with pytest.raises(ContractError, match='eligibility padding'):
        learner(admitted, microbatch=1, steps_per_update=6, batch_size=3).load_checkpoint(path)
