"""Read public level-label values from the pinned, paused offline reference."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import select
import struct
import subprocess
import time
import uuid
from pathlib import Path

from smoke_reference_battle import request

from clasher.rl.native_probe_transport import AdbShellLost, NativeLinkLost

EXPECTED = {
    'libg_sha256': '110aa2b5cac391c498645e072b0d88729428c2c2845e7e2737ca8ee979059783',
    'probe_sha256': '2ea5e10dff5cfe763218d07ec17acdb4be1379eac51d6b4f827d887edc3c645c',
    'content_fingerprint_sha256': 'e0cb2fb9eb2fdd0df1afcb00df3e3ba61cf25aa8b24e39c17cc391d952a4e339',
}
# Phase B probe (FirstLight 28d66cc + Clasher observe-levels/transmit cursors;
# ~/.cache/clasher-native-reference/probe-build-phaseb-20260928/receipt.json).
# Same engine and content; only the probe differs. Not the default pin.
EXPECTED_PHASEB = {**EXPECTED,
                   'probe_sha256': '76953b603b7ffbcefe3daf82aab399987d9bc73c8d1ee6da4060f2bf5176f09f'}

# ``legacy``: host pointer walk, one ``dd`` per range (historical default).
# ``batched``: the same walk in one pinned on-device helper process per frame,
# replayed and re-validated on the host from the helper's raw transcript.
# ``probe``: the Phase B probe's in-process ``observe-levels`` (requires
# EXPECTED_PHASEB). Every reader reads every frame; nothing is cached.
LEVEL_READERS = ('legacy', 'batched', 'probe')
LEVEL_WALK_HELPER_PATH = '/data/local/tmp/clasher-level-walk-v1'
LEVEL_WALK_HELPER_SHA256 = '4a00b4f68c7ee6a9d96d186af815c0a47bfbb6bf4c42ff84bb67b9074f86167d'
LEVEL_WALK_MAX_BYTES = 512 * 1024
PUBLIC_LEVEL_FIELD_OFFSET = 0x120
_TRANSPORT_NAMES = {
    'batched': 'persistent-bounded-adb-level-walk-v1',
    'probe': 'probe-observe-levels-v1',
    'atomic': 'probe-atomic-levels-v1',
}


class _ShortLevelWalk(ValueError):
    """A helper transcript range returned fewer bytes than requested."""


def _check_range(address, size):
    if (type(address) is not int or type(size) is not int or not 0 < address < 1 << 56
            or not 0 < size <= 4096 or address + size > 1 << 56):
        raise ValueError('invalid bounded memory request')


def parse_level_walk(raw: bytes, *, helper_path: str, helper_sha256: str) -> dict:
    """Parse one helper exchange strictly: sha line, framed walk, pid line."""
    expected_line = f'{helper_sha256}  {helper_path}\n'.encode()
    if not raw.startswith(expected_line):
        raise ValueError('native level walk helper identity differs from pin')
    view, offset = memoryview(raw), len(expected_line)

    def take(size):
        nonlocal offset
        if size < 0 or offset + size > len(raw):
            raise ValueError('truncated native level walk transcript')
        chunk = bytes(view[offset:offset + size])
        offset += size
        return chunk

    def u32():
        return struct.unpack('<I', take(4))[0]

    if take(8) != b'CLWALK01':
        raise ValueError('invalid native level walk framing')
    pid, body_count = u32(), u32()
    stat_before = take(u32())
    records = []
    while True:
        tag = take(1)
        if tag == b'\x01':
            address, size, got = struct.unpack('<QII', take(16))
            if got > size:
                raise ValueError('oversized native level walk range')
            records.append((address, size, take(got)))
        elif tag == b'\x02':
            count, stop_reason = u32(), u32()
            break
        else:
            raise ValueError('invalid native level walk record tag')
    if count != len(records):
        raise ValueError('native level walk record count mismatch')
    stat_after = take(u32())
    if take(8) != b'CLWEND01':
        raise ValueError('invalid native level walk trailer')
    tail = raw[offset:]
    if not tail.endswith(b'\n') or not tail[:-1].isdigit() or int(tail[:-1]) <= 0:
        raise ValueError('invalid native level walk closing process identity')
    return {'pid': pid, 'body_count': body_count, 'stat_before': stat_before,
            'records': records, 'stop_reason': stop_reason, 'stat_after': stat_after,
            'pid_after': int(tail[:-1])}


class _LevelWalkTranscript:
    """Serve the host walk's range reads strictly, in order, from one transcript.

    Every host request must equal the next recorded (address, size); a short
    record raises ``_ShortLevelWalk``; ``finish`` requires every record consumed
    and a complete helper walk. Bytes are never spliced across transcripts.
    """

    def __init__(self, walk: dict):
        self.pid = walk['pid']
        self.records = walk['records']
        self.stop_reason = walk['stop_reason']
        self.position = 0

    def read(self, pid, ranges):
        if pid != self.pid:
            raise ValueError('native level walk process differs from the frame process')
        if not ranges or len(ranges) > 128 or sum(size for _, size in ranges) > 65536:
            raise ValueError('invalid native memory batch')
        for address, size in ranges:
            _check_range(address, size)
        chunks = []
        for address, size in ranges:
            if self.position >= len(self.records):
                raise ValueError(
                    f'native level walk transcript ended early (helper stop reason {self.stop_reason})')
            recorded_address, recorded_size, data = self.records[self.position]
            if (recorded_address, recorded_size) != (address, size):
                raise ValueError('native level walk transcript differs from the host walk')
            self.position += 1
            if len(data) != size:
                raise _ShortLevelWalk(f'short native level walk range: address={address:#x}, '
                                      f'expected={size}, actual={len(data)}')
            chunks.append(data)
        return b''.join(chunks)

    def finish(self):
        if self.position != len(self.records) or self.stop_reason != 0:
            raise ValueError('native level walk transcript has unconsumed or incomplete records')


def probe_levels_from_response(response, before, *, expected_generation=None):
    """Validate an in-probe public level response against its ordinary frame.

    Applies the host reader's checks to the probe's facts: object identity,
    owner and card per slot; the body set is exactly the ordinary frame's
    non-null ``hp`` objects; each body has a 3..64 component inventory and a
    valid HP component backlink; level = raw + 1 within 1..127. Returns the
    level map in object-vector order, as the host walk does.
    """
    if (not isinstance(response, dict) or response.get('ok') is not True
            or response.get('schema') != 'native-public-levels.v1'):
        raise ValueError('invalid native public level response')
    for key in ('generation', 'stateEpoch', 'tick', 'count'):
        if type(response.get(key)) is not int or response[key] != before.get(key):
            raise ValueError('native public levels and ordinary frame disagree')
    if (response.get('returned') != response['count'] or response.get('truncated') is not False
            or response.get('levelFieldOffset') != PUBLIC_LEVEL_FIELD_OFFSET
            or response.get('layoutsValid') is not True):
        raise ValueError('native public level response is incomplete')
    count, capacity = response['count'], response.get('capacity')
    objects = response.get('objects')
    if (type(capacity) is not int or not 0 < count <= min(capacity, 128)
            or not isinstance(objects, list) or len(objects) != count):
        raise ValueError('invalid native object vector')
    if len(before['objects']) != count:
        raise ValueError('invalid native object vector')
    expected = {o['nativeObjectId']: o for o in before['objects']}
    if len(expected) != count:
        raise ValueError('duplicate ordinary object ID')
    seen, levels = set(), {}
    for index, (entry, ordinary) in enumerate(zip(objects, before['objects'], strict=True)):
        if not isinstance(entry, dict) or entry.get('slot') != index or entry.get('null'):
            raise ValueError('object identity mismatch')
        identity = entry.get('nativeObjectId')
        obj = expected.get(identity)
        if obj is None or identity in seen or ordinary.get('nativeObjectId') != identity:
            raise ValueError('object identity mismatch')
        seen.add(identity)
        if entry.get('owner') != obj['owner'] or entry.get('cardId') != obj['cardId']:
            raise ValueError('native body metadata mismatch')
        body = obj['hp'] is not None
        if entry.get('hasHitpoints') is not body:
            raise ValueError('native body set differs from ordinary frame')
        if not body:
            if entry.get('levelRaw') is not None:
                raise ValueError('native non-body object reported a level')
            continue
        capacity = entry.get('componentCapacity')
        if type(capacity) is not int or not 3 <= capacity <= 64:
            raise ValueError('missing body component inventory')
        if entry.get('hpComponentBacklink') is not True:
            raise ValueError('HP component owner backlink mismatch')
        raw = entry.get('levelRaw')
        if type(raw) is not int:
            raise ValueError('native public level missing')
        value = raw + 1
        if not 1 <= value <= 127:
            raise ValueError('native public level out of range')
        levels[identity] = value
    if expected_generation is not None and response['generation'] != expected_generation:
        raise ValueError('native public levels generation differs')
    return levels


class _PersistentAdbShell:
    """One bounded, framed ADB shell owned by a read or verified session.

    The shell caches no process identity, pointers or values between frames.
    Base64 framing prevents arbitrary memory bytes from imitating a delimiter.
    """

    def __init__(self, adb: Path, serial: str, *, timeout: float = 10.0):
        self.adb, self.serial, self.timeout = adb, serial, timeout
        self.process = None
        self.sequence = 0

    def __enter__(self):
        self.process = subprocess.Popen(
            [str(self.adb), '-s', self.serial, 'shell', '-T', 'sh'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        return self

    def __exit__(self, *exc):
        assert self.process is not None
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.process.stdout is not None:
            self.process.stdout.close()

    def _exchange(self, command: str, *, max_bytes: int) -> bytes:
        assert self.process is not None
        assert self.process.stdin is not None and self.process.stdout is not None
        self.sequence += 1
        marker = f'__CLASHER_READ_{self.sequence}__'.encode()
        # Commands are internal constants or validated integer memory ranges.
        script = ('{ ' + command + '; } | base64\n'
                  + "printf '\\n%s\\n' " + marker.decode() + '\n')
        # A lost shell (adb transport reconnect, device offline) surfaces as a
        # broken pipe, EOF or stall: ``AdbShellLost`` lets a verified session
        # recover and re-read the same paused frame. The cause is chained, so
        # unrecovered classification is unchanged.
        try:
            self.process.stdin.write(script.encode())
            self.process.stdin.flush()
        except BrokenPipeError as error:
            raise AdbShellLost('native memory shell pipe closed') from error
        deadline = time.monotonic() + self.timeout
        data = bytearray()
        terminator = b'\n' + marker + b'\n'
        encoded_limit = max_bytes * 2 + 256
        while not data.endswith(terminator):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise AdbShellLost('native memory shell response timed out') from TimeoutError(
                    'native memory shell response timed out')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise AdbShellLost('native memory shell closed before its response delimiter')
            data.extend(chunk)
            if len(data) > encoded_limit:
                raise ValueError('oversized native memory shell response')
        encoded = b''.join(bytes(data[:-len(terminator)]).splitlines())
        try:
            result = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError('invalid native memory shell framing') from exc
        if len(result) > max_bytes:
            raise ValueError('oversized native memory shell payload')
        return result

    def pid(self) -> int:
        return int(self._exchange('pidof nullsroyale.rel.free', max_bytes=64))

    def process_start_ticks(self, pid: int) -> int:
        if type(pid) is not int or pid <= 0:
            raise ValueError('invalid native process identity')
        return self._start_ticks(pid, self._exchange(f'cat /proc/{pid}/stat', max_bytes=4096))

    def pid_and_start_ticks(self) -> tuple[int, int]:
        """The same pidof and /proc/PID/stat reads in one shell round trip."""
        raw = self._exchange(
            'p=$(pidof nullsroyale.rel.free) && echo "$p" && cat "/proc/$p/stat"',
            max_bytes=64 + 4096)
        first, separator, stat = raw.partition(b'\n')
        if not separator:
            raise ValueError('invalid native process identity response')
        pid = int(first)
        if pid <= 0:
            raise ValueError('invalid native process identity')
        return pid, self._start_ticks(pid, stat)

    @staticmethod
    def _start_ticks(pid: int, raw: bytes) -> int:
        # The comm field can contain spaces and parentheses; fields after its
        # closing parenthesis begin with field 3, and starttime is field 22.
        prefix, separator, tail = raw.rpartition(b')')
        if not separator or int(prefix.split(b' ', 1)[0]) != pid:
            raise ValueError('invalid native process stat')
        fields = tail.split()
        if len(fields) < 20 or not fields[19].isdigit() or int(fields[19]) <= 0:
            raise ValueError('invalid native process start time')
        return int(fields[19])

    def level_walk(self, manager: int, body_ids, *, helper_path=LEVEL_WALK_HELPER_PATH,
                   helper_sha256=LEVEL_WALK_HELPER_SHA256) -> dict:
        """The whole per-frame range walk in one exchange and one helper process.

        The shell prints the helper's SHA-256, runs it against the current
        ``pidof`` process, then prints ``pidof`` again. Pid and stat identity
        before and after the walk are returned for the caller's checks.
        """
        if type(manager) is not int or not 0 < manager < 1 << 56:
            raise ValueError('invalid native manager address')
        ids = list(body_ids)
        if len(ids) > 128 or any(type(i) is not int or not 0 < i < 1 << 32 for i in ids):
            raise ValueError('invalid native body identities')
        if (not isinstance(helper_path, str) or not helper_path.startswith('/data/local/tmp/')
                or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_./' for c in helper_path)):
            raise ValueError('invalid native level walk helper path')
        # Only validated integers and a validated constant path enter the script.
        command = (f'H={helper_path} && sha256sum "$H" && p=$(pidof nullsroyale.rel.free) && '
                   f'"$H" "$p" {manager}' + ''.join(f' {i}' for i in ids)
                   + ' && pidof nullsroyale.rel.free')
        walk = parse_level_walk(self._exchange(command, max_bytes=LEVEL_WALK_MAX_BYTES),
                                helper_path=helper_path, helper_sha256=helper_sha256)
        walk['start_ticks'] = self._start_ticks(walk['pid'], walk['stat_before'])
        walk['start_ticks_after'] = self._start_ticks(walk['pid'], walk['stat_after'])
        return walk

    def helper_sha256(self, helper_path=LEVEL_WALK_HELPER_PATH) -> str:
        raw = self._exchange(f'sha256sum {helper_path}', max_bytes=256)
        digest, separator, path = raw.decode(errors='replace').partition('  ')
        if not separator or path != helper_path + '\n' or len(digest) != 64:
            raise ValueError('native level walk helper is missing or unreadable')
        return digest

    def read(self, pid: int, ranges) -> bytes:
        commands = []
        for address, size in ranges:
            if not 0 < address < 1 << 56 or not 0 < size <= 4096 or address + size > 1 << 56:
                raise ValueError('invalid bounded memory request')
            commands.append(
                f'dd if=/proc/{pid}/mem bs=4096 skip={address} count={size} '
                'iflag=count_bytes,skip_bytes 2>/dev/null'
            )
        if not 0 < pid or not ranges or len(ranges) > 128 or sum(size for _, size in ranges) > 65536:
            raise ValueError('invalid native memory batch')
        return self._exchange('; '.join(commands), max_bytes=sum(size for _, size in ranges))


def _canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class VerifiedNativeReadSession:
    """Branch-scoped full attestation with frame-local identity verification.

    Enter after configure. Exit must succeed before the caller publishes a
    successful branch. Full content/code hashes are checked at boundaries,
    rather than on every frame; runtime identity is checked on every read.
    Body pointers and level observations are never cached.
    """

    STATUS_IDENTITY_FIELDS = (
        'mode', 'manager', 'generation', 'stateEpoch', 'configRevision',
        'contentRoot', 'contentContext', 'configRoot', 'configLocationId',
    )

    def __init__(self, adb: Path, *, expected_attestation_sha256: str,
                 port=26789, serial='emulator-5580', probe=None,
                 combined_identity_reads=False, level_reader='legacy',
                 expected_build=None, probe_process_identity=False,
                 level_walk_helper_sha256=LEVEL_WALK_HELPER_SHA256, recovery=None):
        if (not isinstance(expected_attestation_sha256, str)
                or len(expected_attestation_sha256) != 64
                or any(c not in '0123456789abcdef' for c in expected_attestation_sha256)):
            raise ValueError('a pinned full attestation SHA-256 is required')
        self.adb, self.port, self.serial = adb, port, serial
        # ``probe`` sends one command over the caller's transport, e.g. an open
        # session-v1 connection. The default opens one connection per command.
        self._probe = probe
        # Per-read pid and process start-time checks in one ADB round trip
        # instead of two; the checked values are unchanged.
        self.combined_identity_reads = bool(combined_identity_reads)
        if level_reader not in LEVEL_READERS:
            raise ValueError('unknown native level reader')
        self.level_reader = level_reader
        # Build pins checked at both attestations; Phase B readers need the
        # Phase B probe, and the legacy/batched readers work with either.
        self.expected_build = dict(EXPECTED if expected_build is None else expected_build)
        if level_reader == 'probe' and self.expected_build != EXPECTED_PHASEB:
            raise ValueError('the probe level reader requires the Phase B probe pin')
        if set(self.expected_build) != set(EXPECTED) or any(
                self.expected_build[k] != EXPECTED[k] for k in EXPECTED if k != 'probe_sha256'):
            raise ValueError('native build pin must keep the pinned engine and content')
        # Per-frame identity from the probe's own pid/start time (Phase B
        # responses) instead of ADB; ADB still establishes and re-checks the
        # identity at session enter and close. Off by default.
        self.probe_process_identity = bool(probe_process_identity)
        if self.probe_process_identity and level_reader != 'probe':
            raise ValueError('probe process identity requires the probe level reader')
        self.level_walk_helper_sha256 = level_walk_helper_sha256
        self._helper_verifications = []
        # Optional ``NativeLinkRecovery`` shared with the probe transport. A
        # lost adb shell is replaced (same serial, same process identity) and
        # the interrupted pure read is repeated in full on the same paused
        # frame; recoveries are recorded there, not in frame evidence.
        self._recovery = recovery
        self.expected_attestation_sha256 = expected_attestation_sha256
        self._transport = None
        self._state = 'new'
        self._failures = []
        self._identity = None
        self._start_attestation = None
        self._end_attestation = None
        self._reader_sha256 = None
        self._session_id = uuid.uuid4().hex
        self._reads = 0

    @property
    def provenance(self):
        return copy.deepcopy({
            'schema': 'native-verified-read-session.v1',
            'session_id': self._session_id, 'status': self._state,
            'verification_frequency': 'full-attestation-at-session-enter-and-close',
            'content_identity_check': 'contentRoot/contentContext each read; content byte hashes at session boundaries',
            'expected_attestation_sha256': self.expected_attestation_sha256,
            'start_attestation_sha256': None if self._start_attestation is None else _canonical_sha(self._start_attestation),
            'end_attestation_sha256': None if self._end_attestation is None else _canonical_sha(self._end_attestation),
            'runtime_identity': self._identity, 'reads_completed': self._reads,
            'reader_sha256': self._reader_sha256, 'failures': self._failures,
            **({} if self.level_reader == 'legacy' else {
                'level_reader': self.level_reader,
                'expected_build': self.expected_build,
                'probe_process_identity': self.probe_process_identity,
                'level_walk_helper': None if self.level_reader != 'batched' else {
                    'path': LEVEL_WALK_HELPER_PATH, 'sha256': self.level_walk_helper_sha256,
                    'verifications': self._helper_verifications,
                    'per_frame_check': 'sha256sum in every walk exchange',
                },
            }),
        })

    def probe(self, command):
        return request(self.port, command) if self._probe is None else self._probe(command)

    def _fail(self, error):
        self._failures.append(f'{type(error).__name__}: {error}')
        self._state = 'failed'

    def _full_attestation(self, *, closing=False):
        response = self.probe('attest')
        if closing:
            self._end_attestation = copy.deepcopy(response)
        if (response.get('ok') is not True
                or not isinstance(response.get('attestation'), dict)
                or any(response['attestation'].get(k) != v for k, v in self.expected_build.items())
                or _canonical_sha(response) != self.expected_attestation_sha256):
            raise ValueError('native session full attestation differs from pin')
        return copy.deepcopy(response)

    def _runtime_identity(self, status, ordinary, pid, start_ticks=None):
        if any(status.get(name) is not True for name in
               ('ready', 'paused', 'configured', 'contentReady', 'contentPublished')):
            raise ValueError('native session runtime must be ready, paused and configured')
        if (ordinary.get('truncated') is not False
                or ordinary.get('returned') != ordinary.get('count')):
            raise ValueError('native session ordinary snapshot is incomplete')
        for name in ('generation', 'stateEpoch', 'configRevision'):
            if type(status.get(name)) is not int or status[name] <= 0:
                raise ValueError('invalid native session generation/configuration identity')
        if any(ordinary.get(key) != status.get(key) for key in ('generation', 'stateEpoch', 'tick')):
            raise ValueError('native session status and observation disagree')
        for name in ('manager', 'contentRoot', 'contentContext'):
            if not isinstance(status.get(name), str) or not 0 < int(status[name], 16) < 1 << 56:
                raise ValueError('invalid native session content or manager identity')
        if status.get('mode') not in ('headless', 'native-render'):
            raise ValueError('unknown native session mode')
        if any(name not in status for name in self.STATUS_IDENTITY_FIELDS):
            raise ValueError('missing native session identity field')
        if type(pid) is not int or pid <= 0:
            raise ValueError('invalid native session process identity')
        return {**{name: status[name] for name in self.STATUS_IDENTITY_FIELDS},
                'pid': pid, 'process_start_ticks': (self._transport.process_start_ticks(pid)
                                                    if start_ticks is None else start_ticks)}

    def _check_identity(self, status, ordinary, pid, start_ticks=None):
        if self._runtime_identity(status, ordinary, pid, start_ticks) != self._identity:
            raise ValueError('native session process/configuration/content identity changed')

    def _check_current_identity(self):
        self._check_identity(self.probe('status'), self.probe('observe'),
                             self._transport.pid())

    def __enter__(self):
        if self._state != 'new':
            raise ValueError('native read session cannot be reentered')
        try:
            self._transport = _PersistentAdbShell(self.adb, self.serial).__enter__()
            self._start_attestation = self._full_attestation()
            self._identity = self._runtime_identity(
                self.probe('status'), self.probe('observe'), self._transport.pid())
            self._reader_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            if self.level_reader == 'batched':
                self._check_helper()
            self._state = 'open'
            return self
        except BaseException as error:
            self._fail(error)
            try:
                if self._transport is not None:
                    self._transport.__exit__(None, None, None)
            except BaseException as cleanup_error:
                self._fail(cleanup_error)
                raise
            finally:
                self._transport = None
            raise

    def read_levels(self, ordinary=None):
        """Read levels of the current paused frame.

        ``ordinary`` may be the caller's ``observe`` response for this frame.
        It replaces only the reader's opening ``observe``; the reader still
        checks it against ``status`` and requires a closing ``observe`` equal
        to it, so any frame change between the caller's reads still fails.
        """
        if self._state != 'open':
            raise ValueError('native read session is not open or was invalidated')
        try:
            result = self._shell_guarded(f'read_levels#{self._reads + 1}', lambda: _read_levels(
                self.adb, port=self.port, serial=self.serial, batched=True,
                transport=self._transport, session=self, ordinary=ordinary,
                level_reader=self.level_reader))
            if result['reader_sha256'] != self._reader_sha256:
                raise ValueError('native level reader source changed within session')
            self._reads += 1
            result['verified_session'] = {
                'schema': 'native-verified-read-session.v1', 'session_id': self._session_id,
                'read_index': self._reads, 'runtime_identity': copy.deepcopy(self._identity),
                'verification_frequency': 'full-attestation-at-session-enter-and-close',
                'pending_final_verification': True,
            }
            return result
        except BaseException as error:
            self._fail(error)
            raise

    def __exit__(self, exc_type, exc, traceback):
        if self._transport is None or self._state not in ('open', 'failed'):
            raise ValueError('native read session cannot close in its current state')
        if exc is not None:
            self._fail(exc)
        close_error = None
        try:
            # Attempt both identity and full boundary attestation even if an
            # earlier read failed. A caught read error cannot rehabilitate a branch.
            operations = (self._check_current_identity, self._close_attestation,
                          self._check_current_identity, self._check_source)
            if self.level_reader == 'batched':
                operations += (self._check_helper,)
            for operation in operations:
                try:
                    self._shell_guarded(f'close:{operation.__name__}', operation)
                except BaseException as error:
                    self._fail(error)
                    close_error = close_error or error
                    if not isinstance(error, Exception):
                        raise
        finally:
            try:
                self._transport.__exit__(exc_type, exc, traceback)
            except BaseException as error:
                self._fail(error)
                raise
            finally:
                self._transport = None
                self._state = 'failed' if self._failures else 'verified'
        if close_error is not None:
            raise ValueError('native session closing verification failed') from close_error
        if self._failures and exc is None:
            raise ValueError('native session was invalidated before close')
        return False

    def _shell_guarded(self, name, operation):
        """Run a pure read; on a lost adb shell recover and repeat it whole."""
        while True:
            try:
                return operation()
            except AdbShellLost as error:
                if self._recovery is None:
                    raise
                self._recover_shell(name, error)

    def _recover_shell(self, name, error):
        expected = None if self._identity is None else {
            'pid': self._identity['pid'],
            'process_start_ticks': self._identity['process_start_ticks']}

        def attempt():
            replacement = _PersistentAdbShell(self.adb, self.serial).__enter__()
            try:
                pid, start_ticks = replacement.pid_and_start_ticks()
                identity = {'pid': pid, 'process_start_ticks': start_ticks}
                if identity != (expected or self._recovery.baseline_identity):
                    raise NativeLinkLost(
                        f'native process identity changed across adb shell recovery: {identity}')
                verification = {'process_identity': identity}
                if self.level_reader == 'batched':
                    digest = replacement.helper_sha256()
                    if digest != self.level_walk_helper_sha256:
                        raise NativeLinkLost('native level walk helper changed across recovery')
                    verification['level_walk_helper_sha256'] = digest
                attestation = self.probe('attest')
                if _canonical_sha(attestation) != self.expected_attestation_sha256:
                    raise NativeLinkLost('native attestation changed across adb shell recovery')
                verification['attestation_sha256'] = self.expected_attestation_sha256
            except BaseException:
                replacement.__exit__(None, None, None)
                raise
            previous, self._transport = self._transport, replacement
            try:
                previous.__exit__(None, None, None)
            except (OSError, ValueError, subprocess.SubprocessError) as cleanup_error:
                # The lost shell is already gone; its replacement is verified.
                verification['lost_shell_cleanup'] = f'{type(cleanup_error).__name__}: {cleanup_error}'
            verification['resolution'] = 'pure read repeated in full on the same paused frame'
            return None, verification

        self._recovery.run(channel='adb-shell', operation=name, cause=error, attempt=attempt)

    def _close_attestation(self):
        self._end_attestation = self._full_attestation(closing=True)

    def _check_helper(self):
        digest = self._transport.helper_sha256()
        self._helper_verifications.append(digest)
        if digest != self.level_walk_helper_sha256:
            raise ValueError('native level walk helper differs from pin')

    def _check_source(self):
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != self._reader_sha256:
            raise ValueError('native level reader source changed within session')


def read_levels(adb: Path, *, port=26789, serial='emulator-5580', batched=False, persistent=False):
    if persistent:
        with _PersistentAdbShell(adb, serial) as transport:
            return _read_levels(adb, port=port, serial=serial, batched=True, transport=transport)
    return _read_levels(adb, port=port, serial=serial, batched=batched)


def _read_levels(adb: Path, *, port, serial, batched, transport=None, session=None, ordinary=None,
                 level_reader='legacy'):
    probe = session.probe if session is not None else (lambda command: request(port, command))
    if ordinary is not None and session is None:
        raise ValueError('a supplied ordinary frame requires a verified session')
    if level_reader not in LEVEL_READERS:
        raise ValueError('unknown native level reader')
    if level_reader != 'legacy' and (session is None or transport is None):
        raise ValueError('non-legacy level readers require a verified session')
    expected_build = EXPECTED if session is None else session.expected_build
    attestation = (copy.deepcopy(session._start_attestation['attestation']) if session is not None
                   else probe('attest')['attestation'])
    if any(attestation.get(k) != v for k, v in expected_build.items()):
        raise ValueError('unverified native build')
    status = probe('status')
    if not status['paused'] or not status['ready']:
        raise ValueError('reference must be ready and paused')
    # A caller-supplied frame is still checked against this status (identity,
    # tick, epoch) and against the closing observe below.
    before = probe('observe') if ordinary is None else copy.deepcopy(ordinary)
    if before['truncated'] or before['returned'] != before['count']:
        raise ValueError('incomplete ordinary snapshot')
    def current_pid():
        return transport.pid() if transport is not None else int(subprocess.check_output(
            [str(adb), '-s', serial, 'shell', 'pidof', 'nullsroyale.rel.free']))

    combined = session is not None and session.combined_identity_reads
    probe_identity = session is not None and session.probe_process_identity
    recoveries = []
    walk = None
    if level_reader == 'batched':
        body_ids = [o['nativeObjectId'] for o in before['objects'] if o.get('hp') is not None]
        manager_address = int(status['manager'], 16)

        def fetch_walk():
            # One exchange: helper hash, pid, stat, the whole walk, stat, pid.
            fetched = transport.level_walk(manager_address, body_ids,
                                           helper_sha256=session.level_walk_helper_sha256)
            session._check_identity(status, before, fetched['pid'], fetched['start_ticks'])
            if (fetched['pid_after'] != fetched['pid']
                    or fetched['start_ticks_after'] != fetched['start_ticks']):
                raise ValueError('native process identity changed during the level walk')
            return fetched

        walk = fetch_walk()
        pid = walk['pid']
    elif level_reader == 'probe' and probe_identity:
        pid = None  # checked from the probe's own response below
    elif combined:
        pid, start_ticks = transport.pid_and_start_ticks()
        session._check_identity(status, before, pid, start_ticks)
    else:
        pid = current_pid()
        if session is not None:
            session._check_identity(status, before, pid)
    range_reader = transport if walk is None else _LevelWalkTranscript(walk)

    def memory(address, size):
        if not 0 < address < 1 << 56 or not 0 < size <= 4096:
            raise ValueError('invalid bounded memory request')
        def perform_read():
            return range_reader.read(pid, [(address, size)]) if range_reader is not None else subprocess.check_output(
                [str(adb), '-s', serial, 'exec-out',
                 f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null'])

        data = perform_read()
        if len(data) < size:
            # Retry the identical bounded read once, only in the same paused
            # process/frame. Discard the partial bytes rather than combining
            # responses or replaying the match to obtain replacement evidence.
            current = probe('status')
            if (
                not current['paused'] or not current['ready']
                or current['manager'] != status['manager']
                or probe('observe') != before
                or current_pid() != pid
            ):
                raise ValueError('native frame or process changed after short memory read')
            received = len(data)
            data = perform_read()
            if len(data) == size:
                recoveries.append({
                    'kind': 'short-single-retry', 'address': hex(address),
                    'expected_bytes': size, 'received_bytes': received,
                })
        if len(data) != size:
            raise ValueError(
                f'invalid native memory read length: address={address:#x}, '
                f'expected={size}, actual={len(data)}'
            )
        return data

    def memory_many(ranges):
        if len(ranges) > 128 or sum(size for _, size in ranges) > 65536:
            raise ValueError('oversized native memory batch')
        for address, size in ranges:
            if not 0 < address < 1 << 56 or not 0 < size <= 4096 or address + size > 1 << 56:
                raise ValueError('invalid bounded memory request')
        if not ranges:
            return []
        if not batched:
            return [memory(address, size) for address, size in ranges]
        # Only validated integer addresses and byte counts enter this script.
        commands = [f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null'
                    for address, size in ranges]
        data = range_reader.read(pid, ranges) if range_reader is not None else subprocess.check_output(
            [str(adb), '-s', serial, 'exec-out', '\n'.join(commands)])
        expected_size = sum(size for _, size in ranges)
        if len(data) != expected_size:
            if len(data) > expected_size:
                raise ValueError(
                    f'oversized native memory response: expected={expected_size}, actual={len(data)}'
                )
            # Recover only transport truncation within the same paused frame.
            # Discard the entire batch; never splice partial and retried bytes.
            if probe('observe') != before:
                raise ValueError('native frame changed after short memory batch')
            chunks = [memory(address, size) for address, size in ranges]
            recoveries.append({
                'kind': 'short-batch-serial-fallback',
                'ranges': len(ranges), 'expected_bytes': expected_size,
                'received_bytes': len(data),
            })
            return chunks
        chunks, offset = [], 0
        for _, size in ranges:
            chunks.append(data[offset:offset + size])
            offset += size
        return chunks

    def pointer(address):
        return struct.unpack('<Q', memory(address, 8))[0]

    def walk_levels():
        manager = int(status['manager'], 16)
        world = pointer(manager + 0xa8)
        king = pointer(world + 0xe0)
        object_manager = pointer(king + 0x10)
        vector = pointer(object_manager + 8)
        capacity, count = struct.unpack('<ii', memory(object_manager + 0x10, 8))
        if not 0 < count <= min(capacity, 128) or count != before['count']:
            raise ValueError('invalid native object vector')
        pointers = struct.unpack(f'<{count}Q', memory(vector, count * 8))
        expected = {o['nativeObjectId']: o for o in before['objects']}
        if len(expected) != count:
            raise ValueError('duplicate ordinary object ID')
        seen, levels, bodies = set(), {}, []
        headers = memory_many([(address, 0xb0) for address in pointers])
        for address, header in zip(pointers, headers, strict=True):
            identity = struct.unpack_from('<I', header, 8)[0]
            obj = expected.get(identity)
            if obj is None or identity in seen:
                raise ValueError('object identity mismatch')
            seen.add(identity)
            owner = struct.unpack_from('<i', header, 0x78)[0]
            card = struct.unpack_from('<i', header, 0xac)[0]
            if owner != obj['owner'] or card != obj['cardId']:
                raise ValueError('native body metadata mismatch')
            if obj['hp'] is None:
                continue
            # Only a validated HP component establishes a character/body layout.
            components = struct.unpack_from('<Q', header, 0x18)[0]
            component_count = struct.unpack_from('<i', header, 0x20)[0]
            if not 3 <= component_count <= 64:
                raise ValueError('missing body component inventory')
            bodies.append((address, identity, components))
        hp_components = [struct.unpack('<Q', data)[0] for data in memory_many(
            [(components + 16, 8) for _, _, components in bodies]
        )]
        backlinks = memory_many([(component + 8, 8) for component in hp_components])
        for (address, _, _), backlink in zip(bodies, backlinks, strict=True):
            if struct.unpack('<Q', backlink)[0] != address:
                raise ValueError('HP component owner backlink mismatch')
        # Read level fields only after every body layout/backlink has validated.
        values = memory_many([(address + 0x120, 4) for address, _, _ in bodies])
        for (_, identity, _), raw in zip(bodies, values, strict=True):
            value = struct.unpack('<i', raw)[0] + 1
            if not 1 <= value <= 127:
                raise ValueError('native public level out of range')
            levels[identity] = value
        return levels

    if level_reader == 'probe':
        response = probe('observe-levels')
        levels = probe_levels_from_response(response, before)
        if probe_identity:
            process = response.get('process')
            if (not isinstance(process, dict) or set(process) != {'pid', 'startTicks'}
                    or any(type(process[k]) is not int or process[k] <= 0 for k in process)):
                raise ValueError('native public levels lack process identity')
            # Explicit start time: never fall back to an ADB stat read here.
            session._check_identity(status, before, process['pid'], process['startTicks'])
    elif walk is None:
        levels = walk_levels()
    else:
        try:
            levels = walk_levels()
        except _ShortLevelWalk as error:
            # Same rule as the legacy single-range retry: only in the same
            # paused process/frame, one fresh complete walk, never a splice.
            current = probe('status')
            if (not current['paused'] or not current['ready']
                    or current['manager'] != status['manager'] or probe('observe') != before):
                raise ValueError('native frame or process changed after short memory read') from error
            walk = fetch_walk()
            if walk['pid'] != pid:
                raise ValueError('native frame or process changed after short memory read') from error
            range_reader = _LevelWalkTranscript(walk)
            try:
                levels = walk_levels()
            except _ShortLevelWalk as retry_error:
                raise ValueError(f'invalid native memory read length after walk retry: {retry_error}') from retry_error
            recoveries.append({'kind': 'short-walk-single-retry', 'detail': str(error)})
        range_reader.finish()
    after = probe('observe')
    final_status = probe('status')
    if after != before or not final_status['paused'] or not final_status['ready'] or final_status['manager'] != status['manager']:
        raise ValueError('native frame changed during read')
    if session is not None:
        if probe_identity:
            # The probe-reported identity above was read inside this bracket;
            # ADB identity is re-established at session close.
            session._check_identity(final_status, after, process['pid'], process['startTicks'])
        elif combined:
            session._check_identity(final_status, after, *transport.pid_and_start_ticks())
        else:
            session._check_identity(final_status, after, current_pid())
    return {'ordinary': before, 'levels': levels, 'attestation': attestation,
            'reader_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'transport': (_TRANSPORT_NAMES[level_reader] if level_reader != 'legacy' else
                          'persistent-bounded-adb' if transport is not None else ('batched-adb' if batched else 'serial-adb')),
            'transport_recoveries': recoveries,
            'scope': 'Exact native level-label reference, not pixel OCR; no HP-derived levels.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batched', action='store_true', help='Experimental batched transport; requires live parity validation')
    parser.add_argument('--persistent', action='store_true', help='Experimental framed shell transport; requires live parity validation')
    args = parser.parse_args()
    result = read_levels(args.adb, batched=args.batched, persistent=args.persistent)
    with args.output.open('x') as f:
        f.write(json.dumps(result, indent=2) + '\n')
    print(result['ordinary']['tick'], result['levels'])


if __name__ == '__main__':
    main()
