"""X4S-4 external watchdog (r10, coordinator rulings SR-1/SR-2; exploration, NEVER ADOPTABLE). One file, stdlib only.

The authoritative host-safety backstop on 127x01. It runs OUTSIDE the study's process tree (own session, no study
marker) and starts before any study process; driver.py, supervise.py and guard.py refuse to start without it.

  watchdog.py start  [--job J]   launcher: starts `run` detached (setsid), waits for its first heartbeat
  watchdog.py status [--job J]   exit 0 only if the recorded watchdog is alive, its heartbeat is < 30 s old, no HALT
  watchdog.py stop   [--job J]   operator STOP: records the STOP start durably, then creates STOP
  watchdog.py resume [--job J]   the ONLY sanctioned STOP removal: records the period durably (start before removal,
                                 end after removal) so rule H-1 never loses a STOP interval (R9-F5); refused after HALT
  watchdog.py run    [--job J]   the loop (foreground)

Study tree (R9-F3). A process is a member if any of these holds:
  * its exec environment carries X4S4_STUDY=<job>; every study entry point requires that marker;
  * its parent is a member and it started no earlier than that parent, so helpers launched with an exact
    environment (io.run_checked) and processes that exec with a cleaned environment are members;
  * it was seen as a member before with the same start time. Membership is retained by (pid, starttime).
The deadline exemption covers only the subtree of a readout runner: a member whose command line is guard.py with
--readout and whose environment carries X4S4_READOUT=1. guard.py accepts --readout only for the exact invocation
`/bin/bash <repo>/reports/explore/x4s3/runtime.sh <repo>/reports/explore/x4s4/{contention,reduce,write_report}.py`.

Schedule (R9-F1/F2). A worker thread performs measurement cycles, each a complete set of checks, starting every CYCLE
(9.5 s). Every heartbeat, log and control-file write also happens in that worker. The main thread never measures and
never writes to job files while checking. It HALTs on any of these:
  * a measurement still running after MEASURE_BUDGET (8 s);
  * no new measurement started within CYCLE + 0.5 s of the previous start, so checks are always <= 10 s apart;
  * no worker progress of any kind (including a stuck heartbeat or log write) for STALL (30 s);
  * a breach or a failed or malformed measurement.
Checks, every cycle:
  * STOP: the tree must be empty STOP_GRACE (180 s) after STOP appeared. STOP periods are logged.
  * the deadline (HARD-STOP-UTC.txt): it is held in memory once read. A change, an unreadable file, or study
    processes before it exists is a breach. Production members still alive STOP_GRACE after the deadline are a
    breach; the readout subtree is exempt.
  * MemAvailable >= 24 GiB. Memory PSI must be well formed (0 <= avg10 <= 100); a readable high value is not a breach.
  * <= 70 members, member PSS <= 96 GiB (every smaps_rollup must carry a Pss line).
  * du -sb <job> <= 100 GB within 4 s; nvidia-smi memory.used <= 40 GiB within 2 s. Both outputs are strictly parsed.
HALT is run by the main thread, so it never waits on the worker's I/O:
  1. HALT.json (exclusive, 0444, fsync'd; the first reason wins) and STOP are written by a helper thread bounded at 5 s.
  2. Every member is stopped one at a time by PID, re-verified by (pid, starttime, membership) immediately before
     each signal: TERM, then KILL after KILL_GRACE. No group signals. Signal records are queued for best-effort
     logging, and teardown never depends on them.
  3. The tree is re-scanned until it is empty. The watchdog then stays in kill mode: HALT is a hard stop.
Confined I/O (R9-F8). The watchdog's own files live under <job> and <job>/watchdog only. They are opened from
directory fds reached by an O_NOFOLLOW walk. Leaves are opened O_NOFOLLOW|O_NONBLOCK and must be single-link regular
files. Temps are exclusive (O_EXCL) and uniquely named. Symlinks, hard links, FIFOs and other special files are refused.
It never reads results: it reads only /proc, STOP, the deadline file, du/nvidia-smi output and its own files.
The options after `--job` exist for the offline tests; the runbook uses the defaults.
"""
import argparse, calendar, json, math, os, queue, secrets, signal, stat as stat_, subprocess, sys, threading, time

MARK, READOUT = 'X4S4_STUDY', 'X4S4_READOUT'
DEFAULT_JOB = '/mpac/sdicks02/jobs/clasher/x4s4-onpolicy'
NF = os.O_NOFOLLOW | os.O_CLOEXEC


def utc(t=None): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


# ---------------------------------------------------------------- confined I/O for the watchdog's own files (R9-F8)
def open_dir(path):
    """fd of an absolute directory, walking every component with O_NOFOLLOW|O_DIRECTORY (no symlinked ancestor)."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in [p for p in path.split('/') if p]:
            if part in ('.', '..'): raise OSError(f'non-canonical path {path}')
            nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | NF, dir_fd=fd); os.close(fd); fd = nfd
        return fd
    except BaseException:
        os.close(fd); raise


def _leaf_check(fd, name):
    st = os.fstat(fd)
    if not stat_.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd); raise OSError(f'{name}: not a single-link regular file')


def read_small(dfd, name, limit=1 << 20):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | NF, dir_fd=dfd); _leaf_check(fd, name)
    try: return os.read(fd, limit).decode()
    finally: os.close(fd)


def exists(dfd, name):
    try: os.stat(name, dir_fd=dfd, follow_symlinks=False); return True
    except FileNotFoundError: return False


def write_atomic(dfd, name, obj):
    tmp = f'.{name}.tmp-{os.getpid()}-{secrets.token_hex(4)}'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NF, 0o644, dir_fd=dfd)
    try:
        os.write(fd, json.dumps(obj).encode()); os.fsync(fd)
    finally:
        os.close(fd)
    try:
        st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        if not stat_.S_ISREG(st.st_mode) or st.st_nlink != 1: raise OSError(f'{name}: not a single-link regular file')
    except FileNotFoundError:
        pass
    except BaseException:
        os.unlink(tmp, dir_fd=dfd); raise
    os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd); os.fsync(dfd)


def append(dfd, name, obj):
    fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK | NF, 0o644, dir_fd=dfd); _leaf_check(fd, name)
    try: os.write(fd, (json.dumps(obj)+'\n').encode()); os.fsync(fd)
    finally: os.close(fd)


def create_excl(dfd, name, obj, mode):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NF, mode, dir_fd=dfd)
    try:
        os.fchmod(fd, mode); os.write(fd, json.dumps(obj).encode()); os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(dfd)


def dirs(job, create=False):
    jfd = open_dir(job)
    if create and not exists(jfd, 'watchdog'): os.mkdir('watchdog', 0o755, dir_fd=jfd)
    return jfd, os.open('watchdog', os.O_RDONLY | os.O_DIRECTORY | NF, dir_fd=jfd)


def bounded(fn, timeout):
    """Run fn in a daemon thread; (True, value) if it finished within timeout, else (False, None). Exceptions -> (True, exc)."""
    box = {}
    def run():
        try: box['v'] = fn()
        except BaseException as exc: box['v'] = exc
    t = threading.Thread(target=run, daemon=True); t.start(); t.join(timeout)
    return (False, None) if t.is_alive() else (True, box.get('v'))


# ---------------------------------------------------------------- /proc
def pstat(pid):
    """(starttime, state, ppid) of a live pid, else None."""
    try:
        with open(f'/proc/{pid}/stat', 'rb') as f: rest = f.read().rsplit(b')', 1)[1].split()
        return int(rest[19]), rest[0].decode(), int(rest[1])
    except (OSError, IndexError, ValueError):
        return None


def penv(pid):
    try:
        with open(f'/proc/{pid}/environ', 'rb') as f: return f.read().split(b'\0')
    except OSError:
        return []


def pargs(pid):
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f: return [a.decode('utf-8', 'replace') for a in f.read().split(b'\0') if a]
    except OSError:
        return []


class Tree:
    """Study membership closed over launched work, retained by (pid, starttime) across exec (R9-F3)."""
    def __init__(self, job):
        self.job, self.mark = job, (MARK+'='+job).encode()
        self.known, self.readout_known = set(), set()

    def scan(self):
        """{pid: starttime} of members and the set of readout-exempt pids (never this process, never zombies)."""
        me, procs = os.getpid(), {}
        for n in os.listdir('/proc'):
            if n.isdigit() and int(n) != me:
                s = pstat(int(n))
                if s and s[1] != 'Z': procs[int(n)] = s
        live = {(p, s[0]) for p, s in procs.items()}
        self.known &= live; self.readout_known &= live
        members = {p for p, s in procs.items() if (p, s[0]) in self.known or self.mark in penv(p)}
        roots = {p for p in members if (p, procs[p][0]) in self.readout_known or self.readout_root(p)}
        changed = True
        while changed:                                                   # descendants of members (and of readout roots)
            changed = False
            for p, (start, _, ppid) in procs.items():
                if ppid in procs and start >= procs[ppid][0]:
                    if ppid in members and p not in members: members.add(p); changed = True
                    if ppid in roots and p not in roots: roots.add(p); changed = True
        members.discard(me)
        self.known |= {(p, procs[p][0]) for p in members}
        self.readout_known |= {(p, procs[p][0]) for p in roots if p in members}
        return {p: procs[p][0] for p in members}, roots & members

    def readout_root(self, pid):
        a = pargs(pid)
        return (READOUT+'=1').encode() in penv(pid) and any(x.endswith('/reports/explore/x4s4/guard.py') for x in a) and '--readout' in a

    def still(self, pid, start):
        """Re-verification immediately before a signal: same pid and start time, and a member."""
        s = pstat(pid)
        return bool(s and s[0] == start and s[1] != 'Z' and ((pid, start) in self.known or self.mark in penv(pid)))


def run_bounded(argv, timeout):
    r = subprocess.run(argv, capture_output=True, timeout=timeout, env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'}, check=True)
    return r.stdout.decode()


def nonneg_int(text, what):
    v = int(text)
    if v < 0: raise ValueError(f'{what} negative: {v}')
    return v


# ---------------------------------------------------------------- the watchdog
class Watchdog:
    def __init__(self, a):
        self.a, self.job = a, a.job
        self.jfd, self.wfd = dirs(a.job, create=True)
        self.tree = Tree(a.job)
        self.deadline = self.deadline_text = None
        self.stop_since = None
        self.halted, self.breach = None, None
        self.m_start = self.m_done = self.last_start = None
        self.progress = time.monotonic()
        self.logq = queue.Queue()

    # ---- one bounded set of checks (worker thread)
    def measure(self):
        a, now = self.a, time.time()
        r = dict(epoch=now)
        members, roots = self.tree.scan(); r['processes'] = len(members)
        if exists(self.jfd, 'STOP'):                                       # STOP periods (H-1) + the stop grace
            if self.stop_since is None:
                self.stop_since = os.stat('STOP', dir_fd=self.jfd, follow_symlinks=False).st_mtime
                append(self.wfd, 'stop-periods.jsonl', dict(kind='start', epoch=self.stop_since, observed=now, source='watchdog'))
            if members and now-self.stop_since > a.stop_grace: return f'STOP not honoured within {a.stop_grace:g} s ({len(members)} study processes)', r
        elif self.stop_since is not None:
            append(self.wfd, 'stop-periods.jsonl', dict(kind='end', epoch=now, source='watchdog')); self.stop_since = None
        if self.deadline is None and exists(self.jfd, 'HARD-STOP-UTC.txt'):
            self.deadline_text = read_small(self.jfd, 'HARD-STOP-UTC.txt', 64)
            self.deadline = calendar.timegm(time.strptime(self.deadline_text.strip(), '%Y-%m-%dT%H:%M:%SZ'))
        if self.deadline is None:
            if members: return 'study processes exist before the deadline file', r
        else:
            if read_small(self.jfd, 'HARD-STOP-UTC.txt', 64) != self.deadline_text: return 'deadline file changed', r
            r['deadline'] = self.deadline
            prod = [p for p in members if p not in roots]
            if now >= self.deadline and prod and now-self.deadline > a.stop_grace:
                return f'{len(prod)} production study processes alive {a.stop_grace:g} s after the deadline', r
        with open(a.meminfo) as f:
            mems = [x for x in f if x.startswith('MemAvailable:')]
        if len(mems) != 1 or mems[0].split()[2:] != ['kB']: return 'measurement failed: MemAvailable malformed', r
        mem = nonneg_int(mems[0].split()[1], 'MemAvailable')*1024; r['mem_available'] = mem
        if mem < a.mem_floor: return f'MemAvailable {mem} < {a.mem_floor}', r
        try:
            with open(a.psi) as f: first = f.readline().split()
            if first[0] != 'some': raise ValueError('no "some" line')
            vals = dict(x.split('=', 1) for x in first[1:])
            psi = float(vals['avg10'])
            if not (math.isfinite(psi) and 0.0 <= psi <= 100.0): raise ValueError(f'avg10 out of range: {psi}')
        except (OSError, IndexError, ValueError, KeyError) as exc:
            return f'memory PSI unreadable or malformed: {exc}', r
        r['psi_some_avg10'] = psi
        if len(members) > a.max_procs: return f'{len(members)} study processes > {a.max_procs}', r
        pss = 0
        for pid in members:
            try:
                with open(f'/proc/{pid}/smaps_rollup') as f: rows = [l for l in f if l.startswith('Pss:')]
            except (FileNotFoundError, ProcessLookupError): continue          # exited since the scan
            if len(rows) != 1 or rows[0].split()[2:] != ['kB']: return f'measurement failed: smaps_rollup of {pid} has no Pss line', r
            pss += nonneg_int(rows[0].split()[1], 'Pss')*1024
        r['tree_pss'] = pss
        if pss > a.tree_pss: return f'study PSS {pss} > {a.tree_pss}', r
        out = run_bounded([a.du, '-sb', '--', self.job], a.du_timeout).split('\n')[0].split('\t')
        if len(out) != 2 or out[1] != self.job: return 'measurement failed: du output malformed', r
        disk = nonneg_int(out[0], 'du'); r['disk'] = disk
        if disk > a.max_disk: return f'disk {disk} > {a.max_disk}', r
        lines = [l.strip() for l in run_bounded([a.nvidia_smi, '--query-gpu=memory.used', '--format=csv,noheader,nounits'], a.gpu_timeout).splitlines() if l.strip()]
        if not lines: return 'measurement failed: nvidia-smi printed nothing', r
        gpu = sum(nonneg_int(l, 'GPU memory') for l in lines); r['gpu_mib'] = gpu
        if gpu > a.gpu_limit_mib: return f'GPU {gpu} MiB > {a.gpu_limit_mib}', r
        return None, r

    # ---- worker: measurements, heartbeat and queued log lines; every step marks progress
    def worker(self):
        me = os.getpid()
        while self.halted is None:
            t0 = time.monotonic(); self.m_done = None; self.last_start = self.m_start = t0
            try: why, readings = self.measure()
            except Exception as exc: why, readings = f'measurement failed: {exc!r}', {}
            self.m_done = time.monotonic(); self.progress = self.m_done
            if why and self.breach is None: self.breach = (why, readings)
            try:
                write_atomic(self.wfd, 'heartbeat.json', dict(utc=utc(), epoch=time.time(), pid=me, halted=self.halted, readings=readings))
                self.flush_log()
            except Exception as exc:
                if self.breach is None: self.breach = (f'watchdog write failed: {exc!r}', {})
            self.progress = time.monotonic()
            time.sleep(max(0.0, self.a.cycle-(time.monotonic()-t0)))

    def flush_log(self):
        while True:
            try: rec = self.logq.get_nowait()
            except queue.Empty: return
            append(self.wfd, 'watchdog.log', rec)

    # ---- main thread: schedule/stall supervision and the HALT path (no job-file I/O except bounded helpers)
    def run(self):
        if alive(self.job, mine_ok=True): raise SystemExit('a watchdog is already running for this job')
        me = os.getpid()
        ok, err = bounded(lambda: (write_atomic(self.wfd, 'pid.json', dict(pid=me, starttime=pstat(me)[0], utc=utc())),
                                   append(self.wfd, 'stop-periods.jsonl', dict(kind='watchdog_start', epoch=time.time()))), 5.0)
        if not ok or isinstance(err, BaseException): raise SystemExit(f'cannot publish the watchdog pid: {err!r}')
        if exists(self.jfd, 'HALT.json'): self.halt('HALT.json present at start', {})
        threading.Thread(target=self.worker, daemon=True).start()
        while True:
            time.sleep(0.2)
            if self.halted is not None: self.kill_tree(); continue        # hard stop: nothing may run again
            why, readings = self.due(time.monotonic())
            if why: self.halt(why, readings)

    def due(self, now):
        """The main thread's decision (no I/O): a reported breach, an overdue measurement, a late measurement start
        (checks must stay <= cycle+0.5 s apart) or no worker progress for STALL s."""
        if self.breach: return self.breach
        if self.m_done is None and self.m_start is not None and now-self.m_start > self.a.measure_budget:
            return f'measurement overdue (> {self.a.measure_budget:g} s)', {}
        if self.last_start is not None and now-self.last_start > self.a.cycle+0.5:
            return f'no measurement started within {self.a.cycle+0.5:g} s', {}
        if now-self.progress > self.a.stall: return f'watchdog stalled > {self.a.stall:g} s', {}
        return None, {}

    def halt(self, reason, readings):
        self.halted = reason
        def mark():
            try: create_excl(self.jfd, 'HALT.json', dict(utc=utc(), epoch=time.time(), reason=reason, readings=readings,
                                                         label='X4S-4 watchdog HALT; hard stop'), 0o444)
            except FileExistsError: pass                                    # the first HALT reason stands
            if not exists(self.jfd, 'STOP'): os.symlink('HALT.json', 'STOP', dir_fd=self.jfd)
        bounded(mark, 5.0)                                                  # never blocks teardown
        self.logq.put(dict(utc=utc(), kind='HALT', reason=reason, readings=readings))
        threading.Thread(target=self.best_effort_log, daemon=True).start()
        self.kill_tree()

    def best_effort_log(self):
        while True:
            try: self.flush_log()
            except Exception: pass
            time.sleep(1.0)

    def kill_tree(self):
        first = {}
        while True:
            members, _ = self.tree.scan()
            if not members: return
            for pid, start in members.items():
                if not self.tree.still(pid, start): continue                # re-verified immediately before the signal
                t0 = first.setdefault((pid, start), time.monotonic())
                sig = signal.SIGKILL if time.monotonic()-t0 >= self.a.kill_grace else signal.SIGTERM
                try: os.kill(pid, sig)
                except ProcessLookupError: pass
                self.logq.put(dict(utc=utc(), kind='signal', pid=pid, starttime=start, signal=int(sig)))
            time.sleep(1.0)


# ---------------------------------------------------------------- status / control
def alive(job, mine_ok=False):
    """The recorded watchdog process is alive with its recorded start time (and is not this process)."""
    try:
        jfd, wfd = dirs(job)
        try: p = json.loads(read_small(wfd, 'pid.json'))
        finally: os.close(wfd); os.close(jfd)
    except (OSError, ValueError):
        return False
    s = pstat(p.get('pid', -1))
    return bool(s and s[0] == p.get('starttime') and s[1] != 'Z' and not (mine_ok and p['pid'] == os.getpid()))


def status(job, max_age=30.0):
    try:
        jfd, wfd = dirs(job)
        try:
            hb = json.loads(read_small(wfd, 'heartbeat.json')); halted = exists(jfd, 'HALT.json')
        finally:
            os.close(wfd); os.close(jfd)
    except (OSError, ValueError):
        return 'no heartbeat', None
    if not alive(job): return 'watchdog not alive', hb
    if time.time()-hb.get('epoch', 0) > max_age: return 'heartbeat older than 30 s', hb
    if hb.get('halted') or halted: return f"HALTED: {hb.get('halted') or 'HALT.json'}", hb
    return None, hb


def open_periods(wfd):
    """True if the durable STOP history has a start without an end."""
    is_open = False
    for line in read_small(wfd, 'stop-periods.jsonl', 64 << 20).splitlines():
        k = json.loads(line).get('kind')
        if k == 'start': is_open = True
        elif k == 'end': is_open = False
    return is_open


def operator_stop(job):
    jfd, wfd = dirs(job)
    try:
        append(wfd, 'stop-periods.jsonl', dict(kind='start', epoch=time.time(), source='operator stop'))   # durable first
        if not exists(jfd, 'STOP'): os.symlink('operator-STOP', 'STOP', dir_fd=jfd)
    finally:
        os.close(wfd); os.close(jfd)


def operator_resume(job):
    """R9-F5: STOP removal with durable evidence: the period's start is on disk before STOP goes, its end after."""
    jfd, wfd = dirs(job)
    try:
        if exists(jfd, 'HALT.json'): raise SystemExit('HALT is a hard stop: no resume')
        if not exists(jfd, 'STOP'): raise SystemExit('no STOP to remove')
        if not open_periods(wfd):
            m = os.stat('STOP', dir_fd=jfd, follow_symlinks=False).st_mtime
            append(wfd, 'stop-periods.jsonl', dict(kind='start', epoch=min(m, time.time()), source='resume'))
        os.unlink('STOP', dir_fd=jfd)
        append(wfd, 'stop-periods.jsonl', dict(kind='end', epoch=time.time(), source='resume'))
    finally:
        os.close(wfd); os.close(jfd)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['start', 'status', 'stop', 'resume', 'run']); ap.add_argument('--job', default=DEFAULT_JOB)
    for k, v in dict(cycle=9.5, measure_budget=8.0, stall=30.0, stop_grace=180.0, kill_grace=20.0, du_timeout=4.0, gpu_timeout=2.0,
                     mem_floor=24*2**30, max_procs=70, tree_pss=96*2**30, max_disk=100*10**9, gpu_limit_mib=40*1024).items():
        ap.add_argument('--'+k.replace('_', '-'), type=type(v), default=v)
    for k, v in dict(du='/usr/bin/du', nvidia_smi='/usr/bin/nvidia-smi', meminfo='/proc/meminfo', psi='/proc/pressure/memory').items():
        ap.add_argument('--'+k.replace('_', '-'), default=v)
    args = list(sys.argv[1:] if argv is None else argv)
    a = ap.parse_args(args)
    a.job = os.path.abspath(a.job)
    if a.measure_budget >= a.cycle: raise SystemExit('--measure-budget must be below --cycle')
    if a.cmd == 'run':
        Watchdog(a).run()
    elif a.cmd == 'status':
        why, hb = status(a.job); print(json.dumps(dict(ok=why is None, why=why, heartbeat=hb))); raise SystemExit(0 if why is None else 1)
    elif a.cmd == 'stop':
        operator_stop(a.job); print(json.dumps(dict(stop=True)))
    elif a.cmd == 'resume':
        operator_resume(a.job); print(json.dumps(dict(resumed=True)))
    else:
        jfd, wfd = dirs(a.job, create=True)
        if alive(a.job): raise SystemExit('a watchdog is already running for this job')
        env = {k: v for k, v in os.environ.items() if k not in (MARK, READOUT)}     # never part of the study tree
        out = os.open('watchdog.out', os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK | NF, 0o644, dir_fd=wfd)
        _leaf_check(out, 'watchdog.out')
        rest = [x for x in args if x != 'start']
        p = subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), 'run']+rest, stdin=subprocess.DEVNULL,
                             stdout=out, stderr=out, env=env, start_new_session=True, close_fds=True)
        os.close(out); os.close(wfd); os.close(jfd)
        t0 = time.time()
        while time.time()-t0 < 3*a.cycle+5:
            why, hb = status(a.job)
            if why is None and hb.get('pid') == p.pid: print(json.dumps(dict(started=p.pid, heartbeat=hb))); return
            if p.poll() is not None: break
            time.sleep(0.2)
        raise SystemExit(f'watchdog did not come up: {status(a.job)[0]}')


if __name__ == '__main__':
    main()
