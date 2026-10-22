"""Local CPU fixtures only. No engine jobs, launch, network, or registered budget."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import featurize as F, rl_coordinator as C, rl_learner as L, stream_actor as A
from bot.pretrain_v1.model import PolicyV1
from bot.pretrain_v1.tests.test_rl_learner import admitted, chunk, learner


class FakeLearner:
    def __init__(self, steps=4, updates=2):
        torch.set_num_threads(1)
        self.config = L.LearnerConfig(seed=L.SEEDS[0], size='S100', microbatch=1,
                                     steps_per_update=steps, updates=updates, batch_size=1, test_only=True)
        self.model = PolicyV1(d=24, layers=1, heads=3, ffn=48, drop=.6).eval()
        self.feature_hash = F.feature_hash()
        self.runtime_manifest = dict(native_sha256=L.NATIVE_SHA256, gamedata_sha256=L.GAMEDATA_SHA256,
                                     actor_source_sha256='c'*64)
        self.provenance_sha256 = L.manifest_sha256(self.runtime_manifest)
        self.anchor_sha256 = 'a'*64
        self.policy_sha256 = A.policy_sha256(self.model)
        self.version = self.generated_steps = self.trained_steps = 0
        self.halted_reason = None
        self.calls, self.maps, self.halts = [], [], []
        self.before_update = self.before_save = None

    def update(self, chunks, *, play_rates):
        self.calls.append(([c.actor_id for c in chunks], list(play_rates)))
        self.generated_steps += sum(c.generated_steps for c in chunks)
        self.maps = [c.action for c in chunks]
        assert all(isinstance(a, np.memmap) and not a.flags.writeable and not a._mmap.closed for a in self.maps)
        if self.before_update:
            self.before_update(chunks)
        assert all(not a._mmap.closed for a in self.maps)
        self.trained_steps += self.config.steps_per_update
        self.version += 1

    def save_checkpoint(self, path):
        if self.before_save:
            self.before_save(path)
        with open(path, 'xb') as out:
            out.write(str(self.version).encode())
            out.flush()
            import os
            os.fsync(out.fileno())

    def halt(self, reason, *, generated_steps=0):
        self.halts.append(generated_steps)
        self.generated_steps += generated_steps
        self.halted_reason = reason


@pytest.fixture
def setup(tmp_path):
    coordinators = []
    def make(quotas=None, steps=4, updates=2, real=None, wait=3):
        l = real or FakeLearner(steps, updates)
        index = len(coordinators)
        caps = C.queue_capacity(l.config.steps_per_update)
        q = A.AtomicChunkQueue(tmp_path/f'q{index}', max_chunks=caps[0], max_bytes=caps[1], runtime_manifest=l.runtime_manifest)
        stops = []
        c = C.Coordinator(l, q, quotas=quotas or {'a': l.config.steps_per_update},
                          checkpoint_dir=tmp_path/f'cp{index}', config=C.CoordinatorConfig(wait, test_only=True), stop_notifier=stops.append)
        coordinators.append(c)
        return c, l, q, stops
    yield make
    for c in coordinators:
        c.abort('test cleanup')
        assert c.join()


def sample(l, key='a', n=2, terminal=True):
    return A.Chunk(**vars(chunk(l, n=n, actor_id=key, terminal_tail=terminal)))


def send(c, ch, *, seq=0, game='g0', game_seq=0, total=None, rate=True, **overrides):
    a = c.actors[ch.actor_id]
    total = a['accepted']+ch.generated_steps if total is None else total
    left = c.quotas[ch.actor_id]-a['update_rows']-ch.generated_steps
    terminal = bool(ch.terminated[-1])
    budget_left = c.budgets[ch.actor_id]-total
    reason = 'budget' if budget_left == 0 else 'quota' if left == 0 else 'terminal' if terminal else 'chunk'
    b = A.Boundary(reason, total, budget_left, left, terminal, reason == 'budget' and not terminal,
                   a['boundary_declined']+ch.boundary_declined_steps)
    p = C.Publication(seq, game, game_seq, int(ch.features['glob'][-1, F.G_TICK])+(1 if terminal else 5), terminal,
                      L.PlayRate(game, 30, 300.) if terminal and rate else None)
    return c.publish(ch.actor_id, ch, replace(b, **overrides), p)


def split(ch, start, end):
    arrays = {k: v[start:end].copy() for k, v in ch.features.items()}
    vectors = {k: getattr(ch, k)[start:end].copy() for k in ('action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt')}
    return replace(ch, features=arrays, **vectors, generated_steps=end-start,
                   bootstrap=ch.bootstrap if end == len(ch.action) else float(ch.old_value[end]))


def test_interleaved_partial_quota_barriers_exact_budget_and_durable_permits(setup):
    c, l, q, _ = setup({'a': 2, 'b': 2})
    with ThreadPoolExecutor(2) as pool:
        for version in range(2):
            x, y = sample(l, 'a'), sample(l, 'b')
            first = pool.submit(send, c, x, seq=version, game=f'a{version}', game_seq=version)
            # First actor cannot trigger update without the other actor's quota.
            with c.condition:
                assert c.condition.wait_for(lambda: c.actors['a']['accepted'] == (version+1)*2, timeout=2)
            if version == 0:
                assert not first.done() and not l.calls
            second = pool.submit(send, c, y, seq=version, game=f'b{version}', game_seq=version)
            u, v = first.result(3), second.result(3)
            if version == 0:
                assert u.version == v.version == 1 and u.quota_steps == v.quota_steps == 2
                assert u.state_dict and v.state_dict and u.policy_sha256 == A.policy_sha256(l.model)
                assert all(a._mmap.closed for a in l.maps)
                ledger = json.loads((c.path/'update-01.json').read_text())
                assert len(ledger['receipts']) == 2 and ledger['model_cfg']['drop'] == .6
                assert ledger['learner_checkpoint']['sha256'] == L.file_sha256(c.path/'update-01.pt')
    result = c.finalize()
    assert len(l.calls) == 2 and l.calls[0][0] == ['a', 'b']
    assert result['generated'] == result['accepted'] == result['trained'] == 8
    assert result['discarded'] == 0 and result['completed_games'] == 4
    assert not any(q.root.glob('chunk-*'))
    assert result['model_cfg_sha256'] == C.digest(l.model.cfg)


def test_same_version_ordinary_ack_and_cross_update_continuity(setup):
    c, l, _, _ = setup(updates=2)
    all_rows = sample(l, n=8)
    first, second, third = split(all_rows, 0, 2), split(all_rows, 2, 4), split(all_rows, 4, 8)
    ack = send(c, first)
    assert ack.version == 0 and ack.state_dict is None and not l.calls
    assert send(c, second, seq=1).version == 1
    send(c, replace(third, version=1), seq=2)
    assert c.finalize()['completed_games'] == 1


@pytest.mark.parametrize('mode', ['duplicate', 'stale', 'badcount', 'discard', 'badsequence', 'missingrate', 'boundary'])
def test_contract_failures_charge_known_attempts_and_halt(setup, mode):
    c, l, _, stops = setup()
    ch = sample(l, n=1, terminal=False)
    send(c, ch)
    other = sample(l, n=1)
    seq, kwargs = 1, {}
    if mode == 'duplicate':
        other, seq, kwargs = ch, 0, dict(total=1)
    elif mode == 'stale':
        other = replace(other, policy_sha256='b'*64)
    elif mode == 'badcount':
        other = replace(other, generated_steps=3)
    elif mode == 'discard':
        kwargs['total'] = 3
    elif mode == 'badsequence':
        seq = 99
    elif mode == 'missingrate':
        kwargs['rate'] = False
    else:
        kwargs['boundary_declined_steps'] = 1
    with pytest.raises((ValueError, AssertionError)):
        send(c, other, seq=seq, **kwargs)
    assert c.stop_event.is_set() and len(stops) == 1 and l.halted_reason
    expected = 4 if mode == 'badcount' else 3 if mode == 'discard' else 2
    assert l.generated_steps == expected
    # Actor cumulative counters exclude the core's additional duplicate charges.
    c.abort('again', generated_counts={'a': c.actors['a']['observed']})
    assert l.generated_steps == expected and len(stops) == 1 and not l.calls


def test_update_failure_no_retry_no_double_charge_and_maps_closed(setup):
    c, l, q, stops = setup()
    def fail(_):
        raise RuntimeError('optimizer failure')
    l.before_update = fail
    with pytest.raises(C.CoordinatorError, match='optimizer failure'):
        send(c, sample(l, n=4))
    assert c.join() and len(l.calls) == 1 and l.generated_steps == 4
    assert sum(l.halts) == 0 and stops and all(a._mmap.closed for a in l.maps)
    assert len(list(q.root.glob('chunk-*'))) == 1
    with pytest.raises(C.CoordinatorError):
        c.finalize()
    assert len(l.calls) == 1


def test_checkpoint_failure_never_releases_next_permit(setup):
    c, l, _, _ = setup()
    l.before_save = lambda _: (_ for _ in ()).throw(OSError('disk failed'))
    with pytest.raises(C.CoordinatorError, match='disk failed'):
        send(c, sample(l, n=4))
    assert c.version == 0 and l.version == 1 and c.stop_event.is_set()


def test_checkpoint_finishes_before_quota_callback_returns(setup):
    c, l, _, _ = setup()
    entered, release = threading.Event(), threading.Event()
    def pause(_):
        entered.set()
        assert release.wait(2)
    l.before_save = pause
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(send, c, sample(l, n=4))
        assert entered.wait(2) and not future.done()
        release.set()
        assert future.result(3).version == 1
        assert (c.path/'update-01.json').exists()


def test_barrier_abort_and_additional_unreported_generated(setup):
    c, l, _, stops = setup({'a': 2, 'b': 2})
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(send, c, sample(l, 'a'))
        with c.condition:
            assert c.condition.wait_for(lambda: c.actors['a']['accepted'] == 2, timeout=2)
        c.abort('lease stopped', generated_counts={'a': 2, 'b': 1})
        with pytest.raises(C.CoordinatorError, match='lease stopped'):
            future.result(3)
    assert l.generated_steps == 3 and len(stops) == 1
    c.abort('late count', generated_counts={'a': 2, 'b': 2})
    assert l.generated_steps == 4


def test_lost_chunk_before_update_is_permanent_and_charged(setup):
    c, l, q, _ = setup({'a': 2, 'b': 2}, updates=1)
    send(c, sample(l, 'a'))  # Final-budget callback is nonblocking.
    receipt = A.Receipt(**c._receipts[0]['receipt'])
    (q.root/receipt.name/'action.npy').unlink()
    send(c, sample(l, 'b'))
    assert c.join()
    with pytest.raises(C.CoordinatorError):
        c.finalize()
    assert not l.calls and l.generated_steps == 4


@pytest.mark.parametrize('replay', [False, True])
def test_cross_update_rejects_game_reset_and_completed_game_replay(setup, replay):
    c, l, _, _ = setup()
    if replay:
        send(c, sample(l, n=4))
        bad = sample(l, n=4)
    else:
        whole = sample(l, n=8)
        send(c, split(whole, 0, 4))
        bad = replace(split(whole, 4, 8), version=1)
    with pytest.raises(C.CoordinatorError, match='replay|continuity'):
        send(c, bad, seq=1, game='g0' if replay else 'replacement', game_seq=1)
    assert l.generated_steps == 8 and len(l.calls) == 1


def test_completed_game_missing_rate_cannot_silently_pass(setup):
    c, l, _, _ = setup()
    with pytest.raises(C.CoordinatorError, match='play-rate'):
        send(c, sample(l, n=4), rate=False)
    assert not l.calls


def test_all_unfinished_final_manifest_is_not_play_rate_go(setup):
    c, l, _, _ = setup(updates=1)
    send(c, sample(l, n=4, terminal=False))
    with pytest.raises(C.CoordinatorError, match='unassessed'):
        c.finalize()
    assert l.trained_steps == 4 and c.stop_event.is_set()


def test_real_learner_readonly_queue_update_and_final_budget(setup, admitted):
    l = learner(admitted, updates=1)
    c, l, q, _ = setup(real=l)
    ch = sample(l, n=8)
    ack = send(c, ch)
    # No next policy/extra action is needed by the unchanged actor at budget.
    assert ack.version == 0 and ack.state_dict is None
    final = c.finalize()
    assert l.version == final['updates'] == 1 and l.generated_steps == l.trained_steps == 8
    assert not list(q.root.glob('chunk-*'))
    state = torch.load(c.path/'update-01.pt', weights_only=False, map_location='cpu')
    assert state['config']['test_only'] and state['trained_steps'] == 8


def test_conservative_queue_and_production_admission(tmp_path):
    l = FakeLearner()
    cap, size = C.queue_capacity(4)
    q = A.AtomicChunkQueue(tmp_path/'q', max_chunks=cap, max_bytes=size, runtime_manifest=l.runtime_manifest)
    kw = dict(quotas={'a': 4}, checkpoint_dir=tmp_path/'cp', stop_notifier=lambda _: None)
    with pytest.raises(C.CoordinatorError, match='test-only'):
        C.Coordinator(l, q, **kw)
    q.max_chunks = 3
    with pytest.raises(C.CoordinatorError, match='queue cap'):
        C.Coordinator(l, q, config=C.CoordinatorConfig(test_only=True), **kw)
    q.max_chunks = cap
    kw['quotas'] = {'a': 3}
    with pytest.raises(C.CoordinatorError, match='sum'):
        C.Coordinator(l, q, config=C.CoordinatorConfig(test_only=True), **kw)


def test_bounded_collection_timeout_stops_all(setup):
    c, l, _, stops = setup(wait=.05)
    assert c.join(timeout=1)
    assert c.stop_event.is_set() and stops and l.halted_reason
    assert l.generated_steps == 0 and not l.calls


def test_abort_during_update_defers_halt_without_unmapping(setup):
    c, l, _, _ = setup()
    entered, release = threading.Event(), threading.Event()
    def pause(chunks):
        entered.set()
        assert release.wait(2)
        assert not chunks[0].action._mmap.closed
    l.before_update = pause
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(send, c, sample(l, n=4))
        assert entered.wait(2)
        c.abort('stop during optimizer')
        assert not l.halts and all(not a._mmap.closed for a in l.maps)
        release.set()
        with pytest.raises(C.CoordinatorError, match='stop during optimizer'):
            future.result(3)
    assert c.join() and sum(l.halts) == 0 and l.generated_steps == 4
    assert all(a._mmap.closed for a in l.maps) and c.version == 0


def test_boundary_declined_terminal_and_unfinished_are_counted_exactly(setup):
    # Synthetic full history up to the registered deadline; no engine is run.
    c, l, _, _ = setup(steps=704, updates=1)
    ch = sample(l, n=704)
    features = {k: v.copy() for k, v in ch.features.items()}
    assert features['glob'][-1, F.G_TICK] == 3605
    # Use 703 real grid rows through 3600, then the terminal game's next first row.
    first = split(ch, 0, 703)
    first = replace(first, features={k: v[:703].copy() for k, v in features.items()},
                    boundary_declined_steps=1, bootstrap=0.)
    first.terminated[-1] = True
    first.reward[-1] = 1.
    first.actor[-1] = False
    first.action[-1] = F.NOOP
    first.old_logp[-1] = 0.
    send(c, first)
    last = sample(l, n=1)
    send(c, last, seq=1, game='g1', game_seq=1)
    result = c.finalize()
    assert result['actors']['a']['boundary_declined'] == 1
    assert result['completed_games'] == 2 and result['trained'] == 704


def test_unchanged_actor_last_budget_callback_and_no_extra_sampling(setup, monkeypatch):
    from bot.pretrain_v1.tests.test_stream_actor import start, view
    c, l, _, _ = setup(steps=2, updates=1)
    def publish(ch, b):
        p = C.Publication(0, 'actual-actor-fixture', 0, 96, True,
                          L.PlayRate('actual-actor-fixture', 30, 300.))
        return c.publish('a', ch, b, p)
    a = A.StreamingPolicyOursPlayer(l.model, publish, actor_id='a', seed=l.config.seed,
                                   anchor_sha256=l.anchor_sha256, provenance_sha256=l.provenance_sha256,
                                   opponent_id='fixture', budget_steps=2, quota_steps=2)
    battle, _ = start(a, monkeypatch)
    a.act(view(90))
    battle.tick = 95
    a.act(view(95))
    battle.tick, battle.game_over, battle.winner = 96, True, 0
    a.close()
    assert a.exhausted and a.generated_steps == a.published_steps == 2 and a.version == 0
    assert c.finalize()['trained'] == 2
    with pytest.raises(A.StreamError):
        a.act(view(100))
    assert a.generated_steps == 2


@pytest.mark.parametrize('operation', ['write', 'acknowledge', 'checkpoint'])
def test_stalled_io_does_not_hold_abort_lock_or_release_permits(setup, monkeypatch, operation):
    c, l, q, _ = setup()
    entered, release = threading.Event(), threading.Event()
    target, name = (l, 'save_checkpoint') if operation == 'checkpoint' else (q, operation)
    original = getattr(target, name)
    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, pause)
    with ThreadPoolExecutor(2) as pool:
        publication = pool.submit(send, c, sample(l, n=4))
        assert entered.wait(2)
        abort = pool.submit(c.abort, 'stop during IO')
        abort.result(.5)
        assert c.stop_event.is_set() and c.version == 0
        release.set()
        with pytest.raises(C.CoordinatorError, match='stop during IO'):
            publication.result(3)
    assert c.join() and l.generated_steps == 4


def test_real_actor_and_learner_continue_same_game_with_new_critic(setup, admitted, monkeypatch):
    import copy
    from bot.pretrain_v1.tests.test_stream_actor import start, view
    l = learner(admitted, microbatch=1, steps_per_update=2, batch_size=2, updates=2)
    c, l, _, _ = setup(real=l)
    sequence = 0
    def publish(ch, b):
        nonlocal sequence
        p = C.Publication(sequence, 'continuing-fixture', 0, battle.tick, b.terminal,
                          L.PlayRate('continuing-fixture', 30, 300.) if b.terminal else None)
        sequence += 1
        return c.publish('a', ch, b, p)
    a = A.StreamingPolicyOursPlayer(copy.deepcopy(l.model), publish, actor_id='a', seed=l.config.seed,
                                   anchor_sha256=l.anchor_sha256, provenance_sha256=l.provenance_sha256,
                                   opponent_id='fixture', budget_steps=4, quota_steps=2)
    battle, _ = start(a, monkeypatch)
    for tick in (90, 95, 100, 105):
        battle.tick = tick
        a.act(view(tick))
        if tick == 100:
            assert a.version == l.version == 1 and a.session.hist.polls == 3
            assert a.policy_sha256 == l.policy_sha256
    battle.tick, battle.game_over, battle.winner = 106, True, 0
    a.close()
    final = c.finalize()
    assert final['generated'] == final['trained'] == a.generated_steps == 4
    assert final['completed_games'] == 1 and final['updates'] == 2 and a.exhausted


@pytest.mark.parametrize('published', [0, 1])
def test_authoritative_shutdown_before_first_pending_callback_never_double_charges(setup, published):
    c, l, _, _ = setup()
    whole = sample(l, n=3)
    if published:
        send(c, split(whole, 0, 1))
    pending = split(whole, published, 3)
    c.abort('shutdown reported pending rows', generated_counts={'a': 3})
    assert l.generated_steps == 3
    with pytest.raises(C.CoordinatorError, match='shutdown reported'):
        send(c, pending, seq=published, total=3)
    assert c.actors['a']['generated'] == l.generated_steps == 3
    c.abort('same report', generated_counts={'a': 3})
    assert l.generated_steps == 3
    # Repeating that callback is now an actual duplicate and consumes attempts.
    with pytest.raises(C.CoordinatorError):
        send(c, pending, seq=published, total=3)
    assert l.generated_steps == 3+len(pending.action)


def test_worst_case_valid_unicode_manifest_rejected_at_admission(tmp_path):
    l = FakeLearner()
    l.runtime_manifest.update({str(i)+'\U0001f600'*250: '\U0001f600'*256 for i in range(125)})
    assert len(l.runtime_manifest) == 128
    assert all(0 < len(k) <= 256 and 0 < len(v) <= 256 for k, v in l.runtime_manifest.items())
    assert len(C.encoded(l.runtime_manifest)) > C.queue_capacity(1)[1]
    l.provenance_sha256 = L.manifest_sha256(l.runtime_manifest)
    caps = C.queue_capacity(4)
    q = A.AtomicChunkQueue(tmp_path/'unicode-q', max_chunks=caps[0], max_bytes=caps[1], runtime_manifest=l.runtime_manifest)
    with pytest.raises(C.CoordinatorError, match='serialized runtime manifest'):
        C.Coordinator(l, q, quotas={'a': 4}, checkpoint_dir=tmp_path/'unicode-cp',
                      config=C.CoordinatorConfig(test_only=True), stop_notifier=lambda _: None)
    assert not list(q.root.glob('chunk-*'))


def test_shutdown_credit_cannot_cover_replayed_rows_under_new_sequence(setup):
    c, l, _, _ = setup()
    pending = sample(l, n=2)
    c.abort('reported all rows', generated_counts={'a': 4})
    for seq in (0, 1):
        with pytest.raises(C.CoordinatorError):
            send(c, pending, seq=seq, total=2)
    assert l.generated_steps == 6


def test_acknowledgement_failure_after_checkpoint_denies_permit(setup, monkeypatch):
    c, l, q, _ = setup()
    def fail(_):
        assert all(a._mmap.closed for a in l.maps)
        assert (c.path/'update-01.json').exists()
        raise OSError('ack failed')
    monkeypatch.setattr(q, 'acknowledge', fail)
    with pytest.raises(C.CoordinatorError, match='ack failed'):
        send(c, sample(l, n=4))
    assert c.join() and c.version == 0 and l.version == 1
    assert l.generated_steps == l.trained_steps == 4 and sum(l.halts) == 0


def test_corruption_during_worker_reload_stops_without_optimizer(setup):
    c, l, q, _ = setup({'a': 2, 'b': 2}, updates=1)
    send(c, sample(l, 'a'))
    path = q.root/c._receipts[0]['receipt']['name']/'action.npy'
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    send(c, sample(l, 'b'))
    assert c.join()
    with pytest.raises(C.CoordinatorError, match='digest mismatch'):
        c.finalize()
    assert not l.calls and l.generated_steps == 4


def test_learner_collapse_halt_never_releases_next_permit(setup):
    c, l, q, _ = setup()
    l.before_update = lambda _: setattr(l, 'halted_reason', 'KL collapse')
    with pytest.raises(C.CoordinatorError, match='KL collapse'):
        send(c, sample(l, n=4))
    assert c.join() and c.version == 0 and l.version == 1
    assert (c.path/'update-01.json').exists() and list(q.root.glob('chunk-*'))
    assert all(a._mmap.closed for a in l.maps)


@pytest.mark.parametrize('late_callback', [False, True])
def test_stop_report_preserves_duplicate_charge_independent_of_delivery_order(setup, late_callback):
    c, l, _, _ = setup()
    whole = sample(l, n=3)
    first = split(whole, 0, 1)
    send(c, first)
    with pytest.raises(C.CoordinatorError):
        send(c, first, seq=0, total=1)
    assert l.generated_steps == 2
    c.abort('final authoritative count', generated_counts={'a': 3})
    assert l.generated_steps == 4
    if late_callback:
        with pytest.raises(C.CoordinatorError):
            send(c, split(whole, 1, 3), seq=1, total=3)
    assert l.generated_steps == c.actors['a']['generated'] == 4
    c.abort('repeat authoritative count', generated_counts={'a': 3})
    assert l.generated_steps == 4


@pytest.mark.parametrize('report', [{'a': -1}, {'unknown': 3}, 'malformed', {'a': True}])
def test_malformed_stop_report_always_stops_and_denies_permits(setup, report):
    c, l, _, stops = setup()
    with pytest.raises(C.CoordinatorError):
        c.abort('lease expired', generated_counts=report)
    assert c.stop_event.is_set() and stops == ['lease expired'] and l.halted_reason
    with pytest.raises(C.CoordinatorError, match='lease expired'):
        send(c, sample(l, n=4))
    assert not l.calls and c.version == 0 and c.join()


def test_no_barrier_eligibility_until_all_publication_maps_close(setup, monkeypatch):
    c, l, q, _ = setup({'a': 2, 'b': 2}, updates=1)
    entered = {k: threading.Event() for k in ('a', 'b')}
    release = {k: threading.Event() for k in ('a', 'b')}
    original = C.close_maps
    first = set()
    lock = threading.Lock()
    def pause(ch):
        with lock:
            should_pause = ch.actor_id not in first
            first.add(ch.actor_id)
        if should_pause:
            entered[ch.actor_id].set()
            assert release[ch.actor_id].wait(2)
        original(ch)
    monkeypatch.setattr(C, 'close_maps', pause)
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(send, c, sample(l, 'a'))
        b = pool.submit(send, c, sample(l, 'b'))
        assert all(e.wait(2) for e in entered.values())
        release['a'].set()
        a.result(2)
        with c.condition:
            assert c.actors['b']['update_rows'] == 0 and not l.calls
            assert len(list(q.root.glob('chunk-*'))) == 2
        release['b'].set()
        b.result(2)
    assert c.finalize()['trained'] == 4
