"""Review-gated, offline CPU terminal actor parity. Run this file before bot imports.

One parent owns acknowledgements and the canonical claim directory. Each case
has two persistent games and the same two games across a reaped actor process.
There is no learner, optimizer, engine checkpoint, retry or promotion path.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
from dataclasses import asdict
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import select
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT/'bot/pretrain_v1'
BASE = 'fe6d64214200679372f337bb37b33606f5c9997d'
AMENDMENT = '148ead65e3249649e14afa5e0c579fc087857c9d'
NEW_FILES = {str(Path(__file__).relative_to(ROOT)),
             'bot/pretrain_v1/tests/test_terminal_recycle_qualifier.py',
             'bot/pretrain_v1/checks/TERMINAL-RECYCLE-QUALIFICATION.md'}
INPUT = Path('/mpac/sdicks02/scratch/pretrain-v1-dev')
READINESS = INPUT/'rl-readiness'
BUNDLE = READINESS/'registered-driver-inputs-r44-v2'
RUNTIME = Path('/mpac/sdicks02/repos/pretrain-v1-rl-runtime-0dcab45f7-joint')
ACTOR_SOURCE = Path('/mpac/sdicks02/repos/pretrain-v1-rl-actors-0dcab45f7-joint')
MANIFEST = READINESS/'joint-manifest.json'
MANIFEST_SHA = '60b94e875dfe856e8bd712ee6947c7f3998ecccc50a2972d20fa4f35e1f2eaee'
MAP_SHAS = {'files': '380c8141ab1c3cc26ea9490869b0023be9e37481532cdbeda75817462410bd30',
            'source_files': '43c20b2df9880af8634e1cd3efefb8ae369e3dad615af7f75bc830b59a9c6583'}
ANCHORS = {'M': '947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4',
           'S100': '74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f'}
POLICIES = {'M': 'a97cb49e7f9795a61753b445ab5059781bcb37cdc1f3fafaa6ad7f33978f3be0',
            'S100': 'b2c50b6fec019b741efd582ed784953a31b4abfdfdc6498f92c0813090183164'}
SELECTIONS = {'M': '84e87fe5a7cfef3523d4445178e3ca43bf83e9799129b48e35dee0c2d1a9320f',
              'S100': 'cad9ccc1cd0c1b5dc31c4e00e5c13b86817216c5ecfe701002658af675569500'}
CONFIGS = {'M': 'b8e2fa174e9eed781f0fb4a8392fef63215489115a1c251e11adfe32e4c01304',
           'S100': '0ac32a186c6ebc68cef69d6f6a223575d6d15b67b1f49ff33ba2bd603faf040b'}
LIMITS = dict(total_games=16, games_per_case_arm=2, active_workers=1,
              worker_seconds=600, parent_seconds=3600, control_seconds=30,
              poll_seconds=0.1, worker_rss_bytes=2 << 30, parent_rss_bytes=1 << 30,
              output_bytes=2 << 30, max_ticks=6001, max_polls_per_game=1183,
              budget_steps=8192, quota_steps=257, chunk_rows=128)
NAMESPACE = 'pv1-offline-terminal-recycle-v1'
LEASE_KEYS = ('CLASHER_LEASE_STOP_FILE', 'CLASHER_LEASE_JOB', 'CLASHER_LEASE_STOP_BY_UTC')
ARRAY_KEYS = {*('f_'+k for k in ('ent', 'ent_mask', 'ev', 'ev_mask', 'rev', 'rev_mask',
                                'tow', 'hand', 'glob', 'lag', 'slot_ok', 'alive')),
              'action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def durable(path, value):
    """Only fresh audit records; never replace a failed attempt's evidence."""
    path = Path(path)
    with open(path, 'xb') as out:
        out.write(encoded(value))
        out.flush()
        os.fsync(out.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKAGE/'checks'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], timeout=30)


def source_receipt():
    require(not git('status', '--porcelain', '--untracked-files=all').strip(), 'clean committed fixture required')
    git('merge-base', '--is-ancestor', BASE, 'HEAD')
    changes = git('diff', '--name-status', BASE, 'HEAD').decode().splitlines()
    require(set(changes) == {'A\t'+name for name in NEW_FILES}, 'new-files-only exact fe6 fixture required')
    names = git('ls-files', 'bot/pretrain_v1').decode().splitlines()
    files = {name: file_sha(ROOT/name) for name in names}
    actual = {str(p.relative_to(ROOT)) for p in PACKAGE.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts}
    require(actual == set(files), 'unexpected package input')
    return dict(base=BASE, commit=git('rev-parse', 'HEAD').decode().strip(),
                files=files, sha256=digest(files))


def cases(seat):
    # Eval seeds are <2**60; registered training occupies 2**60 + [0,3*2**48).
    # This fixture owns a separate 2**61 namespace, shared across the two sizes.
    levels = dict(Skeletons=8, Musketeer=7, IceGolem=7, Cannon=9,
                  Fireball=8, Zap=9, IceSpirit=8, HogRider=10)
    return [dict(sequence=i, seat=seat, seed=(1 << 61)+202610220000+2*seat+i,
                 decks=[list(levels), list(levels)],
                 levels=dict(cards={'0': levels, '1': levels}, towers={'0': 9, '1': 9}, planner='l11'),
                 opponent='scripted-pressure', namespace=NAMESPACE) for i in range(2)]


def match_levels(case):
    """Restore JSON seat mappings for the pinned play_match resolver."""
    return dict(case['levels'], **{key: {int(k): v for k, v in case['levels'][key].items()}
                                  for key in ('cards', 'towers')})


def runtime_record(source_sha256, pins, torch_version):
    return dict(native_sha256=pins['native_sha256'], gamedata_sha256=pins['gamedata_sha256'],
                runtime_source_sha256=MAP_SHAS['files'], actor_source_sha256=MAP_SHAS['source_files'],
                candidate_source_sha256=source_sha256, precision='float64', fixture=NAMESPACE,
                torch_version=torch_version, cpu_math_threads=1, cpu_interop_threads=1,
                attention='mha_fastpath=False,flash=False,mem_efficient=False,math=True')


def journal_sample(path, pending, poll, version):
    """Retain sampled bytes immediately, including a tail lost on fatal unwind."""
    import numpy as np
    require(pending is not None, 'observed decision has no pending raw sample')
    arrays = {'f_'+k: v for k, v in pending.features.items()}
    arrays.update(action=np.array([pending.action], np.int64), old_logp=np.array([pending.old_logp], np.float64),
                  old_value=np.array([pending.old_value], np.float64), actor=np.array([pending.actor], bool))
    parts = {}
    for key, array in sorted(arrays.items()):
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        parts[key] = stream.getvalue()
    header = encoded(dict(poll=poll, version=version, boundary_declined=pending.boundary_declined,
                          arrays={k: dict(dtype=str(arrays[k].dtype), shape=list(arrays[k].shape),
                                          bytes=len(raw)) for k, raw in parts.items()}))
    with open(path, 'ab') as out:
        out.write(struct.pack('!i', len(header)))
        out.write(header)
        for raw in parts.values():
            out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def verify_inputs(*, decisions=None):
    require(file_sha(MANIFEST) == MANIFEST_SHA, 'joint manifest pin')
    manifest = json.loads(MANIFEST.read_bytes())
    for key, root, count in [('files', RUNTIME, 9409), ('source_files', ACTOR_SOURCE, 17010)]:
        require(len(manifest[key]) == count and digest(manifest[key]) == MAP_SHAS[key], 'full manifest map pin')
        for name, sha in manifest[key].items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'manifest path escape')
            require(file_sha(root/name) == sha, 'input changed: '+str(root/name))
    refs = {str(MANIFEST): MANIFEST_SHA,
            str(BUNDLE/'excluded-seeds.json'): '8b02cf4015c911e542b2e02fc554a6ac313c3aaab36366f61b709a2d0378a948',
            str(BUNDLE/'training-populations.json'): '7964820f629403b46b1748379289b33f29102f5f96a7cc2cbb9dba5c67063dc6',
            str(BUNDLE/'documents/RL-DUAL-PREREG.md'): 'ef2bbab7facf31298be335ed50a4c0a176eb7d8949225c6ea32c9aaf76f56d93'}
    for size in ANCHORS:
        root = INPUT/'followup-20261022/next-anchors'/size
        refs.update({str(root/'anchor.pt'): ANCHORS[size], str(root/'selection.json'): SELECTIONS[size],
                     str(BUNDLE/(size+'-model-cfg.json')): CONFIGS[size]})
    for seed, sha in [(2026102101, 'f7f319d53ef86cc64e68b44bd76a41f4c387f022864e97dbe719520688671683'),
                      (2026102102, 'f369791e3e1920819807f8f3301d4590998391480159fe5c87f75b4131769a39'),
                      (2026102103, '34ce316b71d9b421386ed1d1a7c63467ab88494c32f88dd318c78e92831a58cd')]:
        refs[str(BUNDLE/f'configs-complete/banks-{seed}.json')] = sha
    for path, sha in refs.items():
        require(file_sha(path) == sha, 'input pin: '+path)
    decisions = decisions if decisions is not None else git('show', AMENDMENT+':reports/bot/pretrain-v1/DECISIONS.md')
    require(hashlib.sha256(decisions).hexdigest() == '6a6b736a9f6f5a7ecc614f201e1b1abea103e6143d3bdcc0bb8f244c2741752a',
            'DECISIONS amendment pin')
    excluded = set(json.loads((BUNDLE/'excluded-seeds.json').read_bytes())['seeds'])
    for path in refs:
        if Path(path).name.startswith('banks-'):
            bank = json.loads(Path(path).read_bytes())
            excluded.update(r['seed'] for r in bank['primary'])
            excluded.update(r['seed'] for rows in bank['dev'].values() for r in rows)
    fixture_seeds = {c['seed'] for seat in (0, 1) for c in cases(seat)}
    require(not fixture_seeds & excluded and all(2**61 <= s < 2**62 for s in fixture_seeds), 'seed overlap')
    return dict(files=refs, maps=MAP_SHAS, seed_namespace=NAMESPACE, cases=[cases(0), cases(1)],
                amendment=AMENDMENT, decisions=decisions.decode(), decisions_sha256=hashlib.sha256(decisions).hexdigest())


def review_receipt(path, sha, source):
    require(file_sha(path) == sha, 'review receipt changed')
    review = json.loads(Path(path).read_bytes())
    expected = dict(schema='pv1-terminal-recycle-review-v1', verdict='GO',
                    scope='offline-terminal-recycle-only', source_sha256=source['sha256'],
                    base=BASE, limits=LIMITS, model='gpt-6.1-sol', effort='high')
    require(all(review.get(k) == v for k, v in expected.items()), 'fresh independent exact-source review required')
    require(review.get('independent') is True and review.get('engine_resume_qualified') is False,
            'review independence/scope')
    return review


def proc(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = text[text.rindex(')')+2:].split()
    return dict(pid=pid, state=fields[0], ppid=int(fields[1]), sid=int(fields[3]),
                nice=int(fields[16]), start=int(fields[19]))


def rss(pid):
    status = Path(f'/proc/{pid}/status').read_text()
    for line in status.splitlines():
        if line.startswith('VmRSS:'):
            return int(line.split()[1])*1024
    # exit_mm can remove VmRSS before the task becomes a zombie or pidfd-ready.
    # Confirm the kernel reports no address space rather than waive a live RSS.
    pages = list(map(int, Path(f'/proc/{pid}/statm').read_text().split()))
    require(len(pages) >= 2 and pages[0] == pages[1] == 0, 'worker RSS unavailable')
    return 0


def retained_bytes(root):
    """One stat per output file, without a cached size or one-second blind spot."""
    total, todo = 0, [root]
    while todo:
        with os.scandir(todo.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    todo.append(entry.path)
                else:
                    total += entry.stat(follow_symlinks=False).st_size
    return total


def host_guard():
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:')))*1024
    require(available > 28*2**30 and os.getloadavg()[0] <= 90 and os.getpriority(os.PRIO_PROCESS, 0) >= 10,
            'require MemAvailable >28 GiB, load1 <=90 and nice >=10')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and all(os.environ.get(k) == '1' for k in
            ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')),
            'CUDA must be hidden and math thread environments must be 1')
    require(not any(k in os.environ for k in LEASE_KEYS), 'own-host fixture cannot inherit a lease')


class Wire:
    """Nonblocking frames with one deadline from first header byte to last byte."""
    def __init__(self, connection):
        self.connection = connection
        self.buffer = bytearray()
        self.frame_started = None
        connection.setblocking(False)

    def send(self, message, guard=lambda: None, timeout=None):
        timeout = LIMITS['control_seconds'] if timeout is None else timeout
        data = encoded(message)
        require(len(data) <= 2**20, 'control frame too large')
        data = struct.pack('!i', len(data))+data
        deadline = time.monotonic()+timeout
        ready = select.poll()
        ready.register(self.connection.fileno(), select.POLLOUT)
        while data:
            guard()
            require(time.monotonic() < deadline, 'control send timeout')
            if ready.poll(50):
                try:
                    data = data[self.connection.send(data):]
                except BlockingIOError:
                    pass

    def frame_check(self):
        if self.frame_started is not None:
            require(time.monotonic()-self.frame_started < LIMITS['control_seconds'],
                    'control frame timeout')

    def poll(self, wait_seconds=None):
        self.frame_check()
        if len(self.buffer) >= 4:
            n, = struct.unpack('!i', self.buffer[:4])
            require(0 < n <= 2**20, 'control frame size')
            if len(self.buffer) >= n+4:
                return self.pop(n)
        ready = select.poll()
        ready.register(self.connection.fileno(), select.POLLIN)
        remaining = LIMITS['poll_seconds'] if wait_seconds is None else wait_seconds
        if self.frame_started is not None:
            remaining = min(remaining, self.frame_started+LIMITS['control_seconds']-time.monotonic())
        if ready.poll(max(0, int(remaining*1000))):
            while True:
                # Stop exactly at this frame's end; do not consume the next one.
                count = 4-len(self.buffer) if len(self.buffer) < 4 else n+4-len(self.buffer)
                try:
                    part = self.connection.recv(min(65536, count))
                except BlockingIOError:
                    break
                if not part:
                    raise EOFError('worker closed control within frame' if self.buffer else 'worker closed control')
                if self.frame_started is None:
                    self.frame_started = time.monotonic()
                self.buffer.extend(part)
                self.frame_check()
                if len(self.buffer) >= 4:
                    n, = struct.unpack('!i', self.buffer[:4])
                    require(0 < n <= 2**20, 'control frame size')
                    if len(self.buffer) == n+4:
                        break
        # Late bytes, including completion, cannot renew the first-byte deadline.
        self.frame_check()
        if len(self.buffer) < 4:
            return None
        n, = struct.unpack('!i', self.buffer[:4])
        require(0 < n <= 2**20, 'control frame size')
        if len(self.buffer) < n+4:
            return None
        return self.pop(n)

    def pop(self, n):
        message = json.loads(self.buffer[4:n+4])
        del self.buffer[:n+4]
        self.frame_started = None
        encoded(message)
        return message


# Minimal Linux x86_64 equivalent of the reviewed R37 pidfd syscalls. This file
# is hash-pinned by source_receipt; no operational supervisor module is imported.
_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.syscall.restype = ctypes.c_long


def pidfd_open(pid):
    require(sys.platform == 'linux' and os.uname().machine == 'x86_64'
            and ctypes.sizeof(ctypes.c_void_p) == 8, 'unsupported pidfd syscall ABI')
    fd = _LIBC.syscall(ctypes.c_long(434), ctypes.c_int(pid), ctypes.c_uint(0))
    if fd < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    return fd


def pidfd_signal(fd, sig):
    rc = _LIBC.syscall(ctypes.c_long(424), ctypes.c_int(fd), ctypes.c_int(sig),
                       ctypes.c_void_p(), ctypes.c_uint(0))
    if rc < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def cleanup_capability():
    """Exercise both syscalls on self and enable adoption before any worker spawn."""
    fd = pidfd_open(os.getpid())
    try:
        pidfd_signal(fd, 0)
    finally:
        os.close(fd)
    require(_LIBC.prctl(36, 1, 0, 0, 0) == 0, 'child subreaper required')


# This standalone parent has no other child-spawning paths during a worker.
# The hook is inert outside the ownership window and in the spawned process.
_ACTIVE_PARENT = None


def exclusive_spawn(event, args):
    owner = _ACTIVE_PARENT
    if owner is not None and owner.parent_identity['pid'] == os.getpid() and event in (
            'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.posix_spawn'):
        if event == 'subprocess.Popen' and owner.launching:
            owner.launching = False  # One audit permit for the recorded Popen.
            return
        owner.note_failure('dedicated parent forbids concurrent child launches')
        raise RuntimeError('dedicated parent forbids concurrent child launches')


sys.addaudithook(exclusive_spawn)


class OwnedWorker:
    """One child-free, single-thread parent owns one launch and all its adoptees.

    Baseline children refuse launch rather than risk adopting their unseen forks.
    The frozen standalone caller and guard must not spawn through native extensions.
    Python spawn paths are rejected by the scoped audit hook. No shared-parent API.
    """
    def __init__(self, command, connection, log, *, guard=host_guard, seconds=None, output_root=None):
        global _ACTIVE_PARENT
        require(_ACTIVE_PARENT is None, 'dedicated parent already owns a worker')
        self.parent_identity = proc(os.getpid())
        require(self.valid_identity(self.parent_identity, os.getpid()), 'parent identity missing PID/start')
        self.owned, self.pidfds = {}, {}
        self.unresolved = set()
        self.failure = None
        self.launching = False
        self.child = None
        self.identity = None
        _ACTIVE_PARENT = self
        try:
            # Reserve before taking the baseline so a Python signal handler's
            # launch cannot slip between an empty baseline and the reservation.
            self.baseline = sorted(self.children(os.getpid()))
            require(not self.baseline, 'dedicated parent requires no preexisting children')
            require(len(list(Path('/proc/self/task').iterdir())) == 1, 'dedicated parent requires one thread')
            cleanup_capability()  # Unsupported kernel/ABI/permissions refuse before Popen.
            self.guard = guard
            self.seconds = LIMITS['worker_seconds'] if seconds is None else seconds
            self.started = time.monotonic()
            self.peak_rss = 0
            self.output_root = output_root
            self.launching = True
            try:
                self.child = subprocess.Popen(command, pass_fds=(connection.fileno(),), start_new_session=True,
                                              stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            finally:
                self.launching = False
        except BaseException:
            _ACTIVE_PARENT = None  # No Popen child exists on this path.
            raise
        # Identity read failures after Popen belong to monitored cleanup, never an
        # exception from __init__ that strands a child without its OwnedWorker.
        try:
            identity = proc(self.child.pid)
            require(self.valid_identity(identity, self.child.pid), 'worker identity missing PID/start')
            self.identity = identity
            self.owned[self.child.pid] = identity
        except BaseException as ex:
            self.unresolved.add(self.child.pid)
            self.note_failure(str(ex))

    @staticmethod
    def valid_identity(identity, pid):
        return (isinstance(identity, dict) and identity.get('pid') == pid
                and type(identity.get('start')) is int and identity['start'] > 0)

    def note_failure(self, message):
        if self.failure is None:
            self.failure = dict(error=repr(RuntimeError(message)), traceback=''.join(traceback.format_stack()))

    def release(self):
        global _ACTIVE_PARENT
        require(not self.children(os.getpid()), 'dedicated parent still has children')
        require(not any(self.valid_identity(p := proc(pid), pid) and p['start'] == identity['start']
                        for pid, identity in self.owned.items()), 'owned lifetime still present')
        for fd in self.pidfds.values():
            os.close(fd)
        self.pidfds.clear()
        if _ACTIVE_PARENT is self:
            _ACTIVE_PARENT = None

    @staticmethod
    def children(pid):
        children = set()
        try:
            threads = list(Path(f'/proc/{pid}/task').iterdir())
        except (FileNotFoundError, ProcessLookupError):
            return children
        for thread in threads:
            try:
                children.update(map(int, (thread/'children').read_text().split()))
            except (FileNotFoundError, ProcessLookupError):
                pass
        return children

    def pin(self, pid, identity):
        if pid in self.pidfds:
            return
        try:
            fd = pidfd_open(pid)
        except OSError as ex:
            if ex.errno == errno.ESRCH:
                return
            raise
        try:
            current = proc(pid)
            require(current is not None and current['start'] == identity['start'], 'pidfd PID identity changed')
            self.pidfds[pid] = fd
        except BaseException:
            os.close(fd)
            raise

    def collect(self):
        # Kernel enumeration is restricted to this parent and exact owned trees.
        # Single launch + empty baseline make every new direct child attributable
        # even after setsid and reparenting. Never infer ownership from a SID.
        parent = proc(os.getpid())
        require(_ACTIVE_PARENT is self and self.valid_identity(parent, os.getpid())
                and all(parent[k] == self.parent_identity[k] for k in ('pid', 'start', 'ppid', 'sid')),
                'dedicated parent identity changed')
        require(len(list(Path('/proc/self/task').iterdir())) == 1, 'dedicated parent requires one thread')
        candidates = self.children(os.getpid())
        todo = [pid for pid, identity in self.owned.items()
                if self.valid_identity(p := proc(pid), pid) and p['start'] == identity['start']]
        seen = set()
        while todo or candidates:
            candidates.update(todo)
            todo = []
            for pid in candidates-seen:
                seen.add(pid)
                p = proc(pid)
                if not self.valid_identity(p, pid):
                    # A transient read must fail the attempt, and must not turn an
                    # enumerated but unidentifiable child into an empty receipt.
                    self.unresolved.add(pid)
                    self.note_failure('enumerated child identity missing PID/start')
                    continue
                self.unresolved.discard(pid)
                if pid in self.owned:
                    require(p['start'] == self.owned[pid]['start'], 'owned PID identity changed')
                elif p['ppid'] == os.getpid() or p['ppid'] in self.owned:
                    require(p['start'] >= self.parent_identity['start'], 'ambiguous adopted child lifetime')
                    self.owned[pid] = p
                    if pid == self.child.pid and self.identity is None:
                        self.identity = p
                else:
                    self.note_failure('enumerated child ownership changed')
                    continue
                if pid != self.child.pid:
                    # Discovery itself latches failure, including during drain.
                    self.note_failure('fixture worker spawned an extra process')
                todo.extend(self.children(pid)-seen)
            candidates = set()
        # Discover the full set before any pin attempt can fail.
        for pid, identity in self.owned.items():
            if self.valid_identity(p := proc(pid), pid) and p['start'] == identity['start']:
                self.pin(pid, identity)

    def check(self):
        self.guard()
        require(time.monotonic()-self.started < self.seconds, 'worker wall timeout')
        require(rss(os.getpid()) <= LIMITS['parent_rss_bytes'], 'parent RSS limit')
        self.collect()
        require(self.failure is None, self.failure['error'] if self.failure else '')
        require(self.identity is not None, 'worker identity missing PID/start')
        # Check all retained output on every monitor pass, including after done.
        if self.output_root is not None:
            require(retained_bytes(self.output_root) <= LIMITS['output_bytes'], 'retained output limit')
        current = proc(self.child.pid)
        if current is None:
            require(self.child.returncode is not None, 'worker identity missing')
            return
        require(current['start'] == self.identity['start'], 'worker identity changed')
        if current['state'] not in ('Z', 'X'):
            try:
                used = rss(self.child.pid)
            except (FileNotFoundError, ProcessLookupError, StopIteration):
                current = proc(self.child.pid)
                require(current is None or current['state'] in ('Z', 'X'), 'worker RSS unavailable')
            else:
                self.peak_rss = max(self.peak_rss, used)
        require(self.peak_rss <= LIMITS['worker_rss_bytes'] and
                (current is None or current['nice'] >= 10), 'worker RSS/nice limit')

    def signal_exact(self, pid, sig):
        identity = self.owned[pid]
        current = proc(pid)
        if current is None:
            return
        require(current['start'] == identity['start'], 'cleanup PID identity changed')
        if current['state'] in ('Z', 'X'):
            return
        self.pin(pid, identity)
        fd = self.pidfds[pid]
        ready = select.poll()
        ready.register(fd, select.POLLIN)
        if ready.poll(0):  # Held lifetime exited, even if the numeric PID was reused.
            return
        current = proc(pid)
        require(current is not None and current['start'] == identity['start'], 'cleanup PID identity changed')
        try:
            pidfd_signal(fd, sig)
        except OSError as ex:
            if ex.errno != errno.ESRCH:
                raise

    def finish(self, *, failed, failure=None):
        self.failure = self.failure or failure
        errors = []
        if not failed:
            try:
                while True:
                    cycle = time.monotonic()
                    self.check()
                    if self.child.poll() is not None:
                        break
                    ready = select.poll()
                    ready.register(self.pidfds[self.child.pid], select.POLLIN)
                    remaining = min(self.started+self.seconds, cycle+LIMITS['poll_seconds'])-time.monotonic()
                    ready.poll(max(0, int(remaining*1000)))
            except BaseException as ex:
                self.failure = self.failure or dict(error=repr(ex), traceback=traceback.format_exc())
                failed = True
        # One bounded cleanup window, shared by every discovered lifetime.
        if not hasattr(self, 'cleanup_deadline'):
            self.cleanup_deadline = time.monotonic()+5
        deadline = self.cleanup_deadline
        while True:
            try:
                self.collect()
            except BaseException as ex:
                errors.append(repr(ex))
            # Continue with every known identity even if discovery/pinning failed.
            for pid in list(self.owned):
                try:
                    self.signal_exact(pid, signal.SIGKILL)
                except BaseException as ex:
                    errors.append(f'{pid}: {ex!r}')
            self.child.poll()  # Reap the direct child before adopted descendants.
            for pid in list(self.owned):
                current = proc(pid)
                if pid != self.child.pid and current is not None and \
                        current['start'] == self.owned[pid]['start'] and current['ppid'] == os.getpid():
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            # Re-enumerate after exit/reap: children can be adopted during
            # signal delivery or wait. Empty known lifetimes alone is not
            # a fixed point. Any discovery here also latches failure.
            try:
                self.collect()
            except BaseException as ex:
                errors.append(repr(ex))
            survivors = [pid for pid, identity in self.owned.items()
                         if self.valid_identity(p := proc(pid), pid) and p['start'] == identity['start']]
            pending = self.children(os.getpid())
            if (not survivors and not pending) or time.monotonic() >= deadline:
                break
            time.sleep(min(.05, max(0, deadline-time.monotonic())))
        if not survivors and not pending and not self.unresolved:
            self.release()
        return dict(source_process=self.identity, direct_pid=self.child.pid, owned_processes=list(self.owned.values()),
                    retained_pidfd_pids=sorted(self.pidfds), cleanup_deadline=self.cleanup_deadline,
                    ownership_boundary=dict(parent=self.parent_identity, baseline=self.baseline,
                                            protocol='exclusive-child-free-parent-v1'),
                    unresolved_pids=sorted(self.unresolved), pending_children=sorted(pending),
                    exitcode=self.child.returncode, reaped=self.child.returncode is not None and not survivors and not pending and not self.unresolved,
                    survivors=survivors, cleanup_errors=sorted(set(errors)), original_failure=self.failure,
                    peak_rss_bytes=self.peak_rss, wall_seconds=time.monotonic()-self.started,
                    failed=failed or self.failure is not None or bool(errors) or bool(survivors)
                    or bool(pending) or bool(self.unresolved) or self.child.returncode != 0)


def compare_records(expected, actual, where='record'):
    """Report the first exact difference, including missing/extra list entries."""
    require(type(expected) is type(actual), f'{where}: type changed')
    if isinstance(expected, dict):
        require(expected.keys() == actual.keys(), f'{where}: missing/extra keys')
        for key in expected:
            compare_records(expected[key], actual[key], where+'.'+str(key))
    elif isinstance(expected, list):
        require(len(expected) == len(actual), f'{where}: missing/extra rows {len(expected)} != {len(actual)}')
        for i, (a, b) in enumerate(zip(expected, actual)):
            compare_records(a, b, where+f'[{i}]')
    else:
        require(expected == actual, f'{where}: {expected!r} != {actual!r}')


def compare_game_artifacts(expected_dir, actual_dir, sequence):
    """Locate a failed comparison down to a poll or array byte, without replay."""
    a, b = Path(expected_dir), Path(actual_dir)
    left = (a/f'game-{sequence}-polls.jsonl').read_bytes().splitlines()
    right = (b/f'game-{sequence}-polls.jsonl').read_bytes().splitlines()
    require(len(left) == len(right), f'game {sequence}: missing/extra observed polls')
    for i, (x, y) in enumerate(zip(left, right)):
        require(x == y, f'game {sequence} observer poll {i}: {x!r} != {y!r}')
    raw = [(p/f'game-{sequence}-samples.bin').read_bytes() for p in (a, b)]
    if raw[0] != raw[1]:
        offset = next((i for i, (u, v) in enumerate(zip(*raw)) if u != v), min(map(len, raw)))
        raise RuntimeError(f'game {sequence}: sampled array journal changed at byte {offset}')
    left = json.loads((a/f'game-{sequence}.json').read_bytes())['publications']
    right = json.loads((b/f'game-{sequence}.json').read_bytes())['publications']
    require(len(left) == len(right), f'game {sequence}: missing/extra publications')
    maps = [{file_sha(p): p for p in root.glob('raw/chunk-*/manifest.json')} for root in (a, b)]
    for x, y in zip(left, right):
        paths = [mapping[row['manifest_sha256']] for mapping, row in zip(maps, (x, y))]
        manifests = [json.loads(p.read_bytes()) for p in paths]
        require(manifests[0]['arrays'].keys() == manifests[1]['arrays'].keys(), 'missing/extra raw arrays')
        for key in manifests[0]['arrays']:
            entries = [m['arrays'][key] for m in manifests]
            raw = [(p.parent/e['file']).read_bytes() for p, e in zip(paths, entries)]
            if raw[0] != raw[1]:
                offset = next((i for i, (u, v) in enumerate(zip(*raw)) if u != v), min(map(len, raw)))
                raise RuntimeError(f'game {sequence}, publication {x["sequence"]}, array {key}, '
                                   f'first changed NPY byte {offset}; headers {entries}')
        compare_records(manifests[0], manifests[1], f'game{sequence}.publication{x["sequence"]}')


def validate_publication(message, state, case, raw_root):
    """Parent checks every retained NPY byte before the synchronous permit."""
    import numpy as np
    path = Path(message['manifest'])
    require(path.name == 'manifest.json' and path.parent.name.startswith('chunk-')
            and path.parent.parent.resolve() == Path(raw_root).resolve() and not path.is_symlink(), 'publication path')
    raw = path.read_bytes()
    receipt = message['receipt']
    require(hashlib.sha256(raw).hexdigest() == receipt['manifest_sha256'], 'publication manifest digest')
    manifest = json.loads(raw)
    require(manifest['schema'] == 1, 'publication schema')
    require(digest(manifest['runtime_manifest']) == state['runtime_provenance_sha256'], 'publication runtime')
    meta, boundary = manifest['chunk'], message['boundary']
    require(all(meta[k] == state[k] for k in ('actor_id', 'seed', 'anchor_sha256'))
            and meta['provenance_sha256'] == state['runtime_provenance_sha256']
            and meta['opponent_id'] == case['opponent'], 'publication actor/input pins')
    require(message['sequence'] == state['publication_sequence'], 'publication cursor gap/duplicate')
    require(meta['version'] == state['version'] and meta['policy_sha256'] == state['policy_sha256'], 'publication policy')
    arrays, entries, total = {}, manifest['arrays'], len(raw)
    require(set(entries) == ARRAY_KEYS, 'missing/extra publication arrays')
    for key, entry in entries.items():
        require(entry['file'] == key+'.npy', 'array path')
        p = path.parent/entry['file']
        require(p.stat().st_size == entry['bytes'] and file_sha(p) == entry['sha256'], 'raw array changed: '+key)
        array = np.load(p, allow_pickle=False)
        require(str(array.dtype) == entry['dtype'] and list(array.shape) == entry['shape'], 'array dtype/shape')
        arrays[key] = array
        total += entry['bytes']
    n = receipt['rows']
    require(total == receipt['bytes'] and 0 < n <= LIMITS['chunk_rows'], 'receipt byte/row count')
    require(len(arrays['action']) == n == meta['generated_steps'] == receipt['generated_steps'], 'row count')
    ticks = list(map(int, arrays['f_glob'][:, 0]))  # checked below against production F.G_TICK in worker
    require(message['ticks'] == ticks == list(range(state['next_tick'], state['next_tick']+5*n, 5)),
            'missing/extra/gap poll row')
    require(n <= state['remaining_quota'] and state['generated_steps']+n < LIMITS['budget_steps'], 'quota/budget overshoot')
    state['generated_steps'] += n
    state['remaining_quota'] -= n
    state['boundary_declined_steps'] += meta['boundary_declined_steps']
    terminal = bool(arrays['terminated'][-1])
    require(not arrays['terminated'][:-1].any() and boundary['terminal'] == terminal, 'terminal rows')
    actual = message['actual']
    require(actual['terminal'] is terminal and
            (ticks[-1] <= actual['ticks'] <= ticks[-1]+5 if terminal else actual['ticks'] == ticks[-1]+5),
            'actual terminal/tick provenance')
    require(actual['winner'] is None or (terminal and type(actual['winner']) is int and actual['winner'] in (0, 1)),
            'actual winner provenance')
    reward = 0. if actual['winner'] is None else (1. if actual['winner'] == case['seat'] else -1.)
    require(bool((arrays['reward'][:-1] == 0).all()) and float(arrays['reward'][-1]) == reward
            and (not terminal or meta['bootstrap'] == 0.), 'reward/bootstrap provenance')
    reason = 'quota' if state['remaining_quota'] == 0 else 'terminal' if terminal else 'chunk'
    require(boundary['reason'] == reason and boundary['unfinished'] is False
            and boundary['generated_steps'] == state['generated_steps']
            and boundary['remaining_budget'] == LIMITS['budget_steps']-state['generated_steps']
            and boundary['remaining_quota'] == state['remaining_quota']
            and boundary['boundary_declined_steps'] == state['boundary_declined_steps'], 'boundary ledger')
    require(message['case'] == case, 'publication case changed')
    state['publication_sequence'] += 1
    state['next_tick'] += 5*n
    if reason == 'quota':
        state['version'] += 1
        state['remaining_quota'] = LIMITS['quota_steps']
    return dict(version=state['version'], policy_sha256=state['policy_sha256'],
                quota_steps=LIMITS['quota_steps'] if reason == 'quota' else None), manifest


def worker(spec_path, control_fd):
    """Only this entry imports bot, after the full production bootstrap."""
    spec = json.loads(Path(spec_path).read_bytes())
    out = Path(spec['out'])
    result = dict(status='failed', engine_resume_qualified=False)
    connection = socket.socket(fileno=control_fd)
    try:
        host_guard()
        source = spec['source']
        require({name: file_sha(ROOT/name) for name in source['files']} == source['files'], 'worker source changed')
        require(digest(source['files']) == source['sha256'], 'worker source digest')
        review_receipt(spec['review'], spec['review_sha256'], source)
        require(verify_inputs(decisions=spec['inputs']['decisions'].encode()) == spec['inputs'], 'worker inputs changed')
        boot = helper('terminal_engine_bootstrap', 'check_ours_producer.py')
        rt, lineage = boot.bootstrap(RUNTIME, ACTOR_SOURCE, MANIFEST)
        require(rt.root == RUNTIME.resolve() and rt.native_dir.resolve() == RUNTIME/'native', 'wrong runtime root/native')
        require(lineage['runtime_manifest_sha256'] == MAP_SHAS['files']
                and lineage['actor_manifest_sha256'] == MAP_SHAS['source_files'], 'bootstrap lineage')
        import torch
        from bot.pretrain_v1 import stream_actor as A, actor_worker as W, rl_driver as D
        from bot.pretrain_v1 import featurize as F, policy, operational_rejections as O
        from bot.pretrain_v1.lease_adapter import LeaseStopAdapter
        from bot.pretrain_v1.sim_ours import bind_matches
        from bot.players.ours import play_match
        from bot.eval.headline import make_player
        boot.check_origins(RUNTIME, ACTOR_SOURCE)
        require(LeaseStopAdapter.from_environment() is None, 'no leased host')
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        require(not torch.cuda.is_initialized() and F.G_TICK == 0, 'CPU/tick contract')
        size, seat = spec['size'], spec['seat']
        anchor = INPUT/'followup-20261022/next-anchors'/size/'anchor.pt'
        model, checkpoint = policy.load(anchor)
        require(checkpoint['cfg'] == json.loads((BUNDLE/(size+'-model-cfg.json')).read_bytes())
                and checkpoint.get('admission', {}).get('eligible') is True
                and float(model.gate_bias) == checkpoint['gate_bias'], 'selected policy construction')
        model.double().eval().requires_grad_(False)
        require(A.policy_sha256(model) == POLICIES[size], 'reviewed FP64 policy pin')
        runtime = runtime_record(source['sha256'], rt.pins, str(torch.__version__))
        queue = A.AtomicChunkQueue(out/'raw', max_bytes=LIMITS['output_bytes'], max_chunks=64, runtime_manifest=runtime)
        cursor = spec['cursor']
        sequence = cursor['publication_sequence']
        game_sequence = cursor['next_game_sequence']
        commands, publications, polls = [], [], []
        current_case = None

        def publish(c, boundary):
            nonlocal sequence
            host_guard()
            actual = D.public_evidence(play_match, actor)
            require(actual['terminal'] == boundary.terminal == bool(c.terminated[-1]), 'true terminal provenance')
            for i, action in enumerate(c.action):
                if action < F.NOOP:
                    card = F.catalog().cards[int(c.features['hand'][i, int(action)//576, F.H_CARD])-2]['name']
                    commands.append(dict(tick=int(c.features['glob'][i, F.G_TICK]), action=int(action),
                                         card=card, version=c.version, policy_sha256=c.policy_sha256))
            receipt = queue.write(c)  # Retained forever; ACK never deletes qualification data.
            message = dict(kind='publish', sequence=sequence, receipt=asdict(receipt), case=current_case,
                           manifest=str(queue.root/receipt.name/'manifest.json'), boundary=asdict(boundary),
                           ticks=list(map(int, c.features['glob'][:, F.G_TICK])), actual=actual)
            D.send(connection, message, LIMITS['control_seconds'])
            permit = D.receive(connection, LIMITS['control_seconds'])
            require(permit['kind'] == 'permit' and permit['sequence'] == sequence, 'publication acknowledgement')
            publications.append(dict(sequence=sequence, boundary=asdict(boundary),
                                     manifest_sha256=receipt.manifest_sha256, actual=actual))
            sequence += 1
            return A.PolicyUpdate(permit['version'], permit['policy_sha256'],
                model.state_dict() if boundary.reason == 'quota' else None, permit['quota_steps'])

        claims = Path(spec['claims'])
        require(claims.resolve(strict=True) == claims and
                [claims.stat().st_dev, claims.stat().st_ino] == spec['claim_identity'], 'canonical claim directory changed')
        if spec.get('restore'):
            cp = spec['restore']
            actor = W.ActorCheckpoint.restore_record(cp['record'], model, publish,
                expected_sha256=cp['sha256'], driver_state=cursor, claim_directory=spec['claims'])
        else:
            actor = A.StreamingPolicyOursPlayer(model, publish, actor_id=spec['actor_id'], seed=spec['seed'],
                anchor_sha256=ANCHORS[size], provenance_sha256=A.manifest_sha256(runtime),
                opponent_id='scripted-pressure', budget_steps=LIMITS['budget_steps'], quota_steps=LIMITS['quota_steps'],
                chunk_rows=LIMITS['chunk_rows'], expected_policy_sha256=POLICIES[size])
        # The original R7 leak fix stays in the production actor. No model trace
        # or Session is retained by this fixture after its owning game closes.
        require(actor.provenance_sha256 == cursor['runtime_provenance_sha256'], 'cursor runtime')
        result.update(identity=W.process_identity(), runtime=runtime, games=[])
        D.send(connection, dict(kind='ready', identity=W.process_identity(), runtime=runtime,
                               restored=bool(spec.get('restore'))))
        def observer(view, decision):
            D.execution_ok(decision.stats or {})
            if view.seat == seat:
                host_guard()
                require(actor.generated_steps <= 2*LIMITS['max_polls_per_game'], 'poll budget')
            row = dict(tick=view.tick, seat=view.seat, action=int(decision.action),
                       wait_ticks=decision.wait_ticks, stats=decision.stats, can_act=bool(view.can_act))
            polls.append(row)
            if view.seat == seat:
                journal_sample(out/f'game-{game_sequence}-samples.bin', actor.pending, row, actor.version)
            with open(out/f'game-{game_sequence}-polls.jsonl', 'ab') as stream:
                stream.write(encoded(row)+b'\n')

        with helper('terminal_math_backend', 'qualify_fp64.py').math_backend(torch):
            for current_case in cases(seat)[game_sequence:spec['end_game']]:
                commands, publications, polls = [], [], []
                opponent = make_player(rt, current_case['opponent'])
                require(opponent.name == 'scripted-pressure' and opponent.style == 'pressure'
                        and opponent.deadline_seconds is None, 'actual scripted opponent identity')
                opponent_pin = dict(spec=current_case['opponent'], cls=type(opponent).__module__+'.'+type(opponent).__name__,
                                    style='pressure', card_scope='c56', mask_version=1,
                                    source_sha256=file_sha(ACTOR_SOURCE/'bot/players/variants.py'),
                                    controller_sha256=file_sha(RUNTIME/'src/clasher/rl/public_scripted_opponent.py'),
                                    c56_controller_sha256=file_sha(RUNTIME/'src/clasher/rl/c56_scripted.py'))
                levels = match_levels(current_case)
                before = actor.generated_steps
                durable(out/f'game-{game_sequence}-start.json', dict(case=current_case, identity=W.process_identity(),
                        generated_steps=before, version=actor.version, policy_sha256=actor.policy_sha256, opponent=opponent_pin))
                with bind_matches({seat: actor, 1-seat: opponent}):
                    game = helper('terminal_match_audit', 'qualify_ppo_session.py').audited_match(
                        play_match, rt, {seat: actor, 1-seat: opponent}, seed=current_case['seed'],
                        decks=current_case['decks'], levels=levels, max_ticks=LIMITS['max_ticks'],
                        verbose=True, observer=observer,
                        evidence=lambda e: durable(out/f'failed-game-{game_sequence}.json', e))
                durable(out/f'game-{game_sequence}-engine.json', game)
                boot.check_origins(RUNTIME, ACTOR_SOURCE)
                require(game['terminal'] is True and actor.completed_games == game_sequence+1,
                        'nonterminal game cannot be replaced')
                require(0 < actor.generated_steps-before <= LIMITS['max_polls_per_game']
                        and actor.published_steps == actor.generated_steps and actor.discarded_steps == actor.unfinished_games == 0,
                        'missing or discarded rows')
                require(sum(p['seat'] == seat for p in polls) == actor.generated_steps-before, 'missing/extra observed samples')
                counters = {k: getattr(actor, k) for k in W._COUNTERS}
                stable_game = {k: v for k, v in game.items() if k not in ('timing', 'cpu_seconds')}
                item = dict(case=current_case, opponent=opponent_pin, engine=stable_game,
                            operational_rejections=O.game_counts(game, seat, submissions=commands),
                            publications=publications, polls_sha256=file_sha(out/f'game-{game_sequence}-polls.jsonl'),
                            samples_sha256=file_sha(out/f'game-{game_sequence}-samples.bin'),
                            polls=len(polls), counters=counters, counts=dict(actor.counts), version=actor.version,
                            remaining_quota=actor.remaining_quota, policy_sha256=actor.policy_sha256,
                            remaining_budget=actor.budget_steps-actor.generated_steps)
                item['sha256'] = digest(item)
                durable(out/f'game-{game_sequence}.json', item)
                result['games'].append(item)
                game_sequence += 1
                cursor = dict(cursor, publication_sequence=sequence, next_game_sequence=game_sequence)
                cp = W.ActorCheckpoint.capture(actor, cursor)
                cp.write(out/f'checkpoint-{game_sequence}.json')
                D.send(connection, dict(kind='game', record=item, checkpoint=cp.record, sha256=cp.sha256, cursor=cursor))
                retained = D.receive(connection, LIMITS['control_seconds'])
                require(retained == dict(kind='checkpoint_retained', sha256=cp.sha256, cursor=cursor),
                        'parent must durably retain exact checkpoint before source exit')
                # Source arm exits here. No actor call is permitted after capture.
                if game_sequence == spec['end_game']:
                    break
        boot.check_origins(RUNTIME, ACTOR_SOURCE)
        require(not torch.cuda.is_initialized(), 'CUDA initialized')
        result.update(status='completed-pending-review', cuda_initialized=False, optimizer_steps=0,
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                      origins=helper('terminal_origins', 'qualify_fp64.py').origins())
        D.send(connection, dict(kind='done'))
    except BaseException as ex:
        result.update(error=repr(ex), traceback=traceback.format_exc())
        raise
    finally:
        if 'actor' in locals():
            result['final_actor_counters'] = {k: getattr(actor, k) for k in W._COUNTERS}
            result['final_actor_state'] = dict(version=actor.version, remaining_quota=actor.remaining_quota,
                                               remaining_budget=actor.budget_steps-actor.generated_steps,
                                               failed=actor.failed, counts=dict(actor.counts))
        durable(out/'worker-result.json', result)
        connection.close()


def run_process(spec, out, state, *, command=None, guard=host_guard, seconds=None):
    """The same external monitor is exercised by engine-free subprocess tests."""
    out.mkdir()
    durable(out/'spec.json', spec)
    parent, child = socket.socketpair()
    wire = Wire(parent)
    command = command or [sys.executable, '-B', str(Path(__file__).resolve()), '--worker',
                          str(out/'spec.json'), '--control-fd', str(child.fileno())]
    command = [str(p).replace('{control_fd}', str(child.fileno())).replace('{spec}', str(out/'spec.json')) for p in command]
    records, checkpoint, ready, done = [], None, False, False
    failed, cleanup, failure = True, None, None
    with open(out/'worker.log', 'xb') as log:
        try:
            owned = OwnedWorker(command, child, log, guard=guard, seconds=seconds, output_root=out.parent)
        except BaseException:
            parent.close()
            raise
        finally:
            child.close()
        try:
            while not done:
                cycle = time.monotonic()
                owned.check()
                message = wire.poll(max(0, cycle+LIMITS['poll_seconds']-time.monotonic()))
                if message is None:
                    require(owned.child.poll() is None, 'worker exited without completion')
                    continue
                kind = message['kind']
                if kind == 'ready':
                    require(not ready and message['identity']['pid'] == owned.child.pid
                            and message['identity']['start'] == owned.identity['start']
                            and digest(message['runtime']) == state['runtime_provenance_sha256'], 'worker ready identity/runtime')
                    ready = True
                elif kind == 'publish':
                    require(ready, 'publication before readiness')
                    case = cases(spec['seat'])[state['next_game_sequence']]
                    permit, _ = validate_publication(message, state, case, out/'raw')
                    wire.send(dict(kind='permit', sequence=message['sequence'], **permit), owned.check)
                elif kind == 'game':
                    require(ready and message['cursor']['next_game_sequence'] == state['next_game_sequence']+1,
                            'game cursor gap/duplicate')
                    state['next_game_sequence'] += 1
                    require(message['record']['case'] == cases(spec['seat'])[state['next_game_sequence']-1]
                            and message['record']['engine']['terminal'] is True, 'completed case provenance')
                    state['next_tick'] = 90
                    checkpoint = dict(record=message['checkpoint'], sha256=message['sha256'])
                    durable(out/f'parent-retained-{state["next_game_sequence"]}.json', message)
                    require(digest(checkpoint['record']) == checkpoint['sha256'], 'parent retained checkpoint hash')
                    require(message['cursor'] == checkpoint['record']['driver_state'], 'checkpoint driver cursor')
                    expected_cursor = dict(spec['cursor'], publication_sequence=state['publication_sequence'],
                                           next_game_sequence=state['next_game_sequence'])
                    require(message['cursor'] == expected_cursor, 'parent independent cursor mismatch')
                    require(checkpoint['record']['source_process']['pid'] == owned.child.pid
                            and checkpoint['record']['source_process']['start'] == owned.identity['start'], 'checkpoint source PID/start')
                    require(checkpoint['record']['counters'] == dict(generated_steps=state['generated_steps'],
                            published_steps=state['generated_steps'], discarded_steps=0, unfinished_games=0,
                            completed_games=state['next_game_sequence'], boundary_declined_steps=state['boundary_declined_steps'])
                            and checkpoint['record']['remaining_quota'] == state['remaining_quota']
                            and checkpoint['record']['version'] == state['version'], 'checkpoint quota/version/counters')
                    records.append(message['record'])
                    wire.send(dict(kind='checkpoint_retained', sha256=checkpoint['sha256'], cursor=expected_cursor), owned.check)
                elif kind == 'done':
                    require(ready and len(records) == spec['end_game']-spec['cursor']['next_game_sequence'], 'missing games')
                    done = True
                else:
                    raise RuntimeError('unexpected worker message: '+str(kind))
            failed = False
        except BaseException as ex:
            failure = dict(error=repr(ex), traceback=traceback.format_exc())
            raise
        finally:
            try:
                cleanup = owned.finish(failed=failed, failure=failure)
            except BaseException as ex:
                cleanup = dict(status='cleanup-failed', source_process=owned.identity, direct_pid=owned.child.pid,
                               owned_processes=list(owned.owned.values()), unresolved_pids=sorted(owned.unresolved),
                               retained_pidfd_pids=sorted(owned.pidfds), original_failure=owned.failure or failure,
                               cleanup_error=repr(ex), cleanup_traceback=traceback.format_exc(), failed=True)
                if failure is None:
                    raise
            finally:
                parent.close()
                durable(out/'exit.json', cleanup)
    require(not cleanup['failed'] and cleanup['exitcode'] == 0, 'worker exit/cleanup failed: '+str(cleanup.get('original_failure')))
    return records, checkpoint, cleanup


def main_run(a):
    out = a.out.resolve()
    require(not out.exists() and Path('/mpac/sdicks02') in out.parents and ROOT not in out.parents,
            'fresh output outside source under local /mpac/sdicks02 required')
    out.mkdir(parents=True)
    result = dict(status='failed', test_only=True, promotable=False, engine_resume_qualified=False,
                  process_resume_qualified=False, science_rows=0, optimizer_steps=0, limits=LIMITS, cases=[])
    parent_deadline = time.monotonic()+LIMITS['parent_seconds']
    def parent_guard():
        host_guard()
        require(time.monotonic() < parent_deadline, 'parent wall timeout')

    old_handler = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('parent wall timeout')))
    signal.setitimer(signal.ITIMER_REAL, LIMITS['parent_seconds'])
    try:
        parent_guard()
        # Reap any fixture-only descendant after an erroneous worker forks.
        require(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'child subreaper required')
        source = source_receipt()
        require(source['sha256'] == a.source_sha256, 'explicit candidate source pin')
        review = review_receipt(a.review, a.review_sha256, source)
        inputs = verify_inputs()
        durable(out/'source-input-review.json', dict(source=source, inputs=inputs, review=review))
        claims = out/'claims'
        claims.mkdir(mode=0o700)
        claims = claims.resolve(strict=True)
        durable(out/'canonical-claims.json', dict(path=str(claims), device=claims.stat().st_dev, inode=claims.stat().st_ino))
        for size in ('M', 'S100'):
            for seat in (0, 1):
                schedule_sha = digest(cases(seat))
                # Worker and parent must construct exactly the same runtime identity.
                import torch
                require(not torch.cuda.is_initialized(), 'CPU parent')
                joint = json.loads(MANIFEST.read_bytes())
                runtime = runtime_record(source['sha256'], dict(native_sha256=joint['files']['native/clasher_core.abi3.so'],
                                         gamedata_sha256=joint['files']['gamedata.json']), str(torch.__version__))
                cursor = dict(publication_sequence=0, next_game_sequence=0, seed=cases(seat)[0]['seed'],
                              actor_id=f'{NAMESPACE}-{size}-seat{seat}', schedule_sha256=schedule_sha,
                              runtime_provenance_sha256=digest(runtime))
                initial = dict(publication_sequence=0, next_game_sequence=0, next_tick=90, generated_steps=0,
                               remaining_quota=LIMITS['quota_steps'], version=0, policy_sha256=POLICIES[size],
                               runtime_provenance_sha256=digest(runtime), actor_id=cursor['actor_id'], seed=cursor['seed'],
                               anchor_sha256=ANCHORS[size], boundary_declined_steps=0)
                common = dict(size=size, seat=seat, actor_id=cursor['actor_id'], seed=cursor['seed'],
                              source=source, inputs=inputs, review=str(a.review.resolve()), review_sha256=a.review_sha256,
                              claims=str(claims), claim_identity=[claims.stat().st_dev, claims.stat().st_ino], cursor=cursor)
                persistent_state = dict(initial)
                path = out/f'{size}-seat{seat}-persistent'
                persistent, _, _ = run_process(dict(common, out=str(path), end_game=2), path, persistent_state, guard=parent_guard)
                recycled_state = dict(initial)
                path = out/f'{size}-seat{seat}-source'
                first, checkpoint, exit_receipt = run_process(dict(common, out=str(path), end_game=1), path, recycled_state, guard=parent_guard)
                identity = checkpoint['record']['source_process']
                require(identity['pid'] == exit_receipt['source_process']['pid'] and exit_receipt['reaped']
                        and proc(identity['pid']) is None, 'restore before original process reaped')
                path = out/f'{size}-seat{seat}-successor'
                second, _, _ = run_process(dict(common, out=str(path), end_game=2, restore=checkpoint,
                    cursor=checkpoint['record']['driver_state']), path, recycled_state, guard=parent_guard)
                for sequence, arm in [(0, 'source'), (1, 'successor')]:
                    compare_game_artifacts(out/f'{size}-seat{seat}-persistent', out/f'{size}-seat{seat}-{arm}', sequence)
                compare_records(persistent, first+second, f'{size}.seat{seat}')
                compare_records(persistent_state, recycled_state, f'{size}.seat{seat}.final-ledger')
                result['cases'].append(dict(size=size, seat=seat, game_hashes=[r['sha256'] for r in persistent],
                                            original_process=identity, source_exit=exit_receipt))
                require(sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) <= LIMITS['output_bytes'], 'output cap')
        require(len(list(claims.iterdir())) == 4, 'one durable claim per actual handoff')
        result.update(status='completed-parity-pending-independent-postreview', engine_games=16,
                      source_sha256=source['sha256'], source_commit=source['commit'])
    except BaseException as ex:
        result.update(error=repr(ex), traceback=traceback.format_exc())
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        result.update(parent_process=dict(proc(os.getpid()), host=socket.gethostname(),
                                          boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()),
                      actual_games_started=len(list(out.glob('*/game-*-start.json'))),
                      retained_engine_results=len(list(out.glob('*/game-*-engine.json'))))
        durable(out/'result.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-source', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--review-sha256')
    parser.add_argument('--test-only', action='store_true')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--control-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.print_source:
        print(json.dumps(source_receipt(), indent=2))
    elif args.worker:
        worker(args.worker, args.control_fd)
    else:
        require(args.test_only and all((args.out, args.source_sha256, args.review, args.review_sha256)),
                'explicit test-only source and independent review pins required')
        main_run(args)


if __name__ == '__main__':
    main()
