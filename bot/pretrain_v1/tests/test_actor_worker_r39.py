"""Deterministic CPU transfer races using real actors and exited fixture workers."""
import copy
import hashlib
import json
import multiprocessing as mp
import stat
import threading
from types import SimpleNamespace as NS

import pytest

from bot.pretrain_v1 import actor_worker as W
from bot.pretrain_v1.tests import test_actor_worker as T


def _declined_checkpoint_child(connection):
    with pytest.MonkeyPatch.context() as patch:
        a = T.actor()
        a.budget_steps = a.remaining_quota = 2000
        a.chunk_rows = 128
        b, own = T.battle(patch)
        b.game_over, b.winner = False, None
        b.entities[4].hitpoints = 0
        own.elixir = 0.
        a.bind_ours(b)
        a.start(T.MatchContext(0, 101, tuple(T.DECK)))
        for tick in range(90, 3600, 5):
            b.tick = tick
            a.act(NS(tick=tick, seat=0, can_act=True))
        own.elixir = 7.
        b.tick = 3600
        a.act(NS(tick=3600, seat=0, can_act=True))
        b.tick, b.game_over, b.winner = 3601, True, 0
        a.close()
        cp = W.ActorCheckpoint.capture(a, T.cursor(a))
        assert cp.record['counters']['boundary_declined_steps'] == 1
        connection.send((cp.record, cp.sha256, cp.record['driver_state'], None))
    connection.close()


@pytest.fixture(scope='module', params=['standard', 'declined'])
def dead_checkpoint(request):
    ctx = mp.get_context('spawn')
    receive, send = ctx.Pipe(duplex=False)
    target = T._checkpoint_child if request.param == 'standard' else _declined_checkpoint_child
    old = ctx.Process(target=target, args=(send,))
    old.start()
    send.close()
    try:
        assert receive.poll(30)
        record, digest, driver, expected = receive.recv()
        old.join(30)
        assert old.exitcode == 0
        assert not W.S.alive(record['source_process']['pid'], record['source_process']['start'])
        return record, digest, driver, expected
    finally:
        if old.is_alive():
            old.kill()
            old.join(10)
        receive.close()


@pytest.mark.parametrize('pause_at', ['liveness', 'construction'])
def test_restore_uses_verified_private_record_and_independent_cursor(
        dead_checkpoint, tmp_path, monkeypatch, pause_at):
    approved, digest, approved_driver, _ = dead_checkpoint
    record, driver = copy.deepcopy(approved), copy.deepcopy(approved_driver)
    assert driver is not record['driver_state']
    reached, changed = threading.Event(), threading.Event()
    errors = []
    original = W.S.alive if pause_at == 'liveness' else W._replacement

    def paused(*args, **kwargs):
        reached.set()
        assert changed.wait(10)
        return original(*args, **kwargs)

    def mutate():
        try:
            assert reached.wait(10)
            record['budget_steps'] = 1000
            record['remaining_quota'] = 30
            record['version'] += 1
            record['counters']['generated_steps'] += 1
            record['counters']['published_steps'] += 1
            record['counts']['injected'] = 1
            record['anchor_sha256'] = 'd'*64
            record['driver_state']['publication_sequence'] += 1
            record['driver_state']['schedule_sha256'] = 'e'*64
            driver.update(record['driver_state'])
        except BaseException as ex:
            errors.append(ex)
        finally:
            changed.set()

    monkeypatch.setattr(W.S if pause_at == 'liveness' else W,
                        'alive' if pause_at == 'liveness' else '_replacement', paused)
    thread = threading.Thread(target=mutate)
    thread.start()
    try:
        successor = W.ActorCheckpoint.restore_record(record, T.model(), T.callback,
            expected_sha256=digest, driver_state=driver, claim_directory=tmp_path)
    finally:
        thread.join(15)
    assert not thread.is_alive() and not errors
    assert hashlib.sha256(W.encoded(record)).hexdigest() != digest
    assert successor.budget_steps == approved['budget_steps']
    assert successor.remaining_quota == approved['remaining_quota']
    assert successor.version == approved['version']
    assert successor.anchor_sha256 == approved['anchor_sha256']
    assert successor.policy_sha256 == approved['policy_sha256']
    assert successor.counts == approved['counts']
    assert {k: getattr(successor, k) for k in W._COUNTERS} == approved['counters']
    assert W._driver(approved_driver, successor) == approved_driver
    claim, = tmp_path.iterdir()
    assert json.loads(claim.read_bytes())['checkpoint_sha256'] == digest


def test_live_restore_denied_during_real_actor_entry_race(monkeypatch):
    source = T.actor()
    T.game(source, monkeypatch)
    checkpoint = W.ActorCheckpoint.capture(source, T.cursor(source))
    captured = source.generated_steps
    reached, advanced = threading.Event(), threading.Event()
    errors, successors = [], []
    original = W._replacement

    def paused(*args, **kwargs):
        # Original R39 interleaving: after source equality, before retirement.
        reached.set()
        assert advanced.wait(10)
        return original(*args, **kwargs)

    def play():
        try:
            assert reached.wait(10)
            with pytest.MonkeyPatch.context() as patch:
                T.game(source, patch, seed=102)
        except BaseException as ex:
            errors.append(ex)
        finally:
            advanced.set()

    monkeypatch.setattr(W, '_replacement', paused)
    thread = threading.Thread(target=play)
    thread.start()
    try:
        try:
            successors.append(checkpoint.restore(T.model(), T.callback, driver_state=T.cursor(source)))
        except W.WorkerError as ex:
            assert 'in-process' in str(ex)
        finally:
            # A denied API does not enter _replacement; let the source continue.
            reached.set()
    finally:
        thread.join(15)
    assert not thread.is_alive() and not errors
    assert not successors, 'live restore returned stale acknowledged counters'
    assert source.generated_steps == source.published_steps == captured+4
    assert source.completed_games == 2
    assert not source.failed and not getattr(source, '_lifecycle_retired', False)


@pytest.mark.parametrize('bad_model', ['policy', 'config'])
def test_invalid_model_does_not_consume_process_claim(dead_checkpoint, tmp_path, bad_model):
    record, digest, driver, _ = dead_checkpoint
    m = T.model()
    if bad_model == 'policy':
        import torch
        with torch.no_grad():
            next(m.parameters()).add_(1)
    else:
        m.cfg = dict(m.cfg, d=999)
    with pytest.raises((W.WorkerError, T.A.StreamError)):
        W.ActorCheckpoint.restore_record(record, m, T.callback, expected_sha256=digest,
            driver_state=driver, claim_directory=tmp_path)
    assert not list(tmp_path.iterdir())
    successor = W.ActorCheckpoint.restore_record(record, T.model(), T.callback,
        expected_sha256=digest, driver_state=driver, claim_directory=tmp_path)
    assert successor.generated_steps == record['counters']['generated_steps']
    assert successor.budget_steps == record['budget_steps']


@pytest.mark.parametrize('fail_at', [1, 2])
def test_failed_claim_fsync_returns_no_successor_and_denies_retry(
        dead_checkpoint, tmp_path, monkeypatch, fail_at):
    record, digest, driver, _ = dead_checkpoint
    original = W.os.fsync
    synced_directories = []

    def fail(fd):
        synced_directories.append(stat.S_ISDIR(W.os.fstat(fd).st_mode))
        if len(synced_directories) == fail_at:
            raise OSError('injected claim fsync failure')
        original(fd)

    kw = dict(expected_sha256=digest, driver_state=driver, claim_directory=tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(W.os, 'fsync', fail)
        with pytest.raises(OSError, match='injected'):
            W.ActorCheckpoint.restore_record(record, T.model(), T.callback, **kw)
    assert synced_directories == [False, True][:fail_at]
    claim, = tmp_path.iterdir()
    assert json.loads(claim.read_bytes())['checkpoint_sha256'] == digest
    with pytest.raises(W.WorkerError, match='already claimed'):
        W.ActorCheckpoint.restore_record(record, T.model(), T.callback, **kw)


def test_capture_waits_for_actual_terminal_publication_ack(monkeypatch):
    source = T.actor()
    original = source.publish
    reached, acknowledged = threading.Event(), threading.Event()
    errors = []

    def blocked(c, boundary):
        if boundary.terminal:
            reached.set()
            assert acknowledged.wait(10)
        return original(c, boundary)

    def play():
        try:
            with pytest.MonkeyPatch.context() as patch:
                T.game(source, patch)
        except BaseException as ex:
            errors.append(ex)

    source.publish = blocked
    thread = threading.Thread(target=play)
    thread.start()
    try:
        assert reached.wait(10)
        assert source.completed_games == 1
        assert source.generated_steps == 4 and source.published_steps == 2
        with pytest.raises(W.WorkerError, match='closed game'):
            W.ActorCheckpoint.capture(source, T.cursor(source))
    finally:
        acknowledged.set()
        thread.join(15)
    assert not thread.is_alive() and not errors
    cp = W.ActorCheckpoint.capture(source, T.cursor(source))
    assert cp.record['counters']['generated_steps'] == cp.record['counters']['published_steps'] == 4
