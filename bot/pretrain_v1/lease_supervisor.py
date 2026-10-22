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

Stop contract (reclaim, release, expiry or sustained resource breach): the supervisor writes the job's
CLASHER_LEASE_STOP_FILE, sends SIGTERM to every owned process, and SIGKILLs whatever is still owned once the job's
grace (<= 30 min, counted from the lease file's reclaim edit, less the enforced 60-second check bound) ends,
or EXIT_MARGIN plus 60 seconds before the hard stop, whichever is first. The job must checkpoint and exit
within its grace; it resumes by being admitted again under the same name once its record is `gone`.

The lease's `status` becomes `ended` only after every owned process is gone, no record is uncertain, and the lease
still has the identity (project, coordinator, grantor, start) the supervisor started under; a replaced lease stops
our jobs but is never mutated. The edit preserves every other field. Lease readers take flock(LOCK_SH); editors
take flock(LOCK_EX), re-read, then write/truncate/fsync the same inode before unlocking. No editor may rename or
unlink the lease. This cooperative protocol does not protect edits by writers that ignore it. See LEASE-RUNBOOK.md.
"""
import argparse, ctypes, errno, fcntl, json, math, os, signal, socket, stat, subprocess, sys, time, uuid
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
LOCK_WAIT, WORK_BUDGET = 5, 25
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


@contextmanager
def lease_file(path, exclusive=False):
    # All cooperating readers use SH; all editors use EX and write this inode in place.
    with safe_open(path, 'r+' if exclusive else 'r') as f:
        flock_bounded(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        a, b = os.fstat(f.fileno()), os.stat(path, follow_symlinks=False)
        if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino): raise RuntimeError('lease inode changed; retry')
        yield f


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
def load_lease(path, h):
    """Readable clasher lease -> (dict, deadline, max clasher procs, PSS cap GiB). Raises OSError/ValueError/KeyError."""
    with lease_file(path) as f: d = json.load(f)
    if d.get('project') != 'clasher': raise ValueError('lease project %r' % d.get('project'))
    deadline = min(parse_utc(HARD_STOP), parse_utc(d['expected_end_utc']))
    num = lambda k, dflt: min(dflt, d[k]) if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) else dflt
    return d, deadline, num('max_workers', HOSTS[h]), num('pss_cap_gb', PSS_CAP_GB)


def lease_identity(d): return [d.get(k) for k in ('project', 'coordinator_thread', 'granted_by', 'start_utc')]


def lease_ending(d):
    """Why a readable lease no longer permits work, or None."""
    if d.get('reclaim') is not False: return 'reclaim'
    if d.get('status') != 'active': return 'lease status %r' % d.get('status')
    return None


def mark_lease_ended(path, identity, tries=5):
    """Set status=ended on our lease only, preserving every other field and edits made before our re-read."""
    for _ in range(tries):
        try:
            with lease_file(path, exclusive=True) as f:
                d = json.load(f)
                if lease_identity(d) != identity: raise ValueError('lease identity changed; not ours to end')
                if d.get('status') == 'ended': return d
                d['status'] = 'ended'
                encoded = json.dumps(d, indent=2) + '\n'
                f.seek(0); f.write(encoded); f.truncate(); f.flush(); os.fsync(f.fileno())
                return d
        except RuntimeError: continue
        except ValueError as e:
            if 'identity changed' in str(e): raise RuntimeError(str(e))
            raise
    raise RuntimeError('lease inode kept changing; status not marked ended')


# ---------------------------------------------------------------- state
class State:
    def __init__(self, root, h):
        self.h, self.dir = h, os.path.join(root, h)
        self.jobs = os.path.join(self.dir, 'jobs'); self.logs = os.path.join(self.dir, 'logs')
        if not under(self.dir, ALLOWED_ROOTS[1:]): raise SystemExit('state dir outside /mpac/sdicks02/jobs/clasher/')
        for d in (self.jobs, self.logs):
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
            except (ValueError, OSError, KeyError, TypeError, AttributeError): r = {'name': n[:-5], 'state': 'uncertain'}
            out[n[:-5]] = r
        return out

    def validate(self, r):
        if not isinstance(r, dict) or not valid_name(r.get('name')): raise ValueError('bad record name')
        if r['state'] in ('running', 'stopping', 'gone'):
            token = r.get('token')
            if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
                raise ValueError('bad token')
            if not isinstance(r.get('boot'), str) or not r['boot']: raise ValueError('bad boot')
            pairs = r['procs']
            if not isinstance(pairs, list): raise ValueError('bad identities')
            for pair in pairs:
                if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int or x <= 0 for x in pair):
                    raise ValueError('bad process identity')
            if r['state'] != 'gone' and r.get('pid') is None: raise ValueError('missing root identity')
            if r.get('pid') is not None and (type(r['pid']) is not int or r['pid'] <= 0 or
                                            type(r.get('start')) is not int or r['start'] <= 0):
                raise ValueError('bad root identity')
            for key in ('workers', 'pss_gb', 'grace'):
                if not isinstance(r[key], (int, float)) or isinstance(r[key], bool) or not math.isfinite(r[key]) or r[key] <= 0:
                    raise ValueError('bad resource contract')
            if r['grace'] > MAX_GRACE: raise ValueError('bad grace')
            if r['state'] == 'stopping':
                if type(r['kill_at']) not in (int, float) or not math.isfinite(r['kill_at']): raise ValueError('bad kill deadline')
                parse_utc(r['stop_sent_utc'])
            if r['stop_file'] != os.path.join(self.jobs, r['name'] + '.stop'): raise ValueError('unsafe stop file')
            if r['log'] != os.path.join(self.logs, '%s-%s.log' % (r['name'], r['token'][:8])): raise ValueError('unsafe log')
            for path in (r['stop_file'], r['log']): check_path(path)

    def save(self, r):
        if not valid_name(r['name']): raise ValueError('bad record name')
        write_atomic(os.path.join(self.jobs, r['name']+'.json'), r)

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
        if r['state'] not in ('running', 'stopping', 'gone'): continue
        mine = owned(r, procs, boot)
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
        try: d, deadline, cap, pss_cap = load_lease(lease_path, st.h)
        except (OSError, ValueError, KeyError) as e: raise SystemExit('refused: lease unreadable: %s' % e)
        if lease_ending(d) or parse_utc(d['start_utc']) > now():
            raise SystemExit('refused: %s' % (lease_ending(d) or 'lease not started'))
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
        s0 = proc_stat(p.pid)                        # unreaped child: its pid cannot be reused yet
        r.update(state='running', pid=p.pid, start=s0[4], procs=[[p.pid, s0[4]]])
        st.save(r); st.event(ev='admit', name=a.name, pid=p.pid, start=s0[4], cmd=a.cmd)
        print(json.dumps(dict(admitted=a.name, pid=p.pid, start=s0[4], log=r['log'], stop_by_utc=r['stop_by_utc'])))
    finally: lk.close()


# ---------------------------------------------------------------- supervise
class Supervisor:
    def __init__(self, st, lease_path, poll=MAX_POLL):
        self.st, self.lease_path, self.poll_s = st, lease_path, poll
        self.breach, self.lease_bad, self.ending, self.origin, self.identity = 0, 0, None, None, None

    def begin_stop(self, r, reason, deadline):
        t = now()
        with safe_open(r['stop_file'], 'w') as f: f.write(json.dumps(dict(reason=reason, utc=iso(t))) + '\n')
        origin = min(t, self.origin) if self.origin and reason == self.ending else t
        r.update(state='stopping', stop_reason=reason, stop_sent_utc=iso(t),
                 kill_at=max(t, min(origin + r['grace'], deadline - EXIT_MARGIN) - MAX_POLL))
        self.st.event(ev='stop', name=r['name'], reason=reason, kill_at=iso(r['kill_at']))

    def poll(self):
        """One supervision step. Returns 'ended' once the lease is marked ended, else None."""
        st = self.st
        lk = st.lock('state.lock')
        try:
            t, boot = now(), boot_id()
            try:
                d, deadline, cap, pss_cap = load_lease(self.lease_path, st.h); self.lease_bad = 0
                if self.identity is None:                       # first lease seen by any supervisor run is ours
                    path = os.path.join(st.dir, 'lease-identity.json')
                    if not os.path.exists(path): write_atomic(path, lease_identity(d))
                    with safe_open(path, 'r') as f: self.identity = json.load(f)
                if d.get('reclaim') is not False:
                    anchor = min(t, os.stat(self.lease_path).st_mtime)
                    self.origin = min(self.origin, anchor) if self.origin is not None else anchor
                if self.ending is None:
                    self.ending = 'lease replaced' if lease_identity(d) != self.identity else lease_ending(d)
                    if self.ending and self.origin is None: self.origin = min(t, os.stat(self.lease_path).st_mtime)   # reclaim edit time
            except (OSError, ValueError, KeyError, RuntimeError) as e:  # unreadable twice: stop work, but never mutate the lease
                if isinstance(e, TimeoutError): raise
                deadline, cap, pss_cap = parse_utc(HARD_STOP), HOSTS[st.h], PSS_CAP_GB
                self.lease_bad += 1
                if self.ending is None and self.lease_bad >= BREACH_POLLS: self.ending = 'lease unreadable: %s' % e
            if self.ending is None and os.path.exists(st.release): self.ending = 'release'
            recs, procs = st.records(), scan()
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
            if (self.ending in ('reclaim', 'release', 'lease expiry', 'lease replaced') or
                    (self.ending or '').startswith('lease status')) and \
                    all(r['state'] == 'gone' for r in recs.values()) and not final_jobs and not self.lease_bad:
                if self.ending == 'lease replaced':
                    st.event(ev='lease-replaced', note='owned jobs gone; replacement lease left untouched'); return 'ended'
                try: mark_lease_ended(self.lease_path, self.identity)
                except TimeoutError: raise
                except (OSError, ValueError, RuntimeError) as e: st.event(ev='lease-end-failed', error=str(e)); return None
                st.event(ev='lease-ended', reason=self.ending)
                return 'ended'
        finally: lk.close()

    def emergency(self, t0):
        """Polls keep failing: stop every recorded owned process by exact identity; never touches the lease."""
        self.ending = self.ending or 'supervisor errors'
        if not os.path.exists(self.st.halt):
            with safe_open(self.st.halt, 'w') as f: f.write(iso(now()) + '\n')
        hard = parse_utc(HARD_STOP) - EXIT_MARGIN - MAX_POLL
        boot = boot_id()
        for r in self.st.records().values():
            if r.get('boot') != boot or r['state'] not in ('running', 'stopping', 'gone'): continue
            # State.records validates schema and output paths before recovery can signal anything.
            bound = min(t0 + r['grace'] - MAX_POLL, hard, r.get('kill_at', hard))
            for pid, start in r['procs']:
                signal_exact(pid, start, signal.SIGKILL if now() >= bound else signal.SIGTERM)


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
        print('release requested; supervisor stops owned jobs, then marks the lease ended')
    else:
        print(json.dumps(dict(supervisor_live=st.supervisor_live(), release=os.path.exists(st.release),
                              jobs=st.records()), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
