"""R46 CPU contracts: independent failures, high descriptors and lock contention."""
import fcntl
import json
from multiprocessing.connection import Connection
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import threading
import time

import pytest

from bot.pretrain_v1 import rl_coordinator as C, rl_driver as D, rl_learner as L
from bot.pretrain_v1.tests.test_rl_driver_r43 import cpu_driver
from bot.pretrain_v1.tests.test_rl_coordinator import setup, sample, send


@pytest.mark.parametrize('ordering', ['at-cutoff', 'after-parent-abort'])
@pytest.mark.parametrize('failure', ['optimizer', 'parity', 'checkpoint', 'queue', 'stop-wording'])
def test_execution_error_at_cutoff_never_completes(cpu_driver, monkeypatch, ordering, failure):
    original, learner_type = C.Coordinator, L.Learner
    objects, exceptions = [], []
    parent_aborted = threading.Event()
    class FailingLearner(learner_type):
        def update(self, chunks, **kwargs):
            deadline = time.monotonic()+6
            while not any((out/'QUALIFICATION-EXPOSURE-COMPLETE').exists() for out in cpu_driver.outputs):
                assert time.monotonic() < deadline
                time.sleep(.005)
            if ordering == 'after-parent-abort':
                assert parent_aborted.wait(3)
            message = 'driver stop before learner microbatch' if failure == 'stop-wording' else f'R46_{failure}_FAILURE'
            error = RuntimeError(message)
            exceptions.append(error)
            raise error
    class Barrier(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            objects.append(self)
            with self.condition:
                self.steps = 0
                for key, actor in self.actors.items():
                    actor['update_rows'] = self.quotas[key]
                self.condition.notify_all()
        def abort(self, *args, **kwargs):
            super().abort(*args, **kwargs)
            parent_aborted.set()
    monkeypatch.setattr(L, 'Learner', FailingLearner)
    monkeypatch.setattr(C, 'Coordinator', Barrier)
    with pytest.raises(RuntimeError, match='driver stop before learner|R46_') as caught:
        cpu_driver.execute('cooperative')
    c, out = objects[0], cpu_driver.outputs[-1]
    assert caught.value is exceptions[0] is c.execution_failure
    stopped = json.loads((out/'stopped.json').read_text())
    assert str(exceptions[0]) in stopped['error']
    assert any(row['actor_id'] == 'coordinator' and str(exceptions[0]) in row['error'] for row in stopped['failures'])
    assert str(exceptions[0]) in (out/'coordinator-error.txt').read_text()
    assert not (out/'qualification.json').exists()
    assert not (out/'checkpoints/update-01.pt').exists()
    assert stopped['generated_counts'] == {'actor-00': 0, 'actor-01': 0}
    if ordering == 'after-parent-abort':
        assert c.reason == 'separate six-hour qualification exposure complete'


def test_typed_bounded_learner_cancellation_completes(cpu_driver, monkeypatch):
    original, learner_type = C.Coordinator, L.Learner
    objects = []
    class CancellingLearner(learner_type):
        def update(self, chunks, **kwargs):
            deadline = time.monotonic()+6
            while not objects or not objects[0].stop_event.is_set():
                assert time.monotonic() < deadline
                time.sleep(.005)
            # Exercise the driver's actual bounded _batch stop callback.
            self._batch([], [])
    class Barrier(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            objects.append(self)
            with self.condition:
                self.steps = 0
                for key, actor in self.actors.items():
                    actor['update_rows'] = self.quotas[key]
                self.condition.notify_all()
    monkeypatch.setattr(L, 'Learner', CancellingLearner)
    monkeypatch.setattr(C, 'Coordinator', Barrier)
    out, result = cpu_driver.execute('cooperative')
    assert result['status'] == 'completed-exposure-pending-review'
    assert objects[0].execution_failure is None
    assert isinstance(objects[0].learner_cancellation, C.LearnerCancelled)
    assert not (out/'stopped.json').exists()


@pytest.fixture(params=[False, True], ids=['low-fd', 'high-fd'])
def sockets(request):
    before = len(list(Path('/proc/self/fd').iterdir()))
    left, right = socket.socketpair()
    left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    right.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    if request.param:
        # Same socket type as multiprocessing.Pipe, allocated above queue-map fds.
        new_left = fcntl.fcntl(left.fileno(), fcntl.F_DUPFD, 1232)
        new_right = fcntl.fcntl(right.fileno(), fcntl.F_DUPFD, 1232)
        left.close()
        right.close()
        left, right = socket.socket(fileno=new_left), socket.socket(fileno=new_right)
        assert min(left.fileno(), right.fileno()) >= 1232
    connections = [Connection(left.detach()), Connection(right.detach())]
    try:
        yield connections
    finally:
        for connection in connections:
            connection.close()
    assert len(list(Path('/proc/self/fd').iterdir())) == before


@pytest.mark.parametrize('reverse', [False, True])
def test_protocol_full_frame_and_ack(sockets, reverse):
    a, b = sockets[::(-1 if reverse else 1)]
    D.send(a, {'kind': 'ready'})
    assert D.receive(b, .2) == {'kind': 'ready'}
    b.send_bytes(D.S.encoded({'kind': 'permit'}))
    assert D.receive(a, .2) == {'kind': 'permit'}


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('prefix', [b'', b'\0', b'\0\0\0', struct.pack('!i', 2), struct.pack('!i', 2)+b'{'])
@pytest.mark.parametrize('cancelled', [False, True], ids=['deadline', 'cancel'])
def test_partial_header_body_ack_bounded(sockets, reverse, prefix, cancelled):
    a, b = sockets[::(-1 if reverse else 1)]
    os.write(b.fileno(), prefix)
    stop = threading.Event()
    observed = threading.Event()
    results = []
    def cancel():
        observed.set()
        if stop.is_set():
            raise D.ControlCancelled('R46 stop')
    def transfer():
        try:
            results.append(D.receive(a, 30 if cancelled else .08, cancel=cancel))
        except BaseException as exc:
            results.append(exc)
    thread = threading.Thread(target=transfer)
    thread.start()
    try:
        assert observed.wait(1)
        if cancelled:
            stop.set()
        thread.join(.7)
        assert not thread.is_alive()
        assert isinstance(results[0], D.ControlCancelled if cancelled else ValueError)
        if not cancelled:
            assert 'timeout' in str(results[0])
    finally:
        stop.set()
        thread.join(1)
        assert not thread.is_alive()


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('cancelled', [False, True], ids=['deadline', 'cancel'])
def test_stalled_send_bounded(sockets, reverse, cancelled):
    a, _ = sockets[::(-1 if reverse else 1)]
    stop, observed = threading.Event(), threading.Event()
    results = []
    def cancel():
        observed.set()
        if stop.is_set():
            raise D.ControlCancelled('R46 stop')
    def transfer():
        try:
            D.send(a, {'payload': 'x'*900000}, timeout=30 if cancelled else .08, cancel=cancel)
        except BaseException as exc:
            results.append(exc)
    thread = threading.Thread(target=transfer)
    thread.start()
    try:
        assert observed.wait(1)
        if cancelled:
            stop.set()
        thread.join(.7)
        assert not thread.is_alive()
        assert isinstance(results[0], D.ControlCancelled if cancelled else ValueError)
    finally:
        stop.set()
        thread.join(1)
        assert not thread.is_alive()


@pytest.mark.parametrize('repeat', range(10))
def test_monitor_escalates_before_condition_can_progress(cpu_driver, monkeypatch, repeat):
    original = C.Coordinator
    locked, release, monitor_kill = threading.Event(), threading.Event(), threading.Event()
    holders, evidence = [], []
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    unrelated_identity = D.process_identity(unrelated.pid)
    def hold(c):
        with c.condition:
            locked.set()
            assert release.wait(6), 'monitor failed to escalate independently of coordinator lock'
    class Held(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            thread = threading.Thread(target=hold, args=(self,))
            holders.append(thread)
            thread.start()
            assert locked.wait(1)
    original_signal = D.WorkerSession.signal
    def signal_owned(session, sig):
        original_signal(session, sig)
        if threading.current_thread().name == 'registered-resource-monitor' and sig == signal.SIGKILL:
            assert locked.is_set() and not release.is_set()
            evidence.append(dict(pid=session.leader['pid'], start=session.leader['start'], signal=sig))
            monitor_kill.set()
            release.set()
    monkeypatch.setattr(C, 'Coordinator', Held)
    monkeypatch.setattr(D.WorkerSession, 'signal', signal_owned)
    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match='actor failures'):
            cpu_driver.execute('hung-engine')
        assert monitor_kill.is_set() and evidence
        assert time.monotonic()-started < 7
        assert unrelated.poll() is None and D.process_identity(unrelated.pid)['start'] == unrelated_identity['start']
        for row in evidence:
            with pytest.raises(FileNotFoundError):
                D.process_identity(row['pid'])
        out = cpu_driver.outputs[-1]
        assert not (out/'qualification.json').exists() and (out/'stopped.json').exists()
        assert any(row['stopping'] for row in cpu_driver.observations)
    finally:
        release.set()
        for thread in holders:
            thread.join(2)
        unrelated.kill()
        unrelated.wait(timeout=2)


@pytest.mark.parametrize('reverse', [False, True])
def test_large_complete_frame_requires_partial_io(sockets, reverse):
    a, b = sockets[::(-1 if reverse else 1)]
    payload = {'payload': 'x'*200000}
    results = []
    def write():
        try:
            D.send(a, payload, timeout=2)
        except BaseException as exc:
            results.append(exc)
    thread = threading.Thread(target=write)
    thread.start()
    try:
        assert D.receive(b, 2) == payload
    finally:
        thread.join(3)
    assert not thread.is_alive() and not results


@pytest.mark.parametrize('reverse', [False, True])
def test_receive_header_and_body_share_one_deadline(sockets, reverse):
    a, b = sockets[::(-1 if reverse else 1)]
    # Stage the body only once the receiver has consumed the complete header.
    # Its body poll must still use the original operation deadline.
    original = D._transfer
    body_entered = threading.Event()
    body_deadlines = []
    def transfer(connection, data, count, deadline, cancel):
        body_deadlines.append(deadline)
        if len(body_deadlines) == 2:
            body_entered.set()
        return original(connection, data, count, deadline, cancel)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(D, '_transfer', transfer)
        os.write(b.fileno(), struct.pack('!i', 2))
        with pytest.raises(ValueError, match='timeout'):
            D.receive(a, .08)
    assert body_entered.is_set() and len(body_deadlines) == 2
    assert body_deadlines[0] == body_deadlines[1]


def test_corrupt_queue_after_parent_abort_retains_original_failure(cpu_driver, monkeypatch):
    from dataclasses import asdict
    original = C.Coordinator
    objects = []
    parent_aborted = threading.Event()
    errors = []
    class Barrier(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            objects.append(self)
            receipt = self.queue.write(sample(self.learner, key='actor-00', n=4))
            load = self.queue.load
            def corrupt_after_abort(*a, **kw):
                assert parent_aborted.wait(6)
                path = self.queue.root/receipt.name/'action.npy'
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                try:
                    return load(*a, **kw)
                except BaseException as exc:
                    errors.append(exc)
                    raise
            self.queue.load = corrupt_after_abort
            with self.condition:
                self.steps = 4
                self._receipts = [dict(receipt=asdict(receipt))]
                for key, actor in self.actors.items():
                    actor['update_rows'] = self.quotas[key]
                self.condition.notify_all()
        def abort(self, *a, **kw):
            super().abort(*a, **kw)
            parent_aborted.set()
    monkeypatch.setattr(C, 'Coordinator', Barrier)
    with pytest.raises(ValueError, match='digest mismatch') as caught:
        cpu_driver.execute('cooperative')
    c, out = objects[0], cpu_driver.outputs[-1]
    assert c.execution_failure is errors[0] is caught.value
    assert c.reason == 'separate six-hour qualification exposure complete'
    assert not c.learner.calls and c.learner.trained_steps == 0
    assert not (out/'qualification.json').exists()
    assert 'digest mismatch' in (out/'coordinator-error.txt').read_text()
    stopped = json.loads((out/'stopped.json').read_text())
    assert 'digest mismatch' in stopped['error']
    assert any(row['actor_id'] == 'coordinator' for row in stopped['failures'])
    assert not (out/'checkpoints/update-01.pt').exists()


def test_unsolicited_typed_cancellation_is_an_execution_failure(setup):
    c, learner, _, _ = setup()
    error = C.LearnerCancelled('no stop was requested')
    def fail(_):
        raise error
    learner.before_update = fail
    with pytest.raises(C.CoordinatorError):
        send(c, sample(learner, n=4))
    assert c.join() and c.execution_failure is error
    with pytest.raises(C.LearnerCancelled) as caught:
        c.raise_execution_failure()
    assert caught.value is error


def test_checkpoint_execution_error_after_abort_is_retained(cpu_driver, monkeypatch):
    original, learner_type = C.Coordinator, L.Learner
    parent_aborted = threading.Event()
    objects, errors = [], []
    class CheckpointLearner(learner_type):
        def update(self, chunks, **kwargs):
            # Control-only barrier, as in the original R46 reproduction.
            self.version = 1
        def save_checkpoint(self, path):
            if self.version == 0:
                return super().save_checkpoint(path)
            assert parent_aborted.wait(6)
            error = RuntimeError('R46_CHECKPOINT_AFTER_ABORT')
            errors.append(error)
            raise error
    class Barrier(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            objects.append(self)
            with self.condition:
                self.steps = 0
                for key, actor in self.actors.items():
                    actor['update_rows'] = self.quotas[key]
                self.condition.notify_all()
        def abort(self, *args, **kwargs):
            super().abort(*args, **kwargs)
            parent_aborted.set()
    monkeypatch.setattr(L, 'Learner', CheckpointLearner)
    monkeypatch.setattr(C, 'Coordinator', Barrier)
    with pytest.raises(RuntimeError, match='R46_CHECKPOINT_AFTER_ABORT') as caught:
        cpu_driver.execute('cooperative')
    c, out = objects[0], cpu_driver.outputs[-1]
    assert c.execution_failure is errors[0] is caught.value
    assert c.reason == 'separate six-hour qualification exposure complete'
    assert not (out/'qualification.json').exists()
    assert 'R46_CHECKPOINT_AFTER_ABORT' in (out/'stopped.json').read_text()
    assert not (out/'checkpoints/update-01.pt').exists()


def test_learner_halt_returning_after_abort_is_not_clean_cancellation(cpu_driver, monkeypatch):
    original, learner_type = C.Coordinator, L.Learner
    parent_aborted = threading.Event()
    objects = []
    class HaltedLearner(learner_type):
        def update(self, chunks, **kwargs):
            assert parent_aborted.wait(6)
            self.halted_reason = 'R46_INDEPENDENT_LEARNER_HALT'
    class Barrier(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            objects.append(self)
            with self.condition:
                self.steps = 0
                for key, actor in self.actors.items():
                    actor['update_rows'] = self.quotas[key]
                self.condition.notify_all()
        def abort(self, *args, **kwargs):
            super().abort(*args, **kwargs)
            parent_aborted.set()
    monkeypatch.setattr(L, 'Learner', HaltedLearner)
    monkeypatch.setattr(C, 'Coordinator', Barrier)
    with pytest.raises(C.CoordinatorError, match='R46_INDEPENDENT_LEARNER_HALT'):
        cpu_driver.execute('cooperative')
    out = cpu_driver.outputs[-1]
    assert not (out/'qualification.json').exists()
    assert objects[0].execution_failure is not None
    assert not (out/'checkpoints/update-01.pt').exists()
    assert 'R46_INDEPENDENT_LEARNER_HALT' in (out/'stopped.json').read_text()
