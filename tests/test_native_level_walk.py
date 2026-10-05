"""Batched (one helper process per frame) and Phase B in-probe level readers.

Every test uses a mocked device: a memory image, a fake framed ADB shell and a
fake probe. No emulator or adb is touched. The legacy host walk is the
reference; both new readers must return identical levels and fail closed on
every integrity violation the legacy reader rejects, plus their own.
"""
import copy
import hashlib
import importlib
import re
import shutil
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
HELPER_SOURCE = ROOT / 'tools/native_level_walk/clasher_level_walk.c'
PID, START_TICKS = 123, 99
DEVICE_HELPER = '/data/local/tmp/clasher-level-walk-v1'
COMPONENTS, HP_COMPONENTS = 0xe000, 0xf000


def load_reader(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return importlib.import_module('read_native_public_levels')


def stat_line(pid=PID, start_ticks=START_TICKS, comm='nulls (royale) x'):
    middle = ' '.join(str(i) for i in range(1, 19))
    return f'{pid} ({comm}) S {middle} {start_ticks} 0 0\n'.encode()


def build_image(num_bodies=3, non_bodies=2):
    """Object graph at fixed addresses; returns (data, ordinary objects)."""
    data = bytearray(0x10000)

    def write(address, fmt, *values):
        struct.pack_into(fmt, data, address, *values)

    count = num_bodies + non_bodies
    write(0x1000 + 0xa8, '<Q', 0x2000)
    write(0x2000 + 0xe0, '<Q', 0x3000)
    write(0x3000 + 0x10, '<Q', 0x4000)
    write(0x4000 + 8, '<Q', 0x5000)
    write(0x4000 + 0x10, '<ii', count + 4, count)
    objects = []
    order = list(range(0, count, 2)) + list(range(1, count, 2))
    body_slots = set(order[:num_bodies])
    for i in range(count):
        address = 0x6000 + i * 0x200
        body = i in body_slots
        identity = 5000006 + i
        write(0x5000 + i * 8, '<Q', address)
        write(address + 8, '<I', identity)
        write(address + 0x78, '<i', i % 2)
        write(address + 0xac, '<i', 26000000 + i)
        if body:
            components, hp_component = COMPONENTS + i * 0x20, HP_COMPONENTS + i * 0x10
            write(address + 0x18, '<Q', components)
            write(address + 0x20, '<i', 3 + i % 4)
            write(components + 16, '<Q', hp_component)
            write(hp_component + 8, '<Q', address)
            write(address + 0x120, '<i', 8 + i % 7)
        objects.append({'nativeObjectId': identity, 'owner': i % 2, 'cardId': 26000000 + i,
                        'hp': 1000 + i if body else None})
    assert sum(o['hp'] is not None for o in objects) == num_bodies
    return data, objects


def expected_levels(data, objects):
    levels = {}
    for i, obj in enumerate(objects):
        if obj['hp'] is not None:
            levels[obj['nativeObjectId']] = struct.unpack_from('<i', data, 0x6000 + i * 0x200 + 0x120)[0] + 1
    return levels


def emulate_helper(data, pid, manager, body_ids, stat_before, stat_after=None, *, short=None):
    """Byte-exact Python model of clasher_level_walk.c (checked against the C build)."""
    out = bytearray(b'CLWALK01' + struct.pack('<II', pid, len(body_ids)))
    out += struct.pack('<I', len(stat_before)) + stat_before
    records = 0

    def read(address, size):
        nonlocal records
        got = bytes(data[address:address + size]) if address < len(data) else b''
        if short is not None and short(address, size):
            got = got[:-1]
        out.extend(struct.pack('<BQII', 1, address, size, len(got)) + got)
        records += 1
        return got

    def finish(reason):
        out.extend(struct.pack('<BII', 2, records, reason))
        after = stat_before if stat_after is None else stat_after
        out.extend(struct.pack('<I', len(after)) + after + b'CLWEND01')
        return bytes(out)

    single = lambda a, s: 0 < a < 1 << 56 and 0 < s <= 4096
    batch = lambda a, s: single(a, s) and a + s <= 1 << 56
    address, pointer = manager + 0xa8, 0
    for hop in range(4):
        if not single(address, 8):
            return finish(2)
        word = read(address, 8)
        if len(word) != 8:
            return finish(1)
        pointer = struct.unpack('<Q', word)[0]
        if hop < 3:
            address = pointer + (0xe0, 0x10, 0x08)[hop]
    object_manager, vector = address - 8, pointer
    word = read(object_manager + 0x10, 8)
    if len(word) != 8:
        return finish(1)
    capacity, count = struct.unpack('<ii', word)
    if not 0 < count <= min(capacity, 128):
        return finish(3)
    raw = read(vector, count * 8)
    if len(raw) != count * 8:
        return finish(1)
    objects = struct.unpack(f'<{count}Q', raw)
    if not all(batch(o, 0xb0) for o in objects):
        return finish(2)
    headers = []
    for o in objects:
        header = read(o, 0xb0)
        if len(header) != 0xb0:
            return finish(1)
        headers.append(header)
    bodies = []
    for o, header in zip(objects, headers, strict=True):
        if struct.unpack_from('<I', header, 8)[0] not in body_ids:
            continue
        if not 3 <= struct.unpack_from('<i', header, 0x20)[0] <= 64:
            return finish(4)
        bodies.append((o, struct.unpack_from('<Q', header, 0x18)[0]))
    if not all(batch(c + 16, 8) for _, c in bodies):
        return finish(2)
    hp = []
    for _, c in bodies:
        word = read(c + 16, 8)
        if len(word) != 8:
            return finish(1)
        hp.append(struct.unpack('<Q', word)[0])
    if not all(batch(h + 8, 8) for h in hp):
        return finish(2)
    valid = True
    for (o, _), h in zip(bodies, hp, strict=True):
        word = read(h + 8, 8)
        if len(word) != 8:
            return finish(1)
        valid &= struct.unpack('<Q', word)[0] == o
    if not valid:
        return finish(5)
    if not all(batch(o + 0x120, 4) for o, _ in bodies):
        return finish(2)
    for o, _ in bodies:
        if len(read(o + 0x120, 4)) != 4:
            return finish(1)
    return finish(0)


def probe_levels_response(data, ordinary, *, generation=1, epoch=1, tick=20):
    """Model of the Phase B probe's observe-levels over the same memory image."""
    count = struct.unpack_from('<i', data, 0x4014)[0]
    capacity = struct.unpack_from('<i', data, 0x4010)[0]
    objects = []
    for i, obj in enumerate(ordinary['objects']):
        address = 0x6000 + i * 0x200
        body = obj['hp'] is not None
        entry = {'slot': i, 'nativeObjectId': struct.unpack_from('<I', data, address + 8)[0],
                 'owner': struct.unpack_from('<i', data, address + 0x78)[0],
                 'cardId': struct.unpack_from('<i', data, address + 0xac)[0], 'hasHitpoints': body,
                 'componentCapacity': None, 'componentCount': None, 'hpComponentBacklink': None,
                 'levelRaw': None}
        if body:
            components = struct.unpack_from('<Q', data, address + 0x18)[0]
            hp_component = struct.unpack_from('<Q', data, components + 16)[0]
            entry.update(componentCapacity=struct.unpack_from('<i', data, address + 0x20)[0],
                         componentCount=3,
                         hpComponentBacklink=struct.unpack_from('<Q', data, hp_component + 8)[0] == address,
                         levelRaw=struct.unpack_from('<i', data, address + 0x120)[0])
        objects.append(entry)
    return {'ok': True, 'schema': 'native-public-levels.v1', 'generation': generation,
            'stateEpoch': epoch, 'tick': tick, 'count': count, 'capacity': capacity,
            'levelFieldOffset': 0x120, 'layoutsValid': True,
            'process': {'pid': PID, 'startTicks': START_TICKS},
            'objects': objects, 'returned': count, 'truncated': False}


def make_device(monkeypatch):
    """Mocked device: framed shell (real parsing code) plus probe."""
    reader = load_reader(monkeypatch)
    data, objects = build_image()
    helper_sha = reader.LEVEL_WALK_HELPER_SHA256
    rt = SimpleNamespace(
        reader=reader, data=data,
        status={'ready': True, 'paused': True, 'configured': True, 'contentReady': True,
                'contentPublished': True, 'mode': 'headless', 'manager': '0x1000',
                'contentRoot': '0x100', 'contentContext': '0x200', 'configRoot': '0x300',
                'configLocationId': 1, 'generation': 1, 'stateEpoch': 1, 'configRevision': 1,
                'tick': 20},
        ordinary={'tick': 20, 'generation': 1, 'stateEpoch': 1, 'truncated': False,
                  'count': len(objects), 'returned': len(objects), 'objects': objects},
        build=dict(reader.EXPECTED), calls=[], exchanges=[], pid=PID, start_ticks=START_TICKS,
        helper_sha={'open': helper_sha, 'frame': helper_sha, 'close': helper_sha},
        helper_checks=0, walk_hook=None, levels_hook=None, observe_hook=None, short=None,
    )

    class Shell(reader._PersistentAdbShell):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def _exchange(self, command, *, max_bytes):
            rt.exchanges.append(command)
            stat = stat_line(rt.pid, rt.start_ticks)
            if command == 'pidof nullsroyale.rel.free':
                return f'{rt.pid}\n'.encode()
            if command.startswith('p=$(pidof'):
                return f'{rt.pid}\n'.encode() + stat
            if command.startswith('cat /proc/'):
                return stat
            if command.startswith('sha256sum '):
                rt.helper_checks += 1
                key = 'open' if rt.helper_checks == 1 else 'close'
                return f'{rt.helper_sha[key]}  {command.split()[1]}\n'.encode()
            match = re.fullmatch(r'H=(\S+) && sha256sum "\$H" && p=\$\(pidof nullsroyale\.rel\.free\) && '
                                 r'"\$H" "\$p" (\d+)((?: \d+)*) && pidof nullsroyale\.rel\.free', command)
            if match:
                path, manager, ids = match.group(1), int(match.group(2)), match.group(3).split()
                transcript = emulate_helper(rt.data, rt.pid, manager, {int(i) for i in ids}, stat,
                                            short=rt.short)
                raw = f'{rt.helper_sha["frame"]}  {path}\n'.encode() + transcript + f'{rt.pid}\n'.encode()
                return raw if rt.walk_hook is None else rt.walk_hook(raw)
            if 'dd if=/proc/' in command:
                chunks = []
                for part in command.split('; '):
                    fields = dict(p.split('=', 1) for p in part.split() if '=' in p)
                    start, count = int(fields['skip']), int(fields['count'])
                    chunks.append(bytes(rt.data[start:start + count]))
                return b''.join(chunks)
            raise AssertionError(f'unexpected device command {command!r}')

    observes = {'n': 0}

    def request(port, command):
        rt.calls.append(command)
        if command == 'attest':
            return {'ok': True, 'attestation': {**rt.build, 'content_version': 'fixture'}}
        if command == 'status':
            return copy.deepcopy(rt.status)
        if command == 'observe':
            observes['n'] += 1
            frame = copy.deepcopy(rt.ordinary)
            return frame if rt.observe_hook is None else rt.observe_hook(frame, observes['n'])
        if command == 'observe-levels':
            response = probe_levels_response(rt.data, rt.ordinary)
            response['process'] = {'pid': rt.pid, 'startTicks': rt.start_ticks}
            return response if rt.levels_hook is None else rt.levels_hook(response)
        raise AssertionError(f'unexpected probe command {command!r}')

    monkeypatch.setattr(reader, '_PersistentAdbShell', Shell)
    monkeypatch.setattr(reader, 'request', request)
    rt.pin = lambda build=None: reader._canonical_sha(
        {'ok': True, 'attestation': {**(rt.build if build is None else build), 'content_version': 'fixture'}})
    return rt


@pytest.fixture
def device(monkeypatch):
    return make_device(monkeypatch)


def session(rt, level_reader, **kwargs):
    reader = rt.reader
    if level_reader == 'probe':
        rt.build = dict(reader.EXPECTED_PHASEB)
        kwargs.setdefault('expected_build', reader.EXPECTED_PHASEB)
    return reader.VerifiedNativeReadSession(
        Path('/fixture'), expected_attestation_sha256=rt.pin(), level_reader=level_reader,
        combined_identity_reads=kwargs.pop('combined', True), **kwargs)


# ---------------------------------------------------------------- parity

@pytest.mark.parametrize('num_bodies,non_bodies', [(1, 0), (3, 2), (12, 5), (40, 20)])
@pytest.mark.parametrize('combined', [False, True])
def test_all_readers_return_identical_levels(monkeypatch, num_bodies, non_bodies, combined):
    results = {}
    for level_reader in ('legacy', 'batched', 'probe'):
        rt = make_device(monkeypatch)
        rt.data, objects = build_image(num_bodies, non_bodies)
        rt.ordinary.update(objects=objects, count=len(objects), returned=len(objects))
        s = session(rt, level_reader, combined=combined)
        with s:
            first = s.read_levels(ordinary=copy.deepcopy(rt.ordinary))
            # A fresh value on the next frame proves nothing is cached.
            struct.pack_into('<i', rt.data, 0x6120 + 0, struct.unpack_from('<i', rt.data, 0x6120)[0] + 1)
            second = s.read_levels()
        assert s.provenance['status'] == 'verified'
        assert first['levels'] == expected_levels(build_image(num_bodies, non_bodies)[0], objects)
        results[level_reader] = (first['levels'], second['levels'], first['transport'])
        if level_reader == 'batched':
            assert not any('dd if=' in c for c in rt.exchanges)
            walks = [c for c in rt.exchanges if c.startswith('H=')]
            assert len(walks) == 2  # exactly one helper exchange per frame
            assert s.provenance['level_walk_helper']['verifications'] == [
                rt.reader.LEVEL_WALK_HELPER_SHA256] * 2
        if level_reader == 'probe':
            assert rt.calls.count('observe-levels') == 2
            assert not any('dd if=' in c or c.startswith('H=') for c in rt.exchanges)
    assert results['legacy'][:2] == results['batched'][:2] == results['probe'][:2]
    assert results['batched'][2] == 'persistent-bounded-adb-level-walk-v1'
    assert results['probe'][2] == 'probe-observe-levels-v1'
    assert results['legacy'][2] == 'persistent-bounded-adb'


def test_batched_walk_consumes_exactly_the_legacy_ranges(device):
    """The helper transcript is exactly the ordered legacy range list."""
    rt, reader = device, device.reader
    with session(rt, 'legacy') as s:
        s.read_levels()
    legacy_ranges = []
    for command in rt.exchanges:
        if 'dd if=' in command:
            for part in command.split('; '):
                fields = dict(p.split('=', 1) for p in part.split() if '=' in p)
                legacy_ranges.append((int(fields['skip']), int(fields['count'])))
    body_ids = {o['nativeObjectId'] for o in rt.ordinary['objects'] if o['hp'] is not None}
    walk = reader.parse_level_walk(
        f'{reader.LEVEL_WALK_HELPER_SHA256}  {DEVICE_HELPER}\n'.encode()
        + emulate_helper(rt.data, PID, 0x1000, body_ids, stat_line()) + b'123\n',
        helper_path=DEVICE_HELPER, helper_sha256=reader.LEVEL_WALK_HELPER_SHA256)
    assert [(a, s) for a, s, _ in walk['records']] == legacy_ranges
    assert all(len(b) == s for _, s, b in walk['records'])
    assert walk['stop_reason'] == 0


# ------------------------------------------------------- batched negatives

def _tamper(fn):
    return lambda raw: fn(bytearray(raw))


def _first_record_offset(raw):
    line_end = raw.index(b'\n') + 1
    stat_len = struct.unpack_from('<I', raw, line_end + 16)[0]
    return line_end + 20 + stat_len


def _mutate_first_record_address(raw):
    offset = _first_record_offset(raw)
    struct.pack_into('<Q', raw, offset + 1, struct.unpack_from('<Q', raw, offset + 1)[0] + 8)
    return bytes(raw)


def _set_stop_reason(raw, reason=5):
    end = raw.rindex(b'CLWEND01')
    stat_len = len(stat_line())
    struct.pack_into('<I', raw, end - stat_len - 4 - 4, reason)
    return bytes(raw)


def _drop_last_record(raw):
    end = raw.rindex(b'CLWEND01')
    stat_len = len(stat_line())
    trailer = end - stat_len - 4 - 9
    count = struct.unpack_from('<I', raw, trailer + 1)[0]
    last = trailer - (1 + 16 + 4)
    struct.pack_into('<I', raw, trailer + 1, count - 1)
    return bytes(raw[:last] + raw[trailer:])


def _add_extra_record(raw):
    end = raw.rindex(b'CLWEND01')
    stat_len = len(stat_line())
    trailer = end - stat_len - 4 - 9
    count = struct.unpack_from('<I', raw, trailer + 1)[0]
    struct.pack_into('<I', raw, trailer + 1, count + 1)
    extra = struct.pack('<BQII', 1, 0x7000, 4, 4) + b'\0\0\0\0'
    return bytes(raw[:trailer] + extra + raw[trailer:])


def _oversized_got(raw):
    offset = _first_record_offset(raw)
    struct.pack_into('<I', raw, offset + 13, 9)
    return bytes(raw)


BATCHED_FAULTS = {
    'helper_sha_frame': lambda rt: rt.helper_sha.__setitem__('frame', '0' * 64),
    'helper_path_line': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw.replace(
        DEVICE_HELPER.encode(), b'/data/local/tmp/other-helper', 1)),
    'pid_after': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw[:-4] + b'124\n'),
    'pid_after_missing': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw[:-4]),
    'stat_after': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw.replace(
        stat_line(), stat_line(start_ticks=98)).replace(stat_line(start_ticks=98), stat_line(), 1)),
    'pid_session': lambda rt: setattr(rt, 'pid', 124),
    'start_ticks_session': lambda rt: setattr(rt, 'start_ticks', 100),
    'transcript_address': lambda rt: setattr(rt, 'walk_hook', _tamper(_mutate_first_record_address)),
    'transcript_missing': lambda rt: setattr(rt, 'walk_hook', _tamper(_drop_last_record)),
    'transcript_extra': lambda rt: setattr(rt, 'walk_hook', _tamper(_add_extra_record)),
    'transcript_oversized_got': lambda rt: setattr(rt, 'walk_hook', _tamper(_oversized_got)),
    'stop_reason': lambda rt: setattr(rt, 'walk_hook', _tamper(_set_stop_reason)),
    'bad_magic': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw.replace(b'CLWALK01', b'CLWALK02')),
    'bad_trailer': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw.replace(b'CLWEND01', b'CLWEND02')),
    'truncated': lambda rt: setattr(rt, 'walk_hook', lambda raw: raw[:len(raw) // 2]),
    'backlink': lambda rt: struct.pack_into('<Q', rt.data, HP_COMPONENTS + 8, 0x6004),
    'identity': lambda rt: struct.pack_into('<I', rt.data, 0x6008, 7),
    'owner': lambda rt: struct.pack_into('<i', rt.data, 0x6078, 1),
    'range': lambda rt: struct.pack_into('<i', rt.data, 0x6120, 127),
    'component_inventory': lambda rt: struct.pack_into('<i', rt.data, 0x6020, 2),
    'vector_count': lambda rt: struct.pack_into('<ii', rt.data, 0x4010, 9, 4),
    'frame_race': lambda rt: setattr(rt, 'walk_hook', lambda raw: (
        rt.ordinary.__setitem__('tick', 25), raw)[1]),
    'short_twice': lambda rt: setattr(rt, 'short', lambda a, s: a == 0x6000 and s == 0xb0),
}


@pytest.mark.parametrize('fault', sorted(BATCHED_FAULTS))
def test_batched_reader_fails_closed(device, fault):
    rt = device
    s = session(rt, 'batched')
    with pytest.raises(ValueError):
        with s:
            BATCHED_FAULTS[fault](rt)
            s.read_levels()
    assert s.provenance['status'] == 'failed'
    assert s.provenance['reads_completed'] == 0


def test_batched_short_walk_retries_once_with_a_fresh_complete_walk(device):
    rt = device
    shorts = {'n': 0}

    def short(address, size):
        if address == 0x6000 and size == 0xb0 and shorts['n'] == 0:
            shorts['n'] += 1
            return True
        return False

    rt.short = short
    with session(rt, 'batched') as s:
        result = s.read_levels()
    assert result['levels'] == expected_levels(rt.data, rt.ordinary['objects'])
    assert [r['kind'] for r in result['transport_recoveries']] == ['short-walk-single-retry']
    assert len([c for c in rt.exchanges if c.startswith('H=')]) == 2


@pytest.mark.parametrize('boundary', ['open', 'close'])
def test_batched_session_checks_helper_hash_at_boundaries(device, boundary):
    rt = device
    rt.helper_sha[boundary] = 'f' * 64
    s = session(rt, 'batched')
    with pytest.raises(ValueError):
        with s:
            s.read_levels()
    assert s.provenance['status'] == 'failed'


def test_level_walk_command_admits_only_validated_integers(device):
    rt, reader = device, device.reader
    shell = reader._PersistentAdbShell(Path('/fixture'), 'fixture')
    for manager, ids in [(0, []), (1 << 56, []), ('4096', []), (4096, [0]), (4096, [1 << 32]),
                         (4096, ['5; reboot']), (4096, list(range(1, 130)))]:
        with pytest.raises(ValueError):
            shell.level_walk(manager, ids)
    for path in ['/system/bin/sh', '/data/local/tmp/x;reboot', '/data/local/tmp/$(id)']:
        with pytest.raises(ValueError):
            shell.level_walk(4096, [5], helper_path=path)
    assert rt.exchanges == []


def test_parse_level_walk_rejects_garbage_after_closing_pid(device):
    reader = device.reader
    good = (f'{reader.LEVEL_WALK_HELPER_SHA256}  {DEVICE_HELPER}\n'.encode()
            + emulate_helper(device.data, PID, 0x1000, set(), stat_line()) + b'123\n')
    reader.parse_level_walk(good, helper_path=DEVICE_HELPER, helper_sha256=reader.LEVEL_WALK_HELPER_SHA256)
    for bad in (good + b'x', good[:-1], good.replace(b'123\n', b'0\n')):
        with pytest.raises(ValueError):
            reader.parse_level_walk(bad, helper_path=DEVICE_HELPER,
                                    helper_sha256=reader.LEVEL_WALK_HELPER_SHA256)


# --------------------------------------------------------- probe negatives

def _probe_fault(mutate):
    def install(rt):
        def hook(response):
            mutate(response)
            return response
        rt.levels_hook = hook
    return install


def _set(path, value):
    def mutate(response):
        target = response
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


PROBE_FAULTS = {
    'not_ok': _probe_fault(_set(('ok',), False)),
    'schema': _probe_fault(_set(('schema',), 'native-public-levels.v0')),
    'generation': _probe_fault(_set(('generation',), 2)),
    'state_epoch': _probe_fault(_set(('stateEpoch',), 2)),
    'tick': _probe_fault(_set(('tick',), 21)),
    'count': _probe_fault(_set(('count',), 4)),
    'capacity_type': _probe_fault(_set(('capacity',), None)),
    'capacity_small': _probe_fault(_set(('capacity',), 2)),
    'returned': _probe_fault(_set(('returned',), 4)),
    'truncated': _probe_fault(_set(('truncated',), True)),
    'offset': _probe_fault(_set(('levelFieldOffset',), 0x124)),
    'layouts_invalid': _probe_fault(_set(('layoutsValid',), False)),
    'slot_order': _probe_fault(lambda r: r['objects'].reverse()),
    'slot_index': _probe_fault(_set(('objects', 0, 'slot'), 1)),
    'null_slot': _probe_fault(_set(('objects', 0, 'null'), True)),
    'identity': _probe_fault(_set(('objects', 0, 'nativeObjectId'), 7)),
    'duplicate_identity': _probe_fault(lambda r: r['objects'][1].update(
        nativeObjectId=r['objects'][0]['nativeObjectId'])),
    'owner': _probe_fault(_set(('objects', 0, 'owner'), 1)),
    'card': _probe_fault(_set(('objects', 0, 'cardId'), 1)),
    'body_set_extra': _probe_fault(lambda r: next(
        o for o in r['objects'] if not o['hasHitpoints']).update(hasHitpoints=True)),
    'body_set_missing': _probe_fault(_set(('objects', 0, 'hasHitpoints'), False)),
    'non_body_level': _probe_fault(lambda r: next(
        o for o in r['objects'] if not o['hasHitpoints']).update(levelRaw=5)),
    'component_capacity': _probe_fault(_set(('objects', 0, 'componentCapacity'), 2)),
    'component_capacity_high': _probe_fault(_set(('objects', 0, 'componentCapacity'), 65)),
    'backlink': _probe_fault(_set(('objects', 0, 'hpComponentBacklink'), False)),
    'level_missing': _probe_fault(_set(('objects', 0, 'levelRaw'), None)),
    'level_high': _probe_fault(_set(('objects', 0, 'levelRaw'), 127)),
    'level_low': _probe_fault(_set(('objects', 0, 'levelRaw'), -1)),
    'level_bool': _probe_fault(_set(('objects', 0, 'levelRaw'), True)),
    'objects_short': _probe_fault(lambda r: r['objects'].pop()),
    # The frame changes after the in-probe read: the closing observe differs.
    'frame_race': lambda rt: setattr(rt, 'levels_hook', lambda r: (
        rt.ordinary.__setitem__('tick', 25), r)[1]),
    'adb_pid_change': lambda rt: setattr(rt, 'pid', 124),
}


@pytest.mark.parametrize('fault', sorted(PROBE_FAULTS))
def test_probe_reader_fails_closed(device, fault):
    rt = device
    s = session(rt, 'probe')
    with pytest.raises(ValueError):
        with s:
            PROBE_FAULTS[fault](rt)
            s.read_levels()
    assert s.provenance['status'] == 'failed'


def test_probe_level_boundary_values_are_accepted(device):
    rt = device
    struct.pack_into('<i', rt.data, 0x6120, 126)
    struct.pack_into('<i', rt.data, 0x6120 + 0x400, 0)
    with session(rt, 'probe') as s:
        levels = s.read_levels()['levels']
    assert levels[5000006] == 127 and levels[5000008] == 1


@pytest.mark.parametrize('fault', ['pid', 'start_ticks', 'missing', 'extra_key', 'bool_pid', 'zero'])
def test_probe_process_identity_is_explicit_and_checked(device, fault):
    rt = device
    s = session(rt, 'probe', probe_process_identity=True)
    with pytest.raises(ValueError):
        with s:
            def hook(response):
                process = response['process']
                if fault == 'pid': process['pid'] = 124
                elif fault == 'start_ticks': process['startTicks'] = 100
                elif fault == 'missing': del process['startTicks']
                elif fault == 'extra_key': process['uid'] = 0
                elif fault == 'bool_pid': process['pid'] = True
                else: process['startTicks'] = 0
                return response
            rt.levels_hook = hook
            before = len(rt.exchanges)
            try:
                s.read_levels()
            finally:
                # No silent ADB stat fallback during the failed frame.
                assert not any(c.startswith(('cat /proc/', 'p=$(pidof')) for c in rt.exchanges[before:])
    assert s.provenance['status'] == 'failed'


def test_probe_process_identity_skips_per_frame_adb_but_not_boundaries(device):
    rt = device
    with session(rt, 'probe', probe_process_identity=True) as s:
        opened = len(rt.exchanges)
        s.read_levels()
        s.read_levels()
        assert len(rt.exchanges) == opened
    assert s.provenance['status'] == 'verified'
    assert len(rt.exchanges) > opened  # closing ADB identity checks still ran


# ------------------------------------------------------ configuration guards

def test_reader_configuration_guards(device):
    rt, reader = device, device.reader
    pin = rt.pin()
    make = lambda **kw: reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=pin, **kw)
    with pytest.raises(ValueError, match='unknown'):
        make(level_reader='fast')
    with pytest.raises(ValueError, match='Phase B'):
        make(level_reader='probe')
    with pytest.raises(ValueError, match='engine and content'):
        make(expected_build={**reader.EXPECTED, 'libg_sha256': '0' * 64})
    with pytest.raises(ValueError, match='engine and content'):
        make(expected_build={**reader.EXPECTED, 'extra': 'x'})
    with pytest.raises(ValueError, match='probe level reader'):
        make(level_reader='batched', probe_process_identity=True)
    assert rt.calls == [] and rt.exchanges == []
    with pytest.raises(ValueError, match='verified session'):
        reader._read_levels(Path('/fixture'), port=1, serial='x', batched=True, level_reader='batched')
    assert reader.EXPECTED_PHASEB['probe_sha256'] == \
        '76953b603b7ffbcefe3daf82aab399987d9bc73c8d1ee6da4060f2bf5176f09f'
    assert {k: v for k, v in reader.EXPECTED_PHASEB.items() if k != 'probe_sha256'} == \
        {k: v for k, v in reader.EXPECTED.items() if k != 'probe_sha256'}


def test_phaseb_session_rejects_the_pinned_probe_attestation(device):
    rt, reader = device, device.reader
    rt.build = dict(reader.EXPECTED)  # device still runs the old probe
    s = reader.VerifiedNativeReadSession(Path('/fixture'), expected_attestation_sha256=rt.pin(),
                                         level_reader='probe', expected_build=reader.EXPECTED_PHASEB)
    with pytest.raises(ValueError, match='attestation'):
        s.__enter__()


def test_legacy_provenance_is_unchanged(device):
    with session(device, 'legacy') as s:
        s.read_levels()
    assert set(s.provenance) == {
        'schema', 'session_id', 'status', 'verification_frequency', 'content_identity_check',
        'expected_attestation_sha256', 'start_attestation_sha256', 'end_attestation_sha256',
        'runtime_identity', 'reads_completed', 'reader_sha256', 'failures'}


# ------------------------------------------- C helper equals the Python model

def _compile_host_helper(tmp_path):
    compiler = shutil.which('cc') or shutil.which('clang')
    if compiler is None:
        pytest.skip('no host C compiler')
    binary = tmp_path / 'clasher-level-walk-hosttest'
    subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-DCLASHER_WALK_TEST',
                    '-o', str(binary), str(HELPER_SOURCE)], check=True, capture_output=True)
    return binary


@pytest.mark.parametrize('case', ['complete', 'no_bodies', 'backlink', 'inventory', 'count',
                                  'short_level', 'short_header', 'invalid_pointer'])
def test_c_helper_matches_python_model_byte_for_byte(tmp_path, case):
    binary = _compile_host_helper(tmp_path)
    data, objects = build_image(5, 3)
    body_ids = [o['nativeObjectId'] for o in objects if o['hp'] is not None]
    if case == 'no_bodies':
        body_ids = []
    elif case == 'backlink':
        struct.pack_into('<Q', data, HP_COMPONENTS + 8, 0x6004)
    elif case == 'inventory':
        struct.pack_into('<i', data, 0x6020, 65)
    elif case == 'count':
        struct.pack_into('<ii', data, 0x4010, 4, 8)
    elif case == 'short_level':
        # Last body's level word straddles the end of the memory file.
        struct.pack_into('<Q', data, 0x5000, len(data) - 0x122)
        struct.pack_into('<I', data, len(data) - 0x122 + 8, objects[0]['nativeObjectId'])
        struct.pack_into('<i', data, len(data) - 0x122 + 0x20, 3)
        struct.pack_into('<Q', data, len(data) - 0x122 + 0x18, COMPONENTS)
        struct.pack_into('<Q', data, HP_COMPONENTS + 8, len(data) - 0x122)
    elif case == 'short_header':
        struct.pack_into('<Q', data, 0x5000, len(data) - 0x40)
    elif case == 'invalid_pointer':
        struct.pack_into('<Q', data, 0x5008, 0)
    memory, stat = tmp_path / 'mem', tmp_path / 'stat'
    memory.write_bytes(bytes(data))
    stat.write_bytes(stat_line())
    completed = subprocess.run([str(binary), str(PID), str(0x1000), *map(str, body_ids)],
                               env={'CLASHER_WALK_MEM_FILE': str(memory), 'CLASHER_WALK_STAT_FILE': str(stat)},
                               check=True, capture_output=True)
    assert completed.stdout == emulate_helper(data, PID, 0x1000, set(body_ids), stat_line())


def test_c_helper_rejects_malformed_arguments_without_output(tmp_path):
    binary = _compile_host_helper(tmp_path)
    memory, stat = tmp_path / 'mem', tmp_path / 'stat'
    memory.write_bytes(bytes(0x100))
    stat.write_bytes(stat_line())
    env = {'CLASHER_WALK_MEM_FILE': str(memory), 'CLASHER_WALK_STAT_FILE': str(stat)}
    for args in ([], ['123'], ['0', '4096'], ['123', '-1'], ['123', '4096', '0'], ['123', '4096', 'x'],
                 ['123', '4096', str(1 << 32)], ['123', '4096', *['5'] * 129], ['123 456', '4096']):
        completed = subprocess.run([str(binary), *args], env=env, capture_output=True)
        assert completed.returncode == 2 and completed.stdout == b''


def test_batched_exchange_through_a_real_shell(tmp_path, monkeypatch):
    """The exact shell command runs under /bin/sh with the compiled helper."""
    reader = load_reader(monkeypatch)
    binary = _compile_host_helper(tmp_path)
    data, objects = build_image(4, 2)
    memory, stat = tmp_path / 'mem', tmp_path / 'stat'
    memory.write_bytes(bytes(data))
    stat.write_bytes(stat_line())
    device_root = tmp_path / 'device'
    (device_root / 'bin').mkdir(parents=True)
    (device_root / 'data').mkdir()
    shutil.copy(binary, device_root / 'data' / 'clasher-level-walk-v1')
    (device_root / 'bin' / 'pidof').write_text(f'#!/bin/sh\necho {PID}\n')
    # Hash the rewritten local file, print the device path (as toybox does).
    (device_root / 'bin' / 'sha256sum').write_text(
        '#!/bin/sh\nd=$(shasum -a 256 "$1" | cut -d" " -f1)\n'
        f'echo "$d  $(echo "$1" | sed "s#{device_root}/data/#/data/local/tmp/#")"\n')
    for tool in ('pidof', 'sha256sum'):
        (device_root / 'bin' / tool).chmod(0o755)
    fake_adb = tmp_path / 'fake-adb'
    fake_adb.write_text(
        '#!/bin/sh\n'
        f'export PATH="{device_root}/bin:$PATH" CLASHER_WALK_MEM_FILE="{memory}" CLASHER_WALK_STAT_FILE="{stat}"\n'
        f'sed -l "s#/data/local/tmp/#{device_root}/data/#g" | /bin/sh\n')
    fake_adb.chmod(0o755)
    helper_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    body_ids = [o['nativeObjectId'] for o in objects if o['hp'] is not None]
    with reader._PersistentAdbShell(fake_adb, 'fixture') as shell:
        assert shell.helper_sha256() == helper_sha
        walk = shell.level_walk(0x1000, body_ids, helper_sha256=helper_sha)
        with pytest.raises(ValueError, match='identity'):
            shell.level_walk(0x1000, body_ids, helper_sha256='0' * 64)
    assert walk['pid'] == walk['pid_after'] == PID
    assert walk['start_ticks'] == walk['start_ticks_after'] == START_TICKS
    assert walk['stop_reason'] == 0
    transcript = reader._LevelWalkTranscript(walk)
    assert walk['records'] == reader.parse_level_walk(
        f'{helper_sha}  {DEVICE_HELPER}\n'.encode() + emulate_helper(data, PID, 0x1000, set(body_ids), stat_line())
        + f'{PID}\n'.encode(), helper_path=DEVICE_HELPER, helper_sha256=helper_sha)['records']
    for address, size, _ in walk['records']:
        transcript.read(PID, [(address, size)])
    transcript.finish()
