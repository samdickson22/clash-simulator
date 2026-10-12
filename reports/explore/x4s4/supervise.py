"""X4S-4 supervisor on 127x01 (exploration, NEVER ADOPTABLE). Copied from X4S-3 unchanged except
(1) --script: the child script is x4s3/run.py (default) or x4s4/collect.py (same CLI); (2) each census record
adds foreign_cores_host (PLAN r3 C5/R2-9): host-wide CPU time, over the census interval, of every process outside
the X4S-4 process tree (this supervisor's group, its child group, the driver group and every fit group named in
<job>/driver/driver.pid and <job>/receipts/fit-*-launch*.json), on any core, in cores; and (3) reduced_concurrency
(E7): true when this phase runs with fewer than its full worker count (console-user cap) or a console seat is present.
X4S-3 docstring follows.

X4S-3 supervisor on 127x01 (exploration, NEVER ADOPTABLE). Copied from X4S.

Deltas: host 127x01, nice 10, games on physical cores 0-49 only (1-core lanes or
5-core slots), one runtime copy per student (--rt), console-user yield via
fleet-console-users, PSI logged (the driver gates dispatch on it), 12 h hard stop passed explicitly.

Owns exactly one child process group (run.py + its fork pool). Polls every 10 s:
STOP file, hard stop time, host MemAvailable floor and the owned tree's PSS cap.
On any stop it signals only its own child process group, escalates to SIGKILL,
verifies that the group is empty and exits; it never uses pattern kills.
"""
import argparse, datetime, hashlib, json, os, resource, signal, socket, subprocess, time
from pathlib import Path


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def who():
    try: return subprocess.run(['who'], capture_output=True, text=True, timeout=5).stdout
    except Exception as exc: return f'who failed: {exc!r}'
def console_users():
    try:
        r = subprocess.run([os.path.expanduser('~/.local/bin/fleet-console-users')], capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip().split()[0])
    except Exception:
        return 0 if not who().strip() else 1  # helper failed: fall back to plain who
_foreign_prev = {}
_foreign_t = None
def x4s4_pgids(job, child_pgid):
    """Process groups of the X4S-4 tree: this supervisor, its child, the driver and every fit (from receipts)."""
    groups = {os.getpgrp(), child_pgid}
    for f in [job/'driver'/'driver.pid', *sorted((job/'receipts').glob('fit-*-launch*.json'))]:
        try: groups.add(int(json.loads(f.read_text())['pgid']))
        except (FileNotFoundError, ValueError, KeyError, TypeError): pass
    return groups
def foreign_cores(job, child_pgid):
    """Host-wide cores' worth of CPU since the previous call by processes outside the X4S-4 tree (any core)."""
    global _foreign_t
    hz = os.sysconf('SC_CLK_TCK'); t = time.monotonic(); total = 0; seen = {}
    ours = x4s4_pgids(job, child_pgid)
    for d in Path('/proc').iterdir():
        if not d.name.isdigit(): continue
        try:
            f = (d/'stat').read_text().rsplit(')', 1)[1].split()
            pgid, ticks = int(f[2]), int(f[11])+int(f[12])
        except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
            continue
        if pgid in ours: continue
        pid = int(d.name); seen[pid] = ticks
        if pid in _foreign_prev: total += max(0, ticks-_foreign_prev[pid])
    dt = None if _foreign_t is None else t-_foreign_t
    _foreign_prev.clear(); _foreign_prev.update(seen); _foreign_t = t
    return None if not dt else total/hz/dt
def psi_some_avg10():
    try: return float(Path('/proc/pressure/memory').read_text().split()[1].split('=')[1])
    except Exception: return 0.
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def meminfo(key='MemAvailable:'):
    return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(key)))*1024


def group(pgid):
    pids = []
    for d in Path('/proc').iterdir():
        if d.name.isdigit():
            try:
                if int((d/'stat').read_text().rsplit(')', 1)[1].split()[2]) == pgid:
                    pids.append(int(d.name))
            except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
                pass
    return pids


def pss(pids):
    total = 0
    for pid in pids:
        try:
            for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
                if line.startswith('Pss:'):
                    total += int(line.split()[1])*1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--rt', type=Path, required=True)
    ap.add_argument('--phase', required=True)
    ap.add_argument('--range', choices=['reporting', 'smoke', 'qualification'], required=True)
    ap.add_argument('--indices', type=Path, required=True)
    ap.add_argument('--workers', type=int)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--arms', nargs='+')
    ap.add_argument('--stop-at', required=True)
    ap.add_argument('--script', default='reports/explore/x4s3/run.py',
                    choices=['reports/explore/x4s3/run.py', 'reports/explore/x4s4/collect.py'])
    a = ap.parse_args()
    job = a.job
    host = socket.gethostname()
    if not (host == '127x01' and os.sched_getaffinity(0) == set(range(50))): raise SystemExit("supervise.py: check failed: host == '127x01' and os.sched_getaffinity(0) == set(range(50))")
    if not (os.getpriority(os.PRIO_PROCESS, 0) == 10 and os.sched_getscheduler(0) == os.SCHED_OTHER): raise SystemExit('supervise.py: check failed: os.getpriority(os.PRIO_PROCESS, 0) == 10 and os.sched_getscheduler(0) == os.SCHED_OTHER')
    stop_at = datetime.datetime.strptime(a.stop_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    console = who(); seats = console_users()
    config = a.config or a.rt/'repo/reports/explore/x4s3/plan.json'
    arms = a.arms or list(json.loads(config.read_text())['arms'])
    width = 1 if all(json.loads(config.read_text())['arms'][x]['threads'] == 1 for x in arms) else 5
    workers = a.workers or (50//width)
    if seats: workers = min(workers, 16//width)  # <=16 game processes with a console user
    if not (1 <= workers*width <= 50): raise SystemExit('supervise.py: check failed: 1 <= workers*width <= 50')
    out = job/a.phase
    if not (not out.exists()): raise SystemExit('fresh output directory per phase')
    out.mkdir(parents=True)
    cmd = ['taskset', '-c', f'0-{workers*width-1}', 'env', f'X4S3_RT={a.rt}', 'bash', str(a.rt/'repo/reports/explore/x4s3/runtime.sh'),
           a.script, '--config', str(config), '--out', str(out),
           '--workers', str(workers), '--indices', str(a.indices), '--range', a.range]
    if a.arms:
        cmd += ['--arms', *a.arms]
    if (job/'STOP').exists():
        (out/'stop-reason.json').write_text(json.dumps(dict(utc=utc(), reason='STOP present before launch'))+'\n')
        raise SystemExit(3)
    t0 = time.monotonic(); before = resource.getrusage(resource.RUSAGE_CHILDREN)
    reason = None; min_mem = meminfo(); max_pss = 0
    log = (out/'worker.log').open('a')
    child = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    pgid = child.pid
    (out/'launch.json').write_text(json.dumps(dict(
        utc=utc(), host=host, supervisor_pid=os.getpid(), supervisor_pgid=os.getpgrp(), child_pid=child.pid,
        child_pgid=pgid, command=cmd, who=console, console_seats=seats, workers=workers, lane_width=width, slot_physical_cpus=list(range(workers*width)), runtime=str(a.rt),
        indices_sha256=sha(a.indices), config_sha256=sha(config), stop_at=a.stop_at, script=a.script), indent=2)+'\n')

    requested = []
    def stop(why):
        # Bounded: <=45 s TERM grace + <=60 s KILL grace; idempotent.
        nonlocal reason
        if reason is not None:
            return
        reason = why
        (out/'stop-reason.json').write_text(json.dumps(dict(utc=utc(), reason=reason))+'\n')
        for sig, grace in ((signal.SIGTERM, 45), (signal.SIGKILL, 60)):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass
            end = time.monotonic()+grace
            while time.monotonic() < end:
                child.poll()
                if not group(pgid):
                    return
                time.sleep(1)

    # Handlers only record the request; the main loop performs the bounded stop.
    signal.signal(signal.SIGTERM, lambda s, f: requested.append('supervisor_SIGTERM'))
    signal.signal(signal.SIGINT, lambda s, f: requested.append('supervisor_SIGINT'))
    rc = None
    try:
        while True:
            if requested:
                stop(requested[0]); break
            if child.poll() is not None:
                if group(pgid):
                    stop('runner_exited_with_live_workers')
                break
            mem = meminfo(); min_mem = min(min_mem, mem)
            tree = pss(group(pgid)); max_pss = max(max_pss, tree)
            if (job/'STOP').exists():
                stop('owned_STOP'); break
            if datetime.datetime.now(datetime.timezone.utc) >= stop_at:
                stop('hard_stop_time'); break
            # Kill only on real memory exhaustion; memory PSI (logged in census) gates new dispatch in the driver.
            if mem < 24*2**30 or tree > 50*2**30:
                stop('memory_guard'); break
            if not seats and console_users():
                stop('console_user'); break
            progress = dict(utc=utc(), host=host, phase=a.phase, completed_games=len(list((out/'games').glob('*.json'))),
                            complete_blocks=len(list((out/'blocks').glob('*.json'))), memavailable_GiB=mem/2**30,
                            owned_pss_GiB=tree/2**30, psi_some_avg10=psi_some_avg10(), foreign_cores_host=foreign_cores(job, pgid), child_pgid=pgid, workers=workers, full_workers=50//width,
                            console_seats=(seats_now := console_users()), reduced_concurrency=bool(workers < 50//width or seats_now))
            tmp = out/'progress.tmp'; tmp.write_text(json.dumps(progress)+'\n'); tmp.replace(out/'progress.json')
            with (out/'census.jsonl').open('a') as census:
                census.write(json.dumps(progress)+'\n')
            for _ in range(10):
                if requested or child.poll() is not None or (job/'STOP').exists():
                    break
                time.sleep(1)
    except BaseException as exc:
        stop(f'supervisor_exception: {exc!r}')
    finally:
        if group(pgid):
            stop(reason or 'supervisor_finally')
            if group(pgid):  # stop() returns early if already stopping; force once more
                try: os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError: pass
                time.sleep(2)
        rc = child.poll()
    left = group(pgid)
    after = resource.getrusage(resource.RUSAGE_CHILDREN); own = resource.getrusage(resource.RUSAGE_SELF)
    result = dict(utc=utc(), host=host, returncode=rc, reason=reason, remaining_group_pids=left,
                  min_memavailable_GiB=min_mem/2**30, max_owned_pss_GiB=max_pss/2**30,
                  wall_seconds=time.monotonic()-t0,
                  children_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  parent_cpu_seconds=own.ru_utime+own.ru_stime,
                  complete_blocks=len(list((out/'blocks').glob('*.json'))))
    (out/'supervisor-exit.json').write_text(json.dumps(result, indent=2)+'\n')
    raise SystemExit(0 if (rc == 0 and reason is None) else 1)


if __name__ == '__main__':
    main()
