"""X4S-4 external watchdog (r9, coordinator ruling SR-1; exploration, NEVER ADOPTABLE). One file, stdlib only.

The authoritative host-safety backstop on 127x01. It runs OUTSIDE the study's process tree (own session, no study
marker) and starts before any study process; driver.py, supervise.py and guard.py refuse to start without it.

  watchdog.py start  [--job J]   launcher: starts `run` detached (setsid), waits for its first heartbeat
  watchdog.py status [--job J]   exit 0 only if the recorded watchdog is alive and its heartbeat is < 30 s old
  watchdog.py run    [--job J]   the loop (foreground)

Study tree = every live process whose exec environment carries X4S4_STUDY=<job>. The study entry points require that
marker and every study child inherits it. Every CYCLE (10 s, start to start) it checks, each measurement bounded:
  * STOP (lexists): STOP itself is an operator pause, not a breach, but the tree must be empty STOP_GRACE (180 s) after
    STOP appeared. That covers the frozen trainer's 120 s checkpoint grace. STOP periods are logged for rule H-1;
  * the deadline (HARD-STOP-UTC.txt): it is read once it exists and then held in memory. A changed or unreadable file,
    or study processes before it exists, is a breach. At the deadline the study's own guards stop production work, and
    the deadline works like STOP: production study processes still alive STOP_GRACE after it are a breach. Processes
    marked X4S4_READOUT=1 are exempt from the deadline only: the E8 readout (contention, reduce, report) runs after the
    stop by design, via guard.py --readout, which alone sets that marker;
  * MemAvailable < 24 GiB or unreadable. Memory PSI unreadable is a breach; readable high PSI only inhibits dispatch
    (the frozen rule);
  * study processes > 70; study PSS (smaps_rollup) > 96 GiB or unreadable;
  * du -sb <job> > 100 GB, failed, or slower than 5 s;
  * nvidia-smi memory.used > 40 GiB, failed, or slower than 3 s.
Each cycle runs in a worker thread joined with a 30 s limit, so a stalled cycle is itself a breach.
On a breach:
  1. <job>/HALT.json is written (exclusive, fsync'd, the first reason wins) and STOP is created.
  2. Every study process is stopped one at a time by PID. Each is re-verified by (pid, starttime, marker) immediately
     before its signal: TERM first, then KILL after KILL_GRACE. No group signals.
  3. The tree is re-scanned until it is empty.
  4. HALT is a hard stop: the watchdog stays in kill mode, so any later study process is stopped too.
It never reads results. It reads only /proc, the STOP/deadline files, du, nvidia-smi and its own files under
<job>/watchdog.
The options after `--job` exist only for the offline tests; the runbook uses the defaults.
"""
import argparse, calendar, json, os, signal, subprocess, sys, threading, time

MARK = 'X4S4_STUDY'
DEFAULT_JOB = '/mpac/sdicks02/jobs/clasher/x4s4-onpolicy'


def utc(t=None): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def stat(pid):
    """(starttime, state) of a live pid, else None."""
    try:
        with open(f'/proc/{pid}/stat', 'rb') as f: rest = f.read().rsplit(b')', 1)[1].split()
        return int(rest[19]), rest[0].decode()
    except (OSError, IndexError, ValueError):
        return None


def marked(pid, job):
    try:
        with open(f'/proc/{pid}/environ', 'rb') as f: return (MARK+'='+job).encode() in f.read().split(b'\0')
    except OSError:
        return False


def readout(pid):
    try:
        with open(f'/proc/{pid}/environ', 'rb') as f: return b'X4S4_READOUT=1' in f.read().split(b'\0')
    except OSError:
        return False


def tree(job):
    """[(pid, starttime)] of every live (non-zombie) study process, never this watchdog."""
    out, me = [], os.getpid()
    for n in os.listdir('/proc'):
        if not n.isdigit() or int(n) == me: continue
        s = stat(int(n))
        if s and s[1] != 'Z' and marked(int(n), job): out.append((int(n), s[0]))
    return out


def run_bounded(argv, timeout):
    r = subprocess.run(argv, capture_output=True, timeout=timeout, env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'}, check=True)
    return r.stdout.decode()


def write_atomic(path, obj):
    tmp = f'{path}.tmp-{os.getpid()}'
    with open(tmp, 'w') as f: json.dump(obj, f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def append_line(path, obj):
    with open(path, 'a') as f: f.write(json.dumps(obj)+'\n'); f.flush(); os.fsync(f.fileno())


class Watchdog:
    def __init__(self, a):
        self.a, self.job, self.dir = a, a.job, a.job+'/watchdog'
        self.deadline = self.deadline_text = None
        self.stop_since = None            # epoch STOP appeared (its own mtime), while present
        self.halted = None

    # ---------------------------------------------------------------- one bounded measurement cycle
    def measure(self):
        a, job, now = self.a, self.job, time.time()
        r = dict(epoch=now)
        procs = tree(job); r['processes'] = len(procs)
        if os.path.lexists(job+'/STOP'):                                   # H-1 STOP periods + the stop grace
            if self.stop_since is None:
                self.stop_since = os.lstat(job+'/STOP').st_mtime
                append_line(self.dir+'/stop-periods.jsonl', dict(kind='start', epoch=self.stop_since, observed=now))
            if procs and now-self.stop_since > a.stop_grace: return f'STOP not honoured within {a.stop_grace:g} s ({len(procs)} study processes)', r
        elif self.stop_since is not None:
            append_line(self.dir+'/stop-periods.jsonl', dict(kind='end', epoch=now)); self.stop_since = None
        dl = job+'/HARD-STOP-UTC.txt'
        if self.deadline is None and os.path.lexists(dl):
            with open(dl) as f: self.deadline_text = f.read(64)
            self.deadline = calendar.timegm(time.strptime(self.deadline_text.strip(), '%Y-%m-%dT%H:%M:%SZ'))
        if self.deadline is None:
            if procs: return 'study processes exist before the deadline file', r
        else:
            with open(dl) as f:
                if f.read(64) != self.deadline_text: return 'deadline file changed', r
            r['deadline'] = self.deadline
            prod = [p for p, _ in procs if not readout(p)]
            if now >= self.deadline and prod and now-self.deadline > a.stop_grace:
                return f'{len(prod)} production study processes alive {a.stop_grace:g} s after the deadline', r
        with open(a.meminfo) as f:
            mem = next(int(x.split()[1])*1024 for x in f if x.startswith('MemAvailable:'))
        r['mem_available'] = mem
        if mem < a.mem_floor: return f'MemAvailable {mem} < {a.mem_floor}', r
        try:
            with open(a.psi) as f: psi = float(f.read().split()[1].split('=')[1])
        except (OSError, IndexError, ValueError): return 'memory PSI unreadable', r
        r['psi_some_avg10'] = psi
        if len(procs) > a.max_procs: return f'{len(procs)} study processes > {a.max_procs}', r
        pss = 0
        for pid, _ in procs:
            try:
                with open(f'/proc/{pid}/smaps_rollup') as f: pss += sum(int(l.split()[1])*1024 for l in f if l.startswith('Pss:'))
            except (FileNotFoundError, ProcessLookupError): continue        # exited since the scan
        r['tree_pss'] = pss
        if pss > a.tree_pss: return f'study PSS {pss} > {a.tree_pss}', r
        disk = int(run_bounded([a.du, '-sb', '--', job], a.du_timeout).split()[0]); r['disk'] = disk
        if disk > a.max_disk: return f'disk {disk} > {a.max_disk}', r
        gpu = int(run_bounded([a.nvidia_smi, '--query-gpu=memory.used', '--format=csv,noheader,nounits'], a.gpu_timeout).split()[0])
        r['gpu_mib'] = gpu
        if gpu > a.gpu_limit_mib: return f'GPU {gpu} MiB > {a.gpu_limit_mib}', r
        return None, r

    # ---------------------------------------------------------------- HALT: marker, then verified one-by-one stops
    def halt(self, reason, readings):
        if self.halted is None:
            self.halted = reason
            try:
                fd = os.open(self.job+'/HALT.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
                os.fchmod(fd, 0o444)                                        # read-only for everyone, whatever the umask
                with os.fdopen(fd, 'w') as f:
                    json.dump(dict(utc=utc(), epoch=time.time(), reason=reason, readings=readings,
                                   label='X4S-4 watchdog HALT; hard stop'), f); f.flush(); os.fsync(f.fileno())
                dfd = os.open(self.job, os.O_RDONLY); os.fsync(dfd); os.close(dfd)
            except FileExistsError:
                pass                                                        # the first HALT reason stands
            if not os.path.lexists(self.job+'/STOP'): os.symlink('HALT.json', self.job+'/STOP')
            append_line(self.dir+'/watchdog.log', dict(utc=utc(), kind='HALT', reason=reason, readings=readings))
        self.kill_tree()

    def kill_tree(self):
        first = {}
        while True:
            procs = tree(self.job)
            if not procs: return
            for pid, start in procs:
                s = stat(pid)
                if s is None or s[0] != start or not marked(pid, self.job): continue      # re-verified right before
                t0 = first.setdefault((pid, start), time.monotonic())
                sig = signal.SIGKILL if time.monotonic()-t0 >= self.a.kill_grace else signal.SIGTERM
                try: os.kill(pid, sig)
                except ProcessLookupError: pass
                append_line(self.dir+'/watchdog.log', dict(utc=utc(), kind='signal', pid=pid, starttime=start, signal=int(sig)))
            time.sleep(1.0)

    # ---------------------------------------------------------------- the loop
    def run(self):
        os.makedirs(self.dir, exist_ok=True)
        if alive(self.job, mine_ok=True): raise SystemExit('a watchdog is already running for this job')
        me = os.getpid()
        write_atomic(self.dir+'/pid.json', dict(pid=me, starttime=stat(me)[0], utc=utc()))
        if os.path.lexists(self.job+'/HALT.json'): self.halted = 'HALT.json present at start'
        while True:
            t0 = time.monotonic(); box = {}
            def cycle():
                try: box['v'] = self.measure()
                except Exception as exc: box['v'] = (f'measurement failed: {exc!r}', {})
            w = threading.Thread(target=cycle, daemon=True); w.start(); w.join(self.a.stall)
            if w.is_alive(): why, readings = f'watchdog cycle stalled > {self.a.stall:g} s', {}
            else: why, readings = box['v']
            if why and self.halted is None: self.halt(why, readings)
            elif self.halted is not None: self.kill_tree()                  # hard stop: nothing may run again
            write_atomic(self.dir+'/heartbeat.json', dict(utc=utc(), epoch=time.time(), pid=me, halted=self.halted,
                                                          readings=readings))
            time.sleep(max(0.0, self.a.cycle-(time.monotonic()-t0)))


def alive(job, mine_ok=False):
    """The recorded watchdog process is alive with its recorded start time (and is not this process)."""
    try:
        with open(job+'/watchdog/pid.json') as f: p = json.load(f)
    except (OSError, ValueError):
        return False
    s = stat(p.get('pid', -1))
    return bool(s and s[0] == p.get('starttime') and s[1] != 'Z' and not (mine_ok and p['pid'] == os.getpid()))


def status(job, max_age=30.0):
    try:
        with open(job+'/watchdog/heartbeat.json') as f: hb = json.load(f)
    except (OSError, ValueError):
        return 'no heartbeat', None
    if not alive(job): return 'watchdog not alive', hb
    if time.time()-hb.get('epoch', 0) > max_age: return 'heartbeat older than 30 s', hb
    if hb.get('halted'): return f"HALTED: {hb['halted']}", hb
    return None, hb


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['start', 'status', 'run']); ap.add_argument('--job', default=DEFAULT_JOB)
    for k, v in dict(cycle=10.0, stall=30.0, stop_grace=180.0, kill_grace=20.0, du_timeout=5.0, gpu_timeout=3.0,
                     mem_floor=24*2**30, max_procs=70, tree_pss=96*2**30, max_disk=100*10**9, gpu_limit_mib=40*1024).items():
        ap.add_argument('--'+k.replace('_', '-'), type=type(v), default=v)
    for k, v in dict(du='/usr/bin/du', nvidia_smi='/usr/bin/nvidia-smi', meminfo='/proc/meminfo', psi='/proc/pressure/memory').items():
        ap.add_argument('--'+k.replace('_', '-'), default=v)
    a = ap.parse_args(argv)
    a.job = os.path.abspath(a.job)
    if a.cmd == 'run':
        Watchdog(a).run()
    elif a.cmd == 'status':
        why, hb = status(a.job); print(json.dumps(dict(ok=why is None, why=why, heartbeat=hb))); raise SystemExit(0 if why is None else 1)
    else:
        os.makedirs(a.job+'/watchdog', exist_ok=True)
        if alive(a.job): raise SystemExit('a watchdog is already running for this job')
        env = {k: v for k, v in os.environ.items() if k != MARK}                  # never part of the study tree
        log = open(a.job+'/watchdog/watchdog.out', 'a')
        p = subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), 'run']+(argv or sys.argv[1:])[1:], stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, env=env, start_new_session=True, close_fds=True)
        t0 = time.time()
        while time.time()-t0 < 3*a.cycle+5:
            why, hb = status(a.job)
            if why is None and hb.get('pid') == p.pid: print(json.dumps(dict(started=p.pid, heartbeat=hb))); return
            if p.poll() is not None: break
            time.sleep(0.2)
        raise SystemExit(f'watchdog did not come up: {status(a.job)[0]}')


if __name__ == '__main__':
    main()
