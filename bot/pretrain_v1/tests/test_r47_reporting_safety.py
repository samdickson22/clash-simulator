"""Rehashed CPU evidence attacks and bounded native-producer fixtures. No engine."""
import copy
from dataclasses import replace
import math
import shutil

import pytest
import torch

from bot.pretrain_v1 import rl_reporting as R, rl_coordinator as C, stream_actor as A, rl_math
from bot.pretrain_v1.tests.test_r45_reporting_contract import build_chain, rehash_chain
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads, learner, chunk
from bot.pretrain_v1.tests.test_rl_coordinator import send, split


@pytest.fixture(scope='module')
def safety_source(tmp_path_factory):
    path = tmp_path_factory.mktemp('r47-chain')
    torch.set_num_threads(1)
    config, runtime = build_chain(path, admitted.__wrapped__(path), eligible=True)
    return path, config, runtime


@pytest.fixture
def safety_chain(tmp_path, safety_source):
    source, config, runtime = safety_source
    shutil.copytree(source/'checkpoints', tmp_path/'checkpoints')
    shutil.copyfile(source/'completed.json', tmp_path/'completed.json')
    return tmp_path, copy.deepcopy(config), copy.deepcopy(runtime)


def change(path, version, mutate):
    pt = path/f'checkpoints/update-{version:02d}.pt'
    state = torch.load(pt, map_location='cpu', weights_only=False)
    mutate(state)
    torch.save(state, pt)


def kl(state, mean, streak):
    state['high_kl_streak'] = streak
    state['last_metrics'].update(mean_kl=mean, p95_kl=mean, high_kl_streak=streak,
        per_opponent_kl={'frozen-live': dict(mean=mean, p95=mean, polls=262144)})


def authenticate(chain, **kwargs):
    path, config, runtime = chain
    rehash_chain(path)
    return R.authenticate_checkpoints(config, path, runtime, {0}, completed=True, **kwargs)


def test_rehashed_three_high_kl_updates_cannot_hide_stop(safety_chain):
    path, _, _ = safety_chain
    for v in (4, 5, 6):
        change(path, v, lambda s: kl(s, 1., 0))
    with pytest.raises(ValueError, match='streak'):
        authenticate(safety_chain)


@pytest.mark.parametrize('version', [1, 4, 16, 32])
def test_rehashed_negative_second_moment_at_any_stage(safety_chain, version):
    change(safety_chain[0], version, lambda s:
        next(iter(s['optimizer']['state'].values()))['exp_avg_sq'].fill_(-1.))
    with pytest.raises(ValueError, match='second moment'):
        authenticate(safety_chain)


def test_single_tiny_negative_in_last_second_moment_rejects(safety_chain):
    def negative(s):
        moment = list(s['optimizer']['state'].values())[-1]['exp_avg_sq']
        moment.reshape(-1)[-1] = -torch.finfo(moment.dtype).tiny
    change(safety_chain[0], 1, negative)
    with pytest.raises(ValueError, match='second moment'):
        authenticate(safety_chain)


@pytest.mark.parametrize('version', [1, 3, 4, 5, 31, 32])
def test_rehashed_invented_streak_before_and_after_warmup(safety_chain, version):
    change(safety_chain[0], version, lambda s: kl(s, 0., 2))
    with pytest.raises(ValueError, match='streak'):
        authenticate(safety_chain)


@pytest.mark.parametrize('completed', [False, True])
def test_rehashed_correct_third_streak_cannot_continue_or_complete(safety_chain, completed):
    path, config, runtime = safety_chain
    for v in (4, 5, 6):
        change(path, v, lambda s, v=v: kl(s, 1., v-3))
    rehash_chain(path)
    with pytest.raises(ValueError, match='mandatory halt'):
        R.authenticate_checkpoints(config, path, runtime, {6}, completed=completed)


def test_rehashed_valid_streaks_reset_at_exact_threshold(safety_chain):
    # Warmup never accumulates. The exact .5 comparison is unchanged. Carry
    # streak 1/2, reset, and carry again, including the final boundary.
    values = {1: (1., 0), 2: (1., 0), 3: (1., 0), 4: (.6, 1), 5: (.6, 2),
              6: (.5, 0), 7: (.6, 1), 8: (0., 0), 31: (.6, 1), 32: (.6, 2)}
    for v, (mean, streak) in values.items():
        change(safety_chain[0], v, lambda s, mean=mean, streak=streak: kl(s, mean, streak))
    assert set(authenticate(safety_chain)) == {0}


METRIC_FIELDS = (
    'update version warmup generated_steps trained_steps optimizer_steps polls actor_polls forced_polls '
    'busy_polls boundary_declined_steps old_logp_max_error old_value_max_error legal_action_checks '
    'cadence_checks mean_entropy mean_kl p95_kl per_opponent_kl plays_per_300s play_rates_reported '
    'high_kl_streak halted_reason policy_sha256').split()


@pytest.mark.parametrize('field', METRIC_FIELDS)
def test_rehashed_every_native_metric_is_required(safety_chain, field):
    change(safety_chain[0], 1, lambda s: s['last_metrics'].pop(field))
    with pytest.raises(ValueError, match='metric fields'):
        authenticate(safety_chain)


BAD_METRICS = [
    ('busy_polls', -1), ('busy_polls', 1), ('busy_polls', False),
    ('actor_polls', -1), ('actor_polls', 262145), ('actor_polls', 262144.),
    ('forced_polls', -1), ('forced_polls', False), ('boundary_declined_steps', 1),
    ('boundary_declined_steps', -1), ('boundary_declined_steps', False),
    ('old_logp_max_error', 1.), ('old_value_max_error', 1.),
    ('old_logp_max_error', math.nextafter(2e-6, math.inf)), ('old_value_max_error', -1e-10),
    ('old_logp_max_error', float('nan')), ('old_value_max_error', float('inf')),
    ('old_logp_max_error', False), ('mean_entropy', -1e-10), ('mean_entropy', 8.),
    ('mean_entropy', float('nan')), ('mean_entropy', float('inf')), ('mean_entropy', '0'),
    ('mean_kl', float('nan')), ('mean_kl', float('inf')), ('mean_kl', -1.), ('mean_kl', False),
    ('p95_kl', -1.), ('p95_kl', float('nan')), ('p95_kl', float('inf')), ('p95_kl', True),
    ('per_opponent_kl', {}), ('per_opponent_kl', []),
    ('per_opponent_kl', {'x': dict(mean=0., p95=0., polls=0)}),
    ('per_opponent_kl', {'x': dict(mean=0., p95=0., polls=262143)}),
    ('per_opponent_kl', {'x': dict(mean=0., p95=0., polls=262144.)}),
    ('per_opponent_kl', {'x': dict(mean=0., p95=0.)}),
    ('per_opponent_kl', {'': dict(mean=0., p95=0., polls=262144)}),
    ('per_opponent_kl', {'x': dict(mean=float('nan'), p95=0., polls=262144)}),
    ('per_opponent_kl', {'x': dict(mean=0., p95=-1., polls=262144)}),
    ('per_opponent_kl', {'x': dict(mean=1., p95=1., polls=262144)}),
    ('per_opponent_kl', {'x': dict(mean=0., p95=.001, polls=262144)}),
    ('plays_per_300s', {'x': float('nan')}), ('plays_per_300s', {'x': 81.}),
    ('plays_per_300s', []), ('play_rates_reported', 1), ('warmup', 1),
    ('update', 1.), ('version', True), ('polls', 262144.), ('generated_steps', 262144.),
    ('trained_steps', 262144.), ('optimizer_steps', 256.), ('legal_action_checks', 262144.),
    ('cadence_checks', 262144.), ('high_kl_streak', False), ('halted_reason', 'stopped'),
    ('policy_sha256', 'changed'),
]


@pytest.mark.parametrize('field,value', BAD_METRICS)
def test_rehashed_invalid_metric_values_reject(safety_chain, field, value):
    change(safety_chain[0], 1, lambda s: s['last_metrics'].update({field: value}))
    with pytest.raises(ValueError):
        authenticate(safety_chain)


def test_valid_complete_metrics_positive_moments_and_group_accounting(safety_chain):
    def valid(s):
        for values in s['optimizer']['state'].values():
            values['exp_avg_sq'].fill_(.25)
            values['exp_avg'].fill_(-.25)
        s['last_metrics'].update(old_logp_max_error=2e-6, old_value_max_error=2e-6,
            mean_entropy=math.log(2305), mean_kl=.1, p95_kl=.2,
            per_opponent_kl={'a': dict(mean=0., p95=0., polls=131072),
                             'b': dict(mean=.2, p95=.2, polls=131072)})
    change(safety_chain[0], 1, valid)
    assert set(authenticate(safety_chain)) == {0}


def test_tiny_negative_kl_from_native_float32_calculation_is_valid(safety_chain):
    # Cancellation can put near-identical distributions just below zero.
    change(safety_chain[0], 4, lambda s: kl(s, -2e-7, 0))
    assert set(authenticate(safety_chain)) == {0}


def test_negative_second_moment_next_adam_step_is_nonfinite():
    # Demonstrate impact using only this disposable CPU parameter, never a
    # production update or a changed optimizer/resume algorithm.
    p = torch.nn.Parameter(torch.tensor([1.], dtype=torch.float64))
    optimizer = torch.optim.AdamW([p], lr=1e-5, weight_decay=0)
    p.grad = torch.ones_like(p)
    optimizer.step()
    optimizer.state[p]['exp_avg_sq'].fill_(-1.)
    p.grad = torch.ones_like(p)
    optimizer.step()
    assert not bool(torch.isfinite(p).all())


def test_real_learner_offset_stops_after_updates_four_five_six(admitted, tmp_path, monkeypatch):
    l = learner(admitted, updates=32)
    original = rl_math.joint_kl
    monkeypatch.setattr(rl_math, 'joint_kl', lambda *args: original(*args)+.6)
    masks, streak = [], 0
    proof = learner(admitted, updates=32)
    for v in range(1, 7):
        metrics = l.update([chunk(l)])
        assert metrics['high_kl_streak'] == (0 if v <= 3 else v-3)
        assert bool(metrics['halted_reason']) == (v == 6)
        path = tmp_path/f'offset-{v}.pt'
        l.save_checkpoint(path)
        if v < 6:
            _, masks, saved = R.verify_checkpoint(proof, path, v, masks, previous_high_kl_streak=streak)
            streak = saved['high_kl_streak']
        else:
            with pytest.raises(ValueError, match='halted_reason'):
                R.verify_checkpoint(proof, path, v, masks, previous_high_kl_streak=streak)
    with pytest.raises(ValueError, match='halted'):
        l.update([chunk(l)])


def test_real_learner_coordinator_queue_all_32_updates(admitted, tmp_path):
    l = learner(admitted, updates=32)
    caps = C.queue_capacity(8)
    q = A.AtomicChunkQueue(tmp_path/'queue', max_chunks=caps[0], max_bytes=caps[1],
                           runtime_manifest=l.runtime_manifest)
    c = C.Coordinator(l, q, quotas={'a': 8}, checkpoint_dir=tmp_path/'checkpoints',
                      config=C.CoordinatorConfig(wait_seconds=30, test_only=True), stop_notifier=lambda why: None)
    try:
        for v in range(32):
            ch = A.Chunk(**vars(chunk(l, actor_id='a')))
            send(c, ch, seq=v, game=f'game-{v}', game_seq=v)
        final = c.finalize()
        assert c.join(30)
        proof = learner(admitted, updates=32)
        masks, streak = [], 0
        for v in range(33):
            policy, masks, metrics = R.verify_checkpoint(proof, tmp_path/f'checkpoints/update-{v:02d}.pt',
                v, masks, previous_high_kl_streak=streak)
            assert policy == R.read(tmp_path/f'checkpoints/update-{v:02d}.json')['policy_sha256']
            if v:
                assert set(metrics) == set(METRIC_FIELDS)
                streak = metrics['high_kl_streak']
            else:
                assert metrics is None
        assert final['generated'] == final['trained'] == 256
        assert final['completed_games'] == 32 and l.optimizer_steps == 128 and len(masks) == 29
    finally:
        if not c.join(.1):
            c.abort('CPU fixture cleanup')
            assert c.join(30)


def test_real_producer_multiple_opponents_and_forced_only(admitted, tmp_path):
    l = learner(admitted)
    proof = learner(admitted)
    for v in range(1, 5):
        full = chunk(l, forced=(v == 4))
        parts = [split(full, 0, 4), replace(split(full, 4, 8), opponent_id='second')]
        metrics = l.update(parts)
        assert set(metrics['per_opponent_kl']) == {'frozen-live', 'second'}
        path = tmp_path/f'multiple-{v}.pt'
        l.save_checkpoint(path)
        R.verify_checkpoint(proof, path, v)
    assert metrics['actor_polls'] == 0 and metrics['mean_entropy'] == 0
