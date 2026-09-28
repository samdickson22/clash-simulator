"""The diagnostic level reader must reject stale or unbound native memory."""
import copy
import importlib
import struct
from pathlib import Path

import pytest


@pytest.mark.parametrize('batched', [False, True])
@pytest.mark.parametrize('num_bodies', [1, 12])
@pytest.mark.parametrize('fault', [None, 'build', 'backlink', 'identity', 'range', 'race', 'short', 'batch_short', 'batch_race', 'batch_oversized', 'batch_persistent', 'single_short', 'single_race', 'single_late_race', 'single_manager', 'single_pid', 'single_oversized'])
def test_level_reader_rejects_unverified_sources(monkeypatch, fault, num_bodies, batched):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / 'scripts'))
    reader = importlib.import_module('read_native_public_levels')
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
            reader.read_levels(Path('/unused-adb'), batched=batched)
    else:
        result = reader.read_levels(Path('/unused-adb'), batched=batched)
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
