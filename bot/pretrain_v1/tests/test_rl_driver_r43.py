"""R43 regressions: real control sockets and disposable CPU actor processes."""
import json
from multiprocessing.connection import Connection
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
from types import SimpleNamespace as NS

import pytest
import torch

from bot.pretrain_v1 import rl_driver as D, rl_coordinator as C, rl_learner as L, stream_actor as A
from bot.pretrain_v1.tests import test_actor_worker as T
from bot.pretrain_v1.tests.test_rl_coordinator import FakeLearner
from bot.pretrain_v1.tests.test_rl_driver import populations


@pytest.mark.parametrize('prefix', [b'', b'\0', b'\0\0\0', struct.pack('!i', 2), struct.pack('!i', 2)+b'{'])
def test_complete_receive_deadline_includes_partial_header_body_and_ack(prefix):
    left, right = socket.socketpair()
    connection = Connection(left.detach())
    results = []
    def read():
        try:
            results.append(D.receive(connection, .07))
        except BaseException as ex:
            results.append(ex)
    thread = threading.Thread(target=read)
    try:
        right.sendall(prefix)
        thread.start()
        thread.join(.35)
        missed = thread.is_alive()
    finally:
        right.close()  # release the old implementation too; never leak a test thread
        thread.join(2)
        connection.close()
    assert not thread.is_alive()
    assert not missed, 'partial control frame escaped its complete-operation deadline'
    assert isinstance(results[0], ValueError) and 'timeout' in str(results[0])


def test_actual_stalled_sender_has_deadline_and_no_io_thread_leak():
    left, right = socket.socketpair()
    left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    connection = Connection(left.detach())
    results = []
    def write():
        try:
            D.send(connection, {'payload': 'x'*900000}, timeout=.07)
        except BaseException as ex:
            results.append(ex)
    thread = threading.Thread(target=write)
    try:
        thread.start()
        thread.join(.35)
        missed = thread.is_alive()
    finally:
        right.close()
        thread.join(2)
        connection.close()
    assert not thread.is_alive() and not missed
    assert isinstance(results[0], ValueError) and 'timeout' in str(results[0])


@pytest.mark.parametrize('direction', ['send', 'receive'])
def test_complete_control_operation_cancels_without_closing_from_another_thread(direction):
    left, right = socket.socketpair()
    left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    connection = Connection(left.detach())
    stop = threading.Event()
    results = []
    def cancel():
        if stop.is_set():
            raise D.ControlCancelled('fixture stop')
    def transfer():
        try:
            if direction == 'send':
                D.send(connection, {'payload': 'x'*900000}, timeout=86400, cancel=cancel)
            else:
                D.receive(connection, 86400, cancel=cancel)
        except BaseException as ex:
            results.append(ex)
    if direction == 'receive':
        right.sendall(struct.pack('!i', 200)+b'{')
    thread = threading.Thread(target=transfer)
    try:
        thread.start()
        time.sleep(.03)
        stop.set()
        thread.join(.35)
        missed = thread.is_alive()
    finally:
        right.close()
        thread.join(2)
        connection.close()
    assert not thread.is_alive() and not missed
    assert isinstance(results[0], D.ControlCancelled)


@pytest.fixture
def cpu_driver(monkeypatch, tmp_path):
    """Real coordinator, queues, counters, supervisors and sessions; CPU learner only."""
    threads_before = {t.ident for t in threading.enumerate()}
    manifest = dict(native_sha256=L.NATIVE_SHA256, gamedata_sha256=L.GAMEDATA_SHA256, actor_source_sha256='c'*64)
    class CPULearner(FakeLearner):
        def __init__(self, *args, config, **kwargs):
            super().__init__(steps=config.steps_per_update, updates=config.updates)
            self.config = config
            self.model = T.model()
            self.policy_sha256 = A.policy_sha256(self.model)
            self.runtime_manifest = dict(manifest, scope='separate-six-hour-qualification')
            self.provenance_sha256 = A.manifest_sha256(self.runtime_manifest)
    monkeypatch.setattr(L, 'Learner', CPULearner)
    monkeypatch.setattr(D, 'guard', lambda: dict(cpu_fixture=True))
    monkeypatch.setattr(D, 'audit', lambda *a, **k: dict(status='GO', failures=[]))
    monkeypatch.setattr(D, 'make_manifest', lambda _: manifest)
    monkeypatch.setattr(D, 'ensure_fd_capacity', lambda _: dict(cpu_fixture=True))
    monkeypatch.setattr(D.shutil, 'disk_usage', lambda _: NS(free=10**15))
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'mem_get_info', lambda: (10**12, 10**12))
    monkeypatch.setattr(torch.cuda, 'memory_reserved', lambda _: 0)
    from bot.pretrain_v1 import lease_adapter
    observations = []
    def lease_poll():
        observations.append(dict(monotonic=time.monotonic(), stopping=any(
            (path/'QUALIFICATION-EXPOSURE-COMPLETE').exists() for path in outputs)))
        return None
    monkeypatch.setattr(lease_adapter.LeaseStopAdapter, 'from_environment', lambda: NS(poll=lease_poll))
    monkeypatch.setattr(D, 'ENTRY', Path(__file__).with_name('r43_worker_fixture.py'))
    monkeypatch.setattr(D, 'WORKER_EXIT_SECONDS', .25)
    monkeypatch.setattr(D, 'WORKER_TERM_SECONDS', .15)
    monkeypatch.setattr(D, 'WORKER_KILL_SECONDS', 2.)
    monkeypatch.setattr(D, 'SHUTDOWN_SECONDS', 8.)
    monkeypatch.setattr(D, 'STARTUP_SECONDS', 5.)
    monkeypatch.setattr(D, 'QUALIFICATION_SECONDS', .5)
    real_run = subprocess.run
    def run(command, *a, **k):
        if command[0] == 'nvidia-smi':
            return NS(stdout='8192\n')
        return real_run(command, *a, **k)
    monkeypatch.setattr(D.subprocess, 'run', run)
    def reference(name, value):
        path = tmp_path/name
        path.write_bytes(D.S.encoded(value))
        return dict(path=str(path), sha256=D.S.file_sha(path))
    config = dict(qualification_only=True, host=os.uname().nodename.split('.')[0], workers=2,
        wait_seconds=86400, seed=D.S.SEEDS[0], size='S100', precision='float32', chunk_rows=128,
        populations=reference('populations.json', populations()), anchor=reference('anchor.json', {}),
        model_cfg=reference('model.json', T.model().cfg), fixture_mode='cooperative')
    outputs = []
    def execute(mode, workers=2):
        config.update(fixture_mode=mode, workers=workers)
        out = tmp_path/f'run-{len(outputs)}'
        outputs.append(out)
        return out, D._run(config, tmp_path/'ignored.json', out, gpu_admission={}, qualification=True)
    yield NS(execute=execute, config=config, observations=observations, outputs=outputs, manifest=manifest)
    leaked = [t.name for t in threading.enumerate() if t.ident not in threads_before]
    assert not leaked, f'driver left threads alive: {leaked}'
    assert not torch.cuda.is_initialized()


def test_actual_driver_first_terminal_recycle_retains_canonical_single_use_claim(cpu_driver, monkeypatch):
    monkeypatch.setattr(D, 'QUALIFICATION_SECONDS', 6.)
    monkeypatch.setattr(D, 'WORKER_EXIT_SECONDS', 2.)
    out, result = cpu_driver.execute('recycle', workers=1)
    assert result['status'] == 'completed-exposure-pending-review'
    assert result['generated'] == result['accepted'] == 4 and result['trained_steps'] == 0
    assert result['checkpoint_or_data_promotion_allowed'] is False
    assert len(list((out/'claims').iterdir())) == 1
    assert len(list(out.glob('actor-00-recycle-*.json'))) == 1
    successor = json.loads((out/'successor-verified').read_text())
    assert successor == dict(generated=4, completed=1, unfinished=0, version=0)
    published = json.loads((out/'opponent-publications.jsonl').read_text())
    assert published['opponent']['policy_sha256'] == A.policy_sha256(T.model())
    assert published['publication']['terminal'] is True
    assert not (out/'stopped.json').exists()


@pytest.mark.parametrize('mode', ['hung-engine', 'partial-receiver'])
def test_cutoff_cancels_receiver_reaps_hung_worker_and_fails_qualification(cpu_driver, mode):
    started = time.monotonic()
    with pytest.raises(ValueError, match='actor failures'):
        cpu_driver.execute(mode)
    assert time.monotonic()-started < 6.
    out = cpu_driver.outputs[-1]
    assert (out/'QUALIFICATION-EXPOSURE-COMPLETE').exists()
    assert not (out/'qualification.json').exists()
    stopped = json.loads((out/'stopped.json').read_text())
    assert any('forced' in row['error'] for row in stopped['failures'])
    assert stopped['generated_counts'] == {'actor-00': 0, 'actor-01': 0}
    assert any(row['stopping'] for row in cpu_driver.observations), 'lease monitor stopped at cutoff'


def test_startup_spool_failure_aborts_other_live_worker_without_collection_timeout(cpu_driver, monkeypatch):
    queue_type = A.AtomicChunkQueue
    class RefusingSpool(queue_type):
        def __init__(self, root, **kwargs):
            if Path(root).name == 'actor-01':
                # An actual filesystem collision, after the other child launches.
                deadline = time.monotonic()+2
                while not (Path(root).parents[1]/'fixture-ready-actor-00').exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                Path(root).parent.mkdir(exist_ok=True)
                Path(root).write_text('occupied by fixture')
            super().__init__(root, **kwargs)
    monkeypatch.setattr(A, 'AtomicChunkQueue', RefusingSpool)
    started = time.monotonic()
    with pytest.raises(ValueError, match='actor failures'):
        cpu_driver.execute('startup-error')
    assert time.monotonic()-started < 6
    out = cpu_driver.outputs[-1]
    stopped = json.loads((out/'stopped.json').read_text())
    assert any(r['actor_id'] == 'actor-01' and 'FileExistsError' in r['error'] for r in stopped['failures'])
    assert (out/'STOP').exists() and not (out/'qualification.json').exists()


def test_startup_readiness_has_its_own_finite_deadline(cpu_driver, monkeypatch):
    monkeypatch.setattr(D, 'STARTUP_SECONDS', .4)
    started = time.monotonic()
    with pytest.raises(ValueError, match='actor failures'):
        cpu_driver.execute('not-ready')
    assert time.monotonic()-started < 4.
    stopped = json.loads((cpu_driver.outputs[-1]/'stopped.json').read_text())
    assert any('startup readiness' in row['error'] or 'control timeout' in row['error']
               for row in stopped['failures'])
    out = cpu_driver.outputs[-1]
    assert not (out/'QUALIFICATION-EXPOSURE-COMPLETE').exists()
    assert (out/'stopped.json').exists()


def test_current_and_reservoir_metadata_carries_verified_policy_sha(tmp_path, monkeypatch):
    m = T.model()
    factory = D.Opponents(None, m, {}, tmp_path)
    policy = A.policy_sha256(m)
    checkpoint = tmp_path/'update-20.pt'
    torch.save(dict(policy_sha256=policy, model=m.state_dict()), checkpoint)
    checkpoint.with_suffix('.json').write_text(json.dumps(dict(policy_sha256=policy,
        learner_checkpoint=dict(sha256=D.S.file_sha(checkpoint)))))
    monkeypatch.setattr(D, 'bounded_policy_player', lambda model, **_: model)
    for family in ('current', 'reservoir'):
        _, metadata = factory.make(dict(league=family, reservoir_u=.99), 20)
        assert metadata == dict(family=family, version=20, policy_sha256=policy)
        assert D.opponent_identity(metadata) == metadata
    with pytest.raises(ValueError, match='identity missing'):
        D.opponent_identity(dict(family='current', version=20))
    # A ledger that agrees with a tampered checkpoint header cannot bypass the
    # independently recomputed model digest.
    torch.save(dict(policy_sha256='e'*64, model=m.state_dict()), checkpoint)
    checkpoint.with_suffix('.json').write_text(json.dumps(dict(policy_sha256='e'*64,
        learner_checkpoint=dict(sha256=D.S.file_sha(checkpoint)))))
    with pytest.raises(ValueError, match='model policy SHA'):
        factory.make(dict(league='current'), 20)


def test_cutoff_enforces_cleanup_while_coordinator_condition_is_held(cpu_driver, monkeypatch):
    original = C.Coordinator
    released, locked = [], threading.Event()
    release_now = threading.Event()
    holders = []
    def hold(coordinator):
        with coordinator.condition:
            locked.set()
            deadline = time.monotonic()+4
            while not any((out/'QUALIFICATION-EXPOSURE-COMPLETE').exists() for out in cpu_driver.outputs):
                if release_now.wait(.01) or time.monotonic() >= deadline:
                    break
            release_now.wait(1.2)
        released.append(time.monotonic())
    class HeldCoordinator(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            thread = threading.Thread(target=hold, args=(self,), name='fixture-condition-holder')
            holders.append(thread)
            thread.start()
            assert locked.wait(1)
    monkeypatch.setattr(C, 'Coordinator', HeldCoordinator)
    original_signal = D.WorkerSession.signal
    signals = []
    def observed_signal(session, sig):
        signals.append(time.monotonic())
        original_signal(session, sig)
    monkeypatch.setattr(D.WorkerSession, 'signal', observed_signal)
    try:
        with pytest.raises(ValueError, match='actor failures'):
            cpu_driver.execute('hung-engine')
    finally:
        release_now.set()
        for thread in holders:
            thread.join(2)
    assert signals and released and min(signals) < released[0]
    assert any(row['stopping'] for row in cpu_driver.observations)
    assert not (cpu_driver.outputs[-1]/'qualification.json').exists()


def test_exact_worker_session_cleanup_reaps_descendant_and_leaves_other_session_alone(monkeypatch):
    D.adopt_worker_descendants()
    program = '''
import os,signal,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
child=os.fork()
if child:
    print(child,flush=True)
time.sleep(30)
'''
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    owned = subprocess.Popen([sys.executable, '-c', program], stdout=subprocess.PIPE, start_new_session=True)
    session = D.WorkerSession(owned)
    monkeypatch.setattr(D, 'WORKER_EXIT_SECONDS', .05)
    monkeypatch.setattr(D, 'WORKER_TERM_SECONDS', .05)
    monkeypatch.setattr(D, 'WORKER_KILL_SECONDS', 2.)
    try:
        descendant = int(owned.stdout.readline())
        assert descendant in session.observe()
        outcome = session.finish()
        assert outcome['forced'] and session.empty()
        assert unrelated.poll() is None
        with pytest.raises(FileNotFoundError):
            D.process_identity(descendant)
    finally:
        owned.stdout.close()
        session.signal(__import__('signal').SIGKILL)
        owned.wait(timeout=3)
        unrelated.kill()
        unrelated.wait(timeout=3)


def test_entry_exits_failed_after_cleanup_deadline_even_with_stuck_non_daemon_thread(tmp_path):
    program = '''
from contextlib import nullcontext
import sys,threading
from types import SimpleNamespace as NS
from bot.pretrain_v1 import run_registered_rl as E,rl_driver as D
D.read_config=lambda path:{}
def failed(*args,**kwargs):
    threading.Thread(target=threading.Event().wait,daemon=False).start()
    raise D.CleanupIncomplete('fixture unfinished cleanup')
D.run=failed
E.helper=lambda *args:NS(math_backend=lambda _:nullcontext())
sys.argv=['entry','soak','--config',sys.argv[1],'--out',sys.argv[2]]
E.main()
'''
    result = subprocess.run([sys.executable, '-c', program, str(tmp_path/'config'), str(tmp_path/'out')],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2 and 'unfinished cleanup' in result.stderr


def test_exit_mm_flag_keeps_rss_guard_from_misclassifying_an_exiting_task(monkeypatch):
    process = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
    try:
        deadline = time.monotonic()+3
        while True:
            row = D.process_identity(process.pid)
            if row['state'] == 'Z':
                break
            assert time.monotonic() < deadline
            time.sleep(.005)
        # Retain the real PID/start/session and kernel PF_EXITING bit. Project
        # the R state seen before exit_notify; RSS has already gone at exit_mm.
        assert row['exiting']
        monkeypatch.setattr(D, 'process_identity', lambda pid: dict(row, state='R'))
        assert D.worker_observation(process, row['start']) is None
        # An ordinary live identity with unreadable RSS still fails closed.
        monkeypatch.setattr(D, 'process_identity', lambda pid: dict(row, state='R', exiting=False))
        with pytest.raises(ValueError, match='RSS violation'):
            D.worker_observation(process, row['start'])
    finally:
        process.wait(timeout=3)
