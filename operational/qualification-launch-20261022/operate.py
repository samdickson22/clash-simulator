#!/usr/bin/env python3
"""Parent-operated R37 staging and separate qualification. No transport or lease writes."""
import argparse
import ctypes
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import secrets
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).absolute().parent
JOBS = Path('/mpac/sdicks02/jobs/clasher')
HOME = JOBS/'rl-qualification-launch-20261022'
DRIVER = HOME/'driver-fe6d642'
READY = Path('/mpac/sdicks02/repos/clasher-pv1-ready-20261022')
PYTHON = READY/'python/bin/python3.12'
SUPERVISOR = Path('/mpac/sdicks02/repos/clasher-pv1-lease-20261022/bot/pretrain_v1/lease_supervisor.py')
SUPERVISOR_SHA = '0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc'
WATCHERS = {'127x09': (3363731, 245569826), '127x12': (2219277, 903916746)}
LIMITS = {'source': (3, 4, 0, 300, 300), 'inputs': (3, 4, 0, 300, 1800),
          'soak': (40, 48, None, 600, 25200)}  # processes, PSS GiB, GPU GiB, reclaim grace, wall
READY_COUNTS = {'files': 9409, 'source_files': 17010}
THREADS = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


def utc(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()


def stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def absolute(path):
    path = os.fspath(path)
    require(path.startswith('/') and str(Path(path)) == path and '..' not in Path(path).parts,
            'noncanonical absolute path: '+path)
    return Path(path)


def below(path, root):
    path, root = absolute(path), absolute(root)
    require(root in path.parents, 'path outside '+str(root)+': '+str(path))
    return path


@contextmanager
def parent_fd(path, create=False):
    """Walk with dirfds, never following links, including during concurrent renames."""
    path = absolute(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parent.parts[1:]:
            if create:
                try:
                    os.mkdir(name, 0o755, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd, path.name
    finally:
        os.close(fd)


@contextmanager
def opened(path):
    with parent_fd(path) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'regular file required: '+str(path))
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            yield stream
    finally:
        os.close(fd)


def sha(path, tick=lambda: None):
    h = hashlib.sha256()
    with opened(path) as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            tick()
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    def number(value):
        result = float(value)
        require(math.isfinite(result), 'nonfinite JSON')
        return result
    def integer(value):
        require(len(value) <= 1024, 'JSON integer too long')
        return int(value)
    with opened(path) as stream:
        raw = stream.read(16 << 20)
        require(not stream.read(1), 'JSON exceeds 16 MiB')
    return json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                      parse_float=number, parse_constant=number)


def ref(value):
    require(set(value) == {'path', 'sha256'}, 'exact path/SHA reference required')
    below(value['path'], JOBS)
    require(re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None
            and value['sha256'] != '0'*64, 'real nonzero SHA required')
    return value


def pinned(value, tick=lambda: None):
    ref(value)
    require(sha(value['path'], tick) == value['sha256'], 'pin changed: '+value['path'])
    return Path(value['path'])


def verify(path, row, tick=lambda: None):
    require(sha(path, tick) == row['sha256'], 'hash changed: '+str(path))
    with opened(path) as stream:
        require(os.fstat(stream.fileno()).st_size == row['bytes'], 'size changed: '+str(path))


def copy_exact(src, dst, row, tick=lambda: None):
    """Exclusive create; an interrupted copy remains unusable and is never overwritten."""
    dst = below(dst, JOBS)
    verify(src, row, tick)
    with parent_fd(dst, create=True) as (parent, name):
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=parent)
        except FileExistsError:
            verify(dst, row, tick)
            return
        h, count = hashlib.sha256(), 0
        try:
            with opened(src) as stream, os.fdopen(fd, 'wb', closefd=False) as target:
                for block in iter(lambda: stream.read(4 << 20), b''):
                    tick()
                    target.write(block)
                    h.update(block)
                    count += len(block)
                target.flush()
                os.fsync(fd)
            require(h.hexdigest() == row['sha256'] and count == row['bytes'], 'source changed during copy')
            os.fsync(parent)
        finally:
            os.close(fd)


def write_new(path, value):
    path = below(path, HOME)
    with parent_fd(path, create=True) as (parent, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded(value)+b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)


def directory(path):
    below(path, HOME)
    with parent_fd(Path(path)/'.directory-check', create=True):
        pass


def package_pin():
    freeze = read_json(HERE/'freeze.json')
    for name, row in freeze.items():
        require(Path(name).name == name, 'invalid package filename')
        verify(HERE/name, row)
    require(set(freeze) == {'operate.py', 'cpu_probe.py', 'prepare_payload.py', 'test_operate.py', 'inventory.json', 'README.md'},
            'complete frozen package required')
    return sha(HERE/'freeze.json')


def r37():
    require(sha(SUPERVISOR) == SUPERVISOR_SHA, 'R37 source changed')
    # Load the bytes just hashed, rather than reopening source through an import loader.
    with opened(SUPERVISOR) as stream:
        raw = stream.read()
    require(hashlib.sha256(raw).hexdigest() == SUPERVISOR_SHA, 'R37 source raced')
    module = type(sys)('qualification_r37')
    module.__file__ = str(SUPERVISOR)
    exec(compile(raw, str(SUPERVISOR), 'exec'), module.__dict__)
    return module


def check_lease(S, host, seconds, now=None):
    """Read by path each time. Fresh means a valid watcher observation, not lease mtime."""
    now = time.time() if now is None else now
    raw = S.read_snapshot(str(Path(S.LEASE_DIR)/(host+'.json')))
    lease = S.lease_json(raw)
    require(isinstance(lease, dict), 'lease is not object')
    require(not S.lease_trigger(lease), 'lease reclaim/refused')
    deadline, cap, pss = S.validate_lease(lease, host)
    require(lease['project'] == 'clasher' and lease['status'] == 'active'
            and utc(lease['start_utc']) <= now, 'inactive/not-started lease')
    require(deadline <= utc('2026-10-25T07:53:00Z') and deadline > now+seconds,
            'insufficient lease horizon')
    state = Path(S.STATE_ROOT)/host
    watcher, status = read_json(state/'supervisor.json'), read_json(state/'status.json')
    require((watcher['pid'], watcher['start']) == WATCHERS[host] and watcher['boot'] == S.boot_id()
            and S.alive(watcher['pid'], watcher['start']), 'existing R37 watcher identity changed')
    observation = status['observed_lease']
    require(status['status'] == 'watching' and status.get('reason') is None
            and status['boot'] == watcher['boot']
            and 0 <= now-utc(status['utc']) <= 60
            and observation['valid'] is True and 0 <= now-observation['observed_at'] <= 60
            and observation['sha256'] == hashlib.sha256(raw).hexdigest()
            and status['lease_identity'] == S.lease_identity(lease), 'stale/ending R37 lease observation')
    require(not (state/'HALT').exists() and not (state/'RELEASE').exists(), 'R37 halted/released')
    return deadline, cap, pss


def validate_contract(c, inv, package, host):
    require(c['schema'] == 'qualification-operation-v1' and c['host'] == host and host in WATCHERS,
            'wrong contract host/schema')
    require(c['source_commit'] == inv['source_commit'] and c['source_sha256'] == inv['source_sha256']
            and c['package_sha256'] == package, 'changed source/package')
    for key in ('final_config', 'release', 'operational_review', 'r49'):
        ref(c[key])
    require(c['r49']['sha256'] == inv['r49_sha256'], 'R49 authority changed')
    require(c['out'] == str(HOME/'hosts'/host/'soak'), 'fixed fresh host output required')
    require(c['supervisor'] == {'path': str(SUPERVISOR), 'sha256': SUPERVISOR_SHA}, 'R37 pin required')
    destinations = set(inv['inputs']) | {str(DRIVER/name) for name in inv['source_files']}
    extras = c['extra_files']
    require(isinstance(extras, list) and 1 <= len(extras) <= 256, 'bounded explicit extra files required')
    for item in extras:
        ref({k: item[k] for k in ('path', 'sha256')})
        require(set(item) == {'path', 'sha256', 'bytes'} and type(item['bytes']) is int
                and 0 <= item['bytes'] <= 16 << 20, 'bounded extra file required')
        require(item['path'] not in destinations, 'duplicate or conflicting extra destination')
        # Extras are immutable new receipts/configs, never package code, runtime or prepared inputs.
        require(HOME not in Path(item['path']).parents
                and '/rl-input-roots-20261022/prepared-attempt2/' not in item['path'],
                'extra destination overlaps package/prepared inputs')
        protected = (JOBS/'lease-20261022', JOBS/'lease-1316-extension-20261022')
        require(not any(root == Path(item['path']) or root in Path(item['path']).parents for root in protected),
                'extra destination overlaps supervisor/R40 state; supply a new receipt copy')
        destinations.add(item['path'])
    refs = {(x['path'], x['sha256']) for x in extras}
    require(all((c[k]['path'], c[k]['sha256']) in refs for k in
                ('final_config', 'release', 'operational_review', 'r49')), 'authority/config missing from extras')


def check_authority(c, inv, lookup=lambda r: pinned(r)):
    config = read_json(lookup(c['final_config']))
    release = read_json(lookup(c['release']))
    review = read_json(lookup(c['operational_review']))
    lookup(c['r49'])
    require(config['host'] == c['host'] and config['size'] == {'127x09': 'M', '127x12': 'S100'}[c['host']]
            and config['qualification_only'] is True and config['workers'] == 32
            and config['precision'] == 'float64' and config['runtime'] == str(READY/'runtime')
            and config['actor_source'] == str(READY/'actor_source')
            and config['runtime_manifest']['sha256'] == inv['joint_sha256'], 'final config scope/runtime changed')
    for obj in (release, review):
        require(obj['host'] == c['host'] and obj['source_commit'] == inv['source_commit']
                and obj['source_sha256'] == inv['source_sha256']
                and obj['final_config'] == c['final_config'], 'authority source/config/host mismatch')
    require(release['schema'] == 'qualification-r40-release-v1' and release['status'] == 'released'
            and release['explicit_per_host_release'] is True and release['actual_measurement'] is True
            and release['exact_owned_tree_reaped'] is True and release['full_gpu_free'] is True
            and release['physical_measurement'] == config['gpu_admission']['process_measurement'],
            'missing explicit R40 physical release')
    require(utc(release['utc']) <= time.time(), 'release timestamp is in the future')
    reviewed_extras = [x for x in c['extra_files'] if x['path'] != c['operational_review']['path']]
    require(review['schema'] == 'qualification-operational-review-v1' and review['status'] == 'GO'
            and review['scope'] == 'separate-six-hour-qualification'
            and review['model'] == 'gpt-6.1-sol' and review['effort'] == 'high'
            and review['independent'] is True and review['package_sha256'] == c['package_sha256']
            and review['release'] == c['release'] and review['r49'] == c['r49']
            and review['extra_files_sha256'] == digest(reviewed_extras)
            and review['inventory_sha256'] == digest(inv)
            and review['phases'] == ['source', 'inputs', 'soak'], 'fresh independent operational review required')
    lookup(review['report'])
    original = inv['prepared_config_values'][c['host']]
    allowed = {'gate_receipt', 'qualification_gate_receipt', 'precision_registration',
               'league_schedule_registration', 'gpu_admission'}
    require({k: v for k, v in config.items() if k not in allowed}
            == {k: v for k, v in original.items() if k not in allowed}, 'final config changed science/inputs')
    gpu = config['gpu_admission']
    physical = read_json(lookup(gpu['process_measurement']))
    require(physical['status'] == 'pass' and physical['scope'] == 'full-cuda-process'
            and physical['size'] == config['size'] and physical['dtype'] == config['precision']
            and physical['anchor_sha256'] == config['anchor']['sha256']
            and type(gpu['peak_process_bytes']) is int
            and gpu['peak_process_bytes'] == physical['peak_process_bytes'] >= gpu['peak_reserved_bytes'] > 0,
            'physical process measurement required')
    # Resolve every explicitly supplied authority file before staging or admission.
    for item in c['extra_files']:
        lookup({k: item[k] for k in ('path', 'sha256')})
    qualification = read_json(lookup(config['qualification_gate_receipt']))
    for gate in qualification['gates'].values():
        lookup(gate['evidence'])
    precision = read_json(lookup(config['precision_registration']))
    for parity in precision['parity_evidence'].values():
        lookup(parity)
    lookup(gpu['measurement'])
    return config


def payload_rows(inv, c, phase):
    if phase == 'source':
        return [('source/'+n, str(DRIVER/n), row) for n, row in sorted(inv['source_files'].items())]
    rows = [('inputs/'+str(i), n, row) for i, (n, row) in enumerate(sorted(inv['inputs'].items()))]
    rows += [('extras/'+x['sha256'], x['path'], x) for x in c['extra_files']]
    return rows


def payload_lookup(incoming, c, inv):
    by_path = {x['path']: x for x in c['extra_files']}
    inputs = {n: (i, row) for i, (n, row) in enumerate(sorted(inv['inputs'].items()))}
    def lookup(value):
        ref(value)
        if value['path'] in inputs:
            i, row = inputs[value['path']]
            require(row['sha256'] == value['sha256'], 'input authority pin mismatch')
            path = incoming/'inputs'/str(i)
            verify(path, row)
            return path
        require(value['path'] in by_path and by_path[value['path']]['sha256'] == value['sha256'],
                'consumed receipt not explicitly supplied: '+value['path'])
        path = incoming/'extras'/value['sha256']
        verify(path, by_path[value['path']])
        return path
    return lookup


def verify_source(inv, tick=lambda: None):
    actual = set()
    for root, dirs, files in os.walk(DRIVER, followlinks=False):
        for name in dirs+files:
            path = Path(root)/name
            require(not path.is_symlink(), 'source link')
        for name in files:
            actual.add(str((Path(root)/name).relative_to(DRIVER)))
    require(actual == set(inv['source_files']), 'extra/missing staged source files, including tests/catalog')
    for name, row in inv['source_files'].items():
        verify(DRIVER/name, row, tick)
    py = {n: v['sha256'] for n, v in inv['source_files'].items()
          if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}
    require(digest(py) == inv['source_sha256'], 'source_digest mismatch')


def verify_ready(config, inv, tick=lambda: None):
    manifest_path = pinned(config['runtime_manifest'], tick)
    require(config['runtime_manifest']['sha256'] == inv['joint_sha256'], 'joint manifest changed')
    manifest = read_json(manifest_path)
    for key, location in (('files', 'runtime'), ('source_files', 'actor_source')):
        root, expected = Path(config[location]), manifest[key]
        require(len(expected) == READY_COUNTS[key], 'runtime/actor count changed')
        actual = set()
        for base, dirs, files in os.walk(root, followlinks=False):
            tick()
            for name in dirs+files:
                require(not (Path(base)/name).is_symlink(), 'ready tree contains link')
            actual.update(str((Path(base)/name).relative_to(root)) for name in files)
        require(actual == set(expected), 'extra/missing ready files')
        for name, pin in expected.items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts
                    and str(Path(name)) == name, 'unsafe ready manifest path')
            require(sha(root/name, tick) == pin, 'ready source changed: '+name)


def environment(cpu):
    env = os.environ.copy()  # Preserve R37 generation, CPU affinity and GPU visibility.
    for key in ('PYTHONPATH', 'PYTHONSTARTUP', 'PYTHONUSERBASE', 'PYTHONINSPECT',
                'CLASHER_ROOT', 'CLASHER_BOT_RUNTIME', 'CLASHER_EVAL_RUNTIME_ROOT',
                'CLASHER_DELAY_NATIVE_DIR', 'CLASHER_BOT_RUNTIME_PINS'):
        env.pop(key, None)
    env.update({k: '1' for k in THREADS})
    env.update(PYTHONHOME=str(READY/'python'), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
               XDG_CACHE_HOME=str(HOME/'cache'), TORCH_HOME=str(HOME/'cache/torch'),
               NUMBA_CACHE_DIR=str(HOME/'cache/numba'), TMPDIR=str(HOME/'tmp'))
    if cpu:
        env['CUDA_VISIBLE_DEVICES'] = ''
    return env


def check_resources(S, cap, pss, reserve_procs=0, reserve_pss=0):
    procs = S.scan()
    own = {pid: p for pid, p in procs.items() if S.is_clasher(p)}
    require(len(own)+reserve_procs <= cap, 'all-clasher process cap')
    require(sum(S.pss_bytes(pid) for pid in own)+reserve_pss*2**30 <= min(pss, 64)*2**30,
            'all-clasher PSS cap')
    mem, load = S.host_load()
    require(mem >= 32*2**30 and load <= 90 and all(p['nice'] >= 10 for p in own.values()),
            'host mem/load/nice guard')


def child_pids():
    """Kernel children of this wrapper only, including zombies and thread children."""
    out = set()
    for task in (Path('/proc')/str(os.getpid())/'task').iterdir():
        try:
            out.update(map(int, (task/'children').read_text().split()))
        except FileNotFoundError:
            pass  # A thread exited; surviving children transfer to the group leader.
    return out


class Job:
    def __init__(self, S, c, phase):
        self.S, self.c, self.phase = S, c, phase
        self.started, self.last = time.monotonic(), 0
        self.limit = LIMITS[phase][4]
        self.children = []
        self.peak_procs, self.peak_pss = 0, 0
        self.stopping = False
        self.stop_at = utc(os.environ['CLASHER_LEASE_STOP_BY_UTC'])
        start = S.proc_stat(os.getpid())[4]
        self.record = dict(boot=S.boot_id(), token=os.environ['CLASHER_LEASE_JOB'],
                           pid=os.getpid(), start=start, procs=[[os.getpid(), start]])
        require(re.fullmatch('[0-9a-f]{32}', self.record['token']) is not None, 'invalid lease generation')
        expected = Path(S.STATE_ROOT)/c['host']/'jobs'/(c['job_names'][phase]+'.stop')
        require(os.environ['CLASHER_LEASE_STOP_FILE'] == str(expected), 'wrong R37 stop path')
        self.stop_file = expected
        self.init_child_boundary()
        require(self.stop_at > time.time()+self.limit+180, 'job stop bound too short')
        # R37 publishes running just after spawning. Wait only for that bounded race.
        end = time.monotonic()+2
        while True:
            admitted = read_json(expected.with_suffix('.json'))
            if admitted['state'] != 'intent' or time.monotonic() >= end:
                break
            time.sleep(.05)
        require(admitted['state'] == 'running' and admitted['pid'] == os.getpid()
                and admitted['start'] == start and admitted['token'] == self.record['token']
                and admitted['boot'] == self.record['boot'] and admitted['cwd'] == str(HOME)
                and admitted['workers'] == LIMITS[phase][0] and admitted['pss_gb'] == LIMITS[phase][1]
                and admitted['grace'] == LIMITS[phase][3], 'job is not the admitted R37 root')

    def tick(self):
        require(not self.stopping and time.monotonic()-self.started < self.limit, 'job wall/stop bound')
        require(time.time() < self.stop_at and not self.stop_file.exists(), 'own lease stop requested')
        if time.monotonic()-self.last >= 5:
            _, cap, pss = check_lease(self.S, self.c['host'], 180)
            check_resources(self.S, cap, pss)
            mine = self.members()
            used = sum(self.S.pss_bytes(pid) for pid in mine)
            require(len(mine) <= LIMITS[self.phase][0] and used <= LIMITS[self.phase][1]*2**30,
                    'owned job process/PSS budget breached')
            self.peak_procs, self.peak_pss = max(self.peak_procs, len(mine)), max(self.peak_pss, used)
            self.last = time.monotonic()

    def init_child_boundary(self):
        # This admitted wrapper spawns children only in run(), which records each Popen.
        # Capture inherited foreign children before any owned launch or subreaper adoption.
        require(not self.children, 'child boundary must precede owned launches')
        root = self.S.proc_stat(os.getpid())
        require(root is not None and self.record['pid'] == os.getpid()
                and self.record['start'] == root[4], 'invalid child ownership boundary')
        self.child_boundary = (os.getpid(), root[4], root[2])
        self.child_generation = (self.record['boot'], self.record['token'])
        self.foreign_children = {}
        for pid in child_pids():
            st = self.S.proc_stat(pid)
            if st is not None:
                self.foreign_children[pid] = st[4]
        self.known_children = set()

    def members(self):
        self.known_children.update(map(tuple, self.record['procs']))
        procs = self.S.scan()
        foreign = {pid for pid, start in self.foreign_children.items()
                   if pid in procs and procs[pid]['start'] == start}
        while True:
            more = {pid for pid, p in procs.items() if p['ppid'] in foreign}
            if more <= foreign:
                break
            foreign.update(more)
        for pid in foreign:
            self.foreign_children[pid] = procs[pid]['start']
        procs = {pid: p for pid, p in procs.items() if pid not in foreign}
        self.record['procs'] = [[pid, start] for pid, start in self.record['procs']
                                if self.foreign_children.get(pid) != start]
        result = self.S.owned(self.record, procs, self.S.boot_id())
        self.known_children.update(map(tuple, self.record['procs']))
        return result

    def reap_adopted(self):
        """Peek exact OS children; Popen exclusively owns its direct-child wait status."""
        me, start, session = self.child_boundary
        root = self.S.proc_stat(me)
        require(me == os.getpid() and root is not None and root[4] == start
                and root[2] == session and self.record['boot'] == self.S.boot_id()
                and self.child_generation == (self.record['boot'], self.record['token']),
                'child ownership boundary changed')
        direct = {p.pid for p in self.children}
        self.known_children.update(map(tuple, self.record['procs']))
        pending = False
        for pid in child_pids():
            st = self.S.proc_stat(pid)
            if st is None or st[1] != me or self.foreign_children.get(pid) == st[4]:
                continue
            if pid in direct:
                # poll/wait on the object, never waitpid behind its back.
                pending = True
                continue
            # The wrapper has no unregistered child-spawning paths. A new kernel child
            # is an adopted descendant of its recorded launches, even if already dead
            # or detached before R37's first scan. Lifetime and OS parent are mandatory.
            require(st[4] >= start, 'ambiguous adopted child lifetime')
            require(not any(p == pid and saved != st[4] for p, saved in self.known_children),
                    'adopted child PID was reused')
            require((pid, st[4]) in self.known_children or bool(self.children),
                    'adopted child has no owned launch')
            self.known_children.add((pid, st[4]))
            pending = True
            if st[0] not in 'ZX':
                continue
            info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            require(info is not None and info.si_pid == pid, 'owned zombie is not waitable')
            current = self.S.proc_stat(pid)
            require(current is not None and current[1] == me and current[4] == st[4]
                    and current[0] in 'ZX', 'adopted child identity changed')
            waited, _ = os.waitpid(pid, os.WNOHANG)
            require(waited == pid, 'owned zombie was not reaped')
        return pending

    def cleanup(self, cooperative=0):
        """Exact owned signals and nonblocking waits share a 180-second deadline."""
        deadline = getattr(self, 'cleanup_deadline', time.monotonic()+180)
        for sig, allowance in ((None, cooperative), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            end = min(deadline, time.monotonic()+allowance)
            while True:
                require(time.monotonic() < deadline, 'cleanup deadline, R37 retains ownership')
                for child in self.children:
                    child.poll()
                pending = self.reap_adopted()
                members = {pid: p for pid, p in self.members().items() if pid != os.getpid()}
                if not members and not pending and all(p.returncode is not None for p in self.children):
                    # A second kernel-child check closes adoption during the live scan.
                    if not self.reap_adopted():
                        return
                if sig is not None:
                    for pid, p in members.items():
                        self.S.signal_exact(pid, p['start'], sig)
                if time.monotonic() >= end:
                    break
                time.sleep(max(0, min(.1, end-time.monotonic())))
        # Live-only emptiness cannot certify reaping, even after the last KILL.
        for child in self.children:
            child.poll()
        require(not self.reap_adopted()
                and not {p for p in self.members() if p != os.getpid()}
                and all(p.returncode is not None for p in self.children),
                'cleanup incomplete, R37 retains ownership')

    def run(self, argv, env, seconds, result=None):
        self.tick()
        # Output goes directly to R37 log, or an exclusive bounded CPU-probe receipt file.
        with parent_fd(result, create=True) if result else null_fd() as output:
            target = None
            if result:
                target = os.fdopen(os.open(output[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                          0o644, dir_fd=output[0]), 'wb')
            try:
                child = subprocess.Popen(argv, cwd=str(HOME), env=env, stdin=subprocess.DEVNULL,
                                         stdout=target, close_fds=True)
                self.children.append(child)
                end = time.monotonic()+seconds
                while child.poll() is None:
                    self.tick()
                    require(time.monotonic() < end, 'child deadline')
                    time.sleep(.2)
                require(child.returncode == 0, 'child failed: '+str(child.returncode))
                self.tick()
            finally:
                if target:
                    target.close()


@contextmanager
def null_fd():
    yield None


def receipt_path(c, phase):
    return HOME/'hosts'/c['host']/(phase+'.json')


def verify_receipt(c, inv, phase):
    value = read_json(receipt_path(c, phase))
    require(value['status'] == 'staged-cpu-verified-pending-launch-review'
            and value['contract_sha256'] == digest(c) and value['source_sha256'] == inv['source_sha256']
            and value['host'] == c['host'] and value['phase'] == phase
            and value['final_config'] == c['final_config'] and value['cuda_initialized'] is False,
            'staging receipt mismatch')
    pinned(value['cpu_probe'])
    return value


def phase_done(S, c, inv, phase):
    receipt = verify_receipt(c, inv, phase)
    path = Path(S.STATE_ROOT)/c['host']/'jobs'/(c['job_names'][phase]+'.json')
    record = read_json(path)
    require(record['state'] == 'gone' and record['token'] == receipt['lease_token']
            and record['boot'] == S.boot_id(), 'prior stage is not R37 gone for this receipt')
    require(not S.owned(record, S.scan(), S.boot_id()), 'prior stage has owned survivors')


def bounded_cleanup(job, cooperative=0):
    """The outer alarm also interrupts a blocked scan or kernel-child read on success."""
    started = time.monotonic()
    job.cleanup_deadline = min(getattr(job, 'cleanup_deadline', started+180), started+180)
    allowance = job.cleanup_deadline-started
    require(allowance > 0, 'cleanup deadline, R37 retains ownership')
    previous, interval = signal.getitimer(signal.ITIMER_REAL)
    handler = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError('cleanup deadline, R37 retains ownership')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, min(allowance, previous) if previous > 0 else allowance)
    try:
        job.cleanup(cooperative=cooperative)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
        remaining = previous-(time.monotonic()-started)
        if remaining > 0:
            signal.setitimer(signal.ITIMER_REAL, remaining, interval)


def attempt_path(c, phase):
    return HOME/'hosts'/c['host']/(phase+'.attempt.json')


def admission_identity(c, inv, phase):
    return dict(schema='qualification-admission-intent-v1', host=c['host'], phase=phase,
                contract_sha256=digest(c), final_config=c['final_config'],
                source_commit=c['source_commit'], source_sha256=c['source_sha256'],
                package_sha256=c['package_sha256'], inventory_sha256=digest(inv),
                job_name=c['job_names'][phase])


def refuse_attempt(S, c, phase):
    path = attempt_path(c, phase)
    require(not any(os.path.lexists(p) for p in
                    (path, path.with_name(phase+'.started.json'), receipt_path(c, phase))),
            'phase already attempted; parent review required, no automatic retry')
    # Old or ambiguous R37 generations cannot acquire a new intent, even if gone.
    record = Path(S.STATE_ROOT)/c['host']/'jobs'/(c['job_names'][phase]+'.json')
    require(not os.path.lexists(record), 'prior R37 generation; parent review required')


def claim_attempt(S, c, inv, phase):
    refuse_attempt(S, c, phase)
    root = S.proc_stat(os.getpid())
    require(root is not None, 'admitter identity unavailable')
    intent = dict(admission_identity(c, inv, phase), utc=stamp(), claim=secrets.token_hex(16),
                  admitter=dict(pid=os.getpid(), start=root[4], boot=S.boot_id()))
    # O_EXCL serializes concurrent admitters; file and every new directory are fsynced.
    write_new(attempt_path(c, phase), intent)
    return sha(attempt_path(c, phase))


def enter_attempt(c, inv, phase, admission_sha256):
    require(isinstance(admission_sha256, str)
            and re.fullmatch('[0-9a-f]{64}', admission_sha256) is not None,
            'exclusive admission intent pin required')
    path = attempt_path(c, phase)
    require(sha(path) == admission_sha256, 'admission intent pin changed')
    intent = read_json(path)
    expected = admission_identity(c, inv, phase)
    require({k: intent.get(k) for k in expected} == expected, 'admission intent binding changed')
    require(re.fullmatch('[0-9a-f]{32}', intent['claim']) is not None, 'invalid admission claim')
    # Consume once before R37 loading, lease checking, Job setup or subreaper startup.
    write_new(HOME/'hosts'/c['host']/(phase+'.started.json'),
              dict(admission_sha256=admission_sha256, claim=intent['claim'], utc=stamp(),
                   lease_token=os.environ.get('CLASHER_LEASE_JOB')))


def run_job(c, inv, phase, incoming, admission_sha256=None):
    enter_attempt(c, inv, phase, admission_sha256)
    S = r37()
    check_lease(S, c['host'], LIMITS[phase][4]+LIMITS[phase][3]+S.EXIT_MARGIN+180)
    job = Job(S, c, phase)
    require(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'child subreaper required')
    def stopped(*_):
        job.stopping = True
        raise InterruptedError('checkpoint signal/deadline')
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
        signal.signal(sig, stopped)
    signal.setitimer(signal.ITIMER_REAL, LIMITS[phase][4])
    succeeded = False
    try:
        for name in ('tmp', 'cache', 'cache/torch', 'cache/numba'):
            directory(HOME/name)
        config = check_authority(c, inv, payload_lookup(incoming, c, inv) if phase != 'soak' else pinned)
        if phase != 'source':
            phase_done(S, c, inv, 'source')
            verify_source(inv, job.tick)
        if phase in ('source', 'inputs'):
            require(not receipt_path(c, phase).exists(), 'stage receipt already exists')
            for relative, dst, row in payload_rows(inv, c, phase):
                job.tick()
                copy_exact(incoming/relative, dst, row, job.tick)
            verify_source(inv, job.tick)
        if phase == 'soak':
            phase_done(S, c, inv, 'inputs')
            require(not Path(c['out']).exists(), 'soak already attempted; no resume/replacement/topup')
        if phase in ('inputs', 'soak'):
            for path, row in inv['inputs'].items():
                verify(path, row, job.tick)
            check_authority(c, inv)
            verify_ready(config, inv, job.tick)
        # CPU-only probe before every phase completion and before the GPU entry.
        probe = HOME/'hosts'/c['host']/(phase+'-cpu-probe.json')
        args = [str(PYTHON), '-B', '-s', str(HERE/'cpu_probe.py'), str(DRIVER), inv['source_sha256']]
        if phase != 'source':
            args += [c['final_config']['path']]
        job.run(args, environment(True), 1200 if phase != 'source' else 120, probe)
        result = read_json(probe)
        require(result['cuda_initialized'] is False and result['source_sha256'] == inv['source_sha256']
                and (phase == 'source' or result['audit']['status'] == 'GO'), 'CPU readiness failure')
        if phase == 'soak':
            verify_source(inv, job.tick)
            pinned(c['final_config'], job.tick)
            job.run([str(PYTHON), '-B', '-s', str(DRIVER/'bot/pretrain_v1/run_registered_rl.py'),
                     'soak', '--config', c['final_config']['path'], '--out', c['out']],
                    environment(False), 21600+120+150+900)
            qualified = read_json(Path(c['out'])/'qualification.json')
            require(qualified['status'] == 'completed-exposure-pending-review'
                    and qualified['source_sha256'] == inv['source_sha256'] and qualified['wall_seconds'] >= 21600
                    and qualified['test_only'] is True and qualified['counted_registered_prefix'] is False
                    and qualified['checkpoint_or_data_promotion_allowed'] is False
                    and qualified['engine_resume_qualified'] is False, 'incomplete qualification result')
        bounded_cleanup(job)
        job.tick()
        write_new(receipt_path(c, phase), dict(status=('completed-exposure-pending-review' if phase == 'soak'
                  else 'staged-cpu-verified-pending-launch-review'), phase=phase, host=c['host'], utc=stamp(),
                  source_commit=inv['source_commit'], source_sha256=inv['source_sha256'],
                  contract_sha256=digest(c), final_config=c['final_config'],
                  package_sha256=c['package_sha256'], inputs_sha256=digest(inv['inputs']),
                  source_files_sha256=digest(inv['source_files']), extra_files_sha256=digest(c['extra_files']),
                  cpu_probe={'path': str(probe), 'sha256': sha(probe)},
                  cuda_initialized=False if phase != 'soak' else None, cpu_probe_cuda_initialized=False,
                  stage_peak_pss_budget_gib=LIMITS[phase][1], wall_seconds=time.monotonic()-job.started,
                  observed_peak_owned_processes=job.peak_procs, observed_peak_owned_pss_bytes=job.peak_pss,
                  verified_source_files=len(inv['source_files']),
                  verified_prepared_input_files=402 if phase != 'source' else 0,
                  verified_runtime_files=9409 if phase != 'source' else 0,
                  verified_actor_files=17010 if phase != 'source' else 0,
                  owned_children_reaped=True, lease_token=job.record['token']))
        succeeded = True
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        # A second TERM must not interrupt bounded exact cleanup; R37 still owns the root.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if not succeeded:
            # Driver already polls the R37 stop file; allow its existing 150 s shutdown.
            signal.setitimer(signal.ITIMER_REAL, 180)
            try:
                bounded_cleanup(job, cooperative=160 if phase == 'soak' else 0)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('op', choices=('admit', 'job'))
    parser.add_argument('phase', choices=tuple(LIMITS))
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--incoming', type=Path, required=True)
    parser.add_argument('--admission-sha256')
    args = parser.parse_args()
    require(HERE == HOME, 'install this exact frozen package at '+str(HOME))
    require(sys.version_info[:3] == (3, 12, 12) and sys.base_prefix == str(READY/'python')
            and Path(sys.executable) == PYTHON, 'invoke with explicit ready Python and PYTHONHOME')
    require(sha(args.contract) == args.contract_sha256, 'contract changed')
    c, inv = read_json(args.contract), read_json(HERE/'inventory.json')
    host = socket.gethostname().split('.')[0]
    validate_contract(c, inv, package_pin(), host)
    require(set(c['job_names']) == set(LIMITS) and len(set(c['job_names'].values())) == 3
            and all(re.fullmatch(r'qual-fe6-[A-Za-z0-9_-]{1,48}', n) for n in c['job_names'].values()),
            'unique explicit qualification job names required')
    incoming = below(args.incoming, JOBS)
    os.setpriority(os.PRIO_PROCESS, 0, max(10, os.getpriority(os.PRIO_PROCESS, 0)))
    if args.op == 'job':
        run_job(c, inv, args.phase, incoming, args.admission_sha256)
        return
    S = r37()
    require(args.admission_sha256 is None, 'admission pin is for the job handoff only')
    refuse_attempt(S, c, args.phase)
    check_authority(c, inv, payload_lookup(incoming, c, inv) if args.phase != 'soak' else pinned)
    if args.phase != 'source':
        phase_done(S, c, inv, 'source')
    if args.phase == 'soak':
        phase_done(S, c, inv, 'inputs')
    workers, pss, gpu, grace, wall = LIMITS[args.phase]
    config = check_authority(c, inv, payload_lookup(incoming, c, inv) if args.phase != 'soak' else pinned)
    gpu = config['gpu_admission']['peak_process_bytes']/2**30 if gpu is None else gpu
    _, cap, pss_cap = check_lease(S, host, wall+grace+S.EXIT_MARGIN+180)
    check_resources(S, cap, pss_cap, workers, pss)
    if args.phase != 'soak':
        env = environment(True)
    else:
        env = environment(False)
    command = [sys.executable, '-B', str(SUPERVISOR), 'admit', '--name', c['job_names'][args.phase],
               '--workers', str(workers), '--pss-gb', str(pss), '--gpu-gb', str(gpu), '--grace', str(grace),
               '--cwd', str(HOME), '--', sys.executable, '-B', str(HERE/'operate.py'), 'job', args.phase,
               '--contract', str(args.contract), '--contract-sha256', args.contract_sha256,
               '--incoming', str(incoming)]
    admission_sha256 = claim_attempt(S, c, inv, args.phase)
    command += ['--admission-sha256', admission_sha256]
    # R37 performs its own last-moment full admission and preserves its live watcher.
    os.execve(sys.executable, command, env)


if __name__ == '__main__':
    main()
