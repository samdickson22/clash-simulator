"""Precision contract checks with toy budgets. No registered RL launch."""
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import types

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import featurize as F, policy, rl_learner as L, stream_actor as A, rl_math
from bot.pretrain_v1.checks.qualify_fp64 import math_backend
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads, learner, chunk, state, validate
from bot.pretrain_v1.tests.test_stream_actor import make_actor, start, view


def test_precision_is_explicit_test_only_and_default_record_unchanged(admitted):
    config = L.LearnerConfig(seed=L.SEEDS[0], size='M')
    assert config.precision == config.record()['dtype'] == 'float32'
    assert 'precision' not in config.record()
    with pytest.raises(L.ContractError, match='qualification-only'):
        replace(config, precision='float64')
    with pytest.raises(L.ContractError, match='unsupported precision'):
        replace(config, precision='float16', test_only=True)
    fp32 = learner(admitted)
    fp64 = learner(admitted, precision='float64')
    assert fp32.anchor_sha256 == fp64.anchor_sha256
    assert fp32.policy_sha256 != fp64.policy_sha256
    changed_cfg = dict(fp64.model.cfg)
    fp64.model.cfg['drop'] = .2
    assert L.policy_sha256(fp64.model, fp64.feature_hash) != fp64.policy_sha256
    fp64.model.cfg = changed_cfg
    for model in (fp64.model, fp64.anchor):
        assert all(t.dtype == torch.float64 for t in model.state_dict().values())
    assert all(p is q for p, q in zip(fp64.model.parameters(), fp64.optimizer.param_groups[0]['params']))
    assert all(not p.requires_grad and p.grad is None for p in fp64.anchor.parameters())
    assert A.policy_sha256(fp64.model) == fp64.policy_sha256


@pytest.mark.parametrize('microbatch', [128, 256])
def test_actual_session_padded_batches_and_mixed_chunk_widths(admitted, microbatch):
    l = L.Learner(**admitted, config=L.LearnerConfig(seed=L.SEEDS[0], size='M', precision='float64',
                  microbatch=microbatch, steps_per_update=512, batch_size=512, test_only=True))
    with math_backend(torch):
        # Different padding maxima and a short final batch; Session is unchanged.
        c = chunk(l, n=257, ragged=True)
        validate(c, l)
        widths = {key: c.features[key].shape[1] for key in ('ent', 'ev', 'rev')}
        arrays, vectors = validate(c, l)
        trimmed = {k: v[256:].copy() for k, v in arrays.items()}
        for key in ('ent', 'ev', 'rev'):
            width = max(1, int(trimmed[key+'_mask'].sum(1).max()))
            trimmed[key] = trimmed[key][:, :width]
            trimmed[key+'_mask'] = trimmed[key+'_mask'][:, :width]
        for ix in (np.arange(128), np.arange(256), np.array([256]), np.array([0, 257])):
            b, legal = l._batch([arrays, trimmed], np.array([0, 257, 258]), ix)
            with torch.no_grad():
                g, t, value = l._forward(b, legal)
                action = np.r_[c.action, c.action[-1:]][ix]
                dt = np.r_[c.dt, c.dt[-1:]][ix]
                logp, _ = rl_math.joint_terms(g, t, torch.tensor(action), torch.tensor(dt))
            assert np.max(np.abs(logp.double().numpy()-np.r_[c.old_logp, c.old_logp[-1:]][ix])) <= 2e-6
            assert np.max(np.abs(value.numpy()-np.r_[c.old_value, c.old_value[-1:]][ix])) <= 2e-6
        assert widths == {key: c.features[key].shape[1] for key in widths}


def test_fp64_full_update_gradients_anchor_immutability_resume_and_postupdate_session(admitted, tmp_path):
    l = learner(admitted, precision='float64')
    initial_anchor = state(l.anchor)
    saw_policy_gradient = False
    with math_backend(torch):
        for i in range(4):
            c = chunk(l, ragged=True, mixed=True)
            originals = {k: v.tobytes() for k, v in c.features.items()}
            vectors = {k: getattr(c, k).tobytes() for k in A._VECTORS}
            for a in [*c.features.values(), *(getattr(c, k) for k in A._VECTORS)]:
                a.flags.writeable = False
            result = l.update([c])
            assert result['old_logp_max_error'] <= 2e-6 and result['old_value_max_error'] <= 2e-6
            assert all(p.grad is None or (p.grad.dtype == torch.float64 and bool(torch.isfinite(p.grad).all()))
                       for p in l.model.parameters())
            if i == 3:
                saw_policy_gradient = any(p.grad is not None and bool(p.grad.abs().sum() > 0)
                                          for name, p in l.model.named_parameters() if name.startswith('tile.'))
            assert all(torch.equal(v, l.anchor.state_dict()[k]) for k, v in initial_anchor.items())
            assert all(not p.requires_grad and p.grad is None for p in l.anchor.parameters())
            assert originals == {k: v.tobytes() for k, v in c.features.items()}
            assert vectors == {k: getattr(c, k).tobytes() for k in vectors}
        assert saw_policy_gradient
        for values in l.optimizer.state.values():
            assert values['exp_avg'].dtype == values['exp_avg_sq'].dtype == torch.float64
            # AdamW step is a scalar counter, not a model-precision moment.
            assert values['step'].dtype == torch.float32 and values['step'].ndim == 0
        path = tmp_path/'candidate.pt'
        l.save_checkpoint(path)
        restored = learner(admitted, precision='float64')
        restored.load_checkpoint(path)
        assert restored.policy_sha256 == l.policy_sha256
        assert restored.config.record()['test_only'] and restored.config.record()['dtype'] == 'float64'
        c = chunk(restored, ragged=True)
        assert restored.update([c])['old_value_max_error'] <= 2e-6
    with pytest.raises(RuntimeError, match='not admitted'):
        policy.load(path)
    with pytest.raises(L.ContractError, match='config mismatch'):
        learner(admitted).load_checkpoint(path)


@pytest.mark.parametrize('corrupt', ['model', 'anchor', 'optimizer', 'provenance', 'config', 'digest'])
def test_checkpoint_refuses_dtype_and_provenance_corruption(admitted, tmp_path, corrupt):
    l = learner(admitted, precision='float64')
    with math_backend(torch):
        l.update([chunk(l)])
    path = tmp_path/'candidate.pt'
    l.save_checkpoint(path)
    ck = torch.load(path, weights_only=False)
    if corrupt in ('model', 'anchor'):
        key = next(iter(ck[corrupt]))
        ck[corrupt][key] = ck[corrupt][key].float()
    elif corrupt == 'optimizer':
        values = next(iter(ck['optimizer']['state'].values()))
        values['exp_avg'] = values['exp_avg'].float()
    elif corrupt == 'provenance':
        ck['runtime_manifest']['actor_source_sha256'] = 'b'*64
    elif corrupt == 'config':
        ck['config']['dtype'] = 'float32'
    else:
        ck['policy_sha256'] = 'f'*64
    torch.save(ck, path)
    fresh = learner(admitted, precision='float64')
    with pytest.raises(L.ContractError):
        fresh.load_checkpoint(path)
    assert fresh.halted_reason


def test_policy_update_and_queue_keep_fp64_and_refuse_cast(admitted, monkeypatch, tmp_path):
    model = learner(admitted, precision='float64').model
    queue = A.AtomicChunkQueue(tmp_path/'queue', max_bytes=2**20, max_chunks=10,
                              runtime_manifest=dict(source='unit-fixture-only'))
    seen = []
    def publish(c, boundary):
        receipt = queue.write(c)
        m = queue.load(receipt, expected_version=c.version, expected_policy_sha256=c.policy_sha256)
        assert m.old_logp.dtype == m.old_value.dtype == np.float64
        assert np.array_equal(m.old_logp, c.old_logp) and np.array_equal(m.old_value, c.old_value)
        assert all(np.array_equal(m.features[k], v) for k, v in c.features.items())
        for z in [*m.features.values(), *(getattr(m, k) for k in A._VECTORS)]:
            z._mmap.close()
        queue.acknowledge(receipt)
        seen.append(boundary.reason)
        if boundary.reason == 'quota':
            weights = {k: v.clone() for k, v in model.state_dict().items()}
            if len(seen) > 1:
                weights['cls'] = weights['cls'].float()
            return A.PolicyUpdate(c.version+1, A.policy_sha256(model), weights, 2)
        return A.PolicyUpdate(c.version, c.policy_sha256)
    a = make_actor(model, publish, provenance_sha256=queue.provenance_sha256,
                   quota_steps=2, chunk_rows=2)
    b, own = start(a, monkeypatch)
    with math_backend(torch):
        for i in range(4):
            b.tick = 90+5*i
            a.act(view(b.tick))
        assert a.version == 1
        assert all(t.dtype == torch.float64 for t in a.model.original.state_dict().values())
        b.tick = 110
        with pytest.raises(A.StreamError, match='dtypes'):
            a.act(view(b.tick))


@pytest.mark.parametrize('size', ['S100', 'M'])
def test_fp32_byte_identical_to_landed_model_on_retained_real_features(size):
    root = Path(os.environ.get('PRETRAIN_REAL_FIXTURES', '/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness'))
    folder = root/'torch271-inputs'/('numerics-input-'+size)
    anchor = root.parent/'sweep/anchors'/size/'anchor.pt'
    if not folder.exists() or not anchor.exists():
        pytest.skip('retained local real fixture unavailable')
    source = subprocess.check_output(['git', 'show', 'ac3410d8b:bot/pretrain_v1/model.py'], text=True)
    baseline = types.ModuleType('bot.pretrain_v1._landed_model')
    baseline.__package__ = 'bot.pretrain_v1'
    exec(compile(source, '<ac3410d8b:model.py>', 'exec'), baseline.__dict__)
    ck = torch.load(anchor, map_location='cpu', weights_only=False)
    old = baseline.PolicyV1(**ck['cfg']).eval()
    old.load_state_dict(ck['model'])
    new = policy.PolicyV1(**ck['cfg']).eval()
    new.load_state_dict(ck['model'])
    first = sorted(folder.glob('chunk-*'))[0]
    batch = {p.stem[2:]: torch.from_numpy(np.load(p, allow_pickle=False)) for p in first.glob('f_*.npy')}
    legal = torch.from_numpy(policy.tiles_ok_np(batch['hand'].numpy(), batch['slot_ok'].numpy(), batch['alive'].numpy()))
    with torch.no_grad():
        for b, mask in ((batch, legal), ({k: v[:1] for k, v in batch.items()}, legal[:1])):
            cls0, hand0 = old.trunk(b)
            cls1, hand1 = new.trunk(b)
            assert torch.equal(cls0, cls1) and torch.equal(hand0, hand1)
            assert torch.equal(old.gate_logits(cls0, hand0, b['slot_ok']), new.gate_logits(cls1, hand1, b['slot_ok']))
            assert torch.equal(old.tile_logits_all(cls0, hand0, mask), new.tile_logits_all(cls1, hand1, mask))
            assert torch.equal(old.value(cls0), new.value(cls1))
    assert L.policy_sha256(old, F.feature_hash()) == L.policy_sha256(new, F.feature_hash())
