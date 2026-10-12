"""X4S-4 study-wide process tree, admission and live guards (Sol r1 F9, r2 R2-F3; exploration, NEVER ADOPTABLE).
Stdlib only, Python 3.8+. All I/O goes through x4s4io.

The X4S-4 tree is every owned process group recorded under the job as (pgid, leader starttime): the driver
(driver/driver.pid), fits (receipts/fit-*-launch*.json), reporting supervisors (receipts/phase-*-launch.json), every
supervisor/child group of a games/collect/qual/smoke phase (<phase>/launch.json) and every registered CPU job
(receipts/cpujob-*.json: labeler, O_W generator, acceptance smoke, diagnostic). A group number whose leader
starttime differs is a reused number and owns nothing.

admission(job, add): the tree after adding `add` new processes must hold <= 70, the job <= 100 GB (du, cached
300 s; unreadable blocks) - the RESERVATION covers the workers a new pool/fit/phase will create.
monitor(job, own=None, pss_limit): the frozen live stop rules for a running owned task - STOP (lexists), the study
hard stop, MemAvailable < 24 GiB (unreadable = breach), memory PSI unreadable/non-finite, the owned task's PSS
> 50 GiB (any unreadable process = breach), tree > 70 processes, disk > 100 GB or unreadable. Returns a reason or None.
"""
import datetime, math, os, time

import x4s4io as io

MAX_PROCESSES, MAX_DISK_BYTES, DISK_CACHE_SECONDS = 70, 100*10**9, 300
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


def disk_bytes(job=None):
    job = job or io.JOB
    if _disk['bytes'] is None or time.time()-_disk['t'] > DISK_CACHE_SECONDS:
        try:
            r = io.run_checked(['/usr/bin/du', '-sb', '--', job], 900, 4096, env={'LC_ALL': 'C'})
            v = int(r.stdout.split()[0]); _disk['bytes'] = v if v >= 0 else None
        except (io.Refusal, ValueError, IndexError):
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


def monitor(job=None, own=None, pss_limit=PSS_LIMIT, disk=True, check_psi=True):
    """The frozen live stop rules for a running owned task (own = (pgid, starttime) of that task's group)."""
    job = job or io.JOB
    if io.lexists(job+'/STOP'): return 'owned_STOP'
    if hard_stop_passed(job): return 'hard_stop_time'
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
