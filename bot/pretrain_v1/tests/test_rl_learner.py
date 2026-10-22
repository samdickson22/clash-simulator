"""CPU-only component tests. Toy budgets cannot be mistaken for registered launches."""
from dataclasses import replace
import json
import random

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import featurize as F, rl_math
from bot.pretrain_v1.model import PolicyV1, collate, tiles_ok_np
from bot.pretrain_v1.policy import Session
from bot.pretrain_v1.policy_trace import PolicyTrace
from bot.pretrain_v1.rl_learner import (
    Chunk, ContractError, GAMEDATA_SHA256, Learner, LearnerConfig, NATIVE_SHA256,
    PlayRate, SEEDS, file_sha256, policy_sha256, prepare_targets, validate_chunk,
)
from bot.pretrain_v1.tests.test_featurize import rec, unit


@pytest.fixture(autouse=True)
def cpu_threads():
    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(threads)


@pytest.fixture
def admitted(tmp_path):
    torch.manual_seed(12)
    # Nonzero dropout deliberately verifies that the learner always uses eval mode.
    model = PolicyV1(d=24, layers=1, heads=3, ffn=48, drop=.6).eval()
    path = tmp_path/'anchor.pt'
    torch.save(dict(model=model.state_dict(), cfg=model.cfg, feature_hash=F.feature_hash(),
                    gate_bias=float(model.gate_bias), admission=dict(eligible=True)), path)
    digest = file_sha256(path)
    path.with_name('selection.json').write_text(json.dumps(dict(admitted=True, smoke=False, file='anchor.pt', sha256=digest)))
    return dict(anchor_path=path, anchor_sha256=digest, model_cfg=model.cfg,
                runtime_manifest=dict(native_sha256=NATIVE_SHA256, gamedata_sha256=GAMEDATA_SHA256,
                                      actor_source_sha256='a'*64, assembler='registered-test-runtime'))


def learner(admitted, microbatch=2, **kwargs):
    cfg = LearnerConfig(seed=SEEDS[0], size='M', microbatch=microbatch, steps_per_update=8,
                        updates=8, batch_size=4, test_only=True)
    return Learner(**admitted, config=replace(cfg, **kwargs))


def chunk(learner, n=8, *, actor_id='worker-0', terminal_tail=True, mixed=False, forced=False, ragged=False,
          eligible_rows=None, accept_plays=True):
    trace = PolicyTrace(learner.model)
    session = Session(trace, 43)
    features, actions, logps, values, terminals, rewards = [], [], [], [], [], []
    step = 0
    for i in range(n):
        trace.clear()
        r = rec(90+step*5, elixir=0. if forced or i == 1 or
                (eligible_rows is not None and i not in eligible_rows) else 5.)
        if ragged and i == 0:
            r['units'] = [unit('Knight', 'Knight', 1, 3, 20)]
        d = session.step(r)
        features.append(session.last_feat)
        actions.append(d.action)
        logps.append(trace.log_probability(d))
        values.append(d.value)
        terminal = (terminal_tail and i == n-1) or (mixed and i == n//2-1)
        terminals.append(terminal)
        rewards.append((1. if i == n-1 else -1.) if terminal else 0.)
        if d.status == 'play' and accept_plays:
            session.accepted(d)
        step += 1
        if terminal:
            session = Session(trace, 43+i)
            step = 0
    b = {k: v.numpy() for k, v in collate(features).items()}
    return Chunk(features=b, action=np.array(actions, np.int64), old_logp=np.array(logps, np.float64),
                 old_value=np.array(values, np.float64), reward=np.array(rewards, np.float64),
                 terminated=np.array(terminals, bool), actor=b['slot_ok'].any(1), dt=np.full(n, 5, np.int16),
                 bootstrap=0. if terminal_tail else .25, version=learner.version, actor_id=actor_id,
                 seed=learner.config.seed, anchor_sha256=learner.anchor_sha256, policy_sha256=learner.policy_sha256,
                 generated_steps=n, provenance_sha256=learner.provenance_sha256, opponent_id='frozen-live')


def validate(c, l):
    return validate_chunk(c, config=l.config, version=l.version, anchor_sha256=l.anchor_sha256,
                          policy_sha256=l.policy_sha256, provenance_sha256=l.provenance_sha256, model_cfg=l.model.cfg)


def state(model):
    return {k: v.clone() for k, v in model.state_dict().items()}


def test_registered_config_is_fixed_and_records_accumulation():
    for seed in SEEDS:
        for size, micro in [('S100', 256), ('M', 128)]:
            cfg = LearnerConfig(seed=seed, size=size, microbatch=micro)
            record = cfg.record()
            assert cfg.steps_per_update*cfg.updates == 8388608
            assert record['accumulation_steps'] == 2048//micro
            assert record['optimizer_steps_per_update'] == 256
            assert record['weight_decay'] == 0 and record['learning_rate'] == 1e-5
    for kw in [dict(seed=1), dict(size='L'), dict(microbatch=512), dict(batch_size=1024),
               dict(updates=31), dict(steps_per_update=8)]:
        with pytest.raises(ContractError):
            LearnerConfig(**(dict(seed=SEEDS[0], size='S100') | kw))


def test_real_session_logp_joint_distribution_all_slots(admitted):
    l = learner(admitted)
    c = chunk(l)
    validate(c, l)
    b = {k: torch.tensor(v) for k, v in c.features.items()}
    legal = torch.tensor(tiles_ok_np(c.features['hand'], c.features['slot_ok'], c.features['alive']))
    with torch.no_grad():
        g, t, value = l._forward(b, legal)
    logp, entropy = rl_math.joint_terms(g, t, torch.tensor(c.action), torch.tensor(c.dt))
    assert np.max(np.abs(logp.double().numpy()-c.old_logp)) <= 2e-6
    assert np.max(np.abs(value.double().numpy()-c.old_value)) <= 2e-6
    # Independently enumerate ALL slots and tiles. Illegal gate/tile masses vanish.
    p = torch.cat([g.softmax(-1)[:, :1], (g.softmax(-1)[:, 1:, None]*t.softmax(-1)).flatten(1)], 1)
    e = -torch.special.xlogy(p, p).sum(-1)
    assert torch.allclose(e, entropy, atol=2e-6)
    ag, at = g+.2*torch.randn_like(g), t+.2*torch.randn_like(t)
    ag = ag.masked_fill(torch.cat([torch.zeros(len(g), 1, dtype=torch.bool), ~b['slot_ok']], 1), -1e9)
    at = at.masked_fill(~legal, -1e9)
    q = torch.cat([ag.softmax(-1)[:, :1], (ag.softmax(-1)[:, 1:, None]*at.softmax(-1)).flatten(1)], 1)
    exact = (torch.special.xlogy(p, p)-torch.special.xlogy(p, q)).sum(-1)
    assert torch.allclose(rl_math.joint_kl(g, t, ag, at), exact, atol=2e-6)


def test_three_warmups_freeze_every_actor_parameter_then_update_four_changes_policy(admitted):
    l = learner(admitted)
    initial = state(l.model)
    anchor = state(l.anchor)
    for i in range(3):
        result = l.update([chunk(l)])
        assert result['warmup'] and result['update'] == i+1
        assert result['forced_polls'] > 0 and result['actor_polls'] > 0
        assert result['polls'] == result['legal_action_checks'] == result['cadence_checks'] == 8
        assert not l.model.training and not l.anchor.training
        for name, value in l.model.state_dict().items():
            if not name.startswith('value.'):
                assert torch.equal(value, initial[name]), name
    assert any(not torch.equal(v, initial[k]) for k, v in l.model.state_dict().items() if k.startswith('value.'))
    result = l.update([chunk(l)])
    assert not result['warmup'] and result['optimizer_steps'] == 16
    now = l.model.state_dict()
    assert any(not torch.equal(v, initial[k]) for k, v in now.items() if k.startswith(('noop.', 'ptr.', 'tile.')))
    assert not torch.equal(now['cls'], initial['cls'])
    assert all(torch.equal(v, anchor[k]) for k, v in l.anchor.state_dict().items())
    assert all(p.grad is None and not p.requires_grad for p in l.anchor.parameters())
    assert l.model.cfg['drop'] == .6


def test_microbatch_update_equivalence_with_forced_and_all_forced_minibatches(admitted):
    def capture_gradients(l):
        snapshots = []
        original = l.optimizer.step
        def step(*args, **kwargs):
            snapshots.append({name: p.grad.clone() for name, p in l.model.named_parameters() if p.grad is not None})
            return original(*args, **kwargs)
        l.optimizer.step = step
        return snapshots
    for forced in (False, True):
        small, whole = learner(admitted, 1), learner(admitted, 4)
        small_grads, whole_grads = capture_gradients(small), capture_gradients(whole)
        for _ in range(4):
            a, b = small.update([chunk(small, forced=forced)]), whole.update([chunk(whole, forced=forced)])
            if forced:
                assert a['actor_polls'] == b['actor_polls'] == 0
                assert a['mean_entropy'] == b['mean_entropy'] == a['mean_kl'] == 0.
        assert len(small_grads) == len(whole_grads) == 16
        for ga, gb in zip(small_grads, whole_grads):
            assert ga.keys() == gb.keys()
            for name in ga:
                torch.testing.assert_close(ga[name], gb[name], rtol=1e-4, atol=2e-7, msg=name)
        # CPU batched attention has roundoff even in eval mode. Adam amplifies near-zero
        # attention-key bias gradients. Compare real gradients above, and outputs here.
        c = chunk(small)
        b = {k: torch.tensor(v) for k, v in c.features.items()}
        legal = torch.tensor(tiles_ok_np(c.features['hand'], c.features['slot_ok'], c.features['alive']))
        with torch.no_grad():
            out_a, out_b = small._forward(b, legal), whole._forward(b, legal)
        for va, vb in zip(out_a, out_b):
            torch.testing.assert_close(va, vb, rtol=1e-5, atol=2e-6)


def test_chunk_gae_real_terminals_nonterminal_bootstrap_global_normalization(admitted):
    l = learner(admitted)
    c = chunk(l, n=4, mixed=True, terminal_tail=False)
    d = chunk(l, n=4, actor_id='worker-1', terminal_tail=True)
    validate(c, l); validate(d, l)
    adv, returns = prepare_targets([c, d])
    raw, expected = [], []
    for data in (c, d):
        # Independent reverse recurrence with terminal reset.
        next_value, acc = data.bootstrap, 0.
        a = np.zeros(4)
        for i in range(3, -1, -1):
            keep = 1.-data.terminated[i]
            delta = data.reward[i]+keep*next_value-data.old_value[i]
            acc = delta+.95*keep*acc
            a[i] = acc
            next_value = data.old_value[i]
        raw.extend(a)
        expected.extend(a+data.old_value)
    eligible = np.r_[c.actor, d.actor]
    raw = np.array(raw)
    target = np.zeros(8)
    target[eligible] = (raw[eligible]-raw[eligible].mean())/max(raw[eligible].std(), 1e-8)
    np.testing.assert_allclose(adv, target, atol=1e-12)
    np.testing.assert_allclose(returns, expected, atol=1e-12)
    assert returns[3] != 0.  # An unfinished tail bootstraps instead of becoming a terminal draw.
    assert l.update([c, d])['polls'] == 8


@pytest.mark.parametrize('field,value,message', [
    ('version', 1, 'version'), ('seed', SEEDS[1], 'seed'), ('anchor_sha256', '0'*64, 'hash'),
    ('policy_sha256', '0'*64, 'hash'), ('provenance_sha256', '0'*64, 'provenance'),
    ('bootstrap', float('nan'), 'bootstrap'), ('bootstrap', .2, 'terminal'),
    ('generated_steps', 7, 'budget'), ('generated_steps', 9, 'budget'),
])
def test_bad_metadata_stops_without_retries(admitted, field, value, message):
    l = learner(admitted)
    c = replace(chunk(l), **{field: value})
    initial = state(l.model)
    with pytest.raises(ContractError, match=message):
        l.update([c])
    assert l.update_index == l.optimizer_steps == 0
    assert all(torch.equal(v, initial[k]) for k, v in l.model.state_dict().items())
    assert l.generated_steps == c.generated_steps
    with pytest.raises(ContractError, match='halted'):
        l.update([chunk(l)])


@pytest.mark.parametrize('change,message', [
    ('logp', 'old_logp parity'), ('nonfinite', 'nonfinite'), ('nonterminal_reward', 'terminal-only'),
    ('cadence', 'cadence'), ('eligible', 'eligibility'), ('illegal', 'illegal sampled'),
    ('extra_key', 'keys'), ('dtype', 'dtype'), ('object', 'object/string'), ('shape', 'bound/mask'),
    ('busy', 'legality/busy'), ('old_value', 'old_value parity'),
])
def test_bad_arrays_fail_before_any_optimizer_step(admitted, change, message):
    l = learner(admitted)
    c = chunk(l)
    if change == 'logp':
        c.old_logp[np.flatnonzero(c.actor)[0]] -= .01
    elif change == 'old_value':
        c.old_value[0] += .01
    elif change == 'nonfinite':
        c.old_logp[0] = np.nan
    elif change == 'nonterminal_reward':
        c.reward[0] = .1
    elif change == 'cadence':
        c.dt[0] = 10
    elif change == 'eligible':
        c.actor[0] = not c.actor[0]
    elif change == 'illegal':
        c.action[np.flatnonzero(~c.actor)[0]] = 0
        # Forced action is separately checked before geometry.
        message = 'forced/busy'
    elif change == 'extra_key':
        c.features['private_state'] = np.zeros(8)
    elif change == 'dtype':
        c.features['ent'] = c.features['ent'].astype(np.int32)
    elif change == 'object':
        c.features['ent'] = c.features['ent'].astype(object)
    elif change == 'shape':
        c.features['ent'] = np.zeros((8, F.MAX_ENT+1, F.E_COLS), np.int16)
    elif change == 'busy':
        c.features['glob'][0, F.G_BUSY] = 1
    with pytest.raises(ContractError, match=message):
        l.update([c])
    assert l.optimizer_steps == 0 and l.generated_steps == 8


def test_anchor_selection_feature_config_and_state_identity(admitted):
    for field, value, message in [('anchor_sha256', '0'*64, 'file hash'),
                                  ('model_cfg', dict(admitted['model_cfg'], drop=.1), 'configuration')]:
        with pytest.raises(ContractError, match=message):
            learner(dict(admitted, **{field: value}))
    receipt = admitted['anchor_path'].with_name('selection.json')
    original = receipt.read_text()
    receipt.write_text(json.dumps(dict(admitted=False)))
    with pytest.raises(ContractError, match='receipt'):
        learner(admitted)
    receipt.write_text(original)
    l = learner(admitted)
    c = chunk(l)
    with torch.no_grad():
        l.anchor.gate_bias.add_(.01)
    with pytest.raises(ContractError, match='anchor changed'):
        l.update([c])


def test_readonly_memmaps_cpu_tensors_mixed_ragged_and_no_input_mutation(admitted, tmp_path):
    l = learner(admitted)
    chunks = [chunk(l, n=4, actor_id='a', ragged=True), chunk(l, n=4, actor_id='b')]
    before = []
    mapped = []
    for i, c in enumerate(chunks):
        b = {}
        for key, value in c.features.items():
            path = tmp_path/f'{i}-{key}.npy'
            np.save(path, value, allow_pickle=False)
            b[key] = np.load(path, mmap_mode='r', allow_pickle=False)
            before.append((path, file_sha256(path)))
        vectors = {}
        for key in ('action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt'):
            a = getattr(c, key)
            a.flags.writeable = False
            vectors[key] = a
        mapped.append(replace(c, features=b, **vectors))
    l.update(mapped)
    assert all(file_sha256(path) == digest for path, digest in before)
    c = chunk(l)
    tensors = {k: torch.tensor(v) for k, v in c.features.items()}
    validate(replace(c, features=tensors), l)
    assert all(not a.flags.writeable for c in mapped for a in c.features.values())


def test_atomic_checkpoint_exact_continuation_all_rng_and_resume_pins(admitted, tmp_path):
    a = learner(admitted)
    for _ in range(3):
        a.update([chunk(a)])
    path = tmp_path/'resume.pt'
    a.save_checkpoint(path)
    assert list(tmp_path.glob('*.tmp')) == []
    expected_rng = (random.random(), np.random.random(), torch.rand(3))
    expected = a.update([chunk(a)])
    expected_state = state(a.model)
    b = learner(admitted)
    assert b.load_checkpoint(path)['update'] == 3
    got_rng = (random.random(), np.random.random(), torch.rand(3))
    assert expected_rng[:2] == got_rng[:2]
    assert torch.equal(expected_rng[2], got_rng[2])
    result = b.update([chunk(b)])
    assert result == expected
    assert all(torch.equal(v, expected_state[k]) for k, v in b.model.state_dict().items())
    sa, sb = a.optimizer.state_dict(), b.optimizer.state_dict()
    assert sa['param_groups'] == sb['param_groups']
    for k in sa['state']:
        assert all(torch.equal(v, sb['state'][k][name]) if torch.is_tensor(v) else v == sb['state'][k][name]
                   for name, v in sa['state'][k].items())
    c = learner(admitted, microbatch=1)
    with pytest.raises(ContractError, match='config mismatch'):
        c.load_checkpoint(path)
    bad = torch.load(path, weights_only=False)
    bad['model']['gate_bias'] += 1.
    torch.save(bad, tmp_path/'bad.pt')
    with pytest.raises(ContractError, match='policy state hash'):
        learner(admitted).load_checkpoint(tmp_path/'bad.pt')


def test_play_rate_metadata_reports_rates_and_stops_outside_registered_range(admitted):
    l = learner(admitted)
    report = l.update([chunk(l)], play_rates=[PlayRate('game-0', 30, 150.)])
    assert report['plays_per_300s'] == {'game-0': 60.}
    assert report['play_rates_reported']
    for plays in (14, 81):
        l = learner(admitted)
        with pytest.raises(ContractError, match='play-rate collapse'):
            l.update([chunk(l)], play_rates=[PlayRate('game-0', plays, 300.)])
        assert l.optimizer_steps == 0 and l.generated_steps == 8


def test_budget_exhaustion_cannot_buy_an_extra_update(admitted):
    l = learner(admitted, updates=1)
    l.update([chunk(l)])
    with pytest.raises(ContractError, match='budget exhausted'):
        l.update([chunk(l)])
    assert l.generated_steps == 8


def test_three_consecutive_updated_mean_kl_stop(admitted, monkeypatch):
    l = learner(admitted)
    original = rl_math.joint_kl
    def high_kl(*args):
        return original(*args)+.6
    monkeypatch.setattr(rl_math, 'joint_kl', high_kl)
    for i in range(6):
        result = l.update([chunk(l)])
        assert result['high_kl_streak'] == max(0, i-2)
    assert 'three consecutive' in result['halted_reason']
    with pytest.raises(ContractError, match='halted'):
        l.update([chunk(l)])


def test_checkpoint_interrupted_write_preserves_last_complete_file(admitted, tmp_path, monkeypatch):
    l = learner(admitted)
    path = tmp_path/'checkpoint.pt'
    l.save_checkpoint(path)
    original = path.read_bytes()
    def fail_save(value, stream):
        stream.write(b'partial new checkpoint')
        raise OSError('injected write failure')
    monkeypatch.setattr(torch, 'save', fail_save)
    with pytest.raises(OSError, match='injected'):
        l.save_checkpoint(path)
    assert path.read_bytes() == original
    assert list(tmp_path.glob('*.tmp')) == []


def test_upstream_discarded_polls_charge_budget_and_halted_checkpoint_stays_halted(admitted, tmp_path):
    l = learner(admitted)
    l.update([chunk(l)])
    stop = l.halt('producer failed after three additional polls', generated_steps=3)
    assert stop['generated_steps'] == 11 and stop['trained_steps'] == 8
    path = tmp_path/'stopped.pt'
    l.save_checkpoint(path)
    resumed = learner(admitted)
    resumed.load_checkpoint(path)
    assert resumed.generated_steps == 11
    with pytest.raises(ContractError, match='halted'):
        resumed.update([chunk(resumed)])


def test_nonfinite_network_output_stops_and_checkpoints_without_training(admitted, tmp_path):
    l = learner(admitted)
    c = chunk(l)
    hook = l.model.value.register_forward_hook(lambda module, args, output: output*float('nan'))
    with pytest.raises(ContractError, match='nonfinite'):
        l.update([c])
    hook.remove()
    assert l.generated_steps == 8 and l.optimizer_steps == l.trained_steps == 0
    path = tmp_path/'nonfinite.pt'
    l.save_checkpoint(path)
    restored = learner(admitted)
    restored.load_checkpoint(path)
    assert restored.halted_reason is not None
    assert restored.generated_steps == 8


def test_continuing_chunks_check_chronology_and_bootstrap(admitted):
    def split(c):
        def piece(start, end):
            vector_fields = ('action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt')
            return replace(c, features={k: v[start:end] for k, v in c.features.items()}, generated_steps=end-start,
                           **{k: getattr(c, k)[start:end] for k in vector_fields})
        return [replace(piece(0, 4), bootstrap=float(c.old_value[4])), piece(4, 8)]
    l = learner(admitted)
    parts = split(chunk(l))
    assert l.update(parts)['polls'] == 8
    l = learner(admitted)
    parts = split(chunk(l))
    parts[0] = replace(parts[0], bootstrap=parts[0].bootstrap+.1)
    with pytest.raises(ContractError, match='bootstrap disagrees'):
        l.update(parts)
    l = learner(admitted)
    parts = split(chunk(l))
    with pytest.raises(ContractError, match='overlap or omit'):
        l.update([parts[0], parts[0]])


@pytest.mark.parametrize('dtype', [np.int16, np.int32, np.int64])
@pytest.mark.parametrize('as_tensor', [False, True])
def test_all_accepted_action_dtypes_complete_ppo_without_input_mutation(admitted, dtype, as_tensor):
    l, reference = learner(admitted), learner(admitted)
    for _ in range(4):
        c = chunk(l)
        action = c.action.astype(dtype)
        before = action.copy()
        if as_tensor:
            action = torch.from_numpy(action)
        else:
            action.flags.writeable = False
        c = replace(c, action=action)
        validate(c, l)
        actual = l.update([c])
        expected = reference.update([chunk(reference)])
        assert actual == expected
        np.testing.assert_array_equal(action.numpy() if as_tensor else action, before)
        assert all(torch.equal(v, reference.model.state_dict()[k]) for k, v in l.model.state_dict().items())
    assert actual['update'] == 4 and not actual['warmup']


@pytest.mark.parametrize('bad_count', [0, -1, None, True, 4.0])
@pytest.mark.parametrize('reverse', [False, True])
def test_malformed_count_charges_other_known_polls_and_permanently_halts(admitted, tmp_path, bad_count, reverse):
    l = learner(admitted)
    good = chunk(l, n=4)
    bad = replace(chunk(l, n=4, actor_id='bad-worker'), generated_steps=bad_count)
    chunks = [bad, good] if reverse else [good, bad]
    initial = state(l.model)
    with pytest.raises(ContractError, match='invalid generated-step accounting'):
        l.update(chunks)
    assert l.generated_steps == 4
    assert l.update_index == l.optimizer_steps == l.trained_steps == 0
    assert all(torch.equal(v, initial[k]) for k, v in l.model.state_dict().items())
    checkpoint = tmp_path/'malformed-count.pt'
    l.save_checkpoint(checkpoint)
    restored = learner(admitted)
    restored.load_checkpoint(checkpoint)
    assert restored.generated_steps == 4
    with pytest.raises(ContractError, match='halted'):
        restored.update([chunk(restored)])


def boundary_chunk(l, tick=3600, *, terminal=True):
    """Toy public observations: unaffordable polls, then one declined eligible boundary."""
    n = 8
    history = F.History()
    F.observe(rec(tick-5*n, elixir=0.), None, history)
    features = [F.observe(rec(tick-5*(n-1-i), elixir=5. if i == n-1 else 0.), None, history)
                for i in range(n)]
    b = collate(features)
    legal = torch.tensor(tiles_ok_np(b['hand'].numpy(), b['slot_ok'].numpy(), b['alive'].numpy()))
    with torch.no_grad():
        _, _, value = l._forward(b, legal)
    done = np.zeros(n, bool)
    done[-1] = terminal
    rewards = np.zeros(n, np.float64)
    rewards[-1] = 1. if terminal else 0.
    return Chunk(features={k: v.numpy() for k, v in b.items()}, action=np.full(n, F.NOOP, np.int64),
                 old_logp=np.zeros(n, np.float64), old_value=value.double().numpy(), reward=rewards,
                 terminated=done, actor=np.zeros(n, bool), dt=np.full(n, 5, np.int16),
                 bootstrap=0. if terminal else .25, version=l.version, actor_id='boundary-worker',
                 seed=l.config.seed, anchor_sha256=l.anchor_sha256, policy_sha256=l.policy_sha256,
                 generated_steps=n, provenance_sha256=l.provenance_sha256, opponent_id='frozen-live',
                 boundary_declined_steps=1)


@pytest.mark.parametrize('tick', [3600, 6000])
@pytest.mark.parametrize('terminal', [False, True])
def test_declined_boundary_trains_value_counts_poll_and_has_zero_policy_mass(admitted, tick, terminal):
    l = learner(admitted)
    for _ in range(3):
        l.update([chunk(l, forced=True)])
    c = boundary_chunk(l, tick, terminal=terminal)
    before = state(l.model)
    feature_bytes = F.feature_bytes(c.features)
    b, vectors = validate(c, l)
    assert b['slot_ok'][-1].any() and vectors['boundary_declined'].sum() == 1
    _, returns = prepare_targets([c])
    assert returns[-1] == (1. if terminal else .25)
    report = l.update([c])
    assert report['polls'] == report['forced_polls'] == 8
    assert report['boundary_declined_steps'] == 1 and report['actor_polls'] == 0
    assert report['old_logp_max_error'] == report['mean_entropy'] == report['mean_kl'] == 0.
    assert not report['warmup']
    assert F.feature_bytes(c.features) == feature_bytes
    after = l.model.state_dict()
    assert any(not torch.equal(v, after[k]) for k, v in before.items() if k.startswith('value.'))
    assert all(torch.equal(v, after[k]) for k, v in before.items() if k.startswith(('noop.', 'ptr.', 'tile.')))


@pytest.mark.parametrize('change,message', [
    ('count_two', 'must be 0 or 1'), ('boolean_count', 'must be 0 or 1'),
    ('wrong_tick', 'tick 3600 or 6000'), ('missing_metadata', 'eligibility'),
    ('eligible_boundary', 'eligibility'), ('interior_decline', 'eligibility'),
    ('nonzero_logp', 'certain NOOP'), ('played_action', 'certain NOOP'),
])
def test_declined_boundary_exception_is_narrow_and_requires_matching_metadata(admitted, change, message):
    l = learner(admitted)
    c = boundary_chunk(l)
    if change == 'count_two':
        c = replace(c, boundary_declined_steps=2)
    elif change == 'boolean_count':
        c = replace(c, boundary_declined_steps=True)
    elif change == 'wrong_tick':
        c.features['glob'][:, F.G_TICK] -= 5
    elif change == 'missing_metadata':
        c = replace(c, boundary_declined_steps=0)
    elif change == 'eligible_boundary':
        c.actor[-1] = True
    elif change == 'interior_decline':
        c.features['hand'][-2] = c.features['hand'][-1]
        c.features['slot_ok'][-2] = c.features['slot_ok'][-1]
    elif change == 'nonzero_logp':
        c.old_logp[-1] = -.1
    elif change == 'played_action':
        c.action[-1] = 0
    with pytest.raises(ContractError, match=message):
        l.update([c])
    assert l.generated_steps == 8 and l.optimizer_steps == 0
