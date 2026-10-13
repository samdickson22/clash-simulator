"""X4S-4 study-wide process tree, admission and live guards (Sol r1 F9, r2 R2-F3; exploration, NEVER ADOPTABLE).
Stdlib only, Python 3.8+. All I/O goes through x4s4io.

The X4S-4 tree is every owned process group recorded under the job as (pgid, leader starttime): the driver
(driver/driver.pid), fits (receipts/fit-*-launch*.json), reporting supervisors (receipts/phase-*-launch.json), every
supervisor/child group of a games/collect/qual/smoke phase (<phase>/launch.json) and every registered CPU job
(receipts/cpujob-*.json: labeler, O_W generator, acceptance smoke, diagnostic). A group number whose leader
starttime differs is a reused number and owns nothing.

admission(job, add): the tree after adding `add` new processes must hold <= 70, the job <= 100 GB (HR-1: own bounded
disk walk tree_bytes, cached 300 s; unreadable blocks) - the RESERVATION covers the workers a new pool/fit/phase will create.
monitor(job, own=None, pss_limit): the frozen live stop rules for a running owned task - STOP (lexists), the study
hard stop, MemAvailable < 24 GiB (unreadable = breach), memory PSI unreadable/non-finite, the owned task's PSS
> 50 GiB (any unreadable process = breach), tree > 70 processes, disk > 100 GB or unreadable. Returns a reason or None.

r8 (Sol r7, R7-F1..F3 - one mechanism for every long-running or spawning path; see SCRIPTS.md "Guard audit"):
  * Every potentially blocking measurement is bounded: the disk walk (HR-1; was du) has DISK_TIMEOUT (40 s), nvidia-smi 20 s, and
    bounded() runs any measurement with a deadline whose miss is a breach (MeasureTimeout).
  * admit(): dispatch admission (dispatch_ok + admission [+ extra, e.g. GPU]) with every measurement bounded, then the
    cheap STOP/deadline checks LAST.
  * Enforcer: independent expiry - a thread that only does cheap checks (STOP lexists, the immutable deadline, the age
    of the last completed monitor verdict) and never measures, so a stuck scan or native call cannot stall it; STOP,
    the deadline, a breach verdict or no completed verdict for MONITOR_STALE s fires on_breach once.
  * fresh_verdict(): a fresh bounded running-resource verdict, then STOP/deadline LAST - used before packing and before
    any acceptance.
  * guarded_output(): acceptance - an output counts only if a PASSED guard receipt (receipts/guard-*.json, written by
    guard.py after its final fresh guards) names it with its current identity.
  * require_guard(): an owned entry point runs only as the child of a live guard.py runner and ends itself if the
    runner disappears.

r9 (coordinator ruling SR-1): host safety is enforced by the external watchdog.py. The in-process guards remain as
defence in depth. Here:
  * watchdog_ok(): new study work starts only with a live watchdog (fresh heartbeat, not halted).
  * HALT.json counts like STOP in cheap_halt/monitor.
  * h1_reason(): rule H-1. An output whose completion time is at or after a HALT, at or after the deadline, or inside
    a STOP period is never counted. guarded_output enforces it on the guard receipt's completion time; the game
    consumers enforce it on block proofs.
"""
import datetime, errno, math, os, stat, threading, time

import x4s4io as io

MAX_PROCESSES, MAX_DISK_BYTES, DISK_CACHE_SECONDS = 70, 100*10**9, 300
DISK_TIMEOUT = 40                                   # r8: the disk walk is bounded well inside the stop budget (was 900 s)
ENFORCER_TICK, MONITOR_PERIOD, MONITOR_STALE, MEASURE_TIMEOUT = 1.0, 5.0, 75.0, 75.0
MEM_FLOOR, PSS_LIMIT = 24*2**30, 50*2**30
_disk = dict(t=0.0, bytes=None)


def _rec(path, pid_key='pgid', start_key='starttime'):
    try: r = io.read_json(path, 1 << 20)
    except io.Refusal: return None
    g, s = r.get(pid_key), r.get(start_key)
    return (g, s) if isinstance(g, int) and isinstance(s, int) else None


def _glob(directory, prefix, suffix='.json'):
    try: names = io.listdir(directory)
    except io.Refusal: return []
    return [directory+'/'+n for n in names if n.startswith(prefix) and n.endswith(suffix)]


def _phase_launches(job):
    out = []
    for role in ('games', 'collect', 'qual', 'smoke'):
        base = job+'/'+role
        if not io.is_real_dir(base): continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            if 'launch.json' in filenames: out.append(os.path.join(dirpath, 'launch.json'))
    return sorted(out)


def groups(job=None):
    """{(pgid, leader starttime)} of every recorded owned group (own group included)."""
    job = job or io.JOB
    me = io.own_identity(); lead = io.proc_stat(me['pgid'])
    out = {(me['pgid'], lead['starttime'] if lead else me['starttime'])}
    recs = [job+'/driver/driver.pid'] + _glob(job+'/receipts', 'fit-') + _glob(job+'/receipts', 'phase-') \
        + _glob(job+'/receipts', 'cpujob-') + _glob(job+'/receipts', 'calibrate-')    # R5-F2: calibration is owned work
    for p in recs:
        g = _rec(p)
        if g: out.add(g)
    for p in _phase_launches(job):
        for k in ('child', 'supervisor'):
            g = _rec(p, k+'_pgid', k+'_starttime')
            if g: out.add(g)
    return out


def processes(grps):
    pids = set()
    for pgid, start in grps: pids.update(io.owned_pids(pgid, start))
    return sorted(pids)


def pss_bytes(pids):
    """Total PSS, or None if any process's smaps_rollup is unreadable for a reason other than its exit."""
    total = 0
    for pid in pids:
        try:
            with open('/proc/%d/smaps_rollup' % pid) as f:
                total += sum(int(l.split()[1])*1024 for l in f if l.startswith('Pss:'))
        except (FileNotFoundError, ProcessLookupError):
            continue                                          # exited between enumeration and read
        except (PermissionError, OSError, ValueError, IndexError):
            return None
    return total


def mem_available():
    try:
        with open('/proc/meminfo') as f:
            v = next(int(x.split()[1])*1024 for x in f if x.startswith('MemAvailable:'))
        return v if v >= 0 else None
    except Exception:
        return None


def psi_some_avg10():
    """Memory PSI some avg10, or None if unreadable or not a finite number in [0, 100]."""
    try:
        with open('/proc/pressure/memory') as f: v = float(f.read().split()[1].split('=')[1])
    except Exception:
        return None
    return v if math.isfinite(v) and 0.0 <= v <= 100.0 else None


VANISHED = (errno.ENOENT, errno.ENOTDIR)              # HR-1: an entry renamed/removed during the walk (benign)


def tree_bytes(root, timeout, scandir=os.scandir):
    """HR-1 (COORDINATOR 77a01d88): the apparent size of `root` (as `du -sb`: the root and every entry's lstat st_size,
    each inode once) by an own bounded os.scandir/lstat walk. Returns (bytes, vanished). An entry or a directory that
    VANISHES mid-walk (ENOENT, or ENOTDIR for a replaced/vanished parent) is skipped and counted: the study's writers
    rename and remove while it is measured. Every other error raises - a missing or unreadable root (any errno),
    permission, I/O, and running past `timeout` seconds (TimeoutError). Pure stdlib; follows no symlink."""
    end = time.monotonic()+timeout
    st = os.lstat(root)
    if not stat.S_ISDIR(st.st_mode): raise NotADirectoryError(errno.ENOTDIR, 'measurement root is not a directory', root)
    total, vanished, seen, todo = st.st_size, 0, {(st.st_dev, st.st_ino)}, [root]
    while todo:
        d = todo.pop()
        if time.monotonic() > end: raise TimeoutError(errno.ETIMEDOUT, f'tree walk exceeded {timeout:g} s', root)
        try: it = scandir(d)
        except OSError as exc:
            if d != root and exc.errno in VANISHED: vanished += 1; continue
            raise
        with it:
            while True:
                try: e = next(it)
                except StopIteration: break
                except OSError as exc:
                    if d != root and exc.errno in VANISHED: vanished += 1; break
                    raise
                try: s = e.stat(follow_symlinks=False)
                except OSError as exc:
                    if exc.errno in VANISHED: vanished += 1; continue
                    raise
                key = (s.st_dev, s.st_ino)
                if key in seen: continue                          # hard links once, as du
                seen.add(key); total += s.st_size
                if stat.S_ISDIR(s.st_mode): todo.append(e.path)
                if time.monotonic() > end: raise TimeoutError(errno.ETIMEDOUT, f'tree walk exceeded {timeout:g} s', root)
    return total, vanished


def disk_bytes(job=None):
    job = job or io.JOB
    if _disk['bytes'] is None or time.time()-_disk['t'] > DISK_CACHE_SECONDS:
        try:
            _disk['bytes'] = tree_bytes(job, DISK_TIMEOUT)[0]                # HR-1: own walk (was du, which raced renames)
        except OSError:                                                      # incl. TimeoutError: unreadable = None (fail closed)
            _disk['bytes'] = None
        _disk['t'] = time.time()
    return _disk['bytes']


def hard_stop_at(job=None):
    job = job or io.JOB
    text = io.read_text(job+'/HARD-STOP-UTC.txt', 64).strip()
    return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


def hard_stop_passed(job=None):
    try: return datetime.datetime.now(datetime.timezone.utc) >= hard_stop_at(job)
    except (io.Refusal, ValueError): return True              # unreadable deadline = stopped (fail closed)


def admission(job=None, add=0, disk=True):
    """(ok, reason): tree + add <= 70 processes and (if disk) <= 100 GB under the job; unreadable blocks."""
    job = job or io.JOB
    try: n = len(processes(groups(job)))
    except OSError: return False, 'process scan failed'
    if n+add > MAX_PROCESSES: return False, '%d X4S-4 processes + %d new > %d' % (n, add, MAX_PROCESSES)
    if disk:
        b = disk_bytes(job)
        if b is None: return False, 'disk usage unreadable'
        if b > MAX_DISK_BYTES: return False, '%d bytes under the job > %d' % (b, MAX_DISK_BYTES)
    return True, None


def monitor(job=None, own=None, pss_limit=PSS_LIMIT, disk=True, check_psi=True, deadline=True):
    """The frozen live stop rules for a running owned task (own = (pgid, starttime) of that task's group). deadline=False
    only for the post-study readout steps (guard.py --readout: contention, reduce, report)."""
    job = job or io.JOB
    if io.lexists(job+'/HALT.json') or io.lexists(job+'/STOP'): return 'owned_STOP'
    if deadline and hard_stop_passed(job): return 'hard_stop_time'
    mem = mem_available()
    if mem is None or mem < MEM_FLOOR: return 'memory_guard'
    if check_psi and psi_some_avg10() is None: return 'psi_unreadable'
    if own is not None:
        p = pss_bytes(io.owned_pids(*own))
        if p is None or p > pss_limit: return 'pss_guard'
    ok, why = admission(job, 0, disk)
    if not ok: return 'study_tree_cap: '+why
    return None


def register(job, name):
    """Record this CPU job's process group (with leader starttime) so the driver, supervisors and admission count it."""
    me = io.own_identity(); lead = io.proc_stat(me['pgid'])
    path = '%s/receipts/cpujob-%s-%d.json' % (job, name, me['pid'])
    io.write_json_once(path, dict(name=name, pid=me['pid'], pgid=me['pgid'], starttime=lead['starttime'] if lead else me['starttime'],
                                  utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), roles=('receipts',), mode=0o644)
    return path


def dispatch_ok():
    """(ok, reason) for STARTING new work (R3-F2): MemAvailable >= 24 GiB and memory PSI readable and <= 10. This only
    inhibits dispatch; high PSI is never itself a kill threshold (the frozen kill rules are memory/PSS)."""
    mem, psi = mem_available(), psi_some_avg10()
    if mem is None or mem < MEM_FLOOR: return False, 'MemAvailable below 24 GiB or unreadable'
    if psi is None or psi > 10.0: return False, 'memory PSI unreadable or > 10'
    return True, None


class MeasureTimeout(Exception):
    pass


def bounded(fn, timeout=None):
    """Run a potentially blocking measurement in a daemon thread; its value, its exception, or MeasureTimeout if it has
    not completed within `timeout` s (the abandoned thread can no longer influence the caller)."""
    timeout = MEASURE_TIMEOUT if timeout is None else timeout
    box = {}
    def run():
        try: box['v'] = fn()
        except BaseException as exc: box['e'] = exc
    t = threading.Thread(target=run, daemon=True); t.start(); t.join(timeout)
    if t.is_alive(): raise MeasureTimeout(f'measurement exceeded {timeout:g} s')
    if 'e' in box: raise box['e']
    return box['v']


def cheap_halt(job=None, deadline=True):
    """HALT, STOP (lexists, so a dangling link counts) and the immutable deadline - no measurement."""
    job = job or io.JOB
    if io.lexists(job+'/HALT.json'): return 'HALT'
    if io.lexists(job+'/STOP'): return 'owned_STOP'
    if deadline and hard_stop_passed(job): return 'hard_stop_time'
    return None


def admit(job=None, add=0, extra=None, deadline=True, timeout=None):
    """R7-F2: dispatch admission for new work - cheap halt, then dispatch_ok (MemAvailable >= 24 GiB, PSI readable and
    <= 10), admission(add) and `extra` (e.g. a GPU rule) inside ONE bounded measurement (a miss refuses), then the cheap
    STOP/deadline checks again LAST. Returns None or the refusal reason."""
    job = job or io.JOB
    why = cheap_halt(job, deadline)
    if why: return 'admission: '+why
    def measure():
        _disk['bytes'] = None                            # R8-F3: admission measures disk now, not from the cache
        ok, w = dispatch_ok()
        if not ok: return w
        ok, w = admission(job, add)
        if not ok: return w
        return extra() if extra else None
    try: why = bounded(measure, timeout)
    except MeasureTimeout as exc: why = f'admission measurement missed its deadline ({exc})'
    if why: return 'admission: '+why
    why = cheap_halt(job, deadline)
    return 'admission: '+why if why else None


def fresh_verdict(job=None, own=None, extra=None, deadline=True, timeout=None):
    """R7-F1: a FRESH running-resource verdict (monitor [+ extra, e.g. the GPU rule]) inside one bounded measurement (a
    miss is a breach), then the cheap STOP/deadline checks LAST. High readable PSI is not a breach here (frozen rule)."""
    job = job or io.JOB
    def measure():
        _disk['bytes'] = None                            # R8-F3: a fresh verdict measures disk now
        return monitor(job, own=own, deadline=deadline) or (extra() if extra else None)
    try: why = bounded(measure, timeout)
    except MeasureTimeout: why = 'measurement_timeout'
    return why or cheap_halt(job, deadline)


class Enforcer:
    """R7-F2: independent expiry. A daemon thread that every ENFORCER_TICK s performs ONLY cheap checks - STOP (lexists),
    the immutable deadline (unless deadline=False) and the age of the last completed monitor verdict - and never calls
    a potentially blocking measurement, so a stuck scan or native call cannot stall it. The measuring side reports each
    completed verdict with verdict(why). STOP, the deadline, a breach verdict or no completed verdict for MONITOR_STALE s
    ('monitor_stale') calls on_breach(reason) exactly once, from the thread that detected it. active() may restrict
    the staleness rule to periods when guarded work is live."""
    def __init__(self, job, on_breach, deadline=True, active=None):
        self.job, self.on_breach, self.deadline, self.active = job, on_breach, deadline, active
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.last, self.fired, self.thread = time.monotonic(), None, None

    def start(self):
        self.last = time.monotonic()
        self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()
        return self

    def stop(self): self.stopped.set()

    def arm(self):
        """Re-arm for a new guarded child (long-lived parents such as the driver): clears the fired state."""
        with self.lock: self.fired = None
        self.last = time.monotonic()

    def verdict(self, why):
        self.last = time.monotonic()
        if why: self.fire(why)

    def fire(self, why):
        with self.lock:
            if self.fired: return
            self.fired = why
        self.on_breach(why)

    def check(self):
        """One cheap evaluation (the thread's step); returns the reason it fired, or None."""
        why = cheap_halt(self.job, self.deadline)
        if why is None and (self.active is None or self.active()) and time.monotonic()-self.last > MONITOR_STALE:
            why = 'monitor_stale'
        if why: self.fire(why)
        return why

    def _run(self):
        while not self.stopped.wait(ENFORCER_TICK):
            try: self.check()
            except Exception as exc: self.fire(f'enforcer_failed: {exc!r}')


def output_identity(path):
    """A sealed directory's identity is the SHA-256 of its manifest.json; a file's is its SHA-256."""
    path = str(path)
    return io.sha256_file(path+'/manifest.json') if io.is_real_dir(path) else io.sha256_file(path)


WATCHDOG_MAX_AGE = 30.0


def watchdog_ok(job=None):
    """SR-1: None if the external watchdog for this job is alive (recorded pid + start time) with a heartbeat younger
    than 30 s and not halted; else the reason. New study work (guard.py, supervise.py, driver launches) requires it."""
    job = job or io.JOB
    try:
        p = io.read_json(job+'/watchdog/pid.json', 1 << 16); hb = io.read_json(job+'/watchdog/heartbeat.json', 1 << 20)
    except io.Refusal as exc:
        return f'watchdog files unreadable: {exc}'
    st = io.proc_stat(p.get('pid', -1))
    if not (st and st['starttime'] == p.get('starttime') and st['state'] != 'Z'): return 'watchdog not alive'
    if hb.get('pid') != p.get('pid') or time.time()-float(hb.get('epoch', 0)) > WATCHDOG_MAX_AGE: return 'watchdog heartbeat stale'
    if hb.get('halted') or io.lexists(job+'/HALT.json'): return 'HALT'
    return None


def stop_periods(job):
    """[(start, end or None)] epochs of the durable STOP history (watchdog observations, `watchdog.py stop/resume`), plus
    a STOP present now. R9-F5: the history file is created by the watchdog at start; a missing or unreadable history
    raises (H-1 then fails closed), and a period keeps its EARLIEST recorded start until an end closes it."""
    out, open_ = [], None
    path = job+'/watchdog/stop-periods.jsonl'
    if not io.lexists(path): raise ValueError('STOP history unavailable (no watchdog/stop-periods.jsonl)')
    for line in io.read_text(path, 64 << 20).splitlines():
        e = io.loads_strict(line.encode())
        if e.get('kind') == 'start':
            open_ = float(e['epoch']) if open_ is None else min(open_, float(e['epoch']))
        elif e.get('kind') == 'end' and open_ is not None: out.append((open_, float(e['epoch']))); open_ = None
    if open_ is not None: out.append((open_, None))
    if io.lexists(job+'/STOP'): out.append((os.lstat(job+'/STOP').st_mtime, None))
    return out


H1_MARGIN = 0.05          # s: file mtimes use the kernel's coarse clock (<= 1 tick behind time.time()); boundaries widen


def h1_reason(job, t, deadline=True):
    """Rule H-1 for an output completed at epoch t: 'after HALT', 'after deadline', 'during STOP', or None (counts).
    Unreadable HALT/deadline evidence fails closed. deadline=False only for the post-study readout (guard --readout
    receipts: contention, reduce, report), which follows the stop by design (E8); HALT and STOP still apply."""
    job = job or io.JOB
    if io.lexists(job+'/HALT.json'):
        try: h = float(io.read_json(job+'/HALT.json', 1 << 20)['epoch'])
        except (io.Refusal, KeyError, TypeError, ValueError): return 'HALT marker unreadable'
        if t >= h-H1_MARGIN: return 'after HALT'
    try: dl = hard_stop_at(job).timestamp()
    except (io.Refusal, ValueError): return 'deadline unreadable'
    if deadline and t >= dl-H1_MARGIN: return 'after deadline'
    try: periods = stop_periods(job)
    except (io.Refusal, ValueError, KeyError) as exc: return f'STOP periods unreadable: {exc}'
    if any(a-H1_MARGIN <= t and (b is None or t < b+H1_MARGIN) for a, b in periods): return 'during STOP'
    return None


def completed_at(path):
    """Completion time of a written output: its own mtime (single-link regular file, lstat; no read)."""
    return io.stat_leaf(str(path)).st_mtime


def h1_path(job, path):
    """Rule H-1 for one completed file (or a sealed directory's manifest.json)."""
    path = str(path)
    return h1_reason(job, completed_at(path+'/manifest.json' if io.is_real_dir(path) else path))


def ready_student(job, sid):
    """R9-F6: a runtime READY counts at EVERY consumer only if it completed in time (rule H-1); returns its student."""
    p = f'{job}/rt-{sid}/READY.json'
    why = h1_path(job, p)
    io.require(why is None, 'h1', f'{sid} READY completed {why} (rule H-1: never counted)')
    return io.read_json(p, 4 << 20)['student']


READOUT_OUTPUTS = {'contention.py': ('receipts/contention-exclusion.json',), 'reduce.py': ('analysis/results.json',), 'write_report.py': ()}


def readout_invocation(argv):
    """R9-F3: the script of an allowed readout invocation - exactly `/bin/bash <repo>/reports/explore/x4s3/runtime.sh
    <repo>/reports/explore/x4s4/<contention|reduce|write_report>.py ...` (the same staged repo) - else None."""
    if len(argv) < 3 or argv[0] != '/bin/bash' or not argv[1].endswith('/reports/explore/x4s3/runtime.sh'): return None
    repo = argv[1][:-len('/reports/explore/x4s3/runtime.sh')]
    for name in READOUT_OUTPUTS:
        if argv[2] == f'{repo}/reports/explore/x4s4/{name}': return name
    return None


def readout_exempt(job, r, path):
    """The deadline exemption of H-1 applies only to a --readout receipt whose argv is an allowed readout invocation and
    only to that script's declared output."""
    name = readout_invocation(r.get('argv') or []) if r.get('readout') is True else None
    return bool(name) and str(path) in tuple(f'{job}/{o}' for o in READOUT_OUTPUTS[name])


def raw_evidence(job, game_dir):
    """R9-F6/F7: a sealed raw game counts for packing or resume only with its producer's passed, in-time evidence: a
    label game (data/raw-<set>/<arm>/game-NNNN) must be listed with its current manifest SHA in a guarded label
    receipt; an O_W game (data/raw-OW/game-NNNNN) in the guarded selection. Its own completion must pass H-1, and so
    must the evidence (guarded_output). Returns None or the reason it does not count."""
    job = job or io.JOB; game_dir = str(game_dir)
    if not io.lexists(game_dir+'/manifest.json'): return 'not sealed'
    why = h1_path(job, game_dir)
    if why: return f'completed {why}'
    msha = io.sha256_file(game_dir+'/manifest.json')
    parent, name = game_dir.rsplit('/', 1)
    if parent == f'{job}/data/raw-OW':
        sel = f'{job}/data/raw-OW-selection.json'
        if not io.lexists(sel) or guarded_output(job, sel) is None: return 'no passed, in-time O_W selection'
        g = int(name.split('-')[1])
        return None if any(r.get('g') == g and r.get('manifest_sha256') == msha for r in io.read_json(sel, 64 << 20).get('games', [])) \
            else 'not in the guarded O_W selection with this manifest'
    arm, rawset = parent.rsplit('/', 1)[1], parent.rsplit('/', 2)[1]
    if not rawset.startswith('raw-'): return 'unknown raw producer'
    index = int(name.split('-')[1])
    for n in sorted(io.listdir(f'{job}/data')):
        p = f'{job}/data/{n}'
        if n.startswith(f'label-receipt-{rawset[4:]}-') and n.endswith('.json') and guarded_output(job, p) is not None:
            if [arm, index, msha] in io.read_json(p, 64 << 20).get('game_manifests', []): return None
    return 'not in a passed, in-time label receipt with this manifest'


def guarded_output(job, path):
    """R7 acceptance: the PASSED guard receipt (receipts/guard-*.json, written by guard.py only after the child exited 0
    and its final fresh guards held) that names `path` with its CURRENT identity, else None."""
    job = job or io.JOB; path = str(path)
    if not io.lexists(path): return None
    want = output_identity(path)
    for n in sorted(_names(job+'/receipts', 'guard-')):
        try: r = io.read_json(f'{job}/receipts/{n}', 16 << 20)
        except io.Refusal: continue
        if isinstance(r, dict) and r.get('passed') is True and r.get('schema') == 'x4s4.guard.v1' \
                and ((r.get('outputs') or {}).get(path) == want or (r.get('new_files') or {}).get(path) == want):
            if h1_reason(job, completed_at(f'{job}/receipts/{n}'), deadline=not readout_exempt(job, r, path)) is None: return r   # H-1
    return None


def _names(directory, prefix):
    try: return [n for n in io.listdir(directory) if n.startswith(prefix) and n.endswith('.json')]
    except io.Refusal: return []


_WATCHDOG = {}


def require_guard(name=None):
    """R7: an owned long-running entry point runs only as the child of a live guard.py runner (X4S4_GUARD =
    '<pid>:<starttime>:<name>', that process alive with that start time); a watchdog thread ends this process (exit
    70) if the runner disappears, so the work never outlives its enforcement. Returns the runner identity."""
    spec = os.environ.get('X4S4_GUARD', '')
    try:
        pid, start, gname = spec.split(':', 2); pid, start = int(pid), int(start)
    except ValueError:
        raise SystemExit(f'{name or "this step"} runs only under reports/explore/x4s4/guard.py (X4S4_GUARD unset or malformed)')
    def alive():
        st = io.proc_stat(pid); return st is not None and st['starttime'] == start and st['state'] != 'Z'
    if not alive(): raise SystemExit(f'guard runner {pid} is not alive')
    if spec not in _WATCHDOG:
        def loop():
            while alive(): time.sleep(2.0)
            os._exit(70)
        t = threading.Thread(target=loop, daemon=True); t.start(); _WATCHDOG[spec] = t
    return dict(pid=pid, starttime=start, name=gname)


GATES = {'O': ('onpolicy', 'O-VERIFIED.json'), 'holdout': ('onpolicy-holdout', 'HOLDOUT-VERIFIED.json'),
         'OW': ('onpolicy-w', 'OW-VERIFIED.json')}


GATE_SHARED = ('batches', 'rows', 'roots', 'rows_per_arm', 'single_candidate_root_share', 'sources_sha256')
GATE_IDS = {'O': ('label_plan_sha256', 'label_receipts_sha256', 'parity_receipt_sha256'),
            'holdout': ('label_plan_sha256', 'label_receipts_sha256', 'parity_receipt_sha256'),
            'OW': ('selection_sha256', 'o_gate_sha256', 'acceptance_sha256', 'label_receipts_sha256')}


def authenticate_gate(job, mode):
    """R3-F1/R3-F3/R4-F1: a consumer of a verified set re-authenticates it NOW.
      * the verifier receipt is the one the gate pins (SHA), has the complete successful shape (passed, sealed, mode,
        the shared fields and the mode's identity fields) and AGREES with the gate on every shared field - the exact
        batch list (names, manifest SHAs, rows, roots, games), rows, roots, rows per arm, single-candidate share, the
        source-list SHA - and on every input identity (label plan / receipts / parity, or selection / O gate /
        acceptance), so a gate re-pinned to other batches no longer matches its receipt;
      * the exact batch directory inventory equals that list;
      * every batch's complete seal re-verifies and its manifest SHA equals the pin.
    Returns (batch directory paths, gate SHA-256, gate document)."""
    job = job or io.JOB
    root, name = GATES[mode]
    gate_path, rdir = f'{job}/data/{name}', f'{job}/data/{root}'
    io.require(guarded_output(job, gate_path) is not None, 'gate', f'{name} has no passed guard receipt (R7: guarded acceptance)')
    g = io.read_json(gate_path, 64 << 20)
    io.require(isinstance(g, dict) and g.get('mode') == mode and g.get('batches'), 'gate', f'{name} is not a {mode} gate')
    rec_path = rdir+'/VERIFY-RECEIPT.json'
    io.require(io.sha256_file(rec_path) == g.get('receipt_sha256'), 'gate', f'{mode} verifier receipt differs from the gate pin')
    rec = io.read_json(rec_path, 64 << 20)
    io.require(isinstance(rec, dict) and rec.get('passed') is True and rec.get('sealed') is True and rec.get('mode') == mode,
               'gate', f'{mode} verifier receipt not a passed, sealed {mode} verification')
    for k in GATE_SHARED + GATE_IDS[mode]:
        io.require(k in rec and k in g, 'gate', f'{mode} receipt/gate lacks {k}')
        io.require(rec[k] == g[k], 'gate', f'{mode} gate field {k} differs from its verifier receipt')
    names = [b['name'] for b in rec['batches']]
    io.require(len(set(names)) == len(names), 'gate', f'{mode} receipt lists a batch twice')
    present = sorted(n for n in io.listdir(rdir) if n not in ('VERIFY-RECEIPT.json', 'pack-log.txt'))
    io.require(present == sorted(names), 'gate', f'{mode} batch inventory differs from the gate ({present} vs {sorted(names)})')
    out = []
    for b in rec['batches']:
        d = f"{rdir}/{b['name']}"
        _, msha = io.verify_sealed_dir(d)
        io.require(msha == b['manifest_sha256'], 'gate', f"{mode} batch {b['name']} differs from the gate's manifest pin")
        out.append(d)
    return out, io.sha256_file(gate_path), g
