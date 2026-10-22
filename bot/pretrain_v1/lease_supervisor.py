#!/usr/bin/env python3
"""Lease supervisor for clasher pretrain-v1 work on leased 127x09/12/17 hosts. Stdlib only, Python 3.8.

  lease_supervisor.py supervise                       # one per host, detached; must be live before any admit
  lease_supervisor.py admit --name N --workers W --pss-gb P [--gpu-gb G] [--grace S] [--cwd D] -- CMD...
  lease_supervisor.py status | release

Ownership is the exact (pid, starttime, boot_id) of every process the supervisor has seen for a job: the root it
spawned, its descendants by ppid, members of its session while the root is alive, and anything carrying the job's
CLASHER_LEASE_JOB token. The set is persisted each poll, so reparented descendants stay owned. Signals go only
through a pidfd opened and identity-checked first, so a reused PID is never signalled; without pidfd support the
supervisor and admit refuse to run. Nothing is ever restarted. Every invocation raises its own nice to >= 10.

Stop contract: publish a durable generation stopping request and atomic checkpoint stop file before TERM, then KILL exact owned identities at
most 30 minutes after the first observed reclaim/refused flag, reserving 60 seconds for checks. Reopen the
lease PATH every poll without flock or inode comparisons. Missing/invalid reads retry for up to 300 seconds;
known expiry bounds still apply. Ownership leases are strictly read-only. Our own state stays under jobs/clasher;
an ended.json receipt requires verified draining. See LEASE-RUNBOOK.md.
"""
import argparse, ctypes, errno, fcntl, hashlib, json, math, os, signal, socket, stat, subprocess, sys, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone

HOSTS = {'127x09': 96, '127x12': 64, '127x17': 96}   # max clasher processes per host, all owners
HARD_STOP = '2026-10-25T07:53:00Z'
LEASE_DIR = '/mpac/sdicks02/fleet-leases'
STATE_ROOT = '/mpac/sdicks02/jobs/clasher/lease-20261022'
ALLOWED_ROOTS = ('/mpac/sdicks02/repos/clasher', '/mpac/sdicks02/jobs/clasher/')
GIB = 1 << 30
PSS_CAP_GB, MEM_MIN_GB, LOAD_MAX, GPU_FREE_MIN_GB, NICE_MIN = 64, 28, 90, 8, 10
MAX_GRACE, MAX_POLL, EXIT_MARGIN, MIN_RUNTIME, BREACH_POLLS = 1800, 60, 600, 300, 2
LOCK_WAIT, WORK_BUDGET, UNREADABLE_GRACE = 5, 25, 300
MARKER = 'CLASHER_LEASE_JOB'

now = time.time


def iso(t): return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def parse_utc(s): return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
def host(): return socket.gethostname().split('.')[0]
def under(path, roots):
    rp = os.path.realpath(path)
    return any(rp == r.rstrip('/') or rp.startswith(r) for r in roots)   # repos root is a prefix: clasher*
def boot_id():
    with open('/proc/sys/kernel/random/boot_id') as f: return f.read().strip()


def directory(path):
    """Open each component without following links; callers operate relative to the pinned directory."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in os.path.abspath(path).split('/')[1:]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = new
        return fd
    except BaseException:
        os.close(fd); raise


def make_directories(path):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in os.path.abspath(path).split('/')[1:]:
            try: os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError: pass
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = new
    finally: os.close(fd)


def safe_open(path, mode):
    flags = {'r': os.O_RDONLY, 'rb': os.O_RDONLY, 'r+': os.O_RDWR,
             'w': os.O_WRONLY | os.O_CREAT,
             'a': os.O_WRONLY | os.O_CREAT | os.O_APPEND,
             'ab': os.O_WRONLY | os.O_CREAT | os.O_APPEND,
             'a+': os.O_RDWR | os.O_CREAT | os.O_APPEND}[mode]
    d = directory(os.path.dirname(path))
    try: fd = os.open(os.path.basename(path), flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=d)
    finally: os.close(d)
    if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
        os.close(fd); raise ValueError('not a regular file: %s' % path)
    if mode == 'w': os.ftruncate(fd, 0)
    return os.fdopen(fd, mode)


def check_path(path):
    d = directory(os.path.dirname(path))
    try:
        try: st = os.stat(os.path.basename(path), dir_fd=d, follow_symlinks=False)
        except FileNotFoundError: return
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1: raise ValueError('unsafe file: %s' % path)
    finally: os.close(d)


def write_atomic(path, data):
    d = directory(os.path.dirname(path)); tmp = '.tmp-' + uuid.uuid4().hex
    try:
        check_path(path)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=d)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=1, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, os.path.basename(path), src_dir_fd=d, dst_dir_fd=d); os.fsync(d)
    finally:
        try: os.unlink(tmp, dir_fd=d)
        except FileNotFoundError: pass
        os.close(d)


def flock_bounded(f, operation, wait=None):
    if wait is None: wait = LOCK_WAIT
    end = time.monotonic() + wait
    while True:
        try: fcntl.flock(f, operation | fcntl.LOCK_NB); return
        except BlockingIOError:
            if time.monotonic() >= end: raise TimeoutError('lock wait exceeded')
            time.sleep(min(0.02, max(0, end - time.monotonic())))


# ---------------------------------------------------------------- /proc
def proc_stat(pid):
    """(state, ppid, session, nice, starttime) or None if gone."""
    try:
        with open('/proc/%d/stat' % pid) as f: s = f.read()
    except (FileNotFoundError, ProcessLookupError): return None
    a = s[s.rindex(')')+2:].split()
    return a[0], int(a[1]), int(a[3]), int(a[16]), int(a[19])


def alive(pid, start):
    st = proc_stat(pid)
    return st is not None and st[0] not in 'ZX' and st[4] == start


def scan():
    """All live processes of this uid: {pid: dict(ppid, sid, nice, start, env, cmd, cwd)}."""
    uid, out = os.getuid(), {}
    for name in os.listdir('/proc'):
        if not name.isdigit(): continue
        pid = int(name)
        try:
            if os.stat('/proc/%d' % pid).st_uid != uid: continue
            st = proc_stat(pid)
            if st is None or st[0] in 'ZX': continue
            env, cmd, cwd = b'', b'', ''
            try:
                with open('/proc/%d/environ' % pid, 'rb') as f: env = f.read()
                with open('/proc/%d/cmdline' % pid, 'rb') as f: cmd = f.read()
                cwd = os.readlink('/proc/%d/cwd' % pid)
            except PermissionError: pass             # e.g. setuid helpers; still counted by ppid/session
        except (FileNotFoundError, ProcessLookupError): continue
        end = proc_stat(pid)
        if end is None or end[0] in 'ZX' or end[4] != st[4]: continue
        out[pid] = dict(ppid=st[1], sid=st[2], nice=st[3], start=st[4], env=env, cmd=cmd, cwd=cwd)
    return out


def pss_bytes(pid):
    try:
        with open('/proc/%d/smaps_rollup' % pid) as f:
            for line in f:
                if line.startswith('Pss:'): return int(line.split()[1]) * 1024
    except (FileNotFoundError, ProcessLookupError): return 0       # exited; PermissionError propagates (unobservable)
    return 0


def is_clasher(p):
    return (b'\0' + MARKER.encode() + b'=' in b'\0' + p['env'] or any(r.encode() in p['cmd'] for r in ALLOWED_ROOTS)
            or bool(p['cwd']) and under(p['cwd'], ALLOWED_ROOTS))


_libc = ctypes.CDLL(None, use_errno=True)
def _sys(nr, *args):
    rc = _libc.syscall(nr, *args)
    if rc < 0:
        e = ctypes.get_errno(); raise OSError(e, os.strerror(e))
    return rc
def _pidfd_open(pid): return _sys(434, pid, 0)
def _pidfd_signal(fd, sig): _sys(424, fd, sig, None, 0)


def require_pidfd():
    try: os.close(_pidfd_open(os.getpid()))
    except OSError as e: raise SystemExit('refused: pidfd unavailable (%s); cannot signal by exact identity' % e)


def signal_exact(pid, start, sig):
    """Signal pid only if it is still the process with this starttime. True if delivered. Never falls back to kill(2)."""
    try: fd = _pidfd_open(pid)
    except OSError as e:
        if e.errno == errno.ESRCH: return False
        raise
    try:
        if not alive(pid, start): return False      # fd pins this pid; identity checked after pinning
        _pidfd_signal(fd, sig); return True
    except OSError as e:
        if e.errno == errno.ESRCH: return False
        raise
    finally: os.close(fd)


def gpu_free_gb():
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=LOCK_WAIT)
        return min(int(x) for x in r.stdout.split()) / 1024 if r.returncode == 0 and r.stdout.split() else None
    except (OSError, ValueError, subprocess.SubprocessError): return None


def host_load():
    with open('/proc/meminfo') as f:
        mem = next(int(l.split()[1]) * 1024 for l in f if l.startswith('MemAvailable:'))
    with open('/proc/loadavg') as f: load = float(f.read().split()[0])
    return mem, load


# ---------------------------------------------------------------- lease
def read_snapshot(path):
    # A new path open on EVERY call. Writers may rename, truncate, or ignore flock entirely.
    with safe_open(path, 'rb') as f: raw = f.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024: raise ValueError('lease too large')
    return raw


def finite_number(value):
    # Integer comparison is safe even when float(value) would overflow.
    return (type(value) in (int, float) and -sys.float_info.max <= value <= sys.float_info.max
            and (type(value) is int or math.isfinite(value)))


def lease_json(raw):
    def integer(text):
        # Python 3.8 lacks the newer decoder's digit limit. Bound conversion on both.
        if len(text) > 1024: raise ValueError('lease integer too long')
        return int(text)
    return json.loads(raw, parse_int=integer)


def lease_trigger(d):
    if d.get('reclaim') is True: return 'reclaim'
    if d.get('refused') is True: return 'refused'
    return None


def lease_identity(d): return [d.get(k) for k in ('project', 'coordinator_thread', 'granted_by', 'start_utc')]


def validate_lease(d, h):
    # Trigger flags are handled and persisted by the caller BEFORE any schema/project checks.
    if not isinstance(d, dict): raise ValueError('lease is not a dictionary')
    if any(not isinstance(v, str) or not v for v in lease_identity(d)): raise ValueError('incomplete lease identity')
    for key in ('start_utc', 'expected_end_utc'):
        if not isinstance(d.get(key), str) or len(d[key]) != 20: raise ValueError('invalid ' + key)
        parse_utc(d[key])
    deadline = min(parse_utc(HARD_STOP), parse_utc(d['expected_end_utc']))
    if type(d.get('reclaim')) is not bool or type(d.get('refused', False)) is not bool:
        raise ValueError('missing/invalid lease flags')
    if not isinstance(d.get('status'), str) or not d['status']: raise ValueError('missing lease status')
    def cap(key, limit):
        value = d.get(key, limit)
        if not finite_number(value) or value <= 0: raise ValueError('invalid ' + key)
        return min(limit, value)
    return deadline, cap('max_workers', HOSTS[h]), cap('pss_cap_gb', PSS_CAP_GB)


def load_lease(path, h):
    # Read-only convenience for inspection. Operational readers use Supervisor.read_lease to retain flags.
    d = lease_json(read_snapshot(path))
    return (d,) + validate_lease(d, h)


def lease_ending(d):
    return lease_trigger(d) or ('lease status %r' % d.get('status') if d.get('status') != 'active' else None)


# ---------------------------------------------------------------- state
class State:
    def __init__(self, root, h):
        self.h, self.dir = h, os.path.join(root, h)
        self.jobs = os.path.join(self.dir, 'jobs'); self.logs = os.path.join(self.dir, 'logs')
        self.recovery = os.path.join(self.dir, 'recovery')
        if not under(self.dir, ALLOWED_ROOTS[1:]): raise SystemExit('state dir outside /mpac/sdicks02/jobs/clasher/')
        for d in (self.jobs, self.logs, self.recovery):
            make_directories(d)
            fd = directory(d); os.close(fd)
            if not under(d, ALLOWED_ROOTS[1:]): raise ValueError('unsafe state directory')
        self.release, self.halt = os.path.join(self.dir, 'RELEASE'), os.path.join(self.dir, 'HALT')

    def lock(self, name, block=True):
        f = safe_open(os.path.join(self.dir, name), 'a+')
        try:
            if block: flock_bounded(f, fcntl.LOCK_EX)
            else: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: f.close(); return None
        except BaseException: f.close(); raise
        return f

    def supervisor_live(self):
        f = self.lock('supervisor.lock', block=False)
        if f is None: return True
        f.close(); return False

    def records(self):
        """{name: record}; a record that cannot be parsed is returned as {'state': 'uncertain'}."""
        out = {}
        fd = directory(self.jobs)
        try: names = sorted(os.listdir(fd))
        finally: os.close(fd)
        for n in names:
            if not n.endswith('.json'): continue
            try:
                with safe_open(os.path.join(self.jobs, n), 'r') as f: r = json.load(f)
                if r.get('name') != n[:-5] or r.get('state') not in ('intent', 'running', 'stopping', 'gone'):
                    raise ValueError
                self.validate(r)
            except (ValueError, OSError, KeyError, TypeError, AttributeError, RecursionError, OverflowError):
                r = {'name': n[:-5], 'state': 'uncertain'}
            out[n[:-5]] = r
        return out

    def validate(self, r):
        if not isinstance(r, dict) or not valid_name(r.get('name')): raise ValueError('bad record name')
        if r['state'] in ('intent', 'running', 'stopping', 'gone'):
            token = r.get('token')
            if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
                raise ValueError('bad token')
            if not isinstance(r.get('boot'), str) or not r['boot']: raise ValueError('bad boot')
            pairs = r['procs']
            if not isinstance(pairs, list): raise ValueError('bad identities')
            for pair in pairs:
                if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int or x <= 0 for x in pair):
                    raise ValueError('bad process identity')
            if r['state'] not in ('intent', 'gone') and r.get('pid') is None: raise ValueError('missing root identity')
            if r.get('pid') is not None and (type(r['pid']) is not int or r['pid'] <= 0 or
                                            type(r.get('start')) is not int or r['start'] <= 0):
                raise ValueError('bad root identity')
            for key in ('workers', 'pss_gb', 'grace'):
                if not finite_number(r[key]) or r[key] <= 0:
                    raise ValueError('bad resource contract')
            if r['grace'] > MAX_GRACE: raise ValueError('bad grace')
            if r['state'] == 'stopping':
                if not finite_number(r['kill_at']): raise ValueError('bad kill deadline')
                parse_utc(r['stop_sent_utc'])
            if r['stop_file'] != os.path.join(self.jobs, r['name'] + '.stop'): raise ValueError('unsafe stop file')
            if r['log'] != os.path.join(self.logs, '%s-%s.log' % (r['name'], r['token'][:8])): raise ValueError('unsafe log')
            for path in (r['stop_file'], r['log']): check_path(path)

    def save(self, r):
        if not valid_name(r['name']): raise ValueError('bad record name')
        write_atomic(os.path.join(self.jobs, r['name']+'.json'), r)

    def journal(self, request):
        """Append a complete immutable request, without any admission/observation lock.

        Identical requests share a content-derived name. Concurrent publication of those
        bytes is harmless; atomic replace and directory fsync precede every signal.
        """
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        path = os.path.join(self.recovery, digest + '.json')
        # Re-fsync even an existing request: a concurrent publisher may have renamed it
        # but not yet synced its directory. No reader or publisher truncates this file.
        if not os.path.exists(path): write_atomic(path, request)
        with safe_open(path, 'r') as f: os.fsync(f.fileno())
        fd = directory(self.recovery)
        try: os.fsync(fd)
        finally: os.close(fd)

    def requests(self):
        fd = directory(self.recovery)
        try: names = sorted(os.listdir(fd))
        finally: os.close(fd)
        for name in names:
            if not name.endswith('.json'): continue
            with safe_open(os.path.join(self.recovery, name), 'r') as f: request = json.load(f)
            if request.get('kind') == 'recovery':
                if request.get('state') != 'stopping' or not finite_number(request['origin']):
                    raise ValueError('bad recovery request')
                parse_utc(request['deadline'])
                if not isinstance(request['reason'], str): raise ValueError('bad recovery reason')
            elif request.get('kind') == 'stop':
                self.validate(request['record'])
                if request['record']['state'] != 'stopping': raise ValueError('bad stop request')
            else: raise ValueError('unknown recovery request')
            yield request

    def event(self, **kw):
        kw['utc'] = iso(now())
        with safe_open(os.path.join(self.dir, 'events.jsonl'), 'a') as f: f.write(json.dumps(kw, sort_keys=True)+'\n')


def valid_name(name):
    return isinstance(name, str) and name.replace('-', '').replace('_', '').replace('.', '').isalnum()


def owned(r, procs, boot):
    """Refresh r['procs'] to every live owned process. Returns {pid: proc}."""
    if r.get('boot') != boot: r['procs'] = []; return {}
    tok = ('\0%s=%s\0' % (MARKER, r['token'])).encode()
    have = {pid: procs[pid] for pid, start in r.get('procs', []) if pid in procs and procs[pid]['start'] == start}
    for pid, start in r.get('procs', []):
        if pid in have: continue
        st = proc_stat(pid)           # scan omission is not evidence of exit
        if st is not None and st[0] not in 'ZX' and st[4] == start:
            have[pid] = dict(ppid=st[1], sid=st[2], nice=st[3], start=start, env=b'', cmd=b'', cwd='')
    root_alive = r['pid'] in have
    for pid, p in procs.items():
        if tok in b'\0' + p['env'] + b'\0' or (root_alive and p['sid'] == r['pid'] and p['start'] >= r['start']):
            have[pid] = p
    grew = True
    while grew:
        grew = False
        for pid, p in procs.items():
            if pid not in have and p['ppid'] in have and p['start'] >= have[p['ppid']]['start']:
                have[pid] = p; grew = True
    r['procs'] = sorted([pid, p['start']] for pid, p in have.items())
    return have


def discover(recs, procs, boot):
    jobs = {}
    for r in recs.values():
        if r['state'] not in ('intent', 'running', 'stopping', 'gone'): continue
        mine = owned(r, procs, boot)
        if r['state'] == 'intent':
            if not mine: continue  # an uncompleted spawn remains uncertain, never proof of exit
            pid = min(mine, key=lambda p: (mine[p]['start'], p))
            r.update(state='running', pid=pid, start=mine[pid]['start'])
        if r['state'] == 'gone' and mine: r['state'] = 'running'
        if r['state'] != 'gone': jobs[r['name']] = mine
    return jobs


def sample(recs, procs, jobs):
    """Aggregate clasher load, with each live job charged at least its declared workers and PSS. Raises if unobservable."""
    clasher = {pid for pid, p in procs.items() if is_clasher(p)} | {pid for m in jobs.values() for pid in m}
    pss = {pid: pss_bytes(pid) for pid in clasher}
    n, total = len(clasher), sum(pss.values())
    for name, mine in jobs.items():
        r = recs[name]
        n += max(0, r['workers'] - len(mine))
        total += max(0, r['pss_gb'] * GIB - sum(pss[p] for p in mine))
    mem, load = host_load()
    return dict(procs=n, pss=total, mem=mem, load=load)


# ---------------------------------------------------------------- admit
def admit(a, st, lease_path):
    require_pidfd()
    lk = st.lock('state.lock')
    try:
        if not st.supervisor_live(): raise SystemExit('refused: no live supervisor on this host')
        if os.path.exists(st.release): raise SystemExit('refused: release requested')
        if os.path.exists(st.halt): raise SystemExit('refused: supervisor halted after poll errors; inspect events.jsonl')
        sv = Supervisor(st, lease_path)
        result = sv.read_lease()
        if sv.ending: raise SystemExit('refused: ' + sv.ending)
        if result is None: raise SystemExit('refused: lease unreadable; retry next poll')
        d, deadline, cap, pss_cap = result
        if parse_utc(d['start_utc']) > now(): raise SystemExit('refused: lease not started')
        if not (1 <= a.workers and 0 < a.pss_gb and 0 <= a.gpu_gb and 0 < a.grace <= MAX_GRACE):
            raise SystemExit('refused: need workers>=1, pss-gb>0, gpu-gb>=0, 0<grace<=%d' % MAX_GRACE)
        if not valid_name(a.name):
            raise SystemExit('refused: bad name')
        if not under(a.cwd, ALLOWED_ROOTS): raise SystemExit('refused: cwd outside clasher roots')
        stop_at = deadline - EXIT_MARGIN - a.grace
        if now() + MIN_RUNTIME > stop_at: raise SystemExit('refused: too close to lease end (%s)' % iso(stop_at))
        recs = st.records()
        bad = [n for n, r in recs.items() if r['state'] in ('intent', 'uncertain')]
        if bad: raise SystemExit('refused: uncertain records %s; inspect and quarantine by hand' % bad)
        if a.name in recs and recs[a.name]['state'] != 'gone':
            raise SystemExit('refused: %s is %s' % (a.name, recs[a.name]['state']))
        boot = boot_id(); procs = scan()
        for r in recs.values():
            if r['state'] == 'gone' and r.get('boot') == boot and owned(r, procs, boot):
                raise SystemExit('refused: %s marked gone but has live processes' % r['name'])
        s = sample(recs, procs, discover(recs, procs, boot))
        why = []
        if s['procs'] + a.workers > cap: why.append('procs %d+%d>%d' % (s['procs'], a.workers, cap))
        if s['pss'] + a.pss_gb * GIB > pss_cap * GIB: why.append('pss %.1f+%g>%g GiB' % (s['pss']/GIB, a.pss_gb, pss_cap))
        if s['mem'] - a.pss_gb * GIB <= MEM_MIN_GB * GIB: why.append('MemAvailable %.1f-%g<=%d GiB' % (s['mem']/GIB, a.pss_gb, MEM_MIN_GB))
        if s['load'] > LOAD_MAX: why.append('load %.1f>%d' % (s['load'], LOAD_MAX))
        g = gpu_free_gb()                            # every admission, CPU-only too: the lease keeps 8 GiB free
        if g is None or g - a.gpu_gb < GPU_FREE_MIN_GB: why.append('gpu free %s-%g<%d GiB' % (g, a.gpu_gb, GPU_FREE_MIN_GB))
        if why: raise SystemExit('refused: ' + '; '.join(why))

        generation = st.lock('generation.lock')
        try:
            # Emergency sets HALT before taking this lock. Recheck after slow preflight.
            result = sv.read_lease()
            if os.path.exists(st.halt) or os.path.exists(st.release) or sv.ending:
                raise SystemExit('refused: stop requested before spawn')
            if result is None: raise SystemExit('refused: lease unreadable before spawn')
            _, current_deadline, current_cap, current_pss = result
            if current_cap < cap or current_pss < pss_cap: raise SystemExit('refused: lease caps tightened; retry')
            stop_at = current_deadline - EXIT_MARGIN - a.grace
            if now() + MIN_RUNTIME > stop_at: raise SystemExit('refused: too close to lease end')
            token = uuid.uuid4().hex
            r = dict(name=a.name, token=token, state='intent', cmd=a.cmd, cwd=os.path.realpath(a.cwd), workers=a.workers,
                     pss_gb=a.pss_gb, gpu_gb=a.gpu_gb, grace=a.grace, admitted_utc=iso(now()), stop_by_utc=iso(stop_at),
                     boot=boot, procs=[], pid=None, start=None,
                     stop_file=os.path.join(st.jobs, a.name+'.stop'), log=os.path.join(st.logs, '%s-%s.log' % (a.name, token[:8])))
            check_path(r['stop_file']); check_path(r['log'])
            if os.path.exists(r['stop_file']): os.unlink(r['stop_file'])
            st.save(r)                                   # intent precedes spawn: a crash here is visible and blocks
            env = dict(os.environ, **{MARKER: token, 'CLASHER_LEASE_STOP_FILE': r['stop_file'],
                                      'CLASHER_LEASE_STOP_BY_UTC': r['stop_by_utc'], 'PYTHONDONTWRITEBYTECODE': '1'})
            if not a.gpu_gb: env['CUDA_VISIBLE_DEVICES'] = ''
            try:
                with safe_open(r['log'], 'ab') as log, open(os.devnull, 'rb') as nul:
                    p = subprocess.Popen(a.cmd, cwd=r['cwd'], env=env, stdin=nul, stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True, close_fds=True, preexec_fn=lambda: os.setpriority(
                                             os.PRIO_PROCESS, 0, max(NICE_MIN, os.getpriority(os.PRIO_PROCESS, 0))))
            except OSError as e:                         # exec failed: the child never ran
                r.update(state='gone', error=str(e)); st.save(r); raise SystemExit('spawn failed: %s' % e)
            try:
                s0 = proc_stat(p.pid)                    # unreaped child: its pid cannot be reused yet
                if s0 is None: raise RuntimeError('spawned child identity unavailable')
                r.update(state='running', pid=p.pid, start=s0[4], procs=[[p.pid, s0[4]]])
                st.save(r)
                # HALT may have arrived while Popen or publication was in progress.
                sv.read_lease()
                if os.path.exists(st.halt) or os.path.exists(st.release) or sv.ending:
                    sv.ending = sv.ending or 'supervisor errors'
                    raise SystemExit('refused: stop requested during spawn; child retained for draining')
                st.event(ev='admit', name=a.name, pid=p.pid, start=s0[4], cmd=a.cmd)
                print(json.dumps(dict(admitted=a.name, pid=p.pid, start=s0[4], log=r['log'], stop_by_utc=r['stop_by_utc'])))
            except BaseException:
                # Even failed publication leaves a durable token-bearing intent.
                # Stop by captured identity, or rediscover the token if identity lookup failed.
                try:
                    sv.halt(now(), 'admission interrupted after spawn')
                finally:
                    if r['state'] == 'intent': discover({r['name']: r}, scan(), boot)
                    if r['procs']: sv.stop_owned(r, now())
                raise
        finally: generation.close()
    finally: lk.close()


# ---------------------------------------------------------------- supervise
class Supervisor:
    def __init__(self, st, lease_path, poll=MAX_POLL):
        self.st, self.lease_path, self.poll_s = st, lease_path, poll
        self.breach, self.ending, self.origin, self.identity = 0, None, None, None
        self.deadline_bound, self.trigger_origin, self.trigger_reason = parse_utc(HARD_STOP), None, None
        self.recovery_origin = None
        self.stop_requests = {}
        self.unreadable_since, self.observed, self.trigger_observed = None, None, None
        self.cap, self.pss_cap = HOSTS[st.h], PSS_CAP_GB
        self.bound_path = os.path.join(st.dir, 'deadline-bound.json')
        identity_path = os.path.join(st.dir, 'lease-identity.json')
        if os.path.exists(identity_path):
            with safe_open(identity_path, 'r') as f: self.identity = json.load(f)
        self.restore_bounds()

    def restore_bounds(self):
        self.restore_journal()
        if not os.path.exists(self.bound_path): return
        with safe_open(self.bound_path, 'r') as f: saved = json.load(f)
        self.deadline_bound = min(self.deadline_bound, parse_utc(saved['deadline']))
        # Recover old review-era state conservatively, without ever reading an external mtime.
        origin = saved.get('trigger_origin')
        if origin is None and saved.get('reclaim_origin'): origin = parse_utc(saved['reclaim_origin'])
        if origin is not None and (self.trigger_origin is None or origin < self.trigger_origin):
            self.trigger_origin, self.trigger_reason = origin, saved.get('trigger_reason') or 'reclaim'
            self.trigger_observed = saved.get('trigger_observed_lease')
        recovery = saved.get('recovery_origin')
        if recovery is not None:
            self.recovery_origin = min(self.recovery_origin, recovery) if self.recovery_origin is not None else recovery
        self.ending = self.trigger_reason or self.ending or saved.get('ending')
        origins = [t for t in (self.trigger_origin, self.recovery_origin, self.origin) if t is not None]
        self.origin = min(origins) if origins else None
        self.unreadable_since = saved.get('unreadable_since')
        self.observed = saved.get('observed_lease')
        self.cap = min(self.cap, saved.get('max_workers', self.cap))
        self.pss_cap = min(self.pss_cap, saved.get('pss_cap_gb', self.pss_cap))

    def restore_journal(self):
        """Always load independent requests, including before any external read."""
        for request in self.st.requests():
            if request['kind'] == 'recovery':
                t0 = request['origin']
                self.recovery_origin = min(self.recovery_origin, t0) if self.recovery_origin is not None else t0
                self.origin = min(self.origin, t0) if self.origin is not None else t0
                self.deadline_bound = min(self.deadline_bound, parse_utc(request['deadline']))
                self.ending = self.ending or request['reason']
            else:
                r = request['record']
                key = (r['name'], r['token'], r['boot'])
                old = self.stop_requests.get(key)
                if old is not None:
                    r['kill_at'] = min(r['kill_at'], old['kill_at'])
                    r['procs'] = sorted([list(p) for p in set(map(tuple, r['procs'] + old['procs']))])
                    r['stop_sent_utc'] = min(r['stop_sent_utc'], old['stop_sent_utc'])
                self.stop_requests[key] = r

    def restore_stops(self, recs):
        for r in recs.values():
            if r['state'] == 'uncertain': continue
            saved = self.stop_requests.get((r['name'], r['token'], r['boot']))
            if saved is None: continue
            # Merge only this exact generation. Never replace a newer intent or ownership token.
            r['procs'] = sorted([list(p) for p in set(map(tuple, r['procs'] + saved['procs']))])
            if r['state'] == 'gone':
                r['procs'] = [[pid, start] for pid, start in r['procs'] if alive(pid, start)]
            if r['pid'] is None: r.update(pid=saved['pid'], start=saved['start'])
            # Confirmed exits need no new stop publication on every later poll. Their
            # tokens still participate in discovery, with the retained stopping bound.
            state = 'gone' if r['state'] == 'gone' and not r['procs'] else 'stopping'
            r.update(state=state, kill_at=min(r.get('kill_at', saved['kill_at']), saved['kill_at']),
                     stop_reason=saved['stop_reason'], stop_sent_utc=saved['stop_sent_utc'])

    def save_bounds(self):
        write_atomic(self.bound_path, dict(deadline=iso(self.deadline_bound),
                     trigger_origin=self.trigger_origin, trigger_reason=self.trigger_reason,
                     recovery_origin=self.recovery_origin,
                     trigger_observed_lease=self.trigger_observed, unreadable_since=self.unreadable_since,
                     observed_lease=self.observed, ending=self.ending, max_workers=self.cap, pss_cap_gb=self.pss_cap))

    def read_lease(self):
        # Serialize only our observation-state writes, never the external owner's file.
        lk = self.st.lock('observation.lock')
        try: return self.observe_lease()
        finally: lk.close()

    def observe_lease(self):
        """Observe a fresh path snapshot. True flags latch before validation or any later fallible work."""
        self.restore_bounds()
        t = now()
        self.observed = dict(path=self.lease_path, observed_at=t, sha256=None, flags=None, valid=False)
        try:
            raw = read_snapshot(self.lease_path)
            self.observed['sha256'] = hashlib.sha256(raw).hexdigest()
            d = lease_json(raw)
            t = now(); self.observed['observed_at'] = t
            self.observed.update(flags={k: d.get(k) if type(d.get(k)) is bool else None
                                        for k in ('reclaim', 'refused')} if isinstance(d, dict) else None)
            if isinstance(d, dict) and lease_trigger(d):
                if self.trigger_origin is None:
                    self.trigger_origin, self.trigger_reason = t, lease_trigger(d)
                    self.trigger_observed = dict(self.observed)
                self.origin = min(self.origin, self.trigger_origin) if self.origin is not None else self.trigger_origin
                self.ending = self.trigger_reason
                self.save_bounds()  # Never discard an observed flag if a later check/read/scan fails.
            deadline, cap, pss_cap = validate_lease(d, self.st.h)
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError) as e:
            t = now(); self.observed['observed_at'] = t
            self.observed['error'] = '%s: %s' % (type(e).__name__, e)
            if self.unreadable_since is None: self.unreadable_since = t
            if self.ending is None and t - self.unreadable_since > UNREADABLE_GRACE:
                self.ending = 'lease unreadable'
            self.save_bounds()
            return None
        self.deadline_bound = min(self.deadline_bound, deadline)
        self.cap, self.pss_cap = min(self.cap, cap), min(self.pss_cap, pss_cap)
        self.unreadable_since = None  # Only a full valid readable lease resets the retry timer.
        self.observed['valid'] = True
        self.save_bounds()  # Keep valid bounds even if later identity-state I/O fails.
        path = os.path.join(self.st.dir, 'lease-identity.json')
        if self.identity is None:
            if not os.path.exists(path): write_atomic(path, lease_identity(d))
            with safe_open(path, 'r') as f: self.identity = json.load(f)
        if self.ending is None:
            self.ending = ('lease replaced' if d['project'] != 'clasher' or lease_identity(d) != self.identity
                           else lease_ending(d))
        self.save_bounds()
        return d, self.deadline_bound, self.cap, self.pss_cap

    def begin_stop(self, r, reason, deadline):
        t = now()
        origin = min(t, self.origin) if self.origin is not None and reason == self.ending else t
        r.update(state='stopping', stop_reason=reason, stop_sent_utc=iso(t),
                 kill_at=min(origin + r['grace'], deadline - EXIT_MARGIN) - MAX_POLL)
        self.publish_stop(r)
        self.st.save(r)
        self.st.event(ev='stop', name=r['name'], reason=reason, kill_at=iso(r['kill_at']))

    def publish_stop(self, r):
        # The immutable generation request is the stopping record when admission holds
        # generation.lock or job-record publication fails. Both publications precede signals.
        self.st.journal(dict(kind='stop', record=r))
        write_atomic(r['stop_file'], dict(reason=r['stop_reason'], utc=r['stop_sent_utc']))

    def cached_stops(self, recs, t0, emergency=False, persist=True, discover_tokens=True):
        """Stop saved identities first, then recover every token before external I/O."""
        boot, error = boot_id(), None
        def stop_known():
            nonlocal error
            for r in recs.values():
                if r.get('boot') != boot or r['state'] not in ('running', 'stopping') or not r['procs']: continue
                reason = self.ending or ('lease expiry' if now() >= self.deadline_bound-EXIT_MARGIN-r['grace'] else None)
                if not (emergency or reason or r['state'] == 'stopping'): continue
                try: self.stop_owned(r, t0, persist=persist, reason=reason)
                except Exception as e: error = e
        stop_known()  # A failing scan cannot suppress enforcement on captured identities.
        if discover_tokens:
            try: procs = scan()
            except Exception:
                if not emergency: raise
                procs = {}
            discover(recs, procs, boot)
            stop_known()  # Includes intents/gone records recovered by their ownership tokens.
        if error is not None: raise error

    def poll(self):
        """One supervision step. Returns 'ended' after our drained receipt is saved, else None."""
        st = self.st
        lk = st.lock('state.lock')
        generation = None
        try:
            generation = st.lock('generation.lock')
            t, boot = now(), boot_id()
            self.restore_bounds()
            recs = st.records()
            tokens = any(r['state'] in ('intent', 'gone') for r in recs.values())
            self.restore_stops(recs)
            # With a cached stop due, external I/O must follow enforcement. Otherwise
            # observe first, so an unrelated scan failure cannot hide a new owner flag.
            if self.ending or any(r['state'] == 'stopping' or
                                 r['state'] == 'gone' and 'kill_at' in r or
                                 r['state'] in ('running', 'intent', 'gone') and
                                 t >= self.deadline_bound-EXIT_MARGIN-r['grace'] for r in recs.values()):
                self.cached_stops(recs, t, discover_tokens=tokens)
            self.read_lease()
            observation = st.lock('observation.lock')
            try:
                # Recovery may have latched a bound since read_lease released this lock.
                self.restore_bounds()
                if self.ending is None and os.path.exists(st.halt): self.ending = 'supervisor errors'
                if self.ending is None and os.path.exists(st.release): self.ending = 'release'
                self.save_bounds()
            finally: observation.close()
            deadline, cap, pss_cap = self.deadline_bound, self.cap, self.pss_cap
            recs, procs = st.records(), scan()
            self.restore_stops(recs)
            jobs = discover(recs, procs, boot)
            try: s, obs = sample(recs, procs, jobs), None
            except (OSError, ValueError, StopIteration) as e:   # unobservable resources count as a breach
                s, obs = dict(procs=0, pss=0, mem=0, load=0), 'unobservable: %s: %s' % (type(e).__name__, e)
            for r in recs.values():
                if r['state'] not in ('running', 'stopping'): continue
                mine = jobs[r['name']]
                if not mine:
                    r['state'] = 'gone'; r['gone_utc'] = iso(t); st.event(ev='gone', name=r['name']); st.save(r); continue
                for pid, p in mine.items():                      # raising nice is always permitted
                    if p['nice'] < NICE_MIN and alive(pid, p['start']):
                        try: os.setpriority(os.PRIO_PROCESS, pid, NICE_MIN)
                        except OSError: pass
                stop_at = deadline - EXIT_MARGIN - r['grace']
                if r['state'] == 'running' and (self.ending or t >= stop_at):
                    self.begin_stop(r, self.ending or 'lease expiry', deadline)
                    for pid, p in mine.items(): signal_exact(pid, p['start'], signal.SIGTERM)
                if r['state'] == 'stopping':
                    r['kill_at'] = min(r['kill_at'], deadline - EXIT_MARGIN - MAX_POLL)
                    if self.origin is not None:
                        r['kill_at'] = min(r['kill_at'], self.origin + r['grace'] - MAX_POLL)
                    if t < r['kill_at']:
                        st.save(r); continue
                    self.publish_stop(r)
                    st.save(r)
                    for pid, p in mine.items():
                        if signal_exact(pid, p['start'], signal.SIGKILL): st.event(ev='kill', name=r['name'], pid=pid)
                st.save(r)

            live = [r for r in recs.values() if r['state'] == 'running']
            g = gpu_free_gb() if live else None
            why = [w for w, bad in (('procs', s['procs'] > cap), ('pss', s['pss'] > pss_cap * GIB),
                                    ('mem', s['mem'] <= MEM_MIN_GB * GIB), ('load', s['load'] > LOAD_MAX),
                                    ('gpu', bool(live) and (g is None or g < GPU_FREE_MIN_GB))) if bad]
            if obs: why = [obs]
            if why == ['gpu']: live = [r for r in live if r['gpu_gb']]   # only a GPU job can free GPU memory
            self.breach = self.breach + 1 if why and live else 0
            if self.breach >= BREACH_POLLS:                     # shed newest owned job first
                r = max(live, key=lambda r: r['admitted_utc'])
                self.begin_stop(r, 'resource breach: ' + ','.join(why), deadline)
                for pid, p in jobs[r['name']].items(): signal_exact(pid, p['start'], signal.SIGTERM)
                st.save(r); self.breach = 0
            st.event(ev='poll', procs=s['procs'], pss_gb=round(s['pss']/GIB, 2), mem_gb=round(s['mem']/GIB, 1),
                     load=s['load'], breach=why, ending=self.ending,
                     jobs={n: r['state'] for n, r in recs.items()})

            if self.ending is None and t >= deadline - EXIT_MARGIN: self.ending = 'lease expiry'
            recs = st.records()
            # A final scan before release includes gone records and every saved token.
            final_jobs = {}
            if self.ending:
                final_jobs = discover(recs, scan(), boot)
                for r in recs.values():
                    if r['state'] != 'uncertain': st.save(r)
            drained = all(r['state'] == 'gone' for r in recs.values()) and not final_jobs
            receipt = dict(status=('ended' if drained else 'draining') if self.ending else 'watching', reason=self.ending,
                           utc=iso(t), boot=boot, jobs_drained=drained, jobs={n: r['state'] for n, r in recs.items()},
                           observed_lease=self.observed, trigger_observed_lease=self.trigger_observed,
                           lease_identity=self.identity, owner_lease_updated=False)
            write_atomic(os.path.join(st.dir, 'status.json'), receipt)
            if self.ending and drained:
                write_atomic(os.path.join(st.dir, 'ended.json'), receipt)
                st.event(ev='owned-jobs-ended', reason=self.ending, owner_lease_updated=False)
                return 'ended'
        finally:
            if generation is not None: generation.close()
            lk.close()

    def stop_owned(self, r, t0, persist=True, reason=None):
        """Only a generation-lock holder may replace job records. Journal/notification precede signals."""
        hard = self.deadline_bound - EXIT_MARGIN - MAX_POLL
        bound = min(t0 + r['grace'] - MAX_POLL, hard, r.get('kill_at', hard))
        if self.trigger_origin is not None:
            bound = min(bound, self.trigger_origin + r['grace'] - MAX_POLL)
        if self.recovery_origin is not None:
            bound = min(bound, self.recovery_origin + r['grace'] - MAX_POLL)
        r.update(state='stopping', stop_reason=reason or r.get('stop_reason') or self.ending,
                 stop_sent_utc=r.get('stop_sent_utc', iso(min(t0, now()))), kill_at=bound)
        self.publish_stop(r)
        try:
            if persist: self.st.save(r)
        finally:
            # A failed save must not suppress stopping; the previous record/token stays durable.
            error = None
            for pid, start in r['procs']:
                try:
                    if not alive(pid, start): continue
                    sig = signal.SIGKILL if now() >= bound else signal.SIGTERM
                    if signal_exact(pid, start, sig) and sig == signal.SIGKILL:
                        self.st.event(ev='kill', name=r['name'], pid=pid)
                except Exception as e: error = e
            if error is not None: raise error

    def halt(self, t0, reason='supervisor errors'):
        """Retain the first recovery origin independently of job-record publication."""
        self.restore_bounds()
        self.ending = self.ending or reason
        self.recovery_origin = min(self.recovery_origin, t0) if self.recovery_origin is not None else t0
        self.origin = min(self.origin, t0) if self.origin is not None else t0
        self.st.journal(dict(kind='recovery', state='stopping', origin=self.recovery_origin,
                             reason=self.ending, deadline=iso(self.deadline_bound)))
        if not os.path.exists(self.st.halt): write_atomic(self.st.halt, dict(origin=self.recovery_origin))
        # This is our observation state, independent of external lease decoding.
        try:
            lk = self.st.lock('observation.lock')
            try:
                self.restore_bounds()
                self.save_bounds()
            finally: lk.close()
        except Exception: pass  # keep the in-memory bound and continue exact stopping

    def emergency(self, t0):
        """HALT first, then serialize generations or signal without mutating job records."""
        self.halt(t0)
        generation = None
        try:
            try: generation = self.st.lock('generation.lock')
            except TimeoutError: pass
            self.restore_bounds()  # Admission may have journaled captured identities during the wait.
            boot = boot_id()
            recs = self.st.records()   # never reuse a snapshot taken before acquiring the lock
            tokens = any(r['state'] in ('intent', 'gone') for r in recs.values())
            self.restore_stops(recs)
            error = None
            # Enforce cached bounds before external reading or scanning can exhaust a budget.
            # Then tighten against a new observation, still propagating control BaseExceptions.
            try: self.cached_stops(recs, t0, emergency=True, persist=generation is not None, discover_tokens=tokens)
            except Exception as e: error = e
            try: self.read_lease()
            except Exception: pass
            if not tokens:
                try: procs = scan()
                except Exception: procs = {}
                discover(recs, procs, boot)
            for r in recs.values():
                if r.get('boot') != boot or r['state'] not in ('running', 'stopping') or not r['procs']: continue
                try: self.stop_owned(r, t0, persist=generation is not None)
                except Exception as e: error = e
            if error is not None: raise error
        finally:
            if generation is not None: generation.close()


def supervise(a, st, lease_path):
    if not (math.isfinite(a.poll) and 0 < a.poll <= MAX_POLL): raise SystemExit('poll must be in (0, %d] s' % MAX_POLL)
    require_pidfd()
    held = st.lock('supervisor.lock', block=False)
    if held is None: raise SystemExit('refused: a supervisor is already live on this host')
    write_atomic(os.path.join(st.dir, 'supervisor.json'),
                 dict(pid=os.getpid(), start=proc_stat(os.getpid())[4], boot=boot_id(), started_utc=iso(now())))
    sv = Supervisor(st, lease_path, a.poll)
    run_loop(sv, a.poll)


class CadenceError(BaseException): pass


@contextmanager
def bounded_work(seconds=None):
    if seconds is None: seconds = WORK_BUDGET
    # CLI supervision runs in the main thread. SIGALRM interrupts locks, telemetry and /proc work.
    def expired(*_): raise CadenceError('supervision work exceeded wall-time budget')
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old)


def run_loop(sv, poll, sleep=time.sleep):
    errors, t0 = 0, None
    interval = min(poll, MAX_POLL / 2)
    next_poll = time.monotonic()
    while True:
        try:
            if time.monotonic() - next_poll > LOCK_WAIT:
                raise CadenceError('missed monotonic lease-check deadline')
            with bounded_work():
                if sv.poll() == 'ended': return
            errors = 0
        except (Exception, CadenceError) as e:
            errors += 1
            # A missed budget or lock deadline drains immediately, without waiting for another poll.
            fatal = isinstance(e, (TimeoutError, CadenceError))
            if fatal or errors >= BREACH_POLLS:
                t0 = t0 if t0 is not None else now()
                try:
                    with bounded_work(): sv.emergency(t0)
                except (Exception, CadenceError): pass
            try:
                with bounded_work(): sv.st.event(ev='poll-error', n=errors, error='%s: %s' % (type(e).__name__, e))
            except (Exception, CadenceError): pass
        next_poll += interval
        # Never add work duration to the interval. An overrun starts the next check immediately.
        sleep(max(0, next_poll - time.monotonic()))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='op', required=True)
    s = sub.add_parser('supervise'); s.add_argument('--poll', type=float, default=30)
    s = sub.add_parser('admit')
    s.add_argument('--name', required=True); s.add_argument('--workers', type=int, required=True)
    s.add_argument('--pss-gb', type=float, required=True); s.add_argument('--gpu-gb', type=float, default=0)
    s.add_argument('--grace', type=int, default=600); s.add_argument('--cwd', default=os.getcwd())
    s.add_argument('cmd', nargs=argparse.REMAINDER)
    sub.add_parser('status'); sub.add_parser('release')
    a = p.parse_args(argv)
    os.setpriority(os.PRIO_PROCESS, 0, max(NICE_MIN, os.getpriority(os.PRIO_PROCESS, 0)))
    h = host()
    if h not in HOSTS: raise SystemExit('refused: host %s is not leased (%s)' % (h, sorted(HOSTS)))
    st, lease = State(STATE_ROOT, h), os.path.join(LEASE_DIR, h + '.json')   # exact fleet lease, no override
    if a.op == 'admit':
        a.cmd = a.cmd[1:] if a.cmd[:1] == ['--'] else a.cmd
        if not a.cmd: raise SystemExit('admit needs -- CMD')
        admit(a, st, lease)
    elif a.op == 'supervise': supervise(a, st, lease)
    elif a.op == 'release':
        with safe_open(st.release, 'w') as f: f.write(iso(now()) + '\n')
        print('release requested; supervisor drains owned jobs and writes its own ended.json; owner lease stays untouched')
    else:
        print(json.dumps(dict(supervisor_live=st.supervisor_live(), release=os.path.exists(st.release),
                              jobs=st.records()), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
