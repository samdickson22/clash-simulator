"""CPU only. Spawned mock engines never bootstrap or import the real engine."""
import copy
from contextlib import contextmanager
from dataclasses import asdict
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
from types import SimpleNamespace as NS

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bot.pretrain_v1 import actor_worker as W, stream_actor as A
from bot.pretrain_v1.tests import test_actor_worker as T

spec = importlib.util.spec_from_file_location('terminal_recycle_qualifier',
    ROOT/'bot/pretrain_v1/checks/qualify_terminal_recycle.py')
Q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Q)


def tiny_model(rejections=False):
    model = T.model().double().eval()
    if rejections:
        model.gate_bias.fill_(-100.)
    return model


def mock_runtime(source):
    return Q.runtime_record(source['sha256'], dict(native_sha256='a'*64, gamedata_sha256='b'*64), str(torch.__version__))


def mock_worker(path, fd):
    """Exercise the production worker body with only its engine/bootstrap mocked."""
    s = json.loads(Path(path).read_bytes())
    Q.LIMITS.update(s['mock_limits'])
    with pytest.MonkeyPatch.context() as patch:
        from bot.pretrain_v1 import policy, sim_ours
        from bot.players import ours
        from bot.eval import headline
        model = lambda: tiny_model(s['mock_rejections'])
        patch.setattr(Q, 'host_guard', lambda: None)
        patch.setattr(Q, 'verify_inputs', lambda **_: s['inputs'])
        patch.setattr(Q, 'review_receipt', lambda *args: {})
        patch.setattr(Q, 'BUNDLE', Path(s['mock_bundle']))
        patch.setattr(Q, 'POLICIES', {'M': A.policy_sha256(model())})
        patch.setattr(policy, 'load', lambda _: (model(), dict(cfg=model().cfg,
                      admission=dict(eligible=True), gate_bias=float(model().gate_bias))))
        real_helper = Q.helper
        def helper(name, filename):
            if filename == 'check_ours_producer.py':
                runtime = mock_runtime(s['source'])
                return NS(bootstrap=lambda *args: (NS(pins=runtime, root=Q.RUNTIME, native_dir=Q.RUNTIME/'native'),
                          dict(runtime_manifest_sha256=Q.MAP_SHAS['files'], actor_manifest_sha256=Q.MAP_SHAS['source_files'])),
                          check_origins=lambda *args: None)
            return real_helper(name, filename)
        patch.setattr(Q, 'helper', helper)
        @contextmanager
        def bind(_):
            yield
        patch.setattr(sim_ours, 'bind_matches', bind)
        patch.setattr(headline, 'make_player', lambda *args: NS(name='scripted-pressure', style='pressure', deadline_seconds=None))

        def fake_match(rt, players, *, seed, decks, levels, max_ticks, verbose, observer):
            from bot.players.base import MatchContext, Decision, WAIT
            actor = next(p for p in players.values() if isinstance(p, A.StreamingPolicyOursPlayer))
            seat = s['seat']
            b, own = T.battle(patch)
            own.elixir = 7. if s['mock_rejections'] else 0.
            b.players = {0: copy.deepcopy(own), 1: copy.deepcopy(own)}
            b.game_over, b.winner = False, None
            actor.bind_ours(b)
            actor.start(MatchContext(seat, seed, tuple(T.DECK)))
            counts = {a: dict(submitted=0, executed=0, rejected=0, pending_at_end=0) for a in (0, 1)}
            channels = {a: NS(diagnostics=lambda a=a: dict(counts[a])) for a in (0, 1)}
            plays = {0: [], 1: []}
            pending = []
            end = 145 if s['mock_rejections'] else 115
            for tick in range(90, end, 5):
                while pending and pending[0][0] <= tick:
                    executed, card, action = pending.pop(0)
                    # A rejected mock command leaves hand/elixir unchanged.
                    plays[seat].append((executed, card, action, False))
                    counts[seat]['executed'] += 1
                    counts[seat]['rejected'] += 1
                    counts[seat]['pending_at_end'] -= 1
                b.tick = tick
                d = actor.act(NS(tick=tick, seat=seat, can_act=True))
                if d.action < WAIT:
                    counts[seat]['submitted'] += 1
                    counts[seat]['pending_at_end'] += 1
                    pending.append((tick+27, own.hand[d.action//576], d.action))
                else:
                    assert d.action == WAIT
                observer(NS(tick=tick, seat=seat, can_act=True), d)
                observer(NS(tick=tick, seat=1-seat, can_act=True), Decision(WAIT))
            b.tick, b.game_over, b.winner = end-3, True, seed % 2
            actor.close()
            return dict(seed=seed, decks=decks, players={0: 'mock', 1: 'mock'}, terminal=True,
                        winner=b.winner, ticks=b.tick, channels={a: c.diagnostics() for a, c in channels.items()},
                        play_log=plays, accepted={0: 0, 1: 0}, command_sha256='c'*64,
                        timing={}, cpu_seconds=0.)
        patch.setattr(ours, 'play_match', fake_match)
        Q.worker(path, fd)
        assert not any(n == 'clasher' or n.startswith('clasher.') for n in sys.modules), 'real engine imported'


@pytest.fixture(params=[(0, False), (1, False), (0, True)], ids=['seat0', 'seat1', 'rejected-taps'])
def mock_spec(request, tmp_path, monkeypatch):
    monkeypatch.setitem(Q.LIMITS, 'quota_steps', 2)
    monkeypatch.setitem(Q.LIMITS, 'chunk_rows', 3)
    monkeypatch.setitem(Q.LIMITS, 'budget_steps', 100)
    source = dict(files={}, sha256=Q.digest({}), base=Q.BASE, commit='mock-only')
    seat, rejections = request.param
    model = tiny_model(rejections)
    runtime = mock_runtime(source)
    claims = tmp_path/'claims'
    claims.mkdir()
    bundle = tmp_path/'mock-bundle'
    bundle.mkdir()
    (bundle/'M-model-cfg.json').write_bytes(Q.encoded(model.cfg))
    cursor = dict(publication_sequence=0, next_game_sequence=0, seed=Q.cases(seat)[0]['seed'],
                  actor_id='mock-terminal-parity', schedule_sha256=Q.digest(Q.cases(seat)),
                  runtime_provenance_sha256=Q.digest(runtime))
    common = dict(size='M', seat=seat, actor_id=cursor['actor_id'], seed=cursor['seed'], source=source,
                  inputs={}, review='mock-only', review_sha256='mock-only', claims=str(claims),
                  claim_identity=[claims.stat().st_dev, claims.stat().st_ino], cursor=cursor,
                  mock_limits=Q.LIMITS, mock_bundle=str(bundle), mock_rejections=rejections)
    common['inputs'] = dict(decisions='mock-only')
    initial = dict(publication_sequence=0, next_game_sequence=0, next_tick=90, generated_steps=0,
                   remaining_quota=2, version=0, policy_sha256=A.policy_sha256(model),
                   runtime_provenance_sha256=Q.digest(runtime), actor_id=cursor['actor_id'], seed=cursor['seed'],
                   anchor_sha256=Q.ANCHORS['M'], boundary_declined_steps=0)
    return common, initial


def spawn_mock(common, path, state, *, seconds=30, **kw):
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--mock-worker', '{spec}', '{control_fd}']
    return Q.run_process(dict(common, out=str(path), **kw), path, state,
                         command=command, guard=lambda: None, seconds=seconds)


def test_actual_worker_protocol_with_spawned_fake_engine_and_reaped_restore(mock_spec, tmp_path):
    common, initial = mock_spec
    baseline_state, recycled_state = copy.deepcopy(initial), copy.deepcopy(initial)
    baseline, _, baseline_exit = spawn_mock(common, tmp_path/'persistent', baseline_state, end_game=2)
    first, cp, old_exit = spawn_mock(common, tmp_path/'source', recycled_state, end_game=1)
    assert old_exit['reaped'] and old_exit['exitcode'] == 0 and Q.proc(cp['record']['source_process']['pid']) is None
    second, _, new_exit = spawn_mock(dict(common, cursor=cp['record']['driver_state']),
                                    tmp_path/'successor', recycled_state, end_game=2, restore=cp)
    Q.compare_game_artifacts(tmp_path/'persistent', tmp_path/'source', 0)
    Q.compare_game_artifacts(tmp_path/'persistent', tmp_path/'successor', 1)
    Q.compare_records(baseline, first+second)
    assert baseline_state == recycled_state
    n = 11 if common['mock_rejections'] else 5
    assert baseline_state['generated_steps'] == 2*n and baseline_state['version'] == n
    assert cp['record']['version'] == n//2 and cp['record']['remaining_quota'] == 1
    assert all(x['reaped'] and not x['survivors'] for x in (baseline_exit, old_exit, new_exit))
    assert len(list(Path(common['claims']).iterdir())) == 1
    assert len(list((tmp_path/'successor/raw').glob('chunk-*/*.npy'))) > 0
    # A second successor under the same durable namespace fails before a game.
    with pytest.raises((EOFError, RuntimeError)):
        spawn_mock(dict(common, cursor=cp['record']['driver_state']), tmp_path/'duplicate',
                   copy.deepcopy(initial), end_game=2, restore=cp)
    assert 'already claimed' in (tmp_path/'duplicate/worker-result.json').read_text()
    assert not list((tmp_path/'duplicate').glob('game-*-engine.json'))
    if common['mock_rejections']:
        assert all(r['operational_rejections']['counts']['rejected'] > 0 for r in baseline)
        assert baseline[-1]['counters']['discarded_steps'] == 0
        assert all(r['counters']['generated_steps'] == (i+1)*n for i, r in enumerate(baseline))


def test_external_guard_interrupts_worker_waiting_for_terminal_ack(mock_spec, tmp_path, monkeypatch):
    common, initial = mock_spec
    original = Q.Wire.send
    withheld = []
    def send(wire, message, *args, **kw):
        if message['kind'] == 'checkpoint_retained':
            withheld.append(message)
            return  # fault injection: owning actor remains blocked after capture
        return original(wire, message, *args, **kw)
    monkeypatch.setattr(Q.Wire, 'send', send)
    with pytest.raises(RuntimeError, match='worker wall timeout'):
        spawn_mock(common, tmp_path/'hung-ack', copy.deepcopy(initial), end_game=1, seconds=3)
    assert len(withheld) == 1
    receipt = json.loads((tmp_path/'hung-ack/exit.json').read_bytes())
    assert receipt['reaped'] and not receipt['survivors'] and receipt['failed']
    assert (tmp_path/'hung-ack/parent-retained-1.json').exists()
    assert not list(Path(common['claims']).iterdir()), 'blocked source cannot grant a successor'


def publication(tmp_path):
    with pytest.MonkeyPatch.context() as patch:
        actor = T.actor()
        chunks = []
        original = actor.publish
        def publish(chunk, boundary):
            chunks.append((copy.deepcopy(chunk), boundary))
            return original(chunk, boundary)
        actor.publish = publish
        T.game(actor, patch)
    c, b = chunks[0]
    runtime = dict(mock='only')
    c = A.Chunk(**dict(vars(c), provenance_sha256=Q.digest(runtime)))
    queue = A.AtomicChunkQueue(tmp_path/'raw', max_bytes=2**24, max_chunks=10, runtime_manifest=runtime)
    receipt = queue.write(c)
    message = dict(sequence=0, manifest=str(queue.root/receipt.name/'manifest.json'), receipt=asdict(receipt),
                   boundary=asdict(b), ticks=[90, 95], case=Q.cases(0)[0],
                   actual=dict(terminal=False, ticks=100, winner=None))
    # This input is a deliberate small synthetic actor, not a selected anchor.
    message['case'] = dict(message['case'], opponent=c.opponent_id)
    state = dict(publication_sequence=0, next_game_sequence=0, next_tick=90, generated_steps=0,
                 version=0, remaining_quota=2, policy_sha256=c.policy_sha256,
                 actor_id=c.actor_id, seed=c.seed, anchor_sha256=c.anchor_sha256,
                 boundary_declined_steps=0, runtime_provenance_sha256=Q.digest(runtime))
    return message, state


@pytest.mark.parametrize('mutation', ['bytes', 'dtype', 'missing', 'extra', 'cursor', 'quota', 'tick', 'policy', 'runtime', 'actor'])
def test_publication_missing_extra_changed_rows_and_pins_fail_closed(tmp_path, monkeypatch, mutation):
    message, state = publication(tmp_path)
    monkeypatch.setitem(Q.LIMITS, 'budget_steps', 100)
    path = Path(message['manifest'])
    manifest = json.loads(path.read_bytes())
    if mutation == 'bytes':
        p = path.parent/'action.npy'
        raw = bytearray(p.read_bytes()); raw[-1] ^= 1; p.write_bytes(raw)
    elif mutation == 'dtype':
        manifest['arrays']['action']['dtype'] = 'int32'
    elif mutation == 'missing':
        (path.parent/'action.npy').unlink()
    elif mutation == 'extra':
        message['receipt']['rows'] += 1
    elif mutation == 'cursor': message['sequence'] += 1
    elif mutation == 'quota': state['remaining_quota'] -= 1
    elif mutation == 'tick': state['next_tick'] += 5
    elif mutation == 'policy': state['policy_sha256'] = 'f'*64
    elif mutation == 'runtime': state['runtime_provenance_sha256'] = 'f'*64
    elif mutation == 'actor': state['actor_id'] = 'other-actor'
    if mutation == 'dtype':
        path.write_bytes(Q.encoded(manifest))
        message['receipt']['manifest_sha256'] = Q.file_sha(path)
    with pytest.raises((RuntimeError, FileNotFoundError)):
        Q.validate_publication(message, state, message['case'], tmp_path/'raw')
    assert path.exists(), 'failed artifacts must remain'


def test_exact_quota_ack_and_same_version_terminal_protocol(tmp_path, monkeypatch):
    message, state = publication(tmp_path)
    monkeypatch.setitem(Q.LIMITS, 'budget_steps', 100)
    permit, _ = Q.validate_publication(message, state, message['case'], tmp_path/'raw')
    assert permit == dict(version=1, policy_sha256=state['policy_sha256'], quota_steps=257)
    assert state['publication_sequence'] == 1 and state['next_tick'] == 100


@pytest.mark.parametrize('kind', ['engine', 'rss', 'host', 'exception'])
def test_external_guard_cleans_owned_hung_or_failed_worker(tmp_path, kind):
    script = ('import time; time.sleep(60)' if kind != 'exception' else 'raise RuntimeError("fixture failure")')
    command = [sys.executable, '-B', '-c', script]
    calls = [0]
    def guard():
        calls[0] += 1
        if kind == 'host':
            raise RuntimeError('fixture host limit')
    with pytest.MonkeyPatch.context() as patch:
        if kind == 'rss': patch.setitem(Q.LIMITS, 'worker_rss_bytes', 1)
        with pytest.raises((RuntimeError, EOFError)):
            Q.run_process({}, tmp_path/kind, {}, command=command, guard=guard, seconds=.35)
    receipt = json.loads((tmp_path/kind/'exit.json').read_bytes())
    assert receipt['reaped'] and receipt['survivors'] == []
    assert Q.proc(receipt['source_process']['pid']) is None


def test_review_receipt_missing_or_wrong_source_rejects(tmp_path):
    with pytest.raises(FileNotFoundError):
        Q.review_receipt(tmp_path/'absent.json', 'a'*64, dict(sha256='b'*64))
    p = tmp_path/'wrong.json'
    p.write_bytes(Q.encoded(dict(schema='pv1-terminal-recycle-review-v1', verdict='GO')))
    with pytest.raises(RuntimeError, match='independent exact-source'):
        Q.review_receipt(p, Q.file_sha(p), dict(sha256='b'*64))


def test_worker_completion_message_cannot_hide_error_exit(tmp_path):
    script = '''import json, os, socket, struct, sys
s=socket.socket(fileno=int(sys.argv[1]))
fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
identity=dict(pid=os.getpid(),start=int(fields[19]))
for message in [dict(kind='ready',identity=identity,runtime={}),dict(kind='done')]:
 data=json.dumps(message).encode(); s.sendall(struct.pack('!i',len(data))+data)
s.close()
sys.exit(7)
'''
    with pytest.raises(RuntimeError, match='exit/cleanup failed'):
        Q.run_process(dict(end_game=0, cursor=dict(next_game_sequence=0)), tmp_path/'bad-exit',
                      dict(runtime_provenance_sha256=Q.digest({})),
                      command=[sys.executable, '-B', '-c', script, '{control_fd}'], guard=lambda: None)
    receipt = json.loads((tmp_path/'bad-exit/exit.json').read_bytes())
    assert receipt['exitcode'] == 7 and receipt['reaped'] and receipt['failed']


def test_buffered_frames_survive_peer_eof_and_transport_handles_high_fds():
    import fcntl
    left, right = socket.socketpair()
    high = socket.socket(fileno=fcntl.fcntl(left.fileno(), fcntl.F_DUPFD_CLOEXEC, 1232))
    left.close()
    try:
        wire = Q.Wire(high)
        messages = [dict(kind='ready'), dict(kind='done')]
        right.sendall(b''.join(struct.pack('!i', len(Q.encoded(m)))+Q.encoded(m) for m in messages))
        right.close()
        assert wire.poll() == messages[0]
        assert wire.poll() == messages[1]
    finally:
        high.close(); right.close()


def test_sample_journal_retains_empty_entity_axis_and_exact_types(tmp_path):
    pending = NS(features=dict(ent=np.empty((0, 13), np.int16)), action=2304,
                 old_logp=-.125, old_value=.25, actor=True, boundary_declined=False)
    path = tmp_path/'samples.bin'
    Q.journal_sample(path, pending, dict(tick=90), 3)
    raw = path.read_bytes()
    length, = struct.unpack('!i', raw[:4])
    header = json.loads(raw[4:4+length])
    cursor = 4+length
    decoded = {}
    for key, entry in header['arrays'].items():
        decoded[key] = np.load(io.BytesIO(raw[cursor:cursor+entry['bytes']]), allow_pickle=False)
        cursor += entry['bytes']
    assert decoded['f_ent'].shape == (0, 13) and decoded['f_ent'].dtype == np.int16
    assert decoded['action'].dtype == np.int64 and decoded['old_logp'].dtype == np.float64
    assert decoded['old_logp'][0] == -.125 and cursor == len(raw)


def test_changed_driver_cursor_rejected_before_claim_with_dead_source(tmp_path):
    # Use an own spawned fixture process, then change only the independent cursor.
    # A plain subprocess avoids leaving multiprocessing's resource-tracker
    # child in the dedicated monitor parent used by later fixture tests.
    from multiprocessing.connection import Connection
    read_fd, write_fd = os.pipe()
    receive = Connection(read_fd, readable=True, writable=False)
    script = ("import sys; from multiprocessing.connection import Connection; "
              "from bot.pretrain_v1.tests.test_actor_worker import _checkpoint_child; "
              "_checkpoint_child(Connection(int(sys.argv[1]), readable=False, writable=True))")
    child = subprocess.Popen([sys.executable, '-B', '-c', script, str(write_fd)], pass_fds=(write_fd,))
    identity = Q.proc(child.pid)
    os.close(write_fd)
    try:
        assert receive.poll(30)
        record, sha, cursor, _ = receive.recv()
        assert child.wait(30) == 0
    finally:
        if child.poll() is None:
            reap_test_identities([identity])
            child.wait(5)
        receive.close()
    cursor['publication_sequence'] += 1
    with pytest.raises(W.WorkerError, match='cursor mismatch'):
        W.ActorCheckpoint.restore_record(record, T.model(), T.callback, expected_sha256=sha,
            driver_state=cursor, claim_directory=tmp_path)
    assert not list(tmp_path.iterdir())


def test_namespace_is_paired_bounded_and_disjoint_by_construction():
    seeds = {row['seed'] for seat in (0, 1) for row in Q.cases(seat)}
    assert len(seeds) == 4 and all(2**61 <= s < 2**62 for s in seeds)
    assert not seeds & {2026102101, 2026102102, 2026102103}
    assert Q.LIMITS['total_games'] == 2*2*2*2
    assert all(row['opponent'] == 'scripted-pressure' for seat in (0, 1) for row in Q.cases(seat))


def test_difference_names_missing_row_or_changed_field():
    with pytest.raises(RuntimeError, match='missing/extra rows'):
        Q.compare_records([dict(action=4)], [])
    with pytest.raises(RuntimeError, match=r'game\[0\].action'):
        Q.compare_records([dict(action=4)], [dict(action=5)], 'game')


def test_live_source_and_nonterminal_are_refused(tmp_path):
    with pytest.MonkeyPatch.context() as patch:
        actor = T.actor()
        b, _ = T.battle(patch)
        b.game_over, b.winner = False, None
        actor.bind_ours(b)
        actor.start(T.MatchContext(0, 101, tuple(T.DECK)))
        with pytest.raises(W.WorkerError, match='closed game'):
            W.ActorCheckpoint.capture(actor, T.cursor(actor))
        actor.close()
        actor = T.actor(); T.game(actor, patch)
        cp = W.ActorCheckpoint.capture(actor, T.cursor(actor))
        with pytest.raises(W.WorkerError, match='still live'):
            W.ActorCheckpoint.restore_record(cp.record, T.model(), T.callback, expected_sha256=cp.sha256,
                driver_state=T.cursor(actor), claim_directory=tmp_path)
        assert not list(tmp_path.iterdir())


# R59 regressions use pure source extraction or explicitly reaped own children.
def test_r59_real_resolver_contract_from_exact_pinned_ast():
    import ast
    source = Q.ACTOR_SOURCE/'bot/levels/match.py'
    assert Q.file_sha(source) == 'b94929cfdbba8fa1c75b0e25f0b926a67b3d8accb3058e1df6adc413e762a960'
    tree = ast.parse(source.read_bytes())
    names = {'_seat', '_level', 'resolve', 'tag'}
    pure = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names],
                      type_ignores=[])
    assert len(pure.body) == 4
    namespace = dict(MAX_LEVEL=16)
    before = set(sys.modules)
    exec(compile(pure, str(source), 'exec'), namespace)
    for seat in (0, 1):
        for case in json.loads(Q.encoded(Q.cases(seat))):
            # Test the serialized argument and the very helper used at play_match.
            for levels in (case['levels'], Q.match_levels(case)):
                result = namespace['resolve'](levels, case['decks'])
                assert result['towers'] == [9, 9] and result['planner'] == 'l11'
                assert result['cards'] == [case['levels']['cards']['0'], case['levels']['cards']['1']]
            assert Q.match_levels(case)['towers'] == {0: 9, 1: 9}
    assert set(sys.modules) == before, 'resolver contract imported a module'


def test_r59_cleanup_capability_exact_interpreter_and_refusal_before_spawn(tmp_path, monkeypatch):
    import platform
    Q.cleanup_capability()  # Both syscalls work even when Python exposes neither API.
    evidence = dict(python=sys.version, executable=sys.executable, machine=platform.machine(),
                    os_pidfd_open=hasattr(os, 'pidfd_open'),
                    signal_pidfd_send_signal=hasattr(Q.signal, 'pidfd_send_signal'), syscall_probe=True)
    (tmp_path/'capability.json').write_bytes(Q.encoded(evidence))
    spawned = []
    def unsupported(*args):
        raise OSError(38, 'injected unsupported syscall')
    monkeypatch.setattr(Q, 'pidfd_signal', unsupported)
    monkeypatch.setattr(Q.subprocess, 'Popen', lambda *a, **k: spawned.append(a))
    left, right = socket.socketpair()
    try:
        with (tmp_path/'log').open('wb') as log:
            with pytest.raises(OSError, match='unsupported syscall'):
                Q.OwnedWorker(['never'], right, log, guard=lambda: None)
    finally:
        left.close(); right.close()
    assert not spawned


def test_r59_pidfd_identity_race_fails_closed(monkeypatch):
    identity = Q.proc(os.getpid())
    owned = Q.OwnedWorker.__new__(Q.OwnedWorker)
    owned.owned = {identity['pid']: identity}
    fd = Q.pidfd_open(identity['pid'])
    owned.pidfds = {identity['pid']: fd}
    calls, signals = [], []
    def changed(pid):
        calls.append(pid)
        return identity if len(calls) == 1 else dict(identity, start=identity['start']+1)
    monkeypatch.setattr(Q, 'proc', changed)
    monkeypatch.setattr(Q, 'pidfd_signal', lambda *args: signals.append(args))
    try:
        with pytest.raises(RuntimeError, match='identity changed'):
            owned.signal_exact(identity['pid'], Q.signal.SIGKILL)
    finally:
        os.close(fd)
    assert len(calls) == 2 and not signals


def reap_test_identities(identities):
    """Independent test fallback; never count this assistance as candidate cleanup."""
    import time
    from bot.pretrain_v1 import lease_supervisor as pure_r37
    assisted = []
    for identity in identities:
        pid = identity['pid']
        current = Q.proc(pid)
        if current is None or current['start'] != identity['start']:
            continue
        assisted.append(pid)
        pure_r37.signal_exact(pid, identity['start'], Q.signal.SIGKILL)
        deadline = time.monotonic()+5
        while True:
            try:
                reaped = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break
            if reaped != (0, 0):
                break
            assert time.monotonic() < deadline, 'test fallback reap timeout'
            time.sleep(.01)
    return assisted


PROTOCOL_CHILD = '''import json, os, socket, struct, sys, time
s=socket.socket(fileno=int(sys.argv[1]))
fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
identity=dict(pid=os.getpid(),start=int(fields[19]))
def send(message):
 data=json.dumps(message).encode(); s.sendall(struct.pack('!i',len(data))+data)
send(dict(kind='ready',identity=identity,runtime={}))
send(dict(kind='done'))
'''


def test_r59_fork_cleanup_retains_full_set_and_original_failure(tmp_path, monkeypatch):
    import time
    Q.cleanup_capability()
    identity_path = tmp_path/'fork-identity.json'
    script = '''import json, os, sys, time
pid=os.fork()
if pid == 0:
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[1],'w') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
 time.sleep(8)
 os._exit(0)
time.sleep(8)
'''
    # Normal rejection and a transient cleanup-signal failure both reap the exact set.
    original = Q.pidfd_signal
    injected = []
    def signal_once(fd, sig):
        if sig == Q.signal.SIGKILL and not injected:
            injected.append(True)
            raise OSError(5, 'injected cleanup signal failure')
        return original(fd, sig)
    monkeypatch.setattr(Q, 'pidfd_signal', signal_once)
    identities, assisted = [], []
    try:
        with pytest.raises(RuntimeError, match='extra process'):
            Q.run_process({}, tmp_path/'fork', {}, guard=lambda: None, seconds=2,
                          command=[sys.executable, '-B', '-c', script, str(identity_path)])
        receipt = json.loads((tmp_path/'fork/exit.json').read_bytes())
        identities = receipt['owned_processes']
        assert len(identities) == 2
        assert 'extra process' in receipt['original_failure']['error']
        assert 'injected cleanup signal failure' in str(receipt['cleanup_errors'])
        assert receipt['failed'] and receipt['reaped'] and not receipt['survivors']
        assert all(Q.proc(p['pid']) is None for p in identities)
    finally:
        if identity_path.exists(): identities.append(json.loads(identity_path.read_bytes()))
        exit_path = tmp_path/'fork/exit.json'
        if exit_path.exists():
            r = json.loads(exit_path.read_bytes())
            identities.extend(r.get('owned_processes', []))
            identities.append(r.get('source_process', r.get('identity')))
        assisted = reap_test_identities([p for p in identities if p])
        (tmp_path/'explicit-cleanup.json').write_bytes(Q.encoded(dict(assisted=assisted)))
    assert not assisted, 'candidate required independent cleanup assistance'


@pytest.mark.parametrize('violation', ['worker', 'parent', 'host', 'rss', 'output', 'child'])
def test_r59_done_keeps_monitoring_until_reap(tmp_path, monkeypatch, violation):
    import time
    done_at, checks = [], []
    poll = Q.Wire.poll
    def observe(wire, *args):
        message = poll(wire, *args)
        if message and message['kind'] == 'done': done_at.append(time.monotonic())
        return message
    monkeypatch.setattr(Q.Wire, 'poll', observe)
    def guard():
        checks.append(time.monotonic())
        if done_at and time.monotonic()-done_at[0] >= .15 and violation in ('host', 'parent'):
            raise RuntimeError(violation+' wall timeout' if violation == 'parent' else 'injected host limit')
    real_rss = Q.rss
    def rss(pid):
        if done_at and time.monotonic()-done_at[0] >= .15 and pid != os.getpid():
            return Q.LIMITS['worker_rss_bytes']+1
        return real_rss(pid)
    if violation == 'rss': monkeypatch.setattr(Q, 'rss', rss)
    identity_path = tmp_path/'late-child.json'
    tail = 'time.sleep(1.1)\n'
    if violation == 'output':
        monkeypatch.setitem(Q.LIMITS, 'output_bytes', 100000)
        tail = "time.sleep(.15)\nopen(sys.argv[2], 'wb').write(b'x'*100001)\ntime.sleep(.9)\n"
    elif violation == 'child':
        tail = '''time.sleep(.15)
pid=os.fork()
if pid == 0:
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[2],'w') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
 time.sleep(3)
 os._exit(0)
time.sleep(.9)
'''
    output_arg = str(tmp_path/'late-output.bin') if violation == 'output' else str(identity_path)
    identities, assisted = [], []
    try:
        with pytest.raises(RuntimeError, match='worker exit/cleanup failed'):
            Q.run_process(dict(end_game=0, cursor=dict(next_game_sequence=0)), tmp_path/'done',
                          dict(runtime_provenance_sha256=Q.digest({})),
                          command=[sys.executable, '-B', '-c', PROTOCOL_CHILD+tail, '{control_fd}', output_arg],
                          guard=guard, seconds=.45 if violation == 'worker' else 2)
        receipt = json.loads((tmp_path/'done/exit.json').read_bytes())
        identities = receipt['owned_processes']
        assert receipt['reaped'] and not receipt['survivors'] and receipt['failed']
        expected = dict(worker='worker wall timeout', parent='parent wall timeout', host='injected host limit',
                        rss='worker RSS/nice limit', output='retained output limit', child='extra process')
        assert expected[violation] in receipt['original_failure']['error']
        assert done_at and len([t for t in checks if t >= done_at[0]]) >= 2
        assert max(b-a for a, b in zip(checks, checks[1:])) < .25
        assert receipt['wall_seconds'] < .85, 'unchecked completion wait returned'
    finally:
        if identity_path.exists(): identities.append(json.loads(identity_path.read_bytes()))
        path = tmp_path/'done/exit.json'
        if path.exists():
            receipt = json.loads(path.read_bytes())
            identities.extend(receipt.get('owned_processes', []))
            identities.append(receipt.get('source_process', receipt.get('identity')))
        assisted = reap_test_identities([p for p in identities if p])
        (tmp_path/'explicit-cleanup.json').write_bytes(Q.encoded(dict(assisted=assisted)))
    assert not assisted


@pytest.mark.parametrize('prefix', [b'\x00', b'\x00\x00\x00', struct.pack('!i', 10), struct.pack('!i', 10)+b'{'])
@pytest.mark.parametrize('ending', ['eof', 'stall', 'late-byte', 'late-completion'])
def test_r59_whole_frame_deadline_header_body_eof_and_late_bytes(monkeypatch, prefix, ending):
    import fcntl
    now = [100.]
    monkeypatch.setattr(Q.time, 'monotonic', lambda: now[0])
    monkeypatch.setitem(Q.LIMITS, 'control_seconds', .2)
    monkeypatch.setitem(Q.LIMITS, 'poll_seconds', .001)
    left, peer = socket.socketpair()
    high = socket.socket(fileno=fcntl.fcntl(left.fileno(), fcntl.F_DUPFD_CLOEXEC, 1232))
    left.close()
    try:
        wire = Q.Wire(high)
        peer.sendall(prefix)
        assert wire.poll() is None
        if ending == 'eof':
            peer.close()
            with pytest.raises(EOFError, match='within frame'): wire.poll()
        else:
            if ending.startswith('late'):
                now[0] += .15
                # A byte before expiry does not renew the clock.
                peer.sendall(b' ')
                assert wire.poll() is None
            now[0] += .21
            if ending == 'late-completion': peer.sendall(b' '*32)
            with pytest.raises(RuntimeError, match='control frame timeout'): wire.poll()
    finally:
        high.close(); peer.close()


def test_r59_frame_completion_and_idle_compute_have_separate_clocks(monkeypatch):
    now = [100.]
    monkeypatch.setattr(Q.time, 'monotonic', lambda: now[0])
    monkeypatch.setitem(Q.LIMITS, 'control_seconds', .2)
    monkeypatch.setitem(Q.LIMITS, 'poll_seconds', .001)
    left, peer = socket.socketpair()
    try:
        wire = Q.Wire(left)
        now[0] += 60
        assert wire.poll() is None and wire.frame_started is None
        raw = struct.pack('!i', 2)+b'{}'
        peer.sendall(raw[:1]); assert wire.poll() is None
        now[0] += .1
        peer.sendall(raw[1:4]); assert wire.poll() is None
        now[0] += .05
        peer.sendall(raw[4:]); assert wire.poll() == {}
        now[0] += 60
        assert wire.poll() is None and wire.frame_started is None
        peer.sendall(raw); assert wire.poll() == {}
        peer.close()
        with pytest.raises(EOFError, match='closed control'): wire.poll()
    finally:
        left.close(); peer.close()


def test_r59_parent_stalled_frame_rejects_before_worker_deadline(tmp_path, monkeypatch):
    import time
    monkeypatch.setitem(Q.LIMITS, 'control_seconds', .2)
    script = '''import socket, struct, sys, time
s=socket.socket(fileno=int(sys.argv[1]))
s.sendall(struct.pack('!i', 100)+b'{')
time.sleep(1.1)
'''
    checks = []
    with pytest.raises(RuntimeError, match='control frame timeout'):
        Q.run_process({}, tmp_path/'frame', {},
                      command=[sys.executable, '-B', '-c', script, '{control_fd}'],
                      guard=lambda: checks.append(time.monotonic()), seconds=2)
    receipt = json.loads((tmp_path/'frame/exit.json').read_bytes())
    assert receipt['reaped'] and not receipt['survivors'] and receipt['failed']
    assert receipt['wall_seconds'] < .7
    assert 'control frame timeout' in receipt['original_failure']['error']
    assert len(checks) >= 3 and max(b-a for a,b in zip(checks,checks[1:])) < .25


@pytest.mark.parametrize('phase', ['monitor', 'cleanup'])
def test_r59_unexpected_cleanup_failure_keeps_original_evidence_and_exact_fallback(tmp_path, monkeypatch, phase):
    real_finish = Q.OwnedWorker.finish
    instances = []
    def broken_finish(owned, *, failed, failure=None):
        instances.append(owned)
        if phase == 'cleanup':
            # A cleanup-only error must not erase the earlier receive failure.
            owned.collect()
            for fd in owned.pidfds.values(): os.close(fd)
            owned.pidfds.clear()
            raise RuntimeError('injected cleanup crash')
        def original_failure():
            raise RuntimeError('injected original monitor failure')
        def cleanup_crash():
            raise RuntimeError('injected cleanup crash')
        owned.check = original_failure
        owned.child.poll = cleanup_crash
        return real_finish(owned, failed=failed, failure=failure)
    monkeypatch.setattr(Q.OwnedWorker, 'finish', broken_finish)
    tail = "time.sleep(2)\n"
    script = PROTOCOL_CHILD+tail if phase == 'monitor' else "import time; time.sleep(2)"
    identities, assisted = [], []
    try:
        with pytest.raises(RuntimeError):
            Q.run_process(dict(end_game=0, cursor=dict(next_game_sequence=0)), tmp_path/'crash',
                          dict(runtime_provenance_sha256=Q.digest({})), guard=lambda: None, seconds=.25,
                          command=[sys.executable, '-B', '-c', script, '{control_fd}'])
        receipt = json.loads((tmp_path/'crash/exit.json').read_bytes())
        identities = receipt['owned_processes']
        assert len(identities) == 1 and receipt['failed']
        assert receipt['status'] == 'cleanup-failed' and 'injected cleanup crash' in receipt['cleanup_error']
        expected = 'injected original monitor failure' if phase == 'monitor' else 'worker wall timeout'
        assert expected in receipt['original_failure']['error']
        assert receipt['original_failure']['traceback']
    finally:
        for owned in instances:
            # Remove only our injected poll override before the independent reap.
            owned.child.__dict__.pop('poll', None)
            identities.extend(owned.owned.values())
        assisted = reap_test_identities(identities)
        (tmp_path/'explicit-cleanup.json').write_bytes(Q.encoded(dict(
            injected_candidate_cleanup_crash=True, assisted=assisted,
            all_exact_identities_gone=all(Q.proc(p['pid']) is None for p in identities))))
        for owned in instances:
            owned.child.poll()
            for fd in owned.pidfds.values(): os.close(fd)
            owned.pidfds.clear()
            owned.release()
    assert all(Q.proc(p['pid']) is None for p in identities)


@pytest.mark.parametrize('zombie', [False, True], ids=['live-orphan', 'zombie-orphan'])
def test_r62_detached_fast_exit_rejected_and_fully_reaped(tmp_path, zombie):
    # Original R62 shape: valid done, fork/setsid, fast worker exit between checks.
    identity_path = tmp_path/'detached.json'
    tail = '''time.sleep(.03)
pid=os.fork()
if pid == 0:
 os.setsid()
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[2],'x') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19]),sid=int(fields[3])),f)
 if sys.argv[3] == 'live': time.sleep(3)
 os._exit(0)
os._exit(0)
'''
    identities, assisted = [], []
    try:
        with pytest.raises(RuntimeError, match='extra process'):
            Q.run_process(dict(end_game=0, cursor=dict(next_game_sequence=0)), tmp_path/'detached',
                dict(runtime_provenance_sha256=Q.digest({})), guard=lambda: None, seconds=1,
                command=[sys.executable, '-B', '-c', PROTOCOL_CHILD+tail, '{control_fd}',
                         str(identity_path), 'zombie' if zombie else 'live'])
        receipt = json.loads((tmp_path/'detached/exit.json').read_bytes())
        identities = receipt['owned_processes']
        captured = json.loads(identity_path.read_bytes())
        assert len(identities) == 2
        assert captured['sid'] == captured['pid'] != receipt['source_process']['pid']
        assert any(p['pid'] == captured['pid'] and p['start'] == captured['start'] for p in identities)
        assert receipt['failed'] and receipt['reaped'] and not receipt['survivors']
        assert 'extra process' in receipt['original_failure']['error']
        assert not receipt['cleanup_errors']
        assert all(Q.proc(p['pid']) is None for p in identities)
    finally:
        if identity_path.exists(): identities.append(json.loads(identity_path.read_bytes()))
        path = tmp_path/'detached/exit.json'
        if path.exists(): identities.extend(json.loads(path.read_bytes()).get('owned_processes', []))
        assisted = reap_test_identities(identities)
        (tmp_path/'explicit-cleanup.json').write_bytes(Q.encoded(dict(assisted=assisted)))
    assert not assisted, 'candidate required independent cleanup assistance'


def r62_run(path, tail, *, guard=lambda: None, args=()):
    return Q.run_process(dict(end_game=0, cursor=dict(next_game_sequence=0)), path,
        dict(runtime_provenance_sha256=Q.digest({})), guard=guard, seconds=2,
        command=[sys.executable, '-B', '-c', PROTOCOL_CHILD+tail, '{control_fd}', *map(str, args)])


def r62_fallback(path, identity_paths=()):
    identities = []
    for p in identity_paths:
        if p.exists(): identities.append(json.loads(p.read_bytes()))
    if (path/'exit.json').exists():
        identities.extend(json.loads((path/'exit.json').read_bytes()).get('owned_processes', []))
    assisted = reap_test_identities(identities)
    (path.parent/'explicit-cleanup.json').write_bytes(Q.encoded(dict(assisted=assisted)))
    return assisted


@pytest.mark.parametrize('zombie', [False, True], ids=['live-foreign', 'zombie-foreign'])
def test_r62_preexisting_foreign_refuses_launch_and_survives(tmp_path, zombie):
    import time
    foreign = subprocess.Popen([sys.executable, '-B', '-c',
                                'import time; time.sleep(.03)' if zombie else 'import time; time.sleep(3)'])
    identity = Q.proc(foreign.pid)
    try:
        if zombie:
            until = time.monotonic()+1
            while Q.proc(foreign.pid)['state'] != 'Z':
                assert time.monotonic() < until
                time.sleep(.01)
        before = Q.proc(foreign.pid)
        with pytest.raises(RuntimeError, match='no preexisting children'):
            r62_run(tmp_path/'refused', "open(sys.argv[2], 'x').close()", args=[tmp_path/'spawned'])
        after = Q.proc(foreign.pid)
        assert before['start'] == after['start'] == identity['start']
        assert after['state'] == 'Z' if zombie else after['state'] not in ('Z', 'X')
        if zombie:
            assert os.waitid(os.P_PID, foreign.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT).si_pid == foreign.pid
        assert not (tmp_path/'spawned').exists() and not (tmp_path/'refused/exit.json').exists()
        assert Q._ACTIVE_PARENT is None
    finally:
        assisted = reap_test_identities([identity])
        foreign.wait(5)
        (tmp_path/'foreign-owner-cleanup.json').write_bytes(Q.encoded(dict(
            foreign_identity=identity, foreign_owner_cleanup=assisted, candidate_spawned=False)))


def test_r62_foreign_future_adoption_remains_outside_refused_launch(tmp_path):
    import time
    Q.cleanup_capability()
    gate, adopted = tmp_path/'foreign-fork-now', tmp_path/'foreign-adopted.json'
    script = '''import json,os,sys,time
deadline=time.monotonic()+1
while not os.path.exists(sys.argv[1]) and time.monotonic()<deadline: time.sleep(.001)
read,write=os.pipe()
pid=os.fork()
if pid == 0:
 os.close(read);os.setsid()
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[2],'x') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
 os.write(write,b'x');os.close(write)
 time.sleep(3);os._exit(0)
os.close(write);os.read(read,1);os._exit(0)
'''
    foreign = subprocess.Popen([sys.executable, '-B', '-c', script, str(gate), str(adopted)])
    identities = [Q.proc(foreign.pid)]
    try:
        with pytest.raises(RuntimeError, match='no preexisting children'):
            r62_run(tmp_path/'refused', 'time.sleep(.03)')
        gate.touch()
        until = time.monotonic()+1
        while not adopted.exists() or Q.proc(foreign.pid)['state'] != 'Z':
            assert time.monotonic() < until
            time.sleep(.001)
        child = json.loads(adopted.read_bytes())
        identities.append(child)
        current = Q.proc(child['pid'])
        assert current['start'] == child['start'] and current['ppid'] == os.getpid()
        assert current['state'] not in ('Z', 'X')
        assert Q.proc(foreign.pid)['start'] == identities[0]['start']
        assert not (tmp_path/'refused/exit.json').exists() and Q._ACTIVE_PARENT is None
    finally:
        if adopted.exists(): identities.append(json.loads(adopted.read_bytes()))
        assisted = reap_test_identities(identities)
        foreign.wait(5)
        (tmp_path/'foreign-owner-cleanup.json').write_bytes(Q.encoded(dict(
            identities=identities, foreign_owner_cleanup=assisted, candidate_spawned=False)))


def test_r62_multithread_parent_refuses_before_launch(tmp_path):
    import threading
    stop = threading.Event()
    thread = threading.Thread(target=lambda: stop.wait(2))
    thread.start()
    try:
        with pytest.raises(RuntimeError, match='one thread'):
            r62_run(tmp_path/'refused', "open(sys.argv[2], 'x').close()", args=[tmp_path/'spawned'])
        assert not (tmp_path/'spawned').exists() and Q._ACTIVE_PARENT is None
    finally:
        stop.set()
        thread.join(3)


@pytest.mark.parametrize('method', ['fork', 'popen', 'posix_spawn', 'nested-owner'])
def test_r62_concurrent_parent_launch_rejected_even_if_guard_catches(tmp_path, method):
    attempted = []
    def guard():
        if attempted: return
        attempted.append(method)
        with pytest.raises(RuntimeError, match='concurrent child launches|already owns'):
            if method == 'fork': os.fork()
            elif method == 'popen': subprocess.Popen([sys.executable, '-B', '-c', 'pass'])
            elif method == 'posix_spawn': os.posix_spawn(sys.executable, [sys.executable, '-B', '-c', 'pass'], os.environ)
            else: r62_run(tmp_path/'nested', 'time.sleep(.03)')
    path = tmp_path/'exclusive'
    assisted = []
    try:
        if method == 'nested-owner':
            # Refusal alone is sufficient: no second launch was made.
            _, _, receipt = r62_run(path, 'time.sleep(.03)', guard=guard)
            assert not receipt['failed']
        else:
            with pytest.raises(RuntimeError, match='concurrent child launches'):
                r62_run(path, 'time.sleep(.03)', guard=guard)
            receipt = json.loads((path/'exit.json').read_bytes())
            assert receipt['failed']
        assert len(receipt['owned_processes']) == 1 and receipt['reaped'] and not receipt['survivors']
    finally:
        assisted = r62_fallback(path)
    assert not assisted and Q._ACTIVE_PARENT is None


@pytest.mark.parametrize('phase', ['initial', 'collect'])
@pytest.mark.parametrize('missing', ['identity', 'start'])
def test_r62_missing_identity_fails_and_retries_exact_discovery(tmp_path, monkeypatch, phase, missing):
    real_proc = Q.proc
    calls, injected = [], []
    def transient(pid):
        p = real_proc(pid)
        if p and pid != os.getpid():
            calls.append(pid)
            if not injected and len(calls) == (1 if phase == 'initial' else 3):
                injected.append(pid)
                return None if missing == 'identity' else {k: v for k, v in p.items() if k != 'start'}
        return p
    monkeypatch.setattr(Q, 'proc', transient)
    path = tmp_path/'missing'
    assisted = []
    try:
        with pytest.raises(RuntimeError, match='missing PID/start'):
            r62_run(path, 'time.sleep(.3)')
        receipt = json.loads((path/'exit.json').read_bytes())
        assert injected and receipt['failed'] and receipt['reaped'] and not receipt['survivors']
        assert not receipt['unresolved_pids'] and not receipt['pending_children']
        assert 'missing PID/start' in receipt['original_failure']['error']
        assert len(receipt['owned_processes']) == 1 and not receipt['cleanup_errors']
    finally:
        assisted = r62_fallback(path)
    assert not assisted


@pytest.mark.parametrize('missing', ['identity', 'start'])
def test_r62_persistent_missing_identity_never_signals_or_claims_reap(tmp_path, monkeypatch, missing):
    real_proc, real_init, real_signal = Q.proc, Q.OwnedWorker.__init__, Q.pidfd_signal
    instances, identities, signals = [], [], []
    def absent(pid):
        p = real_proc(pid)
        if p and pid != os.getpid():
            if not identities: identities.append(p)
            return None if missing == 'identity' else {k: v for k, v in p.items() if k != 'start'}
        return p
    def init(owned, *args, **kwargs):
        real_init(owned, *args, **kwargs)
        instances.append(owned)
    def signal(fd, sig):
        if sig: signals.append(sig)
        return real_signal(fd, sig)
    monkeypatch.setattr(Q, 'proc', absent)
    monkeypatch.setattr(Q.OwnedWorker, '__init__', init)
    monkeypatch.setattr(Q, 'pidfd_signal', signal)
    path = tmp_path/'unidentifiable'
    try:
        with pytest.raises(RuntimeError, match='missing PID/start'):
            r62_run(path, 'time.sleep(.15)')
        receipt = json.loads((path/'exit.json').read_bytes())
        assert not signals and receipt['failed'] and not receipt['reaped']
        assert receipt['unresolved_pids'] == [identities[0]['pid']]
        assert not receipt['owned_processes'] and receipt['source_process'] is None
        assert receipt['exitcode'] == 0 and not receipt['pending_children']
        assert Q._ACTIVE_PARENT is instances[0]
    finally:
        monkeypatch.setattr(Q, 'proc', real_proc)
        assisted = reap_test_identities(identities)
        for owned in instances:
            owned.child.poll()
            owned.release()
        (tmp_path/'explicit-cleanup.json').write_bytes(Q.encoded(dict(
            identities=identities, assisted=assisted, bounded_self_exit=True,
            candidate_claimed_reap=False)))
    assert not assisted


def test_r62_cleanup_only_discovery_latches_rejection_after_last_check(tmp_path, monkeypatch):
    # Synchronize a real fork strictly after the last successful ordinary check.
    gate, identity_path = tmp_path/'fork-now', tmp_path/'late.json'
    real_check, real_poll = Q.OwnedWorker.check, Q.Wire.poll
    done, triggered = [], []
    def poll(wire, *args):
        message = real_poll(wire, *args)
        if message and message['kind'] == 'done': done.append(True)
        return message
    def check(owned):
        real_check(owned)
        if done and not triggered:
            triggered.append(True)
            gate.touch()
            ready = Q.select.poll()
            ready.register(owned.pidfds[owned.child.pid], Q.select.POLLIN)
            assert ready.poll(1000), 'bounded fixture did not exit'
    monkeypatch.setattr(Q.Wire, 'poll', poll)
    monkeypatch.setattr(Q.OwnedWorker, 'check', check)
    tail = '''deadline=time.monotonic()+1
while not os.path.exists(sys.argv[2]) and time.monotonic()<deadline: time.sleep(.001)
pid=os.fork()
if pid == 0:
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[3],'x') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
 time.sleep(3);os._exit(0)
os._exit(0)
'''
    path = tmp_path/'late'
    assisted = []
    try:
        with pytest.raises(RuntimeError, match='extra process'):
            r62_run(path, tail, args=[gate, identity_path])
        receipt = json.loads((path/'exit.json').read_bytes())
        assert triggered and receipt['failed'] and receipt['reaped'] and not receipt['survivors']
        assert len(receipt['owned_processes']) == 2 and not receipt['cleanup_errors']
        assert 'extra process' in receipt['original_failure']['error']
    finally:
        assisted = r62_fallback(path, [identity_path])
    assert not assisted


def test_r62_descendant_forks_during_drain_keeps_complete_set(tmp_path, monkeypatch):
    import time
    gate, child_path, grand_path = [tmp_path/name for name in ('drain-now', 'child.json', 'grand.json')]
    tail = '''pid=os.fork()
if pid == 0:
 fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
 with open(sys.argv[3],'x') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
 deadline=time.monotonic()+1
 while not os.path.exists(sys.argv[2]) and time.monotonic()<deadline: time.sleep(.001)
 pid=os.fork()
 if pid == 0:
  os.setsid()
  fields=open('/proc/self/stat').read().rsplit(')',1)[1].split()
  with open(sys.argv[4],'x') as f: json.dump(dict(pid=os.getpid(),start=int(fields[19])),f)
  time.sleep(3);os._exit(0)
 os._exit(0)
time.sleep(3)
'''
    signal_exact = Q.OwnedWorker.signal_exact
    triggered = []
    def signal(owned, pid, sig):
        if not triggered:
            triggered.append(True)
            gate.touch()
            until = time.monotonic()+1
            while not grand_path.exists():
                assert time.monotonic() < until
                time.sleep(.001)
        return signal_exact(owned, pid, sig)
    monkeypatch.setattr(Q.OwnedWorker, 'signal_exact', signal)
    path = tmp_path/'drain'
    assisted = []
    try:
        with pytest.raises(RuntimeError, match='extra process'):
            r62_run(path, tail, args=[gate, child_path, grand_path])
        receipt = json.loads((path/'exit.json').read_bytes())
        assert len(receipt['owned_processes']) == 3
        assert receipt['failed'] and receipt['reaped'] and not receipt['survivors']
        assert not receipt['cleanup_errors'] and not receipt['pending_children']
        assert 'extra process' in receipt['original_failure']['error']
    finally:
        assisted = r62_fallback(path, [child_path, grand_path])
    assert not assisted


def test_r62_cleanup_budget_is_not_reset_and_original_failure_survives(tmp_path, monkeypatch):
    # Deliberately prevent candidate signals. This negative control requires
    # exact independent assistance and cannot count as candidate cleanup.
    real_time = Q.time.monotonic
    elapsed, calls, instances = [0.], [], []
    monkeypatch.setattr(Q.time, 'monotonic', lambda: real_time()+elapsed[0])
    def blocked(owned, pid, sig):
        if not instances: instances.append(owned)
        calls.append(pid)
        elapsed[0] += 3
        raise OSError(5, 'injected persistent signal failure')
    monkeypatch.setattr(Q.OwnedWorker, 'signal_exact', blocked)
    def guard(): raise RuntimeError('original monitor refusal')
    path = tmp_path/'bounded'
    assisted = []
    try:
        with pytest.raises(RuntimeError, match='original monitor refusal'):
            r62_run(path, 'time.sleep(3)', guard=guard)
        receipt = json.loads((path/'exit.json').read_bytes())
        assert len(calls) == 2 and receipt['failed'] and not receipt['reaped']
        assert receipt['survivors'] and 'persistent signal failure' in str(receipt['cleanup_errors'])
        assert 'original monitor refusal' in receipt['original_failure']['error']
        assert Q._ACTIVE_PARENT is instances[0], 'failed drain released exclusivity'
    finally:
        monkeypatch.setattr(Q.time, 'monotonic', real_time)
        assisted = r62_fallback(path)
        for owned in instances:
            owned.child.poll()
            owned.release()
    assert assisted, 'negative control did not exercise independent assistance'


if __name__ == '__main__':
    assert sys.argv[1] == '--mock-worker'
    mock_worker(sys.argv[2], int(sys.argv[3]))
