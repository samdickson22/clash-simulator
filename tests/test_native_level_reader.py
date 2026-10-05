"""The diagnostic level reader must reject stale or unbound native memory."""
import copy
import importlib
import struct
from pathlib import Path

import pytest


@pytest.mark.parametrize('batched', [False, True, 'persistent'])
@pytest.mark.parametrize('num_bodies', [1, 12])
@pytest.mark.parametrize('fault', [None, 'build', 'backlink', 'identity', 'range', 'race', 'short', 'batch_short', 'batch_race', 'batch_oversized', 'batch_persistent', 'single_short', 'single_race', 'single_late_race', 'single_manager', 'single_pid', 'single_oversized'])
def test_level_reader_rejects_unverified_sources(monkeypatch, fault, num_bodies, batched):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    persistent = batched == 'persistent'
    batched = bool(batched)
    if persistent:
        class FixtureTransport:
            def __init__(self, adb, serial): self.adb, self.serial = adb, serial
            def __enter__(self): return self
            def __exit__(self, *exc): pass
            def pid(self):
                return int(reader.subprocess.check_output([str(self.adb), '-s', self.serial, 'shell', 'pidof', 'nullsroyale.rel.free']))
            def read(self, pid, ranges):
                commands = [f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null' for address, size in ranges]
                return reader.subprocess.check_output([str(self.adb), '-s', self.serial, 'exec-out', '\n'.join(commands)])
        monkeypatch.setattr(reader, '_PersistentAdbShell', FixtureTransport)
    batch_fault = batched and num_bodies > 1 and fault in {'batch_short', 'batch_race', 'batch_oversized', 'batch_persistent'}
    data = bytearray(0x10000)
    def write(address, fmt, *values):
        struct.pack_into(fmt, data, address, *values)
    write(0x1000+0xa8, '<Q', 0x2000)
    write(0x2000+0xe0, '<Q', 0x3000)
    write(0x3000+0x10, '<Q', 0x4000)
    write(0x4000+8, '<Q', 0x5000)
    write(0x4000+0x10, '<ii', num_bodies, num_bodies)
    objects = []
    for i in range(num_bodies):
        address = 0x6000 + i * 0x200
        components, hp_component = 0x9000 + i * 0x20, 0xb000 + i * 0x20
        identity = 5000006 + i
        write(0x5000 + i * 8, '<Q', address)
        write(address+8, '<I', 7 if fault == 'identity' and i == 0 else identity)
        write(address+0x78, '<i', 0)
        write(address+0xac, '<i', 26000000)
        write(address+0x18, '<Q', components)
        write(address+0x20, '<i', 3)
        write(components+16, '<Q', hp_component)
        write(hp_component+8, '<Q', address+4 if fault == 'backlink' and i == 0 else address)
        write(address+0x120, '<i', 127 if fault == 'range' and i == 0 else 10)
        objects.append({'nativeObjectId': identity, 'owner': 0, 'cardId': 26000000, 'hp': 1766})
    before = {'tick': 20, 'generation': 1, 'stateEpoch': 1, 'truncated': False,
              'returned': num_bodies, 'count': num_bodies, 'objects': objects}
    reads = 0
    status_reads = 0
    pid_reads = 0
    def request(port, command):
        nonlocal reads, status_reads
        if command == 'attest':
            return {'attestation': reader.EXPECTED | ({'libg_sha256': 'wrong'} if fault == 'build' else {})}
        if command == 'status':
            status_reads += 1
            manager = '0x1100' if fault == 'single_manager' and status_reads > 1 else '0x1000'
            return {'paused': True, 'ready': True, 'manager': manager}
        assert command == 'observe'
        reads += 1
        result = copy.deepcopy(before)
        if (
            ((fault in {'race', 'single_race'} or (batch_fault and fault == 'batch_race')) and reads > 1)
            or (fault == 'single_late_race' and reads > 2)
        ):
            result['objects'][0]['hp'] -= 1
        return result
    calls = []
    def output(args):
        nonlocal pid_reads
        if 'pidof' in args:
            pid_reads += 1
            if fault == 'single_pid' and pid_reads > 1:
                return b'124\n'
            return b'123\n'
        calls.append(args)
        chunks = []
        for command in args[-1].splitlines():
            fields = dict(part.split('=',1) for part in command.split() if '=' in part)
            start, count = int(fields['skip']), int(fields['count'])
            assert 0 < count <= 4096
            chunks.append(bytes(data[start:start+count]))
        result = b''.join(chunks)
        if fault and fault.startswith('single_') and len(calls) == 1:
            return result + b'x' if fault == 'single_oversized' else b'x'
        if batch_fault and '\n' in args[-1]:
            return result + b'x' if fault == 'batch_oversized' else result[:-1]
        if batch_fault and fault == 'batch_persistent' and start >= 0x6000:
            return result[:-1]
        return result[:-1] if fault == 'short' else result
    monkeypatch.setattr(reader, 'request', request)
    monkeypatch.setattr(reader.subprocess, 'check_output', output)
    should_fail = bool(fault) and fault not in {'batch_short', 'single_short'}
    if fault and fault.startswith('batch_') and not batch_fault:
        should_fail = False
    if should_fail:
        with pytest.raises(ValueError):
            reader.read_levels(Path('/unused-adb'), batched=batched, persistent=persistent)
    else:
        result = reader.read_levels(Path('/unused-adb'), batched=batched, persistent=persistent)
        assert result['levels'] == {5000006 + i: 11 for i in range(num_bodies)}
        if fault == 'single_short':
            assert result['transport_recoveries'] == [{
                'kind': 'short-single-retry', 'address': '0x10a8',
                'expected_bytes': 8, 'received_bytes': 1,
            }]
            assert calls[0] == calls[1]
        elif batch_fault:
            assert result['transport_recoveries']
            assert all(r['received_bytes'] == r['expected_bytes'] - 1 for r in result['transport_recoveries'])
        else:
            assert result['transport_recoveries'] == []
        if batched and not batch_fault and fault != 'single_short':
            assert len(calls) <= 10
        elif not batched and num_bodies > 1:
            assert len(calls) > 40


def test_persistent_shell_frames_binary_bytes_and_reuses_one_process(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    fake_adb = tmp_path / 'fake-adb'
    fake_adb.write_text('#!/bin/sh\nexec /bin/sh\n')
    fake_adb.chmod(0o755)
    with reader._PersistentAdbShell(fake_adb, 'fixture') as shell:
        process = shell.process
        actual = shell._exchange("printf '\\000\\377\\n__CLASHER_READ_1__\\n'", max_bytes=64)
        assert actual == b'\x00\xff\n__CLASHER_READ_1__\n'
        assert shell._exchange("printf second", max_bytes=6) == b'second'
        assert shell.process is process and process.poll() is None
    assert process.poll() is not None


@pytest.mark.parametrize('fault', ['oversized', 'timeout', 'bad_encoding', 'closed'])
def test_persistent_shell_fails_closed_and_reaps_process(monkeypatch, tmp_path, fault):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    fake_adb = tmp_path / 'fake-adb'
    script = '#!/bin/sh\nexec /bin/sh\n'
    if fault == 'bad_encoding':
        script = "#!/bin/sh\nprintf '!\\n__CLASHER_READ_1__\\n'\ncat >/dev/null\n"
    elif fault == 'closed':
        script = '#!/bin/sh\nexit 0\n'
    fake_adb.write_text(script)
    fake_adb.chmod(0o755)
    with pytest.raises((ValueError, TimeoutError, BrokenPipeError)):
        with reader._PersistentAdbShell(fake_adb, 'fixture', timeout=.03) as shell:
            process = shell.process
            command = 'sleep .2; printf x' if fault == 'timeout' else 'printf oversized'
            shell._exchange(command, max_bytes=1)
    assert process.poll() is not None


@pytest.fixture
def session_runtime(monkeypatch):
    """One mutable paused native frame, with an independently owned memory image."""
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    data = bytearray(0x10000)
    for address, fmt, values in [
        (0x10a8, '<Q', (0x2000,)), (0x20e0, '<Q', (0x3000,)),
        (0x3010, '<Q', (0x4000,)), (0x4008, '<Q', (0x5000,)),
        (0x4010, '<ii', (1, 1)), (0x5000, '<Q', (0x6000,)),
        (0x6008, '<I', (5000006,)), (0x6078, '<i', (0,)),
        (0x60ac, '<i', (26000000,)), (0x6018, '<Q', (0x9000,)),
        (0x6020, '<i', (3,)), (0x9010, '<Q', (0xb000,)),
        (0xb008, '<Q', (0x6000,)), (0x6120, '<i', (10,)),
    ]:
        struct.pack_into(fmt, data, address, *values)
    runtime = SimpleNamespace(
        status={'ready': True, 'paused': True, 'configured': True,
                'contentReady': True, 'contentPublished': True, 'mode': 'headless',
                'manager': '0x1000', 'contentRoot': '0x100', 'contentContext': '0x200',
                'configRoot': '0x300', 'configLocationId': 1,
                'generation': 1, 'stateEpoch': 1, 'configRevision': 1, 'tick': 20},
        ordinary={'tick': 20, 'generation': 1, 'stateEpoch': 1,
                  'truncated': False, 'count': 1, 'returned': 1,
                  'objects': [{'nativeObjectId': 5000006, 'owner': 0,
                               'cardId': 26000000, 'hp': 1766}]},
        attestation={'ok': True, 'attestation': {**reader.EXPECTED, 'content_version': 'fixture'}},
        pid=123, start_ticks=99, calls=[], transports=[], data=data,
        memory_reads=0, mutate_during_read=None, fail_cleanup=False,
    )

    class Transport:
        def __init__(self, adb, serial):
            self.closed = False
            runtime.transports.append(self)
        def __enter__(self): return self
        def __exit__(self, *exc):
            self.closed = True
            if runtime.fail_cleanup: raise OSError('cleanup failed')
        def pid(self): return runtime.pid
        def process_start_ticks(self, pid): return runtime.start_ticks
        def read(self, pid, ranges):
            runtime.memory_reads += 1
            if runtime.mutate_during_read is not None:
                mutate, runtime.mutate_during_read = runtime.mutate_during_read, None
                mutate(runtime)
            return b''.join(bytes(runtime.data[address:address+size]) for address, size in ranges)

    def request(port, command):
        runtime.calls.append(command)
        return copy.deepcopy({'attest': runtime.attestation, 'status': runtime.status,
                              'observe': runtime.ordinary}[command])
    monkeypatch.setattr(reader, '_PersistentAdbShell', Transport)
    monkeypatch.setattr(reader, 'request', request)
    pin = reader._canonical_sha(runtime.attestation)
    return reader, runtime, pin


def test_verified_session_uses_boundary_attestation_and_fresh_frame_values(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with session:
        first = session.read_levels()
        assert first['verified_session']['pending_final_verification'] is True
        assert first['levels'] == {5000006: 11}
        assert runtime.calls.count('attest') == 1
        first['attestation']['probe_sha256'] = 'caller mutation'
        runtime.status['tick'] += 5
        runtime.ordinary['tick'] += 5
        struct.pack_into('<i', runtime.data, 0x6120, 11)
        second = session.read_levels()
        assert second['levels'] == {5000006: 12}
        assert second['attestation']['probe_sha256'] == reader.EXPECTED['probe_sha256']
        assert second['verified_session']['read_index'] == 2
    proof = session.provenance
    assert proof['status'] == 'verified'
    assert proof['reads_completed'] == 2
    assert proof['start_attestation_sha256'] == proof['end_attestation_sha256'] == pin
    assert runtime.calls.count('attest') == 2
    assert len(runtime.transports) == 1 and runtime.transports[0].closed
    proof['runtime_identity']['pid'] = 0
    assert session.provenance['runtime_identity']['pid'] == 123
    with pytest.raises(ValueError, match='cannot be reentered'): session.__enter__()
    with pytest.raises(ValueError, match='not open'): session.read_levels()


@pytest.mark.parametrize('field', [
    'pid', 'start_ticks', 'manager', 'generation', 'stateEpoch', 'configRevision',
    'contentRoot', 'contentContext', 'configRoot', 'configLocationId', 'mode',
    'ready', 'paused', 'configured', 'contentReady', 'contentPublished',
])
def test_verified_session_rejects_each_runtime_identity_change(session_runtime, field):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError):
        with session:
            if field in ('pid', 'start_ticks'):
                setattr(runtime, field, getattr(runtime, field) + 1)
            elif field == 'mode': runtime.status[field] = 'native-render'
            elif type(runtime.status[field]) is bool: runtime.status[field] = False
            elif type(runtime.status[field]) is int: runtime.status[field] += 1
            else: runtime.status[field] = '0x888'
            session.read_levels()
    assert session.provenance['status'] == 'failed'
    assert runtime.memory_reads == 0
    assert runtime.transports[0].closed
    assert runtime.calls.count('attest') == 2


def test_verified_session_detects_process_change_during_read(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError):
        with session:
            runtime.mutate_during_read = lambda state: setattr(state, 'pid', 124)
            session.read_levels()
    assert session.provenance['status'] == 'failed'
    assert session.provenance['reads_completed'] == 0
    assert runtime.transports[0].closed


@pytest.mark.parametrize('boundary', ['enter', 'close'])
def test_verified_session_rejects_changed_full_attestation_and_closes(session_runtime, boundary):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    if boundary == 'enter': runtime.attestation['attestation']['content_version'] = 'changed'
    with pytest.raises(ValueError, match='attestation|closing verification'):
        with session:
            session.read_levels()
            if boundary == 'close': runtime.attestation['attestation']['content_version'] = 'changed'
    assert session.provenance['status'] == 'failed'
    assert runtime.transports[0].closed
    if boundary == 'close':
        assert session.provenance['end_attestation_sha256'] != pin
        assert session.provenance['end_attestation_sha256'] is not None


def test_caught_session_read_failure_still_invalidates_entire_branch(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError, match='invalidated before close'):
        with session:
            runtime.pid = 124
            with pytest.raises(ValueError): session.read_levels()
            runtime.pid = 123
            with pytest.raises(ValueError, match='invalidated'): session.read_levels()
    assert runtime.calls.count('attest') == 2
    assert session.provenance['status'] == 'failed'


def test_session_checks_close_even_after_caller_error(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(RuntimeError, match='caller failed'):
        with session:
            session.read_levels()
            raise RuntimeError('caller failed')
    assert runtime.calls.count('attest') == 2
    assert session.provenance['status'] == 'failed'
    assert runtime.transports[0].closed


def test_session_cleanup_failure_cannot_publish_verified_status(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(OSError, match='cleanup failed'):
        with session: runtime.fail_cleanup = True
    assert session.provenance['status'] == 'failed'


def test_standalone_reader_still_attests_every_read(session_runtime):
    reader, runtime, _ = session_runtime
    for _ in range(2): reader.read_levels(Path('/fixture'), persistent=True)
    assert runtime.calls.count('attest') == 2
    assert len(runtime.transports) == 2
    assert all(transport.closed for transport in runtime.transports)


def test_interrupted_boundary_verification_never_marks_session_verified(session_runtime, monkeypatch):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    def interrupt(): raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        with session:
            monkeypatch.setattr(session, '_close_attestation', interrupt)
    assert session.provenance['status'] == 'failed'
    assert runtime.transports[0].closed


def test_process_start_identity_parses_parentheses_and_spaces(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    shell = reader._PersistentAdbShell(Path('/fixture'), 'fixture')
    stat = b'123 (a name with ) parentheses) S ' + b'0 ' * 18 + b'999 0 0\n'
    monkeypatch.setattr(shell, '_exchange', lambda *a, **kw: stat)
    assert shell.process_start_ticks(123) == 999
    with pytest.raises(ValueError, match='process stat'): shell.process_start_ticks(124)


def test_session_source_change_fails_before_verified_close(session_runtime):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError, match='closing verification'):
        with session:
            session._reader_sha256 = '0' * 64
    assert session.provenance['status'] == 'failed'
    assert runtime.calls.count('attest') == 2
    assert runtime.transports[0].closed


@pytest.mark.parametrize('pin', [None, 'bad', 'A' * 64])
def test_verified_session_requires_explicit_valid_pin_without_native_calls(session_runtime, pin):
    reader, runtime, _ = session_runtime
    with pytest.raises(ValueError, match='pinned full attestation'):
        reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    assert runtime.calls == [] and runtime.transports == []


def test_failed_session_enter_cannot_close_again_or_issue_more_queries(session_runtime):
    reader, runtime, pin = session_runtime
    runtime.attestation['attestation']['content_version'] = 'changed'
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError, match='attestation'): session.__enter__()
    calls = list(runtime.calls)
    with pytest.raises(ValueError, match='cannot close'): session.__exit__(None, None, None)
    assert runtime.calls == calls
    assert runtime.transports[0].closed


def _session_probe(runtime, reader):
    sent = []
    def probe(command):
        sent.append(command)
        return reader.request(0, command)
    return probe, sent


def test_session_probe_routes_every_native_command_through_caller_transport(session_runtime, monkeypatch):
    reader, runtime, pin = session_runtime
    probe, sent = _session_probe(runtime, reader)
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin, probe=probe)
    with session:
        assert session.read_levels()['levels'] == {5000006: 11}
    assert session.provenance['status'] == 'verified'
    assert sent == runtime.calls and sent.count('attest') == 2


def test_supplied_frame_skips_only_the_opening_observe(session_runtime):
    reader, runtime, pin = session_runtime
    probe, sent = _session_probe(runtime, reader)
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin, probe=probe)
    with session:
        start = len(sent)
        supplied = copy.deepcopy(runtime.ordinary)
        result = session.read_levels(ordinary=supplied)
        assert result['levels'] == {5000006: 11}
        assert result['ordinary'] == supplied and result['ordinary'] is not supplied
        assert sent[start:] == ['status', 'observe', 'status']
        start = len(sent)
        session.read_levels()
        assert sent[start:] == ['status', 'observe', 'observe', 'status']
    assert session.provenance['status'] == 'verified'


@pytest.mark.parametrize('change', ['during_read', 'stale_supplied', 'status_tick'])
def test_supplied_frame_still_fails_closed_when_frame_differs(session_runtime, change):
    reader, runtime, pin = session_runtime
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin)
    with pytest.raises(ValueError):
        with session:
            supplied = copy.deepcopy(runtime.ordinary)
            if change == 'during_read':
                runtime.mutate_during_read = lambda state: state.ordinary['objects'][0].update(hp=1)
            elif change == 'stale_supplied':
                supplied['objects'][0]['hp'] = 1
            else:
                supplied['tick'] = 25
            session.read_levels(ordinary=supplied)
    assert session.provenance['status'] == 'failed'


def test_standalone_reader_rejects_supplied_frame(session_runtime):
    reader, _runtime, _ = session_runtime
    with pytest.raises(ValueError, match='verified session'):
        reader._read_levels(Path('/fixture'), port=1, serial='x', batched=True, ordinary={})


def test_combined_identity_reads_check_same_values_in_one_round_trip(session_runtime, monkeypatch):
    reader, runtime, pin = session_runtime
    combined = []
    def pid_and_start_ticks(self):
        combined.append(1)
        return runtime.pid, runtime.start_ticks
    monkeypatch.setattr(reader._PersistentAdbShell, 'pid_and_start_ticks', pid_and_start_ticks, raising=False)
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin,
                                               combined_identity_reads=True)
    with session:
        session.read_levels()
        assert len(combined) == 2
    assert session.provenance['status'] == 'verified'
    session = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin,
                                               combined_identity_reads=True)
    with pytest.raises(ValueError):
        with session:
            runtime.mutate_during_read = lambda state: setattr(state, 'start_ticks', 100)
            session.read_levels()
    assert session.provenance['status'] == 'failed'


def test_combined_process_identity_parsing(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
    shell = reader._PersistentAdbShell(Path('/fixture'), 'fixture')
    stat = b'123 (a name with ) parentheses) S ' + b'0 ' * 18 + b'999 0 0\n'
    monkeypatch.setattr(shell, '_exchange', lambda *a, **kw: b'123\n' + stat)
    assert shell.pid_and_start_ticks() == (123, 999)
    monkeypatch.setattr(shell, '_exchange', lambda *a, **kw: b'124\n' + stat)
    with pytest.raises(ValueError, match='process stat'): shell.pid_and_start_ticks()
    monkeypatch.setattr(shell, '_exchange', lambda *a, **kw: b'123 456\n' + stat)
    with pytest.raises(ValueError): shell.pid_and_start_ticks()
    monkeypatch.setattr(shell, '_exchange', lambda *a, **kw: b'')
    with pytest.raises(ValueError): shell.pid_and_start_ticks()
