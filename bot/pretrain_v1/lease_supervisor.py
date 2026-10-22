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
grace (<= 30 min, counted from the lease file's reclaim edit, less one poll so detection and kill polls fit inside
it) ends, or EXIT_MARGIN plus one poll before the hard stop, whichever is first. The job must checkpoint and exit
within its grace; it resumes by being admitted again under the same name once its record is `gone`.

The lease's `status` becomes `ended` only after every owned process is gone, no record is uncertain, and the lease
still has the identity (project, coordinator, grantor, start) the supervisor started under; a replaced lease stops
our jobs but is never mutated. The edit preserves every other field. Protocol: editors take flock(LOCK_EX) on the
lease file; the supervisor holds it, re-reads and compares bytes just before the atomic rename. A writer that ignores
the flock and writes inside that sub-millisecond window can still be lost; this is not a general CAS.
"""
import argparse, ctypes, errno, fcntl, json, math, os, signal, socket, subprocess, sys, time, uuid
from datetime import datetime, timezone

HOSTS = {'127x09': 96, '127x12': 64, '127x17': 96}   # max clasher processes per host, all owners
HARD_STOP = '2026-10-25T07:53:00Z'
LEASE_DIR = '/mpac/sdicks02/fleet-leases'
STATE_ROOT = '/mpac/sdicks02/jobs/clasher/lease-20261022'
ALLOWED_ROOTS = ('/mpac/sdicks02/repos/clasher', '/mpac/sdicks02/jobs/clasher/')
GIB = 1 << 30
PSS_CAP_GB, MEM_MIN_GB, LOAD_MAX, GPU_FREE_MIN_GB, NICE_MIN = 64, 28, 90, 8, 10
MAX_GRACE, MAX_POLL, EXIT_MARGIN, MIN_RUNTIME, BREACH_POLLS = 1800, 60, 600, 300, 2
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


def write_atomic(path, data):
    tmp = '%s.tmp-%d' % (path, os.getpid())
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=1, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    d = os.open(os.path.dirname(path), os.O_RDONLY); os.fsync(d); os.close(d)


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
        if proc_stat(pid) != st: continue          # exited or exec'd mid-read; next poll sees it
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
                           capture_output=True, text=True, timeout=30)
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
    with open(path) as f: d = json.load(f)
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
        with open(path, 'rb') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            raw = f.read(); d = json.loads(raw.decode())
            if lease_identity(d) != identity: raise RuntimeError('lease identity changed; not ours to end')
            if d.get('status') == 'ended': return d
            d['status'] = 'ended'
            tmp = '%s.ended-tmp-%d' % (path, os.getpid())
            with open(tmp, 'w') as t:
                json.dump(d, t, indent=2); t.write('\n'); t.flush(); os.fsync(t.fileno())
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
            with open(path, 'rb') as g: same = g.read() == raw
            if same: os.replace(tmp, path); return d
            os.unlink(tmp)
    raise RuntimeError('lease kept changing; status not marked ended')


# ---------------------------------------------------------------- state
class State:
    def __init__(self, root, h):
        self.h, self.dir = h, os.path.join(root, h)
        self.jobs = os.path.join(self.dir, 'jobs'); self.logs = os.path.join(self.dir, 'logs')
        if not under(self.dir, ALLOWED_ROOTS[1:]): raise SystemExit('state dir outside /mpac/sdicks02/jobs/clasher/')
        for d in (self.jobs, self.logs): os.makedirs(d, exist_ok=True)
        self.release, self.halt = os.path.join(self.dir, 'RELEASE'), os.path.join(self.dir, 'HALT')

    def lock(self, name, block=True):
        f = open(os.path.join(self.dir, name), 'a+')
        try: fcntl.flock(f, fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
        except BlockingIOError: f.close(); return None
        return f

    def supervisor_live(self):
        f = self.lock('supervisor.lock', block=False)
        if f is None: return True
        f.close(); return False

    def records(self):
        """{name: record}; a record that cannot be parsed is returned as {'state': 'uncertain'}."""
        out = {}
        for n in sorted(os.listdir(self.jobs)):
            if not n.endswith('.json'): continue
            try:
                with open(os.path.join(self.jobs, n)) as f: r = json.load(f)
                if r.get('name') != n[:-5] or r.get('state') not in ('intent', 'running', 'stopping', 'gone'):
                    raise ValueError
            except (ValueError, OSError): r = {'name': n[:-5], 'state': 'uncertain'}
            out[n[:-5]] = r
        return out

    def save(self, r): write_atomic(os.path.join(self.jobs, r['name']+'.json'), r)

    def event(self, **kw):
        kw['utc'] = iso(now())
        with open(os.path.join(self.dir, 'events.jsonl'), 'a') as f: f.write(json.dumps(kw, sort_keys=True)+'\n')


def owned(r, procs, boot):
    """Refresh r['procs'] to every live owned process. Returns {pid: proc}."""
    if r.get('boot') != boot: r['procs'] = []; return {}
    tok = ('\0%s=%s\0' % (MARKER, r['token'])).encode()
    have = {pid: procs[pid] for pid, start in r.get('procs', []) if pid in procs and procs[pid]['start'] == start}
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
    return {r['name']: owned(r, procs, boot) for r in recs.values() if r['state'] in ('running', 'stopping')}


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
        if not a.name.replace('-', '').replace('_', '').replace('.', '').isalnum():
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
        if os.path.exists(r['stop_file']): os.unlink(r['stop_file'])
        st.save(r)                                   # intent precedes spawn: a crash here is visible and blocks
        env = dict(os.environ, **{MARKER: token, 'CLASHER_LEASE_STOP_FILE': r['stop_file'],
                                  'CLASHER_LEASE_STOP_BY_UTC': r['stop_by_utc'], 'PYTHONDONTWRITEBYTECODE': '1'})
        if not a.gpu_gb: env['CUDA_VISIBLE_DEVICES'] = ''
        try:
            with open(r['log'], 'ab') as log, open(os.devnull, 'rb') as nul:
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
        with open(r['stop_file'], 'w') as f: f.write(json.dumps(dict(reason=reason, utc=iso(t))) + '\n')
        origin = min(t, self.origin) if self.origin and reason == self.ending else t
        r.update(state='stopping', stop_reason=reason, stop_sent_utc=iso(t),
                 kill_at=max(t, min(origin + r['grace'], deadline - EXIT_MARGIN) - self.poll_s))
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
                    with open(path) as f: self.identity = json.load(f)
                if self.ending is None:
                    self.ending = 'lease replaced' if lease_identity(d) != self.identity else lease_ending(d)
                    if self.ending: self.origin = os.stat(self.lease_path).st_mtime   # reclaim edit time
            except (OSError, ValueError, KeyError) as e:  # unreadable twice: stop work, but never mutate the lease
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
                elif r['state'] == 'stopping' and t >= r['kill_at']:
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
            if (self.ending in ('reclaim', 'release', 'lease expiry', 'lease replaced') or
                    (self.ending or '').startswith('lease status')) and \
                    all(r['state'] == 'gone' for r in recs.values()) and not self.lease_bad:
                if self.ending == 'lease replaced':
                    st.event(ev='lease-replaced', note='owned jobs gone; replacement lease left untouched'); return 'ended'
                try: mark_lease_ended(self.lease_path, self.identity)
                except (OSError, ValueError, RuntimeError) as e: st.event(ev='lease-end-failed', error=str(e)); return None
                st.event(ev='lease-ended', reason=self.ending)
                return 'ended'
        finally: lk.close()

    def emergency(self, t0):
        """Polls keep failing: stop every recorded owned process by exact identity; never touches the lease."""
        self.ending = self.ending or 'supervisor errors'
        if not os.path.exists(self.st.halt):
            with open(self.st.halt, 'w') as f: f.write(iso(now()) + '\n')
        hard = parse_utc(HARD_STOP) - EXIT_MARGIN - self.poll_s
        kill = now() >= min(t0 + MAX_GRACE - self.poll_s, hard)
        for n in os.listdir(self.st.jobs):
            try:
                with open(os.path.join(self.st.jobs, n)) as f: r = json.load(f)
                for pid, start in r.get('procs', []) if r.get('state') in ('running', 'stopping') else []:
                    signal_exact(pid, start, signal.SIGKILL if kill else signal.SIGTERM)
            except (OSError, ValueError, AttributeError, TypeError): continue


def supervise(a, st, lease_path):
    if not (math.isfinite(a.poll) and 0 < a.poll <= MAX_POLL): raise SystemExit('poll must be in (0, %d] s' % MAX_POLL)
    require_pidfd()
    held = st.lock('supervisor.lock', block=False)
    if held is None: raise SystemExit('refused: a supervisor is already live on this host')
    write_atomic(os.path.join(st.dir, 'supervisor.json'),
                 dict(pid=os.getpid(), start=proc_stat(os.getpid())[4], boot=boot_id(), started_utc=iso(now())))
    sv = Supervisor(st, lease_path, a.poll)
    run_loop(sv, a.poll)


def run_loop(sv, poll, sleep=time.sleep):
    errors, t0 = 0, None
    while True:
        try:
            if sv.poll() == 'ended': return
            errors = 0
        except Exception as e:                       # never spin silently: two failures in a row drain owned work
            errors += 1
            try: sv.st.event(ev='poll-error', n=errors, error='%s: %s' % (type(e).__name__, e))
            except OSError: pass
            if errors >= BREACH_POLLS:
                t0 = t0 or now()
                try: sv.emergency(t0)
                except Exception: pass
        sleep(poll)


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
        with open(st.release, 'w') as f: f.write(iso(now()) + '\n')
        print('release requested; supervisor stops owned jobs, then marks the lease ended')
    else:
        print(json.dumps(dict(supervisor_live=st.supervisor_live(), release=os.path.exists(st.release),
                              jobs=st.records()), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
